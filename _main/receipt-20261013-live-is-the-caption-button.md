# Receipt — 2026-10-13 — "the LIVE button IS the caption button"

Re-baseline of every oracle/probe that asserted the OLD strip-float contract, so the
shipped bytes go GREEN and every gate keeps a control arm that can say NO.

Owner's ruling this is baselined against (verbatim, 2026-10-13):
*"o botao de legenda pra ativar a legenda deve ser o botao 'live'. o botao 'live'
ativo deve mostrar na tela as legendas, igual acontece nas demos de qualquer .zip."*
and *"pro painel de baixo, ele tem que ser mais uma faixa/linha reta."*

The one fact every gate now keys on:
`#strip-live-button[aria-pressed="true"]` <=> `body[data-float]="on"` <=> the
`#caption-float` overlay is displayed on the strip surface.

WRITE SCOPE: `_main/**` only. Nothing under `app/panel/**`, `app/webview/**`,
`worker/**` or `docs/**` was touched.

---

## 0. Product pins (frozen; read, not edited)

| file | bytes | sha256 (first 16) |
|---|---|---|
| app/panel/panel.html | 69875 | D844CF5B77370779 |
| app/panel/panel.js | 154949 | 447FEE7F7E8BF59F |
| app/panel/panel.css | 119872 | 3AD01D08BD52A3FE |

Confirmed by grep: `app/panel/panel.html`, `app/panel/panel.js` and
`app/panel/panel.css` contain **zero** occurrences of `strip-float-button`,
`stripFloatButton`, `data-strip-float`, `paintFloatState`, `toggleFloat` or
`strip-button--float` (matches only inside prose comments, never an id/attribute).

---

## 1. Files changed (exact list)

| file | bytes | sha256 (first 16) |
|---|---|---|
| _main/strip-float-oracle.js | 16939 | 5FC9D76FD58B1253 |
| _main/three-overlays-oracle.js | 20892 | 9D1523619569785F |
| _main/botoes-lane-oracle.js | 15046 | 34A859365A419CC5 |
| _main/_s2-bar-dom-oracle.js | 17843 | A94B538C778F7B9D |
| _main/caption-independent-oracle.js | 34228 | 5D32E29919435E8F |
| _main/_panel2-dom-probe.js | 55192 | C7BFD583F1D1C991 |
| _main/receipt-20261013-live-is-the-caption-button.md | (this file) | — |

Also fixed (same file, listed for completeness): the S21 band check inside
`_main/strip-float-oracle.js` had to strip CSS comments before matching, because the
straight-band rule's own comment contains the words `gradient` and
`border-radius: 10px -> 0` and a naive regex read the comment as a declaration.

Untouched, verified still green (they carry no old-contract token):
- `_main/strip-geometry-oracle.py` — no match; VERDICT: PASS -- 15 check(s), 0 fail.
- `_main/theme-preview-oracle.js` — no old button/attribute; VERDICT: PASS.
- `_main/panel-paint-probe.py` — only reads/writes `data-float` (still the correct
  attribute). It was **read, not run**; see NOT MEASURED.

---

## 2. OLD assertion -> NEW assertion, per gate

### 2.1 _main/strip-float-oracle.js

| check | OLD assertion | NEW assertion |
|---|---|---|
| S8 | `#strip-float-button` is in the markup | `#strip-live-button` is the ONE caption control in the markup |
| S9 | the button carries `data-strip-float` | the separate Linhar button is GONE (one control, not two) |
| S10 | the button is `aria-pressed` | the live button carries `aria-pressed` (the state the overlay keys on) |
| S10b | — (new) | `applyLiveEnabled` drives `applyFloat(liveEnabled)` — live-on IS caption-on-screen, one fact |
| S20 | the Linhar button declares its own order | the live button declares its own order (default 0 would render it before the grip) |
| S20b | float renders AFTER Pause and BEFORE state | row order is `brand<grip<live<open<pause<hide<state` (0,1,2,3,4,5,99) |
| S21 | — (new) | the strip slab is a STRAIGHT BAND: radius 0, no gradient, flat fill, hairline top+bottom |
| W1 | `dom.stripFloatButton` is looked up | `dom.stripLiveButton` is looked up |
| W2 | `stripFloatButton` is bound in wireStripControls | `stripLiveButton` is bound in wireStripControls |
| W9 | `paintFloatState()` exists | `applySurface` re-applies `applyLiveEnabled(liveEnabled, {silent:true})` (which repaints the float) |
| W10 | — (new) | `applyFloat` calls `bridge.setPanelSurface('strip', ...)` ONLY under the `currentSurface()==='strip'` guard |
| Z5 | `.caption__text { font-size: <N>px }` (literal) | accepts `var(--size-closed)` as well as literal px (10 matched, >= 10) |

