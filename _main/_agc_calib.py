"""SottoAutoGain — calibrate the PLAYED level that makes the loopback tap read ~0.10.

No model, ~8 s: play the pt-br clip at a trial gain and capture it with the SAME
WasapiLoopbackTap the live run uses; print captured peak/rms so the live driver
can be tuned to the MEASURED quiet case (tap peak ~0.10). No window: pythonw.
"""
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

sys.path.insert(0, r"H:\sotto\worker")
import wasapi_loopback  # noqa: E402

SRC = r"H:\sotto\_main\pt-br-sample.wav"
GAINS = [float(a) for a in sys.argv[1:]] or [0.04755]

x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)

blocks: list = []
tap = wasapi_loopback.WasapiLoopbackTap(lambda b: blocks.append(np.array(b, dtype=np.float32)),
                                        block_ms=100)
print(f"tap rate={tap.rate} block={tap.block}")
with tap:
    for g in GAINS:
        blocks.clear()
        clip = (x * g).astype(np.float32)
        time.sleep(0.4)
        sd.play(clip, sr, blocking=True)
        time.sleep(0.4)
        fs = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
        if fs.ndim > 1:
            fs = fs.mean(axis=1)
        pk = float(np.abs(fs).max()) if fs.size else 0.0
        rms = float(np.sqrt(np.mean(fs.astype("float64") ** 2))) if fs.size else 0.0
        print(f"CALIB total_gain={g} played_peak={abs(clip).max():.6f} "
              f"tap_peak={pk:.6f} tap_rms={rms:.8f} samples={fs.size}")
