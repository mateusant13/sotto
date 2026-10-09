import sqlite3
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
c = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\","/"), uri=True)
for r in c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('local_runtime_message_rows','local_runtime_queue_items')"):
    print(r[0]); print("---")
print("queue cols:", [d[1] for d in c.execute("PRAGMA table_info(local_runtime_queue_items)")])
print("msg cols:", [d[1] for d in c.execute("PRAGMA table_info(local_runtime_message_rows)")])
print("msg-user-v1 count:", c.execute("SELECT COUNT(*) FROM local_runtime_message_rows WHERE msg_id LIKE 'msg-user-v1-%'").fetchone()[0])
print("sources:", c.execute("SELECT DISTINCT source FROM local_runtime_queue_items LIMIT 20").fetchall())
