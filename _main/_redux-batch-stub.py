#!/usr/bin/env python3
"""A STAND-IN for `worker/redux_batch.py` — which DOES NOT EXIST YET (2026-10-07).

WHY THIS FILE EXISTS, AND WHAT IT DOES **NOT** CLAIM. The batch engine is another
lane's deliverable. Until it lands, the mode switch cannot be exercised end to end
without SOMETHING on the other end of the CLI contract, and a switch nobody can
observe is exactly the "instrument that tests the model and certifies the machine"
failure this repo keeps paying for. So this stub implements ONLY the contract:

    python _redux-batch-stub.py --wav PATH --json
      -> stdout, one JSON object per line:
         {"type":"caption","text":...,"start":<s>,"end":<s>,"producer":"redux"}

IT IS NOT A TRANSCRIBER. It does not load a model, and no probe fed by it may
claim that transcription works or that Redux is installed. What it DOES do is
report the WAV it was handed — its real duration, in real windows — so the line it
returns PROVES the worker passed the accumulated audio across the process
boundary (the windows have to add up to the WAV) and carries the `producer` field
the canonical transcript requires. That is the whole claim.

`--mode fail` exits non-zero without emitting, and `--mode empty` emits nothing and
exits 0, so the switch's failure and silence paths can be driven on purpose.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave


def main() -> int:
    ap = argparse.ArgumentParser(prog="redux-batch-stub")
    ap.add_argument("--wav", required=True, help="the accumulated audio, 16 kHz mono PCM16")
    ap.add_argument("--json", action="store_true", help="emit JSONL on stdout (the contract)")
    ap.add_argument("--window", type=float, default=5.0,
                    help="seconds of WAV per emitted line")
    ap.add_argument("--mode", default="ok", choices=("ok", "fail", "empty"),
                    help="ok = emit one line per window; fail = exit 4 silently; "
                         "empty = exit 0 with no line (the SILENT batch)")
    args = ap.parse_args()

    if args.mode == "fail":
        sys.stderr.write("redux-batch-stub: --mode fail (deliberate)\n")
        return 4

    with wave.open(args.wav, "rb") as wav:
        rate = wav.getframerate()
        frames = wav.getnframes()
        channels = wav.getnchannels()
        width = wav.getsampwidth()
    seconds = frames / float(rate or 1)

    if args.mode == "empty":
        sys.stderr.write(
            f"redux-batch-stub: --mode empty; heard {seconds:.2f}s, emitting nothing\n")
        return 0

    # NO SILENT SUCCESS: a WAV we cannot read is a setup failure, not an empty
    # transcript, and the caller must be able to tell those apart.
    if rate != 16000 or channels != 1 or width != 2:
        sys.stderr.write(
            f"redux-batch-stub: unexpected WAV shape rate={rate} ch={channels} "
            f"width={width} (the contract is 16 kHz mono PCM16)\n")
        return 5

    window = max(0.5, float(args.window))
    index = 0
    start = 0.0
    while start < seconds:
        end = min(start + window, seconds)
        index += 1
        payload = {
            "type": "caption",
            # NOT a transcription: the text NAMES what was handed over, so a
            # reader of the worker's JSONL sees the audio the light path covered
            # and the fact that this engine is a stand-in.
            "text": (f"redux-stub segment {index:02d} "
                     f"[{start:.2f}-{end:.2f}s of {seconds:.2f}s]"),
            "start": round(start, 2),
            "end": round(end, 2),
            "producer": "redux",
            "model": "redux-batch-stub (NOT the real engine)",
        }
        if args.json:
            sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        start = end
    sys.stderr.write(
        f"redux-batch-stub: wav={args.wav} seconds={seconds:.2f} lines={index}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
