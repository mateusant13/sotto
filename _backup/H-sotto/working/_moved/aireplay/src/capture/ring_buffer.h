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

// ------------------------------------------------------------------ the ring budget (law 7)
// WHY THIS LIVES HERE AND NOT IN d3d11_ctx: the arena is a std::vector<uint8_t> on the
// HEAP — committed in full, in SYSTEM RAM, at init().  Nothing in the ring path allocates
// video memory, so budgeting the arena from DXGI DedicatedVideoMemory prices bytes from a
// pool this buffer never draws from (receipt-14).  The budget therefore belongs to the
// thing that actually allocates, and it is QUERYABLE so a receipt can quote a number that
// was measured at runtime rather than one that was reasoned about on paper.
//
// WHICH POOL THE POLICY IS PRICED AGAINST — stated here because the reviewer's F2 found the
// old version ambiguous (2026-10-07).  It is BOTH, deliberately, and neither term is a
// footnote:
//   * TOTAL physical RAM carries the PROPORTIONAL rule (25%).  A budget must not shrink
//     just because the owner has a browser open, so it is priced against the machine, not
//     against the moment.
//   * AVAILABLE physical RAM at query time carries the GUARD (50%).  Total is what the
//     machine owns; availability is what actually decides whether this allocation
//     succeeds.  Pricing only against total is how a 4 GiB commit turns into std::bad_alloc
//     on a machine with 1 GiB free — the case the old code could not reach because its cap
//     topped out at 2048 MiB.
//   * A failed commit is now REPORTED (init() returns false with a message).  It is not a
//     silent short arena and it is not a std::terminate.
struct RingBudget {
    uint64_t total_physical_bytes = 0;   // MEASURED: GlobalMemoryStatusEx().ullTotalPhys
    uint64_t avail_physical_bytes = 0;   // MEASURED: GlobalMemoryStatusEx().ullAvailPhys
    uint64_t quarter_bytes        = 0;   // 25% of total  (MiB-aligned DOWN)
    uint64_t half_avail_bytes     = 0;   // 50% of avail  (MiB-aligned DOWN)
    uint64_t cap_bytes            = 0;   // min(ceiling, quarter, half_avail), then floored
    bool     query_ok             = false;  // GlobalMemoryStatusEx succeeded
    bool     ceiling_binds        = false;  // the 4 GiB ceiling bound
    bool     availability_binds   = false;  // the 50%-of-AVAILABLE guard bound
    bool     floor_applied        = false;  // the 256 MiB floor bound (or a failed query)
};

// The policy, in one place, with no allocation and no side effects: safe to call from a
// probe, from arm(), or from a log line that runs before the arena exists.
RingBudget query_ring_budget();
uint64_t   ring_budget_cap_bytes();

// THE POLICY ITSELF, as a pure function of two numbers.  query_ring_budget() is this plus
// the GlobalMemoryStatusEx call, which is why the ceiling / 25% / availability / floor terms
// can be tested over SYNTHETIC machines: on this host (47.74 GiB total) min(4 GiB, 25%) is
// 4 GiB for any f >= 8.38%, so two of the three terms are unobservable here and only this
// seam can reach them.  query_ok=false means "the pool could not be read": the floor is used
// and the caller is told, rather than a guess being dressed up as a measurement.
RingBudget ring_budget_from(uint64_t total_physical_bytes, uint64_t avail_physical_bytes,
                            bool query_ok);

// The decision init() makes, exposed as a PURE function so the clamp can be tested without
// committing gigabytes:  requested above the cap -> the cap, else the request untouched.
size_t ring_apply_budget(size_t requested_bytes, const RingBudget& b);

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

    // The budget this instance was actually held to, as MEASURED at init() time.
    const RingBudget& budget() const { return budget_; }
    // Bytes init() was asked for before the clamp; 0 when nothing was clamped.  Kept so the
    // clamp is a fact on the record and not a silent shrink.
    uint64_t clamped_from() const { return clamped_from_; }

private:
    void evict_front_locked();
    bool idr_count_at_least_two_locked() const;

    mutable std::mutex      mu_;
    std::vector<uint8_t>    arena_;
    size_t                  cap_ = 0;
    RingBudget              budget_;
    uint64_t                clamped_from_ = 0;
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
