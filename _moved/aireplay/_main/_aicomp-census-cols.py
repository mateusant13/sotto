"""Print the column list of local_runtime_sessions. Read-only, no body scan."""
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    try:
        rows = con.execute("PRAGMA table_info(local_runtime_sessions)").fetchall()
        if not rows:
            print("FAIL: table has no columns")
            return 2
        for cid, name, typ, notnull, dflt, pk in rows:
            print(f"{cid:3} {name:34} {typ:12} pk={pk}")
        print("--- indexes ---")
        for r in con.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='index' "
            "AND tbl_name='local_runtime_sessions'"
        ):
            print(r[0], "|", r[1])
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())