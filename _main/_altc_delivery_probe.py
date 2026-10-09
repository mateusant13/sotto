#!/usr/bin/env python3
"""Alt+C OS-LEVEL delivery probe — independent of the product's own code.

WHY THIS FILE EXISTS
--------------------
`simulate_press()` posts a real `WM_HOTKEY` with `PostThreadMessageW`, so a
`PANEL_SHOWN reason=hotkey` log line is NOT evidence that the OS turned a
physical key into a hotkey message — the in-process simulator produces the very
same line. This probe therefore injects at the INPUT QUEUE level (`SendInput`)
and attributes every log line to itself by recording the log byte offset
immediately before injecting and reading only what appeared after.

Deliberately does NOT import `sotto_webview`: the receiving side must be
measured by a foreign observer, not by the code under test.

Usage:  python _altc_delivery_probe.py <pid> <log-path> [--restore]
"""

import ctypes
import ctypes.wintypes as wt
import json
import sys
import time

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

# Win32 constants (see RegisterHotKey / WM_HOTKEY / SendInput docs)
WM_HOTKEY = 0x0312
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_MENU = 0x12
VK_C = 0x43

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wt.WORD), ('wScan', wt.WORD), ('dwFlags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wt.LONG), ('dy', wt.LONG), ('mouseData', wt.DWORD),
                ('dwFlags', wt.DWORD), ('time', wt.DWORD),
                ('dwExtraInfo', ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [('uMsg', wt.DWORD), ('wParamL', wt.WORD), ('wParamH', wt.WORD)]


class _I(ctypes.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', wt.DWORD), ('u', _I)]


user32.SendInput.argtypes = (wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wt.UINT
user32.GetWindowTextLengthW.argtypes = (wt.HWND,)
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = (wt.HWND, wt.LPWSTR, ctypes.c_int)
user32.GetClassNameW.argtypes = (wt.HWND, wt.LPWSTR, ctypes.c_int)
user32.IsWindowVisible.argtypes = (wt.HWND,)
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = (wt.HWND, ctypes.POINTER(wt.DWORD))
user32.GetWindowThreadProcessId.restype = wt.DWORD

user32.RegisterHotKey.argtypes = (wt.HWND, ctypes.c_int, wt.UINT, wt.UINT)
user32.RegisterHotKey.restype = wt.BOOL


def windows_of_pid(pid):
    """Every top-level window owned by `pid`, with the fields that decide show/hide."""
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append({'hwnd': int(hwnd), 'hex': hex(int(hwnd)),
                          'class': cls.value, 'title': buf.value,
                          'visible': bool(user32.IsWindowVisible(hwnd))})
        return True

    user32.EnumWindows(cb, 0)
    return found


def send_alt_c():
    """A real Alt+C through the OS input path. Returns (events_sent, winerror)."""
    seq = [(VK_MENU, 0), (VK_C, 0), (VK_C, KEYEVENTF_KEYUP), (VK_MENU, KEYEVENTF_KEYUP)]
    arr = (INPUT * len(seq))()
    for i, (vk, flags) in enumerate(seq):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=0)
    ctypes.set_last_error(0)
    sent = user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
    return sent, ctypes.get_last_error()


def read_from(path, offset):
    """Only the bytes appended after `offset` — self-attribution, not a guess."""
    with open(path, 'rb') as fh:
        fh.seek(offset)
        return fh.read().decode('utf-8', 'replace')


def main():
    pid = int(sys.argv[1])
    log_path = sys.argv[2]
    restore = '--restore' in sys.argv

    out = {'pid': pid, 'log': log_path, 't_start': time.strftime('%H:%M:%S')}
    before_wins = windows_of_pid(pid)
    out['windows_before'] = before_wins

    # Which of these windows is the panel? The one the shell's toggle maps.
    was_visible = any(w['visible'] for w in before_wins)

    offset = len(open(log_path, 'rb').read())
    sent, err = send_alt_c()
    out['sendinput'] = {'events': 4, 'sent': sent, 'winerror': err,
                        'note': 'sent < 4 means UIPI/injection refused it'}
    time.sleep(1.5)
    after_wins = windows_of_pid(pid)
    out['windows_after'] = after_wins
    now_visible = any(w['visible'] for w in after_wins)

    delta = read_from(log_path, offset)
    out['log_delta'] = [l for l in delta.splitlines() if l.strip()][-40:]
    out['hotkey_lines'] = [l for l in out['log_delta'] if 'reason=hotkey' in l]
    out['was_visible'] = was_visible
    out['now_visible'] = now_visible
    out['visibility_changed'] = was_visible != now_visible

    # Put the owner's screen back the way this probe found it.
    if restore and now_visible != was_visible:
        sent2, err2 = send_alt_c()
        time.sleep(1.5)
        out['restore'] = {'sent': sent2, 'winerror': err2,
                          'visible_now': any(w['visible'] for w in windows_of_pid(pid))}

    out['VERDICT'] = 'DELIVERED' if (out['visibility_changed']
                                     and out['hotkey_lines']) else 'NOT_PROVEN'
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()