import sqlite3, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
since = int(datetime.datetime(2026,10,7,11,25,0).timestamp()*1000)
rows = c.execute("select count(*) from local_runtime_sessions where created_at_ms > ?", (since,)).fetchone()[0]
print("sessions criadas desde 11:25 (janela do driver v1):", rows)
