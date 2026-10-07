# Sotto — the app

**This is the app.** `run.cmd` here is what you run. Double-click it, or type
it from a terminal:

```
H:\sotto\app\webview\run.cmd
```

It starts hidden and waits for **Alt+C**, which is the global toggle: press it
once and the caption panel appears, press it again and it goes away. Nothing
appears on screen until you ask for it.

**The worker starts by default.** Double-clicking `run.cmd` is enough to be
transcribing — the panel that Alt+C shows is fed by a live capture process. The
worker used to be behind a flag that `run.cmd` never passed, so the documented
launch opened a panel announcing a wait for audio that could never end (audit
`docs/audit/auditoria-completa-20261007.md`, F1). The default is decided by the
**shell's** parser, not by this wrapper, so there is no second flag table in
batch to drift.

```
run.cmd                  start hidden, TRANSCRIBE, wait for Alt+C
run.cmd --show           start with the panel already up
run.cmd --no-worker      shell only: start NO transcription worker
run.cmd --with-worker    accepted alias — the worker is the default
run.cmd --help           every flag
```

| mode | worker | what the panel says |
|---|---|---|
| *(default)* | **ON** — spawned on the first panel load | the worker's real state, then captions |
| `--no-worker` | **OFF** | one honest status: *No transcription worker is running (started with --no-worker)*, in the error colour, because captions are impossible in this mode |
| `--with-worker` | **ON** (alias) | identical to the default; it only *forces* the worker where an automatic opt-out would decline it |
| `--dump-dom`, `--selftest`, `--memory` | **OFF**, unless `--with-worker` | unchanged: these measure the panel or the shell, not transcription, and a run that passes one does not pay a ~2 GB model load. The log line is `WORKER_AUTOSTART=declined reason=measurement-flag(--dump-dom)` |
| `SOTTO_NO_WORKER=1` in the environment | **OFF** | same honest status; the reason logged is `env` |

`--with-worker` is kept as an **alias** because lane instruments pass it
(`_main/_app-drive.py`, `_main/_live-launch.py`); it changes no behaviour and can
no longer be the *reason* a run has a worker. `--show --no-worker` starts the
panel up immediately as a shell only.

Every run logs the decision in one line whose shape is unchanged —
`WORKER_AUTOSTART=started|declined reason=…` — with `reason=default` for a plain
double-click.

### Alt+C is the only control, so its failure modes are first-class

- **Registration, with a fallback chain.** `Alt+C` is registered on its own thread
  (`HotkeyThread`, `MOD_NOREPEAT`). If another program already owns it, the shell
  does NOT go quiet — it used to log one line and run on with a dead hotkey and no
  message, which is a bricked app that looks like a working one. It now walks
  `HOTKEY_FALLBACKS` (`Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C`), registers the
  first free one and logs `WARN HOTKEY_FALLBACK requested=Alt+C using=…`; the
  panel's footer names the key that actually works. If **every** one is taken it
  raises a one-off error dialog on a daemon thread (the panel cannot be the
  messenger — nothing can open it) and keeps transcribing. `--hotkey` overrides the
  request. Measured on this box: `Alt+C` free, `Alt+F9` owned by another program
  (`_main/_audit-hotkey-probe.py`), and the whole path — register → real
  `WM_HOTKEY` → handler → `toggle_panel('hotkey')` → fallback under a taken key →
  mutex — is `VERDICT: GREEN` in `_main/_audit-hotkey-delivery.py`.
- **One shell at a time.** A second shell cannot register Alt+C (`RegisterHotKey`
  → 1409) and used to keep running anyway, invisible, so the owner's Alt+C answered
  the FIRST (possibly stale) instance — indistinguishable from a broken key.
  `take_single_instance_lock()` (a `Local\SottoShell` mutex, released by the kernel
  when the process dies, so there is no stale lock) refuses the second launch with
  a log line and rc 0.
- **The toggle asks the window, not a cache.** `toggle_panel` reads
  `IsWindowVisible` before deciding. The old version trusted `self.visible`, which
  pywebview's navigation-time `form.Show()` and the visibility re-assert can
  invalidate behind its back; a stale `True` made the first Alt+C a no-op HIDE —
  "Alt+C does nothing" until you press it twice.

### Start with Windows

```
run.cmd --install-autostart     # writes HKCU\...\Run\Sotto, then exits
run.cmd --autostart-status      # installed? and does it still point at THIS checkout?
run.cmd --uninstall-autostart   # remove it
```

