// wgc-probe.cpp — WHY does IGraphicsCaptureItemInterop::CreateForWindow return
// E_ACCESSDENIED (0x80070005) on this box?  The product's capture lane saw the failure begin
// partway through a session and then persist, so this probe separates the candidates:
//   (a) our own window      -> the window/style/layered path
//   (b) the foreground window -> somebody else's window
//   (c) the desktop window  -> a system window
//   (d) CreateForMonitor    -> the monitor path
//   (e) GraphicsCaptureSession::IsSupported
//   (f) the per-exe consent gate (CapabilityAccessManager), read from the registry elsewhere
//
// Build (mingw, no MSVC):
//   g++ -std=c++17 -O2 -I third_party wgc-probe.cpp -o wgc-probe.exe \
//       -lole32 -loleaut32 -lruntimeobject -lwindowsapp -luuid -luser32 -lgdi32

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <roapi.h>
#include <winstring.h>
#include <inspectable.h>
#include <windows.graphics.capture.h>
#include <windows.graphics.capture.interop.h>
#include <cstdio>

using namespace ABI::Windows::Graphics::Capture;

static const GUID kIID_ItemInterop =
    { 0x3628e81b, 0x3cac, 0x4c60, { 0xb7, 0xf4, 0x23, 0xce, 0x0e, 0x0c, 0x33, 0x56 } };
static const GUID kIID_Item =
    { 0x79c3f95b, 0x31f7, 0x4ec2, { 0xa4, 0x64, 0x63, 0x2e, 0xf5, 0xd3, 0x07, 0x60 } };

static void say(const char* fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    printf("\n");
    fflush(stdout);
}

static const char* hname(HRESULT hr)
{
    switch ((unsigned)hr) {
    case 0x80070005u: return "E_ACCESSDENIED";
    case 0x800401F0u: return "CO_E_NOTINITIALIZED";
    case 0x80070057u: return "E_INVALIDARG";
    case 0x80004005u: return "E_FAIL";
    case 0x8007000Eu: return "E_OUTOFMEMORY";
    case 0x80070490u: return "ERROR_NOT_FOUND";
    default: return "";
    }
}

static IGraphicsCaptureItemInterop* g_interop = nullptr;

static bool init_interop()
{
    HRESULT hr = RoInitialize(RO_INIT_MULTITHREADED);
    say("RoInitialize                       -> 0x%08lX %s", (unsigned long)hr,
        hr == RPC_E_CHANGED_MODE ? "(RPC_E_CHANGED_MODE: already initialised, fine)" : hname(hr));
    if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) return false;

    HSTRING cls = nullptr;
    const wchar_t* name = L"Windows.Graphics.Capture.GraphicsCaptureItem";
    hr = WindowsCreateString(name, (UINT32)wcslen(name), &cls);
    if (FAILED(hr)) { say("WindowsCreateString                -> 0x%08lX", (unsigned long)hr); return false; }
    hr = RoGetActivationFactory(cls, kIID_ItemInterop, (void**)&g_interop);
    WindowsDeleteString(cls);
    say("RoGetActivationFactory(item interop) -> 0x%08lX %s", (unsigned long)hr, hname(hr));
    return SUCCEEDED(hr) && g_interop;
}

static void try_window(const char* label, HWND h)
{
    if (!h) { say("CreateForWindow(%-22s) -> SKIPPED (null hwnd)", label); return; }
    void* item = nullptr;
    HWND root = GetAncestor(h, GA_ROOT);
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    HRESULT hr = g_interop->CreateForWindow(h, kIID_Item, &item);
    say("CreateForWindow(%-22s) -> 0x%08lX %-18s hwnd=%p root=%p pid=%lu item=%p",
        label, (unsigned long)hr, hname(hr), (void*)h, (void*)root, (unsigned long)pid, item);
    if (item) ((IUnknown*)item)->Release();
}

static void try_monitor(const char* label, HMONITOR m)
{
    void* item = nullptr;
    HRESULT hr = g_interop->CreateForMonitor(m, kIID_Item, &item);
    say("CreateForMonitor(%-20s) -> 0x%08lX %-18s item=%p", label, (unsigned long)hr, hname(hr), item);
    if (item) ((IUnknown*)item)->Release();
}

static LRESULT CALLBACK wp(HWND h, UINT m, WPARAM w, LPARAM l) { return DefWindowProcW(h, m, w, l); }

int main(int argc, char** argv)
{
    say("=== WGC CreateForWindow probe ===");
    if (!init_interop()) { say("interop unavailable; stopping"); return 1; }

    // (e) IsSupported
    HSTRING cls = nullptr;
    const wchar_t* sess = L"Windows.Graphics.Capture.GraphicsCaptureSession";
    static const GUID kIID_SessionStatics =
        { 0x2224A540, 0x5974, 0x49E6, { 0xB6, 0xE1, 0x7D, 0x1A, 0x2C, 0x1B, 0x8F, 0x3C } };
    if (SUCCEEDED(WindowsCreateString(sess, (UINT32)wcslen(sess), &cls))) {
        void* statics = nullptr;
        HRESULT hr = RoGetActivationFactory(cls, kIID_SessionStatics, &statics);
        WindowsDeleteString(cls);
        if (SUCCEEDED(hr) && statics) {
            boolean sup = 0;
            // IsSupported is the 2nd slot after the 3 IInspectable methods.
            typedef HRESULT(STDMETHODCALLTYPE * FnIsSupported)(void*, boolean*);
            void** vt = *(void***)statics;
            FnIsSupported f = (FnIsSupported)vt[6];
            hr = f(statics, &sup);
            say("GraphicsCaptureSession::IsSupported -> 0x%08lX supported=%d", (unsigned long)hr, (int)sup);
            ((IUnknown*)statics)->Release();
        } else {
            say("GraphicsCaptureSession statics      -> 0x%08lX %s", (unsigned long)hr, hname(hr));
        }
    }

    // our own plain window
    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = wp;
    wc.hInstance = GetModuleHandleW(nullptr);
    wc.lpszClassName = L"AireplayWgcProbe";
    RegisterClassExW(&wc);
    HWND own = CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, wc.lpszClassName,
                               L"wgc probe", WS_POPUP | WS_VISIBLE, 0, 0, 200, 200,
                               nullptr, nullptr, wc.hInstance, nullptr);
    say("own window: %p (IsWindowVisible=%d)", (void*)own, own ? (int)IsWindowVisible(own) : 0);

    try_window("our own window", own);
    try_window("foreground window", GetForegroundWindow());
    try_window("desktop window", GetDesktopWindow());
    try_window("shell taskbar", FindWindowW(L"Shell_TrayWnd", nullptr));
    try_monitor("primary monitor", MonitorFromPoint(POINT{ 0, 0 }, MONITOR_DEFAULTTOPRIMARY));

    if (own) DestroyWindow(own);
    say("=== done ===");
    (void)argc; (void)argv;
    return 0;
}
