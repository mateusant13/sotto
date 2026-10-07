# Receipt — the owner's five design directions as five themes in the REAL panel

**Lane:** `painel-cinco-direcoes` · 2026-10-07 · workspace `H:\sotto` (+ `H:\aireplay` read-only)
**Target:** `H:\sotto\app\panel\` — extending the `theme-switcher.js` + `themes/` that already
existed. **No parallel mechanism was invented.**
**Source of truth for the drawing:** `H:\aireplay\docs\design\sotto-app-design-directions\src\data\designs.ts`
plus the components beside it (`components\Caption.tsx`, `components\Panel.tsx`, `src\index.css`).

---

## 0. One-line answer

All five directions **apply to the real panel document** and the gate is **GREEN** with **three
controls RED** and a persistence proof with its own control. **`tele` (Teleprompter) is the one I
completed to its direction**; the other four were already carried by the same generator and pass the
same gate, but their *richer* behaviours (bcast's per-line index, mano's per-word contrast ramp,
cine's forming-fog, inst's LED beyond a rail) are **not** implemented — see §7.

**The previous lane did leave a mechanism** — it did not leave a *delivery*. What it left was
measured RED by its own instrument (10 real-arm problems), and I found the three reasons in the
instrument itself plus two real design defects in `tele`. Both halves are listed in §3.

---

## 1. Which of the five are ready

| # | id | direction | accent | family asked for | ready? | the face **actually used** |
|---|---|---|---|---|---|---|
| 1 | `tele` | Teleprompter | `#f2e9d8` | Barlow Condensed | **YES — completed** | **Barlow Condensed 700** (live) / **400** (history), from the bundle |
| 2 | `bcast` | Broadcast | `#ff6a55` | IBM Plex Mono | applies; index missing | **IBM Plex Mono 600** (live) / **400** (history) |
| 3 | `mano` | Manuscrito | `#a9c1d9` | Newsreader | applies; ramp missing | **Newsreader 400** (live and history) |
| 4 | `cine` | Cartão de Cinema | `#e4b363` | Fraunces | applies; fog missing | **Fraunces 400** (live and history), live line italic |
| 5 | `inst` | Instrumento | `#5fd3a7` | Space Grotesk | applies | **Space Grotesk 700** (live) / **400** (history) |

### Which family was REALLY used — the honest half

`designs.ts` / `index.css` declare the stacks with the direction's family **first** and a fallback
after it (`"Newsreader", Georgia, serif`; `"Fraunces", Georgia, serif`). The panel keeps exactly that
shape, and the measurement says **the fallback was never reached**:

* `familyResolved = true` for all five — the direction's own family is the **first token** of the
  computed stack (measured per theme, not grepped).
* `document.fonts.load('<weight> 20px "<family>"')` resolved **1 face** for every theme.
* The falsifier: with the bundled `.woff2` files removed, the same load returns
  **`error:NetworkError`** and the gate goes RED. So the face that painted came from
  `app/panel/fonts/`, **not** from the system installation and **not** from Georgia.

**The panel does not depend on the owner's font installs at all** — and that is the answer to the
"Newsreader and Fraunces still fall back to Georgia in the browser" report. The panel is a `file://`
document that must paint correctly on a box where nothing was installed, so `build_fonts.py` bundles
the latin `.woff2` subsets: **14 files, 244 028 B (238.3 KB)** in `app/panel/fonts/`, one `@font-face`
each in `app/panel/themes/fonts.css`. The direction's family is named first; the fallback is a
fallback that is never used.

The owner's five installs **are** on this machine — verified: they are **per-user**, in
`%LOCALAPPDATA%\Microsoft\Windows\Fonts`, registered under `HKCU\...\CurrentVersion\Fonts`
(`BarlowCondensed-*`, `IBMPlexMono-*`, `Newsreader`, `Fraunces`, `SpaceGrotesk`). `C:\Windows\Fonts`
carries none of them, which is why a machine-wide listing looks empty — `build_fonts.py`'s docstring
said "`C:\Windows\Fonts` carries NONE of the five" and that sentence has been corrected to say
*machine-wide*, because the unqualified version reads as "the owner installed nothing".

