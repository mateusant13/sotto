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
| `app/webview/run.cmd` | **THE APP.** Double-click it, or run it: starts hidden, **starts the WORKER**, waits for Alt+C. `--no-worker` = shell only, `--show` = panel up now. Since 2026-10-07 the worker starts BY DEFAULT — see the F1 bullet under *Measured facts* |
| `app/webview/sotto_webview.py` | the shell the app IS — WebView2 + pywebview |
| `app/webview/hot_reload.py` | panel-asset/worker watcher + debounce; reloads the panel in place |
| `app/webview/README.md` | how to run it, what it hosts, what is legacy |
| `app/webview/stage.html` | empty page opened first, so the bridge exists before the panel parses |
| `app/panel/` | **THE PANEL.** `panel.{html,css,js}` and the modules the document loads (`caption-formulation.js`, `history-source.js`, `history-store.js`, `surface.js`, `theme-switcher.js`, `themes/`) — the live ones, hosted unmodified by the WebView2 shell. This directory was named `app/electron/` until 2026-10-07: the name was a shell the app no longer is. |
| `app/_legacy-electron/` | **LEGACY — DEAD.** The earlier Electron shell (`main.js`, `preload.js`, `worker-bridge.js`, `hot-reload.js`) with its own probes, docs, toolchain and logs, moved here whole on 2026-10-07 (nothing deleted). NOT a fallback, and no longer runnable as an arm: the panel it hosted lives in `app/panel/`. |
| `docs/model-specs/` | the model's own docs, verbatim + normative index |
| `_main/` | probes and their logs (`precision-ram-probe-*.log`, `*dump*.log`) |

## Measured facts that must not be re-litigated

- **The transcript carries ONLY a line the WORKER closed (`route=final`)** — measured, decided by the
  owner, and fixed 2026-10-06 (`docs/audit/historico-vs-redux.md`). A `provisional-draft` IS the
  live caption: the box may show it, the history may NOT. It reached the file through
  `panel.js:553 engine.flush('status-change')`, which fires on EVERY worker status while this worker
  restarts constantly — MEASURED in the owner's own `history/2026-10-06/10.md`: 10 of the 19 lines
  written after the 2026-10-06 cure are `provisional-draft reason=status-change`, word for word the
  live box. Three guards, one invariant: `panel.js recordHistory` (the choke point that chooses the
  text), `history-store.js append`, `sotto_webview.py history_append`. Both colours in ONE command:
  `node _main/historico-vs-redux-probe.js` → `GREEN` (130 lines), and the SAME run with `--gate-off`
  (the guard line deleted from the store) → `RED` (1221 lines, 1091 of them provisional). **The word
  `redux` names the HISTORY STORE** (`panel.html:109` "History · Redux"), NOT a second-pass ASR
  route. **CORRECTED AGAIN 2026-10-07 — the M1-M3 SECOND PASS IS PRESENT AND WIRED ON THE LIVE PATH.**
  This bullet said the opposite for most of 2026-10-07 ("the second pass is ABSENT today"), on the
  strength of a `grep -n 'def rerun|reset_stream_state|_last_symbol' worker/sotto_worker.py` that
  returned ZERO matches. The grep is now non-empty and the negative claim is FALSE. Measured against the
  live file (**242 082 B, sha256 `64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61`,
  re-verified 2026-10-08 — the numbers below were `:2654`/`:2748`/`:2771` in the 173 388 B revision
  cited before**), `grep -rn` returns:
  `def rerun` = `worker/sotto_worker.py:3637`, `reset_stream_state` = `:623`, `_last_symbol` =
  `:527` (`__init__`) / `:651` (the reset) / `:896` (the chunk seed) / `:2707`+`:2743` (the save/restore
  pair), and `def finalise` = `:3732`, `def drain` = `:3755` (`drain_captions` is separate, at
  `:2645`), called from FIVE `drain()` sites in `asr_thread`. **That revision moved by one line and one
  byte while this bullet was being written** (from 173389 B / `def rerun` `:2655` to 173388 B / `:2654`),
  which is the point of rule 2 below: treat every line number here as a HINT and re-run the grep. So the
  live path is `drain` → `finalise` → `rerun`, and the pass' text is what `final:true` ships. **How the
  earlier revision got it wrong is the transferable part:** it cited `:2281` for `rerun()` and that line
  really was, in the 150592 B revision, device-ladder code — the SAME expression the audit cites, which in
  the current revision is `:3111` (`proved_alive["peak"] = device_peak["value"]`). A correct line citation from a stale revision, plus a
  grep run once and never re-run, produced a confident false negative in the one file every agent loads.
  `reset_stream_state()` is also only HALF a stream start (`:637-646`): the front end (`self.sp`, the
  cache-aware mel window + VAD) has no ORT-GenAI reset and is replaced by `fresh_processor()` (`:592`),
  installed for a second pass and by `reset_frontend()` (`:653`) on a new device — never call one and
  assume the other. ~~The batch model (Parakeet Redux) is still not on disk and has no call site; that
  half of the old bullet was true.~~ **CORRIGIDO 2026-10-07: essa frase estava FALSA e contradizia a
  secção "A LEI DA STACK" deste mesmo ficheiro** — os pesos do Redux **estão** em disco
  (`worker/models/parakeet-redux-ternary/`, sha256 `78ec2573…`), o runner **existe com paridade
  provada** (`worker/redux_batch.py`) e o export ONNX int4 foi apagado de propósito. Uma lane apanhou a
  contradição; resolvida aqui, não reescrita em dois sítios.
