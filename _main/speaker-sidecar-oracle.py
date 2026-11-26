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
import builtins
import contextlib
import gc
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import types

REPO = r"H:\sotto"
WORKER_DIR = os.path.join(REPO, "worker")
if WORKER_DIR not in sys.path:
    sys.path.insert(0, WORKER_DIR)
MODULE_PATH = os.path.join(REPO, "worker", "speaker_sidecar.py")
MIC_MODULE_PATH = os.path.join(REPO, "worker", "mic_tap.py")
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

        # --- A JANELA ESPARSA E' RECORTADA, NAO JOGADA FORA (2026-11-24) ------
        # MEDIDO no JOIN ao vivo: a fala do dono ocupa 2-8 % de uma janela de
        # 20 s, e a porta de 30 % recusava quase todos os tiques -- 7 legendas
        # reais saiam sem voz. A cura NAO e' baixar a barra (foi a esparsa que
        # criou 12 slots para 2 pessoas): e' dar ao modelo o trecho com fala.
        # Estas duas arms medem o recorte e o deslocamento que ele devolve.
        def _silence(n):
            return [0.0] * n
        sparse_file = os.path.join(tmp, "diar-sparse.json")
        ring2 = mod.RingBuffer(rate=16000, window_s=8.0)
        for sec in range(8):
            ring2.push(_speechy(16000, 3) if sec == 2 else _silence(16000),
                       400.0 + sec)
        dial2 = mod.FakeDiarizer()
        state2 = mod.tick(ring2, dial2, sparse_file, threshold=0.9,
                          num_speakers=-1)
        with open(sparse_file, "r", encoding="utf-8") as fh:
            got2 = json.load(fh)
        chk(dial2.calls == 1,
            "a sparse window with speech still reaches the diarizer",
            "calls=%r" % (dial2.calls,))
        trim = got2.get("window_trim") or {}
        chk(abs(trim.get("from_s", -1) - 1.5) < 0.11,
            "and it is cropped to the speech it holds (0,5 s of context)",
            repr(trim))
        chk(1.9 <= (got2.get("diarized_s") or 0) <= 2.2,
            "the model saw ~2 s of speech, not 8 s of mostly silence",
            repr(got2.get("diarized_s")))
        chk(abs(got2["window_start_abs"] - 401.5) < 0.11,
            "the published window names the CROPPED start",
            repr(got2.get("window_start_abs")))
        chk(abs(got2["segments"][0]["start"] - 402.5) < 0.11,
            "and the segment keeps the ABSOLUTE time (offset added back)",
            "%.3f" % got2["segments"][0]["start"])

        # Below the evidence floor the model is NOT asked: a click is not a
        # person, and refusing without spending 277 MB of inference is the
        # cheap half of the same rule.
        click_file = os.path.join(tmp, "diar-click.json")
        ring3 = mod.RingBuffer(rate=16000, window_s=8.0)
        for sec in range(8):
            block = _silence(16000)
            if sec == 3:
                block[8000:8040] = _speechy(40, 5)
            ring3.push(block, 500.0 + sec)
        dial3 = mod.FakeDiarizer()
        state3 = mod.tick(ring3, dial3, click_file, threshold=0.9,
                          num_speakers=-1)
        with open(click_file, "r", encoding="utf-8") as fh:
            got3 = json.load(fh)
        chk(state3.get("declined") is True and dial3.calls == 0,
            "40 ms of speech declines WITHOUT running the model",
            "declined=%r calls=%r" % (state3.get("declined"), dial3.calls))
        chk(got3.get("decline_reason") == "speech-too-short",
            "and the refusal names why", repr(got3.get("decline_reason")))

        silent_file = os.path.join(tmp, "diar-silent.json")
        ring4 = mod.RingBuffer(rate=16000, window_s=4.0)
        for sec in range(4):
            ring4.push(_silence(16000), 600.0 + sec)
        dial4 = mod.FakeDiarizer()
        mod.tick(ring4, dial4, silent_file, threshold=0.9, num_speakers=-1)
        with open(silent_file, "r", encoding="utf-8") as fh:
            got4 = json.load(fh)
        chk(got4.get("decline_reason") == "no-speech" and dial4.calls == 0,
            "digital silence declines by name, costs no inference",
            "%r calls=%r" % (got4.get("decline_reason"), dial4.calls))
        chk(got.get("fake") is True,
            "a fake diarizer marks its payload as fake",
            "the marker is what keeps a fixture from naming a real voice")

        # The reader half must accept what a REAL writer writes. This is the
        # only place the two processes are in the same room, and the fixture
        # above is deliberately stamped `fake` -- so the accept-path payload is
        # the same one with that marker flipped, which is exactly the difference
        # between "an oracle wrote this" and "the model wrote this".
        real_file = out_file + ".real.json"
        with open(real_file, "w", encoding="utf-8") as fh:
            json.dump({k: v for k, v in got.items() if k != "fake"}, fh)
        sys.path.insert(0, os.path.join(REPO, "worker"))
        bridge = load_module(BRIDGE_PATH, "speaker_bridge_oracle")
        chk(bridge.payload_if_fresh(out_file, max_age_s=30.0) is None,
            "a FRESH payload stamped fake is refused by name, not by age")
        payload = bridge.payload_if_fresh(real_file, max_age_s=30.0)
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

        # --- A COUPLING THAT WAS ONLY PROMISED IN A COMMENT -------------------
        # `speaker_sidecar.py` keeps a COPY of the bridge's freshness window so
        # that "the writer's own output must not be refused as stale" is
        # visible. The copy was NEVER READ: the relationship was asserted in
        # prose and enforced by nothing -- change the bridge's window and the
        # sidecar would still claim the coupling held. The audit was right to
        # call that a comment that lies. It is a CHECK now, and this is the
        # gate that keeps it.
        chk(mod.DEFAULT_MAX_AGE_S == bridge.DEFAULT_MAX_AGE_S,
            "the sidecar's freshness window is the bridge's (the copy is not stale)",
            "sidecar=%.1fs bridge=%.1fs" % (mod.DEFAULT_MAX_AGE_S,
                                             bridge.DEFAULT_MAX_AGE_S))
        # TWO cadences, not one: a payload that arrives a tick late is still
        # fresh. One cadence would make the coupling true only in the perfect
        # case, and the perfect case is the one that does not happen.
        chk(bridge.DEFAULT_MAX_AGE_S >= 2 * mod.DEFAULT_EVERY_S,
            "the bridge's window outlives two publish cadences "
            "(a payload is fresh when it is read)",
            "window=%.1fs cadence=%.1fs margin=%.1fs"
            % (bridge.DEFAULT_MAX_AGE_S, mod.DEFAULT_EVERY_S,
               bridge.DEFAULT_MAX_AGE_S - 2 * mod.DEFAULT_EVERY_S))

        # --- honesty about failure ----------------------------------------
        def boom(samples, threshold=0.9, num_speakers=-1):
            raise RuntimeError("the model fell over")

        # O mutante "a-raised-model-kills-the-sidecar" re-lanca a excepcao, e
        # portanto `tick()` REBENTA aqui em vez de devolver um estado. Se a
        # bateria deixasse a excepcao escapar, o mutante contava como
        # "decorativo / nao testado" -- e isso era mentira a favor do gate: o
        # mutante fez exactamente o que promete e a bateria e' que nao soube
        # olhar. Rebentar aqui e' um RED, que e' o que o arm quer dizer.
        try:
            failed = mod.tick(ring, boom, out_file)
            raised = None
        except Exception as exc:                                    # noqa: BLE001
            failed = {}
            raised = type(exc).__name__
        chk(raised is None and failed.get("state") == "error",
            "a diarizer that raises is reported",
            "REBENTOU com %s -- o sidecar morreu em vez de o dizer"
            % raised if raised else repr(failed.get("state")))
        chk(failed.get("n_segments") == 0, "and publishes nothing",
            repr(failed.get("n_segments")))
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
    out.extend(gpu_policy_battery(mod))
    return out


