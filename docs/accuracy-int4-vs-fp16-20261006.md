# int4 vs higher precision, measured on the same audio

**Date:** 2026-10-06 · **Repo:** `H:/sotto` · **Question:** `worker/README.md`
→ "Known limitation — transcript quality": *whether the int4 quantisation causes
this is NOT established*.

**Answer in one line:** it is not the model and it is not the audio. The same
checkpoint at INT8 and at FP32 transcribes both bundled clips as fluent English,
byte-identical to each other on `sample1.flac`, while the shipped int4 arm
returns word salad that is a heavily subsampled echo of that same sentence. The
degradation belongs to the **int4 path**, but this run cannot separate "the 4-bit
weights" from "the int4 export's driver" — both changed together, and no
higher-precision export of *that* generation exists to run inside the worker's
own runtime. Section 4 names the measurement that settles it.

---

## 1. What was run

Three arms, one audio file, one checkpoint (`nvidia/nemotron-3.5-asr-streaming-0.6b`),
streaming at the same 560 ms granularity (`genai_config.chunk_samples = 8960`).

| arm | precision | weights on disk | runtime that drives it | audio |
|---|---|---|---|---|
| **A** int4 | INT4 | `encoder.onnx.data` 690 089 984 B | the worker itself, `sotto_worker.py --selftest` (onnxruntime 1.30.0 + `onnxruntime-genai` 0.17.1) | `worker/assets/sample1.flac` |
| **B** int8 | INT8 | `encoder.int8.onnx` 657 601 403 B | sherpa-onnx 1.13.4 streaming transducer | same file |
| **C** fp32 | FP32 | `encoder.data` 2 454 405 120 B | sherpa-onnx 1.13.4 streaming transducer | same file |

Arms B and C were downloaded today from the two sherpa-onnx exports of the same
checkpoint (see §6). Neither decode loop was reimplemented: sherpa owns the mel
front end and the RNN-T greedy walk for B and C.

`sample2.flac` (14.215 s, sha256 `cb5c48a2…` for sample1; both from
`cdn-media.huggingface.co/speech_samples/`) was run through all three arms as a
second item, so the finding is not one clip.

---

## 2. Per-arm evidence

Peak RSS and wall time come from an instrument that runs **outside** the model
process (`I:/Temp/sotto-acc/measure.py`, sampling the child's kernel
`peak_wset` every 100 ms) so the number is not the model grading itself.
`worker/config.json` was **not modified** — arm A ran on the shipped default
(`models/nemotron-3.5-asr-streaming-0.6b-int4`, `use_vad: false`, `lang_id: 0`).

### Arm A — int4, the shipped worker (SAME RUNTIME as production)

```
cd H:\sotto
python worker/sotto_worker.py --selftest --audio worker/assets/sample1.flac
```

* **rc** = 0
* **wall** = 9.391 s (external) · load 2.416 s · infer 2.622 s · **RTF 0.195**
* **peak RSS** = 2131.2 MB external / 2130.3 MB self-reported (agreement 0.04 %)
* **tokens** = 37 · audio_s 13.44 · frames 350 · blank_frac 0.4800 · empty_chunks 5
* **providers actually in the session**: `["CUDAExecutionProvider","CPUExecutionProvider"]`
  and the CUDA probe returned `note: ""` — i.e. **today the GPU loaded**, unlike
  the historical `cuda-registered-but-not-loadable` in the README. This arm's
  wall/RTF are therefore GPU numbers; arms B and C are CPU-only.
* **transcript** (verbatim, `selftest-done.text`):

```
go sl cous ands  droom for night'  an somece of on moni and can come ily after
```

17 words. Reproduces the README's 37-token result exactly.

### Arm B — int8, same weights, sherpa-onnx

```
python I:/Temp/sotto-acc/measure.py --label int8 --out-dir I:\Temp\sotto-acc\ev -- ^
  python I:/Temp/sotto-acc/sherpa_arm.py --arm int8 --audio H:\sotto\worker\assets\sample1.flac
```

