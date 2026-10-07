"""Reference-vs-Sotto comparison + omission census (lane SottoVsReferencia).

Inputs:
  --ref     the reference transcript as plain text (YouTube caption text)
  --probe   the per-chunk JSONL produced by `_main/sotto-vs-ref-probe.py`
  --out     a JSON file with every derived number

Every number this prints carries its POPULATION (how many items were compared)
and its WINDOW (the time span), because a ratio without both is not a number
this house accepts.

The alignment is word-level (difflib.SequenceMatcher, autojunk off). 'delete'
blocks are the OMISSIONS the owner asked about; each one is reported with its
index in the reference AND the Sotto chunk time at which the surrounding
hypothesis resumes -- derived, not measured by a clock, and labelled as such.
"""

import argparse
import difflib
import json
import re
import sys
import unicodedata

PUNCT = re.compile(r"[^\w']+", re.UNICODE)


def norm_words(text):
    """Lowercase, fold accents, drop punctuation, split on whitespace.

    Punctuation is dropped from BOTH sides identically, so a captioned
    '6.1' and a decoded '6.1' compare equal, and neither side is punished for
    the other's apostrophe style.
    """
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u2019", "'").replace("\u2018", "'")
    t = PUNCT.sub(" ", t)
    return [w for w in t.split() if w]


