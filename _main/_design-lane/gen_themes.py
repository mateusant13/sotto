#!/usr/bin/env python3
"""GENERATOR for the Sotto theme files.

TWO SETS, TWO ZIPS, ONE DOCTRINE
--------------------------------
* `app/panel/themes/theme-1..5.css` <- `zips/directions/`. These ARE the owner's
  five design DIRECTIONS -- Teleprompter, Broadcast, Manuscrito, Cartao de
  Cinema, Instrumento -- and the numbering is the zip's own (`num: "01".."05"`
  in `designs.ts`).
* `app/panel/themes/panel-designs.css` + `.js` <- `zips/panel-designs/`. That
  zip REUSES the same five names over a DIFFERENT implementation (its own
  palette, its own components, five button-free panels with every control on the
  stage). It shipped as nothing at all, so it is a SET of its own here, under
  `pd-*` ids, and its five entries are APPENDED to the same manifest.

A VALUE THIS FILE CANNOT FIND IS A BUILD FAILURE, NOT A DEFAULT. That is the
whole point of the rewrite. `gen_cinematic.py` (this directory) established the
rule for the cinematic zip; the gap audit
(`I:/cc-tmp/theme-system-gap-audit.md`) then measured that THIS file instead
carried the five directions as a hand-written Python list which parsed NO zip at
all -- `designs.ts` appeared only in comments -- so the fidelity of
`theme-1..5.css` to the zip the owner shipped was UNMEASURED and could drift
with no build noticing. Now:

    designs.ts   ids, numbers, names, models, accents, font classes
    index.css    the @theme palette (13 colours) and the font stacks (7)
    Caption.tsx  the live line: size, leading, weight, tracking, colours
    Panel.tsx    the panel surface, the header, the history rows, the footer
    Stage.tsx    the direction switcher and the control cluster
    bits.tsx     the level meter

are PARSED, and every value a theme emits is registered in LEDGER with the
`file:line` it came from. `--trace` prints that ledger as a Markdown table;
`--check` refuses to write a theme whose ledger is missing a required token. So
"this theme is the zip's design" is a printed artefact of the generation, not a
comment someone wrote once.

WHAT IS *NOT* A ZIP VALUE, and where each of those lives
--------------------------------------------------------
* SELECTORS. The zip is a Vite mockup whose DOM is `<div class="sotto-panel">`,
  `.sotto-caption` and a per-design `<p>` branch. Sotto's panel is its own
  document (`app/panel/panel.html`) with `.caption__text`, `.captions__body`,
  `.history__row`, `.chrome`, `.panel__controls`. A theme paints SOTTO's nodes
  with the zip's VALUES; it cannot mount the zip's markup, and pretending
  otherwise is exactly the "skin por cima" the owner refuses. `SKIN` is that
  translation, written once and shared by the five.
* THE LAYOUT of Sotto's own chrome rows (`CHROME[n]`): the widths, the gaps and
  the order of our own controls. Each block names the zip line it mirrors and
  the anchors are re-asserted at build time.
* THE BUTTON POSITION -- the owner's ONE permitted deviation, verbatim: "cada
  tema encontrado dentro dos .zip, fiquem com o design IGUAL, e so muda a posicao
  dos botoes". In the zip every control sits OUTSIDE the panel, on the stage:
  `Stage.tsx:146` is the bottom-left cluster (play, speed pills, scene pills)
  and `Stage.tsx:92` is the direction strip. Sotto's panel is a 380x900 overlay
  with no stage under it, so the cluster has to live INSIDE the panel; where is
  each direction's own answer, and it is the only thing that may differ from the
  zip.
* THE SPACING SCALE, THE RADIUS SCALE AND THE STATE PALETTE. The zip declares
  ONE spacing scale, ONE radius scale and ONE state palette for all five designs
  (`index.css:3-25`), so all five themes sharing them is the zip's own structure
  and not a flattening -- and it is STATED here rather than hidden. Where the
  zip's own designs ARE alike, shipping them alike is correct; the file has to
  say so instead of advertising a difference the CSS does not have.

Run: `py -3 _main/_design-lane/gen_themes.py`            (regenerate, byte-stable)
     `py -3 _main/_design-lane/gen_themes.py --trace`    (the provenance table)
     `py -3 _main/_design-lane/gen_themes.py --check`    (writes nothing, gates)
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
OUT = os.path.join(ROOT, 'app', 'panel', 'themes')
ZIPS = os.path.join(HERE, 'zips')

# --------------------------------------------------------------------------- #
# THE TWO ZIPS, FILE BY FILE. Every path is checked at read time, so a zip that
# was moved or re-extracted is a build failure and not a silent fallback.
# --------------------------------------------------------------------------- #
DIR = os.path.join(ZIPS, 'directions')
DIR_DESIGNS = os.path.join(DIR, 'src', 'data', 'designs.ts')
DIR_CSS = os.path.join(DIR, 'src', 'index.css')
DIR_CAPTION = os.path.join(DIR, 'src', 'components', 'Caption.tsx')
DIR_PANEL = os.path.join(DIR, 'src', 'components', 'Panel.tsx')
DIR_STAGE = os.path.join(DIR, 'src', 'components', 'Stage.tsx')
DIR_BITS = os.path.join(DIR, 'src', 'components', 'bits.tsx')

PD = os.path.join(ZIPS, 'panel-designs')
PD_CSS = os.path.join(PD, 'src', 'index.css')
PD_PANELS = os.path.join(PD, 'src', 'components', 'panels.tsx')
PD_STAGE = os.path.join(PD, 'src', 'components', 'Stage.tsx')
PD_SCRIPTS = os.path.join(PD, 'src', 'lib', 'scripts.ts')


def where(path):
    """The zip-relative path a ledger row prints."""
    return os.path.relpath(path, ZIPS).replace(os.sep, '/')


def slurp(path):
    if not os.path.exists(path):
        raise SystemExit('BUILD FAILURE: the zip source is missing: %s' % path)
    with open(path, encoding='utf-8') as fh:
        return fh.read().replace('\r\n', '\n').split('\n')


def at(lines, path, needle, start=0):
    """The 1-based line number of the first line containing `needle`.

    A miss is a BUILD FAILURE. There is deliberately no "search the whole file
    for something similar" fallback: an anchor that moved means the zip changed
    and a human has to look, which is the opposite of a silent default.
    """
    for i in range(start, len(lines)):
        if needle in lines[i]:
            return i + 1
    raise SystemExit('BUILD FAILURE: %r is not in %s' % (needle, where(path)))


# --------------------------------------------------------------------------- #
# THE LEDGER. Every value a theme emits is registered here with the zip line it
# came from. `--trace` prints it; `--check` gates on it.
# --------------------------------------------------------------------------- #
LEDGER = []


def note(n, token, value, src):
    LEDGER.append((n, token, value, src))
    return value


class Theme(dict):
    """A theme's tokens, plus the `file:line` each one came from."""

    def __init__(self, n, **kw):
        dict.__init__(self, n=n, src={}, **kw)

    def put(self, key, value, src):
        self[key] = value
        self['src'][key] = src
        note(self['n'], key, value, src)
        return value


# --------------------------------------------------------------------------- #
# THE ZIP'S OWN @theme BLOCK -- the palette and the font stacks. One block, at
# `index.css:3-25`, shared by all five designs.
# --------------------------------------------------------------------------- #
def parse_at_theme(path):
    lines = slurp(path)
    start = at(lines, path, '@theme')
    out = {}
    for i in range(start, len(lines)):
        ln = lines[i]
        if ln.strip().startswith('}'):
            break
        m = re.match(r'\s*--([A-Za-z0-9-]+):\s*(.+?);\s*$', ln)
        if m:
            out[m.group(1)] = (m.group(2).strip(), i + 1)
    if not out:
        raise SystemExit('BUILD FAILURE: %s declares no custom property' % where(path))
    return out


PALETTE_KEYS = ('ink', 'ink2', 'ink3', 'bone', 'fog', 'ember', 'lagoon',
                'signal', 'paper', 'pencil', 'gold', 'led', 'amberlite')
FONT_KEYS = ('display', 'body', 'tele', 'bcast', 'mano', 'cine', 'inst')


def zip_palette():
    raw = parse_at_theme(DIR_CSS)
    pal, src = {}, {}
    for key in PALETTE_KEYS:
        if 'color-' + key not in raw:
            raise SystemExit('BUILD FAILURE: --color-%s is not declared in %s'
                             % (key, where(DIR_CSS)))
        pal[key] = raw['color-' + key][0]
        src[key] = '%s:%d' % (where(DIR_CSS), raw['color-' + key][1])
    return pal, src


def zip_fonts():
    raw = parse_at_theme(DIR_CSS)
    fonts, src = {}, {}
    for key in FONT_KEYS:
        if 'font-' + key not in raw:
            raise SystemExit('BUILD FAILURE: --font-%s is not declared in %s'
                             % (key, where(DIR_CSS)))
        fonts[key] = raw['font-' + key][0]
        src[key] = '%s:%d' % (where(DIR_CSS), raw['font-' + key][1])
    return fonts, src


# --------------------------------------------------------------------------- #
# designs.ts -- the five directions' own identity.
# --------------------------------------------------------------------------- #
def parse_designs():
    lines = slurp(DIR_DESIGNS)
    start = at(lines, DIR_DESIGNS, 'export const DESIGNS')
    out, cur = [], None
    for i in range(start, len(lines)):
        ln = lines[i]
        m = re.match(r'\s*id:\s*"([a-z]+)"', ln)
        if m:
            cur = {'id': m.group(1), 'id_line': i + 1}
            out.append(cur)
        if cur is None:
            continue
        for key in ('num', 'name', 'model', 'spec', 'accent', 'fontClass'):
            m = re.match(r'\s*%s:\s*"([^"]*)"' % key, ln)
            if m:
                cur[key] = m.group(1)
                cur[key + '_line'] = i + 1
    if len(out) != 5:
        raise SystemExit('BUILD FAILURE: designs.ts declares %d designs, not 5' % len(out))
    for d in out:
        for key in ('num', 'name', 'accent', 'fontClass'):
            if key not in d:
                raise SystemExit('BUILD FAILURE: design %r has no %s in %s'
                                 % (d['id'], key, where(DIR_DESIGNS)))
    return out


# --------------------------------------------------------------------------- #
# THE CLASS READER. The zip states its values inside Tailwind arbitrary-value
# classes (`bg-[#0b0c0f]/55`, `text-[clamp(30px,4.6vw,54px)]`, `tracking-[0.4em]`
# ...), so the reader's job is to turn one className expression into a class
# string and then to take ONE utility out of it, loudly failing when absent.
# --------------------------------------------------------------------------- #
def class_block(anchor):
    """`(path, needle, span)` -> (class string, 'file:line').

    `span` is how many lines the expression occupies, stated per anchor rather
    than guessed: the zip writes several of them as a two-line concatenation and
    a wrong window would silently drop a utility (which is the failure mode this
    whole rewrite exists to remove).
    """
    path, needle, span = anchor
    lines = slurp(path)
    i = at(lines, path, needle) - 1
    text = '\n'.join(lines[i:i + span])
    parts = re.findall(r'"([^"]*)"', text)
    if not parts:
        raise SystemExit('BUILD FAILURE: no quoted class at %s:%d'
                         % (where(path), i + 1))
    return ' '.join(parts), '%s:%d' % (where(path), i + 1)


WEIGHT = {'thin': 100, 'light': 300, 'normal': 400, 'medium': 500,
          'semibold': 600, 'bold': 700, 'extrabold': 800, 'black': 900}


def _grab(cls, pattern, what, src):
    m = re.search(pattern, cls)
    if not m:
        raise SystemExit('BUILD FAILURE: %s is not stated at %s (%r)' % (what, src, cls))
    return m


def u_size(cls, src):
    return _grab(cls, r'(?<![\w-])text-\[(clamp\([^)]*\)|\d+(?:\.\d+)?px)\]',
                 'a text-[...] size', src).group(1).replace(', ', ',')


def u_weight(cls, src, default=None):
    m = re.search(r'(?<![\w-])font-(thin|light|normal|medium|semibold|bold|extrabold|black)(?![\w-])', cls)
    if not m:
        if default is not None:
            return default
        raise SystemExit('BUILD FAILURE: no font weight at %s (%r)' % (src, cls))
    return str(WEIGHT[m.group(1)])


def u_leading(cls, src):
    return _grab(cls, r'(?<![\w-])leading-\[([^\]]+)\]', 'a leading-[...]', src).group(1)


def u_tracking(cls, src, default=None):
    m = re.search(r'(?<![\w-])tracking-\[([^\]]+)\]', cls)
    if m:
        return m.group(1)
    if default is not None:
        return default
    raise SystemExit('BUILD FAILURE: no tracking-[...] at %s (%r)' % (src, cls))


def u_has(cls, util):
    return bool(re.search(r'(?<![\w-])%s(?![\w-])' % util, cls))


NAMED = {'white': '#FFFFFF', 'black': '#000000'}


def rgba(hexv, a):
    h = hexv.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 'rgba(%d, %d, %d, %s)' % (r, g, b, ('%g' % a))


def alpha_tok(tok):
    if tok is None:
        return 1.0
    if tok.startswith('['):
        return float(tok[1:-1])
    return int(tok) / 100.0


def _colour_names(pal):
    return '|'.join(sorted(list(pal) + list(NAMED), key=len, reverse=True))


def colours_in(cls, pal, src, required=True):
    """EVERY named text colour in a class string, in source order.

    The order is the design's own ternary order (`i === last ? "text-white" :
    "text-paper/82"`), which is how the reader knows which one is the newest
    word without a second anchor.
    """
    out = []
    for m in re.finditer(r'(?<![\w-])text-(%s)(?:/(\d+))?(?![\w-])' % _colour_names(pal), cls):
        name, op = m.group(1), m.group(2)
        hexv = pal.get(name) or NAMED[name]
        out.append((rgba(hexv, alpha_tok(op)) if op else hexv.upper(),
                    'text-%s%s' % (name, '/' + op if op else '')))
    if not out and required:
        raise SystemExit('BUILD FAILURE: no named text colour at %s (%r)' % (src, cls))
    return out


def colour_in(cls, pal, src):
    return colours_in(cls, pal, src)[0]


def surface_in(cls, pal, src):
    """`bg-[#0b0c0f]/55` or `bg-paper/[0.06]` -> (hex, alpha, label)."""
    m = re.search(r'(?<![\w-])bg-\[(#[0-9a-fA-F]{3,8})\](?:/(\d+|\[[\d.]+\]))?', cls)
    if m:
        return (m.group(1).upper(), alpha_tok(m.group(2)),
                'bg-[%s]%s' % (m.group(1), '/' + m.group(2) if m.group(2) else ''))
    m = re.search(r'(?<![\w-])bg-(%s)(?:/(\d+|\[[\d.]+\]))?' % _colour_names(pal), cls)
    if m:
        hexv = pal.get(m.group(1)) or NAMED[m.group(1)]
        return (hexv.upper(), alpha_tok(m.group(2)),
                'bg-%s%s' % (m.group(1), '/' + m.group(2) if m.group(2) else ''))
    raise SystemExit('BUILD FAILURE: no bg surface at %s (%r)' % (src, cls))


def border_in(cls, pal, src):
    """`border-white/10`, `border-gold/15` -> (hex, alpha, label)."""
    m = re.search(r'(?<![\w-])border-(%s)(?:/(\d+|\[[\d.]+\]))?' % _colour_names(pal), cls)
    if not m:
        raise SystemExit('BUILD FAILURE: no border colour at %s (%r)' % (src, cls))
    hexv = pal.get(m.group(1)) or NAMED[m.group(1)]
    return (hexv.upper(), alpha_tok(m.group(2)),
            'border-%s%s' % (m.group(1), '/' + m.group(2) if m.group(2) else ''))


def shadow_in(cls, src):
    m = re.search(r'shadow-\[(.*?)\](?=\s|$)', cls)
    if not m:
        raise SystemExit('BUILD FAILURE: no shadow-[...] at %s (%r)' % (src, cls))
    return m.group(1).replace('_', ' ')


SCALE = {0: 0, 0.5: 2, 1: 4, 1.5: 6, 2: 8, 2.5: 10, 3: 12, 3.5: 14,
         4: 16, 5: 20, 6: 24, 7: 28, 8: 32, 9: 36, 10: 40, 14: 56}
STEP = r'(0\.5|1\.5|2\.5|3\.5|\d+(?:\.\d+)?)'


def pad_in(cls, src, axis):
    """The design's own padding on one axis, in px (`px-4` -> 16)."""
    for util in ('p' + axis, 'p'):
        m = re.search(r'(?<![\w-])%s-%s(?![\w.])' % (util, STEP), cls)
        if m and float(m.group(1)) in SCALE:
            return SCALE[float(m.group(1))], '%s-%s' % (util, m.group(1))
    raise SystemExit('BUILD FAILURE: no p%s-* at %s (%r)' % (axis, src, cls))


def dim_in(cls, util, src):
    """`w-[4px]`, `h-2` -> ('4px', 'w-[4px]')."""
    m = re.search(r'(?<![\w-])%s-\[([^\]]+)\]' % util, cls)
    if m:
        return m.group(1), '%s-[%s]' % (util, m.group(1))
    m = re.search(r'(?<![\w-])%s-%s(?![\w.])' % (util, STEP), cls)
    if m and float(m.group(1)) in SCALE:
        return '%dpx' % SCALE[float(m.group(1))], '%s-%s' % (util, m.group(1))
    raise SystemExit('BUILD FAILURE: no %s-* at %s (%r)' % (util, src, cls))


# --------------------------------------------------------------------------- #
# WHERE EACH DESIGN STATES EACH THING. Every entry is an ANCHOR -- a literal
# substring of the zip -- and `at()` turns it into a line number. A moved anchor
# is a build failure, so this table is the contract between the zip and the five
# CSS files.
# --------------------------------------------------------------------------- #
SPEC = {
    'tele': dict(
        caption_live=(DIR_CAPTION, 'glow-live text-left font-tele', 1),
        caption_words=(DIR_CAPTION, '"w-tele " + (i === forming.length', 1),
        surface=(DIR_PANEL, 'bg-[#0b0c0f]/55 border-white/10', 1),
        header=(DIR_PANEL, 'font-tele text-[12px] font-semibold tracking-[0.42em]', 1),
        history=(DIR_PANEL, '"line-in font-tele text-[16.5px]', 2),
        footer=(DIR_PANEL, 'border-t border-white/8 px-4 py-2.5 font-tele', 1),
        body=(DIR_PANEL, 'panel-scroll flex-1 overflow-y-auto px-4 py-3.5', 1),
        muted=(DIR_PANEL, 'border-t border-white/8 px-4 py-2.5 font-tele', 1),
        rail=None, wordmark='SOTTO',
    ),
    'bcast': dict(
        caption_live=(DIR_CAPTION, 'text-left font-bcast text-[clamp(18px,2.3vw,28px)]', 1),
        caption_words=(DIR_CAPTION, '"w-bcast " + (i === forming.length', 1),
        surface=(DIR_PANEL, 'bg-[#090d10]/70 border-white/12', 1),
        header=(DIR_PANEL, 'border-b border-white/10 px-3.5 py-2.5 font-bcast', 1),
        history=(DIR_PANEL, 'grid grid-cols-[24px_38px_1fr] gap-2 font-bcast text-[10.5px]', 1),
        history_newest=(DIR_PANEL, '<span className="text-white/60">', 1),
        history_oldest=(DIR_PANEL, '<span className="text-white/25">', 1),
        footer=(DIR_PANEL, 'border-t border-white/10 px-3.5 py-2.5 font-bcast', 1),
        body=(DIR_PANEL, 'panel-scroll flex-1 overflow-y-auto px-4 py-3.5', 1),
        muted=(DIR_PANEL, 'border-t border-white/10 px-3.5 py-2.5 font-bcast', 1),
        rail=None, wordmark='REC',
    ),
    'mano': dict(
        caption_live=(DIR_CAPTION, 'text-left font-mano text-[clamp(21px,2.7vw,33px)]', 1),
        caption_words=(DIR_CAPTION, '"--ink-op": 0.45 + 0.55', 1),
        surface=(DIR_PANEL, 'bg-paper/[0.06] border-white/14', 1),
        header=(DIR_PANEL, 'font-mano text-[12.5px] italic text-bone/55', 1),
        history=(DIR_PANEL, 'line-in mb-3 font-mano text-[14px]', 1),
        footer=(DIR_PANEL, 'font-mano text-[11px] italic text-bone/40', 1),
        body=(DIR_PANEL, 'panel-scroll flex-1 overflow-y-auto px-4 py-3.5', 1),
        muted=(DIR_PANEL, 'font-mano text-[11px] text-bone/35', 1),
        rail=None, wordmark='rascunho ao vivo',
    ),
    'cine': dict(
        caption_live=(DIR_CAPTION, 'font-cine text-[clamp(24px,3vw,42px)]', 2),
        caption_words=(DIR_CAPTION, '"w-cine"', 1),
        surface=(DIR_PANEL, 'bg-[#0d0c09]/60 border-gold/15', 1),
        header=(DIR_PANEL, 'font-cine text-[11px] font-medium tracking-[0.34em]', 1),
        history=(DIR_PANEL, '"line-in mb-3.5 font-cine text-[15px]', 2),
        footer=(DIR_PANEL, 'font-cine text-[12px] tracking-[0.5em] text-gold/40', 1),
        body=(DIR_PANEL, 'panel-scroll flex-1 overflow-y-auto px-4 py-3.5', 1),
        muted=(DIR_PANEL, 'font-cine text-[11px] italic text-bone/40', 1),
        rail=(DIR_PANEL, 'border-l border-gold/50 pl-3', 1), wordmark='SOTTO',
    ),
    'inst': dict(
        caption_live=(DIR_CAPTION, 'text-left font-inst text-[clamp(24px,3.1vw,42px)]', 1),
        caption_words=(DIR_CAPTION, '"w-inst"', 1),
        surface=(DIR_PANEL, 'bg-[#090f0d]/65 border-led/15', 1),
        header=(DIR_PANEL, 'font-inst text-[11px] font-bold tracking-[0.3em]', 1),
        history=(DIR_PANEL, '"font-inst text-[13.5px] font-medium leading-[1.45] ', 1),
        footer=(DIR_PANEL, 'border-t border-white/10 px-4 py-2.5 font-inst', 1),
        body=(DIR_PANEL, 'panel-scroll flex-1 overflow-y-auto px-4 py-3.5', 1),
        muted=(DIR_PANEL, '<span className="ml-auto text-white/30">', 1),
        rail=(DIR_CAPTION, 'w-[4px] shrink-0 rounded-full bg-led', 1), wordmark='ON',
    ),
}

