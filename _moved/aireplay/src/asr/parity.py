#!/usr/bin/env python
"""Parity harness: does the int8 ONNX export reproduce the transcripts we already trust?

`specs/02-asr.md` section 6. Two KINDS of oracle, and they must never be confused:

  ternary    -- a DIFFERENT engine's output (the sibling's Redux ternary), read read-only
                from H:\\sotto. This is the independent evidence.
  regression -- the SAME engine's measured text on the registered slice, byte-identical in
                all 8 arms of the thread sweep (docs/research/11-onnx-threads.md:45). This is
                a lock against silent drift, NOT independent evidence.

Registered arms (`--arm`):
  en-8s       src-en-8s.wav  vs _main/redux-en.txt        TERNARY   expect EXACT   (05-onnx-asr.md:101)
  pt-15s      src-pt-15s.wav vs _main/redux-ptbr.txt      TERNARY   expect 0.993711, 1 char (05:102)
  long        plain-3600s.wav [900,1020) silence          REGRESSION expect EXACT  (11:45)
  long-fixed  the same slice on a FIXED 10 s grid         CONTROL   expect RED, ratio 0.229 (05:105)

`--expect red` inverts the verdict: the arm is SUPPOSED to fail, and the harness reports
`RED-as-expected` -- that is how the control proves the instrument can say no.

Exit code: 0 = every arm met its expectation · 1 = at least one did not.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr.constants import (  # noqa: E402
    CONTROL_SEGMENT_MODE,
    DEFAULT_SEGMENT_MODE,
    FIXED_GRID_RATIO,
    FIXED_GRID_S,
    INTRA_OP_NUM_THREADS,
    INTER_OP_NUM_THREADS,
    PARITY_EN,
    PARITY_LONG,
    PARITY_PT,
)
from asr.runner import TranscribeConfig, transcribe  # noqa: E402

__all__ = ["compare_texts", "read_text_any", "oracle_text", "ARMS", "main"]

ENCODINGS = ("utf-8", "cp1252", "latin-1")


def read_text_any(p: Path) -> tuple[str, str]:
    """redux-ptbr.txt is cp1252, not UTF-8 (0xE1 at offset 135, 05-onnx-asr.md:110)."""
    raw = Path(p).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"parity: cannot decode {p}")


def oracle_text(p: Path) -> tuple[str, str]:
    """The sibling's redux-*.txt carry two header lines; the transcript is the LAST non-empty."""
    text, enc = read_text_any(p)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise SystemExit(f"parity: oracle file is empty: {p}")
    return lines[-1].strip(), enc


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def compare_texts(ref: str, hyp: str, max_diffs: int = 12) -> dict:
    r, h = normalise(ref), normalise(hyp)
    sm = difflib.SequenceMatcher(None, r, h)
    char_blocks = [(tag, r[i1:i2], h[j1:j2]) for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != "equal"]
    rw, hw = r.split(), h.split()
    wsm = difflib.SequenceMatcher(None, rw, hw)
    word_blocks = [(tag, " ".join(rw[i1:i2]), " ".join(hw[j1:j2])) for tag, i1, i2, j1, j2 in wsm.get_opcodes() if tag != "equal"]
    return {
        "exact": r == h,
        "ratio": round(sm.ratio(), 6),
        "chars_ref": len(r),
        "chars_hyp": len(h),
        "char_diff_blocks": len(char_blocks),
        "word_diff_blocks": len(word_blocks),
        "word_ratio": round(wsm.ratio(), 6),
        "sha256_ref": sha256_text(r),
        "sha256_hyp": sha256_text(h),
        "char_diffs": [{"op": t, "ref": a, "hyp": b} for t, a, b in char_blocks[:max_diffs]],
        "word_diffs": [{"op": t, "ref": a, "hyp": b} for t, a, b in word_blocks[:max_diffs]],
    }


# ---------------------------------------------------------------------------------------
# Registered arms
# ---------------------------------------------------------------------------------------

