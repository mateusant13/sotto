"""Play one audio file to the DEFAULT render endpoint for N seconds.

Used by lane SottoSpeechSeparation's LIVE proof: the worker captures the WASAPI
loopback of the default render endpoint, so whatever this plays is what the
worker hears. No window, no device name assumed -- `sd.play` uses the default.

  python gate_play.py <file> <seconds> [gain]
"""
import sys
import time

import numpy as np
import soundfile as sf
import sounddevice as sd

path = sys.argv[1]
seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
gain = float(sys.argv[3]) if len(sys.argv) > 3 else 0.6

x, sr = sf.read(path, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
x = (x * gain).astype(np.float32)
print(f"PLAY {path} gain={gain} sr={sr} dur={len(x)/sr:.2f}s peak={abs(x).max():.4f} for {seconds}s", flush=True)
t0 = time.time()
while time.time() - t0 < seconds:
    sd.play(x, sr, blocking=True)
print("PLAY done", flush=True)
