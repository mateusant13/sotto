# Sotto — hot reload

Edit a source file, see it in the app that is **already running**. No restart,
no second instance, no console window on the owner's screen.

Owner directive: *"faz o app ter hot reload com mudança"*.

---

## What it does

| You edit | What happens in the running app |
|---|---|
| `app/electron/panel.html`, `panel.css`, `panel.js` | the live renderer's `webContents` reloads in place (`reloadIgnoringCache`). Same `BrowserWindow`, same geometry, same hotkey, same worker child, same capture session. |
| `worker/*.py` (e.g. `sotto_worker.py`) | exactly **one** python child is restarted, through the existing single-instance path in `worker-bridge.js`. |

Not hot-reloaded, on purpose:

- **`main.js`** — the running main process cannot reload itself.
- **`preload.js`** — a renderer reload does not guarantee a fresh preload, and a
  silently half-applied change is worse than a restart. Restart the app.

---

## The debounce constant

**`DEBOUNCE_MS = 250`** — declared once, in `hot-reload.js`, and re-exported so
`main.js` logs the same number the watcher actually used (`HOT_RELOAD_ENABLED
debounce_ms=250`). The log line, this document, and the code cannot drift apart
because they all read the one constant.

An editor save is not one write: most editors write a temp file and rename it
over the original, which produces 3–5 filesystem events. Without a settling
window a single save would reload the panel 3–5 times, and a worker restart is
not idempotent — it kills a process and spawns another. **250 ms** is above the
tens of milliseconds a rename takes and below the second a human notices.

The debounce is **per kind, not per event**: a panel edit and a worker edit
inside the same window produce one reload *and* one restart — two calls, one for
each thing that changed, and still not four.

## How to turn it off

Start the app with `--no-hot-reload`:

```
electron . --no-hot-reload
```

Nothing is armed at all — the flag is checked before any watcher exists, and the
run prints `HOT_RELOAD_DISABLED reason=--no-hot-reload`. A **packaged** build
(`app.isPackaged`) is exempt for the same reason: there is no source tree to
watch in a shipped app.

---

## How it works

`hot-reload.js` is a watcher and nothing else. It watches **directories**, not
files: a watch on a file dies at the rename that most editors use to save, which
is the classic "hot reload works twice and then stops" bug. A watch on the
directory survives every replacement of its contents.

The module never decides what "reload" means. It decides *when a burst has
settled* and hands the caller the list of files that changed; `main.js` owns the
consequences, because `main.js` is the only thing that knows about the
`BrowserWindow` and the worker bridge.

`main.js` wiring:

- `reloadPanelAssets(files)` calls `webContents.reloadIgnoringCache()`, then
  reads back `globalShortcut.isRegistered(HOTKEY)` and logs it. A renderer reload
  cannot unregister a main-process hotkey, but "cannot" is a claim, so it is
  measured. A dead hotkey logs `HOT_RELOAD_HOTKEY_LOST`.
- `restartWorkerForHotReload(files)` is **no second code path**. It calls the
  existing `stopWorker()` (which is `bridge.stop()`: kills the child, cancels the
  restart and silence timers) and then the existing `startWorker()` (which builds
  one new bridge and calls its own `start()`, which refuses a second start).
  Neither guard is bypassed or re-implemented.

One detail worth naming: `stop()` kills the child, but on Windows kill is a
*request*. `restartWorkerForHotReload` therefore arms `waitForChildExit()`
**before** stopping, and waits for the old pid to actually exit before spawning
the replacement — otherwise two ~2 GB workers could briefly coexist, which is the
exact multi-worker shape the bridge guard exists to prevent. The wait is bounded
(`CHILD_EXIT_TIMEOUT_MS = 5000`) and the outcome (`exit` / `timeout`) is in the
log rather than silent.

Teardown order on quit: the watcher is stopped **before** the worker, so a
watcher still armed cannot restart the worker that the same teardown is killing.

---

## Acceptance — the measured evidence

