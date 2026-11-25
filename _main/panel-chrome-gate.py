#!/usr/bin/env python3
# NO-BUG: instrumento do contrato de CHROME do painel (dono, 2026-10-14/10-18 e
# 2026-11-06). Nao corrige defeito: le os bytes que sao enviados e recusa que as
# palavras retiradas, as linhas de chrome, os seletores mortos ou as leituras
# inventadas voltem -- sem largar browser nenhum, que e' o que impede este
# contrato de ficar sem portao na bateria.
"""panel-chrome-gate -- the panel's CHROME contract, WITHOUT launching a browser.

WHY IT EXISTS. `_main/_panel-chrome-arm.py` is the full instrument for this area
and it is the RIGHT one when a painted claim is needed: it builds a copy of
`panel.html`, loads it in headless Chromium and reads the DOM the real renderer
produced. It also LAUNCHES A BROWSER, so it cannot run in the battery -- and an
area whose only gate cannot run is an area with no gate, which is exactly what
`_main/cobertura-oracle.py` says about it. This file is the STATIC half: the same
contract, read out of the shipped bytes, nothing launched.

THE CONTRACT, and every owner order it comes from:

  2026-10-14  *"tira em curso e historico das barras. o dono quer as barras
              LIMPAS."*                     -> `tele`'s two footer labels go.
  2026-10-18  *"tirar rascunho live / escrito ao ouvído"*  -> `mano`'s phrase goes.
  2026-11-06  *"NO DIRECTION-SPECIFIC FOOTER ... the meter, `LIVE / EM ESPERA`,
              `· · ·` and `OUVINDO / EM ESPERA` were words about the panel, not
              facts."*                      -> EVERY direction's chrome row goes.

So the live contract today is ZERO chrome, and it has four halves that can drift
independently -- which is why this gate reads all four and not just one:

  ARM A  THE WORDS. `HISTÓRICO`, `EM CURSO`, `rascunho live` and
         `escrito ao ouvído` appear in `panel.html` ONLY inside the HTML comments
         that explain their removal -- not one live node carries them, and the
         note itself must survive (a removal nobody can trace is the next
         regression). The 2026-11-06 words are covered by ARM B, which forbids
         the ROW rather than the word.
  ARM B  THE ROWS. No element carries `data-chrome=` at all. The real status
         surface is `#status-dot` + `#status-text`, which must still be there --
         a panel with no status and a panel with no chrome are different failures
         and the gate names them separately.
  ARM C  THE SHEETS. No `.chrome`, `.chrome--*` or `.chrome__*` SELECTOR in any
         shipped stylesheet, `panel.css` included. A rule about a node the
         document cannot carry is a rule about nothing; comments are exempt
         (they are the record of why the rules left).
  ARM D  THE GENERATORS. `gen_themes.py` and `gen_cinematic.py` emit no chrome
         selector and hold no `CHROME` / `STRIP_GUARD` table -- otherwise the
         next regeneration brings the dead rules back.
  ARM E  THE REPLACEMENT IS REAL. The five skins build their own chrome:
         `skin-host.js` mounts the fragment's `chrome` into `.skin__chrome`, and
         `skin-layout.css` carries no chrome rule (it used to hide ours).
  ARM F  NO INVENTED READINGS. The mockups' CONF 0.93 / buffer 38ms are a
         simulated script; this panel has no such measurement and must not print
         one.

THE CONTROL IS FOUR MUTANTS, NOT A COMMENT (`--neg-arm`). Each is a COPY of the
shipped bytes under `$TMPDIR` with ONE half of the contract reverted:
  M1  the `tele` footer spans (HISTÓRICO / ▲ EM CURSO) are put BACK into the
      markup -- the exact regression of 2026-10-14.           -> ARM A must go RED
  M2  a `.chrome--tele[data-chrome="foot"]` rule is put BACK into `theme-1.css`
      -- the dead rule the generator used to emit.            -> ARM C must go RED
  M3  `#status-text` is DELETED from the markup -- then "no chrome" would be
      satisfied by a panel that also lost its status.         -> ARM B must go RED
  M4  the mockups' invented reading `CONF 0.93` is written into the markup.
                                                              -> ARM F must go RED
Every mutant names the anchor it edits and verifies the anchor's COUNT before
writing: a mutant that cannot run is a gate that cannot say no.

WHAT THIS DOES NOT COVER, stated rather than implied: it reads BYTES, so it
cannot see a rule that is present but loses the cascade, a node hidden by
`display:none` somewhere else, or anything the browser synthesises. That is what
`_main/_panel-chrome-arm.py` is for, and the two are complements, not rivals.

NOTHING IS LAUNCHED: no browser, no shell, no worker, no WebView2. `TMPDIR` is
honoured.

Usage:
  py -3 _main/panel-chrome-gate.py             the shipped panel
  py -3 _main/panel-chrome-gate.py --neg-arm   the four controls, must be RED
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(ROOT, 'app', 'panel')
THEMES = os.path.join(PANEL, 'themes')
GEN = os.path.join(HERE, '_design-lane', 'gen_themes.py')
GEN_CINE = os.path.join(HERE, '_design-lane', 'gen_cinematic.py')

# The console on this box is cp1252 and the words this gate measures are UTF-8
# (HISTÓRICO with an acute). Without this the run prints mojibake -- an
# instrument that cannot print what it measured is not an instrument.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# The words the owner ordered off the bars, each with the order that removed it.
# They may survive ONLY inside the comment that explains the removal.
ORDERED_OFF = (
    ('HIST\u00d3RICO', '2026-10-14 "tira em curso e historico das barras"'),
    ('EM CURSO', '2026-10-14 "tira em curso e historico das barras"'),
    ('rascunho live', '2026-10-18 "tirar rascunho live / escrito ao ouvido"'),
    ('escrito ao ouv\u00eddo', '2026-10-18 "tirar rascunho live / escrito ao ouvido"'),
)
# The mockups' invented readings (same list as `_panel-chrome-arm.py`).
FORBIDDEN_TEXT = ('CONF', '48K', '380\u00d7900', '380x900', 'buffer', '0.93',
                  'PT-BR \u00b7 48')

# A selector that keys on the retired class. `\.chrome` matches `.chrome`,
# `.chrome--x` and `.chrome__y` and nothing else (`--size-chrome` is a custom
# property, not a class). It is looked for in SELECTOR position of a parsed rule,
# never in a comment.
CHROME_SELECTOR = re.compile(r'\.chrome(?![-\w])|\.chrome(?:--|__)[-\w]+')

COMMENT_RE = re.compile(r'<!--.*?-->', re.S)
CSS_COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)
RULE_RE = re.compile(r'([^{}]+)\{([^{}]*)\}')


def read(path, newline=''):
    """No newline translation: these files are CRLF and a mutant copy must keep
    the line endings of the original, or the anchor stops matching."""
    with open(path, encoding='utf-8', errors='replace', newline=newline) as fh:
        return fh.read()


def comments_only(path):
    """Every HTML comment, joined -- the only place a retired word may live."""
    return '\n'.join(COMMENT_RE.findall(read(path)))


def strip_html_comments(text):
    return COMMENT_RE.sub('', text)


def strip_css_comments(text):
    return CSS_COMMENT_RE.sub('', text)


def css_files(panel):
    """Every stylesheet in the tree UNDER TEST (never the shipped one)."""
    out = []
    for base in (panel, os.path.join(panel, 'themes')):
        if not os.path.isdir(base):
            continue
        for name in sorted(os.listdir(base)):
            if name.endswith('.css'):
                out.append(os.path.join(base, name))
    return out


def chrome_selectors(text):
    """[(selector, rule_text)] of every rule whose SELECTOR keys on `.chrome`."""
    out = []
    for m in RULE_RE.finditer(strip_css_comments(text)):
        selector = re.sub(r'\s+', ' ', m.group(1)).strip()
        if selector.startswith('@'):
            continue
        if CHROME_SELECTOR.search(selector):
            out.append((selector, m.group(0)))
    return out


def arm_a(panel):
    """The owner's words: gone from live markup, still in the note."""
    bad = []
    html = read(os.path.join(panel, 'panel.html'))
    stripped = strip_html_comments(html)
    notes = comments_only(os.path.join(panel, 'panel.html'))
    for word, order in ORDERED_OFF:
        if word in stripped:
            bad.append('"%s" is still LIVE markup in panel.html (%d occurrence(s) '
                       'outside a comment) -- that is the %s regression'
                       % (word, stripped.count(word), order))
        elif word not in notes:
            bad.append('"%s" is gone from panel.html ENTIRELY -- not even the note '
                       'explaining the removal survives, so nobody can find out why '
                       'it left (%s)' % (word, order))
    return bad


