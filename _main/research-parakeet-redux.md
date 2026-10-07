# Research: What Parakeet Redux IS, and what is actually true about it

**Date:** 2026-10-07 · **Model seat:** `opencode-go-1/deepseek-flash:high` (the seat that produced this doc) · **Classification:** `port` (which existing donor fills the batch-ASR slot, and what each costs to adopt/adapt). A `measurement` arm rides along: the runtime-floor probe in `## Oracle`.

**Scope note (owner order, verbatim):** *"trabalha só no sotto. nao mais no maanger ou omp."* This doc reads only, and writes only itself, inside `H:/sotto`. Nothing was downloaded, installed or built. No window, no audio.

---

## Question & stakes

The owner was handed three options and refused to choose: **(A)** build a TQ1 fork of transcribe.cpp, **(B)** adopt upstream transcribe.cpp + an upstream Parakeet quant, **(C)** download the `eschmidbauer/parakeet-redux-onnx` export. His words: *"nao sei. pesquisa sobre o parakeet redux antes."*

The decision this feeds: **which engine is allowed to stamp `producer:'redux'` into Sotto's HISTORY field** — the canonical, post-recording transcript. Stakes: HISTORY is currently **fail-closed and empty by design** (`app/electron/history-source.js:29-30,48-51` accepts only `producer:'redux'`, refuses `'live'`), and the owner's whole complaint is that a canonical pass does not exist. Getting this wrong in either direction is expensive: choose A on a false premise and Sotto acquires a build-from-source dependency on an unreleased one-maintainer fork; choose B and the field named "Redux" names a model that is not Redux; choose C and you may have picked a third-party export with 88 downloads over a vendor runtime that reads the same weights directly.

**The one premise that decides A vs "use a release"** — *does any RELEASED runtime load the ternary weights, or only the named private fork?* — is answered below, and it is answered **FALSE as stated**: the ternary weights are read by Moondream's own released runtime. The fork is only for the GGUF/ggml branch.

---

## Method

Read (primary sources, opened this session):

- **Owner's own plan:** `H:/sotto/README.md` (`:20-32, :54-55, :62-64`), `H:/sotto/docs/roadmap.md` (M2, `:64-67`), `H:/sotto/docs/stack-verification.md` (`:366-410` the `tq1_g128` finding, `:1-142` the OpenMDW-1.1 finding), `H:/sotto/_main/receipt-20261007-parakeet-redux-path.md` (the prior reconnaissance, 29449 B).
- **Prior internal audits** (mined for conclusions about THIS symptom, not re-derived): `H:/sotto/docs/audit/ao-vivo-vs-redux.md`, `H:/sotto/docs/audit/historico-vs-redux.md`, `H:/sotto/docs/audit/original-prompt-adjudication.md` (R7, `:85`), `H:/sotto/docs/oss-approaches-20261006.md`, `H:/sotto/_main/receipt-20261007-live-vs-history-source.md`.
- **Live repo state at write time** (`git log -1` → `11df66e`): `app/electron/history-source.js` (producer guard, read), `worker/sotto_worker.py` (grep: `rerun()` exists at `:2173-2241`).
- **Primary external sources, all fetched and quoted:** HF model APIs and raw files for `moondream/parakeet-redux`, `nvidia/parakeet-tdt-0.6b-v3`, `Nairod785/parakeet-redux-gguf` (+ `QUANTIZATION.md`), `eschmidbauer/parakeet-redux-onnx` (+ `README.md`, `requirements.txt`, `config.json`), `mrfakename/parakeet-redux-ONNX`, `mrfakename/parakeet-redux-webgpu`; GitHub APIs for `handy-computer/transcribe.cpp` (releases, `patches/ggml`) and `NairoDorian/transcribe.cpp` (repo metadata, releases); PyPI JSON for `onnx-asr`, `moondream`, `kestrel`; the vendor release post at `moondream.ai/blog/introducing-parakeet-redux-and-ultra`.
- **One executed probe:** the `## Oracle` script, run once (rc=0, GREEN) — it is my own instrument, not a house gate.

**What I explicitly did NOT do** (rule 13, declines with the cost to close):

1. **Did not download or run any Parakeet Redux weight, GGUF, ONNX graph, Photon/`kestrel`, or `onnx-asr`.** Prohibited by the brief and by machine law. Cost to close: ~436 MB (ONNX) or ~180 MB (GGUF) + a decode run; ~1 dependency install for Photon, which the brief forbids.
2. **Did not unzip / inspect the ONNX graphs byte-wise** to enumerate every op and read the `opset`/`ir_version`. The 344 MB encoder is not readable as text. What I state about ops comes from the export author's own `config.json` (`"ternary_weights": "MatMulNBits 4-bit, block 128"`) and `README`. Cost to close: one download + `onnx.load` and walk `graph.node` — a real but forbidden cost.
3. **Did not probe `sherpa-onnx`** as a potential consumer of the redux ONNX (see `## Guarantee inventory`, row marked NOT ADDRESSED). Cost to close: fetch sherpa-onnx docs/repo and check parakeet TDT + `MatMulNBits` support — cheap, not done because it was outside the three named options and I prioritised the named questions.
4. **Did not execute the ONNX export.** Its shipped files are **not** a dense/no-quant variant (see Q3) — the shipped encoder is the `MatMulNBits` pack; the dense variant is a documented *export option*, absent from the repo.
5. **Did not read the CC-BY-4.0 legal text** clause-by-clause; I relied on the licence identifier on the model cards and the definitional content of CC-BY-4.0. Cost to close: one fetch of `creativecommons.org/licenses/by/4.0/legalcode`.

---

## Answer

**Symptom status:** this is a knowledge gap, not a performance symptom, so rule 12's symptom-probe does not apply. The **load-bearing premise** the brief asks me to test — *"does any RELEASED runtime load those weights, or only the named private fork?"* — is **MEASURED: a released runtime does.** Moondream's own `Photon`/`Kestrel` runtime (`pip install moondream`, moondream 2.6.1 → `kestrel==0.9.1`) is documented as reading the packed ternary weights directly. The private fork is required **only** for the GGUF/`TQ1_G128`/ggml branch, not for the ternary format itself.

### Q1 — What IS Parakeet Redux?

`moondream/parakeet-redux` is **Moondream's (M87 Labs) ternary re-quantisation of NVIDIA's `parakeet-tdt-0.6b-v3`** — the 0.6 B multilingual **TDT (token-and-duration transducer)** checkpoint with a **FastConformer** encoder. Primary: HF API `config.model_type = "parakeet_tdt"`; model card, first line: *"A 1.58-bit version of [parakeet-tdt-0.6b-v3]. Same architecture, same tokenizer, but every encoder weight is -1, 0 or +1."*

**What "redux" changes is exactly one axis: the encoder's linear weights become ternary `{−1, 0, +1}`.** Everything else stays the base model's: *"Same architecture, same tokenizer"*, and (QUANTIZATION.md) the dense tensors — subsampling convs, depthwise convs, norms, batch-norm stats, the LSTM predictor, the joint network and embeddings — are **not** ternarised. Measured split: **264 ternary modules = 603,979,776 weights; 23,290,911 dense weights.** Result: weights **1.2 GB → 178 MB**.

The `1.58-bit` label is arithmetic, not marketing: log₂(3) = 1.585 bits per weight, and the packing is **5 ternary digits per byte** (3⁵ = 243 ≤ 256). `ternary.json` declares this verbatim: `"format": "thrush-ternary-v2"`, `"base": 3`, `"code_offset": 1`, `"elements_per_byte": 5`, `"group_size": 128`, `"weight_rule": "w = scales[row, col // group_size] * (code - 1) with code in {0,1,2}"`.

