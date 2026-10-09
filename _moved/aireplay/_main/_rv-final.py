import sqlite3, json, os, datetime
db = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + db.replace("\\","/") + "?mode=ro", uri=True)
cur = con.cursor()
VER = {"mvs_36edbf94c94f45f3975623c86322e66f":"L1","mvs_03762d410f7742bba386650146f04cbf":"L3",
"mvs_a4c053f4d29045818c5298e1e36c0642":"L8","mvs_2e2a644a671b4d0cac32dc46aeb699d3":"L15",
"mvs_7bdbb1dd705044f995d8ff0d19ff025d":"L14","mvs_116b631846a74524b859b6a200fca2a7":"L16",
"mvs_97c6a61dfa3642ab8a80f3f7f17346d4":"SYNTH28","mvs_d4cd50d00dd24c6db97944a470576b19":"L4-REVERIFY",
"mvs_cba42e5b9a1f47a6b96d59e11d02fda7":"L3-CLOSURES","mvs_e968a220e92f414082e9d54294b31068":"SYNTH28-REV",
"mvs_be09576a20dd424eb9bf72d736b1ba86":"L16-CLOSURES","mvs_9c1a6ee2dc9049d7af4d6342f8524e9d":"L4",
"mvs_25670c59a6084e1898e1c28bf48c0278":"ROUTER"}
out = r"H:\sotto\_moved\aireplay\_main\_rv-final"
os.makedirs(out, exist_ok=True)
for sid, tag in VER.items():
    cur.execute("SELECT id, created_at_ms, data_json FROM local_runtime_message_rows WHERE session_id=? AND role='assistant' ORDER BY id", (sid,))
    rows = cur.fetchall()
    if not rows:
        print("%-14s %-34s NO ASSISTANT ROW" % (tag, sid[:12])); continue
    mid, cms, dj = rows[-1]
    try:
        txt = (json.loads(dj) or {}).get("msg_content","")
    except Exception as e:
        txt = "<<unparsed %s>>" % e
    if isinstance(txt, list): txt = json.dumps(txt)
    fn = os.path.join(out, tag + ".md")
    open(fn, "w", encoding="utf-8").write("<!-- session %s  last assistant row id=%d  at %s -->\n\n%s\n" % (sid, mid, datetime.datetime.fromtimestamp(cms/1000).strftime("%Y-%m-%d %H:%M:%S"), txt))
    verdictline = [l for l in txt.splitlines() if "meet the spec" in l]
    print("%-14s %-34s rows_asst=%-3d lastid=%-7d chars=%-6d verdict=%s" % (tag, sid[:12], len(rows), mid, len(txt), (verdictline[0][:70] if verdictline else "<<NO VERDICT LINE>>")))
