#!/usr/bin/env python3
"""Audit probe — what the panel PAINTS, what a plain launch actually STARTS, and
whether the panel window can receive the mouse at all.

READ-ONLY with respect to the app's own files: it launches `app/webview/
sotto_webview.py` under `pythonw.exe` with `CREATE_NO_WINDOW`, drives it only
through its OWN flags, and writes its receipts under `_main/_audit-probe/`.
`--no-hotkey` is ALWAYS passed, so a probe run can never answer the owner's
Alt+C with its own panel.

THREE ARMS, each a real shell process (no variants, no copies of the shell):

  plain     `--show`, no `--with-worker`. What the documented double-click entry
            point (`app/webview/run.cmd`) actually gives the owner.
  worker    `--show --with-worker --worker _main/_audit-fake-worker.py`. A real
            shell, a real bridge, a fake worker that writes the REAL worker's
            two line shapes — so the panel is photographed POPULATED (committed
            line + provisional tail) with no model load and no audio device.
  hotreload the shipped hot-reload path (`app/webview/hot_reload.py` ->
            `reload_panel_assets`): the panel file is touched while the app runs,
            and the panel's own state dump (`_main/panel-state.json`) is read
            before and after. This arm runs HIDDEN: the question is the DOM, not
            the pixels.

Usage:
    pythonw.exe _main/_audit-probe-20261007.py [--out DIR]

Prints one JSON object plus a human summary. Kills every process it started
before returning.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
import ctypes.wintypes as wt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
FAKE_WORKER = os.path.join(HERE, '_audit-fake-worker.py')
PANEL_STATE = os.path.join(HERE, 'panel-state.json')
OUT = os.path.join(HERE, '_audit-probe')
PYTHONW = os.path.join(os.environ.get('ProgramFiles', r'C:\Program Files'),
                       'Python311', 'pythonw.exe')
if not os.path.exists(PYTHONW):
    PYTHONW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')

CREATE_NO_WINDOW = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
        ('biPlanes', wt.WORD), ('biBitCount', wt.WORD),
        ('biCompression', wt.DWORD), ('biSizeImage', wt.DWORD),
        ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG),
        ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD),
    ]


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- window tools
def panel_windows():
    """Every top-level window titled `Sotto` (visible or not), outermost first."""
    found = []

    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value == 'Sotto':
                found.append(int(hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def ex_style(hwnd):
    return int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE)) & 0xFFFFFFFF


def style_flags(value):
    return {
        'WS_EX_TRANSPARENT': bool(value & WS_EX_TRANSPARENT),
        'WS_EX_LAYERED': bool(value & WS_EX_LAYERED),
        'WS_EX_NOACTIVATE': bool(value & WS_EX_NOACTIVATE),
        'WS_EX_TOOLWINDOW': bool(value & WS_EX_TOOLWINDOW),
    }


def window_rect(hwnd):
    r = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return {'x': r.left, 'y': r.top, 'w': r.right - r.left, 'h': r.bottom - r.top}


def what_is_at(x, y):
    """The window the OS would deliver a click at (x, y) to."""
    pt = wt.POINT(x, y)
    hwnd = int(user32.WindowFromPoint(pt))
    return hwnd


def capture_png(hwnd, path):
    """PrintWindow(PW_RENDERFULLCONTENT) -> PNG. Works off the owner's desk."""
    try:
        from PIL import Image
    except ImportError:
        return None
    rect = window_rect(hwnd)
    w, h = int(rect['w']), int(rect['h'])
    if w <= 0 or h <= 0:
        return None
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    ok = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)
    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth = w
    bi.biHeight = -h          # top-down
    bi.biPlanes = 1
    bi.biBitCount = 32
    bi.biCompression = 0      # BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer('RGBA', (w, h), buf, 'raw', 'BGRA', 0, 1)
    img.save(path)
    # How much of it is NOT the flat background: proof the capture is a panel and
    # not a uniform rectangle (the trap the paint probe names).
    colours = img.convert('RGB').getcolors(maxcolors=1 << 24) or []
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return {'path': path, 'printed': bool(ok), 'distinct_colours': len(colours)}


