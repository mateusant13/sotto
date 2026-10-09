"""Empirical probe for cron DELIVERY (lane/deliver).

Read-only census of local_runtime_v2_cron_runs in the 3.4 GB runtime store.
Prints rows; never trusts a count it has not printed.
"""
import sqlite3
import sys
import time

DB = r"file:C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite?mode=ro"
TABLE = "local_runtime_v2_cron_runs"


def connect():
    return sqlite3.connect(DB, uri=True, timeout=30)


def census(label):
    con = connect()
    con.row_factory = sqlite3.Row
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
        n = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
        mx = con.execute(f"SELECT MAX(created_at_ms) FROM {TABLE}").fetchone()[0]
        print(f"[{label}] journal_mode={mode} count={n} max_created_at_ms={mx}")
        if mx:
            print(f"    max_as_utc={time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(mx/1000))}Z")
        return n, mx
    finally:
        con.close()


def schema():
    con = connect()
    try:
        print("== pragma table_info ==")
        for r in con.execute(f"PRAGMA table_info({TABLE})"):
            print("   ", tuple(r))
        sql = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
        ).fetchone()
        print("== DDL ==")
        print(sql[0] if sql else "<none>")
    finally:
        con.close()


def dump_rows(limit=5, newest=True):
    con = connect()
    con.row_factory = sqlite3.Row
    try:
        order = "DESC" if newest else "ASC"
        rows = con.execute(
            f"SELECT * FROM {TABLE} ORDER BY created_at_ms {order}, run_id {order} LIMIT ?",
            (limit,),
        ).fetchall()
        print(f"== {len(rows)} rows ({order}) ==")
        cols = rows[0].keys() if rows else []
        for i, r in enumerate(rows):
            print(f"--- row {i} ---")
            for c in cols:
                v = r[c]
                s = repr(v)
                if len(s) > 300:
                    s = s[:300] + f"...<len={len(str(v))}>"
                print(f"    {c} = {s}")
        return rows
    finally:
        con.close()


def status_breakdown():
    con = connect()
    try:
        print("== status x trigger_source ==")
        for r in con.execute(
            f"SELECT status, trigger_source, COUNT(*) c FROM {TABLE} GROUP BY 1,2 ORDER BY 3 DESC"
        ):
            print("   ", tuple(r))
        print("== receipt fields ==")
        for r in con.execute(
            f"""SELECT COUNT(*) total,
                       SUM(session_id IS NOT NULL) has_session,
                       SUM(delivered_at_ms IS NOT NULL) has_delivered,
                       SUM(status='delivered') delivered,
                       SUM(status='failed') failed,
                       SUM(status='pending') pending
                FROM {TABLE}"""
        ):
            print("   ", tuple(r))
    finally:
        con.close()


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "schema"):
        schema()
    if what in ("all", "census"):
        census("census")
    if what in ("all", "rows"):
        dump_rows()
    if what in ("all", "breakdown"):
        status_breakdown()