def arm_b(panel):
    """No chrome rows at all, and the real status surface is still there."""
    bad = []
    stripped = strip_html_comments(read(os.path.join(panel, 'panel.html')))
    rows = re.findall(r'<[^>]*data-chrome="[a-z]+"[^>]*>', stripped)
    if rows:
        bad.append('the document still carries %d chrome row(s), e.g. %r'
                   % (len(rows), rows[0][:100]))
    for node in ('id="status-dot"', 'id="status-text"'):
        if node not in stripped:
            bad.append('the real status surface lost %s -- "no chrome" must not be '
                       'satisfied by a panel with no status either' % node)
    return bad


def arm_c(panel):
    """No shipped sheet styles a `.chrome*` selector."""
    bad = []
    for path in css_files(panel):
        hits = chrome_selectors(read(path))
        if hits:
            bad.append('%s still styles %d chrome rule(s): %r'
                       % (os.path.relpath(path, panel), len(hits),
                          [s for s, _ in hits[:3]]))
    return bad


def arm_d(gen):
    """The generators emit none, so a regeneration cannot bring them back.

    The test is the SHAPE OF A RULE, not the word: a chrome selector immediately
    followed by a declaration block on the same line. Both generators keep prose
    that names the retired class (the note explaining WHY it left, and two
    docstrings) — that prose is the record this repo requires, and a gate that
    read it as an emitter would force the reason out of the file.
    """
    bad = []
    emitter = re.compile(r'\.chrome(?:--|__)?[-\w]*[^\n{}]*\{')
    for path in (gen, GEN_CINE):
        text = read(path)
        live = [ln.strip() for ln in text.splitlines() if emitter.search(ln)]
        if live:
            bad.append('%s still EMITS `.chrome` on %d line(s): %r'
                       % (os.path.basename(path), len(live), live[:3]))
        for table in ('CHROME = {}', 'CHROME[1] =', 'STRIP_GUARD =', 'PD_CHROME_META ='):
            if table in text:
                bad.append('%s still holds the %s table' % (os.path.basename(path), table))
    return bad