* **rc** = 0
* **wall** = 34.55 s (external) · load 12.125 s · infer 18.257 s · **RTF 1.334**
* **peak RSS** = 792.6 MB (external, CPU, 8 threads)
* **words** = 39 · feed 10 640 samples (665 ms) per decode call, 21 calls
* **transcript**:

```
Going along slashy country roads and speaking to damp audiences in droughty schoolrooms day after day for a fortnight, he'll have to put in an appearance at some place of worship on Sunday morning and he can come to
```

### Arm C — fp32, same weights, sherpa-onnx

```
python I:/Temp/sotto-acc/measure.py --label fp32 --out-dir I:\Temp\sotto-acc\ev -- ^
  python I:/Temp/sotto-acc/sherpa_arm.py --arm fp32 --audio H:\sotto\worker\assets\sample1.flac
```

* **rc** = 0
* **wall** = 39.21 s (external) · load 5.033 s · infer 31.700 s · **RTF 2.316**
* **peak RSS** = 2610.8 MB (external) / 2611.8 MB self-reported on a repeat run
  (external 2620.3 MB — the two instruments agree to 0.3 %)
* **words** = 39
* **transcript**: **byte-identical to arm B**.
* Reproducibility: a second FP32 run reproduced the same 39-word string.

### Second clip — `sample2.flac` (14.215 s)

| arm | rc | wall (s) | peak RSS (MB) | transcript |
|---|---|---|---|---|
| A int4 | 0 | 7.799 | 2130.0 | `befor aed burst  question can se her sksty of denco` (24 tokens, 10 words) |
| B int8 | 0 | 17.514 | 792.8 | `Before he had time to answer a much encumbered Vera burst into the room with the question, I say can I leave these here these were a small black pig and a lusty specimen of black` |
| C fp32 | 0 | 29.309 | 2610.6 | `Before he had time to answer a much encumbered Vera burst into the room with the question I say, can I leave these here?  These were a small black pig and a lusty specimen of black` |

