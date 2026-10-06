# Sotto caption worker

Fills the Electron panel's caption area. System audio in, streamed captions out.

```
python sotto_worker.py                 # live loopback capture
python sotto_worker.py --selftest      # prove the model with no audio device
```

## The contract

JSON Lines on **stdout**, one object per line, flushed immediately. Nothing else
goes to stdout; diagnostics go to stderr.

```json
{"type":"status","state":"model-loaded","model":"...","providers":["CPUExecutionProvider"],"load_s":4.48,"rss_mb":912.3,"peak_rss_mb":912.3}
{"type":"caption","text":"Can I leave","start":13.44,"end":14.00,"model":"nemotron-3.5-asr-streaming-0.6b-int8"}
```

States: `boot`, `model-loading`, `model-loaded`, `device`, `capture-started`,
`selftest-start`, `selftest-done`, `done`, `error`. Pre-load lifecycle detail travels on
`boot` as a `stage` (`start`, `lang`, `providers`), the convention this file already used.

## Model

`DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu` (rev
`9e0b74a6c8a803296cafd9c9f66cf18d485c4179`) — the same cache-aware
FastConformer-RNNT as three ONNX graphs (`encoder` / `decoder` / `joint`) plus
`silero_vad.onnx`, in the same `onnx-community` layout the worker has always
driven (`genai_config.json`, `audio_processor_config.json`, `vocab.txt`).
1.07 GB on disk under `models/`. **`config.json` selects this one.**

The INT4 export (`onnx-community/…-onnx-int4`, rev `8364d9e2…`, 756.59 MB) is
still on disk and still works — `--model models/nemotron-3.5-asr-streaming-0.6b-int4`
selects it, and it is fluent too now (see below). Nothing else differs: same
class, same flags, same JSONL.

The one structural difference between the two exports is `left_context` (56 for
INT4, 70 for INT8), so the encoder's cross-attention cache is allocated from
the shapes the encoder graph declares and cross-checked against
`genai_config.json`. It is no longer a literal in the source.

`onnxruntime-genai` 0.17.1 is used **only** for `create_streaming_processor()`,
the generator-supplied cache-aware feature front end. It returns exactly the
encoder's `(1, 65, 128)` input, so no feature maths is reimplemented here.

`onnxruntime-genai` cannot run the decode itself: `nemotron_speech` is not a
registered multi-modal type in 0.17.1 and `Engine` rejects it as
"decoder-only model". The RNN-T greedy loop is therefore implemented here over
the raw graphs.

## Decode: the one thing not to get wrong

The RNN-T greedy search is a walk of the (time, label) grid: at the current
frame, `argmax` the joint; a blank advances the frame, a symbol is emitted and
the decoder is re-run. Two conventions decide whether the output is words or
word salad, and both were wrong here until 2026-10-06.

**1. The prediction vector is the decoder's LAST output — there is no label
cursor.** The LSTM emits position *i* after consuming `targets[:i+1]`, so with
`targets = [newly emitted symbol]` and a carried `h`/`c`, position 0 is the new
prediction. The previous code kept a cursor `k0` counting emitted symbols and
used it to slice `decoder_output`; that array only ever holds 1-2 steps, so the
slice emptied and the chunk ended after a couple of symbols.

**2. The prediction network is re-primed at every chunk boundary.** `h`/`c`
return to zero and the first decoder call of a chunk consumes only the blank.
The acoustic history already crosses the boundary in the encoder cache
(`cache_last_channel` / `cache_last_time`); carrying the decoder state as well
duplicates word tails.

Measured, `sample1.flac` (13.44 s), CPU, only the walk differing:

| walk | tokens | output |
|---|---|---|
| old (label cursor + state carried across chunks) | 37 | `go sl cous ands droom for night' an somece of on moni …` |
| corrected, state carried across chunks | 86 | `Goinging along country roadskingss infty schoolros dayy …` |
| corrected, state re-primed per chunk | 81 | `Going along Slushy Country roads Speaking in School Day For a fortnight …` |

Carrying the full token list *and* `h`/`c` (the older repetition bug) is a third,
distinct failure and is still avoided: each decoder call consumes only what it
has not consumed yet.

## Providers — read this before trusting any RTF

`onnxruntime.get_available_providers()` on this host, verbatim:

```
['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
```

**Registered is not working.** `choose_providers()` therefore **probes CUDA
with a real session** and drops it if the probe session does not actually carry
it, reporting the reason in the `boot` line (`note:`). Never treat
`get_available_providers()` as evidence that the GPU was used — read the
`providers` field of the `model-loaded` status line, which is the session's own
answer.

MEASURED 2026-10-06: on this host today the probe **succeeds** — the `boot`
line reports `note: ""`, `providers_selected: ["CUDAExecutionProvider",
"CPUExecutionProvider"]` and the `model-loaded` line confirms
`providers: ["CUDAExecutionProvider", "CPUExecutionProvider"]`. The older
README text here claimed CUDA always failed to `dlopen` (`cublasLt64_13.dll`
missing, CUDA 12.8 vs the required 13); that was true on the day it was written
and is **no longer**, which is why the RTF below are GPU numbers. The probe
stays: it is what makes the difference visible instead of assumed.

