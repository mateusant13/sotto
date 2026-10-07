#!/usr/bin/env python
"""parity-segments.py -- per-SEGMENT parity, which the repetition in plain-3600s.wav defeats
at whole-text level (the corpus loops the same 4 sentences, so difflib aligns runs of the
same sentence arbitrarily and reports a meaningless 0.49 word ratio).

Pairs each onnx-asr segment with the sibling Redux caption(s) covering the same time span
and prints, per pair, whether the whitespace-normalised text is IDENTICAL and, when it is
not, the exact character difference.

  py -3 parity-segments.py --mine run.json --sibling SIBLING.stdout.txt --slack 1.5
"""

import argparse
import json
import re
from pathlib import Path


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mine", required=True, help="probe-onnx-asr-split.py JSON (has .segments)")
    ap.add_argument("--sibling", required=True, help="redux_batch stdout JSONL with captions")
    ap.add_argument("--slack", type=float, default=1.5)
    args = ap.parse_args()

    mine = json.loads(Path(args.mine).read_text(encoding="utf-8"))
    caps = []
    for line in Path(args.sibling).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            d = json.loads(line)
            if d.get("type") == "caption":
                caps.append(d)

    same = 0
    diff = 0
    empty = 0
    print(f"{'mine [start,end)':>26} | {'chars':>5} | verdict")
    for seg in mine["segments"]:
        a, b = seg["start"], seg["end"]
        txt = norm(seg["text"])
        ref = norm(" ".join(c["text"] for c in caps if c["start"] >= a - args.slack and c["end"] <= b + args.slack))
        if not txt and not ref:
            empty += 1
            print(f"{a:12.2f}-{b:7.2f}{'':5} | {0:5d} | both-empty (silence)")
            continue
        if txt == ref:
            same += 1
            print(f"{a:12.2f}-{b:7.2f}{'':5} | {len(txt):5d} | IDENTICAL")
        else:
            diff += 1
            print(f"{a:12.2f}-{b:7.2f}{'':5} | {len(txt):5d} | DIFFERS  mine={txt[:80]!r}")
            print(f"{'':26} | {'':5} |          sib ={ref[:80]!r}")
    print(f"\nSEGMENT PARITY: identical={same} differs={diff} both-empty={empty} of {len(mine['segments'])}")
    print(f"mode={mine['mode']} n_segments={mine['n_segments']} rtfx={mine['rtfx_infer']} peak_wset={mine['rss_peak_wset_mb']}MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
