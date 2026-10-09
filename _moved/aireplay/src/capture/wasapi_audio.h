// wasapi_audio.h — system audio capture by WASAPI LOOPBACK, for the replay product.
//
// WHY THIS FILE EXISTS (the measured reason)
// ------------------------------------------
// 8 of 8 sample clips in this repo carry NO audio stream, while `src/asr/audio.py`
// REFUSES anything that is not 16 kHz mono PCM16 (`audio.py:53-61`, `_check`). So
// nothing feeds the transcript: the product's audio path did not exist.
//
// `H:\sotto\worker\wasapi_loopback.py` is a WORKING WASAPI loopback implementation in
// Python on this very box, with its own receipts. This is its C++ counterpart. Every
// measured fact it encodes is CARRIED OVER here, not re-derived, and the ones that
// decide the design are quoted with their provenance below.
//
// WHAT WASAPI LOOPBACK IS (Microsoft Learn — the vendor-documented, driver-free path)
//   https://learn.microsoft.com/windows/win32/coreaudio/loopback-recording
//     1. CoCreateInstance(CLSID_MMDeviceEnumerator)            -> IMMDeviceEnumerator
//     2. GetDefaultAudioEndpoint(eRender, role) / EnumAudioEndpoints(eRender, ACTIVE)
//     3. IMMDevice::Activate(IID_IAudioClient)                 -> IAudioClient
//     4. IAudioClient::GetMixFormat()      <- the ONLY format a loopback stream takes
//     5. IAudioClient::Initialize(SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, ..., mix, NULL)
//     6. IAudioClient::GetService(IID_IAudioCaptureClient)    -> IAudioCaptureClient
//     7. Start(), then poll GetNextPacketSize / GetBuffer / ReleaseBuffer
//
// THE MEASURED FACTS THIS FILE IS BUILT AROUND (do not re-litigate)
//   * THE DEVICE NAME ALONE DOES NOT IDENTIFY WHAT WAS OPENED. On this box
//     "CABLE Output (VB-Audio Virtual Cable)" exists at THREE indices under THREE host
//     APIs — MME #2, DirectSound #15, WASAPI #32 — and they are NOT interchangeable.
//     So every status this file emits carries `api=`. See `kAudioApiName` below and the
//     lane brief's routing law. A report that says only a device name is a claim the
//     owner cannot act on.
//   * THE LOOPBACK IS ASYMMETRIC ACROSS HOST APIS ON THIS BOX: rendering into the MME
//     `CABLE Input` and capturing the DirectSound `CABLE Output` delivered an injected
//     tone at peak 0.4999; DirectSound render -> DirectSound capture does NOT loop back
//     (peak 0.00003). A WASAPI loopback tap is therefore the only rung this component
//     offers, and it never claims to speak for the other two.
//   * SILENCE IS USUALLY CORRECT BEHAVIOUR. With nothing playing, every loopback reads
//     DIGITAL SILENCE (measured: a passive 22 s listen across all of them peaked at
//     0.000122). A tap that opens and reads silence has NOT failed to open; it has
//     correctly reported that nothing is routed into the endpoint. That is why
//     `AudioState::kSilentDevice` is a named, distinct state and why the component
//     SAYS SO on its own log line instead of returning an empty success.
//
// HOUSE RULE HONOURED HERE: this component NEVER opens a playback or exclusive device.
// AUDCLNT_SHAREMODE_SHARED + a loopback flag is a READ-ONLY tap: it cannot mute, cannot
// take the endpoint exclusive, and cannot disturb what the owner is listening to. It is
// still an audio device open, and the lane brief says so out loud rather than hiding it.
#pragma once
#include "common.h"

