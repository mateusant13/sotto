// audio_tap.cpp -- lane B (feat/audio-v6), step 2: a WASAPI loopback tap that
// produces PCM.
//
// WHAT THIS IS
// ------------
// MEASURED on this box (2026-10-07): 8 captured clips, AUDIO=NONE on 8/8. The
// video half works; there is no audio producer anywhere in the capture path.
// This file is the producer. It opens the DEFAULT render endpoint as a LOOPBACK
// capture client and pulls the system's own playback as PCM.
//
// THE ROUTE, from the worker that already proves it on this box
// (worker/wasapi_loopback.py, same COM sequence in ctypes, rung (a) of the
// "universal audio ladder" -- the only rung needing no VB-Cable):
//   1. CoCreateInstance(CLSID_MMDeviceEnumerator)        -> IMMDeviceEnumerator
//   2. EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE)  -> every ACTIVE endpoint
//   3. IMMDevice::Activate(IID_IAudioMeterInformation)   -> GetPeakValue per DEVICE
//      ordering by this is the fix for the measured "idle endpoint" defect
//   4. IMMDevice::Activate(IID_IAudioClient)              -> IAudioClient
//   5. IAudioClient::GetMixFormat()                       -> the MIX format
//   6. IAudioClient::Initialize(SHARED | LOOPBACK, ...)   -- MUST be the mix
//      format; a loopback stream has no format negotiation
//   7. IAudioClient::GetService(IID_IAudioCaptureClient)  -> IAudioCaptureClient
//   8. Start(), then GetNextPacketSize / GetBuffer / ReleaseBuffer
//
// Vendor documentation, so a reader can check rather than trust:
//   * https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording
//   * https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudioclient-initialize
//   * https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudioclient-getmixformat
//   * https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-getbuffer
//   * https://learn.microsoft.com/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-releasebuffer
//   * https://learn.microsoft.com/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-imaudioclient-getservice
//   * https://learn.microsoft.com/windows/win32/coreaudio/device-roles
//   * https://learn.microsoft.com/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdeviceenumerator-enumaudioendpoints
//   * https://learn.microsoft.com/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-imaudiometinformation-getpeakvalue
//
// BUILD: mingw g++ 15.2.0, NO MSVC, NO CUDA. Links ole32 + uuid only.
// THREADS: one. This class spawns none; COM is initialised on the CALLING
// thread exactly as the Python does, so it obeys the <=2 threads lane budget.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cwchar>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include "audio_contract.h"  // the ONE place the target format is written down
#include "audio_tap.h"

// The tap's three integers are a MIRROR of the ASR contract, not a second
// definition of it. If someone edits the ASR side and forgets the tap, this
// refuses to compile instead of emitting a WAV the ASR would reject -- the
// header's warning about "a silent format mismatch" turned into a build error.
static_assert(sotto::AudioTap::kSampleRate == static_cast<int>(aireplay::audio::kAsrSampleRate),
              "audio_tap rate must equal the ASR contract (audio_contract.h / constants.py:91)");
static_assert(sotto::AudioTap::kChannels == static_cast<int>(aireplay::audio::kAsrChannels),
              "audio_tap channel count must equal the ASR contract (audio_contract.h / audio.py:57)");
static_assert(sotto::AudioTap::kSampleWidthBytes == static_cast<int>(aireplay::audio::kAsrSampleWidth),
              "audio_tap sample width must equal the ASR contract (audio_contract.h / audio.py:54)");
static_assert(sotto::AudioTap::kChannels * sotto::AudioTap::kSampleWidthBytes ==
                  static_cast<int>(aireplay::audio::kAsrBytesPerFrame),
              "bytes-per-frame must equal the ASR contract (audio_contract.h)");

#if defined(_WIN32)
#include <audioclient.h>
#include <mmdeviceapi.h>
#include <propsys.h>
#include <functiondiscoverykeys_devpkey.h>
#define SOTTO_HAS_WASAPI 1
#else
#define SOTTO_HAS_WASAPI 0
#endif

