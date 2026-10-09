import sqlite3, json, re
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
print("== userMessageId in each QUEUE row (ours vs template) ==")
for r in con.execute("select id, session_id, data_json from local_runtime_queue_items order by id"):
    d=json.loads(r["data_json"])
    u=d.get("userMessageId","<absent>")
    print(f"   qid={r['id']} sess={r['session_id'][:12]} userMessageId={u!r} len={len(str(u))}")
print()
print("== msg_id shape in DELIVERED user rows (runtime's own) ==")
n=0
for r in con.execute("select msg_id from local_runtime_message_rows where role='user' order by rowid desc limit 6"):
    print(f"   msg_id={r['msg_id']!r} len={len(r['msg_id'])}")
print()
print("== do any DELIVERED user msg_ids match a queue row userMessageId? ==")
for r in con.execute("select id, data_json from local_runtime_queue_items order by id"):
    d=json.loads(r["data_json"]); u=d.get("userMessageId")
    if not u: continue
    c=con.execute("select count(*) from local_runtime_message_rows where msg_id=?",(u,)).fetchone()[0]
    print(f"   qid={r['id']} userMessageId={u[:44]!r}... matching_message_rows={c}")
print()
print("== does ANY message row exist with our wake prefix? ==")
print("   POP msg_id LIKE 'msg-user-v1-wake%' =",
      con.execute("select count(*) from local_runtime_message_rows where msg_id like 'msg-user-v1-wake%'").fetchone()[0])
print()
print("== a real delivered user row: full keys for shape comparison ==")
r=con.execute("select data_json from local_runtime_message_rows where role='user' and source='cron' order by rowid desc limit 1").fetchone()
d=json.loads(r["data_json"])
print("   ", json.dumps({k:(str(v)[:80]) for k,v in d.items()}, ensure_ascii=False, indent=2))
con.close()