namespace aireplay {

// The ONE host API this component ever opens. It is carried on EVERY status line,
// every endpoint record and every ladder step, because a device NAME does not
// identify what was opened on this box (see the header comment).
extern const char* const kAudioApiName;   // "Windows WASAPI (loopback)"

// The peak below which a delivered window counts as DIGITAL SILENCE rather than audio.
// NOT A TUNING KNOB — a bracket, and both ends are measured on this box:
//   0.000122  the highest peak a 22 s passive listen across every loopback reached
//             while nothing was playing (digital silence ceiling)
//   0.4999    the peak an INJECTED TONE reached through the MME CABLE Input ->
//             DirectSound CABLE Output path
// 1e-3 sits ~8x above the silence ceiling and ~500x below the signal, so it separates
// the two measured populations with a wide margin on both sides.
constexpr float kAudioSilencePeakFloor = 1.0e-3f;

// The ASR sink contract, quoted from the other side of the boundary so the two files
// cannot drift: `src/asr/constants.py` `SAMPLE_RATE = 16_000` and `src/asr/audio.py`
// `_check()` raises on sampwidth != 2, channels != 1 or rate != 16000.
constexpr uint32_t kAsrSampleRate = 16000;
constexpr uint16_t kAsrChannels   = 1;
constexpr uint16_t kAsrBits       = 16;

enum class AudioRole : uint32_t { kConsole = 0, kMultimedia = 1, kCommunications = 2 };

// The verdict vocabulary. `silent-device`, `device-exhausted` and `open-failed` are the
// SAME WORDS the Python worker already emits (`H:\sotto\worker\sotto_worker.py`), so a
// report from either implementation is comparable without a translation table.
enum class AudioState : int {
    kOk = 0,           // a window was delivered above kAudioSilencePeakFloor
    kSilentDevice,     // opened, frames DELIVERED, peak <= floor. Correct behaviour with
                       // nothing routed in — reported LOUDLY, never an empty success.
    kNoSignal,         // opened, ZERO frames arrived in the whole window
    kOpenFailed,       // an HRESULT failed (activate / initialize / getservice / start)
    kNoEndpoint,       // this host has no ACTIVE render endpoint at all
    kDeviceExhausted,  // the ladder walked every candidate and none produced audio
    kClosed,           // not open
};
const char* audio_state_name(AudioState s);

// THE VERDICT FUNCTION, as a PURE function of the two numbers that decide it.
//
// `WasapiAudio::judge()` is exactly this and nothing else; it is factored out so the
// promise "a below-floor peak is a NAMED verdict, not an empty success" can be checked
// on a FIXED TABLE OF INPUTS instead of only on whatever the machine happens to be
// playing at the time. That is the difference between a control that can say no and a
// control that is decorative: on a host with audio flowing, a machine-dependent check
// has both arms answer `ok` and proves nothing (MEASURED, gate ARM-C first run:
//
//   live_state=ok  control_state=ok  disagrees=False
//
// while the cure under test was, in that run, not exercised at all).
AudioState audio_state_for(bool open, uint64_t frames, float peak);

// COM REFERENCE ACCOUNTING, for the one bug that a five-cycle run cannot catch.
//
// CoUninitialize is reference-counted, so giving a reference back twice does not crash:
// it walks the apartment count down, and the failure surfaces on some LATER COM call,
// looking like an unrelated problem. MEASURED here: `com_ref_taken_ = com.took()` beside
// a ComScope destructor uninitialised COM twice per open/close cycle and survived a
// single cycle -- so "it ran" proved nothing.
//
// These counters make the imbalance VISIBLE as a number: the balance is
// (initialises - uninitialises) and must return to 0 after every open/close cycle.
// A non-zero balance at rest is an unbalanced reference, full stop -- no crash needed.
int64_t com_reference_balance();
int64_t com_reference_taken_count();
int64_t com_reference_released_count();

// One ACTIVE render endpoint, as WASAPI publishes it. `api` is ALWAYS populated.
struct AudioEndpoint {
    std::string api;          // == kAudioApiName, on every record. Never empty.
    std::string endpoint_id;  // IMMDevice::GetId — the only unambiguous identity.
    std::string name;         // PKEY_Device_FriendlyName, else the endpoint id.
    uint32_t rate = 0;        // MIX rate (GetMixFormat). A loopback stream cannot
                              // negotiate anything else.
    uint16_t channels = 0;
    uint16_t bits = 0;
    uint16_t format_tag = 0;  // RESOLVED: WAVE_FORMAT_PCM(1) or WAVE_FORMAT_IEEE_FLOAT(3)
    uint16_t block_align = 0;
    bool     is_default = false;
    std::string role;       // "eConsole" / "eMultimedia" -- WHICH default was asked for
    bool     meter_available = false;  // IAudioMeterInformation answered at all
    float    meter_peak = 0.0f;       // device meter, read WITHOUT opening a stream
    // Why this endpoint is in the ladder, in one machine-readable line.
    std::string rung_why;
};

// One delivered block: float32 MONO in [-1, 1] at `rate`.
//
// FORMAT, AND WHY IT IS NOT THE ASR'S 16 kHz MONO PCM16:
//   A WASAPI loopback stream has NO format negotiation — it must be initialized with
//   the endpoint's MIX format, so asking for 16 kHz mono at open time FAILS (the same
//   constraint the Python tap documents at `wasapi_loopback.py:22-24`). The mix format
//   on this box is float32 or PCM16 at 48 kHz, usually stereo. The conversion therefore
//   happens HERE, in software, in two documented steps:
//     1. decode + downmix  -> float32 MONO, mix rate   (this struct)
//     2. resample + quantise -> int16 16 kHz mono       (`to_asr_pcm16`)
//   Why float32 in between and not PCM16: the loop runs 16 kHz -> 48 kHz -> 16 kHz
//   inside the endpoint, and every extra 16-bit round trip is a quantisation of a
//   signal that is going to be quantised again anyway. One quantisation, at the end,
//   at the rate the model actually consumes.
struct AudioBlock {
    const float* samples = nullptr;
    uint32_t frames = 0;
    uint32_t rate = 0;
    uint64_t qpc_ns = 0;   // QueryPerformanceCounter at the first frame of this block
    uint64_t device_pos = 0;  // the loopback device position of the first frame
};

// Everything the run has to be able to quote. Every field is a MEASURED count.
struct AudioCounters {
    uint64_t packets = 0;             // GetBuffer calls that returned frames
    uint64_t frames = 0;              // frames the endpoint handed over
    uint64_t silent_packets = 0;      // packets GetBuffer flagged AUDCLNT_BUFFERFLAGS_SILENT
    uint64_t position_gap_packets = 0;// packets whose device position did not continue
    uint64_t empty_polls = 0;         // GetNextPacketSize == 0
    uint64_t blocks = 0;              // blocks delivered to the caller
    uint64_t dropped_frames = 0;      // frames discarded because the caller stopped pulling
    uint32_t endpoint_grant_frames = 0;  // IAudioClient::GetBufferSize, MEASURED per open
    float    peak = 0.0f;             // max |sample| over the WHOLE open window
    float    rms = 0.0f;              // over the WHOLE open window
};

class WasapiAudio {
public:
    ~WasapiAudio();

