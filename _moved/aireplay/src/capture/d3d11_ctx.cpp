#include "d3d11_ctx.h"

#include <cstdlib>

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

// ---- the ring budget prices SYSTEM RAM, not VRAM (spec 03, law 7) -----------------
// MEASURED defect (receipts/receipt-14-ring-cap-vram-vs-ram.md): the arena is a
// std::vector<uint8_t> committed in full at init() (ring_buffer.cpp:15, arena_.assign), so
// the ring consumes SYSTEM RAM.  Nothing in the ring path allocates VRAM, yet the cap was
// dedicated_vram/16 -- a budget priced in bytes of a pool the ring never draws from.  On
// this box that bound at 2.0% of the 47.74 GiB of RAM (998.69 MiB, from DedicatedVideoMemory
// 15 979 MiB) and silently clipped 4K60 to 46.5 s instead of the promised 120 s.  VRAM still
// legitimately governs the ENCODE path; it never governed this one.
//
//   cap = clamp(0.25 * systemTotalPhysicalMemory, 256 MiB, 4096 MiB)
//   SOTTO_RING_CAP_MB=<MiB> overrides it, and the override passes through the SAME bounds:
//   an absurd override is refused out loud, never honoured silently.
static const uint64_t RING_CAP_LO = 256ull  << 20;
static const uint64_t RING_CAP_HI = 4096ull << 20;

static uint64_t system_total_phys_bytes(uint64_t* avail_phys)
{
    MEMORYSTATUSEX ms;
    memset(&ms, 0, sizeof(ms));
    ms.dwLength = sizeof(ms);
    if (!GlobalMemoryStatusEx(&ms)) return 0;
    if (avail_phys) *avail_phys = (uint64_t)ms.ullAvailPhys;
    return (uint64_t)ms.ullTotalPhys;
}

uint64_t D3d11Context::ring_cap_bytes() const
{
    // Law 7: budget the ring from the MEASURED pool the ring actually consumes, and say
    // out loud WHERE the number came from, so no receipt has to guess.
    const char* ov = getenv("SOTTO_RING_CAP_MB");
    if (ov && *ov) {
        char* end = nullptr;
        unsigned long long want_mb = strtoull(ov, &end, 10);
        if (end != ov && *end == 0 && want_mb > 0) {
            const unsigned long long lo_mb = RING_CAP_LO >> 20, hi_mb = RING_CAP_HI >> 20;
            unsigned long long cap_mb = want_mb;
            const char* why = "";
            if (cap_mb < lo_mb) { cap_mb = lo_mb; why = "  CLAMPED_LOW"; }
            if (cap_mb > hi_mb) { cap_mb = hi_mb; why = "  CLAMPED_HIGH"; }
            log_line("  ring cap: %llu MB  source=env:SOTTO_RING_CAP_MB  requested=%llu MB  "
                     "clamp=[%llu,%llu] MB%s",
                     cap_mb, want_mb, lo_mb, hi_mb, why);
            return (uint64_t)cap_mb << 20;
        }
        log_line("  ring cap: SOTTO_RING_CAP_MB=\"%s\" is not a whole MiB count > 0 -- IGNORED, "
                 "falling back to system RAM", ov);
    }

    uint64_t avail = 0;
    const uint64_t total = system_total_phys_bytes(&avail);
    if (total == 0) {
        log_line("  ring cap: %llu MB  source=lo_floor  reason=GlobalMemoryStatusEx failed",
                 (unsigned long long)(RING_CAP_LO >> 20));
        return RING_CAP_LO;
    }

    const uint64_t quarter = total / 4;              // 0.25 x system RAM, read at runtime
    uint64_t cap = quarter;
    const char* why = "";
    if (cap < RING_CAP_LO) { cap = RING_CAP_LO; why = "  CLAMPED_LOW"; }
    if (cap > RING_CAP_HI) { cap = RING_CAP_HI; why = "  CLAMPED_HIGH"; }
    log_line("  ring cap: %llu MB  source=system_ram  total_phys=%llu MB  avail_phys=%llu MB  "
             "quarter=%llu MB  clamp=[%llu,%llu] MB%s  vram_ignored=%llu MB",
             (unsigned long long)(cap >> 20), (unsigned long long)(total >> 20),
             (unsigned long long)(avail >> 20), (unsigned long long)(quarter >> 20),
             (unsigned long long)(RING_CAP_LO >> 20), (unsigned long long)(RING_CAP_HI >> 20), why,
             (unsigned long long)(info.dedicated_vram >> 20));
    return cap;
}

void D3d11Context::release()
{
    if (ctx)     { ctx->Release();     ctx = nullptr; }
    if (device)  { device->Release();  device = nullptr; }
    if (adapter) { adapter->Release(); adapter = nullptr; }
    if (factory) { factory->Release(); factory = nullptr; }
}

} // namespace aireplay
