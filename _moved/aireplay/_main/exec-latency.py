#!/usr/bin/env python3
"""exec-latency.py — measure the DELIVERY latency of the `mcode exec` channel.

WHY
---
Receipt-27 measured the QUEUE channel (2m56s, N=1) using the authoritative link.
The EXEC channel is the one that delivers to an IDLE session, and that is the
owner's actual requirement. What was known: it returns rc=0. What was NOT known:
how long from "issued" to "the turn was ACCEPTED".

A process duration is NOT a delivery latency. The exec process stays alive for a
whole agent turn, so timing the subprocess measures the agent, not the channel.
The delivery instant is `turn_ingress.accepted_at_ms` for the target session.

WHAT IT DELIBERATELY PRINTS
  * claim_source and queue_item_ids_json for every candidate ingress row, so the
    channel is identified structurally, never by a text match on the payload.
  * BOTH numbers, separately labelled: accepted-latency and process-duration.
  * Every candidate row in the window, so a concurrent scheduled fire shows up as
    ambiguity instead of silently becoming "the" answer.

Usage:
  py -3 exec-latency.py --session <id> --prompt <file> [--cwd <dir>]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def ts(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S.%f")[:-3]
    except (TypeError, ValueError):
        return repr(ms)


def out(*a) -> None:
    print(*a, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--cwd", required=True)
    ap.add_argument("--timeout", default="8m")
    args = ap.parse_args()

    with open(args.prompt, "r", encoding="utf-8") as fh:
        prompt = fh.read()

    t0 = int(time.time() * 1000)
    out(f"T0 issued        = {ts(t0)}  (local)")
    out(f"target session   = {args.session}")
    out(f"workspace (arg)  = {args.cwd}")
    out(f"prompt           = {len(prompt)} chars, via STDIN (argv splits it)")
    out("channel under test = mcode exec  -- NOT the queue")
    out()    # `mcode` on this box is an npm shim: mcode.ps1 (PowerShell), mcode.cmd and a
    # shell script. Python's subprocess cannot resolve the PowerShell one, and
    # FileNotFoundError is the result. Resolve the .cmd explicitly, then fall back
    # to PATH, then to the known install dir -- never a guess.
    exe = (shutil.which("mcode.cmd") or shutil.which("mcode")
           or r"H:\env\npm-global\mcode.cmd")
    if not os.path.exists(exe):
        out(f"ABORT: cannot resolve the mcode executable (tried {exe})")
        return 1
    out(f"mcode executable  = {exe}")
    out()

    proc = subprocess.run(
        [exe, "exec", "--session", args.session, "--cwd", args.cwd,
         "--permission", "off", "--input", "-", "--timeout", args.timeout],
        input=prompt, capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    t1 = int(time.time() * 1000)
    out(f"T1 process exit  = {ts(t1)}   rc={proc.returncode}")
    out(f"   PROCESS DURATION = {(t1 - t0) / 1000.0:.1f}s "
        f"<- NOT the delivery latency; it includes a whole agent turn")

    # Print WHY. MEASURED 13:05:43: rc=4 with n=0 turns accepted, and this script
    # printed only the number. That is the same defect I fixed in the driver an hour
    # ago -- reporting a code without the reason sends you to fix the wrong thing.
    body = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if body:
        out("\nexec output (the reason, not just the code):")
        for line in body.splitlines()[:14]:
            out("    " + line)
    else:
        out("\nexec output: EMPTY (nothing to explain the failure with)")

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select turn_id, accepted_at_ms, claim_source, queue_item_ids_json, status "
        "from local_runtime_turn_ingress where session_id=? and accepted_at_ms>=? "
        "order by accepted_at_ms asc", (args.session, t0 - 5000)).fetchall()

    out(f"\nPOPULATION = every turn_ingress row for this session with "
        f"accepted_at_ms >= {ts(t0 - 5000)}  ->  n={len(rows)}")
    if not rows:
        out("  NONE. The exec returned but no turn was accepted in the window.")
        out("  That is a real result: it means the exec did NOT deliver.")
        return 2

    out(f"\n{'turn accepted':<16} {'latency':>10}  {'claim_source':<12} "
        f"{'queue-linked':<12} status")
    out("-" * 82)
    linked = []
    for r in rows:
        delta = (r["accepted_at_ms"] - t0) / 1000.0
        q = r["queue_item_ids_json"]
        linked.append((delta, bool(q)))
        out(f"{ts(r['accepted_at_ms']):<16} {delta:>9.1f}s  "
            f"{str(r['claim_source']):<12} {('YES' if q else 'no'):<12} "
            f"{r['status']}")

    first = rows[0]
    d = (first["accepted_at_ms"] - t0) / 1000.0
    out(f"\nEXEC DELIVERY LATENCY = {d:.1f}s  (issued -> turn accepted)")
    out(f"  claim_source={first['claim_source']}  "
        f"queue_item_ids_json={'SET' if first['queue_item_ids_json'] else 'NULL'}")
    out("  If queue_item_ids_json is NULL, this turn did NOT come through the")
    out("  queue -- it is an exec delivery. That is the structural identification,")
    out("  not a text match on the payload.")
    if len(rows) > 1:
        out(f"\n  AMBIGUITY: {len(rows)} turns in the window. A concurrent scheduled")
        out("  fire may be among them. The FIRST is reported; do not read it as")
        out("  exclusively the exec's own delivery without isolating it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())