- **THE HISTORY FEED IS EMPTY BY DESIGN, AND THE ORACLE THAT "PROVES THE CANONICAL PATH IS OPEN"
  FEEDS ITSELF THE STAMP — measured 2026-10-07, do not read the green as evidence.** The canonical
  transcript accepts a line ONLY if `meta.producer` is literally `redux`:
  `app/panel/history-source.js:51` (`const CANONICAL_PRODUCER = 'redux'`) and `:61-63`
  (`isCanonicalLine(meta) { return producerOf(meta) === CANONICAL_PRODUCER; }`, fail-closed — an
  absent or unknown producer is refused, never assumed). **Nothing in the repo writes that field:**
  `grep -rn producer worker/` → **ZERO matches**, and the live engine's meta carries
  `route`/`start`/`routeSource` only. Consequence, both measurable today: the "History · Redux" half
  of the panel is decorative, and the owner's archive has taken no new line since
  `history/2026-10-06/19.md` (mtime **2026-10-06 19:58:36**, the newest file in `history/`).
  `node _main/live-vs-history-source-oracle.js` is **GREEN (13/13)** and is NOT counter-evidence:
  its "canonical path is OPEN" arm STAMPS `source.CANONICAL_PRODUCER` itself
  (`_main/live-vs-history-source-oracle.js:219`), while the "AS SHIPPED" arm builds the meta by hand
  without the field (`:111-117`) — a gate that supplies the thing it then finds cannot say no. The
  batch engine that would stamp it (`moondream/parakeet-redux`) is not on disk and has no call site.
  Where the fix belongs: a new arm that asks "does ANY producer in this repo stamp `producer`?" (grep
  + the engine's REAL meta) — RED today.
- **OPEN RISK — `CANONICAL_PRODUCER = 'redux'` is a LITERAL claim, and a
  different batch engine would make the guard a lie.**
  `app/panel/history-source.js:51` (`const CANONICAL_PRODUCER = 'redux'`; the
  same string is stamped at `panel.js:364` `source: 'redux'`) is the ONLY
  producer the canonical transcript accepts. The guard names the *model*, not
  "the canonical pass": if HISTORY is ever fed a Parakeet that is not literally
  `moondream/parakeet-redux` — e.g. upstream `parakeet-tdt-0.6b-v3` ("option B"
  in `_main/research-parakeet-redux.md`) — every line it writes claims `redux`
  and the guard becomes a lie. Two exits, decided by the owner: **(i) keep the
  literal model** — the tag stays truthful only while the finisher IS Redux; or
  **(ii) rename the tag** to what it actually is, e.g. `canonical-tdt`, and
  change `history-source.js` + `panel.js:364` + the oracle in the SAME edit
  (a half-rename leaves the oracle asserting the old literal). This lane did NOT
  touch `history-source.js` (docs-only).
- **A panel hot reload USED to land on `chrome-error://chromewebdata/`; the mechanism is now the STAGING
  BOUNCE, and the new mechanism is NOT machine-verified (this session has no WebView2).**
  **What it was** — measured and reproduced twice 2026-10-06 (audit F5): after `touch
  app/panel/panel.js` the shell logged `HOT_RELOAD_PANEL_DONE reload=N`, then
  `_main/panel-state.json` read `panel.url = chrome-error://chromewebdata/` with
  `panel.live.count = -1` — `PANEL_STATE_PROBE`'s sentinel for `#caption-list` ABSENT
  (`sotto_webview.py:1145`), i.e. Chromium's OWN error page, not `panel.html`. The cause:
  `reload_panel_assets` navigated to `file_url(PANEL_HTML) + f'?sotto_hr={reload_count}'`, a QUERY
  STRING on a `file://` URL, and `?` is not a legal Windows filename character, so the navigation
  failed. Consequence then: after ANY panel-file edit the panel stopped painting until the shell was
  restarted, and the owner's transcript stopped growing with it.
  **What the code does NOW** (2026-10-07 shell revision, 4326 lines): `reload_panel_assets`
  (`:2725-2785`) sets `self.staged = False` (`:2772` — the PUBLIC attribute `_on_loaded` reads) and
  re-runs `self.window.load_url(file_url(STAGE_HTML))` (`:2774-2775`), i.e. the SAME
  `stage.html` → `panel.html` navigation pair that brings the panel up at startup, now known to land on
  the real document. What arrives is a fresh PARSE of the fresh bytes — which is what a `file://`
  stylesheet gets no guarantee of — rather than a URL change; **any** cache-busting that alters the URL
  of a `file://` document is out for the same reason the old one failed. The only `?sotto_hr=` left in
  the file is inside the docstring that quotes the dead code as the reason it was wrong (`:2742`).
  **Evidence status, stated plainly:** this is "the mechanism the code implements", verified by reading
  it — NOT by running it. The machine check is one hot reload followed by `panel.url = file://…/panel.html`
  and a non-negative `panel.live.count` in `_main/panel-state.json`; until someone runs it, do not write
  that the reload works.
- Model weights on disk: **int4 756 MB / int8 1020 MB / fp16 1230 MB**; RSS after load + one
  inference: **int4 924 MB / int8 1192 MB**. The `.onnx.data` sidecars ARE the weights; a
  listing that shows only the `.onnx` headers understates them by ~150×.
- ~~`CUDAExecutionProvider` is **requested but not loadable here** — ORT silently returns
  `['CPUExecutionProvider']`. The box runs on CPU.~~ **CORRECTED 2026-10-08 — THAT SENTENCE IS
  FALSE. MEASURED: `ort.get_available_providers()` → `['TensorrtExecutionProvider',
  'CUDAExecutionProvider', 'CPUExecutionProvider']`, and `get_device()` → `GPU`.** What is true is
  narrower and more useful: **a CUDA-requesting session in a CLEAN shell falls back to CPU for
  exactly ONE missing DLL** — `cublasLt64_13.dll`, WinError 126 — and **one directory fixes it**:
  `site-packages\nvidia\cu13\bin\x86_64` on the DLL search path. `torch\lib` is CUDA 12 and does
  NOT serve it. **The worker already does this** — `worker/sotto_worker.py:277`
  (`_add_cuda_dll_dirs()`), called from `:3251` before the model load (both re-verified against the
  242 082 B / sha256 `64E7EC6F…` revision) — so the live run IS GPU-backed. The old line was a
  guess from a clean-shell provider probe; the live worker proved it wrong.
- **THE LIVE ENGINE IS HYBRID, NOT "ORT-GenAI" — do not size a change by that name.**
  `og.Model` + `StreamingProcessor` cover only the cache-aware mel window and the Silero VAD;
  the encoder, decoder and joint are plain `onnxruntime.InferenceSession`, and the RNNT decode loop
  is plain Python. So `onnxruntime-genai-cuda` buys **POUCO** here — and the INSTALLED
  `onnxruntime-genai` 0.17.1 is **CPU-only** anyway (`og.is_cuda_available()` → `False`).
- **THE SHIPPING RECIPE HAS A SILENT FAILURE MODE — MEASURED 2026-10-08.**
  `pip install "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai` installs plain `onnxruntime` LAST (it is
  `onnxruntime-genai`'s hard dep) and the plain wheel overwrites 21 shared `onnxruntime/capi/` files and
  drops `providers_cuda` (`onnxruntime-1.30.0.dist-info` RECORD: `capi_entries=21`,
  `providers_cuda_entries=0`; `onnxruntime_gpu-1.30.0.dist-info`: `23` / `1`). Result:
  `available: ['AzureExecutionProvider','CPUExecutionProvider']` and a CUDA-requesting session returns
  `['CPUExecutionProvider']` with **`error: null`** — CPU-only ORT, silently. The fix is one line after:
  `pip install --force-reinstall --no-deps onnxruntime-gpu==1.30.0` → back to
  `['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']`. **The three ORT packages
  share the `onnxruntime` namespace; pip's install ORDER decides which one wins, file by file.**
  **Three different questions, never interchangeable: `get_available_providers()` = what the PACKAGE
  supports; `InferenceSession.get_providers()` = what the SESSION uses; only the ORT profiler says what
  EXECUTES.** This is a DISTINCT failure from the `cublasLt64_13.dll` / WinError 126 one above: there the
  provider is listed and fails to initialise; here it is not listed at all and the error is `null`.
- **`nemotron-…-fp16` IS AN ORPHAN EXPORT — `og.Model()` cannot open it** (no
  `genai_config.json`). Verified by census: present for **fp32 / int4 / int8**, ABSENT for **fp16**,
  `redux-onnx-int4`, `redux-reference` and `redux-ternary`. Pick an export by the presence of that
  file, not by its name.
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
- **THE DOCUMENTED LAUNCH NOW TRANSCRIBES: THE WORKER STARTS BY DEFAULT — changed 2026-10-07 (F1),
  and this flipped the flag's meaning, so stale advice here is a trap.** Until this change
  `app/webview/sotto_webview.py` called `start_worker` only inside `if self.args.with_worker:`, and
  `run.cmd` (the file the owner double-clicks) never passed it — measured in `_main/webview-run.log`:
  **32 shell starts, 10 with a worker, every one of them `reason=with-worker`** (audit §2 F1). Alt+C on
  the documented path opened a panel reading "Waiting for audio" with no capture process in existence.
  The contract NOW, as the code has it: `app/webview/run.cmd:5-9` documents
  `run.cmd` (starts hidden, TRANSCRIBES, waits for Alt+C), `--show`, `--no-worker`, `--with-worker`
  (alias) and `--help`; the decision is ONE factored, testable function —
  `SottoShell._worker_autostart_reason(args, env=None)` (`sotto_webview.py:2628-2679`), called once at
  `:1872` — and its FIVE reasons, most explicit first, are the `reason=` field of the
  `WORKER_AUTOSTART=started|declined reason=…` line:
  `with-worker` (the flag, AUTHORITATIVE — the lane instruments `_main/_app-drive.py` and
  `_main/_live-launch.py` pass it and keep working), `no-worker` (`--no-worker`, `:3991`),
  `env` (`SOTTO_NO_WORKER=1`), `measurement-flag(<flag>)` for the FIVE flags that measure the panel or
  the shell rather than transcription — **`--dump-dom`, `--selftest`, `--memory`, `--no-hotkey` and
  `--exit-after`** (`:2672-2678`) — and `default`, the ONLY value that starts it. The suppression set
  matters: without it a plain probe launch pays a ~2 GB model load and opens an audio tap on every arm.
  `--with-worker` still exists as an ALIAS (`:3999`) so scripts that pass it keep working; it can no
  longer be the reason a run has a worker. Gate, all arms in one command:
  `py -3 _main/_lane1-worker-default-arms.py` → `GREEN -- all 15 arm(s)`. `run.cmd` passes `%*` through
  untouched and adds only `--log`/`--ready-file` (`run.cmd:158-166`), so the wrapper holds no second flag
  table. Read `--help` before repeating any pre-2026-10-07 instruction about this flag.
  **Line numbers here are the 2026-10-07 shell revision (4326 lines); this file moved twice while this
  bullet was being written.**
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
  NOT. That is the decision `app/_legacy-electron/worker-bridge.js`'s STATE_MAP already
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
  `--exit-after`). The first measured closure was `--opaque` (transparent=False
  from CREATION): its flash drops to 3/20 and every catch is alpha=0 (the
  invisible `Opacity=0` creation dance) — **cost: the panel loses its
  transparent background / rounded-corner look.**

  **CLOSED 2026-10-07 WITHOUT that cost — the MAP ITSELF is refused, not
  re-hidden.** The mapping call is pywebview's own, on every navigation start:
  `platforms/edgechromium.py:348 self.form.Show()` (inside `on_navigation_start`,
  gated on `pywebview_window.transparent`, reached from the control's
  `NavigationStarting` subscribed at `:102`) — a call the shell does not make and
  cannot order against. `Show` is a .NET method, but pywebview calls it from
  PYTHON, so an instance attribute on the form shadows it for exactly that call
  (measured: `_main/_pythonnet-show-shadow-test.py` → `base.Show() ->
  INSTANCE-GATED`). `app/webview/sotto_webview.py` `_gate_form_show` (called from
  `_on_before_show`) installs that gate and refuses any map at full opacity while
  nobody asked; pywebview's own invisible creation dance (`Opacity=0`, allowed
  through) and the shell's own `show_panel` → user32 `SW_SHOWNOACTIVATE` (what
  Alt+C and `--show` both take) are untouched. NO subscription changes, so
  `_main/panel-hidden-at-startup-oracle.py`'s "1 pywebview + 1 shell handler"
  keeps its meaning. Measured, N=20 per arm at a 25 ms cadence:
  **`live` 0/20 launches with the window mapped (0 samples, longest 0 ms) vs
  `nogate` — the same file with only this call reverted — 4/20 launches,
  5 samples, longest 57.1 ms.** The gate is not vacuous: every fixed-arm launch
  logs exactly TWO `PANEL_SHOW_REFUSED` (one per navigation) AND still reaches
  `RECEIVER_READY`/`PRELOAD_ACTIVE`, rc=0. `--show` still maps the panel (6/6,
  `PANEL_SHOWN visible=true`), and the panel still PAINTS identically to the
  pre-fix shell: `_main/panel-paint-probe.py --secs 9` returns `PAINTED` with the
  SAME `px_sha256=1e762bdd6b55d0c6` for both. Receipt:
  `_main/receipt-20261007-panel-startup-flash.md`. Residual, disclosed there: the
  creation-dance map remains (alpha=0 ⇒ invisible; 5 of 20 launches, ~0 ms), and
  1 of 20 fixed-arm launches stalled before `CoreWebView2InitializationCompleted`
  — upstream of the gate, unattributed.
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

