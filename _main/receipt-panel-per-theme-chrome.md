# Receipt — per-direction chrome, HUD removal, control move, and what is still open

**Lane:** panel (`H:\sotto\app\panel\` + `_main\_design-lane\gen_themes.py`).
**Revision this receipt describes** (sha256, first 16 hex — the tree moves, so the
numbers are part of the claim):

| file | bytes | sha256 |
|---|---|---|
| `app/panel/panel.html` | 33574 | `FA84DAB82946F0D9` |
| `app/panel/panel.js` | 83347 | `97A8C55A563E6360` |
| `app/panel/panel.css` | 43988 | `B9CE0A3653D384B5` |
| `app/panel/theme-switcher.js` | 14199 | `2ABB57757F2B9F01` |
| `app/panel/themes/theme-1..5.css` | 22903 / 23362 / 22177 / 22366 / 23678 | `DB3121D1C7E599CE` / `A67DDC0D3A8F2225` / `674C1E259B3D6642` / `DA15CC850971A040` / `71E8E9FAFDAE8503` |
| `_main/_design-lane/gen_themes.py` | 69036 | `D32CFB64891026D1` |

The five theme stylesheets are GENERATED — `py -3 _main\_design-lane\gen_themes.py`
is the only writer. Hand-editing them is lost work.

---

## 1. The gate, in one command

```
py -3 _main\_panel-chrome-arm.py --neg-arm
```

* **REAL ARM A — the box as it is** (Windows animations disabled →
  `prefers-reduced-motion: reduce`): **GREEN, 0 problems.**
* **REAL ARM B — the same page with motion emulated on**
  (`--blink-settings=prefersReducedMotion=false`): **GREEN, 0 problems.**
* **control-css** (the five `chrome--*` classes renamed in the theme files): **RED
  as expected, 22 problems** — no direction's header is on screen.
* **control-markup** (the class contract renamed in the markup): **RED as expected,
  14 problems** — all five directions' headers shown at once.

The measurement runs the REAL `app/panel/panel.html` in a **380×900** frame (the
shell's own `PANEL_WIDTH`/`PANEL_HEIGHT` at 96 dpi) and the probe asserts
`innerWidth === 380` from inside the page, so a wrong geometry is a failure and
not a silent re-measurement. `--window-size=380,900` was tried FIRST and is **not**
enough: measured, it leaves `innerWidth=492`.

**Real launch:** `py -3 _main\_launch-gate.py` → shell rc 0 in 14 s,
`sotto: BRIDGE_GATE=GREEN hasPanelElement=true url=file:///H:/sotto/app/panel/panel.html
panelSaidBridgeMissing=false`. The launch uses `--dump-dom --dump-dom-wait 10
--no-hotkey --no-hot-reload --exit-after 45` and **never** `--with-worker`.

---

## 2. What each direction got (the face), per direction

| # | direction | its own header | its own footer | what it shows that the others do not |
|---|---|---|---|---|
| 1 | Teleprompter | keeps the wordmark, then `● LENDO` | `HISTÓRICO … ▲ EM CURSO` | the live line is the largest text and the only one with a halo |
| 2 | Broadcast | `● REC · CH·01 · HH:MM:SS` (clock ticks at 1 Hz) | 5-bar level row + `AO VIVO` | the **per-line ordinal** (`001`, `002`, …), mono, and a per-line timecode |
| 3 | Manuscrito | `rascunho ao vivo … pág. 1` | `— escrito ao ouvido` | word-by-word contrast ramp on the forming line (`--w-i`/`--w-n`) |
| 4 | Cinema Card | `SOTTO · ao vivo ·` in gold | `· · ·` | the forming line sits in fog (`filter: blur`) that dissolves on commit |
| 5 | Instrumento | `■ ON` + a lit LED rail | 5-bar level row + `OUVINDO` | the live line carries a real LED element on its rail |

Each direction's own header/footer is a **separate inert block** in the markup
(`.chrome--<id>[data-chrome="head"|"foot"]`) and the theme CSS shows exactly one;
the probe asserts `shownHeads == [<that direction>]` and that the header carries
the direction's own text **in the direction's own font family**.

### 2.1 The theme button no longer cuts its own label

MEASURED by the renderer lane before the fix: `clientWidth=26` against
`scrollWidth=36–43` in all five themes, so the owner's control read `oadca`,
`nuscr`, `ema C`, `rume`, `epromp`. Cause: `.icon-button{width:28px}` in
`panel.css` won over the themes' `max-width:84px`, which declares no `width`.
Fixed in ONE rule in `panel.css` (`.theme-button{width:auto;min-width:28px;
display:inline-block;…}`). The probe now asserts `clientWidth >= scrollWidth`
per theme, and on the strip the labels read in full:
`Teleprompter 83×26`, `Broadcast 91×26`, `Manuscrito 86×26`, `Cinema Card 100×26`,
`Instrumento 98×26`.

---

## 3. The owner's removals and moves (A) — done

* **The HUD is gone.** Element, its CSS block, its rules in all five themes and
  every JS path that fed it (`hudInfo`, `hudStats`, `refreshHud`, `hudRow`,
  `hudValue`, `hudSourceText`, `paintHudFacts`, `wireStatsSource`, the 4 s poll,
  the `dom` cache entries and every `refreshHud()` call site).
  **Nothing was lost, and the two halves were checked separately:**
  * its *"Open in folder"* button was **not unique** — the transcript bar's own
    path button (`#history-root`) calls the same `revealPath(null)`, so that
    behaviour survives (the comment on `revealPath` now says it is the only
    affordance and names both callers);
  * its **Pause** button WAS unique, so it was **moved**, not deleted: it now sits
    in `.panel__controls` as a 28 px icon button with its own
    `.icon-button--danger` face. `panel.js` finds it by `[data-pause-trigger]`, so
    no wiring changed;
  * its four *"Needs `bridge.getStats()`"* rows were honest placeholders printing
    `—` for a shell call that does not exist.
* **All controls are on the TOP row, in every direction.** The cluster is
  `.panel__controls` and it is the header's row 1 in all five (the `grid-row: 2`
  that themes 2/3/5 used, and the `grid-column: 1/-1` that theme 3 used, are
  gone). The probe asserts every cluster control is inside the header AND above
  the header's mid-line.
  **What was NOT moved, on purpose:** the transcript drawer's own tools (its
  toggle, the folder path button, the search field and its two buttons). They
  belong to the drawer; a search field in the title bar would be a worse panel,
  not a cleaner one. The probe reports both groups and asserts only the cluster.
