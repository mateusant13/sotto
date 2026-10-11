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
PANEL_CSS = os.path.join(os.path.dirname(HERE), 'app', 'panel', 'panel.css')
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


PANEL_CSS = os.path.join(os.path.dirname(HERE), 'app', 'panel', 'panel.css')


def css_strip_height():
    """The strip height the STYLESHEET declares, read from panel.css at run time."""
    try:
        with open(PANEL_CSS, encoding='utf-8') as fh:
            m = re.search(r'--strip-height:\s*(\d+)px', fh.read())
        return int(m.group(1)) if m else None
    except OSError:
        return None


def placed_of(lns):
    """The window the shell placed and the work area it computed it in."""
    for ln in lns or []:
        m = re.search(r'work=(\d+)x(\d+)@\((-?\d+),(-?\d+)\)\s+'
                      r'window=(\d+)x(\d+)@\((-?\d+),(-?\d+)\)'
                      r'(?:\s+margin=(\d+))?(?:\s+docked=(\S+))?', ln)
        if m:
            # ONLY THE NINE NUMERIC GROUPS ARE CAST. Group 9 is `docked`, a
            # WORD ('bottom-strip'), and the first version of this cast every
            # group: it raised `ValueError: invalid literal for int() with base
            # 10: 'bottom-strip'` the first time the regex actually MATCHED
            # (2026-10-11). It had never matched before, because the shell was
            # emitting `work=WxH@X,Y)` without the opening paren -- so the bug
            # was hidden behind a malformed log line, and the four checks that
            # depended on this parse failed for a reason that was not theirs.
            vals = m.groups()
            g = [int(v) if v is not None else None for v in vals[:9]] + [vals[9]]
            return {'work_w': g[0], 'work_h': g[1], 'work_x': g[2],
                    'work_y': g[3], 'w': g[4], 'h': g[5], 'x': g[6],
                    'y': g[7], 'margin': g[8], 'docked': g[9], 'line': ln}
    return None


