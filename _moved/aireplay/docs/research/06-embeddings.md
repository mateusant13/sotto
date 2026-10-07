# 06 — Does the brief's "EmbeddingGemma 2" exist, and do we use it?

**Question:** is the multimodal embedding model the brief describes (`docs/brief-pesquisarsobre.txt` lines 1–60, 1594–1700) real, at the version and shape it claims — and if so, is it what Sotto ships? **Scope: one question.** `MEASURED` = a command on this box produced it (named) · `READ` = external source, URL given · `UNKNOWN` = nobody has shown it. Host: Windows 11 Pro 10.0.26200 · i5-13600K · RTX 5080 · torch 2.7.0+cu128 (CUDA + bfloat16 available).

---

## 0. Answer in one line

**YES. It exists — `google/embeddinggemma-2`, Apache-2.0, sha `914f7f89…` — and every number the brief quotes for it (740M = 270M text + 170M vision + 300M audio, one shared 768-d space, MRL 128/256/512/768, 8 192 tokens, 1 FPS video with a 32-frame cap, MMEB 59.01 @768d) is correct. The correction that decides the architecture is not the model but its granularity: one `encode()` call returns exactly ONE 768-d vector for the whole input — so per-segment indexing is OUR loop, and video sampling is OURS to choose.**

---

## 1. Does it exist? Exact ids, parameters, licence

