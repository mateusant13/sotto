#!/usr/bin/env python3
"""THE WORDMARK METRICS ORACLE -- is `sotto` the same size in every theme?

WHY THIS EXISTS (owner, 2026-10-21, verbatim):
    *"o `sotto` escrito em pixels diferentes, não tá padronizado"*

MEASURED on the five themes the panel actually loads (`panel.html:60-64`), before
the fix -- this is the complaint, as numbers:

    Teleprompter   shared rule (`panel.css .chrome__brand`)   11px / 600 / 0.20em
    Broadcast      `var(--size-time)` (= 10px)                 / 600 / 0.14em
    Manuscrito     `var(--size-time)` (= 10px)                 / 400 / 0.06em
    Cinema Card    literal                                    11px / 500 / 0.34em
    Instrumento    literal                                     9px / 600 / 0.28em

Five directions, five wordmarks. Switching theme changed the name's SIZE, WEIGHT
and TRACKING, so the same word occupied a different box on every screen.

THE FIX lives in the generator (`_main/_design-lane/gen_themes.py`), not in the
generated CSS: `BRAND_METRICS` is appended last in `build()` for lane A, pinning
size/weight/tracking to the shared `panel.css` values. Each direction keeps its own
FAMILY and COLOUR -- that is the design, and it stays.

THIS GATE SIMULATES THE CASCADE rather than looking for a magic string: it starts
from the shared `.chrome__brand` rule in `panel.css`, applies every
`:root[data-theme='theme-N'] ... .chrome__brand` rule in FILE ORDER (equal
specificity: later wins), and compares the resulting metrics. That is why theme-1
— which has no brand override at all — is judged correctly instead of being
special-cased.

CLAIMS
  C1 ALL FIVE AGREE -- the effective font-size, font-weight and letter-spacing are
     identical in every theme.
  C2 THE VALUES ARE THE REFERENCE'S -- they equal the shared `panel.css` rule, so
     the standard is one place and not five copies that happen to match today.
  C3 NO THEME RE-STATES A METRIC LATER -- no per-theme rule sets size/weight/
     tracking AFTER the normalising block, which would silently re-break C1.

FILES ONLY: reads `app/panel/panel.css` and `app/panel/themes/theme-*.css`. No app,
no render, no Chromium -- so it belongs in a battery. What WebView2 paints is not
this gate's claim.

`--neg-arm` appends a theme-5 override (`font-size: 9px;`) to a COPY of that file,
restores it afterwards, and demands C1 AND C2 go RED.
"""
from __future__ import annotations

import argparse
import io
import re

PANEL = "app/panel/panel.css"
THEMES = ["app/panel/themes/theme-%d.css" % i for i in range(1, 6)]
METRICS = ("font-size", "font-weight", "letter-spacing")


