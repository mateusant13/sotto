#!/usr/bin/env python3
"""panel-window-census -- is the SOTTO PANEL on screen? (successor of the house census)

WHY A SUCCESSOR INSTEAD OF A FIX. Audit rows #31 and #32 indict the house census --
`MainWindowHandle != 0` with no monitor test, and a predicate that is not panel-specific (it has
alarmed on `cmd`, `dwm` and plain `python`). That file lives in the parked tree
`_moved/aireplay/_main/window-census.ps1`, which this session must NOT modify, so the finding cannot
be repaired in place. What CAN be done is to build the census the rows describe, keep every test
SEPARATELY NAMED, and gate each one with its own mutant -- which is what this file is.

WHAT IT MEASURES. One window row qualifies as "the panel is on screen" only if ALL SEVEN hold:
  1. the owning process IS the app (a python/pythonw whose command line runs sotto_webview.py),
     which is the panel-specific test #32 asks for;
  2. a top-level window exists (MainWindowHandle != 0, the old census ONLY test);
  3. IsWindowVisible says so (a measured fact, not a cached intention);
  4. MonitorFromWindow(hwnd, MONITOR_DEFAULTTONULL) != 0 -- the window is on a REAL monitor: the
     test #31 says is missing;
  5. the window rect actually INTERSECTS that monitor (a window parked at -32000 is not on screen);
  6. DWM does not report it cloaked (DWMWA_CLOAKED == 0);
  7. if it is layered, its alpha is not 0 -- the invisible creation dance that this repo measured
     as a `WS_VISIBLE` window nobody can see.

BOTH COLOURS, SEVEN MUTANTS. The predicate is a PURE function over a row, so the arms are synthetic
and need no launch: one good row plus one bad row per test. `--neg-arm` writes a copy of THIS file
into a scratch dir with one test removed at a time and requires exactly the matching arm to flip
while the others stay put -- a test that no arm can see is not a test.

LAUNCHES NOTHING. `--sample` reads the process table and enumerates windows (passive); the owner
order forbids opening the app, and nothing here does.
"""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from ctypes import wintypes

#: The app, by the artifact it runs -- never by a bare word: a kill/select filter that matches
#: "sotto" once killed unrelated processes on this box (AGENTS.md), and the same discipline applies
#: to a SELECTION filter.
APP_ARTIFACT = "sotto_webview.py"
HOST_EXES = ("python.exe", "pythonw.exe")


def qualifies(row):
    """One row -> is this the SOTTO PANEL, on a real monitor, actually paintable?"""
    if not row.get("is_app"):                        # TEST 1  panel-specific (#32)
        return False
    if not row.get("hwnd"):                          # TEST 2  a top-level window exists
        return False
    if not row.get("visible"):                       # TEST 3  IsWindowVisible (measured)
        return False
    if not row.get("on_monitor"):                    # TEST 4  MonitorFromWindow != NULL (#31)
        return False
    if not row.get("rect_intersects_monitor"):       # TEST 5  the rect is really over it
        return False
    if row.get("cloaked"):                           # TEST 6  DWM cloaked
        return False
    if row.get("layered") and row.get("alpha", 255) == 0:   # TEST 7  the alpha=0 dance
        return False
    return True


#: Tests in file order: (arm name, the test line this arm would notice if it were removed).
TESTS = (
    ("t1-not-app", "if not row.get(" + chr(34) + "is_app" + chr(34) + "):"),
    ("t2-no-hwnd", "if not row.get(" + chr(34) + "hwnd" + chr(34) + "):"),
    ("t3-hidden", "if not row.get(" + chr(34) + "visible" + chr(34) + "):"),
    ("t4-off-monitor", "if not row.get(" + chr(34) + "on_monitor" + chr(34) + "):"),
    ("t5-rect-outside", "if not row.get(" + chr(34) + "rect_intersects_monitor" + chr(34) + "):"),
    ("t6-cloaked", "if row.get(" + chr(34) + "cloaked" + chr(34) + "):"),
    ("t7-alpha-zero", "if row.get(" + chr(34) + "layered" + chr(34) + ") and row.get("
     + chr(34) + "alpha" + chr(34) + ", 255) == 0:"),
)

GOOD = {"name": "panel", "is_app": True, "hwnd": 501, "visible": True, "on_monitor": True,
        "rect_intersects_monitor": True, "cloaked": False, "layered": False, "alpha": 255}

#: (arm, row override, expected verdict). The first is the positive control: a row that must
#: QUALIFY, so an arm that only ever says NO cannot pass this suite.
ARMS = (
    ("control-good-panel", {}, True),
    ("t1-not-app", {"name": "cmd.exe", "is_app": False}, False),
    ("t2-no-hwnd", {"hwnd": 0}, False),
    ("t3-hidden", {"visible": False}, False),
    ("t4-off-monitor", {"on_monitor": False}, False),
    ("t5-rect-outside", {"rect_intersects_monitor": False}, False),
    ("t6-cloaked", {"cloaked": True}, False),
    ("t7-alpha-zero", {"layered": True, "alpha": 0}, False),
)


