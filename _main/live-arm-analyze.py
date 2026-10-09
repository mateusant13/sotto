"""Analyse one worker JSONL arm: the meter cadence/values AND the caption strings.

Used for BOTH colours of the split-word A/B (live path) and for the peak
measurement the panel animation needs.

Usage:
  py -3 _main/live-arm-analyze.py --jsonl _main/sweep90-live-new.jsonl
  py -3 _main/live-arm-analyze.py --jsonl _main/sweep90-live-before.jsonl --label BEFORE
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys


def load(path):
    rows = []
    bad = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    return rows, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    label = args.label or os.path.basename(args.jsonl)

    rows, bad = load(args.jsonl)
    kinds = {}
    for r in rows:
        kinds[r.get("type")] = kinds.get(r.get("type"), 0) + 1

    print(f"########## {label}  ({os.path.basename(args.jsonl)}) ##########")
    print(f"rows={len(rows)} unparseable={bad}")
    print("kinds:", dict(sorted(kinds.items(), key=lambda kv: -kv[1])))
    print()

    # ── the meter ───────────────────────────────────────────────────────────
    meters = [r for r in rows if r.get("type") == "meter"]
    if meters:
        print(f"===== METER  n={len(meters)} =====")
        print("first object :", json.dumps(meters[0], ensure_ascii=False))
        print("second object:", json.dumps(meters[1], ensure_ascii=False) if len(meters) > 1 else "-")
        print("last object  :", json.dumps(meters[-1], ensure_ascii=False))
        print("keys         :", sorted(meters[0].keys()))

        peaks = [m.get("peak") for m in meters if isinstance(m.get("peak"), (int, float))]
        blocks = [m.get("blocks") for m in meters if isinstance(m.get("blocks"), (int, float))]
        if peaks:
            distinct = len(set(peaks))
            up = down = eq = 0
            for a, b in zip(peaks, peaks[1:]):
                if b > a:
                    up += 1
                elif b < a:
                    down += 1
                else:
                    eq += 1
            print(f"peak  n={len(peaks)} distinct={distinct} "
                  f"min={min(peaks)} max={max(peaks)} mean={statistics.mean(peaks):.6f} "
                  f"median={statistics.median(peaks):.6f}")
            print(f"peak  transitions: up={up} down={down} equal={eq} (of {len(peaks)-1})")
            print(f"peak  ==0 count={sum(1 for p in peaks if p == 0.0)}")
            buckets = [(0.0, 0.05), (0.05, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.5), (0.5, 1.01)]
            for lo, hi in buckets:
                c = sum(1 for p in peaks if lo <= p < hi)
                print(f"   {lo:.2f} <= peak < {hi:.2f} : {c}")
            print("first 12 peaks:", [round(p, 6) for p in peaks[:12]])
            print("last 12 peaks :", [round(p, 6) for p in peaks[-12:]])
        if blocks:
            print(f"blocks n={len(blocks)} distinct={len(set(blocks))} "
                  f"min={min(blocks)} max={max(blocks)} "
                  f"values={sorted(set(blocks))[:12]}")
        # the meter object carries no timestamp; its cadence is pinned by the
        # tap's block count, so state that instead of inventing a dt.
        if blocks:
            print(f"cadence: meter events per delivered block = {len(meters)}/{sum(blocks)}"
                  if sum(blocks) else "")
        print()
    else:
        print("===== METER  n=0  (this arm emitted NO meter object) =====\n")

    # ── captions ────────────────────────────────────────────────────────────
    caps = [r for r in rows if r.get("type") == "caption"]
    if caps:
        print(f"===== CAPTIONS  n={len(caps)} =====")
        print("first object keys:", sorted(caps[0].keys()))
        print("first object     :", json.dumps(caps[0], ensure_ascii=False)[:400])
        finals = [c for c in caps if c.get("final") is True]
        print(f"final:true = {len(finals)}   final:false/absent = {len(caps)-len(finals)}")
        print("--- final:true lines, in order (text verbatim, repr) ---")
        for i, c in enumerate(finals):
            print(f"  [{i:3d}] start={c.get('start')} end={c.get('end')} "
                  f"text={c.get('text')!r}")
        print("--- the JOINED final text, verbatim ---")
        joined = " ".join(c.get("text", "") for c in finals)
        print(repr(joined))
        print("--- same, spaces removed (the fix must not change this) ---")
        print(repr(joined.replace(" ", "")))
        print()
        # split-word smells: a 1-3 char token that is not a real word, or a
        # space inside a word. Report candidates with their line index.
        import re
        print("--- split-word CANDIDATES (<=3-char fragment or glued pair) ---")
        for i, c in enumerate(finals):
            t = c.get("text", "")
            toks = t.split()
            for j, tok in enumerate(toks):
                core = tok.strip(".,!?;:()")
                if 0 < len(core) <= 3 and core.isalpha() and core.lower() not in (
                        "de", "da", "do", "em", "um", "os", "as", "no", "na", "se", "ou",
                        "e", "a", "o", "que", "com", "por", "pra", "pro", "dos", "das",
                        "ao", "aos", "eu", "tu", "ele", "ela", "nos", "vos", "mas", "ja",
                        "so", "the", "and", "you", "for", "are", "was", "his", "her", "its",
                        "our", "not", "but", "all", "can", "had", "has", "one", "out", "who",
                        "any", "how", "now", "new", "get", "use", "way", "may", "day", "too",
                        "see", "him", "two", "its", "let", "put", "say", "she", "try", "why",
                        "bit", "far", "own", "off", "old", "end", "few", "yet", "yes", "top"):
                    print(f"  line[{i:3d}] tok[{j:3d}] {tok!r}   in: {t!r}")
        print()
    else:
        print("===== CAPTIONS  n=0 =====\n")

    # ── statuses / done ─────────────────────────────────────────────────────
    print("===== STATUSES =====")
    for r in rows:
        if r.get("type") == "status":
            keep = {k: v for k, v in r.items() if k in
                    ("state", "verdict", "device", "api", "reason", "rate", "detail", "peak")}
            print("  ", json.dumps(keep, ensure_ascii=False))
    print()
    print("===== done / selftest =====")
    for r in rows:
        if r.get("type") in ("done", "selftest-done"):
            print("  ", json.dumps(r, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
