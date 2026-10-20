#!/usr/bin/env python3
"""THE LOG BUDGET OF THE STATS FEED — bytes per minute, before and after.

WHY THIS EXISTS. The owner's audio wave stopped moving because the worker's meter
default was set to ZERO — a feature switched off to stop a log from growing. That
trade is the defect: the feed and the log are different things, and the LOG is what
has to be bounded. `on_worker_stats` fires once per `WORKER_STATS` line, i.e. once
per METER SAMPLE, so a line per sample is an unbounded log.

TWO ARMS, one subject, same worker, same rate:

  * `per-sample` — a COPY of today's shell whose push logs EVERY sample (the
    textual revert of the aggregation, so the difference is exactly one thing);
  * `aggregated` — the real shell: the first push, then at most one line per
    `STATS_LOG_INTERVAL_S` (30 s), each carrying the count it stands for.

The stand-in worker publishes at `--hz 20` — tens of Hz, which is the shape of a
real meter — and opens NO audio device. The metric is the LOG FILE's own growth
over a fixed window, so it is bytes, not an impression.

WHAT CHANGED ON 2026-10-20 (this file is not the same file it was). The battery
went RED on this gate twice in one night and the PRODUCT WAS NOT BROKEN:

  * the `aggregated` arm never reached `RECEIVER_READY`, so it wrote ZERO push
    lines; the ratio — a division by ~0 — printed as `21586300.0x` and the gate
    said `STRIP-LOG CONTROL FAIL`. A failure about the BOX, dressed as a
    failure about the product;
  * that arm's own log says why: the shell started at 03:20:33.714 and
    `STAGING_SEEN` — which happens BEFORE the page is live — only at 03:21:37.298,
    63.6 s later. The box was saturated (VRAM 100 %, 38 `msedgewebview2.exe`,
    the owner's own python processes, three agent lanes);
  * the SAME app, CALM, reaches `RECEIVER_READY` in 1.98 s
    (`I:\\cc-tmp\\sotto-032942.log`: READY-FILE 1.95 s, STAGING_LOADED 1.97 s,
    RECEIVER_READY 1.98 s).

So the gate now measures the PANEL'S STARTUP as well, and a page that does not
go live inside the deadline makes the gate SKIP — loudly, with the numbers —
instead of failing the product. The CLAIM of the gate did not change: when both
arms are live, the aggregated arm still has to write at least 50x fewer bytes
per minute, or the gate is RED. The deadline, its justification and the shared
decision live in `_main/_strip_stats_load.py`; the gate that proves that
decision honest (with four broken copies of it) is
`_main/_strip-stats-load-oracle.py`.

THE MEASUREMENT WINDOW changed too. It used to start 6 s after the launch — a
fixed settle — which under load counted the panel's own startup as feed time and
diluted the two arms by different amounts. Now it starts when the page goes LIVE
and ends when the shell exits, so both arms are measured over the same kind of
interval: the feed running.

WHAT WAS NOT CHANGED: the 50x ratio, the 100-line floor and the `delivered > 100`
floor. The defect must keep showing up.

    pythonw.exe _main/_strip-stats-log-probe.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _strip_stats_load as load  # noqa: E402  (the path fix has to come first)

SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
STAMP = f'{os.getpid()}-{int(time.time())}'
#: The per-sample COPY of the shell. The name carries the run's stamp because
#: the name is shared by every run of this probe: two probes running at the
#: same time used to overwrite each other's copy, and the arm that believed it
#: was measuring the per-sample shell was really measuring the aggregated one
#: — a RED with no cause, which is the class of failure this file exists to
#: kill. The copy is deleted when the run ends.
MUTANT = os.path.join(os.path.dirname(SHELL),
                      f'_strip-logmutant_{STAMP}_sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
REPORT = os.path.join(HERE, '_strip-stats-log-probe.json')

CREATE_NO_WINDOW = 0x08000000
HZ = 20.0
RUN_S = 24.0
#: How long the page has to go LIVE before the arm is declared unmeasurable.
#: 30 s = 15x the measured calm startup (1.98 s) and 2.1x below the measured
#: loaded one (63.58 s to `STAGING_SEEN`, before `RECEIVER_READY`).
READY_DEADLINE_S = load.READY_DEADLINE_S
#: How long the arm waits for the shell to exit ON ITS OWN after the page went
#: live. The shell arms `--exit-after` when the panel loads, so the feed runs
#: for `RUN_S` after the page is live; the margin covers the shell's own exit
#: path (measured: with a live worker the destroy can outlive the exit timer —
#: `sotto_webview.py:7999-8007` — so a slow box must not be read as a fault).
EXIT_MARGIN_S = 25.0


def max_count(push_lines):
    """The CUMULATIVE `count=` both arms carry, as an integer.

    `BRIDGE_STATS_PUSH count=N` counts pushes since the start (`stats_pushes`),
    in the aggregated arm AND in the per-sample copy. So the MAXIMUM is how many
    pushes had been delivered when the LAST such line was logged — which is the
    number `SHELL_EXIT statsPushes=` would have carried, available even when the
    arm was killed and never reached `SHELL_EXIT`. 0 means "no such line".
    """
    best = 0
    for ln in push_lines:
        m = re.search(r'count=(\d+)', ln)
        if m:
            best = max(best, int(m.group(1)))
    return best


def build_mutant():
    """A COPY of today's shell whose push logs EVERY sample."""
    shutil.copyfile(SHELL, MUTANT)
    with open(MUTANT, encoding='utf-8') as fh:
        src = fh.read()
    reverted = src.replace(
        "        self._stats_log_maybe(payload)\n",
        "        log('BRIDGE_STATS_PUSH count=' + str(self.stats_pushes) + ' '\n"
        "            'payload=' + json.dumps(payload, separators=(',', ':')))\n", 1)
    if reverted == src:
        raise SystemExit('the per-sample control could not be built: '
                         '`self._stats_log_maybe(payload)` was not found verbatim')
    with open(MUTANT, 'w', encoding='utf-8') as fh:
        fh.write(reverted)
    return MUTANT


