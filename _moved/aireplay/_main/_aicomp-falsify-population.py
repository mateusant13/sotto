"""FALSIFIER for the lane census: is the population an artifact of MY filter?

The first census filtered columnar_version = 3. If older rows exist with another
version, the population is wrong and every count built on it is wrong. This
instrument has no such filter, and hunts for the project's sessions under ANY
spelling of the directory (trailing slash, other case, old folder name H:\\aireplay,
and the pre-move name) plus a free-text search of record_json.

A census that cannot say NO is worthless: if it finds sessions the filtered census
did not, it prints RED and exits 2.

Read-only. Exit 0 = no hidden rows. Exit 2 = population was understated.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
PROJECT = r"H:\sotto\_moved\aireplay"

VARIANTS = [
    PROJECT,
    PROJECT + "\\",
    PROJECT.replace("\\", "/"),
    PROJECT.upper(),
    r"H:\aireplay",
    r"H:\aireplay\\",
    r"H:\sotto",
    r"H:\sotto\\",
    r"H:\sotto\_moved",
]


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def main() -> int:
    now = int(dt.datetime.now().timestamp() * 1000)
    con = sqlite3.connect(DB, uri=True)
    hidden = 0
    try:
        print("=" * 78)
        print("A. ALL ROWS, NO columnar_version FILTER -- grouped by version")
        print("=" * 78)
        rows = con.execute(
            "SELECT columnar_version, COUNT(*) FROM local_runtime_sessions "
            "GROUP BY columnar_version ORDER BY columnar_version"
        ).fetchall()
        total = sum(r[1] for r in rows)
        for v, n in rows:
            print(f"  columnar_version={v!s:6} n={n}")
        print(f"  TOTAL rows in table = {total}")

        print()
        print("=" * 78)
        print("B. DIRECTORY SPELLING VARIANTS (exact match, no filter)")
        print("=" * 78)
        for v in VARIANTS:
            n, newest = con.execute(
                "SELECT COUNT(*), MAX(updated_at_ms) FROM local_runtime_sessions "
                "WHERE workspace_dir = ?", (v,)
            ).fetchone()
            marker = "" if n else "   (none)"
            print(f"  n={n:4}  newest={iso(newest)}  {v!r}{marker}")

        print()
        print("=" * 78)
        print("C. LIKE 'aireplay' OR 'sotto' IN workspace_dir (no filter)")
        print("=" * 78)
        rows = con.execute(
            "SELECT workspace_dir, COUNT(*), MAX(updated_at_ms), "
            "       MIN(columnar_version), MAX(columnar_version) "
            "  FROM local_runtime_sessions "
            " WHERE workspace_dir LIKE '%aireplay%' OR workspace_dir LIKE '%sotto%' "
            " GROUP BY workspace_dir ORDER BY 2 DESC"
        ).fetchall()
        if not rows:
            print("  (none)")
        for wdir, n, newest, cvmin, cvmax in rows:
            print(f"  n={n:4} newest={iso(newest)} cv={cvmin}..{cvmax}  {wdir!r}")
            if cvmin != 3:
                hidden += n

        print()
        print("=" * 78)
        print("D. FREE TEXT: record_json / title mentioning this project")
        print("=" * 78)
        rows = con.execute(
            "SELECT session_id, workspace_dir, updated_at_ms, status, columnar_version, title "
            "  FROM local_runtime_sessions "
            " WHERE record_json LIKE '%aireplay%' OR title LIKE '%aireplay%' "
            "    OR record_json LIKE '%_moved%' "
            " GROUP BY workspace_dir"
        ).fetchall()
        if not rows:
            print("  (none)")
        for sid, wdir, upd, status, cv, title in rows:
            print(f"  {sid:34} {iso(upd)} cv={cv} {wdir!r} title={(title or '-')[:30]!r}")
            if cv != 3:
                hidden += 1

        print()
        print("=" * 78)
        print("E. THE 17 POPULATION, FULL TITLE LIST (who are the siblings?)")
        print("=" * 78)
        rows = con.execute(
            "SELECT session_id, updated_at_ms, status, purpose, session_kind, "
            "       title, parent_session_id, runtime "
            "  FROM local_runtime_sessions WHERE workspace_dir = ? "
            " ORDER BY created_at_ms ASC",
            (PROJECT,),
        ).fetchall()
        for (sid, upd, status, purpose, kind, title, parent, runtime) in rows:
            age = (now - upd) / 60000.0
            print(f"  {sid[:20]:20} age={age:6.1f}m {status:9} kind={kind:12} "
                  f"rt={runtime:10} title={(title or '-')[:40]}")

        print()
        if hidden:
            print(f"RED: {hidden} row(s) would have been hidden by the "
                  f"columnar_version=3 filter -> population was understated")
            return 2
        print("GREEN: no rows hidden by the filter; population of 17 stands.")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())