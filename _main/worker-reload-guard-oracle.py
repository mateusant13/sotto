# worker-reload-guard-oracle.py -- does the held worker reload know the
# difference between a worker that is TRANSCRIBING and one that merely has a
# stream open?
#
# THE DEFECT THIS MEASURES. WorkerReloadPolicy holds a worker reload while
# is_capturing() is true, and its only exits are a closed-line boundary or the
# ceiling. is_capturing() is ONE flag for TWO different workers. On this box the
# measured normal is a tap that is OPEN and delivering nothing (nothing routed),
# so no closed line ever arrives, the guard defers at every check, and the
# ceiling then FORCES the reload anyway. MEASURED in the owner's own log:
#   HOT_RELOAD_WORKER_DEFERRED ... waited_ms=2014 max_defer_ms=25000
#   HOT_RELOAD_WORKER_FORCED   ... reason=no-boundary-in-25000ms waited_ms=32046
#   BRIDGE_STOP reason=hot-reload pid=11584 -> BRIDGE_EXIT rc=1 captions=4940
# The deferral bought nothing and cost a 32 s stall of the capture pipeline plus
# a model warm-up -- and the ceiling is only OBSERVED at the 10 s re-check, so
# "25000" was really 32046.
#
# Run: py -3 _main/worker-reload-guard-oracle.py
#      py -3 _main/worker-reload-guard-oracle.py --neg-arm   (must go RED)
import importlib.util
import inspect
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
# The shell imports its own sibling (`import hot_reload`), so the directory
# the file lives in has to be importable before we exec it.
sys.path.insert(0, os.path.join(ROOT, "app", "webview"))
TMP = os.environ.get("TMPDIR") or "I:\\cc-tmp"

FAILURES = []
CHECKS = [0]


def check(num, ok, got):
    CHECKS[0] += 1
    if not ok:
        FAILURES.append(num)
    print("  [%s] %-2s %s" % ("PASS" if ok else "FAIL", num, got))


