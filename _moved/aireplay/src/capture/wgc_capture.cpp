#include "wgc_capture.h"

#include <inspectable.h>
#include <roapi.h>
#include <winstring.h>

#include <windows.foundation.h>
#include <windows.graphics.h>
#include <windows.graphics.directx.direct3d11.h>
#include <windows.graphics.capture.h>
#include <windows.graphics.capture.interop.h>

namespace aireplay {

// ---------------------------------------------------------------------------
// GUIDs written out literally on purpose.  DEFINE_GUID in the mingw headers only
// *declares* an extern unless INITGUID is defined, and __uuidof availability depends
// on __CRT_UUID_DECL — a literal GUID is exact and cannot silently become {0}.
// ---------------------------------------------------------------------------
static const GUID kIID_ItemInterop =
    { 0x3628e81b, 0x3cac, 0x4c60, { 0xb7, 0xf4, 0x23, 0xce, 0x0e, 0x0c, 0x33, 0x56 } };
static const GUID kIID_Item =
    { 0x79c3f95b, 0x31f7, 0x4ec2, { 0xa4, 0x64, 0x63, 0x2e, 0xf5, 0xd3, 0x07, 0x60 } };
static const GUID kIID_PoolStatics2 =
    { 0x589b103f, 0x6bbc, 0x5df5, { 0xa9, 0x91, 0x02, 0xe2, 0x8b, 0x3b, 0x66, 0xd5 } };
static const GUID kIID_Session3 =
    { 0xf2cdd966, 0x22ae, 0x5ea1, { 0x95, 0x96, 0x3a, 0x28, 0x93, 0x44, 0xc3, 0xbe } };
static const GUID kIID_DxgiAccess =
    { 0xa9b3d012, 0x3df2, 0x4ee3, { 0xb8, 0xd1, 0x86, 0x95, 0xf4, 0x57, 0xd3, 0xc1 } };
static const GUID kIID_D3DDevice =
    { 0xa37624ab, 0x8d5f, 0x4650, { 0x9d, 0x3e, 0x9e, 0xae, 0x3d, 0x9b, 0xc6, 0x70 } };

// The documented bridge from a WinRT IDirect3DSurface to the DXGI object behind it.
// Declared by hand: mingw ships windows.graphics.directx.direct3d11.h but not the
// .interop.h that carries this in the Windows SDK.  The vtable is IUnknown + one slot.
struct IDirect3DDxgiInterfaceAccess : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE GetInterface(REFIID iid, void** p) = 0;
};

extern "C" HRESULT WINAPI CreateDirect3D11DeviceFromDXGIDevice(IDXGIDevice* dxgiDevice,
                                                               IInspectable** graphicsDevice);

static bool qi_texture(IUnknown* surface, ID3D11Texture2D** out)
{
    *out = nullptr;
    if (SUCCEEDED(surface->QueryInterface(__uuidof(ID3D11Texture2D), (void**)out)) && *out)
        return true;
    IDirect3DDxgiInterfaceAccess* acc = nullptr;
    if (SUCCEEDED(surface->QueryInterface(kIID_DxgiAccess, (void**)&acc)) && acc) {
        HRESULT hr = acc->GetInterface(__uuidof(ID3D11Texture2D), (void**)out);
        acc->Release();
        if (SUCCEEDED(hr) && *out) return true;
    }
    return false;
}

static bool ro_string(const wchar_t* s, HSTRING* out, std::string* err)
{
    HRESULT hr = WindowsCreateString(s, (UINT32)wcslen(s), out);
    if (FAILED(hr)) { *err = "WindowsCreateString failed " + hr_str(hr); return false; }
    return true;
}

// RoInitialize must run BEFORE RoGetActivationFactory.  Getting this order wrong returns
// CO_E_NOTINITIALIZED (0x800401F0) from the activation factory and looks like "WGC is not
// available on this machine" — it is not; it is a missing initialisation.
static bool ro_init_once(std::string* err)
{
    static HRESULT hr_once = E_PENDING;
    if (hr_once == E_PENDING) hr_once = RoInitialize(RO_INIT_MULTITHREADED);
    if (FAILED(hr_once) && hr_once != RPC_E_CHANGED_MODE) {
        *err = "RoInitialize(RO_INIT_MULTITHREADED) failed " + hr_str(hr_once);
        return false;
    }
    return true;
}

