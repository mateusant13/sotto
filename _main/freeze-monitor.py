# -*- coding: utf-8 -*-
"""Stall + event-timeline monitor for the owner-reported hard freezes.

One timeline, three streams, same clock:
  * STALL  -- a spin thread records every gap above the threshold (the freeze itself),
            with a wall-clock stamp and the depth;
  * LOG    -- the sampler keeps a byte offset into _main/webview-run.log and stamps every
            NEW line with its arrival time, so the app events get timestamps for free;
  * PROC   -- per-process CPU seconds (shell, worker, webviews) at the same cadence, so a
            stall can be attributed to a process.

It launches nothing, needs psutil, and writes NDJSON to $SOTTO_OUT (default
I:/cc-tmp/freeze-monitor.jsonl). Threshold and duration come from the environment.
"""
import json
import os
import sys
import threading
import time

try:
    import psutil
except Exception as exc:  # pragma: no cover - measured on this box: psutil 5.9.8
    sys.stderr.write("freeze-monitor needs psutil: %r\n" % (exc,))
    raise SystemExit(3)

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
LOG = os.path.join(ROOT, "_main", "webview-run.log")
OUT = os.environ.get("SOTTO_OUT", "I:/cc-tmp/freeze-monitor.jsonl")
STALL_MS = float(os.environ.get("SOTTO_STALL_MS", "20"))
SECS = float(os.environ.get("SOTTO_SECS", "600"))
GRID = float(os.environ.get("SOTTO_GRID", "0.25"))

WATCH_NAMES = ("sotto_webview.py", "sotto_worker.py", "msedgewebview2.exe", "pythonw.exe", "python.exe")


def stamp():
    t = time.time()
    return "%s.%03d" % (time.strftime("%H:%M:%S", time.localtime(t)), int((t % 1) * 1000))


def tracked():
    out = {}
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            cmd = " ".join(info.get("cmdline") or [])
            if info.get("name") in WATCH_NAMES and ("sotto" in cmd.lower() or info.get("name") == "msedgewebview2.exe"):
                cpu = proc.cpu_times()
                out[info["pid"]] = {"name": info["name"], "cpu_s": cpu.user + cpu.system,
                                    "rss_mb": round(proc.memory_info().rss / 1048576.0, 1)}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return out


def main():
    stalls = []
    rows = []
    stop = threading.Event()

    def spin():
        last = time.perf_counter()
        while not stop.is_set():
            now = time.perf_counter()
            gap = (now - last) * 1000.0
            if gap > STALL_MS:
                stalls.append({"kind": "stall", "wall": stamp(), "gap_ms": round(gap, 1)})
            last = now

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()

    offset = os.path.getsize(LOG) if os.path.exists(LOG) else 0
    procs = tracked()
    t0 = time.time()
    with open(LOG, encoding="utf-8", errors="replace") as handle:
        handle.seek(offset)
        while time.time() - t0 < SECS:
            time.sleep(GRID)
            fresh = handle.readlines()
            if fresh:
                for line in fresh:
                    text = line.strip()
                    if not text:
                        continue
                    rows.append({"kind": "log", "wall": stamp(), "text": text[:150]})
            now_procs = tracked()
            rows.append({"kind": "proc", "wall": stamp(),
                         "p": {str(k): {"cpu": round(v["cpu_s"] - procs.get(k, {}).get("cpu_s", v["cpu_s"]), 2),
                                       "rss": v["rss_mb"], "n": v["name"]} for k, v in now_procs.items()}})
            procs = now_procs
    stop.set()
    thread.join(timeout=2)

    payload = {"kind": "summary", "wall": stamp(), "secs": SECS, "threshold_ms": STALL_MS,
               "stall_count": len(stalls),
               "stalls": stalls,
               "events": rows}
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    print("freeze-monitor: %.0fs, %d stalls > %.0fms, %d log events, %d proc rows"
          % (SECS, len(stalls), STALL_MS, sum(1 for r in rows if r["kind"] == "log"), sum(1 for r in rows if r["kind"] == "proc")))
    if stalls:
        gaps = sorted(s["gap_ms"] for s in stalls)
        print("  worst=%.1fms median=%.1fms p90=%.1fms" % (gaps[-1], gaps[len(gaps) // 2], gaps[int(len(gaps) * 0.9)]))
        print("  first 20: " + " | ".join("%s %sms" % (s["wall"], s["gap_ms"]) for s in stalls[:20]))
    from collections import Counter
    tally = Counter()
    for r in rows:
        if r["kind"] == "log":
            text = r["text"]
            for token in ("HOT_RELOAD", "OUTSIDE_CLICK", "BRIDGE_STATS_PUSH", "BRIDGE_SILENT", "PANEL_SHOW_REFUSED",
                          "TAP_STALLED", "device-rotated", "CAPTION_APPLIED", "RACE_PROBE"):
                if token in text:
                    tally[token] += 1
    print("  events: " + (", ".join("%s=%d" % kv for kv in sorted(tally.items())) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())