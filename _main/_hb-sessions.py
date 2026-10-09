import sqlite3, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
cols = [r[1] for r in c.execute("PRAGMA table_info(local_runtime_sessions)")]
print("columns:", cols)
print()
since = int((datetime.datetime(2026,10,7,11,0,0)).timestamp()*1000)
rows = c.execute("select session_id, created_at_ms from local_runtime_sessions where created_at_ms > ? order by created_at_ms desc", (since,)).fetchall()
print("sessions created since 11:00 today:", len(rows))
for r in rows[:20]:
    print("  ", r[0][:30], datetime.datetime.fromtimestamp(r[1]/1000).strftime('%H:%M:%S'))
print()
print("TOTAL sessions:", c.execute("select count(*) from local_runtime_sessions").fetchone()[0])
