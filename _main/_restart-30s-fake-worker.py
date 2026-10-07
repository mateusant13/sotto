"""The worker's REAL line shapes, held still, for the 30 s restart-loop lane.

This is an ORACLE FIXTURE, not a worker: it opens no device, loads no model and
renders no audio. What it reproduces is the SHAPE measured in the owner's log
(`_main/webview-run.log`, 2026-10-06, pid=4312 / pid=47056):

  * the warm-up stdout statuses the shell sees at every respawn,
  * ONE caption (the tap declared signal — the ladder settles on it),
  * and then NOTHING on stdout, while the worker keeps publishing its own
    heartbeat `WORKER_STATS tag=tick` on STDERR every `--stats-interval`
    (10 s in the field) with an ADVANCING `blocks=` counter — which is the
    worker telling anyone who reads stderr that it is still consuming audio.

That last line is the whole subject of the lane: it is the only PERIODIC signal
the worker emits, and the shell's no-output watchdog did not count it.

MODE arrives through `SOTTO_FAKE_MODE`, because `WorkerBridge._spawn` launches
`[python, <this file>]` with no extra argv and copies `os.environ` into the
child. `SOTTO_FAKE_TICK_MS` scales the 10 s heartbeat down to the oracle's
compressed clock; the RATIO to the watchdog window is what is under test, not
the absolute number.

  heartbeat  warm-up, one caption, then a heartbeat every tick_ms forever.
             The worker is WORKING. Nothing else is written to stdout.
  wedge      the same warm-up, one heartbeat, then SILENCE on BOTH streams:
             deliberately indistinguishable from a jammed worker, and the
             reason the watchdog must keep existing after the cure.
"""

import json
import os
import sys
import time

DEV = "WASAPI loopback: {0.0.0.00000000}.{9f2c1d84-0000-0000-0000-000000000000}"


def emit(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()


def stats(blocks):
    """The exact `WORKER_STATS tag=tick …` shape `sotto_worker.py` prints."""
    sys.stderr.write(
        f"WORKER_STATS tag=tick blocks={blocks} block_samples={blocks * 4800} "
        f"nonzero_blocks={blocks} peak=0.351506 rms=0.02548697 gain_db=+15.1 "
        f"held_blocks={blocks} speech_blocks={blocks // 4} agc=on "
        f"resampled_samples={blocks * 1600} chunks={blocks // 4} captions=2 "
        f"tokens=12 frames=82 blanks=70 blank_frac=0.8537 empty_chunks=8 "
        f"vad_gated_chunks=0 music_gated_chunks=24 gate_kept=10 gate=on "
        f"queue_drops=0 reruns=0 rerun_wall_s=0.00 audio_s=19.04 "
        f"infer_wall_s=1.78 rss_mb=2415.9\n")
    sys.stderr.flush()


def preamble():
    """boot/model-loading/model-loaded/gate/device/capture-started, on stdout."""
    for state in ("boot", "model-loading", "model-loaded"):
        emit(type="status", state=state)
    emit(type="status", state="gate")
    emit(type="status", state="device")
    emit(type="status", state="capture-started", device=DEV, rate=48000,
         block=4800)
    #: A caption: the tap DECLARED signal. Without one the shell would be right
    #: to suspect the audio, and this lane is not about the audio.
    emit(type="caption", text="Olha o")


def main():
    mode = os.environ.get("SOTTO_FAKE_MODE", "heartbeat")
    try:
        tick_ms = float(os.environ.get("SOTTO_FAKE_TICK_MS", "150"))
    except ValueError:
        tick_ms = 150.0
    preamble()
    blocks = 0
    if mode == "wedge":
        # ONE heartbeat, then nothing on either stream, ever.
        blocks += 20
        stats(blocks)
        while True:
            time.sleep(0.2)
    while True:
        blocks += 20
        stats(blocks)
        time.sleep(max(tick_ms, 1.0) / 1000.0)


if __name__ == "__main__":
    sys.exit(main())
