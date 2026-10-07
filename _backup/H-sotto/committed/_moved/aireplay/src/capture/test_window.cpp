#include "test_window.h"

namespace aireplay {

static const wchar_t* kClass = L"AireplayCaptureTestWindow";
static TestWindow*    g_self  = nullptr;

TestWindow::~TestWindow() { stop(); }

LRESULT CALLBACK TestWindow::wnd_proc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    TestWindow* self = g_self;
    switch (m) {
    case WM_TIMER:
        if (self) InvalidateRect(h, nullptr, FALSE);
        return 0;
    case WM_ERASEBKGND:
        return 1;   // painted in WM_PAINT; no flicker, and no extra GDI pass
    case WM_PAINT: {
        uint64_t t0 = qpc_now_ns();
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(h, &ps);
        uint64_t n = self ? self->paints_.fetch_add(1) + 1 : 1;

        RECT rc;
        GetClientRect(h, &rc);
        // Paint ONLY the dirty region.  MEASURED: a full 1920x1080 FillRect per frame costs
        // ~29 ms of GDI/DWM and capped the test source at ~34 fps (smoke-05) ÔÇö the source
        // would then look like the pipeline's limit.  A moving 1920x120 band keeps the
        // content genuinely changing every frame (so WGC delivers every frame) at a
        // fraction of the paint cost.
        RECT dirty = ps.rcPaint;
        if (dirty.right <= dirty.left || dirty.bottom <= dirty.top) dirty = rc;

        HBRUSH bg = CreateSolidBrush(RGB((int)((n * 7) & 0xFF), (int)((n * 3) & 0xFF), (int)((n * 11) & 0xFF)));
        FillRect(dc, &dirty, bg);
        DeleteObject(bg);

        // REAL entropy, one StretchBlt per frame.  Without it the synthetic source cost
        // ~130 bytes/frame and the ring never filled, so the ring's RAM and its eviction
        // path could not be measured at all (smoke-08: 132 frames = 17 138 bytes).
        if (self && self->memdc_) {
            int off = (int)((n * 37) & 0xFF);
            StretchBlt(dc, dirty.left, dirty.top,
                       dirty.right - dirty.left, dirty.bottom - dirty.top,
                       self->memdc_, off, (off * 3) & 0xFF, 256 - off, 256 - ((off * 3) & 0xFF),
                       SRCCOPY);
        }

        int bw = (rc.right - rc.left) / 8;
        if (bw < 1) bw = 1;
        int bx = (int)((n * 23) % (uint64_t)(rc.right > bw ? rc.right - bw : 1));
        RECT bar;
        bar.left = bx;
        bar.top = dirty.top;
        bar.right = bx + bw;
        bar.bottom = dirty.bottom;
        RECT clip;
        if (IntersectRect(&clip, &bar, &dirty)) {
            HBRUSH fg = CreateSolidBrush(RGB(255, 255, 255));
            FillRect(dc, &clip, fg);
            DeleteObject(fg);
        }

        wchar_t txt[64];
        _snwprintf_s(txt, _TRUNCATE, L"aireplay capture self-test  frame %llu", (unsigned long long)n);
        SetBkMode(dc, TRANSPARENT);
        SetTextColor(dc, RGB(0, 0, 0));
        TextOutW(dc, 16, 16, txt, (int)wcslen(txt));

        EndPaint(h, &ps);
        if (self) self->paint_ns_.fetch_add(qpc_now_ns() - t0);
        return 0;
    }
    case WM_CLOSE:
        return 0;
    case WM_DESTROY:
        if (self) self->quit_ = true;
        PostQuitMessage(0);
        return 0;
    default:
        break;
    }
    return DefWindowProcW(h, m, w, l);
}

DWORD WINAPI TestWindow::thread_entry(LPVOID self) { thread_main((TestWindow*)self); return 0; }

