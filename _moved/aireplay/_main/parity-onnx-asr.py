#!/usr/bin/env python
"""parity-onnx-asr.py -- diff an onnx-asr transcript against the sibling project's Redux transcript.

Read-only on H:\\sotto. Prints, for each claim, the instrument's number:
  * whitespace-normalised exact equality (the hardest, cheapest verdict)
  * SequenceMatcher ratio on characters
  * the word-level differences (what actually changed), first 40
  * python `repr` of every differing char run, so an invisible difference (hyphen,
    non-breaking space, combining accent) cannot hide behind a terminal's rendering

Usage:
  py -3 parity-onnx-asr.py --ref REF.txt --hyp HYP.txt --label NAME
  py -3 parity-onnx-asr.py --ref-jsonl SIBLING.stdout.txt --window 900 2100 --hyp HYP.txt --label NAME
"""

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def read_text_any(p: Path) -> str:
    """redux-ptbr.txt is NOT utf-8 (0xE1 at offset 135) -- it is cp1252. Try, then fall back."""
    raw = p.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"parity: cannot decode {p}")


def load_ref_plain(p: Path) -> str:
    """The sibling's redux-*.txt: header lines then the transcript."""
    lines = [ln for ln in read_text_any(p).splitlines() if ln.strip()]
    return lines[-1]


def load_ref_jsonl(p: Path, start: float, end: float) -> str:
    caps = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("type") == "caption" and d["start"] >= start and d["end"] <= end:
            caps.append(d["text"].strip())
    return " ".join(caps)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="")
    ap.add_argument("--ref-jsonl", default="")
    ap.add_argument("--window", nargs=2, type=float, default=[0.0, 0.0])
    ap.add_argument("--hyp", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--max-diff", type=int, default=40)
    args = ap.parse_args()

    if args.ref_jsonl:
        ref = load_ref_jsonl(Path(args.ref_jsonl), args.window[0], args.window[1])
        ref_src = f"{args.ref_jsonl} window=[{args.window[0]},{args.window[1]}]"
    else:
        ref = load_ref_plain(Path(args.ref))
        ref_src = args.ref
    hyp = Path(args.hyp).read_text(encoding="utf-8")

    r, h = norm(ref), norm(hyp)
    print(f"=== PARITY {args.label} ===")
    print(f"ref   : {ref_src}")
    print(f"hyp   : {args.hyp}")
    print(f"chars ref/hyp        : {len(ref)} / {len(hyp)}")
    print(f"chars norm ref/hyp   : {len(r)} / {len(h)}")
    print(f"EXACT (norm)         : {r == h}")
    print(f"SequenceMatcher ratio: {difflib.SequenceMatcher(None, r, h).ratio():.6f}")

    rw, hw = r.split(), h.split()
    sm = difflib.SequenceMatcher(None, rw, hw)
    print(f"words ref/hyp        : {len(rw)} / {len(hw)}   identical-word ratio: {sm.ratio():.6f}")
    diffs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            diffs.append((tag, rw[i1:i2], hw[j1:j2]))
    print(f"word diff blocks     : {len(diffs)}")
    for tag, a, b in diffs[: args.max_diff]:
        print(f"  {tag:8s} ref={' '.join(a)!r}  hyp={' '.join(b)!r}")

    char_diffs = [
        (tag, r[i1:i2], h[j1:j2])
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, r, h).get_opcodes()
        if tag != "equal"
    ]
    print(f"char diff blocks     : {len(char_diffs)}")
    for tag, a, b in char_diffs[: args.max_diff]:
        print(f"  {tag:8s} ref={a!r}  hyp={b!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
