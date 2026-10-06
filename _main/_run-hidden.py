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
    cmd = [str(ELECTRON), script]
    p = subprocess.run(
        cmd,
        cwd=str(ROOT / "app"),
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=FLAGS,
    )
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr)
    return p.returncode


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "electron/dom-probe.js"
    sys.exit(run(target))