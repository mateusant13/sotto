# Sotto — the app

**This is the app.** `run.cmd` here is what you run. Double-click it, or type
it from a terminal:

```
H:\sotto\app\webview\run.cmd
```

It starts hidden and waits for **Alt+C**, which is the global toggle: press it
once and the caption panel appears, press it again and it goes away. Nothing
appears on screen until you ask for it.

```
run.cmd                  start hidden, wait for Alt+C
run.cmd --show           start with the panel already up
run.cmd --with-worker    also spawn worker\sotto_worker.py and transcribe
run.cmd --help           every flag
```

Add `--show --with-worker` together for "start now and start listening".

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
| `panel.{html,css,js}` | **not here** — loaded byte-for-byte from `app/electron/`, unmodified. |

`stage.html` exists for one reason: the page→host bridge must exist *before*
`panel.js` runs at the bottom of `<body>`, or the panel paints its
"Preload bridge missing" error. Opening an empty page first, registering the
bridge, then navigating to the panel makes the panel's **first** parse correct.
Deleting `stage.html` breaks that ordering.

---

## The Electron tree is legacy

`app/electron/` is the **earlier shell**. It is kept for two reasons and two
only:

1. **it owns the panel.** `panel.html`, `panel.css`, `panel.js` live there and
   this shell loads them unmodified. Moving them would be churn, not work.
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
é pra funcionar, pronto."* Nothing in this directory reaches for Electron, and
the WebView2 shell costs **+33% memory** (416 MB vs 312 MB) — measured, and
ruled on anyway.

### About `hot-reload.js`

`hot_reload.py` is **not a rival** to `app/electron/hot-reload.js`. That module
is CommonJS and `require`s `node:fs`; a Python process cannot load it, so it
was not portable and could not be reused. What `hot_reload.py` reproduces is
the *contract* — watch directories not files, 250 ms debounce per kind, decide
when and hand the caller the settled list — with the engine-appropriate
mechanism (`ReadDirectoryChangesW` instead of `fs.watch`).

---

## Hot reload

Edit `app/electron/panel.css` (or `.html`, `.js`) while the app is running.
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