# THE DESIGN'S OWN LIVE-LINE MARK, read from the zip:
#   tele  none           -- `glow-live`, no rule anywhere on the line
#   bcast none           -- the caret is the signal colour; the line has no rule
#   mano  none           -- its mark is an UNDERLINE, and the signature block
#                           below emits it (`border-b border-bone/35`)
#   cine  border-l       -- `border-l border-gold/50 pl-3` on the forming row
#   inst  a 4 px LED rail -- `w-[4px] shrink-0 rounded-full bg-led`
# A `None` rail means the theme declares `border-left-width: 0`, which is a
# DECLARATION and not an omission: panel.css gives every provisional caption a
# rail, so a theme that wants none has to say so.
RAIL_W = {'tele': '0px', 'bcast': '0px', 'mano': '0px', 'cine': '1px', 'inst': '4px'}

# THE SPACING SCALE, THE RADIUS SCALE AND THE STATE PALETTE -- the zip declares
# ONE of each for all five designs, so all five themes share them. Stated, not
# hidden: see the module docstring.
TAILWIND = ('tailwindcss 4.1.17 default scale (the zip package.json)')
SPACE = (4, 8, 12, 16, 20)
RADIUS_SM = 4      # --radius-sm = rounded-sm = 0.25rem
RADIUS_MD = 6      # --radius-md = rounded-md = 0.375rem
RADIUS_LG = 8      # --radius-lg = rounded-lg = 0.5rem  <- the panel frame


def shared_state(pal, psrc):
    """The zip's own state palette, from its own named colours.

    The zip has no `--ok`/`--error` token pair; it has COLOURS, and three of
    them carry exactly those meanings in the mockups (`bg-led` on Instrumento's
    ON lamp, `bg-signal` on Broadcast's REC, `text-amberlite` on the freshest
    word). Naming them is this panel's job; inventing values is not.
    """
    return {
        'ok': (pal['led'].upper(), psrc['led']),
        'busy': (pal['amberlite'].upper(), psrc['amberlite']),
        'error': (pal['signal'].upper(), psrc['signal']),
        'idle': (pal['fog'].upper(), psrc['fog']),
    }


# --------------------------------------------------------------------------- #
# THE DESIGN'S OWN HALO. Teleprompter is the only direction that states one:
# `@keyframes glowPulse` at `index.css:146-149` and `.glow-live` at `:150`
# (2.6 s, the same period the signature block below uses). Read, not typed.
# --------------------------------------------------------------------------- #
def glow_shadow():
    lines = slurp(DIR_CSS)
    start = at(lines, DIR_CSS, '@keyframes glowPulse')
    for j in range(start, len(lines)):
        m = re.search(r'text-shadow:\s*([^;]+);', lines[j])
        if m:
            return m.group(1).strip(), '%s:%d' % (where(DIR_CSS), j + 1)
    raise SystemExit('BUILD FAILURE: @keyframes glowPulse states no text-shadow')


def glow_period():
    lines = slurp(DIR_CSS)
    i = at(lines, DIR_CSS, '.glow-live {')
    m = re.search(r'animation:\s*glowPulse\s+([\d.]+s)', lines[i - 1])
    if not m:
        raise SystemExit('BUILD FAILURE: .glow-live does not run glowPulse')
    return m.group(1), '%s:%d' % (where(DIR_CSS), i)


def raw_block(anchor):
    """Like class_block(), but the RAW source lines -- for a value the zip states
    in a style object rather than a className (mano's ink ramp)."""
    path, needle, span = anchor
    lines = slurp(path)
    i = at(lines, path, needle) - 1
    return '\n'.join(lines[i:i + span]), '%s:%d' % (where(path), i + 1)


# --------------------------------------------------------------------------- #
# fill() -- the marker language the signature blocks are written in.
#
# The signature blocks used to carry typed hex (`#FFC46B`, `#DCE4ED`,
# `rgba(242, 233, 216, .26)`), which is exactly how a theme drifts from the zip
# it claims to be: nothing connected the literal to the palette. They now carry
# MARKERS -- `@paper/26@`, `@amberlite@`, `@confirmed/80@` -- and this pass
# resolves each one against the theme's own tokens, recording a ledger row with
# the ORIGINAL zip line as its source. An unknown marker is a BUILD FAILURE, not
# an empty string. `@S@`/`@B@` are untouched (uppercase) -- they belong to
# scope().
# --------------------------------------------------------------------------- #
MARKER = re.compile(r'@([a-z0-9_]+)(?:/(\d+|\[[\d.]+\]))?@')


def fill(text, t):
    def sub(m):
        name, alpha = m.group(1), m.group(2)
        if name not in t:
            raise SystemExit('BUILD FAILURE: theme %s has no token %r'
                             % (t.get('name', t.get('n')), name))
        src = t['src'].get(name, '?')
        if alpha:
            val = rgba(t[name], alpha_tok(alpha))
            note(t['n'], 'sig:%s/%s' % (name, alpha), val, src)
        else:
            val = t[name]
            note(t['n'], 'sig:%s' % name, val, src)
        return val
    return MARKER.sub(sub, text)


# --------------------------------------------------------------------------- #
# THE SIGNATURE BLOCKS, verbatim from the file this rewrite replaces. Their
# prose is the owner's own record of what each direction asks for; only their
# LITERALS changed, into markers. They are spliced in by the build that produced
# this file, so nothing here was retyped.
# --------------------------------------------------------------------------- #
# THE SHARED FRAME: one line in the zip, used by all five designs.
FRAME = (DIR_PANEL, 'overflow-hidden rounded-lg border shadow-[0_28px_90px', 1)

# THE STAGE THE ZIP PUTS BEHIND EVERY PANEL -- and the reason the surface below is
# a COMPOSITE. Stage.tsx:46 is bg-black, so the zip's panel is only ever seen
# through its own alpha over black. A WebView2 window cannot blur the desktop
# behind it (backdrop-blur-md, Panel.tsx:30, blurs the PAGE, and Sotto's panel has
# no page behind it), so the theme paints the colour the zip actually shows and
# stays effectively opaque. HUE IS THE ZIP'S; ONLY THE ALPHA IS SOTTO'S.
STAGE = (DIR_STAGE, 'overflow-hidden bg-black', 1)
SLAB_OPACITY = '0.96'


def over_black(hexv, a):
    """`hexv` at alpha `a`, composited over the zip stage's opaque black."""
    h = hexv.lstrip('#')
    return '#' + ''.join('%02X' % round(int(h[i:i + 2], 16) * a) for i in (0, 2, 4))

IDEAS = {
    'tele': 'THE DIRECTION `tele`: the caption as a continuous reading flow. '
             'Barlow Condensed, near-white, RIGIDLY LEFT-ALIGNED, accent #f2e9d8. '
             'The forming line is the biggest, brightest and boldest thing on the '
             'slab and the closed lines are a quiet grey column behind it, so the '
             'eye is on the live line without being told to be. Nothing is boxed, '
             'nothing is decorated: no rail on the forming line, no rail on the '
             'closed ones. The "history recedes, only the now shines" rule of the '
             'direction is the SIZE and the HUE gap between the two states, plus '
             'the STATIC halo the forming line carries (`live_shadow`): the '
             'direction\'s own recommendation is "brilho, peso e um leve '
             'deslocamento optico bastam para mante-la acesa" — a glow is how the '
             'live line SHINES without blinking. It is a static text-shadow, never '
             'a keyframe, because the brief forbids animating the caption text.',
    'bcast': 'THE DIRECTION `bcast`: a transmission happening right now. IBM Plex '
             'Mono, timecodes and small state marks, accent #ff6a55. The forming '
             'line carries a SOLID 2 px signal-red rail and the most recent word is '
             'bright amber; a closed line has NO rail at all and falls to a neutral '
             'grey, so "being said" and "was said" are told apart by SHAPE before '
             'by hue — which is the direction\'s own recommendation ("instrumentation '
             'extremely subtle, never a dashboard").',
    'mano': 'THE DIRECTION `mano`: the caption is born in front of you. Newsreader '
             '— a serif — at the caption, accent #a9c1d9, so provisional text never '
             'reads as an error and history never reads as a broadcast. The forming '
             'line is a DRAFT: it carries a thin SOLID guide rail and its tail still '
             'in doubt is held back in ink grey while the words already confirmed '
             'inside it stand brighter. A closed line is settled text — no rail, '
             'plain weight — so what is provisional reads as unfinished, never as '
             'unreliable.',
    'cine': 'THE DIRECTION `cine`: minimal editorial presence, accent #e4b363. '
             'Fraunces, wide leading, and the direction\'s own mark on the state: '
             'the forming line is ITALIC and sits behind a warm gold rail, while the '
             'closed line is upright and solid — "the finished phrase is solid, the '
             'one in progress lives in the mist" (the direction\'s words). The gold '
             'is warm and low-contrast on purpose: this is the theme that can almost '
             'disappear over the film.',
    'inst': 'THE DIRECTION `inst`: it is ON, it is not an open window. Space '
             'Grotesk, accent #5fd3a7, and the direction\'s own dynamic element — '
             'the FORMING line carries a continuous 4 px LED rail on its left, the '
             'one thing that moves in this theme; closed lines are a settled column '
             'of readings behind a small square mark with no rail at all. Nothing '
             'else is decorated, which is the point: after a week the LED says '
             'everything without being read.',
}

SIG = {
    'tele': '''/* -- SIGNATURE, direction "tele" ------------------------------------------
   The live line BREATHES. That is the one thing this direction asks for that the
   shared caption contract forbids (the caption text is never animated), and it is
   honoured rather than fought: the glow is a TEXT-SHADOW keyframe on the one
   element that already carries a static halo (live_shadow in SKIN), so the
   resting state is the design\'s own and only the pulse is added. Words enter
   with a 6 px rise; paintWords already stamps --w-i, so no JS is needed here. */
@S@ .caption--provisional .caption__provisional .caption__word:last-child{
  color: var(--text-primary);
}
@media (prefers-reduced-motion: no-preference){
  @S@ .caption--provisional .caption__text{
    animation: sotto-1-glow 2.6s ease-in-out infinite;
  }
  @S@ .caption--provisional .caption__provisional .caption__word{
    display: inline-block;
    animation: sotto-1-rise .34s cubic-bezier(.2, .7, .2, 1) both;
  }
}
@keyframes sotto-1-glow{
  0%, 100%{ text-shadow: 0 0 16px @accent/26@, 0 2px 22px rgba(0, 0, 0, .6); }
  50%{ text-shadow: 0 0 30px @accent/50@, 0 2px 22px rgba(0, 0, 0, .6); }
}
@keyframes sotto-1-rise{
  from{ opacity: 0; transform: translateY(6px); }
  to{ opacity: 1; transform: none; }
}''',
    'bcast': '''/* -- SIGNATURE, direction "bcast" ------------------------------------------
   The live line is a TRANSMISSION: the caret is the signal colour and the
   freshest word is amber, so "being said" and "was said" are told apart by HUE
   so "being said" and "was said" are told apart by HUE alone -- the zip gives
   this direction NO rule on the live line, and the theme declares that. */
@S@ .caption--provisional .caption__text{
  font-size: var(--size-caption);
  line-height: var(--leading-caption);
}
@S@ .caption__mark{
  animation: sotto-caret 1.1s steps(1) infinite;
  color: var(--accent);
}
@S@ .caption--provisional .caption__provisional .caption__word:last-child{
  color: @busy@;
}
@media (prefers-reduced-motion: no-preference){
  @S@ .caption--provisional .caption__provisional .caption__word{
    display: inline-block;
    animation: sotto-2-rise .16s ease-out both;
  }
}
@keyframes sotto-2-rise{
  from{ opacity: .35; transform: translateY(2px); }
  to{ opacity: 1; transform: none; }
}''',
    'mano': '''/* -- SIGNATURE, direction "mano" -------------------------------------------
   The live line is a DRAFT ON PAPER: it sits on a thin baseline rule, it ends
   in a 2 px BAR caret instead of the typed glyph every other theme uses, and
   the words still in doubt are held back in ink while the ones already settled
   inside it stand brighter. CHROME already ramps each word through --w-op
   (stamped by paintWords); this signature is what makes that ramp slow enough
   to read as ink drying rather than a fade-out. */
/* underline uses the word itself: no box, no background, ever. */
@S@ .caption--provisional .caption__text{
  color: @text_confirmed@;
  border-bottom: 1px solid @text_confirmed/35@;
  padding-bottom: 4px;
}
@S@ .caption--provisional .caption__provisional .caption__word{
  opacity: var(--w-op, 1);
  transition: opacity 700ms ease;
}
@S@ .caption--provisional .caption__mark{
  animation: none;
  color: transparent;
  display: inline-block;
  width: 2px;
  height: .88em;
  margin-left: 6px;
  vertical-align: -0.06em;
  background: @text_confirmed/80@;
}
@media (prefers-reduced-motion: no-preference){
  @S@ .caption--provisional .caption__mark{
    animation: sotto-caret 1.06s steps(1) infinite;
  }
}
/* THE MID-RAIL (owner, 2026-10-09: the live line is read at the MIDDLE of the
   panel, not glued to its heel). The rail is a scroll box and the live line is
   its last row, so the space under it is the whole mechanism: the list keeps
   empty scroll at the bottom and stickToNewest parks the live line at the
   middle of the box. vh, not %, because percentage padding resolves against
   the box WIDTH (380 px) and this rail is ~830 px tall.
   WHY `calc(50vh - 94px)` AND NOT A ROUND vh: the value has to equal HALF THE
   RAIL, and the rail is not the viewport — the panel chrome (header, the
   collapsed transcript bar, the status bar, the gaps and the panel padding)
   eats 166 px of the 900 px window, so the rail is 734 px and its middle is
   367 px. A bare `44vh` (396 px) landed the live line 5% high, MEASURED
   (`_main/_design-lane/geom.py --surface panel --themes theme-3`):
   `live fromBottom=407.2` against `clientH=734`, i.e. half should be 367.
   With pad = 50vh - 94 px the live line lands at 367 at every window height,
   because the chrome is a CONSTANT 166 px and the relation is linear:
   pad = (viewportH - 166)/2 - 10.8 (the 10.8 px is the rail's own bottom
   inset, measured on the themes that have no padding at all).
   PANEL ONLY: the strip is a 100 px bar at the bottom of the screen and its
   subtitle is MEANT to be at the bottom. */
@S@ body[data-surface="panel"] .captions__body{
  padding-bottom: calc(50vh - 94px);
  -webkit-mask-image: linear-gradient(180deg, transparent 0, #000 120px);
  mask-image: linear-gradient(180deg, transparent 0, #000 120px);
}''',
    'cine': '''/* -- SIGNATURE, direction "cine" ------------------------------------------
   Two things only, both the direction\'s own: the forming line holds back (opacity
   .5) so a sentence reads as SETTLING rather than finished, and every word comes
   out of focus (wordFog -- a chair moving in a dark room). */
@S@ .caption--provisional .caption__text{
  opacity: .5;
}
@media (prefers-reduced-motion: no-preference){
  @S@ .caption--provisional .caption__provisional .caption__word{
    animation: sotto-4-fog .6s ease both;
  }
}
@keyframes sotto-4-fog{
  from{ filter: blur(3px); opacity: .25; }
  to{ filter: none; opacity: 1; }
}/* THE MID-RAIL (owner, 2026-10-09). Same mechanism and the same measured value
   as Manuscrito's: the rail is 734 px at a 900 px window, its middle is 367,
   so `calc(50vh - 94px)` parks the live line exactly there at any height. The
   cinema card gets a taller fade, because its wordmark sits at the bottom of
   the card and must not be washed out by it.
   PANEL ONLY: the strip's subtitle belongs at the bottom of the screen. */
@S@ body[data-surface="panel"] .captions__body{
  padding-bottom: calc(50vh - 94px);
  -webkit-mask-image: linear-gradient(180deg, transparent 0, #000 150px);
  mask-image: linear-gradient(180deg, transparent 0, #000 150px);
}
/* THE SETTLED LINE IS ITALIC; THE FORMING ONE IS NOT. The zip states
   font-light on cine's forming line (Caption.tsx:110) and italic on the line
   just above it (Caption.tsx:101), so --prov-style is "normal" for this
   direction and the italic is declared HERE, on the settled tier. Named
   deviation: Sotto merges the zip's two closed tiers -- the caption's last
   line (italic, Caption.tsx:101) and the panel's transcript column (upright,
   Panel.tsx:168) -- into ONE settled column, and the caption's own mark is the
   one this theme keeps. */
@B@ .caption:not(.caption--provisional) .caption__text{
  font-style: italic;
}''',
    'inst': '''/* -- SIGNATURE, direction "inst" ------------------------------------------
   The LED rail already breathes (sotto-5-led-live, emitted in CHROME with the
   4 px border this direction uses as its mark). What is missing is the TEXT: the
   direction is a heavy monitor face at tight leading, and its words should SNAP
   into place in two steps rather than glide -- only opacity moves, so it costs
   nothing composited. */
@media (prefers-reduced-motion: no-preference){
  @S@ .caption--provisional .caption__provisional .caption__word{
    display: inline-block;
    animation: sotto-5-snap .1s steps(2) both;
  }
}
@keyframes sotto-5-snap{
  from{ opacity: .3; }
  to{ opacity: 1; }
}''',
}



