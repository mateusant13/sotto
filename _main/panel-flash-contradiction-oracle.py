#!/usr/bin/env python3
"""panel-flash-contradiction-oracle -- a number about the panel flash must carry its POPULATION.

HISTORY, because this gate changed sides on 2026-11-12 and the reason matters.

AUDIT ROWS #46 and F3: "AGENTS.md contradicts itself about the panel at startup (0 of 41 vs visible
50 ms-7 s)". The oracle born from that row pinned the CONTRADICTION itself: it required two claim
phrases, three numbers, the word "NÃO reconciliada" and the sentence "no winner was chosen". It
enforced, in other words, that nobody may ever settle the question -- and it passed for a month
while the numbers underneath it were being deleted.

What was measured on 2026-11-12, WITHOUT re-running the census (the owner stop order forbids it):

  * the only surviving census run (`_main/fixtures/panel-startup-flash-census-20261011.log`) reads,
    through the census's own pure reader:
        ARM-SUMMARY-READ arm=live launches=19/20 launches_with_mech=3/19
                         launches_at_startup=0/19 longest_mech_ms=663
    i.e. the CURED shell painted in 3 of 19 launches and NOT ONE episode was at startup -- all
    three land after `PANEL_VISIBILITY_INVARIANT`, two of them right after `TRAY_MENU`.
  * `18/20` is a DIFFERENT arm: the census docstring names `nogate-nonet` as "the state AGENTS.md
    measured at 18/20" (gate AND re-assert removed). It is the pre-fix number, not a rival reading
    of the same one.
  * `0/20` and `run.cmd`'s `11 de 20` have NO log on disk, and cannot get one without a re-run.
    Their honest value is `UNMEASURED aqui`.
  * the reason no log survived: the census's own `log()` opened the evidence file with `'w'` on
    every line, so each invocation erased the previous run (measured: one `--read` left 42 B of a
    4 073 B log).

So the defect was never "two claims disagree". It was: numbers published without the arm, launch
count and phase that make them mean anything, by an instrument that deleted the population. This
gate now enforces the FIX side: every number in the bullet names its arm and its log, the measured
facts are present, and the resolved state is stated instead of frozen.

WHAT IT MEASURES, in AGENTS.md (each a separate arm; each fails on its own):
  A1 the instrument is named (`panel-startup-flash-census.py`);
  A2 the pure reader is named (`--read`), so a number can be re-checked without the owner's screen;
  A3 the surviving log is named (`panel-startup-flash-census-20261011.log`);
  A4 the LIVE arm's own figure is present, with its launch count and phase
     (`launches_with_mech=3/19`, `launches_at_startup=0/19`);
  A5 `18/20` sits within WINDOW lines of `nogate-nonet` (the arm it belongs to);
  A6 every number WITHOUT a log sits within WINDOW lines of `UNMEASURED`;
  A7 the resolved state is stated and the frozen wording is GONE (`NÃO reconciliada` absent);
  A8 the erasure is on record (`apagava o log`), or the next instrument repeats it.

  --neg-arm plants THREE mutations, each on a different arm, and requires each one to be caught
  by ITS OWN arm: (M1) delete the measured phase fact -> A4 red; (M2) re-insert the frozen wording
  -> A7 red; (M3) strip the arm name from `18/20` -> A5 red. A mutant caught by "something else"
  does not count: the report says which arm caught which mutation.

NO LAUNCH: this reads one document and one fixture log name (it does not open the log).

EXIT CODES: normal run 0 PASS / 1 FAIL. `--neg-arm` is 1 BY DESIGN when all three mutants are
caught (the battery's `:expectred` asks for exactly that), 0 when a mutant escaped, 2 when a
mutation could not be prepared (a decorative mutant is worse than none).
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
AGENTS = os.path.join(ROOT, "AGENTS.md")

WINDOW = 40

INSTRUMENT = "panel-startup-flash-census.py"
READER = "--read"
SURVIVING_LOG = "panel-startup-flash-census-20261011.log"
LIVE_FIGURE = "launches_with_mech=3/19"
PHASE_FIGURE = "launches_at_startup=0/19"
PREFIX_ARM = "nogate-nonet"
NO_LOG_MARK = "UNMEASURED"
RESOLVED_ABSENT = "NÃO reconciliada"
ERASURE = "apagava o log"

# Every number the bullet may quote, and what must sit beside it. A number that
# names no population is the defect this gate exists for.
NUMBERS = ("3/19", "18/20", "0/20", "11 de 20")


def near(lines, phrase, needle, window=WINDOW):
    """True iff `phrase` occurs and `needle` sits within `window` lines of it."""
    for index, line in enumerate(lines):
        if phrase in line:
            low = max(0, index - window)
            high = min(len(lines), index + window + 1)
            if any(needle in chunk for chunk in lines[low:high]):
                return True
    return False


def bullet_lines(text):
    lines = text.split("\n")
    for index, line in enumerate(lines):
        if INSTRUMENT in line:
            low = max(0, index - 6)
            high = min(len(lines), index + 20)
            return lines[low:high]
    return []


def check(text):
    lines = text.split("\n")
    scope = "\n".join(bullet_lines(text))
    failures = []

    if INSTRUMENT not in text:
        failures.append("A1 the instrument is not named: " + INSTRUMENT)
    if READER not in scope:
        failures.append("A2 the pure reader is not named in the bullet: " + READER)
    if SURVIVING_LOG not in scope:
        failures.append("A3 the surviving log is not named in the bullet: " + SURVIVING_LOG)
    if LIVE_FIGURE not in scope or PHASE_FIGURE not in scope:
        failures.append("A4 the live arm's own figures are missing (need %r and %r)"
                        % (LIVE_FIGURE, PHASE_FIGURE))
    if "18/20" in text and not near(lines, "18/20", PREFIX_ARM):
        failures.append("A5 18/20 does not name its arm (%s) within %d lines"
                        % (PREFIX_ARM, WINDOW))
    for orphan in ("0/20", "11 de 20"):
        if orphan in text and not near(lines, orphan, NO_LOG_MARK):
            failures.append("A6 %r is quoted without %r within %d lines -- a number with no log and "
                            "no declaration is a claim" % (orphan, NO_LOG_MARK, WINDOW))
    if RESOLVED_ABSENT in text:
        failures.append("A7 the frozen wording is back (%r): the question is settled by population, "
                        "not by a permanent contradiction" % RESOLVED_ABSENT)
    if ERASURE not in scope:
        failures.append("A8 the erasure of the evidence is not on record (%r) -- the next "
                        "instrument will repeat it" % ERASURE)
    for number in NUMBERS:
        if number not in text:
            failures.append("the number %r disappeared from the record" % number)
    return failures


MUTANTS = (
    ("M1-A4", PHASE_FIGURE, "launches_at_startup=ALEGADO", "A4"),
    ("M2-A7", "Corrigido: append com uma rotacao",
     "NÃO reconciliada: append com uma rotacao", "A7"),
    ("M3-A5", "braco `nogate-nonet`", "braco `qualquer-outro`", "A5"),
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(AGENTS, encoding="utf-8") as handle:
        text = handle.read()
    say("panel-flash-contradiction-oracle -- a flash number carries its population (no launch)")
    failures = check(text)
    for line in bullet_lines(text):
        if INSTRUMENT in line:
            say("  locus: %s" % line.strip()[:110])
            break

    if parsed.neg_arm:
        if failures:
            say("NEG-ARM SETUP ERROR: the BASE document already fails, so a mutation proves nothing:")
            for item in failures:
                say("  base: " + item)
            say("")
            say("NEG-ARM FAIL -- not counted")
            return 2
        missed = []
        caught_by = []
        for tag, old, new, arm in MUTANTS:
            hits = text.count(old)
            # O MUTANTE ATINGE TODAS AS OCORRENCIAS, e o zero continua a ser
            # erro de setup (medido 2026-11-12): a figura do M1
            # (`launches_at_startup=0/19`) passou a estar citada DUAS vezes no
            # `AGENTS.md` -- no bullet vivo e na nota do pin que registra o
            # numero antigo -- e a exigencia de ocorrencia UNICA respondia
            # `ambiguous` com rc=2, deixando o passo
            # `red-as-expected-panel-flash-contradiction` RED por um controlo que
            # nao chegava a correr. A intencao do mutante e' "a figura esta
            # errada", e isso vale em todas as copias dela; um numero novo que
            # apareca no texto nao pode transformar o controlo num erro.
            if hits == 0:
                say("NEG-ARM SETUP ERROR: mutation %s anchor %r occurs 0 time(s) -- "
                    "the oracle is stale" % (tag, old[:50]))
                say("")
                say("NEG-ARM FAIL -- a decorative mutant proves nothing; it was NOT counted")
                return 2
            mutant_failures = check(text.replace(old, new))
            mine = [f for f in mutant_failures if f.startswith(arm)]
            if mine:
                caught_by.append("%s->%s" % (tag, arm))
                say("  caught %s by %s: %s" % (tag, arm, mine[0][:90]))
            else:
                missed.append(tag)
                say("  MISSED %s: no %s failure (got %s)"
                    % (tag, arm, [f[:40] for f in mutant_failures]))
        say("")
        if missed:
            say("NEG-ARM FAIL: mutants that escaped = %s" % missed)
            return 0
        say("NEG-ARM PASS: %d/%d mutants, each caught by its own arm (%s)"
            % (len(MUTANTS), len(MUTANTS), ", ".join(caught_by)))
        return 1

    say("")
    say("VERDICT: " + ("PASS" if not failures else "FAIL")
        + " -- every flash number names its arm, its launch count and its phase; the surviving log"
          " is citable without re-running the census, and the frozen contradiction is gone")
    for item in failures:
        say("  wrong: " + item)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
