"""The TWO COLOURS of the word split, measured on the LIVE path (file tap, no device).

GREEN = the shipped `join_fragments`.  RED = the pre-fix body, which is the code the
owner's running worker (pid 29008, spawned 08:01:56) still holds in memory because a
Python process reads its source once, at import.

Also: the owner's own fragments, run through the REAL `LineFormer` and the REAL
`join_fragments`, and the vocabulary fact that decides the apostrophe case.
"""

from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "worker")
sys.path.insert(0, WORKER)

import sotto_worker as W  # noqa: E402

MARK = W.WORD_MARK
VOCAB = W.StreamAsr.__init__ and None


def load(path):
    with io.open(path, encoding="utf-8") as fh:
        return json.load(fh)


def vocab():
    p = os.path.join(WORKER, "models", "nemotron-3.5-asr-streaming-0.6b-int8", "vocab.txt")
    with io.open(p, encoding="utf-8") as fh:
        v = fh.read().split("\n")
    if v and v[-1] == "":
        v.pop()
    return v


def pre_fix_join(frags):
    return " ".join(t for t, _c in frags if t).strip()


def main():
    good = load(os.path.join(HERE, "_live-seam-probe.json"))
    bad = load(os.path.join(HERE, "_live-seam-neg.json"))

    print("=" * 78)
    print("1. THE LIVE PATH, TWO COLOURS — same clip, same live loop, same 14 s")
    print("=" * 78)
    print("   GREEN (shipped join_fragments)   continues=True seen:",
          good["cont"]["true"], "of", len(good["pushes"]), "pushes")
    print("   RED   (pre-fix body, neg-arm)    continues=True seen:",
          bad["cont"]["true"], "of", len(bad["pushes"]), "pushes")
    print()
    g = [e["text"] for e in good["captions"] if e.get("final")]
    b = [e["text"] for e in bad["captions"] if e.get("final")]
    print("   CLOSED lines, GREEN:")
    for t in g:
        print("     ", repr(t))
    print("   CLOSED lines, RED:")
    for t in b:
        print("     ", repr(t))

    print()
    print("   seam-by-seam, the fragments where the two colours DISAGREE:")
    gp = [p for p in good["pushes"] if p["text"]]
    bp = [p for p in bad["pushes"] if p["text"]]
    n = 0
    for i in range(min(len(gp), len(bp))):
        if gp[i]["line_after"] != bp[i]["line_after"]:
            n += 1
            print("    %2d GREEN %-5s %r" % (i, "GLUE" if gp[i]["continues"] else "space",
                                             gp[i]["text"]))
            print("       -> GREEN line %r" % gp[i]["line_after"])
            print("       -> RED   line %r" % bp[i]["line_after"])
    print("   fragments where the two colours differ:", n)

    print()
    print("=" * 78)
    print("2. THE OWNER'S OWN STRINGS, through the REAL LineFormer + join_fragments")
    print("=" * 78)
    # (fragment_a, continues_of_b, fragment_b) — the seam the owner sees split.
    cases = [
        ("lan", "e"), ("Tor", "nado"), ("winn", "able"), ("tow", "s"),
        ("he", "'s"), ("an", "other"),
        # the two from the shell log the coordinating agent quoted
        ("damage he", "'s gonna go for an"), ("gonna go for an", "other golem"),
    ]
    for a, b2 in cases:
        for cont in (True, False):
            f = W.LineFormer(min_chars=0, emit_partial=False)
            f.push(a, 0.0, 0.5)
            f.push(b2, 0.5, 1.0, continues=cont)
            got = f.line()
            want = (a + b2) if cont else (a + " " + b2)
            print("   %-18r + %-22r continues=%-5s -> %-40r %s"
                  % (a, b2, cont, got, "OK" if got == want else "MISMATCH"))
        # what the owner's worker (pre-fix) produced
        f = W.LineFormer(min_chars=0, emit_partial=False)
        f._words = [(a, False), (b2, True)]
        print("      pre-fix body would give: %r" % pre_fix_join(f._words))

    print()
    print("=" * 78)
    print("3. THE VOCABULARY FACT that decides the apostrophe (not a guess)")
    print("=" * 78)
    v = vocab()
    ap = [(i, t) for i, t in enumerate(v) if "'" in t]
    print("   tokens in the whole vocabulary containing an apostrophe:", len(ap), ap)
    print("   tokens starting with the word-start marker + apostrophe:",
          [(i, t) for i, t in enumerate(v) if t.startswith(MARK + "'")])
    print("   => the apostrophe CANNOT carry a word-start marker, so a chunk that")
    print("      begins with `'` is ALWAYS a continuation: the shipped code always")
    print("      glues it, the pre-fix code always spaced it. `he 's` is decided.")
    for frag in ["able", "e", "s", "other", "nado", "winn", "tow", "lan"]:
        has = [i for i, t in enumerate(v) if t == frag]
        marked = [i for i, t in enumerate(v) if t == MARK + frag]
        print("   %-8r bare=%-10s marked=%-10s %s"
              % (frag, has[:1] or "-", marked[:1] or "-",
                 "marked form EXISTS -> model may choose a word start"
                 if marked else "NO marked form -> a chunk starting here must glue"))


if __name__ == "__main__":
    main()
