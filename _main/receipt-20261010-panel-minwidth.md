# Receipt — the header overflow at the shipped panel width, and the one-line cure

**Date:** 2026-10-10 (Sao Paulo), written before the commit it describes.
**Subject:** `app/panel/panel.css` — `.panel__header` (the grid item that carries the wordmark, the
chrome labels and `.panel__controls`) never had `min-width: 0`, so at the SHIPPED panel width
(`PANEL_WIDTH = 380`, `app/webview/sotto_webview.py:84`) it laid out at **402.875 px** and pushed
`.panel__controls` **30.13 px past the window**, where `overflow: hidden` on `.panel`
(`panel.css:136-168`) clipped it silently.

**Instrument:** `_main/_panel-minwidth-probe.py` — 27,442 B, sha256
`23177800AEA46CBA64F45A6E99EE14F67EC54CC18DE1409954F4C01AA8A0E46A`, mtime 2026-10-10T19:59:12Z,
`py_compile` rc=0, runs 1–6 and 9 rc=0, run 7 rc=2 (instrument defect, since fixed), run 8 rc=0.
**Cure:** `app/panel/panel.css` — 88,430 B, sha256
`98E7BFF25D5ABA2D61413DB0B2902908FA3B7450A86F847B685DE722172D114B`, `git diff --stat` =
`10 insertions(+)` (a measured comment block and `min-width: 0;` on `.panel__header`, `:184-201`).
**Companion:** `_main/receipt-20261010-panel-overflow.md` §1 measured the REAL panel at 402.875 px,
the same number this probe reproduces in a fixture — the defect was live in the app, not only in the
instrument.

---

## 1. The geometry, measured, not derived

The panel is 380 px wide, so `.panel`'s content box is **350.00 px** (padding 28 + border 2; measured in
every run: `content box: byClient=350.00 byRect=350.00 (pad=28.00 border=2.00)`).

`.panel` is `display: grid; grid-template-rows: auto auto minmax(140px,1fr) auto; overflow: hidden`.
The header is a grid item, so **`min-width: auto` applies to it**: its automatic minimum size is its
min-content contribution, and that contribution is set by its WIDEST child, not by the item box.