def build_direction_theme(n, d, pal, psrc, fonts, fsrc, ideas):
    """One direction -> one theme dict, every value carrying its zip line."""
    spec = SPEC[d['id']]
    t = Theme(n=n)
    t['id'] = d['id']
    t['name'] = d['name']
    t.put('idea', ideas[d['id']],
          '%s:%d (the direction the zip itself describes)' % (where(DIR_DESIGNS), d['name_line']))

    # ---- the design's identity, from designs.ts ---------------------------
    t.put('accent', d['accent'].upper(),
          '%s:%d (accent)' % (where(DIR_DESIGNS), d['accent_line']))
    fam = d['fontClass'].replace('font-', '')
    if fam not in fonts:
        raise SystemExit('BUILD FAILURE: designs.ts names fontClass %r at %s:%d but '
                         '%s declares no --font-%s'
                         % (d['fontClass'], where(DIR_DESIGNS), d['fontClass_line'],
                            where(DIR_CSS), fam))
    t.put('font_sans', fonts[fam],
          '%s (designs.ts:%d names %s)' % (fsrc[fam], d['fontClass_line'], d['fontClass']))
    t.put('font_mono', fonts['bcast'], fsrc['bcast'])
    t.put('slab_strong', pal['ink2'].upper(), psrc['ink2'])

    # ---- the live line, from Caption.tsx ---------------------------------
    live, live_src = class_block(spec['caption_live'])
    t.put('size_caption', u_size(live, live_src), live_src)
    t.put('leading_caption', u_leading(live, live_src), live_src)
    t.put('weight_caption', u_weight(live, live_src, '400'), live_src)
    t.put('tracking_caption', u_tracking(live, live_src, '0'), live_src)
    t.put('caption_upper', 'uppercase' if u_has(live, 'uppercase') else 'none', live_src)
    t.put('cap_align', 'center' if u_has(live, 'text-center') else 'left', live_src)
    line_colour = colour_in(live, pal, live_src)

    # THE WORD TERNARY, in the design's own order: the FIRST colour is the word
    # still being formed, the SECOND is a word already confirmed. Where the zip
    # states one colour, the other state is the forming line's own colour --
    # which is what the markup does by inheritance.
    words, words_src = class_block(spec['caption_words'])
    wc = colours_in(words, pal, words_src, required=False)
    if len(wc) >= 2:
        provisional, confirmed = wc[0], wc[1]
    elif len(wc) == 1:
        confirmed, provisional = line_colour, wc[0]
    elif d['id'] == 'mano':
        # The ramp is a STYLE value, not a class, so this one anchor is read RAW:
        # class_block() would hand back only the quoted property name.
        ramp_text, ramp_src = raw_block(spec['caption_words'])
        ramp = re.search(r'0\.(\d+)', ramp_text)
        if not ramp:
            raise SystemExit('BUILD FAILURE: no ink ramp at %s (%r)'
                             % (ramp_src, ramp_text))
        provisional = (rgba(line_colour[0], int(ramp.group(1)) / 100.0),
                       "the ramp's floor: %s -- the zip ramps every word from there "
                       "to full ink as it settles" % ramp.group(0))
        confirmed = line_colour
    else:
        confirmed = provisional = line_colour
    t.put('text_confirmed', confirmed[0], '%s (%s)' % (words_src, confirmed[1]))
    t.put('text_provisional', provisional[0], '%s (%s)' % (words_src, provisional[1]))

    def lum(v):
        if v.startswith('#') and len(v) == 7:
            return int(v[1:3], 16) + int(v[3:5], 16) + int(v[5:7], 16)
        m = re.match(r'rgba\((\d+), (\d+), (\d+), ([\d.]+)\)', v)
        if m:
            return (int(m.group(1)) + int(m.group(2)) + int(m.group(3))) * float(m.group(4))
        raise SystemExit('BUILD FAILURE: cannot rank %r' % v)

    bright = max((t['text_confirmed'], t['text_provisional']), key=lum)
    t.put('text_primary', bright,
          'derived: the brighter of %s and %s' % (confirmed[1], provisional[1]))

    # ---- the panel surface and its chrome, from Panel.tsx ----------------
    # TWO anchors, because the zip splits them: ONE shared frame
    # (`Panel.tsx:30` -- the radius, the shadow, the blur) and ONE surface per
    # design (`Panel.tsx:44-52` -- the tint and the hairline).
    frame, frame_src = class_block(FRAME)
    surf, surf_src = class_block(spec['surface'])
    slab, slab_a, slab_lbl = surface_in(surf, pal, surf_src)
    stage, stage_src = class_block(STAGE)
    stage_c, stage_a, stage_lbl = surface_in(stage, pal, stage_src)
    if stage_a != 1.0 or stage_c.upper() != '#000000':
        raise SystemExit('BUILD FAILURE: the zip stage at %s is %r at %s, not opaque '
                         'black -- the composite below would be wrong'
                         % (stage_src, stage_lbl, stage_a))
    t.put('slab', over_black(slab, slab_a),
          '%s (%s) composited over the zip stage %s at %s'
          % (surf_src, slab_lbl, stage_lbl, stage_src))
    t.put('slab_opacity', SLAB_OPACITY,
          'the zip shows this panel only over its own black stage with '
          'backdrop-blur-md (%s); a WebView2 window cannot blur the desktop behind '
          'it, so the surface is composited over that black and the panel stays '
          'effectively opaque' % frame_src)
    line, line_a, line_lbl = border_in(surf, pal, surf_src)
    t.put('line', rgba(line, line_a), '%s (%s)' % (surf_src, line_lbl))
    t.put('line_strong', rgba(line, round(min(line_a * 2.2, 1.0), 2)),
          'derived: %s x2.2 (the zip states ONE hairline per design; Sotto needs '
          'a strong tier for the scrollbar thumb)' % line_lbl)
    t.put('accent_soft', rgba(t['accent'], line_a),
          'derived: the accent at the surface border alpha (%s)' % line_lbl)
    t.put('shadow_slab',
          '%s, 0 0 0 1px %s' % (shadow_in(frame, frame_src), rgba(line, line_a)),
          '%s (the frame shadow-[...]) + the surface hairline (%s)' % (frame_src, line_lbl))
    t.put('radius_lg', '%dpx' % RADIUS_LG,
          '%s (rounded-lg on the frame) + %s' % (frame_src, TAILWIND))
    t.put('radius_sm', '%dpx' % RADIUS_SM, TAILWIND)
    t.put('radius_md', '%dpx' % RADIUS_MD, TAILWIND)
    t.put('radius_dialog', '%dpx' % RADIUS_LG, '%s (the frame radius)' % frame_src)

    head, head_src = class_block(spec['header'])
    t.put('tracking_brand', u_tracking(head, head_src, '0'), head_src)
    t.put('weight_brand', u_weight(head, head_src, '400'), head_src)
    t.put('size_chrome', u_size(head, head_src), head_src)
    t.put('brand_upper', 'uppercase' if spec['wordmark'].isupper() else 'none',
          "%s (the zip writes the wordmark %r; Sotto's own markup is lowercase)"
          % (head_src, spec['wordmark']))

    hist, hist_src = class_block(spec['history'])
    t.put('size_closed', u_size(hist, hist_src), hist_src)
    t.put('leading_closed', u_leading(hist, hist_src), hist_src)
    t.put('weight_closed', u_weight(hist, hist_src, '400'), hist_src)
    if 'history_newest' in spec:
        nc, n_src = class_block(spec['history_newest'])
        oc, o_src = class_block(spec['history_oldest'])
        newest = colour_in(nc, pal, n_src)
        oldest = colour_in(oc, pal, o_src)
        oldest_src = o_src
    else:
        hc = colours_in(hist, pal, hist_src)
        newest = hc[0]
        oldest = hc[1] if len(hc) > 1 else hc[0]
        oldest_src = hist_src
    t.put('text_secondary', newest[0], '%s (%s)' % (hist_src, newest[1]))
    muted, muted_src = class_block(spec['muted'])
    mc = colour_in(muted, pal, muted_src)
    t.put('text_muted', mc[0], '%s (%s)' % (muted_src, mc[1]))
    # A SECOND past tier, because the zip states TWO and Sotto asks for both:
    # --text-muted is the chrome/meta tier (a footer, a brand label) and
    # --time-past is what .caption__time paints on a CLOSED row -- the oldest
    # colour the design states for its own history.
    t.put('time_past', oldest[0], '%s (%s)' % (oldest_src, oldest[1]))

    foot, foot_src = class_block(spec['footer'])
    t.put('size_meta', u_size(foot, foot_src), foot_src)
    t.put('size_time', u_size(foot, foot_src),
          '%s (the design meta tier, which is where its clock sits)' % foot_src)
    t.put('size_small', u_size(foot, foot_src), foot_src)

    body, body_src = class_block(spec['body'])
    bx, bx_lbl = pad_in(body, body_src, 'x')
    by, by_lbl = pad_in(body, body_src, 'y')
    t.put('space', SPACE,
          'the zip declares ONE spacing scale for all five designs (%s); its own '
          'panel body pads %s -> %dpx / %s -> %dpx' % (TAILWIND, bx_lbl, bx, by_lbl, by))

    # ---- the design's own rail on the live line --------------------------
    rail = spec['rail']
    if rail:
        cls, src = class_block(rail)
        if d['id'] == 'cine':
            w, w_lbl = '1px', 'border-l (a 1 px rule)'
        else:
            w, w_lbl = dim_in(cls, 'w', src)
        t.put('prov_rail_w', w, '%s (%s)' % (src, w_lbl))
        t.put('prov_rail_style', 'solid', src)
    else:
        t.put('prov_rail_w', RAIL_W[d['id']],
              '%s: the design states NO rule on the live line; declared 0 so '
              "panel.css's own rail cannot leak in" % live_src)
        t.put('prov_rail_style', 'solid', 'not stated (the width is 0)')
    t.put('closed_rail_w', '0px', '%s: closed lines carry no rule in the zip' % hist_src)
    t.put('prov_pad', '0px' if RAIL_W[d['id']] == '0px' else 'var(--space-3)',
          'derived from the rail width')
    t.put('prov_bg', 'transparent', 'not stated: the zip never backgrounds the line')
    t.put('prov_style', 'normal',
          '%s: the zip never italicises the forming line. The one italic it '
          'states on caption text is Cinema Card on the SETTLED line '
          '(Caption.tsx:101) and lives in that theme signature block' % live_src)
    t.put('prov_extra', '', 'nothing extra')
    t.put('cap_family', 'var(--font-sans)', "the design's own family (font_sans)")
    t.put('closed_family', 'var(--font-sans)', "the design's own family (font_sans)")
    t.put('time_family', 'var(--font-mono)', "the zip's mono (%s)" % fsrc['bcast'])
    t.put('time_live', 'var(--accent)', "the zip's own accent on the live clock")

    if d['id'] == 'tele':
        t.put('live_shadow', glow_shadow()[0], glow_shadow()[1])
        period = glow_period()
        if period[0] not in SIG[d['id']]:
            raise SystemExit('BUILD FAILURE: .glow-live runs glowPulse %s (%s) but '
                             'the signature block uses another period'
                             % (period[0], period[1]))
    else:
        t.put('live_shadow', 'none',
              '%s: the zip states a halo on Teleprompter only' % live_src)

    for key, pair in shared_state(pal, psrc).items():
        t.put(key, pair[0], pair[1])

    t['sig'] = SIG[d['id']]
    return t


REQUIRED = ('accent', 'font_sans', 'font_mono', 'slab', 'slab_strong', 'slab_opacity',
            'line', 'line_strong', 'accent_soft', 'shadow_slab', 'text_primary',
            'text_secondary', 'text_muted', 'text_confirmed', 'text_provisional',
            'ok', 'busy', 'error', 'idle', 'radius_sm', 'radius_md', 'radius_lg',
            'radius_dialog', 'space', 'size_caption', 'leading_caption',
            'weight_caption', 'tracking_caption', 'tracking_brand', 'brand_upper',
            'caption_upper', 'size_time', 'size_closed', 'size_chrome', 'size_meta',
            'size_small', 'leading_closed', 'weight_closed', 'weight_brand', 'time_past',
            'prov_rail_w', 'prov_rail_style', 'prov_pad', 'prov_bg', 'cap_align',
            'time_live', 'live_shadow')


def parsed_themes(ideas):
    pal, psrc = zip_palette()
    fonts, fsrc = zip_fonts()
    designs = parse_designs()
    return [build_direction_theme(i + 1, d, pal, psrc, fonts, fsrc, ideas)
            for i, d in enumerate(designs)]


# THE PRE-DIRECTION THEME TABLES ARE GONE, and this time for a better reason than
# before. Until 2026-10-11 this file carried the five directions as a hand-written
# list of ~50 keys per theme: `designs.ts` appeared only in COMMENTS, so nothing
# connected `theme-1.css`'s `--accent: #F2E9D8` to `designs.ts:23`, and a zip that
# changed would not have moved a byte of the CSS. The list is now PARSED (see the
# head of this file), every value carries the `file:line` it came from, and `--trace`
# prints the table. What the files ARE is `parsed_themes()` below, and `build_fonts.py`
# in this same directory explains the fonts.
# The shared skin rules. `{S}` is the position of the scope prefix; `{B}` marks a
# rule that needs the `body` element for specificity (the caption text overrides).
SKIN = """
/* ── the slab ────────────────────────────────────────────────────────────── */
{S} .panel{{
  border-color: var(--line);
  border-radius: var(--radius-lg);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--bg-slab-strong) {slab_pct}%, transparent) 0%,
                            color-mix(in srgb, var(--bg-slab) {slab_pct}%, transparent) 100%);
  box-shadow: var(--shadow-slab);
}}
{S} .panel::before{{
  background: none;
  background-image: linear-gradient(90deg, var(--accent) 0%, var(--accent-soft) 100%);
  opacity: 0.9;
}}

/* ── the wordmark and the header controls ────────────────────────────────── */
{S} .wordmark__name{{
  color: var(--accent);
  letter-spacing: var(--tracking-brand);
  text-transform: var(--brand-upper);
  font-weight: var(--weight-brand);
  font-size: {brand_size};
}}
{S} .wordmark__tag{{ color: var(--text-muted); }}
/* ── THE TRANSCRIPT HANDLE IS NO LONGER STYLED HERE (owner, 2026-10-14) ─────
   `{S} .history__toggle,` was a member of the three button groups below until the
   button itself was deleted from `panel.html`, verbatim: *"tira o botao de
   transcript… remove o CONTROLO. se a gaveta tiver de ficar por detras,
   esconde-a mas tira o botao."* It went with the markup: a selector for a node
   that does not exist is a selector about nothing, and the drawer it opened is
   still in the document (collapsed, and it opens by itself the day a canonical
   producer exists). */
/* ── THE BUTTONS' RESTING EDGE (owner, 2026-10-14) ───────────────────────────
   `border-color` was `var(--line)`, the FAINT tier: MEASURED, the resting edge of
   every panel control came back at 1.18-1.51:1 against its own slab — the control
   read as a floating glyph with no box. `var(--line-strong)` is the tier this very
   file already used for the HOVER state directly below, so the resting edge now
   borrows the number the hover proved instead of inventing one: 1.99:1 (theme-1) to
   2.80:1 (theme-3) on the dark slabs. The STRIP buttons are untouched by this —
   `panel.css` has a `body[data-surface="strip"] .strip-button` rule that outranks
   this one on specificity and carries the lighter 0.16/0.30 pair the owner asked for
   in 2026-10-12 (*"os botoes tem que ser mais claros"*), which is why the strip is
   NOT re-lit here. THE SIZES ARE UNCHANGED. */
{S} .icon-button,
{S} .strip-button{{
  border-color: var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
}}
{S} .icon-button:hover,
{S} .strip-button:hover{{
  border-color: var(--line-strong);
  background: var(--accent-soft);
  color: var(--text-primary);
}}
{S} .icon-button:focus-visible,
{S} .strip-button:focus-visible,
{S} .reveal-button:focus-visible,
{S} .search__button:focus-visible,
{S} .dialog-button:focus-visible,
{S} .history__path:focus-visible,
{S} .hist:focus-visible,
{S} .theme-button:focus-visible,
{S} .theme-picker__option:focus-visible{{
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}}

/* ── section labels and the caption box chrome ───────────────────────────── */
/* THE history__label RULE IS GONE. MEASURED 2026-10-15 by zipc-designs-oracle.py check I:
   removing the span from panel.html left TEN rules in the generated CSS selecting a node
   that no longer exists -- one per theme-N and one per pd-* direction. `397 selectors,
   10 that match NO node`. A style for an element that is gone is not a style, it is debt,
   and it is the same dead-rule class this repo measured before. */
/* --size-chrome has a reader again. MEASURED 2026-10-15 by cine-themes-oracle C1 and
   cinematic-designs-oracle C: `declared+unread: --size-chrome (x25)` and
   `53 token(s) declared; 1 with NO reader anywhere`. The ONLY reader was the
   `.history__label` rule removed when the transcript label went away (the owner ordered
   the button out, and the label painted a word with no control behind it) -- so the
   token was left declared and unread, which is the orphan class both oracles gate.
   `.captions__hint` is the quiet line above the caption, the same chrome class of text
   the label was, and it had no size of its own. */
{S} .captions__hint{{ color: var(--text-muted); font-size: var(--size-chrome); }}
{S} .captions__body{{
  border-color: var(--line);
  border-radius: var(--radius-md);
  /* THE CAPTION ZONE IS THE DARK PART. MEASURED 2026-10-15 by
     _main/zip-fidelity-by-numbers.py against the zip demo: shot top=0.108 mid=0.091
     bot=0.140 against demo top=0.144 mid=0.162 bot=0.084 -- the shipped profile is
     the demo mirrored, and the caption zone is the BRIGHTEST band of the frame
     instead of the darkest. The zip (zips/cinematic/src/index.css:90-98) dims the
     BOTTOM with `.scrim-bottom` (`to top, var(--scrim) 0%, transparent 100%`),
     because the words are what must win.

     A PREVIOUS ATTEMPT weighted this gradient with --bg-slab-strong and MADE IT WORSE
     (bot 0.140 -> 0.150): that token is a LIGHT tint, so more of it is more light.
     The scrim must be DARK, and the theme own dark token is --bg-slab (#060708 in
     theme-1). This is the zip own shape with the theme own dark: bottom weighted,
     fading to nothing at the top, so the top keeps whatever the scene paints. */
  /* THE CAPTION ZONE IS THE DARK PART. MEASURED 2026-10-15 by
     _main/zip-fidelity-by-numbers.py against the zip demo, over FOUR measured tries:
       flat 55% slab-strong ......... bot=0.140  (the brightest band of the frame)
       slab-strong weighted gradient  bot=0.150  (WORSE -- that token is a LIGHT tint)
       bg-slab 0% -> transparent 100%  bot=0.108  mid=0.061 (right direction, too broad)
     The zip (zips/cinematic/src/index.css:90-98) dims the BOTTOM with `.scrim-bottom`
     (`to top, var(--scrim) 0%, transparent 100%`) -- and the caption sits in the last
     fifth of the box, not everywhere. So the dark is HELD flat across the bottom 22%
     and fades out by 52%, leaving the top of the box to whatever the scene paints.
     --bg-slab is the theme own DARK token (#060708 in theme-1), which is why this try
     moves the number and the slab-strong one did not. */
  background: linear-gradient(0deg, var(--bg-slab) 0%, var(--bg-slab) 22%,
                             transparent 52%),
              color-mix(in srgb, var(--bg-slab-strong) 55%, transparent);
  box-shadow: none;
  scrollbar-color: var(--line-strong) transparent;
}}
/* the theme used to colour the scrollbar thumb; the bar is HIDDEN in panel.css now, so a colour for it would be a rule for something nobody can see. */
{S} .captions__chip{{
  border-color: var(--line-strong);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}}

/* ── THE TWO STATES THE WHOLE DESIGN TURNS ON ────────────────────────────────
   The DOM (panel.html + panel.js bind it; a theme may not change it) is:
     a CLOSED line   <li class="caption [caption--latest]">  time + .caption__text
     the FORMING one <li class="caption caption--provisional">
                        time + .caption__text > .caption__confirmed + .caption__provisional
   So a theme has exactly three handles: the LINE, the CONFIRMED part of the
   forming line, and its still-rewriteable TAIL. All three are painted here. */
{B} .caption{{
  padding: {cap_pad_y} var(--space-3);
  border-radius: var(--radius-sm);
  background: transparent;
  border-left: 2px solid transparent;
  /* panel.css opens every new line with a 220 ms translateY(5px) keyframe. That
     is motion on the caption itself, and the brief forbids it: the line is
     rewritten in place as the hypothesis grows, and a line that also slides is
     read as a line that jumped. The skin keeps a COLOUR transition only. */
  animation: none;
  transition: background-color var(--motion-in), border-color var(--motion-in);
}}
{B} .caption:hover{{ background: color-mix(in srgb, var(--text-primary) 5%, transparent); }}
{B} .caption--latest{{ background: transparent; border-left-color: transparent; }}

{B} .caption__text{{
  color: var(--text-secondary);
  font-family: {cap_family};
  font-size: var(--size-caption);
  line-height: var(--leading-caption);
  font-weight: var(--weight-caption);
  letter-spacing: var(--tracking-caption);
  text-transform: var(--caption-upper);
  /* The direction's own "RIGIDLY LEFT-ALIGNED" (tele) stated in the skin rather
     than inherited from `panel.css`, so the alignment is a property of the
     THEME and a probe can read it per theme. `panel.css` already resolves to
     `start`, which is left here, so this is a declaration of intent and not a
     change for the other four. */
  text-align: {cap_align};
  /* `panel.css` sets `.caption--provisional .caption__text{{ font-style: italic }}`
   * (specificity 0,2,0) to mark the unstable line. Four of the five directions do
   * NOT want an italic there — the Teleprompter direction reads as a fallback
   * face, the Broadcast one is a monitor, the Manuscrito and Instrumento lines are
   * upright — and ONE italic left in place is a fifth of the design leaking into
   * the other four. Declared here so every theme states its own answer; the Cinema
   * Card's italic belongs to its SETTLED line (Caption.tsx:101) and is declared
   * in that theme's signature block instead of here.
   * MEASURED 2026-10-08: without this line the forming line computed `italic` in
   * themes 1, 2, 3 and 5. */
  font-style: normal;
}}
/* a CLOSED line: settled, quieter, one size down, never shouting */
{B} .caption:not(.caption--provisional) .caption__text{{
  color: var(--text-secondary);
  font-size: var(--size-closed);
  line-height: var(--leading-closed);
  font-weight: var(--weight-closed);
  /* The history is FLAT. Declared, not inherited, so a theme that gives its live
     line a halo cannot leak that halo onto the settled column — the rule is
     "the history recedes", and a glow on settled text is the opposite. */
  text-shadow: none;
}}
/* the words inside the forming line that are ALREADY CONFIRMED */
/* D6, CLOSED THE OTHER WAY: this rule painted the confirmed ink as a LITERAL while
   `--text-confirmed` was declared beside it and read by nothing. Measured over the
   ten designs: each one's `--text-confirmed` IS this literal (theme-1
   rgba(242,233,216,0.82), theme-2 rgba(255,255,255,0.9), theme-3 #EAE5D9, theme-4
   #EAE5D9, theme-5 #FFFFFF, pd-tele rgba(255,255,255,0.6) …), so reading the token
   here is the same colour with ONE source instead of two, and the token stops being
   dead weight. */
{B} .caption--provisional .caption__text{{ color: var(--text-confirmed); {cap_family_decl} text-shadow: {live_shadow}; }}
/* …and the tail that may still be rewritten. panel.css also sets it italic. */
{B} .caption--provisional .caption__provisional{{
  color: var(--text-provisional);
  font-style: {prov_style};
  {prov_extra}
}}
{B} .caption__time{{
  /* --time-past, not --text-muted: the zip states the PAST tier as its own
     oldest closed row, separately from the chrome/meta tier the footer carries. */
  color: var(--time-past);
  font-family: {time_family};
  font-size: var(--size-time);
  font-variant-numeric: tabular-nums;
}}
{B} .caption--provisional .caption__time{{ color: {time_live}; }}
/* A past line is GREY, all of them. `.caption--latest` is the newest CLOSED
   line — still past, so still grey: the owner's rule is binary ("o atual"
   vs "os que ficaram pra tras"), and a third colour would blur it. */
{B} .caption--latest .caption__time{{ color: var(--text-muted); }}
/* The forming line's tail marker ('▍', painted by `panel.js`). A monitor's
   block cursor: present, then absent, on a stepped 1.06 s loop — the one
   keyframed thing a caption carries besides the typing reveal, and it touches
   only the marker element, never the words. `prefers-reduced-motion` parks it
   ON (the MOTION block's kill-list spares nothing here, so this rule re-asserts
   stillness explicitly rather than trusting the cascade). */
{B} .caption__mark{{ animation: sotto-caret 1.06s steps(1) infinite; }}
@keyframes sotto-caret{{
  0%, 49%{{ opacity: 1; }}
  50%, 100%{{ opacity: 0; }}
}}

/* the rail that says WHICH line is being spoken */
{B} .caption--provisional{{
  border-left-color: var(--accent);
  border-left-width: {prov_rail_w};
  border-left-style: {prov_rail_style};
  background: {prov_bg};
  padding-left: {prov_pad};
}}
{B} .caption--latest{{
  border-left-color: var(--line-strong);
  border-left-width: {closed_rail_w};
  border-left-style: solid;
}}

/* ── the empty state ─────────────────────────────────────────────────────── */
{S} .captions__placeholder-title{{ color: var(--text-primary); font-weight: {ph_weight}; }}
{S} .captions__placeholder-body{{ color: var(--text-muted); }}
/* panel.css opens the placeholder with a translateY keyframe (`caption-in`).
   This skin takes the caption's motion out, so the empty state must not keep
   the one entrance animation the panel has. */
{S} .captions__placeholder{{ animation: none; }}
{S} .listening span{{ background: var(--accent); background-image: none; opacity: 0.55; }}

/* ── the footer ──────────────────────────────────────────────────────────── */
/* D5 of the audit (2026-10-12), CLOSED HERE BY MEASUREMENT: this section used to
   carry TWO more rules — `{S} .status__hint` and `{S} kbd` — and both painted an
   element the live document CANNOT carry. The owner took the Alt+C hint out of
   the panel himself (recorded at `panel.html:935`): `<kbd>` is now a word inside
   that comment and nowhere else, and the 87 class tokens of `panel.html` plus the
   49 classes the 12 loaded modules assign contain no `status__hint`. The five zips
   do not ask for one either: the `<Kbd>` badges of the directions zip sit on its
   LANDING-PAGE footer (`App.tsx:76-86`), never inside a panel. A selector that can
   never match is dead weight, so the two rules are gone. */
{S} .status{{
  border-top-color: var(--line);
  color: var(--text-secondary);
  font-size: var(--size-small);
}}
{S} .status__dot{{ background: var(--idle); }}
{S} .status--live .status__dot{{ background: var(--ok); box-shadow: {ok_ring}; }}
{S} .status--error .status__dot{{ background: var(--error); box-shadow: {err_ring}; }}
{S} .status--live .status__text{{ color: {ok_text}; }}
{S} .status--error .status__text{{ color: {err_text}; }}

/* ── the transcript drawer: SECONDARY, and it must know how to be quiet ───── */
{S} .history{{ border-top-color: var(--line); }}
/* D5, CLOSED: `.history__source` was a third member of this group and matches
   nothing — no class token in `panel.html`, none assigned by the 12 modules, and
   no history row of any zip prints a source label (the mockup rows carry text,
   time and a confidence figure this panel refuses to invent). The two members
   that DO exist (`.history__note` is `panel.html:490`/`:538`, `.history__count`
   is `:478`) stay. */
{S} .history__note,
{S} .history__count{{ color: var(--text-muted); }}
{S} .history__path{{ color: var(--text-muted); font-family: var(--font-mono); }}
{S} .history__path:hover{{ color: var(--accent); }}
{S} .search__input{{
  border-color: var(--line-strong);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--bg-slab-strong) 60%, transparent);
  color: var(--text-primary);
  font-family: var(--font-sans);
}}
{S} .search__input::placeholder{{ color: var(--text-muted); }}
{S} .search__input:focus{{
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}}
{S} .search__button,
{S} .search__clear,
{S} .reveal-button{{
  border-color: var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: var(--size-small);
}}
{S} .search__button:hover,
{S} .search__clear:hover,
{S} .reveal-button:hover{{
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--text-primary);
}}
/* D5, CLOSED: `.reveal-button--danger` was the other member of this rule and is
   never applied — `reveal-button` exists (`panel.html:520`) but no module ever
   gives it a `--danger` state, while `.dialog-button--danger` is static markup
   and `.icon-button--danger` is the one the JS toggles. The live member keeps
   the rule. */
{S} .dialog-button--danger{{ border-color: color-mix(in srgb, var(--error) 40%, transparent); color: color-mix(in srgb, var(--error) 70%, var(--text-primary)); }}
{S} .hist{{ border-radius: var(--radius-sm); background: color-mix(in srgb, var(--text-primary) 4%, transparent); }}
{S} .hist:hover{{ background: color-mix(in srgb, var(--text-primary) 8%, transparent); }}
{S} .hist--selected{{ border-left-color: var(--accent); background: var(--accent-soft); }}
{S} .hist__time{{ color: var(--text-muted); font-family: var(--font-mono); }}
{S} .hist__text{{ color: var(--text-secondary); font-size: var(--size-small); }}
{S} .hist__text mark,
{S} .hist__text::selection,
{S} .caption__text::selection{{
  background: var(--accent-soft);
  color: var(--text-primary);
}}
{S} .hist__text mark{{ background: color-mix(in srgb, var(--accent) 30%, transparent); }}
{S} .history__empty{{ color: var(--text-muted); }}
{S} .history__list{{ scrollbar-color: var(--line-strong) transparent; }}
{S} .history__list::-webkit-scrollbar-thumb{{ background: var(--line-strong); border-radius: 99px; }}


/* ── the strip surface: the status WORD is the readout ──────────────────── */
{S} .stripbar__dot{{ background: var(--idle); }}
{S} .stripbar__state.is-live .stripbar__dot{{ background: var(--ok); box-shadow: {ok_ring}; }}
{S} .stripbar__state.is-error .stripbar__dot{{ background: var(--error); box-shadow: {err_ring}; }}
{S} .stripbar__word{{
  color: var(--text-muted);
  font-family: var(--font-mono);
  letter-spacing: 0.08em;
}}
{S} .stripbar__state.is-live .stripbar__word{{ color: {ok_text}; }}
{S} .stripbar__state.is-error .stripbar__word{{ color: {err_text}; }}
{S} .strip-button--toggle[aria-pressed="true"]{{
  border-color: var(--line-strong);
  background: var(--accent-soft);
  color: var(--text-primary);
}}
{S} .strip-button--toggle[aria-pressed="false"]{{ border-color: color-mix(in srgb, var(--error) 34%, transparent); }}
{S} .panel.is-paused .captions__body{{ border-color: color-mix(in srgb, var(--error) 34%, transparent); }}

/* ── the pause confirmation ─────────────────────────────────────────────── */
{S} .pause-dialog{{
  border-color: var(--line-strong);
  border-radius: var(--radius-dialog);
  background: var(--bg-slab-strong);
  color: var(--text-primary);
  font-family: var(--font-sans);
}}
{S} .pause-dialog::backdrop{{ background: rgba(0, 0, 0, 0.66); }}
{S} .pause-dialog__title{{ font-weight: var(--weight-brand); }}
{S} .pause-dialog__body{{ color: var(--text-secondary); }}
{S} .pause-dialog__honest{{
  border-color: var(--line);
  border-left: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
}}
{S} .pause-dialog__shell{{ color: {err_text}; }}
{S} .dialog-button{{
  border-color: var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-family: var(--font-sans);
}}
{S} .dialog-button:hover{{ border-color: var(--accent); color: var(--text-primary); }}

/* ── the theme picker this module owns (no panel markup needed) ─────────── */
{S} .theme-button{{
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: 9.5px;
  letter-spacing: 0.02em;
  padding: 0 6px;
  cursor: pointer;
  max-width: 84px;
  overflow: hidden;
  white-space: nowrap;
}}
{S} .theme-button__label{{ text-overflow: ellipsis; overflow: hidden; }}
{S} .theme-button::after{{
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-left: 5px;
  border-radius: 99px;
  background: var(--theme-swatch, var(--accent));
  vertical-align: middle;
}}
{S} .theme-button:hover{{ color: var(--text-primary); border-color: var(--line-strong); }}
{S} .theme-picker{{
  position: absolute;
  top: 46px;
  right: 12px;
  z-index: 40;
  padding: var(--space-2);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-md);
  background: var(--bg-slab-strong);
  box-shadow: var(--shadow-slab);
}}
{S} .theme-picker[hidden]{{ display: none; }}
{S} .theme-picker__list{{ display: flex; flex-direction: column; gap: 2px; }}
{S} .theme-picker__option{{
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 5px var(--space-3);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-family: var(--font-sans);
  font-size: var(--size-small);
  text-align: left;
  cursor: pointer;
}}
{S} .theme-picker__swatch{{
  width: 9px;
  height: 9px;
  flex: none;
  border-radius: 99px;
  background: var(--theme-swatch, var(--accent));
}}
{S} .theme-picker__option:hover{{ background: var(--accent-soft); color: var(--text-primary); }}
{S} .theme-picker__option[aria-current="true"]{{
  border-color: var(--accent);
  color: var(--text-primary);
  font-weight: var(--weight-brand);
}}

/* ── motion ─────────────────────────────────────────────────────────────────
   ONE thing moves in this skin, it is a COLOUR, and it is shorter than 180 ms:
   --motion-in. This skin adds NO keyframe and NO transform to anything that
   carries the caption's text: a line rewritten in place must not slide, fade or
   pulse, and switching themes must never animate the text. The panel's typing
   reveal is the ONE exception in the whole document (it animates the opacity of
   the forming line's newest characters), it is declared in `panel.css`, and
   rule 4 of the header above is what keeps it from being declared twice.
   P2-2 (2026-10-08 audit): the transition used to hang on `{S} *` — every
   element in the document, so every DOM write anywhere paid a colour
   transition. It now hangs on the chrome only (header, footer, state
   indicators): the caption column and the history list change instantly. */
{S} .panel__header, {S} .panel__header *, {S} .status, {S} .status *,
{S} .chrome, {S} .chrome *{{
  transition-property: color, background-color, border-color, box-shadow;
  transition-duration: var(--motion-in);
  transition-timing-function: ease;
}}
{B} .caption,
{B} .caption__text,
{B} .caption__confirmed,
{B} .caption__provisional{{
  transition-property: color, background-color, border-color;
  transition-duration: var(--motion-in);
}}
@media (prefers-reduced-motion: reduce){{
  /* IMPORTANT, and the reason is measured rather than theoretical. `.caption__ch`
     is the TYPING REVEAL's own character span, declared in `panel.css`. This
     block used to silence it with a plain `{S} *` — and on the owner's machine
     Windows reports client-area animations OFF, so Chromium answers
     `prefers-reduced-motion: reduce` and the reveal was disabled by the very
     query written to honour the setting. The exclusion below is what keeps the
     reveal alive; the reveal's own off switch is the token `--type-step: 0ms`.
     Do not re-widen this selector to `{S} *`. */
  {S} *:not(.caption__ch),
  {B} .caption,
  {B} .caption__text,
  {B} .caption__confirmed,
  {B} .caption__provisional,
  {B} .caption__mark{{
    transition-duration: 0ms;
    animation: none;
  }}
  {S} .listening span{{ animation: none; }}
}}
"""

