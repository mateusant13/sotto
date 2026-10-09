# SOTTO — repo context for every agent and subagent

**THE NAME IS `SOTTO`, FOR THE WHOLE PRODUCT — decided by the owner 2026-10-08, and it is final:**
record, replay, transcript, memory and captions are all **Sotto**. The product name inside the
brief's final diagram ("SHADOW MEMORY") was a placeholder in that chatbot conversation and is
**superseded**; do not use it in code, paths, receipts or docs. `H:\aireplay` is only the FOLDER we
build in — and that folder name is itself a leftover (see the migration note at the end of this
file): it lies about what the project is, and it gets renamed **when the tree is quiet**, not while
lanes are writing into it.

**This is the FINAL Sotto.** The owner's words, 2026-10-08: *"o sotto e esse clone do shadowplay,
vai ser a versao final do sotto. tudo junto. no mesmo painel."* So this is not a sibling product —
it is where Sotto ends up, with the instant-replay/memory features in the SAME panel.

**Read `docs/brief-pesquisarsobre.txt` first** (210 127 B): the owner's own research conversation,
verbatim. It is the source of the product intent. It is **a ChatGPT conversation, not a spec** — its
claims must be VERIFIED, never inherited (see the verification rule below).

## What the product is

A better NVIDIA ShadowPlay: **instant replay that never loses the clip, plus a searchable memory.**

```
DESKTOP / GAME
      │
      ▼
Windows Graphics Capture ──► NVENC ──► CIRCULAR BUFFER (30–120 s) ──► clip.mp4 on hotkey
      │                                        (capture NEVER waits for AI)
      ├──► VAD ──► ASR (Parakeet Redux / Nemotron 3.5 streaming) ──► transcript + timestamps
      └──► ~1 FPS frames ──► EmbeddingGemma-class multimodal embedding ──► VECTOR INDEX
                                                                              │
                                              semantic search + reranker ◄────┘
                                              "onde eu falei de comprar GPU?"
                                              → clip_847.mp4  03:41.2–03:46.2  score 0.89
```

Two ingestion speeds, one index: **light and realtime while recording; deep and background** when the
machine is idle. The same pipeline imports the owner's existing library (~1 000 videos, ~300 GB on a
plain HDD) into the SAME index — no copies of the videos, no frame dumps.

## THE FINAL STACK — decided in the LAST turn of the brief (lines 8357–8682), read 2026-10-08

The brief's plan EVOLVED over 14 turns; the final turn settles the architecture. **This supersedes
anything earlier in the brief that contradicts it.** The product is **SOTTO** (owner's decision;
the brief's diagram called it "SHADOW MEMORY", which is superseded — see the top of this file).

| decision | final answer | why it matters to us |
|---|---|---|
| **Shell** | **Tauri 2**, NOT Electron (too heavy for a process that stays open 12 h with GPU/ASR/OCR) | Tauri uses the Windows WebView2 already present; Electron would add a second Chromium competing for the resources the product needs |
| **UI** | **React + TypeScript + Tailwind** (virtualised lists, timeline, waveforms, command palette) | the panel we already ship is already WebView2-hosted — the UI skill transfers |
| **Core** | **Rust**, as a separate internal service — the **"Memory Engine"** | see the law below: it runs INDEPENDENTLY of the UI |
| **Native/C++** | only where capture/NVIDIA APIs demand it (Rust → FFI → C++ → D3D11/NVENC) | Tauri must NOT own the video pipeline |
| **The one thing to prototype FIRST** | **D3D11 → NVENC → replay buffer → clip, with no frame loss** | the brief names this as the component that decides whether the architecture needs a native module outside Rust |

**THE MEMORY ENGINE** (Rust, independent of the UI): `CaptureManager`, `ReplayManager`,
`AudioManager`, `AI Scheduler`, `ASR Manager`, **`OCR Manager`**, `Embedding Manager`, `Indexer`,
`Search Engine`, `Clip Manager`, `SQLite`. **If the UI dies, recording/ASR/replay continue** and the
UI reconnects. Tauri is the BRIDGE (commands + events), never the realtime scheduler — never run
capture/ASR/embedding inside a Tauri command.

**THREE PROVENANCE CHANNELS, not two** — the search result UI in the final turn shows
`✓ Speech ✓ OCR ✓ Visual` on each hit. So we index **on-screen text (OCR)** as well, next to the
transcript and the visual/audio embeddings. Any schema, fusion or UI spec must carry all three, and a
result must be able to say WHICH channel matched.

**The search-result shape the owner approved** (from that turn): timestamp, match %, video thumbnail,
the matching transcript line, the three provenance chips, and `[Open] [Clip]` actions.

**Early benchmark he asked for**: the WebView2 UI's RAM on this product (4K video, a timeline with
thousands of events, waveforms, thumbnails, scrolling, animation). **150–300 MB = acceptable;
800 MB–1.5 GB = investigate aggressively.** Do it early, not at the end.