Measured floors (runs 2/3/4, pre-edit; unchanged post-edit — the floors are a property of the
children, not of the header's own `min-width`):

| item | min-content | max-content |
|---|---|---|
| `.panel__header` | **395.13 px** | 444.72 px |
| `.captions` | 31.45 px | 31.45 px |
| `.panel__controls` | 250.41 px | 250.41 px |
| `.wordmark` | 43.97 px | 93.56 px |
| `.captions__hint` | 0.00 px (off-DOM clone; see §6) | 0.00 px |

**395.13 > 350.00.** The header could not fit, so it took 395.13 px and the panel scrolled. Measured,
pre-edit, at the default injection point:

```
pts   none           live  track=402.88 over=53 clip=52.88 minw=auto   (t~2 s)
sweep as-shipped     panel__controls l=159.72 r=410.13  -> 30.13 px off-window
                     panelOver = 53 px, clippedBy = 52.88 px
```

`.panel__controls` ends at 410.13 while the window is 380 wide: **the owner's play/pause, stop, clear
and theme buttons started 22 px inside the window and were clipped at its right edge.** That is the
defect. A later sweep row for the same theme measured 402.88 → 395.13 during the run (§6); both
numbers are above 350.

## 2. The cure and its measurement

One declaration — `.panel__header { min-width: 0; }` (`panel.css:184-201`) — plus the comment that
records where the number came from. Post-edit (runs 5, 6, 8, 9), all four runs identical:

```
pts   none     live track=350 over=0 clip=0 minw=0px    auto track=402.88 over=53 clip=52.88
sweep as-shipped  panel__controls l=114.59 r=365  -> inside the window
                  kidsRight=365, headerW=350, panelOver=0, docOver=0
THE SHIPPED DOCUMENT, bare: #panel scrollWidth-clientWidth = 0 px, doc overflow = 0 px
```

The **negative control** is the `zero` arm, which sets `min-width: 0` on EVERYTHING (`.panel`,
`.panel__header`, `.captions`, `.wordmark`, `.panel__controls`, `.chrome`, `.caption__text`): at the
default point the live arm reproduces `zero` exactly (`track=350 over=0 clip=0`), and the
NO-REGRESSION PROOF shows live == zero on all nine tracked fields (`panelOver, track, headerW, capsW,
controlsRight, clippedBy, headerScrollOver, capsScrollOver, docOver`) with
`fields moved by the fix: NONE`.

**What did NOT move:** `.panel`'s own box (`byClient == byRect == 350.00` before and after),
`--strip-height`, the grid template, and every theme's token set.
`FIX-CHANGES-SHIPPED-GEOMETRY: NO`.

## 3. The seven injection points (what the fix cures and what it does not)

Long text injected at each point, with `min-width` live vs `auto` (the control) vs all-zero:

| point | live (350) | auto (control) | zero |
|---|---|---|---|
| `none` | 350 / over=0 | 402.88 / over=53 | 350 / over=0 |
| `caption-text` | 350 / over=0 | 402.88 / over=53 | 350 / over=0 |
| `captions-hint` | 968.95 / over=619 | same | 350 / caps=619 / clip=0 |
| `stats-chip` | 1004.89 / over=655 | same | 350 / caps=655 / clip=0 |
| `wordmark__text` | 350 / over=1131 hdr=1145 | 1846.36 / over=1496 | = live |
| `controls + extra span` | 350 / over=1408 hdr=1422 clip=1421.61 | 1892.33 / over=1542 | = live |
| `captions__bar + extra span` | 1534.66 / over=1185 | same | 350 / caps=1185 / clip=0 |

`VERDICT OVERFLOW-REPRODUCED (7 point(s)); cured by min-width:0 at 2 of them`.

**So `min-width: 0` on `.panel__header` cures the header's own min-content floor — nothing else.** It
converts *panel-wide structural overflow* (the panel scrolls, the controls leave the window) into
*local clipping inside the grid item* (the item still overflows, but `.panel`'s `overflow: hidden` now
clips the excess and the item grows with the text). Three of the seven points put long text in an
element that is not `.panel__header`'s min-content contributor; those still overflow the item.
`captions-hint` and `stats-chip` keep 619/655 px of caps overflow in the `zero` arm — that is the
price of keeping one row, the same price the 100-px captions row already pays.

The 100 px captions bar (`captions__bar + extra span`) is the one genuinely ugly survivor: 1,171 px of
caps overflow with a real element (the bar) inside a row whose other axis is `minmax(0,1fr)`.

## 4. `.captions` — the negative result

`.captions` (`panel.css:1007-1012`) has `grid-template-rows: auto minmax(0,1fr); gap: 6px;
min-height: 0` and **no `min-width: 0`**. Its measured min-content floor is **31.45 px ≤ 350**, and
`hdr:0 + caps:0` is numerically identical to `hdr:0` alone in runs 3/4/5/6/9. Adding `min-width: 0`
there would be **defensive-only, zero measurable effect**. Not added. (Its sibling `.chrome` at
`:2185-2214` already HAS `min-width: 0` and it did not stop the header floor at 395.13 — a child's
`min-width: 0` does not lower the PARENT grid item's min-content contribution. Only the item's own
`min-width: 0` does. That is the transferable fact this whole item turned on.)

## 5. What the probe also measured, because the owner reads the result

**Per-child geometry, post-edit, theme-1** (`as-shipped`, `restored`, `restored2` identical):

```
wordmark        l=15      r=56.53   w=41.53   sw=44   over=2
chrome--tele    l=68.53   r=102.59  w=34.06   sw=77   over=43
panel__controls l=114.59  r=365     w=250.41  sw=250  over=0
```

**Per-theme** (`kidsRight=365`, `track=350`, `over=0`, `clip=0` in all 21 sweep rows; the two rows
below are the only sibling overlaps in the whole sweep):

```
theme-2   chrome--bcast l=15 r=365 w=350      + controls l=89    r=365 w=276    -> overlap 276 px
theme-5   chrome--inst  l=15 r=365 w=350      + controls l=89.72 r=365 w=275.28 -> overlap 275.28 px
theme-3   chrome--mano  l=15 r=79.72 w=64.72 over=21 + controls l=89.72
theme-4   chrome--cine  l=15 r=77.64 w=62.64 over=52 + controls l=89.64
skin=1    (skin-theme=cine-cafe) headerW=290.41, clip=-18  (skin-layout.css:72-81 repositions the header)
```

The theme-2/theme-5 overlaps are **byte-identical before and after my edit** — pre-existing, and both
boxes end at `r=365 < 380`, so nothing is pushed off-window; the chrome block shows through the
buttons.

**Paint extents (run 9), because a box is not what the owner sees:**

```
theme-1/as-shipped  chrome--tele paintRight=145.53 > controls.left=114.59  by 30.94
theme=null / cine-* wordmark     paintRight=108    > controls.left=69.2    by 38.8
theme-2             chrome--bcast paintRight=365   > controls.left=89       by 276
theme-3             chrome--mano  paintRight=101   > controls.left=89.72    by 11.28
theme-4             chrome--cine  paintRight=130   > controls.left=89.64    by 40.36
theme-5             chrome--inst  paintRight=365   > controls.left=89.72    by 275.28
state=live          chrome--tele paintRight=126.28 > controls.left=114.59   by 11.69
skin=1              none
```

**And the decisive `paintTop` walk (run 9): `OPAQUE COVER: none` at EVERY crossing in EVERY variant.**
Nothing hides the chrome's label under an opaque button; the topmost element at each crossing is a
real control painted with alpha ≤ 0.16:

```
theme-1        x=130.06  topmost=svg a=0          chain svg < button.icon-button.tune-button < div.panel__controls(a=0)
theme-2        x=227     topmost=button.icon-button.theme-chevro a=0.16
theme-3        x=95.36   topmost=button.icon-button.tune-button a=0.12
theme-4        x=109.82  topmost=path a=0
theme-5        x=227.36  topmost=button.icon-button.theme-chevro a=0.12
theme=null     x=88.6    topmost=path a=0  chain path < svg < button.icon-button.tune-button(a=0.08)
```

So the chrome's paint overlapping the controls' box is **real but not opaque**: the buttons and icons
show through. It is a cosmetic defect, not an occlusion defect.

### Residual cost of the cure (reported, not hidden)

In theme-1 the inert `chrome--tele` label's paint right edge is 145.53 while
`.panel__controls.left` is 114.59: a **30.94 px** crossing whose midpoint lands on the tune button's
svg (alpha 0). The first real control button starts at 144.59, so the overlap touches it by
**0.94 px**. **The pre-edit paint extent was never measured**; inferring from the same 77 px content
width would give ~10.6 px, and that is inference, so it is labelled. A one-line follow-up
(`overflow: hidden` on `.chrome`) would clip the decorative label instead of spilling it — it is an
owner-visible appearance change, so it is offered, **not applied**.

## 6. Honest gaps

1. **The probe is NOT wired into `_main/_audit-verify-all.cmd`, and must not be as a `:record`.** Its
   verdict is `OVERFLOW-REPRODUCED` / `NO-OVERFLOW-POSSIBLE-AT-SHIPPED-WIDTH`; a `:record` step passes
   on rc=0, and the probe returns **rc=0 even when the shipped document still overflows** (that is its
   as-shipped measurement, not a failure). A gate built on it would be vacuous. It stays a
   measurement instrument, run by hand.
2. **Pre-edit paint extents were not measured.** The pre-edit run recorded boxes only
   (`l=159.72 r=410.13`), no `paint`/`paintTop`.
3. **`.captions__hint`'s min-content floor reports 0** because the off-DOM clone used for the floor
   sizes to 0, while the injection arm still produced `track=968.95`. The injection arm is
   authoritative for that point.
4. **A within-run shrink:** in runs 1–4 the `none` row measured `track=402.88 / over=53` at t≈2 s and
   later sweep rows for the SAME theme measured `395.13 / over=45` — a 7.75 px shrink during the run.
   Mechanically: the 402.88-track run leaves 7.75 px of unallocated flex free space inside the header
   item, whose own box still spans 15→417.88 and drives `panelScroll`. Both numbers exceed 350, so the
   pre-fix verdict is unaffected; post-fix both are 350.
5. **`env.theme`** is read from `document.documentElement.dataset.theme` (themes are scoped on `:root`,
   `theme-switcher.js:7`); `data-skin` lives on `document.body` (`skin-host.js:304`). An earlier run
   read `document.body` and reported `theme=None` against a header floor of 395.13 — corrected in run 2.

## 7. Instrument notes (the transferable part)

- `py_compile` rc=0 does **not** validate the embedded JavaScript. A broken edit surfaced only at
  runtime: `RuntimeError: JavascriptException ... SyntaxError: Unexpected identifier 'paintTop'`. Root
  cause: an `edit` anchored on the **second line of a two-line `return { … }`** statement inserted the
  block inside the object literal. **Anchor on a statement's FIRST line.**
- A printer edit whose `old_string` started one line above the target swallowed the `% (…)`
  continuation and an `if not (...)` guard; the fix was to re-read the damaged region and replace it
  whole.
- The battery's byte-offset `call :label` rule does not apply to this file, but the same discipline
  does: an instrument whose sha256 changes mid-run is a dirty run.

## 8. The port

`app/panel/panel.css` is the only product file touched. `_main/_panel-minwidth-probe.py` is new and
untracked until this commit. No `app/webview/`, no `worker/`, no `_moved/aireplay/`, no lane's
`_design-lane/` file was read-modified-written.

