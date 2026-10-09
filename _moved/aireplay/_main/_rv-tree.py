import sqlite3, json, datetime
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
ROOT = "mvs_b7a9f3a7db404912b32d28fc11b83645"
cur.execute("SELECT session_id, parent_session_id, agent_name, session_type, status, title, purpose, created_at_ms, updated_at_ms, record_json FROM local_runtime_sessions")
rows = cur.fetchall()
byid = {}
for r in rows:
    byid[r[0]] = dict(session_id=r[0], parent=r[1], agent=r[2], stype=r[3], status=r[4], title=r[5], purpose=r[6], created=r[7], updated=r[8], rec=r[9])
def ts(ms):
    if not ms: return ""
    return datetime.datetime.fromtimestamp(ms/1000).strftime("%Y-%m-%d %H:%M:%S")
kids = {k:v for k,v in byid.items() if v["parent"]==ROOT}
print("ROOT children POPULATION =", len(kids))
# order by created
def key(k):
    v=byid[k]; return (v["created"] or 0)
for sid in sorted(kids, key=key):
    v = byid[sid]
    gc = [s for s in byid if byid[s]["parent"]==sid]
    print("="*100)
    print("LANE", sid, "| agent=", v["agent"], "| type=", v["stype"], "| status=", v["status"])
    print("  created=", ts(v["created"]), "updated=", ts(v["updated"]))
    print("  title=", (v["title"] or "")[:160])
    print("  purpose=", (v["purpose"] or "")[:160])
    print("  GRANDCHILDREN POPULATION =", len(gc))
    for g in sorted(gc, key=key):
        gv = byid[g]
        print("   -> child", g, "| agent=", gv["agent"], "| type=", gv["stype"], "| status=", gv["status"], "|", ts(gv["created"]))
        print("      title=", (gv["title"] or "")[:150])
        ggc = [s for s in byid if byid[s]["parent"]==g]
        if ggc: print("      great-grandchildren:", len(ggc))
