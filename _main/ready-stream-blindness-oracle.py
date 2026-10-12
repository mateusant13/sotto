#!/usr/bin/env python3
"""ready-stream-blindness-oracle -- the readiness line is written where the supervisor cannot read it.

AUDIT ROW #18: "o ready do supervisor le um stream onde a app nunca escreve (o log vai para --log, nao
para o PTY)". The source document (docs/audit/launch-entry.md 3.4.2) already calls the blindness
MEASURED, and names its own falsifier. What this oracle adds is the four facts, each from an artefact,
plus a guard so a future claim that the app speaks readiness on stdout goes RED.

  1. THE EMIT SITE: the shell writes HOTKEY_REGISTERED through its LOG function (self.log_fn), which
     feeds --log and the ready-file -- never stdout. Measured over the live shell bytes.
  2. THE LAUNCHER: run.cmd launches the shell with pythonw on the normal path -- an interpreter with no
     stdout at all -- and detaches with "start", so the wrapper returns while the app lives. AGENTS.md
     records the ruling that this is deliberate: a wrapper that waited for the app would hold the
     caller's console open for the session. So the PTY of run.cmd CANNOT carry the line, and the
     in-repo alternative is forbidden by a recorded design rule.
  3. THE CONSUMER IS NOT IN THIS REPO: no tracked file consumes HOTKEY_REGISTERED as a readiness
     condition (the only producer is the shell, and the rest are documents), and spec.json -- the row
     second citation -- DOES NOT EXIST ANYWHERE in the repo. The row cites a path that is not here.
  4. THE DOCUMENT still carries the blindness and the falsifier, so the finding is not silently dropped.

THE CURE IS THEREFORE NOT HERE, and this oracle says so instead of pretending otherwise: either the
harness declares ready on a condition the app DOES emit (the ready-file, or the log), or the wrapper
stops detaching -- which the recorded rule forbids. The phenomenon persists until one of those changes;
what is closed is the measurement and the ownership.

--neg-arm rewrites the emit site to print() in an extracted copy of the shell and requires arm 1 to flip.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
RUNCMD = os.path.join(ROOT, "app", "webview", "run.cmd")
DOC = os.path.join(ROOT, "docs", "audit", "launch-entry.md")
TOKEN = "HOTKEY_REGISTERED"


def emit_sites(source):
    """(line number, text) for every line that WRITES the token."""
    return [(n, line.strip()) for n, line in enumerate(source.split("\n"), 1)
            if TOKEN in line and ("log_fn" in line or "print(" in line or "emit" in line)]


def stdout_sites(source):
    return [(n, line.strip()) for n, line in emit_sites(source) if "print(" in line]


def classify(name, text):
    """How a tracked file uses the token -- and the ONLY class this row is about is STDOUT-READER.

    The first version of this oracle called every file that mentions the token a "consumer" and listed
    19 of them, which says nothing: the shell has byte-COPIES and mutants in _main/ (the under-test
    prefixes), and the probes read the app LOG -- which is exactly the right way to observe a line the
    app writes to its log. So the classes are measured, not assumed.
    """
    if "log_fn(f'HOTKEY_REGISTERED" in text or 'log_fn(f"HOTKEY_REGISTERED' in text:
        return "shell-copy"
    if re.search(r"stdout[^\n]{0,120}" + TOKEN + r"|" + TOKEN + r"[^\n]{0,120}stdout", text):
        return "STDOUT-READER"
    if "webview-run.log" in text or "RUN_LOG" in text:
        return "log-reader (reads the app LOG, the channel the app really uses)"
    return "mentions it without reading a stream"


def consumers():
    listing = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True)
    out = {"shell-copy": [], "STDOUT-READER": [], "log-reader": [], "other": []}
    for name in listing.stdout.splitlines():
        if name.endswith(".md") or name.endswith("sotto_webview.py"):
            continue
        try:
            with open(os.path.join(ROOT, name), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        if TOKEN not in text:
            continue
        kind = classify(name, text)
        out["log-reader" if kind.startswith("log-reader") else
            ("other" if kind.startswith("mentions") else kind)].append(name)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(SHELL, encoding="utf-8") as handle:
        shell = handle.read()
    with open(RUNCMD, encoding="utf-8", errors="replace") as handle:
        runcmd = handle.read()
    with open(DOC, encoding="utf-8") as handle:
        doc = handle.read()
    say("ready-stream-blindness-oracle -- row #18 (no launch, no device)")
    wrong = []

    sites = emit_sites(shell)
    bad = stdout_sites(shell)
    if parsed.neg_arm:
        # The mutant claims the app DOES speak on stdout: the emit is rewritten to print() in a copy.
        mutated = re.sub(r"self\.log_fn\(f?['\"]" + TOKEN + ".*?['\"]",
                         "print(f'" + TOKEN + " accelerator={self.accelerator}')", shell, count=1)
        if mutated == shell:
            say("NEG-ARM SETUP ERROR: the emit site did not match")
            return 2
        say("  mutant: the emit site rewritten to print() -> stdout sites=%d" % len(stdout_sites(mutated)))
        if not stdout_sites(mutated):
            wrong.append("NEG-ARM: rewriting the emit to print() produced no stdout site -- arm 1 does "
                         "not measure the emission path")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": an app that answered on stdout would have to be caught here")
        return 0 if not wrong else 1

    say("  1. the emit site: %d line(s) write the token, stdout sites: %d" % (len(sites), len(bad)))
    for number, text in sites:
        say("     :%d  %s" % (number, text[:96]))
    if not sites:
        wrong.append("the shell no longer writes " + TOKEN + " at all")
    if bad:
        wrong.append("the shell DOES print the token to stdout -- the blindness would be gone: " + str(bad))
    joined = " | ".join(text for _n, text in sites)
    if "log_fn" not in joined:
        wrong.append("the token is no longer written through the LOG function")

    pyw = "%PYW%" in runcmd
    ready = "--ready-file" in runcmd
    detached = re.search(r"^\s*start\s", runcmd, re.MULTILINE) is not None
    say("  2. run.cmd: pythonw=%s  --ready-file=%s  detaches with start=%s"
        % (str(pyw).lower(), str(ready).lower(), str(detached).lower()))
    if not pyw:
        wrong.append("run.cmd no longer launches pythonw -- the premise of the blindness changed")
    if not ready:
        wrong.append("run.cmd no longer passes --ready-file")
    if not detached:
        wrong.append("run.cmd no longer detaches with start -- if it now waits, the whole finding must "
                     "be re-measured (and AGENTS.md rule against waiting would be violated)")

    classes = consumers()
    specs = subprocess.run(["git", "ls-files", "*spec.json"], cwd=ROOT, capture_output=True, text=True)
    say("  3. tracked files that mention the token, BY CLASS:")
    for kind in ("shell-copy", "log-reader", "STDOUT-READER", "other"):
        say("     %-12s %2d %s" % (kind, len(classes[kind]), classes[kind][:3]))
    say("     spec.json tracked in this repo: %d (the row second citation)"
        % len(specs.stdout.split()))
    if classes["STDOUT-READER"]:
        wrong.append("a tracked file WAITS FOR THE TOKEN ON STDOUT -- the blindness would be gone: "
                     + str(classes["STDOUT-READER"]))
    if not classes["log-reader"]:
        wrong.append("no in-repo probe reads the token from the LOG -- the claim that the app writes it"
                     " there would be unmeasured")
    if specs.stdout.split():
        wrong.append("a spec.json now exists in the repo -- the row citation would no longer dangle")

    doc_ok = ("PTY" in doc and "ready" in doc and "Falsifier" in doc)
    say("  4. docs/audit/launch-entry.md still names the blindness, the PTY and a falsifier: "
        + str(doc_ok).lower())
    if not doc_ok:
        wrong.append("the source document no longer names the blindness, the PTY or a falsifier")

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the readiness line goes to the log/ready-file and NOT to the PTY, the launcher cannot"
        " carry it (pythonw, detached), no file in this repo consumes it, the row spec.json does not"
        " exist here, and the cure is the HARNESS condition (or the wrapper waiting, which the recorded"
        " rule forbids)")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
