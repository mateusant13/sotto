# Docs, made true — 2026-10-07 (lane: documentation)

The audit's §7 names five files that "lie"; this is the receipt for the four this lane owns
(`AGENTS.md`, `README.md`, `worker/README.md`, `docs/model-specs/README.md`). Every claim written here is
either a measured number in the repo (cited `file:line`) or an upstream URL opened on 2026-10-07.
**§7 items in files this lane does NOT own are left alone deliberately** — see "Not in my lane" below.

**Line numbers drift.** The shell grew 4026 → 4326 lines and the worker moved 150592 B → 173388 B *while
this lane was working*, and the worker shifted by one more line between two of my own greps. Treat every
line number in the four files as a hint; the file, function and symbol names are the contract.

## 1. `AGENTS.md`

| change | evidence |
|---|---|
| The false bullet ("the second pass is ABSENT", citing a ZERO-match grep) rewritten: the M1-M3 pass IS present and wired | live `worker/sotto_worker.py` (173388 B, mtime 03:21:10, sha256 `3ACD3247…`): `def rerun` `:2654`, `reset_stream_state` `:623`, `_last_symbol` `:527/:651/:896/:2707+:2743`, `def finalise` `:2748`, `def drain` `:2771`, five `drain()` sites `:2840/:2879/:2900/:2914/:2925` |
| Same bullet now explains WHY it was wrong (stale-revision line citation + a grep never re-run) | `:2281` in the 150592 B revision was device-ladder code; the same expression is `:3111` today |
| Same bullet records that `reset_stream_state()` is only HALF a stream start | `:637-646`; the other half is `fresh_processor()` `:592` / `reset_frontend()` `:653` |
| New bullet: the HISTORY feed is EMPTY BY DESIGN and the oracle feeds itself the stamp | `app/electron/history-source.js:51,61-63`; `_main/live-vs-history-source-oracle.js:219` vs `:111-117`; `grep -rn producer worker/` → 0; newest `history/` file `2026-10-06/19.md`, mtime 19:58:36 |
| New bullet: the documented launch now TRANSCRIBES — worker starts by default (F1) | `app/webview/sotto_webview.py::SottoShell._worker_autostart_reason` (`:2628-2679`), called at `:1872`; five flags in the suppression set (`:2672-2678`); gate `_main/_lane1-worker-default-arms.py` → 15 arms |
| New bullet: hot reload now bounces through `stage.html`, NOT machine-verified | `reload_panel_assets` `:2725-2785`, `self.staged = False` `:2772`, `load_url(file_url(STAGE_HTML))` `:2775` |
| Layout row for `run.cmd` corrected; new closing §"Keeping THIS file true" (3 rules) | — |

## 2. `README.md` (root)

- New top section **"What this app IS today"**: `run.cmd` → WebView2 + pywebview 6.2.1
  (`_main/webview-run.log:1`) → worker → the DimQ1 int8 export (`worker/config.json:10`); the panel files
  and the legacy Electron shell; **verified** vs **planned** (Tauri plan, batch pass, diarization, GPU).
- `transcribe.cpp`: real project `handy-computer/transcribe.cpp` (MIT); `mudler/transcribe.cpp` → HTTP 404
  (GitHub API); its Parakeet family (13 variants) has **no** `parakeet-redux`; Moondream ships
  **safetensors** and documents **Photon**; the only Redux GGUFs are third-party and need
  `NairoDorian`'s `patches/ggml/0003-tq1_g128-ternary.patch`.
- Licence gate closed for the MODEL: `nvidia/nemotron-3.5-asr-streaming-0.6b` is **OpenMDW-1.1**
  (`license_name: openmdw-1.1`, `license_link: https://openmdw.ai/license/1-1/`); the grant is
  "without restriction", so commercial use is permitted, and distribution owes a copy of the agreement
  plus the notices.
- **NEW caveat, not in the audit:** the export this repo actually runs
  (`DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu`) declares `"license": "cc-by-nc-4.0"`. Recorded as
  an open disagreement, not papered over.

## 3. `worker/README.md`

- States list completed with the six missing words and their emit sites: `gate` `:2408`,
  `device-rotated` `:3000`/`:3153`, `device-exhausted` `:3178`, `silent-device` `:3226`,
  `music-only-capture` `:3262`, `no-speech-in-capture` `:3309` (+ the rest).
- Abandonment rule rewritten: **a CAPTION settles** (`settled = True` `:3053`); the fallback rung settles
  only when it carries signal (`:3059`); the floor only **classifies** (`TAP_PEAK_FLOOR = 0.002` `:219`,
  `TAP_WINDOW_S = 6.0` `:218`); the ladder **re-enters** the loudest signal-carrying candidate once
  (`:3136-3145`); `device-exhausted` is now the no-signal case.
- Language fallback: shipped default `auto`, and an ABSENT `model.lang_id` now means `auto`
  (`sotto_worker.py:2285`), NOT the host locale — the `"os"` sentinel in `lang_prompt.py:236` is only
  reached when written explicitly.
