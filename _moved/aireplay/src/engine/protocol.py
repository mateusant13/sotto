"""src/engine/protocol.py -- the Engine IPC envelope and its ONLY validator.

One JSON object per line, '\n' terminated, in BOTH directions (UI->Engine commands on
the UI's socket, Engine->UI events on the same socket; the capture child speaks the
same shape on stdin/stdout).  The envelope is

    {"v":1, "type":"<verb>", "id":<int>, "ts":<int ms>, "payload":{...}}

    v        protocol version -- must be the integer exactly 1 (not 1.0, not "1")
    type     a short verb: the command or event name, ^[a-z][a-z0-9_]*$
    id       per-emitter monotonic cursor, integer >= 0, GApless.  Events emitted by
             the Engine start at 1 and never skip: a reader that remembers the last
             id it saw can ask for everything after it.  id IS the replay cursor.
    ts       emitter wall clock in milliseconds since the epoch (int)
    payload  a JSON object, possibly empty

The rules mirror the C++ Msg::parse in src/engine/json.{h,cpp} (which rejects
control bytes, non-integer v/id/ts and v != 1) because both ends of the pipe must
agree on what a line is.  Anything this module refuses is never forwarded, never
partially applied, and never written to the protocol stream again.

STDIO IS NOT THE PROTOCOL.  stderr carries diagnostics only; the Engine's own stdout
is EMPTY by contract.  A diagnostic that happens to be valid JSON is still a
diagnostic -- see capture_child.py for the mixed-stdout rule.
"""

from __future__ import annotations

import json
import re
import time

V = 1                       # the one accepted version
TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MAX_LINE = 64 * 1024        # a line longer than this is a protocol error, not a payload

# Engine -> UI events (Engine is the producer; ids are gapless from 1).
EVENTS = (
    "hello", "replay", "capture_started", "clip_written", "asr_partial", "asr_final",
    "index_updated", "health", "error",
    # Engine -> UI answers to a command (they carry reply_to = the command id).
    "cut_ack", "status", "search", "detach", "bye",
)
# UI -> Engine commands.
COMMANDS = ("attach", "detach", "cut", "status", "search", "bye")


class ProtocolError(ValueError):
    """A line that is not a legal envelope.  Never re-emitted, never applied."""


def _pairs_hook(pairs):
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise ProtocolError("duplicate key %r" % (k,))
        seen.add(k)
    return dict(pairs)


def has_control_chars(s):
    return any(ord(c) < 0x20 for c in s)


def now_ms():
    return int(time.time() * 1000)


def _check_envelope(env, where):
    if not isinstance(env, dict):
        raise ProtocolError("%s: envelope is not an object" % where)
    for key in ("v", "type", "id", "ts", "payload"):
        if key not in env:
            raise ProtocolError("%s: missing key %r" % (where, key))
    v = env["v"]
    if isinstance(v, bool) or not isinstance(v, int):
        raise ProtocolError("%s: v must be an integer, got %r" % (where, v))
    if v != V:
        raise ProtocolError("%s: v must be exactly %d, got %d" % (where, V, v))
    t = env["type"]
    if not isinstance(t, str) or not TYPE_RE.match(t):
        raise ProtocolError("%s: bad type %r" % (where, t))
    i = env["id"]
    if isinstance(i, bool) or not isinstance(i, int):
        raise ProtocolError("%s: id must be an integer, got %r" % (where, i))
    if i < 0:
        raise ProtocolError("%s: id must be >= 0, got %d" % (where, i))
    ts = env["ts"]
    if isinstance(ts, bool) or not isinstance(ts, (int, float)):
        raise ProtocolError("%s: ts must be a number, got %r" % (where, ts))
    if ts < 0:
        raise ProtocolError("%s: ts must be >= 0, got %r" % (where, ts))
    p = env["payload"]
    if not isinstance(p, dict):
        raise ProtocolError("%s: payload must be an object, got %r" % (where, type(p).__name__))
    for k in p:
        if not isinstance(k, str) or has_control_chars(k):
            raise ProtocolError("%s: bad payload key %r" % (where, k))
    return env


def encode(env):
    """Envelope -> one '\n'-terminated line.  Validates first, always."""
    _check_envelope(env, "encode")
    return json.dumps(env, separators=(",", ":"), ensure_ascii=False, sort_keys=False) + "\n"


def parse_line(line, where="parse_line"):
    """Line (with or without its trailing '\n') -> validated envelope.

    Raises ProtocolError on anything that is not exactly a legal envelope.
    """
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    if not line:
        raise ProtocolError("%s: empty line" % where)
    if len(line) > MAX_LINE:
        raise ProtocolError("%s: line too long (%d > %d)" % (where, len(line), MAX_LINE))
    if has_control_chars(line):
        raise ProtocolError("%s: control character inside the line" % where)
    if line != line.strip():
        raise ProtocolError("%s: leading/trailing whitespace" % where)
    try:
        env = json.loads(line, object_pairs_hook=_pairs_hook)
    except ProtocolError:
        raise
    except Exception as e:                                   # json errors
        raise ProtocolError("%s: not JSON (%s)" % (where, e))
    return _check_envelope(env, where)


def make(type_, payload=None, id_=0, ts=None):
    """Build a valid envelope (the id/ts the caller passes are trusted here)."""
    return {"v": V, "type": type_, "id": int(id_),
            "ts": int(ts if ts is not None else now_ms()),
            "payload": dict(payload or {})}