def _arm_from(reg: dict, mode: str, expect: str, chunk_s: float = FIXED_GRID_S) -> dict:
    return {
        "kind": reg.get("kind", "regression"),
        "wav": Path(reg["wav"]),
        "oracle": Path(reg["oracle"]),
        "offset_s": float(reg.get("offset_s", 0.0)),
        "max_s": float(reg.get("max_s", 0.0)),
        "segment_mode": mode,
        "chunk_s": chunk_s,
        "ratio_min": reg.get("ratio_min", 1.0),
        "max_char_diff_blocks": reg.get("max_char_diff_blocks", 0),
        "expect": expect,
    }


ARMS: dict[str, dict] = {
    "en-8s": _arm_from(PARITY_EN, DEFAULT_SEGMENT_MODE, "pass"),
    "pt-15s": _arm_from(PARITY_PT, DEFAULT_SEGMENT_MODE, "pass"),
    "long": _arm_from(PARITY_LONG, DEFAULT_SEGMENT_MODE, "pass"),
    "long-fixed": _arm_from(PARITY_LONG, CONTROL_SEGMENT_MODE, "red"),
}


def judge(cmp: dict, arm: dict) -> tuple[bool, str]:
    """True = the measurement met the arm's threshold (before --expect is applied)."""
    ok_ratio = cmp["ratio"] >= arm["ratio_min"]
    ok_diffs = cmp["char_diff_blocks"] <= arm["max_char_diff_blocks"]
    if arm["expect"] == "red":
        # the control must NOT meet the threshold -- and the ratio must collapse, not crawl
        collapsed = cmp["ratio"] <= 0.50
        return (not ok_ratio) and collapsed, (
            f"ratio {cmp['ratio']} <= 0.50 (measured trap {FIXED_GRID_RATIO})" if collapsed
            else f"ratio {cmp['ratio']} did NOT collapse (expected <= 0.50)"
        )
    return ok_ratio and ok_diffs, f"ratio {cmp['ratio']} >= {arm['ratio_min']}, char-diff blocks {cmp['char_diff_blocks']} <= {arm['max_char_diff_blocks']}"


def run_arm(name: str, arm: dict, threads: int = INTRA_OP_NUM_THREADS, hyp_file: Path | None = None) -> dict:
    ref, enc = oracle_text(arm["oracle"])
    info: dict = {"arm": name, "kind": arm["kind"], "expect": arm["expect"],
                  "wav": str(arm["wav"]), "oracle": str(arm["oracle"]), "oracle_encoding": enc,
                  "segment_mode": arm["segment_mode"], "threads_intra": threads,
                  "offset_s": arm["offset_s"], "max_s": arm["max_s"],
                  "oracle_chars": len(normalise(ref))}

    if hyp_file is not None:
        hyp = Path(hyp_file).read_text(encoding="utf-8")
        info["hyp_source"] = str(hyp_file)
    else:
        cfg = TranscribeConfig(
            wav=arm["wav"], offset_s=arm["offset_s"], max_s=arm["max_s"],
            segment_mode=arm["segment_mode"], fixed_chunk_s=arm["chunk_s"],
            intra_op_num_threads=threads, inter_op_num_threads=INTER_OP_NUM_THREADS,
            level=False, label=name,
        )
        done = transcribe(cfg)
        hyp = done["text"]
        info["hyp_source"] = "asr.transcribe"
        info["metrics"] = {k: done[k] for k in (
            "audio_s", "audio_processed_s", "n_segments", "seg_median_s", "seg_max_s", "load_s",
            "infer_s", "rtfx_infer", "rtfx_steady", "rtfx_slice", "rss_after_load_mb",
            "rss_peak_mb", "rss_peak_wset_mb", "cpu_median_pct", "cpu_max_pct")}
        info["segments"] = [(s["start"], s["end"]) for s in done["segments"]]
        info["threads"] = done["threads"]

    cmp = compare_texts(ref, hyp)
    met, why = judge(cmp, arm)
    passed = met
    info.update({"comparison": cmp, "met_threshold": met, "why": why,
                 "verdict": ("PASS" if passed else "FAIL"),
                 "display": ("GREEN" if (passed and arm["expect"] == "pass") else
                             ("RED-as-expected" if (passed and arm["expect"] == "red") else "RED"))})
    return info


