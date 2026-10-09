# Sotto

Real-time transcription of everything your computer says, docked to the right
edge of the screen. Press <kbd>Alt</kbd>+<kbd>C</kbd>.

Sotto listens to **system audio**, not just the microphone. It writes a live
caption into an overlay while you play, call, or stream, and turns the result
into a searchable archive organised by day, then by hour.

---

## What this app IS today (2026-10-07)

Until 2026-10-07 this README described a different product: a Tauri 2 / Rust / Svelte 5 app with "no
Electron" and "Status: Planning". The app that exists is **Python + WebView2** and it runs. The plan
below is still the destination; this table is what is on disk.

| | today | where |
|---|---|---|
| **start it** | double-click `app/webview/run.cmd` — starts hidden, **starts the transcription worker**, waits for <kbd>Alt</kbd>+<kbd>C</kbd> | `app/webview/run.cmd:5-9` |
| opt-outs | `--no-worker` = shell only, no transcription; `--show` = panel up now; `--help` = every flag | `app/webview/run.cmd:5-9`; the rule that decides it is the function **`sotto_webview.py::SottoShell._worker_autostart_reason`** |
| **the shell** | `app/webview/sotto_webview.py` — WebView2 through **pywebview 6.2.1** + pythonnet, launched with `pythonw.exe` so no console window appears | `_main/webview-run.log:1` (`shell=webview2 pywebview=6.2.1 python=3.11.8`) |
| **the panel** | `app/panel/panel.{html,css,js}` — plain HTML/CSS/JS. This is the panel the app hosts and it is the live one | `AGENTS.md` layout |
| **the worker** | `worker/sotto_worker.py` — WASAPI loopback → Silero VAD → ONNX Runtime GenAI → RNNT greedy decode → JSON Lines on stdout | `worker/README.md` |
| **the model that runs** | `worker/models/nemotron-3.5-asr-streaming-0.6b-int8` — the DimQ1 int8 ONNX export, fixed at 560 ms chunks | `worker/config.json:10` |
| **legacy — not a fallback** | `app/_legacy-electron/{main,preload,worker-bridge}.js` is the EARLIER Electron shell, kept for comparison; the panel files it used to host are in `app/panel/` | `AGENTS.md` |
| **the thing to click** | `Sotto.cmd` in the repo root — a two-line forwarder to `run.cmd`, so there is a top-level file to double-click that does not duplicate the wrapper's contract | `Sotto.cmd` |
| **starts with Windows** | **INSTALLED 2026-10-07**: `HKCU\...\Run\Sotto` → `"…\pythonw.exe" "…\app\webview\sotto_webview.py" --log "…\_main\webview-run.log"` (never `run.cmd`: a `.cmd` is a console program and would flash a console at every login). Manage with `run.cmd --install-autostart` / `--autostart-status` / `--uninstall-autostart` | `app/webview/sotto_webview.py::autostart_command` |
| **Alt+C, robustly** | if another program owns Alt+C the shell walks `Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C` and logs the winner; one shell per session (a second launch is refused instead of running invisibly with a dead hotkey); the toggle asks `IsWindowVisible` rather than a cache | `_main/_audit-hotkey-delivery.py` → `VERDICT: GREEN` |

**Line numbers in this file are HINTS; the file and function names are the contract** — several lanes edit
`app/webview/*` concurrently, and the shell grew from 4026 lines to over 4900 in one session.

**The worker now starts by default; that changed on 2026-10-07.** Before it, `run.cmd` started no worker
at all, so the documented launch opened a panel reading "Waiting for audio" with no capture process in
existence — measured: 32 shell starts in `_main/webview-run.log`, 10 with a worker and every one of them
explicitly `--with-worker` (audit §2 F1). The decision now lives in ONE factored, testable function,
`_worker_autostart_reason` (called at `sotto_webview.py:1872`), whose five reasons are, most explicit
first, `with-worker` > `no-worker` > `env` > `measurement-flag(<flag>)` > `default` — and `default` is the
only value that starts the worker. `--with-worker` survives as an accepted ALIAS.

**Verified by measurement** (receipts in `AGENTS.md`, which is the living list): the shell starts and
paints; its layout is byte-identical to the Electron arm's across 14 DOM fields; the panel is kept off
screen at startup (25 ms census: 0/20 launches mapped, vs 4/20 with the gate reverted); Alt+C shows it;
the worker's failure vocabulary reaches the panel as an error with its cause; resident memory int8
1192 MB / int4 924 MB after load + one inference.

**Planned, NOT implemented** — do not describe these as existing: the Tauri 2 / Rust / Svelte 5 shell
(§*The plan*; still the destination); the batch "canonical transcript" pass — **nothing in the repo stamps
`producer:'redux'`**, so the panel's History half is empty BY DESIGN and `history/` has taken no new file
since 2026-10-06 19:58; diarization; a GPU route (`CUDAExecutionProvider` is requested and ORT returns
CPU on this box). **Open defects with their measurements:** `docs/audit/auditoria-completa-20261007.md`.

