"""Generate the PANEL THEMES of the `cinematic` template set.

WHY A GENERATOR AND NOT TWENTY HAND-WRITTEN FILES: the owner's ask is that a theme
be a REAL change (`"eu nao quero só a paleta de cores. eu quero uma mudança mesmo, a
cada tema/template. super parecida com o que ta no zip, ou igual"`), which means every
theme repeats the same structural decisions (the caption stage, the reveal, the
backdrop, the token contract) with its own values. Written by hand, the fourth theme
is already a copy of the third with one value forgotten — and a forgotten token does
not throw, it silently inherits another design's colour.

WHERE THE VALUES COME FROM, AND WHY NOT FROM AN INVENTORY: this file PARSES the
design source the owner put in the workspace, `_main/_design-lane/zips/cinematic/
src/themes.ts`, at generation time. Being read from the source is the whole point:
an inventory is a human's summary and a summary of 20 designs is where a hex gets
transcribed one digit wrong. A value this file cannot find is a build failure, not a
default.

WHAT IT WRITES:
  app/panel/themes/cinematic.css    every theme of the set, scoped, plus the set's
                                    one shared block (the reveal keyframes and the
                                    caret — the only marker that a word is still
                                    forming in this set)
  app/panel/themes/themes.js        the manifest, with the five original directions
                                    preserved VERBATIM (they are captured out of the
                                    file being replaced, never retyped) and the set
                                    appended
  app/panel/themes/backdrops/*.jpg  the wallpaper each theme names, downloaded once

WHAT IT DELIBERATELY DOES NOT DO: it does not touch `theme-1..5.css` (owned by
`gen_themes.py`), it does not invent a colour, and it does not write a theme it could
not read a palette for.

THE TWO DECISIONS THAT ARE MINE AND NOT THE ZIP'S, both recorded here because a
reviewer should be able to challenge them:
  1. `--size-caption` takes the MAX of the source's `clamp(floor, vw, max)`. The
     source's own `vw` term is a stage unit: at our 380 px column `2.7vw` is 10 px,
     so the literal resolution of the zip's own CSS would be its FLOOR (20 px) and the
     caption would look nothing like the zip looks at full size. The max is the size
     the design was drawn for.
  2. Lines older than the newest get `0.72` of the caption size and `--text-secondary`.
     The zips only ever show ONE live line, so they state no treatment for the ones
     our panel keeps; 0.72 is the smallest number that recedes without becoming
     unreadable at 380 px.

Run: `py -3 _main/_design-lane/gen_cinematic.py`
"""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PANEL = os.path.join(ROOT, 'app', 'panel')
THEMES_DIR = os.path.join(PANEL, 'themes')
CSS_OUT = os.path.join(THEMES_DIR, 'cinematic.css')
JS_OUT = os.path.join(THEMES_DIR, 'themes.js')
BACKDROPS = os.path.join(THEMES_DIR, 'backdrops')
SOURCE = os.path.join(HERE, 'zips', 'cinematic', 'src', 'themes.ts')

# filename -> the URL it came from, so the licence note cannot drift from the files.
PHOTO_SRC = {}

PREFIX = 'cine-'

# THE OWNER'S FILTER, verbatim: *"os designs, inclua aqueles que nao sao 'agressivos
# demais'"*. Three of this zip's ten designs are out, each for a reason the source
# itself carries, never for taste:
#   motel-glow  — the zip's only caption GLOW (`0 0 26px rgba(229,143,164,0.14)`)
#   paper-moon  — the only ALL-CAPS caption at 0.16em tracking, and the only light
#                 panel, i.e. the two extremes at once
#   last-reel   — the plan's own finding: its caption class is `warm-hour`'s at weight
#                 500, a one-step grade of a design already shipped
SHIP = [
    'midnight-rain',   # fade
    'warm-hour',       # fade, display italic — the zip's only italic caption
    'velvet-dusk',     # rise — the only rise, the largest per-word travel
    'study-light',     # type + mono — the zip's only monospace caption
    'tideline',        # blur (per character)
    'quiet-streets',   # fade, 0.09em tracking — its only type difference
    'north-fog',       # blur — byte-identical to tideline but for the palette
]

# The ids that ship. `tideline` collides with a DIFFERENT design of the same name in
# the `cinematic-1` zip (unrelated palette), so this one — the body-blur one — is the
# one that carries the suffix. The plan fixes both ids; never merge them.
RENAME = {'tideline': 'tideline-body'}

# The near-duplicate pairs, so the panel can offer them as alternatives to compare
# (the owner: *"pros que sao bem parecidos, faça outra alternativa, a b c testing"*).
# `groupLabel` is written only on the first member.
GROUPS = {
    'abc-rain-body': ('A/B: o mesmo corpo, duas paletas', ['tideline-body', 'north-fog']),
}

