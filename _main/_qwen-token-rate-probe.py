#!/usr/bin/env python3
"""_qwen-token-rate-probe.py -- MEASURE the transcript token rate from real files.

The hourly Qwen feature needs a MIN and a MAX token budget, and both must come
from measured speech, not a guess. The repo's own archive is the corpus:
`history/<YYYY-MM-DD>/<HH>.md`, one file per hour, one line per CLOSED worker
line (`route=final`).

What this measures:
  * lines per hour, lines per minute of wall-clock
  * characters per line, and the character->token ratio for pt/en
  * RAW tokens vs DEDUPLICATED tokens -- the transcript is heavily redundant
    (the worker's own second pass re-emits cumulative hypotheses), so the
    number of tokens an LLM would actually have to read is much smaller than
    the byte count suggests
  * the resulting "minutes of speech -> tokens" ratio the plan quotes

Token counting: exact when `transformers` + a real tokenizer is available;
otherwise a documented character heuristic (CJK/Devanagari-aware) and BOTH
numbers are printed so the plan can say which one it quoted.

Read-only. No downloads, no installs, no window, no audio device.
Run: cmd /c "python _main\_qwen-token-rate-probe.py <out.md>"
"""

from __future__ import annotations

import glob
import os
import re
import statistics
import sys
from datetime import datetime

TAG_RE = re.compile(r"<!--.*?-->")
LINE_RE = re.compile(r"^-\s*\[(\d{1,2}):(\d{2}):(\d{2})\]\s*(.*?)\s*$")


def char_tokens(text: str) -> int:
    """Character heuristic, script-aware.

    English/Portuguese ~ 4.0 chars per token for Qwen's BPE.
    Devanagari/CJK are much denser per character (measured on this corpus: the
    ASR sometimes emits Hindi/Japanese for English audio, and those lines are
    token-heavy), so count those characters at ~1 token each rather than /4.
    """
    dense = 0
    for ch in text:
        o = ord(ch)
        if 0x0900 <= o <= 0x097F:      # Devanagari
            dense += 1
        elif 0x3000 <= o <= 0x9FFF:    # CJK / kana
            dense += 1
        elif 0xAC00 <= o <= 0xD7AF:    # Hangul
            dense += 1
    latin_chars = len(text) - dense
    return dense + max(0, round(latin_chars / 4.0))


def parse_file(path: str):
    """Return (entries, first_dt, last_dt) where entries are (dt, text)."""
    entries = []
    date = os.path.basename(os.path.dirname(path))
    try:
        yr, mo, dy = (int(x) for x in date.split("-"))
    except ValueError:
        return [], None, None

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if not line.startswith("-"):
                continue
            body = TAG_RE.sub("", line).strip()
            hit = LINE_RE.match(body)
            if not hit:
                continue
            hh, mm, ss = int(hit.group(1)), int(hit.group(2)), int(hit.group(3))
            text = hit.group(4)
            if not text:
                continue
            try:
                dt = datetime(yr, mo, dy, hh, mm, ss)
            except ValueError:
                continue
            entries.append((dt, text))
    if not entries:
        return [], None, None
    entries.sort(key=lambda e: e[0])
    return entries, entries[0][0], entries[-1][0]


