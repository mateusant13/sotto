// wasapi_audio.cpp — the C++ half of the WASAPI loopback tap. See wasapi_audio.h for the
// contract, the provenance of every measured constant, and what this file deliberately
// does NOT claim about the MME / DirectSound rungs.
//
// Provenance of the pieces carried over from the WORKING Python implementation on this
// box (`H:\sotto\worker\wasapi_loopback.py`), so a reader can check each one:
//   * the six-step open sequence            wasapi_loopback.py:11-27
//   * COM's THREE outcomes, incl. S_FALSE  wasapi_loopback.py:166-217
//   * friendly name via OpenPropertyStore  wasapi_loopback.py:331-389 (vtable index 4)
//   * the mix format is non-negotiable     wasapi_loopback.py:402-449
//   * the device meter, read with no stream wasapi_loopback.py:490-516
//   * order by WHO IS RENDERING NOW        wasapi_loopback.py:519-591
//   * AUDCLNT_BUFFERFLAGS_SILENT packets   wasapi_loopback.py:980-1002
//   * the poll period that beats the ring  wasapi_loopback.py:935-952
//
// TWO mingw facts this file is written around (both MEASURED here, not assumed):
//   * `H:\msys64\mingw64\include\audioclient.h` does NOT declare IAudioMeterInformation
//     (grep "MeterInformation" = 0 hits), so the one method used here is declared below
//     with its vtable slot. An index wrong by one is a silent wrong answer, so the
//     declaration is spelled out in IDL order rather than guessed.
//   * PROPVARIANT is initialised with a plain value-init, NOT PropVariantInit(), and the
//     VT_LPWSTR is released with CoTaskMemFree(), NOT PropVariantClear(). Both propvar
//     helpers are exported functions from a DLL the repo's own build.cmd does NOT link;
//     what PropVariantClear does for a VT_LPWSTR is CoTaskMemFree on the pointer, so
//     this file needs no library beyond the -lole32 -loleaut32 -luuid already in
//     build.cmd:12.
#include "wasapi_audio.h"

#include <mmdeviceapi.h>
#include <audioclient.h>
#include <mmreg.h>
#include <propsys.h>
#include <propidl.h>
#include <ole2.h>
#include <objbase.h>

#include <algorithm>
#include <cmath>

namespace aireplay {

const char* const kAudioApiName = "Windows WASAPI (loopback)";

const char* audio_state_name(AudioState s)
{
    switch (s) {
        case AudioState::kOk:             return "ok";
        case AudioState::kSilentDevice:   return "silent-device";
        case AudioState::kNoSignal:       return "no-signal";
        case AudioState::kOpenFailed:     return "open-failed";
        case AudioState::kNoEndpoint:     return "no-endpoint";
        case AudioState::kDeviceExhausted:return "device-exhausted";
        case AudioState::kClosed:         return "closed";
    }
    return "?";
}

namespace {

// PKEY_Device_FriendlyName {A45C254E-DF1C-4EFD-8020-67D146A850E0} pid 14. Declared here
// rather than pulled from functiondiscoverykeys_devpkey.h because mingw does not ship
// that header, and a wrong pid reads a DIFFERENT property rather than failing.
const PROPERTYKEY kPkeyDeviceFriendlyName = {
    {0xA45C254E, 0xDF1C, 0x4EFD, {0x80, 0x20, 0x67, 0xD1, 0x46, 0xA8, 0x50, 0xE0}}, 14};

constexpr uint16_t kWaveFormatPcm        = 0x0001;
constexpr uint16_t kWaveFormatIeeeFloat  = 0x0003;
constexpr uint16_t kWaveFormatExtensible = 0xFFFE;

// mingw's audioclient.h declares the two buffer flags as bare enum values and ships NO
// AUDCLNT_BUFFERFLAGS typedef (measured: `grep AUDCLNT_BUFFERFLAGS H:\msys64\mingw64\include\audioclient.h`
// = the two enumerators and nothing else), so they are held as the DWORD the vtable
// actually takes.
constexpr DWORD kBufSilent            = AUDCLNT_BUFFERFLAGS_SILENT;             // 0x2
constexpr DWORD kBufDataDiscontinuity = AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY; // 0x1

// 100 ns units. The documented fallback buffer length, used only when the system
// rejects hnsBufferDuration = 0 (ask the system to choose).
constexpr REFERENCE_TIME kHns100ms = 1000000;

// IAudioMeterInformation, declared here because mingw does not ship it: neither the
// interface (`grep MeterInformation audioclient.h` = 0 hits) nor a way to __uuidof it.
// The IID is spelled out rather than taken from the symbol, because the symbol is the
// thing that is absent -- and a wrong IID here silently returns E_NOINTERFACE, which
// reads exactly like "this endpoint has a meter but it is silent".
//
// IID_IAudioMeterInformation {C02216F6-8C67-4B5B-9D00-D008E73E0064}
// (Microsoft Learn, IAudioMeterInformation)
const GUID kIidAudioMeterInformation = {
    0xC02216F6, 0x8C67, 0x4B5B, {0x9D, 0x00, 0xD0, 0x08, 0xE7, 0x3E, 0x00, 0x64}};

// THE SHAPE BELOW IS LOAD-BEARING, AND GETTING IT WRONG IS A SILENT CRASH, NOT A
// COMPILE ERROR. A COM object is a POINTER TO A VTABLE POINTER:
//
//     obj -> vtbl -> [ QueryInterface ][ AddRef ][ Release ][ GetPeakValue ] ...
//            ^ slot 3 is GetPeakValue, reached by dereferencing TWICE
//
// Writing `struct { fn* QI; fn* AddRef; fn* Release; fn* GetPeakValue; }` and casting
// the OBJECT to it reads offset 24 of the OBJECT -- not of the vtable -- so slot 3 comes
// back as whatever the object happens to carry there. MEASURED on this box before the
// fix: slot 0 = 0x7ff94a7e0f40 (a DATA ADDRESS INSIDE AudioSes.dll, not a function),
// slot 2 = 0xbaadf00d00000001, slot 3 = 0xffffffffffffffff. The call then jumped to
// `0x7ff94a7e0f40` and took SIGSEGV. MEASURED after the fix, same device, same binary
// shape: GetPeakValue = 0x7ff94a6f9250 (a real function in the same DLL) and the meter
// reads 0.391895 on `CABLE Input`.
// The lesson in one line: a cast compiles just as happily against the wrong pointer, so
// this shape is asserted by ARM-B of the gate rather than by the compiler.
struct IAudioMeterInformationVtbl {
    HRESULT (STDMETHODCALLTYPE *QueryInterface)(void* self, REFIID riid, void** ppv);
    ULONG   (STDMETHODCALLTYPE *AddRef)(void* self);
    ULONG   (STDMETHODCALLTYPE *Release)(void* self);
    HRESULT (STDMETHODCALLTYPE *GetPeakValue)(void* self, float* peak);
    HRESULT (STDMETHODCALLTYPE *GetMeteringChannelCount)(void* self, int32_t* count);
    HRESULT (STDMETHODCALLTYPE *GetChannelsPeakValues)(void* self, int32_t count, float* peaks);
    HRESULT (STDMETHODCALLTYPE *QueryHardwareSupport)(void* self, uint32_t mask);
};

struct IAudioMeterInformationMin {
    IAudioMeterInformationVtbl* lpVtbl;   // a POINTER to the table, never the table itself
};

// COM's three documented outcomes. CoInitializeEx has to tell them apart because they
// differ in what the caller then OWES (Microsoft Learn, CoInitializeEx "Return value"):
//   S_OK            COM started here in the MTA  -> A REFERENCE IS TAKEN
//   S_FALSE         COM already running in the MTA -> A REFERENCE IS TAKEN, and it is a
//                   SUCCESS code. A gate that reads it as failure refuses to open a tap
//                   on a thread that legitimately already had COM (this exact defect
//                   closed the whole WASAPI rung on this box -- wasapi_loopback.py:186-193).
//   RPC_E_CHANGED_MODE  COM is running here in ANOTHER apartment. The CALL failed and
//                   NOTHING was taken, but COM is initialised and usable. It is a STATE,
//                   not a fault: sounddevice/PortAudio leaves threads in an STA before
//                   the loopback rung is ever probed, and turning this into an error
//                   DELETED the only rung that needs no virtual cable.
// COM's reference accounting, exposed so an UNBALANCED reference is a visible number
// instead of a crash that shows up somewhere else later (see com_reference_balance()).
std::atomic<int64_t> g_com_inits{0};
std::atomic<int64_t> g_com_uninits{0};

class ComScope {
public:
    ComScope() {
        hr_ = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (hr_ == S_OK || hr_ == S_FALSE)          took_ = true;
        else if (hr_ == RPC_E_CHANGED_MODE)          took_ = false;   // usable, owes nothing
        else                                          took_ = false;   // real failure
        if (took_) g_com_inits.fetch_add(1);
    }
    ~ComScope() { if (take()) { g_com_uninits.fetch_add(1); CoUninitialize(); } }

