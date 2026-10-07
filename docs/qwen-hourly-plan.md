# Qwen hourly title/summary — decision document

**Status:** RESEARCH + DESIGN ONLY. Nothing here is implemented; no model weights were
downloaded and nothing was installed. This document decides the engine, the model, the
hardware gate, the token budget and the hourly/cache design, with the numbers measured on
this box.

**Evidence markers used throughout — please keep them:**

| marker | meaning |
|---|---|
| **MEASURED** | produced by a probe in `_main/` on this machine today; the probe and its log are named |
| **DOCUMENTED** | read from an upstream spec, model card or API response; URL given |
| **ESTIMATED** | arithmetic on measured inputs with a stated model; **not** a benchmark |
| **UNKNOWN** | not determined. Deliberately not guessed |

Probes behind this document:

- [`_main/_qwen-hw-probe.py`](_qwen-hw-probe.py) → [`_main/_qwen-hw-probe.log`](_qwen-hw-probe.log)
  — the capability gate (the deliverable the owner asked for)
- [`_main/_qwen-cuda-init-probe.py`](_qwen-cuda-init-probe.py) → [`_main/_qwen-cuda-init-probe.log`](_qwen-cuda-init-probe.log)
  — why ORT cannot use the GPU here
- [`_main/_qwen-token-rate-probe.py`](_qwen-token-rate-probe.py) → [`_main/_qwen-token-rate-probe.log`](_qwen-token-rate-probe.log)
  — the token arithmetic, measured on the owner's own transcripts

Receipt of every command: [`_main/receipt-qwen-research.md`](receipt-qwen-research.md).

---

## 0. Decisions at a glance

| question | decision | why, in one line |
|---|---|---|
| Which engine? | **ONNX Runtime GenAI** — already installed | the runtime is already in the stack, and its own model builder lists `Qwen` as a supported architecture |
| What must be installed? | **Nothing to run the feature; one optional 3.7 GB model download** | `onnxruntime-genai 0.17.1` + `onnxruntime 1.30.0` are already present (**MEASURED**) |
| Should Ollama be installed? | **No** | it adds a second daemon and a second model store to do what the in-process runtime already does |
| Which model? | **`Qwen3.5-4B` int4** on a GPU tier, **`Qwen3.5-2B` int4** on the CPU tier | 4B is the largest that fits a comfortable VRAM budget; 2B keeps a CPU-only box inside the latency target |
| Is the feature available **on this machine**? | **YES — on CPU today** | CPU-only tier passes (14 physical cores, 17.5 GiB free RAM); the GPU tier is withheld only because ONNX Runtime cannot bind CUDA here |
| Why is the GPU withheld? | ORT 1.30.0 wants **CUDA 13**, this box has **CUDA 12.8** | `cublasLt64_13.dll` is missing, so the CUDA provider silently falls back to CPU (**MEASURED**) |
| Min tokens | **900** (~8 min of speech) | below that there is not enough content for both a title and a summary |
| Max tokens | **8,192** on this box (derived) | `min(context, VRAM/RAM budget, latency budget)` with the arithmetic shown in §4 |
| Language | **match the transcript, decided per hour from the text** | the transcript is sometimes English and sometimes Portuguese; a fixed choice would mistitle half of them |

---

## 1. Which engine — and does anything need installing?

### 1.1 What is already on this box (MEASURED)

```
$ python -m pip show onnxruntime-genai onnxruntime
Name: onnxruntime-genai            Version: 0.17.1
Name: onnxruntime                  Version: 1.30.0
```

`_main/_qwen-hw-probe.log`:

```
ONNX RUNTIME GENAI  (the drop-in path: no new runtime for a Qwen export)
  onnxruntime-genai version          0.17.1
  GenAI API present                  ['Model', 'Generator', 'GeneratorParams', 'Tokenizer', 'Config', 'MultiModalProcessor']
  GenAI can run a text LLM           [YES] an ORT-GenAI Qwen export would need exactly these
```

So the answer to *"does a decent engine need to be installed?"* is: **the engine is already
installed.** `onnxruntime-genai` is a text-generation runtime, not only an ASR runtime — the
same wheel that already serves the live Nemotron model exposes `Model`/`Generator`/
`GeneratorParams`, which is exactly the API a Qwen export needs. **MEASURED.**

### 1.2 The five engines compared

Disk figures are DOCUMENTED from the vendors' own package pages and model repos; the ORT-GenAI
row is MEASURED on this box.

