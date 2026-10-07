"""Oracle for the moment-of-choice cure: does the live endpoint reach attempt 1?

Builds the candidate list the way a SILENT reading leaves it (the default render
endpoint first, because that is the tie-break the sort falls back to when every
meter reads 0.0), then asks `prefer_rendering_now` -- the cure -- to make the
choice again NOW, with the live meter, and asserts that the endpoint which is
actually rendering has been moved to `attempt_no`.

Arms:
  green   : the live endpoint is moved to attempt 0
  red     : built WITHOUT the cure (`_main/_ordem-before`), where nothing moves --
            run with the argument `before` against that copy.

    python.exe _main/_ordem-cura-oracle.py [worker-dir]
"""
import copy
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
worker_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
    os.path.join(HERE, "..", "worker")
sys.path.insert(0, worker_dir)

import wasapi_loopback  # noqa: E402

print("worker_dir = %s" % worker_dir)

peaks = wasapi_loopback.live_render_peaks(meter_ms=0.4)
print("live meter now (endpoint_id -> peak):")
loudest = max(peaks.items(), key=lambda kv: kv[1] or 0.0) if peaks else (None, 0.0)
for eid, pk in sorted(peaks.items(), key=lambda kv: -(kv[1] or 0.0)):
    print("    %-6s %s" % ("%.6f" % (pk or 0.0), eid))
print("LOUDEST = %s at %.6f" % (loudest[0], loudest[1] or 0.0))

# The list a SILENT reading leaves behind: the default endpoint first, then the
# rest in enumeration order -- exactly what `[A1]` of the order probe measured.
# The ids a real candidate carries are IMMDevice::GetId strings, i.e. the
# `{0.0.0.00000000}.{guid}` form -- `device_candidates()` dedups on exactly that.
PREFIX = "{0.0.0.00000000}.{"
SUFFIX = "}"
SILENT_ORDER = [PREFIX + g + SUFFIX for g in (
    "55395a4e-97b2-4b96-9878-18be1ed894e0",   # VoiceMeeter Input   (default, idle here)
    "1aee4592-2e18-4248-bf54-2fa14af8315c",   # Speakers
    "2f1295af-8529-4f15-b00d-7b9bba575ac0",   # CABLE Input          <- carries the audio
    "6780e74d-2f7e-42e0-bcb4-ee85911b5259",   # Fones de ouvido
    "7d427fc9-5cff-431f-ae0c-c1abd1229f8b",   # AG251F1WG2
    "b1e02bd0-0cc2-40b4-8eb8-7827f979ff73",   # Alto-falantes
)]
NAMES = {
    PREFIX + "55395a4e-97b2-4b96-9878-18be1ed894e0" + SUFFIX: "VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)",
    PREFIX + "1aee4592-2e18-4248-bf54-2fa14af8315c" + SUFFIX: "Speakers (NVIDIA Broadcast)",
    PREFIX + "2f1295af-8529-4f15-b00d-7b9bba575ac0" + SUFFIX: "CABLE Input (VB-Audio Virtual Cable)",
    PREFIX + "6780e74d-2f7e-42e0-bcb4-ee85911b5259" + SUFFIX: "Fones de ouvido (soundcore Space Q45)",
    PREFIX + "7d427fc9-5cff-431f-ae0c-c1abd1229f8b" + SUFFIX: "AG251F1WG2 (NVIDIA High Definition Audio)",
    PREFIX + "b1e02bd0-0cc2-40b4-8eb8-7827f979ff73" + SUFFIX: "Alto-falantes (HyperX Quadcast)",
}

candidates = [
    {
        "name": "WASAPI loopback: %s" % NAMES[eid],
        "index": None,
        "wasapi_loopback": True,
        "endpoint_id": eid,
        "rung": "a",
        "rung_why": "WASAPI loopback of an active render endpoint",
    }
    for eid in SILENT_ORDER
]

print("order BEFORE the choice: %s" % [c["name"].split(": ")[1] for c in candidates])

import sotto_worker  # noqa: E402

has_cure = hasattr(sotto_worker, "prefer_rendering_now")
print("cure present in module: %s" % has_cure)

t0 = time.time()
if has_cure:
    chosen = sotto_worker.prefer_rendering_now(candidates, 0)
    cost = time.time() - t0
else:
    chosen = candidates[0]
    cost = time.time() - t0
    # RED arm: reproduce what the ladder does without the cure -- take the head.
print("re-read cost = %.3f s" % cost)
print("order AFTER  the choice: %s" % [c["name"].split(": ")[1] for c in candidates])
print("attempt 1 would open  : %s" % chosen["name"].split(": ")[1])

live_name = NAMES[loudest[0]]
verdict = "GREEN" if chosen["name"].split(": ")[1] == live_name else "RED"
print("VERDICT %s -- live endpoint is %r, attempt 1 opens %r"
      % (verdict, live_name, chosen["name"].split(": ")[1]))
sys.exit(0 if verdict == "GREEN" else 3)
