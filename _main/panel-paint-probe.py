"""Does the panel still PAINT? A pixel check, taken OFF the owner's desk.

WHY THIS EXISTS. The 2026-10-07 cure (`_gate_form_show`) refuses pywebview's
own `form.Show()` at full opacity, so the window is never MAPPED at startup.
Every cheaper check (RECEIVER_READY, PRELOAD_ACTIVE, `--dump-dom`, the panel
state writer) proves the page RUNS — none of them proves a single pixel is
composited. pywebview's own comment calls the Show-on-navigating "a hack to make
transparent window work / no idea why this works", so "the app still logs
RECEIVER_READY" is NOT evidence that the panel is not blank. This probes the
pixels through `PrintWindow(PW_RENDERFULLCONTENT)`, which renders the window's
own content into a bitmap whatever its position — so the copy can sit at
x=-10000 and nothing appears on the owner's screen.

ARMS (each a COPY of the live shell, x moved off the desk; both deleted at end):
  asked     the live shell + `--show`: the owner's own ask. Its window MUST be
            found AND its bitmap MUST be non-uniform, or the fix blanked the
            panel. This is the arm that can FAIL the cure.
  notasked  the live shell, nobody asked. The window must NOT be found among
            the mapped windows (negative control for this instrument: if this
            arm also reports PAINTED, the capture is not measuring an ask).

Usage: py -3 _main/panel-paint-probe.py [--secs 7]
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
VARIANT_DIR = os.path.dirname(SHELL)
LOG = os.path.join(HERE, 'panel-paint-probe.log')

CREATE_NO_WINDOW = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
MONITOR_DEFAULTTONULL = 0x00000000

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_lines) + '\n')
    print(msg, flush=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


def window_class(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(wintypes.HWND(hwnd), buf, 512)
    return buf.value


def find_panel_window(pid: int):
    """The shell's own top-level 'Sotto' form, IF it is mapped."""
    hits = []

    def cb(hwnd, _lp):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        if window_text(hwnd) != 'Sotto':
            return True
        r = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        hits.append({
            'hwnd': int(hwnd), 'class': window_class(hwnd),
            'on_monitor': bool(user32.MonitorFromWindow(
                wintypes.HWND(hwnd), MONITOR_DEFAULTTONULL)),
            'rect': (r.left, r.top, r.right, r.bottom),
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return hits


def capture(hwnd, w: int, h: int) -> dict:
    """PrintWindow into a DIB and summarise the pixels (distinct colours)."""
    hdc = user32.GetWindowDC(wintypes.HWND(hwnd))
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    ok = user32.PrintWindow(wintypes.HWND(hwnd), mem, PW_RENDERFULLCONTENT)
    info = BITMAPINFOHEADER()
    info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.biWidth = w
    info.biHeight = -h               # top-down
    info.biPlanes = 1
    info.biBitCount = 32
    info.biCompression = 0           # BI_RGB
    buf = ctypes.create_string_buffer(w * h * 4)
    got = gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(wintypes.HWND(hwnd), hdc)
    px = buf.raw[:w * h * 4]
    colours = set()
    for i in range(0, len(px) - 3, 4):
        colours.add(px[i:i + 3])
        if len(colours) > 64:
            break
    return {'printwindow_ok': bool(ok), 'getdibits_rows': got,
            'distinct_colours': len(colours),
            'px_sha256': hashlib.sha256(px).hexdigest()[:16],
            'bytes': len(px)}


GATE_REMOVED = (
    ('        self._gate_form_show(form)\n',
     '        pass  # paint-probe control: the 2026-10-07 gate removed\n'),
)


def build_variant(path: str, revert_gate: bool = False) -> str:
    with open(SHELL, encoding='utf-8') as f:
        src = f.read()
    out = src.replace(
        "        self.geometry = dock_right(self.display['workArea'])\n",
        "        self.geometry = dock_right(self.display['workArea'])\n"
        "        # OFF-SCREEN copy (panel-paint-probe.py)\n"
        "        self.geometry['x'] = -10000\n", 1)
    if out == src:
        raise SystemExit('variant: offscreen edit did not apply — refusing')
    if revert_gate:
        for old, new in GATE_REMOVED:
            if old not in out:
                raise SystemExit('variant: --revert-gate edit did not apply')
            out = out.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out)
    return hashlib.sha256(src.encode()).hexdigest()[:16]


def pythonw() -> str:
    exe = sys.executable or ''
    if exe.lower().endswith('pythonw.exe'):
        return exe
    cand = exe.replace('python.exe', 'pythonw.exe')
    return cand if os.path.exists(cand) else exe


def arm(tag: str, extra: list, secs: float, shell: str,
        wait_for_show: bool = False) -> dict:
    alog = os.path.join(HERE, f'_paint-{tag}.log')
    if os.path.exists(alog):
        os.remove(alog)
    args = [pythonw(), shell, '--log', alog, '--no-hotkey', '--no-hot-reload',
            '--exit-after', str(secs), *extra]
    outp = open(alog + '.stdout', 'wb')
    proc = subprocess.Popen(args, stdout=outp, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            cwd=os.path.dirname(shell),
                            creationflags=CREATE_NO_WINDOW)
    pid = proc.pid
    log(f'=== ARM {tag} extra={extra} pid={pid} secs={secs} '
        f'wait_for_show={wait_for_show} ===')
    shot = None
    t0 = time.time()

    def _log_text():
        try:
            with open(alog, encoding='utf-8', errors='replace') as f:
                return f.read()
        except OSError:
            return ''

    def _grab():
        hits = find_panel_window(pid)
        if not hits:
            return None
        h = hits[0]
        x0, y0, x1, y1 = h['rect']
        w, hh = max(1, x1 - x0), max(1, y1 - y0)
        s = dict(h)
        s.update(capture(h['hwnd'], w, hh))
        s['t_s'] = round(time.time() - t0, 2)
        return s

    if wait_for_show:
        # DO NOT capture the first mapped window. pywebview's `hidden=True`
        # dance maps the form for microseconds with `Opacity=0` BEFORE anything
        # is painted — MEASURED: a capture at t=0.95 s returned
        # `distinct_colours=1` (a blank form) for a panel that then loaded and
        # painted normally. So wait for the shell's OWN `PANEL_SHOWN` line and
        # let the page settle; only then is a capture a statement about paint.
        while time.time() - t0 < secs:
            time.sleep(0.3)
            if 'PANEL_SHOWN' in _log_text():
                break
        time.sleep(2.0)
        shot = _grab()
    else:
        while time.time() - t0 < secs:
            time.sleep(0.3)
            if _grab() is not None:
                shot = _grab()
                break

    try:
        proc.wait(timeout=secs + 45)
    except subprocess.TimeoutExpired:
        proc.kill()
    outp.close()
    tail = []
    if os.path.exists(alog):
        for ln in open(alog, encoding='utf-8', errors='replace'):
            if any(k in ln for k in ('RECEIVER_READY', 'PRELOAD_ACTIVE',
                                     'PANEL_VISIBILITY_ON_SCREEN', 'PANEL_SHOWN',
                                     'PANEL_SHOW_REFUSED', 'PANEL_SHOW_GATE')):
                tail.append(ln.strip())
    if shot is None:
        log(f'ARM {tag}: NO mapped Sotto window found in {secs} s — nothing '
            'was captured')
    else:
        log(f'ARM {tag}: hwnd={shot["hwnd"]} class={shot["class"]} '
            f'on_monitor={shot["on_monitor"]} rect={shot["rect"]} '
            f'printwindow_ok={shot["printwindow_ok"]} '
            f'getdibits_rows={shot["getdibits_rows"]} '
            f'distinct_colours={shot["distinct_colours"]} (capped at 65) '
            f'bytes={shot["bytes"]} px_sha256={shot["px_sha256"]} '
            f't_s={shot["t_s"]}')
    for ln in tail:
        log(f'  log: {ln}')
    verdict = 'NO-WINDOW'
    if shot is not None:
        verdict = 'PAINTED' if shot['distinct_colours'] > 1 else 'UNIFORM'
    log(f'ARM-VERDICT {tag}: {verdict}')
    return {'tag': tag, 'shot': shot, 'verdict': verdict}


def main() -> int:
    a = sys.argv[1:]
    secs = 7.0
    if '--secs' in a:
        secs = float(a[a.index('--secs') + 1])
    revert = '--revert-gate' in a
    suffix = '-control' if revert else ''
    log('PAINT panel-paint-probe start='
        f'{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} secs={secs} '
        f'revert_gate={revert}')
    p = os.path.join(VARIANT_DIR, '_paint-offscreen-sotto_webview.py')
    sha = build_variant(p, revert_gate=revert)
    log(f'VARIANT sha256_live={sha} path={os.path.basename(p)} '
        f'revert_gate={revert}')
    try:
        asked = arm('asked' + suffix, ['--show'], secs, p, wait_for_show=True)
        notasked = arm('notasked' + suffix, [], secs, p)
    finally:
        if os.path.exists(p):
            os.remove(p)
            log(f'CLEANUP removed={os.path.basename(p)}')
    log('=== VERDICT ===')
    log(f'asked   : {asked["verdict"]}  (MUST be PAINTED)')
    log(f'notasked: {notasked["verdict"]}  (MUST be NO-WINDOW — the capture\'s '
        'own negative control)')
    ok = asked['verdict'] == 'PAINTED' and notasked['verdict'] == 'NO-WINDOW'
    log(f'PAINT-VERDICT {"PASS" if ok else "FAIL"}')
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
