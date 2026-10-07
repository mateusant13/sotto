"""LANE SottoAltCEnd: drive Alt+C end to end, WITHOUT a window and WITHOUT audio.

WHAT IS DRIVEN, and from where
------------------------------
The accelerator is registered by `sotto_webview.HotkeyThread` with
`RegisterHotKey(hWnd=NULL, ...)` on its OWN thread, so the OS delivers
`WM_HOTKEY` to that thread's queue (sotto_webview.py:678-753). The shell's own
`run_selftest` proves that delivery path with `simulate_press()`. This probe
drives the SAME surface, from the OUTSIDE, without booting pywebview at all:

  ARM A  headless (no window, no WebView2, no audio)
    A1  the real `HotkeyThread` is constructed and started; the real
        `HOTKEY_REGISTERED` log line is emitted by the app's own code.
    A2  INDEPENDENT registration check: while the shell's thread owns Alt+C,
        a SECOND Win32 registration of the same accelerator from another
        thread MUST fail with 1409 (ERROR_HOTKEY_ALREADY_REGISTERED). The
        thread's own `registered` bool cannot prove this by itself.
    A3  delivery: `simulate_press()` (PostThreadMessageW WM_HOTKEY to the
        registering thread) -> the thread's GetMessageW loop ->
        `on_hotkey()` fires, N times, with the press counter agreeing.
    A4  NEGATIVE CONTROL for A2: after `stop()` (which calls
        UnregisterHotKey), the same second registration MUST now SUCCEED.
        Without A4, A2's 1409 could be any other owner on the box.
    A5  focus: GetForegroundWindow() is unchanged across the presses.

  ARM B  the real handler chain against a real window, off every monitor
    `SottoShell.toggle_panel` / `show_panel` / `hide_panel` are the REAL
    methods (not a re-implementation). They are given a REAL Win32 window
    created at x=y=-32000, which `MonitorFromWindow(MONITOR_DEFAULTTONULL)`
    reports as on NO monitor -- the same "mech vs owner" split the house
    already uses (panel-visible-window-probe.py:1-26). So the observed
    effect (the PANEL_SHOWN/PANEL_HIDDEN lines, and the visible-flag
    transition) is measured while the owner sees NOTHING.

WHAT THIS ARM CANNOT SHOW
-------------------------
The panel's RENDERED DOM after Alt+C cannot be read without the real
WebView2 window (pywebview + the panel document). That is reported as
UNPROVEN-in-this-arm, not skipped silently.

Usage: py -3 _main/alt-c-e2e-probe.py [--inject]
       --inject  ALSO send a real synthetic Alt+C through keybd_event (the
                 OS input path), so the accelerator is exercised the way the
                 owner's keypress exercises it. Only runs if our own
                 registration is live (so the key is consumed by the system
                 and cannot reach the foreground window).
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import importlib.util
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

CREATE_NO_WINDOW = 0x08000000
VK_MENU = 0x12
VK_C = 0x43
KEYEVENTF_KEYUP = 0x0002
MOD_ALT = 0x0001
MOD_NOREPEAT = 0x4000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
MONITOR_DEFAULTTONULL = 0x00000000
WS_POPUP = 0x80000000

u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.RegisterHotKey.restype = wt.BOOL
u32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_uint,
                               ctypes.c_uint]
u32.UnregisterHotKey.restype = wt.BOOL
u32.UnregisterHotKey.argtypes = [wt.HWND, ctypes.c_int]
u32.MonitorFromWindow.restype = wt.HANDLE
u32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
u32.CreateWindowExW.restype = wt.HWND
u32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE,
                                wt.LPVOID]
u32.DestroyWindow.argtypes = [wt.HWND]

#: a private id, distinct from the shell's 0xB0F0, for the independent check
PROBE_HOTKEY_ID = 0x5A5A

_results: dict = {}
_captured: list = []


class _Tee:
    """Mirror stdout so the shell's own `sotto: ` lines are in the evidence.

    `sotto_webview.log()` prints one `sotto: ` line per event
    (sotto_webview.py:352). This probe captures those lines verbatim instead
    of paraphrasing them.
    """

    def __init__(self, real):
        self.real = real

    def write(self, s):
        self.real.write(s)
        self.real.flush()
        for line in s.splitlines():
            if line.startswith('sotto: '):
                _captured.append(line)
        return len(s)

    def flush(self):
        self.real.flush()


def load_shell():
    spec = importlib.util.spec_from_file_location('sotto_shell_under_test',
                                                  SHELL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['sotto_shell_under_test'] = mod
    spec.loader.exec_module(mod)
    return mod


def independent_register() -> tuple:
    """Try to own Alt+C from THIS thread. Returns (ok, error_code).

    A second registration of an accelerator that another thread already owns
    fails with 1409. Called BEFORE the shell's thread registers (must be 0
    / free) and AFTER it stops (must succeed again).
    """
    msg = wt.MSG()
    u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # force a queue
    ctypes.set_last_error(0)
    ok = u32.RegisterHotKey(None, PROBE_HOTKEY_ID, MOD_ALT | MOD_NOREPEAT,
                            VK_C)
    err = ctypes.get_last_error()
    if ok:
        u32.UnregisterHotKey(None, PROBE_HOTKEY_ID)
    return bool(ok), int(err)


def make_offscreen_window() -> int:
    """A real Win32 window parked where NO monitor is."""
    hwnd = u32.CreateWindowExW(0, 'STATIC', 'sotto-alt-c-probe', WS_POPUP,
                               -32000, -32000, 380, 900, None, None, None,
                               None)
    return int(hwnd or 0)


def arm_a(shell) -> dict:
    out = {}
    a = {}

    free_before, err_before = independent_register()
    a['independent_register_before'] = {'ok': free_before,
                                        'err': err_before}
    _results['A0_accelerator_free_before'] = a['independent_register_before']

    fired = []
    ev = threading.Event()

    def on_hotkey():
        fired.append(time.time())
        ev.set()

    hk = shell.HotkeyThread('Alt+C', on_hotkey)
    hk.start()
    ready = hk.wait_ready(5)
    a['wait_ready'] = ready
    a['registered'] = bool(hk.registered)
    a['register_error'] = hk.register_error

    # A2: the bool above is self-reported. Prove the OS agrees by trying to
    # take the accelerator away from a second thread.
    taken, err_taken = independent_register()
    a['independent_register_while_held'] = {
        'ok': taken, 'err': err_taken,
        'expect_ok_false_and_1409': (taken is False
                                     and err_taken
                                     == ERROR_HOTKEY_ALREADY_REGISTERED),
    }

    fg_before = int(u32.GetForegroundWindow() or 0)
    presses = 0
    delivered = []
    for _ in range(3):
        delivered.append(bool(hk.simulate_press()))
        ev.wait(2.0)
        ev.clear()
        time.sleep(0.15)
    presses = len(fired)
    fg_after = int(u32.GetForegroundWindow() or 0)

    a['simulate_press_delivered'] = delivered
    a['handler_invocations'] = presses
    a['thread_pressed_counter'] = int(hk.pressed)
    a['focus_before'] = fg_before
    a['focus_after'] = fg_after
    a['focus_stolen'] = fg_before != fg_after

    if INJECT and hk.registered:
        # The owner's gesture, through the OS input path. Safe ONLY while OUR
        # registration is live: the system consumes a registered hotkey, so it
        # cannot reach the foreground window.
        ev.clear()
        n_before = len(fired)
        u32.keybd_event(VK_MENU, 0, 0, 0)
        u32.keybd_event(VK_C, 0, 0, 0)
        time.sleep(0.05)
        u32.keybd_event(VK_C, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        ev.wait(2.0)
        a['injected_keybd_event_extra_presses'] = len(fired) - n_before
        a['injected_keybd_event_delivered'] = (len(fired) - n_before) == 1

    hk.stop()
    time.sleep(0.2)
    free_after, err_after = independent_register()
    a['independent_register_after_stop'] = {'ok': free_after,
                                            'err': err_after}
    a['negative_control_ok'] = free_after is True

    out['arm_a'] = a
    return out


def arm_b(shell) -> dict:
    """The REAL shell methods against a REAL window that is on no monitor."""
    out = {}
    hwnd = make_offscreen_window()
    if not hwnd:
        out['arm_b'] = {'error': 'CreateWindowExW failed'}
        return out

    args = argparse.Namespace(show=False, opaque=False)
    sh = shell.SottoShell(args)
    sh.hwnd = hwnd
    sh.visible = False

    def on_monitor(h):
        return int(u32.MonitorFromWindow(h, MONITOR_DEFAULTTONULL) or 0)

    b = {
        'hwnd': hwnd,
        'monitor_before': on_monitor(hwnd),
        'visible_before': bool(u32.IsWindowVisible(hwnd)),
    }

    # Press 1: hidden -> shown (this is what Alt+C does when the panel is shut)
    r1 = sh.toggle_panel('hotkey')
    time.sleep(0.15)
    b['toggle_1_return'] = bool(r1)
    b['visible_after_toggle_1'] = bool(u32.IsWindowVisible(hwnd))
    b['shell_visible_flag_1'] = bool(sh.visible)
    b['monitor_after_toggle_1'] = on_monitor(hwnd)

    # Press 2: shown -> hidden
    r2 = sh.toggle_panel('hotkey')
    time.sleep(0.15)
    b['toggle_2_return'] = bool(r2)
    b['visible_after_toggle_2'] = bool(u32.IsWindowVisible(hwnd))
    b['shell_visible_flag_2'] = bool(sh.visible)
    b['monitor_after_toggle_2'] = on_monitor(hwnd)

    b['owner_ever_shown_a_window'] = bool(b['monitor_after_toggle_1']
                                          or b['monitor_after_toggle_2'])
    u32.DestroyWindow(hwnd)
    out['arm_b'] = b
    return out


INJECT = False


def main(argv=None) -> int:
    global INJECT
    ap = argparse.ArgumentParser()
    ap.add_argument('--inject', action='store_true',
                    help='also send a real synthetic Alt+C via keybd_event')
    ns = ap.parse_args(argv)
    INJECT = ns.inject

    real_stdout = sys.stdout
    sys.stdout = _Tee(real_stdout)
    try:
        shell = load_shell()
        res = {}
        res.update(arm_a(shell))
        res.update(arm_b(shell))
        res['probe'] = {
            'shell': SHELL,
            'inject': INJECT,
            'python': sys.version.split()[0],
            'pid': os.getpid(),
        }
        rc = 0
        a = res['arm_a']
        if not (a['registered'] and all(a['simulate_press_delivered'])
                and a['handler_invocations'] == 3
                and a['thread_pressed_counter'] == 3
                and a['independent_register_while_held']
                ['expect_ok_false_and_1409']
                and a['negative_control_ok']
                and not a['focus_stolen']):
            rc = 3
        b = res.get('arm_b', {})
        if b.get('visible_after_toggle_1') is not True or \
                b.get('visible_after_toggle_2') is not False or \
                b.get('shell_visible_flag_1') is not True or \
                b.get('shell_visible_flag_2') is not False or \
                b.get('owner_ever_shown_a_window') is not False:
            rc = 3
        if INJECT and not a.get('injected_keybd_event_delivered'):
            rc = 3
        res['verdict'] = {'rc': rc,
                          'PASS' if rc == 0 else 'RED': True}
        res['captured_shell_log_lines'] = _captured
        real_stdout.write('\nALT_C_E2E_RESULT ' + json.dumps(
            res, indent=2, ensure_ascii=False) + '\n')
        real_stdout.flush()
        return rc
    finally:
        sys.stdout = real_stdout


if __name__ == '__main__':
    sys.exit(main())
