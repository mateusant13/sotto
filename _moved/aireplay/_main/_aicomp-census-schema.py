"""Read-only schema census of runtime-state.sqlite.

INSTRUMENT. Prints the schema only. Never writes. Never scans table bodies.
House rule: an instrument that cannot say NO is worthless -- this one can:
any sqlite error is caught, printed and re-raised as exit 2.
"""
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"


def main() -> int:
    con = sqlite3.connect(DB, uri=True)
    try:
        rows = con.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table','view') ORDER BY name"
        ).fetchall()
        if not rows:
            print("FAIL: no tables found")
            return 2
        for name, typ in rows:
            print(f"{typ:5} {name}")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())