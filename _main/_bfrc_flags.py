"""BlankFramesRootCause — THE decisive read: does the loopback return SILENT-flagged
packets, and what is actually in them?

`worker/wasapi_loopback.py:474-496` reads GetBuffer's `flags` and throws it away:
it never tests AUDCLNT_BUFFERFLAGS_SILENT (0x2). Microsoft documents that when that
flag is set the buffer CONTENTS ARE UNDEFINED. A tap that ignores it turns
"undefined" into "audio" and every downstream counter (nonzero_blocks, peak, rms)
reports a signal where Windows said there was none.

This script re-reads the same default render endpoint with the SAME COM plumbing
but KEEPS the flags, per packet, and measures what each packet contains.
READ-ONLY: no stream is started except this capture; nothing is played.
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

import numpy as np

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback as W  # noqa: E402

AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY = 0x1
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR = 0x4
AUDCLNT_SILENT_FLAG = 0x2

ole32 = ctypes.WinDLL("ole32", use_last_error=True)

ep = W.default_render_endpoint()
print(f"endpoint {ep!r} tag={ep.format_tag} bits={ep.bits} ch={ep.channels} align={ep.block_align} rate={ep.rate}")

# activate IAudioClient on the default render endpoint
enum = ctypes.c_void_p()
ole32.CoCreateInstance(ctypes.byref(W.CLSID_MMDeviceEnumerator), None, W.CLSCTX_INPROC_SERVER,
                       ctypes.byref(W.IID_IMMDeviceEnumerator), ctypes.byref(enum))
dev = ctypes.c_void_p()
_vtbl = W._vtbl
HRESULT = W.HRESULT
_vtbl(enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
    enum, 0, 0, ctypes.byref(dev))
client = ctypes.c_void_p()
_vtbl(dev, 3, HRESULT, ctypes.POINTER(W.GUID), wintypes.DWORD, ctypes.c_void_p,
      ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(W.IID_IAudioClient), W.CLSCTX_INPROC_SERVER,
                                       None, ctypes.byref(client))
mix = ctypes.POINTER(W.WAVEFORMATEX)()
_vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(W.WAVEFORMATEX)))(client, ctypes.byref(mix))
init = _vtbl(client, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.c_int64, ctypes.c_int64,
             ctypes.POINTER(W.WAVEFORMATEX), ctypes.c_void_p)
hr = init(client, 0, 0x00020000, 0, 0, mix, None)  # SHARED | LOOPBACK
if hr != 0:
    hr = init(client, 0, 0x00020000, 1000000, 0, mix, None)
print("Initialize hr =", hr)
cap = ctypes.c_void_p()
_vtbl(client, 14, HRESULT, ctypes.POINTER(W.GUID), ctypes.POINTER(ctypes.c_void_p))(
    client, ctypes.byref(W.IID_IAudioCaptureClient), ctypes.byref(cap))
_vtbl(client, 10, HRESULT)(client)  # Start

next_size = _vtbl(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))
get_buffer = _vtbl(cap, 3, HRESULT, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
                   ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
                   ctypes.POINTER(ctypes.c_int64))
release = _vtbl(cap, 4, HRESULT, wintypes.DWORD)

float_fmt = ep.format_tag == W.WAVE_FORMAT_IEEE_FLOAT
flags_hist = {}
packets = []
samples = []
t0 = time.time()
while time.time() - t0 < 8.0:
    n = wintypes.DWORD(0)
    if next_size(cap, ctypes.byref(n)) != 0:
        break
    if n.value == 0:
        time.sleep(0.002)
        continue
    data = ctypes.POINTER(ctypes.c_ubyte)()
    frames = wintypes.DWORD(0)
    flags = wintypes.DWORD(0)
    pos = ctypes.c_int64(0)
    get_buffer(cap, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), ctypes.byref(pos))
    flags_hist[flags.value] = flags_hist.get(flags.value, 0) + 1
    peak = None
    if frames.value and data:
        raw = ctypes.string_at(data, frames.value * ep.block_align)
        arr = np.frombuffer(raw, dtype=np.float32) if float_fmt else \
            np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        if ep.channels > 1:
            arr = arr.reshape(-1, ep.channels).mean(axis=1)
        peak = float(abs(arr).max())
        samples.append(arr.copy())
    packets.append((flags.value, frames.value, peak))
    release(cap, frames.value)
_vtbl(client, 11, HRESULT)(client)  # Stop

print("packets:", len(packets))
print("flag histogram (value -> count):")
for f, c in sorted(flags_hist.items()):
    bits = []
    if f & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY:
        bits.append("DATA_DISCONTINUITY")
    if f & AUDCLNT_BUFFERFLAGS_SILENT:
        bits.append("***SILENT***")
    if f & AUDCLNT_BUFFERFLAGS_TIMESTAMP_ERROR:
        bits.append("TIMESTAMP_ERROR")
    print(f"   flags=0x{f:X} (0b{f:04b}) count={c}  {'|'.join(bits) if bits else 'normal data'}")

silent = [p for p in packets if p[0] & AUDCLNT_SILENT_FLAG]
print(f"packets flagged SILENT: {len(silent)}/{len(packets)}")
sflag = [p[2] for p in silent if p[2] is not None]
nflag = [p[2] for p in packets if not (p[0] & AUDCLNT_SILENT_FLAG) and p[2] is not None]
if sflag:
    print(f"  SILENT-flagged packets: peak min={min(sflag):.6f} med={np.median(sflag):.6f} max={max(sflag):.6f}")
if nflag:
    print(f"  normal   packets: peak min={min(nflag):.6f} med={np.median(nflag):.6f} max={max(nflag):.6f}")
if samples:
    x = np.concatenate(samples)
    print(f"total samples={len(x)} ({len(x)/ep.rate:.2f}s) peak={abs(x).max():.5f} rms={np.sqrt((x.astype('float64')**2).mean()):.6f}")
