// test_window.h — OUR OWN window, so this lane never captures the owner's desktop.
//
// The brief for this lane is explicit: do not capture the owner's screen without saying
// so.  So the capture proof runs against a window this process creates and paints itself,
// placed OFF the virtual desktop.  Its rect and its visibility are logged, and a 25 ms
// census over this process's own HWNDs is what proves nothing appeared on his screen.
//
// THIS HEADER ALSO OWNS THE OUTPUT-DESKTOP QUESTION, because that is the same question:
// "where is the display, how big is it, in PHYSICAL pixels, and what happens when it
// changes under us".  `replay.cpp` used to answer it with the literal 1920x1080
// (replay.cpp:57 in the pre-lane revision), which made every 1440p/4K number in this repo
// arithmetic rather than measurement.  The two halves live together deliberately:
//
//   DesktopInfo            — a MEASURED snapshot of the output desktop.
//   negotiate_capture_window() — a PURE function: request + snapshot -> decision + why.
//
// Pure matters: the negotiation is testable over synthetic desktops (2560x1440, 3840x2160,
// a 1366x768 panel, a 150% high-DPI desktop) on a machine whose only monitor is 1080p,
// with no GPU, no WGC, no window and no encoder.  That is what makes the gate honest.
#pragma once
#include "common.h"

namespace aireplay {

// The product's documented anchor size.  It is the FALLBACK, not the answer: on a desktop
// of this size the negotiation returns exactly these numbers and every byte of the 1080p
// path is unchanged, which is the lane's regression guard.
constexpr uint32_t kDefaultCaptureW = 1920;
constexpr uint32_t kDefaultCaptureH = 1080;

// ------------------------------------------------------------------ the desktop, measured
struct DesktopInfo {
    uint32_t mon_w = 0;        // PRIMARY monitor, PHYSICAL pixels (0 = unmeasured)
    uint32_t mon_h = 0;
    uint32_t virt_w = 0;       // virtual desktop extent, as this process SEES it
    uint32_t virt_h = 0;
    uint32_t dpi = 0;          // 0 = unmeasured
    int      awareness = -1;   // -1 = unmeasured, else DPI_AWARENESS_* from winuser.h
    bool     mon_is_physical = false;   // mon_* came from EnumDisplaySettings (physical)
    bool     metrics_virtualised = false;  // the process is DPI-unaware: SM_* are LOGICAL
    bool     valid = false;
    std::string note;          // says which source answered, and any disagreement
};

// Reads the output desktop.  Never fails hard: an unmeasured desktop is reported as
// `valid=false` and the caller falls back, because "no desktop" must not mean "no capture".
DesktopInfo query_output_desktop();

// ------------------------------------------------------------------ the negotiation, pure
struct WindowDecision {
    enum class Source {
        Fallback,           // no usable desktop measured -> the product's anchor size
        Desktop,            // auto request -> the desktop's own size
        Monitor,            // auto request, sized by the primary monitor
        RequestedAsIs,      // the caller asked for it and the desktop can carry it
        RequestedClampedToMonitor,  // the caller asked for more than the desktop has
    };
    uint32_t w = 0;
    uint32_t h = 0;
    Source   source = Source::Fallback;
    bool     requested_auto = false;
    bool     clamped = false;          // the request was REDUCED
    bool     even_floored = false;     // an odd request was floored (NV12 needs even sides)
    std::string note;                  // one line, human-readable, for the log

    bool ok() const { return w > 0 && h > 0; }
};

// The whole point of the lane, as one pure function.
//
//   req_w==0 or req_h==0  ->  auto: use the output desktop's own size.
//   a request the desktop cannot carry -> CLAMP to what it can carry, and say so.
//   odd dimensions -> floored to even, because the NV12 plane 1 is a half-size R8G8 view.
//   an unmeasured desktop -> the anchor size, and the note says the desktop was unmeasured.
//
// Byte-identity at 1080p is a property of this function: on a 1920x1080 desktop a 1920x1080
// request returns exactly 1920x1080 with source=RequestedAsIs.
WindowDecision negotiate_capture_window(uint32_t req_w, uint32_t req_h, const DesktopInfo& d);

const char* window_source_name(WindowDecision::Source s);

class TestWindow {
public:
    ~TestWindow();

    // x/y default to a point beyond every monitor; the window is still WS_VISIBLE so DWM
    // composes it (WGC captures composition surfaces, not screen pixels).
    bool create(uint32_t w, uint32_t h, int x, int y, std::string* err);
    void stop();

    HWND hwnd() const { return hwnd_; }
    uint64_t paint_count() const { return paints_; }
    // How long the test source itself spends painting — so a low capture rate can be
    // attributed to the HARNESS instead of being read as the pipeline's limit.
    uint64_t paint_ns() const { return paint_ns_; }
    uint64_t loop_iters() const { return loop_iters_; }
    uint64_t update_ns() const { return update_ns_; }   // time inside InvalidateRect+UpdateWindow
    void set_topmost(bool top) { top_ = top; }
    void set_alpha(int a) { alpha_ = a; }
    bool created_on_desktop() const { return on_desktop_; }

    // ---- resolution change while running -------------------------------------------------
    // The window covers the output desktop, so a mode change is delivered to it as
    // WM_DISPLAYCHANGE / WM_SIZE.  These are the three questions the run loop asks; the
    // counters are atomic and cheap so the run loop can poll them every frame.
    uint32_t display_changes() const { return display_changes_.load(); }
    uint32_t desktop_w() const { return desktop_w_.load(); }
    uint32_t desktop_h() const { return desktop_h_.load(); }
    bool     display_changed() const { return display_changes_.load() != 0; }
    // NOTE: there is deliberately no resize_to().  A mode change mid-run cannot be
    // absorbed by moving the window: the NVENC session and the ring are sized at arm
    // time, so the honest handling is for the run loop to REFUSE and say so, not to
    // quietly keep encoding frames of the new size into an old-size stream.

private:
    static LRESULT CALLBACK wnd_proc(HWND, UINT, WPARAM, LPARAM);
    static DWORD WINAPI thread_entry(LPVOID self);
    static void thread_main(TestWindow* self);
    void note_display_size(uint32_t w, uint32_t h, bool from_user);

    HDC     memdc_ = nullptr;      // 256x256 noise source, so the encoder sees REAL entropy
    HBITMAP noise_ = nullptr;
    HBITMAP oldbmp_ = nullptr;

    HWND     hwnd_ = nullptr;
    HANDLE   thread_ = nullptr;
    uint32_t w_ = 0, h_ = 0;
    int      x_ = 0, y_ = 0;
    DWORD    tid_ = 0;
    std::atomic<uint64_t> paints_{0};
    std::atomic<uint64_t> paint_ns_{0};
    std::atomic<uint64_t> loop_iters_{0};
    std::atomic<uint64_t> update_ns_{0};
    std::atomic<bool>     quit_{false};
    bool                  top_ = false;
    int                   alpha_ = -1;      // >=0 => WS_EX_LAYERED with this alpha (1 = invisible)
    bool                  on_desktop_ = false;

    // Display-change tracking.  `tracking_` gates the first WM_SIZE, which is the window
    // being shown rather than the desktop changing.
    std::atomic<uint32_t> display_changes_{0};
    std::atomic<uint32_t> desktop_w_{0};
    std::atomic<uint32_t> desktop_h_{0};
    bool                  tracking_ = false;
};

} // namespace aireplay