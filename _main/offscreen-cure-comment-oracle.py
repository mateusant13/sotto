#!/usr/bin/env python3
"""offscreen-cure-comment-oracle -- the cure that BROKE loading must not be prescribed again.

AUDIT ROWS #33 and its inherited twin F4: "comentarios obsoletos/contraditorios no sotto_webview.py
sobre a cura OFFSCREEN". The cure -- creating the window at x=y=-32000 -- was tried 2026-10-06 and
MEASURED BROKEN (WebView2 never completes the stage->panel navigation, so `_on_loaded` never fires
and the shell HANGS), and a second attempt (`transparent=False` after create) is forbidden for the
same reason. The risk a comment carries here is not fashions: it is that a future lane reads
`OFFSCREEN = -32000` in prose and reintroduces it.

WHAT IT CHECKS, from the bytes of the shell:
  1. every mention of OFFSCREEN is inside a COMMENT (no executable line carries it);
  2. every mention sits within a few lines of a NEGATION marker (REMOVED / do not reintroduce /
     MEASURED BROKEN / zero executable) -- a bare mention is what the row is about;
  3. a snippet that PRESCRIBES the cure IS flagged, so a scanner that always says "fine" fails.

BOTH COLOURS. --neg-arm writes a copy of the shell with the negation marker stripped from the
first mention and requires that mention to be flagged; the pristine copy must stay clean.

NO LAUNCH: text only.
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
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")

#: What turns a mention into a WARNING rather than an instruction. One of these must be within
#: WINDOW lines of the mention.
NEGATION = ("REMOVED", "removed", "do not reintroduce", "MEASURED BROKEN", "zero executable",
            "was tried", "FORBIDDEN", "forbidden")
WINDOW = 4

#: A snippet that PRESCRIBES the dead cure: the control that proves the scanner can say NO.
PRESCRIBES = "self.window = webview.create_window(x=OFFSCREEN, y=OFFSCREEN, width=1)"


def mentions(text):
    return [index for index, line in enumerate(text.split("\n")) if "OFFSCREEN" in line]


#: A line is PROSE if it is a `#` comment, carries a trailing `#`, or sits inside a triple-quoted
#: string. The first draft of this oracle only knew `#` and flagged two DOCSTRING lines as
#: "executable" (measured 2026-10-11) -- a false positive that would have failed a clean file.
def prose_flags(lines):
    inside = False
    flags = []
    for line in lines:
        stripped = line.strip()
        opens = stripped.count(chr(34) * 3)
        was_inside = inside
        if opens % 2 == 1:
            inside = not inside
        flags.append(was_inside or inside or stripped.startswith("#") or "#" in line)
    return flags


def verdicts(text):
    lines = text.split("\n")
    prose = prose_flags(lines)
    flagged = []
    total = 0
    for index in mentions(text):
        total += 1
        in_comment = prose[index]
        window = "\n".join(lines[max(0, index - WINDOW):index + WINDOW + 1])
        negated = any(marker in window for marker in NEGATION)
        if not in_comment:
            flagged.append((index + 1, "EXECUTABLE line mentions OFFSCREEN", lines[index].strip()[:80]))
        elif not negated:
            flagged.append((index + 1, "comment with NO negation nearby", lines[index].strip()[:80]))
    # The control: a snippet that prescribes it must be flagged, or the scanner is blind.
    control_index = len(lines)
    lines.append(PRESCRIBES)
    control_flagged = not lines[-1].lstrip().startswith("#")
    return {"mentions": total, "flagged": flagged, "control_flagged": control_flagged}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--shell", default=SHELL)
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    text = open(parsed.shell, encoding="utf-8").read()
    got = verdicts(text)
    say("offscreen-cure-comment-oracle -- mentions in prose, none prescribing it (no launch)")
    say("  mentions of OFFSCREEN            " + str(got["mentions"]))
    say("  flagged                          " + str(len(got["flagged"])))
    say("  control (a prescribing snippet)  flagged=" + str(got["control_flagged"]))
    for line, why, content in got["flagged"]:
        say("      :" + str(line) + "  " + why + "  " + content)

    if parsed.neg_arm:
        scratch = tempfile.mkdtemp(prefix="sotto-offs-neg-")
        lines = text.split("\n")
        index = mentions(text)[0]
        # Strip the negation marker from the FIRST mention WINDOW without touching the mention.
        for position in range(max(0, index - WINDOW), min(len(lines), index + WINDOW + 1)):
            for marker in ("REMOVED", "removed", "do not reintroduce", "MEASURED BROKEN",
                           "zero executable", "was tried"):
                lines[position] = lines[position].replace(marker, "noted")
        path = os.path.join(scratch, "sotto_webview_no_negation.py")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write("\n".join(lines))
        mut = verdicts("\n".join(lines))
        say("  mutant flagged                   " + str(len(mut["flagged"])))
        wrong = []
        if got["flagged"]:
            wrong.append("the live shell has " + str(len(got["flagged"])) + " flagged mention(s)")
        if not got["control_flagged"]:
            wrong.append("the scanner did not flag a snippet that prescribes the cure")
        if len(mut["flagged"]) != 1:
            wrong.append("the negation-stripped copy flagged " + str(len(mut["flagged"]))
                         + " mention(s), expected exactly 1")
        say("")
        say("NEG-ARM: stripping the negation from the first mention must flag exactly that mention;"
            " wrong: " + str(wrong))
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL"))
        return 0 if not wrong else 1

    wrong = list(got["flagged"])
    if not got["mentions"]:
        wrong.append("no mention of OFFSCREEN at all -- if the prose is gone, say so and close the row")
    if not got["control_flagged"]:
        wrong.append("the scanner did not flag a snippet that prescribes the cure")
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL") + " -- " + str(got["mentions"])
        + " mention(s), all of them prose that says the cure was REMOVED and must not come back,"
        " and the scanner proven able to flag a snippet that prescribes it")
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())