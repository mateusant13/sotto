#!/usr/bin/env python3
"""Sotto -- THE ORACLE FOR THE 'cinematic' TEMPLATE SET (the 25 'cine-*' themes).

WHAT IT GATES, and the audit section each arm answers
  A  D3    every one of the 25 themes DECLARES and CONSUMES the four tuning tokens
           (--size-closed, --leading-closed, --weight-closed, --motion-in) with var()
  B  D5    every class reference in the stylesheet matches a node the panel can load
  C  D6    no token declared in the stylesheet is read by nothing, anywhere
  D  D7/D8 the picker's labels are unique and the shared ids agree with the frozen
           skins that actually mount
  E  rule 10  the bytes on disk ARE a fresh run of the generator
  F  pins  the four values are the ones each zip states, family by family -- the
           closed-line size PINNED WITH the owner's `--caption-scale` font dial in it
           (re-anchored 2026-10-20; the dial is a multiplier and the product now
           carries it)

Run:  py -3 _main/cinematic-designs-oracle.py
      py -3 _main/cinematic-designs-oracle.py --neg-arm

NOTHING IS LAUNCHED: no browser, no shell, no worker. Every measurement is over the
bytes on disk; arm E additionally runs the generator ONCE into a TEMP directory.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PANEL = os.path.join(ROOT, 'app', 'panel')
DEFAULT_CSS = os.path.join(PANEL, 'themes', 'cinematic.css')
DEFAULT_THEMES = os.path.join(PANEL, 'themes', 'themes.js')
DEFAULT_GEN = os.path.join(HERE, '_design-lane', 'gen_cinematic.py')
SKINS = os.path.join(PANEL, 'skins', 'skins.js')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

CLOSED = ['--size-closed', '--leading-closed', '--weight-closed', '--motion-in']

# The 25 ids BY THE FAMILY whose zip states their closed-line values. A PIN, on
# purpose: reading this out of the generator would let a wrong CLOSED row agree with
# itself, which is the one thing a gate must never do.
FAMILIES = {
    'cinematic': ['cine-midnight-rain', 'cine-warm-hour', 'cine-velvet-dusk',
                  'cine-study-light', 'cine-tideline-body', 'cine-north-fog',
                  'cine-motel-glow', 'cine-paper-moon', 'cine-quiet-streets',
                  'cine-last-reel'],
    'cinematic-1': ['cine-cafe', 'cine-tideline', 'cine-rainglass', 'cine-fieldnotes',
                    'cine-dustlight', 'cine-rooftop', 'cine-analog', 'cine-shelves',
                    'cine-ember'],
    'cinematic-2': ['cine-rainline', 'cine-blue-hour', 'cine-cellar', 'cine-linen',
                    'cine-reading-hour', 'cine-last-train'],
}

# The names that LEFT the contract in this lane (D6), each because nothing under
# app/panel/** or the shell reads it (measured: 0 var() consumers, 0 getComputedStyle).
REMOVED = ['--slab-opacity', '--busy', '--font-closed', '--space-1', '--space-4',
           '--space-5', '--bg', '--cine-accent-ink']


def read(path):
    """No newline translation: the files are CRLF and a mutant COPY must keep the
    line endings of its subject, or the copy is a different file for reasons that have
    nothing to do with the defect being injected."""
    with io.open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ── CSS reading ───────────────────────────────────────────────────────────────────

def strip_comments(css):
    """Comments become spaces, NEWLINES KEPT, so a reported line number still points
    at the line a reader sees. The first version of this file collapsed comments into
    one line and moved every number; the audit paid for that lesson already."""
    out = []
    i = 0
    n = len(css)
    while i < n:
        if css.startswith('/*', i):
            j = css.find('*/', i + 2)
            if j < 0:
                j = n - 2
            out.append(''.join('\n' if c == '\n' else ' ' for c in css[i:j + 2]))
            i = j + 2
        else:
            out.append(css[i])
            i += 1
    return ''.join(out)


def match_brace(text, i):
    """Index of the '}' matching the '{' at i."""
    depth = 0
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text) - 1


def parse_rules(text, start=0, end=None):
    """[(prelude, body, line)] for every DECLARATION rule, at any nesting depth.
    An at-rule's own prelude is not a rule; its children are."""
    if end is None:
        end = len(text)
    rules = []
    i = start
    buf = []
    while i < end:
        ch = text[i]
        if ch == '{':
            prelude = ''.join(buf).strip()
            buf = []
            j = match_brace(text, i)
            inner = text[i + 1:j]
            if '{' in inner:
                rules.extend(parse_rules(text, i + 1, j))
            else:
                line = text.count('\n', 0, i) + 1
                rules.append((prelude, inner, line))
            i = j + 1
            continue
        if ch == '}':
            break
        buf.append(ch)
        i += 1
    return rules