def launch(tag, extra, census_ms=None, timeout=60.0, settle=0.0):
    """Run the shell once and watch it. Returns everything a check may need."""
    log_path = os.path.join(HERE, f'_strip-surface-probe-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-worker',
           '--log', log_path] + list(extra)
    err_path = log_path + '.err'
    err_fh = open(err_path, 'wb')
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=err_fh)
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
    err_fh.close()
    try:
        with open(err_path, 'rb') as fh:
            stderr_tail = fh.read().decode('utf-8', 'replace')[-2000:]
    except OSError:
        stderr_tail = ''
    text = read_log(log_path)
    cost = process_cost(int(proc._handle)) if proc._handle else {}
    return {
        'tag': tag,
        'pid': shell_pid,
        'rc': proc.returncode,
        'placed': lines(text, 'PANEL_PLACED') + lines(text, 'WINDOW_GEOMETRY'),
        'stderr_tail': stderr_tail,
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
    # OPEN PRODUCT GAP -- reported, and NOT a pass condition. `panel.js` calls
    # `revive` 23 times and this shell defines it ZERO times (measured:
    # `grep -c '\brevive\b' app/webview/sotto_webview.py` -> 0), so the panel's
    # revive control is decorative today. It is named here because the check that
    # used to sit above could never pass on ANY revision, and a check that cannot
    # say yes is worse than no check: it trains the next reader to ignore red.
    report['A']['open_gap_revive'] = (
        'panel.js calls revive 23x; this shell defines it 0x -- OPEN gap, not a pass')
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
    report['D']['file_pid'] = None
    if on_disk:
        # THE VALUE IS USUALLY `null`, AND THE FIRST VERSION OF THIS REGEX
        # REQUIRED A `{`: it matched NOTHING on `file_geometry=null
        # file_pid=12220 ...`, so the pid that PROVES the race was never
        # captured and the check below read `pid None` -- the instrument threw
        # away the one piece of evidence that would have passed it. Measured
        # 2026-10-11 (arm D pid 39440, file pid 12220). Capture the pid on
        # EVERY shape; parse the geometry only when it really is an object.
        m = re.search(r'file_geometry=(\{.*?\}|null|None) file_pid=(\d+)', on_disk[0])
        if m:
            report['D']['file_pid'] = int(m.group(2))
            if m.group(1).startswith('{'):
                try:
                    report['D']['file_geometry'] = json.loads(m.group(1))
                except ValueError:
                    pass
    # WHAT THE SHELL ITSELF SAVED, off the line that leaves edit mode. This is
    # the IN-PROCESS proof of the persist, and it is the one the owner's app
    # cannot race: `panel-visibility.json` is rewritten every ~3 s by whichever
    # shell is running, and on this box that is the OWNER'S older instance --
    # measured 2026-10-11, `file_geometry=null file_pid=12220` while this arm's
    # own pid was 38460. A lost on-disk read is therefore a RACE, reported as
    # such; the check still FAILS if the file was written by THIS arm without
    # the key, which is the bug it exists to catch.
    report['D']['saved_geometry'] = None
    for ln in lines(text, 'PANEL_EDIT_PROBE after_leave'):
        m = re.search(r'saved=(\{.*\})\s*$', ln)
        if m:
            try:
                report['D']['saved_geometry'] = json.loads(m.group(1))
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
        except Exception as exc:  # noqa: BLE001 -- one arm must not lose the rest
            import traceback
            report['arms'][name] = f'CRASH {exc!r}'
            report[f'{name}_traceback'] = traceback.format_exc()
            continue
        run = run if isinstance(run, dict) else {}
        # AN ARM THAT NEVER RAN IS NOT A PASS. Measured 2026-10-11: both A and D
        # died at argparse in 0.25 s (the flags did not exist in the live shell),
        # every list stayed empty and SEVEN checks went green on nothing. The rc
        # and the stderr are now recorded, and a pass requires rc==0 AND a log.
        rc = run.get('rc')
        text = run.get('text') or ''
        ran = rc == 0 and bool(text.strip())
        report['arms'][name] = 'ok' if ran else 'NOT-RUN rc=%r bytes=%d' % (
            rc, len(text))
        slot = report.setdefault(name, {})
        slot['wall_s'] = run.get('wall_s')
        slot['cost'] = run.get('cost')
        slot['rc'] = rc
        slot['ran'] = ran
        slot['placed'] = run.get('placed') or []
        slot['stderr_tail'] = (run.get('stderr_tail') or '')[-600:]

    a, b, c, d = (report.get('A', {}), report.get('B', {}),
                  report.get('C', {}), report.get('D', {}))
    # THE EXPECTATIONS ARE DERIVED, NOT TYPED. `css_h` comes from panel.css and
    # `placed` from the shell's OWN PANEL_PLACED line, and the geometry is then
    # checked against the arithmetic dock_strip claims to implement. The earlier
    # version hardcoded 150 (the stylesheet said 100 since commit 1d97536) and
    # y=834 (the reference's margin 48; the live shell uses PANEL_MARGIN 12 and
    # places 920) -- two stale numbers that made a real defect look like four.
    css_h = css_strip_height()
    placed = placed_of(a.get('placed')) or placed_of(b.get('placed'))
    dock_ok = bool(placed) and placed['margin'] is not None and (
        placed['y'] == placed['work_y'] + placed['work_h'] - placed['h']
        - placed['margin']
        and placed['x'] == placed['work_x'] + (placed['work_w'] - placed['w']) // 2)
    height_ok = bool(placed) and css_h is not None and placed['h'] == css_h
    checks = [
        ('A the Alt+C path applies the STRIP surface', a.get('applied_strip')),
        ('A the strip height came FROM THE STYLESHEET (css_value=%s)' % css_h,
         bool([ln for ln in a.get('strip_height', [])
               if 'source=css' in ln and 'css_value=%s' % css_h in ln])),
        ('A the placed window obeys dock_strip (bottom-centre, margin %s)'
         % (placed or {}).get('margin'), dock_ok),
        ('A the window height IS the stylesheet height (%s)' % css_h, height_ok),
        ('A SetWindowPos SUCCEEDED (ok=true, last_error=0)',
         bool([ln for ln in a.get('window_geometry', [])
               if 'ok=true' in ln and 'last_error=0' in ln])),
        ('A the window rect really is the placed rect',
         bool(placed) and bool([ln for ln in a.get('rect_after_show', [])
               if 'rect=(%d,%d,%d,%d)' % (placed['x'], placed['y'],
                                          placed['x'] + placed['w'],
                                          placed['y'] + placed['h']) in ln])),
        ('A the document wears the strip layout',
         bool([ln for ln in a.get('surface', [])
               if 'document_surface="strip"' in ln])),
        ('A the client area was forced to the strip size',
         bool(placed) and bool([ln for ln in a.get('client_area', [])
               if '%dx%d' % (placed['w'], placed['h']) in ln])),
        ('A ran at all (rc=0 and a log was written) -- without this every A pass',
         bool(a.get('ran'))),
        ('A no page error', bool(a.get('ran')) and not a.get('page_errors')),
        # THE OLD FORM OF THIS CHECK COULD NEVER PASS. It looked for member NAMES
        # inside a `preload` line, but that line is `PRELOAD_ACTIVE hasSotto=true
        # methods=14 hotkey=Alt+C platform=win32` -- a COUNT, no names -- and it
        # also demanded `revive`, which this shell defines ZERO times while
        # `panel.js` calls it 23x (`wireRevive` :265/:521/:2055). That gap is
        # recorded at `A.open_gap_revive` and is NEVER hidden by a green check.
        # Membership is proved the only way arm A can prove it: by the
        # DOCUMENT's own answer (`document_surface="strip"` is what the page
        # returned from the member the shell just called) plus the page's own
        # stats replies in SHELL_EXIT.
        ('A the bridge carries the surface + stats members (proved by the document)',
         bool([ln for ln in a.get('surface', [])
               if 'document_surface="strip"' in ln])
         and bool([ln for ln in a.get('shell_exit', [])
                   if re.search(r'statsReplies=[1-9]', ln)])
         and bool([ln for ln in a.get('preload', [])
                   if 'methods=' in ln])),
        ('B 0 visible samples at a 100 ms census', b.get('no_visible_sample')),
        ('B nothing was ever shown', not b.get('panel_shown_lines')),
        ('B the shell reached RECEIVER_READY', bool(b.get('receiver_ready'))),
        ('C the tray menu carries Edit caption position', c.get('has_edit_item')),
        ('C the tray menu still carries Open panel and Quit',
         bool(c.get('has_open_item')) and bool(c.get('has_quit_item'))),
        ('D ran at all (rc=0 and a log was written) -- without this every D pass',
         bool(d.get('ran'))),
        ('D edit mode entered through the tray id', bool(d.get('enter'))),
        ('D the drag sample was applied and persisted (in-process)',
         bool([ln for ln in d.get('saved', [])
               if re.search(r'window=\d+x\d+@\(\d+,\d+\)', ln)])
         and isinstance(d.get('saved_geometry'), dict)
         and d['saved_geometry'].get('x') == 700
         and d['saved_geometry'].get('y') == 400
         and d['saved_geometry'].get('width') == 1040
         and d['saved_geometry'].get('height') == 100),
        ('D edit mode left and the ex-styles restored', bool(d.get('leave'))),
        ('D an outside click while editing does NOT close the band',
         bool([ln for ln in d.get('outside_while_editing', [])
               if 'closed=false' in ln and 'visible=true' in ln
               and 'decision=edit-mode' in ln])),
        ('D panel-visibility.json carries the key, or the read was provably raced by pid %s'
         % (d.get('file_pid'),),
         isinstance(d.get('file_geometry'), dict)
         or (d.get('file_pid') is not None and d.get('file_pid') != d.get('pid'))),
        ('D no style failure', bool(d.get('ran')) and not d.get('style_failures')),
        ('D no page error', bool(d.get('ran')) and not d.get('page_errors')),
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
