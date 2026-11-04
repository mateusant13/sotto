"""NEGATIVE CONTROL for the 2026-11-03 boot change: does the number come back?

    python worker/_probe/boot-control.py

Materialises `worker/sotto_worker.py` as it is at `git HEAD` next to the real one
(the worker imports `engine_switch`/`live_queue` BY NAME from its own directory,
so the control has to live in `worker/`), measures BOTH scripts with the SAME
instrument (`boot-io.py`), and removes the control file again.

The only difference between the two arms is the boot change itself: same box, same
weights, same disk state, back to back. If the control arm does not return to the
pre-change number, the change is not what moved it.
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.dirname(HERE)
REPO = os.path.dirname(WORKER)
CTL = os.path.join(WORKER, "_head-control-sotto_worker.py")
PROBE = os.path.join(HERE, "boot-io.py")


def run(label, script):
    print("== %s (%s)" % (label, os.path.basename(script)), flush=True)
    out = subprocess.run([sys.executable, PROBE, "--script", script],
                         cwd=REPO, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for line in out.stdout.splitlines():
        if line.startswith("RESULT"):
            print(line, flush=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr[-2000:])
    return out.returncode


def main():
    src = subprocess.run(["git", "show", "HEAD:worker/sotto_worker.py"],
                         cwd=REPO, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    if src.returncode != 0:
        print("cannot read HEAD worker:", src.stderr[-400:])
        return 2
    with open(CTL, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src.stdout)
    try:
        a = run("HEAD (before)", CTL)
        b = run("WORKTREE (after)", os.path.join(WORKER, "sotto_worker.py"))
        a2 = run("HEAD (before, again)", CTL)
    finally:
        try:
            os.remove(CTL)
        except OSError:
            pass
    return 0 if a == 0 and b == 0 and a2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
