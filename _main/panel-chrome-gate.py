#!/usr/bin/env python3
"""panel-chrome-gate -- the theme chrome contract, WITHOUT launching a browser.

WHY IT EXISTS. `_main/_panel-chrome-arm.py` is the full instrument for this area
and it is the RIGHT one when a painted claim is needed: it builds a copy of
`panel.html`, loads it in headless Chromium and reads the DOM the real renderer
produced. It also LAUNCHES A BROWSER, so it cannot run in the battery -- and an
area whose only gate cannot run is an area with no gate, which is exactly what
`_main/cobertura-oracle.py` says about it. This file is the STATIC half: the same
contract, read out of the shipped bytes, nothing launched.

THE CONTRACT, and the owner's own words (2026-10-14): *"tira em curso e historico
das barras. o dono quer as barras LIMPAS."* Those two words were the Teleprompter
direction's own FOOTER chrome -- HISTORICO in the `start` slot, EM CURSO in the
`end` one -- and BOTH SPANS WERE DELETED FROM THE MARKUP. The other four
directions keep their own footer chrome, because the owner named `em curso` and
`historico` and nothing else.

  ARM A  THE OWNER'S ORDER. The two words appear in `panel.html` ONLY inside an
         HTML comment (the note explaining the removal), and the `tele`
         direction has NO footer block at all.
  ARM B  THE OTHER FOUR KEEP THEIRS. `bcast` (meter + LIVE/EM ESPERA), `mano`
         ("- escrito ao ouvído"), `cine` ("- - -") and `inst` (meter +
         OUVINDO/EM ESPERA) still carry their own footer chrome. A gate that only
         checked the removal would pass on a panel with NO footer chrome at all.
  ARM C  THE CSS AGREES. Zero `chrome--tele[data-chrome="foot"]` rules in every
         generated sheet, and at least one for each of the other four, in the
         theme sheet that owns the direction AND in `panel-designs.css`.
  ARM D  THE GENERATOR AGREES. A rule about a node that no longer exists is a
         rule about nothing: `gen_themes.py` emits no `tele` footer rule either.
  ARM E  THE CLASS CONTRACT IS INTACT. Every element carrying `data-chrome=` also
         carries the chrome class pair -- `chrome` plus `chrome--<direction>` --
         because that pair is what the five stylesheets key on, and all five HEAD
         blocks still exist.
  ARM F  NO INVENTED READINGS. The mockups' CONF 0.93 / buffer 38ms are a
         simulated script; this panel has no such measurement and must not print
         one.

THE CONTROL IS THREE MUTANTS, NOT A COMMENT (`--neg-arm`). Each is a COPY of the
shipped bytes under `$TMPDIR` with ONE half of the mechanism reverted:
  M1  the two `tele` footer spans are PUT BACK into the markup;
        (RE-ANCHORED 2026-10-20, lane caption -- the anchor MOVED, the mutation
         did NOT. The old anchor was the `mano` FOOTER span, which the product
         DELETED on 2026-10-18 (owner: *"tirar rascunho live / escrito ao
         ouvido"*): `mano` moved UP to the head row and, like `tele`, carries no
         footer block at all. The anchor was dead (count=0), so the control was a
         MUTANT THAT COULD NOT RUN -- "CONTROL IS DEAD" means this gate could not
         say no. The anchor is now the node that exists today, `panel.html:245`,
         and its count is VERIFIED to be 1 before the mutation runs.)
  M2  the chrome class contract is renamed (`class="chrome` ->
      `class="chrome-off`), the same mutation `_panel-chrome-arm.py --neg-arm`
      calls `markup`;
  M3  a `chrome--tele[data-chrome="foot"]` rule is PUT BACK into `theme-1.css`.

WHAT THIS DOES NOT COVER, stated rather than implied: it reads BYTES, so it
cannot see a rule that is present but loses the cascade, a node hidden by
`display:none` somewhere else, or anything the browser synthesises. That is what
`_main/_panel-chrome-arm.py` is for, and the two are complements, not rivals.

NOTHING IS LAUNCHED: no browser, no shell, no worker, no WebView2. `TMPDIR` is
honoured.

Usage:
  py -3 _main/panel-chrome-gate.py             the shipped panel
  py -3 _main/panel-chrome-gate.py --neg-arm   the three controls, must be RED
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
GEN = os.path.join(HERE, '_design-lane', 'gen_themes.py')

# The console on this box is cp1252 and the words this gate measures are UTF-8
# (HISTORICO with an acute, the middle dot of the cine footer). Without this the
# run prints mojibake -- an instrument that cannot print what it measured is not
# an instrument, which is the same reason `_panel-chrome-arm.py` reconfigures.
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# The five directions, the theme sheet that owns each, and the FOOTER chrome each
# one is expected to carry. `tele` is the direction the owner emptied.
DIRS = {
    'tele':  ('theme-1.css', []),
    'bcast': ('theme-2.css', [('start', None), ('end', 'LIVE')]),
    # EMPTY ON PURPOSE (owner, 2026-10-18). `mano` used to carry
    # `- escrito ao ouvído` and now carries no footer block at all, the same
    # shape as `tele`. ARM B skips an empty row -- that is its documented
    # behaviour -- so the demand on `bcast`, `cine` and `inst` is untouched.
    # ARM A is what holds this one down: the words must be absent from live
    # markup and present only in the note that explains the removal.
    'mano':  ('theme-3.css', []),
    'cine':  ('theme-4.css', [('start', '\u00b7 \u00b7 \u00b7')]),
    'inst':  ('theme-5.css', [('start', None), ('end', 'OUVINDO')]),
}
SHEETS = ['theme-1.css', 'theme-2.css', 'theme-3.css', 'theme-4.css',
          'theme-5.css', 'panel-designs.css']

# The words the owner ordered off the bars. They may survive ONLY inside the
# comment that explains the removal.
# 2026-10-18: two more, verbatim from the owner -- *"tirar rascunho live /
# escrito ao ouvído"*. Same rule, same reason: `rascunho live` claimed the forming
# line is a DRAFT and `— escrito ao ouvído` was decoration in the `mano` footer.
# Both are now absent from live markup and present only in the note that says so.
ORDERED_OFF = ('HIST\u00d3RICO', 'EM CURSO', 'rascunho live', 'escrito ao ouvído')
# The mockups' invented readings (same list as `_panel-chrome-arm.py`).
FORBIDDEN_TEXT = ('CONF', '48K', '380\u00d7900', '380x900', 'buffer', '0.93',
                  'PT-BR \u00b7 48')

COMMENT_RE = re.compile(r'<!--.*?-->', re.S)


def read(path, newline=''):
    """No newline translation: these files are CRLF and a mutant copy must keep
    the line endings of the original, or the anchor stops matching."""
    with open(path, encoding='utf-8', errors='replace', newline=newline) as fh:
        return fh.read()


def strip_html_comments(text):
    return COMMENT_RE.sub('', text)


def strip_css_comments(text):
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


def foot_blocks(stripped):
    """Every footer chrome block: (direction, slot, the block's own text).

    The block's text runs from its opening tag to the next `data-chrome=` or the
    end of the footer, which covers the nested state span of `bcast`/`inst` as
    well as the inline text of `mano`/`cine`. A regex that tried to match the
    closing tag would have to parse HTML nesting, and a gate that guesses at
    nesting is a gate that lies about what it read.
    """
    out = []
    open_re = re.compile(
        r'<(\w+)[^>]*class="chrome chrome--([a-z0-9]+)"[^>]*data-chrome="foot"'
        r'[^>]*data-slot="([a-z]+)"[^>]*>')
    for m in open_re.finditer(stripped):
        start = m.end()
        nxt = stripped.find('data-chrome=', start)
        endf = stripped.find('</footer>', start)
        stop = min(x for x in (nxt, endf, len(stripped)) if x >= 0)
        out.append((m.group(2), m.group(3), stripped[start:stop]))
    return out


def head_blocks(stripped):
    out = []
    open_re = re.compile(
        r'<(\w+)[^>]*class="chrome chrome--([a-z0-9]+)"[^>]*data-chrome="head"')
    for m in open_re.finditer(stripped):
        out.append(m.group(2))
    return out


def arm_a(panel, gen, stripped):
    """The owner's order: the words survive ONLY in a comment, `tele` has no foot."""
    bad = []
    raw = read(os.path.join(panel, 'panel.html'))
    for word in ORDERED_OFF:
        if word in stripped:
            bad.append('"%s" is still LIVE markup in panel.html (%d occurrence(s) '
                       'outside a comment)' % (word, stripped.count(word)))
        elif word not in raw:
            bad.append('"%s" is gone from panel.html ENTIRELY -- not even the note '
                       'explaining the removal survives, so nobody can find out why '
                       'it left' % word)
    tele_feet = [b for b in foot_blocks(stripped) if b[0] == 'tele']
    if tele_feet:
        bad.append('the tele direction still carries %d footer block(s): %r'
                   % (len(tele_feet), [b[1] for b in tele_feet]))
    return bad


def arm_b(panel, gen, stripped):
    """The other four directions keep their own footer chrome."""
    bad = []
    by_dir = {}
    for d, slot, text in foot_blocks(stripped):
        by_dir.setdefault(d, []).append((slot, text))
    for d, (_sheet, want) in sorted(DIRS.items()):
        if not want:
            continue
        have = by_dir.get(d, [])
        if not have:
            bad.append('the %s direction lost its footer chrome entirely' % d)
            continue
        slots = [s for s, _ in have]
        for slot, word in want:
            if slot not in slots:
                bad.append('the %s direction lost its %s slot' % (d, slot))
                continue
            if word is None:
                continue
            text = ''.join(t for s, t in have if s == slot)
            if word not in text:
                bad.append('the %s %s slot reads %r, expected it to carry %r'
                           % (d, slot, ' '.join(text.split())[:60], word))
    return bad


def arm_c(panel, gen, stripped):
    """The CSS agrees: no `tele` foot rule anywhere, the other four keep theirs."""
    bad = []
    for sheet in SHEETS:
        path = os.path.join(panel, 'themes', sheet)
        if not os.path.exists(path):
            bad.append('the generated sheet %s is missing' % sheet)
            continue
        text = strip_css_comments(read(path))
        tele = len(re.findall(r'chrome--tele[^\n{]*data-chrome="foot"', text))
        if tele:
            bad.append('%s still carries %d chrome--tele footer rule(s)' % (sheet, tele))
        for d, (owner, want) in sorted(DIRS.items()):
            if not want:
                continue
            n = len(re.findall(r'chrome--%s[^\n{]*data-chrome="foot"' % d, text))
            if sheet in (owner, 'panel-designs.css') and not n:
                bad.append('%s carries no chrome--%s footer rule' % (sheet, d))
    return bad


def arm_d(panel, gen, stripped):
    """The generator emits no `tele` footer rule either."""
    bad = []
    text = read(gen)
    live = re.findall(r"chrome--tele[^\n']*data-chrome=[\"']foot", text)
    if live:
        bad.append('gen_themes.py still emits %d chrome--tele footer rule(s): %r'
                   % (len(live), live[:2]))
    for d, (_owner, want) in sorted(DIRS.items()):
        if not want:
            continue
        if not re.search(r"chrome--%s[^\n']*data-chrome=['\"]foot" % d, text):
            bad.append('gen_themes.py no longer emits the chrome--%s footer rule' % d)
    return bad


def arm_e(panel, gen, stripped):
    """The class contract the stylesheets key on, and the five head blocks."""
    bad = []
    for m in re.finditer(r'<(\w+)([^>]*data-chrome="[a-z]+"[^>]*)>', stripped):
        attrs = m.group(2)
        cm = re.search(r'class="([^"]*)"', attrs)
        if not cm:
            bad.append('a data-chrome element carries no class attribute: %r'
                       % m.group(0)[:80])
            continue
        classes = cm.group(1).split()
        if 'chrome' not in classes:
            bad.append('a data-chrome element is not class="chrome ...": %r'
                       % m.group(0)[:80])
        if not any(c.startswith('chrome--') for c in classes):
            bad.append('a data-chrome element carries no chrome--<direction> class: '
                       '%r' % m.group(0)[:80])
    heads = set(head_blocks(stripped))
    for d in sorted(DIRS):
        if d not in heads:
            bad.append('the %s direction lost its HEAD chrome block' % d)
    return bad


def arm_f(panel, gen, stripped):
    bad = []
    for word in FORBIDDEN_TEXT:
        if word in stripped:
            bad.append("the panel prints the mockups' invented reading %r" % word)
    return bad


ARMS = [
    ("ARM A the owner's order (both words off the bars)", arm_a),
    ('ARM B the other four directions keep their footer', arm_b),
    ('ARM C the generated CSS agrees', arm_c),
    ('ARM D the generator agrees', arm_d),
    ('ARM E the class contract and the five head blocks', arm_e),
    ('ARM F no invented readings', arm_f),
]


def run(panel, gen):
    """Returns the list of failures for one revision ([] == GREEN)."""
    fails = []
    stripped = strip_html_comments(read(os.path.join(panel, 'panel.html')))
    for label, fn in ARMS:
        try:
            got = fn(panel, gen, stripped)
        except Exception as exc:  # noqa: BLE001 -- report, never crash the gate
            got = ['raised %s: %s' % (type(exc).__name__, exc)]
        for line in got:
            fails.append('%s: %s' % (label, line))
    return fails


def scratch_tree(tag):
    """A COPY of the shipped panel + generator, for one mutant."""
    base = os.path.join(os.environ.get('TMPDIR') or os.environ.get('TEMP') or HERE,
                        'panel-chrome-gate-' + tag)
    if os.path.exists(base):
        shutil.rmtree(base, ignore_errors=True)
    os.makedirs(os.path.join(base, 'themes'))
    shutil.copy2(os.path.join(PANEL, 'panel.html'), os.path.join(base, 'panel.html'))
    for sheet in SHEETS:
        src = os.path.join(PANEL, 'themes', sheet)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(base, 'themes', sheet))
    gen = os.path.join(base, 'gen_themes.py')
    shutil.copy2(GEN, gen)
    return base, gen


