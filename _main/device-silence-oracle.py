"""ORACLE for the device/silence contract. One command, real exit codes, both colours.

THREE arms, and the two failure arms are DIFFERENT FACTS, not two spellings of one:

  ARM 1 — ZERO CALLBACK BLOCKS (must FAIL LOUD).
    The owner names an endpoint that OPENS and delivers not one callback block.
    This is the shape measured on this box (2026-11-01) on
    `Mixagem estereo (Realtek HD Audio Stereo input)`: `LoopbackTap` opens it,
    the stream starts, and `on_block` is never called (measured here: 0 blocks in
    4 s, beside 39 blocks on the cable). The run used to end with verdict
    `no-callback-blocks` and **exit 0** — the single word every caller treats as
    success, for a run that received no audio at all. It now exits 3, which is
    this worker's established "started and got nothing" (2 = never started).

  ARM 2 — SILENCE (must FAIL LOUD, and this arm is NOT to be changed).
    A candidate OPENS, runs a real window (>= TAP_SILENT_BLOCKS callbacks) and
    measures digital silence under the peak floor. The run must say
    `silent-device`, name the device, its host API, its measured peak and the
    floor, and exit 3. Measured live before this file existed; it stays here so
    a regression that stops naming the DEVICE cannot pass as the new word.

  ARM 3 — ROUTED SPEECH (must SUCCEED).
    Speech is rendered into the virtual cable and the real, unmodified worker
    captures it. exit 0, `captions-emitted`, captions > 0, and the device is the
    CABLE. Without this arm the oracle could pass by failing everything.

THE SHELL IS MEASURED, NOT ASSUMED. For each failure arm the SHIPPED
`app/webview/sotto_webview.py` is imported and asked what it paints: a `done`
carrying this verdict must be `no-audio` (not `error`, and never `busy`), and
the footer must name the verdict. That is the third party to this contract —
worker, oracle and shell — and it is checked, not promised.

WHY EACH ARM READS THE SHAPE IT READS (measured 2026-11-01, this box):
  * `Mixagem estereo (Realtek HD Audio Stereo input)` -> 0 blocks, peak 0.0.
  * `CABLE Output (VB-Audio Virtual Cable)` and `VoiceMeeter Output` -> 39
    blocks in 4 s, peak 0.000031/0.000092, i.e. FLOWING and SILENT. Either is a
    silent-device subject; this file uses VoiceMeeter because the positive arm
    renders into the CABLE, so no arm of this oracle can wake the other's
    device.

Usage:
    py -3 _main/device-silence-oracle.py [seconds]          # all three arms
    py -3 _main/device-silence-oracle.py --neg-arm [seconds]
        builds the PRE-FIX worker (the old exit mapping) as a COPY, runs ARM 1
        against it, and requires the defect to come back (exit 0). rc=1.
Exit 0 = every arm behaved. Exit 1 = at least one arm misbehaved (or the
control reproduced the defect, for `--neg-arm`). Exit 2 = setup error.
"""

from __future__ import annotations

# BATTERY-HEAVY: audio-device -- este instrumento ABRE o dispositivo de audio do
# dono (loopback + render no cabo) e carrega as pesos do modelo num worker REAL
# tres vezes; a classe pesada da bateria so' corre com opt-in
# (SOTTO_BATTERY_HEAVY=1). A classificacao e' a do mapa STEP_KINDS de
# `_main/battery-heavy-gate.py`; faltava so' a declaracao neste ficheiro.

import json
import math
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.normpath(os.path.join(ROOT, "worker", "sotto_worker.py"))
SHELL_DIR = os.path.join(ROOT, "app", "webview")
RUNS = os.path.normpath(os.path.join(ROOT, "worker", "runs"))
SAMPLE = os.path.normpath(os.path.join(ROOT, "worker", "assets", "sample1.flac"))

CREATE_NO_WINDOW = 0x08000000
RENDER = "CABLE Input"
CABLE = "CABLE Output (VB-Audio Virtual Cable)"

