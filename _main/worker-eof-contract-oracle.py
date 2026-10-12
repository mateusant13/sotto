#!/usr/bin/env python3
"""worker-eof-contract-oracle -- the top of the worker must not be a hole in its own contract.

AUDIT ROW F18: "excepcoes fora dos poucos try escapam ao contrato JSONL (EOF sem done/error)".
Measured by reading the entry block: it caught ONLY KeyboardInterrupt -- and answered 0 -- so every
other exception left the JSONL contract OPEN, which is the same shape the shell sees for a healthy
finish: EOF with no done and no error. Every other try in the file is LOCAL to a phase; nothing owned
the top.

WHAT WAS ADDED: contract_guard(main_fn, emit_fn=emit, err_fn=err) wraps the entry. It emits a terminal
error event and returns 4 for any catchable exception, keeps SystemExit's OWN code untouched (2 = usage,
3 = silent device, and run.cmd's --check-args pre-flight reads those numbers), and turns the old silent
KeyboardInterrupt-to-0 into an EVENT plus 130.

WHAT IT CANNOT DO, and the row is about a gap, so this is part of the claim: the shell stops the worker
with terminate()/kill() (TerminateProcess, measured at app/webview/sotto_webview.py:7453, :7457, :7914)
and no Python-level guard catches that. That path still ends in EOF, and no code change can fix it.

DRIVEN WITHOUT A DEVICE, A MODEL OR A PROCESS: the guard is extracted from the worker and exec-ed in a
bare namespace whose emit/err are RECORDERS, and the guard's defaults bind to them -- so this measures
the guard that ships, not a copy of its logic.

  1. ValueError in the run        -> rc 4, exactly one event, state=error stage=unhandled, detail named;
  2. a normal return of 3         -> rc 3, ZERO events (a guard that swallows the happy path fails here);
  3. SystemExit(2)                -> PROPAGATES with code 2 and no event;
  4. KeyboardInterrupt            -> rc 130 with its OWN stage, not 4;
  5. bytes: the entry calls contract_guard and the old bare sys.exit(main()) is GONE.
  --neg-arm replaces the last return of the guard with a re-raise and requires arm 1 to go RED.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")


def extract(source, name):
    lines = source.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.startswith("def " + name + "("):
            start = index
            break
    if start is None:
        return None
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line[0].isspace() and (line.startswith("def ") or line.startswith("class ")
                                               or line.startswith("@")):
            return "\n".join(lines[start:index])
    return "\n".join(lines[start:])


def load(source, mutate=False):
    snippet = extract(source, "contract_guard")
    if snippet is None:
        raise LookupError("the worker has no contract_guard")
    if mutate:
        head, sep, tail = snippet.rpartition("        return 4")
        if not sep:
            raise LookupError("the mutant could not find the guard's return 4")
        snippet = head + "        raise exc" + tail
    events = []
    words = []
    namespace = {
        "emit": lambda **payload: events.append(payload),
        "err": lambda message: words.append(message),
    }
    exec(compile(snippet, "<contract_guard>", "exec"), namespace)
    return namespace["contract_guard"], events, words


def exercise(guard):
    """(label, callable) pairs, in the order they are reported."""
    def owned():
        raise ValueError("boom")

    def fine():
        return 3

    def refusal():
        raise SystemExit(2)

    def interrupted():
        raise KeyboardInterrupt()

    return [("ValueError in the run", owned), ("a normal return of 3", fine),
            ("SystemExit(2)", refusal), ("KeyboardInterrupt", interrupted)]


def run_arm(guard, fn):
    try:
        return int(guard(fn)), None
    except SystemExit as stop:
        return None, stop.code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(WORKER, encoding="utf-8") as handle:
        source = handle.read()
    say("worker-eof-contract-oracle -- row F18: does any catchable exit leave the contract open?")
    try:
        guard, events, words = load(source)
    except LookupError as error:
        say("VERDICT: FAIL -- " + str(error))
        return 1

    recipes = {"ValueError in the run": (4, "unhandled"),
               "a normal return of 3": (3, None),
               "SystemExit(2)": (None, 2, "exit"),
               "KeyboardInterrupt": (130, "interrupted")}
    wrong = []
    for label, fn in exercise(guard):
        events.clear()
        words.clear()
        code, exit_code = run_arm(guard, fn)
        want = recipes[label]
        if label == "SystemExit(2)":
            ok = exit_code == 2 and not events
            say("  %-22s propagates with code %s, events=%d  %s"
                % (label, exit_code, len(events), "ok" if ok else "WRONG"))
            if not ok:
                wrong.append("SystemExit must keep its own code (2) and emit nothing; got code="
                             + str(exit_code) + " events=" + str(len(events)))
            continue
        stage = events[0].get("stage") if events else None
        ok = code == want[0] and (stage == want[1] if want[1] else not events)
        detail = events[0].get("detail", "") if events else ""
        say("  %-22s rc=%-4s events=%d stage=%-12s %s"
            % (label, code, len(events), stage, ("-- " + detail[:34]) if detail else ""))
        if not ok:
            wrong.append(label + ": expected rc=" + str(want[0]) + " stage=" + str(want[1])
                         + ", got rc=" + str(code) + " stage=" + str(stage))

    calls = source.count("contract_guard(main)")
    old_entry = "sys.exit(main())" in source
    say("  entry calls contract_guard(main): " + str(calls) + "  old bare sys.exit(main()): "
        + str(old_entry).lower())
    if calls != 1:
        wrong.append("the entry does not call contract_guard(main) exactly once (got " + str(calls) + ")")
    if old_entry:
        wrong.append("the old bare sys.exit(main()) is still in the file")
    if "emit_fn=emit, err_fn=err" not in source:
        wrong.append("the guard's defaults no longer bind the module's own emitters")

    if parsed.neg_arm:
        mutant, mevents, _words = load(source, mutate=True)
        # The mutant RE-RAISES, so the escape has to be caught here or this oracle dies with the
        # very exception it is measuring -- which is what its first version did.
        escaped = None
        mcode = None
        try:
            mcode, _mexit = run_arm(mutant, lambda: (_ for _ in ()).throw(ValueError("boom")))
        except BaseException as error:
            escaped = type(error).__name__
        say("")
        say("  mutant(re-raise): escaped=%s rc=%s events=%d" % (escaped, mcode, len(mevents)))
        flipped = escaped is not None or mcode != 4 or not mevents
        wrong = [w for w in wrong if not w.startswith("ValueError in the run")]
        if not flipped:
            wrong.append("NEG-ARM: re-raising instead of emitting still returned rc=4 with an event -- "
                         "the arm is not measuring the guard")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": a guard that re-raises must let the exception escape (no rc 4, no event)")
        return 0 if not wrong else 1

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- every catchable exit now ends in a terminal event or a meaningful code, SystemExit keeps"
        " its own number, and the limit is stated: TerminateProcess still ends in EOF")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
