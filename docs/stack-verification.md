# Stack verification

Two gates, settled from primary sources before any product code exists.

All sources below were read on **2026-10-05** (UTC-03:00). Every fetch was a named
URL. No licence term, version number, or function name in this file comes from
recollection; each is traceable to a quote and a URL.

---

## VERDICT: UNRESOLVED

**Two licence questions, two DIFFERENT components — they must not be fused.**

- **Parakeet Redux** (`moondream/parakeet-redux`, the batch model) is **CC-BY-4.0
  end to end** — its base `nvidia/parakeet-tdt-0.6b-v3` is `cc-by-4.0`, and so is
  every derivative (`Nairod785/parakeet-redux-gguf`, `eschmidbauer/parakeet-redux-onnx`).
  CC-BY-4.0 permits redistribution and commercial use, so Redux is **bundle-able
  with attribution** (credit the author + link the licence + state that changes
  were made); there is **no redistribution ban and no royalty**. This closes
  NOT-ESTABLISHED item 5 below, which had left `moondream/parakeet-redux`'s own
  licence unread. Source: `_main/research-parakeet-redux.md` Q4; HF `cardData`
  for the four repos.
- **OpenMDW-1.1 is NOT Redux's licence.** It governs
  `nvidia/nemotron-3.5-asr-streaming-0.6b` — the **streaming** model, a
  *different component*. Its redistribution clause requires retaining notices
  "that are applicable to your distribution", an undefined qualifier that
  decides how much NVIDIA paperwork travels with the weights. Question One below
  is the OpenMDW reading and is untouched by this separation.

Separately from either licence, one **runtime** finding stands: the Parakeet
Redux `tq1_g128` artefact named in the stack cannot be loaded by upstream
transcribe.cpp — it requires an unpublished ggml type patch that exists only on a
fork.

Two findings drive this. Neither is fatal; both must be closed before a public
release.

1. `handy-computer/transcribe.cpp` `main` ships **no** `TQ1_G128` ggml type. The
   `Nairod785/parakeet-redux-gguf` weights carry it. A stock upstream build cannot
   open those files.
2. The redistribution clause of OpenMDW-1.1 requires retaining notices "**that
   are applicable to your distribution**" — an undefined qualifier that decides
   how much NVIDIA paperwork travels with the weights if Sotto bundles them.

If Sotto **downloads** weights at first run instead of bundling them, finding 2
falls away and finding 1 becomes the only blocker, and a one-line swap to a
non-ternary Parakeet variant clears it.

---

## QUESTION ONE — THE LICENCE GATE

`nvidia/nemotron-3.5-asr-streaming-0.6b` is tagged `license:other` on Hugging
Face. What does that permit?

### What I read

| # | URL | Date | Result |
|---|---|---|---|
| 1.1 | `https://huggingface.co/api/models/nvidia/nemotron-3.5-asr-streaming-0.6b` | 2026-10-05 | machine-readable licence metadata |
| 1.2 | `https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/raw/main/LICENSE` | 2026-10-05 | **`Entry not found`** — no LICENSE file in the repo |
| 1.3 | `https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b/raw/main/README.md` | 2026-10-05 | full model card |
| 1.4 | `https://openmdw.ai/license/1-1/` | 2026-10-05 | full OpenMDW-1.1 text |

### The `license:other` resolution

`license:other` is not a licence. It is Hugging Face's marker for "read the link."
From the model API (1.1):

> `"cardData":{"license":"other","license_name":"openmdw-1.1","license_link":"https://openmdw.ai/license/1-1/", ...}`

The card's own frontmatter (1.3) says the same:

> `license: other` / `license_name: openmdw-1.1` / `license_link: >-` / `  https://openmdw.ai/license/1-1/`

And the card's dedicated section:

