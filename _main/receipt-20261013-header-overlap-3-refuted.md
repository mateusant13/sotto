# The header overlap: THREE candidates refuted, and the cause is NOT found

2026-10-13. Status report on a defect that is real and still unattributed. Written so the next
attempt does not repeat any of the three dead ends.

## The defect, restated

Rendered at 380x900 with the DEFAULT theme, the header reads the `SOTTO` wordmark, then
`EM ESPERA` with a dot, **and a second copy of `EM ESPERA` overlapping it.** Reproduced twice,
and the two renders are BYTE-IDENTICAL (sha256
`d8de6d157133888bb72153dce4a1b1b10cdf9159efe8877d24b56f765cf2b833`), so it is stable and not a
frame artefact.

## Three candidates, all MEASURED, all REFUTED

| # | candidate | how it died |
|---|---|---|
| 1 | `#strip-state` inside `.stripbar` paints over the header because `data-surface` is unset | **REFUTED**: the painted DOM has `<body data-surface="panel" data-state="error">`, so `body[data-surface="panel"] .stripbar { display: none }` matches and that subtree is hidden |
| 2 | the four `.chrome__state` blocks all paint | **REFUTED**: `panel.css:2398` gives `.chrome { display: none }` -- "inert until a theme claims it" -- so every one of the four is inside a hidden parent |
| 3 | a theme switches on MORE than one chrome | **REFUTED**: `grep` of every file in `themes/` for a rule containing both `chrome--` and `display` returns **ZERO**. No theme claims any chrome at all |

Each of the three was a plausible reading of the markup. **Each died to one command.** That is
the pattern this defect keeps teaching: the markup is not the page.

## What that leaves

**The cause is NOT in the three places a reader would look first.** The remaining candidates are
all things the DOM dump cannot show by itself:

* the **computed `display`** of the header children, which needs script in the page -- and the
  panel CSP (`script-src self`, no `unsafe-inline`) forbids injecting one, which is the same
  wall that killed the caption fixture;
* a **pseudo-element** (`::before`/`::after`) painting a second copy of the text, which never
  appears in a DOM dump;
* a **background or `content:`** rule, likewise invisible to the dump.

**The next instrument is therefore the COMPUTED STYLE, not the DOM** -- and the honest note is
that reaching it needs either a `--readback`-style hook the paint probe already has, or a
harness that can evaluate script in the page.

## What is NOT claimed

* **The overlap is NOT attributed.** Nothing in this file says what causes it.
* Nothing was changed. No rule was touched.
* Only the default theme was checked for the missing chrome rules; the other themes were
  searched by `grep` but not rendered.
