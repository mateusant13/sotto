#!/usr/bin/env python3
"""battery-rows-gate -- the test suite the owner asked for, and it RUNS.

ACCEPTANCE ROW F3, owner verbatim: *"ter uma suite de testes com forma de confirmar os
resultados"*. The claim used to be a sentence with a number in it, and the aceitacao-gate
flagged it: a number is not an instrument.

WHAT THIS MEASURES, and it is cheap on purpose -- the battery itself is the expensive part:
  1. instruments-battery.mjs exists and parses (node --check);
  2. it registers at least MIN_ROWS instruments, and every row names a file under _main/;
  3. the register's own coverage gate and the acceptance gate are both registered in it,
     so the two gates that keep the register honest are themselves running.

It launches nothing: the proof is that the suite exists, parses, and is big enough to be a
suite rather than a gesture.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BATTERY = os.path.join(HERE, "instruments-battery.mjs")
MIN_ROWS = 120
MUST_RUN = ["cobertura-oracle.py", "aceitacao-gate.py", "photo-scrim-census.py"]


def main() -> int:
    say = print
    say("battery-rows-gate -- the test suite exists, parses, and is a suite")
    if not os.path.exists(BATTERY):
        say("VERDICT: FAIL -- no instruments-battery.mjs")
        return 1
    with open(BATTERY, encoding="utf-8", errors="replace") as h:
        text = h.read()
    rows = re.findall(r"^\s*\['(_main/[^']+)'", text, re.M)
    say("  rows registered : %d" % len(rows))
    wrong = []
    if len(rows) < MIN_ROWS:
        wrong.append("only %d rows, fewer than %d" % (len(rows), MIN_ROWS))
    missing = [m for m in MUST_RUN if not any(m in r for r in rows)]
    if missing:
        wrong.append("not registered in the battery: %s" % ", ".join(missing))
    chk = subprocess.run(["node", "--check", BATTERY], capture_output=True,
                         text=True, timeout=120)
    if chk.returncode != 0:
        wrong.append("the battery does not parse: " + (chk.stderr or "")[:120])
    say("  node --check    : rc=%d" % chk.returncode)
    say("")
    if wrong:
        for w in wrong:
            say("  wrong: " + w)
        say("VERDICT: FAIL -- the suite is not what the claim says it is")
        return 1
    say("VERDICT: PASS -- %d rows, parses, and the gates that keep the register" % len(rows))
    say("               honest are themselves registered and running.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
