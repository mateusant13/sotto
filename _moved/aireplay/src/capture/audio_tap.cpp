// audio_tap.cpp — a WASAPI LOOPBACK tap that produces PCM16 the ASR can consume.
//
// WHY THIS FILE EXISTS (the measured reason, not a guess)
// -------------------------------------------------------
// `ffprobe -select_streams a` on 8 captured clips (3.0 s - 30.0 s, largest 165 MB)
// returned AUDIO=NONE on 8/8 -- every clip is h264 VIDEO-ONLY. The ASR half
// refuses anything that is not the format in `audio_contract.h`
// (16000 Hz / mono / PCM16 / RIFF-WAVE), so searchable memory has no input at all.
// This is the C++ half of that gap: turn the PC's own render stream into PCM16.
//
// THE FORMAT IS NOT DECIDED HERE. `audio_contract.h` is the one place it is written
// down and this file CONSUMES it (`aireplay::audio::kAsr*`); the `AudioTap` struct in
// audio_tap.h is cross-checked against it with static_asserts below, so the two
// cannot drift. If someone edits one without the other, this file does not build.
//
// WHAT WASAPI LOOPBACK IS (Microsoft Learn -- the vendor-documented, driver-free path)
//   https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording
//     1. CoCreateInstance(CLSID_MMDeviceEnumerator)          -> IMMDeviceEnumerator
//     2. EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE)   -> the candidates
//     3. IMMDevice::Activate(IID_IAudioClient)               -> IAudioClient
//     4. IAudioClient::GetMixFormat()   <- the ONLY format a loopback stream takes
//     5. IAudioClient::Initialize(SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, ..., mix, NULL)
//     6. IAudioClient::GetService(IID_IAudioCaptureClient)   -> IAudioCaptureClient
//     7. Start(), then poll GetNextPacketSize / GetBuffer / ReleaseBuffer
//
// WHAT IS REUSED, AND FROM WHERE (carried over, not re-derived)
// -----------------------------------------------------------
// Device selection is lifted from `H:\sotto\worker\sotto_worker.py:1024-1049`
// (`device_candidates`, RUNG A) and `H:\sotto\worker\wasapi_loopback.py`:
//   * EVERY ACTIVE render endpoint is a candidate, not the default one. MEASURED on
//     this box: Chrome rendered to `CABLE Input` (meter peak 0.264) while the default
//     endpoint `VoiceMeeter Input` was IDLE (peak 0.000000) -- a tap on the default
//     alone opened the quiet one and reported "no audio to transcribe" with the sound
//     plainly playing.
//   * Candidates are ORDERED BY WHO IS RENDERING NOW: each endpoint's live
//     IAudioMeterInformation peak, read WITHOUT opening a stream, sorted descending;
//     the default endpoint only breaks a tie.
//   * SILENCE IS USUALLY CORRECT BEHAVIOUR. With nothing playing every loopback reads
//     DIGITAL SILENCE (measured: a 22 s passive listen peaked at 0.000122). A tap that
//     opens and reads silence has NOT failed to open -- so `kSilentDevice` is a named,
//     distinct verdict, reported loudly rather than returned as an empty success.
//   * ComScope: CoInitializeEx has THREE outcomes and they differ in what the caller
//     OWES. S_OK / S_FALSE both took a reference that must be given back; RPC_E_CHANGED_MODE
//     means COM is already running in another apartment, took NOTHING, and is still
//     perfectly usable. (`wasapi_loopback.py:194-226`.)
//   * A friendly name comes from IMMDevice::OpenPropertyStore + GetValue with
//     PKEY_Device_FriendlyName, reading the LPWSTR at PROPVARIANT offset 8 and testing
//     vt == VT_LPWSTR (0x001F). Activate(IPropertyStore) fails on every active render
//     endpoint on this box; the measured working path is used instead.
//
// HOUSE RULES HONOURED HERE
//   * This component NEVER opens a playback or exclusive device. AUDCLNT_SHAREMODE_SHARED
//     + the loopback flag is a READ-ONLY tap: it cannot mute the endpoint, cannot take it
//     exclusive, and cannot disturb what the owner is listening to.
//   * NO THREAD OF ITS OWN. The tap is pull-based and runs entirely on the caller's
//     thread. The brief caps this lane at 2 threads after the owner reported stutter
//     from the probes, so a tap that spawned a capture thread would be the defect.
//
// BUILD (mingw-w64 g++ 15.2.0; there is no MSVC and no CUDA on this box)
//   g++ -std=c++17 -O2 -Wall -Wextra -I <src> -c audio_tap.cpp -lole32 -loleaut32
// Not added to build.cmd: that file builds main.cpp, which is NOT this lane's to edit.
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0602  // Windows 8: IAudioMeterInformation + loopback
#endif

