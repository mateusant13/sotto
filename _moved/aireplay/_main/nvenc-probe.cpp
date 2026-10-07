// nvenc-probe.cpp — Section 03: settle the NVENC session question on THIS box, in C++,
// against REAL SDK headers (not ctypes, not hand-stubbed structs).
//
// The capture lane measured: NvEncodeAPICreateInstance = 0, then EVERY
// NvEncOpenEncodeSessionEx returns status 5, with a real CUDA context and with an
// ID3D11Device on adapter 0 (RTX 5080) and adapter 1 (UHD 770).  So the encoder
// engine count and the driver's refusal point were UNKNOWN.
//
// This probe reports RAW status codes for every arm, including failures, so the
// question is settled by data rather than by reading.
//
//      1. driver/API version handshake (0xD1 => driver speaks API 13.1)
//      2. a real D3D11 device on the NVIDIA adapter, plus the default-adapter control
//      3. CUDA arm        — DEVICE_TYPE_CUDA + a real cuCtxCreate_v2 context
//      4. DIRECTX arm     — DEVICE_TYPE_DIRECTX + ID3D11Device on vendor 0x10DE
//      5. VERSION arms    — the status-5 hypothesis, one variable changed per arm
//      6. one session, INITIALISED (the capture lane never got this far)
//      6a. what the driver itself offers (needs only an OPEN session)
//      6c. incremental INIT self-test: which config actually initialises?
//      7. capabilities per codec: NUM_ENCODER_ENGINES, WIDTH_MAX, HEIGHT_MAX, ...
//      8. concurrent sessions until the driver refuses, each released
//      9. cleanup audit — nothing left held
//
// Build (MSYS2 mingw64 g++; there is no MSVC and no CUDA toolkit on this box):
//   H:\msys64\mingw64\bin\g++.exe -std=c++17 -O1 ^
//     -I H:\aireplay\_main\sdkref H:\aireplay\_main\nvenc-probe.cpp ^
//     -o H:\aireplay\_main\build\nvenc-probe.exe -ldxgi -ld3d11 -luuid
//
// nvEncodeAPI64.dll and nvcuda.dll are bound at RUN TIME with LoadLibraryW +
// GetProcAddress.  They are deliberately NOT linked: putting a -L on
// C:\Windows\System32 makes ld pick up MSVC's msvcrt import library, which collides
// with mingw's UCRT and dies in a wall of __acrt_iob_func errors (measured).

#define UNICODE
#define _UNICODE

#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <psapi.h>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdarg>
#include <ctime>

#include "nvEncodeAPI.h"

// ---------------------------------------------------------------- CUDA driver API
// Hand-declared driver-API prototypes.  The CUDA toolkit is NOT installed here, so
// there is no cuda.h to include; these are stable ABI since CUDA 1.0 and are resolved
// from nvcuda.dll at run time.  Nothing about nvEncodeAPI.h is stubbed.
typedef int (*PFN_cuInit)(unsigned);
typedef int (*PFN_cuDeviceGet)(int *, int);
typedef int (*PFN_cuCtxCreate_v2)(void **, unsigned, int);
typedef int (*PFN_cuCtxDestroy_v2)(void *);
typedef int CUdevice;   // ABI: CUdevice is `int` (CUDA 1.0 .. present)

// --------------------------------------------------------------------- logging
static void line(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    char buf[4096];
    _vsnprintf_s(buf, sizeof(buf), _TRUNCATE, fmt, ap);
    va_end(ap);
    fputs(buf, stdout);
    fputs("\n", stdout);
    fflush(stdout);
}

static const char *st(NVENCSTATUS s, char *buf, size_t n)
{
    const char *name = "?";
    switch (s) {
    case NV_ENC_SUCCESS:                     name = "NV_ENC_SUCCESS"; break;
    case NV_ENC_ERR_NO_ENCODE_DEVICE:        name = "NV_ENC_ERR_NO_ENCODE_DEVICE"; break;
    case NV_ENC_ERR_UNSUPPORTED_DEVICE:      name = "NV_ENC_ERR_UNSUPPORTED_DEVICE"; break;
    case NV_ENC_ERR_INVALID_ENCODERDEVICE:   name = "NV_ENC_ERR_INVALID_ENCODERDEVICE"; break;
    case NV_ENC_ERR_INVALID_DEVICE:          name = "NV_ENC_ERR_INVALID_DEVICE"; break;
    case NV_ENC_ERR_DEVICE_NOT_EXIST:        name = "NV_ENC_ERR_DEVICE_NOT_EXIST"; break;
    case NV_ENC_ERR_INVALID_PTR:             name = "NV_ENC_ERR_INVALID_PTR"; break;
    case NV_ENC_ERR_INVALID_EVENT:           name = "NV_ENC_ERR_INVALID_EVENT"; break;
    case NV_ENC_ERR_INVALID_PARAM:           name = "NV_ENC_ERR_INVALID_PARAM"; break;
    case NV_ENC_ERR_INVALID_CALL:            name = "NV_ENC_ERR_INVALID_CALL"; break;
    case NV_ENC_ERR_OUT_OF_MEMORY:           name = "NV_ENC_ERR_OUT_OF_MEMORY"; break;
    case NV_ENC_ERR_ENCODER_NOT_INITIALIZED: name = "NV_ENC_ERR_ENCODER_NOT_INITIALIZED"; break;
    case NV_ENC_ERR_UNSUPPORTED_PARAM:       name = "NV_ENC_ERR_UNSUPPORTED_PARAM"; break;
    case NV_ENC_ERR_LOCK_BUSY:               name = "NV_ENC_ERR_LOCK_BUSY"; break;
    case NV_ENC_ERR_NOT_ENOUGH_BUFFER:       name = "NV_ENC_ERR_NOT_ENOUGH_BUFFER"; break;
    case NV_ENC_ERR_INVALID_VERSION:         name = "NV_ENC_ERR_INVALID_VERSION"; break;
    case NV_ENC_ERR_MAP_FAILED:              name = "NV_ENC_ERR_MAP_FAILED"; break;
    case NV_ENC_ERR_NEED_MORE_INPUT:         name = "NV_ENC_ERR_NEED_MORE_INPUT"; break;
    case NV_ENC_ERR_ENCODER_BUSY:            name = "NV_ENC_ERR_ENCODER_BUSY"; break;
    case NV_ENC_ERR_EVENT_NOT_REGISTERD:     name = "NV_ENC_ERR_EVENT_NOT_REGISTERD"; break;
    case NV_ENC_ERR_GENERIC:                 name = "NV_ENC_ERR_GENERIC"; break;
    case NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY: name = "NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY"; break;
    case NV_ENC_ERR_UNIMPLEMENTED:           name = "NV_ENC_ERR_UNIMPLEMENTED"; break;
    case NV_ENC_ERR_RESOURCE_REGISTER_FAILED:name = "NV_ENC_ERR_RESOURCE_REGISTER_FAILED"; break;
    case NV_ENC_ERR_RESOURCE_NOT_REGISTERED: name = "NV_ENC_ERR_RESOURCE_NOT_REGISTERED"; break;
    case NV_ENC_ERR_RESOURCE_NOT_MAPPED:     name = "NV_ENC_ERR_RESOURCE_NOT_MAPPED"; break;
    default: break;
    }
    _snprintf_s(buf, n, _TRUNCATE, "%d (%s)", (int)s, name);
    return buf;
}

// ------------------------------------------------------------------ NVENC binding
struct NvApi {
    NV_ENCODE_API_FUNCTION_LIST L;
    bool ok = false;
    const char *failed_at = "";
};

