# Receipt — re-baselining the panel oracles to "the caption ships OFF"

**Date:** 2026-10-13 (~10:30 -03:00)
**Lane:** re-baseline of the panel gates after the Lead re-applied the owner's contract.
**Subject bytes (FROZEN by the brief, NOT edited by this lane):** `app/panel/panel.{html,css,js}`,
`app/panel/strip-drag.js`, `app/panel/caption-float.{js,css}`.
**Write scope actually used:** `_main/**` only. No `app/panel/**`, `app/webview/**`, `worker/**`
or `docs/**` byte was written. Nothing was `git add`ed, committed, stashed or reverted.

Every oracle edit below changes the CHECK to the shipped contract and leaves a control that can
still go RED. No threshold was loosened and no arm was deleted.

All commands were run with `$env:TMPDIR='I:\cc-tmp'` from `H:\sotto`. Node v24.8.0, jsdom 29.1.1.

---

## 1. Contract being asserted now (measured, not assumed)

`app/panel/panel.js` (worktree, 2026-10-13):
- `:264` `let liveEnabled = false;` — the caption ships OFF.
- `:2126-2179` `applyLiveEnabled(enabled)` ends by calling `applyFloat(liveEnabled)` (`:2159`).
- `:2284-2302` `applyFloat(on)` writes `body[data-float]`, `setStripHeight(on ? FLOAT_HEIGHT : STRIP_HEIGHT)`,
  `syncCaptionFloat(want)`, and calls `bridge.setPanelSurface('strip', ...)` ONLY when
  `currentSurface() === 'strip'` (`:2299`).
- `STRIP_HEIGHT = '40px'` (`:70`), `FLOAT_HEIGHT = '220px'` (`:71`).
- `:2195` `word = 'Captions off';` (was `'Live off'`).
- REMOVED: `dom.stripFloatButton`, `paintFloatState()`, `toggleFloat()` (comments at `:122-128`,
  `:2260-2263`).

`app/panel/strip-drag.js` (tracked at `e72e785`; HEAD `panel.html` has 0 inline drag bindings):
it is the file that carries `KEY = "sotto:strip-offset"`, `{x,y,v:1}`, `bridge.setStripOffset`,
`--strip-move-x/y` and the read-back-before-paint.

---

## 2. Files changed by THIS lane

| file | change |
|---|---|
| `_main/_s2-bar-dom-oracle.js` | B arm re-baselined to ships-OFF; mutants N5/N6 added |
| `_main/caption-independent-oracle.js` | stub fidelity + A13/A13b/A13c re-baselined; mutants N7/N8 added |
| `_main/_panel2-dom-probe.js` | ARM S/T/O expectations re-baselined (CRLF file; see §7) |
| `_main/botoes-lane-oracle.js` | E1-E5/E8 now read `strip-drag.js`; M5 retargeted; copy-verify extended |
| `_main/botoes-lane-gesture-oracle.js` | ARM 7 control now mutates a copy of `strip-drag.js` |
| `_main/receipt-20261013-live-ships-off.md` | THIS file |

Other files shown dirty by `git diff` under `_main/` (mutants, receipts, `strip-*.py`,
`_audit-verify/js/*`, `_tmp-panel-noreveal/**`, `_panel-no-wire-revive.js`) were already dirty
when this lane started and were **not** written here.

---

## 3. OLD assertion -> NEW assertion

### 3.1 `_main/_s2-bar-dom-oracle.js`
| arm | OLD (interim "ships pressed") | NEW (ships OFF) |
|---|---|---|
| B1 | live button ships `aria-pressed="true"` | ships `aria-pressed="false"` (the caption is OFF) |
| B3 | click -> OFF `['false','off','none']` | click -> ON `['true','on','block']` |
| B4 | click -> ON `['true','on','block']` | click -> OFF `['false','off','none']` |
| B5 | pressed read after click 2 | pressed read after click 3 (an extra click back ON so B6-B13 still measure the floated overlay) |
| NEG | 4 mutants | + N5 `applyLiveEnabled` no longer calls `applyFloat(liveEnabled)`; + N6 `let liveEnabled = false` -> `true` |

B6-B14 are unchanged: B14 is still the click that lowers the overlay, and B13 still requires
`display:block` with the panel detached.

