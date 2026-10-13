#!/usr/bin/env python3
"""ZIPC-DESIGNS ORACLE -- the gate for the TEN panel designs of the third zip.

WHAT IT DECIDES, and it is the owner's own sentence:
  *"eu quero que, cada tema encontrado dentro dos .zip, fiquem com o design
  IGUAL, e so muda a posicao dos botoes."*
plus defect D2 of the audit: a theme that ignores the tuning dialog is a defect.

WHY IT EXISTS. The audit measured the ten designs of 'zipc-panels.css' as ONE
skeleton recoloured ten times (D1) and 0/17 tune tokens consumed (D2). The
existing gates could not see either: '_main/scope-leak-oracle.js' checks that
every selector is SCOPED (it was, and it stayed so while all ten were the same
design), and '_main/strip-float-oracle.js' Z5 pins a LITERAL 'font-size: Npx' --
which is exactly the form the D2 fix has to remove. A defect with no gate comes
back, so this is the gate.

NOTHING IS LAUNCHED. No browser, no shell, no worker, no WebView2. This parses
bytes and, in --neg-arm, writes mutant COPIES under $TMPDIR.

Usage:
  py -3 _main/zipc-designs-oracle.py
  py -3 _main/zipc-designs-oracle.py --file <path>
  py -3 _main/zipc-designs-oracle.py --neg-arm
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRODUCT = os.path.join(ROOT, "app", "panel", "themes", "zipc-panels.css")
GENERATOR = os.path.join(HERE, "_design-lane", "gen_zipc.py")

THEMES = ["GlassCards", "Hairline", "Paper", "Quotes", "Ledger",
          "Feed", "Bubbles", "Timeline", "Chips", "Gutter"]

# The 17 tokens 'theme-tune.js' can write (its FIELDS table, 17 entries).
TUNE_TOKENS = [
    "--font-sans", "--size-caption", "--leading-caption", "--weight-caption",
    "--tracking-caption", "--caption-upper", "--size-closed", "--leading-closed",
    "--weight-closed", "--accent", "--text-secondary", "--text-provisional",
    "--bg-slab", "--bg-slab-strong", "--radius-lg", "--motion-in", "--type-step",
]

# A property is STRUCTURAL when its VALUE changes the shape of the design rather
# than only its colour. 'background-image' is here because a repeating-gradient
# IS the shape (that is the ruled page of design 03); 'background' and
# 'border-color' are NOT, because they carry the palette and would let a pure
# recolour look structural.
STRUCTURAL_VALUE_PROPS = {
    "display", "grid-template-columns", "grid-template-rows", "grid-area",
    "grid-column", "grid-row", "flex-direction", "align-self", "align-items",
    "justify-content", "border-radius", "backdrop-filter", "content",
    "counter-increment", "counter-reset", "position", "order", "text-align",
    "background-image", "background-repeat", "white-space", "overflow",
    "flex-wrap", "font-style", "animation", "mask-image", "mix-blend-mode",
    "list-style", "box-shadow", "transform", "left", "top", "bottom", "right",
    "width", "height", "min-width", "max-width", "max-height", "padding",
    "margin", "column-gap", "row-gap", "gap", "vertical-align", "pointer-events",
}

# Thresholds, set from a MEASURED pair of files (the shipped defect and the ten
# designs), never from taste. Measured 2026-10-12:
#   legacy  min pairwise diff = 0    fingerprint 56-57   distinct seqs = 1
#   designs min pairwise diff = 43   fingerprint 154-178 distinct seqs = 10
MIN_PAIR_DIFF = 20
MIN_FP_SIZE = 100

# ARM C -- one identity mark per design, read out of that design's OWN component
# in the zip. Every mark is searched INSIDE the design's own blocks, so a mark
# in the wrong theme cannot satisfy it.
IDENTITY_MARKS = [
    ("GlassCards", r"backdrop-filter:\s*blur\(20px\)",
     "the frosted glass that gives the design its name (PanelSetA.tsx:27-31)"),
    ("GlassCards", r"border-radius:\s*50%",
     "the round initials avatar (PanelSetA.tsx:71-76)"),
    ("Hairline", r"grid-template-columns:\s*44px 1fr",
     "the 44px time gutter of grid-cols-[44px_1fr] (PanelSetA.tsx:207)"),
    ("Hairline", r"background:\s*none",
     "no surface at all -- near-invisible panel (PanelSetA.tsx:145-146)"),
    ("Paper", r"repeating-linear-gradient\(180deg",
     "the ruled page (PanelSetA.tsx:250-256)"),
    ("Paper", r"content:\s*\"filed\"",
     "the filed stamp on the last row (PanelSetA.tsx:305-311)"),
    ("Quotes", r'content:\s*"\\201C"',
     "the 34px opening quote (PanelSetA.tsx:392-397)"),
    ("Quotes", r"border-left:\s*2px solid",
     "the speaker-coloured left rule (PanelSetA.tsx:385)"),
    ("Ledger", r"grid-template-columns:\s*46px 58px 1fr",
     "the time/voice/transcript ledger columns (PanelSetA.tsx:484)"),
    ("Ledger", r":nth-child\(even\)",
     "the zebra on the even entries (PanelSetA.tsx:496)"),
    ("Feed", r":nth-last-child\(",
     "the recency opacity ramp (PanelSetB.tsx:63-66)"),
    ("Feed", r'content:\s*">"',
     "the caret that opens the live log line (PanelSetB.tsx:84-86)"),
    ("Bubbles", r"border-radius:\s*16px 16px 16px 5px",
     "the chat bubble with its tail corner (PanelSetB.tsx:198-210)"),
    ("Bubbles", r"align-self:\s*flex-(start|end)",
     "the left/right two-voice layout (PanelSetB.tsx:190-196)"),
    ("Timeline", r"linear-gradient\(180deg, transparent",
     "the spine that fades at both ends (PanelSetB.tsx:307-309)"),
    ("Timeline", r"box-shadow:\s*0 0 0 2px",
     "the halo ring on the spine dot (PanelSetB.tsx:317-320)"),
    ("Chips", r"counter-increment:\s*zipc-chapter",
     "the chapter counter (PanelSetB.tsx:402-408)"),
    ("Chips", r"content:\s*\"search this session",
     "the rounded search field (PanelSetB.tsx:457-467)"),
    ("Gutter", r"grid-template-columns:\s*54px 1fr",
     "the 54px margin gutter (PanelSetB.tsx:539)"),
    ("Gutter", r'content:\s*"rec"',
     "the rec pill (PanelSetB.tsx:534-537)"),
]

# ARM F -- the marks that were measured at ZERO in the shipped file. Every one of
# them belongs to a design above; a zero here means the design went back to being
# a recolour of the skeleton.
WAS_ZERO = [
    ("repeating-linear-gradient", r"repeating-linear-gradient", 1),
    ("grid-template-columns", r"grid-template-columns", 5),
    ("border-radius: 50%", r"border-radius:\s*50%", 4),
    ("backdrop-filter", r"backdrop-filter", 10),
    ("::after", r"::after", 10),
    ("counter(", r"counter\(", 1),
    ("nth-last-child", r":nth-last-child\(", 10),
    ("align-self", r"align-self", 3),
]


# --------------------------------------------------------------------------
# THE PARSER -- comments blanked but every byte kept, so line numbers are real.
# --------------------------------------------------------------------------
def strip_comments(css):
    return re.sub(r"/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), css)


def parse_blocks(css):
    stripped = strip_comments(css)
    out, i, depth, start, prelude = [], 0, 0, 0, ""
    while i < len(stripped):
        c = stripped[i]
        if c == "{":
            if depth == 0:
                prelude = stripped[start:i]
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                out.append((prelude.strip(), stripped[stripped.index("{", start) + 1:i]))
                start = i + 1
        i += 1
    return out


def norm_selector(text):
    return re.sub(r"\s+", " ", re.sub(r":root\[data-theme='[^']+'\]", ":root[data-theme=*]", text)).strip()


def theme_of(prelude):
    m = re.match(r"^:root\[data-theme='([^']+)'\]", prelude)
    return m.group(1) if m else None


def index(blocks):
    per = {t: [] for t in THEMES}
    unscoped, at_rules, leaked = [], [], []
    for prelude, body in blocks:
        if prelude.startswith("@"):
            at_rules.append(prelude)
            continue
        name = theme_of(prelude)
        if name in per:
            per[name].append((norm_selector(prelude.replace(":root[data-theme='%s']" % name, "")).strip(), body))
        else:
            unscoped.append(prelude)
        for member in [m.strip() for m in prelude.split(",") if m.strip()]:
            if not re.match(r"^:root\[data-theme(?:[~^|*$])?=", member):
                leaked.append(member)
    return per, unscoped, at_rules, leaked


def fingerprint(entries):
    """(selector, property) for every declaration, plus (selector, property=value)
    for the structural ones. Colours are deliberately excluded -- see
    STRUCTURAL_VALUE_PROPS."""
    fp = set()
    for sel, body in entries:
        for decl in [d.strip() for d in body.split(";") if d.strip()]:
            if ":" not in decl:
                continue
            prop, val = decl.split(":", 1)
            prop, val = prop.strip(), re.sub(r"\s+", " ", val.strip())
            fp.add(sel + " | " + prop)
            if prop in STRUCTURAL_VALUE_PROPS:
                fp.add(sel + " | " + prop + " = " + val)
    return fp


def selector_sequence(entries):
    return tuple(sel for sel, _ in entries)


def text_of(entries):
    return "\n".join(sel + " {" + body + "}" for sel, body in entries)


# --------------------------------------------------------------------------
# THE ARMS
# --------------------------------------------------------------------------
def arm_a_structure(per):
    """Every PAIR of designs must differ structurally. The defect is a pair that
    differs in NOTHING once the palette is removed -- measured at 0 in the
    shipped file (Timeline vs Gutter)."""
    fps = {t: fingerprint(per[t]) for t in THEMES}
    worst, worst_pair = None, ""
    for i, a in enumerate(THEMES):
        for b in THEMES[i + 1:]:
            d = len(fps[a] ^ fps[b])
            if worst is None or d < worst:
                worst, worst_pair = d, a + " vs " + b
    return worst >= MIN_PAIR_DIFF, "min pairwise structural difference = %d (>= %d), worst pair %s" % (worst, MIN_PAIR_DIFF, worst_pair)


def arm_b_tokens(per):
    """All 17 tune tokens declared AND consumed, in EACH design's own blocks."""
    bad = []
    for t in THEMES:
        text = text_of(per[t])
        root = " ".join(body for sel, body in per[t] if sel == "")
        for tok in TUNE_TOKENS:
            declared = re.search(r"(^|[\s;])" + re.escape(tok) + r"\s*:", root) is not None
            consumed = re.search(r"var\(\s*" + re.escape(tok) + r"\b", text) is not None
            if not (declared and consumed):
                bad.append("%s:%s%s" % (t, "" if declared else " not-declared", "" if consumed else " not-consumed"))
    return not bad, "%d/%d design-token pairs live" % (len(THEMES) * len(TUNE_TOKENS) - len(bad), len(THEMES) * len(TUNE_TOKENS)) + ("" if not bad else "  FAILING: " + ", ".join(bad[:6]))


