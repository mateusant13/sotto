"""BlankFramesRootCause — is the loopback TAP faithful?

Model-free falsification: PLAY a known signal on the default render endpoint and
capture it with the SAME WasapiLoopbackTap the live run uses. Then cross-correlate
captured vs played. A faithful tap correlates near 1; a corrupt tap does not.

This is the one experiment that separates "the tap delivers what Windows sends"
from "the tap delivers a distorted copy".
"""
import os
import sys
import threading
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else r"H:\sotto\_main\pt-br-sample.wav"
GAIN = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
OUT_RAW = r"H:\sotto\_main\bfrc_played_capture.wav"

blocks = []


def on_block(b):
    blocks.append(b.copy())


tap = wasapi_loopback.WasapiLoopbackTap(on_block, block_ms=100)
rate = tap.rate
print(f"tap rate={rate} block={tap.block} native={getattr(tap,'native_rate',None)} "
      f"channels={tap.channels} align={tap.ep.block_align} tag={tap.ep.format_tag} bits={tap.ep.bits}")

x, sr = sf.read(SRC, dtype="float32")
if x.ndim > 1:
    x = x.mean(axis=1)
if sr != rate:
    n = int(len(x) * rate / sr)
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
played = (x * GAIN).astype(np.float32)
print(f"playing {SRC} sr={sr} -> {len(played)} samples @ {rate} gain={GAIN} peak={abs(played).max():.4f}")

import sounddevice as sd  # noqa: E402

t_start = {"t": None}
with tap:
    time.sleep(0.4)  # let the ring fill
    t0 = time.time()
    sd.play(played, rate, blocking=True)
    t_play_end = time.time()
    time.sleep(0.3)
fs = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
print(f"captured blocks={len(blocks)} samples={len(fs)} ({len(fs)/rate:.2f}s) play_wall={t_play_end-t0:.2f}s")
sf.write(OUT_RAW, fs, rate, subtype="FLOAT")

# ── align and correlate ──────────────────────────────────────────────────────
cap = fs if fs.ndim == 1 else fs.mean(axis=1)
n = min(len(cap), len(played))
if n > rate:
    # coarse lag search by cross-correlation on a 2 s window
    win = int(rate * 2.0)
    a = cap[: min(len(cap), win * 3)]
    b = played[:win]
    c = np.correlate(a - a.mean(), b - b.mean(), mode="valid")
    lag = int(np.argmax(np.abs(c)))
    print(f"best lag = {lag} samples ({lag/rate*1000:.1f} ms)")
    seg = cap[lag : lag + len(played)]
    m = min(len(seg), len(played))
    A = seg[:m] - seg[:m].mean()
    B = played[:m] - played[:m].mean()
    denom = float(np.sqrt((A ** 2).sum() * (B ** 2).sum()))
    corr = float((A * B).sum() / denom) if denom else 0.0
    print(f"capture peak={float(abs(cap).max()):.5f} rms={float(np.sqrt((cap.astype('float64')**2).mean())):.6f}")
    print(f"played  peak={float(abs(played).max()):.5f} rms={float(np.sqrt((played.astype('float64')**2).mean())):.6f}")
    print(f"normalised cross-correlation (lag-aligned) = {corr:.4f}")
