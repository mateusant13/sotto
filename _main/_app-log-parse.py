"""Read-only parser for the owner's live app log (SottoFlatEndpointNaApp).

Extracts, in order, every worker spawn/exit/death and the worker's own
WORKER_STATS tag=final numbers, so "did the app emit captions with the new
module" is answerable from the log lines instead of from a glance. Prints
nothing but what the file says.
"""
import json
import re
import sys

path = sys.argv[1] if len(sys.argv) > 1 else "_main/_live_owner3.log"
t = open(path, encoding="utf-8", errors="replace").read()
lines = t.splitlines()


def stats_obj(s):
    """Pull the first WORKER_STATS tag=final field map out of an stderr_tail blob."""
    m = re.search(r"WORKER_STATS tag=final ([^\"]*)", s)
    if not m:
        return None
    d = {}
    for kv in m.group(1).split():
        if "=" in kv:
            k, v = kv.split("=", 1)
            d[k] = v
    return d


print("== BRIDGE events, in order ==")
for i, l in enumerate(lines):
    if "BRIDGE_SPAWNED" in l:
        m = re.search(r"pid=(\d+)", l)
        print("[%4d] SPAWN pid=%s" % (i, m.group(1) if m else "?"))
    elif "BRIDGE_EXIT" in l:
        m = re.search(r"pid=(\d+) rc=(-?\d+) spawns=(\d+) captions=(\d+) statuses=(\d+)", l)
        st = stats_obj(l)
        nz = st.get("nonzero_blocks") if st else "?"
        pk = st.get("peak") if st else "?"
        au = st.get("audio_s") if st else "?"
        print("[%4d] EXIT  pid=%s rc=%s spawns=%s captions=%s statuses=%s | final nonzero=%s peak=%s audio_s=%s"
              % (i,) if False else
              "[%4d] EXIT  %s | final nonzero_blocks=%s peak=%s audio_s=%s"
              % (i, m.groups() if m else l[:80], nz, pk, au))
    elif "BRIDGE_DEATH" in l:
        m = re.search(r"rc=(-?\d+) deaths=(\d+) last=\"([^\"]*)\"", l)
        print("[%4d] DEATH rc=%s deaths=%s last=%r" % (i, m.group(1), m.group(2), m.group(3)) if m else "[%4d] DEATH %s" % (i, l[:120]))

print()
print("== caption events (count) ==")
sent = [i for i, l in enumerate(lines) if "BRIDGE_CAPTION_SENT" in l]
applied = [i for i, l in enumerate(lines) if "CAPTION_APPLIED" in l]
print("BRIDGE_CAPTION_SENT n=%d first_idx=%s last_idx=%s" % (len(sent), sent[0] if sent else None, sent[-1] if sent else None))
print("CAPTION_APPLIED     n=%d first_idx=%s last_idx=%s" % (len(applied), applied[0] if applied else None, applied[-1] if applied else None))
print()
print("== first 3 and last 3 BRIDGE_CAPTION_SENT ==")
for i in sent[:3] + sent[-3:]:
    print("[%4d] %s" % (i, lines[i][:200]))
print()
print("== last 3 CAPTION_APPLIED ==")
for i in applied[-3:]:
    print("[%4d] %s" % (i, lines[i][:200]))

print()
print("== SILENT-DEVICE report lines: first and last ==")
sd = [i for i, l in enumerate(lines) if "SILENT-DEVICE" in l]
print("n=%d" % len(sd))
for i in sd[:2] + sd[-2:]:
    m = re.search(r"SILENT-DEVICE ([^\"\\]*)", lines[i])
    print("[%4d] %s" % (i, m.group(1)[:220] if m else lines[i][:220]))
