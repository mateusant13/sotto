# Receipt — Qwen hourly title/summary research lane

Lane scope: RESEARCH + DESIGN + a hardware probe. **No feature was implemented, no model weights
were downloaded, nothing was installed.** Files owned by this lane:
`docs/qwen-hourly-plan.md`, `_main/_qwen-hw-probe.py`, `_main/receipt-qwen-research.md`
(plus the two supporting probes and their logs, and scratch that was deleted).

Everything below is a command that was actually run and output that was actually captured.

---

## 1. Environment facts, read not assumed

```
$ python -m pip show onnxruntime-genai onnxruntime
Name: onnxruntime-genai            Version: 0.17.1
Summary: ONNX Runtime GenAI        License: MIT
Location: C:\Program Files\Python311\Lib\site-packages
Requires: numpy, onnxruntime

Name: onnxruntime                  Version: 1.30.0
Location: C:\Program Files\Python311\Lib\site-packages
```

**Why it matters:** the text-generation runtime is *already installed* — this is the finding that
decides the whole engine question.

Library availability census (`importlib.util.find_spec`):

```
pynvml PRESENT   numpy PRESENT   torch PRESENT   onnxruntime PRESENT
onnxruntime_genai PRESENT   transformers PRESENT   psutil PRESENT   wmi ABSENT
```

```
$ python -c "import torch; print('torch', torch.__version__, 'cuda_available', torch.cuda.is_available())"
torch 2.7.0+cu128 cuda_available True
```

```
nvidia-smi locations:
  C:\Windows\System32\nvidia-smi.exe -> True
  C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe -> False
```

Note the HF cache on this box is **not** at the default location — `HF_HOME=I:/codeintel/hf-cache`,
and `C:\Users\Administrador\.cache\huggingface\hub` does **not** exist. The token rate probe found
`Qwen/Qwen3.5-4B` already cached there and used it **offline**.

---

## 2. Commands run, in order

| # | command | purpose / outcome |
|---|---|---|
| 1 | `python -m pip show onnxruntime-genai onnxruntime` | engine already present |
| 2 | `python _main\_qwen-hw-probe.py _main\_qwen-hw-probe.log` | capability gate — final version |
| 3 | `python _main\_qwen-cuda-init-probe.py _main\_qwen-cuda-init-probe.log` | why ORT cannot bind CUDA |
| 4 | `python _main\_qwen-token-rate-probe.py _main\_qwen-token-rate-probe.log` | measured transcript token rate |
| 5 | `python _main\_qwen-hw-probe.py <log> --no-smi-on-path` | **robustness test A** |
| 6 | `set SOTTO_PROBE_SIMULATE_TORCH_OOM=1` + probe | **robustness test C** |
| 7 | `python _main\_scratch-hf-facts.py` | HF API: exact file sizes + licences (scratch, deleted) |

---

## 3. Errors hit and how they were resolved (the useful part)

### 3.1 The log came out unreadable — an ONNX Runtime side effect

`cmd /c "python _main\_qwen-cuda-init-probe.py > log 2>&1"` produced a file that the `read` tool
refused as **binary**. Byte inspection:

```
size=32162  first bytes: 32 00 30 00 32 00 36 00   -> UTF-16LE
```

**Cause:** creating an ONNX Runtime `InferenceSession` flips the Windows CRT stdout handle to
UTF-16 (`_O_U16TEXT`). Everything printed *before* the session was UTF-8; everything after was
UTF-16LE, in the same file.

**Fix:** both probes now open their own **UTF-8 log file handle** and write through it
(`Report` / `_Tee` classes), so the report never depends on shell redirection surviving the mode
flip. Re-run: `size=5902  first8=0d0a3d3d` — plain text, readable.

### 3.2 Three separate crashes from one wrong assumption

`run_capture()` returns a **2-tuple** `(rc, text)`, but three call sites were written as
`rc, out, _ = run_capture(...)` (a 3-tuple). Each one crashed a whole capability:

- `display` call in `probe_gpu` → **this looked like a CPU probe failure**, because the handler's
  `getattr(fn, "__name__", "unknown")` resolved the lambda to the *next* function in the sequence
  and mislabelled the record `probe_cpu`. Two real lessons: (a) fix the unpack, (b) a fallback
  label that silently names the wrong capability is worse than no label.

Consequence worth recording: with `physical_cores=0`, the gate returned
**`path: unavailable`, `DOWNLOADS PERMITTED: False`** on a machine with 14 cores and an RTX 5080 —
a **false negative**, the exact failure the owner forbade. After the fix, `cpu-only-adequate`.

