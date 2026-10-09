#!/usr/bin/env python3
"""Watch for the two deliveries that matter, and report a VERDICT.

Delivery A (queue injection)  : a NEW user-role message row appears in
  local_runtime_message_rows for the target session whose payload contains
  the marker.  This is the only thing that counts as "the cron woke the
  agent" -- the INSERT itself proves nothing, which is the mistake the
  previous turn made.

Delivery B (runtime cron)     : a row appears in local_runtime_v2_cron_runs
  for the probe cron id, with status delivered and session_id set.

Everything prints with POPULATION + WINDOW.  Bounded: exits on first
positive, or at --secs.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def local(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def out(*a) -> None:
    print(*a, flush=True)


def marker_in(blob: str, marker: str) -> bool:
    return marker in (blob or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", required=True)
    ap.add_argument("--marker", required=True)
    ap.add_argument("--cron-id", default=None)
    ap.add_argument("--secs", type=int, default=300)
    ap.add_argument("--poll", type=int, default=10)
    args = ap.parse_args()

    start = int(time.time() * 1000)
    out(f"[WATCH] session={args.session} marker={args.marker!r} "
        f"cron={args.cron_id} window={args.secs}s poll={args.poll}s")
    out(f"[WATCH] POPULATION = all message_rows of that session + all cron "
        f"runs of that cron_id, sampled every {args.poll}s")

    a_done = b_done = False
    deadline = time.time() + args.secs
    n = 0
    while time.time() < deadline:
        n += 1
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row

        # --- Delivery A ---
        # role='user' is LOAD-BEARING and was added after a measured false
        # positive: the first version of this watcher matched the marker in an
        # ASSISTANT row -- my own report, quoting the marker back at the owner.
        # An instrument that matches its own output reports PASS while proving
        # nothing.  Same bug class as the "95 HEARTBEAT messages" count.
        rows = con.execute(
            "select id, msg_id, role, source, created_at_ms, data_json "
            "from local_runtime_message_rows where session_id=? and role='user' "
            "order by rowid desc limit 400", (args.session,)).fetchall()
        hits_a = [r for r in rows if marker_in(r["data_json"], args.marker)]
        if hits_a and not a_done:
            a_done = True
            r = hits_a[0]
            out(f"[{local(r['created_at_ms'])}] DELIVERY-A CONFIRMED: "
                f"queue injection reached the session as a USER message row "
                f"id={r['id']} role={r['role']!r} source={r['source']!r}")
            try:
                d = json.loads(r["data_json"])
                out(f"    payload keys={sorted(d.keys())}")
                out(f"    msg_content={str(d.get('msg_content'))[:300]!r}")
            except (ValueError, TypeError) as e:
                out(f"    payload not JSON-parseable for display: {e!r}")

        # --- Delivery B ---
        if args.cron_id and not b_done:
            runs = con.execute(
                "select run_id, trigger_source, status, session_id, "
                "created_at_ms, delivered_at_ms, error_code, error "
                "from local_runtime_v2_cron_runs where cron_id=? "
                "order by created_at_ms desc limit 3",
                (args.cron_id,)).fetchall()
            if runs:
                b_done = True
                for r in runs:
                    out(f"[{local(r['created_at_ms'])}] DELIVERY-B: cron run "
                        f"status={r['status']} trigger={r['trigger_source']} "
                        f"session={r['session_id']} delivered={local(r['delivered_at_ms'])} "
                        f"err={r['error_code']}")

        # --- queue row state (context, not proof) ---
        q = con.execute(
            "select item_id, status, claim_id, claim_lease_expires_at_ms "
            "from local_runtime_queue_items where session_id=? "
            "order by rowid desc limit 3", (args.session,)).fetchall()
        con.close()
        snap = "; ".join(
            f"{r['item_id'][-8:]}={r['status']}/claim={r['claim_id']}" for r in q)
        out(f"  [{n:02d}] A={a_done} B={b_done} queue: {snap}")

        if a_done and (b_done or not args.cron_id):
            out(f"VERDICT PASS  A={a_done} B={b_done} samples={n}")
            return 0
        time.sleep(args.poll)

    out(f"VERDICT INCONCLUSIVE  A={a_done} B={b_done} samples={n} "
        f"window={args.secs}s  (NOT a negative: no positive observed in the "
        f"window; absence of evidence is not evidence of absence)")
    return 1


if __name__ == "__main__":
    sys.exit(main())