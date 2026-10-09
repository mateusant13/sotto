// audio_tap.h -- lane B (feat/audio-v6), step 1 + step 2.
//
// STEP 1 (commit dbe7d8a) is the struct below, verbatim as briefed.
//
// WHY THE TAP EXISTS
// ------------------
// MEASURED (lane B, 2026-10-07): `ffprobe -select_streams a` on 8 captured clips
// (3.0 s - 30.0 s, largest 165 MB) returned AUDIO=NONE on 8/8 -- every clip is
// h264 VIDEO-ONLY. The ASR half consumes WAV and refuses anything else, so
// nothing is ever spoken into the index. The reason it is 8/8 is structural:
// mp4_writer.cpp has no audio track and no one was tapping system audio at all.
// This header is the start of the missing input.
//
// The target format is NOT decided here. It is decided, once, in
// audio_contract.h (`aireplay::audio::kAsrSampleRate` 16000, kAsrChannels 1,
// kAsrSampleWidth 2, taken from the ASR side: constants.py:91, audio.py:54-58).
// The three integers inside AudioTap mirror it and are held to it by the
// static_assert in audio_tap.cpp, so the mirror cannot silently drift into a
// second, competing source of truth.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace sotto {

struct AudioTap {
    static constexpr int kSampleRate = 16000;
    static constexpr int kChannels = 1;
    static constexpr int kSampleWidthBytes = 2;
};

// The owner's cap, honoured in code rather than only in a runbook: a tap stops
// itself at this length. MEASURED constraint from the lane brief -- probes over
// 20 s cause stutter on this box.
constexpr int kMaxCaptureSeconds = 20;

// The endpoint's MIX format, as WASAPI hands it back.
//
// A loopback stream has NO format negotiation: it must be initialised with the
// mix format, so asking WASAPI for 16 kHz mono directly fails. That is why the
// tap records at whatever the endpoint mixes at, and step 3 converts.
// https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording
struct MixFormat {
    uint32_t rate = 0;        // nSamplesPerSec
    uint16_t channels = 0;    // nChannels
    uint16_t bits = 0;        // wBitsPerSample
    uint16_t format_tag = 0;  // 1 = WAVE_FORMAT_PCM, 3 = WAVE_FORMAT_IEEE_FLOAT
    uint16_t block_align = 0; // bytes per frame
};

// One capture candidate: a WASAPI loopback of an ACTIVE render endpoint,
// annotated with the live meter peak that decided its rank.
struct TapCandidate {
    std::wstring name;        // PKEY_Device_FriendlyName, endpoint id if unnamed
    std::wstring endpoint_id; // IMMDevice::GetId
    bool is_default = false;  // the eConsole default render endpoint
    float meter_peak = 0.0f;  // IAudioMeterInformation::GetPeakValue over kMeterSampleMs
    MixFormat mix;
};

constexpr int kMeterSampleMs = 400; // the ladder's ordering window (see wasapi_loopback.py:1100)

class AudioTapImpl {
public:
    AudioTapImpl();
    ~AudioTapImpl();
    AudioTapImpl(const AudioTapImpl&) = delete;
    AudioTapImpl& operator=(const AudioTapImpl&) = delete;

    // Device selection, REUSED from the worker ladder rather than reinvented:
    // every ACTIVE render endpoint is offered, ORDERED BY WHO IS RENDERING NOW
    // (live IAudioMeterInformation peak, descending), default first on a tie.
    // Offering only the default was a measured defect: the tap read an idle
    // endpoint (peak 0) while Chrome rendered to another (peak 0.26), so the app
    // reported "no audio to transcribe" with the sound plainly playing.
    // See worker/wasapi_loopback.py:1084 `loopback_device_specs`.
    // On a non-Windows host this returns an empty vector, never a throw.
    static std::vector<TapCandidate> EnumerateCandidates();

    // Open a loopback capture stream on the best-ranked candidate.
    // Returns false and fills `err` on any HRESULT; never throws.
    bool Open(std::string* err);
    void Close();

    bool is_open() const { return client_ != nullptr; }
    const MixFormat& mix() const { return mix_; }
    const std::wstring& endpoint_name() const { return name_; }

    // Pull whatever WASAPI has buffered since the last call and convert it to
    // INTERLEAVED int16 at the MIX rate and MIX channel count (step 2).
    // Returns the number of FRAMES appended. Stops itself at kMaxCaptureSeconds.
    // `truncated` is set when the cap ended the pull rather than the stream.
    size_t ReadPcm16(std::vector<int16_t>* out, bool* truncated);

private:
    bool OpenOn(const TapCandidate& cand, std::string* err);

    void* enumerator_ = nullptr; // IMMDeviceEnumerator*
    void* device_ = nullptr;     // IMMDevice*      (the chosen one)
    void* client_ = nullptr;      // IAudioClient*
    void* capture_ = nullptr;     // IAudioCaptureClient*
    MixFormat mix_{};
    std::wstring name_;
    std::wstring endpoint_id_;
    int64_t frames_read_ = 0;
    int64_t frame_cap_ = 0;
    bool com_ref_taken_ = false;
};

}  // namespace sotto