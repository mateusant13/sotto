# Receipt — `docs/qwen-model-choice.md`

**Lane:** research only. **Downloaded no model weights. Installed nothing. Deleted nothing.**
Did not touch `worker/**`, `app/**`, or `docs/qwen-hourly-plan.md`. Did not open an audio device,
did not launch the shell or the worker, left no visible window.

**Owned/created files:** `docs/qwen-model-choice.md`, `_main/receipt-qwen-model-choice.md`.
**Scratch created and removed:** one temp file (see §6, "scratch hygiene").

---

## 1. Local commands run, with their output

All on this box, 2026-10-07. Commands are given verbatim so they can be re-run.

### 1.1 What is already installed (MEASURED)

```
$ python -m pip list | Select-String "onnxruntime|llama|transformers|torch|openvino|ollama"
onnxruntime                              1.30.0
onnxruntime-genai                        0.17.1
onnxruntime-gpu                          1.30.0
torch                                    2.7.0+cu128
transformers                             5.15.0
# NO llama-cpp-python, NO llama.cpp, NO ollama, NO openvino-genai
```

```
$ python -c "import importlib.metadata as m; print(m.requires('onnxruntime-genai'))"
numpy>=1.21.6
onnxruntime>=1.20.1          # onnx_ir is NOT declared by the wheel
```

```
$ python -c "import importlib.util as u; print(u.find_spec('onnx_ir'))"
None                          # absent
$ python -m pip index versions onnx_ir
onnx_ir (1.0.0)
Available versions: 1.0.0, 0.2.1, 0.2.0, 0.1.16 ... 0.1.0
```

**This is the finding that corrects the plan's §1.1:** the *runtime* is present, so loading an
already-built ORT-GenAI bundle costs nothing — but the **builder** is broken here:

```
$ python -m onnxruntime_genai.models.builder --help
Traceback (most recent call last):
  File "...\onnxruntime_genai\models\builder.py", line 19, in <module>
    import onnx_ir as ir
ModuleNotFoundError: No module named 'onnx_ir'          [exit code: 1]
```

### 1.2 The builder's real architecture support (MEASURED, read from the installed wheel)

```
$ grep -n 'config.architectures\[0\] ==' builder.py
661: ChatGLMForConditionalGeneration / ChatGLMModel
669: GemmaForCausalLM      671: Gemma2ForCausalLM      674: Gemma3ForCausalLM
683: GptOssForCausalLM     688: Granite…               692: HunYuanDenseV1…
696: Lfm2ForCausalLM       698: Lfm2MoeForCausalLM
748: Qwen2ForCausalLM      754: Qwen3ForCausalLM   <-- the 0.6B path EXISTS
760: Qwen3_5ForConditionalGeneration    764: Qwen3_5MoeForConditionalGeneration
772: VideoChatFlashQwenForCausalLM
```

`builder.py:55` also imports `Qwen3Model` and `Qwen3VLTextModel`. **`NeedleForToolCalling` is
absent** — no dispatch case exists for it.

### 1.3 The shipped int8 ASR model, used as ground truth for the int4 node schema (MEASURED)

Census of `worker/models/nemotron-3.5-asr-streaming-0.6b-int8/encoder.onnx`:

```
ir_version 10   opset_imports [('', 21), ('com.microsoft', 1)]
  ('com.microsoft', 'MatMulNBits')     219
  ('ai.onnx', 'Transpose')             246
  ('ai.onnx', 'Add')                   183
  … (Conv 77, LayerNormalization 144)
first MatMulNBits node:
  inputs: ['_unsafe_view', 'val_121_Q8', 'val_121_scales', 'val_121_zero_point']   <-- FOUR inputs
  outputs: ['val_122_Q8']
  attrs: {'K': 4352, 'N': 1024, 'bits': 8, 'block_size': 32, 'accuracy_level': 4}
  init val_121_Q8          dtype 2 (uint8) dims [1024, 136, 32]
  init val_121_scales      dtype 1 (float) dims [139264]
  init val_121_zero_point  dtype 2 (uint8) dims [139264]
```

This is what made the synthetic int4 probe correct: `domain="com.microsoft"`, **four** inputs
(`zero_point` included), and the shapes `W=[N, K//block, bits*block//8]`,
`S=[N*K//block]` float32, `Z=[N*K//block*bits//8]`. Three earlier probe iterations failed on
schema details, and **all three failures were my probe's error, not a missing kernel** — recorded
here because the failure messages are misleading:

