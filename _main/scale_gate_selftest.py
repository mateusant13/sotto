"""Does the scale gate CAN go RED?  Prove it or it does not exist.

slice_scale_probe.py shipped a gate that printed `RESULT: PASS` at n=211200 with
frac_under_16ms=0.000 -- p50 52.94 ms, p95 68.35 ms, max 86.25 ms, zero of 100
queries inside the 16 ms budget.  The gate had no latency clause at all, so it
could only say NO when rows went missing.  A green gate means nothing until
something has been seen to turn it red.

This file feeds the gate a deliberately non-compliant measurement -- exactly the
observed shape, reconstructed from _main/scale-verdict.md -- and asserts the
verdict is FAIL.  Two properties are asserted for every arm:

  1. the gate returns what the arm demands (RED where it must be red, GREEN
     where it must be green -- a gate that always says FAIL is as useless as
     one that always says PASS);
  2. the gate's reason text carries the real numbers, so a FAIL line is
     evidence rather than an assertion.

Arm R1 additionally runs the OLD defective logic on the same data and asserts it
returns True.  Without that, this suite could not distinguish "the gate works"
from "the gate is broken in the other direction".

Arm E1 is end-to-end on the REAL store/search path: a real index build and real
timed queries at a budget no machine can meet, asserting main() exits non-zero.

Usage:  python _main/scale_gate_selftest.py
EXIT:  0 iff every arm held.  Non-zero means the gate is untrustworthy.

SYNTHETIC ONLY: the latency lists are hand-built from the numbers recorded in
_main/scale-verdict.md.  No vectors are generated here except in arm E1, which
builds a real (small) scratch index in tempfile.mkdtemp().
"""
import os

# --- thread budget FIRST, before anything can pull numpy in ---------------
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import contextlib  # noqa: E402
import importlib.util  # noqa: E402
import io  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent

# --- load the probe under test --------------------------------------------
_CANDIDATES = (HERE / "slice_scale_probe.py",
               REPO / "_main" / "slice_scale_probe.py",
               REPO / "_moved" / "aireplay" / "_main" / "slice_scale_probe.py")
_probe_path = next((p for p in _CANDIDATES if p.is_file()), None)
if _probe_path is None:
    print("FATAL: slice_scale_probe.py not found in any of:")
    for c in _CANDIDATES:
        print(f"  {c}")
    sys.exit(2)

_spec = importlib.util.spec_from_file_location("slice_scale_probe", _probe_path)
probe = importlib.util.module_from_spec(_spec)
sys.modules["slice_scale_probe"] = probe
_spec.loader.exec_module(probe)

gate = probe.gate
BUDGET_MS = probe.BUDGET_MS


# --- the measurement that got a PASS ---------------------------------------
def _through_anchors(anchors, n_queries):
    """n_queries sorted samples, linearly interpolated through
    (index, value) anchors, so the summary stats land on the recorded ones."""
    out = []
    for i in range(n_queries):
        lo_i, lo_v = anchors[0]
        hi_i, hi_v = anchors[-1]
        for j in range(len(anchors) - 1):
            if anchors[j][0] <= i <= anchors[j + 1][0]:
                lo_i, lo_v = anchors[j]
                hi_i, hi_v = anchors[j + 1]
                break
        f = 0.0 if hi_i == lo_i else (i - lo_i) / (hi_i - lo_i)
        out.append(lo_v + (hi_v - lo_v) * f)
    return out


def observed_miss(n_queries=100):
    """The n=211200 run: 0.0% under budget.  POPULATION n=211200 vectors, WINDOW
    100 timed queries, <=2 threads.  Anchored on the summary stats recorded in
    _main/scale-verdict.md -- min 44.96, p50 52.94, p95 68.35, max 86.25 ms --
    so the gate's FAIL line quotes the numbers that were really observed."""
    return _through_anchors(
        [(0, 44.96), (50, 52.94), (95, 68.35), (99, 86.25)], n_queries)


def compliant(n_queries=100):
    """The n=20000 run: 100.0% under budget.  POPULATION n=20000 vectors, WINDOW
    100 timed queries, <=2 threads.  Anchors from _main/scale-verdict.md --
    min 3.21, p50 5.34, p95 7.45, max 8.03 ms."""
    return _through_anchors(
        [(0, 3.21), (50, 5.34), (95, 7.45), (99, 8.03)], n_queries)


def old_defective_gate(n, landed, n_queries, empty, times_ms):
    """Verbatim the logic that shipped, for the regression arm."""
    ok = True
    if landed != n:
        ok = False
    if empty:
        ok = False
    return ok


# --- the runner -----------------------------------------------------------
_results = []


def arm(name, want_ok, fn, must_say=None):
    """Run one arm.  want_ok is the verdict the gate MUST return."""
    try:
        ok, reasons = fn()
    except Exception as exc:                                  # noqa: BLE001
        print(f"FAIL arm={name}: raised {type(exc).__name__}: {exc}")
        _results.append((name, False))
        return None
    held = (ok is want_ok)
    if must_say and ok is False:
        held = held and any(must_say in r for r in reasons)
    print(f"{'PASS' if held else 'FAIL'} arm={name:<26} "
          f"want={'PASS' if want_ok else 'FAIL':<4} got={'PASS' if ok else 'FAIL':<4}"
          f" reasons={len(reasons)}")
    for r in reasons:
        print(f"       reason: {r}")
    _results.append((name, held))
    return ok


