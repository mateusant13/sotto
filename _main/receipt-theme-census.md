# RECEIPT — THE THEME CENSUS: what each design actually PAINTS

Date 2026-10-13. Owner, verbatim, and this is the complaint it answers:

> "eu to vendo div com cor solida inves de invisivel"
> "e varios designs estao bugados"
> "cada zip diferente/tema, nao simplesmente uma skin por cima ou recolor"

Every check on the designs until now was a PARSE of CSS bytes. This one is
PIXELS, and it became possible only after the capture stopped being a race.

## The instrument, and the two fixes that made it honest

1. **Do not fight `theme-switcher.js`, FEED it.** Writing `data-theme` from the
   shell surface script is overwritten by the switcher, which applies the STORED
   theme after the page loads. Pinning the attribute did not help either.
   Writing `localStorage["sotto.theme"]` in the BOOTSTRAP — which the shell
   preload injects before any page script — makes the switcher apply OUR theme as
   its own stored choice. This is what works.
2. **Wait for a SETTLED FRAME.** The probe captured ONCE, 2 s after
   `PANEL_SHOWN`, and a theme switch causes a re-render, so the frame sometimes
   landed mid-render: the same theme gave 1492 colours on one run and 1 on the
   next. It now waits for TWO CONSECUTIVE IDENTICAL FRAMES and reports
   `settled=true|false`, so a single frame is never passed off as settled.
   MEASURED after: `theme-1` identical in 3 of 3 runs; `cine-tideline` stable to
   one colour, and that one colour is explained — its 4px bar carries
   `animation: caption-led-breathe`, so its frame genuinely changes.

## The census

Captured on the panel surface, 380x900, off the owner desk (`on_monitor=False`).
`cores` is distinct colours in the capture; the same `sha` means the SAME image.

| theme | cores | sha | verdict |
|---|---|---|---|
| `Bubbles` | 1916 | `D5D89A8D6EF6BDEE` | PAINTED |
| `Chips` | 1973 | `7C6EACDDED734365` | PAINTED |
| `Feed` | 1613 | `6ABA4248A4E8AD7B` | PAINTED |
| `GlassCards` | 2159 | `183EA42468599B0B` | PAINTED |
| `Gutter` | 1 | `AE960685EBFEE695` | PAINTED |
| `Hairline` | 1 | `AE960685EBFEE695` | PAINTED |
| `Ledger` | 1817 | `E28D1DCFDA9CB59D` | PAINTED |
| `Paper` | 1231 | `A4C24F5B69BDA843` | PAINTED |
| `Quotes` | 2061 | `79C266DF209C2C17` | PAINTED |
| `Timeline` | 1689 | `9739979F1F4D2F61` | PAINTED |
| `cine-analog` | 4130 | `5C268A4365BBA696` | PAINTED |
| `cine-blue-hour` | 4150 | `5B7B69630217060A` | PAINTED |
| `cine-cafe` | 4208 | `F4D25F5CEEE58BF7` | PAINTED |
| `cine-cellar` | 4122 | `E0C3D12AB5220715` | PAINTED |
| `cine-dustlight` | 4153 | `6086D1ED6E92DCF6` | PAINTED |
| `cine-ember` | 4127 | `D5ECA12DD9047D97` | PAINTED |
| `cine-fieldnotes` | SEM PNG | `—` | NO-WINDOW |
| `cine-last-reel` | 1 | `AE960685EBFEE695` | UNIFORM |
| `cine-last-train` | 1 | `AE960685EBFEE695` | UNIFORM |
| `cine-linen` | 4122 | `84E4578BBE9A29CB` | PAINTED |
| `cine-midnight-rain` | 1 | `B0514C577ED8270E` | UNIFORM |
| `cine-motel-glow` | SEM PNG | `—` | NO-WINDOW |
| `cine-north-fog` | 1 | `B0514C577ED8270E` | UNIFORM |
| `cine-paper-moon` | SEM PNG | `—` | NO-WINDOW |
| `cine-quiet-streets` | 1 | `B0514C577ED8270E` | UNIFORM |
| `cine-rainglass` | SEM PNG | `—` | NO-WINDOW |
| `cine-rainline` | SEM PNG | `—` | NO-WINDOW |
| `cine-reading-hour` | SEM PNG | `—` | NO-WINDOW |

## What it says

**SIX THEMES PAINT A SINGLE FLAT COLOUR:** `Gutter`, `Hairline`,
`cine-last-reel`, `cine-last-train`, `cine-midnight-rain`, `cine-north-fog`.
Four share `AE960685EBFEE695` and two share `B0514C577ED8270E`.

**TWO DISTINCT FLAT COLOURS IS WHY THIS READS AS REAL AND NOT AS A BROKEN
INSTRUMENT.** A capture that failed would give the SAME blank for every theme. Two
groups of identical flat pixels is what RENDERING a flat surface looks like. And it
is the owner exact words arriving from a direction nobody had looked from: he was
not only describing the strip window — he was describing themes that paint nothing
but their surface.

**FIFTEEN PAINT, AND ALL FIFTEEN DIFFER**, each with its own sha256: the eight
zip-C designs (Bubbles 1916, Chips 1973, Feed 1613, GlassCards 2159, Ledger 1817,
Paper 1231, Quotes 2061, Timeline 1689) and the `cine-*` that paint (analog 4130,
blue-hour 4150, cafe 4208, cellar 4122, dustlight 4153, ember 4127, linen 4122).
**So the zip-C lane work is visible in pixels**: eight genuinely different designs,
not one recoloured skeleton — which is exactly what the owner asked for.

## What I am NOT claiming

**That the six are DEFECTIVE.** Two readings remain, and this session has already
produced one artefact from reading a capture too eagerly:

* **(a)** the theme paints only its surface, which the owner would see as a solid
  div; or
* **(b)** with no captions arriving, the panel has nothing to draw on that surface
  and a flat colour is correct.

Nothing in `zipc-panels.css` hides the panel for `Gutter` or `Hairline`, which is
why (a) is NOT yet established. **The test that separates them**: capture with
caption text on screen, or inspect what the surface rule covers.

**THREE PRODUCED NO WINDOW AT ALL** — `cine-fieldnotes`, `cine-motel-glow`,
`cine-paper-moon`. Those are NOT counted as findings: a window that never mapped is
an instrument failure, not a theme that paints nothing. They need a re-run.

## Status

The census is STILL RUNNING and writes incrementally to
`I:/cc-tmp/theme-census.txt`; 21 of the 45 themes are unmeasured at the time of
writing. Nothing here is a claim about those.
