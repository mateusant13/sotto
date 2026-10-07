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

struct Mp4Config {
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t fps_num = 60;
    uint32_t fps_den = 1;
    uint32_t timescale = 90000;          // media ticks per second
    std::vector<uint8_t> sps;            // H.264 SPS payload, no start code, no length
    std::vector<uint8_t> pps;            // H.264 PPS payload, no start code, no length
};

class Mp4Writer {
public:
    ~Mp4Writer();

    bool open(const std::string& path, const Mp4Config& cfg, std::string* err);

    // `data` is ONE access unit with NAL units already length-prefixed (AVCC).
    bool write_sample(const uint8_t* data, size_t size, bool is_sync,
                      uint64_t duration_ticks, std::string* err);

    bool close(std::string* err);

    uint64_t sample_count() const { return sizes_.size(); }
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
};

} // namespace aireplay
