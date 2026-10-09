import sqlite3, json
from datetime import datetime
DB=r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con=sqlite3.connect(f"file:{DB}?mode=ro", uri=True); con.row_factory=sqlite3.Row
def L(ms):
    try: return datetime.fromtimestamp(int(ms)/1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
def cols(t): return [r["name"] for r in con.execute(f"pragma table_info({t})")]
for t in ("local_runtime_turn_ingress","local_runtime_turn_ingress_client_requests","local_runtime_session_locks"):
    print(f"== {t} cols = {cols(t)}")
print()
print("== turn_ingress: newest 10 (POP=3686) ==")
ci=cols("local_runtime_turn_ingress")
tcol = "created_at_ms" if "created_at_ms" in ci else ci[0]
for r in con.execute(f"select * from local_runtime_turn_ingress order by rowid desc limit 10"):
    d=dict(r)
    keep={k:(L(v) if k.endswith("_ms") and isinstance(v,int) else (str(v)[:70] if v is not None else None)) for k,v in d.items()}
    print("  ", json.dumps(keep, ensure_ascii=False)[:400])
print()
print("== session_locks (POP=17) ==")
for r in con.execute("select * from local_runtime_session_locks"):
    print("  ", json.dumps({k:(L(v) if k.endswith('_ms') and isinstance(v,int) else str(v)[:40]) for k,v in dict(r).items()}, ensure_ascii=False)[:300])
con.close()
