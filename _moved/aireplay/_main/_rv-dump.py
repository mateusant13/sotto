import sqlite3, json, os, datetime
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
VER = ["mvs_a4c053f4d29045818c5298e1e36c0642","mvs_2e2a644a671b4d0cac32dc46aeb699d3",
"mvs_03762d410f7742bba386650146f04cbf","mvs_9c1a6ee2dc9049d7af4d6342f8524e9d",
"mvs_36edbf94c94f45f3975623c86322e66f","mvs_116b631846a74524b859b6a200fca2a7",
"mvs_97c6a61dfa3642ab8a80f3f7f17346d4","mvs_25670c59a6084e1898e1c28bf48c0278",
"mvs_d4cd50d00dd24c6db97944a470576b19","mvs_cba42e5b9a1f47a6b96d59e11d02fda7",
"mvs_e968a220e92f414082e9d54294b31068","mvs_7bdbb1dd705044f995d8ff0d19ff025d",
"mvs_be09576a20dd424eb9bf72d736b1ba86"]
out = r"H:\sotto\_moved\aireplay\_main\_rv-dump"
for sid in VER:
    cur.execute("SELECT title, status FROM local_runtime_sessions WHERE session_id=?", (sid,))
    r = cur.fetchone()
    title = r[0] if r else "?"
    status = r[1] if r else "?"
    cur.execute("SELECT id, role, created_at_ms, data_json FROM local_runtime_message_rows WHERE session_id=? ORDER BY id", (sid,))
    rows = cur.fetchall()
    asst = [x for x in rows if x[1]=="assistant"]
    fname = os.path.join(out, sid[:12] + ".txt")
    with open(fname, "w", encoding="utf-8") as f:
        f.write("SESSION %s\nTITLE %s\nSTATUS %s\nROWS %d ASSISTANT %d\n" % (sid,title,status,len(rows),len(asst)))
        f.write("="*90 + "\n")
        for (mid, role, cms, dj) in asst:
            try:
                txt = (json.loads(dj) or {}).get("msg_content","")
            except Exception as e:
                txt = "<<unparsed: %s>>" % e
            if isinstance(txt, list):
                txt = json.dumps(txt)
            f.write("\n----- ASSISTANT id=%d chars=%d at=%s -----\n" % (mid, len(txt), datetime.datetime.fromtimestamp(cms/1000).strftime("%H:%M:%S")))
            f.write(txt)
    print("%-34s %-8s rows=%-3d asst=%-3d last_chars=%s" % (sid[:12], status, len(rows), len(asst), (len(asst[-1][3]) if asst else 0)))
