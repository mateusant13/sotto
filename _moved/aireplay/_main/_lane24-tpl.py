import sqlite3, json, sys, base64
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
c=sqlite3.connect("file:"+DB+"?mode=ro", uri=True); c.row_factory=sqlite3.Row
r=c.execute("select session_id,item_id,status,created_at_ms,expires_at_ms,claim_id,data_json from local_runtime_queue_items where routing_fingerprint is not null order by rowid desc limit 1").fetchone()
print("item", r["item_id"], "sess", r["session_id"], "status", r["status"], "exp", r["expires_at_ms"])
d=json.loads(r["data_json"])
for k in sorted(d):
    v=d[k]
    print(f"  {k} = {str(v)[:90]!r}")
mid=d.get("userMessageId","")
print("userMessageId len =", len(mid), repr(mid))
body=mid[len("msg-user-v1-"):]
print("body len", len(body), "urlsafe-decodable:", end=" ")
try:
    print(len(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))))
except Exception as e:
    print("no:", e)
print("has expiresAtMs key in data_json:", "expiresAtMs" in d)
