"""Arm D — the end-to-end live control, re-run against the CURRENT worker (AGC on).

Play a KNOWN speech clip out of the default output while the real worker captures
the default render endpoint. If captions come back, the whole live path (tap ->
resample -> AGC -> chunk -> model -> emit) is proven; if they do not, the live path
is the defect. This is the control that makes the "no speech in the capture" verdict
falsifiable rather than an alibi.
"""
import json
import os
import subprocess
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

ROOT = r"H:\sotto"
PYW = r"C:\Program Files\Python311\pythonw.exe"
CREATE_NO_WINDOW = 0x08000000

x, sr = sf.read(r"H:\sotto\_main\pt-br-sample.wav", dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
if sr != 48000:
    n = int(len(x) * 48000 / sr)
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    sr = 48000
x = (x * 0.25).astype(np.float32)
print(f"speech: n={len(x)} sr={sr} peak={abs(x).max():.4f} ({len(x)/sr:.1f}s)", flush=True)

stop = threading.Event()


def player():
    t0 = time.time()
    while not stop.is_set() and time.time() - t0 < 60:
        sd.play(x, sr, blocking=True)


threading.Thread(target=player, daemon=True).start()
time.sleep(2.0)

out = open(os.path.join(ROOT, "_main", "bfrc_armd.jsonl"), "w", encoding="utf-8")
errf = open(os.path.join(ROOT, "_main", "bfrc_armd.err"), "w", encoding="utf-8")
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
caps = []
for ln in open(os.path.join(ROOT, "_main", "bfrc_armd.jsonl"), encoding="utf-8"):
    ln = ln.strip()
    if not ln:
        continue
    o = json.loads(ln)
    if o.get("type") == "caption":
        caps.append(o["text"])
    if o.get("type") == "status" and o.get("state") in ("no-speech-in-capture", "done"):
        keep = ("verdict", "peak", "chunks", "vad_gated_chunks", "frames", "blank_frac", "captions")
        print(o.get("state"), json.dumps({k: o[k] for k in keep if k in o}, ensure_ascii=False), flush=True)
print("CAPTIONS(%d): %r" % (len(caps), " | ".join(caps)), flush=True)
