#!/usr/bin/env python3
"""A REAL-ASR worker in the slot `WorkerBridge` spawns -- for lane/cap2panel.

WHY A WRAPPER. `SottoShell.start_worker` spawns the worker as exactly
`[python, <worker_path>]` -- NO extra argv (`_strip-stats-worker.py:40-42`, and
`WorkerBridge._spawn`). So the flags the owner needs (`--selftest --audio ...`)
cannot be passed through the panel's own CLI.

THE TRAP THIS FILE EXISTS TO AVOID. `--audio` is SILENTLY IGNORED unless
`--selftest` is ALSO passed. A wrapper that forwarded only `--audio` would
transcribe the LIVE ROOM and look like a working delivery while producing
whatever the desktop happened to be playing. Both flags are always set here,
together, so this worker reads a FILE and cannot touch a device.

It is `runpy.run_path`, not a reimplementation: the captions on stdout are the
REAL worker's, produced by the REAL model in `H:/sotto/worker/models`. Nothing
in this file formats, filters or invents a caption.
"""
from __future__ import annotations

import os
import runpy
import sys

WORKER = r'H:\sotto\worker\sotto_worker.py'
AUDIO = r'H:\sotto\worker\assets\sample1.flac'


def main() -> int:
    # Always BOTH flags. `--audio` alone is ignored (see the module docstring).
    sys.argv = [WORKER, '--selftest', '--audio', AUDIO]
    # The selftest report is already stderr-only; stdout stays pure JSONL so
    # `WorkerBridge._consume` sees nothing but `{"type":"caption",...}` lines.
    os.environ.setdefault('PYTHONUNBUFFERED', '1')
    try:
        runpy.run_path(WORKER, run_name='__main__')
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == '__main__':
    sys.exit(main())