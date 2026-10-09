#!/usr/bin/env python3
"""GENERATOR for the five Sotto theme files — `app/panel/themes/theme-N.css`.

The five mockups differ in COLOUR, TYPE and SURFACE, but they must obey ONE
contract (the owner's, verbatim): every rule scoped to its own
`:root[data-theme='theme-N']`, so five files coexist in one document and a switch
is one attribute write. Writing the shared half — the scoped skin rules over the
REAL class names in `app/panel/panel.html` — once is what makes that true by
construction instead of by five authors agreeing.

Each generated rule is emitted as `:root[data-theme='theme-N'] <selector>` or
`:root[data-theme='theme-N'] body <selector>`. Two attribute selectors plus the
element beat `panel.css`'s own `.caption--provisional .caption__text`
(specificity 0,1,0) and `body[data-surface='strip'] .caption__text` (0,2,0), so a
theme never loses a fight it cannot see.

Run: `py -3 _main/_design-lane/gen_themes.py`  (regenerates all five, byte-stable)
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir, 'app', 'panel', 'themes'))

# --------------------------------------------------------------------------- #
# The FIVE themes ARE the owner's five design DIRECTIONS, one per theme number,
# so the names the panel shows ("Teleprompter", "Broadcast", …) are the names of
# the directions and the number IS the order of `docs/design/gpt-directions.md`
# and of `H:\aireplay\docs\design\sotto-app-design-directions\src\data\designs.ts`:
#
#   theme-1  tele  Teleprompter    accent #f2e9d8  Barlow Condensed
#   theme-2  bcast Broadcast       accent #ff6a55  IBM Plex Mono
#   theme-3  mano  Manuscrito      accent #a9c1d9  Newsreader
#   theme-4  cine  Cinema Card     accent #e4b363  Fraunces
#   theme-5  inst  Instrumento     accent #5fd3a7  Space Grotesk
#
# THE ACCENTS ARE THE DIRECTIONS' OWN, taken verbatim from `designs.ts`
# (`accent:` of each entry). The slabs and the text tiers are the previous lane's
# mockup measurements, still valid: the direction files fix the ACCENT, the type
# and the treatment of the line, not the darkness of the slab. Where the two
# disagreed the direction wins, because it is the owner's brief and the mockups
# are one reading of it.
#
# THE FIVE FAMILIES ARE BUNDLED, not hoped for: `app/panel/fonts/` holds the
# latin `.woff2` subsets (13 files, 217.6 KB — the count and the size are stated
# in `themes/fonts.css`, which is the file that links them; an earlier comment
# here said "17 files, ~400 KB" and was simply wrong) and `app/panel/themes/
# generated next to this file by `build_fonts.py`. On this box none of the five
# names exists in `C:\Windows\Fonts`, so a `font-family: "Barlow Condensed"`
# without the bundle would have painted a system fallback and the theme would
# have been a colour change pretending to be a design.
# --------------------------------------------------------------------------- #

THEMES = [
    dict(
        n=1,
        name='Teleprompter',
        idea='THE DIRECTION `tele`: the caption as a continuous reading flow. '
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
        slab='#0D1013', slab_strong='#12171C',
        text_primary='#FFFFFF',
        text_confirmed='#F2E9D8',
        text_provisional='#8FA6C0',
        text_secondary='#A9B7C6',
        text_muted='#7E8B99',
        line='rgba(242, 233, 216, 0.16)', line_strong='rgba(242, 233, 216, 0.34)',
        accent='#F2E9D8', accent_soft='rgba(242, 233, 216, 0.12)',
        ok='#6EF184', busy='#F2E9D8', error='#F87171', idle='#5B6472',
        radius_sm='7px', radius_md='12px', radius_lg='18px',
        space=(4, 8, 13, 20, 30),
        font_sans='"Barlow Condensed", "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif',
        font_mono='"Cascadia Mono", ui-monospace, Consolas, monospace',
        size_caption='30px', size_closed='18px', size_time='10px', size_chrome='11.5px',
        size_meta='10.5px', size_small='12.5px',
        leading_caption='1.06', leading_closed='1.24',
        weight_caption='700', weight_closed='400', weight_brand='700',
        tracking_caption='0.006em', tracking_brand='0.42em',
        # THE NAME IS LOWERCASE IN EVERY DIRECTION (owner, 2026-10-08: *"bota o nome
        # 'sotto' em todos os temas"*, written lowercase by him). This direction's
        # wordmark is where theme-1's name lives, and `uppercase` here would render
        # the markup's `sotto` as `SOTTO` — the one property that silently overrules
        # the owner's own spelling. `caption_upper` is a different decision and stays.
        brand_upper='none', caption_upper='uppercase',
        slab_opacity='0.97',
        radius_dialog='16px',
        shadow_slab=('0 30px 70px -28px rgba(0, 0, 0, 0.78), '
                     '0 0 0 1px rgba(242, 233, 216, 0.04)'),
        caption_color='var(--text-primary)',
        closed_color='var(--text-secondary)',
        prov_rail_w='0px',
        prov_rail_style='none',
        prov_pad='var(--space-3)',
        # CHANGED 2026-10-07 (lane painel-cinco-direcoes). It was `2px`, which
        # gave the NEWEST CLOSED line (`.caption--latest` -- panel.js puts it on
        # the freshest settled row) a near-white rail. That contradicts this
        # entry's own `idea` a few lines up ("no rail on the closed ones",
        # "nothing is boxed"), and it is what made the five-design probe call
        # theme-1 RED: a settled line wearing the live line's own mark reads as
        # still live. "Only the now shines" is now carried by SIZE + HUE + the
        # static halo alone.
        closed_rail_w='0px',
  time_live='#FFD24A',
        # "a linha viva brilha" -- brilho, never a keyframe. Static on purpose:
        # rule 4 of every theme file is "the caption text is never animated".
        live_shadow='0 0 18px rgba(242, 233, 216, 0.30), 0 0 2px rgba(242, 233, 216, 0.55)',
        cap_align='left',
    ),
    dict(
        n=2,
        name='Broadcast',
        idea='THE DIRECTION `bcast`: a transmission happening right now. IBM Plex '
             'Mono, timecodes and small state marks, accent #ff6a55. The forming '
             'line carries a SOLID 2 px signal-red rail and the most recent word is '
             'bright amber; a closed line has NO rail at all and falls to a neutral '
             'grey, so "being said" and "was said" are told apart by SHAPE before '
             'by hue — which is the direction\'s own recommendation ("instrumentation '
             'extremely subtle, never a dashboard").',
        slab='#0E1011', slab_strong='#131617',
        text_primary='#FFFFFF',
        text_confirmed='#FFFFFF',
        text_provisional='#9A9384',
        text_secondary='#BFC0C2',
        text_muted='#8A8C8E',
        line='rgba(255, 106, 85, 0.22)', line_strong='rgba(255, 106, 85, 0.44)',
        accent='#FF6A55', accent_soft='rgba(255, 106, 85, 0.16)',
        ok='#F0D090', busy='#B9985A', error='#FF8A7A', idle='#5F6265',
        radius_sm='4px', radius_md='5px', radius_lg='8px',
        space=(3, 6, 10, 15, 22),
        font_sans='"IBM Plex Mono", "Cascadia Mono", Consolas, ui-monospace, monospace',
        font_mono='"IBM Plex Mono", "Cascadia Mono", Consolas, ui-monospace, monospace',
        size_caption='20px', size_closed='15px', size_time='11px', size_chrome='10.5px',
        size_meta='10px', size_small='11.5px',
        leading_caption='1.38', leading_closed='1.35',
        weight_caption='600', weight_closed='400', weight_brand='700',
        tracking_caption='0.01em', tracking_brand='0.24em',
        brand_upper='uppercase', caption_upper='none',
        slab_opacity='0.99',
        radius_dialog='6px',
        shadow_slab=('0 26px 60px -26px rgba(0, 0, 0, 0.8), '
                     '0 0 0 1px rgba(255, 106, 85, 0.07)'),
        caption_color='var(--text-primary)',
        closed_color='var(--text-secondary)',
        caption_family='var(--font-mono)',
        closed_family='var(--font-mono)',
        time_family='var(--font-mono)',
        caption_tabular='tabular-nums',
        prov_rail_w='2px',
        prov_rail_style='solid',
        closed_rail_w='0px',
  time_live='#FFD24A',
    ),
    dict(
        n=3,
        name='Manuscrito',
        idea='THE DIRECTION `mano`: the caption is born in front of you. Newsreader '
             '— a serif — at the caption, accent #a9c1d9, so provisional text never '
             'reads as an error and history never reads as a broadcast. The forming '
             'line is a DRAFT: it carries a thin SOLID guide rail and its tail still '
             'in doubt is held back in ink grey while the words already confirmed '
             'inside it stand brighter. A closed line is settled text — no rail, '
             'plain weight — so what is provisional reads as unfinished, never as '
             'unreliable.',
        slab='#0F1216', slab_strong='#141922',
        text_primary='#F4F7FA',
        text_confirmed='#DCE4ED',
        text_provisional='#97A3B0',
        text_secondary='#AEB8C4',
        text_muted='#7F8A97',
        line='rgba(169, 193, 217, 0.16)', line_strong='rgba(169, 193, 217, 0.36)',
        accent='#A9C1D9', accent_soft='rgba(169, 193, 217, 0.12)',
        ok='#58E8B5', busy='#7FD6C2', error='#FF9B8A', idle='#5D6673',
        radius_sm='6px', radius_md='10px', radius_lg='14px',
        space=(5, 9, 14, 21, 30),
        font_sans='"Newsreader", "Segoe UI Variable Text", "Segoe UI", Georgia, serif',
        font_mono='"Cascadia Mono", Consolas, ui-monospace, monospace',
        size_caption='23px', size_closed='17px', size_time='10px', size_chrome='11px',
        size_meta='10px', size_small='12px',
        leading_caption='1.62', leading_closed='1.45',
        weight_caption='400', weight_closed='400', weight_brand='600',
        tracking_caption='0.002em', tracking_brand='0.14em',
        brand_upper='none', caption_upper='none',
        slab_opacity='0.96',
        radius_dialog='12px',
        shadow_slab=('0 28px 64px -28px rgba(0, 0, 0, 0.76), '
                     '0 0 0 1px rgba(169, 193, 217, 0.05)'),
        caption_color='var(--text-primary)',
        closed_color='var(--text-secondary)',
        prov_rail_w='2px',
        prov_rail_style='solid',
        closed_rail_w='0px',
  time_live='#FFD24A',
    ),
    dict(
        n=4,
        name='Cinema Card',
        idea='THE DIRECTION `cine`: minimal editorial presence, accent #e4b363. '
             'Fraunces, wide leading, and the direction\'s own mark on the state: '
             'the forming line is ITALIC and sits behind a warm gold rail, while the '
             'closed line is upright and solid — "the finished phrase is solid, the '
             'one in progress lives in the mist" (the direction\'s words). The gold '
             'is warm and low-contrast on purpose: this is the theme that can almost '
             'disappear over the film.',
        slab='#14110F', slab_strong='#1A1613',
        text_primary='#F6F0E6',
        text_confirmed='#E4DACB',
        text_provisional='#B6A794',
        text_secondary='#D2C6B4',
        text_muted='#A4947F',
        line='rgba(228, 179, 99, 0.20)', line_strong='rgba(228, 179, 99, 0.42)',
        accent='#E4B363', accent_soft='rgba(228, 179, 99, 0.16)',
        ok='#9BD9A0', busy='#E4B363', error='#FF9E86', idle='#776A5C',
        radius_sm='8px', radius_md='13px', radius_lg='20px',
        space=(5, 10, 15, 23, 33),
        font_sans='"Fraunces", "Segoe UI Variable Display", "Segoe UI", Georgia, serif',
        font_mono='"Cascadia Mono", Consolas, ui-monospace, monospace',
        size_caption='24px', size_closed='18px', size_time='10px', size_chrome='11.5px',
        size_meta='10.5px', size_small='12.5px',
        leading_caption='1.52', leading_closed='1.42',
        weight_caption='400', weight_closed='400', weight_brand='600',
        tracking_caption='0.012em', tracking_brand='0.34em',
        brand_upper='uppercase', caption_upper='none',
        slab_opacity='0.97',
        radius_dialog='16px',
        shadow_slab=('0 32px 76px -30px rgba(0, 0, 0, 0.82), '
                     '0 0 0 1px rgba(228, 179, 99, 0.06)'),
        caption_color='var(--text-primary)',
        closed_color='var(--text-secondary)',
        prov_style='italic',
        prov_rail_w='2px',
        prov_rail_style='solid',
        closed_rail_w='0px',
        time_live='var(--accent)',
    ),
    dict(
        n=5,
        name='Instrumento',
        idea='THE DIRECTION `inst`: it is ON, it is not an open window. Space '
             'Grotesk, accent #5fd3a7, and the direction\'s own dynamic element — '
             'the FORMING line carries a continuous 4 px LED rail on its left, the '
             'one thing that moves in this theme; closed lines are a settled column '
             'of readings behind a small square mark with no rail at all. Nothing '
             'else is decorated, which is the point: after a week the LED says '
             'everything without being read.',
        slab='#0A0C0D', slab_strong='#0F1214',
        text_primary='#FFFFFF',
        text_confirmed='#F2F5F8',
        text_provisional='#9BA3AC',
        text_secondary='#9BA3AC',
        text_muted='#7F8A97',  # 2026-10-08 audit: was #757C85 (4.45:1, the panel's only AA fail)
        line='rgba(95, 211, 167, 0.16)', line_strong='rgba(95, 211, 167, 0.38)',
        accent='#5FD3A7', accent_soft='rgba(95, 211, 167, 0.12)',
        ok='#5FD3A7', busy='#C9D0D8', error='#FF8F8F', idle='#4E555C',
        radius_sm='5px', radius_md='8px', radius_lg='12px',
        space=(4, 8, 12, 19, 28),
        font_sans='"Space Grotesk", "Segoe UI Variable Text", "Segoe UI", Inter, system-ui, sans-serif',
        font_mono='"Cascadia Mono", Consolas, ui-monospace, monospace',
        size_caption='24px', size_closed='17px', size_time='10px', size_chrome='11px',
        size_meta='10px', size_small='12px',
        leading_caption='1.30', leading_closed='1.30',
        weight_caption='700', weight_closed='400', weight_brand='700',
        tracking_caption='0.004em', tracking_brand='0.30em',
        brand_upper='uppercase', caption_upper='none',
        slab_opacity='0.99',
        radius_dialog='10px',
        shadow_slab=('0 30px 68px -30px rgba(0, 0, 0, 0.84), '
                     '0 0 0 1px rgba(95, 211, 167, 0.05)'),
        caption_color='var(--text-primary)',
        closed_color='var(--text-secondary)',
        prov_rail_w='4px',
        prov_rail_style='solid',
        closed_rail_w='0px',
  time_live='#FFD24A',
    ),
]

# The PRE-DIRECTION theme tables (the mockup-derived Teleprompter/Broadcast/
# Manuscrito/Cinema/Instrumento values, accents included) are NOT kept here as a
# second dead list: they were the same thirty-odd keys spelled a second time, so a
# reader could not tell which list the files came from. The change is in this
# file's own history — `git -C H:\\sotto log -p -- _main/_design-lane/gen_themes.py` —
# and a second copy of the old numbers would only rot. What the files ARE is
# below, in THEMES, and `build_fonts.py` in this same directory explains the fonts.
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
{S} .icon-button,
{S} .history__toggle,
{S} .strip-button{{
  border-color: var(--line);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
}}
{S} .icon-button:hover,
{S} .history__toggle:hover,
{S} .strip-button:hover{{
  border-color: var(--line-strong);
  background: var(--accent-soft);
  color: var(--text-primary);
}}
{S} .icon-button:focus-visible,
{S} .history__toggle:focus-visible,
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
{S} .history__label{{
  color: var(--text-muted);
  letter-spacing: 0.14em;
  font-size: var(--size-chrome);
}}
{S} .captions__hint{{ color: var(--text-muted); }}
{S} .captions__body{{
  border-color: var(--line);
  border-radius: var(--radius-md);
  background: color-mix(in srgb, var(--bg-slab-strong) 55%, transparent);
  box-shadow: none;
  scrollbar-color: var(--line-strong) transparent;
}}
{S} .captions__body::-webkit-scrollbar-thumb{{ background: var(--line-strong); border-radius: 99px; }}
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
   * Card theme puts `italic` back on the forming line only, by parameter.
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
{B} .caption--provisional .caption__text{{ color: {confirmed_color}; {cap_family_decl} text-shadow: {live_shadow}; }}
/* …and the tail that may still be rewritten. panel.css also sets it italic. */
{B} .caption--provisional .caption__provisional{{
  color: var(--text-provisional);
  font-style: {prov_style};
  {prov_extra}
}}
{B} .caption__time{{
  color: var(--text-muted);
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

/* ── the footer, where Alt+C is announced ────────────────────────────────── */
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
{S} .status__hint{{ color: var(--text-muted); }}
{S} kbd{{
  border-color: var(--line-strong);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--text-secondary);
  font-family: var(--font-mono);
}}

/* ── the transcript drawer: SECONDARY, and it must know how to be quiet ───── */
{S} .history{{ border-top-color: var(--line); }}
{S} .history__note,
{S} .history__count,
{S} .history__source{{ color: var(--text-muted); }}
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
{S} .reveal-button--danger,
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
 * MEASURED FROM: `docs/design/incoming/design-{n}.png`
 *   slab    {slab}   (median of the quiet dark rows inside the panel region)
 *   accent  {accent}   (median of the bright chromatic pixels in that region)
 *   text    {text_primary} / {text_secondary} / {text_muted}  (the three measured tiers)
 * The caption ratios, computed against the slab, are in
 * `_main/receipt-panel-themes.md`.
 */

:root[data-theme='theme-{n}']{{
  /* ── SURFACE ──────────────────────────────────────────────────────────── */
  --bg-slab: {slab};
  --bg-slab-strong: {slab_strong};
  --slab-opacity: {slab_opacity};
  --shadow-slab: {shadow_slab};

  /* ── TEXT ─────────────────────────────────────────────────────────────── */
  --text-primary: {text_primary};
  --text-confirmed: {text_confirmed};
  --text-provisional: {text_provisional};
  --text-secondary: {text_secondary};
  --text-muted: {text_muted};

  /* ── LINES AND ACCENT ─────────────────────────────────────────────────── */
  --line: {line};
  --line-strong: {line_strong};
  --accent: {accent};
  --accent-soft: {accent_soft};
  /* The theme button paints its own swatch from this, so a theme's accent is
     declared in exactly one place. */
  --theme-swatch: {accent};

  /* ── STATE: colour carries information here, never decoration ─────────── */
  --ok: {ok};
  --busy: {busy};
  --error: {error};
  --idle: {idle};

  /* ── SHAPE ────────────────────────────────────────────────────────────── */
  --radius-sm: {radius_sm};
  --radius-md: {radius_md};
  --radius-lg: {radius_lg};
  --radius-dialog: {radius_dialog};

  /* ── SPACE ────────────────────────────────────────────────────────────── */
  --space-1: {s1}px;
  --space-2: {s2}px;
  --space-3: {s3}px;
  --space-4: {s4}px;
  --space-5: {s5}px;

  /* ── TYPE ─────────────────────────────────────────────────────────────── */
  --font-sans: {font_sans};
  --font-mono: {font_mono};
  --font-caption: {font_caption};
  --font-closed: {font_closed};
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
:root[data-theme='theme-{n}']{{
  --bg: var(--bg-slab);
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
@S@ .chrome--tele[data-chrome="foot"]{
  display: inline-flex;
  flex: none;
  font-family: var(--font-sans);
  font-size: 10px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  color: var(--text-muted);
}
@S@ .chrome--tele[data-chrome="foot"][data-slot="start"]{ order: -1; }
@S@ .chrome--tele[data-chrome="foot"][data-slot="end"]{ order: 9; color: var(--accent); }
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
  font-size: 9px;
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
  font-size: 11px;
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
  font-size: 12px;
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
@S@ .chrome--inst .chrome__key{
  margin-left: auto;
  font-size: 9px;
  font-weight: 400;
  letter-spacing: 0.22em;
  color: var(--text-muted);
}
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
ROOT = ":root[data-theme='theme-%s']"

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
                one = one.strip()
                if not one:
                    continue
                one = one[3:] if one.startswith('@S@') else one
                one = one[3:] if one.startswith('@B@') else one
                one = one.strip()
                if one:
                    parts.append('%s %s' % (scope, one))
            if not parts:
                continue
            out.append('%s%s {' % (indent, (',\n' + indent).join(parts)))
            for d in payload:
                out.append('%s  %s;' % (indent, ' '.join(d.split())))
            out.append('%s}' % indent)

    emit(nodes)
    return '\n'.join(out)


def build(t):
    skin = SKIN.format(
        S="@S@", B="@B@",
        slab_pct=int(round(float(t['slab_opacity']) * 100)),
        brand_size="12px" if t['n'] in (2, 5) else "13px",
        cap_pad_y="7px" if t['n'] != 3 else "9px",
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
        n=t['n'], name=t['name'], idea=t['idea'],
        slab=t['slab'], accent=t['accent'], text_primary=t['text_primary'],
        text_secondary=t['text_secondary'], text_muted=t['text_muted'],
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
    return (head + scope(skin, t['n']) + "\n"
            + scope(CHROME[t['n']], t['n']) + "\n"
            + scope(STRIP_GUARD, t['n']) + "\n"
            + scope(MOTION, t['n']) + "\n")

def main():
    os.makedirs(OUT, exist_ok=True)
    for t in THEMES:
        path = os.path.join(OUT, 'theme-%d.css' % t['n'])
        text = build(t)
        # CRLF, NOT LF, and that is measured rather than a preference. The five
        # files on disk in `app/panel/themes/` are 100 % CRLF (theme-1: 633 CRLF /
        # 0 bare LF, and the same N/N for all five), and `core.autocrlf=true`, so
        # CRLF is this working tree's convention. Writing LF here would rewrite
        # every line of every theme on the next generation run — a whole-file diff
        # that buries the one line someone meant to change. Verified before the
        # change: with `newline='\n'` the output was byte-identical to disk
        # EXCEPT for exactly +1 byte per line.
        with open(path, 'w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(text)
        print('wrote %-46s %6d bytes  %4d lines' % (path, len(text.encode('utf-8')),
                                                   text.count('\n')))


if __name__ == '__main__':
    main()
