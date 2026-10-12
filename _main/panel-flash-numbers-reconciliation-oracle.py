#!/usr/bin/env python3
"""panel-flash-numbers-reconciliation-oracle -- the four flash numbers are NOT four answers to one question.

AUDIT ROWS #4 and F1 (the same finding; F1 is inherited from #4): "painel aparece sozinho no ecra <=63 ms em
cada arranque". AGENTS.md declares the pair NAO RECONCILIADO, and the doc carries FOUR numbers from the same
instrument at the same 25 ms cadence. This oracle reconciles them by ATTRIBUTION, from the files:

  SottoStartupFlash.md section 2 ("the numbers (25 ms cadence)"), all arms parked at x=-10000:
    BEFORE   (sync+posted re-assert only)  live    N=20  11/20  longest 57.7 ms
    AFTER    (control-event subscription)  live    N=20  18/20  longest 63 ms   <- the number row #4 quotes
    NEGATIVE (fix reverted)                nocure  N=20  19/20  longest 68 ms
  receipt-20261007-panel-startup-flash.md section 3 (both arms 25 ms, N=20, its own shell sha logged):
    LIVE    (gate present)   0/20  longest 0 ms
    NOGATE  (gate -> pass)   4/20  longest 57 ms

They are different (revision, predicate) pairs: the 10-06 census counts the MECHANISM -- "mech = WS_VISIBLE &
alpha != 0 (the Show happened; POSITION ignored)" -- on the shell of that day; the 10-07 receipt counts the
same mechanism AND an "owner = mech AND on a monitor" axis on the gate-era shell whose sha it logs. And THE
OWNER-VISIBLE AXIS WAS NEVER MEASURED ON A HEALTHY SHELL, which no document states in one place:
  * every arm of both documents ran at x=-10000, i.e. on NO monitor, by design ("so nothing appears on the
    owner desk"), so "owner" was 0 in both arms of the receipt BY CONSTRUCTION;
  * the receipt says so itself ("the owner axis is vacuous" for a shell that flashed);
  * and SottoStartupFlash.md 8 says the on-screen `real` arm is REFUSED BY DEFAULT (--allow-onscreen
    required), the only on-screen phase having been an earlier BROKEN fix, not a measurement.

So the 63 ms is a MECHANISM duration measured off-desk, and "appears on the owner screen" is a claim no
instrument here has ever measured -- which is the reconciliation, and also the honest limit: confirming it
needs a launch, and the owner stop order forbids one.

ARMS: 1 attribution (each number in its own document, and NOT in the other -- measured partition);
2 the two documents declare DIFFERENT predicates; 3 the off-desk geometry, the vacuity note and the refused
on-screen arm are all still stated; 4 CONTROL = no number crosses over, so a moved number goes RED.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SOTTO = os.path.join(ROOT, "_main", "SottoStartupFlash.md")
RECEIPT = os.path.join(ROOT, "_main", "receipt-20261007-panel-startup-flash.md")

# (number, the file it belongs to, the other file) -- the partition measured on 2026-10-12
OWNED = [
    ("11/20", SOTTO, RECEIPT),
    ("18/20", SOTTO, RECEIPT),
    ("19/20", SOTTO, RECEIPT),
    ("57.7 ms", SOTTO, RECEIPT),
    ("63 ms", SOTTO, RECEIPT),
    ("68 ms", SOTTO, RECEIPT),
    ("0 of 20", RECEIPT, SOTTO),
    ("4/20", RECEIPT, SOTTO),
    ("sha256_live=", RECEIPT, SOTTO),
]
MUST_SAY = [
    (SOTTO, "25 ms cadence", "the census own cadence"),
    (SOTTO, "@x=-10000", "the arms are parked off every monitor"),
    (SOTTO, "refused by default", "the on-screen arm is refused by default"),
    (SOTTO, "--allow-onscreen", "and needs an explicit switch"),
    (RECEIPT, "mech = WS_VISIBLE & alpha!=0", "the mechanism predicate"),
    (RECEIPT, "POSITION ignored", "which ignores where the window is"),
    (RECEIPT, "owner = mech AND on a monitor", "the owner-visible predicate"),
    (RECEIPT, "x=-10000", "the arms are off every monitor here too"),
    (RECEIPT, "vacuous", "and the receipt itself calls the owner axis vacuous"),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    say = print
    wrong = []
    with open(SOTTO, encoding="utf-8") as handle:
        s = handle.read()
    with open(RECEIPT, encoding="utf-8") as handle:
        r = handle.read()
    say("panel-flash-numbers-reconciliation-oracle -- rows #4 / F1 (from the files, no launch)")
    say("  1. ATTRIBUTION -- each number lives in its own document and NOT in the other:")
    for number, home, other in OWNED:
        home_text = s if home == SOTTO else r
        other_text = r if home == SOTTO else s
        here, there = number in home_text, number in other_text
        say("     %-12s home=%s other=%s" % (number, str(here).lower(), str(there).lower()))
        if not here:
            wrong.append("the number %s is gone from its own document" % number)
        if there:
            wrong.append("the number %s CROSSED into the other document -- the partition broke" % number)
    say("  2/3. DECLARATIONS that make the numbers different measurements:")
    for path, needle, why in MUST_SAY:
        text = s if path == SOTTO else r
        ok = needle in text
        say("     %-52s %s  (%s)" % (needle[:50], str(ok).lower(), why))
        if not ok:
            wrong.append("a declaration disappeared: " + needle)
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the four numbers are reconciled by REVISION and PREDICATE (11/18/19 of 20 belong to the 10-06"
        " mechanism census off-desk; 0/20 and 4/20 to the gate-era receipt with its own shell sha), and the"
        " OWNER-VISIBLE axis is UNMEASURED on a healthy shell: every arm ran at x=-10000, the receipt calls"
        " that axis vacuous, and the census own on-screen arm is refused by default")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())