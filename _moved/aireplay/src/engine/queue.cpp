#include "queue.h"

#include <cstring>

namespace sotto {

// The three ENGINE_SELFTEST_* mutations below are DELIBERATE DEFECTS, compiled
// only into the control binaries named in docs/design-notes/03-engine-ipc.md
// section 5. They live HERE, in the mechanism, and not in the test, because an
// arm that only lies in its own assertions proves nothing about the code.

bool LineWriter::write_line(const std::string& line) {
  std::lock_guard<std::mutex> lock(mu_);
  if (f_ == nullptr) return false;
  size_t n = line.size();
  if (n > 0 && line[n - 1] == '\n') --n;  // exactly one terminator, always
  if (n > 0 && std::fwrite(line.data(), 1, n, f_) != n) return false;
  if (std::fputc('\n', f_) == EOF) return false;
  if (std::fflush(f_) != 0) return false;
  return true;
}

void LineReader::feed(const char* data, size_t n) {
  if (data != nullptr && n > 0) buf_.append(data, n);
}

bool LineReader::pop(std::string* out) {
  if (has_pending_) {
    *out = pending_;
    has_pending_ = false;
    return true;
  }
  size_t nl = buf_.find('\n');
  if (nl == std::string::npos) return false;  // no terminator yet
  *out = buf_.substr(0, nl);
  buf_.erase(0, nl + 1);
  return true;
}

bool LineReader::finish() {
  while (!buf_.empty()) {
    size_t nl = buf_.find('\n');
    if (nl != std::string::npos) {
      pending_ = buf_.substr(0, nl);  // a COMPLETE line: hand it over honestly
      buf_.erase(0, nl + 1);
      has_pending_ = true;
      return true;
    }
#ifdef ENGINE_SELFTEST_LENIENT_READER
    // THE DELIBERATE BUG (ARM-B control): the truncated tail is published as
    // if it were a whole message. A fabricated event, and exactly what the
    // reader must never do.
    pending_ = buf_;
    buf_.clear();
    has_pending_ = true;
    return true;
#else
    // The tail has no terminator: the peer died mid-record. Count it and drop
    // it. NOT repaired -- a repair would invent a message that never happened.
    ++rejected_truncated_;
    buf_.clear();
    return false;
#endif
  }
  return false;
}

bool Queue::push(std::string line) {
  std::lock_guard<std::mutex> lock(mu_);
#ifdef ENGINE_SELFTEST_UNBOUNDED_QUEUE
  (void)bound_;  // THE DELIBERATE BUG (ARM-A control): no bound at all.
  q_.push_back(std::move(line));
  if (q_.size() > high_water_) high_water_ = q_.size();
  return true;
#else
#ifdef ENGINE_SELFTEST_NO_DROP_COUNTER
  // THE DELIBERATE BUG (ARM-C control): the drop still happens, but it is
  // SILENT -- the counter never moves. The worst of both worlds.
  if (bound_ != kUnbounded && q_.size() >= bound_) return false;
  q_.push_back(std::move(line));
  if (q_.size() > high_water_) high_water_ = q_.size();
  return true;
#else
  if (bound_ != kUnbounded && q_.size() >= bound_) {
    ++dropped_;  // the drop IS the counter (law 1)
    return false;
  }
  q_.push_back(std::move(line));
  if (q_.size() > high_water_) high_water_ = q_.size();
  return true;
#endif
#endif
}

bool Queue::pop(std::string* out) {
  std::lock_guard<std::mutex> lock(mu_);
  if (head_ >= q_.size()) return false;
  *out = std::move(q_[head_]);
  ++head_;
  if (head_ > 4096 && head_ * 2 >= q_.size()) {
    q_.erase(q_.begin(), q_.begin() + static_cast<long>(head_));
    head_ = 0;
  }
  return true;
}

size_t Queue::dropped() const {
  std::lock_guard<std::mutex> lock(mu_);
  return dropped_;
}

size_t Queue::size() const {
  std::lock_guard<std::mutex> lock(mu_);
  return q_.size() - head_;
}

}  // namespace sotto