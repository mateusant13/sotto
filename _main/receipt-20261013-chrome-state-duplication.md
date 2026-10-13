# The duplicated header text is MULTIPLE `.chrome__state` BLOCKS, not `#strip-state`

2026-10-13. This CORRECTS the candidate in `receipt-20261013-header-overlap.md`, which named
`#strip-state` inside `.stripbar`. **That candidate is REFUTED by measurement.**

## The refutation

Dumped the PAINTED DOM (headless Edge, `--dump-dom`, `--virtual-time-budget=5000`):

```
<body data-surface="panel" data-state="error">
```

**`data-surface="panel"` IS set**, so `panel.css:1454-1457`
(`body[data-surface="panel"] .stripbar { display: none }`) DOES match and `.stripbar` -- and
its `#strip-state` -- is hidden. The candidate was a plausible reading of the markup and it is
wrong. This is exactly why it was written down as a candidate rather than acted on.

## What the DOM actually shows

`EM ESPERA` appears **four times**, and every one of them is a `.chrome__state`:

```
.chrome--tele   > .chrome__state > .chrome__on "LENDO"    + .chrome__off "EM ESPERA"
[chrome brand]  > .chrome__state > .chrome__on "· live ·" + .chrome__off "· em espera ·"
.chrome--bcast  > .chrome__state > .chrome__on "LIVE"     + .chrome__off "EM ESPERA"
.chrome--instr  > .chrome__state > .chrome__on "OUVINDO"  + .chrome__off "EM ESPERA"
```

**ALL FOUR designs carry their chrome in the DOM at once**, each with its own `.chrome__state`
whose `__on` and `__off` spans hold the readout. **More than one of them is painting**, which is
the doubled text in the render.

## What is NOT yet established

* **Which elements are visible** was not read -- the dump gives the DOM, not the computed
  display. The `__on`/`__off` pairs are also meant to be toggled against each other, so some of
  the four are expected to be hidden by their own state rules.
* **No rule was changed.** The next step is to read the computed `display` of the four
  `.chrome__state` nodes in the painted page -- the DOM alone cannot say which are painted, and
  guessing again is what this receipt exists to avoid.

## The rule this keeps proving

**A plausible reading of the markup is not a measurement.** The first candidate named a
believable element and a believable rule; the DOM refuted it in one command. Write the
candidate down, then read.