# ── the token contract ────────────────────────────────────────────────────────────
# Every theme must declare ALL of these. The list is the canonical block of
# `themes/theme-1.css:43-108` plus its alias block at `:112-125`; a theme that omits
# one inherits `panel.css`'s `:root` value, which is another design's.
REQUIRED = [
    '--bg-slab', '--bg-slab-strong', '--slab-opacity', '--shadow-slab',
    '--text-primary', '--text-confirmed', '--text-provisional', '--text-secondary',
    '--text-muted',
    '--line', '--line-strong', '--accent', '--accent-soft', '--theme-swatch',
    '--ok', '--busy', '--error', '--idle',
    '--radius-sm', '--radius-md', '--radius-lg', '--radius-dialog',
    '--space-1', '--space-2', '--space-3', '--space-4', '--space-5',
    '--font-sans', '--font-mono', '--font-caption', '--font-closed',
    '--size-caption', '--leading-caption', '--weight-caption', '--tracking-caption',
    '--tracking-brand', '--brand-upper', '--caption-upper',
    '--size-time', '--size-closed', '--size-chrome', '--size-meta', '--size-small',
    '--leading-closed', '--weight-closed', '--weight-brand',
    '--motion-in', '--type-step',
    '--bg', '--bg-raised', '--text', '--text-dim', '--text-faint', '--radius',
    '--font', '--mono', '--accent-from', '--accent-to', '--accent-gradient',
]

# COLOURS THE ZIP DOES NOT STATE, and where each one is borrowed from. The state trio
# carries MEANING in this app (`--ok` = the tap is delivering, `--error` = it is not),
# so it belongs to the product and not to a design direction; the five original themes
# all use these same two literals. `--idle` and `--busy` follow the theme's own palette.
OK_MEANING = '#6EF184'
ERROR_MEANING = '#F87171'

# The repo's own shape and spacing scale. The zip styles panes with Tailwind classes
# and declares no radius scale in its 13 vars, so there is nothing to read here.
SHAPE = {
    '--radius-sm': '7px', '--radius-md': '12px', '--radius-lg': '18px',
    '--radius-dialog': '16px',
    '--space-1': '4px', '--space-2': '8px', '--space-3': '13px',
    '--space-4': '20px', '--space-5': '30px',
    '--size-time': '10px', '--size-closed': '18px', '--size-chrome': '11.5px',
    '--size-meta': '10.5px', '--size-small': '12.5px',
    '--leading-closed': '1.24', '--weight-closed': '400', '--weight-brand': '700',
    '--tracking-brand': '0.42em', '--brand-upper': 'uppercase',
    '--caption-upper': 'none',
    '--motion-in': '150ms', '--slab-opacity': '0.97',
}

# The three families the zip's own stacks name first. The zip's `"Avenir Next"` and
# `"Helvetica Neue"` are not on every Windows box and are NOT bundled, so the fallback
# is the repo's system stack; the bundled face is what paints.
FAMILIES = {
    'body': '"Outfit", "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif',
    'display': '"Fraunces", Georgia, "Times New Roman", serif',
    'mono': '"IBM Plex Mono", "Cascadia Mono", Consolas, ui-monospace, monospace',
}

REVEALS = {
    # name: (what animates, keyframes, duration, easing, --type-step)
    'fade': ('word', 'cine-fade', '450ms', 'cubic-bezier(0.22, 1, 0.36, 1)', '0ms'),
    'rise': ('word', 'cine-rise', '500ms', 'cubic-bezier(0.22, 1, 0.36, 1)', '0ms'),
    'blur': ('char', 'cine-blur', '380ms', 'cubic-bezier(0.22, 1, 0.36, 1)', '38ms'),
    'type': ('none', None, None, None, '45ms'),
}


# ── reading the design source ─────────────────────────────────────────────────────

def read_source():
    with io.open(SOURCE, encoding='utf-8') as fh:
        text = fh.read()

    out = []
    # One design per `{ id: "…", name: "…", … vars: { … } … caption: cap("…", "…") }`.
    # The file is machine-written TypeScript with one field per line, so a line-wise
    # scan is exact where one big regex would be fragile.
    blocks = re.split(r'\n  \{\n', text)
    for block in blocks:
        # The file's HEADER also contains the word `vars:` (in the interface), so the
        # guard is the shape of a real entry: a quoted `id` AND an object literal.
        if not re.search(r'\bid:\s*"[^"]+"', block) or 'vars: {' not in block:
            continue
        def field(key, pattern):
            m = re.search(pattern, block)
            if not m:
                raise SystemExit('MISSING %s in a design block:\n%s' % (key, block[:200]))
            return m.group(1)

        d = {
            'id': field('id', r'\bid:\s*"([^"]+)"'),
            'name': field('name', r'\bname:\s*"([^"]+)"'),
            'mood': field('mood', r'\bmood:\s*"([^"]+)"'),
            'swatch': field('swatch', r'\bswatch:\s*"([^"]+)"'),
        }
        m = re.search(r'\bwallpaper:\s*\n?\s*"([^"]+)"', block)
        d['wallpaper'] = m.group(1) if m else None

        vars_block = block[block.index('vars:'):]
        d['vars'] = dict(re.findall(r'"(--[a-z0-9-]+)":\s*"([^"]+)"', vars_block))
        if len(d['vars']) < 13:
            raise SystemExit('%s: read only %d vars' % (d['id'], len(d['vars'])))

        cap = re.search(r'caption:\s*cap\(\s*"([^"]+)"\s*,\s*"([a-z]+)"', block)
        if not cap:
            raise SystemExit('%s: no caption' % d['id'])
        d['caption_class'] = cap.group(1)
        d['reveal'] = cap.group(2)
        if d['reveal'] not in REVEALS:
            raise SystemExit('%s: unknown reveal %r' % (d['id'], d['reveal']))
        out.append(d)

    if len(out) != 10:
        raise SystemExit('expected 10 designs in the source, read %d' % len(out))
    return out


