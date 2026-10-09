"""Liveness cross-check: is 'recent' == live work, or merely touched files?

Read-only (mode=ro, uri=True, PRAGMA query_only). Joins the sqlite session
registry against the on-disk session dirs measured by the filesystem probe.

All windows are relative to a single pinned instant.
"""
import json
import os
import sqlite3
import time

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
ROOT = r"C:\Users\Administrador\.minimax\v2\sessions"
HORIZON_S = 3600
NOW = time.time()
NOW_MS = int(NOW * 1000)
CUT_MS = NOW_MS - HORIZON_S * 1000

out = {
    "probe_instant_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW)),
    "horizon_s": HORIZON_S,
    "cutoff_ms": CUT_MS,
}

uri = "file:" + DB.replace("\\", "/") + "?mode=ro"
con = sqlite3.connect(uri, uri=True, timeout=5)
con.execute("PRAGMA query_only = ON")
cur = con.cursor()

# Which ms column is actually populated, and over what range?
cur.execute(
    "SELECT COUNT(*), MIN(created_at_ms), MAX(created_at_ms),"
    "       MIN(updated_at_ms), MAX(updated_at_ms) FROM local_runtime_sessions")
tot, cmin, cmax, umin, umax = cur.fetchone()
out["sessions_table_range"] = {
    "rows": tot, "created_min_ms": cmin, "created_max_ms": cmax,
    "updated_min_ms": umin, "updated_max_ms": umax,
    "now_ms": NOW_MS,
    "note": "max(updated_at_ms) vs now_ms shows whether ms is epoch-based",
}

# population: ALL registered sessions (no filter)
cur.execute("SELECT COUNT(*) FROM local_runtime_sessions")
out["all_registered_sessions"] = cur.fetchone()[0]

# population: registered sessions updated inside the horizon
cur.execute("SELECT COUNT(*) FROM local_runtime_sessions"
            " WHERE updated_at_ms >= ?", (CUT_MS,))
out["registered_sessions_updated_within_horizon"] = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM local_runtime_sessions"
            " WHERE created_at_ms >= ?", (CUT_MS,))
out["registered_sessions_created_within_horizon"] = cur.fetchone()[0]

# status breakdown -- 'recent' files do NOT imply live work if status is dead
cur.execute("SELECT status, COUNT(*) FROM local_runtime_sessions"
            " WHERE updated_at_ms >= ? GROUP BY status ORDER BY 2 DESC", (CUT_MS,))
out["recent_sessions_by_status"] = {str(k): v for k, v in cur.fetchall()}

# Does each recent session dir have a matching history dir on disk?
cur.execute("SELECT session_id, history_relative_dir FROM local_runtime_sessions"
            " WHERE updated_at_ms >= ? LIMIT 400", (CUT_MS,))
rows = cur.fetchall()
found = missing = 0
examples = []
for sid, hdir in rows:
    if not hdir:
        missing += 1
        continue
    # history_relative_dir is relative to sessions/<y>/<m>/<d>/
    parts = hdir.replace("\\", "/").split("/")
    full = os.path.join(ROOT, *parts)
    if os.path.isdir(full):
        found += 1
        if len(examples) < 5:
            examples.append({"session_id": sid, "history_relative_dir": hdir,
                             "resolved": full, "exists": True})
    else:
        missing += 1
        if len(examples) < 5:
            examples.append({"session_id": sid, "history_relative_dir": hdir,
                             "resolved": full, "exists": False})
out["recent_session_dirs_on_disk"] = {
    "population": (f"registered sessions updated within {HORIZON_S}s, "
                   "capped at 400 rows"),
    "rows_examined": len(rows),
    "dir_exists_on_disk": found,
    "dir_missing_or_no_path": missing,
    "examples": examples,
}

con.close()
print(json.dumps(out, indent=2))