HEAD = """/* Sotto — theme {n}: {name}.
 *
 * GENERATED by `_main/_design-lane/gen_themes.py`. Do not hand-edit: the five
 * files share one contract on purpose, and the generator is what guarantees it.
 *
 * THE IDEA. {idea}
 *
 * ── THE CONTRACT THIS FILE OBEYS ────────────────────────────────────────────
 * 1. EVERY selector in this file is scoped to `:root[data-theme='theme-{n}']`,
 *    so all five themes can be linked into ONE document and cannot collide.
 * 2. Switching is ONE attribute write: `document.documentElement.dataset.theme`.
 *    No `@import`, no `url()` outside the repo, no network, no per-theme JS.
 * 3. It sets the tokens `panel.css`/`surface.js` consume (see the `:root` block),
 *    and it re-skins COLOUR, TYPE and SURFACE. It ALSO carries its own header
 *    line, footer line, state indicator and control placement (the `CHROME`
 *    block at the end of this file, added 2026-10-08 when the owner asked for
 *    each direction to have its own face); what it never does is touch the
 *    caption's TEXT, the transcript's rows or the shell's own status sentence.
 * 4. This file adds NO keyframe and NO transform to a caption's text. Here
 *    `--motion-in` covers colour and surface only. The single keyframe
 *    animation a caption carries is the TYPING REVEAL on the forming line's
 *    newest word, and it is declared in `panel.css`, never in a theme: one
 *    owner per animation, so a theme cannot fight it or double it.
 * 5. `prefers-reduced-motion: reduce` zeroes THIS file's colour transitions and
 *    the chrome's movement, and it deliberately does NOT silence the typing
 *    reveal: that reveal is the owner's explicit request (2026-10-08) and it is
 *    the reason the reduced-motion blocks below exclude `.caption__ch`. The
 *    reveal's own off switch is the token `--type-step: 0ms`. Before
 *    2026-10-08 this file (and `panel.css`) silenced it under reduced motion,
 *    which made the feature INVISIBLE on the owner's own machine: Windows
 *    reports client-area animations off there, so Chromium answers
 *    `prefers-reduced-motion: reduce` and the animation was disabled by the
 *    very query written to honour it.
 *
 * MEASURED FROM: the zip's own source, `sotto-app-design-directions.zip`,
 * unpacked at `_main/_design-lane/zips/directions/`. EVERY value in this file is
 * PARSED from it at generation time -- `src/data/designs.ts` for the identity,
 * `src/index.css` for the palette and the families, `src/components/Caption.tsx`
 * and `src/components/Panel.tsx` for the type, the surface and the hairline -- and
 * the generator FAILS THE BUILD when a value it needs is not there. Run
 * `py -3 _main/_design-lane/gen_themes.py --trace` for the table of every token
 * against the `file:line` it came from. The revision before this one measured
 * `docs/design/incoming/design-{n}.png` and said so here; those medians are GONE,
 * because a screenshot cannot be re-derived when the design moves and the zip can.
 *
 * ONE DEVIATION, AND IT IS IN ALPHA ONLY. The zip renders its panel over its own
 * black stage (`Stage.tsx:46`) with `backdrop-blur-md` (`Panel.tsx:30`), so the
 * slab below is the surface colour COMPOSITED over that same black -- the colour
 * the zip actually shows -- and the panel stays effectively opaque, because a
 * WebView2 window cannot blur the desktop behind it and Sotto's captions have to
 * be readable over whatever the owner has on screen. Hue is the zip's; only the
 * alpha is Sotto's. The caption ratios are in `_main/receipt-panel-themes.md`.
 */

:root[data-theme='{sel}']{{
  /* ── SURFACE ──────────────────────────────────────────────────────────── */
  /* D6 of the audit, CLOSED: `--slab-opacity` stood here (0.96 in all ten
     designs) and NO rule of any stylesheet in the panel ever read it. The alpha is
     consumed at BUILD time, twice: by `over_black()`, which composites the zip's
     translucent surface over the zip's own black stage, and by the
     `color-mix(... N% ...)` the skin writes into the slab. A declaration nothing
     reads is dead weight; the value is still in the ledger (`--trace`). */
  --bg-slab: {slab};
  --bg-slab-strong: {slab_strong};
  --shadow-slab: {shadow_slab};

  /* ── TEXT ─────────────────────────────────────────────────────────────── */
  --text-primary: {text_primary};
  --text-confirmed: {text_confirmed};
  --text-provisional: {text_provisional};
  --text-secondary: {text_secondary};
  --text-muted: {text_muted};
  --time-past: {time_past};

  /* ── LINES AND ACCENT ─────────────────────────────────────────────────── */
  --line: {line};
  --line-strong: {line_strong};
  --accent: {accent};
  --accent-soft: {accent_soft};
  /* The theme button paints its own swatch from this, so a theme's accent is
     declared in exactly one place. */
  --theme-swatch: {accent};

  /* ── STATE: colour carries information here, never decoration ─────────── */
  /* D6, CLOSED: `--busy` stood here and had 0 readers in the whole panel. The zip
     colour behind it (`--color-amberlite` / `--color-amberx`) is the FRESHEST
     WORD, and that role is already carried by `--text-provisional` — which every
     theme declares and the forming line reads. There is no busy STATE in this
     panel's vocabulary (the status kinds are idle / live / error), so the second
     name for one colour is gone. */
  --ok: {ok};
  --error: {error};
  --idle: {idle};

  /* ── SHAPE ────────────────────────────────────────────────────────────── */
  --radius-sm: {radius_sm};
  --radius-md: {radius_md};
  --radius-lg: {radius_lg};
  --radius-dialog: {radius_dialog};

  /* ── SPACE ────────────────────────────────────────────────────────────── */
  /* D6, CLOSED for the two ENDS of the scale. The zip declares ONE spacing scale
     (Tailwind's, which is dynamic: step N is N x 0.25rem), so all five designs
     share it — but a step nothing reads is not a scale, it is a declaration with
     no consumer. Measured over the ten designs: `--space-2` and `--space-3` are
     read by `panel.css` and by the skin's own rules, `--space-4` is read by the
     one design whose zip states `pl-4` on its live line (pd-cine's
     `padding-left`), and `--space-1` / `--space-5` had 0 readers anywhere.
     Those two are gone. */
  --space-2: {s2}px;
  --space-3: {s3}px;
  --space-4: {s4}px;

  /* ── TYPE ─────────────────────────────────────────────────────────────── */
  --font-sans: {font_sans};
  --font-mono: {font_mono};
  /* D6, CLOSED: `--font-caption` and `--font-closed` stood here, both declared as
     `var(--font-sans)` in all ten designs and read by no rule of any panel
     stylesheet — the caption rule names `var(--font-sans)` directly (see the
     `.caption__text` block of the skin) and a CLOSED line wears the same family
     in every zip (the settled rows are the live line one size down, never another
     face). Two names for one value and no reader is dead weight; the design's
     family is still declared once, in `--font-sans`. */
  --size-caption: {size_caption};
  --leading-caption: {leading_caption};
  --weight-caption: {weight_caption};
  --tracking-caption: {tracking_caption};
  --tracking-brand: {tracking_brand};
  --brand-upper: {brand_upper};
  --caption-upper: {caption_upper};
  --size-time: {size_time};
  --size-closed: {size_closed};
  --size-chrome: {size_chrome};
  --size-meta: {size_meta};
  --size-small: {size_small};
  --leading-closed: {leading_closed};
  --weight-closed: {weight_closed};
  --weight-brand: {weight_brand};

  /* ── MOTION: colour only, and short ───────────────────────────────────── */
  --motion-in: 150ms;
}}

/* The `panel.css` names are kept as ALIASES of the tokens above, so a reader who
 * knows the old file finds the old names and they cannot drift. */
:root[data-theme='{sel}']{{
  /* D6, CLOSED: `--bg: var(--bg-slab)` stood here. Every other alias below is
     READ (panel.css and the skins read --text-dim / --text-faint / --radius /
     --font / --mono / --accent-from / --accent-to / --accent-gradient; caption-float.css
     reads the accent pair), and `panel.css:24` declares its own `--bg` anyway —
     measured: 0 `var(--bg)` in the whole panel and 0 mentions in the JS and in the
     shell. The one alias with no reader is gone; the rest cannot drift because
     they are aliases, not copies. */
  --bg-raised: var(--bg-slab-strong);
  --text: var(--text-primary);
  --text-dim: var(--text-secondary);
  --text-faint: var(--text-muted);
  --radius: var(--radius-lg);
  --font: var(--font-sans);
  --mono: var(--font-mono);
  --accent-from: var(--accent);
  --accent-to: var(--accent);
  --accent-gradient: var(--accent);
  color-scheme: dark;
}}
"""

# --------------------------------------------------------------------------- #
# THE DIRECTION'S OWN CHROME — the second half of the contract, added 2026-10-08
# after the owner asked for it verbatim: *"quero que voce monte o painel super
# parecido com cada tema. pode ate mudar botoes de lugar, se quiser. nao quero a
# cara do design que tinhamos antes."*
#
# Until this block every direction re-skinned COLOUR, TYPE and SURFACE and shared
# ONE header and ONE footer with the other four. The five mockups do not: each
# carries its own header line, its own footer line, its own state indicator, and
# its own place for the controls. So each theme file now also carries:
#
#   * `.chrome--<id>[data-chrome="head"]` — the direction's header line
#     (`SOTTO / LENDO`, `REC / CH·01`, `rascunho ao vivo / pág. 1`,
#     `SOTTO / · ao vivo ·`, `ON / ALT+C`), turned ON here and `display:none`
#     for the other four by `panel.css`;
#   * `.chrome--<id>[data-chrome="foot"][data-slot="start"|"end"]` — its footer
#     line, placed with `order` around the REAL `#status-text`;
#   * where the control cluster sits (`.panel__controls`) — top-right for
#     Teleprompter and Cinema Card, a second header row for Broadcast,
#     Manuscrito and Instrumento;
#   * the direction's own indicator: `bcast`'s per-line ordinal, `mano`'s
#     per-word contrast ramp, `cine`'s forming fog, `inst`'s breathing LED.
#
# THE STATE WORDS ARE CSS, AND THEY ARE THE ONLY FACT THE MOCKUPS AND THIS PANEL
# SHARE. `panel.js` mirrors the footer's own live/error state onto
# `<body data-state>`, and `panel.css` paints exactly one of the two words. NO
# NUMBER IS INVENTED HERE: the mockups print `CONF 0.93`, `buffer 38ms` and
# `48K` from a SIMULATED script (`designs.ts` → `SCRIPT`, and `panels.tsx`'s own
# `setInterval` randomiser); this panel has no such measurement, so none of the
# five prints one. What each prints is what the panel can really read: the state
# the shell reported, the clock, the line ordinal, and the worker's own status
# sentence, which stays in `#status-text` for every direction.
#
# ANIMATION RULES FOR THIS BLOCK (the owner's condition, measured — see
# `_main/receipt-panel-per-theme-chrome.md` §cost): the live box is rewritten on
# EVERY partial, so anything animated must be `opacity`, `transform` or `filter`
# — never a property that forces a relayout — and every animation here is
# measured with the panel running. The `mano` ramp is an OPACITY transition on
# spans that are REUSED, so a partial never restarts it; the `inst` LED is a
# TRANSFORM+OPACITY keyframe on a real element; the `cine` fog is a static
# `filter` that dissolves on commit, never a per-word keyframe (a per-word
# keyframe on a rewritten box replays on every partial — measured, and rejected).
# --------------------------------------------------------------------------- #

CHROME = {}

