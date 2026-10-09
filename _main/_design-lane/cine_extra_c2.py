"""cine_extra_c2.py — the SIX panel themes of the `cinematic-2` design zip.

WHAT THIS FILE IS: DATA. Its one public name is `THEMES`, a list of six dicts that
`_main/_design-lane/gen_cinematic.py` reads through `load_extras()` and splices into
`app/panel/themes/cinematic.css` + `themes.js` (the generator adds the `cine-` id
prefix, the token contract, the file layout and every self-check). This file writes no
file, imports nothing but the generator's own constants, and is never loaded by the
panel. `_tokens()` and `_css()` are the same two private helpers `cine_extra_c1.py`
has, for the same reason: six themes repeat one structural block with their own
values, and hand-copied six times the fourth is already a copy of the third with a
value forgotten.

WHICH SIX, AND WHY THEY ARE THE ONES THAT SHIP — `template-plan.md` §2's rows whose
source zip is `cinematic-2`, and nothing else:
  cine-rainline      `01 rainline`      variant `bare`
  cine-cellar        `03 cellar`        variant `glass`
  cine-linen         `04 linen`         variant `plate`   (inverted: LIGHT plate)
  cine-reading-hour  `11 reading-hour`  variant `chip`
  cine-last-train    `13 last-train`    variant `stack`
  cine-blue-hour     `17 blue-hour`     variant `bare`
The other fourteen designs of this zip are excluded by §4 (eight LOUD) or by §2
(§3's own "not shipped" notes for `07 adobe`, `05 side-b`, `06 north-window`,
`08 glasshouse`, `14 dusk-highway`), and the `02 blue-plate`, `12 snowline` and
`16 fireside` exclusions remove the only other members of three variants. No
`karaoke` theme ships, so §1's karaoke spec is documentation-only for now.

WHERE EVERY VALUE COMES FROM, read at the time of writing:
  * `zips/cinematic-2/src/themes.ts` — per design: the 15 `vars` (VERBATIM — see
    `_tokens()`), `fonts.{ui,display,caption}`, the whole `caption{}` object
    (`style`, `align`, `maxw`, `bottom`, `size`, `weight`, `tracking`, `leading`,
    `italic`), `panel.style`/`width`, `chrome`, `filter`, both `overlays`, `vignette`,
    `grain`, `particle`, `wall`.
  * `zips/cinematic-2/src/index.css` — `wordIn` (`0.42s cubic-bezier(0.22,1,0.36,1)`,
    from `opacity 0 / translateY(6px) / blur(3px)`), `softIn` (0.5s, `translateY(10px)`),
    `caretBlink` (`0.45s` opaque / `0.55s` clear of a 1.05s cycle, `steps(1)`), and the
    `breathe` pulse.
  * `_main/_design-lane/inventory-cinematic-2.md` — `# LIVE CAPTION layout variants`
    §1–§5 for the four variant structures this set uses (`bare`, `glass`, `plate`,
    `chip`, `stack`), §"Forming vs settled text, per variant", and the six
    `# Design inventory` blocks for the panels/chrome each design carries.

THE DOM THIS FILE STYLES is exactly the brief's list: `section#captions` >
`.captions__bar` (`.captions__hint`, `#stats-chip`), `.captions__body` >
`.captions__placeholder`, `ol.captions__list` > `li.caption` (newest also
`.caption--latest`, forming line `.caption--provisional`) > `span.caption__led`,
`span.caption__time`, `span.caption__text` > `span.caption__confirmed` +
`span.caption__provisional` > `span.caption__word` (newest carries `data-typing`) >
`span.caption__ch`. No element is added anywhere in this file.

THE FOUR DECISIONS THAT ARE MINE AND NOT THE ZIP'S, each named again where it is
applied so a reviewer can challenge it in one place:
  1. `--size-caption` IS 17px FOR ALL SIX — the FLOOR of the source's own
     `clamp(1.02rem, {caption.size}, 2.3rem)`. The sibling `cinematic` set takes the
     clamp MAX (20–31px, `gen_cinematic.py` DECISION 1) and the `cinematic-1` set
     takes its own clamp floor. This zip's plan is explicit that a stated MAX yields
     only ~20 characters per line at 380px, so the floor is what the design's own
     formula computes in this column. 17px was chosen over the literal 1.02rem
     (16.32px) so that ALL FIFTEEN `cine-*` themes in the shipped stylesheet size
     their caption from ONE number — and because the check that matters is a
     RELATION, not a constant: every stated size (1.44–1.78rem = 23–28.5px) sits
     above the floor, so the floor is the one choice no design contradicts.
  2. OLDER LINES RE-USE the sibling's `max(13px, calc(var(--size-caption) * 0.66))`
     at `opacity: 0.94`. This zip DOES state a previous-line treatment — `stack`'s
     `calc(size * 0.66)` in `color-mix(--cap-text 34%)` — and where a design states
     it (last-train only) it is copied verbatim below. For the other five the zips
     never show a past line at all, so the sibling's number is kept rather than a
     sixth invented one.
  3. THE PREVIOUS LINE IS THE REAL PREVIOUS `li.caption`. The brief's second hook:
     `stack`'s "previous line at 0.66x" is therefore a REAL rule on
     `.caption:not(.caption--provisional)` and not a decoration.
  4. THE FORMING MARKER IS THE CARET, for all six, and it is RESTYLED, never
     removed. This zip states the caret on every variant (`LiveCaptions.tsx:119-126`,
     `Caret` rendered whenever `isLive`), so unlike the `cinematic-1` set there is no
     variant here that has to be given one. `gen_cinematic`'s shared block draws it
     on `.caption--provisional .caption__provisional::after`; each theme below
     overrides only its geometry and lets `background: currentColor` resolve to
     `--text-provisional`, which is `--cap-text` — the tone the design's own `Caret`
     uses when the speaker is unknown (`tone = speaker ? speakerColor(speaker) :
     "var(--text)"`). No theme in this file sets `content: none`, so the shared
     marker survives every one of them.

Run: `py -3 _main/_design-lane/gen_cinematic.py`
"""

from __future__ import annotations

import gen_cinematic as _G

# ── the families `themes.ts` names. Every first family here is one of the sixteen
#    families `app/panel/themes/fonts.css` bundles, so the face that paints is the
#    face the design names; the generic tail is the source's own fallback. ────────
_FONT = {
    'manrope': '"Manrope", ui-sans-serif, system-ui, sans-serif',
    'inter': '"Inter", ui-sans-serif, system-ui, sans-serif',
    'cormorant': '"Cormorant Garamond", Georgia, serif',
    'news': '"Newsreader", Georgia, serif',
    'jost': '"Jost", ui-sans-serif, system-ui, sans-serif',
    'lora': '"Lora", Georgia, serif',
}

# The zip's own UI/meta face is `fonts.ui` PER DESIGN (it is not one shared mono),
# so the four micro-label roles follow the design's `fonts.ui` and only the true
# monospace role — `--font-mono`, which this zip uses for nothing — falls back to
# the repo's bundled mono. `fonts.css` bundles IBM Plex Mono; `--font-mono` is what
# `.caption__time` and `.captions__hint` inherit when a theme does not override them.
_MONO = _G.FAMILIES['mono']

# ── the caption size, and the two relations built on it ──────────────────────────
_SIZE_CAPTION = '17px'   # decision 1 in the header
_PREV_SIZE = 'max(13px, calc(var(--size-caption) * 0.66))'   # `stack`'s own 0.66
_PREV_OPACITY = '0.94'

# ── the two derivations the zip does not state as tokens ─────────────────────────
# `--text-muted`: the source states ONE dim tone per design (`--dim`) and this panel
# wants two. DEFAULT STEP: 62% of `--dim` mixed into `--bg-slab` — i.e. 38% of the way
# from the stated dim tone towards the page. It is applied in the SAME direction in
# every theme, so the light themes get a DARKER muted tone and the dark themes a
# darker-looking, lower-contrast one; `--text-secondary` stays the stated `--dim`
# itself, untouched. Stated as a `color-mix` of two tokens rather than a third hex so
# that it cannot drift when a palette is edited and so that a reviewer can recompute
# it — the four light-plate themes of this zip are exactly where a hand-blended grey
# would have been wrong half the time.
_MUTE_MIX = '62%'
# `--accent-soft`: the zip states no soft accent. It is the design's own `--accent` at
# the alpha the repo's five original directions use for the same role (0.14), so the
# hue cannot drift from the accent and the alpha is the one already in the panel.
_ACCENT_SOFT_ALPHA = '0.14'


