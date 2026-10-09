# Receipt — shell window behaviour (2026-10-08)

Scope handed to this lane: **Alt+C closes on a click outside**, the **bottom-centre strip**, an
**edit mode** (move + resize + persist), and the **worker-stats bridge member**. In the order given.
`app/panel/` was never touched.

| item | state |
|---|---|
| Alt+C closes when clicking outside | **DONE, measured** (below) |
| the bottom-centre strip (`strip` surface) | **NOT IMPLEMENTED** — contract + numbers below |
| edit mode (move/resize/persist) | **NOT STARTED** — design below |
| worker stats on the bridge (`getStats`/`onStats`) | **NOT STARTED** |

Everything shipped in this lane is verified to leave the app working: a final run with the icon fix,
the tray, the click watcher and the AUMID all ON reaches `RECEIVER_READY`, `panel_loaded=true`, and
**0 visible window samples out of 20** at a 100 ms cadence over the shell's own pid (6 windows, none
visible). `--show` was never passed in any run of this lane.

---

## 1. Alt+C closes when the owner clicks outside — DONE

Owner, verbatim: *"permita o alt c fechar quando eu clico pra fora dele"*.

### The signal, and why it is not "focus loss"

**The obvious signal does not exist here, and that is a deliberate product decision.**
`show_panel` uses `SW_SHOWNOACTIVATE` and the window carries `WS_EX_NOACTIVATE`, so the panel
**never takes focus** (it must not steal focus from a film or a game). A window that never activates
can never receive `WM_ACTIVATE`/`WA_INACTIVE`, and `GetForegroundWindow() != ours` is true *before*
the panel is even shown. `SetCapture` was rejected too: capture routes the outside click **into** the
panel, swallowing the click the owner aimed at the app underneath — the exact thing the click-through
panel exists to prevent.

**So: `WH_MOUSE_LL`, a low-level mouse hook that only OBSERVES.** `CallNextHookEx` is always reached,
so the click still lands where he aimed it *and* the panel goes away. The proc does one rect test and
returns: a slow low-level hook stalls the pointer **system-wide**, so every path is wrapped in
`try/except` and nothing blocks.

### The guards (each one is a case the owner would otherwise meet)

- the panel must be **MEASURED** visible (`IsWindowVisible`), never the cached `self.visible`;
- the click must be **outside** the panel's rect (2 px slack) — a click **inside never closes**;
- a click landing on **our own window** (`WindowFromPoint` → same pid) is not "outside", even when its
  coordinates are — this is what keeps the **tray menu** and any dialog from closing the panel;
- the watcher is **ARMED only in `show_panel`**, so the two startup navigations cannot close anything.

### Measurement — `python _main/_run-outside-click-probe.py` (then read its log)

`--probe-outside-click` is a MEASUREMENT mode: it makes the panel **visible but not seen** with
`form.Opacity = 0` — the very mechanism pywebview's own startup dance uses to map a window invisibly
(`winforms.py:777-781`) — so `IsWindowVisible(hwnd)` is TRUE (the guard the decision reads) while
nothing reaches the owner's screen. **`--show` is not used.** The decisions are driven through the
watcher thread's **real message loop** (`PostThreadMessageW`).

Measured, in order, one run:

```
OUTSIDE_CLICK_HOOK installed=true hook=66788432 thread=30852 type=WH_MOUSE_LL consumes_click=false
OUTSIDE_CLICK source=probe-startup point=(0,0)  decision=not-armed        closed=false
PANEL_SHOWN reason=probe-outside-click visible=true
OUTSIDE_CLICK_PROBE shown visible=true armed=true rect=(1528,66,1908,966)
OUTSIDE_CLICK source=probe point=(1508,76)  decision=outside            closed=true
PANEL_HIDDEN reason=click-outside visible=false
PANEL_SHOWN reason=probe-inside-click visible=true
OUTSIDE_CLICK source=probe point=(1718,516) decision=inside             closed=false
OUTSIDE_CLICK source=hook  point=(1224,725) decision=outside            closed=true
PANEL_HIDDEN reason=click-outside visible=false
```

So all three required cases hold: **click outside → hides**; **click inside → does not hide**; **the
startup navigation does not hide by itself**.

**AND THE HOOK WAS PROVEN ON REAL INPUT, which the design did not promise.** The two
`source=hook` lines are *physical* mouse events, captured by the hook while the probe ran — the
owner's own mouse, mid-probe. The first was refused (`panel-not-visible`, correct), the second closed
the panel (correct: outside the rect). That is the end-to-end path I intended to declare unproven:
the OS delivering a real click to the hook is **measured, twice**.