#: ARM 1's subject: measured HERE, 2026-11-01 -- opens, zero callbacks in 4 s.
ZERO_BLOCK_DEVICE = "Mixagem estéreo (Realtek HD Audio Stereo input)"
#: ARM 2's subject: measured HERE, 2026-11-01 -- 39 blocks in 4 s, peak 9.2e-5
#: (floor is 0.002), and nothing in this repo renders into it: the positive arm
#: of THIS file renders into `CABLE Input`, so the two arms cannot wake each
#: other's device.
SILENT_DEVICE = "VoiceMeeter Output"

#: The line ARM 1 is about, and the pre-fix form the control has to restore.
FIXED_RETURN = '    return 3 if (ran_but_silent or counters["blocks"] == 0) else 0'
PRE_FIX_RETURN = '    return 3 if ran_but_silent else 0'
#: The control's copy LIVES IN `worker/` because the worker imports its own
#: siblings off `sys.path[0] = HERE`; a copy anywhere else cannot start.
NEG_COPY = "_neg-device-silence-worker.py"


def say(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def run_worker(out_path: str, args: list[str], worker: str = WORKER) -> dict:
    out = open(out_path, "wb")
    errf = open(out_path + ".err", "wb")
    proc = subprocess.Popen(
        [sys.executable, worker, *args],
        stdout=out, stderr=errf, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW, cwd=os.path.dirname(WORKER),
    )
    try:
        rc = proc.wait(timeout=400)
    except subprocess.TimeoutExpired:
        # ROW #34 (windows-landmines.md): a bare `wait(timeout=)` leaves the CHILD and
        # its whole TREE alive when the ceiling expires -- measured live by
        # `_main/audit-rows-landmine-child-control.py` (arm r34). `/T` kills the tree, and the
        # target is a PID, never a NAME, so no kill filter can reach an unrelated process.
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)
        raise
    out.close()
    errf.close()
    statuses, captions = [], []
    with open(out_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "caption":
                captions.append(o.get("text", ""))
            else:
                statuses.append(o)
    done = next((o for o in statuses if o.get("state") == "done"), {})
    silent = next((o for o in statuses if o.get("state") == "silent-device"), None)
    return {"rc": rc, "done": done, "silent": silent, "statuses": statuses,
            "captions": captions,
            "text": " ".join(c.strip() for c in captions if c.strip())}


def shell_paint(verdict: str, state: str = "done") -> tuple[str, str]:
    """What the SHIPPED shell paints for this `done`/status. Imported, never copied.

    `worker_status_kind` decides the colour and `worker_status_text` the footer
    sentence; both live in `app/webview/sotto_webview.py` and are the shell's own
    answer about the worker's own word. Importing the module starts nothing (its
    `main()` is behind `__main__`).
    """
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    import sotto_webview as shell_mod

    message = {"verdict": verdict} if state == "done" else {"verdict": state}
    return (shell_mod.worker_status_kind(state, message),
            shell_mod.worker_status_text(state, message, "Worker finished"))


def ledger(res: dict) -> list[dict]:
    rows = res.get("done", {}).get("tap_ledger") or []
    return [r for r in rows if isinstance(r, dict)]


def opened_with_blocks(res: dict, device: str) -> list[dict]:
    """The ledger rows for candidates that OPENED (rung/device match, any blocks)."""
    rows = ledger(res)
    return [r for r in rows
            if device.split("(")[0].strip().lower() in str(r.get("device", "")).lower()
            or device.lower() in str(r.get("device", "")).lower()]


def load_audio(path: str, rate: int):
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1).astype(np.float32)
    if sr != rate:
        n = int(len(mono) * rate / sr)
        mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono).astype(np.float32)
    return mono


def feed_cable(stop: threading.Event, rate: int = 44100) -> None:
    try:
        audio = load_audio(SAMPLE, rate)
    except Exception:
        return
    dev = next((d for d in sd.query_devices()
                if d["max_output_channels"] > 0 and RENDER.lower() in d["name"].lower()), None)
    if dev is None:
        return
    st = sd.OutputStream(device=dev["index"], channels=1, samplerate=rate, dtype="float32")
    st.start()
    pos = 0
    chunk = int(rate * 0.1)
    try:
        while not stop.is_set():
            if pos + chunk > len(audio):
                pos = 0
            st.write((0.6 * audio[pos:pos + chunk]).reshape(-1, 1))
            pos += chunk
    finally:
        st.stop()
        st.close()