Everything below was run on this host, 2026-10-06. The instruments live in
`app/electron/_hotreload/` and are run under **`pythonw.exe`**, never
`python.exe` — a console window on the owner's screen is a failed deliverable.

### 0. The syntax gate can go red

A gate that cannot fail is not a gate. `_hotreload/preflight.py` checks both
files this lane wrote **and** a deliberately broken control:

```
$ pythonw.exe _hotreload/preflight.py && cat _hotreload/preflight.json
  "checks": [ main.js rc=0, hot-reload.js rc=0 ],
  "negative_control": [ _syntax_control_broken.js rc=1
      "SyntaxError: Function statements require a function name" ],
  "control_is_red": true, "all_rc_zero": true, "python_ok": true
  "this_process_console": { "console_hwnd": 0, "verdict": "SEM_JANELA_DE_CONSOLE" }
```

### 1. Panel assets — burst of 5 writes to ONE reload

Appended 5 bytes to `app/electron/panel.css` 40 ms apart while the app ran, then
a single write, then the revert. Verbatim from `_hotreload/app.log`:

```
sotto: HOT_RELOAD_WATCH kind=panel dir="H:\\sotto\\app\\electron" debounce_ms=250
sotto: HOT_RELOAD_WATCH kind=worker dir="H:\\sotto\\worker" debounce_ms=250
sotto: HOT_RELOAD_ENABLED debounce_ms=250

sotto: HOT_RELOAD_PANEL files=["panel.css"] events=5 debounce_ms=250
sotto: HOT_RELOAD_PANEL_DONE files=["panel.css"] alive=true visible=false hotkey=Alt+C hotkeyRegistered=true
sotto: HOT_RELOAD_PANEL files=["panel.css"] events=1 debounce_ms=250
sotto: HOT_RELOAD_PANEL_DONE files=["panel.css"] alive=true visible=false hotkey=Alt+C hotkeyRegistered=true
sotto: HOT_RELOAD_PANEL files=["panel.css"] events=1 debounce_ms=250
sotto: HOT_RELOAD_PANEL_DONE files=["panel.css"] alive=true visible=false hotkey=Alt+C hotkeyRegistered=true
```

**5 filesystem events to 1 reload line** (`events=5`). `alive=true` is the live
window after the reload. `panel.css` came back byte-identical:
`sha_matches: true`.

### 2. Worker — one touch to exactly one restart

`_hotreload/workerarm.py`, 100 ms sampling, pids counted **by parentage**
(`ppid == our electron pid`, never by the bare word `sotto`):

```json
{ "old_pid": 2360, "restarts_logged_before_touch": 0,
  "restarts_logged_after_window": 1, "restarts_caused_by_this_touch": 1,
  "burst_lines_total": 1, "max_concurrent_sampled": 1, "samples": 28,
  "distinct_worker_pids": [2360, 17520], "new_pids_now": [17520],
  "our_byte_restored": true, "sha_matches_pre_touch": true }
```

Verbatim from `_hotreload/workerarm.log`:

```
sotto: HOT_RELOAD_WORKER files=["sotto_worker.py"] events=1 debounce_ms=250
sotto: HOT_RELOAD_WORKER_RESTART files=["sotto_worker.py"] oldPid=2360 oldChildExit=exit started=true newPid=17520 liveChildren=1
```

`oldChildExit=exit` is the bounded wait observing the real exit. `liveChildren=1`
is the bridge's own count. The old pid is gone, the new pid is present.

**Command-line proof, matched by path and never by the bare word `sotto`:**

```
PROOF: 1836 python.exe python H:\sotto\worker\sotto_worker.py
AFTER: 3436 python.exe python H:\sotto\worker\sotto_worker.py
```

This proof is read through a PowerShell query, and that query has a **positive
control**: a process carrying a unique token in its command line is started
first, and the same query must find it. Without that control the query would
"prove" anything by returning nothing at all — which is exactly what happened
before the control was added (see *What the measurements corrected* below).
The control passes:

