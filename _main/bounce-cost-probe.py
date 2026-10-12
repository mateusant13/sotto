# -*- coding: utf-8 -*-
"""Measures the cost of ONE staging bounce, without touching file content.

os.utimes() changes the mtime only, and the watcher filters FILE_NOTIFY_CHANGE_ALL
(which includes LAST_WRITE), so the bounce fires with zero bytes written. The script
records the arrival time of every log line the bounce produces and runs a 20 ms stall
detector in a thread at the same time.
"""
import os
import sys
import threading
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
PANEL = os.path.join(ROOT, "app", "panel", "panel.html")
STALL_MS = float(os.environ.get("SOTTO_STALL_MS", "20"))
WATCH_S = float(os.environ.get("SOTTO_WATCH_S", "12"))

stalls = []
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
    size = os.path.getsize(LOG)
    with open(LOG, encoding="utf-8", errors="replace") as handle:
        handle.seek(size)
        thread = threading.Thread(target=spin, daemon=True)
        thread.start()
        time.sleep(0.3)
        t_touch = time.time()
        os.utime(PANEL, None)
        print("touched %s at %s (mtime only, no bytes written)" % (os.path.basename(PANEL), time.strftime("%H:%M:%S", time.localtime(t_touch))))
        fresh = []
        while time.time() - t_touch < WATCH_S:
            for line in handle.readlines():
                text = line.strip()
                if text:
                    fresh.append((time.time() - t_touch, text))
            time.sleep(0.02)
        stop.set()
        thread.join(timeout=2)
    print("\n--- the bounce, on one clock (seconds after the touch) ---")
    for dt, text in fresh:
        print("  +%6.3fs  %s" % (dt, text[:120]))
    if not fresh:
        print("  (no log line: the bounce did not happen in %.1fs)" % WATCH_S)
    print("\n--- stalls above %.0fms during the bounce ---" % STALL_MS)
    if stalls:
        for when, gap in stalls[:40]:
            print("  +%6.3fs  %.1fms" % (when - t_touch, gap))
        print("  total=%d worst=%.1fms" % (len(stalls), max(g for _, g in stalls)))
    else:
        print("  none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())