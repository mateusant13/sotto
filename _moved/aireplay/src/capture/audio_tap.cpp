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
// STABLE ENDPOINT IDENTITY (this lane -- the measurement hazard, fixed)
// --------------------------------------------------------------------
// THE HAZARD, AS MEASURED ON THIS HOST. Five ACTIVE render endpoints enumerate. One of
// them carries audio; the other four correctly report digital silence. THE ORDER WASAPI
// RETURNS THEM IN IS NOT THE SAME FROM ONE PROCESS LAUNCH TO THE NEXT, and the previous
// selection addressed them BY INDEX. A capture aimed at "index 1" could therefore land
// on a silent endpoint on one run and on the live one on the next, which makes EVERY
// previous audio number unattributable: it was measured against a position, not a device.
//
// WHAT AN IDENTITY IS HERE, AND WHAT IT IS NOT. A friendly name is NOT an identity: this
// box publishes two endpoints called "CABLE Input ..." style names under different APIs,
// and a name can be edited in Windows Sound settings at any time. The identity used by
// this file is the WASAPI endpoint id -- IMMDevice::GetId(), the `{0.0.0.00000000}.{GUID}`
// string the audio service itself publishes, which is what `LoopbackTap::open` ALREADY
// re-resolves the device by. This lane adds three things ON TOP of that id, because "the
// id exists" is not "the id is usable":
//
//   1. `short_id`  a DERIVED id, `ep-<fnv1a64 of the endpoint id>`. Short enough to type on
//                  a command line, and a pure function of the id, so it is stable by
//                  construction -- there is nothing to keep in sync with anything.
//   2. `ordinal`   a FIRST-SEEN POSITION persisted in an id->endpoint map, so "index 1"
//                  keeps meaning ONE NAMED DEVICE even after WASAPI reorders underneath.
//                  The map is the only state this file adds, and it is a cache: delete it
//                  and the ordinals are re-frozen from whatever order the next run sees.
//   3. `raw_index` the position WASAPI actually returned, kept ALONGSIDE the ordinal, so
//                  the disagreement between the two is a MEASURED number (`rebinds=`)
//                  rather than a silent wrong-device capture.
//
// SELECTION IS BY NAME FIRST. `--select` resolves, in order: an exact case-insensitive
// friendly name, a `short_id`, a full endpoint id, `#<ordinal>`, and only then
// `idx:<n>` -- an index, which is resolved THROUGH THE MAP (ordinal n -> the id that
// ordinal n was frozen to) and prints a loud `INDEX_REBIND` line when the raw order at
// position n is not the device the map froze there. AN UNKNOWN SELECTOR IS AN ERROR WITH
// ITS OWN EXIT CODE (4), never a silent fallback to "whatever is first": a selector that
// does not resolve must not quietly become a different device, which is the whole defect.
//
// WHY SILENCE MUST STAY NAMED. Four of five endpoints here are silent because nothing is
// routed into them; that is CORRECT behaviour and this file reports it as a distinct
// verdict (`silent-device`). `--expect-silent` inverts the tap's own verdict into an exit
// code (0 = the endpoint really was silent, 6 = it carried signal where the gate said it
// would not). A gate that can only say yes is not a gate: if selecting a silent endpoint
// by name ever produced signal, the new addressing would be laundering silence into
// signal, and that is the P0 this file is written to make impossible to miss.
//
// BUILD (mingw-w64 g++ 15.2.0; there is no MSVC and no CUDA on this box)
//   g++ -std=c++17 -O2 -Wall -Wextra -I <src> -c audio_tap.cpp -lole32 -loleaut32
// Not added to build.cmd: that file builds main.cpp, which is NOT this lane's to edit.
// The selftest below is the probe that measures all of the above and writes the WAV the
// Goertzel analyser reads; it is a separate translation unit entry, not part of the tap.
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
#include <cstdio>
#include <cstdlib>
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
    // --- identity independent of enumeration order (this lane) ---
    std::string short_id;   // derived: "ep-" + fnv1a64(endpoint_id). A pure function of
                            // the id, so nothing has to be kept in sync with it.
    int ordinal = -1;       // FIRST-SEEN position, frozen in the persisted id->endpoint
                            // map. -1 means "this endpoint was never seen before".
    int raw_index = -1;     // the position WASAPI actually returned, kept BESIDE the
                            // ordinal so the two can be compared instead of conflated.
    uint32_t dev_state = 0; // IMMDevice::GetState bitmask, verbatim (0x1 ACTIVE, ...)
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

