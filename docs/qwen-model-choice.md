# Which model actually runs the hourly title + summary?

**Status:** RESEARCH ONLY. No weights were downloaded by this lane. Nothing was installed,
nothing was deleted, `worker/**` and `app/**` were not touched.

**Question answered:** *what is the SMALLEST model still SUFFICIENT for a title + summary of one
hour of the owner's transcript, and can we actually run it with what is already on this box?*

Evidence markers, same convention as [`qwen-hourly-plan.md`](qwen-hourly-plan.md):

| marker | meaning |
|---|---|
| **MEASURED** | produced by a command or probe on THIS machine; the command is named |
| **DOCUMENTED** | read from a model card, an HF API response or a vendor README; URL given |
| **ESTIMATED** | arithmetic on measured inputs with the model stated; **not** a benchmark |
| **UNKNOWN** | not determined. Deliberately not guessed |

Receipt of every command: [`_main/receipt-qwen-model-choice.md`](../_main/receipt-qwen-model-choice.md).

---

## 0. The two answers the owner asked for, first

### 0.1 Is there a 0.6B in Qwen3.5? **No.**

**There is no Qwen3.5-0.6B.** 0.6B exists **only in the previous generation, Qwen3**
(`Qwen/Qwen3-0.6B`). The smallest tier *inside* Qwen3.5 is **0.8B** — and its real parameter
count is **873,438,784**, i.e. **~16 % bigger than the 0.6B of the older generation**
(751,632,384).

Verified two ways (**MEASURED**, HF API, 2026-10-07):