// ------------------------------------------------------------------ item creation
static bool make_item_for_window(HWND hwnd, void** item, std::string* err)
{
    if (!ro_init_once(err)) return false;
    HSTRING cls = nullptr;
    if (!ro_string(L"Windows.Graphics.Capture.GraphicsCaptureItem", &cls, err)) return false;
    IGraphicsCaptureItemInterop* interop = nullptr;
    HRESULT hr = RoGetActivationFactory(cls, kIID_ItemInterop, (void**)&interop);
    WindowsDeleteString(cls);
    if (FAILED(hr) || !interop) {
        *err = "RoGetActivationFactory(GraphicsCaptureItem, IGraphicsCaptureItemInterop) failed " + hr_str(hr);
        return false;
    }
    hr = interop->CreateForWindow(hwnd, kIID_Item, item);
    interop->Release();
    if (FAILED(hr) || !*item) { *err = "CreateForWindow failed " + hr_str(hr); return false; }
    return true;
}

static bool make_item_for_monitor(HMONITOR mon, void** item, std::string* err)
{
    if (!ro_init_once(err)) return false;
    HSTRING cls = nullptr;
    if (!ro_string(L"Windows.Graphics.Capture.GraphicsCaptureItem", &cls, err)) return false;
    IGraphicsCaptureItemInterop* interop = nullptr;
    HRESULT hr = RoGetActivationFactory(cls, kIID_ItemInterop, (void**)&interop);
    WindowsDeleteString(cls);
    if (FAILED(hr) || !interop) {
        *err = "RoGetActivationFactory(GraphicsCaptureItem, IGraphicsCaptureItemInterop) failed " + hr_str(hr);
        return false;
    }
    hr = interop->CreateForMonitor(mon, kIID_Item, item);
    interop->Release();
    if (FAILED(hr) || !*item) { *err = "CreateForMonitor failed " + hr_str(hr); return false; }
    return true;
}

bool WgcCapture::start_for_window(ID3D11Device* dev, HWND hwnd, std::string* err)
{
    kind_ = "window";
    void* item = nullptr;
    if (!make_item_for_window(hwnd, &item, err)) return false;
    bool ok = start_common(dev, item, err);
    ((IUnknown*)item)->Release();
    return ok;
}

bool WgcCapture::start_for_monitor(ID3D11Device* dev, HMONITOR mon, std::string* err)
{
    kind_ = "monitor";
    void* item = nullptr;
    if (!make_item_for_monitor(mon, &item, err)) return false;
    bool ok = start_common(dev, item, err);
    ((IUnknown*)item)->Release();
    return ok;
}

