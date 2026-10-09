# WINDOW CENSUS for all-gates.ps1 - named verification box CENSUS-ALL-GATES.
#
# WHY THIS FILE EXISTS: hard rule 1 forbids leaving a visible console window, and the
# house window census samples only once per 60 s - which by the project's own measured
# finding cannot prove the ABSENCE of a window (see AGENTS.md, "the house window census
# samples ONCE PER 60 s"). A short-lived flash is exactly the thing that slips past it.
# So this samples at 25 ms over the whole self-test run and names any pid that was
# WS_VISIBLE with a non-zero alpha.
#
# BUG FOUND IN THIS FILE'S OWN FIRST DRAFT, 2026-10-07: it shelled out to `wmic` on
# EVERY 25 ms sample, so the census spent most of its budget waiting on a subprocess
# and could not sample at 25 ms at all. A census that does not run at its stated
# cadence cannot see the flash it exists to catch, and would have reported PASS while
# watching nothing. Fixed by enumerating processes in-process via
# CreateToolhelp32Snapshot (microseconds, no child process).
#
# It tracks the WHOLE process tree rooted at the aggregate. A gate that spawns a
# console of its own is still on the owner's screen and still this lane's fault.
#
# Run it with pythonw.exe (or any hidden launch) - a python.exe console is itself a
# visible window and would make the census report its own noise.
#
# Usage: pythonw.exe _main\_all-gates-window-census.py
# Exit : 0 = no visible window observed. Non-zero = one was.

import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

PW = os.path.join(os.environ.get("PSHOME", r"C:\Program Files\PowerShell\7"), "pwsh.exe")
GATE = r"H:\sotto\_moved\aireplay\_main\all-gates.ps1"
INTERVAL = 0.025          # 25 ms, not the house 60 s
BUDGET_S = 240.0

CREATE_NO_WINDOW = 0x08000000
TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * MAX_PATH),
    ]


def descendants(root):
    """Every descendant pid of `root`, inclusive, in-process and in microseconds."""
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    kids = {}
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not k32.Process32First(snap, ctypes.byref(pe)):
            raise ctypes.WinError(ctypes.get_last_error())
        while True:
            kids.setdefault(pe.th32ParentProcessID, []).append(pe.th32ProcessID)
            if not k32.Process32Next(snap, ctypes.byref(pe)):
                break
    finally:
        k32.CloseHandle(snap)

    out = {root}
    stack = [root]
    while stack:
        cur = stack.pop()
        for k in kids.get(cur, ()):
            if k not in out:
                out.add(k)
                stack.append(k)
    return out


def visible_windows():
    """[(pid, alpha)] for every visible top-level window on the desktop."""
    found = []
    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        # alpha 0 == pywebview's invisible creation dance; not on the owner's screen.
        ex = wintypes.LONG()
        # GWL_EXSTYLE = -20
        if user32.GetWindowLongPtrW(hwnd, ctypes.c_long(-20), ctypes.byref(ex)) & 0x00080000:
            wa = wintypes.BYTE()
            # LWA_ALPHA = 0x2
            if not user32.GetLayeredWindowAttributes(hwnd, None, ctypes.byref(wa), 0x2):
                wa.value = 255
            found.append((pid.value, wa.value))
        else:
            found.append((pid.value, 255))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return found


def main():
    if not os.path.exists(GATE):
        print("CENSUS: gate script not found: %s" % GATE)
        return 2

    popen = subprocess.Popen(
        [PW, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", GATE, "-SelfTest"],
        creationflags=CREATE_NO_WINDOW,      # the census itself opens nothing
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    t0 = time.time()
    samples = 0
    gaps = []
    hits = {}
    last = time.time()
    while popen.poll() is None and (time.time() - t0) < BUDGET_S:
        now = time.time()
        gaps.append(now - last)
        last = now
        try:
            tracked = descendants(popen.pid)
        except OSError as exc:
            # Loud, not silent: without the tree we cannot clear or condemn anything.
            print("CENSUS ERROR: process snapshot failed (%s); census ABORTED "
                  "rather than reporting a clean run it did not observe." % exc,
                  file=sys.stderr)
            popen.kill()
            return 3
        for pid, alpha in visible_windows():
            if pid in tracked and alpha > 0:
                hits.setdefault(pid, []).append(alpha)
        samples += 1
        time.sleep(INTERVAL)

    out = popen.stdout.read().decode("utf-8", "replace") if popen.stdout else ""
    rc = popen.poll()
    if rc is None:
        popen.kill()
        rc = "killed-over-budget"

    elapsed = time.time() - t0
    worst = max(gaps) if gaps else 0.0
    print("CENSUS-ALL-GATES root_pid=%d rc=%s" % (popen.pid, rc))
    print("  cadence     = %.0f ms target, %.1f ms worst observed gap" % (INTERVAL * 1000, worst * 1000))
    print("  samples     = %d over %.1f s  (%.1f Hz effective)" % (samples, elapsed, samples / elapsed if elapsed else 0))
    print("  window-seen = %d samples over %d distinct pid(s)"
          % (sum(len(v) for v in hits.values()), len(hits)))
    print("  detail      = %s" % (
        "NONE - no console window visible on the owner's screen"
        if not hits else "; ".join(
            "pid=%d n=%d alpha=%d" % (p, len(v), max(v)) for p, v in hits.items())))
    tail = out.strip().splitlines()[-1] if out.strip() else "(no output)"
    print("  gate final  = %s" % tail)
    # A census that never sampled is not a pass.
    ok = (not hits) and samples > 100
    print("VERDICT %s" % ("PASS" if ok else
                         ("FAIL - a visible window was observed" if hits
                          else "FAIL - too few samples to clear anything")))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())