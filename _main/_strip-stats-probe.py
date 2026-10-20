#!/usr/bin/env python3
"""THE STATS ARM — `getStats`/`onStats` really FEED the panel's level meter.

TASK D of this lane: the panel's wave (`panel.js:1640-1685`, `pushLevel` →
`paintLevel`) depends on two bridge members the shell never had. A text check
proves the names exist; it cannot prove the panel is FED. So this arm runs the
shell with a STAND-IN worker that publishes real `WORKER_STATS` numbers on stderr
and opens NO audio device, then reads the consequence out of the panel's OWN DOM:

  * `body.dataset.level` — `paintLevel` sets it to `'live'` only when a finite
    level has actually arrived (`panel.js:1668-1669`);
  * the ten `.chrome__meter i` bars' inline `--meter-h`, which is what the CSS
    draws.

Both the PULL (the panel's own 1000 ms `getStats` poll) and the PUSH (the shell
forwarding each `WORKER_STATS`) are logged by the shell as
`BRIDGE_STATS_REPLY`/`BRIDGE_STATS_PUSH`, so the two halves are separable.

NO WINDOW: `--show` is not passed, and `--probe-stats` reads the DOM through
`exec_js`, which needs no mapped surface.

WHAT CHANGED ON 2026-10-20 (this file is not the same file it was). This gate
failed on the same night as the log-budget gate, for the same reason and through
the same door: the PANEL did not come up. Both arms read the DOM of a page
that never loaded, every "the panel said" check failed, and the gate reported
`rc=3` — a RED about the BOX, dressed as a RED about the product. The measured
facts: on a loaded box the page took 63.58 s to reach the stage and never went
live inside the arm's window; on a calm box the same app reaches
`RECEIVER_READY` in 1.98 s (`I:\\cc-tmp\\sotto-032942.log`).

So this gate now measures the PANEL'S STARTUP too, and a page that does not go
live inside the deadline makes the gate SKIP — loudly, with the numbers —
instead of failing the product. The CLAIM of the gate did not change: when the
page is live, the meter must go live with it, the push must really land, and
the control (no worker) must stay dark. The deadline, its justification and the
shared decision live in `_main/_strip_stats_load.py`; the gate that proves that
decision honest (with four broken copies of it) is
`_main/_strip-stats-load-oracle.py`.

    pythonw.exe _main/_strip-stats-probe.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import _strip_stats_load as load  # noqa: E402  (the path fix has to come first)

ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
REPORT = os.path.join(HERE, '_strip-stats-probe.json')
STAMP = f'{os.getpid()}-{int(time.time())}'

CREATE_NO_WINDOW = 0x08000000
#: How long the page has to go LIVE before the arm is declared unmeasurable.
#: 30 s = 15x the measured calm startup (1.98 s) and 2.1x below the measured
#: loaded one (63.58 s to `STAGING_SEEN`, before `RECEIVER_READY`).
READY_DEADLINE_S = load.READY_DEADLINE_S
#: The slack between the watcher's clock and the log's own clock.
CLOCK_MARGIN_S = 5.0

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


kernel32.GetProcessTimes.argtypes = [wt.HANDLE, ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME)]
kernel32.GetProcessTimes.restype = wt.BOOL
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.GetCurrentProcess.argtypes = []
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE,
                                       ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                                       wt.DWORD]
psapi.GetProcessMemoryInfo.restype = wt.BOOL


def _ticks(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def process_cost(handle):
    creation, exit_t, kernel_t, user_t = (wt.FILETIME() for _ in range(4))
    out = {'cpu_s': None, 'peak_ws_bytes': None}
    if kernel32.GetProcessTimes(handle, ctypes.byref(creation),
                                ctypes.byref(exit_t),
                                ctypes.byref(kernel_t), ctypes.byref(user_t)):
        out['cpu_s'] = round((_ticks(kernel_t) + _ticks(user_t)) / 1e7, 3)
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                  ctypes.sizeof(counters)):
        out['peak_ws_bytes'] = int(counters.PeakWorkingSetSize)
    return out


def kill_tree(proc):
    """Kill THIS arm's shell (and the stand-in worker it spawned).

    The shell is the measurement's own child, so killing it is allowed; the
    owner's app is a different pid and is never touched. The wait is bounded
    and NEVER raises: an earlier version raised `TimeoutExpired` here and
    turned a slow box into a CRASH of the instrument.
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