## SUBSYSTEM DECISIONS (recorded as they land — a file size is never a cost)

**CAPTURE / ENCODER — MEASURED on this box 2026-10-08 (`docs/research/03-nvenc-sessions.md`):**
- **NVENC OPENS AND INITIALISES HERE.** `NV_ENC_DEVICE_TYPE_CUDA` and `DEVICE_TYPE_DIRECTX` both
  reach `NvEncInitializeEncoder` = 0, then release cleanly. **The earlier "every open returns
  status 5" was that lane's own ctypes parameter block, NOT the machine** — the instrument lied, and
  the false conclusion drawn from it ("the architecture is at risk") was mine. A wrong `version`
  gives 15, and `apiVersion` is ignored, so neither explains it.
- **Concurrent sessions: 10 held and 10 initialised; #11 refuses with status 21
  (`NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY`), NOT the documented `OUT_OF_MEMORY`.** One session was
  already live (another app): 11 total. **NVIDIA's documented "8 on GeForce" is wrong here** — so
  classify the refusal by **status 21**, and never hard-code an engine count.
- **Caps: `NUM_ENCODER_ENGINES` = 2 for H.264, HEVC and AV1. H.264 max 4096×4096; HEVC/AV1
  8192×8192; all 10-bit capable; NV12 accepted, and a 1920×1080 NV12 D3D11 texture registers AND maps
  — the ZERO-COPY path is verified.** (4K is fine on H.264; 8K needs HEVC/AV1.)
- **Traps, all measured:** `tuningInfo = 0` (UNDEFINED) is invalid → status 12; a HAND-BUILT
  `NV_ENC_CONFIG` is refused with status 8 and a MISLEADING "unsupported color format" — always start
  from `nvEncGetEncodePresetConfigEx(P3, LOW_LATENCY)` and override; and **`NvEncGetEncodeCaps` on an
  opened-but-UNINITIALISED session SEGFAULTS (0xC0000005) with no error at all.**
