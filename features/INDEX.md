# Macro Feature Architecture — sotto

> Auto-synced from Git (`d77871d`) at `2026-11-26T20:22:35Z` by `feature_map_sync.py`.
> Refine `how_it_works`, `inputs`, `outputs`, `interlinks`, `verify_cmd`, and `metric_ids` in `features/features.json` (set `"curated": true`) — re-syncs preserve curated contracts while keeping file lists & commits live.

## 1. Macro Feature Matrix

| Feature | Files | Commits | Inputs | Outputs | Interlinks | How It Works |
|---|---:|---:|---|---|---|---|
| `_main` | 1327 | 331 | Tracked source tree under `_main/`, `app/` and `worker/`; Battery step timings in `_cache/battery-steps.json` and `_main/battery-budget-baseline.json`; Oracle flags such as `--neg-arm` and `--record-step` | Per-oracle PASS/FAIL verdicts and rc on stdout; Step logs under `_main/_audit-verify/`; Ratchet updates in `_main/tooling-intent-baseline.json` | app/panel, app/webview, worker, discord | _main is the verification workshop rather than shipped runtime: `_main/_audit-verify-all.cmd` runs the aggregated battery and records each s |
| `_recovered` | 2 | 0 | Frozen Python snapshots committed during the 2026-10-23 recovery; Diff receipts in `_main/RECOVERY.md` and `_main/INTEGRATION-11.md` | Reconstructable diff between pre-loss HEAD and recovered worker; No runtime JSONL and no app state | - | `_recovered/worker_fab495ac.py` is the 4593-line snapshot recovered from the checkout that destroyed worker edits; `_recovered/worker_186c96 |
| `_tools` | 4 | 0 | Read-only URI to C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite; UTC cutoff and MAX timestamps from `_main/CRON-TRUTH.md` | POPULATION/WINDOW counts and pass-by-pass verdicts on stdout; Cron-silence evidence cited in `_main/CRON-VERDICT.md` | - | All four files are read-only SQLite passes over the same agent runtime store: `_tools/cron-restore-probe.py` counts rows after the 13:11Z cu |
| `app/_legacy-electron` | 11 | 1 | Child-process stdout JSONL (captions and statuses); Renderer IPC messages such as hide, toggle, pointer and getInfo | Captions and statuses delivered to the panel receiver and main-process caption log; Bridge-selftest rc 0/3 with per-step receipts | _main, app/panel, worker | `app/_legacy-electron/main.js` is the retired Electron main process and says so explicitly: the live window is the pywebview shell in `app/w |
| `app/panel` | 119 | 26 | `window.sotto` bridge events and worker caption lines relayed by the shell; Local theme CSS and bundled woff2 fonts; History root with `SOTTO_HISTORY_ROOT` override | Painted panel and floated-overlay DOM state; Per-hour history rows on the Python arm and `ctx1=` context tokens | _main, app/_legacy-electron, app/webview, worker | `panel.html` is the page the live WebView2 shell loads byte-for-byte; `panel.js` is its controller, and `themes/themes.js` plus `skin-host.j |
| `app/shadowplay` | 49 | 2 | Hotkey events and NVENC/ffmpeg encoder settings; Video frames in the replay ring; ffmpeg-generated seed clip in a temp directory | IDR-aligned replay clips on disk; Per-suite RESULT lines and a red-arm refusal verdict | - | `app/shadowplay/index.js` is the composition root: composeShadowplay wires HotkeyRouter, ReplayRing, ClipWriter, SavePath and NvencEncoder s |
| `app/verify` | 3 | 0 | Real `src-tauri/src/geometry.rs` and `memory.rs` sources; rustc tauri and serde stubs in `app/verify/rustc/` | Unit-test verdicts for dock arithmetic and PSAPI link; Receipt in `app/verify/verify-run.log` | - | `app/verify/src/lib.rs` pulls in `../../src-tauri/src/geometry.rs` and `memory.rs` with `#[path]`, so the unit tests executed are the produc |
| `app/webview` | 51 | 67 | YouTube player CDP snapshots and UIA caption window; Worker JSONL status and caption lines; Hotkey and pointer events via the WebView2 bridge | Overlay paint and panel DOM updates; History store rows under `history/<YYYY-MM-DD>/<HH>.md` plus `ctx1=` tokens; Structured run logs | _main, app/_legacy-electron, app/panel, worker | `app/webview/sotto_webview.py` is the live WebView2 shell: it hosts `panel.html` from app/panel unchanged and exposes the `window.sotto` bri |
| `bend_core` | 1 | 0 | Claims and model definitions in `LAWS.bend`; Witnesses in `PROOF.bend` and negative example laws | Lean verdict per law from the Bend gate; Python sample-check output from `model.py --selftest` | tools | `bend_core/LAWS.bend` holds the claims and model definitions, and `PROOF.bend` imports them with one proof per law for `bend PROOF.bend --ve |
| `discord` | 4 | 0 | DISCORD_BOT_TOKEN plus guild and voice-channel ids; Raw Opus packets tagged by SSRC from @discordjs/voice | 16 kHz mono PCM segments and packet JSONL under `out/<user_id>/`; Decoder-count and capture receipts | _main, worker | `discord/src/index.js` is the bot CLI: it takes `--guild` and `--channel`, reads `DISCORD_BOT_TOKEN` and calls `capture()` in `src/live.js`. |
| `probe` | 7 | 0 | Sounddevice device list and a 2 s capture window; Synthetic WAV for transcription; Agent session JSONL tree under C:/Users/Administrador/.minimax/v2/sessions | JSON evidence for loopback and ASR availability on stdout; Logs such as `probe/tap.log` and `probe/load.log` | - | `probe/sotto_probe.py` is the two-question probe: it enumerates sounddevice inputs, captures a short loopback window and transcribes a synth |
| `root-entrypoints` | 2 | 0 | Read-only URI to C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite; Electron runtime plus `_main/flicker-dom-oracle.js` | Schema and queue census on stdout; Flicker measurement results | _main, _tools, app/_legacy-electron | `_probe_schema.py` opens the minimax runtime-state SQLite read-only and prints schemas, a queue census and reference rows for queue, message |
| `scripts` | 4 | 1 | AGENTS.md and installed skill bytes; Worker WORKER_STATS line or a state=done JSON payload | BATTERY-VERDICT task-resolver-gate PASS/FAIL with rc 0/1/2; AGC RED/GREEN verdict with gain evidence | _main, worker | `scripts/task-resolver-gate.py` enforces the task-resolver mandate with checks for the AGENTS.md route, skill version and digest, gate-boots |
| `tools` | 2 | 0 | `bend_core/LAWS.bend` and `PROOF.bend`; Kernel (`lean --version`), translator (`bend version`) and WSL environment | Per-law verdict on stdout with rc; Append-only proof ledger JSONL rows | bend_core, _main | `tools/bend_verify.sh` is the law gate: it runs `bend PROOF.bend --verdict` inside WSL `ubuntu-bend`, checks that LAWS.bend alone still repo |
| `worker` | 44 | 49 | WASAPI loopback or microphone PCM audio; Engine and config flags from `worker/config.json`; Optional per-speaker PCM captured by `discord/` | Flushed caption and status JSONL lines on stdout; WORKER_STATS counters and audio ring state | _main, app/_legacy-electron, app/webview, app/panel | `worker/sotto_worker.py` is the live ASR worker: sounddevice loopback capture into a ring, resample, ONNX streaming features, RNN-T decode,  |

## 2. Subsystem Interconnection Graph

```mermaid
flowchart LR
  _main["_main (1327 files)"]
  _recovered["_recovered (2 files)"]
  _tools["_tools (4 files)"]
  app__legacy_electron["app/_legacy-electron (11 files)"]
  app_panel["app/panel (119 files)"]
  app_shadowplay["app/shadowplay (49 files)"]
  app_verify["app/verify (3 files)"]
  app_webview["app/webview (51 files)"]
  bend_core["bend_core (1 files)"]
  discord["discord (4 files)"]
  probe["probe (7 files)"]
  root_entrypoints["root-entrypoints (2 files)"]
  scripts["scripts (4 files)"]
  tools["tools (2 files)"]
  worker["worker (44 files)"]
  _main --> app_panel
  _main --> app_webview
  _main --> worker
  _main --> discord
  _main --> probe
  _main --> scripts
  app__legacy_electron --> _main
  app__legacy_electron --> app_panel
  app__legacy_electron --> worker
  app_panel --> _main
  app_panel --> app__legacy_electron
  app_panel --> app_webview
  app_panel --> worker
  app_webview --> _main
  app_webview --> app__legacy_electron
  app_webview --> app_panel
  app_webview --> worker
  bend_core --> tools
  discord --> _main
  discord --> worker
  root_entrypoints --> _main
  root_entrypoints --> _tools
  root_entrypoints --> app__legacy_electron
  scripts --> _main
  scripts --> worker
  tools --> bend_core
  tools --> _main
  worker --> _main
  worker --> app__legacy_electron
  worker --> app_webview
  worker --> app_panel
  worker --> discord
  worker --> scripts