def _tokens(d):
    """One design's complete token block, built from its own `vars`.

    THE MAPPING (brief-specified), and the two places it does not exist:
      --bg-slab        <- `--page`        (the opaque colour behind the wallpaper)
      --bg-slab-strong <- `--surface`     (the design's own raised surface)
      --shadow-slab    <- `--shadow`      (the design's own PANEL shadow — NOT the
                          caption's text shadow, which is a different value in every
                          one of the six and is applied on `.caption__text` instead)
      --text-primary   <- `--text`
      --text-secondary <- `--dim`         verbatim, the stated second tone
      --text-muted     <- `--dim` one step towards the page (`_MUTE_MIX` above)
      --text-confirmed / --text-provisional <- `--cap-text`, BOTH, always: in five of
                          this zip's six variants forming and settled are styled
                          IDENTICALLY, and `--cap-text` is the tone the design paints
                          the words in. Rule 4 (the caret) is what says "not final".
      --accent         <- `--accent`      (the caption's own accent role: the `{tone}`
                          of the speaker label, the caret, the rail dot, the chip)
      --accent-soft    <- `--accent` at 0.14 (`_ACCENT_SOFT_ALPHA`)
      --line           <- `--line`        verbatim
      --line-strong    <- the same colour at 0.34 via `raise_alpha`
      --ok / --error   <- the product's own two literals; the zip states none
      --busy           <- `--accent`;  --idle <- `--text-muted`
      --radius-sm/md/lg, --radius-dialog <- FRACTIONS OF `--radius`, which this zip
                          DOES state (4–22px): 0.34 / 0.6 / 1.0 / 0.85 of it. This is
                          the one structural difference from `cinematic-1`, whose
                          radius is a bare number and whose scale came from `SHAPE`.
      --font-sans      <- `fonts.ui`      (chrome, meta rows, panel)
      --font-caption   <- `fonts.caption` (the words)
      --font-closed    <- `fonts.caption` (DECISION in the plan: this zip reuses the
                          caption family for its history row text)
      --size-caption   <- `_SIZE_CAPTION` (decision 1)
      --type-step      <- `0ms`: this zip reveals by WORD (`WordRun` + `.word-in`), and
                          `0ms` is the documented off switch for the per-character
                          reveal, not a deleted rule.
      --cine-scrim     <- the BOTTOM stop of the design's own first `overlay`, i.e. the
                          darkest point of its legibility gradient — where the caption
                          sits (`App.tsx` anchors it at `bottom: caption.bottom`). The
                          zip names no `--scrim` (unlike `cinematic`), so this is the
                          one token read out of the overlay rather than named.
    """
    r = d['radius']
    tk = {
        '--bg-slab': d['page'],
        '--bg-slab-strong': d['surface'],
        '--shadow-slab': d['panel_shadow'],
        '--text-primary': d['text'],
        '--text-confirmed': d['cap_text'],
        '--text-provisional': d['cap_text'],
        '--text-secondary': d['dim'],
        '--text-muted': 'color-mix(in srgb, %s %s, var(--bg-slab))' % (d['dim'], _MUTE_MIX),
        '--line': d['line'],
        '--line-strong': _G.raise_alpha(d['line'], '0.34'),
        '--accent': d['accent'],
        '--accent-soft': 'color-mix(in srgb, %s %d%%, transparent)'
                         % (d['accent'], round(float(_ACCENT_SOFT_ALPHA) * 100)),
        '--theme-swatch': d['accent'],
        '--ok': _G.OK_MEANING,
        '--busy': d['accent'],
        '--error': _G.ERROR_MEANING,
        '--idle': 'var(--text-muted)',
        '--font-sans': _FONT[d['ui_font']],
        '--font-mono': _MONO,
        '--font-caption': _FONT[d['cap_font']],
        '--font-closed': _FONT[d['cap_font']],
        '--size-caption': _SIZE_CAPTION,
        '--leading-caption': d['leading'],
        '--weight-caption': d['weight'],
        '--tracking-caption': d['tracking'],
        '--type-step': '0ms',
        '--cine-scrim': d['scrim'],
        # the radius scale, as fractions of the design's own stated radius
        '--radius-sm': '%gpx' % round(r * 0.34),
        '--radius-md': '%gpx' % round(r * 0.6),
        '--radius-lg': '%dpx' % r,
        '--radius-dialog': '%gpx' % round(r * 0.85),
    }
    tk.update(_G.SHAPE)
    # THE REPO'S SHAPE SCALE MUST NOT OVERWRITE THE RADIUS SCALE WE JUST DERIVED —
    # `SHAPE` carries the `cinematic` zip's fixed 7/12/18/16, and a `dict.update`
    # after it would silently restore another design's corners in every one of these
    # six themes. Re-applied here, AFTER the update, on purpose.
    tk.update({
        '--radius-sm': '%gpx' % round(r * 0.34),
        '--radius-md': '%gpx' % round(r * 0.6),
        '--radius-lg': '%dpx' % r,
        '--radius-dialog': '%gpx' % round(r * 0.85),
    })
    # the aliases `panel.css` and the in-panel editor read
    tk.update({
        '--bg': 'var(--bg-slab)',
        '--bg-raised': 'var(--bg-slab-strong)',
        '--text': 'var(--text-primary)',
        '--text-dim': 'var(--text-secondary)',
        '--text-faint': 'var(--text-muted)',
        '--radius': 'var(--radius-lg)',
        '--font': 'var(--font-sans)',
        '--mono': 'var(--font-mono)',
        '--accent-from': 'var(--accent)',
        '--accent-to': 'var(--accent)',
        '--accent-gradient': 'var(--accent)',
    })
    return tk


# ── one theme's structural block ─────────────────────────────────────────────────

_KEYFRAMES = """/* ── THE WORD REVEAL — declared ONCE for all six `cinematic-2` themes ───────
 * `wordIn` and `caretBlink`, copied from the zip's own `index.css` (the caret's
 * cycle there is a 1.05 s period whose ON phase is the first 45%). They carry no
 * colour and no size, so there is nothing for a theme to have an opinion about, and
 * six copies is six places for one of them to be edited alone.
 *
 * WHY THE REVEAL IS PER WORD: `WordRun` renders one span per word and gives the span
 * at index `revealed - 1` the class `.word-in`; the key includes the word's text, so
 * a changed word REMOUNTS and the animation restarts. The panel's per-character
 * machinery is switched off through `--type-step: 0ms`.
 *
 * THE CARET IS THE SET'S FORMING MARKER (see the file header, rule 4): in five of
 * this zip's six variants the forming text is styled IDENTICALLY to the settled
 * text, so the blinking caret is the ONLY thing on screen that says a word is not
 * final yet. `caretBlink`'s ON value is also the `.caption__provisional::after`
 * rule's base `opacity`, so a suppressed animation leaves the caret VISIBLE. */
@keyframes cine-c2-word {
  from { opacity: 0; transform: translateY(6px); filter: blur(3px); }
  to   { opacity: 1; transform: translateY(0); filter: blur(0); }
}

@keyframes cine-c2-caret {
  0%, 45%   { opacity: 1; }
  55%, 100% { opacity: 0; }
}

@keyframes cine-c2-breathe {
  0%, 100% { transform: scale(1); opacity: 0.85; }
  50%      { transform: scale(1.35); opacity: 0.35; }
}
"""