def wait_ready(proc, log_path, started, deadline_s, margin_s=CLOCK_MARGIN_S):
    """Wait for the page to go LIVE, bounded by the deadline.

    Returns (seen, waited_s, alive_at_deadline): whether the `RECEIVER_READY`
    line appeared, how long the wait took, and whether the shell was STILL
    RUNNING when the wait ended. A slow shell is the box; a DEAD shell is the
    product, and the two must not be confused.
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


def run_arm(tag, extra, timeout=60.0):
    log_path = os.path.join(HERE, f'_strip-stats-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--log', log_path] + list(extra)
    started = time.time()
    err_path = log_path + '.err'
    err_fh = open(err_path, 'wb')
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=err_fh)
    # PHASE 1 — the page has to go LIVE before the DOM says anything.
    seen, waited, alive = wait_ready(proc, log_path, started, READY_DEADLINE_S)
    readiness = load.arm_readiness(load.read_log(log_path), READY_DEADLINE_S)
    ready = readiness['ready']
    # PHASE 2 — the probe reads the DOM 8 s after the page is live and the
    # shell exits on its own (`--exit-after` is armed when the panel loads).
    killed = False
    if ready:
        deadline = time.time() + timeout
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.25)
    if proc.poll() is None:
        killed = True
        kill_tree(proc)
    err_fh.close()
    try:
        with open(err_path, 'rb') as fh:
            stderr_tail = fh.read().decode('utf-8', 'replace')[-2000:]
    except OSError:
        stderr_tail = ''
    text = load.read_log(log_path)
    return {
        'tag': tag, 'rc': proc.returncode, 'log': log_path,
        'wall_s': round(time.time() - started, 2),
        'cost': process_cost(int(proc._handle)) if proc._handle else {},
        'ready': ready,
        'ready_s': readiness['ready_s'],
        'waited_s': round(waited, 2),
        'deadline_s': READY_DEADLINE_S,
        'shell_alive_at_deadline': alive,
        'timeline': readiness['timeline'],
        'readiness_reason': readiness['reason'],
        'killed': killed,
        'autostart': load.log_lines(text, 'WORKER_AUTOSTART'),
        'probe': load.log_lines(text, 'PANEL_STATS_PROBE '),
        'armed': load.log_lines(text, 'PANEL_STATS_PROBE_ARMED'),
        'replies': load.log_lines(text, 'BRIDGE_STATS_REPLY'),
        'pushes': load.log_lines(text, 'BRIDGE_STATS_PUSH'),
        'panel_shown': load.log_lines(text, 'PANEL_SHOWN'),
        'page_errors': load.log_lines(text, 'PAGE_ERROR'),
        'receiver_ready': load.log_lines(text, 'RECEIVER_READY'),
        'stderr_tail': stderr_tail,
        'log_bytes': len(text),
        'ran': proc.returncode == 0 and bool(text.strip()),
        'text': text,
    }


def main():
    report = {'shell': SHELL, 'standin': STANDIN, 'stamp': STAMP, 'arms': {},
              'ready_deadline_s': READY_DEADLINE_S,
              'deadline_facts': load.deadline_facts(READY_DEADLINE_S)}

    # ARM 1 — WITH the stand-in worker: the panel's poll AND the push both have
    #         real numbers, so the meter must go live.
    fed = run_arm('fed', ['--with-worker', '--worker', STANDIN,
                          '--probe-stats', '--probe-stats-wait', '8',
                          '--exit-after', '20'])
    # ARM 2 — the SAME run with NO worker: the honest control. The member exists
    #         and is answered, but there is no measurement, so the meter must
    #         STAY at `none` — an absent field must never become a zero
    #         (`panel.js:1641` refuses a non-finite peak).
    unfed = run_arm('unfed', ['--no-worker', '--probe-stats',
                              '--probe-stats-wait', '8', '--exit-after', '20'])
    report['arms']['fed'] = {k: v for k, v in fed.items() if k != 'text'}
    report['arms']['unfed'] = {k: v for k, v in unfed.items() if k != 'text'}

    def probe_of(run):
        if not run['probe']:
            return {}
        try:
            parsed = json.loads(run['probe'][0].split('PANEL_STATS_PROBE ', 1)[1])
        except ValueError:
            return {}
        # A `null` here is a FAILED page probe (a JS syntax error, a timeout), not
        # an empty measurement — and `None.get` would crash the whole instrument.
        # Measured: a `//` comment inside the one-line script did exactly this.
        return parsed if isinstance(parsed, dict) else {'probe_failed': parsed}

    fed_probe = probe_of(fed)
    unfed_probe = probe_of(unfed)
    report['fed_probe'] = fed_probe
    report['unfed_probe'] = unfed_probe

    fed_bars = [b for b in fed_probe.get('bars', []) if b]
    unfed_bars = [b for b in unfed_probe.get('bars', []) if b]
    checks = [
        # AN ARM THAT NEVER RAN IS NOT A PASS. Measured 2026-10-11: the fed argv
        # carried --probe-stats/--probe-stats-wait, the live shell defined
        # neither, argparse exited 2 in 0.25 s and NO LOG EXISTED -- so every
        # list was empty and SEVEN of the fifteen checks went green on nothing.
        # The rc and the child's stderr are recorded now, and every 'nothing
        # happened' check below is guarded on the run having happened at all.
        ('fed: the shell ran at all (rc=0 and a log was written)', fed['ran']),
        ('fed: the shell ARMED the stats probe', bool(fed['armed'])),
        ('unfed: the shell ran at all (rc=0 and a log was written)',
         unfed['ran']),
        ('fed: the shell started the stand-in (reason=with-worker)',
         bool([ln for ln in fed['autostart'] if 'reason=with-worker' in ln])),
        ('fed: the panel POLLED and was answered',
         fed['ran'] and bool(fed['replies'])),
        ('fed: the shell PUSHED the worker counters',
         fed['ran'] and bool(fed['pushes'])),
        # The payload is the stand-in's own measurement, so the check reads a
        # NON-ZERO finite peak out of the line instead of a magic number typed
        # from one run (the earlier version pinned 0.443448/812.0).
        ('fed: the push carries a real peak and a block count',
         bool([ln for ln in fed['pushes']
               if re.search(r'"peak":(?!0(?:\.0+)?(?:[,\}]))[0-9.]+', ln)
               and '"blocks":' in ln])),
        ('fed: the panel\'s own DOM says data-level=live',
         fed['ran'] and fed_probe.get('level') == 'live'),
        ('fed: the meter bars carry a --meter-h',
         fed['ran'] and len(fed_bars) == 10),
        # THE SEPARATION THAT MATTERS: `data-level=live` alone could be the 1000 ms
        # POLL doing all the work. The page's own push counter must show the PUSH
        # landing too — that is the half the parent asked for.
        ('fed: the PUSH really landed in the page (emit counts.stats >= 2)',
         fed['ran'] and (fed_probe.get('emits') or {}).get('stats', 0) >= 2),
        ('fed: the push is logged at most once per interval, not per sample',
         fed['ran'] and len(fed['pushes']) <= 2),
        ('fed: no page error', fed['ran'] and not fed['page_errors']),
        ('fed: the window was never shown',
         fed['ran'] and not fed['panel_shown']),
        ('unfed: the control did NOT go live (absent is not zero)',
         unfed['ran'] and unfed_probe.get('level') != 'live'),
        ('unfed: the control has no bars painted',
         unfed['ran'] and not unfed_bars),
        ('unfed: the control still POLLED and was answered',
         unfed['ran'] and bool(unfed['replies'])),
        ('unfed: the control pushed nothing (no worker, no counters)',
         unfed['ran'] and not unfed['pushes']),
        ('unfed: no page error',
         unfed['ran'] and not unfed['page_errors']),
    ]
    report['checks'] = [{'what': w, 'ok': bool(o)} for w, o in checks]
    failed = [w for w, o in checks if not o]
    # THE DECISION is the shared one: a page that did not come up in time makes
    # this run UNMEASURED (a SKIP with the numbers), and only a measured run
    # gets to fail.
    verdict = load.decide([fed, unfed], checks, READY_DEADLINE_S)
    report['verdict'] = verdict['verdict']
    report['failed'] = verdict.get('failed') or []
    report['skip_reason'] = verdict.get('skip_reason')
    report['probe_cost'] = process_cost(kernel32.GetCurrentProcess())
    report['shell_cpu_total_s'] = round(sum(
        (report['arms'][a].get('cost') or {}).get('cpu_s') or 0.0
        for a in ('fed', 'unfed')), 3)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    if verdict['verdict'] == 'GREEN':
        print(f'STRIP-STATS VERDICT: GREEN - the meter really is fed: '
              f'level={fed_probe.get("level")} '
              f'bars={len(fed_bars)} '
              f'emits.stats={(fed_probe.get("emits") or {}).get("stats")} '
              f'pushes={len(fed["pushes"])} '
              f'control_level={unfed_probe.get("level")} '
              f'ready_s(fed={fed["ready_s"]},unfed={unfed["ready_s"]}) '
              f'deadline={READY_DEADLINE_S:.0f}s')
    elif verdict['verdict'] == 'SKIP':
        print(f'STRIP-STATS VERDICT: SKIPPED - {verdict["skip_reason"]} | '
              f'deadline={READY_DEADLINE_S:.0f}s per arm | '
              f'fed(ready={fed["ready"]},ready_s={fed["ready_s"]},'
              f'waited_s={fed["waited_s"]}) '
              f'unfed(ready={unfed["ready"]},ready_s={unfed["ready_s"]},'
              f'waited_s={unfed["waited_s"]}) | this run CANNOT claim the wave')
    else:
        print(f'STRIP-STATS VERDICT: RED - failed={len(report["failed"])} '
              f'reason={verdict["reason"]} '
              f'fed(ready={fed["ready"]},ready_s={fed["ready_s"]},'
              f'level={fed_probe.get("level")}) '
              f'unfed(ready={unfed["ready"]},level={unfed_probe.get("level")})')
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
