# Live captions — measured, 2026-10-06

## The defect, and the one line that fixed it

The worker was tapping the wrong endpoint. `worker/config.json` pointed
`audio.device` at the Windows-default mapper:

```
"device": null,
"preferred_devices": ["Mapeador de som da Microsoft - Input", "VoiceMeeter Output", "CABLE Output (VB-Audio Virtual Cable)"]
```

On this machine the **default render endpoint is a virtual device**
(`VoiceMeeter Input (VB-Audio Virtual Cable)`), so "the loopback of the default
endpoint" carries nothing. A 10-candidate control (3 s silence vs. 3 s of
`sample1.flac` written to the default output with an explicit
`sounddevice.OutputStream`, frames counted) showed the mapper flat at
`peak=0.000153` in BOTH arms, while `CABLE Output (VB-Audio Virtual Cable)`
moved with the audio.

The fix is the device, not the code:

```json
"device": "CABLE Output (VB-Audio Virtual Cable)"
```

## Before / after, same worker, same box

| | before (mapper) | after (CABLE Output) |
|---|---|---|
| device | Mapeador de som da Microsoft - Input | CABLE Output (VB-Audio Virtual Cable) |
| audio captured | 24.64 s | 29.68 s |
| nonzero blocks | 5 / 249 | **296 / 300** |
| peak | 0.000122 | **0.766876** |
| rms | 0.0000266 | **0.0693245** |
| chunks | 44 | 53 |
| blanks | 308 / 308 (blank_frac 1.0) | 371 / 651 (blank_frac 0.5699) |
| **captions** | **0** | **31** |
| tokens | 0 | 59 |
| verdict | `model-emitted-nothing` | **`captions-emitted`** |
| rtf | 0.37 | 0.17 |

Commands, both rc=0:

```
cd H:/sotto/worker
python sotto_worker.py --max-seconds 25 --stats-interval 5 > runs/repro-live.log 2>&1   # BEFORE
python sotto_worker.py --max-seconds 30 --stats-interval 5 > runs/live-cable.log 2>&1   # AFTER
```

Raw output of the after-run:

```
{"type": "status", "state": "device", "device": "CABLE Output (VB-Audio Virtual Cable)", ...}
{"type": "status", "state": "capture-started", "device": "CABLE Output (VB-Audio Virtual Cable)", "rate": 16000, "block": 1600}
WORKER_STATS tag=final blocks=300 block_samples=480000 nonzero_blocks=296 peak=0.766876 rms=0.06932448 resampled_samples=480000 chunks=53 captions=31 tokens=59 frames=651 blanks=371 blank_frac=0.5699 empty_chunks=20 queue_drops=0 audio_s=29.68 infer_wall_s=4.94 rss_mb=2141.6
{"type": "status", "state": "done", "verdict": "captions-emitted", ..., "captions": 31, "tokens": 59, "rtf": 0.17, "peak_rss_mb": 2141.7}
```

Sample captions emitted (verbatim, in order):

```
{"type": "caption", "text": "actually t", ...}
{"type": "caption", "text": "ning", "start": 28.0, "end": 28.56, ...}
{"type": "caption", "text": "s", ...}
{"type": "caption", "text": "on", "start": 29.12, "end": 29.68, ...}
```

## What this proves and what it does NOT

PROVEN: live system audio reaches the model and the model emits captions.
The blocking defect — "no captions, ever" — is closed, and the file that closes
it is `worker/config.json`.

NOT PROVEN, and each is a real gap:

1. **The captions are fragments** (`"s"`, `"on"`, `"ning"`), not sentences.
   The panel needs a sentence-assembly layer over the streaming output, and the
   per-token cadence needs a look. Nothing here shows usable prose yet.
2. **The panel has not been exercised with these captions.** The path
   main->IPC->preload->DOM is proven with canned JSONL (`--bridge-selftest`,
   8 arms); whether the live worker's lines render in the panel is unverified.
