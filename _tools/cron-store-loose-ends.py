"""PASS 4 — close two loose ends left open by CRON-VERDICT.md.

1. Is there another store on disk that could be the real cron home?
2. The verdict file cites prompt_bytes=8553 from the DB; cron_definitions has no
   such column. What does the stored prompt actually measure?
3. How many distinct process lifetimes passed during the silence? (proxy for
   "a freshly started process" being tested more than once)
READ-ONLY. Never writes.
"""
import os
import sqlite3
import datetime as dt

HOME = r"C:\Users\Administrador\.minimax"
print("== A. EVERY runtime-state.sqlite UNDER THE RUNTIME DIR (confound check) ==")
hits = []
for root, dirs, files in os.walk(HOME):
    for f in files:
        if f.startswith("runtime-state.sqlite"):
            p = os.path.join(root, f)
            st = os.stat(p)
            hits.append((p, st.st_size, st.st_mtime))
if not hits:
    print("  none")
for p, sz, mt in hits:
    print(f"  {p}  size={sz}  mtime={dt.datetime.fromtimestamp(mt).isoformat()}")
print(f"  POPULATION = {len(hits)} store(s) matching the name under {HOME}")


def iso(ms):
    if ms is None:
        return "NULL"
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z")


con = sqlite3.connect(
    r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro", uri=True)
cur = con.cursor()

print("\n== B. THE MISSION CRON'S STORED PROMPT: chars vs bytes ==")
cols = [c[1] for c in cur.execute("PRAGMA table_info(local_runtime_v2_cron_definitions)")]
print("  cron_definitions columns=" + ",".join(cols))
r = cur.execute(
    "SELECT length(prompt), length(CAST(prompt AS BLOB)), project, model, agent_name, "
    "session_target_mode, revision, deleted_at_ms, updated_at_ms, scheduler_id "
    "FROM local_runtime_v2_cron_definitions WHERE cron_id='d43fb9be-283d-4dd3-8e73-d9fb562fd181'"
).fetchone()
print(f"  len(prompt) CHARS = {r[0]}")
print(f"  len(prompt) BYTES = {r[1]}")
for k, v in zip(["project", "model", "agent_name", "session_target_mode",
                 "revision", "deleted_at_ms", "updated_at_ms", "scheduler_id"], r[2:]):
    print(f"  {k:<20} {iso(v) if k.endswith('_ms') else v}")
n = cur.execute("SELECT COUNT(*) FROM local_runtime_v2_cron_definitions").fetchone()[0]
d = cur.execute(
    "SELECT COUNT(*) FROM local_runtime_v2_cron_definitions WHERE deleted_at_ms IS NOT NULL"
).fetchone()[0]
print(f"  POPULATION=cron_definitions rows={n}  soft_deleted={d}  live={n - d}")
print(f"  has a prompt_bytes column? {'prompt_bytes' in cols}")

print("\n== C. DISTINCT PROCESS LIFETIMES DURING THE SILENCE (proxy: sessions CREATED) ==")
last_cron = cur.execute("SELECT MAX(created_at_ms) FROM local_runtime_v2_cron_runs").fetchone()[0]
sess = cur.execute(
    "SELECT COUNT(*), MIN(created_at_ms), MAX(created_at_ms) FROM local_runtime_sessions WHERE created_at_ms > ?",
    (last_cron,)).fetchone()
print(f"  WINDOW = (last_cron {iso(last_cron)}, now]")
print(f"  sessions CREATED = {sess[0]}   first={iso(sess[1])}   last={iso(sess[2])}")
gap = cur.execute(
    "SELECT COUNT(*) FROM (SELECT DISTINCT strftime('%Y-%m-%dT%H', created_at_ms/1000, 'unixepoch') "
    "FROM local_runtime_sessions WHERE created_at_ms > ?)", (last_cron,)).fetchone()[0]
print(f"  distinct UTC hours containing a NEW session = {gap}  (>= that many process lifetimes)")
print(f"  cron executions in that same window = "
      f"{cur.execute('SELECT COUNT(*) FROM local_runtime_v2_cron_runs WHERE created_at_ms > ?', (last_cron,)).fetchone()[0]}")

con.close()
print("\nREAD-ONLY: closed without write.")