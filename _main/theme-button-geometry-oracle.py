#!/usr/bin/env python3
"""THE BUTTON GEOMETRY ORACLE -- does a theme move or resize a button?

WHY THIS EXISTS (owner, 2026-10-21, verbatim):
    *"vários designs trocam o tamanho do botão e a posição… não consigo manter o
    mouse"*

That is a complaint about the PANEL'S CONTROLS moving between themes: the pointer
is aimed at a button and the button is somewhere else (or a different size) after
a theme switch. The panel's controls are styled by `app/panel/panel.css`, and each
of the five themes is allowed to repaint them -- colour, border, shadow -- but NOT
to move or resize them. Before this gate that rule was a sentence in a receipt
(`_main/receipt-20261013-buttons-are-the-same-in-every-design.md`) and nothing
measured it today.

WHAT IS A BUTTON HERE: any rule scoped to a theme whose selector names a button
(`.icon-button`, `.theme-button`, `.dialog-button`, `.search__button`,
`.strip-button`, `.menu-select`, `button`). For each of those rules the gate keeps
the declarations that can move or resize the element:

    width height min-width max-width min-height
    padding* margin* position top right bottom left
    order flex* transform translate\* scale\*

CLAIMS
  C1 THE SIGNATURE IS IDENTICAL -- all five themes declare the same geometry, in
     the same order, for the same selectors. A theme that adds or drops a
     geometry declaration is a theme where a button changed.
  C2 NOTHING IS PINNED -- no theme declares `position` (other than `static`),
     `top`/`right`/`bottom`/`left`, `order` or `transform` on a button. Those are
     the declarations that put a control somewhere the pointer does not expect.
  C3 THE THEME PICKER ITSELF IS THE SAME -- `.theme-button` carries exactly the
     same geometry in all five, because it is the button the owner clicks to
     switch themes: if it moves, he loses the pointer exactly at the moment he is
     using it.

FILES ONLY: reads `app/panel/themes/theme-*.css`. Launching nothing is what lets it
live in a battery. What WebView2 PAINTS is not this gate's claim (the rendered
half is `_main/_border-radius-probe.py`, a Chromium launch, and is out of battery).

`--neg-arm` inserts a `position: absolute; top: 3px; left: 9px` on one theme's
`.icon-button` -- the owner's complaint in one line -- and demands C1/C2/C3 go RED.
"""
from __future__ import annotations

import argparse
import io
import re

THEMES = ["app/panel/themes/theme-%d.css" % i for i in range(1, 6)]

BUTTON_WORDS = ("icon-button", "theme-button", "dialog-button", "search__button",
                "strip-button", "menu-select")

GEOMETRY = (
    "width", "height", "min-width", "max-width", "min-height", "max-height",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "position", "top", "right", "bottom", "left", "order", "flex", "flex-grow",
    "flex-shrink", "flex-basis", "transform", "translate", "scale",
)

PINNING = ("position", "top", "right", "bottom", "left", "order", "transform",
           "translate", "scale")


