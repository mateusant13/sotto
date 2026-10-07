"""WER/CER for the DECODE ARMS, against the same reference as the audit.

WHY: `_main/sotto-vs-ref-decode-arms.py` emits tokens/words/empty-chunks per arm
but no cost against the reference, and `_main/sotto-vs-ref-compare.py` reads a
per-chunk probe JSONL, not an arms JSON. This closes the loop with the SAME
normalisation the audit used — it IMPORTS `norm_words`/`norm_chars` from
`sotto-vs-ref-compare.py` rather than re-implementing them, so the two cannot
drift.

Every number carries its POPULATION (reference words/chars) and its WINDOW
(the audio the arm consumed), because a ratio without both is not a number.

Usage:
  python _main/sotto-vs-ref-arms-compare.py --ref G:/sotto-ref/reference-en.txt \
         --arms G:/sotto-ref/arms-full-cura.json --out G:/sotto-ref/arms-compare-cura.json
"""

import argparse
import difflib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "sotto_vs_ref_compare", os.path.join(HERE, "sotto-vs-ref-compare.py"))
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def score(ref_words, hyp_words, ref_chars, hyp_chars):
    sm = difflib.SequenceMatcher(None, ref_words, hyp_words, autojunk=False)
    sub = dele = ins = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        la, lb = i2 - i1, j2 - j1
        if tag == "replace":
            m = min(la, lb)
            sub += m
            dele += la - m
            ins += lb - m
        elif tag == "delete":
            dele += la
        elif tag == "insert":
            ins += lb
    smc = difflib.SequenceMatcher(None, ref_chars, hyp_chars, autojunk=False)
    cer_edits = sum((i2 - i1) + (j2 - j1) - min(i2 - i1, j2 - j1)
                    for tag, i1, i2, j1, j2 in smc.get_opcodes() if tag != "equal")
    return {
        "substitutions": sub,
        "deletions_omitted": dele,
        "insertions_extra": ins,
        "wer": (sub + dele + ins) / len(ref_words) if ref_words else None,
        "cer": cer_edits / len(ref_chars) if ref_chars else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--arms", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jsonl", action="append", default=[],
                    help="LABEL:PATH of a worker --selftest JSONL whose "
                         "selftest-done.text is scored as an extra row — this is how "
                         "the SHIPPED worker is shown to agree with an arm")
    args = ap.parse_args()

    ref_text = open(args.ref, encoding="utf-8").read()
    ref_words = C.norm_words(ref_text)
    ref_chars = C.norm_chars(ref_text)
    data = json.load(open(args.arms, encoding="utf-8"))

    rows = []
    for arm in data["arms"]:
        hyp_words = C.norm_words(arm["text"])
        hyp_chars = C.norm_chars(arm["text"])
        s = score(ref_words, hyp_words, ref_chars, hyp_chars)
        row = {
            "arm": arm["arm"],
            "tokens": arm["tokens"],
            "words": arm["words"],
            "words_share_of_ref": arm["words"] / len(ref_words),
            "empty_chunks": arm["empty_chunks"],
            "chunks": arm["chunks"],
            "empty_share": arm["empty_chunks"] / arm["chunks"],
            "blank_frac": arm["blank_frac"],
            "wall_s": arm["wall_s"],
            "audio_s": arm["audio_s"],
            "substitutions": s["substitutions"],
            "omissions": s["deletions_omitted"],
            "insertions": s["insertions_extra"],
            "wer": s["wer"],
            "cer": s["cer"],
            "text_chars": len(arm["text"]),
            "text_sha256_prefix": __import__("hashlib").sha256(
                arm["text"].encode("utf-8")).hexdigest()[:16],
        }
        rows.append(row)
        print(f"arm {row['arm']}: tokens={row['tokens']} words={row['words']} "
              f"({row['words_share_of_ref'] * 100:.1f}% of ref) "
              f"omissions={row['omissions']} empty={row['empty_chunks']}/{row['chunks']} "
              f"({row['empty_share'] * 100:.1f}%) "
              f"WER={row['wer']:.4f} CER={row['cer']:.4f} wall={row['wall_s']}s")

    for spec in args.jsonl:
        label, path = spec.split(":", 1)
        done = None
        for line in open(path, encoding="utf-8"):
            r = json.loads(line)
            if r.get("state") == "selftest-done":
                done = r
        if done is None:
            print(f"jsonl {label}: NO selftest-done row in {path}")
            sys.exit(2)
        hyp_words = C.norm_words(done["text"])
        hyp_chars = C.norm_chars(done["text"])
        s = score(ref_words, hyp_words, ref_chars, hyp_chars)
        row = {
            "arm": label,
            "tokens": done["tokens"],
            "words": len(hyp_words),
            "words_share_of_ref": len(hyp_words) / len(ref_words),
            "empty_chunks": done["empty_chunks"],
            "chunks": None,
            "empty_share": None,
            "blank_frac": done["blank_frac"],
            "wall_s": done.get("infer_wall_s"),
            "audio_s": done["audio_s"],
            "substitutions": s["substitutions"],
            "omissions": s["deletions_omitted"],
            "insertions": s["insertions_extra"],
            "wer": s["wer"],
            "cer": s["cer"],
            "text_chars": len(done["text"]),
            "text_sha256_prefix": __import__("hashlib").sha256(
                done["text"].encode("utf-8")).hexdigest()[:16],
            "source_jsonl": path,
        }
        rows.append(row)
        print(f"{label}: tokens={row['tokens']} words={row['words']} "
              f"({row['words_share_of_ref'] * 100:.1f}% of ref) "
              f"omissions={row['omissions']} empty={row['empty_chunks']} "
              f"WER={row['wer']:.4f} CER={row['cer']:.4f}")

    out = {
        "reference": {
            "path": args.ref,
            "words": len(ref_words),
            "normalised_chars": len(ref_chars),
            "normalisation": "the SAME functions the audit used (imported from "
                             "_main/sotto-vs-ref-compare.py): casefold, fold accents, "
                             "curly->straight apostrophe, drop punctuation, split on whitespace",
        },
        "window_s": data["arms"][0]["audio_s"] if data["arms"] else None,
        "population_note": "WER population = reference words; CER population = reference "
                           "normalised characters; both over the whole video window",
        "caveat": "the reference is itself an ASR transcript: this is a RELATIVE number "
                  "between two ASR systems, not an accuracy against ground truth",
        "arms": rows,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"out: {args.out}  (population {len(ref_words)} ref words, window 0-{out['window_s']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
