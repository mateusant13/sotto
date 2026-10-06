# Sotto — repo context for every agent and subagent

Real-time transcription of ANY audio on this PC, shown as captions on a global **Alt+C** overlay.
Owner's acceptance, verbatim: *"e eu quero que o alt c mostre as transcricoes em tempo real,
de qualquer audio do meu pc. e legendas."*

## MUST READ before touching `worker/`

**`docs/model-specs/README.md`** — the model's OWN documentation, consolidated with the
originals verbatim in `docs/model-specs/original/`. It carries the normative parameters
(`blank_id: 13087`, `max_symbols_per_step: 10`, `chunk_samples: 8960`), the decode contract,
the language-ID table and the shipped VAD settings. **Do not invent a decode convention without
reading it first** — that mistake was already made once in this repo.

Reference upstream code the model's own README points at: `DimQ1/nemotron-speech-csharp`.

## Known deviations from the model spec (read the file, then fix)

| what the model says | what the code does | where |
|---|---|---|
| ~~the model ships lang ids (`pt-BR: 12`, `pt: 13`, `auto: 101`)~~ | **RESOLVED 2026-10-06**: `model.lang_id` is `"auto"` (= the model's own autoSlot 101). It was `"os"` (host USER locale) earlier the same day, and **both silent defaults destroyed a language**: on this pt-BR host `"os"` resolved to `pt-BR` (12) and decoding the bundled ENGLISH sample with prompt 12 collapsed 94 tokens to 10, while the old literal `0` (en-US) did the mirror damage to Portuguese (5 tokens vs 18 on `_main/pt-br-sample.wav`). `"auto"` got 89/94 tokens English and 18/18 Portuguese — the only one of the three good on BOTH. `"os"` remains an ACCEPTED value (a user may still request host-locale); it is just no longer the shipped default. Precedence `--lang-id` > `SOTTO_LANG_ID` > config; an undeclared id is **refused loudly (exit 2)**, never clamped. The old literal `0` was ALSO dead code: `--lang-id` defaulted to `0`, so `args.lang_id is not None` was always true and the config key was unreachable on every run | `worker/config.json` + `worker/lang_prompt.py` (oracle: `_main/lang-id-oracle.py`; default-choice receipt: `_main/lang-id-default-arms.py`) |
| ~~Silero VAD shipped tuned (thr 0.3 / silence 3360 ms / prefix 560 ms)~~ | **RESOLVED 2026-10-06**: `"use_vad": true`. The flag is LIVE, not inert — `get_option('use_vad')` reads back `true`, and a digital-silence chunk makes `process()` return **`None`** (10 of 12 silence chunks gated) where VAD-off returns a `(1,65,128)` block every time. `run_chunk` now handles that `None`; unhandled it exited **1** on the first pause longer than 3.36 s. On the bundled sample the transcript is **byte-identical** with the flag on and off (both before and after a sibling lane moved `lang_id`) — that clip has no 3.36 s stretch of silence. On audio with a real pause it gates 6 chunks and changes the decode | `worker/config.json`, `worker/sotto_worker.py` (oracle: `_main/vad-option-probe.py`) |
| ~~config selected int4 while the worker README described int8~~ | **RESOLVED 2026-10-06**: config now selects `...-int8` (`left_context: 70`); measured cost vs int4 = +268 MB RSS | `worker/config.json` (oracle: `_main/model-spec-oracle.py`) |
| ~~a run that opened a device and heard nothing still exited 0~~ | **RESOLVED 2026-10-06**: a tap that opens and delivers a full window below the peak floor is now `state="silent-device"`, verdict `silent-device`, **exit 3** | `worker/sotto_worker.py` (oracle: `_main/device-silence-oracle.py`) |
| ~~the top-level `done` verdict could disagree with the exit code inside ONE run~~ | **RESOLVED 2026-10-06**: the verdict branch tested the device-SELECTION outcome (`outcome in ("all-flat","open-failed")`) FIRST, so a run that BOTH exhausted the ladder AND measured a silent device reported `done` verdict `all-candidate-taps-flat` while emitting `state="silent-device"` and returning **exit 3** — the word and the code disagreed in the same run (measured: `worker/runs/exit3-armB-worker.jsonl`). The order is now `ran_but_silent` FIRST — the MEASURED, device-attributable fact and the exact predicate the exit code is built from — so `done.verdict == "silent-device"` iff `exit == 3`. `all-candidate-taps-flat` survives for the no-data case (candidates flat without reaching `TAP_SILENT_BLOCKS`). No vocabulary was renamed | `worker/sotto_worker.py` (oracle: `_main/verdict-order-oracle.py`) |

## The routing law on THIS box (measured 2026-10-06, do not re-litigate)

**The worker's loopback path is correct. Whether Sotto hears anything depends
entirely on what the owner has routed into a virtual cable, and a name in
`config.json` cannot make that happen.**

- `CABLE Output (VB-Audio Virtual Cable)` exists at **three** indices under three
  host APIs — MME #2, DirectSound #15, WASAPI #32 — and they are **not
  interchangeable**. A name alone does not identify what was opened; every
  status now carries `api` for that reason.
- The loopback is **asymmetric across APIs**: rendering into the **MME**
  `CABLE Input` and capturing the **DirectSound** `CABLE Output` delivered the
  injected tone at peak **0.4999** (`_main/inject-all-probe.py`). DirectSound
  render → DirectSound capture does **not** loop back on this host (peak
  0.00003). Do not "fix" a silent run by matching a longer device name.
- With nothing playing, **every** loopback reads digital silence: a passive
  22 s listen across all of them peaked at 0.000122
  (`_main/listen-probe.py`, verdict `NOTHING-ROUTED`). The system default output
  is `VoiceMeeter Input`, so app audio reaches a cable only if VoiceMeeter is
  configured to output into it.
- **So a live run that reads silence is usually CORRECT BEHAVIOUR**, not a
  regression. The owner's fix is a routing change in VoiceMeeter / Windows
>  Sound settings; the worker's job is to say so loudly instead of exiting 0.

## Hard rules for any lane here

- **Never leave a visible console window on the owner's screen.** He has been shown a stray
  `python` console twice by lanes and complained. Launch python with `pythonw.exe` or
  `creationflags 0x08000000|0x00000008`. A window census runs every 60 s and logs
  `ALERTA-JANELA` with the pid — it will name you. **The same rule covers the PANEL
  itself:** it must be off screen unless the owner pressed Alt+C or passed `--show`,
  and `hidden=True` alone does not buy that (the measured fact below). A census that
  samples every 60 s cannot prove the absence of a short-lived window — sample at
  your own cadence when the claim is "no window appeared".
- **A kill filter names the ARTIFACT, never a generic word.** Match `sotto_worker\.py`,
  `sotto_webview\.py` or the electron/webview exe path. Filtering on the bare word `sotto`
  once killed two unrelated `closure-admission.sh` processes.
- **Never grep for `AGENTS.md`/context files** — they are auto-loaded.
- **Lanes edit their own files only.** The ownership map is in the dispatch brief.
- **Native `H:\` paths only** — `./node_modules/.bin/electron` does not execute on this box
  (rc=127, measured). Use `H:/sotto/app/node_modules/electron/dist/electron.exe`.

## Layout

| path | what |
|---|---|
| `worker/sotto_worker.py` | capture → chunk → encode → RNNT greedy decode → JSONL on stdout |
| `worker/config.json` | model dir, lang_id, use_vad, providers, audio.block_ms, output.min_chars (all READ; inert keys deleted 2026-10-06 — `_main/delivery-rate-oracle.py`, `docs/audit/config-inert-fixed.md`) |
| `worker/models/nemotron-3.5-asr-streaming-0.6b-{int4,int8,fp16}/` | the three exports |
| `app/webview/run.cmd` | **THE APP.** Double-click it, or run it: starts hidden, waits for Alt+C |
| `app/webview/sotto_webview.py` | the shell the app IS — WebView2 + pywebview |
| `app/webview/hot_reload.py` | panel-asset/worker watcher + debounce; reloads the panel in place |
| `app/webview/README.md` | how to run it, what it hosts, what is legacy |
| `app/webview/stage.html` | empty page opened first, so the bridge exists before the panel parses |
| `app/electron/` | **LEGACY** — the earlier Electron shell. Kept for its panel files and as the reference arm. NOT a fallback. |
| `app/electron/panel.{html,css,js}` | the panel BOTH shells host, unmodified — still the live ones |
| `app/electron/{main,preload,worker-bridge,hot-reload}.js` | the legacy Electron shell's own files |
| `docs/model-specs/` | the model's own docs, verbatim + normative index |
| `_main/` | probes and their logs (`precision-ram-probe-*.log`, `*dump*.log`) |

## Measured facts that must not be re-litigated

- Model weights on disk: **int4 756 MB / int8 1020 MB / fp16 1230 MB**; RSS after load + one
  inference: **int4 924 MB / int8 1192 MB**. The `.onnx.data` sidecars ARE the weights; a
  listing that shows only the `.onnx` headers understates them by ~150×.
- `CUDAExecutionProvider` is **requested but not loadable here** — ORT silently returns
  `['CPUExecutionProvider']`. The box runs on CPU.
- WebView2 shell works and its layout is byte-identical to Electron's (14 DOM fields compared,
  0 mismatches), at **+33% memory** (416 MB vs 312 MB tree). The owner ruled: **no fallback,
  WebView2 is the app.**
- **The app is `app/webview/run.cmd`.** Electron is the EARLIER shell, not a
  fallback; do not offer it as one. The +33% memory verdict was measured and
  the owner ruled on it — do not re-open that trade.
- **Kill filters name the ARTIFACT.** `sotto_webview\.py`,
  `sotto_worker\.py`, the electron exe path. A PowerShell filter that reads a
  process list must run from a `.ps1` FILE with
  `Get-CimInstance Win32_Process`: measured, the inline `-Command` form
  returns EMPTY stdout on this box while the file form returns every row, so
  an inline version silently reports "nothing is running".
- **`run.cmd --with-worker` used to HANG the shell on its own lock — measured
  2026-10-06, fixed, do not reintroduce it.** `WorkerBridge.start()` holds a
  NON-reentrant `threading.Lock` and calls `_spawn()`, whose last statement was
  `_arm_silence()` — a lock-taking call. Measured in `_main/exit3-armB1.log`
  over 8 worker cycles: `BRIDGE_EXIT … statuses=0` every cycle, `WORKER_AUTOSTART`
  never logged, `--dump-dom` never dumped, `--exit-after` never armed. Every
  status AND every caption travels that same stdout pump, so **the app could not
  print a single caption**. `_arm_silence` now takes no lock; anything added to
  `_spawn` must not take `self._lock`. Oracle: `_main/panel-exit3-oracle.py`.
- **The panel paints the worker's OWN failure vocabulary as an error, with the
  worker's cause.** `error`, `device-exhausted` and `silent-device` are errors,
  and so is a `done` whose verdict is not `captions-emitted`; `device-rotated` is
  NOT. That is the decision `app/electron/worker-bridge.js`'s STATE_MAP already
  carried (worker-bridge.js:133) and the WebView2 shell had never ported, so a
  worker that died of a silent device was painted with the same NEUTRAL styling
  as warm-up. The panel text must name the device, and the death must survive the
  automatic restart until a CAPTION proves recovery (the shell re-emits
  `model-loading` after every exit 3). **BOTH halves are gated in
  `_main/panel-exit3-oracle.py`:** ARM 0/D prove the HOLD, and **ARM E** proves
  the second half the earlier oracles never fed — a REAL caption after the exit-3
  death returns the panel to live (`Receiving captions`, error=false, placeholder
  gone). Gate, both colours in ONE command: `py -3 _main/panel-exit3-oracle.py
  --unit --neg-arm` → `VERDICT PASS`, with the CLEAR-removed COPY of today's shell
  going RED on the unlifted hold (`ARM E/E4`, `ARM E/E5`, `ARM E/E6`) and ARM D
  staying green. `py -3 _main/panel-exit3-oracle.py --arm-e-real` pastes both
  painted states from the REAL WebView2 DOM (a fake worker reproduces the death,
  then a caption).
- **A `done` with NO verdict is an ERROR, not a healthy finish — measured and
  fixed 2026-10-06.** `worker_status_kind` read `if verdict and verdict not in
  HEALTHY_DONE_VERDICTS`, so an ABSENT (or empty) verdict skipped the test,
  missed `FAILURE_WORDS_RE` — which contains no `done` — and a bare `done` was
  painted with the same neutral styling as a healthy finish. An unknown word was
  already an error; the missing word was not. The test is now the POSITIVE form,
  `if verdict not in HEALTHY_DONE_VERDICTS`, which is what the rule above always
  said, and the no-verdict footer has its own sentence instead of the f-string
  of a missing key (`app/webview/sotto_webview.py:144-155`, `:168-179`). Gate,
  both colours in ONE command: `py -3 _main/panel-exit3-oracle.py --unit
  --neg-arm` → `VERDICT PASS` with the reverted COPY going RED on
  `done-no-verdict` alone.
- **A MEASUREMENT run of the shell must pass `--no-hotkey` and must be spawned
  with `CREATE_NO_WINDOW` (or `pythonw.exe`).** Alt+C is the app's only control:
  a probe that registers it answers the owner's keypress with its own panel
  (measured: two `PANEL_SHOWN reason=hotkey` lines in one probe run). And
  launching `python.exe` straight from a tool shell put a visible window on the
  owner's screen — the census named it (`ALERTA-JANELA pid=24836 … nome=python`,
  matching line 1 of the probe's own log).
- **THE PANEL CAME UP ON THE OWNER'S SCREEN AT EVERY START — measured
  2026-10-06, fixed in `_on_navigation_start`, do not re-litigate.**
  `create_window(hidden=True)` is NOT enough, and the shell's own `hidden=True`
  dance does leave it hidden: pywebview SHOWS the form again on EVERY
  navigation start when the window is transparent
  (`platforms/edgechromium.py:345-349`, `if transparent: self.form.Show()`),
  transparency is the default here (`--opaque` turns it off) and the shell
  navigates twice (stage.html, then the panel). So the window appeared a few
  hundred ms AFTER `PANEL_VISIBILITY_AT_STARTUP visible=false` — measured by
  running the real entry point, on the owner's desk, whole-run visible:
  `_main/panel-startup-visibility.log`, arm P of the BEFORE run
  (`ALERTA-JANELA … pid=23512 nome=pythonw`, class
  `WindowsForms10.Window.8.app.0.aec740_r16_ad1`, 26 of 38 samples). The cure
  is `_on_navigation_start` → `_reassert_hidden` on
  `NavigationStarting`, run BOTH synchronously and posted, and skipped when
  `--show` or `self.visible`. Gate, both colours in ONE run:
  `pythonw.exe _main/panel-startup-visibility-oracle.py` → `VERDICT PASS`
  (arm P 0 of 41 samples at a 200 ms cadence, arm B — cure removed — on screen,
  arm S — `--show` — still visible).

  **BUT "arm P 0 of 41" IS REFUTED by a 25 ms census, and the pair is NOT the
  cure.** `_main/panel-startup-flash-census.py` samples the shell's OWN pid tree
  every 25 ms over N≥20 launches. Measured 2026-10-06: the panel's WinForms form
  is `WS_VISIBLE` and NOT alpha-occluded in **~18 of 20 launches, longest
  ~63 ms**, landing at the first `PANEL_VISIBILITY_AT_STARTUP` and around
  `STAGING_LOADED` (the stage.html→panel.html navigation). The 200 ms oracle
  simply cannot see a ≤63 ms event; a 25 ms grid catches it in almost every
  launch. Re-subscribing the re-assert to the SAME event pywebview subscribes
  (the control's `NavigationStarting`) did NOT change the count (18/20 vs the
  un-fixed 19/20) — the Show→Hide gap survives same-dispatch subscription.
  **Two attempts to close it were measured to BREAK LOADING and are forbidden:**
  `self.window.transparent = False` after create, and creating the window at
  `OFFSCREEN = -32000` — in both, WebView2 never completes the panel
  navigation, `_on_loaded` never fires and the shell HANGS (reproduced with no
  `--exit-after`). The only measured closure is `--opaque` (transparent=False
  from CREATION): its flash drops to 3/20 and every catch is alpha=0 (the
  invisible `Opacity=0` creation dance) — **cost: the panel loses its
  transparent background / rounded-corner look.**
- **The house window census samples ONCE PER 60 s, so a window that lives less
  than that can pass it unseen — a missing `ALERTA-JANELA` is NOT proof that no
  window appeared.** Measured 2026-10-06: shell pid 23512 was WS_VISIBLE for the
  whole 6 s of the BEFORE run and the shared log never named it, while the
  oracle's own 200 ms census named it in 26 of 38 samples. Any probe that needs
  to prove a window did NOT appear must sample at its own cadence; the 60 s
  governor can only prove presence.
- **`run.cmd` USED TO ANSWER 0 FOR ANYTHING, INCLUDING A FLAG IT REJECTS —
  measured 2026-10-06, fixed, do not reintroduce it.** `run.cmd --bogus-flag`
  returned rc=0 with no output, no log bytes and no process: argparse exits 2 on
  `pythonw.exe` (whose stdout is None) and `start` reports only its OWN success,
  so the interpreter's status never reached the caller. `start` is KEPT (a
  wrapper that waited for the app would hold the caller's console open for the
  session), so the status is taken in a PRE-FLIGHT that starts nothing:
  `"%PYW%" "%SHELL%" --check-args %*` — the shell's OWN parser, no second flag
  table in batch to drift. Non-zero → the wrapper echoes the refusal, appends
  `sotto: ARGS_REJECTED rc=<n> by=run.cmd-preflight` to `_main/webview-run.log`
  (before the fix that file gained NO bytes at all) and `exit /b <child rc>`;
  nothing is spawned. `--check-args` is `help=argparse.SUPPRESS`, so `run.cmd
  --help` output is byte-identical before/after (measured: 2272 B, rc 0, BOTH
  sides). The two branches SottoRunCmdEntry measured working stay working:
  pythonw for a normal hidden launch (arm rc 0, and the wrapper returns in
  ~250 ms while the app lives 8 s — it still detaches), python.exe for the
  `--help`/`--dump-dom`/`--selftest`/`--memory` flags. NOT covered by the
  pre-flight: a list argparse accepts that fails later (missing pywebview, bad
  panel path) still reports 0 — covering it needs a readiness handshake on the
  shell's own first line, `sotto: shell=webview2 pywebview=<v> python=<v>
  pid=<N>`, which would hold the caller's console open for the app's start.
  Gate, both colours in ONE command: `py -3 _main/run-cmd-exit-oracle.py` →
  `ARM-VERDICT PASS` with rc 2/0/0/0 for bogus/help/start-logged/start-default,
  and `py -3 _main/run-cmd-exit-oracle.py --neg-arm` (the PRE-FIX wrapper
  restored in a COPY from `_main/run-cmd-prefix-20261006.cmd`, sha256
  `b9c08fec…`) → `ARM-VERDICT PASS   arm1(bogus) RED-as-expected=True
  arms2-4-still-green=True failed=['bogus']` with rc 0 on the copy: only the
  bogus arm moved, which is what makes it a control. TWO verdicts are printed
  and the final VERDICT is their conjunction, because they are different
  claims: `ARM-VERDICT` is this wrapper's exit contract, `CENSUS-VERDICT` is
  "no visible window in this run's pids" (see the next bullet — the app itself
  can flash its panel, and a census RED must never be read as "the wrapper
  failed"). The census samples its OWN pid tree at 100 ms and seeds the tracked
  set from the pid in the app's log line, because a plain tree walk CANNOT see a
  `start`-detached app once its parent cmd.exe exits — `_main/_armE-window-
  census.py` printed `visible_samples_over_tree=0 distinct=0` around the very
  pass in which the oracle's own census caught a flash.
- **THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s, AND `run.cmd` IS NOT
  THE CAUSE — measured 2026-10-06 by lane SottoRunCmdExitContract while gating
  the wrapper's exit contract. Owned by the lane already sampling it
  (`_main/panel-startup-flash-census.py`, `_main/_flash-*sotto_webview.py`); the
  shell under measurement was `sha256 a3b61c250757b26c…`, mtime unchanged for the
  whole run, cure PRESENT (`_on_navigation_start` ×2, `_reassert_hidden` ×4) —
  so this is not a mutant and not a stale file.** Three instruments, one subject:
  • `_main/_runcmd-panel-flash-probe.py` (50 ms cadence, tracks the app pid read
    from the app's OWN log line, 20 starts): the `Sotto` form is VISIBLE for 1–2
    samples at **+0.76 s / +0.98 s after the app's first line** in 2 of 5 starts,
    and for **88 and 130 samples (~4.4 s / ~6.5 s) on the 8th consecutive start**
    — measured in BOTH arms, `--direct` included (pythonw on `sotto_webview.py`
    with NO run.cmd in the path), so the launcher is exonerated: it is the APP's
    startup, and the duration is not a fixed 50 ms race.
  • `_main/run-cmd-exit-oracle.py`'s own census (100 ms): 0 of 213 and 0 of 249
    samples visible at 04:5x, then **141 of 262** at 08:05, naming
    `CENSUS ALERTA-JANELA <pid>:<hwnd> title='Sotto'
    class='WindowsForms10.Window.8.app.0.aec740_r16_ad1'` for ~7 s of an 8 s run.
  • the 60 s house census caught it on THIS probe's pids:
    `ALERTA-JANELA ts=2026-10-06T08:02:21Z pid=34752 nome=pythonw` (pid proved
    mine by the `pid=` lines in `_main/_runcmd-panel-flash.log`) and
    `ts=08:05:21Z pid=9784 nome=pythonw` — 6 pythonw alarms today.
  **TWO INSTRUMENT TRAPS this measurement exposed, both worth more than the
  numbers:** (a) a `start`-DETACHED app is INVISIBLE to a census that re-walks the
  live process table — `_main/_armE-window-census.py` printed
  `visible_samples_over_tree=0 distinct=0` around the very pass in which the
  app's own pid was visible for 141 samples, because its recorded parent cmd.exe
  no longer exists; seed the tracked set from the app's log line. (b) "0 visible
  in N samples" is not absence: the same oracle printed 0 of 213 and 141 of 262 in
  two passes of the SAME subject.
