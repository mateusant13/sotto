"""cine_extra_c1.py — the NINE panel themes of the `cinematic-1` design zip.

WHAT THIS FILE IS: DATA. Its one public name is `THEMES`, a list of nine dicts that
`_main/_design-lane/gen_cinematic.py` reads through `load_extras()` and splices into
`app/panel/themes/cinematic.css` + `themes.js` (the generator adds the `cine-` id
prefix, the token contract, the file layout and every self-check). This file writes
no file, imports nothing but the generator's own constants, and is never loaded by
the panel. The two private helpers exist for the generator's own reason — nine
themes repeat one structural block with their own values, and hand-copied nine times
the fourth is already a copy of the third with a value forgotten.

WHERE EVERY VALUE COMES FROM — the design source, read at the time of writing,
never an inventory:

  * `zips/cinematic-1/src/data/scenes.ts` — per scene: the whole `caption{}` object
    (`color`, `dim`, `accent`, `size`, `weight`, `leading`, `tracking`, `shadow`,
    `maxWidth`), the whole `panel{}` object (`surface`, `border`, `text`, `muted`,
    `accent`, `soft`, `radius`, `blur`, `shadow`), `captionFont`, `panelFont`,
    `captionVariant`, `panelVariant`, `wallpaper`, `wallOverlay`, `swatch`.
  * `zips/cinematic-1/src/components/CaptionStage.tsx` — the variant's alignment
    (`const centered = variant !== "editorial"`), `clamp(17px, 1.72vw, N px)`, the
    previous line's `clamp(13px, 1.14vw, round(size*0.66))` in `c.dim` at
    `opacity: 0.9`, the meta row (`f-dm text-[10px] uppercase tracking-[0.3em]`), the
    idle caret block and `textWrap: "balance"` + `minHeight: "1.4em"`.
  * `zips/cinematic-1/src/components/StreamText.tsx` — THE FILE THE INVENTORY SAYS
    WAS NOT READ. It IS on disk, and it settles the forming/settled question for
    this zip: every word is its own span with `anim-word-soft` (or `anim-word` when
    `soft={false}`, i.e. the `tight` variant), the tail word takes `opacity: 0.72`
    ONLY when a caret is shown, and the caret is a `0.5ch x 1em` block in
    `caretColor = c.accent`, `border-radius: 2`, `-mb-[0.1em]`, `opacity: 0.55`,
    blinking `caretBlink 1.15s steps(1, end) infinite`. NO word is ever recoloured.
  * `zips/cinematic-1/src/index.css` — the `wordInSoft` / `wordIn` / `caretBlink`
    keyframes, the `.anim-word*` utilities and the `caretBlink` on-values.
  * `zips/cinematic-1/src/components/panels/PanelSetA.tsx` / `PanelSetB.tsx` — each
    panel variant's own geometry (radii, gutters, rails, dots, zebra rows, bubbles,
    chips) and its accent alphas (`${p.accent}3d`, `40`, `12`/`2e`, `16`/`33`, `26`).

THE DOM THIS FILE STYLES, and the one element outside the brief's list:
`section#captions` > `.captions__bar` (`.captions__hint`, `#stats-chip`) and
`.captions__body` > `.captions__placeholder` | `ol.captions__list` > `li.caption`
(`.caption--latest`, `.caption--provisional`) > `.caption__led`, `.caption__time`,
`.caption__text` > `.caption__confirmed` + `.caption__provisional` > `.caption__word`
> `.caption__ch`. The exceptions, each named where it happens in `_css()`:
`.caption__mark` (a real element the brief's list omits — it paints a `\u258d` the
design never has), `@S@ .panel` (the generator's own extras path emits a `.panel`
rule too, and without one a theme inherits `panel.css`'s default violet slab, i.e.
another design's colours), and `@S@ body { color-scheme }`.

THE THREE PRODUCT RULES THIS FILE OBEYS, where the source and the brief disagree the
brief wins and the deviation is recorded in the theme's own CSS comment:
  1. THE FORMING LINE IS THE LIVE LINE. `StreamText` is the design's live line and
     `CaptionStage` gives the previous line `c.dim` at `0.66` size. Our DOM's
     `.caption--provisional` is the line being spoken, so IT takes the live-row
     treatment (full size, the caption's own ink, the accent marker) and every
     committed line takes the design's PREVIOUS-line treatment. The generator's
     base cine themes do the opposite (their `:not(.caption--latest)` rule dims and
     shrinks the FORMING line, which is the one the owner is reading) — this file
     does not repeat that.
  2. THE FORMING TEXT IS NEVER LESS LEGIBLE THAN THE SETTLED TEXT. `StreamText`
     drops the tail word to `opacity: 0.72` when a caret is shown; that is refused
     here (the caret alone is the forming marker, which is what the plan's own
     `tight` note says it is). `--text-provisional` therefore equals the scene's
     single stated caption colour.
  3. NO REMOTE URL, and every backdrop sits behind the scene's own stated
     `wallOverlay` (which is also copied verbatim into `--cine-scrim`'s source: the
     scene's bottom overlay stop, the darkest one, where the caption lives).

Run: `py -3 _main/_design-lane/gen_cinematic.py`
"""

from __future__ import annotations

import gen_cinematic as _G

# ── the families `scenes.ts`'s `F` map declares, verbatim. Every first family here
#    is one of the sixteen families `app/panel/themes/fonts.css` bundles; the
#    generic tails (Georgia, ui-monospace) are the source's own fallbacks. ────────
_FONT = {
    'inter': '"Inter", ui-sans-serif, system-ui, sans-serif',
    'news': '"Newsreader", Georgia, serif',
    'fraunces': '"Fraunces", Georgia, serif',
    'instrument': '"Instrument Serif", Georgia, serif',
    'lora': '"Lora", Georgia, serif',
    'grotesk': '"Space Grotesk", ui-sans-serif, sans-serif',
    'dm': '"DM Mono", ui-monospace, monospace',
}

# The design's own micro-label face everywhere in this zip (`.f-dm`, the TopBar and
# every HistoryPanel) — used for `--font-mono`, for the caption bar and for the row
# timestamps. Nothing else in the zip names a second mono.
_MONO = _FONT['dm']

# `--size-caption` FOR ALL NINE IS THE SOURCE'S CLAMP **FLOOR**, and that is the one
# value in this file that contradicts the sibling generator's `DECISION 1` (which
# takes the clamp MAX for the `cinematic` zip). The plan is explicit for THIS zip:
# §1's `wide` 380 px decision — "1.72vw ~= 6.5px at 380px, so the clamp collapses to
# its 17px floor ... Pick the FLOOR as the column size (see §5)" — and §5's column
# contract names 17px for `cinematic-1` by name. It is also what the design's own
# formula COMPUTES at our width: `clamp(17px, 6.5px, 34px)` = 17px. The scene's
# stated max (27-36px) is quoted in each theme's CSS comment so the decision is one
# number away from being reversed.
_SIZE_CAPTION = '17px'

# OLDER LINES — three treatments exist for the text of a past line and they are
# not the same thing:
#   * the caption STAGE's previous line (`CaptionStage.tsx:81-98`):
#     `clamp(13px, 1.14vw, Math.round(c.size * 0.66))` in `c.dim` at `opacity: 0.9`.
#   * the design's PANEL history rows (`PanelSetA.tsx:88-92`): `text-[13px]` in
#     `p.text` at `opacity: 0.94`.
#   * the PANEL'S OWN CONTRACT (theme-1..5.css and the seven shipped `cinematic`
#     themes): `--text-secondary` at `calc(var(--size-caption) * 0.72)`.
# The third is taken, with the design's own ratio and floor for the size, because it
# is the only one the IN-PANEL EDITOR can drive (`theme-tune.js:159` writes
# `--text-secondary` and calls it "Cor — texto confirmado") and because `c.dim` is
# 0.28-0.34 alpha, i.e. ~3:1 over the plate: fine for the single decorative ghost
# line a mockup draws above a photo, not for the transcript the owner reads back.
_PREV_SIZE = 'max(13px, calc(var(--size-caption) * 0.66))'
_PREV_OPACITY = '0.94'         # PanelSetA.tsx:92 `opacity: 0.94`


