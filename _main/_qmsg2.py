import sqlite3, json, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
row = c.execute("select display_messages_json from local_runtime_messages where session_id=?", (sid,)).fetchone()
msgs = json.loads(row[0]) if row else []
print("total de mensagens nesta sessao:", len(msgs))
print("--- as 5 mais recentes ---")
for m in msgs[-5:]:
    role = m.get("role") or m.get("type") or "?"
    ts = m.get("createdAtMs") or m.get("created_at") or 0
    t = datetime.datetime.fromtimestamp(ts/1000).strftime('%H:%M:%S') if ts else '?'
    txt = json.dumps(m.get("content") or m.get("text") or "")[:80]
    print(" ", t, "|", role, "|", txt)
