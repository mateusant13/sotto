#include "ring_buffer.h"

#include <algorithm>
#include <new>
#include <stdexcept>

namespace aireplay {

RingBuffer::~RingBuffer() {}

// ------------------------------------------------------------------ the ring budget (law 7)
// The arena is SYSTEM RAM (one heap vector, committed in full below).  So the budget is
// priced against physical memory, on THREE terms:
//     cap = min( 4 GiB,               // the "do not eat the machine" ceiling
//                25% of TotalPhys,   // proportional to the machine
//                50% of AvailPhys )  // what can ACTUALLY be committed right now
//     then floored at 256 MiB.
// TOTAL carries the proportional rule because a budget must not shrink every time the owner
// opens a browser; AVAILABILITY carries the guard because availability — not total — is what
// decides whether the commit below succeeds (reviewer's F2).  MiB-aligned DOWN: a budget is
// an upper bound.  The floor is what keeps a small machine usable (init() still refuses
// < 16 MiB, which is a different law: cuttability, not budgeting).
static const uint64_t RING_CAP_CEILING    = 4ull << 30;    // 4 GiB
static const uint64_t RING_CAP_FLOOR      = 256ull << 20;  // 256 MiB
static const uint64_t MIB                 = 1ull << 20;

static uint64_t align_down_mib(uint64_t bytes)
{
    return (bytes / MIB) * MIB;
}

RingBudget ring_budget_from(uint64_t total_physical_bytes, uint64_t avail_physical_bytes,
                            bool query_ok)
{
    RingBudget b;
    b.query_ok = query_ok;

    if (!query_ok) {
        // Say so rather than pretending to measure.  The floor is the honest answer when
        // the pool cannot be read: it is the smallest budget we are willing to run with.
        b.cap_bytes     = RING_CAP_FLOOR;
        b.floor_applied = true;
        return b;
    }

    b.total_physical_bytes = total_physical_bytes;
    b.avail_physical_bytes = avail_physical_bytes;
    b.quarter_bytes    = align_down_mib(total_physical_bytes / 4ull);
    b.half_avail_bytes = align_down_mib(avail_physical_bytes / 2ull);   // the 50% guard

    uint64_t cap = b.quarter_bytes;
    if (cap > RING_CAP_CEILING) { cap = RING_CAP_CEILING; b.ceiling_binds = true; }
    if (b.half_avail_bytes < cap) { cap = b.half_avail_bytes; b.availability_binds = true; }
    if (cap < RING_CAP_FLOOR) { cap = RING_CAP_FLOOR; b.floor_applied = true; }
    b.cap_bytes = cap;
    return b;
}

RingBudget query_ring_budget()
{
    MEMORYSTATUSEX ms;
    memset(&ms, 0, sizeof(ms));
    ms.dwLength = sizeof(ms);
    const bool ok = (GlobalMemoryStatusEx(&ms) != 0);
    return ring_budget_from((uint64_t)ms.ullTotalPhys, (uint64_t)ms.ullAvailPhys, ok);
}

uint64_t ring_budget_cap_bytes() { return query_ring_budget().cap_bytes; }

size_t ring_apply_budget(size_t requested_bytes, const RingBudget& b)
{
    uint64_t cap = b.cap_bytes ? b.cap_bytes : ring_budget_cap_bytes();
    return requested_bytes > cap ? (size_t)cap : requested_bytes;
}

bool RingBuffer::init(size_t capacity_bytes, std::string* err)
{
    if (capacity_bytes < (16u << 20)) {
        *err = "ring capacity below 16 MiB — that cannot hold a cuttable window";
        return false;
    }

    // Price the request against the pool the arena is ACTUALLY allocated from, and say so.
    budget_ = query_ring_budget();
    size_t asked = capacity_bytes;
    capacity_bytes = ring_apply_budget(capacity_bytes, budget_);
    clamped_from_ = (capacity_bytes < (size_t)asked) ? (uint64_t)asked : 0;

    log_line("  RING BUDGET: %llu MiB physical RAM (%llu MiB available)%s -> 25%% = %llu MiB, "
             "50%% of available = %llu MiB -> cap %llu MiB (ceiling %s, availability %s, floor %s)",
             (unsigned long long)(budget_.total_physical_bytes >> 20),
             (unsigned long long)(budget_.avail_physical_bytes >> 20),
             budget_.query_ok ? "" : "  [QUERY FAILED]",
             (unsigned long long)(budget_.quarter_bytes >> 20),
             (unsigned long long)(budget_.half_avail_bytes >> 20),
             (unsigned long long)(budget_.cap_bytes >> 20),
             budget_.ceiling_binds ? "BINDS" : "free",
             budget_.availability_binds ? "BINDS" : "free",
             budget_.floor_applied ? "APPLIED" : "free");
    log_line("  RING ARENA: asked %llu MiB, holding %llu MiB of SYSTEM RAM%s",
             (unsigned long long)(asked >> 20),
             (unsigned long long)(capacity_bytes >> 20),
             clamped_from_ ? "  [CLAMPED to the system-RAM budget]" : "");

    // F2: std::vector::assign either succeeds or THROWS — it never returns short, so the
    // old `if (arena_.size() != capacity_bytes)` was dead code and a real failure escaped
    // init() into std::terminate (this file had no `catch` at all).  A 4 GiB budget makes
    // that reachable on a machine that cannot honour it, so the failure is CAUGHT and
    // REPORTED.  There is no catch (...) here on purpose: an unknown exception is a bug and
    // should keep its stack, not become a one-line error string.
    try {
        arena_.assign(capacity_bytes, 0);
    } catch (const std::bad_alloc&) {
        arena_.clear();
        *err = "could not commit the " + std::to_string(capacity_bytes >> 20) +
               " MiB ring arena (budget allowed " + std::to_string(budget_.cap_bytes >> 20) +
               " MiB; " + std::to_string(budget_.avail_physical_bytes >> 20) +
               " MiB of RAM was available)";
        return false;
    } catch (const std::length_error& le) {
        arena_.clear();
        *err = std::string("the ring arena size is out of range: ") + le.what();
        return false;
    }
    if (arena_.size() != capacity_bytes) { *err = "the ring arena came back short"; return false; }
    cap_ = capacity_bytes;
    entries_.reserve(1 << 16);

    // capacity() — the number a reader compares against, printed so a log line and the
    // committed arena can never disagree without the log showing it (this is what made the
    // reviewer's F6 check measurable at all).
    log_line("  RING ARENA COMMITTED: capacity() = %llu MiB (%zu bytes)%s",
             (unsigned long long)(capacity() >> 20), capacity(),
             clamped_from_ ? "  [request was over budget]" : "");
    return true;
}

bool RingBuffer::idr_count_at_least_two_locked() const { return idr_live_ >= 2; }

void RingBuffer::evict_front_locked()
{
    const RingEntry& e = entries_[first_];
    used_ -= e.size;
    if (e.is_idr) --idr_live_;
    ++first_;
    ++evictions_;
    // Compact occasionally so the index does not grow without bound; the vector stays
    // ordered, so lower_bound keeps working after the erase.
    if (first_ > 4096 && first_ * 2 > entries_.size()) {
        entries_.erase(entries_.begin(), entries_.begin() + (ptrdiff_t)first_);
        first_ = 0;
    }
}

bool RingBuffer::append(const uint8_t* data, size_t size, bool is_idr, int picture_type,
                        uint64_t qpc_ns, uint64_t seq)
{
    if (!data || size == 0) return false;
    std::lock_guard<std::mutex> lk(mu_);

    if (size > cap_) { ++dropped_; return false; }   // a single frame larger than the ring

    // Make room.  Refuse to evict anything the cut has pinned, and refuse to evict the
    // LAST IDR still held: a ring with no IDR cannot produce a decodable clip, so losing
    // a frame is strictly better than losing the window (and it is counted).
    while (used_ + size > cap_) {
        if (first_ >= entries_.size()) break;
        const RingEntry& front = entries_[first_];
        if (pinned_ && front.abs_off >= pin_abs_) { ++dropped_; return false; }
        if (front.is_idr && idr_live_ <= 1)        { ++dropped_; return false; }
        evict_front_locked();
    }

    size_t off = (size_t)(head_abs_ % cap_);
    size_t n1 = size;
    if (off + n1 > cap_) n1 = cap_ - off;
    memcpy(arena_.data() + off, data, n1);
    if (n1 < size) memcpy(arena_.data(), data + n1, size - n1);

    RingEntry e;
    e.abs_off = head_abs_;
    e.qpc_ns = qpc_ns;
    e.seq = seq;
    e.size = (uint32_t)size;
    e.is_idr = is_idr;
    e.picture_type = picture_type;
    entries_.push_back(e);

    head_abs_ += size;
    used_ += size;
    if (is_idr) ++idr_live_;
    return true;
}

void RingBuffer::pin(uint64_t first_abs)
{
    std::lock_guard<std::mutex> lk(mu_);
    pinned_ = true;
    pin_abs_ = first_abs;
}

void RingBuffer::unpin()
{
    std::lock_guard<std::mutex> lk(mu_);
    pinned_ = false;
}

size_t RingBuffer::count() const
{
    std::lock_guard<std::mutex> lk(mu_);
    return entries_.size() - first_;
}

bool RingBuffer::entry_at(size_t i, RingEntry* out) const
{
    std::lock_guard<std::mutex> lk(mu_);
    if (first_ + i >= entries_.size()) return false;
    *out = entries_[first_ + i];
    return true;
}

bool RingBuffer::entry_by_abs(uint64_t abs_off, RingEntry* out) const
{
    std::lock_guard<std::mutex> lk(mu_);
    if (first_ >= entries_.size()) return false;
    RingEntry key;
    key.abs_off = abs_off;
    auto b = std::lower_bound(entries_.begin() + (ptrdiff_t)first_, entries_.end(), key,
                              [](const RingEntry& a, const RingEntry& k) { return a.abs_off < k.abs_off; });
    if (b == entries_.end() || b->abs_off != abs_off) return false;
    *out = *b;
    return true;
}

bool RingBuffer::read_entry(const RingEntry& e, std::vector<uint8_t>& out) const
{
    std::lock_guard<std::mutex> lk(mu_);
    if (e.size == 0 || e.size > cap_) return false;
    out.resize(e.size);
    size_t off = (size_t)(e.abs_off % cap_);
    size_t n1 = e.size;
    if (off + n1 > cap_) n1 = cap_ - off;
    memcpy(out.data(), arena_.data() + off, n1);
    if (n1 < e.size) memcpy(out.data() + n1, arena_.data(), e.size - n1);
    return true;
}

uint64_t RingBuffer::newest_abs() const
{
    std::lock_guard<std::mutex> lk(mu_);
    return head_abs_;
}

uint64_t RingBuffer::oldest_abs() const
{
    std::lock_guard<std::mutex> lk(mu_);
    if (first_ >= entries_.size()) return head_abs_;
    return entries_[first_].abs_off;
}

size_t RingBuffer::bytes_used() const
{
    std::lock_guard<std::mutex> lk(mu_);
    return used_;
}

bool RingBuffer::find_cut_base(uint64_t t_cut_ns, uint64_t window_ns, size_t* index) const
{
    std::lock_guard<std::mutex> lk(mu_);
    if (first_ >= entries_.size()) return false;
    uint64_t target = (t_cut_ns > window_ns) ? (t_cut_ns - window_ns) : 0;
    for (size_t i = first_; i < entries_.size(); ++i) {
        if (entries_[i].is_idr && entries_[i].qpc_ns >= target) { *index = i - first_; return true; }
    }
    return false;
}

bool RingBuffer::find_oldest_idr(size_t* index) const
{
    std::lock_guard<std::mutex> lk(mu_);
    for (size_t i = first_; i < entries_.size(); ++i) {
        if (entries_[i].is_idr) { *index = i - first_; return true; }
    }
    return false;
}



// ------------------------------------------------------------------ AudioRing
// One qpc clock, two rings: copy_window() selects the exact frames that share the video
// cut window, so an instant-replay cut taken NOW carries the SOUND of the last N seconds.
//
// Time model: absolute frame index a maps to qpc through a single anchor -- the newest
// sample ever pushed ends at (head_abs_, head_qpc_ns_).  Because a gap is filled with
// SILENCE rather than skipped, that mapping holds for real and synthesised samples alike,
// which is the whole point: the sound stays aligned to the video.

bool AudioRing::init(double seconds, std::string* err)
{
    std::lock_guard<std::mutex> g(mu_);
    if (cap_frames_) { *err = "AudioRing::init() called twice"; return false; }
    if (!(seconds > 0.5) || seconds > 3600.0) {
        *err = "audio ring seconds must be in (0.5, 3600]";
        return false;
    }
    requested_seconds_ = seconds;

    // Priced from MEASURED resident RAM (GlobalMemoryStatusEx via query_ring_budget), never
    // from VRAM: nvidia-smi is unusable on this host and the audio arena is SYSTEM heap.
    budget_ = query_ring_budget();
    const uint64_t want = ring_apply_budget((uint64_t)((double)seconds * audio::kAsrSampleRate
                                                        * audio::kAsrChannels
                                                        * audio::kAsrSampleWidth),
                                            budget_);
    clamped_from_ = want;
    uint64_t want_frames = want / audio::kAsrChannels;
    if (want_frames < (uint64_t)audio::kAsrSampleRate / 2) {
        *err = "audio ring budget left less than half a second of audio";
        return false;
    }
    try {
        arena_.assign((size_t)want_frames, (int16_t)0);
    } catch (const std::bad_alloc&) {
        *err = "audio ring arena allocation failed (bad_alloc)";
        return false;
    } catch (const std::length_error&) {
        *err = "audio ring arena allocation failed (length_error)";
        return false;
    }
    cap_frames_ = want_frames;
    return true;
}

void AudioRing::shutdown()
{
    std::lock_guard<std::mutex> g(mu_);
    arena_.clear();
    arena_.shrink_to_fit();
    cap_frames_ = 0;
    used_ = first_ = 0;
    head_abs_ = head_qpc_ns_ = 0;
    have_stamp_ = false;
    pushed_ = dropped_ = silence_filled_ = 0;
}

void AudioRing::evict_front_locked()
{
    // Evict in whole seconds so the drop is always a multiple of the frame size.
    uint64_t drop = (uint64_t)audio::kAsrSampleRate;
    if (drop > used_) drop = used_;
    first_ = (first_ + (size_t)drop) % (size_t)cap_frames_;
    used_ -= drop;
    dropped_ += drop;
}

bool AudioRing::push(const int16_t* pcm, uint32_t frames, uint64_t qpc_ns)
{
    std::lock_guard<std::mutex> g(mu_);
    if (!cap_frames_) return false;

    if (!have_stamp_) {
        head_qpc_ns_ = qpc_ns;
        have_stamp_ = true;
    } else if (qpc_ns > head_qpc_ns_) {
        const uint64_t span_ns = qpc_ns - head_qpc_ns_;
        uint64_t span_frames = (uint64_t)((long double)span_ns * audio::kAsrSampleRate
                                          / 1000000000.0L);
        if (span_frames > frames) {
            uint64_t gap = span_frames - frames;
            if (gap > cap_frames_) gap = cap_frames_;   // never synthesise more than we hold
            size_t w = (size_t)(head_abs_ % cap_frames_);
            for (uint64_t i = 0; i < gap; ++i, w = (w + 1) % (size_t)cap_frames_) arena_[w] = 0;
            head_abs_ += gap;
            silence_filled_ += gap;
            used_ += gap;
            while (used_ > cap_frames_) evict_front_locked();
        }
    } else {
        head_qpc_ns_ = qpc_ns;   // a backwards stamp is a clock anomaly: re-stamp
    }

    if (frames) {
        size_t w = (size_t)(head_abs_ % cap_frames_);
        for (uint32_t i = 0; i < frames; ++i, w = (w + 1) % (size_t)cap_frames_)
            arena_[w] = pcm[i];
        head_abs_ += frames;
        used_ += frames;
        while (used_ > cap_frames_) evict_front_locked();
        pushed_ += frames;
    }
    head_qpc_ns_ = qpc_ns;
    return true;
}

bool AudioRing::copy_window(uint64_t from_qpc_ns, uint64_t to_qpc_ns,
                            std::vector<int16_t>* out, uint64_t* out_first_qpc_ns,
                            uint64_t* silence_frames_filled, bool* head_clamped,
                            std::string* err) const
{
    std::lock_guard<std::mutex> g(mu_);
    if (out_first_qpc_ns) *out_first_qpc_ns = 0;
    if (silence_frames_filled) *silence_frames_filled = 0;
    if (head_clamped) *head_clamped = false;
    out->clear();
    if (!cap_frames_) { *err = "audio ring was never initialised"; return false; }
    if (used_ == 0) { *err = "audio ring holds no samples; the clip would carry silence"; return false; }

    // The newest sample ends at (head_abs_, head_qpc_ns_); sample a sits head_qpc_ns_ minus
    // (head_abs_ - a) frames of time.
    const uint64_t ns_per_frame = (uint64_t)(1000000000.0L / (long double)audio::kAsrSampleRate);
    auto abs_of = [&](uint64_t q) -> long long {
        if (q >= head_qpc_ns_) return (long long)head_abs_;
        uint64_t back = head_qpc_ns_ - q;
        uint64_t f = back / ns_per_frame;
        return (long long)head_abs_ - (long long)f;
    };
    auto qpc_of = [&](uint64_t a) -> uint64_t {
        if (a >= head_abs_) return head_qpc_ns_;
        uint64_t back = (head_abs_ - a) * ns_per_frame;
        return head_qpc_ns_ > back ? head_qpc_ns_ - back : 0;
    };

    const uint64_t oldest_abs = head_abs_ - used_;
    long long a0 = abs_of(from_qpc_ns);
    long long a1 = abs_of(to_qpc_ns);
    if (a0 < (long long)oldest_abs) { a0 = (long long)oldest_abs; if (head_clamped) *head_clamped = true; }
    if (a1 > (long long)head_abs_)   { a1 = (long long)head_abs_;   if (head_clamped) *head_clamped = true; }
    if (a1 <= a0) {
        if (out_first_qpc_ns) *out_first_qpc_ns = qpc_of((uint64_t)a0);
        return true;                     // empty window: the caller pads to the video duration
    }

    const uint64_t n = (uint64_t)(a1 - a0);
    out->resize((size_t)n);
    size_t w = (size_t)((uint64_t)a0 % cap_frames_);
    uint64_t zeros = 0;
    for (uint64_t i = 0; i < n; ++i, w = (w + 1) % (size_t)cap_frames_) {
        (*out)[(size_t)i] = arena_[w];
        if (arena_[w] == 0) ++zeros;
    }
    if (out_first_qpc_ns) *out_first_qpc_ns = qpc_of((uint64_t)a0);
    if (silence_frames_filled) *silence_frames_filled = zeros;
    return true;
}

uint64_t AudioRing::bytes_used() const
{
    std::lock_guard<std::mutex> g(mu_);
    return used_ * audio::kAsrChannels * audio::kAsrSampleWidth;
}

bool AudioRing::empty() const
{
    std::lock_guard<std::mutex> g(mu_);
    return used_ == 0;
}

uint64_t AudioRing::frames_pushed() const
{
    std::lock_guard<std::mutex> g(mu_);
    return pushed_;
}

double AudioRing::seconds_held() const
{
    std::lock_guard<std::mutex> g(mu_);
    return cap_frames_ ? (double)cap_frames_ / audio::kAsrSampleRate : 0.0;
}

} // namespace aireplay
