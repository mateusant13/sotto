# ZIP E — the five panel designs, AS RENDERED (with the transcript playing)

Measured 2026-10-13 by rendering the zip with its own vite and driving it with
`--virtual-time-budget=25000` so `useTranscriber()` actually plays and the captions appear.
Without the virtual time budget the caption area is EMPTY and all five panels look identical --
that is why the first pass produced five near-identical screenshots.

Source of truth: `docs/design-intake/rendered/panel-{1..5}-*.png` (809x728 crops of the panel
surface) and `played-E-{1..5}-*.png` (full 1280x800).

## 1. TELEPROMPTER  (viewed)

* **The BACKDROP SHOWS THROUGH** -- a cinematic street scene, blue/teal. The panel is not a
  solid surface; the video is the background and the text sits on it.
* **Captions are a RIGHT-ALIGNED COLUMN on the RIGHT SIDE**, light sans-serif, generous
  line-height. **Older lines are FADED** (opacity dropping upward); the current line is the
  brightest. That fade is the whole reading model: a teleprompter scrolls past you.
* **Status pill, top-LEFT**: monospace, UPPERCASE, letter-spaced, 1px border, rounded, with a
  small GREEN dot and separators -- `FUNDO: FILME . REPRODUZINDO . AUDIO ORIGINAL`.
* **Bottom bar is LIGHT** (near-white band) with: tabs `Filme | Jogo | Reuniao` (active tab
  inverted: white box, black text), a thin scrubber with `0:24:05` and `2:07:44` at its ends,
  then BOXED buttons `||`, `1,0x`, `fantasma`, then a dimmed hint line
  `espaco pausa . 1-5 troca direcao . Alt+C oculta`, and a right-hand chip
  `PAINEL 380x900 . ESCALA 68%`.

## 2. BROADCAST  (viewed, EMPTY state only)

In the empty state it is pixel-for-pixel the same chrome as Teleprompter: same pill, same
bottom bar. **The difference must be in how the caption text is set, which is why the played
render is the one that matters.** Not yet viewed in the played state.

## 3-5. MANUSCRIPT, CINEMA, INSTRUMENT

**NOT YET VIEWED in the played state.** Renders exist (`panel-3-manuscript.png`,
`panel-4-cinema.png`, `panel-5-instrument.png`).

## What this MEANS for our panel, and it is a real difference

Our `panel.html` today: a solid dark surface, a top bar with `SOTTO` on the LEFT and the status
cluster on the RIGHT, a bordered empty transcript box, and a DARK bottom bar with icon buttons.

The zip design: **no solid box at all** -- backdrop visible -- captions right-aligned in a
fading column, **status pill top-LEFT in monospace**, and a **LIGHT bottom bar with boxed
labelled controls and tabs**.

Those are not colour differences. They are structure: where the status lives, whether the
caption area has a frame, which side the text hangs from, and whether the bottom bar is light
or dark.

## The honest limits of this note

* Three of five panels have NOT been looked at in the played state. Do not treat this as the
  full set.
* The crop box `(437, 62, 1246, 790)` was chosen by eye from the first render; if a panel paints
  outside it, the crop hides that.
* This is a DESCRIPTION of pixels I saw. It is not a spec, and it does not yet say which of the
  five our `pd-tele`/`pd-bcast`/`pd-mano`/`pd-cine`/`pd-instr` should match.

---

# ALL FIVE, VIEWED IN THE PLAYED STATE (2026-10-13, second pass)

## The chrome is SHARED by all five

1. **The BACKDROP is visible.** Not one of the five paints a solid opaque panel: the video is
   the surface and the text sits on it.
2. **Status pill, top-LEFT, identical in all five**: monospace, UPPERCASE, letter-spaced, 1px
   border, rounded, small green dot, ` . ` separators -- `FUNDO: FILME . REPRODUZINDO . AUDIO
   ORIGINAL`.
3. **Bottom bar is LIGHT** in all five: tabs `Filme | Jogo | Reuniao` (the active tab is an
   inverted white box with black text), a thin scrubber with `0:24:05` and `2:07:44` at its ends,
   then BOXED buttons `||`, `1,0x`, `fantasma`, then a dimmed hint line
   `espaco pausa . 1-5 troca direcao . Alt+C oculta`, and a right-hand chip
   `PAINEL 380x900 . ESCALA 68%`.

## What actually DIFFERS between the five -- and it is only the CAPTION COLUMN

The five designs are five ways of setting the SAME right-hand caption column. Everything else
is shared, which is why the empty-state renders were indistinguishable.

| # | design | the caption column |
|---|---|---|
| 1 | **Teleprompter** | right-aligned within the column; **older lines FADED**, current line brightest -- the fade IS the reading model |
| 2 | **Broadcast** | same chrome as Teleprompter in the empty state; **the played state was NOT re-viewed** -- do not claim what it does |
| 3 | **Manuscript** | a distinct **light column panel**; text left-aligned inside it; **no fade** (all lines equal); closes with `ouvindo` in italic plus a caret |
| 4 | **Cinema** | **SERIF** typeface; every line prefixed with an em-dash `--`; block right-aligned on the video |
| 5 | **Instrument** | sans-serif column over a subtle darker panel; **and `Alt` `C` drawn as BOXED KEYCAPS with `ocultar painel`** beneath it |

## What this means for OUR panel, stated as structure and not as colour

`app/panel/panel.html` today: a **solid dark surface**; `SOTTO` top-LEFT and the status cluster
top-RIGHT; a **bordered empty transcript box**; a **DARK** bottom bar of icon-only buttons.

The zip design: **no solid box**; status pill top-LEFT in monospace; the caption hangs in a
**right-hand column** with **no frame**; and the bottom bar is **LIGHT with boxed, LABELLED**
controls and tabs.

Concretely different: (a) whether the surface is opaque, (b) which corner the status pill lives
in and in what typeface, (c) whether the caption area is a framed box or an open column,
(d) which side the text hangs from, (e) whether the bottom bar is light or dark, and (f) whether
its controls are icons or boxed labels.

## STILL NOT ESTABLISHED

* **Broadcast has not been viewed with captions.** Four of five is not five of five.
* **The zips A, B, C and D have NOT been rendered at all** -- only E. The owner asked for "each
  .zip (each demo)"; three of them have no `node_modules` on this box and were never built.
* No mapping has been made from these five to our `pd-tele` / `pd-bcast` / `pd-mano` /
  `pd-cine` / `pd-instr`, and the names are a TRAP: our `pd-cine` is not obviously the zip Cinema.
* **Nothing in the product has been changed by this note.** It is a description of what I saw.