namespace sotto {
namespace {

#if SOTTO_HAS_WASAPI

// ── Win32 / COM constants ─────────────────────────────────────────────────────
constexpr HRESULT kSOk = 0;
constexpr HRESULT kSFalse = 1;
// 0x80010106: COM is already initialised on this thread in ANOTHER apartment.
// The CALL fails and NO reference is taken, but COM is initialised and usable.
// Measured on this box (worker/wasapi_loopback.py:194 `_com_init`): turning this
// into an error DELETED the one rung that needs no virtual cable, because
// PortAudio leaves the main thread in an STA before the tap is ever probed.
constexpr HRESULT kRpcEChangedMode = static_cast<HRESULT>(0x80010106u);

constexpr ERole kERoleConsole = eConsole;
constexpr DWORD kClsctxInprocServer = CLSCTX_INPROC_SERVER;
constexpr AUDCLNT_SHAREMODE kShareModeShared = AUDCLNT_SHAREMODE_SHARED;
constexpr DWORD kStreamFlagsLoopback = AUDCLNT_STREAMFLAGS_LOOPBACK;
constexpr DWORD kBufferFlagSilent = AUDCLNT_BUFFERFLAGS_SILENT;

constexpr WORD kWaveFormatPcm = WAVE_FORMAT_PCM;
constexpr WORD kWaveFormatIeeeFloat = WAVE_FORMAT_IEEE_FLOAT;
constexpr WORD kWaveFormatExtensible = WAVE_FORMAT_EXTENSIBLE;

// REFERENCE_TIME unit is 100 ns. 100 ms buffer period -- the documented
// fallback, and the same window the Python ladder uses.
constexpr REFERENCE_TIME kHns100Ms = 1000000;

// vtable slots, named so the numbers are auditable instead of magic.
// mingw-w64's mmdeviceapi.h ships no IAudioMeterInformation, and the ORDERING
// signal depends on it, so the one-method interface is declared here against
// the same UUID. Layout: IUnknown's three slots, then GetPeakValue at slot 3 --
// which is exactly what IMMDevice::Activate hands back.
struct __declspec(uuid("C02216F6-8C67-4B5B-9D00-D008E73E0064")) IMeterInformation : public IUnknown {
    virtual HRESULT STDMETHODCALLTYPE GetPeakValue(float* pfPeak) = 0;
};

const GUID kIidAudioMeterInformation = {
    0xC02216F6, 0x8C67, 0x4B5B, {0x9D, 0x00, 0xD0, 0x08, 0xE7, 0x3E, 0x00, 0x64}};

std::string Fmt(const char* what, HRESULT hr) {
    char buf[160];
    std::snprintf(buf, sizeof(buf), "%s failed: 0x%08lX", what,
                  static_cast<unsigned long>(static_cast<ULONG>(hr)));
    return std::string(buf);
}

template <typename T>
void Release(T** p) {
    if (*p) {
        (*p)->Release();
        *p = nullptr;
    }
}

// COM on this thread. Returns true when THIS call took a reference the caller
// owes a CoUninitialize for; false when COM was already up in another
// apartment and nothing was taken. Mirrors `_com_init` exactly -- including the
// S_FALSE case, which IS a success code and DOES take a reference.
bool ComInit(bool* took_reference, std::string* err) {
    *took_reference = false;
    HRESULT hr = ::CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (hr == kSOk || hr == kSFalse) {
        *took_reference = true;  // a reference WAS taken, even on S_FALSE
        return true;
    }
    if (hr == kRpcEChangedMode) {
        return true;  // already an STA: usable, but nothing to give back
    }
    if (err) *err = Fmt("CoInitializeEx", hr);
    return false;
}

// The WAVEFORMATEX a loopback stream reports. A loopback stream cannot be
// initialised with anything else (step 6 above).
bool ReadMixFormat(IAudioClient* client, MixFormat* out, std::string* err) {
    WAVEFORMATEX* mix = nullptr;
    HRESULT hr = client->GetMixFormat(&mix);
    if (FAILED(hr) || mix == nullptr) {
        if (err) *err = Fmt("IAudioClient::GetMixFormat", hr);
        if (mix) CoTaskMemFree(mix);
        return false;
    }

    WORD tag = mix->wFormatTag;
    if (tag == kWaveFormatExtensible && mix->cbSize >= 22) {
        // WAVEFORMATEXTENSIBLE layout: 18 = wValidBitsPerSample,
        // 20 = dwChannelMask, 24 = the SubFormat GUID, whose Data1 carries the
        // real tag in its low 16 bits. Read it through a copy so the struct's
        // own padding can never be part of the GUID.
        const BYTE* base = reinterpret_cast<const BYTE*>(mix);
        GUID sub = {};
        std::memcpy(&sub, base + 24, sizeof(sub));
        tag = static_cast<WORD>(sub.Data1 & 0xFFFF);
    }

    out->rate = mix->nSamplesPerSec;
    out->channels = mix->nChannels;
    out->bits = mix->wBitsPerSample;
    out->block_align = mix->nBlockAlign;
    out->format_tag = tag;
    CoTaskMemFree(mix);

    if (out->rate == 0 || out->channels == 0 || out->block_align == 0) {
        if (err) *err = "endpoint mix format is degenerate (rate/channels/align = 0)";
        return false;
    }
    if (tag != kWaveFormatPcm && tag != kWaveFormatIeeeFloat) {
        if (err) {
            char buf[128];
            std::snprintf(buf, sizeof(buf), "unsupported mix subformat 0x%04X", tag);
            *err = buf;
        }
        return false;
    }
    return true;
}

// One IMMDevice -> one TapCandidate. Returns false when the device simply will
// not open, so the ladder moves on instead of failing the whole tap.
bool DescribeDevice(IMMDevice* dev, bool is_default, int meter_ms, TapCandidate* out,
                    std::string* err) {
    LPWSTR id = nullptr;
    if (SUCCEEDED(dev->GetId(&id)) && id) {
        out->endpoint_id = id;
        CoTaskMemFree(id);
    }

    // The name, via OpenPropertyStore. NOT via Activate(IPropertyStore): that
    // fails with E_NOINTERFACE on every active render endpoint on this box, so
    // every endpoint used to be reported by raw GUID
    // (worker/wasapi_loopback.py:331).
    IPropertyStore* store = nullptr;
    if (SUCCEEDED(dev->OpenPropertyStore(STGM_READ, &store)) && store) {
        PROPVARIANT var = {};
        if (SUCCEEDED(store->GetValue(PKEY_Device_FriendlyName, &var)) && var.vt == VT_LPWSTR) {
            // The union starts at offset 8 (8-byte header on x64). Reading at
            // offset 0 reinterprets the header as a pointer: measured access
            // violation, rc=5.
            auto* pw = *reinterpret_cast<LPWSTR*>(reinterpret_cast<BYTE*>(&var) + 8);
            if (pw) out->name = pw;
        }
        PropVariantClear(&var);
        store->Release();
    }
    if (out->name.empty()) {
        // Some drivers publish no friendly name. The endpoint id still names it
        // exactly; "unnamed render endpoint" would tell the owner nothing.
        out->name = out->endpoint_id.empty() ? L"<unnamed render endpoint>" : out->endpoint_id;
    }

    // The ORDERING SIGNAL. Read per DEVICE, over a window rather than
    // instantaneously: the moment between two tracks is not "this endpoint is
    // idle" (worker/wasapi_loopback.py:1100, meter_ms=0.4).
    IAudioMeterInformation* meter = nullptr;
    if (SUCCEEDED(dev->Activate(kIidAudioMeterInformation, kClsctxInprocServer, nullptr,
                                reinterpret_cast<void**>(&meter))) &&
        meter) {
        float peak = 0.0f;
        const int samples = std::max(1, meter_ms / 20);
        for (int i = 0; i < samples; ++i) {
            float p = 0.0f;
            if (SUCCEEDED(meter->GetPeakValue(&p)) && p > peak) peak = p;
            if (i + 1 < samples) std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        meter->Release();
        out->meter_peak = peak;
    }

    IAudioClient* probe = nullptr;
    HRESULT hr = dev->Activate(IID_IAudioClient, kClsctxInprocServer, nullptr,
                               reinterpret_cast<void**>(&probe));
    if (FAILED(hr) || probe == nullptr) {
        if (err) *err = Fmt("IMMDevice::Activate(IAudioClient)", hr);
        return false;
    }
    bool ok = ReadMixFormat(probe, &out->mix, err);
    probe->Release();
    return ok;
}

#endif  // SOTTO_HAS_WASAPI

}  // namespace

AudioTapImpl::AudioTapImpl() = default;

AudioTapImpl::~AudioTapImpl() { Close(); }

void AudioTapImpl::Close() {
#if SOTTO_HAS_WASAPI
    if (capture_) {
        static_cast<IAudioCaptureClient*>(capture_)->Stop();
        Release(&capture_);
    }
    if (client_) {
        static_cast<IAudioClient*>(client_)->Stop();
        Release(&client_);
    }
    Release(&device_);
    Release(&enumerator_);
    if (com_ref_taken_) {
        ::CoUninitialize();
        com_ref_taken_ = false;
    }
#endif
    frames_read_ = 0;
    frame_cap_ = 0;
}

std::vector<TapCandidate> AudioTapImpl::EnumerateCandidates() {
    std::vector<TapCandidate> out;
#if SOTTO_HAS_WASAPI
    std::string err;
    bool took = false;
    if (!ComInit(&took, &err)) return out;

    auto* enumerator = static_cast<IMMDeviceEnumerator*>(nullptr);
    HRESULT hr = ::CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, kClsctxInprocServer,
                                   IID_PPV_ARGS(&enumerator));
    if (FAILED(hr) || enumerator == nullptr) {
        if (took) ::CoUninitialize();
        return out;
    }

