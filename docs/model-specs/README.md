# Model specs — the model's OWN documentation, consolidated

**Read this before changing anything in `worker/`.** Every fact below is quoted from a file
that shipped WITH the model, copied verbatim into `original/` (sha256 verified against the
source at copy time). Nothing here is reverse-engineered.

```
original/int4/{genai_config.json, model_config.json, audio_processor_config.json, tokenizer_config.json}
original/int8/{genai_config.json, model_config.json, audio_processor_config.json, tokenizer_config.json, README.md}
original/fp16/{config.json, languages.json}
original/worker-README.md          <- what OUR worker already documents
```

Source of truth on disk: `worker/models/nemotron-3.5-asr-streaming-0.6b-<prec>/`.
Provenance: `DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-<prec>-cpu`, converted by Microsoft
Olive from `nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b` (`original/int8/README.md:1-30`).

---

## 1. The normative parameters (`original/int4/genai_config.json`)

The model ships its own spec. These are not guesses:

| key | value | meaning |
|---|---|---|
| `type` | `nemotron_speech` | NOT a registered multimodal type in `onnxruntime-genai` 0.17.1 |
| `vocab_size` | `13088` | |
| `blank_id` | **`13087`** | the RNN-T blank / joiner-blank token |
| `max_symbols_per_step` | **`10`** | upper bound on labels emitted per encoder frame |
| `chunk_samples` | **`8960`** | 0.56 s @ 16 kHz — the streaming chunk |
| `sample_rate` | `16000` | |
| `num_mels` / `fft_size` / `hop_length` / `win_length` | `128` / `512` / `160` / `400` | mel front end |
| `preemph` | `0.97` | |
| `subsampling_factor` | `8` | |
| `left_context` | `56` (int4) / `70` (int8) | cross-attention cache depth — **differs per export** |
| `conv_context` | `8` | |
| `pre_encode_cache_size` | `9` | |
| `encoder` | 24 layers, hidden 1024 | |
| `decoder` | 2 layers, hidden 640 | |
| `vad.threshold` | `0.3` | Silero VAD, shipped tuned |
| `vad.silence_duration_ms` | `3360` | |
| `vad.prefix_padding_ms` | `560` | |

### 1.1 The chunk size is a property of the EXPORT, not a knob in this repo

