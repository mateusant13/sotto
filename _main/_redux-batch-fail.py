#!/usr/bin/env python3
"""A runner that ALWAYS FAILS — the light path's failure arm, on purpose.

WHY THIS FILE EXISTS. `worker/redux_batch.py` is the real engine and it works, so
its failure branch is unreachable from a passing test. That branch is exactly
where a silent failure would hide: the runner is a separate process whose stderr
the worker CAPTURES, and a captured stderr nobody logs turns "the batch engine
refused its input" into `lines=0` — indistinguishable from "this audio had no
speech". This stub exits non-zero with a distinctive stderr tail so the arm can
assert that the worker (a) still reports the pass, (b) counts it as a failure, and
(c) prints the tail it would otherwise have thrown away.

It emits NOTHING on stdout, which is also true of a real runner that dies before
its first line: the arm therefore covers the empty-batch path too.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser(prog="redux-batch-fail")
    ap.add_argument("--wav", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    sys.stderr.write(
        "redux-batch-fail: DELIBERATE FAILURE (the failure arm of "
        f"_main/_redux-visibility-probe.py); wav={args.wav}\n")
    # 4, not 1: the arm distinguishes this deliberate rc from an interpreter
    # crash, and a gate asserting `rc != 0` would not notice a page of Python
    # traceback replacing a clean refusal.
    return 4


if __name__ == "__main__":
    sys.exit(main())