def rules_of(css):
    return parse_rules(strip_comments(css))


def theme_blocks(rules):
    """{theme id: [bodies of its token blocks]} — the rules whose prelude IS the
    theme scope, i.e. where a token is DECLARED."""
    out = {}
    for prelude, body, _line in rules:
        m = re.fullmatch(r":root\[data-theme='(cine-[a-z0-9-]+)'\]", prelude)
        if m:
            out.setdefault(m.group(1), []).append(body)
    return out


def scoped_rules(rules, theme):
    """Every rule whose selector matches this theme: its own scope or the set's."""
    out = []
    for prelude, body, line in rules:
        if ("[data-theme='%s']" % theme) in prelude or "[data-theme^='cine-']" in prelude:
            out.append((prelude, body, line))
    return out


def consumes(body, token):
    return ('var(%s)' % token) in body or ('var(%s,' % token) in body


# ── the markup universe (D5) ──────────────────────────────────────────────────────

def markup_classes():
    """Every class the document can carry: static class= in panel.html, plus every
    class string any module can assign. A SUPERSET on purpose -- a class this scan
    cannot see would come out as a false dead reference."""
    files = [os.path.join(PANEL, 'panel.html')]
    for dirpath, dirnames, filenames in os.walk(PANEL):
        dirnames[:] = [d for d in dirnames if d not in ('node_modules', '.git')]
        for fn in filenames:
            if fn.endswith('.js'):
                files.append(os.path.join(dirpath, fn))
    uni = set()
    for f in files:
        text = read(f)
        for m in re.finditer(r'class="([^"]*)"', text):
            uni.update(m.group(1).split())
        for m in re.finditer(r"className\s*=\s*['\"]([^'\"]*)['\"]", text):
            uni.update(m.group(1).split())
        for m in re.finditer(r"classList\.(?:add|toggle|remove)\(\s*['\"]([^'\"]+)['\"]", text):
            uni.add(m.group(1))
    return uni, files


def css_classes(rules):
    """[(class, prelude, line)] for every class token in a selector."""
    out = []
    for prelude, _body, line in rules:
        for m in re.finditer(r'\.(-?[_a-zA-Z][\w-]*)', prelude):
            out.append((m.group(1), prelude, line))
    return out


# ── the manifest (D7/D8) ──────────────────────────────────────────────────────────

def manifest_entries(text):
    return re.findall(r"name:\s*'([^']+)',\s*label:\s*'([^']+)'", text)


def skin_labels():
    """{id: label} out of the frozen skins bundle (minified JSON in one line)."""
    text = read(SKINS)
    out = {}
    for m in re.finditer(r'"(cine-[a-z0-9-]+)":\{"bindings"', text):
        key = m.group(1)
        tail = text[m.start():m.start() + 20000]
        lab = re.search(r'"label":"([^"]+)"', tail)
        if lab:
            out[key] = lab.group(1)
    return out


# ── the arms ──────────────────────────────────────────────────────────────────────

def tune_tokens():
    """The tokens `theme-tune.js` can write, read out of the module itself (never a
    copy of its list). The four D3 tokens are a subset; the audit's '13/17' count was
    about this list, so the gate measures the whole dialog and not only the four."""
    src = read(os.path.join(PANEL, 'theme-tune.js'))
    return re.findall(r"token:\s*'(--[a-z0-9-]+)'", src)


