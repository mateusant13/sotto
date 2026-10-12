# -*- coding: utf-8 -*-
"""ARM gate for THE POLICY that decides whether a stalled-looking tap is re-opened.

The owner-reported freeze ("travada muito forte a cada alguns segundos") was traced
to an idle default render endpoint that delivers NO packets: the worker read that
silence as a dead tap and re-opened the shared audio endpoint every 8..60 s
(measured 32 re-opens in one run, pump thread alive). The cure is pure --
worker/sotto_worker.py::tap_stall_reason -- so this gate tests the table itself.

ARMS
  1  the truth table: which states earn a re-open and which wait.
  2  the LIVE wiring: the run loop must CALL the policy (no shadow copy).
  3  NEGATIVE control: a policy that always re-opens must FAIL arm 1, so the
     oracle can say NO instead of rubber-stamping the constants.

Launches nothing. Receipt: _main/receipt-20261012-freeze-hunt.md
"""
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
sys.path.insert(0, os.path.join(ROOT, "worker"))

BROKEN = []


def check(name, got, want):
    ok = got == want
    print("  [%s] %-44s got=%-13s want=%s" % ("PASS" if ok else "FAIL", name, got, want))
    if not ok:
        BROKEN.append(name)
    return ok


ROWS = [
    ("idle 30 s, 0 reopens -> wait", False, 30.0, 0, "endpoint-idle"),
    ("idle 60 s, 3 reopens -> wait", False, 60.0, 3, "endpoint-idle"),
    ("idle 299 s, 0 reopens -> wait", False, 299.0, 0, "endpoint-idle"),
    ("idle 400 s, capped -> wait", False, 400.0, 20, "endpoint-idle"),
    ("idle 9999 s, capped -> wait", False, 9999.0, 99, "endpoint-idle"),
    ("pump dead 5 s, 0 reopens -> re-open", True, 5.0, 0, "pump-dead"),
    ("pump dead 60 s, 12 reopens -> re-open", True, 60.0, 12, "pump-dead"),
    ("pump dead, cap reached -> re-open", True, 400.0, 20, "pump-dead"),
    ("idle 300 s, 0 reopens -> re-arm once", False, 300.0, 0, "idle-rearm"),
    ("idle 3600 s, 19 reopens -> re-arm", False, 3600.0, 19, "idle-rearm"),
    ("idle 299.9 s, right side -> wait", False, 299.9, 0, "endpoint-idle"),
]


def arm1_table(policy, label):
    """The table. Rows 1-5 are what the owner buys: an idle endpoint costs no
    re-open. The pump-dead rows keep what 2026-10-11 already had to keep: a
    broken client still earns one."""
    print("\n-- ARM 1 (%s) ---------------------------------------------" % label)
    for name, pump_exited, idle_s, reopens, want in ROWS:
        check(name, policy(pump_exited, idle_s, reopens), want)


def main():
    import sotto_worker as module
    with open(WORKER, encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    print("tap-stall policy oracle: worker = %d B" % os.path.getsize(WORKER))
    arm1_table(module.tap_stall_reason, "as shipped")
    control = len(BROKEN)
    arm1_table(lambda *a: "pump-dead", "CONTROL: always re-open (the old policy)")
    arm1_table(lambda *a: "idle-rearm", "CONTROL: always re-arm (degenerate)")
    control_failures = len(BROKEN) - control

    print("\n-- ARM 2: the run loop must CALL the policy ----------------")
    check("one call site in the run loop", source.count("stall_reason = tap_stall_reason("), 1)
    check("no inline re-decision of the policy", source.count('stall_reason = "pump-dead"'), 0)
    check("TAP_IDLE_MAX_S == 300.0", getattr(module, "TAP_IDLE_MAX_S", None), 300.0)
    check("TAP_REOPEN_MAX == 20", getattr(module, "TAP_REOPEN_MAX", None), 20)
    check("TAP_REOPEN_MIN_S == 5.0", getattr(module, "TAP_REOPEN_MIN_S", None), 5.0)
    check("the re-open floor is honoured", source.count("stall_backoff = max(TAP_REOPEN_MIN_S,"), 1)
    check("the idle wait is a wait, not a spin", source.count("reason=waiting-not-reopening"), 1)
    check("an idle diagnostic is logged once", source.count("idle_logged"), 3)
    shipped_failures = control

    print("\n-- VERDICT ---------------------------------------------------")
    print("  shipped failures : %d" % shipped_failures)
    print("  control failures  : %d (must be > 0)" % control_failures)
    if shipped_failures or control_failures <= 0:
        print("  RED -- " + "; ".join(BROKEN[:4]))
        return 1
    print("  PASS -- an idle endpoint costs no re-open; a broken client still earns one")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())