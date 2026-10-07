#include "ring_buffer.h"

#include <algorithm>

namespace aireplay {

RingBuffer::~RingBuffer() {}

bool RingBuffer::init(size_t capacity_bytes, std::string* err)
{
    if (capacity_bytes < (16u << 20)) {
        *err = "ring capacity below 16 MiB ÔÇö that cannot hold a cuttable window";
        return false;
    }
    arena_.assign(capacity_bytes, 0);
    if (arena_.size() != capacity_bytes) { *err = "could not allocate the ring arena"; return false; }
    cap_ = capacity_bytes;
    entries_.reserve(1 << 16);
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

} // namespace aireplay
