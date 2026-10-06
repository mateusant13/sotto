"""Prove `captured-signal-has-no-speech` deterministically.

Play a KNOWN NON-SPEECH signal out of the default output, run the real worker live
at the same time, and read back the verdict. Playback is done exactly the way the
successful play-and-capture experiment did it (sounddevice in this process), which
is the only configuration measured to land in the endpoint the loopback tap reads.
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
CREATE_NO_WINDOW = 0x08000000

x, sr = sf.read(r"H:\sotto\_main\bfrc_live_capture2.wav", dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
x = (x * 0.35).astype(np.float32)
print(f"drone: n={len(x)} sr={sr} peak={abs(x).max():.4f}", flush=True)

stop = threading.Event()


def player():
    t0 = time.time()
    while not stop.is_set() and time.time() - t0 < 60:
        sd.play(x, sr, blocking=True)


t = threading.Thread(target=player, daemon=True)
t.start()
time.sleep(2.0)

out = open(os.path.join(ROOT, "_main", "bfrc_proof2.jsonl"), "w", encoding="utf-8")
errf = open(os.path.join(ROOT, "_main", "bfrc_proof2.err"), "w", encoding="utf-8")
argv = [PYW, os.path.join(ROOT, "worker", "sotto_worker.py"),
        "--config", os.path.join(ROOT, "worker", "config.json"),
        "--stats-interval", "60", "--max-seconds", "18"]
p = subprocess.Popen(argv, cwd=ROOT, stdout=out, stderr=errf, creationflags=CREATE_NO_WINDOW)
rc = p.wait(timeout=180)
stop.set()
time.sleep(0.5)
out.close()
errf.close()
print("worker rc =", rc, flush=True)

for ln in open(os.path.join(ROOT, "_main", "bfrc_proof2.jsonl"), encoding="utf-8"):
    ln = ln.strip()
    if not ln:
        continue
    o = json.loads(ln)
    if o.get("type") != "status":
        continue
    if o.get("state") in ("capture-started", "device-rotated", "no-speech-in-capture", "done", "silent-device"):
        keep = ("verdict", "peak", "chunks", "vad_gated_chunks", "frames", "blank_frac",
                "captions", "device", "detail")
        print(o.get("state"), json.dumps({k: o[k] for k in keep if k in o}, ensure_ascii=False), flush=True)