CHROME[1] = """
/* ── THE DIRECTION'S OWN CHROME: a teleprompter's header and footer ──────────
   `SOTTO` (the wordmark, kept) + `● LENDO`. The tag line and the mark go: the
   direction's header is two words and a dot, and "nothing is boxed" applies to
   the controls too — they lose their chrome and stay as glyphs. */
@S@ .wordmark__tag,
@S@ .wordmark__mark{ display: none; }
@S@ .chrome--tele[data-chrome="head"]{
  display: inline-flex;
  margin-left: auto;
  gap: 7px;
  font-family: var(--font-sans);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--text-muted);
}
@S@ .chrome--tele .chrome__dot{
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 99px;
  background: var(--idle);
}
@S@ body[data-state="live"] .chrome--tele .chrome__dot{
  background: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 16%, transparent);
}
/* "Nothing is boxed": the controls are glyphs, not buttons. */
@S@ .panel__controls{ gap: 2px; }
@S@ .panel__controls .icon-button{
  border-color: transparent;
  background: transparent;
  color: var(--text-muted);
}
@S@ .panel__controls .icon-button:hover{
  border-color: transparent;
  background: transparent;
  color: var(--accent);
}
/* ── THE FOOTER CHROME IS GONE (owner, 2026-10-14) ─────────────────────────
   Verbatim: *"tira em curso e historico das barras. o dono quer as barras
   LIMPAS."* Three rules stood here, styling the two spans `panel.html` used
   to carry in the footer bar: `HISTÓRICO` in the `start` slot and
   `▲ EM CURSO` in the `end` one. BOTH SPANS WERE DELETED FROM THE MARKUP in
   the same pass, so these rules styled nothing and went with them — a rule
   about a node that no longer exists is a rule about nothing, and the panel
   file's own convention is to delete it rather than leave it looking live.

   WHAT THE BAR KEEPS: the REAL status sentence (`#status-dot` +
   `#status-text`), which is the worker's own cause and not a mockup label, so
   the footer is CLEAN rather than empty. WHAT IS UNTOUCHED: this direction's
   HEADER chrome above (the wordmark, `● LENDO` and the dot), and every OTHER
   direction's own footer chrome — `bcast`'s meter and LIVE/EM ESPERA,
   `mano`'s "— escrito ao ouvido", `cine`'s "· · ·", `inst`'s meter and
   OUVINDO/EM ESPERA — because the owner named `em curso` and `historico` and
   nothing else. */
"""

CHROME[2] = """
/* ── THE DIRECTION'S OWN CHROME: a broadcast monitor ─────────────────────────
   `● REC · CH·01 ····· HH:MM:SS` on the header line, and the controls move OFF
   the header entirely: they become the monitor's second row, right-aligned,
   which is where a machine's operation keys belong. The wordmark is replaced by
   the channel line — the direction's own header has no logo. */
@S@ .wordmark{ display: none; }
/* THE NAME, IN THIS DIRECTION'S OWN VOICE (owner, 2026-10-08: *"e bota o nome
   'sotto' em todos os temas"*). Not a logo pasted on top: it is set in the
   monitor's own mono face at the channel line's own size and muted, so it reads as
   the machine's nameplate. `text-transform: none` because he wrote it lowercase. */
@S@ .chrome--bcast .chrome__brand{
  font-family: var(--font-mono);
  font-size: var(--size-time);
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: none;
  color: var(--text-secondary);
}
@S@ body:not([data-surface="strip"]) .panel__header{
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 6px 10px;
}
@S@ .chrome--bcast[data-chrome="head"]{
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-family: var(--font-mono);
  font-size: 9.5px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-secondary);
}
@S@ .chrome--bcast .chrome__state{ color: var(--accent); font-weight: 600; }
@S@ .chrome--bcast .chrome__rec{
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: 99px;
  background: var(--idle);
}
@S@ body[data-state="live"] .chrome--bcast .chrome__rec{
  background: var(--accent);
  animation: sotto-2-rec 1.6s ease-out infinite;
}
/* P2-1: the pulse is OPACITY only — the old keyframe animated `box-shadow`
   spread, which is a paint property and a layout-adjacent cost every frame. */
@keyframes sotto-2-rec{
  0%{ opacity: 1; }
  70%{ opacity: 0.35; }
  100%{ opacity: 1; }
}
@S@ .chrome--bcast .chrome__chan{ color: var(--text-muted); }
@S@ .chrome--bcast .chrome__tc{
  margin-left: auto;
  color: var(--text-primary);
  letter-spacing: 0.08em;
  font-variant-numeric: tabular-nums;
}
/* THE CONTROLS ARE ON THE TOP ROW (owner, 2026-10-08: *"move todos os botoes
   la pra cima tambem"*), right-aligned, small and square. */
@S@ body:not([data-surface="strip"]) .panel__controls{
  grid-column: 2;
  grid-row: 1;
  justify-self: end;
  gap: 4px;
}
@S@ .panel__controls .icon-button{ border-radius: 3px; }
/* THE PER-LINE ORDINAL IS NOT PAINTED. This direction's mockup prints `001`,
   `002`, … beside the clock (`pad3(h.id)` in `Panel.tsx`), and the element that
   carried it was removed from the screen at the OWNER's own instruction
   (2026-10-08, twice): *"tira esse numero de 033 11:21:03"*, then *"to falando
   desse numero a esquerda. o vermelho. nao é pra ter mais ele"*. The `033` was
   the INDEX OF THE ROW, red on the forming line and grey on the closed ones, and
   he wants none of them. The ordinal survives as `li[data-index]` for the probes.
   The `grid-template-columns` that used to reserve its track went with it — and
   it was INERT anyway: nothing ever set `display: grid` on `.caption`. */
@S@ .chrome--bcast[data-chrome="foot"]{
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 6px;
  font-family: var(--font-mono);
  font-size: var(--size-meta);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}
@S@ .chrome--bcast[data-chrome="foot"][data-slot="start"]{ order: -1; color: var(--accent); }
@S@ .chrome--bcast[data-chrome="foot"][data-slot="end"]{ order: 9; color: var(--accent); }
/* ── NO METER ANIMATION. MEASURED, AND DELETED. ────────────────────────────
   A `@keyframes sotto-2-meter` loop stood here and animated the five bars
   identically with speech, with silence and with a DEAD WORKER — a wave that
   lies, which is exactly what the owner forbade. `docs/research/
   12-audio-level-contract.md` is the measurement; the bars now carry the level
   the worker really reports (`.chrome__meter` is driven by `--meter-N` custom
   properties, see `panel.css`), and with no real data they sit at the floor. */
"""

CHROME[3] = """
/* ── THE DIRECTION'S OWN CHROME: a manuscript being written ──────────────────
   `rascunho ao vivo ····· pág. 1` on the header line; the controls become the
   second header row (a manuscript has no buttons at the top of the page). */
@S@ .wordmark{ display: none; }
/* THE NAME, IN THIS DIRECTION'S OWN VOICE (owner, 2026-10-08: *"e bota o nome
   'sotto' em todos os temas"*). A manuscript signs itself quietly: the name is set
   in the same hand as the page, lowercase, in the ink colour, at the margin. */
@S@ .chrome--mano .chrome__brand{
  font-family: var(--font-serif);
  font-size: var(--size-time);
  font-weight: 400;
  font-style: normal;
  letter-spacing: 0.06em;
  text-transform: none;
  color: var(--text-muted);
}
@S@ body:not([data-surface="strip"]) .panel__header{
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: baseline;
  gap: 4px 10px;
}
@S@ .chrome--mano[data-chrome="head"]{
  grid-column: 1;
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  font-family: var(--font-sans);
  color: var(--text-muted);
}
@S@ .chrome--mano .chrome__draft{ font-size: 12.5px; font-style: italic; color: var(--text-secondary); }
/* THE PAGE NUMBER IS WHAT THE NAME COST (owner, 2026-10-08: *"e bota o nome
   'sotto' em todos os temas"*, then *"Não espremas"*). MEASURED, not guessed —
   `_main\_panel-geometry.js` on a real 380x900 panel, theme-3, header 350 px wide:
     header grid columns       138.594px 201.406px   (1fr auto; the controls own col 2)
     .chrome--mano   (the cell) 138.6 px
       .chrome__brand  24.1 x 15.0   = ONE line (10px/15px)      <- the name is free
       .chrome__draft  68.0 x 37.5   = TWO lines (12.5px/18.75px)  <- it wrapped
       .chrome__page   26.5 x 33.0   = TWO lines (11px/16.5px)     <- it wrapped
   Sum of the three WRAPPED widths + the two 10px gaps = 138.6 px: the cell is
   exactly full, so both wider items were compressed and re-flowed, the block grew
   37.5, and the header row grew 28 -> 41.5 px, taking 13.5 px off the live box
   (760.5 -> 747). A ONE-LINE header is impossible at 380 px, not tight: the
   wrapped widths alone already need 138.6 + a 10px column gap + the controls'
   201.4 = 350.0, and the two items were compressed to reach that. So the name
   cannot be added for free while all three texts stay — one of them has to go.
   The page number goes: it is static, it names a page in a transcript that has
   none, and the owner removed this class of decoration twice already (item B,
   item 3). The name stays, at its own size, unsqueezed. Revert = this one line. */
@S@ .chrome--mano .chrome__page{ display: none; }
@S@ body:not([data-surface="strip"]) .panel__controls{ grid-column: 2; grid-row: 1; justify-self: end; gap: 4px; }
@S@ .chrome--mano[data-chrome="foot"]{
  display: inline-flex;
  flex: none;
  font-family: var(--font-sans);
  font-size: var(--size-meta);
  font-style: italic;
  color: var(--text-muted);
}
@S@ .chrome--mano[data-chrome="foot"][data-slot="start"]{ order: 9; }

/* ── THE RAMP: "cada palavra recém-chegada ganha contraste aos poucos" ───────
   `panel.js` gives every word of the forming line `--w-op` (the mockup's own
   `0.45 + 0.55·(i+1)/len`), and this paints it. THE TRANSITION IS THE WHOLE
   POINT AND IT IS ALSO THE COST DECISION: it is `opacity`, which the compositor
   owns, on a span that is REUSED across partials — so as the line grows, every
   older word's contrast eases DOWN to its new value instead of snapping, and a
   partial never restarts a keyframe. No per-word entry animation is shipped:
   measured, a keyframe on a word inside a box that is rewritten every partial
   replays on every partial (see the receipt's cost table). */
@B@ .caption--provisional .caption__word{
  opacity: var(--w-op, 1);
  transition: opacity 260ms ease;
}
"""

CHROME[4] = """
/* ── THE DIRECTION'S OWN CHROME: a festival card ─────────────────────────────
   `SOTTO` in gold, tracked wide, and `· ao vivo ·` in italic at the other end.
   The wordmark GOES WHOLE — mark, name and tag — because the direction's header
   is one word in gold and the panel's own wordmark says "Sotto" too; leaving
   both would print the brand twice. The footer is the film's own ellipsis. The
   controls stay top-right and lose nothing but their weight. */
@S@ .wordmark{ display: none; }
@S@ .chrome--cine[data-chrome="head"]{
  display: flex;
  align-items: baseline;
  /* `flex: 1 1 auto`, NOT `flex: 1`. MEASURED at the real 380x900 geometry
     (`_main/_panel-chrome-arm.py`, which asserts `innerWidth === 380` from
     inside the page): with `flex: 1` the basis is 0, so once the control row
     is on the top row the direction's own header line is squeezed to
     **width 0** — present in the DOM, invisible on screen, and nothing
     errors. `auto` keeps the line at its content width. */
  flex: 1 1 auto;
  gap: 10px;
  min-width: 0;
  font-family: var(--font-sans);
  color: var(--text-muted);
}
@S@ .chrome--cine .chrome__brand{
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.34em;
  /* LOWERCASE, KEPT LOWERCASE. The mockup prints `SOTTO` and this rule used to
     force it with `text-transform: uppercase`, so the markup's `sotto` came out
     shouting. The owner wrote the name in lowercase (2026-10-08: *"bota o nome
     'sotto' em todos os temas"*) and `text-transform` is exactly the property that
     would silently overrule him. */
  text-transform: none;
  color: var(--accent);
}
@S@ .chrome--cine .chrome__state{ margin-left: auto; font-size: 11px; font-style: italic; }
@S@ .panel__controls{ gap: 4px; }
@S@ .panel__controls .icon-button{ background: transparent; border-color: color-mix(in srgb, var(--accent) 22%, transparent); }
@S@ .chrome--cine[data-chrome="foot"]{
  display: inline-flex;
  flex: none;
  font-family: var(--font-sans);
  font-size: var(--size-meta);
  letter-spacing: 0.5em;
  color: var(--accent);
}
@S@ .chrome--cine[data-chrome="foot"][data-slot="start"]{ order: 9; }

/* ── THE FORMING FOG: "a frase fechada é sólida; a em curso vive na névoa" ───
   TWO TIERS, BOTH STATIC, OPACITY ONLY (P2-6, 2026-10-08 audit): this used to be
   a `filter: blur()` on the live line — 0.45 px on the confirmed part, 0.95 px
   on the tail. A blur on text the worker rewrites every few hundred ms is a
   repaint of the most expensive kind on the exact line the owner is reading, and
   at sub-pixel radii it reads as unfocused rather than misted. The direction
   keeps its two tiers — confirmed barely held back, tail harder — as opacity
   steps, and the transition still dissolves the fog when the line commits. */
@B@ .caption--provisional .caption__text{
  opacity: 0.92;
  transition: opacity 600ms ease;
}
@B@ .caption--provisional .caption__provisional{
  opacity: 0.55;
  transition: opacity 600ms ease;
}
@B@ .caption:not(.caption--provisional) .caption__text{ opacity: 1; }
"""

CHROME[5] = """
/* ── THE DIRECTION'S OWN CHROME: an instrument that is ON ────────────────────
   `■ ON ················· ALT+C` on the header line, the controls on the second
   header row, and the footer's own level meter beside `OUVINDO`. The wordmark is
   replaced by the state line — the direction's header says whether the thing is
   ON, not what it is called. */
@S@ .wordmark{ display: none; }
/* THE NAME, IN THIS DIRECTION'S OWN VOICE (owner, 2026-10-08: *"e bota o nome
   'sotto' em todos os temas"*). An instrument is LABELLED: the name is silkscreened
   in the panel's own mono legend face, tracked wide like the other legends, in the
   legend colour rather than the accent, so it never competes with the state lamp. */
@S@ .chrome--inst .chrome__brand{
  font-family: var(--font-mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.28em;
  text-transform: none;
  color: var(--text-muted);
}
@S@ body:not([data-surface="strip"]) .panel__header{
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 6px 10px;
}
@S@ .chrome--inst[data-chrome="head"]{
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--text-primary);
}
@S@ .chrome--inst .chrome__led{
  width: 8px;
  height: 8px;
  flex: none;
  border-radius: 2px;
  background: var(--idle);
}
@S@ body[data-state="live"] .chrome--inst .chrome__led{
  background: var(--accent);
  animation: sotto-5-led 1.5s ease-in-out infinite;
}
/* D5, CLOSED: `@S@ .chrome--inst .chrome__key` stood here — the Alt+C badge of the
   Instrumento header (`ON / ALT+C`, quoted in this file's own chrome header). The
   owner ordered that hint OUT of the panel (`panel.html:935`), the element went
   with it, and `.chrome__key` is not one of the 12 `chrome__*` classes the panel
   actually carries (brand, chan, dot, draft, led, meter, off, on, page, rec,
   state, tc). Measured: 0 matches in `panel.html`, in the 12 loaded modules, in
   the 105 skin files, and in the five zips' panel sources. The rule is gone. */
@keyframes sotto-5-led{
  0%, 100%{ transform: scaleY(0.45); opacity: 0.65; }
  50%{ transform: scaleY(1); opacity: 1; }
}
@S@ body:not([data-surface="strip"]) .panel__controls{ grid-column: 2; grid-row: 1; justify-self: end; gap: 4px; }
@S@ .panel__controls .icon-button{ border-radius: 3px; }
/* ── THE INDICATOR: "o indicador da linha ativa é o principal elemento
   dinâmico" ────────────────────────────────────────────────────────────────
   The live line already carries its 4 px LED rail as a BORDER (the direction's
   own mark, and the probe reads it). A border cannot be animated on the
   compositor, so the breathing is a REAL element laid exactly over that rail:
   `transform: scaleY()` + `opacity`, both compositor properties, on a 4 px
   box — the one thing in this panel that moves while a sentence forms. */
@B@ .caption--provisional .caption__led{
  display: block;
  left: -4px;
  width: 4px;
  background: var(--accent);
  animation: sotto-5-led-live 1.7s ease-in-out infinite alternate;
}
@keyframes sotto-5-led-live{
  from{ opacity: 0.62; transform: scaleY(0.92); }
  to{ opacity: 1; transform: scaleY(1); }
}
@S@ .chrome--inst[data-chrome="foot"]{
  display: inline-flex;
  flex: none;
  align-items: center;
  gap: 6px;
  font-family: var(--font-sans);
  font-size: 9px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--text-muted);
}
@S@ .chrome--inst[data-chrome="foot"][data-slot="start"]{ order: -1; color: var(--accent); }
@S@ .chrome--inst[data-chrome="foot"][data-slot="end"]{ order: 9; color: var(--accent); }
/* ── NO EQUALISER ANIMATION. Same measurement, same deletion: three keyframe
   loops (`sotto-5-eqA/B/C`) animated the instrument's bars regardless of what
   the microphone heard. The bars are now painted from the worker's own reported
   level. */
@keyframes sotto-5-eqA{
  0%, 100%{ transform: scaleY(0.3); }
  28%{ transform: scaleY(1); }
  56%{ transform: scaleY(0.5); }
  80%{ transform: scaleY(0.85); }
}
@keyframes sotto-5-eqB{
  0%, 100%{ transform: scaleY(0.55); }
  35%{ transform: scaleY(0.95); }
  62%{ transform: scaleY(0.35); }
  85%{ transform: scaleY(0.75); }
}
@keyframes sotto-5-eqC{
  0%, 100%{ transform: scaleY(0.42); }
  30%{ transform: scaleY(0.7); }
  58%{ transform: scaleY(1); }
}
"""

# The scope every rule is written under. `%s` is the theme number, so each file
# can only ever style its own theme and five of them coexist in one document.
ROOT = ":root[data-theme='%s']"

# --------------------------------------------------------------------------- #
# LANE B's CHROME PAINTS THE DESIGN'S OWN META SIZE, NOT THE FIRST ZIP'S.
#
# THE ORDER (owner, verbatim): *"eu quero que, cada tema encontrado dentro dos
# .zip, fiquem com o design IGUAL"*. Each `pd-*` design declares `--size-meta`
# with the size ITS OWN zip states for its meta tier -- `--trace` prints the zip
# line of every one of them -- and until this block NO rule of lane B read it:
# every chrome row painted a LITERAL, and those literals are the FIRST zip's
# (the shared `CHROME` templates were written from
# `sotto-app-design-directions.zip`). Measured, the defect: `pd-tele` declared
# 11px and painted 10px.
#
# WHY THE SWAP IS HERE AND NOT INSIDE THE TEMPLATES. `CHROME[n]` is SHARED by the
# two lanes -- it is emitted into `theme-n.css` AND into `panel-designs.css` -- so
# a literal edited inside a template rewrites `theme-1..5.css` as well, and this
# lane is ordered not to touch those five files. The swap therefore runs on the
# EMITTED text of the `pd-*` designs alone, keyed by design, one exact anchor per
# rule. Each anchor must occur EXACTLY ONCE in its template or the build FAILS: a
# template that drifts stops the build instead of silently painting the family's
# size again.
#
# WHAT MOVES (the zip line is the authority; every one was re-measured against
# the .zip member `src/components/panels.tsx`, which is byte-identical to the
# extracted copy the generator parses):
#   pd-tele   head  10px   -> 11px     the zip's own `sotto`, panels.tsx:31
#   pd-bcast  head  9.5px  -> 9.5px    no visible move: it already paints its own
#                                      meta row (panels.tsx:158) and stops being a
#                                      literal
#   pd-mano   draft 12.5px -> 10px     `registro continuo`, panels.tsx:182
#   pd-cine   brand 11px   -> 13px     the zip's own `sotto`, panels.tsx:253
#   pd-cine   state 11px   -> 13px     the same tier as the brand above
#   pd-instr  brand 9px    -> 10px     `PT-BR . 48 kHz`, panels.tsx:340
#   pd-instr  head  11px   -> 10px     the ON/STBY chip is SOTTO's own node, not
#                                      the zip's status word: that one is
#                                      `.status`, which already reads
#                                      `--size-small`
#   pd-instr  foot  9px    -> 10px     `PT-BR . 48 kHz`, panels.tsx:340
#
# WHAT IS DELIBERATELY UNTOUCHED: `bcast`'s `.chrome__brand` already reads
# `var(--size-time)`, the design's OWN clock tier (panels.tsx:105), and its
# `.chrome__tc` is a lane-B-only literal of that same clock -- neither is a number
# the first zip owned. `bcast`, `mano` and `cine` already had their FOOT row read
# `var(--size-meta)` from the shared template before this block existed.
# --------------------------------------------------------------------------- #
PD_CHROME_META = {
    1: (("  font-size: 10px;",
         "  font-size: var(--size-meta);"),),
    2: (("  font-size: 9.5px;",
         "  font-size: var(--size-meta);"),),
    3: (("@S@ .chrome--mano .chrome__draft{ font-size: 12.5px; font-style: italic; color: var(--text-secondary); }",
         "@S@ .chrome--mano .chrome__draft{ font-size: var(--size-meta); font-style: italic; color: var(--text-secondary); }"),),
    4: (("@S@ .chrome--cine .chrome__brand{\n  font-size: 11px;",
         "@S@ .chrome--cine .chrome__brand{\n  font-size: var(--size-meta);"),
        ("@S@ .chrome--cine .chrome__state{ margin-left: auto; font-size: 11px; font-style: italic; }",
         "@S@ .chrome--cine .chrome__state{ margin-left: auto; font-size: var(--size-meta); font-style: italic; }"),),
    5: (("  font-family: var(--font-mono);\n  font-size: 9px;\n  font-weight: 600;",
         "  font-family: var(--font-mono);\n  font-size: var(--size-meta);\n  font-weight: 600;"),
        ("  font-size: 11px;",
         "  font-size: var(--size-meta);"),
        ("  font-family: var(--font-sans);\n  font-size: 9px;\n  letter-spacing: 0.22em;",
         "  font-family: var(--font-sans);\n  font-size: var(--size-meta);\n  letter-spacing: 0.22em;"),),
}