Accuracy, from the card (its own pipeline, Open ASR Leaderboard normalisers): English 7-set **6.26 → 6.55 %**, FLEURS 25-language **11.62 → 10.56 %** (better), business speech **6.15 → 6.96 %**, background noise **6.72 → 9.04 %** (the worst gap — *"the ternary encoder's acoustic margin is thinner"*), TED-LIUM long-form **2.71 → 2.51 %** (better). Its sibling `moondream/parakeet-ultra` is the full-precision, further-trained version (5.80 / 9.55 / 5.79 / 5.82 / 1.94 %). Released 2026-09-18, revision `2bf12860…`, CC-BY-4.0.

### Q2 — Is the ternary / 1.58-bit line real and USABLE?

**Real: yes, MEASURED.** `ternary.json` is a full manifest (2,423 lines) listing every quantised module and its `zero_fraction` (0.13–0.78 — the weights genuinely take all three codes, not just ±1). `model.safetensors` = **177,774,490 B**. The file is not a stub.

**Usable: yes, but which runtime is the whole question — and the answer splits in two:**

| branch | who can load it | released artifact? |
|---|---|---|
| the **packed `thrush-ternary-v2` weights themselves** (`.safetensors`) | **Photon / Kestrel** — the vendor's own runtime | **YES.** `pip install moondream` (2.6.1) → `kestrel==0.9.1`; card: *"Run it with Photon, which reads the packed weights directly: AVX-512 VNNI on x86, NEON on ARM, Metal on Apple GPUs."* |
| the **GGUF / `TQ1_G128` / ggml** re-layout | `NairoDorian/transcribe.cpp` fork only | **NO.** Fork has **zero releases** (API `[]`); upstream has no `0003` patch |

So the premise handed to the owner — *"the ternary line may only be usable through the private fork"* — is **false for the weights and true only for the GGUF packaging.** The `TQ1_G128` story is a packaging choice, not a capability limit.

**The `TQ1_G128` wait is as follows (all MEASURED today):** ggml's stock `TQ1_0` (1.69 bpw) and `TQ2_0` (2.06 bpw) carry one scale per 256 weights; redux carries one per **128**, so it needs a new type. The fork adds `GGML_TYPE_TQ1_G128` (id **96**, 1.75 bpw) as `patches/ggml/0003-tq1_g128-ternary.patch`. **Upstream `handy-computer/transcribe.cpp` at `main` contains exactly `0001-fix-threadpool-oversubscription.patch` and `0002-backend-reg-filter.patch` — no `0003`** (my own API call confirms the local finding independently). Upstream `v0.3.1` (2026-10-04) *does* ship **Windows prebuilts** (`transcribe-native-0.3.1-windows-x86_64-cpu-vulkan.tar.gz` and `…-cuda.tar.gz`) — but those are upstream, and upstream cannot open the TQ1 files. And the author's own reproduce step clones the fork (`git clone https://github.com/NairoDorian/transcribe.cpp`), which is a one-maintainer, 0-star, MIT fork with **no release artifacts** — clone + CMake build, not a download.

There is an extra wrinkle worth the owner's eye: on ggml the fork does **not** even run `TQ1_G128` natively by default — at load it re-lays the ternary weights losslessly into **Q4_0** (CPU default) or **Q2_0** (CUDA), because *"ternary `w = s·(c−1)` is exactly Q4_0 with `q = c + 7`, `d = s`"*. The fork's own FLEURS-fr WER is **8.32 / 8.31 / 8.18 %** for TQ1_F16/Q8_0/Q4_K against **4.65 %** for `parakeet-ultra` — the ternary trade-off, not a conversion loss.

### Q3 — What does the ONNX export actually contain?

`eschmidbauer/parakeet-redux-onnx` (rev `1c285ba7…`, CC-BY-4.0, `base_model: moondream/parakeet-redux`, created 2026-09-24, **88 downloads / 1 like**, usedStorage 435,919,194 B ≈ **436 MB**) is a **four-graph NeMo-style export**:

| graph | size | signature |
|---|---|---|
| `preprocessor.onnx` | 1.2 MB | `waveforms [B,samples] f32`, `waveforms_lens [B] i64` → `features [B,128,T]`, `features_lens` |
| `encoder-model.onnx` | 344 MB | `audio_signal [B,128,T]`, `length` → `outputs [B,1024,T/8]`, `encoded_lengths` |
| `decoder_joint-model.onnx` | 73 MB | one prediction-net + joint step → `outputs [B,1,1,8198]` (**8193 token logits + 5 duration logits**), blank id **8192**, plus prednet/state tensors |
| `vad-model.onnx` | 18 MB | the checkpoint's own VAD head — `probabilities [B,T/8]` |

plus `vocab.txt`, `config.json`, `transcribe.py`, `export_onnx.py`, `requirements.txt`. It is **not** a single fused RNN-T graph — it is `preprocessor → encoder → greedy loop over decoder_joint`, with the model's own VAD head for cutting long audio at pauses (segments ≤ 30 s).

**Ops:** the ternary encoder uses **`com.microsoft::MatMulNBits`** — an ONNX Runtime contrib op, CPU-provider-supported. The export author's own `config.json` states it verbatim: `"ternary_weights": "MatMulNBits 4-bit, block 128"`, and the card explains the encoding: *"The ternary encoder weights are stored as 4-bit MatMulNBits blocks that reproduce the -1/0/+1 values exactly"* with the source's fp16 group scales (block size 128 = the `group_size` in `ternary.json`).

**onnxruntime floor:** **`onnxruntime>=1.22`** — this is the export repo's OWN `requirements.txt` (`# Inference (transcribe.py): onnxruntime>=1.22 / numpy`), MEASURED. Exported with onnxruntime 1.30. **This box has onnxruntime 1.30.0 → satisfies the floor.** (The `1.22` floor is the author's declared inference floor for `transcribe.py`; it is the strongest primary number available short of reading the graph's `ir_version`, which I declined — see Method.)

**Is there a dense / no-quant variant?** Notably, **not in the repo.** The shipped encoder *is* the `MatMulNBits` pack. A **dense float32 "plain ONNX, 2.4 GB"** variant is documented as an *export option* (`export_onnx.py --bits 0`), alongside `--bits 2` (193 MB encoder) and `--accuracy-level 4` (int8 activations, ~2× faster). Producing it needs the Photon runtime (i.e. PyTorch). So "dense ONNX" is reproducible but **absent** — it is not a download-able alternative today.

A **second, independent export exists**: `mrfakename/parakeet-redux-ONNX` (created 2026-10-05, **23 downloads**, usedStorage 454,140,598 B) — same four graphs plus a **`decoder_joint-model.int8.onnx`**, tagged `webgpu`, backing the `mrfakename/parakeet-redux-webgpu` space (a static, in-browser WebGPU demo). Worth naming because it broadens the option space (see Q6).

### Q4 — Licence and redistribution

**Parakeet Redux is CC-BY-4.0, and so is the entire chain behind it:**

| artefact | licence | source |
|---|---|---|
| `nvidia/parakeet-tdt-0.6b-v3` (base) | `cc-by-4.0` | HF API, opened |
| `moondream/parakeet-redux` | `cc-by-4.0` | HF API cardData; card: *"License is CC-BY-4.0, same as the original."* |
| `eschmidbauer/parakeet-redux-onnx` | `cc-by-4.0` | HF API cardData |
| `Nairod785/parakeet-redux-gguf` | `cc-by-4.0` | HF API cardData |

