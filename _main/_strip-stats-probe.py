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

    pythonw.exe _main/_strip-stats-probe.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
STANDIN = os.path.join(HERE, '_strip-stats-worker.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
REPORT = os.path.join(HERE, '_strip-stats-probe.json')
STAMP = f'{os.getpid()}-{int(time.time())}'

CREATE_NO_WINDOW = 0x08000000
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
                                ctypes.byref(exit_t), ctypes.byref(kernel_t),
                                ctypes.byref(user_t)):
        out['cpu_s'] = round((_ticks(kernel_t) + _ticks(user_t)) / 1e7, 3)
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                  ctypes.sizeof(counters)):
        out['peak_ws_bytes'] = int(counters.PeakWorkingSetSize)
    return out


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def lines(text, needle):
    return [ln.strip() for ln in text.splitlines() if needle in ln]


def run_arm(tag, extra, timeout=60.0):
    log_path = os.path.join(HERE, f'_strip-stats-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-tray',
           '--log', log_path] + list(extra)
    started = time.time()
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + timeout
    while time.time() < deadline and proc.poll() is None:
        time.sleep(0.25)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    text = read_log(log_path)
    return {
        'tag': tag, 'rc': proc.returncode, 'log': log_path,
        'wall_s': round(time.time() - started, 2),
        'cost': process_cost(int(proc._handle)) if proc._handle else {},
        'autostart': lines(text, 'WORKER_AUTOSTART'),
        'probe': lines(text, 'PANEL_STATS_PROBE '),
        'armed': lines(text, 'PANEL_STATS_PROBE_ARMED'),
        'replies': lines(text, 'BRIDGE_STATS_REPLY'),
        'pushes': lines(text, 'BRIDGE_STATS_PUSH'),
        'panel_shown': lines(text, 'PANEL_SHOWN'),
        'page_errors': lines(text, 'PAGE_ERROR'),
        'receiver_ready': lines(text, 'RECEIVER_READY'),
        'text': text,
    }


def main():
    report = {'shell': SHELL, 'standin': STANDIN, 'stamp': STAMP, 'arms': {}}

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
        ('fed: the shell started the stand-in (reason=with-worker)',
         bool([ln for ln in fed['autostart'] if 'reason=with-worker' in ln])),
        ('fed: the panel POLLED and was answered',
         bool(fed['replies'])),
        ('fed: the shell PUSHED the worker counters',
         bool(fed['pushes'])),
        ('fed: the push carries the worker\'s own peak',
         bool([ln for ln in fed['pushes'] if '"peak":0.443448' in ln
               and '"blocks":812.0' in ln])),
        ('fed: the panel\'s own DOM says data-level=live',
         fed_probe.get('level') == 'live'),
        ('fed: the meter bars carry a --meter-h',
         len(fed_bars) == 10),
        # THE SEPARATION THAT MATTERS: `data-level=live` alone could be the 1000 ms
        # POLL doing all the work. The page's own push counter must show the PUSH
        # landing too — that is the half the parent asked for.
        ('fed: the PUSH really landed in the page (emit counts.stats >= 2)',
         (fed_probe.get('emits') or {}).get('stats', 0) >= 2),
        ('fed: the push is logged at most once per interval, not per sample',
         len(fed['pushes']) <= 2),
        ('fed: no page error', not fed['page_errors']),
        ('fed: the window was never shown', not fed['panel_shown']),
        ('unfed: the control did NOT go live (absent is not zero)',
         unfed_probe.get('level') != 'live'),
        ('unfed: the control has no bars painted', not unfed_bars),
        ('unfed: the control still POLLED and was answered',
         bool(unfed['replies'])),
        ('unfed: the control pushed nothing (no worker, no counters)',
         not unfed['pushes']),
        ('unfed: no page error', not unfed['page_errors']),
    ]
    report['checks'] = [{'what': w, 'ok': bool(o)} for w, o in checks]
    failed = [w for w, o in checks if not o]
    report['verdict'] = 'GREEN' if not failed else 'RED'
    report['failed'] = failed
    report['probe_cost'] = process_cost(kernel32.GetCurrentProcess())
    report['shell_cpu_total_s'] = round(sum(
        (report['arms'][a].get('cost') or {}).get('cpu_s') or 0.0
        for a in ('fed', 'unfed')), 3)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
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
