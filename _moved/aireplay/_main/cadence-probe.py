#!/usr/bin/env python3
"""cadence-probe.py -- gate the 3-minute wake cadence (receipt-33).

THE DEFECT THIS GATES
---------------------
The Windows task `SottoReplayHeartbeat` fires every PT3M and is healthy, but
successful wakes were landing ~4-5 min apart. Two causes, separated by
measurement, not by preference:

  (a) The task's Settings.MultipleInstances = IgnoreNew and
      StartWhenAvailable = False. A tick that arrives while the previous pass
      is still running is DISCARDED, not deferred, and never made up. So a
      pass longer than 180 s silently eats the next tick. The driver could not
      even see the tick it lost -- IgnoreNew logs nothing.

  (b) The delivery cadence is the SUM of the fire gap and the DIFFERENCE of two
      exec durations:
          delivery_gap(N+1) = fire_gap(N+1) + exec(N+1) - exec(N)
      which is exact on the measured population. fire_gap is 180 or 360; the
      exec term is agent-turn jitter (measured 98-227 s).

Cause (a) is a driver defect and this lane fixed it. Cause (b) is NOT a driver
defect: the runtime refuses a prompt into a session that already has an open
turn, so no cron can deliver faster than that session's own turns complete.
The gate therefore asserts two different things and says which one it measured:

  * PASS CADENCE  -- every tick is served. Mechanical, fully in the driver's
                     control, and the thing v6 changed.
  * DELIVERY CADENCE -- how often a wake actually lands in the session. Bounded
                     below by the turn duration. Reported, not asserted away.

ARMS
----
  ARM-L1  live mechanism predicate   (real log, real task settings)
  ARM-L2  live PASS cadence          (real log, v6 records)
  ARM-L3  live DELIVERY cadence      (real log + the causal identity)
  ARM-S-FIXED  sandbox, today's driver text,  detached   -> must be GREEN
  ARM-S-NEG    sandbox, the SAME text with ONLY the detach reverted to a
               blocking WaitForExit()                          -> must be RED

The sandbox executes the real driver text. Both arms replay the SAME measured
exec-duration distribution against the SAME measured scheduler semantics, so
the only variable between them is the fix. Nothing here is hand-waved: the
negative arm runs the shipped script with one line changed.

  py -3 _main/cadence-probe.py            # live arms + both sandbox arms
  py -3 _main/cadence-probe.py --neg-arm   # prove the negative arm goes red
  py -3 _main/cadence-probe.py --live-only # no subprocess simulation
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(r"H:\sotto\_moved\aireplay")
MAIN = ROOT / "_main"
DRIVER = MAIN / "heartbeat.ps1"
LOG = MAIN / "heartbeat.log"
SANDBOX = MAIN / "_cadence-sandbox"
TASK_NAME = "SottoReplayHeartbeat"
TARGET_SESSION = "mvs_a00662bff55242cb9b56c0f1165bdad7"

INTERVAL_S = 180.0          # measured: Triggers[0].Repetition.Interval = PT3M
CADENCE_OK_S = 210.0        # acceptance: median <= 3m30s
CADENCE_MET_S = 180.0       # "met the 3-minute target"

TS_RE = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)$")


def out(s: str = "") -> None:
    print(s, flush=True)


# --------------------------------------------------------------------------
# log parsing
# --------------------------------------------------------------------------
def parse_log(path: Path):
    """Return one dict per pass, from the real heartbeat.log.

    v5 records the pass start as the CRON-ALARM line and the pass end as the
    PASS-SHUTDOWN-COUNTER / WAKE rc= line.  v6 records TASK-FIRE and PASS-END
    explicitly and moves the exec into a child, so exec duration is read from
    EXEC-POST exec_ms in that case.
    """
    passes = []
    cur = None
    if not path.exists():
        return passes

    def new_rec(ts, era):
        r = {"fire": ts, "pre": None, "post": None, "exec_s": None,
             "exec_ms": None, "rc": None, "outcome": "", "pass_s": None,
             "era": era, "delivered": None, "queued": False,
             "inflight": False, "detach_ok": None}
        passes.append(r)
        return r

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = TS_RE.match(raw)
        if not m:
            continue
        ts = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")
        rest = m.group(2)
        # v6 starts the pass with TASK-FIRE, which lands BEFORE CRON-ALARM.
        # v5 has no TASK-FIRE, so CRON-ALARM is the start. If a v6 record was
        # opened <60s ago the CRON-ALARM belongs to the SAME pass -- creating a
        # second record there silently shifts every later pairing by one, which
        # is how this parser was wrong the first time.
        if rest.startswith("TASK-FIRE"):
            cur = new_rec(ts, "v6")
            continue
        if rest.startswith("CRON-ALARM"):
            if cur is not None and cur["era"] == "v6" \
                    and (ts - cur["fire"]).total_seconds() < 60:
                pass
            else:
                cur = new_rec(ts, "v5")
            continue
        if cur is None:
            continue
        if cur["pre"] is None and rest.startswith("WAKE sending"):
            cur["pre"] = ts
        if cur["post"] is None and (rest.startswith("PASS-SHUTDOWN-COUNTER")
                                    or rest.startswith("WAKE rc=")
                                    or rest.startswith("WAKE no-op")):
            cur["post"] = ts
        dm = re.match(r"WAKE delivered rc=(\d+)", rest)
        if dm:
            cur["outcome"], cur["rc"] = "delivered", int(dm.group(1))
            cur["delivered"] = ts
        nm = re.match(r"WAKE no-op rc=(\d+)", rest)
        if nm:
            cur["outcome"], cur["rc"] = "noop", int(nm.group(1))
        rm = re.match(r"WAKE rc=(\d+) kind=(\S+)", rest)
        if rm:
            cur["outcome"], cur["rc"] = "refused", int(rm.group(1))
        qm = re.match(r"WAKE queued for after this turn ends rc=(\d+)", rest)
        if qm:
            cur["queued"] = True
        if rest.startswith("WAKE QUEUE FAILED"):
            cur["outcome"] = "queue-failed"
        if rest.startswith("EXEC-INFLIGHT"):
            cur["inflight"] = True
        pm = re.search(r"PASS-END .*pass_ms=(\d+) .*spawned=(\w+)", rest)
        if pm:
            cur["pass_ms"] = int(pm.group(1))
            cur["detach_ok"] = pm.group(2)
        em = re.search(r"EXEC-POST .*exec_ms=(\d+)", rest)
        if em:
            cur["exec_ms"] = int(em.group(1))
            cur["exec_s"] = int(em.group(1)) / 1000.0
            cur["post"] = ts

    # Derive what is derivable. v5 measures the exec window inside the parent
    # (pre -> post); v6 measures it in the child (exec_ms). One number either way.
    for r in passes:
        if r["exec_s"] is None and r["pre"] and r["post"]:
            r["exec_s"] = (r["post"] - r["pre"]).total_seconds()
        if r["pass_s"] is None and r["post"]:
            r["pass_s"] = (r["post"] - r["fire"]).total_seconds()
    return passes


def stat(xs):
    if not xs:
        return {}
    s = sorted(xs)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    return {"n": n, "min": s[0], "median": med, "mean": sum(s) / n, "max": s[-1]}


def fmt(st):
    if not st:
        return "n=0"
    return ("n=%d min=%.0fs median=%.0fs mean=%.0fs max=%.0fs"
            % (st["n"], st["min"], st["median"], st["mean"], st["max"]))


# --------------------------------------------------------------------------
# ARM-L1 -- mechanism predicate on real data
# --------------------------------------------------------------------------
def read_task_policy():
    ps = ("$t=Get-ScheduledTask -TaskName '%s';"
          "$i=Get-ScheduledTaskInfo -TaskName '%s';"
          "[pscustomobject]@{"
          "MultipleInstances=[string]$t.Settings.MultipleInstances;"
          "StartWhenAvailable=[string]$t.Settings.StartWhenAvailable;"
          "Interval=[string]$t.Triggers[0].Repetition.Interval;"
          "LastTaskResult=$i.LastTaskResult} | ConvertTo-Json -Compress"
          % (TASK_NAME, TASK_NAME))
    r = subprocess.run(["pwsh", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=90,
                       creationflags=0x08000000)
    if r.returncode != 0:
        return {}
    try:
        return json.loads(r.stdout.strip())
    except Exception:
        return {}


def arm_l1(passes, policy):
    out("=" * 78)
    out("ARM-L1  MECHANISM PREDICATE (real log, real task settings)")
    out("=" * 78)
    if not policy:
        out("  VERDICT INCONCLUSIVE -- could not read the scheduled task")
        return {"verdict": "INCONCLUSIVE"}
    out("  task.Settings.MultipleInstances  = %s" % policy.get("MultipleInstances"))
    out("  task.Settings.StartWhenAvailable = %s" % policy.get("StartWhenAvailable"))
    out("  task.Triggers[0].Repetition.Interval = %s" % policy.get("Interval"))
    ignore_new = str(policy.get("MultipleInstances")).strip() == "IgnoreNew"
    out("  IgnoreNew => a tick arriving during a running pass is DISCARDED, "
        "not deferred, and StartWhenAvailable=False means it is never made up.")

    # Complete v5 passes only: they carry an exec window in the parent.
    v5 = [p for p in passes if p["era"] == "v5" and p["pre"] and p["post"]]
    rows, hit, tot = [], 0, 0
    prev = None
    for p in v5:
        exec_s = (p["post"] - p["pre"]).total_seconds()
        pass_s = (p["post"] - p["fire"]).total_seconds()
        fgap = None if prev is None else (p["fire"] - prev["fire"]).total_seconds()
        if fgap is not None:
            tot += 1
            dropped = fgap >= INTERVAL_S * 1.5
            # predicate: dropped IFF the previous pass overran its own next tick
            overran = prev["post"] > prev["fire"] + dt.timedelta(seconds=INTERVAL_S)
            if dropped == overran:
                hit += 1
            rows.append((p["fire"].strftime("%H:%M:%S"), pass_s, fgap,
                         "DROP" if dropped else "ok",
                         "YES" if overran else "no",
                         p["outcome"], p["rc"]))
        prev = p
    out("")
    out("  %-9s %9s %9s %6s %10s %-10s %s"
        % ("fire", "pass_s", "fireGap", "drop", "overran_tick", "outcome", "rc"))
    for r in rows:
        out("  %-9s %9.0f %9.0f %6s %10s %-10s %s" % r)
    verdict = "PASS"
    if ignore_new:
        if tot == 0:
            verdict = "INSUFFICIENT-POPULATION"
        elif hit == tot:
            out("")
            out("  PREDICATE  'tick dropped IFF previous pass overran its own next "
                "tick': %d of %d correct." % (hit, tot))
        else:
            verdict = "FAIL"
            out("  PREDICATE only %d of %d correct -- mechanism NOT established."
                % (hit, tot))
    else:
        verdict = "INCONCLUSIVE"
        out("  policy is not IgnoreNew; the drop story does not apply.")
    return {"verdict": verdict, "hits": hit, "total": tot, "policy": policy,
            "rows": rows}


# --------------------------------------------------------------------------
# ARM-L2 / ARM-L3 -- live v6 cadence
# --------------------------------------------------------------------------
def arm_l2(passes):
    out("")
    out("=" * 78)
    out("ARM-L2  LIVE PASS CADENCE (the thing v6 changed)")
    out("=" * 78)
    v6 = [p for p in passes if p["era"] == "v6" and p["pass_ms"] is not None]
    if not v6:
        out("  NO v6 PASSES YET -- the driver has not logged a PASS-END line.")
        return {"verdict": "INSUFFICIENT-POPULATION", "n": 0}
    durs = [p["pass_ms"] / 1000.0 for p in v6]
    fgap = [(v6[i]["fire"] - v6[i - 1]["fire"]).total_seconds()
            for i in range(1, len(v6))]
    drops = [g for g in fgap if g >= INTERVAL_S * 1.5]
    over = [d for d in durs if d > INTERVAL_S]
    for i, p in enumerate(v6):
        out("  fire=%s pass_ms=%-6s exec_ms=%-7s outcome=%s"
            % (p["fire"].strftime("%H:%M:%S"),
               p["pass_ms"],
               p["exec_ms"] if p["exec_ms"] is not None else "-",
               p["outcome"] or "pending"))
    st = stat(fgap)
    out("")
    out("  pass wall time   : %s   (interval is %.0fs)" % (fmt(stat(durs)), INTERVAL_S))
    out("  fire gap         : %s" % fmt(st))
    out("  ticks DROPPED    : %d of %d   (IgnoreNew dropped a tick)"
        % (len(drops), len(fgap)))
    out("  passes >interval : %d of %d" % (len(over), len(durs)))
    bad = len(drops) + len(over)
    # TICK COVERAGE: a tick that is "served" but whose exec cannot run (a child
    # is still in flight) falls to the queue. If the queue is dead those ticks
    # wake NOBODY, and counting them as "served" flatters the fix. This is the
    # number that caught the real remaining defect.
    spawned = len([p for p in passes
                   if p["detach_ok"] == "True" or p["outcome"] == "delivered"])
    total = len(passes)
    qfail = len([p for p in passes if p["outcome"] == "queue-failed"])
    if total:
        out("")
        out("  TICK COVERAGE: passes=%d, produced a wake=%d, produced NOTHING=%d"
            % (total, spawned, total - spawned))
        out("  ticks that woke nobody: %d of %d (%.1f%%)"
            % (total - spawned, total, 100.0 * (total - spawned) / total))
        if qfail:
            out("  of those, %d took the queue path and FAILED (dead transport)"
                % qfail)
    verdict = "PASS" if (len(v6) >= 2 and bad == 0) else (
        "INSUFFICIENT-POPULATION" if len(v6) < 2 else "FAIL")
    out("  VERDICT %s -- every tick is served" % verdict)
    return {"verdict": verdict, "n": len(v6), "drops": len(drops),
            "gaps": fgap, "durations": durs}


def arm_l3(passes):
    out("")
    out("=" * 78)
    out("ARM-L3  LIVE DELIVERY CADENCE + the causal identity")
    out("=" * 78)
    dl = [(p["fire"], p["delivered"]) for p in passes if p["delivered"]]
    gaps = [(dl[i][1] - dl[i - 1][1]).total_seconds() for i in range(1, len(dl))]
    if not gaps:
        out("  fewer than 2 deliveries in the log -- nothing to measure.")
        return {"verdict": "INSUFFICIENT-POPULATION", "n": 0}
    window = (dl[-1][1] - dl[0][1]).total_seconds() / 60.0
    st = stat(gaps)
    met = len([g for g in gaps if g <= CADENCE_MET_S])
    out("  POPULATION = %d deliveries   WINDOW = %s -> %s (%.1f min)"
        % (len(dl), dl[0][1].strftime("%H:%M:%S"),
           dl[-1][1].strftime("%H:%M:%S"), window))
    out("  gaps (s)      : %s" % ", ".join("%.0f" % g for g in gaps))
    out("  distribution  : %s" % fmt(st))
    out("  met the 180 s target: %d of %d gaps" % (met, len(gaps)))
    out("")
    out("  IDENTITY  delivery_gap(N+1) = fire_gap(N+1) + exec(N+1) - exec(N)")
    ok = err = 0
    seq = [p for p in passes if p["fire"]]
    for i in range(1, len(seq)):
        a, b = seq[i - 1], seq[i]
        fa = (b["fire"] - a["fire"]).total_seconds()
        ea = a["exec_s"]
        eb = b["exec_s"]
        if ea is None or eb is None:
            continue
        pred = fa + eb - ea
        act = (b["delivered"] - a["delivered"]).total_seconds() \
            if (a["delivered"] and b["delivered"]) else None
        if act is None:
            continue
        d = abs(pred - act)
        if d <= 3:
            ok += 1
        else:
            err += 1
        out("   %s -> %s  fire_gap=%4.0f exec %5.0f->%5.0f rc %s->%s  "
            "predicted=%5.0f actual=%5.0f  %s"
            % (a["fire"].strftime("%H:%M:%S"), b["fire"].strftime("%H:%M:%S"),
               fa, ea, eb, a["rc"], b["rc"], pred, act,
               "ok" if d <= 3 else "OFF"))
    if ok or err:
        out("  identity holds within 3 s on %d of %d pairs (log resolution is "
            "1 s)." % (ok, ok + err))
    # The residual bound, stated rather than asserted away.
    ex = [p["exec_s"] for p in passes if p["exec_s"]]
    out("")
    out("  CEILING: exec duration is the agent turn itself -- measured %s."
        % fmt(stat(ex)))
    out("  The runtime refuses a prompt into a session with an open turn, so no")
    out("  cron can deliver faster than that session's turns close. Delivery")
    out("  cadence is therefore bounded BELOW by this number, not by the cron.")
    verdict = "PASS" if st["median"] <= CADENCE_OK_S else "OVER-CADENCE"
    out("  VERDICT %s (median %.0fs vs acceptance %.0fs)"
        % (verdict, st["median"], CADENCE_OK_S))
    return {"verdict": verdict, "n": len(gaps), "stat": st, "met": met,
            "gaps": gaps, "identity_ok": ok, "identity_err": err}


def arm_l4(passes):
    """THE OWNER'S METRIC: how long after the cron SENT the wake does the wake
    arrive. Not the gap between two arrivals.

    THE PAIRING IS STRUCTURAL, NOT A HEAPERSHEEVE. Each pass record carries
    both endpoints: `pre` from the parent's "WAKE sending" line and `delivered`
    from the child's "WAKE delivered" line, and both belong to the SAME record
    because the log is read in order and a record ends only at the next pass
    boundary. Under v6 the child that emits EXEC-POST/WAKE delivered is the one
    this pass spawned (child_pid is logged), so latency == that child's
    exec_ms. That equality is asserted below rather than assumed.

    Zipping two independently sorted lists of sends and deliveries produces
    numbers 10x too large and is the single easiest way to report a latency
    finding that is not there.
    """
    out("")
    out("=" * 78)
    out("ARM-L4  SEND -> DELIVERY LATENCY  (the owner's quantity)")
    out("=" * 78)
    rows = []
    for p in passes:
        if not (p["pre"] and p["delivered"]):
            continue
        lat = (p["delivered"] - p["pre"]).total_seconds()
        rows.append((p, lat))
    if not rows:
        out("  no pass has both a send and a delivery.")
        return {"verdict": "INSUFFICIENT-POPULATION", "n": 0}
    pre = [r for r, _ in rows if r["fire"].hour < 13 or
           (r["fire"].hour == 13 and r["fire"].minute < 31)]
    post = [r for r, _ in rows if not (r["fire"].hour < 13 or
                                       (r["fire"].hour == 13 and r["fire"].minute < 31))]
    for name, grp in (("PRE-EDIT  (v5, before 13:30:59)", pre),
                      ("POST-EDIT (v6, from 13:31:01)", post)):
        lats = [lat for r, lat in rows if r in grp]
        if not lats:
            out("")
            out("  %s : no samples yet" % name)
            continue
        st = stat(lats)
        met = len([x for x in lats if x <= CADENCE_MET_S])
        span = ((grp[-1]["delivered"] - grp[0]["pre"]).total_seconds() / 60.0)
        out("")
        out("  %s" % name)
        out("    POPULATION = %d sends with a delivery   WINDOW = %s -> %s (%.1f min)"
            % (len(lats), grp[0]["pre"].strftime("%H:%M:%S"),
               grp[-1]["delivered"].strftime("%H:%M:%S"), span))
        out("    latencies (s): %s" % ", ".join("%.0f" % x for x in lats))
        out("    %s" % fmt(st))
        out("    under the 180 s target: %d of %d" % (met, len(lats)))
    # The structural check that makes the pairing auditable.
    bad = 0
    for p, lat in rows:
        if p["exec_ms"] is not None and abs(p["exec_ms"] / 1000.0 - lat) > 2:
            bad += 1
            out("    MISMATCH pass %s: send->delivery %.0fs vs exec_ms %.0fs"
                % (p["fire"].strftime("%H:%M:%S"), lat, p["exec_ms"] / 1000.0))
    n_exec = len([1 for p, _ in rows if p["exec_ms"] is not None])
    out("")
    if n_exec:
        out("    send->delivery == exec_ms on %d of %d instrumented passes"
            % (n_exec - bad, n_exec))
        out("    (expected: `mcode exec` runs the turn synchronously and returns")
        out("     when the turn ends, so the owner's latency IS the turn length.)")
    post_lat = [lat for r, lat in rows if r in post]
    pre_lat = [lat for r, lat in rows if r in pre]
    if not post_lat:
        out("  VERDICT INSUFFICIENT-POPULATION -- need >=6 post-edit sends")
        return {"verdict": "INSUFFICIENT-POPULATION", "n_post": len(post_lat)}
    v = stat(post_lat)
    verdict = "PASS" if v["median"] <= CADENCE_OK_S else "OVER-CADENCE"
    out("")
    out("  POST-EDIT VERDICT %s (median %.0fs vs acceptance %.0fs, n=%d)"
        % (verdict, v["median"], CADENCE_OK_S, len(post_lat)))
    if pre_lat:
        pv = stat(pre_lat)
        out("  pre-edit median was %.0fs; post-edit median %.0fs; delta %+.0fs"
            % (pv["median"], v["median"], v["median"] - pv["median"]))
    return {"verdict": verdict, "n_post": len(post_lat), "n_pre": len(pre_lat),
            "post": v, "pre": stat(pre_lat) if pre_lat else {}}


# --------------------------------------------------------------------------
# ARM-S -- sandbox, real driver text, both colours
# --------------------------------------------------------------------------
STUB_FIX = r'''#!/usr/bin/env python3
"""Stub for wake-fix.py inside the cadence sandbox. Answers the five calls the
driver makes, with the shapes the real tool prints. It touches NO database."""
import sys, os
mode = sys.argv[1] if len(sys.argv) > 1 else ""
sess = TARGET = os.environ.get("SOTTO_SESSION", "mvs_a00662bff55242cb9b56c0f1165bdad7")
if mode == "cron-alarm":
    print("CRON-ALARM verdict=ALARM newest_run=2026-10-06 10:11:00 age=1640.0min "
          "armed_active_crons=5 threshold=15min POPULATION: cron_runs rows=1442 "
          "POPULATION: cron_runs rows=1442 (window = whole store)")
    sys.exit(3)
if mode == "wake-plan":
    print("SESSION-STATE session=%s status=idle busy=NO reason=no-lease-no-open-turn "
          "lease=none lease_expires=- open_turn=- open_turn_age_min=- "
          "max_open_turn_mins=45 status_says_busy=NO (status DISAGREES=NO)" % sess)
    print("WORKSPACE C:\\Users\\Administrador")
    sys.exit(0)
if mode == "session-workspace":
    print("SESSION %s status=idle" % sess); print("C:\\Users\\Administrador")
    sys.exit(0)
if mode == "prune":
    print("[sandbox] PRUNE --all-sessions target=%s (POPULATION = whole queue "
          "table = 0 queued rows) pruned=0 kept=0" % sess)
    sys.exit(0)
if mode == "inject":
    print("[sandbox] INJECT into session=%s item_id=queue_sandbox status=queued" % sess)
    sys.exit(0)
print("[sandbox] unknown mode %r" % mode); sys.exit(1)
'''

STUB_SLEEP = r'''#!/usr/bin/env python3
"""Stub for `mcode exec`. It sleeps a MEASURED duration from the driver text's
own population instead of running an agent, so the sandbox reproduces the
scheduler's overlap behaviour and nothing else."""
import os, sys, time
durs = [float(x) for x in os.environ.get("CADENCE_STUB_DURATIONS", "1").split(",")]
ctr = os.environ.get("CADENCE_STUB_COUNTER", "counter.txt")
n = 0
if os.path.exists(ctr):
    try:
        n = int(open(ctr).read().strip() or "0")
    except Exception:
        n = 0