**The OpenMDW-1.1 question does NOT apply to Parakeet Redux. It belongs to a different component.** From the local `stack-verification.md` (`:49-142`), OpenMDW-1.1 is the licence of `nvidia/nemotron-3.5-asr-streaming-0.6b` (`license:other` → OpenMDW-1.1) — Sotto's **streaming** model. Redux is a separate model under a separate licence. The brief (and the plan) ties the two together; they must be kept apart, because the two questions have different answers.

**Can the weights be BUNDLED in a shipped app?** Under CC-BY-4.0 — which permits redistribution and commercial use — **yes, provided the three CC-BY-4.0 conditions are met: (a) credit the author, (b) link the licence, (c) state that changes were made.** There is **no redistribution ban and no royalty**. Concretely: bundling `moondream/parakeet-redux` owes Moondream + NVIDIA a notice; bundling the ONNX export additionally owes a note that it is a third-party conversion (*"Neither moondream nor NVIDIA endorse this export"*) — same attribution, more names. **Bundling is a paperwork cost, not a legal blocker.** The `stack-verification.md` "download at first run dodges the redistribution clause" logic is an **OpenMDW/Nemotron** argument and does not describe redux.

The `transcribe.cpp` runtime (either build) is **MIT** — the fork's API record reports `license.spdx_id = "MIT"` — so bundling a built binary carries only the MIT notice.

### Q5 — Batch/offline vs streaming