> **License/Terms of Use**
>
> Governing Terms: Use of the model is governed by the [OpenMDW-1.1](https://openmdw.ai/license/1-1/) license.

### The full licence text (1.4, quoted verbatim)

> OpenMDW License Agreement, version 1.1 (OpenMDW-1.1)
>
> By exercising rights granted to you under this agreement, you accept and agree to its terms.
>
> As used in this agreement, "Model Materials" means the materials provided to you under this agreement, consisting of: (1) one or more machine learning models (including architecture and parameters); and (2) all related artifacts (including associated data, documentation and software) that are provided to you hereunder.
>
> Subject to your compliance with this agreement, permission is hereby granted, free of charge, to deal in the Model Materials without restriction, including under all copyright, patent, database, and trade secret rights included or embodied therein.
>
> If you distribute any portion of the Model Materials, you shall retain in your distribution (1) a copy of this agreement, and (2) all copyright notices and other notices of origin included in the Model Materials that are applicable to your distribution.
>
> If you file, maintain, or voluntarily participate in a lawsuit against any person or entity asserting that the Model Materials directly or indirectly infringe any patent or copyright, then all rights and grants made to you hereunder are terminated, unless that lawsuit was in response to a corresponding lawsuit first brought against you.
>
> This agreement does not impose any restrictions or obligations with respect to any use, modification, or sharing of any outputs generated by using the Model Materials.
>
> THE MODEL MATERIALS ARE PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, NONINFRINGEMENT, ACCURACY, OR THE ABSENCE OF LATENT OR OTHER DEFECTS OR ERRORS, WHETHER OR NOT DISCOVERABLE, ALL TO THE GREATEST EXTENT PERMISSIBLE UNDER APPLICABLE LAW.
>
> YOU ARE SOLELY RESPONSIBLE FOR (1) CLEARING RIGHTS OF OTHER PERSONS THAT MAY APPLY TO THE MODEL MATERIALS OR ANY USE THEREOF, INCLUDING WITHOUT LIMITATION ANY PERSON'S COPYRIGHTS OR OTHER RIGHTS INCLUDED OR EMBODIED IN THE MODEL MATERIALS; (2) OBTAINING ANY NECESSARY CONSENTS, PERMISSIONS OR OTHER RIGHTS REQUIRED FOR ANY USE OF THE MODEL MATERIALS; OR (3) PERFORMING ANY DUE DILIGENCE OR UNDERTAKING ANY OTHER INVESTIGATIONS INTO THE MODEL MATERIALS OR ANYTHING INCORPORATED OR EMBODIED THEREIN.
>
> IN NO EVENT SHALL THE PROVIDERS OF THE MODEL MATERIALS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE MODEL MATERIALS, THE USE THEREOF OR OTHER DEALINGS THEREIN.

### Reading: what is permitted

**Commercial use — PERMITTED.** The grant is unqualified: "to deal in the Model
Materials without restriction." There is no revenue clause, no MAU threshold, no
field-of-use carve-out, no prohibited-use list anywhere in the text. This is an
unusually open grant for a commercial model.

Separately, the model card (1.3) asserts:

> This model is ready for commercial use.

That is NVIDIA's editorial claim, not a licence term. It is *consistent* with the
licence text and does not need to be relied on — the licence text alone permits it.

**Redistribution — PERMITTED, with conditions.** There is no share-alike clause
and no copyleft. The only two conditions are document retention, quoted above:
a copy of the agreement, plus notices of origin.

**Use inside a distributed desktop application — PERMITTED, but the obligation
depends on an architecture decision nobody has made yet.** This is the fork in
the road:

- *If Sotto bundles the weights* (ships the `.gguf` in the installer or the public
  repo), it "distributes … the Model Materials" and owes both retention items.
- *If Sotto downloads the weights at first run* from Hugging Face, it distributes
  no Model Materials; it distributes only its own MIT-licensed inference runtime.
  The redistribution clause appears not to trigger.

The licence does not say which of these Sotto is doing, and neither does the
roadmap as far as this document can tell.

**Attribution — no display or credit obligation is stated.** OpenMDW-1.1 contains
no "you must credit X in your product" clause, no in-UI attribution requirement,
and no derived-work naming rule. The entire attribution-shaped obligation is
documentary: retain a copy of the agreement, and retain notices of origin. That
is satisfiable with a `LICENSE` file plus a `NOTICE` file in the repo and a
`licenses/` folder in the installer — no product-UI work implied.

**Weights versus code — there is no separate code licence, because there is no
code.** The repo's complete file list (1.1) contains no source files at all:

> `.gitattributes`, `README.md`, `arch_slide10.png`, `avg_wer_summary.png`,
> `bias.md`, `config.json`, `explainability.md`, `fleurs_langid_vs_auto.png`,
> `fleurs_wer_vs_chunk_size.png`, `generation_config.json`, `latency_vs_parallel.png`,
> `model.safetensors`, `model_architecture.png`, `model_overview.png`,
> `nemotron-3.5-asr-streaming-0.6b.nemo`,
> `nemotron-3.5-asr-streaming-0.6b.q8_0.gguf`, `privacy.md`,
> `processor_config.json`, `safety.md`, `throughput_vs_chunk.png`,
> `tokenizer.json`, `tokenizer_config.json`

So the weights-vs-code split is not ambiguous here — it is vacuous. Every artefact
in this repository, weights and metadata alike, is governed by OpenMDW-1.1. The
*inference code* is a third party's, licensed separately (see Question Two). This
is the cleanest possible answer to that sub-question, and it is a finding rather
than an absence.

### The ambiguity, stated and not resolved

**Sentence:** "all copyright notices and other notices of origin included in the
Model Materials **that are applicable to your distribution**."

Why it matters: "applicable to your distribution" is never defined. It has at
least two readings that produce different legal outcomes for Sotto:

- **Narrow:** retain only notices concerning the parts actually redistributed. If
  Sotto bundles a Q4_K_M `.gguf`, that is the whole of the Model Materials anyway,
  so this reading collapses into "ship everything" — which happens to be safe.
- **Broad/other:** retain notices that *would* apply to Sotto's use, including
  upstream attribution and training-data provenance the licensee can identify
  outside the bundle.

I am not resolving this into a comfortable answer. It is narrow enough that the
conservative reading ("ship the agreement and every notice you can find") is
available and cheap, but "cheap to be conservative" is not the same as "the term
is satisfied", and a public repository that ships under a licence nobody has fully
read is precisely the risk this gate exists to catch.

**A second, structural fragility — the licence is not in the repo.** Fetch 1.2
returned `Entry not found`. The terms live only at a URL on a third party's
WordPress site, hosted by the Linux Foundation. For a project whose repository is
public from the first commit, this means the governing terms are not pinned to the
commit that relies on them: the page can change, move, or vanish, and nothing in
the model repo records what the text said on any given date. That is a fact about
the licence's durability, not about its permissiveness.

---

## QUESTION TWO — THE RUNTIME GATE

### What I read

| # | URL | Date | Result |
|---|---|---|---|
| 2.1 | `https://api.github.com/search/repositories?q=transcribe.cpp…` | 2026-10-05 | located the repo; `stephenberry/transcribe.cpp` 404s |
| 2.2 | `https://api.github.com/repos/handy-computer/transcribe.cpp/releases/latest` | 2026-10-05 | v0.3.1 + asset list |
| 2.3 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/README.md` | 2026-10-05 | repo README |
| 2.4 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/LICENSE` | 2026-10-05 | MIT text |
| 2.5 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/include/transcribe.h` | 2026-10-05 | public C header (middle truncated, see NOT ESTABLISHED) |
| 2.6 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/CMakeLists.txt` | 2026-10-05 | build/link mode |
| 2.7 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/docs/bindings.md` | 2026-10-05 | binding + link manifest contract |
| 2.8 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/bindings/rust/transcribe-cpp/README.md` | 2026-10-05 | Rust crate, **names Tauri explicitly** |
| 2.9 | `https://raw.githubusercontent.com/handy-computer/transcribe.cpp/main/docs/models/nemotron-3.5-asr-streaming-0.6b.md` | 2026-10-05 | Nemotron support + perf tables |
| 2.10 | `https://api.github.com/repos/handy-computer/transcribe.cpp/contents/patches/ggml` | 2026-10-05 | patch list — **no TQ1 patch** |
| 2.11 | `https://huggingface.co/api/models/handy-computer/nemotron-3.5-asr-streaming-0.6b-gguf` | 2026-10-05 | downloads, streaming flag, RTF |
| 2.12 | `https://huggingface.co/api/models/Nairod785/parakeet-redux-gguf` | 2026-10-05 | ternary repo metadata |
| 2.13 | `https://huggingface.co/Nairod785/parakeet-redux-gguf/raw/main/QUANTIZATION.md` | 2026-10-05 | **names the fork and the patch** |
| 2.14 | `https://api.github.com/repos/NairoDorian/transcribe.cpp` | 2026-10-05 | confirms fork lineage |

### Repository, licence, version

`https://github.com/handy-computer/transcribe.cpp` — organisation `handy-computer`,
language C++, 1,985 stars, 114 forks, last push 2026-10-05.

**Licence: MIT** (2.4, verbatim):

> MIT License
>
> Copyright (c) 2026 The transcribe.cpp authors
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of
> this software and associated documentation files (the "Software"), to deal in
> the Software without restriction, including without limitation the rights to
> use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
> of the Software, and to permit persons to whom the Software is furnished to do
> so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

Explicitly redistribution-friendly ("distribute, sublicense, and/or sell"), with a
notice-retention obligation. Compatible with shipping inside a closed-source
desktop app provided the notice travels with it.

**Version: v0.3.1**, published 2026-10-04 (2.2). The header (2.5) confirms the
same value at compile time:

> `#define TRANSCRIBE_VERSION_MAJOR 0`
> `#define TRANSCRIBE_VERSION_MINOR 3`
> `#define TRANSCRIBE_VERSION_PATCH 1`

### How a host program loads a model and calls it

**A single-header C API** (2.5, verbatim header comment):

> ```
> transcribe.h - public C API for transcribe.cpp
>  *
>  * One-header public surface. Callers never need to include <ggml.h>.
> ```

It is `extern "C"`-wrapped, with an export-visibility macro (2.5):

> ```c
> #ifndef TRANSCRIBE_API
> #    if defined(_WIN32) && !defined(__GNUC__)
> #        if defined(TRANSCRIBE_STATIC)
> #            define TRANSCRIBE_API
> #        elif defined(TRANSCRIBE_BUILD)
> #            define TRANSCRIBE_API __declspec(dllexport)
> #        else
> #            define TRANSCRIBE_API __declspec(dllimport)
> #        endif
> #    else
> #        define TRANSCRIBE_API __attribute__((visibility("default")))
> #    endif
> #endif
> ```

**Function names read verbatim as prototypes** in `transcribe.h` (2.5) — model and
session lifecycle, the streaming path, and result accessors:

| Function | Purpose (from its own doc comment) |
|---|---|
| `transcribe_version()` | "Runtime version of the loaded native library." |
| `transcribe_version_commit()` | "Short git commit the library was built from…" |
| `transcribe_log_set()` | global log sink; call once at startup |
| `transcribe_init_backends()` | backend/module init (named in 2.7) |
| `transcribe_stream_begin(session, run_params, stream_params)` | start a stream |
| `transcribe_stream_feed(session, pcm, n_samples, update)` | "Feed PCM into the active stream. 16 kHz mono float32, same as transcribe_run." |
| `transcribe_stream_finalize(session, update)` | "Signal end of input. Flushes buffered audio…" |
| `transcribe_stream_reset(session)` | abandon without finalizing |
| `transcribe_stream_get_state()` / `transcribe_stream_revision()` / `transcribe_stream_last_status()` | stream lifecycle + change detection |
| `transcribe_full_text()` | clean transcript |
| `transcribe_get_segment()` / `_word()` / `_token()` | copy-out row accessors |
| `transcribe_timings_init()` / `transcribe_get_timings()` | stage timings |
| `transcribe_abi_struct_size()` / `_align()` | ABI introspection for bindings |

`transcribe_model_load_file()` and `transcribe_run()` are named in doc comments
(2.5) but **their prototypes fell inside the truncated middle of my fetch** — see
NOT ESTABLISHED. Their names are verbatim from the source; their signatures are
not something I read whole.

**Shared library: produced, but not by default** (2.6, verbatim):

> ```cmake
> # TRANSCRIBE_BUILD_SHARED OFF (default) builds a static libtranscribe + static
> # ggml, so `cmake -B build` yields a self-contained transcribe-cli with no
> # libtranscribe/libggml to chase at runtime — the posture every porting, test,
> # and bench workflow relies on. The Python wheel/provider build sets it ON to
> # produce a shared libtranscribe the FFI layer can dlopen.
> ```

and:

> ```cmake
> option(TRANSCRIBE_BUILD_SHARED    "Build libtranscribe + ggml as shared libraries"  OFF)
> ```

So: `-DTRANSCRIBE_BUILD_SHARED=ON` yields `libtranscribe` (+ `libggml`), with
`SOVERSION` derived from the header version. Release v0.3.1 ships prebuilt native
bundles for Windows/Linux/macOS across cpu-vulkan, cuda, and metal (2.2), named
e.g. `transcribe-native-0.3.1-windows-x86_64-cpu-vulkan.tar.gz`.

### The Rust linking story — and the Tauri answer

There is an **official** Rust binding (2.3):

> | Rust | [bindings/rust/transcribe-cpp](bindings/rust/transcribe-cpp) |

Two crates: `transcribe-cpp` (safe wrapper) and `transcribe-cpp-sys` (raw FFI)
(2.8):

> The raw FFI layer is [`transcribe-cpp-sys`](https://crates.io/crates/transcribe-cpp-sys); this crate is the safe wrapper.

The default link is static, which for Tauri is the easy case (2.8, verbatim):

> The default link is static and self-contained. Advanced packaging modes are
> available through `shared` and `dynamic-backends`; see the `transcribe-cpp-sys`
> README if you need runtime-loaded backend modules or custom
> `TRANSCRIBE_CMAKE_ARGS`.

And the build story needs no external C library (2.8):

> The native library is compiled from source by the `transcribe-cpp-sys` crate, so
> a first build needs a C++ toolchain and **CMake**. There is no external
> compression dependency (the deflate codec is vendored), so no system zlib /
> vcpkg setup is required on any platform.

For a shared/dynamic build, the crate hands the host build script the artifact
directory, and the README's own worked example is a Tauri one (2.8, verbatim):

> This crate forwards the native build's output directories to **your** build
> script as `DEP_TRANSCRIBE_CPP_*` env vars. The one you usually want is
> `DEP_TRANSCRIBE_CPP_RUNTIME_DIR`…

> ```rust
>     // A stable folder your bundler references with a STATIC path (e.g.
>     // tauri.conf.json `"resources": { "transcribe-libs/*": "." }`).
> ```

For non-CMake consumers there is a machine-readable link manifest (2.7):

> **`lib/transcribe-link.json`** — installed by `cmake --install`… the
> machine-readable link interface for non-CMake consumers building from source
> (the Rust `-sys` crate's `build.rs`).

### Model formats

**GGUF only** (2.3, verbatim):

> Runs diverse STT model families via [GGUF](https://github.com/ggerganov/gguf) models on the [ggml](https://github.com/ggml-org/ggml) runtime, with Metal, Vulkan, and CUDA backends for fast GPU inference plus a tinyBLAS-accelerated CPU path.

Upstream quantisation presets (2.3, verbatim):

> The `transcribe-quantize` tool produces smaller models from the
> reference GGUF. Available presets: `F16`, `Q8_0`, `Q6_K`, `Q5_K_M`,
> `Q4_K_M`.

### The `tq1_g128` question — ANSWER: different runtime build (a fork)

**`tq1_g128` is NOT supported by upstream transcribe.cpp.** Four independent
primary sources agree:

1. **No TQ1 preset.** The presets list (2.3) is `F16, Q8_0, Q6_K, Q5_K_M, Q4_K_M`.
   No ternary type.
2. **No `parakeet-redux` in the family table.** The Parakeet row (2.3) lists
   `parakeet-ctc-0.6b`, `parakeet-ctc-1.1b`, `parakeet-primeline`,
   `parakeet-rnnt-0.6b`, `parakeet-rnnt-1.1b`, `parakeet-tdt-0.6b-v2`,
   `parakeet-tdt-0.6b-v3`, `parakeet-tdt-1.1b`, `parakeet-tdt_ctc-1.1b`,
   `parakeet-tdt_ctc-110m`, `parakeet-ultra`, `parakeet-unified-en-0.6b`.
   `parakeet-redux` is absent.
3. **No TQ1 patch upstream.** `patches/ggml/` on `main` (2.10) contains exactly
   two files: `0001-fix-threadpool-oversubscription.patch` and
   `0002-backend-reg-filter.patch`. There is no `0003`.
4. **The author of the ternary weights says so explicitly** (2.13, verbatim):

   > So transcribe.cpp adds **`GGML_TYPE_TQ1_G128`** (id 96), shipped as the downstream ggml patch `patches/ggml/0003-tq1_g128-ternary.patch`:

   and its own reproduction step clones a fork, not upstream (2.13, verbatim):

   > ```bash
   > git clone https://github.com/NairoDorian/transcribe.cpp && cd transcribe.cpp
   > ```

   GitHub confirms the lineage (2.14): `NairoDorian/transcribe.cpp` reports
   `"fork": true` with `"parent": handy-computer/transcribe.cpp`, last pushed
   2026-09-26, MIT, 0 stars.

So the precise answer: **not a different project and not a different language —
a different build of the same project.** `Nairod785/parakeet-redux-gguf` is
consumable only by a fork carrying an extra ggml tensor type. A stock upstream
release cannot open those three files.

This is a maintenance liability for a repo that is public from its first commit:
the ternary format has no upstream release, no upstream CI lane, and one
maintainer. It is a small file — 179 MB / 159 MB / 157 MB (2.13) — so the
ternary advantage is size, and that advantage is currently purchased with a
private fork.

Note also that the fork's own numbers are good: FLEURS-fr WER 8.32 / 8.31 / 8.18 %
for TQ1_F16 / TQ1_Q8_0 / TQ1_Q4_K, against 4.65 % for `parakeet-ultra` (2.13).
The gap is the model's own ternary compression, not the conversion.

### Streaming — supported, and a separate entry point

The API is genuinely separate from batch: `transcribe_run` / `transcribe_run_batch`
for one-shot and batch, versus `transcribe_stream_begin` → `_feed` → `_finalize`
(2.5). `transcribe_stream_feed` takes the same PCM format as `transcribe_run`
("16 kHz mono float32").

Per family, streaming is opt-in and advertised separately. The README (2.3) marks
capabilities per family — Parakeet and Nemotron carry `streaming`; Canary, Whisper
and others do not.

For Nemotron specifically the two paths converge (2.9, verbatim):

> Both paths ship: the **offline** path (`transcribe_run`) defaults to
> `[56, 13]` (1.12 s) for the headline accuracy, and **chunked streaming** is
> selectable at runtime via `--stream-chunk-ms 1120 --stream-att-right
> {0,3,6,13}`. Streaming at R=13 is byte-equal to the offline transcript;
> lower-R settings trade lookahead for latency.

**So: a separate code path at the API surface, the same model and same weights
underneath, and at the widest setting byte-identical output.** Sotto's overlay
panel maps onto `_feed` + `_finalize` directly.

### NVIDIA Nemotron 3.5 ASR streaming — SUPPORTED, first-class

It is in the family table with capabilities (2.3, verbatim):

> | Nemotron 3.5 ASR Streaming 0.6B | `nemotron-3.5-asr-streaming-0.6b` | streaming, token timestamps | [docs/models/nemotron-3.5-asr-streaming-0.6b.md](docs/models/nemotron-3.5-asr-streaming-0.6b.md) |

A dedicated model doc exists (2.9) with WER tables across 26 languages, a
tensor-level validation protocol, and reproduction steps. The HF artefact
`handy-computer/nemotron-3.5-asr-streaming-0.6b-gguf` exists with **`"streaming":
true`** in its metadata block (2.11).

**Downloads: 1,835,919** as returned by the HF API (2.11) on 2026-10-05. This is
the counter for that GGUF repo only — not the upstream NVIDIA model (1.27 M, 2.1) —
and it is cumulative across all revisions and files in the repo. The briefing's
"over 1.8 million" is consistent with what I measured.

Two caveats worth carrying into the roadmap:

- The GPU numbers in NVIDIA's model card are **H100** figures (2.3: "Measured on a
  single NVIDIA H100"), i.e. datacentre hardware. They do not describe a desktop.
- The auxiliary CTC head is dropped at conversion, so CTC-argmax timestamps are
  unavailable (2.9, verbatim):

  > The auxiliary CTC head present in the upstream checkpoint is dropped at
  > conversion (the RNN-T head is the inference path); CTC-argmax timestamps
  > are not available.

### Reported memory and CPU cost

**CPU cost — published, with machines.**

Nemotron 3.5, compute latency (mel + encode + decode), speedup over realtime in
parentheses; Q8_0 column (2.9):

| Machine | Backend | jfk (11.0 s) | dots (35.3 s) |
|---|---|---|---|
| Apple M4 Max | Metal | 76 ms (143.94×) | 256 ms (138.26×) |
| Apple M4 Max | CPU | 358 ms (30.76×) | 1.19 s (29.73×) |
| AMD Ryzen 7 PRO 4750U (Radeon RADV RENOIR) | Vulkan | 640 ms (17.18×) | 2.07 s (17.09×) |
| AMD Ryzen 7 PRO 4750U (Radeon RADV RENOIR) | CPU | 951 ms (11.56×) | 3.67 s (9.62×) |

Provenance stated in the doc: M4 Max at transcribe.cpp `77b0c93` on 2026-09-14;
Ryzen at `218aeae3` on 2026-09-14. The HF catalogue independently records
`rtf_m4_max: {cpu 30.25, metal 141.1}` and `rtf_ryzen_4750u: {cpu 10.59, vulkan
17.13}` (2.11).

Parakeet Redux, encoder time on a 29.3 s clip, **RTX 4070 Laptop** (2.13) — the
default retyped runtime per backend:

| Backend | Q4_0 | Q2_0 | native TQ1_G128 | default |
|---|---|---|---|---|
| CPU (x86 AVX2) | **1327 ms** | ~2700 ms | ~4400 ms | Q4_0 |
| CUDA | 52 ms | **38 ms** | 47 ms | Q2_0 |
| Vulkan | **66 ms** | 133 ms | 114 ms | Q4_0 |
| Metal | — | — | — | Q4_0 (unmeasured) |

Note the ternary format is *not* the fast path: on CPU the Q4_0 retyping is ~3.3×
faster than running TQ1_G128 natively.

**Memory — NO SUCH NUMBER IS PUBLISHED.** No RAM figure, no VRAM figure, no
resident-set measurement appears anywhere in the sources I read for either model.
The only memory statement is qualitative (2.9, verbatim):

> The cache-aware streaming path carries constant-memory caches rather than a
> growing KV, so it stays unbounded for the same reason.

"constant-memory" is not a measurement. Disk footprint is *not* memory, but it is
the one number that bounds it, so for reference the published file sizes are
(2.9, 2.13): Nemotron Q4_K_M **496 MB** / Q8_0 751 MB / F16 1.28 GB / F32 2.55 GB;
Parakeet Redux TQ1_Q4_K **156,696,672 B** / TQ1_Q8_0 159,121,504 B / TQ1_F16
179,312,288 B. **Peak resident memory for either model is unmeasured by anyone I
could find, and Sotto cannot state a memory budget until it measures one itself.**

### The decisive question

> **Can a Tauri/Rust process reach both models through a C or C++ boundary, with
> no Python resident?**

**For Nemotron 3.5: YES.** Established directly — upstream-supported family, first-class
Rust binding, static-by-default link, and a worked Tauri packaging example in the
binding's own README (2.8).

**For Parakeet Redux as currently specified (`tq1_g128`): NOT WITHOUT A FORK.**
The C boundary is fine — the language boundary is not the problem. The problem is
that the weights' tensor type does not exist in any upstream release. The same
runtime reaches the same *architecture* fine through a different quantisation, and
upstream Parakeet variants are directly loadable.

**No Python is required on either path.** The Python bindings are an option
alongside TypeScript, Rust, and Swift (2.3), not a dependency of the C library.

### Two further facts that will shape the architecture

**Concurrency limit.** From `transcribe.h` (2.5, verbatim):

> KNOWN 0.x LIMITATION — concurrent COMPUTE is not yet supported: at most
> one transcribe_run / transcribe_run_batch / active stream may be in
> flight across ALL sessions of a given model at a time.

So two *different* models can compute concurrently, but two streams off *one*
model cannot. A desktop app that ever wants both the Nemotron stream and a second
Parakeet pass on the same audio concurrently needs two loaded models, not two
sessions. The Rust binding enforces this with a per-model mutex (2.8).

**Pre-1.0 ABI.** From `transcribe.h` (2.5, verbatim):

> This library is pre-1.0. The on-disk ABI MAY break between 0.x minor
> releases. Consumers should rebuild against matching headers and
> should not assume any layout, enum value, or symbol set is frozen.

A public repo that vendors a prebuilt `libtranscribe` is carrying a binary that
can break under it. Budget for pinning the exact version and rebuilding on bump.

---

## NOT ESTABLISHED

Questions I could not answer from primary sources. Each is left open on purpose.

1. **`transcribe_run()` and `transcribe_model_load_file()` prototypes.** My fetch
   of `include/transcribe.h` truncated in the middle ("estimated 35927 tokens
   exceeded 16000; omitted middle content"). Their *names* appear verbatim in doc
   comments I did read, but I did not read their signatures. Re-fetch the header
   in ranges before writing any host code.
2. **Peak memory for either model.** No published RAM/VRAM figure exists in the
   sources I read. Only "constant-memory caches" (2.9). Must be measured locally.
3. **Peak memory or streaming behaviour for Parakeet Redux specifically.** No
   upstream model doc exists for it, because upstream does not support it. The
   ternary QUANTIZATION.md (2.13) publishes encoder latency and WER but no
   resident-memory number and no streaming statement.
4. **Whether `parakeet-redux` is streaming-capable at all.** Upstream marks
   `streaming` per family (2.3) and `parakeet-redux` is not in that table; the
   ternary repo's card does not claim streaming. **Unverified either way.** If
   Sotto needs streaming from this second model, this is an open question, not a
   settled no.
5. **The base model's licence.** `Nairod785/parakeet-redux-gguf` declares
   `license: cc-by-4.0` (2.12) and `base_model: moondream/parakeet-redux`. I did
   **not** read `moondream/parakeet-redux`'s own licence. The CC-BY-4.0 tag is a
   third party's claim about their own quantised derivative; it says nothing
   about what Moondream permits. If Sotto ships Parakeet Redux, this must be read
   directly — it is a second licence gate I was not asked to open but that the
   stack implies.
6. **NVIDIA / Linux Foundation trademark policy.** OpenMDW-1.1 imposes no
   attribution or credit clause (see Question One), so the question of whether
   using the "Nemotron" name in Sotto's UI or docs is restricted was not
   answered. The openmdw.ai footer links a trademark policy I did not open.
7. **What "notices of origin" concretely means for this model.** The clause is
   quoted above; the *set* of notices that would satisfy it is not enumerated
   anywhere I read. Nobody has established what NVIDIA considers the notices of
   origin for these artefacts.
8. **`NVIDIA/NeMo-Speech.cpp`.** The upstream model card (1.3) names it as the
   native C++ runtime for this model and shows a `nemo-speech transcribe` CLI —
   while transcribe.cpp independently supports the same model. I did not read
   that repository's licence, API, or build, so I cannot say whether it is a
   viable or better alternative. It may be a competing option the roadmap has
   not considered.
9. **Model-specific streaming latency on desktop hardware.** Every streaming
   number in 2.9 is for the offline `[56, 13]` path; the doc says so explicitly
   (2.9, verbatim):

   > Published latency numbers cover the offline `[56, 13]` path; the sub-1.12 s
   > streaming settings are functionally validated (byte-equal at R=13) but not
   > separately benchmarked.

   So the latency Sotto's overlay would actually experience is unmeasured.
10. **Windows CUDA/Vulkan behaviour in practice.** Release assets exist for both
    (2.2) and the build is documented, but I read no report of these running on a
    consumer desktop.

---

## WHAT WOULD CHANGE THE VERDICT

**To SHIPPABLE — one fact suffices:** upstream `handy-computer/transcribe.cpp`
publishes a release whose `patches/ggml/` contains `0003-tq1_g128-ternary.patch`
(or an equivalent `GGML_TYPE_TQ1_G128` in a tagged release). Verifiable with one
API call: `GET /repos/handy-computer/transcribe.cpp/contents/patches/ggml?ref=v<next>`.

Alternatively, and more cheaply: **Sotto drops the ternary variant** and uses an
upstream-published Parakeet quantisation (`Q4_K_M` or better) instead. That
removes the fork dependency entirely and resolves finding 1 today.

Both paths also require the architecture decision that makes finding 2 moot or
small: **Sotto downloads weights at first run rather than bundling them**, so
OpenMDW-1.1's redistribution clause never triggers and only the MIT notice
obligation from transcribe.cpp applies.

**To NOT SHIPPABLE:** a written term from NVIDIA or the Linux Foundation
restricting redistribution of the weights inside a distributed binary, or
restricting commercial use of the outputs. Nothing in OpenMDW-1.1 as read on
2026-10-05 says either — but the licence text is not pinned in the model repo,
so this could change without notice to the project. **This is the one gate where
a re-read is cheap insurance and a change would be silent.**

**Would NOT change the verdict:** the MIT licence of transcribe.cpp (already
clear), the availability of Nemotron support (already clear), or the absence of a
Python dependency (already clear).