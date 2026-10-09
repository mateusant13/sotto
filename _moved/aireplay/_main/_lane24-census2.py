#!/usr/bin/env python3
"""lane24 follow-up: why does LIKE '%* * * *' return 0 on rows that visibly
contain that text?  And what are the 35 'msg-user-v1-wake%' rows?"""
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
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return repr(ms)


print("=== LIKE experiment on schedule_json ===")
row = con.execute("select scheduler_id, schedule_json from "
                  "local_runtime_v2_scheduler_jobs where schedule_json "
                  "like '%*/3%'").fetchone()
s = row["schedule_json"]
print("sample:", repr(s))
print("python '*/3 * * * *' in s ->", "*/3 * * * *" in s)
for pat in ["%* * * *%", "%* * * *", "%*%*%*%*%", "%* * * * *", "*/3 * * * *"]:
    n = con.execute("select count(*) from local_runtime_v2_scheduler_jobs "
                    "where schedule_json like ?", (pat,)).fetchone()[0]
    print(f"  like {pat!r:<16} -> {n}")
print("  instr(s,'* * * *') =", con.execute(
    "select instr(schedule_json,'* * * *') from local_runtime_v2_scheduler_jobs "
    "where schedule_json like '%*/3%'").fetchone()[0])
print("  glob '* * * *' ->", con.execute(
    "select count(*) from local_runtime_v2_scheduler_jobs "
    "where schedule_json glob '* * * *'").fetchone()[0])
print("  json_extract(expression) ->", [r[0] for r in con.execute(
    "select json_extract(schedule_json,'$.expression') from "
    "local_runtime_v2_scheduler_jobs where state='active'")])
print("  expression like '*/%' ->", con.execute(
    "select count(*) from local_runtime_v2_scheduler_jobs "
    "where json_extract(schedule_json,'$.expression') like '*/%'").fetchone()[0])

print()
print("=== the 35 'msg-user-v1-wake%' rows ===")
rows = con.execute("select id, session_id, role, source, created_at_ms, data_json "
                   "from local_runtime_message_rows "
                   "where data_json like '%msg-user-v1-wake%' "
                   "order by id desc").fetchall()
print("POP =", len(rows))
for r in rows:
    d = json.loads(r["data_json"] or "{}")
    mid = str(d.get("msg_id") or "")
    print(f"  id={r['id']} role={r['role']:<9} src={r['source']:<16} "
          f"{ts(r['created_at_ms'])} len={len(mid)} turn={d.get('turn_id')} "
          f"{mid[:40]}")

print()
print("=== is the 48-char wake id linked to a queue item + turn_ingress? ===")
wake_ids = []
for r in rows:
    d = json.loads(r["data_json"] or "{}")
    mid = str(d.get("msg_id") or "")
    if mid.startswith("msg-user-v1-wake"):
        wake_ids.append((r["id"], r["session_id"], r["role"], r["source"], mid,
                         d.get("turn_id")))
for (mid_id, sess, role, src, mid, turn) in wake_ids:
    print(f"\n message id={mid_id} session={sess} role={role} src={src}")
    print(f"   msg_id={mid}  turn_id={turn}")
    hit = con.execute("select item_id, session_id, status, created_at_ms "
                      "from local_runtime_queue_items where data_json like ?",
                      ("%" + mid + "%",)).fetchall()
    print(f"   queue rows carrying this msg_id: {len(hit)}")
    for h in hit:
        print(f"     item={h['item_id']} sess={h['session_id']} "
              f"status={h['status']} created={ts(h['created_at_ms'])}")
    if turn:
        ti = con.execute("select turn_id, session_id, claim_source, "
                         "queue_item_ids_json, queue_acknowledged_at_ms, status "
                         "from local_runtime_turn_ingress where turn_id=?",
                         (turn,)).fetchall()
        print(f"   turn_ingress rows for that turn_id: {len(ti)}")
        for t in ti:
            print(f"     turn={t['turn_id']} sess={t['session_id']} "
                  f"claim_source={t['claim_source']} "
                  f"queue_items={t['queue_item_ids_json']} "
                  f"ack={t['queue_acknowledged_at_ms']} status={t['status']}")