#include <windows.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <propsys.h>

// mingw-w64's headers do not carry these two, and this lane must not add a dependency
// to fix it. Both are declared verbatim from the vendor headers so the values are the
// documented ones and not a remembered number.
namespace {

// PKEY_Device_FriendlyName {A45C254E-DF1C-4EFD-8020-67D146A850E0}, 14.
constexpr PROPERTYKEY kPkeyDeviceFriendlyName = {
    {0xa45c254e, 0xdf1c, 0x4efd, {0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0}}, 14};

// IID_IAudioMeterInformation {C02216F6-8C67-4B5B-9D00-D008E73E0064} -- the LIVE device
// meter, read WITHOUT opening a stream. This is what ranks the candidates
// (Microsoft Learn, IAudioMeterInformation::GetPeakValue).
constexpr GUID kIidAudioMeterInformation = {
    0xc02216f6, 0x8c67, 0x4b5b, {0x9d, 0x00, 0xd0, 0x08, 0xe7, 0x3e, 0x00, 0x64}};

// mingw-w64's libuuid does not define the two audio IIDs (MEASURED here: linking with
// -luuid still gives "undefined reference to `IID_IAudioClient`"), so they are carried
// over verbatim from the working Python tap, `wasapi_loopback.py:109-110`, rather than
// re-derived from memory.
constexpr GUID kIidAudioClient = {
    0x1cb9ad4c, 0xdbfa, 0x4c32, {0xb1, 0x78, 0xc2, 0xf5, 0x68, 0xa7, 0x03, 0xb2}};
constexpr GUID kIidAudioCaptureClient = {
    0xc8adbd64, 0xe71e, 0x48a0, {0xa4, 0xde, 0x18, 0x5c, 0x39, 0x5c, 0xd3, 0x17}};

}  // namespace

struct IAudioMeterInformation : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE GetPeakValue(float* pfPeakValue) = 0;
    virtual HRESULT STDMETHODCALLTYPE GetMeteringChannelCount(int* pnChannelCount) = 0;
    virtual HRESULT STDMETHODCALLTYPE GetChannelsPeakValues(int u32ChannelCount,
                                                            float* afPeakValues) = 0;
    virtual HRESULT STDMETHODCALLTYPE RequestMeteringRefresh() = 0;
};

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

#include "audio_contract.h"
#include "audio_tap.h"

