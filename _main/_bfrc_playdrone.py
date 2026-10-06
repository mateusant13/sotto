"""Play a known NON-speech signal into the default render endpoint for N seconds.

Used only to make the loopback tap provably ALIVE while carrying no speech, so the
`captured-signal-has-no-speech` verdict can be exercised deterministically.
"""
import sys
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

PATH = r"H:\sotto\_main\bfrc_live_capture2.wav"   # the real captured drone
GAIN = 0.35
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0

x, sr = sf.read(PATH, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
x = (x * GAIN).astype(np.float32)
print(f"playing {PATH} gain={GAIN} peak={abs(x).max():.4f} for {SECONDS}s", flush=True)
t0 = time.time()
while time.time() - t0 < SECONDS:
    sd.play(x, sr, blocking=True)
print("playback done", flush=True)
