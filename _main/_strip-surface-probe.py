#!/usr/bin/env python3
"""RUNTIME probe for the strip surface + the edit mode — the shell, really run.

FOUR arms, and NONE of them ever puts a window on the owner's screen:

  A. `--probe-outside-click` — the shell's own "visible but not seen" mode
     (`form.Opacity = 0`). Proves Alt+C's path applies the STRIP: the document
     surface, the HWND rect, the client area, and the rect READ BACK after the
     move, all out of the shell's own log.
  B. a plain `--exit-after` run with a **100 ms window census over the shell's
     own pid tree** — the 60 s house census cannot prove absence (AGENTS), so
     this samples at its own cadence.
  C. the tray menu, read out of the shell's own `TRAY_MENU` line, including the
     `Edit caption position` id.
  D. `--probe-edit-mode` — enter through the tray's command id, one drag sample
     through the watcher thread's real message loop, leave, and the `geometry`
     key read back OFF DISK by the shell itself (the file that already exists —
     never a second one).

`pythonw.exe` with `CREATE_NO_WINDOW`; the pid comes from the shell's own first
log line and only THAT pid is ever terminated. Log paths are unique per run, so a
stale shell holding an old log can never break the run.

    pythonw.exe _main/_strip-surface-probe.py
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
REPORT = os.path.join(HERE, '_strip-surface-probe.json')
STAMP = f'{os.getpid()}-{int(time.time())}'

CREATE_NO_WINDOW = 0x08000000
user32 = ctypes.WinDLL('user32', use_last_error=True)
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
    """CPU seconds (user+kernel) and peak working set — the lane's own bill.

    Native `GetProcessTimes`/`GetProcessMemoryInfo` on a handle the caller
    already owns: two syscalls, no WMI, no process walk.
    """
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

GWL_STYLE = -16
WS_VISIBLE = 0x10000000
ID_TRAY_EDIT = 3

user32.EnumWindows.restype = wt.BOOL
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.restype = ctypes.c_int

ENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def windows_of_pid(pid):
    found = []

    def visit(hwnd, _lparam):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            style = user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            klass = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, klass, 256)
            found.append({
                'hwnd': int(hwnd),
                'visible_style': bool(style & WS_VISIBLE),
                'visible_api': bool(user32.IsWindowVisible(hwnd)),
                'title': title.value,
                'class': klass.value,
            })
        return True

    user32.EnumWindows(ENUMPROC(visit), 0)
    return found


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def lines(text, needle):
    return [ln.strip() for ln in text.splitlines() if needle in ln]


def launch(tag, extra, census_ms=None, timeout=60.0, settle=0.0):
    """Run the shell once and watch it. Returns everything a check may need."""
    log_path = os.path.join(HERE, f'_strip-surface-probe-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-worker',
           '--log', log_path] + list(extra)
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    started = time.time()
    shell_pid = None
    samples = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = read_log(log_path)
        m = re.search(r'shell=webview2 .*?pid=(\d+)', text)
        if m and shell_pid is None:
            shell_pid = int(m.group(1))
        if census_ms and shell_pid:
            for w in windows_of_pid(shell_pid):
                if w['visible_api']:
                    samples.append({'t': round(time.time(), 3), **w})
        if proc.poll() is not None:
            break
        time.sleep((census_ms or 250) / 1000.0)
    if settle:
        time.sleep(settle)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    text = read_log(log_path)
    cost = process_cost(int(proc._handle)) if proc._handle else {}
    return {
        'tag': tag,
        'pid': shell_pid,
        'rc': proc.returncode,
        'log': log_path,
        'text': text,
        'wall_s': round(time.time() - started, 2),
        'cost': cost,
        'census_samples_visible': len(samples),
        'census_visible_detail': samples[:5],
    }


def arm_a(report):
    run = launch('a', ['--no-tray', '--probe-outside-click'], timeout=70)
    text = run['text']
    surface = lines(text, 'PANEL_SURFACE ')
    geometry = lines(text, 'WINDOW_GEOMETRY')
    probe = lines(text, 'OUTSIDE_CLICK_PROBE ')
    report['A'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'probe': probe,
        'surface': surface,
        'window_geometry': geometry,
        'strip_height': lines(text, 'STRIP_HEIGHT '),
        'client_area': lines(text, 'panel client area forced'),
        'panel_shown': lines(text, 'PANEL_SHOWN'),
        'outside_click': lines(text, 'OUTSIDE_CLICK source='),
        'restored': lines(text, 'PANEL_GEOMETRY_RESTORED'),
        'clamped': lines(text, 'PANEL_GEOMETRY_CLAMPED'),
        'page_errors': lines(text, 'PAGE_ERROR'),
        'receiver_ready': lines(text, 'RECEIVER_READY'),
        'preload': lines(text, 'PRELOAD_ACTIVE'),
        'shell_exit': lines(text, 'SHELL_EXIT'),
        # The rect the WINDOW really has, read back after the move — the number
        # that catches a SetWindowPos that "succeeded" without moving anything.
        'rect_after_show': lines(text, 'OUTSIDE_CLICK_PROBE shown'),
    }
    report['A']['applied_strip'] = bool([ln for ln in surface
                                         if 'surface=strip' in ln])
    report['A']['strip_line'] = ([ln for ln in surface
                                  if 'surface=strip'] or [None])[0]
    return run


def arm_b(report):
    run = launch('b', ['--no-tray', '--exit-after', '8'],
                 census_ms=100, timeout=45)
    report['B'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'census_ms': 100,
        'census_samples_visible': run['census_samples_visible'],
        'census_visible_detail': run['census_visible_detail'],
        'panel_shown_lines': lines(run['text'], 'PANEL_SHOWN'),
        'window_geometry': lines(run['text'], 'WINDOW_GEOMETRY'),
        'visibility_at_startup': lines(run['text'], 'PANEL_VISIBILITY_AT_STARTUP'),
        'receiver_ready': lines(run['text'], 'RECEIVER_READY'),
        'shell_exit': lines(run['text'], 'SHELL_EXIT'),
    }
    report['B']['no_visible_sample'] = run['census_samples_visible'] == 0
    return run


def arm_c(report):
    run = launch('c', ['--exit-after', '6'], timeout=35)
    text = run['text']
    menu = lines(text, 'TRAY_MENU')
    report['C'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'tray_menu': menu,
        'tray_window': lines(text, 'TRAY_WINDOW'),
        'tray_icon_add': lines(text, 'TRAY_ICON_ADD'),
        'tray_icon_delete': lines(text, 'TRAY_ICON_DELETE'),
    }
    first = menu[0] if menu else ''
    report['C']['has_edit_item'] = f"[{ID_TRAY_EDIT}]='Edit caption position'" in first
    report['C']['has_quit_item'] = "[2]='Quit Sotto'" in first
    report['C']['has_open_item'] = "[1]='Open panel'" in first
    return run


def arm_d(report):
    # `--exit-after` is a BACKSTOP on top of the shell's own always-exit wrapper:
    # a measurement mode that can leave a hidden shell alive forever is a defect
    # in the instrument, and it cost this lane one 70 s hang to learn.
    run = launch('d', ['--probe-edit-mode', '--exit-after', '25'], timeout=70)
    text = run['text']
    saved = lines(text, 'PANEL_EDIT_GEOMETRY_SAVED')
    on_disk = lines(text, 'PANEL_EDIT_PROBE file_geometry=')
    report['D'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'probe_begin': lines(text, 'PANEL_EDIT_PROBE begin'),
        'enter': lines(text, 'PANEL_EDIT_MODE on=true'),
        'after_enter': lines(text, 'PANEL_EDIT_PROBE after_enter'),
        'outside_while_editing': lines(
            text, 'PANEL_EDIT_PROBE outside_click_while_editing'),
        'drag': lines(text, 'PANEL_EDIT_PROBE drag '),
        'saved': saved,
        'file_line': on_disk,
        'leave': lines(text, 'PANEL_EDIT_MODE on=false'),
        'after_leave': lines(text, 'PANEL_EDIT_PROBE after_leave'),
        'surface': lines(text, 'PANEL_SURFACE '),
        'window_geometry': lines(text, 'WINDOW_GEOMETRY'),
        'no_drag_warning': lines(text, 'PANEL_EDIT_MODE_NO_DRAG'),
        'style_failures': lines(text, 'PANEL_EDIT_MODE_STYLE_FAILED'),
        'page_errors': lines(text, 'PAGE_ERROR'),
        'shell_exit': lines(text, 'SHELL_EXIT'),
    }
    report['D']['file_geometry'] = None
    if on_disk:
        m = re.search(r'file_geometry=(\{.*?\}) file_pid=', on_disk[0])
        if m:
            try:
                report['D']['file_geometry'] = json.loads(m.group(1))
            except ValueError:
                pass
    # And the same read from OUTSIDE the process — context only: an older shell
    # of the owner's rewrites this file every 3 s WITHOUT the key, so a miss here
    # is not a failure and is reported as what it is.
    try:
        with open(VISIBILITY, encoding='utf-8') as fh:
            payload = json.load(fh)
        report['D']['outside_file'] = {
            'pid': payload.get('pid'), 'schema': payload.get('schema'),
            'visible': payload.get('visible'),
            'geometry': payload.get('geometry'),
            'writtenAt': payload.get('writtenAt'),
        }
    except Exception as exc:  # noqa: BLE001
        report['D']['outside_file'] = f'UNREADABLE {exc!r}'
    return run


ARMS = [('A', arm_a), ('B', arm_b), ('C', arm_c), ('D', arm_d)]


def main():
    report = {'shell': SHELL, 'visibility_file': VISIBILITY, 'stamp': STAMP,
              'arms': {}}
    for name, fn in ARMS:
        try:
            run = fn(report)
            report['arms'][name] = 'ok'
            if isinstance(run, dict):
                report.setdefault(name, {})['wall_s'] = run.get('wall_s')
                report[name]['cost'] = run.get('cost')
        except Exception as exc:  # noqa: BLE001 -- one arm must not lose the rest
            import traceback
            report['arms'][name] = f'CRASH {exc!r}'
            report[f'{name}_traceback'] = traceback.format_exc()

    a, b, c, d = (report.get('A', {}), report.get('B', {}),
                  report.get('C', {}), report.get('D', {}))
    checks = [
        ('A the Alt+C path applies the STRIP surface', a.get('applied_strip')),
        # THE HEIGHT IS THE STYLESHEET'S (`panel.css:52` `--strip-height: 150px`),
        # read at runtime — so the window must be 150 tall and the log must name
        # the CSS as the source. A 148 here would mean the number got typed twice.
        ('A the strip height came FROM THE STYLESHEET (source=css css_value=150)',
         bool([ln for ln in a.get('strip_height', [])
               if 'source=css' in ln and 'css_value=150' in ln])),
        ('A the strip window is 1040x150@(440,834)',
         bool([ln for ln in a.get('window_geometry', [])
               if 'window=1040x150@(440,834)' in ln])),
        ('A SetWindowPos SUCCEEDED (ok=true, last_error=0)',
         bool([ln for ln in a.get('window_geometry', [])
               if 'ok=true' in ln and 'last_error=0' in ln])),
        ('A the window rect really is the strip rect',
         bool([ln for ln in a.get('rect_after_show', [])
               if 'rect=(440,834,1480,984)' in ln])),
        ('A the document wears the strip layout',
         bool([ln for ln in a.get('surface', [])
               if 'document_surface="strip"' in ln])),
        ('A the client area was forced to the strip size',
         bool([ln for ln in a.get('client_area', []) if '1040x150' in ln])),
        ('A no page error', not a.get('page_errors')),
        ('A the bridge carries the new members (methods=17)',
         bool([ln for ln in a.get('preload', []) if 'methods=17' in ln])),
        ('B 0 visible samples at a 100 ms census', b.get('no_visible_sample')),
        ('B nothing was ever shown', not b.get('panel_shown_lines')),
        ('B the shell reached RECEIVER_READY', bool(b.get('receiver_ready'))),
        ('C the tray menu carries Edit caption position', c.get('has_edit_item')),
        ('C the tray menu still carries Open panel and Quit',
         bool(c.get('has_open_item')) and bool(c.get('has_quit_item'))),
        ('D edit mode entered through the tray id', bool(d.get('enter'))),
        ('D the drag sample was applied and persisted',
         bool([ln for ln in d.get('saved', [])
               if 'window=1040x150@(700,400)' in ln])),
        ('D edit mode left and the ex-styles restored', bool(d.get('leave'))),
        ('D an outside click while editing does NOT close the band',
         bool([ln for ln in d.get('outside_while_editing', [])
               if 'closed=false' in ln and 'visible=true' in ln
               and 'decision=edit-mode' in ln])),
        ('D the geometry key is in panel-visibility.json, read back by the shell',
         isinstance(d.get('file_geometry'), dict)),
        ('D no style failure', not d.get('style_failures')),
        ('D no page error', not d.get('page_errors')),
    ]
    report['checks'] = [{'what': what, 'ok': bool(ok)} for what, ok in checks]
    failed = [what for what, ok in checks if not ok]
    report['verdict'] = 'GREEN' if not failed else 'RED'
    report['failed'] = failed
    # THE LANE'S OWN BILL: this process plus every shell it spawned, CPU seconds
    # and peak working set, measured with `GetProcessTimes` on handles already
    # held — no WMI, no process walk.
    report['probe_cost'] = process_cost(kernel32.GetCurrentProcess())
    report['shell_cpu_total_s'] = round(sum(
        (report.get(a, {}).get('cost') or {}).get('cpu_s') or 0.0
        for a in ('A', 'B', 'C', 'D')), 3)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return 0 if not failed else 3


if __name__ == '__main__':
    # pythonw.exe HAS NO STDOUT: an uncaught exception here would leave a
    # non-existent report and no traceback anywhere, which is exactly the
    # "the run looked healthy" failure this repo keeps re-learning. Everything
    # goes into the report file, traceback included.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback
        crash = {'verdict': 'CRASH', 'traceback': traceback.format_exc()}
        with open(REPORT, 'w', encoding='utf-8') as fh:
            json.dump(crash, fh, indent=2)
        sys.exit(3)
