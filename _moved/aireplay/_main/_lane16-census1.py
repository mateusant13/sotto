import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
print("POP queue_items =", con.execute("select count(*) from local_runtime_queue_items").fetchone()[0], "(whole table)")
for r in con.execute("select * from local_runtime_queue_items order by rowid"):
    d={k:r[k] for k in r.keys()}
    print("\n--- rowid", r["id"], "---")
    for k in ("session_id","item_id","status","source","client_request_id","dedupe_key","expires_at_ms","claim_id","claim_lease_expires_at_ms"):
        print(f"   {k} = {d[k]!r}")
    print("   created =", L(d["created_at_ms"]))
    print("   fp =", ("SET len=%d" % len(d["routing_fingerprint"])) if d["routing_fingerprint"] else "NULL")
    j=json.loads(d["data_json"])
    print("   data keys =", sorted(j.keys()))
    print("   status_in_json =", j.get("status"), " source_in_json =", j.get("source"))
    print("   requestedTurnId =", j.get("requestedTurnId"))
    print("   clientRequestId =", j.get("clientRequestId"))
    print("   content =", repr(str(j.get("message",{}).get("content",""))[:400]))
con.close()
