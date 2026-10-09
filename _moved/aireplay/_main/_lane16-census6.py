import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
print("== ALL TABLES ==")
tabs=[r[0] for r in con.execute("select name from sqlite_master where type='table' order by name")]
for t in tabs:
    try: n=con.execute(f"select count(*) from {t}").fetchone()[0]
    except Exception as e: n=f"ERR {e}"
    print(f"  {t:55s} {n}")
print()
print("== tables whose NAME mentions turn/claim/deliver/event/log ==")
for t in tabs:
    if any(k in t.lower() for k in ("turn","claim","deliver","event","log","notif")):
        print("  ", t)
con.close()