| probe error | misleading message | truth |
|---|---|---|
| node built without `domain="com.microsoft"` | `No Op registered for MatMulNBits with domain_version of 21` | the node was routed to ai.onnx opset 21; the com.microsoft domain declaration was missing |
| `W` shape `[N, K*bits//8//block, block]` | `B initializer shape {1024,68,32} does not match attribute-derived shape [1024,136,16]` | ITF: `[N, K//block, bits*block//8]` |
| `Z` shape `[N*K//block]` | `zero_points … does not match [69632] or [1024,68]` | int4 zero-points are 4-bit packed: `[N*K//block*bits//8]` |

### 1.4 THE MEASUREMENT — int4 vs int8 vs fp32 on this CPU (MEASURED)

```
$ python -c "<synthetic MatMulNBits graphs, com.microsoft domain, CPUExecutionProvider>"
bits=8 K=4352 N=1024 block=32 -> BOUND
512x2560x2560 int4 blk32:      12.0 ms    557.7 GFLOP/s   (attn proj, 0.7B-class)
512x1024x3072 int4 blk32:       5.2 ms    617.4 GFLOP/s   (Qwen3-0.6B mlp up)
512x2560x9216 int4 blk32:      40.8 ms    592.5 GFLOP/s   (Qwen3.5-4B mlp up)
2048x2560x2560 int4 blk32:     67.5 ms    397.9 GFLOP/s
512x2560x2560 int8  blk32:     42.2 ms    158.9 GFLOP/s
```

Against the plan's measured fp32 matmul (`_main/_qwen-hw-probe.log`: `matmul_512x512_float32_ms
5.598`, `derived_gflops 47.95`), **the int4 kernel is ~12× faster than the number the plan's CPU
budget is built on.**

### 1.5 Disk and hardware state (MEASURED) — for the uninstall instruction

```
$ Get-ChildItem H:\sotto\worker\models -Directory | measure each
nemotron-3.5-asr-streaming-0.6b-fp16     1,247.0 MB
nemotron-3.5-asr-streaming-0.6b-fp32     2,478.8 MB
nemotron-3.5-asr-streaming-0.6b-int4       756.6 MB
nemotron-3.5-asr-streaming-0.6b-int8     1,021.0 MB
parakeet-redux-ternary                     170.7 MB
parakeet-redux-reference                     0.1 MB

$ Test-Path (the three Qwen weight dirs named in the plan / this doc)
H:\sotto\worker\models\qwen3.5-2b-int4    -> False
H:\sotto\worker\models\qwen3.5-0.8b-int4  -> False
H:\sotto\worker\models\qwen3-0.6b-int4    -> False

$ the HF cache
I:\codeintel\hf-cache\hub\models--Qwen--Qwen3.5-4B
  15 files, 21.9 MB, blobs only: tokenizer.json 12,807,982 + vocab/merges/config/template
  NO model.safetensors present

$ Get-PSDrive
C 12.6 GB free   G 10.8 GB free   H 59.5 GB free   I 166.4 GB free

