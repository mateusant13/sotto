#!/usr/bin/env python3
"""verify-all-launch-audit -- does _main/_audit-verify-all.cmd start anything? MEASURED, not read from its
own header.

The owner stop order forbids opening Sotto. The product-root battery header CLAIMS "nothing here starts a
window, an audio device, or the app", and this repo own rule says absence needs an instrument: a header is
prose, and prose has been wrong here before. So this audit walks every step the script declares (all four
kinds: gate, control, skipped, expect-red), takes the COMMAND line of each, and classifies it by the
launcher signature it carries -- naming the file and line for every hit, so the classification can be
checked rather than trusted.

It runs nothing: it reads. The verdict is the precondition for running the battery at all.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SCRIPT = os.path.join(ROOT, "_main", "_audit-verify-all.cmd")
STEP = re.compile(r"^\s*call :(record|control|skipped|expectred)\s+(\S+)")
# Anything that can put a window on the desk, open the app, or start a device.
LAUNCHERS = [
    ("run.cmd", "the wrapper that starts the app"),
    ("pythonw", "starts the shell windowless but ALIVE"),
    ("--dump-dom", "launches the shell to read its DOM"),
    ("--arm-e-real", "launches the shell with a fake worker"),
    ("--show", "asks the panel to appear"),
    ("Start-Process", "spawns whatever it names"),
    ("start /", "spawns whatever it names"),
    ("_live-launch", "the live launcher"),
]
# Commands that name the app file but only READ it: a compile check or a registry read.
SAFE_APP_USES = ["py_compile", "--autostart-status", "--check-args", "--help"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    say = print
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    with open(SCRIPT, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().split("\n")
    steps = []
    for index, line in enumerate(lines):
        match = STEP.match(line)
        if not match:
            continue
        kind, name = match.group(1), match.group(2)
        above = index - 1
        while above >= 0 and (not lines[above].strip() or lines[above].strip().upper().startswith("REM")):
            above -= 1
        steps.append((kind, name, lines[above].strip(), above + 1))
    say("verify-all-launch-audit -- every step of the product battery, classified by measurement")
    say("  script: %d bytes, %d line(s), %d step(s)" % (os.path.getsize(SCRIPT), len(lines), len(steps)))
    hits = []
    for kind, name, command, at in steps:
        low = command.lower()
        safe = any(token.lower() in low for token in SAFE_APP_USES)
        found = [why for token, why in LAUNCHERS if token.lower() in low]
        if found and not safe:
            hits.append((name, command, at, found))
        say("    %-9s %-34s line %-4d %s" % (kind, name[:34], at, "LAUNCH: " + "; ".join(found) if found and not safe else ("SAFE-APP-USE" if found else "launch-free")))
        say("              " + command[:104])
    say("")
    say("VERDICT: " + ("FAIL" if hits else "PASS")
        + " -- %d step(s) read; %d carry a launcher signature outside the safe-uses list." % (len(steps), len(hits)))
    for name, command, at, found in hits:
        say("  launches: %s (line %d): %s -- %s" % (name, at, command[:70], "; ".join(found)))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())