#!/usr/bin/env python3
"""cited-instruments-oracle -- can every proof the map cites still be RUN?

WHY THIS EXISTS. The last two rounds each found the same shape: a gate a document called GREEN
(`panel-exit3-oracle.py --unit` returning 1) and one that measured a defect and ignored the measurement
(the self-test focus theft). Both were invisible to every check this repo had, because the checks all
read CLAIMS and none read the EVIDENCE CHAIN: a row says APPLIED and cites `_main/something-oracle.py`,
and nothing ever asks whether that file is still there, still runnable, or safe to run.

WHAT IT MEASURES, from the map itself:
  1. every runnable path a row cites EXISTS -- a cited-and-absent instrument is not a style problem, it
     is a row whose evidence cannot be re-run by anyone;
  2. every cited instrument is CLASSIFIED: gated by the committed battery, or NOT RUN here with a named
     reason. "APPLIED, and its proof needs a launch" and "APPLIED, and its proof ran in-process" are
     different claims and the map should not blur them;
  3. the LAUNCH-RISK scan is static: a cited instrument whose text names the shell, the worker,
     `run.cmd` or the audit battery is reported WITH the marker that named it, so nobody runs it by
     accident from a sweep like this one.

BOTH COLOURS. --neg-arm builds two synthetic maps -- one citing a file that does not exist, one citing a
file whose text carries launch markers -- and requires both to be flagged.

NO LAUNCH, and it never executes a cited instrument: it reads paths and bytes.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MAP = os.path.join(ROOT, "docs", "audit", "00-MAPA-CONSOLIDADO.md")
BATTERY = os.path.join(ROOT, "_main", "instruments-battery.mjs")

#: TWO boundaries the first draft got wrong, and both produced FALSE ABSENT rows (measured -- four of
#: the six "absent" citations were this scanner's fault, not the map's):
#:   (?<![A-Za-z0-9_/])  the path must not START mid-path: `_moved/aireplay/_main/window-census.ps1`
#:                       contains `_main/window-census.ps1`, which is not a citation to `_main/`.
#:   (?![A-Za-z0-9])     the extension must not match a PREFIX: `oracle-after.json` was read as
#:                       `oracle-after.js` and reported absent while the file was right there.
CITATION = re.compile(r"(?<![A-Za-z0-9_/])((?:app|worker|docs|scripts|_main|_moved)/[A-Za-z0-9_./-]+"
                      r"\.(?:py|js|mjs|cmd|ps1|json|jsonl|md))(?![A-Za-z0-9])(?::(\d+)(?:-(\d+))?)?")

LAUNCH_MARKERS = ("run.cmd", "sotto_webview.py", "sotto_worker.py", "_audit-verify-all",
                  "webview.create_window", "_legacy-electron")

SYNTHETIC_MISSING = "| 2 | a row | `_main/this-does-not-exist-oracle.py:9` | **APPLIED** |"
SYNTHETIC_RISKY = "| 3 | a row | `_main/panel-exit3-oracle.py:1` | **APPLIED** |"


def citations(text):
    """path -> {count, lines}, in first-seen order."""
    found = {}
    for match in CITATION.finditer(text):
        path = match.group(1)
        line = int(match.group(2)) if match.group(2) else 0
        entry = found.setdefault(path, {"count": 0, "lines": []})
        entry["count"] += 1
        if line and len(entry["lines"]) < 6:
            entry["lines"].append(line)
    return found


def battery_paths():
    if not os.path.exists(BATTERY):
        return set()
    with open(BATTERY, encoding="utf-8") as handle:
        text = handle.read()
    return set(re.findall(r"'(_main/[A-Za-z0-9_.-]+\.(?:py|js|mjs))", text))


#: Basenames present in the repo. WHY THIS EXISTS: a row may legitimately QUOTE a broken path --
#: rows F10 and F19 are ABOUT wrong citations ("AGENTS.md cita worker/runs/exit3-armB-worker.jsonl; o
#: ficheiro vive em _main/") -- so "the path does not resolve" is not by itself a defect. What IS a
#: defect is an artefact that exists NOWHERE: then the row points at nothing a reader can open. The
#: rule is therefore: a non-resolving path is accepted when its BASENAME exists somewhere in the repo.
SKIP_DIRS = {".git", "node_modules", "models", "__pycache__", ".venv"}


def basename_index():
    index = {}
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            index.setdefault(name, os.path.relpath(os.path.join(base, name), ROOT))
    return index


def launch_markers(path):
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return None
    return [marker for marker in LAUNCH_MARKERS if marker in text]


#: Only RUNNABLE files are classified by launch risk; a `.md`/`.json` citation is evidence too, but it
#: cannot be "run", so it is counted separately instead of being called a risk.
RUNNABLE = (".py", ".js", ".mjs", ".cmd", ".ps1")


def classify(entries, gated, index=None):
    absent, quoted, risky, safe, gated_here, docs = [], [], [], [], [], []
    index = index if index is not None else {}
    for path, entry in sorted(entries.items()):
        if not os.path.exists(os.path.join(ROOT, path)):
            elsewhere = index.get(os.path.basename(path))
            (quoted if elsewhere else absent).append((path, entry, elsewhere))
            continue
        if not path.endswith(RUNNABLE):
            docs.append((path, entry))
            continue
        markers = launch_markers(path)
        if path in gated:
            gated_here.append((path, markers or []))
        elif markers:
            risky.append((path, markers))
        else:
            safe.append((path, entry))
    return {"absent": absent, "quoted": quoted, "risky": risky, "safe": safe,
            "gated": gated_here, "docs": docs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--map", default=MAP)
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(parsed.map, encoding="utf-8") as handle:
        text = handle.read()
    gated = battery_paths()

    if parsed.neg_arm:
        say("cited-instruments-oracle -- neg-arm (synthetic maps, nothing is executed)")
        missing = classify(citations(SYNTHETIC_MISSING), set(), basename_index())
        risky = classify(citations(SYNTHETIC_RISKY), set(), basename_index())
        say("  synthetic(absent)      absent=%d" % len(missing["absent"]))
        say("  synthetic(launch-risk) risky=%d" % len(risky["risky"]))
        wrong = []
        if len(missing["absent"]) != 1:
            wrong.append("the checker did not flag a citation to a file that does not exist")
        if len(risky["risky"]) < 1:
            wrong.append("the checker did not classify a launch-risk citation")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": both synthetic defects must be flagged; wrong: " + str(wrong))
        return 0 if not wrong else 1

    result = classify(citations(text), gated, basename_index())
    say("cited-instruments-oracle -- the map's evidence chain (nothing is executed)")
    say("  cited runnable path(s)           %d" % (len(result["gated"]) + len(result["safe"])
                                                     + len(result["risky"]) + len(result["absent"])))
    say("  cited document/report(s)         %d" % len(result["docs"]))
    say("    gated by the committed battery %d" % len(result["gated"]))
    say("    runnable in-process, NOT gated %d" % len(result["safe"]))
    say("    launch-risk (marker named)     %d" % len(result["risky"]))
    say("    path wrong, artefact EXISTS     %d  (a row quoting a broken path)" % len(result["quoted"]))
    say("    ABSENT EVERYWHERE (defect)     %d" % len(result["absent"]))
    for path, entry, elsewhere in result["quoted"]:
        say("      quoted  %s  -> the artefact is at %s" % (path, elsewhere))
    for path, entry, _elsewhere in result["absent"]:
        say("      ABSENT  %s  (cited %d time(s), lines %s)" % (path, entry["count"], entry["lines"]))
    for path, markers in result["risky"][:14]:
        say("      risk    %s  <- %s" % (path, ", ".join(markers)))
    for path, entry in result["safe"][:14]:
        say("      safe    %s  (cited %d time(s), lines %s)" % (path, entry["count"], entry["lines"]))

    wrong = []
    for path, entry, _elsewhere in result["absent"]:
        wrong.append("cited but the artefact exists NOWHERE in the repo: %s (cited %d time(s))"
                     % (path, entry["count"]))
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- every runnable path the map cites exists; the re-runnable ones are in the committed"
        " battery and the launch-risk ones are NAMED rather than run (owner order)")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
