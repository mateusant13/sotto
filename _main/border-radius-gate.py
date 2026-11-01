"""GATE: the panel's borders must be TRANSPARENT and ROUNDED BY THE DESIGN.

THE OWNER, verbatim (2026-10-21):

    *"as bordas de cada design nao tao transparentes, tao cinzas/pretas. assim,
    nao ficam arredondadas pelo design."*

THE DEFECT HAD TWO INDEPENDENT CAUSES, BOTH IN `app/panel/panel.css`, AND NEITHER
IS VISIBLE BY GREPPING A SINGLE RULE:

  1. THE ROOT PAINTED THE CANVAS. The shared `html, body` rule carried the render
     protection's base (`rgba(11,15,20,0.98)`) on BOTH elements. A background on
     the ROOT element PROPAGATES TO THE CANVAS, and the canvas background is
     painted across the whole viewport WITHOUT being clipped by the root's
     `border-radius` (CSS Backgrounds 3: the root's background "extends to cover
     the entire canvas"). So the four corners were an opaque grey/black rectangle
     whatever radius the design asked for - the design's rounding was drawn ON TOP
     of a square plate. The base moved to `body` only; `html` is transparent.
     `body` is an ordinary element, so ITS box IS clipped by ITS radius, and the
     protection is NOT lost - a broken `.panel` still cannot leave the window white.

  2. THE FLOOR WAS A LITERAL. `border-radius: 12px !important` crushed every
     design whose own radius is bigger (GlassCards declares `--radius-lg: 22px`,
     Bubbles 20px, Quotes 18px, Timeline/Gutter 16px). The floor is now
     `max(var(--radius, 14px), 12px)`: the designs that declare less keep the 12px
     floor the earlier ruling asked for, and every other design gets ITS OWN
     radius - which is the whole point of the token.

WHAT THIS GATE IS, AND IS NOT. It judges the FILES: it parses `panel.css` and
asserts the two invariants above hold. It does NOT render anything, it launches
nothing, and it never touches the owner's running app. The RENDERED half - that
the compositor really shows the desktop through the corners - is measured by
`_main/_border-radius-probe.py` (real Chromium, 45 designs, PASS) and by the
running shell, and that half is declared NOT MEASURED here on purpose.

WHY A GATE AT ALL, AND WHY THIS ONE. The owner's complaint is one he has made
repeatedly (*"ainda to vendo as bordas"*), and AGENTS rule 6 says a gate that
judges files ENTERS the battery: a negative arm that is not in the battery is a
mutant nobody ever looks at again. The rendered probe CANNOT be a battery step
(it LAUNCHES a browser), so this file is the one that can.

THE THREE CLAIMS, AND EACH ONE IS A FACT ABOUT THE PRODUCT, NOT ABOUT THE
TEXT: a rule that breaks any of them is a rule that brings the defect back.

  C1  THE ROOT PAINTS NOTHING. No rule may put a non-transparent background on
      the root element (`html`), directly or through a combined selector list
      (`html, body`). This is the claim that stops the canvas from being painted
      square again.

  C2  THE BASE PAINT IS ON `body`. The render protection must EXIST and it must
      live on the body (the element whose box IS clipped by the radius). Without
      it a broken `.panel` would leave the window white - so "the root paints
      nothing" is only half the fix, and this claim is the other half.

  C3  THE FLOOR IS A `max()`, NOT A LITERAL. Every `!important` radius on the
      panel surface (`html`, `body`, `.panel`) must be the token expression
      `max(var(--radius, ...)`. A literal there crushes the designs again.

HEADLESS BY CONSTRUCTION: no window, no WebView2, no browser, no audio, no
process. It reads two files and prints a verdict.

    python _main\\border-radius-gate.py              -> rc 0 PASS / rc 1 FAIL
    python _main\\border-radius-gate.py --neg-arm    -> rc 1 BY DESIGN
"""

from __future__ import annotations

import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, "app", "panel", "panel.css")

# THE PROTECTION'S BASE. It is the colour the panel paints on, and it is the
# colour that must NEVER be on the root (C1) and must ALWAYS be on the body (C2).
BASE = "rgba(11, 15, 20, 0.98)"

TRANSPARENT = ("transparent", "rgba(0, 0, 0, 0)", "rgba(0,0,0,0)")


