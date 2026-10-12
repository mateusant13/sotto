#!/usr/bin/env python3
"""preflight-refusal-visible-oracle -- does the caller of run.cmd ever learn WHICH flag was refused?

AUDIT ROW G5: "o proprio pre-flight e um run pythonw sem stdout: o usage:/error: do argparse e
descartado e o rc e o contrato inteiro".

THE CAUSE WAS MEASURED, AND IT IS NOT pythonw. The SAME pre-flight command was run twice on 2026-10-12:
  pythonw sotto_webview.py --check-args --bogus-flag   with a file handle -> rc 2, 757 B of argparse
                                                       usage/error on stderr;
                                                       with NO handle (the wrapper plain line)
                                                       -> rc 2, 0 B anywhere.
So pythonw does not discard the message: NOBODY HAD GIVEN IT SOMEWHERE TO GO. The wrapper ran the child
with no stdout and no stderr, so argparse wrote into the void and the caller got only the wrapper own
legend ("rc=2 is a bad flag"). The cure is one redirection plus printing what it caught -- and it is
measurable END TO END without launching the app, because --check-args STARTS NOTHING by its own contract.

ARMS (each runs the REAL wrapper; none of them reaches the launch path):
  1  run.cmd --bogus-flag   -> rc 2, and the caller output carries argparse own "unrecognized arguments:
                               --bogus-flag" -- WHICH flag, not only the class; the log grows too.
  2  run.cmd --help         -> rc 0 (the help path is untouched by the cure).
  3  run.cmd --check-args   -> rc 0 and the log does NOT grow: a valid list still starts nothing and
                               leaves no receipt.
  4  CONTROL: the PRE-FIX wrapper, extracted from git HEAD (which does not carry this cure yet), run with
     the same --bogus-flag -> rc 2 but NO argparse text -- the message really was invisible, so arm 1 is
     measuring the cure and not something else. This is the same technique run-cmd-exit-oracle.py uses
     with _main/run-cmd-prefix-20261006.cmd.

The control copy is written next to the real wrapper (so %HERE% resolves exactly as it does for the app)
and DELETED in a finally block; the oracle fails if it cannot remove it.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
APPDIR = os.path.join(ROOT, "app", "webview")
RUNCMD = os.path.join(APPDIR, "run.cmd")
CONTROL = os.path.join(APPDIR, "_oracle-prefix-run.cmd")
LOG = os.path.join(ROOT, "_main", "webview-run.log")
NEEDLE = "unrecognized arguments"
#: The wrapper's OWN receipt line. MEASURED 2026-10-12: measuring this gate by the
#: log's SIZE is a race the wrapper cannot win -- the app writes to the SAME file
#: while it runs, so a concurrent appender made arm 3 report "a valid pre-flight
#: wrote to the log (+624 B)" for a run whose wrapper had written NOTHING. Since the
#: Windows autostart task was registered the app is up essentially always, so that
#: race is the normal case. The claim under test is "the WRAPPER left a receipt", so
#: the receipt is what gets read. This is STRICTER, not looser: the size could grow
#: from the app's own traffic while the wrapper stayed mute, and the size form would
#: have answered PASS.
MARKER = "PREFLIGHT_REFUSED"
PREFIX_COMMIT = "3e85202"  # the wrapper as it shipped BEFORE the G5 cure; not HEAD, by design


def run_wrapper(path, args, env=None):
    full = {**os.environ, "TMPDIR": "I:/cc-tmp"}
    if env:
        full.update(env)
    proc = subprocess.run(["cmd.exe", "/c", path, *args], cwd=ROOT, capture_output=True, text=True,
                          errors="replace", env=full, timeout=120)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def log_size():
    try:
        return os.path.getsize(LOG)
    except OSError:
        return -1


def log_delta(before):
    """The bytes appended since `before`, or None when nothing was appended."""
    try:
        size = os.path.getsize(LOG)
    except OSError:
        return None
    if size <= before:
        return None
    with open(LOG, encoding="utf-8", errors="replace") as handle:
        handle.seek(before)
        return handle.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parsed = parser.parse_args(argv)
    say = print
    say("preflight-refusal-visible-oracle -- row G5 (runs the pre-flight only; starts nothing)")
    wrong = []

    before = log_size()
    rc1, out1 = run_wrapper(RUNCMD, ["--bogus-flag"])
    after = log_size()
    delta1 = log_delta(before) or ""
    say("  arm 1  --bogus-flag : rc=%d, caller text=%d B, log %+d B, receipt=%s"
        % (rc1, len(out1), after - before, str(MARKER in delta1).lower()))
    say("         caller sees: " + " | ".join(line for line in out1.splitlines() if line.strip())[:190])
    if rc1 != 2:
        wrong.append("arm 1: a rejected flag no longer returns 2 (got %d)" % rc1)
    if NEEDLE not in out1:
        wrong.append("arm 1: the caller does NOT see which argument argparse rejected")
    if "--bogus-flag" not in out1:
        wrong.append("arm 1: the refused FLAG is not named in the caller output")
    if MARKER not in delta1:
        wrong.append("arm 1: the log took no RECEIPT from this wrapper -- a hidden run"
                     " would leave no reason at all (any bytes may be the app's own)")
    if NEEDLE not in delta1:
        wrong.append("arm 1: the receipt does not carry WHICH flag argparse rejected")

    rc2, out2 = run_wrapper(RUNCMD, ["--help"])
    say("  arm 2  --help       : rc=%d, caller text=%d B" % (rc2, len(out2)))
    if rc2 != 0:
        wrong.append("arm 2: --help no longer returns 0 (got %d)" % rc2)

    before3 = log_size()
    rc3, out3 = run_wrapper(RUNCMD, ["--check-args"])
    after3 = log_size()
    delta3 = log_delta(before3) or ""
    say("  arm 3  --check-args : rc=%d, caller text=%d B, log %+d B, receipt=%s"
        % (rc3, len(out3), after3 - before3, str(MARKER in delta3).lower()))
    if rc3 != 0:
        wrong.append("arm 3: a VALID list is refused (rc=%d) -- the cure would cost a good launch" % rc3)
    if MARKER in delta3:
        wrong.append("arm 3: a VALID pre-flight wrote a refusal receipt -- the cure"
                     " would cost a good launch")

    control_written = False
    try:
        # THE CONTROL MUST NAME A COMMIT, NOT HEAD. The first version read HEAD -- and the moment the
        # cure was committed, HEAD BECAME the fixed wrapper, so the control silently stopped being a
        # control and the arm passed for the wrong reason (found by the battery, one round after the
        # commit that caused it). 3e85202 is the revision immediately before the cure.
        show = subprocess.run(["git", "show", PREFIX_COMMIT + ":app/webview/run.cmd"], cwd=ROOT,
                              capture_output=True, text=True)
        if show.returncode != 0 or "check-args" not in show.stdout:
            say("  arm 4  CONTROL      : could not read the pre-fix wrapper from git HEAD")
            wrong.append("arm 4: the control could not be built (git show failed)")
        else:
            with open(CONTROL, "w", encoding="utf-8", newline="") as handle:
                handle.write(show.stdout)
            control_written = True
            before4 = log_size()
            rc4, out4 = run_wrapper(CONTROL, ["--bogus-flag"])
            after4 = log_size()
            with open(LOG, encoding="utf-8", errors="replace") as handle:
                handle.seek(max(0, before4))
                delta = handle.read()
            # THE DISCRIMINATING CHECK, and it is narrower than the row's wording: this harness gives
            # the whole tree a PIPE, so the pre-fix child inherits a handle and its message DOES reach
            # the caller -- measured here as the SAME caller text as arm 1. The row premise ("pythonw
            # discards it") is therefore true only when the child has NO handle at all (a console-less
            # spawn), which this harness cannot stage. What the fix changes ALWAYS, in every context, is
            # the RECEIPT: the pre-fix wrapper own log line never names the flag.
            say("  arm 4  CONTROL (pre-fix wrapper from git HEAD): rc=%d, caller text=%d B (SAME as arm 1"
                " -- the harness gives it a pipe), log delta=%+d B, delta names the flag=%s"
                % (rc4, len(out4), after4 - before4,
                     str(MARKER in delta or NEEDLE in delta).lower()))
            if rc4 != 2:
                wrong.append("arm 4: the pre-fix wrapper returned %d, expected 2" % rc4)
            # "2>" alone is too crude: the pre-fix wrapper already contains ">nul 2>&1". The cure has
            # markers of its own -- the REFUSAL variable and the redirect onto it.
            carries_cure = ("REFUSAL=" in show.stdout) or ('2>"%REFUSAL%' in show.stdout)
            if carries_cure or MARKER in delta or NEEDLE in delta:
                wrong.append("arm 4: the control revision " + PREFIX_COMMIT + " already carries the cure --"
                             " it is not a control (did the pin drift?)")
    finally:
        if control_written:
            os.remove(CONTROL)
            if os.path.exists(CONTROL):
                wrong.append("the control copy could not be deleted: " + CONTROL)

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the refused flag is now named to the caller and written to the log, a valid list is still"
        " accepted with rc 0 and no receipt, and the PRE-FIX wrapper is shown blind by the same arm")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