    IMMDeviceCollection* coll = nullptr;
    hr = enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &coll);
    if (SUCCEEDED(hr) && coll) {
        UINT count = 0;
        coll->GetCount(&count);

        // Which one is the default, so it can lead the list on a tie rather than
        // being dropped (it is the historical driver-free path).
        IMMDevice* def = nullptr;
        bool has_default = false;
        if (SUCCEEDED(enumerator->GetDefaultAudioEndpoint(eRender, kERoleConsole, &def)) && def) {
            LPWSTR def_id = nullptr;
            if (SUCCEEDED(def->GetId(&def_id)) && def_id) {
                has_default = true;
                for (UINT i = 0; i < count; ++i) {
                    IMMDevice* d = nullptr;
                    if (FAILED(coll->Item(i, &d)) || !d) continue;
                    LPWSTR id = nullptr;
                    if (SUCCEEDED(d->GetId(&id)) && id) {
                        if (std::wcscmp(id, def_id) == 0) {
                            TapCandidate c;
                            std::string e;
                            if (DescribeDevice(d, true, kMeterSampleMs, &c, &e)) {
                                out.push_back(c);
                            }
                        }
                        CoTaskMemFree(id);
                    }
                    d->Release();
                }
                CoTaskMemFree(def_id);
            }
            def->Release();
        }
        (void)has_default;

        for (UINT i = 0; i < count; ++i) {
            IMMDevice* d = nullptr;
            if (FAILED(coll->Item(i, &d)) || !d) continue;
            // Skip the default: it was already described above.
            LPWSTR id = nullptr;
            bool is_def = false;
            if (SUCCEEDED(d->GetId(&id)) && id) {
                for (const auto& c : out) {
                    if (c.endpoint_id == id) { is_def = true; break; }
                }
                CoTaskMemFree(id);
            }
            if (!is_def) {
                TapCandidate c;
                std::string e;
                if (DescribeDevice(d, false, kMeterSampleMs, &c, &e)) out.push_back(c);
            }
            d->Release();
        }
        coll->Release();
    }

