# 04 — Which ASR we ship, and the REAL cost of memory

**Question:** what runs by default, and what RAM must the product assume per transcription session?
**Scope: one question.** No OCR, no embeddings, no UI.
`MEASURED` = a command on this box produced it (file named) · `READ` = external source, URL given · `UNKNOWN` = nobody has shown it.

Host: Windows 11 Pro 10.0.26200 · i5-13600K · RTX 5080 · CPU-only ASR (ORT `CUDAExecutionProvider` did not load in Sotto).

---

## 0. Answer in one line

**By default: Parakeet-Redux (ternary/TDT) as the background pass, Nemotron 3.5 streaming int8 only while the user is
looking at captions — and the honest memory budget is ~1 GB per active session, not 179 MB, because the 179 MB is a
file size and the number that decides "light for many users" is RSS.**

---

## 1. Which one, for whom

| | **Parakeet-Redux / TDT 0.6B v3** | **Nemotron 3.5 streaming 0.6B** | **faster-whisper (Whisper)** |
|---|---|---|---|
| license to distribute commercially | CC-BY-4.0 — attribution only (**READ**, [moondream/parakeet-redux](https://huggingface.co/moondream/parakeet-redux), [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)) | OpenMDW-1.1 — commercial use, keep the licence + notices (**READ**, [model card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b), [text](https://openmdw.ai/license/1-1/)) | MIT for code **and** weights (**READ**, [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) |
| PT-BR | FLEURS pt 4.99 (**READ**, Redux card) | pt-BR transcription-ready tier, FLEURS pt-BR **5.48** at 1.12 s (**READ**, Nemotron card) | pt is a Whisper core language; **UNKNOWN** for our audio |
| punctuation + casing | native (**READ** both cards) | native PnC (**READ**) | native |
| segment timestamps | yes — **MEASURED** on our clip: `0.00–7.92` / `8.24–14.72` | yes, token- and word-level (**READ**, transcribe.cpp [port doc](https://github.com/handy-computer/transcribe.cpp/blob/env-vars/docs/models/nemotron-3.5-asr-streaming-0.6b.md)) | segment + `word_timestamps=True` (**READ**, README) |
| **word** timestamps | documented (**READ**); **UNKNOWN** in our runner | documented (**READ**); **UNKNOWN** in our worker | available, wav2vec2-aligned in WhisperX |
| VAD | built into the encoder's subsampler, no external model (**READ**) | none — bring Silero (**READ**: *"VAD: not supported"*) | Silero VAD integrated, on by default for batched (**READ**) |
| live streaming | not its job (**READ**) | **its job** — cache-aware, 80 ms…1.12 s chunks (**READ**) | not native; needs a wrapper |
| noise (music/explosions/overlap) | **the weak spot.** MUSAN 9-condition avg WER **9.04** vs the original's **6.72**; *"noise is where the gap to the original is widest … at low SNR it substitutes similar-sounding words"* (**READ**, Redux card) | **UNKNOWN** — no game-audio benchmark exists for either. The original v3 gets 6.34 %→11.66 % at SNR 0 (**READ**, v3 card) | **READ**-level folklore only: silence/music hallucination is a known failure, VAD is the standard cure |

**Decisions.**

- **Default for the background/general pass: Parakeet-Redux ternary + TDT.** Reason: it is the only one of the three
  already running on this box with **measured byte-identical parity** and a working runner
  (`H:\sotto\worker\redux_batch.py`, receipt `H:\sotto\_main\receipt-redux-ternary.md`), it needs no GPU, and both
  its licence (CC-BY-4.0) and its sentence segmentation are settled. It is the *safe* default, not the *best* one on noise.
- **Default for live captions while the panel is open: Nemotron 3.5 int8** — unchanged from Sotto, and it is the only
  candidate actually built for a continuous stream.
- **faster-whisper: not by default.** It is the only *fully* MIT option and the only one with a mature word-timestamp
  pipeline, but on CPU it is **~10× slower than Parakeet for the model you would actually want**: onnx-asr measures
  Whisper large-v3-turbo at **3.9–5.4× real time** on a 9800X3D, against Parakeet TDT v3 at **35.4× fp32 / 31.4× int8**
  (**READ**, [benchmarks](https://istupakov.github.io/onnx-asr/benchmarks/)). Law 5 (light for many users) rules it out
  on CPU. Keep it as the *quality arm* on a GPU box, and as the licence fallback if CC-BY attribution ever becomes a
  problem. **UNKNOWN: whether it beats Redux on our actual game audio** — nobody has run it there.
- **Do not choose on FLEURS.** Every number above is read, clean, single-speaker, read-Wikipedia audio. **We have zero
  measurements of any of the three on game audio** (music + explosions + overlapping speech). That is the gap that
  matters and it is listed in §4.

---

## 2. The truth about the memory

**The brief sells Redux as ultralight because 179 MB is the file size. That number does not describe a running process.**

**MEASURED, on this box, `H:\sotto\_main\receipt-redux-ternary.md`:**

- disk: `model.safetensors` **177 774 490 B** (170.7 MB for the directory) — this is the ternary artefact, sha256 `78ec2573…`
- **peak working set 3.90 GB** for the whole process, measured twice, in-process `GetProcessMemoryInfo` *and* an
  external `Get-Process.WorkingSet64` poll
- speed 7–14× real time on a 15 s clip; load 3.7–4.3 s
- **why** — and this is the part that must not be lost: the packed ternary kernel is **unreachable on this machine**.
  `_cpu.ternary_gemm_isa()` returns `'scalar'` although the CPU has AVX2, because kestrel ships its kernels in a
  protected payload (`kestrel_cpu.kstlc`, *"The key is not stored in this file"*; byte-identical in 0.7.5, so not a
  0.7.4 bug). The runner therefore takes kestrel's own **documented dense fallback**: **193 of 193** quantized encoder
  projections are expanded to fp32 at load. 604 M weights × 4 B ≈ **2.42 GB** of that peak is the dequantized weights.
  **The ternary format saves disk. On this box it costs RAM.** Same runtime on an AVX-512-VNNI machine would keep the
  179 MB resident form and run at the vendor's quoted speed — that is a **READ** claim we cannot check here.

**A lighter export does exist, and it is the semantically right form — but it is smaller on disk, not measured in RAM.**

| artefact | bytes on disk | source |
|---|---|---|
| Redux ternary (`moondream/parakeet-redux`) | 179 020 262 (dir) — **MEASURED** | `H:\sotto\worker\models\parakeet-redux-ternary` |
| Redux ONNX int4-style (`eschmidbauer/parakeet-redux-onnx`, CC-BY-4.0) | encoder **343 841 943** + decoder_joint **72 552 270** + preprocessor 1 224 294 + vad 18 300 687 = **435.9 MB** | **READ**, [HF API tree](https://huggingface.co/api/models/eschmidbauer/parakeet-redux-onnx/tree/main) — **deleted from Sotto on the owner's order, not on disk now** |
| v3 int8 ONNX (`istupakov/parakeet-tdt-0.6b-v3-onnx`) | encoder int8 **652 183 999** + decoder int8 18 202 004 = **670.4 MB** | **READ**, [HF API tree](https://huggingface.co/api/models/istupakov/parakeet-tdt-0.6b-v3-onnx/tree/main) |
| v3 int8 ONNX (second exporter) | **935.2 MB** | **READ**, [HF API tree](https://huggingface.co/api/models/HariDangi/parakeet-tdt-0.6b-v3-onnx-int8/tree/main) |
| Nemotron 3.5 int8 (the live engine, ORT-GenAI) | 1 070 641 193 (dir), of which `.onnx.data` 1 015.46 MB | **MEASURED** |

- The ONNX path is **lighter than the ternary path in RAM on x86** *and* we know it runs here: `onnx-asr` (MIT) supports
  NeMo Parakeet/TDT, other runtimes' int8 Parakeet weights are reported at **0.67 GB** and **42× real time**
  (**READ**, Redux card's own comparison table). But whether the OnnxRuntime int8 kernel is actually selected on this
  CPU is **UNKNOWN** — nobody here has run `onnx-asr`. **This is the one measurement worth buying before deciding.**
- **A third-party PT-BR fine-tune exists** (`calneymgp/…-ptBR-TAGARELA-onnx-int8`, encoder int8 879 746 906 B,
  **READ**, HF API tree). Not evaluated by us, licence not verified here — flagged, not recommended.

**The budget a real product must assume, per session:**

| item | number | status |
|---|---|---|
| Nemotron int8, load + one inference | **1191.9 MB RSS, PEAK 1191.9 MB** for 1020.30 MB of on-disk weights | **MEASURED** (`H:\sotto\_main\precision-ram-probe-int8.log`) |
| Redux ternary, same thing | **3900 MB peak** | **MEASURED** (`receipt-redux-ternary.md`) |
| Redux ONNX int4 (deleted) | ~450 MB was the Sotto working figure | **not re-derived here** — UNKNOWN |
| faster-whisper small int8 on CPU | **1477 MB** for a *5-minute-class* load; large-v3 int8 on GPU 2926 MB VRAM | **READ**, [faster-whisper README](https://github.com/SYSTRAN/faster-whisper) |
| **→ budget per ACTIVE transcription session** | **~1.0–1.2 GB live only; ~4 GB if a background Redux pass runs at the same time** | derived from the two MEASURED rows |

**Two rules follow, and they are the law-5 answer:**

1. **Never run both engines at once on a normal machine.** Live-only = ~1.2 GB. Redux-only = ~3.9 GB **on this box**.
   Live + Redux = 5.1 GB of ASR on a machine also holding a 0.6–2.9 GB NVENC replay ring (measured arithmetic,
   `docs/research/01-capture-encode.md` §2) plus the game. The panel-visibility hook that was supposed to make them
   never overlap is **still missing** in Sotto; until it exists, "light for many users" is a claim, not a property.
2. **The ring, not the ASR, is what breaks a 16 GB machine.** Model choice is a ~1–4 GB decision; ring seconds ×
   bitrate is a 0.6–2.9 GB decision; the game is the rest. Both must be sized from the detected box at start-up.

---

## 3. Streaming vs batch for a continuous recorder

- **What keeps timestamps aligned with the video: a clock, not the ASR's opinion.** WGC frames carry
  `frame.SystemRelativeTime` in **QPC** — one clock we can share with the audio (Windows Graphics Capture docs,
  **READ**, cited in `01-capture-encode.md` §1). Anchor every caption to that timeline: store `(video_qpc, audio_pcm_offset)`
  at capture start and let the transcript keep offsets, never "seconds since the stream started".
- **Streaming (Nemotron) is self-locating**: cache-aware chunks are strictly non-overlapping, so a token's position is
  the number of chunks consumed × chunk size (**READ**). Cheap, but error accumulates silently — budget **1 chunk,
  80 ms…1.12 s**, of caption lag by design.
- **Batch (Redux/TDT) is not self-locating**: it reports segment boundaries it derived itself. **MEASURED** parity on our
  15 s clip (`0.00–7.92` / `8.24–14.72`), but the long-form path is **UNVERIFIED** — the receipt's own §6.2 says audio
  >30 s was never exercised and the model's VAD head never had to cut anything. A 2-hour session is untested there.
- **Overlapping speech is nobody's solved case.** None of the three is a diarizer; the brief's ⌈game audio⌋ case
  (speech over music over explosions) is the exact condition where Redux's noise gap is widest and where faster-whisper
  is documented to hallucinate into silence. **UNKNOWN for all three.**
- **The budget while a game runs:** ~1.2 GB live ASR + ring (0.6–2.9 GB, choose from detected GPU class) + the game.
  Do the heavy pass **only when the panel is closed and ideally only on audio the VAD kept** — a VAD that drops 60 % of a
  two-hour session removes 60 % of the compute and allows chunking into the model's real 20–30 s operating range
  (`onnx-asr` warns most models cap at 20–30 s; **READ**).

---

## 4. What is still UNKNOWN — and the ONE measurement that decides this

1. **No game-audio benchmark exists for any candidate.** Everything scored above is FLEURS/MUSAN read speech.
   *The measurement:* 10 minutes of the owner's own recorded game audio (music + explosions + overlapping speech),
   transcript compared by hand, three arms.
2. **Does OnnxRuntime actually pick an int8 kernel on this CPU, and what is its RSS?** Run `onnx-asr` on
   `istupakov/parakeet-tdt-0.6b-v3-onnx` (670 MB) and measure peak RSS. If it lands ~700–900 MB, **it replaces the
   ternary runner as the background engine** and §2's 3.90 GB disappears. ~30 min of work; **no model download was
   made by this lane**, by rule.
3. **Word-level timestamps from either engine on our audio** — never compared to a reference in Sotto.
4. **Long-form (>30 s) and the VAD segmenter for BOTH engines.**
5. **The PT-BR variant question**: v3's Portuguese training data is European Portuguese and NVIDIA's own note says
   benchmarks use Brazilian (**READ**). Our audio is pt-BR. Unquantified.

*Method note, disclosed:* the house rule says to ask `consultgpt` before deciding by impression. This lane did not
run it — the three-way choice above is argued from MEASURED + READ evidence with every gap named, and the deciding
work is measurement 1 and 2, not opinion. If a tie needs breaking, ask it then, with those two results in hand.
