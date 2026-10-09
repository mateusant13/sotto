"""PASS 2 — refute PASS 1.

Pass 1 said rows_after_cutoff=1 against a cutoff of 13:11:00.000Z. The MAX row is
13:11:00.022Z, i.e. 22 ms PAST that cutoff, so '1' is the last pre-existing row
counted by a boundary that clips it, not a new execution. This pass moves the
boundary onto the exact MAX and adds windows anchored on NOW.
READ-ONLY. Never writes.
"""
import sqlite3
import datetime as dt
import os

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
NOW = dt.datetime.now(dt.timezone.utc)
NOW_MS = int(NOW.timestamp() * 1000)


def iso(ms):
    if ms is None:
        return "NULL"
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")


con = sqlite3.connect(DB, uri=True)
cur = con.cursor()
total, mx = cur.execute("SELECT COUNT(*), MAX(created_at_ms) FROM local_runtime_v2_cron_runs").fetchone()

print(f"anchor_now_utc={iso(NOW_MS)}")
print(f"POPULATION=all rows of local_runtime_v2_cron_runs: rows_total={total} max={iso(mx)}")

print("\n== A. REFUTATION OF PASS 1: boundary ON the exact MAX row ==")
n = cur.execute("SELECT COUNT(*) FROM local_runtime_v2_cron_runs WHERE created_at_ms > ?", (mx,)).fetchone()[0]
print(f"rows STRICTLY AFTER the max row = {n}   <-- 0 means nothing ran since 13:11:00.022Z")
rows = cur.execute(
    "SELECT run_id, cron_id, scheduler_trigger_id, trigger_source, status, created_at_ms "
    "FROM local_runtime_v2_cron_runs ORDER BY created_at_ms DESC LIMIT 5"
).fetchall()
print("last 5 rows (newest first):")
for r in rows:
    print(f"  {iso(r[5])}  status={r[4]:9s} trigger={r[3]:9s} cron={r[1]} sched={r[2]}")

print("\n== B. WINDOWS ANCHORED ON NOW (POPULATION = all rows) ==")
for label, ms in (
    ("last_1h", NOW_MS - 3600_000),
    ("last_6h", NOW_MS - 6 * 3600_000),
    ("last_12h", NOW_MS - 12 * 3600_000),
    ("last_24h", NOW_MS - 24 * 3600_000),
):
    c = cur.execute("SELECT COUNT(*) FROM local_runtime_v2_cron_runs WHERE created_at_ms > ?", (ms,)).fetchone()[0]
    print(f"  WINDOW={label} (from {iso(ms)})  executions={c}")

print("\n== C. DID THE START PROCESS TOUCH THE SCHEDULERS? (POPULATION = all rows) ==")
for r in cur.execute(
    "SELECT scheduler_id, state, run_count, next_run_at_ms, updated_at_ms, schedule_generation "
    "FROM local_runtime_v2_scheduler_jobs ORDER BY updated_at_ms DESC"
):
    print(f"  job={str(r[0])[:8]} state={r[1]:7s} runs={r[2]} next={iso(r[3]):26s} updated={iso(r[4]):26s} gen={r[5]}")
nstate = cur.execute("SELECT COUNT(*) FROM local_runtime_v2_scheduler_jobs").fetchone()[0]
print(f"  scheduler_jobs POPULATION={nstate}")

print("\n== D. PER-CRON BREAKDOWN (POPULATION = all rows, newest 10 crons) ==")
for r in cur.execute(
    "SELECT cron_id, COUNT(*), MAX(created_at_ms), "
    "SUM(CASE WHEN status='delivered' THEN 1 ELSE 0 END) "
    "FROM local_runtime_v2_cron_runs GROUP BY cron_id ORDER BY MAX(created_at_ms) DESC LIMIT 10"
):
    print(f"  cron={str(r[0])[:40]:40s} runs={r[1]:5d} last={iso(r[2]):26s} delivered={r[3]}")

print("\n== E. ANY TABLE WITH A ROW WRITTEN AFTER THIS PROCESS STARTED? ==")
tables = [t[0] for t in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
hit = []
for t in tables:
    cols = [c[1] for c in cur.execute(f'PRAGMA table_info("{t}")')]
    for c in ("updated_at_ms", "created_at_ms", "updated_at", "last_used_at_ms"):
        if c in cols:
            try:
                v = cur.execute(f'SELECT MAX("{c}") FROM "{t}"').fetchone()[0]
            except sqlite3.Error:
                break
            if v is not None and isinstance(v, (int, float)) and v > NOW_MS - 6 * 3600_000:
                hit.append((t, c, iso(v)))
            break
if hit:
    for t, c, v in sorted(hit, key=lambda x: x[2]):
        print(f"  {t}.{c} max={v}   <-- WRITTEN IN THE LAST 6h")
else:
    print("  no table had any *_at_ms value inside the last 6h window")

print("\n== F. WAL SIDECARS (are newer rows sitting unmerged?) ==")
base = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
for suf in ("", "-wal", "-shm"):
    p = base + suf
    if os.path.exists(p):
        st = os.stat(p)
        print(f"  {os.path.basename(p):28s} size={st.st_size:>14d}  mtime={dt.datetime.fromtimestamp(st.st_mtime).isoformat()}")
    else:
        print(f"  {os.path.basename(p):28s} ABSENT")

con.close()
print("\nREAD-ONLY: closed without write.")