```

## 3. Per-Feature Contracts

### `_main` —  Main
- **How it works:** _main is the verification workshop rather than shipped runtime: `_main/_audit-verify-all.cmd` runs the aggregated battery and records each step's rc, while `_main/battery-budget-oracle.py` enforces the per-step ratchet against `_main/battery-budget-baseline.json` and `_main/tooling-intent-oracle.py` checks that new instruments declare the bug they serve. `_main/yt-capture-replay-oracle.py` and `_main/yt-headless-paint-oracle.py` replay real player and paint fixtures offline, and `_main/dead-unwired-oracle.py` keeps the known-unwired twins from silently becoming second owners. Step timings live in `_cache/battery-steps.json`; none of this opens the owner's app.
- **Inputs:** Tracked source tree under `_main/`, `app/` and `worker/`, Battery step timings in `_cache/battery-steps.json` and `_main/battery-budget-baseline.json`, Oracle flags such as `--neg-arm` and `--record-step`
- **Outputs:** Per-oracle PASS/FAIL verdicts and rc on stdout, Step logs under `_main/_audit-verify/`, Ratchet updates in `_main/tooling-intent-baseline.json`
- **Interlinks:** app/panel, app/webview, worker, discord, probe, scripts, tools
- **Verify command:** `python _main/battery-budget-oracle.py`
- **Metric budgets:** e2e.battery_budget_gate_ms, subsystem.tooling_intent_ms
- **Key files (1327):** `_main/_47bb_main.cpp`, `_main/_agc_calib.py`, `_main/_agc_live.py`, `_main/_agents-md-rewrap.py`, `_main/_altc_delivery_probe.py`, `_main/_altc_thread_owner.py`, `_main/_anim-cost2.js`, `_main/_anim-cost2.py`, `_main/_anim-timeline-diff.py`, `_main/_anim-visual.js`, `_main/_app-census.py`, `_main/_app-drive.py` ...

### `_recovered` —  Recovered
- **How it works:** `_recovered/worker_fab495ac.py` is the 4593-line snapshot recovered from the checkout that destroyed worker edits; `_recovered/worker_186c969e_HEAD.py` is the 4511-line pre-loss HEAD baseline kept so the diff is reproducible. Both are the same system-audio-in / JSONL-captions-out worker now maintained as `worker/sotto_worker.py`, and both are frozen: no shell imports or spawns them. `_main/RECOVERY.md` records the hash, size and what was deliberately not committed.
- **Inputs:** Frozen Python snapshots committed during the 2026-10-23 recovery, Diff receipts in `_main/RECOVERY.md` and `_main/INTEGRATION-11.md`
- **Outputs:** Reconstructable diff between pre-loss HEAD and recovered worker, No runtime JSONL and no app state
- **Interlinks:** none detected
- **Verify command:** `HOLE: no gate`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (2):** `_recovered/worker_186c969e_HEAD.py`, `_recovered/worker_fab495ac.py`

### `_tools` —  Tools
- **How it works:** All four files are read-only SQLite passes over the same agent runtime store: `_tools/cron-restore-probe.py` counts rows after the 13:11Z cutoff, `_tools/cron-restore-refute.py` moves the boundary onto the exact MAX row, `_tools/cron-silence-control.py` counts hourly session and message rows while that store was being written, and `_tools/cron-store-loose-ends.py` checks for another store and process lifetimes. They print POPULATION and WINDOW counts and never write or start an app. The verdict they support is kept in `_main/CRON-VERDICT.md`.
- **Inputs:** Read-only URI to C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite, UTC cutoff and MAX timestamps from `_main/CRON-TRUTH.md`
- **Outputs:** POPULATION/WINDOW counts and pass-by-pass verdicts on stdout, Cron-silence evidence cited in `_main/CRON-VERDICT.md`
- **Interlinks:** none detected
- **Verify command:** `python _tools/cron-restore-probe.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (4):** `_tools/cron-restore-probe.py`, `_tools/cron-restore-refute.py`, `_tools/cron-silence-control.py`, `_tools/cron-store-loose-ends.py`

