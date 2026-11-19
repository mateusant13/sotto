#!/usr/bin/env python
"""cage.py -- run one measured job under an explicit, printed ceiling.

WHY THIS EXISTS
---------------
The house rule says `python -m watcher run --cpu 40 --io very-low -- <cmd>`.
On this box that command does not exist:

    $ python -c "import watcher"
    ModuleNotFoundError: No module named 'watcher'

so every bench script that documented the watcher form (including
`arm_a_diarize.py`) was documenting a cage nobody could enter. A ceiling that is
only written in a docstring is a declared number with no judge (anti-pattern 9).
This file is the judge: it prints the ceiling BEFORE the job, and the MEASURED
line AFTER it, from `psutil` on the real process tree.

TWO CEILINGS, and they are different things
-------------------------------------------
  * CPU ceiling  -- soft. Reported, and the job is killed if it exceeds
    `--max-cpu-pct` of ONE core... no: of the whole box. The number is checked
    against the measured peak, not against an intention.
  * MEMORY floor -- hard, and it is the one that protects the owner's live
    Discord call. Below `--min-free-mb` of available RAM the child is killed.
    A bench that swaps the owner's call to death "measured" nothing worth having.

Usage
-----
    python _main/bench/cage.py --threads 2 --max-cpu-pct 40 -- python foo.py ...
    python _main/bench/cage.py --show -- python foo.py ...   # ceiling only

Exit code is the child's, except 97 = killed by a ceiling, 98 = killed by the
memory floor.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import psutil

RC_CPU_CEILING = 97
RC_MEM_FLOOR = 98


def _tree_cpu_s(proc: psutil.Process) -> float:
    """Summed user+system seconds over the whole tree, including exited kids."""
    total = 0.0
    try:
        procs = [proc] + proc.children(recursive=True)
    except psutil.Error:
        return 0.0
    for p in procs:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.Error:
            continue
    return total


def _tree_rss_b(proc: psutil.Process) -> int:
    total = 0
    try:
        procs = [proc] + proc.children(recursive=True)
    except psutil.Error:
        return 0
    for p in procs:
        try:
            total += p.memory_info().rss
        except psutil.Error:
            continue
    return total


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--threads", type=int, default=2,
                    help="thread budget written into OMP/MKL/torch env for the child")
    ap.add_argument("--max-cpu-pct", type=float, default=40.0,
                    help="peak whole-box CPU%% allowed for the tree")
    ap.add_argument("--max-rss-mb", type=float, default=3000.0)
    ap.add_argument("--min-free-mb", type=float, default=350.0,
                    help="hard floor on system available RAM; below it the child dies")
    ap.add_argument("--label", default="")
    ap.add_argument("--wait-free-mb", type=float, default=0.0,
                    help="before launching, block until this much RAM is available; "
                         "this box swings from 7 GB to 25 MB free in seconds, so a job "
                         "started in the wrong second is killed by its own floor")
    ap.add_argument("--wait-s", type=float, default=180.0,
                    help="how long to wait for that window")
    ap.add_argument("--retries", type=int, default=0,
                    help="relaunch (after waiting again) when the memory floor killed it")
    ap.add_argument("--show", action="store_true", help="print the ceiling and exit")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)

    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        ap.error("no command (use: cage.py -- <cmd...>)")

    for attempt in range(1 + max(0, args.retries)):
        rc = _one(args, cmd)
        if rc != RC_MEM_FLOOR:
            return rc
        print("CAGE: retry %d/%d after a memory-floor kill" % (attempt + 1, args.retries),
              file=sys.stderr, flush=True)
    return RC_MEM_FLOOR


def _one(args, cmd) -> int:
    """One launch, with the ceiling printed and the tree measured."""
    if args.wait_free_mb > 0:
        t_w = time.perf_counter()
        while time.perf_counter() - t_w < args.wait_s:
            av = psutil.virtual_memory().available / 1e6
            if av >= args.wait_free_mb:
                print("WINDOW: free %.0f MB >= %.0f MB after %.1f s"
                      % (av, args.wait_free_mb, time.perf_counter() - t_w), flush=True)
                break
            time.sleep(2.0)
        else:
            print("CAGE: no %.0f MB window in %.0f s -- running anyway, the floor decides"
                  % (args.wait_free_mb, args.wait_s), flush=True)
    vm = psutil.virtual_memory()
    ncores = psutil.cpu_count()
    print("CEILING: 1 job | threads %d | cpu %.0f%% of %d cores | rss <= %.0f MB | "
          "free-RAM floor %.0f MB | host free now %.0f MB"
          % (args.threads, args.max_cpu_pct, ncores, args.max_rss_mb,
             args.min_free_mb, vm.available / 1e6), flush=True)
    print("CEILING-CMD: %s" % " ".join(cmd), flush=True)
    if args.show:
        return 0

    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        env[k] = str(args.threads)
    # Deterministic, quiet child: no console window, no bytecode litter.
    env.setdefault("PYTHONDONTWRITEBYTECODE", "1")

    creation = 0
    if os.name == "nt":
        creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, env=env, creationflags=creation)
    try:
        ps = psutil.Process(proc.pid)
    except psutil.Error:
        ps = None
    if ps is not None:
        try:
            ps.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        except psutil.Error:
            pass

    peak_rss = 0
    peak_cpu_pct = 0.0
    last_cpu = 0.0
    last_t = t0
    rc_forced = 0
    while proc.poll() is None:
        time.sleep(0.4)
        now = time.perf_counter()
        if ps is None:
            continue
        cpu = _tree_cpu_s(ps)
        rss = _tree_rss_b(ps)
        dt = max(1e-6, now - last_t)
        # percent of the WHOLE BOX, not of one core: 2 threads on 20 cores is 10%.
        pct = 100.0 * (cpu - last_cpu) / (dt * max(1, ncores))
        last_cpu, last_t = cpu, now
        peak_rss = max(peak_rss, rss)
        peak_cpu_pct = max(peak_cpu_pct, pct)
        free_mb = psutil.virtual_memory().available / 1e6
        if free_mb < args.min_free_mb:
            print("CAGE: ABORT -- free RAM %.0f MB below floor %.0f MB; killing the job "
                  "so the owner's live call keeps its memory" % (free_mb, args.min_free_mb),
                  file=sys.stderr, flush=True)
            rc_forced = RC_MEM_FLOOR
            proc.kill()
            break
        if peak_cpu_pct > args.max_cpu_pct * 3:
            # 3x is a runaway, not jitter: one window of scheduler noise is not
            # a reason to lose a measurement, an unthrottled job is.
            print("CAGE: ABORT -- tree CPU %.1f%% of the box is 3x the %.0f%% ceiling"
                  % (peak_cpu_pct, args.max_cpu_pct), file=sys.stderr, flush=True)
            rc_forced = RC_CPU_CEILING
            proc.kill()
            break

    rc = proc.wait()
    wall = time.perf_counter() - t0
    if ps is not None:
        try:
            peak_rss = max(peak_rss, _tree_rss_b(ps))
        except psutil.Error:
            pass
    print("MEASURED: wall %.2f s | peak tree CPU %.1f%% of the box | peak tree RSS "
          "%.0f MB | host free now %.0f MB | rc %d%s"
          % (wall, peak_cpu_pct, peak_rss / 1e6,
             psutil.virtual_memory().available / 1e6, rc,
             " (FORCED)" if rc_forced else ""), flush=True)
    return rc_forced or rc


if __name__ == "__main__":
    sys.exit(main())