def gpu_policy_battery(mod) -> list:
    """Model-free controls for the full diarizer's GPU-only admission gate."""
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    validator = getattr(mod, "_validate_gpu_speaker_attestation", None)
    if not callable(validator):
        chk(False, "full diarizer requires runtime provider attestation",
            "validator is absent")
        chk(False, "attestation tests are wired", "validator is absent")
        return out

    expected = {"segmentation": "a" * 64, "embedding": "b" * 64}

    def component(digest, nodes=7, fallback_disabled=True, provider="CUDAExecutionProvider"):
        assignments = {provider: nodes}
        return {
            "model_sha256": digest,
            "cpu_ep_fallback_disabled": fallback_disabled,
            "node_assignment_counts": assignments,
        }

    valid = {
        "schema": "sotto-speaker-gpu-attestation-v1",
        "evidence": "onnxruntime-node-assignment",
        "components": {
            "segmentation": component(expected["segmentation"], nodes=18),
            "embedding": component(expected["embedding"], nodes=42),
        },
    }

    def accepts(candidate):
        try:
            validator(candidate, expected)
            return True
        except (RuntimeError, ValueError, TypeError):
            return False

    chk(accepts(valid), "exact CUDA node attestation for both speaker models passes")
    chk(not accepts(None), "missing runtime attestation fails closed")

    bad_hash = json.loads(json.dumps(valid))
    bad_hash["components"]["segmentation"]["model_sha256"] = "c" * 64
    chk(not accepts(bad_hash), "source hash mismatch fails closed")

    bad_cpu = json.loads(json.dumps(valid))
    bad_cpu["components"]["embedding"]["node_assignment_counts"] = {
        "CUDAExecutionProvider": 41, "CPUExecutionProvider": 1,
    }
    chk(not accepts(bad_cpu), "any CPU-assigned neural node fails closed")

    bad_fallback = json.loads(json.dumps(valid))
    bad_fallback["components"]["segmentation"]["cpu_ep_fallback_disabled"] = False
    chk(not accepts(bad_fallback), "CPU EP fallback must be disabled")

    bad_provider = json.loads(json.dumps(valid))
    bad_provider["components"]["embedding"]["node_assignment_counts"] = {
        "UnknownExecutionProvider": 42,
    }
    chk(not accepts(bad_provider), "unknown provider fails closed")

    # Exercise the strict adapter path without loading an ONNX graph. The fake
    # adapter records the exact contract and returns only synthetic readback;
    # this proves the consumer rejects a weaker adapter before audio starts.
    missing = object()
    with tempfile.TemporaryDirectory(prefix="sidecar-gpu-policy-") as tmp:
        seg_path = os.path.join(tmp, "seg.onnx")
        emb_path = os.path.join(tmp, "emb.onnx")
        with open(seg_path, "wb") as fh:
            fh.write(b"seg-fixture")
        with open(emb_path, "wb") as fh:
            fh.write(b"emb-fixture")
        expected_files = {
            "segmentation": mod._sha256_file(seg_path),
            "embedding": mod._sha256_file(emb_path),
        }
        actual_attestation = json.loads(json.dumps(valid))
        actual_attestation["components"]["segmentation"]["model_sha256"] = \
            expected_files["segmentation"]
        actual_attestation["components"]["embedding"]["model_sha256"] = \
            expected_files["embedding"]

        class Config:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def validate(self):
                return True

        class FakeDiarizer:
            def __init__(self, readback_value):
                self.readback_value = readback_value
                self.closed = False

            def get_runtime_node_assignment_readback(self):
                return self.readback_value

            def close(self):
                self.closed = True

        adapter_calls = []
        made = []

        def factory(config, *, disable_cpu_ep_fallback, expected_model_sha256):
            adapter_calls.append((disable_cpu_ep_fallback, expected_model_sha256))
            item = FakeDiarizer(actual_attestation)
            made.append(item)
            return item

        adapter = types.SimpleNamespace(
            OfflineSpeakerSegmentationPyannoteModelConfig=Config,
            OfflineSpeakerSegmentationModelConfig=Config,
            SpeakerEmbeddingExtractorConfig=Config,
            FastClusteringConfig=Config,
            OfflineSpeakerDiarizationConfig=Config,
            create_gpu_only_offline_speaker_diarizer=factory,
        )
        fake_ort = types.SimpleNamespace(
            get_available_providers=lambda: ["CUDAExecutionProvider", "CPUExecutionProvider"])
        cpu_only_ort = types.SimpleNamespace(
            get_available_providers=lambda: ["CPUExecutionProvider"])
        prior = sys.modules.get("sherpa_onnx", missing)
        prior_ort = sys.modules.get("onnxruntime", missing)
        sys.modules["sherpa_onnx"] = adapter
        sys.modules["onnxruntime"] = fake_ort
        try:
            diarizer = mod._load_sherpa_diarizer(seg_path, emb_path)
            chk(diarizer is made[0]
                and adapter_calls == [(True, expected_files)],
                "real loader passes exact model hashes and disables CPU fallback")

            called_before = len(adapter_calls)
            sys.modules["onnxruntime"] = cpu_only_ort
            try:
                mod._load_sherpa_diarizer(seg_path, emb_path)
                rejected = False
            except RuntimeError as exc:
                rejected = "CUDAExecutionProvider" in str(exc)
            chk(rejected and len(adapter_calls) == called_before,
                "missing CUDA provider refuses before adapter/model construction")
            sys.modules["onnxruntime"] = fake_ort

            weak = FakeDiarizer(None)
            adapter.create_gpu_only_offline_speaker_diarizer = (
                lambda *args, **kwargs: weak)
            try:
                mod._load_sherpa_diarizer(seg_path, emb_path)
                rejected = False
            except RuntimeError:
                rejected = True
            chk(rejected and weak.closed,
                "malformed runtime readback closes adapter and fails closed")

            bad = json.loads(json.dumps(valid))
            bad["components"]["segmentation"]["node_assignment_counts"] = {
                "CUDAExecutionProvider": 17, "CPUExecutionProvider": 1,
            }
            cpu = FakeDiarizer(bad)
            adapter.create_gpu_only_offline_speaker_diarizer = (
                lambda *args, **kwargs: cpu)
            try:
                mod._load_sherpa_diarizer(seg_path, emb_path)
                rejected = False
            except RuntimeError:
                rejected = True
            chk(rejected and cpu.closed,
                "runtime CPU node readback closes adapter and fails closed")
        finally:
            if prior is missing:
                sys.modules.pop("sherpa_onnx", None)
            else:
                sys.modules["sherpa_onnx"] = prior
            if prior_ort is missing:
                sys.modules.pop("onnxruntime", None)
            else:
                sys.modules["onnxruntime"] = prior_ort

    # Exercise the loader with the API shape actually present in sherpa-onnx
    # 1.13.4: a provider config, but no strict factory/readback surface. Its
    # constructor must not run before the capability refusal.
    calls = {"constructor": 0}

    class LegacyDiarizer:
        def __init__(self, config):
            calls["constructor"] += 1

    legacy = types.SimpleNamespace(OfflineSpeakerDiarization=LegacyDiarizer)
    prior = sys.modules.get("sherpa_onnx", missing)
    prior_ort = sys.modules.get("onnxruntime", missing)
    sys.modules["sherpa_onnx"] = legacy
    sys.modules["onnxruntime"] = types.SimpleNamespace(
        get_available_providers=lambda: ["CUDAExecutionProvider"])
    try:
        try:
            mod._load_sherpa_diarizer("seg.onnx", "emb.onnx")
            refused = False
        except RuntimeError as exc:
            refused = "GPU-only" in str(exc) or "attestation" in str(exc)
    except Exception as exc:  # the missing-adapter path must be intentional
        refused = False
        detail = "%s: %s" % (type(exc).__name__, exc)
    else:
        detail = ""
    finally:
        if prior is missing:
            sys.modules.pop("sherpa_onnx", None)
        else:
            sys.modules["sherpa_onnx"] = prior
        if prior_ort is missing:
            sys.modules.pop("onnxruntime", None)
        else:
            sys.modules["onnxruntime"] = prior_ort
    chk(refused and calls["constructor"] == 0,
        "legacy sherpa API is refused before model construction",
        detail or "constructor_calls=%d" % calls["constructor"])

    # MEASURED 2026-11-24: 'cpu' is the SHIPPED provider (`DIARIZER_PROVIDER`,
    # DER 0,03 % / RTF 0,416 measured with it) and is no longer a refusal.
    # What must still be refused, before sherpa is imported, is a provider
    # nobody measured -- otherwise a typo becomes a silent CPU run.
    chk(mod.DIARIZER_PROVIDER == "cpu",
        "the sidecar asks for the MEASURED cpu provider",
        repr(mod.DIARIZER_PROVIDER))
    calls["constructor"] = 0

    class CpuConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def validate(self):
            return True

    cpu_adapter = types.SimpleNamespace(
        OfflineSpeakerSegmentationPyannoteModelConfig=CpuConfig,
        OfflineSpeakerSegmentationModelConfig=CpuConfig,
        SpeakerEmbeddingExtractorConfig=CpuConfig,
        FastClusteringConfig=CpuConfig,
        OfflineSpeakerDiarizationConfig=CpuConfig,
        OfflineSpeakerDiarization=lambda config: object(),
    )
    sy = sys.modules.get("sherpa_onnx", missing)
    sys.modules["sherpa_onnx"] = cpu_adapter
    try:
        built_flag = {"n": 0}
        cpu_adapter.OfflineSpeakerDiarization = (
            lambda config: built_flag.__setitem__("n", built_flag["n"] + 1) or object())
        mod._load_sherpa_diarizer("seg.onnx", "emb.onnx", provider="cpu")
        built = built_flag["n"] == 1
        why = "constructor_calls=%d" % built_flag["n"]
    except Exception as exc:  # noqa: BLE001 -- an exception here is the failure
        built = False
        why = "%s: %s" % (type(exc).__name__, exc)
    finally:
        if sy is missing:
            sys.modules.pop("sherpa_onnx", None)
        else:
            sys.modules["sherpa_onnx"] = sy
    chk(built, "provider='cpu' builds the diarizer with no accelerator to attest", why)

    for requested in ("unknown", "rocm"):
        try:
            mod._load_sherpa_diarizer("seg.onnx", "emb.onnx", provider=requested)
            rejected = False
        except RuntimeError as exc:
            rejected = "'cpu' or 'cuda'" in str(exc)
        chk(rejected, "requested provider %r is refused by name" % requested)

    # THE ENDPOINT PICKER, WHICH HAD NO GATE (2026-11-24), AND THE SECOND
    # DEFECT THE JOIN FOUND (2026-11-25). Two measured failures set the order:
    # `spec["default"]` was never written (the writer writes `is_default`), and
    # the static default is NOT what the worker opens -- Windows keeps one
    # default per role (E_CONSOLE vs E_MULTIMEDIA), so the sidecar captured
    # `VoiceMeeter Input` while the worker transcribed `Fones de ouvido
    # (soundcore Space Q45)`: 91 captions, ZERO attributed. The worker's rung A
    # follows the LIVE meter (`live_endpoint_order`); the picker now asks that
    # same question first, so both halves open one endpoint by construction.
    #
    # Every arm STUBS `wasapi_loopback`, because an arm that reads the real
    # device on this box cannot fail: the machine is always rendering
    # something, so the fixture would be ignored and the arm would "pass" by
    # accident (measured: the first draft of these arms did exactly that).
    prior_wasapi = sys.modules.get("wasapi_loopback", missing)

    def _stub(live_entries, default_id):
        class _Probe:
            endpoint_id = default_id
        return types.SimpleNamespace(
            live_endpoint_order=lambda: list(live_entries),
            default_render_endpoint=lambda: _Probe())

    def _pick(specs, live_entries=(), wanted=None, default_id="hp2"):
        sys.modules["wasapi_loopback"] = _stub(live_entries, default_id)
        try:
            return mod._open_endpoint(specs, wanted)
        finally:
            if prior_wasapi is missing:
                sys.modules.pop("wasapi_loopback", None)
            else:
                sys.modules["wasapi_loopback"] = prior_wasapi

    two = [
        {"name": "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)", "endpoint_id": "vm"},
        {"name": "Fones de ouvido (soundcore Space Q45)", "endpoint_id": "hp",
         "is_default": True},
    ]
    chk((_pick(two) or {}).get("endpoint_id") == "hp",
        "with nothing rendering, the DEFAULT wins even when it is not first",
        repr(_pick(two)))
    chk((_pick(two, wanted="voicemeeter") or {}).get("endpoint_id") == "vm",
        "an explicit device name still wins over everything")
    chk((_pick(two, [{"endpoint_id": "vm", "name": "VoiceMeeter Input",
                      "meter_peak": 0.0},
                     {"endpoint_id": "hp", "name": "Fones de ouvido",
                      "meter_peak": 0.31}]) or {}).get("endpoint_id") == "hp",
        "the endpoint RENDERING NOW wins over the static default (the worker's rule)")
    silent = [{"name": "A", "endpoint_id": "a"},
              {"name": "B", "endpoint_id": "b2"}]
    chk((_pick(silent, [], default_id="b2") or {}).get("endpoint_id") == "b2",
        "no live meter and no flagged default: GetDefaultAudioEndpoint decides",
        repr(_pick(silent, [], default_id="b2")))
    chk((_pick(silent, [{"endpoint_id": "zzz", "name": "not in the specs",
                         "meter_peak": 0.22}]) or {}).get("endpoint_id") == "zzz",
        "a live endpoint missing from the spec list is still opened by id")
    chk(_pick([], []) is None, "no endpoints and nothing rendering means None")
    chk((_pick([], [{"endpoint_id": "live", "name": "live",
                     "meter_peak": 0.2}]) or {}).get("endpoint_id") == "live",
        "an empty spec list is not a refusal: the live endpoint is still opened")

    out.extend(watch_policy_battery(mod))
    return out