def arm_e(panel):
    """The skins' own chrome is what replaced it, and it is still wired."""
    bad = []
    host = os.path.join(panel, 'skin-host.js')
    text = read(host)
    if 'skin__chrome' not in text:
        bad.append('skin-host.js no longer builds the `.skin__chrome` node')
    if 'frag.chrome' not in text:
        bad.append('skin-host.js no longer reads the fragment\'s own `chrome`')
    skin_css = chrome_selectors(read(os.path.join(panel, 'skin-layout.css')))
    if skin_css:
        bad.append('skin-layout.css still styles %r' % [s for s, _ in skin_css[:3]])
    return bad


def arm_f(panel):
    bad = []
    stripped = strip_html_comments(read(os.path.join(panel, 'panel.html')))
    for word in FORBIDDEN_TEXT:
        if word in stripped:
            bad.append("the panel prints the mockups' invented reading %r" % word)
    return bad


ARMS = [
    ("ARM A the owner's words are off the bars", arm_a),
    ('ARM B no chrome row, and the real status is still there', arm_b),
    ('ARM C no shipped sheet styles a chrome selector', arm_c),
    ('ARM D the generators emit none', arm_d),
    ('ARM E the skins carry the chrome now', arm_e),
    ('ARM F no invented readings', arm_f),
]


def run(panel, gen):
    """Returns the list of failures for one revision ([] == GREEN)."""
    fails = []
    for label, fn in ARMS:
        try:
            got = fn(panel) if fn is not arm_d else fn(gen)
        except Exception as exc:  # noqa: BLE001 -- report, never crash the gate
            got = ['raised %s: %s' % (type(exc).__name__, exc)]
        for line in got:
            fails.append('%s: %s' % (label, line))
    return fails


