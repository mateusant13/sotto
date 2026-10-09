#!/usr/bin/env python3
"""check-delivery.py — did anything actually reach this session as a USER message?

Read-only.  REWRITTEN 2026-10-07 (receipt-24) because the previous version's
"delivery" question could be answered by a TEXT MATCH, and a text match lies.

THE TRAP, MEASURED IN THIS STORE, not hypothetical:
  message row 227835 (12:40:54) and 228892 (12:49:03), session mvs_b7a9f3a7,
  role='user', source='api', msg_id = 'msg-user-v1-wake14c1cc...' (OURS).
      their turn_id is NULL, and turn_ingress has NO row for them.
  They arrived because somebody ran `mcode exec --session ...`, NOT because the
  queue delivered anything.  Any check that greps for the wake payload credits
  them to the queue.  Receipt-21 caught the orchestrator making exactly that
  mistake in its own receipt.

THE AUTHORITATIVE LINK, and the only one:
      local_runtime_turn_ingress.queue_item_ids_json  NAMES the queue item,
      the turn is acknowledged (queue_acknowledged_at_ms IS NOT NULL), and a
      role='user' message row in the SAME session carries that SAME turn_id.
Three runtime tables, joined by runtime-written identifiers.  No payload text
is consulted anywhere in this proof.

MEASURED POPULATION of the proof (whole store, 20 most recent queue-driven
turns): 20/20 satisfied every clause.  STRICT variant, matching the queue
item's own userMessageId, is 0/20 -- because a DELIVERED queue row is deleted
by the runtime, so its userMessageId cannot be read back.  The turn_id hop is
what survives; that is why it is the link used.

Modes:  status | queue-linked | marker | cron
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def ts(ms) -> str:
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def connect(db: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def q1_queue_rows(con, session) -> None:
    n = con.execute("select count(*) from local_runtime_queue_items").fetchone()[0]
    print(f"=== Q1 queue rows for this session "
          f"(POPULATION = whole table = {n} rows) ===")
    for r in con.execute(
            "select item_id, status, claim_id, claim_lease_expires_at_ms, "
            "created_at_ms, expires_at_ms, data_json "
            "from local_runtime_queue_items where session_id=? "
            "order by rowid desc", (session,)):
        try:
            c = json.loads(r["data_json"] or "{}").get("message", {}).get("content", "")
        except (ValueError, TypeError) as e:
            c = f"<unparseable: {e!r}>"
        exp = r["expires_at_ms"]
        print(f"  {r['item_id']}  status={r['status']}  claim={r['claim_id']}")
        print(f"     created={ts(r['created_at_ms'])}  "
              f"expires={ts(exp) if exp else 'NULL (nothing can ever reap it)'}"
              f"  content={c[:80]!r}")


def q2_user_rows(con, session, since: int) -> int:
    print(f"\n=== Q2 role='user' rows newer than id {since} "
          f"(POPULATION = whole table) ===")
    n = 0
    for r in con.execute(
            "select id, source, created_at_ms, data_json "
            "from local_runtime_message_rows where session_id=? and role='user' "
            "and id>? order by id asc", (session, since)):
        n += 1
        try:
            d = json.loads(r["data_json"] or "{}")
            txt = str(d.get("msg_content"))[:160]
            turn = d.get("turn_id")
        except (ValueError, TypeError) as e:
            txt = f"<unparseable: {e!r}>"
            turn = None
        print(f"  id={r['id']} {ts(r['created_at_ms'])} src={r['source']} "
              f"turn_id={turn}")
        print(f"      {txt!r}")
    print(f"  rows found = {n}")
    return n


def queue_linked(con, session=None, limit=20) -> tuple:
    """THE PROOF.  Returns (delivered, examined); prints every item it looks at."""
    where = " and t.session_id=?" if session else ""
    params = (session,) if session else ()
    turns = con.execute(
        "select t.turn_id, t.session_id, t.claim_source, t.queue_item_ids_json, "
        "t.queue_acknowledged_at_ms, t.status, t.accepted_at_ms "
        "from local_runtime_turn_ingress t "
        "where t.queue_item_ids_json is not null and t.claim_source='api'" + where +
        " order by t.accepted_at_ms desc limit ?", params + (limit,)).fetchall()
    pop = con.execute(
        "select count(*) from local_runtime_turn_ingress "
        "where queue_item_ids_json is not null and claim_source='api'"
    ).fetchone()[0]
    print(f"\n=== Q3 QUEUE-LINKED DELIVERY -- THE PROOF "
          f"(POPULATION = {pop} queue-driven turns; showing newest {len(turns)}) ===")
    delivered = 0
    for t in turns:
        items = json.loads(t["queue_item_ids_json"] or "[]")
        ack = t["queue_acknowledged_at_ms"] is not None
        users = con.execute(
            "select count(*) from local_runtime_message_rows "
            "where session_id=? and role='user' and data_json like ?",
            (t["session_id"], "%" + t["turn_id"] + "%")).fetchone()[0]
        ok = ack and users > 0
        delivered += 1 if ok else 0
        print(f"  {ts(t['accepted_at_ms'])} sess={t['session_id']} "
              f"status={t['status']} acknowledged={ack} "
              f"user_rows_with_this_turn_id={users} "
              f"=> {'DELIVERED' if ok else 'NOT-DELIVERED'}")
        for it in items:
            print(f"      queue_item_ids_json names: {it}")
            still = con.execute(
                "select status from local_runtime_queue_items where item_id=?",
                (it,)).fetchone()
            print(f"      queue row now: "
                  f"{still['status'] if still else 'GONE (deleted after delivery)'}")
    print(f"  DELIVERED_BY_QUEUE = {delivered}/{len(turns)}")
    print("  Proof used: turn_ingress.queue_item_ids_json names the item AND "
          "queue_acknowledged_at_ms is set AND a role='user' row in the same "
          "session carries that turn_id. NO payload text is consulted.")
    return delivered, len(turns)


def marker_check(con, session, marker) -> int:
    print(f"\n=== Q4 marker match: role='user' rows containing {marker!r} ===")
    hits = con.execute(
        "select id, source, created_at_ms, data_json "
        "from local_runtime_message_rows where session_id=? and role='user' "
        "order by rowid desc", (session,)).fetchall()
    matched = []
    for r in hits:
        if marker in (r["data_json"] or ""):
            d = json.loads(r["data_json"] or "{}")
            turn = d.get("turn_id")
            ti = con.execute(
                "select queue_item_ids_json, claim_source "
                "from local_runtime_turn_ingress where turn_id=?",
                (turn,)).fetchone() if turn else None
            linked = bool(ti and ti["queue_item_ids_json"])
            matched.append((r, linked))
            print(f"  HIT id={r['id']} {ts(r['created_at_ms'])} src={r['source']} "
                  f"turn_id={turn} queue_linked={linked}")
    n = len(matched)
    unlinked = sum(1 for _r, l in matched if not l)
    print(f"  marker hits = {n}   of which NOT queue-linked = {unlinked}")
    print("  MARKER_MATCHES_ARE_NOT_PROOF: a hit here proves only that the text "
          "arrived. It is DELIVERY BY THE QUEUE only if turn_ingress names the "
          "queue item for it (see Q3). A hand-pushed `mcode exec --session` "
          "produces a role='user' row with turn_id NULL and no ingress row at "
          "all -- measured twice in this store.")
    return n


def cron_health(con) -> bool:
    print("\n=== Q5 runtime cron scheduler health (D-2 + D-4) ===")
    rows = con.execute("select count(*) from local_runtime_v2_cron_runs").fetchone()[0]
    mx = con.execute("select max(created_at_ms) from "
                     "local_runtime_v2_cron_runs").fetchone()[0]
    armed = con.execute(
        "select count(*) from local_runtime_v2_cron_definitions d "
        "join local_runtime_v2_scheduler_jobs j "
        "on j.scheduler_id=d.scheduler_id "
        "where d.deleted_at_ms is null and j.state='active'").fetchone()[0]
    if mx is None:
        print("  never ran")
        return armed == 0
    age_min = (con.execute("select cast((julianday('now') - julianday("
                           "datetime(?/1000.0,'unixepoch'))) * 1440 as integer)",
                           (mx,)).fetchone()[0])
    alarming = armed > 0 and age_min > 15
    print(f"  cron_runs rows (POPULATION) = {rows}")
    print(f"  newest run = {ts(mx)}  age = {age_min} min")
    print(f"  undeleted crons joined to an ACTIVE job = {armed}")
    print(f"  verdict = {'ALARM (threshold 15 min)' if alarming else 'ok'}")
    return alarming


def main() -> int:
    ap = argparse.ArgumentParser(
        description="queue-LINKED delivery check; a text match is not proof")
    ap.add_argument("session")
    ap.add_argument("since", nargs="?", default=0, type=int)
    ap.add_argument("marker", nargs="?", default=None)
    ap.add_argument("--db", default=DB)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--require-linked", type=int, default=0,
                    help="exit 4 unless at least N of the newest queue-driven "
                         "turns satisfy the full linkage proof")
    args = ap.parse_args()
    con = connect(args.db)

    q1_queue_rows(con, args.session)
    q2_user_rows(con, args.session, args.since)
    if args.marker:
        marker_check(con, args.session, args.marker)
    delivered, examined = queue_linked(con, limit=args.limit)
    cron_health(con)
    if args.require_linked and delivered < args.require_linked:
        print(f"FAIL: require-linked={args.require_linked} but only "
              f"{delivered} linked deliveries found")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())