def watch_policy_battery(mod) -> list:
    """Fake-ORT controls for the actual --watch-only powerset loader."""
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    #: O QUE A ATRIBUICAO DO PROPRIO ORT DEVOLVE NESTE GRAFO, medido 2026-11-23.
    measured_cpu = [("/lstm/Concat", "Concat"), ("/lstm/Gather", "Gather"),
                    ("/lstm/Unsqueeze", "Unsqueeze"), ("Equal_115", "Equal"),
                    ("Gather", "Gather"), ("Gather_113", "Gather")]
    measured_cuda = 46
    entry_key = "session.record_ep_graph_assignment_info"

    def assignment_rows(cuda=measured_cuda, cpu=None, extra_ep=None):
        cpu_nodes = measured_cpu if cpu is None else list(cpu)
        rows = []
        if cuda:
            rows.append(types.SimpleNamespace(
                ep_name="CUDAExecutionProvider",
                get_nodes=lambda n=int(cuda): [
                    types.SimpleNamespace(name="cuda_node_%d" % i,
                                          op_type="Conv", domain="")
                    for i in range(n)]))
        if cpu_nodes:
            rows.append(types.SimpleNamespace(
                ep_name="CPUExecutionProvider",
                get_nodes=lambda rows_cpu=tuple(cpu_nodes): [
                    types.SimpleNamespace(name=name, op_type=op, domain="")
                    for name, op in rows_cpu]))
        for provider, count in (extra_ep or {}).items():
            rows.append(types.SimpleNamespace(
                ep_name=provider,
                get_nodes=lambda n=int(count): [
                    types.SimpleNamespace(name="%s_node_%d" % (provider, i),
                                          op_type="Conv", domain="")
                    for i in range(n)]))
        return rows

    def run_case(*, census="cuda", available=None, entry_readback="1",
                 option_reader=True, providers=None, runtime_fallback=False,
                 disable_api=True, assignment_api=True, assignment=None,
                 assignment_raises=False):
        trace = []
        calls = {"session": 0, "requested": None, "options": None,
                 "enable_fallback": None, "runtime_disable": 0,
                 "assignment_reads": 0}
        options = types.SimpleNamespace(entries={})

        def add_entry(key, value):
            trace.append(("option-write", key, str(value)))
            options.entries[key] = str(value)

        options.add_session_config_entry = add_entry
        if option_reader:
            def get_entry(key):
                trace.append(("option-read", key))
                return entry_readback
            options.get_session_config_entry = get_entry

        payload = assignment_rows() if assignment is None else assignment

        class FakeSession:
            def __init__(self, path, opts, providers=None, enable_fallback=1):
                trace.append(("session",))
                calls["session"] += 1
                calls["requested"] = list(providers or ())
                calls["option_value_at_construction"] = opts.entries.get(entry_key)
                calls["readback_before_construction"] = (
                    ("option-read", entry_key) in trace)
                calls["enable_fallback"] = enable_fallback
                self._enable_fallback = bool(enable_fallback)

            def disable_fallback(self):
                trace.append(("runtime-fallback-disable",))
                calls["runtime_disable"] += 1
                self._enable_fallback = bool(runtime_fallback)

            def get_providers(self):
                return list(providers or ["CUDAExecutionProvider", "CPUExecutionProvider"])

            def get_provider_graph_assignment_info(self):
                trace.append(("assignment-read",))
                calls["assignment_reads"] += 1
                if assignment_raises:
                    raise RuntimeError("injected assignment readback failure")
                return list(payload)

        if not disable_api:
            delattr(FakeSession, "disable_fallback")
        if not assignment_api:
            delattr(FakeSession, "get_provider_graph_assignment_info")

        def get_devices():
            trace.append(("census",))
            if census == "unknown":
                raise RuntimeError("injected census unavailable")
            if census == "cpu":
                return [types.SimpleNamespace(ep_name="CPUExecutionProvider")]
            return [types.SimpleNamespace(ep_name="CUDAExecutionProvider")]

        fake = types.SimpleNamespace()
        if census != "missing":
            fake.get_ep_devices = get_devices
        fake.get_available_providers = lambda: list(
            available or ["CUDAExecutionProvider", "CPUExecutionProvider"])

        def make_options():
            trace.append(("options",))
            calls["options"] = options
            return options

        fake.SessionOptions = make_options
        fake.InferenceSession = FakeSession
        missing = object()
        prior = sys.modules.get("onnxruntime", missing)
        helper_name = "ort_cuda_runtime"
        prior_helper = sys.modules.get(helper_name, missing)
        fake_helper = types.ModuleType(helper_name)
        fake_helper.prepare_ort_runtime = lambda: fake
        sys.modules[helper_name] = fake_helper
        sys.modules["onnxruntime"] = fake
        try:
            try:
                result = mod._load_powerset("model-free-fake.onnx", threads=3)
                error = None
            except Exception as exc:  # model-free injected provider failures only
                result, error = None, exc
        finally:
            if prior is missing:
                sys.modules.pop("onnxruntime", None)
            else:
                sys.modules["onnxruntime"] = prior
            if prior_helper is missing:
                sys.modules.pop(helper_name, None)
            else:
                sys.modules[helper_name] = prior_helper
        return result, error, calls, trace

    result, error, calls, trace = run_case()
    chk(error is None and result is not None
        and calls["requested"] == ["CUDAExecutionProvider"]
        and calls["enable_fallback"] == 0
        and calls["runtime_disable"] == 1
        and calls.get("option_value_at_construction") == "1"
        and calls.get("readback_before_construction") is True
        and calls.get("assignment_reads") == 1
        and result.sotto_cuda_device_census is True
        and result.sotto_runtime_fallback_readback is False
        and result.sotto_graph_assignment_readback == "1"
        and result.sotto_node_assignment_counts == {
            "CUDAExecutionProvider": 46, "CPUExecutionProvider": 6}
        and result.sotto_node_assignment_cuda_share == 0.8846
        and result.sotto_node_assignment_cpu == sorted(name for name, _ in measured_cpu)
        and result.sotto_provider_readback == [
            "CUDAExecutionProvider", "CPUExecutionProvider"],
        "watch loader accepts the MEASURED node assignment and publishes it",
        "counts=46 cuda / 6 allowlisted cpu; share=0.8846")

    chk(mod.WATCH_GPU_CPU_ONLY_NODES == frozenset(name for name, _ in measured_cpu),
        "the CPU allowlist is exactly the six measured node names",
        "allowlist=%r" % sorted(mod.WATCH_GPU_CPU_ONLY_NODES))
    chk(0.0 < mod.WATCH_CUDA_NODE_SHARE_MIN <= 1.0,
        "the CUDA node-share floor is a fraction inside (0, 1]",
        "floor=%r" % (mod.WATCH_CUDA_NODE_SHARE_MIN,))

    for census, label in (("cpu", "CPU-only"), ("unknown", "unknown"),
                          ("missing", "missing")):
        result, error, calls, trace = run_case(census=census)
        chk(isinstance(error, RuntimeError) and calls["session"] == 0,
            "watch loader refuses %s CUDA census before session construction" % label,
            "sessions=%d" % calls["session"])

    result, error, calls, _ = run_case(
        available=["CPUExecutionProvider"])
    chk(isinstance(error, RuntimeError) and calls["session"] == 0,
        "watch loader refuses when CUDA provider is unavailable before construction")

    result, error, calls, _ = run_case(option_reader=False)
    chk(isinstance(error, RuntimeError) and calls["session"] == 0,
        "watch loader refuses missing SessionOptions assignment readback before construction")

    result, error, calls, _ = run_case(entry_readback="0")
    chk(isinstance(error, RuntimeError) and calls["session"] == 0,
        "watch loader refuses a non-1 assignment readback before construction")

    result, error, calls, _ = run_case(providers=["CPUExecutionProvider"])
    chk(isinstance(error, RuntimeError) and calls["session"] == 1,
        "watch loader refuses session without CUDA provider readback")

    result, error, calls, _ = run_case(runtime_fallback=True)
    chk(isinstance(error, RuntimeError) and calls["runtime_disable"] == 1,
        "watch loader refuses Python runtime fallback that remains enabled")

    result, error, calls, _ = run_case(disable_api=False)
    chk(isinstance(error, RuntimeError) and calls["session"] == 0,
        "watch loader refuses missing Python fallback-disable API before construction")

    result, error, calls, _ = run_case(assignment_api=False)
    chk(isinstance(error, RuntimeError) and calls["assignment_reads"] == 0,
        "watch loader refuses a session with no EP graph-assignment API")

    result, error, calls, _ = run_case(assignment=[])
    chk(isinstance(error, RuntimeError) and calls["assignment_reads"] == 1,
        "watch loader refuses an empty EP graph-assignment readback")

    result, error, calls, _ = run_case(assignment_raises=True)
    chk(isinstance(error, RuntimeError) and calls["assignment_reads"] == 1,
        "watch loader refuses an EP graph-assignment readback that raises")

    result, error, calls, _ = run_case(assignment=assignment_rows(cuda=0))
    chk(isinstance(error, RuntimeError) and "share" in str(error),
        "watch loader refuses when every node is the allowlisted CPU set (zero CUDA)",
        "an allowlist alone is not a green; str(err)=%s" % (error,))

    result, error, calls, _ = run_case(
        assignment=assignment_rows(cpu=measured_cpu + [("/lstm/MatMul", "MatMul")]))
    chk(isinstance(error, RuntimeError) and "/lstm/MatMul" in str(error),
        "watch loader refuses a CPU node that is not on the measured allowlist",
        "a shape-op allowlist is not a licence for any op")

    result, error, calls, _ = run_case(assignment=assignment_rows(cuda=2))
    chk(isinstance(error, RuntimeError) and "share" in str(error),
        "watch loader refuses a CUDA node share below the floor")

    result, error, calls, _ = run_case(
        assignment=assignment_rows(extra_ep={"TensorrtExecutionProvider": 4}))
    chk(isinstance(error, RuntimeError)
        and "refuses unknown execution providers" in str(error),
        "watch loader refuses an execution provider the policy did not request",
        "the refusal names the PROVIDER, not only its nodes; str(err)=%s" % (error,))
    out.extend(watch_cuda_bootstrap_battery(mod))
    out.extend(watch_main_capture_order_battery(mod))
    return out