def report(label, got, ok):
    red = bool(got)
    print('NEG-ARM %-46s %s' % (label, 'RED as expected' if red
                                else 'STILL GREEN -- the gate cannot say no'))
    for line in got[:4]:
        print('        ' + line[:150])
    return ok and red


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', default=PANEL)
    ap.add_argument('--gen', default=GEN)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    print('panel : %s' % args.panel)
    print('gen   : %s' % args.gen)
    print('html  : %d B' % os.path.getsize(os.path.join(args.panel, 'panel.html')))

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

    # ── M1: the two tele footer spans, put back ──────────────────────────────
    # RE-ANCHORED 2026-10-20 (lane caption). The anchor was the `mano` FOOTER
    # span -- `        <span class="chrome chrome--mano" data-chrome="foot"
    # data-slot="start">` -- which the product DELETED on 2026-10-18 (owner:
    # *"tirar rascunho live / escrito ao ouvido"*). `mano` moved UP to the head
    # row (`panel.html:245`, `        <div class="chrome chrome--mano"
    # data-chrome="head">`) and, like `tele`, carries no footer block at all.
    # The old anchor therefore had count=0 and the mutant COULD NOT RUN: the
    # gate could not say no, which is worse than a red gate.
    # THE MUTATION IS UNCHANGED -- the two `tele` footer spans are put back into
    # the markup, which is exactly what ARM A is about (the words live only in
    # the note that explains the removal, and `tele` has no footer). Only the
    # ANCHOR MOVED, and its count is checked to be exactly 1 before the copy is
    # written.
    base, gen = scratch_tree('m1')
    path = os.path.join(base, 'panel.html')
    html = read(path)
    anchor = '        <div class="chrome chrome--mano" data-chrome="head">'
    if html.count(anchor) != 1:
        print('NEG-ARM M1 tele labels back: CONTROL IS DEAD (anchor count=%d)'
              % html.count(anchor))
        ok = False
    else:
        back = ('        <span class="chrome chrome--tele" data-chrome="foot" '
                'data-slot="start">HIST\u00d3RICO</span>\n'
                '        <span class="chrome chrome--tele" data-chrome="foot" '
                'data-slot="end">\u25b2 EM CURSO</span>\n' + anchor)
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(html.replace(anchor, back, 1))
        ok = report('M1 tele labels back', run(base, gen), ok)

    # ── M2: the chrome class contract renamed ────────────────────────────────
    base, gen = scratch_tree('m2')
    path = os.path.join(base, 'panel.html')
    html = read(path)
    n = html.count('class="chrome')
    if n == 0:
        print('NEG-ARM M2 class renamed: CONTROL IS DEAD (anchor count=0)')
        ok = False
    else:
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(html.replace('class="chrome', 'class="chrome-off'))
        ok = report('M2 class renamed (%d block(s))' % n, run(base, gen), ok)

    # ── M3: a tele footer rule, put back into theme-1.css ────────────────────
    base, gen = scratch_tree('m3')
    path = os.path.join(base, 'themes', 'theme-1.css')
    css = read(path)
    marker = '\n:root[data-theme=\'theme-1\'] .chrome--tele[data-chrome="head"] {'
    if css.count(marker) != 1:
        print('NEG-ARM M3 tele foot rule back: CONTROL IS DEAD (anchor count=%d)'
              % css.count(marker))
        ok = False
    else:
        rule = ('\n:root[data-theme=\'theme-1\'] '
                '.chrome--tele[data-chrome="foot"] { display: block; }\n')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            fh.write(css.replace(marker, rule + marker, 1))
        ok = report('M3 tele foot rule back', run(base, gen), ok)

    print('VERDICT: ' + ('PASS' if ok else 'FAIL') + '  (every mutant RED=%s)' % ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
