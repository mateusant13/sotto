# ZIP A — built, rendered and VIEWED (2026-10-13)

Same recipe as zip E, and it worked first time because zip A also ships its own `node_modules`:

```
cd _moved/aireplay/docs/design/sotto-app-design-directions
NODE_ENV=production node node_modules/vite/bin/vite.js build
#  [plugin vite:singlefile] inlining index + style
#  dist/index.html  269.53 kB   built in 3.54s
```

Artefact kept at `_main/zip-mockups/zip-A-directions.html` (269 525 B).

## WHAT ZIP A IS, because it is NOT the same kind of thing as zip E

**It is a DESIGN-DIRECTIONS EXPLORER, not a panel mockup.** The frame is a full-screen page:

* Top: `SOTTO` + `LEGENDAS AO VIVO DO AUDIO DO PC`, and chips `380 x 900`,
  `SEMPRE NO TOPO`, `NUNCA ROUBO FOCO`.
* A row of FIVE TABS: `01 TELEPROMPTER` (active), `02 Broadcast`, `03 Manuscrito`,
  `04 Cartao de Cinema`, `05 Instrumento`.
* **A large headline bottom-left: "O SOM CHEGA ANTES DA IMAGEM."**
* Bottom bar: pause, `0,6x`, `1x` (active), `1,6x`, then pills `NOITE` (active), `PALCO`,
  `ABISMO`, and the hint `1-5 TROCA A DIRECAO . ESPACO PAUSA . CENA: TELEPROMPTER`.
* Right: the caption panel -- `SOTTO` with a `LENDO` state -- holding a LIST of lines with
  **the OLDER LINES FADED and the newest brightest**, then `HISTORICO` and `EM CURSO`.
* Bottom-right: `01 . A LEGENDA COMO FLUXO CONTINUO DE LEITURA`.

## The one thing that matters most from this render

**THE FADE IS UNMISTAKABLE HERE.** In zip A the caption list shows ten lines at once, each
dimmer than the one below it, with the last one clearly lit. That is the reading model the
`pd-*` work is trying to reproduce, and seeing it side by side makes the TARGET unambiguous in
a way a description could not.

## What is NOT done

* **Only the DEFAULT tab is captured.** `01 TELEPROMPTER` is active; the other four designs of
  zip A need the tab driven, which is a click -- not done.
* **Zips B, C and D are still unbuilt.** They have no `node_modules` on this box; A and E are
  the two that ship theirs.
* This is a DESCRIPTION of pixels, not a spec, and no mapping exists from zip A five directions
  to our `pd-tele` / `pd-bcast` / `pd-mano` / `pd-cine` / `pd-instr`.