def panel_consumers():
    """Tokens consumed by rules that apply to ANY theme: `panel.css` and
    `caption-float.css` are unscoped, so a theme's value for them is read directly.
    This is the alias bridge — a theme declares `--font: var(--font-sans)` and
    panel.css reads `--font`, which is what makes the dialog's font knob live."""
    out = set()
    for fn in ('panel.css', 'caption-float.css'):
        p = os.path.join(PANEL, fn)
        if os.path.exists(p):
            for _pre, body, _l in rules_of(read(p)):
                for m in re.finditer(r'var\(\s*(--[a-z0-9-]+)', body):
                    out.add(m.group(1))
    return out


def arm_a(rules):
    """D3 -- A1: the four dead tokens, strictly per theme. A2: EVERY token the tuning
    dialog can write, per theme, through the alias bridge (the dialog is the thing the
    owner turns; four live knobs beside thirteen dead ones would still be a broken
    dialog)."""
    blocks = theme_blocks(rules)
    strict_live = 0
    strict_total = 0
    bad = []
    for family, ids in FAMILIES.items():
        for t in ids:
            strict_total += len(CLOSED)
            if t not in blocks:
                bad.append('%s: no token block' % t)
                continue
            decl = '\n'.join(blocks[t])
            for tok in CLOSED:
                declared = bool(re.search(r'(?m)^\s*%s\s*:' % re.escape(tok), decl))
                consumed = any(consumes(b, tok) for _p, b, _l in scoped_rules(rules, t))
                if declared and consumed:
                    strict_live += 1
                else:
                    bad.append('%s %s declared=%s consumed=%s' % (t, tok, declared, consumed))
    toks = tune_tokens()
    bridge = panel_consumers()
    tune_live = 0
    tune_total = 0
    for family, ids in FAMILIES.items():
        for t in ids:
            tune_total += len(toks)
            block = '\n'.join(blocks.get(t, []))
            live = set(bridge)
            for _p, b, _l in scoped_rules(rules, t):
                for m in re.finditer(r'var\(\s*(--[a-z0-9-]+)', b):
                    live.add(m.group(1))
            alias = {}
            for m in re.finditer(r'(--[a-z0-9-]+)\s*:\s*var\(\s*(--[a-z0-9-]+)', block):
                alias.setdefault(m.group(1), set()).add(m.group(2))
            changed = True
            while changed:
                changed = False
                for a, bs in alias.items():
                    if a in live:
                        for b in bs:
                            if b not in live:
                                live.add(b)
                                changed = True
            miss = [x for x in toks if x not in live]
            tune_live += len(toks) - len(miss)
            for x in miss:
                bad.append('%s %s (dialog token)' % (t, x))
    return {
        'ok': strict_live == strict_total and tune_live == tune_total,
        'detail': '%d/%d D3 pairs live; %d/%d dialog-token pairs live (%d tokens x 25 themes)'
                  % (strict_live, strict_total, tune_live, tune_total, len(toks)),
        'bad': bad,
    }


def arm_b(rules):
    """D5 -- no selector names a class the document cannot carry."""
    uni, files = markup_classes()
    dead = []
    seen = 0
    for cls, prelude, line in css_classes(rules):
        seen += 1
        if cls not in uni:
            dead.append('%s (line %d: %s)' % (cls, line, prelude[:70]))
    return {
        'ok': not dead,
        'detail': '%d class reference(s) against a %d-name universe from %d file(s); %d dead'
                  % (seen, len(uni), len(files), len(dead)),
        'bad': dead,
        'info': 'universe built from panel.html + %d module(s)' % (len(files) - 1),
    }


