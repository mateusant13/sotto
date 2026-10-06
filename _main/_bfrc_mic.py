"""BlankFramesRootCause — is the render endpoint actually carrying a MICROPHONE?

The defect being hunted is "the default render endpoint's mix contains a constant
low-frequency rumble and no speech". One mechanism produces exactly that: a capture
device routed to a render device in real time -- Windows' "Listen to this device",
or a virtual mixer's monitor path. This correlates the render loopback against the
default INPUT (microphone) captured at the same time.

PRIVACY: the microphone samples are kept IN MEMORY ONLY. Nothing is written to
disk and no content is printed -- the only outputs are two correlation numbers and
a lag. If the correlation is high, the render endpoint is playing the microphone.

READ-ONLY: no stream is started except these two captures; nothing is played.
"""
import os
import sys
import threading
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback as W  # noqa: E402
import sounddevice as sd  # noqa: E402

SECONDS = 10.0

# ── render loopback ──────────────────────────────────────────────────────────
rblocks = []
tap = W.WasapiLoopbackTap(lambda b: rblocks.append(b.copy()), block_ms=100)
rate = tap.rate

# ── default input (microphone) ───────────────────────────────────────────────
mblocks = []
try:
    info = sd.query_devices(kind="input")
    try:
        sd.check_input_settings(device=info["index"], channels=1, dtype="float32", samplerate=rate)
        mrate = rate
    except Exception:
        mrate = int(info["default_samplerate"])
    print(f"mic: {info['name']!r} index={info['index']} rate={mrate}")


    def mcb(indata, frames, t, status):
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata[:, 0]
        mblocks.append(np.ascontiguousarray(mono, dtype=np.float32))


    mstream = sd.InputStream(device=info["index"], channels=1, samplerate=mrate, dtype="float32",
                             blocksize=int(mrate * 0.1), callback=mcb)
    mic_ok = True
except Exception as exc:
    print(f"microphone unavailable: {type(exc).__name__}: {exc}")
    mic_ok = False
    mrate = rate

with tap:
    if mic_ok:
        mstream.start()
    time.sleep(SECONDS)
    if mic_ok:
        mstream.stop()
        mstream.close()

r = np.concatenate(rblocks) if rblocks else np.zeros(0, np.float32)
if r.ndim > 1:
    r = r.mean(axis=1)
print(f"render loopback: n={len(r)} peak={abs(r).max():.5f} rms={np.sqrt((r.astype('float64')**2).mean()):.6f}")

if not mic_ok or not mblocks:
    print("RESULT: microphone could not be captured -- correlation not measurable")
    raise SystemExit(0)

m = np.concatenate(mblocks)
if m.ndim > 1:
    m = m.mean(axis=1)
print(f"mic (in memory only): n={len(m)} peak={abs(m).max():.5f} rms={np.sqrt((m.astype('float64')**2).mean()):.6f}")

# ── correlation, both at the same nominal rate ───────────────────────────────
if mrate != rate:
    n = int(len(m) * rate / mrate)
    m = np.interp(np.linspace(0, len(m) - 1, n), np.arange(len(m)), m).astype(np.float32)

win = min(len(r), len(m))
# search |lag| <= 2 s either way, on a 2 s window
lag_n = int(rate * 2.0)
seg_r = r[: min(len(r), int(rate * 4))].astype(np.float64)
best = (0.0, 0)
for lag in range(-lag_n, lag_n + 1, 8):
    a = seg_r[max(0, lag): max(0, lag) + int(rate * 2)]
    b = m[: len(a)].astype(np.float64)
    if len(a) < rate or len(b) < len(a):
        continue
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
    if d:
        c = float((a * b).sum() / d)
        if abs(c) > abs(best[0]):
            best = (c, lag)
print(f"best |correlation(lag)| = {best[0]:.4f} at lag {best[1]} samples ({best[1]/rate*1000:.0f} ms)")
print("control: correlation at a deliberately wrong region (r[5s:] vs m[:2s]):", end=" ")
a = r[int(rate * 5):int(rate * 7)].astype(np.float64)
b = m[: len(a)].astype(np.float64)
a = a - a.mean(); b = b - b.mean()
d = np.sqrt((a ** 2).sum() * (b ** 2).sum())
print(f"{float((a*b).sum()/d) if d else 0.0:.4f}")
del m  # drop the mic samples
