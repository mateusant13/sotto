

## 2026-10-06 04:52Z — THE SHELL CRASH IS FIXED AND ALT+C IS REGISTERED (live captions observed)

Root cause of "alt c nao faz nada", measured from the owner's own error dialog:
`ReferenceError: Cannot access 'argValue' before initialization` — a TDZ crash at
module load. `app/electron/main.js:33` called `argValue('--hotkey')` while the
`const argValue = ...` that defines it sat at line 65. The main process died
before `createPanel()` and before `globalShortcut.register(...)`, so the ONLY
thing the owner could see was Electron's "A JavaScript error occurred in the main
process" dialog and a hotkey that did not exist.

A second instance of the SAME defect was found and fixed while verifying: line 80
read `TRANSCRIBE_FILE !== null` while `const TRANSCRIBE_FILE` was declared at 108.

Fixes (both in `app/electron/main.js`):
1. `const HOTKEY = argValue('--hotkey') || 'Alt+C'` -> `let HOTKEY = 'Alt+C'`
   declared early, assigned at line 77 AFTER `argValue` exists.
2. `START_VISIBLE` now calls `argValue('--transcribe')` directly instead of
   reading the not-yet-initialised `TRANSCRIBE_FILE`.

Verify command (detached, hidden, native path — `./node_modules/...` resolves to
rc=127 in this shell):
    python -c "import subprocess,io; fh=io.open(r'H:\\sotto\\app\\electron\\panel-run.log','w'); subprocess.Popen([r'H:\\sotto\\app\\node_modules\\electron\\dist\\electron.exe','.','--with-worker'],cwd=r'H:\\sotto\\app',stdout=fh,stderr=subprocess.STDOUT,creationflags=0x00000008|0x08000000)"

Log `app/electron/panel-run.log`, 130 lines, ZERO errors in it. Lines that matter:
    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide
    panel window created frame=false transparent=true alwaysOnTop=true skipTaskbar=true resizable=false show=false focusable=false
    panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
    BRIDGE_STATUS state="capture-started" kind=busy
    BRIDGE_CAPTION text="checked" start=0.56 end=1.12 model="nemotron-3.5-asr-streaming-0.6b-int4"
    CAPTION_APPLIED lines=1 text="checked"      <-- FIRST TIME EVER, live
    ... CAPTION_APPLIED up to lines=23, 29 captions total in 40 s

So the whole chain is proven live end to end for the first time:
audio -> worker -> bridge -> renderer DOM caption.

STILL NOT PROVEN / OPEN:
- The owner must press Alt+C and SEE the panel. The panel is created `show=false`
  and is toggled by the hotkey; this receipt proves the registration, not the
  toggle, because pressing keys on his desktop is not something Main may do.
- Fragments are 1-2 words ("checked", "has", "under", "o", "so", "is", "ven").
  Sentence assembly is NOT done.
- The device the bridge passed is still the literal
  `Mapeador de som da Microsoft - Input` (see BRIDGE_START), yet captions came
  out — so the worker is not honouring `worker/config.json` verbatim, or the
  mapper is carrying the audio. That contradiction is UNRESOLVED and is the next
  measurement: runtime tap discovery (resolve the loopback of the current default
  render endpoint) is still the right fix.