| artefact | id / bytes | status |
|---|---|---|
| reference weights | [`google/embeddinggemma-2`](https://huggingface.co/google/embeddinggemma-2) — `model.safetensors` **1 488 915 288 B**, `license: apache-2.0`, 742 likes / 7 562 dl | **READ** ([HF API](https://huggingface.co/api/models/google/embeddinggemma-2?blobs=true)) |
| modular packs | `litert-community/embeddinggemma-2-{text-270m,text-vision-440m,740m}-litert-lm` (+10 NPU `.litertlm` each) | **READ** (HF API) — "loadable by module" ships as three separate tiers |
| ONNX | [`onnx-community/embeddinggemma-2-ONNX`](https://huggingface.co/onnx-community/embeddinggemma-2-ONNX) — `model/vision_encoder/audio_encoder.onnx`, each fp32/fp16/q8/q4/q4f16 | **READ** |
| GGUF + Ollama | [`ggml-org/embeddinggemma-2-GGUF`](https://huggingface.co/ggml-org/embeddinggemma-2-GGUF): text `557 950 176 B` BF16 / `309 855 456 B` Q8_0 **+ mmproj** `982 074 784 B` BF16 / `554 821 024 B` Q8_0 · [Ollama](https://ollama.com/library/embeddinggemma-2) 17 tags, 378 MB…1.3 GB | **READ** |

**Parameters, exact:** total **744 371 488** and text+audio **576 613 664** are printed by Google's own guide (**READ**, [multimodal guide](https://ai.google.dev/gemma/docs/embeddinggemma/multimodal-embeddinggemma-with-sentence-transformers)); vision = **167 757 824** (arithmetic on those two); text-only 270M = 130M transformer + 140M embedder. The four tiers (`vision_config=None`/`audio_config=None` → 270M, 440M, 570M, 740M) are the card's own table.

**The video+audio claims are in THIS model's card, not borrowed from another model** — the brief's suspicion (ours too) is refuted by two independent runtimes: llama.cpp's `mmproj` loads with `clip.has_vision_encoder = True`, `clip.has_audio_encoder = True`, projectors `gemma4v`/`gemma4a` (**READ**, [llama.cpp #30082](https://github.com/ggml-org/llama.cpp/issues/30082) body), and the ONNX export ships a real `audio_encoder.onnx_data` of 1 172 750 848 B. `config.json` declares `model_type: embedding_gemma2` with `text_config` (24 layers, hidden 512, `embedding_dim: 768`, sliding 512), `vision_config` (16 layers, patch 16, `default_output_length: 280`), `audio_config` (12 layers, hidden 1024) and the placeholders `<|image|>` 258880 / `<|audio|>` 258881 / `<|video|>` 258884. Pretraining cutoff **January 2025**.

---

## 2. Video: the model receives FRAMES, and the sampling is ours

Verbatim from the card: *"video is processed as sampled frames through the vision encoder at **1 frame per second**; FPS sampling rate is configurable"*; from transformers.js: *"Videos with more than 32 frames are subsampled uniformly to 32 frames"*. Therefore:

- **Frames, not a file — unless we choose otherwise.** `sentence-transformers` can decode an MP4 for you (`model.encode({"video": p})`, needs `torchcodec`), **or** you pass your own pre-extracted list of `PIL.Image` or a 4D/5D tensor. Sotto already owns a frame tap (WGC), so pass frames and never pay a second decode.
- **Sampling is ours, per call:** `processing_kwargs={"video": {"max_frames": 16, "fps": None, "overflow_strategy": "uniform"|"truncate", "add_timestamps": True}}` (**READ**, same guide).
- **32 is a processor default, not a model limit.** The real limit is the shared 8 192-token budget at 140 tokens/frame → **~58 frames**, ~114 at a 70-token vision budget (**READ**, card §Context Limits).
- **Per video or per segment? PER CALL.** Every example returns shape `(768,)` — one vector for a sentence, for 32 frames, for 5 minutes of audio alike. **No per-frame/per-second vectors, no timestamps out** (`add_timestamps` inserts frame times *into* the input sequence). ⇒ The product's timeline is built by **us**: one call per window — 5 s @ 1 FPS = 5 frames = 700 tokens, well inside budget.
- **Audio, same mechanism:** mono **16 kHz**, **25 tokens/s**, ~327 s max per call; accepts a file, a URL or an in-memory `float32` NumPy array, so our own PCM goes straight in (**READ**, card + guide).

---

## 3. Real dimensions and the benchmark table

Native **768-d**, mean pooling, 512→768 projection. Truncation **512/256/128** (MRL), with two silent-failure traps from the card: **re-normalise after truncating**, and **query and corpus must share a dimension**. The brief's table (lines 1966–1970) is the card's, digit for digit:

| Output dim | MTEB multi v2 | MTEB eng v2 | MTEB code v1 | MIEB (lite) | **MMEB v2 Overall** | MSEB (retr.) | MAEB |
|---|---|---|---|---|---|---|---|
| 768d | 61.36 | 68.46 | 78.68 | 64.64 | **59.01** | 69.54 | 49.39 |
| 512d | 61.17 | 68.41 | 77.24 | 64.32 | 58.38 | 69.18 | 49.21 |
| 256d | 60.41 | 67.78 | 76.18 | 63.13 | 56.24 | 66.76 | 48.91 |
| 128d | 57.89 | 65.68 | 71.41 | 59.06 | 45.65 | 56.71 | 46.92 |

Per modality at 768d (**READ**, card): MMEB v2 Image **57.28** Hit@1, VisDoc 67.84, **Video 50.67**, MTEB code 78.68 vs v1's 68.76. **Video is the weakest channel — 6.6 points below image** — and it is the channel the brief's headline demo rests on. 128d keeps ~90 % of text but drops image/video/speech to ~75 % (**READ**, developer guide), so the brief's choice of **256d** for the index is right.

---

## 4. How it runs locally, and what RAM/VRAM it costs

| runtime | formats | note |
|---|---|---|
| `sentence-transformers` **≥6.1.0** + `transformers` + `torchcodec` | safetensors, bf16/fp32 | reference path; **does not run here yet** (below) |
| ONNX Runtime / transformers.js | 3 encoders × 5 dtypes | WebGPU/WASM/CPU; Node must decode media itself (`Float32Array` + `RawVideo`); **WebGPU dispatch limit ≈2 700 tokens/batch** (>19 s video at 1 FPS) |
| **llama.cpp / GGUF** | text GGUF + `mmproj` | **merged**: [PR #30054](https://github.com/ggml-org/llama.cpp/pull/30054) "support embeddinggemma2 (text+vision+audio)" (2026-10-06) and [PR #29556](https://github.com/ggml-org/llama.cpp/pull/29556) (typed content for `/v1/embeddings`). Working shape `{"input":[{"content":[{"type":"image_url",…}]}]}`; cross-modal `cos(red_image,"a solid red square") = 0.7290`, 9 images in ~1.8 s (**READ**, #30082 close comment) |
| Ollama · LM Studio · vLLM · SGLang · MLX · LiteRT-LM | GGUF / server / mac / mobile | named by the launch blog; Ollama's own *Input* column lists only Text/Image per tag |

**This machine, MEASURED (no weights downloaded, by rule):** `transformers 5.15.0` is installed and **has no `EmbeddingGemma2Model`** (`hasattr` → `False`, no `embedding_gemma*` module) while `config.json` declares `transformers_version: 5.18.0.dev0` and PyPI's latest is 5.19.0; `sentence-transformers`/`torchcodec` are **absent** (`soundfile 0.14.0`, `av 18.0.0`, `PIL 10.4.0` present); `onnxruntime 1.30.0` lists `CUDAExecutionProvider`; there is **no HF cache at all**, so nothing on this box has run this model.

**Cost per module — file sizes from the ONNX card's dtype table (READ), _not_ memory:**

| tier | fp32 | fp16 | q8 | q4 | q4f16 |
|---|---|---|---|---|---|
| text 270M | 1 085 MB | 543 MB | 314 MB | 175 MB | 157 MB |
| vision 170M | 671 MB | 336 MB | 195 MB | 109 MB | 98 MB |
| audio 300M | 1 173 MB | 587 MB | 340 MB | 189 MB | 171 MB |
| **full 740M** | **2 929 MB** | **1 465 MB** | **850 MB** | **473 MB** | **426 MB** |

Text+vision (440M) is 1 756 / 879 / **509** / 284 / 255 MB. Resident weights ≈ those bytes at the chosen dtype (bf16 = 2 B/param: 744 371 488 × 2 ≈ 1 489 MB, the checkpoint exactly). **Peak RAM/VRAM is UNKNOWN and none of these numbers may be quoted as one** — this house already paid for that mistake: Sotto's Redux receipt measured **179 MB on disk costing 3.90 GB RSS** (`docs/research/04-asr.md` §2). Activations, per-frame vision buffers and the KV/sequence for up to 8 192 tokens are unmeasured; nobody has loaded this model anywhere on this box.

---

## 5. Licence and attribution

- `license: apache-2.0` on the reference repo and every mirror; the blog says *"released under the Apache 2.0 license"*, and the card's licence link resolves to [`ai.google.dev/gemma/apache_2`](https://ai.google.dev/gemma/apache_2) — the **verbatim stock Apache 2.0 text** (**READ**, fetched), *not* the Gemma Terms of Use.
- **Two things that are not Apache 2.0, both from the card:** deployments *"must adhere to the Gemma Prohibited Use Policy"*, and §6 grants **no trademark rights** — do not name the product "EmbeddingGemma".
- §4 duties when shipping: include the licence text, mark modified files, retain attribution notices, ship a NOTICE if one exists. **The repo ships neither `LICENSE` nor `NOTICE`** (full sibling list, sha `914f7f89…`), so we carry the text ourselves and credit "EmbeddingGemma 2, © Google DeepMind, Apache-2.0" in an about/licenses screen.
- **v2 is a licensing upgrade over v1:** `google/embeddinggemma-300m` is licensed `gemma` (Gemma Terms of Use) and its `model.safetensors` is **1 211 486 072 B** — the brief's line 53 figures (~308M, ~1.21 GB) verified exactly. Commercial shipping: **allowed, attribution only.**

---

## 6. If it did not serve — and the recommendation

It does serve; nothing else puts four modalities in one 768-d space under 1B on an Apache-2.0 grant. Alternatives, for the record: [`Qwen/Qwen3-VL-Embedding-2B`](https://huggingface.co/Qwen/Qwen3-VL-Embedding-2B) and 8B (apache-2.0, text+image, **no audio**, 3–10× the weights) · `nvidia/llama-nemotron-embed-vl-1b-v2` (licence `other`) · `jinaai/jina-embeddings-v4` (**UNKNOWN** — HF declares no licence and `?blobs=true` returned 401) · [`laion/clap-htsat-unfused`](https://huggingface.co/laion/clap-htsat-unfused) (apache-2.0, audio↔text only, second index).

**Ship EmbeddingGemma 2 and start at the text+vision (440M) tier:** the transcript already comes from Parakeet and the third channel is OCR, so the 300M audio encoder buys non-speech sound retrieval (explosions, music) for 340 MB q8 / 587 MB fp16 — enable it only if the owner wants "find the explosion", not "find where I spoke". Index **256d**; **one call per window** (5 s @ 1 FPS = 5 frames); feed frames from our own tap, never the MP4. Runtime: **llama.cpp GGUF** is the pragmatic Windows path (text Q8_0 310 MB + mmproj Q8_0 555 MB, no Python) — but its audio path prints *"experimental stage and may have reduced quality"*; **sentence-transformers** is the reference path once `transformers ≥5.19`, `sentence-transformers ≥6.1.0` and `torchcodec` are installed.

---

## 7. Traps, and what is still UNKNOWN

1. **Never run the PyTorch path in `float16`.** The card: activations exceed fp16's range and the model *"returns NaN or silently degraded embeddings rather than raising an error"*. Use **bfloat16** (default on this GPU) or fp32. Unresolved conflict: the ONNX export *does* ship `fp16` with a claimed worst-case cosine of 0.9998 — other stack, nobody here measured either.
2. **8 192 tokens is the contract; "256K" is a metadata artefact.** `config.json` says `max_position_embeddings: 262144` and Ollama advertises "256K", while the card, the guide and the context table all say **8 192**. Never size a window on 262 144.
3. **Ollama's audio/video support is unverified:** the page tags `audio`, but no tag's *Input* column lists anything beyond Text/Image. If we use Ollama, assume text+image until measured.
4. **Video is the weakest channel (50.67)** and 4-bit damages audio most (the ONNX card itself recommends q8 there).
5. **UNKNOWN, all ours to measure:** seconds and RSS/VRAM per window for text+vision and for video on this box; whether VRAM survives a game; whether 5 s windows retrieve the owner's moments at 256d. **The deciding measurement:** 200 s of the owner's own footage, 5 s windows, text+vision bf16, 20 hand-labelled queries — report RSS/VRAM, s/window and recall@5 at 768d vs 256d. This lane downloaded no weights, so nothing above is a claim about behaviour, only about the artefact.