def norm_chars(text):
    return " ".join(norm_words(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--probe", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-omissions", type=int, default=30)
    args = ap.parse_args()

    ref_text = open(args.ref, encoding="utf-8").read()
    rows = [json.loads(l) for l in open(args.probe, encoding="utf-8") if l.strip()]
    summary = next(r for r in rows if r.get("kind") == "summary")
    chunks = [r for r in rows if r.get("kind") != "summary"]

    hyp_text = summary["text"]
    ref_w, hyp_w = norm_words(ref_text), norm_words(hyp_text)

    # hyp word index -> the chunk (and therefore the audio time) it came from
    hyp_chunk_time = []
    for c in chunks:
        for _ in norm_words(c["text"]):
            hyp_chunk_time.append((c["i"], c["t0"], c["t0"] + 0.56))

    sm = difflib.SequenceMatcher(None, ref_w, hyp_w, autojunk=False)
    ops = sm.get_opcodes()
    sub = dele = ins = 0
    omissions = []
    substitutions = []
    insertions = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            continue
        la, lb = i2 - i1, j2 - j1
        if tag == "replace":
            m = min(la, lb)
            sub += m
            dele += la - m
            ins += lb - m
            for k in range(m):
                substitutions.append(
                    {
                        "ref_index": i1 + k,
                        "ref": ref_w[i1 + k],
                        "hyp": hyp_w[j1 + k],
                    }
                )
            for k in range(m, la):
                omissions.append({"ref_index": i1 + k, "word": ref_w[i1 + k]})
            for k in range(m, lb):
                insertions.append({"hyp_index": j1 + k, "word": hyp_w[j1 + k]})
        elif tag == "delete":
            dele += la
            for k in range(la):
                omissions.append({"ref_index": i1 + k, "word": ref_w[i1 + k]})
        elif tag == "insert":
            ins += lb
            for k in range(lb):
                insertions.append({"hyp_index": j1 + k, "word": hyp_w[j1 + k]})

    for o in omissions:
        # the hypothesis position that brackets the gap
        o["hyp_resume_index"] = sm.get_opcodes() and None
    # annotate omissions with the Sotto chunk that resumes after them
    for tag, i1, i2, j1, j2 in ops:
        if tag in ("delete", "replace"):
            for o in omissions:
                if i1 <= o["ref_index"] < i2:
                    if j1 < len(hyp_chunk_time):
                        ci, t0, t1 = hyp_chunk_time[j1]
                    elif hyp_chunk_time:
                        ci, t0, t1 = hyp_chunk_time[-1]
                    else:
                        ci, t0, t1 = (-1, None, None)
                    o["sotto_chunk"] = ci
                    o["sotto_time_s"] = t0

    n_ref, n_hyp = len(ref_w), len(hyp_w)
    wer = (sub + dele + ins) / n_ref if n_ref else None

    # character-level
    r_c, h_c = norm_chars(ref_text), norm_chars(hyp_text)
    smc = difflib.SequenceMatcher(None, r_c, h_c, autojunk=False)
    cer_edits = sum((i2 - i1) + (j2 - j1) - min(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in smc.get_opcodes() if tag != "equal")
    cer = cer_edits / len(r_c) if r_c else None

    # per-chunk statistics
    frame_counts = [c["frames"] for c in chunks]
    sym_counts = [c["sym"] for c in chunks]
    T_counts = [c["T"] for c in chunks]
    feats = [tuple(c["feats"]) if c["feats"] else None for c in chunks]
    audio_s = summary["audio_s"]

    out = {
        "reference": {
            "source": "YouTube automatic caption, language 'en' (the ORIGINAL track: the audio stream downloaded is format 251-20 [en-US] English (US) original (default))",
            "kind": "AUTOMATIC (ASR), not a human transcript",
            "words": n_ref,
        },
        "sotto": {
            "model": summary["model"],
            "use_vad": summary["use_vad"],
            "words": n_hyp,
            "tokens": summary["tokens"],
            "audio_s": audio_s,
            "window": f"0 - {audio_s:.3f} s",
        },
        "alignment": {
            "matched": sm.ratio(),
            "substitutions": sub,
            "deletions_omitted": dele,
            "insertions_extra": ins,
            "wer": wer,
            "cer": cer,
            "population_words_ref": n_ref,
            "window_s": audio_s,
            "caveat": "reference is itself an ASR transcript; this is a RELATIVE number, not an accuracy",
        },
        "chunk_accounting": {
            "chunks_processed": summary["chunks_processed"],
            "chunk_samples": summary["chunk_samples"],
            "tail_seconds_dropped": summary["tail_seconds_dropped"],
            "empty_chunks": summary["empty_chunks"],
            "empty_chunk_share": summary["empty_chunks"] / summary["chunks_processed"],
            "vad_gated_chunks": summary["vad_gated_chunks"],
            "music_gated_chunks": summary["music_gated_chunks"],
            "frames_total": summary["frames"],
            "frames_per_chunk_mean": sum(frame_counts) / len(frame_counts),
            "frames_per_second_of_audio": summary["frames"] / audio_s,
            "symbols_over_limit_chunks": summary["symbols_over_limit_chunks"],
            "partial_tail_tokens": summary["partial_tail_tokens"],
            "T_values": T_counts[:20],
            "feat_shapes": [list(f) if f else None for f in feats[:20]],
            "symbols_per_chunk_histogram": {str(k): sym_counts.count(k) for k in sorted(set(sym_counts))},
        },
        "first_omissions": omissions[: args.n_omissions],
        "omission_count": len(omissions),
        "first_substitutions": substitutions[:30],
        "substitution_count": len(substitutions),
        "first_insertions": insertions[:30],
        "insertion_count": len(insertions),
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"ref words      : {n_ref}")
    print(f"sotto words    : {n_hyp}  ({n_hyp / n_ref:.3f} of reference)")
    print(f"tokens         : {summary['tokens']}")
    print(f"substitutions  : {sub}")
    print(f"OMISSIONS      : {dele}")
    print(f"insertions     : {ins}")
    print(f"WER            : {wer:.4f}  (population {n_ref} words, window 0-{audio_s:.1f}s)")
    print(f"CER            : {cer:.4f}  (population {len(r_c)} chars)")
    print(f"empty chunks   : {summary['empty_chunks']}/{summary['chunks_processed']} "
          f"= {summary['empty_chunks'] / summary['chunks_processed']:.3f}")
    print(f"vad gated      : {summary['vad_gated_chunks']}")
    print(f"frames/s       : {summary['frames'] / audio_s:.2f}")
    print(f"T values       : {T_counts[:12]}")
    print(f"feat shapes    : {[list(f) if f else None for f in feats[:6]]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