### 3.2 `_main/caption-independent-oracle.js`
| item | OLD | NEW |
|---|---|---|
| stub `setLiveEnabled` | returned `{liveEnabled:true}` unconditionally | echoes `Boolean(on)` — what the real shell does. The old stub made the SECOND click's resolved promise "correct" the FIRST, moving the overlay asynchronously: the stub, not the panel, decided A19. |
| A13 | ships `'true'` | ships `'false'` |
| A13b | click -> OFF `['false','off','none']` | click -> ON `['true','on','block']` (renamed) |
| A13c | click -> ON `['true','on','block']` | click -> OFF `['false','off','none']`, moved after A20 |
| A13d | — (new) | click back ON, `['true','on']`, so ARM B's floated-page arm (B3) still runs floated |
| A14/A15/A19/A20 | unchanged | unchanged (now reached with the caption ON) |
| A3 comment | said "the app ships live ON" | says it ships OFF; the assertion (`[true,'block']`) did not change |
| NEG | 6 mutants | + N7 delete the `applyFloat(liveEnabled)` call; + N8 `liveEnabled` defaults `true` |

### 3.3 `_main/_panel2-dom-probe.js`
| arm | OLD | NEW |
|---|---|---|
| S — toggle announces its state | `'true'` | `'false'` |
| S — strip word is a SHORT status | `'Live'` | `'Captions off'` (the title sentence "Receiving captions ..." is unchanged) |
| S — strip state carries the LIVE class | `[true, true]` | `[false, true]` (is-live follows `liveEnabled=false`; the dot is still a painted shape) |
| T — toggle flips | `['true','false']` | `['false','true']` |
| T — shell is told, NEW value | `[false]` | `[true]` |
| T — second click | "turning it back on carries true" `[false,true]` | "turning it back off carries false" `[true,false]` |
| T — unwired reports its state | `'false'` | `'true'` (one click from OFF) |
| O — shell surface calls | `[{strip,strip-float-on},{panel,strip-open}]` | `[{strip,strip-float-off},{panel,strip-open}]` |

### 3.4 `_main/botoes-lane-oracle.js` — the drag arms were STALE, not connected to this change
**Investigation first, as ordered.** The E arm reads the bytes of `panel.html` for a drag that is no
longer there. Measured:
- `git show HEAD:app/panel/panel.html` contains **0** `bar.addEventListener("pointerdown"` and **0**
  `var KEY = "sotto:strip-offset"`; it already points at `<script src="strip-drag.js"></script>`.
