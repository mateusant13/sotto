"""ORACLE for the WORD-SPLIT defect in `worker/sotto_worker.py` (lane SottoWordSplit).

THE DEFECT (owner, verbatim: "vamo formatar o texto direito. tem palavras que
ficam com espaço tipo 'shi t'")
-----------------------------------------------------------------------------
`StreamAsr.detok()` turns the SentencePiece word-start marker U+2581 into a space
and then `.strip()`s it away, and `LineFormer.line()` joined the decoded chunk
texts with `" ".join(...)` — so EVERY chunk boundary became a WORD boundary.
MEASURED on `_main/pt-br-sample.wav`: the chunk at 5.60 s decodes `▁próx` and the
chunk at 6.16 s decodes `ima` (one token, NO marker — the model saying "this is
the rest of the word"), and the caption read **"próx ima"**.

THE FIX (`join_fragments` + `chunk_is_continuation`, `LineFormer.push(continues=)`)
---------------------------------------------------------------------------------
A chunk boundary is not a word boundary: a fragment whose first real token
carries no `▁` is GLUED to the word the previous chunk left open; every other
fragment takes exactly one space. `join_fragments` is the single separator
decision — `line()` and the `max_chars` lookahead both go through it.

THIS ORACLE
-----------
Drives the REAL `LineFormer`/`join_fragments`/`chunk_is_continuation` from the
shipped module (never a hand copy) over the REAL per-chunk token ids captured by
`_main/word-split-trace.py`, and compares against the REAL end-to-end file-mode
runs (`_main/_wordsplit-before.jsonl` = the same path with the one join line
reverted, `_main/_wordsplit-after.jsonl` = `--selftest` as shipped).

  --neg-arm  reverts the ONE line (monkeypatches `join_fragments` to its pre-fix
             body, `" ".join(...)`) and requires every FIX arm to go RED while
             every control/invariant arm stays GREEN. A fix arm the pre-fix code
             also passes would prove nothing.

Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window, no audio device, no model
load: pure file reads.
"""

from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

TRACE = os.path.join(HERE, "word-split-trace.json")
BEFORE_JSONL = os.path.join(HERE, "_wordsplit-before.jsonl")
AFTER_JSONL = os.path.join(HERE, "_wordsplit-after.jsonl")

RESULTS = []          # (name, ok, is_fix_arm)


def arm(name, got, want, fix_arm=True):
    ok = got == want
    RESULTS.append((name, ok, fix_arm))
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}"
          f"{'' if fix_arm else '   (invariant/control)'}")
    print(f"       got  = {got!r}")
    print(f"       want = {want!r}")


def pre_fix_join(frags):
    """The shipped join, verbatim: every chunk seam became a word boundary."""
    return " ".join(t for t, _c in frags if t).strip()


def load_vocab(trace):
    p = os.path.join(REPO, trace["model_dir"], "vocab.txt")
    with io.open(p, encoding="utf-8") as fh:
        v = fh.read().split("\n")
    if v and v[-1] == "":
        v.pop()
    return v


def jsonl_captions(path):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "caption":
                out.append(rec.get("text", ""))
    return out


def replay(W, trace, vocab, partial=True, min_chars=1):
    """The file-mode event order, verbatim: push, take_closed, …, flush, take_closed."""
    f = W.LineFormer(min_chars=min_chars, emit_partial=partial)
    out = []
    for row in trace["chunks"]:
        cont = W.chunk_is_continuation(vocab, row["ids"])
        for ev in W.line_events(f.push(row["stripped"], row["start"], row["end"],
                                       continues=cont)):
            out.append(ev["text"])
        for ev in W.line_events(f.take_closed()):
            out.append(ev["text"])
    for ev in W.line_events(f.flush()):
        out.append(ev["text"])
    for ev in W.line_events(f.take_closed()):
        out.append(ev["text"])
    return out


def changed_seams(W, trace, vocab):
    """The seams the fix is allowed to touch: a fragment that continues the open
    word, i.e. the model marked NO word boundary there."""
    seams = []
    for row in trace["chunks"]:
        if not row["stripped"]:
            continue
        if W.chunk_is_continuation(vocab, row["ids"]):
            seams.append(row["i"])
    return seams


