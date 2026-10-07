#!/usr/bin/env python3
"""Does the tray's Quit really close the app — shell AND worker?

Owner, 2026-10-08: *"tira o botao de quit sotto do painel. só tem q quit no icon
do system tray"*. The tray did not exist, so it was built; and because it is now
the ONLY way to close the app, "the Quit works" has to be a number, not a claim.

This probe is OUTSIDE the shell and measures, on a real run:

  1. the tray WINDOW exists (a message-only window of the shell's own pid);
  2. the tray ICON is registered in the notification area — proved from ANOTHER
     process by `Shell_NotifyIconW(NIM_MODIFY)` on the same (hwnd, uID), which
     answers FALSE for an icon that is not there;
  3. the menu CONTAINS a Quit item — its id and its text, read out of the shell's
     log (`TRAY_MENU`), which the shell logs when it builds the menu;
  4. before the Quit: the live pids (shell + its children), the mutex
     `Local\\SottoShell`, and the window census;
  5. the Quit is driven through the REAL message path — `WM_COMMAND` with the
     menu's own Quit id, posted to the tray window — i.e. everything except the
     mouse click that opens the menu;
  6. after the Quit: NEITHER pid alive, the mutex FREE, the icon GONE, no window.

No `--show`, no audio device (a stand-in worker that opens none), the child is
`pythonw.exe` with CREATE_NO_WINDOW, and every kill names the exact pid after
reading that pid's own image path.

Usage: python _main/tray-quit-probe.py
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
FAKE_WORKER = os.path.join(HERE, '_fake-worker-stdout.py')
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
MUTEX_NAME = 'Local\\SottoShell'

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

WM_COMMAND = 0x0111
CREATE_NO_WINDOW = 0x08000000
NIM_MODIFY = 1
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
WM_TRAY_CALLBACK = 0x8000 + 1
TRAY_ID = 0xB0F1
SYNCHRONIZE = 0x00100000
TH32CS_SNAPPROCESS = 0x00000002
MAX_PATH = 260

user32.PostMessageW.restype = wt.BOOL
user32.PostMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                ctypes.c_ssize_t]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wt.LPARAM]
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.CloseHandle.argtypes = [wt.HANDLE]
kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD,
                                               wt.LPWSTR,
                                               ctypes.POINTER(wt.DWORD)]
kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.c_void_p]
kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.c_void_p]
kernel32.OpenMutexW.restype = wt.HANDLE
kernel32.OpenMutexW.argtypes = [wt.DWORD, wt.BOOL, wt.LPCWSTR]
shell32.Shell_NotifyIconW.restype = wt.BOOL
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', ctypes.c_uint),
        ('uFlags', ctypes.c_uint), ('uCallbackMessage', ctypes.c_uint),
        ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128),
        ('dwState', wt.DWORD), ('dwStateMask', wt.DWORD),
        ('szInfo', wt.WCHAR * 256), ('uVersion', ctypes.c_uint),
        ('szInfoTitle', wt.WCHAR * 64), ('dwInfoFlags', wt.DWORD),
        ('guidItem', ctypes.c_byte * 16), ('hBalloonIcon', wt.HICON),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD),
                ('th32ProcessID', wt.DWORD),
                ('th32DefaultHeapID', ctypes.c_void_p),
                ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                ('th32ParentProcessID', wt.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wt.DWORD),
                ('szExeFile', wt.WCHAR * MAX_PATH)]


def icon_registered(hwnd: int) -> bool:
    """TRUE only if the notification area holds an icon for this (hwnd, uID).

    `NIM_MODIFY` on an icon that is not there answers FALSE, so this is a real
    external question about the tray's state — not a read-back of our own intent.
    """
    if not hwnd:
        return False
    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.hWnd = hwnd
    nid.uID = TRAY_ID
    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
    nid.uCallbackMessage = WM_TRAY_CALLBACK
    nid.szTip = 'probe'
    return bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))


def mutex_held(name=MUTEX_NAME) -> bool:
    handle = kernel32.OpenMutexW(SYNCHRONIZE, False, name)
    if handle:
        kernel32.CloseHandle(handle)
        return True
    return False


def image_path(pid: int):
    h = kernel32.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wt.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(h)


def _first_int(pattern, text, default=None):
    m = re.search(pattern, text)
    return int(m.group(1)) if m else default


def children_of(pid: int):
    """Direct child pids, from the OS process table."""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap:
        return []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    out = []
    try:
        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.th32ParentProcessID == pid:
                out.append(int(entry.th32ProcessID))
            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snap)
    return out


def alive(pid: int) -> bool:
    return image_path(pid) is not None


def windows_of_pid(pid: int):
    found = []
    WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _lparam):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        buf = ctypes.create_unicode_buffer(512)
        user32.GetClassNameW(hwnd, buf, 512)
        cls = buf.value
        user32.GetWindowTextW(hwnd, buf, 512)
        found.append({'hwnd': int(hwnd), 'class': cls, 'title': buf.value,
                      'visible': bool(user32.IsWindowVisible(hwnd))})
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def log_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except FileNotFoundError:
        return ''


def wait_for(path, needle, timeout):
    until = time.time() + timeout
    while time.time() < until:
        if needle in log_text(path):
            return True
        time.sleep(0.1)
    return False


def launch(tag, worker=True, mutex_name=None):
    stamp = time.strftime('%Y%m%d-%H%M%S')
    log_path = os.path.join(HERE, f'_tray-quit-{tag}-{stamp}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--log', log_path]
    if mutex_name:
        # A PRIVATE name: the owner's own shell holds the default one, so the
        # default cannot answer "was the lock released".
        cmd += ['--mutex-name', mutex_name]
    if worker:
        # `--with-worker` is AUTHORITATIVE and outranks the `--no-hotkey`
        # measurement suppression, which would otherwise decline the worker.
        cmd += ['--with-worker', '--worker', FAKE_WORKER]
    proc = subprocess.Popen(cmd, cwd=os.path.join(ROOT, 'app', 'webview'),
                            creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc, log_path


def kill_exact(pid):
    """PID-EXACT, and only after reading that pid's own image path."""
    img = image_path(pid)
    if not img or not os.path.basename(img).lower().startswith('python'):
        return False
    h = kernel32.OpenProcess(0x0001, False, pid)
    if not h:
        return False
    try:
        kernel32.TerminateProcess(h, 0)
    finally:
        kernel32.CloseHandle(h)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(HERE, 'tray-quit.json'))
    ap.add_argument('--no-relaunch', action='store_true')
    args = ap.parse_args()

    result = {'mutex_held_before': mutex_held()}
    # The owner's own shell holds the DEFAULT name, so the default can never
    # answer "was the lock released". A PRIVATE name can.
    probe_mutex = f'Local\\SottoShell-probe-{os.getpid()}'
    result['probe_mutex_name'] = probe_mutex
    result['probe_mutex_free_before'] = not mutex_held(probe_mutex)
    proc, log_path = launch('run1', mutex_name=probe_mutex)
    result['log'] = log_path
    try:
        got_window = wait_for(log_path, 'TRAY_WINDOW created=true', 20)
        got_icon = wait_for(log_path, 'TRAY_ICON_ADD ok=true', 10)
        wait_for(log_path, 'RECEIVER_READY', 15)
        text = log_text(log_path)
        result['tray_window_logged'] = got_window
        result['tray_icon_add_ok'] = got_icon
        m = re.search(r'pid=(\d+)', text)
        result['shell_pid'] = int(m.group(1)) if m else proc.pid
        result['tray_hwnd'] = _first_int(r'TRAY_WINDOW created=true hwnd=(\d+)',
                                         text)
        result['tray_menu'] = [
            line.strip() for line in text.splitlines() if 'TRAY_MENU' in line]
        result['tray_disabled'] = 'TRAY_DISABLED' in text
        result['shell_workers'] = children_of(result['shell_pid'])
        result['icon_registered_external'] = icon_registered(result['tray_hwnd'])
        result['windows_before'] = windows_of_pid(result['shell_pid'])
        result['visible_before'] = sum(1 for w in result['windows_before']
                                       if w['visible'])
        result['mutex_held_with_app'] = mutex_held()
        result['probe_mutex_held_with_app'] = mutex_held(probe_mutex)
        result['single_instance_logged'] = [
            line.strip() for line in text.splitlines()
            if 'SINGLE_INSTANCE' in line]

        # ---- the Quit, through the REAL message path -----------------------
        quit_id = None
        for line in result['tray_menu']:
            mm = re.search(r"\[(\d+)\]='Quit Sotto'", line)
            if mm:
                quit_id = int(mm.group(1))
        result['quit_menu_id'] = quit_id
        if quit_id is None or not result['tray_hwnd']:
            result['verdict'] = 'NO-QUIT-ITEM'
            return 1
        user32.PostMessageW(wt.HWND(result['tray_hwnd']), WM_COMMAND, quit_id, 0)
        until = time.time() + 15
        while time.time() < until and alive(result['shell_pid']):
            time.sleep(0.2)
        time.sleep(1.5)  # let the process table settle

        result['shell_alive_after'] = alive(result['shell_pid'])
        result['workers_after'] = [p for p in result['shell_workers'] if alive(p)]
        result['mutex_held_after'] = mutex_held()
        result['probe_mutex_held_after'] = mutex_held(probe_mutex)
        result['icon_registered_after'] = icon_registered(result['tray_hwnd'])
        result['windows_after'] = windows_of_pid(result['shell_pid'])
        result['quit_logged'] = 'TRAY_QUIT requested=true' in log_text(log_path)
        result['tray_icon_delete_logged'] = 'TRAY_ICON_DELETE ok=true' in log_text(log_path)
        result['shell_exit_logged'] = [
            line.strip() for line in log_text(log_path).splitlines()
            if 'SHELL_EXIT' in line]

        # ---- and the tray does not come up TWICE ---------------------------
        if not args.no_relaunch:
            proc2, log2 = launch('run2', worker=False)
            wait_for(log2, 'TRAY_ICON_ADD ok=true', 20)
            text2 = log_text(log2)
            m2 = re.search(r'pid=(\d+)', text2)
            pid2 = int(m2.group(1)) if m2 else proc2.pid
            hwnd2 = _first_int(r'TRAY_WINDOW created=true hwnd=(\d+)', text2)
            result['relaunch'] = {
                'pid': pid2,
                'tray_hwnd': hwnd2,
                'tray_windows_for_pid': [
                    w for w in windows_of_pid(pid2)
                    if w['class'] == 'SottoTrayWindow'],
                'icon_registered_new': icon_registered(hwnd2),
                'icon_registered_old': icon_registered(result['tray_hwnd']),
                'single_instance': 'already_running=true' in text2,
            }
            kill_exact(pid2)
            proc2.wait(timeout=5)
            result['relaunch_killed_pid'] = pid2
        result['verdict'] = 'MEASURED'
        return 0
    finally:
        kill_exact(proc.pid)
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
        with open(args.out, 'w', encoding='utf-8') as fh:
            json.dump(result, fh, indent=2)
        print(json.dumps(result, indent=2))


if __name__ == '__main__':
    sys.exit(main())
