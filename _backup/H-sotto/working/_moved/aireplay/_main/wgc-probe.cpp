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

// ---------------------------------------------------------------------------------------
// (f) GraphicsCaptureAccess::RequestAccessAsync(Programmatic)
//
// The ONE call Microsoft documents for "this app has not been granted programmatic screen
// capture", and the only recovery this lane is authorised to try — the alternatives
// (sign-out, reboot, DWM restart) kill a live transcription session or disrupt the machine.
//
// mingw ships no Windows SDK, so there is no IID for IGraphicsCaptureAccessStatics.  It is
// not needed: EVERY WinRT activation factory implements IInspectable, so
// RoGetActivationFactory(cls, IID_IInspectable, ...) is guaranteed to hand back the factory,
// and GraphicsCaptureAccess declares exactly ONE static method — so the first vtable slot
// after IUnknown(3) + IInspectable(3) is RequestAccessAsync.  Every call below is guarded by
// its own HRESULT before the next one is made, so a wrong assumption stops here instead of
// jumping through a bad function pointer.
static void try_request_access()
{
    static const GUID kIID_Inspectable =
        { 0xaf86e2e0, 0xb12d, 0x4c6a, { 0x9c, 0x5a, 0xd7, 0xaa, 0x65, 0x10, 0x1e, 0x90 } };
    static const GUID kIID_AsyncInfo =
        { 0x00000036, 0x0000, 0x0000, { 0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46 } };

    say("--- (f) GraphicsCaptureAccess::RequestAccessAsync(Programmatic) ---");
    HSTRING cls = nullptr;
    const wchar_t* name = L"Windows.Graphics.Capture.GraphicsCaptureAccess";
    HRESULT hr = WindowsCreateString(name, (UINT32)wcslen(name), &cls);
    if (FAILED(hr)) { say("WindowsCreateString(GraphicsCaptureAccess) -> 0x%08lX", (unsigned long)hr); return; }

    void* factory = nullptr;
    hr = RoGetActivationFactory(cls, kIID_Inspectable, &factory);
    WindowsDeleteString(cls);
    say("RoGetActivationFactory(GraphicsCaptureAccess, IInspectable) -> 0x%08lX %s",
        (unsigned long)hr, hname(hr));
    if (FAILED(hr) || !factory) { say("cannot reach the statics without the SDK IID; stopping here"); return; }

    typedef HRESULT(STDMETHODCALLTYPE * FnRequest)(void*, int, void**);
    void** vt = *(void***)factory;
    FnRequest req = (FnRequest)vt[6];              // GraphicsCaptureAccessKind: Programmatic = 0
    void* op = nullptr;
    hr = req(factory, 0, &op);
    say("RequestAccessAsync(Programmatic) -> 0x%08lX %s  op=%p", (unsigned long)hr, hname(hr), op);
    if (FAILED(hr) || !op) { say("no async operation returned; nothing further to read"); return; }

    IAsyncInfo* info = nullptr;
    hr = ((IUnknown*)op)->QueryInterface(kIID_AsyncInfo, (void**)&info);
    say("QueryInterface(IAsyncInfo) -> 0x%08lX %s", (unsigned long)hr, hname(hr));
    if (SUCCEEDED(hr) && info) {
        AsyncStatus st = Started;
        for (int i = 0; i < 200; ++i) {            // up to ~10 s
            st = Started;
            if (FAILED(info->get_Status(&st))) break;
            if (st != Started) break;
            Sleep(50);
        }
        HRESULT ec = S_OK;
        info->get_ErrorCode(&ec);
        say("async status = %d (0=Started 1=Completed 2=Canceled 3=Error)  errorCode=0x%08lX",
            (int)st, (unsigned long)ec);
        if (st == Completed) {
            // IAsyncOperation<T> vtable: put_Completed(11) get_Completed(12) GetResults(13)
            typedef HRESULT(STDMETHODCALLTYPE * FnResults)(void*, int*);
            FnResults res = (FnResults)(*(void***)op)[13];
            int status = -1;
            HRESULT hr2 = res(op, &status);
            const char* meaning =
                status == 0 ? "Allowed" :
                status == 1 ? "DeniedBySystem" :
                status == 2 ? "DeniedByUser" :
                status == 3 ? "NotDeclaredByApp" :
                status == 4 ? "UserPromptRequired" : "(unknown)";
            say("GetResults -> 0x%08lX  GraphicsCaptureAccessStatus = %d (%s)",
                (unsigned long)hr2, status, meaning);
        }
        info->Release();
    }
    ((IUnknown*)op)->Release();
    ((IUnknown*)factory)->Release();
}