---

## 2. How each direction maps onto the mechanism that ALREADY EXISTED

Nothing new was invented. The existing contract is:

* `app/panel/themes/themes.js` — the manifest: five entries `{name, label, file, swatch}`, `fallback:
  'theme-1'`, in the owner's order. Loaded **before** the switcher.
* `app/panel/theme-switcher.js` — owns the choice, and the whole switch is **one attribute write**:
  `document.documentElement.dataset.theme = 'theme-N'`.
* `app/panel/themes/theme-N.css` — all five linked at once by `panel.html`; **every** rule scoped to
  `:root[data-theme='theme-N']`, so five themes coexist in one document and cannot collide.
* `app/panel/panel.html` — `<html lang="en" data-theme="theme-1">` is spelled in the markup so the
  first paint is the chosen theme; `themes/fonts.css` is linked **before** `panel.css`.

The mapping is therefore: **direction → manifest entry + one scoped stylesheet + one `--accent`.**

| direction | manifest | stylesheet | accent token | live line is marked by | history is |
|---|---|---|---|---|---|
| `tele` | `theme-1` / "Teleprompter" | `themes/theme-1.css` | `--accent: #F2E9D8` | size 30px · weight 700 · **static halo** · uppercase · **no rail** | 18px · 400 · `#A9B7C6` · flat, no rail |
| `bcast` | `theme-2` / "Broadcast" | `themes/theme-2.css` | `--accent: #FF6A55` | 20px · 600 · **2px accent rail** | 15px · 400 · no rail |
| `mano` | `theme-3` / "Manuscrito" | `themes/theme-3.css` | `--accent: #A9C1D9` | 23px · 400 · 2px rail | 17px · 400 · no rail |
| `cine` | `theme-4` / "Cinema Card" | `themes/theme-4.css` | `--accent: #E4B363` | 24px · 400 · **italic** · 2px rail | 18px · 400 · no rail |
| `inst` | `theme-5` / "Instrumento" | `themes/theme-5.css` | `--accent: #5FD3A7` | 24px · 700 · **4px LED rail** | 17px · 400 · no rail |

The five stylesheets are **generated** by `_main/_design-lane/gen_themes.py` (one `THEMES` table, one
skin template, one `scope()` pass) — they are not hand-edited, so the five cannot drift apart. The
bundle is generated by `_main/_design-lane/build_fonts.py`. Both were edited at the source and
re-run; the `.css` files are their output.

### What I changed, and where

| file | change |
|---|---|
| `_main/_design-lane/gen_themes.py` | theme-1: `closed_rail_w` `2px → 0px`; new `live_shadow` (the halo) and `cap_align` parameters; template: `text-shadow: none` on settled lines, `text-shadow: {live_shadow}` on the live line, `text-align: {cap_align}` on `.caption__text`; stale "17 files, ~400 KB" corrected |
| `_main/_design-lane/build_fonts.py` | `Barlow Condensed` weights `(700,) → (400, 700)`; two stale claims corrected |
| `app/panel/themes/theme-1..5.css` | regenerated (576 lines each) |
| `app/panel/themes/fonts.css` | regenerated: 13 → **14** `@font-face` |
| `app/panel/fonts/` | + `barlow-condensed-latin-400-normal.woff2` (21 164 B) |
| `app/panel/themes/themes.js` | comment: it cited `_main/_theme-styles-oracle.js`, **which does not exist**; now names the real check |
| `_main/_theme-probe.js`, `_main/_theme-probe-arm.py` | the instrument — see §3.2 |

**`theme-switcher.js` was NOT changed.** It already works, and that is measured, not assumed: the
live WebView2 DOM carries
`<button class="icon-button theme-button" id="theme-button" data-wired="true" data-theme-current="theme-1" style="--theme-swatch: #f2e9d8;"><span class="theme-button__label">Teleprompter</span></button>`.

