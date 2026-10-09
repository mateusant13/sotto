import sqlite3, sys, time
c=sqlite3.connect("file:C:\\Users\\Administrador\\.minimax\\v2\\sqlite\\runtime-state.sqlite?mode=ro",uri=True)
c.row_factory=sqlite3.Row
print("live queued rows now:")
for r in c.execute("select item_id, session_id, created_at_ms from local_runtime_queue_items where status='queued'"):
    print("  ", r["item_id"][:30], r["session_id"], "age=%.1f min" % ((time.time()*1000-r["created_at_ms"])/60000))
print("rows with expires_at_ms set:", c.execute("select count(*) from local_runtime_queue_items where expires_at_ms is not null").fetchone()[0])
print("queue_1dfd5c7c present:", c.execute("select count(*) from local_runtime_queue_items where item_id like 'queue_1dfd5c7c%'").fetchone()[0])
