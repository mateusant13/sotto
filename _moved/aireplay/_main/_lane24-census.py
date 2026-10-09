#!/usr/bin/env python3
"""lane24 census — REPRODUCE the audit's numbers before changing anything.

Read-only. Prints POPULATION and WINDOW for every figure.
"""
import datetime
import json
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
now_ms = int(time.time() * 1000)

print("=" * 78)
print("D-1  userMessageId shape")
print("=" * 78)
rows = con.execute(
    "select id, session_id, source, data_json from local_runtime_message_rows "
    "where role='user' order by id desc limit 20").fetchall()
print(f"POP: 20 most recent role='user' rows (whole-table filter role='user')")
for r in rows:
    d = json.loads(r["data_json"] or "{}")
    mid = d.get("msg_id") or d.get("messageId") or ""
    print(f"  len={len(str(mid)):>3}  {str(mid)[:60]}  src={r['source']}")
lens = {}
for r in rows:
    d = json.loads(r["data_json"] or "{}")
    mid = str(d.get("msg_id") or d.get("messageId") or "")
    lens[len(mid)] = lens.get(len(mid), 0) + 1
print("  length histogram:", lens)
print("POP 'msg-user-v1-wake%' =",
      con.execute("select count(*) from local_runtime_message_rows "
                  "where data_json like '%msg-user-v1-wake%'").fetchone()[0])

print()
print("=" * 78)
print("D-2  cron schedule_json shape")
print("=" * 78)
tot = con.execute("select count(*) from local_runtime_v2_scheduler_jobs").fetchone()[0]
five = con.execute("select count(*) from local_runtime_v2_scheduler_jobs "
                   "where schedule_json like '%* * * * *%'").fetchone()[0]
four = con.execute("select count(*) from local_runtime_v2_scheduler_jobs "
                   "where schedule_json like '%* * * *'").fetchone()[0]
print(f"POP scheduler jobs (whole table) = {tot}")
print(f"  like '%* * * * *' -> {five}   <-- shipped query")
print(f"  like '%* * * *'   -> {four}   <-- candidate fix")
for r in con.execute("select scheduler_id, state, schedule_json, next_run_at_ms, "
                     "run_count from local_runtime_v2_scheduler_jobs limit 6"):
    print(f"  {r['state']:<10} {r['schedule_json'][:100]}")
print("  distinct schedule_json values:")
for r in con.execute("select schedule_json, count(*) n from "
                     "local_runtime_v2_scheduler_jobs group by schedule_json "
                     "order by n desc limit 10"):
    print(f"    n={r['n']:<3} {r['schedule_json'][:110]}")

print()
print("=" * 78)
print("D-3/D-5  queue table shape + expiry + orphans")
print("=" * 78)
print("columns:", [r["name"] for r in con.execute(
    "pragma table_info(local_runtime_queue_items)")])
print("POP rows total =", con.execute(
    "select count(*) from local_runtime_queue_items").fetchone()[0])
print("POP rows with expires_at_ms NOT NULL =", con.execute(
    "select count(*) from local_runtime_queue_items "
    "where expires_at_ms is not null").fetchone()[0])
print("live queued rows:")
for r in con.execute("select item_id, session_id, status, claim_id, "
                     "created_at_ms, expires_at_ms from "
                     "local_runtime_queue_items where status='queued' "
                     "order by rowid"):
    age = (now_ms - r["created_at_ms"]) / 60000.0
    print(f"  {r['item_id']:<40} sess={r['session_id']} "
          f"age={age:.1f}min claim={r['claim_id']} exp={r['expires_at_ms']}")

print()
print("=" * 78)
print("D-4  runtime cron scheduler aliveness")
print("=" * 78)
n = con.execute("select count(*) from local_runtime_v2_cron_runs").fetchone()[0]
mx = con.execute("select max(created_at_ms) from local_runtime_v2_cron_runs").fetchone()[0]
print(f"POP cron_runs rows (whole table) = {n}")
print(f"  newest created_at_ms = {mx} -> {ts(mx)}")
print(f"  age = {(now_ms - mx) / 60000.0 / 60.0:.2f} h  "
      f"({(now_ms - mx) / 60000.0:.1f} min)")
act = con.execute(
    "select count(*) from local_runtime_v2_cron_definitions d "
    "join local_runtime_v2_scheduler_jobs j on j.scheduler_id=d.scheduler_id "
    "where d.deleted_at_ms is null and j.state='active'").fetchone()[0]
print(f"POP undeleted cron definitions joined to an ACTIVE scheduler job = {act}")

print()
print("=" * 78)
print("D-6  shutdown deadline occurrences in heartbeat.log")
print("=" * 78)
try:
    with open(r"H:\sotto\_moved\aireplay\_main\heartbeat.log", encoding="utf-8",
              errors="replace") as fh:
        lines = fh.readlines()
    occ = [l for l in lines if "shutdown deadline exceeded" in l]
    exc = [l for l in lines if "WAKE rc=" in l or "WAKE delivered" in l]
    print(f"POP heartbeat.log lines = {len(lines)}  (window = whole log)")
    print(f"  'shutdown deadline exceeded' lines = {len(occ)}")
    for l in occ[-5:]:
        print("   ", l.rstrip()[:160])
    print(f"  wake outcome lines (WAKE rc=/delivered) = {len(exc)}")
except OSError as e:
    print("cannot read heartbeat.log:", e)

print()
print("=" * 78)
print("turn_ingress / delivery linkage (authoritative proof field)")
print("=" * 78)
print("turn_ingress cols:", [r["name"] for r in con.execute(
    "pragma table_info(local_runtime_turn_ingress)")])
q = con.execute("select count(*) from local_runtime_turn_ingress "
                "where queue_item_ids_json is not null and claim_source='api'"
                ).fetchone()[0]
print("POP queue-driven turns =", q)
for r in con.execute("select turn_id, session_id, claim_source, "
                     "queue_item_ids_json, queue_acknowledged_at_ms, status "
                     "from local_runtime_turn_ingress "
                     "where queue_item_ids_json is not null "
                     "order by rowid desc limit 3"):
    print("  ", r["status"], r["session_id"], r["queue_item_ids_json"][:90])