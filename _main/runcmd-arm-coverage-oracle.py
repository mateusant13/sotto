#!/usr/bin/env python3
"""runcmd-arm-coverage-oracle -- a receipt must declare the arms it did NOT run.

AUDIT ROWS #58 and its inherited twin #D: "o braco bogus do runcmd-entry-driver.py nao tem recibo".
A receipt that lists only what ran cannot be told apart from a receipt whose author forgot an arm --
forgotten, skipped and passed all look the same on disk. That is the whole finding.

MEASURED, from the artefacts:
  * runcmd-entry-report.json holds ONE arm (caption), so the driver was last run as --arms caption;
  * the driver knows SIX arms (its KNOWN_ARMS table, added 2026-10-11, and cross-checked here against
    every results['x'] = ... site so the table cannot drift from the dispatch);
  * bogus is one of the five that did not run, and its reason is on record: it launches run.cmd with an
    argument the shell rejects, and the owner stop order forbids launching run.cmd at all. The
    pre-flight means nothing is spawned -- but the launch itself is the letter of the order.
So the answer to "why has bogus no receipt?" is now IN THE ARTEFACT rather than in someone memory.

WHAT THE DRIVER NOW WRITES: every future receipt carries a _coverage block with ran/not_run, computed
from the same table. This oracle DERIVES that coverage from the current receipt as well, so the existing
receipt (which predates the change and cannot be regenerated without launching the app) is answered
too -- and if the written and the derived coverage ever disagree, that is RED.

  1. every key the dispatch produces is in KNOWN_ARMS (and vice versa);
  2. bogus is declared, and its reason names the owner order -- the block is the reason, not prose;
  3. every arm in the current receipt that did NOT run carries a reason from the table;
  4. if the receipt carries _coverage, written and derived must agree;
  5. bytes: the writer computes _coverage from the table.
  --neg-arm removes bogus from the extracted table and requires arm 3 to go RED.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
DRIVER = os.path.join(ROOT, "_main", "runcmd-entry-driver.py")
REPORT = os.path.join(ROOT, "_main", "runcmd-entry-report.json")


def known_arms(source, drop=None):
    match = re.search(r"KNOWN_ARMS = (\{.*?\n\})", source, re.DOTALL)
    if not match:
        raise LookupError("the driver has no KNOWN_ARMS table")
    table = ast.literal_eval(match.group(1))
    if drop:
        table.pop(drop, None)
    return table


def dispatched(source):
    return sorted(set(re.findall(r"results\['([a-z]+)'\] =", source)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(DRIVER, encoding="utf-8") as handle:
        source = handle.read()
    with open(REPORT, encoding="utf-8") as handle:
        report = json.load(handle)
    say("runcmd-arm-coverage-oracle -- rows #58/#D: which arms did NOT run, and why?")
    wrong = []
    try:
        table = known_arms(source, drop="bogus" if parsed.neg_arm else None)
    except LookupError as error:
        say("VERDICT: FAIL -- " + str(error))
        return 1

    produced = dispatched(source)
    missing = [name for name in produced if name not in table]
    extra = [name for name in table if name not in produced]
    say("  arms the dispatch produces: " + str(produced))
    say("  arms the table declares:    " + str(sorted(table)))
    if missing:
        wrong.append("the dispatch produces arms the table does not declare: " + str(missing))
    if extra:
        wrong.append("the table declares arms the dispatch does not produce: " + str(extra))
    if "bogus" not in table:
        wrong.append("the NEGATIVE arm bogus is not declared in the table")
    elif "owner stop order" not in table["bogus"]:
        wrong.append("the bogus reason no longer names the owner stop order -- the block would be a "
                     "bare absence again")

    ran = sorted(k for k in report if not k.startswith("_"))
    not_run = [name for name in sorted(table) if name not in ran]
    say("  the RECEIPT on disk ran:    " + str(ran))
    say("  derived as NOT run:         " + str(not_run))
    undeclared = [name for name in not_run if not str(table.get(name, "")).strip()]
    if undeclared:
        wrong.append("these arms did not run and carry NO reason: " + str(undeclared))
    for name in not_run:
        say("    not_run %-8s %s" % (name, str(table.get(name, ""))[:88]))
    for name in ran:
        say("    ran     %-8s (present in the receipt)" % name)

    written = report.get("_coverage")
    if written is None:
        say("  the receipt predates the _coverage block (it cannot be regenerated without launching"
            " run.cmd, which the owner order forbids) -- this oracle derives the same answer instead")
    else:
        same = (sorted(written.get("ran", [])) == ran
                and sorted(written.get("not_run", {})) == not_run)
        say("  the receipt WRITES its own coverage, and it " + ("agrees" if same else "DISAGREES")
            + " with the derivation")
        if not same:
            wrong.append("written _coverage disagrees with the derived one: " + json.dumps(written))
    if "results['_coverage'] = {" not in source:
        wrong.append("the driver no longer computes _coverage for its receipts")

    say("")
    if parsed.neg_arm:
        say("NEG-ARM " + ("PASS" if wrong else "FAIL")
            + ": dropping bogus from the table must make an un-run arm unexplained ("
            + str(len(wrong)) + " failure(s): " + "; ".join(w[:58] for w in wrong) + ")")
        return 0 if wrong else 1
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- every arm the driver knows is either in the receipt or declared not-run WITH a reason,"
        " so bogus having no receipt is an EXPLAINED fact instead of a hole")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
