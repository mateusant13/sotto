"""Census of I:\\!aicompanion -- the project NAMED after this seat.

Purpose: test the owner's premise ("17 dead lanes belonged to this project")
against BOTH candidate projects, and print them side by side so the choice is
evidence, not naming.

The seat is named 'aicompanion' and a real repo I:\\!aicompanion exists. But this
session's own workspace_dir is H:\\sotto\\_moved\\aireplay. Both are censused here.

Read-only. Exit 2 = could not verify.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
MINE = r"H:\sotto\_moved\aireplay"
DECOY = r"I:\!aicompanion"
DEAD_AFTER_MIN = 45

COLS = ("session_id, updated_at_ms, status, agent_name, parent_session_id, "
        "purpose, session_kind, archived, workspace_dir, title, created_at_ms")


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def classify(status, upd, now):
    age = (now - upd) / 60000.0
    live = (status or "").lower() in {"running", "active", "started"}
    if live and age <= DEAD_AFTER_MIN:
        return "ALIVE", age
    if age <= DEAD_AFTER_MIN:
        return "RECENT", age
    if live:
        return "STALE", age
    return "DEAD", age


def census(con, wdir, now, verbose=False):
    rows = con.execute(
        f"SELECT {COLS} FROM local_runtime_sessions WHERE workspace_dir = ? "
        "ORDER BY updated_at_ms DESC", (wdir,)).fetchall()
    tally, dead_rows = {}, []
    for r in rows:
        m = dict(zip(COLS.split(", "), r))
        v, age = classify(m["status"], m["updated_at_ms"], now)
        tally[v] = tally.get(v, 0) + 1
        if v in {"DEAD", "STALE"}:
            dead_rows.append((m["session_id"], v, m["status"], m["updated_at_ms"],
                              m["parent_session_id"], m["title"], m["archived"]))
    print(f"--- {wdir}")
    print(f"    population = {len(rows)}   window = {DEAD_AFTER_MIN} min")
    print(f"    tally      = {dict(sorted(tally.items()))}")
    print(f"    newest     = {iso(max((r[1] for r in rows), default=0))}")
    print(f"    DEAD+STALE = {len(dead_rows)}")
    by_status: dict[str, int] = {}
    for _, _, st, _, _, _, _ in dead_rows:
        by_status[st or "-"] = by_status.get(st or "-", 0) + 1
    print(f"    dead-by-status = {dict(sorted(by_status.items(), key=lambda kv: -kv[1]))}")
    if verbose:
        for sid, v, st, upd, par, title, arch in dead_rows[:60]:
            root = "ROOT" if par is None else f"<-{par[:12]}"
            print(f"      {sid} {v:5} {st:12} {iso(upd)} {root:16} "
                  f"arch={arch} {(title or '-')[:40]}")
    return len(rows), len(dead_rows)


def main() -> int:
    now = int(dt.datetime.now().timestamp() * 1000)
    con = sqlite3.connect(DB, uri=True)
    try:
        print(f"now = {iso(now)}   death window = {DEAD_AFTER_MIN} min")
        print()
        print("=" * 78)
        print("SIDE BY SIDE: seat name vs session binding")
        print("=" * 78)
        p1, d1 = census(con, MINE, now, verbose=True)
        print()
        p2, d2 = census(con, DECOY, now, verbose=False)
        print()
        print("=" * 78)
        print("VERDICT ON THE OWNER'S PREMISE (17 dead lanes 'belonged to this project')")
        print("=" * 78)
        print(f"  {MINE}")
        print(f"    population={p1}  dead+stale={d1}   -> {'MATCHES 17' if d1 == 17 else 'does NOT match 17'}")
        print(f"  {DECOY}")
        print(f"    population={p2}  dead+stale={d2}   -> {'MATCHES 17' if d2 == 17 else 'does NOT match 17'}")
        print()
        print("  My seat is bound by workspace_dir, NOT by the agent name.")
        print(f"  I:\\!aicompanion is a DIFFERENT repo (own AGENTS.md + package.json).")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())