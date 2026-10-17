# 2026-10-17 — AS SETE CORRECOES DO PAINEL (o dono: *"printa tudo, leia e arruma tudo"*)

Lane: UI defects reported by the owner from the running app. The app was **running**
(shell pid 36336, panel hwnd 9640730) and was **never restarted, killed or launched** by
this lane. No panel edit could be seen by the running instance, and the reason is a fact,
not an excuse — see §0.

---

## §0 THE INSTRUMENT THAT DECIDED HOW EVERYTHING BELOW WAS MEASURED

**`hot_reload.py` IS NOT ARMED IN THE OWNER'S INSTANCE.** `sotto_webview.py:11296`:
`if args.hot_reload:` — and `:11288-11295` records that `run.cmd` passes no flag, that hot
reload "was armed in production" until 2026-10-12 and that the default now flips to OFF.
The running shell was started without `--hot-reload`, so **editing `app/panel/*` cannot
change what is on his screen** until the Lead restarts it. Verified, not assumed: I edited
`button-contract.css`, waited, re-captured hwnd 9640730 and the header pixels were
**byte-identical** (`I:\cc-tmp\before-17a.png` vs `I:\cc-tmp\after1-17a.png`: wordmark rows
37-45 / controls 22-33 in both).

So the measurement rig is a **render copy of the shipped page**, not the owner's window:

* `_main/_render-1710/render.ps1` — Edge `--headless=new`, `--force-device-scale-factor=1`,
  `--window-size=380,900` / `1040,150`, `--virtual-time-budget=6000`. Nothing of the
  owner's app is touched; a fresh `--user-data-dir`, launched `-WindowStyle Hidden`.
* the BEFORE tree is `git archive HEAD app/panel` (**the committed bytes**, not a copy of
  my working tree), the AFTER tree is the same tree with my six files over it, so the only
  difference between a pair is the change under test.
* `_main/_render-1710/probe-inject.js` + `probe.ps1` — a `--dump-dom` read of
  `getComputedStyle` of the real elements. This is what measures the things pixels cannot:
  a 1 px `box-shadow` ring, a 1×1 collapsed element, the colour of a dot.
* `_main/_render-1710/drag-test.html` + `drag-run.ps1` — loads the **real `strip-drag.js`**
  against a stub bridge that counts `beginWindowDrag`, and presses seven things.

The rig reproduces the live defect exactly where it can be checked: the live capture
(`I:\cc-tmp\before-17a.png`, 380×900) and the rig's BEFORE render put the control row at
glyph rows **22-33** and the `sotto` wordmark at **37-45** — the same numbers from two
independent instruments.

| artefact | what |
|---|---|
| `I:\cc-tmp\before-17a.png` + `before-c-header.png` + `before-corner-tl2.png` | the LIVE window, before |
| `_main/_render-1710/shot-before-panel.png`, `strip-b.png` | BEFORE render (HEAD bytes) |
| `_main/_render-1710/final-after-panel.png`, `final-after-strip.png` | AFTER render |
| `_main/_render-1710/strip-b-state.png` / `strip-a-state.png` | the state readout, 5× |
| `_main/_render-1710/drag-test.html` | the drag-surface instrument |

---

## 1 — HEADER: THE CONTROL ROW AND THE WORDMARK WERE ON TWO LINES

**Wrong, measured.** The header's control row painted at glyph rows **22-33**
(centroid 28.6) and the `sotto` wordmark at **37-45** (centroid 40.7) — **12.1 px apart**,
in the live capture *and* in the rig. Mechanism, from the computed styles:
`button-contract.css` pins `.panel__controls` to `position: fixed; top: 14px; height: 28px`
while the header it belongs to is 56 px tall (`panel.css:3303`, the F8 block) with 14 px of
slab padding — so the row hung from the padding and the wordmark sat on the header's centre.

**Changed** — `app/panel/button-contract.css:50-63`:
`top: 14px` → `top: calc(14px + (56px - 28px) / 2)` (= 28 px), written as the arithmetic it
is, still ONE value for all 45 themes. In the contract file, not in a theme, so it cannot
move between designs.

**After** — controls glyphs **36-47** (centroid 41.5) against the wordmark's 40.7: the gap
is **0.8 px**. Evidence: `_main/_render-1710/hdr-b.txt` vs `hdr-a2.txt`, crops
`after-c-header.png`. Not visible in the owner's window until the Lead restarts.

---

## 2 — THE GRAB DOTS: GREY PILLS, NOT ACCENT DOTS, NOT CENTRED