### `app/_legacy-electron` — App /  Legacy Electron
- **How it works:** `app/_legacy-electron/main.js` is the retired Electron main process and says so explicitly: the live window is the pywebview shell in `app/webview/sotto_webview.py`. `preload.js` is the original `window.sotto` contract that the live shell ports line for line, and `worker-bridge.js` spawns the Python worker, parses its stdout as JSONL and feeds captions and statuses to the panel. `bridge-selftest.js` drives that real child-process pipe with hostile lines (a traceback, a non-zero exit, explicit flushes) and exits 3 when any step is not observed.
- **Inputs:** Child-process stdout JSONL (captions and statuses), Renderer IPC messages such as hide, toggle, pointer and getInfo
- **Outputs:** Captions and statuses delivered to the panel receiver and main-process caption log, Bridge-selftest rc 0/3 with per-step receipts
- **Interlinks:** _main, app/panel, worker
- **Verify command:** `node app/_legacy-electron/bridge-selftest.js`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (11):** `app/_legacy-electron/bridge-selftest.js`, `app/_legacy-electron/bridge-single-instance-selftest.js`, `app/_legacy-electron/caption-formulation_modified.js`, `app/_legacy-electron/dom-probe.js`, `app/_legacy-electron/flicker-preload.js`, `app/_legacy-electron/hot-reload.js`, `app/_legacy-electron/main.js`, `app/_legacy-electron/preload.js`, `app/_legacy-electron/transcript-append-oracle.js`, `app/_legacy-electron/worker-bridge.js`, `app/_legacy-electron/worker-proc-count-probe.js`

