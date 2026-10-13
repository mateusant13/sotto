# ALL FIVE ZIPS BUILD — and the trick was a JUNCTION, not an install

2026-10-13. Extends `receipt-20261013-zip-mockups-buildable.md`, which found that zip A and
zip E ship their own `node_modules` and the other three do not.

## The unlock

The five zips are all the same stack (`react-vite-tailwind`), so the three cinematic ones do
not need their OWN install -- they need A toolchain. A directory JUNCTION works:

```
cmd /c mklink /J <the-zip>\node_modules <zip-E>\node_modules
NODE_ENV=production node node_modules/vite/bin/vite.js build
```

**NO INSTALL WAS PERFORMED AND NOTHING WAS DOWNLOADED.** The junction is removed after the
build, so the repo tree is left as it was.

## All five, built today

| zip | what | artefact | size |
|---|---|---|---|
| A | sotto-app-design-directions | `zip-A-directions.html` | 269 525 B |
| B | cinematic-transcription-app-designs | `zip-B-themes.html` | 287 262 B |
| C | cinematic-transcription-app-designs (1) | `zip-C-panels.html` | 324 029 B |
| D | cinematic-transcription-app-designs (2) | `zip-D-themes.html` | 297 695 B |
| E | sotto-transcription-panel-designs | `zip-E-panels.html` | 265 073 B |

All five are single self-contained HTML files (`vite-plugin-singlefile` inlines the JS and the
CSS), so any of them can be rendered in the same engine the panel uses.

## What is DONE and what is not

* **DONE: all five BUILD.** That was the blocker; it is gone.
* **DONE: A and E have been RENDERED AND VIEWED** (`docs/design-intake/ZIP-A-AS-RENDERED.md`,
  `ZIP-E-DESIGNS-AS-RENDERED.md`).
* **NOT DONE: B, C and D have been built but NEVER RENDERED OR LOOKED AT.** Building is not
  seeing, and nothing about their designs is known here. Do not read this file as if it were.
* **NOT DONE: the mapping** from any zip design to our `pd-tele` / `pd-bcast` / `pd-mano` /
  `pd-cine` / `pd-instr`. The names are a trap -- our `pd-cine` is not obviously zip Cinema.
* The built artefacts are committed; the `dist/` trees and the junctions are not.
