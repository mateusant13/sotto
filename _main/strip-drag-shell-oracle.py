#!/usr/bin/env python3
"""The SHELL half of the strip drag, driven directly. Nothing launched.

The drag has three halves. The PAGE half needs a real gesture -- synthetic pointer
events do not reach the handler, measured over several rounds. The BRIDGE half is
proven for other kinds (RECEIVER_READY reaches the shell). THE SHELL HALF can be
driven directly: _set_strip_offset computes a position and calls SetWindowPos, and
both are observable on a fake object with a stubbed user32.

This is the half that MOVES THE WINDOW, so it is the one worth proving.
"""
import argparse
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
WORK = {"x": 0, "y": 0, "width": 1920, "height": 1080}
BASE = (770, 872)
WIDTH = 380
HEIGHT = 40
RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), str(detail)))
    print(("  ok   " if ok else "  FAIL ") + label + ("  -- " + str(detail) if detail else ""))


def load(path, name):
    here = os.path.dirname(os.path.abspath(path))
    if here not in sys.path:
        sys.path.insert(0, here)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeUser32(object):
    def __init__(self):
        self.calls = []

    def SetWindowPos(self, hwnd, after, x, y, cx, cy, flags):
        self.calls.append((hwnd, after, x, y, cx, cy, flags))
        return True


class FakeShell(object):
    def __init__(self):
        self.surface_applied = "strip"
        self.hwnd = 1234
        self._strip_dock_base = BASE
        self.geometry = {"x": BASE[0], "y": BASE[1], "width": WIDTH,
                         "height": HEIGHT, "docked": "bottom-strip"}
        self.display = {"scaleFactor": 1.0}
        self.logged = []

    def work_area(self):
        return dict(WORK)

    def geometry_snapshot(self):
        return dict(self.geometry)

    def publish_panel_visibility(self, reason):
        self.logged.append(("publish", reason))

    def exec_js(self, script):
        # NOT TRUNCATED. It was [:60] and that cut the script BEFORE the very
        # string the check looks for, so the check failed while the call was
        # correct -- the second time in this one file that a stub hid its own
        # evidence.
        self.logged.append(("exec_js", str(script)))
        return True


def run(sw, tag, u32):
    sw.user32 = u32
    f = FakeShell()
    u32.calls = []
    sw.SottoShell._set_strip_offset(f, {"x": 60, "y": 30, "phase": "move"})
    moved = u32.calls[-1] if u32.calls else None
    check(tag + "the drag calls SetWindowPos", moved is not None, str(moved))
    if moved:
        check(tag + "and moves by exactly the offset, base plus 60,30",
              (moved[2], moved[3]) == (830, 902),
              "x=%s y=%s want=(830, 902)" % (moved[2], moved[3]))
        check(tag + "and does NOT resize", bool(moved[6] & 1), "flags=%s" % moved[6])
    # THE SCRIPT TEXT, NOT THE TAG. The first version searched str(tuple) for a
    # string that lives in the SECOND half and reported FAIL while the log showed
    # [exec_js] -- the call was happening all along and the check read the wrong
    # part. Fixing the check, not the code, is the right move only because the
    # evidence said the call WAS made.
    execs = [e[1] for e in f.logged if e[0] == "exec_js"]
    check(tag + "and tells the page the window moved",
          any("data-strip-moved" in s for s in execs), str(execs)[:80])
    check(tag + "and the geometry carries the new position",
          (f.geometry.get("x"), f.geometry.get("y")) == (830, 902),
          "%s,%s" % (f.geometry.get("x"), f.geometry.get("y")))
    f2 = FakeShell()
    u32.calls = []
    sw.SottoShell._set_strip_offset(f2, {"x": 99999, "y": 99999, "phase": "move"})
    m2 = u32.calls[-1] if u32.calls else None
    check(tag + "an absurd offset is CLAMPED into the work area",
          m2 is not None and m2[2] + WIDTH <= 1920 and m2[3] + HEIGHT <= 1080, str(m2))
    f3 = FakeShell()
    f3.surface_applied = "panel"
    u32.calls = []
    sw.SottoShell._set_strip_offset(f3, {"x": 60, "y": 30, "phase": "move"})
    check(tag + "and it REFUSES when the surface is not strip", not u32.calls,
          "calls=%d" % len(u32.calls))


ANCHOR = "        nx = max(work['x'], min(base[0] + dx, work['x'] + work['width'] - width))"
MUTANT = "        nx = base[0] + dx  # mutant: no clamp"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args()
    sw = load(SHELL, "sotto_shell_drag_live")
    print("live shell %s  (%d B)" % (SHELL, os.path.getsize(SHELL)))
    print("-- control: the shipped _set_strip_offset --")
    run(sw, "", FakeUser32())
    control = list(RESULTS)
    if args.neg_arm:
        import shutil
        import tempfile
        print("-- neg-arm: the CLAMP removed in a COPY --")
        tmp = tempfile.mkdtemp(prefix="sotto-drag-")
        try:
            src = open(SHELL, encoding="utf-8").read()
            if ANCHOR not in src:
                check("neg-arm anchor found", False, "anchor missing, mutant would be INERT")
            else:
                p = os.path.join(tmp, "mut.py")
                open(p, "w", encoding="utf-8").write(src.replace(ANCHOR, MUTANT, 1))
                m = load(p, "sotto_shell_drag_mut")
                before = len(RESULTS)
                run(m, "  mutant: ", FakeUser32())
                red = [r for r in RESULTS[before:] if not r[1]]
                check("neg-arm the missing clamp goes RED",
                      any("CLAMPED" in r[0] for r in red),
                      "red=%s" % [r[0].strip()[:50] for r in red])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    cf = [r for r in control if not r[1]]
    if args.neg_arm:
        rc = [r for r in RESULTS if r[0].startswith("neg-arm ")]
        failed = cf + [r for r in rc if not r[1]]
        total = len(control) + len(rc)
    else:
        failed, total = cf, len(control)
    print("")
    print("VERDICT: %s -- %d check(s), %d fail"
          % ("PASS" if not failed else "FAIL", total, len(failed)))
    for r in failed:
        print("   FAILED: " + r[0] + "  -- " + r[2])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())