- **Alt+C IS THE APP'S ONLY CONTROL, so it now has a fallback chain, a single-instance lock and a
  loud failure — all three measured 2026-10-07, do not simplify them away.** `Alt+C` registers on its
  own thread (`HotkeyThread`, `MOD_NOREPEAT`); if another program owns it, the shell walks
  `HOTKEY_FALLBACKS` (`Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C`), registers the first free one and
  logs `WARN HOTKEY_FALLBACK requested=… using=…`, because the shipped behaviour was ONE
  `RegisterHotKey` whose failure was a single log line — a hidden app with a dead hotkey, i.e. a
  bricked app that looks like a working one. If every key is taken it raises a one-off error dialog on
  a daemon thread (the panel cannot be the messenger: nothing can open it). `take_single_instance_lock()`
  (`Local\SottoShell`, a kernel-released mutex) refuses a SECOND shell, because a second shell cannot
  register Alt+C (`RegisterHotKey` → 1409) and used to run on invisibly, so the owner's Alt+C answered
  the FIRST — possibly stale — instance; that collision stops being hypothetical now that autostart
  exists. `toggle_panel` decides from `IsWindowVisible`, not from the cached `self.visible`: a stale
  cache made the first Alt+C a no-op HIDE ("Alt+C does nothing" until pressed twice). Measured on this
  box: `Alt+C` is FREE, `Alt+F9` is OWNED by another program, and the whole path is
  `VERDICT: GREEN` in `_main/_audit-hotkey-delivery.py` (register → real `WM_HOTKEY` → handler →
  `toggle_panel('hotkey')` → fallback under the taken key → the mutex refusing the second holder).
