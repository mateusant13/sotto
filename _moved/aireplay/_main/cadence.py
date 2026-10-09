#!/usr/bin/env python3
"""cadence.py — does the wake actually fire every 3 minutes, over a real sample?

WHY
---
Every claim about the wake so far has been N=1: one delivery, one latency, one
no-op. The owner's requirement is a CADENCE -- a wake every 3 minutes with the
agent alive between fires. A cadence claim needs a cadence sample, so this
census runs for a bounded window and reports the DISTRIBUTION of gaps, not an
average, because an average hides exactly the failure that matters: a fire that
took 20 minutes is invisible in a mean.

WHAT IT COUNTS, precisely
  * a "fire" is a line in heartbeat.log matching TARGET|PRUNE|WAKE sending|ABORT|SKIP
  * a "delivery" is a queue-linked turn OR an exec rc=0 in the same window
  * a "no-op" is a fire whose outcome is a refusal (rc=4 / already queued)

It never greps the store for a payload marker. Delivery is claimed only from
the structural links (turn_ingress.queue_item_ids_json for the queue channel;
the exec exit code for the exec channel), and the two are reported separately
because they are different channels -- the mistake this project retracted twice.

Runs until --secs elapses or --max-fires is reached, then prints the census.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
LOG = r"H:\sotto\_moved\aireplay\_main\heartbeat.log"
# ONE FIRE = ONE PASS. The first version counted LOG LINES matching a broad
# pattern; each pass emits TARGET + PRUNE + WAKE sending within the same second,
# so it reported ~3 fires per pass and a pile of 0.0-minute gaps. That was an
# instrument bug, disclosed in the receipt. A pass is identified by its TARGET
# line, which is written exactly once per pass. Lines from the same second are
# collapsed so a pass can never be counted twice.
FIRE = re.compile(r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\]\s+TARGET\s")
PASS_MARKERS = re.compile(r"WAKE delivered rc=0|WAKE no-op|WAKE FAILED|WAKE QUEUE FAILED|already queued|ABORT|SKIP ")


def ts(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def out(*a) -> None:
    print(*a, flush=True)


def parse_log():
    fires, delivered, refused = [], 0, 0
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as e:
        out(f"UNREADABLE {LOG}: {e!r} -- this census cannot run.")
        return fires, delivered, refused
    seen = set()
    for ln in lines:
        m = re.match(r"\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]", ln)
        if not m:
            continue
        stamp = m.group(1)
        if FIRE.search(ln) and stamp not in seen:
            seen.add(stamp)
            fires.append(stamp)
        if "WAKE delivered rc=0" in ln:
            delivered += 1
        if "rc=4" in ln or "refused" in ln or "already queued" in ln:
            refused += 1
    return fires, delivered, refused


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=int, default=3900)
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--min-fires", type=int, default=20)
    args = ap.parse_args()

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    start_ingress = con.execute(
        "select coalesce(max(accepted_at_ms),0) as m from local_runtime_turn_ingress"
    ).fetchone()["m"]
    out(f"[{ts(int(time.time()*1000))}] CADENCE CENSUS ARMED")
    out(f"  WINDOW: up to {args.secs}s, polling every {args.poll}s")
    out(f"  STOP CONDITION: {args.min_fires} fires observed, or the window ends")
    out(f"  baseline turn_ingress.accepted_at_ms = {ts(start_ingress)}")
    out(f"  log = {LOG}")
    out("  A fire is NOT a delivery. Deliveries are counted structurally, below.\n")

    deadline = time.time() + args.secs
    n = 0
    while time.time() < deadline:
        n += 1
        fires, delivered, refused = parse_log()
        linked = con.execute(
            "select count(*) as c from local_runtime_turn_ingress "
            "where queue_item_ids_json is not null and accepted_at_ms>=?",
            (start_ingress,)).fetchone()["c"]
        out(f"  [{n:03d}] fires={len(fires)} (POP) delivered_rc0={delivered} "
            f"refused={refused} queue_linked_turns_since_baseline={linked}")
        if len(fires) >= args.min_fires:
            out("\nMIN-FIRES REACHED -- census complete.")
            break
        time.sleep(args.poll)

    fires, delivered, refused = parse_log()
    gaps = []
    for a, b in zip(fires, fires[1:]):
        t0 = datetime.strptime(a, "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(b, "%Y-%m-%d %H:%M:%S")
        gaps.append((t1 - t0).total_seconds() / 60.0)

    out("\n=== CADENCE CENSUS ===")
    out(f"POPULATION = {len(fires)} fires in heartbeat.log "
        f"(census of the log, not a sample)")
    out(f"WINDOW = {fires[0] if fires else 'n/a'} -> {fires[-1] if fires else 'n/a'}")
    if gaps:
        gs = sorted(gaps)
        out(f"gap between consecutive fires, minutes: "
            f"min {gs[0]:.2f} median {gs[len(gs)//2]:.2f} max {gs[-1]:.2f}")
        out(f"  distribution: {['%.1f' % g for g in gaps]}")
        over = [g for g in gaps if g > 3.5]
        out(f"  gaps > 3.5 min (the cadence being missed): {len(over)} of {len(gaps)}")
        if over:
            out(f"  worst: {['%.1f' % g for g in sorted(over, reverse=True)[:5]]}")
    else:
        out("gap analysis: UNRESOLVED (fewer than 2 fires in the log)")

    linked = con.execute(
        "select count(*) as c from local_runtime_turn_ingress "
        "where queue_item_ids_json is not null and accepted_at_ms>=?",
        (start_ingress,)).fetchone()["c"]
    out(f"\nDELIVERIES, by channel, since baseline {ts(start_ingress)}:")
    out(f"  queue channel: {linked} queue-linked turns (structural link)")
    out(f"  exec  channel: {delivered} fires with rc=0 (exit code, NOT a turn link)")
    out(f"  refusals     : {refused} fires")
    out("\nAn average gap is not a cadence result. The distribution above is the result;")
    out("a single large gap is the failure a mean would hide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())