def kill_tree(proc):
    """Kill THIS arm's shell (and the stand-in worker it spawned).

    The shell is the measurement's own child, so killing it is allowed; the
    owner's app is a different pid and is never touched. The TREE is killed
    because the shell spawns the stand-in worker, and a worker that outlives
    its shell keeps its pipe open. The wait is bounded and NEVER raises: the
    earlier version raised `TimeoutExpired` here and turned a slow box into a
    CRASH of the instrument (measured 2026-10-20 03:32, the arm's own log).
    """
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=CREATE_NO_WINDOW, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        pass


def wait_ready(proc, log_path, started, deadline_s, margin_s=5.0):
    """Wait for the page to go LIVE, bounded by the deadline.

    Returns (seen, waited_s, alive_at_deadline). `seen` says the `RECEIVER_READY`
    line appeared in the log; whether the page came up INSIDE the deadline is
    judged afterwards, by the LOG's own clock (`arm_readiness`), because that
    clock is the one the measurements were read with. The margin is the slack
    between the two clocks: the log's first line is written a fraction of a
    second after the process starts, so a page that the log calls "29.9 s" must
    still be seen by a watcher whose own clock says "30.1 s".

    `alive_at_deadline` says the shell was STILL RUNNING when the wait ended: a
    slow shell is the box, a DEAD shell is the product, and the two must not be
    confused.
    """
    waited = 0.0
    while True:
        waited = time.time() - started
        if waited >= deadline_s + margin_s:
            return False, waited, proc.poll() is None
        if proc.poll() is not None:
            return False, waited, False
        if load.READY_MILESTONE in load.read_log(log_path):
            return True, time.time() - started, True
        time.sleep(0.2)


def run_arm(tag, shell, run_s=RUN_S):
    log_path = os.path.join(HERE, f'_strip-stats-log-{tag}-{STAMP}.log')
    # The shell spawns the worker as `[python, <worker_path>]`, so the rate goes
    # in the ENVIRONMENT (which `WorkerBridge._spawn` copies into the child's).
    env = dict(os.environ)
    env['SOTTO_STANDIN_HZ'] = str(HZ)
    env['SOTTO_STANDIN_SECS'] = '60'
    cmd = [PYW, shell, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--with-worker', '--worker', STANDIN,
           '--log', log_path, '--exit-after', str(RUN_S)]
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL), env=env,
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # PHASE 1 — the page has to go LIVE. This is the phase the loaded box
    # loses: on 2026-10-20 the page took 63.6 s and the arm never got here.
    seen, waited, alive = wait_ready(proc, log_path, started, READY_DEADLINE_S)
    # The LOG's own clock is the authority on whether the page came up INSIDE
    # the deadline -- it is the clock the measurements were read with.
    readiness = load.arm_readiness(load.read_log(log_path), READY_DEADLINE_S)
    ready = readiness['ready']
    # PHASE 2 — the feed needs its window; the shell exits on its own. A page
    # that came up LATE is not measured: the gate will SKIP it, and there is no
    # reason to keep the box busy for a window nobody may claim.
    if ready:
        deadline = time.time() + run_s + EXIT_MARGIN_S
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.25)
    killed = False
    if proc.poll() is None:
        killed = True
        kill_tree(proc)
    ended = time.time()

    text = load.read_log(log_path)
    all_lines = text.splitlines()
    # The MEASUREMENT WINDOW is the feed's own time: from the line that says
    # the page is live to the end of the log. The shell logs `RECEIVER_READY`
    # before any push, so the push lines after it are the feed's.
    ready_at = None
    for index, line in enumerate(all_lines):
        if load.READY_MILESTONE in line:
            ready_at = index
            break
    feed_lines = all_lines[ready_at + 1:] if ready_at is not None else []
    push_lines = [ln for ln in feed_lines if 'BRIDGE_STATS_PUSH' in ln]
    every_push = [ln for ln in all_lines if 'BRIDGE_STATS_PUSH' in ln]
    # THE NUMBER THAT MATTERS: bytes the FEED put in the log, isolated from the
    # shell's own periodic lines (which grow the file in both arms).
    push_bytes = sum(len(ln) + 1 for ln in push_lines)
    exit_line = load.log_lines(text, 'SHELL_EXIT')
    total = None
    if exit_line:
        m = re.search(r'statsPushes=(\d+)', exit_line[-1])
        if m:
            total = int(m.group(1))
    # DELIVERED, robust to a killed arm: `SHELL_EXIT` is the clean source, and
    # the cumulative `count=` is the fallback that survives a stall.
    delivered = total if total is not None else max_count(every_push)
    # The window the BYTES are counted over: the time the feed was running,
    # i.e. from the page going live to the end of the arm.
    feed_window = max(0.001, ended - started - (waited if ready else 0.0))
    size = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    return {
        'tag': tag, 'shell': shell, 'log': log_path, 'rc': proc.returncode,
        'killed': killed, 'ready': ready,
        'ready_s': readiness['ready_s'],
        'waited_s': round(waited, 2),
        'deadline_s': READY_DEADLINE_S,
        'shell_alive_at_deadline': alive,
        'timeline': readiness['timeline'],
        'readiness_reason': readiness['reason'],
        'window_s': round(feed_window, 2),
        'final_bytes': size,
        'push_lines': len(push_lines),
        'push_lines_total': len(every_push),
        'push_bytes': push_bytes,
        'push_bytes_per_min': round(push_bytes / feed_window * 60.0, 1),
        'pushes_total': total,
        'delivered': delivered,
        'autostart': load.log_lines(text, 'WORKER_AUTOSTART'),
        'push_sample': push_lines[:2],
    }


