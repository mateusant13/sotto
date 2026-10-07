# Sotto — M0 shell (Electron)

The first runnable shell: a frameless overlay docked to the right edge of the
primary display, toggled by a **global** `Alt+C`. No audio, no model, no
transcript. The caption area is a finished-looking receiver waiting for input.

```
app/electron/
  main.js       Electron main process: window, geometry, hotkey, IPC
  preload.js    the contextBridge API — the contract the next milestone calls
  panel.html    the panel document
  panel.css     dark theme, brand accent #7DD3FC -> #A78BFA
  panel.js      the renderer: draws captions, owns the DOM
  run.log       acceptance (b) + (c): 15 s launch, stdout/stderr captured
  selftest.log  acceptance (b'): the same app, self-exiting, with an rc
```

## Run it

```powershell
cd H:\sotto\app\electron
npm install
npm start
```

Then press **Alt+C**. The panel appears docked right; Alt+C again hides it.

`npm start` does not print to a terminal you can scroll (Electron on Windows is a
GUI-subsystem binary), so run it detached and read the log, or use the self-test:

```powershell
.\node_modules\electron\dist\electron.exe . --selftest
```

## Why Electron, and why the Tauri build was not touched

The Tauri/Rust implementation at `../src-tauri` (main.rs, commands.rs,
geometry.rs, memory.rs) cannot be built on this host: cargo hangs indefinitely
at "Updating crates.io index", reproduced on both the gnu and msvc toolchains,
while `curl` on the same host returns in 0.15 s. Rust was out of scope for this
milestone. Nothing under `../src-tauri` was executed, edited, moved, or deleted —
its newest `LastWriteTime` is still 2026-10-05 22:22.

The panel geometry here is a **port** of `../src-tauri/src/geometry.rs`
(`dock_right`), keeping its invariants: dock against the **work area** (screen
minus taskbar), not the full screen; clamp the output inside the work area;
apply the width cap as a fraction of the work area; never produce a
non-finite size. Measured on this host:

```
sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
```

1528 + 380 = 1908 = 1920 − 12, flush right minus the margin; y = 66 centres 900
in the 1032 px work area; the 48 px taskbar is excluded.

**One deliberate difference from the Rust geometry:** the Rust shell used
360 px wide and full-height with a 10 px margin; this one is a fixed 380 × 900
slab, vertically centred, per the Electron brief.

## The hotkey — the thing that has to be trustworthy

`globalShortcut.register('Alt+C', …)` is checked, never assumed. A hotkey that
silently failed to register is exactly the bug this milestone exists to kill, so
the result is printed as a bare token at the start of a line:

- `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide`
- `HOTKEY_REGISTER_FAILED accelerator=Alt+C register=false isRegistered=false reason=another application already owns Alt+C`

grep `run.log` for `HOTKEY_` and you have the answer. On this host:

```
HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide
```

The registration is released on `will-quit`, and a single-instance lock means a
second launch hands the panel to the running one instead of losing the hotkey to
a race.

**Not proven by the logs:** that a *physical* keypress reaches the handler. The
self-test calls the same callback the hotkey calls, so the toggle path is
measured; the OS-side key delivery still needs the owner's finger. Press Alt+C
while `npm start` is running — that is the one check this file cannot do.

## Window behaviour

`frame:false`, `transparent:true`, `alwaysOnTop:true`, `skipTaskbar:true`,
`resizable:false`, `focusable:false`, `show:false` — it starts hidden. Every one
of these platform calls is logged with its result, so "it did that" is a line in
`run.log` rather than a belief:

```
sotto: panel window created frame=false transparent=true alwaysOnTop=true skipTaskbar=true resizable=false show=false focusable=false
sotto: panel setAlwaysOnTop(floating) ok
sotto: panel setVisibleOnAllWorkspaces ok
sotto: panel setFocusable(false) ok
sotto: panel setIgnoreMouseEvents(true, forward) ok
```

The overlay must not steal focus: it shows with `showInactive()`, is
`setFocusable(false)`, and is click-through via `setIgnoreMouseEvents(true,
{forward:true})`. Forwarding still delivers pointer events, so the page can ask
for interactivity **over its own controls only** — `mouseenter` on the slab
turns interaction on, `mouseleave` turns it off, leaving the transparent margin
click-through to whatever is underneath.

