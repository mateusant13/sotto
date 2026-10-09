#!/usr/bin/env python3
"""lane24 D-7, part 2: WHICH signal predicts `mcode exec` acceptance?

Ground truth = the 2 measured refusals (POP=2, both rc=4, both
"Session already has an active Turn", 13:05:05 and 13:08:59).

A signal is only a PREDICTOR if it was TRUE at the instant of a refusal.
Two bugs in the first version of this script, both named rather than hidden:
  * local_runtime_session_locks is CURRENT-STATE ONLY.  Rows are deleted when
    the turn completes (the 13:07:11 lease was present at 13:10:46 and gone by
    13:11:07, the turn having completed 13:10:53), so querying it today says
    nothing about 13:05.  Good LIVE predicate, useless HISTORICAL one.
  * "completed_at_ms is not null" is NOT "was finished at that instant".
    Both timestamps are retained, so the comparison must be against the
    instant.  The buggy version reported both refusals as FINISHED.
"""
import datetime
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
SESSION = "mvs_a00662bff55242cb9b56c0f1165bdad7"
now_ms = int(time.time() * 1000)
REFUSALS = (("13:05:05", 1791389105000), ("13:08:59", 1791389339000))


def ts(ms):
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S")
    except Exception:
        return repr(ms)


con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row

print("=== each refusal, reconstructed at the instant (POP=2) ===")
for label, at in REFUSALS:
    sess = con.execute("select status from local_runtime_sessions where session_id=?",
                       (SESSION,)).fetchone()["status"]
    ing = con.execute(
        "select turn_id, status, accepted_at_ms, completed_at_ms "
        "from local_runtime_turn_ingress where session_id=? and accepted_at_ms <= ? "
        "order by accepted_at_ms desc limit 1", (SESSION, at)).fetchone()
    done_at = (ing["completed_at_ms"] is not None
               and int(ing["completed_at_ms"]) <= at)
    print(f"\n  {label} exec REFUSED rc=4 (ground truth: a turn WAS active)")
    print(f"    A  sessions.status            = {sess!r}   -> PREDICTS-BUSY? "
          f"{sess != 'idle'}")
    print(f"    D  newest turn accepted       = {ts(ing['accepted_at_ms'])} "
          f"completed_at={ts(ing['completed_at_ms'])}")
    print(f"       was it OPEN at {label}?      = {not done_at}   -> PREDICTS-BUSY? "
          f"{not done_at}")

print("\n=== TURN DURATION DISTRIBUTION, whole population (not top-N) ===")
d = con.execute("select (completed_at_ms - accepted_at_ms) / 60000.0 "
                "from local_runtime_turn_ingress "
                "where completed_at_ms is not null").fetchall()
mins = sorted(r[0] for r in d)
if mins:
    n = len(mins)
    print(f"  POP completed turns = {n}")
    for lbl, v in (("min", mins[0]), ("median", mins[n // 2]),
                   ("p90", mins[int(n * 0.90)]), ("p99", mins[int(n * 0.99)]),
                   ("max", mins[-1])):
        print(f"    {lbl:<7} {v:8.1f} min")

print("\n=== unfinished turns: can the ingress signal WEDGE the channel? ===")
u = con.execute("select session_id, status, accepted_at_ms from "
                "local_runtime_turn_ingress where completed_at_ms is null "
                "order by accepted_at_ms").fetchall()
print(f"  POP unfinished (whole store) = {len(u)}")
for x in u:
    print(f"    sess={x['session_id']} status={x['status']} "
          f"accepted={ts(x['accepted_at_ms'])} "
          f"age={(now_ms - x['accepted_at_ms']) / 60000.0:.1f}min")
print("  The ingress signal carries NO expiry of its own, so it is used only")
print("  BOUNDED BY AGE; the lease carries a real expiry and is used as the")
print("  primary.  Both are backstops: no pre-flight signal can be perfect,")
print("  which is why the driver also falls back to the QUEUE on refusal.")

print("\n=== locks table hygiene (why the lease cannot rot) ===")
h = con.execute("select owner_kind, count(*) n, "
                "sum(case when expires_at_ms is null then 1 else 0 end) no_exp, "
                "sum(case when expires_at_ms <= ? then 1 else 0 end) expired "
                "from local_runtime_session_locks group by owner_kind",
                (now_ms,)).fetchall()
print(f"  POP rows (whole table) = "
      f"{con.execute('select count(*) from local_runtime_session_locks').fetchone()[0]}")
for k in h:
    print(f"    owner_kind={k['owner_kind']!r} n={k['n']} "
          f"without_expiry={k['no_exp']} already_expired={k['expired']}")