import sqlite3, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
cols = [d[1] for d in c.execute("PRAGMA table_info(local_runtime_messages)")]
print("cols:", cols[:14])
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
q = "select id, created_at_ms, json_extract(record_json,'$.role') from local_runtime_messages where session_id=? order by created_at_ms desc limit 6"
try:
    for r in c.execute(q, (sid,)):
        ts = datetime.datetime.fromtimestamp(r[1]/1000).strftime('%H:%M:%S') if r[1] else '?'
        print(" ", ts, (r[2] or "?"), str(r[0])[:24])
except Exception as e:
    print("fallback:", e)
    for r in c.execute("select * from local_runtime_messages where session_id=? order by rowid desc limit 3", (sid,)):
        print("  ", str(r)[:160])