    bool ok() const {
        return hr_ == S_OK || hr_ == S_FALSE || hr_ == RPC_E_CHANGED_MODE;
    }
    HRESULT hr() const { return hr_; }
    bool took() const { return took_; }
    // Hand the reference to someone else (the owning object) so this scope's destructor
    // does NOT also give it back. Called at most once. Returns whether one was handed on.
    bool take() { const bool t = took_; took_ = false; return t; }

    ComScope(const ComScope&)            = delete;
    ComScope& operator=(const ComScope&) = delete;

private:
    HRESULT hr_ = E_FAIL;
    bool    took_ = false;
};

void com_scope_fail_note(std::string* err, const char* what, HRESULT hr)
{
    if (err) *err = std::string(what) + ": CoInitializeEx " + hr_str((long)hr);
}

std::string fmt(const char* f, ...)
{
    char b[2048];
    va_list ap;
    va_start(ap, f);
    vsnprintf(b, sizeof(b), f, ap);
    va_end(ap);
    return std::string(b);
}

// Sanitise a string that is going into a machine-readable log line: a device friendly
// name is owner-editable free text and routinely contains spaces and quotes.
std::string q(const std::string& s)
{
    std::string o;
    o.reserve(s.size() + 2);
    o.push_back('"');
    for (char c : s) {
        if (c == '"' || c == '\\') o.push_back('\\');
        o.push_back(c);
    }
    o.push_back('"');
    return o;
}

const char* role_name(AudioRole r)
{
    switch (r) {
        case AudioRole::kConsole:       return "eConsole";
        case AudioRole::kMultimedia:    return "eMultimedia";
        case AudioRole::kCommunications: return "eCommunications";
    }
    return "?";
}

const char* tag_name(uint16_t t)
{
    if (t == kWaveFormatPcm)       return "pcm";
    if (t == kWaveFormatIeeeFloat) return "float32";
    return "unsupported";
}

// PKEY_Device_FriendlyName, or "" when the device genuinely publishes none.
//
// NOT reached through IMMDevice::Activate(IID_IPropertyStore): that fails with
// E_NOINTERFACE (0x80004002) on ALL SIX active render endpoints measured on this box,
// which is why the Python tap names every endpoint by its raw GUID. It is reached
// through IMMDevice::OpenPropertyStore instead (wasapi_loopback.py:331-359).
std::string friendly_name(IMMDevice* dev)
{
    IPropertyStore* store = nullptr;
    if (!dev) return std::string();
    if (FAILED(dev->OpenPropertyStore(STGM_READ, &store)) || !store) return std::string();
    std::string name;
    PROPVARIANT var{};                       // what PropVariantInit does, without the DLL
    if (SUCCEEDED(store->GetValue(kPkeyDeviceFriendlyName, &var))) {
        // The measured vt of a friendly name is VT_LPWSTR (0x1F) -- the Python tap's
        // earlier 0x001B test was no PROPVARIANT type at all.
        if (var.vt == VT_LPWSTR && var.pwszVal) name = narrow(var.pwszVal);
        // A VT_LPWSTR is owned by the store and released with CoTaskMemFree, which is
        // exactly what PropVariantClear would do here.
        if (var.vt == VT_LPWSTR && var.pwszVal) CoTaskMemFree(var.pwszVal);
    }
    store->Release();
    return name;
}

std::string endpoint_id_of(IMMDevice* dev)
{
    if (!dev) return std::string();
    LPWSTR id = nullptr;
    if (FAILED(dev->GetId(&id)) || !id) return std::string();
    std::string s = narrow(id);
    CoTaskMemFree(id);
    return s;
}

// Resolve the mix format to a tag this component can actually decode.
//
// A loopback stream has NO format negotiation: it must be initialized with exactly this
// format, so asking the device for 16 kHz mono fails (wasapi_loopback.py:22-24). A
// WAVE_FORMAT_EXTENSIBLE carries its real subformat in a GUID past the WAVEFORMATEX, so
// it is resolved here rather than refused by name — refusing every extensible endpoint
// would refuse most of them.
// The two subformat GUIDs, spelled out rather than taken from ksmedia.h's
// KSDATAFORMAT_SUBTYPE_* symbols. Those are `extern` GUIDs that live in ksuuid, and the
// repo's own build.cmd:12 links no such library -- using them makes this translation
// unit fail to LINK in the product while compiling fine in isolation, which is the
// worst possible way to fail. The values are fixed by the kernel audio spec:
//   https://learn.microsoft.com/windows-hardware/drivers/audio/subformat-guid
const GUID kSubTypePcm = {0x00000001, 0x0000, 0x0010,
                          {0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71}};
const GUID kSubTypeIeeeFloat = {0x00000003, 0x0000, 0x0010,
                                {0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71}};

bool resolve_mix(const WAVEFORMATEX* mix, uint16_t* tag_out,
                 uint32_t* rate, uint16_t* ch, uint16_t* bits, uint16_t* block_align,
                 std::string* err)
{
    if (!mix) { if (err) *err = "GetMixFormat returned null"; return false; }
    uint16_t tag = mix->wFormatTag;
    if (tag == kWaveFormatExtensible) {
        if (mix->cbSize < 22) {
            if (err) *err = fmt("WAVE_FORMAT_EXTENSIBLE with cbSize=%u (need >= 22)", (unsigned)mix->cbSize);
            return false;
        }
        WAVEFORMATEXTENSIBLE ext{};
        memcpy(&ext, mix, sizeof(ext));
        if (IsEqualGUID(ext.SubFormat, kSubTypePcm))            tag = kWaveFormatPcm;
        else if (IsEqualGUID(ext.SubFormat, kSubTypeIeeeFloat))  tag = kWaveFormatIeeeFloat;
        else {
            if (err) *err = fmt("unsupported mix subformat {%08lX-%04X-%04X}",
                                (unsigned long)ext.SubFormat.Data1,
                                (unsigned)ext.SubFormat.Data2, (unsigned)ext.SubFormat.Data3);
            return false;
        }
    }
    // Only two are decoded below. Anything else is REFUSED LOUDLY, never quietly
    // reinterpreted -- the same discipline `src/asr/audio.py:53-61` applies at the sink.
    if (tag != kWaveFormatPcm && tag != kWaveFormatIeeeFloat) {
        if (err) *err = fmt("unsupported mix format tag 0x%04X", (unsigned)tag);
        return false;
    }
    if (tag == kWaveFormatPcm && mix->wBitsPerSample != 16) {
        if (err) *err = fmt("PCM mix at %u bits is not decoded (only 16)",
                            (unsigned)mix->wBitsPerSample);
        return false;
    }
    if (mix->nChannels == 0) { if (err) *err = "mix format has 0 channels"; return false; }
    *tag_out     = tag;
    *rate        = mix->nSamplesPerSec;
    *ch          = mix->nChannels;
    *bits        = mix->wBitsPerSample;
    *block_align = mix->nBlockAlign;
    return true;
}

bool describe_device(IMMDevice* dev, const std::string& default_id, uint32_t meter_ms,
                     AudioEndpoint* out, std::string* err)
{
    IAudioClient* client = nullptr;
    HRESULT hr = dev->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr,
                               reinterpret_cast<void**>(&client));
    if (FAILED(hr) || !client) {
        if (err) *err = "Activate(IAudioClient) " + hr_str((long)hr);
        return false;
    }
    bool ok = false;
    WAVEFORMATEX* mix = nullptr;
    hr = client->GetMixFormat(&mix);
    if (SUCCEEDED(hr) && mix) {
        uint16_t tag = 0, bits = 0, ba = 0;
        uint32_t rate = 0; uint16_t ch = 0;
        if (resolve_mix(mix, &tag, &rate, &ch, &bits, &ba, err)) {
            out->api         = kAudioApiName;
            out->endpoint_id = endpoint_id_of(dev);
            out->name        = friendly_name(dev);
            if (out->name.empty()) out->name = out->endpoint_id;   // honest, not invented
            if (out->name.empty()) out->name = "<unnamed render endpoint>";
            out->rate        = rate;
            out->channels    = ch;
            out->bits        = bits;
            out->format_tag  = tag;
            out->block_align = ba;
            out->is_default  = !out->endpoint_id.empty() && out->endpoint_id == default_id;
            ok = true;
        }
    } else if (err) {
        *err = "GetMixFormat " + hr_str((long)hr);
    }
    CoTaskMemFree(mix);
    client->Release();
    if (!ok) return false;

