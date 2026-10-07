"""aicompanion lane census -- BOUNDARY DISCOVERY, then death census.

Read-only against runtime-state.sqlite. Never writes. Never touches a session.

Two phases, deliberately separated so the population is not assumed before it is
measured:

  PHASE A (discovery) -- which workspace_dir values exist, how many sessions each,
     and which of them are roots vs children. Prints every distinct dir with a
     count so the project boundary can be READ from the data, not guessed.

  PHASE B (death)    -- for the dirs chosen as "this project", every session with
     its updated_at_ms, status, runtime, parent and purpose.

VERDICT RULE (evidence of death, never naming):
  ALIVE    if status is running/active AND updated within DEAD_AFTER_MIN
  RECENT   if updated within DEAD_AFTER_MIN (but not started)
  STALE    if status says started/active but updated older than DEAD_AFTER_MIN
  DEAD     otherwise (finished/failed/errored, or stale beyond the window)
The window is printed with every count. No verdict is ever emitted without one.

EXIT CODES ARE CONTRACTS: 0 = census printed, 2 = could not verify (never
"success"). --selftest proves the verdict rule can say NO on a known-dead fixture.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
DEAD_AFTER_MIN = 45  # MEASURED choice, stated in output, never silent

QUARANTINE = {"mvs_19e3d42432374e52a03ba256db70a8b5"}


def connect() -> sqlite3.Connection:
    return sqlite3.connect(DB, uri=True)


def iso(ms: int | None) -> str:
    if not ms:
        return "-"
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def verdict(status: str, updated_ms: int, now_ms: int) -> str:
    age_min = (now_ms - updated_ms) / 60000.0
    live = (status or "").lower() in {"running", "active", "started"}
    if age_min <= DEAD_AFTER_MIN and live:
        return "ALIVE"
    if age_min <= DEAD_AFTER_MIN:
        return "RECENT"
    if live:
        return "STALE"
    return "DEAD"


def phase_a(con: sqlite3.Connection, now_ms: int) -> int:
    print("=" * 78)
    print("PHASE A -- WORKSPACE BOUNDARY (population = all sessions in the store)")
    print("=" * 78)
    rows = con.execute(
        """
        SELECT COALESCE(workspace_dir,'(null)')  AS wdir,
               COUNT(*)                          AS n,
               SUM(CASE WHEN parent_session_id IS NULL THEN 1 ELSE 0 END) AS roots,
               MAX(updated_at_ms)                AS newest
          FROM local_runtime_sessions
         WHERE columnar_version = 3
         GROUP BY wdir
         ORDER BY n DESC
        """
    ).fetchall()
    if not rows:
        print("FAIL: census returned zero rows -- store unreadable")
        return 2
    total = sum(r[1] for r in rows)
    print(f"{'workspace_dir':52} {'n':>5} {'roots':>5}  newest")
    for wdir, n, roots, newest in rows:
        print(f"{wdir[:52]:52} {n:>5} {roots:>5}  {iso(newest)}")
    print(f"\nTOTAL sessions with columnar_version=3: {total}")
    print(f"distinct workspace_dir values: {len(rows)}")
    print(f"now (local): {iso(now_ms)}")
    return 0


def phase_b(con: sqlite3.Connection, now_ms: int, match: str) -> int:
    print()
    print("=" * 78)
    print(f"PHASE B -- DEATH CENSUS for workspace_dir LIKE {match!r}")
    print(f"death window = updated_at older than {DEAD_AFTER_MIN} min")
    print("=" * 78)
    rows = con.execute(
        """
        SELECT session_id, updated_at_ms, status, runtime, agent_name,
               parent_session_id, purpose, session_kind, archived,
               workspace_dir, error_code
          FROM local_runtime_sessions
         WHERE columnar_version = 3
           AND workspace_dir LIKE ?
         ORDER BY updated_at_ms DESC
        """,
        (match,),
    ).fetchall()
    if not rows:
        print(f"FAIL: no sessions match {match!r} -- cannot certify any verdict")
        return 2
    print(f"POPULATION = {len(rows)} sessions matching {match!r}\n")
    hdr = f"{'session_id':34} {'updated_at':19} {'age_min':>8} {'verdict':7} {'status':10} parent/root"
    print(hdr)
    print("-" * len(hdr))
    tally: dict[str, int] = {}
    for (sid, upd, status, runtime, agent, parent, purpose, kind,
         archived, wdir, errc) in rows:
        v = verdict(status, upd, now_ms)
        tally[v] = tally.get(v, 0) + 1
        age = (now_ms - upd) / 60000.0
        flag = ""
        if sid in QUARANTINE:
            flag = "  [QUARANTINE -- NEVER TOUCH]"
        root = "ROOT" if parent is None else f"<-{parent[:12]}"
        print(
            f"{sid:34} {iso(upd):19} {age:8.1f} {v:7} "
            f"{(status or '-'):10} {root:18}{flag}"
        )
    print("\nTALLY:", dict(sorted(tally.items())))
    print(f"population={len(rows)}  window={DEAD_AFTER_MIN}min  now={iso(now_ms)}")
    print("NOTE: columns name/agent/purpose/kind/errc archived are printed on "
          "demand only; use --verbose for per-lane detail.")
    if tally.get("ALIVE"):
        print(f"\nALIVE lanes in this population: {tally['ALIVE']} "
              f"-> concurrency budget is shared with them")
    return 0


def selftest() -> int:
    """The control must go RED. A census that cannot say NO is worthless."""
    now = 1_000_000_000_000
    cases = [
        ("running", now - 60_000, "ALIVE"),
        ("running", now - 60 * 60_000, "STALE"),
        ("finished", now - 60_000, "RECENT"),
        ("finished", now - 60 * 60_000, "DEAD"),
        ("failed", now - 90 * 60_000, "DEAD"),
        ("", now - 60 * 60_000, "DEAD"),
    ]
    bad = 0
    for status, upd, want in cases:
        got = verdict(status, upd, now)
        ok = got == want
        bad += 0 if ok else 1
        print(f"{'ok ' if ok else 'RED'} status={status or '(empty)':10} "
              f"want={want:7} got={got}")
    if bad:
        print(f"FAIL selftest: {bad} case(s) wrong")
        return 2
    print("selftest green: verdict rule discriminates ALIVE/STALE/RECENT/DEAD")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["a", "b", "all"], default="all")
    ap.add_argument("--match", default="%sotto%")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--now-ms", type=int, default=0)
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    now_ms = args.now_ms or int(dt.datetime.now().timestamp() * 1000)
    try:
        con = connect()
    except sqlite3.Error as exc:
        print(f"FAIL: cannot open store read-only: {exc}")
        return 2
    try:
        rc = 0
        if args.phase in ("a", "all"):
            rc |= phase_a(con, now_ms)
        if args.phase in ("b", "all"):
            rc |= phase_b(con, now_ms, args.match)
        return rc
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())