## The caption API — what the next milestone calls

Exposed by `preload.js` through `contextBridge` as `window.sotto`:

| call | direction | purpose |
|---|---|---|
| `pushCaption(text, meta?)` | page → panel | add one caption line; renders immediately |
| `setStatus(text)` | page → panel | replace the status line |
| `onCaption(cb)` | main → page | subscribe; main pushes `webContents.send('sotto:caption', {text, meta})` |
| `onStatus(cb)` | main → page | subscribe to status updates |
| `onGeometry(cb)` | main → page | the real slab size, so CSS never guesses |
| `hide()` / `toggle()` / `quit()` | page → main | window control |
| `setPointerInteractive(bool)` | page → main | click-through control |
| `getInfo()` | page → main | hotkey, versions, geometry (a promise) |

One rule prevents a feedback loop: a caption that came **from** a page is
reported to main as `sotto:caption-observed` (a receipt) and never echoed back.
Only a producer in the main process drives `onCaption`.

A later milestone owns the producer. In `main.js` it is two functions:

```js
sendCaption(text, { source: 'loopback' });   // -> IPC -> preload -> DOM
sendStatus('Recording');                     // -> IPC -> preload -> DOM
```

The renderer acknowledges every applied line back to main
(`CAPTION_APPLIED`), which is what makes the receiver **provable from stdout**:
an applied caption is a line in the log, not an assumption.

## What was measured, with rc

| # | check | result |
|---|---|---|
| a | `npm install` | **rc=0** — `changed 63 packages in 6s`; first install of the tree added 13 packages in 2 s; lockfile holds 71 packages; `npm ls --depth=0` **rc=0** → `electron@40.10.2` |
| b | 15 s launch, stdout+stderr → `run.log` | alive after 15 s, `run.log` 867 B, `run.err.log` **0 B**, `HOTKEY_REGISTERED` present, **0** `PANEL_SHOWN` lines (it starts hidden) |
| c | hotkey path | `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide` |
| b' | `--selftest` (self-exiting) | **rc=0**, `SELFTEST_RESULT PASS steps=4` |
| c' | `electron.exe --version` | **EXITCODE=0**, stdout `v40.10.2` |
| d | no cargo/rustc | no `cargo`/`rustc`/`rustup` process on the host; `src-tauri` untouched |

`npm install` is pinned to `electron@40.10.2` exactly, not a caret range: the
44.5.1 binary download **stalled** on this host (open socket to the GitHub CDN,
95.9 MB RSS, zero bytes written for 10 minutes) while a plain range GET of the
same host returned 1 MB in 657 ms. 40.10.2 was already in the local Electron
cache, so the build needs no download at all. Everything used here —
`globalShortcut`, `contextBridge`, transparent frameless windows,
`setIgnoreMouseEvents` — behaves the same in both.

## Friction found while building this (cost real time, worth recording)

1. **`npm install` and `npx` hang on this host, intermittently.** Flat CPU, no
   sockets, no log output; it cleared on its own and a later identical command
   finished in 6 s. Three separate wedged runs, three clean ones. There is no
   diagnostic for it, which makes a green hard to distinguish from a hang.
2. **A green `npm install` that ships nothing.** Electron 44 dropped its
   postinstall hook, so `npm install` reported rc=0 with 13 packages while
   `electron.exe` did not exist — the binary is fetched on *first launch*
   (`node_modules/electron/index.js`). A package count is not an installed
   runtime; the binary has to be checked.
3. **Electron's stdout is invisible to PowerShell's `&` operator.** The binary
   is GUI-subsystem on Windows, so `& .\electron.exe --version` returned an empty
   `$LASTEXITCODE` and no output *and left the app running* — a stray instance
   that then held the single-instance lock, so the next launch logged
   `second instance detected` instead of starting. `Start-Process
   -RedirectStandardOutput … -Wait -PassThru` captures it and returns a real rc.

## Notes

- `node_modules/`, `package-lock.json`, `run*.log`, `selftest*.log` and
  `npm-install*.log` are build/run artefacts of this directory, not sources.
- `npm install -g` was never used; nothing global was touched.