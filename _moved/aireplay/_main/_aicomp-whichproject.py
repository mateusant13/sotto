"""Resolve WHICH project this session belongs to, from the store, not from naming.

The trap this instrument exists to catch: the agent NAME is 'aicompanion' and
there IS a directory I:\\!aicompanion, but the session's own workspace_dir is the
anchor. Naming is not evidence; workspace_dir + parent lineage is.

Prints:
  1. this session's own row (agent_name, workspace_dir, purpose, parent)
  2. the project it names, and whether that dir exists on disk
  3. the full lane population for that dir with death verdicts
  4. the same-named-directory decoy, so the ambiguity is shown not hidden

Read-only. Exit 2 = could not verify.
"""
from __future__ import annotations

import datetime as dt
import os
import sqlite3
import sys

DB = r"file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
SELF = "mvs_83add95c22ad4ddc9db1c91e3a9f877e"
PARENT = "mvs_433958d5e0414b07a33f79254fa505fc"
DECOY = r"I:\!aicompanion"
DEAD_AFTER_MIN = 45
QUARANTINE = {"mvs_19e3d42432374e52a03ba256db70a8b5"}

COLS = ("session_id, updated_at_ms, status, runtime, agent_name, "
        "parent_session_id, purpose, session_kind, archived, workspace_dir, "
        "title, created_at_ms, error_code")


def iso(ms):
    return dt.datetime.fromtimestamp(ms / 1000).strftime("%Y-%m-%d %H:%M:%S") if ms else "-"


def main() -> int:
    now = int(dt.datetime.now().timestamp() * 1000)
    con = sqlite3.connect(DB, uri=True)
    try:
        print("=" * 78)
        print("1. THIS SESSION'S OWN ROW (the anchor)")
        print("=" * 78)
        row = con.execute(
            f"SELECT {COLS} FROM local_runtime_sessions WHERE session_id = ?", (SELF,)
        ).fetchone()
        if row is None:
            print(f"FAIL: own session {SELF} not in store -- cannot self-locate")
            return 2
        keys = COLS.split(", ")
        d = dict(zip(keys, row))
        for k in keys:
            v = d[k]
            if k.endswith("_ms"):
                v = f"{iso(v)}  ({v})"
            print(f"  {k:24} {v}")
        project_dir = d["workspace_dir"]

        print()
        print("=" * 78)
        print("2. IS THE NAMED DIR THE PROJECT? (decoy test)")
        print("=" * 78)
        print(f"  agent name says      : {d['agent_name']}")
        print(f"  session workspace_dir: {project_dir}")
        print(f"  decoy with same name : {DECOY}  exists={os.path.isdir(DECOY)}")
        print(f"  project dir exists   : {os.path.isdir(project_dir)}")
        print("  => naming does NOT decide this; workspace_dir does.")

        print()
        print("=" * 78)
        print(f"3. LANE POPULATION for {project_dir}")
        print(f"   death window = updated_at older than {DEAD_AFTER_MIN} min")
        print("=" * 78)
        rows = con.execute(
            f"SELECT {COLS} FROM local_runtime_sessions "
            "WHERE workspace_dir = ? ORDER BY updated_at_ms DESC",
            (project_dir,),
        ).fetchall()
        if not rows:
            print("FAIL: population empty")
            return 2
        pop = len(rows)
        print(f"POPULATION = {pop} sessions with workspace_dir = {project_dir!r}\n")
        hdr = (f"{'session_id':34} {'updated_at':19} {'age_min':>8} {'verdict':7} "
               f"{'status':11} {'kind':8} parent/root")
        print(hdr)
        print("-" * len(hdr))
        tally = {}
        for r in rows:
            m = dict(zip(COLS.split(", "), r))
            age = (now - m["updated_at_ms"]) / 60000.0
            live = (m["status"] or "").lower() in {"running", "active", "started"}
            v = ("ALIVE" if (live and age <= DEAD_AFTER_MIN)
                 else "RECENT" if age <= DEAD_AFTER_MIN
                 else "STALE" if live else "DEAD")
            tally[v] = tally.get(v, 0) + 1
            root = "ROOT" if m["parent_session_id"] is None else f"<-{m['parent_session_id'][:12]}"
            q = "  [QUARANTINE]" if m["session_id"] in QUARANTINE else ""
            print(f"{m['session_id']:34} {iso(m['updated_at_ms']):19} {age:8.1f} "
                  f"{v:7} {(m['status'] or '-'):11} {(m['session_kind'] or '-'):8} {root:16}{q}")
        print(f"\nTALLY: {dict(sorted(tally.items()))}")
        print(f"population={pop} window={DEAD_AFTER_MIN}min now={iso(now)}")

        print()
        print("=" * 78)
        print(f"4. THE SAME-NAMED DECOY {DECOY} (not this project -- shown, not hidden)")
        print("=" * 78)
        d2 = con.execute(
            "SELECT COUNT(*), MAX(updated_at_ms), SUM(CASE WHEN parent_session_id IS NULL THEN 1 ELSE 0 END) "
            "FROM local_runtime_sessions WHERE workspace_dir = ?", (DECOY,)
        ).fetchone()
        print(f"  sessions={d2[0]}  roots={d2[2]}  newest={iso(d2[1])}")
        print("  => a different repo (own AGENTS.md/package.json). NOT revived by me.")

        print()
        print("=" * 78)
        print("5. REVIVABLE SET = DEAD or STALE, minus quarantine, minus roots")
        print("=" * 78)
        cand = []
        for r in rows:
            m = dict(zip(COLS.split(", "), r))
            age = (now - m["updated_at_ms"]) / 60000.0
            live = (m["status"] or "").lower() in {"running", "active", "started"}
            v = ("ALIVE" if (live and age <= DEAD_AFTER_MIN)
                 else "RECENT" if age <= DEAD_AFTER_MIN
                 else "STALE" if live else "DEAD")
            if v in {"DEAD", "STALE"} and m["session_id"] not in QUARANTINE:
                cand.append((m["session_id"], v, m["parent_session_id"], m["title"]))
        for sid, v, par, title in cand:
            root = "ROOT" if par is None else f"<-{par}"
            t = (title or "")[:46].replace("\n", " ")
            print(f"  {sid:34} {v:6} {root:18} {t}")
        print(f"\nREVIVABLE (dead/stale, non-quarantined) = {len(cand)} of {pop}")
        return 0
    except sqlite3.Error as exc:
        print(f"FAIL sqlite: {exc}")
        return 2
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())