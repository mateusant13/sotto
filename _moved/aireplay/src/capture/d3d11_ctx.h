// d3d11_ctx.h — the D3D11 device the whole capture path lives on.
//
// Spec 03 §2.2: the adapter is CHOSEN by vendor, never taken from the default-adapter
// path.  On this box the default happens to be the RTX 5080 too, but on a hybrid or
// docked machine it is the wrong one, and the NVENC session must be opened on the SAME
// ID3D11Device that owns the textures.
#pragma once
#include "common.h"

namespace aireplay {

struct AdapterInfo {
    UINT     index = 0;
    UINT     vendor = 0;
    UINT     device_id = 0;
    uint64_t dedicated_vram = 0;
    UINT     flags = 0;
    char     name[128] = "?";
};

struct D3d11Context {
    IDXGIFactory1*       factory = nullptr;
    IDXGIAdapter1*       adapter = nullptr;
    ID3D11Device*        device  = nullptr;
    ID3D11DeviceContext* ctx     = nullptr;
    AdapterInfo          info;
    D3D_FEATURE_LEVEL    level   = (D3D_FEATURE_LEVEL)0;

    // Enumerate every DXGI adapter (logged) and create the device on the first whose
    // VendorId matches.  Returns false with *err set when there is no such adapter or
    // the device could not be created — never falls back to the default adapter.
    bool create_on_vendor(UINT vendor, std::string* err);

    // Ring budget from the measured hardware class (spec 03 §2.6, law 7).
    uint64_t ring_cap_bytes() const;

    void release();
};

} // namespace aireplay
