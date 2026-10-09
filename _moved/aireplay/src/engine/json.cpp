#include "json.h"

#include <cstdio>

namespace sotto {
namespace {

bool is_control(unsigned char c) { return c < 0x20; }

// Strict integer: optional '-', then digits, and NOTHING else.
bool parse_i64(const std::string& s, long long* out) {
  if (s.empty()) return false;
  size_t i = 0;
  bool neg = false;
  if (s[0] == '-') { neg = true; i = 1; }
  if (i >= s.size()) return false;
  long long v = 0;
  for (; i < s.size(); ++i) {
    if (s[i] < '0' || s[i] > '9') return false;
    v = v * 10 + (s[i] - '0');
    if (v > 4611686018427387904LL) return false;  // overflow guard
  }
  *out = neg ? -v : v;
  return true;
}

// Reads "..." at s[i]. Advances i past the closing quote.
bool parse_key(const std::string& s, size_t* i, std::string* out) {
  if (*i >= s.size() || s[*i] != '"') return false;
  ++(*i);
  size_t start = *i;
  while (*i < s.size() && s[*i] != '"') {
    if (s[*i] == '\\') ++(*i);  // our keys are ASCII, but stay in step
    ++(*i);
  }
  if (*i >= s.size()) return false;  // truncated
  *out = s.substr(start, *i - start);
  ++(*i);
  return true;
}

// Scans one raw value starting at s[i]: a string, an object, an array, or a
// bare token. Stops at depth 0 on ',' or on the enclosing '}'. Returns the
// index where it stopped.
size_t scan_value(const std::string& s, size_t i, std::string* out) {
  size_t start = i;
  int depth = 0;
  bool in_str = false, esc = false;
  for (; i < s.size(); ++i) {
    char c = s[i];
    if (in_str) {
      if (esc) esc = false;
      else if (c == '\\') esc = true;
      else if (c == '"') in_str = false;
      continue;
    }
    if (c == '"') { in_str = true; }
    else if (c == '{' || c == '[') { ++depth; }
    else if (c == '}' || c == ']') {
      if (depth == 0) break;  // the enclosing object's own brace
      --depth;
    } else if (c == ',' && depth == 0) {
      break;
    }
  }
  *out = s.substr(start, i - start);
  return i;
}

// A truncated object: unbalanced braces, or a quote left open.
bool is_truncated(const std::string& s) {
  int depth = 0;
  bool in_str = false, esc = false;
  for (char c : s) {
    if (in_str) {
      if (esc) esc = false;
      else if (c == '\\') esc = true;
      else if (c == '"') in_str = false;
      continue;
    }
    if (c == '"') in_str = true;
    else if (c == '{' || c == '[') ++depth;
    else if (c == '}' || c == ']') --depth;
  }
  return in_str || depth != 0;
}

}  // namespace

bool JsonObj::encode_string(const std::string& in, std::string* out) {
  out->clear();
  out->push_back('"');
  for (unsigned char c : in) {
    if (is_control(c)) return false;  // framing, not cosmetics
    if (c == '"' || c == '\\') out->push_back('\\');
    out->push_back(static_cast<char>(c));
  }
  out->push_back('"');
  return true;
}

bool JsonObj::str(const char* key, const std::string& v) {
  std::string enc;
  if (!encode_string(v, &enc)) { ok_ = false; return false; }
  f_.emplace_back(key, enc);
  return true;
}

bool JsonObj::i64(const char* key, long long v) {
  char buf[32];
  std::snprintf(buf, sizeof buf, "%lld", v);
  f_.emplace_back(key, std::string(buf));
  return true;
}

bool JsonObj::b(const char* key, bool v) {
  f_.emplace_back(key, std::string(v ? "true" : "false"));
  return true;
}

void JsonObj::put_obj(const char* key, const JsonObj& nested) {
  if (!nested.ok()) { ok_ = false; return; }
  f_.emplace_back(key, nested.encode());
}

std::string JsonObj::encode() const {
  std::string out;
  out.push_back('{');
  bool first = true;
  for (const auto& kv : f_) {
    if (!first) out.push_back(',');
    first = false;
    std::string key;
    // Keys are ASCII literals from our own code.
    if (encode_string(kv.first, &key)) {
      out += key;
      out.push_back(':');
    } else {
      ok_ = false;
      continue;
    }
    out += kv.second;
  }
  out.push_back('}');
  return out;
}

bool JsonObj::get(const char* key, std::string* out) const {
  for (const auto& kv : f_) {
    if (kv.first == key) { *out = kv.second; return true; }
  }
  return false;
}

std::string Msg::to_json() const {
  JsonObj e;
  e.i64("v", v);
  e.str("type", type);
  e.i64("id", id);
  e.i64("ts", ts);
  e.put_obj("payload", payload);
  return e.encode();
}

std::string Msg::to_line() const { return to_json() + "\n"; }

bool Msg::parse(const std::string& line, Msg* out, std::string* err) {
  auto fail = [&](const char* m) { if (err) *err = m; return false; };

  for (unsigned char c : line) {
    if (is_control(c)) return fail("control byte");
  }
  size_t b = 0, e = line.size();
  while (b < e && (line[b] == ' ' || line[b] == '\t' || line[b] == '\r')) ++b;
  while (e > b && (line[e - 1] == ' ' || line[e - 1] == '\t' || line[e - 1] == '\r')) --e;
  if (b >= e) return fail("empty");
  if (line[b] != '{') return fail("not an object");
  if (line[e - 1] != '}') return fail("truncated: no closing brace");
  if (is_truncated(line.substr(b, e - b))) return fail("truncated");

  std::string body = line.substr(b, e - b);

  std::string sv, stype, sid, sts, spayload;
  bool have_v = false, have_type = false, have_id = false, have_ts = false,
       have_payload = false;
  size_t i = 1;
  for (;;) {
    while (i < body.size() && (body[i] == ' ' || body[i] == ',')) ++i;
    if (i < body.size() && body[i] == '}') { ++i; break; }
    std::string key;
    if (!parse_key(body, &i, &key)) return fail("truncated key");
    while (i < body.size() && body[i] == ' ') ++i;
    if (i >= body.size() || body[i] != ':') return fail("expected ':'");
    ++i;
    while (i < body.size() && body[i] == ' ') ++i;
    std::string raw;
    i = scan_value(body, i, &raw);
    if (key == "v") { sv = raw; have_v = true; }
    else if (key == "type") { stype = raw; have_type = true; }
    else if (key == "id") { sid = raw; have_id = true; }
    else if (key == "ts") { sts = raw; have_ts = true; }
    else if (key == "payload") { spayload = raw; have_payload = true; }
  }
  if (i != body.size()) return fail("trailing bytes");

  if (!have_v) return fail("missing v");
  if (!have_type) return fail("missing type");
  if (!have_id) return fail("missing id");
  if (!have_ts) return fail("missing ts");
  if (!have_payload) return fail("missing payload");

  Msg m;
  if (!parse_i64(sv, &m.v)) return fail("v is not an integer");
  if (m.v != 1) return fail("unsupported protocol version");
  if (!parse_i64(sid, &m.id)) return fail("id is not an integer");
  if (!parse_i64(sts, &m.ts)) return fail("ts is not an integer");

  if (stype.size() < 2 || stype.front() != '"' || stype.back() != '"') {
    return fail("type is not a string");
  }
  m.type = stype.substr(1, stype.size() - 2);
  if (m.type.empty()) return fail("empty type");

  if (spayload.empty() || spayload.front() != '{') {
    return fail("payload is not an object");
  }
  // The payload is kept as raw bytes and NOT walked -- see the design note.

  if (out) *out = m;
  return true;
}

}  // namespace sotto