    // The device meter: what THIS endpoint is rendering right now, read WITHOUT opening
    // a stream, so it is safe to ask about every candidate.
    IUnknown* meter = nullptr;
    if (SUCCEEDED(dev->Activate(kIidAudioMeterInformation, CLSCTX_INPROC_SERVER,
                                nullptr, reinterpret_cast<void**>(&meter))) && meter) {
        auto* m = reinterpret_cast<IAudioMeterInformationMin*>(meter);
        // TWO dereferences, and the second one is the one the bug was in.
        if (!m->lpVtbl) { meter->Release(); return true; }
        float best = 0.0f;
        uint64_t t0 = qpc_now_ns();
        for (;;) {
            float v = 0.0f;
            // `m` is passed explicitly: these are data members holding function pointers,
            // so there is no implicit `this` to be had for free.
            if (m->lpVtbl->GetPeakValue(m, &v) == S_OK && v > best) best = v;
            if ((qpc_now_ns() - t0) / 1000000ull >= meter_ms) break;
            micro_wait_ms(10);
        }
        meter->Release();
        out->meter_available = true;
        out->meter_peak = best;
    }
    return true;
}

// Return the default render endpoint's id, so a tie can be broken toward it.
std::string default_endpoint_id(IMMDeviceEnumerator* en, AudioRole role)
{
    IMMDevice* dev = nullptr;
    std::string id;
    if (SUCCEEDED(en->GetDefaultAudioEndpoint(eRender, (ERole)(uint32_t)role, &dev)) && dev) {
        id = endpoint_id_of(dev);
        dev->Release();
        return id;
    }
    if (SUCCEEDED(en->GetDefaultAudioEndpoint(eRender, eMultimedia, &dev)) && dev) {
        id = endpoint_id_of(dev);
        dev->Release();
    }
    return id;
}

} // namespace