def arm_c(rules, css):
    """D6 -- every token declared here has a reader somewhere; and the names this lane
    removed are really gone.

    The declarations are read out of the PARSED rule bodies and not off line starts,
    because a mutant can write a declaration on the same line as its selector
    (`sel { --busy: x; }`) and the first version of this arm missed exactly that:
    measured, M3 stayed GREEN and the gate was silently blind to its own defect."""
    declared = set()
    for _prelude, body, _line in rules:
        for m in re.finditer(r'(?<![\w-])(--[a-z0-9-]+)\s*:', body):
            declared.add(m.group(1))
    declared = sorted(declared)
    others = []
    for dirpath, dirnames, filenames in os.walk(PANEL):
        dirnames[:] = [d for d in dirnames if d not in ('node_modules', '.git')]
        for fn in filenames:
            if fn.endswith(('.css', '.js', '.html')):
                p = os.path.join(dirpath, fn)
                if os.path.abspath(p) != os.path.abspath(args.file):
                    others.append(p)
    others.append(SHELL)
    other_text = '\n'.join(read(p) for p in others if os.path.exists(p))
    dead = []
    external_only = []
    for tok in declared:
        inside = consumes(css, tok)
        outside = consumes(other_text, tok)
        if not inside and not outside:
            dead.append(tok)
        elif not inside:
            external_only.append(tok)
    still_there = [t for t in REMOVED if t in declared]
    return {
        'ok': not dead and not still_there,
        'detail': '%d token(s) declared; %d with NO reader anywhere; %d of the removed names still declared'
                  % (len(declared), len(dead), len(still_there)),
        'bad': dead + ['%s (removed, still declared)' % t for t in still_there],
        'info': ('read only outside this file: ' + ', '.join(external_only)) if external_only else '',
    }


def arm_d(themes_text):
    """D7/D8 -- labels unique, and the shared ids agree with the skin that mounts."""
    entries = manifest_entries(themes_text)
    names = [n for n, _l in entries]
    labels = [l for _n, l in entries]
    bad = []
    dup_names = sorted({n for n in names if names.count(n) > 1})
    dup_labels = sorted({l for l in labels if labels.count(l) > 1})
    if dup_names:
        bad.append('duplicate names: %s' % ', '.join(dup_names))
    if dup_labels:
        bad.append('duplicate labels: %s' % ', '.join(dup_labels))
    skin = skin_labels()
    shared = 0
    mismatched = []
    for n, l in entries:
        if n in skin:
            shared += 1
            if skin[n] != l:
                mismatched.append('%s picker=%r skin=%r' % (n, l, skin[n]))
    bad.extend(mismatched)
    pinned = {'cine-tideline-body': 'Tideline', 'cine-tideline': 'Tideline (wide)',
              'cine-cellar': 'Cellar', 'cine-linen': 'Linen'}
    for n, want in pinned.items():
        got = dict(entries).get(n)
        if got != want:
            bad.append('%s label %r != pinned %r' % (n, got, want))
    return {
        'ok': not bad,
        'detail': '%d entries, %d distinct names, %d distinct labels; %d shared with a frozen skin, %d label mismatch(es)'
                  % (len(entries), len(set(names)), len(set(labels)), shared, len(mismatched)),
        'bad': bad,
        'info': '%d frozen skin labels read from skins.js' % len(skin),
    }


def arm_e(css_path, themes_path, gen_path, workdir):
    """rule 10 -- the bytes on disk are a FRESH run of the generator, redirected."""
    spec = importlib.util.spec_from_file_location('gen_cinematic_oracle', gen_path)
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    out_css = os.path.join(workdir, 'fresh-cinematic.css')
    out_js = os.path.join(workdir, 'fresh-themes.js')
    out_bd = os.path.join(workdir, 'backdrops')
    os.makedirs(out_bd, exist_ok=True)
    # fetch_backdrop() reads the wallpapers from BACKDROPS; point it at the real ones
    # so no download is attempted and the emitted notes are the shipped ones.
    real_bd = os.path.join(PANEL, 'themes', 'backdrops')
    for fn in os.listdir(real_bd):
        if fn.endswith('.jpg'):
            shutil.copyfile(os.path.join(real_bd, fn), os.path.join(out_bd, fn))
    # manifest() reads the file it replaces to capture the five originals.
    shutil.copyfile(themes_path, out_js)
    g.CSS_OUT = out_css
    g.JS_OUT = out_js
    g.BACKDROPS = out_bd
    # The generator prints its theme table; this oracle prints its own report.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = g.main()
    if rc != 0:
        return {'ok': False, 'detail': 'the generator refused (rc=%d)' % rc, 'bad': []}
    a, b = sha256(css_path), sha256(out_css)
    c, d = sha256(themes_path), sha256(out_js)
    bad = []
    if a != b:
        bad.append('css %s != fresh %s' % (a[:16], b[:16]))
    if c != d:
        bad.append('manifest %s != fresh %s' % (c[:16], d[:16]))
    return {
        'ok': not bad,
        'detail': 'css %s, manifest %s == a fresh run' % (a[:16], d[:16]),
        'bad': bad,
    }