---

## 3. The two halves of what was broken

### 3.1 The instrument could not have passed (three defects, all measured)

1. **`measure()` never returned the closed line.** The local variable was computed and then omitted
   from the returned object, so the judge read `None` for every theme. `formingBiggerThanClosed` used
   the local and was right, which is exactly why the bug hid.
2. **`window.getMatchedCSSRules` does not exist in this Chromium** (checked: the string is absent
   from the dumped DOM). The check returned `null`, the judge coerced it to `[]`, and **all five
   themes failed an assertion that could never pass**. Replaced with a real read: the theme's own
   `CSSStyleSheet` is found in `document.styleSheets` and asserted **present, parsed, scoped to
   `:root[data-theme=…]`, with a rule that names `.caption__text`**.
3. **The "closed line" being measured was the wrong row.** `panel.js:444-446` moves
   `.caption--latest` onto the row that *just closed*, so that row is "the line that was live a
   moment ago", not the history column — and the fixture had two rows where the real list holds
   three. Two further errors came from the same place: `0px solid` (a border that paints nothing) was
   called "a rail kept", and `panel.css`'s `border-left: 2px solid transparent` on every `.caption`
   (a gutter, not a mark) was called a rail too. The probe now builds the **three** rows the real list
   holds, in the real order, and a rail is visible only if style ≠ none **and** width > 0 **and** the
   colour's alpha > 0.

### 3.2 Real defects in the `tele` direction

1. **The newest closed line wore a rail.** `theme-1.css` gave `.caption--latest` a `2px solid`
   near-white border, which contradicts the direction's own prose two lines above it in the same
   generated file — *"Nothing is boxed, nothing is decorated: no rail on the forming line, no rail on
   the closed ones"* — and contradicts `designs.ts`: *"O histórico recua em cinza; só o agora
   brilha."* A settled line wearing the live line's own mark reads as still live. → **`0px`.**
2. **"A linha viva brilha" was not implemented.** No theme carried any `text-shadow`; the live line
   was distinguished by size, weight and hue only, while the direction's own recommendation is
   *"brilho, peso e um leve deslocamento óptico bastam para mantê-la acesa"*. → a **static** halo
   (`0 0 18px rgba(242,233,216,.30), 0 0 2px rgba(242,233,216,.55)`) on the live line, and an explicit
   `text-shadow: none` on the settled column so a halo cannot leak onto the history. It is **not a
   keyframe**: rule 4 of every theme file is "the caption text is never animated".
