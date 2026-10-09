"""The clean FILE-arm A/B: same argv, same process, ONE function different.

The earlier attempt (`word-split-before-run.py`) drove `W.selftest(...)` directly
while the NEW colour was driven by `worker/sotto_worker.py --selftest --audio ...`
-- two different entry paths. The two arms then decoded DIFFERENTLY
(`PS.` vs `PCor`, `SDG,` vs `SD`, frames 528 vs 524, infer 210 s vs 14 s), so it
was not a one-function revert and cannot carry a two-colour claim.

This driver removes that: both arms call `W.main()` with the SAME argv, so the
only difference in the whole run is whether `join_fragments` is the on-disk
function or the pre-fix one-liner.

`--mode new` twice gives the determinism control: if two NEW runs do not produce
the same `RECOGNISED` text, the pipeline is not reproducible and NO audio-driven
A/B can be read from it -- say so instead of shipping the diff.

Usage:
  py -3 _main/file-arm-ab.py --wav _main/live-sample-cable-input-90s.wav \
      --mode new --out _main/fa-new-1.jsonl
"""

from __future__ import annotations

import argparse
import io
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pre_fix_join(frags):
    """The join as it was before 2026-10-08: every chunk boundary is a word boundary."""
    return " ".join(t for t, _c in frags if t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=("new", "before"), required=True)
    ap.add_argument("--threads", type=int, default=1)
    args = ap.parse_args()

    wav = os.path.abspath(args.wav)
    out = os.path.abspath(args.out)
    sys.path.insert(0, os.path.join(REPO, "worker"))

    import sotto_worker as W

    if args.mode == "before":
        W.join_fragments = pre_fix_join

    # EXACTLY the argv the NEW colour was measured with.
    sys.argv = ["sotto_worker.py", "--selftest", "--audio", wav,
                "--threads", str(args.threads)]

    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        real = sys.stdout
        sys.stdout = fh
        try:
            rc = W.main()
        finally:
            sys.stdout = real
    print(f"wrote {out} rc={rc} mode={args.mode} join_fragments="
          f"{'REVERTED' if args.mode == 'before' else 'on-disk'}", file=sys.stderr)
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