def watch_cuda_bootstrap_battery(mod) -> list:
    """Prove standalone sidecar bootstraps ORT CUDA before its device census."""
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))

    helper_path = os.path.join(REPO, "worker", "ort_cuda_runtime.py")
    if not os.path.isfile(helper_path):
        return [(False, "watch sidecar uses shared CUDA bootstrap helper",
                 "missing %s" % helper_path)]

    worker_dir = os.path.join(REPO, "worker")
    added_path = worker_dir not in sys.path
    if added_path:
        sys.path.insert(0, worker_dir)
    helper_name = "ort_cuda_runtime"
    saved_helper = sys.modules.pop(helper_name, None)
    saved_ort = sys.modules.get("onnxruntime", None)
    missing = object()
    if saved_ort is None:
        saved_ort = missing

    helper_source = open(helper_path, "r", encoding="utf-8").read()

    def run_case(*, missing_preload=False, missing_register=False,
                 initial_cuda=False,
                 mutation=None):
        trace = []
        state = {"preloaded": False, "registered": False, "sessions": 0,
                 "initial_cuda": bool(initial_cuda)}
        options = types.SimpleNamespace(entries={})

        def add_entry(key, value):
            trace.append(("option-write", key, str(value)))
            options.entries[key] = str(value)

        def get_entry(key):
            trace.append(("option-read", key))
            return options.entries.get(key, "")

        options.add_session_config_entry = add_entry
        options.get_session_config_entry = get_entry

        class FakeSession:
            def __init__(self, path, opts, providers=None, enable_fallback=1):
                trace.append(("session", int(enable_fallback)))
                state["sessions"] += 1
                self._enable_fallback = bool(enable_fallback)

            def disable_fallback(self):
                trace.append(("runtime-fallback-disable",))
                self._enable_fallback = False

            def get_providers(self):
                trace.append(("provider-readback",))
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]

            def get_provider_graph_assignment_info(self):
                trace.append(("assignment-read",))
                return [types.SimpleNamespace(
                    ep_name="CUDAExecutionProvider",
                    get_nodes=lambda: [types.SimpleNamespace(
                        name="cuda_node_%d" % i, op_type="Conv", domain="")
                        for i in range(46)]),
                    types.SimpleNamespace(
                        ep_name="CPUExecutionProvider",
                        get_nodes=lambda: [types.SimpleNamespace(
                            name=name, op_type=op, domain="")
                            for name, op in (
                                ("/lstm/Concat", "Concat"),
                                ("/lstm/Gather", "Gather"),
                                ("/lstm/Unsqueeze", "Unsqueeze"),
                                ("Equal_115", "Equal"),
                                ("Gather", "Gather"),
                                ("Gather_113", "Gather"))])]

        class FakeOrt(types.ModuleType):
            pass

        fake = FakeOrt("onnxruntime")
        if not missing_preload:
            def preload_dlls():
                trace.append(("preload",))
                state["preloaded"] = True
            fake.preload_dlls = preload_dlls

        def get_devices():
            trace.append(("census",))
            if state["registered"] or state["initial_cuda"]:
                return [types.SimpleNamespace(ep_name="CUDAExecutionProvider"),
                        types.SimpleNamespace(ep_name="CPUExecutionProvider")]
            return [types.SimpleNamespace(ep_name="CPUExecutionProvider")]

        def get_available_providers():
            trace.append(("available",))
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]

        def register(provider, path):
            trace.append(("register", provider, os.path.basename(path)))
            if not state["preloaded"]:
                raise RuntimeError("fake CUDA plugin registration before preload")
            if provider != "CUDAExecutionProvider" or not os.path.isfile(path):
                raise RuntimeError("fake packaged CUDA plugin path invalid")
            state["registered"] = True

        fake.get_ep_devices = get_devices
        fake.get_available_providers = get_available_providers
        if not missing_register:
            fake.register_execution_provider_library = register
        fake.SessionOptions = lambda: options
        fake.InferenceSession = FakeSession

        with tempfile.TemporaryDirectory(prefix="speaker-ort-bootstrap-") as temp:
            capi = os.path.join(temp, "capi")
            os.makedirs(capi)
            plugin_name = ("onnxruntime_providers_cuda.dll" if os.name == "nt"
                           else "libonnxruntime_providers_cuda.dylib" if sys.platform == "darwin"
                           else "libonnxruntime_providers_cuda.so")
            plugin_path = os.path.join(capi, plugin_name)
            with open(plugin_path, "wb") as fh:
                fh.write(b"fake plugin path only")
            fake.__file__ = os.path.join(temp, "__init__.py")

            try:
                mutated_source = helper_source
                if mutation == "skip-preload":
                    anchor = ("    ort = preload_dlls(ort)\n"
                              "    register_cuda_plugin_if_needed(ort)\n")
                    replacement = ("    register_cuda_plugin_if_needed(ort)\n")
                elif mutation == "skip-registration":
                    anchor = ("    register_cuda_plugin_if_needed(ort)\n"
                              "    return True\n")
                    replacement = ("    return True\n")
                elif mutation == "register-before-preload":
                    anchor = ("    ort = preload_dlls(ort)\n"
                              "    register_cuda_plugin_if_needed(ort)\n")
                    replacement = ("    register_cuda_plugin_if_needed(ort)\n"
                                   "    ort = preload_dlls(ort)\n")
                else:
                    anchor, replacement = None, None
                if anchor:
                    if mutated_source.count(anchor) != 1:
                        raise AssertionError("CUDA ordering mutation anchor missing")
                    mutated_source = mutated_source.replace(anchor, replacement, 1)
                helper = types.ModuleType(helper_name)
                helper.__file__ = helper_path
                exec(compile(mutated_source, helper_path, "exec"), helper.__dict__)  # noqa: S102
                # Avoid real package discovery / DLL registration in this fake-only
                # control; the helper's ordering and registration policy stay real.
                helper.add_cuda_dll_dirs = lambda handles=None: trace.append(("dll-dirs",))
                sys.modules[helper_name] = helper
                sys.modules["onnxruntime"] = fake
                prior_import = builtins.__import__
                def trace_import(name, globals=None, locals=None, fromlist=(), level=0):
                    if name == "onnxruntime":
                        trace.append(("ort-import",))
                    return prior_import(name, globals, locals, fromlist, level)
                builtins.__import__ = trace_import
                try:
                    result = mod._load_powerset("model-free-fake.onnx", threads=1)
                    error = None
                except Exception as exc:  # only fake runtime policy paths
                    result, error = None, exc
            finally:
                if "prior_import" in locals():
                    builtins.__import__ = prior_import
                sys.modules.pop(helper_name, None)
                if saved_helper is not None:
                    sys.modules[helper_name] = saved_helper
                if saved_ort is missing:
                    sys.modules.pop("onnxruntime", None)
                else:
                    sys.modules["onnxruntime"] = saved_ort
        return result, error, trace, state

    try:
        result, error, trace, state = run_case()
        expected_prefix = [
            ("dll-dirs",), ("ort-import",), ("preload",),
            ("census",), ("available",),
            ("register", "CUDAExecutionProvider",
             "onnxruntime_providers_cuda.dll" if os.name == "nt" else
             "libonnxruntime_providers_cuda.dylib" if sys.platform == "darwin" else
             "libonnxruntime_providers_cuda.so"),
            ("census",), ("census",), ("census",), ("available",),
        ]
        chk(error is None and result is not None
            and trace[:len(expected_prefix)] == expected_prefix
            and state["sessions"] == 1
            and result.sotto_cuda_device_census is True,
            "watch CUDA startup orders DLL dirs, preload, registration and positive census",
            repr(trace))

        for kwargs, label in (
                ({"missing_preload": True}, "missing preload API"),
                ({"missing_register": True}, "missing plugin-registration API"),
                ({"mutation": "skip-preload"}, "skipped preload mutation"),
                ({"mutation": "skip-registration"}, "skipped registration mutation"),
                ({"mutation": "register-before-preload"},
                 "registration-before-preload ordering mutation")):
            result, error, trace, state = run_case(**kwargs)
            chk(isinstance(error, RuntimeError) and state["sessions"] == 0,
                "watch CUDA startup refuses %s before session" % label,
                "sessions=%d trace=%r" % (state["sessions"], trace))
        result, error, trace, state = run_case(
            missing_register=True, initial_cuda=True)
        chk(error is None and result is not None and state["sessions"] == 1
            and result.sotto_cuda_device_census is True,
            "watch CUDA startup tolerates absent registration API after positive CUDA census",
            "error=%r sessions=%d trace=%r" % (error, state["sessions"], trace))
    finally:
        if saved_helper is not None:
            sys.modules[helper_name] = saved_helper
        else:
            sys.modules.pop(helper_name, None)
        if saved_ort is missing:
            sys.modules.pop("onnxruntime", None)
        else:
            sys.modules["onnxruntime"] = saved_ort
        if added_path:
            try:
                sys.path.remove(worker_dir)
            except ValueError:
                pass
    out.extend(cuda_dll_enumeration_battery())
    return out


def cuda_dll_enumeration_battery() -> list:
    """Exercise the shared helper's total NVIDIA directory-entry budget."""
    helper_path = os.path.join(REPO, "worker", "ort_cuda_runtime.py")
    helper = types.ModuleType("ort_cuda_runtime_budget_fake")
    helper.__file__ = helper_path
    with open(helper_path, "r", encoding="utf-8") as fh:
        helper_source = fh.read()
    exec(compile(helper_source, helper_path, "exec"), helper.__dict__)  # noqa: S102
    scan = getattr(helper, "_nvidia_library_dirs", None)
    if not callable(scan):
        return [(False, "CUDA DLL directory census has a total bounded walk",
                 "_nvidia_library_dirs missing")]

    rows = []
    with tempfile.TemporaryDirectory(prefix="speaker-cuda-dll-budget-") as temp:
        root = os.path.join(temp, "nvidia")
        library_dir = os.path.join(root, "pkg", "lib")
        os.makedirs(library_dir)
        with open(os.path.join(library_dir, "cuda.dll"), "wb") as fh:
            fh.write(b"placeholder")
        try:
            found = scan([temp], max_entries=3)
            rows.append((found == [library_dir],
                         "CUDA DLL census accepts tree at exact entry budget",
                         "found=%r" % found))
        except Exception as exc:  # noqa: BLE001 -- fake filesystem only
            rows.append((False, "CUDA DLL census accepts tree at exact entry budget",
                         "%s: %s" % (type(exc).__name__, exc)))

    with tempfile.TemporaryDirectory(prefix="speaker-cuda-dll-overflow-") as temp:
        root = os.path.join(temp, "nvidia")
        os.makedirs(root)
        for name in ("pkg-a", "pkg-b", "pkg-c"):
            os.makedirs(os.path.join(root, name))
        try:
            scan([temp], max_entries=2)
        except RuntimeError as exc:
            refused = "cuda-dll-directory-entry-limit-exceeded" in str(exc)
            detail = str(exc)
        except Exception as exc:  # noqa: BLE001 -- only named refusal is accepted
            refused, detail = False, "%s: %s" % (type(exc).__name__, exc)
        else:
            refused, detail = False, "unbounded walk returned normally"
        rows.append((refused,
                     "CUDA DLL census refuses with named error above total entry budget",
                     detail))
    return rows