3. **The history asked for a weight the bundle did not carry.** Theme 1 declares
   `--weight-closed: 400`, and the bundle shipped **only** Barlow Condensed **700**. CSS font matching
   takes the nearest available face, so the settled column painted the live line's heavy strokes
   while `getComputedStyle` said `400` — "the history recedes" was being carried by size and hue
   alone. → the **400** `.woff2` is bundled, and the probe now asserts, per theme, that the bundle
   really carries a face at the live **and** the settled weight (a `font-weight` number is the
   author's wish; `document.fonts` is where the faces are).

**`tele` is therefore the one direction completed to its own spec**, and it is the only theme that
needed a design change rather than an instrument change.

---

## 4. The panel contract — untouched

| contract | state |
|---|---|
| the live line **substitutes** (identity = `start`) | untouched — `panel.js` not edited |
| the provisional is rewritten in place, removed on commit | untouched |
| `stickToNewest` keeps the newest visible | untouched |
| the history records only lines the worker closed | untouched |
| the `page-error` channel stays wired | untouched; the real run logs `PRELOAD_ACTIVE hasSotto=true methods=14` and **no** `PAGE_ERROR` |
| **anything the init block can touch is declared ABOVE it** | respected — I added no state to `panel.js`; the switcher declares its own state at module top |

**Not touched, per the brief:** `worker/**`, `app/webview/sotto_webview.py`, the semantics of
`history-*.js`, the routing/producer of `caption-formulation.js`. No file in `app/webview/` was
edited. Every change is inside `app/panel/` or `_main/`.

---

## 5. Proofs — both colours

### 5.1 The panel starts — the real WebView2 shell, `BRIDGE_GATE=GREEN`

```
cmd /c "python app\webview\sotto_webview.py --dump-dom --dump-dom-wait 10 --no-hotkey --no-hot-reload --exit-after 45 --log _main\_panel-theme-dump.log"
```

```
sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
sotto: DOMDUMP_WAIT s=10.0
sotto: BRIDGE_GATE=GREEN hasPanelElement=true url=file:///H:/sotto/app/panel/panel.html panelSaidBridgeMissing=false
sotto: SHELL_EXIT rc=0 reason=dump-dom
```

`rc=0`, 13.4 s. Log: `_main\_panel-theme-dump.log` (5 467 B, sha256 `1D5A10CEF568AC1F…`).

**Two deliberate deviations, both stated:**

* **`--with-worker` was NOT passed.** The literal command in the brief carries it, but the brief also
  says *"não abras dispositivo de áudio"*, and `--with-worker` is the **authoritative** reason in
  `_worker_autostart_reason` — it would start a second `sotto_worker.py` and open a second WASAPI
  loopback tap **while the owner's own worker already holds one** (`AUDCLNT_E_DEVICE_IN_USE` is the
  documented outcome). The theme claim is a CSS claim about the panel document and needs no worker.
  The sanctioned form in the brief (`--dump-dom --no-hotkey`) is what ran.
* **`--exit-after 45` was added** so a stalled launch cannot leave a hidden shell behind. It was
  needed: the **first** attempt hung after `PANEL_SHOW_REFUSED count=2` and never reached
  `_on_loaded`; the retry was clean and reproduced GREEN. That stall is the known unattributed
  residual, **not** a panel regression — the log shows `CoreWebView2InitializationCompleted` and
  `STAGING_LOADED` both reached, and no `PAGE_ERROR` was ever logged.

**Theme evidence from the REAL WebView2 document** (the shell's own dump reads a fixed element list,
so this is what it can prove):

| read | value | what it proves |
|---|---|---|
| `sheets` parsed | **7** | `fonts.css` + `panel.css` + **all five** `theme-N.css` parsed in the app |
| `.wordmark__name` colour | `rgb(242, 233, 216)` | **theme-1's `--accent` #F2E9D8 is painted** — the un-themed value is `#7dd3fc` (measured in the `control-theme` arm) |
| `#clear-button`, `#status` colour | `rgb(169, 183, 198)` | theme-1's `--text-secondary` #A9B7C6 |
| `.panel__header` display | `flex` | the theme button is on screen (it lives in `.panel__controls` inside the header) |

**No window on the owner's screen:** `PANEL_VISIBILITY_ON_SCREEN visible=false`,
`PANEL_SHOW_REFUSED` ×2, **no `PANEL_SHOWN`**, **no `ALERTA-JANELA`**. Launched with `pythonw.exe`
and `-WindowStyle Hidden`; no stray process left; the owner's app (pid 28428) was never touched.

### 5.2 The theme applies in the COMPUTED STYLE — a table per theme

`py -3 _main\_theme-probe-arm.py --neg-arm` → log `_main\_panel-theme-probe.log` (13 661 B,
sha256 `B511C28B5E47FB2A…`), **`rc=0`**.

Real `panel.html`, real `panel.css`, real `theme-switcher.js`, real `themes/themes.js`, real bundled
fonts, loaded headless in Edge **154.0.4258.62** — the **same version** as the installed WebView2
runtime (154.0.4258.62). The switch is driven through the shipped `SottoTheme.set(name, {persist:false})`,
so the button repaints exactly as it does on a click.