- `use_vad`'s code fallback is now `True` (`:2332`), so a config missing the key no longer contradicts
  this file; header de-"Electron"-ed; the VAD numbers attributed to the EXPORT.

## 4. `docs/model-specs/README.md`

- New §1.1: the chunk menu is **80/160/320/560/1120 ms** on the card, and the chunk is baked into the
  **export** — this one is 8960 (560 ms) / `left_context 70`, while siblings ship 17920 (1.12 s) with
  56/140, and sherpa ships one export per chunk size. Hence a faster caption needs another export;
  `audio.block_ms` cannot do it.
- §3: the engine default is `0` = `en-US` (card: "the pipeline uses the default language prompt (index 0,
  `en-US`)"), `auto` = 101, plus the card's LangID-vs-auto WER table — Portuguese is a tie
  (5.65 vs 5.57 at 560 ms; 5.48 vs 5.47 at 1.12 s), English is not (7.99 → 8.80).
- §4: the VAD numbers are the **exporter's** choice and two exporters DISAGREE — the `DimQ1` family
  (incl. the one Sotto ships) declares `0.3/3360/560`, while `onnx-community/nemotron-speech-streaming-es-0.6b-ft`
  declares `0.5/500/300` (fetched 2026-10-07). NVIDIA's card says nothing about VAD; Silero's own defaults
  are `0.5 / 100 / 30` + `neg_threshold = max(threshold-0.15, 0.01)` (link to `silero_vad/utils_vad.py`).
  That sibling export also carries `vocab_size 8193`, `blank_id 8192`, `chunk_samples 8960`,
  `left_context 70` and **no `lang_id` input** — recorded as the warning that every constant in §1 belongs
  to ONE export.
- §5: the precision trade with published numbers (LibriSpeech test-clean F32 3.04 / Q8_0 3.06 / Q4_K_M
  3.28 ⇒ ~0.02 vs ~0.25 pp), against the repo's own measured +268 MB RSS; AND the NeMo
  `compute_dtype != float32` refusal, now cited verbatim from
  `examples/asr/cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py::main()` with the
  one-clause scope ("a guard in NeMo's streaming inference SCRIPT and its config schema; the encoder
  modules carry no such check").
- §6 drift item 4: the export's `cc-by-nc-4.0` tag vs the base model's OpenMDW-1.1, framed in `README.md`
  as an **observed procurement risk** (two independent readings agree on the tag; not a legal conclusion,
  and `_main/research-parakeet-redux.md` agrees).

## What this lane could NOT fix

| item | why |
|---|---|
| `caption-formulation.js:296-299`, `panel.js:308-324`, `wasapi_loopback.py:865-878` (§7 rows) | files owned by other lanes — untouched |
| the hot-reload fix's new mechanism | code-read only; this sandbox has no WebView2, so `AGENTS.md` says plainly it is NOT machine-verified and names the check |

*(Two earlier UNVERIFIED rows were closed by a second reading on the same day: the VAD `0.5/500/300` figures
belong to the `onnx-community` es fine-tune, not the `DimQ1` family, and the `compute_dtype` guard lives in
NeMo's inference script rather than its encoder modules. Both are now cited with URL + scope; the audit's
claims stand. That is the third claim this round corrected by re-reading a source instead of a summary.)*

## Bonus findings (claims the audit did not list)

1. **`_main/panel-live-vs-history-probe.js:190`** claims the live `producer` comes from
   `worker/sotto_worker.py::_event` — `grep -rn producer worker/` returns **zero matches**. A third file
   asserting a producer that no code writes.
2. **The audit's §4.3 wording is wrong about the third-party GGUF.** It says the ternary "disappears"
   (de-quantised to F16/Q8_0/Q4_K). The card states the ternary encoder weights are **bit-identical to
   Moondream's in all three files**; only the 23 M dense params differ, and the load-time re-layout is
   **lossless**. The real objection is the fork dependency.
3. **The export we ship is tagged non-commercial** (`cc-by-nc-4.0`) while the base model is OpenMDW-1.1.
4. **The shell's suppression set is five flags, not three** (`--no-hotkey` and `--exit-after` also
   suppress the worker) — a `--dump-dom`-only reading would mis-describe every probe launch.

## Sources opened 2026-10-07

- <https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b> (card: chunk menu, LangID vs auto table, default prompt index 0, OpenMDW-1.1)
- <https://openmdw.ai/license/1-1/> · <https://huggingface.co/moondream/parakeet-redux>
- <https://huggingface.co/DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu> (cardData `cc-by-nc-4.0`) and the `-fp32-cpu` / `-fp32-c056-cpu` / `-fp32-c112-cpu` / `-gpu-cuda` `genai_config.json`
- <https://huggingface.co/onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4> · <https://huggingface.co/Nairod785/parakeet-redux-gguf>
- <https://github.com/handy-computer/transcribe.cpp> (+ `docs/models/nemotron-3.5-asr-streaming-0.6b.md`) · <https://api.github.com/repos/mudler/transcribe.cpp> (404)
- <https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py>