// ---------------------------------------------------------------------------------------
// (f2) FIND the statics IID, then make the call.
//
// WHY A SEARCH AND NOT A GUESS: mingw ships no Windows SDK, so IGraphicsCaptureAccessStatics
// has no IID here.  A GUESSED VTABLE SLOT IS NOT SAFE — the first attempt called slot 6 of
// the object RoGetActivationFactory returns, which is IActivationFactory::ActivateInstance
// (the factory's FIRST interface is always IActivationFactory, not the statics), passed a
// null HSTRING* and took an access violation.  A GUESSED IID *IS* SAFE: RoGetActivationFactory
// with an unknown IID returns E_NOINTERFACE and nothing else happens.
//
// So the candidates come from the OS's own metadata (Windows.Graphics.winmd), extracted by
// `01 00` + 16 GUID bytes, and the extractor is validated by requiring it to reproduce a GUID
// that was verified byte-for-byte by hand first.  Once an IID returns S_OK, the interface IS
// the statics, and its first method after IUnknown+IInspectable is RequestAccessAsync.
static bool parse_guid(const char* s, GUID* g)
{
    unsigned a, b, c, d, e, f, h, i, j, k, l;
    if (sscanf_s(s, "%8x-%4x-%4x-%2x%2x-%2x%2x%2x%2x%2x%2x",
                 &a, &b, &c, &d, &e, &f, &h, &i, &j, &k, &l) != 11) return false;
    g->Data1 = a; g->Data2 = (unsigned short)b; g->Data3 = (unsigned short)c;
    g->Data4[0] = (unsigned char)d; g->Data4[1] = (unsigned char)e;
    g->Data4[2] = (unsigned char)f; g->Data4[3] = (unsigned char)h;
    g->Data4[4] = (unsigned char)i; g->Data4[5] = (unsigned char)j;
    g->Data4[6] = (unsigned char)k; g->Data4[7] = (unsigned char)l;
    return true;
}

