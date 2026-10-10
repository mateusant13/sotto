"""Does the WebView2 child HWND become VISIBLE when the shell maps the form?

THE DEFECT THIS GATES, MEASURED 2026-10-09 (child-window census during Alt+C):

    form     (WindowsForms10...)  vis=True   1040x150 @ (440,870)
      webview (Chrome_WidgetWin_0) vis=False  1040x150 @ (440,870)

The form was mapped and the browser window was NOT. What reached the screen was
the WinForms form's own background -- the .NET default, WHITE -- with the panel
painted correctly behind it. Every instrument that said the panel was fine was
right and beside the point: the DOM was parsed, the CSS was loaded, the computed
backgrounds were dark, `--show` painted 65 distinct colours. None of them can see
a hidden child HWND, because `EnumWindows` only lists TOP-LEVEL windows.

WHY IT HAPPENED. `_gate_form_show` refuses pywebview's `form.Show()` at
navigation start, to stop the startup flash the owner complained about. pywebview
shows the WebView2 child TOGETHER with the form, so refusing that call also left
the child hidden. The shell then maps the FORM with raw user32
(`SW_SHOWNOACTIVATE` in `show_panel`, `SW_SHOW+FOREGROUND` in
`show_strip`/`show_side`), which shows the form and nothing else. On `--show` the
gate ALLOWS the show (`show_requested=True`), so pywebview shows both -- which is
exactly why every "does it paint?" probe that used `--show` came back GREEN while
the owner's own Alt+C came back white. THE INSTRUMENT WAS THE BLIND SPOT.

THE FIX: `ensure_webview_shown()` shows the child with the form, and all three
show paths call it. This gate runs the REAL shell, presses the REAL Alt+C, and
censors the child window tree. No images are written: the compositing verdict is
a luminance COUNT over the strip's screen rect, nothing more.

Usage: py -3 _main/webview-child-gate.py [--secs 12]
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
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\wv-child.log"
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
    user32.GetWindowTextW(wintypes.HWND(h), b, 512)
    return b.value


def _cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(h), b, 256)
    return b.value


def _rect(h):
    r = R()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def census(pid):
    """Top-level 'Sotto' form plus every WebView2 HWND under it, two levels."""
    rows = []

    def _kid(k, _lp):
        if _cls(k).startswith('Chrome_WidgetWin'):
            rows.append(('webview', int(k), _rect(k),
                         bool(user32.IsWindowVisible(wintypes.HWND(k)))))
        return True

    def _top(h, _lp):
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value != pid or _text(h) != 'Sotto':
            return True
        rows.append(('form', int(h), _rect(h),
                     bool(user32.IsWindowVisible(wintypes.HWND(h)))))
        user32.EnumChildWindows(
            wintypes.HWND(h),
            ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                               wintypes.LPARAM)(_kid), 0)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                          wintypes.LPARAM)(_top), 0)
    return rows


def luminance_mix(x, y, w, h):
    """A COUNT of light/dark pixels over the screen rect. No image is written."""
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
    tot = max(light + dark, 1)
    return light, dark, tot


def send_alt_c():
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)


def main():
    secs = float(sys.argv[sys.argv.index('--secs') + 1]) if '--secs' in sys.argv else 12
    if os.path.exists(LOG):
        os.remove(LOG)
    user32.SetProcessDPIAware()
    p = subprocess.Popen([sys.executable, SHELL, "--with-worker",
                          "--exit-after", "70", "--log", LOG],
                         creationflags=0x08000000 | 0x00000008)
    print("launched pid=%d (real shell, WORKER ON, nobody asked)" % p.pid)
    t0 = time.time()
    while time.time() - t0 < 40:
        try:
            if "PRELOAD_ACTIVE" in open(LOG, encoding="utf-8",
                                        errors="replace").read():
                break
        except OSError:
            pass
        time.sleep(0.5)
    print("PRELOAD_ACTIVE seen; waiting %ss for the worker to settle" % secs)
    time.sleep(secs)
    print("--- BEFORE Alt+C (nobody asked) ---")
    before = census(p.pid)
    for tag, h, r, v in before:
        print("  %-8s vis=%-5s %sx%s@(%s,%s)" % (tag, v, r[2], r[3], r[0], r[1]))

    send_alt_c()
    print("--- Alt+C sent ---")
    saw = None
    t0 = time.time()
    while time.time() - t0 < 8 and saw is None:
        rows = census(p.pid)
        if rows:
            saw = rows
        time.sleep(0.05)
    if saw is None:
        print("VERDICT RED -- Alt+C mapped no window at all")
        p.kill()
        return 1
    # The show is short: poll a few times and keep the LAST state seen, so we
    # measure after `ensure_webview_shown` has had a chance to run.
    for _ in range(12):
        time.sleep(0.2)
        rows = census(p.pid)
        if rows:
            saw = rows
    for tag, h, r, v in saw:
        print("  %-8s vis=%-5s %sx%s@(%s,%s)" % (tag, v, r[2], r[3], r[0], r[1]))

    forms = [x for x in saw if x[0] == 'form']
    webs = [x for x in saw if x[0] == 'webview']
    if not forms:
        print("VERDICT RED -- no form")
        p.kill()
        return 1
    if not webs:
        print("VERDICT RED -- no WebView2 child HWND found; the census cannot "
              "see what the owner sees")
        p.kill()
        return 1
    hidden = [w for w in webs if not w[3]]
    if hidden:
        print("VERDICT RED -- %d of %d WebView2 child HWND(s) still HIDDEN: "
              "the form's white background is what composites"
              % (len(hidden), len(webs)))
        p.kill()
        return 1

    fx, fy, fw, fh = forms[0][2]
    light, dark, tot = luminance_mix(fx, fy, fw, fh)
    print("composited pixels: LIGHT=%.1f%%  DARK=%.1f%%"
          % (100.0 * light / tot, 100.0 * dark / tot))
    if light / tot > 0.60:
        print("VERDICT RED -- the strip composites WHITE even with the child shown")
        p.kill()
        return 1
    print("VERDICT GREEN -- WebView2 child is visible and the strip composites "
          "a dark slab")
    p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