- **SOTTO STARTS WITH WINDOWS, INSTALLED 2026-10-07, and the Run value is `pythonw.exe`, NEVER
  `run.cmd`.** `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\Sotto` =
  `"…\pythonw.exe" "…\app\webview\sotto_webview.py" --log "…\_main\webview-run.log"` — verified by
  `reg query`. A `.cmd` is a console program, so Windows would flash a console at EVERY login, which
  this repo forbids and the house census reports. Manage it with `run.cmd --install-autostart`,
  `--autostart-status` (it prints `matches this checkout: False` if the tree ever moves) and
  `--uninstall-autostart`. Side effect worth knowing: the login launch and a manual double-click can
  now race — which is exactly what the single-instance lock above is for.

- **THE PANEL WAS DEAD ON EVERY LAUNCH FOR A DAY (a `let` in the wrong place), and the fix is an
  ORDERING RULE — measured 2026-10-07 by running the app for the first time, with a video playing.**
  Symptom: the worker transcribed (peak 0.44, `captions (worker)=119`), the shell logged thousands of
  `BRIDGE_CAPTION_SENT delivered=true`, and the panel stayed frozen on *"Starting the worker"* with
  `#caption-list` at **`display:none`** and `live.count=0`. Cause, from the real DOM
  (`--dump-dom --with-worker`) plus the page-error channel added the same day:
  `Uncaught ReferenceError: Cannot access 'selectedEntry' before initialization`
  at `panel.js:428` ← `markRevealState` ← `wireHistory` ← **panel.js:87** (module init), while
  `let selectedEntry` was declared at **:263**. `let`/`const` hoist without initialising, so the read
  is a `ReferenceError` (temporal dead zone) and **the init block aborted at its first statement**:
  `wireCaptions()`, `wireStatus()`, `wireStats()`, `wireControls()` never ran, on every launch. The
  state that an init call can reach (`historyEntries`, `selectedEntry`, `searchQuery`, `searchHits`,
  `canonicalProducer`) is now declared ABOVE the init block, and the old declarations are GONE (a
  second `let` of the same name in one scope is a `SyntaxError` that takes the panel down harder).
  **RULE FOR `panel.js`: anything the init block can touch is declared above it.**
