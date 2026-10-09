import sqlite3, datetime, json
c = sqlite3.connect(r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite")
for sid in ("mvs_29d66ede958940f7bfa1825617","mvs_8344c99a1bee40cb9552cdf440"):
    r = c.execute("select session_id,created_at_ms,workspace_dir,origin_cron_id,parent_session_id,purpose,session_type,status,title from local_runtime_sessions where session_id=?", (sid,)).fetchone()
    if r:
        print(r[0])
        print("   criado   :", datetime.datetime.fromtimestamp(r[1]/1000).strftime('%H:%M:%S'))
        print("   workspace:", r[2])
        print("   cron_id  :", r[3])
        print("   parent   :", r[4])
        print("   purpose  :", (r[5] or "")[:90])
        print("   type/stat:", r[6], "/", r[7])
        print("   title    :", (r[8] or "")[:70])
        print()
