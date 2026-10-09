#!/usr/bin/env python3
"""lane24 D-7 measurement: WHICH field predicts whether `mcode exec` is accepted?

The driver branches on local_runtime_sessions.status and that branch was measured
WRONG twice (13:05:05 and 13:08:59, both rc=4, both with the store saying
'idle').  So do not read the schema and guess: sample every candidate signal
over a window and report each one's agreement with a known outcome.

Candidates
  A  local_runtime_sessions.status
  B  local_runtime_session_locks  (owner_kind / expires_at_ms)
  C  turn_ingress  status='accepted' with completed_at_ms IS NULL
  D  any turn_ingress row for the session with no completed_at_ms
  E  lock expiry in the past (a stale lock that still blocks)

Usage: _lane24-d7-census.py [--session <id>] [--window-min 60]
"""
import datetime
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
SESSION = "mvs_a00662bff55242cb9b56c0f1165bdad7"
if "--session" in sys.argv:
    SESSION = sys.argv[sys.argv.index("--session") + 1]

now_ms = int(time.time() * 1000)


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return repr(ms)


con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
print(f"TARGET SESSION {SESSION}\nNOW {ts(now_ms)}\n")

print("=== A: local_runtime_sessions.status ===")
r = con.execute("select session_id, status, workspace_dir, updated_at_ms "
                "from local_runtime_sessions where session_id=?",
                (SESSION,)).fetchone()
print("  ", dict(r) if r else "NO ROW")
status = r["status"] if r else None

print("\n=== B: local_runtime_session_locks (ALL rows for this session) ===")
cols = [c["name"] for c in con.execute(
    "pragma table_info(local_runtime_session_locks)")]
print("  columns:", cols)
locks = con.execute("select * from local_runtime_session_locks "
                    "where session_id=? order by rowid", (SESSION,)).fetchall()
print(f"  POP locks for this session = {len(locks)}")
for l in locks:
    exp = l["expires_at_ms"]
    print(f"    owner_kind={l['owner_kind']!r} owner_id={l['owner_id']!r} "
          f"acquired={ts(l['acquired_at_ms'])} expires={ts(exp) if exp else 'NULL'}"
          f"{'  EXPIRED' if exp and int(exp) <= now_ms else ''}")
lock_blocks = any(l["owner_kind"] and "turn" in str(l["owner_kind"]).lower()
                  for l in locks)

print("\n=== C/D: turn_ingress for this session, most recent 12 ===")
cols2 = [c["name"] for c in con.execute(
    "pragma table_info(local_runtime_turn_ingress)")]
print("  columns:", cols2)
t = con.execute("select turn_id, source, claim_source, queue_item_ids_json, "
                "status, accepted_at_ms, completed_at_ms, client_request_id "
                "from local_runtime_turn_ingress where session_id=? "
                "order by accepted_at_ms desc limit 12", (SESSION,)).fetchall()
unfinished = 0
for x in t:
    age = (now_ms - (x["accepted_at_ms"] or now_ms)) / 60000.0
    open_ = x["completed_at_ms"] is None
    unfinished += 1 if open_ else 0
    print(f"    {ts(x['accepted_at_ms'])} status={x['status']:<9} "
          f"claim={x['claim_source']} completed={'NULL' if open_ else ts(x['completed_at_ms'])} "
          f"age={age:.1f}min queue_items={x['queue_item_ids_json']}")

print("\n=== all unfinished turns across the WHOLE store ===")
g = con.execute("select session_id, status, accepted_at_ms, claim_source, "
                "queue_item_ids_json from local_runtime_turn_ingress "
                "where completed_at_ms is null order by accepted_at_ms desc "
                "limit 10").fetchall()
print(f"  POP rows with completed_at_ms IS NULL (whole table) = "
      f"{con.execute('select count(*) from local_runtime_turn_ingress where completed_at_ms is null').fetchone()[0]}")
for x in g:
    print(f"    sess={x['session_id']} status={x['status']} "
          f"accepted={ts(x['accepted_at_ms'])} "
          f"age={(now_ms - (x['accepted_at_ms'] or now_ms)) / 60000.0:.1f}min")

print("\n=== VERDICT: which signal is TRUE right now ===")
print(f"  A status == 'idle'                  -> {status == 'idle'}")
print(f"  B a turn-lease lock is held         -> {lock_blocks}")
print(f"  C an accepted-but-uncompleted turn  -> "
      f"{con.execute(chr(39).join(['select count(*) from local_runtime_turn_ingress where session_id=? and status=', '']) + 'accepted' + chr(39) + ' and completed_at_ms is null', (SESSION,)).fetchone()[0] > 0}")
print(f"  D any unfinished turn for session   -> {unfinished > 0}")
print("  Measured outcomes: exec was REFUSED at 13:05:05 and 13:08:59 with")
print("  'Session already has an active Turn' while the store said 'idle'.")
print("  So the honest reading is: A is NOT a predictor of exec acceptance.")