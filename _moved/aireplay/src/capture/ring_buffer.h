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
#include "audio_contract.h"   // aireplay::audio::kAsr* -- the ASR contract the AudioRing is priced in.

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

// ------------------------------------------------------------------ the AUDIO ring
// The video ring above carries NVENC Annex-B access units and is silent by construction.
// Instant replay needs the SOUND of the last N seconds too, so the same ring budget that
// prices video now prices this one: PCM at the canonical contract (16 kHz, mono, int16 =
// 32 B per frame, 32 000 B/s -- audio_contract.h), every frame stamped with the SAME qpc
// clock the video ring stamps f.qpc_ns with, so the cut window [base_qpc_ns, cut_qpc_ns]
// is ONE window across both rings.
//
// Design notes:
//   * Circular arena of FRAMES with absolute frame indices, mirroring RingBuffer above.
//     The size is derived from the MEASURED resident RAM via ring_budget_from(), never from
//     VRAM (nvidia-smi is unusable on this host) and never larger than the caller asked for.
//   * A GAP in the audio stream (a tap stall, a device restart) is filled with SILENCE and
//     counted, never skipped: a skipped gap would shift the sound against the video for the
//     rest of the replay.  copy_window() reports how many frames it manufactured.
//   * copy_window() copies under the lock and returns owned memory, so a cut can be taken on
//     the cut thread while the capture thread keeps appending.
class AudioRing {
public:
    bool init(double seconds, std::string* err);
    void shutdown();

    // Appends silence up to qpc_ns when there was a gap, then frames of PCM.  Returns false
    // only when the ring was never initialised.
    bool push(const int16_t* pcm, uint32_t frames, uint64_t qpc_ns);

    // Copies the frames whose time falls inside [from_qpc_ns, to_qpc_ns] and reports the qpc
    // stamp of the first sample.  Silence frames synthesised to fill gaps are counted out.
    bool copy_window(uint64_t from_qpc_ns, uint64_t to_qpc_ns, std::vector<int16_t>* out,
                    uint64_t* out_first_qpc_ns, uint64_t* silence_frames_filled,
                    bool* head_clamped, std::string* err) const;

    uint64_t capacity_frames() const { return cap_frames_; }
    uint64_t frames_pushed() const;
    uint64_t frames_dropped() const { return dropped_; }
    uint64_t silence_frames() const { return silence_filled_; }
    uint64_t bytes_used() const;
    bool    empty() const;
    double  seconds_held() const;
    double  seconds_requested() const { return requested_seconds_; }
    const RingBudget& budget() const { return budget_; }
    uint64_t clamped_from() const { return clamped_from_; }
    uint32_t rate() const { return audio::kAsrSampleRate; }
    uint32_t channels() const { return audio::kAsrChannels; }

private:
    void evict_front_locked();
    void append_locked(uint32_t frames, uint64_t qpc_ns);

    mutable std::mutex      mu_;
    std::vector<int16_t>    arena_;        // cap_frames_ samples, mono
    uint64_t                cap_frames_ = 0;
    double                  requested_seconds_ = 0;
    RingBudget              budget_;
    uint64_t                clamped_from_ = 0;
    size_t                  first_ = 0;      // arena index of the oldest held sample
    uint64_t                used_ = 0;       // samples held
    uint64_t                head_abs_ = 0;   // absolute index of the NEXT sample
    uint64_t                head_qpc_ns_ = 0;// qpc stamp of head_abs_
    bool                    have_stamp_ = false;
    uint64_t                pushed_ = 0;     // real samples accepted
    uint64_t                dropped_ = 0;
    uint64_t                silence_filled_ = 0;
};

} // namespace aireplay
