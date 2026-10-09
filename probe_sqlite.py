"""Read-only inventory of runtime-state.sqlite. Never copied; mode=ro + uri=True.

Bounded queries only -- the store is ~3.6 GB, so no unbounded COUNT(*) over
huge tables. Used solely to cross-check whether the recent session dirs
correspond to registered sessions.
"""
import json
import os
import sqlite3
import time

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
NOW = time.time()
out = {"db": DB, "size": os.path.getsize(DB), "probe_instant_utc":
       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW))}

uri = "file:" + DB.replace("\\", "/") + "?mode=ro"
con = sqlite3.connect(uri, uri=True, timeout=5)
con.execute("PRAGMA query_only = ON")
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
out["tables"] = tables

# column shapes, cheap
cols = {}
for t in tables:
    try:
        cur.execute('PRAGMA table_info("%s")' % t.replace('"', '""'))
        cols[t] = [r[1] for r in cur.fetchall()]
    except sqlite3.Error as exc:
        cols[t] = ["ERR " + repr(exc)]
out["columns"] = cols

# bounded counts only on tables that look like a session registry
def bounded_count(table, limit=200000):
    try:
        cur.execute('SELECT COUNT(*) FROM (SELECT 1 FROM "%s" LIMIT %d)'
                    % (table.replace('"', '""'), limit))
        return cur.fetchone()[0], "capped at %d" % limit
    except sqlite3.Error as exc:
        return None, "ERR " + repr(exc)

reg = {}
for t in tables:
    if any(k in t.lower() for k in ("session", "lane", "task", "agent")):
        reg[t] = bounded_count(t)
out["bounded_counts"] = reg
con.close()

print(json.dumps(out, indent=2))