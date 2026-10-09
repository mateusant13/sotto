#include "d3d11_ctx.h"

#include <cstdlib>   // getenv / strtoull — the run-time override channel

namespace aireplay {

static void dump_adapters(IDXGIFactory1* f)
{
    log_line("  --- DXGI adapters (all) ---");
    IDXGIAdapter1* a = nullptr;
    for (UINT i = 0; i < 16; ++i) {
        if (f->EnumAdapters1(i, &a) == DXGI_ERROR_NOT_FOUND) break;
        DXGI_ADAPTER_DESC1 d;
        memset(&d, 0, sizeof(d));
        a->GetDesc1(&d);
        log_line("    idx=%u vendor=0x%04X device=0x%04X vram=%lluMB flags=0x%X name=%s",
                 i, (unsigned)d.VendorId, (unsigned)d.DeviceId,
                 (unsigned long long)(d.DedicatedVideoMemory >> 20), (unsigned)d.Flags,
                 narrow(d.Description).c_str());
        a->Release();
        a = nullptr;
    }
}

bool D3d11Context::create_on_vendor(UINT want_vendor, std::string* err)
{
    HRESULT hr = CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void**)&factory);
    if (FAILED(hr)) { *err = "CreateDXGIFactory1 failed " + hr_str(hr); return false; }

    dump_adapters(factory);

    IDXGIAdapter1* a = nullptr;
    for (UINT i = 0; i < 16; ++i) {
        if (factory->EnumAdapters1(i, &a) == DXGI_ERROR_NOT_FOUND) break;
        DXGI_ADAPTER_DESC1 d;
        memset(&d, 0, sizeof(d));
        a->GetDesc1(&d);
        if (d.VendorId != want_vendor) { a->Release(); a = nullptr; continue; }

        D3D_FEATURE_LEVEL got = (D3D_FEATURE_LEVEL)0;
        // DRIVER_TYPE_UNKNOWN is REQUIRED when an explicit adapter is passed.
        hr = D3D11CreateDevice(a, D3D_DRIVER_TYPE_UNKNOWN, nullptr, 0, nullptr, 0,
                               D3D11_SDK_VERSION, &device, &got, &ctx);
        info.index = i;
        info.vendor = d.VendorId;
        info.device_id = d.DeviceId;
        info.dedicated_vram = (uint64_t)d.DedicatedVideoMemory;
        info.flags = (UINT)d.Flags;
        snprintf(info.name, sizeof(info.name), "%s", narrow(d.Description).c_str());
        level = got;
        if (FAILED(hr)) {
            *err = "D3D11CreateDevice on vendor 0x" + std::to_string(want_vendor) +
                   " (" + info.name + ") failed " + hr_str(hr);
            a->Release();
            return false;
        }
        adapter = a;
        log_line("  device: adapter idx=%u vendor=0x%04X name=%s feature_level=0x%X vram=%lluMB",
                 info.index, info.vendor, info.name, (unsigned)level,
                 (unsigned long long)(info.dedicated_vram >> 20));
        return true;
    }
    *err = "no DXGI adapter with VendorId 0x" + std::to_string(want_vendor) +
           " was found (the default-adapter path is NOT used on purpose)";
    return false;
}

// ---------------------------------------------------------------------------
// Law 7 ring budget.
//
// The arena is HOST memory, not video memory: ring_buffer.cpp:15 does
// arena_.assign(capacity_bytes, 0) on a std::vector<uint8_t>, so the whole cap is
// committed out of the system pool at init().  Nothing in the ring path allocates
// VRAM.  This function USED to divide info.dedicated_vram by 16, i.e. it budgeted
// a host-memory arena out of video memory.
//
// MEASURED on the dev box, before this change:
//   DedicatedVideoMemory = 15 979 MiB -> cap = 998.69 MiB
//   TotalPhysicalMemory  = 47.74 GiB
// so the cap bound at 2.0% of the pool the arena actually comes from, and at
// 4K60 the ring silently kept 46.5 s of the 120 s the spec promises.  The divisor
// is now host RAM, measured at RUN time — never hardcoded — and the log line names
// the source so the number in a receipt is traceable.
// ---------------------------------------------------------------------------

namespace {

// The host memory pool, read at run time.  0 only if the call itself fails.
uint64_t system_phys_bytes()
{
    MEMORYSTATUSEX ms;
    memset(&ms, 0, sizeof(ms));
    ms.dwLength = sizeof(ms);
    if (!GlobalMemoryStatusEx(&ms)) return 0;
    return (uint64_t)ms.ullTotalPhys;
}

const uint64_t kRingLoMb = 256;    // floor  — smaller cannot hold a useful window
const uint64_t kRingHiMb = 4096;   // ceiling — the arena is committed in full at init()
const char*     kRingMbEnv = "SOTTO_RING_MB";

} // namespace

uint64_t D3d11Context::ring_cap_bytes() const
{
    // Everything below is in MiB so an absurd override cannot overflow a shift.
    const uint64_t total_mb = system_phys_bytes() >> 20;   // the pool we actually take from
    const uint64_t want_mb  = total_mb / 4;                // law 7: 25% of host RAM

    uint64_t    pick_mb = want_mb;
    const char* source  = "system RAM: GlobalMemoryStatusEx().ullTotalPhys / 4";

    // Run-time override, so a receipt can reproduce the exact cap without a rebuild.
    const char* env = getenv(kRingMbEnv);
    if (env && *env) {
        uint64_t asked_mb = strtoull(env, nullptr, 10);
        if (asked_mb) {
            pick_mb = asked_mb;
            source  = "override: env SOTTO_RING_MB";
        }
    }

    uint64_t cap_mb = pick_mb;
    char     clamp[128];
    clamp[0] = '\0';
    if (cap_mb < kRingLoMb) {
        snprintf(clamp, sizeof(clamp), "  [CLAMPED UP %llu -> %llu MB, floor]",
                 (unsigned long long)cap_mb, (unsigned long long)kRingLoMb);
        cap_mb = kRingLoMb;
    } else if (cap_mb > kRingHiMb) {
        snprintf(clamp, sizeof(clamp), "  [CLAMPED DOWN %llu -> %llu MB, ceiling]",
                 (unsigned long long)cap_mb, (unsigned long long)kRingHiMb);
        cap_mb = kRingHiMb;
    }

    // One line per fact: the source, the raw host pool, what was asked, what was
    // applied, and the clamp when one fired.  dedicated_vram is printed too, so the
    // receipt shows the pool that is deliberately NOT used for this budget.
    log_line("  RING CAP (law 7): source=%s sysram=%lluMB asked=%lluMB -> cap=%lluMB%s  (vram=%lluMB NOT used: the arena is host RAM)",
             source, (unsigned long long)total_mb, (unsigned long long)pick_mb,
             (unsigned long long)cap_mb, clamp,
             (unsigned long long)(info.dedicated_vram >> 20));

    return cap_mb << 20;
}

void D3d11Context::release()
{
    if (ctx)     { ctx->Release();     ctx = nullptr; }
    if (device)  { device->Release();  device = nullptr; }
    if (adapter) { adapter->Release(); adapter = nullptr; }
    if (factory) { factory->Release(); factory = nullptr; }
}

} // namespace aireplay
