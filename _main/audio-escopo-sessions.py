"""AudioEscopo — WHO is rendering on EACH active render endpoint, by pid.

The peak on an endpoint says SOMETHING is playing; it does not say who. On this
box a sibling lane's fixture player targets "CABLE Input" by default, so a peak
measured on a virtual cable may be a sibling's tone and NOT the owner's audio.
This names the render sessions (pid + process + display name) per endpoint, so
the confound is visible instead of assumed away.

    pythonw.exe _main/audio-escopo-sessions.py            # json + log
"""
import ctypes
import io
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "worker"))
import wasapi_loopback as W  # noqa: E402

HRESULT = W.HRESULT
_vtbl = W._vtbl
GUID = W.GUID

IID_IAudioSessionManager2 = W._guid("{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}")
IID_IAudioMeterInformation = W._guid("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

OUT_JSON = os.path.join(HERE, "audio-escopo-sessions.json")
OUT_LOG = os.path.join(HERE, "audio-escopo-sessions.log")
log_f = io.open(OUT_LOG, "w", encoding="utf-8")


def p(*a):
    log_f.write(" ".join(str(x) for x in a) + "\n")
    log_f.flush()


ole32 = ctypes.WinDLL("ole32", use_last_error=True)
ole32.CoInitializeEx(None, 0)

E_RENDER, E_CONSOLE, DEVICE_STATE_ACTIVE = 0, 0, 0x1


def dev_id(dev):
    b = ctypes.c_wchar_p()
    _vtbl(dev, 5, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(dev, ctypes.byref(b))
    v = b.value
    ole32.CoTaskMemFree(b)
    return v


def proc_name(pid):
    if not pid:
        return "?"
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000).stdout.strip()
        if out and not out.startswith("INFO:"):
            return out.split(",")[0].strip('"')
    except Exception as exc:
        return "<%s>" % type(exc).__name__
    return "?"


def sessions(dev):
    mgr = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(IID_IAudioSessionManager2),
                                              W.CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(mgr)) != 0:
        return None
    senum = ctypes.c_void_p()
    if _vtbl(mgr, 5, HRESULT, ctypes.POINTER(ctypes.c_void_p))(mgr, ctypes.byref(senum)) != 0:
        W._release(mgr)
        return []
    sc = wintypes.INT(0)
    _vtbl(senum, 3, HRESULT, ctypes.POINTER(wintypes.INT))(senum, ctypes.byref(sc))
    rows = []
    for j in range(sc.value):
        s = ctypes.c_void_p()
        if _vtbl(senum, 4, HRESULT, wintypes.INT, ctypes.POINTER(ctypes.c_void_p))(
                senum, j, ctypes.byref(s)) != 0:
            continue
        pid = wintypes.DWORD(0)
        _vtbl(s, 14, HRESULT, ctypes.POINTER(wintypes.DWORD))(s, ctypes.byref(pid))
        state = wintypes.DWORD(0)
        _vtbl(s, 3, HRESULT, ctypes.POINTER(wintypes.DWORD))(s, ctypes.byref(state))
        dn = ctypes.c_wchar_p()
        _vtbl(s, 4, HRESULT, ctypes.POINTER(ctypes.c_wchar_p))(s, ctypes.byref(dn))
        dname = dn.value
        if dname:
            ole32.CoTaskMemFree(dn)
        rows.append({"pid": pid.value, "process": proc_name(pid.value),
                     "state": state.value, "display": dname})
        W._release(s)
    W._release(senum)
    W._release(mgr)
    return rows


def meter_peak(dev, seconds=1.0):
    m = ctypes.c_void_p()
    if _vtbl(dev, 3, HRESULT, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p,
             ctypes.POINTER(ctypes.c_void_p))(dev, ctypes.byref(IID_IAudioMeterInformation),
                                              W.CLSCTX_INPROC_SERVER, None,
                                              ctypes.byref(m)) != 0:
        return None
    get_peak = _vtbl(m, 3, HRESULT, ctypes.POINTER(ctypes.c_float))
    best = 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        v = ctypes.c_float(0.0)
        if get_peak(m, ctypes.byref(v)) == 0:
            best = max(best, float(v.value))
        time.sleep(0.05)
    W._release(m)
    return best


def main():
    enum = ctypes.c_void_p()
    ole32.CoCreateInstance(ctypes.byref(W.CLSID_MMDeviceEnumerator), None,
                           W.CLSCTX_INPROC_SERVER, ctypes.byref(W.IID_IMMDeviceEnumerator),
                           ctypes.byref(enum))
    dev_default = ctypes.c_void_p()
    _vtbl(enum, 4, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
        enum, E_RENDER, E_CONSOLE, ctypes.byref(dev_default))
    default_id = dev_id(dev_default)
    coll = ctypes.c_void_p()
    _vtbl(enum, 3, HRESULT, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(
        enum, E_RENDER, DEVICE_STATE_ACTIVE, ctypes.byref(coll))
    count = wintypes.UINT(0)
    _vtbl(coll, 3, HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))

    out = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "default_id": default_id,
           "endpoints": []}
    p("=== AudioEscopo session census ===")
    p("timestamp:", out["timestamp"])
    p("default:", default_id)
    for i in range(count.value):
        dev = ctypes.c_void_p()
        _vtbl(coll, 4, HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(
            coll, i, ctypes.byref(dev))
        did = dev_id(dev)
        mp = meter_peak(dev, 1.0)
        sess = sessions(dev)
        row = {"index": i, "id": did, "is_default": did == default_id,
               "meter_peak": mp, "sessions": sess}
        out["endpoints"].append(row)
        p("")
        p("[%s] %s  meter_peak=%s  sessions=%s"
          % ("DEFAULT" if row["is_default"] else "       ", did,
             ("%.6f" % mp) if mp is not None else "n/a",
             "n/a" if sess is None else len(sess)))
        for s in (sess or []):
            p("      pid=%-8s state=%s proc=%r display=%r"
              % (s["pid"], s["state"], s["process"], s["display"]))
    with io.open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    p("")
    p("wrote", OUT_JSON)
    log_f.close()
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