3. **A silent input would still look like success**: the `done` line carries
   `captions-emitted` or `model-emitted-nothing`, but `model-emitted-nothing`
   does not say whether the input was silent. That distinction is still owed.
4. **Why `CABLE Output` is live at all was not established.** It carried
   `peak=0.442` even in the "silence" arm, which means something on this box
   feeds VB-CABLE continuously while nothing of mine was playing (checked:
   no ffplay/ffmpeg/vlc/mpv process). The tap is proven to MOVE with audio;
   the constant floor is unexplained and must be before any accuracy claim.
5. `Mapeador` staying flat while 48 000 frames were written to the default
   output suggests PortAudio's `device=None` did not resolve to the same
   endpoint Windows calls default. Unverified; it changes what "tap the default"
   should mean in code.


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


## 2026-10-06 04:55Z — FRAGMENTS ARE JOINED, AND THE TAP CONTRADICTION IS RESOLVED

### (b) The device contradiction, measured both arms in the same minute
| arm | device the worker opened | result |
|---|---|---|
| worker ALONE (reads `worker/config.json`) | `CABLE Output (VB-Audio Virtual Cable)` | `nonzero_blocks=0 peak=0.000031 captions=0` — silence |
| via the bridge (`--with-worker`) | `Mapeador de som da Microsoft - Input` | **29 captions with text** |

Cause, one line: `app/electron/worker-bridge.js:67` hardcodes
`DEFAULT_AUDIO_DEVICE = 'Mapeador de som da Microsoft - Input'` and line 381 forces it
into the child env as `SOTTO_AUDIO_DEVICE`, so `worker/config.json` is IGNORED whenever
the shell launches the worker. **Neither name is stable** — which device carries the
audio flips with the owner's routing. That is the case for runtime tap resolution, and
lane `SottoAdaptiveTap` owns it (dispatched 04:53Z via `agent()` inside `eval`; the
`task` tool is retired on this box and returns 0 lanes).

### (c) Fragment joining — DONE and proven (`app/electron/panel.js`)
The model emits 1-2 words per hop, so the raw stream read "checked / has / under / o".
`ingestFragment()` now accumulates and `flushPhrase()` emits ONE line when the phrase
closes: terminal punctuation, a silence gap > 1200 ms, or the 6000 ms / 90-char cap.
Nothing is invented — a line is the fragments concatenated in arrival order.

Oracle: `_main/join-harness.js` runs the REAL extracted source text of those functions
with a stubbed clock and a recording `addCaption` (5 arms, rc=0):
    PASS arm1 closes as one 12-word line
    PASS arm1 negative control: not 12 lines      <-- RED if the join were absent
    PASS arm2 gap closes the phrase / tail held then flushed
    PASS arm3 terminal punctuation closes immediately / tail flushed
    PASS arm4 empty and whitespace fragments ignored
    PASS arm5 length cap closes a run-on; no line exceeds the cap
    JOIN-HARNESS: PASS (5 arms)
First run of this harness was 3-FAILED and the faults were the TEST's expectations
(the 12x560 ms arm closes as ONE line at the cap; arm 3 inherited arm 2's un-flushed
tail, which is correct by design). The arms were corrected and the negative control
added; the code was not changed to make a wrong expectation pass.

END TO END, live shell, pid 23484, `--with-worker`, 45 s:
    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true
    raw BRIDGE_CAPTION fragments: 38  ->  CAPTION_APPLIED rendered lines: 9
    "how t how t n t s how ' se they make in they actually"
    "for i b co se s dly do"
    errors: [] (zero)

### What is still NOT proven
- The TEXT is still garbled ("le flo how t", "for i b co se s dly do"). That is the
  MODEL's accuracy on this audio (nemotron-3.5-asr-streaming-0.6b-int4), not the join:
  the join only groups what the model produced. The `int4` vs `FP16` question that
  worker/README.md leaves open is now the top accuracy candidate.
- The owner pressing Alt+C has still never been observed: registration is proven, the
  toggle is not (pressing keys on his desktop is not something Main may do).
