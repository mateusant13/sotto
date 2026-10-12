#!/usr/bin/env python3
"""selftest-quality-oracle -- a self-test that could not fail.

AUDIT ROWS #25 and #H1: "shell --selftest nao afirma qualidade do output (verde com word-salad)".
Measured by reading: selftest() asked only whether the text was EMPTY and then returned 0
unconditionally, so the run this file own header describes -- 37 tokens, rc=0, "a green exit code on
word salad" -- was indistinguishable from the corrected one at 94 tokens.

WHAT WAS ADDED, and what it is NOT. The floor is DERIVED FROM TWO MEASURED RUNS OF THE SAME FILE, both
quoted from the worker header: the greedy-walk defect returned 37 tokens over 13.44 s = 2.75 tokens/s
with rc=0; the corrected walk returns 94 = 6.99 tokens/s. The floor sits at 4.0 -- above the defective
run, below the good one. It is NOT a quality verdict and cannot tell fluent English from
fluent-sounding nonsense; it catches the one degradation this repo MEASURED, which is a counting
failure, by counting what came out against the audio that went in. Claiming more than that would be the
same dishonesty the row is about.

WHAT IT DRIVES, with no audio, no model and no launch: selftest_quality is extracted from the worker
and exec-ed in a BARE namespace -- so a dependency creeping into it (a global, a ctypes handle) fails
here instead of passing through a module import.

  1. the HISTORIC defect (37 tokens / 13.44 s) is REFUSED;
  2. the CORRECTED run (94 tokens / 13.44 s) is ACCEPTED -- the positive control: a rule that refuses
     everything would fail here;
  3. an EMPTY transcript is REFUSED, by its own clause, with no division involved;
  4. an unknown duration is ACCEPTED, because a floor cannot be applied to a number nobody has -- the
     limit is stated rather than hidden;
  5. the shell still CALLS the verdict, and the old unconditional return 0 is GONE (a presence-only
     check would pass with the fix and the defect both on disk).
  --neg-arm sets the floor to ZERO -- exactly what "no floor" means -- and requires arm 1 to stop being
  refused while arm 3 stays refused, so the two clauses are shown to be independent.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")

DEFECT = {"tokens": 37, "audio_s": 13.44, "empty": False}
CORRECTED = {"tokens": 94, "audio_s": 13.44, "empty": False}
EMPTY = {"tokens": 0, "audio_s": 13.44, "empty": True}
NO_DURATION = {"tokens": 30, "audio_s": 0.0, "empty": False}


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


def load(source, floor_override=None):
    match = re.search(r"^SELFTEST_MIN_TOKENS_PER_S\s*=\s*(.+)$", source, re.MULTILINE)
    if not match:
        raise LookupError("the worker has no SELFTEST_MIN_TOKENS_PER_S")
    namespace = {"SELFTEST_MIN_TOKENS_PER_S": float(match.group(1))}
    snippet = extract(source, "selftest_quality")
    if not snippet:
        raise LookupError("the worker has no selftest_quality")
    if floor_override is not None:
        namespace["SELFTEST_MIN_TOKENS_PER_S"] = floor_override
    exec(compile(snippet, "<selftest_quality>", "exec"), namespace)
    return namespace["selftest_quality"], namespace["SELFTEST_MIN_TOKENS_PER_S"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(WORKER, encoding="utf-8") as handle:
        source = handle.read()
    say("selftest-quality-oracle -- the floor, and its limit (no audio, no launch)")
    try:
        verdict, floor = load(source)
    except LookupError as error:
        say("VERDICT: FAIL -- " + str(error))
        return 1

    calls = source.count("selftest_quality(")
    old_return = 'print("--- end selftest ---", file=sys.stderr)\n    return 0' in source
    say("  shell references to selftest_quality: " + str(calls) + " (definition + call = 2)")
    say("  the OLD unconditional return 0 after the selftest: " + str(old_return).lower())
    say("  floor = " + str(floor) + " tokens/s")

    cases = [("historic defect 37 tok / 13.44 s (2.75/s)", DEFECT, False),
             ("corrected run 94 tok / 13.44 s (6.99/s)", CORRECTED, True),
             ("an EMPTY transcript", EMPTY, False),
             ("an unknown duration (audio_s = 0)", NO_DURATION, True)]
    results = {}
    for label, reading, want in cases:
        ok, why = verdict(dict(reading))
        results[label] = ok
        if label.startswith("unknown"):
            say("  %-42s accepted=%s" % (label, str(ok).lower()))
        else:
            say("  %-42s accepted=%-5s %s" % (label, str(ok).lower(), ("-- " + why[:56]) if not ok else ""))

    wrong = []
    if calls < 2:
        wrong.append("the worker does not call selftest_quality (only the definition exists)")
    if old_return:
        wrong.append("the OLD unconditional return 0 is still there -- the refusal cannot reach rc")
    for label, _reading, want in cases:
        if results[label] != want:
            wrong.append(label + ": expected accepted=" + str(want) + ", got " + str(results[label]))

    if parsed.neg_arm:
        mutant, _floor = load(source, floor_override=0.0)
        defect_ok, _ = mutant(dict(DEFECT))
        empty_ok, _ = mutant(dict(EMPTY))
        say("")
        say("  mutant(floor 0.0): historic defect accepted=" + str(defect_ok).lower()
            + "  empty accepted=" + str(empty_ok).lower())
        if defect_ok:
            wrong = [w for w in wrong if not w.startswith("historic defect")]
        else:
            wrong.append("NEG-ARM: with the floor at zero the historic defect is STILL refused -- the "
                         "floor is not what refuses it")
        if empty_ok:
            wrong.append("NEG-ARM: with the floor at zero the EMPTY clause stopped biting -- the two "
                         "clauses are not independent")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": removing the floor must accept the historic defect and leave the EMPTY clause alone")
        return 0 if not wrong else 1

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the self-test now refuses a transcript below the MEASURED floor (and an empty one by its"
        " own clause), while accepting the corrected run; it is a floor, not a quality verdict, and the"
        " limit is written where the floor is")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
