# Receipt — LANE B: as mudancas de interface (2026-10-14)

Lane: interface (B). Owner-direct, not diagnostics: everything below is a change the owner
asked for in his own words. Files owned and touched: `app/panel/panel.html`,
`app/panel/panel.css`, `app/panel/panel.js` — plus the GENERATORS that write the theme CSS
(`_main/_design-lane/gen_themes.py`, `gen_cinematic.py`, `gen_zipc.py`, `cine_extra_c1.py`,
`cine_extra_c2.py`), because AGENTS.md rule 10 forbids hand-editing a generated file, and the
three oracles whose expectation tables named the removed controls.

NOTHING WAS LAUNCHED. No app, no shell, no worker, no WebView2, no browser. Every
measurement here is bytes, parse, an offline JPEG decode, or an in-process gate.
`$env:TMPDIR = I:/cc-tmp` was set for every tool run.

## The owner's order (verbatim, 2026-10-14)

> *"alt c nao aperta direito em diversos caso. arruma agora. abrir ou fechar o sotto causa
> travamento no meu pc. arruma. sotto ta reclamando de coisa nao carregada, com erro
> vermelho. arruma. tira em curso e historico das barras. tira o botao de transcript. os
> botoes sao botoes simples e pequenos porem visiveis o suficiente pro usuario. e nao e pra
> ter tema branco."*

This lane took the LAST FOUR clauses (B1–B4). The first three clauses are the functional
lane's; the context already measured by this session is not re-measured here.

---

## B1 — "em curso" and "historico" are OUT of the bars

**Where they were.** Exactly one place in the whole panel painted those two words, and the
census that found them was a literal grep over `app/panel/**` for `EM CURSO|HIST[OÓ]RICO`
(case-insensitive): 6 hits in prose comments, and **2 in painted markup** — the Teleprompter
direction's own footer chrome, in `panel.html`:

```html
<span class="chrome chrome--tele" data-chrome="foot" data-slot="start">HISTÓRICO</span>
<span class="chrome chrome--tele" data-chrome="foot" data-slot="end">▲ EM CURSO</span>
```

The strip bar was checked too, not assumed: `#strip-word` is painted by
`panel.js paintStripState` and the string `EM CURSO` appears **nowhere** in `panel.js`
(0 matches), so the bottom bar never carried the label.

**What was removed.**

1. Both `<span>`s deleted from `panel.html`. The comment above them now records the removal.
2. The three generated rules that styled them —
   `:root[data-theme='theme-1'] .chrome--tele[data-chrome="foot"]` and its two
   `data-slot` members, in `theme-1.css` **and** `panel-designs.css` — deleted from
   `gen_themes.py` (the `CHROME[1]` template) and the two files regenerated. A rule about a
   node that no longer exists is a rule about nothing, and the panel file's own convention
   is to delete it rather than leave it looking live.

**What the bar keeps.** The REAL status sentence: `#status-dot` and `#status-text`, which carry
the worker's own cause. The footer is CLEAN, not empty.

**What was lost, and why nothing was.** Both spans were INERT chrome: no code read either
node (`panel.js` never queried either id, no handler was bound). The only readers anywhere were
the expectation tables of `_main/_panel-chrome-arm.py` and `_main/_panel-chrome-probe.js`,
re-baselined below. The OTHER directions keep their own footer chrome (`bcast`'s meter and
LIVE/EM ESPERA, `mano`'s "— escrito ao ouvido", `cine`'s "· · ·", `inst`'s meter and
OUVINDO/EM ESPERA) — the owner named `em curso` and `historico` and nothing else.

---

## B2 — the transcript button is OUT, the drawer stays BEHIND

**What was removed.** The drawer handle: `#history-toggle`, the chevron `<button>` that
expanded and collapsed the transcript section, and the ONLY control that could open the
drawer by hand. Deleted from `panel.html` (a measured note sits where it was).

**What stays.**

* the section itself, `.history#history`, still `history--collapsed`;
* the CSS-only hide on `.history__body` — its rows stay in the DOM, so a read-back probe
  that counts `#history-list .hist` still sees them;
* the label and the FOLDER button `#history-root` (the folder is where the data lives and the
  owner kept that affordance himself on 2026-10-08: the PATH went, the button stayed);