Same shape: the int4 arm emits a *recognisable subset* of the sentence
(`befor`, `burst`, `question can se her` ≈ "…Vera burst into the room with the
question, I say can I leave…"), not a different sentence. It is dropping content,
not hallucinating.

### Agreement between arms

Token-level edit distance of the int4 transcript against the FP32 transcript of
the **same audio** (Levenshtein over normalised whitespace tokens; the FP32
transcript is a reference for this comparison and **not** a ground truth):

| clip | FP32 words | int4 words | edits | WER(int4 vs FP32) |
|---|---|---|---|---|
| sample1 | 39 | 17 | 33 | **0.846** |
| sample2 | 36 | 10 | 32 | **0.889** |

int8 vs fp32: identical on sample1; on sample2 they differ only in punctuation
and one comma placement.

---

## 3. Is this the quantisation, or the streaming 0.6 B model?

**Not the model, not the audio.** Both non-int4 arms are the *same 0.6 B
streaming checkpoint* on the *same 13.69 s / 14.2 s files*, and both produce
coherent English sentences. Nothing about the streaming architecture or the audio
explains a 0.85 WER.

**What the measurement cannot separate.** Arm A differs from arms B/C in three
things at once:

1. weight precision (INT4 vs INT8/FP32),
2. export generation (`onnx-community/…-onnx-int4`: genai's cache-aware
   streaming processor, `lang_id` input, per-chunk decode written in
   `sotto_worker.py`) vs `csukuangfj2/…` sherpa exports (`prompt_index`, sherpa's
   own fbank and greedy loop),
3. execution provider (CUDA vs CPU).

Only precision is the question; (2) and (3) are uncontrolled. No FP32 or INT8
export of the `onnx-community` generation exists on the Hub (searched 2026-10-06:
`onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` is the only repo in
that family, and `…-onnx` returns 404), so the missing cell of the 2×2 —
*worker's own driver, non-quantised weights* — could not be measured today.

**A probe that bears on it, and why it is inconclusive.** Pushing the *identical*
65-frame mel features (produced by onnxruntime-genai's own streaming processor)
through the int4 encoder and through the FP32 encoder of the same checkpoint:

```
control  FP32 vs FP32 (8 vs 4 threads) : cosine mean 1.000000  min 1.000000  (28 frames)
int4    vs FP32                          : cosine mean 0.327870  min -0.054003  p10 0.028089
encoded_lengths                          : int4 7 / fp32 7 on every chunk
encoder_output_rms                       : int4 [0.051, 0.081, 0.106, 0.081]
                                           fp32 [0.052, 0.034, 0.039, 0.047]
```

The control is exactly 1.0, so the instrument is sound and the 0.33 is real: the
two encoders are **not** the same function on the same input tensor. That is
consistent with genuine numeric damage from 4-bit weights — and equally
consistent with export-convention differences (feature scaling the two front ends
do not share, attention/right-context masking, `lang_id` vs `prompt_index`), which
this probe does not control. **Treat it as suggestive, not as the answer.**

---

## 4. The measurement that would settle it

One cell is missing and it is named:

> **Run `sotto_worker.py`'s own `StreamAsr.run_chunk` — the genai streaming
> processor and the hand-written greedy walk, unchanged — against a
> non-quantised copy of the *same export generation*: an FP32 or INT8
> `encoder/decoder/joint.onnx` in the `onnx-community` layout (with
> `genai_config.json`, `audio_processor_config.json`, `vocab.txt`).**

* If the transcript comes back clean → the 4-bit quantisation is the cause, and
  the fix is a precision change, not a decode change.
* If it stays garbled → the driver is the cause, and the decode loop is the thing
  to fix.
* Either result is actionable and neither can be obtained from today's arms.

Two cheaper substitutes for that cell, in order of cost:

1. **Replay the worker's loop against the sherpa FP32 graphs** (port the six
   input names; same tensors). Costs an afternoon, needs no new export. Clean text
   ⇒ driver bug; garbage ⇒ weights.
2. **Weight-level comparison, no decode at all.** Dequantise the int4 encoder's
   `MatMulNBits` initialisers back to FP32 and compare them tensor-by-tensor
   against the FP32 encoder weights of the same checkpoint (available locally at
   `I:/Temp/sotto-acc/models/fp32`). Caveat to expect: the two exports come from
   different toolchains, so the initialiser *names* will not line up 1:1 and a
   name-matching rule has to be written and justified first — a cosine computed
   over mis-paired tensors would be a fabricated number, which is worse than no
   number.

Until one of those lands, the correct statement for the README is: *the int4
export is where the loss is; it is not yet proven whether the loss is the 4-bit
weights or the int4 export's driver.*

---

## 5. What was NOT measured

* **FP16.** The local `worker/models/nemotron-3.5-asr-streaming-0.6b-fp16`
  (soniqo, rev `76daabfd…`, 1.29 GB of FP16 weights) was **not run**, and no FP16
  number appears anywhere in this document. It is a *different export
  generation*: encoder takes `audio_signal [1,128,32]` + `language_mask [1,128]`
  + `pre_cache [1,128,9]`, the decoder is per-token (`token [1,1]`), and the
  directory has no `genai_config.json`, no `audio_processor_config.json` and no
  `vocab.txt` — so neither `StreamAsr` nor `onnxruntime-genai`'s streaming
  processor can drive it, and its model card ships no reference Python decode
  (it points at an Android SDK). The brief allows substituting the next best
  available precision when FP16 cannot run; **FP32 of the same weights is
  strictly higher precision than FP16 and was run instead** (arms B and C).
* **The worker's own runtime at non-int4 precision.** Does not exist to measure
  (see §4).
* **Ground-truth WER.** No human transcript for `sample1.flac` / `sample2.flac`
  was obtained (the LibriSpeech reference for these CDN samples is not in the
  repo, and the web-search path was not available). Every WER here is
  **int4 vs the FP32 transcript of the same audio**, and is labelled as such.
* **The live capture path.** File arm only — no audio device, no tap, no bridge,
  no panel. Nothing here says anything about the tap.
* **Provider parity.** Arm A ran on CUDA (probe succeeded today); arms B and C
  were pinned `provider=cpu`. Wall time and peak RSS are therefore not
  apples-to-apples across arms; the int4 arm's 2131 MB includes a CUDA context.
  The *texts* are provider-independent as far as anything measured here.
* **Sample size.** Two read-speech clips from one CDN source, one run per arm
  (plus one FP32 repeat that reproduced the transcript exactly). No noise, no
  far-field, no other language, `use_vad=false` everywhere, no endpointing.
* **Feature-front-end parity.** sherpa's kaldi-style fbank and genai's streaming
  processor were never proven numerically identical. That gap is precisely what
  makes the §3 encoder-agreement probe inconclusive.
* **The `sherpa_arm.py` in-process `peak_rss_mb` field read 0.0** in the runs
  cited above (a hand-rolled ctypes `GetProcessMemoryInfo` call that fails
  silently on this host). Fixed to psutil afterwards and re-verified
  (2611.8 MB in-process vs 2620.3 MB external). All RSS figures quoted in this
  document come from the external instrument.

---

## 6. Provenance

**Audio** — `worker/assets/sample1.flac`, 16 kHz mono, 13.690 s,
sha256 `cb5c48a2d1d6f7dedd0330f088a4cbe76de1a86e6a6109c06d255bb1ca2f7542`.
Provenance per `worker/_probe/README.md`: `https://cdn-media.huggingface.co/speech_samples/sample1.flac`.

**Models**

| arm | repo | revision | files |
|---|---|---|---|
| int4 | `onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` | `8364d9e2dd9da23789b480bdbba9e423717e42ee` | local; `encoder.onnx.data` 690 089 984 B (sha256 prefix `2f27295855aeb99a`), `decoder.onnx.data` 59 785 216 B, `joint.onnx.data` 37 830 656 B |
| int8 | `csukuangfj2/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-int8-2026-06-11` | `ab43d895f5985b1bbab8b6eac8607fcdc05343f3` | `encoder.int8.onnx` 657 601 403 B, `decoder.int8.onnx` 14 978 075 B, `joiner.int8.onnx` 9 504 438 B, `tokens.txt` 131 440 B |
| fp32 | `csukuangfj2/sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-560ms-2026-06-11` | `2072aba9fb2d6ee6202b69e441761599ab7520b8` | `encoder.data` 2 454 405 120 B, `encoder.onnx` 42 247 484 B, `decoder.onnx` 59 764 944 B, `joiner.onnx` 37 824 291 B, `tokens.txt` 131 440 B |

Both sherpa cards state `base_model: nvidia/nemotron-3.5-asr-streaming-0.6b` —
the same checkpoint the int4 export came from.

**Scripts used** (outside the repo, so nothing in `worker/` changed except this
document):

```
I:/Temp/sotto-acc/fetch.py            # downloads arms B and C (snapshot_download)
I:/Temp/sotto-acc/sherpa_arm.py       # runs arm B or C through sherpa-onnx
I:/Temp/sotto-acc/measure.py          # external wall / rc / peak-RSS instrument
I:/Temp/sotto-acc/encoder_agree.py    # the §3 encoder probe (with its control)
I:/Temp/sotto-acc/wer.py              # token edit distance between two transcripts
I:/Temp/sotto-acc/ev/                 # every stdout/stderr of every run cited
```

**Host** — Windows 10.0.26200 x64, Python 3.11, onnxruntime 1.30.0,
onnxruntime-genai 0.17.1, sherpa-onnx 1.13.4, `TMPDIR=I:/Temp` for every run.

**Streaming cadence, measured (not assumed).** The sherpa encoder consumes
**65 mel frames per call** and `GetFrames` refuses less:

```
step  8960 samples (56 frames) -> "0 + 65 > 55"   rc=255
step 10400 samples (65 frames) -> "0 + 65 > 64"   rc=255
step 10640 samples             -> decodes, 21 calls for 13.69 s
```

65 frames per call is the same per-call frame count the int4 export consumes
(genai hands its encoder `(1, 65, 128)`), so all three arms decode at the same
frame granularity.

---

## 7. What this changes

`worker/README.md` should stop saying "NOT established" without a pointer, and
should stop implying the 0.6 B streaming model is the limit. The measured claim
that is safe to make today:

> On this host, the shipped int4 export returns ~0.85 WER against the same
> model's own FP32 transcript on both bundled clips, while INT8 and FP32 of the
> same checkpoint return fluent English. The loss is in the int4 path; whether it
> is the 4-bit weights or that export's driver is not yet separated.

---

## 8. SELF-AUDIT

**protocolos em falta.** The brief said "if FP16 is not present/downloadable,
compare int4 against whatever the second best available precision is". I read
that as "a different number on a comparable model", and shipped **FP32 and INT8
of the same checkpoint in a different runtime**. The protocol I did not have,
and should have asked for before spending the run, is the house rule that an
accuracy comparison must vary **one** variable. I substituted a controlled
*pair* (same weights, same audio, same frame granularity, two precisions, one
runtime) for the uncontrolled contrast the README asked about (int4 vs FP16,
necessarily two runtimes), because the controlled pair was obtainable and the
controlled contrast was not — but I should have declared that trade at the top
of the brief instead of discovering it mid-run, and the report still carries the
result of a choice nobody reviewed. Second omission: no ground-truth transcript,
so every WER in this document is against a model output rather than a human
reference; that should have been flagged as a deliverable risk, not discovered
at write-up.

**verificacao adicional.** I ran one and it changed the document: the
`FP32 vs FP32` control inside the encoder probe. Before it, "cosine 0.33" could
have been read as "int4 damage"; with it, the instrument is provably exact
(1.000000) and 0.33 is a real property of the pair — which is what forced §3 to
say "suggestive, not conclusive" instead of the cleaner claim I wanted to make.
The cheap check I did **not** run and would run next: the same probe with
sherpa's own fbank features instead of genai's, which would separate
"different front end" from "different weights" in one extra run.

**checkboxes novas.** For a precision arm to count as an arm: (a) a
**self-control** — the same model against itself under a changed-but-equivalent
setting, so the instrument's floor is measured before the comparison is quoted;
(b) a **declared cadence** — the per-call frame count proven by the error message
when a smaller feed is refused, not inferred from the model name; (c) an
**external memory instrument**, because a model grading its own RSS is a number
that can be wrong in the direction that flatters it (this run's
`peak_rss_mb: 0.0` was exactly that, and it went unnoticed until the doc was
being written).

**review por outro subagente.** sim — specifically, an independent re-run of the
three transcripts by someone who did not pick the arms, to test whether "byte
identical INT8 vs FP32" and "int4 is a subsample of the same sentence" are
facts about the models or artefacts of how the arms were wired. I accept being
put through it. Not done in this lane: it is a second session's work.

**gate-doubt:**

- **verde-de-verdade:** the int4 arm's `rc=0` and 37-token result are real — the
  same command reproduces the README's number, and the external instrument
  (2131.2 MB) agrees with the worker's self-report (2130.3 MB) to 0.04 %. The
  sherpa arms' `rc=0` is real but **their transcripts were produced by a
  runtime whose feature front end I never validated against genai's**; a fluent
  English sentence is strong evidence the wiring is right and is not proof of
  it. The `cosine 1.000000` control is the one green I trust completely,
  because a wrong instrument could not have produced it. The `peak_rss_mb: 0.0`
  in the sherpa evidence is the counter-example: those files say `rc: 0` and look
  clean while carrying a silently broken field.
- **falta-no-gate:** nothing checks that an accuracy arm used the same audio,
  the same checkpoint or the same frame granularity — a future change that
  re-points `worker/config.json`'s `model.dir` at a different export, or edits
  `genai_config.chunk_samples`, sails through every existing gate and silently
  changes what this document means. The scenario that breaks: someone upgrades
  the int4 export in place and the next "accuracy regression" reading compares
  two different models.
- **gate-melhor:** a mechanical check that every accuracy receipt names the
  audio sha256, the model repo + revision, and the per-call frame count for each
  arm, and refuses two arms whose `chunk_samples` differ —
  `python scripts/accuracy-arm-parity.py --receipt <md>`, RED when two arms
  declare different frame counts, or when an arm omits the sha256. Input that
  must leave it RED: this document with `65 frames per call` changed to
  `56 frames per call` in arm C's row, or arm B's sha256 deleted.

**confianca.** media-alta for the claim actually made (the int4 path is where
the words are lost — it survives a second clip and a repeated FP32 run); **baixa**
for anything finer-grained, in particular any statement about *which* part of
the int4 path is at fault. What would move it: the §4 cell-1 measurement, or the
sherpa-fbank variant of the encoder probe.

**nao verificado.**
* That the two arms share a frame cadence — asserted from the 65-frame refusal
  and genai's `(1, 65, 128)`, never measured side by side in one process.
* That sherpa's fbank matches genai's mel (blocks the §3 probe from concluding).
* That `prompt_index=0` in the sherpa export means the same thing as
  `lang_id=0` in the int4 export.
* Whether the sherpa arms' feed of 10 640 samples (rather than a 56-frame
  stride with re-fed lookahead) changes the transcript; the text is fluent, but
  fluent is not the same as cadence-correct.
