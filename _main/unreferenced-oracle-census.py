#!/usr/bin/env python3
"""unreferenced-oracle-census -- classify every _main/*.py by REAL references.

WHY THIS EXISTS. A dead instrument is indistinguishable from a missing one: both are
absent from the battery, from the code, and from the receipts. Deleting blind is
destructive, so this instrument answers the question with counts and a machine-readable
list of paths plus the evidence line that classified each one. A later lane can then
reclaim by evidence instead of by guesswork.

WHAT IT READS (never executes, no subprocess, no network):
  1. the committed battery _main/_audit-verify-all.cmd                  -> GATED
  2. imports/path-like mentions in other .py under _main, app, worker,
     scripts (a file never counts itself)                              -> REFERENCED
  3. docs/*.md and _main/receipt-*.md                                  -> DOCUMENTED
  4. .artifacts.toml and revival/*.json*                               -> DOCUMENTED

VERDICTS, IN STRICT PRECEDENCE (each file lands in exactly one bucket):
  GATED       named in the battery
  REFERENCED  code reference, with no battery name
  DOCUMENTED  only documentation/config mention, with no code reference
  ORPHAN      none of the above

A path-like mention in a code file is counted as a reference even when it sits in a
comment: the evidence field records the exact referring file and line so a reader can
see whether that mention is an invocation, an import, or a note. In docs/config a
mention is evidence of provenance, never of execution.

BOTH MUTANTS. --neg-arm mutates this same classifier twice IN MEMORY (the corpus is read
once): battery lookup forced to match nothing, and code lookup forced to match every
inventory file. Both must move the counts in the expected direction. House convention:
mutated run CAUGHT -> rc 1, clean run -> rc 0.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MAIN_DIR = os.path.join(ROOT, "_main")
BATTERY = os.path.join(MAIN_DIR, "_audit-verify-all.cmd")

#: Two forms: `_main/name.py` (which may sit behind a path prefix such as
#: `%ROOT%\` or `H:/sotto/`) and a bare `name.py` invocation. The bare form refuses
#: a preceding path separator, so `app/webview/foo.py` is not read as a reference
#: to `_main/foo.py`; the explicit `_main/` form is accepted even mid-path.
MAIN_REF = re.compile(r"(?<![\w.-])(?:_main[\\/])([A-Za-z_][A-Za-z0-9_.-]*\.py)\b",
                      re.I)
BARE_REF = re.compile(r"(?<![\w/\\.-])([A-Za-z_][A-Za-z0-9_.-]*\.py)\b", re.I)
IMPORT_REF = re.compile(r"^\s*(?:from\s+[A-Za-z0-9_.]+\s+)?import\s+([A-Za-z0-9_., \t]+)")
IMPORT_NAME = re.compile(r"^[A-Za-z_]\w*$")
SKIP_DIRS = {".git", "__pycache__", "node_modules", "models", ".venv"}
EVIDENCE_CAP = 6
CATEGORIES = ("battery", "code", "docs", "config")
VERDICTS = ("GATED", "REFERENCED", "DOCUMENTED", "ORPHAN")


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def inventory():
    """lowercase stem -> relative path, for every _main/*.py."""
    found = {}
    with os.scandir(MAIN_DIR) as entries:
        for entry in entries:
            if entry.is_file() and entry.name.lower().endswith(".py"):
                found[entry.name[:-3].lower()] = rel(entry.path)
    return found


def load_corpus():
    """Read each referring file exactly once; mutations below reuse these strings."""
    code = []
    for base in ("_main", "app", "worker", "scripts"):
        base_dir = os.path.join(ROOT, base)
        if not os.path.isdir(base_dir):
            continue
        for dirpath, dirs, files in os.walk(base_dir):
            dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
            for name in files:
                if name.lower().endswith(".py"):
                    path = os.path.join(dirpath, name)
                    code.append((rel(path), read_text(path)))

    doc_paths = glob.glob(os.path.join(ROOT, "docs", "*.md"))
    doc_paths += glob.glob(os.path.join(MAIN_DIR, "receipt-*.md"))
    config_paths = [os.path.join(ROOT, ".artifacts.toml")]
    config_paths += glob.glob(os.path.join(ROOT, "revival", "*.json*"))

    def bundle(paths):
        return [(rel(path), read_text(path)) for path in sorted(set(paths))
                if os.path.isfile(path)]

    return {"battery": read_text(BATTERY), "code": code,
            "docs": bundle(doc_paths), "config": bundle(config_paths)}


def mentions(text, by_stem, referrer):
    """Yield (target_path, line, kind) for each real mention of an inventory file."""
    for lineno, line in enumerate(text.splitlines(), 1):
        for matcher in (MAIN_REF, BARE_REF):
            for match in matcher.finditer(line):
                name = match.group(1)[:-3].lower()
                target = by_stem.get(name)
                if target and target != referrer:
                    yield target, lineno, "path"
        imported = IMPORT_REF.match(line)
        if imported:
            for token in imported.group(1).split(","):
                token = token.strip()
                if not IMPORT_NAME.match(token):
                    continue
                target = by_stem.get(token.lower())
                if target and target != referrer:
                    yield target, lineno, "import"


def build_evidence(by_stem, paths, corpus, battery_off=False, code_all=False):
    """Evidence lines and match counts per path, for the clean or a mutated lookup."""
    evidence = {path: {category: [] for category in CATEGORIES} for path in paths}
    counts = {path: {category: 0 for category in CATEGORIES} for path in paths}

    def add(path, category, source, line, kind):
        counts[path][category] += 1
        if len(evidence[path][category]) < EVIDENCE_CAP:
            evidence[path][category].append(
                {"file": source, "line": line, "kind": kind})

    if not battery_off:
        source = rel(BATTERY)
        for target, line, kind in mentions(corpus["battery"], by_stem, source):
            if target in counts:
                add(target, "battery", source, line, kind)

    if code_all:
        # Mutant B: the code lookup matches EVERY inventory file, even one with no
        # referring code at all. The fake source is labelled, never hidden.
        for path in paths:
            add(path, "code", "<mutant:code-all>", 0, "mutant")
    else:
        for source, text in corpus["code"]:
            for target, line, kind in mentions(text, by_stem, source):
                if target in counts:
                    add(target, "code", source, line, kind)

    for category in ("docs", "config"):
        for source, text in corpus[category]:
            for target, line, kind in mentions(text, by_stem, source):
                if target in counts:
                    add(target, category, source, line, kind)
    return evidence, counts


def classify(paths, counts):
    verdicts, totals = {}, {name: 0 for name in VERDICTS}
    for path in paths:
        if counts[path]["battery"]:
            verdict = "GATED"
        elif counts[path]["code"]:
            verdict = "REFERENCED"
        elif counts[path]["docs"] or counts[path]["config"]:
            verdict = "DOCUMENTED"
        else:
            verdict = "ORPHAN"
        verdicts[path] = verdict
        totals[verdict] += 1
    return verdicts, totals


def neg_arm(paths, by_stem, corpus, clean_counts, clean_verdicts, clean_totals):
    print("unreferenced-oracle-census -- neg-arm (two in-memory classifier mutants)")
    off_evidence, off_counts = build_evidence(by_stem, paths, corpus, battery_off=True)
    off_verdicts, off_totals = classify(paths, off_counts)
    all_evidence, all_counts = build_evidence(by_stem, paths, corpus, code_all=True)
    all_verdicts, all_totals = classify(paths, all_counts)

    battery_caught = (
        clean_totals["GATED"] > 0
        and off_totals["GATED"] == 0
        and off_totals["GATED"] < clean_totals["GATED"]
        and sum(off_totals.values()) == len(paths)
        and any(off_verdicts[path] != clean_verdicts[path] for path in paths
                if clean_verdicts[path] == "GATED")
    )
    code_caught = (
        all_totals["REFERENCED"] > clean_totals["REFERENCED"]
        and all_totals["ORPHAN"] == 0
        and all_totals["DOCUMENTED"] == 0
        and sum(all_totals.values()) == len(paths)
        and any(all_verdicts[path] != clean_verdicts[path] for path in paths
                if clean_verdicts[path] in ("ORPHAN", "DOCUMENTED"))
    )

    print("  MUTANT battery_lookup_disabled: %s  GATED %d -> %d"
          % ("CAUGHT" if battery_caught else "MISSED",
             clean_totals["GATED"], off_totals["GATED"]))
    print("  MUTANT code_lookup_all:         %s  REFERENCED %d -> %d,"
          " ORPHAN %d -> %d, DOCUMENTED %d -> %d"
          % ("CAUGHT" if code_caught else "MISSED",
             clean_totals["REFERENCED"], all_totals["REFERENCED"],
             clean_totals["ORPHAN"], all_totals["ORPHAN"],
             clean_totals["DOCUMENTED"], all_totals["DOCUMENTED"]))
    ok = battery_caught and code_caught
    print("")
    print("NEG-ARM: %s -- both mutants CAUGHT; rc=1 by house convention (clean run rc=0)"
          % ("PASS" if ok else "FAIL"))
    return 1 if ok else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="print one machine-readable object and nothing else")
    parser.add_argument("--neg-arm", action="store_true",
                        help="mutate this classifier in memory; caught mutants -> rc 1")
    args = parser.parse_args(argv)

    by_stem = inventory()
    paths = sorted(by_stem.values())
    corpus = load_corpus()
    evidence, counts = build_evidence(by_stem, paths, corpus)
    verdicts, totals = classify(paths, counts)

    if args.neg_arm:
        return neg_arm(paths, by_stem, corpus, counts, verdicts, totals)

    if args.json:
        print(json.dumps({
            "totals": dict(totals, ALL=len(paths)),
            "files": [{"path": path, "verdict": verdicts[path],
                       "evidence": evidence[path],
                       "evidence_counts": counts[path]} for path in paths],
        }, ensure_ascii=False, indent=2))
        return 0

    print("unreferenced-oracle-census -- every _main/*.py, classified by real references")
    print("  (read-only: no subprocess, no launch, no network)")
    print("  inventory _main/*.py               %d" % len(paths))
    print("  GATED (battery)                    %d" % totals["GATED"])
    print("  REFERENCED (code import/call)      %d" % totals["REFERENCED"])
    print("  DOCUMENTED (docs/config only)      %d" % totals["DOCUMENTED"])
    print("  ORPHAN (no evidence)               %d" % totals["ORPHAN"])
    print("  total                              %d" % sum(totals.values()))
    orphans = [path for path in paths if verdicts[path] == "ORPHAN"]
    print("  ORPHAN sample (up to 12; full list via --json):")
    for path in orphans[:12]:
        print("    " + path)
    print("")
    print("rc=0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