1. The family page [`huggingface.co/api/collections/Qwen/qwen35`](https://huggingface.co/api/collections/Qwen/qwen35)
   lists every member with `numParameters`. The smallest is `Qwen/Qwen3.5-0.8B` at 873,438,784.
   There is no 0.6B entry. The full small series is **0.8B / 2B / 4B / 9B**.
2. An unfiltered search of the whole Hub for `Qwen3.5` (100 results, sorted by downloads) returns
   **no** 0.6B tier — only `0.8B`, `0.8B-Base`, `2B`, `2B-Base`, `4B`, `9B`, `27B`, `35B-A3B`,
   `122B-A10B`, `397B-A17B`.
3. The two generations *after* 3.5 are **larger, not smaller**:
   [`Qwen3.6`](https://huggingface.co/api/models?author=Qwen&search=Qwen3.6) exists only as
   27B and 35B-A3B; [`Qwen3.8`](https://huggingface.co/api/models?author=Qwen&search=Qwen3.8)
   starts at 27B. **So "the most recent ones" are not the smallest ones** — Qwen3.5-0.8B is the
   smallest recent Qwen of any 3.x generation.

**Model ids and licences for the small Qwen3.5 series (DOCUMENTED, HF API `cardData.license`):**

| model id | parameters | licence |
|---|---|---|
| `Qwen/Qwen3.5-0.8B` | 873,438,784 (BF16 873,436,192) | **apache-2.0** |
| `Qwen/Qwen3.5-2B` | 2,274,069,824 | apache-2.0 |
| `Qwen/Qwen3.5-4B` | 4,659,865,088 | apache-2.0 |
| `Qwen/Qwen3.5-9B` | 9,653,104,368 | apache-2.0 |

(`-Base` variants are pretrained, not instruct — do not use them; this feature needs instruction
following.)

### 0.2 What is "Needle"? **A tool-calling model, and it does not fit.**

"Needle" is **`Cactus-Compute`'s function-calling family**, not a general small LM:

| repo | what it is |
|---|---|
| [`Cactus-Compute/needle3`](https://huggingface.co/Cactus-Compute/needle3) | `architectures: ["NeedleForToolCalling"]`, tags `tool-calling`, `function-calling`, `webassembly`; weights `checkpoints/needle3.safetensors` 242,047,978 B (231 MiB); licence **apache-2.0**; **115,640 downloads / 304 likes** |
| [`Cactus-Compute/needle`](https://huggingface.co/Cactus-Compute/needle) | `jax` + `safetensors`, tags `function-calling`, `tool-use`, encoder-decoder, licence MIT |
| `Cactus-Compute/needle2` | same shape, Apache-2.0 |
| `Abdalrahman/needle-rs-safetensors`, `Blankyy/needle-mlx`, `TiGa-RCE/needle-mlx` | third-party re-packagings |

Three independent disqualifiers (**DOCUMENTED**, the repos above):

1. **Wrong task.** Every Needle repo is tagged `tool-calling` / `function-calling`. It is an
   encoder-decoder built to *emit a structured call*, not to write prose about an hour of speech.
   Its own config names the architecture `NeedleForToolCalling`.
2. **Wrong runtime, and the runtime is not a Python wheel.** The repos ship per-architecture
   **prebuilt native binaries and static libs** (`windows-x86_64/needle.exe`, `libneedle.a`,
   `.wasm`, `.cact`) plus a `cactus-needle` Python wheel. Adopting it means a second, unrelated
   runtime owned by a third party, for a task it was not trained on. The ORT-GenAI builder does
   **not** list it: `NeedleForToolCalling` is absent from the builder's architecture dispatch
   (**MEASURED**, `builder.py`).
3. **Its size is also not an advantage here.** 231 MiB of weights is ~half of Qwen3-0.6B's int4,
   but it is designed for a *narrow* task; the 0.6B-class models below are general instruct models.
   A model trained for a narrow task is not a cheaper general model — it is a worse one.

**Verdict: "Needle" is real and it is tiny, but it is not a summariser. Excluded.**

---

## 1. The comparison table

Sizes are **DOCUMENTED per file** from the HF API (`?blobs=true`), not estimated. "Quantised size"
means the artefact you must actually download and keep, excluding duplicate/vision files.

| # | candidate | params | quantised size (exact) | context | languages | licence | engine / how to run | engine cost |
|---|---|---|---|---|---|---|---|---|
| 1 | **`Qwen/Qwen3-0.6B`** via [`Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4) | 751,632,384 (non-embedding **0.44B**) | **483,328,000 B weights + 331,869 B graph + 11,422,650 B tokenizer + 6,064 B configs = 495,088,583 B ≈ 472.15 MiB** (Arm's own card says 461.25 MB, 838.22 MB peak RAM) | **40,960** (`genai_config.json`: `context_length` 40960, `max_length` 40960) | `100+ languages and dialects` incl. pt (Qwen3 card) | **apache-2.0** | **ORT-GenAI, ALREADY INSTALLED — no build** | **0 MB model-tooling** — we already have `onnxruntime-genai 0.17.1` + `onnxruntime 1.30.0`; the export is already in ORT-GenAI layout |
| 2 | **`Qwen/Qwen3.5-0.8B`** built locally to ORT-GenAI int4 | 873,438,784 | source checkpoint **1,746,942,600 B (1.63 GiB)**; built int4 output **~500 MiB ESTIMATED** (0.8B-class int4; cross-check: the same family's GGUF `Q4_0` is 563,036,064 B) | base **262,144** (`max_position_embeddings`); built export's own value **UNKNOWN** | Qwen3.5 family (multimodal, multilingual) | **apache-2.0** | ORT-GenAI builder, `Qwen3_5ForConditionalGeneration` is dispatched (**MEASURED**, `builder.py:760`) | **+`onnx_ir` pip package (absent today) + a ~1.9 GB scratch conversion**; hybrid linear-attention export is flagged **experimental** by the builder's own README |
| 3 | **`google/gemma-3-270m-it`** | 268,098,176 — but **170M is embedding** and only **~100M is transformer blocks** (vendor blog) | BF16 checkpoint (build required); int4 output **~150-200 MiB ESTIMATED** | 32,768 (Gemma 3 family) | English-first | **`gemma`** — HF puts the repo behind `gated: "manual"`: you must log in and accept Google's usage licence | ORT-GenAI builder supports `Gemma3ForCausalLM` (**MEASURED**, `builder.py:674`); no existing ORT-GenAI export exists (**MEASURED**: `?filter=onnxruntime-genai` returns `[]`) | **+`onnx_ir` + build + a Google licence click-through** |
| 4 | `HuggingFaceTB/SmolLM3-3B` | 3B | GGUF Q4 ~1.8 GiB (not fetched) | 128k | 6 languages incl. **Portuguese** | Apache-2.0 | builder supports `SmolLM3` | **+`onnx_ir`**; and **there is no SmolLM3 below 3B** — SmolLM2's 135M/360M are a different, older family the builder does not list |
| 5 | `LiquidAI/LFM2-350M` | 354,483,968 | BF16 708,984,464 B; int4 ~200 MiB ESTIMATED | **UNKNOWN** (not read) | en, ar, zh, fr, de, ja, ko, es — **no Portuguese** | **`license: other`, `license_name: lfm1.0`** — not a standard permissive licence | builder supports `Lfm2ForCausalLM` | **+`onnx_ir` + build**; and no pt |
| 6 | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | 1,100,048,384 | `model.safetensors` 2,200,119,864 B (BF16, 2023-era); GGUF Q4 ~0.7 GiB | **2,048** — `config.json` `max_position_embeddings: 2048` | `language: ["en"]` only | apache-2.0 | builder supports `Llama` | **+`onnx_ir`**; **context 2,048 cannot hold a 6,634-token hour** — structurally incapable, and no Portuguese |
| 7 | `Cactus-Compute/needle3` | ~240M weights | 242,047,978 B | UNKNOWN | — | apache-2.0 | **`NeedleForToolCalling` — NOT in the builder**; ships its own native binaries + `cactus-needle` wheel | **a whole new third-party runtime, for the wrong task** |

**Row 1's context is the one that matters.** The hourly requirement is a context *comfortably above
~8k before the prompt*. Row 1 clears it **5×** (40,960). Row 6 cannot hold the hour at all.

### 1.1 What "engine cost" means, concretely

Two different costs, and row 1 is the only candidate that pays neither:

- **Runtime cost.** The ORT-GenAI runtime is already installed and **MEASURED** working:
  `onnxruntime-genai 0.17.1`, `onnxruntime 1.30.0`, and `onnxruntime-gpu 1.30.0`. Rows 4-6 keep
  this runtime. **Needle does not** — it needs the `cactus-needle` wheel plus its own native
  library. **No candidate here needs Ollama, llama.cpp, vLLM or a server**, so the engine decision
  in the plan (§1.3) **does not change**.
- **Build cost.** Loading an already-exported ORT-GenAI bundle needs **nothing**. *Building* one
  from PyTorch needs the builder, and the builder is **currently broken on this box for a missing
  dependency** — **MEASURED**:
  ```
  $ python -m onnxruntime_genai.models.builder --help
  ModuleNotFoundError: No module named 'onnx_ir'      (builder.py line 19)
  ```
  `onnx_ir` is **not installed** (**MEASURED**) and is available on PyPI (`pip index versions
  onnx_ir` → `Available versions: 1.0.0, 0.2.1, …`). The GenAI wheel itself does not declare it —
  `Requires: numpy, onnxruntime` (**MEASURED**). So building **any** candidate costs one extra pip
  install, which the plan's §1.1 ("the engine is already installed", true for *running*) did not
  account for.

---

## 2. The measurement that changes the latency arithmetic

The plan's CPU budget is built on **47.95 GFLOPS**, which is a **float32** matmul. An int4 model
does not run that kernel. Measured on this box (**MEASURED**, synthetic `MatMulNBits` graphs,
`com.microsoft` domain, four-input schema, `block_size=32`, `accuracy_level=4`, CPU EP — the same
node shape the shipped int8 ASR model uses: 219 `MatMulNBits` nodes, `K=4352 N=1024 bits=8
block_size=32 accuracy_level=4`):

| kernel | shape (M×K×N) | time | effective |
|---|---|---|---|
| **int4** MatMulNBits | 512×2560×2560 | 12.0 ms | **557.7 GFLOP/s** |
| **int4** MatMulNBits | 512×1024×3072 | 5.2 ms | **617.4 GFLOP/s** |
| **int4** MatMulNBits | 512×2560×9216 | 40.8 ms | **592.5 GFLOP/s** |
| **int4** MatMulNBits | 2048×2560×2560 | 67.5 ms | 397.9 GFLOP/s |
| int8 MatMulNBits | 512×2560×2560 | 42.2 ms | 158.9 GFLOP/s |
| fp32 MatMul (the plan's number) | 512³ | 5.598 ms | 47.95 GFLOP/s |

**The int4 kernel bound on CPU is ~12× the GFLOPS the plan assumed.** Corroboration from a vendor
who measured the same model class: Arm's card reports **time-to-first-token 334.11 ms for a
127-token prompt on 4 threads of a Neoverse-V2** — i.e. ~2.6 ms per prompt token *on 4 threads*.
A ~6,634-token hour would be **~17 s of prefill on 4 threads** there, and this box has 14 physical
cores and a much faster int4 path.

**Consequence — and this is the important one:** the plan's CPU conclusion *"a full hour does not
fit the derived CPU budget"* (and therefore `MAX = 3,072` and the chunking/40-minute fallback) is
derived from the wrong kernel. **ESTIMATED** on the measured primitive alone, a full 6,634-token
hour at 40-50 % of the measured peak:

```
Qwen3-0.6B  ~1.5 GFLOP/token -> ~20-30 s prefill + a few s decode
Qwen3.5-0.8B ~1.75 GFLOP/token -> ~25-35 s
Qwen3.5-2B   ~4.5 GFLOP/token -> ~70-110 s
```

**Marked ESTIMATED**: one int4 GEMM shape is not a whole model (attention, RoPE, the hybrid
linear-attention recurrence and the CPU-side sampling are all outside the GEMM), and the int4
GatherBlockQuantized embedding type is a different kernel entirely. **Before shipping, run one real
pass and replace these.** But the direction is unambiguous: **latency is not the reason to pick the
smallest model any more. Quality is.**

> **Action for the plan owner:** re-derive `MAX` from the int4 kernel, not from 47.95 GFLOPS. On
> this evidence the CPU tier holds the **full hour** for a 0.6B/0.8B-class model, and the
> 3,072-token cap is likely an artefact of the wrong kernel. Do not chunk the hour until one real
> pass says you must.

---

## 3. The ranking

Ranked by *sufficiency per unit of cost* — the thing the owner actually asked for ("the smallest
possible, and they are enough for our task").

| rank | model | download | why here |
|---|---|---|---|
| **1** | **`Qwen/Qwen3-0.6B` int4 (Arm ORT-GenAI export)** | **495,082,519 B ≈ 472 MiB**, one download, no build | smallest artefact that runs the job **today**: ORT-GenAI layout, 40,960 context, CPU-int4 already targeted, **zero new pip installs, zero conversion, zero scratch**. It is the only candidate whose "can we run it" answer is *yes* without a build step. |
| **2** | **`Qwen/Qwen3.5-0.8B` built to int4** | 1.63 GiB checkpoint (+`onnx_ir`, +~1.9 GB scratch) → ~500 MiB kept | the **current** generation, same family as the plan's 2B, **apache-2.0**, 262k base context, ORT-GenAI builder dispatches it. 79 MB of *kept* size more than rank 1 — the cheapest upgrade if rank 1 disappoints. |
| 3 | `Qwen/Qwen3.5-2B` int4 (the plan's current pick) | ~1.3-1.4 GiB | the quality fallback. No longer needed *for latency* (§2) — only if quality collapses. |
| 4 | `google/gemma-3-270m-it` | ~150-200 MiB + build | 4× *less* non-embedding compute than Qwen3-0.6B, English-first, a Google licence click-through, and its own vendor says it is not for this. Ranked by size it would be #1; by sufficiency it is #4. |
| — | `LFM2-350M`, `TinyLlama`, `SmolLM2/3` | — | LFM2: no Portuguese + custom licence. TinyLlama: 2,048 context, cannot hold the hour. SmolLM3: nothing below 3B in the family the builder supports. |
| ✗ | `Needle` (all versions) | — | wrong task, wrong runtime (§0.2). |

### 3.1 Recommendation

> **Rank 1 — download `Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4` (Qwen3-0.6B, int4,
> ORT-GenAI, apache-2.0, 472 MiB) and prove it on the owner's own archive.**
>
> **Runner-up — `Qwen/Qwen3.5-0.8B` built to ORT-GenAI int4 with the installed builder.**

**Why rank 1 first, when it is the *older* generation.** The owner's instruction was *"we want the
most recent ones, and they are enough for our task. The smallest possible."* Those two clauses
point at different models, and the tie-break is which one can be **proven fastest at the lowest
risk**:

- Rank 1 is **already in the target format**. It loads with the runtime that is already installed,
  with **no build**, no `onnx_ir` install, no 1.9 GB scratch conversion, and no unverified
  dependency chain. Its export even ships the runtime versions it was validated against
  (ORT-GenAI 0.14.1 / ORT 1.27.0) and a real accuracy number (§4).
- Rank 2 is **one generation newer, 79 MiB bigger after conversion, and inherits two UNKNOWNS**:
  (a) the builder's own README marks the Qwen3.5 hybrid path **experimental** — *"The hybrid state
  manifest is experimental and its schema is not yet stable. It requires coordinated Engine runtime
  work beyond the current onnxruntime-genai#2454 head and is not compatible with the merged runtime
  on its own"* — and this box has the **merged, released** runtime 0.17.1; and (b) the base model
  declares 262,144 context but a **built export's own `context_length` is UNKNOWN** until it is
  inspected, and quantised exports frequently default far lower.
- Both are **apache-2.0** and both keep the engine decision unchanged, so there is no licence or
  architecture reason to prefer one.
- **De-risking order:** rank 1 costs one download and a few minutes to answer the question the plan
  has flagged as its biggest UNKNOWN. If it fails on **quality**, rank 2 is the next 1.63 GiB; if
  that fails, the plan's 2B. **Never start by building the hardest one.**

### 3.2 If rank 1 is chosen — the exact download

```
Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4
  genai_config.json      1,520 B        <- the ORT-GenAI marker
  model.onnx               331,869 B    <- the graph ONLY
  model.onnx.data      483,328,000 B    <- THE WEIGHTS (the sidecar. a listing that
                                          shows only model.onnx understates by ~1,457x)
  tokenizer.json        11,422,650 B
  tokenizer_config.json        376 B
  chat_template.jinja        4,168 B
  ------------------------------------------------
  TOTAL                495,082,519 B  = 472.15 MiB
```

Not required for the job (reference/benchmark material): `README.md`, `example.py`, `config.yaml`,
`metadata.yaml`, `pyproject.toml`, `uv.lock`, `.python-version`, `predictions.json`,
`benchmarks/*` — ~50 KB total, harmless.

**`genai_config.json` as shipped (DOCUMENTED, fetched raw):** `"type": "qwen3"`,
`context_length: 40960`, `max_length: 40960`, 28 layers, `hidden_size` 1024, 16 Q / 8 KV heads,
`head_size` 128, `vocab_size` 151936, sampling `temperature 0.6 / top_p 0.95 / top_k 20`.
**Two settings must be overridden for our job:** `do_sample: true` → greedy (a title/summary wants
determinism), and `max_length: 40960` → the plan's `MAX`. Also note the export uses
**`past_present_share_buffer: true`** (KV sharing) — that is why its own card reports only
**838.22 MB peak memory**.

**Provenance warning, stated plainly:** this is a **third-party derivative of a first-party model**,
published by Arm (89 downloads, 0 likes) and described by Arm itself as *"a reference
implementation … not a production-ready or supported solution"*, and *"Arm does not commit to
provide ongoing support, maintenance or updates"* (**DOCUMENTED**, its README). It has **not** been
integrity-verified by this lane. It is a derivative of `Qwen/Qwen3-0.6B` under Apache-2.0, so the
licence is clean; the **weights are unvetted**. First implementation step must be a gate that
proves it loads and emits a coherent sentence — exactly the gate the plan already demands in §2.3.

The benchmark metadata (`config.yaml`) also records that the export used
`GatherBlockQuantized` for the embedding table in a **natively INT4-packed** form, and
`accuracy_level`/`k_quant_last` for the LM head.

---

## 4. The honest question: is 0.6B/0.8B/270M actually enough?

**Short answer: probably enough for a TITLE, genuinely uncertain for a SUMMARY of a full hour. The
design that survives that uncertainty is "tiny model writes the title, and the summary is graded —
keep the bigger model available for it".**

### 4.1 What real evidence exists

| evidence | what it says | limit |
|---|---|---|
| Arm's published eval (**DOCUMENTED**, its card): **MMLU 5-shot 45.18 %** for the int4 export vs **47.32 %** for the fp32 original — a **-2.14 pp** drop with non-overlapping 95 % CIs; `MMLU macro` 46.81 % vs 49.16 % | int4 quantisation costs **real but small** accuracy at this size, and the card publishes the number honestly. Int4 is not the cliff. | MMLU is 5-shot **knowledge recall**. It does not measure *summarising someone else's speech*, which is what we ask for. It is the closest thing to evidence that exists and it is only adjacent. |
| Qwen3-0.6B card (**DOCUMENTED**): **0.44B non-embedding** parameters of 28 layers; Qwen3 family supports **100+ languages** | the 0.6B is a *general instruct model*, and its Qwen3 training carries explicit multilingual instruction-following — the requirement that rules **Gemma 3 270M** out is satisfied on paper. | "100+ languages" is a **family-level** claim; the card does not show a per-tier Portuguese score. |
| Gemma 3 270M's own vendor (**DOCUMENTED**, Google's launch post): *"While this model is not designed for complex conversational use cases, it's a strong model that follows general instructions"*; its value is *"unlocked through fine-tuning"* for *"text classification and data extraction"* | the 270M class is **explicitly not** a summariser. It is a fine-tuning base for narrow, well-defined tasks. | none — this is the vendor's own statement, and it is the strongest single data point in this section. |
| Architecture arithmetic (**MEASURED** from `safetensors.parameters` + the vendor blog): Qwen3-0.6B has **440M non-embedding** params; Gemma 3 270M has **~100M** transformer params with **170M** of its 268M eaten by a 256k-token vocabulary | "270M" and "0.6B" are **not** 2× apart in capability-relevant compute — they are **~4.4× apart** once embeddings are removed. A 270M-class model is not a slightly smaller 0.6B; it is a different class. | parameters are a proxy; it does not predict summarisation quality by itself. |

### 4.2 Where I am guessing — say it plainly

1. **No one has measured a 0.6B/0.8B/270M model summarising 6,634 tokens of noisy bilingual ASR
   transcript.** Not on HF, not in a paper I could find, not in any of these cards. The plan's own
   §8 already lists this shape of UNKNOWN for 4B; it is no better for 0.6B. **Every quality claim
   below is inference from the model's design intent, not measurement.**
2. **The input is adversarial on purpose.** The owner's archive (`history/2026-10-06/19.md`,
   52,157 B, **MEASURED**) contains Devanagari output for English audio, split words at chunk
   boundaries, and Portuguese/English mixing. A small model asked to abstract *that* is being asked
   for its weakest skill on its hardest input.
3. **The task shape is the risk, not the size.** Titling is a **selection** task — pick the salient
   subject from 6,634 tokens. Summarising is an **abstraction over the whole window** — it needs the
   model to hold the arc of an hour and compress it. The second is exactly where capability
   collapses first as parameters shrink. A 0.6B model routinely produces a *usable* title and a
   summary that is fluent, topically correct, and **thin or repetitive** — it describes the first
   and last few minutes rather than the hour.
4. **The tokenizer is shared but not identical.** The plan's 6,634 tokens/hour was measured with
   the **Qwen3.5-4B** tokenizer. Every small Qwen3.x tier uses the same Qwen2 BPE class, so the
   number should transfer closely — but this is **ESTIMATED, not re-measured** for the 0.6B in this
   lane.

### 4.3 The legitimate split design

The split is not a compromise that dodges the question — it is the correct answer to it:

| tier | assignment | why |
|---|---|---|
| **Qwen3-0.6B int4 (472 MiB)** | **title**, and a *first-draft* summary | a title is a selection task inside a small model's competence; it is also where the small model's speed pays off most (a title-only pass can run on every hour boundary without anyone noticing) |
| **Qwen3.5-2B int4 (~1.3 GiB, or 0.8B at ~500 MiB)** | **the summary, only when the hour deserves one** | the abstraction task gets the parameters. Cheap to gate: run the 0.6B on every hour; re-run the summary with the bigger model only when the hour passed `MIN` **and** its content hash changed (the cache rule the plan already defines in §5.3) |

**And here is the finding that makes the split cheap:** §2 measured the int4 CPU path at ~12× the
GFLOPS the plan assumed. If that holds end-to-end, the **0.8B or 2B summary pass is affordable in
the hourly window**, and the split costs *nothing extra in wall-clock* — it only costs disk
(~500 MiB, or ~1.3 GiB for 2B) and RAM. **A tiny title model plus a small-but-not-tiny summary model
is a defensible ship; "tiny does both" is the optimistic case that must be tested before it is
believed.**

### 4.4 The falsifier — what proves or kills rank 1

One pass, on the owner's own data, no new code beyond a loader:

```
input  : history/2026-10-06/19.md  (52,157 B, 390 lines, measured 7,787 tokens)
ask    : the §5.4 prompt — title ≤ 12 words + 3-sentence summary, same language as input
pass if: (a) the title names a subject a human would accept,
         (b) the summary's three sentences are about the WHOLE hour, not the first minutes,
         (c) it does not invent a subject, and (d) the Portuguese hours come out in Portuguese
```

A **failure on (a)+(d) only** → title-only split (§4.3). A **failure on (b)+(c)** → the 0.6B class
is too small for the summary; go straight to rank 2, and if 0.8B also fails (b)/(c), to the 2B.
Do not tune the prompt to rescue (b) before trying a bigger model — prompt tuning against an
abstraction failure buys fluency, not coverage.

---

## 5. Download size, disk, and the uninstall instruction

### 5.1 Cost of the recommendation

| item | bytes | note |
|---|---|---|
| `model.onnx.data` (the int4 weights) | **483,328,000** | the real download |
| `model.onnx` (graph) | 331,869 | |
| `tokenizer.json` + config + template | 11,427,194 | |
| **total download** | **495,088,583 B (472.15 MiB)** | **MEASURED**, HF API `?blobs=true` |
| disk kept | 495,088,583 B | no duplicate checkpoint is needed |
| peak RAM (**DOCUMENTED**, Arm) | 838.22 MB | vs 2,523.21 MB for the fp32 baseline |
| free disk today (**MEASURED**) | H: 59.5 GB, I: 166.4 GB, C: 12.6 GB, G: 10.8 GB | the target dir is on H: |

### 5.2 The exact id to download

```
Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4
```

into **`H:\sotto\worker\models\qwen3-0.6b-int4\`** — a fresh directory, lowercase, matching the
existing `worker/models/nemotron-3.5-asr-streaming-0.6b-int4/` naming idiom.

### 5.3 Uninstall instruction — **and the honest current state**

> **Current measured state: THERE IS NOTHING TO UNINSTALL YET.** No Qwen weights are on disk.
> The plan's 2B download **has not happened** (**MEASURED**, this lane):
> ```
> H:\sotto\worker\models\qwen3.5-2b-int4  -> exists=False
> H:\sotto\worker\models\qwen3.5-0.8b-int4 -> exists=False
> H:\sotto\worker\models\qwen3-0.6b-int4   -> exists=False
> ```
> `worker/models/` holds only the ASR artefacts: `nemotron-…-fp16` 1,247.0 MB,
> `…-fp32` 2,478.8 MB, `…-int4` 756.6 MB, `…-int8` 1,021.0 MB,
> `parakeet-redux-ternary` 170.7 MB, `parakeet-redux-reference` 0.1 MB.
> And the HF cache holds **only the 4B tokenizer**, 21.9 MB in 15 files, **no `safetensors`**
> (`I:\codeintel\hf-cache\hub\models--Qwen--Qwen3.5-4B`).
>
> **So the space freed by not downloading the 2B is 0 bytes today, because 0 bytes of 2B exist.**
> That is a *finding*, not a no-op: the plan's "uninstall the 2B once the winner is proven" step
> is **already satisfied** and no lane needs to schedule it.

**When a 2B download does exist**, this is the exact instruction, for the lane that owns it:

```
path to delete (the directory, not a file):
  H:\sotto\worker\models\qwen3.5-2b-int4\

bytes freed (ESTIMATED, same int4 class as the 0.8B row):
  ~1.3-1.4 GiB  ~= 1,400,000,000 B   (NOT yet measured -- the tree does not exist)
  ESTIMATE BASIS: 2B params x ~4.5 bits/param effective (4-bit weights + fp16 scales
  + int4-packed embedding) + ~12.8 MB tokenizer. Cross-check: the 0.8B class lands at
  ~500 MiB, and 2.27B/0.87B x 500 MiB = ~1.30 GiB.
```

**Two hard warnings for whoever runs that delete, both earned in this repo:**

1. **Name the full artifact path.** The filter/target must be the literal
   `H:\sotto\worker\models\qwen3.5-2b-int4\`. A bare-word filter (`qwen`, `sotto`) has already
   killed unrelated processes twice tonight.
2. **Do not delete `I:\codeintel\hf-cache\hub\models--Qwen--Qwen3.5-4B`** as an "uninstall" — it is
   21.9 MB of tokenizer only, it is **not** on the `worker/models/` path, and the plan's token
   measurement depends on it.

**This lane deleted nothing.** Two scratch artefacts were created and removed while probing; both
were confirmed absent afterwards, and the verification is recorded in the receipt.

---

## 6. What is UNKNOWN / unverified

1. **Whether the Arm int4 export actually loads and generates on THIS x64 box.** It is documented
   as Arm-optimised and validated on Neoverse-V2/aarch64 with ORT-GenAI 0.14.1 and ORT 1.27.0; this
   box is x86-64 with **0.17.1 / 1.30.0**. The kernel exists here (**MEASURED**, int4
   `MatMulNBits` binds on `CPUExecutionProvider`), but x64 is not the target Arm validated. **This
   is the first thing to test, and it is one download away.**
2. **Whether a built Qwen3.5-0.8B int4 export loads in the released ORT-GenAI 0.17.1.** The
   builder's README says the hybrid state manifest *"requires coordinated Engine runtime work
   beyond the current onnxruntime-genai#2454 head and is not compatible with the merged runtime on
   its own"*. This is the single biggest technical risk in this document.
3. **Every end-to-end latency figure.** §2 measures one GEMM primitive and cites a vendor TTFT. No
   model was loaded by this lane. The prefill efficiency factor (40-50 %) is assumed, not measured.
   **One real pass replaces all of §2's ESTIMATED numbers.**
4. **Build-time cost of the int4 conversion** (disk scratch, minutes) — not measured; the plan
   estimated ~30-60 min and ~20 GB scratch for the 4B, so a 0.8B should be far cheaper, but that is
   another guess.
5. **`onnx_ir` compatibility.** The builder needs it; the install was **not** attempted (no installs
   in this lane). `pip` offers version 1.0.0 and the module's API compatibility with
   onnxruntime-genai 0.17.1 is unverified.
6. **Quality at 0.6B/0.8B on this specific task** — no benchmark exists (§4.2). This is the honest
   core of the deliverable.
7. **Which of it is Portuguese-strong.** Qwen3 claims 100+ languages *for the family*; no per-tier
   Portuguese evaluation was found for 0.6B or 0.8B, and no per-tier number exists on the cards.
8. **The tokenizer for a 0.8B build** — `Qwen/Qwen3.5-0.8B`'s `tokenizer.json` (12,807,982 B) is
   **not** in the local HF cache (only the 4B's is), so a build needs that fetch too.
9. **Arm's `model.onnx.data` internal layout.** `GatherBlockQuantized` for a natively INT4-packed
   embedding is a layout that the *runtime* must support in the version installed here; the graph's
   node census was **not** inspected (the file was not downloaded).
10. **Whether `hf download` of that repo pulls `benchmarks/`, `uv.lock` and the wheels cleanly** —
    not tested; the required file list is enumerated in §3.2 either way.

---

## 7. The public record: is `Qwen3.5-0.8B` or `Qwen3-0.6B` better quality, and does int4 matter?

**Status:** this section was added after a follow-up question, and it **supersedes §4.1's "no
task-relevant evals exist"** — they do exist for the larger of the two models. Nothing was
downloaded; every number below is read from a published source, named inline.

### 7.1 The published numbers, side by side

| benchmark | `Qwen3.5-0.8B` | `Qwen3-0.6B` | protocol | source |
|---|---|---|---|---|
| **MMLU** (5-shot) | — *not published* | **45.18 % int4** / **47.32 % fp32** | MMLU test, 14042 samples, 5-shot | [Arm int4 `benchmarks/*-int4.yaml`](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/benchmarks/qwen3-0-6b-onnx-genai-graviton-g4-int4.yaml) and [the fp32 pair](https://huggingface.co/Arm/qwen3-0-6b-onnx-genai-int4-kquantlast-emb-int4/raw/main/benchmarks/qwen3-0-6b-onnx-genai-graviton-g4-fp32.yaml) |
| **MMLU-Redux 2.0** (0-shot) | **50.49 % int4** / **50.53 % f16** | — | MMLU-Redux 2.0 test, 5330 samples, 0-shot | [Arm Qwen3.5-0.8B card](https://huggingface.co/Arm/qwen3-5-0-8b-q4-k-m-llamacpp-vivo-x300) and its [`-fp32.yaml`](https://huggingface.co/Arm/qwen3-5-0-8b-q4-k-m-llamacpp-vivo-x300/raw/main/benchmarks/qwen3-5-0-8b-llamacpp-vivo-x300-fp32.yaml) |
| MMLU-Pro (non-thinking) | **29.7** | — not published | Qwen's own harness | [Qwen3.5-0.8B card](https://huggingface.co/Qwen/Qwen3.5-0.8B) |
| MMLU-Redux (non-thinking) | 48.5 | — | Qwen's own harness | same card |
| IFEval (non-thinking) | **52.1** | — | Qwen's own harness | same card |
| IFBench (thinking) | 21.0 | — | Qwen's own harness | same card |
| MultiChallenge (thinking) | 18.9 | — | Qwen's own harness | same card |
| **AA-LCR** (long context, thinking) | **4.7** | — | Qwen's own harness | same card |
| **LongBench v2** (long context, thinking) | **26.1** | — | Qwen's own harness | same card |
| MMMLU (multilingual) | 34.1 non-thinking / 44.3 thinking | — | Qwen's own harness | same card |
| WMT24++ / NOVA-63 | 27.2 / 42.4 | — | Qwen's own harness | same card |
| GPQA (thinking) | 11.9 | — | Qwen's own harness | same card |
| HMMT Feb/Nov 25 | `--` (not measured) | — | Qwen's own harness | same card |

**Two asymmetries that matter, stated before the comparison is drawn:**

1. **`Qwen3-0.6B`'s own card publishes NO benchmark table at all** — only prose highlights
   ("100+ languages", "0.44B non-embedding"). The only accuracy number that exists for it anywhere
   is Arm's MMLU pair above. `Qwen3.5-0.8B`'s card publishes ~20 benchmarks.
2. **The two are scored on *different* benchmarks and protocols.** `MMLU` 5-shot (14042 samples)
   vs `MMLU-Redux 2.0` 0-shot (5330 samples) are **not interchangeable** — Arm's own card says so
   explicitly: *"The reported accuracy is a 0-shot, no-template, MCF measurement; figures produced
   under a different evaluation protocol are not directly comparable."* And Qwen's own harness rows
   are yet a third protocol (temperature 1.0, presence_penalty, thinking/non-thinking split).
   **No single benchmark exists on both models. There is no apples-to-apples number.**

**What the record therefore does and does not support.** It does **not** support "0.8B scores 5
points higher on MMLU" — that comparison is protocol-invalid. It **does** support the weaker,
defensible claim that `Qwen3.5-0.8B` was **evaluated** across retrieval, long-context and
instruction-following and **scored low on all of them**, while `Qwen3-0.6B` has **no evaluation on
those axes at all** — an absence, not a win.

**For a summarisation/titling task specifically:** the only published row that is *shape*-matched to
"read a long input and select what matters" is long-context retrieval, and Qwen measured that axis
**only for the 0.8B**, where it scores **AA-LCR 4.7** and **LongBench v2 26.1**. Those are low on
their own terms — but the immediately comparable bigger sibling in the same table, `Qwen3-1.7B`,
scores **AA-LCR 6.7** and **26.5**, i.e. the 0.8B is **0.70×** on AA-LCR and **0.98×** on
LongBench v2. **Neither model has any published summarisation, ROUGE, title-generation or
transcript-abstract benchmark.** For summarisation the public record does not contain the
measurement — it contains a proxy, and the proxy says the tier is weak.

### 7.2 Quantisation delta at int4, both models

| model | quant | metric | fp32/f16 baseline | int4 | **delta** |
|---|---|---|---|---|---|
| `Qwen3-0.6B` | GPTQ int4, group 32, int8 LM head, INT4-packed embedding | MMLU 5-shot | 47.32 % | **45.18 %** | **−2.14 pp** (−4.5 % rel.) |
| `Qwen3.5-0.8B` | K-quant `Q4_K_M` (25 tensors → Q6_K, 133 norm/SSM tensors fp32), imatrix-calibrated | MMLU-Redux 2.0 0-shot | 50.525 % | **50.49 %** | **−0.035 pp** (−0.07 % rel.) |

**Reading of the two deltas.** By relative loss (−4.52 % vs −0.069 %), the **0.8B is ~65× more
quantisation-robust than the 0.6B** on the published numbers. Two honest caveats before anyone
leans on that:

- Different quantisation schemes (GPTQ vs K-quant), different weight coverage (the 0.6B export
  quantises everything including the embedding; the K-quant recipe leaves 133 tensors at fp32 and
  promotes 25 to Q6_K) and different metrics. The comparison of *deltas* is weaker than the
  comparison of *scores*, and neither is apples-to-apples.
- **Arm measured the 0.8B in GGUF/llama.cpp, and we would run it in ORT-GenAI.** The recipe that
  produced the −0.035 pp figure is **not the recipe we would use** (§2 of this doc: ORT-GenAI
  `MatMulNBits`, `block_size` 32). The number is evidence that *this model tolerates int4*, not a
  prediction of our export.

**No perplexity/KL table exists for either.** Checked directly: `bartowski/Qwen_Qwen3.5-0.8B-GGUF`
and `mradermacher/Qwen3.5-0.8B-i1-GGUF` publish file-size tables and *qualitative* labels
("Very high quality, near perfect, *recommended*") — **no PPL and no KLD numbers** (`mradermacher`'s
25-file tree contains the quants and `.imatrix.gguf`, no results file). So the "GGUF quantisation
tables" that exist for some models **do not exist for these**.

### 7.3 Is an unquantized arm worth producing here?

**Cost, measured where it can be.**

| route | what it needs | size | verdict |
|---|---|---|---|
| **Builder** (fixes the blocker) | `onnx_ir` **only** — `onnxruntime-genai` does not declare it (`Requires: numpy, onnxruntime`, **MEASURED**) | wheel **185,849 B (181 KiB)** — downloaded to a temp dir and measured, then the temp dir was deleted | **trivial.** The builder already dispatches `Qwen3_5ForConditionalGeneration`; this one file unblocks `-p fp16` |
| `optimum` + `optimum-onnx` | two more packages, **neither installed** (`optimum` absent, **MEASURED**) | ~1-2 MiB wheels ESTIMATED (not measured) | avoidable |
| weights to convert | the 1.63 GiB bf16 checkpoint (**already counted**) | — | — |
| scratch / time | bf16 ONNX ~1.75 GiB out; peak ~4-6 GiB scratch; minutes ESTIMATED | — | — |
| **or skip ONNX entirely** | `transformers 5.15.0` + `torch 2.7.0+cu128` are **already installed** (**MEASURED**) — load `Qwen/Qwen3.5-0.8B` directly for a one-off quality read | checkpoint only | **cheapest unquantized arm by far** — no ONNX, no builder, no new wheel |

**Opinion, with the evidence behind it: the quantisation delta is irrelevant next to the task
risk.** Four reasons, in order of weight:

1. **The published delta is a fraction of a point.** −0.035 pp on the 0.8B, −2.14 pp on the 0.6B —
   and **neither figure carries a confidence interval**. Arm reports a 2.14 pp gap between two runs
   of 14042 samples with no error bar; a single 5-shot MMLU evaluation at that sample count is not
   demonstrably outside run-to-run noise. **The quantisation loss may not even be resolvable at
   these sizes.**
2. **The failure modes this task actually has are recorded, in writing, by the vendor — and they are
   not quantisation failures.** Qwen's own `Qwen3.5-0.8B` card, verbatim: *"In thinking mode, we have
   observed that when using the recommended sampling parameters, **Qwen3.5-0.8B is more prone to
   entering thinking loops** compared to other Qwen3.5 models, **which may prevent it from
   terminating generation properly**."* A model that fails to terminate has no accuracy to lose.
   Likewise the §4.4 falsifiers — hallucinating a subject, or truncating an hour to its first
   minutes — are **categorical** failures: they turn a `-0.04 pp` question into a 0-vs-1 question.
3. **The int4 kernel is not the weak link.** §2 measured int4 `MatMulNBits` at 398-617 GFLOP/s on
   this CPU, ~12× the plan's assumed fp32 figure, and `accuracy_level=4` in the shipped schema means
   the builder's int4 runs its activations at higher precision. Nothing in the measured path is
   marginal.
4. **A non-terminating or topic-inventing output is a bug; a 2 pp MMLU shift is a curve.** Effort
   spent on an fp32 arm buys a point of benchmark accuracy that this task cannot express, while the
   real risks (does it cover the whole hour? does it invent a subject? does it answer in
   Portuguese?) remain untested by *any* quantisation level.

**So: spend the hours on the head-to-head, not on an fp32 arm.** If an unquantized comparison is
wanted anyway, take §7.3's last row — `transformers` + the bf16 checkpoint, already installed — and
do **not** wait for the broken builder.

### 7.4 One-line verdict

> **The public record cannot decide this, so the empirical head-to-head must.**
>
> What it *can* say, and does: `Qwen3.5-0.8B` is the only one of the two with **any** published
> quality measurement, it quantises to int4 at **−0.035 pp** (vs the 0.6B's **−2.14 pp**), and on
> the one axis that resembles our task it scores **AA-LCR 4.7 / LongBench v2 26.1** — thin. The
> 0.6B's advantages (a working ORT-GenAI artefact today, apache-2.0, 472 MiB) are **engineering**,
> not quality, and its only quality number comes from a third party on a protocol that cannot be
> compared to the 0.8B's.
>
> **If forced to name one from the public record alone: `Qwen3.5-0.8B` — because it is the only one
> of the two with evaluated long-context and instruction-following numbers at all, and its int4
> penalty is negligible — subject to the caveat that its ORT-GenAI export path is still unproven
> and the model carries a vendor-documented non-termination failure mode.**
>
> **Treat that as a preference, not a finding.** Neither model has a published summarisation or
> titling evaluation. The 6,634-token hour decides it.