```
CONTROL can_see= True
  pid 544 ppid 10168 pythonw.exe
  "C:\Program Files\Python311\pythonw.exe" -c "import time; time.sleep(45)" SOTTO_CMDLINE_CONTROL_1791266620
```

**The repo's own probe**, untouched, as the brief requires
(`node worker-proc-count-probe.js`, 20 rapid starts inside the backoff window):

```
sotto: PROCCOUNT startsAcceptedInsideWindow=0 of 20
sotto: PROCCOUNT BEFORE the backoff window  = max 1 over 6 samples
sotto: PROCCOUNT AFTER the backoff window   = max 1 over 28 samples
sotto: PROCCOUNT_RESULT PASS baselineMax=0 beforeMax=1 afterMax=1 afterStopMax=0 rc=0
```

### 3. Hotkey — Alt+C still toggles after both reloads

A **real** `Alt+C`, injected at the input-queue level with `SendInput`
(Electron registered the accelerator with `RegisterHotKey`, so the system matches
it before ordinary key dispatch — no focus needed, no focus stolen). Accepted
only when the app logs `reason=hotkey Alt+C`:

```
sotto: PANEL_SHOWN reason=hotkey Alt+C bounds={"x":1528,"y":66,"width":380,"height":900}   <- control, before any reload
sotto: PANEL_HIDDEN reason=hotkey Alt+C                                                     <- pressed twice on purpose
sotto: PANEL_SHOWN reason=hotkey Alt+C bounds={"x":1528,"y":66,"width":380,"height":900}   <- AFTER both reloads
```

```
"altc-control-before-reloads": { "panel_shown_by_hotkey": true, "panel_hidden_by_hotkey": true }
"altc-after-reloads":          { "panel_shown_by_hotkey": true }
```

Re-registration is not needed and does not happen: the accelerator lives in the
main process, and every reload logged `hotkeyRegistered=true`.

### 4. Window census — before, during, after

`EnumWindows` on this machine, recording window **class** and owning pid and **no
titles** (another application's title is not this lane's to read). A console
window is class `ConsoleWindowClass`.

```
WIN_BEFORE   {'visible_total': 29, 'visible_console_windows': 0, 'console_pids': [], 'our_visible_windows': []}
WIN_RUNNING  {'visible_total': 30, 'visible_console_windows': 0, 'console_pids': [], 'our_visible_windows': ['34516:Chrome_WidgetWin_1']}
WIN_AFTER    {'visible_total': 29, 'visible_console_windows': 0, 'console_pids': [], 'our_visible_windows': []}
```

**Zero console windows at all three points.** The only new visible window is the
panel itself (`Chrome_WidgetWin_1` — the Electron panel, which is the product),
and it is gone again after shutdown.

Direct measurement that this lane's own processes own no window
(`_hotreload/winprobe.py`, 25 samples of a spawned `pythonw` child):

```json
{ "child_pid": 35184, "child_exe": "...\\pythonw.exe", "samples": 25,
  "child_windows_ever": [], "child_visible_windows_ever": [],
  "spawned_child_owns_visible_window": false,
  "console_hwnd_of_driver": 0,
  "verdict": "nenhum pythonw filho deste lane teve janela visivel" }
```

### 5. Opt-out — `--no-hot-reload` really disables it

`_hotreload/optout.py`: start the app **with** the flag, edit `panel.css` while
it runs, and observe that no reload line appears. The same edit in section 1
produces one, so the pair is the control.

```json
{ "argv": ["...\\electron.exe", ".", "--no-hot-reload"],
  "startup_said_disabled": true, "startup_said_enabled": false,
  "watch_armed": false, "watch_lines": [], "reload_lines_after_edit": [],
  "verdict_optout_holds": true, "panel_css_restored": true }
```

```
sotto: HOT_RELOAD_DISABLED reason=--no-hot-reload
```

### 6. Nothing left running

```
SHUTDOWN {'killed_pids': [34516, 30036, 23216, 34292, 3436],
          'taskkill_rc': 0, 'survivors': []}
```