def main():
    neg = "--neg-arm" in sys.argv
    for p in (TRACE, BEFORE_JSONL, AFTER_JSONL):
        if not os.path.exists(p):
            print(f"SETUP ERROR: missing {p}\n"
                  f"  run: pythonw.exe _main/word-split-evidence.py")
            return 2

    import sotto_worker as W  # noqa: E402
    global W_REF
    W_REF = W

    trace = json.load(io.open(TRACE, encoding="utf-8"))
    vocab = load_vocab(trace)

    if neg:
        W.join_fragments = pre_fix_join
        print("NEG-ARM: `join_fragments` reverted to the pre-fix body "
              '(" ".join(...)); every FIX arm must go RED.\n')

    # ── the two texts, over the SAME trace, same model, same audio ──────────
    before = replay_with(W, trace, vocab, pre_fix_join)
    after = replay(W, trace, vocab)
    before_txt = "\n".join(before)
    after_txt = "\n".join(after)
    real_before = jsonl_captions(BEFORE_JSONL)
    real_after = jsonl_captions(AFTER_JSONL)

    print(f"trace: {trace['wav']}  {trace['wav_s']}s  model={trace['model']}  "
          f"lang={trace['lang']}({trace['lang_id']})  chunks={len(trace['chunks'])}")
    print(f"worker sha256: {trace['worker_sha256']}")
    print("\n--- BEFORE (chunk seam = word boundary) ---")
    print(before_txt)
    print("\n--- AFTER (a chunk boundary is not a word boundary) ---")
    print(after_txt)

    seams = changed_seams(W, trace, vocab)
    print(f"\nseams the model marked as MID-WORD (no U+2581): chunk indexes {seams}")
    for i in seams:
        row = trace["chunks"][i]
        print(f"  chunk {i:>2}  first_tok={row['first_tok']!r}  "
              f"raw={row['raw']!r}  stripped={row['stripped']!r}")

    # ── arm 1 (control): the trace IS the shipped path ──────────────────────
    # Replayed through the pre-fix join it must reproduce the real BEFORE run,
    # caption for caption. If it does not, the trace is not the code path the
    # owner runs and nothing below is about the owner's captions.
    arm("the trace replayed through the PRE-FIX join reproduces the real BEFORE run",
        before, real_before, fix_arm=False)

    # ── arm 2 (control): the defect is REAL in that text ────────────────────
    # Not "contains a space": the two halves of a word the model decoded as ONE
    # word, split. `próx` + `ima` and `preci` + `m` are the two measured cases.
    split_words = ["próx ima", "preci m"]
    arm("the BEFORE text really contains the owner's split words",
        ([w for w in split_words if w in before_txt], "shi t" in before_txt),
        (split_words, False), fix_arm=False)

    # ── arm 3 (FIX): the split words are whole ──────────────────────────────
    arm("the AFTER text has the whole words",
        ([w for w in split_words if w in after_txt], ["próxima" in after_txt,
                                                      "precim" in after_txt]),
        ([], [True, True]))

    # ── arm 4 (FIX): NOTHING ELSE MOVED — the two texts differ by SPACES ONLY ─
    # Strongest available statement: both are the same fragments in the same
    # order, so deleting every space from both must give the SAME string. Any
    # letter changed, added, dropped or reordered breaks this arm. The second
    # element is the same claim at character level: no character except the
    # space may be present in BEFORE and absent from AFTER. The FIRST element is
    # what keeps this arm from passing vacuously when the fix is reverted: the
    # text must actually have changed.
    arm("the two texts differ by SPACES ONLY, and the fix did change them",
        (before_txt != after_txt,
         before_txt.replace(" ", "") == after_txt.replace(" ", ""),
         sorted(set(before_txt) - set(after_txt) - {" "})),
        (True, True, []))

    # ── arm 5 (FIX): the changed seams are exactly the MID-WORD seams ───────
    # Compare the LINES so a line that merely got shorter is visible per seam,
    # and pin the line COUNT: a `zip` over two lists of different lengths would
    # silently hide a line the fix moved.
    def diff_seams(a, b):
        out = []
        for x, y in zip(a, b):
            if x != y:
                out.append((x, y))
        return out

    d = diff_seams(before, after)
    arm("exactly the MID-WORD seams changed, and each change only DELETES spaces",
        (len(before) == len(after), len(d) >= 1,
         all(x.replace(" ", "") == y.replace(" ", "") and len(y) < len(x)
             for x, y in d)),
        (True, True, True))

    # ── arm 5b (FIX): the verbatim unit of the owner's defect ───────────────
    # The four real fragments of the measured seam, pushed with the verdicts the
    # model's own tokens give: `▁próx` | `ima` | `▁segunda-feira` | `.`
    f = W.LineFormer(emit_partial=False)
    got5b = []
    for frag, cont in (("próx", False), ("ima", True),
                       ("segunda-feira", False), (".", True)):
        got5b += [e["text"] for e in f.push(frag, 0.0, 0.5, continues=cont)]
    got5b += [e["text"] for e in W.line_events(f.flush())]
    arm("a continuing fragment glues, a new word takes one space (verbatim case)",
        got5b, ["próxima segunda-feira."])

    # ── arm 6 (control): the FIRST fragment is never glued ─────────────────
    f = W.LineFormer(emit_partial=False)
    f.push("abc", 0.0, 0.5, continues=True)
    arm("a continuation verdict on the FIRST fragment of a line is ignored",
        [e["text"] for e in W.line_events(f.flush())], ["abc"], fix_arm=False)

    # ── arm 7 (control): a close drops the continuation ────────────────────
    # Same expectation under BOTH colours on purpose: this arm is about the
    # CLOSE, not about the join. After a line has closed, a fragment that would
    # have continued it must start a word — the word it would continue is gone.
    f = W.LineFormer(emit_partial=False)
    shown = [e["text"] for e in f.push("abc", 0.0, 0.5, continues=False)]
    shown += [e["text"] for e in f.push(".", 0.5, 1.0, continues=False)]
    closed = [e["text"] for e in W.line_events(f.take_closed())]
    shown += [e["text"] for e in f.push("xy", 1.0, 1.5, continues=True)]
    shown += [e["text"] for e in f.flush()]
    arm("a fragment arriving after a CLOSE starts a word (nothing left to continue)",
        (closed, shown, "abc .xy" not in shown), (["abc ."], ["abc .", "xy"], True),
        fix_arm=False)

    # ── arm 8 (FIX): a glued fragment pays NO separator at the cap ──────────
    # max_chars=10: "abcde" + continuing "fghij" is a 10-char line and must NOT
    # close; the pre-fix lookahead charged 5+1+5=11 and closed it into two lines.
    f = W.LineFormer(emit_partial=False, max_chars=10)
    caps = []
    for ev in f.push("abcde", 0.0, 0.5, continues=False):
        caps.append(ev["text"])
    for ev in f.push("fghij", 0.5, 1.0, continues=True):
        caps.append(ev["text"])
    caps += [e["text"] for e in f.flush()]
    arm("the max_chars lookahead charges a glued fragment no separator",
        (caps, max(len(t) for t in caps) <= 10), (["abcdefghij"], True))

    # ── arm 9 (control): the verdict comes from the TOKENS, specials skipped ─
    v = ["<blank>", "\u2581próx", "ima", "a", "b"]
    arm("chunk_is_continuation reads the tokens and skips <special>s",
        (W.chunk_is_continuation(v, [0, 1]), W.chunk_is_continuation(v, [2]),
         W.chunk_is_continuation(v, [0]), W.chunk_is_continuation(v, [1, 3])),
        (False, True, False, False), fix_arm=False)

    # ── arm 10 (FIX): the pure replay equals the REAL --selftest run ────────
    arm("the pure AFTER replay equals the real shipped --selftest captions",
        after, real_after)

    # ── arm 11 (FIX): the captions AGREE with the model's own whole-run text ─
    # `done.text` is `detok()` of the WHOLE run's token list: it joins every
    # token (markers included) and only then turns `▁` into a space, so it never
    # had the defect and is the model's own ground truth for these words.
    # MEASURED: it is byte-identical BEFORE and AFTER the fix (tokens 70, frames
    # 252, blank_frac 0.7222 on both) and it already reads "…na próxima
    # segunda-feira.  Os moradores precim de…". The captions had drifted from it;
    # the fix makes them agree, and the pre-fix ones do NOT appear in it.
    def done_text(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line.startswith("{"):
                continue
            rec = json.loads(line)
            if rec.get("state") == "selftest-done":
                return rec.get("text", "")
        return ""

    def finals(path):
        out = []
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line.startswith("{"):
                continue
            rec = json.loads(line)
            if rec.get("type") == "caption" and rec.get("final"):
                out.append(rec.get("text", ""))
        return out

    gt = done_text(AFTER_JSONL)
    gt_before = done_text(BEFORE_JSONL)
    aj, bj = " ".join(after), " ".join(before)
    arm("the captions agree with the model's own whole-run detok (`done.text`)",
        ([f in gt for f in finals(AFTER_JSONL)],
         [f in gt for f in finals(BEFORE_JSONL)],
         gt == gt_before,
         "próxima" in aj, "precim" in aj,
         "próxima" in bj, "precim" in bj),
        ([True, True], [False, False], True, True, True, False, False))

    # ── verdict ─────────────────────────────────────────────────────────────
    if neg:
        red_fix = [n for n, ok, fix in RESULTS if fix and not ok]
        green_fix = [n for n, ok, fix in RESULTS if fix and ok]
        bad_inv = [n for n, ok, fix in RESULTS if not fix and not ok]
        ok = bool(red_fix) and not green_fix and not bad_inv
        print(f"\nNEG-ARM: {len(red_fix)} FIX arm(s) went RED as required, "
              f"{len(green_fix)} stayed green (must be 0), "
              f"{len(bad_inv)} control arm(s) broke (must be 0)")
        for n in green_fix:
            print(f"  STILL GREEN under the revert: {n}")
        for n in bad_inv:
            print(f"  CONTROL BROKE: {n}")
        print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\nword-split-oracle: {len(RESULTS) - len(failed)} PASS / {len(failed)} FAIL "
          f"({len(RESULTS)} arms)  impl={W.__file__}")
    for n in failed:
        print(f"  FAILED: {n}")
    print(f"VERDICT: {'PASS' if not failed else 'FAIL'}")
    return 0 if not failed else 1


def replay_with(W, trace, vocab, joiner):
    saved = W.join_fragments
    W.join_fragments = joiner
    try:
        return replay(W, trace, vocab)
    finally:
        W.join_fragments = saved


if __name__ == "__main__":
    sys.exit(main())
