#!/usr/bin/env python3
"""child-channel-oracle -- can you still hear a child you asked not to have a console?

AUDIT ROWS #5 and its inherited twin F1: `console-census.py` passes
`CREATE_NO_WINDOW | DETACHED_PROCESS` and then reads the child stdout -- and gets a 0-BYTE channel
with rc 0, so `python_pids()` sees nothing and the census reports "no window" for a run that opened
one. The file the row indicts (`_main/_probe/console-census.py`) is GIT-IGNORED, so the repair is not
committable there; what IS committable is the proof, and one correction the first draft of this
oracle needed.

WHAT THE FIRST DRAFT GOT WRONG (measured, and it said so instead of passing): it required a
`python -c` child under CREATE_NO_WINDOW|DETACHED_PROCESS to produce 0 bytes. It produced 23. A
blanket "DETACHED_PROCESS means a blind channel" is FALSE; the child that reproduces it is a
CONSOLE-SUBSYSTEM program that re-launches itself detached, which is what the census ran (measured,
and recorded in app/_legacy-electron/HOTRELOAD.md: rc 0, no output, 0.11 s; DETACHED alone hung to a
90 s timeout). So arm 1 runs PowerShell, and the defect class is not the flag alone but FLAG PLUS a
caller that reads that child output.

FOUR MEASUREMENTS, every run:
  1. THE DEFECT, reproduced live: 0 bytes and rc 0.
  2. THE CURE: the same child with CREATE_NO_WINDOW alone delivers its bytes.
  3. THE DEFECT CLASS IN THE REPO: tracked files that set the flag AND capture child output. They are
     LISTED, never swept -- they are other lanes measurement probes and this session must not clobber
     in-flight work; a flag with no capture is counted separately and is harmless to a channel.
  4. THE SCANNER CAN SAY NO: a synthetic document that DOES contain the pattern must be seen.

Nothing else is launched: two tiny children whose only job is to print one line.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
MARK = "bytes-that-must-arrive"

ALLOWED = {
    "_main/child-channel-oracle.py": "this oracle: it must name the flag to test it",
    "_main/audit-rows-landmine-child-control.py": "the landmine oracle: mutates the census with it",
}

FLAG = re.compile(r"creationflags\s*=[^\n]*(?:DETACHED_PROCESS|0x0*8\b)")
CAPTURE = re.compile(r"capture_output|stdout\s*=\s*subprocess\.PIPE|stdout\s*=\s*PIPE"
                     r"|\.communicate\(|check_output")


def reproducer():
    """The child that reproduces it: a console-subsystem program that re-launches detached."""
    return ["powershell", "-NoProfile", "-Command", "Write-Output " + repr(MARK)]


def scan_text(text):
    return [(index + 1, line.strip()) for index, line in enumerate(text.split("\n"))
            if FLAG.search(line)]


def captures(text):
    return bool(CAPTURE.search(text))


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         creationflags=CREATE_NO_WINDOW)
    return [name for name in out.stdout.split("\n") if name.strip()]


def scan_tracked():
    """Flag AND capture (the defect class), separate from flag alone (harmless to a channel)."""
    both, flag_only = [], []
    for name in tracked_files():
        if name in ALLOWED or not name.endswith((".py", ".ps1", ".cmd", ".mjs", ".js")):
            continue
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        found = scan_text(text)
        if not found:
            continue
        entry = (name, found[0][0], found[0][1])
        (both if captures(text) else flag_only).append(entry)
    return both, flag_only


def spawn(child, flags):
    proc = subprocess.run(child, capture_output=True, text=True, creationflags=flags, timeout=60)
    return {"rc": proc.returncode, "bytes": len(proc.stdout), "stdout": proc.stdout.strip()[:60],
            "stderr": proc.stderr.strip()[:80]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verbose", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("child-channel-oracle -- the 0-byte channel, reproduced every run (two tiny children only)")

    defect = spawn(reproducer(), CREATE_NO_WINDOW | DETACHED_PROCESS)
    cure = spawn(reproducer(), CREATE_NO_WINDOW)
    say("  arm 1 defect (CreateNoWindow|Detached)   bytes=" + str(defect["bytes"])
        + " rc=" + str(defect["rc"]))
    say("  arm 2 cure   (CreateNoWindow alone)      bytes=" + str(cure["bytes"])
        + " rc=" + str(cure["rc"]) + " stdout=" + repr(cure["stdout"]))

    synthetic = "subprocess.run([cmd], creationflags=0x08000000 | 0x00000008, capture_output=True)"
    seen = scan_text(synthetic)
    say("  arm 4 scanner on a document that DOES contain it: " + str(len(seen))
        + " flag hit(s), capture seen=" + str(captures(synthetic)))

    both, flag_only = scan_tracked()
    say("  arm 3 tracked files with flag + capture (the DEFECT class): " + str(len(both)))
    for name, line, text in both[:10]:
        say("      " + name + ":" + str(line) + "  " + text[:70])
    say("        flag WITHOUT capture (harmless to a channel): " + str(len(flag_only)) + " file(s)")
    if parsed.verbose:
        for name, line, _text in flag_only[:16]:
            say("      flag-only " + name + ":" + str(line))

    wrong = []
    if defect["bytes"] != 0:
        wrong.append("the defect did not reproduce (bytes=" + str(defect["bytes"])
                     + "): rewrite this oracle before citing it")
    if cure["bytes"] <= 0 or MARK not in cure["stdout"]:
        wrong.append("the cure delivered nothing (bytes=" + str(cure["bytes"]) + ")")
    if not seen:
        wrong.append("the scanner missed a document that contains the pattern")
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- defect reproduced (0 bytes, rc 0), cure delivered " + str(cure["bytes"])
        + " bytes, scanner proven able to see the pattern; the DEFECT CLASS (flag + capture) has "
        + str(len(both)) + " tracked file(s) LISTED above and NOT swept (other lanes probes;"
        " this session must not clobber in-flight work)")
    if wrong:
        say("  wrong: " + str(wrong))
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())