def watch_main_capture_order_battery(mod) -> list:
    """Fake the watch-only main path and prove failed guards do not start capture."""
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))

    wasapi_name = "wasapi_loopback"
    prior_wasapi = sys.modules.get(wasapi_name)
    # ISOLATION, MEDIDO 2026-11-26: o `main` consulta o registo VIVO do
    # `capture_share` e, numa maquina com o worker do dono a publicar, o braco
    # recebia um cliente (share nao-None) e nunca chegava a construir o tap --
    # `calls=['load']`. O sujeito deste braco e' a ORDEM dos guardas, nao o
    # registo do transporte: com `connect_client` a devolver None ele mede o
    # que promete, com ou sem app aberta.
    prior_share = sys.modules.get("capture_share")
    sys.modules["capture_share"] = types.SimpleNamespace(
        connect_client=lambda **_kw: None)
    wasapi = types.SimpleNamespace(loopback_device_specs=lambda: [{
        "name": "fake endpoint", "rate": 48000, "default": True,
    }])
    calls = []
    prior_loader, prior_tap = mod._load_powerset, mod._tap_for
    prior_evicted = mod.resume_evicted_total
    class FakeStream:
        def start(self):
            calls.append("start")
        def stop(self):
            calls.append("stop")

    class FakeTap:
        stream = FakeStream()

    try:
        sys.modules[wasapi_name] = wasapi
        with tempfile.TemporaryDirectory(prefix="speaker-watch-main-") as temp:
            model = os.path.join(temp, "placeholder.onnx")
            with open(model, "wb") as fh:
                fh.write(b"placeholder path only")
            mod.resume_evicted_total = lambda _path: 0
            mod._load_powerset = lambda *_args, **_kwargs: (
                calls.append("load") or types.SimpleNamespace(
                    sotto_cuda_device_census=True,
                    sotto_graph_assignment_readback="1",
                    sotto_node_assignment_counts={
                        "CUDAExecutionProvider": 46, "CPUExecutionProvider": 6},
                    sotto_node_assignment_cuda_share=0.8846,
                    sotto_node_assignment_cpu=sorted([
                        "/lstm/Concat", "/lstm/Gather", "/lstm/Unsqueeze",
                        "Equal_115", "Gather", "Gather_113"]),
                    sotto_runtime_fallback_readback=False,
                    sotto_provider_readback=["CUDAExecutionProvider"]))
            mod._tap_for = lambda *_args, **_kwargs: (
                calls.append("tap") or (FakeTap(), "mic=fake"))
            with contextlib.redirect_stdout(io.StringIO()):
                ok_rc = mod.main(["--watch-only", "--seg-model", model,
                                  "--duration-s", "-1"])
            chk(ok_rc == 0 and calls == ["load", "tap", "start", "stop"],
                "watch main loads guarded session before constructing capture tap",
                "rc=%r calls=%r" % (ok_rc, calls))

            calls.clear()
            def refuse(*_args, **_kwargs):
                calls.append("load-refused")
                raise RuntimeError("injected CUDA preflight refusal")
            mod._load_powerset = refuse
            with contextlib.redirect_stdout(io.StringIO()):
                refused_rc = mod.main(["--watch-only", "--seg-model", model,
                                       "--duration-s", "-1"])
            chk(refused_rc == 2 and calls == ["load-refused"],
                "watch main refuses before tap/capture when GPU preflight fails",
                "rc=%r calls=%r" % (refused_rc, calls))
    finally:
        mod._load_powerset, mod._tap_for = prior_loader, prior_tap
        mod.resume_evicted_total = prior_evicted
        if prior_share is None:
            sys.modules.pop("capture_share", None)
        else:
            sys.modules["capture_share"] = prior_share
        if prior_wasapi is None:
            sys.modules.pop(wasapi_name, None)
        else:
            sys.modules[wasapi_name] = prior_wasapi
    return out


GPU_POLICY_MUTANTS = [
    ("skip-cuda-provider-preflight",
     "    _require_cuda_execution_provider()",
     "    pass  # mutation: skip CUDA availability"),
    ("allow-cpu-assigned-nodes",
     'or set(assignments) != {"CUDAExecutionProvider"}:',
     'or not assignments:'),
    ("allow-cpu-ep-fallback",
     'if row.get("cpu_ep_fallback_disabled") is not True:',
     'if False:'),
    ("skip-watch-cuda-device-census",
     "    if cuda_device is not True:",
     "    if False:"),
    ("skip-watch-assignment-readback",
     '    if assignment_readback != "1":',
     "    if False:"),
    ("drop-watch-assignment-recording",
     '    opts.add_session_config_entry("session.record_ep_graph_assignment_info", "1")',
     "    pass  # mutation: never ask ORT to record the node assignment"),
    ("skip-watch-provider-readback",
     '    if "CUDAExecutionProvider" not in selected:',
     "    if False:"),
    ("skip-watch-runtime-fallback-constructor",
     '    enable_fallback=0)',
     ')'),
    ("skip-watch-runtime-fallback-disable",
     '        disable_fallback()\n',
     '        pass  # mutation: leave Python runtime fallback untouched\n'),
    ("skip-watch-runtime-fallback-readback",
     '    if getattr(sess, "_enable_fallback", None) is not False:',
     '    if False:'),
    ("skip-watch-unknown-ep-refusal",
     "    if unknown_eps:",
     "    if False:"),
    ("allow-non-allowlisted-cpu-node",
     "    if unexpected:",
     "    if False:"),
    ("skip-watch-cuda-share-floor",
     "    if cuda_share < WATCH_CUDA_NODE_SHARE_MIN:",
     "    if False:"),
]


