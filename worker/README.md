# Sotto caption worker

Fills the caption area of the Sotto panel. System audio in, streamed captions out. The panel files are
`app/electron/panel.{html,css,js}` and the shell that hosts them today is WebView2
(`app/webview/sotto_webview.py`); the rest of `app/electron/` is the EARLIER Electron shell, kept as the
reference arm and not a fallback.

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

States — the COMPLETE list the code emits, each with its emit site in `worker/sotto_worker.py`:
`boot` (`:2179`, and `:2301`/`:2342` carrying a `stage` — `start`, `lang`, `providers`), `model-loading`
(`:2359`), `model-loaded` (`:2375`), `gate` (`:2408`; carries `gate=on|off`, its `source` and the three
thresholds), `device` (`:2477`), `capture-started` (`:3014`), `device-rotated` (`:3000`, reason
`open-failed`; `:3153`, reason `flat`), `device-exhausted` (`:3178`), `silent-device` (`:3226`),
`music-only-capture` (`:3262`), `no-speech-in-capture` (`:3309`), `selftest-start` (`:1919`),
`selftest-done` (`:1953`), `done` (`:3349`), `error` (ten sites: `:1914`, `:2191`, `:2289`, `:2356`,
`:2366`, `:2429`, `:2464`, `:2471`, `:2881`, `:2990`).

Pre-load lifecycle detail travels on `boot` as a `stage` (`start`, `lang`, `providers`), the convention
this file already used. **This list used to stop at nine words while the code emitted six more** —
`gate`, `device-rotated`, `device-exhausted`, `silent-device`, `music-only-capture` and
`no-speech-in-capture` — so a consumer written from this file painted the worker's own failure vocabulary
raw. **The line numbers are the 173388 B revision (mtime 2026-10-07 03:21:10) and they DRIFT** — the worker
moved by one line while this file was being corrected, so re-grep (`grep -n 'state="' worker/sotto_worker.py`)
before trusting one.

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

**2. The prediction network CARRIES ACROSS every chunk boundary, and the first
decoder call of a chunk is fed the LAST EMITTED SYMBOL — not the blank.**
(Changed 2026-10-06, `docs/audit/predictor-carry-cura.md`.) The acoustic history
crosses the boundary in the encoder cache (`cache_last_channel` /
`cache_last_time`) *and* the predictor's `h`/`c` crosses with it; the seed for
the new chunk is what the last chunk actually ended on.

This was **re-primed per chunk** (`h`/`c` → 0, first decode eats `<blank>`) until
2026-10-06, on the strength of the 13.44 s-clip table below. That table was
measuring the wrong arm: it carried `h`/`c` but still fed the blank, so the
predictor restarted mid-word and glued tails (`backnst`, `weekendn`, `gotral`) —
the glue, not the carry, is what it measured. Measured on the reference video
`PQw0TRzpCkk` (2 692 chunks × 560 ms, CUDA, int8, only the predictor policy
differing, `_main/sotto-vs-ref-decode-arms.py`):

| walk | tokens | words | % of ref | empty chunks | WER |
|---|---|---|---|---|---|
| re-prime per chunk (old shipped) | 5 661 | 2 183 | 50.7 % | 1 597 (59.3 %) | 0.6105 |
| carry `h`/`c`, seed `<blank>` | 8 192 | 3 304 | 76.8 % | 622 (23.1 %) | 0.5954 |
| **carry `h`/`c`, seed last symbol (shipped)** | **10 738** | **4 279** | **99.4 %** | **270 (10.0 %)** | **0.1536** |

Carrying the full token list *and* `h`/`c` (the older repetition bug) is a third,
distinct failure and is still avoided: each decoder call consumes only what it
has not consumed yet. The predictor is reset in exactly two places, both
start-of-stream: `__init__` and `reset_stream_state()`.

Measured, `sample1.flac` (13.44 s), CPU, only the walk differing — the original
table, kept for provenance:

| walk | tokens | output |
|---|---|---|
| old (label cursor + state carried across chunks) | 37 | `go sl cous ands droom for night' an somece of on moni …` |
| corrected, state carried across chunks + seed `<blank>` | 86 | `Goinging along country roadskingss infty schoolros dayy …` |
| corrected, state re-primed per chunk (was shipped) | 81 | `Going along Slushy Country roads Speaking in School Day For a fortnight …` |

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
- Candidates are TRIED, not trusted. **A CAPTION is the only thing that settles the ladder.** `peak >=
  floor` proves the tap HEARS SOMETHING, not that it hears SPEECH, and the model's own front end gates
  non-speech (`vad_gated_chunks`); so the peak floor only **classifies** and the ladder keeps looking. A
  candidate that stays below `--tap-peak-floor` (built-in default 0.002, `sotto_worker.py:219`) for
  `--tap-window` seconds (built-in default 6.0, `:218`) with no caption is closed and the next one opened.
  The two things that can settle a candidate are `settled = True` at **`:3053`** (a caption arrived) and
  at **`:3059`** (this is the re-entered fallback and it carries signal); the per-candidate ledger row is
  appended at **`:3080`**; a rotation logs
  `{"type":"status","state":"device-rotated","from":…,"to":…,"reason":"flat","peak":…,"run_peak":…}`
  (**`:3153`**; the open-failed rotation is `:3000`), where `peak` is that device's own maximum and
  `run_peak` is the run's. A candidate is only credited as the run's device once it produced a caption
  **or** was the re-entered fallback (`proved_alive`, **`:3109`**).
- **When every candidate has been opened once and none produced a caption, the ladder RE-ENTERS the
  loudest signal-carrying candidate instead of ending** (**`:3136-3145`**: `rung=fallback`, `rung_why`
  says why, and `best_carried["retried"]` allows it AT MOST ONCE), so a live run keeps streaming rather
  than exiting on the owner with nothing. `state=device-exhausted` (**`:3178`**) is therefore the case
  where no candidate carried signal at all — `outcome in ("all-flat","open-failed")`, which includes
  every candidate failing to OPEN. **This is the 2026-10-06 change:** before it, a candidate was
  abandoned on the floor alone and "every candidate flat" always ended the run.
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
  3.36 s of silence to gate. The code's own fallback is now `True` as well
  (`worker/sotto_worker.py:2332` — `bool(cfg.get("model", {}).get("use_vad", True))`, F14 cured
  2026-10-07): the default used to be `False` in the code while `config.json` shipped `true`, so a
  config file missing the key ran with the VAD OFF and contradicted this README. The three numbers
  above are the EXPORT's choices, not NVIDIA's or Silero's recommendation —
  `docs/model-specs/README.md` §4 carries that distinction with the upstream citations.

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

**An ABSENT `model.lang_id` now means `auto`, NOT the host locale (F13, cured 2026-10-07).** The last rung
used to pass `None`, and `None` is `lang_prompt.resolve_lang_id`'s sentinel for `"os"` — so a config file
with the key deleted silently conditioned every run on the host's USER locale (on this pt-BR host, `12` =
`pt-BR`, which collapsed the bundled ENGLISH sample from 94 tokens to 10). `sotto_worker.py:2285` now
passes `"auto"` on that rung; the `boot stage=lang` line names the resolution it used
(`source=default:auto`). `"os"` is still resolved when it is written EXPLICITLY — the sentinel in
`worker/lang_prompt.py:236` is untouched; it was the caller that stopped reaching it by accident.

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