"""The line shapes worker/sotto_worker.py writes, held still for the bridge.

This is an ORACLE FIXTURE, not a worker: it opens no device, loads no model and
renders no audio. It writes exactly the JSONL `type: "status"` shapes the real
worker writes on stdout and then goes quiet, which is the whole subject of the
lane: what the shell does with a worker that is alive and has nothing to say.

MODE arrives through `SOTTO_FAKE_MODE`, because `WorkerBridge._spawn` launches
`[python, <this file>]` with no extra argv and copies `os.environ` into the
child. The default is `idle`.

  idle           AN IDLE DESKTOP, as measured (`_main/_live_owner3.log`): the
                 ladder opens candidate after candidate, every one of them flat,
                 and the run then streams a tap that carries nothing -- nothing
                 on stdout, forever. The child stays ALIVE.
  verdict-quiet  the same, and the worker has ALSO published its TERMINAL
                 device verdict (`silent-device`, `device-exhausted`) and its
                 `done` line before going quiet -- the exact verdict words from
                 worker/sotto_worker.py:2319-2371/2415, fed as the shell sees
                 them.
  signal-quiet   the tap DECLARED signal -- a caption came out, which is the one
                 thing the ladder settles on -- and then the child went mute.
  no-verdict     the stream simply opened (`capture-started`) and nothing else,
                 ever: the shape of a wedged worker, and the only silence the
                 shell is still allowed to call anomalous.
"""

import json
import os
import sys
import time

DEV = "WASAPI loopback: {0.0.0.00000000}.{9f2c1d84-0000-0000-0000-000000000000}"


def emit(**kw):
    sys.stdout.write(json.dumps(kw) + "\n")
    sys.stdout.flush()


def preamble():
    """boot/model-loading/model-loaded/gate/device -- the warm-up the shell sees."""
    for _ in range(3):
        emit(type="status", state="boot")
    emit(type="status", state="model-loading")
    emit(type="status", state="model-loaded")
    emit(type="status", state="gate")
    emit(type="status", state="device")


def candidate(attempt, of):
    emit(type="status", state="capture-started", device=DEV, rate=48000,
         block=4800, attempt=attempt, of=of)


def rotate(attempt, of, peak):
    emit(**{
        "type": "status", "state": "device-rotated", "reason": "flat",
        "from": DEV, "to": DEV + " (next)",
        "peak": peak, "run_peak": peak, "window_s": 6.0, "peak_floor": 0.002,
        "attempt": attempt, "of": of,
    })


def main():
    mode = os.environ.get("SOTTO_FAKE_MODE", "idle")
    preamble()
    if mode == "idle":
        # Three candidates opened, none produced a caption, then the fourth
        # opens and the run streams it: from here the real worker writes nothing
        # on stdout. The PEAKS are the measured ones from the live idle run
        # (`_main/_tap-restart-live-after.log`: `device-rotated reason=flat
        # peak=0.465216 floor=0.002`) -- note the loudest of them is ABOVE the
        # floor, because `reason=flat` means "no caption in this window", not
        # "silence". A fixture that used only sub-floor peaks would be testing a
        # case the real worker does not produce.
        for i, peak in enumerate((0.0, 0.000122, 0.465216), start=1):
            candidate(i, 6)
            rotate(i, 6, peak)
        candidate(4, 6)
    elif mode == "verdict-quiet":
        for i, peak in enumerate((0.0, 0.000122), start=1):
            candidate(i, 2)
            rotate(i, 2, peak)
        candidate(3, 3)
        emit(type="status", state="device-exhausted", reason="all-flat",
             detail="every candidate tap was flat over 6.0s (peak floor 0.002)",
             device=DEV, tried=[DEV], rotations=2, peak=0.000122, captions=0)
        emit(type="status", state="silent-device", verdict="silent-device",
             device=DEV, api="MME", peak=0.000122, peak_floor=0.002, blocks=122,
             window_s=6.0, silent_min_blocks=20,
             detail=f"{DEV} [MME] opened and delivered 122 blocks but never "
                    "reached peak 0.002 -- digital silence, not a model fault.",
             captions=0)
        emit(type="status", state="done", verdict="silent-device", blocks=341,
             peak=0.000122, chunks=102, captions=0, audio_s=57.12,
             peak_rss_mb=2413.7)
    elif mode == "signal-quiet":
        candidate(1, 1)
        emit(type="caption", text="ola mundo", start=0.0, end=1.4)
        emit(type="status", state="done", verdict="captions-emitted",
             blocks=90, peak=0.24, chunks=18, captions=1)
    elif mode == "no-verdict":
        candidate(1, 6)
    else:
        sys.stderr.write(f"fake-worker: unknown SOTTO_FAKE_MODE={mode!r}\n")
        return 2

    # ALIVE AND QUIET. This is the state the shell's watchdog has to judge; the
    # child must not exit, or the shell would be measuring a death, not a silence.
    while True:
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