bool WgcCapture::start_common(ID3D11Device* dev, void* item, std::string* err)
{
    dev_ = dev;

    if (!ro_init_once(err)) return false;

    HRESULT hr = S_OK;

    // --- WinRT wrapper around OUR D3D11 device (same device, same adapter).
    IDXGIDevice* dxgi = nullptr;
    hr = dev->QueryInterface(__uuidof(IDXGIDevice), (void**)&dxgi);
    if (FAILED(hr) || !dxgi) { *err = "ID3D11Device->IDXGIDevice failed " + hr_str(hr); return false; }
    IInspectable* insp = nullptr;
    hr = CreateDirect3D11DeviceFromDXGIDevice(dxgi, &insp);
    dxgi->Release();
    if (FAILED(hr) || !insp) {
        *err = "CreateDirect3D11DeviceFromDXGIDevice failed " + hr_str(hr);
        return false;
    }
    hr = insp->QueryInterface(kIID_D3DDevice, (void**)&d3d_device_);
    insp->Release();
    if (FAILED(hr) || !d3d_device_) { *err = "QI for IDirect3DDevice failed " + hr_str(hr); return false; }
    ABI::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice* rtdev =
        (ABI::Windows::Graphics::DirectX::Direct3D11::IDirect3DDevice*)d3d_device_;

    // --- item size.
    ABI::Windows::Graphics::SizeInt32 sz;
    memset(&sz, 0, sizeof(sz));
    hr = ((ABI::Windows::Graphics::Capture::IGraphicsCaptureItem*)item)->get_Size(&sz);
    if (FAILED(hr) || sz.Width <= 0 || sz.Height <= 0) {
        *err = "IGraphicsCaptureItem::get_Size failed " + hr_str(hr);
        return false;
    }
    w_ = (uint32_t)sz.Width;
    h_ = (uint32_t)sz.Height;
    item_ = item;

    // --- frame pool, FREE-THREADED: no message pump, no UI thread.
    HSTRING cls = nullptr;
    if (!ro_string(L"Windows.Graphics.Capture.Direct3D11CaptureFramePool", &cls, err)) return false;
    ABI::Windows::Graphics::Capture::IDirect3D11CaptureFramePoolStatics2* statics2 = nullptr;
    hr = RoGetActivationFactory(cls, kIID_PoolStatics2, (void**)&statics2);
    WindowsDeleteString(cls);
    if (FAILED(hr) || !statics2) {
        *err = "RoGetActivationFactory(Direct3D11CaptureFramePool, Statics2) failed " + hr_str(hr);
        return false;
    }
    ABI::Windows::Graphics::Capture::IDirect3D11CaptureFramePool* pool = nullptr;
    hr = statics2->CreateFreeThreaded(rtdev,
                                      ABI::Windows::Graphics::DirectX::DirectXPixelFormat_B8G8R8A8UIntNormalized,
                                      3, sz, &pool);
    statics2->Release();
    if (FAILED(hr) || !pool) { *err = "CreateFreeThreaded failed " + hr_str(hr); return false; }
    pool_ = pool;

    // --- session.
    ABI::Windows::Graphics::Capture::IGraphicsCaptureSession* sess = nullptr;
    hr = pool->CreateCaptureSession((ABI::Windows::Graphics::Capture::IGraphicsCaptureItem*)item, &sess);
    if (FAILED(hr) || !sess) { *err = "CreateCaptureSession failed " + hr_str(hr); return false; }
    session_ = sess;

    // The border: a plain Win32 exe CANNOT remove it (needs a packaged app with the
    // graphicsCaptureWithoutBorder capability and a one-time prompt).  We ask anyway and
    // record the answer, instead of pretending the border is not there.
    ABI::Windows::Graphics::Capture::IGraphicsCaptureSession3* s3 = nullptr;
    if (SUCCEEDED(sess->QueryInterface(kIID_Session3, (void**)&s3)) && s3) {
        boolean before = 1, after = 1;
        s3->get_IsBorderRequired(&before);
        HRESULT h2 = s3->put_IsBorderRequired(0);
        s3->get_IsBorderRequired(&after);
        log_line("  WGC border: IsBorderRequired before=%d after=%d put_hr=%s (a plain Win32 exe cannot remove it)",
                 (int)before, (int)after, hr_str(h2).c_str());
        s3->Release();
    } else {
        log_line("  WGC border: IGraphicsCaptureSession3 not available; border state NOT queried");
    }

    hr = sess->StartCapture();
    if (FAILED(hr)) { *err = "StartCapture failed " + hr_str(hr); return false; }

    log_line("  WGC capture started: item=%s %ux%u pool=CreateFreeThreaded(3 buffers, B8G8R8A8UIntNormalized)",
             kind_, w_, h_);
    return true;
}

