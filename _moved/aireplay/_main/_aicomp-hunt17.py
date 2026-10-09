"""Where could the owner's '17 aicompanion lanes' come from? Hunt the number.

The premise must not be dismissed on a hunch -- it must be located or declared
UNLOCATED. Tests, all read-only:
  T1 root-lane count of each candidate (the fence killed ROOTS, per the record)
  T2 lanes dead on a specific day (the fence incident day vs today)
  T3 quarantine / queue-migration tables that could record a fence event
  T4 sessions carrying a revival/quarantine marker in purpose or status
Exit 2 = could not verify.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
MINE = r"H:\sotto\_moved\aireplay"
DECOY = r"I:\!aicompanion"


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def main() -> int:
    now = int(dt.datetime.now().timestamp() * 1000)
    con = sqlite3.connect(DB, uri=True)
    try:
        print("T1 -- ROOT-lane counts (a fence that killed lanes would show roots)")
        for w in (MINE, DECOY):
            n, newest = con.execute(
                "SELECT COUNT(*), MAX(updated_at_ms) FROM local_runtime_sessions "
                "WHERE workspace_dir=? AND parent_session_id IS NULL", (w,)).fetchone()
            print(f"    roots={n:4} newest={iso(newest)}  {w}")

        print()
        print("T2 -- dead lanes per DAY (fence-day clustering)")
        rows = con.execute(
            "SELECT workspace_dir, DATE(updated_at_ms/1000,'unixepoch','localtime') d, "
            "       COUNT(*) FROM local_runtime_sessions "
            " WHERE workspace_dir IN (?,?) AND updated_at_ms < ? "
            " GROUP BY workspace_dir, d ORDER BY workspace_dir, d",
            (MINE, DECOY, now - 45 * 60_000)).fetchall()
        cur = None
        for w, d, n in rows:
            if w != cur:
                print(f"    {w}")
                cur = w
            print(f"      {d}  {n:4} dead lanes")

        print()
        print("T3 -- quarantine / migration tables")
        for t in ("local_runtime_queue_migration_quarantine",
                  "local_runtime_v2_agent_legacy_history_notice_repair"):
            try:
                n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                print(f"    {t}: {n} rows")
                if n:
                    for r in con.execute(f"SELECT * FROM {t} LIMIT 5"):
                        print(f"      {r}")
            except sqlite3.Error as exc:
                print(f"    {t}: FAIL {exc}")

        print()
        print("T4 -- any session anywhere whose purpose/title mentions revive|quarantine|fence")
        rows = con.execute(
            "SELECT session_id, workspace_dir, updated_at_ms, status, purpose, title "
            "  FROM local_runtime_sessions "
            " WHERE LOWER(COALESCE(purpose,'')) LIKE '%reviv%' "
            "    OR LOWER(COALESCE(purpose,'')) LIKE '%quarantin%' "
            "    OR LOWER(COALESCE(title,'')) LIKE '%reviv%' "
            "    OR LOWER(COALESCE(status,'')) LIKE '%quarantin%' "
            " LIMIT 40").fetchall()
        if not rows:
            print("    (none)")
        for sid, w, upd, st, pur, title in rows:
            print(f"    {sid} {iso(upd)} {st:12} {w} {(pur or '-')[:44]} {(title or '-')[:24]}")

        print()
        print("T5 -- THE QUARANTINE ID: does it exist, and where?")
        q = "mvs_19e3d42432374e52a03ba256db70a8b5"
        row = con.execute(
            "SELECT workspace_dir, updated_at_ms, status, title, agent_name "
            "  FROM local_runtime_sessions WHERE session_id=?", (q,)).fetchone()
        if row is None:
            print(f"    {q}: NOT in the v2 store (may be a pre-v2 id)")
        else:
            age = (now - row[1]) / 60000.0
            print(f"    found: {row[0]} updated={iso(row[1])} age={age:.1f}min "
                  f"status={row[2]} title={row[3]!r} agent={row[4]}")
            print(f"    => NEVER TOUCH, per the absolute-quarantine constraint.")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())