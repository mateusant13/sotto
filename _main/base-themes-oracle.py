#!/usr/bin/env python3
"""BASE-THEMES ORACLE -- the gate for D4, D5 and D6 of I:/cc-tmp/design-bugs-audit.md
on the two theme families this lane owns: theme-1..5.css + panel-designs.css
(generator _main/_design-lane/gen_themes.py) and the D4 half of cinematic.css
(generator _main/_design-lane/gen_cinematic.py).

ARMS (each a claim about the SHIPPED bytes, not about a plan):

  A  D5 -- every CLASS selector in the six files matches a class the live document can
     carry. The universe is RE-DERIVED at run time: the class attribute tokens of
     panel.html unioned with every class the modules IT loads assigns (class= /
     className= / classList.add|toggle|remove). The four names the audit measured as
     unmatchable must have ZERO selector occurrences.
  B  D6 -- no token is DECLARED in the six files with zero readers. A reader is a var()
     in the same file, in a base stylesheet that applies under the theme scope
     (panel.css, caption-float.css, skin-layout.css, skins/*.css), or a mention in the
     panel JS / the shell. Two families are read OUTSIDE CSS and are excused by name
     with their instrument: --strip-height/--float-height (getComputedStyle in the
     shell) and --c-i/--meter-h (written inline by panel.js).
  C  D4 -- no rule of the six files or of cinematic.css asks for an ITALIC the bundle
     cannot paint. The faces are read out of fonts.css; a request with no matching face
     is a browser-SYNTHESISED oblique. The arm also checks the invariant the fix
     introduced: a theme italicises its .captions__placeholder ONLY IF its own caption
     is italic (the zip states the caption, never the placeholder).
  D  RULE 10 -- a FRESH run of each generator, executed from a copy whose sha256 is
     proven equal to the repo file, reproduces the shipped bytes. Outputs are redirected
     into $TMPDIR; nothing under app/ is written.

KNOWN OPEN ITEMS are declared BY NAME with their measurement and are printed, never
silently passed: anything NOT declared fails the arm. That is what keeps this gate able
to say NO to a dead token nobody has measured yet.

CONTROL (--neg-arm): the SAME predicates run against the output of MUTATED COPIES of the
GENERATORS, and the arm that must catch each mutation has to go RED. One mutant is INERT
for A/B/C (it only adds a comment) and must stay GREEN there, which is what proves those
arms measure the RELATION and not a hash.

Run:  py -3 _main/base-themes-oracle.py
      py -3 _main/base-themes-oracle.py --neg-arm
Nothing is launched: no browser, no shell, no worker, no WebView2. The only subprocess is
the node --check the cinematic generator runs on its own manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(ROOT, "app", "panel")
THEMES = os.path.join(PANEL, "themes")
LANE = os.path.join(HERE, "_design-lane")
TMP = os.environ.get("TMPDIR", r"I:\cc-tmp")
SCRATCH = os.path.join(TMP, "base-themes-oracle-out")

SIX = [os.path.join(THEMES, "theme-%d.css" % n) for n in (1, 2, 3, 4, 5)] + \
      [os.path.join(THEMES, "panel-designs.css")]
CINEMATIC = os.path.join(THEMES, "cinematic.css")
FONTS_CSS = os.path.join(THEMES, "fonts.css")
PANEL_HTML = os.path.join(PANEL, "panel.html")
GEN_THEMES = os.path.join(LANE, "gen_themes.py")
GEN_CINEMATIC = os.path.join(LANE, "gen_cinematic.py")
BUILD_FONTS = os.path.join(LANE, "build_fonts.py")

DEAD_CLASSES = ("status__hint", "history__source", "reveal-button--danger", "chrome__key")

EXTERNAL_READERS = {
    "--strip-height": "sotto_webview.py reads it via getComputedStyle",
    "--float-height": "sotto_webview.py reads it via getComputedStyle",
    "--c-i": "panel.js writes it inline",
    "--meter-h": "panel.js writes it inline",
}

# MEASURED, DECLARED, NOT CLOSED -- see _main/receipt-base-themes.md section D6.
# Anything not named here fails ARM B, so this table cannot hide a new dead token.
KNOWN_OPEN_TOKENS = {
    "--size-meta": (
        "declared by all ten designs and read by none. The rule that SHOULD read it is "
        "the shared CHROME block, whose font-size literals ARE this tier -- but that block "
        "is shared by the two lanes and wiring it changes the painted size of 5 of the 10 "
        "B-lane designs (measured: pd-tele 11->10, pd-bcast 9.5->9, pd-mano 10->11, "
        "pd-cine 13->12, pd-instr 10->9). Which size a chrome paints is a DESIGN decision, "
        "so the token stays as the handle and the decision is reported."),
    "--space-4": (
        "dead in theme-1..5 (no rule reads it) but ALIVE in panel-designs: pd-cine's "
        "live-line padding is 'padding-left: var(--space-4)', parsed from that zip's own "
        "'pl-4'. The token block is shared by both lanes, so removing it would break the "
        "one design that reads it."),
}


def sha(path):
    with io.open(path, "rb") as fh:
        b = fh.read()
    return len(b), hashlib.sha256(b).hexdigest().upper()


def read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def strip_css_comments(text):
    return re.sub(r"/\*[\s\S]*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def style_rules(css):
    """Yield (selector, body) per style rule, recursing into @media/@supports.

    @keyframes bodies are SKIPPED: their preludes are 0%, 49%, not selectors, and a
    scanner that walks raw by braces reads them as rules.
    """
    text = strip_css_comments(css)
    out = []

    def walk(s):
        i = 0
        while i < len(s):
            j = s.find("{", i)
            if j < 0:
                break
            prelude = s[i:j].strip()
            depth, k = 1, j + 1
            while k < len(s) and depth:
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                k += 1
            body = s[j + 1:k - 1]
            head = prelude.split()[0] if prelude else ""
            if head.startswith("@") and head[1:] in ("media", "supports", "layer"):
                walk(body)
            elif head.startswith("@"):
                pass
            else:
                for part in prelude.split(","):
                    if part.strip():
                        out.append((part.strip(), body))
            i = k

    walk(text)
    return out


def class_tokens(selector):
    return set(re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)", selector))


# --------------------------------------------------------------------------- #
# ARM A -- the class universe, re-derived from the live document
# --------------------------------------------------------------------------- #

def class_universe():
    html = read(PANEL_HTML)
    universe = set()
    for m in re.finditer(r'class="([^"]*)"', html):
        for c in m.group(1).split():
            if re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", c):
                universe.add(c)
    scripts = re.findall(r'<script src="([^"]+)"', html)
    per_module = {}
    for s in scripts:
        path = os.path.join(PANEL, s)
        if not os.path.isfile(path):
            per_module[s] = None
            continue
        t = read(path)
        names = set()
        for m in re.finditer(r'class(?:Name)?\s*=\s*["\x27\x60]([^"\x27\x60]*)["\x27\x60]', t):
            names.update(x for x in m.group(1).split() if re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", x))
        for m in re.finditer(r"classList\.(?:add|toggle|remove)\(([^)]*)\)", t):
            for q in re.finditer(r'["\x27\x60]([^"\x27\x60]*)["\x27\x60]', m.group(1)):
                names.update(x for x in q.group(1).split() if re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", x))
        per_module[s] = names
        universe |= names
    return universe, per_module, scripts


def arm_a(files):
    universe, per_module, scripts = class_universe()
    bad, dead = [], []
    for f in files:
        for sel, _b in style_rules(read(f)):
            for c in sorted(class_tokens(sel)):
                if c not in universe:
                    bad.append((os.path.basename(f), sel, c))
                    if c in DEAD_CLASSES:
                        dead.append((os.path.basename(f), c))
    return universe, per_module, scripts, bad, dead


# --------------------------------------------------------------------------- #
# ARM B -- the token census
# --------------------------------------------------------------------------- #

def js_strip(t):
    t = re.sub(r"/\*[\s\S]*?\*/", " ", t)
    t = re.sub(r"(^|[^:\x27\x60\\])//[^\n]*", r"\1", t)
    return t


def py_strip(t):
    t = re.sub(r'"""[\s\S]*?"""', " ", t)
    t = re.sub(r"'''[\s\S]*?'''", " ", t)
    t = re.sub(r"(^|\s)#[^\n]*", r"\1", t)
    return t


def reader_map():
    readers = {}

    def add(tok, where):
        readers.setdefault(tok, []).append(where)

    css_files = [os.path.join(PANEL, "panel.css"),
                 os.path.join(PANEL, "caption-float.css"),
                 os.path.join(PANEL, "skin-layout.css")]
    for dirpath, _dirs, names in os.walk(os.path.join(PANEL, "skins")):
        css_files += [os.path.join(dirpath, n) for n in names if n.endswith(".css")]
    for f in css_files:
        for i, line in enumerate(strip_css_comments(read(f)).split("\n"), 1):
            for m in re.finditer(r"var\(\s*(--[A-Za-z0-9_-]+)", line):
                add(m.group(1), "%s:%d" % (os.path.relpath(f, ROOT), i))
    other = [os.path.join(PANEL, n) for n in sorted(os.listdir(PANEL))
             if n.endswith(".js") or n.endswith(".html")]
    webview = os.path.join(ROOT, "app", "webview")
    if os.path.isdir(webview):
        other += [os.path.join(webview, n) for n in sorted(os.listdir(webview))
                  if n.endswith(".js") or n.endswith(".py")]
    for f in other:
        t = py_strip(read(f)) if f.endswith(".py") else js_strip(read(f))
        for i, line in enumerate(t.split("\n"), 1):
            for m in re.finditer(r"(--[A-Za-z0-9_-]+)", line):
                add(m.group(1), "%s:%d" % (os.path.relpath(f, ROOT), i))
    return readers


def rel_to_root(path):
    """A label for a path that may live on ANOTHER MOUNT (the control's mutants do)."""
    try:
        return os.path.relpath(path, ROOT)
    except ValueError:
        return path


def declared_tokens(path):
    out = []
    for i, line in enumerate(read(path).split("\n"), 1):
        m = re.match(r"\s*(--[A-Za-z0-9_-]+)\s*:", line)
        if m:
            out.append((m.group(1), i))
    return out


def arm_b(files, readers):
    dead, excused, open_hits = [], [], []
    for f in files:
        self_reads = set()
        for _sel, body in style_rules(read(f)):
            self_reads |= set(re.findall(r"var\(\s*(--[A-Za-z0-9_-]+)", body))
        for tok, line in declared_tokens(f):
            rel = rel_to_root(f) + ":"
            outside = [w for w in readers.get(tok, []) if not w.startswith(rel)]
            if tok in self_reads or outside:
                continue
            if tok in EXTERNAL_READERS:
                excused.append((os.path.basename(f), tok, line, EXTERNAL_READERS[tok]))
            elif tok in KNOWN_OPEN_TOKENS:
                open_hits.append((os.path.basename(f), tok, line))
            else:
                dead.append((os.path.basename(f), tok, line))
    return dead, excused, open_hits


# --------------------------------------------------------------------------- #
# ARM C -- the italic requests vs the bundled faces
# --------------------------------------------------------------------------- #

def bundled_faces():
    faces = {}
    for m in re.finditer(r"@font-face\s*\{([^}]*)\}", read(FONTS_CSS)):
        b = m.group(1)

        def g(k):
            r = re.search(k + r"\s*:\s*([^;]+);", b)
            return r.group(1).strip().replace('"', "").replace("'", "") if r else ""
        faces.setdefault(g("font-family"), set()).add((g("font-weight"), g("font-style")))
    return faces


def theme_scopes(path):
    out = {}
    text = strip_css_comments(read(path))
    for m in re.finditer(r":root\[data-theme='([^']+)'\]\{([\s\S]*?)\n\}", text):
        d = out.setdefault(m.group(1), {})
        for dm in re.finditer(r"(--[A-Za-z0-9_-]+)\s*:\s*([^;]+);", m.group(2)):
            d.setdefault(dm.group(1), dm.group(2).strip())
    return out


def resolve(scope_vars, value, depth=0):
    if depth > 6:
        return value
    m = re.search(r"var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,\s*([^)]+))?\)", value)
    if not m:
        return value
    decl = scope_vars.get(m.group(1))
    if decl:
        return resolve(scope_vars, decl, depth + 1)
    if m.group(2):
        return resolve(scope_vars, m.group(2), depth + 1)
    return value


def arm_c(files, faces):
    missing, placeholder_italic, caption_italic, inherited = [], {}, {}, []
    for f in files:
        scopes = theme_scopes(f)
        for sel, body in style_rules(read(f)):
            if not re.search(r"font-style\s*:\s*italic", body):
                continue
            m = re.search(r"data-theme='([^']+)'", sel)
            sc = m.group(1) if m else "?"
            sv = scopes.get(sc, {})
            fm = re.search(r"font-family\s*:\s*([^;]+);", body)
            if fm:
                fam = resolve(sv, fm.group(1).strip()).split(",")[0].strip().strip('"').strip("'")
                if not [x for x in faces.get(fam, ()) if x[1] == "italic"]:
                    missing.append((os.path.basename(f), sc, sel[:70], fam))
            else:
                cands = [resolve(sv, v).split(",")[0].strip().strip('"').strip("'")
                         for k, v in sv.items() if k.startswith("--font-")]
                ok = any([x for x in faces.get(c, ()) if x[1] == "italic"] for c in cands)
                inherited.append((os.path.basename(f), sc, cands, ok))
                if not ok:
                    missing.append((os.path.basename(f), sc, sel[:70], "inherits:%s" % cands))
            if "captions__placeholder" in sel:
                placeholder_italic[sc] = True
            if "caption__text" in sel:
                caption_italic[sc] = True
    bad_echo = sorted(s for s in placeholder_italic if s not in caption_italic)
    return missing, inherited, bad_echo, sorted(placeholder_italic), sorted(caption_italic)


def cinematic_ship():
    """The ids gen_cinematic.py emits from its OWN code path (read, not hard-coded).

    THE RENAME IS PART OF THE IDENTITY: SHIP names the zip's own scene ids and RENAME
    maps one of them to the shipped id (tideline -> tideline-body), so a set built from
    SHIP alone would check cine-tideline-body as if it were an extra and would call the
    EXTRA cine-tideline a ship theme -- measured, that is exactly the false RED this
    function produced on its first run.
    """
    t = read(GEN_CINEMATIC)
    m = re.search(r"^SHIP\s*=\s*\[([^\]]*)\]", t, re.M)
    if not m:
        return set()
    rename = {}
    rm = re.search(r"^RENAME\s*=\s*\{([^}]*)\}", t, re.M)
    if rm:
        for k, v in re.findall(r"'([^']+)'\s*:\s*'([^']+)'", rm.group(1)):
            rename[k] = v
    return {"cine-" + rename.get(s, s) for s in re.findall(r"'([^']+)'", m.group(1))}


def extras_italic_source():
    """file:line of the extras modules that emit the placeholder italic (measured)."""
    hits = []
    for name in sorted(os.listdir(LANE)):
        if not name.startswith("cine_extra") or not name.endswith(".py"):
            continue
        lines = read(os.path.join(LANE, name)).split("\n")
        for i, line in enumerate(lines):
            if "font-style: italic" in line and i >= 2 and "captions__placeholder" in lines[i - 2]:
                hits.append("%s:%d" % (name, i + 1))
    return hits


# --------------------------------------------------------------------------- #
# ARM D -- RULE 10: a fresh run of each generator reproduces the shipped bytes
# --------------------------------------------------------------------------- #

def run_quiet(g):
    """Call the generator's main() with its own chatter swallowed."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        g["main"]()
    finally:
        sys.stdout = old
    return buf.getvalue()


def run_generator(dst_name, src, patches):
    """Run the generator from a byte-verified COPY, with its own chatter swallowed.

    The copy is what executes (sha256 checked against the repo file first); __file__
    still points at the repo so its INPUT paths resolve normally -- only the OUTPUT
    constants are patched. Path is not logic.
    """
    dst = os.path.join(TMP, dst_name)
    shutil.copyfile(src, dst)
    if sha(src) != sha(dst):
        raise SystemExit("COPY MISMATCH %s" % dst_name)
    g = {"__name__": "gen_copy", "__file__": src}
    exec(compile(read(dst), dst, "exec"), g)
    for k, v in patches.items():
        g[k] = v
    return run_quiet(g)


def arm_d(files):
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH)
    os.makedirs(SCRATCH)
    tdir = os.path.join(SCRATCH, "themes")
    cdir = os.path.join(SCRATCH, "cine")
    fdir = os.path.join(SCRATCH, "fonts")
    for d in (tdir, cdir, fdir):
        os.makedirs(d)
    run_generator("oracle-gen-themes.py", GEN_THEMES, {
        "OUT": tdir,
        "PD_CSS_OUT": os.path.join(tdir, "panel-designs.css"),
        "PD_JS_OUT": os.path.join(tdir, "panel-designs.js"),
    })
    # manifest() READS the file it replaces and fetch_backdrop() treats an already
    # bundled photo as INPUT: both are seeded from the shipped bytes, which is also what
    # keeps this run network-free (measured: with an empty backdrops dir the generator
    # DOWNLOADS, and its output then differs).
    shutil.copyfile(os.path.join(THEMES, "themes.js"), os.path.join(cdir, "themes.js"))
    shutil.copytree(os.path.join(THEMES, "backdrops"), os.path.join(cdir, "backdrops"))
    run_generator("oracle-gen-cinematic.py", GEN_CINEMATIC, {
        "CSS_OUT": os.path.join(cdir, "cinematic.css"),
        "JS_OUT": os.path.join(cdir, "themes.js"),
        "BACKDROPS": os.path.join(cdir, "backdrops"),
    })
    run_generator("oracle-build-fonts.py", BUILD_FONTS, {
        "FONTS_OUT": fdir,
        "CSS_OUT": os.path.join(SCRATCH, "fonts.css"),
    })
    pairs = [(os.path.join(tdir, os.path.basename(f)), f) for f in files]
    pairs += [(os.path.join(cdir, "cinematic.css"), CINEMATIC),
              (os.path.join(SCRATCH, "fonts.css"), FONTS_CSS)]
    bad = []
    for fresh, disk in pairs:
        if sha(fresh) != sha(disk):
            bad.append((os.path.basename(disk), sha(fresh), sha(disk)))
    return bad


# --------------------------------------------------------------------------- #
# the arms, as one function so the CONTROL runs the SAME predicates
# --------------------------------------------------------------------------- #

def evaluate(files, cine=(CINEMATIC,)):
    """Run every arm on ONE population.

    The populations differ on purpose: the shipped run judges the six files AND the
    shipped cinematic.css, while a mutant that regenerates only the six must not be
    judged on the shipped cinematic (and vice versa) -- otherwise every mutant inherits
    the OTHER family's open items, which is exactly the false RED the control produced
    on its first run.
    """
    res = {}
    res["universe"] = arm_a(files)
    readers = reader_map()
    res["readers"] = readers
    res["b"] = arm_b(files, readers)
    faces = bundled_faces()
    res["faces"] = faces
    res["c"] = arm_c(list(files) + list(cine), faces)
    return res


def report(res, files, rule10=True):
    fails = []
    universe, per_module, scripts, bad_a, dead_a = res["universe"]
    print("ARM A (D5) -- class universe: %d class(es) from panel.html + %d module(s)"
          % (len(universe), len(scripts)))
    if bad_a:
        fails.append("A: %d class selector(s) match no class of the live document" % len(bad_a))
        for row in bad_a[:20]:
            print("    RED %s: %s  (class .%s)" % row)
    else:
        print("    GREEN every class selector matches a class the live document can carry")
    for name in DEAD_CLASSES:
        hit = [r for r in dead_a if r[1] == name]
        if hit:
            fails.append("A: dead class .%s still a selector in %s" % (name, hit[0][0]))
            print("    RED .%s is still a selector in %s" % (name, hit[0][0]))
        else:
            print("    GREEN .%s: 0 selector(s) in the six files" % name)

    dead_b, excused, open_hits = res["b"]
    print("ARM B (D6) -- %d declared token(s) checked against %d reader site(s)"
          % (sum(len(declared_tokens(f)) for f in files), len(res["readers"])))
    if dead_b:
        fails.append("B: %d declared token(s) with zero readers and no declaration" % len(dead_b))
        for row in dead_b:
            print("    RED %s declares %s (line %d) and nothing reads it" % row)
    else:
        print("    GREEN no undeclared dead token in the six files")
    seen = {}
    for base, tok, line in open_hits:
        seen.setdefault(tok, []).append("%s:%d" % (base, line))
    for tok in sorted(seen):
        print("    OPEN  %s declared %d time(s) with 0 readers [%s] -- declared, not closed:"
              % (tok, len(seen[tok]), ", ".join(seen[tok])))
        print("          %s" % KNOWN_OPEN_TOKENS[tok])
    for row in excused:
        print("    EXCUSED %s %s (line %d): %s" % row)

    missing_c, inherited, bad_echo, ph, cap = res["c"]
    ship = cinematic_ship()
    print("ARM C (D4) -- %d bundled famil(ies); %d rule(s) with font-style: italic resolved"
          % (len(res["faces"]), len(inherited) + len(missing_c)))
    miss_ship = [r for r in missing_c if (not r[1].startswith("cine-")) or (r[1] in ship)]
    miss_extra = [r for r in missing_c if r not in miss_ship]
    echo_ship = [s for s in bad_echo if s in ship]
    if miss_ship:
        fails.append("C: %d italic request(s) with no bundled face in the lane's own path"
                     % len(miss_ship))
        for row in miss_ship:
            print("    RED %s %s: %s  family=%s" % row)
    else:
        print("    GREEN every italic request of theme-1..5 / panel-designs / the 10 SHIP")
        print("          cinematic themes has a real bundled face")
    if echo_ship:
        fails.append("C: %d SHIP theme(s) italicise the placeholder without an italic caption"
                     % len(echo_ship))
        print("    RED placeholder italic without caption italic: %s" % echo_ship)
    else:
        print("    GREEN placeholder italic only where the zip italicises the caption")
    print("    placeholder italic: %d theme(s); caption italic: %d theme(s)" % (len(ph), len(cap)))
    for row in inherited:
        print("    note: %s %s inherits its family (%s) -> an italic face is present: %s"
              % (row[0], row[1], row[2], row[3]))
    echo_extra = [s for s in bad_echo if s not in ship]
    if miss_extra or echo_extra:
        srcs = extras_italic_source()
        print("    OPEN  %d italic request(s) and %d placeholder-echo(es) remain, ALL in"
              % (len(miss_extra), len(echo_extra)))
        print("          themes emitted by the two extras modules (OUTSIDE this lane's write")
        print("          scope); the emitting line is %s in each:" % (", ".join(srcs) or "?"))
        for row in miss_extra:
            print("          %s %s: %s  family=%s" % row)
        if echo_extra:
            print("          placeholder italic without caption italic: %s" % echo_extra)

    if rule10:
        bad_d = arm_d(files)
        print("ARM D (RULE 10) -- a fresh run of each generator from a sha256-verified copy")
        if bad_d:
            fails.append("D: %d output(s) not reproduced by a fresh generator run" % len(bad_d))
            for name, f, d in bad_d:
                print("    RED %s fresh=%d/%s disk=%d/%s" % (name, f[0], f[1][:16], d[0], d[1][:16]))
        else:
            print("    GREEN theme-1..5.css, panel-designs.css, cinematic.css, fonts.css"
                  " all reproduced byte-for-byte")
    return fails


# --------------------------------------------------------------------------- #
# the CONTROL
# --------------------------------------------------------------------------- #

MUT_D5 = ("""{S} .status--error .status__text{{ color: {err_text}; }}""",
          """{S} .status--error .status__text{{ color: {err_text}; }}
{S} .status__hint{{ color: var(--text-muted); }}""")

MUT_D6 = ("""  --ok: {ok};
  --error: {error};""",
          """  --ok: {ok};
  --busy: {busy};
  --error: {error};""")

MUT_D4 = ("""    a('  font-family: var(--font-caption);')
    if toks['__italic']:
        a('  font-style: italic;')""",
          """    a('  font-family: var(--font-caption);')
    a('  font-style: italic;')""")

MUT_INERT = ("""{S} .status{{""",
             """/* the inert control adds this comment and nothing else */
{S} .status{{""")


def mutate(name, pairs):
    src = os.path.join(LANE, name)
    dst = os.path.join(TMP, "mutant-" + name)
    t = read(src)
    for old, new in pairs:
        if old not in t:
            raise SystemExit("MUTATION ANCHOR MISSING in %s: %r" % (name, old[:60]))
        t = t.replace(old, new, 1)
    with io.open(dst, "w", encoding="utf-8", newline="") as fh:
        fh.write(t)
    return dst


def eval_mutant(gen_path, repo_path, kind, files):
    """Regenerate with the mutant and run the SAME predicates on ITS output.

    __file__ points at the REPO generator, not at the mutant copy: the mutant lives in
    $TMPDIR and the generator resolves its INPUTS (zips/, sibling data modules) from
    __file__. Bytes differ, paths do not -- the same rule the rule-10 arm follows.
    """
    if os.path.isdir(SCRATCH):
        shutil.rmtree(SCRATCH)
    os.makedirs(SCRATCH)
    tdir = os.path.join(SCRATCH, "themes")
    os.makedirs(tdir)
    g = {"__name__": "gen_copy", "__file__": repo_path}
    exec(compile(read(gen_path), gen_path, "exec"), g)
    if kind == "themes":
        g["OUT"] = tdir
        g["PD_CSS_OUT"] = os.path.join(tdir, "panel-designs.css")
        g["PD_JS_OUT"] = os.path.join(tdir, "panel-designs.js")
        run_quiet(g)
        out = [os.path.join(tdir, os.path.basename(f)) for f in files]
    else:
        cdir = os.path.join(SCRATCH, "cine")
        os.makedirs(cdir)
        shutil.copyfile(os.path.join(THEMES, "themes.js"), os.path.join(cdir, "themes.js"))
        shutil.copytree(os.path.join(THEMES, "backdrops"), os.path.join(cdir, "backdrops"))
        g["CSS_OUT"] = os.path.join(cdir, "cinematic.css")
        g["JS_OUT"] = os.path.join(cdir, "themes.js")
        g["BACKDROPS"] = os.path.join(cdir, "backdrops")
        run_quiet(g)
        out = [os.path.join(cdir, "cinematic.css")]
    return out


def neg_arm(files):
    fails = []
    cases = [
        ("M1 D5 -- a dead class selector re-inserted", GEN_THEMES, "themes", [MUT_D5], "A"),
        ("M2 D6 -- a dead token re-declared", GEN_THEMES, "themes", [MUT_D6], "B"),
        ("M3 D4 -- the unconditional placeholder italic restored", GEN_CINEMATIC, "cine",
         [MUT_D4], "C"),
        ("M4 INERT -- a comment added (must stay GREEN on A/B/C)",
         GEN_THEMES, "themes", [MUT_INERT], "INERT"),
    ]
    for label, gen, kind, pairs, arm in cases:
        path = mutate(os.path.basename(gen), pairs)
        outs = eval_mutant(path, gen, kind, files)
        res = evaluate(outs, []) if kind == "themes" else evaluate(files, outs)
        bad_a = res["universe"][3]
        dead_b = res["b"][0]
        miss_c, _inh, echo_c, _ph, _cap = res["c"]
        reds = []
        if bad_a:
            reds.append("A(%d)" % len(bad_a))
        if dead_b:
            reds.append("B(%d)" % len(dead_b))
        if miss_c or echo_c:
            reds.append("C(%d)" % (len(miss_c) + len(echo_c)))
        if arm == "INERT":
            ok = not reds
            print("%-56s -> %s" % (label, "GREEN (inert, as required)" if ok
                                   else "UNEXPECTED RED %s" % reds))
            if not ok:
                fails.append("CONTROL: the inert mutant moved A/B/C: %s" % reds)
        else:
            ok = arm in [r[0] for r in reds]
            print("%-56s -> %s" % (label, "RED as required on %s" % reds if ok
                                   else "NOT CAUGHT (reds=%s)" % reds))
            if not ok:
                fails.append("CONTROL: mutant %r not caught by ARM %s (reds=%s)"
                             % (label, arm, reds))
    path = mutate(os.path.basename(GEN_THEMES),
                  [("  --radius-sm: {radius_sm};", "  --radius-sm: {radius_sm} /*moved*/;")])
    outs = eval_mutant(path, GEN_THEMES, "themes", files)
    bad = [os.path.basename(d) for fresh, d in zip(outs, files) if sha(fresh) != sha(d)]
    ok = bool(bad)
    print("%-56s -> %s" % ("M5 RULE 10 -- a generator mutation that moves the bytes",
                           "RED as required on D (%s)" % ",".join(bad) if ok else "NOT CAUGHT"))
    if not ok:
        fails.append("CONTROL: a mutated generator still reproduced the shipped bytes")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args()
    print("== BASE-THEMES ORACLE ==")
    fails = report(evaluate(SIX, [CINEMATIC]), SIX)
    print("VERDICT: %s" % ("PASS" if not fails else "FAIL"))
    for f in fails:
        print("  - %s" % f)
    if args.neg_arm:
        print()
        print("== CONTROL: the same predicates against MUTATED GENERATOR COPIES ==")
        ctrl = neg_arm(SIX)
        print("CONTROL VERDICT: %s" % ("PASS" if not ctrl else "FAIL"))
        fails = fails + ctrl
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
