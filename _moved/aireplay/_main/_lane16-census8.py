import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
SESS="mvs_b7a9f3a7db404912b32d28fc11b83645"
print("== turn_ingress rows for TARGET session (POP for session) ==")
n=con.execute("select count(*) from local_runtime_turn_ingress where session_id=?",(SESS,)).fetchone()[0]
print("  POP =", n)
for r in con.execute("select turn_id, source, client_request_id, claim_id, claim_source, queue_item_ids_json, status, accepted_at_ms, completed_at_ms, queue_acknowledged_at_ms, input_digest from local_runtime_turn_ingress where session_id=? order by rowid desc limit 6",(SESS,)):
    print("   turn=",r["turn_id"][:34],"src=",r["source"],"crid=",r["client_request_id"],"claim_src=",r["claim_source"])
    print("      status=",r["status"],"accepted=",L(r["accepted_at_ms"]) if r["accepted_at_ms"] else None,"completed=",L(r["completed_at_ms"]) if r["completed_at_ms"] else None,"qack=",L(r["queue_acknowledged_at_ms"]) if r["queue_acknowledged_at_ms"] else None)
    print("      queue_items=",r["queue_item_ids_json"])
print()
print("== ingress rows whose client_request_id is a heartbeat inject ==")
for r in con.execute("select session_id, turn_id, client_request_id, claim_source, status, accepted_at_ms, queue_item_ids_json from local_runtime_turn_ingress where client_request_id like '%_hb_%' order by rowid desc limit 10"):
    print(f"   {L(0) and ''}crid={r['client_request_id']} sess={r['session_id'][:12]} turn={r['turn_id'][:30]} claim_src={r['claim_source']} status={r['status']} accepted={L(r['accepted_at_ms']) if r['accepted_at_ms'] else None} q={r['queue_item_ids_json']}")
print()
print("== ingress rows carrying ANY of our injected item_ids ==")
for it in ("queue_88e53fbb-2565-4684-9afc-d83c58551d80","queue_cf6aed5b","queue_ec7ae0a0","queue_f6b00dc4"):
    n=con.execute("select count(*) from local_runtime_turn_ingress where queue_item_ids_json like ?", (f"%{it}%",)).fetchone()[0]
    print(f"   {it}: ingress_rows={n}")
print()
print("== distinct turn_ingress.status values (whole table, POP=3686) ==")
for r in con.execute("select status, count(*) c from local_runtime_turn_ingress group by status order by c desc"):
    print(f"   {r['status']!r}: {r['c']}")
print()
print("== claim turnIds from our rows: do they exist anywhere? ==")
for t in ("turn_69a5c2b0-eb8f-43ed-8ab6-7a3783b46ad5","turn_5ef4b809-4fb1-4967-b708-008054ccf04d","turn_e33579f4-04c8-449d-ad59-05ea52872728"):
    a=con.execute("select count(*) from local_runtime_turn_ingress where turn_id=?",(t,)).fetchone()[0]
    b=con.execute("select count(*) from local_runtime_message_rows where turn_id=?",(t,)).fetchone()[0]
    print(f"   {t}: turn_ingress={a} message_rows={b}")
con.close()
