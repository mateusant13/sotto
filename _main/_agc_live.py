"""SottoAutoGain — LIVE acceptance: does a QUIET source now transcribe?

Plays the pt-br speech clip through the DEFAULT RENDER endpoint at a PLAYED PEAK
of ~0.100 (the brief's quiet source; Main measured the same peak on the file arm
and got blank_frac=1.0000, ZERO captions), while the SHIPPED worker captures the
loopback live, twice:

  quiet_agc  : SOTTO_AGC=1 (the cure)   -> must emit a NON-EMPTY caption
  quiet_nogc : SOTTO_AGC=0 (the control) -> must emit no caption

Same source, same device, same code path; the ONLY variable is the gain stage.
The tap is UNITY-faithful (calibration: tap_peak == played_peak), so the played
peak IS the tap peak when nothing else is on the endpoint. Each arm's own
`peak=` in WORKER_STATS is the reported pre-gain measured peak.

No window: pythonw + CREATE_NO_WINDOW for the child.
"""
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = r"H:\sotto"
PYW = r"C:\Program Files\Python311\pythonw.exe"
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
CFG = os.path.join(ROOT, "worker", "config.json")
SRC = os.path.join(ROOT, "_main", "pt-br-sample.wav")
TARGET_PLAYED_PEAK = 0.1005      # the brief's quiet source (~-20 dBFS peak)
CREATE_NO_WINDOW = 0x08000000
SECONDS = 20

x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
orig_peak = float(np.abs(x).max())
g = TARGET_PLAYED_PEAK / orig_peak
clip = (x * g).astype(np.float32)
print(
    f"play {SRC} sr={sr} n={len(clip)} orig_peak={orig_peak:.6f} "
    f"total_gain={g:.5f} ({20*np.log10(g):+.1f} dBFS) played_peak={abs(clip).max():.6f}"
)

stop = threading.Event()


def play_loop():
    while not stop.is_set():
        try:
            sd.play(clip, sr, blocking=True)
        except Exception as exc:  # noqa: BLE001
            print("play error:", exc)
            return


th = threading.Thread(target=play_loop, daemon=True)
th.start()
time.sleep(0.8)


def summarise(path):
    caps, done = [], None
    for ln in open(path, encoding="utf-8"):
        ln = ln.strip()
        if not ln.startswith("{"):
            continue
        try:
            o = json.loads(ln)
        except Exception:  # noqa: BLE001
            continue
        if o.get("type") == "caption":
            caps.append(o.get("text"))
        if o.get("state") == "done":
            done = o
    keys = ("verdict", "captions", "peak", "peak_out", "gain_db", "gain_max_db",
            "agc", "queue_drops", "blank_frac", "audio_s", "resampled_samples")
    return caps, {k: done[k] for k in keys if done and k in done}


def run(arm, agc_on):
    out = open(os.path.join(ROOT, "_main", f"agc_{arm}.jsonl"), "w", encoding="utf-8")
    errf = open(os.path.join(ROOT, "_main", f"agc_{arm}.err"), "w", encoding="utf-8")
    env = os.environ.copy()
    env.pop("SOTTO_AUDIO_FILE", None)
    env["SOTTO_AGC"] = "1" if agc_on else "0"
    argv = [PYW, WORKER, "--config", CFG, "--stats-interval", "5", "--max-seconds", str(SECONDS)]
    t0 = time.time()
    p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=errf,
                         creationflags=CREATE_NO_WINDOW)
    try:
        rc = p.wait(timeout=180)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "TIMEOUT"
    out.close()
    errf.close()
    caps, done = summarise(os.path.join(ROOT, "_main", f"agc_{arm}.jsonl"))
    print(f"ARM {arm} agc={agc_on} rc={rc} wall={time.time()-t0:.1f}s "
          f"captions={len(caps)} {caps}")
    print(f"     done={json.dumps(done)}")


only = sys.argv[1] if len(sys.argv) > 1 else None
for arm, agc_on in (("quiet_agc", True), ("quiet_nogc", False)):
    if only and only != arm:
        continue
    run(arm, agc_on)

stop.set()
try:
    sd.stop()
except Exception:  # noqa: BLE001
    pass
print("DONE")
