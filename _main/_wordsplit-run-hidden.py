"""Run a command WINDOW-FREE and capture its stdout/stderr to files (lane SottoWordSplit).

WHY (house rule): `python.exe` launched straight from a tool shell put a visible
console on the owner's screen and the census named the pid. This wrapper is
started with `pythonw.exe` (no console of its own) and spawns its child with
`CREATE_NO_WINDOW`, so neither process can paint a window.

Usage:
  pythonw.exe _main/_wordsplit-run-hidden.py --out _main/x.out --err _main/x.err -- <cmd...>
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--err", required=True)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()
    cmd = args.cmd
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        return 2
    with open(args.out, "wb") as fo, open(args.err, "wb") as fe:
        rc = subprocess.call(cmd, stdout=fo, stderr=fe,
                             creationflags=CREATE_NO_WINDOW, cwd=args.cwd)
    with open(args.out + ".rc", "w", encoding="utf-8") as fh:
        fh.write(f"{rc}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