### 3.3 A `print(` → `p(` rewrite broke the file

A bulk regex replace also rewrote the line inside the `Report` class, joining two statements and
producing `SyntaxError: invalid syntax` at line 140. Caught by `python -m py_compile`. Repaired by
hand. **Lesson:** a bulk rewrite of a file you are still editing needs a compile check immediately,
not later.

### 3.4 The OOM probe thrashed the machine and had to be killed

The first OOM honesty test asked the driver for a flat **64 GiB**. It did not fail — it
**over-committed into system memory and thrashed the box**; the job hit the 120 s tool timeout and
was moved to the background.

**Process note (the hard rule was honoured):** before killing anything I read the command line of
every `python.exe`. The 1.6 GB process was

```
ProcessId : 29464
CommandLine : "C:\Program Files\Python311\python.EXE" H:\sotto\worker\sotto_worker.py
```

— **the owner's LIVE worker.** It was left untouched. The kill filter named the artifact and a
single pid:

```
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*_qwen-hw-probe*" }
  -> ProcessId 26356   <- killed this one only
Stop-Process -Id 26356 -Force
# re-verified: owner worker 29464 still alive; 0 probe processes remain
```

**Fix:** the OOM test is now bounded by `torch.cuda.set_per_process_memory_fraction(0.10)` and asks
for 4× that cap, so the OOM is raised inside the caching allocator with **no driver over-commit**.
Result: `OutOfMemoryError` after **0.027 s**, `recovered: True`.

### 3.5 A false alarm from my own gate — fixed, and the fix mattered

First version flagged `VRAM free disagrees: nvidia-smi=12835 vs torch=14987` as `degraded`. That is
**not** a defect: free VRAM is a live value and the two runtimes snapshot it at different instants.
Flagging it would train the reader to ignore the word.

Rewritten to compare **TOTAL** (stable device property, >2% = real discrepancy) and to report free
differences as an explanatory **NOTE**, using the **most conservative** reading:

```
NOTE: free VRAM varies by method (live value, not a defect): nvidia-smi=11224 MiB,
      pynvml=11224 MiB, torch=14987 MiB -- gate uses the most conservative: 11224 MiB from pynvml
```

A related latent bug was found by the simulated-OOM test: the gate read `vram_free` **only when the
gpu verdict was `ok`**, so a `degraded` verdict produced the misleading string
`vram_free=0.0 GiB` on a box with 11 GiB free — which could tip a borderline machine to a false
`unavailable`. Fixed; the same test now reports `vram_free=11.7 GiB`.

---

## 4. The probe, final state — raw output

### 4.1 Normal run (`_main/_qwen-hw-probe.log`)

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
    method: oversized request inside a capped caching allocator
    cap_fraction: 0.1   cap_gib: 1.59   asked_gib: 6.36   free_gib_before: 14.57
    result: OOM raised cleanly (this is the CORRECT behaviour)
    exception_type: OutOfMemoryError
    exception_text: CUDA out of memory. Tried to allocate 6.36 GiB. GPU 0 has a total capacity of 15.89 GiB of which 14.57 GiB is free. 1.59 GiB allowed; ...
    failed_after_seconds: 0.027
    recovered: True
    free_gib_after: 14.57

  [OK  ] cuda_gpu
         confidence : measured
         method     : nvidia-smi+pynvml(NVML)+torch.cuda (cross-checked)

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
  [OK  ] cpu

CAPABILITY: system RAM
  total 47.74 GiB  available 16.03 GiB  load 66%
  [OK  ] ram

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

The `WMI AdapterRAM` trap, captured live on this box:

```
| NVIDIA GeForce RTX 5080|4293918720|      <- 3 GiB 16 B reported for a 16 GB card (uint32 wrap)
| Intel(R) UHD Graphics 770|2147479552|
rows_showing_the_wrap: ["NVIDIA GeForce RTX 5080"]
```

### 4.2 Robustness test A — `nvidia-smi` simulated absent

```
MODE: --no-smi-on-path (robustness self-test: nvidia-smi simulated ABSENT)
  nvidia-smi  : NOT USABLE -- SIMULATED: nvidia-smi treated as absent (--no-smi-on-path)
  pynvml/NVML : 1 device(s)
    | ALLOCATION PERFORMED: torch.zeros(1, device='cuda') OK, memory_allocated=512 B
  NOTE: free VRAM varies by method: pynvml=10844 MiB, torch=14987 MiB
        -- gate uses the most conservative: 10844 MiB from pynvml
  [OK  ] cuda_gpu
         method     : pynvml(NVML)+torch.cuda (cross-checked)
```

