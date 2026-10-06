"""BlankFramesDecisive ARM B -- the failing case, done PROPERLY.

The failing live runs (bfrc_b_live) were captured with no controlled source, so
"live path broken" and "nothing decodable was playing" are indistinguishable.
This plays the KNOWN speech clip (pt-br-sample.wav) through the DEFAULT RENDER
endpoint at normal volume while the shipped worker captures the loopback live.
No window: pythonw + CREATE_NO_WINDOW for the child.
"""
import os
import subprocess
import threading
import time

import numpy as np
import soundfile as sf
import sounddevice as sd

ROOT = r"H:\sotto"
PYW = r"C:\Program Files\Python311\pythonw.exe"
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
CFG = os.path.join(ROOT, "worker", "config.json")
SRC = os.path.join(ROOT, "_main", "pt-br-sample.wav")
GAIN = 0.30
CREATE_NO_WINDOW = 0x08000000

x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
clip = (x * GAIN).astype(np.float32)
print(f"play {SRC} sr={sr} n={len(clip)} gain={GAIN} peak={abs(clip).max():.4f}")

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

out = open(os.path.join(ROOT, "_main", "bfrc_head.jsonl"), "w", encoding="utf-8")
errf = open(os.path.join(ROOT, "_main", "bfrc_head.err"), "w", encoding="utf-8")
env = os.environ.copy()
env.pop("SOTTO_AUDIO_FILE", None)
argv = [PYW, WORKER, "--config", CFG, "--stats-interval", "5", "--max-seconds", "25"]
t0 = time.time()
p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=errf,
                     creationflags=CREATE_NO_WINDOW)
try:
    rc = p.wait(timeout=180)
except subprocess.TimeoutExpired:
    p.kill()
    rc = "TIMEOUT"
stop.set()
try:
    sd.stop()
except Exception:
    pass
out.close()
errf.close()
print(f"ARM B rc={rc} wall={time.time()-t0:.1f}s")
