# READ-ONLY probe. Does the live store actually contain message rows whose
# data_json yields content() == None?  That is the condition review-synthesis.ps1
# crashes on (line 53: content(d).strip()).
# Prints POPULATION and WINDOW. Writes nothing anywhere.
import sqlite3, json, sys, collections

DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
PARENT = sys.argv[1] if len(sys.argv) > 1 else "mvs_b7a9f3a7db404912b32d28fc11b83645"

c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)


def content(d):
    """VERBATIM copy of content() as embedded in _main/review-synthesis.ps1:36-39"""
    try:
        j = json.loads(d)
    except Exception:
        return ""
    return j.get("msg_content") if isinstance(j, dict) else ""


kids = c.execute(
    "select session_id from local_runtime_sessions where parent_session_id=?", (PARENT,)
).fetchall()

pop = 0
hits = 0
kinds = collections.Counter()
detail = []
for (sid,) in kids:
    msgs = c.execute(
        "select id, role, data_json from local_runtime_message_rows "
        "where session_id=? order by id",
        (sid,),
    ).fetchall()
    for mid, role, d in msgs:
        pop += 1
        v = content(d)
        if v is None:
            hits += 1
            kinds[role] += 1
            if len(detail) < 8:
                try:
                    j = json.loads(d)
                    keys = sorted(j.keys())[:12] if isinstance(j, dict) else type(j).__name__
                except Exception:
                    keys = "<unparseable>"
                detail.append((sid[:20], mid, role, keys))

print("PROBE POPULATION = %d message rows across %d child sessions" % (pop, len(kids)))
print("ROWS WHERE content()==None = %d" % hits)
print("BY ROLE = %s" % dict(kinds))
for sid, mid, role, keys in detail:
    print("  NULL-CONTENT %s mid=%s role=%s json_keys=%s" % (sid, mid, role, keys))
print("CRASH-WORTHY = %s" % ("YES" if hits else "NO (latent only)"))