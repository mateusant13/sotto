"""src/engine/stub_capture.py -- a STUB capture child.  A STUB, NOT THE REAL THING.

WHAT THIS IS: a child process that speaks the REAL capture child's wire protocol --
stdin/stdout JSONL, one line in / one reply out, the SAME verbs ("ping", "cut") and
the SAME reply fields as src/capture/main.cpp's stdin_handle()/cut_finalise_and_reopen()
(main.cpp:1151-1159) -- and REAL clip FILES on disk (16 kHz mono WAV, finalised with a
correct header the instant a cut lands, so "the clip is already on disk when the key
was pressed" is measurable).  It also writes DIAGNOSTIC lines to stdout exactly the
way the real child does, so the engine's mixed-stdout parser is exercised for real.

WHY A STUB EXISTS AT ALL (measured, 2026-10-09, revision HEAD 399bc85): the REAL child
refuses to cut from ANY offline h264 file, today, with
    === CUT SESSION REFUSED: no SPS/PPS: avcC cannot be built ===
because SourceStream::load() captures sps/pps INSIDE the 'if (vcl)' block
(main.cpp:999-1004) and NAL types 7/8 (SPS/PPS) are not VCL -- so those two lines are
dead code and src.sps/src.pps are always empty.  That is a child-side bug this lane is
NOT allowed to fix (src/capture/* is read-only here) and the fix is one line: move the
two assignments out of the 'if (vcl)'.  The live path (--run) is unaffected because the
ring's IDR carries repeatSPSPPS.  The gate therefore measures that refusal against the
REAL binary (ARM-D's neighbour) and uses this stub for the ring/clip/UI/ASR arms.

WHAT A STUB ARM CANNOT CLAIM: that the C++ capture device works, that WGC works
(blocked here, E_ACCESSDENIED, lane D), or that NVENC encodes.  Those stay with the
real child, and this file never prints PASS for them.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import threading
import time


def log_line(fmt, *a):
    # The real child writes its log to STDOUT (measured); keep that mixed channel.
    sys.stdout.write((fmt % a if a else fmt) + "\n")
    sys.stdout.flush()


class WavClip(object):
    """A clip file being written RIGHT NOW, finalised on cut."""

    def __init__(self, path, sample_rate):
        self.path = path
        self.sample_rate = sample_rate
        self.frames = 0
        self.data_bytes = 0
        self.t0 = time.time()
        self.f = open(path, "wb")
        self.f.write(b"RIFF" + struct.pack("<I", 36) + b"WAVEfmt " +
                     struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16) +
                     b"data" + struct.pack("<I", 0))
        self.f.flush()

    def feed(self, chunk):
        self.f.write(chunk)
        self.data_bytes += len(chunk)
        self.frames += len(chunk) // 2

    def finalise(self):
        self.f.seek(4)
        self.f.write(struct.pack("<I", 36 + self.data_bytes))
        self.f.seek(40)
        self.f.write(struct.pack("<I", self.data_bytes))
        self.f.flush()
        os.fsync(self.f.fileno())
        self.f.close()
        return self.path


def tone_pcm(sample_rate, n, phase):
    """Deterministic, hermetically generated audio (no fixture file needed)."""
    out = bytearray()
    for i in range(n):
        t = (phase + i) / float(sample_rate)
        v = 0.35 * math.sin(2 * math.pi * 220.0 * t) + 0.25 * math.sin(2 * math.pi * 443.0 * t)
        v *= 0.5 + 0.5 * math.sin(2 * math.pi * 0.7 * t)
        s = int(max(-1.0, min(1.0, v)) * 30000)
        out += struct.pack("<h", s)
    return bytes(out)


class Session(object):
    def __init__(self, args):
        self.dir = args.out
        self.fps = args.fps
        self.sample_rate = args.sample_rate
        self.seconds = args.seconds
        self.index = 0
        self.opened = 1
        self.closed = 0
        self.refused = 0
        self.frames_total = 0
        self.bytes_total = 0
        self.largest = 0
        self.cur = None
        self.phase = 0
        self.lock = threading.Lock()
        self._open_locked()

    def path_for(self, index):
        return os.path.join(self.dir, "cut-%04d.wav" % index)

    def _open_locked(self):
        os.makedirs(self.dir, exist_ok=True)
        self.cur = WavClip(self.path_for(self.index), self.sample_rate)

    def feed(self, frames):
        """One tick of the feeder: a fixed slice of audio into the open clip."""
        with self.lock:
            chunk = tone_pcm(self.sample_rate, frames, self.phase)
            self.phase += frames
            self.cur.feed(chunk)

    def cut(self):
        """The verb: finalise the open clip, open the next one.  Returns reply fields."""
        with self.lock:
            frames = self.cur.frames
            path = self.cur.finalise()
            size = os.path.getsize(path)
            self.closed += 1
            self.frames_total += frames
            self.bytes_total += size
            if size > self.largest:
                self.largest = size
            self.index += 1
            self.opened += 1
            self._open_locked()
            return {"cut": True, "ok": True, "closed_clip": self.index - 1,
                    "closed_frames": frames, "closed_bytes": size,
                    "opened_clip": self.index, "clips_opened": self.opened,
                    "clips_closed": self.closed, "cuts_refused": self.refused,
                    "path": path}

    def final_only(self):
        with self.lock:
            if self.cur is None:
                return {"cut": False, "ok": False, "error": "no clip open", "final": True}
            frames = self.cur.frames
            path = self.cur.finalise()
            size = os.path.getsize(path)
            self.closed += 1
            self.frames_total += frames
            self.bytes_total += size
            self.cur = None
            return {"cut": True, "ok": True, "closed_clip": self.index,
                    "closed_frames": frames, "closed_bytes": size,
                    "clips_closed": self.closed, "final": True, "path": path}

    def counts(self):
        return {"closed": self.closed, "refused": self.refused,
                "frames_total": self.frames_total, "bytes_total": self.bytes_total,
                "largest": self.largest, "opened": self.opened}


def reply(obj):
    """One line out.  Shaped like the real child's stdin_write_reply(probe_json(...))."""
    sys.stdout.write(json.dumps(obj, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def selftest(fault):
    """The pre-flight arm.  Mirrors the real child's LAW-6 vocabulary."""
    if fault == "no-nvenc":
        log_line("=== SELFTEST: attempted H.264:open(INJECTED FAULT: nvEncodeAPI64.dll "
                 "treated as absent) ===")
        log_line("DECISION: REFUSED - NO ENCODER INITIALISED - the replay hotkey is NOT "
                 "armed.  Attempted: H.264:open(INJECTED FAULT)")
        log_line("The replay hotkey is NOT armed.  A dead hotkey that says why beats a "
                 "live hotkey that does nothing.")
        log_line("EXIT=3")
        return 3
    log_line("=== SELFTEST: stub encoder (no device, no WGC, no NVENC) ===")
    log_line("DECISION: ARMED - stub")
    log_line("OK: stub capture child initialised")
    log_line("EXIT=0")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--session", action="store_true")
    ap.add_argument("--inject-fault", default="none")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--sample-rate", type=int, default=16000)
    ap.add_argument("--seconds", type=float, default=3600.0)
    args = ap.parse_args()

    if args.selftest:
        return selftest(args.inject_fault)

    sess = Session(args)
    log_line("=== CUT SESSION: feed=STUB aus=generated fps=%u dir=%s ===",
             args.fps, args.out)
    log_line("  clip 0 open: %s", sess.path_for(0))

    stop = threading.Event()

    def stdin_pump():
        for raw in sys.stdin:
            line = raw.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line).get("cmd")
            except Exception:
                reply({"error": "unsupported or malformed command", "ok": False})
                continue
            if cmd == "ping":
                reply({"ok": True})
            elif cmd == "cut":
                reply(sess.cut())
            else:
                reply({"error": "unsupported or malformed command", "ok": False})
        stop.set()

    t = threading.Thread(target=stdin_pump, daemon=True)
    t.start()

    frames_per_tick = max(1, int(round(args.sample_rate / float(args.fps))))
    tick = 1.0 / float(args.fps)
    t0 = time.time()
    while not stop.is_set() and (time.time() - t0) < args.seconds:
        sess.feed(frames_per_tick)
        time.sleep(tick)

    log_line("  END OF STREAM: %s", json.dumps(sess.final_only(), separators=(",", ":")))
    c = sess.counts()
    log_line("=== CUT SESSION RESULT ===")
    log_line("  commands_served=?  cuts_sent=?  clips_opened=%d  clips_closed=%d  "
             "cuts_refused=%d", c["opened"], c["closed"], c["refused"])
    log_line("  frames_written=%d  bytes_written=%d  largest_clip_bytes=%d",
             c["frames_total"], c["bytes_total"], c["largest"])
    log_line("EXIT=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