def read_css(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def rules(text: str):
    """Every declaration block with its selector list.

    A deliberately small parser: the subject is the CSS this repo writes (no
    nesting beyond `@media`, no strings with braces in the values that matter).
    """
    out = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        selector = " ".join(match.group(1).split())
        body = match.group(2)
        if not selector or not body.strip():
            continue
        # A `@media`/`@supports` prelude is not a selector; keep only the part
        # after the last `}` or the whole thing when there is none.
        selector = selector.split("}")[-1].strip()
        if selector.startswith("@"):
            continue
        parts = [p.strip() for p in selector.split(",") if p.strip()]
        if not parts:
            continue
        out.append((parts, body))
    return out


def declarations(body: str) -> dict:
    """The declarations of a block, lower-cased property names."""
    out = {}
    for chunk in body.split(";"):
        if ":" not in chunk:
            continue
        prop, _, value = chunk.partition(":")
        prop = prop.strip().lower()
        value = " ".join(value.split())
        if prop:
            out[prop] = value
    return out


def compounds_of(selector_part: str):
    """The compounds of a selector, on the DESCENDANT combinator too.

    The split respects `[...]` and `(...)` and quotes, because a descendant
    combinator inside `:has(> body[...])` or inside an attribute value is NOT a
    combinator of THIS selector. Getting this wrong is the difference between
    `html[data-brand] body[data-surface="strip"] .panel` (subject: `.panel`)
    and `html` (subject: the root) - which is the difference between a
    background on the slab and a background on the CANVAS.
    """
    out, buf = [], []
    depth = 0
    quote = None
    for ch in selector_part:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if depth == 0 and ch in ">+~ \t\r\n":
            if buf:
                out.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append("".join(buf))
    return [c for c in out if c]


def subject(selector_part: str):
    """The element the selector part points at: (element_name, last_compound).

    `html:has(> body[data-surface="panel"])` -> ("html", ...); `.panel::before` ->
    (None, ".panel::before"); `html body[data-surface="panel"] .panel` -> (None,
    ".panel").
    """
    compounds = compounds_of(selector_part.strip())
    if not compounds:
        return None, ""
    last = compounds[-1]
    # A pseudo-element hangs off the compound before it: `.panel::before`.
    base = re.sub(r"::[a-zA-Z-]+(\([^)]*\))?$", "", last).strip()
    match = re.match(r"^([a-zA-Z][a-zA-Z0-9-]*)", base)
    element = match.group(1).lower() if match else None
    return element, last.lower()


def background_of(decls: dict):
    for prop in ("background", "background-color"):
        if prop in decls:
            return decls[prop]
    return None


def is_transparent(value) -> bool:
    if value is None:
        return True
    value = value.strip().lower()
    return value in TRANSPARENT or value.startswith("rgba(0, 0, 0, 0)")


def judge(css_text: str) -> list:
    """The claims, checked against a CSS text. Returns a list of failures."""
    failures = []
    text = strip_comments(css_text)
    blocks = rules(text)

    # -- C1: the root paints nothing ------------------------------------------
    for parts, body in blocks:
        decls = declarations(body)
        paint = background_of(decls)
        if paint is None or is_transparent(paint):
            continue
        for part in parts:
            element, _ = subject(part)
            if element == "html":
                failures.append(
                    "C1 the ROOT paints %s (selector `%s`): a background on the "
                    "root PROPAGATES TO THE CANVAS and is not clipped by the "
                    "root's border-radius, so the corners are a square plate"
                    % (paint, part[:90])
                )
                break

    # -- C2: the base paint is on the body -------------------------------------
    on_body = False
    for parts, body in blocks:
        decls = declarations(body)
        paint = background_of(decls)
        if paint is None or is_transparent(paint):
            continue
        for part in parts:
            element, _ = subject(part)
            if element == "body":
                on_body = True
                break
    if not on_body:
        failures.append(
            "C2 the render protection's base (%s) is on NO `body` rule: the root "
            "must paint nothing (C1) AND the body must carry the paint, or a "
            "broken `.panel` leaves the window WHITE" % BASE
        )

    # -- C3: the floor is a max(), not a literal --------------------------------
    for parts, body in blocks:
        decls = declarations(body)
        radius = decls.get("border-radius")
        if not radius or "!important" not in radius.lower():
            continue
        surface = False
        for part in parts:
            element, last = subject(part)
            if element in ("html", "body") or "panel" in last:
                surface = True
                break
        if not surface:
            continue
        if "max(var(--radius" not in radius.lower():
            failures.append(
                "C3 the panel surface's radius is the LITERAL `%s` (selector `%s`): "
                "it must be `max(var(--radius, 14px), 12px)` so every design keeps "
                "ITS OWN rounding and only the 0px designs get the floor"
                % (radius.replace("!important", "").strip(),
                   ", ".join(parts)[:90])
            )

    return failures


# ---------------------------------------------------------------------------
# THE MUTANTS: three real defects, each one a copy of the file with ONE change.
# A mutant that does not change the file is a mutant that proves nothing, so
# each one asserts that its own edit landed.
# ---------------------------------------------------------------------------

def mutant_root_paints(css: str) -> str:
    """THE OLD DEFECT: the base paint back on the root.

    It REPLACES the `background: transparent` of the `html` rule. Prepending a
    second `background` would not do it: in CSS the LAST declaration of a
    property wins, so the root would still be transparent and the mutant would
    prove nothing.
    """
    # RE-ANCORADO EM 2026-10-30: o defeito antigo vivia numa regra `html { background:
    # transparent }` que ja' nao existe -- o `html` deixou de estar na lista `html, body` do
    # `panel.css`. O mutante passou a ACRESCENTAR a regra no FIM do ficheiro, que e' a forma
    # em que o defeito pode voltar (a ultima declaracao da propriedade ganha), e o `judge`
    # le todos os blocos, pelo que a regra acrescentada e' julgada como qualquer outra.
    if re.search(r"(^|[},\s])html\s*(,|\{)", css, flags=re.M) is None:
        pass  # o `html` pode nao aparecer de todo: e' o estado saudavel de hoje
    out = css + "\n\nhtml {\n  background: %s;\n}\n" % BASE
    return out


def mutant_no_base(css: str) -> str:
    """THE HALF-FIX: the root paints nothing AND the body paints nothing."""
    out, n = re.subn(r"background:\s*" + re.escape(BASE) + r"\s*;", "", css, count=1)
    if n == 0:
        raise RuntimeError("the mutant did not find the body's base paint")
    return out


def mutant_literal_floor(css: str) -> str:
    """THE OLD FLOOR: the literal 12px, crushing every design's own radius.

    The pattern carries the PROPERTY NAME, on purpose: the file's COMMENT
    quotes the expression too (`max(var(--radius, 14px), 12px)` is written out
    in the note that explains it), and a mutant that edits a comment proves
    nothing at all.
    """
    out, n = re.subn(
        r"border-radius:\s*max\(var\(--radius,\s*14px\),\s*12px\)",
        "border-radius: 12px",
        css,
        count=1,
    )
    if n == 0:
        raise RuntimeError("the mutant did not find the `max(var(--radius...)` floor")
    return out


MUTANTS = [
    ("M1 the base paint is back on the ROOT (the canvas is painted square)",
     mutant_root_paints, "C1"),
    ("M2 the base paint is on NEITHER the root nor the body (a white window)",
     mutant_no_base, "C2"),
    ("M3 the floor is the LITERAL 12px again (every design's radius is crushed)",
     mutant_literal_floor, "C3"),
]


def run_neg_arm() -> int:
    """Each mutant must make the gate go RED. rc=1 BY DESIGN."""
    css = read_css(CSS)
    print("BORDER-RADIUS GATE -- NEGATIVE ARM (three mutants, each a broken copy)")
    print("  file: %s" % CSS)
    failures = 0
    for name, mutate, claim in MUTANTS:
        try:
            broken = mutate(css)
        except RuntimeError as exc:
            print("  FAIL  %s -- the mutant could not be built: %s" % (name, exc))
            failures += 1
            continue
        hits = judge(broken)
        named = [f for f in hits if f.startswith(claim)]
        if named:
            print("  ok    %s" % name)
            print("        the gate says: %s" % named[0][:160])
        else:
            print("  FAIL  %s -- the mutant did NOT make the gate red (%s): %s"
                  % (name, claim, hits[0][:140] if hits else "the gate still passes"))
            failures += 1
    print("")
    if failures:
        print("NEG-ARM FAIL: %d mutant(s) were not caught" % failures)
        print("VERDICT: FAIL")
        return 1
    print("NEG-ARM PASS: %d mutant(s), every one caught" % len(MUTANTS))
    print("VERDICT: FAIL (rc=1 BY DESIGN -- the negative arm is a control)")
    return 1


def main(argv) -> int:
    if "--neg-arm" in argv:
        return run_neg_arm()
    if "--css" in argv:
        path = argv[argv.index("--css") + 1]
    else:
        path = CSS
    if not os.path.exists(path):
        print("BORDER-RADIUS GATE -- the file is NOT THERE: %s" % path)
        print("VERDICT: FAIL")
        return 1
    css = read_css(path)
    failures = judge(css)
    print("BORDER-RADIUS GATE -- the FILES (no browser, no launch)")
    print("  file: %s" % path)
    print("  %d B" % len(css.encode("utf-8")))
    print("")
    print("  C1 the root paints nothing                     %s"
          % ("ok" if not [f for f in failures if f.startswith("C1")] else "FAIL"))
    print("  C2 the base paint is on the body               %s"
          % ("ok" if not [f for f in failures if f.startswith("C2")] else "FAIL"))
    print("  C3 the floor is a max(), not a literal         %s"
          % ("ok" if not [f for f in failures if f.startswith("C3")] else "FAIL"))
    if failures:
        print("")
        for item in failures:
            print("  FAIL %s" % item)
        print("")
        print("VERDICT: FAIL")
        return 1
    print("")
    print("NOT MEASURED HERE: the compositor's own output. The rendered half is")
    print("`_main/_border-radius-probe.py` (real Chromium, 45 designs) and the")
    print("running shell; this gate only says the FILES still say the right thing.")
    print("")
    print("VERDICT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
