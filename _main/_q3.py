import sqlite3
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
rows = c.execute("select item_id,status,created_at_ms,source from local_runtime_queue_items where session_id='mvs_a00662bff55242cb9b56c0f1165bdad7' order by created_at_ms desc limit 3").fetchall()
for r in rows: print("  ", r)