    enumerator->Release();
    if (took) ::CoUninitialize();

    // ORDER BY WHO IS RENDERING NOW, default first on a tie. This is the fix
    // for the measured defect where the tap opened an idle endpoint while a
    // real speaker carried the audio (worker/wasapi_loopback.py:1084).
    std::stable_sort(out.begin(), out.end(), [](const TapCandidate& a, const TapCandidate& b) {
        if (a.is_default != b.is_default) return a.is_default;
        return a.meter_peak > b.meter_peak;
    });
#endif
    return out;
}

bool AudioTapImpl::OpenOn(const TapCandidate& cand, std::string* err) {
#if SOTTO_HAS_WASAPI
    auto* enumerator = static_cast<IMMDeviceEnumerator*>(enumerator_);
    IMMDeviceCollection* coll = nullptr;
    HRESULT hr = enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &coll);
    if (FAILED(hr) || !coll) {
        if (err) *err = Fmt("EnumAudioEndpoints", hr);
        return false;
    }
    UINT count = 0;
    coll->GetCount(&count);
    IMMDevice* chosen = nullptr;
    for (UINT i = 0; i < count && !chosen; ++i) {
        IMMDevice* d = nullptr;
        if (FAILED(coll->Item(i, &d)) || !d) continue;
        LPWSTR id = nullptr;
        if (SUCCEEDED(d->GetId(&id)) && id) {
            if (cand.endpoint_id == id) chosen = d;
            else d->Release();
            CoTaskMemFree(id);
        } else {
            d->Release();
        }
    }
    coll->Release();
    if (!chosen) {
        if (err) *err = "chosen endpoint vanished from the ACTIVE list";
        return false;
    }
    device_ = chosen;

    auto* client = static_cast<IAudioClient*>(nullptr);
    hr = chosen->Activate(IID_IAudioClient, kClsctxInprocServer, nullptr,
                          reinterpret_cast<void**>(&client));
    if (FAILED(hr) || !client) {
        if (err) *err = Fmt("IMMDevice::Activate(IAudioClient)", hr);
        Close();
        return false;
    }
    if (!ReadMixFormat(client, &mix_, err)) {
        client->Release();
        Close();
        return false;
    }
    // The mix format IS the initialisation format for a loopback stream.
    WAVEFORMATEX wf = {};
    wf.wFormatTag = kWaveFormatPcm;
    wf.nChannels = mix_.channels;
    wf.nSamplesPerSec = mix_.rate;
    wf.wBitsPerSample = mix_.bits;
    wf.nBlockAlign = mix_.block_align;
    wf.nAvgBytesPerSec = mix_.rate * mix_.block_align;
    hr = client->Initialize(kShareModeShared, kStreamFlagsLoopback, kHns100Ms, 0, &wf, nullptr);
    if (FAILED(hr)) {
        if (err) *err = Fmt("IAudioClient::Initialize(LOOPBACK)", hr);
        client->Release();
        Close();
        return false;
    }
    client_ = client;
    hr = client->GetService(IID_IAudioCaptureClient, reinterpret_cast<void**>(&capture_));
    if (FAILED(hr) || !capture_) {
        if (err) *err = Fmt("IAudioClient::GetService(IAudioCaptureClient)", hr);
        Close();
        return false;
    }
    hr = client->Start();
    if (FAILED(hr)) {
        if (err) *err = Fmt("IAudioClient::Start", hr);
        Close();
        return false;
    }
    name_ = cand.name;
    endpoint_id_ = cand.endpoint_id;
    // The owner's 20 s ceiling, in frames, enforced in code.
    frame_cap_ = static_cast<int64_t>(mix_.rate) * kMaxCaptureSeconds;
    frames_read_ = 0;
    return true;