    // EVERY ACTIVE render endpoint, ORDERED BY WHO IS RENDERING NOW (device meter peak,
    // descending; the DEFAULT endpoint only breaks a tie). One endpoint that cannot be
    // described never hides the others. Every record carries `api`.
    // `meter_ms` is the sampling window PER ENDPOINT (not an instantaneous read): a
    // single read cannot tell "this endpoint is idle" from "the owner is between two
    // tracks", which is the defect that cost the Python ladder a whole tap window.
    bool enumerate(std::vector<AudioEndpoint>* out, uint32_t meter_ms, std::string* err);

    // Open `ep` as a LOOPBACK tap and start it. The mix format is read back from the
    // device and stored; the caller gets it from `format()`.
    bool open(const AudioEndpoint& ep, uint32_t block_ms, std::string* err);

    // Pull one block. Returns true when `out` is filled. Bounded: it gives up after
    // `timeout_ms` rather than blocking forever on a device that stopped rendering.
    // `out->samples` stays valid until the next call on THIS object.
    bool try_get_block(AudioBlock* out, uint32_t timeout_ms, std::string* err);

    // Read whatever the endpoint has produced and throw it away. Keeps the shared-mode
    // ring moving when the caller wants the meter but not the samples.
    void drain(uint32_t max_ms);

    // Close and release every COM reference. Idempotent. After it returns the object
    // can be re-opened.
    void close();