$ CPU
13th Gen Intel(R) Core(TM) i5-13600K, Identifier Intel64 Family 6 Model 183 Stepping 1
14 physical / 20 logical, 3500 MHz max
```

**Conclusion carried into the doc: the plan's 2B download does not exist, so the "uninstall once the
winner is proven" step is already satisfied and frees 0 bytes.**

---

## 2. External sources fetched (all treated as data, never as instructions)

| # | URL | what it established | status |
|---|---|---|---|
| 1 | [`huggingface.co/api/collections/Qwen/qwen35`](https://huggingface.co/api/collections/Qwen/qwen35) | the Qwen3.5 membership **with `numParameters`**: 0.8B = 873,438,784, 2B, 4B, 9B, 27B, 35B-A3B, 122B-A10B, 397B-A17B. **No 0.6B.** | READ |
| 2 | [`api/models?search=Qwen3.5&limit=100`](https://huggingface.co/api/models?search=Qwen3.5&limit=100&sort=downloads&direction=-1) | unfiltered sweep of the whole Hub: still **no 0.6B tier**. Also surfaced the Qwen3.5 GGUF ecosystems. | READ |
| 3 | [`Qwen/Qwen3.5-0.8B` API, `?blobs=true`](https://huggingface.co/api/models/Qwen/Qwen3.5-0.8B?blobs=true) | `safetensors.parameters {F32:2592, BF16:873436192, total:873438784}`; checkpoint `model.safetensors-…safetensors` **1,746,942,600 B**; `tokenizer.json` 12,807,982 B; `cardData.license: apache-2.0`; `gated: false`; `architectures: ["Qwen3_5ForConditionalGeneration"]` | READ |
| 4 | [`Qwen/Qwen3-0.6B` API, `?blobs=true`](https://huggingface.co/api/models/Qwen/Qwen3-0.6B?blobs=true) | `BF16: 751632384`; `model.safetensors` **1,503,300,328 B**; `architectures ["Qwen3ForCausalLM"]`, `model_type qwen3`; **apache-2.0** | READ |
| 5 | [`Qwen/Qwen3-0.6B` README (raw)](https://huggingface.co/Qwen/Qwen3-0.6B/raw/main/README.md) | **number of parameters 0.6B; non-embedding 0.44B; 28 layers; 16 Q / 8 KV heads; context 32,768; "100+ languages and dialects"**; thinking/non-thinking switch exists | READ |
| 6 | [`Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4` API, `?blobs=true`](https://huggingface.co/api/models/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4?blobs=true) | the exact artefact: `model.onnx` 331,869 B + **`model.onnx.data` 483,328,000 B** + `tokenizer.json` 11,422,650 B + `genai_config.json` 1,520 B; `downloads: 89, likes: 0`; **apache-2.0**; tags `arm`, `arm-optimized`, `cloud-cpu`, `int4` | READ |
| 7 | [`…/raw/main/genai_config.json`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/genai_config.json) | **`context_length: 40960`, `max_length: 40960`**, `type: qwen3`, 28 layers, hidden 1024, 16/8 heads, head_size 128, vocab 151,936, `past_present_share_buffer: true`, sampling 0.6/0.95/20 | READ |
| 8 | [`…/raw/main/README.md`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/README.md) | **MMLU 5-shot 45.18 % vs fp32 47.32 % (-2.14 pp, non-overlapping CIs)**; size 461.25 MB, **peak memory 838.22 MB**; TTFT 334.11 ms @ 127 tokens on Neoverse-V2 / 4 threads; GPTQ INT4 g=32 + int8 `k_quant_last` LM head + INT4-packed embedding via `GatherBlockQuantized`; validated on ORT-GenAI 0.14.1 / ORT 1.27.0; Arm's own words: *"not a production-ready or supported solution"* | READ |
| 9 | [`Cactus-Compute/needle3` API, `?blobs=true`](https://huggingface.co/Cactus-Compute/needle3?blobs=true) | `architectures: ["NeedleForToolCalling"]`, `model_type: needle`, tags `tool-calling`/`function-calling`/`webassembly`; `checkpoints/needle3.safetensors` 242,047,978 B; ships **native binaries per platform** (`windows-x86_64/needle.exe` 1,563,136 B, `linux-x86_64/needle`, `macos-arm64/needle`, `.wasm`, `.cact` 35,335,380 B) + a `cactus-needle` wheel; **apache-2.0**; 115,640 downloads, 304 likes | READ |
| 10 | [`api/models?search=Needle`](https://huggingface.co/api/models?search=Needle&limit=30&sort=downloads&direction=-1) | the whole Needle family: `needle` (jax, MIT), `needle2`, `needle3`, plus `needle-rs`, `needle-mlx`, `needle-tr` re-packagings — **all** tagged tool/function-calling | READ |
| 11 | [`api/models?search=gemma-3-270m`](https://huggingface.co/api/models?search=gemma-3-270m&limit=25&sort=downloads&direction=-1) | `google/gemma-3-270m-it`; GGUF/MLX/LiteRT quants exist | READ |
| 12 | [`api/models?search=gemma-3-270m&filter=onnxruntime-genai`](https://huggingface.co/api/models?search=gemma-3-270m&filter=onnxruntime-genai&limit=20) | **`[]` — no ORT-GenAI export of the 270M exists** | READ |
| 13 | [`google/gemma-3-270m-it` API](https://huggingface.co/api/models/google/gemma-3-270m-it) | `safetensors BF16: 268098176`; **`gated: "manual"`** with an "agree to Google's usage licence" gate; `cardData.license: gemma`; `architectures ["Gemma3ForCausalLM"]` | READ |
| 14 | [Google Developers Blog — *Introducing Gemma 3 270M*](https://developers.googleblog.com/en/introducing-gemma-3-270m/) | **"170 million embedding parameters … and 100 million for our transformer blocks"**; **"While this model is not designed for complex conversational use cases, it's a strong model that follows general instructions"**; value *"unlocked through fine-tuning"* for *"text classification and data extraction"* | READ |
| 15 | [`onnxruntime-genai` builder README (raw)](https://raw.githubusercontent.com/microsoft/onnxruntime-genai/main/src/python/py/models/README.md) | *Current Support* list = AMD OLMo, ChatGLM, DeepSeek, ERNIE 4.5, **Gemma**, gpt-oss, Granite, …, **LFM2**, **Llama**, Mistral, Nemotron, Phi, **Qwen**, **SmolLM3**, Whisper; the GGUF path (`-i path_to_gguf_file`); `block_size`, `algo_config`, `matmul_mixed_precision`, `kv_cache_quant_scheme`; **the Qwen3.5/3.8 paged hybrid state manifest is described as experimental** — *"requires coordinated Engine runtime work beyond the current onnxruntime-genai#2454 head and is not compatible with the merged runtime on its own"* | READ |
| 16 | [`api/models?search=Qwen3-0.6B&filter=onnxruntime-genai`](https://huggingface.co/api/models?search=Qwen3-0.6B&filter=onnxruntime-genai&limit=30) | community ORT-GenAI 0.6B exports exist (`SamTheDev/qwen3-0.6B-oga`, `xiaoyao9184/Qwen3-0.6B-onnx-genai`, …) — all 0 downloads; **Arm's is the only one with a published evaluation** | READ |
| 17 | [`LiquidAI/LFM2-350M` API, `?blobs=true`](https://huggingface.co/api/models/LiquidAI/LFM2-350M?blobs=true) | `BF16: 354483968`, `model.safetensors` 708,984,464 B; `architectures ["Lfm2ForCausalLM"]`; languages `en, ar, zh, fr, de, ja, ko, es` — **no pt**; **`license: other`, `license_name: lfm1.0`** | READ |
| 18 | [`ggml-org/Qwen3.5-0.8B-GGUF` API, `?blobs=true`](https://huggingface.co/api/models/ggml-org/Qwen3.5-0.8B-GGUF?blobs=true) | `gguf.context_length: 262144`, `architecture: qwen35`, `total 772,845,888`; files BF16 **1,557,662,496 B**, Q8_0 833,592,096 B, Q4_0 **563,036,064 B** (the size cross-check used for the 0.8B int4 estimate) | READ |
| 19 | [`api/models?author=Qwen&search=Qwen3.8`](https://huggingface.co/api/models?author=Qwen&search=Qwen3.8&limit=40) | Qwen3.8 = 27B, 27B-FP8, Flash-Next, 2.4T-A95B — **no small tier** | READ |
| 20 | [`api/models?author=Qwen&search=Qwen3.6`](https://huggingface.co/api/models?author=Qwen&search=Qwen3.6&limit=20) | Qwen3.6 = 27B, 35B-A3B (+FP8) — **no small tier** | READ |
| 21 | [HF discussion `Qwen/Qwen3.5-0.8B/discussions/6`](https://huggingface.co/Qwen/Qwen3.5-0.8B/discussions/6) | a user asking exactly the owner's question ("Is there a comparison between Qwen3.5-0.8B and Qwen3-0.6B?") — **the page body did not load under fetch; content TRUNCATED. Do not cite it as evidence.** Recorded here so nobody thinks a comparison was found. | UNREAD (failed) |
| 22 | [HF `smollm` repo `text/README.md`](https://raw.githubusercontent.com/huggingface/smollm/refs/heads/main/text/README.md) | SmolLM3 is **3B only**; **6 languages incl. Portuguese**; 128k context via NoPE+YaRN. SmolLM2 = 135M/360M/1.7B (older family, not in the builder's support list) | READ |
| 23 | [HF API `Qwen/Qwen3.5-4B` cache / local blob read](file:///I:/codeintel/hf-cache/hub/models--Qwen--Qwen3.5-4B) | local copy holds `config.json` (text_config: 32 layers, hidden 2560, `full_attention_interval: 4`, `layer_types` 3×linear + 1×full, head_dim 256, 16 Q / **4 KV** heads, `max_position_embeddings 262144`, vocab 248,320, mrope) and the tokenizer — **no weights** | MEASURED (local) |
| 24 | [`TinyLlama/TinyLlama-1.1B-Chat-v1.0/raw/main/config.json`](https://huggingface.co/TinyLlama/TinyLlama-1.1B-Chat-v1.0/raw/main/config.json) | **`max_position_embeddings: 2048`** (verified on the model's own config, not recalled), `vocab_size 32000`, 22 layers, 4 KV heads. Plus its API: `BF16: 1100048384`, `model.safetensors` 2,200,119,864 B, `language: ["en"]`. Confirms the row-6 exclusion: 2,048 context cannot hold a 6,634-token hour. | READ |
| 25 | [`transformers` `configuration_llama.py`](https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/models/llama/configuration_llama.py) | independently confirms `max_position_embeddings: int = 2048` is the Llama-class default, i.e. TinyLlama never raised it | READ |

### 2.1 Search engine calls

Four `web_search` batches (16 queries total) covering: the Qwen3.5 small release tiers;
ORT-GenAI Qwen3 exports; "Needle"; Gemma 3 270M instruction following; SmolLM/LFM2 tiers;
`gemma-3-270m` intended use; Qwen3.5-0.8B vs Qwen3-0.6B comparisons. **All returned only link
lists, no summaries.** Every factual claim in the doc therefore traces to one of the **fetched**
sources in §2 above — nothing rests on a search-result snippet.

---

## 3. MEASURED vs READ vs ESTIMATED — the ledger

### MEASURED on this box, today

| claim | instrument |
|---|---|
| `onnxruntime-genai 0.17.1` + `onnxruntime 1.30.0` + `onnxruntime-gpu 1.30.0` installed | `pip list` |
| the GenAI wheel declares only `numpy, onnxruntime` | `importlib.metadata.requires` |
| **`onnx_ir` is absent, and the builder cannot start without it** | `python -m onnxruntime_genai.models.builder --help` → `ModuleNotFoundError`, exit 1 |
| `onnx_ir` is installable, versions 1.0.0 … 0.1.0 | `pip index versions onnx_ir` |
| builder dispatches `Qwen3ForCausalLM` **and** `Qwen3_5ForConditionalGeneration`; does **not** dispatch `NeedleForToolCalling` | read of `builder.py` (installed wheel) |
| the shipped int8 ASR encoder uses **219** `com.microsoft` `MatMulNBits` nodes, 4-input schema, `block_size=32`, `accuracy_level=4`, ir_version 10, opsets `('',21)+('com.microsoft',1)` | `onnx.load` census |
| **int4 MatMulNBits is bound on `CPUExecutionProvider`, at 398-617 GFLOP/s** (4 shapes) | synthetic-graph inference + timing |
| int8 same shape = 158.9 GFLOP/s | same |
| **no Qwen weights anywhere on disk**; `worker/models/` holds only ASR artefacts; HF cache holds only the 4B tokenizer (21.9 MB, no safetensors) | directory walks + `Test-Path` on the three candidate paths |
| free disk C 12.6 / G 10.8 / H 59.5 / I 166.4 GB; CPU i5-13600K, 14 physical cores | `Get-PSDrive`, `Win32_Processor` |
| no scratch artefact left behind | `Test-Path` after delete (§6) |

### READ from an external source (URL in §2)

Every model id, parameter count, file size in bytes, `context_length`, licence, language list,
download count and every vendor performance/accuracy figure in the doc. Each is attributed inline
in `docs/qwen-model-choice.md` with its URL.

### ESTIMATED — labelled as such in the doc

| estimate | basis | confidence |
|---|---|---|
| 0.8B int4 built output **~500 MiB** | 0.8B-class int4; cross-checked against the same family's `Q4_0` GGUF at 563,036,064 B and against 0.6B int4 at 483,328,000 B (+3-15 % for embedding/LM-head policy) | medium |
| 2B int4 dir **~1.3-1.4 GiB** (the uninstall figure) | 2.27B/0.87B × ~500 MiB + tokenizer | medium; **explicitly marked not measured** because the tree does not exist |
| Gemma 3 270M int4 **~150-200 MiB** | 268M params × ~4.5 bits | low |
| per-model prefill seconds in §2 | measured int4 GEMM × an assumed 40-50 % prefill efficiency | **low-moderate; the doc says so in bold** |
| "~4.4× less capability-relevant compute for Gemma 270M than Qwen3-0.6B" | 440M vs ~100M non-embedding params, both vendor/API-sourced | medium (params are a proxy) |
| FLOP/token weights (1.5 / 1.75 / 4.5 GFLOP) | 2 × non-embedding params | standard arithmetic |

---

## 4. What I could NOT determine

1. **Whether the Arm Qwen3-0.6B int4 export loads and generates on this x86-64 box with ORT-GenAI
   0.17.1.** It is documented as Arm/aarch64-validated on 0.14.1. The int4 kernel binds here, but
   the export's `GatherBlockQuantized` INT4-packed embedding is a runtime-layout dependency I could
   not test without downloading. **This is the gate, and it is one 472 MiB download away.**
2. **Whether a locally built Qwen3.5-0.8B int4 export loads in the *released* runtime.** The
   builder's README contradicts itself constructively: it supports the architecture, but describes
   the hybrid state manifest as needing runtime work "beyond the current #2454 head" and "not
   compatible with the merged runtime on its own". 0.17.1 is the merged runtime.
3. **Whether a 0.6B/0.8B model produces a *useful* summary of an hour.** No benchmark, card, paper
   or discussion I found measures this. §4.2 of the doc says so in plain words. The MMLU figure is
   adjacent (knowledge recall), not on-target.
4. **Any end-to-end latency on this box.** No model was loaded. Only one GEMM primitive was timed.
5. **Build cost** (scratch GB, minutes) for an int4 conversion here, and whether `onnx_ir` 1.0.0 is
   API-compatible with the builder in 0.17.1. Not installed, not attempted.
6. **`Qwen/Qwen3.5-0.8B`'s text-only parameter split** (`text_config` vs the bundled vision tower).
   1.63 GiB / 873M params are the *total*; how much the builder would actually convert is unknown.
7. **Per-tier Portuguese quality for 0.6B or 0.8B.** Only a family-level "100+ languages" claim.
8. **`ggml-org/Qwen3.5-0.8B-GGUF`'s BF16 file is 1.56 GB while the HF checkpoint is 1.63 GiB** —
   consistent, but I did not verify that a GGUF is an acceptable `-i` input for a **Qwen3.5 hybrid**
   build specifically (the README documents the GGUF path generally).
9. **The one HF discussion page that asks our exact comparison question did not render.** Recorded
   as UNREAD rather than assumed (§2 row 21).

---

## 5. Judgement calls, stated so they can be rejected

| call | reasoning | what would overturn it |
|---|---|---|
| Recommend the **older-generation 0.6B community export** as the first artefact to try, not the newer 0.8B | it runs **today** with zero new installs and zero conversion; the 0.8B needs `onnx_ir` + a 1.63 GiB checkpoint + a build whose hybrid path the builder itself calls experimental. Cheapest path to the answer the plan says it needs. | if `Needle`-style arms-length evidence appears that 0.6B-class summaries are unusable, skip straight to 0.8B/2B |
| Treat the **plan's CPU latency model as superseded** | the plan's 47.95 GFLOPS is fp32; the int4 kernel measured here is ~12× that. The plan's `MAX = 3,072` and its "full hour does not fit the CPU budget" conclusion are derived from the wrong kernel. | one real end-to-end pass on the chosen model — the doc asks for exactly that |
| Keep the **engine decision unchanged (ORT-GenAI)** | every candidate except Needle either loads in ORT-GenAI as-is or can be built into it; no candidate needs Ollama/llama.cpp/vLLM/a server. Needle's exclusion removes the only runtime that would have changed the decision. | if the 0.6B export fails to load **and** the 0.8B build fails, revisit llama.cpp + GGUF, which is a genuinely second-best option the plan already documents |
| Rank **Gemma 3 270M below the 0.6B despite being smaller** | the vendor says it is not for this task; it is English-first where the job is Portuguese+English; its licence is gated; and its non-embedding compute is ~4.4× smaller than the 0.6B's. | a fine-tune specifically for this task — which is a *project*, not a download |
| Call the split design **legitimate and probably the right ship** | a title is a selection task; a summary is an abstraction task. Capability collapses first on abstraction. §2 shows the bigger pass is likely affordable. | if the 0.6B produces a whole-hour-covering summary on the falsifier in §4.4, the split is unnecessary complexity |

---

## 6. Scratch hygiene and the no-window rule

- **No visible window was created.** No GUI, no shell, no worker, no hotkey. Only `pwsh`
  command invocations and `python -c` one-liners; no `python.exe` was launched with a console window,
  no `Add-Type`/WinForms, no audio device.
- **One scratch file was created and removed.** `Join-Path $env:TEMP '_qmc_matmulnbits_probe.py'`
  was written for the first int4 probe. It executed **foreign content** (a JSON payload about
  `active_detail`, keys `measured_at_ms`/`cap`/`population`), i.e. **the temp path was already
  occupied by another process's artefact at that instant**. That was treated as noise from another
  lane, not as a result: the probe was abandoned, re-run **without a temp file** (`python -c`), and
  the path was checked afterwards.
  ```
  $ Test-Path 'G:\Temp\_qmc_matmulnbits_probe.py'   ->   not present
  ```
  **No file of this lane's remains on disk outside its two owned documents.** No file belonging to
  another lane was deleted — the path was verified empty before any write and after the delete.
- **No kill filter was used at all.** This lane ran no `Stop-Process`, no process census, no filter
  — so the "a kill filter names the ARTIFACT, never a generic word" rule had no opportunity to be
  violated. Nothing was killed.
- **No model weights were downloaded.** Every size in the doc comes from an API response
  (`?blobs=true`, `size` fields) or a local file listing.
- **No installs.** The `onnx_ir` install the builder needs was deliberately **not** performed.
- **Files touched:** created `docs/qwen-model-choice.md` and `_main/receipt-qwen-model-choice.md`.
  `docs/qwen-hourly-plan.md`, `worker/**` and `app/**` were **read-only and were not modified**.

---

## 7. Follow-up round: public quality evidence (appended to §7 of the doc)

Same rules held: no weights downloaded, no installs, nothing deleted.

### 7.1 New sources fetched

| # | URL | what it established |
|---|---|---|
| 26 | [`Qwen/Qwen3.5-0.8B/raw/main/README.md`](https://huggingface.co/Qwen/Qwen3.5-0.8B/raw/main/README.md) | **the 0.8B card DOES publish a full benchmark table** (~20 rows, thinking + non-thinking): MMLU-Pro 29.7, MMLU-Redux 48.5, SuperGPQA 16.9, IFEval 52.1, MMMLU 34.1, **AA-LCR 4.7**, **LongBench v2 26.1**, GPQA 11.9, HMMT `--`. Sibling column `Qwen3-1.7B` for scale. Also the **vendor-documented failure mode**: *"Qwen3.5-0.8B is more prone to entering thinking loops … which may prevent it from terminating generation properly."* Also: 24 layers, `6 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN))`, hidden 1024, FFN 3584, vocab 248320, context **262,144 natively**, and *"the intended use cases are prototyping, task-specific fine-tuning, and other research or development purposes."* | READ |
| 27 | [`Arm/qwen3-5-0-8b-q4-k-m-llamacpp-vivo-x300` README](https://huggingface.co/Arm/qwen3-5-0-8b-q4-k-m-llamacpp-vivo-x300) | **the Qwen3.5-0.8B int4-vs-f16 pair**: MMLU-Redux 2.0, test, **5330 samples, 0-shot** → optimized **50.49 %** vs baseline **50.53 %** = **−0.04 pp**; 504.78 MB vs 1446.48 MB. Recipe disclosed: K-quant `Q4_K_M`, 25 tensors promoted to Q6_K, **133 norm/SSM tensors kept FP32**, imatrix on 200 WikiText-2 samples. Also: *"The reported accuracy is a 0-shot, no-template, MCF measurement; figures produced under a different evaluation protocol are not directly comparable"* — the sentence that forbids the cross-model comparison. Runtime llama.cpp, NOT ORT-GenAI. | READ |
| 28 | [`Arm/…/benchmarks/qwen3-5-0-8b-llamacpp-vivo-x300-fp32.yaml`](https://huggingface.co/Arm/qwen3-5-0-8b-q4-k-m-llamacpp-vivo-x300/raw/main/benchmarks/qwen3-5-0-8b-llamacpp-vivo-x300-fp32.yaml) | the machine-readable baseline: `accuracy_pct: 50.525`, `shot_count: 0`, dataset `MMLU-Redux 2.0`, `sample_count: 5330` | READ |
| 29 | [`Arm/qwen3-0-6b-onnx-genai-int4…/benchmarks/…-int4.yaml`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/benchmarks/qwen3-0-6b-onnx-genai-graviton-g4-int4.yaml) | machine-readable: `accuracy_pct: 45.18`, `shot_count: 5`, dataset `MMLU` (cais/mmlu), `sample_count: 14042`, ORT 1.27.0 CPU + MLAS + KleidiAI, 4 threads | READ |
| 30 | [`Arm/qwen3-0-6b-onnx-genai-int4…/benchmarks/…-fp32.yaml`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/benchmarks/qwen3-0-6b-onnx-genai-graviton-g4-fp32.yaml) | machine-readable baseline: `accuracy_pct: 47.32`, `shot_count: 5`, `profile: Baseline` → the **−2.14 pp** figure is confirmed from the raw files, not just the card prose | READ |
| 31 | [`bartowski/Qwen_Qwen3.5-0.8B-GGUF` README](https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/raw/main/README.md) | **24 quants with file sizes** (bf16 1.56 GB … IQ2_M 0.40 GB) and **qualitative labels only** — *"Very high quality, near perfect, recommended"* — **no PPL, no KLD, no accuracy table.** This is the negative result for Q2 of the follow-up | READ |
| 32 | [`mradermacher/Qwen3.5-0.8B-i1-GGUF` API `?blobs=true`](https://huggingface.co/api/models/mradermacher/Qwen3.5-0.8B-i1-GGUF?blobs=true) | 25 files: the quants + `Qwen3.5-0.8B.imatrix.gguf` 1,134,720 B. **No results/perplexity file anywhere in the tree.** Second negative result for Q2 | READ (file listing) |
| 33 | [`unsloth.ai/docs/models/qwen3.5/gguf-benchmarks`](https://unsloth.ai/docs/models/qwen3.5/gguf-benchmarks) | attempted because a search result advertised a Qwen3.5 GGUF benchmark page | **UNREAD — the page body did not render under fetch (JS-rendered GitBook); truncated to nav only.** Recorded so nobody assumes a PPL table was read there |
| 34 | `web_search` ×2 (5 queries) on Qwen3-0.6B published MMLU/GSM8K/IFEval | returned link lists only, no numbers | **no published Qwen3-0.6B benchmark table found** — the absence is the finding |

### 7.2 Local measurements added this round

```
# the builder's missing dependency, sized (NOT a model weight)
$ python -m pip download onnx_ir==1.0.0 --no-deps -d <temp>
onnx_ir-1.0.0-py3-none-any.whl = 185,849 B (181 KiB)
<temp dir deleted afterwards; Test-Path -> removed: True>

$ python -c "find_spec('onnx_ir')"                     -> None
$ python -c "find_spec('optimum')"                     -> ModuleNotFoundError (absent)
$ pip list | grep -E "^optimum|onnxconverter|onnxscript|accelerate|^torch |^onnx "
accelerate 1.12.0   onnx 1.22.0   torch 2.7.0+cu128    # NO optimum, NO onnx_ir
```

**The 181 KiB figure is the answer to "what to install":** the builder needs `onnx_ir` only, the
GenAI wheel does not declare it, and it is a pure-Python 181 KiB wheel — not a multi-GB toolchain.
`optimum` is absent and is therefore the *avoidable* route; `transformers` + `torch` are already
installed and give the cheapest unquantized arm with no ONNX at all.

### 7.3 The comparison this round explicitly REFUSES to make

The temptation was to write "0.8B scores 50.5 vs 0.6B's 45.2 on MMLU → 0.8B is better". **It is not
a valid comparison** and the doc says so:

| | `Qwen3-0.6B` | `Qwen3.5-0.8B` |
|---|---|---|
| dataset | MMLU (`cais/mmlu`) | **MMLU-Redux 2.0** (`edinburgh-dawg/mmlu-redux-2.0`) |
| shot count | **5** | **0** |
| samples | **14042** | **5330** |
| runtime | ORT-GenAI, chat deployment mode | llama.cpp, no-template MCF |

Different dataset revision, different shot count, different sample count, different runtime,
different template. Arm's own card supplies the rule that settles it: *"figures produced under a
different evaluation protocol are not directly comparable."* **So the doc reports two independent
quantisation deltas (which each compare a model to ITSELF, and are therefore valid) and declines
to rank the two models on score.** The only cross-model statement it makes is an *absence* claim:
Qwen measured long-context and instruction-following for the 0.8B and for nothing smaller.

### 7.4 Changes this round made to earlier sections

- **§4.1's claim "no benchmark exists for this task" was too broad** and §7 now supersedes it for
  the 0.8B: benchmarks exist, they are simply not summarisation benchmarks. §4's honest core — that
  no published evaluation measures hour-long transcript abstraction — is unchanged and now
  quantified.
- **§4.1's architecture note is now exact** rather than inferred from a sibling: the 0.8B is
  **24 layers**, `6 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN))` — i.e. only
  **6 full-attention layers**, 2 KV heads, head_dim 256. This is the structure behind the
  builder's "experimental hybrid state manifest" caveat in §1.
- **New risk recorded (§7.3 of the doc, reason 2):** the vendor documents that `Qwen3.5-0.8B`
  **can fail to terminate** in thinking mode. That outranks any quantisation question.

### 7.5 Still UNKNOWN after this round

1. **Any published summarisation/titling/ROUGE evaluation for either model.** None found; the
   proxy (long-context retrieval) says the tier is weak.
2. **No confidence intervals on either quantisation delta.** A −2.14 pp gap over 14042 samples is
   reported bare. The doc therefore says the delta "may not even be resolvable at these sizes".
3. **The ORT-GenAI int4 delta for the 0.8B.** Arm measured Q4_K_M in **llama.cpp**; we would run
   `MatMulNBits` in **ORT-GenAI** with a different block size and coverage. Unmeasured.
4. **`Qwen3.5-0.8B`'s MMLU (5-shot) figure, to make the two tail-to-tail.** Qwen does not publish
   it; without it there is no valid cross-model number.
5. **Whether the `unsloth` GGUF benchmark page carries a PPL/KLD table** — it did not render. Not
   claimed either way.
6. **Wall-clock of an fp32/bf16 ONNX export here**, and whether `onnx_ir` 1.0.0 is
   API-compatible with the builder in 0.17.1. Still not attempted (no installs in this lane).
