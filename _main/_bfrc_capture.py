"""BlankFramesRootCause — capture the RAW loopback tap to a WAV, and measure it.

Read-only w.r.t. the worker: it uses worker/wasapi_loopback.WasapiLoopbackTap
directly, the same object the live run uses, so what lands here is EXACTLY what
the live run feeds to the ASR -- at the native mix rate, before any resample.
"""
import os
import sys
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback  # noqa: E402

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
OUT = sys.argv[2] if len(sys.argv) > 2 else r"H:\sotto\_main\bfrc_live_capture.wav"

blocks = []
started = {"t": None}


def on_block(block):
    if started["t"] is None:
        started["t"] = time.time()
    blocks.append(block.copy())


tap = wasapi_loopback.WasapiLoopbackTap(on_block, block_ms=100)
print(f"tap rate={tap.rate} block={tap.block} native={getattr(tap,'native_rate',None)}")
with tap:
    t0 = time.time()
    while time.time() - t0 < SECONDS:
        time.sleep(0.05)

x = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
nblocks = len(blocks)
rate = tap.rate
print(f"blocks={nblocks} samples={len(x)} rate={rate} wall={time.time()-t0:.2f}s audio_s={len(x)/rate:.2f}")
if len(x):
    print(f"peak={float(abs(x).max()):.6f} rms={float(np.sqrt((x.astype('float64')**2).mean())):.8f} "
          f"nonzero_frac={float((abs(x) > 1e-4).mean()):.4f}")
    mono = x
    if mono.ndim > 1:
        mono = mono.mean(axis=1)
    # per-block energy: is signal steady or bursty?
    per = []
    for b in blocks:
        bb = b.mean(axis=1) if b.ndim > 1 else b
        per.append(float(np.sqrt((bb.astype("float64") ** 2).mean())))
    per = np.array(per)
    print(f"per-block rms: min={per.min():.6f} med={np.median(per):.6f} max={per.max():.6f} "
          f"blocks_below_1e-4={(per < 1e-4).sum()}")
    # crude band split: energy above 4 kHz vs below (a 3:1 boxcar + real speech differ)
    if len(mono) > 4096:
        n = 1 << int(np.log2(min(len(mono), 1 << 16)))
        seg = mono[:n] - mono[:n].mean()
        w = np.hanning(n)
        S = np.abs(np.fft.rfft(seg * w)) ** 2
        f = np.fft.rfftfreq(n, 1.0 / rate)
        lo = S[(f >= 100) & (f < 4000)].sum()
        hi = S[(f >= 4000) & (f < 8000)].sum()
        print(f"energy 100-4k={lo:.3e} 4k-8k={hi:.3e} ratio_hi_lo={hi/max(lo,1e-30):.4f}")
    sf.write(OUT, x if x.ndim == 1 else x, rate, subtype="FLOAT")
    print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes, {rate} Hz)")
