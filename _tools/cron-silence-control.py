"""PASS 3 — the control pass.

Pass 2 proved cron_runs is frozen at 2026-10-06T13:11:00.022Z while this session
was writing to the SAME store at 20:28:50Z. One confound remains: maybe the whole
process was down the whole time, and "no cron rows" is just "no process".

This pass settles it: hourly row counts in the session/message tables across the
entire silence window. If sessions kept being written, a live process owned the
store and simply fired no cron.
READ-ONLY. Never writes.
"""
import sqlite3
import datetime as dt

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


START = int(dt.datetime(2026, 10, 6, 12, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)
HOUR = 3600_000

con = sqlite3.connect(DB, uri=True)
cur = con.cursor()

print("== A. HOURLY ACTIVITY: cron_runs vs message_rows vs sessions (WINDOW 2026-10-06 12:00Z -> now) ==")
print(f"{'hour_utc':<18}{'cron_runs':>10}{'messages':>10}{'sessions':>10}{'bg_tasks':>10}   <- control")
tot_c = tot_m = tot_s = 0
cur.execute("SELECT ?", (START,))
bucket = START
while bucket < int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000) + HOUR:
    nxt = bucket + HOUR
    c = cur.execute("SELECT COUNT(*) FROM local_runtime_v2_cron_runs WHERE created_at_ms>=? AND created_at_ms<?", (bucket, nxt)).fetchone()[0]
    m = cur.execute("SELECT COUNT(*) FROM local_runtime_message_rows WHERE created_at_ms>=? AND created_at_ms<?", (bucket, nxt)).fetchone()[0]
    s = cur.execute("SELECT COUNT(*) FROM local_runtime_sessions WHERE updated_at_ms>=? AND updated_at_ms<?", (bucket, nxt)).fetchone()[0]
    b = cur.execute("SELECT COUNT(*) FROM local_runtime_background_tasks WHERE updated_at_ms>=? AND updated_at_ms<?", (bucket, nxt)).fetchone()[0]
    tot_c += c; tot_m += m; tot_s += s
    flag = "   <== LAST CRON" if c else ""
    print(f"{iso(bucket):<18}{c:>10}{m:>10}{s:>10}{b:>10}{flag}")
    bucket = nxt
print(f"TOTALS in window: cron_runs={tot_c} messages={tot_m} sessions_touched={tot_s}")

print("\n== B. HOW MANY *HOURS* OF SILENCE, vs HOW MANY HOURS THE STORE WAS LIVE ==")
last_cron = cur.execute("SELECT MAX(created_at_ms) FROM local_runtime_v2_cron_runs").fetchone()[0]
now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
gap_h = (now_ms - last_cron) / 3600_000
live_h = cur.execute(
    "SELECT COUNT(DISTINCT strftime('%Y-%m-%dT%H', created_at_ms/1000, 'unixepoch')) "
    "FROM local_runtime_message_rows WHERE created_at_ms > ?", (last_cron,)).fetchone()[0]
print(f"POPULATION=local_runtime_message_rows; WINDOW=(last_cron {iso(last_cron)}, now {iso(now_ms)}]")
print(f"  hours with ZERO cron executions : {gap_h:.1f}")
print(f"  hours with >=1 message row      : {live_h}  (distinct UTC hours)")

print("\n== C. THE FIVE 'active' JOBS: ARE THEY STILL ARMED AND OVERDUE? ==")
for r in cur.execute(
    "SELECT scheduler_id, run_count, next_run_at_ms, updated_at_ms, state FROM "
    "local_runtime_v2_scheduler_jobs WHERE state='active' ORDER BY next_run_at_ms"
):
    overdue_h = (now_ms - r[2]) / 3600_000 if r[2] else None
    od = f"OVERDUE {overdue_h:.1f}h" if overdue_h and overdue_h > 0 else "future"
    print(f"  {str(r[0])[:8]} runs={r[1]:<5} next={iso(r[2]):<18} last_touched={iso(r[3]):<18} {od}")

print("\n== D. sched-7f2c94e: created today, armed for 15:07:51Z, and it never fired ==")
r = cur.execute(
    "SELECT run_count, created_at_ms, next_run_at_ms, updated_at_ms, state, schedule_json "
    "FROM local_runtime_v2_scheduler_jobs WHERE scheduler_id='sched-7f2c94e7c5eb'").fetchone()
print(f"  created={iso(r[1])}  next_run={iso(r[2])}  run_count={r[0]}  state={r[4]}")
print(f"  schedule={r[5]}")
rows = cur.execute(
    "SELECT COUNT(*) FROM local_runtime_v2_cron_runs WHERE scheduler_trigger_id LIKE 'sched-7f2c94e7c5eb%'"
).fetchone()[0]
print(f"  cron_runs rows for this trigger (POPULATION=all rows, WINDOW=all time) = {rows}")

print("\n== E. cron_definitions: is the consolidated mission cron still enabled? ==")
c = [x[1] for x in cur.execute("PRAGMA table_info(local_runtime_v2_cron_definitions)")]
print("  columns=" + ",".join(c))
for r in cur.execute("SELECT * FROM local_runtime_v2_cron_definitions LIMIT 0"):
    pass
sel = [x for x in ("cron_id", "state", "enabled", "schedule", "next_run_at_ms", "updated_at_ms", "prompt_bytes") if x in c]
for r in cur.execute(f"SELECT {','.join(sel)} FROM local_runtime_v2_cron_definitions WHERE cron_id='d43fb9be-283d-4dd3-8e73-d9fb562fd181'"):
    print("  mission cron " + "  ".join(f"{k}={v}" for k, v in zip(sel, r)))

con.close()
print("\nREAD-ONLY: closed without write.")