// ---------------------------------------------------------------------------------
// WasapiAudio
// ---------------------------------------------------------------------------------
WasapiAudio::~WasapiAudio() { close(); }

bool WasapiAudio::enumerate(std::vector<AudioEndpoint>* out, uint32_t meter_ms, std::string* err)
{
    if (!out) { if (err) *err = "enumerate(out=null)"; return false; }
    out->clear();
    ComScope com;
    if (!com.ok()) { com_scope_fail_note(err, "enumerate", com.hr()); return false; }

    IMMDeviceEnumerator* en = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                 __uuidof(IMMDeviceEnumerator),
                                 reinterpret_cast<void**>(&en));
    if (FAILED(hr) || !en) {
        if (err) *err = "CoCreateInstance(MMDeviceEnumerator) " + hr_str((long)hr);
        return false;
    }
    const std::string default_id = default_endpoint_id(en, AudioRole::kConsole);

    IMMDeviceCollection* coll = nullptr;
    hr = en->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &coll);
    if (FAILED(hr) || !coll) {
        if (err) *err = "EnumAudioEndpoints(eRender, ACTIVE) " + hr_str((long)hr);
        en->Release();
        return false;
    }
    UINT32 count = 0;
    coll->GetCount(&count);
    for (UINT32 i = 0; i < count; ++i) {
        IMMDevice* dev = nullptr;
        if (FAILED(coll->Item(i, &dev)) || !dev) continue;
        AudioEndpoint ep;
        std::string e;
        if (describe_device(dev, default_id, meter_ms, &ep, &e)) {
            ep.role = role_name(AudioRole::kConsole);
            if (ep.is_default) {
                ep.rung_why = "WASAPI loopback of the DEFAULT render endpoint";
            } else {
                ep.rung_why = "WASAPI loopback of an active render endpoint";
            }
            if (ep.meter_available) {
                ep.rung_why += fmt(" (meter peak %.6f over %u ms)", (double)ep.meter_peak,
                                   (unsigned)meter_ms);
            } else {
                ep.rung_why += " (meter unavailable)";
            }
            out->push_back(ep);
        }
        // One endpoint that cannot be described must not hide the others: the ladder
        // still needs the ones that can.
        dev->Release();
    }
    coll->Release();
    en->Release();

    // ORDER IS THE CONTRACT: whoever is rendering now goes first. Measured on this box
    // (wasapi_loopback.py:594-616): at process start every one of six endpoints read
    // meter_peak=0.000000, the sort could not discriminate, and the default tie-break
    // handed the first tap window to an endpoint this box never renders to while the
    // audio was on another one.
    std::stable_sort(out->begin(), out->end(), [](const AudioEndpoint& a, const AudioEndpoint& b) {
        if (a.meter_peak != b.meter_peak) return a.meter_peak > b.meter_peak;
        return a.is_default && !b.is_default;
    });
    return true;
}

bool WasapiAudio::open(const AudioEndpoint& ep, uint32_t block_ms, std::string* err)
{
    close();
    return open_common(ep, block_ms ? block_ms : 100, err);
}