def pd_chrome_meta(block, chrome):
    """Lane B only: the chrome rows paint THIS design's own meta tier.

    `block` is the FILLED `CHROME[chrome]` template; `chrome` selects the anchor
    set. Nothing here runs for `theme-1..5`: those five keep the exact bytes this
    generator shipped before this block existed.
    """
    pairs = PD_CHROME_META.get(chrome)
    if not pairs:
        raise SystemExit('BUILD FAILURE: no pd-chrome anchor set for chrome %r' % (chrome,))
    out = block
    for old, new in pairs:
        n = out.count(old)
        if n != 1:
            raise SystemExit('BUILD FAILURE: the pd-chrome anchor for design %d occurs %d '
                             'time(s), must be exactly 1: %r' % (chrome, n, old[:70]))
        out = out.replace(old, new, 1)
    return out


# --------------------------------------------------------------------------- #
# `prefers-reduced-motion` FOR THE CHROME — ONE BLOCK, APPENDED TO ALL FIVE.
#
# It has to be `!important`, and that is a measured consequence, not laziness.
# The chrome's animations are written with real selectors —
# `body[data-state="live"] .chrome--inst .chrome__led`, and
# `.chrome__meter i:nth-child(2)` — because that is what makes them specific
# enough to beat `panel.css`. A plain override can only beat those by repeating
# every one of them at the same specificity, and the `:nth-child` delays make
# that a list that drifts the moment one animation is added. `!important` on a
# reduced-motion block is the standard form of exactly this override, and it is
# what makes "no motion" TRUE for every animation in the block — including the
# ones added later.
# --------------------------------------------------------------------------- #
MOTION = """
/* ── REDUCED MOTION: nothing in the chrome moves ───────────────────────────── */
@media (prefers-reduced-motion: reduce){
  @B@ .chrome,
  @B@ .chrome *,
  @B@ .caption__word,
  @B@ .caption__led,
  @B@ .caption__text,
  @B@ .caption__mark{
    animation: none !important;
    transition: none !important;
  }
}
"""

# --------------------------------------------------------------------------- #
# THE STRIP SURFACE OWNS ITS OWN FOOTER — and this rule is in the THEME file, not
# only in `panel.css`, because of a MEASURED specificity fact: the chrome blocks
# are addressed as `.chrome--<id>[data-chrome="foot"][data-slot="end"]`
# (specificity 0,5,0), so `panel.css`'s `body[data-surface="strip"] .status .chrome`
# (0,3,2) LOSES to them and a direction's footer label leaks into the ~150 px
# strip. The rule below carries the same two attribute selectors, so it is
# (0,5,1) — higher — and the strip stays the strip. Both halves are kept: the
# `panel.css` rule is the belt, this is the braces, and the arm asserts the
# OUTCOME (nothing of the direction's chrome is on screen on the strip) rather
# than either rule.
# --------------------------------------------------------------------------- #
STRIP_GUARD = """
/* ── THE STRIP: the direction's chrome stays on the PANEL surface ──────────── */
@S@ body[data-surface="strip"] .chrome[data-chrome="head"],
@S@ body[data-surface="strip"] .chrome[data-chrome="foot"]{ display: none; }
"""


def _strip_comments(text):
    """Replace every comment with a NEWLINE, never with nothing.

    Joining the bytes on either side of a comment would weld a line-leading
    scope marker onto the previous rule's closing brace and produce a phantom
    rule — which is exactly what a first cut of this script did.
    """
    out = []
    i = 0
    while i < len(text):
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            out.append('\n')
            i = len(text) if j < 0 else j + 2
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def _split_top(text, sep):
    """Split on `sep` at depth 0 only (parentheses and strings respected)."""
    parts = []
    depth = 0
    cur = []
    quote = None
    for ch in text:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in '"\'':
            quote = ch
            cur.append(ch)
            continue
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == sep and depth == 0:
            parts.append(''.join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append(''.join(cur))
    return parts


def _parse(text):
    """A CSS block into nodes: ('at', prelude, body) for `@media`, ('rule', selector, decls)."""
    clean = _strip_comments(text)
    nodes = []
    i = 0
    n = len(clean)
    while i < n:
        while i < n and clean[i] in ' \t\r\n':
            i += 1
        if i >= n:
            break
        j = clean.find('{', i)
        if j < 0:
            break
        sel = clean[i:j].strip()
        # the matching close brace
        depth = 0
        k = j
        while k < n:
            if clean[k] == '{':
                depth += 1
            elif clean[k] == '}':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        body = clean[j + 1:k]
        bare = sel.replace('@S@', '').replace('@B@', '')
        if bare.lstrip().startswith('@'):
            nodes.append(('at', bare.strip(), _parse(body)))
            i = k + 1
            continue
        mark = 'B' if '@B@' in sel else 'S'
        plain = '\n'.join(x.replace('@B@', '').replace('@S@', '').strip().rstrip(',')
                          for x in sel.split('\n'))
        decls = [d.strip() for d in _split_top(body, ';') if d.strip()]
        # A prelude that is NOTHING but `@B@`/`@S@` is a SCOPE MARKER on its own
        # line, not a rule: it is the marker of the selector that FOLLOWS.
        if plain.strip() == '' and sel.strip():
            nodes.append(('marker', mark, []))
        elif decls and all(
                d.replace('@S@', '').replace('@B@', '').strip() == '' and d.strip()
                for d in decls):
            # `@B@ .sel{ @B@ }` — the marker sat INSIDE the braces of its own
            # selector. Normalise it: marker up, body empty.
            nodes.append(('rule', plain.strip(), [], mark))
        else:
            nodes.append(('rule', plain.strip(), decls, mark))
        i = k + 1
    return nodes


def _merge(nodes):
    """Fold a run of rules with an EMPTY body into the next rule's selector list.

    The template writes a selector list one line per selector so it stays
    readable, which the parser reads as N rules of which the first N-1 have no
    declarations. A group like

        @S@ .a,
        @B@ .b,
        @S@ .c{ outline: ... }

    is ONE rule, and it is emitted as one — with ONE scope for the whole list,
    because members of a selector list must not end up at different specificities.
    """
    out = []
    pending = []
    mark = None
    for node in nodes:
        kind = node[0]
        if kind == 'at':
            out.append(('at', node[1], _merge(node[2])))
            continue
        if kind == 'marker':
            mark = node[1]
            continue
        sel, payload, own = node[1], node[2], node[3]
        if not payload and sel.strip():
            pending.append(sel.strip())
            continue
        group = pending + ([sel.strip()] if sel.strip() else [])
        pending = []
        chosen = 'B' if (own == 'B' or mark == 'B'
                         or any(g.startswith('B') for g in [])) else 'S'
        mark = None
        out.append(('rule', chosen + '\n' + ',\n'.join(group), payload))
    for g in pending:
        out.append(('rule', 'S\n' + g, []))
    return out


def scope(block, n):
    """Prefix every top-level selector with `{S} ` (skin) or `{B} ` (needs `body`).

    `_merge` has already decided the scope of each rule and encoded it as the
    first line of the selector, so this pass only renders: it strips the marker
    and writes it back as the CSS prefix.

    TWO AT-RULES ARE EMITTED VERBATIM, and this is not a convenience: a
    `@keyframes` body is a list of PERCENTAGE selectors, so scoping it would turn
    `0%` into `:root[data-theme='theme-N'] 0%`, which is not a keyframe selector
    at all and would silently kill the animation. `@font-face` has no selector
    either. Everything else (`@media`, and any future `@supports`) IS scoped
    inside, because its body holds real selectors.
    """
    out = []
    nodes = _merge(_parse(block))

    def emit_plain(items, indent=''):
        """Emit a body WITHOUT the theme scope (keyframes, @font-face)."""
        for kind, sel, payload in items:
            if kind == 'at':
                out.append('%s%s {' % (indent, sel))
                emit_plain(payload, indent + '  ')
                out.append('%s}' % indent)
                continue
            lines = [l.strip() for l in sel.split('\n') if l.strip()]
            if lines and lines[0] in ('S', 'B'):
                lines = lines[1:]
            lines = [l[3:].strip() if l[:3] in ('@S@', '@B@') else l for l in lines]
            lines = [l for l in lines if l]
            if not lines:
                continue
            out.append('%s%s {' % (indent, (',\n' + indent).join(lines)))
            for d in payload:
                out.append('%s  %s;' % (indent, ' '.join(d.split())))
            out.append('%s}' % indent)

    def emit(items, indent=''):
        for kind, sel, payload in items:
            if kind == 'at':
                out.append('%s%s {' % (indent, sel))
                if sel.lstrip().startswith('@keyframes') or sel.lstrip().startswith('@font-face'):
                    emit_plain(payload, indent + '  ')
                else:
                    emit(payload, indent + '  ')
                out.append('%s}' % indent)
                continue
            lines = sel.split('\n')
            mark = lines[0] if lines[0] in ('S', 'B') else 'S'
            lines = lines[1:] if lines[0] in ('S', 'B') else lines
            scope = ("%s body" % ROOT % n) if mark == 'B' else (ROOT % n)
            parts = []
            for one in lines:
                # ONE SOURCE LINE CAN HOLD SEVERAL SELECTORS, and the scope has
                # to land on EVERY one of them. It used to be prefixed to the
                # LINE, so a group written `@S@ .a, @S@ .b, ...` on one line came
                # out with only `.a` scoped and `.b`, `.c` ... LEAKING into every
                # OTHER theme's document, where the last stylesheet loaded won --
                # measured 2026-10-11: 4 unscoped selectors in EACH of the five
                # generated files, all of them from the one group at the end of
                # SKIN. Splitting at depth 0 keeps `:is(a, b)` and `[x="a,b"]` in
                # one piece, and `_merge` has already fixed ONE mark per rule, so
                # every member of a list still gets the SAME scope -- the
                # invariant its docstring states.
                for member in _split_top(one, ','):
                    member = member.strip()
                    if not member:
                        continue
                    member = member[3:] if member.startswith('@S@') else member
                    member = member[3:] if member.startswith('@B@') else member
                    member = member.strip()
                    if member:
                        parts.append('%s %s' % (scope, member))
            if not parts:
                continue
            out.append('%s%s {' % (indent, (',\n' + indent).join(parts)))
            for d in payload:
                out.append('%s  %s;' % (indent, ' '.join(d.split())))
            out.append('%s}' % indent)

    emit(nodes)
    return '\n'.join(out)


# --------------------------------------------------------------------------- #
# TOKENS A THEME CONSUMES AND DOES NOT OWN.
#
# `_main/_design-lane/assert-themes.js` requires every token a file CONSUMES with
# `var(--x)` to be DECLARED in that same file, and that rule is the right one: a
# `var()` with no declaration anywhere and no fallback is INVALID AT
# COMPUTED-VALUE TIME, so the property silently falls back to `inherit` and the
# file's own intent is gone without one line of output saying so. Measured
# 2026-10-11: two tokens broke it, and both belong to the `mano` direction.
#
#   --font-serif  the `mano` chrome's brand face. It was declared NOWHERE -- not
#                 in this repo, not by any script -- so the declaration
#                 `font-family: var(--font-serif)` never resolved and
#                 `.chrome__brand` INHERITED its parent instead:
#                 `.chrome--mano[data-chrome="head"]`, which this same theme sets
#                 to `var(--font-sans)` (theme-3: "Newsreader", Georgia, serif).
#                 Pointing the token at `--font-sans` is that same stack, STATED
#                 instead of inherited.
#   --w-op        STAMPED AT RUNTIME by `app/panel/panel.js` (`paintWords`), one
#                 value per word span. Both of its consumers already read
#                 `var(--w-op, 1)`, so 1 IS the value they paint with before the
#                 stamp lands; declaring it here moves no pixel, and the inline
#                 stamp still wins on every span that gets one.
#
# `resolve_consumed()` FAILS THE BUILD on any consumed token that is not in this
# table, so the next one is a decision somebody makes, never another silent
# `inherit`.
# --------------------------------------------------------------------------- #
CONSUMED_NOT_OWNED = {
    '--font-serif': ('var(--font-sans)',
                     "the mano chrome's brand face, which inherited --font-sans"),
    '--w-op': ('1',
               "the value panel.js paintWords stamps over, and the consumers' own fallback"),
}


def resolve_consumed(text, sel):
    """Declare, inside the file, EVERY token the file consumes.

    This is the gate's own third rule (`assert-themes.js`), run at generation
    time so a theme can never be written with a token it does not declare.
    Comments are stripped first, exactly as the gate's tokenizer does, so a token
    named in prose is not mistaken for a declaration.
    """
    probe = _strip_comments(text)
    used = set(re.findall(r'var\(\s*(--[a-z0-9-]+)', probe, re.I))
    declared = set(re.findall(r'(--[a-z0-9-]+)\s*:', probe, re.I))
    missing = sorted(used - declared)
    unknown = [m for m in missing if m not in CONSUMED_NOT_OWNED]
    if unknown:
        raise SystemExit(
            'BUILD FAILURE: %s consumes %s and declares it nowhere. A `var()`'
            ' with no declaration and no fallback is INVALID AT COMPUTED-VALUE'
            ' TIME: the property silently inherits and the file loses its own'
            ' intent. Decide the value and add it to CONSUMED_NOT_OWNED in this'
            ' script.' % (sel, ', '.join(unknown)))
    if not missing:
        return text
    note = '\n'.join('   %-13s %s' % (tok + ':', CONSUMED_NOT_OWNED[tok][1])
                     for tok in missing)
    rows = '\n'.join('  %s: %s;' % (tok, CONSUMED_NOT_OWNED[tok][0]) for tok in missing)
    return text + (
        '/* -- TOKENS THIS THEME CONSUMES AND DOES NOT OWN ---------------------------\n'
        '   Declared here so every `var()` in this file RESOLVES. A `var()` with no\n'
        '   declaration anywhere and no fallback is invalid at computed-value time,\n'
        '   and the property then silently falls back to `inherit`. Each value below\n'
        '   is the one this file was ALREADY rendering with, so nothing on screen\n'
        '   moves:\n'
        '%s\n'
        '   ------------------------------------------------------------------------ */\n'
        ":root[data-theme='%s']{\n%s\n}\n" % (note, sel, rows))

def build(t):
    # "sel" is the data-theme value ("theme-1" for lane A, "pd-tele" for lane B)
    # and "chrome" is WHICH of the five chrome families this theme wears. They are
    # the same number in lane A; lane B keeps the family and changes the scope.
    sel = t.get('sel') or ('theme-%d' % t['n'])
    chrome = t.get('chrome', t['n'])
    skin = SKIN.format(
        S="@S@", B="@B@",
        slab_pct=int(round(float(t['slab_opacity']) * 100)),
        brand_size=t.get('brand_size') or ("12px" if chrome in (2, 5) else "13px"),
        cap_pad_y=t.get('cap_pad_y') or ("7px" if chrome != 3 else "9px"),
        cap_family=t.get('caption_family', 'var(--font-sans)'),
        closed_family=t.get('closed_family', 'var(--font-sans)'),
        time_family=t.get('time_family', 'var(--font-mono)'),
        cap_family_decl='',
        confirmed_color=t['text_confirmed'],
        prov_style=t.get('prov_style') or 'normal',
        prov_extra=t.get('prov_extra', ''),
        prov_rail_w=t.get('prov_rail_w', '2px'),
        prov_rail_style=t.get('prov_rail_style', 'solid'),
        prov_bg=t.get('prov_bg', 'transparent'),
        prov_pad=t.get('prov_pad', 'var(--space-3)'),
        closed_rail_w=t.get('closed_rail_w', '2px'),
        time_live=t.get('time_live', 'var(--accent)'),
        live_shadow=t.get('live_shadow', 'none'),
        cap_align=t.get('cap_align', 'left'),
        ph_weight=t['weight_brand'],
        ok_ring="0 0 0 3px color-mix(in srgb, var(--ok) 18%, transparent)",
        err_ring="0 0 0 3px color-mix(in srgb, var(--error) 18%, transparent)",
        ok_text="var(--ok)",
        err_text="color-mix(in srgb, var(--error) 72%, var(--text-primary))",
    )
    head = HEAD.format(
        n=t['n'], sel=sel, name=t['name'], idea=t['idea'],
        slab=t['slab'], accent=t['accent'], text_primary=t['text_primary'],
        text_secondary=t['text_secondary'], text_muted=t['text_muted'],
        time_past=t['time_past'],
        slab_strong=t['slab_strong'], slab_opacity=t['slab_opacity'],
        shadow_slab=t['shadow_slab'],
        text_confirmed=t['text_confirmed'], text_provisional=t['text_provisional'],
        line=t['line'], line_strong=t['line_strong'], accent_soft=t['accent_soft'],
        ok=t['ok'], busy=t['busy'], error=t['error'], idle=t['idle'],
        radius_sm=t['radius_sm'], radius_md=t['radius_md'], radius_lg=t['radius_lg'],
        radius_dialog=t['radius_dialog'],
        s1=t['space'][0], s2=t['space'][1], s3=t['space'][2], s4=t['space'][3], s5=t['space'][4],
        font_sans=t['font_sans'], font_mono=t['font_mono'],
        size_caption=t['size_caption'], leading_caption=t['leading_caption'],
        weight_caption=t['weight_caption'], tracking_caption=t['tracking_caption'],
        tracking_brand=t['tracking_brand'], brand_upper=t['brand_upper'],
        caption_upper=t['caption_upper'], size_time=t['size_time'],
        size_closed=t['size_closed'], size_chrome=t['size_chrome'],
        size_meta=t['size_meta'], size_small=t['size_small'],
        leading_closed=t['leading_closed'], weight_closed=t['weight_closed'],
        weight_brand=t['weight_brand'],
        font_caption=t.get('caption_family', 'var(--font-sans)'),
        font_closed=t.get('closed_family', 'var(--font-sans)'),
    )
    chrome_text = fill(CHROME[chrome], t)
    if t.get('sel'):
        # LANE B ONLY -- the chrome paints THIS design's own meta size (PD_CHROME_META)
        chrome_text = pd_chrome_meta(chrome_text, chrome)
    text = (head + scope(skin, sel) + "\n"
            + scope(chrome_text, sel) + "\n"
            + scope(fill(t.get('sig', ''), t), sel) + "\n"
            + scope(STRIP_GUARD, sel) + "\n"
            + scope(MOTION, sel) + "\n")
    return resolve_consumed(text, sel)

# =========================================================================== #
# LANE B -- "sotto-transcription-panel-designs.zip", the second zip.
#
# A DIFFERENT SET, not a second palette: its own @theme block, its own
# components, its own five designs, and no shipped theme until now. It gets its
# own two files and its own selector namespace (pd-*), so nothing here can
# collide with theme-1..5 or cine-*. Every value is PARSED at generation time
# from this zip, and a value the zip does not state is a BUILD FAILURE -- the
# same contract lane A obeys.
# =========================================================================== #

PD_IDS = {1: 'pd-tele', 2: 'pd-bcast', 3: 'pd-mano', 4: 'pd-cine', 5: 'pd-instr'}
PD_COLOUR_KEYS = ('ink', 'coal', 'paper', 'accent', 'amberx', 'moss')
PD_LEADING = {'none': '1', 'tight': '1.25', 'snug': '1.375', 'normal': '1.5',
              'relaxed': '1.625', 'loose': '2'}


def pd_palette():
    """The second zip's OWN @theme palette, index.css:11-16."""
    lines = slurp(PD_CSS)
    out, src = {}, {}
    for i, l in enumerate(lines):
        m = re.match(r'\s*--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8});', l)
        if m:
            out[m.group(1)] = m.group(2).upper()
            src[m.group(1)] = '%s:%d (--color-%s)' % (where(PD_CSS), i + 1, m.group(1))
    for k in PD_COLOUR_KEYS:
        if k not in out:
            raise SystemExit('BUILD FAILURE: %s declares no --color-%s' % (where(PD_CSS), k))
    return out, src


def pd_fonts():
    """--font-* from the same block, plus an index by the FIRST family name."""
    lines = slurp(PD_CSS)
    out, src, first = {}, {}, {}
    for i, l in enumerate(lines):
        m = re.match(r'\s*--font-([a-z0-9-]+):\s*(.+);', l)
        if m:
            key, val = m.group(1), m.group(2).strip()
            out[key] = val
            src[key] = '%s:%d (--font-%s)' % (where(PD_CSS), i + 1, key)
            fm = re.match(r'"?([^",]+)"?', val)
            if fm:
                first[fm.group(1).strip()] = key
    for k in ('mono', 'body'):
        if k not in out:
            raise SystemExit('BUILD FAILURE: %s declares no --font-%s' % (where(PD_CSS), k))
    return out, src, first


def pd_directions():
    """The zip's OWN directions table (src/lib/scripts.ts), id -> identity."""
    lines = slurp(PD_SCRIPTS)
    start = at(lines, PD_SCRIPTS, 'export const DIRECTIONS')
    out = {}
    for i in range(start - 1, len(lines)):
        m = re.match(r'\s*id:\s*(\d+),', lines[i])
        if not m:
            continue
        n = int(m.group(1))
        blk = '\n'.join(lines[i:i + 7])

        def grab(field, blk=blk, n=n, i=i):
            mm = re.search(r'%s:\s*"([^"]+)"' % field, blk)
            if not mm:
                raise SystemExit('BUILD FAILURE: no %s for direction %d at %s:%d'
                                 % (field, n, where(PD_SCRIPTS), i + 1))
            return mm.group(1)

        out[n] = dict(key=grab('key'), name=grab('name'), font=grab('font'), line=i + 1)
    if len(out) != 5:
        raise SystemExit('BUILD FAILURE: %s states %d direction(s), not 5'
                         % (where(PD_SCRIPTS), len(out)))
    return out


def pd_surface(cls, src):
    """bg-[rgba(8,10,13,0.88)] -> (hex, alpha, label).

    The second zip states its panel tints as an rgba() inside an arbitrary value
    rather than as a hex with a slash opacity -- the one shape surface_in() does
    not take.
    """
    m = re.search(r'bg-\[rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)\]', cls)
    if not m:
        raise SystemExit('BUILD FAILURE: no bg-[rgba(...)] surface at %s (%r)' % (src, cls))
    hexv = '#%02X%02X%02X' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (hexv, float(m.group(4)),
            'bg-[rgba(%s,%s,%s,%s)]' % (m.group(1), m.group(2), m.group(3), m.group(4)))


def pd_first_stop(raw, src):
    """The first stop of a gradient the zip states in a style object."""
    m = re.search(r'rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)', raw)
    if not m:
        raise SystemExit('BUILD FAILURE: no rgba() stop at %s (%r)' % (src, raw))
    hexv = '#%02X%02X%02X' % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return (hexv, float(m.group(4)),
            'the first stop, rgba(%s,%s,%s,%s)' % (m.group(1), m.group(2), m.group(3), m.group(4)))


def pd_text(cls, pal, src, required=True):
    """text-[#f1ece2], text-[rgba(235,232,225,0.88)], text-white/85."""
    m = re.search(r'text-\[#([0-9a-fA-F]{6})\]', cls)
    if m:
        return '#' + m.group(1).upper(), 'text-[#%s]' % m.group(1)
    m = re.search(r'text-\[rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)\]', cls)
    if m:
        return ('rgba(%s, %s, %s, %s)' % (m.group(1), m.group(2), m.group(3), m.group(4)),
                'text-[rgba(%s,%s,%s,%s)]' % (m.group(1), m.group(2), m.group(3), m.group(4)))
    got = colours_in(cls, pal, src, required=required)
    return got[0] if got else (None, None)


def pd_bg(cls, pal, src):
    """The colour of a marker the zip draws as a BACKGROUND (the dots, the bars)."""
    m = re.search(r'bg-\[rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)\]', cls)
    if m:
        return ('rgba(%s, %s, %s, %s)' % (m.group(1), m.group(2), m.group(3), m.group(4)),
                'bg-[rgba(%s,%s,%s,%s)]' % (m.group(1), m.group(2), m.group(3), m.group(4)))
    m = re.search(r'bg-\[#([0-9a-fA-F]{6})\]', cls)
    if m:
        return '#' + m.group(1).upper(), 'bg-[#%s]' % m.group(1)
    m = re.search(r'(?<![\w-])bg-(white|black)(?:/(\d+|\[[\d.]+\]))?(?![\w-])', cls)
    if m:
        return (rgba(NAMED[m.group(1)], alpha_tok(m.group(2))),
                'bg-%s%s' % (m.group(1), '/' + m.group(2) if m.group(2) else ''))
    m = re.search(r'(?<![\w-])bg-([a-z]+)(?![\w-])', cls)
    if m and m.group(1) in pal:
        return pal[m.group(1)].upper(), 'bg-%s' % m.group(1)
    raise SystemExit('BUILD FAILURE: no background colour at %s (%r)' % (src, cls))


def pd_classes(anchor):
    """class_block, or the RAW source when the classes live in a template literal.

    Three of this zip's markers (the dots and the eq bars) are inside
    className={... ? "a" : "b"}, which class_block does not read; its failure is
    loud, so the fallback is a decision and not a guess.
    """
    try:
        return class_block(anchor)
    except SystemExit:
        raw, src = raw_block(anchor)
        return raw, src + ' (template literal: read raw)'


def pd_border(cls, src):
    """border-white/10 -> (hex, alpha, label). NO border is a stated value here."""
    m = re.search(r'(?<![\w-])border-(white|black)(?:/(\d+|\[[\d.]+\]))?(?![\w-])', cls)
    if not m:
        return ('#000000', 1.0, 'the zip states NO border on this panel')
    return (NAMED[m.group(1)], alpha_tok(m.group(2)),
            'border-%s%s' % (m.group(1), '/' + m.group(2) if m.group(2) else ''))


def pd_alpha(colour, a):
    """The same colour at a stated alpha, whatever shape it arrived in."""
    m = re.match(r'rgba\((\d+), (\d+), (\d+), ([\d.]+)\)', colour)
    if m:
        return 'rgba(%s, %s, %s, %s)' % (m.group(1), m.group(2), m.group(3), '%g' % a)
    if colour.startswith('#'):
        return rgba(colour, a)
    raise SystemExit('BUILD FAILURE: cannot set alpha on %r' % colour)


def pd_weight(cls, src, default=None):
    """Named weights AND the arbitrary one this zip uses (font-[450])."""
    m = re.search(r'(?<![\w-])font-\[(\d+)\](?![\w-])', cls)
    if m:
        return m.group(1)
    return u_weight(cls, src, default)


def pd_leading(cls, src, default=None):
    """leading-[1.6] and the named scale (leading-snug = 1.375)."""
    m = re.search(r'(?<![\w-])leading-\[([^\]]+)\](?![\w-])', cls)
    if m:
        return m.group(1)
    m = re.search(r'(?<![\w-])leading-(none|tight|snug|normal|relaxed|loose)(?![\w-])', cls)
    if m:
        return PD_LEADING[m.group(1)]
    if default is not None:
        return default
    raise SystemExit('BUILD FAILURE: no leading-* at %s (%r)' % (src, cls))


def pd_ramp(anchor):
    """Math.max(0.6 - (n - 1 - i) * 0.08, 0.14) -> (newest, step, floor, label, src)."""
    raw, src = raw_block(anchor)
    m = re.search(r'Math\.max\(([\d.]+)\s*-\s*\(n\s*-\s*1\s*-\s*i\)\s*\*\s*([\d.]+),\s*([\d.]+)\)', raw)
    if not m:
        raise SystemExit('BUILD FAILURE: no opacity ramp at %s (%r)' % (src, raw))
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)),
            'opacity Math.max(%s - (n - 1 - i) * %s, %s)' % (m.group(1), m.group(2), m.group(3)),
            src)


