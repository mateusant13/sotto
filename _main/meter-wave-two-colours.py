"""The WAVE datum, measured on the live path at the SHIPPED DEFAULT (no flag).

TWO colours, and the coordinating agent's rule that one without the other is not a
pass:
  * the datum EXISTS and MOVES — a level per window whose amplitude changes between
    samples, rising AND falling (a run maximum can only rise);
  * the LOG-side cost is a NUMBER, so the flood is a budget and not a scare.

Also prints what the PANEL would receive today, from the shell's own code path
(`stats()` reads `last_worker_stats`, which the shell parses from the WORKER_STATS
stderr line) — because "the datum moves" and "the wave moves" are two different
claims and only the second one is the owner's.
"""

from __future__ import annotations

import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))


def rows(path):
    with io.open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip().startswith("{")]


def main():
    p = os.path.join(HERE, "_meter-default-live.jsonl")
    r = rows(p)
    m = [x for x in r if x.get("type") == "meter"]
    caps = [x for x in r if x.get("type") == "caption"]

    print("=" * 78)
    print("1. THE DATUM AT THE SHIPPED DEFAULT (live loop, file tap, no device)")
    print("=" * 78)
    print("   meter events        :", len(m))
    print("   captions            :", len(caps))
    if not m:
        print("   NO EVENTS -> the wrong cure is back (data switched off)")
        return
    lv = [e["peak"] for e in m]
    rises = sum(1 for a, b in zip(lv, lv[1:]) if b > a)
    falls = sum(1 for a, b in zip(lv, lv[1:]) if b < a)
    flat = sum(1 for a, b in zip(lv, lv[1:]) if b == a)
    print("   distinct amplitudes :", len(set(lv)), "of", len(lv), "samples")
    print("   RISES / FALLS / flat:", rises, "/", falls, "/", flat)
    print("   min / max           :", min(lv), "/", max(lv))
    print("   first 14 samples    :", [round(v, 4) for v in lv[:14]])
    print()
    print("   THE WAVE IS DRAWN FROM THE CHANGES: a wave whose amplitude never")
    print("   changes is a flat line, and one that only rises is a staircase.")
    print("   MEASURED: %d rises and %d falls across %d samples." % (rises, falls, len(lv)))
    print("   `blocks` per event  :", sorted({e["blocks"] for e in m}))

    print()
    print("=" * 78)
    print("2. WHAT THE PANEL RECEIVES TODAY (the shell's own path, not mine)")
    print("=" * 78)
    st = [l for l in io.open(os.path.join(HERE, "_meter-default-live.err"),
                             encoding="utf-8", errors="replace")
          if l.startswith("WORKER_STATS")]
    print("   WORKER_STATS lines on stderr:", len(st), "at --stats-interval 4")
    for l in st[-2:]:
        d = dict(re.findall(r"(\w+)=([^ ]+)", l))
        print("     tag=%-6s peak=%s blocks=%s  <- this is what `stats()` returns"
              % (d.get("tag"), d.get("peak"), d.get("blocks")))
    print()
    print("   The shell's `stats()` (`sotto_webview.py:4796-4809`) reads `peak` and")
    print("   `blocks` from `last_worker_stats`, which `_pump` fills ONLY from the")
    print("   WORKER_STATS stderr line (`:6142-6147`). It has NO `type:\"meter\"`")
    print("   branch (`grep meter` -> no `kind == 'meter'`).")
    print("   CONSEQUENCE, stated plainly: **the datum moves at 10 Hz; the WAVE")
    print("   still moves at 1 point per %s s, from a RUN MAXIMUM that cannot fall.**"
          % "10")
    print("   That is the ORIGINAL defect, and it is the shell's half to close.")

    print()
    print("=" * 78)
    print("3. THE LOG-SIDE COST, AS A NUMBER (bytes per minute)")
    print("=" * 78)
    line = "sotto: BRIDGE_UNKNOWN type='meter'"
    # the shell prefixes every line with 'sotto: ' and writes it with a newline
    n = len(line.encode("utf-8")) + 1
    print("   the shell's line, verbatim shape: %r" % line)
    print("   bytes per line (UTF-8 + newline):", n)
    print("   at 10 Hz  = %d B/s  = %d B/min = %.1f KB/min" % (n * 10, n * 600, n * 600 / 1024))
    print("   at 0.1 Hz (today, WORKER_STATS) = %d B/min" % (n * 6))
    print()
    print("   AND THE FIX ALREADY EXISTS IN THAT FILE, for the sibling push:")
    print("   `_stats_log_maybe` (`:4847-4860`) logs the FIRST sample and then at")
    print("   most ONE line per `STATS_LOG_INTERVAL_S = 30.0`, carrying the count.")
    print("   The same shape applied to the unknown-type path takes %d B/min ->"
          % (n * 600))
    print("   %d B/min (1 line + 2 aggregates per minute, ~%d B each)."
          % (3 * n, n))
    print("   NOT RUN: I cannot run the shell (single-instance lock, and it is the")
    print("   owner's live app). This is the file's own arithmetic.")


if __name__ == "__main__":
    main()
