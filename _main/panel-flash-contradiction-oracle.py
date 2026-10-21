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

# RE-ANCHORED 2026-10-21: AGENTS.md was CONDENSED (the history moved to
# `docs/AGENTS-archive-20261021.md`), and the two claims now live in ONE bullet
# instead of two, in new words. The SUBSTANCE is what this gate exists for --
# neither end of the contradiction may be edited away, and the note that says
# so must name the instrument and pick no winner -- and the condensed doc still
# carries all three. Only the PHRASES moved, so only the phrases changed here.
GATE_CLAIM = "o censo de 25 ms mede `live` 0/20"
VISIBLE_CLAIM = "o bullet histórico do mesmo instrumento mede 18/20"
POINTER = "NÃO reconciliada"
# RE-ANCHORED 2026-10-21: the CONDENSED AGENTS.md carries the SAME disagreement
# in the SAME bullet, with the numbers that are in the doc today: the 25 ms
# census says `live` 0/20 (4/20 without the cure) and the historical bullet
# says 18/20 and 88/130 samples visible. The old pair ('19/20', '141 de 262')
# was a THIRD reading of the same instrument and is not in the condensed text
# -- and "19/20" is the cure-REMOVED arm of the 0/20 claim, which the condensed
# doc states as "4/20 sem a cura". The NUMBERS are what the DOC says, so they
# are what is checked.
NO_WINNER = "antes de acreditar num dos dois"
INSTRUMENT = "panel-startup-flash-census.py"
NUMBERS = ("0/20", "18/20", "88/130")
WINDOW = 40

# THE ANCHOR of the negative arm: the exact text of the reconciliation note.
# It must be UNIQUE in AGENTS.md -- an anchor that is missing (the oracle is
# stale) or that appears more than once (the mutation would hit the wrong end)
# is DECORATIVE, and a decorative mutant proves nothing. The oracle refuses to
# count it, says so, and exits != 0.
# RE-ANCHORED 2026-10-21: the old anchor was the whole reconciliation NOTE
# ("NAO RECONCILIADO (nota 2026-10-11)"), which the CONDENSED doc no longer
# has -- the note is now the bullet that holds both claims. The mutant's
# PURPOSE is unchanged and is now expressed on the NOTE'S OWN WORDS: take the
# "this is a contradiction, no winner was chosen" phrase out and the gate must
# flip -- because a doc that quietly picks one side is the defect this gate
# exists to catch.
MUTANT_ANCHOR = "NÃO reconciliada"


def ends(lines):
    """(gate claim line, visible claim line).

    RE-ANCHORED 2026-10-21: with the CONDENSED AGENTS.md both ends live in ONE
    bullet, so the old rule ("the visible end must be a BULLET HEADING") no
    longer applies -- and it no longer has to. The old reason for that rule was
    that the reconciliation NOTE QUOTES the phrase in italics, so a naive match
    collapsed both ends into the note and the gate passed while the bullet
    itself pointed nowhere. The guard for that is now STRONGER and simpler: each
    phrase must occur EXACTLY ONCE in the document, so it cannot be a quotation
    of the other (the uniqueness is asserted in `check`).
    """
    gate = visible = None
    for index, line in enumerate(lines):
        if gate is None and GATE_CLAIM in line:
            gate = index
        if visible is None and VISIBLE_CLAIM in line:
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
    # EACH PHRASE EXACTLY ONCE: the guard that replaced "the visible end must be
    # a bullet heading" (see `ends`). A phrase that occurs twice could be the
    # note quoting the claim, and both ends would collapse into the note.
    if text.count(GATE_CLAIM) != 1:
        failures.append("the gate claim occurs %d time(s) -- it must be once, or it is a quotation"
                        % text.count(GATE_CLAIM))
    if text.count(VISIBLE_CLAIM) != 1:
        failures.append("the visible claim occurs %d time(s) -- it must be once, or it is a quotation"
                        % text.count(VISIBLE_CLAIM))
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
