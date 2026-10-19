#!/usr/bin/env python
"""CENSUS: how much PLAYER CHROME the YouTube reader fed the caption box.

Owner, 2026-10-19, verbatim:
    "eu quero que tu trabalhe nas legendas do youtube substituem a ao vivo"

WHY A CENSUS AND NOT A PROSE CLAIM
----------------------------------
The mechanism that makes YouTube's captions replace the live ASR caption was
MEASURED WORKING long ago (the log shows `EXTERNAL_CAPTION_SENT` ->
`EXTERNAL_CAPTIONS_WORKER_PARKED` -> `BRIDGE_STOP reason=external-captions`:
the ASR worker is stopped and the player's line takes the box). What nobody
measured is WHAT the reader feeds it.

This reads the owner's own app log -- 220 real `EXTERNAL_CAPTION_SENT` lines,
produced on this box on 2026-10-17 and 2026-10-18 -- and asks one question of
every line: would the SHIPPED rule call it chrome?

    python _main/external-caption-chrome-census.py
    python _main/external-caption-chrome-census.py --neg-arm

THE NEGATIVE ARM removes the rule from a COPY of the shipped module and shows
the survivors going back up. A census that cannot say no is a paragraph.

Nothing is launched. No browser, no player, no shell, no worker.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import os
import re
import sys
import tempfile

REPO = r"H:\sotto"
TARGET = os.path.join(REPO, "app", "webview", "external_subs.py")
LOG = os.path.join(REPO, "_main", "webview-run.log")

SENT = re.compile(r'EXTERNAL_CAPTION_SENT count=(\d+) source=(\S+) '
                  r'final=(\S+) text="((?:[^"\\]|\\.)*)"')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def real_lines():
    """[(day, text)] -- every external line the owner's own app produced."""
    out = []
    if not os.path.exists(LOG):
        return out
    with open(LOG, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = SENT.search(line)
            if not m:
                continue
            try:
                text = json.loads('"' + m.group(4) + '"')
            except ValueError:
                text = m.group(4)
            out.append((line[:10], text))
    return out


def mutante(src):
    """A copy whose chrome rule is gone -> the pre-fix behaviour.

    ONE mutation, count-asserted, so a stale anchor fails loudly instead of
    silently measuring the shipped code a second time.
    """
    out, n = re.subn(r"(?m)^    text = str\(line or ''\)\.strip\(\)$",
                     "    return False\n    text = str(line or '').strip()",
                     src)
    if n != 1:
        raise SystemExit("MUTANT INVALID: anchor matched %d times, want 1" % n)
    return out


def classify(rows, mod):
    chrome, kept = [], []
    for day, text in rows:
        if mod._joined_row_is_chrome(text):
            chrome.append((day, text))
        else:
            kept.append((day, text))
    return chrome, kept


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true",
                    help="also run the copy WITHOUT the chrome rule")
    args = ap.parse_args(argv)

    rows = real_lines()
    if not rows:
        print("NO EXTERNAL LINES in %s -- nothing to census" % LOG)
        return 1
    live = load_module(TARGET, "extsubs_census")
    chrome, kept = classify(rows, live)

    print("CENSUS: %d external lines in %s" % (len(rows), os.path.basename(LOG)))
    byday = collections.Counter(d for d, _t in rows)
    chromeday = collections.Counter(d for d, _t in chrome)
    for day in sorted(byday):
        print("  %s  lines=%3d  chrome=%2d  (%d%%)"
              % (day, byday[day], chromeday[day],
                 round(100.0 * chromeday[day] / max(1, byday[day]))))
    print()
    print("  chrome the shipped rule CATCHES (%d):" % len(chrome))
    for day, text in sorted(set(chrome), key=lambda t: (t[0], t[1])):
        print("    %s  %r" % (day, text))
    print()
    print("  lines that SURVIVE as captions (%d):" % len(kept))

    failures = []
    # The chrome that the owner's log shows, by name. Each of these reached
    # the caption box in the real app.
    MUST_CATCH = [
        "344", "277", "1", "2", "1,9 mil", "15 mil há 8 h", "4,6 mi há 5 dias",
        "há 1 dia", "há 4 sem.", "@zachw2906", "·",
    ]
    caught_texts = set(t for _d, t in chrome)
    for t in MUST_CATCH:
        if t not in caught_texts:
            failures.append("chrome %r is NOT caught by the shipped rule" % t)
    # The RESIDUE: chrome that is a SENTENCE, so no shape rule can take it
    # without eating a real caption. It is REPORTED, not failed -- and it is
    # the reason the real caption track exists (the reader that paints the
    # page can only ever read the page).
    KNOWN_RESIDUE = [
        "Oferta sujeita aos termos. Cancele quando quiser.",
    ]
    kept_texts = set(t for _d, t in kept)
    for t in KNOWN_RESIDUE:
        if t in kept_texts:
            print("  RESIDUE (chrome that is a sentence, so shape cannot take it):"
                  " %r" % t)
    # The captions must NOT be eaten: these are real lines from the log.
    MUST_KEEP = [
        "Same with Jame time and their outsider major win. the ultima",
        "FURIA seized their moment.",
        "will be FURIA moment. 18,000 of the most",
        ">> Nobody in modern Counter-Strike would",
        "quando ele disse >> aquilo",          # a `>` INSIDE a sentence
        "ficou lá 1 dia",                       # "há 1 dia" inside a sentence
        "foram 2 os que chegaram",             # a number inside a sentence
    ]
    kept_texts = set(t for _d, t in kept)
    for t in MUST_KEEP:
        if t in kept_texts:
            continue
        # The two "inside a sentence" cases are not in the log: they are
        # constructed here and must survive the rule.
        try:
            if not live._joined_row_is_chrome(t):
                continue
        except Exception:
            pass
        failures.append("a real caption %r was eaten by the chrome rule" % t)

    for f in failures:
        print("  RED %s" % f)

    if args.neg_arm:
        with open(TARGET, "r", encoding="utf-8") as fh:
            src = fh.read()
        tmp = tempfile.mkdtemp(prefix="chrome-census-")
        path = os.path.join(tmp, "extsubs_nochrome.py")
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(mutante(src))
        broken = load_module(path, "extsubs_nochrome")
        chrome2, kept2 = classify(rows, broken)
        print()
        print("NEGATIVE ARM (the rule removed from a COPY):")
        print("  chrome caught: %d -> %d   lines kept as captions: %d -> %d"
              % (len(chrome), len(chrome2), len(kept), len(kept2)))
        if len(kept2) <= len(kept):
            failures.append("NEGATIVE ARM PRODUCED NO EXTRA CHROME -> the census "
                            "cannot say no")

    print("VERDICT: %s" % ("PASS" if not failures else "FAIL"))
    for f in failures:
        print("  - %s" % f)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
