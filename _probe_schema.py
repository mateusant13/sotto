import sqlite3, json, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
for t in ("local_runtime_queue_items", "local_runtime_message_rows",
          "local_runtime_turn_ingress"):
    print("=" * 70)
    print("SCHEMA", t)
    for r in con.execute("select sql from sqlite_master where tbl_name=? and sql is not null", (t,)):
        print(r[0])
print("=" * 70)
print("QUEUE CENSUS")
for r in con.execute("select status, count(*) from local_runtime_queue_items group by status"):
    print("  ", r[0], r[1])
print("=" * 70)
print("REFERENCE QUEUE ROW (newest, full)")
cur = con.execute("select * from local_runtime_queue_items order by rowid desc limit 2")
cols = [d[0] for d in cur.description]
print("cols:", cols)
for hit in cur.fetchall():
    d = dict(hit)
    for k, v in d.items():
        s = repr(v)
        print(f"    {k:<28} = {s[:300]}")
    print("   ---")
print("=" * 70)
print("MESSAGE ROW sample (newest 2 user rows, whole store)")
cur = con.execute("select * from local_runtime_message_rows where role='user' order by rowid desc limit 2")
mcols = [d[0] for d in cur.description]
print("cols:", mcols)
for hit in cur.fetchall():
    for k, v in dict(hit).items():
        print(f"    {k:<28} = {repr(v)[:260]}")
    print("   ---")
print("=" * 70)
print("DISTINCT source values in message_rows")
for r in con.execute("select source, count(*) from local_runtime_message_rows group by source"):
    print("  ", r[0], r[1])