- `app/panel/strip-drag.js` is tracked (last touched by `e72e785` "THE STRIP DRAG WORKS. The cause
  was the panel CSP blocking its own inline script."), while this oracle was last committed in
  `e36a09b` — i.e. the oracle predates the drag's externalisation.
- The stale bytes therefore belong to a DIFFERENT lane's rework (CSP fix), not to the live-button
  change in this brief. The oracle was re-baselined to the shipped drag contract; no threshold moved.

| arm | OLD | NEW |
|---|---|---|
| read | `panel.html`, `panel.css` | + `strip-drag.js` |
| E1 | `getElementById("strip-controls")` and `bar.addEventListener("pointerdown"` in `panel.html` | same predicates against `strip-drag.js` |
| E2 | `addEventListener("pointermove")` + `start.ox + dx` in `panel.html` | against `strip-drag.js` |
| E3 | `var KEY = "sotto:strip-offset"` in `panel.html` | against `strip-drag.js` |
| E4 | `JSON.stringify({x:Math.round(off.x),y:Math.round(off.y),v:1})` in `panel.html` | against `strip-drag.js` |
| E5 | `typeof bridge.setStripOffset === "function"` in `panel.html` | against `strip-drag.js` |
| E8 | `var offset = read();\n paint(offset);` in `panel.html` | against `strip-drag.js` |
| E6/E7/E9 | unchanged | pass against `panel.css`/`panel.html` |
| M5 | mutant applied to `panel.html` | mutant applied to `strip-drag.js` (file field + tag) |
| copy verify | `panel.html, panel.css` | + `strip-drag.js` |

### 3.5 `_main/botoes-lane-gesture-oracle.js` — the run-time control was vacuous
The ARM 7 mutant replaced `window.addEventListener("pointermove"` **inside the unmutated
`panel.html` read a second time**, and the "really mutated" check compared the marker against two
copies of the same unmutated file, so it asserted `[false,false]` and could not fail. The gesture
now lives in `strip-drag.js`, so the mutant anchors there.

| item | OLD | NEW |
|---|---|---|
| ARM 7 mutation | `load(PANEL, mutateHtml)` replacing a string in `panel.html` (no longer present) | scratch copy of `app/panel`, `strip-drag.js`'s `pointermove` binding renamed, copy loaded whole |
| check 7 | `[false,false]` (vacuous) | `[true,false]` — the copy carries the marker, the shipped bytes do not |
| 7b / 7c | failed (mutant still recorded/painted) | `[null,0]` and `['0px','0px']` |
| header | "including the inline gesture" | "including the EXTERNAL strip-drag.js" |

---

## 4. Commands per gate and measured output

### 4.1 Positive colour (shipped bytes)
```
$env:TMPDIR='I:\cc-tmp'; cd H:\sotto
node _main/_s2-bar-dom-oracle.js
node _main/caption-independent-oracle.js
node _main/_panel2-dom-probe.js
node _main/botoes-lane-oracle.js
node _main/botoes-lane-gesture-oracle.js
```
Measured:
| gate | result | rc |
|---|---|---|
| `_main/_s2-bar-dom-oracle.js` | `23 check(s), 0 failed` / `VERDICT: PASS` | 0 |
| `_main/caption-independent-oracle.js` | `49 check(s), 0 failed` / `VERDICT: PASS` | 0 |
| `_main/_panel2-dom-probe.js` | `RESULT: GREEN — 83/83 arm(s)` | 0 |
| `_main/botoes-lane-oracle.js` | `34 check(s), 0 failed` / `VERDICT: PASS` | 0 |
| `_main/botoes-lane-gesture-oracle.js` | `11 check(s), 0 failed` / `VERDICT: PASS` | 0 |

Key measured values on the live button (DOM, real bytes, not text):
- initial: `aria-pressed="false"`, `body[data-float]="off"`, `--strip-height=40px`, overlay `display:none`
- click 1: `["true","on","block"]`
- click 2: `["false","off","none"]`
- bridge surfaces on the strip: `strip-float-on` / `strip-float-off`; on the panel surface no
  `setPanelSurface` call from `applyFloat`.

### 4.2 Negative colour

**`node _main/_s2-bar-dom-oracle.js --neg-arm`** -> `NEG-ARM VERDICT: PASS`, rc=0:
```
RED N1 the strip shows its caption box again -> 1 failing check(s)
RED N2 the live button no longer moves the overlay (the panel->overlay call is neutered) -> 2
RED N3 the overlay push is inert -> 5
RED N4 the overlay is fed different words than the panel row -> 5
RED N5 the live button no longer drives the overlay (applyFloat call deleted) -> 5
RED N6 the caption ships ON again (liveEnabled defaults true) -> 6
```
N5 makes B3/B4/B13/B14 disagree (button/attribute vs overlay); N6 makes B1/B3/B4/B5/B14 stale.

**`node _main/caption-independent-oracle.js --neg-arm`** -> `NEG-ARM VERDICT: PASS`, rc=0:
```
RED N1 the theme/skin guard is never armed -> 5 (C3|C4|C5|C6|C9)
RED N2 the pin writes the TOP instead of the bottom -> 3 (C3|C4|C5)
RED N3 the page paints its solid slab behind the caption -> 3 (B2|B3|B3b)
RED N4 the meter plate comes back -> 4 (B1|B2|B4|B5)
RED N5 the overlay can no longer build itself -> 5 (A7|A8|A10|A11|A12)
RED N6 the shell cannot see the float state on <html> -> 3 (A11|A14|B3)
RED N7 the live button no longer drives the overlay (applyFloat call deleted) -> 8 (A13b|A14|A15|A19|A20)
RED N8 the caption ships ON again (liveEnabled defaults true) -> 9 (A13|A13b|A14|A15|A19)
```

**`node _main/botoes-lane-oracle.js --neg-arm`** -> `NEG-ARM VERDICT: PASS`, rc=0:
```
RED M1 the live button is deleted -> 4
RED M2 the live OFF state loses its word -> 1
RED M3 the right panel caption label comes back -> 2
RED M4 hide stops being the rightmost control on the strip -> 1
RED M5 the drag gesture pointerdown binding is deleted (from strip-drag.js) -> 1   <- the retargeted control
RED M6 the caption-float.css link is deleted -> 2
RED M7 the strip shows its caption box again -> 1
RED M8 the removed Linhar button comes back -> 2
```

**`_main/botoes-lane-gesture-oracle.js`** carries its control INSIDE the one command (there is no
`--neg-arm` flag): `7 CONTROL ... = [true,false]`, `7b = [null,0]`, `7c = ['0px','0px']`, all PASS
in the same `11 check(s), 0 failed` run.

**`_main/_panel2-dom-probe.js`** has no `--neg-arm` flag either; its documented control is
`SOTTO_PANEL_DIR` against a broken copy. Two one-line mutants of `panel.js` in scratch trees under
`I:\cc-tmp`:
```
MUTANT A: delete 'applyFloat(liveEnabled);'
  RESULT: RED — 1 violation(s) — 82/83 arm(s)
    FAIL [O] with the shell call present, the panel asks the SHELL to switch surface
  rc=1
MUTANT B: 'let liveEnabled = false;' -> 'let liveEnabled = true;'
  RESULT: RED — 8 violation(s) — 75/83 arm(s)
    FAIL [S] the toggle announces its state
    FAIL [S] the strip word is a SHORT status, and the shell sentence is still readable
    FAIL [S] the strip state carries the LIVE class, and the dot is a shape not a colour
    FAIL [T] the toggle flips aria-pressed on a click
    FAIL [T] and the shell is told, with the NEW value
    FAIL [T] turning it back off carries false
    FAIL [T] and it still reports the state it is showing
    FAIL [O] with the shell call present, the panel asks the SHELL to switch surface
  rc=1
```
So each touched panel2 arm has a run that turns it RED.

### 4.3 Neighbours re-run (not edited by this lane, kept as controls)
```
node _main/strip-float-oracle.js      -> 50 check(s), 0 failed / VERDICT: PASS   (asserts the NEW contract: S9 Linhar GONE, S10b applyLiveEnabled->applyFloat, W10 strip-only guard)
node _main/three-overlays-oracle.js   -> 31 check(s), 0 failed / VERDICT: PASS   (already re-baselined, with its own N9 delete-applyFloat control)
node _main/panel-row-identity-oracle.js -> 7/7 GREEN / VERDICT: PASS
```

---

## 5. Search for every other assertion of the OLD contract

Patterns searched over `_main/**` (excluding `_gaps-*`, `_s2-panel-before`, `_panel-*-mutant.py`):
`stripFloatButton`, `strip-float-button`, `paintFloatState`, `toggleFloat`,
`strip-button--float`, `'Live off'`, `liveEnabled = true`, "ships pressed", "ships live ON".

| hit | disposition |
|---|---|
| `_s2-bar-dom-oracle.js` | re-baselined (§3.1) |
| `caption-independent-oracle.js` | re-baselined (§3.2) |
| `_panel2-dom-probe.js` | re-baselined (§3.3) |
| `botoes-lane-oracle.js` | drag arms re-baselined (§3.4); A7 already asserts Linhar GONE |
| `botoes-lane-gesture-oracle.js` | control re-baselined (§3.5) |
| `strip-float-oracle.js` | NO change needed — it asserts the NEW contract |
| `three-overlays-oracle.js` | NO change needed — already re-baselined (N9/N10) and PASSES |
| `revive-panel-render-test/_panel-under-test.js` | **generated at run time** by `revive-pipeline-oracle.py:138` from today's `panel.js`; it is not an oracle and its stale on-disk copy is overwritten on every run |
| `_panel-no-wire-revive.js` | generated at run time by `revive-pipeline-oracle.py:556`; stale on disk, overwritten per run — NOT edited |
| `_tmp-panel-noreveal/**` | another lane's scratch tree, not an oracle — NOT edited |
| `receipt-*.md` | historical prose records — NOT edited |

---

## 6. Unrelated REDs found while searching (not touched, not caused by this change)

- `node _main/flicker-dom-oracle.js` -> `ReferenceError: document is not defined` at load
  (`:15`). It is a fragment expecting a host document; it references none of the old-contract
  tokens. Pre-existing, **NOT MEASURED** meaningfully here.
- `node _main/redux-live-overlay-panel-oracle.js` -> `ERR_INVALID_ARG_TYPE` `readFileSync(undefined)`
  at `:13`. Pre-existing; references none of the old-contract tokens.
- `_main/panel-paint-probe.py` and `revive-pipeline-oracle.py` were **NOT run**: the first launches a
  shell copy, the second launches Chromium (ARM P). FORBIDDEN by the brief.

---

## 7. NOT MEASURED (stated plainly)

- **No pixel/launch measurement.** Nothing here starts the app, the shell, the worker, WebView2,
  `run.cmd` or a browser. `_main/panel-paint-probe.py` was not run. The real WebView2 paint of the
  40px band, the 220px floated caption and the overlay's on-screen geometry is **UNMEASURED**.
- **No shell log, no hot reload, no Alt+C.** The shell half of `setPanelSurface` / window resize is
  only asserted through a stub; whether the real shell resizes to 40/220px is **UNMEASURED**.
- **No worker / audio / network.**
- The bridge stubs echo the values they are given; a real shell that replies with a different
  confirmed state is outside these oracles (the panel's own correction path is exercised by
  `audit.live` only).
- `_panel2-dom-probe.js` is a **CRLF** file while the other `_main` instruments are LF. It was kept
  CRLF (its native form), which is why its diff is line-ending-consistent; the one pre-existing bare
  LF in it was normalised to CRLF.
- This receipt is prose; the oracle bytes are the evidence.

## 8. Acted-on requests for the product (not edited by this lane)

None. No product file looked wrong; the frozen `app/panel` bytes match the contract in §1 as
measured by the gates above. `panel.css`'s strip order and the straight band are asserted by
`strip-float-oracle.js` S20b/S21 (PASS) and were not demanded again here.