**Wrong, measured.** `panel.css:.stripbar__grip` painted
`radial-gradient(circle, var(--text-faint) 1px, transparent 1.2px)` on a 4×4 px tile inside
a 12×22 px box → **three columns × five rows** of dots (`strip-b.png`: the grid is at
x 68/72/76, rows 10-11/14-15/18-19/22-23/26-27) — the owner's "five grey vertical pills".
Two more measured facts: the colour was the muted token at 0.55 opacity, so in theme-1 the
brightest pixel **inside the grip's own box is 25** against a ~26 background (invisible);
and `align-self: stretch` anchored the pattern to the bar's top edge.

**Changed** — `app/panel/panel.css:1735-1763`: `--accent` instead of `--text-faint`,
`background-repeat: repeat-y` + `background-position: center` (ONE centred column, so
marks cannot merge into a pill), `align-self: center`, `border-radius: 0`, `opacity: 0.85`.

**After** — brightest pixel in the same box **208** (`rgb(242,233,216)` = theme-1's
`--accent`), a single column at x 71-72, rows **64-84**, inside a bar spanning rows 62-87 —
centred. Evidence: `strip-a.png`, `frame-rules`/computed `gripBg` in `probe` output.

**NOT AS THE BRIEF SAID, and I will not pretend otherwise.** The brief places these dots at
"y≈281-294 inside a 900px panel". Measured on the live panel surface and in the rig:
**they are not there** — `.stripbar` is `display:none` on the panel surface
(`panel.css:1522-1531`) and the probe reads `grip rect = 0,0,0,0` on that surface. The grip
exists only on the strip. What I fixed is the grip as it exists.

---

## 3 — THE STATUS INDICATOR WAS TEXT

**Wrong, measured.** Two surfaces, two words. The strip painted **93 px** of readout
(`strip-b-state.png`, "● STARTING"). The panel header painted
`.chrome__state` at rect **414.25,34.5 → 63.75×15** — that is the `LENDO`/`EM ESPERA` pair
of `panel.html:216-252`; the live capture shows `● LENDO` at x 325-380.

**Changed** — `app/panel/panel.css:3332-3349`: `.chrome__state` and `#strip-word` become
**visually hidden** (1×1, `clip-path: inset(50%)`), and `:3384-3401` gives the dot the state:
an opacity-only breathe keyframe on `body[data-state="live"]` (the same pattern
`gen_themes.py` P2-1 uses for the REC lamp — a `box-shadow` spread keyframe is a paint
property per frame), with `prefers-reduced-motion` honoured. Colours are the theme's own
(`--idle`/`--ok`/`--error`), already applied by the generated themes.

**WHY NOT `display:none`.** The word IS the real state — `.chrome__on`/`.chrome__off`
(`panel.css:2515-2528`) are switched by `<body data-state>`, which `panel.js` mirrors from
the worker's status. `display:none` would delete the only place the document says what state
it is in. Clipping keeps it in the accessibility tree, so nothing is invented.

**After** — strip: **93 px → a 6 px dot** (`strip-a-state.png`). Panel header:
`.chrome__state` rect **1×1** at 471,41.5 (was 63.75×15). `panel.html` needed no change.

---

## 4 — THE RIGHT PANEL WAS VERTICALLY CENTRED

**Wrong.** `sotto_webview.py:1014` was `y = work['y'] + round((h - panel_height) / 2)`.

**Changed** — the new formula, exactly: **`y = work['y'] + m`** — the SAME `m` the right
edge already uses (`max(0, min(margin, w/8, h/8))`, `:1008`), so the panel hangs
`PANEL_MARGIN` (12) from the top and from the right; the width is untouched. Containment is
arithmetic: `panel_height` is clamped to `h - 2*m` (`:1011`) and both clamps below still run.

**Measured on this host's REAL work area** (`Screen.Primary.WorkingArea` = 1920×1032):

| | x | y |
|---|---|---|
| old formula | 1528 | **66** |
| new formula | 1528 | **12** |

and 66 is exactly where the live window is sitting right now (hwnd 9640730 rect `(1528,66)`),
which is the old formula's output — proof the running instance still has the old code.
Containment held on 7 work areas including degenerate ones (`100×100` → `59,19 34×76`;
negative origin → inside). **This one needs a shell restart to be seen; this lane may not
do it.** Lead: restart the app and the panel will sit 54 px higher.

---

## 5 — THE WHOLE BAR IS THE DRAG SURFACE (and a press is still a press)

**Wrong, measured, and smaller than the brief says.** The whole-div part was **already
true**: `strip-drag.js:56-64` binds `pointerdown` on `#strip-controls` (the whole `.stripbar`)
and on `.panel__header`, and asks the shell for ONE native drag. What was broken is the
other half — a gesture that belonged to a control was taken by the window. The harness
against **HEAD's** `strip-drag.js` returned: bar 1, grip 1, header 1, header gap 1, `<button>`
0, `<button>` in a `<label>` 0, **`role="button"` 1**, **bare `<label>` 1** → **VERDICT FAIL**.
A `role="button"` and a `<label>` inside the bar moved the WINDOW instead of pressing.