A later full process census of every `electron.exe` / `python.exe` /
`pythonw.exe` on the machine reports `electron_pids: []`. Only the exact pids
this lane started were ever signalled.

---

## What the measurements corrected

These are not caveats; they are things the first implementation got wrong and the
instrument caught.

1. **The PowerShell command-line query was BLIND, and looked like a pass.**
   It returned zero rows for the worker, which — read carelessly — is exactly
   what "the worker is not running" would look like. The positive control
   (a process with a unique token) is what exposed it. Two real causes:
   passing the script inline via `-Command` mangles the embedded quotes; and
   `$args[0]` arrived **empty**, so an impossible needle matched **363 of 384**
   processes, because an empty regex matches everything. The needle now travels
   in the environment and the script refuses to run without it.

2. **`DETACHED_PROCESS` (0x8) breaks PowerShell.** Measured in
   `_hotreload/psdiag.json`, one variable at a time:

   | flags | rc | bytes | elapsed |
   |---|---|---|---|
   | `CREATE_NO_WINDOW` + `DETACHED_PROCESS` | 0 | **0** | 0.11 s |
   | `CREATE_NO_WINDOW` only | 0 | 7542 | 0.59 s |
   | none | 0 | 7534 | 0.74 s |
   | `DETACHED` only | -1 | 0 | **hung to a 90 s timeout** |

   The brief asked for `0x08000000` **and** `0x00000008`. The AND half is
   measurably wrong for this executable, so the PowerShell child gets
   `CREATE_NO_WINDOW` alone. The brief's other option — run under `pythonw.exe` —
   is what every driver here does, and `pythonw` has no console to detach from.
   **Reporting this rather than silently choosing.**

3. **A gate that cannot go red.** The first worker-restart evidence was produced
   by an instrument that returned nothing at all. Both the syntax gate and the
   command-line query now carry a control that is measured RED when it should be.

4. **A run of my own was void and I did not use it.** One acceptance run logged
   `startup {"hotkey_registered": false}` and `app.log` opened with
   `sotto: second instance detected; handing the panel to the running one` — my
   `optout.py` had started a second Electron at the same moment. Its numbers
   (`restart_lines: 4`, a `CONFLICT` on `panel.css`) are **discarded, not
   reported**. Four orphaned `electron.exe` from the racing runs were found and
   killed by exact pid.

5. **`worker/sotto_worker.py` is owned by another lane that was writing it while
   this lane tested it.** The first clean acceptance run saw **four** restarts and
   a `CONFLICT` on restore — three of those restarts were somebody else's save,
   which is why "one touch, one restart" is claimed from the isolated
   `workerarm.py` run instead (section 2), where the file went out and came back
   byte-identical. Two fields in `workerarm.json` are mislabelled and are NOT
   evidence: `contaminated_by_concurrent_writer` compares a digest against bytes
   and is therefore always `true`, and `old_pid_still_present` is a union over all
   samples, so it necessarily contains the pre-restart pid. The trustworthy
   fields are the ones quoted in section 2.

---

## Known limits — stated, not hidden

- **`app.isPackaged` is not exercised.** The flag is a one-line condition, but a
  packaged build cannot be produced here, so it is untested rather than proven.
- **The graceful-teardown path is not exercised by the acceptance run.** The run
  stops the app by exact pid with `taskkill /F`, and a forced kill does not run
  Electron's `will-quit`, so `HOT_RELOAD_STOPPED` never appears in these logs.
  The ordering that matters (`stopHotReload` before `stopWorker`) is in the code
  and is reviewed, but it is **not** measured here.