- **`PAGE_ERROR` IS THE CHANNEL THAT NAMES A BROKEN PANEL — it did not exist until 2026-10-07, and it
  is the reason the TDZ bug above is no longer invisible.** `evaluate_js` reports the SHELL's call
  (which succeeds), never the page's own JavaScript, so a throw inside `panel.js` left the log full of
  healthy `BRIDGE_CAPTION_SENT` lines while the owner looked at a frozen panel. The injected bridge
  now installs `window.addEventListener('error' | 'unhandledrejection')` → `post('page-error')` →
  `SottoShell._page_error` → `WARN PAGE_ERROR text=… at=file:line:col stack=…`. It runs from document
  start, so an INIT-time throw is caught. A bare resource event (no message/source/stack) is filtered
  on purpose: a fake `PAGE_ERROR` on every launch trains the next reader to ignore the word.
- **THE WORKER MUST NOT DIE ON AN ENDPOINT ANOTHER PROCESS HOLDS — and the holder is usually ITS OWN
  PREDECESSOR.** Measured on the app run: **86 `BRIDGE_DEATH`s**, every one
  `WasapiError: Initialize(SHARED|LOOPBACK) failed: 0x8889000A` (`AUDCLNT_E_DEVICE_IN_USE`),
  `captions=0`, restarted every 2 s forever. Two fixes in `worker/sotto_worker.py`, one place each:
  (1) the open happens in **`start()` → `_open()`**, NOT in the constructor, so the per-candidate
  guard now wraps the open too (it used to raise outside every handler as a traceback); (2) a busy
  endpoint is **waited for and retried twice** (1.5 s) before the ladder moves on, because the shell
  respawns 2 s after an exit and the endpoint release lags the process that held it — rotating AWAY
  from the busy endpoint abandoned the one candidate that was working. Proof: run the worker directly
  and candidate **1 of 10** (`WASAPI loopback: CABLE Input`, `rate=48000`) opens and transcribes the
  video; in the app, `deaths=0 restarts=0`, `peak=0.443448`.
- **A SECOND SHELL IS REFUSED — but ONLY when a hotkey is at stake.** `take_single_instance_lock()`
  (`Local\SottoShell`) protects the GLOBAL HOTKEY, the one genuinely exclusive resource. It was first
  written without that distinction and promptly refused every MEASUREMENT run while the owner's app was
  up (`SINGLE_INSTANCE already_running=true` on a `--dump-dom` dump) — i.e. the guard bricked the whole
  instrument set. It is now skipped, with `SINGLE_INSTANCE_SKIPPED reason=<flag>`, for `--no-hotkey`,
  `--dump-dom`, `--selftest`, `--memory` and `--probe-v2` (a measurement run registers no global
  hotkey: that is why AGENTS makes `--no-hotkey` mandatory for one). Never make that lock
  unconditional again.
