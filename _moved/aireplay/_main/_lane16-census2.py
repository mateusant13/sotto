import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
print("POP message_rows =", con.execute("select count(*) from local_runtime_message_rows").fetchone()[0])
print("POP rows containing 'WAKE-TEST-A3F1' (WHOLE TABLE, any role) =",
      con.execute("select count(*) from local_runtime_message_rows where data_json like '%WAKE-TEST-A3F1%'").fetchone()[0])
print("POP  ... same, role='user' =",
      con.execute("select count(*) from local_runtime_message_rows where data_json like '%WAKE-TEST-A3F1%' and role='user'").fetchone()[0])
for r in con.execute("select id, session_id, role, source, created_at_ms, msg_id from local_runtime_message_rows where data_json like '%WAKE-TEST-A3F1%' order by rowid"):
    print(f"   HIT id={r['id']} session={r['session_id']} role={r['role']!r} source={r['source']!r} at={L(r['created_at_ms'])} msg_id={r['msg_id']}")

print()
markers = {
 "OWNER-REALMSG": "reiniciei. que workspace estamos",
 "HEARTBEAT-PASS": "Pass automatico. Continua o plano do Sotto",
 "CORRUPT-ERR": "Queue row is corrupt",
 "CRON-TESTE": "CRON UNICO DE TESTE",
}
for name, m in markers.items():
    tot = con.execute("select count(*) from local_runtime_message_rows where data_json like ?", (f"%{m}%",)).fetchone()[0]
    usr = con.execute("select count(*) from local_runtime_message_rows where data_json like ? and role='user'", (f"%{m}%",)).fetchone()[0]
    print(f"MARKER {name!r}: any_role={tot} role_user={usr}")
    for r in con.execute("select id, session_id, role, source, created_at_ms from local_runtime_message_rows where data_json like ? order by rowid", (f"%{m}%",)):
        print(f"     id={r['id']} session={r['session_id']} role={r['role']!r} source={r['source']!r} at={L(r['created_at_ms'])}")
con.close()
