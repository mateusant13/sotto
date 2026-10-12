#!/usr/bin/env python3
"""inherited-row-reconciler -- the same finding cannot be OPEN and APPLIED at once.

WHY. The audit map carries two kinds of row: the PRIMARY rows (numbered #1..#63, one per finding)
and INHERITED rows, which repeat a finding as another document reported it and SAY SO in the text:
"herdado da linha #NN". Those inherited rows carry their own ids (F1, F3, F8 ...) which COLLIDE
across documents, so nothing that groups by id can pair them -- measured 2026-10-11: the id-based
duplicate check found four duplicated NUMBERED rows and could not see these at all.

WHAT IT MEASURES, mechanically, from the inheritance the row itself declares: if an inherited row
reads OPEN while the row it names is APPLIED, then the SAME finding is being counted twice in two
different states, and the OPEN count is inflated by exactly those rows. The link is in the text, so
this is a lookup, not an opinion.

BOTH COLOURS. `--neg-arm` builds a mutant map in which a reconciled row is left alone but one of its
PRIMARY rows is reverted to OPEN: the reconciler must then refuse to call that inherited row stale
(it must be able to say "genuinely open"), and must still repair the others.

`--apply` rewrites the stale rows state cell to APPLIED and cites the primary row. NO LAUNCH: text.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MAP = os.path.join(ROOT, "docs", "audit", "00-MAPA-CONSOLIDADO.md")

#: A numbered primary row. Anchored at the start of a line and requiring the numeric id cell.
PRIMARY = re.compile(r"^\|\s*(\d{1,3})\s*\|")
ANY_ROW = re.compile(r"^\|\s*([A-Za-z][A-Za-z0-9 ]{0,14}|\d{1,3})\s*\|")
INHERITS = re.compile(r"herdado da linha\s*#?(\d{1,3})", re.IGNORECASE)

#: The state words this map uses, in the order they must be tested: APPLIED wins over OPEN because a
#: long APPLIED cell can quote the word OPEN.
def state_of(line):
    if "APPLIED" in line:
        return "APPLIED"
    if "IN-FLIGHT" in line:
        return "IN-FLIGHT"
    if "OPEN" in line:
        return "OPEN"
    return "?"


def scan(text):
    lines = text.split("\n")
    primary = {}
    inherited = []
    for index, line in enumerate(lines):
        if not ANY_ROW.match(line):
            continue
        state = state_of(line)
        match = PRIMARY.match(line)
        if match:
            primary[match.group(1)] = {"line": index, "state": state}
            continue
        link = INHERITS.search(line)
        if link:
            inherited.append({"line": index, "refers_to": link.group(1), "state": state,
                              "id": line.split("|")[1].strip()})
    stale = [row for row in inherited
             if row["state"] == "OPEN"
             and primary.get(row["refers_to"], {}).get("state") == "APPLIED"]
    genuinely_open = [row for row in inherited
                      if row["state"] == "OPEN" and row not in stale]
    return {"primary": primary, "inherited": inherited, "stale": stale,
            "genuinely_open": genuinely_open}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default=MAP)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    text = open(parsed.map, encoding="utf-8").read()

    if parsed.neg_arm:
        # A SYNTHETIC fixture, not the live map: once the live map is reconciled it has no stale row
        # left, and an instrument that can only be tested BEFORE its own fix cannot be re-tested
        # after it (measured design error, 2026-10-11). The fixture carries one pair of each kind.
        fixture = "\n".join([
            "| 12 | a finding that is PAID | where | **APPLIED** — proof |",
            "| 77 | a finding that is NOT paid | where | **OPEN** |",
            "| F3 | the paid one, as another doc filed it | **OPEN** — herdado da linha #12 |",
            "| F9 | the unpaid one, as another doc filed it | **OPEN** — herdado da linha #77 |",
        ])
        first = scan(fixture)
        reverted = fixture.replace("| 12 | a finding that is PAID | where | **APPLIED** — proof |",
                                   "| 12 | a finding that is PAID | where | **OPEN** |")
        second = scan(reverted)
        wrong = []
        if len(first["stale"]) != 1:
            wrong.append("fixture: expected exactly 1 stale row, got " + str(len(first["stale"])))
        if len(first["genuinely_open"]) != 1:
            wrong.append("fixture: expected exactly 1 genuinely-open row, got "
                         + str(len(first["genuinely_open"])))
        if second["stale"]:
            wrong.append("reverted fixture still reported stale rows: "
                         + str([r["id"] for r in second["stale"]]))
        if len(second["genuinely_open"]) != 2:
            wrong.append("reverted fixture should have BOTH rows genuinely open, got "
                         + str(len(second["genuinely_open"])))
        say("  fixture stale            " + str(len(first["stale"])))
        say("  fixture genuinely_open   " + str(len(first["genuinely_open"])))
        say("  reverted stale           " + str(len(second["stale"])))
        say("  reverted genuinely_open  " + str(len(second["genuinely_open"])))
        say("")
        say("NEG-ARM: the fixture must read one stale and one genuinely-open row, and reverting the"
            " PRIMARY must move its inherited row to genuinely-open; wrong: " + str(wrong))
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL"))
        return 0 if not wrong else 1

    found = scan(text)
    say("inherited-row-reconciler -- one finding, one state (no launch)")
    say("  primary rows seen        " + str(len(found["primary"])))
    say("  inherited rows seen      " + str(len(found["inherited"])))
    say("  inherited + OPEN         " + str(len(found["stale"]) + len(found["genuinely_open"])))
    say("  ... of which GENUINELY open (their primary is open too): "
        + str(len(found["genuinely_open"])))
    say("")
    for row in found["stale"]:
        say("  STALE-OPEN  " + row["id"].ljust(10) + "line " + str(row["line"] + 1).ljust(6)
            + "refers to #" + row["refers_to"] + " which is APPLIED")
    if not found["stale"]:
        say("VERDICT: PASS -- no inherited row contradicts its own primary row")
        return 0
    if parsed.apply:
        lines = text.split("\n")
        for row in found["stale"]:
            lines[row["line"]] = lines[row["line"]].replace(
                "**OPEN**",
                "**APPLIED** — herdado da linha #" + row["refers_to"]
                + ", que esta APPLIED: mesmo achado, mesma prova (reconciliado 2026-10-11)", 1)
        with open(parsed.map, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines))
        after = scan("\n".join(lines))
        say("")
        say("APPLIED to " + str(len(found["stale"])) + " row(s); stale now " + str(len(after["stale"])))
        say("VERDICT: PASS -- every inherited row now agrees with the row it names")
        return 0 if not after["stale"] else 1
    say("")
    say("VERDICT: FAIL -- " + str(len(found["stale"]))
        + " inherited row(s) read OPEN while the row they name is APPLIED:"
        " the same finding is counted twice, in two states. Re-run with --apply to reconcile.")
    return 1


if __name__ == "__main__":
    sys.exit(main())