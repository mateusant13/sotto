import sqlite3, json, datetime
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
sid = "mvs_a00662bff55242cb9b56c0f1165bdad7"
rows = c.execute("select item_id,status,created_at_ms,claim_id,claim_lease_expires_at_ms,data_json from local_runtime_queue_items where session_id=? order by created_at_ms desc", (sid,)).fetchall()
print("itens na fila para a TUA sessao:", len(rows))
for r in rows:
    print()
    print("  itemId  :", r[0])
    print("  status  :", r[1])
    print("  criado  :", datetime.datetime.fromtimestamp(r[2]/1000).strftime('%H:%M:%S'))
    print("  claimId :", r[3])
    print("  lease ate:", r[4])
    d = json.loads(r[5])
    print("  attempts:", len(d.get("deliveryAttempts", [])))
    print("  conteudo:", d["message"]["content"][:70])
