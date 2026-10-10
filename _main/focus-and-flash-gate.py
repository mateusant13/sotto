"""Does the panel STEAL FOCUS, and does the STARTUP FLASH come back?

ChatGPT's review of the transparency fix raised two measurable risks rather than
opinions, and both are the kind of thing that quietly ruins an overlay:

  1. `Form.Show()` is what restores WebView2's composition, but `Show()` is not a
     documented transparency API and it can make a HIDDEN form visible. If it
     fires when the owner did not ask, the startup flash we cured in 2026-10-07
     comes back.
  2. Omitting `Activate()` removes the explicit focus request, but it does not
     prove the overlay never becomes the foreground window. ChatGPT's words:
     "Do not treat WS_EX_NOACTIVATE as verified merely because it appears in
     source code."

So this measures, with the real shell and the real Alt+C:
  * `GetForegroundWindow()` before and after the press -- whose window owns the
    keyboard; a caption overlay that takes it is a serious defect, not a nit;
  * whether any window of ours is mapped BEFORE the owner asks (the flash), by
    censusing every `Sotto` window from process start.

No images are written.
"""

import ctypes
import io
import os
import subprocess
import sys
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
SHELL = r"H:\sotto\app\webview\sotto_webview.py"
LOG = os.environ.get("TMPDIR", r"I:\cc-tmp") + r"\focus.log"
VK_MENU, VK_C = 0x12, 0x43
HWND, BOOL, LPARAM = wintypes.HWND, wintypes.BOOL, wintypes.LPARAM


def _text(h):
    b = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(h, b, 512)
    return b.value


def foreground():
    h = user32.GetForegroundWindow()
    if not h:
        return None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    return int(h), pid.value


def mapped(pid):
    """Every MAPPED top-level window of this pid, with its title."""
    rows = []

    def cb(h, _lp):
        if not user32.IsWindowVisible(h):
            return True
        wp = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(wp))
        if wp.value == pid:
            rows.append((int(h), _text(h)))
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)(cb), 0)
    return rows


def kill_everything():
    subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' or "
         "Name='python.exe'\" | Where-Object { $_.CommandLine -match "
         "'sotto_webview\\.py|sotto_worker\\.py' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
        capture_output=True, text=True, creationflags=0x08000000)
    for _ in range(40):
        if not mapped(0):
            return True
        time.sleep(0.25)
    return False


def main():
    user32.SetForegroundWindow.restype = wintypes.BOOL
    if not kill_everything():
        print("leftover windows: contaminated, not evidence")
        return 1
    if os.path.exists(LOG):
        os.remove(LOG)
    p = subprocess.Popen([sys.executable, SHELL, "--with-worker",
                          "--exit-after", "75", "--log", LOG],
                         creationflags=0x08000000 | 0x00000008)
    print("launched pid=%d (real shell, WORKER ON)" % p.pid)

    # THE FLASH ARM: watch from process start. Any of OUR windows mapped before
    # the owner asks is the startup flash returning.
    print("--- watching for a window mapped BEFORE anyone asked ---")
    flash = []
    t0 = time.time()
    ready = False
    while time.time() - t0 < 40:
        for h, title in mapped(p.pid):
            flash.append((round(time.time() - t0, 2), h, title))
        try:
            if "PRELOAD_ACTIVE" in open(LOG, encoding="utf-8",
                                        errors="replace").read():
                ready = True
                break
        except OSError:
            pass
        time.sleep(0.05)
    print("  PRELOAD_ACTIVE seen=%s after %.1fs" % (ready, time.time() - t0))
    if flash:
        print("  FLASH: %d mapped sample(s) before any ask:" % len(flash))
        for ts, h, title in flash[:6]:
            print("     t+%5.2fs hwnd=%s title=%r" % (ts, h, title[:40]))
    else:
        print("  no window mapped before the ask -> the startup flash is still "
              "cured")

    time.sleep(12)

    # THE FOCUS ARM
    before = foreground()
    print("--- FOCUS: GetForegroundWindow before Alt+C ---")
    print("  hwnd=%s pid=%s" % before)
    me = os.getpid()

    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_C, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_C, 0, 2, 0)
    user32.keybd_event(VK_MENU, 0, 2, 0)
    time.sleep(1.5)

    after = foreground()
    print("--- FOCUS: after Alt+C ---")
    print("  hwnd=%s pid=%s   (our shell pid=%d, this probe pid=%d)"
          % (after[0], after[1], p.pid, me))
    if after[0] is None:
        print("  VERDICT: no foreground window at all -- treat as UNMEASURED, "
              "not as 'no theft'")
    elif after[1] == p.pid:
        print("  VERDICT: FOCUS TAKEN -- the overlay is now the foreground "
              "window. WS_EX_NOACTIVATE did not hold on this path.")
    elif after == before:
        print("  VERDICT: focus unchanged -- the overlay did not take it")
    else:
        print("  VERDICT: focus moved to a DIFFERENT window (not ours, not the "
              "previous one) -- something else changed; re-measure")

    print("--- log ---")
    try:
        for l in open(LOG, encoding="utf-8", errors="replace").read().splitlines():
            if any(k in l for k in ('PANEL_SHOWN', 'PANEL_SHOW_REFUSED',
                                    'FORM_SHOW_TRANSPARENCY_HACK',
                                    'POINTER_INTERACTIVE', 'FOREGROUND')):
                print("   " + l[:150])
    except OSError:
        pass
    p.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
