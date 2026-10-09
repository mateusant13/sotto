#!/usr/bin/env python3
"""lane24 wedge simulation — drives the SHIPPED wake-fix.py, not a copy of its
predicate.

The previous audit reproduced the D-3 wedge by RE-IMPLEMENTING the predicate in
the gate's own python (receipt-21 ARM D1/D2).  That proves the gate's copy of
the predicate, not the one that ships.  This calls wake-fix.py itself as a
subprocess and reads its real exit code, so the arm is about the artifact.

Usage:  _lane24-wedge-sim.py <sqlite-path> <nocure|expired> [<wake-fix.py>]

Each of the 5 attempts replants the same dead row before it runs, so every
attempt faces the identical question a real 3-minute fire faces:
    "there is an old, never-claimed row for this session -- do you refuse?"
--stale-mins 999 switches the PRUNE cure OFF, so the only thing that can rescue
the session is expiry-awareness in the predicate itself.  That is the property
D-3 asks for: the wedge must be impossible, not merely swept.

Prints "2,2,2,2,2" (wedged) or "0,0,0,0,0" (healed) and nothing else.
"""
import os
import sqlite3
import subprocess
import sys
import time

DB, ARM = sys.argv[1], sys.argv[2]
WF = sys.argv[3] if len(sys.argv) > 3 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "wake-fix.py")
SESSION = "mvs_lane24sim00000000000000000000000"
# The template lives in its OWN session so that replanting the dead row (which
# deletes every row of SESSION) cannot delete the row the injector reads as
# its template.  The injector falls back to a global search and says so.
TPL_SESSION = "mvs_lane24simtpl00000000000000000000000"
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lane24-sim-backups")
os.makedirs(BAK, exist_ok=True)

TPL = ('{"agentName":"mavis","clientRequestId":"minimax-code_sim_0",'
       '"createdAt":"%d","itemId":"queue_sim_template","model":'
       '{"provider_id":"minimax","model_id":"MiniMax-M3.1-Flash-Preview"},'
       '"requestedTurnId":"turn_sim_template","sessionId":"%s","source":"api",'
       '"status":"queued","userMessageId":'
       '"msg-user-v1-q0ca3dhwpZb9hWFFFtb-Q9j7Zido0pOjxOWKWZNKfhg"}')

if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.execute("create table local_runtime_queue_items (id integer primary key, "
            "session_id text, item_id text, status text, created_at_ms integer, "
            "data_json text, source text, client_request_id text, "
            "dedupe_key text, expires_at_ms integer, claim_id text, "
            "claim_lease_expires_at_ms integer, routing_fingerprint text)")
con.execute("insert into local_runtime_queue_items (session_id,item_id,status,"
            "created_at_ms,data_json,source,routing_fingerprint) values "
            "(?,?,?,?,?,'api','queue-routing/v1:sim')",
            (TPL_SESSION, "queue_sim_template", "queued", int(time.time() * 1000),
             TPL % (int(time.time() * 1000), TPL_SESSION)))
con.commit()
con.close()

env = dict(os.environ)
env["SOTTO_WAKE_DB"] = DB
env["SOTTO_WAKE_BACKUP_DIR"] = BAK
env["PYTHONIOENCODING"] = "utf-8"

rcs = []
for attempt in range(5):
    # replant the SAME dead row: unclaimed, 120 min old
    con = sqlite3.connect(DB)
    now_ms = int(time.time() * 1000)
    con.execute("delete from local_runtime_queue_items where session_id=?", (SESSION,))
    con.execute("insert into local_runtime_queue_items (session_id,item_id,status,"
                "created_at_ms,data_json,expires_at_ms,claim_id) values "
                "(?,?,'queued',?,'{}',?,NULL)",
                (SESSION, "queue_sim_dead%d" % attempt, now_ms - 120 * 60_000,
                 (now_ms - 1000) if ARM == "expired" else None))
    con.commit()
    con.close()
    p = subprocess.run([sys.executable, WF, "inject", "--session", SESSION,
                        "--stale-mins", "999"],
                       capture_output=True, text=True, env=env)
    rcs.append(p.returncode)

print(",".join(str(x) for x in rcs))
sys.exit(0)