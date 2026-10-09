#!/usr/bin/env python3
"""delivery-latency.py — measure queue-wake delivery latency with the AUTHORITATIVE link.

WHY THIS FILE EXISTS
--------------------
Three times today a text match was promoted to proof of mechanism. The correction,
recorded in receipt-23, is that a turn is a QUEUE DELIVERY only when
`local_runtime_turn_ingress.queue_item_ids_json` NAMES a queue item. A `role='user'`
message row proves a MESSAGE ARRIVED; it does not prove the queue brought it.

So this script never greps for a marker. It walks the ingress table, keeps only rows
whose `queue_item_ids_json` is non-null, resolves each named item in
`local_runtime_queue_items`, and reports injected -> delivered latency per item.

Every number carries its POPULATION and its WINDOW. A row that cannot be resolved is
reported as UNRESOLVED, never silently dropped and never rounded to zero.

Read-only. It opens the store with mode=ro.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"


def ts(ms) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return repr(ms)


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else None
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    where = "WHERE i.session_id = ?" if target else ""
    params = (target,) if target else ()

    rows = con.execute(
        "select i.session_id, i.accepted_at_ms, i.queue_item_ids_json, i.status AS turn_status, i.claim_source "
        "from local_runtime_turn_ingress i " + where +
        " order by i.accepted_at_ms desc limit 200", params).fetchall()

    linked = [r for r in rows if r["queue_item_ids_json"]]
    print(f"[{ts(int(datetime.now().timestamp()*1000))}] WINDOW = now")
    print(f"POPULATION = the newest {len(rows)} turn_ingress rows"
          + (f" for session {target}" if target else " (all sessions)")
          + f"; of those, rows whose queue_item_ids_json is NOT NULL = {len(linked)}")

    if not linked:
        print("\nNO queue-linked turns in this window.")
        print("That is a real result, not an error: it means no wake reached a")
        print("session through the queue inside the window examined. To test a")
        print("specific fire, pass the target session id.")
        return 2

    print(f"\n{'item_id':<40} {'injected':<10} {'delivered':<10} {'latency':>10}  session")
    print("-" * 104)
    resolved = unresolved = 0
    lat = []
    for r in linked[:25]:
        acc = r["accepted_at_ms"]
        try:
            ids = json.loads(r["queue_item_ids_json"])
            if isinstance(ids, str):
                ids = [ids]
        except (ValueError, TypeError) as e:
            print(f"  <unparseable queue_item_ids_json: {e!r}>")
            unresolved += 1
            continue
        for item in ids:
            q = con.execute(
                "select item_id, created_at_ms, status, claim_id, source "
                "from local_runtime_queue_items where item_id=?", (item,)).fetchone()
            if q is None:
                # The item was consumed and removed. Fall back to the turn time and
                # say so -- a missing row is NOT zero latency and NOT a delivery.
                print(f"{item[-38:]:<40} {'(row gone)':<10} {ts(acc):<10}"
                      f" {'UNRESOLVED':>10}  {r['session_id']}")
                unresolved += 1
                continue
            delta = (acc - q["created_at_ms"]) / 1000.0
            lat.append(delta)
            resolved += 1
            print(f"{item[-38:]:<40} {ts(q['created_at_ms']):<10} "
                  f"{ts(acc):<10} {delta:>9.1f}s  {r['session_id']}")
            if len(lat) <= 3:
                print(f"{'':<40}   status={q['status']} source={q['source']} "
                      f"claim={q['claim_id']}")

    print(f"\nRESOLVED = {resolved}   UNRESOLVED = {unresolved}")
    if lat:
        lat_sorted = sorted(lat)
        print(f"latency over POPULATION {len(lat)} resolved deliveries: "
              f"min {lat_sorted[0]:.1f}s  median "
              f"{lat_sorted[len(lat_sorted)//2]:.1f}s  max {lat_sorted[-1]:.1f}s")
        print("NOTE: this is INJECTED -> A QUEUE-LINKED TURN EXISTED. It is not")
        print("proved end-to-end delivery: the turn must also carry a role='user'")
        print("message row, and that link is checked separately.")
    return 0


if __name__ == "__main__":
    sys.exit(main())