"""Play a file to the WASAPI default render endpoint, hidden, for N seconds.

Used as the positive control for the Sotto ladder: it makes the default render
endpoint actually RENDER, which is the only condition under which a WASAPI
loopback client is fed. Kill by artifact path only.
"""
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sf_mod  # noqa: F401  (import check)
import sounddevice as sd
import soundfile as sf

SRC = sys.argv[1] if len(sys.argv) > 1 else r"H:\sotto\worker\assets\sample1.flac"
SECONDS = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0

apis = sd.query_hostapis()
wasapi = next((a for a in apis if "wasapi" in a["name"].lower()), None)
dev = wasapi["default_output_device"] if wasapi else None
info = sd.query_devices(dev) if dev is not None else sd.query_devices(kind="output")
rate = int(info["default_samplerate"])
ch = int(info["max_output_channels"]) or 2
print("playing %s to %r (index %s, %d Hz, %d ch) for %.0fs" % (SRC, info["name"], dev, rate, ch, SECONDS))

pcm, src_rate = sf.read(SRC, dtype="float32", always_2d=True)
if src_rate != rate:
    n = int(len(pcm) * rate / src_rate)
    idx = np.linspace(0, len(pcm) - 1, n)
    pcm = np.stack([np.interp(idx, np.arange(len(pcm)), pcm[:, c]) for c in range(pcm.shape[1])], axis=1)
    print("resampled %d -> %d Hz" % (src_rate, rate))
if pcm.shape[1] < ch:
    pcm = np.repeat(pcm, ch, axis=1)[:, :ch]
elif pcm.shape[1] > ch:
    pcm = pcm[:, :ch]

# np.interp/np.repeat widen to float64; PortAudio's OutputStream with
# dtype='float32' REFUSES a float64 array ("dtype mismatch"), and a player that
# raises before its first write makes the loopback read silence -- which reads
# like a loopback failure. Cast once, here.
pcm = np.ascontiguousarray(pcm, dtype="float32")

stop = threading.Event()
t0 = time.time()
with sd.OutputStream(device=dev, samplerate=rate, channels=ch, dtype="float32") as out:
    while not stop.is_set() and (time.time() - t0) < SECONDS:
        out.write(pcm)
print("played %.1fs" % (time.time() - t0))