def main():
    report = {'shell': SHELL, 'hz': HZ, 'run_s': RUN_S,
              'ready_deadline_s': READY_DEADLINE_S,
              'deadline_facts': load.deadline_facts(READY_DEADLINE_S)}
    try:
        build_mutant()
        # NO RETRY. The old code retried once when an arm never came up ready.
        # With a deadline the retry buys nothing: a box slow enough to miss
        # 30 s is slow enough to miss 60 s, and the retry doubled the wait on
        # exactly the machine that could least afford it.
        report['per_sample'] = run_arm('per-sample', MUTANT)
        report['aggregated'] = run_arm('aggregated', SHELL)
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass

    per = report['per_sample']
    agg = report['aggregated']
    checks = load.budget_checks(per, agg)
    verdict = load.decide([per, agg], checks, READY_DEADLINE_S)
    report['checks'] = [{'what': w, 'ok': bool(o)} for w, o in checks]
    report['verdict'] = verdict['verdict']
    report['failed'] = verdict.get('failed') or []
    report['skip_reason'] = verdict.get('skip_reason')
    report['ratio'] = round(
        (per['push_bytes_per_min'] or 0.0)
        / max(0.001, agg['push_bytes_per_min'] or 0.0), 1)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    # ALWAYS PRINT. A probe that only prints when it passes writes a 0-byte
    # step log on a RED run, and the battery's recorder then cannot find its
    # verdict sentence — which reads as "the instrument never ran" instead of
    # "the instrument ran and failed". The FAIL line is that sentence.
    if verdict['verdict'] == 'GREEN':
        print(f'STRIP-LOG CONTROL PASS ratio={report["ratio"]}x '
              f'per_sample_lines={per["push_lines"]} '
              f'per_sample_bytes_per_min={per["push_bytes_per_min"]} '
              f'aggregated_lines={agg["push_lines"]} '
              f'aggregated_bytes_per_min={agg["push_bytes_per_min"]} '
              f'delivered={agg["delivered"]} '
              f'ready_s(per={per["ready_s"]},agg={agg["ready_s"]}) '
              f'deadline={READY_DEADLINE_S:.0f}s')
    elif verdict['verdict'] == 'SKIP':
        print(f'STRIP-LOG CONTROL SKIPPED VERDICT: SKIPPED - '
              f'{verdict["skip_reason"]} | deadline={READY_DEADLINE_S:.0f}s '
              f'per arm | per_sample(ready={per["ready"]},'
              f'ready_s={per["ready_s"]},waited_s={per["waited_s"]}) '
              f'aggregated(ready={agg["ready"]},ready_s={agg["ready_s"]},'
              f'waited_s={agg["waited_s"]}) | this run CANNOT claim the log '
              f'budget')
    else:
        print(f'STRIP-LOG CONTROL FAIL ratio={report["ratio"]}x '
              f'failed={len(report["failed"])} reason={verdict["reason"]} '
              f'per_sample(ready={per["ready"]},killed={per["killed"]},'
              f'lines={per["push_lines"]},delivered={per["delivered"]}) '
              f'aggregated(ready={agg["ready"]},killed={agg["killed"]},'
              f'lines={agg["push_lines"]},delivered={agg["delivered"]})')
    return 0 if verdict['verdict'] != 'RED' else 3


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback
        with open(REPORT, 'w', encoding='utf-8') as fh:
            json.dump({'verdict': 'CRASH', 'traceback': traceback.format_exc()},
                      fh, indent=2)
        sys.exit(3)
