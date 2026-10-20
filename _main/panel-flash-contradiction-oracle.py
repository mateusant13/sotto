#!/usr/bin/env python3
"""panel-flash-contradiction-oracle -- a declared contradiction must be declared at BOTH ends.

AUDIT ROWS #46 and its inherited twin F3: "AGENTS.md contradiz-se sobre o painel no arranque (0 de 41
vs visivel 50 ms-7 s)". The numbers come from ONE instrument (_main/panel-startup-flash-census.py) and
they disagree:
  the gate bullet       -- 'live' 0/20 launches with the window mapped, at a 25 ms cadence;
  the older bullet      -- THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s, 88/130 samples and
                           141 of 262 in another pass;
  and the same 25 ms census quoted inside the note shows 18/20 (19/20 without the cure).
The owner stop order forbids re-running the census, so this session CANNOT pick a winner. What it can do
is make sure the disagreement is not SILENT, at whichever end a reader lands on.

WHAT IT MEASURES, in AGENTS.md:
  1. both claims are still there (a note about a contradiction that has been edited away is stale);
  2. the RECONCILIATION note exists and names the instrument, both claims and the fact that no winner
     was chosen -- a note that quietly picked one would be the same defect in new clothes;
  3. BOTH ENDS: a pointer to that note sits within WINDOW lines of EACH claim. This is the arm the first
     run FAILED: the note existed only next to the gate bullet, so a reader who landed on the
     VISIBLE AT STARTUP bullet read a confident claim with no hint that the gate measures 0/20.
  --neg-arm removes the note marker from a COPY and requires the end that carried it to go RED.

NO LAUNCH: this reads one document.

EXIT CODES: the normal run is 0 PASS / 1 FAIL. `--neg-arm` is 1 BY DESIGN when it
passes (the negative arm is SUPPOSED to find the defect), 0 when the mutant was
NOT caught, and 2 when the anchor is missing or ambiguous -- a decorative mutant
is worse than no mutant at all, so the oracle refuses to count it.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
AGENTS = os.path.join(ROOT, "AGENTS.md")

GATE_CLAIM = "0/20 launches with the window mapped"
VISIBLE_CLAIM = "THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s"
POINTER = "NAO RECONCILIADO"
NO_WINNER = "escolhi um vencedor"
INSTRUMENT = "panel-startup-flash-census.py"
NUMBERS = ("0/20", "18/20", "19/20", "88/130", "141 de 262")
WINDOW = 40

# THE ANCHOR of the negative arm: the exact text of the reconciliation note.
# It must be UNIQUE in AGENTS.md -- an anchor that is missing (the oracle is
# stale) or that appears more than once (the mutation would hit the wrong end)
# is DECORATIVE, and a decorative mutant proves nothing. The oracle refuses to
# count it, says so, and exits != 0.
MUTANT_ANCHOR = "NAO RECONCILIADO (nota 2026-10-11)"


def ends(lines):
    """(gate claim line, visible claim line). The VISIBLE end must be the BULLET HEADING: the note also
    QUOTES that phrase in italics, and the first version matched the quotation -- so both ends collapsed
    into the note and the gate passed while the bullet itself still pointed nowhere. Measured."""
    gate = visible = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if gate is None and GATE_CLAIM in line:
            gate = index
        if visible is None and VISIBLE_CLAIM in line and stripped.startswith("- **"):
            visible = index
    return gate, visible


def pointer_at(lines, index):
    low = max(0, index - WINDOW)
    high = min(len(lines), index + WINDOW + 1)
    return any(POINTER in line for line in lines[low:high])


def check(text):
    lines = text.split("\n")
    failures = []
    gate, visible = ends(lines)
    if gate is None:
        failures.append("the gate claim is GONE from AGENTS.md: " + GATE_CLAIM)
    if visible is None:
        failures.append("the visible claim is GONE from AGENTS.md: " + VISIBLE_CLAIM)
    missing = [n for n in NUMBERS if n not in text]
    if missing:
        failures.append("numbers of the disagreement missing from the document: " + str(missing))
    if POINTER not in text:
        failures.append("the reconciliation note is gone (no " + POINTER + ")")
    if NO_WINNER not in text:
        failures.append("the note no longer says that no winner was chosen -- it may have picked one")
    if INSTRUMENT not in text:
        failures.append("the note does not name the instrument they disagree about")
    gate_end = bool(gate is not None and pointer_at(lines, gate))
    visible_end = bool(visible is not None and pointer_at(lines, visible))
    return {"failures": failures, "gate_end": gate_end, "visible_end": visible_end,
            "gate_line": (gate or 0) + 1, "visible_line": (visible or 0) + 1}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(AGENTS, encoding="utf-8") as handle:
        text = handle.read()
    say("panel-flash-contradiction-oracle -- rows #46/#F3, declared at both ends (no launch)")
    result = check(text)
    say("  gate claim at line %d, pointer within %d lines: %s"
        % (result["gate_line"], WINDOW, str(result["gate_end"]).lower()))
    say("  visible claim at line %d, pointer within %d lines: %s"
        % (result["visible_line"], WINDOW, str(result["visible_end"]).lower()))
    wrong = list(result["failures"])
    if not result["gate_end"]:
        wrong.append("a reader landing on the GATE bullet sees no sign of the disagreement")
    if not result["visible_end"]:
        wrong.append("a reader landing on the VISIBLE bullet sees no sign of the disagreement")

    if parsed.neg_arm:
        hits = text.count(MUTANT_ANCHOR)
        if hits != 1:
            say("NEG-ARM SETUP ERROR: the anchor %r appears %d time(s) in %s -- %s"
                % (MUTANT_ANCHOR, hits, os.path.basename(AGENTS),
                   "the oracle is stale" if hits == 0 else "the anchor is AMBIGUOUS"))
            say("")
            say("NEG-ARM FAIL -- a decorative mutant proves nothing; it was NOT counted")
            return 2
        mutant = text.replace(MUTANT_ANCHOR, "nota removida", 1)
        mutated = check(mutant)
        say("  mutant: gate_end=%s visible_end=%s note_present=%s"
            % (str(mutated["gate_end"]).lower(), str(mutated["visible_end"]).lower(),
               str(POINTER in mutant).lower()))
        flipped = []
        if result["gate_end"] and not mutated["gate_end"]:
            flipped.append("gate")
        if result["visible_end"] and not mutated["visible_end"]:
            flipped.append("visible")
        wrong = [w for w in wrong if "landing on" not in w]
        if not flipped:
            wrong.append("NEG-ARM: removing the note flipped NEITHER end -- the ends are not being "
                         "measured")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": removing the note must flip the end that carried it; flipped=" + str(flipped))
        # rc=1 BY DESIGN when it passes: the negative arm is SUPPOSED to find the
        # defect, so "found it" is a non-zero exit -- the battery's :expectred
        # recorder asks for exactly that. rc=0 means the mutant was NOT caught.
        # rc=2 (above) is a setup error: the mutant could not be prepared.
        return 1 if not wrong else 0

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the disagreement is declared at BOTH ends, with the instrument named, all the numbers"
        " present and the note saying that no winner was chosen (the owner order forbids re-measuring)")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