namespace sotto {
namespace {

// The contract is the contract. audio_tap.h repeats the three numbers so a reader of
// the tap's shape has them in one glance; if the two files ever disagree, this file
// refuses to build rather than emitting a clip the ASR would reject.
static_assert(AudioTap::kSampleRate == static_cast<int>(aireplay::audio::kAsrSampleRate),
              "audio_tap.h disagrees with audio_contract.h on the sample rate");
static_assert(AudioTap::kChannels == static_cast<int>(aireplay::audio::kAsrChannels),
              "audio_tap.h disagrees with audio_contract.h on the channel count");
static_assert(AudioTap::kSampleWidthBytes == static_cast<int>(aireplay::audio::kAsrSampleWidth),
              "audio_tap.h disagrees with audio_contract.h on the sample width");

constexpr uint32_t kAsrRate = aireplay::audio::kAsrSampleRate;
constexpr uint16_t kAsrChannels = aireplay::audio::kAsrChannels;
constexpr uint16_t kAsrWidth = aireplay::audio::kAsrSampleWidth;

// The peak below which a window is DIGITAL SILENCE rather than audio. NOT a tuning knob
// -- a bracket with a measured floor on both ends (wasapi_audio.h:57-65, same box):
//   0.000122  the ceiling a 22 s passive listen across every loopback reached
// 1e-3 sits ~8x above that ceiling and ~500x below an injected tone (peak 0.4999).
constexpr float kSilenceFloor = 1.0e-3f;

// REFERENCE_TIME units are 100 ns. A 100 ms buffer is the documented fallback.
constexpr REFERENCE_TIME kHns100Ms = 10000000;

std::string hresult_str(HRESULT hr) {
    char buf[64] = {0};
    // snprintf into the buffer; the HRESULT stays printable even when FormatMessage
    // knows nothing about it (the Python tap's _fmt() fix, wasapi_loopback.py:242).
    snprintf(buf, sizeof(buf), "0x%08lX", static_cast<unsigned long>(hr));
    return std::string(buf);
}

// COM REFERENCE ACCOUNTING. A wrong answer here does not crash: CoUninitialize is
// reference-counted, so over-releasing walks the apartment count down and the failure
// surfaces on some LATER COM call looking like an unrelated problem. The counters make
// the imbalance visible as a number instead.
int64_t g_com_taken = 0;
int64_t g_com_released = 0;

class ComScope {
public:
    ComScope() {
        // S_OK (0) and S_FALSE (1) BOTH took a reference and BOTH are success.
        // RPC_E_CHANGED_MODE means COM is already running in another apartment: nothing
        // was taken and nothing may be given back, but COM is usable here.
        const HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        if (hr == S_OK || hr == S_FALSE) {
            took_ = true;
            ++g_com_taken;
        } else if (hr == RPC_E_CHANGED_MODE) {
            took_ = false;
        } else {
            init_hr_ = hr;
        }
    }
    ~ComScope() {
        if (took_) {
            CoUninitialize();
            ++g_com_released;
        }
    }
    ComScope(const ComScope&) = delete;
    ComScope& operator=(const ComScope&) = delete;
    bool ok() const { return SUCCEEDED(init_hr_); }
    HRESULT hr() const { return init_hr_; }

private:
    bool took_ = false;
    HRESULT init_hr_ = S_OK;
};

int64_t com_balance() { return g_com_taken - g_com_released; }

// One ACTIVE render endpoint, as WASAPI publishes it. `endpoint_id` is the only
// unambiguous identity on this box (the same friendly name can name two endpoints).
struct Endpoint {
    std::string name;
    std::string endpoint_id;
    uint32_t rate = 0;
    uint16_t channels = 0;
    uint16_t bits = 0;
    uint16_t format_tag = 0;   // RESOLVED: PCM (1) or IEEE float (3)
    uint16_t block_align = 0;
    float meter_peak = 0.0f;
    bool meter_available = false;
    bool is_default = false;
};

bool com_release(IUnknown* p) {
    if (!p) return true;
    p->Release();
    return true;
}

std::string utf8_of(LPCWSTR w) {
    if (!w || !*w) return std::string();
    const int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    if (n <= 1) return std::string();
    std::string out(static_cast<size_t>(n - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, w, -1, &out[0], n, nullptr, nullptr);
    return out;
}

// PKEY_Device_FriendlyName through OpenPropertyStore + GetValue. The LPWSTR sits at
// PROPVARIANT offset 8 (an 8-byte header on every supported ABI), and the measured vt is
// VT_LPWSTR. Reading offset 0 reinterprets the header as a pointer and kills the process.
std::string friendly_name(IMMDevice* dev) {
    IPropertyStore* store = nullptr;
    if (FAILED(dev->OpenPropertyStore(STGM_READ, &store)) || !store) return std::string();
    std::string out;
    PROPVARIANT var;
    PropVariantInit(&var);
    if (SUCCEEDED(store->GetValue(kPkeyDeviceFriendlyName, &var)) && var.vt == VT_LPWSTR &&
        var.pwszVal) {
        out = utf8_of(var.pwszVal);
    }
    // Only after a successful GetValue: clearing an uninitialised PROPVARIANT would free
    // a pointer nobody set.
    PropVariantClear(&var);
    com_release(store);
    return out;
}

std::string endpoint_id(IMMDevice* dev) {
    LPWSTR id = nullptr;
    if (FAILED(dev->GetId(&id)) || !id) return std::string();
    std::string out = utf8_of(id);
    CoTaskMemFree(id);
    return out;
}

// Resolve a mix format to (rate, channels, block align, PCM-or-float). A loopback stream
// has NO negotiation, so this format is the one the stream MUST be initialised with.
bool read_mix_format(IMMDevice* dev, Endpoint* ep, std::string* err) {
    IAudioClient* client = nullptr;
    if (FAILED(dev->Activate(kIidAudioClient, CLSCTX_INPROC_SERVER, nullptr,
                             reinterpret_cast<void**>(&client))) || !client) {
        *err = "Activate(IAudioClient) failed";
        return false;
    }
    WAVEFORMATEX* mix = nullptr;
    const HRESULT hr = client->GetMixFormat(&mix);
    if (FAILED(hr) || !mix) {
        com_release(client);
        *err = "GetMixFormat failed " + hresult_str(hr);
        return false;
    }
    ep->rate = mix->nSamplesPerSec;
    ep->channels = mix->nChannels;
    ep->bits = mix->wBitsPerSample;
    ep->block_align = mix->nBlockAlign;
    uint16_t tag = mix->wFormatTag;
    if (tag == WAVE_FORMAT_EXTENSIBLE) {
        if (mix->cbSize >= 22) {
            // WAVEFORMATEXTENSIBLE: 18 = wValidBitsPerSample, 20 = dwChannelMask,
            // 24 = the SubFormat GUID whose first field carries PCM(1)/float(3).
            const auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(mix);
            tag = static_cast<uint16_t>(ext->SubFormat.Data1 & 0xFFFF);
        } else {
            tag = 0;
        }
    }
    CoTaskMemFree(mix);
    com_release(client);
    if (tag != WAVE_FORMAT_PCM && tag != WAVE_FORMAT_IEEE_FLOAT) {
        *err = "unsupported mix subformat " + hresult_str(static_cast<HRESULT>(tag));
        return false;
    }
    ep->format_tag = tag;
    return true;
}

// The live meter, read WITHOUT opening a stream. This is what ranks the candidates.
bool read_device_peak(IMMDevice* dev, float* peak, bool* available) {
    IAudioMeterInformation* meter = nullptr;
    if (FAILED(dev->Activate(kIidAudioMeterInformation, CLSCTX_INPROC_SERVER, nullptr,
                             reinterpret_cast<void**>(&meter))) || !meter) {
        *available = false;
        return false;
    }
    float p = 0.0f;
    const HRESULT hr = meter->GetPeakValue(&p);
    com_release(meter);
    if (FAILED(hr)) {
        *available = false;
        return false;
    }
    *peak = p;
    *available = true;
    return true;
}

}  // namespace

// EVERY ACTIVE render endpoint, ordered by who is rendering NOW (meter peak descending;
// the default endpoint only breaks a tie). `meter_ms` is the sampling window PER ENDPOINT:
// a single instantaneous read cannot tell "idle" from "the owner is between two tracks",
// which is the defect that cost the Python ladder a whole tap window.
bool enumerate_endpoints(std::vector<Endpoint>* out, uint32_t meter_ms, std::string* err);

// The verdict vocabulary. The names are the WORDS the Python worker already emits, so a
// report from either implementation is comparable without a translation table.
enum class TapState : int {
    kOk = 0,             // frames delivered above the silence floor
    kSilentDevice,       // opened, frames DELIVERED, peak <= floor. With nothing routed
                         // in this is CORRECT behaviour, reported loudly, not an empty
                         // success.
    kNoSignal,           // opened, ZERO frames arrived in the whole window
    kOpenFailed,         // an HRESULT failed
    kNoEndpoint,         // this host has no ACTIVE render endpoint at all
    kClosed,             // not open
};

const char* tap_state_name(TapState s);

// Everything the run has to be able to quote. Every field is a measured count.
struct TapCounters {
    uint64_t packets = 0;
    uint64_t frames = 0;            // frames the endpoint handed over
    uint64_t silent_packets = 0;    // packets GetBuffer flagged SILENT
    uint64_t empty_polls = 0;       // GetNextPacketSize == 0
    uint64_t blocks = 0;
    uint64_t pcm_bytes = 0;         // bytes of PCM16 actually produced
    uint32_t endpoint_grant_frames = 0;
    float peak = 0.0f;
    float rms = 0.0f;
};

// A pull-based WASAPI loopback tap. Runs entirely on the caller's thread.
class LoopbackTap {
public:
    LoopbackTap() = default;
    ~LoopbackTap() { close(); }
    LoopbackTap(const LoopbackTap&) = delete;
    LoopbackTap& operator=(const LoopbackTap&) = delete;