def arm_zero_blocks(secs: str, worker: str = WORKER, out: str = "oracle-zero.jsonl") -> dict:
    """ARM 1: an endpoint that opens and delivers NOT ONE callback block."""
    a = run_worker(os.path.join(RUNS, out),
                   ["--max-seconds", secs, "--device", ZERO_BLOCK_DEVICE],
                   worker=worker)
    failures: list[str] = []
    verdict = a["done"].get("verdict")
    rows = opened_with_blocks(a, ZERO_BLOCK_DEVICE)
    if a["rc"] == 0:
        failures.append("exit code was 0; a run that received NO audio at all must not be "
                        "success (this is the defect the arm exists for)")
    if a["rc"] != 3:
        failures.append(f"expected exit 3 ('started and got nothing'), got {a['rc']}")
    if verdict != "no-callback-blocks":
        failures.append(f"verdict was {verdict!r}, expected 'no-callback-blocks'")
    if a["captions"]:
        failures.append(f"{len(a['captions'])} caption(s) came out of a device that delivered "
                        f"no blocks -- the measurement is not about the device it names")
    if not rows:
        failures.append(f"no tap_ledger row names {ZERO_BLOCK_DEVICE!r}; the run did not say "
                        f"WHICH endpoint delivered nothing (ledger={ledger(a)})")
    else:
        flowing = [r for r in rows if (r.get("blocks") or 0) != 0]
        if flowing:
            failures.append(f"{ZERO_BLOCK_DEVICE!r} delivered blocks in this run "
                            f"({[(r.get('device'), r.get('blocks')) for r in flowing]}); "
                            f"the arm measured a silent device, not a zero-block one")
    kind, footer = shell_paint("no-callback-blocks")
    if kind != "no-audio":
        failures.append(f"the SHELL paints a 'no-callback-blocks' done as {kind!r}, not "
                        f"'no-audio' -- worker and shell disagree about the word")
    if "no-callback-blocks" not in footer:
        failures.append(f"the SHELL footer does not name the verdict ({footer!r})")
    return {"arm": "1-zero-blocks-must-fail-loud", "rc": a["rc"], "verdict": verdict,
            "captions": len(a["captions"]),
            "ledger": [{k: r.get(k) for k in ("device", "rung", "blocks", "peak")}
                       for r in ledger(a)],
            "shell_kind": kind, "shell_footer": footer, "failures": failures}


def arm_silence(secs: str, out: str = "oracle-silent.jsonl") -> dict:
    """ARM 2: a window of callbacks that measure digital silence."""
    a = run_worker(os.path.join(RUNS, out),
                   ["--max-seconds", secs, "--device", SILENT_DEVICE])
    failures: list[str] = []
    s = a["silent"]
    verdict = a["done"].get("verdict")
    if a["rc"] != 3:
        failures.append(f"expected exit 3 (silent device), got {a['rc']}")
    if verdict != "silent-device":
        failures.append(f"verdict was {verdict!r}, expected 'silent-device'")
    if s is None:
        failures.append("no state='silent-device' status naming the device")
    else:
        if not (s.get("device") and s.get("peak") is not None):
            failures.append(f"silent-device status does not name device+peak: {s}")
        if (s.get("blocks") or 0) < 20:
            failures.append(f"silent verdict fired on only {s.get('blocks')} blocks; not a "
                            f"real window")
        if s.get("peak") is not None and s.get("peak_floor") is not None \
                and s["peak"] >= s["peak_floor"]:
            # NOT a silent device: something was RENDERED into this endpoint
            # during the window (another lane, the owner, a test tone). The arm
            # did not measure silence, and saying so is the only honest answer.
            failures.append(f"{SILENT_DEVICE!r} carried SIGNAL during the window "
                            f"(peak {s['peak']} >= floor {s['peak_floor']}): something is "
                            f"rendering into it, so this arm measured nothing")
    kind, footer = shell_paint("silent-device")
    if kind != "no-audio":
        failures.append(f"the SHELL paints 'silent-device' as {kind!r}, not 'no-audio'")
    return {"arm": "2-silence-must-fail-loud", "rc": a["rc"], "verdict": verdict,
            "captions": len(a["captions"]),
            "device": (s or {}).get("device"), "api": (s or {}).get("api"),
            "peak": (s or {}).get("peak"), "peak_floor": (s or {}).get("peak_floor"),
            "blocks": (s or {}).get("blocks"),
            "shell_kind": kind, "shell_footer": footer, "failures": failures}


