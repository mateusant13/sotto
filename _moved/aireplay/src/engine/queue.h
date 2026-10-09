// Sotto Engine -- the three mechanisms the IPC needs, each for a stated law.
//
// Law 1: CAPTURE NEVER WAITS FOR AI. The queue never blocks its producer, and
// every drop increments a counter that is published in the Engine's health
// event -- so a drop is never silent.
#pragma once
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

namespace sotto {

// A writer that cannot interleave partial lines from two threads.
//
// The mutex covers the WHOLE record (fwrite + '\n' + fflush), not a field or a
// buffer. Coarse on purpose: a partial-line interleave makes the UI show an
// event that never happened, and the flush must be serialised anyway.
class LineWriter {
 public:
  explicit LineWriter(std::FILE* f) : f_(f) {}
  // Takes the line WITHOUT its newline and adds exactly one. Returns false if
  // the underlying write failed; nothing is retried and nothing is swallowed.
  bool write_line(const std::string& line);

 private:
  std::FILE* f_;
  std::mutex mu_;
};

// A reader that tolerates a truncated last line.
//
// A line is only delivered once its '\n' has arrived. finish() is EOF: a
// non-empty tail means the peer died mid-record, so it is REJECTED and counted,
// never delivered. It is deliberately not repaired -- a repaired line would be
// a fabricated message, and law 2 says the clip is already written; we do not
// invent evidence.
class LineReader {
 public:
  void feed(const char* data, size_t n);
  void feed(const std::string& s) { feed(s.data(), s.size()); }
  // Returns a complete line without its '\n'. False when none is buffered.
  bool pop(std::string* out);
  // EOF. Returns false and counts a rejection if the tail is non-empty.
  bool finish();
  long long rejected_truncated() const { return rejected_truncated_; }

 private:
  std::string buf_;
  std::string pending_;
  bool has_pending_ = false;
  long long rejected_truncated_ = 0;
};

// A bounded queue that drops WITH A COUNTER (law 1).
//
// push() takes a mutex and never waits on a condition variable: the producer
// is never blocked, so a message storm on the AI side cannot cost a capture
// frame. If the queue is full the push fails and dropped() goes up -- the drop
// IS the counter.
class Queue {
 public:
  // bound == kUnbounded makes an unbounded queue. That variant exists ONLY so
  // ARM-A can prove the bounded check can say NO; it is never a product config.
  static const size_t kUnbounded = static_cast<size_t>(-1);
  explicit Queue(size_t bound) : bound_(bound) {}

  bool push(std::string line);          // false == dropped
  bool pop(std::string* out);           // false == empty
  size_t dropped() const;
  size_t size() const;
  size_t bound() const { return bound_; }
  // High-water mark: how full this queue ever actually got. A healthy Engine
  // should keep this far below the bound.
  size_t high_water() const { return high_water_; }

 private:
  mutable std::mutex mu_;
  std::vector<std::string> q_;
  size_t bound_;
  size_t head_ = 0;
  size_t dropped_ = 0;
  size_t high_water_ = 0;
};

}  // namespace sotto