**Disclosure:** that also means the probe is exposed to real input. The final `after_inside_click
visible=false` is caused by the *physical* click at (1224,725), not by the inside click — the inside
click's own decision (`closed=false`) is what proves the inside case. And because the hook never
consumes, those real clicks also landed normally on whatever was beneath them (as any click would).

### What is still NOT proved for this item

- Only **one** geometry (the docked-right panel) and one screen (1920×1080) were exercised.
- A click on the **panel's own edge** inside the 2 px slack, and a click on a **child window** of the
  panel (there are none today), are untested.
- The watcher was never run while the **tray menu was actually open** — the `our-own-window` guard is
  code-verified, not measured.
- A `--show`/`--probe-v2` run was not exercised (the arm is not armed by `--show` in this lane).

---

## 2. The bottom-centre strip — NOT IMPLEMENTED (stopped for budget)

**The target, now settled by the owner, verbatim:** *"alt c > abre embaixo. passo o mouse encima >
aparece mais botoes"* — the live caption **at the bottom, horizontally centred**; that is what *"no
meio da tela"* meant (horizontal centre, not vertical). It matches `Stage.tsx:134` — *"legenda ao
vivo, embaixo ao centro"*.

**The panel half already exists**: `app/panel/surface.js` (`window.SottoSurfaces.set('strip'|'panel')`)
plus `panel.css`'s `body[data-surface="strip"]` block and the `.stripbar` markup. `surface.js:28-31`
states it explicitly: *"NOTHING HERE TOUCHES A WINDOW. Sizing the window to the strip is the SHELL's
job (it owns the HWND and the work area)"*, and points at `_main/receipt-panel-two-surfaces.md` —
**which does not exist on disk**. The shell half is absent: `grep 'surface|SottoSurfaces|strip'` over
`app/webview/sotto_webview.py` returns **no implementation**.

**The contract, recovered from the panel's own caller** (`app/panel/panel.js:1239-1243`):

```js
/** Open the FULL panel. `bridge.setPanelSurface('panel')` resizes in the shell. */
function openFullPanel(reason) {
  if (bridge && typeof bridge.setPanelSurface === 'function') {
    bridge.setPanelSurface('panel', reason);
```

So the shell owes **one** member — `setPanelSurface(surface, reason)` on the `window.sotto` bridge —
and must set the document surface with `window.SottoSurfaces.set(...)`. Without that member the strip's
own **"Open panel" button falls back to switching the layout only** and the window stays strip-sized
(`panel.js:1245-1247` says exactly that), so the strip must not become the default surface before
this member exists.

**The geometry I would use — NUMBERS, and why** (this is the answer the lane was asked for; it is a
PROPOSAL, not a measurement, because nothing was implemented):

| quantity | value on this box (1920×1080, work area `1920x1032@(0,0)`) | why |
|---|---|---|
| width | `min(1040, max(480, round(work.width * 0.62)))` → **1040** | the classic subtitle band is ~55–65 % of the screen; capped at 1040 px so it stays a caption and not a second panel |
| height | **148** | `panel.css:1527` describes the strip as "the strip's ~150 px"; a fixed height is also what `panel.css:1024-1028` asks for ("the strip is sized to its content by the SHELL", `overflow: hidden`) |
| x | `work.x + (work.width - width) // 2` → **440** | horizontally CENTRED — the owner's *"no meio"* |
| y | `work.y + work.height - height - 48` → **836** | 48 px above the bottom of the WORK area (not the screen), so the strip clears the taskbar |
| docked | `bottom-centre` | — |
| full panel (unchanged) | `380x900@(1528,66)`, `docked=right` | measured this session: `rect=(1528,66,1908,966)` |

Resizing is `SetWindowPos` + the existing `_fit_client_area` (the client area must be forced after a
resize for the same reason `panel.css`/`_fit_client_area` document), and the surface is set with
`exec_js("window.SottoSurfaces.set('strip')")` — the API `surface.js` defines, not a second copy of
the attribute name.

**Not done, and the risk if it is rushed:** the resize interacts with the documented startup dance
(`_reassert_hidden`, `_gate_form_show`, `_fit_client_area`) and with the panel's own
`data-surface="strip"` CSS. It needs its own before/after arm, and a half-done resize would leave the
owner's Alt+C showing a 380×900 column with strip CSS inside it.

