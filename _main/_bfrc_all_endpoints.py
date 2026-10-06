"""BlankFramesRootCause — capture EVERY active render endpoint for 2 s and report,
per endpoint: the GetBuffer FLAGS histogram, the peak, and the rms.

Purpose: the pump in worker/wasapi_loopback.py:474-496 never tests
AUDCLNT_BUFFERFLAGS_SILENT. Microsoft's contract for that flag is that the buffer
CONTENTS ARE UNDEFINED. If an idle endpoint returns SILENT packets and this tap
turns them into "audio", then the run's own counters (nonzero_blocks, peak, rms)
are a claim Windows never made. This measures whether that state is reachable
here, and what the honest level of each endpoint is.
READ-ONLY: no stream is started except these captures; nothing is played.
"""
import ctypes
import time
from ctypes import wintypes

import numpy as np

import os
import sys

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback as W  # noqa: E402

HRESULT = W.HRESULT
_vtbl = W._vtbl
FLAG_DISC = 0x1
FLAG_SILENT = 0x2
FLAG_TS = 0x4

ep_default = W.default_render_endpoint()

ole32 = ctypes.WinDLL("ole32", use_last_error=True)
enum = ctypes.c_void_p()
ole32.CoCreateInstance(ctypes.byref(W.CLSID_MMDeviceEnumerator), None, W.CLSCTX_INPROC_SERVER,
                       ctypes.byref(W.IID_IMMDeviceEnumerator), ctypes.byref(enum))
coll = ctypes.c_void_p()
_vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
    enum, 0, 1, ctypes.byref(coll))
count = wintypes.UINT(0)
_vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
print("active render endpoints:", count.value)


def dev_id(dev):
    b = ctypes.c_wchar_p()
    _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(b))
    v = b.value
    ole32.CoTaskMemFree(b)
    return v


def capture(dev, seconds=2.0):
    client = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(W.GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(W.IID_IAudioClient),
                                              W.CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(client)) != 0:
        return None
    mix = ctypes.POINTER(W.WAVEFORMATEX)()
    if _vtbl(client, 8, HRESULT, ctypes.POINTER(ctypes.POINTER(W.WAVEFORMATEX)))(client, ctypes.byref(mix)) != 0:
        return None
    init = _vtbl(client, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.c_int64, ctypes.c_int64,
                 ctypes.POINTER(W.WAVEFORMATEX), ctypes.c_void_p)
    if init(client, 0, 0x00020000, 1000000, 0, mix, None) != 0:
        return None
    cap = ctypes.c_void_p()
    if _vtbl(client, 14, HRESULT, ctypes.POINTER(W.GUID), ctypes.POINTER(ctypes.c_void_p))(
            client, ctypes.byref(W.IID_IAudioCaptureClient), ctypes.byref(cap)) != 0:
        return None
    _vtbl(client, 10, HRESULT)(client)
    wf = mix.contents
    ch = int(wf.nChannels)
    align = int(wf.nBlockAlign)
    chunks = []
    hist = {}
    t0 = time.time()
    while time.time() - t0 < seconds:
        n = wintypes.DWORD(0)
        if _vtbl(cap, 5, HRESULT, ctypes.POINTER(wintypes.DWORD))(cap, ctypes.byref(n)) != 0:
            break
        if n.value == 0:
            time.sleep(0.002)
            continue
        data = ctypes.POINTER(ctypes.c_ubyte)()
        frames = wintypes.DWORD(0)
        flags = wintypes.DWORD(0)
        pos = ctypes.c_int64(0)
        _vtbl(cap, 3, HRESULT, ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),
              ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD),
              ctypes.POINTER(ctypes.c_int64))(
            cap, ctypes.byref(data), ctypes.byref(frames), ctypes.byref(flags), ctypes.byref(pos))
        hist[flags.value] = hist.get(flags.value, 0) + 1
        if frames.value and data:
            arr = np.frombuffer(ctypes.string_at(data, frames.value * align), dtype=np.float32)
            if ch > 1:
                arr = arr.reshape(-1, ch).mean(axis=1)
            chunks.append(arr.copy())
        _vtbl(cap, 4, HRESULT, wintypes.DWORD)(cap, frames.value)
    _vtbl(client, 11, HRESULT)(client)
    x = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    return hist, x


for i in range(count.value):
    dev = ctypes.c_void_p()
    _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(coll, i, ctypes.byref(dev))
    did = dev_id(dev)
    tag = "DEFAULT" if did == ep_default.endpoint_id else "       "
    r = capture(dev)
    if r is None:
        print(f"  [{tag}] {did}  <capture failed>")
        continue
    hist, x = r
    flags_s = ", ".join(
        f"0x{f:X}"
        + ("[SILENT]" if f & FLAG_SILENT else "")
        + ("[DISC]" if f & FLAG_DISC else "")
        + ("[TSERR]" if f & FLAG_TS else "")
        + f"x{c}" for f, c in sorted(hist.items()))
    if len(x):
        print(f"  [{tag}] {did}\n        flags: {flags_s}\n        n={len(x)} peak={abs(x).max():.6f} "
              f"rms={np.sqrt((x.astype('float64')**2).mean()):.6f}")
    else:
        print(f"  [{tag}] {did}\n        flags: {flags_s}\n        n=0")