**Parakeet Redux is an inherently offline (file/batch) model.** It is a full-context FastConformer encoder + TDT decoder; there is **no streaming flag** for it anywhere (it is absent from transcribe.cpp's per-family `streaming` table, and it carries a VAD *head* whose whole purpose is to cut a finished recording at pauses, not to emit incrementally). The card itself describes long audio as: *"Photon uses it to cut recordings at pauses into segments of at most 30 seconds."*

The word "streaming" appears only as **chunked re-decode in the vendor's client**: the release post shows `stream=True` and `atranscribe` for parakeet-redux, with the honest qualifier *"Live previews begin after four seconds of audio and are scheduled every two seconds after that; earlier text can change as more context arrives"* and *"Each update replaces the previous transcript; don't append it."* That is a batch model wrapped live over a growing window — not incremental decoding. **The correct mental model: offline transducer, optionally re-run over a sliding window.**

**For Sotto's stated use this is the right fit, not a compromise.** Sotto needs *"a canonical transcript afterwards"* (`README.md:54-55`) — a **POST-RECORDING** file pass, which M2 already scopes as *"Batch, not streaming"* (`roadmap.md:64-66`). Prior art agrees: Sotto's own R7 lineage and RealtimeSTT both pair a streaming model for the live box with a **Parakeet finalizer** for the authoritative text (`docs/oss-approaches-20261006.md:46`; `docs/audit/original-prompt-adjudication.md:85`). The built-in VAD head means the batch pass can take a whole recording without a hand-tuned segmenter.

### Q6 — A cheaper true path neither A, B nor C names

**Yes: use `onnx-asr` (istupakov) to consume the redux ONNX, instead of hand-writing option C's decode loop.** Option C's only genuinely non-trivial work item is *"the greedy loop over decoder_joint"*; `onnx-asr` **is** that loop, for NeMo TDT models, already written.

- **MEASURED (PyPI + docs):** `onnx-asr` 0.12.0, **MIT**, deps **numpy + onnxruntime** (`onnxruntime>=1.18.1`) — no torch, no transformers, no ffmpeg. *"Works on Windows, Linux, and macOS on x86 and Arm CPUs, with support for CUDA, TensorRT, CoreML, DirectML, ROCm, and WebGPU."* It supports the model type **`nemo-conformer-tdt`** — which is *exactly* the export's `config.json` `model_type` — plus `load_model(name, local_dir)`, VAD-based long-form, batch, timestamps and a CLI.
- **The export author himself documents the call** (primary, from the export's card): `onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", "path/to/parakeet-redux-onnx")`.
- **Why this is cheaper than C:** it removes option C's only real engineering (the TDT greedy decode + state threading + VAD segmentation, which is where a hand-rolled loop silently gets `blank_id`/duration handling wrong), and adds one MIT pure-Python dependency on top of the runtime already installed here (onnxruntime 1.30.0 ≥ any floor). **`[INFERENCE]`** that it runs the redux graphs *unchanged*: the export's filenames match the `istupakov/parakeet-tdt-0.6b-v3-onnx` layout that onnx-asr expects, and the author asserts it — but I did not execute it.
- **This is also consistent with what Sotto actually ships.** The plan's "no resident Python / C++ from Rust" framing is already obsolete in-tree: `docs/audit/doc-vs-code.md` R8 records that *the product IS Python* (`app/webview/run.cmd` starts `pythonw.exe sotto_webview.py`). A pure-Python MIT decoder is a smaller divergence from reality than a C++ runtime.

Two adjacent cheaper-than-they-look paths, named but not recommended yet: **(d) the WebGPU branch** — `mrfakename/parakeet-redux-ONNX` + ORT-web inside the WebView2 Chromium, i.e. **zero new runtime at all** (the app *is* a browser); unproven, cheap to explore. **(e) the vendor's Photon path** — the most "official" and the fastest (113× on 8 CPU cores), but it drags `kestrel`, which requires **torch≥2.8** and reports **telemetry** (`kestrel` PyPI description: it *"reports basic usage telemetry … model in use, your GPU type and memory, aggregate request/error and token counts, your machine's hostname, and timestamps"*) — a poor fit for a local transcription product even though *"prompts, images, and model outputs are never sent."*

---

## Guarantee inventory

*(Q2 is a possible/impossible question — "can any released runtime load these weights?" — so every claimant of that property is enumerated and each is kept or killed with a named reason. An unlisted claimant is a hole; the row marked NOT ADDRESSED keeps that part OPEN.)*

| claimant of "can load Parakeet Redux ternary weights" | state | named reason |
|---|---|---|
| **Photon / Kestrel** (`pip install moondream` → `kestrel`) | **ALIVE** | card: *"reads the packed weights directly"*; `moondream` 2.6.1 on PyPI requires `kestrel==0.9.1`; kestrel's own docs list `parakeet-redux` and say it *"runs on the CPU and on Apple silicon as well as CUDA"*. `[INFERENCE]` on Windows-CPU specifically: kestrel's Requirements section names *"NVIDIA GPU on … Windows x86_64"* and *"Apple Silicon Mac"*, while the package docs say *"CPUs for supported models"* and document `OMP_WAIT_POLICY` *"when transcribing on the CPU"* — so CPU transcription is documented, but CPU-on-Windows is not spelled out. |
| **ONNX Runtime** (via the `eschmidbauer` / `mrfakename` export, `com.microsoft::MatMulNBits`) | **ALIVE** | `requirements.txt` declares `onnxruntime>=1.22`; box has **1.30.0** (Oracle AR1 PASS); the export was made with ORT 1.30; `MatMulNBits` is a documented ORT contrib op on the CPU EP. |
| **`onnx-asr` (istupakov)** as the decoder over that ONNX | **ALIVE** | MIT; model type `nemo-conformer-tdt`; the export author documents the exact call. `[INFERENCE]` on running *these* graphs unmodified (not executed). |
| **transcribe.cpp fork `NairoDorian` (`GGML_TYPE_TQ1_G128`)** | **ALIVE-BUT-UNBUILT** | the `0003` patch exists (patches/ggml); but the fork has **zero releases** (Oracle AR3 PASS) → clone + CMake build from source, one maintainer, 0 stars. |
| **transcribe.cpp upstream `handy-computer`** | **DEAD for TQ1** | no `0003` patch at `main` (Oracle AR2 PASS); `parakeet-redux` absent from its family table (`stack-verification.md:371-376`); Windows prebuilts exist but cannot open the TQ1 files. |
| **HuggingFace `transformers` `ParakeetForTDT` + PyTorch** | **ALIVE (generic)** | the ternary author used it for reference dumps (`QUANTIZATION.md` §5.1) — so transformers can run redux *dequantized*; it is a PyTorch path, heavy, and not a shipping candidate. |
| **`parakeet-mlx` (Apple)** | **DEAD for redux** | the card's benchmark row `parakeet-mlx fp32 2.51 GB` is a different (dense) model; no ternary support claimed anywhere. |
| **ORT-web / WebGPU in the browser** | **ALIVE-SPACE, UNVERIFIED** | the `mrfakename/parakeet-redux-webgpu` static space exists and ships its own ONNX; no primary statement that it is correct or that WebView2 exposes WebGPU. Kept as a claimant, marked unproven. |
| **sherpa-onnx** | **NOT ADDRESSED** | I did not probe whether sherpa-onnx can consume this ONNX / `MatMulNBits` encoder. Per rule 13 an unaddressed row keeps the "any released runtime?" verdict **OPEN at the edge** — but the verdict is already satisfied ALIVE by Photon + ORT, so this row does not change the answer, only the completeness. Cost to close: one docs/repo fetch. |

---

## Theory space

*Quantified where a number exists; each theory carries its own falsifier.*

**T1 — Option A: build the `NairoDorian` fork and ship the `TQ1_G128` GGUF.** Mechanism: clone + CMake; consume `Nairod785/parakeet-redux-gguf` (TQ1_F16 **179,312,288 B** / TQ1_Q8_0 **159,121,504 B** / TQ1_Q4_K **156,696,672 B**); call `transcribe_run` and stamp `producer:'redux'`. Pros: the only path that is literally "Redux ternary", self-contained native binary, Windows prebuild of *upstream* exists as a fallback shape. Cons: **no release artifact to download** (build from source); one maintainer, 0 stars, pre-1.0 ABI; and at runtime the fork re-lays TQ1 to Q4_0/Q2_0 anyway, so the "ternary speed" is partly not ternary. Cost: **HIGH** (~0.5 d clone+build + vendor a pre-1.0 binary + a Rust/C binding). **Falsifier:** if `NairoDorian/transcribe.cpp` publishes a tagged release whose `patches/ggml/` carries `0003`, the "no release" objection dies (check: `GET /repos/NairoDorian/transcribe.cpp/releases`).

**T2 — Option B: upstream transcribe.cpp + a non-Redux Parakeet quant.** Mechanism: download `transcribe-native-0.3.1-windows-x86_64-cpu-vulkan.tar.gz` (exists), pair with an upstream-supported Parakeet quant. Pros: **lowest engineering** — binary + a GGUF + a call site; MIT; a real release. Cons: **it changes the product** — the field named "History · Redux" would name a model that is not Redux. Cost: **LOW to ship, MEDIUM product redefinition** (owner call). **Falsifier:** if the owner decides "Redux" is a UI label meaning "the canonical pass, whatever engine", T2 becomes the cheapest correct answer and T1/T3 lose their raison d'être.

**T3 — Option C: the `eschmidbauer` ONNX on the installed onnxruntime.** Mechanism: download ~436 MB; write the greedy TDT loop; stamp `producer:'redux'`. Pros: **zero new runtime** (ORT 1.30.0 present, floor 1.22 satisfied); it is the *actual Redux model*; the README already names this repo (`README.md:30-32`). Cons: third-party export with **88 downloads / 1 like**; the decode loop is real engineering; a single maintainer. Cost: **LOW-MEDIUM** (~436 MB + the loop). **Falsifier:** if the shipped `MatMulNBits` encoder fails to load or mis-decodes on this box's ORT, C collapses to "regenerate a dense export", which needs PyTorch — a hidden cost (Method §4).

**T4 — `onnx-asr` over the same ONNX (the Q6 shortcut).** Mechanism: as C, but the loop is `onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", "<dir>")`. Pros: **deletes C's only hard part**; MIT, pure-Python, Windows-supported, same installed runtime. Cons: adds a dependency; `[INFERENCE]` that it runs these graphs unchanged. Cost: **LOW** (one pip dep + a call site). **Falsifier:** `pip install onnx-asr; python -c "import onnx_asr; m=onnx_asr.load_model('nemo-parakeet-tdt-0.6b-v3','<redux-onnx-dir>'); print(m.recognize('a.wav'))"` — if it errors or garbage-decodes, T4 dies to T3.

**T5 — Vendor Photon/Kestrel.** Mechanism: `md.photon("moondream/parakeet-redux", device="cpu")`. Pros: **official**, reads the packed weights natively, **113× real-time** (fastest measured), built-in VAD segmentation. Cons: **requires torch≥2.8** (heavy) and **reports telemetry** (hostname, GPU, timestamps) — wrong shape for a local privacy product. Cost: **MEDIUM-HIGH** (heavy dep, telemetry policy). **Falsifier:** kestrel dropping torch from the CPU path, or a documented "no-telemetry" build, would make T5 competitive.

**Ranked by evidence, not preference:** T4 ≈ T3 (same model, T4 less code) > T2 (cheapest but renames the thing) > T5 (best runner, worst dependency) > T1 (only literal ternary GGUF, hardest to ship).

---

## Evidence

*Freshness = the date I opened the source, or the source's own stated date. Confidence ∈ {observed, inference, hypothesis}.*

| Finding | Source | Freshness | Confidence |
|---|---|---|---|
| `moondream/parakeet-redux` is a ternary derivative of `nvidia/parakeet-tdt-0.6b-v3` | HF API `moondream/parakeet-redux` (`model_type":"parakeet_tdt"`); model card line 1 | opened 2026-10-07; card dated ~2026-09-22 | observed |
| Ternary packing is 5 trits/byte, base 3, group_size 128, `w=scales*(code-1)` | `moondream/parakeet-redux/raw/main/ternary.json` | opened 2026-10-07 | observed |
| 264 ternary modules = 603,979,776 weights; 23,290,911 dense | `Nairod785/parakeet-redux-gguf/QUANTIZATION.md` §1 | opened 2026-10-07 | observed |
| Weights 1.2 GB → 178 MB; WER table 6.26→6.55 / 11.62→10.56 / 6.72→9.04 / 2.71→2.51 | model card | opened 2026-10-07 | observed |
| **Vendor runtime Photon reads the packed ternary weights directly** | model card, Usage §; `moondream` PyPI 2.6.1 `requires kestrel==0.9.1` | opened 2026-10-07 | observed |
| `kestrel` requires `torch>=2.8` and reports telemetry | PyPI `kestrel` 0.9.2 description | opened 2026-10-07 | observed |
| **Upstream `patches/ggml` at `main` has no `0003`** | GitHub API contents `handy-computer/transcribe.cpp/patches/ggml`; Oracle AR2 PASS | 2026-10-07 | observed |
| **Fork `NairoDorian/transcribe.cpp` has ZERO releases** | GitHub API releases; Oracle AR3 PASS | 2026-10-07 | observed |
| Fork is MIT, `fork:true`, parent `handy-computer`, 0 stars, pushed 2026-10-06 | GitHub API repo metadata | 2026-10-07 | observed |
| Upstream v0.3.1 ships Windows prebuilts (cpu-vulkan, cuda) | GitHub API releases assets | released 2026-10-04 | observed |
| `TQ1_G128` = ggml id 96, 1.75 bpw, one scale per 128; fork re-lays to Q4_0/Q2_0 at load | `QUANTIZATION.md` §2–§3 | opened 2026-10-07 | observed |
| ONNX export = 4 graphs (preprocessor/encoder/decoder_joint/vad), NeMo tensor names | `eschmidbauer/parakeet-redux-onnx` card + `config.json` | opened 2026-10-07 | observed |
| Ternary encoded as `com.microsoft::MatMulNBits` 4-bit, block 128 | export `config.json` (`"ternary_weights"`); card | opened 2026-10-07 | observed |
| Export decode = greedy TDT, `outputs[B,1,1,8198]` = 8193 logits + 5 durations, blank 8192 | export card | opened 2026-10-07 | observed |
| **Export's own inference floor is `onnxruntime>=1.22`; box has 1.30.0** | export `requirements.txt`; Oracle AR1 PASS | opened 2026-10-07 | observed |
| Dense float32 (`--bits 0`, 2.4 GB) is a documented export option, NOT shipped | export card (Export §) + siblings list; Oracle AR4 PASS | opened 2026-10-07 | observed |
| Whole chain is CC-BY-4.0 (base, redux, ONNX, GGUF) | HF API cardData for all four repos | opened 2026-10-07 | observed |
| **OpenMDW-1.1 is the Nemotron streaming model's licence, not redux's** | `stack-verification.md:49-142` (license:other → OpenMDW-1.1) | in-repo | observed |
| Redux is batch/offline; long audio is VAD-segmented to ≤30 s | model card Notes; vendor release post | opened 2026-10-07 | observed |
| Vendor post shows `stream=True`/`atranscribe` for redux — replacement snapshots, not deltas | vendor post (moondream.ai/blog/…-redux-and-ultra) | dated 2026-09-22; opened 2026-10-07 | observed |
| `onnx-asr` 0.12.0 is MIT, numpy+onnxruntime only, Windows-supported, model type `nemo-conformer-tdt` | PyPI `onnx-asr`; istupakov docs | opened 2026-10-07 | observed |
| `onnx-asr` runs the redux ONNX unchanged | export card (author's documented call) | opened 2026-10-07 | inference |
| A second export exists: `mrfakename/parakeet-redux-ONNX` (+ int8 decoder, webgpu) | HF API | created 2026-10-05; opened 2026-10-07 | observed |
| Prior measured cost on this box: Parakeet Redux CUDA RTF **0.769** vs Parakeet v3 int8 CUDA **0.256** | `docs/audit/original-prompt-adjudication.md:85` (manager scratch, outside `H:/sotto`) | prior lane | inference (not re-measured by me) |
| Sotto HISTORY accepts only `producer:'redux'`, refuses `'live'`; repo HEAD `11df66e` | `app/electron/history-source.js:29-30,48-51`; `git log -1` | 2026-10-07 | observed |

---

## Checkboxes (research plan, self-graded)

- [x] read `H:/sotto/README.md` — the plan names `moondream/parakeet-redux` + `transcribe.cpp` (`:20-32,54-55`) and says the ternary/`tq1_g128` claim
- [x] read `H:/sotto/docs/roadmap.md:64-67` — M2 is explicitly *"Batch, not streaming"*, confirming the batch fit
- [x] read `H:/sotto/docs/stack-verification.md:1-142,366-410` — OpenMDW-1.1 belongs to Nemotron, `tq1_g128` needs a fork
- [x] read `H:/sotto/_main/receipt-20261007-parakeet-redux-path.md` — prior inventory + the three options
- [x] read `docs/audit/ao-vivo-vs-redux.md`, `historico-vs-redux.md`, `oss-approaches-20261006.md`, `original-prompt-adjudication.md:85` (prior art, not re-derived)
- [x] opened HF API `moondream/parakeet-redux` — confirms `parakeet_tdt`, CC-BY-4.0, sha `2bf12860…`
- [x] opened `ternary.json` — confirms the 1.58-bit packing (5 trits/byte, base 3, group 128)
- [x] opened the model card — confirms "1.58-bit version of parakeet-tdt-0.6b-v3", Photon, WER table
- [x] opened HF API `nvidia/parakeet-tdt-0.6b-v3` — base licence `cc-by-4.0`
- [x] opened HF API + `QUANTIZATION.md` for `Nairod785/parakeet-redux-gguf` — TQ1_G128, sizes, fork
- [x] ran GitHub API releases for `NairoDorian/transcribe.cpp` — **`[]`, zero releases**
- [x] ran GitHub API releases for `handy-computer/transcribe.cpp` — v0.3.1, Windows prebuilts listed
- [x] ran GitHub API contents `patches/ggml` — only `0001`,`0002`, **no `0003`**
- [x] opened HF API + card + `requirements.txt` + `config.json` for `eschmidbauer/parakeet-redux-onnx` — 4 graphs, `MatMulNBits` 4-bit block 128, `onnxruntime>=1.22`
- [x] opened HF API `mrfakename/parakeet-redux-ONNX` — second export, int8 decoder, webgpu
- [x] opened PyPI `onnx-asr` + istupakov docs — MIT, `nemo-conformer-tdt`, Windows (Q6 path)
- [x] opened PyPI `moondream` + `kestrel` — Photon path requires torch; telemetry
- [x] opened the vendor release post — redux supports files/live/timestamps via Photon
- [x] **executed** the `## Oracle` script once — rc=0, GREEN (rule 15)
- [x] re-verified live repo state at write time — HEAD `11df66e`; `history-source.js` guard present; `rerun()` present
- [ ] enumerate the ONNX `opset`/`ir_version` by loading the graphs — **DEFERRED: requires downloading 344 MB, forbidden by the brief**
- [ ] probe sherpa-onnx as a consumer — **DEFERRED: outside the three named options; cheap (one docs fetch)**
- [ ] execute `onnx-asr` on the redux ONNX — **DEFERRED: requires downloading ~436 MB + a pip install, forbidden by the brief**

---

## ABSENT

Searches that returned nothing, with their tri-state, so nobody "fixes" a phantom:

| searched for | probe | tri-state | result |
|---|---|---|---|
| a **dense / no-quant ONNX** shipped in `eschmidbauer/parakeet-redux-onnx` | HF API siblings; Oracle AR4 | **ok** (API returned 200 with the full list) | **absent** — only `MatMulNBits` graphs ship; `--bits 0` dense is a documented *export option*, not a file |
| a **release** of the fork that carries `TQ1_G128` | GitHub API `NairoDorian/transcribe.cpp/releases`; Oracle AR3 | **ok** (200) | **absent** — `[]` |
| `0003-tq1` patch in **upstream** `patches/ggml` | GitHub API contents; Oracle AR2 | **ok** (200) | **absent** — only `0001`, `0002` |
| any **streaming** claim for the redux model itself | model card + vendor post + `config.json` | **ok** (all read) | **absent** as a model property; present only as client-side chunked re-decode |
| the redux model in **transcribe.cpp's** upstream family table | `stack-verification.md:371-376` | **ok** (in-repo read) | **absent** |
| `moondream/parakeet-redux` weights/binaries on the Sotto disk | prior receipt (`find`, `ls`, `grep`) | **ok** (per prior lane) | **absent** — HISTORY empty by design |

**Deliberately-not-probed declines (rule 13) and the cost to close each:** (1) binary/byte-level ONNX graph inspection — cost: one download + `onnx.load`; (2) executing any engine — cost: 180–436 MB download + a build or pip install, forbidden; (3) reading the CC-BY-4.0 legal text clause-by-clause — cost: one fetch; (4) sherpa-onnx support probe — cost: one fetch.

---

## Recommendation

**Verdict: Parakeet Redux is real, its ternary line is real and vendor-loadable, and the cheapest truthful path to a canonical `producer:'redux'` line is the ONNX export consumed through `onnx-asr` on the already-installed onnxruntime — i.e. option C, minus its only hard part.** The premise that "the ternary weights need a private fork" is false; the fork is needed only for the GGUF packaging, and that path has no release artifact at all. Reason: option C+T4 uses the *actual Redux model*, adds only an MIT pure-Python dependency, runs on the runtime already present (1.30.0 ≥ floor 1.22), and matches Sotto's real stack (Python + WebView2). Option A is the only literal-ternary-GGUF path and the one that costs a from-source build of a 0-star fork. Option B is cheapest but renames the artefact. **Confidence: 82/100.** What holds it back from higher: the ONNX path (C/T4) was NOT executed here (forbidden), the export has 88 downloads, and kestrel's Windows-CPU support is only partially specified.

---

## Directly actionable (A0/A1)

Facts the manager can act on now — **without downloading anything**:

1. **The `producer:'redux'` gap is closable with zero new runtime.** The batch engine the plan wants is `moondream/parakeet-redux` via the ONNX export, running on onnxruntime **1.30.0** already installed (floor 1.22). Proposed card: *"SottoBatchRedux — wire `onnx-asr` (or a minimal TDT loop) over a local redux ONNX dir; emit `producer:'redux'` on the canonical line; measure RTF + resident RSS on `sample1.flac`."* Acceptance: a real line in the HISTORY feed, and the existing `_main/live-vs-history-source-oracle.js` *"`producer:'redux'` arm"* (130 lines) turns into a real feed.
2. **Correct the record in-tree.** `README.md:22` claims `transcribe.cpp` "runs **both** models as GGUF … `tq1_g128`". That is **false for the upstream release** (no `0003` at `main`, no redux in the family table) — the local `docs/stack-verification.md` already says so; README should be aligned so the next lane does not re-derive it. Proposed card (docs-only, one line + a pointer).
3. **Separate the two licence questions.** Redux is **CC-BY-4.0** end-to-end (base `nvidia/parakeet-tdt-0.6b-v3` included) → bundle-able with attribution. **OpenMDW-1.1 belongs to the Nemotron streaming model, not to Redux.** Any doc that fuses them should be split. Proposed card (docs-only).
4. **Name the label risk.** If HISTORY is allowed to carry a Parakeet that is *not* Redux, the guard in `history-source.js` (`CANONICAL_PRODUCER='redux'`) becomes a lie. Either keep the literal model, or rename the producer tag to what it actually is (e.g. `canonical-tdt`). Proposed card (one-line decision, see A2).

---

## Decisions that are YOURS (A2+)

- **A2.1 — literal Redux, or "any canonical pass"?** *RECOMMENDATION: literal Redux via C/T4*, because the field's name and the guard already say Redux, and the cost is one ONNX download + a decoder. If you instead accept "any batch Parakeet", option B becomes the cheapest (upstream Windows prebuilt + an upstream quant) but the label must change.
- **A2.2 — bundle the weights, or fetch at first run?** *RECOMMENDATION: bundle.* CC-BY-4.0 permits it; the cost is the attribution notice in the installer, not a licence gate. Fetch-at-first-run only "buys" anything for the OpenMDW/Nemotron model, which is a different component.
- **A2.3 — accept a Python dependency in the batch path?** *RECOMMENDATION: yes* (`onnx-asr`, MIT, numpy+onnxruntime). The plan's C++-from-Rust goal is already obsolete in-tree (R8: the app IS Python). If a *native* batch engine is a hard requirement, then A2.3 flips to A2.4.
- **A2.4 — if a native engine is mandatory: fork-build (A) vs Photon (T5).** *RECOMMENDATION: neither, today.* A has no release; T5 drags torch and reports telemetry. Revisit only if A publishes a tagged release or kestrel drops torch/telemetry.

---

## Starshot

*Assume nothing is impossible.* The constraint everyone is working around is "one model, one pass, one runtime". Remove it:

- **Build the two-pass product the original plan actually describes, with Redux as the finisher.** Nemotron streaming paints the live box; on stop, the same recorded PCM is handed to a **Redux ONNX pass** that produces the canonical line — exactly RealtimeSTT's proven pattern (`docs/oss-approaches-20261006.md:46`). Neither model is resident during idle, and the batch pass is a single file decode.
- **Then delete the need for a decoder at all:** `onnx-asr` already implements NeMo TDT greedy decode + VAD; wire it, and the "write the greedy loop" work item disappears. The end state is: **a ~436 MB model directory + one pip dep, and a canonical line that stamps its own provenance.**
- **The genuinely cheap experiment toward it:** a *dense* export (`--bits 0`) exists in principle but not in the repo. If the MatMulNBits encoder ever disagrees with the box's ORT, the escape hatch is one command the export author documents (`python export_onnx.py --bits 0`) — **but it needs PyTorch.** So the first cheap experiment is the opposite: prove the *shipped* MatMulNBits graph loads and decodes on ORT 1.30.0 before writing anything else.

---

## Scale-128 line

At **N=128** concurrent transcriptions the arithmetic stops being about WER and starts being about memory and scheduling:

- **Model residency is the multiplier.** Sixteen 436 MB ONNX sessions is ~7 GB of weights before activations; the export's own note says *"Recordings over 30 s are cut at pauses"*, so each of 128 workers holds a ≤30 s segment plus decoder state. What must exist first: **one shared session pool**, not 128 sessions — the ONNX export is a single-utterance graph (`B` is a real batch dim in the preprocessor/encoder, so batching is possible, but the decoder_joint loop is per-utterance and serialises).
- **What breaks first: CPU decode.** The card's own CPU numbers are 113× (8 cores) at ONE utterance; 128 parallel utterances do not scale linearly, and `kestrel`'s docs already warn *"set `OMP_WAIT_POLICY=passive` before torch loads … or torch's idle OpenMP workers spin on the cores"* — a 128-way fan-out on shared OpenMP is a known thrash. What must exist first: **a queue with a bounded worker count** identical to the idle-contract principle already in `roadmap.md`.
- **The `producer` contract scales cleanly:** the guard is a pure predicate, so 128 producers stamping `redux` is O(1) per line. The scaling risk is *disk*, not the guard — the history store is one markdown file per hour, and 128 streams writing it is the failure mode `docs/audit/historico-vs-redux.md` already documents at one stream.

---

## Critic pass

**Strongest attack on my recommendation:** *"You picked C+T4 on paper and admitted you never ran it. The export has 88 downloads and one maintainer — a third-party conversion of a third-party ternary re-quant, and you are proposing to make it the canonical transcript engine for a product. Meanwhile Photon is the vendor's own runtime, reads the exact packed weights, is 113× faster than anything you measured, and you dismissed it for 'telemetry' and a torch dependency — both of which are policy, not capability. The owner asked what is TRUE, and what is true is that the official path exists and works; your shortcut is the unproven one."*

**My reply:** the attack is half-right and I am recording it as the live risk, not rebutting it away. Correct: T4 is unexecuted, and Photon is the only path I can call *observed-works* from a primary source, because the vendor both writes and runs it. But the brief's own constraint is what rules Photon out for the *batch* slot: `kestrel` requires **torch≥2.8**, and the product's stated contract is that **no model is resident when idle** (`roadmap.md` idle table) — a torch-bearing Python runtime is the single heaviest thing you can leave parked, and it reports telemetry from a product whose premise is *local*. So the honest ranking is not "C beats Photon"; it is "**Photon is the most proven runner and the worst fit for the product's own idle contract**, and C+T4 is the unproven runner that fits it." The decision the owner should make is that trade, explicitly — see A2.1/A2.3. And the single most useful cheap action remains the one I could not take: **run C/T4 once**, which either promotes it to `observed` or kills it to T3/T5.

**Second attack (accepted):** I leaned on `stack-verification.md` for the OpenMDW separation rather than reading the Nemotron card directly this session. That is a citation-of-a-citation for one row; it is corroborated by the model card's `license:other` in the local doc, and it does not touch the redux answer.

---

## Oracle

One re-runnable check that goes **RED** if the central claim is wrong. Central claim: *the ternary line needs no private fork to be loaded by a released runtime, and the ONNX export runs on the already-installed onnxruntime.* It was **executed once** (rule 15), rc=0.

```bash
cd H:/sotto && py -3 -c "
import json, urllib.request
def get(u): return urllib.request.urlopen(u,timeout=30).read().decode('utf-8','replace')
arms=[]
try:
    import onnxruntime as o
    v=[int(x) for x in o.__version__.split('.')[:2]]
    arms.append(('AR1 installed onnxruntime >= export floor 1.22', v>=[1,22], 'onnxruntime '+o.__version__))
except Exception as e:
    arms.append(('AR1', False, 'import failed: %r'%e))
try:
    d=json.loads(get('https://api.github.com/repos/handy-computer/transcribe.cpp/contents/patches/ggml'))
    names=[x['name'] for x in d]
    arms.append(('AR2 no 0003-tq1 patch upstream', not any('tq1' in n for n in names), ','.join(names)))
except Exception as e:
    arms.append(('AR2', None, 'fetch failed: %r'%e))
try:
    d=json.loads(get('https://api.github.com/repos/NairoDorian/transcribe.cpp/releases'))
    arms.append(('AR3 fork has zero releases', len(d)==0, 'n=%d'%len(d)))
except Exception as e:
    arms.append(('AR3', None, 'fetch failed: %r'%e))
try:
    d=json.loads(get('https://huggingface.co/api/models/eschmidbauer/parakeet-redux-onnx'))
    names=[x['rfilename'] for x in d['siblings']]
    arms.append(('AR4 export ships MatMulNBits encoder, not a dense graph', 'encoder-model.onnx' in names and not any('dense' in n.lower() for n in names), ','.join(names)))
except Exception as e:
    arms.append(('AR4', None, 'fetch failed: %r'%e))
for n,ok,d in arms: print(('PASS' if ok else ('UNVERIFIED' if ok is None else 'FAIL')), n, '::', d)
print('ORACLE', 'GREEN' if all(ok for _,ok,_ in arms) else 'RED')
"
```

**Measured output (2026-10-07, rc=0):**

```
PASS AR1 installed onnxruntime >= export floor 1.22 :: onnxruntime 1.30.0
PASS AR2 no 0003-tq1 patch upstream :: 0001-fix-threadpool-oversubscription.patch,0002-backend-reg-filter.patch
PASS AR3 fork has zero releases :: n=0
PASS AR4 export ships MatMulNBits encoder, not a dense graph :: .gitattributes,.gitignore,README.md,config.json,decoder_joint-model.onnx,encoder-model.onnx,export_onnx.py,preprocessor.onnx,requirements.txt,transcribe.py,vad-model.onnx,vocab.txt
ORACLE GREEN
ORACLE_EXIT=0
```

RED is expected the moment any of these flips: upstream publishes a `0003` patch (AR2), the fork publishes a release (AR3), the box's onnxruntime drops below 1.22 (AR1), or the export repo swaps its shipped encoder for a dense graph (AR4). AR2/AR3/AR4 need network; AR1 is local.

---

## Open risks / follow-ups

- **Freshness / expiry of my own claims.** Everything external here was read **2026-10-07**. The mutable facts — fork releases, upstream `patches/ggml`, the export's sibling list, download counts — are exactly what the Oracle re-checks. Re-run the Oracle before acting on T1 or T3/T4.
- **Unexecuted central path (the big one).** C/T4 was not run. It is the difference between `observed` and `inference` for the recommendation. One download + one script closes it.
- **kestrel on Windows-CPU is partially specified.** Photon's Requirements list Windows only for NVIDIA GPUs; CPU transcription is documented but CPU-on-Windows is not spelled out. If Photon becomes a candidate, this needs its own probe.
- **`sherpa-onnx` unaddressed** (see Guarantee inventory) — could add a second ONNX consumer, or could be a dead end; unprobed.
- **The fork is *active* (pushed 2026-10-06).** Its `0003` may yet land upstream; that would flip AR2/AR3 and could reopen option A as the cheap path. This is the fork's live risk to watch.
- **`WER 9.04 %` in noise is the product risk.** For Sotto (system audio: music, calls, games) noise robustness matters more than the FLEURS win. `parakeet-ultra` (5.82 % noise) is its sibling — GPU-oriented today, but the number is the honest warning.
- **Label honesty.** If the batch engine chosen is not literally Redux, `history-source.js`'s `CANONICAL_PRODUCER='redux'` must change with it, or the guard becomes a lie (see A1.4).

---

## SELF-AUDIT

- **protocolos em falta** — faltou-me um protocolo explícito para **duas fontes primárias que se contradizem**, e resolvi-o sozinho: o `receipt-20261007-parakeet-redux-path.md` tratava a Opção C como "o caminho mais pequeno" e a Opção A como "forquilhada", mas nenhum dos dois documentos *internos* separava as **duas rotas ternary** (Photon sobre os pesos `thrush` **vs** o fork para o GGUF `TQ1_G128`). A pergunta 2 do brief é exactamente essa separação e nenhuma fonte local a tinha. Faria diferente: se houver um protocolo de "premissa load-bearing do brief tem de ser re-medida contra fonte primária, não herdada do receipt", tê-lo-ia citado em vez de o inferir da regra 5.
- **verificacao adicional** — corri a barata: **executei** o meu oráculo (rc=0, GREEN) em vez de o deixar por correr, e confirmei o estado vivo do repo (`git log -1` = `11df66e`, a guarda em `history-source.js`, o `rerun()` no worker). A que **NÃO** corri e é a única que fecharia o centro da recomendação: descarregar ~436 MB e correr o ONNX/T4 — **proibida pelo brief**. Custo se fosse permitida: 1 download + 1 script; elevaria C/T4 de `inference` a `observed`.
- **checkboxes novas** — MECÂNICO: *antes de tratar "runtime X não suporta Y" como facto herdado, correr a sonda que separa as DUAS empacotagens — para este caso,
  `py -3 -c "import json,urllib.request as u; print([x['name'] for x in json.load(u.urlopen('https://api.github.com/repos/handy-computer/transcribe.cpp/contents/patches/ggml'))])"`
  tem de NÃO mostrar `0003` E `json.load(u.urlopen('https://api.github.com/repos/NairoDorian/transcribe.cpp/releases'))` tem de dar `[]`.* RED input: se `0003` aparecer, a afirmação "só o fork carrega TQ1" fica RED e a Opção A reabre. E: *toda afirmação de licença tem de nomear QUAL componente — a fusão Redux/OpenMDW que este brief herdou é o defeito que a checkbox previne.*
- **review por outro subagente** — **sim-com-escopo**: (a) atacar a escolha **C+T4 sobre Photon** — eu próprio a deixei como risco vivo no `## Critic pass`; um reviewer independente que valorize "fonte oficial > shortcut não-corrido" pode inverter a recomendação; (b) confirmar na `eschmidbauer/parakeet-redux-onnx` que `onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", dir)` é o mecanismo documentado e não uma leitura minha (o card mostra-o). **Não** vale re-rever o inventário (todas as linhas têm fonte aberta e o oráculo faz o re-check mecânico).
- **gate-doubt**:
  - **verde-de-verdade:** o `ORACLE GREEN` é real: as quatro arms foram **executadas** neste box sobre fontes vivas (GitHub API + HF API + `import onnxruntime`), e AR1 é uma medição local. **Um verde que eu DESCONTO:** AR2/AR3/AR4 leem APIs de TERCEIROS que mudam — um verde de hoje não é prova de amanhã; por isso o oráculo é re-corrido, não citado.
  - **falta-no-gate:** nada no oráculo verifica o que a **recomendação** depende — que o ONNX `MatMulNBits` **realmente carrega e decodifica** neste ORT 1.30.0. Cenário que atravessa: se o encoder falhar a carregar, a minha recomendação C/T4 morre e todo o oráculo continua GREEN (mede a existência do ficheiro, não a sua usabilidade). Nomeado.
  - **gate-melhor:** MECÂNICO: acrescentar ao oráculo uma arm que faça `onnxruntime.InferenceSession` sobre o encoder e devolva RED se levantar. Comando: `py -3 -c "import onnxruntime as o; o.InferenceSession(r'<dir>/encoder-model.onnx',providers=['CPUExecutionProvider'])"`. RED input: qualquer excepção (op em falta, IR demasiado novo). **Não** o escrevi porque a arm EXIGE o ficheiro de 344 MB que o brief proíbe descarregar — fica nomeado, dono: quem tiver o ficheiro em disco (a lane que fizer o download).
- **confianca** — **alta** no núcleo factual (todas as linhas da tabela têm fonte primária aberta esta sessão + oráculo executado): identidade Redux, packing 1.58-bit, fork sem release, upstream sem `0003`, export de 4 grafos com `MatMulNBits`, piso ORT 1.22, licença CC-BY-4.0 em toda a cadeia, natureza batch. **média** na RECOMENDAÇÃO (C/T4 não corrido; export de terceiro com 88 downloads; kestrel Windows-CPU só parcialmente especificado).
- **nao verificado** — (1) **o motor batch a correr** — nenhum peso/ONNX/GGUF descarregado ou executado (proibido); (2) o `opset`/`ir_version` reais dos grafos ONNX (só li o `config.json` e o card, não os grafos); (3) `onnx-asr` sobre as grafos redux (documentado pelo autor, não executado); (4) `sherpa-onnx` como consumidor (não sondado); (5) o texto legal da CC-BY-4.0 cláusula a cláusula; (6) a telemetria/hostname do `kestrel` em execução (lida da descrição, não observada); (7) a minha própria afirmação sobre a forma do ficheiro do HISTORY (guard) — lida do código, não exercida nesta lane.
- **SELF-AUDIT-LINT** — `bash I:/!manager/scripts/self-audit-lint.sh H:/sotto/_main/research-parakeet-redux.md` was **NOT run**: every attempt this turn was refused by the `THEORIST-SEAL` channel gate, which demanded dispositions of successive I:/!manager theorist passes (05-26Z/05-22Z/05-03Z) that belong to the manager-orchestrator seat, not to this sotto-scoped lane. **UNVERIFIED** for that reason, not for a missing section. The CACHE/PRICE block below WAS produced (rc=0).

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh ParakeetReduxResearch` — **rc=0**. Output VERBATIM (`> G:/Temp/parakeet-redux-research/cache.txt`), reproduced unedited; the one long `partition sums to …` segment is cut by the console at `…` exactly where shown below.

```
## CACHE/PRICE
- task/agent: ParakeetReduxResearch
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\ParakeetReduxResearch.jsonl
- cache: read=2594688 write=0 hit=93.4573% (cache-read / input+cache-read); universe: 22 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\ParakeetReduxResearch.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=20 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 22 of…
- when-failed: break_items=3; WHEN=2026-10-07T05:44:37.351000+00:00 | break_items=3; WHEN=2026-10-07T05:44:37.888000+00:00 | break_items=2; WHEN=2026-10-07T05:46:43.411000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 126371 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'ParakeetReduxResearch']; window: 2026-10-07T05:44:37.351000+00:00..2026-10-07T05:46:43.411000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791351877351 | session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351877888 | session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=deepseek-flash model=deepseek-flash item_index=101; turn_id=1791352003411 (state=RESOLVED-BREAKS-OMP; population: 3 of 126371 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'ParakeetReduxResearch']; window: 2026-10-07T05:44:37.351000+00:00..2026-10-07T05:46:43.411000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-07T05:49:07.556861+00:00
- usage rows: 22
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 181648
- output tokens: 41171
- cache-read tokens: 2594688
- cache-write tokens: 0
- hit ratio: 93.4573% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=20 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 22 of 22 matched usage rows
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 3 of 126371 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'ParakeetReduxResearch']; window: 2026-10-07T05:44:37.351000+00:00..2026-10-07T05:46:43.411000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-07T05:44:37.351000+00:00; WHERE session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791351877351
  - break_items=3; WHEN=2026-10-07T05:44:37.888000+00:00; WHERE session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351877888
  - break_items=2; WHEN=2026-10-07T05:46:43.411000+00:00; WHERE session_id=01a114e4-6a19-70cc-8408-e4105fea1c2b provider=deepseek-flash model=deepseek-flash item_index=101; turn_id=1791352003411
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Note: `verdict: UNKNOWN` is the instrument's own honest fail-closed output (no task-level acceptance verdict is stored), reproduced as-is rather than replaced by a number.

---

## SELO DO DONO (pendency received while this lane ran)

Two external governors are RED (`observer`, `theorist-delta-guard`) and the seal asked this seat to close them or name the owner. **They are NOT this seat's to close, and I did not attempt it** (brief: *"trabalha só no sotto"*, no writes to I:/!manager or the omp tree):

- **`observer` (VERMELHO-DAEMON-STALE)** — dono `G:/superharness/scripts/observer.sh` (daemon). The required closure is a **restart of the daemon from the shell that owns its pid**. Owner of the capability: the **SuperHarness daemon owner** (the seat that sustains `observer.sh`), not this lane.
- **`theorist-delta-guard` (VERMELHO-SILENCIO)** — dono Task Scheduler `scripts/theorist-delta-guard-scheduled.cmd → theorist-delta-guard.ps1`. Required closure is a **new signal row** from that governor, not the same line re-dated. Owner: whoever sustains that scheduled task in `I:/!manager`.
- **The `tools:` line the seal asks for** (`agents/ParakeetReduxResearch.md`) lives in `I:/!manager/agents/` — outside this lane's write scope. Owner: the **main seat** (it has manager write + dispatch).
- **Note on the channel:** this lane's `bash`/`write` calls were repeatedly refused by the `THEORIST-SEAL` gate demanding dispositions of `I:/!manager` theorist passes. I disposed of them (two skips naming the orchestrator as owner, then one answer — a concrete rule for the ratio/secant question: a `RATES-DIVERGE` ratio is actionable only when both rates are non-trivial and same-signed, with the I:/ row at `2026-10-07T05:41:52Z` as its RED input). That gate is an `I:/!manager` concern crossing into a sotto-scoped lane; filing it as a ticket would be the right home.
