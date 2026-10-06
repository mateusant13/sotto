"""Exercise the Sotto audio ladder's candidate order and print the rung taken.

Read-only: builds the candidate list and, optionally, opens the first candidate
for a bounded window to measure its peak. Writes verbatim to
H:/sotto/_main/ladder-probe.log. Launch hidden.
"""
import io
import json
import os
import sys
import time

ROOT = r"H:\sotto"
sys.path.insert(0, os.path.join(ROOT, "worker"))
OUT = os.path.join(ROOT, "_main", "ladder-probe.log")

log = io.open(OUT, "w", encoding="utf-8")


def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


import sotto_worker as W  # noqa: E402

p("=== PREFERRED_DEVICES (shipped literal list) ===")
p("  ", repr(W.PREFERRED_DEVICES))
p("=== heuristic patterns ===")
p("  ", W.LOOPBACK_NAME_PATTERNS)

cfg = json.load(io.open(os.path.join(ROOT, "worker", "config.json"), encoding="utf-8"))
audio = cfg["audio"]
p("")
p("=== config.json audio block ===")
p("  device:", repr(audio.get("device")), " preferred_devices:", repr(audio.get("preferred_devices")))

p("")
p("=== LADDER: device_candidates(config, wanted=None) ===")
cands = W.device_candidates(audio, None)
for i, d in enumerate(cands):
    p(
        "  [%d] rung=%s api=%s\n        name=%r\n        why=%s"
        % (i, d.get("rung"), W._host_api_name(d), d["name"], d.get("rung_why"))
    )

p("")
p("=== LADDER: device_candidates(config, wanted='CABLE') -- explicit override ===")
cands_w = W.device_candidates(audio, "CABLE")
for i, d in enumerate(cands_w[:4]):
    p("  [%d] rung=%s name=%r" % (i, d.get("rung"), d["name"]))

p("")
p("=== RUNG TAKEN ===")
if cands:
    first = cands[0]
    p(
        "  rung=%s  device=%r  api=%s"
        % (first.get("rung"), first["name"], W._host_api_name(first))
    )
    if first.get("rung") == "a":
        p("  -> the driver-free rung wins: WASAPI loopback of the default render endpoint.")
    elif first.get("rung") == "b":
        p("  -> rung (b): a virtual-cable/stereo-mix input matched BY NAME PATTERN.")
    elif first.get("rung") == "c":
        p("  -> rung (c): the explicit override.")

# ── live arm: open the top candidate and measure a real peak ─────────────────
if "--live" in sys.argv:
    seconds = float(os.environ.get("LADDER_SECONDS", "6"))
    blocks = []
    peaks = {"v": 0.0}

    def on_block(b):
        import numpy as np

        blocks.append(1)
        pk = float(abs(b).max()) if b.size else 0.0
        if pk > peaks["v"]:
            peaks["v"] = pk

    dev = cands[0]
    p("")
    p("=== LIVE: opening rung %s for %.1fs ===" % (dev.get("rung"), seconds))
    try:
        tap = W.LoopbackTap(dev, on_block, block_ms=100)
        tap.__enter__()
        p("  opened: class=%s rate=%s block=%s" % (type(tap).__name__, tap.rate, tap.block))
        t0 = time.time()
        while time.time() - t0 < seconds:
            time.sleep(0.1)
        tap.__exit__(None, None, None)
        p("  blocks=%d peak=%.6f" % (len(blocks), peaks["v"]))
        if peaks["v"] >= W.TAP_PEAK_FLOOR:
            p("  VERDICT: rung %s CARRIED audio (peak %.6f >= floor %.6f)"
              % (dev.get("rung"), peaks["v"], W.TAP_PEAK_FLOOR))
        else:
            p("  VERDICT: rung %s opened and was SILENT (peak %.6f < floor %.6f)"
              % (dev.get("rung"), peaks["v"], W.TAP_PEAK_FLOOR))
    except Exception as exc:
        p("  OPEN FAILED: %s: %s" % (type(exc).__name__, exc))

log.close()
sys.stdout.write("ladder-probe written to %s\n" % OUT)
