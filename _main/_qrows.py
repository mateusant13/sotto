import sqlite3, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
cols = [d[1] for d in c.execute("PRAGMA table_info(local_runtime_message_rows)")]
print("cols:", cols)
q = ("select * from local_runtime_message_rows where session_id=? "
     "order by rowid desc limit 4")
for r in c.execute(q, (sid,)):
    print("  ", str(r)[:230])
print()
n = c.execute("select count(*) from local_runtime_message_rows where session_id=? and record_json like '%HEARTBEAT%'", (sid,)).fetchone()[0]
print("mensagens HEARTBEAT já entregues nesta sessão:", n, " [0 = NÃO CHEGOU]")