**Passed:** the GPU is still found, and the verdict stays `ok`. Absence of `nvidia-smi` is not
treated as absence of a GPU.

### 4.3 Robustness test B — query says yes, allocation says no

`SOTTO_PROBE_SIMULATE_TORCH_OOM=1` (`$env:` set in PowerShell — `set VAR=1 && cmd` did **not**
propagate, which cost one wasted run):

```
    | ALLOCATION SIMULATED-FAILED (robustness self-test armed)
  [DEGR] cuda_gpu
         method     : nvidia-smi+pynvml(NVML)+torch.cuda (methods DISAGREE)
         reason     : SIMULATED: torch.cuda.is_available()=True but the allocation was refused
GATE DECISION
  path                 : cpu-only-adequate
  available            : True
  recommended model    : Qwen3.5-2B int4 (CPU)
  DOWNLOADS PERMITTED  : True
  reason               : cpu-only-adequate via ort-cpu: ort_gpu_provider_bound=False,
                         torch_cuda_usable=False, vram_free=11.7 GiB, ram_free=19.3 GiB, physical_cores=14
```

**Passed:** the disagreement is surfaced as evidence, the `ok` verdict is withdrawn, and the machine
still gets a correct `available` answer via the CPU path — **no false negative**. (This run also
confirms the `vram_free` fix from §3.5.)

### 4.4 Method disagreement under load — an accidental but useful observation

The same probe on consecutive runs reported **4.98** and **1.13** GFLOPS/physical-core, because the
owner's live ASR worker held a core. This is why the CPU calibration is **per physical core** and
why its floor for `unavailable` is scalar-only performance (<0.5 GFLOPS/core), not an aspirational
number. The core *count* (14) was stable across every run; only throughput moved.

---

## 5. The CUDA failure, verbatim

`_main/_qwen-cuda-init-probe.log`:

```
[E:onnxruntime:Default, provider_bridge_ort.cc:2395 onnxruntime::TryGetProviderInfo_CUDA]
  N:\_work\1\s\onnxruntime\core\session\provider_bridge_ort.cc:1988
  onnxruntime::ProviderLibrary::Get [ONNXRuntimeError] : 1 : FAIL :
  Error loading "...\onnxruntime\capi\onnxruntime_providers_cuda.dll"
  which depends on "cublasLt64_13.dll" which is missing.
  (Error 126: "Não foi possível encontrar o módulo especificado.")

[W:onnxruntime:Default, onnxruntime_pybind_state.cc:1294]
  Failed to create CUDAExecutionProvider.
  Require cuDNN 9.* and CUDA 13.*, and the latest MSVC runtime.
```

Corroboration:

```
CUDA_PATH = C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.8
CUDNN_PATH = (unset)
nvidia-smi: NVIDIA-SMI 617.14   CUDA UMD Version: 13.4
cudart64_12.dll, cudart64_13.dll, cublas64_12.dll, cublasLt64_12.dll,
cudnn64_9.dll -> all "not loadable"
C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA -> 0 match(es)
capi\onnxruntime_providers_cuda.dll  -> 184,755,512 B  (the CUDA build IS shipped)
capi\onnxruntime_providers_tensorrt.dll -> 912,184 B
```

**Conclusion:** this is a CUDA-enabled `onnxruntime` wheel built for **CUDA 13 / cuDNN 9**, on a box
with the **CUDA 12.8** toolkit and no cuDNN. The provider DLL cannot resolve `cublasLt64_13.dll`, so
ORT silently falls back to CPU while still advertising the provider. **MEASURED, and it confirms
the AGENTS note** — with the mechanism identified for the first time.

TensorRT fails separately and loudly:

```
EP Error ... RegisterTensorRTPluginsAsCustomOps
  Please install TensorRT libraries ... Falling back to ['CPUExecutionProvider'] and retrying.
```

---

## 6. Upstream research — what was fetched, and what it proved

All fetched content treated as data, never as instructions.