static bool load_table(HMODULE dll, NvApi *api)
{
    typedef NVENCSTATUS (NVENCAPI *PFN_CreateInstance)(NV_ENCODE_API_FUNCTION_LIST *);
    PFN_CreateInstance createInstance =
        (PFN_CreateInstance)(void *)GetProcAddress(dll, "NvEncodeAPICreateInstance");
    if (!createInstance) { api->failed_at = "NvEncodeAPICreateInstance export missing"; return false; }
    memset(&api->L, 0, sizeof(api->L));
    api->L.version = NV_ENCODE_API_FUNCTION_LIST_VER;
    NVENCSTATUS s = createInstance(&api->L);
    if (s != NV_ENC_SUCCESS) { api->failed_at = "NvEncodeAPICreateInstance returned non-zero"; return false; }
    api->ok = true;
    return true;
}

static int count_nonnull(const NV_ENCODE_API_FUNCTION_LIST &L)
{
    const void *ptrs[40] = {
        (const void *)L.nvEncOpenEncodeSession, (const void *)L.nvEncGetEncodeGUIDCount,
        (const void *)L.nvEncGetEncodeProfileGUIDCount, (const void *)L.nvEncGetEncodeProfileGUIDs,
        (const void *)L.nvEncGetEncodeGUIDs, (const void *)L.nvEncGetInputFormatCount,
        (const void *)L.nvEncGetInputFormats, (const void *)L.nvEncGetEncodeCaps,
        (const void *)L.nvEncGetEncodePresetCount, (const void *)L.nvEncGetEncodePresetGUIDs,
        (const void *)L.nvEncGetEncodePresetConfig, (const void *)L.nvEncInitializeEncoder,
        (const void *)L.nvEncCreateInputBuffer, (const void *)L.nvEncDestroyInputBuffer,
        (const void *)L.nvEncCreateBitstreamBuffer, (const void *)L.nvEncDestroyBitstreamBuffer,
        (const void *)L.nvEncEncodePicture, (const void *)L.nvEncLockBitstream,
        (const void *)L.nvEncUnlockBitstream, (const void *)L.nvEncLockInputBuffer,
        (const void *)L.nvEncUnlockInputBuffer, (const void *)L.nvEncGetEncodeStats,
        (const void *)L.nvEncGetSequenceParams, (const void *)L.nvEncRegisterAsyncEvent,
        (const void *)L.nvEncUnregisterAsyncEvent, (const void *)L.nvEncMapInputResource,
        (const void *)L.nvEncUnmapInputResource, (const void *)L.nvEncDestroyEncoder,
        (const void *)L.nvEncInvalidateRefFrames, (const void *)L.nvEncOpenEncodeSessionEx,
        (const void *)L.nvEncRegisterResource, (const void *)L.nvEncUnregisterResource,
        (const void *)L.nvEncReconfigureEncoder, (const void *)L.nvEncCreateMVBuffer,
        (const void *)L.nvEncDestroyMVBuffer, (const void *)L.nvEncRunMotionEstimationOnly,
        (const void *)L.nvEncGetLastErrorString, (const void *)L.nvEncSetIOCudaStreams,
        (const void *)L.nvEncGetEncodePresetConfigEx, (const void *)L.nvEncGetSequenceParamEx
    };
    int nn = 0;
    for (int i = 0; i < 40; ++i) if (ptrs[i]) ++nn;
    return nn;
}

// ---------------------------------------------------------- real D3D11 on NVIDIA
struct Dx {
    IDXGIAdapter1 *adapter = nullptr;
    ID3D11Device  *dev     = nullptr;
    UINT           vendor  = 0;
    char           name[128] = "?";
};

static IDXGIFactory1 *g_factory = nullptr;

static void dump_adapters()
{
    line("");
    line("--- DXGI adapters (all) ---");
    IDXGIFactory1 *f = nullptr;
    if (FAILED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void **)&f))) { line("  CreateDXGIFactory1 FAILED"); return; }
    IDXGIAdapter1 *a = nullptr;
    for (UINT i = 0; i < 16 && f->EnumAdapters1(i, &a) != DXGI_ERROR_NOT_FOUND; ++i) {
        DXGI_ADAPTER_DESC1 d;
        memset(&d, 0, sizeof(d));
        a->GetDesc1(&d);
        char nm[128];
        WideCharToMultiByte(CP_UTF8, 0, d.Description, -1, nm, sizeof(nm), nullptr, nullptr);
        line("  idx=%u vendor=0x%04X device=0x%04X vram=%lluMB flags=0x%X name=%s",
             i, (unsigned)d.VendorId, (unsigned)d.DeviceId,
             (unsigned long long)(d.DedicatedVideoMemory >> 20), (unsigned)d.Flags, nm);
        a->Release();
    }
    f->Release();
}

static bool make_d3d11_on_vendor(UINT want_vendor, Dx *out, DWORD *out_hr, int *out_level)
{
    *out_hr = (DWORD)-1;
    *out_level = -1;
    if (!g_factory && FAILED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void **)&g_factory))) return false;
    IDXGIAdapter1 *a = nullptr;
    for (UINT i = 0; i < 16 && g_factory->EnumAdapters1(i, &a) != DXGI_ERROR_NOT_FOUND; ++i) {
        DXGI_ADAPTER_DESC1 d;
        memset(&d, 0, sizeof(d));
        a->GetDesc1(&d);
        if (d.VendorId == want_vendor) {
            D3D_FEATURE_LEVEL got = (D3D_FEATURE_LEVEL)0;
            HRESULT hr = D3D11CreateDevice(a, D3D_DRIVER_TYPE_UNKNOWN, nullptr, 0,
                                           nullptr, 0, D3D11_SDK_VERSION,
                                           &out->dev, &got, nullptr);
            char nm[128];
            WideCharToMultiByte(CP_UTF8, 0, d.Description, -1, nm, sizeof(nm), nullptr, nullptr);
            strncpy_s(out->name, sizeof(out->name), nm, _TRUNCATE);
            out->adapter = a;
            out->vendor  = d.VendorId;
            *out_hr = (DWORD)hr;
            *out_level = (int)got;
            if (SUCCEEDED(hr)) return true;
            a->Release();
            out->adapter = nullptr;
            return false;
        }
        a->Release();
    }
    return false;
}

