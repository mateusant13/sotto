// Sotto Engine -- hand-rolled JSON for the FIXED envelope.
//
// NOT a conformant JSON library. There is no JSON library on this box and
// nothing was downloaded. What that forbids is written down in
// docs/design-notes/03-engine-ipc.md section 3:
//   * arbitrary user input (payloads are machine-generated only)
//   * floating point (use scaled ints, e.g. score_milli)
//   * \uXXXX escapes (UTF-8 passes through raw, like the production
//     json.dumps(..., ensure_ascii=False) at sotto_worker.py:376)
//   * a string containing any byte < 0x20 -- REJECTED and counted, because an
//     unescaped newline would split one message into two
//   * arbitrary nesting: the reader keeps `payload` as raw bytes
#pragma once
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace sotto {

// Builds one flat JSON object. Values are stored ALREADY ENCODED, in insertion
// order, so the writer never has to re-escape anything it did not write itself.
class JsonObj {
 public:
  // Each of these returns false and latches ok_=false if the value cannot be
  // encoded (currently: a control byte in a string). Nothing is silently
  // mangled into a valid-looking value.
  bool str(const char* key, const std::string& v);
  bool i64(const char* key, long long v);
  bool b(const char* key, bool v);
  void put_obj(const char* key, const JsonObj& nested);  // nested, not string

  const std::vector<std::pair<std::string, std::string>>& fields() const {
    return f_;
  }
  bool ok() const { return ok_; }
  // "{...}" or "{}" when empty.
  std::string encode() const;

  // Find a raw value by key. Returns false if absent.
  bool get(const char* key, std::string* out) const;

  // Escapes a string value, or returns false if it holds a byte < 0x20.
  static bool encode_string(const std::string& in, std::string* out);

 private:
  std::vector<std::pair<std::string, std::string>> f_;
  bool ok_ = true;
};

// One message of the wire protocol. See the envelope table in the design note.
struct Msg {
  long long v = 1;
  std::string type;
  long long id = 0;
  long long ts = 0;
  JsonObj payload;

  // Serialises WITHOUT the trailing '\n'; the LineWriter adds it atomically.
  std::string to_json() const;
  // The full wire form, '\n' included.
  std::string to_line() const;

  // Parses one complete line. Returns false and sets *err for: a truncated or
  // over-long line, a missing envelope field, v != 1, a non-integer id/ts/v, a
  // payload that is not an object, or a control byte anywhere. It NEVER
  // returns a partially populated Msg -- a repair would be a fabricated event.
  static bool parse(const std::string& line, Msg* out, std::string* err);
};

}  // namespace sotto