def pd_lum(v):
    if v.startswith('#') and len(v) == 7:
        return int(v[1:3], 16) + int(v[3:5], 16) + int(v[5:7], 16)
    m = re.match(r'rgba\((\d+), (\d+), (\d+), ([\d.]+)\)', v)
    if m:
        return (int(m.group(1)) + int(m.group(2)) + int(m.group(3))) * float(m.group(4))
    raise SystemExit('BUILD FAILURE: cannot rank %r' % v)


# --------------------------------------------------------------------------- #
# WHERE EACH OF THE FIVE STATES EACH THING. Every entry is a LITERAL substring of
# the zip and at() turns it into a line number, so a moved anchor is a build
# failure rather than a silently stale value.
# --------------------------------------------------------------------------- #
PD_SPEC = {
    1: dict(
        panel=(PD_PANELS, 'absolute inset-0 flex flex-col font-cond', 1),
        frame_style=(PD_PANELS, 'linear-gradient(to right, rgba(5,7,10,0.82)', 1),
        head=(PD_PANELS, 'flex items-center gap-2 px-7 pt-6', 1),
        brand=(PD_PANELS, 'text-[11px] font-body font-semibold uppercase tracking-[0.34em] text-white/30', 1),
        dot=(PD_PANELS, 'h-[5px] w-[5px] rounded-full', 3),
        muted=(PD_PANELS, 'text-[11px] font-body font-semibold uppercase tracking-[0.34em] text-white/30', 1),
        idle=(PD_PANELS, 'h-[5px] w-[5px] rounded-full', 3),
        body=(PD_PANELS, 'mask-fade-top flex flex-1 flex-col justify-end gap-[14px]', 1),
        closed=(PD_PANELS, 'line-in text-[25px] leading-[1.12] font-medium text-white', 1),
        live=(PD_PANELS, 'tp-active ml-[7px] text-[32px] leading-[1.1] font-semibold text-white', 1),
        ramp=(PD_PANELS, 'opacity: Math.max(0.6 - (n - 1 - i) * 0.08, 0.14)', 1),
        meta=None, clock=None, time=None, live_text=None, live_style=None,
        rail=None, closed_text=None,
    ),
    2: dict(
        panel=(PD_PANELS, 'absolute inset-0 flex flex-col border border-white/10 bg-[rgba(8,10,13,0.88)] font-mono', 1),
        frame_style=None,
        head=(PD_PANELS, 'border-b border-white/10 px-4 pb-2.5 pt-3.5', 1),
        brand=(PD_PANELS, 'text-[10px] font-semibold tracking-[0.18em] text-accent', 3),
        dot=(PD_PANELS, 'h-[7px] w-[7px] rounded-full', 3),
        muted=(PD_PANELS, 'tracking-[0.12em] text-white/45', 1),
        idle=(PD_PANELS, 'h-[7px] w-[7px] rounded-full', 3),
        body=(PD_PANELS, 'mask-fade-top flex flex-1 flex-col justify-end gap-[9px]', 1),
        closed=(PD_PANELS, 'line-in text-[13.5px] leading-snug', 1),
        closed_text=(PD_PANELS, 'text-white/55', 1),
        live=(PD_PANELS, 'line-in border-l-2 border-accent bg-[rgba(232,87,79,0.08)] py-1.5 pl-3 pr-2', 1),
        live_text=(PD_PANELS, 'text-[13.5px] leading-snug text-white', 1),
        ramp=None,
        time=(PD_PANELS, 'mr-2 text-white/25 tabular-nums', 1),
        meta=(PD_PANELS, 'mt-1 text-[9.5px] text-white/25 tabular-nums', 1),
        clock=(PD_PANELS, 'text-[12px] font-medium text-white/85 tabular-nums', 1),
        live_style=None, rail=None,
    ),
    3: dict(
        panel=(PD_PANELS, 'absolute inset-0 bg-[rgba(12,12,15,0.62)] backdrop-blur-[7px]', 1),
        frame_style=None,
        head=(PD_PANELS, 'absolute left-7 top-7 flex items-baseline gap-2', 1),
        brand=(PD_PANELS, 'text-[10px] font-semibold uppercase tracking-[0.3em] text-white/28', 1),
        dot=None,
        muted=(PD_PANELS, 'text-[10px] font-semibold uppercase tracking-[0.3em] text-white/28', 1),
        idle=(PD_PANELS, 'text-[10px] italic text-white/20', 1),
        body=(PD_PANELS, 'mask-fade-top absolute inset-x-0 bottom-0 top-20 flex flex-col justify-end gap-[15px]', 1),
        closed=(PD_PANELS, 'line-in font-body text-[18px] leading-[1.6] font-[450] text-[rgba(235,232,225,0.88)]', 1),
        live=(PD_PANELS, 'font-body text-[18px] leading-[1.6] italic text-[rgba(235,232,225,0.52)]', 1),
        ramp=None, time=None, live_text=None, live_style=None, rail=None, closed_text=None,
        meta=(PD_PANELS, 'text-[10px] italic text-white/20', 1), clock=None,
    ),
    4: dict(
        panel=(PD_PANELS, 'absolute inset-0 backdrop-blur-[3px]', 1),
        frame_style=(PD_PANELS, 'linear-gradient(to top, rgba(4,5,8,0.72)', 1),
        head=None, dot=None,
        brand=(PD_PANELS, 'absolute bottom-7 right-9 font-cinema text-[13px] italic text-white/25', 1),
        muted=(PD_PANELS, 'absolute bottom-7 right-9 font-cinema text-[13px] italic text-white/25', 1),
        idle=(PD_PANELS, 'mr-2.5 text-white/25', 1),
        body=(PD_PANELS, 'mask-fade-top absolute inset-x-0 bottom-0 top-0 flex flex-col justify-end gap-[26px]', 1),
        closed=(PD_PANELS, 'line-in font-cinema text-[21px] leading-[1.55] font-medium text-[#f1ece2]', 1),
        live=(PD_PANELS, 'border-l border-white/25 pl-4 font-cinema text-[21px] leading-[1.55] font-medium text-[#f1ece2]', 1),
        ramp=(PD_PANELS, 'opacity: Math.max(0.92 - (n - 1 - i) * 0.13, 0.3)', 1),
        live_style=(PD_PANELS, 'opacity: 0.5, filter: "blur(0.45px)"', 1),
        meta=None, clock=None, time=None, live_text=None, rail=None, closed_text=None,
    ),
    5: dict(
        panel=(PD_PANELS, 'absolute inset-0 flex flex-col overflow-hidden rounded-[10px] border border-white/[0.08] bg-[rgba(10,12,15,0.92)] font-instr', 1),
        frame_style=None,
        head=(PD_PANELS, 'flex items-center justify-between border-b border-white/[0.07] px-5 pb-3.5 pt-4', 1),
        brand=(PD_PANELS, 'text-[11px] font-medium tracking-[0.24em] text-white/70', 1),
        dot=(PD_PANELS, 'h-full w-[3px] rounded-sm bg-accent', 1),
        muted=(PD_PANELS, 'text-[10px] tracking-[0.14em] text-white/30', 1),
        idle=(PD_PANELS, 'w-[3px] rounded-sm bg-white/25', 1),
        body=(PD_PANELS, 'mask-fade-top flex flex-1 flex-col justify-end gap-[13px]', 1),
        closed=(PD_PANELS, 'line-in ml-[16px] text-[18px] leading-[1.3] font-medium text-white', 1),
        live=(PD_PANELS, 'text-[23px] leading-[1.22] font-bold text-white', 1),
        rail=(PD_PANELS, 'indicator-pulse w-[3px] shrink-0 self-stretch rounded-full bg-accent', 1),
        ramp=(PD_PANELS, 'opacity: Math.max(0.5 - (n - 1 - i) * 0.06, 0.14)', 1),
        meta=(PD_PANELS, 'text-[10px] tracking-[0.14em] text-white/30', 1),
        clock=(PD_PANELS, 'text-[12px] text-white/40 tabular-nums', 1),
        time=None, live_text=None, live_style=None, closed_text=None,
    ),
}


PD_CSS_OUT = os.path.join(OUT, 'panel-designs.css')
PD_JS_OUT = os.path.join(OUT, 'panel-designs.js')

PD_IDEAS = {
    1: 'The teleprompter: Barlow Condensed, one flat left-aligned column, the '
       'closed rows stepping down a five-step opacity ramp and the live line '
       'stepping OUT of that column by 7px at 32px. No rail, no border, no time.',
    2: 'The broadcast monitor: IBM Plex Mono, a hairline-bordered chassis, a REC '
       'lamp and a wall clock, and the live line as a bordered tinted block with '
       'the accent rail. The only design here that prints a timecode per row.',
    3: 'The manuscript: Instrument Sans on a notebook sheet, a hairline margin '
       'rule at 27px, and the live line in italic UNDERLINED at 52 % -- the '
       'correction visibly in progress. No indicator, no rail, no time.',
    4: 'The cinema card: Fraunces, one wide column of large serif lines, the '
       'closed rows on a 0.92 to 0.30 ramp, the live line a 50 % blurred left-'
       'ruled quote, and the wordmark alone at the bottom right. No time.',
    5: 'The instrument: Space Grotesk in a rounded 10px card, an eq meter in the '
       'header, the live line at 23px bold behind a 3px accent rail, and the '
       'closed rows indented 16px to clear it. A keycap footer. No time.',
}

PD_SIG = {
    1: "@S@ .panel {\n"
       "  background: linear-gradient(to right, rgba(5, 7, 10, 0.82) 0%, rgba(5, 7, 10, 0.42) 62%, rgba(5, 7, 10, 0.12) 100%);\n"
       "  border-color: transparent;\n  border-radius: 0;\n  box-shadow: none;\n}\n"
       "@S@ .panel__header { padding: 24px 28px 0; }\n"
       "@S@ .wordmark { display: none; }\n"
       "@S@ .chrome--tele .chrome__dot { width: 5px; height: 5px; border-radius: 999px; background: @idle@; }\n"
       "@S@ body[data-state=\"live\"] .chrome--tele .chrome__dot { background: @accent@; }\n"
       "@S@ .captions__body { padding: 96px 28px 56px; }\n"
       "@S@ .captions__list { gap: 14px; }\n"
       "@B@ .caption { padding: 0; border-left: 0; background: transparent; }\n"
       "@B@ .caption--provisional .caption__text { margin-left: 7px; }\n"
       "@S@ .caption__time, @S@ .caption__mark { display: none; }\n",
    2: "@S@ .panel {\n  background: rgba(8, 10, 13, 0.88);\n"
       "  border-color: @line@;\n  border-radius: 0;\n  box-shadow: none;\n}\n"
       "@S@ .panel__header { padding: 14px 16px 10px; border-bottom: 1px solid @line@; }\n"
       "@S@ .wordmark { display: none; }\n"
       "@S@ .chrome--bcast .chrome__dot { width: 7px; height: 7px; border-radius: 999px; background: @idle@; }\n"
       "@S@ body[data-state=\"live\"] .chrome--bcast .chrome__dot { background: @accent@; }\n"
       "@S@ .chrome--bcast .chrome__tc { font-size: 12px; font-weight: 500; color: @text_primary@; font-variant-numeric: tabular-nums; }\n"
       "@S@ .captions__body { padding: 80px 16px 12px; }\n"
       "@S@ .captions__list { gap: 9px; }\n"
       "@B@ .caption { padding: 0; border-left: 0; background: transparent; }\n"
       "@B@ .caption--provisional { border-left: 2px solid @accent@; background: @prov_bg@; padding: 6px 8px 6px 12px; }\n"
       "@S@ .caption__time { font-size: 12px; color: @text_muted@; font-variant-numeric: tabular-nums; }\n"
       "@S@ .chrome--bcast[data-chrome=\"foot\"] { border-top: 1px solid @line@; padding: 10px 16px; }\n",
    3: "@S@ .panel {\n  background: rgba(12, 12, 15, 0.62);\n"
       "  border-color: transparent;\n  border-radius: 0;\n  box-shadow: none;\n}\n"
       "@S@ .panel::before {\n  content: \"\";\n  position: absolute;\n"
       "  left: 27px;\n  top: 32px;\n  bottom: 32px;\n  width: 1px;\n"
       "  background: rgba(255, 255, 255, 0.07);\n}\n"
       "@S@ .panel__header { padding: 28px 32px 0; }\n"
       "@S@ .wordmark { display: none; }\n"
       "@S@ .captions__body { padding: 80px 32px 32px 48px; }\n"
       "@S@ .captions__list { gap: 15px; }\n"
       "@B@ .caption { padding: 0; border-left: 0; background: transparent; }\n"
       "@S@ .caption__time, @S@ .caption__mark { display: none; }\n",
    4: "@S@ .panel {\n"
       "  background: linear-gradient(to top, rgba(4, 5, 8, 0.72) 0%, rgba(4, 5, 8, 0.4) 55%, rgba(4, 5, 8, 0.14) 100%);\n"
       "  border-color: transparent;\n  border-radius: 0;\n  box-shadow: none;\n}\n"
       "@S@ .panel__header { padding: 32px 36px 0; }\n"
       "@S@ .wordmark {\n  display: flex;\n  position: absolute;\n"
       "  right: 36px;\n  bottom: 28px;\n  z-index: 4;\n}\n"
       "@S@ .wordmark__mark { display: none; }\n"
       "@S@ .wordmark__name { font-family: var(--font-sans); font-size: 13px; font-style: italic; font-weight: 400; letter-spacing: 0; color: @text_muted@; }\n"
       "@S@ .wordmark__tag { display: none; }\n"
       "@S@ .captions__body { padding: 128px 36px 80px; }\n"
       "@S@ .captions__list { gap: 26px; }\n"
       "@B@ .caption { padding: 0; border-left: 0; background: transparent; }\n"
       "@B@ .caption__mark { margin-right: 10px; color: @text_muted@; }\n"
       "@S@ .caption__time { display: none; }\n",
    5: "@S@ .panel {\n  background: rgba(10, 12, 15, 0.92);\n"
       "  border-color: @line@;\n  border-radius: 10px;\n  box-shadow: none;\n}\n"
       "@S@ .panel__header { padding: 16px 20px 14px; border-bottom: 1px solid @line@; }\n"
       "@S@ .wordmark { display: none; }\n"
       "@S@ .chrome--inst .chrome__meter { display: flex; align-items: flex-end; gap: 3px; height: 18px; }\n"
       "@S@ .chrome--inst .chrome__meter i { width: 3px; border-radius: 4px; background: @idle@; }\n"
       "@S@ .chrome--inst .chrome__meter i:nth-child(1) { height: 5px; }\n"
       "@S@ .chrome--inst .chrome__meter i:nth-child(2) { height: 8px; }\n"
       "@S@ .chrome--inst .chrome__meter i:nth-child(3) { height: 4px; }\n"
       "@S@ .chrome--inst .chrome__meter i:nth-child(n+4) { display: none; }\n"
       "@S@ body[data-state=\"live\"] .chrome--inst .chrome__meter i { background: @accent@; }\n"
       "@S@ .captions__body { padding: 64px 20px 24px; }\n"
       "@S@ .captions__list { gap: 13px; }\n"
       "@B@ .caption { padding: 0; border-left: 0; background: transparent; margin-left: 16px; }\n"
       "@S@ .caption__time { font-size: 12px; color: @text_muted@; font-variant-numeric: tabular-nums; }\n"
       "@S@ .chrome--inst[data-chrome=\"foot\"] { border-top: 1px solid @line@; padding: 12px 20px; }\n",
}

