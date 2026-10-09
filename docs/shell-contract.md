## THE SHELL'S OWN CONTRACT — strip surface, bridge, worker hot reload (measured 2026-10-08, lane `strip-surface`)

Everything below was measured against `app/webview/sotto_webview.py` — a revision another lane
has since appended to: this lane's own bytes ended at **389 256 B, sha256 `C4E04600BF1E4D96…`**,
and the file is now **397 180 B / sha256 `EA014D8F2CACD72E…` (7 930 lines)** with every marker
below still present (`_arm_exit_watchdog` `:3115`, `run_hover_probe` `:5426`,
`set_panel_surface` `:4659`, the `meter` branch `:6843`, `_stats_log_maybe` `:5009`).
Measured with `--no-hotkey --no-tray` and a hidden form (`Opacity = 0`), never `--show`.

### Alt+C opens a STRIP, not the 380×900 panel

`setPanelSurface(surface, reason)` is the page→host call (`window.sotto.setPanelSurface`), routed by
`SottoHost.dispatch('panel-surface')`, and it is what makes Alt+C open a **short strip**: one document,
two layouts via `document.body.dataset.surface = 'strip' | 'panel'`.

- Strip geometry, measured on this box: **`1040×150` at `(440,834)`**, window rect `(440,834,1480,984)`
  — and `984 = 1032 − 48`, i.e. the bottom margin `STRIP_BOTTOM_MARGIN`. Width is
  `clamp(480, 62 % of work width, 1040)` = `clamp(480, 1190, 1040)` = 1040.
- **THE HEIGHT IS NEVER HARD-CODED.** `panel.css:52` declares `--strip-height: 150px`; the shell READS
  it with `getComputedStyle` and applies it (`STRIP_HEIGHT_CSS_VAR = '--strip-height'`). Measured
  `STRIP_HEIGHT from=148 to=150 source=css css_value=150`. The constant
  `STRIP_HEIGHT_FALLBACK = 148` is a FALLBACK ONLY, and **every time it is used, that fact is logged**
  — a silent fallback is how a CSS edit stops taking effect without anyone noticing.
- The panel surface is unchanged: `380×900@(1528,66)`.

**`SetWindowPos` AND ITS ARGTYPES — a real defect this lane found and fixed.** Calling
`user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, w, h, flags)` with **no `argtypes` declared** makes
ctypes marshal `HWND_TOPMOST` (-1) as a 32-bit value, and the call fails silently: measured
`ok=false last_error=1400`. With the seven `argtypes` plus `restype = wt.BOOL` declared it returns
`ok=true last_error=0`. The pre-existing `set_topmost()` had been failing this way the whole time.
**Any new ctypes window call in this file declares its `argtypes` first.**

### Edit mode: move the caption, and persist it

From the tray, **Edit caption position** enters edit mode: `make_click_through(hwnd, False)` plus
removing `WS_EX_NOACTIVATE` so the band takes the mouse, then a LOW-FREQUENCY `SetWindowPos` follows the
drag (not per-pixel — a per-pixel loop would flood the log and the UI thread).

Measured: `PANEL_EDIT_MODE on=true … rect=(440,834,1480,984)`; dragging to `(700,400)` →
`PANEL_EDIT_GEOMETRY_SAVED surface=strip window=1040x150@(700,400) moves=1`. The position is persisted
in the EXISTING `_main/panel-visibility.json` under a **`geometry`** key
(`{"surface":"strip","x":700,"y":400,"width":1040,"height":150,"docked":"edited","workWidth":1920,"workHeight":1032}`)
— never a second file, or the shell and the worker's poll would disagree about which one is
authoritative. On restore the rect is CLAMPED to the work area and **clamped exactly once** with one log
line: in-bounds `(700,400)` → `clamped=false`; off-screen `(5000,5000)` → `(880,884) clamped=true`.

### The bridge the panel was owed: `getStats` / `onStats`, and the meter branch

`getStats()` and `onStats(...)` are now real bridge methods, and `BRIDGE_PROBE.methods` reads
**17**. Measured end to end: a `stats` push of `{"peak":0.443448,"blocks":812.0}` reached the DOM and set
`data-level="live"` with ten bars carrying `--meter-h: 0.443`; an unfed page stayed at `level="none"`.

