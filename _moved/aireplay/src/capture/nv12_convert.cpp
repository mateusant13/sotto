#include "nv12_convert.h"

#include <d3dcommon.h>

namespace aireplay {

// ------------------------------------------------------------------ HLSL
// Compiled AT RUN TIME from d3dcompiler_47.dll: there is no fxc on this box (no MSVC).
// The full-screen triangle needs no vertex buffer and no input layout.
static const char* kHlsl = R"HLSL(
Texture2D<float4> srcTex : register(t0);
SamplerState      srcSmp : register(s0);

struct VSOut { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };

VSOut VSMain(uint vid : SV_VertexID)
{
    VSOut o;
    float2 t = float2((float)((vid << 1) & 2), (float)(vid & 2));   // (0,0) (2,0) (0,2)
    o.uv  = t;
    o.pos = float4(t.x * 2.0 - 1.0, 1.0 - t.y * 2.0, 0.0, 1.0);
    return o;
}

// BT.709, LIMITED (studio) range — what an H.264 decoder assumes by default.
static const float3 KR = float3(0.2126, 0.7152, 0.0722);

float PSY(VSOut i) : SV_Target
{
    float3 rgb  = srcTex.Sample(srcSmp, i.uv).rgb;
    float  ylin = dot(rgb, KR);
    return 0.062745098 + 0.858823529 * ylin;          // 16/255 + (219/255)*Y'
}

float2 PSUV(VSOut i) : SV_Target
{
    float3 rgb  = srcTex.Sample(srcSmp, i.uv).rgb;
    float  ylin = dot(rgb, KR);
    float  cb   = (rgb.b - ylin) / 1.8556;
    float  cr   = (rgb.r - ylin) / 1.5748;
    return float2(0.5 + 0.858823529 * cb, 0.5 + 0.858823529 * cr);
}
)HLSL";

// ------------------------------------------------------------------ D3DCompile, bound late
typedef HRESULT (WINAPI *PFN_D3DCompile)(LPCVOID, SIZE_T, LPCSTR, const D3D_SHADER_MACRO*,
                                         ID3DInclude*, LPCSTR, LPCSTR, UINT, UINT,
                                         ID3DBlob**, ID3DBlob**);

static bool compile(const char* entry, const char* target, ID3DBlob** blob, std::string* err)
{
    static HMODULE lib = nullptr;
    static PFN_D3DCompile fn = nullptr;
    if (!lib) {
        lib = LoadLibraryW(L"d3dcompiler_47.dll");
        if (lib) fn = (PFN_D3DCompile)(void*)GetProcAddress(lib, "D3DCompile");
    }
    if (!fn) { *err = "d3dcompiler_47.dll / D3DCompile not available"; return false; }

    ID3DBlob* errors = nullptr;
    HRESULT hr = fn(kHlsl, strlen(kHlsl), "nv12_convert.hlsl", nullptr, nullptr,
                    entry, target, 0x00008000 /*OPT_LEVEL3*/, 0, blob, &errors);
    if (FAILED(hr)) {
        std::string msg = "D3DCompile(" + std::string(entry) + ") failed " + hr_str(hr);
        if (errors) { msg += ": "; msg += (const char*)errors->GetBufferPointer(); errors->Release(); }
        *err = msg;
        return false;
    }
    if (errors) errors->Release();
    return true;
}

bool Nv12Converter::init(ID3D11Device* dev, std::string* err)
{
    ID3DBlob* vsb = nullptr;
    ID3DBlob* pyb = nullptr;
    ID3DBlob* pub = nullptr;
    if (!compile("VSMain", "vs_5_0", &vsb, err)) return false;
    if (!compile("PSY",    "ps_5_0", &pyb, err)) { vsb->Release(); return false; }
    if (!compile("PSUV",   "ps_5_0", &pub, err)) { vsb->Release(); pyb->Release(); return false; }

    HRESULT hr = dev->CreateVertexShader(vsb->GetBufferPointer(), vsb->GetBufferSize(), nullptr, &vs_);
    vsb->Release();
    if (FAILED(hr)) { *err = "CreateVertexShader " + hr_str(hr); return false; }
    hr = dev->CreatePixelShader(pyb->GetBufferPointer(), pyb->GetBufferSize(), nullptr, &psy_);
    pyb->Release();
    if (FAILED(hr)) { *err = "CreatePixelShader(PSY) " + hr_str(hr); return false; }
    hr = dev->CreatePixelShader(pub->GetBufferPointer(), pub->GetBufferSize(), nullptr, &psuv_);
    pub->Release();
    if (FAILED(hr)) { *err = "CreatePixelShader(PSUV) " + hr_str(hr); return false; }

    D3D11_SAMPLER_DESC sd;
    memset(&sd, 0, sizeof(sd));
    sd.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU = sd.AddressV = sd.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
    sd.MaxLOD = D3D11_FLOAT32_MAX;
    hr = dev->CreateSamplerState(&sd, &samp_);
    if (FAILED(hr)) { *err = "CreateSamplerState " + hr_str(hr); return false; }

    D3D11_RASTERIZER_DESC rd;
    memset(&rd, 0, sizeof(rd));
    rd.FillMode = D3D11_FILL_SOLID;
    rd.CullMode = D3D11_CULL_NONE;      // the full-screen triangle's winding is not a contract
    rd.DepthClipEnable = TRUE;
    hr = dev->CreateRasterizerState(&rd, &rs_);
    if (FAILED(hr)) { *err = "CreateRasterizerState " + hr_str(hr); return false; }

    return true;
}