def _css(d):
    """One design's structural block, with `@S@` standing for its scope selector.

    The generator replaces `@S@` with `:root[data-theme='cine-<id>'] `, so every rule
    below outranks `panel.css`'s single-class rules on specificity alone — which
    matters, because `panel.css` paints the forming line as a dashed, dimmed, ITALIC
    lesser thing (`.caption--provisional .caption__text`) and every variant of this zip
    paints the forming line as the live line.
    """
    a = []

    def w(s=''):
        a.append(s)

    # ── header ──────────────────────────────────────────────────────────────────
    w('/* ── %s — from the `cinematic-2` zip, design `%s` (%s) ───────────'
      % (d['label'], d['id'], d['n']))
    w(' * caption variant `%s`, panel `%s` (%dpx), chrome `%s`%s.'
      % (d['variant_name'], d['panel'], d['panel_width'], d['chrome'],
         ', caption italic' if d['italic'] else ''))
    w(' * The source states the caption as `clamp(1.02rem, %s, 2.3rem)`, weight %s,'
      % (d['size'], d['weight']))
    w(' * leading %s, tracking %s, maxw %s, bottom %s.'
      % (d['leading'], d['tracking'], d['maxw'], d['bottom']))
    w(' * `--size-caption` is the clamp FLOOR (17px), not the stated %s (%.2fpx): at'
      % (d['size'], float(d['size'].replace('rem', '')) * 16))
    w(' * this 380px column the stated size wraps to ~20 characters per line, and the')
    w(' * plan\'s §5 column contract fixes the floor. See the file header, decision 1.')
    w(' * Radius %dpx, blur %s, filter `%s`, vignette %s, grain %s, particle `%s`.'
      % (d['radius'], d['blur'], d['filter'], d['vignette'], d['grain'], d['particle']))
    for n in d['note']:
        w(' * ' + n)
    w(' */')
    w('')

    # ── the backdrop ────────────────────────────────────────────────────────────
    w('/* THE BACKDROP — the design\'s own wallpaper under the design\'s own TWO')
    w(' * overlays, copied VERBATIM out of `themes.ts` in array order, exactly as')
    w(' * `Stage.tsx:84-86` paints them (legibility gradient first, then the warm/cool')
    w(' * pool). WHY THIS RULE EXISTS: the extras path in `gen_cinematic.load_extras()`')
    w(' * emits a FLAT `linear-gradient(--cine-scrim, --cine-scrim)` over the')
    w(' * photograph, and a flat scrim throws away the falloff — the design\'s own')
    w(' * gradient is what grades the image. With NO rule at all the theme inherits')
    w(' * `panel.css`\'s default violet/blue slab, i.e. ANOTHER design\'s colours.')
    w(' * NOT reproduced: the `filter` (`%s`) belongs to the' % d['filter'])
    w(' * wallpaper ELEMENT, and a `filter` on `.panel` would filter the caption with')
    w(' * it; the vignette/grain/particles are ambient layers this panel has no')
    w(' * element for. The photograph is bundled next to this stylesheet, never')
    w(' * fetched. */')
    w('@S@ .panel {')
    w('  background-color: var(--bg-slab);')
    w('  background-image: %s,' % d['overlay_1'])
    w('                    %s,' % d['overlay_2'])
    w('                    url(%s);' % d['photo'])
    w('  background-size: cover, cover, cover;')
    w('  background-position: center, center, center;')
    w('  border-color: var(--line);')
    w('}')
    w('')

    # ── the bar ─────────────────────────────────────────────────────────────────
    w('/* THE BAR — %s' % d['bar_lead'])
    for n in d['bar_note']:
        w(' * ' + n)
    w(' */')
    w('@S@ .captions__bar {')
    for decl in d['bar']:
        w('  ' + decl)
    w('}')
    w('@S@ .captions__hint {')
    w('  color: var(--text-secondary);')
    w('  font-family: var(--font-sans);')
    w('  font-size: %s;' % d['meta_size'])
    w('  letter-spacing: %s;' % d['meta_track'])
    w('  text-transform: uppercase;')
    w('}')
    w('@S@ #stats-chip {')
    w('  color: var(--text-muted);')
    w('  font-family: var(--font-sans);')
    w('  font-size: %s;' % d['footer_size'])
    w('  letter-spacing: %s;' % d['footer_track'])
    w('  text-transform: uppercase;')
    w('}')
    w('')

    # ── the caption box ─────────────────────────────────────────────────────────
    w('/* THE CAPTION BOX — %s' % d['plate_lead'])
    for n in d['plate_note']:
        w(' * ' + n)
    w(' */')
    w('@S@ .captions__body {')
    for decl in d['plate']:
        w('  ' + decl)
    w('}')
    if d.get('light_panel'):
        w('@S@ body { color-scheme: light; }')
    w('')

    # ── the list and the rows ───────────────────────────────────────────────────
    w('/* THE LIST — %s' % d['list_lead'])
    for n in d['list_note']:
        w(' * ' + n)
    w(' */')
    w('@S@ .captions__list {')
    for decl in d['list']:
        w('  ' + decl)
    w('}')
    for rule in d.get('list_extra', []):
        w(rule)
    w('')
    w('/* ONE ROW — %s' % d['row_lead'])
    w(' *')
    w(' * THE FORMING LINE IS THE LIVE LINE. `LiveCaptions.tsx` gives the line being')
    w(' * spoken the whole caption treatment and our `.caption--provisional` IS that')
    w(' * line, so it carries the variant\'s live device; the rule that says so is')
    w(' * written per theme below rather than here, because the four variants each')
    w(' * have their own. `panel.css` gives the forming line a dashed border and an')
    w(' * italic, dimmed text — every design in this zip refuses both. */')
    w('@S@ .caption {')
    for decl in d['row']:
        w('  ' + decl)
    w('}')
    if d.get('led'):
        w('/* The real per-line LED (`span.caption__led`), used as %s. */'
          % d['led_what'])
        w('@S@ .caption__led {')
        for decl in d['led']:
            w('  ' + decl)
        w('}')
    else:
        w('/* This variant has %s, so the real LED element stays OFF' % d['led_what'])
        w(' * rather than being faked into one. */')
        w('@S@ .caption__led { display: none; }')
    w('@S@ .caption__time {')
    for decl in d['time']:
        w('  ' + decl)
    w('}')
    for rule in d.get('live_rules', []):
        w(rule)
    w('')

    # ── the words ───────────────────────────────────────────────────────────────
    w('/* THE TEXT — the design\'s own `--cap-text`, weight, leading, tracking and the')
    w(' * variant\'s alignment. `overflow-wrap: anywhere` because a 380px column must')
    w(' * break a long word rather than push the row sideways. */')
    w('@S@ .caption__text {')
    w('  color: var(--text-confirmed);')
    w('  font-family: var(--font-caption);')
    w('  font-size: var(--size-caption);')
    w('  font-weight: var(--weight-caption);')
    w('  line-height: var(--leading-caption);')
    w('  letter-spacing: var(--tracking-caption);')
    w('  text-transform: none;')
    w('  font-style: %s;' % ('italic' if d['italic'] else 'normal'))
    w('  text-align: %s;' % d['align'])
    w('  overflow-wrap: anywhere;')
    w('  /* THE SHADOW IS THE DESIGN\'S OWN AND IT IS NOT OPTIONAL: every design in')
    w('     this zip is type over a photograph, `bare` states one literal shadow for')
    w('     the whole set, and the pane variants keep it because the pane is')
    w('     translucent. See the file header\'s mapping note on `--cap-text`. */')
    w('  text-shadow: %s;' % d['shadow'])
    w('}')
    w('')
    w('/* FORMING vs SETTLED — this zip states EXACTLY ONE caption colour: in five of')
    w(' * its six variants the forming words and the settled words are styled')
    w(' * identically (`WordRun` is called without `bright`/`dim`), so')
    w(' * `--text-provisional` equals `--text-confirmed` here and the forming marker')
    w(' * is the caret. The exception is `karaoke`, which no shipped theme uses. */')
    w('@S@ .caption--provisional .caption__text {')
    w('  color: var(--text-provisional);')
    w('  font-style: %s;' % ('italic' if d['italic'] else 'normal'))
    w('}')
    w('/* OLDER LINES — %s' % d['prev_lead'])
    for n in d['prev_note']:
        w(' * ' + n)
    w(' */')
    w('@S@ .caption:not(.caption--provisional) .caption__text {')
    w('  color: var(--text-secondary);')
    w('  font-size: %s;' % _PREV_SIZE)
    w('  %s' % d['prev_extra'] if d.get('prev_extra') else None)
    w('  text-shadow: %s;' % d['shadow'])
    w('}')
    w('@S@ .caption:not(.caption--provisional) { opacity: %s; }' % _PREV_OPACITY)
    w('/* THE PANEL\'S OWN TAIL GLYPH, OFF. `panel.js` writes a `\u258d` into')
    w(' * `.caption__mark` on every forming line. This zip\'s tail marker is the caret')
    w(' * (`Caret`, drawn only while `isLive`), so a block glyph would be a second and')
    w(' * wrong one. */')
    w('@S@ .caption__mark { display: none; }')
    w('')
    w('/* The empty state. Each variant states its own idle line ("the room is quiet…"')
    w(' * / "waiting for the first line…" / "nothing said yet, that\'s alright…" /')
    w(' * "rolling…") and this file may not add elements, so the panel\'s own words are')
    w(' * kept and only their VOICE is borrowed: the caption\'s face, italic. */')
    w('@S@ .captions__placeholder {')
    w('  font-family: var(--font-caption);')
    w('  font-style: italic;')
    w('}')
    w('')

    # ── the reveal ──────────────────────────────────────────────────────────────
    w('/* THE REVEAL — one WORD at a time, `wordIn 0.42s cubic-bezier(0.22,1,0.36,1)`')
    w(' * from the zip\'s own `index.css`, with `both` fill. The panel\'s char-by-char')
    w(' * reveal is switched OFF through `--type-step: 0ms`, the documented off switch,')
    w(' * because two animations on one character\'s opacity multiply. NO `color:`')
    w(' * HERE: this zip never recolours a forming word — the accent\'s only job on the')
    w(' * live line is the caret below. */')
    w('@S@ .caption--provisional .caption__word[data-typing] {')
    w('  animation: cine-c2-word 420ms cubic-bezier(0.22, 1, 0.36, 1) both;')
    w('}')
    w('/* THE CARET — `LiveCaptions.tsx:119-126`: 2px wide, 0.92em tall,')
    w(' * `borderRadius: 2`, `transform: translateY(0.06em)`, background `{tone}` and')
    w(' * `caretBlink 1.05s steps(1) infinite`. This theme\'s `{tone}` for an unknown')
    w(' * speaker is `var(--text)`, which is why the shared rule paints it')
    w(' * `currentColor`: here the caret inherits `--text-provisional` = the design\'s')
    w(' * own `--cap-text`. Only the geometry and the blink are overridden, so the')
    w(' * shared marker survives this theme. The base `opacity` is the keyframes\' own')
    w(' * ON value, so a suppressed animation leaves the caret VISIBLE. */')
    w('@S@ .caption--provisional .caption__provisional::after {')
    w('  width: 2px;')
    w('  height: 0.92em;')
    w('  margin-left: %s;' % d['caret_gap'])
    w('  border-radius: 2px;')
    w('  vertical-align: baseline;')
    w('  transform: translateY(0.06em);')
    w('  opacity: 1;')
    w('  animation: cine-c2-caret 1.05s steps(1) infinite;')
    w('}')
    w('')
    if d.get('keyframes'):
        w(_KEYFRAMES)
    else:
        w('/* The two keyframes this block uses (`cine-c2-word`, `cine-c2-caret`) are')
        w(' * declared ONCE, in the `cine-rainline` block at the top of this set. */')
        w('')
    return '\n'.join(x for x in a if x is not None)