def print_report(info: dict) -> None:
    c = info["comparison"]
    print(f"=== PARITY {info['arm']} [{info['kind']}] expect={info['expect']} -> {info['display']} ===")
    print(f"  wav          : {info['wav']}  ({info['segment_mode']}, offset={info['offset_s']}, max={info['max_s']})")
    print(f"  oracle       : {info['oracle']}  encoding={info['oracle_encoding']}")
    print(f"  threads      : intra={info['threads_intra']} inter={INTER_OP_NUM_THREADS}")
    if "metrics" in info:
        m = info["metrics"]
        print(f"  measured     : segs={m['n_segments']} med={m['seg_median_s']}s max={m['seg_max_s']}s "
              f"infer={m['infer_s']}s rtfx(steady/infer/slice)={m['rtfx_steady']}/{m['rtfx_infer']}/{m['rtfx_slice']} "
              f"rss(load/peak/wset)={m['rss_after_load_mb']}/{m['rss_peak_mb']}/{m['rss_peak_wset_mb']}MB "
              f"cpu(med/max)={m['cpu_median_pct']}/{m['cpu_max_pct']}%")
    print(f"  chars        : ref={c['chars_ref']} hyp={c['chars_hyp']}")
    print(f"  EXACT        : {c['exact']}   ratio={c['ratio']}   word-ratio={c['word_ratio']}")
    print(f"  diff blocks  : char={c['char_diff_blocks']} word={c['word_diff_blocks']}")
    print(f"  sha256 hyp   : {c['sha256_hyp']}")
    for d in c["char_diffs"]:
        print(f"    char {d['op']:8s} ref={d['ref']!r} hyp={d['hyp']!r}")
    print(f"  why          : {info['why']}")
    print(f"  VERDICT      : {info['verdict']} ({info['display']})")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asr.parity", description=__doc__.splitlines()[0])
    p.add_argument("--arm", action="append", default=[], choices=sorted(ARMS),
                   help="registered arm; repeatable. Default: all four.")
    p.add_argument("--wav", default="")
    p.add_argument("--oracle", default="")
    p.add_argument("--kind", default="ternary", choices=["ternary", "regression"])
    p.add_argument("--offset-s", type=float, default=0.0)
    p.add_argument("--max-s", type=float, default=0.0)
    p.add_argument("--segment-mode", default=DEFAULT_SEGMENT_MODE,
                   choices=[DEFAULT_SEGMENT_MODE, CONTROL_SEGMENT_MODE])
    p.add_argument("--chunk-s", type=float, default=FIXED_GRID_S)
    p.add_argument("--threads", type=int, default=INTRA_OP_NUM_THREADS)
    p.add_argument("--expect", default="pass", choices=["pass", "red"])
    p.add_argument("--hyp", default="", help="compare an existing transcript instead of running the model")
    p.add_argument("--ratio-min", type=float, default=1.0)
    p.add_argument("--max-char-diff-blocks", type=int, default=0)
    p.add_argument("--json", default="")
    args = p.parse_args(argv)

    if args.wav and args.oracle:
        arm = {
            "kind": args.kind, "wav": Path(args.wav), "oracle": Path(args.oracle),
            "offset_s": args.offset_s, "max_s": args.max_s, "segment_mode": args.segment_mode,
            "chunk_s": args.chunk_s, "ratio_min": args.ratio_min,
            "max_char_diff_blocks": args.max_char_diff_blocks, "expect": args.expect,
        }
        names = [Path(args.wav).stem]
        arms = {names[0]: arm}
    else:
        names = args.arm or ["en-8s", "pt-15s", "long", "long-fixed"]
        arms = {n: ARMS[n] for n in names}

    results = []
    for name in names:
        info = run_arm(name, arms[name], threads=args.threads,
                       hyp_file=Path(args.hyp) if args.hyp else None)
        print_report(info)
        results.append(info)

    bad = [r for r in results if r["verdict"] != "PASS"]
    controls = [r for r in results if r["expect"] == "red"]
    print()
    print(f"ARMS {len(results)}  pass={len(results) - len(bad)}  fail={len(bad)}  "
          f"controls={len(controls)} ({sum(1 for c in controls if c['display'] == 'RED-as-expected')} red-as-expected)")
    for r in bad:
        print(f"  FAILED: {r['arm']} -- {r['why']}")
    print(f"PARITY-VERDICT: {'GREEN' if not bad else 'RED'}")
    if args.json:
        Path(args.json).write_text(json.dumps({"arms": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
