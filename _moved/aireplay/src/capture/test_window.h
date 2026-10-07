// test_window.h — OUR OWN window, so this lane never captures the owner's desktop.
//
// The brief for this lane is explicit: do not capture the owner's screen without saying
// so.  So the capture proof runs against a window this process creates and paints itself,
// placed OFF the virtual desktop.  Its rect and its visibility are logged, and a 25 ms
// census over this process's own HWNDs is what proves nothing appeared on his screen.
#pragma once
#include "common.h"

namespace aireplay {

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

private:
    static LRESULT CALLBACK wnd_proc(HWND, UINT, WPARAM, LPARAM);
    static DWORD WINAPI thread_entry(LPVOID self);
    static void thread_main(TestWindow* self);

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
};

} // namespace aireplay