    // Open `ep` as a LOOPBACK tap and start it. The mix format is read back from the
    // device; asking for 16 kHz mono here would FAIL, which is why the conversion to the
    // contract's format happens in software (see append_pcm).
    bool open(const Endpoint& ep, uint32_t block_ms, std::string* err);

    // Pull whatever the endpoint has produced and convert it to PCM16 at the contract's
    // format. Returns true when `out` received PCM. `out->samples` is valid until the
    // next call on THIS object. Bounded: it never blocks forever on a device that
    // stopped rendering -- the poll loop is driven by GetNextPacketSize, not by sleep.
    bool pull(std::vector<int16_t>* out, uint32_t timeout_ms, std::string* err);

    void close();
    bool is_open() const { return client_ != nullptr; }
    const TapCounters& counters() const { return c_; }
    const std::string& last_error() const { return last_err_; }
    TapState judge() const;

private:
    void release_all();
    // One GetBuffer pass: read a packet, downmix to mono float at the mix rate.
    bool pump_once(std::vector<float>* mono, std::string* err);
    // Downmix -> resample -> quantise, the two documented steps of `wasapi_audio.h`.
    void append_pcm(const std::vector<float>& mono, uint32_t mono_rate,
                    std::vector<int16_t>* out);
    void decode_packet(const uint8_t* data, uint32_t frames, std::vector<float>* mono);

