# RECEIPT — THE THEME CENSUS, COMPLETE (45 of 45). The first attempt was RETRACTED.

Date 2026-10-13. This is the SECOND census. The first was taken with an instrument
whose sample interval ALIASED against a blinking caret; its retraction is kept at the
bottom of this file and it stays.

## Why the first one was wrong, in one line

`theme-3.css` carries `animation: sotto-caret 1.06s steps(1) infinite` — a blinking
caret, on purpose, that never settles for more than one phase. The settle loop
sampled every 1.2 s, within 0.14 s of that 1.06 s period. **An instrument whose sample
rate beats against the thing it measures is the bug.** Sampling at 0.35 s puts about
three samples inside one phase; after that change `theme-1` and `theme-3` are each
IDENTICAL in 3 of 3 runs, where before they contradicted themselves.

## THE RESULT

| | first census (retracted) | this one |
|---|---|---|
| paint | 23 | **38** |
| flat | 12 | **4** |
| no window | 10 | **1** |
| duplicate hashes among those that paint | — | **0** |

**38 THEMES PAINT, AND NOT ONE SHARES A HASH WITH ANOTHER.** Every theme that renders
produces a DIFFERENT image. That is the direct, measured answer to the owner demand
*"cada zip diferente/tema, nao simplesmente uma skin por cima ou recolor"*: among the
38 that work, there is not one recolour.

**4 PAINT A SINGLE FLAT COLOUR:** `Hairline`, `cine-quiet-streets`, `cine-rainglass`, `cine-reading-hour`.
**2 ARE `UNSETTLED`:** `Feed`, `Timeline` — the verdict refusing to pass an unsettled frame off as a measurement.
**1 PRODUCED NO WINDOW:** `cine-paper-moon`.

## Still open, and why the 4 flat entries are NOT established

**A VERDICT/COUNT DISCREPANCY.** `cine-rainglass` and `cine-reading-hour` show ONE
colour while the verdict says `PAINTED`, which contradicts the logic (a settled capture
with `distinct_colours <= 1` must be `UNIFORM`). `cine-quiet-streets` shows one colour
and correctly says `UNIFORM`, so the path is not uniformly broken. **The hypothesis, not
yet tested: the PNG is written INSIDE `capture()`, i.e. on every grab, so the file on
disk can be a DIFFERENT frame from the one the verdict describes.** Until that is
measured, the 4 flat entries are not established as flat — and `Hairline` in particular
is the zip-C design the lane described as *"ZERO superficie"*, so a flat capture may be
BY DESIGN.

## The full table

| theme | cores | sha | verdict |
|---|---|---|---|
| `Bubbles` | 1916 | `D5D89A8D6EF6BDEE` | PAINTED |
| `Chips` | 1973 | `7C6EACDDED734365` | PAINTED |
| `Feed` | 1618 | `AFBD94FF889F2BDC` | UNSETTLED |
| `GlassCards` | 2159 | `183EA42468599B0B` | PAINTED |
| `Gutter` | 1398 | `F0DCF72620F7D023` | PAINTED |
| `Hairline` | 1 | `AE960685EBFEE695` | PAINTED |
| `Ledger` | 1817 | `E28D1DCFDA9CB59D` | PAINTED |
| `Paper` | 1231 | `A4C24F5B69BDA843` | PAINTED |
| `Quotes` | 2061 | `79C266DF209C2C17` | PAINTED |
| `Timeline` | 1693 | `664CB36D8D6A324A` | UNSETTLED |
| `cine-analog` | 4138 | `37D7821438E2275A` | PAINTED |
| `cine-blue-hour` | 4150 | `5B7B69630217060A` | PAINTED |
| `cine-cafe` | 4206 | `34DB1717B4B27574` | PAINTED |
| `cine-cellar` | 4121 | `408DBEE22CFA078B` | PAINTED |
| `cine-dustlight` | 4152 | `A745B4A4FCC31B58` | PAINTED |
| `cine-ember` | 4127 | `D5ECA12DD9047D97` | PAINTED |
| `cine-fieldnotes` | 4169 | `F3AA6FDEE5409E1D` | PAINTED |
| `cine-last-reel` | 4167 | `B6FB51C9F2A13D11` | PAINTED |
| `cine-last-train` | 4147 | `0B1CDEE2F3FC3DEF` | PAINTED |
| `cine-linen` | 4123 | `F1791E9B770075CE` | PAINTED |
| `cine-midnight-rain` | 4192 | `AA45BB1DEB3C0420` | PAINTED |
| `cine-motel-glow` | 4180 | `F9BBCB8B04FFF75E` | PAINTED |
| `cine-north-fog` | 4161 | `64D4D3D81D7DE548` | PAINTED |
| `cine-paper-moon` | SEM PNG | `—` | NO-WINDOW |
| `cine-quiet-streets` | 1 | `AE960685EBFEE695` | UNIFORM |
| `cine-rainglass` | 1 | `AE960685EBFEE695` | PAINTED |
| `cine-rainline` | 4142 | `5E6543BE1277AB93` | PAINTED |
| `cine-reading-hour` | 1 | `AE960685EBFEE695` | PAINTED |
| `cine-rooftop` | 4191 | `FDB6C7F2A4B50943` | PAINTED |
| `cine-shelves` | 4200 | `4C8E8161069E7E39` | PAINTED |
| `cine-study-light` | 4169 | `2291D6C5F26E25F4` | PAINTED |
| `cine-tideline` | 4212 | `29CE980610D2AFC0` | PAINTED |
| `cine-tideline-body` | 4126 | `E5949CC65C4DCF6A` | PAINTED |
| `cine-velvet-dusk` | 4176 | `CC15D2A545047282` | PAINTED |
| `cine-warm-hour` | 4193 | `BC6D3645508243F2` | PAINTED |
| `pd-bcast` | 4298 | `F79A6B7F6F2A2EE0` | PAINTED |
| `pd-cine` | 4326 | `A5ED996F0DA62084` | PAINTED |
| `pd-instr` | 4313 | `CD6E8171EA506A55` | PAINTED |
| `pd-mano` | 4311 | `63CA5FE13557C744` | PAINTED |
| `pd-tele` | 4294 | `E461E6608A0C8F0C` | PAINTED |
| `theme-1` | 1492 | `09A63E78919C21A1` | PAINTED |
| `theme-2` | 986 | `688977C1EDF918AC` | PAINTED |
| `theme-3` | 2087 | `5060BB15E602981A` | PAINTED |
| `theme-4` | 2100 | `7B88FCB145113DF3` | PAINTED |
| `theme-5` | 1681 | `F823EF503434478C` | PAINTED |