| theme | direction | computed family (1st token) | live | align | halo | history | rail live/hist/latest | `--accent` | theme sheet scoped/rules→`.caption__text` | faces |
|---|---|---|---|---|---|---|---|---|---|---|
| theme-1 | Teleprompter | Barlow Condensed | 30px/700/31.8px | **left** | **glow** | 18px/400 flat | **no / no / no** | `#F2E9D8` | 92 / 5 | 1 |
| theme-2 | Broadcast | IBM Plex Mono | 20px/600/27.6px | left | flat | 15px/400 flat | yes / no / no | `#FF6A55` | 92 / 5 | 1 |
| theme-3 | Manuscrito | Newsreader | 23px/400/37.26px | left | flat | 17px/400 flat | yes / no / no | `#A9C1D9` | 92 / 5 | 1 |
| theme-4 | Cinema Card | Fraunces | 24px/400/36.48px | left | flat | 18px/400 flat | yes / no / no | `#E4B363` | 92 / 5 | 1 |
| theme-5 | Instrumento | Space Grotesk | 24px/700/31.2px | left | flat | 17px/400 flat | yes / no / no | `#5FD3A7` | 92 / 5 | 1 |

Bundle coverage asserted per theme (the check that caught defect §3.2.3):
`Barlow Condensed ['400','700'] · IBM Plex Mono ['400','500','600','700'] · Newsreader ['400','600'] ·
Fraunces ['400','500','600'] · Space Grotesk ['400','500','700']` — live and settled weight both
`covered=True` for all five.

Per theme the judge also asserts: the direction's family is the **first** token; the accent token on
`:root` **equals** the direction's accent from `designs.ts`; the accent is **painted** somewhere real
(rail, wordmark or live text); the live line is **larger than both** the settled rows; the settled
rows carry **no** halo and **no** visible rail; the live line's `font-style` is `normal` (except
`cine`, which puts `italic` back by parameter); the theme's own stylesheet is present/parsed/scoped/
reaching `.caption__text`; the switcher button's label and swatch match the manifest; the manifest's
order, labels, swatches and fallback match the owner's five.

### 5.3 The CONTROLS — the same instrument against a broken copy, all RED

| control | what is removed from the copy | result |
|---|---|---|
| `control-theme` | the five `theme-N.css` links **and** `themes.js` + `theme-switcher.js` | **RED** — 53 problems. family falls to `-apple-system`, accent token to `#7dd3fc`, rail on live/history/latest, `sheet=0/0`, manifest absent |
| `control-fonts` | the 13/14 bundled `.woff2` files | **RED** — 5 problems. `facesLoadedByApi='error:NetworkError'` for all five: the family is *named* but no face **loads** |
| `control-weight` | **only** the Barlow Condensed **400** `@font-face` | **RED** — 2 problems, **theme-1 only**: `bundle weights for Barlow Condensed = ['700'] ; settled 400 covered=False`. The other four themes stay green in this arm — which is what makes it a control rather than a second way to fail everything |
| `persist-virgin` | a profile that never chose a theme | **RED-as-expected** — comes up in `theme-1`, so the persistence arm is not vacuous |

`VERDICT: GREEN — all five directions apply to the real panel document`, exit code **0**.

Two things the instrument **cannot** falsify, reported rather than asserted:
`document.fonts.check("Sotto No Such Family")` answered **TRUE**, so `check()` is not a usable
falsifier for a family name on this Chromium — `document.fonts.load()` is, and `control-fonts` is
what proves it. The dead `getMatchedCSSRules` check is described in §3.1.

### 5.4 How the owner cycles the themes, and whether it persists

**On screen, in the panel header** (`.panel__controls`, leftmost of the four controls):

* **left-click** the `theme-button` → **next theme, wrapping**, in the owner's order:
  **Teleprompter → Broadcast → Manuscrito → Cinema Card → Instrumento → Teleprompter**.
  The button shows the current direction's name and a swatch dot in that theme's accent, so the
  label and the dot always name what is on screen.
