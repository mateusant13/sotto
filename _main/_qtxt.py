import sqlite3, json, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
r = c.execute("select data_json from local_runtime_message_rows where session_id=? and msg_id like 'msg-user-v1-%' order by created_at_ms desc limit 1", (sid,)).fetchone()
d = json.loads(r[0])
print("campos:", list(d.keys()))
txt = d.get("text") or d.get("content") or ""
if isinstance(txt, list):
    txt = " ".join(str(x.get("text","")) for x in txt if isinstance(x,dict))
print()
print("TEXTO DA TUA ULTIMA MENSAGEM:")
print(" ", str(txt)[:300])
