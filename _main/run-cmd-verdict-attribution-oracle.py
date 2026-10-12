#!/usr/bin/env python3
"""run-cmd-verdict-attribution-oracle -- one exit code, three claims, and only one of them is the wrapper's.

AUDIT ROWS #30 and its inherited twin #C: "run-cmd-exit-oracle esta RED hoje no conjunct do census".
The recorded receipt _main/run-cmd-exit-oracle-after.json says verdict FAIL with the reason
"a VISIBLE window was measured (app-side, see CENSUS ALERTA-JANELA above)". That is the defect, named by
the oracle own words: the oracle prints THREE verdicts because they are three different claims, then
ANDed them into ONE exit code -- so an APP-side fact (a visible window; AGENTS.md says in as many words
that a census RED must never be read as "the wrapper failed") turned the WRAPPER contract test red.

WHAT CHANGED: the decision is now the pure function verdict_from(arms_ok, gaps_ok, census_ok) in
_main/run-cmd-exit-oracle.py, and the exit code carries arms+gaps -- the wrapper own exit contract. The
census keeps its own word, its own line and its own receipt key, and when it is RED the reason says so in
capitals, because DROPPING it silently would be the opposite defect: a number that stops being reported.
A VERDICT-CARRIES line states which claim the code carries, so no reader has to infer it.

DRIVEN WITHOUT LAUNCHING ANYTHING: the function is extracted from the oracle and exec-ed in a bare
namespace -- it takes three booleans and touches nothing.

  1. (arms T, gaps T, census T) -> exit OK, no note;
  2. (arms T, gaps T, census F) -> exit OK **and the why still NAMES the visible window** (this is the
     changed behaviour AND the anti-silence clause in one arm);
  3. (arms F, gaps T, census T) -> exit FAIL (a real contract failure still fails);
  4. (arms T, gaps F, census T) -> exit FAIL;
  5. bytes: the old conjunction is GONE from the oracle, the receipt records all three verdicts plus
     verdict_carries, and the VERDICT-CARRIES line is printed.
  --neg-arm restores the old conjunction inside the extracted copy and requires arm 2 to go RED.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
ORACLE = os.path.join(ROOT, "_main", "run-cmd-exit-oracle.py")
OLD_CONJUNCTION = "verdict_ok = arms_ok and census_ok and gaps_ok"


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


def load(source, restore_conjunction=False):
    snippet = extract(source, "verdict_from")
    if snippet is None:
        raise LookupError("the oracle has no verdict_from")
    if restore_conjunction:
        old = "    contract_ok = bool(arms_ok) and bool(gaps_ok)"
        if old not in snippet:
            raise LookupError("the mutant could not find the contract line")
        snippet = snippet.replace(old, old + " and bool(census_ok)")
    namespace = {}
    exec(compile(snippet, "<verdict_from>", "exec"), namespace)
    return namespace["verdict_from"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(ORACLE, encoding="utf-8") as handle:
        source = handle.read()
    say("run-cmd-verdict-attribution-oracle -- rows #30/#C: which claim does the exit code carry?")
    try:
        verdict_from = load(source)
    except LookupError as error:
        say("VERDICT: FAIL -- " + str(error))
        return 1

    cases = [("arms T, gaps T, census T", (True, True, True), True, False),
             ("arms T, gaps T, census F", (True, True, False), True, True),
             ("arms F, gaps T, census T", (False, True, True), False, False),
             ("arms T, gaps F, census T", (True, False, True), False, False)]
    wrong = []
    for label, args, want_ok, want_note in cases:
        ok, why = verdict_from(*args)
        note = "VISIBLE window" in why
        say("  %-26s exit_ok=%-5s note=%-5s %s"
            % (label, str(ok).lower(), str(note).lower(),
               ("-- " + why[:46]) if not ok else ""))
        if ok != want_ok:
            wrong.append(label + ": expected exit_ok=" + str(want_ok) + ", got " + str(ok))
        if note != want_note:
            wrong.append(label + ": expected the census note=" + str(want_note) + ", got " + str(note))

    conjunction_gone = OLD_CONJUNCTION not in source
    carries = source.count("'verdict_carries'")
    printed = "VERDICT-CARRIES" in source
    keys = [k for k in ("'arms_ok'", "'gaps_ok'", "'census_ok'", "'census_verdict'") if k in source]
    say("  old conjunction gone: " + str(conjunction_gone).lower()
        + "  receipt keys present: " + str(len(keys)) + "/4"
        + "  verdict_carries: " + str(carries) + "  VERDICT-CARRIES printed: " + str(printed).lower())
    if not conjunction_gone:
        wrong.append("the old conjunction is still in the oracle: " + OLD_CONJUNCTION)
    if carries < 1:
        wrong.append("the receipt does not record which claim the exit code carries")
    if not printed:
        wrong.append("the VERDICT-CARRIES line is not printed")
    if len(keys) != 4:
        wrong.append("the receipt lost one of its three verdict keys: " + str(keys))

    if parsed.neg_arm:
        mutant = load(source, restore_conjunction=True)
        m_ok, _why = mutant(True, True, False)
        say("")
        say("  mutant(old conjunction restored): arms T gaps T census F -> exit_ok=" + str(m_ok).lower())
        wrong = [w for w in wrong if not w.startswith("arms T, gaps T, census F")]
        if m_ok:
            wrong.append("NEG-ARM: the restored conjunction did NOT turn the census RED into a FAIL -- "
                         "arm 2 is not measuring anything")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": restoring the conjunction must make an app-side window fail the wrapper contract again")
        return 0 if not wrong else 1

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the exit code carries the wrapper contract (arms+gaps), the census RED is still NAMED in"
        " the reason and still recorded in the receipt, and a real contract failure still fails")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