- Runtime tap resolution is IN FLIGHT (lane SottoAdaptiveTap), not landed.


## 2026-10-06 04:56Z — SHELL DECISION (owner asked: "oq e melhor q electron e leve?" / "tem que ser bonito")

Measured, same day, same machine:
| term | size |
|---|---|
| Electron shell (bundled browser engine) | **213 947 904 B** (`app/node_modules/electron/dist/electron.exe`) |
| ASR worker RSS, idle contract | **2 141.7 MB** (`peak_rss_mb` in the worker's own final stats) |
| ratio | the model costs ~10x the shell |

Tauri is DEAD on this host, and it was measured, not assumed (commit `460125a`):
`cargo` sat 12+ min on "Updating crates.io index" with CPU frozen at 0.203125 across
three 15 s samples while `curl.exe` fetched the same URLs with HTTP 200 in 0.209 s; the
msvc nightly hangs identically. `ctranslate2` also hangs at import, which is why the ASR
route is ONNX Runtime.

DECISION: **keep Electron for now.** A WebView2 port saves ~214 MB of a ~2.4 GB process
(the engine is 9% of the footprint — the model is 89%), and it costs a shell rewrite plus
a new process model, right when Alt+C has only just been proven to register. The look the
owner asked for is already HTML/CSS in `panel.html`/`panel.css`, which renders identically
under WebView2 — so the swap stays CHEAP and can land later without touching the UI.
Revisit when the panel's own cost, not the model's, is the binding constraint.


## 2026-10-06 05:09Z — TAP ROTATION LANDED, AND A REGRESSION MY OWN JOIN INTRODUCED IS FIXED

### Runtime tap resolution (lane SottoAdaptiveTap — verified, not taken on trust)
Lane artifact `H:/sotto/worker/runs/adaptive-tap-acceptance.log`; files `worker/sotto_worker.py`,
`app/electron/worker-bridge.js`. Independent checks I ran:
- `node --check app/electron/worker-bridge.js` -> **rc=0**.
- Live shell: `BRIDGE_START ... device=auto` (the bridge no longer forces a device) and
  `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true`.
- Worker alone, 14 s, from `H:/sotto`: settled on attempt 1 of 6 with
  `"device": "CABLE Output (VB-Audio Virtual Cable)"`, `peak=0.500031`, `captions=2`,
  verdict `captions-emitted` — so the ordered candidate list picks a live tap and the
  rotation was not needed on this run.
- Rotation/exhaustion branch forced by the lane (`--tap-window 2 --tap-peak-floor 99`):
  `device-rotated` x5 then `device-exhausted reason=all-flat` with the tried list, peak
  0.485291, captions 0 — the bounded-window branch is exercised, not merely present.
LIMIT: I verified the branch in the LANE's log; I did not re-run the forced exhaustion
myself. Two logs, one command each, both on disk.

### Regression MY join introduced, measured and fixed
The first live run after the join showed `text="g"`, `"gen"`, `"s"` in the log with
**0 `CAPTION_APPLIED`**: the fragments sat in the join buffer and nothing rendered them,
because no further fragment and no status arrived to trigger a flush. A sparse stream was
invisible to the owner while the log looked healthy — the worst shape of this class.

Fix: `armPhraseTimer()` schedules a flush `PHRASE_GAP_MS` (1200 ms) after each fragment,
so a phrase closes on TIME, not only on the next event. `flushPhrase()` clears the timer.

Oracle `_main/join-harness.js`, **6 arms, rc=0**, all against the REAL extracted source:
    PASS arm1 closes as one 12-word line / negative control: not 12 lines
    PASS arm2 gap closes the phrase / tail held then flushed
    PASS arm3 terminal punctuation closes immediately / tail flushed
    PASS arm4 empty and whitespace fragments ignored
    PASS arm5 length cap closes a run-on; no line exceeds the cap
    PASS arm6 nothing rendered while open / a flush WAS scheduled / timer closed the tail
arm6 is the regression arm: it stubs `setTimeout`, captures the scheduled callback, fires
it with NO further input, and asserts the line appears. Removing the timer makes it RED.

LIVE, after the fix — pid 36144, `--with-worker`, 50 s:
    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true
    raw fragments: 2  ->  RENDERED lines: 1   ("com s")   errors: []
Before the fix the same sparse shape rendered 0 lines.

### Still not proven
- The owner pressing Alt+C. Registration is proven; the toggle is not — pressing keys on
  his desktop is not something Main may do.
- Text accuracy. The model (nemotron-3.5-asr-streaming-0.6b-int4) emits short, sometimes
  wrong words ("ressconti", "com s"). That is the model, not the plumbing. The int4 vs
  FP16 question that worker/README.md leaves open is the top accuracy candidate.


## 2026-10-06 05:25Z — THE PANEL IS FIXED (measured), AND TWO INSTRUMENT FAULTS OF MINE ARE RECORDED

### The renderer fix, verified by me and not taken from the lane's word
Lane `SottoPanelSurface` owns panel.html/panel.css. Its instrument `app/electron/dom-probe.js` (NEW,
605 lines) loads panel.html in the REAL window options WITH the real preload.js and asserts three
states — idle, live (2 captions over real IPC), cleared (the Clear button actually clicked) — with the
contract enforced BOTH ways: required-visible elements must render, out-of-contract elements must NOT.
It also computes WCAG contrast against the paint composited behind each text element.

    BEFORE (lane): rc=1  ok=False failures=32
    AFTER  (me):   rc=0  ok=True  failures=0        <- I ran it myself; not the lane's claim

Defects it named with numbers, all now fixed:
- `.wordmark__name` color rgba(0,0,0,0), contrast 1.09 (background-clip:text only) — the Sotto title
  was invisible unless the clip painted.
- `#caption-list` hidden=FALSE in the IDLE state — the empty list rendered when it should not.
- headerAlignmentDeltaY = 3.34 (tolerance 2).
- `.status__hint` contrast 4.04 at 10.5px — under WCAG AA 4.5.

### Pixel proof, before vs after, against the owner's own screenshot
10 bands of 38px, % of pixels differing from the slab colour, left to right
(`_main/panel-transparent.png` is now the AFTER render — see the collision note):

    OWNER screenshot (broken)   56.7 37.3 33.0 28.4 25.7 25.4 25.5 26.5 29.1 34.8
    ELECTRON before the fix     53.8 18.3 15.5 12.6 13.1 13.0 11.9 11.2 18.5 55.9
    ELECTRON after the fix      25.3 14.0  9.7  7.9  7.9  7.8  8.0  9.4 19.2 22.3

The heavy EDGE artifacts are gone: left 53.8 -> 25.3, right 55.9 -> 22.3. The owner's profile sits
closest to the BROKEN arm, which is what he was looking at.

### TWO INSTRUMENT FAULTS OF MINE, recorded rather than buried
1. **A 48x44 ASCII map of a 380x900 capture is too coarse to read a layout from.** I called a
   left-column collapse in the owner's screenshot; the band profile refutes it — content spans every
   band in all three images. Orientation only, never a verdict. (Row `instrument-granularity-20261006`.)
2. **`--dump-dom` names its capture by ARM only (`panel-<transparent|opaque>.png`), so a second run
   SILENTLY OVERWRITES the first.** I lost the before-fix PNG to the after-fix run and only noticed
   because the band numbers changed under the same filename. The fix is a `--tag` in the filename;
   until then, copy the file between runs. The before-fix numbers survive in this table.

### Still open, stated plainly
- Owner pressing Alt+C: registration is proven, the toggle is not.
- Text accuracy: lane `SottoAccuracyInt4` (in flight) owns the int4-vs-best-precision comparison.
- WebView swap: lane `SottoWebViewShell` (in flight) owns it. NOT done.