#else
    (void)cand;
    if (err) *err = "WASAPI loopback is Windows-only";
    return false;
#endif
}

bool AudioTapImpl::Open(std::string* err) {
#if SOTTO_HAS_WASAPI
    if (client_) return true;
    std::string local;
    bool took = false;
    if (!ComInit(&took, &local)) {
        if (err) *err = local;
        return false;
    }
    com_ref_taken_ = took;

    auto* enumerator = static_cast<IMMDeviceEnumerator*>(nullptr);
    HRESULT hr = ::CoCreateInstance(__uuidof(MMDeviceEnumerator), nullptr, kClsctxInprocServer,
                                   IID_PPV_ARGS(&enumerator));
    if (FAILED(hr) || !enumerator) {
        if (err) *err = Fmt("CoCreateInstance(MMDeviceEnumerator)", hr);
        Close();
        return false;
    }
    enumerator_ = enumerator;

    std::vector<TapCandidate> cands = EnumerateCandidates();
    if (cands.empty()) {
        if (err) *err = "no ACTIVE render endpoint on this machine";
        Close();
        return false;
    }
    std::string last;
    for (const auto& c : cands) {
        std::string e;
        if (OpenOn(c, &e)) return true;
        last = e;
    }
    if (err) *err = "no render endpoint could be tapped: " + last;
    Close();
    return false;
#else
    if (err) *err = "WASAPI loopback is Windows-only";
    return false;
#endif
}