* the automatic half: `panel.js isTranscriptExpanded()` is unchanged, so the drawer still
  opens BY ITSELF the day the shell reports a canonical producer. Nobody can open it by hand
  any more, which is the point.

**The code that went with the control** (dead by the markup change, deleted rather than left
pointing at nothing):

* `panel.js` — `transcriptToggle: document.getElementById('history-toggle')` in the dom
  table; the click handler in `wireHistory` that flipped `transcriptExpanded`; the
  `if (dom.transcriptToggle)` branch in `applyTranscriptMode` that set `aria-expanded` and
  the title. Every one of them was already NULL-CHECKED, so removing the markup could not
  throw — which is what made the deletion safe to do without a launch.
* `panel.css` — the six `.history__toggle` rules (the 22 px chevron, its 14 px glyph, the
  90° rotation while open, the hover tint, the focus ring).
* `gen_themes.py` — the `.history__toggle` member of the three generated button groups
  (base, `:hover`, `:focus-visible`); all five `theme-N.css` and `panel-designs.css`
  regenerated. No panel stylesheet contains the string `history__toggle` any more (measured:
  0 matches across every `.css` under `app/panel`).

`node --check app/panel/panel.js` passes after the edit; `panel.html` is well-formed
(stack-based tag check: every open tag matched, comments balanced 62/62).

---

## B3 — the buttons: SIMPLE, SMALL, and VISIBLE ENOUGH

**Measured before anything was changed.** The instrument was a small compositing script over
the shipped bytes: each rule's colour, the theme's own tokens, WCAG 2.x relative luminance
and contrast. Two numbers came out, and they are different questions:

| surface | control | GLYPH vs its background | EDGE vs the bar/panel |
|---|---|---|---|
| strip | `.strip-button` (26 px circle, 13 px glyph) | **12.94 : 1** (dark themes) | **1.71 : 1** |
| strip | the six light themes (see B4) | **1.04 – 1.14 : 1** | 1.71 : 1 |
| panel | `.icon-button` (28 px, 16 px glyph) | 10.9 – 16 : 1 | **1.0 : 1 — NO EDGE AT ALL** |

So the glyph was already readable in the 39 dark themes and INVISIBLE in the six white
ones, and the panel controls had **no boundary at all**: `border: 1px solid transparent`
and an 8 % fill, i.e. a glyph floating with no box. 30 of the 45 themes (every `cine-*` and
every `zipc-*`) do not restyle `.icon-button`, so the base rule in `panel.css` IS what they
paint — measured, not assumed.

**What changed. Three edits, no new design, no size change.**

1. `panel.css` `.icon-button`: `border: 1px solid transparent` →
   `1px solid rgba(148, 163, 184, 0.34)` — the same slate family the rule already used for its
   fill. Measured: the edge goes **1.0 : 1 → 1.89 : 1** on the dark slab. It is a hairline,
   not a frame: 0.50 alpha reaches only 2.71 : 1, so a 3 : 1 edge would mean a chunky border
   nobody asked for.
2. `panel.css` `.icon-button`: `background` `0.08` → `0.12`. The resting fill now reads as a
   surface instead of a stain; the hover still steps up from it.
3. `panel.css` `body[data-surface="strip"] .strip-button svg`: `13px` → `14px`. The CIRCLE
   does not grow (26 px, the size the strip window is handed); only the glyph does, because a
   13 px stroke on a dark bar was the thin end of "visible enough".
4. `gen_themes.py` (the `SKIN` group shared by the ten `theme-N`/`pd-*` directions): the
   resting `border-color` moves from `var(--line)` (the FAINT tier, measured 1.18 – 1.51 : 1)
   to `var(--line-strong)` — the tier this very file already used for the `:hover` state. The
   resting edge now borrows the number the hover proved instead of inventing one:
   1.99 : 1 (theme-1) to 2.80 : 1 (theme-3).

**What was deliberately NOT touched.**

* The strip button's fill and border alphas (`rgba(148,163,184,0.16)` / `0.30`). They are
  PINNED, deliberately, by `_main/strip-float-oracle.js` arms S6/S7 — the pair the owner asked
  for himself on 2026-10-12 (*"os botoes tem que ser mais claros"*). This lane did not
  re-baseline them; both oracles are green as shipped.
