"""BlankFramesRootCause — is the live signal SPEECH buried under LF rumble, or
is it simply not speech at all?

Two measurements:
  1. envelope modulation spectrum (speech: ~4 Hz syllabic peak; music/ambient: beat)
  2. a high-passed copy of the captured live audio, written out for the worker
"""
import sys

import numpy as np
import soundfile as sf

SRC = r"H:\sotto\_main\bfrc_live_capture.wav"
x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
print(f"{SRC}: n={len(x)} sr={sr} peak={abs(x).max():.5f} mean={x.mean():+.6f}")

# ── 1. DC and sub-100 Hz content, measured directly ─────────────────────────
print(f"DC offset (mean)      = {x.mean():+.6f}")
# leaky-integrate to look at the sub-20 Hz trend
k = int(sr * 0.01)
trend = np.convolve(x, np.ones(k, dtype=np.float64) / k, mode="valid")[::k]
print(f"trend(10ms avg) std   = {trend.std():.6f}  (a real rumble shows here)")

# ── 2. envelope modulation spectrum ─────────────────────────────────────────
W = int(sr * 0.02)  # 20 ms frames
nf = len(x) // W
env = np.sqrt((x[: nf * W].reshape(nf, W).astype(np.float64) ** 2).mean(axis=1))
env = env - env.mean()
E = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
efr = np.fft.rfftfreq(len(env), 0.02)
tot = E[efr > 0.3].sum()
print("envelope modulation (Hz -> % of 0.3-25 Hz energy):")
for a, b in [(0.3, 2), (2, 4), (4, 6), (6, 8), (8, 12), (12, 25)]:
    print(f"   {a:>4}-{b:<4} Hz : {100*E[(efr>=a)&(efr<b)].sum()/tot:5.1f}%")

# ── 3. high-passed copy (100 Hz, 2nd order, zero-phase) ─────────────────────
def highpass(sig, sr, f0, order=2):
    # simple Butterworth via bilinear transform, applied forward+backward
    from math import tan, pi
    w = tan(pi * f0 / sr)
    k1 = np.sqrt(2) * w
    k2 = w * w
    a0 = 1 + k1 + k2
    b = [(1 + k1 + k2) / a0, -2 * (1 - k2) / a0, (1 - k1 + k2) / a0]
    a = [1.0, 2 * (k2 - 1) / a0, (1 - k1 + k2) / a0]
    y = sig.astype(np.float64)
    for _ in range(order):
        y = _filtfilt(b, a, y)
    return y.astype(np.float32)

def _filtfilt(b, a, x):
    from scipy.signal import filtfilt  # noqa
    return filtfilt(b, a, x)

try:
    hp = highpass(x, sr, 120.0)
    sf.write(r"H:\sotto\_main\bfrc_live_highpass.wav", hp, sr, subtype="FLOAT")
    print(f"highpass 120 Hz -> _main/bfrc_live_highpass.wav peak={abs(hp).max():.5f} "
          f"rms={np.sqrt((hp.astype('float64')**2).mean()):.6f}")
except Exception as exc:
    print("highpass unavailable:", exc)

# ── 4. same analysis on the KNOWN-SPEECH playback capture, for contrast ─────
xp, srp = sf.read(r"H:\sotto\_main\bfrc_played_capture.wav", dtype="float32")
if xp.ndim > 1:
    xp = xp.mean(axis=1)
nf = len(xp) // W
envp = np.sqrt((xp[: nf * W].reshape(nf, W).astype(np.float64) ** 2).mean(axis=1))
envp = envp - envp.mean()
Ep = np.abs(np.fft.rfft(envp * np.hanning(len(envp)))) ** 2
totp = Ep[efr > 0.3].sum()
print("\nplayed-capture (KNOWN speech), same bands:")
for a, b in [(0.3, 2), (2, 4), (4, 6), (6, 8), (8, 12), (12, 25)]:
    print(f"   {a:>4}-{b:<4} Hz : {100*Ep[(efr>=a)&(efr<b)].sum()/totp:5.1f}%")