### `app/panel` — App / Panel
- **How it works:** `panel.html` is the page the live WebView2 shell loads byte-for-byte; `panel.js` is its controller, and `themes/themes.js` plus `skin-host.js` switch the `data-theme` attribute and frozen skins. `caption-float.js` owns an independent overlay with its own DOM, CSS and bridge feed, while `history-context-store.js` implements the shared `ctx1=` token codec. `history-store.js` is the Node twin of the Python history writer and is deliberately unwired from every page; `_main/panel-deps-oracle.py` checks that all assets named by the page exist.
- **Inputs:** `window.sotto` bridge events and worker caption lines relayed by the shell, Local theme CSS and bundled woff2 fonts, History root with `SOTTO_HISTORY_ROOT` override
- **Outputs:** Painted panel and floated-overlay DOM state, Per-hour history rows on the Python arm and `ctx1=` context tokens
- **Interlinks:** _main, app/_legacy-electron, app/webview, worker
- **Verify command:** `python _main/panel-deps-oracle.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (119):** `app/panel/brand-bridge.js`, `app/panel/button-contract.css`, `app/panel/caption-float.css`, `app/panel/caption-float.js`, `app/panel/caption-formulation.js`, `app/panel/caption.html`, `app/panel/history-context-store.js`, `app/panel/history-source.js`, `app/panel/history-store.js`, `app/panel/lazy-assets.js`, `app/panel/letter-swap.js`, `app/panel/panel-unified.css` ...

### `app/shadowplay` — App / Shadowplay
- **How it works:** `app/shadowplay/index.js` is the composition root: composeShadowplay wires HotkeyRouter, ReplayRing, ClipWriter, SavePath and NvencEncoder so a press can actually land a clip. `run-all.mjs` discovers every `*.test.mjs` plus `parse-gate.mjs`, requires a RESULT line from each suite and includes a `--red-arm` that must be refused. `e2e.test.mjs` drives barrel, hotkey, ring, writer and clock in a temp dir with a real ffmpeg-encoded clip, and `audio-mix.js` and `broadcast.js` cover the audio and stream sides.
- **Inputs:** Hotkey events and NVENC/ffmpeg encoder settings, Video frames in the replay ring, ffmpeg-generated seed clip in a temp directory
- **Outputs:** IDR-aligned replay clips on disk, Per-suite RESULT lines and a red-arm refusal verdict
- **Interlinks:** none detected
- **Verify command:** `node app/shadowplay/run-all.mjs`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (49):** `app/shadowplay/_diskswap.mjs`, `app/shadowplay/_f48window.mjs`, `app/shadowplay/_inherit.mjs`, `app/shadowplay/_m5probe.mjs`, `app/shadowplay/_m5stss.mjs`, `app/shadowplay/_nonidr-probe.mjs`, `app/shadowplay/_rootdrive.mjs`, `app/shadowplay/_rootdrive2.mjs`, `app/shadowplay/audio-mix.js`, `app/shadowplay/audio-mix.test.mjs`, `app/shadowplay/audio-track.js`, `app/shadowplay/audio-track.test.mjs` ...

### `app/verify` — App / Verify
- **How it works:** `app/verify/src/lib.rs` pulls in `../../src-tauri/src/geometry.rs` and `memory.rs` with `#[path]`, so the unit tests executed are the product's own assertions rather than copies. `rustc/tauri_stub.rs` and `rustc/fakeserde.rs` stand in for external crates; `Cargo.toml` and `README.md` document exactly what a green does and does not prove. Nothing here starts the app, opens a window or exercises the hotkey.
- **Inputs:** Real `src-tauri/src/geometry.rs` and `memory.rs` sources, rustc tauri and serde stubs in `app/verify/rustc/`
- **Outputs:** Unit-test verdicts for dock arithmetic and PSAPI link, Receipt in `app/verify/verify-run.log`
- **Interlinks:** none detected
- **Verify command:** `cargo test --manifest-path app/verify/Cargo.toml`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (3):** `app/verify/rustc/fakeserde.rs`, `app/verify/rustc/tauri_stub.rs`, `app/verify/src/lib.rs`