def arm_f(rules):
    """Pins -- the four values are each zip's own, family by family."""
    blocks = theme_blocks(rules)
    bad = []
    # THE PIN IS THE SHIPPED FORM, and the shipped form carries the owner's font dial.
    # RE-ANCHORED 2026-10-20: `--caption-scale` is the MULTIPLIER of the transcript
    # font dial (`app/panel/panel.js:306` -- "THE TRANSCRIPT FONT DIAL (owner,
    # 2026-10-09)"), written on the document element at `panel.js:2312` and read by
    # the CSS. The generator now carries it on BOTH terms of the floor -- the zip's
    # own 0.66 ratio AND the 13 px floor -- because a hard 13 px floor was a SECOND,
    # invisible size dial fighting the visible one (`_main/_design-lane/
    # gen_cinematic.py:260-271`, the generator's own words: "NEITHER TERM CARRIED
    # THE DIAL ... that is the 'inconsistent size' the owner reports").
    # MEASURED 2026-10-20 on `app/panel/themes/cinematic.css`: 15 declarations carry
    # `max(13px * var(--caption-scale), calc(var(--size-caption) * 0.66 *
    # var(--caption-scale)))` -- the 9 `cinematic-1` + the 6 `cinematic-2` themes --
    # and 10 carry the `cinematic` family's own fixed `13px` (its zip's ghost line:
    # `gen_cinematic.py:249` and `CLOSED_SOURCE` at :285), which does not move with
    # the dial because that family never had a `max()` to scale.
    # PINNING THE DIAL IN is what gives this arm its teeth over the dial: drop
    # `--caption-scale` from the product and this pin goes RED, which is exactly the
    # defect the generator's comment is about.
    want = {
        'cinematic': {'--size-closed': '13px', '--leading-closed': '1.375',
                      '--weight-closed': '300', '--motion-in': '150ms'},
        'cinematic-1': {'--size-closed': 'max(13px * var(--caption-scale), calc(var(--size-caption) * 0.66 * var(--caption-scale)))',
                        '--leading-closed': '1.45', '--motion-in': '320ms'},
        'cinematic-2': {'--size-closed': 'max(13px * var(--caption-scale), calc(var(--size-caption) * 0.66 * var(--caption-scale)))',
                        '--motion-in': '300ms'},
    }
    checked = 0
    for family, ids in FAMILIES.items():
        for t in ids:
            decl = '\n'.join(blocks.get(t, []))
            for tok, val in want[family].items():
                checked += 1
                m = re.search(r'(?m)^\s*%s\s*:\s*([^;]+);' % re.escape(tok), decl)
                got = m.group(1).strip() if m else 'ABSENT'
                if got != val:
                    bad.append('%s %s = %r, want %r' % (t, tok, got, val))
            if family == 'cinematic-1':
                checked += 1
                if not re.search(r'(?m)^\s*--weight-closed\s*:\s*var\(--weight-caption\)', decl) \
                   and '--weight-closed: var(--weight-caption)' not in decl:
                    # apply_closed() writes the theme's own caption weight literally
                    m = re.search(r'(?m)^\s*--weight-closed\s*:\s*([^;]+);', decl)
                    w = re.search(r'(?m)^\s*--weight-caption\s*:\s*([^;]+);', decl)
                    if not (m and w and m.group(1).strip() == w.group(1).strip()):
                        bad.append('%s --weight-closed != --weight-caption' % t)
            if family == 'cinematic-2':
                checked += 1
                m = re.search(r'(?m)^\s*--leading-closed\s*:\s*([^;]+);', decl)
                w = re.search(r'(?m)^\s*--leading-caption\s*:\s*([^;]+);', decl)
                if not (m and w and m.group(1).strip() == w.group(1).strip()):
                    bad.append('%s --leading-closed != --leading-caption' % t)
    return {
        'ok': not bad,
        'detail': '%d pinned value(s) match the zip, family by family' % checked,
        'bad': bad,
    }