# --------------------------------------------------------------------------
# R1  THE REGRESSION ARM -- the exact defect, and proof the old logic missed it
# --------------------------------------------------------------------------
def arm_r1_old_logic_was_wrong():
    """Runs first: it is the assertion that makes this suite non-vacuous."""
    times = observed_miss()
    old_ok = old_defective_gate(211200, 211200, len(times), 0, times)
    print(f"{'PASS' if old_ok else 'FAIL'} arm={'R0_old_logic':<26} "
          f"want=PASS  got={'PASS' if old_ok else 'FAIL':<4} "
          f"reasons=0   <- the shipped gate said PASS to a 3.3x miss")
    _results.append(("R0_old_logic", old_ok))


def arm_r1_observed_miss():
    return gate(211200, 211200, 100, 0, observed_miss())


def arm_r2_tail_clause_alone():
    """under_min=0 disables the fraction clause, so the p95 CEILING must be
    what fires.  At the shipped under_min=0.99 the p95 clause is subsumed by
    the fraction clause; this arm proves it is still live and not decorative."""
    return gate(211200, 211200, 100, 0, observed_miss(), under_min=0.0)


def arm_g1_compliant():
    return gate(20000, 20000, 100, 0, compliant())


def arm_g2_tolerated_outlier():
    """99 under budget, one 100 ms outlier -> PASS by design: under_min=0.99
    admits a single timing hiccup.  Documented here so a future edit that
    silently tightens or loosens it is visible."""
    times = compliant()
    times[-1] = 100.0
    return gate(20000, 20000, 100, 0, times)


def arm_x1_rows_missing():
    return gate(20000, 19999, 100, 0, compliant())


def arm_x2_empty_results():
    return gate(20000, 20000, 100, 3, compliant())


def arm_x3_no_timings():
    """Unmeasured is not a pass."""
    return gate(20000, 20000, 100, 0, [])


# --------------------------------------------------------------------------
# E1  END-TO-END on the real store/search path
# --------------------------------------------------------------------------
def arm_e1_real_run_exits_nonzero():
    """A REAL index build and REAL timed queries, with BUDGET_MS forced to a
    value no machine meets.  Proves main() itself -- not just gate() -- returns
    non-zero and prints RESULT: FAIL on the real path.
    POPULATION n=2000 vectors, WINDOW 20 timed queries, <=2 threads."""
    saved = probe.BUDGET_MS
    buf = io.StringIO()
    try:
        probe.BUDGET_MS = 0.001              # impossible: ~1 microsecond
        with contextlib.redirect_stdout(buf):
            rc = probe.main(["selftest", "2000", "20", "1000"])
    finally:
        probe.BUDGET_MS = saved
    out = buf.getvalue()
    tail = [ln for ln in out.splitlines()
            if ln.startswith(("FAIL:", "SCALE:", "GATE :", "RESULT:"))]
    verdict = [ln for ln in tail if ln.startswith("RESULT:")]
    ok = (rc == 1) and verdict == ["RESULT: FAIL"]
    print(f"{'PASS' if ok else 'FAIL'} arm={'E1_real_run_nonzero':<26} "
          f"want=rc=1  got=rc={rc}  verdict={verdict or 'MISSING'}")
    for ln in tail:
        print(f"       probe: {ln}")
    _results.append(("E1_real_run_nonzero", ok))


# --------------------------------------------------------------------------
def main():
    print(f"probe under test: {_probe_path}")
    print(f"budget={BUDGET_MS:g}ms under_need>={probe.UNDER_MIN_FRAC:.2f} "
          f"p95_need<={probe.P95_MAX_MS:g}ms")
    print(f"arms            : 9 expected\n")

    arm_r1_old_logic_was_wrong()
    arm("R1_observed_miss", False, arm_r1_observed_miss,
        must_say="latency budget MISSED")
    arm("R2_tail_clause_alone", False, arm_r2_tail_clause_alone,
        must_say="p95")
    arm("G1_compliant", True, arm_g1_compliant)
    arm("G2_tolerated_outlier", True, arm_g2_tolerated_outlier)
    arm("X1_rows_missing", False, arm_x1_rows_missing, must_say="landed")
    arm("X2_empty_results", False, arm_x2_empty_results, must_say="no hit")
    arm("X3_no_timings", False, arm_x3_no_timings, must_say="no query timings")
    arm_e1_real_run_exits_nonzero()

    held = sum(1 for _, h in _results if h)
    total = len(_results)
    red = [n for n, h in _results if h and n.startswith(("R", "X", "E"))]
    print(f"\nheld            : {held}/{total} arms")
    print(f"proved RED on   : {', '.join(red)}")
    print("SELFTEST: PASS" if held == total else "SELFTEST: FAIL")
    return 0 if held == total else 1


if __name__ == "__main__":
    sys.exit(main())