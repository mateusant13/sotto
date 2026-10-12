#!/usr/bin/env python3
"""selftest-focus-oracle -- a self-test that measures a focus theft and then ignores it.

AUDIT ROWS #28, #H6 and Finding B: "shell selftest registra focus_stolen=true e mesmo assim sai 0".
The self-test read `foreground_window()` before and after its two simulated presses, LOGGED
`focus_stolen=...` when they differed, and then computed its verdict WITHOUT that fact -- so a run in
which the panel took the owner's foreground was reported rc=0, green. A gate that measures a defect and
then declines to look at the measurement is worse than one that never measured it.

THE FIX HAS TWO HALVES, and the second is why this is not just an `or` clause:
  1. ATTRIBUTION. `stolen_by_us` is true only when the new foreground window belongs to THIS process
     (GetWindowThreadProcessId == os.getpid()). A foreign window becoming foreground is the owner using
     his own PC -- failing on that would make the self-test flaky on every busy desktop, and a flaky
     gate gets muted, which is how this defect survived.
  2. THE VERDICT is now the pure function `selftest_broken(reading)` in the shell, so it can be driven
     with synthetic readings -- no hotkey, no WebView2, no launch.

WHAT IT ASSERTS, every run:
  1. the shell still CALLS `selftest_broken(` (the factoring did not leave an orphan);
  2. the old inline expression is GONE from the shell -- a presence-only check would pass with both the
     fix and the defect on disk;
  3. the function is PURE: its source is exec-ed in a BARE namespace, so a dependency creeping in (a
     global, ctypes, the module) fails here instead of passing through a module import;
  4. five readings: the positive control is ACCEPTED, the own-window theft is REFUSED, a FOREIGN window
     is NOT a failure, and the two pre-existing clauses still bite;
  5. --neg-arm rewrites the marked clause to `if False and ...` in the extracted source and requires the
     own-window reading to stop being refused -- a check that cannot fail proves nothing.

NO LAUNCH: text extraction plus pure-function calls.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

GOOD = {"registered": True, "pressed": True, "presses": 2, "visible": True, "want_visible": True,
        "focus_stolen_by_own_window": False, "focus_before": 100, "focus_after": 100}
OWN = dict(GOOD, focus_stolen_by_own_window=True, focus_after=4242)
FOREIGN = dict(GOOD, focus_stolen_by_own_window=False, focus_after=9999)
NOHOTKEY = dict(GOOD, registered=False)
WRONGVIS = dict(GOOD, visible=False)

CASES = [("control (nothing wrong)", GOOD, False),
         ("own window took the foreground", OWN, True),
         ("a FOREIGN window took it (owner using the PC)", FOREIGN, False),
         ("the hotkey never registered", NOHOTKEY, True),
         ("the window reads the wrong visibility", WRONGVIS, True)]


def extract_function(source, name):
    """The function source, from its `def` to the next top-level statement."""
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


def load(source):
    """exec the extracted function in a BARE namespace: purity is the point."""
    namespace = {}
    exec(compile(source, "<extracted>", "exec"), namespace)  # noqa: S102 - the subject itself
    return namespace["selftest_broken"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shell", default=SHELL)
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(parsed.shell, encoding="utf-8") as handle:
        shell = handle.read()
    source = extract_function(shell, "selftest_broken")
    say("selftest-focus-oracle -- the verdict now reads the focus it measures (no launch)")
    if not source:
        say("VERDICT: FAIL -- the shell has no `selftest_broken`; the verdict was never factored")
        return 1
    try:
        verdict = load(source)
    except NameError as error:
        say("VERDICT: FAIL -- the verdict is NOT pure: exec in a bare namespace raised " + str(error))
        return 1

    calls = shell.count("selftest_broken(")
    orphans = "broken = (not self.hotkey.registered" in shell
    say("  shell references to selftest_broken: " + str(calls) + " (definition + call = 2)")
    say("  old inline expression still present: " + str(orphans).lower())

    results = {}
    for label, reading, want in CASES:
        got, why = verdict(dict(reading))
        results[label] = got
        say("  %-46s broken=%-5s %s" % (label, str(got).lower(), ("-- " + why[:58]) if got else ""))

    wrong = []
    if calls < 2:
        wrong.append("the shell does not call selftest_broken (only the definition is present)")
    if orphans:
        wrong.append("the OLD inline verdict expression is still in the shell")
    for label, _reading, want in CASES:
        if results[label] != want:
            wrong.append(label + ": expected broken=" + str(want) + ", got " + str(results[label]))

    marker = "    if reading.get('focus_stolen_by_own_window'):  # FOCUS-CLAUSE"

    if parsed.neg_arm:
        if source.count(marker) != 1:
            say("NEG-ARM SETUP ERROR: the marked clause appears " + str(source.count(marker))
                + " time(s), expected 1")
            return 2
        mutant_source = source.replace(
            marker, "    if False and reading.get('focus_stolen_by_own_window'):  # FOCUS-CLAUSE")
        mutant = load(mutant_source)
        mutant_own, _ = mutant(dict(OWN))
        mutant_good, _ = mutant(dict(GOOD))
        mutant_hot, _ = mutant(dict(NOHOTKEY))
        say("")
        say("  mutant: own-window broken=" + str(mutant_own).lower()
            + " (live: " + str(results["own window took the foreground"]).lower() + ")")
        say("  mutant: control broken=" + str(mutant_good).lower()
            + "  hotkey-missing broken=" + str(mutant_hot).lower())
        if mutant_own:
            wrong.append("NEG-ARM: with the clause disabled the own-window theft is STILL refused -- "
                         "the check does not bite")
        # `mutant_good` FALSE is the CORRECT reading (the control must stay unbroken): the first
        # draft of this check asserted `not mutant_good` and failed its own green run -- the
        # polarity was inverted, and the instrument said so instead of passing.
        if mutant_good:
            wrong.append("NEG-ARM: with the focus clause disabled the CONTROL is now refused -- an "
                         "unrelated verdict moved")
        if not mutant_hot:
            wrong.append("NEG-ARM: with the focus clause disabled the missing-hotkey verdict stopped "
                         "biting -- an unrelated verdict moved")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": disabling the marked clause must stop refusing the own-window theft and leave the"
            " other verdicts alone")
        return 0 if not wrong else 1

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the self-test FAILS when the panel takes the foreground (own pid) and stays GREEN when a"
        " foreign window does; the verdict is pure and the old inline expression is gone")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
