#!/usr/bin/env python3
"""Triage the queue row that the runtime called corrupt, and find the
runtime's own cron store.

Two questions, both measured, never inferred:

  Q1  Which key(s) make a queued row INVALID?  Answer by diffing the
      hand-written row against a row the runtime itself wrote, key by key.
      Population = the 3 queued rows + the newest delivered rows.

  Q2  Does the runtime own a cron store, and what is its shape?
      Population = every table name in runtime-state.sqlite.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
BROKEN = "queue_ec7ae0a0-d5ad-44a4-9d53-7a824dc2d162"


def now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%H:%M:%S")


def out(*a) -> None:
    print(*a, flush=True)


def walk_diff(a, b, prefix="") -> list[str]:
    """Report keys present in `a` (broken) that are missing/different in `b`
    (known-good), one line each.  Returns human lines, never raises."""
    lines: list[str] = []
    if not isinstance(a, dict) or not isinstance(b, dict):
        if a != b:
            lines.append(f"{prefix or '<root>'}: broken={a!r} good={b!r}")
        return lines
    for k in sorted(a.keys()):
        if k not in b:
            lines.append(f"{prefix}{k}: ONLY IN BROKEN = {a[k]!r}")
            continue
        av, bv = a[k], b[k]
        if isinstance(av, dict) and isinstance(bv, dict):
            lines.extend(walk_diff(av, bv, f"{prefix}{k}."))
        elif av != bv:
            lines.append(f"{prefix}{k}: broken={av!r} good={bv!r}")
    return lines


def main() -> int:
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    out(f"[{now()}] READ-ONLY :: {DB}")

    # ---------- Q2 : full table census ----------
    names = [r[0] for r in con.execute(
        "select name from sqlite_master where type='table' order by name")]
    out(f"\n=== ALL TABLES  (POPULATION = {len(names)} tables) ===")
    cronish = [n for n in names if any(k in n.lower() for k in
               ("cron", "sched", "timer", "job", "task", "wake"))]
    out(f"  cron/schedule-ish: {cronish or 'NONE'}")
    for n in names:
        cnt = con.execute(f"select count(*) from {n}").fetchone()[0]
        out(f"    {n:<52} rows={cnt}")

    # ---------- Q1 : the corrupt row vs a real one ----------
    out("\n=== Q1: BROKEN ROW vs RUNTIME-WRITTEN ROW ===")
    cur = con.execute(
        "select item_id, session_id, status, source, client_request_id, "
        "dedupe_key, expires_at_ms, claim_id, routing_fingerprint, data_json "
        "from local_runtime_queue_items order by rowid desc limit 12")
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    broken = next((r for r in rows if r["item_id"] == BROKEN), None)
    out(f"  broken row found in last 12: {bool(broken)}")
    if not broken:
        c = con.execute(
            "select item_id, session_id, status, source, client_request_id, "
            "dedupe_key, expires_at_ms, claim_id, routing_fingerprint, data_json "
            "from local_runtime_queue_items where item_id=?", (BROKEN,)).fetchone()
        if c is None:
            out(f"  BROKEN ITEM NOT IN TABLE ANYWHERE: {BROKEN}")
            return 1
        broken = dict(zip(cols, c))

    good = next((r for r in rows
                 if r["item_id"] != BROKEN
                 and r["routing_fingerprint"]), None)
    out(f"  reference (runtime-written) row: {good['item_id'] if good else None}")

    out("\n-- column-level diff --")
    for k in cols:
        if k == "data_json":
            continue
        bv, gv = broken[k], (good[k] if good else None)
        flag = "SAME" if bv == gv else "DIFF"
        out(f"  [{flag}] {k:<22} broken={bv!r}")
        if flag == "DIFF":
            out(f"          {'good':<22}      ={gv!r}")

    bj = json.loads(broken["data_json"])
    out("\n-- data_json key diff (broken vs good) --")
    if good:
        gj = json.loads(good["data_json"])
        for line in walk_diff(bj, gj):
            out(f"  {line}")
        out("\n-- keys the runtime wrote that the broken row LACKS --")
        for k in sorted(gj.keys()):
            if k not in bj:
                out(f"  MISSING {k} = {gj[k]!r}")
        out("\n-- message-level diff --")
        gm = gj.get("message") or {}
        bm = bj.get("message") or {}
        for line in walk_diff(bm, gm, "message."):
            out(f"  {line}")
        for k in sorted(gm.keys()):
            if k not in bm:
                out(f"  MISSING message.{k} = {gm[k]!r}")

    out("\n=== FULL data_json of the BROKEN row ===")
    out(json.dumps(bj, indent=2, ensure_ascii=False))
    if good:
        out("\n=== FULL data_json of the GOOD row (template to copy) ===")
        out(json.dumps(good["data_json"] and json.loads(good["data_json"]),
                       indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())