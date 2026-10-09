import sqlite3
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
for t in ("local_runtime_queues","local_runtime_queue_items","local_runtime_queue_pauses"):
    print("=== "+t)
    cur = c.execute("PRAGMA table_info("+t+")")
    print("   cols:", [d[1] for d in cur])
    n = c.execute("select count(*) from "+t).fetchone()[0]
    print("   rows:", n)
    for r in c.execute("select * from "+t+" limit 3"):
        print("   ", str(r)[:220])
    print()