* **The shortcut is not advertised in the panel.** Every mention removed: the
  visible `<kbd>Alt</kbd>+<kbd>C</kbd>` hint and its CSS, the `ALT+C` key span in
  `the instrument`'s header and its theme rule, the `title="Hide (Alt+C)"`, and
  the prose mentions in `panel.html`, `panel.js`, `panel.css` and `surface.js`.
  The probe now asserts **zero** occurrences of `alt+c` in the body text, in any
  `title`, and in the markup. **The shortcut still works** — this was the panel's
  copy, not the registration (`app/webview/sotto_webview.py`).
* **A4 — the layout no longer depends on WHEN the surface is claimed.** The
  renderer lane's fixture writes a bare `<body>` (no `data-surface`), so theme
  rules scoped `body[data-surface="panel"]` silently did not apply there. They are
  now `body:not([data-surface="strip"])`: the panel layout is the DEFAULT and only
  the strip opts out.

---

## 4. Also delivered in this pass (B, partial)

* **The line's own clock is YELLOW on the current line and GREY on the ones left
  behind** (owner: *"ate tempo, que é amarelo o atual e cinza os que ficaram pra
  tras"*). `theme-4` uses its own gold accent (`#E4B363`), because the owner's rule
  says to use the accent when it already is yellow; the other four use a true
  yellow `#FFD24A`, and every past row (including `.caption--latest`) uses the
  theme's own muted grey. Asserted per theme on computed colour: the live one must
  be yellow, a past one must not be, and a past one must be measurably dimmer.
* **The panel is draggable by its header.** `-webkit-app-region: drag` on
  `.panel__header` (and on `.stripbar`, which is the strip's handle because the
  strip hides the header); `no-drag` on every control, declared once in
  `panel.css` so a theme cannot forget it. The probe asserts BOTH halves in every
  direction. **HONEST LIMIT:** the property is parsed (computed value reads back
  `drag`) but this shell is pywebview's EdgeChromium, which does **not** act on
  app-region — it is an Electron/Chrome-app integration, not a WebView2 one. The
  shell still has to do the moving, by either `WM_NCHITTEST` → `HTCAPTION` on the
  form, or a pointer-drag handler calling `window.moveTo`. **Nothing in the shell
  was changed by this lane.**
* **The background is transparent, and it is measured rather than asserted.**
  Alpha of `.panel`, `.captions`, `#captions-body` and the live `.caption` is read
  per theme; the probe fails on `alpha >= 1`. Measured: `.panel` 0,
  `#captions-body` **0.55**, `.captions` 0, `.caption` 0. (The first version of the
  check could not parse `color(srgb … / 0.55)` — the modern syntax this Chromium
  computes for `color-mix()` — and reported "could not be read" for a plainly
  transparent value; the parser now handles `rgb(r g b / a)`,
  `rgba(r,g,b,a)`, `color(srgb …)`, `oklab(…)` and `transparent`.)
  `--opaque` was **not** used: it changes window creation and the panel loses its
  rounded corner.
* **The level bars no longer lie, and the wave is MOUNTED AND OFF.** The
  `@keyframes sotto-2-meter` and `sotto-5-eqA/B/C` loops are DELETED: per
  `docs/research/12-audio-level-contract.md` they animated identically with
  speech, with silence and with a dead worker. In their place, `panel.js` has a
  real consumer: `wireLevel()` takes `stats.peak`/`stats.blocks` from
  `onStats`/`getStats`, keeps an N=128 ring (≈12.8 s at 10 Hz), smooths with an
  **instant attack and a ~200 ms release**, and paints the five bars through
  `--meter-h` with `transform: scaleY()` — compositor-only, no relayout.
  **With no feed the bars sit at the floor and `body[data-level="none"]` says so**,
  and the probe asserts exactly that (no `animationName`, `data-level="none"`).
  The shell exposes neither `onStats` nor `getStats` today, so this is off by
  construction, not by omission.

---

## 5. Open — stated, not hidden

* **Typing animation on the live line (D): NOT IMPLEMENTED.** The owner asked for
  it (*"faz aquela animacao de 'digitacao' que vai letra por letra"*) and the three
  traps are understood (never un-type; never rebuild per-character spans per
  partial; measure the cost on/off at 380×900). The cheapest honest technique is a
  single `--reveal` custom property on ONE wrapper (a mask / `clip-path`), with the
  revealed counter monotonic. It is not written, so there is nothing to measure.
* **The middle-of-screen surface (`data-surface="center"`): NOT IMPLEMENTED.**
* **More designs from the zips: NOT INVENTORIED.** The two zips were listed
  (ZIP 1 = the reference, 5 directions + `Ticker`/`Verdict`/`Stage`; ZIP 2 =
  `sotto-transcription-panel-designs` with its own `panels.tsx` variants) but no
  variant was ported and nothing was reported as deliberately not ported.
* **Transparency + blur: the BLUR variant was not built and therefore not
  measured.** Only the `rgba` half is done. The owner's warning is recorded
  (`backdrop-filter` reads and blurs the backdrop, and a box rewritten on every
  partial is the worst case for it): if it is added, it must be a separate static
  layer with the smallest radius, never animated, and measured against `rgba` at
  380×900 — and `rgba` stays the default unless the numbers say otherwise.
* **Animation cost with and without:** the instrument now WORKS
  (`_main/_panel-anim-cost-arm.py` beacons a real measurement out of a page served
  over 127.0.0.1, on real wall-clock timers). Its FIRST results are in
  `_main\_panel-anim-cost.log`, and they say something worth saying plainly: over
  6 s at 8 partials/s the caption path costs **~0.01–0.25 ms per partial**, the
  frame channel is flat at p50 16.7 / p95 16.8 / max 16.8 ms in EVERY arm, and
  there is **one** long-animation-frame entry in the whole window (the start-up
  frame) — i.e. **the caption path is not the thing that stalls a panel at this
  size, and the per-direction animations are below the instrument's floor.** The
  `width`-animated control was ALSO not caught, so the instrument is not yet
  sensitive enough to certify a compositor-only animation; the thresholds are
  currently wrong (they compare the start-up frame's `duration` across arms, which
  is noise). **This must be fixed before any cost claim is made**, and it is the
  first thing to do next.
* **Quit (`#quit-button`) — LOCATED, NOT REMOVED, and BLOCKED on the tray.** It is
  the power-symbol button in `.panel__controls` (top row), `title="Quit Sotto
  (stops the captions and closes the app)"`. It calls `bridge.quit()` — the
  WebView2 shell's `quit(reason)` (`app/webview/sotto_webview.py:3425`), i.e. the
  SHELL closes and the worker it owns goes with it. It is the only control that
  closes the app, and there is no tray yet (`grep pystray|NotifyIcon|
  Shell_NotifyIcon` in `app/` = 0), so removing it today would leave the owner with
  the Task Manager as the only way out. **Pending removal, condition: the shell
  proves the tray's Quit closes BOTH the shell and the worker.**
* **Clear (`#clear-button`) — LOCATED, NOT REMOVED, and it needs a decision.** It
  is the bin-symbol button in `.panel__controls` (top row). Its three answers:
  1. **the view** — yes: `dom.list.replaceChildren()`, the placeholder comes back,
     `#caption-list` hidden, `updateLiveHint()`;
  2. **the transcript on disk** — **no**: it makes no `historyApi` call of any
     kind, so `history/…` is untouched;
  3. **the engine's state** — **YES**: `engine.reset()` (drops the committed and
     provisional words and the re-cover watermark `emittedStart`/`emittedWords`/
     `emittedEnd`), `clearTimeout(holdTimer)`, `committedByStart = new Map()`, and
     `bridge.clearApplied(0)` tells the shell.
  Because it touches the ENGINE, the removal takes a capability away and is
  **left to the owner** — per the instruction not to remove it unilaterally.
  No keyboard shortcut fires Clear (the only `keydown` handler is on history
  rows; `Escape` closes the pause dialog natively), so nothing else would have to
  go with it.
