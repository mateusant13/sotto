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

# O PAR QUE ESCONDE (medido 2026-11-04 na tela do dono): o `creationflags`
# pede, o `startupinfo` e o que o Windows respeita quando o pai nao tem
# consola. Sem ele o Windows Terminal pinta a consola NOVA do filho.
if os.name == "nt":
    _SI = subprocess.STARTUPINFO()
    _SI.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    _SI.wShowWindow = 0
else:
    _SI = None
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.dirname(HERE)
REPO = os.path.dirname(WORKER)
CTL = os.path.join(WORKER, "_head-control-sotto_worker.py")
PROBE = os.path.join(HERE, "boot-io.py")

# Ceiling for both child processes. `boot-io.py` spawns the worker and waits up
# to 600 s itself; the owner's log shows 65-206 s to `model-loaded` on a
# contended disk (6 s idle). 300 s clears that documented worst case with
# margin, yet caps a hung child at 5 min -- caught well before boot-io's own
# 600 s inner ceiling would let it linger. Used at both subprocess.run sites.
CHILD_TIMEOUT_S = 300


def run(label, script, argv=None):
    """Return the probe's rc; argv overrides the probe command (selftest only)."""
    print("== %s (%s)" % (label, os.path.basename(script)), flush=True)
    if argv is None:
        argv = [sys.executable, PROBE, "--script", script]
    try:
        out = subprocess.run(argv, cwd=REPO, capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             startupinfo=_SI, timeout=CHILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        sys.stderr.write("%s: child timed out after %ss\n" % (label, CHILD_TIMEOUT_S))
        return 1
    for line in out.stdout.splitlines():
        if line.startswith("RESULT"):
            print(line, flush=True)
    if out.returncode != 0:
        sys.stderr.write(out.stderr[-2000:])
    return out.returncode


def main():
    try:
        src = subprocess.run(["git", "show", "HEAD:worker/sotto_worker.py"],
                             cwd=REPO, capture_output=True, text=True,
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             startupinfo=_SI, timeout=CHILD_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        sys.stderr.write("git show timed out after %ss\n" % CHILD_TIMEOUT_S)
        return 2
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


def _selftest():
    """Prove the TimeoutExpired arm fires with CHILD_TIMEOUT_S shrunk.

    The child sleeps via `py -c`; a tiny timeout must make run() name the
    ceiling on stderr and return its failure rc, with no traceback.
    """
    import io

    global CHILD_TIMEOUT_S
    real_timeout = CHILD_TIMEOUT_S
    stderr = sys.stderr
    captured = io.StringIO()
    try:
        CHILD_TIMEOUT_S = 0.05
        sys.stderr = captured
        rc = run("slow child", "-c",
                 argv=[sys.executable, "-c", "import time; time.sleep(2)"])
    finally:
        sys.stderr = stderr
        CHILD_TIMEOUT_S = real_timeout
    msg = captured.getvalue()
    print("selftest: timeout arm rc=%d stderr=%r" % (rc, msg), flush=True)
    if rc != 1 or "timed out after 0.05s" not in msg:
        sys.stderr.write("selftest FAIL: timeout arm did not fire\n")
        return 1
    print("selftest OK: timeout arm caught the slow child", flush=True)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