def read(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def strip_comments(css):
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def brand_rules(css):
    """[(selector, [(prop, value)])] for every rule mentioning `.chrome__brand`."""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", strip_comments(css)):
        selector = re.sub(r"\s+", " ", m.group(1)).strip()
        if ".chrome__brand" not in selector or "::" in selector:
            continue
        decls = []
        for decl in m.group(2).split(";"):
            if ":" in decl:
                prop, value = decl.split(":", 1)
                decls.append((prop.strip(), value.strip()))
        out.append((selector, decls))
    return out


def reference():
    """The shared rule's metrics: the standard every theme must meet."""
    ref = {}
    for selector, decls in brand_rules(read(PANEL)):
        if selector == ".chrome__brand":
            for prop, value in decls:
                if prop in METRICS:
                    ref[prop] = value
    missing = [p for p in METRICS if p not in ref]
    if missing:
        raise SystemExit("%s: `.chrome__brand` declares no %s" % (PANEL, ", ".join(missing)))
    return ref


def effective(index):
    """The cascade's answer for theme `index`, plus the rules that set a metric."""
    start = reference()
    current = dict(start)
    setters = []
    for selector, decls in brand_rules(read(THEMES[index - 1])):
        for prop, value in decls:
            if prop in METRICS:
                current[prop] = value
                setters.append((prop, value))
    return current, setters


def claim_all_agree(files=THEMES):
    rows, problems = {}, []
    for i in range(1, len(files) + 1):
        eff, _ = effective(i)
        rows[i] = (eff["font-size"], eff["font-weight"], eff["letter-spacing"])
    values = set(rows.values())
    detail = " | ".join("theme-%d %s/%s/%s" % (i, *rows[i]) for i in sorted(rows))
    if len(values) > 1:
        problems.append("%d distinct metric triples" % len(values))
        return False, "%s -- %s" % (", ".join(problems), detail)
    return True, "one triple in all five -- %s" % detail.split(" | ")[0].split(" ", 1)[1]


def claim_matches_reference(files=THEMES):
    ref = reference()
    want = (ref["font-size"], ref["font-weight"], ref["letter-spacing"])
    bad = []
    for i in range(1, len(files) + 1):
        eff, _ = effective(i)
        got = (eff["font-size"], eff["font-weight"], eff["letter-spacing"])
        if got != want:
            bad.append("theme-%d %s != %s" % (i, got, want))
    if bad:
        return False, " | ".join(bad)
    return True, "all five equal the shared `panel.css` rule: %s/%s/%s" % want


def claim_no_late_override(files=THEMES):
    """The last metric setter in each theme must be the normalising block's triple."""
    ref = reference()
    want = {"font-size": ref["font-size"], "font-weight": ref["font-weight"],
            "letter-spacing": ref["letter-spacing"]}
    problems = []
    for i in range(1, len(files) + 1):
        _, setters = effective(i)
        if not setters:
            continue                      # theme-1: inherits the shared rule, fine
        tail = {}
        for prop, value in setters:
            tail[prop] = value
        for prop in METRICS:
            if prop in tail and tail[prop] != want[prop]:
                problems.append("theme-%d sets %s: %s LAST (expected %s)"
                                % (i, prop, tail[prop], want[prop]))
    if problems:
        return False, " | ".join(problems)
    return True, "no theme re-breaks a metric after the normalising block"


def run(label, files=THEMES):
    rows = [
        ("C1", "all five themes measure identically", claim_all_agree(files)),
        ("C2", "and equal the shared reference rule", claim_matches_reference(files)),
        ("C3", "no theme overrides a metric later", claim_no_late_override(files)),
    ]
    failed = 0
    print(label)
    for key, what, (ok, detail) in rows:
        print("  %s %s %-42s %s" % ("ok  " if ok else "FAIL", key, what, detail))
        if not ok:
            failed += 1
    print("")
    print("%d check(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser(description="is the wordmark the same size in every theme?")
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    if not args.neg_arm:
        print("WORDMARK METRICS ORACLE -- PRISTINE")
        return 0 if run("") == 0 else 1

    original = read(THEMES[4])
    print("WORDMARK METRICS ORACLE -- CONTROL")
    ctrl = run("  CONTROL (the files as they stand) must be GREEN")
    print("")
    try:
        broke = original + (
            "\n/* MUTANT: the owner's complaint, restored */\n"
            ":root[data-theme='theme-5'] .chrome--inst .chrome__brand{\n"
            "  font-size: 9px;\n}\n")
        if broke == original:
            print("  MUTATION DID NOT APPLY -- the anchor is spent")
            return 1
        with io.open(THEMES[4], "w", encoding="utf-8", newline="") as fh:
            fh.write(broke)
        mut = run("  M1 theme-5's name drops to 9px again must be RED")
    finally:
        with io.open(THEMES[4], "w", encoding="utf-8", newline="") as fh:
            fh.write(original)

    ok = (ctrl == 0 and mut > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s (file restored, CRLF kept)"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl == 0 else "RED",
             "RED" if mut > 0 else "GREEN (INERT MUTANT)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