* Any WER against a human transcript.
* Any behaviour with `use_vad=true`, a non-English prompt, or a live device.

---

## 9. CACHE/PRICE

Pasted verbatim from `bash I:/!manager/scripts/cache-task-report.sh SottoAccuracyInt4`
(rc=0, run 2026-10-06T05:31:44Z):

```
## CACHE/PRICE
- task/agent: SottoAccuracyInt4
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAccuracyInt4.jsonl
- cache: read=14054556 write=0 hit=98.0507% (cache-read / input+cache-read); universe: 89 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAccuracyInt4.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=89 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 89 of 89 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T05:11:52.701000+00:00 | break_items=2; WHEN=2026-10-06T05:17:03.065000+00:00 | break_items=2; WHEN=2026-10-06T05:27:15.039000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 110642 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAccuracyInt4']; window: 2026-10-06T05:11:52.701000+00:00..2026-10-06T05:27:15.039000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=41; turn_id=1791263512701 | session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=98; turn_id=1791263823065 | session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=176; turn_id=1791264435039 (state=RESOLVED-BREAKS-OMP; population: 3 of 110642 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAccuracyInt4']; window: 2026-10-06T05:11:52.701000+00:00..2026-10-06T05:27:15.039000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T05:31:44.587203+00:00
- usage rows: 89
- model + route: opencode-zen/space-bunny-free
- input tokens: 279415
- output tokens: 52227
- cache-read tokens: 14054556
- cache-write tokens: 0
- hit ratio: 98.0507% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=89 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 89 of 89 matched usage rows
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 3 of 110642 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAccuracyInt4']; window: 2026-10-06T05:11:52.701000+00:00..2026-10-06T05:27:15.039000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T05:11:52.701000+00:00; WHERE session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=41; turn_id=1791263512701
  - break_items=2; WHEN=2026-10-06T05:17:03.065000+00:00; WHERE session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=98; turn_id=1791263823065
  - break_items=2; WHEN=2026-10-06T05:27:15.039000+00:00; WHERE session_id=01a10f9e-2115-73ae-b77f-66386ca65a48 provider=space-bunny-free model=space-bunny-free item_index=176; turn_id=1791264435039
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

`gate-change-request: n/a — this receipt names no gate script; the only lint run
against it (`I:/!manager/scripts/self-audit-lint.sh`) is the check this block
feeds, and its one proposal is written above as prose rather than as a patch to
the manager's gate tree.`

**Cost of the work itself, not of the model runs:** 3.2 GB of model weights were
downloaded to `I:/Temp/sotto-acc/models/` for this measurement (INT8 0.68 GB +
FP32 2.59 GB) and are still there. They are reproducible from the revisions in
§6 and can be deleted with `rm -rf I:/Temp/sotto-acc`.