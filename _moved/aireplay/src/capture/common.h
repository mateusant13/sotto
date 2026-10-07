// common.h — shared plumbing for the Sotto capture/encode lane.
//
// House rules this file exists to serve:
//   * nothing here opens an audio device, creates a window, or starts a thread pool;
//   * every counter the "zero frame loss" proof needs is in ONE struct (Stats), so a
//     clip can always say how many frames it is missing;
//   * the log is one line per fact, machine-readable, and it goes to stdout AND a file.
#pragma once
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <windows.h>
#include <d3d11.h>
#include <dxgi1_2.h>

#include <atomic>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace aireplay {

// ------------------------------------------------------------------ logging
void log_open_file(const std::string& path);
void log_close_file();
void log_line(const char* fmt, ...);

// ------------------------------------------------------------------ helpers
std::string narrow(const wchar_t* w);
std::string hr_str(long hr);            // "0x887A0004 (DXGI_ERROR_...)"

// QPC — the ONE clock this product anchors everything to (spec 03 §2.1).
uint64_t qpc_freq();
uint64_t qpc_now_ns();

// A ~1 ms wait that is NOT quantised to the 15.6 ms system tick.  MEASURED: the capture
// loop's `Sleep(1)` on an empty frame pool really slept ~15.6 ms, which at 60 fps means
// the loop missed a frame every time it found the pool empty.  This uses a
// high-resolution waitable timer, so the wait costs ~1 ms and does NOT raise the global
// timer resolution (which would change the owner's power behaviour for every process).
void micro_wait_ms(uint32_t ms);

// ------------------------------------------------------------------ counters
// Every field is a fact the receipt must be able to quote. Nothing here is an estimate.
struct Stats {
    std::atomic<uint64_t> frames_captured{0};      // frames handed to us by WGC
    std::atomic<uint64_t> frames_converted{0};     // BGRA->NV12 draws completed
    std::atomic<uint64_t> frames_encoded{0};       // bitstreams received from NVENC
    std::atomic<uint64_t> frames_ring_dropped{0};  // ring had no room without losing its last IDR
    std::atomic<uint64_t> frames_encode_failed{0};
    std::atomic<uint64_t> frame_pool_empty_polls{0};
    std::atomic<uint64_t> convert_ns{0};
    std::atomic<uint64_t> encode_ns{0};
    std::atomic<uint64_t> wall_ns{0};
    std::atomic<uint64_t> idr_forced{0};
    std::atomic<uint64_t> idr_observed{0};
    std::atomic<uint64_t> ring_evictions{0};
    std::atomic<uint64_t> cuts_written{0};
    std::atomic<uint64_t> cuts_refused{0};
    std::atomic<uint64_t> peak_rss_bytes{0};
    std::atomic<uint64_t> rss_at_arm_bytes{0};
    std::atomic<uint64_t> cpu_user_100ns{0};
    std::atomic<uint64_t> cpu_kernel_100ns{0};
};

// Process RSS / CPU samplers — cheap, called from the run loop, never from a probe thread.
uint64_t process_rss_bytes();
void     process_cpu_100ns(uint64_t* user, uint64_t* kernel);

// ------------------------------------------------------------------ H.264 bitstream helpers
struct NalSpan {
    const uint8_t* data;   // points INTO the original buffer, past the start code
    size_t         size;
    uint8_t        type;   // nal_unit_type (H.264: b0 & 0x1F)
};

// Split an Annex-B access unit into NAL units (3- and 4-byte start codes both handled).
void annexb_split(const uint8_t* data, size_t size, std::vector<NalSpan>& out);

// Rewrite one Annex-B access unit into AVCC form (4-byte big-endian lengths).
void annexb_to_avcc(const uint8_t* data, size_t size, std::vector<uint8_t>& out);

// ------------------------------------------------------------------ byte helpers
inline void put_u8(std::vector<uint8_t>& v, uint8_t x) { v.push_back(x); }
inline void put_u16be(std::vector<uint8_t>& v, uint16_t x) {
    v.push_back((uint8_t)(x >> 8)); v.push_back((uint8_t)x);
}
inline void put_u24be(std::vector<uint8_t>& v, uint32_t x) {
    v.push_back((uint8_t)(x >> 16)); v.push_back((uint8_t)(x >> 8)); v.push_back((uint8_t)x);
}
inline void put_u32be(std::vector<uint8_t>& v, uint32_t x) {
    v.push_back((uint8_t)(x >> 24)); v.push_back((uint8_t)(x >> 16));
    v.push_back((uint8_t)(x >> 8));  v.push_back((uint8_t)x);
}
inline void put_u64be(std::vector<uint8_t>& v, uint64_t x) {
    put_u32be(v, (uint32_t)(x >> 32)); put_u32be(v, (uint32_t)x);
}

} // namespace aireplay
