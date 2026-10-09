import sqlite3, json, os, datetime, re
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
VER = {"mvs_36edbf94c94f45f3975623c86322e66f":"L1","mvs_03762d410f7742bba386650146f04cbf":"L3",
"mvs_a4c053f4d29045818c5298e1e36c0642":"L8","mvs_2e2a644a671b4d0cac32dc46aeb699d3":"L15"}
for sid, tag in VER.items():
    print("#"*100)
    print("###", tag, sid)
    cur.execute("SELECT id, created_at_ms, data_json FROM local_runtime_message_rows WHERE session_id=? AND role='assistant' ORDER BY id", (sid,))
    for mid, cms, dj in cur.fetchall():
        try: txt = (json.loads(dj) or {}).get("msg_content","")
        except Exception: txt = ""
        if isinstance(txt, list): txt = json.dumps(txt)
        if not txt: 
            print("  id=%-7d at=%s chars=0 (tool call)" % (mid, datetime.datetime.fromtimestamp(cms/1000).strftime("%H:%M:%S")))
            continue
        heads = re.findall(r"^#{2,3} .*$", txt, re.M)
        hl = " ; ".join(h.strip() for h in heads)[:150]
        print("  id=%-7d at=%s chars=%-6d %s" % (mid, datetime.datetime.fromtimestamp(cms/1000).strftime("%H:%M:%S"), len(txt), hl))
