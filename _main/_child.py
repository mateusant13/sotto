import sqlite3
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
SID = "mvs_a00662bff55242cb9b56c0f1165bdad7"
rows = c.execute("select session_id, status, session_type, archived from local_runtime_sessions where parent_session_id=?", (SID,)).fetchall()
print("POPULACAO: sessoes-filhas deste agente =", len(rows))
from collections import Counter
print("  por status   :", dict(Counter(r[1] for r in rows)))
print("  por tipo     :", dict(Counter(r[2] for r in rows)))
alive = [r for r in rows if r[1] in ("active","running")]
print("  vivas agora  :", len(alive))
