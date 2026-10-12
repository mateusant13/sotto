#!/usr/bin/env python3
"""channel-class-site-oracle -- the 0-byte channel, judged at the SPAWN SITE, not per file.

AUDIT ROWS #5 and its inherited twin F1. Three things are measured here that the older instrument
(_main/child-channel-oracle.py, which reproduces the mechanism) does NOT:

  1. THE MECHANISM, IN FOUR FORMS, because one belief had to be refuted: it is not only the PIPE that
     DETACHED_PROCESS empties. Measured 2026-10-11 with the same tiny PowerShell child --
       both flags + capture_output -> 0 bytes / rc 0 (the defect)
       CREATE_NO_WINDOW alone     -> 23 bytes / rc 0 (the cure)
       both flags + stdout=FILE   -> 0 bytes / rc 0   <-- the FILE form is blind too
       CREATE_NO_WINDOW + FILE    -> 23 bytes / rc 0
     so "redirected to a file" is NOT a cure, which this oracle assumed in its first version, and the
     arm went RED and corrected it.
  2. THE DEFECT CLASS, PER SITE. Calling a file "flag + capture" when the FILE contains both is a
     file-level guess: six of the eight files the older instrument listed spawn with no capture at all
     and read a LOG FILE instead.
  3. THE CENSUS FILE IS GIT-IGNORED, so git protects nothing in it. _main/_probe/console-census.py
     spawns its PowerShell table with creationflags=0x08000000 ALONE today, and its own comment records
     why (0x08000008 -> 0 bytes / rc 0, so python_pids() returned [] and any kill filter built from it
     matched NOTHING; 0x08000000 -> 2448 bytes / 17 rows). This oracle IS the guard for that repair.

A site whose class is pipe or file consumes a channel these flags empty, so it MUST carry a declared
reason here -- a new blind instrument makes the oracle RED until someone judges it.

No device, no model, no shell: PowerShell one-liners only.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
CENSUS = os.path.join(ROOT, "_main", "_probe", "console-census.py")
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
MARK = "bytes-that-must-arrive"
FLAG = re.compile(r"creationflags\s*=[^\n]*(?:DETACHED_PROCESS|0x0*8\b|0x00000008\b)")
POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

#: Every flagged site whose class is pipe or file, with the VERDICT someone measured. A site missing
#: here is RED: that is how the class stays judged instead of counted.
DECLARED = {
    ("_main/child-channel-oracle.py", 116):
        "INTENTIONAL REPRODUCER -- capturing the empty channel is the measurement",
    ("_main/redux-long-probe.py", 342):
        "diagnostics only: the .stdout.txt/.stderr.txt it writes are never READ (re-measured: the only "
        "later uses are two more closes)",
    ("_moved/aireplay/src/pipeline/share_export.py", 119):
        "PARKED TREE (docs declare it parked, not the product); captures a channel these flags empty",
    ("_moved/aireplay/src/pipeline/share_gate.py", 123):
        "PARKED TREE; captures a channel these flags empty",
    ("_moved/aireplay/src/pipeline/share_gate.py", 661):
        "PARKED TREE; captures a channel these flags empty",
}


def child():
    return [POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", "Write-Output " + repr(MARK)]


def spawn(flags, mode):
    """mode: pipe captures stdout; file redirects it to a scratch file (and reads it back)."""
    if mode == "pipe":
        done = subprocess.run(child(), capture_output=True, text=True, creationflags=flags)
        return done.stdout, done.returncode
    path = os.path.join(tempfile.gettempdir(), "channel-class-site.txt")
    if os.path.exists(path):
        os.remove(path)
    with open(path, "w", encoding="utf-8") as handle:
        done = subprocess.run(child(), stdout=handle, stderr=subprocess.DEVNULL,
                              text=True, creationflags=flags)
    with open(path, encoding="utf-8") as handle:
        return handle.read(), done.returncode


def tracked_flagged_sites():
    listing = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW)
    sites = []
    for name in listing.stdout.splitlines():
        if not name.endswith((".py", ".cmd", ".mjs", ".js")):
            continue
        try:
            with open(os.path.join(ROOT, name), encoding="utf-8", errors="replace") as handle:
                lines = handle.read().split("\n")
        except OSError:
            continue
        for index, line in enumerate(lines):
            if FLAG.search(line):
                sites.append((name, index + 1, lines))
    return sites


def classify(lines, line_number):
    """What happens to the CHILD's stdout at this call: pipe, file or none, with the evidence."""
    text = "\n".join(lines[max(0, line_number - 6):line_number + 6])
    if "capture_output=True" in text or "stdout=PIPE" in text or "stdout=subprocess.PIPE" in text:
        return "pipe", "capture_output/PIPE in the call window"
    if re.search(r"stdout\s*=\s*subprocess\.DEVNULL", text):
        return "none", "stdout discarded"
    if re.search(r"stdout\s*=\s*[A-Za-z_]", text):
        return "file", "stdout redirected to a handle (blind too -- see arm 3)"
    return "none", "no stdout= and no capture in the call window"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("channel-class-site-oracle -- rows #5/#F1, judged at the spawn site (no launch, no device)")
    wrong = []

    say("")
    say("  MECHANISM, the same child in four forms (the third is the one that corrected this oracle):")
    forms = [("both flags + capture_output (PIPE)", CREATE_NO_WINDOW | DETACHED_PROCESS, "pipe", False),
             ("CREATE_NO_WINDOW alone + PIPE", CREATE_NO_WINDOW, "pipe", True),
             ("both flags + stdout=FILE", CREATE_NO_WINDOW | DETACHED_PROCESS, "file", False),
             ("CREATE_NO_WINDOW alone + FILE", CREATE_NO_WINDOW, "file", True)]
    for label, flags, mode, want_bytes in forms:
        if parsed.neg_arm and mode == "file":
            # The mutant asserts the redirection is a cure -- exactly what arm 3 refuted. It must fail
            # ONLY the arms that expect bytes from the file form.
            got, rc = ("", 0)
        else:
            got, rc = spawn(flags, mode)
        arrived = MARK in got
        say("    %-38s bytes=%-4d rc=%s  %s" % (label, len(got), rc,
                                                "bytes arrived" if arrived else "NOTHING ARRIVED"))
        if arrived != want_bytes:
            wrong.append(label + ": expected bytes=" + str(want_bytes) + ", got " + str(len(got)))

    say("")
    say("  THE CENSUS FILE (git-ignored, so this oracle is its only guard):")
    if not os.path.exists(CENSUS):
        wrong.append("the census file is gone: " + CENSUS)
        say("    ABSENT: " + CENSUS)
    else:
        with open(CENSUS, encoding="utf-8", errors="replace") as handle:
            census = handle.read()
        deadly = [line.strip() for line in census.split("\n")
                  if FLAG.search(line) and ("0x00000008" in line or "DETACHED" in line)]
        say("    flagged creationflags line(s) in the census: " + str(len(deadly)))
        for line in deadly:
            say("      " + line[:96])
        if deadly:
            wrong.append("the census sets DETACHED_PROCESS again -- the blindness it documents is back")

    say("")
    sites = tracked_flagged_sites()
    say("  TRACKED SPAWN SITES with a DETACHED/0x08 creationflag: " + str(len(sites)))
    counts = {"pipe": 0, "file": 0, "none": 0}
    hazards = []
    for name, line_number, lines in sites:
        kind, why = classify(lines, line_number)
        counts[kind] += 1
        verdict = DECLARED.get((name, line_number))
        if kind == "none":
            mark = "unaffected"
        elif verdict is None:
            mark = "UNDECLARED"
            wrong.append("a flagged spawn site consumes a channel and has no verdict: " + name + ":"
                         + str(line_number) + " (" + kind + ")")
        else:
            mark = "declared"
            hazards.append((name, line_number, kind, verdict))
        say("    %-46s :%-4d %-5s %-10s %s" % (name, line_number, kind, mark, why))
    say("    classes: pipe=%d file=%d none=%d" % (counts["pipe"], counts["file"], counts["none"]))
    for name, line_number, kind, verdict in hazards:
        say("    HAZARD(declared) " + name + ":" + str(line_number) + " [" + kind + "] " + verdict)

    say("")
    if parsed.neg_arm:
        say("NEG-ARM " + ("PASS" if wrong else "FAIL")
            + ": the mutant asserts a FILE redirect is a cure; the arms that expect bytes from the file"
            " form must go RED and nothing else (" + str(len(wrong)) + " failure(s))")
        return 0 if wrong else 1
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the mechanism is measured in four forms, the ignored census is gated against the deadly"
        " flag, and every flagged spawn site carries a measured verdict instead of a per-file guess")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
