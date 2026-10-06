import ctypes
from ctypes import wintypes

HRESULT = ctypes.c_long
ole32 = ctypes.WinDLL("ole32")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def guid(s):
    a, b, c, d, e = s.strip().strip("{}").split("-")
    tail = [int(d[i:i + 2], 16) for i in (0, 2)]
    tail += [int(e[i:i + 2], 16) for i in (0, 2, 4, 6, 8, 10)]
    return GUID(int(a, 16), int(b, 16), int(c, 16), (ctypes.c_ubyte * 8)(*tail))


CLSID = guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
IID_ENUM = guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
IID_IUNKNOWN = guid("{00000000-0000-0000-C000-000000000046}")

ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
ole32.CoInitializeEx.restype = HRESULT
ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = HRESULT
ole32.CoInitializeEx(None, 0)

p = ctypes.c_void_p()
hr = ole32.CoCreateInstance(ctypes.byref(CLSID), None, 1, ctypes.byref(IID_ENUM), ctypes.byref(p))
print("CoCreateInstance hr=0x%08X ptr=%s" % (hr & 0xFFFFFFFF, hex(p.value)))

vtbl = ctypes.cast(p, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
print("vtbl base = %s" % hex(ctypes.cast(vtbl, ctypes.c_void_p).value))
for i in range(8):
    print("   slot[%d] = %s" % (i, hex(ctypes.cast(vtbl[i], ctypes.c_void_p).value or 0)))

# QueryInterface is slot 0 and is guaranteed valid on any COM object.
qi = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))(vtbl[0])
out = ctypes.c_void_p()
h = qi(p, ctypes.byref(IID_IUNKNOWN), ctypes.byref(out))
print("QueryInterface(IUnknown) hr=0x%08X out=%s" % (h & 0xFFFFFFFF, hex(out.value or 0)))

# CFUNCTYPE variant of the same call (x64 makes stdcall==cdecl)
gde = ctypes.CFUNCTYPE(HRESULT, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD)(vtbl[4])
try:
    h = gde(p, 0, 0)
    print("GetDefaultAudioEndpoint(CFUNCTYPE) hr=0x%08X" % (h & 0xFFFFFFFF))
except OSError as e:
    print("GetDefaultAudioEndpoint(CFUNCTYPE) FAULT:", e)
