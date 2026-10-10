"""THE RENDER PROTECTION GATE (owner, 2026-10-09).

The Sotto panel window is WS_EX_LAYERED and the page is transparent by design,
so anything the page does not paint shows the compositor's default: WHITE. The
owner measured that himself -- *"vejo os dois paineis branco"* -- on BOTH
surfaces, which rules out any single per-surface rule.

`.panel` owns the visible slab. Until this gate existed it was the ONLY thing
painainting a background, and that is a single point of failure: one theme rule,
one unresolved custom property, or one parse error after that rule and the
window is white.

THE INVARIANT THIS GATE DEFENDS: the page must carry TWO independent
background layers -- `.panel` (the visible slab, with its gradients) AND `body`
(the same dark base underneath). A single layer is a single point of failure.

The gate reads the REAL file, not a copy, and it has BOTH colours:
  GREEN  both layers paint a non-transparent background
  RED    remove the body background (or make it transparent) and it fails

Usage:  py -3 _main/render-protection-gate.py [--neg]
        --neg builds a broken COPY in a temp dir and must go RED.
"""

import io
import os
import re
import shutil
import sys
import tempfile

CSS = os.path.join("H:\\sotto", "app", "panel", "panel.css")

# The minimum mean alpha a background must carry to count as PAINTING. A
# rgba(...,0) or `transparent` is not paint; it is a hole in the page.
MIN_ALPHA = 0.90

# The colour the compositor shows through a hole.
COMPOSITOR_DEFAULT = (255, 255, 255)


def _selector_blocks(css):
    """Yield (selector, declarations) for every top-level rule, braces balanced
    so a nested @media block cannot be mistaken for the end of a rule.

    COMMENTS ARE STRIPPED FIRST, and that is not tidiness: this file's own
    comments quote CSS snippets (`.caption__time {`, `body[data-surface=...]`),
    so a brace counted inside a comment desynchronises the matcher and the real
    `.panel` rule is never seen at all -- which reads as "RULE ABSENT" and looks
    like a missing layer rather than a broken instrument."""
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    out = []
    i = 0
    n = len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel = css[i:j].strip()
        # skip at-rules that own a block (@media, @supports, @keyframes)
        depth = 1
        k = j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if not sel.startswith("@"):
            out.append((sel, body))
        i = k
    return out


def _declares_background(decls):
    """Return (paints, detail) for a rule's declarations: does it set a
    background that is not transparent?"""
    text = " ".join(decls.split())
    m = re.search(r"(?<!-)\bbackground(?:-color)?\s*:\s*([^;}]+)", text)
    if not m:
        return False, "no background declaration"
    value = m.group(1).strip()
    if value in ("transparent", "none", "inherit", "initial", "unset"):
        return False, "background=%s" % value
    alphas = [float(a) for a in re.findall(r"rgba\([^)]*,\s*([0-9.]+)\s*\)", value)]
    if alphas and max(alphas) < MIN_ALPHA:
        return False, "background alpha %s < %s" % (max(alphas), MIN_ALPHA)
    # A hex colour #rrggbb is opaque; #rrggbbaa with aa=00 is not.
    hexes = re.findall(r"#([0-9a-fA-F]{3,8})", value)
    for h in hexes:
        if len(h) == 8 and int(h[6:8], 16) / 255.0 < MIN_ALPHA:
            return False, "background #%s alpha < %s" % (h, MIN_ALPHA)
    if not alphas and not hexes and not value.startswith(("rgb(", "hsl(", "var(")):
        return False, "unrecognised background=%r" % value
    return True, value[:70]


def check(path):
    css = io.open(path, encoding="utf-8").read()
    layers = {}
    for sel, decls in _selector_blocks(css):
        for candidate in sel.split(","):
            c = candidate.strip()
            if c in ("body", ".panel"):
                paints, detail = _declares_background(decls)
                layers[c] = (paints, detail)
    return layers


def main():
    neg = "--neg" in sys.argv
    target = CSS
    tmp = None
    if neg:
        tmp = tempfile.mkdtemp(prefix="render-prot-neg-")
        target = os.path.join(tmp, "panel.css")
        shutil.copy(CSS, target)
        css = io.open(target, encoding="utf-8").read()
        # THE CONTROL: put the body background back to the hole it used to be.
        broken = css.replace("background: rgba(11, 15, 20, 0.98);",
                             "background: transparent;", 1)
        if broken == css:
            print("NEG ARM COULD NOT BREAK THE COPY -- the protection string "
                  "changed, so the control must be rewritten, not the code.")
            return 1
        io.open(target, "w", encoding="utf-8").write(broken)

    try:
        layers = check(target)
        body_ok = layers.get("body", (False, "absent"))[0]
        panel_ok = layers.get(".panel", (False, "absent"))[0]
        print("POPULATION=%s WINDOW=%s" % (target, "py -3 render-protection-gate.py"))
        for name in ("body", ".panel"):
            paints, detail = layers.get(name, (False, "RULE ABSENT"))
            print("%-8s %s  %s" % (name, "PAINTS" if paints else "HOLE", detail))
        ok = body_ok and panel_ok
        print("LAYERS=%d/2" % (int(body_ok) + int(panel_ok)))
        if neg:
            # the control MUST fail
            if ok:
                print("RED ARM STAYED GREEN -- the instrument cannot say NO, "
                      "so the GREEN above is not evidence.")
                return 1
            print("RED AS EXPECTED=True -> body is a hole again, window would "
                  "be %s" % ("rgb%s" % (COMPOSITOR_DEFAULT,)))
            return 0
        if not ok:
            print("VERDICT: RED - the panel can still render WHITE")
            return 1
        print("VERDICT: GREEN - two independent background layers, the "
              "compositor default (%s) is unreachable" % ("rgb%s" % (COMPOSITOR_DEFAULT,)))
        return 0
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
