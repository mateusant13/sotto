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

WHAT WAS WRONG, and why this file was corrected (2026-10-20). The audit used to classify the WHOLE
`call :step` line, so it read the DEPS argument -- the semicolon-separated list of files the step's cache
key is built from -- as if it were a command. `_main/_audit-verify-all.cmd:414` names `app\webview\run.cmd`
in the DEPS of the `agents-md-pins` step, whose COMMAND is `python _main\agents-md-pins-oracle.py` (a
reader that answers `--help` and exits). The audit therefore reported a launcher that is NEVER EXECUTED --
a FALSE POSITIVE, and a red gate on a battery that starts nothing.

THE COMMAND AND THE DEPS ARE NOW SEPARATED before the signature is looked for. The step shape is
(`_main/_audit-verify-all.cmd:862-891`, the `:step` label):

    call :step [always] <name> <expected-rc> "<deps>" "<log>" <command...>

The DEPS are a CACHE KEY -- they are handed to `_main\_stepcache.py` and never executed -- so only the
COMMAND is classified. The DEPS are still printed, so a reader can see that the shell's name appears there
and WHY it is not a launch.

THE TOOTH IS PROVEN, not asserted. `--prove-teeth` runs the SAME classifier over synthetic steps and
fails if it cannot say no: a step whose COMMAND starts the shell must be a hit, a step whose DEPS name the
shell but whose COMMAND only reads a file must not, and a step whose COMMAND is a launcher used safely
must be recognised as safe. A gate that cannot say no is decoration. `--script` points the audit at any
other `.cmd` (a COPY in $TMPDIR, with a step invented in it), which is how the tooth is proved against the
real file rather than against a description of it.
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
# A CMD argument: a quoted run, or a bare word. The quotes come off, which is
# what a signature search wants.
ARG = re.compile(r'"([^"]*)"|(\S+)')


def tokenize(line):
    """Split a CMD command line into arguments, honouring the double quotes."""
    out = []
    for match in ARG.finditer(line):
        out.append(match.group(1) if match.group(1) is not None else match.group(2))
    return out


def split_step(line):
    """(name, deps, log, command) of a `call :step` line -- or None.

    The shape is `:step [always] <name> <expected-rc> "<deps>" "<log>" <command...>`,
    taken from the `:step` label itself (`_main/_audit-verify-all.cmd:862-891`), which
    reads `%~1`=name, `%~2`=rc, `%~3`=deps, `%~4`=log and the REST as the command.
    The `always` prefix is a flag the label shifts away before reading `%~1`.
    """
    tokens = tokenize(line)
    if len(tokens) < 3:
        return None
    if tokens[0].lower() != "call" or tokens[1].lower() != ":step":
        return None
    rest = tokens[2:]
    if rest and rest[0].lower() == "always":
        rest = rest[1:]
    if len(rest) < 3:
        return None
    name, deps = rest[0], rest[2]
    log = rest[3] if len(rest) > 3 else ""
    command = rest[4:]
    return name, deps, log, command


def classify(command_line):
    """(found, deps, scanned) for one `call :step` line.

    `found` is the launcher signatures the COMMAND carries. The DEPS are
    returned so the caller can print them -- they are a cache key, never a
    command, and are NOT part of the signature search.
    """
    parsed = split_step(command_line)
    if parsed is None:
        # A shape this audit does not know: classify the whole line, and say so
        # in the output, so a reader is never left guessing.
        return _classify_text(command_line), "", command_line
    _name, deps, _log, command = parsed
    return _classify_text(" ".join(command)), deps, " ".join(command)


def _classify_text(scan):
    low = scan.lower()
    return [why for token, why in LAUNCHERS if token.lower() in low]


def is_safe(scan):
    """True when the command only READS the app file (a compile, a --help)."""
    low = scan.lower()
    return any(token.lower() in low for token in SAFE_APP_USES)


