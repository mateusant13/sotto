#!/usr/bin/env python3
"""lane24 orphan simulation — D-5, session scope.

Builds a throwaway store holding the rows that matter, then runs the SHIPPED
`wake-fix.py prune` with the command heartbeat.ps1 actually issues on the BUSY
path (`--stale-mins 999 --all-sessions --orphan-min-mins 60`):

    ORPHAN sess, 900 min old   -> must be SWEPT      (D-5: a session-scoped
                                                       prune can never reach it)
    OTHER  sess,   5 min old   -> must be KEPT       (foreign floor is 60 min:
                                                       a live session's pending
                                                       wake is never collateral)
    TARGET sess,   5 min old   -> must be KEPT       (stale-mins 999 on the busy
                                                       path: the driver never
                                                       deletes the wake it is
                                                       about to queue -- the bug
                                                       the previous prune fix
                                                       shipped)

The first version of this sim asserted KEPT_FRESH for the TARGET row while
passing --stale-mins 3, which prunes it BY DESIGN on the idle path; the sim was
testing the wrong configuration rather than finding a real defect.

Usage: _lane24-orphan-sim.py <sqlite> <wake-fix.py>
Prints SWEPT / KEPT_FOREIGN / KEPT_TARGET and exits 0.
"""
import os
import sqlite3
import subprocess
import sys
import time

DB = sys.argv[1]
WF = sys.argv[2]
ORPHAN_SESS = "mvs_lane24orphan0000000000000000000000"
OTHER_SESS = "mvs_lane24other00000000000000000000000"
TARGET_SESS = "mvs_lane24target00000000000000000000000"
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lane24-sim-backups")
os.makedirs(BAK, exist_ok=True)

if os.path.exists(DB):
    os.remove(DB)
now_ms = int(time.time() * 1000)
con = sqlite3.connect(DB)
con.execute("create table local_runtime_queue_items (id integer primary key, "
            "session_id text, item_id text, status text, created_at_ms integer, "
            "data_json text, source text, client_request_id text, "
            "dedupe_key text, expires_at_ms integer, claim_id text, "
            "claim_lease_expires_at_ms integer, routing_fingerprint text)")
for sess, item, age in ((ORPHAN_SESS, "queue_lane24_orphan", 900),
                        (OTHER_SESS, "queue_lane24_foreign_fresh", 5),
                        (TARGET_SESS, "queue_lane24_target_fresh", 5)):
    con.execute("insert into local_runtime_queue_items (session_id,item_id,status,"
                "created_at_ms,data_json,claim_id) values "
                "(?,?,'queued',?,'{}',NULL)",
                (sess, item, now_ms - age * 60_000))
con.commit()
con.close()

env = dict(os.environ)
env["SOTTO_WAKE_DB"] = DB
env["SOTTO_WAKE_BACKUP_DIR"] = BAK
env["PYTHONIOENCODING"] = "utf-8"
p = subprocess.run([sys.executable, WF, "prune", "--session", TARGET_SESS,
                    "--stale-mins", "999", "--all-sessions",
                    "--orphan-min-mins", "60"],
                   capture_output=True, text=True, env=env)

con = sqlite3.connect(DB)
left = {r[0] for r in con.execute("select item_id from local_runtime_queue_items")}
con.close()
print(f"SWEPT={1 if 'queue_lane24_orphan' not in left else 0}")
print(f"KEPT_FOREIGN={1 if 'queue_lane24_foreign_fresh' in left else 0}")
print(f"KEPT_TARGET={1 if 'queue_lane24_target_fresh' in left else 0}")
print(f"RC={p.returncode}")
sys.exit(0)