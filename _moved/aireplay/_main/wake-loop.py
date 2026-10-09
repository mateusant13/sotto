#!/usr/bin/env python3
"""wake-loop.py — the thing that guarantees the orchestrator is never idle.

WHY THIS EXISTS
---------------
The owner is away and cannot restart anything. A turn that ends with nothing running is
a dead turn. This watcher is the wake source: when it EXITS, the runtime resumes the
owning conversation. That resume is the whole loop. It does not depend on the cron, on a
restart, or on the owner.

It exits EARLY on the first real event, so every wake is informative rather than a timer.

EVENTS (any one of these ends the watch)
  E1  a queue row for the target session changed state (claimed / delivered / consumed)
  E2  a NEW user-role message row appeared in the target session   <- the real proof
      that something reached the agent as a user message
  E3  a NEW row in local_runtime_v2_cron_runs (the runtime's own scheduler fired)
  E4  heartbeat.log gained a WAKE line since the baseline
  E5  a new lane gate / receipt appeared on disk (a lane landed work)

Trap this script exists to avoid: a text search that matches the auditor's OWN report.
E2 therefore filters on role='user' and on rows NEWER than the baseline id. An
instrument that matches its own output reports PASS while proving nothing.

Usage:
  py -3 wake-loop.py --secs 240 --session <id> [--marker TEXT]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
MAIN = r"H:\sotto\_moved\aireplay\_main"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def out(*a) -> None:
    print(*a, flush=True)


def ro() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=15.0)
    c.row_factory = sqlite3.Row
    return c


def baseline(con, session: str) -> dict:
    msg = con.execute(
        "select coalesce(max(id),0) as m from local_runtime_message_rows "
        "where session_id=? and role='user'", (session,)).fetchone()["m"]
    run = con.execute(
        "select coalesce(max(created_at_ms),0) as m from local_runtime_v2_cron_runs"
    ).fetchone()["m"]
    q = con.execute(
        "select item_id, status, claim_id from local_runtime_queue_items "
        "where session_id=?", (session,)).fetchall()
    log = os.path.join(MAIN, "heartbeat.log")
    nlog = 0
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            nlog = sum(1 for line in fh if "WAKE" in line)
    gates = len(glob.glob(os.path.join(MAIN, "_lane*-gate.ps1")))
    receipts = len(glob.glob(r"H:\sotto\_moved\aireplay\receipts\*.md"))
    return {"max_user_msg_id": msg, "max_cron_run_ms": run,
            "queue": {(r["item_id"][-8:], r["status"], r["claim_id"]) for r in q},
            "wake_lines": nlog, "gates": gates, "receipts": receipts}


def check(con, session: str, base: dict, marker: str | None) -> list[str]:
    ev: list[str] = []

    rows = con.execute(
        "select id, role, source, data_json from local_runtime_message_rows "
        "where session_id=? and role='user' and id>? order by id asc",
        (session, base["max_user_msg_id"])).fetchall()
    for r in rows:
        extra = ""
        if marker and marker in (r["data_json"] or ""):
            extra = f" MARKER-HIT({marker})"
        try:
            txt = str(json.loads(r["data_json"]).get("msg_content"))[:160]
        except (ValueError, TypeError, AttributeError):
            txt = "<payload not JSON-parseable>"
        ev.append(f"E2 user-role msg id={r['id']} source={r['source']} "
                  f"{txt!r}{extra}")

    runs = con.execute(
        "select run_id, cron_id, trigger_source, status, session_id, created_at_ms "
        "from local_runtime_v2_cron_runs where created_at_ms>? order by created_at_ms",
        (base["max_cron_run_ms"],)).fetchall()
    for r in runs:
        ev.append(f"E3 cron run {r['cron_id'][:8]} src={r['trigger_source']} "
                  f"status={r['status']} session={r['session_id']}")

    q = con.execute(
        "select item_id, status, claim_id from local_runtime_queue_items "
        "where session_id=?", (session,)).fetchall()
    nowq = {(r["item_id"][-8:], r["status"], r["claim_id"]) for r in q}
    for k in sorted(nowq - base["queue"]):
        ev.append(f"E1 queue changed -> {k}")
    for k in sorted(base["queue"] - nowq):
        ev.append(f"E1 queue row gone -> {k}")

    log = os.path.join(MAIN, "heartbeat.log")
    if os.path.exists(log):
        with open(log, "r", encoding="utf-8", errors="replace") as fh:
            n = sum(1 for line in fh if "WAKE" in line)
        if n > base["wake_lines"]:
            ev.append(f"E4 heartbeat.log WAKE lines {base['wake_lines']} -> {n}")

    gates = len(glob.glob(os.path.join(MAIN, "_lane*-gate.ps1")))
    receipts = len(glob.glob(r"H:\sotto\_moved\aireplay\receipts\*.md"))
    if gates > base["gates"]:
        ev.append(f"E5 lane gates {base['gates']} -> {gates}")
    if receipts > base["receipts"]:
        ev.append(f"E5 receipts {base['receipts']} -> {receipts}")
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secs", type=int, default=240)
    ap.add_argument("--poll", type=int, default=15)
    ap.add_argument("--session", required=True)
    ap.add_argument("--marker", default=None)
    args = ap.parse_args()

    con = ro()
    base = baseline(con, args.session)
    out(f"[{now()}] WAKE-LOOP ARMED session={args.session} window={args.secs}s "
        f"poll={args.poll}s")
    out(f"[{now()}] baseline: user_msg_id<={base['max_user_msg_id']} "
        f"cron_run<={base['max_cron_run_ms']} queue={len(base['queue'])} "
        f"wake_lines={base['wake_lines']} gates={base['gates']} "
        f"receipts={base['receipts']}")
    out("        POPULATION = that session's user rows + all cron runs + "
        "_main\\_lane*-gate.ps1 + receipts\\*.md")

    deadline = time.time() + args.secs
    n = 0
    events: list[str] = []
    while time.time() < deadline:
        time.sleep(args.poll)
        n += 1
        con = ro()
        ev = check(con, args.session, base, args.marker)
        con.close()
        if ev:
            events.extend(ev)
            out(f"[{now()}] EVENT after {n} samples:")
            for e in events:
                out(f"        {e}")
            out(f"[{now()}] WAKE-LOOP EXIT reason=event events={len(events)}")
            return 0
        out(f"  [{n:02d}] quiet (no event)")

    out(f"[{now()}] WAKE-LOOP EXIT reason=timeout samples={n} "
        f"window={args.secs}s events=0")
    out("        A timeout wake is NOT a failure and NOT proof of health: it "
        "means nothing changed inside the window. State that, do not dress it up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())