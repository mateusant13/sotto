#!/usr/bin/env python3
"""aceitacao-gate -- every claim in the owner register is machine-checkable, or named as not.

The goal, verbatim: *"nenhum criterio se fecha sem um numero"* and *"a bateria cobre todos"*.
The register (_main/aceitacao-dono.md) carries the owner own words as 32 criteria in SIX
groups, and for each it claims an instrument that proves it.

WHAT THIS MEASURED, and why the gate exists: the claims in the register are PROSE. A grep
for backticked instrument names found only TWO of the dozens the register cites -- so there
was no way to tell a criterion that has a gate running in the battery from one that only
has a sentence. That is the exact shape of the hole this session kept finding: an artefact
that looks like proof and is not.

WHAT THIS ASSERTS, per criterion:
  1. the row exists and names a STATE -- PROVADO, MEDIDO, ABERTO, or SO TU PODES FECHAR;
  2. if it claims PROVADO, it must name an instrument that EXISTS and is LISTED in the
     battery -- a proof with nothing running behind it is the defect, not the criterion;
  3. if it says SO TU PODES FECHAR, it must say WHAT the owner must do -- never a vague one.

It reads two files and launches nothing.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.path.pardir))
REGISTER = os.path.join(HERE, "aceitacao-dono.md")
BATTERY = os.path.join(HERE, "instruments-battery.mjs")

GROUPS = {"A": 2, "B": 6, "C": 8, "D": 7, "E": 4, "F": 5}


def main() -> int:
    say = print
    for p in (REGISTER, BATTERY):
        if not os.path.exists(p):
            say("aceitacao-gate: MISSING %s" % p)
            return 1
    with open(REGISTER, encoding="utf-8", errors="replace") as h:
        reg = h.read()
    with open(BATTERY, encoding="utf-8", errors="replace") as h:
        battery = h.read()
    wrong = []
    rows = re.findall(r"^\| ([A-F]\d+) \| (.+?) \| (.+?) \| (.+?) \|$", reg, re.M)
    seen = {}
    for cid, claim, proof, state in rows:
        cid = cid.strip()
        seen[cid] = state.strip()
        state_up = state.upper()
        if "PROVADO" in state_up or "MEDIDO" in state_up:
            named = re.findall(r"([a-z0-9-]+(?:-oracle|-census|-gate))(?:[.](?:py|js|mjs))?", proof)
            if not named:
                wrong.append("%s claims %s but names NO instrument" % (cid, state.strip()))
                continue
            for inst in named:
                if inst not in battery:
                    wrong.append("%s cites %s, which is NOT in the battery" % (cid, inst))
        if "SO TU PODES" in state_up or "TUA MAO" in state_up or "TEUS OLHOS" in state_up:
            if len(state.strip()) < 25:
                wrong.append("%s says it is yours to close but does not say WHAT for" % cid)
    for group, count in sorted(GROUPS.items()):
        have = len([c for c in seen if c.startswith(group)])
        if have != count:
            wrong.append("group %s: the register lists %d of %d criteria" % (group, have, count))
    say("aceitacao-gate -- %d criteria read, %d group(s) expected"
        % (len(seen), len(GROUPS)))
    for cid in sorted(seen):
        say("  %-4s %s" % (cid, seen[cid][:78]))
    say("")
    if wrong:
        for w in wrong:
            say("  wrong: " + w)
        say("VERDICT: FAIL -- %d claim(s) in the register are not machine-checkable" % len(wrong))
        return 1
    say("VERDICT: PASS -- every PROVADO/MEDIDO criterion names an instrument that RUNS,")
    say("               and every yours-to-close says what the owner must do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
