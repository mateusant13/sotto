"""BlankFramesRootCause — is the live signal SPEECH buried under LF rumble, or
is it simply not speech at all?

  1. DC / sub-100 Hz trend
  2. envelope modulation spectrum (speech: ~4 Hz syllabic peak)
  3. a high-passed copy of the captured live audio, written out for the worker
numpy only -- no scipy on this box.
"""
import numpy as np
import soundfile as sf

SRC = r"H:\sotto\_main\bfrc_live_capture.wav"
x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
print(f"{SRC}: n={len(x)} sr={sr} peak={abs(x).max():.5f} mean={x.mean():+.6f}")

k = int(sr * 0.01)
trend = np.convolve(x.astype(np.float64), np.ones(k) / k, mode="valid")[::k]
print(f"trend(10ms avg) std   = {trend.std():.6f}   (<- low-frequency wander)")


def highpass_fft(sig, sr, f0):
    """Zero-phase high-pass in the frequency domain -- no recursion to blow up."""
    n = len(sig)
    X = np.fft.rfft(sig.astype(np.float64))
    f = np.fft.rfftfreq(n, 1.0 / sr)
    H = 1.0 / (1.0 + (f0 / np.maximum(f, 1e-9)) ** 4) ** 0.5
    H[f == 0] = 0.0
    return np.fft.irfft(X * H, n=n).astype(np.float32)


W = int(sr * 0.02)


def modspec(sig, label):
    nf = len(sig) // W
    env = np.sqrt((sig[: nf * W].reshape(nf, W).astype(np.float64) ** 2).mean(axis=1))
    env = env - env.mean()
    E = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    efr = np.fft.rfftfreq(len(env), 0.02)
    tot = E[efr > 0.3].sum()
    print(f"\n{label}: envelope modulation, % of 0.3-25 Hz energy")
    for a, b in [(0.3, 2), (2, 4), (4, 6), (6, 8), (8, 12), (12, 25)]:
        print(f"   {a:>4}-{b:<4} Hz : {100*E[(efr>=a)&(efr<b)].sum()/tot:5.1f}%")


modspec(x, "live capture (failing)")
xp, _ = sf.read(r"H:\sotto\_main\bfrc_played_capture.wav", dtype="float32")
if xp.ndim > 1:
    xp = xp.mean(axis=1)
modspec(xp, "played capture (KNOWN speech)")

hp = highpass_fft(x, sr, 120.0)
sf.write(r"H:\sotto\_main\bfrc_live_highpass.wav", hp, sr, subtype="FLOAT")
print(f"\nhighpass 120 Hz -> _main/bfrc_live_highpass.wav peak={abs(hp).max():.5f} "
      f"rms={np.sqrt((hp.astype('float64')**2).mean()):.6f}")