def run_arms(css_path, themes_path, gen_path, with_generator, workdir):
    css = read(css_path)
    rules = rules_of(css)
    results = [
        ('A', arm_a(rules)),
        ('B', arm_b(rules)),
        ('C', arm_c(rules, css)),
        ('D', arm_d(read(themes_path))),
        ('F', arm_f(rules)),
    ]
    if with_generator:
        results.append(('E', arm_e(css_path, themes_path, gen_path, workdir)))
    return results


# ── the negative arm: each defect injected into a COPY ────────────────────────────

def mutate_css(src, dst, old, new, count=1):
    text = read(src)
    if old not in text:
        raise SystemExit('mutant anchor not found: %r' % old[:60])
    shutil.copyfile(src, dst)
    with io.open(dst, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text.replace(old, new, count))
    return dst


def neg_arm(args):
    tmp = tempfile.mkdtemp(prefix='cine-neg-')
    css = args.file
    themes = args.themes
    mutants = []
    # M1 -- D3: one theme stops consuming --size-closed (the literal comes back).
    # THE ANCHOR IS THE SHIPPED FORM (re-anchored 2026-10-20). The owner's font dial
    # `--caption-scale` is a MULTIPLIER, so the generator emits the closed line as
    # `calc(var(--size-caption) * 0.72 * var(--caption-scale))` and NOT the old
    # `calc(var(--size-caption) * 0.72)` (`_main/_design-lane/gen_cinematic.py:958`).
    # MEASURED 2026-10-20 on `app/panel/themes/cinematic.css`: the old anchor has
    # count=0 -- which is why this arm died with "mutant anchor not found" -- and
    # the shipped one has count=10, the first at `cinematic.css:251`, inside
    # `:root[data-theme='cine-midnight-rain'] .caption:not(.caption--latest)
    # .caption__text` -- a THEME scope, and the set-wide block
    # (`:root[data-theme^='cine-']`) does not read `--size-closed` at all (measured:
    # 0 of the shared rules read it). So the mutant really does take that theme's
    # only `var(--size-closed)` reader away, and the D3 arm goes RED.
    m1 = mutate_css(css, os.path.join(tmp, 'm1.css'),
                    'font-size: var(--size-closed, calc(var(--size-caption) * 0.72 * var(--caption-scale)));',
                    'font-size: calc(var(--size-caption) * 0.72 * var(--caption-scale));')
    mutants.append(('M1 one theme stops consuming --size-closed (the D3 defect)', m1, themes, 'A'))
    # M2 -- D5: a scoped selector that matches no node of the real markup.
    m2 = mutate_css(css, os.path.join(tmp, 'm2.css'),
                    ":root[data-theme='cine-cellar'] .caption__text {",
                    ":root[data-theme='cine-cellar'] .chrome__key,\n:root[data-theme='cine-cellar'] .caption__text {")
    mutants.append(('M2 a selector that matches no node (the D5 defect)', m2, themes, 'B'))
    # M3 -- D6: a token declared and read by nothing (the D6 defect).
    m3 = mutate_css(css, os.path.join(tmp, 'm3.css'),
                    ":root[data-theme='cine-cellar'] .caption__text {",
                    ":root[data-theme='cine-cellar'] { --busy: #fff; }\n:root[data-theme='cine-cellar'] .caption__text {")
    mutants.append(('M3 a token declared with no reader (the D6 defect)', m3, themes, 'C'))
    # M4 -- D7: two entries with one label.
    text = read(themes)
    m4 = os.path.join(tmp, 'm4.js')
    with io.open(m4, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text.replace("label: 'North Fog'", "label: 'Tideline'"))
    mutants.append(('M4 two picker entries share a label (the D7 defect)', css, m4, 'D'))
    # M5 -- D8: the picker label stops agreeing with the skin that mounts.
    m5 = os.path.join(tmp, 'm5.js')
    with io.open(m5, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text.replace("label: 'Cellar'", "label: 'Cellar Sessions'"))
    mutants.append(('M5 picker label != the mounted skin (the D8 defect)', css, m5, 'D'))
    # M6 -- rule 10: one byte changed, so the file is no longer the generator's output.
    m6 = mutate_css(css, os.path.join(tmp, 'm6.css'),
                    ':root[data-theme=', ':root[data-theme =', count=1)
    mutants.append(('M6 a hand edit (rule 10: not the generator output)', m6, themes, 'E'))

    print('')
    print('NEG-ARM -- each defect injected into a COPY, the SAME predicate re-run')
    control = run_arms(css, themes, args.generator, False, tmp)
    control_bad = [n for n, r in control if not r['ok']]
    print('  CONTROL GREEN  failed=%s' % (','.join(control_bad) if control_bad else 'none'))
    print('')
    wrong = 0
    inert = 0
    for label, c, t, target in mutants:
        with_gen = (target == 'E')
        res = run_arms(c, t, args.generator, with_gen, tmp)
        reds = [n for n, r in res if not r['ok']]
        ok = target in reds
        if not ok:
            wrong += 1
        if not reds:
            inert += 1
        print('  %s %s' % ('PASS' if ok else 'FAIL', label))
        print('        want RED on %s   got RED on %s' % (target, ','.join(reds) if reds else 'NONE'))
        for n, r in res:
            if not r['ok'] and r['bad']:
                print('        %s: %s' % (n, '; '.join(r['bad'])[:150]))
    print('')
    verdict = (not control_bad) and wrong == 0 and inert == 0
    print('NEG-ARM VERDICT: %s -- %d mutant(s), %d wrong, %d inert, control %s'
          % ('PASS' if verdict else 'FAIL', len(mutants), wrong, inert,
             'GREEN' if not control_bad else 'RED'))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if verdict else 1