# --------------------------------------------------------------------- the run
def launch(extra, log_path):
    if os.path.exists(log_path):
        os.remove(log_path)
    argv = [PYTHONW, SHELL, '--no-hotkey', '--log', log_path] + extra
    # stdout/stderr are CAPTURED, not discarded: pythonw has no console, so this
    # is the only place a pywebview/WebView2 diagnostic can land.
    out = open(log_path + '.stdout', 'wb')
    err = open(log_path + '.stderr', 'wb')
    child = subprocess.Popen(argv, cwd=ROOT, creationflags=CREATE_NO_WINDOW,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=err)
    child._audit_handles = (out, err)
    return child


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read().splitlines()
    except OSError:
        return []


def wait_for(log_path, needle, timeout=25.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(needle in line for line in read_log(log_path)):
            return True
        time.sleep(0.2)
    return False


def kill(child):
    if child is None:
        return
    if child.poll() is None:
        subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                       creationflags=CREATE_NO_WINDOW,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        child.wait(timeout=10)
    except Exception:
        pass
    for handle in getattr(child, '_audit_handles', ()):
        try:
            handle.close()
        except Exception:
            pass


def grep(lines, pattern):
    rx = re.compile(pattern)
    return [line for line in lines if rx.search(line)]


def arm_plain(out_dir):
    log_path = os.path.join(out_dir, 'plain.log')
    child = launch(['--show', '--no-hot-reload', '--exit-after', '9'], log_path)
    result = {'arm': 'plain'}
    try:
        wait_for(log_path, 'PANEL_VISIBILITY_ON_SCREEN', 20)
        time.sleep(2.0)
        lines = read_log(log_path)
        hwnds = panel_windows()
        result['windowCount'] = len(hwnds)
        if hwnds:
            hwnd = hwnds[0]
            result['rect'] = window_rect(hwnd)
            result['exStyle'] = style_flags(ex_style(hwnd))
            result['visible'] = bool(user32.IsWindowVisible(hwnd))
            pt = result['rect']
            cx = pt['x'] + pt['w'] // 3
            cy = pt['y'] + pt['h'] // 3
            result['hotkeyTestedAt'] = [cx, cy]
            result['windowUnderPoint'] = what_is_at(cx, cy)
            result['panelIsTheWindowUnderPoint'] = (
                result['windowUnderPoint'] == hwnd)
            result['png'] = capture_png(
                hwnd, os.path.join(out_dir, 'plain.png'))
        result['workerStarted'] = bool(grep(lines, r'BRIDGE_SPAWNED|WORKER_AUTOSTART'))
        result['placeholder'] = [l for l in grep(lines, r'RECEIVER_READY')]
        result['statusLines'] = grep(lines, r'STATUS_APPLIED|BRIDGE_STATUS')
        result['panelShown'] = grep(lines, r'PANEL_SHOWN')
    finally:
        kill(child)
    result['log'] = log_path
    return result


def arm_worker(out_dir):
    out_dir = os.path.join(out_dir, 'fakestate')
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, 'worker.log')
    child = launch(['--show', '--no-hot-reload', '--with-worker',
                    '--worker', FAKE_WORKER, '--exit-after', '14'], log_path)
    result = {'arm': 'worker'}
    try:
        wait_for(log_path, 'RECEIVER_READY', 25)
        # Wait for the fake worker's `final` line + the provisional tail to land.
        deadline = time.time() + 12
        while time.time() < deadline:
            if len(grep(read_log(log_path), r'CAPTION_APPLIED')) >= 2:
                break
            time.sleep(0.25)
        time.sleep(1.0)
        lines = read_log(log_path)
        hwnds = panel_windows()
        if hwnds:
            result['png'] = capture_png(
                hwnds[0], os.path.join(out_dir, 'populated.png'))
        result['captionsApplied'] = grep(lines, r'CAPTION_APPLIED')
        result['historyAppend'] = grep(lines, r'HISTORY_APPEND')
        result['historyFailed'] = grep(lines, r'HISTORY_APPEND_FAILED')
        result['placeholderApplied'] = grep(lines, r'PLACEHOLDER_APPLIED')
        result['workerSpawned'] = grep(lines, r'BRIDGE_SPAWNED')
        result['statuses'] = grep(lines, r'BRIDGE_STATUS')
        if os.path.exists(PANEL_STATE):
            with open(PANEL_STATE, encoding='utf-8') as fh:
                result['panelState'] = json.load(fh)
    finally:
        kill(child)
    result['log'] = log_path
    return result