static void find_and_request(const char* list_path)
{
    static const GUID kIID_AsyncInfo =
        { 0x00000036, 0x0000, 0x0000, { 0xc0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46 } };

    say("--- (f2) find IGraphicsCaptureAccessStatics in the OS metadata, then call it ---");
    FILE* f = nullptr;
    if (fopen_s(&f, list_path, "r") != 0 || !f) { say("cannot open %s", list_path); return; }

    HSTRING cls = nullptr;
    const wchar_t* name = L"Windows.Graphics.Capture.GraphicsCaptureAccess";
    if (FAILED(WindowsCreateString(name, (UINT32)wcslen(name), &cls))) { fclose(f); return; }

    GUID found = {};
    bool have = false;
    int tried = 0, noiface = 0, other = 0;
    char line[128];
    while (fgets(line, sizeof(line), f)) {
        GUID cand = {};
        if (!parse_guid(line, &cand)) continue;
        ++tried;
        void* p = nullptr;
        HRESULT hr = RoGetActivationFactory(cls, cand, &p);
        if (hr == S_OK && p) {
            found = cand; have = true;
            say("  MATCH after %d candidate(s): {%08lX-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}",
                tried, (unsigned long)cand.Data1, cand.Data2, cand.Data3,
                cand.Data4[0], cand.Data4[1], cand.Data4[2], cand.Data4[3],
                cand.Data4[4], cand.Data4[5], cand.Data4[6], cand.Data4[7]);
            ((IUnknown*)p)->Release();
            break;
        }
        if (hr == E_NOINTERFACE || hr == REGDB_E_CLASSNOTREG) ++noiface; else ++other;
    }
    fclose(f);
    WindowsDeleteString(cls);
    say("  candidates tried=%d  E_NOINTERFACE/notreg=%d  other=%d", tried, noiface, other);
    if (!have) { say("  no candidate IID was accepted; the statics are unreachable without the SDK"); return; }

    // Now the slot is justified: this IS IGraphicsCaptureAccessStatics, whose only method is
    // RequestAccessAsync.  GraphicsCaptureAccessKind: Programmatic = 0.
    void* statics = nullptr;
    HRESULT hr = RoGetActivationFactory(cls, found, &statics);
    if (FAILED(hr) || !statics) { say("  re-acquire failed 0x%08lX", (unsigned long)hr); return; }

    typedef HRESULT(STDMETHODCALLTYPE * FnRequest)(void*, int, void**);
    FnRequest req = (FnRequest)(*(void***)statics)[6];
    void* op = nullptr;
    hr = req(statics, 0, &op);
    say("  RequestAccessAsync(Programmatic) -> 0x%08lX %s  op=%p", (unsigned long)hr, hname(hr), op);
    if (FAILED(hr) || !op) { ((IUnknown*)statics)->Release(); return; }

    IAsyncInfo* info = nullptr;
    hr = ((IUnknown*)op)->QueryInterface(kIID_AsyncInfo, (void**)&info);
    if (SUCCEEDED(hr) && info) {
        AsyncStatus st = Started;
        for (int i = 0; i < 200; ++i) {          // up to ~10 s
            st = Started;
            if (FAILED(info->get_Status(&st))) break;
            if (st != Started) break;
            Sleep(50);
        }
        HRESULT ec = S_OK;
        info->get_ErrorCode(&ec);
        say("  async status = %d (0=Started 1=Completed 2=Canceled 3=Error)  errorCode=0x%08lX",
            (int)st, (unsigned long)ec);
        if (st == Completed) {
            // STOPPED HERE, ON PURPOSE.  The result enum is the last thing wanted, but the
            // async object's vtable does NOT match the IAsyncOperation<T> ABI layout mingw's
            // headers imply: slot 6 of `op` faults, while the IAsyncInfo pointer that
            // QueryInterface handed back answers correctly at slot 7 — so `op` and `info` are
            // different objects and {put_Completed, get_Completed, GetResults} cannot be
            // located by slot arithmetic.  Three attempts, three access violations.
            // A guessed slot on a live COM object is a crash generator, not an instrument, so
            // the enum is left UNREAD and reported as unread rather than guessed at again.
            //
            // What IS established, and what the decision actually needs:
            //   RequestAccessAsync(Programmatic) -> S_OK, async Completed, errorCode 0.
            //   Capture is STILL denied afterwards (probe + a real 6 s product run, exit 2).
            say("  result enum NOT read: the async object's vtable does not match the ABI layout");
            say("  (three slot probes faulted; receipt 03 §7). The call itself SUCCEEDED.");
        }
        info->Release();
    }
    ((IUnknown*)op)->Release();
    ((IUnknown*)statics)->Release();
}

int main(int argc, char** argv)
{
    const char* list = nullptr;
    for (int i = 1; i < argc; ++i)
        if (strcmp(argv[i], "--find-access-iid") == 0 && i + 1 < argc) list = argv[++i];

    say("=== WGC CreateForWindow probe ===");
    if (!init_interop()) { say("interop unavailable; stopping"); return 1; }
    if (list) find_and_request(list);

    // (e) IsSupported — the statics IID from the SDK metadata, so this is the REAL call.
    static const GUID kIID_SessionStatics =
        { 0x2224a540, 0x5974, 0x49aa, { 0xb2, 0x32, 0x08, 0x82, 0x53, 0x6f, 0x4c, 0xb5 } };
    HSTRING cls = nullptr;
    const wchar_t* sess = L"Windows.Graphics.Capture.GraphicsCaptureSession";
    if (SUCCEEDED(WindowsCreateString(sess, (UINT32)wcslen(sess), &cls))) {
        void* statics = nullptr;
        HRESULT hr = RoGetActivationFactory(cls, kIID_SessionStatics, &statics);
        WindowsDeleteString(cls);
        if (SUCCEEDED(hr) && statics) {
            boolean sup = 0;
            typedef HRESULT(STDMETHODCALLTYPE * FnIsSupported)(void*, boolean*);
            void** vt = *(void***)statics;
            FnIsSupported f = (FnIsSupported)vt[6];   // IUnknown(3) + IInspectable(3) -> slot 6
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