* **right-click** (or **↓/↑** with the button focused) → the picker, all five listed with their
  swatches, one click to jump. Escape, a click outside, or focus leaving closes it.
* Alt+C opens the **full panel** surface today — the shell does not yet switch surfaces
  (`surface.js` exists, `sotto_webview.py` never sets `document.body.dataset.surface`), so the
  header **is** visible and the button **is** reachable. Verified in the real dump:
  `.panel__header` computes `display:flex`.

**Persistence — measured, and it holds.** Three independent page loads in one profile directory:

```
arm persist-set     themeAfterSet='theme-3'   store={writable:true, roundTrip:'ok', SottoTheme.last():'theme-3'}
arm persist-read    themeAtLoad='theme-3'     SottoTheme.last()='theme-3'      <- a NEW document, SAME profile
arm persist-virgin  themeAtLoad='theme-1'     <- CONTROL: a profile that never chose falls back
PERSISTENCE: GREEN
```

The mechanism is `localStorage['sotto.theme']` written by `writeStore()` in `theme-switcher.js`, read
back **before first paint** by `apply()`. It is defensive on purpose (a throw is swallowed and the
session still works), and the probe reports the storage verdict separately so "cannot persist" cannot
hide behind "works this session".

**One assumption I tested and was wrong about:** I expected `file://` `localStorage` to be refused
without `--allow-file-access-from-files` (the headless arms pass it; the shell passes nothing). The
arm `no-file-access` drops that flag and reports `localStorage writable=True, error=None`. So the
storage works on this engine without the flag, and the shell does not need one. **Caveat, stated
plainly:** that was measured in `msedge.exe` 154.0.4258.62; the WebView2 host process itself was not
driven through a second load, so the WebView2 half of persistence is *same engine, same build, same
document, same code* — not a direct measurement.

---

## 6. Reproduce everything

```powershell
cd H:\sotto

# 1. the five directions, computed styles + three controls + persistence
py -3 _main\_theme-probe-arm.py --neg-arm          # rc 0, VERDICT GREEN

# 2. the real WebView2 panel boots (no audio device opened)
pythonw.exe app\webview\sotto_webview.py --dump-dom --dump-dom-wait 10 `
    --no-hotkey --no-hot-reload --exit-after 45 --log _main\_panel-theme-dump.log
#   -> BRIDGE_GATE=GREEN