def read(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def strip_comments(css):
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def button_rules(css, index):
    """[(selector, [geometry declarations])] for one theme, in file order."""
    out = []
    body = strip_comments(css)
    for m in re.finditer(r"(:root\[data-theme='theme-%d'\])([^{}]*)\{([^}]*)\}" % index, body):
        selector = (m.group(1) + m.group(2)).strip()
        selector = re.sub(r"\s+", " ", selector)
        if not any(word in selector for word in BUTTON_WORDS):
            continue
        geo = []
        for decl in m.group(3).split(";"):
            if ":" not in decl:
                continue
            prop = decl.split(":", 1)[0].strip().lower()
            value = decl.split(":", 1)[1].strip()
            if prop in GEOMETRY:
                geo.append("%s: %s" % (prop, value))
        # ONLY RULES THAT ACTUALLY DECLARE GEOMETRY COUNT. A theme is allowed to
        # repaint a control without resizing it, so a colour-only rule for a
        # selector another theme does not mention is not a geometry difference --
        # counting it made this claim fail on the shipped files for a reason that
        # is not the owner's complaint.
        if geo:
            out.append((selector, geo))
    return out


def signature(index, css):
    """Just the geometry, selector by selector -- what must not differ.

    The selector text is normalised (`theme-1` -> `theme-N`) before it is compared:
    the theme's own NUMBER is the one difference that is correct, and comparing raw
    text would make this claim fail on every theme for a reason that is not a defect.
    """
    out = []
    for sel, geo in button_rules(css, index):
        out.append((re.sub(r"theme-\d+", "theme-N", sel), tuple(geo)))
    return out


def claim_signature(files):
    sigs = {}
    for i, path in enumerate(files, start=1):
        sigs[i] = signature(i, read(path))
    first = sigs[1]
    problems = []
    for i, sig in sigs.items():
        if i == 1:
            continue
        if sig != first:
            missing = [s for s, _ in first if s not in [x for x, _ in sig]]
            extra = [s for s, _ in sig if s not in [x for x, _ in first]]
            changed = [s for s, g in first if dict(sig).get(s) != g]
            problems.append("theme-%d differs (missing=%d extra=%d changed=%d): %s"
                            % (i, len(missing), len(extra), len(changed),
                               (extra or missing or changed)[0][:60]))
    if problems:
        return False, " | ".join(problems)
    total = sum(len(g) for _, g in first)
    return True, "all five themes declare the same %d geometry declaration(s) over %d button rule(s)" % (
        total, len(first))


def claim_nothing_pinned(files):
    problems = []
    for i, path in enumerate(files, start=1):
        for selector, geo in button_rules(read(path), i):
            for decl in geo:
                prop = decl.split(":", 1)[0].strip()
                value = decl.split(":", 1)[1].strip()
                if prop in PINNING and value not in ("static", "none", "1"):
                    problems.append("theme-%d %s -> %s" % (i, selector[:48], decl))
    if problems:
        return False, " | ".join(problems[:6])
    return True, "no theme pins, offsets, reorders or transforms a button"


def claim_picker_stable(files):
    rows, problems = [], []
    for i, path in enumerate(files, start=1):
        geo = dict((sel, g) for sel, g in button_rules(read(path), i)
                   if sel.endswith(".theme-button"))
        key = [sel for sel in geo if sel.endswith(".theme-button")]
        if not key:
            problems.append("theme-%d: no .theme-button rule" % i)
            continue
        rows.append((i, tuple(geo[key[0]])))
    values = {r for _, r in rows}
    if len(values) > 1:
        problems.append("the picker's geometry differs: %s" % rows)
    if problems:
        return False, " | ".join(problems)
    return True, ".theme-button is %s in all five" % (list(values)[0] if values else "-",)


def run(files, label):
    rows = [
        ("C1", "every theme declares the same button geometry", claim_signature(files)),
        ("C2", "no theme pins / offsets / reorders a button", claim_nothing_pinned(files)),
        ("C3", "the theme picker is the same in all five", claim_picker_stable(files)),
    ]
    failed = 0
    print(label)
    for key, what, (ok, detail) in rows:
        print("  %s %s %-48s %s" % ("ok  " if ok else "FAIL", key, what, detail))
        if not ok:
            failed += 1
    print("")
    print("%d check(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


def inject_defect(css):
    """The complaint in one line: this theme's icon button jumps."""
    return css.replace(
        ".icon-button",
        ".icon-button { position: absolute; top: 3px; left: 9px; } .icon-button",
        1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="do themes move or resize the panel's buttons?")
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    if not args.neg_arm:
        print("BUTTON GEOMETRY ORACLE -- PRISTINE")
        return 0 if run(THEMES, "") == 0 else 1

    original = {p: read(p) for p in THEMES}
    print("BUTTON GEOMETRY ORACLE -- CONTROL")
    ctrl = run(THEMES, "  CONTROL (the files as they stand) must be GREEN")
    print("")

    target = THEMES[1]
    try:
        broken = inject_defect(original[target])
        if broken == original[target]:
            print("  MUTATION DID NOT APPLY -- the anchor is spent")
            return 1
        with io.open(target, "w", encoding="utf-8", newline="") as fh:
            fh.write(broken)
        mut = run(THEMES, "  M1 one theme's icon button jumps (position/top/left) must be RED")
    finally:
        for path, text in original.items():
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)

    ok = (ctrl == 0 and mut > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s (restored from memory, CRLF kept)"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl == 0 else "RED",
             "RED" if mut > 0 else "GREEN (INERT MUTANT)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
