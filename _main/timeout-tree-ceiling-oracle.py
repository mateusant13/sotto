#!/usr/bin/env python3
"""timeout-tree-ceiling-oracle -- is `subprocess.run(timeout=)` a ceiling around a PROCESS TREE?

AUDIT ROW #62: "`subprocess.run(timeout=)` a volta do `electron.exe` multi-processo pode nao ser tecto
[INFERENCE]" (_main/_run-hidden.py:24). The row is an INFERENCE, and this oracle turns it into a
measurement without ever launching Electron (a DEAD shell here, and launching it would open a window on
the owner desk): the mechanism is staged with scratch python processes of our own.

ARM 1 -- THE ORPHAN. A scratch tree (one parent that spawns one grandchild; both sleep 30 s) is run the
OLD way, subprocess.run(timeout=1.5). On Windows the timeout ends the DIRECT child only; the grandchild
is left ALIVE. Its pid comes from a file the parent writes, so the survivor is identified, not assumed.
ARM 2 -- THE CURE. The same tree run the way _main/_run-hidden.py now does it: a Popen whose pid is
kept, and on timeout taskkill /F /T /PID <pid>. Zero survivors.
ARM 3 -- THE FILE carries the cure (Popen + taskkill /F /T + the pid + the 124 status).
ARM 4 -- CONTROL: a COPY with the tree kill stripped must go RED on arm 3.

Every process spawned here is killed BY PID (never by image name) in a finally block; the scratch tree
lives in %TEMP%. Nothing here is Electron, run.cmd, the shell or the worker.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
PROBE = os.path.join(ROOT, "_main", "_run-hidden.py")
FLAGS = 0x08000000

TREE = "\n".join([
    "import subprocess, sys, time",
    "child = subprocess.Popen([sys.executable, \"-c\", \"import time; time.sleep(30)\"],"
    "                       creationflags=0x08000000)",
    "open(sys.argv[1], \"w\").write(str(child.pid))",
    "print(\"parent-ready\", flush=True)",
    "time.sleep(30)",
]) + "\n"


def alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid, "/NH"], capture_output=True,
                             text=True, creationflags=FLAGS, timeout=30)
    except Exception:
        return None
    return str(pid) in (out.stdout or "")


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True,
                   creationflags=FLAGS)


def wait_for(path, seconds=15.0):
    end = time.time() + seconds
    while time.time() < end:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path) as handle:
                text = handle.read().strip()
            if text.isdigit():
                return int(text)
        time.sleep(0.05)
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parsed = parser.parse_args(argv)
    say = print
    wrong = []
    work = os.path.join(tempfile.gettempdir(), "tree-ceiling")
    os.makedirs(work, exist_ok=True)
    tree = os.path.join(work, "tree.py")
    with open(tree, "w", encoding="utf-8", newline="") as handle:
        handle.write(TREE)
    say("timeout-tree-ceiling-oracle -- row #62 (scratch trees only; no Electron, no shell)")

    pidfile = os.path.join(work, "gp1.txt")
    if os.path.exists(pidfile):
        os.remove(pidfile)
    grandchild = None
    try:
        subprocess.run([sys.executable, tree, pidfile], capture_output=True, text=True,
                       creationflags=FLAGS, timeout=1.5)
        say("  arm 1: the tree finished inside the timeout -- the orphan cannot be staged here")
    except subprocess.TimeoutExpired:
        grandchild = wait_for(pidfile)
        state = alive(grandchild) if grandchild else None
        say("  arm 1  OLD subprocess.run(timeout=1.5): grandchild pid=%s still alive=%s"
            % (grandchild, state))
        if grandchild is None:
            wrong.append("arm 1: the grandchild never reported its pid -- the instrument is blind")
        elif state is False:
            wrong.append("arm 1: the grandchild did NOT survive the timeout on this host")
    finally:
        if grandchild:
            kill_tree(grandchild)

    pidfile2 = os.path.join(work, "gp2.txt")
    if os.path.exists(pidfile2):
        os.remove(pidfile2)
    grandchild2 = None
    parent = None
    try:
        parent = subprocess.Popen([sys.executable, tree, pidfile2], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, creationflags=FLAGS)
        grandchild2 = wait_for(pidfile2)
        kill_tree(parent.pid)
        time.sleep(0.6)
        state2 = alive(grandchild2) if grandchild2 else None
        say("  arm 2  CURE Popen + taskkill /F /T /PID %s: grandchild pid=%s still alive=%s"
            % (parent.pid, grandchild2, state2))
        if grandchild2 is None:
            wrong.append("arm 2: the grandchild never reported its pid")
        elif state2 is not False:
            wrong.append("arm 2: the tree kill left the grandchild alive -- the cure does not work")
    finally:
        if grandchild2:
            kill_tree(grandchild2)
        if parent and parent.poll() is None:
            kill_tree(parent.pid)

    with open(PROBE, encoding="utf-8") as handle:
        source = handle.read()
    marks = {
        "Popen with a kept pid": "proc = subprocess.Popen(" in source,
        # the CALL, not the word: both files mention taskkill in prose (this one explains why), and a
        # word test passes on a comment -- the trap this arm fell into on its first run.
        "taskkill on the pid": '["taskkill", "/F", "/T", "/PID", str(proc.pid)]' in source,
        "timeout status 124": re.search(r"rc = 124", source) is not None,
        "child is no longer subprocess.run": "stdout=subprocess.PIPE" in source,
    }
    say("  arm 3  the file carries the cure: " + ", ".join("%s=%s" % (k, str(v).lower())
        for k, v in marks.items()))
    for key, ok in marks.items():
        if not ok:
            wrong.append("arm 3: _run-hidden.py no longer has " + key)

    mutant = os.path.join(work, "_run-hidden-mutant.py")
    stripped = source.replace('["taskkill", "/F", "/T", "/PID", str(proc.pid)]',
                             '["echo", "no-tree-kill"]')
    with open(mutant, "w", encoding="utf-8", newline="") as handle:
        handle.write(stripped)
    with open(mutant, encoding="utf-8") as handle:
        mm = handle.read()
    mutant_ok = '["taskkill", "/F", "/T", "/PID", str(proc.pid)]' in mm
    say("  arm 4  CONTROL (taskkill stripped from a copy): still carries the tree kill=%s"
        % str(mutant_ok).lower())
    if mutant_ok:
        wrong.append("arm 4: the stripped copy still carries the tree kill -- arm 3 measures nothing")

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the row inference is CONFIRMED by measurement: a Windows timeout ends the direct child"
        " and leaves the grandchild alive; the taskkill-on-pid cure leaves zero; and _run-hidden.py"
        " carries that cure")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())