Two related traps on this host:

- The CPU wheel `onnxruntime` 1.30.0 and `onnxruntime-gpu` install into the
  **same** package directory; whichever ran last owns it. A CPU install silently
  removes the GPU build.
- CUDA/cuDNN DLLs live inside `torch/lib` and `nvidia/*/lib`, not on `PATH`.
  `_add_cuda_dll_dirs()` registers them before importing onnxruntime. Without it
  CUDA cannot load even with the GPU wheel installed.
- `onnxruntime-genai` 0.17.1 requires ORT API 26, so `onnxruntime-gpu==1.23.2`
  (which speaks API ≤23) breaks genai with a DLL load failure. The two must be
  version-matched.

## Known limitation — transcript quality

**Resolved 2026-10-06.** The "English-like but degraded" output was NOT the 4-bit
quantisation. It was this file's greedy walk, in two defects:

1. a label cursor `k0` that counted emitted symbols but sliced an array holding
   only 1-2 decoder steps, so the walk ran off the end of it;
2. the decoder LSTM state carried across the chunk boundary on top of the
   encoder cache that already carries the acoustic history, duplicating word
   tails.

Both are fixed. Same file (`sample1.flac`, 13.44 s), same weights, only the walk
changed — 37 tokens of word salad with `rc=0` became fluent English.

```
INT8 (shipped, CUDA): Going along  slushy Country roads  speaking damp  in dr
  drafty school  day For a fortnight He'll have  an appearance At some Sunday
  morning and  he can come to  immediate          94 tokens, RTF 0.144
INT4 (revert flag, CUDA): Going along Slushy Country roads Speaking  in School
  Day For a fortnight He'll have  an appearance At some Sunday morni and  he
  can come to  immediate                           80 tokens, RTF 0.110
```

INT8 recovers ~14 more tokens and is what `config.json` points at; it costs
1.07 GB of disk and ~265 MB of peak RSS more than INT4 (2393.7 vs 2129.1 MB).
INT4 is the cheaper arm and no longer a degraded one.

History and provenance: `docs/accuracy-int4-vs-fp16-20261006.md` (which
correctly localised the loss to "the int4 path" and named the missing cell)
and `docs/int8-route-20261006.md` (which ran that cell). The FP16 export
(`soniqo/…-ONNX-FP16`) remains a different generation and was not run.

## Audio

- `device_candidates()` builds the ordered tap list: an explicit `--device`, then
  the shell's `SOTTO_AUDIO_DEVICE` (only set when the owner asked for one), then
  `config.json`'s `audio.device`, then `audio.preferred_devices`, then
  `PREFERRED_DEVICES`, then remaining non-microphone inputs. One entry per
  PHYSICAL endpoint: Windows lists one cable under several host-API indices with
  different truncated names, and rotating across those would re-open the same
  dead device.
- Candidates are TRIED, not trusted. A candidate that stays below `--tap-peak-floor`
  (default 0.002) for `--tap-window` seconds (default 6) with no caption is
  closed and the next one opened, logging
  `{"type":"status","state":"device-rotated","from":…,"to":…,"reason":"flat","peak":…}`.
  `peak` is that device's own maximum; `run_peak` is the run's. When every
  candidate is flat the run ends on `state=device-exhausted`.
- Capture uses a **callback** stream. Blocking reads fail on this host with
  `PaErrorCode -9999`.
- The device is asked for 16 kHz mono directly (PortAudio/WASAPI converts); if it
  refuses, capture falls back to the native rate and resamples with numpy. Exact
  integer ratios use block averaging. **No scipy.**
- The callback only enqueues. ASR runs on a separate thread, so a slow chunk
  never blocks capture.
- `use_vad` is read from `config.json` and forwarded to the `StreamingProcessor`; it is **on**.
  It is not a passive flag: when the shipped Silero VAD (threshold 0.3 / silence 3360 ms /
  prefix 560 ms) withholds a chunk, `process()` returns `None`. `run_chunk` counts those in
  `vad_gated_chunks` and advances the clock instead of dying on the `None`.
  `WORKER_STATS` and the final `done` status both carry `vad_gated_chunks`, so "the VAD acted"
  is a number rather than an assumption. On `assets/sample1.flac` it is `0` — that clip has no
  3.36 s of silence to gate.

### Speech/music gate (`SOTTO_GATE`)

