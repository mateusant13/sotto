#!/usr/bin/env python3
"""Measure the candidate delivery arms before writing the gate, so no arm is
invented on hope.  Read-only."""
import json
import sqlite3
import sys
import time
import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S")
    except Exception:
        return repr(ms)


turns = con.execute(
    "select t.turn_id, t.session_id, t.claim_source, t.queue_item_ids_json, "
    "t.queue_acknowledged_at_ms, t.status, t.accepted_at_ms, t.completed_at_ms "
    "from local_runtime_turn_ingress t where t.queue_item_ids_json is not null "
    "and t.claim_source='api' order by t.accepted_at_ms desc limit 20").fetchall()
print(f"POP queue-driven turns (claim_source='api' AND queue_item_ids_json IS NOT NULL), newest 20 of "
      f"{con.execute('select count(*) from local_runtime_turn_ingress where queue_item_ids_json is not null and claim_source=%s' % chr(39) + 'api' + chr(39)).fetchone()[0]}")

strict = 0
loose = 0
for t in turns:
    items = json.loads(t["queue_item_ids_json"] or "[]")
    qrow = con.execute("select item_id, session_id, data_json from "
                       "local_runtime_queue_items where item_id=?",
                       (items[0],)).fetchone()
    msg_id = None
    if qrow is not None:
        msg_id = json.loads(qrow["data_json"] or "{}").get("userMessageId")
    # a user row in the SAME session carrying that exact msg_id
    hit = con.execute("select count(*) from local_runtime_message_rows "
                      "where session_id=? and role='user' and data_json like ?",
                      (t["session_id"], "%" + (msg_id or "@@none@@") + "%")).fetchone()[0] if msg_id else 0
    # a user row in the same session carrying this turn_id
    turnhit = con.execute("select count(*) from local_runtime_message_rows "
                          "where session_id=? and role='user' and data_json like ?",
                          (t["session_id"], "%" + t["turn_id"] + "%")).fetchone()[0]
    ack = t["queue_acknowledged_at_ms"] is not None
    if hit:
        strict += 1
    if hit or turnhit:
        loose += 1
    print(f"  {ts(t['accepted_at_ms'])} {t['status']:<9} ack={ack!s:<5} "
          f"queue_row={'PRESENT' if qrow else 'GONE(deleted)'} "
          f"user_rows_by_msg_id={hit} user_rows_by_turn_id={turnhit} "
          f"item={items[0][:20]}")

print(f"\nSTRICT (user row carries the queue item's own userMessageId): {strict}/20")
print(f"LOOSE  (user row carries the msg_id OR the turn_id):            {loose}/20")

print("\n=== our own injected rows (client_request_id LIKE 'minimax-code_hb_%') ===")
hb = con.execute("select item_id, session_id, status, claim_id, created_at_ms "
                 "from local_runtime_queue_items where client_request_id "
                 "like 'minimax-code_hb_%' order by rowid").fetchall()
print("POP still present:", len(hb))
for r in hb:
    print(f"  {r['item_id'][:24]} sess={r['session_id'][-8:]} status={r['status']} "
          f"claim={r['claim_id']} created={ts(r['created_at_ms'])}")
print("  (rows pruned/deleted leave no trace here; the message-row search below does)")

print("\n=== CONTROL probe: a role='user' text match whose turn is NOT queue-linked ===")
unlinked = con.execute(
    "select m.id, m.session_id, m.created_at_ms, m.data_json "
    "from local_runtime_message_rows m where m.role='user' "
    "and m.source='api' and m.data_json like '%msg-user-v1-wake%' "
    "order by m.id desc limit 5").fetchall()
print("POP role='user' rows carrying a wake-minted msg_id:", len(unlinked))
for m in unlinked:
    d = json.loads(m["data_json"] or "{}")
    mid = d.get("msg_id", "")
    turn = d.get("turn_id")
    ti = con.execute("select queue_item_ids_json, claim_source, status "
                     "from local_runtime_turn_ingress where turn_id=?",
                     (turn,)).fetchone() if turn else None
    q = con.execute("select item_id, status from local_runtime_queue_items "
                    "where data_json like ?", ("%" + mid + "%",)).fetchall()
    print(f"  id={m['id']} {ts(m['created_at_ms'])} turn_id={turn} "
          f"turn_ingress={'NONE' if ti is None else (str(ti['queue_item_ids_json']) + ' claim=' + str(ti['claim_source']))} "
          f"queue_rows_with_msg_id={len(q)}")

print("\n=== does ANY turn in the store name one of OUR wake msg_ids? ===")
ours = [json.loads(m["data_json"] or "{}").get("msg_id")
        for m in unlinked]
linked = 0
for mid in ours:
    if not mid:
        continue
    n = con.execute("select count(*) from local_runtime_turn_ingress "
                    "where queue_item_ids_json is not null and "
                    "queue_item_ids_json like ?", ("%" + mid + "%",)).fetchone()[0]
    linked += n
print(f"turn_ingress rows naming one of our wake msg_ids: {linked} "
      f"(of {len(ours)} wake user rows)")