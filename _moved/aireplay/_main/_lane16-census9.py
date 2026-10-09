import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
print("== row 4200 claim turn turn_3be0675b... ==")
t="turn_3be0675b-25ed-4ab7-9e97-1174cbe1e958"
print("   turn_ingress:", con.execute("select count(*) from local_runtime_turn_ingress where turn_id=?",(t,)).fetchone()[0])
print("   message_rows with that turn_id:", con.execute("select count(*) from local_runtime_message_rows where turn_id=?",(t,)).fetchone()[0])
print()
print("== session mvs_ea552229 : user rows around 2026-10-06 20:25 ==")
S="mvs_ea552229fe164f9e8856fcca8589c41a"
for r in con.execute("select id, role, source, created_at_ms, msg_id, turn_id, data_json from local_runtime_message_rows where session_id=? and created_at_ms between ? and ? order by rowid",(S,1791331200000,1791336000000)):
    d=json.loads(r["data_json"])
    print(f"   id={r['id']} role={r['role']!r} src={r['source']!r} at={L(r['created_at_ms'])} turn={r['turn_id']}")
    print(f"      {str(d.get('msg_content'))[:260]!r}")
print()
print("== search WHOLE table for the exact injected text of row 4200 ==")
m="nao quero que isso ocorra"
tot=con.execute("select count(*) from local_runtime_message_rows where data_json like ?",(f"%{m}%",)).fetchone()[0]
usr=con.execute("select count(*) from local_runtime_message_rows where data_json like ? and role='user'",(f"%{m}%",)).fetchone()[0]
print(f"   {m!r}: any={tot} user={usr}")
for r in con.execute("select id, session_id, role, source, created_at_ms from local_runtime_message_rows where data_json like ? order by rowid",(f"%{m}%",)):
    print(f"     id={r['id']} sess={r['session_id'][:12]} role={r['role']!r} src={r['source']!r} at={L(r['created_at_ms'])}")
print()
print("== ALL role='user' AND source='cron' rows: newest 3 and count by day ==")
print("   POP cron-user rows =", con.execute("select count(*) from local_runtime_message_rows where role='user' and source='cron'").fetchone()[0])
for r in con.execute("select id, session_id, created_at_ms from local_runtime_message_rows where role='user' and source='cron' order by rowid desc limit 3"):
    print(f"     id={r['id']} sess={r['session_id'][:12]} at={L(r['created_at_ms'])}")
print()
print("== probe cron state NOW ==")
for r in con.execute("select d.cron_id, j.run_count, j.next_run_at_ms, j.updated_at_ms, j.state from local_runtime_v2_cron_definitions d join local_runtime_v2_scheduler_jobs j on j.scheduler_id=d.scheduler_id where d.cron_id like 'probe-%'"):
    print(f"   cron={r['cron_id']} run_count={r['run_count']} next={L(r['next_run_at_ms'])} updated={L(r['updated_at_ms'])} state={r['state']}")
print("   POP cron_runs for probe crons =", con.execute("select count(*) from local_runtime_v2_cron_runs where cron_id like 'probe-%'").fetchone()[0])
con.close()
