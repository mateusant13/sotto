import sqlite3
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
c = sqlite3.connect(DB, timeout=15)
rows = c.execute("select item_id, data_json from local_runtime_queue_items where session_id=? and status='queued'",
                 ("mvs_a00662bff55242cb9b56c0f1165bdad7",)).fetchall()
import json
for iid, dj in rows:
    d = json.loads(dj)
    d["message"]["content"] = ("[HEARTBEAT] Pass automatico. Continua o plano do Sotto: "
        "H:\\sotto\\_moved\\aireplay\\ROADMAP.md. Pesquisa primeiro, roadmap, depois constroi. "
        "Frontend no fim. Um so app. Le o ultimo receipt antes de repetir trabalho. "
        "Se estiveres bloqueado, diz o bloqueio pelo nome em vez de fingir progresso.")
    c.execute("update local_runtime_queue_items set data_json=? where item_id=?", (json.dumps(d), iid))
    print("substituida:", iid)
c.commit(); c.close()