Negative arm: M2 ("delete the Linhar button") and M6 ("float button loses its order")
were anchors that no longer exist; replaced by
- M2 = delete `applyFloat(liveEnabled);` from `applyLiveEnabled` (breaks S10b);
- M6 = make `applyFloat` unconditional (remove the strip-only guard; breaks W10);
- M7 = put `border-radius: 10px` back on the band (breaks S21).

### 2.2 _main/three-overlays-oracle.js

| check | OLD assertion | NEW assertion |
|---|---|---|
| A5 | `stripFloatButton` bound AND `setStripHeight(FLOAT_HEIGHT)` | `stripLiveButton` bound AND `applyFloat(liveEnabled)` AND `setStripHeight(FLOAT_HEIGHT)` |
| D1 | BARE set included `strip-float-button` | BARE = live, open, hide, pause (four controls) |
| D1b | the three the owner cut are GONE | the four the owner cut are GONE (`strip-float-button` added to CUT) |

Negative arm: added N9 = delete `applyFloat(liveEnabled);` (breaks A5) and
N10 = rename the open button to `id="strip-float-button"` (breaks A4/D1/D1b).

### 2.3 _main/botoes-lane-oracle.js

| check | OLD assertion | NEW assertion |
|---|---|---|
| A4 | expected `strip-live-button,strip-open-button,strip-hide-button,strip-float-button,strip-pause-button` | expected `strip-live-button,strip-open-button,strip-hide-button,strip-pause-button` |
| A7 | — (new) | the separate Linhar button is GONE (`/id="strip-float-button"/` absent) |

Negative arm: M4 anchor moved from `order: 6` to `order: 5` (the shipped hide order);
added M8 = rename the open button to `id="strip-float-button"` (breaks A4/A7).

### 2.4 _main/_s2-bar-dom-oracle.js (jsdom)

| check | OLD assertion | NEW assertion |
|---|---|---|
| B1 | the Linhar button exists and starts unpressed | the live button is the caption control and ships pressed (`true`) |
| B2 | overlay hidden before the click | overlay hidden before the strip repaints |
| B3 | one click flips `data-float` on | one click OFF: `['false','off','none']` (button, attribute, overlay agree) |
| B4 | overlay `display:block` | second click ON: `['true','on','block']` (one fact, three reads) |
| B5 | the button reports itself pressed | unchanged (live ON) |
| B14 | the second click lowers it | the next click lowers it |

Negative arm: N2 ("the overlay never becomes visible" by deleting the CSS
`display:block` rule) was stale — the overlay's visibility is now the module's own
inline style via `panel.js syncCaptionFloat`. N2 repointed to neuter
`api.setFloat(state === 'on');` (the panel->overlay call), which is the new contract.

### 2.5 _main/caption-independent-oracle.js (jsdom)

| check | OLD assertion | NEW assertion |
|---|---|---|
| SETUP | overlay+panel+`strip-float-button` in the document | overlay+panel+`strip-live-button` in the document |
| A3 | `show()` returns `true` and display is block | `api.state().painted` is true and display is block (show() returns "no change" because the app ships live ON) |
| A13 | click the Linhar button -> display block | A13 live ships pressed; A13b click OFF -> `['false','off','none']`; A13c click ON -> `['true','on','block']` |

Negative arm: unchanged (N1..N6), all still RED.

### 2.6 _main/_panel2-dom-probe.js (jsdom)

| check | OLD assertion | NEW assertion |
|---|---|---|
| ARM O | `audit.surfaces === [{panel, strip-open}]` | `[{strip, strip-float-on}, {panel, strip-open}]` — the load-time `applyFloat` on the `#strip` harness now asks the shell for the strip first |

No `--neg-arm` flag exists in this probe; it carries its own internal controls
("and that arm can still say NO ... in a COPY") which remained green.

---

## 3. Gates — commands and real measured output

All commands run as `$env:TMPDIR='I:\cc-tmp'; cd H:\sotto; <cmd>`. Read-only
node/python gates only; no app, shell, worker, WebView2, `run.cmd` or browser.

```
node _main/strip-float-oracle.js
  50 check(s), 0 failed
  VERDICT: PASS
  rc=0

node _main/three-overlays-oracle.js
  31 check(s), 0 failed
  VERDICT: PASS
  rc=0

node _main/botoes-lane-oracle.js
  34 check(s), 0 failed
  VERDICT: PASS
  rc=0

node _main/_s2-bar-dom-oracle.js
  23 check(s), 0 failed
  VERDICT: PASS
  rc=0

node _main/caption-independent-oracle.js
  48 check(s), 0 failed
  VERDICT: PASS
  rc=0

node _main/_panel2-dom-probe.js
  every arm PASS, rc=0   (ARM O now: [{"surface":"strip","reason":"strip-float-on"},
                          {"surface":"panel","reason":"strip-open"}], body surface = panel)
```