def scratch_tree(tag):
    """A COPY of the shipped panel + generators, for one mutant."""
    base = os.path.join(os.environ.get('TMPDIR') or os.environ.get('TEMP') or HERE,
                        'panel-chrome-gate-' + tag)
    if os.path.exists(base):
        shutil.rmtree(base, ignore_errors=True)
    os.makedirs(os.path.join(base, 'themes'))
    shutil.copy2(os.path.join(PANEL, 'panel.html'), os.path.join(base, 'panel.html'))
    for name in sorted(os.listdir(PANEL)):
        if name.endswith('.css') or name == 'skin-host.js':
            shutil.copy2(os.path.join(PANEL, name), os.path.join(base, name))
    for name in sorted(os.listdir(THEMES)):
        if name.endswith('.css'):
            shutil.copy2(os.path.join(THEMES, name),
                         os.path.join(base, 'themes', name))
    gen = os.path.join(base, 'gen_themes.py')
    shutil.copy2(GEN, gen)
    shutil.copy2(GEN_CINE, os.path.join(base, 'gen_cinematic.py'))
    return base, gen


def report(label, got, ok):
    red = bool(got)
    print('NEG-ARM %-46s %s' % (label, 'RED as expected' if red
                                else 'STILL GREEN -- the gate cannot say no'))
    for line in got[:4]:
        print('        ' + line[:150])
    return ok and red


def rewrite(path, before, after, label):
    """Replace exactly one anchor; report rather than guess when it is gone."""
    text = read(path)
    n = text.count(before)
    if n != 1:
        print('NEG-ARM %s: CONTROL IS DEAD (anchor count=%d)' % (label, n))
        return False
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text.replace(before, after, 1))
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', default=PANEL)
    ap.add_argument('--gen', default=GEN)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    print('panel : %s' % args.panel)
    print('gen   : %s' % args.gen)
    print('html  : %d B' % os.path.getsize(os.path.join(args.panel, 'panel.html')))
    print('sheets: %d' % len(css_files(args.panel)))

    if not args.neg_arm:
        fails = run(args.panel, args.gen)
        for line in fails:
            print('   FAIL ' + line)
        print('VERDICT: ' + ('FAIL' if fails else 'PASS'))
        return 1 if fails else 0

    live = run(args.panel, args.gen)
    ok = not live
    print('control: the shipped panel is GREEN (%d failure(s))' % len(live))
    for line in live:
        print('   LIVE ' + line)

    # ── M1: the tele footer labels, put back (the 2026-10-14 regression) ─────
    base, gen = scratch_tree('m1')
    anchor = '      <footer class="status" id="status">'
    back = (anchor + '\n'
            '        <span class="chrome chrome--tele" data-chrome="foot" '
            'data-slot="start">HIST\u00d3RICO</span>\n'
            '        <span class="chrome chrome--tele" data-chrome="foot" '
            'data-slot="end">\u25b2 EM CURSO</span>')
    if rewrite(os.path.join(base, 'panel.html'), anchor, back, 'M1 tele labels back'):
        ok = report('M1 tele labels back', run(base, gen), ok)

    # ── M2: a dead chrome rule, put back into theme-1.css ────────────────────
    base, gen = scratch_tree('m2')
    sheet = os.path.join(base, 'themes', 'theme-1.css')
    marker = "\n:root[data-theme='theme-1'] .wordmark__text {"
    rule = ("\n:root[data-theme='theme-1'] "
            ".chrome--tele[data-chrome=\"foot\"] { display: block; }\n")
    if rewrite(sheet, marker, rule + marker, 'M2 chrome rule back'):
        ok = report('M2 chrome rule back', run(base, gen), ok)

    # ── M3: the real status surface removed (so "no chrome" is not enough) ───
    base, gen = scratch_tree('m3')
    anchor = '<span class="status__text" id="status-text">'
    if not rewrite(os.path.join(base, 'panel.html'), anchor, '<span>', 'M3 status-text gone'):
        base = None
    if base:
        ok = report('M3 status-text gone', run(base, gen), ok)

    # ── M4: an invented reading, the mockups' `CONF 0.93` ────────────────────
    base, gen = scratch_tree('m4')
    anchor = '      <footer class="status" id="status">'
    if rewrite(os.path.join(base, 'panel.html'), anchor,
               anchor + '\n        <span class="chrome__meter">CONF 0.93</span>',
               'M4 invented reading'):
        ok = report('M4 invented reading', run(base, gen), ok)

    print('VERDICT: ' + ('PASS' if ok else 'FAIL') + '  (every mutant RED=%s)' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