    IAudioClient* client_ = nullptr;
    IAudioCaptureClient* capture_ = nullptr;
    Endpoint ep_;
    TapCounters c_;
    std::string last_err_;

    bool started_ = false;
    uint16_t block_align_ = 0;
    bool mix_is_float_ = false;
    double resample_pos_ = 0.0;   // fractional source position, carried across calls so
                                  // block boundaries do not click
    double sum_sq_ = 0.0;
};

const char* tap_state_name(TapState s) {
    switch (s) {
        case TapState::kOk: return "ok";
        case TapState::kSilentDevice: return "silent-device";
        case TapState::kNoSignal: return "no-signal";
        case TapState::kOpenFailed: return "open-failed";
        case TapState::kNoEndpoint: return "no-endpoint";
        case TapState::kClosed: default: return "closed";
    }
}

bool enumerate_endpoints(std::vector<Endpoint>* out, uint32_t meter_ms, std::string* err) {
    ComScope com;
    if (!com.ok()) {
        *err = "CoInitializeEx failed " + hresult_str(com.hr());
        return false;
    }
    IMMDeviceEnumerator* enm = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                 __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(&enm));
    if (FAILED(hr) || !enm) {
        *err = "MMDeviceEnumerator unavailable " + hresult_str(hr);
        return false;
    }
    // One endpoint that cannot be described must never hide the others.
    IMMDeviceCollection* coll = nullptr;
    hr = enm->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &coll);
    if (FAILED(hr) || !coll) {
        com_release(enm);
        *err = "EnumAudioEndpoints failed " + hresult_str(hr);
        return false;
    }
    UINT count = 0;
    coll->GetCount(&count);

    // The default endpoint, which only ever breaks a tie.
    IMMDevice* def = nullptr;
    // The default endpoint is fetched so the tie-break below is real. A host with no
    // default render endpoint still enumerates its ACTIVE ones, so this may be null.
    SUCCEEDED(enm->GetDefaultAudioEndpoint(eRender, eConsole, &def));

    for (UINT i = 0; i < count; ++i) {
        IMMDevice* dev = nullptr;
        if (FAILED(coll->Item(i, &dev)) || !dev) continue;
        Endpoint ep;
        ep.endpoint_id = endpoint_id(dev);
        ep.name = friendly_name(dev);
        if (ep.name.empty()) {
            // Some drivers publish no friendly name at all (measured on this box); the
            // endpoint id still identifies it exactly, and "unnamed" tells the owner
            // nothing he can act on.
            ep.name = ep.endpoint_id.empty() ? "<unnamed render endpoint>" : ep.endpoint_id;
        }
        if (!read_mix_format(dev, &ep, err)) {
            com_release(dev);
            continue;   // skip this one, keep enumerating
        }
        // The meter is sampled over a WINDOW, not read once.
        float peak = 0.0f;
        bool avail = false;
        for (uint32_t slept = 0; slept < meter_ms && avail == false; slept += 10) {
            avail = read_device_peak(dev, &peak, &avail);
            if (avail && slept + 10 < meter_ms) Sleep(10);
        }
        ep.meter_available = avail;
        ep.meter_peak = avail ? peak : 0.0f;
        out->push_back(ep);
        com_release(dev);
    }
    if (def) {
        // Match the default against the enumerated list by endpoint id, so the record
        // that says "is_default" is the one that really is.
        LPWSTR def_id = nullptr;
        if (SUCCEEDED(def->GetId(&def_id)) && def_id) {
            const int n = WideCharToMultiByte(CP_UTF8, 0, def_id, -1, nullptr, 0, nullptr, nullptr);
            std::string want;
            if (n > 1) {
                want.resize(static_cast<size_t>(n - 1));
                WideCharToMultiByte(CP_UTF8, 0, def_id, -1, &want[0], n, nullptr, nullptr);
            }
            CoTaskMemFree(def_id);
            for (auto& ep : *out) {
                if (!want.empty() && ep.endpoint_id == want) ep.is_default = true;
            }
        }
        com_release(def);
    }
    com_release(coll);
    com_release(enm);

    std::stable_sort(out->begin(), out->end(), [](const Endpoint& a, const Endpoint& b) {
        if (a.meter_peak != b.meter_peak) return a.meter_peak > b.meter_peak;
        return a.is_default && !b.is_default;   // the default only breaks a tie
    });
    if (out->empty()) {
        *err = "no ACTIVE render endpoint on this host";
        return false;
    }
    return true;
}