# 3. regenerate the stylesheets / the font bundle (both are generated)
py -3 _main\_design-lane\gen_themes.py
py -3 _main\_design-lane\build_fonts.py
```

`_main\_theme-probe-arm.py` writes its arm DOMs to a temp dir it prints as `artifacts:` —
`dom-real.html`, `dom-control-theme.html`, `dom-control-fonts.html`, `dom-control-weight.html`,
`dom-persist-set.html`, `dom-persist-read.html`, `dom-persist-virgin.html`, `dom-persist-noflag.html`.

---

## 7. What is NOT done — by name

1. **`bcast`'s per-line INDEX is missing.** The direction asks for *"índice + timecode por linha"*.
   The per-line **timecode** is there (`.caption__time` is in the panel's own DOM). The **index** is
   not: the mockup prints `pad3(h.id)`, and the panel's rows carry `data-start` but no visible
   ordinal. Adding it means either `panel.js` emitting a number (out of my remit — the theme
   contract says a theme "moves nothing: the structure owns the DOM") or a CSS counter, which would
   renumber as `MAX_CAPTIONS` trims the list and would break `.caption`'s two-column grid. **Not
   faked.**
2. **`mano`'s progressive word-by-word contrast** (`--ink-op: 0.45 + 0.55·i/len`, the mockup's
   `w-mano`) is not implemented — the theme treats the forming line as one colour. The direction's
   *"cada palavra recém-chegada ganha contraste aos poucos"* is absent.
3. **`cine`'s forming-fog** (the mockup's `w-cine` blur-in) is not implemented; only the **italic**
   on the forming line is (the mockup's own `italic`). There is no `filter: blur()` in any theme.
4. **`inst`'s indicator** is the 4px LED rail on the live line; the mockup's breathing animation is
   deliberately absent, because every theme file forbids animating the caption text.
5. **The per-direction headers and footers of the mockups** (`SOTTO / LENDO`, `REC / CH·01`, `rascunho
   ao vivo / pág. 1`, `· ao vivo ·`, `ON / ALT+C`) are **not** themed — the panel has one shared
   header/footer and the theme contract re-skins colour, type and surface only.
6. **The strip surface has no theme button.** `body[data-surface="strip"] .panel__header` is
   `display:none`, and the button lives in that header. **This is not live today** (the shell never
   sets `data-surface="strip"`), but the moment the two-surface work lands, the owner will press Alt+C
   and get a surface with **no way to change the theme**. Flagged, not silently changed — the strip's
   "four controls, nothing else" shape is another lane's in-flight decision
   (`_main/receipt-panel-two-surfaces.md`).
7. **Font resolution inside the WebView2 host process was not measured.** The dump carries no
   `font-family`. It was measured on `msedge.exe` **154.0.4258.62**, the identical version to the
   installed WebView2 runtime, on the same document with the same bundled files — but the WebView2
   process itself is the residual gap. The theme's **colours** *are* measured in the real WebView2
   panel (§5.1).
8. **One intermittent stall, reproduced once.** The first `--dump-dom` launch hung after
   `PANEL_SHOW_REFUSED count=2` and never reached `_on_loaded`; the retry was clean. This is the
   already-documented unattributed residual (AGENTS.md: "1 of 20 fixed-arm launches stalled"), it is
   **upstream of anything this lane touched**, and no `PAGE_ERROR` was logged in either run. Any
   future `--dump-dom` here should carry `--exit-after` so a stall cannot leave a hidden shell behind.

---

## 8. Files, with the revision named

| path | bytes | sha256 (first 16) |
|---|---|---|
| `app/panel/themes/theme-1.css` | 20 999 | `B5A06BF04E63CF5F` |
| `app/panel/themes/theme-2.css` | 20 503 | `2B299977578E419E` |
| `app/panel/themes/theme-3.css` | 20 539 | `0ECBDB1F1EF28D0D` |
| `app/panel/themes/theme-4.css` | 20 482 | `134E84AACE21CB6F` |
| `app/panel/themes/theme-5.css` | 20 485 | `E767DF4104DA4B45` |
| `app/panel/themes/fonts.css` | 6 524 | `8567B9ED9E26E274` |
| `app/panel/themes/themes.js` | 3 380 | `69BBB7E963D085C9` |
| `app/panel/theme-switcher.js` | 12 315 | `D82B8D5AB8CB76D2` (**unchanged**) |
| `app/panel/panel.html` | 28 137 | `063A78C412C583D4` (**unchanged**) |
| `app/panel/fonts/` | 14 files, 244 028 B | — |
| `_main/_theme-probe.js` | 27 530 | `553F880444EA176D` |
| `_main/_theme-probe-arm.py` | 30 488 | `2F0564E03841DEF1` |
| `_main/_panel-theme-probe.log` | 13 661 | `B511C28B5E47FB2A` |
| `_main/_panel-theme-dump.log` | 5 467 | `1D5A10CEF568AC1F` |

Sources of truth read: `H:\aireplay\AGENTS.md`, `H:\sotto\AGENTS.md`,
`H:\aireplay\docs\design\sotto-app-design-directions\src\data\designs.ts`,
`...\src\components\Caption.tsx`, `...\src\components\Panel.tsx`, `...\src\index.css`.

`_main\_design-lane\gen_themes.py` and `build_fonts.py` remain the generators; **do not hand-edit the
five `.css` files or `fonts.css`** — re-run the generators.
