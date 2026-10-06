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

## 5. Quality table, per the model's own README (`original/int8/README.md:78-84`)

| variant | encoder | total | the README's word |
|---|---|---|---|
| FP32 | 2380 MB | 2479 MB | ⭐ Best |
| INT8 | 922 MB | 1021 MB | Good |
| INT4 | 658 MB | 757 MB | ⚡ Fastest |

Memory measured on this box (session build + one real inference, one process per arm):
int4 756 MB on disk → **924 MB RSS**; int8 1020 MB → **1192 MB RSS**
(`_main/precision-ram-probe-int4.log`, `-int8.log`).

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
