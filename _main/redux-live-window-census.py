#!/usr/bin/env python3
"""Window census for the Redux live lane -- does MY process tree ever own a VISIBLE window?

WHY THIS FILE EXISTS
--------------------
The dispatch brief's hard rule: *"Never leave a visible window (pythonw.exe or
creationflags 0x08000000)"*.  Reading the source and seeing the flag is a claim
about the code; this file is the MEASUREMENT of it, because the repo's own rule
is that absence needs an instrument with a positive control ("a census that
samples every 60 s cannot prove the absence of a short-lived window").

INSTRUMENT, CADENCE, COUNT (stated up front, as the house rules demand)
----------------------------------------------------------------------
* Instrument: `user32.EnumWindows` + `IsWindowVisible` + `GetWindowThreadProcessId`,
  called IN-PROCESS through ctypes -- no WMI, no subprocess per sample, and never
  `Get-CimInstance Win32_Process` in a loop.
* Cadence: every 100 ms (10 Hz), from before the spawn until the child is gone.
  (The loop checks `poll()` BEFORE sampling, so the last sample is the last one
  in which the child was alive -- there is no post-exit tail; saying otherwise
  here would be a claim the code does not keep.)
* Count: printed as `samples=<N>`; the verdict is a fraction of N, never a bare
  zero.

THE POSITIVE CONTROL, AND WHY IT COSTS THE OWNER NOTHING
--------------------------------------------------------
A census that reports zero windows proves nothing unless it can report a
non-zero one.  The naive control -- spawn the same child WITHOUT the flag and
watch the console appear -- would put a real console on the owner's screen and
STEAL FOCUS from whatever he is watching, which this repo forbids.  So the
control is built from the same sample set instead: the instrument must see
VISIBLE windows belonging to OTHER pids in the same samples (the owner's shell,
his browser, whatever is on screen).  Those rows are the proof the instrument
is not blind; the child's own count is the measurement.

ARMS (both colours in ONE command, no flag to remember)
------------------------------------------------------
  ARM A / child-with-CREATE_NO_WINDOW   expect: child visible samples == 0
  ARM B / instrument-is-not-blind       expect: other-pid visible samples >= 1
  ARM C / no-python-family-window       expect: NO pid named python/pythonw/conhost/py
                                        owns a visible window in ANY sample.  ARM A alone
                                        tracks one pid; a child can be reached through a
                                        helper (conhost, a launcher).  This arm closes that
                                        gap by NAME, over every pid the census ever saw.
  VERDICT is the conjunction; any arm failing prints FAIL and returns 1.

No audio device is opened (the child is run on a WAV).  Nothing is killed: the
child is asked to stop by its own `--max-seconds`, and pids 28428 / 29008 are
only ever READ.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
WORKER = ROOT / "worker" / "redux_live.py"
CREATE_NO_WINDOW = 0x08000000

user32 = ctypes.WinDLL("user32", use_last_error=True)

WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumWindows.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int


def visible_windows() -> dict:
    """{pid: [title, ...]} for every VISIBLE top-level window, right now."""
    out: dict = {}

    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        pid = wt.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, buf, n + 1)
        out.setdefault(int(pid.value), []).append(buf.value)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return out


# Names that would mean THIS lane put a window on the owner's screen.  `conhost`
# is in the set on purpose: a console window belongs to conhost.exe, not to the
# python.exe that owns the console, so tracking the child pid alone would miss it.
PYTHON_FAMILY = {"python", "pythonw", "py", "conhost"}


def resolve_names(pids) -> dict:
    """{pid: process_name} for `pids`, in ONE `Get-Process` call.

    Deliberately not a per-sample loop and deliberately not `Get-CimInstance
    Win32_Process` (both are house-rule violations on this box); this runs once,
    after the samples, purely to give the pids the census saw a NAME.
    """
    pids = sorted({int(p) for p in pids})
    if not pids:
        return {}
    listing = ",".join(str(p) for p in pids)
    script = (f"Get-Process -Id {listing} -ErrorAction SilentlyContinue | "
              "Select-Object Id,ProcessName | ConvertTo-Json -Compress")
    try:
        out = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:                      # noqa: BLE001 - reported, never hidden
        print(f"# WARN name resolution failed: {exc!r}")
        return {}
    if not out:
        return {}
    try:
        rows = json.loads(out)
    except ValueError as exc:
        print(f"# WARN name resolution unparseable ({exc}): {out[:120]}")
        return {}
    if isinstance(rows, dict):
        rows = [rows]
    return {int(r["Id"]): str(r.get("ProcessName") or "") for r in rows}


def main() -> int:
    argv = sys.argv[1:]
    max_seconds = "3"
    engine = "onnx"
    neg = "--neg-arm" in argv
    if "--max-seconds" in argv:
        max_seconds = argv[argv.index("--max-seconds") + 1]
    if "--engine" in argv:
        engine = argv[argv.index("--engine") + 1]

    cmd = [sys.executable, str(WORKER), "--engine", engine,
           "--wav", str(HERE / "en-us-sample.wav"),
           "--max-seconds", max_seconds, "--threads", "2"]

    print(f"# redux-live-window-census  cadence=100ms  engine={engine}  max_seconds={max_seconds}")
    print(f"# child: {' '.join(cmd)}")
    print("# flag: creationflags=CREATE_NO_WINDOW (0x08000000) -- the claim under test")

    # POSITIVE CONTROL, taken BEFORE the spawn: the instrument must already see
    # windows that are on screen right now.  This is not the child's evidence.
    pre = visible_windows()
    pre_titles = [t for titles in pre.values() for t in titles if t]
    print(f"# PRE-SPAWN positive control: visible windows={sum(len(v) for v in pre.values())} "
          f"pids={len(pre)} sample_titles={json.dumps(pre_titles[:4], ensure_ascii=False)}")

    t0 = time.perf_counter()
    proc = subprocess.Popen(cmd, cwd=str(ROOT), creationflags=CREATE_NO_WINDOW,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    child = proc.pid
    print(f"# child pid={child} spawned with CREATE_NO_WINDOW")

    samples = 0
    child_hits = []          # (t_s, titles) -- MUST stay empty
    other_samples = 0        # samples in which the instrument saw ANY other pid's window
    other_seen: dict = {}
    own_tree = {child}
    while True:
        alive = proc.poll() is None
        if not alive and time.perf_counter() - t0 > 0:
            break
        wins = visible_windows()
        samples += 1
        if child in wins:
            child_hits.append((round(time.perf_counter() - t0, 3), wins[child]))
        others = {p: v for p, v in wins.items() if p not in own_tree}
        if others:
            other_samples += 1
            for p, v in others.items():
                for t in v:
                    other_seen.setdefault(p, set()).add(t)
        time.sleep(0.1)

    wall = round(time.perf_counter() - t0, 2)
    rc = proc.wait()
    print(f"# child exited rc={rc} wall={wall}s")
    print(f"samples={samples} at 100ms  child_visible_samples={len(child_hits)}  "
          f"other_pid_visible_samples={other_samples}")
    if child_hits:
        for t_s, titles in child_hits[:5]:
            print(f"  CHILD WINDOW at +{t_s}s titles={json.dumps(titles, ensure_ascii=False)}")

    # ARM A: the child never owned a visible window.
    arm_a = len(child_hits) == 0
    # ARM B: the instrument demonstrably sees visible windows (positive control).
    arm_b = other_samples >= 1

    # ARM C: no pid that ever showed a window is a python-family process.  ARM A
    # watches ONE pid; a console window belongs to conhost.exe, so this arm asks
    # the question by NAME over every pid the census saw.  Names come from ONE
    # `Get-Process` call, after the samples -- never a per-sample process walk.
    ever = set(other_seen) | ({child} if child_hits else set())
    if neg:
        # NEGATIVE CONTROL for ARM C, and it costs the owner no window: THIS
        # probe is itself a python process, so injecting its pid must make the
        # classifier report a python-family pid.  If ARM C still says GREEN with
        # a known python pid in the set, ARM C cannot say RED and its green
        # above was worth nothing.
        ever.add(os.getpid())
    names = resolve_names(ever)
    family = sorted(f"{p}:{n}" for p, n in names.items() if n.lower() in PYTHON_FAMILY)
    arm_c = not family
    print(f"ARM C / no-python-family-window       pids ever seen with a window={len(ever)} "
          f"named={len(names)} python-family={family or '[]'} -> {'GREEN' if arm_c else 'RED'}")
    if neg:
        print(f"NEG-ARM / ARM C goes RED on a known python pid -> "
              f"{'RED as required' if not arm_c else 'STILL GREEN -- ARM C IS BLIND'}")
        return 0 if not arm_c else 1
    named = ", ".join(f"{p}={n or '?'}" for p, n in sorted(names.items(),
                                                           key=lambda kv: -len(other_seen.get(kv[0], ()))))
    if named:
        print(f"  names: {named}")

    print(f"ARM A / child-with-CREATE_NO_WINDOW   child_visible=0 in {samples} samples -> "
          f"{'GREEN' if arm_a else 'RED'}")
    top = sorted(other_seen.items(), key=lambda kv: -len(kv[1]))[:3]
    pretty = [f"pid {p} ({len(v)} win) {json.dumps(sorted(v)[:1], ensure_ascii=False)}" for p, v in top]
    print(f"ARM B / instrument-is-not-blind       other_pid_visible>0 in "
          f"{other_samples}/{samples} samples -> {'GREEN' if arm_b else 'RED'}")
    for line in pretty:
        print(f"  seen: {line}")
    verdict = arm_a and arm_b and arm_c
    print(f"VERDICT {'PASS' if verdict else 'FAIL'} -- "
          f"child_visible=0={arm_a} instrument_not_blind={arm_b} no_python_window={arm_c}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