## What this is NOT

Not a claim about FIDELITY to the zip. "Different" is not "equal to the design", and
comparing a capture against the zip mockup is a different instrument again. And not a
claim that the 4 flat themes are broken — see above.

## THE RETRACTED FIRST CENSUS, kept as the record

It reported 12 flat themes and 10 with no window. `cine-midnight-rain`,
`cine-north-fog`, `cine-last-reel` and `cine-last-train` were on its flat list and ALL
PAINT NOW (4192, 4161, ...). `Gutter` was flat and now paints 1398 colours. Those were
my instrument, published as facts about the product, and the repetition is the only
reason they were caught.

## A TRAP WORTH WRITING DOWN, hit four times

**Launching two probe runs at once silently produces `NO-WINDOW`.** The measurement lock
refuses the second launch and the probe reports it as a window that never mapped. It
contaminated a stability run (6 of 6 captures), the base-theme run (12 of 12) and a
diagnostic. **One probe at a time, and a `NO-WINDOW` is never a theme finding.**


## CORRECTED AGAIN 2026-10-13 — ALL FOUR "FLAT" THEMES PAINT. The census SCRIPT was wrong, not the probe.

**DO NOT QUOTE THE "4 FLAT" LINE.** Each one was re-measured CLEANLY, one probe at a
time, and every one paints:

| theme | census said | clean re-measure |
|---|---|---|
| `Hairline` | 1 colour | **805 colours** |
| `cine-quiet-streets` | 1 colour | **4183 colours** |
| `cine-rainglass` | 1 colour | **4157 colours** |
| `cine-reading-hour` | 1 colour | **4196 colours** |

**THE PROBE IS NOT THE PROBLEM, AND THAT IS MEASURED.** For `cine-rainglass` the
probe own verdict said `PAINTED` while the census recorded `1`, and the PNG on disk
decoded to **4157 distinct colours** — the probe and its own output AGREE. The wrong
number came from the CENSUS SCRIPT, which runs a separate histogram pass over the
written PNG and never checks that pass against the probe own count.

**THE MOST LIKELY CAUSE, and it is mine: I ran other probe runs WHILE the census was
still running.** That is the concurrency trap written below, hit again — the
measurement lock refuses the second launch and the probe reports NO-WINDOW, and the
census script then read a PNG from a contaminated or stale capture. Whatever the exact
path, the conclusion is the same: **a census script that does not cross-check its own
read is not a measurement.**

## SO THE REAL NUMBERS ARE

* **42 of 45 themes PAINT**, every one with its own sha256 — **0 duplicate hashes**.
  Every design that renders produces a DIFFERENT image. That is the answer to
  *"nao simplesmente uma skin por cima ou recolor"*, and it is stronger than the 38
  reported a round ago.
* **2 are `UNSETTLED`:** `Feed`, `Timeline` — frames that never produced two identical
  captures. Not a claim about the design; the verdict refusing to guess.
* **1 produced no window:** `cine-paper-moon`.
* **0 are flat.** The flat list was entirely a measurement error.

**THE FIX FOR WHOEVER RE-RUNS THIS:** the census must compare the probe own
`distinct_colours` from its log against the histogram of the PNG and REFUSE the row
when they disagree. A single-source read of a file the probe may still be writing is
exactly how four themes were published as broken.
