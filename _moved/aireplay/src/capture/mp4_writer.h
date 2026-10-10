// mp4_writer.h — a minimal, STREAMING ISO-BMFF (MP4) muxer for H.264/AVC.
//
// Spec 03 §2.7.  The ring holds Annex-B access units exactly as NVENC emitted them; this
// writer takes them already rewritten to AVCC (4-byte big-endian NAL lengths) and builds
// the `avcC` record from the SPS/PPS carried by the cut's base IDR.
//
// Streaming shape: `ftyp` + an `mdat` whose payload is appended as samples arrive, and a
// `moov` written by close().  One chunk per sample (legal, simple, and it makes `stco`
// trivially correct).  A clip larger than the 32-bit `mdat` limit is REFUSED loudly
// instead of silently truncated — a corrupt clip is worse than an error.
#pragma once
#include "common.h"

namespace aireplay {

// ------------------------------------------------------------------ the audio trak
// The ring carries the canonical ASR contract (16 kHz mono PCM16, audio_contract.h) because
// that is what the transcriber consumes.  A CLIP carries one of two shapes, decided at
// RUNTIME and reported, never guessed:
//
//   AAC-LC via the Windows Media Foundation encoder (48 kHz stereo — the MFT refuses
//   16 kHz mono at SetInputType, so the tap resamples).  The AAC frames go into the SAME
//   `mdat` as the video and are described by `mp4a` + `esds` whose DecoderSpecificInfo is
//   the AudioSpecificConfig.  No ADTS headers: the sample entry already carries the config.
//
//   raw PCM (`sowt`, the ring's own 16 kHz mono) — the fallback when this host has no AAC
//   encoder at all.  The samples are the ring's bytes verbatim.
//
// Either way the trak is a SECOND trak in the same moov (next_track_ID becomes 3), so a
// consumer sees exactly one video stream and one audio stream in one file.
struct Mp4AudioConfig {
    bool     enabled = false;
    bool     pcm = false;            // true -> `sowt`; false -> `mp4a` + `esds`
    uint32_t sample_rate = 48000;    // the rate of the samples handed to write_audio_sample()
    uint32_t channels = 2;
    uint32_t sample_width = 2;       // PCM route: bytes per sample per channel
    uint32_t frame_samples = 1024;   // AAC route: samples per AAC frame
    uint32_t bitrate = 128000;       // esds max/avg bitrate (informational)
    std::vector<uint8_t> asc;        // AAC route: the AudioSpecificConfig
};

struct Mp4Config {
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t fps_num = 60;
    uint32_t fps_den = 1;
    uint32_t timescale = 90000;          // media ticks per second
    std::vector<uint8_t> sps;            // H.264 SPS payload, no start code, no length
    std::vector<uint8_t> pps;            // H.264 PPS payload, no start code, no length
    Mp4AudioConfig audio;                 // optional second trak; enabled=false -> video only
};

class Mp4Writer {
public:
    ~Mp4Writer();

    bool open(const std::string& path, const Mp4Config& cfg, std::string* err);

    // `data` is ONE access unit with NAL units already length-prefixed (AVCC).
    bool write_sample(const uint8_t* data, size_t size, bool is_sync,
                      uint64_t duration_ticks, std::string* err);
    // ONE audio sample, into the SAME mdat as the video.  `duration_ticks` is expressed in
    // the AUDIO timescale and may be 0, in which case it is derived from the audio config
    // (AAC: one frame of frame_samples; PCM: the byte count over the frame size).  Returns
    // false — loudly, with a reason — when audio is not enabled at all: a silent drop would
    // produce a video-only clip that looks like the audio was written.
    bool write_audio_sample(const uint8_t* data, size_t size, uint64_t duration_ticks,
                            std::string* err);

    bool close(std::string* err);

    uint64_t sample_count() const { return sizes_.size(); }
    uint64_t audio_sample_count() const { return a_sizes_.size(); }
    // Audio duration in SECONDS, as the samples were actually written — the number the gate
    // compares against the video duration (contract: within 50 ms).
    double   audio_seconds() const;
    bool     audio_is_pcm() const { return cfg_.audio.pcm; }
    uint32_t audio_sample_rate() const { return cfg_.audio.sample_rate; }
    uint32_t audio_channels() const { return cfg_.audio.channels; }
    uint64_t bytes_written() const { return (uint64_t)pos_; }

private:
    FILE*    f_ = nullptr;
    uint64_t pos_ = 0;
    uint64_t mdat_start_ = 0;      // file offset of the 'mdat' box header
    uint64_t mdat_payload_ = 0;
    Mp4Config cfg_;
    std::vector<uint32_t> sizes_;
    std::vector<uint64_t> offsets_;
    std::vector<uint32_t> sync_numbers_;             // 1-based
    std::vector<std::pair<uint32_t, uint32_t>> stts_; // (count, delta)

    bool build_audio_trak(std::vector<uint8_t>& out, uint64_t movie_timescale,
                          uint64_t movie_duration, std::string* err) const;

    std::vector<uint32_t> a_sizes_;                            // audio samples, same mdat
    std::vector<uint64_t> a_offsets_;
    std::vector<std::pair<uint32_t, uint32_t>> a_stts_;        // (count, delta), audio ts
};

} // namespace aireplay