HEAD_PD = '''/* Sotto -- {name} ({sel}).
 *
 * GENERATED BY _main/_design-lane/gen_themes.py. Do not edit this file: edit the
 * generator and regenerate. --trace prints every value below with the line of the
 * zip it was read from.
 *
 * THE DESIGN IS sotto-transcription-panel-designs.zip ({key}), unpacked at
 * _main/_design-lane/zips/panel-designs/: src/index.css (the @theme palette and
 * the font stacks), src/components/panels.tsx (the five panel designs),
 * src/components/Stage.tsx (the stage and the control cluster) and
 * src/lib/scripts.ts (the zip's own directions table). This file is a PARSE of
 * that source, not a recolour of another theme: the frame, the type tiers, the
 * live-line treatment and the closed-row ramp below are the ones THIS design
 * states, and a value the zip does not state fails the build.
 *
 * {idea}
 *
 * ONE DEVIATION, AND IT IS IN ALPHA ONLY. The zip renders its panel over its own
 * opaque black stage (Stage.tsx:48) behind a 2-8px backdrop blur, and a WebView2
 * window cannot blur the desktop behind it. So the panel tint is COMPOSITED over
 * that black at alpha {slab} for all five: the hue is the zip's, the alpha is
 * Sotto's, and the alpha is applied at GENERATION time — by `over_black()` and by
 * the `color-mix()` of the skin's slab rule — not by a token (the dead
 * `--slab-opacity` declaration was removed under D6). The blur is dropped for the
 * same reason.
 *
 * THE BUTTON CLUSTER IS THE ONE THING THIS FILE DOES NOT TAKE FROM THE ZIP, and
 * it is the one thing the owner's rule allows to differ. These five designs have
 * NO buttons in the panel at all: the zip puts its controls on the stage, at
 * Stage.tsx:133 -- absolute bottom-4 left-4 flex flex-col items-start gap-2.5, a
 * vertical column of chips at the stage's bottom-left (recorded as controls_pos in
 * --trace). Sotto's own cluster (theme, clear, quit, font size, pause, hide) keeps
 * SOTTO's placement in the panel header, exactly as the five themes of the first
 * zip do, and this file only paints it.
 *
 * THE FIVE ARE NOT ONE SKIN. This zip has ONE accent (--color-accent: #E8574F)
 * and the five designs differ in everything else; this one's accent token is
 * {accent}, and its frame and its live line are its own. Three of the five share
 * the accent swatch because the zip itself does.
 */
'''


def build_panel_theme(i, pal, psrc, fonts, fsrc, first, dirs):
    """One design, every token parsed from the second zip."""
    spec = PD_SPEC[i]
    d = dirs[i]
    t = Theme(5 + i)
    t['id'] = i
    t['key'] = d['key']
    t['name'] = d['name']
    t['sel'] = PD_IDS[i]
    t['chrome'] = i
    t['label'] = d['name'] + ' \u00b7 painel'
    dsrc = '%s:%d' % (where(PD_SCRIPTS), d['line'])
    t.put('idea', PD_IDEAS[i], dsrc + ' (the direction this zip itself describes)')

    # ---- identity, from the zip's own DIRECTIONS table ---------------------
    fam = first.get(d['font'])
    if fam is None:
        raise SystemExit('BUILD FAILURE: %s:%d names font %r and %s declares no '
                         'stack that starts with it'
                         % (where(PD_SCRIPTS), d['line'], d['font'], where(PD_CSS)))
    t.put('font_sans', fonts[fam],
          '%s (scripts.ts:%d names %s)' % (fsrc[fam], d['line'], d['font']))
    t.put('font_mono', fonts['mono'], fsrc['mono'])
    t.put('slab_strong', pal['coal'], psrc['coal'])
    t.put('space', SPACE,
          'the shared Tailwind space scale (this zip writes px-[...] and gap-[...] directly)')

    # ---- the frame ---------------------------------------------------------
    panel, panel_src = pd_classes(spec['panel'])
    if spec.get('frame_style'):
        raw, rsrc = raw_block(spec['frame_style'])
        slab, slab_a, slab_lbl = pd_first_stop(raw, rsrc)
        panel_src = rsrc
    else:
        slab, slab_a, slab_lbl = pd_surface(panel, panel_src)
    t.put('slab', over_black(slab, slab_a),
          '%s (%s composited over the stage black)' % (panel_src, slab_lbl))
    t.put('slab_opacity', SLAB_OPACITY,
          'Sotto-side alpha: the zip blurs a live photo behind this panel (%s) and a '
          'WebView2 window cannot blur the desktop' % where(PD_STAGE))
    bc, ba, blbl = pd_border(panel, panel_src)
    t.put('line', 'transparent' if ba >= 1.0 else rgba(bc, ba), '%s (%s)' % (panel_src, blbl))
    t.put('line_strong', 'transparent' if ba >= 1.0 else rgba(bc, min(1.0, round(ba * 2.2, 2))),
          '%s (%s x 2.2)' % (panel_src, blbl))
    t.put('accent_soft', rgba(pal['accent'], ba if ba < 1.0 else 0.12),
          '%s at the panel border alpha' % psrc['accent'])
    rm = re.search(r'rounded-\[(\d+)px\]', panel)
    t.put('radius_lg', (rm.group(1) + 'px') if rm else '0px',
          panel_src if rm else '%s (the zip states NO radius on this panel)' % panel_src)
    t.put('radius_md', '6px', '%s:134 (rounded-md, the stage control cluster)' % where(PD_STAGE))
    t.put('radius_sm', '4px', '%s:291 (rounded-sm, the eq bars)' % where(PD_PANELS))
    t.put('radius_dialog', '6px', '%s:134 (the zip rounds its controls, not its panel)' % where(PD_STAGE))
    t.put('shadow_slab', 'none',
          'the zip states NO shadow on this panel (no shadow-* anywhere in %s)' % where(PD_PANELS))

    # ---- the accent: the colour THIS design's own marker uses --------------
    if i == 3:
        t.put('accent', pal['amberx'], '%s (scripts.ts:%d tags this direction "amberx")'
              % (psrc['amberx'], d['line']))
    elif i == 4:
        t.put('accent', '#F1ECE2', '%s:235 (this design has no red; its live line is the ink)'
              % where(PD_PANELS))
    else:
        t.put('accent', pal['accent'], psrc['accent'])

    # ---- the type tiers ----------------------------------------------------
    brand, brand_src = pd_classes(spec['brand'])
    closed, closed_src = pd_classes(spec['closed'])
    live, live_src = pd_classes(spec['live'])
    closed_c, closed_csrc = (pd_classes(spec['closed_text']) if spec.get('closed_text')
                             else (closed, closed_src))
    live_c, live_csrc = (pd_classes(spec['live_text']) if spec.get('live_text')
                         else (live, live_src))
    meta, meta_src = (pd_classes(spec['meta']) if spec.get('meta') else (brand, brand_src))
    clock, clock_src = (pd_classes(spec['clock']) if spec.get('clock') else (meta, meta_src))
    muted, muted_src = (pd_classes(spec['muted']) if spec.get('muted') else (meta, meta_src))

    t.put('size_caption', u_size(live_c, live_csrc), live_csrc)
    t.put('leading_caption', pd_leading(live_c, live_csrc, '1.4'), live_csrc)
    t.put('weight_caption', pd_weight(live_c, live_csrc, '400'), live_csrc)
    t.put('tracking_caption', u_tracking(live_c, live_csrc, '0'), live_csrc)
    t.put('caption_upper', 'uppercase' if u_has(live_c, 'uppercase') else 'none', live_csrc)
    t.put('cap_align', 'center' if u_has(live_c, 'text-center') else 'left', live_csrc)
    t.put('size_closed', u_size(closed, closed_src), closed_src)
    t.put('leading_closed', pd_leading(closed, closed_src, '1.4'), closed_src)
    t.put('weight_closed', pd_weight(closed, closed_src, '400'), closed_src)
    t.put('size_chrome', u_size(brand, brand_src), brand_src)
    t.put('tracking_brand', u_tracking(brand, brand_src, '0'), brand_src)
    t.put('weight_brand', pd_weight(brand, brand_src, '400'), brand_src)
    braw, braw_src = raw_block(spec['brand'])
    caps = re.search(r'>\s*([A-Z][A-Z0-9 /\u00b7.\-]{2,})\s*<', braw)
    if u_has(brand, 'uppercase'):
        t.put('brand_upper', 'uppercase', '%s (uppercase)' % brand_src)
    elif caps:
        t.put('brand_upper', 'uppercase',
              '%s (the zip writes its own mark in caps: %s)' % (braw_src, caps.group(1).strip()))
    else:
        t.put('brand_upper', 'none', brand_src)
    t.put('size_meta', u_size(meta, meta_src), meta_src)
    t.put('size_small', u_size(meta, meta_src), meta_src)
    t.put('size_time', u_size(clock, clock_src), clock_src)

    # ---- the four text tiers ----------------------------------------------
    c_hex, c_lbl = pd_text(closed_c, pal, closed_csrc, required=False)
    if c_hex is None:
        raise SystemExit('BUILD FAILURE: no closed-row colour at %s' % closed_csrc)
    if spec.get('ramp'):
        newest, step, floor, ramp_lbl, ramp_src = pd_ramp(spec['ramp'])
        t.put('text_secondary', pd_alpha(c_hex, newest),
              '%s (%s) at %s' % (closed_csrc, c_lbl, ramp_lbl))
        t.put('time_past', pd_alpha(c_hex, floor),
              '%s (the ramp FLOOR: the oldest row this design will draw)' % ramp_src)
    else:
        t.put('text_secondary', c_hex, '%s (%s)' % (closed_csrc, c_lbl))
        if spec.get('time'):
            tc, tsrc = pd_classes(spec['time'])
            th, tl = pd_text(tc, pal, tsrc)
            t.put('time_past', th, '%s (%s)' % (tsrc, tl))
        else:
            t.put('time_past', c_hex,
                  '%s (%s; this design states ONE colour for every closed row)'
                  % (closed_csrc, c_lbl))

    p_hex, p_lbl = pd_text(live_c, pal, live_csrc)
    prov = p_hex
    if spec.get('live_style'):
        raw, rsrc = raw_block(spec['live_style'])
        om = re.search(r'opacity:\s*([\d.]+)', raw)
        if om:
            prov = pd_alpha(p_hex, float(om.group(1)))
            p_lbl = '%s at opacity %s (%s)' % (p_lbl, om.group(1), rsrc)
    t.put('text_provisional', prov, '%s (%s)' % (live_csrc, p_lbl))
    t.put('text_confirmed', t['text_secondary'],
          '%s (the settled tier: this design draws its closed rows there)' % closed_csrc)
    t.put('text_primary', max((t['text_confirmed'], t['text_provisional']), key=pd_lum),
          'derived: the brighter of the settled tier and the live line')
    m_hex, m_lbl = pd_text(muted, pal, muted_src)
    t.put('text_muted', m_hex, '%s (%s: the chrome/meta tier)' % (muted_src, m_lbl))
    idle_cls, idle_src = (pd_classes(spec['idle']) if spec.get('idle') else (muted, muted_src))
    i_hex, i_lbl = pd_text(idle_cls, pal, idle_src, required=False)
    if i_hex is None:
        i_hex, i_lbl = pd_bg(idle_cls, pal, idle_src)
    t.put('idle', i_hex, '%s (%s: the resting marker)' % (idle_src, i_lbl))
    t.put('ok', pal['moss'], psrc['moss'])
    t.put('busy', pal['amberx'], psrc['amberx'])
    t.put('error', pal['accent'], psrc['accent'])

    # ---- the live line: rail, pad, wash, decorations ----------------------
    rail_w, rail_src = '0px', '%s (the zip states no rail on this live line)' % live_src
    m = re.search(r'border-l-(\d+)(?![\w.])', live)
    if m:
        rail_w = m.group(1) + 'px'
        rail_src = '%s (border-l-%s)' % (live_src, m.group(1))
    if spec.get('rail'):
        rc, rsrc = pd_classes(spec['rail'])
        rw, rlbl = dim_in(rc, 'w', rsrc)
        rail_w, rail_src = rw, '%s (%s)' % (rsrc, rlbl)
    t.put('prov_rail_w', rail_w, rail_src)
    t.put('prov_rail_style', 'solid', 'the zip draws its rails solid')
    pad, pad_src = '0px', '%s (no left pad: the live line sits in a flex column)' % live_src
    pm = re.search(r'(?<![\w-])pl-(%s)(?![\w.])' % STEP, live)
    if pm and float(pm.group(1)) in SCALE and float(pm.group(1)).is_integer():
        pad = 'var(--space-%d)' % int(float(pm.group(1)))
        pad_src = '%s (pl-%s)' % (live_src, pm.group(1))
    t.put('prov_pad', pad, pad_src)
    bg, bg_src = 'transparent', '%s (no wash on this live line)' % live_src
    bm = re.search(r'bg-\[rgba\([^)]*\)\]', live)
    if bm:
        bg, bg_src = bm.group(0)[4:-1], '%s (%s)' % (live_src, bm.group(0))
    t.put('prov_bg', bg, bg_src)
    extra = []
    if u_has(live_c, 'italic'):
        extra.append('font-style: italic')
    if u_has(live_c, 'underline'):
        extra.append('text-decoration: underline')
        dm = re.search(r'(?<![\w-])decoration-([a-z]+)/(\d+)(?![\w-])', live_c)
        if dm:
            dcol = NAMED.get(dm.group(1)) or pal.get(dm.group(1))
            if dcol is None:
                raise SystemExit('BUILD FAILURE: unknown decoration colour %r at %s'
                                 % (dm.group(1), live_csrc))
            extra.append('text-decoration-color: %s' % rgba(dcol, alpha_tok(dm.group(2))))
        dm = re.search(r'decoration-\[(\d+px)\]', live_c)
        if dm:
            extra.append('text-decoration-thickness: %s' % dm.group(1))
        dm = re.search(r'underline-offset-\[(\d+px)\]', live_c)
        if dm:
            extra.append('text-underline-offset: %s' % dm.group(1))
    if spec.get('live_style'):
        raw, rsrc = raw_block(spec['live_style'])
        fm = re.search(r'filter:\s*"blur\(([\d.]+px)\)"', raw)
        if fm:
            extra.append('filter: blur(%s)' % fm.group(1))
            extra.append('opacity: %s' % re.search(r'opacity:\s*([\d.]+)', raw).group(1))
    t.put('prov_extra', '; '.join(extra) + ';' if extra else '',
          '%s (%s)' % (live_csrc, ', '.join(extra) or 'no decoration'))
    t.put('prov_style', 'normal', 'the live line keeps the face the zip gives it')
    t.put('closed_rail_w', '0px', '%s (the zip draws no rail on a closed row)' % closed_src)
    t.put('time_live', 'var(--text-muted)', 'Sotto chrome: the live clock is this design\'s meta tier')
    t.put('live_shadow', 'none', 'the zip states no glow on this live line')
    t.put('time_family', 'var(--font-mono)' if spec.get('time') else 'var(--font-sans)',
          '%s (the row timecode)' % (spec.get('time') and pd_classes(spec['time'])[1] or closed_src))
    t['sig'] = PD_SIG[i]
    t.put('controls_pos', 'absolute bottom-4 left-4 flex flex-col items-start gap-2.5',
          '%s:133 (the zip puts its own controls here -- on the STAGE, not in the panel; '
          'Sotto\'s chrome cluster keeps Sotto\'s placement, the one permitted deviation)'
          % where(PD_STAGE))
    return t


def parsed_panel_designs():
    pal, psrc = pd_palette()
    fonts, fsrc, first = pd_fonts()
    dirs = pd_directions()
    return [build_panel_theme(i, pal, psrc, fonts, fsrc, first, dirs) for i in (1, 2, 3, 4, 5)]


def build_panel_design(t):
    """The same body, with THIS set's own provenance header in front of it."""
    text = build(t)
    i = text.index(ROOT % t['sel'])
    rest = text[text.rindex('*/', 0, i) + 2:]
    return HEAD_PD.format(name=t['name'], sel=t['sel'], key=t['key'], idea=t['idea'],
                          slab=t['slab_opacity'], accent=t['accent']) + rest


def write_panel_designs(themes):
    rows = [t for t in themes if t.get('sel')]
    if len(rows) != 5:
        raise SystemExit('BUILD FAILURE: %d panel-design theme(s), not 5' % len(rows))
    text = '\n'.join(build_panel_design(t) for t in rows)
    with open(PD_CSS_OUT, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %-46s %6d bytes  %4d lines'
          % (PD_CSS_OUT, len(text.encode('utf-8')), text.count('\n')))


def write_panel_manifest(themes):
    """panel-designs.js: the manifest FRAGMENT, same shape as the skins precedent."""
    rows = [t for t in themes if t.get('sel')]
    if len(rows) != 5:
        raise SystemExit('BUILD FAILURE: %d panel-design entry(ies), not 5' % len(rows))
    out = []
    out.append('/* panel-designs.js -- the manifest FRAGMENT for the second zip.')
    out.append(' *')
    out.append(' * GENERATED BY _main/_design-lane/gen_themes.py. Do not edit this file:')
    out.append(' * edit the generator and regenerate.')
    out.append(' *')
    out.append(' * WHY A FRAGMENT AND NOT A THEME: app/panel/themes/themes.js carries the five')
    out.append(' * designs of sotto-app-design-directions.zip, and app/panel/themes/skins.js set')
    out.append(' * the precedent -- a second file, loaded after the manifest, that pushes its own')
    out.append(' * entries into SottoThemeManifest.themes. This is that file for')
    out.append(' * sotto-transcription-panel-designs.zip, whose five designs REUSE the same five')
    out.append(' * names as a different implementation (own palette, own components). They are a')
    out.append(' * separate set, they have their own stylesheet, and they are loaded by')
    out.append(' * app/panel/panel.html in two lines:')
    out.append(' *   <link rel="stylesheet" href="themes/panel-designs.css" />   (in <head>)')
    out.append(' *   <script src="themes/panel-designs.js"></script>              (after themes.js)')
    out.append(' *')
    out.append(' * The swatch of each entry IS that design\'s own accent token in the stylesheet:')
    for t in rows:
        out.append(' *   %-9s %s  <- %s' % (t['sel'], t['accent'], t['src']['accent']))
    out.append(' */')
    out.append('(function (root) {')
    out.append("  'use strict';")
    out.append('  var fragment = [')
    for k, t in enumerate(rows):
        out.append('    {')
        out.append("      name: '%s'," % t['sel'])
        out.append("      label: '%s'," % t['label'])
        out.append("      file: 'themes/panel-designs.css',")
        out.append("      swatch: '%s'," % t['accent'])
        out.append("      group: 'panel-designs',")
        out.append("      groupLabel: 'Pain\u00e9is (2.\u00ba zip)'")
        out.append('    }' + (',' if k < len(rows) - 1 else ''))
    out.append('  ];')
    out.append('  root.SOTTO_THEME_MANIFEST_FRAGMENT = fragment;')
    out.append('  var manifest = root.SottoThemeManifest;')
    out.append('  if (!manifest || !manifest.themes || typeof manifest.themes.push !== "function") {')
    out.append('    return;')
    out.append('  }')
    out.append('  for (var i = 0; i < fragment.length; i += 1) {')
    out.append('    manifest.themes.push(fragment[i]);')
    out.append('  }')
    out.append("})(typeof window !== 'undefined' ? window : this);")
    out.append('')
    text = '\n'.join(out)
    with open(PD_JS_OUT, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(text)
    print('wrote %-46s %6d bytes  %4d lines'
          % (PD_JS_OUT, len(text.encode('utf-8')), text.count('\n')))


def trace_table(themes):
    """The provenance table: every emitted token and the zip line it came from."""
    out = []
    for t in themes:
        # Resolve the signature markers HERE too, so the table below carries the
        # rows they turn into: the markers are the one place a theme states a
        # value the token layer does not, and an empty ledger line would hide it.
        build(t)
        out.append('### %s -- %s' % (t.get('sel') or ('theme-%d' % t['n']), t['name']))
        out.append('')
        out.append('| token | value | source |')
        out.append('|---|---|---|')
        for (n, token, value, src) in LEDGER:
            if n != t['n'] or token.startswith('sig:'):
                continue
            val = value if isinstance(value, str) else ' / '.join(str(v) for v in value)
            out.append('| `%s` | `%s` | `%s` |' % (token, val, src))
        sigrows = [(k, v) for (n, k, v, s) in LEDGER if n == t['n'] and k.startswith('sig:')]
        out.append('')
        out.append('signature markers resolved: ' + (', '.join(
            '`%s`=`%s`' % (k, v) for (k, v) in sigrows) or 'none'))
        out.append('')
    return '\n'.join(out)


def main():
    argv = list(sys.argv[1:])
    if '--help' in argv or '-h' in argv:
        print(__doc__)
        return
    themes = parsed_themes(IDEAS) + parsed_panel_designs()

    have = {}
    for (n, token, value, src) in LEDGER:
        have.setdefault(n, set()).add(token)
    missing = []
    for t in themes:
        for key in REQUIRED:
            if key not in have.get(t['n'], ()):
                missing.append('theme-%d:%s' % (t['n'], key))
    if missing:
        raise SystemExit('BUILD FAILURE: no provenance for %d token(s): %s'
                         % (len(missing), ', '.join(missing)))

    if '--trace' in argv:
        print(trace_table(themes))
    if '--trace' in argv or '--check' in argv:
        print('checked %d theme(s), %d ledger row(s), 0 without provenance'
              % (len(themes), len(LEDGER)))
        return

    os.makedirs(OUT, exist_ok=True)
    for t in [x for x in themes if not x.get('sel')]:
        path = os.path.join(OUT, 'theme-%d.css' % t['n'])
        text = build(t)
        # CRLF, NOT LF, and that is measured rather than a preference. The five
        # files in `app/panel/themes/` are 100 % CRLF and core.autocrlf=true, so
        # CRLF is this working tree's convention. Writing LF here would rewrite
        # every line of every theme on the next generation run -- a whole-file
        # diff that buries the one line someone meant to change.
        with open(path, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(text)
        print('wrote %-46s %6d bytes  %4d lines' % (path, len(text.encode('utf-8')),
                                                   text.count('\n')))
    write_panel_designs(themes)
    write_panel_manifest(themes)


if __name__ == '__main__':
    main()
