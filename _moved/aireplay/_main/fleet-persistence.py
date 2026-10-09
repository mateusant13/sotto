#!/usr/bin/env python3
"""fleet-persistence.py — do dispatched subagent sessions survive their turn?

WHY
---
A woken agent reported, unprompted, that the fleet it had dispatched was dead on
arrival: "encontrei 0 vivas ... Cinco canceled". That report was NOT verified
against the store. This reads the store directly and counts, per parent session,
how many child sessions exist and what state they are in.

POPULATION and WINDOW are printed for every count. A claim of "0 alive" is
checked against the sessions table, not against a narrative.

Read-only.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"

PARENTS = {
    "mvs_a00662bff55242cb9b56c0f1165bdad7": "the IDLE session (reported 0 alive)",
    "mvs_b7a9f3a7db404912b32d28fc11b83645": "this session (the orchestrator)",
}


def out(*a) -> None:
    print(*a, flush=True)


def ts(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).astimezone()
    out(f"WINDOW = {now.strftime('%H:%M:%S')} local")
    out("POPULATION = every row in local_runtime_sessions for each parent listed "
        "below; counts are census, not a sample.\n")

    for parent, why in PARENTS.items():
        rows = con.execute(
            "select session_id, status, purpose, created_at_ms, updated_at_ms, "
            "archived from local_runtime_sessions where parent_session_id=? "
            "order by created_at_ms asc", (parent,)).fetchall()
        by_status: dict[str, int] = {}
        for r in rows:
            k = f"{r['status']}/archived={r['archived']}"
            by_status[k] = by_status.get(k, 0) + 1
        out(f"--- parent {parent}  ({why})")
        out(f"    child sessions in POPULATION = {len(rows)}")
        if not rows:
            out("    (none)")
        for k, n in sorted(by_status.items()):
            out(f"      {k:<34} n={n}")
        if rows:
            out(f"      oldest child created {ts(rows[0]['created_at_ms'])}, "
                f"newest {ts(rows[-1]['created_at_ms'])}")
            live = [r for r in rows if r["status"] == "started"]
            out(f"      status='started' (the live shape) = {len(live)}")
            if live:
                out(f"      newest still-started: "
                    f"{ts(max(r['updated_at_ms'] for r in live))}")
        out()

    out("HOW TO READ THIS")
    out("  A child with status 'started' and an OLD updated_at_ms is a lane that")
    out("  stopped being updated when its parent's turn ended -- i.e. it did not")
    out("  persist. Compare the newest updated_at_ms against the parent's own turn")
    out("  boundary before calling anything dead or alive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())