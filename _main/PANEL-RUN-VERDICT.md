# PANEL RUN VERDICT — the first real measurement of Sotto's desktop panel

Lane: `chore/panel-run-1` @ worktree `H:\sotto-wt\panelrun`.
Owner: `_main/PANEL-RUN-VERDICT.md` (this file). Nothing else in the repo was edited.

`a3c288f`'s message says **"verified"**. This file measures it. The word
**"verified" in that commit message was a CLAIM, not a measurement** — see §6.

## 1. THE ENTRY POINT

**The app is `app/webview/run.cmd`; the panel is hosted by `app/webview/sotto_webview.py`.**

Source, quoted:

- `AGENTS.md:76` — `` | `app/webview/run.cmd` | **THE APP.** Double-click it, or run it: starts hidden, **starts the WORKER**, waits for Alt+C. ``
- `AGENTS.md:81` — `` | `app/panel/` | **THE PANEL.** `panel.{html,css,js}` and the modules the document loads ... hosted unmodified by the WebView2 shell. ``
- `app/webview/run.cmd:3-9` (the file's own banner):
  ```
  REM  Sotto -- THE APP.  Double-click this file, or run it from a terminal.
  REM    run.cmd                  start hidden, TRANSCRIBE, wait for Alt+C
  REM    run.cmd --show           start with the panel already up
  REM    run.cmd --no-worker      shell only: start NO transcription worker
  ```

**There is no compiler and no build step.** The panel is
`panel.html` + `panel.css` + `panel.js` (85 KB) + modules + 5 theme
stylesheets, hosted by a pywebview/WebView2 shell. `mingw g++` is on PATH
(`H:\msys64\mingw64\bin\g++.exe`) but **nothing in the panel path is C++**;
the `-j` warning in my briefing does not apply to this project.

## 2. DOES IT BUILD? — `pywebview` 6.2.1, python 3.11.8, WebView2 154.0.4258.62

| measurement | result | how the exit code was captured |
|---|---|---|
| `python sotto_webview.py --help` | **rc=0**, 4048 B stdout, 0 B stderr | `Start-Process -Wait -PassThru`, read `.ExitCode` |
| `python sotto_webview.py --selftest --no-hotkey --no-tray` | **rc=3** | same |
| `python sotto_webview.py --dump-dom --dump-dom-wait 4 --no-hotkey --no-tray` | **rc=0**, 7272 B stdout | same |

`--help` prints `usage: sotto-webview ...` with all 27 flags — the shell's own
argparse loads, imports pywebview and parses.

`--selftest` returning **rc=3 is not a build failure**, and it is the shell
refusing its own precondition, in its own words:

```
sotto: SELFTEST refused=--no-hotkey (nothing registered to prove)
sotto: SHELL_EXIT rc=3 reason=selftest-needs-hotkey
```

`AGENTS.md:259-262` requires a measurement run to pass `--no-hotkey` ("a probe
that registers it answers the owner's keypress with its own panel"), so
`--selftest` **cannot** be satisfied by a well-behaved measurement run. That is
a contract contradiction in the tool, not a defect in the panel.

## 3. DOES IT RUN? — YES. A REAL WINDOW, A REAL DOCUMENT, A REAL BRIDGE.

From the `--selftest` run (same process that created the window):

```
sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=17076
sotto: panel window created frame=false transparent=true alwaysOnTop=true
       skipTaskbar=true resizable=false show=false focusable=false engine=WebView2/pywebview
sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
sotto: WINDOW_ICON ... file_exists=true file_sha256=d3442cfc32c96e33 ...
sotto: WINDOW_ICON_APPLIED applied=true path=...\app\webview\sotto.ico handle=205661507
sotto: STAGING_LOADED core=yes -> navigating to panel ...\app\panel\panel.html
sotto: RECEIVER_READY captions=0 hasBridge=True placeholder="Waiting for audio ..."
sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
```

And from `--dump-dom` (**rc=0**) — the browser's OWN computed values for the
live document, not a grep of the source:

```
sotto: BRIDGEPROBE {"hasPanelElement":true,"hasSotto":true,"readyState":"complete",
  "methods":["pushCaption","setStatus","onCaption","onStatus","onGeometry","hide",
  "toggle","quit","setPointerInteractive","getInfo","captionApplied","statusApplied",
  "ready","clearApplied"],
  "panelSaidBridgeMissing":false,"title":"Sotto",
  "url":"file:///H:/sotto-wt/panelrun/app/panel/panel.html"}
sotto: BRIDGE_GATE=GREEN hasPanelElement=true
       url=file:///H:/sotto-wt/panelrun/app/panel/panel.html panelSaidBridgeMissing=false
sotto: SHELL_EXIT rc=0 reason=dump-dom
```

So, measured: **the window is created, `panel.html` navigates, the panel's
JavaScript parses and executes, the 14-method bridge binds, and the document
reaches `readyState: complete`** — on the real WebView2 runtime, not a mock.

### 3a. The panel must NOT be on the owner's screen — and it was not

`AGENTS.md:53-59` forbids a stray window; `--show` is the owner's key only. No
arm below passes `--show`. Every arm additionally passes `--no-hotkey` and
`--no-tray`, and every shell arm was launched through `Start-Process
-NoNewWindow`, so no console was allocated either. The shell's own log records
the refusal to show:

```
sotto: PANEL_SHOW_REFUSED reason=not-asked ... show_requested=false panel_shown=false count=1
sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup panel_shown=false
```

## 4. THE FIVE THEMES — MEASURED, IN A REAL BROWSER, WITH THE GATE PROVEN IN BOTH COLOURS

`py -3 _main/_theme-probe-arm.py --neg-arm` → **rc=0, `VERDICT: GREEN`**, browser
`msedge.exe`, `--headless=new`, `--virtual-time-budget`, loading a COPY of the
REAL `app/panel/panel.html`.

This is not "the class changed". It reads `getComputedStyle` on the caption
element `panel.js` actually builds, per theme:

| theme | label | computed family | live size/weight/leading | align | halo | accent |
|---|---|---|---|---|---|---|
| theme-1 | Teleprompter | Barlow Condensed | 30px/700/31.8px | left | glow | #F2E9D8 |
| theme-2 | Broadcast | IBM Plex Mono | 20px/600/27.6px | left | flat | #FF6A55 |
| theme-3 | Manuscrito | Newsreader | 23px/400/37.26px | left | flat | #A9C1D9 |
| theme-4 | Cinema Card | Fraunces | 24px/400/36.48px | left | flat | #E4B363 |
| theme-5 | Instrumento | Space Grotesk | 24px/700/31.2px | left | flat | #5FD3A7 |

`themeCountLinked: 5`, `fontSourceWoff2: 14`, and each theme's own face really
loads (`faces=1`).

**The instrument can say no.** All three controls went RED-as-expected in the
SAME run — this is the "gate must be able to say NO" requirement, satisfied by
the project's own probe:

- `CONTROL control-theme` (five theme stylesheets deleted): **RED, 53 problems** —
  every theme collapses to `-apple-system`, 15px/400/22.5px, accent `#7dd3fc`.
- `CONTROL control-fonts` (bundled woff2 removed): **RED, 5 problems** —
  `faces='error:NetworkError'`.
- `CONTROL control-weight` (Barlow Condensed 400 `@font-face` removed): **RED, 2 problems**.
- `CONTROL persist-virgin`: **RED-as-expected** — a profile that never chose
  falls back to `theme-1`, so `PERSISTENCE: GREEN` is not vacuous.

Persistence measured too: one document chose `theme-3`, and a SECOND,
independent document against the SAME profile came up already wearing it
(`themeAtLoad='theme-3'`).

**Honest caveat the probe itself prints:** `document.fonts.check()` answered
TRUE for a family that does not exist on this Chromium, so `check()` cannot
falsify a family name; the falsifiable half is `document.fonts.load()`, which
is what the `faces=` column and `control-fonts` arm use.