# ── the token contract ───────────────────────────────────────────────────────────

def _tokens(d):
    """One theme's complete token block, built from the scene's own values.

    THE MAPPING, and where a role has no source value at all:
      --bg-slab        <- `panel.surface`   (the scene's panel background)
      --bg-slab-strong <- `panel.soft`      (its soft/raised tint; this zip has
                                             exactly ONE soft tone, so the two
                                             tokens the contract would fill with a
                                             second tone both take it)
      --text-primary   <- `panel.text`      (the brightest UI ink)
      --text-secondary <- `panel.muted`     (the dim UI tone: the design's own
                                             micro-labels are painted in it)
      --text-muted     <- `caption.dim`     (the faintest ink the scene states: the
                                             tone it paints its caption-stage meta
                                             row and its single ghost previous line
                                             in. It lands on the placeholder and on
                                             `--idle`; the ROW timestamps and the
                                             OLDER LINES take `panel.muted`, which
                                             is what the design paints a row's
                                             time in and what the in-panel editor
                                             drives as the committed line's colour
                                             — see `_PREV_SIZE` above)
      --text-confirmed/-provisional <- `caption.color`, both, always (rule 2 above)
      --accent         <- `caption.accent`  (the accent's most visible job here is
                                             the caption: the forming line's caret
                                             and the live row's marker. For three
                                             scenes the zip also states a SECOND,
                                             darker `panel.accent` — the contract
                                             has no token for it, so it is unused
                                             and that is named in the report)
      --accent-soft    <- `panel.soft`
      --line           <- `panel.border`    verbatim
      --line-strong    <- the same colour at alpha 0.34 (the repo's second weight)
      --ok/--error     <- the product's own two literals (`OK_MEANING` /
                          `ERROR_MEANING`): the zip states no state colours, and
                          these two MEAN something (the tap is delivering / it is
                          not), so they belong to the app and not to a direction.
      --busy           <- `--accent`; --idle <- `--text-muted`
    """
    tk = {
        '--bg-slab': d['surface'],
        '--bg-slab-strong': d['soft'],
        '--shadow-slab': d['panel_shadow'],
        '--text-primary': d['panel_text'],
        '--text-confirmed': d['caption_color'],
        '--text-provisional': d['caption_color'],
        '--text-secondary': d['panel_muted'],
        '--text-muted': d['caption_dim'],
        '--line': d['border'],
        '--line-strong': _G.raise_alpha(d['border'], '0.34'),
        '--accent': d['caption_accent'],
        '--accent-soft': d['soft'],
        '--theme-swatch': d['caption_accent'],
        '--ok': _G.OK_MEANING,
        '--busy': d['caption_accent'],
        '--error': _G.ERROR_MEANING,
        '--idle': d['caption_dim'],
        '--font-sans': _FONT[d['panel_font']],
        '--font-mono': _MONO,
        '--font-caption': _FONT[d['caption_font']],
        '--font-closed': _FONT[d['panel_font']],
        '--size-caption': _SIZE_CAPTION,
        '--leading-caption': d['leading'],
        '--weight-caption': d['weight'],
        '--tracking-caption': d['tracking'],
        # `StreamText` animates WHOLE WORDS in this zip (one span per word), so the
        # panel's per-character typing reveal is switched off — the documented
        # `--type-step: 0ms` off switch, not a deleted rule. The comment in `_css()`
        # records what that costs (no letter-by-letter typing on these nine).
        '--type-step': '0ms',
        # The scene's own scrim: its `wallOverlay`'s BOTTOM stop — the darkest one,
        # and the one the caption sits under, since `CaptionStage` anchors at
        # `bottom-0 pb-[7vh]`.
        '--cine-scrim': d['scrim'],
    }
    tk.update(_G.SHAPE)
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

_KEYFRAMES = """/* ── THE WORD REVEAL — declared ONCE for all nine `cinematic-1` themes ───────
 * `wordInSoft` / `wordIn` / `caretBlink`, copied from the zip's own `index.css`.
 * They carry no colour and no size, so there is nothing for a theme to have an
 * opinion about, and nine copies is nine places for one of them to be edited
 * alone — the generator's own reason for keeping its set-wide block in one piece.
 * The eight themes below this one reference these three names.
 *
 * WHY THE REVEAL IS PER WORD: `StreamText` renders ONE SPAN PER WORD with
 * `anim-word-soft` (or `anim-word` when `soft={false}`, which is the `tight`
 * variant only). The panel's per-character machinery is switched off through
 * `--type-step: 0ms`, and NOTHING IS RECOLOURED: in this zip the newest word is not
 * given the accent — only the caret is (see each theme's caret block). */
@keyframes cine-c1-word-soft {
  from { opacity: 0; transform: translateY(0.16em); filter: blur(3px); }
  to   { opacity: 1; transform: none; filter: blur(0); }
}

@keyframes cine-c1-word {
  from { opacity: 0; transform: translateY(0.42em); filter: blur(7px); }
  to   { opacity: 1; transform: translateY(0); filter: blur(0); }
}

@keyframes cine-c1-caret {
  0%, 46%   { opacity: 0.85; }
  54%, 100% { opacity: 0; }
}
"""