Untouched gates re-confirmed green:
```
py -3 _main/strip-geometry-oracle.py
  VERDICT: PASS -- 15 check(s), 0 fail   rc=0

node _main/theme-preview-oracle.js
  VERDICT: PASS   rc=0
```

---

## 4. Negative arms — real measured output (every mutant must go RED)

```
node _main/strip-float-oracle.js --neg-arm
  RED  M1 the height goes back to the old 100px            -> S1
  RED  M2 the caption is no longer driven by live          -> S10b
  RED  M3 the overlay push in addCaption is deleted        -> W3
  RED  M4 the runtime height change is deleted             -> W8
  RED  M6 applyFloat becomes unconditional                 -> W10
  RED  M5 the overlay gains a background                   -> S15
  RED  M7 the straight band gets its rounded corners back  -> S21
  NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0

node _main/three-overlays-oracle.js --neg-arm
  RED  N1..N8 (pre-existing, all RED)
  RED  N9  the LIVE button no longer drives the caption    -> A5
  RED  N10 the removed Linhar button comes back            -> A4 | D1 | D1b
  NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0

node _main/botoes-lane-oracle.js --neg-arm
  RED  M1 (live button deleted) -> 4 failing checks
  RED  M2 -> 1 | M3 -> 2 | M4 -> 1 | M5 -> 1 | M6 -> 2 | M7 -> 1
  RED  M8 the removed Linhar button comes back -> 2
  NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0

node _main/_s2-bar-dom-oracle.js --neg-arm
  RED  N1 the strip shows its caption box again                          -> 1
  RED  N2 the live button no longer moves the overlay (call neutered)    -> 2
  RED  N3 the overlay push is inert                                      -> 5
  RED  N4 the overlay is fed different words than the panel row          -> 5
  NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0

node _main/caption-independent-oracle.js --neg-arm
  RED  N1 -> C3 C4 C5 C6 C9
  RED  N2 -> C3 C4 C5
  RED  N3 -> B2 B3 B3b
  RED  N4 -> B1 B2 B4 B5
  RED  N5 -> A7 A8 A10 A11 A12
  RED  N6 -> A11 A14 B3
  NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0
```

---

## 5. NOT MEASURED

**No pixel measurement and no launch measurement was taken.** Nothing in this receipt
is a statement about what WebView2 actually paints.

- `_main/panel-paint-probe.py` **was not run**. It launches a shell copy; per the
  brief it is read-only. It was read (lines 380-440) and found to encode the CURRENT
  contract (`data-float`), so it was left byte-identical.
- No `run.cmd`, no `sotto_webview.py`, no `sotto_worker.py`, no WebView2 and no
  browser was started by this lane. (The 05:16:48 shell launch logged in
  `_main/panel-paint-probe.log` is another lane's — I ran only the read-only gates
  listed in section 3; see the message to the Lead.)
- The equivalence `#strip-live-button[aria-pressed="true"]` <=>
  `body[data-float]="on"` <=> overlay displayed is asserted **statically and on
  jsdom**, not on the real compositor. jsdom does resolve the module's inline
  `display` and the panel's attribute writes, which is what the B arms measure.
- The straight-band geometry (radius 0 / no gradient / hairline borders / flat fill)
  is asserted from the **bytes** of `panel.css`, not from rendered pixels.
- The history/theme/skin scroll arms of `caption-independent-oracle.js` are jsdom
  measurements, unchanged by this lane.
- `_main/webview-run.log` still contains the string `paintFloatState` — it is a
  historical run log, not an oracle, and was deliberately not edited.

---

## 6. Sweep result

A scan of the 2657 top-level files in `_main` (excluding `_gaps-*`,
`_s2-panel-before` and `_panel-*-mutant.py`) finds the old tokens in **no oracle or
probe** other than the three re-baselined files, where the remaining occurrences are
the negative assertions and the new mutants (e.g. `/id="strip-float-button"/.test(html)`
expecting `false`, and M8/N10 restoring it). Remaining matches live only in the
frozen receipts (`receipt-20261012-s1.md`, `receipt-20261012-S2.md`,
`receipt-20261012-three-overlays.md`, `receipt-botoes.md`) and in
`webview-run.log` — records, not gates.