bool Nv12Converter::ensure_targets(ID3D11Device* dev, ID3D11Texture2D* nv12,
                                   uint32_t w, uint32_t h, std::string* err)
{
    if (bound_ == nv12 && rtv_y_ && rtv_uv_ && w_ == w && h_ == h) return true;
    if (rtv_y_)  { rtv_y_->Release();  rtv_y_  = nullptr; }
    if (rtv_uv_) { rtv_uv_->Release(); rtv_uv_ = nullptr; }
    bound_ = nv12;
    w_ = w; h_ = h;

    D3D11_RENDER_TARGET_VIEW_DESC rd;
    memset(&rd, 0, sizeof(rd));
    rd.ViewDimension = D3D11_RTV_DIMENSION_TEXTURE2D;
    rd.Texture2D.MipSlice = 0;

    // Plane 0 (luma) as R8, plane 1 (interleaved Cb/Cr) as R8G8 at half size.
    rd.Format = DXGI_FORMAT_R8_UNORM;
    HRESULT hr = dev->CreateRenderTargetView(nv12, &rd, &rtv_y_);
    if (FAILED(hr)) { *err = "CreateRenderTargetView(NV12 plane 0, R8_UNORM) " + hr_str(hr); return false; }
    rd.Format = DXGI_FORMAT_R8G8_UNORM;
    hr = dev->CreateRenderTargetView(nv12, &rd, &rtv_uv_);
    if (FAILED(hr)) { *err = "CreateRenderTargetView(NV12 plane 1, R8G8_UNORM) " + hr_str(hr); return false; }
    return true;
}

bool Nv12Converter::convert(ID3D11Device* dev, ID3D11DeviceContext* ctx,
                            ID3D11ShaderResourceView* srv,
                            ID3D11Texture2D* nv12, uint32_t w, uint32_t h,
                            std::string* err)
{
    if (!ensure_targets(dev, nv12, w, h, err)) return false;

    ID3D11ShaderResourceView*  srvs[1] = { srv };
    ID3D11SamplerState*        smps[1] = { samp_ };
    ID3D11Buffer*              cbufs[1] = { nullptr };
    ID3D11RenderTargetView*    rtvs[1] = { nullptr };

    ctx->IASetInputLayout(nullptr);
    ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ctx->VSSetShader(vs_, nullptr, 0);
    ctx->PSSetShaderResources(0, 1, srvs);
    ctx->PSSetSamplers(0, 1, smps);
    ctx->PSSetConstantBuffers(0, 1, cbufs);
    ctx->RSSetState(rs_);
    ctx->OMSetDepthStencilState(nullptr, 0);
    ctx->OMSetBlendState(nullptr, nullptr, 0xFFFFFFFF);

    // Pass 1 — luma.
    rtvs[0] = rtv_y_;
    ctx->OMSetRenderTargets(1, rtvs, nullptr);
    D3D11_VIEWPORT vp;
    memset(&vp, 0, sizeof(vp));
    vp.Width  = (float)w;
    vp.Height = (float)h;
    vp.MaxDepth = 1.0f;
    ctx->RSSetViewports(1, &vp);
    ctx->PSSetShader(psy_, nullptr, 0);
    ctx->Draw(3, 0);

    // Pass 2 — chroma at half resolution (the R8G8 view of an NV12 texture is half-size).
    rtvs[0] = rtv_uv_;
    ctx->OMSetRenderTargets(1, rtvs, nullptr);
    vp.Width  = (float)(w / 2);
    vp.Height = (float)(h / 2);
    ctx->RSSetViewports(1, &vp);
    ctx->PSSetShader(psuv_, nullptr, 0);
    ctx->Draw(3, 0);

    ID3D11ShaderResourceView* none[1] = { nullptr };
    ctx->PSSetShaderResources(0, 1, none);
    ++calls_;
    return true;
}

void Nv12Converter::release()
{
    if (rtv_y_)  { rtv_y_->Release();  rtv_y_  = nullptr; }
    if (rtv_uv_) { rtv_uv_->Release(); rtv_uv_ = nullptr; }
    if (samp_)   { samp_->Release();   samp_   = nullptr; }
    if (rs_)     { rs_->Release();     rs_     = nullptr; }
    if (psy_)    { psy_->Release();    psy_    = nullptr; }
    if (psuv_)   { psuv_->Release();   psuv_   = nullptr; }
    if (vs_)     { vs_->Release();     vs_     = nullptr; }
    bound_ = nullptr;
}

} // namespace aireplay
