import sqlite3
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
c = sqlite3.connect("file:%s?mode=ro" % DB.replace("\\","/"), uri=True)
print("msg rows by (source, role, prefix):")
for r in c.execute("""select source, role, case when msg_id like 'msg-user-v1-%' then 'msg-user-v1'
   else substr(msg_id,1,14) end p, count(*) from local_runtime_message_rows
   group by 1,2,3 order by 4 desc limit 25"""):
    print("  ", r)
print()
print("session mvs_SELFTEST_throwaway rows:", c.execute("select count(*) from local_runtime_message_rows where session_id='mvs_SELFTEST_throwaway'").fetchone()[0])
print("session mvs_SELFTEST_throwaway queue rows:", c.execute("select count(*) from local_runtime_queue_items where session_id='mvs_SELFTEST_throwaway'").fetchone()[0])
print("msg-user-v1 sources:", c.execute("select source, count(*) from local_runtime_message_rows where msg_id like 'msg-user-v1-%' group by 1 order by 2 desc limit 10").fetchall())
