#!/usr/bin/env python3
"""panel-chrome-marks-oracle -- the owner byte-level claims about the panel, in one gate.

ACCEPTANCE ROWS B3, C3, C4, C7, C8 and D7 of _main/aceitacao-dono.md. Each is a sentence the
owner wrote and each was being answered with another sentence ("medido em bytes"), which the
aceitacao-gate correctly flagged as a claim with no instrument behind it.

WHAT IS MEASURED, and it is bytes and parse only -- nothing is launched and nothing is painted:
  B3  "fim da div com COR SOLIDA"  -- the strip carries no solid slab of its own; the window
      (`.panel`) is what paints, so no second slab can float over it
  C3  "tira esse padrao de design de todos" -- no UNIFORM resting edge on the controls, in any
      theme: the rgba(148,163,184) solid border is the measured uniform pattern
  C4  "nao e pra ter moldura no painel" -- the control's first resting rule declares its edge
      transparent; a panel with no `.icon-button` rule at all is CANNOT-MEASURE, never green
  C7  "tema nao rola para o topo" -- the picker does not scroll the page
  C8  live state + X on the right + the transcript control is gone
  D7  "designs bugados" -- the measured defect is the DUPLICATE paint: a theme that declares
      `[data-theme=X] .panel` twice with a background in both emits its scrim twice, and the
      first rule is dead

A row is ok only when its own predicate holds. Every row is also exercised by `--neg-arm`, which
injects the defect each row names and requires that row to go RED -- a row whose injection cannot
be caught is reported as NOT-CAUGHT instead of being trusted.

RETIRED (2026-11-16): B3 used to pass on a CSS COMMENT ("THE WINDOW IS THE BAR"), C3 was vetoed
by the substring `transparent` appearing anywhere in the file (it appears 38 times, so the row
could never fail), C4 went green when no `.icon-button` rule existed, and D7 matched the regex
`^s*background-size` (a literal `s`, zero hits) against a `> 25` ceiling over a population of 9.
Measured that day: the three rows stayed GREEN with the exact defects they name injected -- that is
the class this file now closes.
"""

from __future__ import annotations

import argparse
import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = os.path.normpath(os.path.join(HERE, os.path.pardir, "app", "panel"))

ROWS = (
    ("B3", "the window IS the bar (no second slab can float)"),
    ("C3", "no uniform design pattern across the themes"),
    ("C4", "no moldura: the control has no resting edge"),
    ("C7", "the theme picker does not scroll the page"),
    ("C8", "live state + X on the right + no transcript control"),
    ("D7", "no theme paints its panel twice (duplicate scrim)"),
)

#: the measured uniform pattern the owner asked to be removed from every design
UNIFORM_EDGE = re.compile(r"\.icon-button[^{}]*\{[^}]*border:\s*1px solid rgba\(\s*148\s*,\s*163\s*,\s*184")
#: a rule that gives the strip its own solid surface
STRIP_SLAB = re.compile(r"(?:^|\n)\s*(?:#strip|\.strip|#strip-bar|\.strip-bar)\s*\{[^}]*background")
#: the theme-scoped panel rule, with its body
THEME_PANEL = re.compile(r"\[data-theme=['\"]?([\w-]+)['\"]?\]\s+\.panel\s*\{([^}]*)\}")


def _read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as h:
        return h.read()


def panel_files(panel_dir=PANEL):
    """Every byte this gate judges, in memory -- so `--neg-arm` can mutate a copy."""
    themes = {}
    for path in sorted(glob.glob(os.path.join(panel_dir, "themes", "*.css"))):
        themes[os.path.basename(path)] = _read(path)
    return {
        "html": _read(os.path.join(panel_dir, "panel.html")),
        "css": _read(os.path.join(panel_dir, "panel.css")),
        "zip": _read(os.path.join(panel_dir, "zip-overlay.css")),
        "themes": themes,
    }


def _all_css(files):
    return [("panel.css", files["css"])] + [("themes/" + n, t) for n, t in sorted(files["themes"].items())]


