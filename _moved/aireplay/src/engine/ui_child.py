"""ui_child.py -- the GATE-SIDE UI client for THE ENGINE PROCESS.

The gate needs a SECOND process to attach, detach and reattach to a live Engine
and to report, in one JSON line, what it saw.  Two defects were measured in
THIS file on 2026-10-09 and both are fixed here, because they cost ARM-B and
ARM-C a whole run each while the Engine was correct.

DEFECT 1 -- THE READER LOST EVERY LIVE EVENT.  The reader was a buffered file
object over the socket (socket.makefile) read with readline() under a socket
timeout.  Measured (repro5: three readers attached to ONE live Engine for 10 s):

    A-makefile-1s   -> {"hello": 1, "replay": 1, "health": 1}                     lost all clips
    B-raw-1s        -> {"hello": 1, "replay": 1, "health": 11, "clip_written": 10}
    C-makefile-50ms -> {"hello": 1, "replay": 1, "health": 1}                     lost all clips

The buffered reader and the socket timeout disagree after the FIRST timeout and
every later envelope is dropped.  The Engine meanwhile delivered all of them
(its own diag logged the attach of all three readers, and the raw reader held
ids 2..12 with no hole).

THE READER IS NOW A RAW recv() WITH ITS OWN LINE BUFFER.  That is the fix that
carries ARM-C: capture cadence is measured from live clip_written events, and
with the old reader the interval list was empty, so the arm failed a
"0 < interval < 2500 ms" check on a perfectly healthy Engine.

DEFECT 2 -- id ACCOUNTING COUNTED EVENTS THAT HAVE NO id.  Only RING-BORNE
events carry the monotonic since_id cursor and are retained for replay; hello,
replay, health, status, detach, cut_ack, search and bye carry id 0 and are
never retained.  Counting them produced 6 duplicate ids and 8 phantom holes in
ARM-B and put 0 into the reconnect cursor, so the reconnecting UI asked for
"since 0" and was answered with the whole earliest retained window instead of
the true continuation point.

Only RING_TYPES is counted now, and the reconnect cursor is the last RING id
the client actually saw.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time

NL = chr(10)
NLB = NL.encode("ascii")
CRB = chr(13).encode("ascii")

RING_TYPES = frozenset(["capture_started", "clip_written", "asr_partial",
                       "asr_final", "index_updated", "error"])


def now_ms():
    return int(time.time() * 1000)


def env(type_, payload=None, id_=0):
    return {"v": 1, "type": type_, "id": int(id_), "ts": now_ms(),
            "payload": dict(payload or {})}


class UiClient(object):
    """One UI connection.  Raw recv reader, no buffered file object."""

    def __init__(self, host, port, since, log_fh, label):
        self.host = host
        self.port = int(port)
        self.since = int(since)
        self.log = log_fh
        self.label = label
        self.sock = None
        self.buf = b""
        self.events = []
        self.ring_ids = []
        self.replay = None
        self.replay_env = None
        self.replay_latency_ms = None
        self.attach_ms = 0
        self.eof = False

    # ---------------------------------------------------------------- wire
    def connect(self, timeout=15.0):
        t0 = now_ms()
        last = None
        while now_ms() - t0 < timeout * 1000:
            try:
                self.sock = socket.create_connection((self.host, self.port),
                                                     timeout=5.0)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.buf = b""
                return now_ms() - t0
            except OSError as exc:
                last = exc
                time.sleep(0.1)
        raise RuntimeError("cannot connect %s:%s: %s" % (self.host, self.port, last))

    def send(self, type_, payload=None):
        line = json.dumps(env(type_, payload), separators=(",", ":"))
        self.sock.sendall((line + NL).encode("utf-8"))

    def attach(self):
        self.attach_ms = now_ms()
        self.send("attach", {"since": self.since})

    def detach(self):
        self.send("detach", {})

    def close(self):
        try:
            if self.sock is not None:
                self.sock.close()
        except OSError:
            pass
        self.sock = None

    # ---------------------------------------------------------------- read
    def _lines(self, timeout):
        """Complete lines read with a RAW recv, or nothing on timeout.

        NOT a buffered file object -- see DEFECT 1 in the module docstring.
        """
        if self.sock is None:
            raise EOFError
        self.sock.settimeout(max(0.05, timeout))
        try:
            chunk = self.sock.recv(65536)
        except (socket.timeout, OSError):
            return None
        if not chunk:
            self.eof = True
            raise EOFError
        self.buf += chunk
        out = []
        while True:
            i = self.buf.find(NLB)
            if i < 0:
                break
            raw = self.buf[:i]
            self.buf = self.buf[i + 1:]
            if raw.endswith(CRB):
                raw = raw[:-1]
            if raw:
                out.append(raw)
        return out

    def _handle(self, raw, stop_on_ready):
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            return False
        try:
            e = json.loads(line)
        except ValueError:
            return False
        if not isinstance(e, dict):
            return False
        if self.log:
            try:
                self.log.write(line + NL)
            except OSError:
                pass
        t = e.get("type")
        p = e.get("payload")
        if not isinstance(p, dict):
            p = {}
        if t == "health" and bool(p.get("ui_ready")):
            self.replay = dict(p)
            if self.replay_latency_ms is None:
                self.replay_latency_ms = now_ms() - self.attach_ms
            return stop_on_ready
        if t == "replay":
            self.replay_env = dict(p)
            # The replayed events ARE ring events this client received: they
            # arrive NESTED inside the replay envelope, so counting only
            # top-level envelopes leaves a phantom hole in the id sequence.
            for ev in p.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                if ev.get("type") not in RING_TYPES:
                    continue
                j = ev.get("id")
                if isinstance(j, int) and j > 0:
                    self.ring_ids.append(j)
        self.events.append(e)
        if t in RING_TYPES:
            i = e.get("id")
            if isinstance(i, int) and i > 0:
                self.ring_ids.append(i)
        return False

    def pump(self, deadline_s, stop_on_ready=False, poll=0.5):
        """Read until the deadline, or until the attach handshake completes."""
        while True:
            left = deadline_s - time.time()
            if left <= 0:
                return
            try:
                raw_lines = self._lines(min(poll, left))
            except EOFError:
                return
            if not raw_lines:
                continue
            for raw in raw_lines:
                if self._handle(raw, stop_on_ready):
                    return


def main(argv=None):
    ap = argparse.ArgumentParser(description="gate-side UI client for the Engine")
    ap.add_argument("--portfile", required=True)
    ap.add_argument("--since", type=int, default=0)
    ap.add_argument("--attach-timeout", type=float, default=15.0)
    ap.add_argument("--hold", type=float, default=4.0,
                    help="seconds to read after the attach handshake")
    ap.add_argument("--detach-after", type=float, default=0.0,
                    help="send detach + close after N seconds (0 = stay attached)")
    ap.add_argument("--detach-gap", type=float, default=1.5,
                    help="seconds between the detach close and the reconnect; "
                         "must exceed one cut cadence so the reconnecting UI "
                         "has a window to replay")
    ap.add_argument("--reattach-hold", type=float, default=3.0)
    ap.add_argument("--log", default="")
    ap.add_argument("--label", default="ui")
    a = ap.parse_args(argv)

    port = None
    t0 = time.time()
    while port is None:
        try:
            with open(a.portfile, "r", encoding="utf-8") as f:
                port = json.load(f).get("port")
        except (OSError, ValueError):
            port = None
        if port is None:
            if time.time() - t0 > a.attach_timeout:
                sys.stderr.write("UI-CHILD-FAIL no portfile %s after %.1fs%s"
                                 % (a.portfile, a.attach_timeout, NL))
                return 2
            time.sleep(0.1)

    log_fh = open(a.log, "a", encoding="utf-8") if a.log else None
    c = UiClient("127.0.0.1", port, a.since, log_fh, a.label)
    c.connect(timeout=a.attach_timeout)
    c.attach()
    c.pump(time.time() + a.hold, stop_on_ready=True)
    first_replay = dict(c.replay or {})
    first_latency = c.replay_latency_ms
    first_replay_env = dict(c.replay_env or {})

    detach_ms = None
    reattach = None
    if a.detach_after > 0:
        c.pump(time.time() + a.detach_after)
        detach_ms = now_ms()
        c.detach()
        time.sleep(a.detach_gap)
        c.close()
        since = (c.ring_ids[-1] if c.ring_ids else a.since)
        r = UiClient("127.0.0.1", port, since, log_fh, a.label + "-reconnect")
        r.connect(timeout=a.attach_timeout)
        r.attach()
        r.pump(time.time() + a.reattach_hold, stop_on_ready=True)
        r.pump(time.time() + a.reattach_hold)
        reattach = {
            "since": since,
            "last_ring_id_before_detach": (c.ring_ids[-1] if c.ring_ids else None),
            "replay": dict(r.replay or {}),
            "replay_env": dict(r.replay_env or {}),
            "replay_latency_ms": r.replay_latency_ms,
            "detach_gap_ms": r.attach_ms - detach_ms,
            "events": len(r.events),
            "ring_ids": list(r.ring_ids),
        }
        r.close()
    else:
        c.pump(time.time() + a.hold)
        c.close()

    ids = list(c.ring_ids)
    if reattach:
        ids = ids + reattach["ring_ids"]
    gaps = []
    prev = None
    for i in ids:
        if prev is not None and i != prev + 1 and i != prev:
            gaps.append({"prev": prev, "next": i})
        prev = i
    dupes = len(ids) - len(set(ids))
    if reattach:
        ev_ids = [int(e.get("id", 0)) for e in reattach["replay_env"].get("events", [])
                  if e.get("type") in RING_TYPES]
        reattach["replayed_ids"] = ev_ids
        reattach["replay_size"] = len(ev_ids)
        reattach["replay_exact_range"] = bool(
            ev_ids and ev_ids == list(range(min(ev_ids), min(ev_ids) + len(ev_ids)))
            and min(ev_ids) == reattach["since"] + 1)
    out = {
        "port": port,
        "first_attach": {"since": a.since, "replay": first_replay,
                         "replay_env": first_replay_env,
                         "replay_latency_ms": first_latency,
                         "events_seen": len(c.events),
                         "ring_ids": list(c.ring_ids),
                         "max_ring_id": (c.ring_ids[-1] if c.ring_ids else a.since)},
        "reattach": reattach,
        "ids_all": ids,
        "ring_id_count": len(ids),
        "gap_count": len(gaps), "gaps": gaps[:10], "duplicate_count": dupes,
        "max_ring_id_seen": max(ids) if ids else 0,
        "types_seen": sorted({e.get("type") for e in c.events}),
    }
    print(json.dumps(out, separators=(",", ":")))
    if log_fh:
        log_fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