bool WgcCapture::try_get_frame(CapturedFrame* out, std::string* err)
{
    err->clear();
    out->texture = nullptr;

    ABI::Windows::Graphics::Capture::IDirect3D11CaptureFrame* frame = nullptr;
    HRESULT hr = ((ABI::Windows::Graphics::Capture::IDirect3D11CaptureFramePool*)pool_)->TryGetNextFrame(&frame);
    if (FAILED(hr)) { *err = "TryGetNextFrame failed " + hr_str(hr); return false; }
    if (!frame) return false;                 // nothing ready — normal, not an error

    uint64_t t_now = qpc_now_ns();
    ABI::Windows::Foundation::TimeSpan ts;
    memset(&ts, 0, sizeof(ts));
    frame->get_SystemRelativeTime(&ts);

    ABI::Windows::Graphics::DirectX::Direct3D11::IDirect3DSurface* surf = nullptr;
    hr = frame->get_Surface(&surf);
    if (FAILED(hr) || !surf) {
        frame->Release();
        *err = "IDirect3D11CaptureFrame::get_Surface failed " + hr_str(hr);
        return false;
    }
    ID3D11Texture2D* tex = nullptr;
    bool got = qi_texture((IUnknown*)surf, &tex);
    surf->Release();
    if (!got) {
        frame->Release();
        *err = "the frame's IDirect3DSurface would not yield an ID3D11Texture2D "
               "(neither a direct QI nor IDirect3DDxgiInterfaceAccess::GetInterface)";
        return false;
    }

    // The pool texture is only ours while the frame object lives; AddRef and release
    // the frame immediately so the pool buffer returns to circulation.
    tex->AddRef();
    frame->Release();

    if (!clock_checked_) {
        clock_checked_ = true;
        long long off = (long long)ts.Duration * 100 - (long long)t_now;
        log_line("  WGC clock check: frame.SystemRelativeTime=%lld.%03llds vs QueryPerformanceCounter=%lld.%03llds  offset=%+lld ms",
                 (long long)(ts.Duration / 10000000), (long long)((ts.Duration / 10000) % 1000),
                 (long long)(t_now / 1000000000), (long long)((t_now / 1000000) % 1000),
                 off / 1000000);
    }

    // SRV for the pixels.  WGC pool textures are not contractually shader-resource
    // bindable, so a failure here is expected on some drivers and is handled by
    // copying into our own BGRA texture once per frame — measured, not assumed.
    ID3D11ShaderResourceView* srv = nullptr;
    hr = dev_->CreateShaderResourceView(tex, nullptr, &srv);
    if (SUCCEEDED(hr) && srv) {
        if (owned_srv_) { owned_srv_->Release(); owned_srv_ = nullptr; }
        owned_srv_ = srv;
        frame_srv_ = srv;
    } else {
        if (!copy_fallback_) {
            D3D11_TEXTURE2D_DESC td;
            tex->GetDesc(&td);
            td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
            td.Usage = D3D11_USAGE_DEFAULT;
            td.CPUAccessFlags = 0;
            td.MiscFlags = 0;
            HRESULT h2 = dev_->CreateTexture2D(&td, nullptr, &bgra_copy_);
            if (FAILED(h2)) {
                tex->Release();
                *err = "neither an SRV on the WGC texture (" + hr_str(hr) +
                       ") nor a fallback BGRA texture (" + hr_str(h2) + ") could be created";
                return false;
            }
            h2 = dev_->CreateShaderResourceView(bgra_copy_, nullptr, &bgra_srv_);
            if (FAILED(h2)) {
                tex->Release();
                *err = "CreateShaderResourceView(fallback BGRA) failed " + hr_str(h2);
                return false;
            }
            copy_fallback_ = true;
            log_line("  WGC note: pool texture is not SRV-bindable (%s); using an explicit "
                     "CopyResource into our own BGRA texture", hr_str(hr).c_str());
        }
        if (!ctx_) dev_->GetImmediateContext(&ctx_);
        ctx_->CopyResource(bgra_copy_, tex);
        frame_srv_ = bgra_srv_;
    }

    out->texture  = tex;
    out->qpc_ns   = t_now;
    out->sys_rel_ns = (uint64_t)(ts.Duration * 100);
    out->width    = w_;
    out->height   = h_;
    ++delivered_;
    return true;
}

void WgcCapture::release()
{
    if (session_) { ((IUnknown*)session_)->Release(); session_ = nullptr; }
    if (pool_)    { ((IUnknown*)pool_)->Release();    pool_    = nullptr; }
    if (d3d_device_) { ((IUnknown*)d3d_device_)->Release(); d3d_device_ = nullptr; }
    if (owned_srv_) { owned_srv_->Release(); owned_srv_ = nullptr; }
    frame_srv_ = nullptr;
    if (bgra_srv_)  { bgra_srv_->Release();  bgra_srv_  = nullptr; }
    if (bgra_copy_) { bgra_copy_->Release(); bgra_copy_ = nullptr; }
    if (ctx_)       { ctx_->Release();       ctx_       = nullptr; }
    dev_ = nullptr;
    item_ = nullptr;
}

} // namespace aireplay