* Every size: 28 px panel icons, 26 px strip circles, `--strip-height: 40px`. The owner asked
  for SMALL; nothing here makes a button bigger.
* `theme-1`'s own "nothing is boxed" control chrome (`.panel__controls .icon-button {
  border-color: transparent; background: transparent }`) — that is the direction's own
  design decision and it outranks the shared rule on specificity.

**The two together.** B3 fixed the edge; B4 fixed the glyph. The strip glyph contrast in the
six ex-light themes went **1.04 – 1.14 : 1 → 12.44 – 13.06 : 1**:

| theme | glyph before | glyph after |
|---|---|---|
| cine-paper-moon | 1.14 : 1 | 12.94 : 1 |
| cine-fieldnotes | 1.04 : 1 | 13.06 : 1 |
| cine-dustlight | 1.04 : 1 | 12.95 : 1 |
| cine-linen | 1.06 : 1 | 12.84 : 1 |
| Paper (zipc) | 1.04 : 1 | 12.44 : 1 |
| Gutter (zipc) | 1.07 : 1 | 12.49 : 1 |

---

## B4 — no white theme: the census, then the fix

### The instrument (new: `_main/theme-lightness-census.py`)

Written first, run BEFORE any change, and it is the proof the owner asked for
(*"faz o censo: percorre os CSS dos temas, mede a luminosidade do fundo de cada um, e lista
quais sao claros"*). It reads only bytes — no browser, no shell, no worker — and for each of
the **45** themes the picker offers (the registry is read out of the three manifests:
`themes/themes.js`, `themes/panel-designs.js`, `themes/zipc-panels.js`, cross-checked against
the CSS scopes: 5 `theme-N` + 25 `cine-*` + 5 `pd-*` + 10 `zipc`) it:

1. reads the theme's own token block and its own `.panel` rule;
2. rebuilds the PAINTED background the way CSS composites it — every `background-image`
   layer in CSS order (first is the TOP one), then `background-color`, then the shell's own
   opaque form colour `rgba(11,15,20,0.98)` for the translucent layers — and for a `cine-*`
   theme that includes the bundled backdrop PHOTOGRAPH, decoded offline with Pillow, and the
   scrim gradients painted over it, because the photograph is most of what the eye sees;
3. reports the WCAG 2.x relative luminance of that colour, the verdict against the 0.5
   threshold — the SAME threshold `gen_cinematic.py panel_is_light()` already uses to choose
   `color-scheme` — and the contrast of the theme's own caption ink, body ink and dim ink
   against it.

`py -3 _main/theme-lightness-census.py [--light] [--gate]`. `--gate` exits 1 when ANY theme
is still light, so the instrument can say NO as well as list.

**One bug the instrument caught in itself, recorded because it changed the answer:** the
first version composited the layers bottom-up from a list built top-first, so it painted the
photograph OVER its own scrim and reported `cine-paper-moon` as `#5f6062`. Fixed to CSS
order, it reports `#e6e7e4` — and the corrected number is what showed that three of the six
"light" themes were actually painting DARK with DARK ink (see below).

### The census BEFORE (the proof of the white)

45 themes measured, **6 LIGHT** (luminance ≥ 0.5):

| theme | painted background | luminance | body ink | caption ink |
|---|---|---|---|---|
| cine-paper-moon | #e6e7e4 | 0.7978 | 13.92 : 1 | **1.14 : 1** |
| cine-fieldnotes | #ece9e1 | 0.8148 | 12.02 : 1 | **1.07 : 1** |
| cine-dustlight | #f6ede1 | 0.8560 | 12.54 : 1 | **1.03 : 1** |
| cine-linen | #d4cbbb | 0.6037 | 8.88 : 1 | 11.08 : 1 |
| Paper (zipc) | #f6ede1 | 0.8560 | 12.54 : 1 | 12.54 : 1 |
| Gutter (zipc) | #e5e2d9 | 0.7586 | 10.86 : 1 | 10.86 : 1 |

The other 39 were dark (0.0012 – 0.0637).

