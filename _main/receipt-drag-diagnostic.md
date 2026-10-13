# RECEIPT — THE DRAG DIAGNOSTIC, AND MY RETRACTION

Date 2026-10-13. Owner item 1: *"o painel de baixo tem que ser movivel pra cima ou
pra baixo ou pros lados."* The shell half is written, the bridge exposes
`setStripOffset` (`PRELOAD_ACTIVE methods=14 -> 15`), and the gesture oracle passes.
**Whether a drag actually moves the WINDOW has never been verified.**

## WHAT I REPORTED, AND WHY IT WAS WRONG

I built a `--dragoffset DX,DY` mode: the probe injects
`window.sotto.setStripOffset(dx, dy, "move")` into the surface script, and the probe
already logs the window rect — so the two rects ARE the measurement. It reported:

```
no drag     rect=(-10000, 992, -9620, 1092)
--dragoffset 60,30   rect=(-10000, 992, -9620, ...)   UNCHANGED
STRIP_DRAG lines in the shell log: 0
```

**And I concluded: "the call never reaches the shell; `window.sotto.setStripOffset` is
not reachable from the surface script context — a real candidate defect in the drag,
not just in my instrument."**

**THAT CONCLUSION IS RETRACTED. It was measured on a probe that never fired.** The
line that APPLIES the injection — `out = out.replace(drag_anchor, drag_js +
drag_anchor, 1)` — had been dropped by one of my own rewrites of that region, so
`drag_js` was computed and thrown away. The variant carried no injection at all.
Verified by grepping the BUILT VARIANT for the probe string: **0 matches.**

**The check that would have caught it the first time, and did not happen until too
late: grep the BUILT VARIANT, not the probe source.** Everything I checked was in the
probe; the thing being executed was the variant.

## WHAT HAPPENED AFTER THE MISSING LINE WAS RESTORED

Two further attempts, both breaking the generated Python, both the SAME mistake:

1. `kind:'dragprobe'` — **single quotes inside a single-quoted Python literal**. The
   string terminated at the first apostrophe and the shell would not load. Fixed to
   double quotes.
2. `'move'` in the three `setStripOffset` calls — **the same single quotes, still
   there.** A regex fix for it produced mismatched quotes and broke the file again.

**THE RULE, WRITTEN DOWN: nothing single-quoted goes into an injected JS fragment.**
That text lands inside the shell single-quoted Python literal, so an apostrophe in the
JS is a Python syntax error. `json.dumps` is the safe way to build any JS string
literal here, and it is what the caption injection already uses.

## STATE

`_main/panel-paint-probe.py` is RESTORED from git (`cde5a0d`), `py_compile` clean, and
it runs (`PAINTED` / `NO-WINDOW`). Nothing is left dirty.

**THE DRAG REMAINS UNVERIFIED, and this receipt claims nothing about it** — not that
it works, and no longer that the bridge is unreachable. The narrowed question is still
open: does the injected call arrive, and does the window move by (dx, dy)?

**THE CHEAPER INSTRUMENT IS THE OWNER HAND ON THE MOUSE.** One drag settles it, and it
has been asked for.
