#!/usr/bin/env python3
"""Diagnose (and optionally repair) a local_runtime_queue_items row.

READ-ONLY by default. Every count printed here carries its POPULATION and its
WINDOW, because the previous instrument counted its own output.

Why this exists: a hand-written row in the runtime queue was reported back as
  "Queue row is corrupt: <sessionId>/<itemId>"
which blocks "continue the latest conversation".  Diagnosing needs the exact
schema + a known-good reference row, so this script prints both.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
TARGET_SESSION = "mvs_a00662bff55242cb9b56c0f1165bdad7"
TARGET_ITEM = "queue_ec7ae0a0-d5ad-44a4-9d53-7a824dc2d162"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def out(*a) -> None:
    print(*a, flush=True)


def tables(con) -> list[str]:
    rows = con.execute(
        "select name from sqlite_master where type='table' order by name"
    ).fetchall()
    return [r[0] for r in rows]


def schema(con, name: str) -> str:
    row = con.execute(
        "select sql from sqlite_master where type in ('table','index') "
        "and tbl_name=? order by name",
        (name,),
    ).fetchall()
    if not row:
        return f"(no schema for {name})"
    return "\n".join((r[0] or "(null sql)").strip() for r in row)


def row_as_dict(con, name: str, where: str, params: tuple) -> dict:
    cur = con.execute(f"select * from {name} where {where}", params)
    cols = [d[0] for d in cur.description]
    hit = cur.fetchone()
    if hit is None:
        return {}
    return dict(zip(cols, hit))


def render(d: dict) -> str:
    if not d:
        return "(no row)"
    lines = []
    for k, v in d.items():
        s = repr(v)
        if len(s) > 400:
            s = s[:400] + f"...<truncated, {len(s)} chars total>"
        lines.append(f"    {k:<26} = {s}")
    return "\n".join(lines)


def inspect(con) -> None:
    out(f"[{now()}] OPEN read-only :: {DB}")
    names = tables(con)
    out(f"  tables containing 'queue': {[n for n in names if 'queue' in n]}")

    out("\n=== SCHEMA local_runtime_queue_items ===")
    out(schema(con, "local_runtime_queue_items"))

    out("\n=== STATUS CENSUS (queue table) ===")
    try:
        rows = con.execute(
            "select status, count(*) from local_runtime_queue_items group by status"
        ).fetchall()
        out(f"  POPULATION = all rows in local_runtime_queue_items")
        for st, n in rows:
            out(f"    status={st!r:<16} n={n}")
    except Exception as e:  # noqa: BLE001
        out(f"  census failed: {e!r}")

    out(f"\n=== TARGET ROW ({TARGET_ITEM}) ===")
    d = row_as_dict(con, "local_runtime_queue_items", "item_id=?", (TARGET_ITEM,))
    out(render(d))

    out("\n=== REFERENCE ROWS (most recent 6, any session) ===")
    cur = con.execute(
        "select * from local_runtime_queue_items order by rowid desc limit 6"
    )
    cols = [x[0] for x in cur.description]
    out(f"  columns ({len(cols)}): {cols}")
    for i, hit in enumerate(cur.fetchall()):
        out(f"  --- ref[{i}] ---")
        out(render(dict(zip(cols, hit))))

    out("\n=== MESSAGE TABLES ===")
    msg_tables = [n for n in names if "message" in n]
    out(f"  {msg_tables}")
    for t in msg_tables:
        out(f"\n--- schema {t} ---")
        out(schema(con, t)[:2500])

    out(f"\n=== SESSION {TARGET_SESSION} : last 6 user rows ===")
    mt = "local_runtime_message_rows"
    try:
        cur = con.execute(
            f"select * from {mt} where session_id=? and role='user' "
            "order by rowid desc limit 6",
            (TARGET_SESSION,),
        )
        cols = [x[0] for x in cur.description]
        out(f"  columns ({len(cols)}): {cols}")
        for i, hit in enumerate(cur.fetchall()):
            out(f"  --- user[{i}] ---")
            out(render(dict(zip(cols, hit))))
    except Exception as e:  # noqa: BLE001
        out(f"  read failed: {e!r}")


def delete_row(con, item_id: str) -> int:
    cur = con.execute(
        "delete from local_runtime_queue_items where item_id=?", (item_id,)
    )
    con.commit()
    return cur.rowcount


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--delete", metavar="ITEM_ID",
                    help="delete one queue row (the corrupt one)")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    if args.delete:
        n = delete_row(con, args.delete)
        out(f"[{now()}] DELETE item_id={args.delete} rowcount={n}")
        left = con.execute(
            "select count(*) from local_runtime_queue_items where item_id=?",
            (args.delete,),
        ).fetchone()[0]
        out(f"  rows remaining with that item_id = {left}  (POPULATION=1 item, "
            f"WINDOW=now)")
        return 0 if left == 0 else 1
    inspect(con)
    return 0


if __name__ == "__main__":
    sys.exit(main())