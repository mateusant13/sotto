import sqlite3, json, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
n = c.execute("select count(*) from local_runtime_message_rows where session_id=? and data_json like '%HEARTBEAT%'", (sid,)).fetchone()[0]
print("mensagens HEARTBEAT entregues nesta sessao:", n, "  [0 = NAO CHEGOU]")
print()
print("--- ultimas mensagens de USER (msg-user-v1-*) ---")
for mid, created, src, dj in c.execute(
    "select msg_id, created_at_ms, source, data_json from local_runtime_message_rows where session_id=? and role='user' order by created_at_ms desc limit 4", (sid,)):
    ts = datetime.datetime.fromtimestamp(created/1000).strftime('%H:%M:%S')
    d = json.loads(dj)
    content = d.get("content")
    if isinstance(content, list):
        content = " ".join(str(x.get("text","")) for x in content if isinstance(x, dict))
    print(" ", ts, "| source =", src)
    print("      ", str(content)[:120])
    print()
