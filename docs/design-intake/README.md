# THE DESIGN INTAKE -- the .zip originals, printed, measured, compared

**What this folder is.** The owner, 2026-10-19:

> *"me explica por que DIVERSOS designs nao encaixam direito ou truncam na merda do
> painel da direita. do meio nao vi. e o painel do meio tem que mudar de acordo com o
> design selecionado."*
>
> *"se nao ta igual a porra da demo de painel lateral do .zip original, arruma. é isso q
> tu vai fazer, pra TODOS ELES... tira print de cada demo do .zip. e compara com as
> atuais."*

So: a print of EVERY demo in the five .zip originals, a measured comparison of each
against the panel the owner has today, and the measured reason several designs do not
fit.

**The receipt with the commands and the numbers is
[`_main/receipt-20261020-design-intake.md`](../../_main/receipt-20261020-design-intake.md).**
The per-demo comparison is [`COMPARISON.md`](COMPARISON.md).

> **This folder already had a lane in it.** `INVENTORY.md`, `TRANSLATION-SHEET.md`,
> `ALL-FIVE-ZIPS-AS-RENDERED.md`, `ZIP-A/B/E-AS-RENDERED.md`, `gap-oracle.mjs`,
> `rendered/` and the five extracted zips are from the 12-13/10 lane and are NOT mine --
> I did not touch them. `rendered/` holds that lane's prints; **those were taken with
> Edge's own `--screenshot`, so they are pictures of a 492 px layout cropped to 380**
> (the clamp measured below), which is why this lane made its own. `README.md` and
> `COMPARISON.md` are new (created 2026-10-20 01:07 and 00:57).

---

## THE INSTRUMENT, AND WHY IT IS NOT A SCREENSHOT

A print is a picture. A MEASUREMENT is not. Headless Edge on this box **clamps the
layout viewport to 492 px** -- measured 2026-10-20, not assumed:

| `--window-size` | `innerWidth` |
|---|---|
| 380,900 | **492** |
| 520,900 | 496 |
| 1000,900 | 976 |

i.e. `layout = max(492, requested - 24)`: the window's minimum outer width on this box
is 516 px. The owner's panel is **380 px** (`sotto_webview.py:124` `PANEL_WIDTH = 380`),
so every coordinate read from a plain screenshot of the panel describes a 492 px layout
cropped to 380 -- 112 px of fiction. `--headless=new` and `--headless=old` return the
same numbers.

So the prints here are taken by **`_main/_design-lane/cdp.mjs`**, a Chrome DevTools
Protocol driver that sets the LAYOUT viewport with `Emulation.setDeviceMetricsOverride`
-- the thing `vw` units and media queries resolve against. It measures `innerWidth 380`
at `--w 380` and `1280` at `--w 1280`. It launches no vite, no npm, no app, no worker:
it starts a headless Edge with a remote debugging port, which draws nothing on the
owner's screen.

**The demo side** is the owner's OWN prebuilt bundle, committed in the repo at
`_main/zip-mockups/` (see `_main/receipt-20261013-all-five-zips-build.md`). MEASURED
2026-10-20: `zip-A-directions.html`, `zip-D-themes.html` and `zip-E-panels.html` are
BYTE-IDENTICAL to the other copies on this box (sha256 `9D1AF1F5..` / `12793DAC..` /
`FD4601AE..`), so the five files in that folder are one set and are used for all five
prints. The demos are driven by their own keys (`1`-`5` and `ArrowRight`).

**The product side** is a COPY of `app/panel/` wearing the theme, measured at a true
380x900, with the zip's OWN script lines in the rail
(`_main/ziprefs/dirs/src/data/designs.ts:85`); the forming line is that script's
longest line, 57 characters -- the worst case the panel has to survive.

---

## THE FIVE ZIPS AND EVERY DEMO IN THEM

| the zip | the bundle | the demos | the product theme that carries it |
|---|---|---|---|
| `sotto-app-design-directions.zip` | `zip-A-directions.html` | 5 (teleprompter, broadcast, manuscrito, cartao-de-cinema, instrumento) | `theme-1..theme-5` |
| `sotto-transcription-panel-designs.zip` | `zip-E-panels.html` | 5 (teleprompter, broadcast, manuscrito, cartao-de-cinema, instrumento) | `pd-tele..pd-instr` |
| `cinematic-transcription-app-designs.zip` | `zip-B-themes.html` | 10 (midnight-rain .. north-fog) | `cine-midnight-rain` .. `cine-north-fog` |
| `cinematic-transcription-app-designs (1).zip` | `zip-C-panels.html` | 10 (glass-cards .. gutter) | `GlassCards` .. `Gutter` |
| `cinematic-transcription-app-designs (2).zip` | `zip-D-themes.html` | 20 (rainline .. quiet-marina) | 6 of the 20 ship (`cine-rainline`, `cine-cellar`, `cine-linen`, `cine-reading-hour`, `cine-last-train`, `cine-blue-hour`); the other 14 were left out on purpose (`_main/_design-lane/template-plan.md`) |

**50 demos.** Each one has two prints in `demos/`:

* `<set>-<nn>-<name>.png` -- the demo as the owner sees it, whole app;
* `<set>-<nn>-<name>-panel.png` -- the demo's OWN PANEL, clipped out of it. The clip is
  the one the comparison needs: the product's panel is 380x900, so the demo's panel is
  what the product has to look like.

## THE PRODUCT'S PANEL, ONE PRINT PER THEME

`current/current-<theme>.png` -- all 45 themes the owner can pick, at a true
380x900. The measurements are the `.json` next to each print.

**A note on the `cine-*` themes.** They are not the stock panel: `skin-host.js` mounts
the vendor design in a SHADOW ROOT and `skin-layout.css` hides our own caption box and
transcript drawer. The stylesheet that carries them (`themes/cinematic.css`) is not
`<link>`ed in `panel.html` either -- the SHELL injects `app/panel/lazy-assets.js` as
`BOOTSTRAP_JS` and the loader pulls the sheet in when a `cine-*` or `pd-*` theme is
selected. A copy of the document that runs without the shell therefore paints the BASE
skin. MEASURED 2026-10-20, the difference this makes: without the loader, `pd-tele`'s
live line measures **15 px** (the base `--caption-size`) instead of the theme's own
**32 px**. The copy in `data/` therefore ships the loader and a `window.sotto.dispatch`
stub that answers the loader's ask the way the shell's gate does -- the bytes then come
off the disk, from the very same file the shell would serve.

## THE FILES HERE

| path | what |
|---|---|
| `demos/` | 100 prints: 50 demos x (the app, the panel) |
| `current/` | 45 prints + 45 measurements: the product's panel, one per theme |
| `COMPARISON.md` | the per-demo comparison, with the numbers on both sides |
| `data/jobs.json` | every job the driver ran, with its URL, viewport and keys |
| `data/jobs-result.json` | the driver's own result log |
| `data/*.json` (in `demos/`, `current/`) | the measurement behind each print |

The instruments that made all of it are in `_main/_design-lane/`: `cdp.mjs` (the
driver), `probe-panel.js` and `probe-demo.js` (the two probes), `panel-measure.py`
(the product side), `intake-shots.py` (the prints), `compare.py` (the comparison) and
`gen-proof.py` (the generator's byte-for-byte proof).