def run_arms(predicate):
    out = {}
    for name, override, expected in ARMS:
        row = dict(GOOD)
        row.update(override)
        got = bool(predicate(row))
        out[name] = {"expected": expected, "got": got, "ok": got == expected}
    return out


def verdict_of(arms):
    bad = [name for name, item in arms.items() if not item["ok"]]
    return bad


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- the real sampler (passive: process table + window enumeration) ----------
def window_rows():
    """Every top-level window with the seven facts the predicate needs."""
    import psutil

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    except OSError:
        dwmapi = None

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                    ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]

    rows = []

    def pid_facts(pid):
        try:
            proc = psutil.Process(pid)
            name = (proc.name() or "").lower()
            cmdline = " ".join(proc.cmdline() or [])
        except Exception:
            return (None, "")
        return (name, cmdline)

    def intersects(rect, monitor_rect):
        return not (rect.right <= monitor_rect.left or rect.left >= monitor_rect.right
                    or rect.bottom <= monitor_rect.top or rect.top >= monitor_rect.bottom)

    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name, cmdline = pid_facts(pid.value)
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        hmon = user32.MonitorFromWindow(hwnd, 0)      # MONITOR_DEFAULTTONULL
        monitor_rect = RECT()
        if hmon:
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                monitor_rect = info.rcMonitor
        cloaked = False
        if dwmapi is not None:
            value = ctypes.c_int(0)
            if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(value),
                                            ctypes.sizeof(value)) == 0:
                cloaked = value.value != 0
        alpha = ctypes.c_ubyte(0)
        key = ctypes.c_ulong(0)
        flags = ctypes.c_ulong(0)
        layered = bool(user32.GetLayeredWindowAttributes(
            hwnd, ctypes.byref(key), ctypes.byref(alpha), ctypes.byref(flags)))
        rows.append({
            "hwnd": int(hwnd), "pid": int(pid.value), "name": name,
            "cmdline_tail": cmdline[-90:],
            "is_app": bool(name in HOST_EXES and APP_ARTIFACT in cmdline),
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "on_monitor": bool(hmon),
            "rect_intersects_monitor": bool(hmon) and intersects(rect, monitor_rect),
            "rect": [rect.left, rect.top, rect.right, rect.bottom],
            "cloaked": cloaked,
            "layered": layered,
            "alpha": int(alpha.value),
        })
        return True

    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(
        callback), 0)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sample", action="store_true",
                        help="also read the LIVE desktop (passive; launches nothing)")
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("panel-window-census -- seven named tests, one mutant each (launches NOTHING)")

    live = run_arms(qualifies)
    for name, item in live.items():
        say("  live  " + name.ljust(22) + ("ok" if item["ok"] else "WRONG")
            + "  expected=" + str(item["expected"]) + " got=" + str(item["got"]))
    bad = verdict_of(live)

    if parsed.neg_arm:
        scratch = tempfile.mkdtemp(prefix="sotto-census-neg-")
        source = open(os.path.abspath(__file__), encoding="utf-8").read()
        wrong = []
        if bad:
            wrong.append("control: " + str(bad))
        for arm, test_line in TESTS:
            # THE WHOLE TEST GOES -- the condition AND the body line under it. Removing the
            # condition alone leaves an indented `return False` behind and every mutant dies of
            # IndentationError (measured twice, 2026-10-11: first the replacement added its own
            # indent, then it left the orphan body). A line-wise delete keeps the file valid and
            # removes exactly one test.
            lines = source.split("\n")
            index = None
            for position, line in enumerate(lines):
                if test_line in line:
                    index = position
                    break
            if index is None or "return False" not in lines[index + 1]:
                say("SETUP ERROR: " + arm + " is not where this file documents it (line or body)")
                return 2
            del lines[index:index + 2]
            path = os.path.join(scratch, arm + ".py")
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("\n".join(lines))
            mut = run_arms(load_module(path, "census_" + arm.replace("-", "_")).qualifies)
            moved = sorted(name for name, item in mut.items()
                           if item["ok"] != live[name]["ok"])
            say("  mut   " + arm.ljust(22) + "flipped=" + str(moved))
            if moved != [arm]:
                wrong.append(arm + " flipped " + str(moved))
        say("")
        say("NEG-ARM: each removed test must flip EXACTLY its own arm; wrong: " + str(wrong))
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL"))
        return 0 if not wrong else 1

    if parsed.sample:
        rows = window_rows()
        panels = [row for row in rows if qualifies(row)]
        say("")
        say("  sampled windows      " + str(len(rows)))
        say("  qualifying panels    " + str(len(panels)))
        for row in panels[:6]:
            say("    " + json.dumps({k: row[k] for k in (
                "hwnd", "pid", "name", "rect", "alpha", "layered", "cloaked")}))

    say("")
    say("VERDICT: " + ("PASS" if not bad else "FAIL") + " -- " + str(len(ARMS))
        + " synthetic row(s), " + str(len(ARMS) - 1) + " of them BAD in exactly one named way; "
        "tests=" + str(len(TESTS)) + (" (all arms as declared)" if not bad else str(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())