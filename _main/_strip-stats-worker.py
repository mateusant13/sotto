#!/usr/bin/env python3
"""A STAND-IN worker for the STATS arm: opens NO audio device.

WHY IT EXISTS: proving that `getStats`/`onStats` FEED the panel's level meter
needs a worker that publishes a `WORKER_STATS` line, and the lane's rules forbid
opening an audio device (the owner's own worker holds the loopback). This occupies
exactly the slot `WorkerBridge` spawns and does nothing but print the two line
kinds the shell's reader consumes:

  * a `status` object on STDOUT (the pump parses JSON there), so the panel leaves
    "Starting the worker";
  * `WORKER_STATS` lines on STDERR, which is where the real worker writes them
    (`_pump` reads stderr for `WORKER_STATS`/`WORKER_ALIVE`);
  * `meter` objects on STDOUT — `{"type":"meter","peak":<window>,"blocks":<n>}`,
    exactly the shape `worker/sotto_worker.py:3591` emits — because the shell's
    WAVE branch reads that and its `peak` is a WINDOW peak, not a running max;
  * a `caption` with `final:true` on STDOUT (the CLOSED line): it is the boundary
    a held hot reload lands on, so the reload instrument needs one from a REAL
    child process.

The numbers are the shape of a REAL measurement — `peak` and `blocks` are exactly
what the owner's app logged (`peak=0.443448`) — but they are OURS, not a device's.
Nothing here says an audio device was opened.

    python _main/_strip-stats-worker.py [--secs N] [--hz N] [--meter-hz N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

STATS = ('WORKER_STATS tag=tick peak={peak} blocks=812 nonzero_blocks=806 '
         'queue_drops=0 reruns=0 audio_s=12.5 infer_wall_s=2.1 captions=3')


def main() -> int:
    # The shell spawns the worker as `[python, <worker_path>]` — NO extra argv —
    # so the knobs travel in the ENVIRONMENT, which `WorkerBridge._spawn` copies
    # from the shell's own environment.
    ap = argparse.ArgumentParser()
    ap.add_argument('--secs', type=float,
                    default=float(os.environ.get('SOTTO_STANDIN_SECS', '120')))
    #: The meter's own cadence. The worker publishes `WORKER_STATS` per meter
    #: sample, so this is what the shell's per-sample log would have to survive.
    ap.add_argument('--hz', type=float,
                    default=float(os.environ.get('SOTTO_STANDIN_HZ', '0.5')))
    ap.add_argument('--peak', default=os.environ.get('SOTTO_STANDIN_PEAK',
                                                     '0.443448'))
    #: The WAVE's cadence, on STDOUT. 0 disables it (the shell must then fall
    #: back to the stderr running maximum, which is the other colour).
    ap.add_argument('--meter-hz', type=float,
                    default=float(os.environ.get('SOTTO_STANDIN_METER_HZ', '0')))
    #: Emit ONE `caption` with `final:true` this many seconds in. -1 = never.
    ap.add_argument('--closed-at', type=float,
                    default=float(os.environ.get('SOTTO_STANDIN_CLOSED_AT',
                                                 '-1')))
    args, _unknown = ap.parse_known_args()

    sys.stdout.write(json.dumps({
        'type': 'status', 'state': 'capture-started',
        'detail': 'stand-in worker for the stats arm (no audio device)'}) + '\n')
    sys.stdout.flush()
    interval = 1.0 / args.hz if args.hz > 0 else 2.0
    meter_interval = 1.0 / args.meter_hz if args.meter_hz > 0 else 0.0
    start = time.time()
    deadline = start + args.secs
    next_meter = start
    next_closed = (start + args.closed_at) if args.closed_at >= 0 else None
    #: A WAVE, not a constant: the peak of each window walks up and down, which
    #: is the whole point of a meter (`0.443448` is only the FIRST sample).
    step = 0
    while time.time() < deadline:
        sys.stderr.write(STATS.format(peak=args.peak) + '\n')
        sys.stderr.flush()
        now = time.time()
        if meter_interval and now >= next_meter:
            # The window peak OSCILLATES, so a consumer reading a running maximum
            # and one reading the window differ measurably.
            wave = [0.10, 0.42, 0.18, 0.31, 0.07, 0.55, 0.23, 0.12][step % 8]
            step += 1
            sys.stdout.write(json.dumps({'type': 'meter', 'peak': wave,
                                         'blocks': 12}) + '\n')
            sys.stdout.flush()
            next_meter = now + meter_interval
        if next_closed is not None and now >= next_closed:
            sys.stdout.write(json.dumps({
                'type': 'caption', 'text': 'stand-in closed line',
                'final': True, 'start': 0.0, 'end': 1.0}) + '\n')
            sys.stdout.flush()
            next_closed = None
        time.sleep(min(0.05, interval))
    return 0


if __name__ == '__main__':
    sys.exit(main())