The card offers a **menu of chunk sizes — 80 / 160 / 320 / 560 / 1120 ms** — expressed as
`att_context_size = [56, right_context]` with `right_context ∈ {0, 1, 3, 6, 13}`, "each chunk processed in
non-overlapping fashion" ([model
card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b), [transcribe.cpp's port
doc](https://github.com/handy-computer/transcribe.cpp/blob/main/docs/models/nemotron-3.5-asr-streaming-0.6b.md)).
**The export on disk is fixed at one of them.** `worker/models/nemotron-3.5-asr-streaming-0.6b-int8`
declares `"chunk_samples": 8960` (= 560 ms) and `left_context: 70` in its own `genai_config.json`, and its
card says so in words ("Chunk size 0.56s (8,960 samples @ 16kHz)"). The geometry is baked into the graphs:
the encoder's caches are allocated from the shapes the encoder declares and cross-checked against
`genai_config.json` (`worker/README.md`), so editing `chunk_samples` in the JSON is not a supported way to
change cadence. Upstream ships SIBLINGS with different geometry — which is the evidence that this is an
export property, all read 2026-10-07:

| export | `chunk_samples` | `left_context` |
|---|---|---|
| `DimQ1/…-onnx-int8-cpu` (**the one this repo ships**) | 8960 (560 ms) | 70 |
| `DimQ1/…-onnx-fp32-c056-cpu` | 8960 (560 ms) | 56 |
| `DimQ1/…-onnx-fp32-c112-cpu`, `…-onnx-gpu-cuda` | 17920 (1.12 s) | 56 / 140 |
| `csukuangfj2/sherpa-onnx-…-{80,160,560,1120}ms-int8-2026-06-11` | one export per chunk size | — |

**Consequence for the product:** `audio.block_ms` (100 in `worker/config.json`) changes only the CAPTURE
granularity — it cannot make the decoder commit sooner. A faster caption needs a different export
(`chunk_samples` 1280 / 2560 / 5120 = 80 / 160 / 320 ms), and that trades latency for accuracy: the card's
own averages fall **10.38 → 9.49 → 9.12 → 8.84 %** FLEURS WER as the chunk grows 80 ms → 320 ms → 560 ms →
1.12 s.

**I/O names are declared, not to be invented** (`genai_config.json`, `encoder.inputs`):
`audio_signal`, `length`, `cache_last_channel`, `cache_last_time`, `cache_last_channel_len`,
`lang_id`; outputs `outputs`, `encoded_lengths`, `cache_last_channel_next`,
`cache_last_time_next`, `cache_last_channel_len_next`. Decoder: `targets`, `h_in`, `c_in` →
`decoder_output`, `h_out`, `c_out`. Joiner: `encoder_output` + `decoder_output` → `joint_output`.

`audio_processor_config.json` is the mel spec (`n_fft 512`, `hop 160`, `n_mels 128`,
`window_length 400` hann, `fmin 0`, `fmax 8000`, `dither 1e-05`, `preemphasis 0.97`,
`log_zero_guard_type add`, `log_zero_guard_value 1e-10`, `center true`, `mag_power 2.0`).

## 2. The canonical decode, as the model's own README gives it

`original/int8/README.md:44-63`, verbatim:

```python
model = og.Model("DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu")
processor = og.StreamingProcessor(model)
tokenizer  = og.Tokenizer(model)
generator  = og.Generator(model, params)
generator.set_runtime_option("lang_id", "11")   # Russian
chunk = np.zeros(8960, dtype=np.float32)        # 0.56s @ 16kHz
inputs = processor.process(chunk)
if inputs is not None:
    generator.set_inputs(inputs)
    while not generator.is_done():
        generator.generate_next_token()
```

Two facts this settles: **the chunk is 8960 samples** and **`lang_id` is set per stream**.
A full reference app is linked at `README.md:70` (`DimQ1/nemotron-speech-csharp`).

Our own `original/worker-README.md` states the algorithmic rule the same way:

> "The RNN-T greedy search is a **row-major walk of the (time, label) grid**: inside one encoder
> frame, advance label positions until a non-blank appears — that is the next symbol; a blank
> advances the frame cursor and is free. The trap is the decoder carry. Carrying the LSTM state
> `h`/`c` *and* re-feeding the accumulated token list consumes every symbol twice."

**Rule for this repo:** a non-blank advances the LABEL cursor within the frame; a blank advances
the TIME cursor. `max_symbols_per_step: 10` is the ceiling on one frame's label run.
Feeding the decoder a label list that is not the running prefix (e.g. `[blank, last_symbol]`)
is a deviation from both texts above.

## 3. Language IDs — `original/fp16/languages.json`

`numPrompts: 128`, `autoSlot: 101`. The entries that matter here:

| language | id |
|---|---|
| `en-US`, `en` | **0** |
| `pt-BR` | **12** |
| `pt-PT`, `pt` | **13** |
| `auto` | **101** |

**The engine's own default is `0` = `en-US`; `auto` is the model's `autoSlot` (101).** The card is explicit
about the default path: "the pipeline uses the default language prompt (index 0, `en-US`)". So ANY caller
that forgets to send the prompt is silently conditioning on English — the exact failure the 2026-10-06
default change exists to prevent, and the reason an ABSENT `model.lang_id` now resolves to `auto` in the
worker (`worker/README.md`, and the `boot stage=lang` line names which rung won).

What the prompt is worth, from the card's own FLEURS table (WER %, LangID columns against auto-detect
columns, [Performance](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b#performance)):

| language | LangID 80 ms | LangID 320 ms | LangID 560 ms | LangID 1.12 s | auto 80 ms | auto 320 ms | auto 560 ms | auto 1.12 s |
|---|---|---|---|---|---|---|---|---|
| Portuguese (pt-BR, pt-PT) | 6.29 | 5.81 | 5.65 | 5.48 | 6.41 | 5.82 | 5.57 | 5.47 |
| English (en-US, en-GB) | 9.43 | 8.27 | 7.99 | 7.91 | 9.72 | 8.84 | 8.80 | 8.84 |
| German (de-DE) | 9.81 | 8.83 | 8.42 | 8.31 | 9.90 | 8.87 | 8.58 | 8.22 |
| **average** | **10.38** | **9.49** | **9.12** | **8.84** | **11.14** | **10.05** | **9.63** | **9.21** |

Portuguese is the case this repo has to read honestly: at 560 ms it is **5.65 (LangID) vs 5.57 (auto)** and
at 1.12 s **5.48 vs 5.47** — a tie, so `auto` costs this host's language nothing. English is where `auto`
is measurably worse (7.99 → 8.80 at 560 ms; 7.91 → 8.84 at 1.12 s): that is the price of not knowing the
language, and the reason `--lang-id 0` stays available for a user who only ever transcribes English.

**RESOLVED 2026-10-06.** `model.lang_id` in `worker/config.json` is `"auto"` (the model's own
`autoSlot`, **101**). It was `"os"` (the host's USER locale, `GetUserDefaultLocaleName`) earlier
the same day, and BOTH silent defaults destroyed a language on the same clip: on this pt-BR host
`"os"` resolved to `12` (pt-BR) and decoding the bundled **English** sample
(`worker/assets/sample1.flac`) with prompt 12 collapsed **94 tokens to 10**; the older literal `0`
(en-US) did the mirror damage to Portuguese (**5 tokens vs 18** on `_main/pt-br-sample.wav`).
`"auto"` scored **89/94 tokens** on the English clip and **18/18** on the Portuguese one — the only
one of the three good on BOTH. `"os"` is still an accepted value (host-locale on request); it is
just no longer the default. It is resolved by `worker/lang_prompt.py`, which reads THIS file rather
than a copy of it, and the resolution order is `--lang-id` > `SOTTO_LANG_ID` > `config.json`.

The literal `0` that used to be here was ALSO dead code, which is the half of this deviation
that was easy to miss: `--lang-id` was declared `default=0`, so `args.lang_id is not None`
was true on every run and the `else` branch reading the config key was unreachable. The key
was documented in two READMEs and had never reached the model.

An id this table does not declare (`999`, `-1`, `klingon`) is **refused loudly, exit 2**,
before a model session is built — never clamped. That refusal is load-bearing and measured:
onnxruntime itself ACCEPTS `lang_id=999` on the encoder and returns numbers (`_main/lang-id-oracle.log`),
so the graph does not police the slot.

## 4. VAD — shipped, tuned, ON (as of 2026-10-06)

`genai_config.json` declares `silero_vad.onnx` with threshold 0.3, silence 3360 ms, prefix 560 ms.
`worker/config.json` sets `"use_vad": true`.

**The option is consumed, not merely stored.** Read back with `get_option`: `use_vad` -> `true`,
`silence_duration_ms` -> `3360`, `prefix_padding_ms` -> `560` (`_main/vad-option-probe.py`).
When it gates a chunk, `StreamingProcessor.process()` returns **`None`** — the model's own README
guards exactly that (`if inputs is not None`). MEASURED: the same digital-silence chunk returns a
`(1,65,128)` feature block 12/12 times with `use_vad=0`, and `None` 10/12 times with `use_vad=1`.
`worker/sotto_worker.py:run_chunk` handles the `None` by counting it in `vad_gated_chunks` and
advancing the clock; before that guard it raised
`TypeError: 'NoneType' object is not subscriptable` and the worker exited 1.

**Where `0.3 / 3360 / 560` come from — and what Silero's own defaults are.** They are the ONNX EXPORT's
numbers, not a NVIDIA recommendation and not a Silero one: `original/int8/genai_config.json:66-68` declares
them, and **the model card never mentions VAD at all** (the word does not appear on
https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b outside this project's own notes). These five
exports checked on 2026-10-07 all declare the SAME three values — `DimQ1/…-onnx-fp32-cpu`,
`…-onnx-fp32-c056-cpu`, `…-onnx-fp32-c112-cpu`, `…-onnx-gpu-cuda` and
`onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` — so this is a deliberate converter default
rather than one repo's accident; **a different conversion of the same architecture chose different numbers
(next paragraph)**, which is the proof that this is a per-export choice and still **not normative**.
Silero's own library defaults are different:
`threshold 0.5`, `min_silence_duration_ms 100`, `speech_pad_ms 30`, `min_speech_duration_ms 250`, plus
hysteresis `neg_threshold = max(threshold - 0.15, 0.01)` and the 512-sample (32 ms) frame the ONNX wrapper
enforces ([`silero_vad/utils_vad.py`](https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py)).
None of those is `0.3 / 3360 / 560`. The shipped values are defensible *because they came with the export*
— but "the model's documentation says so" is FALSE, and this is the file where that distinction lives.

**The numbers are the EXPORTER's choice, and two exporters disagree — which is the general lesson.** The
`DimQ1` family (all five repos named above, including the one this repo ships) declares
`0.3 / 3360 / 560`. A different conversion of the same architecture declares something else:
`onnx-community/nemotron-speech-streaming-es-0.6b-ft` — a Spanish fine-tune — ships
`"vad": {"threshold": 0.5, "silence_duration_ms": 500, "prefix_padding_ms": 300}`
([`genai_config.json`](https://huggingface.co/onnx-community/nemotron-speech-streaming-es-0.6b-ft/raw/main/genai_config.json),
fetched 2026-10-07). So **there is no "the model's VAD setting"**: it is a per-export default, it is not
NVIDIA's (the card never mentions VAD), and it is not Silero's (their own defaults are `0.5 / 100 / 30`).
That same sibling export is also a warning against copying constants between exports — it carries
`vocab_size: 8193`, `blank_id: 8192`, `chunk_samples: 8960`, `left_context: 70`, and its encoder declares
**no `lang_id` input at all** (it is not prompt-conditioned). Every constant in §1 belongs to ONE export.

## 5. Quality table, per the model's own README (`original/int8/README.md:78-84`)

| variant | encoder | total | the README's word |
|---|---|---|---|
| FP32 | 2380 MB | 2479 MB | ⭐ Best |
| INT8 | 922 MB | 1021 MB | Good |
| INT4 | 658 MB | 757 MB | ⚡ Fastest |

Memory measured on this box (session build + one real inference, one process per arm):
int4 756 MB on disk → **924 MB RSS**; int8 1020 MB → **1192 MB RSS**
(`_main/precision-ram-probe-int4.log`, `-int8.log`).

**The precision trade, with published numbers.** The shipped choice is int8 (`worker/config.json:10`);
int4 is the smaller, faster arm. What the two cost in accuracy is published for this model by
`transcribe.cpp` (GGUF quant presets, LibriSpeech test-clean, 2 620 utterances): **F32 3.04 / F16 3.03 /
Q8_0 3.06 / Q6_K 3.07 / Q5_K_M 3.10 / Q4_K_M 3.28** WER %, against a 3.03 % NeMo reference — i.e. ~**0.02
pp** for the 8-bit-class preset and ~**0.25 pp** for the 4-bit-class one
([Nemotron doc](https://github.com/handy-computer/transcribe.cpp/blob/main/docs/models/nemotron-3.5-asr-streaming-0.6b.md)).
Those are that runtime's GGUF presets, not these ONNX exports, and this repo's own measured cost of the
choice is **memory, not WER**: **+268 MB RSS** for int8 over int4 (`AGENTS.md`, deviations table;
`_main/precision-ram-probe-*.log`). Read together: the 8-bit-class arm buys ~0.2–0.25 pp of WER for ~270 MB
— which is the trade this repo took, and the reason int8 is the shipped arm.

**Why a lower-precision COMPUTE path is not the alternative it looks like.** NeMo's own cache-aware
streaming inference script refuses a non-float32 `compute_dtype` outright. In
`examples/asr/cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py`, inside `main()`:

```python
if compute_dtype != torch.float32:
    # NB: cache-aware models do not currently work with compute_dtype != float32
    # since in some layers output is force-casted to float32
    # TODO(vbataev): implement support in future; set `compute_dtype` in config to None by default
    raise NotImplementedError(
        f"Compute dtype {compute_dtype} is not yet supported for cache-aware models, use float32 instead"
    )
```

the config dataclass carries the same note (`# NB: default compute_dtype is float32 since currently
cache-aware models do not work with different dtype`, `compute_dtype: Optional[str] = "float32"`), and
`amp=true` with any other dtype raises `ValueError("amp=true is mutually exclusive with a compute_dtype
other than float32")` ([file](https://github.com/NVIDIA/NeMo/blob/main/examples/asr/asr_cache_aware_streaming/speech_to_text_cache_aware_streaming_infer.py),
fetched 2026-10-07). **Scope, in one clause:** that is a guard in NeMo's streaming inference SCRIPT and
its config schema — the encoder modules themselves carry no such check (I read
`nemo/collections/asr/modules/conformer_encoder.py` and `parts/mixins/streaming.py` and found none). The
consequence for this project is unchanged either way: precision comes from choosing a **quantised export**,
not from running the float32 graph in half precision.

## 6. Known drift between this doc set and the code

1. ~~`original/worker-README.md` says `config.json` selects the **int8** export...~~ **RESOLVED
   2026-10-06**: the shipped `worker/config.json` now selects
   `models/nemotron-3.5-asr-streaming-0.6b-int8` (`left_context: 70`), which is the export the
   worker README always described. The earlier int4 selection is no longer in force.
   Measured cost of that choice: RSS 1192 MB vs int4's 924 MB (`_main/precision-ram-probe-*.log`).
2. ~~`lang_id` is a literal `0` in config instead of being derived from `languages.json`.~~
   **RESOLVED 2026-10-06** — `model.lang_id` is `"auto"` (= autoSlot **101**), resolved from this
   model's own `languages.json` by `worker/lang_prompt.py`; `0` is `en-US`, `12` is `pt-BR`,
   `13` is `pt`, `101` is `auto`. It was `"os"` (host user locale) earlier the same day, and both
   values silently destroyed a language (94→10 tokens English for `"os"`; 18→5 tokens Portuguese
   for `0`) — see §3. The literal `0` was also dead code (the CLI flag's `default=0` shadowed the
   config key on every run) and an undeclared id is now refused with exit 2.
   Oracles: `_main/lang-id-oracle.py` (mechanism), `_main/lang-id-default-arms.py` (default choice).
3. ~~`use_vad: false` while the model ships a tuned VAD.~~ **RESOLVED 2026-10-06**: config is now
   `"use_vad": true`. Flipping the boolean alone changed **nothing measurable on
   `worker/assets/sample1.flac`** — identical 16 captions, 94 tokens, 262 frames, `blank_frac`
   0.6412 — because that clip never contains 3.36 s of silence for the VAD to gate. Re-measured
   later the same day, after another lane changed `lang_id` from the literal `0` to `"os"` (see
   drift item 2), the two arms are **still field-for-field identical** on that clip
   (`after == neg` on 2 captions / 10 tokens / 178 frames / 168 blanks / `blank_frac` 0.9438 /
   `vad_gated_chunks` 0; only `rtf`, `infer_wall_s` and `peak_rss_mb` differ, which is timing).
   On audio that DOES contain a pause (`sample1` + 6.0 s of digital silence + `sample2`, 33.9 s)
   the run **crashed with `TypeError: 'NoneType' object is not subscriptable` and exit 1** until
   `run_chunk` was taught to handle the gated chunk; afterwards it gates 6 chunks and emits
   6 captions vs 4 with the flag off. The flag is a real behaviour change that the bundled sample
   cannot see. Receipts: `_main/vad-arm-*.json` (before/after/neg/gap-on/gap-off),
   `_main/vad-option-probe.py`, `_main/vad-renderer-arms.js`.
4. **The export's own licence tag does not match the base model's** — OPEN, recorded 2026-10-07.
   `DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu`, the repo the weights in `worker/models/` came
   from, declares `"license": "cc-by-nc-4.0"` in its cardData and repeats it on its card ("inherits
   cc-by-nc-4.0 from the base NVIDIA Nemotron model"), while the base model this doc set documents
   publishes **OpenMDW-1.1** (commercial use permitted; only the licence copy and the notices have to
   travel with a distribution). The two statements disagree and this file does not resolve it — see
   `README.md` §"Licence posture", which records the disagreement and names the way out (download the
   weights at first run, or choose an export whose terms match the base).

## 7. ORACLE

One re-runnable check that fails if the central claim of this doc is wrong — that the shipped
config agrees with the model's own declared spec:

```bash
py -3 -c "import json,os,sys; c=json.load(open('worker/config.json')); d=c['model']['dir']; g=json.load(open(os.path.join('worker',d,'genai_config.json')))['model']; print('dir',d); print('blank_id',g['blank_id'],'chunk',g['chunk_samples'],'maxsym',g['max_symbols_per_step']); print('lang_id',c['model'].get('lang_id'),'use_vad',c['model'].get('use_vad')); sys.exit(0 if g['blank_id']==13087 and g['chunk_samples']==8960 else 1)"
```

Exit 0 = the config and the model spec were read from the SAME model and agree on the two
constants every decoder depends on. Exit 1 = they do not; fix before touching decode.

A second oracle covers the language prompt specifically (`_main/lang-id-oracle.py`, rc 0 = OK):
the table is read from the model's own `languages.json`; the documented ids resolve to the
documented tags; `"os"` resolves to the host locale; `999`/`-1`/`klingon` are refused; the
encoder DECLARES a `lang_id` input and changing it changes the encoder output on identical
audio; and `--lang-id`'s default is `None`, so `config.json` is reachable.
