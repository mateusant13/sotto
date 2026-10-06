"""BlankFramesRootCause — build the control inputs for the decisive experiment.

Inputs are derived from the SAME speech (pt-br-sample.wav, 22050 Hz) so that the
ONLY things varying across arms are (a) the sample rate the worker sees and hence
which resample branch runs, and (b) the signal level.

  22050 Hz  -> src % 16000 != 0 -> np.interp branch        (the "file" arm)
  48000 Hz  -> src % 16000 == 0 -> 3:1 block-average branch (the "live" arm's branch)
"""
import numpy as np
import soundfile as sf

SRC = "_main/pt-br-sample.wav"
x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
print(f"src {SRC} sr={sr} n={len(x)} peak={abs(x).max():.6f} rms={np.sqrt((x.astype('float64')**2).mean()):.8f}")

# level that reproduces the measured LIVE tap: peak=0.100510 rms=0.01474
g = 0.100510 / float(abs(x).max())
xq = (x * g).astype(np.float32)
print(f"quiet gain={g:.6f} peak={abs(xq).max():.6f} rms={np.sqrt((xq.astype('float64')**2).mean()):.8f}")

def upsample(sig, src_sr, dst_sr):
    n = int(len(sig) * dst_sr / src_sr)
    return np.interp(np.linspace(0, len(sig) - 1, n), np.arange(len(sig)), sig).astype(np.float32)

sf.write("_main/bfrc_a_22050_full.wav", x, sr, subtype="PCM_16")
sf.write("_main/bfrc_a_22050_quiet.wav", xq, sr, subtype="PCM_16")
x48 = upsample(x, sr, 48000)
xq48 = upsample(xq, sr, 48000)
sf.write("_main/bfrc_c_48000_full.wav", x48, 48000, subtype="PCM_16")
sf.write("_main/bfrc_c_48000_quiet.wav", xq48, 48000, subtype="PCM_16")
for f in ["_main/bfrc_a_22050_full.wav", "_main/bfrc_a_22050_quiet.wav",
          "_main/bfrc_c_48000_full.wav", "_main/bfrc_c_48000_quiet.wav"]:
    y, s = sf.read(f, dtype="float32")
    print(f"{f} sr={s} n={len(y)} peak={abs(y).max():.6f} rms={np.sqrt((y.astype('float64')**2).mean()):.8f}")
