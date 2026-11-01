#!/usr/bin/env python3
"""THE RESPAWN CEILING ORACLE -- does the shell actually STOP restarting?

WHY THIS EXISTS (owner, 2026-10-22): "worker busy-spin (1.3-1.8 cores) with no
backoff on respawn". He was right about the consequence, and the cause is not a
missing backoff -- it is a backoff whose STOP was written in a place that never
runs.

MEASURED, the shell's own log, 2026-10-22 04:04 -> 04:20, one no-audio death
every ~85 s:

    BRIDGE_DEATH rc=3 deaths=1   -> BRIDGE_RESTART ladder=no-audio in_ms=15000
    BRIDGE_DEATH rc=3 deaths=2   -> BRIDGE_RESTART ladder=no-audio in_ms=30000
    BRIDGE_DEATH rc=3 deaths=3   -> BRIDGE_RESTART ladder=no-audio in_ms=60000
    BRIDGE_DEATH rc=3 deaths=4   -> BRIDGE_RESTART ladder=no-audio in_ms=120000
    BRIDGE_DEATH rc=3 deaths=5   -> BRIDGE_RESTART ladder=no-audio in_ms=240000
    BRIDGE_DEATH rc=3 deaths=6   -> BRIDGE_RESTART ladder=no-audio in_ms=300000

`no_audio_restart_cap=3` (sotto_webview.py:11919) says that after the THIRD
consecutive no-audio death the shell must stop and wait for Alt+C. It never did:
`BRIDGE_RESTART_SUPPRESSED` appears ZERO times in 41 MB of log while `deaths`
climbs past the cap.

THE CAUSE, read literally out of the file (`_schedule_restart`):

    12998  indent= 8  if self.stopped:
    12999  indent=12      return
    13000  indent= 8  # The two ladders. ...
    13004  indent=12  # O TECTO. ...
    13008  indent=12  if self.no_audio_restarts >= self.no_audio_restart_cap:

An `if` at indent 12 directly after a `return` at indent 12 is still the BODY of
the `if self.stopped:` at indent 8. So the ceiling is (a) nested under "the shell
is stopping" -- the one state in which nobody needs it -- and (b) unconditionally
unreachable, because the `return` above it already left. `ast.parse` is happy:
dead code after `return` is legal Python. That is why no gate caught it and why
the log never printed the suppression.

TWO CLAIMS, because a behavioural test alone would not name the cause:
  C1 STRUCTURAL -- the ceiling statement must not sit inside a block that is
     entered only when the shell is stopping, and must not follow an
     unconditional `return` in its own block. This is the claim that FAILS today
     and the only one that says WHY.
  C2 BEHAVIOURAL -- drive `cap + 3` no-audio deaths through the real function and
     demand exactly `cap` restarts followed by a suppression. This is the claim
     the owner feels.

AND THE THIRD CLAIM, which is what makes the other two mean anything:
  C3 THE LADDER IS BOUNDED -- every scheduled delay is <= no_audio_backoff_max,
     and a suppression arms NO timer.

`--neg-arm`: a COPY with the block re-indented back under `if self.stopped:` must
turn C1 and C2 RED. The mutation is the shipped defect, restored -- this oracle's
negative arm is not hypothetical, it is the file as it was found.

Nothing here launches the app, loads a model or opens an audio device: the
function is lifted out of the source with `ast` and driven against a stub. That
is why it can live in a battery.
"""
from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import textwrap
import threading
import types

SHELL = "app/webview/sotto_webview.py"
FUNCTION = "_schedule_restart"


# ---------------------------------------------------------------------------
# LIFTING THE REAL FUNCTION OUT OF THE REAL FILE
# ---------------------------------------------------------------------------
def read_source(path=SHELL):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def find_function(src, name=FUNCTION):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise SystemExit("%s not found in %s" % (name, SHELL))