## 2b. "passo o mouse encima > aparece mais botoes"

This is the panel's business (the `.stripbar` markup and `panel.css` already exist, and the strip
carries its own theme button). The shell's only obligations are: **do not steal focus on hover** (it
already never activates) and **let the window grow if the revealed controls need more height** — which
is why the height above is a number the shell must be able to change at runtime rather than a constant
baked into the CSS. **No DOM attribute is needed from the panel lane for this**, so nothing was asked.

---

## 3. Edit mode (move + resize + persist) — NOT STARTED

Design, so the next lane does not re-derive it:

- **Entering/leaving**: a tray menu item (`Edit caption position`) is the obvious home now that the
  tray exists and the panel must stay free of always-visible chrome — and it is impossible to trigger
  by accident while reading a caption. It would set a shell flag; the panel's own affordance (if any)
  would need a DOM attribute, which is the panel lane's.
- **Move**: while in edit mode the window must stop being click-through (`make_click_through(hwnd,
  False)`, the existing helper) and the panel must be shown WITHOUT `WS_EX_NOACTIVATE` so it can be
  dragged; the shell then moves the HWND from the mouse, not the DOM (the panel's own
  `release-and-overlay-plan.md:75-78` warns that moving the NATIVE window per frame is the short path
  to flicker — a low-frequency `SetWindowPos` on mouse-move is the compromise).
- **Resize**: the same, with a corner grip; `WS_THICKFRAME` is not available on a frameless form, so
  the shell computes the new size from the cursor.
- **Persist**: `_main/panel-visibility.json` already exists and is written by
  `panel_visibility.write(...)`; the strip geometry belongs in the SAME file under a `geometry` key
  (`{surface, x, y, width, height}`) rather than a second file, so the worker's existing poll and the
  shell's writer cannot disagree about which file is authoritative. Restore at startup from that key.
- **Resolution change**: not measured, and I will not invent it. The honest rule is: clamp the restored
  rect into the current work area on restore, and say so in the log when the clamp moves it.

## 4. Worker stats on the bridge — NOT STARTED

`self.last_worker_stats` already holds them (`_pump`, and it is the same object the watchdog and
`snapshot()` read), and the panel's `wireStatsSource()` (`panel.js:1574`) is waiting for
`getStats`/`onStats` on `window.sotto`. The shape must be the panel's existing whitelist (`peak`,
`blocks`) — no new fields. Served exactly like the `'info'` round-trip, with nothing allowed to cross
the boundary as an exception. This was not started; nothing was changed.

---

## 5. The "middle of the screen" search — the record of what was searched

The owner said he had already explained it; he had not, in any file on this machine that I could find.
Searched, with the regex and the result:

- `H:\aireplay\docs\brief-pesquisarsobre.txt` (210 KB) — `meio da tela|centro da tela|centralizad|no
  meio|embaixo|parte de baixo|modo de edi|redimension|alt+c` → **1 match**, `redimensionar os
  frames;`, about video frames; a second pass `tela|ecrã|legenda|overlay` → 14 matches, all about
  screen capture / OCR research.
- `H:\aireplay\docs\design\` recursive → 32 matches, all `node_modules` noise or the `preview.html`
  comparison table.
- `sotto-app-design-directions\src\` (30) and `sotto-transcription-panel-designs\src\` (33) → only
  `items-center`/`justify-center` CSS utilities; `Stage.tsx:134` = *"legenda ao vivo, embaixo ao
  centro"* (the BOTTOM caption).
- `H:\sotto\docs\` → 6 matches: `battle-prompt.md` (the status sentence at the bottom),
  `release-and-overlay-plan.md:77` (moving/resizing the NATIVE window — used above for edit mode),
  and audit files.
- `H:\sotto\_main\` → 2 matches, unrelated.
- `H:\aireplay\AGENTS.md`, `H:\aireplay\receipts\` → *"A superfície `strip` (o que o Alt+C abre)"* and
  *"legenda ao vivo ao fundo-centro do palco"* — both written by lanes, both "bottom/centre of the
  STAGE".
- `H:\sotto\docs\design\panel-brief.md` (the owner's own design brief) fixes the surface as a
  **380×900 column docked RIGHT**.
- `H:\sotto\docs\audit\original-prompt-adjudication.md` quotes the original prompt: *"edge of the
  screen. Press Alt+C."*

Nothing implemented without the position — and the position then arrived from the owner:
**bottom, horizontally centred**.
