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

THE THREE DECISIONS THAT ARE MINE AND NOT THE ZIP'S, all recorded here because a
reviewer should be able to challenge them:
  1. `--size-caption` is the source's OWN `clamp(floor, vw, max)`, emitted VERBATIM —
     the shape `themes/theme-1.css:90` already ships
     (`--size-caption: clamp(30px, 4.6vw, 54px)`). An earlier revision of this file
     BAKED THE MAX (its own comment read `DECISION 1 … the clamp's MAX, not its
     floor`) and that OVERSIZED every caption: at our 380 px column the zip's own CSS
     resolves `clamp(20px,2.7vw,31px)` to 20 px, not 31 px — a 55 % oversize on the one
     line the owner actually reads. Emitting the clamp keeps BOTH ends: the floor in the
     380 px panel column, the `vw` term on the 1040 px strip, where the same design
     is 28 px wide.
  2. Lines older than the newest keep `--text-secondary` and recede at `opacity: 0.72`
     (the panel's own decision: it keeps many lines, a zip shows one). WHAT THEY ARE
     SIZED, LEADED AND WEIGHTED BY IS THE ZIP'S OWN, and each of the four tokens
     below is a knob of the owner's dialog, so each theme DECLARES its family's value
     and CONSUMES it with `var()` (D3 of `I:/cc-tmp/design-bugs-audit.md`). Read from
     the design sources, never invented:
       * `cinematic`   the GHOST LINE (`LiveCaption.tsx:114-125`): `text-[13px]`
                       (`md:text-[14.5px]` needs 768 px; our column is 380), Tailwind
                       `leading-snug` = 1.375, `font-light` = 300 (the default
                       `ghostClassName`, `themes.ts:25` — no design overrides it).
       * `cinematic-1` the PREVIOUS LINE (`CaptionStage.tsx:81-98`): the clamp
                       `clamp(13px, 1.14vw, round(size*0.66))` — the `vw` term is
                       dead in a 380 px column, so the 13 px floor is what applies —
                       at `lineHeight: 1.45` and `fontWeight: c.weight`.
       * `cinematic-2` the `stack` PREVIOUS LINE (`LiveCaptions.tsx:371-383`):
                       `calc(size * 0.66)`, inheriting the caption's leading and
                       weight; the other five variants show no previous line at all,
                       so the sibling's relation stands for them.
     `--motion-in` is the COLOUR/SURFACE transition duration, the meaning it has in
     every other family (`themes/theme-1.css:219`), and the zips state their own
     where they have one (`StreamText.tsx:40` 320 ms, `LiveCaptions.tsx:436-437`
     300 ms); the repo's 150 ms stands where they do not. THE GHOST LINE'S 0.7 s ENTRY
     IS NOT `--motion-in`: the dialog's range is 0-400 ms (`theme-tune.js:164`), so a
     700 ms token there would be a control that lies about itself, and the entry is
     already carried by `panel.css`'s own `caption-in` animation.

Run: `py -3 _main/_design-lane/gen_cinematic.py`
"""

from __future__ import annotations

import io
import math
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
# The OTHER two zips contribute data through their own modules, but one fact of
# `cinematic-2` is only in that zip: each design's own PARTICLES. Read from the source,
# never typed here.
C2_SOURCE = os.path.join(HERE, 'zips', 'cinematic-2', 'src', 'themes.ts')

# filename -> the URL it came from, so the licence note cannot drift from the files.
PHOTO_SRC = {}

PREFIX = 'cine-'

# ALL TEN DESIGNS SHIP (owner's rule for this lane, verbatim: *"eu quero que, cada tema
# encontrado dentro dos .zip, fiquem com o design IGUAL, e so muda a posicao dos
# botoes"*). An earlier revision shipped SEVEN and filtered three out on the strength of
# an OLDER line of his (*"os designs, inclua aqueles que nao sao 'agressivos demais'"*)
# plus the plan's finding that `last-reel`'s caption class is `warm-hour`'s at weight
# 500. Both reasons are real; neither is a reason to DROP a design he asked to see. A
# design that is a one-step grade of another is what the A/B/C picker exists for, and the
# two extremes the filter feared are the two most distinctive themes of the ten:
#   motel-glow  the zip's only caption GLOW (`0 0 26px rgba(229,143,164,0.14)` on the
#               slab shadow) and its only rose neon palette
#   paper-moon  the only ALL-CAPS caption at 0.16em tracking, and the only LIGHT panel
#               (`rgba(240,241,238,0.94)`, dark type on it — `color-scheme: light`)
#   last-reel   display italic at weight 500 — the same grade as warm-hour, at a lower
#               max, over the zip's only analog-gold palette
SHIP = [
    'midnight-rain',   # fade
    'warm-hour',       # fade, display italic — the zip's only italic caption
    'velvet-dusk',     # rise — the only rise, the largest per-word travel
    'study-light',     # type + mono — the zip's only monospace caption
    'tideline',        # blur (per character) — IDENTICAL to north-fog, see GROUPS
    'motel-glow',      # fade, display italic 500 — the zip's only caption GLOW
    'paper-moon',      # type, mono, UPPERCASE 0.16em — the zip's only LIGHT panel
    'quiet-streets',   # fade, 0.09em tracking
    'last-reel',       # fade, display italic 500 — warm-hour's grade, lower max
    'north-fog',       # blur — byte-identical to tideline but for the palette
]

# The ids that ship. `tideline` collides with a DIFFERENT design of the same name in
# the `cinematic-1` zip (unrelated palette), so this one — the body-blur one — is the
# one that carries the suffix. The plan fixes both ids; never merge them.
RENAME = {'tideline': 'tideline-body'}

# ── NO LIGHT SLAB SHIPS (owner, 2026-10-14) ─────────────────────────────────────────
# The owner's ruling, verbatim: *"e nao e pra ter tema branco."* Measured first, by
# `_main/theme-lightness-census.py` over the bytes this file writes: of the 45 themes the
# picker offers, SIX declared a light surface (`--bg-slab` at or above 0.5 relative
# luminance) — `cine-paper-moon`, `cine-fieldnotes`, `cine-dustlight`, `cine-linen`, and
# the two `zipc` designs `Paper` and `Gutter`. The other four are fixed in their own
# data files (`cine_extra_c1.py`, `cine_extra_c2.py`, `gen_zipc.py`); `paper-moon` is the
# one whose palette is READ VERBATIM out of `zips/cinematic/src/themes.ts`, so its
# override lives HERE, in one table, rather than in a hand edit of a vendored source.
#
# WHY AN OVERRIDE AND NOT A DELETED DESIGN. The owner kept the count explicit — *"cuidado:
# nao percas os 45 temas que o dono tem"* — so a design is never dropped for being light;
# its SURFACE AND INK ARE INVERTED INSTEAD, keeping the design's own hue, its accent, its
# caption ink, its typography and its photograph. `paper-moon` keeps the silver
# monochrome that names it; what it loses is white.
#
# THE PAPER-MOON INK WAS ALREADY BROKEN, and that is the half of the measurement that
# decided this. The design states dark ink (`--ink: #191b1f`) for a light sheet, and the
# sheet sits UNDER the scene's own scrim (`rgba(5,6,10,0.62)`) over the wallpaper — so
# what actually painted was #212124 (measured) and the panel's own text came out at
# 1.08:1, i.e. INVISIBLE. A light slab with dark ink is not a taste question here, it is
# a defect, and the fix is the same one for both halves.
NO_LIGHT_SLAB = {
    'paper-moon': {
        '--panel': 'rgba(22,24,28,0.96)',
        '--panel-2': 'rgba(170,179,192,0.07)',
        '--ink': '#EDEFF2',
        '--dim': '#9AA2AC',
        '--faint': '#7C838D',
        '--line': 'rgba(237,239,242,0.12)',
        "--accent": '#aab3c0',
        '--hover': 'rgba(221,226,233,0.07)',
    },
}

# The near-duplicate pairs, so the panel can offer them as alternatives to compare
# (the owner: *"pros que sao bem parecidos, faça outra alternativa, a b c testing"*).
# `groupLabel` is written only on the first member, and it may only claim what the CSS
# in this file actually does — a label that advertises a difference the stylesheet does
# not have is the exact defect this lane exists to remove.
#
# THIS PAIR IS PROVEN IDENTICAL, NOT MERELY SIMILAR. `zips/cinematic/src/themes.ts:161-163`
# (tideline) and `:298-300` (north-fog) are CHARACTER-FOR-CHARACTER the same caption
# class — `font-body font-light text-[clamp(20px,2.6vw,30px)] leading-[1.45]` — with the
# same reveal (`blur`). The two designs ARE the same body in two palettes, so shipping
# them alike is CORRECT and the label says so. Every other pair in this set differs
# structurally; the lane's report carries the pairwise set-difference for all of them.
GROUPS = {
    'abc-rain-body': ('A/B: o MESMO corpo — `themes.ts:161-163` e `:298-300` são '
                      'idênticos caractere a caractere (mesma classe de caption, mesmo '
                      'reveal `blur`); só a paleta muda',
                      ['tideline-body', 'north-fog']),
}

# ── the token contract ────────────────────────────────────────────────────────────
# Every theme must declare ALL of these. The list is the canonical block of
# `themes/theme-1.css:43-108` plus its alias block at `:112-125`; a theme that omits
# one inherits `panel.css`'s `:root` value, which is another design's.
#
# SEVEN NAMES OF THAT CANONICAL BLOCK ARE NOT HERE, and each one is gone because it
# has NO READER ANYWHERE — measured, not assumed: `var(--t)` returns 0 matches across
# `app/panel/**` (CSS, JS, HTML, skins, caption-float) and `app/webview/sotto_webview.py`,
# and no module reads it through `getComputedStyle` either. A token nothing reads is
# dead weight, not a design value:
#   `--slab-opacity`  the zip's `--panel` already carries its own alpha, and
#                     `theme-tune.js:41-45` records it as deliberately not a knob.
#   `--busy`          `panel.js` toggles `status--live`/`status--error` only; there
#                     is no busy state class in the panel to paint.
#   `--font-closed`   `cine_extra_c1.py:183` declares the PANEL font, while the zip's
#                     own previous line paints `scene.captionFont`
#                     (`CaptionStage.tsx:85`) — a reader would paint a font the
#                     design never uses, so the name leaves instead of gaining one.
#   `--space-1`, `--space-4`, `--space-5`  panel.css reads `--space-2` and
#                     `--space-3` only (2 consumers each); the rest have none.
#   `--bg`            the other ten aliases all have readers; this one has none.
REQUIRED = [
    '--bg-slab', '--bg-slab-strong', '--shadow-slab',
    '--text-primary', '--text-confirmed', '--text-provisional', '--text-secondary',
    '--text-muted',
    '--line', '--line-strong', '--accent', '--accent-soft', '--theme-swatch',
    '--ok', '--error', '--idle',
    '--radius-sm', '--radius-md', '--radius-lg', '--radius-dialog',
    '--space-2', '--space-3',
    '--font-sans', '--font-mono', '--font-caption',
    '--size-caption', '--leading-caption', '--weight-caption', '--tracking-caption',
    '--tracking-brand', '--brand-upper', '--caption-upper',
    '--size-time', '--size-closed', '--size-chrome', '--size-meta', '--size-small',
    '--leading-closed', '--weight-closed', '--weight-brand',
    '--motion-in', '--type-step',
    '--bg-raised', '--text', '--text-dim', '--text-faint', '--radius',
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
    '--space-2': '8px', '--space-3': '13px',
    '--size-time': '10px', '--size-chrome': '11.5px',
    '--size-meta': '10.5px', '--size-small': '12.5px',
    '--weight-brand': '700',
    '--tracking-brand': '0.42em', '--brand-upper': 'uppercase',
    '--caption-upper': 'none',
    # THE FOUR CLOSED-LINE TOKENS SIT HERE FOR ONE MECHANICAL REASON: the two extra
    # modules read `_G.SHAPE` at IMPORT time and check it against `_G.REQUIRED`, so a
    # name the contract demands but this table omits would fail their import before the
    # generator could set it. THE VALUES ARE THE `cinematic` FAMILY'S OWN (its ghost
    # line: 13 px / leading-snug / font-light), and the other two families override
    # them in `CLOSED` below. See the header's DECISION 2 for every source.
    '--size-closed': '13px', '--leading-closed': '1.375', '--weight-closed': '300',
    '--motion-in': '150ms',
}


# ── THE FOUR CLOSED-LINE TOKENS, PER FAMILY ───────────────────────────────────────
# These are the four knobs of the owner's dialog that were DEAD in all 25 `cine-*`
# themes: declared 25 times each and read by no rule (D3 of the audit: 100
# declarations, 0 `var()`). Each family now declares what ITS OWN zip states for the
# line that is no longer live. `None` means "follow this theme's own caption token",
# which is what the design itself does by inheritance.
CLOSED = {
    # family: (size, leading, weight, motion)
    'cinematic-1': ('max(13px, calc(var(--size-caption) * 0.66))', '1.45', None, '320ms'),
    'cinematic-2': ('max(13px, calc(var(--size-caption) * 0.66))', None, None, '300ms'),
}

# What each family's closed-line values were read from, so the emitted comment names
# its source instead of saying "the zip" and leaving a reviewer to guess.
CLOSED_SOURCE = {
    'cinematic': 'the ghost line of `LiveCaption.tsx:114-125` (13 px / `leading-snug` / `font-light`)',
    'cinematic-1': 'the previous line of `CaptionStage.tsx:81-98` (the 0.66 clamp / `lineHeight: 1.45` / `fontWeight: c.weight`)',
    'cinematic-2': 'the `stack` previous line of `LiveCaptions.tsx:371-383` (`calc(size * 0.66)`, inheriting leading and weight)',
}


def apply_closed(t):
    """Write one EXTRA theme's four closed-line tokens from its family's row in
    `CLOSED`, falling back to the theme's own caption tokens where the zip inherits
    them (the `stack` previous line states no leading and no weight of its own)."""
    size, leading, weight, motion = CLOSED[t['__source']]
    tk = t['tokens']
    tk['--size-closed'] = size
    tk['--leading-closed'] = leading if leading is not None else tk['--leading-caption']
    tk['--weight-closed'] = weight if weight is not None else tk['--weight-caption']
    tk['--motion-in'] = motion

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


# ── WHERE THE CONTROL CLUSTER SITS — the owner's ONE permitted deviation ──────────
#
# The owner's rule, verbatim: *"eu quero que, cada tema encontrado dentro dos .zip,
# fiquem com o design IGUAL, e so muda a posicao dos botoes"*. So a theme may differ
# from its design in exactly ONE place, and this table is that place. Every position
# below is READ OUT OF THE DESIGN'S OWN CHROME; none of them is a taste of mine:
#
#   cinematic   `LiveCaption.tsx:74-79` centres the caption column at `bottom-[5.5vh]`
#               and `:81-99` puts the transport row (`grid h-9 w-9 rounded-full border
#               border-white/15 bg-black/25`) in the MIDDLE of that column, above the
#               type. Position: centred, at the foot of the stage.
#   cinematic-2 `TopChrome.tsx:180-232` (`chrome: 'bar'`) keeps every control at the
#               RIGHT of a 62 px top bar; `:241-290` (`chrome: 'float'`) floats a
#               CENTRED pill at `top-4 left-1/2` with the brand alone at the left.
#   cinematic-1 states NO caption-side cluster at all: its controls live inside the
#               right-hand history panel (`App.tsx:101-115`) and its only floating
#               cluster is the design switcher at `DesignSwitcher.tsx:20`
#               (`anim-chrome pointer-events-auto absolute left-7 top-[240px]
#               w-[272px]`) — a vertical column down the LEFT edge, under the brand
#               (`Chrome.tsx:69` is why the top-left is not taken: the brand owns it).
#
# NOT taken from any design: the cluster's INTERNAL ORDER. `panel.html:589-590` fixes
# it and `panel.css` forbids a theme from reordering it — a theme may MOVE the row,
# never shuffle it. And every panel rule is qualified by `body[data-surface='panel']`
# because the strip hides `.panel__header` outright (`panel.css:1440-1445`): on the
# `100 px strip the cluster is invisible whatever a theme does to it, so the strip's own
# row is what moves there (`justify-content` on `.stripbar`).
CLUSTERS = {
    'column-center': (
        ("the zip's own position — the caption column is centred at the foot of the",
         "stage (`LiveCaption.tsx:74-79`) and the transport row sits in the middle of",
         "it, under the type (`:81-99`). Our newest line is at the HEEL of the list, so",
         "the row goes below it and the list reserves the band it occupies. THE ORDER",
         "IS INVERTED against the zip, which draws its controls ABOVE the caption: a",
         "foot anchor cannot put a row above a list that grows upward, and the",
         "deviation is named here rather than hidden.",
         "ONE POSITION FOR ALL TEN of this zip's designs, because the zip has ONE",
         "chrome — `App.tsx` and `LiveCaption.tsx` are shared by all ten; what differs",
         "between them is the caption, the palette and the backdrop."),
        ("@S@ body[data-surface='panel'] .panel__controls {",
         "  position: absolute;",
         "  left: 50%;",
         "  top: 14px;   /* the slab own 14 px padding: the header row */",
         "  transform: translateX(-50%);",
         "  /* the caption rows are positioned: without this they paint over it */",
         "  z-index: 4;",
         "}",
         "/* The band the row occupies, so the newest line is never painted through. */",
         "@S@ body[data-surface='panel'] .captions__list { padding-bottom: 36px; }",
         "/* The strip has no header at all (`panel.css:1440-1445`), so ITS row is the",
         " * one that moves. */",
         "@S@ body[data-surface='strip'] .stripbar { justify-content: center; }"),
    ),
    'bar-right': (
        ("the zip's own position — `TopChrome.tsx:180-232`: every control at the RIGHT",
         "of a 62 px top bar (`className=\"ml-auto flex items-center gap-2.5\"`), which",
         "is exactly where `panel.css` already puts ours. So this theme does not MOVE",
         "the cluster; it gives the header the BAR the zip draws around it — the",
         "source's own 180° gradient and `backdropFilter: blur(10px)` — which is the",
         "part of that design our header did not have."),
        ("@S@ body[data-surface='panel'] .panel__header {",
         "  background-image: linear-gradient(180deg, color-mix(in srgb, var(--bg-slab) 88%, transparent), transparent);",
         "  backdrop-filter: blur(10px);",
         "  border-bottom: 1px solid var(--line);",
         "}",
         "@S@ body[data-surface='strip'] .stripbar { justify-content: flex-end; }"),
    ),
    'pill-center': (
        ("the zip's own position — `TopChrome.tsx:260-290`: a CENTRED floating pill at",
         "`absolute top-4 left-1/2 -translate-x-1/2`, `rounded-full`, `background:",
         "var(--surface)`, `backdropFilter: blur(var(--blur))`, `border: 1px solid",
         "var(--line)`, holding every control, with the brand alone at the left",
         "(`:241`). The pill is drawn with this theme's own `--bg-slab-strong` (this",
         "generator's name for the zip's `--surface`) and its own `--line`."),
        ("@S@ body[data-surface='panel'] .panel__controls {",
         "  position: absolute;",
         "  left: 50%;",
         "  top: 14px;   /* the slab's own 14 px padding: the header's row */",
         "  transform: translateX(-50%);",
         "  z-index: 4;",
         "  padding: 0 8px;",
         "  border: 1px solid var(--line);",
         "  border-radius: 999px;",
         "  background: var(--bg-slab-strong);",
         "  backdrop-filter: blur(10px);",
         "}",
         "@S@ body[data-surface='strip'] .stripbar { justify-content: center; }"),
    ),
    'rail-left': (
        ("the zip's own position — this zip has NO top bar: `Chrome.tsx:69` puts the",
         "brand alone at `absolute left-7 top-6`, and its only floating control cluster",
         "is the design switcher at `DesignSwitcher.tsx:20` (`anim-chrome",
         "pointer-events-auto absolute left-7 top-[240px] w-[272px]`): a vertical column",
         "down the LEFT edge. The cluster leaves the header and becomes that column, at",
         "our 28 px control size.",
         "DEVIATION, named: the source anchors the column 240 px below the top, i.e.",
         "just under its own brand — and the brand here lives in the header the cluster",
         "is leaving, so the column is centred vertically instead of typed at 240 px.",
         "NOTHING IS RESERVED FOR IT: the zip's own switcher is a 272 px box painted",
         "OVER the stage, and this column is 28 px wide."),
        ("@S@ body[data-surface='panel'] .panel__controls {",
         "  position: absolute;",
         "  left: 50%;",
         "  top: 14px;   /* the slab own 14 px padding: the same row as every other theme */",
         "  transform: translateX(-50%);",
         "  z-index: 4;",
         "}",
         "@S@ body[data-surface='strip'] .stripbar { justify-content: flex-start; }"),
    ),
}


def cluster_rules(S, kind):
    """One `CLUSTERS` entry as CSS, scoped to a theme. The `@S@` placeholder is the
    theme's scope, the same convention `cine_extra_c1.py`/`cine_extra_c2.py` use for
    their own blocks, so this ONE table serves a design read by `theme_css()` and a
    design contributed by an extra module."""
    lead, rules = CLUSTERS[kind]
    out = ['/* THE CONTROL CLUSTER — %s' % lead[0]]
    for line in lead[1:]:
        out.append(' * ' + line)
    out.append(' */')
    out.extend(r.replace('@S@', S) for r in rules)
    return out


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
    # THE CLAMP IS KEPT WHOLE AND VERBATIM, spaces and all: it is what the design
    # states and it is what the panel emits (`--size-caption`, DECISION 1 in the
    # header). Splitting it is only for the comment that records both of its ends.
    t['size_clamp'] = 'clamp(%s)' % m.group(1)
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


def panel_is_light(color):
    """True when the design's OWN `--panel` is a light surface, i.e. the design draws
    dark type on it. Exactly one of this zip's ten is: `paper-moon`,
    `rgba(240,241,238,0.94)`. The test is the sRGB relative luminance of the stated
    colour against 0.5, the midpoint of the scale — a threshold, not a colour, and it is
    what decides `color-scheme` in the emitted block (a light slab under a
    `color-scheme: dark` declaration paints dark scrollbars and dark form controls ON
    it)."""
    m = re.match(r'rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)', color)
    if not m:
        return False
    r, g, b = (float(m.group(i)) / 255.0 for i in (1, 2, 3))
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 0.5


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
        '--error': ERROR_MEANING,
        '--idle': v['--faint'],
        '--font-sans': t['family'],
        '--font-mono': FAMILIES['mono'],
        '--font-caption': 'var(--font-sans)',
        # DECISION 1 (see the header): the design's own clamp, emitted VERBATIM.
        '--size-caption': t['size_clamp'],
        '--leading-caption': t['leading'],
        '--weight-caption': str(t['weight']),
        '--tracking-caption': t['tracking'],
        '--type-step': step,
        # the zip's `--scrim`: the layer between the wallpaper and the type. Named
        # here because it is a colour of its own and nothing in the contract owns it.
        '--cine-scrim': v['--scrim'],
    }
    out.update(SHAPE)
    # `SHAPE` carries the repo's `--caption-upper: none`, and it is the one SHAPE value
    # a design can contradict: `paper-moon`'s caption class states `uppercase`, and the
    # design wins. Without this the theme paints lower-case type in a class that says
    # ALL CAPS at 0.16em — the single most distinctive thing that design does.
    if 'uppercase' in d['caption_class']:
        out['--caption-upper'] = 'uppercase'
    # the aliases `panel.css` reads
    out.update({
        '--bg-raised': 'var(--bg-slab-strong)',
        '--text': 'var(--text-primary)', '--text-dim': 'var(--text-secondary)',
        '--text-faint': 'var(--text-muted)', '--radius': 'var(--radius-lg)',
        '--font': 'var(--font-sans)', '--mono': 'var(--font-mono)',
        '--accent-from': 'var(--accent)', '--accent-to': 'var(--accent)',
        '--accent-gradient': 'var(--accent)',
    })
    out['__italic'] = t['italic']
    out['__reveal'] = d['reveal']
    out['__kind'] = reveal_kind
    # THE DESIGN'S OWN TYPE VALUES, kept beside the tokens that carry them. They are
    # what `.caption__text` emits as the FALLBACK of each `var()` the in-panel editor
    # writes (see `theme_css`), so the painted value is the design's whether or not a
    # dial ever wrote the token — and so the rule is not byte-identical across themes.
    out['__family'] = t['family']
    out['__weight'] = str(t['weight'])
    out['__leading'] = t['leading']
    out['__tracking'] = t['tracking']
    out['__size_clamp'] = t['size_clamp']
    out['__size_floor'] = t['size_floor']
    out['__size_max'] = t['size_max']
    out['__light'] = panel_is_light(v['--panel'])
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
   the worker sends would make the whole caption jump.

   WHY THE MOTION TOKEN IS HERE TOO: `--motion-in` is DECLARED by every one of the
   twenty-five themes and READ by the one rule at the end of this block. A copy of
   that rule per theme would be twenty-five places for one of them to be edited
   alone, and the value still comes from each theme's own token block — a custom
   property resolves per element, so the dial is live in every theme either way. */
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

/* ── THE MOTION TOKEN ─────────────────────────────────────────────────────────────
   `--motion-in` is a COLOUR/SURFACE transition duration in every other family of this
   repo (`themes/theme-1.css:219` runs `background-color var(--motion-in),
   border-color var(--motion-in)`), and it is one of the four knobs of the owner's
   dialog that were DEAD in all twenty-five of these themes (D3 of the audit: 25
   declarations, 0 readers). The VALUE is declared per theme: `cinematic-1`'s 320 ms is
   `StreamText.tsx:40` (`transition: opacity 320ms ease`), `cinematic-2`'s 300 ms is
   `LiveCaptions.tsx:436-437` (`color .3s ease, filter .3s ease`), and the
   `cinematic` set keeps the repo's 150 ms because that zip states no colour
   transition on its caption. The property list is `theme-1.css`'s, verbatim. */
:root[data-theme^='cine-'] .caption,
:root[data-theme^='cine-'] .caption__text,
:root[data-theme^='cine-'] .caption__confirmed,
:root[data-theme^='cine-'] .caption__provisional {
  transition-property: color, background-color, border-color;
  transition-duration: var(--motion-in);
  transition-timing-function: ease;
}

/* THE `prefers-reduced-motion` OVERRIDE IS THE FILE'S LAST BLOCK (`SHARED_TAIL`),
   not this one: the per-theme rules that read `--motion-in` are emitted AFTER this
   block, and an override at equal specificity must come LAST to win. */
"""


SHARED_TAIL = """/* ═══ THE SET'S REDUCED-MOTION OVERRIDE — THE FILE'S LAST BLOCK ══════════════════

   THE SAME PROMISE `themes/theme-1.css:593-602` MAKES, for every node this file
   gives a transition to: a reader who asked for less motion gets no transition and
   still gets every colour change. IT IS LAST ON PURPOSE — the per-theme rules that
   read `--motion-in` (the caption ones in `SHARED`, the chrome ones each theme
   emits) tie on specificity with this one, so the later block is the one that wins.

   IT COVERS THE CHROME TOO: `--motion-in` drives `.panel__header`, `.status` and
   `.chrome` in every theme (`theme-1.css:576-585`), and a colour transition that
   survives `prefers-reduced-motion` in one half of the set and not the other is a
   promise kept by accident. */
@media (prefers-reduced-motion: reduce) {
  :root[data-theme^='cine-'] .caption,
  :root[data-theme^='cine-'] .caption__text,
  :root[data-theme^='cine-'] .caption__confirmed,
  :root[data-theme^='cine-'] .caption__provisional,
  :root[data-theme^='cine-'] .panel__header,
  :root[data-theme^='cine-'] .panel__header *,
  :root[data-theme^='cine-'] .status,
  :root[data-theme^='cine-'] .status *,
  :root[data-theme^='cine-'] .chrome,
  :root[data-theme^='cine-'] .chrome * {
    transition-duration: 0ms;
  }
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
    for k in ('--bg-slab', '--bg-slab-strong', '--shadow-slab'):
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
    a('     the same two literals the five directions already use; `--idle` follows')
    a('     this palette. (`--busy` used to sit here and left the contract: no rule in')
    a('     `app/panel/**` or the shell reads it — `panel.js` toggles only')
    a('     `status--live`/`status--error`.) */')
    for k in ('--ok', '--error', '--idle'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* SHAPE and SPACE — the zip has no radius scale (it styles panes with')
    a('     Tailwind classes), so these are the repo\'s. */')
    for k in ('--radius-sm', '--radius-md', '--radius-lg', '--radius-dialog',
              '--space-2', '--space-3'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* TYPE — read out of the design\'s own caption class string. */')
    for k in ('--font-sans', '--font-mono', '--font-caption'):
        a('  %s: %s;' % (k, toks[k]))
    a('  --size-caption: %s;   /* THE DESIGN\'S OWN CLAMP, VERBATIM (floor %s, max %s) */'
      % (toks['--size-caption'], toks['__size_floor'], toks['__size_max']))
    for k in ('--leading-caption', '--weight-caption', '--tracking-caption',
              '--caption-upper', '--tracking-brand', '--brand-upper',
              '--size-time', '--size-closed', '--size-chrome', '--size-meta',
              '--size-small', '--leading-closed', '--weight-closed', '--weight-brand'):
        a('  %s: %s;' % (k, toks[k]))
    a('  /* MOTION — `--motion-in` is the COLOUR/SURFACE transition duration, the')
    a('     meaning it has in every other family (`themes/theme-1.css:219`); the')
    a('     shared set block at the top of this file reads it. The reveal is the')
    a('     theme\'s own animation, declared below. */')
    a('  --motion-in: %s;' % toks['--motion-in'])
    a('  --type-step: %s;%s' % (
        toks['--type-step'],
        '   /* the char-by-char reveal, unchanged from `panel.css` */' if toks['--type-step'] != '0ms'
        else '  /* 0: this theme reveals by WORD, not by character */'))
    a('  --cine-scrim: %s;' % toks['--cine-scrim'])
    a('}')
    a('')
    a('/* The aliases `panel.css` reads. Kept as aliases so a reader who knows the old')
    a(' * names finds them, and so the two cannot drift. */')
    a('%s{' % S)
    for k in ('--bg-raised', '--text', '--text-dim', '--text-faint',
              '--radius', '--font', '--mono', '--accent-from', '--accent-to',
              '--accent-gradient'):
        a('  %s: %s;' % (k, toks[k]))
    # `color-scheme` FOLLOWS THE DESIGN'S OWN SLAB. One of the ten states a LIGHT panel
    # (`paper-moon`, `rgba(240,241,238,0.94)`) and a light slab under `dark` paints
    # dark scrollbars and dark form controls on it. See `panel_is_light`.
    a('  color-scheme: %s;' % ('light' if toks['__light'] else 'dark'))
    a('}')
    a('')

    # ── the backdrop ─────────────────────────────────────────────────────────────
    # THE ZIP'S OWN THREE READING SCRIMS, not a flat one. Copied VERBATIM out of
    # `zips/cinematic/src/index.css:90-98` — scrim-top, scrim-bottom (the layer that
    # carries THIS design's own `--cine-scrim`, as the zip carries each theme's
    # `--scrim`) and the vignette — in the zip's own order and with the zip's own
    # stops, with the photograph LAST as the base, exactly as `Backdrop.tsx:35-37`
    # stacks them over the wallpaper.
    # WHY NOT A FLAT SCRIM, and the cost of having shipped one: a single
    # `linear-gradient(var(--cine-scrim), var(--cine-scrim))` over the whole panel
    # washes the photograph out EVERYWHERE — the frame neither reads as a scene nor
    # recedes behind the caption, which is what the owner meant by *"duas coisas
    # sobrepostas ... como se fosse um glitch"* (E4) and *"por que tem personagens
    # falando em um dos designs replicados?"* (E3). These three layers leave the
    # MIDDLE of the frame showing and darken the bottom third, where the caption
    # reads — measured, per theme, by `_main/photo-scrim-census.py`, which now
    # composites the CAPTION ZONE instead of reading a flat alpha.
    a('/* THE BACKDROP: the zip\'s own wallpaper under the zip\'s own THREE reading')
    a(' * scrims, copied VERBATIM out of `index.css:90-98` — scrim-top, scrim-bottom')
    a(' * (the one carrying this design\'s own `--cine-scrim`) and the vignette — in')
    a(' * the zip\'s own order and stops, photograph LAST, as `Backdrop.tsx:35-37`')
    a(' * stacks them. The middle of the frame stays SHOWING and the caption zone is')
    a(' * the dark one; a flat scrim washed the photograph out everywhere. */')
    a('%s .panel {' % S)
    a('  background-color: var(--bg-slab);')
    if toks.get('__photo'):
        a('  background-image:')
        a('    linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)),')
        a('    linear-gradient(to top, var(--cine-scrim), rgba(0,0,0,0)),')
        a('    radial-gradient(125% 95% at 50% 42%, transparent 52%, rgba(0,0,0,0.44) 100%),')
        a('    url(%s);' % toks['__photo'])
        a('  background-size: cover, cover, cover, cover;')
        a('  background-position: center, center, center, center;')
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
    # THE DESIGN'S OWN TYPE, AS THE FALLBACK OF THE TOKEN THE EDITOR WRITES.
    # `theme-tune.js` writes `--font-caption` / `--size-caption` / `--leading-caption` /
    # `--weight-caption` / `--tracking-caption` as INLINE custom properties on <html>
    # (`setProperty`), so a LITERAL here would be beaten by the dial the moment the owner
    # turns it, and a `var()` with no fallback would paint the panel's 15 px base if a
    # dial ever CLEARED the token — `apply()` removes every token it can write before it
    # writes. With the design's own value as the fallback the painted type is the
    # design's either way, the editor still wins, and the rule is NOT byte-identical
    # across these ten themes — which is the whole difference between ten designs and
    # one skin over ten palettes.
    a('  font-family: var(--font-caption, %s);' % toks['__family'])
    a('  font-size: var(--size-caption, %s);' % toks['__size_clamp'])
    a('  font-weight: var(--weight-caption, %s);%s'
      % (toks['__weight'], '\n  font-style: italic;' if toks['__italic'] else ''))
    a('  line-height: var(--leading-caption, %s);' % toks['__leading'])
    a('  letter-spacing: var(--tracking-caption, %s);' % toks['__tracking'])
    a('  text-transform: var(--caption-upper);')
    a('  /* the zip\'s own shadow, verbatim: it is what holds the type off a photograph. */')
    a('  text-shadow: 0 2px 26px rgba(0, 0, 0, 0.72), 0 1px 6px rgba(0, 0, 0, 0.6);')
    a('}')
    a('%s .caption--provisional .caption__text {' % S)
    a('  color: var(--text-provisional);')
    a('}')
    a('/* THE CLOSED LINE — the four tokens of the owner\'s dialog that were DEAD in')
    a(' * every one of these themes now carry the values the ZIP states for the line')
    a(' * that is no longer live: the ghost line of `LiveCaption.tsx:114-125` — 13 px')
    a(' * at Tailwind `leading-snug` (1.375) and `font-light` (300) — with')
    a(' * `--motion-in` the colour transition the shared set block runs. The values in')
    a(' * the `var()` fallbacks are the design\'s own, so a cleared dial still paints')
    a(' * the design. The opacity below is the panel\'s own recede (DECISION 2). */')
    a('%s .caption:not(.caption--latest) .caption__text {' % S)
    a('  color: var(--text-secondary);')
    a('  font-size: var(--size-closed, calc(var(--size-caption) * 0.72));')
    a('  line-height: var(--leading-closed, 1.375);')
    a('  font-weight: var(--weight-closed, 300);')
    a('}')
    a('%s .caption:not(.caption--latest) {' % S)
    a('  opacity: 0.72;')
    a('}')
    # D4 OF THE AUDIT (2026-10-12), CLOSED HERE: THE PLACEHOLDER'S ITALIC IS NOT
    # THE ZIP'S. The line below used to be emitted for ALL 25 themes, while the
    # caption's own italic three lines up is read OUT OF THE ZIP (`__italic` comes
    # from the design's caption class, `themes.ts`). Measured over the shipped bytes
    # (`DC356228...`): 30 rules carried `font-style: italic`, and the 10 whose family
    # has NO italic face in the bundle -- Outfit x5, Inter x3, Manrope x1, Jost x1 --
    # were ALL `.captions__placeholder`, i.e. OUR empty state, an element no zip
    # draws. The browser therefore SYNTHESISED an oblique for exactly those 10.
    # The placeholder is not a design element, so it does not get to invent an axis
    # the design never states: it now echoes the design's OWN answer. Where the zip
    # italicises its caption (warm-hour, motel-glow, last-reel, dustlight, rooftop)
    # the placeholder stays italic and the family is Fraunces/Lora, both bundled
    # with real italics; everywhere else the placeholder is upright.
    # The @fontsource packages of Outfit and Manrope carry NO italic file at all
    # (measured: `files/*italic*` = 0 of 84 for Manrope, 0 of 96 for Outfit), so
    # packaging one is impossible -- that is a real limit of the bundle, and this
    # generator no longer asks for a face that cannot exist.
    a('%s .captions__placeholder {' % S)
    a('  color: var(--text-muted);')
    a('  font-family: var(--font-caption);')
    if toks['__italic']:
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
    # ── THE MOTION TOKEN, READ INSIDE THIS THEME'S OWN SCOPE ─────────────────────
    # D3 of the audit measured `--motion-in` declared 25 times and read by NO rule of
    # this file (the audit's own count: 25 declarations, 0 `var()`). The shared block at
    # the top now reads it for the CAPTION — the four selectors `theme-1.css:586-592`
    # uses — and this rule is the other half of `theme-1.css:576-585`: the chrome is
    # what changes colour when a status flips, and the property list is that file's,
    # verbatim. The DURATION is this theme's own token, so the knob of the tuning
    # dialog is read INSIDE each of the twenty-five scopes instead of once for the set.
    # No other rule of this theme sets `transition` on these nodes, so nothing later
    # in the file can out-rank it.
    a('%s .panel__header,' % S)
    a('%s .panel__header *,' % S)
    a('%s .status,' % S)
    a('%s .status *,' % S)
    a('%s .chrome,' % S)
    a('%s .chrome * {' % S)
    a('  transition-property: color, background-color, border-color, box-shadow;')
    a('  transition-duration: var(--motion-in);')
    a('  transition-timing-function: ease;')
    a('}')
    a('')

    # ── the control cluster (the owner's ONE permitted deviation) ────────────────
    # Same position for all ten designs of this zip, because the zip has ONE chrome
    # (`App.tsx`, `LiveCaption.tsx`) shared by all ten; what differs between them is the
    # caption, the palette and the backdrop. See `CLUSTERS`.
    for line in cluster_rules(S, 'column-center'):
        a(line)
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
#
# `cine_extra_c1.py` / `cine_extra_c2.py` carry each extra theme's TOKENS and its own
# structural CSS. TWO things they do not carry — because they are properties of the
# zip's CHROME and of one design's own particles, not of the theme's palette — are
# emitted HERE, so they are scoped, re-generatable and checked like every other block in
# this file: the position of the control cluster (`CLUSTERS`) and, for `rainline`, the
# zip's own rain.

# c2's own `groupLabel` (`cine_extra_c2.py:517-518`) advertises `sheet` and `rail` as
# the difference between the pair, and its shipped CSS does not branch on either — that
# module uses `panel`/`panel_width`/`chrome` in its HEADER COMMENT ONLY
# (`cine_extra_c2.py:287-288`). What the two themes DO differ by, after the generator's
# own rules below, is the chrome and the particles, and that is what the label says. The
# correction lives here so no other lane's data file is edited.
LABEL_OVERRIDE = {
    'rainline': 'A/B: mesmo `bare` ao centro — Manrope 300/1.42 vs Inter 300/1.46; '
                'barra no topo à direita vs pílula centrada; 46 riscos de chuva vs '
                'nenhuma partícula',
}

# ── THE LABELS THE PICKER SHOWS, CORRECTED (D7/D8 of the audit) ─────────────────
# Neither of these changes a single painted pixel: `themes.js` is the manifest the
# picker renders, the swatch already agrees with the frozen skins 20/20, and only
# the two names below disagreed with what the owner actually sees when the design
# is mounted.
LABEL_FIX = {
    # TWO DESIGNS IN TWO DIFFERENT ZIPS ARE BOTH NAMED `Tideline` in their own
    # source (`zips/cinematic/src/themes.ts:139-140`, and the `cinematic-1` zip's
    # `tideline`). The zip B one is `cine-tideline-body` — the id carries the
    # suffix only to keep the two apart — so IT keeps the plain label, and the
    # `cinematic-1` design (variant `wide`, grouped with `Midnight Café`) gets the
    # distinguishing one.
    'cine-tideline': 'Tideline (wide)',
    # THE SKIN IS WHAT MOUNTS (audit §1.3): the frozen skins call these two
    # `Cellar` and `Linen`, the picker called them `Cellar Sessions`/`Linen
    # Hours`, and the swatches already agree 20/20. The label follows the skin.
    'cine-cellar': 'Cellar',
    'cine-linen': 'Linen',
}


def _rnd(seed):
    """The source's OWN pseudo-random, character for character —
    `cinematic-2/src/components/Stage.tsx:9-13`:
    `Math.sin(seed * 12.9898) * 43758.5453`, fractional part. Every particle position
    and duration in that zip comes out of it, so the layer below is the SAME rain the
    design draws, not a lookalike."""
    x = math.sin(seed * 12.9898) * 43758.5453
    return x - math.floor(x)


def c2_facts(design_id):
    """`(particle, particleColor)` for one design of the `cinematic-2` zip, read out of
    ITS OWN `src/themes.ts` — the design's `particle:` and `particleColor:` fields.
    `(None, None)` when the file or the design is not there: a missing PARTICLE is not a
    build failure (a missing PALETTE is, see `read_source`)."""
    if not os.path.exists(C2_SOURCE):
        return None, None
    with io.open(C2_SOURCE, encoding='utf-8') as fh:
        src = fh.read()
    m = re.search(r"id:\s*['\"]%s['\"]" % re.escape(design_id), src)
    if not m:
        return None, None
    nxt = re.search(r"\n\s*id:\s*['\"]", src[m.end():])
    block = src[m.end():m.end() + (nxt.start() if nxt else len(src))]
    p = re.search(r"particle:\s*['\"]([^'\"]+)['\"]", block)
    c = re.search(r"particleColor:\s*['\"]([^'\"]+)['\"]", block)
    return (p.group(1) if p else None), (c.group(1) if c else None)


def rain_rules(S, color, count):
    """THE ZIP'S OWN RAIN, as CSS: `count` streaks, one background layer each, so the
    whole field is ONE pseudo-element and ONE timeline.

    CARRIED VERBATIM OUT OF THE SOURCE: the count (`Stage.tsx:27-29` — 46 for `rain`),
    every streak's geometry (`Stage.tsx:30-46`: height `8 + r3*18`, left `r1*108 - 4`,
    width `1.6px` when `r3 > 0.8` else `1px`, opacity `0.18 + r2*0.4`) and both ends of
    `rainFall` (`src/index.css:72-76`). The colour is the design's own `particleColor`
    (`themes.ts:99`), which is what `Stage.tsx:46` paints the streak with — the static
    `color-mix(in srgb, #fff 60%, transparent)` at `index.css:81` is only the fallback
    the inline style overrides.

    NOT CARRIED, and this is the price of one pseudo-element: each streak's own
    `animationDuration` (`0.9 + r3*1.3` s) and `animationDelay` (`-r2*3` s). One element
    has one timeline, so all 46 share 1.55 s (the source's mean) and start together; the
    source's own `-4%` horizontal drift is dropped with them, because it is 4 % of a
    1 px-wide element — 0.04 px. Each streak's opacity IS carried, folded into its
    gradient's alpha (a background layer has no opacity of its own)."""
    m = re.match(r'rgba?\(\s*([0-9.]+)\s*,\s*([0-9.]+)\s*,\s*([0-9.]+)'
                 r'\s*(?:,\s*([0-9.]+)\s*)?\)', color or '')
    if not m:
        return []
    rgb = ', '.join(m.group(i) for i in (1, 2, 3))
    base = float(m.group(4)) if m.group(4) else 1.0
    layers, sizes, places = [], [], []
    for i in range(count):
        r1, r2, r3 = _rnd(i + 1), _rnd(i * 7.3 + 2), _rnd(i * 3.7 + 5)
        layers.append('linear-gradient(to bottom, transparent, rgba(%s, %s))'
                      % (rgb, round(base * (0.18 + r2 * 0.4), 3)))
        sizes.append('%.2fpx %.1f%%' % (1.6 if r3 > 0.8 else 1.0, 8 + r3 * 18))
        places.append('%.2f%% 0' % (r1 * 108 - 4))
    return [
        "/* THE PARTICLES — the design's own rain, %d streaks, and the one ambient layer"
        ' * the `cinematic-2` module says this panel has no element for'
        ' (`cine_extra_c2.py:316-317`);' % count,
        ' * it is carried here because it is what the design\'s own A/B label names as the',
        ' * difference between `rainline` and `blue-hour`. `isolation: isolate` makes the slab',
        ' * the stacking context, so a `z-index: -1` layer cannot escape behind its own',
        ' * wallpaper, and it paints after the background and before the type — the order',
        ' * `Stage.tsx:69` gives the rain layer (`absolute inset-0 overflow-hidden`) inside the',
        ' * stage. */',
        '%s .panel { isolation: isolate; }' % S,
        '%s .panel::after {' % S,
        "  content: '';",
        '  position: absolute;',
        '  inset: 0;',
        '  z-index: -1;',
        '  pointer-events: none;',
        '  background-repeat: no-repeat;',
        '  background-image: %s;' % ', '.join(layers),
        '  background-size: %s;' % ', '.join(sizes),
        '  background-position: %s;' % ', '.join(places),
        '  animation: cine-rainfall 1.55s linear infinite;',
        '}',
        '/* `rainFall` (src/index.css:72-76), retargeted at the layer field: one element',
        ' * cannot carry 46 timelines, and `background-position-y` is the one property that',
        ' * moves every layer at once. The two ends and the 10 % step are the source\'s. */',
        '@keyframes cine-rainfall {',
        '  from { background-position-y: -20%; opacity: 0; }',
        '  10% { opacity: .5; }',
        '  to { background-position-y: 110%; opacity: 0; }',
        '}',
    ]


def extra_rules(t):
    """The structural rules the GENERATOR adds on top of an extra theme's own block:
    where its cluster sits, read out of its design's own chrome, plus its particles.
    Emitted AFTER the extra's own CSS so that, on a tie, the generator's rule wins."""
    S = ":root[data-theme='%s']" % (PREFIX + t['id'])
    raw = t.get('__raw') or {}
    out = []
    if t['__source'] == 'cinematic-1':
        # `DesignSwitcher.tsx:20` is that zip's only floating cluster — a vertical column
        # at the LEFT edge (`absolute left-7 top-[240px] w-[272px]`) — and `Chrome.tsx:69`
        # is why it is not the top-left: the brand owns that corner.
        out.extend(cluster_rules(S, 'rail-left'))
    elif t['__source'] == 'cinematic-2':
        chrome = raw.get('chrome')
        if chrome == 'bar':
            out.extend(cluster_rules(S, 'bar-right'))
        elif chrome == 'float':
            out.extend(cluster_rules(S, 'pill-center'))
        particle, color = c2_facts(t['id'])
        if particle == 'rain':
            out.extend(rain_rules(S, color, 46))

    # ── THE MOTION TOKEN, READ INSIDE THIS THEME'S OWN SCOPE ─────────────────────
    # `--motion-in` was declared by every extra theme and read by no rule of theirs
    # (D3). The shared block reads it for the CAPTION; this is the chrome half, the
    # property list of `theme-1.css:576-585`, at the duration this theme declares.
    out.extend([
        '%s .panel__header,' % S,
        '%s .panel__header *,' % S,
        '%s .status,' % S,
        '%s .status *,' % S,
        '%s .chrome,' % S,
        '%s .chrome * {' % S,
        '  transition-property: color, background-color, border-color, box-shadow;',
        '  transition-duration: var(--motion-in);',
        '  transition-timing-function: ease;',
        '}',
    ])

    # ── THE CLOSED LINE, and the three tokens that were dead in these themes too ──
    # The extra module already styles the closed line with its own literal
    # (`_PREV_SIZE`); THIS rule is what makes its size, leading and weight
    # come from the owner's dialog. It is emitted after that module's block ON
    # PURPOSE: the selectors tie on specificity and the later rule wins, so the
    # token supersedes the literal without this generator editing another lane's
    # data file. The `var()` fallbacks are the extra module's own values, so a
    # cleared dial still paints the design.
    out.extend([
        '/* THE CLOSED LINE — the tuning tokens of the owner\'s dialog, which were DEAD',
        ' * in all 25 `cine-*` themes. The values are this family\'s own zip:',
        ' * %s.' % CLOSED_SOURCE[t['__source']],
        ' * The rule below supersedes this theme\'s own literal `font-size` (same',
        ' * specificity, emitted later). */',
        '%s .caption:not(.caption--provisional) .caption__text {' % S,
        '  font-size: var(--size-closed, %s);' % t['tokens']['--size-closed'],
        '  line-height: var(--leading-closed, %s);' % t['tokens']['--leading-closed'],
        '  font-weight: var(--weight-closed, %s);' % t['tokens']['--weight-closed'],
        '}',
        '/* THE CASE TOKEN — `--caption-upper` is the dialog\'s "Maiúsculas" field.',
        ' * `cinematic-1` consumes it in its own caption rule; `cinematic-2` wrote the',
        ' * design\'s transform as a LITERAL (`text-transform: none`), so the knob was',
        ' * DEAD in those six themes — a fifth dead control this lane found by measuring',
        ' * every dialog token against every theme, which the audit\'s D3 did not name',
        ' * (its count called a token live if ANY file consumed it). One rule for every',
        ' * extra theme; the declared value is the design\'s own, so the painted type is',
        ' * unchanged and the dial moves it. */',
        '%s .caption__text {' % S,
        '  text-transform: var(--caption-upper, %s);' % t['tokens']['--caption-upper'],
        '}',
    ])
    return out


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
        # `THEMES` holds ASSEMBLED dicts (`[_theme(d) for d in _RAW]` in both modules)
        # and `_theme()` passes only the fields the contract needs, so the RAW dict is
        # matched back by id: it is where `chrome` lives, and the cluster position is
        # read from it.
        raws = {r['id']: r for r in getattr(mod, '_RAW', [])}
        for t in mod.THEMES:
            t['__source'] = src
            t['__raw'] = raws.get(t['id'], {})
            if t['id'] in LABEL_OVERRIDE:
                t['groupLabel'] = LABEL_OVERRIDE[t['id']]
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
        # NO LIGHT SLAB SHIPS (owner, 2026-10-14, verbatim: *"e nao e pra ter tema
        # branco"*). The override is applied to the READ vars BEFORE anything maps them,
        # so every derived token, the alias block and `color-scheme` all follow the dark
        # surface in one step. A design not in the table is untouched.
        for k, v in NO_LIGHT_SLAB.get(did, {}).items():
            d['vars'][k] = v
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
        # THE FOUR CLOSED-LINE TOKENS, PER FAMILY, before anything reads them: the
        # extra module filled them from `SHAPE` (the `cinematic` family's values)
        # because its own import-time check demands every `REQUIRED` name be present.
        apply_closed(t)
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
            # THE ZIP'S OWN THREE READING SCRIMS, NOT A FLAT ONE -- the same
            # composition theme_css() now writes for the base designs, copied
            # VERBATIM out of `zips/cinematic/src/index.css:90-98` (scrim-top,
            # scrim-bottom carrying this theme's own `--cine-scrim`, vignette),
            # photograph LAST, and FOUR values in background-size /
            # background-position -- one per layer.
            # WHY IT IS EMITTED CONDITIONALLY: an extra module that paints its OWN
            # `.panel` rule in `css` emits it AFTER this one, so its rule WINS.
            # MEASURED 2026-10-15 (the parent lane's own run, and mine): changing only
            # this site left 15 themes with a default rule that never paints,
            # duplicated per theme -- the exact defect
            # `receipt-20261015-duas-imagens-no-painel.md` demands be fixed as ONE
            # `.panel` rule with ONE background-image per theme. So the default is
            # emitted ONLY when the module does not paint its own photograph
            # composition; today that is none of them (all 15 extras carry their
            # design's own overlay), and a future one fails closed onto the zip's
            # own three layers rather than onto `panel.css`'s violet slab.
            _own = re.sub(r'/\*[\s\S]*?\*/', '', t.get('css') or '')
            if not re.search(r'\.panel\s*\{[^}]*url\(', _own, re.S):
                strs.append('%s .panel { background-image: '
                            'linear-gradient(to bottom, rgba(0,0,0,0.5), rgba(0,0,0,0)), '
                            'linear-gradient(to top, var(--cine-scrim), rgba(0,0,0,0)), '
                            'radial-gradient(125% 95% at 50% 42%, transparent 52%, rgba(0,0,0,0.44) 100%), '
                            'url(%s); '
                            'background-size: cover, cover, cover, cover; '
                            'background-position: center, center, center, center; }'
                            % (S, t['photo']))
        if t.get('css'):
            strs.append(t['css'].replace('@S@', S))
        # THE GENERATOR'S OWN RULES LAST, so the cluster and the particles cannot be
        # undone by an extra module's block and are the same code path as every other
        # theme's. See `extra_rules`.
        strs.extend(extra_rules(t))
        blocks.append('\n'.join(strs) + '\n')
        row = {'name': i, 'label': t['label'], 'file': 'themes/cinematic.css',
               'swatch': t['swatch']}
        for k in ('group', 'groupLabel', 'variant'):
            if t.get(k):
                row[k] = t[k]
        rows.append(row)

    # D7/D8 — THE LABELS THE PICKER SHOWS, applied in ONE place so a base theme and an
    # extra theme cannot be fixed on one side only.
    for r in rows:
        if r['name'] in LABEL_FIX:
            r['label'] = LABEL_FIX[r['name']]

    # THE REDUCED-MOTION OVERRIDE GOES LAST, after every theme's own transition rules,
    # because it ties with them on specificity and only a later block wins.
    blocks.append(SHARED_TAIL)

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
        # THE SWATCH IS THE CHIP'S COLOUR, and it is NOT always the accent: the designs
        # state BOTH, and `paper-moon` — a LIGHT slab — states a silver swatch
        # (`#aab3c0`, what its own design rail draws) with a DARK accent (`#4c5666`),
        # because silver on near-white is invisible. The check used to demand
        # `--accent == swatch`, and it passed only while that design was filtered out of
        # the build; asserting the CHIP token is both truer and stronger, and `--accent`
        # is still covered by the REQUIRED loop above.
        m = re.search(r'\n  --theme-swatch: (.*?);', '\n' + body)
        if not m or m.group(1).strip().lower() != r['swatch'].lower():
            fails.append('%s: swatch %s != --theme-swatch %s'
                         % (r['name'], r['swatch'], m.group(1).strip() if m else 'ABSENT'))
    # THE OWNER'S OWN RULING, 2026-10-14: *"e nao e pra ter tema branco."* A build that
    # can ship a light slab again is a build that can undo the fix silently, so the
    # threshold is checked HERE, on the bytes this run just wrote, with the SAME number
    # `panel_is_light()` uses to choose `color-scheme` — the census
    # (`_main/theme-lightness-census.py`) reads these same bytes with the same line, so
    # the generator and the instrument cannot disagree about what "light" means.
    for r in rows:
        bodies = re.findall(r":root\[data-theme='%s'\]\{(.*?)\n\}" % re.escape(r['name']),
                            css, re.S)
        m = re.search(r'\n  --bg-slab: (.*?);', '\n' + '\n'.join(bodies))
        if m and panel_is_light(m.group(1).strip()):
            fails.append('%s: LIGHT slab %s -- the owner ruled no white theme (2026-10-14)'
                         % (r['name'], m.group(1).strip()))
    names = [r['name'] for r in rows]
    for n in names:
        if names.count(n) > 1:
            fails.append('%s appears twice' % n)
        if re.match(r'^theme-[1-5]$', n):
            fails.append('%s collides with an original direction' % n)
    # D7/D8 — TWO FACTS THE AUDIT MEASURED, and a build that fails on either cannot
    # ship them again: every `LABEL_FIX` key must name a shipped theme (a rename that
    # matches nothing is a silent no-op), and no two entries may share a label (the
    # owner saw two "Tideline" and had no way to tell which was which).
    for k in LABEL_FIX:
        if k not in names:
            fails.append('LABEL_FIX names %s, which does not ship' % k)
    labels = [r['label'] for r in rows]
    for lab in labels:
        if labels.count(lab) > 1:
            fails.append('label %r appears %d times' % (lab, labels.count(lab)))
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
    print('emitted %d theme(s) -> %s (%d B)' % (len(rows), CSS_OUT, len(open(CSS_OUT, 'rb').read())))
    print('manifest -> %s' % JS_OUT)
    print('SELF-CHECK: every theme declares all %d tokens, swatch == --theme-swatch, '
          'ids unique, no remote url' % len(REQUIRED))
    return 0


if __name__ == '__main__':
    sys.exit(main())
