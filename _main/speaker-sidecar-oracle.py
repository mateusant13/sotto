#!/usr/bin/env python
"""ORACLE: THE WRITER HALF -- BUFFER, OFFSET, ATOMIC PUBLISH, HONEST ERRORS.

The reader half is gated by `_main/speaker-id-oracle.py` (70/70 arms, 11/11
mutants). This gates the other half, `worker/speaker_sidecar.py`, and it exists
for ONE reason above all.

THE OFFSET IS THE WHOLE JOB. Diarization runs on a 20-second WINDOW and returns
times counted from the start of that window -- 1,0 s means "1,0 s into the bit I
handed the model". The captions the panel paints are timed from the moment the
capture started, which on a real call is an hour earlier. Forget to add the
window's offset and nothing crashes, nothing logs an error and the badge looks
entirely plausible: every line is simply attributed to whichever stranger spoke
at that offset in some earlier minute. It is the worst failure a caption can
have, because the owner cannot tell it is wrong.

So the arms here are mostly about arithmetic, and the two historical mutators
are the ones that would put a plausible lie on screen:

    the offset       a window starting at 300 s must publish 301,0 s
    the buffer       bounded to the window; an hour-long call keeps 20 s
    atomicity        a reader never observes a half-written payload
    honesty          a diarizer that raises costs a payload, never the app

THE NEGATIVE ARM breaks the writer four ways. Three of the four produce output
that is *plausible* and *wrong*, which is exactly why they are tested.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import time

REPO = r"H:\sotto"
MODULE_PATH = os.path.join(REPO, "worker", "speaker_sidecar.py")
BRIDGE_PATH = os.path.join(REPO, "worker", "speaker_bridge.py")

EXIT_PASS, EXIT_FAIL = 0, 1
FORBIDDEN_AT_IMPORT = ("numpy", "sherpa_onnx", "soundfile", "onnxruntime",
                       "torch", "webview")


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def battery(mod) -> list:
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    # --- the buffer is bounded, and knows where it starts ------------------
    buf = mod.RingBuffer(rate=100, window_s=1.0)          # capacity 100
    chk(buf.capacity == 100, "capacity is rate x window", repr(buf.capacity))
    for i in range(10):                                    # 10 s into a 1 s window
        buf.push([0.1] * 50, i * 0.5)
    chk(len(buf) == 100, "the buffer refuses to grow past its window",
        "%d samples" % len(buf))
    chk(abs(buf.window_duration_s() - 1.0) < 1e-9,
        "it holds exactly one window", "%.3f s" % buf.window_duration_s())

    # The offset arithmetic depends on this: 10 pushes x 50 samples at 100 Hz is
    # 5,0 s of audio laid down from t=0,0, and a 1,0 s window keeps the last one
    # -- so the first retained sample is the one at 4,0 s.
    chk(abs(buf.start_t - 4.0) < 1e-9, "start_t tracks the oldest retained sample",
        "%.3f" % buf.start_t)

    empty = mod.RingBuffer(rate=100, window_s=1.0)
    empty.push([], 5.0)
    chk(len(empty) == 0, "an empty push costs nothing")

    # --- THE OFFSET --------------------------------------------------------
    fake = {"segments": [{"start": 1.0, "end": 3.0, "speaker": 0},
                         {"start": 4.0, "end": 6.5, "speaker": 1}]}
    moved = mod.to_absolute(fake, 300.0)
    chk(abs(moved["segments"][0]["start"] - 301.0) < 1e-9,
        "a window at 300 s publishes a segment at 301 s",
        "%.3f" % moved["segments"][0]["start"])
    chk(abs(moved["segments"][1]["end"] - 306.5) < 1e-9,
        "and its end likewise", "%.3f" % moved["segments"][1]["end"])
    chk(moved.get("window_start_abs") == 300.0,
        "the payload says which window it came from")
    chk(mod.to_absolute(fake, 0.0)["segments"][0]["start"] == 1.0,
        "a window at zero is the identity, as it must be")
    chk(mod.to_absolute(None, 10.0) == {}, "no payload in, no payload out")
    chk(mod.to_absolute({"segments": None}, 10.0)["segments"] == [],
        "a payload with no segments is empty, not a crash")
    chk(len(mod.to_absolute(
        {"segments": [{"start": "x", "end": 1.0}, {"nope": 1}, "junk", None]}, 5.0
    )["segments"]) == 0, "junk rows cost rows, not the run")
    chk(mod.to_absolute(fake, 10.0)["segments"][0]["speaker"] == 0,
        "the speaker survives the move")

    # --- one tick, end to end, on a synthetic call -------------------------
    tmp = tempfile.mkdtemp(prefix="sidecar-oracle-")
    try:
        out_file = os.path.join(tmp, "diar-live.json")
        ring = mod.RingBuffer(rate=1000, window_s=2.0)
        # Audio COM FALA, nao silencio. A porta de densidade
        # (`MIN_SPEECH_FRACTION`) recusa uma janela sem fala -- correctamente, e
        # e' o que impede o painel de inventar pessoas. Um fixture de silencio
        # num bloco que mede `tick` a publicar segmentos deixava de medir isso.
        # O silencio tem os seus proprios arms noutro sitio.
        import math as _math
        def _speechy(n, seed):
            return [0.2 * _math.sin(2 * _math.pi * (140.0 + seed) * (i / 1000.0))
                    * (0.6 + 0.4 * _math.sin(2 * _math.pi * 2.5 * (i / 1000.0)))
                    for i in range(n)]
        ring.push(_speechy(1000, 1), 300.0)
        ring.push(_speechy(1000, 2), 301.0)
        dial = mod.FakeDiarizer()
        state = mod.tick(ring, dial, out_file, threshold=0.9, num_speakers=-1)
        chk(state.get("state") == "written", "a tick writes a payload",
            repr(state.get("state")))
        chk(dial.calls == 1, "the diarizer was asked once", repr(dial.calls))
        with open(out_file, "r", encoding="utf-8") as fh:
            got = json.load(fh)
        chk(abs(got["segments"][0]["start"] - 301.0) < 1e-9,
            "the published segment carries the offset",
            "%.3f" % got["segments"][0]["start"])
        chk(abs(got["window_start_abs"] - 300.0) < 1e-9,
            "the published payload names its window",
            repr(got.get("window_start_abs")))
        chk(abs(got["window_s"] - 2.0) < 1e-9, "and how long the window was",
            repr(got.get("window_s")))

        # The reader half must accept what the writer half just wrote. This is
        # the only place the two processes are in the same room.
        sys.path.insert(0, os.path.join(REPO, "worker"))
        bridge = load_module(BRIDGE_PATH, "speaker_bridge_oracle")
        payload = bridge.payload_if_fresh(out_file, max_age_s=30.0)
        chk(isinstance(payload, dict), "the bridge accepts the sidecar's payload")
        lines = bridge.apply_to_lines(
            [{"start": 301.2, "end": 302.8, "text": "e ai gente"}],
            base_source="device:CABLE Output (VB-Audio Virtual Cable)",
            payload=payload)
        chk(lines[0].get("speaker") == "speaker-1",
            "a real line through the real writer gets a real voice",
            repr(lines[0].get("speaker")))
        chk("voice:speaker-1" in str(lines[0].get("source")),
            "and its own source key", repr(lines[0].get("source")))

        # --- honesty about failure ----------------------------------------
        def boom(samples, threshold=0.9, num_speakers=-1):
            raise RuntimeError("the model fell over")
        failed = mod.tick(ring, boom, out_file)
        chk(failed.get("state") == "error", "a diarizer that raises is reported",
            repr(failed.get("state")))
        chk(failed.get("n_segments") == 0, "and publishes nothing")
        with open(out_file, "r", encoding="utf-8") as fh:
            after = json.load(fh)
        chk(after.get("segments") == got.get("segments"),
            "the previous payload is still intact -- a crash is not a deletion")

        drained = mod.RingBuffer(rate=1000, window_s=2.0)
        chk(mod.tick(drained, dial, out_file).get("state") == "empty",
            "an empty buffer publishes nothing")
        chk(dial.calls == 1, "and does not wake the model for silence")

        # The minimum-audio floor. MEASURED, not designed: the first version of
        # this oracle ticked at t=0 on an empty buffer and, in a short run,
        # that wasted tick was the only one -- so nothing was ever published.
        # A diarizer handed a tenth of a second is also being asked a question
        # nobody asked it; publishing the answer is worse than publishing none.
        thin = mod.RingBuffer(rate=1000, window_s=2.0)
        thin.push([0.0] * 400, 100.0)
        before_calls = dial.calls
        thin_state = mod.tick(thin, dial, out_file, min_audio_s=1.0)
        chk(thin_state.get("state") == "too-short",
            "a 0,4 s window is refused, not diarized", repr(thin_state.get("state")))
        chk(dial.calls == before_calls,
            "and the model is never woken for it")
        fat = mod.RingBuffer(rate=1000, window_s=2.0)
        fat.push([0.0] * 1600, 100.0)
        chk(mod.tick(fat, dial, out_file, min_audio_s=1.0).get("state") == "written",
            "1,6 s is enough")
        chk(mod.tick(thin, dial, out_file, min_audio_s=0.0).get("state")
            == "written", "the floor is a parameter, not a law of nature")

        unwritable = os.path.join(tmp, "no-such-dir", "\0bad", "x.json")
        chk(mod.write_payload_atomic(unwritable, {"a": 1}) is False,
            "an impossible path returns False, it does not raise")

        # --- atomicity, observed rather than assumed ----------------------
        # A reader is a different process in production. Here a thread stands
        # in for it while the writer replaces the file under it, which is the
        # only way to know that `os.replace` is doing the work.
        #
        # AND THE WINDOWS FACT. The first run of this arm failed on this box:
        # the writer got `PermissionError: [Errno 13]` on every single replace,
        # because Python's `_wopen` does not grant `FILE_SHARE_DELETE` and
        # `os.replace` needs DELETE access to the target. The sidecar now
        # retries, and both halves of that are pinned here:
        #   * the WRITER must lose zero publishes -- a silent give-up would
        #     leave the owner with names that quietly stopped updating
        #   * the READER may meet PermissionError (the writer retrying) but must
        #     NEVER meet a partial or an absent file, which is the whole point
        race_out = os.path.join(tmp, "race.json")
        mod.write_payload_atomic(race_out, {"segments": [], "pad": "0"})
        seen_bad = []
        transient = []
        writes = 0
        stop = threading.Event()

        def reader():
            while not stop.is_set():
                try:
                    with open(race_out, "r", encoding="utf-8") as fh:
                        body = fh.read()
                    json.loads(body)
                except FileNotFoundError:
                    seen_bad.append("absent")
                except PermissionError as exc:
                    transient.append(str(exc))
                except ValueError as exc:
                    seen_bad.append("partial: %s" % exc)

        th = threading.Thread(target=reader)
        th.daemon = True
        th.start()
        lost = 0
        try:
            for i in range(150):
                writes += 1
                if not mod.write_payload_atomic(
                        race_out,
                        {"segments": [{"start": float(i), "end": float(i) + 1,
                                       "speaker": i % 3}],
                         "pad": "x" * 1200}):
                    lost += 1
        finally:
            stop.set()
            th.join(timeout=5.0)
        chk(not seen_bad,
            "%d replacements, no reader ever saw a partial or absent file"
            % writes, repr(seen_bad[:2]))
        chk(lost == 0, "the writer lost zero publishes on Windows",
            "lost=%d of %d" % (lost, writes))
        print("       (reader met %d PermissionError(s) -- the Windows sharing"
              " race, tolerated by design)" % len(transient))
        leftovers = [n for n in os.listdir(tmp) if n.startswith(".diar-")]
        chk(not leftovers, "no temporary file is left behind", repr(leftovers))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


MUTANTS = [
    # The plausible lie: a correct-looking payload, attributed to the wrong
    # minute of the call.
    ("offset-ignored",
     '            start = float(row["start"]) + window_start_abs',
     '            start = float(row["start"])'),
    ("offset-applied-to-the-window-not-the-row",
     '            end = float(row["end"]) + window_start_abs',
     '            end = float(row["end"]) + window_start_abs * 2'),
    ("buffer-never-trimmed",
     "        while self._n > self.capacity:",
     "        while False:"),
    ("publish-is-not-atomic",
     "            _replace_with_retry(tmp, path)",
     "            open(path, 'w', encoding='utf-8').write("
     "open(tmp, encoding='utf-8').read())"),
    ("no-retry-on-the-windows-sharing-race",
     "            _replace_with_retry(tmp, path)",
     "            os.replace(tmp, path)"),
    ("a-raised-model-kills-the-sidecar",
     "    except Exception as exc:                                    # noqa: BLE001",
     "    except _NeverMatchesThis:                                  # noqa: BLE001"),
]


def main() -> int:
    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()

    print("PURITY (numpy / sherpa / Win32 must be lazy, not imported)")
    # Only the MODULE BODY counts. `ast.walk` descends into functions, and the
    # whole point of the lazy import is that it lives in the one function that
    # needs it -- so counting it would report the design working as a defect.
    imported = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    heavy = sorted(imported & set(FORBIDDEN_AT_IMPORT))
    print("  %s the model is imported inside the function that needs it%s"
          % ("GREEN" if not heavy else "RED  ",
             "" if not heavy else "  found=%r" % (heavy,)))
    lazy_ok = "import numpy" in source and "import sherpa_onnx" in source
    print("  %s ...and both really are imported lazily, inside their functions%s"
          % ("GREEN" if lazy_ok else "RED  ", "" if lazy_ok else ""))

    print("\nARMS (the real sidecar)")
    mod = load_module(MODULE_PATH, "speaker_sidecar_live")
    rows = battery(mod)
    for ok, name, detail in rows:
        print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                             ("  " + detail) if detail else ""))
    green = sum(1 for ok, _, _ in rows if ok)
    print("\n  %d/%d" % (green, len(rows)))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    caught = 0
    tmp = tempfile.mkdtemp(prefix="sidecar-oracle-mut-")
    try:
        for idx, (label, old, new) in enumerate(MUTANTS):
            if old not in source:
                print("  RED   mutant %-42s ANCHOR MISSING -- oracle is stale"
                      % label)
                continue
            path = os.path.join(tmp, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, "speaker_sidecar_mut_%d" % idx)
                res = battery(bad)
            except Exception as exc:                                # noqa: BLE001
                print("  GREEN mutant %-42s refused to run (%s)"
                      % (label, type(exc).__name__))
                caught += 1
                continue
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-42s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-42s SURVIVED -- the gate is blind here"
                      % label)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = (not heavy) and green == len(rows) and caught == len(MUTANTS)
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", green, len(rows), caught, len(MUTANTS)))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())