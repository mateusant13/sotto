# -*- coding: utf-8 -*-
"""Light rotation-burst monitor: stamps every rotation LINE with its arrival time.
Same clock as a 20 ms stall detector, no process enumeration (the box is under measurement).
"""
import os
import sys
import threading
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
SECS = float(os.environ.get("SOTTO_SECS", "180"))
STALL_MS = float(os.environ.get("SOTTO_STALL_MS", "50"))
MARK = ("device-rotated (tap-stalled)", "TAP_STALLED", "capture-started",
        "BRIDGE_METER", "BRIDGE_SILENT", "model-loading", "done", "silent-device")

stalls = []
events = []
stop = threading.Event()


def spin():
    last = time.perf_counter()
    while not stop.is_set():
        now = time.perf_counter()
        gap = (now - last) * 1000.0
        if gap > STALL_MS:
            stalls.append((time.time(), gap))
        last = now


def main():
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    t0 = time.time()
    offset = os.path.getsize(LOG)
    with open(LOG, encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        while time.time() - t0 < SECS:
            time.sleep(0.05)
            for line in handle.readlines():
                text = line.strip()
                if text and any(mark in text for mark in MARK):
                    events.append((time.time() - t0, text[:130]))
    stop.set()
    thread.join(timeout=2)
    print("rotation-burst monitor: %.0fs at %.0fms threshold" % (SECS, STALL_MS))
    print("events: %d   stalls>%.0fms: %d (worst %.1fms)" % (
        len(events), STALL_MS, len(stalls), max([g for _, g in stalls], default=0)))
    print("--- the timeline ---")
    prev = None
    for dt, text in events:
        gap = "" if prev is None else "  (+%.2fs)" % (dt - prev)
        print("  %7.2fs %s%s" % (dt, text, gap))
        prev = dt
    return 0


if __name__ == "__main__":
    raise SystemExit(main())