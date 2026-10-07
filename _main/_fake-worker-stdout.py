#!/usr/bin/env python3
"""A STAND-IN worker: a child process that opens NO audio device.

WHY IT EXISTS: the Quit has to be proved to kill the WORKER, and the lane's rules
forbid opening an audio device. The real `worker/sotto_worker.py` opens a WASAPI
loopback in `start()`, so it cannot be used as the subject here. This stand-in
occupies exactly the same slot — a child process of the shell, spawned by
`WorkerBridge` — and does nothing but write its pid and sleep, so "the Quit left
a worker running" is measurable without any device.

It is NOT the worker and nothing here says it is.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid-file', default=None)
    ap.add_argument('--secs', type=float, default=600.0)
    args, _unknown = ap.parse_known_args()

    if args.pid_file:
        with open(args.pid_file, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps({'pid': os.getpid(), 'argv': sys.argv}))
    # One status line so the bridge's reader thread has something to consume, and
    # a WORKER_STATS heartbeat so its silence watchdog is fed. No device.
    sys.stdout.write(json.dumps({'type': 'status', 'state': 'listening',
                                 'detail': 'stand-in worker (no audio device)'}) + '\n')
    sys.stdout.flush()
    deadline = time.time() + args.secs
    while time.time() < deadline:
        sys.stderr.write('WORKER_STATS peak=0.0 blocks=0 captions=0\n')
        sys.stderr.flush()
        time.sleep(2.0)
    return 0


if __name__ == '__main__':
    sys.exit(main())
