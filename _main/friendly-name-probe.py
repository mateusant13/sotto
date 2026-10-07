"""Find the working path to PKEY_Device_FriendlyName for this box.

Tries BOTH documented routes:
  (i)  IMMDevice::Activate(IPropertyStore, CLSCTX_INPROC_SERVER, ...)  -- what
       wasapi_loopback._friendly_name uses today
  (ii) IMMDevice::OpenPropertyStore(STGM_READ, ...)                    -- the
       documented route for a property store
and reads the LPWSTR at BOTH candidate union offsets (0 and 8) of the 24-byte
x64 PROPVARIANT, so the layout assumption is measured rather than assumed.
"""
import ctypes
import os
import sys
from ctypes import wintypes

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "worker"))

import wasapi_loopback as w  # noqa: E402

STGM_READ = 0x00000000

com = w._com_init()
try:
    ole32 = w._ole32()
    enum = w._make_enumerator(ole32)
    coll = ctypes.c_void_p()
    w._vtbl(enum, 3, w.HRESULT, wintypes.DWORD, wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p))(
        enum, w.E_RENDER, w.DEVICE_STATE_ACTIVE, ctypes.byref(coll))
    count = wintypes.UINT(0)
    w._vtbl(coll, 3, w.HRESULT, ctypes.POINTER(wintypes.UINT))(coll, ctypes.byref(count))

    READ_OFFSET_0 = os.environ.get("PROBE_OFFSET0") == "1"

    def name_at(var):
        vt = ctypes.cast(var, ctypes.POINTER(ctypes.c_ushort))[0]
        out = {}
        for off in ((0, 8) if READ_OFFSET_0 else (8,)):
            p = ctypes.cast(ctypes.addressof(var) + off, ctypes.POINTER(ctypes.c_void_p))[0]
            try:
                out[off] = ctypes.cast(p, ctypes.c_wchar_p).value if p else None
            except Exception as exc:
                out[off] = "<unreadable: %s>" % exc
        return vt, out

    for i in range(count.value):
        dev = ctypes.c_void_p()
        if w._vtbl(coll, 4, w.HRESULT, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))(
                coll, i, ctypes.byref(dev)) != 0 or not dev:
            continue
        try:
            eid = w._endpoint_id(dev, ole32)
            print("---- %s" % eid)

            # (i) Activate(IPropertyStore)
            store = ctypes.c_void_p()
            ah = w._vtbl(dev, 3, w.HRESULT, ctypes.POINTER(w.GUID), wintypes.DWORD,
                         ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
                dev, ctypes.byref(w.IID_IPropertyStore), w.CLSCTX_INPROC_SERVER, None,
                ctypes.byref(store))
            print("   (i)  Activate(IPropertyStore) hr=0x%08X store=%s"
                  % (ah & 0xFFFFFFFF, store.value))
            if store and ah == 0:
                var = (ctypes.c_ubyte * 24)()
                gh = w._vtbl(store, 5, w.HRESULT, ctypes.POINTER(w.PROPERTYKEY),
                             ctypes.POINTER(ctypes.c_ubyte))(
                    store, ctypes.byref(w._PKEY_FRIENDLY), var)
                vt, m = name_at(var)
                print("       GetValue hr=0x%08X vt=0x%04X name=%r"
                      % (gh & 0xFFFFFFFF, vt, m[8]))
                w._release(store)

            # (ii) OpenPropertyStore(STGM_READ)
            store2 = ctypes.c_void_p()
            oh = w._vtbl(dev, 4, w.HRESULT, wintypes.DWORD,
                         ctypes.POINTER(ctypes.c_void_p))(dev, STGM_READ, ctypes.byref(store2))
            print("   (ii) OpenPropertyStore(STGM_READ) hr=0x%08X store=%s"
                  % (oh & 0xFFFFFFFF, store2.value))
            if store2 and oh == 0:
                var = (ctypes.c_ubyte * 24)()
                gh = w._vtbl(store2, 5, w.HRESULT, ctypes.POINTER(w.PROPERTYKEY),
                             ctypes.POINTER(ctypes.c_ubyte))(
                    store2, ctypes.byref(w._PKEY_FRIENDLY), var)
                vt, m = name_at(var)
                print("       GetValue hr=0x%08X vt=0x%04X name=%r"
                      % (gh & 0xFFFFFFFF, vt, m[8]))
                w._release(store2)
        finally:
            w._release(dev)
    w._release(coll)
    w._release(enum)
finally:
    if com == w.COM_REF_TAKEN:
        w._com_uninit()