- **THE LIVE BOX REPLACES, IT DOES NOT APPEND — and now it is measured, not asserted.** The engine
  emits a CUMULATIVE hypothesis (`start` fixed for the segment, `end` growing, `text` = the whole line,
  `final:false`), and `renderProvisional` (`panel.js:137-175`) rewrites ONE `<li>`'s `textContent` in
  place and drops it when the line commits. Measured over 40 s with a video playing: the box went
  **14 → 25 rows** (≈1 row per CLOSED line) while hundreds of partials arrived — an append-per-partial
  would have been thousands. Order is oldest-at-top, and `scrollTop = scrollHeight` fires only when the
  reader is within 48 px of the bottom (`:285-290`), so reading back is never interrupted.
  **CLOSED 2026-10-08 — FIXED AND GATED. The resolution is at the END of this bullet;
  the text that follows is the HISTORICAL description of the defect, kept because the
  mechanism is the transferable part:** words were split at CHUNK boundaries (`"não comp arecer"`,
  `"sse desequi líbrio"`) because `detok` converts the word-start marker `▁` to a space and then
  `.strip()`s it away (`sotto_worker.py:587`), while `push()` joins chunk texts with `" ".join(...)`
  over `frag.strip()` (`:1814`/`:1834`) — every chunk boundary becomes a word boundary. The fix touches
  `_words`/`line()`/the `max_chars` cap/`_close()` (~6 sites) and was deliberately NOT rushed: a wrong
  change there garbles every caption. Falsifier: run the worker 20 s on speech and look for a word split
  across a chunk boundary (seconds today).
  **RESOLVED 2026-10-08 (`_main/receipt-word-split-fix.md`; worker 235345 B sha256 `9DF88827…`, then
  237024 B `CEFD1868…` after the meter default):** a chunk boundary is no longer a word boundary.
  `chunk_is_continuation` reads the continuation from the TOKENS, `join_fragments` is the single
  separator decision, and the three emitters pass `continues=`; `detok` is untouched and `_close()` needed
  no change (a reported deviation from the "~6 sites" hint). Same input, before → after:
  `…na próx ima segunda-feira .  Os` → `…na próxima segunda-feira.  Os`; the two texts are **identical
  once spaces are removed**, and `done.text` (the whole-run detok, which never had the defect) is
  **byte-identical before and after**. Oracle `_main/word-split-oracle.py`: 12/12 PASS; `--neg-arm` (one
  function reverted) → **7 FIX arms RED, 0 stayed green, 0 controls broken**. No regressions:
  caption-lines 12/12, verdict-gate 14/14, fresh-processor GREEN, segment-rerun PASS. NOT proven: the
  live DEVICE path (the owner's worker holds the endpoint) and the second pass end-to-end.

- **A LEI DA STACK (decidida pelo dono, 2026-10-07) — e o que dela ainda NÃO existe.** Dois motores,
  dois regimes: o **nemotron streaming (0.6b int8, ONNX GenAI) é o motor AO VIVO** e só deve trabalhar
  quando o painel está ABERTO; o **Parakeet Redux é o motor GERAL**, e entra quando o painel está
  FECHADO, fazendo um transcritor **LEVE — o oposto do NVIDIA** (batch sobre o áudio acumulado, sem
  gastar CPU a cada 560 ms de stream). A frase do dono, verbatim: *"o nvidia é pro ao vivo, o parakeet
  redux é pro geral. o ao vivo só acontece quando o painel ta aberto. quando ta fechado, o redux entra,
  e vira um transcritor LEVE ao contrario do nvidia."*
  **Estado real, verificado 2026-10-07 (23h): OS PESOS EXISTEM AGORA EM DISCO.** Baixados pela HF CLI
  e verificados por sha256 contra o que a API publica (5/5 `MATCH`), em `worker/models/`:
  - ~~**`parakeet-redux-onnx-int4/`**~~ — **ESTÁ DE NOVO EM DISCO (2026-10-08): 27 ficheiros,
    415,87 MB, re-baixado. O "APAGADO" abaixo ficou VALSO.** ~~APAGADO a pedido do dono (2026-10-07,
    "usa o de 179m. o outro deleta"); re-baixável em ~20 s com
    `hf download eschmidbauer/parakeet-redux-onnx`.~~ **E O QUE DECIDE A LEI DA STACK É O PREÇO EM
    RAM, NÃO O NOME:** o ONNX int4 bate o ternário por **6,3× na RAM** — pico medido
    **615,3 MB contra 3,90 GB** (`_main/redux-cost-onnx.log`: `rss_peak_mb 615.3`, `rtf 8.33`,
    `text_matches_oracle: true`, 15,0 s de áudio em 1,80 s) com transcrição **byte-idêntica**. Para o
    "transcritor LEVE de fundo", o int4 é o motor leve; o ternário é o mais leve **em disco**
    (179 MB) e o mais pesado **em RAM**. Os três
    ficheiros pequenos que são a referência portátil ficaram em `worker/models/parakeet-redux-reference/`
    (`transcribe.py` 17.844 B — o laço TDT —, `config.json`, `vocab.txt`), e as transcrições de
    referência em `_main/redux-ptbr.txt` / `_main/redux-en.txt`. Era o export quantizado que a NOSSA stack
    corria:
    `encoder-model.onnx` 343.841.943 B (`sha256 ade2c65c…`), `decoder_joint-model.onnx` 72.552.270 B
    (`97ae0cb0…`), `preprocessor.onnx` 1.224.294 B (`3de5742f…`), `vad-model.onnx` 18.300.687 B
    (`18dfbe34…`), `vocab.txt`, `config.json`, **`transcribe.py` (17.844 B — a implementação de
    referência do laço TDT, o equivalente do `DimQ1/nemotron-speech-csharp` para o modelo ao vivo)**.
    Fonte `eschmidbauer/parakeet-redux-onnx` (revisão `1c285ba7…`), licença **CC-BY-4.0**.
    **Quantização CONFIRMADA por censo de ops meu, não pelo cartão:** `MatMulNBits` ×193 no encoder,
    IR 10, opset `ai.onnx` 18 + `com.microsoft` 1. `requirements.txt` do export: **`onnxruntime>=1.22`
    + numpy** e mais nada para inferência — nenhum llama.cpp, nenhum fork de GGUF.
  - **`parakeet-redux-ternary/`** — o Redux canónico (`moondream/parakeet-redux`, revisão `2bf12860…`):
    `model.safetensors` 177.774.490 B (`78ec2573…`), `ternary.json` (o manifesto do empacotamento:
    base 3, 5 dígitos/byte, grupos de 128, `w = scales·(code−1)`), `tokenizer.json`. Licença
    **CC-BY-4.0**. Correr ESTE exige o runtime do Moondream (`pip install moondream` → Photon/kestrel),
    que traz PyTorch — é o caminho caro; o ONNX acima é o pragmático.
  - **Fichas do modelo (do export ONNX):** `nemo-conformer-tdt`, `vocab_size` 8193, **blank 8192**,
    `max_tokens_per_step` 10, `durations` [0,1,2,3,4], `encoder_frame_seconds` 0.08, 16 kHz — é um
    **TDT** (token-and-duration transducer), **NÃO** o RNNT do nemotron: o laço de decodificação é
    outro (cada passo emite um token E um salto de duração) e há que portar o `transcribe.py`.
  **O RUNNER EXISTE E A PARIDADE ESTÁ PROVADA (2026-10-07, `_main/receipt-redux-ternary.md`).**
  `worker/redux_batch.py` corre o ternário **através do runtime do vendor**: `pip install --no-deps
  moondream==2.6.1 kestrel==0.9.1 kestrel-kernels… kestrel-native torch-c-dlpack-ext` (488,3 MB em
  disco; o `torch` já cá estava). O loader do próprio kestrel
  (`kestrel/models/parakeet_tdt/weights.py::unpack_export`) lê `ternary.json` + `model.safetensors`
  direto — **nenhum unpacker foi escrito**. Uso: `python worker/redux_batch.py --wav FICHEIRO
  [--json]` (legendas no stdout, diagnóstico no stderr, UTF-8 fixado). **Paridade byte-idêntica** com
  as duas transcrições do oráculo ONNX (pt-BR e en-US), incluindo as fronteiras de segmento;
  15 s de áudio em 1,1–2,1 s = **7–14× tempo real**, carga 3,6–4,3 s.
  **DUAS CONSEQUÊNCIAS QUE MANDAM NA DECISÃO:** (1) **custa 3,90 GB de RSS no pico**, porque o kernel
  int8 compilado do kestrel está inacessível nesta máquina (`_cpu.ternary_gemm_isa()` → `'scalar'`
  apesar de o CPU ter AVX2; o payload `kestrel_cpu.kstlc` é protegido e não traz a chave) e o runner cai
  na forma **dense documentada** (193/193 camadas ternary desquantizadas de uma vez). Ou seja: o
  ternário é mais leve **em disco** (179 MB) e ~8× mais pesado **em RAM** do que o export ONNX int4 que
  foi apagado (~450 MB) — para um transcritor de fundo "leve", a RAM é que conta. (2) **`torch.cuda.is_available()`
  é TRUE nesta caixa** (RTX 5080, torch 2.7.0+cu128) — a nota antiga "CUDA não carregável" vale para o
  `CUDAExecutionProvider` do **ORT**, não para o torch. NÃO VERIFICADO: áudio >30 s e o segmentador VAD
  (os dois clipes tinham <15 s), timestamps por palavra, `--device cuda`, e o caminho `gemm8`
  empacotado do Photon (não medido, não refutado).
  **O que AINDA falta para a lei da stack valer:** o gancho de visibilidade do painel e o agendador
  horário. Até isso existir, **não corte a captura ao esconder o painel** — hoje o NVIDIA é o único
  transcritor LIGADO. Correção de registo: a nota de procurement `cc-by-nc-4.0` referia-se a OUTRO artefacto
  (o branch GGUF/TQ1 do transcribe.cpp); **os dois artefactos baixados são CC-BY-4.0** — exigem
  atribuição, não proíbem uso.
- **O painel SEGUE a linha nova por omissão, e isso é medido — não volte à regra "já está perto do
  fundo".** O dono reportou *"a transcrição não tá dando auto scroll no painel"* (2026-10-07). A regra
  antiga lia `scrollHeight - scrollTop - clientHeight < 48` para decidir se rolava — uma regra que
  **nunca pode COMEÇAR**: com `scrollTop = 0` e uma lista já mais alta que a caixa, a expressão vale
  centenas de pixels, então o painel mostrava as linhas MAIS VELHAS para sempre enquanto as novas se
  acumulavam abaixo do fundo (parecia que as legendas tinham parado). Além disso a linha em curso só
  seguia ao ser CRIADA, não quando CRESCIA (`renderProvisional` reescreve o `<span>` e a linha fica
  mais alta — o momento exato em que o dono está a ler). Agora existe um flag `stickToNewest`: segue
  por omissão, para de seguir quando o dono rola para cima, retoma quando ele volta ao fundo —
  e o estado é declarado ACIMA do bloco de init (a lição do bug TDZ). **Instrumento (porque `count`
  não prova posição):** o `PANEL_STATE_PROBE` publica `live.scroll = {top,height,client,atBottom,
  overflowing}`. Medido com um vídeo a tocar: `top` acompanha `height - client` em todas as amostras
  (106/816, 450/1160, 748/1458, 1092/1802, 1458/2168) com `overflow=True` e `atBottom=True` — antes,
  `top` ficava em 0 para sempre. O hot reload do painel foi a PRIMEIRA verificação de máquina do F5
  (`HOT_RELOAD_PANEL_DONE reload=5` → `HOT_RELOAD_APPLIED` → `PANEL_SHOWN reason=hot-reload`).

- **HÁ UM CHATGPT NO TERMINAL E O DONO PEDIU QUE SE USE (2026-10-07).** Antes de decidir uma pergunta
  de engenharia ou de design por impressão, pergunta-se: `gpt` = `consultgpt`
  (`C:\Program Files\Python311\Scripts\gpt.exe`), browser real, sem API key —
  `gpt --no-code --session <nome> --prompt-file _main\<pergunta>.txt > _main\<resposta>.txt 2>&1`
  (o `--no-code` é obrigatório sem código anexado, demora 30–60 s, correr em background). Usa-se o que
  se concordar dele, e registe-se o que se aceitou e o que se rejeitou. **Como usar, armadilhas e o que
  já se perguntou: `docs/tools/consultgpt.md`** (o `codex` também existe mas a autenticação dele está
  morta aqui).

- **`_main\_audit-verify-all.cmd` MUST STAY CRLF, AND ITS EXIT CODE IS ITS VERDICT — measured 2026-10-08, do not re-litigate (this file said nothing about the battery until now, which is how a green word and a red run coexisted).** The subroutines are reached by `call :label` / `exit /b`, and **cmd.exe seeks a batch file by BYTE OFFSET**: with LF-only endings those stored offsets drift and the step list runs **TWICE** — measured (`_main\_audit-verify\_run-20261008-LF-only-double-run.log`): pass 1 reported `steps : 16 gate=10` GREEN, then cmd resumed and re-ran the tail, printing a SECOND summary `steps : 40 gate=28 control=10 expect-red=2` — 40 beacons for **29 distinct steps**, every control twice, **two int8 model loads**. The file is CRLF today (`len=18595`, 337 CRLF / 0 bare LF, sha256 `9DA38ECFCD33C53889458F17087FAF35012AE3BD4B3CCC914384E6B6B3D45BB`); the same bytes converted to LF ran once. **Any tool that rewrites it with `\n` silently re-breaks it — convert back (`-replace "\n", "\r\n"`) or the aggregation lies.** **AND CRLF IS NOT ENOUGH — A SECOND CAUSE, PROVEN 2026-10-08: A CONCURRENT EDIT OF THE FILE MID-RUN.** The byte-offset resume breaks on ANY length change in bytes cmd.exe has not yet read, LF or not. Reproducer, both arms, `_main\_cmd-offset-drift\subject.cmd` (pure CRLF, 919 B / 29 CRLF / 0 bare LF), with a `call :slow` outstanding while the controller rewrote it: **identical bytes → `SUBJECT-SUMMARY x1` / `[step] x3`; one `REM` inserted mid-run (919 → 964 B, sha256 `395A6E72…` → `C53C8A93…`) → cmd resumed at a stale offset, read `exit /b 0` as `'xit' não é reconhecido…`, and re-ran the tail: `SUBJECT-BEGIN` printed TWICE.** No LF involved. The strip lane measured the same on THIS file at 100 % CRLF (28 947 → 31 071 B mid-run); that edit IS the reproduction. So **a run whose `.cmd` sha256 changes mid-run is DIRTY: say so and repeat it, never present it as clean.** The size is a moving target: 18 595 B above, 31 071 B at that run, **32 203 B / 538 CRLF / 0 bare LF / sha256 `EBF715E9E4CF75B2FF5E62A529C2C375985246CBB7BFE8459EF2A9DD1BD0EB1C`** after the skip-guard cure. **`edit` preserves CRLF; the `write` tool emits LF-ONLY** (measured: a 29-line `.cmd` written by `write` came out 890 B / 0 CRLF / 29 bare LF) — never `write` this file. The battery AGGREGATES and its **exit code IS the verdict**: three step kinds — `:record` (the gate), `:control` (passes ONLY when the instrument's control actually went RED on its broken copy AND printed its control verdict), `:expectred` (rc must be exactly 1 with the violation text) — a MISSING instrument is a FAILURE, and any failure exits 1. Measured: clean run `steps : 29 gate=23 control=5 expect-red=1 missing=0 / BATTERY-VERDICT: GREEN / exit-code: 0` (`_main\_audit-verify\_battery-summary.txt`); negative proof `INJECTED-FAILING-STEP rc=3 … BATTERY-VERDICT: RED - 1 step(s) failed … NEGPROOF-EXITCODE=1` (`_run-20261008-negproof.log`). **Before this, a run with THREE red steps (`hotkey-delivery`, `verdict-gate`, `history-producer-gate`) exited 0** — a failure answering as success. So read the `BATTERY-VERDICT` / exit-code pair, never a step's own `rc`, never a lone last line, and never a `steps :` count without checking there is only ONE of them.

## Keeping THIS file true (it has been wrong twice in one day)

Every agent loads this file, so a false line here is not a doc defect — it is work done twice, or work
undone. Three rules, both earned today:

1. **A "grep returned ZERO matches" is a claim with a shelf life.** Re-run the grep before you repeat it,
   and paste the CURRENT numbers. The second pass went missing from this file because a zero-match grep was
   written once and cited afterwards; two lanes then reasoned from a file they had not re-read.
2. **Name the revision whenever you cite a line.** These lanes edit `worker/sotto_worker.py`,
   `app/webview/sotto_webview.py` and `app/webview/run.cmd` concurrently — today the worker moved from
   150592 B to 173388 B (and by one line *while this file was being written*), the shell from 4026 to
   4326 lines, and the flag `--with-worker` changed MEANING (it is now an alias; `--no-worker` is the
   opt-out). Give size, mtime and/or sha256, and re-check before you act on an old line number.
3. **Absence needs an instrument, not an impression.** "X is not implemented", "no window appeared",
   "nothing stamps this field" are all claims that a single grep, or a 60 s census, cannot support. Name
   the instrument, its cadence and its count — the same rule the panel's own windows and the segment-rerun
   canary were held to.
---

## THE SHELL'S OWN CONTRACT — strip surface, bridge, worker hot reload (measured 2026-10-08, lane `strip-surface`)

Everything below was measured against `app/webview/sotto_webview.py` — a revision another lane
has since appended to: this lane's own bytes ended at **389 256 B, sha256 `C4E04600BF1E4D96…`**,
and the file is now **397 180 B / sha256 `EA014D8F2CACD72E…` (7 199 lines)** with every marker
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
