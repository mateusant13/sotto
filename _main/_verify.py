import sqlite3, json
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
for iid, dj in c.execute("select item_id,data_json from local_runtime_queue_items where session_id=? and status='queued'", ("mvs_a00662bff55242cb9b56c0f1165bdad7",)):
    d = json.loads(dj)
    print("itemId     :", iid)
    print("status     :", d["status"])
    print("userMessageId:", d["userMessageId"][:40])
    print("content    :", d["message"]["content"][:100])