**The measurement split the six into two DIFFERENT defects, and that decided the fix:**

* `cine-paper-moon`, `cine-fieldnotes` and `cine-dustlight` state a light sheet with DARK ink
  (`--ink: #191b1f` / `#232A2C` / `#35261B`) — but their sheet sits UNDER the scene's own
  dark scrim over the wallpaper, so what painted was `#212124`, `#191e22` and `#271a0e`, and
  the panel's own text came out at **1.08 : 1, 1.15 : 1 and 1.17 : 1 — INVISIBLE**. Not a
  taste question: a defect.
* `cine-linen`, `Paper` and `Gutter` paint a genuinely light panel (#d4cbbb, #f6ede1, #e5e2d9)
  with dark ink that reads fine (8.88 : 1, 12.54 : 1, 10.86 : 1). White, as the owner said.

### The fix: darken, never delete (the 45 themes survive)

The owner's count warning is explicit (*"cuidado: nao percas os 45 temas que o dono tem"*),
so no design was dropped. Each theme's SURFACE AND INK ARE INVERTED while its hue, accent,
caption ink, typography, photograph and structure stay. The edits live in the generators that
write the bytes, never in the generated files:

| theme | where the palette lives | what changed |
|---|---|---|
| cine-paper-moon | `gen_cinematic.py`, new `NO_LIGHT_SLAB` table (its vars are read verbatim out of the vendored `zips/cinematic/src/themes.ts`, so the override lives in the generator, not in a hand edit of the source) | `--panel rgba(240,241,238,.94) → rgba(22,24,28,.96)`; `--ink #191b1f → #EDEFF2`; dim/faint/line/hover to the light tier; `--accent → #aab3c0` (the design's own silver, which reads on a dark slab) |
| cine-fieldnotes | `cine_extra_c1.py` `_RAW` | surface `rgba(243,239,230,.94) → rgba(20,26,28,.94)`; panel_text `#232A2C → #E9F0EE`; border to the accent's own light tier; `light_panel → False` |
| cine-dustlight | `cine_extra_c1.py` `_RAW` | surface `#F6EDE1 → #1E140C`; panel_text `#35261B → #F7ECDD`; border/soft to the accent's light tier; `light_panel → False` |
| cine-linen | `cine_extra_c2.py` `_RAW` | page `#efe7da → #1a1610`; text `#2e2a24 → #f2ece0`; cap_bg/cap_text/cap_edge, `surface`, `surface_2`, `line`, both overlay gradients and the scrim to dark warm; `light_panel → False`; the `plate` block to dark warm linen |
| Paper (zipc) | `gen_zipc.py` — **two** tables, `DESIGNS` (surface/line/text/muted/soft) and `STRUCT` (`--bg-slab`, the provisional ink and `color-scheme` both live there) | surface `#F6EDE1 → rgba(26,18,13,.96)`; text `#35261B → #F6E7D4`; scheme `light → dark`; `light → False` |
| Gutter (zipc) | `gen_zipc.py`, same two tables | surface `rgba(243,239,230,.94) → rgba(20,28,30,.96)`; text `#232D30 → #E2EBEF`; scheme `light → dark`; `light → False` |

**A build-time self-check, so the fix cannot be undone silently.** `gen_cinematic.py` now
fails the build if any emitted theme declares a light `--bg-slab`, with the SAME threshold
the census uses and the SAME function (`panel_is_light`) that chooses `color-scheme`. The
generator and the instrument cannot disagree about what "light" means.

### The census AFTER

```
themes measured: 45
LIGHT (luminance >= 0.50): 0
GATE: GREEN -- no theme ships a light panel
weakest body ink over its own background: cine-linen 11.62:1, cine-north-fog 12.17:1,
  cine-study-light 13.45:1, cine-paper-moon 13.90:1, cine-last-reel 13.97:1
```

Per theme (painted background, luminance, body ink / dim ink / caption ink):

| theme | painted | lum | ink | dim | caption |
|---|---|---|---|---|---|
| `theme-1` | #060708 | 0.0021 | 20.16:1 | 20.16:1 | 16.73:1 |
| `theme-2` | #06090b | 0.0026 | 19.97:1 | 19.97:1 | 19.97:1 |
| `theme-3` | #0f0e0d | 0.0044 | 15.34:1 | 15.34:1 | 15.34:1 |
| `theme-4` | #080705 | 0.0021 | 16.02:1 | 20.14:1 | 16.02:1 |
| `theme-5` | #060a08 | 0.0027 | 19.91:1 | 19.91:1 | 19.91:1 |
| `cine-midnight-rain` | #0a0c11 | 0.0036 | 16.95:1 | 7.57:1 | 18.21:1 |
| `cine-warm-hour` | #100905 | 0.0031 | 16.69:1 | 8.59:1 | 17.66:1 |
| `cine-velvet-dusk` | #230f21 | 0.0080 | 15.11:1 | 7.22:1 | 16.02:1 |
| `cine-study-light` | #2c1d0b | 0.0144 | 13.45:1 | 6.75:1 | 14.16:1 |
| `cine-tideline-body` | #0c1012 | 0.0050 | 16.80:1 | 8.31:1 | 18.12:1 |
| `cine-north-fog` | #272c2c | 0.0244 | 12.17:1 | 5.81:1 | 13.30:1 |
| `cine-motel-glow` | #160a0c | 0.0043 | 16.35:1 | 7.75:1 | 17.56:1 |
| `cine-paper-moon` | #212124 | 0.0156 | 13.90:1 | 6.20:1 | 14.74:1 |
| `cine-quiet-streets` | #151616 | 0.0081 | 15.41:1 | 7.34:1 | 16.82:1 |
| `cine-last-reel` | #2d1b05 | 0.0136 | 13.97:1 | 7.19:1 | 14.92:1 |
| `cine-cafe` | #100d0b | 0.0042 | 15.95:1 | 15.95:1 | 16.82:1 |
| `cine-tideline` | #0a1117 | 0.0053 | 15.39:1 | 15.39:1 | 16.31:1 |
| `cine-rainglass` | #0c0f10 | 0.0045 | 16.26:1 | 16.26:1 | 16.85:1 |
| `cine-fieldnotes` | #191e22 | 0.0126 | 14.50:1 | 14.50:1 | 14.72:1 |
| `cine-dustlight` | #271a0e | 0.0119 | 14.53:1 | 14.53:1 | 14.17:1 |
| `cine-rooftop` | #1f1b25 | 0.0122 | 14.18:1 | 14.18:1 | 14.28:1 |
| `cine-analog` | #130d0a | 0.0046 | 15.26:1 | 15.26:1 | 17.42:1 |
| `cine-shelves` | #0b0a07 | 0.0031 | 16.26:1 | 16.26:1 | 16.89:1 |
| `cine-ember` | #0c0706 | 0.0025 | 15.74:1 | 15.74:1 | 16.43:1 |
| `cine-rainline` | #080d11 | 0.0037 | 17.36:1 | 7.98:1 | 18.23:1 |
| `cine-blue-hour` | #13171e | 0.0084 | 15.43:1 | 6.94:1 | 16.57:1 |
| `cine-cellar` | #0e0b06 | 0.0034 | 16.23:1 | 6.38:1 | 17.24:1 |
| `cine-linen` | #332d23 | 0.0268 | 11.62:1 | 4.98:1 | 11.62:1 |
| `cine-reading-hour` | #0d0905 | 0.0029 | 16.09:1 | 6.31:1 | 17.84:1 |
| `cine-last-train` | #090e0d | 0.0040 | 16.61:1 | 7.35:1 | 17.72:1 |
| `pd-tele` | #040608 | 0.0017 | 20.30:1 | 20.30:1 | 20.30:1 |
| `pd-bcast` | #07090b | 0.0026 | 19.94:1 | 19.94:1 | 19.94:1 |
| `pd-mano` | #070709 | 0.0022 | 16.45:1 | 16.45:1 | 16.45:1 |
| `pd-cine` | #030406 | 0.0012 | 17.42:1 | 17.42:1 | 17.42:1 |
| `pd-instr` | #090b0e | 0.0033 | 19.70:1 | 19.70:1 | 19.70:1 |
| `GlassCards` | #0f0c0b | 0.0039 | 16.05:1 | 16.05:1 | 16.05:1 |
| `Hairline` | #080c11 | 0.0037 | 16.50:1 | 16.50:1 | 16.50:1 |
| `Paper` | #19120d | 0.0067 | 15.25:1 | 15.25:1 | 15.25:1 |
| `Quotes` | #120e0c | 0.0045 | 15.75:1 | 15.75:1 | 15.75:1 |
| `Ledger` | #0b0e0c | 0.0042 | 15.22:1 | 15.22:1 | 15.22:1 |
| `Feed` | #08080e | 0.0026 | 16.46:1 | 16.46:1 | 16.46:1 |
| `Bubbles` | #110f1a | 0.0054 | 16.05:1 | 16.05:1 | 16.05:1 |
| `Timeline` | #090d10 | 0.0038 | 16.14:1 | 16.14:1 | 16.14:1 |
| `Chips` | #0f0a07 | 0.0034 | 15.92:1 | 15.92:1 | 15.92:1 |
| `Gutter` | #141b1e | 0.0104 | 14.37:1 | 14.37:1 | 14.37:1 |

All 45 dark; the weakest body ink in the whole set is `cine-linen` at 11.62 : 1 (it was
1.04 : 1 in `Paper`). No theme lost its identity: every accent, caption ink, font, radius and
photograph is the design's own.

---

## The gates

`node _main/instruments-battery.mjs` → **89/89 rc=0, failed=0, launches=0**
(measured 2026-10-14 at ~21:2x -03:00, 173 s, `TMPDIR=I:/cc-tmp`). That battery includes
`gen-themes-repro-oracle.py` and `gen-cinematic-repro-oracle.py` (AGENTS.md rule 10: the
shipped theme CSS must be reproduced by a fresh run of its generator — PASS on both, which is
also the proof that no generated file was hand-edited), and `scope-leak-oracle.js`
(9 stylesheets, 0 leaked members).

Run outside the battery, all green:

| gate | result |
|---|---|
| `node _main/three-overlays-oracle.js` | PASS (32 checks) |
| `node _main/three-overlays-oracle.js --neg-arm` | PASS — 11/11 mutants RED, including the new N11 |
| `node _main/strip-float-oracle.js` | PASS (S1–S21 + W1–W5) |
| `node _main/botoes-lane-oracle.js` | PASS |
| `node _main/botoes-lane-oracle.js --neg-arm` | PASS — 8/8 mutants RED |
| `node _main/scope-leak-oracle.js [--neg-arm]` | PASS |
| `py -3 _main/cine-themes-oracle.py` | PASS |
| `py -3 _main/cinematic-designs-oracle.py` | PASS |
| `py -3 _main/zipc-designs-oracle.py` | PASS |
| `py -3 _main/theme-lightness-census.py --gate` | GREEN — 0 light themes of 45 |

### The three expectation tables re-baselined, and why

Two oracles named the controls the owner removed. Re-baselining an expectation is the
dangerous move this repo has been burned by, so each one says here why, and each one still
has to be able to say NO:

1. `_main/three-overlays-oracle.js` arm **D5** DEMANDED `history-toggle` — the very button
   the owner ordered out, so it went RED the moment the work was done (the same shape as its
   own 2026-10-12 theme-pill re-baseline). D5 now asserts BOTH halves: the CONTROL is gone
   AND the drawer is still on the panel, still in the DOM and still CSS-collapsed. New
   mutant **N11** restores the button and D5 goes RED — measured, both arms green.
2. `_main/_panel-chrome-arm.py` + `_main/_panel-chrome-probe.js`: `tele`'s footer
   expectation was `foot_start='HISTÓRICO'` / `foot_end='▲ EM CURSO'`. Now `None` for both,
   PLUS a positive absence check (`foot_absent=['HISTÓRICO', '▲ EM CURSO']` asserted
   against the chrome text the probe reports) — because a `None` expectation alone would pass
   just as well with the labels present and merely skipped, which is a guess, not a gate.
   **NOT RUN: this pair launches a real browser** (`_panel-chrome-arm.py` drives
   Edge/Chrome against a copy of the panel), which the owner's standing order forbids. The
   edits are byte-checked (`py_compile`, `node --check`) and classified exactly as
   `_main/cited-instruments-oracle.py` demands: APPLIED, and its proof needs a launch.
3. `_main/strip-float-oracle.js` S6/S7 (the strip button's 0.16/0.30 pair) were NOT touched.

---

## Files, before → after

| file | before | after |
|---|---|---|
| `app/panel/panel.html` | 66962 B / `a667e8d717fa7064` | 70280 B / `66d62d93745cc371` |
| `app/panel/panel.css` | 119959 B / `c6c33850902226a1` | 123233 B / `c815691c2235809c` |
| `app/panel/panel.js` | 158015 B / `e640549906a682da` | 160746 B / `a45939163203e439` |
| `app/panel/themes/theme-1.css` | 28985 B / `35342ddaffd8103d` | 28348 B / `3040207d1cbd4958` |
| `app/panel/themes/theme-2.css` | 29204 B / `73283d6ad507ade1` | 29050 B / `1624e29027205260` |
| `app/panel/themes/theme-3.css` | 29353 B / `f4815e2b837a65ff` | 29199 B / `470bae65c6873a96` |
| `app/panel/themes/theme-4.css` | 28286 B / `d10338e273539834` | 28132 B / `46ee9de33b662ac8` |
| `app/panel/themes/theme-5.css` | 29297 B / `697f811b0cc10925` | 29143 B / `730175d0166d0b9c` |
| `app/panel/themes/panel-designs.css` | 139659 B / `38be34dfdbb57639` | 138400 B / `739f8cf6f622b45a` |
| `app/panel/themes/cinematic.css` | 350433 B / `0c5607149d6f4876` | 350250 B / `0dda0b3ec076085b` |
| `app/panel/themes/zipc-panels.css` | 72757 B / `cb08dca3af1c4f22` | 72803 B / `0d7c8ec46a811d62` |
| `_main/_design-lane/gen_themes.py` | 165019 B / `26bc7671aec7ccd4` | 167322 B / `6d737829e0942015` |
| `_main/_design-lane/gen_cinematic.py` | 85696 B / `fa8a9a59e4944d19` | 89208 B / `1e00b68548945aef` |
| `_main/_design-lane/gen_zipc.py` | 71239 B / `1029a09290174670` | 73093 B / `cd179e5ffabcedb8` |
| `_main/_design-lane/cine_extra_c1.py` | 70346 B / `fc4358a47e17d24d` | 71688 B / `35ae62c88b47457a` |
| `_main/_design-lane/cine_extra_c2.py` | 70054 B / `023c7a5fedb1a60a` | 71581 B / `2aae36499db61614` |
| `_main/three-overlays-oracle.js` | 20884 B / `9d1523619569785f` | 22879 B / `c896289ffeb2e9ab` |
| `_main/_panel-chrome-arm.py` | 38849 B / `50567af60c07783d` | 40855 B / `3f960f00d7457558` |
| `_main/_panel-chrome-probe.js` | 35424 B / `7aa9c4c273d40e5d` | 36465 B / `9685cd7449c80ff8` |
| `_main/theme-lightness-census.py` | — | 13785 B / `9f7186895da62320` | **NEW** |

`themes.js` and `panel-designs.js` are BYTE-UNCHANGED (same sha) — the manifest, the picker
and the 45-theme count are exactly what they were.

---

## What is NOT measured (stated, not hidden)

* **Nothing here was seen painted.** No launch is permitted, so every claim is about bytes,
  parse, or an offline decode. What the real WebView2 paints — and whether the owner now
  reads the bars as CLEAN and the buttons as visible enough — is the one thing this receipt
  cannot prove, and it is the Lead's call to run.
* The census measures a photograph by its MEAN RGB (a 48×27 average), which is a summary and
  not a per-pixel map: a wallpaper that is half white and half black reads as mid-grey. It is
  good enough to separate 0.86 from 0.0067 by three orders of magnitude; it is not a
  rendering.
* `_panel-chrome-arm.py` / `_panel-chrome-probe.js` were re-baselined but NOT run (browser).
* The panel's own `silent-device` red error is BY DESIGN (AGENTS.md, decision of
  2026-10-06) and was NOT touched by this lane; the owner's "erro vermelho" clause belongs to
  the functional lane.