def arm_c_identity(per):
    missing = []
    for theme, pattern, why in IDENTITY_MARKS:
        if re.search(pattern, text_of(per[theme])) is None:
            missing.append("%s: %s" % (theme, why))
    return not missing, "%d/%d identity marks present in their own design" % (len(IDENTITY_MARKS) - len(missing), len(IDENTITY_MARKS)) + ("" if not missing else "  MISSING: " + " | ".join(missing[:4]))


def arm_d_sequences(per):
    """No two designs may declare the SAME sequence of selectors. Measured at 1
    distinct sequence for all ten in the shipped file."""
    seqs = {t: selector_sequence(per[t]) for t in THEMES}
    distinct = len(set(seqs.values()))
    return distinct == len(THEMES), "%d distinct selector sequence(s) for %d designs" % (distinct, len(THEMES))


def arm_e_breadth(per):
    sizes = {t: len(fingerprint(per[t])) for t in THEMES}
    worst = min(sizes.values())
    return worst >= MIN_FP_SIZE, "smallest structural fingerprint = %d (>= %d); per design %s" % (worst, MIN_FP_SIZE, ", ".join("%s=%d" % (t, sizes[t]) for t in THEMES))


def arm_f_marks(css):
    text = strip_comments(css)
    bad = []
    for name, pattern, minimum in WAS_ZERO:
        n = len(re.findall(pattern, text))
        if n < minimum:
            bad.append("%s=%d (<%d)" % (name, n, minimum))
    return not bad, "every mark that measured 0 is back" + ("" if not bad else "  FAILING: " + ", ".join(bad))