// ---------------------------------------------------------------------------
// STABLE IDENTITY, INDEPENDENT OF ENUMERATION ORDER (this lane)
// ---------------------------------------------------------------------------
// FNV-1a 64. Used ONLY to make the endpoint id short and typeable; it is not a security
// hash and is never used to decide that two devices are equal -- equality is always the
// full endpoint id. A short_id that collided would be a reporting nuisance, never a
// wrong-device capture, because the id is what `open()` resolves the device by.
uint64_t fnv1a64(const std::string& s) {
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : s) {
        h ^= c;
        h *= 1099511628211ULL;
    }
    return h;
}

// A DERIVED id: "ep-" + the first 8 bytes of FNV-1a over the endpoint id. A pure function
// of the id, so it is stable across launches by construction -- there is no stored value
// that can drift out of sync with the device it names.
std::string derive_short_id(const std::string& eid) {
    char buf[24];
    snprintf(buf, sizeof(buf), "ep-%016llx", static_cast<unsigned long long>(fnv1a64(eid)));
    return std::string(buf);
}

std::string lower_ascii(const std::string& s) {
    std::string out = s;
    for (char& c : out) {
        if (c >= 'A' && c <= 'Z') c = static_cast<char>(c - 'A' + 'a');
    }
    return out;
}

// THE PERSISTED id->endpoint MAP. Text, one record per line, TAB separated:
//   ordinal <TAB> short_id <TAB> name <TAB> endpoint_id <TAB> unix_last_seen
// Tab separated because a friendly name on this host contains spaces and parentheses and
// "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)" must not need quoting to round-trip.
// The ordinal is the WHOLE POINT: it freezes "index 1" onto one named device, so the
// address survives WASAPI reordering the collection underneath it.
struct MapEntry {
    int ordinal = 0;
    std::string short_id;
    std::string name;
    std::string endpoint_id;
    long long last_seen = 0;
};

// Where the map lives. `SOTTO_ENDPOINT_MAP` overrides it (so a lane can measure against a
// throwaway map instead of the host's), otherwise %LOCALAPPDATA%\sotto\endpoints.map.
std::string map_path() {
    char buf[MAX_PATH] = {0};
    const DWORD n = GetEnvironmentVariableA("SOTTO_ENDPOINT_MAP", buf, sizeof(buf));
    if (n > 0 && n < sizeof(buf)) return std::string(buf, n);
    if (n > 0 && n >= sizeof(buf)) return std::string();
    char local[MAX_PATH] = {0};
    const DWORD m = GetEnvironmentVariableA("LOCALAPPDATA", local, sizeof(local));
    std::string base = (m > 0 && m < sizeof(local)) ? std::string(local, m) : std::string(".");
    return base + "\\sotto\\endpoints.map";
}

bool load_map(std::vector<MapEntry>* out) {
    out->clear();
    FILE* f = fopen(map_path().c_str(), "rb");
    if (!f) return false;   // no map yet is the normal first-run case, not an error
    char line[2048];
    while (fgets(line, sizeof(line), f)) {
        std::string s(line);
        while (!s.empty() && (s.back() == '\n' || s.back() == '\r')) s.pop_back();
        if (s.empty() || s[0] == '#') continue;
        std::vector<std::string> f4;
        size_t start = 0;
        while (true) {
            const size_t tab = s.find('\t', start);
            if (tab == std::string::npos) { f4.push_back(s.substr(start)); break; }
            f4.push_back(s.substr(start, tab - start));
            start = tab + 1;
        }
        if (f4.size() < 4) continue;
        MapEntry e;
        e.ordinal = atoi(f4[0].c_str());
        e.short_id = f4[1];
        e.name = f4[2];
        e.endpoint_id = f4[3];
        if (f4.size() >= 5) e.last_seen = atoll(f4[4].c_str());
        out->push_back(e);
    }
    fclose(f);
    return true;
}

