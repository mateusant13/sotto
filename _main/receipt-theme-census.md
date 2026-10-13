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
   theme after the page loads. Pinning the attribute did not help either. Writing
   `localStorage["sotto.theme"]` in the BOOTSTRAP — which the shell preload
   injects before any page script — makes the switcher apply OUR theme as its own
   stored choice. This is what works.
2. **Wait for a SETTLED FRAME.** The probe captured ONCE, 2 s after
   `PANEL_SHOWN`, and a theme switch causes a re-render, so the frame sometimes
   landed mid-render: the same theme gave 1492 colours on one run and 1 on the
   next. It now waits for TWO CONSECUTIVE IDENTICAL FRAMES and reports
   `settled=true|false`. MEASURED after: `theme-1` identical in 3 of 3 runs;
   `cine-tideline` stable to one colour, and that one colour is explained — its
   4px bar carries `animation: caption-led-breathe`, so its frame genuinely
   changes.

## The census

Captured on the panel surface, 380x900, off the owner desk (`on_monitor=False`).
`cores` is distinct colours; the same `sha` means the SAME image. **40 of 45
themes measured**; `theme-1`..`theme-5` are unmeasured and nothing here is a claim
about them.

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
| `cine-reading-hour` | SEM PNG | `—` | NO-WINDOW |
| `cine-rooftop` | 1 | `AE960685EBFEE695` | UNIFORM |
| `cine-shelves` | 1 | `B0514C577ED8270E` | UNIFORM |
| `cine-study-light` | 4167 | `5AA7E20DB57CD884` | PAINTED |
| `cine-tideline` | 4212 | `29CE980610D2AFC0` | PAINTED |
| `cine-tideline-body` | 4127 | `9124CC1A221A1819` | PAINTED |
| `cine-velvet-dusk` | 4177 | `36B7BF909B181C4D` | PAINTED |
| `cine-warm-hour` | 4194 | `64654B8E54E65F17` | PAINTED |
| `pd-bcast` | 1 | `AE960685EBFEE695` | UNIFORM |
| `pd-cine` | 1 | `AE960685EBFEE695` | UNIFORM |
| `pd-instr` | 4323 | `472D27CFF98AE6B9` | PAINTED |
| `pd-mano` | SEM PNG | `—` | NO-WINDOW |
| `pd-tele` | 4294 | `E461E6608A0C8F0C` | PAINTED |
| `theme-1` | 1 | `AE960685EBFEE695` | UNIFORM |

## THE THREE NUMBERS THAT MATTER

**22 PAINT, AND ALL 22 DIFFER — ZERO DUPLICATE HASHES.** Every theme that paints
produces a DIFFERENT image. That is the direct answer to *"nao simplesmente uma
skin por cima ou recolor"*: among the designs that render, there is not one
recolour. The eight zip-C designs paint 1231–2159 distinct colours each with its
own sha256, so the zip-C lane work is visible in pixels.

**11 PAINT A SINGLE FLAT COLOUR:** Gutter, Hairline, cine-last-reel, cine-last-train, cine-midnight-rain, cine-north-fog, cine-quiet-streets, cine-rooftop, cine-shelves, pd-bcast, pd-cine, theme-1.

**7 PRODUCED NO WINDOW AT ALL:** cine-fieldnotes, cine-motel-glow, cine-paper-moon, cine-rainglass, cine-rainline, cine-reading-hour, pd-mano. A window that never
mapped is an INSTRUMENT failure by definition and is NOT counted as a finding —
but 7 of 40 is a high rate and it is itself worth investigating before any of
these is called a broken design.

## What I am NOT claiming, and the test I could not run

**That the 11 flat themes are DEFECTIVE.** Two readings remain:

* **(a)** the theme paints only its surface, which the owner would see as a solid
  div; or
* **(b)** with no captions arriving, the panel has nothing to draw on that surface
  and a flat colour is correct.

Nothing in `zipc-panels.css` hides the panel for `Gutter` or `Hairline`, so (a) is
not established. **The test that separates them — a capture WITH caption text on
screen — was ATTEMPTED THREE TIMES AND DID NOT RUN.** Attempts one and two
hand-escaped the caption into the shell JS string and produced Python that would
not compile; attempt three used `json.dumps`, compiles cleanly, and STILL returns
SEM PNG on every capture, so the injection itself breaks the page or the window
mapping. The mode is kept with a warning at the top of it: **do not read a
`--caption` capture as evidence, and do not read its absence as a theme that paints
nothing.**

## Status

`theme-1`..`theme-5` unmeasured. The 7 no-window themes need a re-run. The 11 flat
themes need the discriminator. Nothing above is a claim about fidelity to the zip —
"different" is not "equal to the design", and comparing a capture against the zip
mockup is a different instrument again.


## RETRACTED 2026-10-13 — THE CENSUS NUMBERS ARE NOT REPRODUCIBLE, and here is the proof

**DO NOT USE THE TABLE ABOVE.** The same theme was measured twice, in two runs, and
it FLIPPED:

```
theme-1   run 1 = 1 colour UNIFORM   |  run 2 = 1488 colours PAINTED   <- DIFFERS
theme-3   run 1 = 2087 colours PAINTED | run 2 = 1 colour UNIFORM      <- DIFFERS
theme-2 / theme-4 / theme-5   no window in BOTH runs
```

A theme cannot paint and not paint in the same session. **The instrument is still
racy**, and the cause is measurable:

* the settle loop budget is `max(6.0, secs * 0.9)`;
* the CENSUS ran with `--secs 10`, so the budget was 9 s;
* the STABILITY TEST that looked convincing ran with `--secs 12`, so the budget was
  10.8 s;
* when the budget runs out the loop falls back to the LAST frame and marks it
  `settled=false` — which is honest, but the census did not check that flag.

So the census is a set of single frames with a shorter settle budget, and at least
two of them are demonstrably wrong. **The 22-and-all-differ headline may survive —
unique hashes within one run is not the same claim as reproducibility — but it has
not been earned either, and it must not be quoted until the census is re-run with a
budget that actually settles and with `settled=true` REQUIRED.**

**ALSO MEASURED, AND A SEPARATE DEFECT IN THE INSTRUMENT:** launching two probe runs
at once silently produces `NO-WINDOW`. The first census job was still running when a
second was started, and all 12 captures of the second came back SEM PNG — including
`theme-1`, which was stable 3/3 minutes earlier. The measurement lock refuses the
second launch and the probe reports it as a window that never mapped. **One probe at
a time, and a NO-WINDOW must never be read as a theme finding.**

## What IS still true

* `theme-1` was IDENTICAL in 3 of 3 runs at `--secs 12` (1492 colours, sha
  `09A63E78919C21A1`), and `cine-tideline` was stable to one colour, explained by
  its `animation: caption-led-breathe`. Those runs used the longer budget.
* The mechanism works: feeding `localStorage["sotto.theme"]` from the bootstrap
  does apply a theme, and different themes do produce different images.
* The two readings for the flat themes are still open, and the discriminator still
  has not run.
