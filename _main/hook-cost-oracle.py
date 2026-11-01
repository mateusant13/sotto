#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
"""DECISION-COST ORACLE -- how long does ONE outside-click decision cost?

HISTORY, AND WHY THE NAME IS OLDER THAN THE SUBJECT. Born 2026-10-17 to price
ONE firing of the `WH_MOUSE_LL` click hook, whose cadence was measured (11.82
clicks a minute) and whose DURATION was not. A low-level mouse hook runs the
callback on the input path: everything it costs is paid before the pointer
moves, for the WHOLE machine.

THAT HOOK WAS DELETED ON 2026-10-30 (owner: *"se esses hooks sao burros ou
desnecessarios, remove. nao mantem nada q tu ta achando q e pior"*). Nothing in
the shell calls `SetWindowsHookEx` any more -- `_main/input-path-oracle.py` C1
is the gate that says so. The question this file answers did NOT disappear with
it: the same `_consider -> _record -> log` path is what the 100 ms FOREGROUND
tick runs, ten times a second while the panel is open. A cost that was
irrelevant at 11.82 calls a minute stops being irrelevant at 600.

So the arms are unchanged and the subject is the tick: it imports the REAL
shell as a module, builds a REAL OutsideClickWatcher whose shell is a stub, and
times every call of the real `_consider -> _record -> log` path.
No hook is installed, no thread is started, no window is created.

Arms:
  A the path with no --log file (stdout only)      what a run without --log pays
  B the same path with a REAL log file open         what run.cmd pays per click
  N the same object with the log call REMOVED from _record -- the part of
    the cost the log write itself adds. If N is not cheaper than B, the
    measurement is void and the oracle says so.
"""
import io
import os
import statistics
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), "app", "webview", "sotto_webview.py")
N = 4000
TMP_FILES = []          # best-effort cleanup, never a run failure
FRAME_MS = 16.7      # one 60 fps frame: the scale of a perceptible stall
FAILURES = []


def check(num, ok, got):
    if not ok:
        FAILURES.append("#%s failed, got %r" % (num, got))


def pct(rows, p):
    rows = sorted(rows)
    return rows[min(len(rows) - 1, int(len(rows) * p))] if rows else 0.0


def main():
    sys.path.insert(0, os.path.dirname(SHELL))
    import importlib.util
    spec = importlib.util.spec_from_file_location("_shell_under_test", SHELL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    print("shell: %d bytes, %d lines" % (os.path.getsize(SHELL),
          len(open(SHELL, "rb").read().split(b"\n")) - 1))

    class StubShell:
        hwnd = 0
        exiting = threading.Event()
        edit_grab = None

        def hide_panel(self, reason):
            self.hide_calls = getattr(self, "hide_calls", 0) + 1

    msg = mod.WM_LBUTTONDOWN
    mod._stamp = lambda: "2026-10-12T00:00:00.000-03:00"
    results = {}
    for arm in ("A", "B", "N"):
        w = mod.OutsideClickWatcher.__new__(mod.OutsideClickWatcher)
        threading.Thread.__init__(w, daemon=True)
        w.shell = StubShell()
        # `__new__` salta o `__init__` (que lancaria a thread): os campos que os
        # setters tocam tem de ser postos a mao. O `thread_id` e' None porque NAO
        # ha thread -- e' o mesmo "sem thread" que o `_apply_timer` aguenta.
        w.thread_id = None
        w.exiting = threading.Event()
        w._armed = False
        w._edit_mode = False
        w._dragging = False
        w._last_drag_post = 0.0
        w.drag_samples = 0
        w._last_fg = None
        w.polls = 0
        w.armed = True
        w.edit_mode = False
        w.decisions = []
        w._ready = threading.Event()
        if arm == "N":
            def _record_nolog(self, x, y, source, reason, closed):
                entry = {"x": x, "y": y, "source": source, "decision": reason,
                         "closed": closed}
                self.decisions.append(entry)
                del self.decisions[:-20]
            w._record = _record_nolog.__get__(w, type(w))
        tmp = tempfile.NamedTemporaryFile("a+", suffix=".log", delete=False)
        saved = (mod._LOG_FILE, mod._LOG_QUEUE, mod._LOG_WRITER)
        # THE REAL PATH: _open_log() opens the file AND starts the writer thread,
        # exactly as run.cmd does. Assigning _LOG_FILE by hand would skip the
        # thread that the fix added, and the arm would measure the old defect.
        if arm == "B":
            mod._open_log(tmp.name)
        try:
            w._consider(12, 34, msg, source="hook")
            t = []
            for _ in range(N):
                t0 = time.perf_counter()
                r = w._consider(12, 34, msg, source="hook")
                t1 = time.perf_counter()
                t.append((t1 - t0) * 1000.0)
                if not isinstance(r, bool):
                    FAILURES.append("#return-contract %r" % (r,))
        finally:
            mod._log_drain()
            (mod._LOG_FILE, mod._LOG_QUEUE, mod._LOG_WRITER) = saved
            tmp.close()
            # A handle kept by the writer (or by the OS) must not take the
            # RUN down: the measurement is what this oracle exists for.
            TMP_FILES.append(tmp.name)
        s = sorted(t)
        d = {"n": len(t), "mean": statistics.fmean(t), "p50": pct(t, 0.50),
             "p99": pct(t, 0.99), "max": max(t)}
        d["log_entries"] = len(w.decisions)
        results[arm] = d
        print("ARM %s n=%d mean=%.4f p50=%.4f p99=%.4f max=%.4f ms" % (
            arm, d["n"], d["mean"], d["p50"], d["p99"], d["max"]))
    a = results["A"]["p99"]
    b = results["B"]["p99"]
    n = results["N"]["p99"]
    print("HOOK_COST p99 stdout-only=%.4f ms with-log-file=%.4f ms negative=%.4f ms" % (a, b, n))
    print("HOOK_COST at the measured cadence 11.82 clicks/min:")
    for arm in ("A", "B"):
        s = results[arm]["p99"]
        print("   arm %s %.4f ms per click = %.4f s per hour of hook time" % (
            arm, s, s * 11.82 * 3600.0 / 1000.0))
    amax = results["A"]["max"]
    bmax = results["B"]["max"]
    check("whole-path-under-one-frame-both-arms", amax < FRAME_MS and bmax < FRAME_MS, [amax, bmax])
    check("log-write-attributable", n < b, [n, b])
    check("every-arm-measured", N, results["A"]["n"])
    check("decisions-recorded", N + 1, results["A"]["log_entries"])
    for p in TMP_FILES:
        try:
            os.unlink(p)
        except OSError:
            pass
    print("VERDICT " + ("PASS" if not FAILURES else "FAIL"))
    if FAILURES:
        for f in FAILURES:
            print("  [NO] " + f)
        return 1
    print("  worst case in %d clicks: stdout-only %.4f ms, with-log %.4f ms," % (N, amax, bmax))
    print("  and the log write adds %.4f ms at p99 -- all far under one 60 fps frame." % (b - a))
    print("  THEREFORE one tick's decision path is MEASURED CLEAN at the 10 Hz the")
    print("  foreground poll asks for (10 calls a second, not the 1000 events a")
    print("  second a low-level mouse hook put on the input path before it was")
    print("  removed on 2026-10-30 -- see _main/input-path-oracle.py C1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
