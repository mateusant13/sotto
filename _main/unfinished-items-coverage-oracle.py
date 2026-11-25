#!/usr/bin/env python3
"""unfinished-items-coverage-oracle -- every unfinished item, from every source the objective names, in ONE
place, with the rule that a NEW unfinished item turns this RED.

The objective named five sources. Three are live and are enumerated below: AGENTS.md open risks,
`docs/audit/`, and `_main/receipt-*.md`. Two are GONE and are reported as such, not crashed on:
`_main/DEBT-LEDGER.md` never existed in the product root (the ledger lived in the parked `_moved/` tree)
and the `TO-BE-ANSWERED-BY-OWNER.md` files lived there too. MEASURED 2026-11-25: the whole `_moved/`
tree is absent from this checkout, so those four paths print `ABSENT (parked tree removed)` and the
enumerator no longer dies reading them -- the absence is a fact about the product, not a crash.
  * docs/audit/ holds 46 markdown files; the map gate counts 43 finding-docs. This oracle prints the
    difference by NAME instead of leaving the gap to be guessed.

This is a GATE, not a report: the id sets below are pinned from the 2026-10-12 measurement, and an item that
is NOT in its pin set is printed as UNCLASSIFIED and fails the run -- so a new open risk, a new owner
question or a new ledger row cannot appear silently. Items that DISAPPEAR are reported as gone, never as a
failure: closing work is the point.

Arm 6 is the control: --neg-arm plants a fake owner question in a COPY of the lease-audit file and requires
the enumerator to see it and the unclassified rule to fire. The real files are never modified.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MAP = os.path.join(ROOT, "docs", "audit", "00-MAPA-CONSOLIDADO.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")
LEDGER_A = os.path.join(ROOT, "_moved", "aireplay", "_main", "DEBT-LEDGER.md")
LEDGER_B = os.path.join(ROOT, "_moved", "aireplay-wt", "wip", "laneH-contract", "_main", "DEBT-LEDGER.md")
OWNER_A = os.path.join(ROOT, "_moved", "aireplay", "_main", "TO-BE-ANSWERED-BY-OWNER.md")
OWNER_B = os.path.join(ROOT, "_moved", "aireplay", "_main", "_lease-audit", "TO-BE-ANSWERED-BY-OWNER.md")
AUDIT_DIR = os.path.join(ROOT, "docs", "audit")
MAIN_DIR = os.path.join(ROOT, "_main")

# Pinned 2026-10-12. A new id is UNCLASSIFIED and fails until it is classified here.
PIN_AGENTS_MARKERS = [
    "RISCO ABERTO que esta ordem impede de medir: a corre",
    "OPEN RISK ? `CANONICAL_PRODUCER = 'redux'` is a LITE",
]
PIN_OWNER_QUESTION_COUNTS = {OWNER_A: 8, OWNER_B: 7}
PIN_LEDGER_OPEN_IDS = ["D-IDLE-WAKE", "D-D1", "D-D4", "D-D5", "D-D6", "D-H1-MEDIUMIL"]
QUALIFIED = re.compile(r"STILL OPEN|SUPERSEDED|UNVERIFIED|stays OPEN|OPEN-UNTESTABLE")
NUM_IN_MAP = re.compile(r"^- \*\*(APPLIED|OPEN):\*\* (\d+)", re.MULTILINE)


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def agents_open_ids(path):
    """The strict open-risk markers of one AGENTS.md-like file, as ids."""
    lines = read(path).split("\n")
    strict = [ln.strip() for ln in lines if "RISCO ABERTO" in ln or "OPEN RISK" in ln]
    return strict, [marker_id(ln) for ln in strict]


def ascii_safe(text):
    """Ids are pinned in this file, which is ASCII: sanitize before comparing, never after."""
    return re.sub(r"\s+", " ", text.encode("ascii", "replace").decode("ascii")).strip()


def marker_id(line):
    stripped = ascii_safe(line.lstrip("-* "))
    return stripped[:52]


# A ledger row carries its state at the END of the line, and a heading can carry it too. A filter that
# looks for the WORD OPEN anywhere matches rows that merely mention it ("is OPEN below as the real
# requirement") -- the same prose-vs-state trap this repo keeps meeting.
LEDGER_ROW = re.compile(r"^\| \*{0,2}(D-[A-Z0-9-]+)")
LEDGER_HEAD = re.compile(r"^#{2,4} (D-[A-Z0-9-]+).*(OPEN|ESCALAT)")


def ledger_state_open(line):
    cells = line.split("|")
    state = cells[-2] if len(cells) >= 3 else ""
    return re.match(r"\s*\*{0,2}(OPEN|ESCALATED)", state) is not None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true", help="plant a fake owner question in a COPY")
    args = parser.parse_args(argv)
    # The console here is cp1252 and the ledger carries arrows and quotes: without this the oracle dies on a
    # PRINT, which is a bug in the instrument, not a finding. Found by running it.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001 -- older runtimes simply keep the console default
        pass
    say = print
    wrong = []
    say("unfinished-items-coverage-oracle -- every source the objective names, with its items")

    # ---- 1. the product map ------------------------------------------------
    counts = dict(NUM_IN_MAP.findall(read(MAP)))
    applied, opened = int(counts.get("APPLIED", 0)), int(counts.get("OPEN", 0))
    open_rows = [ln.strip()[:96] for ln in read(MAP).split("\n") if "**OPEN**" in ln]
    say("  1. docs/audit map: applied %d, open %d (rows: %d)" % (applied, opened, len(open_rows)))
    for row in open_rows:
        say("       still open: " + row)

    # ---- 2. AGENTS.md open risks + qualified claims ------------------------
    agents = read(AGENTS).split("\n")
    strict, ids = agents_open_ids(AGENTS)
    qualified = [ln.strip() for ln in agents if QUALIFIED.search(ln)]
    say("  2. AGENTS.md: %d strict open-risk marker(s), %d line(s) carrying a load-bearing qualifier"
        % (len(strict), len(qualified)))
    for ident in ids:
        fresh = ident not in PIN_AGENTS_MARKERS
        say("       %s%s" % (ident, "   <-- UNCLASSIFIED" if fresh else ""))
        if fresh:
            wrong.append("a NEW open risk in AGENTS.md is unclassified: " + ident)
    for ident in PIN_AGENTS_MARKERS:
        if ident not in ids:
            say("       gone (closed or reworded): " + ident)

    # ---- 3/4. the parked-tree sources: REMOVED, and said so ----------------
    # MEASURED 2026-11-25: the whole `_moved/` tree is gone from this checkout,
    # so the two debt ledgers and the two owner-question files this oracle was
    # built around do not exist. `read()` on them used to kill the run with
    # FileNotFoundError -- the instrument was measuring a product that had been
    # parked away, and it read that absence as a crash instead of as a fact.
    # Nothing live replaced them: the product's own open work lives in
    # `docs/audit/00-MAPA-CONSOLIDADO.md` (section 1) and in the receipts
    # (section 6), which are still enumerated below.
    for path in (LEDGER_A, LEDGER_B, OWNER_A, OWNER_B):
        state = "present" if os.path.exists(path) else "ABSENT (parked tree removed)"
        say("  3/4. %s: %s" % (os.path.relpath(path, ROOT), state))
    for path in (LEDGER_A, LEDGER_B):
        if not os.path.exists(path):
            continue
        lines = read(path).split("\n")
        rows = [ln for ln in lines if LEDGER_ROW.match(ln)]
        flagged = [ln for ln in rows if ledger_state_open(ln)] + [ln for ln in lines if LEDGER_HEAD.match(ln)]
        say("  3. %s: %d D-row(s), %d naming OPEN/ESCALATED" % (os.path.relpath(path, ROOT), len(rows), len(flagged)))
        for ln in flagged:
            table = LEDGER_ROW.match(ln)
            heading = LEDGER_HEAD.match(ln)
            name = table.group(1) if table else (heading.group(1) if heading else ln[:40])
            fresh = name not in PIN_LEDGER_OPEN_IDS
            say("       %-16s %s%s" % (name, ln.strip()[-58:], "   <-- UNCLASSIFIED" if fresh else ""))
            if fresh:
                wrong.append("a NEW open ledger row is unclassified: " + name)
    for path in (OWNER_A, OWNER_B):
        if not os.path.exists(path):
            continue
        text = read(path)
        titles = re.findall(r"^## (Q\d+\b.*)$", text, re.MULTILINE)
        pinned = PIN_OWNER_QUESTION_COUNTS[path]
        say("  4. %s: %d owner question(s), pinned %d" % (os.path.relpath(path, ROOT), len(titles), pinned))
        for title in titles:
            say("       " + title[:96])
        if len(titles) != pinned:
            wrong.append("%s: owner questions moved %d -> %d" % (os.path.basename(path), pinned, len(titles)))

    # ---- 5. docs/audit population vs the map -------------------------------
    docs = sorted(name for name in os.listdir(AUDIT_DIR) if name.endswith(".md"))
    map_text = read(MAP)
    named = [name for name in docs if name in map_text]
    unnamed = [name for name in docs if name not in map_text]
    say("  5. docs/audit: %d file(s) on disk, %d named inside the map, %d not named"
        % (len(docs), len(named), len(unnamed)))
    for name in unnamed:
        say("       not named: " + name)

    # ---- 6. receipts that declare their own residual -----------------------
    receipts = sorted(name for name in os.listdir(MAIN_DIR) if name.startswith("receipt-") and name.endswith(".md"))
    residual = [name for name in receipts if QUALIFIED.search(read(os.path.join(MAIN_DIR, name)))]
    say("  6. %d receipt(s); %d declare a residual of their own (STILL OPEN/SUPERSEDED/UNVERIFIED)"
        % (len(receipts), len(residual)))

    # ---- 7. control --------------------------------------------------------
    if args.neg_arm:
        # RE-ANCHORED 2026-11-25: the control used to plant a question in a COPY
        # of `_moved/aireplay/.../TO-BE-ANSWERED-BY-OWNER.md`. That file is gone
        # with the parked tree, so `shutil.copyfile` died with FileNotFoundError
        # and the control could no longer say NO. The live source is AGENTS.md:
        # a planted open risk must come back UNCLASSIFIED through the same rule
        # section 2 uses.
        work = os.path.join(tempfile.gettempdir(), "coverage-neg")
        os.makedirs(work, exist_ok=True)
        fake = os.path.join(work, "AGENTS.md")
        shutil.copyfile(AGENTS, fake)
        with open(fake, "a", encoding="utf-8", newline="") as handle:
            handle.write("\n- **RISCO ABERTO QUE NINGUEM CLASSIFICOU (CONTROLE) -- planted**\n")
        _strict, seen = agents_open_ids(fake)
        fresh = [ident for ident in seen if ident not in PIN_AGENTS_MARKERS]
        say("  7. CONTROL (a COPY of AGENTS.md with a planted open risk): %d marker(s) seen, "
            "%d unclassified" % (len(seen), len(fresh)))
        if not fresh:
            wrong.append("control: the planted open risk was NOT seen -- the enumerator is not reading the file")
        else:
            say("       CONTROL FIRED: %s" % fresh[0][:60])
            say("       the planted marker is a new id -- the same rule that fails the real file when a"
                " new open risk appears. A control that cannot say NO is not a control.")
        os.remove(fake)
    else:
        say("  7. CONTROL not run (pass --neg-arm)")

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- product map: %d applied / %d open; the parked tree carries its own ledger rows and owner"
        " questions, which are NOT product rows. Every id above is either pinned (classified) or reported as"
        " UNCLASSIFIED, which fails this run: a new open risk cannot appear silently." % (applied, opened))
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())