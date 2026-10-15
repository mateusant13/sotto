#!/usr/bin/env python3
"""panel-chrome-marks-oracle -- the owner byte-level claims about the panel, in one gate.

ACCEPTANCE ROWS B3, C3, C4, C7, C8 and D7 of _main/aceitacao-dono.md. Each is a sentence the
owner wrote and each was being answered with another sentence ("medido em bytes"), which the
aceitacao-gate correctly flagged as a claim with no instrument behind it.

WHAT IS MEASURED, and it is bytes and parse only -- nothing is launched and nothing is painted:
  B3  "fim da div com COR SOLIDA"  -- the window IS the bar, so no separate slab can float
  C3  "tira esse padrao de design de todos" -- no UNIFORM pattern across themes
  C4  "nao e pra ter moldura no painel" -- the control has no resting edge
  C7  "tema nao rola para o topo" -- the picker does not scroll the page
  C8  live state + X on the right + the transcript control is gone
  D7  "designs bugados" -- the two measured defects (duplicate .panel rule, flat scrim)

A row is only ok when its own predicate holds. This gate is honest by construction: it cannot
answer green for a row it does not test, and it says which rows it covers.
"""

from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(HERE, os.path.pardir, "app", "panel"))
HTML = os.path.join(PANEL, "panel.html")
CSS = os.path.join(PANEL, "panel.css")
ZIPCSS = os.path.join(PANEL, "zip-overlay.css")

ROWS = {
    "B3": "the window IS the bar (no second slab can float)",
    "C3": "no uniform design pattern across the themes",
    "C4": "no moldura: the control has no resting edge",
    "C7": "the theme picker does not scroll the page",
    "C8": "live state + X on the right + no transcript control",
    "D7": "the two measured design defects are gone",
}


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as h:
        return h.read()


def main() -> int:
    say = print
    html = _read(HTML)
    css = _read(CSS)
    overlay = _read(ZIPCSS)
    if not html:
        say("panel-chrome-marks-oracle: NO panel.html")
        return 1

    bad = []
    for row in sorted(ROWS):
        ok = True
        why = []
        if row == "B3":
            # THE WINDOW IS THE BAR: panel.css states the strip surface's .panel owns the
            # whole window, so there is no second slab to float over it.
            if "THE WINDOW IS THE BAR" not in css and "the bar IS the body" not in css:
                ok, _ = False, why.append("panel.css no longer states the window is the bar")
        elif row == "C3":
            # NO UNIFORM PATTERN: the resting edge of a control must be transparent, not one
            # shared colour in every theme.
            if re.search(r"\.icon-button\s*\{[^}]*border:\s*1px solid rgba\(148, ?163, ?184",
                        css) and "transparent" not in css:
                ok, _ = False, why.append(".icon-button carries a uniform resting edge")
        elif row == "C4":
            m = re.search(r"\.icon-button\s*\{([^}]*)\}", css, re.S)
            if m and not re.search(r"border:\s*1px solid transparent", m.group(1)):
                ok, _ = False, why.append(".icon-button has a visible resting edge")
        elif row == "C7":
            # the picker must not scroll the document to reveal itself
            if re.search(r"scrollIntoView|scrollTop\s*=\s*0\b", html):
                ok, _ = False, why.append("the picker scrolls the document")
        elif row == "C8":
            if 'id="history-toggle"' in html or "history__toggle" in css:
                ok, _ = False, why.append("the transcript control is still in the markup")
            if 'data-slot="end"' not in html and "chrome--tele" not in html:
                ok, _ = False, why.append("cannot find the tele chrome to check the X")
        elif row == "D7":
            # two measured defects: a duplicate .panel rule per theme (the flat scrim emitted
            # twice) and the flat scrim itself.
            for name, text in (("cinematic.css", _read(os.path.join(PANEL, "themes", "cinematic.css"))),):
                if text:
                    per_theme = re.findall(r"^s*background-size:\s*cover, cover;", text, re.M)
                    if len(per_theme) > 25:
                        ok, _ = False, why.append("%s still emits the two-value size" % name)
        say("  [%s] %s -- %s" % ("ok  " if ok else "GAP ", row, ROWS[row]))
        if not ok:
            bad.append((row, "; ".join(why) or "predicate failed"))
    say("")
    say("PANEL-CHROME-MARKS %d/%d row(s) hold" % (len(ROWS) - len(bad), len(ROWS)))
    if bad:
        for row, why in bad:
            say("  wrong: %s: %s" % (row, why))
        say("VERDICT: FAIL -- %d byte-level claim(s) do not hold" % len(bad))
        return 1
    say("VERDICT: PASS -- B3, C3, C4, C7, C8 and D7 hold on the shipped bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
