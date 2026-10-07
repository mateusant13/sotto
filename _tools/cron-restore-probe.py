"""READ-ONLY probe: did a fresh process start restore cron delivery?

Opens the runtime store with mode=ro and immutable untouched. Never writes.
Every count printed with POPULATION and WINDOW.
"""
import sqlite3
import datetime as dt

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
CUTOFF_MS = int(dt.datetime(2026, 10, 6, 13, 11, 0, tzinfo=dt.timezone.utc).timestamp() * 1000)


def iso(ms):
    if ms is None:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")


con = sqlite3.connect(DB, uri=True)
cur = con.cursor()

print("== A. FULL POPULATION: local_runtime_v2_cron_runs (all rows, all time) ==")
total, mx = cur.execute(
    "SELECT COUNT(*), MAX(created_at_ms) FROM local_runtime_v2_cron_runs"
).fetchone()
print(f"rows_total={total}")
print(f"max_created_at_ms={mx}  -> {iso(mx)}")

print()
print("== B. NEW ROWS AFTER CUTOFF 2026-10-06T13:11:00Z (WINDOW = (cutoff, now]) ==")
after, after_max = cur.execute(
    "SELECT COUNT(*), MAX(created_at_ms) FROM local_runtime_v2_cron_runs WHERE created_at_ms > ?",
    (CUTOFF_MS,),
).fetchone()
print(f"rows_after_cutoff={after}")
print(f"max_after_cutoff={after_max} -> {iso(after_max)}")

print()
print("== C. SAME TEST ON THE 'now' COLUMN IF IT EXISTS ==")
cols = [r[1] for r in cur.execute("PRAGMA table_info(local_runtime_v2_cron_runs)")]
print("columns=" + ",".join(cols))

print()
print("== D. PER-JOB BREAKDOWN, POPULATION = all rows ==")
q = """
SELECT scheduler_job_id, COUNT(*), MAX(created_at_ms),
       SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END)
FROM local_runtime_v2_cron_runs
GROUP BY scheduler_job_id
ORDER BY MAX(created_at_ms) DESC
LIMIT 12
"""
try:
    for row in cur.execute(q):
        print(f"job={row[0]} runs={row[1]} last={iso(row[2])} delivered={row[3]}")
except sqlite3.Error as e:
    print("per-job query failed:", e)

print()
print("== E. SCHEDULER JOBS: POPULATION = all rows ==")
scols = [r[1] for r in cur.execute("PRAGMA table_info(local_runtime_v2_scheduler_jobs)")]
print("columns=" + ",".join(scols))
for row in cur.execute(
    "SELECT scheduler_id, state, run_count, next_run_at_ms FROM local_runtime_v2_scheduler_jobs "
    "WHERE state='active' ORDER BY next_run_at_ms"
):
    print(f"active job={row[0]} state={row[1]} run_count={row[2]} next_run_at={iso(row[3])}")

con.close()
print("\nREAD-ONLY: closed without write.")