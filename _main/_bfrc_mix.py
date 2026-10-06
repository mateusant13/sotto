"""BlankFramesRootCause — the DETECTION FLOOR.

The live endpoint's mix carries a constant low-frequency ambient at peak ~0.098 /
rms ~0.0147. Speech that reaches the model must be recoverable THROUGH that
ambient. This builds mixtures of the known speech clip with the REAL captured
ambient at a range of speech levels and asks the model where it stops captioning.

Deliverable of this run: the level, relative to the ambient, at which Sotto goes
silent -- and whether the ambient level measured on this box is above or below it.
"""
import os

import numpy as np
import soundfile as sf

SR = 48000
sp, _ = sf.read(r"H:\sotto\_main\bfrc_c_48000_full.wav", dtype="float32")   # pt-br-sample @48k
am, _ = sf.read(r"H:\sotto\_main\bfrc_live_capture2.wav", dtype="float32")  # real ambient
if sp.ndim > 1:
    sp = sp.mean(axis=1)
if am.ndim > 1:
    am = am.mean(axis=1)
sp = sp / float(abs(sp).max())          # full-scale reference (peak 1.0)
# tile ambient to cover the clip, take a slice from a quiet-ish region
n = len(sp)
while len(am) < n:
    am = np.concatenate([am, am])
amb = am[:n]
amb = amb * (0.098 / float(abs(amb).max()))
print(f"ambient slice peak={abs(amb).max():.4f} rms={np.sqrt((amb.astype('float64')**2).mean()):.5f}")
print(f"speech full-scale peak=1.0 rms={np.sqrt((sp.astype('float64')**2).mean()):.5f}")

for g in [0.50, 0.25, 0.12, 0.06, 0.03, 0.015]:
    mix = (amb + sp * g).astype(np.float32)
    p = r"H:\sotto\_main\bfrc_mix_%04d.wav" % int(g * 1000)
    sf.write(p, mix, SR, subtype="FLOAT")
    snr = 20 * np.log10(np.sqrt((sp.astype("float64") ** 2).mean()) * g
                        / np.sqrt((amb.astype("float64") ** 2).mean()))
    print(f"  gain={g:<6} speech_rms={np.sqrt((sp.astype('float64')**2).mean())*g:.5f} "
          f"speech/ambient={snr:+6.1f} dB  -> {os.path.basename(p)}")
