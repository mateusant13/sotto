"""Do lanes exist in the PRE-v2 store? Read-only. Answers NO honestly."""
import sqlite3
import sys

OLD = r"file:C:/Users/Administrador/.minimax/sqlite.db?mode=ro"


def main() -> int:
    try:
        con = sqlite3.connect(OLD, uri=True)
    except sqlite3.Error as exc:
        print(f"FAIL open: {exc}")
        return 2
    try:
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("tables:", names)
        if not names:
            print("FAIL: pre-v2 store has no tables")
            return 2
        for t in names:
            if "session" not in t.lower():
                continue
            n = con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            print(f"  {t}: {n} rows")
            cols = [c[1] for c in con.execute(f'PRAGMA table_info("{t}")')]
            print(f"    cols: {cols}")
            if n and any("dir" in c.lower() or "workspace" in c.lower() for c in cols):
                wcol = next(c for c in cols if "dir" in c.lower() or "workspace" in c.lower())
                rows = con.execute(
                    f'SSELECT 1' if False else
                    f'SELECT "{wcol}", COUNT(*) FROM "{t}" '
                    f"WHERE LOWER(\"{wcol}\") LIKE '%aireplay%' "
                    f'   OR LOWER("{wcol}") LIKE "%sotto%" '
                    f'GROUP BY "{wcol}"').fetchall()
                print(f"    aireplay/sotto rows in {wcol}: {rows if rows else '(none)'}")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())