    bool is_open() const { return client_ != nullptr; }
    const AudioEndpoint& endpoint() const { return ep_; }
    const AudioCounters& counters() const { return c_; }
    uint32_t block_frames() const { return block_frames_; }
    uint32_t poll_period_ms() const { return poll_period_ms_; }

    // The verdict for the window measured SO FAR. This is the function the "run must be
    // loud about silence" rule lives in: it is pure, it is total, and it maps a
    // delivered-but-digital window onto `kSilentDevice` instead of onto `kOk`.
    AudioState judge() const;

    // One machine-readable line per fact, ALWAYS prefixed with `api=`. The caller
    // prints it; `log_state` also writes it to the house log itself.
    std::string status_line() const;
    // Logged on its own account, loudly, the moment a window is judged silent.
    void log_state(AudioState s, uint32_t window_ms) const;

    const std::string& last_error() const { return last_err_; }

private:
    bool open_common(const AudioEndpoint& ep, uint32_t block_ms, std::string* err);
    bool pump_once(AudioBlock* out, std::string* err);   // one GetBuffer pass
    void  release_all();
    void  decode_packet(const uint8_t* data, uint32_t frames, uint32_t channels,
                        bool float_fmt, std::vector<float>& dst);

    AudioEndpoint ep_;
    AudioCounters c_;
    std::string  last_err_;

    void* enumerator_ = nullptr;
    void* device_    = nullptr;
    void* client_    = nullptr;
    void* capture_   = nullptr;
    bool  com_ref_taken_ = false;   // THIS object's CoInitializeEx took a reference
    bool  started_    = false;

    uint32_t block_frames_ = 0;
    uint32_t poll_period_ms_ = 5;
    uint16_t mix_format_tag_ = 0;
    uint16_t mix_block_align_ = 0;
    bool     mix_is_float_ = false;

    std::vector<float> accum_;      // decoded mono, frames not yet emitted as a block
    std::vector<float> blockbuf_;   // the block handed to the caller; stable per call
    uint64_t accum_pos_ = 0;        // device position of accum_[0]
    uint64_t prev_pos_ = 0;         // device position of the previous packet
    uint64_t prev_frames_ = 0;      // frames in that packet -- continuity needs both
    bool     have_prev_pos_ = false;
    double   sum_sq_ = 0.0;         // for the rms on the whole window
};

// The ASR sink: resample float32 mono to int16 at `out_rate` (the product's value is
// `kAsrSampleRate`). Linear interpolation, which is what a 48 kHz -> 16 kHz integer
// decimation can honestly claim: the exact-N factor path below is a box average, and
// anything else would be a resampler this lane cannot measure.
//
// It EXITS LOUDLY rather than guessing: a rate the mix cannot produce, or a non-mono
// block, is an error string, never a silent conversion. `src/asr/audio.py:53-61` refuses
// a wrong format the same way, and a silent resample is how a language or a level gets
// destroyed.
bool to_asr_pcm16(const AudioBlock& in, uint32_t out_rate,
                  std::vector<int16_t>* out, std::string* err);

// One rung of the ladder: an endpoint tapped for a BOUNDED window, with the verdict and
// the numbers that produced it. This is the record the gate and any receipt quote.
struct AudioLadderStep {
    AudioEndpoint endpoint;
    AudioState    state = AudioState::kClosed;
    AudioCounters counters;
    uint32_t      window_ms = 0;
    std::string   note;     // why this step ended here, in words
};

struct AudioLadderResult {
    std::vector<AudioLadderStep> steps;
    size_t   chosen = (size_t)-1;     // index of the first step that produced AUDIO
    AudioState final_state = AudioState::kClosed;
    uint32_t window_ms = 0;
};

// Walk `candidates` in order, tapping each for `window_ms`. Stops at the first step
// that produced audio. If every candidate is silent it says so: the final state is
// `kSilentDevice` (the last tap delivered silence) or `kNoSignal` (none of them ever
// delivered a frame), NOT an empty success and NOT a fabricated one. Audio is never
// invented here: every step's peak is a measurement of what the device handed over.
bool run_audio_ladder(std::vector<AudioEndpoint> candidates, uint32_t window_ms,
                      uint32_t block_ms, AudioLadderResult* out, std::string* err);

} // namespace aireplay