The Run value is
`"…\Python311\pythonw.exe" "…\app\webview\sotto_webview.py" --log "…\_main\webview-run.log"`
— **never `run.cmd`**, because a `.cmd` is a console program and Windows would flash
a console window at every login (forbidden in this repo; the house census names
stray consoles). `pythonw.exe` is GUI-subsystem: no console, no window, and the
shell then does exactly what a double-click does — worker included. **Installed on
this box 2026-10-07** and verified by an independent read:

```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run
    Sotto    REG_SZ    "C:\Program Files\Python311\pythonw.exe" "H:\sotto\app\webview\sotto_webview.py" --log "H:\sotto\_main\webview-run.log"
```

Task Manager → **Startup** shows it as *Sotto*. `--autostart-status` exists because
the value embeds absolute paths: if the checkout ever moves, the status line says
`matches this checkout: False` instead of silently starting nothing at login.

### The exit contract — `run.cmd` returns the CHILD's status

`start` detaches the app, so the wrapper never sees the interpreter's status;
it used to answer **0 for anything**, including a flag argparse rejects:

```
run.cmd --bogus-flag      ->  rc=0, no output, no log bytes, no process
```

That is fixed by a **pre-flight**: before anything is spawned, the wrapper runs
the shell's own parser on the same argument list

```
"%PYW%" "%SHELL%" --check-args %*
```

