#!/usr/bin/env python3
"""THE RESTORE ARM — the `geometry` key survives a restart, and it is CLAMPED.

`_main/_strip-surface-probe.py` proves the edit mode WRITES the key. This proves
the other half: a shell that starts with that key in the file opens at the saved
rect, and a saved rect that is no longer inside the work area is pulled back with
ONE log line.

HOW THE RACE IS WON. `_main/panel-visibility.json` is shared with the owner's
running shell (pid read out of the file), which rewrites it every 3 s WITHOUT the
key. So the seed is written immediately after one of HIS writes — the file's
mtime is watched, and the seed goes in the same instant — which leaves ~3 s of
quiet, far more than the ~1 s the shell needs to reach `create_window`.

THE FILE IS PUT BACK. The original bytes are snapshotted and written back in a
`finally`, because leaving a test rect in the owner's own file would make his next
launch open the band in a position a probe chose.

`pythonw.exe _main/_strip-restore-probe.py` — no window is ever shown: the
restore happens in `create_window`, before any show, and the arms pass
`--exit-after`.
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
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
VISIBILITY = os.path.join(HERE, 'panel-visibility.json')
REPORT = os.path.join(HERE, '_strip-restore-probe.json')
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


def seed_after_his_write(rect, wait_s=12.0):
    """Write `geometry` right after the OTHER writer touches the file.

    Returns (seeded: bool, note: str). A quiet window of one `interval_s` (3 s)
    is what makes the seed survive until the shell reads it.
    """
    try:
        before = os.stat(VISIBILITY).st_mtime_ns
    except OSError as exc:
        return False, f'stat failed {exc!r}'
    deadline = time.time() + wait_s
    while time.time() < deadline:
        time.sleep(0.05)
        try:
            now = os.stat(VISIBILITY).st_mtime_ns
        except OSError:
            continue
        if now != before:
            break
    try:
        with open(VISIBILITY, encoding='utf-8') as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return False, f'read failed {exc!r}'
    if not isinstance(payload, dict):
        return False, 'payload is not an object'
    payload['geometry'] = dict(rect)
    tmp = VISIBILITY + f'.seed-{STAMP}'
    with open(tmp, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2)
    os.replace(tmp, VISIBILITY)
    return True, f"seeded over pid={payload.get('pid')}"


def geometry_now():
    """The `geometry` key in the visibility file RIGHT NOW, or None."""
    try:
        with open(VISIBILITY, encoding='utf-8') as fh:
            payload = json.load(fh)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    geo = payload.get('geometry')
    return geo if isinstance(geo, dict) else None


def launch(tag, timeout=45.0, rect=None):
    log_path = os.path.join(HERE, f'_strip-restore-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-worker',
           '--no-tray', '--exit-after', '8', '--log', log_path]
    started = time.time()
    # THE OWNER'S OWN SHELL REWRITES THIS FILE EVERY ~3 s WITHOUT THE `geometry`
    # KEY (it runs the previous revision). Seeding once is therefore a RACE: the
    # key can be gone again before the shell under test reads it. Measured: the
    # in-bounds arm read `rect=380x900@(-10000,66)` — its own default — because
    # the seed had already been overwritten. So re-seed IMMEDIATELY before the
    # launch, and let `main` retry the case if the shell still read something
    # else. An environmental race is not a measurement of the clamp.
    reseeded = False
    if rect is not None:
        current = geometry_now()
        want = (rect.get('x'), rect.get('y'), rect.get('width'), rect.get('height'))
        have = (current.get('x'), current.get('y'), current.get('width'),
                current.get('height')) if current else None
        if have != want:
            seed_after_his_write(rect, wait_s=1.0)
            reseeded = True
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
        'tag': tag,
        'rc': proc.returncode,
        'log': log_path,
        'reseeded': reseeded,
        'wall_s': round(time.time() - started, 2),
        'cost': process_cost(int(proc._handle)) if proc._handle else {},
        'restored': lines(text, 'PANEL_GEOMETRY_RESTORED'),
        'clamped': lines(text, 'PANEL_GEOMETRY_CLAMPED'),
        'refused': lines(text, 'PANEL_GEOMETRY_RESTORE_REFUSED'),
        'failed': lines(text, 'PANEL_GEOMETRY_RESTORE_FAILED'),
        'window_geometry': lines(text, 'WINDOW_GEOMETRY'),
        'panel_shown': lines(text, 'PANEL_SHOWN'),
        'visibility': lines(text, 'PANEL_VISIBILITY_MODE'),
    }


CASES = [
    ('in-bounds', {'surface': 'strip', 'x': 700, 'y': 400, 'width': 1040,
                   'height': 148, 'docked': 'edited', 'workWidth': 1920,
                   'workHeight': 1032}, False),
    ('off-screen', {'surface': 'strip', 'x': 5000, 'y': 5000, 'width': 1040,
                    'height': 148, 'docked': 'edited', 'workWidth': 1920,
                    'workHeight': 1032}, True),
]


def main():
    report = {'shell': SHELL, 'visibility_file': VISIBILITY, 'stamp': STAMP,
              'cases': {}}
    with open(VISIBILITY, 'rb') as fh:
        original = fh.read()
    report['original_len'] = len(original)
    try:
        for name, rect, expect_clamped in CASES:
            want_surface = rect['surface']
            want = (f'rect={rect["width"]}x{rect["height"]}@({rect["x"]},{rect["y"]})'
                    if not expect_clamped else 'clamped=true')
            # Up to TWO attempts: the first, and — only if the owner's concurrent
            # write destroyed the seed before the shell read it — one retry. An
            # environmental race must not be recorded as a clamp failure.
            attempts = []
            for attempt in (1, 2):
                seeded, note = seed_after_his_write(rect)
                run = launch(f'{name}-a{attempt}', rect=rect)
                attempts.append({'attempt': attempt, 'seeded': seeded,
                                 'seed_note': note, **run})
                good = bool([ln for ln in run['restored'] if want in ln])
                read_ours = any(want_surface in ln for ln in run['restored'])
                if good or read_ours or attempt == 2:
                    break
            run = attempts[-1]
            report['cases'][name] = {
                'expected_clamped': expect_clamped,
                'attempts': [{k: v for k, v in a.items()
                              if k in ('attempt', 'seeded', 'rc', 'reseeded')}
                             for a in attempts],
                **run,
            }
    finally:
        with open(VISIBILITY, 'wb') as fh:
            fh.write(original)
        report['file_restored'] = True

    checks = []
    for name, rect, expect_clamped in CASES:
        case = report['cases'][name]
        want = (f'rect={rect["width"]}x{rect["height"]}@({rect["x"]},{rect["y"]})'
                if not expect_clamped else 'clamped=true')
        checks.append((
            f'{name}: the shell restored the saved rect and clamped={expect_clamped}',
            bool([ln for ln in case['restored'] if want in ln])))
        checks.append((f'{name}: a clamp line is present iff it moved',
                       bool(case['clamped']) == expect_clamped))
        checks.append((f'{name}: the window was never shown',
                       not case['panel_shown']))
    report['checks'] = [{'what': w, 'ok': bool(o)} for w, o in checks]
    failed = [w for w, o in checks if not o]
    report['verdict'] = 'GREEN' if not failed else 'RED'
    report['failed'] = failed
    report['probe_cost'] = process_cost(kernel32.GetCurrentProcess())
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
