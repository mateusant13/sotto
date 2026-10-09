import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
print("NOW", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("== deliveryAttempts per queue row ==")
for r in con.execute("select id, session_id, status, claim_id, data_json, created_at_ms from local_runtime_queue_items order by rowid"):
    d=json.loads(r["data_json"])
    print(f"  id={r['id']} session={r['session_id'][:12]} status={r['status']} claim={r['claim_id']} created={L(r['created_at_ms'])} deliveryAttempts={d.get('deliveryAttempts','<absent>')}")
print()
print("== cron_runs: newest 8 (POP=", con.execute("select count(*) from local_runtime_v2_cron_runs").fetchone()[0], ") ==")
for r in con.execute("select run_id, cron_id, trigger_source, status, session_id, created_at_ms, delivered_at_ms, error_code, error from local_runtime_v2_cron_runs order by created_at_ms desc limit 8"):
    print(f"  {L(r['created_at_ms'])} cron={r['cron_id'][:14]} src={r['trigger_source']} status={r['status']} sess={(r['session_id'] or '-')[:12]} delivered={L(r['delivered_at_ms']) if r['delivered_at_ms'] else '-'} err={r['error_code']} err_txt={(r['error'] or '')[:90]!r}")
print()
print("== probe crons (name like %probe%) ==")
for r in con.execute("select d.cron_id, d.name, d.deleted_at_ms, j.state, j.next_run_at_ms, j.run_count, j.updated_at_ms from local_runtime_v2_cron_definitions d left join local_runtime_v2_scheduler_jobs j on j.scheduler_id=d.scheduler_id where d.name like '%probe%' order by d.created_at_ms desc limit 10"):
    print(f"  cron={r['cron_id']} name={r['name']!r} deleted={r['deleted_at_ms']} state={r['state']} run_count={r['run_count']} next={L(r['next_run_at_ms'])} upd={L(r['updated_at_ms'])}")
print()
print("== active scheduler jobs: how many */3 and when updated ==")
for r in con.execute("select j.scheduler_id, j.state, j.run_count, j.next_run_at_ms, j.updated_at_ms, d.name, d.deleted_at_ms, d.target_session_id, d.session_target_mode from local_runtime_v2_scheduler_jobs j left join local_runtime_v2_cron_definitions d on d.scheduler_id=j.scheduler_id where j.schedule_json like '%* * * * *%' order by j.next_run_at_ms"):
    print(f"  sched={j_ok if False else r['scheduler_id']} state={r['state']} runs={r['run_count']} next={L(r['next_run_at_ms'])} upd={L(r['updated_at_ms'])} deleted={r['deleted_at_ms']} tgt={(r['target_session_id'] or '-')[:12]} mode={r['session_target_mode']} name={r['name']!r}")
con.close()