size_t AudioTapImpl::ReadPcm16(std::vector<int16_t>* out, bool* truncated) {
    if (truncated) *truncated = false;
#if SOTTO_HAS_WASAPI
    if (!client_ || !capture_ || out == nullptr) return 0;
    auto* capture = static_cast<IAudioCaptureClient*>(capture_);
    const size_t start = out->size();

    for (;;) {
        if (frames_read_ >= frame_cap_) {
            if (truncated) *truncated = true;  // the 20 s ceiling, not the stream
            break;
        }
        UINT32 avail = 0;
        HRESULT hr = capture->GetNextPacketSize(&avail);
        if (FAILED(hr)) break;
        if (avail == 0) break;  // nothing buffered: a poll, not a block

        BYTE* data = nullptr;
        UINT32 frames = 0;
        DWORD flags = 0;
        hr = capture->GetBuffer(&data, &frames, &flags, nullptr);
        if (FAILED(hr)) break;

        const int ch = mix_.channels;
        if (flags & kBufferFlagSilent) {
            // GetBuffer handed back a NULL pointer on purpose: this packet is
            // digital silence and MUST be written out, not skipped, or the
            // timeline desynchronises from the video.
            out->insert(out->end(), static_cast<size_t>(frames) * ch, 0);
        } else if (data) {
            const size_t bps = static_cast<size_t>(mix_.block_align) / static_cast<size_t>(ch);
            const size_t total = static_cast<size_t>(frames) * ch;
            out->resize(out->size() + total);
            const size_t base = out->size() - total;
            for (size_t i = 0; i < total; ++i) {
                const BYTE* p = data + i * bps;
                int32_t v = 0;
                if (mix_.format_tag == kWaveFormatPcm) {
                    if (bps == 2) {
                        int16_t s;
                        std::memcpy(&s, p, 2);
                        v = s;
                    } else if (bps == 1) {  // 8-bit PCM is UNSIGNED in WAV
                        v = (static_cast<int>(*p) - 128) << 8;
                    } else if (bps == 3) {
                        int32_t t = static_cast<int32_t>(p[0] | (p[1] << 8) | (p[2] << 16));
                        if (t & 0x800000) t |= static_cast<int32_t>(0xFF000000u);
                        v = t >> 8;
                    } else if (bps == 4) {
                        int32_t s32;
                        std::memcpy(&s32, p, 4);
                        v = s32 >> 16;
                    }
                } else {  // IEEE float, in [-1,1]
                    if (bps == 4) {
                        float f;
                        std::memcpy(&f, p, 4);
                        f = std::max(-1.0f, std::min(1.0f, f));
                        v = static_cast<int32_t>(std::lround(f * 32767.0f));
                    } else if (bps == 8) {
                        double d;
                        std::memcpy(&d, p, 8);
                        d = std::max(-1.0, std::min(1.0, d));
                        v = static_cast<int32_t>(std::lround(d * 32767.0));
                    }
                }
                out[base + i] = static_cast<int16_t>(v);
            }
        }
        capture->ReleaseBuffer(frames, 0);
        frames_read_ += frames;
    }

    const size_t added = out->size() - start;
    return added / static_cast<size_t>(mix_.channels ? mix_.channels : 1);
#else
    (void)out;
    return 0;
#endif
}

}  // namespace sotto