def arm_g_scope(leaked, unscoped):
    return not leaked and not unscoped, "%d leaked member(s), %d unscoped block(s)" % (len(leaked), len(unscoped))


def arm_h_reproducible(css, path, tmpdir):
    """The bytes on disk must BE the generator's output. A hand edit to a
    generated file is the defect this arm refuses."""
    if not os.path.exists(GENERATOR):
        return True, "generator absent -- arm skipped"
    out = os.path.join(tmpdir, "zipc-regen.css")
    rc = subprocess.call([sys.executable, GENERATOR, "--profile", "designs", "--out", out],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if rc != 0 or not os.path.exists(out):
        return False, "the generator did not run (rc=%d)" % rc
    with open(out, "rb") as fh:
        regen = fh.read()
    same = regen == css.encode("utf-8")
    return same, ("the file IS the generator's output (%d B, sha256 %s)" % (len(regen), hashlib.sha256(regen).hexdigest()[:16].upper())) if same else "the file DIFFERS from the generator's output -- it was hand-edited"


DOM_ARM_JS = r"""
const fs = require("fs");
const { JSDOM } = require(process.argv[3]);
const html = fs.readFileSync(process.argv[2], "utf8");
const sels = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const dom = new JSDOM(html);
const doc = dom.window.document;
// The caption row panel.js builds (panel.js:799-839), then enough rows for the
// :nth-child(4n+1) chapter band and the :nth-last-child ramp to have targets.
const list = doc.getElementById("caption-list");
if (list) {
  list.hidden = false;
  const mk = (cls) => {
    const li = doc.createElement("li");
    li.className = cls;
    li.setAttribute("data-source", "proc:1");
    li.innerHTML = '<span class="caption__led"></span><span class="caption__time">00:00</span>' +
      '<span class="caption__text"><span class="caption__confirmed">' +
      '<span class="caption__word"><span class="caption__ch">o</span></span></span>' +
      '<span class="caption__provisional"></span><span class="caption__mark">&#9611;</span></span>';
    return li;
  };
  list.appendChild(mk("caption caption--provisional caption--latest"));
  list.appendChild(mk("caption caption--latest"));
  // 16 more: the recency ramp reaches :nth-last-child(n+13) only past 13 rows.
  for (let i = 0; i < 16; i += 1) list.appendChild(mk("caption"));
}
// Runtime state classes panel.js applies. '.status--live' is the live state of
// the ONE .status node; without it this arm would call a live rule dead.
const status = doc.getElementById("status");
if (status) status.classList.add("status--live");
const captions = doc.getElementById("captions");
if (captions) captions.classList.add("is-paused");
// theme-switcher.js creates #theme-button inside .panel__controls when absent.
const controls = doc.querySelector(".panel__controls");
if (controls) {
  const b = doc.createElement("button");
  b.className = "icon-button theme-button";
  b.id = "theme-button";
  controls.appendChild(b);
}
const dead = [];
for (const sel of sels) {
  const bare = sel.replace(/::(before|after|first-line|placeholder|selection)/g, "")
                  .replace(/:(?:hover|focus-visible|focus|active)(?![A-Za-z0-9_-])/g, "");
  if (!bare.trim()) continue;
  try {
    if (doc.querySelectorAll(bare).length === 0) dead.push(sel);
  } catch (e) { dead.push(sel + "   [UNPARSEABLE: " + e.message + "]"); }
}
process.stdout.write(JSON.stringify(dead));
"""


def arm_i_dom(css, tmpdir):
    """Every selector must MATCH at least one node of the real panel document.

    A rule whose selector matches nothing is a design that is not there -- the
    same defect class as the audit's D5 (42 class references that could never
    match the markup). jsdom is a local instrument; nothing is launched.
    """
    node_modules = os.path.join(ROOT, "node_modules")
    jsdom = os.path.join(node_modules, "jsdom")
    if not os.path.exists(jsdom):
        return True, "jsdom absent -- arm skipped"
    html = os.path.join(ROOT, "app", "panel", "panel.html")
    selectors = []
    per, unscoped, at_rules, leaked = index(parse_blocks(css))
    for prelude, _ in parse_blocks(css):
        if prelude.startswith("@") or theme_of(prelude) is None:
            continue
        for member in [m.strip() for m in prelude.split(",") if m.strip()]:
            selectors.append(re.sub(r"^:root\[data-theme='[^']+'\]\s*", "", member).strip())
    js = os.path.join(tmpdir, "dom-arm.js")
    sels = os.path.join(tmpdir, "dom-arm-sels.json")
    with open(js, "w", encoding="utf-8") as fh:
        fh.write(DOM_ARM_JS)
    with open(sels, "w", encoding="utf-8") as fh:
        fh.write(__import__("json").dumps(selectors))
    try:
        out = subprocess.check_output(["node", js, html, jsdom, sels], stderr=subprocess.DEVNULL)
        dead = __import__("json").loads(out.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return True, "the jsdom arm could not run (%s) -- skipped" % type(exc).__name__
    return not dead, "%d selector(s), %d that match NO node in panel.html%s" % (
        len(selectors), len(dead), "" if not dead else "  DEAD: " + " | ".join(dead[:5]))


def run_arms(css, path, tmpdir):
    per, unscoped, at_rules, leaked = index(parse_blocks(css))
    return [
        ("A", "no two designs are structurally identical",) + arm_a_structure(per),
        ("B", "every design consumes the 17 tune tokens",) + arm_b_tokens(per),
        ("C", "every design carries its own zip identity marks",) + arm_c_identity(per),
        ("D", "no two designs declare the same selector sequence",) + arm_d_sequences(per),
        ("E", "every design is built, not just recoloured",) + arm_e_breadth(per),
        ("F", "the marks that measured zero are back",) + arm_f_marks(css),
        ("G", "every selector member is rooted at a theme scope",) + arm_g_scope(leaked, unscoped),
        ("H", "the file is the generator's output, not a hand edit",) + arm_h_reproducible(css, path, tmpdir),
        ("I", "every selector matches a node of the real panel DOM",) + arm_i_dom(css, tmpdir),
    ]


# --------------------------------------------------------------------------
# THE CONTROL ARM -- the defect injected into COPIES under $TMPDIR
# --------------------------------------------------------------------------
def mutants(css, tmpdir):
    """Each mutant is a COPY with ONE defect restored. M1 is the shipped file
    itself, which IS defect D1: one skeleton, ten palettes."""
    out = []

    legacy = os.path.join(tmpdir, "zipc-legacy.css")
    if os.path.exists(GENERATOR):
        subprocess.call([sys.executable, GENERATOR, "--profile", "legacy", "--out", legacy],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(legacy):
        with open(legacy, "rb") as fh:
            out.append(("M1 the shipped file (one skeleton recoloured ten times)",
                        fh.read().decode("utf-8"), ["A", "B", "C", "D", "E", "F"]))

    m2 = re.sub(r"var\(\s*(--[a-zA-Z0-9-]+)\s*\)", "0px", css)
    out.append(("M2 every var() consumed by a literal (the D2 defect)", m2, ["B"]))

    m3 = css.replace("repeating-linear-gradient(180deg, transparent 0 27px, rgba(60,40,26,0.075) 27px 28px)", "none")
    out.append(("M3 Paper loses the ruled page", m3, ["C"]))

    m4 = css.replace("grid-template-columns: 44px 1fr", "grid-template-columns: 28px 1fr")
    out.append(("M4 Hairline's gutter collapses onto GlassCards' avatar column", m4, ["C"]))

    m5 = re.sub(r":root\[data-theme='Feed'\] \.caption:nth-last-child\([^)]*\) \{[^}]*\}\r?\n\r?\n?", "", css)
    out.append(("M5 Feed loses the recency ramp", m5, ["C"]))

    # A rule whose selector matches nothing is a design that is not there. This
    # is the D5 defect class (42 class references that could never match).
    m6 = css.replace(".caption__led", ".caption__ledd")
    out.append(("M6 a selector that matches no node in the panel", m6, ["I"]))

    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="the gate for the ten zip C designs")
    ap.add_argument("--file", default=PRODUCT)
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)

    tmpdir = os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp"
    tmpdir = os.path.join(tmpdir, "zipc-oracle")
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.makedirs(tmpdir, exist_ok=True)

    with open(args.file, "rb") as fh:
        raw = fh.read()
    css = raw.decode("utf-8")

    if not args.neg_arm:
        print("ZIPC-DESIGNS ORACLE -- PRISTINE (the bytes on disk)")
        print("  file: %s" % args.file)
        print("  %d B, sha256 %s" % (len(raw), hashlib.sha256(raw).hexdigest()[:16].upper()))
        print("")
        rows = run_arms(css, args.file, tmpdir)
        failed = 0
        for key, what, ok, detail in rows:
            print("  %s %s %-52s %s" % ("ok  " if ok else "FAIL", key, what, detail))
            if not ok:
                failed += 1
        print("")
        print("%d check(s), %d failed" % (len(rows), failed))
        print("VERDICT: %s" % ("PASS" if failed == 0 else "FAIL"))
        shutil.rmtree(tmpdir, ignore_errors=True)
        return 0 if failed == 0 else 1

    # THE NEGATIVE ARM: the untouched copy must be GREEN, every mutant RED.
    print("ZIPC-DESIGNS ORACLE -- CONTROL (untouched copy + mutants under $TMPDIR)")
    print("  control: %s" % args.file)
    print("")
    ctrl = run_arms(css, args.file, tmpdir)
    ctrl_bad = [k for k, w, ok, d in ctrl if not ok]
    print("  CONTROL %s  failed=%s" % ("GREEN" if not ctrl_bad else "RED", ctrl_bad or "none"))
    print("")
    wrong, inert = 0, []
    for label, blob, expected in mutants(css, tmpdir):
        path = os.path.join(tmpdir, re.sub(r"[^A-Za-z0-9]+", "-", label)[:40] + ".css")
        with open(path, "wb") as fh:
            fh.write(blob.encode("utf-8"))
        rows = run_arms(blob, path, tmpdir)
        red = [k for k, w, ok, d in rows if not ok]
        hit = all(k in red for k in expected)
        if not hit:
            wrong += 1
        if not red:
            inert.append(label)
        print("  %s %s" % ("PASS" if hit else "FAIL", label))
        print("        want RED on %s, got RED on %s" % (",".join(expected), ",".join(red) or "(none -- INERT)"))
    print("")
    print("NEG-ARM VERDICT: %s -- %d mutant(s), %d wrong, %d inert, control %s" % (
        "PASS" if (not wrong and not inert and not ctrl_bad) else "FAIL",
        len(mutants(css, tmpdir)), wrong, len(inert), "GREEN" if not ctrl_bad else "RED"))
    shutil.rmtree(tmpdir, ignore_errors=True)
    return 0 if (not wrong and not inert and not ctrl_bad) else 1


if __name__ == "__main__":
    raise SystemExit(main())