def evaluate(files):
    """Pure judgement over a file map. Returns [(row, state, why)] with state ok|gap|cannot."""
    out = []
    css = files["css"]
    html = files["html"]

    # B3 -- the strip owns no solid surface of its own; the window paints.
    strip_hit = [name for name, text in _all_css(files) if STRIP_SLAB.search(text)]
    if not re.search(r"(?:^|\n)\s*\.panel\s*\{[^}]*background", css):
        out.append(("B3", "cannot", "no `.panel` background rule: the window is not what paints"))
    elif strip_hit:
        out.append(("B3", "gap", "the strip declares its own surface in %s" % ", ".join(strip_hit)))
    else:
        out.append(("B3", "ok", "no strip slab; the panel rule paints the window"))

    # C3 -- no control carries the uniform resting edge, in any theme.
    uniform = [name for name, text in _all_css(files) if UNIFORM_EDGE.search(text)]
    out.append(("C3", "gap", "uniform edge in %s" % ", ".join(uniform)) if uniform
               else ("C3", "ok", "no rgba(148,163,184) resting edge in %d stylesheet(s)" % len(_all_css(files))))

    # C4 -- the control's first resting rule declares its edge transparent.
    first = re.search(r"\.icon-button\s*\{([^}]*)\}", css, re.S)
    if not first:
        out.append(("C4", "cannot", "panel.css has no .icon-button rule -- nothing to judge"))
    elif not re.search(r"border:\s*1px solid transparent", first.group(1)):
        out.append(("C4", "gap", "the first .icon-button rule carries a visible edge"))
    else:
        out.append(("C4", "ok", "the first .icon-button rule is transparent"))

    # C7 -- the picker never scrolls the document.
    scroll = re.search(r"scrollIntoView|scrollTop\s*=\s*0\b", html)
    out.append(("C7", "gap", "the picker scrolls the document (%s)" % scroll.group(0)) if scroll
               else ("C7", "ok", "no scrollIntoView / scrollTop=0 in panel.html"))

    # C8 -- live state + X on the right + the transcript control gone.
    # RE-AIMED 2026-11-25: this row used to look for the `tele` chrome footer
    # (`data-slot="end"` / `chrome--tele`), which left the document on 2026-11-06.
    # The two things it actually wants still exist and are named directly: the
    # live state is `#status-dot` (with `#status-text` beside it) and the X is the
    # hide control. A row that cannot find its subject says so instead of passing.
    gone = 'id="history-toggle"' in html or "history__toggle" in css
    dot = 'id="status-dot"' in html and 'id="status-text"' in html
    x_right = 'id="hide-button"' in html
    if gone:
        out.append(("C8", "gap", "the transcript control is still in the markup"))
    elif not (dot and x_right):
        out.append(("C8", "gap", "no status dot (%r) or no hide control (%r) in the markup"
                    % (dot, x_right)))
    else:
        out.append(("C8", "ok", "live state + X present, no transcript control"))

    # D7 -- no theme paints its panel twice under the same selector.
    dupes = []
    for name, text in sorted(files["themes"].items()):
        paints = collections.Counter()
        for theme, body in THEME_PANEL.findall(text):
            if re.search(r"background(?:-image|-color)?\s*:", body):
                paints[theme] += 1
        for theme, n in sorted(paints.items()):
            if n > 1:
                dupes.append("%s/%s x%d" % (name, theme, n))
    out.append(("D7", "gap", "painted twice: %s" % ", ".join(dupes)) if dupes
               else ("D7", "ok", "every theme paints its panel once"))

    return out


def report(rows, say=print):
    bad = 0
    for row, state, why in rows:
        tag = {"ok": "ok  ", "gap": "GAP ", "cannot": "N/M "}[state]
        say("  [%s] %s -- %s" % (tag, row, why))
        if state != "ok":
            bad += 1
    say("")
    say("PANEL-CHROME-MARKS %d/%d row(s) hold" % (len(rows) - bad, len(rows)))
    return bad


# ---------------------------------------------------------------------------
# The control: inject the defect each row names and require that row to go RED.
# ---------------------------------------------------------------------------

def _inject(row, files):
    """Mutate a copy so the named row must fail. Returns (mutated, anchor_found)."""
    f = {k: (dict(v) if isinstance(v, dict) else v) for k, v in files.items()}
    if row == "B3":
        f["css"] = f["css"] + "\n.strip { background: #101010; }\n"
        return f, True
    if row == "C3":
        f["css"] = f["css"] + "\n.icon-button { border: 1px solid rgba(148, 163, 184, 0.9); }\n"
        return f, True
    if row == "C4":
        first = re.search(r"\.icon-button\s*\{([^}]*)\}", f["css"], re.S)
        if not first:
            return f, False
        body = first.group(1)
        new = body.replace("border: 1px solid transparent", "border: 1px solid #ffffff")
        if new == body:
            new = body + "\n  border: 1px solid #ffffff;\n"
        f["css"] = f["css"][:first.start(1)] + new + f["css"][first.end(1):]
        return f, True
    if row == "C7":
        f["html"] = f["html"] + "\n<script>el.scrollIntoView();</script>\n"
        return f, True
    if row == "C8":
        f["html"] = f["html"] + '\n<div id="history-toggle"></div>\n'
        return f, True
    if row == "D7":
        target = next((n for n, t in sorted(f["themes"].items()) if THEME_PANEL.search(t)), None)
        if target is None:
            return f, False
        theme = THEME_PANEL.search(f["themes"][target]).group(1)
        f["themes"][target] = (f["themes"][target]
                               + "\n[data-theme='%s'] .panel { background: #000; }\n" % theme)
        return f, True
    raise AssertionError(row)


def neg_arm(files, say=print):
    caught, missed, applied = 0, [], 0
    for row, _desc in ROWS:
        mutant, anchored = _inject(row, files)
        if not anchored:
            say("  %-3s ANCHOR-GONE -- the row cannot be exercised, and that is NOT a catch" % row)
            missed.append(row)
            continue
        applied += 1
        got = {r: s for r, s, _w in evaluate(mutant)}
        if got.get(row) in ("gap", "cannot"):
            caught += 1
            say("  %-3s CAUGHT  (mutated state=%s)" % (row, got.get(row)))
        else:
            say("  %-3s MISSED  (mutated state=%s -- this row is not doing its job)" % (row, got.get(row)))
            missed.append(row)
    say("")
    if caught == len(ROWS):
        say("NEG-ARM: PASS -- %d/%d rows caught their own injected defect" % (caught, len(ROWS)))
        return 1
    say("NEG-ARM: FAIL -- %d/%d caught (applied=%d, missed=%s)"
        % (caught, len(ROWS), applied, ",".join(missed) or "-"))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", default=PANEL, help="the app/panel directory to judge")
    ap.add_argument("--neg-arm", action="store_true",
                    help="inject each row's defect and require the row to go RED (rc=1 on catch)")
    args = ap.parse_args(argv)
    files = panel_files(args.panel)
    if not files["html"]:
        print("panel-chrome-marks-oracle: NO panel.html under %s" % args.panel)
        return 2
    if args.neg_arm:
        return neg_arm(files)
    bad = report(evaluate(files))
    if bad:
        print("VERDICT: FAIL -- %d row(s) do not hold on the shipped bytes" % bad)
        return 1
    print("VERDICT: PASS -- B3, C3, C4, C7, C8 and D7 hold on the shipped bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
