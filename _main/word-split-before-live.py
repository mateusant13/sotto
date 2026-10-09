"""The NEGATIVE-CONTROL run on the **LIVE** path: `SOTTO_FILE_TAP` + one function reverted.

WHY THIS EXISTS (lane MEDICAO / live-audio sweep)
-------------------------------------------------
`_main/word-split-before-run.py` reverts `join_fragments` on the FILE arm
(`sotto_worker.selftest()`), which runs its OWN chunk loop and never enters
`asr_thread`. The receipt that closed the word-split fix (`_main/receipt-word-split-fix.md`)
names exactly that as the gap: "NOT proven: the live DEVICE path ... and the
second pass end-to-end".

This driver closes it WITHOUT opening an audio device. `SOTTO_FILE_TAP=<path>`
(worker/sotto_worker.py `file_tap_candidate` / `FileTap`) swaps the device ladder
for one file-sourced candidate, so the file's PCM is delivered through the REAL
live `asr_thread` — `seg_pcm` retention/prune, the five `drain()` call sites and
the `drain` -> `finalise` -> `rerun` second pass included. `join_fragments` is
then replaced by its pre-fix body, so BEFORE and AFTER are produced by the same
code, the same model and the same audio.

It opens NO audio device and writes NO file outside `_main/`.

Usage:
  py -3 _main/word-split-before-live.py --wav _main/live-sample-cable-input-90s.wav \
      --out _main/sweep90-live-before.jsonl --max-seconds 140
"""

from __future__ import annotations

import argparse
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)


def pre_fix_join(frags) -> str:
    """The shipped join, verbatim: every chunk seam became a word boundary."""
    return " ".join(t for t, _c in frags if t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=os.path.join(HERE, "live-sample-cable-input-90s.wav"))
    ap.add_argument("--out", default=os.path.join(HERE, "sweep90-live-before.jsonl"))
    ap.add_argument("--max-seconds", type=float, default=140.0)
    ap.add_argument("--threads", type=int, default=1)
    args = ap.parse_args()

    # The live loop, fed from a file, no device. Set BEFORE `W.main()` reads it.
    os.environ["SOTTO_FILE_TAP"] = args.wav

    import sotto_worker as W  # noqa: E402

    # ── THE REVERT: exactly one function ────────────────────────────────────
    W.join_fragments = pre_fix_join

    sys.argv = [
        "sotto_worker.py",
        "--max-seconds", str(args.max_seconds),
        "--meter-hz", "0",           # the meter is the OTHER arm's subject
        "--threads", str(args.threads),
    ]

    fh = io.open(args.out, "w", encoding="utf-8")
    real_stdout = sys.stdout
    sys.stdout = fh
    try:
        rc = W.main()
    finally:
        sys.stdout = real_stdout
        fh.close()
    print(f"wrote {args.out} rc={rc} (join_fragments REVERTED, SOTTO_FILE_TAP live loop)",
          file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
