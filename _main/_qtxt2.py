import sqlite3, json, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
print("--- as 3 ultimas mensagens de USER, texto real ---")
for mid, created, dj in c.execute(
    "select msg_id, created_at_ms, data_json from local_runtime_message_rows where session_id=? and role='user' order by created_at_ms desc limit 3", (sid,)):
    d = json.loads(dj)
    ts = datetime.datetime.fromtimestamp(created/1000).strftime('%H:%M:%S')
    print(" ", ts, "| source =", d.get("source"), "| msg_type =", d.get("msg_type"))
    print("      TEXTO:", str(d.get("msg_content"))[:200])
    print()
