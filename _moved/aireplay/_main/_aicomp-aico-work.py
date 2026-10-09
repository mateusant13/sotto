"""I:\\!aicompanion -- identify the work that died, and locate the '17'.

Facts to establish, all read-only:
  A. status breakdown of all 110 lanes (the abnormal-death subset vs clean idle)
  B. does 11 interrupted + 5 error + 1 aborted == 17 ?
  C. are those 17 clustered in time (a fence event) or spread?
  D. the titles/purposes of the MOST RECENT dead lanes -- i.e. what work stopped
  E. the 16 roots, and their death evidence
Exit 2 = could not verify.
"""
from __future__ import annotations

import collections
import datetime as dt
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
W = r"I:\!aicompanion"


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def main() -> int:
    now = int(dt.datetime.now().timestamp() * 1000)
    con = sqlite3.connect(DB, uri=True)
    try:
        rows = con.execute(
            "SELECT session_id, updated_at_ms, status, parent_session_id, purpose, "
            "       title, created_at_ms, archived "
            "  FROM local_runtime_sessions WHERE workspace_dir = ? "
            " ORDER BY updated_at_ms DESC", (W,)).fetchall()
        pop = len(rows)
        print(f"A. POPULATION = {pop}   now={iso(now)}")
        st = collections.Counter(r[2] or "(empty)" for r in rows)
        for k, v in st.most_common():
            print(f"     status {k:14} {v}")
        abnormal = sum(v for k, v in st.items()
                       if k in {"interrupted", "error", "aborted"})
        idle = st.get("idle", 0)
        print(f"     abnormal (interrupted+error+aborted) = {abnormal}")
        print(f"     clean idle                             = {idle}")
        print(f"     abnormal + idle                         = {abnormal + idle} (== pop: "
              f"{abnormal + idle == pop})")

        print()
        print(f"B. DOES THE OWNER'S 17 MAP HERE?")
        print(f"     17 == abnormal({abnormal})? {abnormal == 17}")
        print(f"     17 == idle({idle})?       {idle == 17}")
        print(f"     17 == population({pop})?  {pop == 17}")
        print(f"     NOTE: I:\\!aicompanion has 16 ROOTS. 17 = 16 roots + 1? UNVERIFIED.")

        print()
        print("C. TIME CLUSTERING of the abnormal-death lanes (fence signature)")
        days = collections.Counter(
            dt.datetime.fromtimestamp(r[1] / 1000).strftime("%Y-%m-%d")
            for r in rows if (r[2] or "") in {"interrupted", "error", "aborted"})
        for k, v in sorted(days.items()):
            print(f"     {k}  {v} abnormal lanes")
        print(f"     distinct days = {len(days)} -> "
              f"{'CLUSTERED (fence-like)' if len(days) <= 2 else 'SPREAD (no fence event)'}")

        print()
        print("D. MOST RECENT DEAD LANES -- what work actually stopped")
        for r in rows[:22]:
            sid, upd, status, par, pur, title, cre, arch = r
            age = (now - upd) / 60000.0
            root = "ROOT" if par is None else f"<-{par[:10]}"
            kind = (pur or "").split(":")[0][:26]
            print(f"  {iso(upd)} age={age:7.1f}m {status:12} {root:14} "
                  f"{kind:26} {(title or '-')[:40]}")

        print()
        print("E. THE 16 ROOTS (death evidence per root)")
        for r in rows:
            if r[3] is not None:
                continue
            sid, upd, status, par, pur, title, cre, arch = r
            age = (now - upd) / 60000.0
            kids = sum(1 for x in rows if x[3] == sid)
            print(f"  {sid} {iso(upd)} age={age:8.1f}m {status:12} children={kids:3} "
                  f"{(title or '-')[:44]}")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())