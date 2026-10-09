#!/usr/bin/env python3
"""IS THE HUNG PER-SAMPLE CONTROL A PROPERTY OF THE CHATTY COPY, OR A STARTUP FLAKE?

WHY. `_main/_strip-stats-log-probe.py` is a `:control` step of the battery
(`_main/_audit-verify-all.cmd`). On the 2026-10-08 run it answered rc=3: its
per-sample arm never printed `SHELL_EXIT`, so the arm's delivered count could not
be read. The obvious story ("20 Hz logging breaks the pump") does not survive
contact with the code: the shell's stdout is `DEVNULL` in that arm, `log()` takes
one short lock, and the per-push call site sits inside the stderr pump's
`try/except` that logs `BRIDGE_STATS_CALLBACK_FAILED` — a line the hung log does
not carry. A first single-run repro stalled EARLIER still (before
`RECEIVER_READY`), which is a startup stall the repo already knows about
(~1 launch in 20, upstream of the panel-show gate, unattributed).

So this instrument runs BOTH arms N times each and reports, per launch, how far
the shell got. The claim it can settle: if the shipped shell stalls at the same
rate as the control copy, the battery's RED is an instrument flake and the log
budget is NOT the cause.

    python _main/_strip-logmutant-repro.py --repeat 3 --secs 24
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
MUTANT = os.path.join(os.path.dirname(SHELL), '_strip-logmutant-repro_sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
CREATE_NO_WINDOW = 0x08000000
HZ = 20.0
PUSH = re.compile(r'BRIDGE_STATS_PUSH count=(\d+)')
# Every line that says HOW the launch ended. The first two are the ones the hung
# control lacked; the rest prove the shell was past the WebView2 handshake.
MILESTONES = (
    'RECEIVER_READY', 'PRELOAD_ACTIVE', 'STAGING_LOADED', 'PANEL_SHOW_REFUSED',
    'BRIDGE_PUMP_DIED', 'BRIDGE_STATS_CALLBACK_FAILED', 'BRIDGE_DEATH',
    'BRIDGE_EXIT', 'BRIDGE_STOP', 'WORKER_AUTOSTART', 'SHELL_EXIT',
    'CORE_INIT', 'NAVIGATION_COMPLETED',
)


def build_mutant():
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


def cpu_of(pid):
    """CPU seconds of one pid, or None. `Get-Process`, NOT WMI (machine law)."""
    try:
        out = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f'(Get-Process -Id {pid} -ErrorAction SilentlyContinue).CPU'],
            capture_output=True, text=True, timeout=8,
            creationflags=CREATE_NO_WINDOW)
        return out.stdout.strip() or None
    except Exception:
        return None


def one_launch(arm, shell, secs, watch):
    stamp = f'{os.getpid()}-{int(time.time() * 1000) % 1000000}'
    log_path = os.path.join(HERE, f'_strip-logmutant-{arm}-{stamp}.log')
    env = dict(os.environ)
    env['SOTTO_STANDIN_HZ'] = str(HZ)
    env['SOTTO_STANDIN_SECS'] = '120'
    cmd = [PYW, shell, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--with-worker', '--worker', STANDIN,
           '--log', log_path, '--exit-after', str(secs)]
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL), env=env,
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.time()
    last_growth = started
    last_count = 0
    cpu = None
    while time.time() - started < watch:
        time.sleep(1.0)
        if proc.poll() is not None:
            break
        try:
            with open(log_path, encoding='utf-8', errors='replace') as fh:
                text = fh.read()
        except OSError:
            text = ''
        counts = PUSH.findall(text)
        count = int(counts[-1]) if counts else 0
        if count != last_count:
            last_growth, last_count = time.time(), count
        if int(time.time() - started) % 5 == 0:
            cpu = cpu_of(proc.pid) or cpu
    alive = proc.poll() is None
    if alive:
        proc.kill()
    try:
        rc = proc.wait(timeout=10)
    except Exception:
        rc = None
    quiet_for = round(time.time() - last_growth, 1)
    try:
        with open(log_path, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError:
        text = ''
    pushes = PUSH.findall(text)
    exit_line = [ln for ln in text.splitlines() if 'SHELL_EXIT' in ln]
    total = None
    if exit_line:
        m = re.search(r'statsPushes=(\d+)', exit_line[-1])
        total = int(m.group(1)) if m else None
    return {
        'arm': arm, 'pid': proc.pid, 'rc': rc, 'alive_at_end': alive,
        'quiet_for_s': quiet_for, 'push_lines': len(pushes),
        'last_push_count': int(pushes[-1]) if pushes else 0,
        'pushes_total_from_exit': total,
        'bytes': len(text),
        'reached': [m for m in MILESTONES if m in text],
        'cpu_s': cpu, 'log': log_path,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=float, default=24.0,
                    help='the probe arm runs 24 s; keep it identical')
    ap.add_argument('--watch', type=float, default=0.0,
                    help='0 = secs + 25')
    ap.add_argument('--repeat', type=int, default=3)
    args = ap.parse_args()
    watch = args.watch or args.secs + 25

    build_mutant()
    runs = []
    for i in range(args.repeat):
        for arm, shell in (('shipped', SHELL), ('per-sample', MUTANT)):
            r = one_launch(arm, shell, args.secs, watch)
            runs.append(r)
            print(f"{arm:>10} #{i + 1} rc={r['rc']} alive_at_end={r['alive_at_end']} "
                  f"quiet={r['quiet_for_s']}s push_lines={r['push_lines']} "
                  f"pushes_total={r['pushes_total_from_exit']} cpu={r['cpu_s']} "
                  f"reached={'+'.join(r['reached']) or 'NOTHING'}", flush=True)
    # The claim: a startup stall is not a property of the chatty copy.
    stalled = [r for r in runs if 'RECEIVER_READY' not in r['reached']]
    no_exit = [r for r in runs if 'SHELL_EXIT' not in r['reached']]
    per_stall = [r for r in stalled if r['arm'] == 'per-sample']
    ship_stall = [r for r in stalled if r['arm'] == 'shipped']
    per_noexit = [r for r in no_exit if r['arm'] == 'per-sample']
    ship_noexit = [r for r in no_exit if r['arm'] == 'shipped']
    print(f'REPRO-STALLS launches={len(runs)} stalled_before_receiver={len(stalled)} '
          f'(shipped={len(ship_stall)} per-sample={len(per_stall)}) '
          f'no_shell_exit={len(no_exit)} (shipped={len(ship_noexit)} '
          f'per-sample={len(per_noexit)})', flush=True)
    verdict = ('BOTH-ARMS-STALL-EQUALLY' if ship_stall and per_stall
               else 'SHIPPED-CLEAN-CONTROL-STALLS' if per_stall and not ship_stall
               else 'NO-STALL-REPRODUCED')
    print(f'REPRO-VERDICT {verdict}', flush=True)
    with open(os.path.join(HERE, '_strip-logmutant-repro.json'), 'w',
              encoding='utf-8') as fh:
        json.dump({'secs': args.secs, 'repeat': args.repeat, 'runs': runs,
                   'verdict': verdict}, fh, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
