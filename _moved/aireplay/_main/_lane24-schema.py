import sqlite3
c=sqlite3.connect("file:C:\\Users\\Administrador\\.minimax\\v2\\sqlite\\runtime-state.sqlite?mode=ro",uri=True)
print(c.execute("select sql from sqlite_master where name='local_runtime_v2_cron_runs'").fetchone()[0])
