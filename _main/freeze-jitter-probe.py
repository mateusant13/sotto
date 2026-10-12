#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
"""freeze-jitter-probe.py -- is the OWNER'S machine freezing, and WHAT froze it?

A "travada" is a wall-clock pause: the box stops answering for a fraction of a
second to seconds. The instrument has two halves, run in ONE process so the
pause and its context are captured together:

  1. A tight timer loop (time.perf_counter, no work between iterations) for
     --secs. Any gap > --threshold-ms is a pause; the histogram (p50..p99.9,
     MAX, and counts above 5/20/100/500/1000 ms) is the answer to "my pc
     dar uma travada muito forte": a 300 ms gap IS a felt freeze, a 743 ms gap
     is a hard one.

  2. AT EACH PAUSE, the probe records the byte size of the shell's log BEFORE
     and AFTER the pause, plus machine facts (the shell's 2 s heartbeat file
     mtime, the worker's own state and reopens counter read out of
     panel-state.json). After the loop it reads the log bytes that were
     appended DURING each pause and prints them. That is the attribution step:
     a pause that lands on
        STATUS_APPLIED text="device-rotated (tap-stalled)"
     is the tap re-open; a pause that lands on OUTSIDE_CLICK lines is the click
     hook; a pause with no log growth at all is outside this app.

LIMITS, stated so the receipt does not overclaim:
  * A tight Python loop runs on ONE core. On a 20-core box it cannot see a
    freeze of a different core, a GPU/driver stall, or a single-core spin that
    does not deschedule it. So "max_gap_ms small" means "no whole-machine
    freeze in this window", not "the machine is healthy". The companion
    instrument _main/panel-stall-probe.py covers the box-wide case through the
    shell's own 2 s heartbeat.
  * The log context is only as good as the log: a pause caused by something
    that writes nothing to _main/webview-run.log shows up as "no log growth",
    which is a true negative for THIS app, not proof of innocence.
  * The pause is not timestamped against the shell's clock, so a coincidence
    inside the same second is the strongest claim available here.

Usage:
    pythonw.exe _main/freeze-jitter-probe.py --secs 120 --threshold-ms 50
Exit 0 always.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO_ROOT, "_main", "webview-run.log")
STATE = os.path.join(REPO_ROOT, "_main", "panel-state.json")


def facts():
    out = {}
    try:
        out["state_mtime_age"] = round(time.time() - os.path.getmtime(STATE), 3)
    except OSError:
        out["state_mtime_age"] = None
    try:
        with open(STATE, "r", encoding="utf-8", errors="replace") as fh:
            ps = json.load(fh)
        w = ps.get("worker") or {}
        out["worker_state"] = w.get("state")
        out["namedState"] = ps.get("namedState")
        out["noAudioAge"] = w.get("noAudioEvidenceAgeS")
        tap = next((l for l in (w.get("stderrTail") or []) if "TAP_STALLED" in l), "")
        out["tap_dev"] = (tap.split("device=", 1)[1].split("'", 1)[0]
                            if "device=" in tap else None)
    except Exception as exc:
        out["err"] = type(exc).__name__
    return out


def main():
    ap = argparse.ArgumentParser(description="tight-loop timer jitter + per-pause log attribution")
    ap.add_argument("--secs", type=float, default=60.0)
    ap.add_argument("--threshold-ms", type=float, default=50.0)
    args = ap.parse_args()

    gaps = []
    pauses = []
    prev = time.perf_counter()
    t0 = prev
    log_size = os.path.getsize(LOG)
    n = 0
    while time.perf_counter() - t0 < args.secs:
        now = time.perf_counter()
        g = (now - prev) * 1000.0
        prev = now
        gaps.append(g)
        n += 1
        try:
            sz = os.path.getsize(LOG)
        except OSError:
            sz = log_size
        if g > args.threshold_ms:
            pauses.append({"t": round(now - t0, 3), "gap_ms": round(g, 3),
                           "log_before": log_size, "log_after": sz,
                           "facts": facts()})
            log_size = sz
        else:
            log_size = sz

    s = sorted(gaps)
    ms = lambda p: s[min(len(s)-1, int(len(s)*p))]
    print("freeze-jitter-probe: %d iterations over %.1f s" % (n, time.perf_counter()-t0))
    print("  gap (ms): min=%.3f p50=%.3f p90=%.3f p99=%.3f p99.9=%.3f MAX=%.3f"
          % (s[0], ms(.5), ms(.9), ms(.99), ms(.999), s[-1]))
    for th in (5, 20, 50, 100, 500, 1000):
        print("  gaps > %5d ms : %d" % (th, sum(1 for x in s if x > th)))

    print("")
    print("=== PAUSES over %.0f ms: %d ===" % (args.threshold_ms, len(pauses)))
    for p in pauses:
        lines = []
        if p["log_after"] > p["log_before"]:
            try:
                with open(LOG, "rb") as fh:
                    fh.seek(p["log_before"])
                    chunk = fh.read(min(p["log_after"] - p["log_before"], 200000))
                for raw in chunk.split(b"\n"):
                    t = raw.decode("utf-8", "replace").strip()
                    if t:
                        lines.append(t.replace("sotto: ", "")[:150])
            except OSError as exc:
                lines.append("(read failed: " + type(exc).__name__ + ")")
        f = p["facts"]
        print("  t=%6.2fs gap=%9.3fms log%+6dB heartbeat_age=%s worker=%s noAudioAge=%s tap=%s"
              % (p["t"], p["gap_ms"], p["log_after"]-p["log_before"],
                 f.get("state_mtime_age"), f.get("worker_state"), f.get("noAudioAge"), f.get("tap_dev")))
        for l in lines:
            print("        | " + l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