# ── the six designs ──────────────────────────────────────────────────────────────
# Every colour, size and font below is copied out of `zips/cinematic-2/src/themes.ts`;
# the `*_lead` / `*_note` strings are the design argument (which variant structure and
# which `LiveCaptions.tsx` / `HistoryPanel.tsx` line it comes from), and `css` is built
# from them by `_css()`.
_RAW = [
    {
        'id': 'rainline',
        'label': 'Rainline',
        'group': 'abc-bare-center', 'variant': 'A',
        'groupLabel': 'A/B: mesmo `bare` ao centro, Manrope 300/1.42 vs Inter 300/1.46 — '
                      '`sheet` + 46 riscos de chuva vs `rail` sem partículas',
        'keyframes': True,
        'n': '01',
        'swatch': '#9fc9dd',
        'variant_name': 'bare',
        'panel': 'sheet', 'panel_width': 384, 'chrome': 'bar',
        'size': '1.72rem', 'weight': '300', 'leading': '1.42', 'tracking': '-0.01em',
        'maxw': '62ch', 'bottom': '6.5rem',
        'italic': False, 'align': 'center',
        'cap_font': 'manrope', 'ui_font': 'manrope',
        'page': '#060c11', 'text': '#eaf3f7', 'dim': '#93a9b4',
        'accent': '#9fc9dd', 'live': '#8fd0c9',
        'surface': 'rgba(10,20,27,.74)', 'surface_2': 'rgba(255,255,255,.055)',
        'line': 'rgba(200,226,238,.14)', 'radius': 16, 'blur': '22px',
        'panel_shadow': '0 24px 70px -30px rgba(0,0,0,.85)',
        'cap_bg': 'rgba(8,18,24,.62)', 'cap_text': '#f2f8fb',
        'cap_edge': 'rgba(220,240,250,.16)',
        'filter': 'saturate(0.78) contrast(1.06) brightness(0.78)',
        'overlay_1': 'linear-gradient(180deg, rgba(6,16,22,.78) 0%, rgba(6,16,22,.24) 34%, '
                     'rgba(6,16,22,.34) 62%, rgba(4,12,18,.9) 100%)',
        'overlay_2': 'radial-gradient(120% 80% at 78% 18%, rgba(160,205,225,.20), transparent 60%)',
        'scrim': 'rgba(4,12,18,.9)',
        'vignette': '0.85', 'grain': '0.05', 'particle': 'rain x46',
        # the one shadow the whole zip shares: `bare` states it, and it is why a
        # weight-300 light-blue line survives a bright frame.
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/rainline.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.6rem', 'meta_track': '0.3em',
        'footer_size': '0.6rem', 'footer_track': '0.26em',
        'note': [
            '`bare` is the ONE variant with no box at all (no `--cap-bg`, no border, no',
            '`soft-in`): type straight on the photograph, `flex flex-col gap-3.5`, with',
            'the `StatusBadge` pill ABOVE and the `Meta` row BELOW, and the speaker label',
            'as an inline `calc(0.66rem * 1.15)` = 0.759rem span before the words.',
            'Our `.captions__bar` is the badge row and `span.caption__time` is the Meta',
            'row; neither element exists for the pill or the divider, so their WORDS are',
            'not reproduced and their type is.',
        ],
        'bar_lead': 'the `StatusBadge` row, which sits ABOVE the words in `bare`.',
        'bar_note': [
            'The badge is a pill (`borderRadius: 999`, `background var(--cap-bg)`,',
            '`border 1px solid var(--cap-edge)`, `blur(var(--blur))`) with an 8px',
            '`breathe` dot over a 6px dot and "listening" at `0.6rem`/`0.3em`/uppercase.',
            'The panel\'s bar is the same ROW, and it keeps the row\'s metrics instead of',
            'the pill, because the pill is a status control and the bar is a hint plus',
            'the panel\'s own behind-chip.',
        ],
        'plate_lead': 'NO BOX — `bare` states no surface, border, radius or blur at all.',
        'plate_note': [
            'The panel\'s `.captions__body` is reset to transparent with no border and',
            'no mask, so the photograph is the only thing behind the words. The mask',
            '`panel.css` puts on this box (a top fade) is REMOVED here: it is a detail of',
            'the original directions\' rail, not of a caption floating on a photograph.',
        ],
        'plate': ['background: none;', 'border: 0;', 'border-radius: 0;',
                  'box-shadow: none;', 'backdrop-filter: none;',
                  '-webkit-mask-image: none;', 'mask-image: none;'],
        'bar': ['justify-content: center;', 'gap: 12px;', 'border: 0;',
                'background: none;', 'padding: 0;'],
        'list_lead': 'the design\'s own `px-5` stage inset, one floating line per row',
        'list_note': ['(`App.tsx:159-183`: `px-5 sm:px-10`, `maxWidth: caption.maxw`;',
                     'the 62ch measure is a stage value and the column\'s content box',
                     'is the measure here, so the padding is what is kept).'],
        'list': ['padding: 0 0 4px;', 'gap: 16px;'],
        'row_lead': '`flex flex-col items-center gap-3.5`, the Meta row UNDER the line',
        'row': ['display: flex;', 'flex-direction: column-reverse;',
                'align-items: center;', 'gap: 10px;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no rail and no dot (this variant has neither)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 9.5px;', 'letter-spacing: 0.26em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — `bare`\'s live badge is the pill with the `breathe` dot',
            ' * in `var(--live)`. Our bar is the badge row, so the live line states',
            ' * itself here: the badge\'s `var(--live)` is this design\'s `--live`',
            ' * `#8fd0c9`, which is NOT its `--accent` `#9fc9dd` — the one design of',
            ' * the six whose live tone differs from its accent. This theme therefore',
            ' * keeps the clock in `--text-muted`, the tone `panel.css` already gives a',
            ' * past line, rather than putting the accent on a clock the design paints',
            ' * in its dim tone. */',
            '@S@ .caption--provisional .caption__time { color: var(--text-muted); }',
        ],
        'prev_lead': 'the sibling set\'s committed-line treatment (decision 2).',
        'prev_note': [
            '`bare` states no previous line: the design shows ONE live line and the',
            '`Meta` row below it. `--text-secondary` is the stated `--dim` here, and the',
            '0.66 factor is the ratio the `stack` variant of this same zip uses for its',
            'own previous line (`calc({caption.size} * 0.66)`).',
        ],
    },
    {
        'id': 'cellar',
        'label': 'Cellar Sessions',
        'group': 'abc-glass', 'variant': 'A',
        'groupLabel': 'A/B: mesmo painel `glass` com `blur(var(--blur)) saturate(1.15)` — '
                      'roman 18px/.46 vs itálico 22px/.5',
        'keyframes': False,
        'n': '03',
        'swatch': '#d9a94f',
        'variant_name': 'glass',
        'panel': 'rail', 'panel_width': 368, 'chrome': 'float',
        'size': '1.78rem', 'weight': '400', 'leading': '1.4', 'tracking': '0.005em',
        'maxw': '64ch', 'bottom': '6rem',
        'italic': False, 'align': 'center',
        'cap_font': 'cormorant', 'ui_font': 'inter',
        'page': '#0c0807', 'text': '#f3e8d7', 'dim': '#a88f6d',
        'accent': '#d9a94f', 'live': '#d9a94f',
        'surface': 'rgba(20,15,11,.7)', 'surface_2': 'rgba(255,236,196,.06)',
        'line': 'rgba(226,196,140,.16)', 'radius': 18, 'blur': '18px',
        'panel_shadow': '0 30px 80px -34px rgba(0,0,0,.9)',
        'cap_bg': 'rgba(18,12,8,.46)', 'cap_text': '#f8efe0',
        'cap_edge': 'rgba(230,196,138,.22)',
        'filter': 'saturate(1.02) contrast(1.05) brightness(0.72)',
        'overlay_1': 'linear-gradient(180deg, rgba(14,10,8,.82) 0%, rgba(18,12,8,.34) 40%, '
                     'rgba(18,12,8,.44) 68%, rgba(10,7,4,.93) 100%)',
        'overlay_2': 'radial-gradient(80% 60% at 70% 26%, rgba(220,168,84,.28), transparent 60%)',
        'scrim': 'rgba(10,7,4,.93)',
        'vignette': '0.95', 'grain': '0.08', 'particle': 'dust x26 (haloed)',
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/cellar.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.66rem', 'meta_track': '0.26em',
        'footer_size': '9.5px', 'footer_track': '0.24em',
        'note': [
            '`glass` is ONE frosted pane: `soft-in`, `px-6 py-4 sm:px-8 sm:py-5`, radius',
            '`var(--radius)`, `backdropFilter: blur(var(--blur)) saturate(1.15)`, and the',
            'harder shadow `0 30px 80px -40px rgba(0,0,0,.9), inset 0 1px 0',
            'rgba(255,255,255,.06)`. At `--cap-bg` 0.46 the image reads THROUGH the',
            'glass, which is the variant\'s whole identity. Its footer word (`live',
            'track`/`hold`) is the level-bars column of the design and is not',
            'reproduced: our DOM has no second footer element.',
        ],
        'bar_lead': 'the pane\'s HEADER row (dot + speaker tag, LevelBars right).',
        'bar_note': [
            'A `h-1.5 w-1.5` dot with `background: {tone}` and',
            '`boxShadow: 0 0 10px {tone}` sits beside a `fonts.ui` `0.66rem`/`0.26em`',
            'uppercase speaker tag in `{tone}`. The GLOW is reproduced as a text-shadow',
            'on the bar\'s own label rather than as a second box-shadow ring, because the',
            'bar is a flex row here and the dot element does not exist in our DOM.',
        ],
        'plate_lead': 'the design\'s own frosted pane, verbatim.',
        'plate_note': [
            'Every declared value is copied: `--cap-bg`, the `--cap-edge` hairline,',
            '`var(--radius)`, the 18px blur with `saturate(1.15)`, and the pane\'s shadow',
            'including its `inset 0 1px 0 rgba(255,255,255,.06)` top light. The pane wraps',
            'the bar AND the words, which is why it lives on `.captions__body` and not on',
            'a single row: in the design the pane holds the header, the body and the',
            'footer.',
        ],
        'plate': ['background: rgba(18,12,8,.46);   /* --cap-bg, 0.46 opaque so the',
                  '                                          image reads THROUGH the glass */',
                  'border: 1px solid rgba(230,196,138,.22);   /* --cap-edge */',
                  'border-radius: var(--radius-lg);',
                  'backdrop-filter: blur(18px) saturate(1.15);',
                  '-webkit-backdrop-filter: blur(18px) saturate(1.15);',
                  'box-shadow: 0 30px 80px -40px rgba(0,0,0,.9), '
                  'inset 0 1px 0 rgba(255,255,255,.06);',
                  'padding: 16px 20px 14px;'],
        'bar': ['justify-content: space-between;', 'gap: 12px;', 'border: 0;',
                'background: none;', 'padding: 0 0 10px;'],
        'list_lead': 'the pane\'s body, one line per row',
        'list_note': ['(`px-6 py-4 sm:px-8 sm:py-5` is the pane\'s padding, so the list',
                     'carries none of its own beyond the row gap).'],
        'list': ['padding: 0;', 'gap: 6px;'],
        'row_lead': 'a line inside the pane, with the `Meta` row UNDER it',
        'row': ['display: flex;', 'flex-direction: column-reverse;',
                'align-items: center;', 'gap: 8px;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no rail in this variant (its dot lives in the header row)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 9.5px;', 'letter-spacing: 0.26em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — the header\'s dot is `{tone}` with a `0 0 10px {tone}`',
            ' * glow and its tag is `{tone}`; the footer prints `live track`. The glow',
            ' * is reproduced on the bar\'s label (the only element in our DOM that',
            ' * stands in for that header) and the accent also marks the line\'s own',
            ' * clock, which is where `panel.css` otherwise puts a TRUE yellow. */',
            '@S@ .captions__hint {',
            '  color: var(--accent);',
            '  text-shadow: 0 0 10px var(--accent);',
            '}',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
            '/* the rail dot, switched to `var(--live)` while running — here the live',
            ' * tone and the accent are the same `#d9a94f`, so one token carries both. */',
            '@S@ .captions__body { border-color: var(--accent); }',
        ],
        'prev_lead': 'a committed line inside the pane, at the sibling set\'s ratio.',
        'prev_note': [
            '`glass` states no previous line either — the pane shows the live words and',
            'the footer. `--text-secondary` is this design\'s stated `--dim` `#a88f6d`,',
            'which is a warm brass and reads as a receded version of the same ink.',
        ],
    },
    {
        'id': 'linen',
        'label': 'Linen Hours',
        'group': 'abc-plate', 'variant': 'A',
        'groupLabel': 'A/B: mesmo painel `plate` com trilho à esquerda — escuro 18px/.46 '
                      'vs papel claro 18px/.9',
        'keyframes': False,
        'n': '04',
        'swatch': '#a8672f',
        'variant_name': 'plate',
        'panel': 'list', 'panel_width': 380, 'chrome': 'bar',
        'size': '1.55rem', 'weight': '400', 'leading': '1.38', 'tracking': '0em',
        'maxw': '66ch', 'bottom': '5.5rem',
        'italic': False, 'align': 'center',
        'cap_font': 'news', 'ui_font': 'inter',
        'page': '#efe7da', 'text': '#2e2a24', 'dim': '#8a7f6f',
        'accent': '#a8672f', 'live': '#7d9c6d',
        'surface': 'rgba(251,247,240,.86)', 'surface_2': 'rgba(46,42,36,.05)',
        'line': 'rgba(90,78,62,.16)', 'radius': 18, 'blur': '16px',
        'panel_shadow': '0 22px 60px -34px rgba(70,54,36,.45)',
        'cap_bg': 'rgba(252,249,243,.9)', 'cap_text': '#332d26',
        'cap_edge': 'rgba(120,104,84,.18)',
        'filter': 'saturate(0.9) contrast(0.98) brightness(1.06)',
        'overlay_1': 'linear-gradient(180deg, rgba(246,240,229,.24) 0%, rgba(246,240,229,.06) 30%, '
                     'rgba(246,240,229,.2) 60%, rgba(244,236,222,.72) 100%)',
        'overlay_2': 'radial-gradient(90% 70% at 30% 20%, rgba(255,246,226,.4), transparent 62%)',
        'scrim': 'rgba(244,236,222,.72)',
        'vignette': '0.3', 'grain': '0.03', 'particle': 'dust x26',
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/linen.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.66rem', 'meta_track': '0.28em',
        'footer_size': '0.66rem', 'footer_track': '0.28em',
        'light_panel': True,
        'note': [
            '`plate` is a two-column block: a LEFT RAIL (8px dot in `var(--live)` or',
            '`var(--dim)`, above a `w-px flex-1` hairline in',
            '`color-mix(--cap-text 18%)`) and a right column whose meta row sits ABOVE',
            'the words (`0.66rem`, `0.28em`, speaker in `{tone}` then "speaking now" in',
            '`color-mix(--cap-text 40%)`, sentence case because that span has no',
            '`uppercase` class). No `StatusBadge`, no `LevelBars`, no `Meta` at all.',
            'THE PLATE IS THE ZIP\'S LIGHT ONE: dark ink `#332d26` on',
            '`rgba(252,249,243,.9)`, where everything the variant mixes with',
            '`--cap-text N%` is a DARKENING of paper rather than a fading of light.',
        ],
        'bar_lead': 'the variant\'s meta row, which sits ABOVE the words.',
        'bar_note': [
            'Reproduced at `0.66rem`/`0.28em` with the speaker slot in `{tone}` — here',
            'the accent `#a8672f`, so the panel\'s hint carries the design\'s own accent.',
            'The sentence-case "speaking now" span is the second half of that row and has',
            'no element here; the panel\'s own behind-chip keeps its panel styling and',
            'only borrows this row\'s metrics.',
        ],
        'plate_lead': 'the design\'s own plate: `rgba(252,249,243,.9)`, radius 18, NO blur.',
        'plate_note': [
            'Copied verbatim, including the absence of `backdropFilter` — `plate` states',
            'none, unlike `glass`/`chip`/`stack`, and the light plate is 0.9 opaque so',
            'there is nothing to read through. Padding is the stated',
            '`1.05rem 1.6rem 0.95rem` with the horizontal value reduced to the 20px the',
            'plan\'s §1 `plate` block fixes for a 380px column (1.6rem = 51px per side).',
            'The plate carries the two-column rail INSIDE it (see the list rules).',
        ],
        'plate': ['background: rgba(252,249,243,.9);',
                  'border: 1px solid rgba(120,104,84,.18);',
                  'border-radius: var(--radius-lg);',
                  'backdrop-filter: none;',
                  '-webkit-backdrop-filter: none;',
                  'box-shadow: 0 26px 70px -36px rgba(0,0,0,.85);',
                  'padding: 16.8px 20px 15.2px;'],
        'bar': ['justify-content: center;', 'gap: 12px;', 'border: 0;',
                'background: none;', 'padding: 0 0 6px;'],
        'list_lead': 'the plate\'s inner rail and its right column',
        'list_note': [
            'The rail is drawn on the LIST, not on the plate, so it runs the height of',
            'the lines it marks (the design draws it inside the block, at',
            '`pt-1.5` from its top). Its hairline is',
            '`color-mix(in srgb, var(--cap-text) 18%, transparent)` — on this light plate',
            'that mix is a DARK grey, which is what makes it visible on paper.',
        ],
        'list': ['position: relative;', 'padding: 0 0 0 28px;', 'gap: 8px;'],
        'list_extra': [
            '@S@ .captions__list::before {',
            '  content: \'\';',
            '  position: absolute;',
            '  left: 7px;',
            '  top: 6px;',
            '  bottom: 6px;',
            '  width: 1px;',
            '  background: color-mix(in srgb, var(--text-confirmed) 18%, transparent);',
            '}',
            '/* the 8px rail dot, in `var(--live)` on the live row and `var(--dim)`',
            ' * otherwise (`LiveCaptions.tsx:287-289`). */',
            '@S@ .captions__list::after {',
            '  content: \'\';',
            '  position: absolute;',
            '  left: 4px;',
            '  top: 8px;',
            '  width: 8px;',
            '  height: 8px;',
            '  border-radius: 99px;',
            '  background: var(--text-muted);',
            '}',
        ],
        'row_lead': 'the right column of the plate, one line per row',
        'row': ['display: flex;', 'flex-direction: column;',
                'align-items: center;', 'gap: 6px;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no per-line LED (the plate\'s dot is the rail\'s head)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 0.66rem;', 'letter-spacing: 0.28em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — the rail dot is `var(--live)` `#7d9c6d` while running and',
            ' * `var(--dim)` otherwise; the meta row prints "speaking now" in',
            ' * `color-mix(--cap-text 40%)`. The dot is the one element-less device a',
            ' * pseudo-element can honestly carry, so the list\'s own dot takes the live',
            ' * tone on the forming row via the `:has()` selector below, and the accent',
            ' * marks the clock. This is the ONE design of the six whose `--live`',
            ' * `#7d9c6d` is a different hue from its accent `#a8672f`. */',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
            '@S@ .captions__body:has(.caption--provisional) .captions__list::after {',
            '  background: #7d9c6d;   /* the design\'s own --live */',
            '}',
        ],
        'prev_lead': 'a past line on the plate, at the sibling set\'s ratio.',
        'prev_note': [
            '`plate` states no previous line. `--text-secondary` is this design\'s',
            '`--dim` `#8a7f6f`, a warm grey that on paper reads as faded ink.',
        ],
    },
    {
        'id': 'reading-hour',
        'label': 'Reading Hour',
        'group': 'abc-chip', 'variant': 'A',
        'groupLabel': 'A/B: mesma `chip` ao centro, peso 400 — Lora 1.46/1.44 escuro vs '
                      'Newsreader 1.44/1.44 claro',
        'keyframes': False,
        'n': '11',
        'swatch': '#c9a447',
        'variant_name': 'chip',
        'panel': 'cards', 'panel_width': 372, 'chrome': 'bar',
        'size': '1.46rem', 'weight': '400', 'leading': '1.44', 'tracking': '0em',
        'maxw': '58ch', 'bottom': '6rem',
        'italic': False, 'align': 'center',
        'cap_font': 'lora', 'ui_font': 'lora',
        'page': '#110c07', 'text': '#f2e6d3', 'dim': '#a58e6c',
        'accent': '#c9a447', 'live': '#c9a447',
        'surface': 'rgba(22,16,10,.74)', 'surface_2': 'rgba(255,234,196,.06)',
        'line': 'rgba(232,200,148,.16)', 'radius': 12, 'blur': '18px',
        'panel_shadow': '0 24px 68px -32px rgba(0,0,0,.88)',
        'cap_bg': 'rgba(20,14,9,.56)', 'cap_text': '#fbf2e1',
        'cap_edge': 'rgba(232,198,142,.2)',
        'filter': 'saturate(0.98) contrast(1.05) brightness(0.76)',
        'overlay_1': 'linear-gradient(180deg, rgba(18,13,9,.78) 0%, rgba(20,15,10,.26) 34%, '
                     'rgba(20,15,10,.4) 66%, rgba(11,8,5,.92) 100%)',
        'overlay_2': 'radial-gradient(70% 60% at 30% 30%, rgba(240,196,120,.26), transparent 62%)',
        'scrim': 'rgba(11,8,5,.92)',
        'vignette': '0.9', 'grain': '0.07', 'particle': 'dust x26',
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/reading-hour.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.66rem', 'meta_track': '0.24em',
        'footer_size': '0.58rem', 'footer_track': '0.26em',
        'note': [
            '`chip` is a header row ABOVE the words: a PILL holding a 6px dot and the',
            'uppercase speaker (`0.66rem`/`0.24em`, `{tone}`), then "capturing"/"paused"',
            '(`0.58rem`/`0.26em`, `color-mix(--cap-text 40%)`), then `LevelBars` pushed',
            'by `ml-auto` and painted even when paused. Body only below — no `Meta`, no',
            'footer word. Every role in this design is Lora, including the',
            '`0.62rem` buttons and the wordmark, so the whole surface is one serif.',
        ],
        'bar_lead': 'the variant\'s header row (speaker pill + state + LevelBars).',
        'bar_note': [
            'The pill is a rounded capsule at radius 999 with',
            '`color-mix(in srgb, {tone} 18%, transparent)` and a `34%` border. Our bar',
            'holds two spans rather than a pill, so the CAPSULE\'s tone is reproduced on',
            'the bar\'s own two labels (18% fill is unreadable over a photo without an',
            'element to fill) and the pill\'s geometry is not — the panel\'s bar is 340px',
            'wide and a capsule plus a state word plus the behind-chip does not fit on',
            'one row at that width. Recorded as a deviation, not as an inventory value.',
        ],
        'plate_lead': 'the chip plate: `calc(var(--radius) * 0.9)` = 10.8px, blur 0.8x.',
        'plate_note': [
            'Every declared value is copied: `--cap-bg`, `--cap-edge`,',
            '`borderRadius: calc(var(--radius) * 0.9)`,',
            '`blur(calc(var(--blur) * 0.8))` = 14.4px (written out, because a',
            '`calc()` inside a `backdrop-filter` is not honoured by every engine this',
            'panel runs on), and the variant\'s own softer shadow',
            '`0 24px 60px -34px rgba(0,0,0,.78)`. Padding `px-5 py-4` = 20px / 16px.',
        ],
        'plate': ['background: rgba(20,14,9,.56);',
                  'border: 1px solid rgba(232,198,142,.2);',
                  'border-radius: 10.8px;',
                  'backdrop-filter: blur(14.4px);',
                  '-webkit-backdrop-filter: blur(14.4px);',
                  'box-shadow: 0 24px 60px -34px rgba(0,0,0,.78);',
                  'padding: 16px 20px;'],
        'bar': ['justify-content: space-between;', 'gap: 10px;', 'border: 0;',
                'background: none;', 'padding: 0 0 10px;'],
        'list_lead': 'the chip\'s body, one line per row, nothing below it',
        'list_note': ['(`flex flex-col gap-2.5`; the list\'s own 10px gap is the',
                     'variant\'s `gap-2.5` and the plate supplies the rest).'],
        'list': ['padding: 0;', 'gap: 10px;'],
        'row_lead': 'a line inside the chip plate, with no meta row of its own',
        'row': ['display: flex;', 'flex-direction: column;',
                'align-items: center;', 'gap: 0;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no per-line dot (the dot belongs to the header pill)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 0.58rem;', 'letter-spacing: 0.26em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — the pill is `color-mix({tone} 18%, transparent)` with a',
            ' * `34%` border and a `{tone}` dot; "capturing" is',
            ' * `color-mix(--cap-text 40%)` and the bars are',
            ' * `color-mix(--cap-text 50%)`. The pill is reproduced as the real',
            ' * `--accent-soft` token (18% is NOT the token\'s alpha; the density the',
            ' * token uses is 0.14, so the two live rows of the A/B pair stay',
            ' * comparable) and the state word takes the accent. */',
            '@S@ .captions__hint {',
            '  color: var(--accent);',
            '  background: var(--accent-soft);',
            '  border: 1px solid color-mix(in srgb, var(--accent) 34%, transparent);',
            '  border-radius: 999px;',
            '  padding: 3px 11px;',
            '}',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
        ],
        'prev_lead': 'a past line in the chip plate, at the sibling set\'s ratio.',
        'prev_note': [
            '`chip` states no previous line — it has no `Meta` and no footer either. The',
            'stated `--dim` `#a58e6c` is the committed-line tone, which is the same warm',
            'brass family as the accent.',
        ],
    },
    {
        'id': 'last-train',
        'label': 'Last Train',
        'group': 'abc-stack', 'variant': 'A',
        'groupLabel': 'A/B: o mesmo `stack` de duas linhas — peso 300 sage vs 400 âmbar '
                      '(fireside NÃO embarcado, ver §4)',
        'keyframes': False,
        'n': '13',
        'swatch': '#a9c4a0',
        'variant_name': 'stack',
        'panel': 'rail', 'panel_width': 368, 'chrome': 'bar',
        'size': '1.48rem', 'weight': '300', 'leading': '1.4', 'tracking': '0.01em',
        'maxw': '58ch', 'bottom': '6rem',
        'italic': False, 'align': 'center',
        'cap_font': 'jost', 'ui_font': 'jost',
        'page': '#0b1113', 'text': '#e8efe9', 'dim': '#93a399',
        'accent': '#a9c4a0', 'live': '#a9c4a0',
        'surface': 'rgba(14,21,21,.72)', 'surface_2': 'rgba(226,240,226,.06)',
        'line': 'rgba(200,224,204,.15)', 'radius': 16, 'blur': '18px',
        'panel_shadow': '0 24px 68px -32px rgba(0,0,0,.86)',
        'cap_bg': 'rgba(10,16,16,.5)', 'cap_text': '#f0f6f0',
        'cap_edge': 'rgba(204,228,208,.18)',
        'filter': 'saturate(0.86) contrast(1.04) brightness(0.78)',
        'overlay_1': 'linear-gradient(180deg, rgba(12,18,18,.78) 0%, rgba(14,20,20,.26) 34%, '
                     'rgba(14,20,20,.4) 64%, rgba(8,13,13,.92) 100%)',
        'overlay_2': 'radial-gradient(70% 60% at 68% 24%, rgba(196,222,196,.2), transparent 62%)',
        'scrim': 'rgba(8,13,13,.92)',
        'vignette': '0.85', 'grain': '0.05', 'particle': 'none',
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/last-train.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.56rem', 'meta_track': '0.26em',
        'footer_size': '0.56rem', 'footer_track': '0.26em',
        'note': [
            '`stack` is the TWO-LINE ROLL and the only variant that states a previous',
            'line: `showPrev = Boolean(partial) && prevText !== words.join(" ")`,',
            'rendered ABOVE the live line in a `truncate` div at',
            '`fontSize: calc({caption.size} * 0.66)` = `calc(1.48rem * 0.66)` =',
            '`0.9768rem`, `color: color-mix(--cap-text 34%)`, `fonts.caption`,',
            '`caption.tracking`. Its root is `soft-in px-5 py-4 sm:px-7` with',
            '`borderLeft: 2px solid {tone}` and NO other border,',
            '`borderRadius: calc(var(--radius) * 0.55)`, `blur(calc(var(--blur) * 0.7))`.',
            'It is the only `stack` theme at weight 300.',
        ],
        'bar_lead': 'the `plain` StatusBadge row (dot + "listening", no pill).',
        'bar_note': [
            '`plain` means no pill background, no border and no blur — just the',
            '`breathe` dot and the word, with "rolling" at `ml-auto` in',
            '`color-mix(--cap-text 34%)` at `0.56rem`/`0.26em`. Our bar is exactly that',
            'shape: two labels, no chip. The `breathe` pulse belongs to the 8px/6px dot',
            'PAIR, and our DOM has no dot element inside the bar, so the pulse is not',
            'reproduced rather than faked onto a text label.',
        ],
        'plate_lead': 'the roll: `--cap-bg` with ONE 2px accent edge and no other border.',
        'plate_note': [
            'The border is on the LEFT only, 2px solid in the speaker tone,',
            '`borderRadius: calc(var(--radius) * 0.55)` = 8.8px,',
            '`blur(calc(var(--blur) * 0.7))` = 12.6px written out, and the variant\'s own',
            'shadow. Padding `px-5 py-4 sm:px-7` reduced to 20px sides for the column.',
            'The 2px edge is `var(--accent)`: `--accent` and `--live` are both `#a9c4a0`',
            'in this design, so the tone and the live colour are the same value.',
        ],
        'plate': ['background: rgba(10,16,16,.5);',
                  'border: 0;',
                  'border-left: 2px solid var(--accent);',
                  'border-radius: 8.8px;',
                  'backdrop-filter: blur(12.6px);',
                  '-webkit-backdrop-filter: blur(12.6px);',
                  'box-shadow: 0 24px 60px -34px rgba(0,0,0,.8);',
                  'padding: 16px 20px;'],
        'bar': ['justify-content: space-between;', 'gap: 10px;', 'border: 0;',
                'background: none;', 'padding: 0 0 8px;'],
        'list_lead': 'the roll\'s two lines, the past one FIRST and truncated to one line',
        'list_note': [
            'The design shows at most two lines at once and truncates the previous one',
            'rather than letting it wrap (the plan\'s own §1 note: a wrapped previous line',
            'pushes the live line off a 900px box). Our list keeps every committed line,',
            'so the truncation rule is applied to each past row below.',
        ],
        'list': ['padding: 0;', 'gap: 6px;'],
        'row_lead': 'the live line, and above it the past line in the design\'s own 34% tone',
        'row': ['display: flex;', 'flex-direction: column-reverse;',
                'align-items: center;', 'gap: 6px;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no per-row LED (this variant\'s device is the 2px left edge)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 0.56rem;', 'letter-spacing: 0.26em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — "rolling" at `ml-auto` in `color-mix(--cap-text 34%)`, and',
            ' * the 2px edge in `{tone}`. The state word is the panel\'s own hint, so it',
            ' * takes that tone at the stated 34% mix; the accent marks the clock. */',
            '@S@ .captions__hint {',
            '  color: color-mix(in srgb, var(--text-confirmed) 34%, transparent);',
            '}',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
        ],
        'prev_lead': 'THE DESIGN\'S OWN PREVIOUS LINE, copied verbatim (the only one stated).',
        'prev_note': [
            '`fontSize: calc({caption.size} * 0.66)`, `color: color-mix(--cap-text 34%)`,',
            '`fonts.caption`, `caption.tracking`. The live size here is the FLOOR (17px)',
            'and not the stated 1.48rem, so the design\'s own 0.66 ratio is applied to the',
            'size the theme actually paints: 17px * 0.66 = 11.22px, which is the same',
            'relation the design draws and the same factor the sibling set uses. That is',
            'why this theme does not need a second rule to be smaller than the live line —',
            'the 0.66 IS the relation.',
        ],
        'prev_extra': 'color: color-mix(in srgb, var(--text-confirmed) 34%, transparent);\n'
                      '  letter-spacing: var(--tracking-caption);\n'
                      '  white-space: nowrap;\n'
                      '  overflow: hidden;\n'
                      '  text-overflow: ellipsis;\n'
                      '  max-width: 100%;',
    },
    {
        'id': 'blue-hour',
        'label': 'Blue Hour',
        'group': 'abc-bare-center', 'variant': 'B',
        'keyframes': False,
        'n': '17',
        'swatch': '#e0a894',
        'variant_name': 'bare',
        'panel': 'rail', 'panel_width': 364, 'chrome': 'float',
        'size': '1.5rem', 'weight': '300', 'leading': '1.46', 'tracking': '0.005em',
        'maxw': '60ch', 'bottom': '6.5rem',
        'italic': False, 'align': 'center',
        'cap_font': 'inter', 'ui_font': 'inter',
        'page': '#0a111c', 'text': '#e9eef6', 'dim': '#93a2b8',
        'accent': '#e0a894', 'live': '#e0a894',
        'surface': 'rgba(13,20,32,.72)', 'surface_2': 'rgba(228,238,250,.06)',
        'line': 'rgba(208,222,240,.15)', 'radius': 18, 'blur': '20px',
        'panel_shadow': '0 24px 70px -32px rgba(0,0,0,.88)',
        'cap_bg': 'rgba(10,16,26,.4)', 'cap_text': '#f2f6fb',
        'cap_edge': 'rgba(212,226,244,.18)',
        'filter': 'saturate(0.92) contrast(1.04) brightness(0.74)',
        'overlay_1': 'linear-gradient(180deg, rgba(10,17,28,.78) 0%, rgba(12,19,30,.26) 34%, '
                     'rgba(12,19,30,.4) 66%, rgba(7,12,20,.92) 100%)',
        'overlay_2': 'radial-gradient(80% 60% at 66% 30%, rgba(214,178,168,.24), transparent 64%)',
        'scrim': 'rgba(7,12,20,.92)',
        'vignette': '0.85', 'grain': '0.05', 'particle': 'none',
        'shadow': '0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)',   # the design's caption textShadow
        'photo': 'backdrops/blue-hour.jpg',
        'caret_gap': '0.12em',
        'meta_size': '0.6rem', 'meta_track': '0.3em',
        'footer_size': '0.6rem', 'footer_track': '0.26em',
        'note': [
            'The restraint row of the zip: no box, no particles, `float` chrome, blush',
            '`--accent` `#e0a894` on a navy page, and the same `bare` structure as',
            '`01 rainline` at the lighter weight and slower leading (`1.5rem`, 300,',
            '`1.46`). Structurally it is `10 nightswim` moved from',
            'purple/serif/italic/1.95rem to navy/sans/roman/1.5rem.',
        ],
        'bar_lead': 'the `StatusBadge` row, above the words — `bare`\'s full pill.',
        'bar_note': [
            'Same structure as Rainline\'s badge but with `--live` === `--accent`, so the',
            'pill, the Mark ring and the radial pool behind the frame are all the same',
            'blush. Kept as a row rather than a pill for the same reason as Rainline\'s:',
            'the panel\'s bar carries a hint and the behind-chip and no status element.',
        ],
        'plate_lead': 'NO BOX — `bare` again: no surface, border, radius or blur.',
        'plate_note': [
            'Reset to transparent with the panel\'s own top-fade mask removed, for the',
            'same reason as Rainline\'s: this variant is type on the photograph and no',
            'part of the original directions\' rail applies to it.',
        ],
        'plate': ['background: none;', 'border: 0;', 'border-radius: 0;',
                  'box-shadow: none;', 'backdrop-filter: none;',
                  '-webkit-mask-image: none;', 'mask-image: none;'],
        'bar': ['justify-content: center;', 'gap: 12px;', 'border: 0;',
                'background: none;', 'padding: 0;'],
        'list_lead': 'the design\'s own stage inset, one floating line per row',
        'list_note': ['(`px-5 sm:px-10`; the 60ch measure is a stage value and the',
                     'column\'s content box is the measure here).'],
        'list': ['padding: 0 0 4px;', 'gap: 16px;'],
        'row_lead': '`flex flex-col items-center gap-3.5`, the Meta row UNDER the line',
        'row': ['display: flex;', 'flex-direction: column-reverse;',
                'align-items: center;', 'gap: 10px;', 'padding: 0;',
                'background: none;', 'border: 0;', 'box-shadow: none;',
                'border-radius: 0;', 'text-align: center;',
                'animation: none;'],
        'led_what': 'no rail and no dot (this variant has neither)',
        'led': None,
        'time': ['color: var(--text-muted);', 'font-family: var(--font-sans);',
                 'font-size: 9.5px;', 'letter-spacing: 0.26em;',
                 'text-transform: uppercase;', 'text-align: center;',
                 'font-variant-numeric: tabular-nums;'],
        'live_rules': [
            '/* THE LIVE ROW — the badge pill fills with `var(--live)` `#e0a894`, which in',
            ' * this design IS the accent, so the pill\'s colour and the accent are one',
            ' * value. The accent also replaces the true yellow `panel.css` puts on the',
            ' * live clock, because the owner\'s own rule for that clock says the theme\'s',
            ' * accent is the right tone where the design already uses it. */',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
        ],
        'prev_lead': 'the sibling set\'s committed-line treatment (decision 2).',
        'prev_note': [
            '`bare` states no previous line. `--text-secondary` is the stated `--dim`',
            '`#93a2b8` — a cool grey-blue, the receded version of this palette\'s ink.',
        ],
    },
]