**Changed** — `app/panel/strip-drag.js:33-53`: `isControl()` now matches the set of things
that ACT like a control (`button, a, input, select, textarea, summary, label, [role=button],
[role=link], [role=checkbox], [role=switch], [role=tab], [role=menuitem],
[contenteditable=true], [data-no-drag]`). `app/panel/panel.css:506-524`: the panel's cluster
gets the `-webkit-app-region: no-drag` declaration the strip's buttons already had — the
declaration half was missing, the behaviour half was not.

**After** — the same harness: bar 1, grip 1, header 1, header gap 1, button 0, labelled 0,
**role=button 0, bare label 0** → **VERDICT PASS**. The dots stay `aria-hidden` and carry no
handler; they are an affordance only, as asked.

---

## 6 — THE CAPTION BUTTON ONLY CHANGED THE BUTTON

**Wrong, and the code is quotable.** The click was `applyLiveEnabled(!liveEnabled)`
(`panel.js:2013`); that function flipped a module-level boolean and repainted `aria-pressed`,
`data-state`, the label and the title **before it asked anybody**. Then it asked the shell and
treated the answer as a confirmation:

```js
result.then((payload) => { const confirmed = payload.liveEnabled ...; applyLiveEnabled(confirmed); })
```

while the shell resolves `{liveEnabled: <the value the page asked for>}`
(`sotto_webview.py:3607-3611`). **The page confirmed itself** — which is precisely the
owner's *"quando eu clico em legenda, ele simplesmente muda o botao"*.

**Changed** — `app/panel/panel.js`:
* `requestCaptionOverlay()` (`:2213-2242`) — the click asks the shell and **paints nothing**.
* `watchCaptionWindowState()` (`:2246-2259`) — a `MutationObserver` on
  `data-caption-window`, the attribute the shell's own `show_caption_window` writes when it
  has actually shown or hidden its caption window (`sotto_webview.py:7177-7179`). The paint
  comes from there, so a refused overlay leaves the button where it was, and a window already
  on screen paints the button on with no click at all.
* `applyLiveEnabled()` (`:2265+`) is now a **painter**, never a switch. The Promise echo and
  the `dataset.state` self-mutation tail are **deleted** (kept as a comment naming what went).
* the click handler (`:2013-2020`) and the arming (`:629`) were rewired to match.

**NOT verified at runtime.** Both halves of the read-back already exist in the shipped
shell, so no Python change was needed — but the running instance cannot execute the new JS
until it is restarted, and I may not click the owner's window. Verification: static review of
the call graph (one door to the shell, no caller of `applyLiveEnabled` asks anything) +
`node --check panel.js` rc=0.

---

## 7 — THE WINDOW EDGE: WHITE, SQUARE, NOT TRANSPARENT

**What the window actually is — measured on hwnd 9640730, not assumed:**
`GetClientRect` **380×900 == `GetWindowRect` 380×900**; `GetWindowLong(GWL_STYLE)` =
`0x06010000` = `WS_CLIPSIBLINGS|WS_CLIPCHILDREN|WS_MAXIMIZEBOX` — **no `WS_CAPTION`, no
`WS_THICKFRAME`, no `WS_BORDER`**; exstyle `0x080100A8` = `WS_EX_NOACTIVATE|WS_EX_TRANSPARENT|
WS_EX_TOOLWINDOW|WS_EX_APPWINDOW` and **not `WS_EX_LAYERED`**. So the frame is **not** a title
bar. The owner was told it was; measurement says otherwise and I am reporting the measurement.

**What WAS painting it.** `getComputedStyle(#panel).boxShadow` =
`rgba(0,0,0,0.6) 0 28px 90px, rgba(255,255,255,0.1) 0 0 0 1px` — a **1 px white ring around
the slab**, from the generated `--shadow-slab` (`gen_themes.py:1040`). Five of the 45 designs
ship that ring (white 0.10/0.12/0.14, mint, gold). Both halves of the token are worthless on a
slab that fills the window: the drop shadow is clipped away (`panel.css:181-182` says so).

**The corners.** `--radius-lg` is `0px` in four designs, and `html`/`body` carry
`rgba(11,15,20,0.98)` clipped by the same radius → the whole window was opaque and square.

**Changed** — `app/panel/panel.css:3423-3454` (`!important`, because the generated
`:root[data-theme=...] .panel` selectors are 0,3,0 and `panel.css` is linked BEFORE the
themes, `panel.html:49` vs `:60-72`): the base INSET shading is restored (still painted,
inside, no frame), and a **12 px radius floor** is put on the panel surface (`html`, `body`,
`.panel`, `.panel::before`). The strip keeps `border-radius: 0` — a straight band by the
owner's own ruling (`panel.css:2919`).