bool WasapiAudio::open_common(const AudioEndpoint& ep, uint32_t block_ms, std::string* err)
{
    // COM for the tap's LIFETIME, so the stream stays legal between `open()` and
    // `close()`. The enumeration above released its own reference when it returned, so
    // CoCreateInstance here would otherwise run on a thread whose COM may already be
    // closed.
    //
    // THE OWNERSHIP HANDOFF, which is easy to get wrong twice over:
    //   * `ComScope`'s destructor uninitialises COM when `open_common` RETURNS. On
    //     success the reference must therefore SURVIVE past this function -- it belongs to
    //     the open stream -- so the scope must give up ownership first.
    //   * `com.take()` is called exactly ONCE, on the success path. It both sets
    //     `com_ref_taken_` (so `close()` gives the reference back) and disarms the scope's
    //     destructor (so it is not given back HERE as well).
    // MEASURED before this was fixed: setting `com_ref_taken_ = com.took()` and letting
    // the scope also fire meant CoUninitialize ran TWICE per open/close cycle -- the
    // object's reference AND the scope's -- which drives the apartment's count negative.
    ComScope com;
    if (!com.ok()) { com_scope_fail_note(err, "open", com.hr()); return false; }

    // THE FAILURE GUARD. From here on, member pointers are being filled in. Without this,
    // every `return false` below would leave `enumerator_` / `device_` / `client_` /
    // `capture_` holding COM references that NOTHING releases until the next open() or
    // the destructor -- so a host where the ladder walks six endpoints and fails five would
    // leak five sets per pass. The guard releases on the way out and is disarmed only on
    // the success path, where close() owns them instead.
    struct FailGuard {
        WasapiAudio* self;
        bool armed = true;
        ~FailGuard() { if (armed) self->release_all(); }
    } guard{this};

    IMMDeviceEnumerator* en = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                 __uuidof(IMMDeviceEnumerator),
                                 reinterpret_cast<void**>(&en));
    if (FAILED(hr) || !en) {
        if (err) *err = "CoCreateInstance(MMDeviceEnumerator) " + hr_str((long)hr);
        return false;
    }
    enumerator_ = en;

    IMMDevice* dev = nullptr;
    // The endpoint the CALLER chose. Opening the default instead would silently
    // substitute the very endpoint whose silence is the defect.
    if (!ep.endpoint_id.empty()) {
        LPWSTR wid = nullptr;
        const int n = MultiByteToWideChar(CP_UTF8, 0, ep.endpoint_id.c_str(), -1, nullptr, 0);
        if (n > 0) {
            wid = (LPWSTR)CoTaskMemAlloc((size_t)n * sizeof(wchar_t));
            if (wid) MultiByteToWideChar(CP_UTF8, 0, ep.endpoint_id.c_str(), -1, wid, n);
        }
        hr = wid ? en->GetDevice(wid, &dev) : E_OUTOFMEMORY;
        if (wid) CoTaskMemFree(wid);
        if (FAILED(hr) || !dev) {
            if (err) *err = fmt("GetDevice(%s) %s", ep.endpoint_id.c_str(), hr_str((long)hr).c_str());
            return false;
        }
    } else {
        hr = en->GetDefaultAudioEndpoint(eRender, eConsole, &dev);
        if (FAILED(hr) || !dev) {
            dev = nullptr;
            hr = en->GetDefaultAudioEndpoint(eRender, eMultimedia, &dev);
        }
        if (FAILED(hr) || !dev) {
            if (err) *err = "no default render endpoint " + hr_str((long)hr);
            return false;
        }
    }
    device_ = dev;

    IAudioClient* client = nullptr;
    hr = dev->Activate(__uuidof(IAudioClient), CLSCTX_INPROC_SERVER, nullptr,
                       reinterpret_cast<void**>(&client));
    if (FAILED(hr) || !client) {
        if (err) *err = "Activate(IAudioClient) " + hr_str((long)hr);
        return false;
    }
    client_ = client;

    // The MIX format is read back from the device and used verbatim. This is not a
    // preference: a loopback stream has no negotiation (Microsoft Learn, loopback
    // recording), so any other format fails at Initialize.
    WAVEFORMATEX* mix = nullptr;
    hr = client->GetMixFormat(&mix);
    if (FAILED(hr) || !mix) {
        if (err) *err = "GetMixFormat " + hr_str((long)hr);
        return false;
    }
    std::string ferr;
    uint16_t tag = 0, bits = 0, ba = 0, ch = 0; uint32_t rate = 0;
    const bool resolved = resolve_mix(mix, &tag, &rate, &ch, &bits, &ba, &ferr);
    if (!resolved) {
        CoTaskMemFree(mix);
        if (err) *err = ferr;
        return false;
    }
    // Keep the caller's own identification, but take every FORMAT fact from the device.
    ep_ = ep;
    ep_.api = kAudioApiName;
    ep_.endpoint_id = endpoint_id_of(dev);
    if (ep_.name.empty()) ep_.name = ep_.endpoint_id.empty() ? "<unnamed render endpoint>"
                                                           : ep_.endpoint_id;
    ep_.rate = rate; ep_.channels = ch; ep_.bits = bits;
    ep_.format_tag = tag; ep_.block_align = ba;

    // SHARED + LOOPBACK, and nothing else. AUDCLNT_STREAMFLAGS_LOOPBACK is what makes
    // this a tap of what the endpoint is RENDERING instead of a microphone
    // (Microsoft Learn, IAudioClient::Initialize). No EVENTCALLBACK: this component
    // polls, so it does not need an event and does not need a message loop.
    hr = client->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK,
                            0, 0, mix, nullptr);
    if (FAILED(hr)) {
        hr = client->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK,
                                kHns100ms, 0, mix, nullptr);
    }
    CoTaskMemFree(mix);
    if (FAILED(hr)) {
        if (err) *err = fmt("Initialize(SHARED|LOOPBACK) %s (rate=%u ch=%u tag=%s)",
                            hr_str((long)hr).c_str(), (unsigned)rate, (unsigned)ch,
                            tag_name(tag));
        return false;
    }

    IAudioCaptureClient* cap = nullptr;
    hr = client->GetService(__uuidof(IAudioCaptureClient),
                            reinterpret_cast<void**>(&cap));
    if (FAILED(hr) || !cap) {
        if (err) *err = "GetService(IAudioCaptureClient) " + hr_str((long)hr);
        return false;
    }
    capture_ = cap;

    hr = client->Start();
    if (FAILED(hr)) {
        if (err) *err = "IAudioClient::Start " + hr_str((long)hr);
        return false;
    }
    started_ = true;

    mix_format_tag_    = tag;
    mix_is_float_      = (tag == kWaveFormatIeeeFloat);
    mix_block_align_   = ba;
    block_frames_      = (uint32_t)((uint64_t)rate * block_ms / 1000ull);
    if (block_frames_ == 0) block_frames_ = 1;

    // The device's OWN grant, measured not assumed: this endpoint handed 1056 frames
    // (= 22 ms at 48 kHz) on this box, and a 25 ms poll overflowed it every cycle
    // (wasapi_loopback.py:935-951). The period below is derived from OUR block size and
    // clamped to [1, 5] ms, so it polls ~4x faster than the ring fills at the shipped
    // 100 ms block.
    UINT32 grant = 0;
    if (SUCCEEDED(client->GetBufferSize(&grant))) c_.endpoint_grant_frames = grant;
    poll_period_ms_ = (uint32_t)std::min<uint32_t>(5, std::max<uint32_t>(1, block_ms / 20));

    c_ = AudioCounters();
    c_.endpoint_grant_frames = grant;
    accum_.clear();
    blockbuf_.clear();
    accum_.reserve(block_frames_ * 4);
    blockbuf_.reserve(block_frames_);
    have_prev_pos_ = false;
    accum_pos_ = 0;
    prev_pos_ = 0;
    prev_frames_ = 0;
    sum_sq_ = 0.0;
    last_err_.clear();

    log_line("WASAPI_AUDIO api=%s action=open endpoint_id=%s name=%s rate=%u ch=%u bits=%u "
             "format=%s grant_frames=%u block_frames=%u poll_ms=%u mode=shared-loopback",
             kAudioApiName, ep_.endpoint_id.c_str(), q(ep_.name).c_str(), (unsigned)rate,
             (unsigned)ch, (unsigned)bits, tag_name(tag), (unsigned)grant,
             (unsigned)block_frames_, (unsigned)poll_period_ms_);

    // THE HANDOFF. The stream is open, so the COM reference belongs to THIS OBJECT, not to
    // the scope that is about to go out of scope. `take()` records it for `close()` and
    // disarms the destructor. Until this line, a failure below would have been cleaned up
    // correctly BY the destructor; after it, nothing would.
    com_ref_taken_ = com.take();
    guard.armed = false;   // success: close() owns the interfaces now, not the guard
    return true;
}

