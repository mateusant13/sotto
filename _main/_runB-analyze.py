"""Analyse the Run B log delta: captions, final stats, probe gate.

Prints ONLY what the file says, with the line numbers in the post-launch slice,
so every claim in the report can be traced to a line.
"""
import json
import re
import sys

log = sys.argv[1] if len(sys.argv) > 1 else "_main/webview-run.log"
base = int(open("_main/_runB-baseline.txt").read().strip())
lines = open(log, encoding="utf-8", errors="replace").read().splitlines()
new = lines[base:]
print("=== log=%s  baseline=%d  total=%d  NEW=%d ===" % (log, base, len(lines), len(new)))

sent = [l for l in new if "BRIDGE_CAPTION_SENT" in l]
applied = [l for l in new if "CAPTION_APPLIED" in l]
print("BRIDGE_CAPTION_SENT  n=%d" % len(sent))
print("CAPTION_APPLIED      n=%d" % len(applied))
for l in sent[:6]:
    print("   ", l[:220])
if len(sent) > 6:
    print("    ...")
    for l in sent[-3:]:
        print("   ", l[:220])

print()
print("=== PANEL V2 ===")
for l in new:
    if "PANEL_V2" in l:
        print(l[:4000])

print()
print("=== worker spawn / exit / death / silent ===")
for i, l in enumerate(new):
    if ("BRIDGE_SPAWNED" in l or "BRIDGE_EXIT" in l or "BRIDGE_DEATH" in l
            or "BRIDGE_SILENT" in l or "BRIDGE_CAPTION" in l):
        print("[%4d] %s" % (i, l[:260]))

print()
print("=== WORKER_STATS final + peak-bearing tick lines (from stderr_tail blobs) ===")
blob = "\n".join(new)
for m in re.finditer(r"WORKER_STATS tag=(final|tick) ([^\"\\]*)", blob):
    tag, body = m.group(1), m.group(2)
    d = dict(kv.split("=", 1) for kv in body.split() if "=" in kv)
    if tag == "final" or (d.get("peak") and float(d["peak"] or 0) > 0.01):
        print("tag=%-5s nonzero_blocks=%s peak=%s captions=%s tokens=%s audio_s=%s"
              % (tag, d.get("nonzero_blocks"), d.get("peak"),
                 d.get("captions"), d.get("tokens"), d.get("audio_s")))

print()
print("=== verdict / device_outcome / silent-device / all-flat mentions ===")
for pat in ("SILENT-DEVICE", "all-flat", "verdict", "device_outcome",
            "proved_alive", "tap_ledger", "rung"):
    hits = [l for l in new if pat in l]
    print("  %-16s n=%d" % (pat, len(hits)))
    for l in hits[:2]:
        print("      ", l[:240])
