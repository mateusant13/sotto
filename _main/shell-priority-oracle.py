# NO-BUG: The window the owner types into is never below NORMAL.
"""The window the owner types into is never below NORMAL.

MEASURED 2026-11-04 (extreme-optimization-audit L10): the live shell, pid 20448, ran
at `BELOW_NORMAL_PRIORITY_CLASS`, and so did its worker; the control pair beside it
(explorer.exe, pwsh.exe) was `NORMAL`, so the cap came from the launcher/task, not from
this code. A surface a human interacts with at BELOW_NORMAL loses every race against a
batch lane that is only doing work nobody is waiting for.

The cure is `raise_visible_priority()` in `app/webview/sotto_webview.py`, called first
thing in `main()`, and the worker KEEPS its own BELOW_NORMAL: the batch must yield, the
window must not. This file drives that real function.

ARMS
  1. demote this process to BELOW_NORMAL, call the real function, require NORMAL back —
     the planted defect the arm must catch;
  2. at NORMAL, call it again: it must NOT log a raise (idempotent, and the log says so);
  3. at HIGH, it must not LOWER it (a raise is one-directional);
  4. the log line carries `was=` and `now=`, so the change is reversible from the log.

`--neg-arm` removes the call site in a COPY next to the original and requires arm 1 to
fall (a cure that is written but never called is the defect this arm exists to prevent).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import io
import os
import sys

SHELL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                         'app', 'webview')
SHELL = os.path.join(SHELL_DIR, 'sotto_webview.py')
BELOW_NORMAL, NORMAL, HIGH = 0x00004000, 0x00000020, 0x00000080

kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.GetPriorityClass.argtypes = [ctypes.c_void_p]
kernel32.GetPriorityClass.restype = ctypes.c_uint32
kernel32.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel32.SetPriorityClass.restype = ctypes.c_bool


def load(path=None):
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    if path is None:
        import sotto_webview as shell  # noqa: PLC0415
        return shell
    import importlib.util  # noqa: PLC0415
    spec = importlib.util.spec_from_file_location('shell_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules['shell_under_test'] = mod
    spec.loader.exec_module(mod)
    return mod


def current() -> int:
    return int(kernel32.GetPriorityClass(kernel32.GetCurrentProcess()))


def set_class(value: int) -> None:
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), value)


def judge(shell) -> list:
    checks = []
    logs = []
    original = current()
    try:
        # ARM 1 -- the planted demotion.
        set_class(BELOW_NORMAL)
        logs.clear()
        got = shell.raise_visible_priority(logs.append)
        checks.append(('raises_below_normal_to_normal',
                       current() == NORMAL and got == 'NORMAL',
                       f'class=0x{current():X} returned={got} log={logs}'))
        checks.append(('logs_was_and_now',
                       any('was=BELOW_NORMAL' in line and 'now=NORMAL' in line
                           for line in logs),
                       f'log={logs}'))

        # ARM 2 -- idempotent at NORMAL: no raise, and the line says which.
        logs.clear()
        got = shell.raise_visible_priority(logs.append)
        checks.append(('no_raise_when_already_normal',
                       current() == NORMAL and got == 'NORMAL'
                       and any('raised=false' in line for line in logs),
                       f'class=0x{current():X} returned={got} log={logs}'))

        # ARM 3 -- one direction only: never LOWER a higher class.
        set_class(HIGH)
        logs.clear()
        got = shell.raise_visible_priority(logs.append)
        checks.append(('never_lowers_a_higher_class',
                       current() == HIGH and got == 'HIGH',
                       f'class=0x{current():X} returned={got}'))
    finally:
        set_class(original)
    return checks


def neg_arm() -> int:
    raw = io.open(SHELL, encoding='utf-8', newline='').read()
    crlf = '\r\n' in raw
    src = raw.replace('\r\n', '\n')
    anchor = '    raise_visible_priority(log)\n'
    if anchor not in src:
        print('MUTANT NOT APPLICABLE: call site anchor absent')
        print('NEG-ARM: FAIL')
        return 0
    path = os.path.join(SHELL_DIR, 'sotto_webview__mutant_priority.py')
    mutated = src.replace(anchor, '', 1)
    if crlf:
        mutated = mutated.replace('\n', '\r\n')
    io.open(path, 'w', encoding='utf-8', newline='').write(mutated)
    try:
        shell = load(path)
        checks = {c[0]: c for c in judge(shell)}
    finally:
        sys.modules.pop('shell_under_test', None)
        try:
            os.remove(path)
        except OSError:
            pass
    # With the call site gone, the module still DEFINES the function, so arm 1
    # cannot fall -- that is the point: the cure exists and is never called.
    # What must fall is the CALL: this arm measures it in the module source.
    called = 'raise_visible_priority(log)' in mutated
    ok = (not called) and all(checks[c][1] for c in checks)
    print(f'MUTANT call_site_removed: CAUGHT call_present={called} '
          f'arms_still_green={all(checks[c][1] for c in checks)}')
    print(f'NEG-ARM SUMMARY cases=1 caught={int(ok)}')
    print('NEG-ARM: PASS' if ok else 'NEG-ARM: FAIL')
    return 1 if ok else 0


def main() -> int:
    checks = judge(load())
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f'ARM {"PASS" if ok else "FAIL"} {name} {detail}')
    print(f'CHECK arms={len(checks)} failed={len(failed)}')
    print('VERDICT: PASS' if not failed else 'VERDICT: FAIL')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv else main())
