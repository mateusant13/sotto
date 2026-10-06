"""Build a stationary non-speech IDLE-FLOOR / drone bed at the level the capture
actually carried, for the ORDER's arm (a).

Why synthesized: the real capture fixture (`_main/bfrc_live_capture2.wav`, peak
0.103287, rms -37.6 dBFS) was deleted from `_main/` by a sibling lane mid-run —
measured with `ls` at 2026-10-06T09:20. The real drone can no longer be replayed,
so this reproduces the LEVEL the assignment names ("an idle floor at -37 dBFS")
with a provably stationary bed: three low tones, constant amplitude, no envelope.
The gate's own calibration measured a pure tone at dB-range 1.3 (speech is 20+),
so a gate that keeps this would be broken.
"""
import numpy as np
import soundfile as sf

OUT = r"H:\sotto\_main\agc_drone_floor.wav"
SR = 48000
SECONDS = 20.0
TARGET_DBFS = -37.5          # the measured idle floor the AGC would boost ~+17 dB

t = np.arange(int(SR * SECONDS)) / SR
bed = (1.00 * np.sin(2 * np.pi * 90 * t)
       + 0.60 * np.sin(2 * np.pi * 240 * t)
       + 0.40 * np.sin(2 * np.pi * 620 * t)
       + 0.10 * np.sin(2 * np.pi * 1180 * t))
rms = float(np.sqrt(np.mean(bed ** 2)))
g = (10 ** (TARGET_DBFS / 20.0)) / rms
x = (bed * g).astype(np.float32)
pk = float(np.abs(x).max())
print(f"written {OUT} sr={SR} dur={SECONDS}s rms_dbfs={20*np.log10(np.sqrt(np.mean(x.astype(np.float64)**2))):.2f} peak={pk:.6f} (needs <0.12)")
sf.write(OUT, x, SR)