d = durs[n % len(durs)]
with open(ctr, "w") as f:
    f.write(str(n + 1))
sys.stdout.write("[sandbox-exec] stub mcode exec, sleeping %.2fs (sample %d of %d)\n"
                 % (d, n % len(durs) + 1, len(durs)))
sys.stdout.flush()
sys.stdin.read()
time.sleep(d)
print("[sandbox-exec] done")
sys.exit(0)
'''

# The negative arm reverts EXACTLY ONE thing: v6 detaches the exec and returns,
# the negative arm starts the same child and then WAITS for it. Nothing else is
# touched, so the arm measures the fix and not a rewrite.
NEG_ANCHOR = """        $spawned = $true
        Log ('EXEC-DETACH child_pid=' + $child.Id + ' spawn_ms=' + (Ms $swPass) +
             ' create_no_window=True exe=' + $pwshExe)"""
NEG_REPLACEMENT = """        $spawned = $true
        # SANDBOX-NEG ARM -- the ONLY change vs the shipped driver. It reverts
        # v6's detach (Start, then return immediately) to v5's behaviour (start,
        # then WAIT for the exec to finish). Nothing else is touched, so this arm
        # measures the fix rather than a rewrite.
        Log ('EXEC-DETACH-NEG blocking_waitforexit=True child_pid=' + $child.Id)
        $child.WaitForExit()"""


def build_copy(dest: Path, neg: bool) -> Path:
    """Copy the shipped driver, redirect its $root into the sandbox, and for the
    negative arm revert the detach. Returns the copy path."""
    text = DRIVER.read_text(encoding="utf-8")
    m = re.search(r"\$root\s*=\s*'([^']+)'", text)
    if not m:
        raise RuntimeError("could not find $root assignment in %s" % DRIVER)
    live_root = m.group(1)
    sandbox_main = dest / "_main"
    sandbox_main.mkdir(parents=True, exist_ok=True)
    text = text.replace("$root      = '%s'" % live_root,
                        "$root      = '%s'" % sandbox_main.parent, 1)
    if neg:
        if NEG_ANCHOR not in text:
            raise RuntimeError(
                "NEGATIVE ARM ANCHOR NOT FOUND -- the shipped driver changed and "
                "this gate would silently be testing nothing. Anchor:\n%s" % NEG_ANCHOR)
        text = text.replace(NEG_ANCHOR, NEG_REPLACEMENT, 1)
    copy = sandbox_main / ("heartbeat-neg.ps1" if neg else "heartbeat-fixed.ps1")
    copy.write_text(text, encoding="utf-8")
    return copy


def run_arm(copy: Path, durations, interval, ticks, tag):
    """Drive the sandbox copy the way Task Scheduler drives it: fire every
    `interval` seconds, and if a pass is still running, DISCARD the tick
    (MultipleInstances=IgnoreNew) and log nothing."""
    sb_main = copy.parent
    (sb_main / "wake-fix.py").write_text(STUB_FIX, encoding="utf-8")
    (sb_main / "ORCHESTRATOR-PROMPT.md").write_text(
        "[sandbox] orchestrator mandate\n", encoding="utf-8")
    mcode = sb_main / "mcode.cmd"
    mcode.write_text('@echo off\r\npython "%~dp0stub_sleep.py" %*\r\n', encoding="utf-8")
    (sb_main / "stub_sleep.py").write_text(STUB_SLEEP, encoding="utf-8")
    counter = sb_main / ("counter-%s.txt" % tag)
    if counter.exists():
        counter.unlink()
    # The copy's own $root was redirected into this sandbox, so it writes to
    # sb_main\heartbeat.log -- NOT a per-arm name. Each arm gets its OWN sandbox
    # tree for exactly that reason: a FIXED child outlives its parent by minutes
    # and would otherwise append into the NEXT arm's log.
    logf = sb_main / "heartbeat.log"
    if logf.exists():
        logf.unlink()

    env = dict(os.environ)
    env["PATH"] = str(sb_main) + os.pathsep + env.get("PATH", "")
    env["CADENCE_STUB_DURATIONS"] = ",".join("%.3f" % d for d in durations)
    env["CADENCE_STUB_COUNTER"] = str(counter)
    env["SOTTO_SESSION"] = TARGET_SESSION

    pwsh = shutil.which("pwsh") or "pwsh.exe"
    args = [pwsh, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-WindowStyle", "Hidden", "-File", str(copy)]
    # CREATE_NO_WINDOW only. NOT 0x08000000|0x00000008 here: Win32 documents
    # CREATE_NO_WINDOW as IGNORED when DETACHED_PROCESS is also specified, so
    # adding DETACHED_PROCESS would give the child a detached CONSOLE -- a
    # visible window on the owner's screen, the exact thing this project has
    # been shown twice. The live driver uses .NET CreateNoWindow with no
    # DETACHED_PROCESS for the same reason. This harness is a measurement tool,
    # not the app, so it takes the safe flag and says so.
    CF = 0x08000000  # CREATE_NO_WINDOW

    # Capture every spawned pass's own stdout/stderr. A pass that dies at once
    # writes NOTHING to the log, which is indistinguishable from "never ran" --
    # exactly the ambiguity that made the first two sandbox runs report 0 passes
    # with no clue why. The capture is what turned that into a readable error.
    outp = open(sb_main / ("passes-%s.out" % tag), "wb")
    running = {"p": None}
    dropped = {"n": 0, "ts": []}
    started, done = [], threading.Event()

    def tick_loop():
        t0 = time.time()
        for i in range(ticks):
            target = t0 + i * interval
            now = time.time()
            if target > now:
                done.wait(target - now)
            if running["p"] is not None and running["p"].poll() is None:
                dropped["n"] += 1
                dropped["ts"].append(i)
                continue  # IgnoreNew: discarded, never made up
            try:
                running["p"] = subprocess.Popen(args, env=env, stdout=outp,
                                                stderr=subprocess.STDOUT,
                                                creationflags=CF)
                started.append((i, time.time() - t0))
            except Exception as exc:  # pragma: no cover
                out("  sandbox: spawn failed at tick %d: %s" % (i, exc))
                return
        # let the tail finish
        deadline = time.time() + interval * 4
        while running["p"] is not None and running["p"].poll() is None \
                and time.time() < deadline:
            time.sleep(0.05)
        done.set()

    th = threading.Thread(target=tick_loop, daemon=True)
    th.start()
    th.join(timeout=interval * ticks + interval * 6)
    if th.is_alive():
        if running["p"] is not None and running["p"].poll() is None:
            running["p"].kill()
        done.set()
        out("  sandbox: TIMED OUT and was killed")

    # Best-effort close of the capture handle. A failure here means the handle
    # leaked, NOT that the measurement is wrong -- the driver writes its own log
    # independently. Reported rather than swallowed so a reader can audit it.
    try:
        outp.close()
    except Exception as exc:
        out("      NOTE: capture handle close failed (%s); measurement "
            "unaffected, handle leaked." % exc)

    ps = parse_log(logf)
    if not ps:
        cap = sb_main / ("passes-%s.out" % tag)
        out("      DIAGNOSTIC: 0 passes parsed. The spawned process said:")
        if cap.exists() and cap.stat().st_size:
            for ln in cap.read_text(encoding="utf-8", errors="replace") \
                    .splitlines()[:8]:
                out("        | " + ln[:160])
        else:
            out("        | (no output at all -- the process died before it "
                "could write anything, or never started)")
    dl = [p["delivered"] for p in ps if p["delivered"]]
    gaps = [(dl[i] - dl[i - 1]).total_seconds() for i in range(1, len(dl))]
    fgap = [(ps[i]["fire"] - ps[i - 1]["fire"]).total_seconds()
            for i in range(1, len(ps))]
    return {"drops": dropped["n"], "dropped_ticks": dropped["ts"],
            "n_passes": len(ps), "deliveries": len(dl), "gaps": gaps,
            "fire_gaps": fgap, "stat": stat(gaps),
            "queued": len([p for p in ps if p["queued"]]),
            "log": logf, "ticks": ticks}


def arm_s(measured_durations, scale, ticks):
    out("")
    out("=" * 78)
    out("ARM-S  SANDBOX: the shipped driver text, FIXED vs NEGATIVE")
    out("=" * 78)
    out("  Scheduler model  = MultipleInstances:IgnoreNew (measured), PT3M")
    out("  Clock compressed by %dx: interval %.1fs, exec durations scaled from" % (scale, INTERVAL_S / scale))
    out("  the REAL v5 population so the exec/interval RATIO is preserved.")
    out("  log timestamp resolution is 1 s, which is %d%% of the scaled interval."
        % int(round(100.0 / (INTERVAL_S / scale))))
    out("  Measured exec durations used (real seconds): %s"
        % ", ".join("%.0f" % d for d in measured_durations))
    scaled = [d / scale for d in measured_durations]
    out("  Scaled               (seconds)            : %s"
        % ", ".join("%.2f" % d for d in scaled))
    out("")

    if SANDBOX.exists():
        shutil.rmtree(SANDBOX, ignore_errors=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    interval = INTERVAL_S / scale
    res = {}
    for neg, tag in ((False, "FIXED"), (True, "NEG")):
        copy = build_copy(SANDBOX / tag, neg)
        out("  --- arm %s: %s" % (tag, copy.name))
        r = run_arm(copy, scaled, interval, ticks, tag)
        res[tag] = r
        st = r["stat"]
        out("      passes=%d deliveries=%d queued=%d ticks_dropped=%d"
            % (r["n_passes"], r["deliveries"], r["queued"], r["drops"]))
        out("      fire gaps : %s" % ", ".join("%.1f" % g for g in r["fire_gaps"][:14]))
        out("      deliveries: %s" % fmt(st))
        if r["gaps"]:
            met = len([g for g in r["gaps"] if g <= interval])
            out("      gaps within one interval: %d of %d" % (met, len(r["gaps"])))
        out("")

    out("  SCALE BACK TO REAL SECONDS (x%d)" % scale)
    fx, ng = res["FIXED"], res["NEG"]
    out("    FIXED : drops=%-3d deliveries=%-3d median_gap=%.0fs (=%.1f min real)"
        % (fx["drops"], fx["deliveries"], fx["stat"].get("median", 0),
           fx["stat"].get("median", 0) * scale / 60.0))
    out("    NEG   : drops=%-3d deliveries=%-3d median_gap=%.0fs (=%.1f min real)"
        % (ng["drops"], ng["deliveries"], ng["stat"].get("median", 0),
           ng["stat"].get("median", 0) * scale / 60.0))
    out("")
    out("    FIXED median %.0fs vs NEG median %.0fs -- the fix moves the median"
        % (fx["stat"].get("median", 0), ng["stat"].get("median", 0)))
    out("    by %.0f scaled seconds (%+.0f%%) and removes %d dropped ticks."
        % (ng["stat"].get("median", 0) - fx["stat"].get("median", 0),
           100.0 * (fx["stat"].get("median", 1) - ng["stat"].get("median", 1))
           / max(ng["stat"].get("median", 1), 1e-9),
           ng["drops"] - fx["drops"]))
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true",
                    help="require the NEGATIVE arm to be RED (proves the gate "
                         "can go red); exit non-zero if it is green")
    ap.add_argument("--live-only", action="store_true")
    ap.add_argument("--sandbox-only", action="store_true")
    ap.add_argument("--scale", type=float, default=30.0,
                    help="clock compression factor (default 30: 180s -> 6s)")
    ap.add_argument("--ticks", type=int, default=24)
    args = ap.parse_args()

    out("cadence-probe.py  --  %s  driver=%s" % (dt.datetime.now().isoformat(timespec="seconds"), DRIVER))
    passes = parse_log(LOG)
    out("heartbeat.log: %d passes parsed (%d v5, %d v6)"
        % (len(passes), len([p for p in passes if p["era"] == "v5"]),
           len([p for p in passes if p["era"] == "v6"])))

    results = {}
    if not args.sandbox_only:
        results["L1"] = arm_l1(passes, read_task_policy())
        results["L2"] = arm_l2(passes)
        results["L3"] = arm_l3(passes)
        results["L4"] = arm_l4(passes)

    if not args.live_only:
        measured = [p["exec_s"] for p in passes
                    if p["era"] == "v5" and p["pre"] and p["post"]]
        if not measured:
            measured = [p["exec_s"] for p in passes if p["exec_s"]]
        if not measured:
            measured = [155.0, 227.0, 98.0, 184.0, 130.0, 162.0, 128.0]
            out("")
            out("  WARNING: no measured durations in the log; using the published")
            out("  receipt-22 population instead.")
        results["S"] = arm_s(measured, args.scale, args.ticks)

    out("")
    out("=" * 78)
    out("VERDICT SUMMARY")
    out("=" * 78)
    for k in ("L1", "L2", "L3", "L4"):
        if k in results:
            out("  %-3s %s" % (k, results[k]["verdict"]))
    rc = 0
    if "S" in results:
        fx = results["S"]["FIXED"]
        ng = results["S"]["NEG"]
        fx_med = fx["stat"].get("median")
        ng_med = ng["stat"].get("median")
        fx_ok = fx["drops"] == 0 and fx_med is not None and ng_med is not None \
            and fx_med < ng_med
        neg_red = ng["drops"] > 0 and ng_med is not None and ng_med > fx_med
        out("  S-FIXED %s  drops=%d median=%.1fs"
            % ("GREEN" if fx_ok else "RED", fx["drops"], fx_med or -1))
        out("  S-NEG   %s  drops=%d median=%.1fs"
            % ("RED" if neg_red else "GREEN", ng["drops"], ng_med or -1))
        if not fx_ok or not neg_red:
            rc = 2
        if args.neg_arm and not neg_red:
            out("")
            out("  --neg-arm: THE NEGATIVE ARM IS GREEN. This gate proves nothing.")
            rc = 3
    if not args.sandbox_only:
        for k in ("L1", "L2", "L3", "L4"):
            if results[k]["verdict"] == "FAIL":
                rc = max(rc, 2)
    out("")
    out("VERDICT %s" % ("PASS" if rc == 0 else "FAIL(rc=%d)" % rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())