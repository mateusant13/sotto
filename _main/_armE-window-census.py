"""Window census for ARM E's OWN process tree, at this probe's own cadence.

The house census samples ONCE PER 60 s (AGENTS.md), so it can only prove
PRESENCE and never absence -- a window shorter than its period passes unseen. A
claim of "no window appeared" therefore has to sample at its own cadence, over
its OWN pids. This driver does exactly that: it spawns the command after `--`
with CREATE_NO_WINDOW, walks the process tree rooted at that child, and every
200 ms counts the VISIBLE top-level windows owned by any pid in that tree.

    py -3 _main/_armE-window-census.py --secs 60 -- py -3 _main/panel-exit3-oracle.py --arm-e-real

READ-ONLY: it opens no window and signals no process. The child's own stdout is
inherited, so the oracle's JSON is printed verbatim; this driver writes its
receipt to stderr and prints a final summary line to stdout.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

CREATE_NO_WINDOW = 0x08000000
TH32CS_SNAPPROCESS = 0x00000002
CADENCE_S = float(os.environ.get('CENSUS_CADENCE_MS', '100')) / 1000.0

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
user32 = ctypes.WinDLL('user32', use_last_error=True)


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
                ('th32ProcessID', wintypes.DWORD),
                ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)),
                ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
                ('th32ParentProcessID', wintypes.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                ('szExeFile', ctypes.c_wchar * 260)]


def process_table() -> list[tuple[int, int, str]]:
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == wintypes.HANDLE(-1).value or not snap:
        return []
    rows: list[tuple[int, int, str]] = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        if kernel32.Process32FirstW(snap, ctypes.byref(entry)):
            while True:
                rows.append((int(entry.th32ProcessID),
                             int(entry.th32ParentProcessID), entry.szExeFile))
                if not kernel32.Process32NextW(snap, ctypes.byref(entry)):
                    break
    finally:
        kernel32.CloseHandle(snap)
    return rows


def tree(root: int) -> set[int]:
    rows = process_table()
    kids: dict[int, list[int]] = {}
    for pid, ppid, _ in rows:
        kids.setdefault(ppid, []).append(pid)
    seen, stack = set(), [root]
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        stack.extend(kids.get(p, []))
    return seen


def visible_windows() -> list[tuple[int, int, str, str]]:
    out: list[tuple[int, int, str, str]] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            out.append((int(pid.value), int(hwnd), buf.value, cls.value))
        return True

    user32.EnumWindows(cb, 0)
    return out


def main() -> int:
    argv = sys.argv[1:]
    secs = 0.0
    if '--secs' in argv:
        i = argv.index('--secs')
        secs = float(argv[i + 1])
        del argv[i:i + 2]
    if '--' not in argv:
        print('usage: _armE-window-census.py --secs N -- <command>', file=sys.stderr)
        return 2
    cmd = argv[argv.index('--') + 1:]

    proc = subprocess.Popen(cmd, creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    root = proc.pid
    print(f'CENSUS-PID root={root} cadence_ms={int(CADENCE_S * 1000)} '
          f'cmd={cmd}', file=sys.stderr)
    samples = 0
    visible_samples = 0
    named: dict[str, int] = {}
    t0 = time.time()
    while proc.poll() is None:
        pids = tree(root)
        wins = [w for w in visible_windows() if w[0] in pids]
        samples += 1
        if wins:
            visible_samples += 1
            for pid, hwnd, title, cls in wins:
                key = f'{pid}:{hwnd}'
                named[key] = named.get(key, 0) + 1
                print(f'CENSUS-PID visible pid={pid} hwnd={hwnd} '
                      f'title={title!r} class={cls!r} sample={samples}',
                      file=sys.stderr)
        if secs and time.time() - t0 > secs:
            print(f'CENSUS-PID deadline {secs}s reached; child still running',
                  file=sys.stderr)
            break
        time.sleep(CADENCE_S)
    rc = proc.wait()
    child_out = proc.stdout.read().decode('utf-8', 'replace') if proc.stdout else ''
    if child_out:
        sys.stdout.write(child_out if child_out.endswith('\n') else child_out + '\n')
    print(f'CENSUS-PID pid_tree_root={root} samples={samples} '
          f'visible_samples_over_tree={visible_samples} '
          f'distinct={len(named)} child_rc={rc}')
    for k, n in named.items():
        print(f'CENSUS-PID ALERTA-JANELA chave={k} samples_visible={n}')
    return rc


if __name__ == '__main__':
    sys.exit(main())