### `app/webview` — App / Webview
- **How it works:** `app/webview/sotto_webview.py` is the live WebView2 shell: it hosts `panel.html` from app/panel unchanged and exposes the `window.sotto` bridge ported from the Electron preload. `youtube_cdp_source.py` supplies captions from the player CDP tree when UIA goes blank in a background tab, with `youtube_clock.py` and `youtube_monotonic.py` owning cue timing. `overlay_paint.py` holds the pure measurement, layout and bitmap half of the overlay paint while `caption_overlay.py` owns the on-screen window; `history_context.py` and the shell's history writer persist committed lines. `headless_paint.py` replays 745 real freeze samples off-screen for the paint budget.
- **Inputs:** YouTube player CDP snapshots and UIA caption window, Worker JSONL status and caption lines, Hotkey and pointer events via the WebView2 bridge, Existing history files under `history/`
- **Outputs:** Overlay paint and panel DOM updates, History store rows under `history/<YYYY-MM-DD>/<HH>.md` plus `ctx1=` tokens, Structured run logs
- **Interlinks:** _main, app/_legacy-electron, app/panel, worker
- **Verify command:** `python _main/yt-headless-paint-oracle.py`
- **Metric budgets:** basic.yt_capture_replay_ms, e2e.yt_paint_worst_ms
- **Key files (51):** `app/webview/audio_playing.py`, `app/webview/batch_queue.py`, `app/webview/bridge_census.py`, `app/webview/caption_drag.py`, `app/webview/caption_overlay.py`, `app/webview/caption_settings.py`, `app/webview/caption_wrap.py`, `app/webview/capture_exclusion.py`, `app/webview/code_identity.py`, `app/webview/cost_watchdog.py`, `app/webview/exit_killer.py`, `app/webview/external_subs.py` ...