def arm_hotreload(out_dir):
    out_dir = os.path.join(out_dir, 'hotreload')
    os.makedirs(out_dir, exist_ok=True)
    log_path = os.path.join(out_dir, 'hotreload.log')
    panel_css = os.path.join(ROOT, 'app', 'panel', 'panel.css')
    before_stat = os.stat(panel_css)
    # HIDDEN arm: no --show. The question is the DOM the shell holds, which the
    # panel-state dump reads over the same exec_js the app already uses.
    # Hot reload is ON (no `--no-hot-reload`): this arm measures the shipped path.
    child = launch(['--exit-after', '24'], log_path)
    result = {'arm': 'hotreload'}
    try:
        wait_for(log_path, 'RECEIVER_READY', 25)
        time.sleep(1.0)
        if os.path.exists(PANEL_STATE):
            with open(PANEL_STATE, encoding='utf-8') as fh:
                state = json.load(fh)
            result['beforeUrl'] = (state.get('panel') or {}).get('url')
            result['beforeLive'] = ((state.get('panel') or {}).get('live')
                                    or {}).get('count')
        # Touch the ASSET, exactly as an edit would: content unchanged, mtime
        # bumped, so the watcher fires and nothing in the repo changes.
        os.utime(panel_css, (before_stat.st_atime, time.time()))
        fired = wait_for(log_path, 'HOT_RELOAD_PANEL_DONE', 15)
        result['reloadFired'] = fired
        time.sleep(5.0)
        if os.path.exists(PANEL_STATE):
            with open(PANEL_STATE, encoding='utf-8') as fh:
                state = json.load(fh)
            result['afterUrl'] = (state.get('panel') or {}).get('url')
            result['afterLive'] = ((state.get('panel') or {}).get('live')
                                   or {}).get('count')
            result['afterNamedState'] = state.get('namedState')
            result['afterStatus'] = ((state.get('panel') or {}).get('status')
                                     or {}).get('text')
        lines = read_log(log_path)
        result['hotReloadLines'] = grep(lines, r'HOT_RELOAD')
        result['loadErrors'] = grep(lines, r'BRIDGE_GATE|exec_js failed')
        result['receiverReadyCount'] = len(grep(lines, r'RECEIVER_READY'))
    finally:
        kill(child)
        os.utime(panel_css, (before_stat.st_atime, before_stat.st_mtime))
    result['log'] = log_path
    return result


def main():
    out_dir = OUT
    argv = sys.argv[1:]
    if '--out' in argv:
        out_dir = argv[argv.index('--out') + 1]
    os.makedirs(out_dir, exist_ok=True)
    which = argv[0] if argv and argv[0].startswith('--arm=') else None
    only = which.split('=', 1)[1].split(',') if which else None

    arms = {'plain': arm_plain, 'worker': arm_worker, 'hotreload': arm_hotreload}
    results = {}
    for name, fn in arms.items():
        if only and name not in only:
            continue
        log(f'--- arm {name} ' + '-' * 50)
        try:
            results[name] = fn(out_dir)
        except Exception as exc:  # noqa: BLE001 -- the probe reports, never dies
            results[name] = {'arm': name, 'error': repr(exc)}
        log(json.dumps({k: v for k, v in results[name].items()
                        if k not in ('panelState',)}, ensure_ascii=False,
                       indent=2, default=str))
    summary = os.path.join(out_dir, 'summary.json')
    with open(summary, 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2, default=str)
    log(f'\nreceipt: {summary}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
