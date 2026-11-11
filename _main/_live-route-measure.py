#!/usr/bin/env python3
"""MEASURE the paint age of every caption the shell received, from the LIVE log.

The question this answers, with numbers and no code reading: did any caption
whose AUDIO is older than a small bound reach the live surface (the overlay)?

Two clocks are in the log, and the arithmetic is done here:

  * `tap_ms` on a LIVE line is the wall clock (ms, epoch) of the block that
    closed it, so `age_ms` in the same line is already honest.
  * a BATCH line has `tap_ms=None` and carries only `end` -- seconds of the
    worker's capture clock. Its audio instant is
    `capture_start_epoch + end`, and `capture_zero` is solved from the live
    lines of the SAME worker session: `tap_ms/1000 - (end + age_ms/1000)`.

The log holds many worker sessions, so the file is split at `BRIDGE_SPAWNED`
and the clock is solved per session -- one zero for the whole file is not a
small error, it is the wrong instrument (217 000 s of spread across sessions).

    python _main\\_live-route-measure.py [--log PATH] [--bound-s 2.5] [--all]
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), 'worker'))
try:
    import live_route as _route
except Exception:                                   # noqa: BLE001
    _route = None

STAMP = (r"^(?P<y>\d{4})-(?P<m>\d\d)-(?P<d>\d\d) "
         r"(?P<H>\d\d):(?P<M>\d\d):(?P<S>\d\d\.\d+)")
CAPTION = re.compile(
    STAMP +
    r" .*?CAPTION_IN start=(?P<start>[^ ]+) end=(?P<end>[^ ]+) final=(?P<final>[^ ]+) "
    r"stable=(?P<stable>[^ ]+) tap_ms=(?P<tap>[^ ]+) age_ms=(?P<age>[^ ]+)")
SPAWN = re.compile(STAMP + r" .*?BRIDGE_SPAWNED pid=(?P<pid>\d+)")


def _epoch(m):
    import datetime
    base = datetime.datetime(int(m["y"]), int(m["m"]), int(m["d"]),
                             int(m["H"]), int(m["M"]), 0)
    return base.timestamp() + float(m["S"])


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sessions(path):
    """[(pid, start_epoch, [caption rows])] -- split at BRIDGE_SPAWNED."""
    out = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "BRIDGE_SPAWNED" in line:
                m = SPAWN.match(line)
                if m:
                    out.append((int(m["pid"]), _epoch(m), []))
                    continue
            if "CAPTION_IN" not in line or not out:
                continue
            m = CAPTION.match(line)
            if not m:
                continue
            out[-1][2].append({
                "at": _epoch(m), "tap": _num(m["tap"]), "end": _num(m["end"]),
                "age_ms": _num(m["age"]), "final": m["final"],
                "stable": m["stable"]})
    return out


def _replay(rows, zero):
    """O MESMO corpus, com a decisao NOVA: quantas pintam?

    A linha de lote entra com a rota que o `engine_switch._run_runner` mesmo
    carimba (`route=redux-batch`, `producer=redux`) e a idade MEDIDA -- o
    veredicto real (`worker/live_route.live_route_verdict`, extraido do fonte)
    decide. A linha viva entra com o `tap_ms` que o log tem; a idade que a guarda
    ve' e' a do EMIT do worker, e o log a mede por `now - tap_ms` no receipt da
    shell (logo este numero e' um TETO para a idade que a guarda ve').
    """
    if _route is None:
        return None
    batch_paint = live_paint = live_refused = 0
    for r in rows:
        if r["end"] is None:
            continue
        if r["tap"] is None:
            payload = {"type": "caption", "text": "x", "route": "redux-batch",
                       "producer": "redux", "end": r["end"],
                       "audio_age_s": max(0.0, r["at"] - (zero + r["end"]))}
            if _route.live_route_verdict(payload)["paint"]:
                batch_paint += 1
        else:
            payload = {"type": "caption", "text": "x", "tap_ms": r["tap"]}
            if _route.live_route_verdict(payload, now_ms=r["at"] * 1000.0)["paint"]:
                live_paint += 1
            else:
                live_refused += 1
    return batch_paint, live_paint, live_refused


def _report(pid, start, rows, bound, verbose):
    zeros = [r["tap"] / 1000.0 - r["end"] - r["age_ms"] / 1000.0
             for r in rows
             if r["tap"] is not None and r["end"] is not None
             and r["age_ms"] is not None]
    if len(zeros) < 5:
        print("session pid=%d captions=%d -- no live clock (skip)" % (pid, len(rows)))
        return 0, 0.0, {}
    zero = statistics.median(zeros)
    batch, live = [], []
    for r in rows:
        if r["end"] is None:
            continue
        age = r["at"] - (zero + r["end"])
        (batch if r["tap"] is None else live).append(age)

    def _over(ages):
        return [a for a in ages if a > bound]

    ob, ol = _over(batch), _over(live)

    def _line(name, ages):
        if not ages:
            return "%s n=0" % name
        ages = sorted(ages)
        return ("%s n=%-5d p50=%8.2f p90=%9.2f max=%9.2f over=%-5d"
                % (name, len(ages), ages[len(ages) // 2],
                   ages[int(len(ages) * 0.9)], ages[-1], len(_over(ages))))

    if verbose or ob or ol:
        print("session pid=%-6d zero_src=%d  %s | %s"
              % (pid, len(zeros), _line("batch", batch), _line("live", live)))
    replay = _replay(rows, zero)
    if replay is not None and (verbose or ob or ol):
        bp, lp, lr = replay
        print("    AFTER  batch_paints=%-4d live_paints=%-5d live_refused=%-4d "
              "(route=redux-batch never paints; live bound 2.5 s)"
              % (bp, lp, lr))
    state = {"batch_paint": 0, "live_paint": 0, "live_refused": 0}
    if replay is not None:
        state = dict(zip(("batch_paint", "live_paint", "live_refused"), replay))
    return len(ob) + len(ol), max(batch + live) if (batch or live) else 0.0, state


def main(argv=None):
    ap = argparse.ArgumentParser(prog="live-route-measure")
    ap.add_argument("--log", default="_main/webview-run.log")
    ap.add_argument("--bound-s", type=float, default=2.5)
    ap.add_argument("--all", action="store_true",
                    help="print every session, not only the ones that painted stale")
    args = ap.parse_args(argv)

    sessions = _sessions(args.log)
    if not sessions:
        print("VERDICT: FAIL no BRIDGE_SPAWNED/CAPTION_IN in %s" % args.log)
        return 2
    print("--- audio age when the shell received the line (s), per worker session ---")
    total = 0
    worst = 0.0
    after = {"batch_paint": 0, "live_paint": 0, "live_refused": 0}
    for pid, start, rows in sessions:
        over, w, state = _report(pid, start, rows, args.bound_s, args.all)
        total += over
        worst = max(worst, w)
        for key in after:
            after[key] += state.get(key, 0)
    print("painted_stale_total=%d bound_s=%.1f worst_audio_age_s=%.2f"
          % (total, args.bound_s, worst))
    print("AFTER_SET batch_paints=%d live_paints=%d live_refused=%d"
          % (after["batch_paint"], after["live_paint"], after["live_refused"]))
    print("VERDICT: %s -- %d caption(s) reached the live surface with audio older "
          "than %.1f s (worst %.2f s)"
          % ("STALE-REACHED" if total else "CLEAN", total, args.bound_s, worst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