def typography(caption_class, reveal):
    """Read the caption's type out of the source's Tailwind class string."""
    t = {}
    if 'font-display' in caption_class:
        t['family'] = FAMILIES['display']
    elif 'font-mono' in caption_class:
        t['family'] = FAMILIES['mono']
    else:
        t['family'] = FAMILIES['body']
    t['italic'] = 'italic' in caption_class
    weight = {'font-light': 300, 'font-normal': 400, 'font-medium': 500}
    t['weight'] = next((v for k, v in weight.items() if k in caption_class), 400)

    m = re.search(r'text-\[clamp\(([^)]+)\)\]', caption_class)
    if not m:
        raise SystemExit('no clamp in %r' % caption_class)
    parts = [p.strip() for p in m.group(1).split(',')]
    if len(parts) != 3:
        raise SystemExit('clamp with %d parts in %r' % (len(parts), caption_class))
    t['size_floor'], t['size_max'] = parts[0], parts[2]

    m = re.search(r'leading-\[([0-9.]+)\]', caption_class)
    t['leading'] = m.group(1) if m else '1.45'
    m = re.search(r'tracking-\[([-0-9.]+)em\]', caption_class)
    t['tracking'] = (m.group(1) + 'em') if m else '0'
    return t


# ── the tokens a theme declares ───────────────────────────────────────────────────

def raise_alpha(rgba, to):
    """`rgba(r,g,b,a)` at a new alpha. Used for `--line-strong`: the zip declares ONE
    line colour and our panel has two weights of it, so the second is a derivation of
    the stated value and never a new colour."""
    m = re.match(r'rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)', rgba)
    if not m:
        return rgba
    return 'rgba(%s, %s, %s, %s)' % (m.group(1), m.group(2), m.group(3), to)


def tokens_for(d):
    v = d['vars']
    t = typography(d['caption_class'], d['reveal'])
    reveal_kind, _kf, _dur, _ease, step = REVEALS[d['reveal']]

    # THE CAPTION'S COLOURS GO ON THE TOKENS THE PANEL AND THE IN-PANEL EDITOR ACTUALLY
    # READ. `--text-confirmed`/`--text-provisional` are the two the caption's own spans
    # consume, and the newest word takes `--accent` — which is the zip's
    # `--caption-accent` role and is also the one accent the editor already drives, so
    # every colour in this set stays editable from the panel.
    out = {
        '--bg-slab': v['--panel'],
        '--bg-slab-strong': v['--panel-2'],
        '--shadow-slab': v['--shadow'],
        '--text-primary': v['--ink'],
        '--text-confirmed': v['--caption-ink'],
        '--text-provisional': v['--caption-ink'],
        '--text-secondary': v['--dim'],
        '--text-muted': v['--faint'],
        '--line': v['--line'],
        '--line-strong': raise_alpha(v['--line'], '0.34'),
        '--accent': v['--accent'],
        '--accent-soft': v['--hover'],
        '--theme-swatch': d['swatch'],
        '--ok': OK_MEANING,
        '--busy': v['--accent'],
        '--error': ERROR_MEANING,
        '--idle': v['--faint'],
        '--font-sans': t['family'],
        '--font-mono': FAMILIES['mono'],
        '--font-caption': 'var(--font-sans)',
        '--font-closed': 'var(--font-sans)',
        # DECISION 1 (see the header): the clamp's MAX, not its floor.
        '--size-caption': t['size_max'],
        '--leading-caption': t['leading'],
        '--weight-caption': str(t['weight']),
        '--tracking-caption': t['tracking'],
        '--type-step': step,
        # the zip's `--scrim`: the layer between the wallpaper and the type. Named
        # here because it is a colour of its own and nothing in the contract owns it.
        '--cine-scrim': v['--scrim'],
        '--cine-accent-ink': v['--accent-ink'],
    }
    out.update(SHAPE)
    # the aliases `panel.css` reads
    out.update({
        '--bg': 'var(--bg-slab)', '--bg-raised': 'var(--bg-slab-strong)',
        '--text': 'var(--text-primary)', '--text-dim': 'var(--text-secondary)',
        '--text-faint': 'var(--text-muted)', '--radius': 'var(--radius-lg)',
        '--font': 'var(--font-sans)', '--mono': 'var(--font-mono)',
        '--accent-from': 'var(--accent)', '--accent-to': 'var(--accent)',
        '--accent-gradient': 'var(--accent)',
    })
    out['__italic'] = t['italic']
    out['__reveal'] = d['reveal']
    out['__kind'] = reveal_kind
    return out


# ── the shared block: the reveal engine and the caret ─────────────────────────────

