"""A TIMELINE, not a snapshot: does the white coincide with the child hidden?

The last instrument sampled luminance once, three seconds after the window first
appeared — which is exactly when the strip auto-hides — so it could see the
owner's DESKTOP behind a hidden window and call it "white". Run 1 said WHITE
with `webview=2 visible=0`; runs 2 and 3 said DARK with the SAME
`visible=0`. A measurement that returns opposite answers from an identical
state is not measuring that state.

So this takes a timeline from the instant the window is first mapped, sampling
pairs of (child visibility, composited luminance) every ~120 ms for the whole
show. The question "is the strip white" is only answerable against "was the
WebView2 child visible at that instant", and those two have never been measured
in the same frame. No images are written.
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
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\timeline.log"
VK_MENU, VK_C = 0x12, 0x43
SRC = 0x00CC0020
HWND = wintypes.HWND
BOOL, LPARAM = wintypes.BOOL, wintypes.LPARAM


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


def _rect(h):
    r = R()
    user32.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def state(pid):
    """(form hwnd+rect, n_webview, n_visible) in ONE pass."""
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
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value != pid or _text(h) != 'Sotto':
            return True
        out['form'] = (int(h), _rect(h))
        user32.EnumChildWindows(h, ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(_kid), 0)
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(_top), 0)
    return out


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
    runs = int(sys.argv[sys.argv.index('--runs') + 1]) if '--runs' in sys.argv else 3
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

        # Sample the INSTANT the window appears, then keep sampling.
        t0 = time.time()
        first = None
        while time.time() - t0 < 8 and first is None:
            st = state(p.pid)
            if st['form'] and st['form'][1][2] == 1040:
                first = st['form']
            time.sleep(0.02)
        if first is None:
            print("  no strip mapped in 8 s")
            p.kill()
            continue

        print("  t(ms)  form      webview vis/hidden  LIGHT%   DARK%")
        white_when_child_shown = 0
        white_when_child_hidden = 0
        dark_when_child_shown = 0
        dark_when_child_hidden = 0
        for k in range(24):
            st = state(p.pid)
            form = st['form'] or first
            x, y, w, h = form[1]
            light, dark, tot = luminance_mix(x, y, w, h)
            shown = st['vis'] > 0
            verdict = 'WHITE' if light / tot > 0.60 else 'dark'
            if verdict == 'WHITE':
                if shown:
                    white_when_child_shown += 1
                else:
                    white_when_child_hidden += 1
            else:
                if shown:
                    dark_when_child_shown += 1
                else:
                    dark_when_child_hidden += 1
            print("  %5d  %4dx%-4d %2d/%2d          %5.1f   %5.1f  %s"
                  % (int((time.time() - t0) * 1000), w, h, st['vis'],
                     st['n'] - st['vis'], 100.0 * light / tot,
                     100.0 * dark / tot, verdict))
            time.sleep(0.12)
        p.kill()
        print("  correlations: WHITE(child shown)=%d WHITE(child hidden)=%d "
              "dark(child shown)=%d dark(child hidden)=%d"
              % (white_when_child_shown, white_when_child_hidden,
                 dark_when_child_shown, dark_when_child_hidden))
        if white_when_child_hidden and not white_when_child_shown:
            print("  RUN VERDICT: white happens ONLY when the WebView2 child "
                  "is hidden -> `ensure_webview_shown` is not doing its job")
        elif white_when_child_shown:
            print("  RUN VERDICT: white happens WITH the child shown -> the "
                  "child fix is not sufficient; the child itself paints white")
        else:
            print("  RUN VERDICT: no white in this run's timeline")


if __name__ == "__main__":
    main()
