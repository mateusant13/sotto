import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
SESS="mvs_b7a9f3a7db404912b32d28fc11b83645"
print("NOW", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("== ALL role='user' rows for target session since 12:00 (POP shown) ==")
tot=con.execute("select count(*) from local_runtime_message_rows where session_id=? and role='user'",(SESS,)).fetchone()[0]
print("POP user rows for session (all time) =", tot)
for r in con.execute("select id, role, source, created_at_ms, msg_id, turn_id, data_json from local_runtime_message_rows where session_id=? and role='user' and created_at_ms > ? order by rowid", (SESS, 1791384000000)):
    print(f"\n  id={r['id']} role={r['role']!r} source={r['source']!r} at={L(r['created_at_ms'])} turn={r['turn_id']} msg_id={r['msg_id']}")
    try:
        d=json.loads(r["data_json"])
        c=d.get("msg_content") or d.get("content") or ""
        print(f"    keys={sorted(d.keys())}")
        print(f"    content={str(c)[:500]!r}")
    except Exception as e:
        print("    raw:", r["data_json"][:300])
print()
print("== newest 12 rows ANY role for target session ==")
for r in con.execute("select id, role, source, created_at_ms from local_runtime_message_rows where session_id=? order by rowid desc limit 12",(SESS,)):
    print(f"  id={r['id']} role={r['role']!r} source={r['source']!r} at={L(r['created_at_ms'])}")
con.close()