---

## What is verified and what is not

Everything in this section was measured against the Hugging Face API or the repositories' own files, on
the date named in each row (2026-10-05 for the counts in `docs/stack-verification.md`, 2026-10-07 for the
rows re-read here). Numbers are downloads and likes at that instant, and they move.

| component | repo | status | notes |
|---|---|---|---|
| streaming ASR | `nvidia/nemotron-3.5-asr-streaming-0.6b` | **verified** | 1,282,468 downloads · 1,174 likes (HF API, 2026-10-07) · `nemo` · cache-aware FastConformer-RNNT · the card declares **40 language-locales**, of which **32 transcribe out of the box** (19 transcription-ready + 13 broad-coverage) and 8 are adaptation-ready (need fine-tuning) · **OpenMDW-1.1**, not `license:other` in substance — see *Licence posture* |
| batch ASR | `moondream/parakeet-redux` | **verified** | 10,187 downloads · 231 likes · `ternary` · `1.58-bit` · 25 languages incl. `pt` · **CC-BY-4.0** |
| inference runtime | `handy-computer/transcribe.cpp` (**MIT**) | **corrected 2026-10-07** | runs the Nemotron GGUF (that repo: **1,835,919 downloads** on 2026-10-05, `docs/stack-verification.md:460`). It is **not** the answer for Parakeet Redux: its Parakeet family lists 13 variants — `parakeet-ctc-0.6b/1.1b`, `parakeet-primeline`, `parakeet-rnnt-0.6b/1.1b`, `parakeet-tdt-0.6b-v2/v3`, `parakeet-tdt-1.1b`, `parakeet-tdt_ctc-1.1b/110m`, `parakeet-ultra`, `parakeet-unified-en-0.6b`, `orukeet` — **and `parakeet-redux` is not one of them**; where it mentions Moondream it points at the sibling `parakeet-ultra`. The name `mudler/transcribe.cpp` in earlier drafts of this file **does not exist** (GitHub API returns HTTP 404) |