def _css(d):
    """One theme's structural block, with `@S@` standing for its scope selector.

    The generator replaces `@S@` with `:root[data-theme='cine-<id>'] `, so every rule
    below outranks `panel.css`'s single-class rules on specificity alone (two
    class-level selectors more) — which matters, because `panel.css` paints the
    forming line as a dashed, dimmed, italic lesser thing and this design paints it
    as THE live line.
    """
    a = []

    def w(s=''):
        a.append(s)

    # ── the header ──────────────────────────────────────────────────────────────
    w('/* ── %s — from the `cinematic-1` zip, scene `%s` ─────────────────────'
      % (d['label'], d['id']))
    w(' * caption variant `%s`, panel variant `%s`.' % (d['variant_name'], d['panel']))
    w(' * The source states the caption as `clamp(17px, 1.72vw, %dpx)`, weight %s,'
      % (d['size_max'], d['weight']))
    w(' * leading %s, tracking %s%s.' % (d['leading'], d['tracking'],
                                         ', italic' if d['italic'] else ''))
    w(' * `--size-caption` is the clamp FLOOR (17px): at this 380px column the `vw`')
    w(' * term is 6.5px, so 17px is what the source\'s own formula computes here.')
    w(' * The stated max (%dpx) is a stage value and is NOT used — see the header'
      % d['size_max'])
    w(' * of `cine_extra_c1.py` and the report for why this differs from the')
    w(' * sibling `cinematic` themes, which take the max.')
    for n in d['note']:
        w(' * ' + n)
    w(' */')
    w('')

    # ── the backdrop ────────────────────────────────────────────────────────────
    w('/* THE BACKDROP — the scene\'s own wallpaper under the scene\'s own overlay,')
    w(' * `wallOverlay` copied VERBATIM out of `scenes.ts`. WHY THIS RULE EXISTS:')
    w(' * the generator\'s own extras loop (`gen_cinematic.main()`) emits exactly ONE')
    w(' * `.panel` rule per extra theme — a flat `linear-gradient(--cine-scrim,')
    w(' * --cine-scrim)` over the photograph — and this scene states its overlay as a')
    w(' * gradient with three stops, so the flat form would throw the design\'s own')
    w(' * top-to-bottom falloff away. (This rule comes AFTER the generator\'s, so it is')
    w(' * the one that paints.) With NO rule at all the theme would inherit')
    w(' * `panel.css`\'s default violet/blue slab, i.e. ANOTHER design\'s colours,')
    w(' * which is the failure this whole generator exists to prevent. The scene\'s')
    w(' * `wallFilter` is the one thing NOT reproduced: it belongs to the wallpaper')
    w(' * element, and a `filter` on `.panel` would filter the caption with it. The')
    w(' * photograph is bundled next to this stylesheet, never fetched. */')
    w('@S@ .panel {')
    w('  background-color: var(--bg-slab);')
    w('  background-image: %s,' % d['overlay'])
    w('                    url(%s);' % d['photo'])
    w('  background-size: cover, cover;')
    w('  background-position: center, center;')
    w('  border-color: var(--line);')
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

    # ── the bar ─────────────────────────────────────────────────────────────────
    w('/* THE BAR — the design\'s own meta row, which `CaptionStage` draws ABOVE the')
    w(' * caption: `f-dm text-[10px] uppercase tracking-[0.3em]` in the caption\'s own')
    w(' * dim tone, with the session line pushed to the right. The panel\'s hint and')
    w(' * its "behind" chip are the two elements that map onto it. The chip\'s RED is')
    w(' * a state ("the live path is falling behind") and no design repaints it: only')
    w(' * its face changes here. */')
    w('@S@ .captions__bar {')
    for decl in d['bar']:
        w('  ' + decl)
    w('}')
    w('@S@ .captions__hint {')
    w('  color: var(--text-secondary);')
    w('  font-family: var(--font-mono);')
    w('  font-size: 10px;')
    w('  letter-spacing: 0.3em;')
    w('  text-transform: uppercase;')
    w('}')
    w('@S@ #stats-chip {')
    w('  font-family: var(--font-mono);')
    w('  font-size: 10px;')
    w('  letter-spacing: 0.24em;')
    w('  text-transform: uppercase;')
    w('}')
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
    w(' * THE FORMING LINE IS THE LIVE LINE: `CaptionStage` gives the line being')
    w(' * spoken the whole caption treatment, so `.caption--provisional` carries this')
    w(' * scene\'s live-row device (the dot, the edge, the accent timestamp) and every')
    w(' * COMMITTED line carries the treatment the design gives past lines in its')
    w(' * panel — the same hierarchy the design draws, and the reverse of what the')
    w(' * sibling generator does with its `:not(.caption--latest)` rule, which dims')
    w(' * and shrinks the forming line, i.e. the one the owner is reading. */')
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
        w('/* This panel variant has %s, so the real LED element stays off rather'
          % d['led_what'])
        w(' * than being faked into one. */')
        w('@S@ .caption__led { display: none; }')
    w('@S@ .caption__time {')
    for decl in d['time']:
        w('  ' + decl)
    w('}')
    for rule in d.get('live_rules', []):
        w(rule)
    w('')
    w('/* THE TEXT — the scene\'s own `caption.color`, shadow, leading and tracking,')
    w(' * `text-wrap: balance` and `min-height: 1.4em` from `CaptionStage`, both')
    w(' * verbatim. */')
    w('@S@ .caption__text {')
    w('  color: var(--text-confirmed);')
    w('  font-family: var(--font-caption);')
    w('  font-size: var(--size-caption);')
    w('  font-weight: var(--weight-caption);')
    w('  line-height: var(--leading-caption);')
    w('  letter-spacing: var(--tracking-caption);')
    w('  text-transform: var(--caption-upper);')
    w('  font-style: %s;' % ('italic' if d['italic'] else 'normal'))
    w('  text-align: %s;' % d['align'])
    w('  text-wrap: balance;')
    w('  min-height: 1.4em;')
    w('  /* the scene\'s own shadow, verbatim: it is what holds the type off the') 
    w('     photograph, and it is the design\'s stated legibility device. */')
    w('  text-shadow: %s;' % d['caption_shadow'])
    w('}')
    if d.get('editorial_rule'):
        w('/* THE EDITORIAL RULE — `editorial` is the only left-aligned family of the')
        w(' * zip and its identity above the words is a `h-[1px] w-8` rule at')
        w(' * `opacity: 0.45` in the speaker\'s colour (the speaker\'s NAME has no')
        w(' * element in our DOM, the rule does). 32px = `w-8`. */')
        w('@S@ .caption--provisional .caption__text::before {')
        w('  content: \'\';')
        w('  display: block;')
        w('  width: 32px;')
        w('  height: 1px;')
        w('  margin: 0 0 6px;')
        w('  background: var(--accent);')
        w('  opacity: 0.45;')
        w('}')
    w('')

    # ── forming vs settled, and the older lines ─────────────────────────────────
    w('/* FORMING vs SETTLED — the scene states ONE caption colour, and this keeps')
    w(' * it: `StreamText` drops its tail word to `opacity: 0.72` when a caret is')
    w(' * shown, and that is REFUSED (the brief: the forming text is never less')
    w(' * legible than the settled text). The caret below is the forming marker,')
    w(' * which is what it is in the design too. */')
    w('@S@ .caption--provisional .caption__text {')
    w('  color: var(--text-provisional);')
    w('}')
    w('/* OLDER LINES — `--text-secondary` at the previous line\'s own')
    w(' * `clamp(13px, 1.14vw, 0.66 x size)` (the `vw` term is dead in a 380px')
    w(' * column, so the 13px floor is what applies at this 17px caption) and')
    w(' * `opacity: 0.94` from the design\'s own history rows. `--text-secondary` is')
    w(' * the repo\'s committed-line tone and the ONE the in-panel editor drives. */')
    w('@S@ .caption:not(.caption--provisional) .caption__text {')
    w('  color: var(--text-secondary);')
    w('  font-size: %s;' % _PREV_SIZE)
    w('  text-shadow: %s;' % d['caption_shadow'])
    w('}')
    w('@S@ .caption:not(.caption--provisional) { opacity: %s; }' % _PREV_OPACITY)
    w('/* THE PANEL\'S OWN TAIL GLYPH, OFF. `panel.js` writes a `\u258d` into')
    w(' * `.caption__mark` on every forming line. This zip\'s tail marker is the')
    w(' * caret, and in `wide`/`editorial` it has NO tail marker at all — a block')
    w(' * glyph would be a decoration the design never draws, and next to the')
    w(' * caret it would be a second, wrong one. */')
    w('@S@ .caption__mark { display: none; }')
    w('')
    w('/* The empty state. The design draws an idle caret block and NO prose at all,')
    w(' * so the panel\'s own words are left exactly as `panel.css` paints them — its')
    w(' * title and its body each carry their own colour — and only their VOICE is')
    w(' * borrowed here: the caption\'s own face, italic. */')
    w('@S@ .captions__placeholder {')
    w('  font-family: var(--font-caption);')
    w('  font-style: italic;')
    w('}')
    w('')

    # ── the reveal ──────────────────────────────────────────────────────────────
    w('/* THE REVEAL — one WORD at a time, `%s`.'
      % ('anim-word-soft (soft = true)' if d['word_soft']
         else 'anim-word (soft = false)'))
    w(' * The panel\'s char-by-char typing is OFF (`--type-step: 0ms`), because this')
    w(' * zip reveals whole words and two animations on one character\'s opacity')
    w(' * multiply. The keyframes are declared once, in the `cine-cafe` block. */')
    w('@S@ .caption--provisional .caption__word[data-typing] {')
    w('  /* NO `color:` here, on purpose: this zip never recolours the newest word.')
    w('     The accent\'s only job on the live line is the caret. */')
    w('  animation: %s;' % d['reveal_anim'])
    w('}')
    w('@S@ .caption--provisional .caption__word[data-typing] .caption__ch {')
    w('  animation: none;')
    w('}')
    if d['caret']:
        w('/* THE CARET — `StreamText`: a `0.5ch x 1em` block in `caretColor = c.accent`,')
        w(' * `border-radius: 2`, `-mb-[0.1em]`, blinking `1.15s steps(1, end)` with its')
        w(' * own keyframes holding `0.85` for the first 46% of the cycle. The `0.3em`')
        w(' * lead is the word gap `StreamText` gives every word (`mr-[0.3em]`), which')
        w(' * the panel has no need of — it separates word spans with real spaces. The')
        w(' * caret is drawn by the shared `::after`, so its geometry is overridden')
        w(' * here rather than duplicated. The base `opacity` is the keyframes\' own')
        w(' * on-value, so a suppressed animation leaves the caret VISIBLE. */')
        w('@S@ .caption--provisional .caption__provisional::after {')
        w('  content: \'\';')
        w('  display: inline-block;')
        w('  width: 0.5ch;')
        w('  height: 1em;')
        w('  margin-left: 0.3em;')
        w('  margin-bottom: -0.1em;')
        w('  border-radius: 2px;')
        w('  background: var(--accent);')
        w('  vertical-align: baseline;')
        w('  opacity: 0.85;')
        w('  animation: cine-c1-caret 1.15s steps(1, end) infinite;')
        w('}')
    else:
        w('/* NO CARET — `StreamText` is called with')
        w(' * `caret={variant === "mono" || variant === "tight" || variant === "italic"}`')
        w(' * and this variant is none of the three, so the forming line carries NO')
        w(' * marker at all and its text is styled exactly like the settled text. The')
        w(' * set-wide caret is switched off for this theme: it belongs to the other')
        w(' * zip\'s designs. */')
        w('@S@ .caption--provisional .caption__provisional::after { content: none; }')
    w('')
    if d.get('keyframes'):
        w(_KEYFRAMES)
    else:
        w('/* The three word/caret keyframes this block uses are declared ONCE, in the')
        w(' * `cine-cafe` block at the top of this set. */')
        w('')
    return '\n'.join(a)