def load_shell(path):
    spec = importlib.util.spec_from_file_location("shell_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["shell_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def broken_copy():
    """The PRE-FIX policy, restored in a COPY. This is the arm that must go RED."""
    src = open(SHELL, "r", encoding="utf-8", newline="").read()
    # (1) the guard condition: drop the second fact again, so ONE flag answers
    #     both "transcribing" and "merely capturing".
    new_cond = "if capturing and not boundary and not forced and transcribing:"
    old_cond = "if capturing and not boundary and not forced:"
    if new_cond not in src:
        return None, "anchor(1) not found -- the fix is not in the file"
    src = src.replace(new_cond, old_cond)
    # (2) the ceiling: arm the full re-check again, so 25000 really means 32046.
    new_arm = ("            self._arm(min(self.defer_recheck_ms," + "\r\n"
               "                          max(0, self.max_defer_ms - waited_ms)))")
    old_arm = "            self._arm(self.defer_recheck_ms)"
    if new_arm not in src:
        return None, "anchor(2) not found -- the fix is not in the file"
    src = src.replace(new_arm, old_arm)
    dst = os.path.join(TMP, "_neg_worker_reload_shell.py")
    os.makedirs(TMP, exist_ok=True)
    open(dst, "w", encoding="utf-8", newline="").write(src)
    return dst, None


class Bridge(object):
    """The two facts, as a stand-in the REAL policy reads."""

    def __init__(self, capturing, idle_ms, captions=1, has_clock=True):
        self.has_clock = bool(has_clock)
        self.capturing = bool(capturing)
        self.child = object()          # a live child, so the respawn shortcut is off
        self.spawned_at = 0.0
        self.worker_path = WORKER
        self.loaded_sha256 = "0" * 64
        self.captions = captions
        self.last_caption_at = (0.0 if idle_ms is None
                                else time.monotonic() - idle_ms / 1000.0)
        if not self.has_clock:
            # EXACTLY the shape of the shell's own StandInBridge: the surface the
            # policy reads, and no clock. The guard must read "cannot report" as
            # "in flight", because its failure mode is never a restart.
            del self.last_caption_at

    def is_capturing(self):
        return self.capturing


def run(shell, capturing, idle_ms, boundary, waited_ms, floor_clear=True,
        captions=1):
    """Drive the REAL _fire once and report what it DECIDED."""
    br = Bridge(capturing, idle_ms, captions)
    seen = {"restart": 0, "arm": None, "logs": []}
    pol = shell.WorkerReloadPolicy(
        log_fn=lambda m: seen["logs"].append(m),
        get_bridge=lambda: br,
        restart=lambda files: seen.__setitem__("restart", seen["restart"] + 1),
    )
    pol.pending = [WORKER]
    pol.pending_since = time.monotonic() - waited_ms / 1000.0
    pol._boundary_hit = bool(boundary)
    # 1000 s ago clears the 180 s floor and stays POSITIVE: on Windows
    # time.monotonic() is uptime-based, so `now - 1e6` can be negative and the
    # policy then resets it to now -- which silently re-arms the floor.
    pol._last_applied_at = ((time.monotonic() - 1000.0) if floor_clear
                            else time.monotonic())
    pol._arm = lambda ms: seen.__setitem__("arm", int(ms))
    pol._fire()
    kinds = []
    for m in seen["logs"]:
        for k in ("DEFERRED", "FORCED", "COOLDOWN", "BOUNDARY_APPLIED",
                  "APPLIED_AT_BOUNDARY", "IDLE_APPLIED", "SKIPPED", "RESTART"):
            if k in m:
                kinds.append(k)
    seen["kinds"] = kinds
    seen["kind"] = kinds[-1] if kinds else "none"
    return seen


def main():
    neg = "--neg-arm" in sys.argv
    path = SHELL
    if neg:
        path, why = broken_copy()
        if path is None:
            print("NEG-ARM IMPOSSIBLE: %s" % why)
            return 1
    shell = load_shell(path)
    print("shell: %d bytes%s" % (os.path.getsize(path),
                                 "  (NEG-ARM: the pre-fix policy, in a copy)" if neg else ""))
    fn = shell.WorkerReloadPolicy._fire
    print("policy: WorkerReloadPolicy._fire%s" % (inspect.signature(fn),))
    print("constants: max_defer=%s recheck=%s floor=%s" % (
        shell.WORKER_RELOAD_MAX_DEFER_MS, shell.WORKER_RELOAD_DEFER_RECHECK_MS,
        shell.WORKER_RELOAD_MIN_INTERVAL_MS))
    print("")

    print("-- ARM 1-4: the two facts must NOT share one flag ---------------")
    # ARM 1 -- THE DEFECT. Capturing, but no caption for 60 s: nothing is in
    # flight, so a reload cuts nothing and must NOT wait out the ceiling.
    r = run(shell, True, 60_000, False, 2_000)
    check(1, r["restart"] == 1 and "DEFERRED" not in r["kinds"],
          "1 open stream, NO caption for 60s -> apply now            "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))
    # ARM 2 -- the fact the guard EXISTS for. Transcribing: a caption 1 s ago.
    r = run(shell, True, 1_000, False, 2_000)
    check(2, r["restart"] == 0 and "DEFERRED" in r["kinds"],
          "2 TRANSCRIBING, caption 1s ago -> hold for a boundary     "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))
    # ARM 3 -- never captioned at all.
    r = run(shell, True, None, False, 2_000, captions=0)
    check(3, r["restart"] == 1 and "DEFERRED" not in r["kinds"],
          "3 open stream, NEVER captioned -> apply now              "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))
    # ARM 4 -- a closed line is still the boundary that wins.
    r = run(shell, True, 1_000, True, 2_000)
    check(4, r["restart"] == 1 and "BOUNDARY_APPLIED" in r["kinds"],
          "4 closed-line boundary -> applies at the boundary        "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))

    print("")
    print("-- ARM 5-7: the ceiling must be a DEADLINE, not a hint ----------")
    # ARM 5 -- the measured overshoot. waited 22014 of a 25000 ceiling: the
    # re-arm must be the REMAINDER (2986), never the full 10000 re-check.
    r = run(shell, True, 1_000, False, 22_014)
    check(5, r["arm"] is not None and r["arm"] <= 3_000,
          "5 waited 22014/25000, transcribing -> re-arm the REMAINDER  "
          "arm_ms=%s (old code armed 10000 -> realised 32046)" % (r["arm"],))
    # ARM 6 -- early in the wait the re-check is still the re-check.
    r = run(shell, True, 1_000, False, 2_014)
    check(6, r["arm"] == shell.WORKER_RELOAD_DEFER_RECHECK_MS,
          "6 waited 2014/25000 -> full re-check                     arm_ms=%s"
          % (r["arm"],))
    # ARM 7 -- the ceiling itself still forces a TRANSCRIBING worker.
    r = run(shell, True, 1_000, False, 32_046)
    check(7, r["restart"] == 1 and "FORCED" in r["kinds"],
          "7 waited 32046 >= ceiling, transcribing -> FORCED        "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))

    print("")
    print("")
    print("-- ARM 10: a bridge with NO caption clock is HELD (fail-safe) ----")
    # The shell's OWN selftest drives WorkerReloadPolicy with a StandInBridge that
    # carries no last_caption_at, and asserts restarts_during_capture == 0. That
    # arm is reached only through --selftest, which LAUNCHES the app, so it cannot
    # be run from here; this arm reproduces its exact contract in process instead.
    br = Bridge(True, 60_000, 1, has_clock=False)
    seen = {"restart": 0, "logs": []}
    pol = shell.WorkerReloadPolicy(
        log_fn=lambda m: seen["logs"].append(m),
        get_bridge=lambda: br,
        restart=lambda files: seen.__setitem__("restart", seen["restart"] + 1))
    pol.pending = [WORKER]
    pol.pending_since = time.monotonic() - 0.2
    pol._boundary_hit = False
    pol._last_applied_at = time.monotonic() - 1000.0
    pol._arm = lambda ms: None
    pol._fire()
    kinds = [k for m in seen["logs"]
             for k in ("DEFERRED", "FORCED", "COOLDOWN", "IDLE_APPLIED", "RESTART")
             if k in m]
    check(10, seen["restart"] == 0 and "DEFERRED" in kinds,
          "10 StandInBridge shape (no clock) -> HOLD, never a restart "
          "kinds=%-14s restart=%d" % (",".join(kinds) or "none", seen["restart"]))

    print("-- ARM 8-9: the invariants that must NOT move ------------------")
    # ARM 8 -- the RATE floor still bounds a reload.
    r = run(shell, True, 60_000, False, 2_000, floor_clear=False)
    check(8, r["restart"] == 0 and "COOLDOWN" in r["kinds"],
          "8 floor not elapsed -> COOLDOWN, never a restart         "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))
    # ARM 9 -- a worker that is NOT capturing is never held.
    r = run(shell, False, 1_000, False, 2_000)
    check(9, r["restart"] == 1 and "DEFERRED" not in r["kinds"],
          "9 not capturing -> apply now                             "
          "kind=%-16s restart=%d" % (r["kind"], r["restart"]))

    print("")
    print("-- VERDICT ------------------------------------------------------")
    if neg:
        print("  NEG-ARM: the restored pre-fix policy must be RED on arm 1 and 3.")
        print("  failures: %d (must be > 0)" % len(FAILURES))
        if FAILURES:
            print("  RED -- arm(s) %s" % ", ".join(str(f) for f in FAILURES))
            return 0
        print("  THE NEG-ARM PASSED -- this oracle cannot say NO.")
        return 1
    if FAILURES:
        print("  failures: %d" % len(FAILURES))
        print("  RED -- %s" % "; ".join("arm %s" % f for f in FAILURES))
        return 1
    print("  failures: 0  (%d checks)" % CHECKS[0])
    print("  PASS -- the held reload tells TRANSCRIBING from merely CAPTURING,")
    print("          and the ceiling is a deadline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