def lift(src, name=FUNCTION):
    """The function's source, dedented, as a plain callable taking `self`."""
    node = find_function(src, name)
    body = ast.get_source_segment(src, node)
    ns = {}
    exec(compile(textwrap.dedent(body), "<lifted %s>" % name, "exec"), ns)
    return ns[name]


# ---------------------------------------------------------------------------
# C1 -- STRUCTURAL: is the ceiling reachable at all?
# ---------------------------------------------------------------------------
def claim_structural(src):
    """Walk to the ceiling `if` and report every enclosing guard.

    The defect is not "a long function". It is that the statement sits inside an
    `if` whose test is `self.stopped`, behind an unconditional `return`. Both are
    readable from the AST, and both are reported so the failure message names the
    cause instead of pointing at a line number.
    """
    fn = find_function(src)
    stmts = fn.body

    def find_ceiling(block, ancestors):
        for idx, stmt in enumerate(block):
            if isinstance(stmt, ast.If) and "no_audio_restart_cap" in ast.dump(stmt.test):
                return stmt, idx, ancestors, block
            for field in ("body", "orelse"):
                sub = getattr(stmt, field, None)
                if isinstance(sub, list) and sub:
                    got = find_ceiling(sub, ancestors + [stmt])
                    if got:
                        return got
        return None

    got = find_ceiling(stmts, [])
    if not got:
        return False, "the ceiling `if ... no_audio_restart_cap` is not in %s at all" % FUNCTION

    stmt, idx, ancestors, block = got
    problems = []
    for anc in ancestors:
        dump = ast.dump(anc.test) if isinstance(anc, ast.If) else ""
        if "stopped" in dump:
            problems.append(
                "it is nested inside `if self.stopped:` -- the ceiling is only "
                "reachable while the shell is ALREADY stopping, which is the one "
                "state that never needs it")
    for before in block[:idx]:
        if isinstance(before, ast.Return):
            problems.append(
                "an unconditional `return` on line %d precedes it in the same "
                "block, so nothing after it can ever run"
                % getattr(before, "lineno", -1))
    if problems:
        return False, " | ".join(problems)
    return True, "the ceiling is reachable: no `self.stopped` guard above it, no `return` before it"


# ---------------------------------------------------------------------------
# C2 + C3 -- BEHAVIOUR: how many respawns does `cap + 3` deaths produce?
# ---------------------------------------------------------------------------
class Stub:
    """Only what `_schedule_restart` touches. No app, no worker, no audio."""

    def __init__(self, cap=3, base=15000, ceiling=300000):
        self.stopped = False
        self.no_audio_restarts = 0
        self.no_audio_restart_cap = cap
        self.no_audio_backoff_base = base
        self.no_audio_backoff_max = ceiling
        self.restarts = 0
        self.backoff_base = 1000
        self.backoff_max = 30000
        self._restart_timer = None
        self.pending_error = None
        self.lines = []
        self.scheduled = []
        self.armed = 0

    def log(self, line):
        self.lines.append(line)

    def _restart(self):                      # never called: timers are not run
        raise AssertionError("the oracle must not run a restart")

    # the timer is what arms a respawn; count arms instead of running them
    def arm_patch(self, func_ns):
        stub = self

        class FakeTimer:
            def __init__(self, delay, fn):
                self.delay = delay
                self.daemon = True
                stub.armed += 1
                stub.scheduled.append(delay)

            def start(self):
                pass

            def cancel(self):
                pass

        func_ns["threading"].Timer = FakeTimer


def drive(src, deaths=6, cap=3):
    fn = lift(src)
    stub = Stub(cap=cap)
    ns = {"threading": threading, "NO_AUDIO_STATE": "no-audio"}
    body_ns = dict(ns)
    stub.arm_patch(body_ns)
    # rebind the lifted function's globals to the patched namespace
    fn.__globals__["threading"] = body_ns["threading"]
    fn.__globals__.setdefault("NO_AUDIO_STATE", "no-audio")
    for _ in range(deaths):
        fn(stub, "exit", no_audio=True)
    return stub


