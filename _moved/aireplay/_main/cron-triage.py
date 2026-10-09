#!/usr/bin/env python3
"""Read the runtime's OWN cron store and decide whether a 3-minute cron can
deliver a message into a live session like the owner does.

Tables: local_runtime_v2_cron_definitions, local_runtime_v2_scheduler_jobs,
        local_runtime_v2_cron_runs

Everything printed carries POPULATION + WINDOW.  Read-only.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def ms(v):
    if v in (None, ""):
        return "None"
    try:
        return datetime.fromtimestamp(int(v) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return repr(v)


def out(*a) -> None:
    print(*a, flush=True)


def cols_of(con, table):
    return [c[1] for c in con.execute(f"PRAGMA table_info({table})")]


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out(f"[{now()}] READ-ONLY :: {DB}")

    for t in ("local_runtime_v2_cron_definitions",
              "local_runtime_v2_scheduler_jobs",
              "local_runtime_v2_cron_runs"):
        out(f"\n=== SCHEMA {t} ===")
        out(f"  columns: {cols_of(con, t)}")
        out("  " + (con.execute(
            "select sql from sqlite_master where name=?", (t,)).fetchone()[0] or "").replace("\n", "\n  "))

    out("\n=== CRON DEFINITIONS (POPULATION = whole table) ===")
    dcols = cols_of(con, "local_runtime_v2_cron_definitions")
    out(f"  columns: {dcols}")
    for r in con.execute("select * from local_runtime_v2_cron_definitions"):
        d = dict(r)
        keep = {k: v for k, v in d.items()
                if not (isinstance(v, str) and len(v) > 160)}
        dropped = [k for k, v in d.items()
                   if isinstance(v, str) and len(v) > 160]
        out(f"  - {keep}")
        for k in dropped:
            s = d[k]
            out(f"      .{k}[{len(s)}b] = {s[:200]}...")

    out("\n=== RUNS PER CRON (POPULATION = all 1442 runs) ===")
    rcols = cols_of(con, "local_runtime_v2_cron_runs")
    out(f"  columns: {rcols}")
    idcol = "cron_id" if "cron_id" in rcols else rcols[1]
    tscol = next((c for c in ("started_at_ms", "created_at_ms", "fired_at_ms",
                              "run_at_ms", "scheduled_at_ms") if c in rcols), None)
    for r in con.execute(
            f"select {idcol} as cid, count(*) as n"
            + (f", max({tscol}) as last" if tscol else "")
            + " from local_runtime_v2_cron_runs group by cid order by n desc"):
        d = dict(r)
        out(f"  {d['cid']}  n={d['n']}  last={ms(d.get('last'))}")

    out("\n=== LAST 5 RUNS, full rows ===")
    order = tscol or "rowid"
    for r in con.execute(
            f"select * from local_runtime_v2_cron_runs order by {order} desc limit 5"):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 220:
                d[k] = v[:220] + f"...<{len(v)}b>"
        out(f"  - {d}")

    out("\n=== SCHEDULER JOBS (POPULATION = whole table) ===")
    for r in con.execute("select * from local_runtime_v2_scheduler_jobs"):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 220:
                d[k] = v[:220] + f"...<{len(v)}b>"
        out(f"  - {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())