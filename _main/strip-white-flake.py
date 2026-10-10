"""Is the strip's white INTERMITTENT, and does `ensure_webview_shown` fix it?

ARM A (windowed, SOTTO_WEBVIEW_WINDOW_TO_VISUAL=0) composited 100% DARK.
ARM B (the new default, also windowed) composited 100% LIGHT. Same flags, same
code -- so the earlier single run was not a stable measurement, and
`WEBVIEW_CHILD shown=2 already=3` (FIVE WebView2 children) says the process
table was contaminated by windows left over from the killed runs before it.

This runs N launches on a CLEAN slate: every Sotto window is enumerated and
reported BEFORE each launch, so a leftover is visible in the output rather than
silently poisoning the verdict. For each launch it presses Alt+C once, censors
the child tree, and counts the composited luminance of the strip's own rect.

Usage: py -3 _main/strip-white-flake.py [--runs 3] [--secs 10]
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
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\flake.log"
VK_MENU, VK_C = 0x12, 0x43
SRC = 0x00CC0020


class R(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


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
    return b.value


HWND = wintypes.HWND


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(h), b, 256)
    return b.value


def _rect(h):
    r = R()
    user32.GetWindowRect(wintypes.HWND(h), ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def all_sotto():
    """Every top-level 'Sotto' window on the box, whoever owns it."""
    out = []

    def cb(h, _lp):
        if _text(int(h)) == 'Sotto':
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
            out.append((pid.value, _rect(int(h)),
                        bool(user32.IsWindowVisible(wintypes.HWND(int(h))))))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND,
                                          wintypes.LPARAM)(cb), 0)
    return out


def kill_everything():
    """Kill every python holding a Sotto shell/worker, then wait for the windows
    to leave. A leftover window belongs to a process we no longer control, so
    measuring it would be measuring somebody else's launch."""
    killer = subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or "
         "Name='python.exe'\" | Where-Object { $_.CommandLine -match "
         "'sotto_webview\\.py|sotto_worker\\.py' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
        capture_output=True, text=True, creationflags=0x08000000)
    for _ in range(40):
        if not all_sotto():
            return True
        time.sleep(0.25)
    return not all_sotto()


def census(pid):
    rows = []

    def _kid(k, _lp):
        if _cls(int(k)).startswith('Chrome_WidgetWin'):
            rows.append(('webview', int(k), _rect(int(k)),
                         bool(user32.IsWindowVisible(wintypes.HWND(int(k))))))
        return True

    def _top(h, _lp):
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value != pid or _text(int(h)) != 'Sotto':
            return True
        rows.append(('form', int(h), _rect(int(h)),
                     bool(user32.IsWindowVisible(wintypes.HWND(int(h))))))
        user32.EnumChildWindows(
            wintypes.HWND(int(h)),
            ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)(_kid), 0)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND,
                                          wintypes.LPARAM)(_top), 0)
    return rows


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


def send_alt_c():
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)


def one_run(n, secs):
    print("=== RUN %d ===" % n)
    if not kill_everything():
        print("  LEFTOVER Sotto windows could not be cleared; this run is "
              "contaminated and its verdict is not evidence")
        return None
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
    send_alt_c()
    saw = None
    t0 = time.time()
    while time.time() - t0 < 8 and saw is None:
        rows = census(p.pid)
        if rows:
            saw = rows
        time.sleep(0.05)
    if saw is None:
        print("  no window mapped after Alt+C")
        p.kill()
        return None
    for _ in range(15):
        time.sleep(0.2)
        rows = census(p.pid)
        if rows:
            saw = rows
    forms = [x for x in saw if x[0] == 'form']
    webs = [x for x in saw if x[0] == 'webview']
    hidden = [w for w in webs if not w[3]]
    print("  form=%s  webview=%d visible=%d hidden=%d"
          % (forms[0][2] if forms else None, len(webs),
             len(webs) - len(hidden), len(hidden)))
    if not forms or not webs:
        p.kill()
        return None
    fx, fy, fw, fh = forms[0][2]
    light, dark, tot = luminance_mix(fx, fy, fw, fh)
    verdict = 'WHITE' if light / tot > 0.60 else 'DARK'
    print("  composited LIGHT=%.1f%% DARK=%.1f%% -> %s"
          % (100.0 * light / tot, 100.0 * dark / tot, verdict))
    p.kill()
    return verdict


def main():
    runs = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
    secs = float(sys.argv[sys.argv.index('--secs') + 1]) if '--secs' in sys.argv else 10
    user32.SetProcessDPIAware()
    results = []
    for n in range(1, runs + 1):
        v = one_run(n, secs)
        if v:
            results.append(v)
    print("=== SUMMARY ===")
    for i, v in enumerate(results, 1):
        print("  run %d: %s" % (i, v))
    if not results:
        print("VERDICT RED -- no clean measurement was possible")
        return 1
    white = results.count('WHITE')
    if white == len(results):
        print("VERDICT RED -- the strip composites WHITE in every clean run")
        return 1
    if white:
        print("VERDICT RED -- INTERMITTENT: %d of %d clean runs were white, so "
              "the strip is a race, not a constant" % (white, len(results)))
        return 1
    print("VERDICT GREEN -- %d of %d clean runs composited a dark strip"
          % (len(results), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
