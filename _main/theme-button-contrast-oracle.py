#!/usr/bin/env python3
"""THE THEME-BUTTON CONTRAST ORACLE -- can you SEE the button's border?

WHY THIS EXISTS (owner, 2026-10-21, verbatim):
    *"o botão do nome do tema não tem contraste, não dá pra ver a borda"*

He was describing a border that is present in the CSS and absent to the eye:

    :root[data-theme='theme-N'] .theme-button {
      border: 1px solid var(--line);        <-- a PANEL/desktop hairline
      background: var(--accent-soft);       <-- the button's own fill
    }

`--line` is tuned to separate the panel from the desktop, so on the button's own
`--accent-soft` fill it measured **1.35-1.56:1** across the five shipped themes.
WCAG 1.4.11 (non-text contrast) asks **3:1** for a component boundary. The border
was therefore below the threshold that makes it a boundary at all.

THE FIX, and why 0.70: `--line-strong` does not save it (worst case 2.05:1), and
the accent has to be composited over the fill to be judged. Measured across all
five themes, border vs the fill it sits on:

    accent @ 0.45 -> worst 2.26:1   FAILS
    accent @ 0.60 -> worst 3.06:1
    accent @ 0.70 -> worst 3.71:1   CHOSEN
    accent @ 1.00 -> worst 6.26:1   (a shouting border)

CLAIMS
  C1 the rule USES the derived token -- `.theme-button`'s resting border is
     `var(--accent-line)`, not `var(--line)` (a fix that only changes the token
     value while the rule still points at the hairline fixes nothing).
  C2 the CONTRAST is real -- composited exactly as a browser would, every one of
     the five themes reaches 3:1. Measured, not asserted.
  C3 HOVER does not go backwards -- the hover border is at least as visible as
     the resting one. (It used to point at `--line-strong`, i.e. hovering made
     the border fainter than resting after this fix.)

FILES ONLY: this reads `app/panel/themes/theme-*.css`. It launches nothing, so it
belongs in a battery. The rendered half (what WebView2 paints) is not this gate's
claim and is not measured here.

`--neg-arm` restores the shipped defect (the rule back to `var(--line)`) and
demands C1 and C2 go RED.
"""
from __future__ import annotations

import argparse
import io
import re
import sys

THEMES = ["app/panel/themes/theme-%d.css" % i for i in range(1, 6)]
MIN_RATIO = 3.0


# ---------------------------------------------------------------- colour maths
def parse_colour(value):
    value = value.strip()
    m = re.match(r"rgba?\(([^)]*)\)", value)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        alpha = float(parts[3]) if len(parts) > 3 else 1.0
        return (float(parts[0]), float(parts[1]), float(parts[2]), alpha)
    m = re.match(r"#([0-9a-fA-F]{6})\b", value)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    return None


def over(fg, bg):
    r, g, b, a = fg
    return (r * a + bg[0] * (1 - a), g * a + bg[1] * (1 - a), b * a + bg[2] * (1 - a))


def luminance(c):
    def channel(x):
        x = x / 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2])


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------- the CSS
def read(path):
    # newline="" -- read the bytes as they are. With universal newlines the file's
    # CRLF is translated to LF on read, and the negative arm's restore would then
    # write the generator's CRLF files back as LF: a tested file silently rewritten
    # in a different convention. (Measured the hard way: the first run of this
    # oracle left all five themes at 0 CRLF / 730 bare LF.)
    with io.open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def strip_comments(css):
    return re.sub(r"/\*[\s\S]*?\*/", "", css)


def tokens_for(index, css):
    """The `:root[data-theme='theme-N']` custom properties, as a dict."""
    root = re.search(r":root\[data-theme='theme-%d'\]\s*\{([^}]*)\}" % index, strip_comments(css))
    if not root:
        raise SystemExit("theme-%d: the :root[data-theme] block was not found" % index)
    out = {}
    for decl in root.group(1).split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            key = key.strip()
            if key.startswith("--"):
                out[key] = value.strip()
    return out


def rule_for(css, index, selector, pseudo=""):
    """The declarations of one rule, as text (empty when the rule is absent)."""
    body = strip_comments(css)
    pattern = r":root\[data-theme='theme-%d'\]\s*\.%s%s\s*\{([^}]*)\}" % (
        index, re.escape(selector), re.escape(pseudo))
    found = re.search(pattern, body)
    return found.group(1) if found else ""


def resting_border(css, index):
    body = rule_for(css, index, "theme-button")
    m = re.search(r"border(?:-color)?\s*:\s*([^;]+);", body)
    return m.group(1).strip() if m else ""


def hover_border(css, index):
    body = rule_for(css, index, "theme-button", ":hover")
    m = re.search(r"border-color\s*:\s*([^;]+);", body)
    return m.group(1).strip() if m else ""


