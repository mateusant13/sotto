import sqlite3, json, os, datetime
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
WANT = [229300,229489,229562,229790,230154,227864,228167,228226,228145,228352,234123]
out = r"H:\sotto\_moved\aireplay\_main\_rv-final"
for mid in WANT:
    cur.execute("SELECT session_id, created_at_ms, data_json FROM local_runtime_message_rows WHERE id=?", (mid,))
    r = cur.fetchone()
    if not r: print("MISSING", mid); continue
    sid, cms, dj = r
    try: txt = (json.loads(dj) or {}).get("msg_content","")
    except Exception: txt = ""
    if isinstance(txt, list): txt = json.dumps(txt)
    fn = os.path.join(out, "row%d-%s.md" % (mid, sid[:8]))
    open(fn,"w",encoding="utf-8").write("<!-- session %s row %d at %s chars=%d -->\n\n%s\n" % (sid, mid, datetime.datetime.fromtimestamp(cms/1000).strftime("%Y-%m-%d %H:%M:%S"), len(txt), txt))
    print("%-7d %-10s chars=%-6d %s" % (mid, sid[:8], len(txt), fn.split("\\")[-1]))