void WasapiAudio::decode_packet(const uint8_t* data, uint32_t frames, uint32_t channels,
                                bool float_fmt, std::vector<float>& dst)
{
    const size_t total = (size_t)frames * channels;
    if (float_fmt) {
        const float* f = reinterpret_cast<const float*>(data);
        if (channels == 1) {
            dst.insert(dst.end(), f, f + total);
        } else {
            for (uint32_t i = 0; i < frames; ++i) {
                double acc = 0.0;
                for (uint32_t ch = 0; ch < channels; ++ch) acc += f[(size_t)i * channels + ch];
                dst.push_back((float)(acc / (double)channels));
            }
        }
    } else {
        const int16_t* s = reinterpret_cast<const int16_t*>(data);
        if (channels == 1) {
            for (size_t i = 0; i < total; ++i) dst.push_back((float)(s[i] / 32768.0));
        } else {
            for (uint32_t i = 0; i < frames; ++i) {
                double acc = 0.0;
                for (uint32_t ch = 0; ch < channels; ++ch) acc += s[(size_t)i * channels + ch];
                dst.push_back((float)(acc / 32768.0 / (double)channels));
            }
        }
    }
}

bool WasapiAudio::pump_once(AudioBlock* out, std::string* err)
{
    (void)out;
    IAudioCaptureClient* cap = static_cast<IAudioCaptureClient*>(capture_);
    if (!cap) { if (err) *err = "capture client is null"; return false; }

    UINT32 avail = 0;
    HRESULT hr = cap->GetNextPacketSize(&avail);
    if (FAILED(hr)) { if (err) *err = "GetNextPacketSize " + hr_str((long)hr); return false; }
    if (avail == 0) { ++c_.empty_polls; return false; }

    BYTE*  data  = nullptr;
    UINT32 frames = 0;
    DWORD  flags  = 0;
    UINT64 pos    = 0;
    // The 5th out-parameter (pu64QPCPosition) is optional in the IDL and is passed as an
    // explicit NULL, not omitted: the Python tap declared only FOUR and the callee's
    // 5th slot was uninitialised stack it may write 8 bytes through
    // (wasapi_loopback.py:914-923).
    hr = cap->GetBuffer(&data, &frames, &flags, &pos, nullptr);
    if (FAILED(hr)) { if (err) *err = "GetBuffer " + hr_str((long)hr); return false; }

    if (frames) {
        ++c_.packets;
        c_.frames += frames;

        // A packet whose device position does not continue the previous one means the
        // ring lost frames (or the endpoint rewound). Counted, so a gap is a visible
        // number instead of ~0.1 s of audio spliced together. This comparison does not
        // depend on AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY being set, which it is not
        // always.
        if (have_prev_pos_ && pos != prev_pos_ + prev_frames_) ++c_.position_gap_packets;
        prev_pos_ = pos;
        prev_frames_ = frames;
        have_prev_pos_ = true;
        if (accum_.empty()) accum_pos_ = pos;

        if ((flags & kBufSilent) || !data) {
            // AUDCLNT_BUFFERFLAGS_SILENT says the endpoint is NOT rendering and the
            // packet's bytes are NOT VALID SAMPLES. They are accumulated as ZEROS and
            // COUNTED, never decoded: decoding undefined bytes is precisely what
            // produced the dead-endpoint signature "this device hears something" with
            // peak=0.000092 and nonzero_blocks>0 (wasapi_loopback.py:980-994).
            ++c_.silent_packets;
            accum_.insert(accum_.end(), frames, 0.0f);
        } else {
            decode_packet(data, frames, ep_.channels, mix_is_float_, accum_);
        }
        if (flags & kBufDataDiscontinuity) {
            // Disclosed, not silently healed. It is NOT counted as a gap_packets on its
            // own, because the position comparison above already catches the drop.
            log_line("WASAPI_AUDIO api=%s event=discontinuity endpoint_id=%s frames=%u",
                     kAudioApiName, ep_.endpoint_id.c_str(), (unsigned)frames);
        }
    }
    cap->ReleaseBuffer(frames);
    return true;
}

bool WasapiAudio::try_get_block(AudioBlock* out, uint32_t timeout_ms, std::string* err)
{
    if (!out) { if (err) *err = "try_get_block(out=null)"; return false; }
    if (!client_) { if (err) *err = "not open"; return false; }
    // The pump's error is always collected HERE and only then handed to the caller's
    // buffer. Passing the caller's pointer straight through would let a caller pass
    // nullptr and have the real failure vanish with the local buffer it went into.
    std::string local;

    const uint64_t t0 = qpc_now_ns();
    while (accum_.size() < block_frames_) {
        if (!pump_once(nullptr, &local) && !local.empty()) {
            last_err_ = local;
            if (err) *err = local;
            return false;
        }
        if (accum_.size() >= block_frames_) break;
        if ((qpc_now_ns() - t0) / 1000000ull >= (uint64_t)timeout_ms) {
            // No full block yet. This is NORMAL on a device that is not rendering and it
            // is NOT an error: `judge()` is what turns "nothing arrived" into
            // `no-signal`, and it can say so only because nothing here invented a block.
            last_err_.clear();
            return false;
        }
        micro_wait_ms(poll_period_ms_);
    }

    // Bound the accumulator. A caller that stops pulling would otherwise grow it at the
    // endpoint's rate forever; the excess is DROPPED and COUNTED, never quietly kept.
    if (accum_.size() > (size_t)block_frames_ * 4) {
        const size_t excess = accum_.size() - (size_t)block_frames_ * 4;
        accum_.erase(accum_.begin(), accum_.begin() + (long)excess);
        accum_pos_ += excess;
        c_.dropped_frames += excess;
    }

    blockbuf_.assign(accum_.begin(), accum_.begin() + block_frames_);
    accum_.erase(accum_.begin(), accum_.begin() + block_frames_);
    accum_pos_ += block_frames_;

    float block_peak = 0.0f;
    for (float v : blockbuf_) {
        const float a = v < 0 ? -v : v;
        if (a > block_peak) block_peak = a;
        sum_sq_ += (double)v * (double)v;
    }
    if (block_peak > c_.peak) c_.peak = block_peak;
    ++c_.blocks;

    out->samples     = blockbuf_.data();
    out->frames      = block_frames_;
    out->rate        = ep_.rate;
    out->qpc_ns      = qpc_now_ns();
    out->device_pos  = accum_pos_ - block_frames_;
    last_err_.clear();
    return true;
}