### `bend_core` — Bend Core
- **How it works:** `bend_core/LAWS.bend` holds the claims and model definitions, and `PROOF.bend` imports them with one proof per law for `bend PROOF.bend --verdict` in the `ubuntu-bend` WSL distro. `bend_core/model.py` is the same model written in Python for hosts without Bend 2: it checks named sample inputs and exposes `--selftest`, but is explicitly not the proof. The `NEGATIVE_*.bend` files are the red arms for laws that must fail.
- **Inputs:** Claims and model definitions in `LAWS.bend`, Witnesses in `PROOF.bend` and negative example laws
- **Outputs:** Lean verdict per law from the Bend gate, Python sample-check output from `model.py --selftest`
- **Interlinks:** tools
- **Verify command:** `bash tools/bend_verify.sh`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (1):** `bend_core/model.py`

### `discord` — Discord
- **How it works:** `discord/src/index.js` is the bot CLI: it takes `--guild` and `--channel`, reads `DISCORD_BOT_TOKEN` and calls `capture()` in `src/live.js`. `live.js` joins with `@discordjs/voice` and hands raw Opus packets to `receiver-core.js`, which maps SSRC to user and writes one continuous PCM file plus a packet JSONL per speaker with one decoder per stream. `harness/two-speakers.js` drives the same core synthetically, and `worker/discord_streams.py` is the alternate reader reachable from `run.cmd --worker`, not from the live shell.
- **Inputs:** DISCORD_BOT_TOKEN plus guild and voice-channel ids, Raw Opus packets tagged by SSRC from @discordjs/voice
- **Outputs:** 16 kHz mono PCM segments and packet JSONL under `out/<user_id>/`, Decoder-count and capture receipts
- **Interlinks:** _main, worker
- **Verify command:** `python _main/discord-streams-oracle.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (4):** `discord/harness/two-speakers.js`, `discord/src/index.js`, `discord/src/live.js`, `discord/src/receiver-core.js`

### `probe` — Probe
- **How it works:** `probe/sotto_probe.py` is the two-question probe: it enumerates sounddevice inputs, captures a short loopback window and transcribes a synthetic WAV through faster_whisper, printing JSON and failing if either side has no evidence. `tap_probe.py` tests candidate tap devices for actual signal, `load_model.py` measures model load and device choice, and `laneshape.py`, `shape.py` and `native_imports.py` inspect agent-session lane shape and import availability. They are standalone instruments: no app module imports them.
- **Inputs:** Sounddevice device list and a 2 s capture window, Synthetic WAV for transcription, Agent session JSONL tree under C:/Users/Administrador/.minimax/v2/sessions
- **Outputs:** JSON evidence for loopback and ASR availability on stdout, Logs such as `probe/tap.log` and `probe/load.log`
- **Interlinks:** none detected
- **Verify command:** `python probe/sotto_probe.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (7):** `probe/laneshape.py`, `probe/load_model.py`, `probe/native_imports.py`, `probe/shape.py`, `probe/sotto_probe.py`, `probe/tap_probe.py`, `probe/which_import.py`

