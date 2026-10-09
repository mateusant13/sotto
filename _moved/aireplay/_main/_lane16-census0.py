import sqlite3, json, time
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
print("NOW_LOCAL", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "epoch_ms", int(time.time()*1000))
for t in ("local_runtime_queue_items","local_runtime_message_rows","local_runtime_v2_cron_definitions","local_runtime_v2_scheduler_jobs","local_runtime_v2_cron_runs"):
    try:
        n=con.execute(f"select count(*) from {t}").fetchone()[0]
        print(f"POP {t} = {n}")
    except Exception as e:
        print(f"ERR {t} {e!r}")
print("\n== SCHEMA queue_items ==")
for r in con.execute("pragma table_info(local_runtime_queue_items)"): print("  ", r["name"], r["type"])
print("\n== SCHEMA message_rows ==")
for r in con.execute("pragma table_info(local_runtime_message_rows)"): print("  ", r["name"], r["type"])
con.close()