* **The final control list, per surface** (what SURVIVES):
  * **panel surface, top row (5):** theme button, Clear, Quit, Hide, Pause.
  * **panel surface, transcript drawer (its own, unchanged):** drawer toggle,
    folder path button, search field, Search, Clear-search, and the per-line
    "Show in folder" in the drawer body.
  * **strip surface (4):** Live on/off, Pause, Open panel, theme button.
  * The HUD is gone; if Quit and Clear also go, the panel's top row is **three**:
    theme, Hide, Pause.

---

## 6. The capture, and what it does and does not show

`py -3 H:\aireplay\_main\render-panel-temas.py` → **VERDICT: PASS**, five captures
+ `panel-temas-comparacao.png`, `window census 114 samples / 0 visible`,
3 370 229 B of the 200 MB budget. The fixture was regenerated from the CURRENT
`panel.html` (its caption lines are extracted from that document's own prose, and
they now read the new comment text — which is how the re-capture is provably not
stale).

**What it shows:** the caption skin per direction — typeface, size, rail, halo,
the live line's colour, and the five accents. In the current capture the live
line's clock is visibly **yellow** (`10:22:02`) against the closed rows.

**What it does NOT show, and this matters for reading the image:** the fixture is
a CAPTION instrument. Its own `fixture-geometry.css` pins `html,body{380px;900px}`
and makes `.panel` `position:absolute;inset:0`, and the fixture arranges the
caption parts itself — so in `panel-temas-comparacao.png` the header appears
part-way down the frame, overlapping caption text. That is the fixture's
arrangement, **not** the panel's layout: in the real document the header is the
first row and the control cluster is on it. Control placement is proved by
`_main\_panel-chrome-arm.py` (which asserts `innerWidth === 380` and the cluster's
position from inside the real page), **not** by the capture.

---

## 7. The instrument traps this pass earned

1. `--dump-dom` on an iframe's document does not exist: a `file://` iframe is
   cross-origin, so the payload written inside it is invisible. The frame's own
   poll mirrors it out, and that needs `--allow-file-access-from-files`.
2. `--window-size=380,900` does **not** set the viewport here (measured:
   `innerWidth=492`). The capture path resizes; the `--dump-dom` path does not.
3. A CSS animation added by a COPY is a difference between the copy and the
   shipped panel; every arm states its differences, and this pass has exactly one
   (the two extra `<script>` tags, no CSP change).
4. `alpha()` must understand `color(srgb … / a)` and `oklab(… / a)`, or it reports
   a transparent panel as unreadable.
5. A control that goes RED for the wrong reason is not a control: the control arms
   now run in the same 380×900 frame as the real arms.
6. A measurement that does not say which geometry it used describes a layout
   nobody sees — hence `innerWidth` in every payload.
