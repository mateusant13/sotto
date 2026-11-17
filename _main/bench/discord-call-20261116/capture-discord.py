"""Capture ONE program's audio (Discord's process tree) into a benchmark track.

WHY: the endpoint mix that the ring already records contains EVERYTHING the
machine renders (game, music, alerts). For a benchmark that judges voice
separation on the call itself, the reference has to be the call only. Windows
process loopback (`VAD\\Process_Loopback`, INCLUDE_TARGET_PROCESS_TREE) gives
exactly that, and `worker/sotto_worker.ProcessLoopbackTap` already implements it
-- this script is the thin harness that points it at the ring writer instead of
at the ASR.

WHAT IT REUSES, NOT REIMPLEMENTS
  * `worker/process_target.resolve()`  -- image name -> tree ROOT pid
  * `worker/sotto_worker.ProcessLoopbackTap` -- the 48 kHz declared-format tap
  * `worker/sotto_worker.resample_to_16k`     -- 48000 -> 16000 (3:1 boxcar)
  * `worker/audio_ring.AudioRing`             -- ogg opus segments + pruning

BOUNDED AND HIDDEN BY CONSTRUCTION
  * `--duration` stops it (default 900 s, and the caller also wraps it in
    `python -m watcher run --cpu 40 --timeout ...`).
  * no audio device is opened, muted or re-configured: process loopback is a
    read-only tap of one process tree.
  * launched with `pythonw.exe`, so there is no console window on the owner's
    screen; everything it has to say goes to `--log`.

Usage (caged, hidden):
  PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 --io very-low \
    --timeout 1200 -- pythonw.exe _main/bench/discord-call-20261116/capture-discord.py \
    --out _main/bench/discord-call-20261116/capture --duration 900
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
WORKER = os.path.join(ROOT, 'worker')
if WORKER not in sys.path:
    sys.path.insert(0, WORKER)

import numpy as np                                                     # noqa: E402

import audio_ring                                                      # noqa: E402
import process_target                                                  # noqa: E402
import sotto_worker                                                    # noqa: E402


def _run(argv):
    r = subprocess.run(argv, capture_output=True)
    if r.returncode:
        raise SystemExit('command failed rc=%d: %r\n%s'
                         % (r.returncode, argv, r.stderr.decode('utf-8', 'replace')[:400]))
    return r.stdout


def concat_segments(day_dir, out_path):
    """Stream-copy the closed opus segments into ONE file (no re-encode)."""
    segs = [os.path.join(day_dir, n) for n in sorted(os.listdir(day_dir))
            if n.endswith('.opus') and os.path.getsize(os.path.join(day_dir, n)) > 0]
    if not segs:
        return None, 0
    lst = out_path + '.concat.txt'
    with open(lst, 'w', encoding='utf-8') as fh:
        for p in segs:
            fh.write("file '%s'\n" % p.replace('\\', '/'))
    _run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '1',
          '-f', 'concat', '-safe', '0', '-i', lst, '-map', '0:a:0',
          '-c:a', 'copy', '-f', 'ogg', out_path])
    os.remove(lst)
    return out_path, len(segs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--target-name', default='Discord.exe')
    ap.add_argument('--out', default=os.path.join(HERE, 'capture'))
    ap.add_argument('--duration', type=float, default=900.0,
                    help='stop after this many seconds (default 900)')
    ap.add_argument('--segment-s', type=float, default=60.0,
                    help='ring segment length in audio seconds (default 60)')
    ap.add_argument('--block-ms', type=float, default=100.0)
    ap.add_argument('--log', default=None)
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    log_path = args.log or os.path.join(out_dir, 'capture.log')

    def log(msg):
        line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
        try:
            with open(log_path, 'a', encoding='utf-8') as fh:
                fh.write(line + '\n')
        except OSError:
            pass

    pid = process_target.resolve(args.target_name)
    if not pid:
        log('REFUSED no running process matches %r' % args.target_name)
        return 2
    desc = sotto_worker._plp_proc_desc(pid) or ''
    log('TARGET name=%s pid=%s desc=%r duration_s=%.0f out=%s'
        % (args.target_name, pid, desc, args.duration, out_dir))

    ring = audio_ring.AudioRing(out_dir, hours=1.0, kbps=24,
                                segment_s=args.segment_s, cap_mb=100.0, log=log)
    if not ring.enabled:
        log('REFUSED ring did not start (no ffmpeg?)')
        return 2

    stats = {'blocks': 0, 'samples_16k': 0, 'peak': 0.0, 't0': time.time(),
             'pid': pid, 'name': args.target_name}
    rates = {}

    def on_block(block):
        """The tap hands mono float32 at the endpoint's own rate (48000 here)."""
        r = int(rates.get('rate') or 48000)
        x = sotto_worker.resample_to_16k(np.asarray(block, dtype=np.float32), r)
        if x.size:
            ring.push(x)
            stats['blocks'] += 1
            stats['samples_16k'] += int(x.size)
            stats['peak'] = max(stats['peak'], float(np.abs(x).max()))

    tap = sotto_worker.ProcessLoopbackTap(on_block, pid, pid_desc=desc,
                                          block_ms=args.block_ms)
    tap.start()
    rates['rate'] = tap.rate
    log('TAP_OPENED pid=%s rate=%d channels=%d block=%d'
        % (pid, tap.rate, tap.channels, tap.block))

    deadline = time.time() + float(args.duration)
    try:
        while time.time() < deadline:
            if tap.pump_exited:
                log('PUMP_EXITED hr=%s where=%s' % (tap.pump_exit_hr, tap.pump_exit_where))
                break
            time.sleep(0.5)
    finally:
        tap.close()
        ring.close()

    day_dir = os.path.join(out_dir, 'history', 'audio',
                           time.strftime('%Y-%m-%d'))
    track, nseg = concat_segments(day_dir, os.path.join(out_dir, 'discord.24k.opus')) \
        if os.path.isdir(day_dir) else (None, 0)

    stats.update({
        'wall_s': round(time.time() - stats['t0'], 1),
        'ring': ring.status(),
        'segments': nseg,
        'track': track,
        'track_bytes': os.path.getsize(track) if track else 0,
    })
    with open(os.path.join(out_dir, 'capture-status.json'), 'w', encoding='utf-8') as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)
        fh.write('\n')
    log('DONE ' + json.dumps({k: stats[k] for k in
                              ('wall_s', 'blocks', 'samples_16k', 'peak', 'segments',
                               'track_bytes')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
