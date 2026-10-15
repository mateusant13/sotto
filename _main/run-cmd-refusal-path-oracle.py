#!/usr/bin/env python3
"""run-cmd-refusal-path-oracle -- the capture path is RESOLVED, never hand-written.

WHY IT IS STATIC. I set out to run run.cmd --bogus-flag under several invocation forms
and check where the pre-flight capture lands. MEASURED 2026-10-15 while building it: two
of the three forms do NOT stop at the pre-flight -- they reach the LAUNCH path and answer
rc=4 (the HANG report, run.cmd:240), and one actually started the shell (its own
WEBVIEW2_ENV lines in the output). A gate that launches the app is forbidden by the house
rule, so this oracle asserts the INVARIANT that bug violates, without invoking anything.

THE DEFECT IT CATCHES, proven by a stray file:
    app/webview/-preflight-refusal.txt
        pythonw.exe: can not open file H:\\sotto\\app\\webview\\sottoappwebviewsotto_webview.py

TWO mangled things in that one line, the same defect twice: a .bat with CRLF line endings
eats backslashes under some cmd /c invocations, so a hand-written percent HERE dot-dot
relative path resolved against a HERE that had already lost them -- the SHELL path lost
its backslashes, the capture name lost its prefix AND both random halves, and the capture
landed in app/webview/ instead of _main/. The caller got an ENOENT instead of the usage.

THE INVARIANT: the capture directory is obtained by RESOLVING a path with a tilde-f
expansion, never by writing a relative one, and the capture name carries the prefix and
both random halves. A hand-written relative path in a .bat is a promise about EVERY
invocation, and only one of them was ever tested.

NOT COVERED, and named rather than hidden: the exit contract is gated by
run-cmd-exit-oracle.py and the visibility of the refusal by
preflight-refusal-visible-oracle.py. The capture path UNDER EVERY invocation is gated by
nothing -- the two forms that reach the launch path are unrunnable from a gate and stay an
open defect.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.path.pardir))
RUNCMD = os.path.join(ROOT, "app", "webview", "run.cmd")
MAIN = os.path.join(ROOT, "_main")
WEBVIEW = os.path.join(ROOT, "app", "webview")
NAME = re.compile(r"^sotto-preflight-refusal-[0-9]+[0-9]+[.]txt$")


def main() -> int:
    say = print
    if not os.path.exists(RUNCMD):
        say("run-cmd-refusal-path-oracle: NO run.cmd")
        return 1
    with open(RUNCMD, encoding="utf-8", errors="replace") as h:
        body = h.read()
    wrong = []
    say("run-cmd-refusal-path-oracle -- the capture path is resolved, not hand-written")
    if "%~fI" not in body:
        wrong.append("run.cmd never expands a path with a tilde-f form -- resolution gone")
    m = re.search('^set "REFUSAL=([^"]*)"', body, re.M)
    if not m:
        wrong.append("no REFUSAL assignment found")
    else:
        refusal = m.group(1)
        if ".." in refusal:
            wrong.append("REFUSAL is built by hand with a relative path")
        if "sotto-preflight-refusal-%RANDOM%%RANDOM%" not in refusal:
            wrong.append("REFUSAL name lost its prefix or a RANDOM half: " + repr(refusal))
    for folder in (MAIN, WEBVIEW):
        if not os.path.isdir(folder):
            continue
        for f in os.listdir(folder):
            if "preflight-refusal" in f and f.endswith(".txt") and not NAME.match(f):
                wrong.append("a MANGLED capture file is on disk: " + folder + "/" + f)
    say("")
    if wrong:
        for w in wrong:
            say("  wrong: " + w)
        say("VERDICT: FAIL -- hand-written path or a mangled capture on disk")
        return 1
    say("VERDICT: PASS -- the directory is resolved, the name carries both random halves,")
    say("               and no mangled capture exists in _main/ or app/webview/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