void WasapiAudio::drain(uint32_t max_ms)
{
    if (!capture_) return;
    std::string local;
    const uint64_t t0 = qpc_now_ns();
    while ((qpc_now_ns() - t0) / 1000000ull < (uint64_t)max_ms) {
        if (!pump_once(nullptr, &local)) {
            if (!local.empty()) { last_err_ = local; return; }
            micro_wait_ms(poll_period_ms_);
        }
        if (accum_.size() >= (size_t)block_frames_ * 4) { accum_.clear(); accum_pos_ = 0; }
    }
}

AudioState audio_state_for(bool open, uint64_t frames, float peak)
{
    if (!open)    return AudioState::kClosed;
    if (frames == 0) return AudioState::kNoSignal;
    if (peak <= kAudioSilencePeakFloor) return AudioState::kSilentDevice;
    return AudioState::kOk;
}

AudioState WasapiAudio::judge() const
{
    return audio_state_for(client_ != nullptr, c_.frames, c_.peak);
}

std::string WasapiAudio::status_line() const
{
    AudioState s = judge();
    uint64_t win_ms = 0;
    if (c_.blocks && block_frames_ && ep_.rate)
        win_ms = (uint64_t)c_.blocks * block_frames_ * 1000ull / ep_.rate;
    const float rms = c_.frames ? (float)std::sqrt(sum_sq_ / (double)c_.frames) : 0.0f;
    return fmt("WASAPI_AUDIO api=%s state=%s endpoint_id=%s name=%s rate=%u ch=%u bits=%u "
               "format=%s role=%s default=%d meter_peak=%.6f grant_frames=%u poll_ms=%u "
               "window_ms=%llu blocks=%llu packets=%llu frames=%llu silent_packets=%llu "
               "gaps=%llu empty_polls=%llu dropped_frames=%llu peak=%.6f rms=%.6f floor=%.6f",
               kAudioApiName, audio_state_name(s), ep_.endpoint_id.c_str(),
               q(ep_.name).c_str(), (unsigned)ep_.rate, (unsigned)ep_.channels,
               (unsigned)ep_.bits, tag_name(mix_format_tag_),
               ep_.role.empty() ? "eConsole" : ep_.role.c_str(),
               ep_.is_default ? 1 : 0, (double)ep_.meter_peak,
               (unsigned)c_.endpoint_grant_frames, (unsigned)poll_period_ms_,
               (unsigned long long)win_ms, (unsigned long long)c_.blocks,
               (unsigned long long)c_.packets, (unsigned long long)c_.frames,
               (unsigned long long)c_.silent_packets,
               (unsigned long long)c_.position_gap_packets,
               (unsigned long long)c_.empty_polls,
               (unsigned long long)c_.dropped_frames, (double)c_.peak, (double)rms,
               (double)kAudioSilencePeakFloor);
}

void WasapiAudio::log_state(AudioState s, uint32_t window_ms) const
{
    log_line("%s", status_line().c_str());
    if (s == AudioState::kSilentDevice) {
        // The house rule: a run that reads silence SAYS SO. Silence here is CORRECT
        // BEHAVIOUR (nothing is routed into this endpoint) and must never be reported as
        // an empty success -- but it must also never be reported as a crash.
        log_line("WASAPI_AUDIO_SILENT api=%s state=silent-device endpoint_id=%s name=%s "
                 "peak=%.6f floor=%.6f frames=%llu silent_packets=%llu window_ms=%u "
                 "cause=nothing is routed into this render endpoint "
                 "action=route audio into it, or pick another endpoint on the ladder "
                 "note=this is CORRECT behaviour, not a capture failure",
                 kAudioApiName, ep_.endpoint_id.c_str(), q(ep_.name).c_str(),
                 (double)c_.peak, (double)kAudioSilencePeakFloor,
                 (unsigned long long)c_.frames, (unsigned long long)c_.silent_packets,
                 (unsigned)window_ms);
    }
}

void WasapiAudio::release_all()
{
    if (client_) {
        if (started_) static_cast<IAudioClient*>(client_)->Stop();
        static_cast<IAudioClient*>(client_)->Release();
        client_ = nullptr;
    }
    if (capture_) { static_cast<IAudioCaptureClient*>(capture_)->Release(); capture_ = nullptr; }
    if (device_)  { static_cast<IMMDevice*>(device_)->Release(); device_ = nullptr; }
    if (enumerator_) { static_cast<IMMDeviceEnumerator*>(enumerator_)->Release(); enumerator_ = nullptr; }
    started_ = false;
}

void WasapiAudio::close()
{
    release_all();
    if (com_ref_taken_) {
        // Counted for the same reason ComScope counts: an unbalanced release is a number
        // you can assert, where a double release is a mystery crash somewhere later.
        g_com_uninits.fetch_add(1);
        CoUninitialize();
        com_ref_taken_ = false;
    }
    accum_.clear();
    blockbuf_.clear();
}

int64_t com_reference_balance()
{
    return g_com_inits.load() - g_com_uninits.load();
}
int64_t com_reference_taken_count()    { return g_com_inits.load(); }
int64_t com_reference_released_count() { return g_com_uninits.load(); }

