# The zip mockups are BUILDABLE: the missing half of the fidelity measurement

2026-10-13. `TRANSLATION-SHEET.md` says the one thing it never measured is whether a live
theme LOOKS like the zip design it is matched to by name, because "o gap-oracle e uma
matriz de NOMES" and **no zip was ever built or opened**. That second half is now false.

## Why it looked impossible, and is not

Each zip is a Vite/React app: `index.html` loads `/src/main.tsx`, which a browser cannot
run. `app/package.json` advertises a dead toolchain (`electron`, `tauri`, `svelte-check`)
and the repo rule says there is no build step in the PRODUCT path -- all true, and it made
"build the zip" look like "install a toolchain".

It is not. MEASURED: the zips under `_moved/aireplay/docs/design/` ship their OWN
`node_modules` -- **60 packages each** for `sotto-app-design-directions` (zip A) and
`sotto-transcription-panel-designs` (zip E). No install was needed or performed.

## The recipe, and it is one command

```
cd _moved/aireplay/docs/design/sotto-transcription-panel-designs
NODE_ENV=production node node_modules/vite/bin/vite.js build
```

The zip configures **`vite-plugin-singlefile`**, which inlines the JS and CSS:

```
vite v7.3.2 building client environment for production...
35 modules transformed.
[plugin vite:singlefile] Inlining: index-CWSjaDOd.js
[plugin vite:singlefile] Inlining: style-CtO-3fn8.css
dist/index.html  263.89 kB | gzip: 77.21 kB   built in 1.28s
```

**One self-contained file.** That is exactly the shape needed to render it in the same
WebView2 the panel uses and compare pixels, which is what the sheet calls unmeasured.

The built artefact is kept at `_main/zip-mockups/zip-E-panels.html` (263 888 B).

## What is NOT done here, stated plainly

* **Nothing was rendered and nothing was compared.** This file proves the reference can be
  BUILT; it does not measure fidelity, and must not be cited as if it did.
* The other three zips (`cinematic-transcription-app-designs` and its `(1)`/`(2)`) have NO
  `node_modules` on this box, so the same command does not work for them yet. Zip A
  (5 designs) and zip E (5 panels) are the two that are buildable today.
* Rendering needs a probe that loads an arbitrary local HTML and captures it. The paint
  probe is hardwired to `panel.html`, and pointing it elsewhere by editing the panel would
  trip the hot reload and change the owner app. That probe is the next piece of work.

## The rule this leaves

"There is no instrument for this" was wrong, and it was wrong for a specific reason:
I looked for the tool where the DOCUMENTATION said the toolchain was dead, and not where
the artefacts were. **The zips brought their own.** A repo-wide rule about the PRODUCT
path says nothing about a vendored reference sitting in `_moved/`.