def load_seconds(res: dict) -> float | None:
    """How long the run's OWN model load took, from the run's own record."""
    for o in res.get("statuses", []):
        v = o.get("load_s") if o.get("state") == "model-loaded" else None
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


def arm_routed(secs: str) -> dict:
    """ARM 3: speech rendered into the cable must be transcribed, exit 0.

    THE WINDOW MUST COVER THE LOAD, AND THE LOAD IS MEASURED, NOT ASSUMED
    (measured 2026-11-02). `--max-seconds` is WALL time from process start
    (`sotto_worker.py` starts the clock before the model is loaded,
    `t_start = time.time()` at the top of `main`). On this box the live model
    costs `load_s=38.96` s cold, so a 20 s window is consumed ENTIRELY by the
    load: the run reported `blocks=56 peak=0.275 speech_blocks=6 captions=0` --
    speech really was captured and transcribed into nothing, because the window
    closed before a decode could land. That is an INSTRUMENT budget, not a
    product defect, and the two must never be confused in either direction:
    the arm retries ONCE with `load_s + max(secs, 20) + 10` seconds, and ONLY
    when the run's own record proves the load ate the whole window (captions=0,
    blocks>0, load_s >= window). Every other shape is judged as it lands, so a
    real regression still goes RED.
    """
    stop = threading.Event()
    t = threading.Thread(target=feed_cable, args=(stop,), daemon=True)
    t.start()
    time.sleep(1.5)
    a = run_worker(os.path.join(RUNS, "oracle-pos.jsonl"),
                   ["--max-seconds", secs, "--device", CABLE])
    load_s = load_seconds(a)
    retried = None
    if (not a["captions"] and (a["done"].get("blocks") or 0) > 0
            and load_s is not None and load_s >= float(secs)):
        window = int(math.ceil(load_s)) + max(int(float(secs)), 20) + 10
        stop.set()
        t.join(timeout=5)
        retried = {"why": "the run's own load_s ate the whole window",
                   "load_s": load_s, "window_s": window}
        stop = threading.Event()
        t = threading.Thread(target=feed_cable, args=(stop,), daemon=True)
        t.start()
        time.sleep(1.5)
        a = run_worker(os.path.join(RUNS, "oracle-pos.jsonl"),
                       ["--max-seconds", str(window), "--device", CABLE])
    stop.set()
    t.join(timeout=5)
    failures: list[str] = []
    if a["rc"] != 0:
        failures.append(f"expected exit 0 (captions emitted), got {a['rc']}")
    if a["done"].get("verdict") != "captions-emitted":
        failures.append(f"verdict was {a['done'].get('verdict')!r}, expected "
                        f"'captions-emitted'")
    if len(a["captions"]) == 0:
        failures.append("0 captions with audio routed into the cable")
    if CABLE not in str(a["done"].get("device", "")):
        failures.append(f"settled on {a['done'].get('device')!r}, expected the CABLE")
    if not a["done"].get("proved_alive"):
        failures.append("done record does not carry proved_alive=true")
    kind, _footer = shell_paint("captions-emitted")
    if kind not in ("busy", "done", "ok"):
        failures.append(f"the SHELL paints 'captions-emitted' as {kind!r} -- a healthy finish "
                        f"must not be painted as a fault")
    return {"arm": "3-routed-must-succeed", "rc": a["rc"],
            "verdict": a["done"].get("verdict"), "captions": len(a["captions"]),
            "device": a["done"].get("device"), "peak": a["done"].get("peak"),
            "proved_alive": a["done"].get("proved_alive"),
            "rotations": a["done"].get("rotations"), "load_s": load_s,
            "retry": retried,
            "shell_kind": kind,
            "caption_words": a["text"][:180], "failures": failures}


