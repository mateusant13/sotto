"""The split-word A/B on the LIVE path: identical audio, one function reverted.

Reads the two `SOTTO_FILE_TAP` arms and reports, ASCII-escaped so nothing is lost
to a console codepage:

  * every caption the arm emitted, in order, final and provisional;
  * the closed (`final:true`) lines;
  * whether the two arms' text is IDENTICAL ONCE SPACES ARE REMOVED -- which is
    the precise claim the fix makes (a chunk boundary stops being a word
    boundary; it must not change a single letter);
  * the fragment tokens each arm produced, so the owner's complaint shape
    ("lan e", "Tor nado", "winn able") can be seen or seen to be gone.

Usage:
  py -3 _main/word-split-live-ab.py --new _main/sweep90-live-new.jsonl \
      --before _main/sweep90-live-before.jsonl --out _main/word-split-live-ab.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys

SHORT_OK = {
    "de", "da", "do", "em", "um", "os", "as", "no", "na", "se", "ou", "e", "a", "o",
    "que", "com", "por", "pra", "pro", "dos", "das", "ao", "aos", "eu", "tu", "ele",
    "ela", "nos", "vos", "mas", "ja", "so", "la", "ca", "ta", "ne", "ai", "vi", "ver",
    "the", "and", "you", "for", "are", "was", "his", "her", "its", "our", "not", "but",
    "all", "can", "had", "has", "one", "out", "who", "any", "how", "now", "new", "get",
    "use", "way", "may", "day", "too", "see", "him", "two", "let", "put", "say", "she",
    "try", "why", "bit", "far", "own", "off", "old", "end", "few", "yet", "yes", "top",
}


def load(path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def caps(rows, final=None):
    out = []
    for r in rows:
        if r.get("type") == "caption" and (final is None or r.get("final") is final):
            out.append(r)
    return out


def fragments(text):
    got = []
    for tok in text.split():
        core = tok.strip(".,!?;:()\u2026\"'").lower()
        if 0 < len(core) <= 3 and core.isalpha() and core not in SHORT_OK:
            got.append(tok)
    return got


def dump(rows, label, fh):
    def w(s=""):
        print(s)
        fh.write(s + "\n")

    allc = caps(rows)
    fin = caps(rows, final=True)
    prov = caps(rows, final=False)
    w(f"########## {label} ##########")
    w(f"caption objects: total={len(allc)}  final:true={len(fin)}  final:false={len(prov)}")
    w()
    w("--- every caption text, in emission order (ascii-escaped, verbatim) ---")
    for i, c in enumerate(allc):
        tag = "FINAL" if c.get("final") else "prov "
        w(f"  [{i:3d}] {tag} {c.get('start')!s:>7} -> {c.get('end')!s:<7} "
          f"{ascii(c.get('text',''))}")
    w()
    w("--- closed (final:true) lines ---")
    for i, c in enumerate(fin):
        w(f"  [{i:3d}] {c.get('start')} -> {c.get('end')}  {ascii(c.get('text',''))}")
    w()
    joined_f = " ".join(c.get("text", "") for c in fin)
    joined_a = " ".join(c.get("text", "") for c in allc)
    w("--- joined FINAL text, verbatim ---")
    w("  " + ascii(joined_f))
    w("--- joined FINAL text, spaces removed ---")
    w("  " + ascii(joined_f.replace(" ", "")))
    w("--- joined ALL text, spaces removed ---")
    w("  " + ascii(joined_a.replace(" ", "")))
    w()
    w("--- fragment tokens (<=3 chars, not a known short word) ---")
    frags = []
    for c in allc:
        for f in fragments(c.get("text", "")):
            if f not in frags:
                frags.append(f)
    w(f"  {len(frags)} distinct: {ascii(frags)}")
    w()
    return joined_f, joined_a, frags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "word-split-live-ab.txt"))
    args = ap.parse_args()

    nrows = load(args.new)
    brows = load(args.before)

    with open(args.out, "w", encoding="utf-8") as fh:
        nf, na, nfr = dump(nrows, f"LIVE-NEW (on-disk code)  {os.path.basename(args.new)}", fh)
        bf, ba, bfr = dump(brows, f"LIVE-BEFORE (join_fragments reverted)  {os.path.basename(args.before)}", fh)

        def w(s=""):
            print(s)
            fh.write(s + "\n")

        w("########## THE COMPARISON ##########")
        w(f"final text identical?            {nf == bf}")
        w(f"final text identical w/o spaces? {nf.replace(' ','') == bf.replace(' ','')}")
        w(f"all   text identical w/o spaces? {na.replace(' ','') == ba.replace(' ','')}")
        w()
        w(f"fragments NEW    ({len(nfr)}): {ascii(nfr)}")
        w(f"fragments BEFORE ({len(bfr)}): {ascii(bfr)}")
        w(f"fragments only in BEFORE: {ascii([f for f in bfr if f not in nfr])}")
        w(f"fragments only in NEW   : {ascii([f for f in nfr if f not in bfr])}")
        w()
        w("--- character-level diff of the two joined FINAL texts ---")
        import difflib
        a = bf.replace(" ", "")
        b = nf.replace(" ", "")
        if a == b:
            w("  IDENTICAL character for character once spaces are removed.")
        else:
            sm = difflib.SequenceMatcher(None, a, b)
            w(f"  ratio={sm.ratio():.4f}  (not identical -- the arms decoded differently)")
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                if op != "equal":
                    w(f"   {op:8s} BEFORE {ascii(a[i1:i2])!s:20s} -> NEW {ascii(b[j1:j2])}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