**THE METER BUG, AND WHY THE THROTTLE BELONGS NEXT TO THE BRANCH.** The worker's stdout carries a
`{"type":"meter", …}` event (`sotto_worker.py:3591`, `level = {"peak": <WINDOW peak>, "blocks": <n>}`,
`METER_HZ_DEFAULT = 10.0`). `WorkerBridge._consume` had no `meter` branch, so every meter sample fell
into the unknown-kind `else` — **which had no throttle**, at 35 B/sample × 10 Hz ≈ **20.5 KB/min** of
log. Two facts had to be true together, and the fix keeps them together in the same branch:

1. the wave must show the **WINDOW** value (`stats()`), never the stderr `WORKER_STATS` **running
   maximum**, which paints a staircase instead of a wave; and
2. that branch must carry its own log budget — **one line per declared interval, not one per sample.**

**DO NOT "FIX" A GROWING LOG BY SWITCHING THE DATA OFF.** That is the defect this lane was called to
undo: the meter's default had been set to zero to quiet a log. The feed and the log are different
things; bound the LOG. The shipped feed logs on `_stats_log_maybe` (first push, then at most one line
per `STATS_LOG_INTERVAL_S = 30.0`, each line carrying `count=`, `in_window_s=`, `rate_hz=` and the
payload it stands for) while still delivering EVERY sample to the page. Measured, two arms, same
worker at 20 Hz: per-sample **460 lines / 83 405 B/min** vs aggregated **1 line / 145,1 B/min** —
**575× fewer bytes with 440 pushes still delivered.** Proof is in both directions, and the number that
proves the feed is alive is the PUSH COUNT, not the log line.

### Worker hot reload: a boundary, a ceiling, and a floor (the defect that ran stale code)

The owner's report was, verbatim: **"e tu estás a correr código antigo"**. It was real. Since his worker
started at 08:01:56 the shell logged **20 QUEUED / 20 DEFERRED / 0 APPLIED / 0 respawns** — every reload
request deferred, never applied. The cause is the defer GUARD: `is_capturing()` is true whenever the
worker is capturing, and a worker that is playing audio **never stops**, so the boundary never arrived.

`WorkerReloadPolicy` now runs in this order, and the order is the fix:

1. **DEBOUNCE** — `WORKER_RELOAD_DEBOUNCE_MS = 2000`.
2. **GUARD** — never reload mid-capture (`WORKER_CAPTURING_STATES = frozenset({'capture-started'})`).
3. **BOUNDARY** — wait for a line the WORKER CLOSED (`final:true`, `sotto_worker.py:2078`).
4. **CEILING** — after `WORKER_RELOAD_MAX_DEFER_MS`, apply ANYWAY and log
   `HOT_RELOAD_WORKER_FORCED reason=no-boundary-in-Ns`. **N = 25 000 ms, and the number is measured,
   not guessed:** the owner's own cadence is ≈3.6 s per closed line (14 → 25 rows in 40 s with a video
   playing), so 25 s is about **seven** closed-line intervals — the boundary essentially always wins,
   the FORCED path stays the exception, and the worst case is bounded to half a minute instead of
   never.
5. **FLOOR** — `WORKER_RELOAD_MIN_INTERVAL_MS = 180000` still bounds how often a model may be reloaded.

Two more rules that came out of it:

- **STALENESS IS A QUERY, NOT A DISCOVERY.** The shell compares sha256 on disk against the sha256 the
  loaded worker was spawned with (`sha256_disk` vs `sha256_at_spawn`) and carries both in the log AND
  in `panel_state_snapshot()['shell']`; after applying, the state shows the NEW pid and the NEW sha256.
  A file watcher cannot tell the owner that the running worker is old — that requires asking.
- **THE SHELL CANNOT RELOAD ITSELF.** After a worker reload, if the shell's own bytes changed, the
  divergence is made VISIBLE with a one-line restart hint rather than silently ignored.
- **RESTART THE SHELL FIRST (or both together)** after editing worker code, or the old shell's
  `_consume` will keep flooding `BRIDGE_UNKNOWN` on the `meter` event the new worker now sends.
- If the hot reload applies and the captions blink once, **that is acceptable** — the alternative was
  code that never reloaded at all.

Six arms gate all of it (`_main/_strip-reload-probe.py`, no WebView2 needed) and the in-shell
`--probe-reload` is GREEN: guard (0 deferred where 0 were expected), storm (6/6), burst (1/1), the
closed-line arm (**0 applied before the boundary → 1 after**, with `still_capturing=True`), the ceiling
(1 restart with **no** boundary at all, logging `HOT_RELOAD_WORKER_FORCED`), and the floor (0 restarts,
`pending_held=True`).

