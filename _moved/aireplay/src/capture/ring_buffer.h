// ring_buffer.h — the replay ring: ENCODED frames in RAM, keyframe-bookmarked.
//
// Spec 03 §2.6 / research 01 §2.  RAM, not disk: the hotkey must be a pointer flip, not
// a seek plus concat, and must not depend on a filesystem a game or an AV scanner can
// stall.  Law 7: the ring is the memory hog, so the arena is allocated ONCE and the
// receipt quotes its real size — there is no per-frame allocation to hide the cost in.
//
// Two invariants that make "zero frame loss" a measurable claim rather than a slogan:
//   1. eviction NEVER removes the last IDR still held; if it would, the frame is dropped
//      and COUNTED (dropped() ), and the encoder is asked to force an IDR immediately;
//   2. a cut PINS the entries it needs, so appending during the write cannot overwrite
//      the bytes being muxed.
#pragma once
#include "common.h"

#include <mutex>

namespace aireplay {

struct RingEntry {
    uint64_t abs_off = 0;   // absolute byte offset in the (circular) stream
    uint64_t qpc_ns = 0;    // capture timestamp of the frame this bitstream came from
    uint64_t seq = 0;       // monotonic frame sequence
    uint32_t size = 0;
    bool     is_idr = false;
    int      picture_type = -1;
    uint32_t nal_flags = 0; // bit0 SPS seen, bit1 PPS seen
};

class RingBuffer {
public:
    ~RingBuffer();

    bool init(size_t capacity_bytes, std::string* err);

    // Returns false when the frame could not be stored.  That is a DROPPED frame and it
    // is counted — never silently absorbed (law 1).
    bool append(const uint8_t* data, size_t size, bool is_idr, int picture_type,
                uint64_t qpc_ns, uint64_t seq);

    // --- reader side (the cut thread) ------------------------------------------------
    // Pin: no entry with abs_off >= first_abs may be evicted until unpin().
    void pin(uint64_t first_abs);
    void unpin();

    size_t count() const;
    bool   entry_at(size_t i, RingEntry* out) const;
    bool   entry_by_abs(uint64_t abs_off, RingEntry* out) const;
    bool   read_entry(const RingEntry& e, std::vector<uint8_t>& out) const;
    uint64_t newest_abs() const;          // one past the last stored byte
    uint64_t oldest_abs() const;

    // Spec 03 §2.7: the first entry with is_idr whose qpc_ns >= t_cut - window_ns.
    // Returns false when no such IDR exists (the caller must then either use the oldest
    // IDR held — find_oldest_idr() — or REFUSE to write a clip).
    bool find_cut_base(uint64_t t_cut_ns, uint64_t window_ns, size_t* index) const;
    bool find_oldest_idr(size_t* index) const;

    size_t   capacity() const { return cap_; }
    size_t   bytes_used() const;
    uint64_t dropped() const { return dropped_; }
    uint64_t evictions() const { return evictions_; }

private:
    void evict_front_locked();
    bool idr_count_at_least_two_locked() const;

    mutable std::mutex      mu_;
    std::vector<uint8_t>    arena_;
    size_t                  cap_ = 0;
    std::vector<RingEntry>  entries_;   // ordered by abs_off; entries_[first_] is the oldest
    size_t                  first_ = 0;
    size_t                  used_ = 0;
    uint64_t                head_abs_ = 0;
    uint64_t                dropped_ = 0;
    uint64_t                evictions_ = 0;
    bool                    pinned_ = false;
    uint64_t                pin_abs_ = 0;
    int                     idr_live_ = 0;
};

} // namespace aireplay