def main(argv: list[str]) -> int:
    args = [a for a in argv if a != "--neg-arm"]
    neg = "--neg-arm" in argv
    secs = args[0] if args else "20"
    os.makedirs(RUNS, exist_ok=True)

    # O AUDIO DO DONO NAO SE TOCA (ordem 2026-11-02): este oraculo RENDERIZA e
    # abre endpoint. Sem a bandeira dele nao corre -- e diz SKIPPED, nunca GREEN.
    if str(os.environ.get("SOTTO_OWNER_AUDIO_OK") or "").strip() != "1":
        print("DEVICE-SILENCE VERDICT: SKIPPED")
        print("recusa: audio do dono (device-silence nao corre sem "
              "SOTTO_OWNER_AUDIO_OK=1)")
        print("\nVERDICT: SKIPPED")
        return 0

    if neg:
        return neg_arm(secs)

    failures: list[str] = []
    # ── ARM 1 ────────────────────────────────────────────────────────────
    one = arm_zero_blocks(secs)
    say(one)
    failures += [f"ARM1 {f}" for f in one["failures"]]
    # ── ARM 2 ─────────────────────────────────────────────────────────────
    # MEASURED: running two arms back to back makes the second die at
    # "model-loading" with an EMPTY stderr and exit 4294967295 -- the first
    # process has exited but its ~2.4 GB working set is still being torn down
    # while the next maps ~1 GB of weights on top. It is a gap, not a retry: a
    # retry would let a genuine memory failure pass.
    time.sleep(20)
    two = arm_silence(secs)
    say(two)
    failures += [f"ARM2 {f}" for f in two["failures"]]
    # ── ARM 3 ─────────────────────────────────────────────────────────────
    time.sleep(20)
    three = arm_routed(secs)
    say(three)
    failures += [f"ARM3 {f}" for f in three["failures"]]

    say({"oracle": "device-silence",
         "verdict": "PASS" if not failures else "FAIL",
         "failures": failures})
    # A plain line, because the battery's skip-capable accounting greps TEXT and
    # not the JSON: the same shape the mute oracle already prints.
    print("DEVICE-SILENCE VERDICT: %s" % ("PASS" if not failures else "FAIL"))
    return 1 if failures else 0


def neg_arm(secs: str) -> int:
    """The CONTROL: restore the pre-fix exit mapping and require the defect back.

    A control that has stopped being a control is REFUSED, never run: the copy is
    built only from the one line this file is about, exactly once.
    """
    try:
        with open(WORKER, encoding="utf-8") as f:
            src = f.read()
    except OSError as exc:
        print(f"NEG-ARM SETUP: cannot read the worker: {exc!r}")
        return 2
    if src.count(FIXED_RETURN) != 1:
        print(f"NEG-ARM REFUSED: the line this control reverts is not in the worker "
              f"exactly once ({src.count(FIXED_RETURN)}), so the copy would not be the "
              f"pre-fix worker: {FIXED_RETURN!r}")
        return 2
    copy_path = os.path.join(os.path.dirname(WORKER), NEG_COPY)
    try:
        with open(copy_path, "w", encoding="utf-8", newline="") as f:
            f.write(src.replace(FIXED_RETURN, PRE_FIX_RETURN))
        a = run_worker(os.path.join(RUNS, "oracle-neg-arm.jsonl"),
                       ["--max-seconds", secs, "--device", ZERO_BLOCK_DEVICE],
                       worker=copy_path)
    finally:
        try:
            os.remove(copy_path)
        except OSError:
            pass
    removed = not os.path.exists(copy_path)
    verdict = a["done"].get("verdict")
    reproduced = a["rc"] == 0 and verdict == "no-callback-blocks"
    say({"neg_arm": "pre-fix-worker", "rc": a["rc"], "verdict": verdict,
         "copy_removed": removed,
         "reproduced": reproduced,
         "note": "the defect is exit 0 for a run that received no audio at all"})
    print("NEG-ARM PASS -- the pre-fix worker exits 0 for a device that delivered no "
          "blocks; ARM 1 catches exactly that" if reproduced else
          "NEG-ARM FAIL -- the pre-fix copy did NOT reproduce the defect "
          f"(rc={a['rc']}, verdict={verdict!r}); this control is not controlling anything",
          flush=True)
    print(f"NEG-ARM CLEANUP copy_removed={removed}", flush=True)
    # rc=1 POR DESENHO no braco negativo (a convencao de `--neg-arm` desta casa).
    return 1 if reproduced and removed else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