// ---------------------------------------------------------------------------------
// The ASR sink
// ---------------------------------------------------------------------------------
bool to_asr_pcm16(const AudioBlock& in, uint32_t out_rate,
                  std::vector<int16_t>* out, std::string* err)
{
    if (!out) { if (err) *err = "to_asr_pcm16(out=null)"; return false; }
    out->clear();
    if (!in.samples || in.frames == 0) {
        if (err) *err = "to_asr_pcm16: empty block";
        return false;
    }
    if (out_rate == 0) { if (err) *err = "to_asr_pcm16: out_rate=0"; return false; }
    if (in.rate == 0)   { if (err) *err = "to_asr_pcm16: block rate=0"; return false; }

    if (out_rate == in.rate) {
        out->resize(in.frames);
        for (uint32_t i = 0; i < in.frames; ++i) {
            float v = in.samples[i];
            if (v >  1.0f) v =  1.0f;
            if (v < -1.0f) v = -1.0f;
            (*out)[i] = (int16_t)lrintf(v * 32767.0f);
        }
        return true;
    }

    const uint64_t out_frames = (uint64_t)in.frames * out_rate / in.rate;
    if (out_frames == 0) { if (err) *err = "to_asr_pcm16: resampled to 0 frames"; return false; }
    out->reserve((size_t)out_frames);

    // An INTEGER factor is the only case a box average can claim honestly: N adjacent
    // input samples -> one output sample. Any other ratio would need a real resampler,
    // and inventing one here is how a level or a language gets destroyed silently.
    if (in.rate % out_rate == 0) {
        const uint32_t n = in.rate / out_rate;
        for (uint64_t i = 0; i < out_frames; ++i) {
            double acc = 0.0;
            for (uint32_t k = 0; k < n; ++k) {
                const uint64_t idx = i * n + k;
                if (idx >= in.frames) break;
                acc += in.samples[idx];
            }
            float v = (float)(acc / (double)n);
            if (v >  1.0f) v =  1.0f;
            if (v < -1.0f) v = -1.0f;
            out->push_back((int16_t)lrintf(v * 32767.0f));
        }
        return true;
    }

    if (err) {
        *err = fmt("to_asr_pcm16: REFUSING a non-integer ratio %u->%u "
                   "(this component will not invent a resampler; the loopback mix rate "
                   "and the model rate must share a factor)", (unsigned)in.rate,
                   (unsigned)out_rate);
    }
    return false;
}

// ---------------------------------------------------------------------------------
// The ladder
// ---------------------------------------------------------------------------------
bool run_audio_ladder(std::vector<AudioEndpoint> candidates, uint32_t window_ms,
                      uint32_t block_ms, AudioLadderResult* out, std::string* err)
{
    if (!out) { if (err) *err = "run_audio_ladder(out=null)"; return false; }
    *out = AudioLadderResult();
    out->window_ms = window_ms;
    if (candidates.empty()) {
        out->final_state = AudioState::kNoEndpoint;
        log_line("WASAPI_AUDIO_LADDER api=%s state=no-endpoint steps=0 window_ms=%u "
                 "note=this host has no ACTIVE render endpoint to tap",
                 kAudioApiName, (unsigned)window_ms);
        return true;
    }

    AudioState last = AudioState::kNoSignal;
    bool ever_frames = false;
    for (size_t i = 0; i < candidates.size(); ++i) {
        AudioLadderStep step;
        step.endpoint  = candidates[i];
        step.window_ms = window_ms;

        WasapiAudio tap;
        std::string e;
        if (!tap.open(step.endpoint, block_ms, &e)) {
            step.state = AudioState::kOpenFailed;
            step.note  = e;
        } else {
            const uint64_t t0 = qpc_now_ns();
            AudioBlock block{};
            for (;;) {
                std::string le;
                if (!tap.try_get_block(&block, 50, &le)) {
                    if (!le.empty()) { step.note = le; break; }
                }
                if ((qpc_now_ns() - t0) / 1000000ull >= (uint64_t)window_ms) break;
            }
            step.state    = tap.judge();
            step.counters = tap.counters();
            step.note     = step.state == AudioState::kSilentDevice
                              ? "opened and delivered a full window of digital silence"
                              : "";
            tap.log_state(step.state, window_ms);
            tap.close();
            if (step.counters.frames) ever_frames = true;
        }
        out->steps.push_back(step);

        log_line("WASAPI_AUDIO_STEP api=%s step=%zu/%zu state=%s endpoint_id=%s name=%s "
                 "peak=%.6f frames=%llu silent_packets=%llu window_ms=%u blocks=%llu "
                 "population=%zu note=%s",
                 kAudioApiName, i + 1, candidates.size(), audio_state_name(step.state),
                 step.endpoint.endpoint_id.c_str(), q(step.endpoint.name).c_str(),
                 (double)step.counters.peak, (unsigned long long)step.counters.frames,
                 (unsigned long long)step.counters.silent_packets, (unsigned)step.window_ms,
                 (unsigned long long)step.counters.blocks, candidates.size(),
                 q(step.note).c_str());

        if (step.state == AudioState::kOk) {
            out->chosen      = i;
            out->final_state = AudioState::kOk;
            log_line("WASAPI_AUDIO_LADDER api=%s state=ok chosen_step=%zu/%zu endpoint_id=%s "
                     "peak=%.6f window_ms=%u population=%zu",
                     kAudioApiName, i + 1, candidates.size(),
                     step.endpoint.endpoint_id.c_str(), (double)step.counters.peak,
                     (unsigned)window_ms, candidates.size());
            return true;
        }
        last = step.state;
    }

    // Every candidate walked and none produced audio. THAT IS A NAMED OUTCOME, reported
    // loudly -- never an empty success, and never a fabricated peak.
    //   kDeviceExhausted  not ONE candidate could even be opened (an exhausted ladder)
    //   kSilentDevice     they opened and every one delivered DIGITAL SILENCE
    //   kNoSignal         they opened and not one delivered a single frame
    bool any_opened = false;
    for (const AudioLadderStep& s : out->steps)
        if (s.state != AudioState::kOpenFailed) any_opened = true;
    if (!any_opened)              out->final_state = AudioState::kDeviceExhausted;
    else if (ever_frames)         out->final_state = AudioState::kSilentDevice;
    else                          out->final_state = AudioState::kNoSignal;
    (void)last;
    log_line("WASAPI_AUDIO_LADDER api=%s state=%s steps=%zu window_ms=%u peak_over_ladder=%.6f "
             "floor=%.6f population=%zu note=%s",
             kAudioApiName, audio_state_name(out->final_state), out->steps.size(),
             (unsigned)window_ms,
             (double)(out->steps.empty() ? 0.0f : out->steps.back().counters.peak),
             (double)kAudioSilencePeakFloor, out->steps.size(),
             out->final_state == AudioState::kSilentDevice
                 ? "every endpoint opened and delivered DIGITAL SILENCE -- nothing is routed"
                 : (out->final_state == AudioState::kDeviceExhausted
                        ? "no candidate endpoint could be opened at all"
                        : "no endpoint delivered a single frame"));
    return true;
}

} // namespace aireplay