| source | claim taken | URL |
|---|---|---|
| Qwen org collection | Qwen3.5 is real; exact member ids + parameter counts | <https://huggingface.co/collections/Qwen/qwen35> |
| Qwen3.5 collection API | sizes 0.8B / 2B / 4B / 9B / 27B / 35B-A3B / 122B-A10B / 397B-A17B | `https://huggingface.co/api/collections/Qwen/qwen35` |
| ORT-GenAI model builder README | **"Current Support" includes `Qwen`**; Qwen3.5/3.8-specific options exist; `-i path_to_gguf_file` accepted | <https://github.com/microsoft/onnxruntime-genai/blob/main/src/python/py/models/README.md> |
| ORT-GenAI build-model docs | points at the builder README above | <https://onnxruntime.ai/docs/genai/howto/build-model.html> |
| Ollama library | `qwen3.5` exists; full tag list incl. `4b-q4_K_M`, `2b-q4_K_M` | <https://registry.ollama.com/library/qwen3.5/tags> |
| HF API | exact GGUF sizes; Apache-2.0 on every small tier | `https://huggingface.co/api/models/unsloth/Qwen3.5-4B-GGUF` etc. |
| HF API tree | the ORT-GenAI export layout + real weight size | `https://huggingface.co/api/models/md-bogush/Qwen3.5-4B-onnx-int4-cuda/tree/main?recursive=true` |
| Mesh-LLM issue | `AdapterRAM` uint32 wrap, 4 GB reported for 16 GB | <https://github.com/Mesh-LLM/mesh-llm/issues/1811> |
| llmfit PR | reading true VRAM from the driver registry instead of WMI | <https://github.com/AlexsJones/llmfit/pull/831> |
| vLLM install docs | CUDA-Linux-first | <https://docs.vllm.ai/en/v0.20.2/getting_started/installation/gpu/> |

### 6.1 Exact sizes measured (HF API, not quoted from a card)

```
unsloth/Qwen3.5-4B-GGUF   Q4_K_M 2614.0 MiB | Q8_0 4274.8 MiB | BF16 8034.1 MiB
unsloth/Qwen3.5-2B-GGUF   Q4_K_M 1221.5 MiB
unsloth/Qwen3.5-0.8B-GGUF Q4_K_M  507.8 MiB
unsloth/Qwen3.5-9B-GGUF   Q4_K_M 5417.4 MiB
md-bogush/Qwen3.5-4B-onnx-int4-cuda:
  genai_config.json      1,829 B          <- the ORT-GenAI marker
  model.onnx               644,486 B      <- graph only
  model.onnx.data        3,709,272,064 B  <- THE WEIGHTS (3.45 GiB)
  tokenizer.json         19,989,325 B
Qwen/Qwen3.5-4B          8.70 GiB (FP16 safetensors, 2 shards)
```

**The `model.onnx` = 644 KB vs `model.onnx.data` = 3.45 GiB ratio is the same ~5,800× trap
AGENTS records for the ASR models.** Quote the download as **~3.71 GB**, never "0.6 MB".

### 6.2 ORT-GenAI Qwen3.5 exports: they exist, but they are amateur

```
md-bogush/Qwen3.5-4B-onnx-int4-cuda   downloads 14   likes 0
Prince-1/Qwen3.5-4B-Onnx              downloads  8   likes 0
Prince-1/Qwen3.5-0.8B-Onnx            downloads  0   likes 0
onnx-community/Qwen3.5-9B-Onnx        downloads 24   likes 0
```

And the trap that looks official: `onnx-community/Qwen3.5-4B-ONNX` is **`transformers.js` split
format** (`decoder_model_merged*.onnx`, `embed_tokens_*`, `vision_encoder_*`) with **no
`genai_config.json`** — **not** loadable by ORT-GenAI as-is. Verified by reading its sibling list.

---

## 7. The token arithmetic — measured, not assumed

`_main/_qwen-token-rate-probe.py` over `history/2026-10-06/*.md` (9 files, 2,072 lines), tokenised
with the **real `Qwen/Qwen3.5-4B` tokenizer** read from the local HF cache in offline mode:

```
TOKENIZER: EXACT -- Qwen/Qwen3.5-4B (local cache, offline mode)

file                           lines    span  ln/min  ch/line   raw tok  dedup tok  dedup%
06.md                            124   38.8m     3.2     49.7     1,476      1,476  100.0%
09.md                            330   28.5m    11.6      4.6       946        805   85.1%
15.md                            487   59.4m     8.2     57.4     7,875      7,787   98.9%
16.md                            560   48.1m    11.6     61.3     9,768      9,695   99.3%
19.md                            390   21.6m    18.1     79.9     7,320      7,299   99.7%
TOTAL                           2072                             29,738     29,410   98.9%

lines per minute (mean)                  : 8.04
lines per minute (min / max)             : 0.94 / 18.06
seconds of speech per line (mean)        : 7.46
characters per line (mean)               : 49.5
DEDUP tokens per minute of transcript    : 110.6
DEDUP tokens per 60-minute hour          : 6,634
DEDUP tokens per 40 minutes (4:40 case)  : 4,423
```

