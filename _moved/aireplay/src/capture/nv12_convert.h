// nv12_convert.h — BGRA8 -> NV12 on the GPU.
//
// Spec 03 §2.3.  This is the ONLY pixel cost the product owns: desktop->pool is DWM's
// (already paid to show the pixels) and pool->NVENC is zero-copy.  Doing it on the CPU
// would mean 8.3 MB/frame of mapping + arithmetic at 1080p60 (~500 MB/s) on the same
// machine the owner is typing on — law 8 forbids that by measurement, not by taste.
//
// Two passes, not MRT: D3D11 requires every RTV in an MRT set to have identical
// dimensions, and the chroma plane of NV12 is half-size.
#pragma once
#include "common.h"

namespace aireplay {

class Nv12Converter {
public:
    bool init(ID3D11Device* dev, std::string* err);

    // srv must be a shader resource view over the source BGRA8/BGRA texture.
    // nv12 must have been created DXGI_FORMAT_NV12 with D3D11_BIND_RENDER_TARGET.
    // Creates (and caches) the two plane RTVs for that exact texture.
    bool convert(ID3D11Device* dev, ID3D11DeviceContext* ctx,
                 ID3D11ShaderResourceView* srv,
                 ID3D11Texture2D* nv12, uint32_t w, uint32_t h,
                 std::string* err);

    void release();

    // Measured cost of the conversion itself (sum over the run).
    uint64_t convert_calls() const { return calls_; }

private:
    bool ensure_targets(ID3D11Device* dev, ID3D11Texture2D* nv12, uint32_t w, uint32_t h,
                        std::string* err);

    ID3D11VertexShader*   vs_   = nullptr;
    ID3D11PixelShader*    psy_  = nullptr;
    ID3D11PixelShader*    psuv_ = nullptr;
    ID3D11SamplerState*   samp_ = nullptr;
    ID3D11RasterizerState* rs_  = nullptr;

    ID3D11RenderTargetView* rtv_y_  = nullptr;
    ID3D11RenderTargetView* rtv_uv_ = nullptr;
    ID3D11Texture2D*        bound_  = nullptr;
    uint32_t                w_ = 0, h_ = 0;
    uint64_t                calls_ = 0;
};

} // namespace aireplay