**AND A CLOCK BUG THE FLOOR ARM FOUND.** The policy read `spawned_at >= self.pending_since`, and
`time.monotonic()` has a COARSE tick on this box (two consecutive calls compare equal, and are still
equal 100 µs apart — measured), so a spawn on the same tick was misread as a respawn and the boundary
arm reported `APPLIED_AT_BOUNDARY` for a respawn that never happened. The comparison is now STRICT `>`.
**Whenever a duration decides whether something happened, remember the clock may not have ticked.**

### The hover claim, measured on the renderer, in BOTH surfaces

The owner said, verbatim: *"passo o mouse encima > aparece mais botoes"*. A CSS read cannot answer the
real question — *if the reveal is CSS-only inside a small window, are the buttons still inside the
hit-test, or clipped out of it?* — so `_strip-hover-probe.py` drives the shell's own
`--probe-hover`, which synthesises a REAL renderer hover through CDP
`Input.dispatchMouseEvent` (no physical cursor is ever moved; the owner's mouse stays where it is) and
reads the consequence. Measured, window never seen (`Opacity = 0`):

- **STRIP surface** (`inner 1040×150`, `.stripbar` `display:flex`, `opacity:1`, `visibility:visible`):
  all **four** buttons are laid out (`64×26`, `60×26`, `80×26`, `83×26`), all `in_viewport:true`, and
  all **`hit_is_button:true`** — `document.elementFromPoint` at each centre returns the button or a
  descendant, i.e. **they are in the hit-test**. The synthetic hover is exclusive and real: moving to
  each centre in turn sets `:hover` on exactly that one button and `false` on the other three. A
  synthesised click on the first button TOGGLES `aria-pressed` `true → false`. **So the buttons are
  laid out and clickable; `:hover` only restyles them — nothing "appears" on hover.**
- **PANEL surface** (`.stripbar display:none`): every button reads `box [0,0]`, `in_viewport:false`,
  `hit_is_button:false`, and the probe reports `unreachable_no_button_in_viewport` with click
  `target:null`. **On the panel surface there are no strip buttons in the hit-test to reveal.** (The
  DOM `innerWidth/innerHeight` stays at the larger strip value there even though the window is
  `380×900` — a stale layout viewport; the `display:none` + `[0,0]` hit-test result is the
  authoritative part, and the probe reads a settled snapshot before measuring.)

### Declared limitations — what was NOT proven, and what a future lane must test

- **`--show` and `--selftest` were NEVER RUN, deliberately**: they map a real window on the owner's
  desk. Everything above was measured with `--no-hotkey --no-tray` and `Opacity = 0` instead. Do not
  read this section as covering the visible path.
- **MULTI-MONITOR IS A DECLARED LIMITATION, NOT A MEASUREMENT.** This box has **one** monitor
  (`DPI=96 scale=1`, `monitors=1`, `\\.\DISPLAY1 primary=True monitor=[0,0 1920x1080]`,
  `work=[0,0 1920x1032]`). `primary_display()` uses
  `MonitorFromPoint(POINT(0,0), MONITOR_DEFAULTTOPRARY)`, so the strip opens on the PRIMARY monitor,
  **not the cursor's**. With one monitor that difference is unmeasurable, so "opens under the cursor" is
  **not** a claim this lane can make. A future two-monitor lane must test: (a) strip x/y chosen by the
  CURSOR's monitor rather than the primary, (b) clamp against the correct monitor's work area, (c) the
  CSS `--strip-height` is device-independent so only the GEOMETRY needs per-monitor work, and (d) the
  edit-mode drag clamps to the work area of the monitor the strip is actually on.
- **Hover-driven height growth is NOT WIRED.** `set_strip_height()` exists and the CSS supports it, but
  nothing calls it — so there is no "the strip grows as the mouse approaches" behaviour yet. Measured
  as absent, not assumed.
- `statsReplies` counts the page's own 1000 ms poll; `statsPushes` counts the shell→page pushes. Both
  travel in `SHELL_EXIT`, which is why a push can be proven without any log line per sample.

### Two rules for instruments, both paid for in this lane

- **A LEAKED HUNG SHELL POISONS EVERY LATER LAUNCH.** A shell launched with `--exit-after N` is normally
  killed by the timer armed in `_on_loaded` — which does not exist until the panel loads. A hang upstream
  of the load (WebView2 never reaching the receiver, `bridge.start()` blocked on its own non-reentrant
  lock) left a HIDDEN `pythonw` alive for ~20 minutes, and while it was alive **6 of 6** later launches
  stalled before `RECEIVER_READY`. Once it exited, the same box measured **3 of 3 healthy**. The cure is
  in the SHELL, not in each probe: `_arm_exit_watchdog()` fires a hard `os._exit`
  `EXIT_WATCHDOG_GRACE_S = 60` after window creation and logs
  `SHELL_EXIT_ARMED where=window-created`, then `SHELL_EXIT reason=exit-after-watchdog` if the graceful
  path never ran. It uses `os._exit` and NOT `request_exit` on purpose: `request_exit` joins
  `bridge.stop()`, which takes the very lock a startup hang may be holding. Verified additive — a
  healthy launch logs the arm at `after_s=68.0` and still exits on its own `SHELL_EXIT rc=0`.
- **A PROBE THAT PRINTS NOTHING ON RED LOOKS LIKE A PROBE THAT NEVER RAN — and worse, it DEFEATS ITS
  OWN CONTROL.** `_strip-stats-log-probe.py` printed only when GREEN, so its RED run wrote a **0-byte**
  step log and the battery's `:control` kind could not find `STRIP-LOG CONTROL PASS` — a control that
  reports "the instrument did not run" instead of "the instrument ran and failed". **Every instrument
  in the battery prints a verdict line in BOTH colours**, a shell that never exits is its OWN named
  failure (`killed`/`ready`, not a slow number), the delivered-push count falls back to the cumulative
  `count=` in the last `BRIDGE_STATS_PUSH` line when `SHELL_EXIT` is missing, and an arm that never
  reaches `RECEIVER_READY` is RETRIED once — an environmental stall is not a measurement of the log
  budget.
- **`python -c "import pywebview"` fails on this box and means NOTHING: the distribution is `pywebview`,
  the IMPORT NAME is `webview`.** A lane concluded from that `ModuleNotFoundError` that the shell's
  dependency was missing and that a WebView2 user-data question was unanswerable. It was a bad test.

### Product rule owed by another lane: ask WHICH APP is making the sound

- **O SOM QUE O WORKER TRANSCREVE NÃO PASSA PELA ENDPOINT POR OMISSÃO — ENUMERAR SÓ A POR OMISSÃO DÁ A
  RESPOSTA ERRADA.** Medido 2026-10-07 (lane `audio-source-metadata`): a endpoint de render por omissão desta
  caixa é `VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)`, mas o Chrome que o worker estava a transcrever
  renderizava para **`CABLE Input (VB-Audio Virtual Cable)`** — e essa é uma de **seis** endpoints de render
  activas. O meter do `CABLE Input` leu **0.126788** e a sessão `chrome.exe` **0.149162** enquanto o worker
  transcrevia, com **todas as outras endpoints a 0.000000**. Qualquer código que pergunte "que app está a soar"
  tem de varrer **todas** as endpoints de render activas (`EnumAudioEndpoints(eRender, ACTIVE)`), não só
  `GetDefaultAudioEndpoint`: senão nomeia a app errada com toda a confiança, exactamente no cenário do dono
  (VoiceMeeter a encaminhar para um cabo virtual). The browser window title must NEVER be presented as
  "the tab that made the sound" — it is the SELECTED tab — and **prefer `null` to a guess that lies**;
  per-tab attribution needs a browser extension (`sotto.browser-tab/1`, not implemented).
  *(Recibo: `_main/receipt-audio-source-metadata.md`, §5.1–5.2; probe: `_main/audio-source-probe.py --all-endpoints`.)*

### Focus attribution: a RULE, never a pid snapshot taken at startup

- **EXCLUDE SOTTO'S OWN WINDOWS BY RULE (title + class), NEVER BY A PID SNAPSHOT TAKEN AT STARTUP.** A
  shell instance is born AFTER startup — hot reload, a measurement run, login autostart — so a snapshot
  is not a rule. Measured: the title+class rule saw **6 panel pids and 0 of them in the focus queue**,
  while the startup-only sweep **MISSED 6 other shell instances** (`5396, 5940, 8896, 27020, 33188,
  36508`, 2 events each) that **reached FOCUS**. Without this rule the owner's narrative gains
  `usuario voltou pro pythonw.exe(Sotto)` — the exact leak the per-app collapse exists to remove.
  *(Recibo: `_main/receipt-focus-timeline.md` §G4 item 6, 34 799 B, 602 linhas, sha256 `5BAE4502…`.)*
