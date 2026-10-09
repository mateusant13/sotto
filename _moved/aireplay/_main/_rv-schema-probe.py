import sqlite3, json, sys
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES:", [r[0] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(local_runtime_sessions)")
print("SESSIONS COLS:", [r[1] for r in cur.fetchall()])
cur.execute("PRAGMA table_info(local_runtime_message_rows)")
print("MSG COLS:", [r[1] for r in cur.fetchall()])