def _theme(d):
    """One entry of `THEMES`: the generator's fields plus this theme's block."""
    return {
        'id': d['id'],
        'label': d['label'],
        'swatch': d['swatch'],
        'tokens': _tokens(d),
        'photo': d.get('photo'),
        'css': _css(d),
        'group': d.get('group'),
        'groupLabel': d.get('groupLabel'),
        'variant': d.get('variant'),
    }


# `variant` above is the A/B/C LETTER the plan's §3 groups assign; the caption variant
# (`bare`/`glass`/`plate`/`chip`/`stack`) is `variant_name` inside `_RAW`, because the
# generator's manifest field is the letter and nothing else.
THEMES = [_theme(d) for d in _RAW]


def _check():
    """Fail at IMPORT, before the generator's own self-check, on the three things this
    file can get wrong silently: a token the contract needs and this file forgot, a
    swatch that is not the accent the CSS paints, and a theme whose `swatch` would
    disagree with the accent through a `color-mix`."""
    for t in THEMES:
        miss = [k for k in _G.REQUIRED if k not in t['tokens']]
        if miss:
            raise SystemExit('%s misses tokens: %s' % (t['id'], ', '.join(miss)))
        if t['swatch'] != t['tokens']['--accent']:
            raise SystemExit('%s: swatch %s != --accent %s'
                             % (t['id'], t['swatch'], t['tokens']['--accent']))
        if t['id'].startswith(_G.PREFIX):
            raise SystemExit('%s carries the generator\'s own prefix' % t['id'])
        if not t['tokens']['--size-caption'].endswith('px'):
            raise SystemExit('%s: --size-caption is not a px value' % t['id'])
        if not t.get('photo') or 'http' in t['photo']:
            raise SystemExit('%s: photo is not a local path' % t['id'])
        if '@S@' not in t['css']:
            raise SystemExit('%s: css carries no scope placeholder' % t['id'])
        if 'content: none' in t['css'] or 'content:none' in t['css']:
            raise SystemExit('%s: css removes the shared forming caret' % t['id'])


_check()
