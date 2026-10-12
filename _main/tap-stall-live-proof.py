# -*- coding: utf-8 -*-
"""The LIVE proof for the tap-stall policy: does the worker still rotate the shared
audio endpoint while the endpoint is idle?

It counts REAL rotations (a `STATUS_APPLIED text="device-rotated"` the WORKER
emitted), NOT the bridge replays (`BRIDGE_STATUS_HELD`), and it measures stalls with
a spin thread at 20 ms. Before the fix the same box rotated every 45-62 s (two
independent instruments: `_main/rotation-burst-monitor.py` and
`_main/tap-stall-rate-probe.py`).

Writes nothing to the app log. Launches nothing.
"""
import os
import threading
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
SECS = float(os.environ.get("SOTTO_SECS", "600"))
MARK = ("device-rotated", "TAP_IDLE", "TAP_STALLED", "BRIDGE_EXIT", "BRIDGE_SPAWNED",
        "BRIDGE_CAPTION_SENT")

stalls = []
events = []
stop = threading.Event()


def spin():
    last = time.perf_counter()
    while not stop.is_set():
        now = time.perf_counter()
        gap = (now - last) * 1000.0
        if gap > 20.0:
            stalls.append(gap)
        last = now


def main():
    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    t0 = time.time()
    with open(LOG, encoding="utf-8", errors="replace") as handle:
        handle.seek(0, os.SEEK_END)
        while time.time() - t0 < SECS:
            time.sleep(0.05)
            for line in handle.readlines():
                text = line.strip()
                if text and any(mark in text for mark in MARK):
                    events.append((time.time() - t0, text))
    stop.set()
    thread.join(timeout=2)
    rotations = [e for e in events if "device-rotated" in e[1]
                 and "BRIDGE_STATUS_HELD" not in e[1]]
    prints = [e for e in events if "TAP_IDLE" in e[1] or "TAP_STALLED" in e[1]]
    captions = [e for e in events if "BRIDGE_CAPTION_SENT" in e[1]]
    deaths = [e for e in events if "BRIDGE_EXIT" in e[1]]
    spawns = [e for e in events if "BRIDGE_SPAWNED" in e[1]]
    worst = max(stalls, default=0.0)
    print("live proof: %.0fs at 20ms threshold" % SECS)
    print("REAL rotations emitted by the worker : %d" % len(rotations))
    print("idle/stall diagnostics                : %d" % len(prints))
    print("worker exits / spawns                : %d / %d" % (len(deaths), len(spawns)))
    print("captions in the window               : %d" % len(captions))
    print("machine stalls >20ms                 : %d (worst %.1f ms, p99 %.1f ms)"
          % (len(stalls), worst,
             sorted(stalls)[int(0.99 * len(stalls))] if stalls else 0.0))
    if rotations:
        print("the rotated endpoints:")
        for dt, text in rotations[:12]:
            print("  %6.1fs %s" % (dt, text[:110]))
    if prints:
        print("diagnostics:")
        for dt, text in prints[:12]:
            print("  %6.1fs %s" % (dt, text[:150]))
    verdict = "no rotation in %.0f s" % SECS
    print("VERDICT: %s" % ("PASS (an idle endpoint no longer costs a re-open)"
                              if not rotations else "FAIL: %d rotations" % len(rotations)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())