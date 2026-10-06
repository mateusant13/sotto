"""BlankFramesDecisive -- what IS the default render endpoint, and what does the
failing capture contain? Names the endpoint behind the loopback GUID and prints
the envelope-modulation spectrum of the failing capture vs the known-speech one.
READ-ONLY."""
import os
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, r"H:\sotto\worker")
import wasapi_loopback as W  # noqa: E402

# ── 1. name the default render endpoint ──────────────────────────────────────
import ctypes
from ctypes import wintypes

ole32 = ctypes.WinDLL("ole32", use_last_error=True)
ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED, required before CoCreateInstance
enum = ctypes.c_void_p()
ole32.CoCreateInstance(ctypes.byref(W.CLSID_MMDeviceEnumerator), None, W.CLSCTX_INPROC_SERVER,
                       ctypes.byref(W.IID_IMMDeviceEnumerator), ctypes.byref(enum))
dev = ctypes.c_void_p()
W._vtbl(enum, 4, W.HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
    enum, 0, 0, ctypes.byref(dev))
ps = ctypes.c_void_p()
hr = W._vtbl(dev, 4, W.HRESULT, ctypes.POINTER(W.GUID), wintypes.DWORD,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(W.IID_IPropertyStore), 0,
                                             ctypes.byref(ps))
pv = (ctypes.c_ubyte * 64)()
if hr == 0:
    W._vtbl(ps, 5, W.HRESULT, ctypes.POINTER(W.PROPERTYKEY), ctypes.c_void_p)(
        ps, ctypes.byref(W._PKEY_FRIENDLY), ctypes.byref(pv))
    name = ctypes.wstring_at(ctypes.addressof(pv) + 8)
    print(f"default render endpoint friendly name = {name!r}")
else:
    print(f"property store hr={hr}")

# the endpoint id the loopback reports
iid = ctypes.c_void_p()
try:
    W._vtbl(dev, 5, W.HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(iid))
except Exception:
    pass
try:
    W._vtbl(dev, 5, W.HRESULT, ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(iid))
    print("device id =", ctypes.wstring_at(iid))
except Exception as exc:
    print("device id probe:", exc)

# ── 2. what does the default OUTPUT device look like to PortAudio? ───────────
import sounddevice as sd  # noqa: E402
print("sd.default.device =", sd.default.device)
for i, d in enumerate(sd.query_devices()):
    if d["max_output_channels"] > 0:
        print(f"  out[{i}] {d['name']!r} api={sd.query_hostapis(d['hostapi'])['name']!r} "
              f"out_ch={d['max_output_channels']} sr={d['default_samplerate']}")

# ── 3. envelope modulation: failing capture vs known-speech capture ──────────
W_IN = int(48000 * 0.02)


def modspec(path, label):
    x, sr = sf.read(path, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    nf = len(x) // W_IN
    env = np.sqrt((x[: nf * W_IN].reshape(nf, W_IN).astype(np.float64) ** 2).mean(axis=1))
    env = env - env.mean()
    E = np.abs(np.fft.rfft(env * np.hanning(len(env)))) ** 2
    efr = np.fft.rfftfreq(len(env), 0.02)
    tot = E[efr > 0.3].sum()
    print(f"\n{label}: {path}")
    print(f"  peak={abs(x).max():.5f} rms={np.sqrt((x.astype('float64')**2).mean()):.6f} "
          f"dur={len(x)/sr:.2f}s")
    for a, b in [(0.3, 2), (2, 4), (4, 6), (6, 8), (8, 12), (12, 25)]:
        pct = 100 * E[(efr >= a) & (efr < b)].sum() / tot if tot else 0
        print(f"   {a:>4}-{b:<4} Hz : {pct:5.1f}%")


modspec(r"H:\sotto\_main\bfrc_live_capture.wav", "FAILING live capture (bfrc_b_live's content)")
modspec(r"H:\sotto\_main\bfrc_played_capture.wav", "KNOWN-speech loopback capture")
modspec(r"H:\sotto\_main\bfrc_mix_0060.wav", "mix: known speech @0.06 + real ambient (CAPTIONED)")
