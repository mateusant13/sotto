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
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
MUTANT = os.path.join(os.path.dirname(SHELL), '_strip-logmutant_sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
REPORT = os.path.join(HERE, '_strip-stats-log-probe.json')
STAMP = f'{os.getpid()}-{int(time.time())}'

CREATE_NO_WINDOW = 0x08000000
HZ = 20.0
RUN_S = 24.0
#: Bytes are counted only after the shell has finished starting, so the startup
#: lines are not attributed to the feed.
SETTLE_S = 6.0
#: A shell that never reaches this milestone is stuck on something environmental
#: (WebView2 start, a leftover instance) — NOT a property of the log budget — so
#: the arm is RETRIED once. `RECEIVER_READY` is the milestone that means the page
#: is live; if it is absent the shell never got far enough to push anything.
READY_MILESTONE = 'RECEIVER_READY'


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def lines(text, needle):
    return [ln for ln in text.splitlines() if needle in ln]


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


def run_arm(tag, shell):
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
    # The window starts once the shell has settled: `--exit-after` counts from the
    # panel load, so measure from there.
    deadline = time.time() + RUN_S + 20
    settle_until = started + SETTLE_S
    while time.time() < settle_until and proc.poll() is None:
        time.sleep(0.25)
    baseline = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    t0 = time.time()
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.25)
    try:
        proc.wait(timeout=20)
        killed = False
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
        killed = True
    t1 = time.time()
    size = os.path.getsize(log_path) if os.path.exists(log_path) else 0
    text = read_log(log_path)
    window = max(0.001, t1 - t0)
    grew = max(0, size - baseline)
    push_lines = lines(text, 'BRIDGE_STATS_PUSH')
    # THE NUMBER THAT MATTERS: bytes the FEED put in the log, isolated from the
    # shell's own periodic lines (which grow the file in both arms).
    push_bytes = sum(len(ln) + 1 for ln in push_lines)
    exit_line = lines(text, 'SHELL_EXIT')
    total = None
    if exit_line:
        m = re.search(r'statsPushes=(\d+)', exit_line[-1])
        if m:
            total = int(m.group(1))
    # DELIVERED, robust to a killed arm: `SHELL_EXIT` is the clean source, and
    # the cumulative `count=` is the fallback that survives a stall.
    delivered = total if total is not None else max_count(push_lines)
    # Did the page actually come up? `RECEIVER_READY` is the milestone the
    # house logs before any push; if it is missing, the shell never reached the
    # point where it COULD push, and the numbers below say nothing about the
    # log budget.
    ready = bool(lines(text, READY_MILESTONE))
    return {
        'tag': tag, 'shell': shell, 'log': log_path, 'rc': proc.returncode,
        'killed': killed, 'ready': ready,
        'window_s': round(window, 2),
        'baseline_bytes': baseline,
        'final_bytes': size,
        'grew_bytes': grew,
        'bytes_per_min': round(grew / window * 60.0, 1),
        'push_lines': len(push_lines),
        'push_bytes': push_bytes,
        'push_bytes_per_min': round(push_bytes / window * 60.0, 1),
        'pushes_total': total,
        'delivered': delivered,
        'autostart': lines(text, 'WORKER_AUTOSTART'),
        'push_sample': push_lines[:2],
    }


def run_arm_with_retry(tag, shell):
    """Run an arm once, and RETRY once if the shell stalled before it was ready.

    A launch that never reaches `RECEIVER_READY` is stuck on something
    environmental, not on the property under test. Retrying once keeps a
    transient from being recorded as a measurement of the log budget. The
    result reports which attempt was kept and every attempt's `ready`/`killed`.
    """
    attempts = []
    for attempt in (1, 2):
        result = run_arm(f'{tag}-a{attempt}', shell)
        attempts.append(result)
        if result['ready'] and not result['killed']:
            result['attempt'] = attempt
            result['attempts'] = [{'attempt': a['attempt'] if 'attempt' in a else i + 1,
                                   'ready': a['ready'], 'killed': a['killed'],
                                   'delivered': a['delivered']}
                                  for i, a in enumerate(attempts)]
            return result
    # Both attempts failed to come up ready: keep the LAST attempt's numbers but
    # mark them, so the caller's checks see `ready=false` / `killed=true`.
    kept = attempts[-1]
    kept['attempt'] = len(attempts)
    kept['attempts'] = [{'attempt': i + 1, 'ready': a['ready'],
                         'killed': a['killed'], 'delivered': a['delivered']}
                        for i, a in enumerate(attempts)]
    return kept


