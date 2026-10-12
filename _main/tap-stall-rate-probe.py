#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
"""tap-stall-rate-probe.py -- MEASURE the cadence of the worker's tap rotation,
without inventing the numbers.

WHY THIS EXISTS (2026-10-12, owner's bug: "faz meu pc dar uma travada muito
forte a cada alguns segundos").

The shell log '_main/webview-run.log' carries NO timestamp per line -- that is a
registered deficiency (owner brief, the S7 task). So a rate cannot be read off
the file; it has to be SAMPLED live. This instrument:

  * follows ONLY the new bytes appended to the log (byte offset, partial lines
    held back until their newline arrives -- a half-written line is never counted);
  * every --interval seconds (default 2.0 s) it counts, for each candidate
    pattern, how many appeared in that slice;
  * over --secs (default 90 s) it prints one row per sample and a final summary:
    per-minute rate, mean interval between events, and the burst shape (max
    events seen in one single 2 s sample).

It counts SEVERAL cadences in the SAME window, because the question the owner
asked is a COMPARISON: which of these repeats "every few seconds"? Counting one
pattern alone cannot answer that -- hence every column below is measured over
the same slice, on the same clock, from the same file:

  tap-stall   STATUS_APPLIED text="device-rotated (tap-stalled)"
              -> the settled-tap watchdog fired: device_blocks froze
                 (worker TAP_STALL_S=8.0 s), so the worker CLOSED the WASAPI
                 endpoint and RE-OPENED one, in place.
  ladder-flat STATUS_APPLIED text="device-rotated (flat)"
              -> the ladder exhausted a 6 s window below the peak floor and
                 rotated to the next candidate (worker TAP_WINDOW_S=6.0).
  benign      BRIDGE_SILENT_BENIGN -> the bridge's 30 s silence window, a 30 s
              cadence, NOT a rotation.
  execjs      WARN exec_js TIMEOUT -> the panel's UI thread did not answer an
              exec_js in time (5 s DOM probe / 10 s caption push). This is a
              FREEZE SYMPTOM on the panel side, counted here as the competing
              hypothesis, not as evidence for the tap.
  outside     OUTSIDE_CLICK -> the click-hook logging.
  caption     CAPTION_APPLIED -> the healthy path, for scale.
  restart     BRIDGE_RESTART / BRIDGE_EXIT / HOT_RELOAD_WORKER_RESTART
              -> worker restarts (the owner already measured 0 in 1500 lines).

WHAT THIS DOES NOT PROVE: sampling the log gives the RATE of events, not the
wall-clock timestamps of the rotations themselves. A causal claim ("the
rotations freeze the PC") is NOT this instrument's output -- it produces the
interval the next step compares against "every few seconds".

Usage (never leaves a console window -- launched with pythonw):
    pythonw.exe _main/tap-stall-rate-probe.py --secs 90 --interval 2.0
    pythonw.exe _main/tap-stall-rate-probe.py --secs 60 --out _main/x.json
Exit code is 0 whenever the file could be followed, even with 0 events.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# name -> literal substring counted in each new slice. Deliberately LITERAL:
# a regex here would let a typo silently widen the claim.
CANDIDATES = [
    ("tap-stall", 'STATUS_APPLIED text="device-rotated (tap-stalled)"'),
    ("ladder-flat", 'STATUS_APPLIED text="device-rotated (flat)"'),
    ("benign", "BRIDGE_SILENT_BENIGN"),
    ("execjs", "WARN exec_js TIMEOUT"),
    ("outside", "OUTSIDE_CLICK"),
    ("caption", "CAPTION_APPLIED"),
    ("restart", "BRIDGE_RESTART"),
    ("exit", "BRIDGE_EXIT"),
    ("stats-push", "BRIDGE_STATS_PUSH"),
]


def follow(path, offset):
    """Return (new_complete_text, new_offset). Partial trailing line is held."""
    if not os.path.exists(path):
        return "", offset
    size = os.path.getsize(path)
    if size < offset:                      # log truncated/rotated under us
        offset = 0
    with open(path, "rb") as fh:
        fh.seek(offset)
        chunk = fh.read(size - offset)
    offset = size
    last_nl = chunk.rfind(b"\n")
    if last_nl < 0:
        return "", offset                  # no complete line yet
    return chunk[: last_nl + 1].decode("utf-8", "replace"), offset


def main():
    ap = argparse.ArgumentParser(description="sample the shell log for tap-rotation cadence")
    ap.add_argument("--secs", type=float, default=90.0)
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--log", default=os.path.join(REPO_ROOT, "_main", "webview-run.log"))
    ap.add_argument("--out", default=os.path.join(REPO_ROOT, "_main", "tap-stall-rate.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    names = [n for n, _ in CANDIDATES]
    totals = dict((n, 0) for n in names)
    per_sample = []                        # one dict per interval
    burst = dict((n, 0) for n in names)    # max events in ONE sample
    offset = 0
    t0 = time.time()
    deadline = t0 + args.secs
    # Prime the offset: a line written between startup and the first tick is
    # still counted, but the whole 10 MB history is NOT.
    _, offset = follow(args.log, 0)

    if not args.quiet:
        print("tap-stall-rate-probe: log=%s secs=%.1f interval=%.1f" % (
            args.log, args.secs, args.interval))
        print("sample  " + "  ".join("%-10s" % n for n in names))

    while True:
        now = time.time()
        if now >= deadline:
            break
        time.sleep(max(0.0, min(args.interval, deadline - now)))
        text, offset = follow(args.log, offset)
        row = dict((n, 0) for n in names)
        for name, needle in CANDIDATES:
            row[name] = text.count(needle)
            totals[name] += row[name]
            if row[name] > burst[name]:
                burst[name] = row[name]
        row["t"] = round(time.time() - t0, 2)
        row["bytes"] = len(text.encode("utf-8", "replace"))
        per_sample.append(row)
        if not args.quiet:
            print("%6.1fs " % row["t"] + "  ".join(
                "%10d" % row[n] for n in names) + "   (%d B)" % row["bytes"])

    secs = max(1e-9, time.time() - t0)
    summary = {
        "instrument": "_main/tap-stall-rate-probe.py",
        "log": args.log,
        "window_s": round(secs, 2),
        "interval_s": args.interval,
        "totals": totals,
        "per_min": dict((n, round(v * 60.0 / secs, 2)) for n, v in totals.items()),
        "max_per_sample": dict(burst),
        "mean_interval_s": dict(
            (n, (round(secs / v, 2) if v else None)) for n, v in totals.items()),
        "samples": len(per_sample),
        "samples_with_tap_stall": sum(1 for r in per_sample if r["tap-stall"]),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "per_sample": per_sample}, fh, indent=2)

    print("\n--- SUMMARY over %.1f s (%d samples) ---" % (secs, len(per_sample)))
    print("%-12s %8s %10s %14s %10s" % ("candidate", "count", "per_min", "mean_int_s", "max/2s"))
    for n in names:
        print("%-12s %8d %10.2f %14s %10d" % (
            n, totals[n], summary["per_min"][n],
            summary["mean_interval_s"][n] if summary["mean_interval_s"][n] is not None else "n/a",
            burst[n]))
    print("json written to %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
