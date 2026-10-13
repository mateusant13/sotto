# RECEIPT — THE THEME CENSUS, SECOND ATTEMPT (the first was RETRACTED)

Date 2026-10-13. The FIRST census in this file was taken with an instrument whose
sample interval ALIASED against a blinking caret, and its numbers were wrong. The
retraction is below and stays. THIS is the re-run, with the instrument stable.

## Why the first one was wrong, in one line

`theme-3.css` carries `animation: sotto-caret 1.06s steps(1) infinite` — a blinking
caret, on purpose, that never settles for more than one phase. The settle loop
sampled every 1.2 s, within 0.14 s of that 1.06 s period, so consecutive frames
landed in the same phase on some runs and drifted on others. **An instrument whose
sample rate beats against the thing it measures is the bug.** Sampling at 0.35 s
puts about three samples inside one phase. Measured after: `theme-1` and `theme-3`
each IDENTICAL in 3 of 3 runs, where before they contradicted themselves.

## The reliable census — 30 of 45 themes

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
| `cine-shelves` | 4200 | `4C8E8161069E7E39` | PAINTED |

## What it says, so far

* **23 PAINT, AND NONE SHARE A HASH** — 0 duplicate hashes among
  them. Every theme that renders produces a DIFFERENT image, which is the direct
  answer to *"nao simplesmente uma skin por cima ou recolor"*.
* **4 PAINT A SINGLE FLAT COLOUR:** `Hairline`, `cine-quiet-streets`, `cine-rainglass`, `cine-reading-hour`.
* **2 ARE `UNSETTLED`:** `Feed`, `Timeline` —
  the new verdict refusing to pass an unsettled frame off as a measurement.
* **1 produced no window:** `cine-paper-moon`.

**THE FIRST CENSUS WAS MASSIVELY WRONG AND THIS IS THE PROOF.** It reported 12 flat
themes and 10 with no window. `cine-midnight-rain`, `cine-north-fog`, `cine-last-reel`
and `cine-last-train` were among its flat list — **they all paint now** (4192, 4161, …).
`Gutter` was flat and now paints 1398 colours. The no-window count went from 10 to 1.
Those were my instrument, published as facts about the product.

## Still open

**A VERDICT/COUNT DISCREPANCY:** `cine-rainglass` and `cine-reading-hour` show ONE
colour and the verdict says `PAINTED`, which contradicts the logic (a settled capture
with `distinct_colours <= 1` must be `UNIFORM`). `cine-quiet-streets` shows one colour
and correctly says `UNIFORM`, so the path is not uniformly broken. Either the probe
own count disagrees with the PNG histogram — it counts from the DIB and caps at 65,
the histogram decodes the written PNG — or the verdict does not read the field it
thinks it does. Until that is understood, the 4 flat entries are
NOT established as flat.

The census is still running; 15 themes are unmeasured and
nothing here is a claim about them. And none of this is a claim about FIDELITY to the
zip: "different" is not "equal to the design".