- **`worker/sotto_worker.py` may carry one trailing newline from a touch.** The
  restore rule refuses to truncate a file that changed underneath the run (that
  rule is why this lane never silently eats another lane's edit), and the owning
  lane kept rewriting the file. A single trailing newline is semantically inert;
  the file was left for its owner rather than mutated blind. Worth a glance from
  whoever owns it.
- **Two `ALERTA-JANELA` alarms naming `pythonw` (06:11:21Z, 06:12:21Z) could not
  be attributed.** Those pids were gone before they could be inspected. What is
  measured, not assumed: a `pythonw` child spawned by this lane with the brief's
  exact flags owns **zero** windows across 25 samples (section 4), and this lane's
  console-window count was 0 before, during and after. The alarms name an image,
  not a lane — the most likely producers are another lane's `pythonw`, or the
  census's own `pythonw`-based producer. Flagged rather than dismissed.

---

## Files

| Path | Role |
|---|---|
| `app/electron/hot-reload.js` | the watcher: two directory watches, one debounce, no policy |
| `app/electron/main.js` | the wiring: reload the renderer, restart the one worker, arm/disarm |
| `app/electron/HOTRELOAD.md` | this file |
| `app/electron/_hotreload/` | the acceptance instruments and their measured reports |

### Re-running the acceptance

```
cd H:/sotto/app/electron
pythonw.exe _hotreload/preflight.py     # syntax gate + its negative control
pythonw.exe _hotreload/acceptance.py    # full run -> _hotreload/report.json
pythonw.exe _hotreload/workerarm.py     # one touch, one restart -> workerarm.json
pythonw.exe _hotreload/optout.py        # --no-hot-reload -> optout.json
pythonw.exe _hotreload/winprobe.py      # pythonw owns no window -> winprobe.json
node worker-proc-count-probe.js         # the repo's own single-instance probe
```

Always `pythonw.exe`. Always one at a time — two Electron instances collide on
the single-instance lock and the second one measures nothing.
---

## GATE-CHANGE REQUEST

gate-change-request: n/a — this lane consumed gates (`self-audit-lint.sh`, the
house window census) but found no hole in a GATE'S OWN LOGIC. What it found was
a hole in an instrument **this lane wrote** — a PowerShell query that returned
zero rows and would have read as a pass — and that hole is closed inside
`_hotreload/acceptance.py` by the positive control, not by changing a house gate.
No merge-ready patch to a house gate is therefore owed.

## SELF-AUDIT

**protocolos em falta** — two. (1) "measure the instrument before you believe the
measurement": I ran the worker CommandLine proof through a query that had never
been shown to work, and its empty result was one reading away from being reported
as a pass. A control-before-use protocol (every instrument ships with a case that
must go RED) would have caught it at the first use instead of the third.
(2) A "one owner at a time" protocol for **test files, not just source files**:
two of my own drivers collided on `panel.css` and on the Electron single-instance
lock, voiding an entire run. The rule I know says do not edit another lane's
source; it does not say "do not run a test that writes another lane's file, and
do not start a second app instance".

**verificacao adicional** — run and it changed the result: the CommandLine
positive control. Cost ~2 minutes per driver launch, and it converted a
vacuous "PASS" into a real one. Cheap for what it caught.

**checkboxes novas** — for any lane that runs an app to measure it:
1. `node --check` on every file the lane wrote, AND a deliberately broken control
   that must return non-zero (run: `_hotreload/preflight.py`, control rc=1).
2. Every out-of-process query ships with a positive control that must be FOUND
   and a negative control that must NOT be.
3. Before starting an app instance, assert no other instance of that app is
   running (the single-instance lock turns the second one into a silent no-op).
4. After any test that touched a file, print the sha256 and compare it to the
   pre-test sha — an unrestored file is a defect in the TEST, not in the source.
5. Census the machine for `ConsoleWindowClass` windows before AND after, and
   report the count even when it is zero.

**review por outro subagente** — sim-com-escopo: `hot-reload.js` + the
`main.js` hot-reload block only, specifically asking "can any input to this
watcher produce two reloads or two workers". I accept review. It was not run
because the remaining budget went to making the evidence non-vacuous, and that
trade is worth flagging rather than hiding.

**gate-doubt**
- **verde-de-verdade:** three greens were near-vacuous and each was caught by a
  control, not by reading harder: (a) the worker CommandLine proof — an
  instrument that returned 0 bytes for a needle that WAS present, i.e. it could
  "pass" by seeing nothing; (b) the syntax gate, which I only trusted after a
  broken control returned rc=1; (c) the first full acceptance run, which was
  entirely void because a second Electron instance held the lock — its
  `hotkey_registered: false` is the shape of a gate passing vacuously.
  Named races: my `optout.py` versus the acceptance run (same file, same lock).
- **falta-no-gate:** no house gate checks that a lane left **no processes
  running**; a scenario that crosses this is any future Electron/Python lane,
  where a void run silently leaves `electron.exe` children behind. I found four
  orphans by hand. The window census counts windows, not processes.
- **gate-melhor:** a mechanical "lane left no orphans" check: snapshot every
  `electron.exe`/`python.exe` pid before the lane and after it, and fail on any
  pid that appeared and survived. RED input for it: start `electron.exe .`
  detached, let the lane finish without killing it, and the gate must report
  `leaked=[<pid>]`. Cost: ~30 lines, reusing the toolhelp snapshot already
  written in `_hotreload/whois.py`.

**confianca** — media-alta. Alta for the panel reload, the debounce, the hotkey,
the opt-out and the no-console-window claim: each has a control that can fail and
each failed at least once during development. Media for the worker arm, because
the file under test belongs to another lane that was writing it during the run;
the isolated arm restored the file byte-identically, but the environment is not
quiet and a repeat could differ. Would raise it by: (a) a run of `workerarm.py`
when the owning lane is idle, (b) the peer review above, (c) exercising
`HOT_RELOAD_STOPPED` through a graceful quit instead of a forced kill.

**nao verificado**
- `app.isPackaged` exemption — no packaged build can be produced here.
- Graceful teardown (`will-quit` -> `HOT_RELOAD_STOPPED`) — the run force-kills by
  pid, so this ordering is reviewed but not measured.
- Whether `worker/sotto_worker.py` currently ends with the one trailing newline
  my touch may have added; its owner was rewriting it throughout and the restore
  rule refuses to truncate a file that changed underneath the run.
- Attribution of the two `ALERTA-JANELA ... nome=pythonw` alarms: the pids were
  gone before inspection. Measured instead: a pythonw child of this lane owns
  zero windows across 25 samples, and this lane's console-window count is 0
  before, during and after.

## CACHE/PRICE

Verbatim figures from `bash scripts/cache-task-report.sh SottoHotReload`:

- task/agent: SottoHotReload
- source: `C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoHotReload.jsonl`
- cache: read=18487447 write=0 hit=98.4038% (cache-read / input+cache-read); universe: 103 usage rows from the same file; instrument: `scripts/cache-task-report.sh`
- price: $0.00000000 USD (source: session JSONL `message.usage.cost.total`; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); partition: opencode-zen/space-bunny-free calls=103 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000
- when-failed: break_items=3; WHEN=2026-10-06T05:51:36.081000+00:00 | break_items=2; WHEN=2026-10-06T05:56:47.410000+00:00 | break_items=1; WHEN=2026-10-06T06:09:16.132000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 111698 OMP prefix-ledger rows; window: 2026-10-06T05:51:36Z..2026-10-06T06:09:16Z)
- where-failed: session_id=01a10fc2-9bab-75b3-8296-c1430b9e091f provider=space-bunny-free model=space-bunny-free item_index=39 turn_id=1791265896081 | item_index=107 turn_id=1791266207410 | item_index=204 turn_id=1791266956132
- report generated_at: 2026-10-06T06:14:30.401926+00:00
- usage rows: 103 | model + route: opencode-zen/space-bunny-free
- input tokens: 299888 | output tokens: 85070
- cache-read tokens: 18487447 | cache-write tokens: 0 | hit ratio: 98.4038%
- cost: $0.00000000 USD | prefix breaks: 6 (state=RESOLVED-BREAKS-OMP)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision