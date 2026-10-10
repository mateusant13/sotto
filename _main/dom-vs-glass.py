"""The ONE measurement that separates "the page does not paint" from "the page
paints but does not composite".

Everything else so far answered a different question. `getComputedStyle` was
measured in `--show` runs; luminance was measured in `--with-worker` runs; the
WebView2's window title was measured separately again. A defect that lives in the
gap between the DOM and the glass needs both halves in the SAME run, at the SAME
instant.

So: launch with the shell's own `--dump-dom --dump-dom-wait`, press the real
Alt+C, and the moment `DOMDUMP` lands in the log, read BOTH the page's computed
`body` background AND the pixels at the strip's rect. No images are written.

    DOM says dark  + pixels dark   -> working; the earlier whites were another cause
    DOM says dark  + pixels white  -> COMPOSITING failure (the page paints, the
                                      window does not show it)
    DOM says clear + pixels white  -> CSS failure (the page is not painting)
"""

import ctypes
import io
import json
import os
import re
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
SHELL = r"H:\sotto\app\webview\sotto_webview.py"
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\both.log"
VK_MENU, VK_C = 0x12, 0x43
SRC = 0x00CC0020
HWND, BOOL, LPARAM = wintypes.HWND, wintypes.BOOL, wintypes.LPARAM


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
    wait = float(sys.argv[sys.argv.index('--wait') + 1]) \
        if '--wait' in sys.argv else 30
    user32.SetProcessDPIAware()
    if not kill_everything():
        print("leftover windows: contaminated")
        return 1
    if os.path.exists(LOG):
        os.remove(LOG)
    argv = [sys.executable, SHELL,
            "--dump-dom", "--dump-dom-wait", str(wait),
            "--exit-after", str(wait + 25), "--log", LOG]
    if '--no-worker' in sys.argv:
        # The strip auto-hides ~3 s after Alt+C, so the two halves of this
        # measurement must be taken while it is UP. The worker is not part of
        # the question and its ~15 s model load only makes the timing harder.
        argv.insert(2, "--no-worker")
    else:
        argv.insert(2, "--with-worker")
    p = subprocess.Popen(argv, creationflags=0x08000000 | 0x00000008)
    print("launched pid=%d  (dumps at t=%ss)" % (p.pid, wait))
    t0 = time.time()
    while time.time() - t0 < 40:
        try:
            if "PRELOAD_ACTIVE" in open(LOG, encoding="utf-8",
                                        errors="replace").read():
                break
        except OSError:
            pass
        time.sleep(0.5)
    # Align Alt+C to the dump: the strip auto-hides ~3 s after it opens, so the
    # keypress must land a couple of seconds BEFORE `--dump-dom-wait` expires.
    settle = max(0.0, wait - (time.time() - t0) - 4.0)
    if settle > 0:
        time.sleep(settle)
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)
    print("Alt+C sent; waiting for DOMDUMP at t=%ss" % wait)

    dom = None
    t0 = time.time()
    while time.time() - t0 < wait + 20 and dom is None:
        try:
            data = open(LOG, encoding="utf-8", errors="replace").read()
        except OSError:
            data = ""
        if "DOMDUMP " in data:
            line = [l for l in data.splitlines() if "DOMDUMP " in l][-1]
            dom = json.loads(line[line.index("DOMDUMP ") + 8:])
        time.sleep(0.4)
    if dom is None:
        print("no DOMDUMP; log tail:")
        try:
            for l in open(LOG, encoding="utf-8", errors="replace").read().splitlines()[-10:]:
                print("   " + l[:150])
        except OSError:
            pass
        p.kill()
        return 1

    form = None
    def cb(h, _lp):
        global form
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == p.pid and _text(h) == 'Sotto':
            form = (int(h), _rect(h))
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(cb), 0)

    els = dom.get('els') or {}
    body = els.get('body') or {}
    panel = els.get('#panel') or {}
    print("--- THE PAGE (computed) ---")
    print("  body.bgc   = %r" % body.get('bgc'))
    print("  body.bgi   = %r" % str(body.get('bgi'))[:70])
    print("  #panel.bgc = %r" % panel.get('bgc'))
    print("  #panel.bgi = %r" % str(panel.get('bgi'))[:70])
    print("  sheets     = %r  surface=%r skin=%r"
          % (dom.get('sheets'), dom.get('surface'), dom.get('skin')))
    print("--- THE GLASS (same instant) ---")
    if not form:
        print("  no Sotto window mapped right now")
    else:
        x, y, w, h = form[1]
        light, dark, tot = luminance_mix(x, y, w, h)
        print("  rect=%s  LIGHT=%.1f%%  DARK=%.1f%%"
              % (form[1], 100.0 * light / tot, 100.0 * dark / tot))

    bgc = str(body.get('bgc') or '')
    dark_css = bool(re.search(r'rgba?\(\s*1?\d?\d?\s*,', bgc)) and 'rgba(0, 0, 0, 0)' not in bgc
    print("--- VERDICT ---")
    if form and light / tot > 0.60 and dark_css:
        print("COMPOSITING FAILURE: the page reports a dark background and the "
              "window composites white. The DOM and the glass disagree.")
    elif form and light / tot > 0.60:
        print("CSS FAILURE: the page is not painting a background either "
              "(body.bgc=%r)." % bgc)
    else:
        print("The window composites a dark slab in this configuration.")
    p.kill()
    return 0


if __name__ == "__main__":
    main()
