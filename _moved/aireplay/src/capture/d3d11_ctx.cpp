#include "d3d11_ctx.h"

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

uint64_t D3d11Context::ring_cap_bytes() const
{
    // Law 7: budget the ring from the measured hardware class, then derive seconds.
    // clamp(VRAM/16, 256 MiB, 2048 MiB).
    uint64_t cap = info.dedicated_vram / 16;
    const uint64_t lo = 256ull << 20, hi = 2048ull << 20;
    if (cap < lo) cap = lo;
    if (cap > hi) cap = hi;
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