def main():
    report = {'shell': SHELL, 'hz': HZ, 'run_s': RUN_S, 'settle_s': SETTLE_S}
    try:
        build_mutant()
        report['per_sample'] = run_arm_with_retry('per-sample', MUTANT)
        report['aggregated'] = run_arm_with_retry('aggregated', SHELL)
    finally:
        try:
            os.remove(MUTANT)
        except OSError:
            pass

    per = report['per_sample']
    agg = report['aggregated']
    # `delivered` survives a killed arm; `pushes_total` is the clean source when
    # the shell reached `SHELL_EXIT`.
    per_delivered = per['delivered']
    agg_delivered = agg['delivered']
    checks = [
        ('both arms ran the stand-in worker at the same rate',
         bool([ln for ln in per['autostart'] if 'reason=with-worker' in ln])
         and bool([ln for ln in agg['autostart'] if 'reason=with-worker' in ln])),
        # A shell that never came up ready is an ENVIRONMENTAL fault, not a
        # log-budget measurement: name it so the RED reads as the stall it is.
        ('both arms reached the live page (READY) and exited on their own',
         per['ready'] and agg['ready'] and not per['killed'] and not agg['killed']),
        ('the per-sample arm logged a line PER SAMPLE (>= 100 lines)',
         per['push_lines'] >= 100),
        ('the aggregated arm logged at most a handful of lines',
         agg['push_lines'] <= 3),
        ('the feed\'s bytes per minute fall by at least 50x',
         agg['push_bytes_per_min'] * 50 <= per['push_bytes_per_min']),
        ('the aggregated arm still DELIVERED the feed (delivered > 100)',
         agg_delivered > 100),
        ('the per-sample arm delivered the same feed (the control is not idle)',
         per_delivered > 100),
    ]
    report['checks'] = [{'what': w, 'ok': bool(o)} for w, o in checks]
    failed = [w for w, o in checks if not o]
    report['verdict'] = 'GREEN' if not failed else 'RED'
    report['failed'] = failed
    report['ratio'] = round(
        per['push_bytes_per_min'] / max(0.001, agg['push_bytes_per_min']), 1)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    # ALWAYS PRINT. A probe that only prints when it passes writes a 0-byte
    # step log on a RED run, and the battery's `:control` kind then cannot find
    # its verdict sentence — which reads as "the instrument never ran" instead
    # of "the instrument ran and failed". The FAIL line is that sentence.
    if not failed:
        print(f'STRIP-LOG CONTROL PASS ratio={report["ratio"]}x '
              f'per_sample_lines={per["push_lines"]} '
              f'per_sample_bytes_per_min={per["push_bytes_per_min"]} '
              f'aggregated_lines={agg["push_lines"]} '
              f'aggregated_bytes_per_min={agg["push_bytes_per_min"]} '
              f'delivered={agg_delivered}')
    else:
        print(f'STRIP-LOG CONTROL FAIL ratio={report["ratio"]}x '
              f'failed={len(failed)} reason={"; ".join(failed)} '
              f'per_sample(ready={per["ready"]},killed={per["killed"]},'
              f'lines={per["push_lines"]},delivered={per_delivered}) '
              f'aggregated(ready={agg["ready"]},killed={agg["killed"]},'
              f'lines={agg["push_lines"]},delivered={agg_delivered})')
    return 0 if not failed else 3


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
