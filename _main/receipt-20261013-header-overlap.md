# The top-left status is painted TWICE — and it is the BASE panel, not a theme

2026-10-13. Follows `receipt-20261013-pdtele-vs-zipE.md`, where the overlap was first seen
while rendering `pd-tele` for the zip mapping.

## It is not a theme

Rendered with `--theme theme-1` and compared: **the overlap is there too, and the render is
BYTE-IDENTICAL to the default one (same sha256 `d8de6d157133888bb72153dce4a1b1b10cdf9159efe8877d24b56f765cf2b833`).**
So `theme-1` IS the default, and **the defect is in the base panel and would ship on every
theme.**

## What the render shows

The header reads roughly: the `SOTTO` wordmark, then `EM ESPERA` with a dot, **and a SECOND
copy of `EM ESPERA` overlapping it** -- then, to the right, `Teleprompter` with a dot, a
chevron, and the theme / A A / pause / close icons.

The panel FOOTER is separate and says `HISTORICO` + the worker message, and `EM CURSO` on the
right. So the footer is NOT the second copy.

## The markup that is involved, read (not guessed)

* `panel.html:139` `<header class="panel__header">`, whose first child is `<div class="wordmark">`
  -- the SVG logo. That is the left end of the header.
* `panel.html:894` `<footer class="status" id="status">` with `#status-dot` and
  `#status-text` -- the BOTTOM readout, not the top.
* `panel.html:858` `<span class="stripbar__state" id="strip-state">` -- INSIDE `.stripbar`.
* `panel.css:1454-1457` hides `.stripbar` on the panel surface:
  `body[data-surface="panel"] .stripbar { display: none }`.

## The candidate, and it is specific

**`#strip-state` is inside `.stripbar`, and `.stripbar` is hidden ONLY when the body carries
`data-surface="panel"`.** If that attribute is absent or set to something else at paint time,
the hide rule does not match, `.stripbar` renders, and `#strip-state` paints its readout on top
of the header -- which is exactly the doubled text in the picture.

`panel.js` sets the attribute (`document.body.dataset.surface = strip | panel`), so in the
real app it should be set -- **which is why the next step is to READ the attribute at paint
time rather than assume it, and not to "fix" the CSS blind.**

## Not established

* **No rule was changed.** The overlap was SEEN and the candidate is a READING of the markup,
  not a measurement of the live DOM.
* The probe renders the shell it copies; whether the attribute is set at the instant of the
  paint has NOT been read.
* `pd-bcast`, `pd-mano`, `pd-cine` and `pd-instr` were not rendered, so it is not claimed that
  the overlap looks identical under each -- only that it is present in the base.