`SpeechMusicGate` decides, per 560 ms chunk and before the encoder, whether the chunk is speech.
The feature is TEMPORAL, not spectral: it splits the chunk into 20 ms sub-frames and measures
the dB span of their RMS. A stationary drone/tone/ambient bed barely moves inside 560 ms;
speech is syllabically modulated and swings far wider. The span is a RATIO, so it is immune to
the automatic gain upstream. Thresholds: `GATE_DB_RANGE_MIN` (18 dB), `GATE_RMS_FLOOR` (0.004)
and `GATE_HOLD_CHUNKS` (3, a hangover so a stop closure inside a word does not chop the line).
A withheld chunk never reaches the encoder and is counted in `music_gated_chunks`, which
`WORKER_STATS`, the `done` status and the `selftest-done` status all carry. It is ON by default
for the LIVE branch and OFF for the file/`--selftest` branch (which every existing oracle
compares against); `SOTTO_GATE=1` turns it on in BOTH and `SOTTO_GATE=0` is the control.
When EVERY chunk is gated the run ends on `verdict=captions-all-music-gated` /
`state=music-only-capture` — the endpoint carried something that is measurably not speech, and
the model was never asked. Policy, measurements and cost: `docs/audit/speech-separation.md`.

## Config

`config.json` — `audio.device` (substring or null), `audio.preferred_devices`, `audio.block_ms`,
`model.dir`, `model.lang_id`, `model.use_vad`, `model.providers`, `output.min_chars`.

Every key above is READ by `worker/sotto_worker.py`. Five keys that nothing read were **deleted**
on 2026-10-06 (`audio.match`, `audio.sample_rate`, `audio.channels`, `audio.latency`,
`output.partial`) and two that nothing read were **wired** and are now live: `audio.block_ms`
(passed to `LoopbackTap`, sets the tap's block and the WASAPI pump's poll period) and
`output.min_chars` (the minimum trimmed-caption length both emitters print; below 1 is refused
back to 1). Nothing is silently ignored: see `docs/audit/config-inert-fixed.md`.

`model.lang_id` is the **language prompt**, resolved by `worker/lang_prompt.py` from the
model's OWN `models/*/languages.json` (never a copy of it). Accepted values:

| value | meaning |
|---|---|
| an id | any slot the table declares — `0` en-US, `12` pt-BR, `13` pt/pt-PT |
| a tag | `"pt-BR"`, `"pt"`, `"pt_BR"`, `"en"` — looked up in the model's dictionary |
| `"auto"` | the model's own `autoSlot`, 101 — **the shipped default** (2026-10-06) |
| `"os"` | the host's USER locale (`GetUserDefaultLocaleName`), mapped through the table, falling back to `auto` when the locale names no slot — an accepted value on request, no longer the default |

Resolution order: `--lang-id` > `SOTTO_LANG_ID` > `config.json` > the shipped default.
The env rung exists because `worker-bridge.js#spawn` builds argv as
`python [...extraArgs, workerPath]`, so a flag handed over by the shell lands BEFORE the
script path and is eaten by the interpreter — the same reason `SOTTO_AUDIO_DEVICE` exists.

A value the model does not declare (`999`, `-1`, `"klingon"`) is **refused**: exit **2**, one
`{"type":"status","state":"error","stage":"lang-id"}` line on stdout, the reason on stderr,
and **no model session is built**. It is never clamped and never silently ignored — measured:
onnxruntime itself ACCEPTS `lang_id=999` and returns numbers, so the graph does not police
the slot.

Every run names what it resolved:
`{"type":"status","state":"boot","stage":"lang","lang_id":12,"lang":"pt-BR","source":"config:os-locale","table":"…languages.json"}`.

**Why `"auto"` and not a hardcoded `pt-BR` or `en-US` (measured 2026-10-06):** the shipped
value must not silently destroy one language to favour another. Both other candidates did,
measured on the SAME clip each time — `"os"` resolves to `pt-BR` (12) on this host and prompt 12
on the bundled **English** sample (`worker/assets/sample1.flac`) collapsed **94 tokens to 10**;
the old literal `0` (en-US) collapsed the Portuguese sample (`_main/pt-br-sample.wav`) to
**5 tokens vs 18**. `"auto"` (autoSlot 101) got **89/94** on English and **18/18** on Portuguese —
the only one of the three good on BOTH. Three repeats each, byte-stable. The honest cost, named:
on English `"auto"` trails the language-matched explicit prompt `0` by 5 tokens (89 vs 94, ~5%),
and this is a two-sample result, not a WER. A user who speaks a third language gets the model's
own language-ID over its 84 declared slots, not a forced pt-BR/en-US. Override per session with
`--lang-id` > `SOTTO_LANG_ID` > this file. Receipt: `_main/lang-id-default-arms.py`,
`_main/langdef-arms.json`.

## Detokenisation

The exported `tokenizer.json` is **malformed** — `transformers` raises
`Exception: expected ',' or '}' at line 52384 column 17`. Decoding uses
`vocab.txt` (13088 entries, `13087 = <blank>`) with the sentencepiece metaspace
`▁` → space. Language-tagged tokens (`<en-US>`, `<pt-BR>`, …) are skipped. The
INT4 and INT8 exports ship byte-identical vocabularies (verified entry count and
blank position), so a transcript is comparable across the two.