def claim_behaviour(src, cap=3):
    stub = drive(src, deaths=cap + 3)
    suppressed = [l for l in stub.lines if "BRIDGE_RESTART_SUPPRESSED" in l]
    if not suppressed:
        return False, ("%d consecutive no-audio deaths produced %d respawn(s) and "
                       "ZERO suppression: %s -- cap=%d was never reached"
                       % (cap + 3, stub.armed, stub.scheduled, cap))
    if stub.armed != cap:
        return False, "suppression appeared but %d timers were armed (expected %d)" % (stub.armed, cap)
    return True, ("%d deaths -> exactly %d respawn(s) %s, then SUPPRESSED"
                  % (cap + 3, stub.armed, stub.scheduled))


def claim_bounded(src, cap=3, ceiling=300000):
    stub = drive(src, deaths=cap + 3)
    over = [d for d in stub.scheduled if d > ceiling]
    if over:
        return False, "delay(s) above the ceiling: %s (max %d)" % (over, ceiling)
    return True, "every scheduled delay <= %d ms: %s" % (ceiling, stub.scheduled)


# ---------------------------------------------------------------------------
# THE MUTATION -- the shipped defect, restored
# ---------------------------------------------------------------------------
def mutate_restore_defect(src):
    """Re-indent the ceiling under `if self.stopped:` again.

    This is the ORIGINAL shape of the file, not an invented bug: it is what the
    owner's machine was running when he reported the spin. If this oracle cannot
    see it come back, it is decoration.
    """
    lines = src.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if "O TECTO. Ver `no_audio_restart_cap`" in line:
            start = i
            break
    if start is None:
        raise SystemExit("the ceiling comment was not found -- the mutation anchor is spent")
    # the block runs from the comment to the `return` that closes the suppression
    end = start
    while end < len(lines) and "return" not in lines[end]:
        end += 1
    # SHIFT the whole block RIGHT by one level. Flattening it to a fixed indent
    # destroys the block's own nesting and the mutant stops parsing -- a mutant
    # that does not compile proves nothing except that the mutation was wrong.
    for i in range(start, end + 1):
        if lines[i].strip():
            lines[i] = "    " + lines[i]
    return "".join(lines)


# ---------------------------------------------------------------------------
def run(src, label):
    rows = [
        ("C1", "the ceiling is REACHABLE (not under `self.stopped`, not after `return`)",
         claim_structural(src)),
        ("C2", "consecutive no-audio deaths STOP at the cap", claim_behaviour(src)),
        ("C3", "the respawn ladder is bounded and a suppression arms no timer", claim_bounded(src)),
    ]
    failed = 0
    print("%s" % label)
    for key, what, (ok, detail) in rows:
        print("  %s %s %-58s %s" % ("ok  " if ok else "FAIL", key, what, detail))
        if not ok:
            failed += 1
    print("")
    print("%d check(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description="does the shell stop restarting a silent worker?")
    ap.add_argument("--file", default=SHELL)
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    src = read_source(args.file)

    if not args.neg_arm:
        print("RESPAWN CEILING ORACLE -- PRISTINE (%s)" % args.file)
        return 0 if run(src, "") == 0 else 1

    print("RESPAWN CEILING ORACLE -- CONTROL")
    print("  control: %s" % args.file)
    print("")
    ctrl_failed = run(src, "  CONTROL (the file as it stands) must be GREEN")
    print("")
    broken = mutate_restore_defect(src)
    if broken == src:
        print("  MUTATION DID NOT APPLY -- the anchor is spent")
        return 1
    mut_failed = run(broken, "  M1 the shipped defect restored (ceiling back under `if self.stopped:`) must be RED")
    ok = (ctrl_failed == 0 and mut_failed > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl_failed == 0 else "RED",
             "RED" if mut_failed > 0 else "GREEN (INERT MUTANT)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