// -------------------------------------------------------------------------- main
int main()
{
    char b1[96], b2[96];
    line("================================================================================");
    line("nvEncodeAPI probe — raw status codes, MEASURED on this box");
    line("================================================================================");

    __time64_t now; _time64(&now);
    char ts[64]; struct tm tmv;
    _localtime64_s(&tmv, &now);
    strftime(ts, sizeof(ts), "%Y-%m-%d %H:%M:%S", &tmv);
    line("timestamp      : %s (local)", ts);
    line("source header  : nvEncodeAPI.h %d.%d  sha256 8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228",
         NVENCAPI_MAJOR_VERSION, NVENCAPI_MINOR_VERSION);
    line("               : byte-identical to FFmpeg/nv-codec-headers master eddcea9e27f6b772057c9b3f87de2cc1737faffc");
    line("               : official NVIDIA Video Codec SDK NOT used (its download is behind a login)");
    line("compiler       : g++ %d.%d.%d %s", __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__, __VERSION__);
    line("struct sizes   : SESSION_EX_PARAMS=%zu  INITIALIZE_PARAMS=%zu  CONFIG=%zu",
         sizeof(NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS), sizeof(NV_ENC_INITIALIZE_PARAMS), sizeof(NV_ENC_CONFIG));
    line("versions       : NVENCAPI_VERSION=0x%08X  SESSION_EX_VER=0x%08X  FUNCTION_LIST_VER=0x%08X",
         (unsigned)NVENCAPI_VERSION, (unsigned)NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER,
         (unsigned)NV_ENCODE_API_FUNCTION_LIST_VER);
    line("device types   : DIRECTX=%d  CUDA=%d", (int)NV_ENC_DEVICE_TYPE_DIRECTX, (int)NV_ENC_DEVICE_TYPE_CUDA);
    line("error codes    : OUT_OF_MEMORY=%d  INVALID_VERSION=%d  INVALID_DEVICE=%d  INVALID_PARAM=%d  INVALID_PTR=%d  INCOMPATIBLE_CLIENT_KEY=%d",
         (int)NV_ENC_ERR_OUT_OF_MEMORY, (int)NV_ENC_ERR_INVALID_VERSION, (int)NV_ENC_ERR_INVALID_DEVICE,
         (int)NV_ENC_ERR_INVALID_PARAM, (int)NV_ENC_ERR_INVALID_PTR, (int)NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY);

    // GPU context: this box is shared with the owner's other projects, so a session
    // measurement is only meaningful next to what was already running.
    line("");
    line("--- 0. GPU / machine context (so a session count is not read in a vacuum) -----");
    {
        MEMORYSTATUSEX ms; memset(&ms, 0, sizeof(ms)); ms.dwLength = sizeof(ms);
        if (GlobalMemoryStatusEx(&ms))
            line("  physical RAM   : %llu MiB total, %llu MiB available", ms.ullTotalPhys >> 20, ms.ullAvailPhys >> 20);
        char exe[MAX_PATH]; GetModuleFileNameA(nullptr, exe, MAX_PATH);
        line("  probe exe      : %s", exe);
        HANDLE me = GetCurrentProcess(); PROCESS_MEMORY_COUNTERS pmc;
        if (GetProcessMemoryInfo(me, &pmc, sizeof(pmc)))
            line("  probe peak WS  : %llu MiB", (unsigned long long)(pmc.PeakWorkingSetSize >> 20));
        int others = 0;
        DWORD pids[1024], needed = 0;
        if (EnumProcesses(pids, sizeof(pids), &needed)) {
            for (unsigned i = 0; i < needed / sizeof(DWORD); ++i) {
                if (!pids[i] || pids[i] == GetCurrentProcessId()) continue;
                HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pids[i]);
                if (!h) continue;
                char pn[512]; DWORD sz = sizeof(pn);
                if (QueryFullProcessImageNameA(h, 0, pn, &sz)) {
                    if (strstr(pn, "nvcontainer") || strstr(pn, "NVIDIA Broadcast") ||
                        strstr(pn, "NVIDIA Overlay") || strstr(pn, "ShareX"))
                        line("  nvidia-adjacent process: pid=%lu %s", pids[i], pn);
                }
                CloseHandle(h);
                if (++others > 900) break;
            }
        }
        line("  note: which of those holds the pre-existing NVENC session is NOT proven here;");
        line("        nvidia-smi reports only the COUNT (1 before this probe ran).");
    }

    // --------------------------------------------------------------- 1. handshake
    line("");
    line("--- 1. driver/API version handshake -------------------------------------------");
    HMODULE hlib = LoadLibraryW(L"nvEncodeAPI64.dll");
    if (!hlib) { line("LoadLibrary(nvEncodeAPI64.dll) FAILED err=%lu", GetLastError()); return 2; }
    char dll[MAX_PATH]; GetModuleFileNameA(hlib, dll, MAX_PATH);
    line("dll            : %s", dll);

    typedef NVENCSTATUS (NVENCAPI *PFN_GetMaxVer)(uint32_t *);
    PFN_GetMaxVer getMax = (PFN_GetMaxVer)(void *)GetProcAddress(hlib, "NvEncodeAPIGetMaxSupportedVersion");
    if (!getMax) { line("NvEncodeAPIGetMaxSupportedVersion export MISSING"); return 2; }
    uint32_t driverApi = 0;
    NVENCSTATUS s = getMax(&driverApi);
    line("NvEncodeAPIGetMaxSupportedVersion -> status=%s  driverApi=0x%08X (major=%u minor=%u)",
         st(s, b1, sizeof(b1)), driverApi, driverApi >> 24, driverApi & 0xFF);

    NvApi api;
    if (!load_table(hlib, &api)) { line("table load FAILED: %s", api.failed_at); return 2; }
    line("NvEncodeAPICreateInstance(version=0x%08X) -> NV_ENC_SUCCESS", (unsigned)NV_ENCODE_API_FUNCTION_LIST_VER);
    line("function table : %d of 40 named slots non-null; reserved1=%s reserved2[0]=%s",
         count_nonnull(api.L),
         api.L.reserved1 ? "NON-NULL(unexpected)" : "null-as-documented",
         api.L.reserved2[0] ? "NON-NULL(unexpected)" : "null-as-documented");
    if (!api.L.nvEncOpenEncodeSessionEx || !api.L.nvEncDestroyEncoder) { line("ESSENTIAL POINTERS NULL"); return 2; }

    auto note_last_error = [&](void *h, const char *tag) {
        if (!api.L.nvEncGetLastErrorString) { line("    %s lastErrorString: (entry point absent)", tag); return; }
        const char *m = api.L.nvEncGetLastErrorString(h);
        if (m && (unsigned char)m[0] >= 0x20 && (unsigned char)m[0] < 0x7F && m[0] != '0' && m[1] != '\0')
            line("    %s lastErrorString: %s", tag, m);
        else
            line("    %s lastErrorString: (non-printable/NULL/placeholder; not always set)", tag);
    };

    // ------------------------------------------------------------------ 2. devices
    dump_adapters();
    line("");
    line("--- 2. a real D3D11 device ON THE NVIDIA ADAPTER (not the default one) --------");
    Dx nv; DWORD hr = 0; int lvl = -1;
    bool have_nv = make_d3d11_on_vendor(0x10DE, &nv, &hr, &lvl);
    line("  D3D11CreateDevice(adapter = vendor 0x10DE, DRIVER_TYPE_UNKNOWN) ->");
    line("    hr=0x%08X  feature_level=0x%X  device=%p  name=%s",
         (unsigned)hr, (unsigned)lvl, (void *)nv.dev, nv.name);

    line("");
    line("--- 2b. CONTROL: D3D11CreateDevice(NULL, HARDWARE) — which adapter is that? ---");
    {
        ID3D11Device *dflt = nullptr; D3D_FEATURE_LEVEL got = (D3D_FEATURE_LEVEL)0;
        HRESULT h2 = D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0, nullptr, 0,
                                       D3D11_SDK_VERSION, &dflt, &got, nullptr);
        line("  hr=0x%08X feature_level=0x%X", (unsigned)h2, (unsigned)got);
        if (SUCCEEDED(h2)) {
            IDXGIDevice *dxdev = nullptr;
            if (SUCCEEDED(dflt->QueryInterface(__uuidof(IDXGIDevice), (void **)&dxdev))) {
                IDXGIAdapter *ad = nullptr;
                if (SUCCEEDED(dxdev->GetAdapter(&ad))) {
                    DXGI_ADAPTER_DESC d; memset(&d, 0, sizeof(d)); ad->GetDesc(&d);
                    char nm[128]; WideCharToMultiByte(CP_UTF8, 0, d.Description, -1, nm, sizeof(nm), nullptr, nullptr);
                    line("  -> the DEFAULT device really lives on: vendor=0x%04X name=%s", (unsigned)d.VendorId, nm);
                    ad->Release();
                }
                dxdev->Release();
            }
            dflt->Release();
        }
    }

    // ------------------------------------------------------------------ 3. CUDA arm
    line("");
    line("--- 3. CUDA arm --------------------------------------------------------------");
    HMODULE hcu = LoadLibraryW(L"nvcuda.dll");
    void *cu_ctx = nullptr;
    if (!hcu) {
        line("  LoadLibrary(nvcuda.dll) FAILED err=%lu", GetLastError());
    } else {
        PFN_cuInit         cuInit    = (PFN_cuInit)(void *)GetProcAddress(hcu, "cuInit");
        PFN_cuDeviceGet    cuDevGet  = (PFN_cuDeviceGet)(void *)GetProcAddress(hcu, "cuDeviceGet");
        PFN_cuCtxCreate_v2 cuCtxC    = (PFN_cuCtxCreate_v2)(void *)GetProcAddress(hcu, "cuCtxCreate_v2");
        line("  nvcuda exports : cuInit=%s cuDeviceGet=%s cuCtxCreate_v2=%s",
             cuInit ? "yes" : "NO", cuDevGet ? "yes" : "NO", cuCtxC ? "yes" : "NO");
        if (cuInit && cuDevGet && cuCtxC) {
            CUdevice devIndex = 0;
            int r_init = cuInit(0);
            int r_dev  = cuDevGet(&devIndex, 0);
            int r_ctx  = cuCtxC(&cu_ctx, 0, devIndex);
            line("  cuInit(0)        -> %d", r_init);
            line("  cuDeviceGet(0)   -> %d  (CUdevice=%d)", r_dev, (int)devIndex);
            line("  cuCtxCreate_v2   -> %d  (CUcontext=%p)", r_ctx, cu_ctx);
            if (r_ctx != 0) cu_ctx = nullptr;
        }
    }

    NvApi apic;
    line("  NvEncodeAPICreateInstance (fresh table for the CUDA arm) -> %s",
         load_table(hlib, &apic) ? "NV_ENC_SUCCESS" : apic.failed_at);

    line("");
    line("  ARM 2 — DEVICE_TYPE_CUDA, real CUDA context, header-correct version/apiVersion");
    if (cu_ctx && apic.ok && apic.L.nvEncOpenEncodeSessionEx) {
        NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
        memset(&p, 0, sizeof(p));
        p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
        p.deviceType = NV_ENC_DEVICE_TYPE_CUDA;
        p.device     = cu_ctx;
        p.apiVersion = NVENCAPI_VERSION;
        void *e = nullptr;
        NVENCSTATUS r = apic.L.nvEncOpenEncodeSessionEx(&p, &e);
        line("    sent version=0x%08X deviceType=%d device=%p apiVersion=0x%08X",
             (unsigned)p.version, (int)p.deviceType, p.device, (unsigned)p.apiVersion);
        line("    NvEncOpenEncodeSessionEx -> %s  encoder=%p", st(r, b1, sizeof(b1)), e);
        note_last_error(e, "CUDA arm:");
        if (r == NV_ENC_SUCCESS && e) line("    released -> %s", st(apic.L.nvEncDestroyEncoder(e), b2, sizeof(b2)));
    } else {
        line("    SKIPPED: no usable CUDA context — UNMEASURED, not passing");
    }

    NvApi apix;
    line("");
    line("--- 4. DIRECTX arm ------------------------------------------------------------");
    line("  NvEncodeAPICreateInstance (fresh table for the DIRECTX arm) -> %s",
         load_table(hlib, &apix) ? "NV_ENC_SUCCESS" : apix.failed_at);
    line("  ARM 3 — DEVICE_TYPE_DIRECTX, ID3D11Device on the NVIDIA adapter, header-correct");
    if (have_nv && apix.ok && apix.L.nvEncOpenEncodeSessionEx) {
        NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
        memset(&p, 0, sizeof(p));
        p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
        p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
        p.device     = nv.dev;
        p.apiVersion = NVENCAPI_VERSION;
        void *e = nullptr;
        NVENCSTATUS r = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
        line("    sent version=0x%08X deviceType=%d device=%p apiVersion=0x%08X",
             (unsigned)p.version, (int)p.deviceType, p.device, (unsigned)p.apiVersion);
        line("    NvEncOpenEncodeSessionEx -> %s  encoder=%p", st(r, b1, sizeof(b1)), e);
        note_last_error(e, "DX arm:");
        if (r == NV_ENC_SUCCESS && e) line("    released -> %s", st(apix.L.nvEncDestroyEncoder(e), b2, sizeof(b2)));
    } else {
        line("    SKIPPED: no NVIDIA D3D11 device");
    }

    // ------------------------------------------------------------- 5. version arms
    line("");
    line("--- 5. VERSION arms — the status-5 hypothesis, one variable at a time --------");
    {
        struct Arm { const char *label; uint32_t ver; uint32_t apiv; };
        const Arm arms[] = {
            { "ARM 4  version = header macro (CORRECT), but apiVersion = 0",   (uint32_t)NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER, 0u },
            { "ARM 5  version = 0 (field never filled), apiVersion correct",    0u, (uint32_t)NVENCAPI_VERSION },
            { "ARM 6  version = NVENCAPI_STRUCT_VERSION(99) (bogus struct ver)", (uint32_t)NVENCAPI_STRUCT_VERSION(99), (uint32_t)NVENCAPI_VERSION },
            { "ARM 7  apiVersion = 12.0 (older than driver 13.1)",              (uint32_t)NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER, 12u },
            { "ARM 8  apiVersion = 14.0 (newer than driver 13.1)",              (uint32_t)NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER, 14u },
        };
        for (int i = 0; i < 5; ++i) {
            line("");
            line("  %s", arms[i].label);
            if (!have_nv || !apix.ok || !apix.L.nvEncOpenEncodeSessionEx) { line("    SKIPPED"); continue; }
            NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
            memset(&p, 0, sizeof(p));
            p.version    = arms[i].ver;
            p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
            p.device     = nv.dev;
            p.apiVersion = arms[i].apiv;
            void *e = nullptr;
            NVENCSTATUS r = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
            line("    sent version=0x%08X apiVersion=0x%08X -> %s  encoder=%p",
                 (unsigned)p.version, (unsigned)p.apiVersion, st(r, b1, sizeof(b1)), e);
            if (r != NV_ENC_SUCCESS) note_last_error(e, "arm:");
            if (r == NV_ENC_SUCCESS && e) { apix.L.nvEncDestroyEncoder(e); line("    (released)"); }
        }
    }

    // ------------------------------------------------- 6. one session, initialised
    line("");
    line("--- 6. open ONE session and INITIALISE it (the capture lane never got here) ---");
    void *enc = nullptr;
    bool session_initialized = false;
    NVENCSTATUS s6 = NV_ENC_ERR_UNIMPLEMENTED;
    if (have_nv && apix.ok && apix.L.nvEncOpenEncodeSessionEx) {
        NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
        memset(&p, 0, sizeof(p));
        p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
        p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
        p.device     = nv.dev;
        p.apiVersion = NVENCAPI_VERSION;
        s6 = apix.L.nvEncOpenEncodeSessionEx(&p, &enc);
        line("  NvEncOpenEncodeSessionEx -> %s  (session=%p)", st(s6, b1, sizeof(b1)), enc);
    }
    if (s6 == NV_ENC_SUCCESS && enc) {
        // Tuning info: 0 is NV_ENC_TUNING_INFO_UNDEFINED, which the header itself calls
        // "Invalid value for encoding" — a plain memset(0) walks straight into it.
        NV_ENC_INITIALIZE_PARAMS ip;
        memset(&ip, 0, sizeof(ip));
        ip.version      = NV_ENC_INITIALIZE_PARAMS_VER;
        ip.encodeGUID   = NV_ENC_CODEC_H264_GUID;
        ip.presetGUID   = NV_ENC_PRESET_P3_GUID;
        ip.encodeWidth  = 1920;
        ip.encodeHeight = 1080;
        ip.darWidth     = 1920;
        ip.darHeight    = 1080;
        ip.frameRateNum = 60;
        ip.frameRateDen = 1;
        ip.enablePTD    = 1;
        ip.bufferFormat = NV_ENC_BUFFER_FORMAT_NV12;
        ip.tuningInfo   = NV_ENC_TUNING_INFO_LOW_LATENCY;
        NVENCSTATUS r = apix.L.nvEncInitializeEncoder(enc, &ip);
        line("  NvEncInitializeEncoder(H264 P3, 1920x1080, NV12, 60fps, tuning=LOW_LATENCY, no explicit config)");
        line("    -> %s", st(r, b1, sizeof(b1)));
        session_initialized = (r == NV_ENC_SUCCESS);
        if (r != NV_ENC_SUCCESS) note_last_error(enc, "initialize:");
    }
    line("  => encoder INITIALISED: %s", session_initialized ? "YES" : "NO");

    // -------------------------------------- 6a. what the driver offers (open session)
    line("");
    line("--- 6a. what the driver itself offers (needs only an OPEN session) -----------");
    if (!enc) {
        line("  SKIPPED: no session");
    } else {
        uint32_t n = 0, used = 0;
        line("  codec GUIDs:");
        if (apix.L.nvEncGetEncodeGUIDCount && apix.L.nvEncGetEncodeGUIDs &&
            apix.L.nvEncGetEncodeGUIDCount(enc, &n) == NV_ENC_SUCCESS) {
            line("    nvEncGetEncodeGUIDCount -> %u", n);
            if (n > 0 && n <= 16) {
                GUID g[16];
                if (apix.L.nvEncGetEncodeGUIDs(enc, g, 16, &used) == NV_ENC_SUCCESS) {
                    const GUID known[3] = { NV_ENC_CODEC_H264_GUID, NV_ENC_CODEC_HEVC_GUID, NV_ENC_CODEC_AV1_GUID };
                    const char *nm[3] = { "H.264", "HEVC", "AV1" };
                    for (uint32_t k = 0; k < used; ++k) {
                        const char *label = "(other)";
                        for (int q = 0; q < 3; ++q) if (!memcmp(&g[k], &known[q], sizeof(GUID))) label = nm[q];
                        line("      %08lX-%04X-%04X  <- %s", (unsigned long)g[k].Data1, g[k].Data2, g[k].Data3, label);
                    }
                }
            }
        }
        line("  INPUT BUFFER FORMATS the driver lists for H.264:");
        if (apix.L.nvEncGetInputFormatCount && apix.L.nvEncGetInputFormats) {
            uint32_t fc = 0;
            if (apix.L.nvEncGetInputFormatCount(enc, NV_ENC_CODEC_H264_GUID, &fc) == NV_ENC_SUCCESS) {
                line("    nvEncGetInputFormatCount -> %u", fc);
                if (fc > 0 && fc <= 32) {
                    NV_ENC_BUFFER_FORMAT fmts[32]; uint32_t fu = 0;
                    if (apix.L.nvEncGetInputFormats(enc, NV_ENC_CODEC_H264_GUID, fmts, 32, &fu) == NV_ENC_SUCCESS)
                        for (uint32_t k = 0; k < fu; ++k) line("      0x%08X", (unsigned)fmts[k]);
                }
            } else line("    nvEncGetInputFormatCount -> non-zero status");
        }
        line("  preset config the DRIVER defines for P3/H264/LOW_LATENCY:");
        if (apix.L.nvEncGetEncodePresetConfigEx) {
            NV_ENC_PRESET_CONFIG pc;
            memset(&pc, 0, sizeof(pc));
            pc.version = NV_ENC_PRESET_CONFIG_VER;
            pc.presetCfg.version = NV_ENC_CONFIG_VER;
            NVENCSTATUS r = apix.L.nvEncGetEncodePresetConfigEx(enc, NV_ENC_CODEC_H264_GUID,
                                NV_ENC_PRESET_P3_GUID, NV_ENC_TUNING_INFO_LOW_LATENCY, &pc);
            line("    status=%s  profileGUID=%08lX-%04X gopLength=%u frameIntervalP=%u",
                 st(r, b1, sizeof(b1)), (unsigned long)pc.presetCfg.profileGUID.Data1,
                 pc.presetCfg.profileGUID.Data2, pc.presetCfg.gopLength, pc.presetCfg.frameIntervalP);
            line("    rc.rateControlMode=0x%X rc.averageBitRate=%u",
                 (unsigned)pc.presetCfg.rcParams.rateControlMode, pc.presetCfg.rcParams.averageBitRate);
        }
    }

    // -------------------------------------------------- 6b. register a real texture
    line("");
    line("--- 6b. register a REAL D3D11 NV12 texture as an NVENC input resource --------");
    if (!(session_initialized && enc && have_nv)) {
        line("  SKIPPED: needs an INITIALISED session.  Measured earlier: on an opened-but-");
        line("  uninitialised session NvEncRegisterResource returns 5");
        line("  (NV_ENC_ERR_DEVICE_NOT_EXIST) — the SAME status 5 the capture lane saw on OPEN.");
        line("  That is why a bare status 5 is ambiguous unless session state is reported.");
    } else {
        ID3D11Texture2D *tex = nullptr;
        D3D11_TEXTURE2D_DESC td; memset(&td, 0, sizeof(td));
        td.Width = 1920; td.Height = 1080; td.MipLevels = 1; td.ArraySize = 1;
        td.Format = DXGI_FORMAT_NV12; td.SampleDesc.Count = 1;
        td.Usage = D3D11_USAGE_DEFAULT; td.BindFlags = D3D11_BIND_RENDER_TARGET;
        HRESULT h = nv.dev->CreateTexture2D(&td, nullptr, &tex);
        line("    CreateTexture2D(NV12 1920x1080) hr=0x%08X tex=%p", (unsigned)h, (void *)tex);
        if (SUCCEEDED(h) && tex && apix.L.nvEncRegisterResource) {
            NV_ENC_REGISTER_RESOURCE rr; memset(&rr, 0, sizeof(rr));
            rr.version            = NV_ENC_REGISTER_RESOURCE_VER;
            rr.resourceType       = NV_ENC_INPUT_RESOURCE_TYPE_DIRECTX;
            rr.width              = 1920;
            rr.height             = 1080;
            rr.resourceToRegister = tex;
            rr.bufferFormat       = NV_ENC_BUFFER_FORMAT_NV12;
            rr.bufferUsage        = NV_ENC_INPUT_IMAGE;
            NVENCSTATUS r2 = apix.L.nvEncRegisterResource(enc, &rr);
            line("    NvEncRegisterResource -> %s registeredPtr=%p", st(r2, b1, sizeof(b1)), rr.registeredResource);
            if (r2 == NV_ENC_SUCCESS && rr.registeredResource && apix.L.nvEncMapInputResource) {
                NV_ENC_MAP_INPUT_RESOURCE mr; memset(&mr, 0, sizeof(mr));
                mr.version            = NV_ENC_MAP_INPUT_RESOURCE_VER;
                mr.registeredResource = rr.registeredResource;
                NVENCSTATUS r3 = apix.L.nvEncMapInputResource(enc, &mr);
                line("    NvEncMapInputResource -> %s mappedPtr=%p", st(r3, b1, sizeof(b1)), mr.mappedResource);
                line("    => D3D11 texture -> NVENC zero-copy path %s",
                     r3 == NV_ENC_SUCCESS ? "COMPLETED on this box (no synthetic frames encoded)" : "did NOT complete");
                if (r3 == NV_ENC_SUCCESS && apix.L.nvEncUnmapInputResource) apix.L.nvEncUnmapInputResource(enc, mr.mappedResource);
            }
            if (apix.L.nvEncUnregisterResource) apix.L.nvEncUnregisterResource(enc, rr.registeredResource);
        }
        if (tex) tex->Release();
    }

    // ---------------------------------------- 6c. incremental init self-test sweep
    line("");
    line("--- 6c. incremental INIT self-test: which config actually initialises? --------");
    {
        auto try_init = [&](const char *what, NV_ENC_BUFFER_FORMAT fmt, NV_ENC_TUNING_INFO tuning,
                            bool withCfg, ID3D11Device *dev) -> NVENCSTATUS {
            NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
            memset(&p, 0, sizeof(p));
            p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
            p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
            p.device     = dev;
            p.apiVersion = NVENCAPI_VERSION;
            void *e = nullptr;
            NVENCSTATUS r = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
            if (r != NV_ENC_SUCCESS || !e) { line("  %-58s OPEN failed: %s", what, st(r, b2, sizeof(b2))); return r; }

            NV_ENC_CONFIG cfg;
            memset(&cfg, 0, sizeof(cfg));
            cfg.version        = NV_ENC_CONFIG_VER;
            cfg.profileGUID    = NV_ENC_H264_PROFILE_HIGH_GUID;
            cfg.gopLength      = 120;
            cfg.frameIntervalP = 1;
            cfg.rcParams.version         = NV_ENC_RC_PARAMS_VER;
            cfg.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CBR;
            cfg.rcParams.averageBitRate  = 40000000;
            cfg.rcParams.maxBitRate      = 40000000;
            cfg.rcParams.vbvBufferSize   = 40000000;
            cfg.rcParams.vbvInitialDelay = 40000000;

            NV_ENC_INITIALIZE_PARAMS ip;
            memset(&ip, 0, sizeof(ip));
            ip.version      = NV_ENC_INITIALIZE_PARAMS_VER;
            ip.encodeGUID   = NV_ENC_CODEC_H264_GUID;
            ip.presetGUID   = NV_ENC_PRESET_P3_GUID;
            ip.encodeWidth  = 1920;
            ip.encodeHeight = 1080;
            ip.darWidth     = 1920;
            ip.darHeight    = 1080;
            ip.frameRateNum = 60;
            ip.frameRateDen = 1;
            ip.enablePTD    = 1;
            ip.bufferFormat = fmt;
            ip.tuningInfo   = tuning;
            ip.encodeConfig = withCfg ? &cfg : nullptr;
            NVENCSTATUS r2 = apix.L.nvEncInitializeEncoder(e, &ip);
            line("  %-58s -> %s", what, st(r2, b2, sizeof(b2)));
            if (r2 != NV_ENC_SUCCESS && apix.L.nvEncGetLastErrorString) {
                const char *m = apix.L.nvEncGetLastErrorString(e);
                if (m && (unsigned char)m[0] >= 0x20 && (unsigned char)m[0] < 0x7F) line("        driver says: %s", m);
            }
            apix.L.nvEncDestroyEncoder(e);
            return r2;
        };

        if (!have_nv) {
            line("  SKIPPED: no NVIDIA device");
        } else {
            try_init("STEP 1  NV12 tuning=LOW_LATENCY   encodeConfig=NULL",
                     NV_ENC_BUFFER_FORMAT_NV12, NV_ENC_TUNING_INFO_LOW_LATENCY, false, nv.dev);
            try_init("STEP 2  NV12 tuning=LOW_LATENCY   encodeConfig=CBR 40Mbps",
                     NV_ENC_BUFFER_FORMAT_NV12, NV_ENC_TUNING_INFO_LOW_LATENCY, true, nv.dev);
            try_init("STEP 3  NV12 tuning=UNDEFINED(0)  encodeConfig=NULL",
                     NV_ENC_BUFFER_FORMAT_NV12, NV_ENC_TUNING_INFO_UNDEFINED, false, nv.dev);
            try_init("STEP 4  NV12 tuning=HIGH_QUALITY(1) encodeConfig=NULL",
                     NV_ENC_BUFFER_FORMAT_NV12, NV_ENC_TUNING_INFO_HIGH_QUALITY, false, nv.dev);
            line("");
            line("  BUFFER FORMAT sweep (fresh session each, minimal config):");
            struct F { const char *n; NV_ENC_BUFFER_FORMAT f; };
            const F fmts[] = {
                { "NV12",         NV_ENC_BUFFER_FORMAT_NV12 },
                { "IYUV",         NV_ENC_BUFFER_FORMAT_IYUV },
                { "YV12",         NV_ENC_BUFFER_FORMAT_YV12 },
                { "YUV444",       NV_ENC_BUFFER_FORMAT_YUV444 },
                { "YUV420_10BIT", NV_ENC_BUFFER_FORMAT_YUV420_10BIT },
                { "ARGB",         NV_ENC_BUFFER_FORMAT_ARGB },
                { "ABGR",         NV_ENC_BUFFER_FORMAT_ABGR },
            };
            for (int i = 0; i < 7; ++i) {
                char lbl[160];
                _snprintf_s(lbl, sizeof(lbl), _TRUNCATE, "STEP F  fmt=%-13s (0x%08X) tuning=LOW_LATENCY",
                            fmts[i].n, (unsigned)fmts[i].f);
                try_init(lbl, fmts[i].f, NV_ENC_TUNING_INFO_LOW_LATENCY, false, nv.dev);
            }
            line("");
            line("  => the first SUCCESS above is a config this box accepts.  If STEP 3 fails and");
            line("     STEP 1 passes, the failure is the UNDEFINED tuning value, not the format.");

            // STEP 2 failed with "Unsupported color format" although bufferFormat was a
            // legal NV12.  NV_ENC_CONFIG has NO bufferFormat field in this header, so the
            // driver's complaint has to be about one of the fields below.  Walk them one
            // at a time from the failing config down to a working one.
            line("");
            line("  FIELD ISOLATION for STEP 2 (from the failing config towards a working one):");
            struct CfgArm { const char *label; int level; };
            const CfgArm cfgArms[] = {
                { "level 0  encodeConfig=memset(0) + version only          ", 0 },
                { "level 1  + profileGUID = H264 PROFILE_HIGH              ", 1 },
                { "level 2  + gopLength = 120                              ", 2 },
                { "level 3  + frameIntervalP = 1                           ", 3 },
                { "level 4  + rcParams.version only                        ", 4 },
                { "level 5  + rc.rateControlMode = CBR                     ", 5 },
                { "level 6  + rc.averageBitRate / maxBitRate = 40Mbps      ", 6 },
                { "level 7  + rc.vbvBufferSize / vbvInitialDelay = 40Mbps  ", 7 },
            };
            for (int i = 0; i < 8; ++i) {
                NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
                memset(&p, 0, sizeof(p));
                p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
                p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
                p.device     = nv.dev;
                p.apiVersion = NVENCAPI_VERSION;
                void *e = nullptr;
                if (apix.L.nvEncOpenEncodeSessionEx(&p, &e) != NV_ENC_SUCCESS || !e) {
                    line("  %s -> OPEN failed", cfgArms[i].label); continue;
                }
                int L = cfgArms[i].level;
                NV_ENC_CONFIG cfg;
                memset(&cfg, 0, sizeof(cfg));
                cfg.version = NV_ENC_CONFIG_VER;
                if (L >= 1) cfg.profileGUID    = NV_ENC_H264_PROFILE_HIGH_GUID;
                if (L >= 2) cfg.gopLength      = 120;
                if (L >= 3) cfg.frameIntervalP = 1;
                if (L >= 4) cfg.rcParams.version = NV_ENC_RC_PARAMS_VER;
                if (L >= 5) cfg.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CBR;
                if (L >= 6) { cfg.rcParams.averageBitRate = 40000000; cfg.rcParams.maxBitRate = 40000000; }
                if (L >= 7) { cfg.rcParams.vbvBufferSize = 40000000; cfg.rcParams.vbvInitialDelay = 40000000; }

                NV_ENC_INITIALIZE_PARAMS ip;
                memset(&ip, 0, sizeof(ip));
                ip.version      = NV_ENC_INITIALIZE_PARAMS_VER;
                ip.encodeGUID   = NV_ENC_CODEC_H264_GUID;
                ip.presetGUID   = NV_ENC_PRESET_P3_GUID;
                ip.encodeWidth  = 1920;
                ip.encodeHeight = 1080;
                ip.darWidth     = 1920;
                ip.darHeight    = 1080;
                ip.frameRateNum = 60;
                ip.frameRateDen = 1;
                ip.enablePTD    = 1;
                ip.bufferFormat = NV_ENC_BUFFER_FORMAT_NV12;
                ip.tuningInfo   = NV_ENC_TUNING_INFO_LOW_LATENCY;
                ip.encodeConfig = &cfg;
                NVENCSTATUS ri = apix.L.nvEncInitializeEncoder(e, &ip);
                line("  %s -> %s", cfgArms[i].label, st(ri, b2, sizeof(b2)));
                if (ri != NV_ENC_SUCCESS && apix.L.nvEncGetLastErrorString) {
                    const char *m = apix.L.nvEncGetLastErrorString(e);
                    if (m && (unsigned char)m[0] >= 0x20 && (unsigned char)m[0] < 0x7F) line("        driver says: %s", m);
                }
                apix.L.nvEncDestroyEncoder(e);
            }

            // The isolation says even `NV_ENC_CONFIG` with ONLY `version` set is refused,
            // so the explicit config has to be the DRIVER'S OWN, fetched with
            // nvEncGetEncodePresetConfig(Ex) and then refined.  That is the pattern the
            // SDK samples use.  This arm proves the pattern works WITH an explicit config.
            line("");
            line("  STEP 5  explicit config taken from nvEncGetEncodePresetConfig(Ex), then refined:");
            if (!apix.L.nvEncGetEncodePresetConfigEx && !apix.L.nvEncGetEncodePresetConfig) {
                line("    SKIPPED: no preset-config entry point");
            } else {
                NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
                memset(&p, 0, sizeof(p));
                p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
                p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
                p.device     = nv.dev;
                p.apiVersion = NVENCAPI_VERSION;
                void *e = nullptr;
                if (apix.L.nvEncOpenEncodeSessionEx(&p, &e) != NV_ENC_SUCCESS || !e) {
                    line("    OPEN failed");
                } else {
                    NV_ENC_PRESET_CONFIG pc;
                    memset(&pc, 0, sizeof(pc));
                    pc.version          = NV_ENC_PRESET_CONFIG_VER;
                    pc.presetCfg.version = NV_ENC_CONFIG_VER;
                    NVENCSTATUS rp;
                    if (apix.L.nvEncGetEncodePresetConfigEx) {
                        rp = apix.L.nvEncGetEncodePresetConfigEx(e, NV_ENC_CODEC_H264_GUID,
                                NV_ENC_PRESET_P3_GUID, NV_ENC_TUNING_INFO_LOW_LATENCY, &pc);
                        line("    nvEncGetEncodePresetConfigEx(P3, LOW_LATENCY) -> %s", st(rp, b1, sizeof(b1)));
                    } else {
                        rp = apix.L.nvEncGetEncodePresetConfig(e, NV_ENC_CODEC_H264_GUID,
                                NV_ENC_PRESET_P3_GUID, &pc);
                        line("    nvEncGetEncodePresetConfig(P3) -> %s", st(rp, b1, sizeof(b1)));
                    }
                    if (rp == NV_ENC_SUCCESS) {
                        pc.presetCfg.gopLength      = 120;   // our 2 s forced-IDR cadence
                        pc.presetCfg.frameIntervalP = 1;     // P-only
                        pc.presetCfg.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CBR;
                        pc.presetCfg.rcParams.averageBitRate  = 40000000;
                        pc.presetCfg.rcParams.maxBitRate      = 40000000;
                        pc.presetCfg.rcParams.vbvBufferSize   = 40000000;
                        pc.presetCfg.rcParams.vbvInitialDelay = 40000000;
                        NV_ENC_INITIALIZE_PARAMS ip;
                        memset(&ip, 0, sizeof(ip));
                        ip.version      = NV_ENC_INITIALIZE_PARAMS_VER;
                        ip.encodeGUID   = NV_ENC_CODEC_H264_GUID;
                        ip.presetGUID   = NV_ENC_PRESET_P3_GUID;
                        ip.encodeWidth  = 1920;
                        ip.encodeHeight = 1080;
                        ip.darWidth     = 1920;
                        ip.darHeight    = 1080;
                        ip.frameRateNum = 60;
                        ip.frameRateDen = 1;
                        ip.enablePTD    = 1;
                        ip.bufferFormat = NV_ENC_BUFFER_FORMAT_NV12;
                        ip.tuningInfo   = NV_ENC_TUNING_INFO_LOW_LATENCY;
                        ip.encodeConfig = &pc.presetCfg;
                        NVENCSTATUS ri = apix.L.nvEncInitializeEncoder(e, &ip);
                        line("    NvEncInitializeEncoder(explicit config from the driver) -> %s", st(ri, b2, sizeof(b2)));
                        if (ri == NV_ENC_SUCCESS) {
                            line("    => an EXPLICIT config DOES initialise; the earlier 8 was the config");
                            line("       CONTENT, not the concept.  (gopLength=%u frameIntervalP=%u rc=0x%X)",
                                 pc.presetCfg.gopLength, pc.presetCfg.frameIntervalP,
                                 (unsigned)pc.presetCfg.rcParams.rateControlMode);
                        } else if (apix.L.nvEncGetLastErrorString) {
                            const char *m = apix.L.nvEncGetLastErrorString(e);
                            if (m && (unsigned char)m[0] >= 0x20 && (unsigned char)m[0] < 0x7F) line("    driver says: %s", m);
                        }
                    }
                    apix.L.nvEncDestroyEncoder(e);
                }
            }
        }
    }

    // ------------------------------------------------------------------ 7. capabilities
    line("");
    line("--- 7. NvEncGetEncodeCaps per codec ------------------------------------------");
    {
        struct C { const char *name; GUID g; };
        const C codecs[] = { {"H.264", NV_ENC_CODEC_H264_GUID}, {"HEVC", NV_ENC_CODEC_HEVC_GUID}, {"AV1", NV_ENC_CODEC_AV1_GUID} };
        struct Cap { const char *name; NV_ENC_CAPS c; };
        const Cap caps[] = {
            { "NUM_ENCODER_ENGINES", NV_ENC_CAPS_NUM_ENCODER_ENGINES },
            { "WIDTH_MAX",           NV_ENC_CAPS_WIDTH_MAX },
            { "HEIGHT_MAX",          NV_ENC_CAPS_HEIGHT_MAX },
            { "WIDTH_MIN",           NV_ENC_CAPS_WIDTH_MIN },
            { "HEIGHT_MIN",          NV_ENC_CAPS_HEIGHT_MIN },
            { "RATECONTROL_MODES",   NV_ENC_CAPS_SUPPORTED_RATECONTROL_MODES },
            { "SUPPORT_10BIT",       NV_ENC_CAPS_SUPPORT_10BIT_ENCODE },
            { "MB_PER_SEC_MAX",      NV_ENC_CAPS_MB_PER_SEC_MAX },
        };
        if (!(session_initialized && enc)) {
            line("  SKIPPED — and it cannot be worked around: NvEncGetEncodeCaps needs an");
            line("  INITIALISED session.  MEASURED: calling it on an opened-but-uninitialised");
            line("  session does not return an error, it SEGFAULTS the process (0xC0000005, on");
            line("  the first run of this probe).  So NUM_ENCODER_ENGINES and maxEncodeWidth/");
            line("  maxEncodeHeight stay UNKNOWN unless NvEncInitializeEncoder succeeds.");
        } else {
            for (int i = 0; i < 3; ++i) {
                line("  [%s]", codecs[i].name);
                for (int j = 0; j < 8; ++j) {
                    NV_ENC_CAPS_PARAM cp; memset(&cp, 0, sizeof(cp));
                    cp.version     = NV_ENC_CAPS_PARAM_VER;
                    cp.capsToQuery = caps[j].c;
                    int val = -12345;
                    NVENCSTATUS r = apix.L.nvEncGetEncodeCaps(enc, codecs[i].g, &cp, &val);
                    line("    %-20s -> status=%s value=%d", caps[j].name, st(r, b1, sizeof(b1)), val);
                }
            }
        }
    }

    // ------------------------------------------------------------------ 8. concurrency
    line("");
    line("--- 8. CONCURRENT SESSION LIMIT: open until the driver refuses, release each --");
    {
        void *pool[128];
        int    opened = 0;
        unsigned first_fail = 0, first_fail_at = 0;
        memset(pool, 0, sizeof(pool));
        if (!have_nv || !apix.ok || !apix.L.nvEncOpenEncodeSessionEx) {
            line("  SKIPPED: no NVIDIA device / no table");
        } else {
            for (int i = 0; i < 64; ++i) {
                NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
                memset(&p, 0, sizeof(p));
                p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
                p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
                p.device     = nv.dev;
                p.apiVersion = NVENCAPI_VERSION;
                void *e = nullptr;
                NVENCSTATUS r = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
                if (r == NV_ENC_SUCCESS && e) {
                    pool[opened++] = e;
                    line("  session #%2d -> status=%s  encoder=%p   (now holding %d)",
                         opened, st(r, b1, sizeof(b1)), e, opened);
                } else {
                    first_fail = (unsigned)r;
                    first_fail_at = (unsigned)opened + 1;
                    line("  session #%2d -> status=%s  (encoder=%p)   *** FIRST REFUSAL ***",
                         opened + 1, st(r, b1, sizeof(b1)), e);
                    note_last_error(e, "refusal:");
                    break;
                }
            }
            line("");
            line("  => concurrent sessions opened and HELD at one time : %d", opened);
            if (first_fail) line("  => the driver refused #%u with status %s", first_fail_at, st((NVENCSTATUS)first_fail, b1, sizeof(b1)));
            else            line("  => NO refusal up to this probe's 64-session cap (limit NOT reached)");

            line("");
            line("  --- 8b. release every session, then open one more (does the budget return?)");
            for (int i = 0; i < opened; ++i) {
                NVENCSTATUS r = apix.L.nvEncDestroyEncoder(pool[i]);
                if (r != NV_ENC_SUCCESS) line("  destroy #%2d (%p) -> %s", i + 1, pool[i], st(r, b1, sizeof(b1)));
                pool[i] = nullptr;
            }
            line("  all %d released.", opened);
            NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
            memset(&p, 0, sizeof(p));
            p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
            p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
            p.device     = nv.dev;
            p.apiVersion = NVENCAPI_VERSION;
            void *e = nullptr;
            NVENCSTATUS r = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
            line("  after releasing all %d, open one more -> %s", opened, st(r, b1, sizeof(b1)));
            if (r == NV_ENC_SUCCESS && e) line("  released again -> %s", st(apix.L.nvEncDestroyEncoder(e), b2, sizeof(b2)));
        }

        // ------------------------------------------------ 8c. INITIALISED sessions
        // Section 8 holds sessions that were OPENED but never initialised.  That is not
        // the same resource: the limit that matters for a recorder is how many sessions
        // can hold a real encoder at once.  Each iteration opens AND initialises, and
        // keeps the session only on success — so the count is "sessions doing real work".
        line("");
        line("  --- 8c. same question for INITIALISED sessions (open + init, hold, repeat) ---");
        if (!have_nv || !apix.ok || !apix.L.nvEncOpenEncodeSessionEx || !apix.L.nvEncInitializeEncoder) {
            line("  SKIPPED: no device / no table");
        } else {
            void *ipool[64];
            int    iopened = 0;
            unsigned ifail = 0, ifail_at = 0, ifail_stage = 0;
            for (int i = 0; i < 32; ++i) {
                NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
                memset(&p, 0, sizeof(p));
                p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
                p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
                p.device     = nv.dev;
                p.apiVersion = NVENCAPI_VERSION;
                void *e = nullptr;
                NVENCSTATUS ro = apix.L.nvEncOpenEncodeSessionEx(&p, &e);
                if (ro != NV_ENC_SUCCESS || !e) {
                    ifail = (unsigned)ro; ifail_at = (unsigned)iopened + 1; ifail_stage = 1;
                    line("  init-session #%2d -> OPEN %s   *** REFUSED AT OPEN ***", iopened + 1, st(ro, b1, sizeof(b1)));
                    note_last_error(e, "open-refusal:");
                    break;
                }
                NV_ENC_INITIALIZE_PARAMS ip;
                memset(&ip, 0, sizeof(ip));
                ip.version      = NV_ENC_INITIALIZE_PARAMS_VER;
                ip.encodeGUID   = NV_ENC_CODEC_H264_GUID;
                ip.presetGUID   = NV_ENC_PRESET_P3_GUID;
                ip.encodeWidth  = 1920;
                ip.encodeHeight = 1080;
                ip.darWidth     = 1920;
                ip.darHeight    = 1080;
                ip.frameRateNum = 60;
                ip.frameRateDen = 1;
                ip.enablePTD    = 1;
                ip.bufferFormat = NV_ENC_BUFFER_FORMAT_NV12;
                ip.tuningInfo   = NV_ENC_TUNING_INFO_LOW_LATENCY;
                NVENCSTATUS ri = apix.L.nvEncInitializeEncoder(e, &ip);
                if (ri != NV_ENC_SUCCESS) {
                    ifail = (unsigned)ri; ifail_at = (unsigned)iopened + 1; ifail_stage = 2;
                    line("  init-session #%2d -> OPEN 0, INIT %s   *** REFUSED AT INIT ***",
                         iopened + 1, st(ri, b1, sizeof(b1)));
                    note_last_error(e, "init-refusal:");
                    apix.L.nvEncDestroyEncoder(e);
                    break;
                }
                ipool[iopened++] = e;
                line("  init-session #%2d -> opened AND initialised, encoder=%p   (holding %d live encoders)",
                     iopened, e, iopened);
            }
            line("");
            line("  => INITIALISED sessions held at one time : %d", iopened);
            if (ifail) line("  => refused #%u at %s with status %s", ifail_at,
                            ifail_stage == 1 ? "OPEN" : "INITIALIZE", st((NVENCSTATUS)ifail, b1, sizeof(b1)));
            else       line("  => no refusal up to this arm's 32 cap (limit NOT reached)");
            for (int i = 0; i < iopened; ++i) {
                NVENCSTATUS rr2 = apix.L.nvEncDestroyEncoder(ipool[i]);
                if (rr2 != NV_ENC_SUCCESS) line("  destroy init-session #%d -> %s", i + 1, st(rr2, b1, sizeof(b1)));
            }
            line("  all %d initialised sessions released.", iopened);
        }
    }

    // ------------------------------------------------------------------ 9. cleanup
    line("");
    line("--- 9. cleanup audit — nothing may be left held -------------------------------");
    if (enc) { line("  single session destroy -> %s", st(apix.L.nvEncDestroyEncoder(enc), b1, sizeof(b1))); enc = nullptr; }
    if (cu_ctx && hcu) {
        PFN_cuCtxDestroy_v2 d = (PFN_cuCtxDestroy_v2)(void *)GetProcAddress(hcu, "cuCtxDestroy_v2");
        line("  cuCtxDestroy_v2 -> %d", d ? d(cu_ctx) : -1);
        cu_ctx = nullptr;
    }
    if (nv.dev)     { nv.dev->Release(); nv.dev = nullptr; }
    if (nv.adapter) { nv.adapter->Release(); nv.adapter = nullptr; }
    if (g_factory)  { g_factory->Release(); g_factory = nullptr; }
    line("  every session opened above was destroyed or refused; none is meant to be held.");
    line("");
    line("probe finished.");
    return 0;
}