# The synthetic steps that prove the classifier can still say NO. The same
# classifier, the same LAUNCHERS list, the same SAFE_APP_USES list.
TEETH = [
    ("a step whose COMMAND starts the shell",
     'call :step invented-launch 0 "app\\webview\\run.cmd" "%OUT%\\x.log" '
     'app\\webview\\run.cmd', True),
    ("a step whose COMMAND starts the shell windowless",
     'call :step invented-launch2 0 "" "%OUT%\\x.log" '
     'pythonw app\\webview\\sotto_webview.py', True),
    ("a step whose COMMAND dumps the shell DOM",
     'call :step invented-launch3 0 "" "%OUT%\\x.log" '
     'python app\\webview\\sotto_webview.py --dump-dom', True),
    ("a step whose DEPS name the shell but whose COMMAND only reads a file",
     'call :step invented-deps 0 '
     '"_main\\agents-md-pins-oracle.py;app\\webview\\run.cmd" "%OUT%\\x.log" '
     'python _main\\agents-md-pins-oracle.py', False),
    ("a step whose COMMAND is a launcher used safely (--help)",
     'call :step invented-safe 0 "" "%OUT%\\x.log" '
     'app\\webview\\run.cmd --help', False),
    ("a step whose COMMAND only compiles a file",
     'call :step invented-compile 0 "app\\webview\\sotto_webview.py" '
     '"%OUT%\\x.log" python -m py_compile app\\webview\\sotto_webview.py', False),
]


def prove_teeth():
    """The classifier must be able to say NO. Synthetic steps, same code path."""
    bad = []
    print("TEETH -- the same classifier over synthetic steps")
    for label, line, expect_hit in TEETH:
        found, _deps, scan = classify(line)
        hit = bool(found) and not is_safe(scan)
        print("  %s %-58s %s"
              % ("OK  " if hit == expect_hit else "BAD ", label,
                 ("HIT: " + "; ".join(found)) if hit else "launch-free"))
        if hit != expect_hit:
            bad.append(label)
    print("")
    if bad:
        print("TEETH: FAIL -- %d synthetic step(s) classified wrongly" % len(bad))
        for label in bad:
            print("  wrong: " + label)
        return 1
    print("TEETH: PASS -- %d/%d synthetic steps classified as they must be"
          % (len(TEETH), len(TEETH)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--script", default=SCRIPT,
                        help="the .cmd to audit (default: the product battery)")
    parser.add_argument("--prove-teeth", action="store_true",
                        help="run the classifier over synthetic steps and fail if "
                             "it cannot say no")
    args = parser.parse_args(argv)
    say = print
    if args.prove_teeth:
        return prove_teeth()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    with open(args.script, encoding="utf-8", errors="replace") as handle:
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
    say("  script: %s -- %d bytes, %d line(s), %d step(s)"
        % (args.script, os.path.getsize(args.script), len(lines), len(steps)))
    hits = []
    for kind, name, command, at in steps:
        found, deps, scan = classify(command)
        safe = is_safe(scan)
        if found and not safe:
            hits.append((name, scan, at, found))
        if found and not safe:
            mark = "LAUNCH: " + "; ".join(found)
        elif found:
            mark = "SAFE-APP-USE"
        else:
            mark = "launch-free"
        say("    %-9s %-34s line %-4d %s" % (kind, name[:34], at, mark))
        say("              cmd: " + (scan[:100] or "(none)"))
        if deps:
            # The deps are a cache key, never a command. They are printed so a
            # reader can see the shell's name there and WHY it is not a launch.
            named = [why for token, why in LAUNCHERS if token.lower() in deps.lower()]
            say("              deps: %s%s"
                % (deps[:92], ("  [names " + "; ".join(named) + " -- NEVER EXECUTED]")
                   if named else ""))
    say("")
    say("VERDICT: " + ("FAIL" if hits else "PASS")
        + " -- %d step(s) read; %d carry a launcher signature outside the safe-uses list." % (len(steps), len(hits)))
    for name, scan, at, found in hits:
        say("  launches: %s (line %d): %s -- %s" % (name, at, scan[:70], "; ".join(found)))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
