"""THE SKIN+STRIP GATE (owner, 2026-10-09).

THE DEFECT IT DEFENDS AGAINST, MEASURED BEFORE THE FIX: with a skin recorded on
`document.body` (`skin-host.js:304` sets `data-skin`, and only UNMOUNTING the
skin removes it at `:325`), `skin-layout.css` stripped the slab with
`body[data-skin] .panel { background: none }` while
`body[data-surface="strip"] #skin { display: none !important }` hid the one
element that was supposed to replace it. On the strip that left NOTHING to
paint, and the window is WS_EX_LAYERED, so the compositor's default showed
through: a 100% white strip. `body[data-skin] .captions` was `display:none
!important` too, so the captions went with it.

THE INVARIANT THIS GATE DEFENDS: while a skin is recorded, the STRIP surface must
still paint its slab and still show its live captions. A skin mounts on the
panel surface only; `data-skin` survives a surface switch, so every skin rule
that removes paint has to say WHICH surface it applies to.

GREEN  no `body[data-skin]` rule without a `[data-surface="panel"]` scope either
       strips `.panel`'s background or hides `.captions`.
RED    unscoped versions of those two rules exist -- the copy of the file as it
       was before 2026-10-09.
"""

import io
import os
import re
import shutil
import sys
import tempfile

CSS = os.path.join("H:\\sotto", "app", "panel", "skin-layout.css")
PANEL_SCOPE = '[data-surface="panel"]'

# The two declarations that took the strip's paint away. Each is the whole
# defect, so the gate names them separately instead of counting rules.
BAD = {
    ".panel": re.compile(r"background\s*:\s*none\b"),
    ".captions": re.compile(r"display\s*:\s*none\b"),
}


def rules(css):
    """Top-level rules with comments stripped (this file's comments quote CSS).
    Yields (selectors, declarations)."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    out = []
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append((sel, css[j + 1:k - 1]))
        i = k
    return out


def offenders(css):
    """A rule is an offender when it is skin-scoped, has NO surface scope, and
    removes paint from `.panel` or visibility from `.captions`."""
    bad = []
    for sel, decls in rules(css):
        if "data-skin" not in sel:
            continue
        if PANEL_SCOPE in sel:
            continue
        targets = []
        for name, pat in BAD.items():
            if re.search(re.escape(name) + r"\b", sel) and pat.search(decls):
                targets.append(name)
        if targets:
            bad.append((sel.split("\n")[0][:70], ",".join(targets)))
    return bad


def main():
    neg = "--neg" in sys.argv
    target, tmp = CSS, None
    if neg:
        tmp = tempfile.mkdtemp(prefix="skin-strip-neg-")
        target = os.path.join(tmp, "skin-layout.css")
        with io.open(CSS, encoding="utf-8") as f:
            css = f.read()
        # THE CONTROL: put the strip-scoped rules back to how they shipped.
        broken = css.replace('[data-skin][data-surface="panel"]', "[data-skin]")
        broken = broken.replace('[data-skin][data-surface="panel"]', "[data-skin]")
        broken = re.sub(r'body\[data-skin\]\[data-surface="panel"\]', r'body[data-skin]',
                        broken)
        if broken == css:
            print("NEG ARM COULD NOT BREAK THE COPY -- rewrite the control.")
            return 1
        with io.open(target, "w", encoding="utf-8") as f:
            f.write(broken)

    try:
        with io.open(target, encoding="utf-8") as f:
            css = f.read()
        bad = offenders(css)
        print("POPULATION=%s" % target)
        for sel, what in bad:
            print("  OFFENDER  %-58s removes paint from %s" % (sel, what))
        print("OFFENDERS=%d" % len(bad))
        if neg:
            if not bad:
                print("RED ARM STAYED GREEN -- the instrument cannot say NO.")
                return 1
            print("RED AS EXPECTED=True -> the strip would be white again")
            return 0
        if bad:
            print("VERDICT: RED - a skin can still blank the strip surface")
            return 1
        print("VERDICT: GREEN - the strip keeps its slab and its captions "
              "with a skin recorded")
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