def main() -> int:
    out_path = sys.argv[1] if len(sys.argv) > 1 else None

    class Tee:
        def __init__(self, p):
            self.fh = open(p, "w", encoding="utf-8") if p else None
            self._o = sys.__stdout__

        def write(self, s):
            self._o.write(s)
            if self.fh:
                self.fh.write(s); self.fh.flush()
            return len(s)

        def flush(self):
            pass

    tee = Tee(out_path)
    sys.stdout = tee

    # Try for an exact tokenizer, STRICTLY from the local HF cache. The hard rule
    # for this lane is "no downloads of model weights": HF_HUB_OFFLINE=1 makes a
    # cache miss fail fast instead of silently pulling a tokenizer off the Hub.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    tok = None
    try:
        from transformers import AutoTokenizer  # type: ignore
        tok_name = None
        for cand in ("Qwen/Qwen3.5-4B", "Qwen/Qwen3-4B", "Qwen/Qwen2.5-4B",
                     "Qwen/Qwen3-0.6B"):
            try:
                tok = AutoTokenizer.from_pretrained(
                    cand, trust_remote_code=True, local_files_only=True)
                tok_name = cand
                break
            except Exception:
                continue
        if tok is not None:
            print(f"TOKENIZER: EXACT -- {tok_name} (local cache, offline mode)")
        else:
            print("TOKENIZER: heuristic -- no Qwen tokenizer in the local HF cache")
            print("           (no download attempted: HF_HUB_OFFLINE=1)")
    except Exception as exc:  # noqa: BLE001
        print(f"TOKENIZER: heuristic (transformers unavailable: {type(exc).__name__})")

    def count(text: str) -> int:
        if tok is not None:
            try:
                return len(tok.encode(text, add_special_tokens=False))
            except Exception:
                pass
        return char_tokens(text)

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "history")
    files = sorted(glob.glob(os.path.join(root, "*", "*.md")))
    print(f"CORPUS: {len(files)} transcript file(s) under {root}")
    if not files:
        print("\nNO CORPUS -- cannot measure. Report this as UNKNOWN, do not estimate.")
        return 1

    print()
    print(f"{'file':<28} {'lines':>7} {'span':>7} {'ln/min':>7} "
          f"{'ch/line':>8} {'raw tok':>9} {'dedup tok':>10} {'dedup%':>7}")
    print("-" * 100)

    all_ln_per_min: list[float] = []
    all_chars_per_line: list[float] = []
    all_dedup_ratio: list[float] = []
    all_tok_per_min: list[float] = []
    total_lines = total_raw = total_dedup = 0

    for path in files:
        entries, first, last = parse_file(path)
        if not entries:
            continue
        span_s = max(0.0, (last - first).total_seconds())
        # A 1-line file has no measured rate; a 0 span means one timestamp cluster.
        span_min = span_s / 60.0
        ln_per_min = (len(entries) / span_min) if span_min > 0.5 else float("nan")

        texts = [t for _dt, t in entries]
        chars = [len(t) for t in texts]

        raw_tok = sum(count(t) for t in texts)

        # Deduplicate: the second pass re-emits the SAME hypothesis with a longer
        # tail. Keep a line only when it is not a near-duplicate of the previous
        # kept line, and count a kept line's NOVEL tail only.
        kept: list[str] = []
        dedup_tok = 0
        for t in texts:
            if kept and (t == kept[-1] or t.startswith(kept[-1][:max(12, len(kept[-1]) // 2)])):
                # cumulative re-emission: score only the novel suffix
                prev = kept[-1]
                novel = t[len(prev):] if t.startswith(prev) else t
                if len(novel.strip()) < 4:
                    continue
                dedup_tok += count(novel)
                kept[-1] = t
            else:
                dedup_tok += count(t)
                kept.append(t)

        ratio = dedup_tok / raw_tok if raw_tok else 1.0
        tok_per_min = (dedup_tok / span_min) if span_min > 0.5 else float("nan")

        if span_min > 0.5:
            all_ln_per_min.append(ln_per_min)
            all_tok_per_min.append(tok_per_min)
        all_chars_per_line.append(statistics.mean(chars))
        all_dedup_ratio.append(ratio)
        total_lines += len(entries)
        total_raw += raw_tok
        total_dedup += dedup_tok

        print(f"{os.path.basename(path):<28} {len(entries):>7} "
              f"{span_min:>6.1f}m {ln_per_min:>7.1f} {statistics.mean(chars):>8.1f} "
              f"{raw_tok:>9,} {dedup_tok:>10,} {ratio * 100:>6.1f}%")

    print("-" * 100)
    print(f"{'TOTAL':<28} {total_lines:>7} {'':>7} {'':>7} "
          f"{'':>8} {total_raw:>9,} {total_dedup:>10,} "
          f"{(total_dedup / total_raw * 100 if total_raw else 0):>6.1f}%")

    print()
    print("=== DERIVED RATES (the numbers the plan's arithmetic substitutes) ===")
    if all_ln_per_min:
        print(f"  lines per minute (mean, {len(all_ln_per_min)} file(s)) : "
              f"{statistics.mean(all_ln_per_min):.2f}")
        print(f"  lines per minute (median)                       : "
              f"{statistics.median(all_ln_per_min):.2f}")
        if len(all_ln_per_min) > 1:
            print(f"  lines per minute (min / max)                    : "
                  f"{min(all_ln_per_min):.2f} / {max(all_ln_per_min):.2f}")
    print(f"  seconds of speech per line (mean of ln/min)     : "
          f"{(60.0 / statistics.mean(all_ln_per_min)) if all_ln_per_min else float('nan'):.2f}")
    print(f"  characters per line (mean)                      : "
          f"{statistics.mean(all_chars_per_line):.1f}")
    print(f"  dedup/raw token ratio (mean)                    : "
          f"{statistics.mean(all_dedup_ratio) * 100:.1f}%")
    if all_tok_per_min:
        m = statistics.mean(all_tok_per_min)
        print(f"  DEDUP tokens per minute of transcript (mean)    : {m:.1f}")
        print(f"  DEDUP tokens per 60-minute hour                 : {m * 60:,.0f}")
        print(f"  DEDUP tokens per 40 minutes (4:40 manual case)  : {m * 40:,.0f}")
        print(f"  DEDUP tokens per 10 minutes                     : {m * 10:,.0f}")
    print(f"  RAW tokens per 60-minute hour (worst case)      : "
          f"{(total_raw / max(1, total_lines) * statistics.mean(all_ln_per_min) * 60) if all_ln_per_min else float('nan'):,.0f}")

    tee.fh and tee.fh.close()
    sys.stdout = tee._o
    return 0


if __name__ == "__main__":
    sys.exit(main())