SHARED = """/* ═══ THE SET'S ONE SHARED BLOCK — the reveal engine and the caret ═══════════════

   THIS IS THE ONLY BLOCK IN THIS FILE THAT IS NOT SCOPED TO ONE THEME, and it is
   scoped to the SET instead (`[data-theme^='cine-']`), never to the document: the five
   original directions must not inherit a single declaration from here.

   WHY IT IS SHARED AND NOT REPEATED SEVEN TIMES: these are keyframes and one
   pseudo-element. They carry no colour and no size, so there is nothing for a theme to
   have an opinion about, and seven copies of a keyframe is seven places for one of
   them to be edited alone.

   THE CARET IS THE POINT. In five of the six caption treatments of the design zips the
   text that is still forming is styled IDENTICALLY to the text that has settled — the
   caret is the ONLY thing on screen that says "this word is not final yet". It is also
   the only difference our panel can honestly show, because the worker sends us the
   words it has and not the ones it has not.

   THE ENTRY ANIMATIONS ARE ON THE WORD OR ON THE CHARACTER, NEVER ON THE LINE: a line
   whose text is rewritten in place must not slide or fade as a whole, or every partial
   the worker sends would make the whole caption jump. */
@keyframes cine-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}

@keyframes cine-rise {
  from { opacity: 0; transform: translateY(0.55em); }
  to   { opacity: 1; transform: none; }
}

/* The blur reveal is per CHARACTER in the source, and it is the one reveal that moves
   the thing being read — a 3 px blur on an incoming character, gone by the time it
   settles. `filter` is animated rather than `opacity` because the character is
   already painting. */
@keyframes cine-blur {
  from { opacity: 0; filter: blur(3px); }
  60%  { opacity: 1; filter: blur(0.6px); }
  to   { opacity: 1; filter: none; }
}

@keyframes cine-caret {
  0%, 49%   { opacity: 1; }
  50%, 100% { opacity: 0; }
}

:root[data-theme^='cine-'] .caption--provisional .caption__provisional::after {
  content: '';
  display: inline-block;
  width: 2px;
  height: 0.92em;
  margin-left: 0.12em;
  border-radius: 2px;
  background: currentColor;
  transform: translateY(0.06em);
  animation: cine-caret 1.05s steps(1) infinite;
}
"""


# ── one theme's CSS ───────────────────────────────────────────────────────────────

