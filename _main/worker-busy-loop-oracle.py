#!/usr/bin/env python3
"""THE BUSY-LOOP ORACLE -- the worker must not have a loop that can only end with
the process.

WHY THIS EXISTS (owner, verbatim, the 100 h backlog):
    *"worker busy-spin (1.3-1.8 cores)"*

The respawn half of that complaint was a real defect and is closed elsewhere
(`_main/worker-respawn-ceiling-oracle.py`: the `no_audio_restart_cap` ceiling sat
at indent 12 behind a `return`). The CPU half is a different question, and the
cheapest honest thing that can be said about it WITHOUT launching the app is
structural: is there a `while` loop in the worker that cannot end?

WHAT A BUSY-SPIN LOOKS LIKE IN PYTHON, precisely:
  * a constant condition (`while True:` / `while 1:`) -- nothing in the program
    state can make it false, so it ends only via `break`, `return`, an exception,
    or a blocking call that raises; and
  * no blocking call in the body -- `sleep`, `wait`, `get`, `recv`, `read`,
    `join`, `acquire`, `select`, `run`/`process` (the inference).

A loop with a constant condition and no blocking call and no break/return is a
loop that burns a core until someone kills it. That is the claim.

  C1 no `while True:` in the worker is unbounded in that sense.
  C2 THE CENSUS IS THE EVIDENCE, so it is printed: every `while True:` found, with
     the escape it uses. A gate that only says PASS teaches nothing the day it
     goes red.
  C3 the same holds for `app/webview/sotto_webview.py` (the shell owns the worker
     and its own pump loops; a shell spin is the same 1.3 cores).

WHAT THIS DOES **NOT** CLAIM -- and it matters, because a green gate is not a
measurement of cores:
  * it does not measure CPU. Only `_main/sotto-perf-log.py --launch` and psutil
    can say 1.3-1.8 cores, and that costs a launch of the model. DECLARED, NOT DONE.
  * it cannot see a spin inside a C extension (onnxruntime, pycaw, sounddevice).
    Measured later or not at all -- not by this file.
  * a loop that blocks but wakes 10 000 times a second would pass C1. The capture
    loop's own comment says 10 Hz; that rate is measured by the perf log, not here.

FILES ONLY: `ast` over two sources, no imports of either, nothing launched. So it
belongs in a battery.

`--neg-arm` writes a `while True: pass` into a copy and demands C1 go RED.
"""
from __future__ import annotations

import argparse
import ast
import io
import sys
import tempfile

TARGETS = (
    ("worker/sotto_worker.py", "the worker"),
    ("app/webview/sotto_webview.py", "the shell"),
)

#: Calls that can block. `get`/`wait`/`sleep`/`read`/`recv`/`join`/`acquire`/
#: `select`/`poll` are the obvious ones; `run`/`process` are listed because the
#: inference itself is long-running and is a legitimate loop escape.
BLOCKING = frozenset({
    "sleep", "wait", "wait_for", "recv", "recv_into", "read", "readinto",
    "join", "acquire", "get", "select", "poll", "accept", "readframes",
    "run", "process", "infer", "decode", "call", "evaluate_js",
})


def is_constant_condition(test):
    if isinstance(test, ast.Constant):
        return bool(test.value)
    return False


def escapes(loop):
    """How a `while True:` can end: 'break' / 'return' / a blocking call."""
    found = []
    for node in ast.walk(loop):
        if isinstance(node, ast.Break):
            found.append("break")
        elif isinstance(node, ast.Return):
            found.append("return")
        elif isinstance(node, ast.Raise):
            found.append("raise")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in BLOCKING:
                found.append("blocking:%s" % name)
    return sorted(set(found))


def census(src):
    """Every `while True:` with the escapes it has (for the report)."""
    tree = ast.parse(src)
    rows = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        for loop in [n for n in ast.walk(fn) if isinstance(n, ast.While)]:
            if not is_constant_condition(loop.test):
                continue
            rows.append((fn.name, loop.lineno, escapes(loop)))
    return rows


def claim_no_unbounded(src, label):
    rows = census(src)
    bad = [(fn, ln, esc) for fn, ln, esc in rows if not esc]
    for fn, ln, esc in rows:
        print("      %-18s %-26s L%-6d escapes=%s" % (label, fn, ln, esc or "NONE"))
    if bad:
        detail = "; ".join("%s() L%d has no escape" % (fn, ln) for fn, ln, _ in bad)
        return False, detail
    return True, "%d `while True:` loop(s) in %s, every one with an escape" % (len(rows), label)


def mutate_add_busy_loop(src):
    """Append a loop that can only end when the process dies."""
    return src + (
        "\n\ndef _mutant_busy_spin():\n"
        "    total = 0\n"
        "    while True:\n"
        "        total += 1\n"
        "    return total\n"
    )


def run(src_pairs):
    rows = []
    print("  C2 the census (what was found, and how each loop can end):")
    for path, src, label in src_pairs:
        ok, detail = claim_no_unbounded(src, label)
        rows.append((path, ok, detail))
    print("")
    failed = 0
    for path, ok, detail in rows:
        print("  %s C1 %-34s %s" % ("ok  " if ok else "FAIL", path.split("/")[-1], detail))
        if not ok:
            failed += 1
    print("")
    print("%d source(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


def load():
    out = []
    for path, label in TARGETS:
        with io.open(path, encoding="utf-8", newline="") as fh:
            out.append((path, fh.read(), label))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="is there a loop in the worker that cannot end?")
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    pairs = load()
    if not args.neg_arm:
        print("BUSY-LOOP ORACLE -- PRISTINE")
        print("  (a `while True:` with no blocking call, break, return or raise burns a core)")
        return 0 if run(pairs) == 0 else 1

    print("BUSY-LOOP ORACLE -- CONTROL")
    ctrl = run(pairs)
    if ctrl != 0:
        print("")
        print("NEG-ARM VERDICT: FAIL -- the control is already RED, no mutation to judge")
        return 1

    path = pairs[0][0]
    broken = mutate_add_busy_loop(pairs[0][1])
    if broken == pairs[0][1]:
        print("  MUTATION DID NOT APPLY -- the anchor is spent")
        return 1
    print("")
    print("  M1 a `while True:` with no escape appended to %s must be RED" % path)
    mut = run([(path, broken, pairs[0][2])] + pairs[1:])
    ok = (ctrl == 0 and mut > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl == 0 else "RED",
             "RED" if mut > 0 else "GREEN (INERT MUTANT)"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
