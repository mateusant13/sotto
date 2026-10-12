"""Launch the Electron dom-probe with NO console window.

CREATE_NO_WINDOW on the Electron process and on python itself. Used for every
probe in this lane so no run can flash a console on the owner's desktop.
Kill by artifact path only -- never the bare word 'sotto'.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"H:\sotto")
ELECTRON = ROOT / "app" / "node_modules" / "electron" / "dist" / "electron.exe"
FLAGS = 0x08000000  # CREATE_NO_WINDOW


def run(script: str, timeout: int = 120) -> int:
    """Run the probe under a timeout that is a REAL ceiling for a process TREE.

    AUDIT ROW #62: `subprocess.run(timeout=)` around the multi-process electron.exe is not a ceiling.
    MEASURED 2026-10-12 by _main/timeout-tree-ceiling-oracle.py: on Windows the timeout kills the DIRECT
    child only, and the grandchildren an Electron run leaves behind (its own gpu/renderer/utility
    processes, and any child a probe spawned) stay ALIVE -- a staged tree left 1 survivor behind with
    `subprocess.run(timeout=)` and 0 with the tree kill below. `run()` also could not reap them: it hid
    the pid, and TimeoutExpired carries the command, not the process.

    So the child is a Popen (whose pid we keep) and a timeout ends with `taskkill /F /T` on that pid --
    the tree, by pid, never by image name. Return 124 (the conventional timeout status) so a caller can
    tell a timeout from a probe that finished and failed.
    """
    cmd = [str(ELECTRON), script]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT / "app"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=FLAGS,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            creationflags=FLAGS,
        )
        try:
            out, err = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        rc = 124
    sys.stdout.write(out or "")
    sys.stderr.write(err or "")
    return rc


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "electron/dom-probe.js"
    sys.exit(run(target))