**What `moondream/parakeet-redux` actually is, and how it wants to be run** (all fetched 2026-10-07;
primary sources [model card](https://huggingface.co/moondream/parakeet-redux)):

- **Weights are safetensors, not GGUF** — `model.safetensors` 177.8 MB, packed ternary
  (`thrush-ternary-v2`, 5 trits/byte, group 128).
- **The runtime its owner documents is [Photon](https://moondream.ai/photon)**
  (`pip install moondream` → `md.photon("moondream/parakeet-redux", device="cpu")`), which reads the
  packed weights directly. 113× real time on 8 x86 cores, CC-BY-4.0.
- **The only Redux GGUFs are third-party**, and they need a **fork**: `Nairod785/parakeet-redux-gguf`
  ([card](https://huggingface.co/Nairod785/parakeet-redux-gguf)) ships `TQ1_F16` / `TQ1_Q8_0` / `TQ1_Q4_K`
  built for `NairoDorian/transcribe.cpp`, whose `patches/ggml/0003-tq1_g128-ternary.patch` adds the
  `TQ1_G128` ggml type. Upstream `handy-computer/transcribe.cpp` has **no `0003` patch** and cannot read
  them. **A correction to the audit's own §4.3 wording:** these are *not* plain "de-quantizations to
  F16/Q8_0/Q4_K" — the card states the ternary encoder weights are **bit-identical to Moondream's in all
  three files** and only the 23 M dense (never-ternary) parameters differ; the `Q*` suffix names the dense
  part, and the ternary codes are re-laid-out *losslessly* at load. The real objection to the GGUF path is
  the **fork dependency**, not a precision loss.

So the honest statement is: `transcribe.cpp` does not open the Redux ternary GGUF **as upstream ships**,
and the alternative is not an unreleased hack — it is either the model owner's own runtime (Photon) or a
different export consumed by a runtime that already exists. Either way, someone must write the decode loop
and stamp `producer:'redux'`; see `_main/research-parakeet-redux.md` (its options A/B/C, and its own
admission that HISTORY is fail-closed and empty by design). And note the plan's "no resident Python"
constraint is **already moot in-tree**: the app that exists IS Python, so a Python decoder for the batch
pass costs *less* than a C++ one.

Paths that exist and are not yet chosen: Photon (the owner's runtime — heaviest dependency, it drags
`torch>=2.8` and reports usage telemetry); the ONNX export (`eschmidbauer/parakeet-redux-onnx`, 4 graphs,
the ternarised encoder stored as `MatMulNBits`, declared inference floor `onnxruntime>=1.22`, and this box
has 1.30.0) driven by `onnx-asr` (MIT, numpy + onnxruntime only) or a hand-written TDT loop; CoreML for
Apple silicon; `sherpa-onnx`. None of them is wired. Falsifiers for each: `_main/research-parakeet-redux.md`.

Not yet verified: diarization model, embedding model, the small LLM, sqlite-vec version.

---

## Licence posture

**The streaming model's gate is read; the EXPORT this repo ships is the part still open.**

- **`nvidia/nemotron-3.5-asr-streaming-0.6b` is OpenMDW-1.1.** The [model
  card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b) declares `license: other` /
  `license_name: openmdw-1.1` / `license_link: https://openmdw.ai/license/1-1/`, and its own
  "License/Terms of Use" section points at the same text
  ([OpenMDW-1.1](https://openmdw.ai/license/1-1/)). In that text the grant is unqualified — "permission is
  hereby granted, free of charge, to deal in the Model Materials **without restriction**" — so
  **commercial use is permitted**: no field-of-use carve-out, no MAU threshold, no share-alike, no
  in‑UI attribution clause. The only conditions on **distributing** the materials are documentary:
  "(1) a copy of this agreement, and (2) all copyright notices and other notices of origin included in the
  Model Materials that are applicable to your distribution" — satisfiable with a `LICENSE` + `NOTICE` in
  the repo and a `licenses/` folder in the installer. The card's "This model is ready for commercial use"
  is NVIDIA's editorial claim, not a licence term; the licence text alone permits it. Full reading with
  the verbatim quotes: `docs/stack-verification.md`, "QUESTION ONE".
- **`moondream/parakeet-redux` is CC-BY-4.0**, like its base `nvidia/parakeet-tdt-0.6b-v3` and every
  derivative in this stack (its ONNX export, the third-party GGUF). Redistribution and commercial use are
  permitted; attribution (credit, licence link, "changes were made") is required. Bundling is a paperwork
  cost, not a blocker.
- **OPEN — the export this repo actually runs is tagged NON-COMMERCIAL.** `worker/config.json:10` selects
  `worker/models/nemotron-3.5-asr-streaming-0.6b-int8`, whose upstream is
  [DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu](https://huggingface.co/DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu)
  — and that repo's cardData is `"license": "cc-by-nc-4.0"`, restated on its card as "This model inherits
  [cc-by-nc-4.0] from the base NVIDIA Nemotron model". Its licence link points at a *differently named*
  NVIDIA repository than the one this project read (`nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b`
  vs `nvidia/nemotron-3.5-asr-streaming-0.6b`), whose published licence is OpenMDW-1.1. **The two
  statements disagree; this README records the disagreement instead of picking the convenient one.**
  Until an export whose terms match the base model is chosen, or NVIDIA confirms the export inherits
  OpenMDW-1.1, the export is the gate that remains — and **downloading the weights at first run** from the
  model owner is the path that distributes none of them.

  **How to read that item: an OBSERVED PROCUREMENT RISK, not a settled legal conclusion.** Two independent
  readings (this lane and `_main/research-parakeet-redux.md`) agree that the tag is `cc-by-nc-4.0`; neither
  is legal advice, and the contradiction inside the tag itself — it claims to inherit from a repository
  whose published licence is OpenMDW-1.1 — is NVIDIA's to resolve, not ours to assume away.

---

## The plan — the destination, NOT what runs today

Read this as the target state. What runs today is in the table at the top of this file.

- **Shell** — Tauri 2, Rust, Svelte 5 + TypeScript, replacing the current **WebView2 + pywebview**
  shell (`app/webview/`). "No Electron" is still the plan; note that the CURRENT shell also is not
  Electon — `app/_legacy-electron/` is the earlier shell; the panel files it hosted are in `app/panel/`.
- **Capture** — CPAL, WASAPI loopback on Windows. Loopback, not microphone: the
  product is "any audio on the PC".
- **Hotkey** — Tauri global shortcut, `Alt+C`.
- **ASR** — Nemotron 3.5 streaming while recording (**this is what ships**); Parakeet Redux for the
  canonical transcript afterwards (**not implemented** — nothing stamps `producer:'redux'`, so the
  History feed stays empty).
- **Diarization** — TBD.
- **Search** — SQLite + FTS5 + sqlite-vec, so lexical and semantic search share
  one database and one file.
- **Idle policy** — every model worker is on demand. With no audio, nothing is
  resident but the shell and the database.

## Status

**The app exists and runs (see the top of this file); the TARGET architecture above is planning.** The
shipped shell is WebView2 + pywebview, the panel is HTML/CSS/JS, the worker is Python, and open defects
are tracked with measurements in `docs/audit/auditoria-completa-20261007.md`. Roadmap: `docs/roadmap.md`.