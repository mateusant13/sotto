# Receipt 2026-10-14 — LANE A: the three functional defects (red error, freeze, Alt+C)

Owner's verbatim order (2026-10-14): *"alt c nao aperta direito em diversos caso. arruma
agora. abrir ou fechar o sotto causa travamento no meu pc. arruma. sotto ta reclamando de
coisa nao carregada, com erro vermelho. arruma. tira em curso e historico das barras. tira o
botao de transcript. os botoes sao botoes simples e pequenos porem visiveis o suficiente pro
usuario. e nao e pra ter tema branco."*

Lane A scope of THIS receipt: A1 (red error), A2 (freeze on open/close), A3 (Alt+C). The
button/transcript/white-theme items belong to the UI lane and are not touched here.

**NOTHING WAS LAUNCHED.** No shell, no worker, no `run.cmd`. Every measurement below is
either a passive read of the owner's own log, a passive process census
(`Get-CimInstance`, from a `.ps1` FILE per AGENTS.md), or an IN-PROCESS import of the
real modules (the same technique `_main/panel-exit3-oracle.py` uses).

One disclosed deviation, caught and corrected inside this lane: the first version of my
A1 in-process check called `WorkerBridge._spawn()`, which really spawns a worker child. It
was rewritten to reset the two verdict slots by hand instead (`I:/cc-tmp/laneA-paint-sequence-check.py`,
`# NOT _spawn()` comment marks it). The child that briefly existed died with the check; a
full census afterwards shows exactly ONE `sotto_worker.py` process (pid 35168, parent 2740 —
the shell's own churn spawn) and no orphan. No window, no log line, no device state left
behind. The rule was bent for seconds and the evidence says there is no residue.

Environment: `$env:TMPDIR = I:/cc-tmp` for every run.

---

## A1 — THE RED ERROR

### What was measured (before touching anything)

`_main/webview-run.log` (17 012 423 B, 114 394 lines, mtime 2026-10-14T23:28:24Z) is the
owner's own shell log. The paint path is: `worker_status_kind(state, message)`
(`app/webview/sotto_webview.py:562`) -> `WorkerBridge._consume` (`severity = worker_status_kind(...)`,
`:8729`) -> `_status(text, kind, info)` -> `SottoShell.on_worker_status` (`:7322`) ->
`apply_panel_state` (`:5048`) + `send_status` -> panel.js `wireStatus` -> `setStatus(text, 'error')`
(`panel.js:3083`) which paints `#status-dot[data-state=error]`, the `status--error` class,
`body[data-state=error]`, and the footer sentence; `panel.css:1382` makes the dot `#f87171`.

The owner's own log says exactly when it goes red, and it is NOT at startup:

```
20:10:32.530 STATUS_APPLIED text="Starting worker... (sotto_worker.py)"   PLACEHOLDER "Starting the worker"
20:10:32.613 STATUS_APPLIED text="boot"                                    PLACEHOLDER "Warming up the teleprompter"  (NEUTRAL)
20:10:34.029 STATUS_APPLIED text="model-loading"                          (NEUTRAL)
20:10:36.952 BRIDGE_LOAD_MS ms=4422 pid=8300 worker_load_s=2.93
20:10:38.081 STATUS_APPLIED text="model-loaded"                            (NEUTRAL)
20:10:40.587 STATUS_APPLIED text="capture-started"                         PLACEHOLDER "Ready — speak and the line flows"  (NEUTRAL)
20:12:25.603 BRIDGE_STATUS_ERROR state="device-exhausted" kind=error text="Audio tap carried no signal - every candidate device was flat"
20:12:25.608 BRIDGE_STATUS_ERROR state="silent-device"    kind=error text="Silent audio device - VoiceMeeter Output (VB-Audio Vo [MME] peaked 0.000122 < floor 0.002"
20:12:25.608 BRIDGE_STATUS_ERROR state="done"            kind=error text="Worker finished on silent-device"
20:12:26.396 BRIDGE_EXIT pid=8300 rc=3 spawns=1 captions=0 statuses=31
```

So the first ~105 s of every quiet boot are already NEUTRAL (warming -> ready). The RED is
the worker's own no-audio verdict: the device ladder ran a full window below the peak
floor and the worker exited 3. `87` `BRIDGE_STATUS_ERROR` lines exist in the log; the last
ones (20:28:19-20:28:22) are `Worker error at open-stream - WasapiError:` — a real fault.

### The rule that made it red, and why that rule is now wrong for half its cases

AGENTS.md records the 2026-10-06 decision: `error`, `device-exhausted` and `silent-device`
are painted as errors "with the worker's cause", because painting them neutral meant
"a healthy-looking app while nothing could ever transcribe". That reasoning is still
right for the cases it was measured on. What it got wrong is the COLOUR it chose for the
no-audio half, and the same file's routing law says why:

> "So a live run that reads silence is usually CORRECT BEHAVOUR, not a regression. The
> owner's fix is a routing change in VoiceMeeter / Windows Sound settings."

With nothing routed into a cable, every loopback reads digital silence by design. So on an
idle desktop the no-audio verdict is the NORMAL answer of a WORKING app, and painting it
the same red as `WasapiError: Initialize(SHARED|LOOPBACK) failed` trains the owner to read
"broken app" from "quiet machine" — which is exactly his complaint: *"sotto ta reclamando
de coisa nao carregada, com erro vermelho"*. RED now means "the worker FAILED"; the
no-audio verdict got its own calm kind. Nothing is hidden: the worker's own sentence
(device, api, peak, floor) still paints, the state still holds across the automatic
restart, and a caption still clears it.

### The change (minimal, one new kind: `no-audio`)

`app/webview/sotto_webview.py`:

1. `worker_status_kind` (`:562`) returns a THIRD kind, `'no-audio'`, for
   `WORKER_NO_AUDIO_STATES` and for a `done` whose verdict is in
   `WORKER_NO_AUDIO_VERDICTS`. Order is load-bearing and the code says so: the no-audio
   test comes BEFORE `WORKER_ERROR_STATES`, whose members it overlaps.
2. `_consume` records the calm verdict in a new `last_no_audio` slot (mutually exclusive
   with `last_error`: each write clears the other), logs `BRIDGE_STATUS_NOAUDIO`, and
   titles the placeholder `No audio to transcribe` instead of `Not transcribing`.
3. `worker_status_text` now composes `Worker finished on {verdict}` for the calm
   `done` too (it used to return a bare `done` for any non-error kind).
4. `_wait` paints the exit-3 death as `no-audio` when — and only when — the worker
   itself said so (`last_no_audio` set, `last_error` clear). A crash with NO verdict
   stays RED.
5. `_spawn` resets both verdict slots (they describe the child that published them).
6. `apply_panel_state` toggles `status--noaudio`; `BRIDGE_PROBE` reports
   `status.noAudio` from the DOM.

`app/panel/panel.js`: `statusKind` maps `no-audio`; the `wireStatus` handler paints the
shell's sentence (visible, not offscreen) with the calm headline; `setStatus` treats
`no-audio` like `error` for the sentence and adds the class; `skinStateWord` returns
`idle`; the strip's word is `No audio` (no `is-error` class).

`app/panel/panel.css`: `.status__dot[data-state="no-audio"]` and
`.status--noaudio .status__dot` in amber `#fbbf24` (same shape as the error dot, different
colour — the panel's own rule that states differ in shape and colour);
`body[data-state="no-audio"] .chrome__off` shows the standby word.

### Measured, after the change (in-process, nothing launched)

`py -3 I:/cc-tmp/laneA-paint-sequence-check.py` -> `"verdict": "PASS"`, rc=0:

```
quiet boot paints: boot=busy, model-loading=busy, model-loaded=busy, device=busy,
capture-started=busy, device-rotated (flat)=busy,
Silent audio device - VoiceMeeter Output (VB-Audio Virtual Cable) [MME] peaked 9.2e-05 < floor 0.002 = no-audio,
Worker finished on silent-device = no-audio
death:  "Worker stopped (exit 3) - Worker finished on silent-device"  kind=no-audio  title='No audio to transcribe'
real error: "Worker error at open-stream - WasapiError: ... 0x8889000A"  kind=error  title='Not transcribing'   (STILL RED)
bare crash after a no-audio death: kind=error                                                              (STILL RED)
```

The two things the brief demanded are both true in that table: a real failure is still
red, and the quiet-machine verdict is not.

Gate: `py -3 _main/panel-exit3-oracle.py --unit --neg-arm` -> `"verdict": "PASS"`, rc=0.
The oracle was UPDATED to encode the new decision (ARM 0/ARM D/ARM E/ARM B expectations
plus the `rendered()` DOM read), and its three negative arms still fail for the right
reasons: the benign-verdict mutant on `done-no-verdict`, the clear-removed mutant on
`ARM E/E4-E6`, and the permissive criterion mutant on `ONE caption`. A mutant that paints
everything red now goes red on the calm cases, so the gate still discriminates.

---

## A2 — THE FREEZE ON OPEN/CLOSE

### Measured from the owner's own log (before proposing anything)

OPEN, the last real boot (2026-10-14):

```
20:10:31.668 shell=webview2 pywebview=6.2.1 python=3.11.8 pid=2740
20:10:31.704 HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true thread=8808
20:10:32.415 STAGING_LOADED core=yes -> navigating to panel           (+0.75 s)
20:10:32.502 RECEIVER_READY captions=0 hasBridge=True                   (+1.3 s)
20:10:32.507 PRELOAD_ACTIVE hasSotto=true methods=15                    (+1.3 s)
20:10:32.523 BRIDGE_START reason=default ... BRIDGE_SPAWNED pid=8300     (the worker DOES start at boot)
20:10:32.530 STATUS "Starting worker..."
20:10:36.952 BRIDGE_LOAD_MS ms=4422 worker_load_s=2.93                   (model load: 4.4 s wall)
20:10:40.587 STATUS "capture-started"                                  (+9 s)
```

CLOSE (tray Quit), the three measured events:

```
2026-10-13 14:09:53.816 TRAY_QUIT -> 14:09:54.722 SHELL_EXIT rc=0 reason=tray-quit   (0.91 s)
2026-10-13 18:09:30.541 TRAY_QUIT -> 18:09:31.064 SHELL_EXIT rc=0 reason=tray-quit   (0.52 s)
2026-10-14 13:59:27.035 TRAY_QUIT -> 13:59:27.728 SHELL_EXIT rc=0 reason=tray-quit   (0.69 s)
```

OPEN-by-hotkey is 11-30 ms per `PANEL_SHOWN` (measured `20:16:44.024 WINDOW_GEOMETRY` ->
`20:16:44.050 PANEL_SHOWN`, `20:16:47.401` -> `20:16:47.412`).

**So the freeze is NOT in the app's own timestamps on this box**: the shell is up in 1.3 s,
the model load is 4.4 s (the worker's own `load_s=2.93`), Alt+C opens in tens of
milliseconds, and Quit returns in under a second. The 2026-10-11 feedback loop (the two
guards) is indeed gone from the log: the `strip-float-off` repaint storm the audit
measured at 30 647 lines does not recur — the whole 30-hour log is 114 394 lines, ~63/min
average, and the recent tail runs at one line every few seconds.

### The two things that ARE measurably wrong at boot (both left as evidence, one fixed)

1. **A second launch dies silently.** `20:16:36.257 shell=webview2 ... pid=18772` and
   `20:16:36.258 APP_USER_MODEL_ID ...` and then NOTHING from that pid, ever: no
   `SINGLE_INSTANCE` line, no `STAGING_LOADED`, no `RECEIVER_READY`, no hotkey, no
   worker. It is absent from the census. The code between those two lines cannot block
   (`shutil.which('python')`, three no-op autostart branches, a logged mutex call), and
   an exception under `pythonw.exe` has nowhere to print. **Cause NOT attributed** — what
   I did is make the next occurrence falsifiable: a `SHELL_STARTUP_STAGE stage=pre-lock`
   line is logged before the mutex (`main()`), so a death there is now distinguishable
   from a death earlier.
2. **The worker's exit-3 churn on a quiet machine.** Measured in the same log: `deaths=8`,
   `restart=8`, `BRIDGE_DEATH rc=3` each cycle, model re-loaded 4.42/4.45 s each time,
   `BRIDGE_RESTART in_ms` growing 1 s -> 2 s -> 4 s -> ... -> 30 s. One full cycle is
   ~2.5 min, i.e. a ~1 GB model reload every 2.5 minutes for hours on a machine with
   nothing routed. This is a plausible contributor to "travamento" on a loaded box but
   I did NOT change it: the exit-3 contract is the worker's (`done.verdict ==
   "silent-device"` iff `exit == 3`, oracle-gated by `verdict-order-oracle.py` and
   `device-silence-oracle.py`) and delaying the worker would break the owner's own
   transcribe-at-boot contract (AGENTS.md F1). **Left for the worker lane, with the
   numbers above.**

### What I deliberately did NOT do

Delaying the worker to the first Alt+C. Measured, the model load is 4.4 s on this box and
the shell is up in 1.3 s, so the load is not the freeze; and `run.cmd` transcribing from
boot is an explicit owner requirement ("quero que o alt c mostre as transcricoes em tempo
real, de qualquer audio do meu pc" — the capture must already be running when he presses
Alt+C).

---

## A3 — ALT+C

### One path, and where it breaks

There is exactly ONE hotkey path: `HotkeyThread` (`:1846`) -> `RegisterHotKey(NULL, _HOTKEY_ID,
mods | MOD_NOREPEAT, vk)` on a private thread with its own message queue, with
`HOTKEY_FALLBACKS = ('Alt+Shift+C', 'Ctrl+Alt+C', 'Ctrl+Shift+C')` tried in order by
`arm_hotkey` (`:2651`) when a key is already owned. There is no `GetAsyncKeyState` polling
loop and no keyboard hook anywhere in the shell (`grep` -> 0 matches for both).

Measured in the owner's own log: **the key is not taken**. `HOTKEY_REGISTER_FAILED`,
`HOTKEY_TRY_FAILED`, `HOTKEY_FALLBACK`, `HOTKEY_UNAVAILABLE`, `HOTKEY_HANDLER_FAILED`,
`RegisterHotKey` — all **0** occurrences in 114 394 lines; four `HOTKEY_REGISTERED` lines,
all `accelerator=Alt+C register=true isRegistered=true`. The fallback chain never had to
fire on this box, which agrees with the 2026-10-07 probe measurement recorded in the
shell's own comment (Alt+C free here). So a conflict with another app is measured NOT to
be the cause.

**The cause is the third state of the cycle being unreachable.** `hotkey_pressed` (`:5693`)
is the owner's own contract: `HIDDEN -> STRIP -> SIDE -> HIDDEN`, decided on `self.panel_mode`.
And `panel_mode` has exactly ONE writer, `place_panel` (`:5742`) — which NOTHING calls
(`grep -n place_panel` on the live shell returns the definition, two comments and a
docstring, zero call sites; the 2026-10-09 P0 refactor removed its callers). So
`panel_mode` stayed `'strip'` forever and the `panel_mode == 'side'` arm — the only thing
that HIDES the panel — was dead code.

The owner's keyboard measured it, ten presses in three seconds:

```
20:16:44.050 PANEL_SHOWN reason=hotkey mode=strip  visible=true   (press 1 -> strip)
20:16:47.412 PANEL_SHOWN reason=hotkey mode=side    visible=true   (press 2 -> side)
20:16:48.484 PANEL_SHOWN reason=hotkey mode=side    visible=true   (press 3 -> SIDE AGAIN)
20:18:01.297 .. 20:18:04.605  PANEL_SHOWN reason=hotkey mode=side  x10 (visible=true each time)
20:18:07.721 PANEL_HIDDEN reason=page visible=false              (the ONLY PANEL_HIDDEN in 114 394 lines)
```

### The change

`app/webview/sotto_webview.py`: `show_strip` sets `self.panel_mode = 'strip'` (`:5842`),
`show_side` sets `self.panel_mode = 'side'` (`:5895`), and `show_panel` records which
surface it put up (`:5633`) so the cycle decides correctly however the panel was opened
(`--show`, tray, the page's `toggle`).

### Measured, after the change (in-process)

`py -3 I:/cc-tmp/laneA-hotkey-cycle-check.py` -> `"verdict": "PASS"`, rc=0:

```
press 1 show_strip | 2 show_side | 3 hide_panel | 4 show_strip | 5 show_side | 6 hide_panel
old arm (writes removed): show_strip, show_side, show_side, show_side, show_side, show_side   <- the defect, reproduced
panel_mode writes in the shell: 5
```

The old arm in that same run reproduces the owner's measurement exactly — that is the
negative control built into the check.

---

## What I did NOT close

1. **A2's freeze cause is not attributed.** The app's own timestamps show no freeze (1.3 s
   to ready, 4.4 s model load, 30 ms Alt+C, 0.5-0.9 s Quit). The measured anomalies are
   the silent second-launch death (cause unknown; now diagnosable via the stage line) and
   the worker's 2.5-minute reload churn (worker lane's file, not mine). If the owner's
   "travamento" is a whole-PC stutter, the churn is the first suspect and it is NOT
   fixed here.
2. ~~The battery is 87/89, both failures another lane's.~~ **CLOSED — the battery is now
   89/89, rc=0** (`node _main/instruments-battery.mjs`, final run). An earlier run in this
   same window gave 87/89 with both failures in `_main/gen-cinematic-repro-oracle.py` and its
   neg arm, caused by a `SyntaxError` in `_main/_design-lane/cine_extra_c1.py` (another lane
   editing it in flight, mtime 2026-10-15T00:09:21Z). That lane finished its edit during my
   run and the last battery is green; the two earlier failures were never mine (Lane A does
   not own that file and did not touch it). Both numbers are recorded because rule 1 of
   this repo says a measurement has a shelf life.
3. **ARM A/ARM B of the exit3 oracle launch shells and were NOT run** (the owner's order
   forbids it). Their assertions were updated to the new decision by reading only.
4. **The painted amber colour was not seen with my own eyes** — no WebView2 run is
   permitted in this session. The DOM contract is asserted through
   `status.noAudio` in `BRIDGE_PROBE`, the `status--noaudio` class and the oracle's
   `rendered()`.
5. **`_main/hotkey-conflict-probe.py` was NOT run on purpose**: registering Alt+C from a
   probe while the owner's shell holds it is the one action that could take his control
   away for a reboot. The log already answers the question it would ask (0 failures).

## Pins (measured after the edits, this session)

| file | bytes | sha256 (16) | mtime |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 522 287 | `c47ef42f69a7e7be` | 2026-10-15T00:16:45Z |
| `app/panel/panel.js` | 160 746 | `a45939163203e439` | 2026-10-14T23:50:12Z |
| `app/panel/panel.css` | 123 233 | `c815691c2235809c` | 2026-10-14T23:53:38Z |
| `_main/panel-exit3-oracle.py` | 64 949 | `dfaa53408499e3d1` | 2026-10-14T23:57:33Z |

(panel.js/panel.css are also being edited by the UI lane in this same window; the hashes
are the state at the moment I measured them and my edits are confined to the status
pipeline named above.)

## Commands used (all with `$env:TMPDIR = I:/cc-tmp`)

```
node _main/instruments-battery.mjs                                   # 89/89 rc=0 (earlier run this window: 87/89, design lane)
py -3 _main/panel-exit3-oracle.py --unit --neg-arm                    # VERDICT: PASS, rc=0
py -3 I:/cc-tmp/laneA-paint-sequence-check.py                        # VERDICT: PASS, rc=0
py -3 I:/cc-tmp/laneA-hotkey-cycle-check.py                          # VERDICT: PASS, rc=0
node --check app/panel/panel.js ; py -3 -m py_compile app/webview/sotto_webview.py
```

Static syntax was re-run after EVERY edit (`py_compile` / `node --check`); no edit was
left unchecked, and nothing was reverted with `git checkout --`.

The live processes measured at the end (passive census): shell `pythonw.exe` pid **2740**
(started 20:10:31), its 5 `msedgewebview2` children, and ONE `sotto_worker.py` child
(pid 35168, the shell's own churn spawn). Nothing of mine is running.