bool LoopbackTap::open(const Endpoint& ep, uint32_t block_ms, std::string* err) {
    close();
    if (block_ms == 0) block_ms = 100;
    ComScope com;
    if (!com.ok()) {
        *err = "CoInitializeEx failed " + hresult_str(com.hr());
        last_err_ = *err;
        return false;
    }
    IMMDeviceEnumerator* enm = nullptr;
    HRESULT hr = CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, CLSCTX_INPROC_SERVER,
                                 __uuidof(IMMDeviceEnumerator), reinterpret_cast<void**>(&enm));
    if (FAILED(hr) || !enm) {
        *err = "MMDeviceEnumerator unavailable " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    // Find the endpoint back by its id: a friendly name is NOT an identity on this box.
    IMMDevice* dev = nullptr;
    if (!ep.endpoint_id.empty()) {
        int n = MultiByteToWideChar(CP_UTF8, 0, ep.endpoint_id.c_str(), -1, nullptr, 0);
        if (n > 0) {
            std::wstring wid(n, L'\0');
            MultiByteToWideChar(CP_UTF8, 0, ep.endpoint_id.c_str(), -1, &wid[0], n);
            enm->GetDevice(wid.c_str(), &dev);
        }
    }
    if (!dev) {
        // No id, or the endpoint went away: fall back to the default console endpoint.
        hr = enm->GetDefaultAudioEndpoint(eRender, eConsole, &dev);
        if (FAILED(hr) || !dev) {
            com_release(enm);
            *err = "endpoint not openable " + hresult_str(hr);
            last_err_ = *err;
            return false;
        }
    }

    hr = dev->Activate(kIidAudioClient, CLSCTX_INPROC_SERVER, nullptr,
                       reinterpret_cast<void**>(&client_));
    if (FAILED(hr) || !client_) {
        com_release(dev);
        com_release(enm);
        *err = "Activate(IAudioClient) failed " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    WAVEFORMATEX* mix = nullptr;
    hr = client_->GetMixFormat(&mix);
    if (FAILED(hr) || !mix) {
        com_release(dev);
        com_release(enm);
        *err = "GetMixFormat failed " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    const uint16_t rate = mix->nSamplesPerSec;
    const uint16_t channels = mix->nChannels;
    const uint16_t align = mix->nBlockAlign;
    uint16_t tag = mix->wFormatTag;
    if (tag == WAVE_FORMAT_EXTENSIBLE && mix->cbSize >= 22) {
        tag = static_cast<uint16_t>(
            reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(mix)->SubFormat.Data1 & 0xFFFF);
    }
    mix_is_float_ = (tag == WAVE_FORMAT_IEEE_FLOAT);
    block_align_ = align;

    // SHARED + LOOPBACK is a READ-ONLY tap. It cannot mute the endpoint, cannot take it
    // exclusive, and cannot disturb what the owner is listening to. The mix format is
    // mandatory: a loopback stream negotiates nothing. No EVENTCALLBACK flag, because
    // this tap is pull-based and never waits on an event.
    hr = client_->Initialize(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK,
                             kHns100Ms, 0, mix, nullptr);
    CoTaskMemFree(mix);
    if (FAILED(hr)) {
        com_release(dev);
        com_release(enm);
        *err = "Initialize(loopback) failed " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    ep_ = ep;
    ep_.rate = rate;
    ep_.channels = channels;
    ep_.bits = mix_is_float_ ? 32 : 16;
    ep_.format_tag = tag;
    ep_.block_align = align;

    hr = client_->GetService(kIidAudioCaptureClient, reinterpret_cast<void**>(&capture_));
    if (FAILED(hr) || !capture_) {
        com_release(dev);
        com_release(enm);
        *err = "GetService(IAudioCaptureClient) failed " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    UINT32 grant = 0;
    if (SUCCEEDED(client_->GetBufferSize(&grant))) c_.endpoint_grant_frames = grant;

    hr = client_->Start();
    com_release(dev);
    com_release(enm);
    if (FAILED(hr)) {
        *err = "Start failed " + hresult_str(hr);
        last_err_ = *err;
        return false;
    }
    started_ = true;
    resample_pos_ = 0.0;
    sum_sq_ = 0.0;
    c_ = TapCounters();
    c_.endpoint_grant_frames = grant;
    return true;
}

void LoopbackTap::decode_packet(const uint8_t* data, uint32_t frames, std::vector<float>* mono) {
    // STEP 1 of the two documented steps: decode + downmix to float32 MONO at the mix
    // rate. Averaging the channels (not taking channel 0) is what keeps a centre-panned
    // voice at its own level instead of losing 6 dB to an odd channel count.
    const uint16_t ch = ep_.channels ? ep_.channels : 1;
    mono->resize(static_cast<size_t>(frames));
    if (mix_is_float_) {
        const float* src = reinterpret_cast<const float*>(data);
        for (uint32_t f = 0; f < frames; ++f) {
            double acc = 0.0;
            for (uint16_t cidx = 0; cidx < ch; ++cidx) acc += src[f * ch + cidx];
            (*mono)[f] = static_cast<float>(acc / ch);
        }
    } else {
        const int16_t* src = reinterpret_cast<const int16_t*>(data);
        for (uint32_t f = 0; f < frames; ++f) {
            double acc = 0.0;
            for (uint16_t cidx = 0; cidx < ch; ++cidx) acc += src[f * ch + cidx];
            (*mono)[f] = static_cast<float>(acc / (ch * 32768.0));   // -> [-1,1]
        }
    }
}

void LoopbackTap::append_pcm(const std::vector<float>& mono, uint32_t mono_rate,
                             std::vector<int16_t>* out) {
    // STEP 2: resample to the contract's rate, then quantise ONCE, at the end, at the
    // rate the model actually consumes. Linear interpolation is what a 48 kHz -> 16 kHz
    // integer decimation can honestly claim.
    if (mono.empty() || mono_rate == 0 || mono_rate != kAsrRate) {
        if (mono.empty()) return;
    }
    const size_t n = mono.size();
    if (mono_rate != kAsrRate) {
        const double step = static_cast<double>(mono_rate) / static_cast<double>(kAsrRate);
        double pos = resample_pos_;
        while (pos + 1.0 < static_cast<double>(n)) {
            const size_t i = static_cast<size_t>(pos);
            const double frac = pos - static_cast<double>(i);
            const double v = mono[i] + (mono[i + 1] - mono[i]) * frac;
            // Clamp before the cast: a loopback sample CAN exceed 1.0 when the endpoint
            // mix clips, and an out-of-range int16 cast is undefined behaviour.
            double q = v * 32767.0;
            if (q > 32767.0) q = 32767.0;
            if (q < -32768.0) q = -32768.0;
            out->push_back(static_cast<int16_t>(std::lround(q)));
            pos += step;
        }
        // Carry the fractional position so a block boundary does not click.
        resample_pos_ = pos - static_cast<double>(n);
        if (resample_pos_ < 0.0) resample_pos_ = 0.0;
    } else {
        for (size_t i = 0; i < n; ++i) {
            double q = static_cast<double>(mono[i]) * 32767.0;
            if (q > 32767.0) q = 32767.0;
            if (q < -32768.0) q = -32768.0;
            out->push_back(static_cast<int16_t>(std::lround(q)));
        }
    }
    c_.pcm_bytes += static_cast<uint64_t>(out->size()) * kAsrWidth;
}

bool LoopbackTap::pump_once(std::vector<float>* mono, std::string* err) {
    UINT32 avail = 0;
    HRESULT hr = capture_->GetNextPacketSize(&avail);
    if (FAILED(hr)) {
        *err = "GetNextPacketSize failed " + hresult_str(hr);
        return false;
    }
    if (avail == 0) {
        ++c_.empty_polls;
        return true;   // nothing yet; not an error
    }
    BYTE* data = nullptr;
    UINT32 frames = 0;
    DWORD flags = 0;
    hr = capture_->GetBuffer(&data, &frames, &flags, nullptr, nullptr);
    if (FAILED(hr)) {
        *err = "GetBuffer failed " + hresult_str(hr);
        return false;
    }
    if (flags & AUDCLNT_BUFFERFLAGS_SILENT) {
        // Flagged silence: the packet is NOT readable, but it is still real time passing,
        // so it counts as frames delivered (all zeros).
        ++c_.silent_packets;
        mono->assign(frames, 0.0f);
    } else {
        decode_packet(data, frames, mono);
    }
    for (uint32_t f = 0; f < frames; ++f) {
        const float v = (*mono)[f];
        const float a = v < 0 ? -v : v;
        if (a > c_.peak) c_.peak = a;
        sum_sq_ += static_cast<double>(v) * static_cast<double>(v);
    }
    c_.packets += 1;
    c_.frames += frames;
    capture_->ReleaseBuffer(frames);
    return true;
}

bool LoopbackTap::pull(std::vector<int16_t>* out, uint32_t timeout_ms, std::string* err) {
    if (!is_open()) {
        *err = "tap is not open";
        last_err_ = *err;
        return false;
    }
    const uint32_t budget = timeout_ms ? timeout_ms : 100;
    // Bounded: a device that stopped rendering must not hang the caller forever. The
    // bound is on WALL time and the loop still drains whatever is already buffered.
    const ULONGLONG deadline = GetTickCount64() + budget;
    std::vector<float> mono;
    out->clear();
    do {
        const size_t before = out->size();
        std::string perr;
        if (!pump_once(&mono, &perr)) {
            *err = perr;
            last_err_ = perr;
            return false;
        }
        if (!mono.empty()) append_pcm(mono, ep_.rate, out);
        if (out->size() > before) {
            ++c_.blocks;
            return true;
        }
        Sleep(2);
    } while (GetTickCount64() < deadline);
    *err = "no frames within " + std::to_string(budget) + " ms";
    last_err_ = *err;
    return false;
}

void LoopbackTap::release_all() {
    if (started_ && client_) client_->Stop();
    started_ = false;
    com_release(capture_);
    capture_ = nullptr;
    com_release(client_);
    client_ = nullptr;
}

void LoopbackTap::close() { release_all(); }

TapState LoopbackTap::judge() const {
    if (!is_open()) return TapState::kClosed;
    if (c_.frames == 0) return TapState::kNoSignal;
    if (c_.peak <= kSilenceFloor) return TapState::kSilentDevice;
    return TapState::kOk;
}

}  // namespace sotto

// A bounded probe of this tap, compiled ONLY with -DAUDIO_TAP_SELFTEST. It exists so the
// component can be exercised on a real host without editing any file this lane does not
// own, and so the "it opened" claim can never be confused with "it carried audio": every
// line printed is a MEASURED number, including the peak, which is what separates a tap
// that worked from a tap that correctly reported digital silence.
//
//   g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> audio_tap.cpp -o tap.exe
//       -lole32 -loleaut32
//
// It opens ONE loopback tap for ONE bounded window and runs entirely on this thread: no
// extra thread is created, in keeping with the lane's 2-thread ceiling.
#ifdef AUDIO_TAP_SELFTEST
#include <cstdio>

int main(int argc, char** argv) {
    using namespace sotto;
    const uint32_t meter_ms = 300;
    const uint32_t window_ms = (argc > 1) ? static_cast<uint32_t>(atoi(argv[1])) : 1500;

    std::vector<Endpoint> eps;
    std::string err;
    if (!enumerate_endpoints(&eps, meter_ms, &err)) {
        printf("AUDIO=NONE reason=%s\n", err.c_str());
        printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
        return 2;
    }
    printf("ENDPOINTS=%zu\n", eps.size());
    for (size_t i = 0; i < eps.size(); ++i) {
        printf("  [%zu] name=%s meter=%.6f meter_available=%d default=%d mix=%u Hz "
               "%uch %ubit tag=0x%04X id=%s\n",
               i, eps[i].name.c_str(), static_cast<double>(eps[i].meter_peak),
               eps[i].meter_available ? 1 : 0, eps[i].is_default ? 1 : 0, eps[i].rate,
               eps[i].channels, eps[i].bits, eps[i].format_tag, eps[i].endpoint_id.c_str());
    }

    LoopbackTap tap;
    if (!tap.open(eps[0], 100, &err)) {
        printf("OPEN=FAILED reason=%s\n", err.c_str());
        return 3;
    }
    printf("OPEN=ok endpoint=%s\n", eps[0].name.c_str());

    std::vector<int16_t> pcm;
    const ULONGLONG deadline = GetTickCount64() + window_ms;
    uint64_t total_pcm = 0;
    uint64_t pulls = 0;
    while (GetTickCount64() < deadline) {
        if (tap.pull(&pcm, 200, &err)) {
            total_pcm += pcm.size();
            ++pulls;
        }
    }
    const TapCounters& c = tap.counters();
    const TapState s = tap.judge();
    printf("VERDICT=%s packets=%llu frames=%llu silent_packets=%llu empty_polls=%llu "
           "blocks=%llu pulls=%llu pcm_samples=%llu peak=%.6f\n",
           tap_state_name(s), static_cast<unsigned long long>(c.packets),
           static_cast<unsigned long long>(c.frames),
           static_cast<unsigned long long>(c.silent_packets),
           static_cast<unsigned long long>(c.empty_polls),
           static_cast<unsigned long long>(c.blocks), static_cast<unsigned long long>(pulls),
           static_cast<unsigned long long>(total_pcm), static_cast<double>(c.peak));
    printf("WAV_FMT=%d ch / %d Hz / %d bytes PCM16 (the contract)\n",
           static_cast<int>(AudioTap::kChannels), static_cast<int>(AudioTap::kSampleRate),
           static_cast<int>(AudioTap::kSampleWidthBytes));
    tap.close();
    printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
    return 0;
}
#endif  // AUDIO_TAP_SELFTEST