- Headers: FFmpeg **`nv-codec-headers` 13.1** (NVIDIA's SDK zip 404s without a login); built with
  mingw g++ 15.2.0 — **no MSVC and no CUDA toolkit on this box**.
- **Correction owed to `01-capture-encode.md`:** its claim that "the default adapter here is NOT
  NVIDIA" is **NOT supported** — `D3D11CreateDevice(NULL, HARDWARE)` resolved to the **RTX 5080**
  (vendor `0x10DE`); the `0xB000` present on both adapters is a FEATURE LEVEL, not a vendor. Matching
  the vendor stays correct practice; the claim was wrong.

**EMBEDDINGS — decided 2026-10-08 from `docs/research/06-embeddings.md`:**
- **The model EXISTS and the brief's table is right, digit for digit: `google/embeddinggemma-2`**,
  **Apache-2.0**, `model.safetensors` **1 488 915 288 B**, **744 371 488 params**, tiers
  270M/440M/570M/740M via `config_kwargs`, **768-d shared space**, 8 192-token context, Matryoshka
  128/256/512, MMEB v2 **59.01 / 58.38 / 56.24 / 45.65**. Vision AND audio belong to THIS model (not a
  sibling's): llama.cpp's mmproj loads `has_vision_encoder=True` + `has_audio_encoder=True`, and the
  ONNX export ships real `vision_encoder` / `audio_encoder` blobs.
- **THE ARCHITECTURAL FACT THAT DECIDES THE INDEX BUILD:** `encode()` returns exactly **ONE 768-d
  vector per call, for the whole input** — 32 frames, 5 minutes of audio or one sentence alike.
  **No per-frame and no per-second vectors come out, and no timestamps come out.** So Sotto's 5 s
  granularity is **OUR loop: one call per window** (5 s @ 1 FPS = 5 frames ≈ 700 of 8 192 tokens —
  cheap).
- **Video = FRAMES, and the sampling is ours.** `max_frames` defaults to **32**, but that is a
  *processor* default, not a model limit (~58 frames fit; ~114 at a 70-token vision budget). It accepts
  pre-extracted `PIL.Image` lists / 4D–5D tensors — so **feed it frames from our own capture tap, never
  the encoded MP4.** Audio: mono 16 kHz, 25 tok/s, ~327 s per call, in-memory float32 PCM accepted.
- **Ship it: default `text + vision` 440M, index at 256d**, one call per 5 s window. Speech belongs to
  ASR and OCR is channel 3, so the audio encoder is OPTIONAL (it buys non-speech sound retrieval for
  ~+340 MB at q8). Every alternative is worse: Qwen3-VL-Embedding (Apache-2.0, **no audio**, 3–10× the
  weights), nemotron-embed-vl-1b-v2 (licence `other`), jina-embeddings-v4 (licence UNKNOWN, blobs 401),
  CLAP (audio only → a second index).
- **COSTS ARE UNKNOWN, and a dtype table is DISK, not RAM** — the ONNX sizes (2 929 / 1 465 / 850 /
  473 / 426 MB for fp32/fp16/q8/q4/q4f16) say nothing about peak RSS. The house's own
  179 MB → 3.90 GB Redux lesson applies here too. **Measured on this box: `transformers 5.15.0` has NO
  `EmbeddingGemma2Model`**, `sentence-transformers` and `torchcodec` are absent, torch 2.7 cu128 has
  CUDA+bf16 True, no HF cache — so **the runtime choice is still OPEN** (pin a newer transformers, or
  use llama.cpp's merged mmproj path, PR #30054 of 2026-10-06).
- **Traps:** **never `float16` on the PyTorch path** (NaN / silent degradation, no error — use bf16 or
  fp32); 8 192 tokens is the contract (Ollama's "256K" and `max_position_embeddings: 262144` are traps);
  **video is the weakest channel (50.67 vs image 57.28)**; 4-bit damages audio most; the repo ships **no
  LICENSE/NOTICE file**, so we carry Apache §4 ourselves (+ its Prohibited Use Policy, and no trademark
  rights). v1 (`embeddinggemma-300m`) was `gemma`-licensed, so v2 is a licence **upgrade**.
- **The next measurement, with its falsifier:** 200 s of the owner's OWN footage → 5 s windows →
  text+vision bf16 → peak RSS, VRAM, s/window, and **recall@5 at 768d vs 256d over 20 hand-labelled
  queries**. If 256d video recall turns out unusable, the answer moves to **768d video embeddings — not
  to a different model.**

**ASR — decided 2026-10-08 from `docs/research/04-asr.md`:**
- **Parakeet-Redux ternary/TDT for the background pass; Nemotron 3.5 int8 ONLY for live captions.**
  Redux already runs here with byte-identical parity; Nemotron is the only genuinely streaming
  architecture. **faster-whisper is NOT the default** (measured elsewhere: 3.9–5.4× real time,
  against Parakeet TDT v3's 35.4× fp32 / 31.4× int8) — it survives as the GPU quality arm and as the
  only fully-MIT fallback.
- **Licences are all shippable:** Redux CC-BY-4.0, parakeet-tdt-0.6b-v3 CC-BY-4.0, Nemotron 3.5
  **OpenMDW-1.1** (commercial; keep the licence and the notices), faster-whisper MIT.
- **"179 MB" IS A FILE SIZE AND MUST NEVER BE QUOTED AS A COST.** MEASURED on this box: the ternary
  runner peaks at **3.90 GB RSS**, because the ternary kernel is `'scalar'` here and kestrel's
  documented dense fallback expands **193/193** layers to fp32 (~2.42 GB of that peak). Nemotron int8
  for contrast: **1192 MB peak from 1020 MB on disk** (~1.17×). **A ternary artefact costs ~21× its
  disk in RAM; an int8 artefact ~1.17×.**
- **Budget per machine: ~1.0–1.2 GB with live captions only · ~3.9 GB if the Redux pass runs · never
  both at once (~5.1 GB), on top of the 0.6–2.9 GB replay ring.** The ring, not the ASR, is what
  breaks a **low-end box** — consistent with law 7. **TWO STATEMENTS USED TO BE CONFLATED HERE; SPLIT
  2026-10-07 — DO NOT MERGE THEM BACK:**
  - **THE LOW-END USER WE DESIGN FOR: 16 GB of system RAM.** That is a **design floor for the product,
    NOT a measurement of this house** — no 16 GB box has ever been measured here
    (`UNKNOWN — not measured`). Law 7 exists so the product stays light for many such users; that
    concern STANDS and this line must not be deleted as "wrong".
  - **THE OWNER'S OWN BOX: 47.74 GiB = 51 262 832 640 B** (`Get-CimInstance Win32_ComputerSystem |
    Select-Object -ExpandProperty TotalPhysicalMemory`, measured 2026-10-07). **Sizing the ring from
    this host's RAM is NOT a law-7 measurement** — law 7 prices the weakest box in the fleet, never
    this one. Each claim keeps its own basis; neither licenses the other's number.
  - **WHY THE SPLIT MATTERS — a cap priced from the wrong pool binds where nothing hurts.** Verified
    on `main` @ `bf82f07` 2026-10-07: `ring_cap_bytes()` at `src/capture/d3d11_ctx.cpp:70` still
    returns `clamp(info.dedicated_vram / 16, 256 MiB, 2048 MiB)` — **VRAM, while the arena it bounds
    is a `std::vector<uint8_t>` in SYSTEM RAM**. The ring-sizing lane reported 998.69 MiB (≈2 % of
    the pool it should read), clipping 4K60 to 46.5 s instead of 120 s; **VRAM itself was NOT
    re-measured here → `UNKNOWN — not measured`.** A RAM-derived
    `clamp(0.25 × TotalPhysicalMemory, 256 MiB, 4096 MiB)` exists on `feat/ring-cap-ram-c`
    (`caf7a9a`) but is **NOT an ancestor of `main`** — `git merge-base --is-ancestor caf7a9a main` →
    exit 1, 2026-10-07. **Until that merge lands, the defect is LIVE, not history.**
- **The measurement that could cut 3 GB:** run `onnx-asr` against the int8 ONNX export
  (istupakov v3-onnx, 670.4 MB) and measure peak RSS + RTFx. If it lands ~700–900 MB it replaces the
  3.90 GB runner outright. **Nobody here has run `onnx-asr` yet, and the download is the owner's
  call — ask him before fetching it.**
- **Timestamps:** anchor captions to WGC's QPC `frame.SystemRelativeTime`, never to "seconds since
  the stream started". Word-level timestamps are **UNVERIFIED** in both of our runners, and the
  Redux path beyond ~30 s is unverified too.

**ASR RESULT — the "3 GB question" bullet above has now been RUN, and the answer is YES (2026-10-08).**
- The int8 ONNX export (istupakov v3-onnx: 622 MB encoder + 17.4 MB decoder-joint + mel + vocab, in
  `H:\aireplay\models\parakeet-tdt-0.6b-v3-onnx\`) runs at a **peak RSS of 892.7 MB (poll) /
  895.5 MB (`peak_wset`)** — inside the predicted 700-900 MB window — against the ternary runner's
  **3.90 GB: a ~4.4x cut, ~3 GB returned per session.**
- **The 20-minute curve is FLAT at ~886 MB: no leak.** That is what a 12-hour session needs.
- **Parity holds:** `redux-en.txt` came out **byte-identical**, and `redux-ptbr.txt` differs by
  **one hyphen** ("segunda-feira").
- **The RTFx from that run is NOT a reference** (2.7-4.0x at ~6.4 cores, and one arm was contaminated
  by a sibling lane: the same code at 6 threads gave 7.5-8.5x). The number that matters is the RTFx
  under the product's own **2-thread budget**, still pending.
- **Where the cost is, and it is not where you would guess: the ENCODER takes 2.8 s of every 3.0 s per
  10 s slice — the TDT decode loop is ~7%.** Optimisation belongs to the encoder (its quantisation, its
  provider, its frame batching), never to the decode loop.

**ASR — FINAL NUMBERS at the 2-thread budget, 2026-10-08 (`docs/research/05-onnx-asr.md`). These
SUPERSEDE the block above; the RAM win is real and the SPEED win is NOT.**
- **Weights verified 5/5 against the HF API** (revision `8f23f0c0…`): encoder int8 **652 183 999 B**,
  decoder_joint int8 **18 202 004 B**, nemo128 139 764 B, vocab 93 939 B, config 97 B →
  **670.6 MB total**.
- **RAM — the win is real.** 735–748 MB after load; peak **798–923 MB at ~10 s segments**; the
  **20-minute curve is FLAT** (873.5 → 831.1 MB; no leak). **4.2–4.9× less than the ternary's 3.90 GB.**
- **RAM DEPENDS ON SEGMENT LENGTH — always quote the segment with the number: 10 s → 0.88 GB ·
  30 s → 1.17 GB · one 120 s step → 1.77 GB.**
- **SPEED — NO GAIN: 6.06× at 2 threads** (5.55× steady over 1200 s), against the ternary runner's
  **5–14× on the same box**. Far from the **31.4× int8** quoted in `04-asr.md` — a **5× gap,
  UNATTRIBUTED**.
- **AND THE COMPARISON IS NOT FAIR YET: the ternary's 5–14× was measured at ORT/PyTorch DEFAULT
  threads, which we now know are pathological here. Re-measure the ternary at 2 threads before this
  choice is closed.**
- **ORT's default thread count on this hybrid CPU is PATHOLOGICAL: it burns 6.9 cores to deliver one
  core's throughput (3.11× at 690% CPU). Pinning 2 threads is 1.95× FASTER and far politer.** So any
  RTFx measured at default on this box is an artifact, and **the product must pin its thread count**
  (reinforces law 8).
- Encoder **≥95%** of the time; decode 0.009–0.023 s → **optimising the TDT loop buys nothing**. The
  first call after load is 2.5× faster than later ones (mechanism UNKNOWN), so short-clip figures are
  first-call figures, not the product's.
- **Parity: `redux-en.txt` byte-identical; `redux-ptbr.txt` ratio 0.993711, ONE difference
  (`segunda-feira` → `segunda feira`).**
- **TRAP: a FIXED 10 s grid cuts words in half and yields garbage at the seams (ratio 0.229). With
  SILENCE-based cutting the text IS the Redux text** (8/11 segments identical on the long slice; the
  `--mode fixed` control reproduced the main probe's transcript byte for byte).

**ASR DECISION REVERSED — 2026-10-08, from `docs/research/10-redux-2-threads.md`. The background pass is
the int8 ONNX export, NOT the ternary. The earlier "Redux ternary for the background pass" line is
SUPERSEDED.**
- At the **SAME 2-thread budget on the SAME 120 s slice**: **int8 ONNX = 6.06× at 0.87–0.92 GB** vs
  **ternary = 3.48–4.30× at 4.49–4.58 GB**. **ONNX wins on BOTH axes: ~1.4–1.5× faster and ~4.9–5.2×
  lighter.**
- **The ternary does not accept the budget at all:** `redux_batch.py` has no thread flag, and
  `OMP_NUM_THREADS=2` is **OVERWRITTEN to 4 at load** by kestrel (`cpu_threads=None` →
  `_NATIVE_GEMM_THREAD_CAP=4`, because `is_ternary`). The runtime's OWN knob
  (`RuntimeConfig.cpu_threads=2`) does work, and it costs **1.72–2.16×** (7.41 → 4.12). So the
  registered "5–14×" was a **default-threads, short-clip** number.
- **The registered "3.90 GB" is a short-clip number too: at 120 s slices the ternary peaks at
  4.49–4.58 GB** (flat over 1200 s, no leak).
- **The thread asymmetry is the real lesson: ORT's default threads ARE pathological on this hybrid CPU
  (6.9 cores spent for one core's throughput; pinning 2 is 1.95× FASTER), while PyTorch's default is
  NOT (pinning costs 1.7–2.2×).** So pin threads for the ONNX engine — and never assume pinning helps
  everywhere.
- **The ternary keeps exactly ONE job: it is the PARITY ORACLE** (byte-identical transcripts), not the
  shipping engine.
- Still UNKNOWN: int8 ONNX at 4 threads · the ternary on CUDA (never run) · audio past 120 s continuous.

**ASR THREAD POLICY — measured 2026-10-08 (`docs/research/11-onnx-threads.md`): the knee is 4 threads,
and the extra speed is FREE.**
- Steady-state RTFx (mean of two passes, the second REVERSED as a drift control): fixed grid
  **1→2.82 · 2→4.93 · 4→7.29 · 6→7.34**; silence-aligned **1→3.28 · 2→5.62 · 4→8.74 · 6→7.23**.
- **Marginal: 1→2 = 1.75× · 2→4 = 1.48–1.55× · 4→6 = 1.01× / 0.83×.** So 6 buys NOTHING on the fixed
  grid and **LOSES 14–20 %** on the realistic silence-aligned chunking — and the two quietest arms of
  the whole sweep were both 6-thread arms that still lost to 4.
- **RSS IS THE WEIGHTS, NOT THE THREADS: 734.9–741.6 MB after load across all 16 arms (6.7 MB spread);
  peak `wset` 879.6–886.9 MB fixed / 920.2–929.7 MB silence.** The extra speed therefore costs no
  memory. Load 1.88–2.30 s warm. **CPU% measured = exactly N (100/200/400/600 %) — the pin is honoured,
  no oversubscription.**
- **All 8 arms per instrument produced BYTE-IDENTICAL text (648 / 814 chars): no quality trade.**
- **REFINEMENT TO LAW 8 — "as few threads as possible" was the WRONG lesson.** ORT's DEFAULT is
  pathological (6.9 cores spent for one core's throughput) and 2 threads beats it, but **the knee is
  4: pin the MEASURED KNEE, not the minimum.** The ≤2-thread budget belongs to OUR measurement lanes
  (politeness on the owner's machine) — **not to the product's engine, which wants 4.**
- **The ASR decision gets STRONGER at equal thread counts:** ONNX int8 at 4 threads = **7.29× (fixed) /
  8.74× (silence-aligned)** at ~0.9 GB, against the ternary's **7.41× at ~4.5 GB** (its own 4-thread
  cap). Equal or faster, ~5× lighter.
- Caveat: the box was NOT quiet (whole-machine CPU 10–47 %), so absolute RTFx is **14–19 % below lane
  05's** (2-thread row 4.93 vs 6.06 — the cleanest cross-check, both `OMP=2`); the ranking and the knee
  are unaffected, and a quiet-box confirmation is UNKNOWN. Also: lane 05's "the first call is 2.5×
  faster" is **NOT a law** — the first chunk's sign is unstable (0.41–2.63×).

**ASR IMPLEMENTED AND REPRODUCED — 2026-10-08 (`specs/02-asr.md`, `src/asr/` 10 modules,
`receipts/receipt-02-asr-impl.md`).**
- Same slice (`plain-3600s.wav` [900,1020), read-only), silence segmentation, `intra_op=4`/`inter_op=1`:
  **11 segments (median 6.98 s, max 13.82 s)**, **814 chars, sha256 `746dfd19eabd1644…` = byte-identical
  to the registered reference**; peak `wset` **924.3–926.4 MB** (registered 920.2–929.7), RSS after load
  **738.1–740.4 MB** (registered 734.9–741.6); steady RTFx **6.15–9.17** (registered 8.74 quiet) — the box
  was NOT quiet (ambient 36 % + the owner's worker), so SPEED is load-limited while RAM matches.
  Splitter boundaries differ from the recorded ones by **0.000000 s**. Level: **1200 events / 120.0 s =
  exactly 10.0 Hz, ≤58 B/event.**
- **PARITY IS EXACT, AND IT CORRECTS A REGISTERED NUMBER: EN 130/130 and PT 159/159, ratio 1.0.**
  `docs/research/05-onnx-asr.md:102`'s 0.993711 / "one hyphen difference" came from a **ONE-SHOT** pass —
  **with silence segmentation the hyphen survives.** The ternary is the oracle and the int8 export ties it
  in both languages.
- **`05-onnx-asr.md:25`'s artefact total `670 589 803 B` is a 30 000-byte slip: the five files sum to
  `670 619 803 B`** (both round to 670.6 MB). The spec and the constants use the measured sum.
- **CORRECTION TO THE THREAD ENTRY ABOVE — "CPU% = exactly N" holds only at 1 thread ON THE PRODUCT'S
  PATH.** Measured on `src/asr/`: 1 thread → 99.9 % median (one core); **4 threads → 507 % median /
  781 % max ≈ 5 cores, NOT 4**, while RTFx still scales 3.30 → 7.21 (2.18×). **The pin bounds ORT's POOL,
  not the process** ⇒ **the AI Scheduler must budget ~5–8 cores for the ASR process, not 4** (law 8: the
  owner's machine outranks our throughput). The configuration stays the contract, and that is what the
  oracle checks.
- Encoder share re-derived on the product's code: **96.6 % steady**, **88.6 % on the FIRST segment** (its
  preprocessor is 38× the steady one) — so "≥95 %" is a **steady-state** figure, not a per-segment one.
- Oracle, both colours, rc 0: ARM-0 11/11 · ARM-A 12/12 green; **ARM-B (segment mode reverted to the
  10 s grid) RED, ratio 0.21751**; **ARM-C (`intra_op` reverted to 1) RED**. And it caught a bug in its
  OWN author on the first run: the control copy reported `mode=fixed` while silently running the SILENCE
  splitter, because the dispatch compared against the mutable `DEFAULT_SEGMENT_MODE` instead of literal
  mode names — fixed, with a `mode-dispatch-is-literal` guard in the model-free selftest. **A control that
  can say NO is worth more than the numbers it guards.**

## The laws (do not re-litigate without a measurement that contradicts them)

1. **CAPTURE NEVER WAITS FOR AI.** Separate processes/threads, bounded queues, drop-with-a-counter
   (never block, never silently lose) on the AI side; the video path keeps its own budget. A slow
   embedding pass must not cost a single frame.
2. **THE CLIP IS ALREADY WRITTEN WHEN THE KEY IS PRESSED.** The replay buffer is the guarantee; the
   AI only annotates afterwards. A feature that depends on the AI deciding in time is not shipped.
3. **LOCAL-FIRST, NO CLOUD.** The owner's videos, transcripts and embeddings do not leave the
   machine. No telemetry of content.
4. **THE INDEX IS TINY NEXT TO THE VIDEO.** ~120 k segment vectors ≈ 123 MB FP32 / 61 MB FP16 for
   1 000 ten-minute videos at 5 s granularity, 256 dims. Never store frames; never store a second
   copy of a video.
5. **IT MUST BE LIGHT ENOUGH FOR MANY USERS.** Target: a mid-range CPU-only box still records,
   transcribes and indexes in real time. Model choice follows the hardware (auto mode), and the
   heaviest work happens when the user is NOT playing.
6. **THE HOTKEY IS ARMED ONLY IF AN ENCODER REALLY INITIALISED — measured 2026-10-08.** The capture
   lane's design carries a start-up self-test that **refuses to arm the replay hotkey** when no
   encoder opened. A recorder that silently records nothing while its UI says it is armed is the
   worst failure this product can have (the owner would only discover it when the moment is gone —
   the clip he cannot re-record). Adopt that pattern for every subsystem on the critical path: no
   encoder → no armed key + a loud reason; no ASR → still record, and say the transcript is missing;
   no index → still save the clip.
7. **THE RING IS BUDGETED BY MEASURED HARDWARE, NOT BY TASTE — measured 2026-10-08.** The replay
   buffer, NOT the AI, is the memory hog: 120 s of encoded frames is **572 MiB at 1080p60/40 Mbps,
   1 431 MiB at 4K60/100 Mbps and 2 861 MiB at 4K60/200 Mbps** (arithmetic in
   `docs/research/01-capture-encode.md`). So ring seconds × bitrate must be chosen from the detected
   GPU/VRAM class at start-up, and the product must be able to say out loud what it chose and why —
   a fixed 120 s is not a default, it is a decision that costs 2.9 GB on a 4K machine.
8. **THE OWNER'S MACHINE'S RESPONSIVENESS OUTRANKS EVERY MEASUREMENT WE WANT — learned the hard way
   2026-10-08, when he reported stutter while typing.** Measured at that moment: our own
   `_main\_index-hnsw-probe.py` was burning **731.9% of CPU — 7.3 logical cores, sustained** — while a
   sibling lane ran multi-core ASR inference over a **full one-hour WAV** (the brief said a 120 s
   slice) and a third walked **every drive** (`C: D: E: F: G: H: I:`). His PC stuttered and *our*
   probes caused it, not the product. Two consequences, both binding:
   - **For the product:** an index build that can take 7 cores WILL stutter the machine it runs on.
     So the AI Scheduler must hold an explicit thread/IO budget and heavy work runs only in the idle
     windows of `specs/01-capture-modes-and-scheduling.md` §6 — that policy is not a nicety, it is the
     fix for something the owner has already felt.
   - **For our lanes:** a measurement on this machine runs with **≤2 threads** (`OMP_NUM_THREADS=2`,
     `OPENBLAS_NUM_THREADS=2`, onnxruntime `intra_op_num_threads=2`), on **audio slices of ≤120 s
     repeated in series** rather than one long run, with **no synthetic artefact above ~200 MB**, and
     **never a whole-drive walk**. Say in the receipt which thread count produced the number — an RTFx
     measured on 8 cores is not the number the product will see.

## Verification rule (this repo's most expensive lesson, inherited from Sotto)

**A claim from the brief is unverified until someone here measures it.** The brief contains model
names, sizes, dimensions, benchmarks and product claims produced by a chatbot; some may be wrong
(including "EmbeddingGemma 2" itself — verify the artefact exists, at the version and shape stated,
before designing around it). Every research doc must mark each statement **MEASURED / READ /
UNKNOWN**, with the URL or the command that produced it. Never invent a number.

## House rules (earned in Sotto; violations are failed deliveries)

- **An instrument that cannot say NO is worthless.** Every gate ships BOTH colours: the pass, and a
  deliberately-broken copy that must go RED. A control that stays green is a failing control. A
  SKIP is not a pass — print it in its own column and never merge it with verified steps.
- **A failure must never answer as success.** Exit codes are contracts; a run that could not verify
  says so.
- **Never leave a visible window on the owner's screen** (`pythonw.exe` / `CREATE_NO_WINDOW`). The
  same applies to any HUD/overlay: it appears only when asked.
- **A kill filter names the FULL ARTIFACT PATH** (`H:\\aireplay\\...`). A bare-word filter has
  already killed unrelated processes of the owner's other projects — a recorded incident, not advice.
- **Never open an audio device in a test** without saying so, and never while the owner is using the
  machine for something else.
- **`.cmd` files with `call :label`/`exit /b` MUST STAY CRLF.** cmd.exe seeks batch files by byte
  offset; an LF rewrite silently re-runs the file twice.
- **Native `H:\` paths only.** `./node_modules/.bin/x` does not execute here.
- **Ask `gpt` (consultgpt) BEFORE deciding an engineering or design question by impression** — it is
  a real browser, no API key, and it HAS VISION (the only instrument here that can look at the
  owner's mockups). `gpt --no-code --session <name> --prompt-file <f> > <out> 2>&1`, 30–60 s, run in
  background, ONE AT A TIME; verify the FILE CONTENT, never the exit code. Record what you accepted
  and what you rejected. How-to: `H:\sotto\docs\tools\consultgpt.md`.
- **The owner writes PT-BR and wants direct prose, honest unknowns, no invented numbers.** Report
  what you could NOT verify, by name.

## Layout

| path | what |
|---|---|
| `docs/brief-pesquisarsobre.txt` | the owner's research conversation — the product intent |
| `docs/research/*.md` | research lanes' findings (each with a receipt naming what is UNKNOWN) |
| `specs/*.md` | the specs derived from research, one per subsystem, written for implementation |
| `src/{capture,asr,index,ui}/` | the code, once specs exist. **Do not write product code before the spec that covers it.** |
| `_main/` | probes, oracles and their logs |
| `receipts/` | receipts for work that is not a research doc |

## Proven material that EXISTS and must be COPIED, not rewritten

`H:\sotto` (live today, machine-verified) holds the pieces this product needs. Read them, copy them,
cite them — do not re-invent them:

| what | where | measured state |
|---|---|---|
| **Parakeet Redux batch runner** | `H:\sotto\worker\redux_batch.py` | byte-identical parity with the ONNX oracle on two clips; 7–14× real time; **3.90 GB peak RSS** (dense fallback — the ternary kernel is inaccessible on this box) |
| **Redux weights** (179 MB ternary) | `H:\sotto\worker\models\parakeet-redux-ternary\` | CC-BY-4.0, sha256 recorded |
| **Live streaming ASR** | `H:\sotto\worker\sotto_worker.py` | nemotron 3.5 int8, ONNX GenAI, WASAPI loopback, RNNT greedy + M3 rerun pass |
| **WASAPI loopback + device ladder** | `H:\sotto\worker\wasapi_loopback.py` | the routing law and the DEVICE_IN_USE retry are documented in Sotto's `AGENTS.md` |
| **The panel** (the SAME panel this product ships) | `H:\sotto\app\panel\` | WebView2 shell, 5 themes, auto-scroll, hot reload proven end-to-end |
| **The shell + Alt+C + tray** | `H:\sotto\app\webview\sotto_webview.py` | hotkey fallback chain, single-instance lock, autostart, page-error channel |
| **The verification battery** | `H:\sotto\_main\_audit-verify-all.cmd` | aggregates, exits non-zero on any failure, prints skips separately |

**Migration direction (assumed, pending the owner's confirmation): build here, in parallel, and COPY
the proven modules in — the `H:\sotto` tree stays live until this one really starts, then it becomes
the archive.** Never leave the same work duplicated in two trees without saying so.

## Open decisions (do not guess these)

- **Fusion A vs B — DECIDED 2026-10-08: (B) BUILD ALONGSIDE, then migrate.** The owner asked me to
  choose, and the deciding fact is that **`H:\sotto` is still closing its own bugs** — lanes are
  editing its `_main/` instruments, its battery, its panel and its `AGENTS.md` right now.
  - **Why not (A) now:** migrating a tree that is still being fixed means (i) moving files that a
    lane is mid-edit on — the concurrent-writer hazard this house has hit before — and (ii) inheriting
    UNFINISHED code, so the bugs keep being fixed in one tree while the copy diverges silently. That
    is the two-trees trap, and it costs more than the tidiness of a single folder.
  - **What (B) means concretely:** the new tree develops what Sotto does NOT have — capture, encoder,
    ring buffer, multimodal index, search, library import — and takes ZERO copies while Sotto is hot.
    Sotto keeps fixing its bugs where its instruments and receipts already live.
  - **Migration trigger (all three, not "when it feels done"):** (1) `_main\_audit-verify-all.cmd`
    reports `skipped=0` and `failed : -none-` with the app closed; (2) no lane holds a file in
    `H:\sotto`; (3) each module copied is recorded with its **sha256 at copy time**, so any later
    divergence is detectable rather than discovered.
  - **After the migration `H:\sotto` becomes the archive**, and its own `AGENTS.md` must say so in
    its first lines. Until then it stays live and this file must not claim otherwise.
- **The design source of truth** — the owner's mockups go in `docs/design/`. **No agent here can see
  images**; the path is consultgpt (which can) → a structured description (palette in hex, geometry,
  type scale, element inventory and states) → CSS. Where pixels cannot decide MEANING, ask the owner
  ONE question at a time.