and spawns the app only when that returns 0. A rejected list exits **2** (the
child's own argparse status) and appends one receipt line to the run log —
`sotto: ARGS_REJECTED rc=2 by=run.cmd-preflight`. `--check-args` is hidden from
`--help`, so the usage above is byte-for-byte what it always was, and there is
no second flag table in batch to drift from the shell's argparse: add a flag to
`parse_args` and the wrapper validates it, with no change to `run.cmd`.

What the pre-flight does **not** cover: a flag list argparse accepts but that
fails later (missing pywebview, a broken panel path) still reports 0 if the
spawn itself succeeded. Covering that needs waiting for a readiness line (the
shell's first, `sotto: shell=webview2 ... pid=<N>`), which would hold the
caller's console open for the app's start; the argument list is the contract
this wrapper owns.

Oracle (both colours, one command):

```
py -3 H:\sotto\_main\run-cmd-exit-oracle.py           # the live wrapper
py -3 H:\sotto\_main\run-cmd-exit-oracle.py --neg-arm # pre-fix wrapper in a
                                                      # COPY -> arm 1 must be RED
```

---

## What this hosts

| file | what it is |
|---|---|
| `sotto_webview.py` | **the shell.** WebView2 (pywebview 6.2.1 + pythonnet). Owns the window, the global hotkey and the worker bridge. |
| `run.cmd` | **the launcher.** Finds pythonw, starts the shell, leaves a log. |
| `hot_reload.py` | panel-asset / worker-source watcher + debounce. Reload the panel in place when you save. |
| `stage.html` | an empty page opened first, so the page↔host bridge is ready before the panel is ever parsed. See below. |
| `panel.{html,css,js}` | **not here** — loaded byte-for-byte from `app/panel/`, unmodified. |

`stage.html` exists for one reason: the page→host bridge must exist *before*
`panel.js` runs at the bottom of `<body>`, or the panel paints its
"Preload bridge missing" error. Opening an empty page first, registering the
bridge, then navigating to the panel makes the panel's **first** parse correct.
Deleting `stage.html` breaks that ordering.

---

## The Electron tree is legacy

`app/_legacy-electron/` is the **earlier shell**. It is kept for two reasons and
two only:

1. **it owned the panel.** `panel.html`, `panel.css`, `panel.js` lived there and
   this shell loaded them unmodified. They live in `app/panel/` since
   2026-10-07 and are loaded from there — the old folder was named after a shell
   the app is not, so the panel and the dead tree were separated.
2. **it is the reference.** `--dump-dom` in this shell runs the Electron arm's
   own probe text, so the two arms' layout numbers can be diffed.

Legacy files — the Electron shell itself, not the panel:

| file | what it was |
|---|---|
| `main.js` | the Electron main process |
| `preload.js` | Electron's `contextBridge` surface (ported here as a WebView2 script) |
| `worker-bridge.js` | the Electron worker bridge (ported here as `WorkerBridge`) |
| `hot-reload.js` | the Electron hot-reload watcher — see below |
| `package.json`, `node_modules/` | the Electron toolchain, no longer used to run the app |

**It is not a fallback.** The owner ruled (2026-10-06): *"sem fallback. webview2
é pra funcionar, pronto."* Nothing in this shell reaches for Electron, and
the WebView2 shell costs **+33% memory** (416 MB vs 312 MB) — measured, and
ruled on anyway.

### About `hot-reload.js`

`hot_reload.py` is **not a rival** to `app/_legacy-electron/hot-reload.js`. That module
is CommonJS and `require`s `node:fs`; a Python process cannot load it, so it
was not portable and could not be reused. What `hot_reload.py` reproduces is
the *contract* — watch directories not files, 250 ms debounce per kind, decide
when and hand the caller the settled list — with the engine-appropriate
mechanism (`ReadDirectoryChangesW` instead of `fs.watch`).

---

## Hot reload

Edit `app/panel/panel.css` (or `.html`, `.js`) while the app is running.
After 250 ms of quiet the panel reloads **in place** — same window, same
process, Alt+C keeps working. Touch `worker/*.py` and the one worker restarts.

`--no-hot-reload` turns it off.

To check the watcher itself without starting a window:

```
py -3 H:\sotto\app\webview\hot_reload.py --selftest
```

Six arms against real files in a temp directory: a burst of 8 writes → exactly
1 reload; one write → exactly 1; three rename-overs → exactly 1 **and the
watcher is still alive afterwards** (the failure this design exists to
prevent); a worker `.py` → its own kind; a non-asset file → nothing.

---

## The panel as TEXT (no screenshot, no vision)

The owner's order (2026-10-06): *"faz uma versao do sotto ou painel que tu pode
ver sem precisar da visao"*. Until now the only way to know what the panel
shows was a screen capture. Now the app writes a dump —

```
H:\sotto\_main\panel-state.json
```

— every **2 s** and **on request**, holding what the panel shows right now: the
`live` lines (each marked `provisional` or committed), the named state, the
caption counters, the endpoint being tapped, and the worker's `peak` /
`nonzero_blocks`. Read it with the `read` tool, or:

```powershell
py -3 H:\sotto\app\webview\panel_state.py --read      # dump + its AGE
py -3 H:\sotto\app\webview\panel_state.py --read --json
py -3 H:\sotto\app\webview\panel_state.py --request   # dump NOW, no waiting
```

`_main/panel-state.request` is the on-demand sentinel: the app removes it and
dumps on its next tick. `panel_state.py` is a **read channel** — it changes
nothing the owner sees.

**Where the data comes from (no second path).** Every field is state the shell
already holds: the worker bridge's own `state` and counters; the shell's
`caption_log`; the panel's own live box read over the existing `exec_js` seam
(the read a screenshot makes, in text); the `WORKER_STATS` line the bridge
already reads off the worker's stderr — kept whole here, so `peak` and
`nonzero_blocks` are readable instead of discarded after three lines; and the
endpoint from the worker's own `device` / `device-rotated` status messages.

**Freshness.** The dump carries `writtenAt` (ISO, with offset),
`writtenAtEpoch` and `staleAfterSeconds`. The authoritative age is
`now - writtenAtEpoch`, computed by the READER, never frozen into the JSON — a
producer that died cannot update a number inside the file it stopped writing,
and a self-reported age would then be the very lie this design exists to
remove. `ageSeconds` in the JSON is therefore defined as the age AT WRITE.

The acceptance run and its real output are in
`docs/audit/painel-texto.md`.

---

## No console window

A normal launch goes through `pythonw.exe`, a GUI-subsystem binary: Windows
allocates no console for it. Measured detached on this box —
`stdout=None stderr=None GetConsoleWindow()=0`.

`pythonw` therefore has no stdout, so `run.cmd` passes `--log` and the receipt
of a run is the **file**, not the screen:

```
H:\sotto\_main\webview-run.log
```

`--help`, `--dump-dom`, `--selftest` and `--memory` are the exception: they
print, so they run under `python.exe` and write to the terminal you already
have. That creates no new window.

---

## Runtime, as actually installed

```
py -3 -m pip show pywebview    -> 6.2.1
py -3 -c "import pythonnet"    -> ok
WebView2 runtime, registry HKLM\...\EdgeUpdate\Clients\{F3017226-...}
FOUND pv ('154.0.4258.53', 1)
```

Nothing had to be installed for this shell. `watchdog` is **not** installed and
is not needed — `hot_reload.py` uses `ReadDirectoryChangesW` directly.

Native `H:\` paths only: a node-style `./` relative path does not execute on
this box (rc=127, measured).