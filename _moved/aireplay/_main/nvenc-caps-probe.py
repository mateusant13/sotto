"""nvenc-caps-probe.py -- ask the INSTALLED DRIVER what its NVENC can do.

Read-only, window-less, no capture, no disk output, no audio device.
Creates a D3D11 device, opens NVENC encode sessions on it, queries
NV_ENC_CAPS_* capability values, then closes every session.

Every struct layout, enum value, GUID byte order and function-table slot index
below is copied from H:\\aireplay\\_main\\sdkref\\nvEncodeAPI.h
(NVENC API 13.1, 313554 B,
 sha256 8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228).
The installed driver reports the matching API version:
NvEncodeAPIGetMaxSupportedVersion -> 0x000000D1 = 13.1.

Output: one JSON object on stdout.
"""
import ctypes
import json
import os
import sys

_TORCH_LIB = r"C:\Program Files\Python311\Lib\site-packages\torch\lib"
if os.path.isdir(_TORCH_LIB):
    try:
        os.add_dll_directory(_TORCH_LIB)
    except OSError:
        pass

NVENCAPI_VERSION = 0x0D | (0x01 << 24)          # 13 | (1<<24)


def SV(ver: int) -> int:
    return NVENCAPI_VERSION | (ver << 16) | (0x7 << 28)


NV_ENC_CAPS_PARAM_VER = SV(1)
NV_ENCODE_API_FUNCTION_LIST_VER = SV(2)
NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER = SV(1)

NV_ENC_DEVICE_TYPE_DIRECTX = 0x0
NV_ENC_DEVICE_TYPE_CUDA = 0x1
NV_ENC_SUCCESS = 0

# ---- NV_ENC_CAPS: value = declaration index in the header ----------------
CAPS = {
    "NUM_MAX_BFRAMES": 0,
    "SUPPORTED_RATECONTROL_MODES": 1,
    "SUPPORT_FIELD_ENCODING": 2,
    "SUPPORT_DYN_RES_CHANGE": 11,
    "SUPPORT_DYN_BITRATE_CHANGE": 12,
    "SUPPORT_DYN_RC_TYPE": 14,
    "SUPPORT_ME_ONLY": 16,
    "SUPPORT_WEIGHTED_PREDICTION": 20,
    "SUPPORT_INTRA_REFRESH": 21,
    "SUPPORT_H264_HIGH_10": 24,
    "SUPPORT_H264_444": 25,
    "SUPPORT_HEVC_444": 26,
    "SUPPORT_HEVC_422": 27,
    "SUPPORT_HEVC_HIGH_10": 28,
    "SUPPORT_HEVC_MAIN10_422": 29,
    "ASYNC_ENCODE_SUPPORT": 30,
    "SUPPORT_2PASS": 31,
    "SUPPORT_LOOKAHEAD": 37,
    "SUPPORT_AV1_MAIN10": 43,
    "SUPPORT_AV1_422": 44,
    "NUM_ENCODER_ENGINES": 49,
    "SUPPORT_SPLIT_FRAME_ENCODING": 50,
    "SUPPORT_ALPHA": 51,
    "SUPPORT_LOOKAHEAD_LEVEL": 56,
}


def guid(a, b, c, d):
    g = (ctypes.c_ubyte * 16)()
    g[0] = a & 0xFF
    g[1] = (a >> 8) & 0xFF
    g[2] = (a >> 16) & 0xFF
    g[3] = (a >> 24) & 0xFF
    g[4] = b & 0xFF
    g[5] = (b >> 8) & 0xFF
    g[6] = c & 0xFF
    g[7] = (c >> 8) & 0xFF
    for i in range(8):
        g[8 + i] = d[i]
    return g


CODEC_GUIDS = {
    "H264": guid(0x6bc82762, 0x4e63, 0x4ca4,
                 (0xAA, 0x85, 0x1E, 0x50, 0xF3, 0x21, 0xF6, 0xBF)),
    "HEVC": guid(0x790cdc88, 0x4522, 0x4d7b,
                 (0x94, 0x25, 0xBD, 0xA9, 0x97, 0x5F, 0x76, 0x03)),
    "AV1": guid(0x0a352289, 0x0aa7, 0x4759,
                (0x86, 0x2D, 0x5D, 0x15, 0xCD, 0x16, 0xD2, 0x54)),
}

# NV_ENCODE_API_FUNCTION_LIST slot indices, counted from the header's order:
#  0 version, 1 reserved, 2 nvEncOpenEncodeSession, 3 GetEncodeGUIDCount,
#  4 GetEncodeProfileGUIDCount, 5 GetEncodeProfileGUIDs, 6 GetEncodeGUIDs,
#  7 GetInputFormatCount, 8 GetInputFormats, 9 GetEncodeCaps,
# ... 29 nvEncOpenEncodeSessionEx, 32 nvEncDestroyEncoder,
# 39 nvEncGetLastErrorString
SLOT_GET_ENCODE_GUID_COUNT = 3
SLOT_GET_ENCODE_CAPS = 9
SLOT_OPEN_SESSION_EX = 29
SLOT_DESTROY_ENCODER = 32
SLOT_GET_LAST_ERROR = 39


class NV_ENC_CAPS_PARAM(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32),
                ("capsToQuery", ctypes.c_int),
                ("reserved", ctypes.c_uint32 * 62)]


class NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32),
                ("deviceType", ctypes.c_int),
                ("device", ctypes.c_void_p),
                ("reserved_dev", ctypes.c_void_p),
                ("apiVersion", ctypes.c_uint32),
                ("reserved1", ctypes.c_uint32 * 253),
                ("reserved2", ctypes.c_void_p * 64)]


# IID_IDXGIFactory1 = {770aae78-f26f-4dba-a829-253c83d1b387}
class _IIDF1(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]


IDXGIFactory1_IID = _IIDF1(0x770AAE78, 0xF26F, 0x4DBA,
                           (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C,
                                                0x83, 0xD1, 0xB3, 0x87))

# IID_ID3D10Multithread = {9B7E4E00-342C-4106-A19F-4F2704F689F0}
MULTITHREAD_IID = _IIDF1(0x9B7E4E00, 0x342C, 0x4106,
                         (ctypes.c_ubyte * 8)(0xA1, 0x9F, 0x4F, 0x27,
                                              0x04, 0xF6, 0x89, 0xF0))


class DXGI_ADAPTER_DESC(ctypes.Structure):    _fields_ = [("Description", ctypes.c_wchar * 128),
                ("VendorId", ctypes.c_uint),
                ("DeviceId", ctypes.c_uint),
                ("SubSysId", ctypes.c_uint),
                ("Revision", ctypes.c_uint),
                ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t),
                ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", ctypes.c_longlong)]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class DXGI_ADAPTER_DESC1(ctypes.Structure):
    _fields_ = [("Description", ctypes.c_wchar * 128),
                ("VendorId", ctypes.c_uint),
                ("DeviceId", ctypes.c_uint),
                ("SubSysId", ctypes.c_uint),
                ("Revision", ctypes.c_uint),
                ("DedicatedVideoMemory", ctypes.c_size_t),
                ("DedicatedSystemMemory", ctypes.c_size_t),
                ("SharedSystemMemory", ctypes.c_size_t),
                ("AdapterLuid", LUID),
                ("Flags", ctypes.c_uint)]


def enum_adapters():
    """Return [(index, name, vendor_id, luid, ded_vram, flags)]."""
    dxgi = ctypes.WinDLL("dxgi.dll")
    out = []
    fac = ctypes.c_void_p(0)
    hr = dxgi.CreateDXGIFactory1(IDXGIFactory1_IID, ctypes.byref(fac))
    if hr != 0:
        return out, "CreateDXGIFactory1 hr=0x%08X" % (hr & 0xFFFFFFFF)
    vt = ctypes.cast(fac, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    EnumAdapters1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                       ctypes.c_uint,
                                       ctypes.POINTER(ctypes.c_void_p))(vt[12])
    i = 0
    while True:
        ad = ctypes.c_void_p(0)
        hr = EnumAdapters1(fac, i, ctypes.byref(ad))
        if hr != 0 or not ad.value:
            break
        avt = ctypes.cast(ad, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
        GetDesc1 = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                      ctypes.POINTER(DXGI_ADAPTER_DESC1))(avt[10])
        d = DXGI_ADAPTER_DESC1()
        GetDesc1(ad, ctypes.byref(d))
        out.append(dict(index=i, name=d.Description, vendor="0x%04X" % d.VendorId,
                        luid=(d.AdapterLuid.HighPart & 0xFFFFFFFF) << 32 |
                             d.AdapterLuid.LowPart,
                        dedicated_vram_bytes=d.DedicatedVideoMemory,
                        flags=d.Flags,
                        _ptr=ad))
        i += 1
    return out, None


def make_d3d11_device(adapter=None):
    d3d11 = ctypes.WinDLL("d3d11.dll")
    fn = d3d11.D3D11CreateDevice
    fn.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                   ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint,
                   ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p),
                   ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_void_p)]
    fn.restype = ctypes.c_long
    D3D_DRIVER_TYPE_UNKNOWN = 0
    D3D_DRIVER_TYPE_HARDWARE = 1
    D3D11_SDK_VERSION = 7
    D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
    D3D11_CREATE_DEVICE_VIDEO_SUPPORT = 0x800
    flags = D3D11_CREATE_DEVICE_BGRA_SUPPORT | D3D11_CREATE_DEVICE_VIDEO_SUPPORT
    dev = ctypes.c_void_p(0)
    feat = ctypes.c_uint(0)
    ctx = ctypes.c_void_p(0)
    if adapter is None:
        driver_type, adapter_arg = D3D_DRIVER_TYPE_HARDWARE, None
    else:
        # an explicit IDXGIAdapter requires D3D_DRIVER_TYPE_UNKNOWN
        driver_type, adapter_arg = D3D_DRIVER_TYPE_UNKNOWN, ctypes.c_void_p(adapter)
    hr = fn(adapter_arg, driver_type, None, flags,
            None, 0, D3D11_SDK_VERSION, ctypes.byref(dev), ctypes.byref(feat),
            ctypes.byref(ctx))
    if hr == 0 and dev.value:
        # NVENC samples require multithread protection on the D3D11 device.
        try:
            qi = ctypes.cast(dev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
            QueryInterface = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p))(qi[0])
            mt = ctypes.c_void_p(0)
            hrmt = QueryInterface(dev, MULTITHREAD_IID, ctypes.byref(mt))
            if hrmt == 0 and mt.value:
                mvt = ctypes.cast(mt, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
                SetMT = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p,
                                           ctypes.c_int)(mvt[9])
                SetMT(mt, 1)
        except Exception:  # noqa: BLE001
            pass
    return hr, dev, feat.value, ctx, d3d11


def main():
    verbose = "--verbose" in sys.argv

    def step(msg):
        if verbose:
            print("STEP %s" % msg, file=sys.stderr, flush=True)

    step("start")
    out = {"probe": "nvenc-caps-probe.py", "source_header": "nvEncodeAPI.h 13.1"}
    dll = ctypes.WinDLL("nvEncodeAPI64.dll")

    v = ctypes.c_uint32(0)
    fn = dll.NvEncodeAPIGetMaxSupportedVersion
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint32)]
    fn.restype = ctypes.c_int
    st = fn(ctypes.byref(v))
    out["driver_nvenc_api"] = {"status": st, "raw": "0x%08X" % v.value,
                               "version": "%d.%d" % (v.value >> 4, v.value & 0xF)}

    create = dll.NvEncodeAPICreateInstance
    create.argtypes = [ctypes.c_void_p]
    create.restype = ctypes.c_int
    RAW = (ctypes.c_void_p * 512)()
    RAW[0] = NV_ENCODE_API_FUNCTION_LIST_VER
    st = create(ctypes.byref(RAW))
    out["NvEncodeAPICreateInstance_status"] = st
    if st != NV_ENC_SUCCESS:
        out["result"] = "ABORT: NvEncodeAPICreateInstance failed"
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    funcs = RAW   # RAW[0]=version, RAW[1]=reserved, RAW[n]=nth function pointer
    step("table non-null slots=%d" % sum(1 for i in range(2, 120) if funcs[i]))

    def slot_proto(idx, argtypes):
        addr = funcs[idx]
        assert addr, "NVENC function table slot %d is NULL" % idx
        return ctypes.WINFUNCTYPE(ctypes.c_int, *argtypes)(addr)

    GetEncodeCaps = slot_proto(SLOT_GET_ENCODE_CAPS,
                               [ctypes.c_void_p, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.c_void_p])
    OpenEx = slot_proto(SLOT_OPEN_SESSION_EX,
                        [ctypes.POINTER(NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS),
                         ctypes.POINTER(ctypes.c_void_p)])
    DestroyEncoder = slot_proto(SLOT_DESTROY_ENCODER, [ctypes.c_void_p])
    GetLastErr = ctypes.WINFUNCTYPE(ctypes.c_char_p, ctypes.c_void_p)(
        funcs[SLOT_GET_LAST_ERROR]) if funcs[SLOT_GET_LAST_ERROR] else None

    step("create-instance ok")
    mode = "cuda"
    if "--directx" in sys.argv:
        mode = "directx"
    out["sessions"] = {}
    if mode == "directx":
        hr, dev, feat, ctx, _d3d11 = make_d3d11_device()
        step("d3d11 hr=%s feat=0x%X" % (hr, feat))
        device_ptr = dev.value
        dev_type = NV_ENC_DEVICE_TYPE_DIRECTX
    else:
        # CUDA path: the driver wants the CUDA CONTEXT handle, not the ordinal
        # (ProgGuide 3.1.1.5: "pass the CUDA context handle as
        # NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS::device").
        dev_type = NV_ENC_DEVICE_TYPE_CUDA
        cuda = ctypes.WinDLL("nvcuda.dll")
        cuda.cuInit.argtypes = [ctypes.c_uint]
        cuda.cuInit.restype = ctypes.c_int
        out["cuInit"] = cuda.cuInit(0)
        dev = ctypes.c_int(0)
        cuda.cuDeviceGet.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        cuda.cuDeviceGet.restype = ctypes.c_int
        out["cuDeviceGet"] = cuda.cuDeviceGet(ctypes.byref(dev), 0)
        ctx_ptr = ctypes.c_void_p(0)
        cuda.cuCtxGetCurrent.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        cuda.cuCtxGetCurrent.restype = ctypes.c_int
        rc = cuda.cuCtxGetCurrent(ctypes.byref(ctx_ptr))
        if not ctx_ptr.value:
            cuda.cuCtxCreate_v2.argtypes = [ctypes.POINTER(ctypes.c_void_p),
                                            ctypes.c_uint, ctypes.c_int]
            cuda.cuCtxCreate_v2.restype = ctypes.c_int
            rc = cuda.cuCtxCreate_v2(ctypes.byref(ctx_ptr), 0, dev.value)
            out["cuCtxCreate_v2"] = rc
        else:
            out["cuCtxGetCurrent_rc"] = rc
        out["cu_context_handle_nonzero"] = bool(ctx_ptr.value)
        device_ptr = ctx_ptr.value
        step("CUDA driver context handle=%s" % device_ptr)
    out["device_mode"] = mode
    out["gpu_encoder_handle_probe"] = {"device_type": dev_type, "device_ptr": device_ptr}
    if mode == "directx":
        out["d3d11_device"] = {"hr": hr, "feature_level": "0x%X" % feat,
                               "device_ptr_nonzero": bool(dev.value)}
        if hr != 0 or not dev.value:
            out["result"] = "ABORT: D3D11CreateDevice failed"
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

    def open_session(device_type, device_ptr):
        p = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS()
        ctypes.memset(ctypes.byref(p), 0, ctypes.sizeof(p))
        p.version = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER
        p.deviceType = device_type
        p.device = ctypes.c_void_p(device_ptr) if device_ptr else None
        p.apiVersion = NVENCAPI_VERSION
        h = ctypes.c_void_p(0)
        return OpenEx(ctypes.byref(p), ctypes.byref(h)), h

    def query_caps(device_type, device_ptr):
        """Open one session, query every cap, close it. Returns a record."""
        st, handle = open_session(device_type, device_ptr)
        rec = {"open_status": st}
        if st != NV_ENC_SUCCESS or not handle.value:
            if handle.value:
                rec["last_error"] = (GetLastErr(handle).decode("utf-8", "replace")
                                     if GetLastErr else None)
            return rec, False
        caps = {}
        for capname, capid in CAPS.items():
            cp = NV_ENC_CAPS_PARAM()
            ctypes.memset(ctypes.byref(cp), 0, ctypes.sizeof(cp))
            cp.version = NV_ENC_CAPS_PARAM_VER
            cp.capsToQuery = capid
            val = ctypes.c_int(-1)
            s2 = GetEncodeCaps(handle, ctypes.byref(CODEC_GUIDS["H264"]),
                               ctypes.byref(cp), ctypes.byref(val))
            caps[capname] = dict(status=s2, value=val.value)
        rec["caps_H264"] = caps
        rec["destroy_status"] = DestroyEncoder(handle)
        return rec, True

    def report(codec, device_type, device_ptr):
        st, handle = open_session(device_type, device_ptr)
        step("open %s -> %d ptr=%s" % (codec, st, bool(handle.value)))
        rec = {"open_status": st}
        if st != NV_ENC_SUCCESS or not handle.value:
            out["sessions"][codec] = rec
            return False
        caps = {}
        for capname, capid in CAPS.items():
            cp = NV_ENC_CAPS_PARAM()
            ctypes.memset(ctypes.byref(cp), 0, ctypes.sizeof(cp))
            cp.version = NV_ENC_CAPS_PARAM_VER
            cp.capsToQuery = capid
            val = ctypes.c_int(-1)
            s2 = GetEncodeCaps(handle, ctypes.byref(CODEC_GUIDS[codec][0]),
                               ctypes.byref(cp), ctypes.byref(val))
            caps[capname] = dict(status=s2, value=val.value)
        rec["caps"] = caps
        rec["destroy_status"] = DestroyEncoder(handle)
        out["sessions"][codec] = rec
        return True

    # Probe every DXGI adapter for a device NVENC will actually accept. On a
    # hybrid laptop/desktop (Intel iGPU + NVIDIA dGPU) the default adapter is
    # NOT necessarily the NVIDIA one, and NVENC answers
    # NV_ENC_ERR_INVALID_DEVICE (5) for a device it does not own.
    adapters, enum_err = enum_adapters()
    out["dxgi_adapters"] = [{k: v for k, v in a.items() if k != "_ptr"}
                            for a in adapters]
    if enum_err:
        out["dxgi_enum_error"] = enum_err

    working = None
    if mode == "directx":
        out["adapter_session_probe"] = []
        for a in adapters:
            hr2, dev2, feat2, ctx2, _ = make_d3d11_device(a["_ptr"].value)
            entry = {"adapter": a["index"], "name": a["name"],
                     "d3d11_hr": hr2, "feature_level": "0x%X" % feat2}
            if hr2 == 0 and dev2.value:
                rec, ok = query_caps(NV_ENC_DEVICE_TYPE_DIRECTX, dev2.value)
                entry["nvenc_open_status"] = rec["open_status"]
                if ok:
                    working = (dev2, feat2, a)
                    out["sessions"]["H264"] = rec
            out["adapter_session_probe"].append(entry)
            if working:
                break
        if working:
            dev2, feat2, a = working
            out["nvenc_device"] = {"adapter_index": a["index"], "adapter_name": a["name"],
                                   "feature_level": "0x%X" % feat2}
            for codec in ("HEVC", "AV1"):
                report(codec, NV_ENC_DEVICE_TYPE_DIRECTX, dev2.value)
            dev_type, device_ptr = NV_ENC_DEVICE_TYPE_DIRECTX, dev2.value
        else:
            out["result"] = "NO-ADAPTER-ACCEPTED-BY-NVENC"
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
    else:
        for codec in CODEC_GUIDS:
            report(codec, dev_type, device_ptr)

    # How many concurrent sessions on THIS GPU before the driver refuses?
    out["concurrent_session_probe"] = []
    held = []
    try:
        for i in range(12):
            st, handle = open_session(dev_type, device_ptr)
            out["concurrent_session_probe"].append({"n": i + 1, "status": st})
            if st != NV_ENC_SUCCESS or not handle.value:
                break
            held.append(handle)
    finally:
        for h in held:
            DestroyEncoder(h)
    out["result"] = "OK"
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
