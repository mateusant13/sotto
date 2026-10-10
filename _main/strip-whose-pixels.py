"""WHOSE pixels are we looking at? `WindowFromPoint` decides it.

The timeline showed white both before and after the WebView2 child becomes
visible, so "the child paints white" was one conclusion too fast. The other
possibility is that Sotto is NOT at that point at all — the strip sits at
y=870..1020 on a 1920x1032 work area, i.e. the bottom strip of the screen where
the taskbar lives — and we were sampling the TASKBAR, calling it "the panel is
white". The earlier "DARK" runs would then be the runs where the window really
was on top.

A luminance count can never tell those two apart. `WindowFromPoint` can: it names
the window that actually owns the pixel. So each sample takes (a) the window at
the strip's centre, (b) whether that window belongs to the Sotto process, (c)
whether the form is visible, (d) the luminance of the strip's rect, and (e) a
REFERENCE rect at (0,0) that is always plain desktop, so a "white" reading can
be checked against what the desktop looks like right now.

No images are written.
"""

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SHELL = r"H:\sotto\app\webview\sotto_webview.py"
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\whose.log"
VK_MENU, VK_C = 0x12, 0x43
SRC = 0x00CC0020
HWND, BOOL, LPARAM = wintypes.HWND, wintypes.BOOL, wintypes.LPARAM


class R(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class BIH(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD), ('biWidth', ctypes.c_long),
                ('biHeight', ctypes.c_long), ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', ctypes.c_long),
                ('biYPelsPerMeter', ctypes.c_long),
                ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]


def _text(h):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    return b.value or '<unnamed>'


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value or '<noclass>'


def _rect(h):
    r = R()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def pid_of(h):
    wp = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
    return wp.value


def owns_pid(h, pid):
    """Is h, or any of its ancestors, a window of pid?"""
    cur = h
    for _ in range(8):
        if not cur:
            return False
        if pid_of(cur) == pid:
            return True
        cur = user32.GetParent(cur)
    return False


def luminance_mix(x, y, w, h):
    if w <= 0 or h <= 0:
        return 0, 0, 1
    hdc = user32.GetWindowDC(None)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, w, h, hdc, x, y, SRC)
    i = BIH()
    i.biSize = ctypes.sizeof(BIH)
    i.biWidth, i.biHeight = w, -h
    i.biPlanes, i.biBitCount, i.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(i), 0)
    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(None, hdc)
    px = buf.raw
    light = dark = 0
    for n in range(0, len(px), 4):
        L = (px[n + 2] * 299 + px[n + 1] * 587 + px[n] * 114) // 1000
        if L > 200:
            light += 1
        elif L < 60:
            dark += 1
    return light, dark, max(light + dark, 1)


def form_state(pid):
    out = {'form': None, 'n': 0, 'vis': 0}

    def _kid(k, _lp):
        b = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(k, b, 256)
        if b.value.startswith('Chrome_WidgetWin'):
            out['n'] += 1
            if user32.IsWindowVisible(k):
                out['vis'] += 1
        return True

    def _top(h, _lp):
        if pid_of(h) != pid or _text(h) != 'Sotto':
            return True
        out['form'] = (int(h), _rect(h))
        user32.EnumChildWindows(h, ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(_kid), 0)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(_top), 0)
    return out


def kill_everything():
    subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or "
         "Name='python.exe'\" | Where-Object { $_.CommandLine -match "
         "'sotto_webview\\.py|sotto_worker\\.py' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
        capture_output=True, text=True, creationflags=0x08000000)
    for _ in range(40):
        rows = []
        def cb(h, _):
            if _text(h) == 'Sotto':
                rows.append(1)
            return True
        user32.EnumWindows(ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(cb), 0)
        if not rows:
            return True
        time.sleep(0.25)
    return False


def main():
    runs = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 2
    secs = float(sys.argv[sys.argv.index('--secs') + 1]) if '--secs' in sys.argv else 10
    user32.SetProcessDPIAware()
    for n in range(1, runs + 1):
        print("=== RUN %d ===" % n)
        if not kill_everything():
            print("  leftover windows: contaminated, not evidence")
            continue
        if os.path.exists(LOG):
            os.remove(LOG)
        p = subprocess.Popen([sys.executable, SHELL, "--with-worker",
                              "--exit-after", "70", "--log", LOG],
                             creationflags=0x08000000 | 0x00000008)
        t0 = time.time()
        while time.time() - t0 < 40:
            try:
                if "PRELOAD_ACTIVE" in open(LOG, encoding="utf-8",
                                            errors="replace").read():
                    break
            except OSError:
                pass
            time.sleep(0.5)
        time.sleep(secs)

        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_C, 0, 2, 0)
        user32.keybd_event(VK_MENU, 0, 2, 0)

        t0 = time.time()
        first = None
        while time.time() - t0 < 8 and first is None:
            st = form_state(p.pid)
            if st['form'] and st['form'][1][2] == 1040:
                first = st['form']
            time.sleep(0.02)
        if first is None:
            print("  no strip mapped in 8 s")
            p.kill()
            continue

        print("  t(ms) formVis child  LIGHT%  at-point (pid owns?)        ref(0,0) LIGHT%")
        stats = {'sotto_white': 0, 'sotto_dark': 0,
                 'other_white': 0, 'other_dark': 0}
        for k in range(22):
            st = form_state(p.pid)
            form = st['form'] or first
            fh, (x, y, w, h) = form
            lw = user32.IsWindowVisible(wintypes.HWND(fh))

            cx, cy = x + w // 2, y + h // 2
            pt = POINT(cx, cy)
            at = user32.WindowFromPoint(pt)
            at_pid = pid_of(at) if at else 0
            mine = owns_pid(at, p.pid)
            at_desc = "%s/%s" % (_cls(at), _text(at))
            if len(at_desc) > 26:
                at_desc = at_desc[:26]

            light, dark, tot = luminance_mix(x, y, w, h)
            rl, rd, rt = luminance_mix(0, 0, 200, 120)
            verdict = 'WHITE' if light / tot > 0.60 else 'dark'

            if mine:
                key = 'sotto_white' if verdict == 'WHITE' else 'sotto_dark'
            else:
                key = 'other_white' if verdict == 'WHITE' else 'other_dark'
            stats[key] += 1

            print("  %5d %-7s %d/%d    %5.1f   %-27s %-5s %5.1f"
                  % (int((time.time() - t0) * 1000), lw, st['vis'],
                     st['n'] - st['vis'], 100.0 * light / tot, at_desc,
                     'SOTTO' if mine else 'no', 100.0 * rl / rt))
            time.sleep(0.12)
        p.kill()
        print("  SUMMARY sotto-white=%d sotto-dark=%d  not-sotto-white=%d "
              "not-sotto-dark=%d"
              % (stats['sotto_white'], stats['sotto_dark'],
                 stats['other_white'], stats['other_dark']))
        if stats['sotto_white'] and not stats['sotto_dark']:
            print("  RUN VERDICT: Sotto's own window composites WHITE -> the "
                  "defect is in the panel/WebView2, not in our sampling")
        elif stats['other_white'] and not stats['sotto_white']:
            print("  RUN VERDICT: the white is NOT Sotto -- we were sampling "
                  "whatever is behind it (taskbar/desktop). Sotto was not "
                  "on top at those instants.")
        elif stats['sotto_dark'] and not stats['sotto_white']:
            print("  RUN VERDICT: Sotto composites DARK whenever it is the "
                  "window at that point -> no white defect in this run")
        else:
            print("  RUN VERDICT: mixed -- needs the per-row table above")


if __name__ == "__main__":
    main()