| | **ONNX Runtime GenAI** (in-process) | **Ollama** | **llama.cpp / llama-server (GGUF)** | **vLLM** | **transformers + PyTorch** |
|---|---|---|---|---|---|
| **Install cost** | **0 MB — already installed** (MEASURED) | Windows installer (hundreds of MB) + a separate model store; the app is a full desktop bundle, not a library | a `llama-server.exe` release zip plus GGUF weights, or the `llama-cpp-python` wheel (~tens of MB) | multi-GB **CUDA** stack; DOCUMENTED Linux-first ([vLLM GPU install docs](https://docs.vllm.ai/en/v0.20.2/getting_started/installation/gpu/)) | `torch` + `transformers`; this box already carries torch 2.7.0+cu128 (**MEASURED**), a fresh install is multiple GB |
| **Daemon / service?** | **No.** In-process library | **Yes** — a background service that must be running | No for `llama-cpp-python` (in-process); yes for `llama-server` (an HTTP server process) | Yes (a server) | No |
| **How Python talks to it** | `import onnxruntime_genai as og` — direct calls | HTTP `localhost:11434` via the `ollama` package | `llama_cpp.Llama(...)` in-process, or HTTP to `llama-server` | HTTP | in-process |
| **Quantisation** | int4/int8 `MatMulNBits` (RTN, k-quant, AWQ/GPTQ import); `block_size`, `accuracy_level`, `is_symmetric`, KV-cache quant all exposed by the builder ([builder README](https://github.com/microsoft/onnxruntime-genai/blob/main/src/python/py/models/README.md)) | GGUF Q4_K_M / Q8_0 / MXFP8 / NVFP4 | GGUF, the widest scheme set (Q4_K_M, IQ4_XS, Q5_K_M …) | AWQ / GPTQ / FP8 | bitsandbytes / GPTQ, heaviest |
| **Windows support** | First-class (`pip install`, prebuilt wheels) | First-class (an installer) | First-class (prebuilt releases) | **Weak** — CUDA-Linux-first, best-effort on Windows | First-class |
| **Fit for an HOURLY BATCH job** | **Excellent** — one process, one `Model` object, can be cached and kept warm; no server to babysit | Good, but the daemon must stay resident or pay a cold start hourly | Good if `llama-cpp-python` in-process; a server is another lifecycle to manage | **Poor** — built for throughput serving, oversized for one job an hour | Poor — reloading a multi-GB torch model hourly is the worst latency |
| **GPU requirement** | Optional — CPU and CUDA both supported | Optional | Optional | **Effectively mandatory** | Optional |

### 1.3 Recommendation

> **Use ONNX Runtime GenAI.** *Reason:* the runtime is already installed as part of this stack,
> its model builder officially supports the `Qwen` architecture, and an hourly batch job wants
> an in-process library — not a second daemon (Ollama), a second server (llama.cpp's
> `llama-server`), a Linux-first CUDA stack (vLLM) or a multi-GB PyTorch dependency.

**What I would install ONLY if the hardware passes the gate:** the **model weights**, and nothing
else. Specifically `Qwen3.5-4B` converted to the ORT-GenAI int4 format (§2.3), ~3.7 GB, into
`worker/models/`. If the gate says `unavailable`, **nothing at all is installed or downloaded** (§6).

**Honest counter-arguments, and why they do not change the verdict:**

- **Ollama's ergonomics are genuinely better** — `ollama pull qwen3.5:4b` and you are done, with a
  huge tested tag matrix (§2.2). It loses on the one thing that matters here: it is a **second
  daemon** and a **second model store** for a job that runs 24 times a day in a process that is
  already alive.
- **llama.cpp has the best quantisation menu**, including `IQ4_XS` and `Q4_K_M` (§2.2), and its
  GGUF files are the ones that actually exist for Qwen3.5-4B today. This is the strongest
  argument against the ORT-GenAI route, and it is a real one. It is answered by §2.3: the
  ORT-GenAI **model builder can eat a GGUF file directly** (`-i path_to_gguf_file`), so the
  GGUF quantisation ecosystem is reachable *without* adopting llama.cpp as a runtime.
- **vLLM is the wrong shape entirely** for one batch job an hour on a single desktop GPU.
- **`transformers` + PyTorch** is the only option that needs no conversion step (point it at
  `Qwen/Qwen3.5-4B` and generate), but it pays a multi-GB dependency and the slowest per-invocation
  load for a job whose entire value is being cheap and occasional.

---

## 2. Is "Qwen 3.5" real, and what tags exist?

**Yes — "Qwen 3.5" is a real, current model family.** It is not a misremembering of Qwen3.
**DOCUMENTED**, verified against Qwen's own Hugging Face organisation:

- Collection `Qwen/Qwen3.5`: <https://huggingface.co/collections/Qwen/qwen35>
- The collection's own API response (fetched) lists the members, with parameter counts.

### 2.1 Real model ids and sizes (DOCUMENTED)

| model id | parameters | HF | licence |
|---|---|---|---|
| `Qwen/Qwen3.5-0.8B` | 873,438,784 | [card](https://huggingface.co/Qwen/Qwen3.5-0.8B) | Apache-2.0 |
| `Qwen/Qwen3.5-2B` | 2,274,069,824 | [card](https://huggingface.co/Qwen/Qwen3.5-2B) | Apache-2.0 |
| `Qwen/Qwen3.5-4B` | 4,659,865,088 | [card](https://huggingface.co/Qwen/Qwen3.5-4B) | Apache-2.0 |
| `Qwen/Qwen3.5-9B` | 9,653,104,368 | [card](https://huggingface.co/Qwen/Qwen3.5-9B) | Apache-2.0 |
| `Qwen/Qwen3.5-27B`, `-35B-A3B`, `-122B-A10B`, `-397B-A17B` | 27.8B … 403B | [collection](https://huggingface.co/collections/Qwen/qwen35) | Apache-2.0 |

Every `cardData.license` queried for the small tiers returned `apache-2.0` (**MEASURED**, HF API).
There are also `-Base` variants (pretrained, no instruction tuning) — **do not use those**; the
feature needs an instruct model.

**Beyond 3.5:** Qwen has since published `Qwen3.6` and `Qwen3.8` collections, listed on the same
organisation page. So **Qwen3.5 is not the newest family** — it is the newest with a mature
small-model + tooling ecosystem. Newer is not automatically better here: §2.3 shows the ORT-GenAI
model builder explicitly supports Qwen3.5/3.8 recurrent ops, so 3.5 is a safe, supported target.

### 2.2 Ollama and GGUF tags that actually exist (DOCUMENTED)

**Ollama library — `qwen3.5` exists, with a large tag matrix**
(<https://registry.ollama.com/library/qwen3.5/tags>). Exact tags, fetched:

```
latest, 0.8b, 2b, 4b, 9b, 27b, 35b, 122b,
0.8b-q8_0, 0.8b-bf16, 0.8b-mxfp8, 0.8b-nvfp4, 0.8b-mtp-q8_0,
2b-q4_K_M, 2b-q8_0, 2b-bf16, 2b-mxfp8, 2b-nvfp4, 2b-mtp-q4_K_M,
4b-q4_K_M, 4b-q8_0, 4b-bf16, 4b-mxfp8, 4b-nvfp4, 4b-mtp-q4_K_M, 4b-mtp-q8_0,
9b-q4_K_M, 9b-q8_0, 9b-bf16, 9b-mxfp8, 9b-nvfp4, 9b-mtp-q4_K_M, 9b-mtp-q8_0, ...
```

So the natural Ollama ids would be `qwen3.5:4b`, `qwen3.5:4b-q4_K_M`, `qwen3.5:2b-q4_K_M`, etc.
**Not used in the recommendation**, but this is the fallback if the ORT-GenAI route is ever blocked.

**GGUF file sizes — MEASURED from the HF API** (`unsloth/Qwen3.5-*-GGUF`, `gguf.architecture`
`qwen35`, `context_length` 262144):

| repo | quant | file size |
|---|---|---|
| `unsloth/Qwen3.5-4B-GGUF` | `Q4_K_M` | **2,614.0 MiB** |
| `unsloth/Qwen3.5-4B-GGUF` | `Q8_0` | 4,274.8 MiB |
| `unsloth/Qwen3.5-4B-GGUF` | `BF16` | 8,034.1 MiB |
| `unsloth/Qwen3.5-2B-GGUF` | `Q4_K_M` | **1,221.5 MiB** |
| `unsloth/Qwen3.5-0.8B-GGUF` | `Q4_K_M` | **507.8 MiB** |
| `unsloth/Qwen3.5-9B-GGUF` | `Q4_K_M` | 5,417.4 MiB |

Note `pipeline_tag` is `image-text-to-text` on all of them: Qwen3.5 is a **multimodal** family.
The `mmproj-*.gguf` files are the *vision* projectors — **the text-only job does not need them**,
which is why the sizes above are quoted per-file and not per-repo.

### 2.3 ORT-GenAI builds — what exists, and the honest state of it

**The ONNX Runtime GenAI model builder officially supports this architecture.**
**DOCUMENTED:** the "Current Support" list in
<https://github.com/microsoft/onnxruntime-genai/blob/main/src/python/py/models/README.md> includes
**`Qwen`**, and the same README has Qwen3.5-specific sections — *"MTP Head (Qwen3.6)"*,
*"Compact State Updates (Qwen3.5/3.8)"*, *"Select the Qwen3.5/3.8 Recurrent Operator"*, and a note
that Qwen3.5/3.8 uses packed position IDs of shape `[3, num_tokens]` for paged attention. A model
family does not get dedicated builder options and a purpose-built recurrent operator unless it is a
supported target.

**Prebuilt ORT-GenAI Qwen3.5 exports do exist, but only as a thin amateur ecosystem.**
**MEASURED** via the HF API (`?search=Qwen3.5&filter=onnxruntime-genai`), and the download counts
are the point:

| repo | layout | downloads | likes |
|---|---|---|---|
| [`md-bogush/Qwen3.5-4B-onnx-int4-cuda`](https://huggingface.co/md-bogush/Qwen3.5-4B-onnx-int4-cuda) | ORT-GenAI int4, CUDA-oriented | 14 | 0 |
| [`Prince-1/Qwen3.5-4B-Onnx`](https://huggingface.co/Prince-1/Qwen3.5-4B-Onnx) | ORT-GenAI, includes a vision encoder | 8 | 0 |
| [`Prince-1/Qwen3.5-0.8B-Onnx`](https://huggingface.co/Prince-1/Qwen3.5-0.8B-Onnx) | ORT-GenAI, `cpu/` + `cuda/` subfolders | 0 | 0 |
| [`onnx-community/Qwen3.5-9B-Onnx`](https://huggingface.co/onnx-community/Qwen3.5-9B-Onnx) | ORT-GenAI | 24 | 0 |

The `onnx-community/Qwen3.5-4B-ONNX` repo — which looks official — is **not** this format: it is
`transformers.js` split-model format (`decoder_model_merged*.onnx`, `embed_*`, `vision_encoder_*`,
`onnx_data_1..7`) and carries **no `genai_config.json`** (**MEASURED**, sibling listing). It is not
loadable by ORT-GenAI as-is.

`md-bogush/Qwen3.5-4B-onnx-int4-cuda` **is** the right shape (**MEASURED**, recursive tree):

```
genai_config.json          1,829 B      <- the ORT-GenAI model config: this is the marker
model.onnx                   644 KB      <- the graph ONLY
model.onnx.data            3,709,272,064 B (3.45 GiB)  <- THE WEIGHTS
tokenizer.json            19,989,325 B
```

**That is the same trap AGENTS records for the ASR models:** `model.onnx` is 644 KB while the real
weights are the 3.45 GiB sidecar — a listing that shows only the `.onnx` understates the download
by ~5,800×. **Quoted download size: ~3.71 GB.**

**Verdict on §2.3 — the honest position.** There is no *first-party, well-tested* ORT-GenAI Qwen3.5
export. Both viable routes are therefore:

1. **Build it locally with the builder that is already installed** (preferred — it is the supported
   path, it is deterministic, and it can consume a GGUF or the PyTorch checkpoint):
   ```
   python -m onnxruntime_genai.models.builder -m Qwen/Qwen3.5-4B -o <out> -p int4 -e cpu --extra_options block_size=32
   ```
   Cost: the 8.70 GiB FP16 checkpoint in the HF cache, converted once, then the checkpoint can be
   deleted. **ESTIMATED** ~30–60 min and ~20 GB peak scratch — **not measured** (no download was
   authorised).
2. **Use a community export** (`md-bogush/…`, 3.71 GB) and **verify it** before trusting it —
   load it, run one prompt, check `genai_config.json` names the right provider. Downloads 14,
   likes 0: treat it as unvetted input, and record its sha256 in the receipt when it is fetched.

**This is the single biggest UNKNOWN in the plan.** The fact that a supported conversion path
exists in the installed wheel is **DOCUMENTED**; that a Qwen3.5-4B int4 build **actually produces a
model that loads and generates** on this box is **UNVERIFIED** — verifying it requires the
download, which this lane did not perform. **The first implementation step must be a gate that
proves the model generates one sentence before the hourly job is wired to it.**

---

## 3. The hardware gate, MEASURED on this box

`_main/_qwen-hw-probe.py` is the deliverable that implements the owner's rule — **a wrong GPU
detection is forbidden**, so it is built on one principle:

> **A capability QUERY is not evidence. Only PERFORMING the capability is.**
> Every library's own claim (`torch.cuda.is_available()`, `ort.get_available_providers()`,
> WMI `AdapterRAM`) is recorded as a labelled **HINT**, and is never the verdict on its own.

That rule is not paranoia. Three vendor/runtime probes on **this one machine** gave three
different answers, one of them a lie (§3.4).

### 3.1 Raw probe output (MEASURED, verbatim from `_main/_qwen-hw-probe.log`)

```
CAPABILITY: CUDA / NVIDIA GPU
  nvidia-smi  : nvidia-smi
    | NVIDIA GeForce RTX 5080, 16303, 11224
  pynvml/NVML : 1 device(s)
    | #0 NVIDIA GeForce RTX 5080 total=16303.0 MiB free=11224.1 MiB
  torch       : version=2.7.0+cu128 is_available()=True  [HINT]
    | mem_get_info #0 free=14987.0 MiB total=16275.4 MiB
    | ALLOCATION PERFORMED: torch.zeros(1, device='cuda') OK, memory_allocated=512 B
  NOTE: free VRAM varies by method (live value, not a defect): nvidia-smi=11224 MiB,
        pynvml=11224 MiB, torch=14987 MiB -- gate uses the most conservative: 11224 MiB from pynvml

  OOM honesty probe (bounded, does not touch driver over-commit):
    cap_fraction: 0.1   cap_gib: 1.59   asked_gib: 6.36   free_gib_before: 14.57
    result: OOM raised cleanly (this is the CORRECT behaviour)
    exception_type: OutOfMemoryError
    failed_after_seconds: 0.027
    recovered: True

CAPABILITY: ONNX Runtime execution providers (what the stack ALREADY uses)
  onnxruntime 1.30.0
    get_available_providers() = ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']   [HINT, not a verdict]
    get_device()              = GPU   [HINT]
    CUDAExecutionProvider        advertised=YES  SESSION BOUND=NO   (session bound ['CPUExecutionProvider'] instead)
    TensorrtExecutionProvider    advertised=YES  SESSION BOUND=NO   (session bound ['CPUExecutionProvider'] instead)
    CPUExecutionProvider         advertised=YES  SESSION BOUND=YES

CAPABILITY: CPU (cores, SIMD)
  CPU model        : 13th Gen Intel(R) Core(TM) i5-13600K
  physical/logical : 14 / 20  (WMI Win32_Processor.NumberOfCores)
  AVX2 feature flag: True  [HINT]
  PERFORMED matmul : {'matmul_512x512_float32_ms': 5.598, 'derived_gflops': 47.95}
  GFLOPS/physical-core: 4.98

CAPABILITY: system RAM
  total 47.74 GiB  available 16.03 GiB  load 66%

GATE DECISION
  path                 : cpu-only-adequate
  compute              : ort-cpu
  available            : True
  recommended model    : Qwen3.5-2B int4 (CPU)
  DOWNLOADS PERMITTED  : True
  reason               : cpu-only-adequate via ort-cpu: ort_gpu_provider_bound=False,
                         torch_cuda_usable=True, vram_free=10.8 GiB, ram_free=16.0 GiB,
                         physical_cores=14; NOTE: a usable CUDA GPU EXISTS (torch allocated on it)
                         but ONNX Runtime cannot bind it, so the GPU tier is withheld until the
                         ORT CUDA 13 / cuDNN 9 dependency is installed
```

Also MEASURED: GPU is an **NVIDIA GeForce RTX 5080, 16,303 MiB total**, driver **617.14**; an
Intel UHD Graphics 770 iGPU is also present; free disk **59.7 GB on `H:`** and **20.1 GB on `C:`**.

### 3.2 Why ONNX Runtime cannot use the GPU — the raw cause (MEASURED)

This is the contradiction AGENTS predicted, now with the mechanism. From
`_main/_qwen-cuda-init-probe.log`, ORT's own verbose refusal:

```
[E:onnxruntime:Default, provider_bridge_ort.cc:2395 onnxruntime::TryGetProviderInfo_CUDA]
  ... Error loading "...\onnxruntime\capi\onnxruntime_providers_cuda.dll"
  which depends on "cublasLt64_13.dll" which is missing. (Error 126: ...)

[W:onnxruntime:Default, onnxruntime_pybind_state.cc:1294]
  Failed to create CUDAExecutionProvider.
  Require cuDNN 9.* and CUDA 13.*, and the latest MSVC runtime.
```

and the corroborating environment census:

```
CUDA_PATH = C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8
cudart64_12.dll / cudart64_13.dll / cublas64_12.dll / cublasLt64_12.dll /
cudnn64_9.dll ... -> not loadable
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA -> 0 match(es)
```

**Diagnosis:** `onnxruntime 1.30.0` (the CUDA-enabled wheel — it ships a 184 MB
`onnxruntime_providers_cuda.dll`) is built against **CUDA 13** and **cuDNN 9**. This box has the
**CUDA 12.8** toolkit and **cuDNN absent**. The provider DLL therefore cannot load its dependency,
and ORT does what it always does: **silently falls back to CPU**, while
`get_available_providers()` still lists CUDA and `get_device()` still says `GPU`.

**The fix, if the GPU tier is wanted:** install the CUDA 13 runtime + cuDNN 9 DLLs (either the full
toolkits, several GB, or the `nvidia-cublas-cu13` / `nvidia-cudnn-cu13`-style pip packages) so
`cublasLt64_13.dll` and `cudnn64_9.dll` resolve. **Not done — no installs in this lane.** Cost is
**UNKNOWN** (not downloaded); it is a one-time runtime install, not a model.

### 3.3 Availability verdict for THIS machine

> **The feature IS available on this machine.** Path `cpu-only-adequate`, recommended model
> `Qwen3.5-2B int4`, downloads permitted.
>
> The GPU tier (`gpu-mid`, `Qwen3.5-4B int4`) is **withheld, not denied**: the gate reports
> `gpu_exists_but_runtime_cannot_use_it: true` and says exactly why, so the owner can unlock it
> with the CUDA 13 install in §3.2 without redesigning anything.

**Roughly how long an hourly pass would take — ESTIMATED, arithmetic shown.**

Inputs: **6,634 tokens** for a full hour (§4), **~185 output tokens** for a title + summary, and
the **MEASURED** CPU throughput of **47.95 GFLOPS** at 512³ float32.

*A 4B int4 model needs ~2 FLOP per parameter per generated token:*

```
4.66e9 params × 2 FLOP = 9.3 GFLOP per token (decode)
47.95 GFLOP/s (MEASURED)  ->  9.3 / 47.95 = 0.19 s per generated token   [CPU, optimistic]
```

**CPU, 4B int4: 185 tokens × 0.19 s ≈ 36 s of decode, plus prefill.** Prefill is one pass over
6,634 tokens; a CPU prefill is typically several times the cost of one decode step, so:

```
prefill ≈ 6,634 tokens × ~0.05 s/token ≈ 330 s   [ESTIMATED, not measured]
total   ≈ 330 + 36 ≈ 6 minutes on CPU for a 4B   [ESTIMATED]
```

That is why the gate recommends **2B on the CPU tier**: halving the parameter count roughly halves
both terms →

```
CPU, 2B int4:  prefill ≈ 165 s + decode ≈ 18 s ≈ 3 minutes per hourly pass   [ESTIMATED]
```

```
GPU, 4B int4 (if §3.2 is fixed), RTX 5080:  prefill ~2-4 s + decode ~2 s ≈ under 10 s   [ESTIMATED]
```

**Marked ESTIMATED, and deliberately so:** these are FLOP-count models, not benchmarks. The
MEASURED inputs are the 47.95 GFLOPS and the 6,634-token budget; the per-token cost of an int4
`MatMulNBits` kernel and the prefill scaling are assumed. **Before shipping, measure one real pass
and replace these numbers.**

**Sustainable?** Yes: even the pessimistic 6-minute CPU figure is 10% of an hour, on a machine
whose 14 physical cores are mostly idle while the live ASR worker holds one. The job must still be
**nice**d and must not run while the panel is in active use (§5.6).

### 3.4 The detection design — and the robustness tests

The gate's rule is *perform, do not ask*. Concretely:

| capability | method (the thing PERFORMED) | hint that is NOT trusted |
|---|---|---|
| CUDA device exists | `nvidia-smi --query-gpu` **and** `pynvml.nvmlDeviceGetMemoryInfo` **and** `torch.cuda` — cross-checked, and `torch.zeros(1, device='cuda')` actually allocated | `torch.cuda.is_available()` |
| VRAM free | the **smallest** of the methods' readings (conservative) | — |
| ORT can use the GPU | **create an `InferenceSession` on the provider and read back `sess.get_providers()`** | `get_available_providers()`, `get_device()` |
| CPU SIMD | **a performed float32 512³ matmul**, calibrated per physical core | `IsProcessorFeaturePresent(40)`, CPU brand string |
| RAM | `GlobalMemoryStatusEx` | — |

**The `nvidia-smi`-is-not-on-PATH case is handled explicitly and MEASURED:** the probe tries
`nvidia-smi` on PATH, then `C:\Windows\System32\nvidia-smi.exe`, then
`C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe`; **absence is reported as
"NOT USABLE", never as "no GPU"**. Robustness test A (`--no-smi-on-path`) **passed** — the verdict
stayed `ok` and the GPU was still found via NVML + torch:

```
MODE: --no-smi-on-path (robustness self-test: nvidia-smi simulated ABSENT)
  nvidia-smi  : NOT USABLE -- SIMULATED: nvidia-smi treated as absent
  pynvml/NVML : 1 device(s)
    | ALLOCATION PERFORMED: torch.zeros(1, device='cuda') OK
  [OK  ] cuda_gpu
         method     : pynvml(NVML)+torch.cuda (cross-checked)
```

**The forbidden reading, demonstrated on this very box.** `Win32_VideoController.AdapterRAM` is a
uint32 and wraps above 4 GB. MEASURED here:

```
| NVIDIA GeForce RTX 5080|4293918720|      <- 4,293,918,720 B = 3 GiB 16 B : the uint32 WRAP
| Intel(R) UHD Graphics 770|2147479552|
rows_showing_the_wrap: ["NVIDIA GeForce RTX 5080"]
```

A 16 GB card reporting **3 GiB**. The probe records this only to demonstrate the trap and marks it
`"trust": "FORBIDDEN as a VRAM reading -- uint32 wraps above 4 GB"`. Sources:
[Mesh-LLM #1811](https://github.com/Mesh-LLM/mesh-llm/issues/1811),
[llmfit PR #831](https://github.com/AlexsJones/llmfit/pull/831).

**Method-disagreement handling.** On the first run the gate flagged
"VRAM free disagrees: nvidia-smi=12835 vs torch=14987" as a `degraded` verdict. On review that was
**a false alarm**: free VRAM is a *live* value and different runtimes snapshot it at different
instants — that is not a defect, and flagging it would train the reader to ignore the word. The
logic now separates the two:

- **VRAM TOTAL** is the authoritative cross-check (a stable device property). A >2% spread is a
  genuine discrepancy.
- **VRAM FREE** differences are reported as an explanatory **NOTE**, and the gate uses the
  **most conservative** reading. This matters directly: an over-reported free-memory figure is the
  dangerous direction, because it would promise a tier the box cannot actually run.

**The third required test — "query says yes, allocation says no" — PASSED.** Armed with
`SOTTO_PROBE_SIMULATE_TORCH_OOM=1`:

```
| ALLOCATION SIMULATED-FAILED (robustness self-test armed)
[DEGR] cuda_gpu
       method     : nvidia-smi+pynvml(NVML)+torch.cuda (methods DISAGREE)
       reason     : SIMULATED: torch.cuda.is_available()=True but the allocation was refused
GATE DECISION
  path                 : cpu-only-adequate
  available            : True
  DOWNLOADS PERMITTED  : True
```

The disagreement is surfaced as evidence, the `ok` verdict is **withdrawn**, and the machine still
gets a correct `available` answer on the CPU path instead of a false negative. The bound OOM probe
also confirmed **clean, fast failure** with recovery: `OutOfMemoryError` after **0.027 s**,
`recovered: True`, free VRAM restored.

> **A note on that OOM probe — it was fixed after it nearly took the box down.** The first version
> asked the driver for a flat **64 GiB**, which did not fail; it **thrashed the machine** (driver
> pagefile over-commit) and had to be killed. It is now bounded by
> `torch.cuda.set_per_process_memory_fraction(0.10)` and asks for 4× that cap, so the OOM is raised
> **inside the caching allocator** with no driver over-commit. A probe that can take down the box it
> measures is not a probe.

**The vendor-probe that lied, quoted as the design's justification.** kestrel's
`_cpu.ternary_gemm_isa()` returns `'scalar'` on this i5-13600K, which **has** AVX2 — because the
compiled kernel sits in a protected payload whose key is not shipped (AGENTS, `receipt-redux-ternary.md`).
Our own probe's AVX2 *hint* agrees with reality here, but the point stands: had we trusted a vendor
probe, we would have wrongly concluded the CPU was scalar-only.

---

## 4. The token arithmetic, shown

### 4.1 The measured transcript rate

**MEASURED** by `_main/_qwen-token-rate-probe.py` over the owner's own archive
(`history/<date>/<hour>.md`, 9 files, 2,072 lines), counting tokens with the **real
`Qwen/Qwen3.5-4B` tokenizer** from the local HF cache (offline, `HF_HUB_OFFLINE=1`, no download):

```
file                lines    span  ln/min  ch/line   raw tok  dedup tok  dedup%
15.md                 487   59.4m     8.2     57.4     7,875      7,787   98.9%
16.md                 560   48.1m    11.6     61.3     9,768      9,695   99.3%
19.md                 390   21.6m    18.1     79.9     7,320      7,299   99.7%
...
TOTAL                2072                             29,738     29,410   98.9%

lines per minute (mean)                  : 8.04
lines per minute (min / max)             : 0.94 / 18.06
seconds of speech per line (mean)        : 7.46
characters per line (mean)               : 49.5
DEDUP tokens per minute of transcript    : 110.6
DEDUP tokens per 60-minute hour          : 6,634
DEDUP tokens per 40 minutes (4:40 case)  : 4,423
```

Note the rate is measured **per minute of transcript**, which is the right denominator — these
files only contain minutes in which something was said. It is therefore a **density**, not a
guarantee that any given hour reaches it. The min/max span (0.94 → 18.06 lines/min) is a 19× swing
and is why the gate is a token count and not a duration.

### 4.2 MIN — the smallest transcript worth a title + summary

**Derivation, in tokens and in speech:**

```
MIN = 900 tokens

in speech:  900 / 110.6 tok/min = 8.1 minutes of content
in lines :  8.1 min × 8.04 lines/min ≈ 65 closed lines
```

**Why 900.** A useful title is ~8–15 tokens, a three-sentence summary ~80–150 tokens, and the
prompt plus instructions ~120 tokens; call the irreducible request overhead ~250 tokens with a
safety margin. Leaving ~650 tokens of transcript is the point at which summarisation stops being
degenerate — below roughly 400 tokens of content a 2B-class model reliably either echoes the input
or invents a subject. 900 also sits **above** the transcript's own noise floor: at the measured
0.94 lines/min minimum, a whole hour yields only ~56 lines ≈ 560 tokens, so **a near-idle hour will
correctly be skipped** rather than titling 40 seconds of silence.

**MIN is deliberately a constant, not hardware-derived.** The owner asked for the MAX to be derived
from the hardware; the MIN is a property of *the text*, not of the machine — a weak box reading the
same 900 tokens wants the same decision. Tying MIN to hardware would make a weak machine title
*larger* transcripts more eagerly, which is backwards.

### 4.3 MAX — derived from the measured hardware

**Formula:**

```
MAX = min( context_window_model , budget_from_memory , budget_from_latency )   rounded down to 1024
```

**Term 1 — the model's context window.** Qwen3.5's GGUF metadata reports
`context_length = 262144` **DOCUMENTED** (`unsloth/Qwen3.5-4B-GGUF`). Not binding. **Important
caveat:** the ORT-GenAI export we would actually load has its own `genai_config.json`, and its
`context_length` is **UNKNOWN** until a built model is inspected — a locally built int4 export
often ships a much smaller default than the base model's 262k.

**Term 2 — the memory budget.** This is the term the owner meant. On this box, MEASURED:

```
VRAM total            = 16,303 MiB   (nvidia-smi + NVML, cross-checked)
VRAM free at measure  = 11,224 MiB   (conservative: the smaller of NVML 11,224 / torch 14,987)
reserve for display   =  2,048 MiB   (a desktop WDDM card always holds this much)
usable VRAM           = 11,224 - 2,048 = 9,176 MiB

weights (Qwen3.5-4B int4) = 3,709,272,064 B / 2^20 = 3,538 MiB   (MEASURED, md-bogush export)
KV cache, fp16, 4B model: 32 layers x 8 KV heads x 128 head_dim x 2 (K and V) x 2 B
                          = 131,072 B per token = 0.125 MiB per token

KV budget = 9,176 - 3,538 = 5,638 MiB
tokens from memory = 5,638 MiB / 0.125 MiB per token = 45,104 tokens
```

**Term 3 — the latency budget.** A batch job that holds the GPU for minutes is not acceptable
during use. At the MEASURED 47.95 GFLOPS the CPU case is the binding one; taking a 60-second
prefill target on the CPU tier:

```
CPU: 60 s x 47.95 GFLOP/s = 2,877 GFLOP
prefill cost ~2 FLOP/param/token for 2B int4: 2.27e9 x 2 = 4.54 GFLOP/token
tokens from latency = 2,877 / 4.54 = 634 tokens   ... far below MIN, so the CPU tier CANNOT
                                                     hold an hour inside 60 s. Budget 300 s:
tokens = 634 x 5 = 3,170 tokens
```

**Combine:**

```
MAX = min( 262,144 , 45,104 , 3,170 ) = 3,170  -> round down to 1,024 -> 3,072 tokens
```

> **On this machine, MAX = 3,072 tokens** (the GPU tier would give `min(262,144, 45,104, ~74,000)
> = 45,104 → 45,056, bounded instead by Term 1's real config value).

**The honest reading of that number, and the thing to raise with the owner.** The measured hourly
transcript is **6,634 tokens**, which is **more than twice MAX on the CPU tier**. So on this box, as
measured, **a full hour does not fit the derived CPU budget** — the feature would have to summarise
in chunks or the latency target would have to be relaxed. Two consequences:

1. The gate's CPU recommendation (`2B`) is the right mitigation: halving the model halves the
   per-token prefill cost, which moves the CPU latency budget from 3,170 to ~6,340 tokens — **just
   enough for a full hour**, at the cost of a ~5-minute pass. That is the configuration I would
   ship on this box: **`Qwen3.5-2B int4`, CPU, full hour, ~5 min, offline.**
2. **The formula is the deliverable, not the constant.** The numbers above are what *this* box
   produces; the same code on a 4 GB-VRAM laptop yields a much smaller MAX automatically, which is
   exactly what the owner asked for.

**Mark all of §4.3's sub-terms as ESTIMATED except the VRAM readings, the quantised weight size
and the transcript token counts, which are MEASURED.** The `0.125 MiB/token` KV figure assumes
fp16 KV with Qwen3.5-4B's published head configuration; the FLOP-per-token costs are textbook
inference arithmetic, not benchmarks.

---

## 5. The hourly design, with cache

### 5.1 One window, three triggers

The manual button and the hourly job are **the same operation on different windows**, which is what
makes them coexist without double work:

| trigger | window | example |
|---|---|---|
| manual ("use Qwen now") | **start of the current hour → now** | at 4:40 → 40 minutes |
| hourly boundary | **the whole previous hour** | at 5:00 → 4:00–5:00 |

### 5.2 The hour boundary behaviour (the owner's 4:40 → 5:00 case)

At 4:40 the manual run covers 4:00–4:40 and writes a **partial** result. At 5:00 the scheduler
**reprocesses the FULL hour 4:00–5:00**, including the 40 minutes already covered.

**Why reprocess and not just append the missing 20 minutes?** Because a summary built by stitching
a 40-minute summary to a 20-minute summary reads as two documents, and the title of the first half
is often wrong for the whole. A summary is a **lossy, order-dependent reduction**: folding a
reduction over a sub-range and then over the remainder is not the same function. The owner said
*"de preferência com cache e etc."* — so we **cache the expensive part (the tokenisation) and keep
the cheap part (the window) exact**:

- **Cache the tokenised hour**, not the prose. Re-running the model over an existing token buffer
  costs one pass; re-tokenising costs nothing.
- **Bound the cost:** the 5:00 pass is a **full re-summarise**, but it is allowed to skip entirely
  if the hour's content hash is unchanged since the manual run (§5.3) — the only case where the
  4:40 result *is* the 5:00 result is when no new speech arrived, and then no work is done at all.

**Incremental (previous summary + new minutes) is explicitly rejected as the default** for the
hourly boundary, because it produces the stitched document. It is kept as a **fallback** for one
case only: if the full hour exceeds `MAX` (§4.3), fold in chunks *in order* rather than a lossy
stitch of independent summaries.

### 5.3 What is cached, and where

Following the store's own convention (`<root>/<YYYY-MM-DD>/<HH>.md`, one file per hour, no
database — see `app/electron/history-store.js`), the summary is a **sibling file**, not new markup
inside the transcript:

```
history/2026-10-06/19.md          <- the transcript (UNCHANGED)
history/2026-10-06/19.summary.json <- the Qwen result
```

**Why a sibling file and not inside `19.md`:** the transcript is append-only and single-writer; the
panel, the Electron arm's store and the WebView2 shell's `history_append` all agree on its format,
and a JSON blob in it would have to be re-parsed by every one of them. A sibling file cannot break
any existing reader.

Format:

```json
{
  "schema": 1,
  "hour": "2026-10-06T19:00:00-03:00",
  "window": {"from": "19:00:00", "to": "19:59:59", "minutes_covered": 59.4},
  "content_hash": "sha256:...",              // over the CONCATENATED LINE TEXT, not the raw file
  "line_count": 487,
  "input_tokens": 7787,
  "title": "EmbedGemma 2 and multimodal embeddings explained",
  "summary": "...",
  "language": "en",                           // decided per hour, see 5.4
  "model": "Qwen3.5-4B-int4",
  "engine": "onnxruntime-genai 0.17.1",
  "provider_bound": ["CPUExecutionProvider"],
  "trigger": "hourly",                        // "hourly" | "manual" | "backfill"
  "partial": false,                           // true if this covers part of the hour
  "generated_at": "2026-10-07T08:00:04Z",
  "elapsed_seconds": 61.2,
  "estimated": false
}
```

**Cache key = `hour` + `content_hash`, and the suffix carries the provenance** — the same idiom
`history-store.js` already uses for `reason=`/`src=`. This is what makes the manual/:00 pair safe:

- Manual at 4:40 writes `04.summary.json` with `partial: true` and the hash of 4:00–4:40.
- At 5:00 the scheduler hashes 4:00–5:00, finds **no `04.summary.json` with `partial: false` and a
  matching hash**, and runs the full hour.
- If the owner pressed the button at 4:59 and nothing was said in that minute, the hashes match and
  the 5:00 pass is **skipped**. That is the only "no double work" case, and it is the one that
  actually matters.

### 5.4 Language of the title and summary

**Recommendation: match the transcript, decided per hour from the transcript itself.**

The transcript is genuinely bilingual on this box, and MEASURED evidence of exactly why a fixed
choice is wrong is sitting in the archive: `history/2026-10-06/19.md` contains
`- [19:37:44] इम्बेड िंग जमा टू सैट्स ...` — the ASR emitted **Devanagari** for English audio, and
also emits Portuguese. So even *one hour* is not reliably one language.

**Rule:** the summariser is told to answer **in the dominant language of the input**, with the
dominant language computed by character-class census over the hour's lines (Latin-with-Portuguese
diacritics vs English stopwords vs other scripts). The system prompt says, in both languages:

```
You are given a transcript. Reply in the SAME language as the transcript.
If the transcript mixes languages, use the one that dominates.
Produce exactly: a title of at most 12 words, then a summary of 3 sentences.
```

**Fallback:** if the census is ambiguous (a genuinely 50/50 hour), default to **Portuguese**, the
owner's own language and the host locale. Store the decision in `language` so it is auditable.

### 5.5 Where the result is shown

The panel reads the sibling JSON. The contract is the one the panel already uses for history: the
shell hands the panel a finished entry, path included, so the layout stays in one place.

**"Summary ready" event** (one JSON line on the worker/shell status channel, same grammar as the
existing `BRIDGE_*` lines):

```json
{"type":"summary","hour":"2026-10-06T19:00:00-03:00","partial":false,
 "title":"...","summary":"...","language":"en","model":"Qwen3.5-4B-int4",
 "path":"history/2026-10-06/19.summary.json","trigger":"hourly","elapsed_seconds":61.2}
```

and the failure counterpart, which must be a **first-class** message, not silence:

```json
{"type":"summary-unavailable","reason":"gate-unavailable",
 "detail":"no usable ONNX Runtime provider; processor below the floor",
 "downloads_attempted":false}
```

`downloads_attempted: false` is the machine-checkable form of the owner's rule (§6).

### 5.6 How the panel asks for a summary

**Manual button** → panel posts `{"type":"summary-now","scope":"since-hour-start"}` over the
existing bridge. The shell does **not** run the model on the UI thread; it hands the job to the
worker process, which is already the process that owns the transcript. The panel shows a pending
state keyed on the hour, and the button is **disabled while a pass for that hour is running** —
that is the second guard against double work, independent of the cache.

**The loudest constraint on the scheduler:** the live ASR is the primary job. The hourly pass must
(a) run in the worker process only when no caption is in flight, (b) at below-normal priority, and
(c) **never run while the panel is being actively read** — defer to the next idle window. The
existing law that the live engine must not be cut must not be approached by a background job
starving it for 5 minutes.

---

## 6. The honest weak-PC path

### 6.1 When the check runs

**Both, and they are the same function.**

1. **At install time** — before anything is fetched, the gate runs and its verdict is stored.
2. **At first run and on every scheduled pass** — because hardware changes: a driver update can
   make CUDA load, and a laptop can be undocked from its eGPU. Re-running is cheap (it is a few
   seconds of probes) and a stale "yes" is exactly the false positive the owner forbade.

**The stored verdict is a cache with a timestamp, never an authority.** On every scheduled hour the
gate re-performs the capability checks; if the verdict flipped from `available` to `unavailable`,
the feature is disabled and the message below is shown. A verdict older than 24 h is not reused.

### 6.2 The exact user-facing sentence

When the gate returns `unavailable`:

> **"Resumo por Qwen indisponível neste PC — processador e memória insuficientes para rodar o
> modelo local. Nada foi baixado."**

> *"Qwen summary is unavailable on this PC — the processor and memory are not enough to run the
> local model. Nothing was downloaded."*

When it is available **but the GPU tier is withheld** (this machine's case today):

> **"Resumo por Qwen disponível no modo CPU (mais lento, ~5 min por hora). Sua placa de vídeo não
> pode ser usada porque o ONNX Runtime precisa do CUDA 13 e o PC tem o CUDA 12.8."**

> *"Qwen summary is available in CPU mode (slower, ~5 min per hour). Your GPU cannot be used
> because ONNX Runtime requires CUDA 13 and this PC has CUDA 12.8."*

The second sentence matters as much as the first: it is the difference between "your PC is weak"
(which is **false** — this box has an RTX 5080) and "one dependency is missing" (which is true and
actionable). Saying "weak PC" here would be a lie the owner would catch.

### 6.3 The mechanism that guarantees nothing is downloaded

**The gate runs before any code path that can download, and the download is unreachable when the
verdict is not `available`.** Concretely:

1. `decide_gate()` returns a record containing **`downloads_permitted: false`** when the path is
   `unavailable`. This is a field, not a convention.
2. The model-acquisition step **takes that record as a required argument** and refuses to proceed
   without `downloads_permitted is True`. It cannot be called "by accident" from a button.
3. The gate runs **at install time, before the installer would fetch anything**, and again before
   each pass. So a machine that fails the gate never runs the fetching code at all.
4. Every acquisition sets `HF_HUB_OFFLINE=1` after a first successful download, so a later
   run-time failure cannot silently re-pull. (This lane used the same switch to read the
   tokenizer without downloading — MEASURED to work.)
5. The failure message carries **`downloads_attempted: false`**, so the claim is
   machine-checkable rather than a promise.

**Fail-closed by construction:** the verdicts that permit a download are exactly
`gpu-high`, `gpu-mid`, `gpu-low`, `cpu-only-adequate`. Note `cpu-only-**marginal**` **does permit**
a download, deliberately: a machine with 6–12 GiB free and 4–8 cores can run a 0.8B model usefully,
and denying it would be the false negative the owner forbade. `unavailable` is reserved for the
case where even the 0.8B tier does not fit.

---

## 7. Proposed interface

### 7.1 How the panel asks

```
panel  --{"type":"summary-now","scope":"since-hour-start"}-->  shell
panel  <--{"type":"summary-pending","hour":"...","eta_seconds":300}--  shell
panel  <--{"type":"summary", ...}--  shell           (on success)
panel  <--{"type":"summary-unavailable", ...}--  shell   (on refusal/failure)
```

The panel never learns the model, the provider or the file path: it renders `title`, `summary` and
a provenance line, exactly as it already renders history entries.

### 7.2 How the shell/worker calls the engine

In-process, in the worker, in one function:

```python
import onnxruntime_genai as og          # already installed: 0.17.1 (MEASURED)

def summarise(tokens_text: str, *, model_dir: str, max_tokens: int) -> dict:
    model = og.Model(model_dir)                       # cache this per process
    tokenizer = og.Tokenizer(model)
    params = og.GeneratorParams(model)
    params.set_search_options(max_length=max_tokens, do_sample=False)
    prompt = build_prompt(tokens_text)                # §5.4 language rule
    generator = og.Generator(model, params)
    generator.append_tokens(tokenizer.encode(prompt))
    while not generator.is_done():
        generator.generate_next_token()
    return parse_title_and_summary(
        tokenizer.decode(generator.get_sequence(0)))
```

**Two rules this function must obey**, both learned from this box's own measurements:

1. **The model must be loaded once and kept warm**, not per invocation. A `og.Model` load is the
   dominant cost, and the process is already alive.
2. **The bound provider must be reported, not assumed.** `generator` binds whatever EP the session
   got. Because CUDA *advertises itself and does not bind* here (§3.2), the result must record the
   provider the session **actually** got, and that is what `provider_bound` in §5.3 stores. Writing
   "GPU" because CUDA was advertised would be exactly the false positive the owner forbade.

### 7.3 Proposed `worker/qwen_hourly.py` surface (design only — not written)

```
python worker/qwen_hourly.py --report                 # print the gate verdict, JSON
python worker/qwen_hourly.py --hour 2026-10-06T19:00  # backfill one hour
python worker/qwen_hourly.py --now                    # the manual button's job
python worker/qwen_hourly.py --daemon                 # the hourly scheduler
```

Same grammar as the existing `worker/redux_batch.py` (`--json` for machine output, diagnostics on
stderr, UTF-8 pinned) so the two batch engines are driven the same way.

---

## 8. What is UNKNOWN or unverified

Stated plainly, because a guess dressed as a fact is the failure mode this repo has already paid for twice.

1. **Whether a Qwen3.5-4B int4 ORT-GenAI build actually loads and generates on this box.**
   The builder *supports* the architecture (**DOCUMENTED**), the runtime is present
   (**MEASURED**), and the export format is confirmed (**MEASURED**, the `md-bogush` tree) — but
   nobody has run generation. **This is the first thing to verify before building the feature.**
2. **Every latency figure in §3.3 and §4.3 is ESTIMATED**, derived from the measured 47.95 GFLOPS
   and the measured 6,634-token hour. No model was loaded. `prefill ≈ 0.05 s/token` on CPU is an
   assumption, and it is the single number that decides whether the CPU tier is viable.
3. **The ORT-GenAI export's actual `context_length`** is unknown until a built model is inspected
   (Term 1 of §4.3). The base model says 262,144; a quantised export frequently defaults far lower.
4. **The size and cost of the CUDA 13 + cuDNN 9 runtime install** (§3.2) — not installed, not
   downloaded, not measured.
5. **The community ORT-GenAI exports are unvetted** — 14 downloads, 0 likes on the only usable
   one. No integrity check was performed beyond reading the file tree.
6. **`Qwen3.8` exists and was not evaluated.** It may be a better target; the ORT-GenAI builder
   supports "Qwen3.5/3.8" together (**DOCUMENTED**). Choosing 3.5 was a conservative call, not a
   measured superiority claim.
7. **Whether `torch.cuda` and an ORT CUDA provider would agree once the DLLs are installed.** They
   disagree *today* for a known reason (torch bundles its own CUDA runtime; ORT needs the system
   one). That is a documented mechanism, but the post-fix agreement is unverified.
8. **The `nvidia-smi` PATH cases were simulated, not observed.** `--no-smi-on-path` proves the
   fallback logic, not a real machine missing the binary.