void TestWindow::thread_main(TestWindow* self)
{
    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = &TestWindow::wnd_proc;
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.hCursor = nullptr;
    wc.hbrBackground = nullptr;
    wc.lpszClassName = kClass;
    RegisterClassExW(&wc);

    // MEASURED (smoke-15): with the window 99.8% OUTSIDE the virtual desktop, WGC delivered
    // frames but every one of them was a UNIFORM BLACK image ÔÇö DWM has nothing to compose
    // beyond the desktop bounds.  The clip was real (283 frames, monotonic, decodable) but
    // its content was black, which makes the encoded BITRATE meaningless and the ring's
    // eviction path unreachable.  `alpha_ >= 0` selects the alternative: a WS_EX_LAYERED
    // window covering the WHOLE desktop at that alpha.  At alpha=1 it is imperceptible to
    // the owner (1/255 = 0.4%) and it is fully composed, so the encoder sees real pixels.
    DWORD ex_style = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
    if (self->alpha_ >= 0) {
        ex_style |= WS_EX_LAYERED;
        self->x_ = GetSystemMetrics(SM_XVIRTUALSCREEN);
        self->y_ = GetSystemMetrics(SM_YVIRTUALSCREEN);
        self->w_ = (uint32_t)GetSystemMetrics(SM_CXVIRTUALSCREEN);
        self->h_ = (uint32_t)GetSystemMetrics(SM_CYVIRTUALSCREEN);
        self->on_desktop_ = true;
    } else if (self->x_ == INT_MIN || self->y_ == INT_MIN) {
        const int vx = GetSystemMetrics(SM_XVIRTUALSCREEN);
        const int vy = GetSystemMetrics(SM_YVIRTUALSCREEN);
        const int vw = GetSystemMetrics(SM_CXVIRTUALSCREEN);
        const int vh = GetSystemMetrics(SM_CYVIRTUALSCREEN);
        const int ov = 4;
        self->x_ = vx + vw - ov;
        self->y_ = vy + vh - ov;
    }

    // WS_EX_TOOLWINDOW: never in the taskbar, never in Alt+Tab.  WS_EX_NOACTIVATE: it
    // cannot steal focus from the owner.  WS_POPUP: no frame, no caption.
    HWND h = CreateWindowExW(ex_style,
                             kClass, L"aireplay self-test (4x4 sliver, bottom-right)",
                             WS_POPUP | WS_VISIBLE,
                             self->x_, self->y_, (int)self->w_, (int)self->h_,
                             nullptr, nullptr, GetModuleHandleW(nullptr), nullptr);
    if (!h) {
        log_line("  TEST WINDOW: CreateWindowExW FAILED, GetLastError=%lu", GetLastError());
        self->quit_ = true;
        return;
    }
    self->hwnd_ = h;
    self->tid_ = GetCurrentThreadId();
    if (self->alpha_ >= 0) {
        BOOL ok = SetLayeredWindowAttributes(h, 0, (BYTE)self->alpha_, LWA_ALPHA);
        log_line("  TEST WINDOW: layered alpha=%d SetLayeredWindowAttributes=%s (this window "
                 "covers the whole desktop and is %s)",
                 self->alpha_, ok ? "ok" : "FAILED",
                 self->alpha_ <= 2 ? "effectively invisible" : "VISIBLE");
    }
    ShowWindow(h, SW_SHOWNOACTIVATE);
    UpdateWindow(h);
    SetWindowPos(h, self->top_ ? HWND_TOP : HWND_BOTTOM, 0, 0, 0, 0,
                 SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE);

    // A 256x256 random-pixel source, so the encoder sees REAL entropy.  Without it the
    // synthetic source cost ~130 bytes/frame and the ring never filled, which would make
    // the ring's RAM and its eviction path unmeasurable.
    {
        BITMAPINFO bi;
        memset(&bi, 0, sizeof(bi));
        bi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bi.bmiHeader.biWidth = 256;
        bi.bmiHeader.biHeight = -256;          // top-down
        bi.bmiHeader.biPlanes = 1;
        bi.bmiHeader.biBitCount = 32;
        bi.bmiHeader.biCompression = BI_RGB;
        void* bits = nullptr;
        HDC screen = GetDC(nullptr);
        self->memdc_ = CreateCompatibleDC(screen);
        self->noise_ = CreateDIBSection(screen, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
        ReleaseDC(nullptr, screen);
        if (self->noise_ && bits) {
            uint32_t* px = (uint32_t*)bits;
            uint32_t s = 0x12345678u;
            for (int i = 0; i < 256 * 256; ++i) {
                s ^= s << 13; s ^= s >> 17; s ^= s << 5;
                px[i] = s | 0xFF000000u;
            }
            self->oldbmp_ = (HBITMAP)SelectObject(self->memdc_, self->noise_);
        } else {
            log_line("  TEST WINDOW: could not build the noise source; the encoded bitrate "
                     "will be far below the mode's target");
        }
    }

    RECT r;
    GetWindowRect(h, &r);
    log_line("  TEST WINDOW: hwnd=%p rect=(%d,%d)-(%d,%d) size=%ux%u IsWindowVisible=%d  %s",
             (void*)h, r.left, r.top, r.right, r.bottom, self->w_, self->h_,
             IsWindowVisible(h) ? 1 : 0,
             self->on_desktop_
                 ? "WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|HWND_BOTTOM; covers the whole "
                   "desktop at alpha 1/255, so it is composed (real pixels reach the encoder) and "
                   "imperceptible to the owner"
                 : "WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|HWND_BOTTOM; only a 4x4 px corner of this "
                   "window is on the desktop, at its bottom-right, under the taskbar -- and MEASURED, "
                   "an off-desktop window is captured as uniform BLACK");

    // MEASURED (smoke-10): a 1 ms MsgWaitForMultipleObjects timeout is quantised to the
    // system tick (~15.6 ms), so the loop ran at 68 iterations/s and painted at 34/s
    // (loop_iters=407, paints=205 in 6 s) even though the paint itself costs 0.20 ms.
    // A HIGH-RESOLUTION waitable timer gives a ~1 ms clock WITHOUT raising the global
    // timer resolution (which would change the owner's power behaviour for every process).
#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif
    HANDLE htimer = CreateWaitableTimerExW(nullptr, nullptr,
                                           CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,
                                           TIMER_ALL_ACCESS);
    if (!htimer) {
        log_line("  TEST WINDOW: CreateWaitableTimerExW(HIGH_RESOLUTION) failed (%lu); "
                 "falling back to a coarse clock", GetLastError());
        htimer = CreateWaitableTimerW(nullptr, FALSE, nullptr);
    }
    LARGE_INTEGER due;
    due.QuadPart = -10000;                 // first fire in 1 ms
    // 15 ms => ~66 Hz, just above the display's own composition rate.  MEASURED: at 16 ms
    // the source painted 65/s and WGC delivered 57/s; at 12 ms it painted 86/s and WGC
    // delivered 55/s ÔÇö WGC cannot outrun DWM's composition rate, so over-driving buys
    // nothing and only costs DWM work.  The achieved rate is reported, never assumed.
    SetWaitableTimer(htimer, &due, 15, nullptr, nullptr, FALSE);

    int band = 0;
    const int band_h = 120;

    MSG msg;
    while (!self->quit_) {
        DWORD w = MsgWaitForMultipleObjects(1, &htimer, FALSE, INFINITE, QS_ALLINPUT);
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) {
            if (msg.message == WM_QUIT) { self->quit_ = true; break; }
            TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
        if (self->quit_) break;
        self->loop_iters_.fetch_add(1);
        if (w != WAIT_OBJECT_0) continue;   // a message woke us, not the paint clock

        uint64_t u0 = qpc_now_ns();
        if (self->on_desktop_) {
            // The whole desktop-sized window is composed, so the WHOLE frame is dirtied and
            // every frame is genuinely new content ÔÇö which is what makes the encoded bitrate
            // comparable to the mode's target.
            RECT full;
            full.left = 0; full.top = 0;
            full.right = (LONG)self->w_; full.bottom = (LONG)self->h_;
            InvalidateRect(h, &full, FALSE);
        } else {
        RECT r;
        r.left = 0;
        r.top = band;
        r.right = (LONG)self->w_;
        r.bottom = band + band_h;
        band += 37;
        if (band > (int)self->h_) band = 0;
        InvalidateRect(h, &r, FALSE);
        // MEASURED (smoke-06): WGC only delivers a frame when the window's ON-SCREEN
        // region changes.  With a 4x4 px sliver on the desktop and a moving band that
        // quickly leaves that sliver, 278 paints produced only 10 frames.  So the sliver
        // is dirtied on EVERY tick, which is what makes the capture run at the source's
        // real rate while the paint itself stays cheap.
        RECT sliver;
        sliver.left = 0; sliver.top = 0; sliver.right = 8; sliver.bottom = 8;
        InvalidateRect(h, &sliver, FALSE);
        }
        UpdateWindow(h);
        self->update_ns_.fetch_add(qpc_now_ns() - u0);
    }

    if (htimer) { CancelWaitableTimer(htimer); CloseHandle(htimer); }
    if (self->memdc_) {
        if (self->oldbmp_) SelectObject(self->memdc_, self->oldbmp_);
        DeleteDC(self->memdc_);
        self->memdc_ = nullptr;
    }
    if (self->noise_) { DeleteObject(self->noise_); self->noise_ = nullptr; }
    DestroyWindow(h);
    self->hwnd_ = nullptr;
}

bool TestWindow::create(uint32_t w, uint32_t h, int x, int y, std::string* err)
{
    w_ = w; h_ = h; x_ = x; y_ = y;
    g_self = this;
    thread_ = CreateThread(nullptr, 0, &TestWindow::thread_entry, this, 0, nullptr);
    if (!thread_) { *err = "CreateThread for the test window failed"; return false; }
    for (int i = 0; i < 400 && !hwnd_ && !quit_; ++i) Sleep(5);
    if (!hwnd_) { *err = "the test window never came up"; return false; }
    return true;
}

void TestWindow::stop()
{
    if (hwnd_ && tid_) PostThreadMessageW(tid_, WM_QUIT, 0, 0);
    quit_ = true;
    if (thread_) {
        WaitForSingleObject(thread_, 3000);
        CloseHandle(thread_);
        thread_ = nullptr;
    }
    hwnd_ = nullptr;
    g_self = nullptr;
}

} // namespace aireplay