bool save_map(const std::vector<MapEntry>& m) {
    const std::string path = map_path();
    // Create the parent directory if needed (CreateDirectoryA on the parent only; the
    // file itself is written by the CRT, which is what the rest of this file already uses).
    const size_t cut = path.find_last_of("\\/");
    if (cut != std::string::npos) {
        const std::string dir = path.substr(0, cut);
        CreateDirectoryA(dir.c_str(), nullptr);
    }
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    fprintf(f, "# sotto endpoint identity map: ordinal\\tshort_id\\tname\\tendpoint_id\\tlast_seen\n");
    for (const MapEntry& e : m) {
        fprintf(f, "%d\t%s\t%s\t%s\t%lld\n", e.ordinal, e.short_id.c_str(), e.name.c_str(),
                e.endpoint_id.c_str(), e.last_seen);
    }
    fclose(f);
    return true;
}

// Bind the freshly enumerated endpoints to their persisted ordinals. Endpoints the map
// has never seen are APPENDED at the end (a new device must not steal an existing
// device's ordinal -- that is precisely the hazard being fixed), and `rebinds` counts the
// positions where the raw WASAPI order disagrees with the frozen ordinal: a non-zero
// count is the instability, measured rather than asserted.
void bind_map(std::vector<Endpoint>& raw, std::vector<MapEntry>* map, int* new_endpoints,
              int* rebinds) {
    *new_endpoints = 0;
    *rebinds = 0;
    load_map(map);
    const long long now = static_cast<long long>(GetTickCount64());
    int next = 0;
    for (const MapEntry& e : *map) {
        if (e.ordinal + 1 > next) next = e.ordinal + 1;
    }
    for (Endpoint& ep : raw) {
        MapEntry* hit = nullptr;
        for (MapEntry& e : *map) {
            if (ep.endpoint_id == e.endpoint_id) { hit = &e; break; }
        }
        if (!hit) {
            MapEntry e;
            e.ordinal = next++;
            e.short_id = ep.short_id;
            e.name = ep.name;
            e.endpoint_id = ep.endpoint_id;
            e.last_seen = now;
            map->push_back(e);
            ++(*new_endpoints);
            ep.ordinal = e.ordinal;
        } else {
            hit->last_seen = now;
            ep.ordinal = hit->ordinal;
        }
    }
    // The raw order vs the frozen ordinals, endpoint by endpoint.
    for (const Endpoint& ep : raw) {
        if (ep.ordinal != ep.raw_index) ++(*rebinds);
    }
}