def gpu_policy_mutation_checks(source: str) -> list:
    """Require the focused policy battery to catch weakened safety guards."""
    rows = []
    with tempfile.TemporaryDirectory(prefix="sidecar-gpu-mut-") as tmp:
        for idx, (label, old, new) in enumerate(GPU_POLICY_MUTANTS):
            if old not in source:
                rows.append((False, "mutation anchor " + label, "anchor missing"))
                continue
            path = os.path.join(tmp, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                mutant = load_module(path, "speaker_gpu_policy_mut_%d" % idx)
                result = gpu_policy_battery(mutant)
            except Exception as exc:  # a mutant that fails import was not tested
                rows.append((False, "mutation " + label,
                             "decorative mutant: %s" % type(exc).__name__))
                continue
            failures = [name for ok, name, _ in result if not ok]
            rows.append((bool(failures), "mutation caught " + label,
                         "; ".join(failures[:2])))
    return rows


def _installed_policy_row(mod) -> tuple:
    """The ONE cheap arm: the shipped policy asks for the provider we measured.

    Pure on purpose -- it reads a module constant, opens no model, and is what
    `installed_consumer_mutation` reddens. The expensive arms below sit on top.
    """
    wanted = str(getattr(mod, "DIARIZER_PROVIDER", "")).strip().lower()
    return (wanted == "cpu", "installed policy asks for cpu by name",
            "DIARIZER_PROVIDER=%r" % (getattr(mod, "DIARIZER_PROVIDER", None),))


def installed_consumer_check(mod) -> list:
    """The real `--speakers` consumer under the MEASURED provider policy.

    WHAT THIS ARM USED TO SAY, and why THAT was the defect (2026-11-25): it
    required `_make_live_diarizer` to REFUSE -- the row was literally named
    `installed --speakers diarizer consumer fails closed` -- because sherpa-onnx
    1.13.4 ships no strict GPU adapter. That was the contract while the sidecar
    asked for CUDA by default. Since 2026-11-24 it asks for CPU BY NAME
    (`DIARIZER_PROVIDER`), the provider `_main/_diar-run.py` measured (DER
    0,03 %, RTF 0,416, 277 MB, 0,9 s load at 2 threads): a CPU request cannot
    fall back FROM an accelerator it never asked for, so "refuse everything"
    became "refuse cuda, BUILD cpu". The old row therefore reported a working
    product as RED, forever.

    The contract now, both halves measured here: the shipped policy is cpu; the
    cpu consumer really builds the full diarizer from the cached models; and a
    cuda request is still refused by name, before either model is loaded.
    """
    rows = []

    def chk(ok, name, detail=""):
        rows.append((bool(ok), name, detail))

    try:
        import onnxruntime
        import sherpa_onnx
    except Exception as exc:  # noqa: BLE001 -- inventory only, no model construction
        chk(False, "installed runtimes import",
            "%s: %s" % (type(exc).__name__, exc))
        return rows

    providers = list(onnxruntime.get_available_providers())
    version = getattr(sherpa_onnx, "__version__", "unknown")
    rows.append(_installed_policy_row(mod))
    models_present = (os.path.isfile(mod.DEFAULT_SEG_MODEL)
                      and os.path.isfile(mod.DEFAULT_EMB_MODEL))
    chk(models_present, "cached speaker models are on disk",
        "" if models_present else mod.DEFAULT_SEG_MODEL)
    if not models_present:
        return rows

    args = types.SimpleNamespace(
        seg_model=mod.DEFAULT_SEG_MODEL,
        emb_model=mod.DEFAULT_EMB_MODEL,
        threads=1,
        num_speakers=-1,
        threshold=0.9,
    )
    prior = getattr(mod, "DIARIZER_PROVIDER", None)

    # POSITIVE: the shipped policy builds the real consumer (models load once).
    try:
        mod.DIARIZER_PROVIDER = "cpu"
        built = mod._make_live_diarizer(args)
        chk(callable(built), "installed cpu consumer builds the real diarizer",
            "sherpa-onnx=%s providers=%r" % (version, providers))
    except Exception as exc:  # noqa: BLE001 -- any failure is the arm's verdict
        chk(False, "installed cpu consumer builds the real diarizer",
            "%s: %s" % (type(exc).__name__, exc))
    finally:
        mod.DIARIZER_PROVIDER = prior
        built = None
        gc.collect()

    # NEGATIVE: cuda is still refused BY NAME, before any model file is read.
    try:
        mod.DIARIZER_PROVIDER = "cuda"
        mod._make_live_diarizer(args)
        chk(False, "installed cuda request is refused by name",
            "_make_live_diarizer returned for a cuda request")
    except RuntimeError as exc:
        text = str(exc).lower()
        chk("cuda" in text or "gpu" in text,
            "installed cuda request is refused by name", str(exc)[:160])
    except Exception as exc:  # noqa: BLE001 -- an unexpected exception is not the guard
        chk(False, "installed cuda request is refused by name",
            "%s: %s" % (type(exc).__name__, exc))
    finally:
        mod.DIARIZER_PROVIDER = prior
    return rows


def installed_consumer_mutation(source: str) -> list:
    """The policy arm's own negative control: flip the constant, it must redden."""
    old = 'DIARIZER_PROVIDER = "cpu"'
    if old not in source:
        return [(False, "mutation anchor installed-policy", "anchor missing")]
    with tempfile.TemporaryDirectory(prefix="sidecar-installed-mut-") as tmp:
        path = os.path.join(tmp, "mutant_policy.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source.replace(old, 'DIARIZER_PROVIDER = "cuda"', 1))
        mutant = load_module(path, "speaker_installed_policy_mut")
        ok, _name, detail = _installed_policy_row(mutant)
        return [(not ok, "mutation caught installed-policy-flipped", detail)]


def score_fake_controls() -> list:
    """Code-only positive/negative controls for the Redux score consumer seam."""
    path = os.path.join(REPO, "_main", "bench", "separate.py")
    if not os.path.isfile(path):
        return [(False, "score benchmark module exists", path)]

    pool_names = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                  "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")
    saved_env = {name: os.environ.get(name) for name in pool_names}
    saved_path = list(sys.path)
    module = None
    rows = []

    def chk(ok, name, detail=""):
        rows.append((bool(ok), name, detail))

    try:
        spec = importlib.util.spec_from_file_location("speaker_score_fake", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        class FakeSession:
            def __init__(self, enabled=False):
                self._enable_fallback = enabled

            def get_providers(self):
                return ["CUDAExecutionProvider"]

        class FakeEngine:
            def __init__(self, *, device="cuda", bad_fallback=False):
                self.device = device
                self.cpu_execution_policy = "cuda-only" if device == "cuda" else "cpu"
                self.transcribed = []
                self._model = types.SimpleNamespace(
                    cpu_ep_fallback_disabled=True,
                    _sotto_vad_exists=False,
                    _sotto_vad_deferred=False,
                    preprocessor=FakeSession(), encoder=FakeSession(),
                    decoder_joint=FakeSession(enabled=bad_fallback),
                )
                self.provider_readback = {
                    graph: ["CUDAExecutionProvider"]
                    for graph in module.REDUX_EAGER_GRAPHS
                }
                options = {
                    graph: {
                        "disable_cpu_ep_fallback": "1",
                        "runtime_fallback_disabled": not (bad_fallback and
                                                            graph == "decoder_joint-model.onnx"),
                    }
                    for graph in module.REDUX_EAGER_GRAPHS
                }
                self.thread_policy = {
                    "session_options_readback": options,
                    "runtime_fallback_readback": {
                        graph: row["runtime_fallback_disabled"]
                        for graph, row in options.items()
                    },
                }

            def transcribe(self, pcm):
                self.transcribed.append(module.np.asarray(pcm).copy())
                return "Maria disse dado privado", [{"start": 0.0, "end": 0.1}]

        events = []
        engine = FakeEngine()

        class FakeConsumer:
            def __init__(self):
                events.append("consumer")
                self.engine_calls = 0

            def engine(self):
                events.append("engine")
                self.engine_calls += 1
                return engine

        def release():
            events.append("release")
            return {"models_cleared": 1, "torch_cuda_reserved_mb_after": 0.0}

        consumer, backend, readback = module.create_score_backend(FakeConsumer, release)
        mix = module.np.asarray([0.1, 0.2], dtype=module.np.float32)
        stem_0 = module.np.asarray([0.3, 0.4], dtype=module.np.float32)
        stem_1 = module.np.asarray([-0.3, -0.4], dtype=module.np.float32)
        scores = module.score_inputs(backend, [("mix", mix), ("stem_0", stem_0),
                                                ("stem_1", stem_1)])
        chk(events == ["release", "consumer", "engine"],
            "separator release precedes one production-consumer engine construction",
            repr(events))
        chk(consumer.engine_calls == 1 and len(engine.transcribed) == 3
            and all(module.np.array_equal(a, b) for a, b in
                    zip(engine.transcribed, (mix, stem_0, stem_1))),
            "mix and two stems are sent as three distinct audio calls")
        encoded = json.dumps({"scores": scores, "readback": readback}, sort_keys=True)
        chk(set(scores) == {"mix", "stem_0", "stem_1"}
            and all("text" not in row for row in scores.values())
            and all(len(row["text_sha256"]) == 64 for row in scores.values())
            and "Maria" not in encoded and "speaker" not in encoded,
            "score output stores only anonymous labels and transcript hashes")

        before = len(engine.transcribed)
        try:
            module.score_inputs(backend, [("speaker-1", mix)])
            identity_rejected = False
        except ValueError:
            identity_rejected = True
        chk(identity_rejected and len(engine.transcribed) == before,
            "identity labels are rejected before reaching the ASR")

        cpu_engine = FakeEngine(device="cpu")
        cpu_calls = []
        class CpuConsumer:
            def engine(self):
                return cpu_engine
        try:
            module.create_score_backend(CpuConsumer, lambda: {"models_cleared": 0})
            cpu_rejected = False
        except RuntimeError:
            cpu_rejected = True
        chk(cpu_rejected and not cpu_engine.transcribed,
            "CPU backend is refused before any audio transcription")

        fallback_engine = FakeEngine(bad_fallback=True)
        class FallbackConsumer:
            def engine(self):
                return fallback_engine
        try:
            module.create_score_backend(FallbackConsumer, lambda: {"models_cleared": 0})
            fallback_rejected = False
        except RuntimeError:
            fallback_rejected = True
        chk(fallback_rejected and not fallback_engine.transcribed,
            "missing runtime fallback readback is refused before transcription")

        read_calls = []
        args = types.SimpleNamespace(score=True, wav="synthetic.wav")
        def refuse_preflight(_args):
            events.append("preflight-refuse")
            raise RuntimeError("no CUDA/fallback guard")
        def reader(wav):
            read_calls.append(wav)
            return object()
        try:
            module.read_audio_after_score_preflight(args, refuse_preflight, reader)
            read_refused = False
        except RuntimeError:
            read_refused = True
        chk(read_refused and not read_calls,
            "failed CUDA/fallback preflight refuses before audio is opened")

    except Exception as exc:
        chk(False, "score fake controls execute", "%s: %s" % (type(exc).__name__, exc))
    finally:
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        sys.path[:] = saved_path
    env_restored = all(os.environ.get(name) == saved_env[name] for name in pool_names)
    path_restored = sys.path == saved_path
    chk(env_restored and path_restored,
        "fake control restores numeric environment and import path on exit")
    return rows


def mic_battery(mod) -> list:
    """The microphone path: which device, and what the mix does to the audio.

    OWNER ORDER 2026-11-25: *"its capture my mic and transcript it aswell, in
    real time. and its any mic not just mine cause this will be a product"*.
    Every arm is fake: no PortAudio device is opened and no microphone is
    recorded, so the battery runs on any machine and cannot pass by hearing the
    developer's room.

    What it proves, in the order the product needs it:
      1. the device chosen IS a microphone -- a virtual cable, the Sound Mapper
         and Stereo Mix never are, and the OS's default is followed otherwise;
      2. a machine without one gets a NAMED refusal, not a crash and not the
         loopback quietly pretending nothing happened;
      3. the mix keeps the loopback level constant (no AGC pumping), adds the
         microphone on top, converts 48 kHz to 16 kHz, carries microphone audio
         a loopback block could not hold, and leaves the loopback path
         byte-identical when there is no microphone at all.
    """
    rows = []

    def chk(ok, name, detail=""):
        rows.append((bool(ok), name, detail))

    import numpy as np

    class FakeSD:
        def __init__(self, devices, default_input):
            self.devices = devices
            self.default_input = default_input

        def query_devices(self, kind=None, device=None):  # noqa: ARG002
            if kind == "input":
                return {"name": self.default_input}
            return self.devices

    cable = {"name": "CABLE Output (VB-Audio Virtual Cable)",
             "max_input_channels": 8, "default_samplerate": 44100}
    usb = {"name": "Microphone (Some USB Mic)", "max_input_channels": 2,
           "default_samplerate": 48000}
    hfp = {"name": r"Headset (@System32\drivers\bthhfenum.sys,#2) Hands-Free",
           "max_input_channels": 1, "default_samplerate": 16000}

    dev, why = mod.pick_microphone(sd=FakeSD([cable, usb], cable["name"]))
    chk(dev is not None and dev["name"] == usb["name"],
        "a virtual cable is never chosen, even as the OS default", why)

    dev, why = mod.pick_microphone("some usb", sd=FakeSD([cable, usb], cable["name"]))
    chk(dev is not None and dev["name"] == usb["name"],
        "an explicit microphone name is honoured over the default", why)

    dev, why = mod.pick_microphone("cable", sd=FakeSD([cable, usb], cable["name"]))
    chk(dev is not None and "CABLE" in dev["name"],
        "an explicit name overrules even a device the product would not pick", why)

    dev, why = mod.pick_microphone(sd=FakeSD([cable], cable["name"]))
    chk(dev is None and "only virtual" in why,
        "no real microphone is a NAMED refusal, not a crash", why)

    dev, why = mod.pick_microphone(sd=FakeSD([hfp], hfp["name"]))
    chk(dev is not None and dev["name"] == hfp["name"],
        "a headset microphone IS offered: refusing it is the user's call", why)

    # ── the mix arithmetic, with fake taps (no device is opened) ────────────
    class FakePrimary:
        rate = 48000
        block_ms = 100
        block = 4800
        endpoint_id = "ep"
        device = {"name": "loopback"}

        def __init__(self, cb):
            self.cb = cb
            self.stream = self

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    class FakeMic:
        rate = 16000
        device = {"name": "mic"}
        dropped_samples = 0
        peak = 0.5

        def __init__(self, feed):
            self.feed = list(feed)
            self.started = False
            self.pushed = 0

        def start(self):
            self.started = True

        def stop(self):
            pass

        def close(self):
            pass

        def drain(self):
            return self.feed.pop(0) if self.feed else None

        def push_back(self, pcm):
            self.pushed += int(pcm.size)
            self.feed.insert(0, pcm)

    def _open(mic_feed, primary_factory=FakePrimary):
        got = []
        mic = FakeMic(mic_feed)
        saved = mod._mic_or_refusal
        mod._mic_or_refusal = lambda prefer: (mic, "fake microphone")  # noqa: ARG005
        try:
            tap, note = mod.open_stream(primary_factory, got.append)
        finally:
            mod._mic_or_refusal = saved
        return tap, got, mic, note

    class LateRatePrimary(FakePrimary):
        """The PROCESS rung's real shape: `rate` is provisional until start().

        `ProcessLoopbackTap` declares 48 kHz and then `_open()` writes back the
        format the winning arm really accepted (the ladder has a 44.1 kHz arm).
        A mix that freezes the rate in `attach()` therefore resamples 44.1 kHz
        audio as 48 kHz -- 4 410 samples out as 1 470 instead of 1 600, an 8 %
        pitch error on the rung the microphone was added to (2026-11-25).
        """

        def __init__(self, cb):
            super().__init__(cb)
            self.rate = 48000

        def start(self):
            self.rate = 44100
            self.block = 4410

    tap, got, mic, note = _open([np.full(1600, 0.2, dtype=np.float32)])
    tap.start()
    src_block = np.full(4800, 0.4, dtype=np.float32)
    tap.primary.cb(src_block)
    out = got[-1]
    chk(mic.started, "the microphone stream starts with the conversation tap", note)
    chk(getattr(tap, "block", None) == 4800,
        "the mix still owes the loop the loopback's block size (it does not "
        "hide the tap surface)", "block=%r" % (getattr(tap, "block", None),))
    chk(out.size == 1600,
        "a 100 ms 48 kHz loopback block becomes 1600 samples at 16 kHz",
        "n=%d" % out.size)
    chk(abs(float(out[0]) - 0.45) < 1e-6,
        "the microphone is added on top of an attenuated loopback block",
        "%.4f (expected 0.75*0.4 + 0.75*0.2)" % float(out[0]))
    chk(abs(float(src_block[0]) - 0.4) < 1e-6,
        "the loopback's own buffer is never written by the mix",
        "%.4f" % float(src_block[0]))

    mic.feed = []
    tap.primary.cb(np.full(4800, 0.4, dtype=np.float32))
    chk(abs(float(got[-1][0]) - 0.3) < 1e-6,
        "a silent microphone leaves the level CONSTANT, not 1.0 (no AGC pumping)",
        "%.4f (expected 0.75*0.4)" % float(got[-1][0]))

    mic.feed = [np.full(4000, 1.0, dtype=np.float32)]
    tap.primary.cb(np.full(4800, 0.0, dtype=np.float32))
    chk(mic.pushed == 2400,
        "microphone audio a loopback block cannot hold is carried to the next one",
        "pushed=%d (expected 2400)" % mic.pushed)
    chk(float(np.abs(got[-1]).max()) <= 1.0,
        "the mix is clipped, never out of range",
        "peak=%.3f" % float(np.abs(got[-1]).max()))

    # ── the primary's rate is read from the OPEN stream, not frozen in attach ─
    late, got_late, mic_late, _note = _open(
        [np.full(1600, 0.2, dtype=np.float32)], primary_factory=LateRatePrimary)
    late.start()                     # the winning arm writes 44.1 kHz back
    late.primary.cb(np.full(late.primary.block, 0.4, dtype=np.float32))
    out_late = got_late[-1] if got_late else np.zeros(0, dtype=np.float32)
    chk(out_late.size == 1600 and abs(float(out_late[0]) - 0.45) < 1e-6,
        "a primary that settles 44.1 kHz in start() is resampled at THAT rate",
        "n=%d want=1600 v=%.4f (a frozen 48 kHz rate gives 1470 samples)"
        % (out_late.size, float(out_late[0]) if out_late.size else -1.0))

    # ── a microphone that delivers zeros is REPORTED, not silently absorbed ──
    import contextlib as _ctx
    import io as _io
    got_silent = []
    mic_silent = FakeMic([])
    mic_silent.peak = 0.0
    saved = mod._mic_or_refusal
    mod._mic_or_refusal = lambda prefer: (mic_silent, "fake microphone")  # noqa: ARG005
    out_buf = _io.StringIO()
    try:
        with _ctx.redirect_stdout(out_buf):
            tap3, _note3 = mod.open_stream(FakePrimary, got_silent.append)
            for _ in range(60):
                tap3.primary.cb(np.zeros(4800, dtype=np.float32))
    finally:
        mod._mic_or_refusal = saved
    said = out_buf.getvalue()
    chk(said.count("MIC_SILENT") == 1 and "digital-silence" in said,
        "a microphone delivering zeros is reported ONCE, by name",
        said.strip().splitlines()[0] if said.strip() else "nothing printed")

    got_none = []
    saved = mod._mic_or_refusal
    mod._mic_or_refusal = lambda prefer: (None, "no microphone: only virtual")  # noqa: ARG005
    try:
        tap2, note2 = mod.open_stream(FakePrimary, got_none.append)
    finally:
        mod._mic_or_refusal = saved
    chk(not isinstance(tap2, mod.ConversationTap),
        "without a microphone the plain loopback tap is returned", note2)
    tap2.cb(np.full(4800, 0.5, dtype=np.float32))
    chk(bool(got_none) and abs(float(got_none[-1][0]) - 0.5) < 1e-9,
        "and that path is untouched: no attenuation, no resample, no mix",
        "%.3f" % (float(got_none[-1][0]) if got_none else -1.0))

    # ── the privacy switch is an ENABLE list, and a failed primary leaks nothing ─
    # REVIEWER FINDING 2026-11-25: `SOTTO_MIC=00` used to fall through to ON --
    # a typo that turns a microphone on is the one direction that must never be
    # a guess -- and a primary that raised after the mic was opened never closed
    # it, leaving one input stream alive per failed ladder candidate.
    saved = mod._mic_or_refusal
    mod._mic_or_refusal = lambda prefer: (FakeMic([]), "fake microphone")  # noqa: ARG005
    try:
        import os as _os
        prior_env = _os.environ.get("SOTTO_MIC")
        verdicts = {}
        try:
            for value in ("00", "0", "off", "no", "false", "", "1", "YES", "en"):
                _os.environ["SOTTO_MIC"] = value
                got_switch = []
                tap_switch, _n = mod.open_stream(FakePrimary, got_switch.append)
                verdicts[value] = isinstance(tap_switch, mod.ConversationTap)
        finally:
            if prior_env is None:
                _os.environ.pop("SOTTO_MIC", None)
            else:
                _os.environ["SOTTO_MIC"] = prior_env
        chk(not any(verdicts[v] for v in ("00", "0", "off", "no", "false")),
            "SOTTO_MIC: every off-looking value (including `00`) keeps the "
            "microphone CLOSED", str(verdicts))
        chk(all(verdicts[v] for v in ("", "1", "YES", "en")),
            "SOTTO_MIC: an explicit enable value (or none) opens it", str(verdicts))

        leak_mic = FakeMic([])
        closed = {"n": 0}
        leak_mic.close = lambda: closed.__setitem__("n", closed["n"] + 1)
        mod._mic_or_refusal = lambda prefer, m=leak_mic: (m, "fake microphone")  # noqa: ARG005

        def _explode(_sink):
            raise RuntimeError("the loopback refused to open")

        raised = False
        try:
            mod.open_stream(_explode, lambda _b: None)
        except RuntimeError:
            raised = True
        chk(raised and closed["n"] == 1,
            "a primary that fails to open closes the microphone it already "
            "opened (no leaked input stream per ladder rung)",
            "raised=%s closes=%d" % (raised, closed["n"]))
    finally:
        mod._mic_or_refusal = saved
    # ── the LADDER FACTORY: every rung, not only the endpoint rung ────────
    # MEASURED DEFECT 2026-11-25: `open_stream` was called on the WASAPI rung
    # only. The process and PortAudio rungs returned their tap directly, so
    # the owner's speech never reached the ASR whenever the ladder landed
    # there. Drive the real factory with fake primaries (the worker module
    # needs COM/PortAudio at import, so only this function's AST is executed)
    # and inject THIS mic module as sys.modules["mic_tap"], so the fake
    # microphone and SOTTO_MIC below are what the factory really sees.
    import ast as _ast
    import types as _types

    # Mutants are loaded from a temp dir, so mod.__file__ is NOT the worker's
    # neighbour; the module path the oracle loaded the real mic module from is.
    worker_path = os.path.join(os.path.dirname(os.path.abspath(MIC_MODULE_PATH)),
                               "sotto_worker.py")
    with open(worker_path, "r", encoding="utf-8") as fh:
        worker_source = fh.read()
    factory_def = next(n for n in _ast.parse(worker_source).body
                       if isinstance(n, _ast.FunctionDef) and n.name == "LoopbackTap")
    factory_ast = _ast.fix_missing_locations(
        _ast.Module(body=[factory_def], type_ignores=[]))
    made = []
    notes = []

    class _FakePrimary:
        def __init__(self, cb, rate, kind, block_ms=100, **kw):
            self.cb = cb
            self.rate = rate
            self.kind = kind
            self.block_ms = int(block_ms)
            self.block = int(rate * self.block_ms / 1000)
            self.device = {"name": kind}
            self.endpoint_id = kw.get("endpoint_id")
            self.kw = kw
            self.stream = self
            self.started = False
            made.append(self)

        def start(self):
            self.started = True

        def stop(self):
            pass

        def close(self):
            pass

    class FakeProcessTap(_FakePrimary):
        def __init__(self, cb, pid, pid_desc="", block_ms=100):
            super().__init__(cb, 48000, "process", block_ms,
                             pid=pid, pid_desc=pid_desc)

    class FakePortAudioTap(_FakePrimary):
        def __init__(self, device, cb, want_rate=16000, block_ms=100):
            super().__init__(cb, want_rate, "portaudio", block_ms, device=device)

    class FakeWasapiTap(_FakePrimary):
        def __init__(self, cb, block_ms=100, endpoint_id=None):
            super().__init__(cb, 48000, "wasapi", block_ms,
                             endpoint_id=endpoint_id)

    fake_wasapi = _types.ModuleType("wasapi_loopback")
    fake_wasapi.WasapiLoopbackTap = FakeWasapiTap
    factory_ns = {
        "TARGET_SR": mod.TARGET_SR,
        "ProcessLoopbackTap": FakeProcessTap,
        "FileTap": lambda *a, **kw: None,  # noqa: ARG005
        "_PortAudioTap": FakePortAudioTap,
        "err": notes.append,
        "__name__": "loopback_factory_oracle",
    }
    exec(compile(factory_ast, worker_path, "exec"), factory_ns)
    factory = factory_ns["LoopbackTap"]

    rungs = (
        ("process", {"name": "app", "process_loopback": True,
                     "target_pid": 4242, "target_desc": "app"}),
        ("wasapi", {"name": "endpoint", "wasapi_loopback": True,
                    "endpoint_id": "ep-1"}),
        ("portaudio", {"name": "pa", "max_input_channels": 2,
                       "index": 3, "default_samplerate": 16000}),
    )
    saved_modules = {k: sys.modules.get(k)
                     for k in ("mic_tap", "wasapi_loopback")}
    saved_env = os.environ.get("SOTTO_MIC")
    saved_refusal = mod._mic_or_refusal
    sys.modules["mic_tap"] = mod
    sys.modules["wasapi_loopback"] = fake_wasapi
    try:
        for kind, dev in rungs:
            # (1) microphone available: the mixer wraps THIS rung's primary.
            made.clear()
            notes.clear()
            mod._mic_or_refusal = lambda prefer, m=FakeMic([np.full(
                1600, 0.2, dtype=np.float32)]): (m, "fake microphone")  # noqa: ARG005
            os.environ["SOTTO_MIC"] = "1"
            got = []
            tap = factory(dev, got.append)
            chk(isinstance(tap, mod.ConversationTap),
                "%s rung: an available microphone is mixed in" % kind,
                "tap=%s note=%r" % (type(tap).__name__,
                                    notes[-1] if notes else ""))
            primary = getattr(tap, "primary", None)
            chk(primary is made[-1] if made else False,
                "%s rung: the mixer wraps the primary this rung would return" % kind,
                "primary=%r" % (getattr(primary, "kind", None),))
            if primary is not None:
                chk((primary.kind == kind and
                     (kind != "process" or (primary.kw.get("pid") == 4242 and
                                            primary.kw.get("pid_desc") == "app")) and
                     (kind != "wasapi" or primary.endpoint_id == "ep-1") and
                     (kind != "portaudio" or primary.kw.get("device") is dev)),
                    "%s rung: pid / endpoint / device selection is untouched" % kind,
                    "kw=%r" % (primary.kw,))
                got.clear()
                src = np.full(primary.block, 0.4, dtype=np.float32)
                primary.cb(src)
                out = got[-1] if got else np.zeros(0, dtype=np.float32)
                chk(out.size == 1600 and abs(float(out[0]) - 0.45) < 1e-6,
                    "%s rung: the microphone's audio reaches ASR in the mix" % kind,
                    "n=%d v=%.4f" % (out.size, float(out[0]) if out.size else -1.0))
            else:
                chk(False, "%s rung: pid / endpoint / device selection is untouched" % kind,
                    "no primary was built")
                chk(False, "%s rung: the microphone's audio reaches ASR in the mix" % kind,
                    "no primary was built")

            # (2) SOTTO_MIC=0: the plain tap and byte-identical audio.
            made.clear()
            os.environ["SOTTO_MIC"] = "0"
            got.clear()
            tap0 = factory(dev, got.append)
            plain0 = made[-1] if made else None
            chk(not isinstance(tap0, mod.ConversationTap) and plain0 is not None,
                "%s rung: SOTTO_MIC=0 returns the plain tap" % kind,
                "tap=%s" % type(tap0).__name__)
            if plain0 is not None:
                src0 = np.full(plain0.block, 0.4, dtype=np.float32)
                plain0.cb(src0)
                out0 = got[-1] if got else np.zeros(0, dtype=np.float32)
                chk(out0.size == src0.size and np.array_equal(out0, src0),
                    "%s rung: SOTTO_MIC=0 leaves the block byte-identical" % kind,
                    "n=%d v=%.4f" % (out0.size, float(out0[0]) if out0.size else -1.0))
            else:
                chk(False, "%s rung: SOTTO_MIC=0 leaves the block byte-identical" % kind,
                    "no primary was built")

            # (3) a machine with no microphone: the same plain path, same bytes.
            made.clear()
            os.environ["SOTTO_MIC"] = "1"
            mod._mic_or_refusal = lambda prefer: (None, "no microphone: fake")  # noqa: ARG005
            got.clear()
            tap2 = factory(dev, got.append)
            plain2 = made[-1] if made else None
            chk(not isinstance(tap2, mod.ConversationTap) and plain2 is not None,
                "%s rung: no microphone returns the plain tap" % kind,
                "tap=%s" % type(tap2).__name__)
            if plain2 is not None:
                src2 = np.full(plain2.block, 0.5, dtype=np.float32)
                plain2.cb(src2)
                out2 = got[-1] if got else np.zeros(0, dtype=np.float32)
                chk(out2.size == src2.size and np.array_equal(out2, src2),
                    "%s rung: no microphone leaves the block byte-identical" % kind,
                    "n=%d v=%.4f" % (out2.size, float(out2[0]) if out2.size else -1.0))
            else:
                chk(False, "%s rung: no microphone leaves the block byte-identical" % kind,
                    "no primary was built")
    finally:
        mod._mic_or_refusal = saved_refusal
        if saved_env is None:
            os.environ.pop("SOTTO_MIC", None)
        else:
            os.environ["SOTTO_MIC"] = saved_env
        for k, v in saved_modules.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return rows


MIC_MUTANTS = [
    # The defect the first unit check measured: gain only on blocks that carry
    # microphone audio, so the loopback level jumps between blocks.
    ("mix-gain-only-on-mic-blocks",
     "        pcm = pcm * LOOPBACK_GAIN",
     "        pcm = pcm"),
    # Microphone audio past the loopback block is DROPPED instead of carried.
    ("leftover-mic-audio-dropped",
     "                self.mic.push_back(microphone[n:])",
     "                pass"),
    # The filter that keeps a virtual cable from becoming the microphone.
    ("a-virtual-cable-becomes-the-microphone",
     '"vb-audio", "voicemeeter", "cable input", "cable output", "cable out",',
     '"vb-audio-nope",'),
    # The mix stopped delegating the rest of the tap surface, so the run loop
    # dies on `tap.block` with zero captions (measured 2026-11-25).
    ("the-mix-hides-the-tap-surface",
     "        return getattr(primary, name)",
     "        raise AttributeError(name)"),
    # A microphone that only ever delivers zeros is absorbed as "nobody is
    # speaking", which is exactly the silence this repo refuses to leave unnamed.
    ("a-silent-microphone-is-not-reported",
     "            self._silent_reported = True", "            pass"),
    # The explicit name is ignored, so a user cannot choose their microphone.
    ("explicit-microphone-name-ignored",
     "    if prefer:\n        low = prefer.strip().lower()",
     "    if False:\n        low = prefer.strip().lower()"),
    # The new ladder arms must have teeth too. Four DIFFERENT behaviours:
    # the privacy switch, the microphone's contribution, the primary's sample
    # rate (the process rung is 48 kHz), and the byte-identical no-mic path.
    ("sotto-mic-zero-ignored",
     '    setting = os.environ.get("SOTTO_MIC", "").strip().lower()\n'
     '    if not enabled or (setting not in ("", "1", "on", "true", "yes", "en")):',
     "    if not enabled:"),
    ("the-microphone-contributes-nothing",
     "MIC_GAIN = 0.75",
     "MIC_GAIN = 0.0"),
    # MEASURED 2026-11-25: the mix used to freeze the primary's rate in
    # `attach()`, but `ProcessLoopbackTap.rate` is PROVISIONAL until `_open()`
    # reads the winning arm back, so a 44.1 kHz arm was resampled as 48 kHz
    # (4 410 samples -> 1 470 instead of 1 600). The mutation is the old
    # behaviour: read the rate ONCE, before the stream starts.
    ("a-48k-primary-is-treated-as-16k",
     '            return int(getattr(self.primary, "rate", None) or self.src_rate\n'
     "                       or TARGET_SR)",
     "            return self.src_rate"),
    ("no-microphone-path-attenuates-audio",
     "    mic, note = _mic_or_refusal(prefer)\n"
     "    if mic is None:\n"
     "        return make_primary(sink), note",
     "    mic, note = _mic_or_refusal(prefer)\n"
     "    if mic is None:\n"
     "        return make_primary(lambda b: sink(b * 0.9)), note"),
    # A primary that refuses to open must close the microphone it already
    # opened; without the `except` the ladder leaks one input stream per failed
    # candidate (reviewer finding 2026-11-25).
    ("a-failed-primary-leaks-the-microphone",
     "    except BaseException:\n",
     "    except ZeroDivisionError:\n"),
]


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
    # ESTE ERA DECORATIVO, e o proprio oracao nao via: substituia
    # `except Exception` por `except _NeverMatchesThis`, um nome que nao
    # existe, e o mutante rebentava no IMPORT com NameError. Contava como
    # "apanhado" sem ter corrido um unico check -- e `caught += 1` nao sabia a
    # diferenca. Um mutante que nao carrega prova que o gate esta vivo, nao
    # que o gate tem olhos.
    #
    # Agora o mutante RE-LANCA: o modelo que rebenta leva o sidecar abaixo, que
    # e' exactamente o defeito que o arm quer apanhar. Carrega, corre, e os
    # checks veem.
    ("a-raised-model-kills-the-sidecar",
     "    except Exception as exc:                                    # noqa: BLE001",
     "    except Exception as exc:                                    # noqa: BLE001\n"
     "        raise"),
    # A COPIA PODRE (achado da auditoria): a constante do sidecar passa a
    # discordar da ponte. O mutante tem de ser apanhado pelo check de
    # IGUALDADE -- e nao por um accidento qualquer.
    ("a-stale-freshness-copy",
     "DEFAULT_MAX_AGE_S = 30.0",
     "DEFAULT_MAX_AGE_S = 45.0"),
    # A CADENCIA CORRIDA: publica de 40 em 40 s com uma janela de 30 s na
    # ponte, e um payload atrasado um tick ja e' velho. O check do intervalo
    # tem de o apanhar.
    ("a-cadence-outlives-the-window",
     "DEFAULT_EVERY_S = 5.0",
     "DEFAULT_EVERY_S = 40.0"),
    # THE PICKER'S SECOND DEFECT (2026-11-25): the sidecar and the worker must
    # ask the SAME question. A picker that skips the live meter, or that reads
    # it backwards, captures a different endpoint than the one being
    # transcribed -- 91 captions, 0 attributed, no crash and no error.
    ("the-live-meter-rule-removed",
     "    for entry in live or ():\n"
     "        if not entry.get(\"meter_peak\"):\n"
     "            continue",
     "    for entry in ():\n"
     "        if not entry.get(\"meter_peak\"):\n"
     "            continue"),
    ("the-meter-peak-read-backwards",
     "        if not entry.get(\"meter_peak\"):\n"
     "            continue",
     "        if entry.get(\"meter_peak\"):\n"
     "            continue"),
]


def main() -> int:
    if "--score-fake-only" in sys.argv[1:]:
        rows = score_fake_controls()
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        green = sum(1 for ok, _, _ in rows if ok)
        print("REDUX SCORE FAKE VERDICT: %s (%d/%d controls)"
              % ("PASS" if green == len(rows) else "FAIL", green, len(rows)))
        return EXIT_PASS if green == len(rows) else EXIT_FAIL

    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    with open(MIC_MODULE_PATH, "r", encoding="utf-8") as fh:
        mic_source = fh.read()

    if "--gpu-policy-only" in sys.argv[1:]:
        mod = load_module(MODULE_PATH, "speaker_sidecar_gpu_policy")
        rows = gpu_policy_battery(mod)
        rows.extend(gpu_policy_mutation_checks(source))
        if "--probe-installed-consumer" in sys.argv[1:]:
            rows.extend(installed_consumer_check(mod))
            rows.extend(installed_consumer_mutation(source))
        for ok, name, detail in rows:
            print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                                 ("  " + detail) if detail else ""))
        green = sum(1 for ok, _, _ in rows if ok)
        print("GPU POLICY VERDICT: %s (%d/%d checks)"
              % ("PASS" if green == len(rows) else "FAIL", green, len(rows)))
        return EXIT_PASS if green == len(rows) else EXIT_FAIL

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
    mic_mod = load_module(MIC_MODULE_PATH, "mic_tap_live")
    rows = battery(mod)
    rows.extend(mic_battery(mic_mod))
    for ok, name, detail in rows:
        print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                             ("  " + detail) if detail else ""))
    green = sum(1 for ok, _, _ in rows if ok)
    print("\n  %d/%d" % (green, len(rows)))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    caught = 0
    weak = 0
    tmp = tempfile.mkdtemp(prefix="sidecar-oracle-mut-")
    try:
        for idx, (label, old, new) in enumerate(MUTANTS):
            if old not in source:
                print("  RED   mutant %-42s ANCHOR MISSING -- oracle is stale"
                      % label)
                weak += 1
                continue
            path = os.path.join(tmp, "mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source.replace(old, new, 1))
            try:
                bad = load_module(path, "speaker_sidecar_mut_%d" % idx)
            except Exception as exc:                                # noqa: BLE001
                # UM MUTANTE QUE NAO CARREGA NAO E' UM MUTANTE APANHADO.
                # E' uma mutacao decorativa: nada foi testado. Contar isto
                # como apanhado foi o defeito que o auditor provou -- o gate
                # dizia 6/6 com dois mutantes que nunca correram um check.
                # Agora conta a parte e o VERDICT REPROVA, porque um braco
                # negativo que promete N mutantes e testa N-2 nao cumpre.
                print("  RED   mutant %-42s DECORATIVO: nao carregou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                res = battery(bad)
            except Exception as exc:                                # noqa: BLE001
                print("  RED   mutant %-42s a bateria rebentou (%s) -- "
                      "NAO foi testado" % (label, type(exc).__name__))
                weak += 1
                continue
            reds = [name for ok, name, _ in res if not ok]
            if reds:
                print("  GREEN mutant %-42s caught by: %s"
                      % (label, "; ".join(reds[:3])))
                caught += 1
            else:
                print("  RED   mutant %-42s SURVIVED -- the gate is blind here"
                      % label)
        # The microphone module has its own source and its own battery; a
        # mutant that is never run proves nothing, so it is not counted.
        for idx, (label, old, new) in enumerate(MIC_MUTANTS):
            if old not in mic_source:
                print("  RED   mutant %-42s ANCHOR MISSING -- oracle is stale"
                      % label)
                weak += 1
                continue
            path = os.path.join(tmp, "mic_mutant_%d.py" % idx)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(mic_source.replace(old, new, 1))
            try:
                bad = load_module(path, "mic_tap_mut_%d" % idx)
            except Exception as exc:                                # noqa: BLE001
                print("  RED   mutant %-42s DECORATIVO: nao carregou (%s)"
                      % (label, type(exc).__name__))
                weak += 1
                continue
            try:
                res = mic_battery(bad)
            except Exception as exc:                                # noqa: BLE001
                print("  RED   mutant %-42s a bateria rebentou (%s)"
                      % (label, type(exc).__name__))
                weak += 1
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

    total = len(MUTANTS) + len(MIC_MUTANTS)
    ok = (not heavy) and green == len(rows) and caught == total and weak == 0
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", green, len(rows), caught, total))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao carregaram, logo nao provaram "
              "nada. Um braco negativo que promete %d e testa %d nao cumpre -- "
              "reescreve o mutante para ser COMPORTAMENTAL."
              % (weak, total, caught))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