def resolve_colour(spec, tok):
    """`var(--x)` -> the token's value; a literal passes through."""
    m = re.search(r"var\((--[a-z0-9-]+)", spec)
    if m:
        return m.group(1), tok.get(m.group(1))
    return None, spec


# ---------------------------------------------------------------- the claims
def claim_uses_token(files):
    problems = []
    for i, path in enumerate(files, start=1):
        css = read(path)
        spec = resting_border(css, i)
        if not spec:
            problems.append("theme-%d: no border on .theme-button" % i)
            continue
        name, _ = resolve_colour(spec, tokens_for(i, css))
        if name != "--accent-line":
            problems.append("theme-%d: resting border is %s (expected var(--accent-line))" % (i, spec))
    if problems:
        return False, " | ".join(problems)
    return True, "all five themes paint the resting border from var(--accent-line)"


def claim_contrast(files):
    rows, problems = [], []
    for i, path in enumerate(files, start=1):
        css = read(path)
        tok = tokens_for(i, css)
        slab = parse_colour(tok["--bg-slab"])
        fill = over(parse_colour(tok["--accent-soft"]), slab[:3])
        _, border_spec = resolve_colour(resting_border(css, i), tok)
        border = over(parse_colour(border_spec), fill)
        ratio = contrast(border, fill)
        rows.append((i, ratio))
        if ratio < MIN_RATIO:
            problems.append("theme-%d: %.2f:1" % (i, ratio))
    detail = " | ".join("theme-%d %.2f:1" % (i, r) for i, r in rows)
    if problems:
        return False, "below %.1f:1 -> %s (all: %s)" % (MIN_RATIO, ", ".join(problems), detail)
    return True, "worst %.2f:1 (needs %.1f) -- %s" % (min(r for _, r in rows), MIN_RATIO, detail)


def claim_hover(files):
    problems = []
    for i, path in enumerate(files, start=1):
        css = read(path)
        tok = tokens_for(i, css)
        slab = parse_colour(tok["--bg-slab"])
        fill = over(parse_colour(tok["--accent-soft"]), slab[:3])

        def ratio_of(spec):
            _, value = resolve_colour(spec, tok)
            return contrast(over(parse_colour(value), fill), fill)

        rest = ratio_of(resting_border(css, i))
        hover = ratio_of(hover_border(css, i))
        if hover + 0.05 < rest:
            problems.append("theme-%d: hover %.2f:1 < resting %.2f:1" % (i, hover, rest))
    if problems:
        return False, "hover is weaker than resting -- " + " | ".join(problems)
    return True, "hover is at least as visible as the resting border in all five"


def run(files, label):
    rows = [
        ("C1", "the rule USES the derived token", claim_uses_token(files)),
        ("C2", "the border reaches 3:1 against its own fill", claim_contrast(files)),
        ("C3", "hover is not weaker than resting", claim_hover(files)),
    ]
    failed = 0
    print(label)
    for key, what, (ok, detail) in rows:
        print("  %s %s %-46s %s" % ("ok  " if ok else "FAIL", key, what, detail))
        if not ok:
            failed += 1
    print("")
    print("%d check(s), %d failed" % (len(rows), failed))
    print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
    return failed


# ---------------------------------------------------------------- the mutation
def restore_defect(css):
    """Put the shipped `var(--line)` hairline back on the button."""
    out = re.sub(r"(\.theme-button\s*\{\s*\n\s*border:\s*1px solid )var\(--accent-line\)",
                 r"\1var(--line)", css)
    out = out.replace("border-color: var(--accent); }", "border-color: var(--line-strong); }")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="is the theme button's border visible?")
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    if not args.neg_arm:
        print("THEME-BUTTON CONTRAST ORACLE -- PRISTINE")
        return 0 if run(THEMES, "") == 0 else 1

    original = {p: read(p) for p in THEMES}
    print("THEME-BUTTON CONTRAST ORACLE -- CONTROL")
    ctrl = run(THEMES, "  CONTROL (the files as they stand) must be GREEN")
    print("")

    mutated = 0
    try:
        for path in THEMES:
            broken = restore_defect(original[path])
            if broken == original[path]:
                print("  MUTATION DID NOT APPLY to %s -- the anchor is spent" % path)
                return 1
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(broken)
            mutated += 1
        mut = run(THEMES, "  M1 the shipped hairline restored (border: var(--line)) must be RED")
    finally:
        for path, text in original.items():
            with io.open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)

    ok = (ctrl == 0 and mut > 0)
    print("")
    print("NEG-ARM VERDICT: %s -- control %s, mutant %s (%d file(s) mutated, all restored)"
          % ("PASS" if ok else "FAIL",
             "GREEN" if ctrl == 0 else "RED",
             "RED" if mut > 0 else "GREEN (INERT MUTANT)", mutated))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