# ── report ────────────────────────────────────────────────────────────────────────

def main():
    global args
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', default=DEFAULT_CSS)
    ap.add_argument('--themes', default=DEFAULT_THEMES)
    ap.add_argument('--generator', default=DEFAULT_GEN)
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--skip-generator', action='store_true')
    args = ap.parse_args()

    if args.neg_arm:
        return neg_arm(args)

    css = read(args.file)
    print('CINEMATIC-DESIGNS ORACLE -- PRISTINE (the bytes on disk)')
    print('  file:    %s' % os.path.abspath(args.file))
    print('           %d B, sha256 %s' % (os.path.getsize(args.file), sha256(args.file)[:16].upper()))
    print('  manifest:%s' % os.path.abspath(args.themes))
    print('')
    tmp = tempfile.mkdtemp(prefix='cine-oracle-')
    try:
        results = run_arms(args.file, args.themes, args.generator,
                           not args.skip_generator, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    failed = 0
    for name, r in results:
        if not r['ok']:
            failed += 1
        print('  %s  %s %s' % ('ok  ' if r['ok'] else 'FAIL', name, r['detail']))
        if r.get('info'):
            print('        %s' % r['info'])
        for b in r['bad'][:8]:
            print('        %s' % b)
    print('')
    print('%d check(s), %d failed' % (len(results), failed))
    print('VERDICT: %s' % ('PASS' if failed == 0 else 'FAIL'))
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
