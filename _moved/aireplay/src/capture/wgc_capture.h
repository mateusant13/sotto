// wgc_capture.h — Windows Graphics Capture, item chosen PROGRAMMATICALLY.
//
// Spec 03 §2.1.  Two things this file is careful about:
//   * the capture item comes from IGraphicsCaptureItemInterop::CreateForWindow /
//     CreateForMonitor, reached from the activation factory — there is NO
//     GraphicsCapturePicker, so no dialog and no window ever appears;
//   * the frame pool is CreateFreeThreaded, so no message pump, no UI thread, and the
//     shipping process has no window at all.
//
// frame.SystemRelativeTime is the QPC-based clock the transcript and OCR must share
// (research 01 §1); the first frame's offset against QueryPerformanceCounter is logged
// once so the claim "same clock" is a measurement, not a reading.
#pragma once
#include "common.h"

namespace aireplay {

struct CapturedFrame {
    ID3D11Texture2D* texture = nullptr;   // AddRef'd — the caller MUST Release it
    uint64_t qpc_ns = 0;                  // QueryPerformanceCounter at retrieval
    uint64_t sys_rel_ns = 0;              // frame.SystemRelativeTime, converted to ns
    uint32_t width = 0, height = 0;
};

class WgcCapture {
public:
    bool start_for_window(ID3D11Device* dev, HWND hwnd, std::string* err);
    bool start_for_monitor(ID3D11Device* dev, HMONITOR mon, std::string* err);

    // false + empty err means "no frame ready right now" (normal, not an error).
    // false + non-empty err means the capture itself failed.
    bool try_get_frame(CapturedFrame* out, std::string* err);

    void release();

    uint32_t width() const  { return w_; }
    uint32_t height() const { return h_; }
    const char* item_kind() const { return kind_; }
    // true once we have seen at least one frame — the liveness watchdog's raw signal.
    bool ever_delivered() const { return delivered_ > 0; }
    uint64_t delivered() const { return delivered_; }

private:
    bool start_common(ID3D11Device* dev, void* item, std::string* err);

    ID3D11Device*                    dev_        = nullptr;   // not owned
    void*                            d3d_device_ = nullptr;   // WinRT IDirect3DDevice*, held as void*
                                                              // so this header needs no WinRT includes
    void*                            item_       = nullptr;   // IGraphicsCaptureItem*
    void*                            pool_       = nullptr;   // IDirect3D11CaptureFramePool*
    void*                            session_    = nullptr;   // IGraphicsCaptureSession*
    uint32_t                         w_ = 0, h_ = 0;
    const char*                      kind_ = "?";
    uint64_t                         delivered_ = 0;
    bool                             clock_checked_ = false;
    // Fallback path: WGC pool textures are not contractually SRV-able, so if the
    // direct view fails we keep our own BGRA texture and CopyResource into it.
    ID3D11Texture2D*                 bgra_copy_ = nullptr;
    ID3D11ShaderResourceView*        bgra_srv_  = nullptr;
    ID3D11DeviceContext*             ctx_       = nullptr;   // cached, only used by the fallback
    bool                             copy_fallback_ = false;
public:
    // The SRV for the most recent frame's pixels (either the pool texture's own view or
    // our copy).  Valid until the next try_get_frame().
    ID3D11ShaderResourceView* last_srv() const { return frame_srv_; }
    bool using_copy_fallback() const { return copy_fallback_; }
private:
    ID3D11ShaderResourceView*        frame_srv_ = nullptr;
    ID3D11ShaderResourceView*        owned_srv_ = nullptr;   // our own SRV on a pool texture
};

} // namespace aireplay
