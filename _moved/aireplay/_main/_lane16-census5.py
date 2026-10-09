import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
SESS="mvs_b7a9f3a7db404912b32d28fc11b83645"
print("NOW", datetime.now().strftime("%H:%M:%S"))
print("== queue table RIGHT NOW ==")
for r in con.execute("select id, session_id, item_id, status, claim_id, created_at_ms, data_json from local_runtime_queue_items order by id"):
    d=json.loads(r["data_json"])
    print(f"  id={r['id']} sess={r['session_id'][:12]} item={r['item_id'][:14]} status={r['status']} claim={r['claim_id']} created={L(r['created_at_ms'])} attempts={d.get('deliveryAttempts','<absent>')}")
    print(f"      content={str(d.get('message',{}).get('content',''))[:90]!r}")
print()
print("== rows with turn_id of the claim, or role IS NULL (last 20) ==")
for r in con.execute("select id, session_id, role, source, created_at_ms, turn_id, data_json from local_runtime_message_rows where turn_id=? order by rowid", ("turn_69a5c2b0-eb8f-43ed-8ab6-7a3783b46ad5",)):
    print(f"  CLAIM-TURN id={r['id']} sess={r['session_id'][:12]} role={r['role']!r} src={r['source']!r} at={L(r['created_at_ms'])}")
    print("     ", repr(r["data_json"])[:400])
print()
n=con.execute("select count(*) from local_runtime_message_rows where role is null").fetchone()[0]
print("POP rows role IS NULL (whole table) =", n)
for r in con.execute("select id, session_id, role, source, created_at_ms, data_json from local_runtime_message_rows where role is null order by rowid desc limit 5"):
    print(f"  NULLROLE id={r['id']} sess={r['session_id'][:12]} src={r['source']!r} at={L(r['created_at_ms'])}")
    print("     ", repr(r["data_json"])[:500])
print()
print("== any row ANYWHERE containing 'ACORDADO' or 'acorda.' ==")
for m in ("ACORDADO","acorda. Se leste isto"):
    c=con.execute("select count(*) from local_runtime_message_rows where data_json like ?", (f"%{m}%",)).fetchone()[0]
    u=con.execute("select count(*) from local_runtime_message_rows where data_json like ? and role='user'", (f"%{m}%",)).fetchone()[0]
    print(f"  {m!r}: any={c} user={u}")
    for r in con.execute("select id, session_id, role, source, created_at_ms from local_runtime_message_rows where data_json like ? order by rowid", (f"%{m}%",)):
        print(f"     id={r['id']} sess={r['session_id'][:12]} role={r['role']!r} src={r['source']!r} at={L(r['created_at_ms'])}")
con.close()