def theme_css(d, toks, backdrop_note):
    i = PREFIX + RENAME.get(d['id'], d['id'])
    S = ":root[data-theme='%s']" % i
    lines = []
    a = lines.append

    a('/* ── %s — %s ─────────────────────────────────────────────────────────' % (d['name'], d['mood']))
    a(' * from `cinematic/src/themes.ts`, id `%s`, reveal `%s`%s' % (d['id'], d['reveal'], backdrop_note))
    if d['id'] in RENAME:
        a(' * SHIPPED AS `%s`: the id `%s` names an UNRELATED design of the' % (i, d['id']))
        a(' * same name in the `cinematic-1` zip. The two are never merged.')
    a(' */')
    a('%s{' % S)
    a('  /* SURFACE — the zip\'s `--panel` is the slab, its `--panel-2` the raised tint. */')
    for k in ('--bg-slab', '--bg-slab-strong', '--slab-opacity', '--shadow-slab'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* TEXT — the caption\'s own two tones are the zip\'s `--caption-ink`; the')
    a('     newest word takes the accent, which is the zip\'s `--caption-accent` role. */')
    for k in ('--text-primary', '--text-confirmed', '--text-provisional',
              '--text-secondary', '--text-muted'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* LINES AND ACCENT — `--line-strong` is the zip\'s ONE line colour at a')
    a('     higher alpha: the panel has two weights of the same line, and a second')
    a('     colour would be a colour the design never states. */')
    for k in ('--line', '--line-strong', '--accent', '--accent-soft', '--theme-swatch'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* STATE — the zip declares none. `--ok`/`--error` MEAN something in this app')
    a('     (the tap is delivering / it is not), so they are the product\'s and are')
    a('     the same two literals the five directions already use; `--busy` and')
    a('     `--idle` follow this palette. */')
    for k in ('--ok', '--busy', '--error', '--idle'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* SHAPE and SPACE — the zip has no radius scale (it styles panes with')
    a('     Tailwind classes), so these are the repo\'s. */')
    for k in ('--radius-sm', '--radius-md', '--radius-lg', '--radius-dialog',
              '--space-1', '--space-2', '--space-3', '--space-4', '--space-5'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* TYPE — read out of the design\'s own caption class string. */')
    for k in ('--font-sans', '--font-mono', '--font-caption', '--font-closed'):
        a('  %s: %s;' % (k, toks[k]))
    a('  --size-caption: %s;   /* the source clamp\'s MAX: %s */'
      % (toks['--size-caption'], d['caption_class'].split('clamp(')[1].split(')')[0]))
    for k in ('--leading-caption', '--weight-caption', '--tracking-caption',
              '--caption-upper', '--tracking-brand', '--brand-upper',
              '--size-time', '--size-closed', '--size-chrome', '--size-meta',
              '--size-small', '--leading-closed', '--weight-closed', '--weight-brand'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* MOTION — `--motion-in` is a COLOUR transition and nothing else; the')
    a('     reveal is the theme\'s own animation, declared below. */')
    a('  --motion-in: %s;' % toks['--motion-in'])
    a('  --type-step: %s;%s' % (
        toks['--type-step'],
        '   /* the char-by-char reveal, unchanged from `panel.css` */' if toks['--type-step'] != '0ms'
        else '  /* 0: this theme reveals by WORD, not by character */'))
    a('  --cine-scrim: %s;' % toks['--cine-scrim'])
    a('  --cine-accent-ink: %s;' % toks['--cine-accent-ink'])
    a('}')
    a('')
    a('/* The aliases `panel.css` reads. Kept as aliases so a reader who knows the old')
    a(' * names finds them, and so the two cannot drift. */')
    a('%s{' % S)
    for k in ('--bg', '--bg-raised', '--text', '--text-dim', '--text-faint',
              '--radius', '--font', '--mono', '--accent-from', '--accent-to',
              '--accent-gradient'):
        a('  %s: %s;' % (k, toks[k]))
    a('  color-scheme: dark;')
    a('}')
    a('')

    # ── the backdrop ─────────────────────────────────────────────────────────────
    a('/* THE BACKDROP: the zip\'s own wallpaper behind the zip\'s own scrim. The scrim')
    a(' * is what the design puts between the photograph and the type, and it is the')
    a(' * reason the caption stays readable over a bright frame. */')
    a('%s .panel {' % S)
    a('  background-color: var(--bg-slab);')
    if toks.get('__photo'):
        a('  background-image: linear-gradient(var(--cine-scrim), var(--cine-scrim)),')
        a('                    url(%s);' % toks['__photo'])
        a('  background-size: cover, cover;')
        a('  background-position: center, center;')
    else:
        a('  /* No photograph could be bundled for this theme, so the backdrop is a')
        a('   * vertical falloff between the palette\'s own two surface tones. It is a')
        a('   * STAND-IN and it is named as one; a flat scrim over a flat colour would')
        a('   * be the same pixels everywhere and would read as a missing asset. */')
        a('  background-image: linear-gradient(180deg,')
        a('    var(--bg-slab-strong) 0%, transparent 42%, var(--cine-scrim) 100%);')
    a('  border-color: var(--line);')
    a('}')
    a('')

    # ── the caption stage ────────────────────────────────────────────────────────
    a('/* THE LIVE CAPTION: the zip\'s `bare` treatment — NO box, no border, no pane,')
    a(' * because the design\'s whole idea is type over the photograph. The stage keeps')
    a(' * ONE thing the zip does not have: our panel holds older lines, so they recede')
    a(' * (DECISION 2 in the header of the generator). */')
    a('%s .captions__bar {' % S)
    a('  justify-content: center;')
    a('  border: 0;')
    a('  background: none;')
    a('}')
    a('%s .captions__hint {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-mono);')
    a('  font-size: 9.5px;')
    a('  letter-spacing: 0.3em;')
    a('  text-transform: uppercase;')
    a('}')
    a('%s .captions__list {' % S)
    a('  background: none;')
    a('  border: 0;')
    a('  box-shadow: none;')
    a('  padding: 0;')
    a('}')
    a('%s .caption {' % S)
    a('  background: none;')
    a('  border: 0;')
    a('  box-shadow: none;')
    a('  padding: 2px 0;')
    a('  text-align: center;')
    a('  justify-content: center;')
    a('}')
    a('%s .caption__time {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-mono);')
    a('  font-size: 9.5px;')
    a('  letter-spacing: 0.18em;')
    a('  opacity: 0.7;')
    a('}')
    a('%s .caption__text {' % S)
    a('  color: var(--text-confirmed);')
    a('  font-family: var(--font-caption);')
    a('  font-size: var(--size-caption);')
    a('  font-weight: var(--weight-caption);%s' % ('\n  font-style: italic;' if toks['__italic'] else ''))
    a('  line-height: var(--leading-caption);')
    a('  letter-spacing: var(--tracking-caption);')
    a('  text-transform: var(--caption-upper);')
    a('  /* the zip\'s own shadow, verbatim: it is what holds the type off a photograph. */')
    a('  text-shadow: 0 2px 26px rgba(0, 0, 0, 0.72), 0 1px 6px rgba(0, 0, 0, 0.6);')
    a('}')
    a('%s .caption--provisional .caption__text {' % S)
    a('  color: var(--text-provisional);')
    a('}')
    a('/* Older lines: the smallest number that recedes without becoming unreadable at')
    a(' * 380 px. The zips never show an older line, so this value is mine. */')
    a('%s .caption:not(.caption--latest) .caption__text {' % S)
    a('  color: var(--text-secondary);')
    a('  font-size: calc(var(--size-caption) * 0.72);')
    a('}')
    a('%s .caption:not(.caption--latest) {' % S)
    a('  opacity: 0.72;')
    a('}')
    a('%s .captions__placeholder {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-caption);')
    a('  font-style: italic;')
    a('  opacity: 0.55;')
    a('}')
    a('%s .status {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-mono);')
    a('  font-size: var(--size-meta);')
    a('  letter-spacing: 0.14em;')
    a('  text-transform: uppercase;')
    a('}')
    a('')

    # ── the reveal ───────────────────────────────────────────────────────────────
    kind, kf, dur, ease, _step = REVEALS[d['reveal']]
    a('/* THE REVEAL — `%s`. One word, or one character, at a time. */' % d['reveal'])
    if kind == 'none':
        a('/* (`type` needs no rule of its own: it IS the character reveal `panel.css`')
        a(' * already declares, driven by the `--type-step` above. The caret is shared. */')
    elif kind == 'word':
        a('%s .caption--provisional .caption__word[data-typing] {' % S)
        a('  color: var(--accent);   /* the newest word, the zip\'s `--caption-accent` role */')
        a('  animation: %s %s %s both;' % (kf, dur, ease))
        a('}')
        a('/* The per-character reveal is switched OFF for this theme: two animations on')
        a(' * one character\'s opacity multiply, and the design moves the WORD here. */')
        a('%s .caption--provisional .caption__word[data-typing] .caption__ch {' % S)
        a('  animation: none;')
        a('}')
    else:  # char
        a('%s .caption--provisional .caption__word[data-typing] {' % S)
        a('  color: var(--accent);')
        a('}')
        a('/* The character reveal, with this theme\'s own keyframe instead of the')
        a(' * opacity pop: the delay is still `--c-i * --type-step`. */')
        a('%s .caption--provisional .caption__word[data-typing] .caption__ch {' % S)
        a('  animation: %s %s %s both;' % (kf, dur, ease))
        a('  animation-delay: calc(var(--c-i) * var(--type-step));')
        a('}')
    a('')
    return '\n'.join(lines)


# ── the manifest ──────────────────────────────────────────────────────────────────

MANIFEST_PARA = """ * THE TEMPLATE SET (added 2026-10-08, owner: *"gostei de alguns designs que botei
 * ai no workspace… eu quero uma mudança mesmo, a cada tema/template"*). Every entry
 * below the five carries its own `file` — `themes/cinematic.css`, one generated
 * document holding the whole set — and may carry `group`/`groupLabel`/`variant`,
 * which is what makes a near-duplicate pair visible AS a pair in the picker instead
 * of two unrelated names. `group` is the A/B/C family, `variant` is the letter, and
 * `groupLabel` is written only on the FIRST member of a group. All three are
 * rendered by `theme-switcher.js` and none of them decides anything about the
 * design. This file is REGENERATED by `_main/_design-lane/gen_cinematic.py`, which
 * reads the five entries above out of it verbatim — so the five are never retyped,
 * and their swatches cannot drift from what `gen_themes.py` writes into their CSS.
"""


def manifest(rows):
    with io.open(JS_OUT, encoding='utf-8') as fh:
        old = fh.read()

    # IDEMPOTENT, AND IT WAS NOT — TWICE. First, the anchor this looked for (` */`
    # followed by the IIFE) still exists AFTER the paragraph is inserted, because the
    # paragraph goes in BEFORE that ` */`, so every run added a whole copy: measured,
    # the header reached 9 499 B of a 12 073 B file, all inside a comment, so
    # `node --check` stayed GREEN and only the byte count was wrong. Then, cutting from
    # the paragraph's TEXT left its opening ` *` line orphaned and the file still grew,
    # by 4 bytes a run. The marker is now the opening line TOGETHER with the ` *` above
    # it, and the insertion puts that ` *` back. A generator that grows its own output
    # is a generator nobody can diff.
    marker = ' *\n * THE TEMPLATE SET (added'
    if marker in old:
        start = old.index(marker)
        old = old[:start] + old[old.index(' */\n(function (root) {', start):]

    head_end = old.index(' */\n(function (root) {')
    head = old[:head_end] + ' *\n' + MANIFEST_PARA + old[head_end:]
    tail = old[old.index('\n  var api = {'):]

    # THE FIVE ORIGINALS ARE READ OUT OF THE FILE BEING REPLACED, so they are never
    # retyped and their swatches cannot drift from what `gen_themes.py` writes into
    # their CSS. IDEMPOTENCE: on a second run the file already holds the set as well,
    # so the capture takes only the entries that are NOT the set — otherwise every run
    # would double the manifest, and the doubling would be silent and cumulative.
    entries = [e for e in re.findall(r'\n    \{\n      name:[\s\S]*?\n    \}', old)
               if ("name: '" + PREFIX) not in e]
    if len(entries) != 5:
        raise SystemExit('captured %d original entries, expected 5' % len(entries))

    out = [head[:head.index('  var THEMES = [')] + '  var THEMES = [']
    # JOINED WITH A COMMA, and the captured originals are joined the same way as the
    # new ones. The capture regex stops at the entry's closing brace, so it does NOT
    # carry that entry's trailing comma — splicing the pieces back without one is a
    # manifest that reads `} {` and a panel whose manifest silently never publishes
    # itself (the stylesheet-free fallback then hides the whole template set).
    parts = [e for e in entries]
    for r in rows:
        parts.append('\n    {\n      name: %s,\n      label: %s,\n      file: %s,\n'
                     '      swatch: %s%s%s%s\n    }' % (
                         js(r['name']), js(r['label']), js(r['file']), js(r['swatch']),
                         ',\n      group: %s' % js(r['group']) if r.get('group') else '',
                         ',\n      groupLabel: %s' % js(r['groupLabel']) if r.get('groupLabel') else '',
                         ',\n      variant: %s' % js(r['variant']) if r.get('variant') else ''))
    out.append(','.join(parts))
    out.append('\n  ];')
    body = ''.join(out)
    body += tail
    return body


def js(s):
    return "'" + str(s).replace('\\', '\\\\').replace("'", "\\'") + "'"


# ── backdrops ─────────────────────────────────────────────────────────────────────

def fetch_backdrop(d, log):
    """Download the wallpaper the design names. NEVER fatal: the panel's CSP forbids
    a remote URL, so a photo we cannot bundle is a photo we do not use, and the theme
    falls back to a gradient of its own palette — which the scrim has already been
    flattening towards anyway.

    CURL, NOT `urllib`: measured on this box, Python's own TLS cannot verify Pexels at
    all — all ten wallpapers returned `CERTIFICATE_VERIFY_FAILED: certificate has
    expired` — while `curl.exe`, which uses the WINDOWS certificate store, returns the
    same URL with exit 0 and a valid JPEG magic (`FF D8 FF E1`, 172 948 B). A
    downloader that fails on every input is not a fallback path, it is a silent
    decision to ship no photographs. `CREATE_NO_WINDOW` because this repo does not put
    consoles on the owner's screen, and curl is run ONCE per theme, not per build."""
    if not d['wallpaper']:
        return None, ' (no wallpaper named: gradient)'
    name = RENAME.get(d['id'], d['id']) + '.jpg'
    path = os.path.join(BACKDROPS, name)
    if os.path.exists(path) and os.path.getsize(path) > 8192:
        PHOTO_SRC[name] = d['wallpaper']
        return 'backdrops/' + name, ' (bundled photo)'
    os.makedirs(BACKDROPS, exist_ok=True)
    try:
        proc = subprocess.run(
            ['curl.exe', '-sSL', '--fail', '--max-time', '25', '-o', path, d['wallpaper']],
            capture_output=True, timeout=60, creationflags=0x08000000)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        if proc.returncode != 0 or size < 8192:
            raise ValueError('curl rc=%d, %d B' % (proc.returncode, size))
        with open(path, 'rb') as fh:
            if fh.read(2) != b'\xff\xd8':
                raise ValueError('not a JPEG')
        log.append('downloaded %s (%d B)' % (name, size))
        PHOTO_SRC[name] = d['wallpaper']
        return 'backdrops/' + name, ' (bundled photo)'
    except Exception as exc:                                    # noqa: BLE001
        log.append('NO PHOTO for %s: %s' % (d['id'], exc))
        return None, ' (no photo could be bundled: gradient of the palette)'


# ── the extras (the other two zips contribute DATA, never CSS) ────────────────────

def load_extras():
    """`cine_extra_c1.py` / `cine_extra_c2.py` may each define `THEMES`, a list of
    dicts with `id`, `label`, `swatch`, `tokens` (already mapped to the contract),
    `italic`, `reveal`, `group`, `variant`, `groupLabel`, `photo`, `css` (a scoped
    structural block with `@S@` standing for the theme's scope). They contribute data;
    the token contract, the file layout and the self-checks stay HERE, in one place."""
    out = []
    for mod_name, src in (('cine_extra_c1', 'cinematic-1'), ('cine_extra_c2', 'cinematic-2')):
        path = os.path.join(HERE, mod_name + '.py')
        if not os.path.exists(path):
            continue
        sys.path.insert(0, HERE)
        mod = __import__(mod_name)
        for t in mod.THEMES:
            t['__source'] = src
            out.append(t)
    return out


# ── main ──────────────────────────────────────────────────────────────────────────

def main():
    designs = {d['id']: d for d in read_source()}
    log = []
    photo_note = {}

    blocks = [SHARED]
    rows = []
    seen = set()

    for did in SHIP:
        d = designs[did]
        toks = tokens_for(d)
        photo, note = fetch_backdrop(d, log)
        toks['__photo'] = photo
        i = PREFIX + RENAME.get(did, did)
        photo_note[i] = note
        blocks.append(theme_css(d, toks, note))
        seen.add(i)
        rows.append({'name': i, 'label': d['name'], 'file': 'themes/cinematic.css',
                     'swatch': d['swatch']})

    # The A/B/C letters, applied from the ONE table above so a pair cannot be
    # labelled on one side only.
    for group, (label, members) in GROUPS.items():
        for n, member in enumerate(members):
            for r in rows:
                if r['name'] == PREFIX + member:
                    r['group'] = group
                    r['variant'] = 'ABC'[n]
                    if n == 0:
                        r['groupLabel'] = label

    for t in load_extras():
        i = PREFIX + t['id']
        if i in seen:
            raise SystemExit('extra theme %s collides with a shipped id' % i)
        seen.add(i)
        S = ":root[data-theme='%s']" % i
        strs = []
        strs.append('/* ── %s — from the `%s` zip ── */' % (t['label'], t['__source']))
        strs.append('%s{' % S)
        missing = [k for k in REQUIRED if k not in t['tokens']]
        if missing:
            raise SystemExit('%s is missing tokens: %s' % (i, ', '.join(missing)))
        for k in REQUIRED:
            strs.append('  %s: %s;' % (k, t['tokens'][k]))
        strs.append('  --cine-scrim: %s;' % t['tokens'].get('--cine-scrim', 'rgba(0,0,0,0.55)'))
        strs.append('}')
        if t.get('photo'):
            strs.append('%s .panel { background-image: linear-gradient(var(--cine-scrim), var(--cine-scrim)), url(%s); background-size: cover, cover; background-position: center, center; }' % (S, t['photo']))
        if t.get('css'):
            strs.append(t['css'].replace('@S@', S))
        blocks.append('\n'.join(strs) + '\n')
        row = {'name': i, 'label': t['label'], 'file': 'themes/cinematic.css',
               'swatch': t['swatch']}
        for k in ('group', 'groupLabel', 'variant'):
            if t.get(k):
                row[k] = t[k]
        rows.append(row)

    css = '\n'.join(blocks)

    # GROUP MEMBERS ADJACENT, and this is a PRODUCT decision, not tidiness. The owner
    # asked for the near-duplicates to be shippable as alternatives he can compare
    # (*"pros que sao bem parecidos, faça outra alternativa, a b c testing"*) and for
    # the two mouse buttons to walk the list — so the two members of a group have to
    # be neighbours, or "compare them" becomes a trip through the picker instead of
    # one click each way. It also stops a group's heading from being printed twice,
    # which is what happened the first time this ran: `quiet-streets` sat between the
    # two members of `abc-rain-body` and the picker drew the heading again after it.
    ordered, done = [], set()
    for r in rows:
        if r['name'] in done:
            continue
        g = r.get('group')
        if g:
            for m in [x for x in rows if x.get('group') == g]:
                ordered.append(m)
                done.add(m['name'])
        else:
            ordered.append(r)
            done.add(r['name'])
    rows = ordered

    # ── SELF-CHECKS. A generated theme set fails by omission, not by crashing. ────
    fails = []
    for r in rows:
        # A theme's tokens live in TWO blocks — the canonical set and the alias block,
        # exactly as `themes/theme-1.css` has it — so the check reads ALL of that
        # theme's blocks. Reading only the first was this check's own first bug, and
        # it reported eleven missing aliases per theme: fail-closed, no file written.
        bodies = re.findall(r":root\[data-theme='%s'\]\{(.*?)\n\}" % re.escape(r['name']),
                            css, re.S)
        if not bodies:
            fails.append('%s: no token block emitted' % r['name'])
            continue
        body = '\n'.join(bodies)
        for k in REQUIRED:
            if ('\n  %s:' % k) not in ('\n' + body):
                fails.append('%s: missing %s' % (r['name'], k))
        m = re.search(r'\n  --accent: (.*?);', '\n' + body)
        if not m or m.group(1).strip().lower() != r['swatch'].lower():
            fails.append('%s: swatch %s != --accent %s'
                         % (r['name'], r['swatch'], m.group(1).strip() if m else 'ABSENT'))
    names = [r['name'] for r in rows]
    for n in names:
        if names.count(n) > 1:
            fails.append('%s appears twice' % n)
        if re.match(r'^theme-[1-5]$', n):
            fails.append('%s collides with an original direction' % n)
    for url in re.findall(r'url\(([^)]*)\)', css):
        if url.startswith(('http:', 'https:')):
            fails.append('remote url in the CSS: %s' % url)
    if not rows:
        fails.append('no themes emitted')

    if fails:
        for f in fails:
            print('FAIL ' + f, file=sys.stderr)
        return 1

    # BUILD BOTH DOCUMENTS BEFORE OPENING EITHER. `with open(path, 'w')` TRUNCATES on
    # entry, so an exception raised while building the text — which is exactly what
    # happened the first time this generator ran — leaves the artifact EMPTY. Both
    # texts are computed first and written only once they exist.
    js_text = manifest(rows)

    # CRLF, MATCHING THE FILES THESE SIT BESIDE. Measured: `themes/themes.js` is 88
    # CRLF / 0 bare LF and `themes/theme-1.css` is 646 / 0. The repo's theme tooling
    # checks line endings, and a generator that writes LF into a CRLF family shows up
    # as a whole-file diff in every later review.
    with io.open(CSS_OUT, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(css)
    with io.open(JS_OUT, 'w', encoding='utf-8', newline='\r\n') as fh:
        fh.write(js_text)

    # THE MANIFEST IS CHECKED BY A JAVASCRIPT ENGINE, NOT BY THIS FILE. The token
    # self-check above passed on a manifest that did not PARSE (`} {` where a comma
    # belongs), and a manifest that does not parse does not throw in the panel: it
    # leaves `SottoThemeManifest` undefined, the switcher falls back to its built-in
    # five, and the entire template set is invisible with no error anywhere. So the
    # last thing this generator does is ask node to read its own output.
    try:
        check = subprocess.run(['node', '--check', JS_OUT], capture_output=True,
                               timeout=60, creationflags=0x08000000)
    except Exception as exc:                                    # noqa: BLE001
        print('FAIL: could not run node --check: %s' % exc, file=sys.stderr)
        return 1
    if check.returncode != 0:
        print('FAIL: the generated manifest does not parse:\n%s'
              % check.stderr.decode('utf-8', 'replace'), file=sys.stderr)
        return 1

    # THE LICENCE NOTE IS GENERATED TOO. The set ships photographs, they are not ours,
    # and a hand-written credit list is one that stops matching the directory the first
    # time a theme is added. The Pexels licence asks for no attribution; this is here
    # because a bundled third-party asset should say where it came from.
    lic = [
        '# Backdrop licences',
        '',
        'The wallpapers of the template set. Each is a photograph NAMED BY THE DESIGN',
        'SOURCE of one of the zips the owner put in the workspace, downloaded once and',
        'bundled locally: the panel runs over `file://` under',
        "`img-src 'self' data:`, so a remote URL would be a backdrop that never loads.",
        '',
        'Licence (Pexels, https://www.pexels.com/license/): free to use, including',
        'commercially, no attribution required. Credited here anyway, one line each,',
        'and GENERATED by `_main/_design-lane/gen_cinematic.py` — do not hand-edit.',
        '',
    ]
    for name in sorted(PHOTO_SRC):
        lic.append('- `%s` — %s' % (name, PHOTO_SRC[name]))
    if not PHOTO_SRC:
        lic.append('- (no photograph was bundled in this run)')
    with io.open(os.path.join(BACKDROPS, 'LICENCES.md'), 'w', encoding='utf-8',
                 newline='\r\n') as fh:
        fh.write('\n'.join(lic) + '\n')

    for r in rows:
        print('%-22s %-16s %s%s' % (r['name'], r['label'], r['swatch'],
                                    photo_note.get(r['name'], '')))
    for line in log:
        print('  ' + line)
    print('emitted %d theme(s) -> %s (%d B)' % (len(rows), CSS_OUT, len(css)))
    print('manifest -> %s' % JS_OUT)
    print('SELF-CHECK: every theme declares all %d tokens, swatch == --accent, '
          'ids unique, no remote url' % len(REQUIRED))
    return 0


if __name__ == '__main__':
    sys.exit(main())