# ── the nine scenes ──────────────────────────────────────────────────────────────
# One dict per scene. EVERY colour, size and font below is copied out of
# `zips/cinematic-1/src/data/scenes.ts`; the `*_lead`/`*_note` strings are the
# design argument (which panel variant's geometry is being reproduced and which
# panel-source line it comes from), and `css` is built from them by `_css()`.
_RAW = [
    {
        'id': 'cafe',
        'label': 'Midnight Caf\u00e9',
        'group': 'abc-wide-news', 'variant': 'A',
        'groupLabel': 'A/B: mesmo `wide`, mesma Newsreader — 34px/400/1.34 vs 32px/300/1.4',
        'keyframes': True,
        'swatch': '#E9A85B',
        'variant_name': 'wide',
        'panel': 'glassCards',
        'size_max': 34, 'weight': '400', 'leading': '1.34', 'tracking': '-0.012em',
        'italic': False, 'align': 'center', 'caret': False, 'word_soft': True,
        'caption_font': 'news', 'panel_font': 'inter',
        'caption_color': '#FCEDD8', 'caption_dim': 'rgba(252,237,216,0.34)',
        'caption_accent': '#E9A85B',
        'caption_shadow': '0 2px 22px rgba(6,3,1,0.9), 0 1px 2px rgba(0,0,0,0.7)',
        'panel_text': '#F6E7D4', 'panel_muted': 'rgba(246,231,212,0.5)',
        'border': 'rgba(255,223,182,0.12)', 'surface': 'rgba(26,18,13,0.52)',
        'soft': 'rgba(255,222,180,0.07)',
        'radius': 22, 'blur': 20,
        'panel_shadow': '0 30px 80px -30px rgba(0,0,0,0.85)',
        'overlay': 'linear-gradient(180deg, rgba(28,17,10,0.62) 0%, '
                   'rgba(20,13,9,0.34) 46%, rgba(10,7,5,0.86) 100%)',
        'scrim': 'rgba(10,7,5,0.86)',
        'photo': 'backdrops/cafe.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`glassCards` is the zip\'s most "floating cards" panel: separately rounded',
            'translucent cards over the room, radius 22 on the header and',
            '`max(12, radius - 6)` = 16 on each row, blur 20, and the newest row edged',
            'in `${p.accent}3d` (24%). Row geometry from `PanelSetA.tsx:26-135`.',
        ],
        'plate_lead': 'the design\'s own frosted card (`panel.surface` + blur 20).',
        'plate_note': [
            'The scene paints its own 13px `panel.text` on this surface, so it is a',
            'surface the design itself holds text on; the caption sits on it with the',
            'design\'s own shadow over the design\'s own scrim behind it.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 22,
                  'backdrop-filter: blur(%dpx);' % 20,
                  '-webkit-backdrop-filter: blur(%dpx);' % 20,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s stage inset is `paddingLeft/Right: 32`',
        'list_note': ['(`CaptionStage.tsx:46`), which is what a 380px column can carry',
                     'once the panel\'s own 14px sides are spent: 288px of measure.'],
        'list': ['padding: 10px 32px 12px;', 'gap: 10px;'],
        'row_lead': 'one floating card, `p-3` with `max(12, radius - 6)` = 16.',
        'row': ['grid-template-columns: 1fr;', 'gap: 3px;', 'padding: 10px 12px;',
                'text-align: center;', 'background: var(--bg-slab-strong);',
                'border: 1px solid transparent;', 'border-radius: 16px;'],
        'led_what': 'the card\'s leading dot',
        'led': ['display: block;', 'position: absolute;', 'left: 12px;', 'top: 14px;',
                'width: 6px;', 'height: 6px;', 'border-radius: 99px;',
                'background: var(--accent);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'letter-spacing: 0.14em;',
                 'font-variant-numeric: tabular-nums;', 'text-align: center;'],
        'live_rules': [
            '/* THE LIVE ROW — the design edges its live card in `${p.accent}3d`',
            ' * (PanelSetA.tsx:103). */',
            '@S@ .caption--provisional {',
            '  border-color: color-mix(in srgb, var(--accent) 24%, transparent);',
            '}',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'rainglass',
        'label': 'Rainglass',
        'group': 'abc-tight-inter', 'variant': 'A',
        'groupLabel': 'A/B: mesmo `tight`, Inter 300 + caret — hairline vs folha clara',
        'swatch': '#9FC4D8',
        'variant_name': 'tight',
        'panel': 'hairline',
        'size_max': 28, 'weight': '300', 'leading': '1.5', 'tracking': '-0.02em',
        'italic': False, 'align': 'center', 'caret': True, 'word_soft': False,
        'caption_font': 'inter', 'panel_font': 'inter',
        'caption_color': '#E8F1F7', 'caption_dim': 'rgba(232,241,247,0.3)',
        'caption_accent': '#9FC4D8',
        'caption_shadow': '0 2px 20px rgba(2,6,10,0.92), 0 1px 2px rgba(0,0,0,0.75)',
        'panel_text': '#E4EDF3', 'panel_muted': 'rgba(228,237,243,0.46)',
        'border': 'rgba(255,255,255,0.09)', 'surface': 'rgba(9,15,21,0.34)',
        'soft': 'rgba(159,196,216,0.06)',
        'radius': 14, 'blur': 8,
        'panel_shadow': '0 20px 60px -40px rgba(0,0,0,0.9)',
        'overlay': 'linear-gradient(180deg, rgba(7,13,19,0.64) 0%, '
                   'rgba(8,14,20,0.32) 50%, rgba(5,9,13,0.88) 100%)',
        'scrim': 'rgba(5,9,13,0.88)',
        'photo': 'backdrops/rainglass.jpg',
        'reveal_anim': 'cine-c1-word 620ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`hairline` is the zip\'s only panel with NO card at all: no radius above',
            '14, no shadow glow, blur 8, rows as `grid-cols-[44px_1fr]` on a bottom',
            'hairline with a 4px speaker dot, and a 1px `panel.accent` underline on',
            'the active tab (`PanelSetA.tsx:150-230`) — moved here onto the live row.',
            '`tight` is also the ONE variant with `soft={false}`, i.e. the sharper',
            '`wordIn` (0.42em travel, 7px blur) and a caret.',
        ],
        'plate_lead': 'the DESIGN\'S OWN "no surface" panel, so the box is flat.',
        'plate_note': [
            'The scene states a 0.34-alpha tint and a blur of 8 and nothing else —',
            'no border, no radius, no shadow — so the plate keeps the tint and the',
            'blur and drops the card entirely. A hairline needs an edge to sit on,',
            'and this design\'s edge is the ROW\'s, not the box\'s.',
        ],
        'plate': ['background: var(--bg-slab);', 'border: 0;', 'border-radius: 0;',
                  'backdrop-filter: blur(%dpx);' % 8,
                  '-webkit-backdrop-filter: blur(%dpx);' % 8,
                  'box-shadow: none;'],
        'bar': ['justify-content: space-between;',
                'border-bottom: 1px solid var(--line);',
                'background: none;', 'padding: 0 0 6px;'],
        'list_lead': 'the design\'s stage inset, with the rows on their own hairlines',
        'list_note': ['(`PanelSetA.tsx:186`), so the list itself carries no gap.'],
        'list': ['padding: 2px 32px 6px;', 'gap: 0;'],
        'row_lead': '`grid-cols-[44px_1fr] gap-3 border-b py-3`, no card',
        'row': ['grid-template-columns: 44px 1fr;', 'gap: 12px;',
                'padding: 10px 0;', 'background: none;', 'border: 0;',
                'border-bottom: 1px solid var(--line);', 'border-radius: 0;'],
        'led_what': 'the row\'s own 4px speaker dot',
        'led': ['display: block;', 'position: absolute;', 'left: 44px;', 'top: 15px;',
                'width: 4px;', 'height: 4px;', 'border-radius: 99px;',
                'background: var(--accent);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'font-variant-numeric: tabular-nums;',
                 'padding-top: 2px;'],
        'live_rules': [
            '/* THE LIVE ROW — the design paints the live row\'s time column in',
            ' * `panel.accent` (it prints the word "now" there, which is copy and not',
            ' * our element) and underlines the active tab in 1px `panel.accent`; the',
            ' * underline moves onto the live row here. `caption.accent` and',
            ' * `panel.accent` are the same value in this scene. */',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
            '@S@ .caption--provisional { border-bottom-color: var(--accent); }',
            '/* the dot gets a 12px lead because the row\'s text starts at 44 + 12 */',
            '@S@ .caption__text { padding-left: 12px; }',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'tideline',
        'label': 'Tideline',
        'group': 'abc-wide-news', 'variant': 'B',
        'swatch': '#9CC3CC',
        'variant_name': 'wide',
        'panel': 'timeline',
        'size_max': 32, 'weight': '300', 'leading': '1.4', 'tracking': '-0.014em',
        'italic': False, 'align': 'center', 'caret': False, 'word_soft': True,
        'caption_font': 'news', 'panel_font': 'inter',
        'caption_color': '#E7EFF3', 'caption_dim': 'rgba(231,239,243,0.28)',
        'caption_accent': '#9CC3CC',
        'caption_shadow': '0 2px 20px rgba(2,6,8,0.94), 0 1px 2px rgba(0,0,0,0.75)',
        'panel_text': '#DFE9ED', 'panel_muted': 'rgba(223,233,237,0.44)',
        'border': 'rgba(190,214,220,0.1)', 'surface': 'rgba(13,19,23,0.5)',
        'soft': 'rgba(156,195,204,0.06)',
        'radius': 16, 'blur': 12,
        'panel_shadow': '0 30px 80px -36px rgba(0,0,0,0.88)',
        'overlay': 'linear-gradient(180deg, rgba(9,14,17,0.62) 0%, '
                   'rgba(11,17,20,0.34) 50%, rgba(5,8,10,0.88) 100%)',
        'scrim': 'rgba(5,8,10,0.88)',
        'photo': 'backdrops/tideline.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`timeline` is a drawn spine with dots on it: a 1px line at `left-[26px]`',
            'fading in and out over the full height plus 7px dots per row that turn',
            '`panel.accent` on the live row (`PanelSetB.tsx:236-303`). The same',
            'Tideline id exists in the `cinematic` zip with an unrelated palette;',
            'they are shipped as `cine-tideline` (this one) and `cine-tideline-body`,',
            'and they are never merged.',
        ],
        'plate_lead': 'the design\'s own translucent card (surface + blur 12).',
        'plate_note': [
            'The spine is drawn on the LIST rather than the box so it scrolls with',
            'the lines it marks — the design draws it inside the scrolling column too.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 16,
                  'backdrop-filter: blur(%dpx);' % 12,
                  '-webkit-backdrop-filter: blur(%dpx);' % 12,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s stage inset plus the timeline spine',
        'list_note': ['(`PanelSetB.tsx:255`: `linear-gradient(180deg, transparent,',
                     '${p.border} 8%, ${p.border} 92%, transparent)`), verbatim.'],
        'list': ['position: relative;', 'padding: 10px 32px 12px 56px;', 'gap: 8px;'],
        'list_extra': [
            '@S@ .captions__list::before {',
            '  content: \'\';',
            '  position: absolute;',
            '  left: 30px;',
            '  top: 8px;',
            '  bottom: 8px;',
            '  width: 1px;',
            '  background: linear-gradient(180deg, transparent, var(--line) 8%, '
            'var(--line) 92%, transparent);',
            '}',
        ],
        'row_lead': 'a dot on the spine, the words centred beside it',
        'row': ['grid-template-columns: 1fr;', 'gap: 3px;', 'padding: 8px 0;',
                'text-align: center;', 'background: none;', 'border: 0;',
                'border-radius: 0;'],
        'led_what': 'the row\'s 7px timeline dot (`panelWidth` 350, dots 7px)',
        'led': ['display: block;', 'position: absolute;', 'left: 27px;', 'top: 14px;',
                'width: 7px;', 'height: 7px;', 'border-radius: 99px;',
                'background: var(--bg-slab);',
                'box-shadow: 0 0 0 2px var(--line);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'font-variant-numeric: tabular-nums;',
                 'text-align: center;'],
        'live_rules': [
            '/* THE LIVE ROW — `PanelSetB.tsx:267-289`: the dot takes the speaker',
            ' * colour (`panel.accent` here) and a `0 0 0 2px ${color}40` ring, and',
            ' * the time column is printed in the accent. */',
            '@S@ .caption--provisional .caption__led {',
            '  background: var(--accent);',
            '  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);',
            '}',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'fieldnotes',
        'label': 'Field Notes',
        'group': 'abc-tight-inter', 'variant': 'B',
        'swatch': '#A9CBC6',
        'variant_name': 'tight',
        'panel': 'gutter',
        'size_max': 27, 'weight': '300', 'leading': '1.52', 'tracking': '-0.018em',
        'italic': False, 'align': 'center', 'caret': True, 'word_soft': False,
        'caption_font': 'inter', 'panel_font': 'news',
        'caption_color': '#F3F0E8', 'caption_dim': 'rgba(243,240,232,0.3)',
        'caption_accent': '#A9CBC6',
        'caption_shadow': '0 2px 20px rgba(3,7,9,0.92), 0 1px 2px rgba(0,0,0,0.7)',
        'panel_text': '#232A2C', 'panel_muted': 'rgba(35,42,44,0.5)',
        'border': 'rgba(35,45,48,0.12)', 'surface': 'rgba(243,239,230,0.94)',
        'soft': 'rgba(63,94,96,0.07)',
        'radius': 16, 'blur': 0,
        'panel_shadow': '0 34px 80px -34px rgba(0,0,0,0.75)',
        'overlay': 'linear-gradient(180deg, rgba(17,27,32,0.62) 0%, '
                   'rgba(19,29,34,0.32) 50%, rgba(10,16,19,0.88) 100%)',
        'scrim': 'rgba(10,16,19,0.88)',
        'photo': 'backdrops/fieldnotes.jpg',
        'reveal_anim': 'cine-c1-word 620ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'light_panel': True,
        'note': [
            '`gutter` is a LIGHT sheet (surface `rgba(243,239,230,0.94)`, blur 0) with',
            'a 54px margin column whose timestamps are right-aligned and whose live',
            'row carries an initials avatar in `panel.accent`',
            '(`PanelSetA.tsx:236-303`). It is one of the zip\'s two inverted-chrome',
            'scenes: dark ink on paper, while the CAPTION of this scene is LIGHT ink',
            '(`#F3F0E8`) designed to sit on the graded photograph, not on the sheet.',
        ],
        'plate_lead': 'the design\'s sheet, but UNDER the design\'s own scrim.',
        'plate_note': [
            'The sheet is 0.94-opaque LIGHT paper, and this scene\'s caption is light',
            'ink: the pair is about 1.05:1 and would be invisible. So the sheet sits',
            'under `--cine-scrim` — the scene\'s own `wallOverlay` bottom stop, which',
            'is exactly the layer the design puts between the photograph and the type',
            '— and the palette\'s paper warmth still tints the plate. No invented',
            'colour: both layers are the scene\'s.',
        ],
        'plate': ['background: linear-gradient(var(--cine-scrim), var(--cine-scrim)),',
                  '            var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 16,
                  'backdrop-filter: none;',
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s 54px margin gutter, rows on their own rules',
        'list_note': [
            'The gutter\'s rules are the sheet\'s `panel.border` alpha (0.12) carried',
            'onto the scene\'s own `caption.color` ink: `rgba(35,45,48,0.12)` is dark',
            'ink for the LIGHT sheet, and the caption is not on the sheet.',
        ],
        'list': ['padding: 4px 20px 6px;', 'gap: 0;'],
        'row_lead': '`grid-cols-[54px_1fr]` with the time right-aligned in the gutter',
        'row': ['grid-template-columns: 54px 1fr;', 'gap: 14px;',
                'padding: 9px 0;', 'background: none;', 'border: 0;',
                'border-bottom: 1px solid '
                'color-mix(in srgb, var(--text-confirmed) 12%, transparent);',
                'border-radius: 0;'],
        'led_what': 'the gutter\'s avatar slot, reduced to the scene\'s own accent dot',
        'led': ['display: block;', 'position: absolute;', 'left: 24px;', 'top: 30px;',
                'width: 5px;', 'height: 5px;', 'border-radius: 99px;',
                'background: var(--accent);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'font-variant-numeric: tabular-nums;',
                 'justify-self: end;', 'text-align: right;', 'padding-top: 2px;'],
        'live_rules': [
            '/* THE LIVE ROW — the design paints the live row\'s time column in',
            ' * `panel.accent` (Gutter, `PanelSetA.tsx:283`). */',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
            '@S@ .caption--provisional {',
            '  border-bottom-color: color-mix(in srgb, var(--accent) 55%, transparent);',
            '}',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'dustlight',
        'label': 'Dustlight',
        'group': 'abc-italic-serif', 'variant': 'A',
        'groupLabel': 'A/B: mesmo `italic`, 1.42 e -0.008em — Fraunces 33 vs Lora 30',
        'swatch': '#F09A55',
        'variant_name': 'italic',
        'panel': 'paper',
        'size_max': 33, 'weight': '400', 'leading': '1.42', 'tracking': '-0.008em',
        'italic': True, 'align': 'center', 'caret': True, 'word_soft': True,
        'caption_font': 'fraunces', 'panel_font': 'dm',
        'caption_color': '#FFE7CC', 'caption_dim': 'rgba(255,231,204,0.32)',
        'caption_accent': '#F09A55',
        'caption_shadow': '0 2px 22px rgba(24,10,3,0.9), 0 1px 2px rgba(0,0,0,0.65)',
        'panel_text': '#35261B', 'panel_muted': 'rgba(53,38,27,0.52)',
        'border': 'rgba(60,40,26,0.14)', 'surface': '#F6EDE1',
        'soft': 'rgba(196,86,47,0.07)',
        'radius': 10, 'blur': 0,
        'panel_shadow': '0 34px 80px -34px rgba(0,0,0,0.8)',
        'overlay': 'linear-gradient(180deg, rgba(34,19,11,0.5) 0%, '
                   'rgba(44,23,14,0.26) 52%, rgba(14,8,5,0.82) 100%)',
        'scrim': 'rgba(14,8,5,0.82)',
        'photo': 'backdrops/dustlight.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'light_panel': True,
        'note': [
            '`paper` is one OPAQUE ruled sheet: `background: #F6EDE1`, radius 10,',
            '`blur: 0`, a 27px repeating rule, a 1.5px red margin rule at `left-[52px]`',
            'filled `${p.accent}59`, and `leading-[27px]` rows on a',
            '`grid-cols-[52px_1fr]` (`PanelSetA.tsx:250-340`). The FIRST inverted',
            '(light) chrome in the zip: `DM Mono` transcribes and a serif narrates,',
            'while the caption stays warm light-on-dark over the photograph.',
        ],
        'plate_lead': 'the design\'s paper sheet, UNDER the design\'s own scrim.',
        'plate_note': [
            'Same reason as Field Notes: this scene\'s caption ink is light',
            '(`#FFE7CC`) and the sheet is opaque `#F6EDE1` — 1.02:1 — so the design\'s',
            'own scrim goes between them. The measured asset behind it is a desert',
            'highway at sunset whose sky is nearly white, i.e. the worst case for a',
            'light caption: the scrim is not decoration here, it is the product.',
        ],
        'plate': ['background: linear-gradient(var(--cine-scrim), var(--cine-scrim)),',
                  '            var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 10,
                  'backdrop-filter: none;',
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the sheet\'s red margin rule and its 52px time column',
        'list_note': [
            'The margin rule is `${p.accent}59` = the scene\'s own accent at 35%,',
            'reproduced with `color-mix`, and drawn on the LIST so it scrolls with',
            'the page. The 27px rule period is NOT reproduced as a fixed rhythm: our',
            'rows hold a live caption of variable height, so each row sits on its own',
            'rule instead (the design\'s intent — "every text line sits on a printed',
            'rule").',
        ],
        'list': [
            'position: relative;',
            '/* padding-left 0: the sheet\'s time column is FLUSH with the sheet\'s',
            '   edge and the red margin rule falls at the END of it (52px), which is',
            '   the design\'s own `grid-cols-[52px_1fr]` + `left-[52px]` pairing. */',
            'padding: 6px 16px 8px 0;',
            'gap: 0;',
            'background-image: linear-gradient(90deg, transparent 52px,',
            '  color-mix(in srgb, var(--accent) 35%, transparent) 52px,',
            '  color-mix(in srgb, var(--accent) 35%, transparent) 53.5px,',
            '  transparent 53.5px);',
        ],
        'row_lead': '`grid-cols-[52px_1fr]`, right-aligned 9.5px timestamps',
        'row': ['grid-template-columns: 52px 1fr;', 'gap: 12px;',
                'padding: 7px 0;', 'background: none;', 'border: 0;',
                'border-bottom: 1px solid '
                'color-mix(in srgb, var(--text-confirmed) 7.5%, transparent);',
                'border-radius: 0;'],
        'led_what': 'no per-row dot (the sheet\'s device is its red margin rule)',
        'led': None,
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 9.5px;', 'font-variant-numeric: tabular-nums;',
                 'justify-self: end;', 'text-align: right;', 'padding-top: 4px;'],
        'live_rules': [
            '/* THE LIVE ROW — the design prints the live row\'s timestamp in',
            ' * `panel.accent` and stamps the row `filed`; the accent timestamp is',
            ' * the part our DOM can carry. `caption.accent` and `panel.accent`',
            ' * differ in this scene (`#F09A55` / `#C4562F`) and the token takes the',
            ' * CAPTION\'s — see the report. */',
            '@S@ .caption--provisional .caption__time { color: var(--accent); }',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'analog',
        'label': 'Analog',
        'swatch': '#DCB183',
        'variant_name': 'wide',
        'panel': 'quotes',
        'size_max': 36, 'weight': '400', 'leading': '1.3', 'tracking': '-0.01em',
        'italic': False, 'align': 'center', 'caret': False, 'word_soft': True,
        'caption_font': 'instrument', 'panel_font': 'lora',
        'caption_color': '#FFF2E0', 'caption_dim': 'rgba(255,242,224,0.32)',
        'caption_accent': '#DCB183',
        'caption_shadow': '0 2px 24px rgba(20,8,2,0.92), 0 1px 2px rgba(0,0,0,0.7)',
        'panel_text': '#F1E3D3', 'panel_muted': 'rgba(241,227,211,0.48)',
        'border': 'rgba(232,198,155,0.13)', 'surface': 'rgba(32,22,16,0.58)',
        'soft': 'rgba(217,168,108,0.07)',
        'radius': 18, 'blur': 16,
        'panel_shadow': '0 30px 80px -30px rgba(0,0,0,0.85)',
        'overlay': 'radial-gradient(120% 90% at 42% 38%, rgba(58,34,18,0.42) 0%, '
                   'rgba(20,13,9,0.66) 62%, rgba(12,8,6,0.9) 100%)',
        'scrim': 'rgba(12,8,6,0.9)',
        'photo': 'backdrops/analog.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`quotes` is a stack of sleeve-note cards: radius 18 header card,',
            '`px-4 py-3.5 pl-5` segment cards at radius 14 with a `2px` coloured left',
            'edge and a `text-[34px]` opening quote glyph at `${color}2e`, the live',
            'card filled `${p.accent}12` with a `${p.accent}30` border',
            '(`PanelSetA.tsx:353-440`). The GLYPH is the one device not reproduced:',
            'it is a character, and this file may not add content to the DOM.',
        ],
        'plate_lead': 'the design\'s own card stack surface (surface + blur 16).',
        'plate_note': [
            'The scene\'s overlay is the zip\'s only RADIAL one — a cocoa pool at',
            '42%/38% — and it is copied verbatim above.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 18,
                  'backdrop-filter: blur(%dpx);' % 16,
                  '-webkit-backdrop-filter: blur(%dpx);' % 16,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s stage inset, one card per line',
        'list_note': ['(`maxWidth: 760`, the widest in the zip).'],
        'list': ['padding: 12px 32px 14px;', 'gap: 10px;'],
        'row_lead': 'a sleeve-note card, radius 14, with the scene\'s own left edge',
        'row': ['grid-template-columns: 1fr;', 'gap: 3px;', 'padding: 10px 14px;',
                'text-align: center;', 'background: var(--bg-slab);',
                'border: 1px solid var(--line);', 'border-radius: 14px;'],
        'led_what': 'no per-row dot (this variant\'s marker is the 2px left edge)',
        'led': None,
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'font-variant-numeric: tabular-nums;',
                 'text-align: center;'],
        'live_rules': [
            '/* THE LIVE ROW — `PanelSetA.tsx:413-415`: fill `${p.accent}12` (7%),',
            ' * border `${p.accent}30` (19%), `borderLeft: 2px solid ${p.accent}`. */',
            '@S@ .caption--provisional {',
            '  background: color-mix(in srgb, var(--accent) 7%, transparent);',
            '  border-color: color-mix(in srgb, var(--accent) 19%, transparent);',
            '  border-left: 2px solid var(--accent);',
            '}',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'shelves',
        'label': 'Quiet Shelves',
        'group': 'abc-editorial', 'variant': 'A',
        'groupLabel': 'A/B: mesmo `editorial` à esquerda, 1.38 e -0.01em — Lora 31 vs Fraunces 32',
        'swatch': '#D8B060',
        'variant_name': 'editorial',
        'panel': 'ledger',
        'size_max': 31, 'weight': '400', 'leading': '1.38', 'tracking': '-0.01em',
        'italic': False, 'align': 'left', 'caret': False, 'word_soft': True,
        'caption_font': 'lora', 'panel_font': 'grotesk',
        'caption_color': '#F2EDDD', 'caption_dim': 'rgba(242,237,221,0.3)',
        'caption_accent': '#D8B060',
        'caption_shadow': '0 2px 20px rgba(4,6,4,0.92), 0 1px 2px rgba(0,0,0,0.72)',
        'panel_text': '#EDE9DA', 'panel_muted': 'rgba(237,233,218,0.46)',
        'border': 'rgba(216,176,96,0.12)', 'surface': 'rgba(17,21,16,0.6)',
        'soft': 'rgba(216,176,96,0.06)',
        'radius': 6, 'blur': 14,
        'panel_shadow': '0 30px 80px -34px rgba(0,0,0,0.88)',
        'overlay': 'linear-gradient(180deg, rgba(10,14,10,0.66) 0%, '
                   'rgba(12,16,12,0.4) 48%, rgba(7,9,7,0.88) 100%)',
        'scrim': 'rgba(7,9,7,0.88)',
        'photo': 'backdrops/shelves.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`ledger` is a real table: a printed column-header band',
            '(`grid-cols-[46px_58px_1fr]`, `text-[9px] uppercase tracking-[0.2em]`),',
            'zebra rows on `i % 2 ? p.soft : transparent`, and a live row whose time',
            'cell is replaced by a 5px `LiveDot` with a `${p.accent}40` rule',
            '(`PanelSetA.tsx:461-520`). The column band maps onto the panel\'s own',
            'caption bar, and `46px 58px` reduces to `46px 1fr` in a 380px column.',
            '`editorial` is one of the zip\'s two LEFT-aligned captions, and its',
            'speaker row (`h-[1px] w-8` at opacity 0.45) is above the words.',
        ],
        'plate_lead': 'the design\'s ledger surface (radius 6, blur 14).',
        'plate_note': [
            'The zip\'s least "card-like" frosted layout: the smallest radius (6) and',
            'a 14px blur, which is why the plate stays square-edged here.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 6,
                  'backdrop-filter: blur(%dpx);' % 14,
                  '-webkit-backdrop-filter: blur(%dpx);' % 14,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;',
                'border-bottom: 1px solid var(--line);',
                'background: none;', 'padding: 0 0 6px;',
                'text-transform: uppercase;'],
        'list_lead': 'a table: a 46px time column, rules, and zebra rows',
        'list_note': [
            'Zebra is the design\'s own rule (`i % 2 ? p.soft : transparent`), so the',
            'even rows — index 1, 3, 5 — take the soft tint.',
            'The 32px editorial rule lives above the words, below.',
        ],
        'list': ['padding: 0 20px 8px;', 'gap: 0;'],
        'list_extra': [
            '@S@ .caption:nth-child(even) { background: var(--bg-slab-strong); }',
        ],
        'row_lead': '`grid-cols-[46px_1fr]`, rows on a rule, the live row boxed',
        'row': ['grid-template-columns: 46px 1fr;', 'gap: 10px;',
                'padding: 9px 8px;', 'text-align: left;',
                'background: transparent;', 'border: 0;',
                'border-bottom: 1px solid var(--line);', 'border-radius: 0;'],
        'led_what': 'the ledger\'s 5px `LiveDot`, which replaces the live row\'s clock',
        'led': ['display: none;', 'position: absolute;', 'left: 22px;',
                'top: 50%;', 'margin-top: -2.5px;', 'width: 5px;', 'height: 5px;',
                'border-radius: 99px;', 'background: var(--accent);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 10px;', 'font-variant-numeric: tabular-nums;',
                 'justify-self: end;', 'text-align: right;', 'padding-top: 2px;'],
        'live_rules': [
            '/* THE LIVE ROW — `PanelSetA.tsx:506`: `borderColor: ${p.accent}40`',
            ' * (25%) over `p.soft`, its time cell a 5px ringless `LiveDot`. */',
            '@S@ .caption--provisional {',
            '  background: var(--bg-slab-strong);',
            '  border-bottom-color: color-mix(in srgb, var(--accent) 25%, transparent);',
            '}',
            '@S@ .caption--provisional .caption__led { display: block; }',
        ],
        'editorial_rule': True,
    },
    {
        'id': 'rooftop',
        'label': 'Rooftop Dusk',
        'group': 'abc-italic-serif', 'variant': 'B',
        'swatch': '#E4B0CC',
        'variant_name': 'italic',
        'panel': 'bubbles',
        'size_max': 30, 'weight': '400', 'leading': '1.42', 'tracking': '-0.008em',
        'italic': True, 'align': 'center', 'caret': True, 'word_soft': True,
        'caption_font': 'lora', 'panel_font': 'inter',
        'caption_color': '#F3E9F4', 'caption_dim': 'rgba(243,233,244,0.3)',
        'caption_accent': '#E4B0CC',
        'caption_shadow': '0 2px 20px rgba(8,4,16,0.9), 0 1px 2px rgba(0,0,0,0.66)',
        'panel_text': '#F0E9F2', 'panel_muted': 'rgba(240,233,242,0.48)',
        'border': 'rgba(240,222,246,0.12)', 'surface': 'rgba(29,23,42,0.56)',
        'soft': 'rgba(228,176,204,0.08)',
        'radius': 20, 'blur': 18,
        'panel_shadow': '0 30px 80px -32px rgba(0,0,0,0.85)',
        'overlay': 'linear-gradient(180deg, rgba(28,22,46,0.6) 0%, '
                   'rgba(38,28,52,0.28) 52%, rgba(14,11,22,0.86) 100%)',
        'scrim': 'rgba(14,11,22,0.86)',
        'photo': 'backdrops/rooftop.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`bubbles` is a two-voice chat: every segment is a bubble with the',
            'asymmetric radius `16px 16px 5px 16px` / `16px 16px 16px 5px`, the',
            'default fill `p.surface` and border `p.border`, and the live bubble',
            '`${p.accent}16` (9%) over `${p.accent}33` (20%); its dot carries',
            '`0 0 0 4px ${p.accent}26` (15%) (`PanelSetB.tsx:119-207`). Our rows have',
            'no speaker, so the asymmetry is keyed on the live row only.',
        ],
        'plate_lead': 'the design\'s bubble surface (radius 20, blur 18).',
        'plate_note': [
            'One of the zip\'s three heaviest blurs, with the largest radius in the',
            'set after GlassCards.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 20,
                  'backdrop-filter: blur(%dpx);' % 18,
                  '-webkit-backdrop-filter: blur(%dpx);' % 18,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s stage inset, one bubble per line',
        'list_note': ['The bubble tail points at the left, where the speaker column',
                     'sits in the design (`maxWidth: 720`).'],
        'list': ['padding: 12px 32px 14px;', 'gap: 8px;'],
        'row_lead': 'a bubble with the zip\'s asymmetric bottom-left tail',
        'row': ['grid-template-columns: 1fr;', 'gap: 3px;', 'padding: 9px 12px;',
                'text-align: center;', 'background: var(--bg-slab);',
                'border: 1px solid var(--line);',
                'border-radius: 16px 16px 16px 5px;'],
        'led_what': 'the bubble\'s own dot, with the design\'s 4px halo ring',
        'led': ['display: block;', 'position: absolute;', 'left: 14px;', 'top: 16px;',
                'width: 5px;', 'height: 5px;', 'border-radius: 99px;',
                'background: var(--accent);'],
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 9.5px;', 'font-variant-numeric: tabular-nums;',
                 'text-align: center;'],
        'live_rules': [
            '/* THE LIVE ROW — the design\'s live bubble flips the tail to the right',
            ' * (`16px 16px 5px 16px`), fills `${p.accent}16` (9%), borders',
            ' * `${p.accent}33` (20%) and blooms its dot with `0 0 0 4px',
            ' * ${p.accent}26` (15%) — `PanelSetB.tsx:179-190, 289`. */',
            '@S@ .caption--provisional {',
            '  background: color-mix(in srgb, var(--accent) 9%, transparent);',
            '  border-color: color-mix(in srgb, var(--accent) 20%, transparent);',
            '  border-radius: 16px 16px 5px 16px;',
            '}',
            '@S@ .caption--provisional .caption__led {',
            '  background: var(--accent);',
            '  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 15%, transparent);',
            '}',
        ],
        'editorial_rule': False,
    },
    {
        'id': 'ember',
        'label': 'Ember',
        'group': 'abc-editorial', 'variant': 'B',
        'swatch': '#F08A4B',
        'variant_name': 'editorial',
        'panel': 'chips',
        'size_max': 32, 'weight': '400', 'leading': '1.38', 'tracking': '-0.01em',
        'italic': False, 'align': 'left', 'caret': False, 'word_soft': True,
        'caption_font': 'fraunces', 'panel_font': 'inter',
        'caption_color': '#FFE4CE', 'caption_dim': 'rgba(255,228,206,0.3)',
        'caption_accent': '#F08A4B',
        'caption_shadow': '0 2px 22px rgba(20,6,1,0.92), 0 1px 2px rgba(0,0,0,0.7)',
        'panel_text': '#F6E0D2', 'panel_muted': 'rgba(246,224,210,0.46)',
        'border': 'rgba(255,196,150,0.12)', 'surface': 'rgba(24,14,11,0.66)',
        'soft': 'rgba(240,138,75,0.08)',
        'radius': 14, 'blur': 16,
        'panel_shadow': '0 30px 80px -30px rgba(0,0,0,0.88)',
        'overlay': 'radial-gradient(110% 80% at 50% 88%, rgba(196,84,26,0.34) 0%, '
                   'rgba(30,14,9,0.6) 52%, rgba(10,6,5,0.92) 100%)',
        'scrim': 'rgba(10,6,5,0.92)',
        'photo': 'backdrops/ember.jpg',
        'reveal_anim': 'cine-c1-word-soft 520ms cubic-bezier(0.22, 0.68, 0.2, 1) both',
        'note': [
            '`chips` is four-turn chapter blocks: each row radius `max(12, 14 - 6)`',
            '= 8, the live row filled `${p.accent}12` (7%), bordered `${p.accent}2e`',
            '(18%) with a `2px` accent left edge, and a `${p.accent}40` divider',
            '(`PanelSetB.tsx:337-441`). Its `chapter NN` label and always-visible',
            'search pill are panel chrome our caption box has no element for.',
            '`editorial`: left-aligned, with the zip\'s 32px rule above the words.',
        ],
        'plate_lead': 'the design\'s chip surface (surface + blur 16).',
        'plate_note': [
            'The scene\'s overlay is radial and rises from the BOTTOM (50% 88%), the',
            'hottest stop of any scene in the zip (`rgba(196,84,26,0.34)`), copied',
            'verbatim.',
        ],
        'plate': ['background: var(--bg-slab);',
                  'border: 1px solid var(--line);',
                  'border-radius: %dpx;' % 14,
                  'backdrop-filter: blur(%dpx);' % 16,
                  '-webkit-backdrop-filter: blur(%dpx);' % 16,
                  'box-shadow: var(--shadow-slab);'],
        'bar': ['justify-content: space-between;', 'border: 0;',
                'background: none;', 'padding: 0 0 4px;'],
        'list_lead': 'the design\'s stage inset, one chapter chip per line',
        'list_note': ['(`maxWidth: 720`, editorial\'s flush-left column).'],
        'list': ['padding: 10px 20px 12px;', 'gap: 8px;'],
        'row_lead': 'a chapter chip, radius 8, transparent until it is the live one',
        'row': ['grid-template-columns: 1fr;', 'gap: 3px;', 'padding: 9px 11px;',
                'text-align: left;', 'background: transparent;',
                'border: 1px solid transparent;',
                'border-left: 2px solid transparent;', 'border-radius: 8px;'],
        'led_what': 'no per-row dot (this variant\'s marker is the 2px left edge)',
        'led': None,
        'time': ['color: var(--text-secondary);', 'font-family: var(--font-mono);',
                 'font-size: 9px;', 'letter-spacing: 0.24em;',
                 'font-variant-numeric: tabular-nums;', 'text-align: left;'],
        'live_rules': [
            '/* THE LIVE ROW — `PanelSetB.tsx:387-389`: `background: p.soft`,',
            ' * `borderLeft: 2px solid p.accent`. The scene\'s own chip fill is',
            ' * `${p.accent}12` (7%) over its `${p.accent}2e` border. */',
            '@S@ .caption--provisional {',
            '  background: color-mix(in srgb, var(--accent) 7%, transparent);',
            '  border-color: color-mix(in srgb, var(--accent) 18%, transparent);',
            '  border-left: 2px solid var(--accent);',
            '}',
        ],
        'editorial_rule': True,
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


# `variant` above is the A/B/C LETTER the plan's §3 groups assign; the caption
# variant (`wide`/`tight`/`italic`/`editorial`) is `variant_name` inside `_RAW`,
# because the generator's manifest field is the letter and nothing else.
THEMES = [_theme(d) for d in _RAW]


def _check():
    """Fail at IMPORT, before the generator`s own self-check, on the two things this
    file can get wrong silently: a token the contract needs and this file forgot,
    and a swatch that is not the accent the CSS paints."""
    for t in THEMES:
        miss = [k for k in _G.REQUIRED if k not in t['tokens']]
        if miss:
            raise SystemExit('%s misses tokens: %s' % (t['id'], ', '.join(miss)))
        if t['swatch'] != t['tokens']['--accent']:
            raise SystemExit('%s: swatch %s != --accent %s'
                             % (t['id'], t['swatch'], t['tokens']['--accent']))
        if t['id'].startswith(_G.PREFIX):
            raise SystemExit('%s carries the generator`s own prefix' % t['id'])


_check()
