"""BlankFramesRootCause — WHICH render endpoint is default, and WHICH process is
putting audio into it right now.

The live run captures "WASAPI loopback of the DEFAULT render endpoint" and that
endpoint reports NO friendly name (PKEY_Device_FriendlyName comes back empty on
this box), so the run's own log cannot say WHICH of the six candidate endpoints
it opened. This enumerates every ACTIVE render endpoint, names it, says which is
the default, reads each one's master peak meter, and (for the default) lists the
audio sessions with their process id -- i.e. names the producer of the sound.

READ-ONLY: every call is a query. No stream is started, nothing is played.
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.join(r"H:\sotto", "worker"))
import wasapi_loopback as W  # noqa: E402

GUID = W.GUID
HRESULT = W.HRESULT
_vtbl = W._vtbl
_guid = W._guid
_fmt = W._fmt

IID_IAudioSessionManager2 = _guid("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
IID_IAudioMeterInformation = _guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")
PKEY_FriendlyName = _guid("{A45C254E-DF1C-4EFD-8020-67D146A850E0}")


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]


ole32 = ctypes.WinDLL("ole32", use_last_error=True)
ole32.CoInitializeEx(None, 0)  # COINIT_MULTITHREADED == 0

enum = ctypes.c_void_p()
hr = ole32.CoCreateInstance(
    ctypes.byref(W.CLSID_MMDeviceEnumerator), None, W.CLSCTX_INPROC_SERVER,
    ctypes.byref(W.IID_IMMDeviceEnumerator), ctypes.byref(enum))
assert hr == 0, _fmt(hr)

# which is default (render)
E_RENDER, E_CONSOLE = 0, 0
dev_default = ctypes.c_void_p()
_vtbl(enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
    enum, E_RENDER, E_CONSOLE, ctypes.byref(dev_default))
get_id = _vtbl(dev_default, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))
buf = ctypes.c_wchar_p()
_vtbl(dev_default, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev_default, ctypes.byref(buf))
default_id = buf.value if buf.value else None
ole32.CoTaskMemFree(buf)
print("DEFAULT RENDER ENDPOINT id =", default_id)

# enumerate all active render endpoints: DEVICE_STATE_ACTIVE = 1
coll = ctypes.c_void_p()
DEVICE_STATE_ACTIVE = 0x00000001
hr = _vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
    enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll))
print("EnumAudioEndpoints hr =", hr)
count = wintypes.UINT(0)
_vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))
print("active render endpoints:", count.value)

def friendly(dev):
    store = ctypes.c_void_p()
    hr = _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
               ctypes.POINTER(ctypes.c_void_p))(
        dev, ctypes.byref(W.IID_IPropertyStore), W.CLSCTX_INPROC_SERVER, None, ctypes.byref(store))
    if hr != 0:
        return None
    var = (ctypes.c_ubyte * 24)()
    pk = PROPERTYKEY(PKEY_FriendlyName, 14)
    ok = _vtbl(store, 5, HRESULT, ctypes.POINTER(PROPERTYKEY), ctypes.POINTER(ctypes.c_ubyte))(
        store, ctypes.byref(pk), var)
    name = None
    if ok == 0 and ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0] == 0x001B:
        name = ctypes.cast(ctypes.cast(var, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.c_wchar_p).value
    return name

rows = []
for i in range(count.value):
    dev = ctypes.c_void_p()
    _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(coll, i, ctypes.byref(dev))
    idbuf = ctypes.c_wchar_p()
    _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(idbuf))
    did = idbuf.value
    ole32.CoTaskMemFree(idbuf)
    nm = friendly(dev)
    peak = None
    m = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(
            dev, ctypes.byref(IID_IAudioMeterInformation), W.CLSCTX_INPROC_SERVER, None,
            ctypes.byref(m)) == 0:
        p = ctypes.c_float(0.0)
        if _vtbl(m, 3, HRESULT, ctypes.POINTER(ctypes.c_float))(m, ctypes.byref(p)) == 0:
            peak = p.value
        W._release(m)
    rows.append((i, nm, did, peak, did == default_id))
for i, nm, did, peak, isdef in rows:
    print(f"  [{'DEFAULT' if isdef else '       '}] peak={('%.6f'%peak) if peak is not None else 'n/a':>9}  {nm!r}  {did}")

# audio sessions on the default endpoint
print("\nSESSIONS on the default render endpoint:")
mgr = ctypes.c_void_p()
hr = _vtbl(dev_default, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
           ctypes.POINTER(ctypes.c_void_p))(
    dev_default, ctypes.byref(IID_IAudioSessionManager2), W.CLSCTX_INPROC_SERVER, None,
    ctypes.byref(mgr))
print("Activate(IAudioSessionManager2) hr =", hr)
if hr == 0:
    senum = ctypes.c_void_p()
    hr2 = _vtbl(mgr, 5, HRESULT, ctypes.POINTER(ctypes.c_void_p))(mgr, ctypes.byref(senum))
    print("GetSessionEnumerator hr =", hr2)
    if hr2 == 0:
        sc = wintypes.INT(0)
        _vtbl(senum, 3, HRESULT, ctypes.POINTER(wintypes.INT))(senum, ctypes.byref(sc))
        print("session count =", sc.value)
        for j in range(sc.value):
            s = ctypes.c_void_p()
            _vtbl(senum, 4, HRESULT, wintypes.INT, ctypes.POINTER(ctypes.c_void_p))(senum, j, ctypes.byref(s))
            pid = wintypes.DWORD(0)
            _vtbl(s, 14, HRESULT, ctypes.POINTER(wintypes.DWORD))(s, ctypes.byref(pid))
            state = wintypes.DWORD(0)
            _vtbl(s, 3, HRESULT, ctypes.POINTER(wintypes.DWORD))(s, ctypes.byref(state))
            dn = ctypes.c_wchar_p()
            _vtbl(s, 4, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(s, ctypes.byref(dn))
            dname = dn.value
            if dname:
                ole32.CoTaskMemFree(dn)
            name = "?"
            try:
                import subprocess
                out = subprocess.run(["tasklist", "/FI", f"PID eq {pid.value}", "/FO", "CSV", "/NH"],
                                     capture_output=True, text=True, creationflags=0x08000000).stdout.strip()
                name = out.split(",")[0].strip('"') if out else "?"
            except Exception:
                pass
            print(f"  session[{j}] pid={pid.value:<8} state={state.value} proc={name!r} display={dname!r}")