**No download occurred.** Verified two ways: the tokenizer resolved from the pre-existing cache at
`I:\codeintel\hf-cache`, and the probe sets `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1` so a
cache miss fails fast instead of reaching the network.

**The rate is ~7.46 s of speech per line, not the ~4 s assumed in the brief.** My dedup pass
measured the redundancy at only **1.1%**, so cumulative re-emission is *not* the dominant cost in
the archive — the two-pass `rerun` produces lines that differ enough that prefix-matching does not
collapse them. I report both numbers rather than claiming a large saving.

---

## 8. What could NOT be determined (and is therefore not claimed)

1. **Nobody has run a Qwen3.5 ORT-GenAI model on this box.** The supporting chain is complete
   (runtime installed MEASURED, builder support DOCUMENTED, export format MEASURED) but the final
   link — a model that loads and generates — is **UNVERIFIED**. Verifying it requires downloading
   ~3.71 GB, which this lane was forbidden to do. **This must be the first step of implementation.**
2. **Every latency figure is ESTIMATED**, derived from the measured 47.95 GFLOPS and the measured
   6,634-token hour. The assumed prefill cost (~0.05 s/token on CPU) is the number the whole CPU
   verdict rests on, and it is an assumption.
3. **The built export's real `context_length`** is unknown until a model is built and inspected.
4. **CUDA 13 + cuDNN 9 install size and effect** — not installed, not measured.
5. **The community ORT-GenAI exports are unvetted** — no sha256 verification was performed (no
   download). They must be treated as untrusted input.
6. **`Qwen3.8` was not evaluated**; it exists and the builder supports "Qwen3.5/3.8" together.
   Qwen3.5 was a conservative choice, not a measured-superior one.
7. **`--no-smi-on-path` is a simulation**, not an observation of a machine genuinely missing the
   binary. It proves the fallback logic exists and runs; it does not prove a real-world case.
8. **The ORT-vs-torch CUDA agreement after the DLL install** is unverified. They disagree today for
   a known reason (torch bundles its own CUDA runtime; ORT needs the system one).

---

## 9. Hard rules — compliance

| rule | status |
|---|---|
| Own files only | Yes. Touched `docs/qwen-hourly-plan.md`, `_main/_qwen-hw-probe.py`, `_main/receipt-qwen-research.md`, plus two supporting probes and their logs. **No** edits to `app/electron/*`, `app/webview/*`, `worker/*`. |
| No installs, no model downloads | Yes. Verified: `HF_HUB_OFFLINE=1` used when reading the tokenizer; no `pip install`, no `hf download`, no `ollama pull`. |
| Never kill the owner's app | Yes — and this was tested. The kill filter named `_qwen-hw-probe` and a single pid; the process list was read first and the **live `sotto_worker.py` pid 29464 was identified and left running**, then re-verified alive after the kill. |
| Never leave a visible window | Yes. Every subprocess spawn used `creationflags=0x08000000` (`CREATE_NO_WINDOW`); all probes are short-lived. |
| Never open an audio device | Yes. Nothing in this lane touches audio. |
| `cmd /c "python ... > file 2>&1"` | Used, **and its UTF-16 side effect was found and worked around** (§3.1). |
| Web tools cite URLs | Yes — §6. |
| Scratch deleted | See §10. |

---

## 10. Scratch created and deleted

| file | why | status |
|---|---|---|
| `_main/_scratch-hf-facts.py` | HF API size/licence census | **TO DELETE** |
| `_main/_scratch-hf-facts.log` | its output (facts transcribed into the plan §2.2/§6.1) | **TO DELETE** |

Kept (not scratch — they are the evidence base for the plan and are cited from it):
`_main/_qwen-hw-probe.log`, `_main/_qwen-hw-probe-nosmi.log`, `_main/_qwen-hw-probe-oom.log`,
`_main/_qwen-cuda-init-probe.log`, `_main/_qwen-token-rate-probe.log`,
`_main/_qwen-cuda-init-probe.py`, `_main/_qwen-token-rate-probe.py`.

> **A note on `_main/_qwen-cuda-init-probe.txt`** — a stray UTF-16 artefact from the encoding
> investigation in §3.1. It was superseded by the `.log` and is listed for deletion with the scratch.