**The mechanism, named as asked:** `FormBorderStyle = None` (pywebview `winforms.py:271`,
already on via `frameless=True` — measured above), WebView2 `DefaultBackgroundColor =
Color.Transparent` (`edgechromium.py:113-114`), and the form's `BackColor = Color.Transparent`
with the `SupportsTransparentBackColor` style pywebview sets (`winforms.py:289`); the shell
already does this at `sotto_webview.py:4900`. **`TransparencyKey`, `LWA_COLORKEY` and
`WS_EX_LAYERED` are not reintroduced anywhere**: I changed no style call, the live exstyle
carries no `WS_EX_LAYERED` bit, and `set_layered_color_key` (`:1515`) — the only
`LWA_COLORKEY` primitive in the tree — is **never called** (grep: one hit, the definition).
WebView2Feedback #118: a colour key cannot key an opaque WebView2 child. Because the form is
transparent and the WebView2 background is transparent, the pixels outside the new radius are
the **desktop**.

**After, measured:** `boxShadow` = `rgba(255,255,255,0.05) 0 1px 0 inset, rgba(0,0,0,0.35)
0 0 0 1px inset, rgba(0,0,0,0.6) 0 -34px 54px -34px inset` (no outer ring at all);
`.panel` radius 8px → **12px**; `html` radius 8px → **12px**; the rendered corner goes from a
square dark corner to a rounded one (`final-after-panel.png` vs `shot-before-panel.png`).

**NOT verified at runtime** — the pixels outside the radius only become the DESKTOP on the
owner's machine, and that needs one restart of the shell.

---

## WHAT I DID NOT TOUCH, AND WHY

* **`app/panel/panel.html`** — nothing needed changing. Item 3's words are hidden by CSS, so
  they stay in the accessibility tree with their real state; `panel.html` needed no edit.
* **the generated theme CSS** — not hand-edited, as the rule demands. Items 2, 3 and 7 were
  solved in `panel.css` / `button-contract.css`, which load before the themes and win with
  `!important`, so **the generator was not changed and nothing was regenerated**.
* **the app itself** — never launched, restarted or killed. The render rig is Edge headless
  over a copy; the only thing ever pointed at the owner's window is a `PrintWindow` capture
  with `SW_SHOWNOACTIVATE`, which re-hides the window (it was hidden before and after).

## GATES

| gate | result |
|---|---|
| `node _main/scope-leak-oracle.js` | **VERDICT PASS** — 9 stylesheets, `leaked=0` |
| `node --check panel.js` / `strip-drag.js` | rc=0 / rc=0 |
| `ast.parse(sotto_webview.py)` | OK |
| drag harness (§5) | FAIL on HEAD → **PASS** after |
| `node app/shadowplay/run-all.mjs` (what the pre-commit itself runs) | **SUITES 15 passed, 0 failed** + **GATE 9 passed, 0 refused**, `VERDICT suites_ok=true gate_ok=true`, exit 0 — run once up front and again by the hook on **every one of the five commits below** |
| `sotto_webview.py` line endings after the change | 11198 CRLF + **139 bare LF → 11213 CRLF + 139 bare LF** (unchanged count; staged with `core.autocrlf=false`) |
| `panel.css` / `panel.js` / `strip-drag.js` line endings | **0 bare LF** each |

## THE FIVE COMMITS

1. `adaf2af` — `button-contract.css` + `panel.css`: items 1, 2, 3 and 7 (CSS).
2. `c21ee26` — `panel.js`: item 6.
3. `8d90343` — `strip-drag.js` + `panel.css`: item 5.
4. `f1a007c` — `sotto_webview.py`: item 4.
5. this receipt + the instruments that produced the numbers.

**The render trees (`_main/_render-1710/before`, `/after`, the PNGs, the Edge profiles)
are untracked scratch and were deliberately NOT committed.** They are reproducible:
`git archive HEAD app/panel` for the BEFORE tree, copy the six changed files over it for
the AFTER tree, then `_main/_render-1710/render.ps1`. The scripts, the probe and the drag
instrument are committed; the trees are not.

## FOR THE LEAD — ONE RESTART BUYS THE WHOLE LANE

    # stop the current shell, then start it again; nothing else is needed
    # (the owner is using the machine, so this is your call, not this lane's)

Items 1, 3, 6 and 7 are CSS/JS/shell changes that are **on disk and correct but invisible**
until the shell restarts. If you want the panel to reload while you work, launch it with
`--hot-reload` so the next lane does not have to write its own render rig.