// How many positions the RAW order moved, counting endpoints already known to the map.
// Kept separate from `rebinds` (which also counts never-seen endpoints as a difference)
// so a first run cannot be read as instability.
int count_known_moves(const std::vector<Endpoint>& raw, const std::vector<MapEntry>& map) {
    int moves = 0;
    for (const Endpoint& ep : raw) {
        for (const MapEntry& e : map) {
            if (ep.endpoint_id == e.endpoint_id) {
                if (ep.ordinal != ep.raw_index) ++moves;
                break;
            }
        }
    }
    return moves;
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

// The SAME list in the order WASAPI returned it, unsorted. This is the order whose
// instability between launches this lane measured, and the one an index selector must
// never trust on its own.
bool enumerate_raw(std::vector<Endpoint>* out, uint32_t meter_ms, std::string* err);

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

// EVERY ACTIVE render endpoint in the order WASAPI ACTUALLY RETURNED THEM. The order is
// NOT stable between process launches on this host (measured, this lane), so this function
// deliberately does NOT sort: sorting here is what let an index address a different device
// from one run to the next. `ep.raw_index` records the position as returned, which is the
// thing the stability measurement compares against the frozen ordinals.
// `meter_ms` is the sampling window PER ENDPOINT: a single instantaneous read cannot tell
// "idle" from "the owner is between two tracks", which is the defect that cost the Python
// ladder a whole tap window.
bool enumerate_raw(std::vector<Endpoint>* out, uint32_t meter_ms, std::string* err) {
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
        ep.raw_index = static_cast<int>(i);
        ep.endpoint_id = endpoint_id(dev);
        ep.short_id = derive_short_id(ep.endpoint_id);
        // The device's own state word, read verbatim. It is not decoration: it is how a
        // run says "the thing I enumerated is ACTIVE", independently of any meter reading.
        // DWORD, not uint32_t: on mingw-w64 DWORD is `unsigned long` and `unsigned int`
        // is a DIFFERENT type, so a uint32_t* does not bind (measured, build rc=1).
        DWORD dev_state = 0;
        dev->GetState(&dev_state);
        ep.dev_state = static_cast<uint32_t>(dev_state);
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
        // The meter is sampled over a WINDOW, and the PEAK OVER THAT WINDOW is what is
        // kept. This used to be a single instantaneous read that stopped as soon as the
        // meter answered (`slept < meter_ms && avail == false`), which is exactly the
        // failure the comment above it warns about: one read cannot tell "idle" from "the
        // owner is between two tracks", and it made the same endpoint read `carries=0` on
        // one launch and `carries=1` on the next (measured this lane). A window with the
        // max kept cannot: a tone present for any part of the window is seen.
        float peak = 0.0f;
        bool avail = false;
        for (uint32_t slept = 0; slept < meter_ms; slept += 10) {
            float p = 0.0f;
            bool a = false;
            if (read_device_peak(dev, &p, &a) && a) {
                avail = true;
                if (p > peak) peak = p;
            }
            if (slept + 10 < meter_ms) Sleep(10);
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

    if (out->empty()) {
        *err = "no ACTIVE render endpoint on this host";
        return false;
    }
    return true;
}

// The order-by-loudness view, a RANKING and not an identity: it ranks the endpoints that
// are already enumerated by meter peak, default breaking a tie. It is a separate function
// so the ranking can be printed from the SAME metering pass as the raw order -- two
// enumerations would meter every endpoint twice and could even disagree with themselves.
// Two endpoints that both read peak 0.000000 tie here, and the tie is broken by the
// enumeration order underneath -- which is exactly how an index-based selection ends up
// pointing at a different device from one run to the next. Selection by name or by the
// frozen ordinal does not go through this ranking.
void sort_by_loudness(std::vector<Endpoint>* v) {
    std::stable_sort(v->begin(), v->end(), [](const Endpoint& a, const Endpoint& b) {
        if (a.meter_peak != b.meter_peak) return a.meter_peak > b.meter_peak;
        return a.is_default && !b.is_default;   // the default only breaks a tie
    });
}

bool enumerate_endpoints(std::vector<Endpoint>* out, uint32_t meter_ms, std::string* err) {
    if (!enumerate_raw(out, meter_ms, err)) return false;
    sort_by_loudness(out);
    return true;
}

// ---------------------------------------------------------------------------
// SELECTION: BY NAME FIRST, INDEX ONLY THROUGH THE MAP (this lane)
// ---------------------------------------------------------------------------
enum class SelectVia : int {
    kName = 0,        // exact case-insensitive friendly name
    kNamePrefix,      // a unique case-insensitive prefix of the friendly name
    kShortId,         // ep-<fnv1a64>, the derived id
    kEndpointId,      // the full WASAPI endpoint id
    kOrdinal,         // #N or idx:N -- resolved THROUGH the persisted map
    kDefault,         // no selector given: the loudest endpoint, which is a RANKING
};
const char* select_via_name(SelectVia v) {
    switch (v) {
        case SelectVia::kName: return "NAME";
        case SelectVia::kNamePrefix: return "NAME-PREFIX";
        case SelectVia::kShortId: return "SHORT-ID";
        case SelectVia::kEndpointId: return "ENDPOINT-ID";
        case SelectVia::kOrdinal: return "MAP-ORDINAL";
        case SelectVia::kDefault: default: return "LOUDEST";
    }
}

const Endpoint* loudest_of(const std::vector<Endpoint>& v) {
    const Endpoint* best = v.empty() ? nullptr : &v[0];
    for (const Endpoint& ep : v) {
        if (ep.meter_peak > best->meter_peak) best = &ep;
    }
    return best;
}

// Resolve `want` to ONE endpoint, or return nullptr with `*err` set. An unresolved
// selector is NEVER a silent fallback to "the first one": that is the defect this whole
// section exists to remove, so the caller turns a null here into a loud line and its own
// exit code instead of a capture of the wrong device.
const Endpoint* select_endpoint(const std::vector<Endpoint>& v, const std::string& want,
                                std::string* err, SelectVia* via) {
    if (v.empty()) {
        *err = "no endpoints to select from";
        return nullptr;
    }
    const std::string w = lower_ascii(want);

    if (want.empty()) {
        *via = SelectVia::kDefault;
        return loudest_of(v);
    }

    // 1. exact friendly name
    for (const Endpoint& ep : v) {
        if (lower_ascii(ep.name) == w) { *via = SelectVia::kName; return &ep; }
    }
    // 2. derived short id
    for (const Endpoint& ep : v) {
        if (lower_ascii(ep.short_id) == w) { *via = SelectVia::kShortId; return &ep; }
    }
    // 3. the full WASAPI endpoint id, or a unique suffix of it (a GUID tail is enough)
    for (const Endpoint& ep : v) {
        const std::string e = lower_ascii(ep.endpoint_id);
        if (e == w) { *via = SelectVia::kEndpointId; return &ep; }
    }
    {
        const Endpoint* hit = nullptr;
        int n = 0;
        for (const Endpoint& ep : v) {
            const std::string e = lower_ascii(ep.endpoint_id);
            if (e.size() >= w.size() && e.compare(e.size() - w.size(), w.size(), w) == 0) {
                ++n;
                hit = &ep;
            }
        }
        if (n == 1) { *via = SelectVia::kEndpointId; return hit; }
        if (n > 1) {
            *err = "endpoint-id suffix '" + want + "' is ambiguous (" + std::to_string(n) +
                   " endpoints match); give more of the id";
            return nullptr;
        }
    }
    // 4. #N / idx:N -- AN INDEX, RESOLVED THROUGH THE MAP. `raw_index` is what WASAPI
    //    returned and it moves between launches; `ordinal` is what the map froze, so this
    //    is the one spelling that still names the same device tomorrow.
    if (w[0] == '#' || w.compare(0, 4, "idx:") == 0) {
        const std::string digits = (w[0] == '#') ? w.substr(1) : w.substr(4);
        bool numeric = !digits.empty();
        for (char c : digits) {
            if (c < '0' || c > '9') { numeric = false; break; }
        }
        if (numeric) {
            const int n = atoi(digits.c_str());
            const Endpoint* hit = nullptr;
            for (const Endpoint& ep : v) {
                if (ep.ordinal == n) { hit = &ep; break; }
            }
            if (!hit) {
                *err = "no endpoint has map ordinal " + std::to_string(n) +
                       " (the map is %LOCALAPPDATA%\\sotto\\endpoints.map; #0.." +
                       std::to_string(v.size() - 1) + " are the frozen ones)";
                return nullptr;
            }
            *via = SelectVia::kOrdinal;
            return hit;
        }
    }
    // 5. a unique prefix of a friendly name -- long names on this box are painful to type
    {
        const Endpoint* hit = nullptr;
        int n = 0;
        for (const Endpoint& ep : v) {
            const std::string e = lower_ascii(ep.name);
            if (e.size() >= w.size() && e.compare(0, w.size(), w) == 0) {
                ++n;
                hit = &ep;
            }
        }
        if (n == 1) { *via = SelectVia::kNamePrefix; return hit; }
        if (n > 1) {
            *err = "name prefix '" + want + "' is ambiguous (" + std::to_string(n) +
                   " endpoints match); give more of the name";
            return nullptr;
        }
    }

    // The LOUD failure. Everything this host has is listed so the owner does not have to
    // guess what the right spelling is.
    std::string known;
    for (const Endpoint& ep : v) {
        known += "\n    " + ep.name + "  [" + ep.short_id + "  #" + std::to_string(ep.ordinal) + "]";
    }
    *err = "UNKNOWN SELECTOR '" + want + "'. No endpoint has that name, short id, endpoint id "
           "or map ordinal. Known endpoints:" + known;
    return nullptr;
}

// ---------------------------------------------------------------------------
// A RIFF-WAVE WRITER, so the capture can be handed to the Goertzel analyser as bytes
// instead of as a claim. (16 kHz / mono / PCM16 -- the contract format.)
// ---------------------------------------------------------------------------
bool write_wav(const std::string& path, const std::vector<int16_t>& pcm, uint32_t rate,
               uint16_t channels, uint16_t width) {
    FILE* f = fopen(path.c_str(), "wb");
    if (!f) return false;
    const uint32_t data_bytes = static_cast<uint32_t>(pcm.size()) * width;
    const uint16_t ch = channels ? channels : 1;
    const uint16_t bits = static_cast<uint16_t>(width * 8);
    const uint32_t byte_rate = rate * ch * width;
    const uint16_t block_align = static_cast<uint16_t>(ch * width);
    uint8_t hdr[44] = {0};
    memcpy(hdr + 0, "RIFF", 4);
    const uint32_t riff_size = 36 + data_bytes;
    memcpy(hdr + 4, &riff_size, 4);
    memcpy(hdr + 8, "WAVE", 4);
    memcpy(hdr + 12, "fmt ", 4);
    const uint32_t fmt_size = 16;
    memcpy(hdr + 16, &fmt_size, 4);
    const uint16_t tag = 1;   // WAVE_FORMAT_PCM
    memcpy(hdr + 20, &tag, 2);
    memcpy(hdr + 22, &ch, 2);
    memcpy(hdr + 24, &rate, 4);
    memcpy(hdr + 28, &byte_rate, 4);
    memcpy(hdr + 32, &block_align, 2);
    memcpy(hdr + 34, &bits, 2);
    memcpy(hdr + 36, "data", 4);
    memcpy(hdr + 40, &data_bytes, 4);
    const bool ok_h = fwrite(hdr, 1, sizeof(hdr), f) == sizeof(hdr);
    const bool ok_d =
        data_bytes == 0 || fwrite(pcm.data(), 1, data_bytes, f) == data_bytes;
    fclose(f);
    return ok_h && ok_d;
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
    uint32_t meter_ms = 300;
    uint32_t window_ms = 1500;
    std::string want;              // --select
    std::string wav_path;          // --wav
    bool enum_only = false;        // --enum-only
    bool expect_silent = false;    // --expect-silent
    bool no_map = false;           // --no-map: measure order without touching the map
    bool by_loudness = false;      // --by-loudness: also run the public ranking entry point

    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--enum-only") {
            enum_only = true;
        } else if (a == "--expect-silent") {
            expect_silent = true;
        } else if (a == "--no-map") {
            no_map = true;
        } else if (a == "--by-loudness") {
            by_loudness = true;
        } else if (a == "--select" && i + 1 < argc) {
            want = argv[++i];
        } else if (a == "--wav" && i + 1 < argc) {
            wav_path = argv[++i];
        } else if (a == "--meter-ms" && i + 1 < argc) {
            meter_ms = static_cast<uint32_t>(atoi(argv[++i]));
        } else if (a == "--window-ms" && i + 1 < argc) {
            window_ms = static_cast<uint32_t>(atoi(argv[++i]));
        } else if (a.size() > 0 && a[0] >= '0' && a[0] <= '9') {
            window_ms = static_cast<uint32_t>(atoi(argv[i]));   // positional: window ms
        } else {
            fprintf(stderr, "BAD_ARG '%s' (usage: [--enum-only] [--select SPEC] [--wav PATH] "
                            "[--meter-ms N] [--window-ms N] [--expect-silent] [--no-map] [ms])",
                    a.c_str());
            return 64;
        }
    }

    // RAW order, never sorted: the order under test.
    std::vector<Endpoint> raw;
    std::string err;
    if (!enumerate_raw(&raw, meter_ms, &err)) {
        printf("AUDIO=NONE reason=%s\n", err.c_str());
        printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
        return 2;
    }

    // Freeze identities against the persisted map and MEASURE the disagreement.
    std::vector<MapEntry> map;
    int new_eps = 0;
    int rebinds = 0;
    bind_map(raw, &map, &new_eps, &rebinds);
    const int known_moves = count_known_moves(raw, map);
    if (!no_map && !save_map(map)) {
        fprintf(stderr, "MAP_WRITE_FAILED path=%s\n", map_path().c_str());
    }

    printf("RAW_ENUM count=%zu order=%s\n", raw.size(),
           known_moves == 0 ? "SAME-AS-MAP" : "CHANGED-FROM-MAP");
    for (const Endpoint& ep : raw) {
        printf("  RAW[%d] state=0x%02lX name=%s short=%s ordinal=#%d carries=%d meter=%.6f "
               "meter_available=%d default=%d mix=%u Hz %uch %ubit tag=0x%04X id=%s\n",
               ep.raw_index, static_cast<unsigned long>(ep.dev_state), ep.name.c_str(),
               ep.short_id.c_str(), ep.ordinal,
               (ep.meter_available && ep.meter_peak > kSilenceFloor) ? 1 : 0,
               static_cast<double>(ep.meter_peak), ep.meter_available ? 1 : 0,
               ep.is_default ? 1 : 0, ep.rate, ep.channels, ep.bits, ep.format_tag,
               ep.endpoint_id.c_str());
    }
    printf("MAP path=%s entries=%zu new=%d rebinds=%d known_moved=%d\n", map_path().c_str(),
           map.size(), new_eps, rebinds, known_moves);
    printf("MAPORDER");
    for (const Endpoint& ep : raw) printf(" %d:%s", ep.ordinal, ep.short_id.c_str());
    printf("\n");
    // A loud, human-readable rebind line: the raw position N holding a device other than
    // the one the map froze at ordinal N. This is the hazard, made visible per run.
    for (const Endpoint& ep : raw) {
        if (ep.ordinal != ep.raw_index) {
            printf("INDEX_REBIND raw_index=%d holds=%s but map ordinal #%d is frozen to %s\n",
                   ep.raw_index, ep.name.c_str(), ep.ordinal,
                   map[static_cast<size_t>(ep.ordinal)].name.c_str());
        }
    }
    printf("CARRIES count=%d of %zu\n", [&] {
        int n = 0;
        for (const Endpoint& ep : raw) {
            if (ep.meter_available && ep.meter_peak > kSilenceFloor) ++n;
        }
        return n;
    }(), raw.size());
    // The SECOND order under test: the by-loudness ranking. It is what the worker asked
    // for ("who is rendering NOW"), and it is a RANKING, not an identity -- four endpoints
    // here tie at 0.000000 and the tie is broken by the enumeration order underneath, so
    // this order can move between launches for exactly the same reason the raw one does.
    // Printed by NAME and short id, never by a bare index.
    {
        std::vector<Endpoint> sorted = raw;
        sort_by_loudness(&sorted);
        printf("SORTED_BY_LOUDNESS");
        for (const Endpoint& ep : sorted) printf(" %s(%.6f)", ep.short_id.c_str(),
                                                 static_cast<double>(ep.meter_peak));
        printf("\n");
    }
    // The public entry point, exercised through ITS OWN fresh enumeration -- not the
    // ranking helper on the copy above. Two separate COM enumerations agreeing is a real
    // check that `enumerate_endpoints()` still works as the component's API, and it is the
    // only place in this file that calls it.
    if (by_loudness) {
        std::vector<Endpoint> ranked;
        std::string rerr;
        if (enumerate_endpoints(&ranked, meter_ms, &rerr)) {
            printf("LOUDNESS_RANK count=%zu", ranked.size());
            for (size_t i = 0; i < ranked.size(); ++i) {
                printf(" [%zu]=%s#%d(%.6f)", i, ranked[i].name.c_str(), ranked[i].ordinal,
                       static_cast<double>(ranked[i].meter_peak));
            }
            printf("\n");
        } else {
            printf("LOUDNESS_RANK UNAVAILABLE reason=%s\n", rerr.c_str());
        }
    }
    if (enum_only) {
        printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
        return 0;
    }

    SelectVia via = SelectVia::kDefault;
    const Endpoint* sel = select_endpoint(raw, want, &err, &via);
    if (!sel) {
        // LOUD, on stderr, and a distinct exit code. A selector that does not resolve must
        // not become a different device: this is the exit code that says so.
        fprintf(stderr, "SELECTOR_UNKNOWN selector='%s' reason=%s\n", want.c_str(), err.c_str());
        printf("OPEN=NOT-ATTEMPTED selector_unknown=1\n");
        printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
        return 4;
    }
    printf("SELECT selector=%s via=%s name=%s short=%s ordinal=#%d raw_index=%d\n",
           want.empty() ? "<none>" : want.c_str(), select_via_name(via), sel->name.c_str(),
           sel->short_id.c_str(), sel->ordinal, sel->raw_index);
    // An index selector that reached a device through the map while the raw order
    // disagrees is worth saying out loud at the moment of selection, not only in the map
    // report above.
    if (via == SelectVia::kOrdinal) {
        const Endpoint* at_raw = nullptr;
        for (const Endpoint& ep : raw) {
            if (ep.raw_index == sel->ordinal) { at_raw = &ep; break; }
        }
        if (at_raw && at_raw->endpoint_id != sel->endpoint_id) {
            printf("SELECT_WARN index=%d resolved through the map to %s, but the RAW order "
                   "currently holds %s there\n", sel->ordinal, sel->name.c_str(),
                   at_raw->name.c_str());
        }
    }

    LoopbackTap tap;
    if (!tap.open(*sel, 100, &err)) {
        printf("OPEN=FAILED reason=%s\n", err.c_str());
        return 3;
    }
    printf("OPEN=ok endpoint=%s short=%s ordinal=#%d\n", sel->name.c_str(), sel->short_id.c_str(),
           sel->ordinal);

    std::vector<int16_t> pcm;
    std::vector<int16_t> all;
    const ULONGLONG deadline = GetTickCount64() + window_ms;
    uint64_t total_pcm = 0;
    uint64_t pulls = 0;
    while (GetTickCount64() < deadline) {
        if (tap.pull(&pcm, 200, &err)) {
            total_pcm += pcm.size();
            all.insert(all.end(), pcm.begin(), pcm.end());
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
    printf("TAPPED endpoint=%s short=%s ordinal=#%d rate=%u Hz ch=%u\n", sel->name.c_str(),
           sel->short_id.c_str(), sel->ordinal, kAsrRate,
           static_cast<unsigned>(kAsrChannels));
    printf("WAV_FMT=%d ch / %d Hz / %d bytes PCM16 (the contract)\n",
           static_cast<int>(AudioTap::kChannels), static_cast<int>(AudioTap::kSampleRate),
           static_cast<int>(AudioTap::kSampleWidthBytes));

    // The NEGATIVE ARM, expressed as an exit code. `--expect-silent` means "this endpoint
    // must still read digital silence". If it ever carries signal, the addressing has
    // started laundering silence into signal: that is exit 6, the P0, and it is reachable
    // only by naming the silent endpoint explicitly.
    if (expect_silent) {
        const bool carried = (s == TapState::kOk);
        printf("EXPECT_SILENT endpoint=%s verdict=%s result=%s\n", sel->name.c_str(),
               tap_state_name(s), carried ? "VIOLATED-carries-signal" : "holds-silent");
        if (carried) {
            fprintf(stderr, "P0 SILENCE_LAUNDERED endpoint='%s' short=%s expected silence, "
                            "measured peak=%.6f -- naming a silent endpoint returned signal\n",
                    sel->name.c_str(), sel->short_id.c_str(), static_cast<double>(c.peak));
        }
        tap.close();
        printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
        return carried ? 6 : 0;
    }

    if (!wav_path.empty()) {
        const bool ok = write_wav(wav_path, all, kAsrRate, kAsrChannels, kAsrWidth);
        printf("WAV path=%s ok=%d samples=%zu bytes=%zu\n", wav_path.c_str(), ok ? 1 : 0,
               all.size(), all.size() * kAsrWidth);
        if (!ok) return 7;
    }
    tap.close();
    printf("COM_BALANCE=%lld\n", static_cast<long long>(sotto::com_balance()));
    return 0;
}
#endif  // AUDIO_TAP_SELFTEST