### `root-entrypoints` — Root Entrypoints
- **How it works:** `_probe_schema.py` opens the minimax runtime-state SQLite read-only and prints schemas, a queue census and reference rows for queue, message and turn-ingress tables. `flicker-injection-harness.js` creates an Electron BrowserWindow and injects `_main/flicker-dom-oracle.js` through `executeJavaScript` to measure renderer flicker. Neither file is imported by the shipped shell; both are run directly from the repo root.
- **Inputs:** Read-only URI to C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite, Electron runtime plus `_main/flicker-dom-oracle.js`
- **Outputs:** Schema and queue census on stdout, Flicker measurement results
- **Interlinks:** _main, _tools, app/_legacy-electron
- **Verify command:** `python _probe_schema.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (2):** `_probe_schema.py`, `flicker-injection-harness.js`

### `scripts` — Scripts
- **How it works:** `scripts/task-resolver-gate.py` enforces the task-resolver mandate with checks for the AGENTS.md route, skill version and digest, gate-bootstrap law, evidence vocabulary and battery wiring; its mutation arms require the named check to go red. `scripts/check-bug-hunt-wiring.py` does the equivalent for bug-hunt, `scripts/test_task_resolver_gate.py` unit-tests the gate, and `scripts/agc-gate.sh` reads WORKER_STATS to prove the live AGC acts when allowed and needed.
- **Inputs:** AGENTS.md and installed skill bytes, Worker WORKER_STATS line or a state=done JSON payload
- **Outputs:** BATTERY-VERDICT task-resolver-gate PASS/FAIL with rc 0/1/2, AGC RED/GREEN verdict with gain evidence
- **Interlinks:** _main, worker
- **Verify command:** `python scripts/task-resolver-gate.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (4):** `scripts/agc-gate.sh`, `scripts/check-bug-hunt-wiring.py`, `scripts/task-resolver-gate.py`, `scripts/test_task_resolver_gate.py`

### `tools` — Tools
- **How it works:** `tools/bend_verify.sh` is the law gate: it runs `bend PROOF.bend --verdict` inside WSL `ubuntu-bend`, checks that LAWS.bend alone still reports open TODOs, and asserts each law has a proof. `tools/bend_proof_ledger.py` is the append-only ledger: one JSONL line per run records hashes of kernel, translator, import closure, gate checks and environment so a green result can be tied to its toolchain.
- **Inputs:** `bend_core/LAWS.bend` and `PROOF.bend`, Kernel (`lean --version`), translator (`bend version`) and WSL environment
- **Outputs:** Per-law verdict on stdout with rc, Append-only proof ledger JSONL rows
- **Interlinks:** bend_core, _main
- **Verify command:** `bash tools/bend_verify.sh`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (2):** `tools/bend_proof_ledger.py`, `tools/bend_verify.sh`

### `worker` — Worker
- **How it works:** `worker/sotto_worker.py` is the live ASR worker: sounddevice loopback capture into a ring, resample, ONNX streaming features, RNN-T decode, punctuation and prosody, and speaker sidecars, with one JSON object per flushed stdout line. `live_route.py` and `engine_switch.py` choose the engine, `audio_queue_consumer.py` drains the queue and `discord_streams.py` is the alternate reader reachable from `run.cmd --worker`. `_main/audio-recorder-oracle.py` and `_main/worker-churn-oracle.py` gate capture and shell-driven restarts.
- **Inputs:** WASAPI loopback or microphone PCM audio, Engine and config flags from `worker/config.json`, Optional per-speaker PCM captured by `discord/`
- **Outputs:** Flushed caption and status JSONL lines on stdout, WORKER_STATS counters and audio ring state
- **Interlinks:** _main, app/_legacy-electron, app/webview, app/panel, discord, scripts
- **Verify command:** `python _main/audio-recorder-oracle.py`
- **Metric budgets:** UNSET — bind in benchmarks/budgets.json
- **Key files (44):** `worker/_prefix_audioflag.py`, `worker/_probe/_churn.py`, `worker/_probe/boot-control.py`, `worker/_probe/boot-io.py`, `worker/_probe/boot-phases.py`, `worker/_probe/no-background.py`, `worker/_sotto_worker_agcinert.py`, `worker/asr_node_assignment.py`, `worker/audio_queue_consumer.py`, `worker/audio_recorder.py`, `worker/audio_ring.py`, `worker/build_nemotron_cuda_mask.py` ...
