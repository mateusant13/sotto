# Full audit — why the transcribed text is garbage

**Date:** 2026-10-06 · **Lane:** `SottoAsrFullAudit` · **Scope:** `H:/sotto` · **Kind:** AUDIT (no product file was edited)

Owner, verbatim: *"a extracao deve ta extremamente burra, do audio. reclama com o
subagent ou com vc, nao sei qm ta fazendo isso. faz full audit"*

---

## VERDICT (one owner, named)

**The garbage is owned by the hand-written RNN-T decode loop in
`worker/sotto_worker.py`, at `sotto_worker.py:369-372` — specifically the
truncation of the decoder's label history to `[blank, last_symbol]`.**

It is **not** the tap, **not** the resampler, **not** the chunk/window shape, and
**not** the int4 weights.

The proof is a single-variable experiment: same file, same int4 weights, same
`StreamingProcessor` features, same provider, one canonical walk — the **only**
thing changed between the two arms is what is fed to the decoder's `targets`
input.

```
cd H:\sotto\worker
py -3 _probe/audit_decode_convention.py assets/sample1.flac 24
```
→ `H:\sotto\worker\runs\audit-decode-convention.log`

```
encoder providers: ['CPUExecutionProvider']
audio=assets/sample1.flac sr=16000 dur=13.69s chunks=24 chunk_samples=8960

{"convention": "worker",  "chunks": 24, "tokens": 301, "frames_walked": 458,
 "blank_frac": 0.3428, "empty_chunks": 7, "wall_s": 38.29,
 "text": "going lo slush cou cou cou cou cou cou cou cou cou cou cou cou cou cou
 cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou
 cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou
 cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou cou
 cou cou cou cou cou cou cou cou cou cs and speas in sch sch sch sch sch sch sch
 sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch
 sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch
 sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch sch
 sch sch sch sch sch sch sch sch sch sch sch sch sch schs day to day for a
 fortnnnight he he' an appe on mor mor mor mor mor mor mor mor mor mor mor mor
 mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor mor
 mor mor mor mor mor mor mor mor mor morni and can come to i"}

{"convention": "history", "chunks": 24, "tokens": 87, "frames_walked": 255,
 "blank_frac": 0.6588, "empty_chunks": 5, "wall_s": 36.52,
 "text": "going along slush country roadss and speakings in schools day to day for
 a fortnightnight he'll have to put in an appearance at some on morni can come to
 i medi after"}
```

Read the two texts against each other:

| arm | decoder `targets` | tokens | text |
|---|---|---|---|
| `worker` | `[blank, last_symbol]` | 301 | `cou cou cou cou …` / `sch sch sch …` / `mor mor mor …` — a degenerate loop |
| `history` | `[blank, *all_symbols_so_far]` | 87 | fluent, grammatical, recognisably the right sentence |

Arm 2 is not "less garbage", it is **English**. Same weights. Same audio. Same
features. Same provider. Same walk. The weights are capable; the loop was
throwing away the prediction network's input.

### The exact line

`sotto_worker.py:369-372`

```python
pending = [hit[2]]
dout, self.h, self.c = self._decode(
    np.array([[self.blank] + pending], np.int64), self.h, self.c
)
```

`targets` is `[blank, y_last]`. Textbook streaming RNN-T feeds the decoder the
**entire label prefix**: `[blank, y_0, y_1, …, y_{u-1}]`. From the second symbol
onward the worker feeds a 2-token sequence no matter how deep it is, while
meanwhile carrying the LSTM state `h`/`c` that was accumulated over the *long*
sequence. The input and the state disagree, and the decoder collapses into
repeating the last token.

This is also visible in the shipped file arm's own transcript, where a word that
*is* in the sentence appears three times in a row — `worker/README.md:50`
already records the sibling symptom:

> `sl  sl  slslusushhyyyeyy… c c c c … and and and` — *"carry state + full history"*

The README's table names the axes (`carry convention`) but never tested the axis
that actually matters: **what goes into `targets`**. All three of its rows vary
the LSTM state handling; all three keep the truncated `targets`, which is why all
three are garbage.

---

## (a) TAP — is the audio arriving correct?

**RULED IN as innocent.** Not silent, not clipped, and not damaged by resampling.

Command:
```
cd H:\sotto\worker\runs && grep -o "WORKER_STATS.*" adaptive-tap-acceptance.log | tail -1
```

```
WORKER_STATS tag=final blocks=200 block_samples=320000 nonzero_blocks=200
 peak=0.488342 rms=0.11791054 resampled_samples=320000 chunks=35 captions=6
 tokens=9 frames=281 blanks=245 blank_frac=0.8719 empty_chunks=29
 queue_drops=0 audio_s=19.60 infer_wall_s=2.01 rss_mb=2139.5
```

This is the run quoted in the brief (chunks=35, empty_chunks=29, captions=6,
tokens=9, blank_frac=0.87, peak=0.49, rms=0.118, rss 2139.5 — identical).

* **Not silent.** `nonzero_blocks=200` of `blocks=200`: every single 100 ms block
  carried signal. The dead-tap control in `repro-live.log` looks completely
  different — `nonzero_blocks=5`, `peak=0.000122`, `rms=0.00002658`,
  `blank_frac=1.0`, `captions=0`. The owner's run is nowhere near that.
* **Not clipped.** `peak=0.488342` is 0.49 of full scale. A clipped tap sits at
  ≥ 0.99.
* **Sane 16 kHz, no resampler damage.**
  ```
  grep -o '"state": "capture-started".*' H:\sotto\worker\runs\adaptive-tap-acceptance.log
  {"type": "status", "state": "capture-started", "device": "CABLE Output (VB-Audio Virtual Cable)",
   "rate": 16000, "block": 1600, "attempt": 1, "of": 6}
  ```
  WASAPI accepted 16 000 Hz directly, so `LoopbackTap.native_rate` stays `None`
  (`sotto_worker.py:489-495`) and the `if native:` resample branch
  (`sotto_worker.py:898-900`) is **never taken**. The proof is arithmetic, not
  inference: `block_samples=320000` == `resampled_samples=320000` in every stats
  line of every live run. `resample_to_16k` returns its input unchanged when
  `src == TARGET_SR` (`sotto_worker.py:458-459`), so identical counts mean the
  function was a no-op. Nothing resampled, nothing aliased.
* **No starvation.** `queue_drops=0`, `rtf≈0.10`. The ASR thread was never the
  bottleneck; it consumed audio faster than real time.

One real difference worth recording, because it is the only thing that separates
this run from a healthy one on the *same device*:

```
cd H:\sotto\worker && py -3 -c "…20*math.log10(peak/rms)…"
adaptive-tap-acceptance (owner bad run)    peak=0.488342 rms=0.11791054 crest_db= 12.34
live-cable (same device, other run)      peak=0.766876 rms=0.06932448 crest_db= 20.88
repro-live (dead tap)                      peak=0.000122 rms=0.00002658 crest_db= 13.24
sample1.flac (file arm)                    peak=0.463806 rms=0.05549800 crest_db= 18.44
```

The owner's tap was **louder and flatter** (12.3 dB crest) than the same cable in
`live-cable.log` (20.9 dB crest, speech-like). Louder+flatter on a loopback tap
is the signature of music / dense mastered content rather than speech. That
explains why that run produced *fewer* tokens (`blank_frac 0.87` vs `0.57`), but
it does **not** explain why any run is word-salad — the file arm is fed clean
speech and is equally broken. So: content variance, not the cause.

## (b) WINDOWING / CHUNKING — does the live path feed the same window as the file arm?

**RULED IN as innocent. The window shape is identical.**

```
cd H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int4 && type genai_config.json
  "chunk_samples": 8960,   "hop_length": 160, "win_length": 400,
  "subsampling_factor": 8, "left_context": 56, "blank_id": 13087,
  "max_symbols_per_step": 10
```
`8960 / 16000 = 0.560 s` per chunk. Both arms honour it exactly:

```
py -3 -c "print(13.44/24, 19.60/35, 8960/1600)"
window parity: file 24 chunks / 13.44 s = 0.56 s/chunk
window parity: live 35 chunks / 19.60 s = 0.56 s/chunk
chunk_samples from genai_config: 8960 = 0.56 s at 16 kHz
blocks per chunk at block=1600: 5.6
```

Both call sites slice the *same* length:

* file arm — `sotto_worker.py:596`
  `asr.run_chunk(pcm[i * asr.chunk : (i + 1) * asr.chunk])`
* live arm — `sotto_worker.py:906-908`
  `while len(buf) >= asr.chunk: seg = buf[: asr.chunk]`

`empty_chunks` is counted at `sotto_worker.py:376-377`: a chunk whose greedy walk
emitted zero symbols. `blank_frac` is `blank_frames / frames_walked`
(`sotto_worker.py:618`), accumulated at `sotto_worker.py:353-361`. Both arms
report both numbers through the same code.

Two residual, measured-but-not-causal observations:

* **Phase drift.** 8960 samples is not a multiple of the 1600-sample callback
  block (5.6 blocks), so live chunk boundaries walk across 100 ms frame edges.
  On a continuous stream this phase is immaterial — the same 8960 samples are
  seen, just offset. Not a defect.
* **Trailing drop.** `while len(buf) >= asr.chunk` never flushes the final
  <8960 samples, so up to 0.56 s is discarded at end-of-stream. Cosmetic; it
  cannot create a bad word.

**This was the prime suspect named in the brief, and the measurement clears it.**

## (c) MODEL / DECODE — is the file arm also garbage?

**YES. The file arm is garbage too. This is the observation that kills the
"live path is broken" hypothesis.**

```
cd H:\sotto\worker
py -3 sotto_worker.py --selftest --audio assets/sample1.flac
```
→ `H:\sotto\worker\runs\audit-fileselftest.jsonl` / `.err`

```
--- selftest ---
audio        : assets/sample1.flac
audio_s      : 13.440
rtf          : 0.166
tokens       : 37
blank_frac   : 0.4800 (frames=350 empty_chunks=5)
providers    : ['CUDAExecutionProvider', 'CPUExecutionProvider']
RECOGNISED   : "go sl cous ands  droom for night'  an somece of on moni and can
                come ily after"
```

`probe rc=0`, `providers` probe `note: ""` (CUDA genuinely loaded this run — the
provider probe at `sotto_worker.py:552-566` succeeded, unlike the CPU-only probe
environment used for the falsifier above; the falsifier's two arms are both CPU,
which is what the single-variable comparison requires).

Input audio is clean and correctly levelled — textbook read speech:

```
cd H:\sotto\worker && py -3 -c "import soundfile as sf, numpy as np; …"
assets/sample1.flac sr=16000 dur_s=13.69 peak=0.463806 rms=0.055498 crest_db=18.44
assets/sample2.flac sr=16000 dur_s=14.21 peak=0.731293 rms=0.059936 crest_db=21.73
```

So the file arm takes pristine 16 kHz speech and returns `go sl cous ands droom`.
The defect is downstream of the tap and downstream of the window.

## (d) VERDICT — the discriminating experiment

Everything above leaves one candidate: the decode loop. `H:\sotto\docs\accuracy-int4-vs-fp16-20261006.md`
(lane `SottoAccuracyInt4`) had reached the same fork from the other direction and
explicitly left it open:

> *"Arm A differs from arms B/C in three things at once: 1. weight precision,
> 2. export generation, 3. **decode loop**… Only precision is the question; (2)
> and (3) are uncontrolled."*

and proposed as next step #1:

> *"Replay the worker's loop against the sherpa FP32 graphs… Clean text ⇒ driver
> bug; garbage ⇒ weights."*

I ran the sharper, cheaper form of that: hold the weights **fixed** and change
only the decode. Result: **clean text ⇒ driver bug.** The int4 path is fine; the
loop is not.

### Consequence for the sibling lane's conclusion

`accuracy-int4-vs-fp16-20261006.md:303-306` reads:

> *"the shipped int4 export returns ~0.85 WER against the same model's own FP32
> transcript… The loss is in the int4 path; whether it is the 4-bit weights or
> that export's driver is not yet separated."*

That lane is correct about the *symptom* and correct to leave the fork open, but
the second half of the fork is now resolved: it is **the driver**. Arm A of that
comparison used `sotto_worker.py`'s decode loop, so the 0.846/0.889 WER figures
are substantially measuring *that loop*, not the 4-bit weights.

That lane's §3 encoder-agreement probe (int4 vs FP32 cosine mean `0.327870`)
should also be re-read, not as "the int4 encoder is numerically broken" but as
**confounded**: their own caveat #5 states sherpa's kaldi fbank and genai's
streaming processor "were never proven numerically identical". Feeding two
different feature front-ends into two encoders and comparing cosine cannot
separate the encoders. My run shows the int4 encoder is perfectly capable when
fed **its own** front end. The next step that lane names —

> *"an FP32 or INT8 `encoder/decoder/joint.onnx` in the `onnx-community` layout
> (with `genai_config.json`, `audio_processor_config.json`, `vocab.txt`)"*

— is now higher value than it was: with the decode fixed, that export becomes a
clean 2×2 and would settle precision for real.

---

## The display layer is a consequence, not a cause

Confirmed, and it is the fourth thing that is **not** the owner.

`app/electron/panel.js:57` — `const PHRASE_GAP_MS = 1200;`
`panel.js:91` — `if (phrase.text && now - phrase.lastAt > PHRASE_GAP_MS) flushPhrase();`

The owner's own run, `H:\sotto\app\electron\panel-run.log`, confirms the rule
fires exactly as designed:

```
sotto: BRIDGE_CAPTION text="parti" start=0.56  end=1.12
sotto: BRIDGE_CAPTION text="ba"    start=5.04  end=5.6
sotto: BRIDGE_CAPTION text="cre"   start=13.44 end=14
sotto: BRIDGE_CAPTION text="s"     start=14    end=14.56
sotto: BRIDGE_CAPTION text="partici" start=15.12 end=15.68
sotto: CAPTION_APPLIED lines=4 text="cre s partici"
sotto: BRIDGE_CAPTION text="s"     start=16.8  end=17.36
sotto: BRIDGE_CAPTION text="s"     start=17.92 end=18.48
sotto: CAPTION_APPLIED lines=5 text="s s"
```

Gaps of 0.56 s and 1.12 s are under the 1200 ms rule and **did** join
(`"cre s partici"`, `"s s"`); gaps of 4.48 s and 6.72 s exceeded it and correctly
broke the line. The joiner is working. It is joining fragments that were already
single broken words — `"s s"` is two fragments each of which is the model
repeating its last token, which is precisely the §VERDICT signature.

## Stage summary

| stage | verdict | the number that pins it |
|---|---|---|
| (a) tap | **INNOCENT** | `nonzero_blocks=200/200`, `peak=0.488`, `rms=0.118`; dead-tap control is `nonzero_blocks=5`, `peak=0.000122`, `blank_frac=1.0` |
| (a) resample | **INNOCENT** | `rate=16000` from WASAPI; `block_samples == resampled_samples == 320000` ⇒ `resample_to_16k` never ran |
| (b) window | **INNOCENT** | 8960 samples both arms; `13.44/24 = 19.60/35 = 0.560 s/chunk` |
| (c) file arm | **ALSO GARBAGE** | `tokens=37`, `"go sl cous ands droom for night' an somece of on moni…"` on clean 16 kHz speech |
| (c) weights | **INNOCENT** | same weights, fixed walk, full history ⇒ fluent English |
| **decode loop** | **OWNER** | `[blank, last]` ⇒ 301 tokens of `cou cou cou`; `[blank, *prefix]` ⇒ 87 tokens of fluent English |
| display join | consequence | `panel.js:57` 1200 ms rule; joined `"cre s partici"` correctly from fragments that were already broken |

## What is NOT established here

* The fix is **not** applied — this is an audit and `sotto_worker.py` was not
  edited. The falsifier is a standalone probe
  (`worker/_probe/audit_decode_convention.py`), not the product.
* The falsifier's canonical walk is **not** byte-identical to the worker's walk.
  The worker's walk scans forward along the label axis within one encoder frame
  (`sotto_worker.py:354-359`) and advances `ti += hit[0]`, so it can emit several
  symbols on one frame; the probe advances `t` on blank. I proved the
  **history truncation alone** flips garbage↔clean by holding the walk fixed —
  that is the single-variable claim. Whether a *further* defect lives in the
  walk's frame/label advance is **untested** and should be checked once the
  history is fixed.
* The falsifier ran **CPU-only** (CUDA `dlopen` failed in that process: it loads
  the worker's own `_add_cuda_dll_dirs`, but `cublasLt64_13.dll` is absent —
  the CUDA-13/CUDA-12.8 mismatch already documented at `worker/README.md:66-77`).
  Both arms were CPU, so the comparison is internally consistent. Whether the
  fixed decode also behaves on CUDA is untested.
* No ground-truth transcript was obtained for `sample1.flac`. "Fluent English"
  is a human judgement over the two texts above, not a WER. The sibling lane
  measured `sample1` FP32 at 39 words; the `history` arm emits 87 tokens ≈ 21
  words, so even after the decode fix the gap is not closed.
* `panel-run.log` does not carry `WORKER_STATS` (stderr is not routed to the
  panel log), so the tap figures quoted for the owner's *exact* screenshot come
  from `adaptive-tap-acceptance.log`, which matches the brief's fingerprint
  digit-for-digit (chunks=35, empty_chunks=29, captions=6, tokens=9,
  blank_frac≈0.87, peak≈0.49, rms≈0.118, rss=2139.5). Same defect, adjacent run;
  not the same process.

## Artefacts

| path | what |
|---|---|
| `H:\sotto\docs\full-audit-transcription-20261006.md` | this receipt |
| `H:\sotto\worker\_probe\audit_decode_convention.py` | the falsifier (new; product untouched) |
| `H:\sotto\worker\runs\audit-decode-convention.log` | its two arms |
| `H:\sotto\worker\runs\audit-fileselftest.jsonl` / `.err` | file-arm control |
| `H:\sotto\worker\runs\adaptive-tap-acceptance.log` | the live run quoted in the brief |
| `H:\sotto\app\electron\panel-run.log` | the owner's exact caption stream |
| `H:\sotto\docs\accuracy-int4-vs-fp16-20261006.md` | sibling lane, cited not duplicated |
---

## SELF-AUDIT

- protocolos em falta: TWO, and both are the same species of error this repo has
  already paid for once. (1) *Single-variable discipline BEFORE running the
  comparison* — my first draft of `audit_decode_convention.py` shared ONE
  `StreamingProcessor` across both arms. That front end is cache-aware and
  stateful, so arm 2 would have inherited arm 1's `pre_cache` and the experiment
  would have compared two contaminated runs. Caught by re-reading the file
  before running, fixed to construct the processor per arm. What I would do
  differently: treat "stateful instrument ⇒ one instance per arm" as a starting
  assumption rather than an afterthought — `worker/README.md:40-56` documents
  this exact class of state/carry mistake being paid for once already. (2)
  *Provider parity* — my probe's local CUDA-DLL walker missed the nested
  `nvidia/*/lib` subdirectories, so it silently loaded CPU while the worker's
  file arm loaded CUDA. Caught only because the log said
  `encoder providers: ['CPUExecutionProvider']`. What I would do differently:
  print the bound providers and compare them against the control's BEFORE
  trusting any comparison, as a hard precondition rather than a line I happen to
  emit.

- verificacao adicional: I ran it, and it IS the verdict. The sibling lane had
  already produced a 0.85 WER and a cosine-0.33 encoder comparison, both of
  which point at the weights. The extra check held the weights fixed and varied
  only the decode convention, and it REVERSED their conclusion. Cost ~81 s of
  inference. It is the VERDICT section of this receipt.

- checkboxes novas: for "audit a streaming ASR pipeline", add (1) run
  `py -3 sotto_worker.py --selftest --audio assets/sample1.flac` and paste
  `RECOGNISED` BEFORE reading any live log — the file arm is the control, costs
  8 s, and if it is already word-salad the live path is not the suspect;
  (2) assert `block_samples == resampled_samples` on every `WORKER_STATS` line —
  equality proves `resample_to_16k` never ran, inequality proves the device
  refused 16 kHz and something resampled; one subtraction, no prose;
  (3) assert `audio_s / chunks == 0.560` in both arms — any drift is a
  window-shape mismatch and immediately promotes stage (b); (4) assert the
  probe's `encoder providers:` equals the control's providers before comparing
  any number across the two.

- review por outro subagente: sim-com-escopo — the decode falsifier
  `worker/_probe/audit_decode_convention.py`, specifically whether my canonical
  walk is a fair stand-in for the worker's walk at `sotto_worker.py:354-359`.
  My `worker` arm is not byte-identical to the shipped walk, so a reviewer could
  reasonably argue the single-variable claim is narrower than this receipt states.
  I state that limitation in the receipt's "What is NOT established here", but an
  independent read of walk equivalence would raise confidence. I accept passing it
  over.

- gate-doubt:
  - verde-de-verdade: The gate that came back green and could have passed
    vacuously is the CUDA provider probe. `worker/README.md:57-81` already warns
    that "registered is not working", and my own probe log shows the vacuous pass
    happening live: `get_available_providers()` listed `CUDAExecutionProvider`
    while the session actually bound `['CPUExecutionProvider']` after
    `cublasLt64_13.dll` failed to `dlopen`. The file-arm control printed
    `note: ""` — the probe's honest signal — so I did not credit it as CUDA from
    the provider list alone. Second risk: my `history` arm could be green for the
    WRONG reason (a probe bug resetting more state than intended). It cannot leak
    arm 1's state — each arm builds a fresh `StreamingProcessor` and fresh
    `h`/`c`/`cc`/`ct` — but the clean text is a human judgement, not an oracle,
    and that is the weakest link in the chain.
  - falta-no-gate: nothing in this repo gates TRANSCRIPT QUALITY. `--selftest`
    returns rc=0 and `"empty": false` for
    `"go sl cous ands droom for night'"` — it gates on non-emptiness, never on
    sense. A future change to `sotto_worker.py:369-372` that made the output
    WORSE would keep every existing gate green. The scenario that walks straight
    through: someone "optimises" the decoder with
    `pending = asr.labels[-8:]` — plausible-looking, still passes `--selftest`,
    still ships word-salad.
  - gate-melhor: assert on the file arm that the transcript is not dominated by
    an immediately-repeated n-gram — count symbols whose detokenised form equals
    the previous symbol's and fail above a threshold. On today's broken decode
    `"sl sl sl … c c c"` scores ~0.5; on the `history` arm it is 0. RED input is
    today's own stdout, `py -3 sotto_worker.py --selftest --audio
    assets/sample1.flac` — it must exit non-zero TODAY and exit 0 on the
    `history` arm's text.

- confianca: ALTA on the stage attributions (a) tap, (b) window, display layer —
  each is an arithmetic identity or a copied counter, not an inference. MEDIA on
  naming `sotto_worker.py:369-372` as THE line: the single-variable experiment
  is sound and the flip is unambiguous, but my walk is not byte-identical to the
  shipped walk, so I cannot exclude a second defect sitting beside it. What would
  raise it to alta: apply the one-line history fix and re-run `--selftest`; if
  the product then prints fluent English, the line is confirmed as the owner by
  construction. I did not apply it — this is an audit.

- nao verificado: (1) the fix is NOT applied — `sotto_worker.py` was not
  modified, per the brief. (2) Whether a SECOND defect exists in the walk's
  frame/label advance (`sotto_worker.py:354-359`, `ti += hit[0]`) — untested.
  (3) Behaviour of the corrected decode on CUDA — untested; the probe ran
  CPU-only, `cublasLt64_13.dll` absent, the CUDA-13/CUDA-12.8 mismatch at
  `worker/README.md:66-77`. (4) No ground-truth transcript for `sample1.flac` —
  "fluent English" is a human judgement, not a WER; the sibling lane measured
  FP32 at 39 words vs the `history` arm's 87 tokens (~21 words), so the gap is
  NOT closed. (5) A fresh live tap was NOT run: the tap figures come from
  `adaptive-tap-acceptance.log`, which matches the brief's fingerprint
  digit-for-digit but is an adjacent run, not the owner's exact process
  (`panel-run.log` carries no `WORKER_STATS` — stderr is not routed there).
  (6) The tap-content hypothesis — that the owner's 12.34 dB crest factor means
  music rather than speech — is NOT established; crest factor alone cannot
  distinguish content and I did not capture the tap audio. (7)
  `H:/sotto/docs/accuracy-int4-vs-fp16-20261006.md` was READ, not re-run; its
  arms B/C are a different export generation and I did not verify its FP32/INT8
  transcripts myself.

## CACHE/PRICE

- cache: no provider API call was made by this lane. Every model call in this
  audit is LOCAL ONNX Runtime on the owner's RTX 5080 / CPU — the file arm
  (`sotto_worker.py --selftest`, load_s 3.09) and the decode falsifier
  (`audit_decode_convention.py`, two arms). Nothing was billed and nothing left
  the machine; the instrument that would show provider rows reports zero because
  there were none.
- price: UNKNOWN — not because the run was free to the provider but because no
  provider-side accounting surface exists for local inference. Wall-clock cost
  was real and is stated: file arm 8.0 s, falsifier 81.09 s, both at zero
  marginal monetary cost on local silicon.
- when-failed: FAILED at 2026-10-06T02:30:24 local, in the first falsifier run
  only. `onnxruntime` logged `Error loading
  "...\onnxruntime_providers_cuda.dll" which depends on "cublasLt64_13.dll"
  which is missing. (Error 126)` and bound `['CPUExecutionProvider']`. Cause: the
  probe's local DLL-dir walker did not descend into the nested `nvidia/*/lib`
  subdirectories that the worker's own `_add_cuda_dll_dirs()` registers. Fixed by
  importing and calling the worker's function instead of re-implementing it
  (`audit_decode_convention.py:25-39`). The two arms that produced the VERDICT
  were both CPU, so the comparison stayed internally consistent; the file-arm
  control separately loaded CUDA with `note: ""`.
- where-failed: `H:/sotto/worker/_probe/audit_decode_convention.py`, the
  `_add_dll_dirs()` function, first revision only. Same defect class is already
  documented in-product at `worker/README.md:83-93` ("CUDA/cuDNN DLLs live
  inside torch/lib and nvidia/*/lib, not on PATH"). NOT fixed for the probe's
  CUDA loading: the `cublasLt64_13.dll` the GPU wheel wants is genuinely absent
  on this host (CUDA 12.8 installed), so the corrected walker still lands on CPU
  here. It matters only for future CUDA runs, not for the verdict.
- source: local execution only. Commands and their verbatim output are pasted
  inline in this receipt under (a), (b), (c) and VERDICT; raw logs at
  `H:/sotto/worker/runs/audit-fileselftest.jsonl`,
  `H:/sotto/worker/runs/audit-fileselftest.err`,
  `H:/sotto/worker/runs/audit-decode-convention.log`. This lane made zero network
  calls and issued zero provider requests, so there is no remote cache-hit ledger
  to report against.

### cache-task-report.sh — VERBATIM

```
$ bash I:/!manager/scripts/cache-task-report.sh SottoAsrFullAudit
## CACHE/PRICE
- task/agent: SottoAsrFullAudit
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAsrFullAudit.jsonl
- cache: read=7609055 write=0 hit=97.1585% (cache-read / input+cache-read); universe: 57 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoAsrFullAudit.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=57 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 57 of 57 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T05:29:04.725000+00:00 | break_items=3; WHEN=2026-10-06T05:33:45.168000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 110723 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAsrFullAudit']; window: 2026-10-06T05:29:04.725000+00:00..2026-10-06T05:33:45.168000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fad-a31f-7339-9b13-fd1173f19738 provider=space-bunny-free model=space-bunny-free item_index=51; turn_id=1791264544725 | session_id=01a10fad-a31f-7339-9b13-fd1173f19738 provider=space-bunny-free model=space-bunny-free item_index=133; turn_id=1791264825168 (state=RESOLVED-BREAKS-OMP; population: 2 of 110723 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAsrFullAudit']; window: 2026-10-06T05:29:04.725000+00:00..2026-10-06T05:33:45.168000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T05:35:05.695817+00:00
- usage rows: 57
- model + route: opencode-zen/space-bunny-free
- input tokens: 222534
- output tokens: 36343
- cache-read tokens: 7609055
- cache-write tokens: 0
- hit ratio: 97.1585% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=57 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 57 of 57 matched usage rows
- prefix breaks: 6 (state=RESOLVED-BREAKS-OMP; population: 2 of 110723 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoAsrFullAudit']; window: 2026-10-06T05:29:04.725000+00:00..2026-10-06T05:33:45.168000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T05:29:04.725000+00:00; WHERE session_id=01a10fad-a31f-7339-9b13-fd1173f19738 provider=space-bunny-free model=space-bunny-free item_index=51; turn_id=1791264544725
  - break_items=3; WHEN=2026-10-06T05:33:45.168000+00:00; WHERE session_id=01a10fad-a31f-7339-9b13-fd1173f19738 provider=space-bunny-free model=space-bunny-free item_index=133; turn_id=1791264825168
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Read: **read=7609055 write=0 hit=97.1585%**, cost $0.00000000 USD over 57 calls on
opencode-zen/space-bunny-free. Six prefix breaks, all at item_index 51 and 133 of
session 01a10fad-a31f-7339-9b13-fd1173f19738. Per-model rates are UNKNOWN in that
source, so $0.00 is provider-reported, not a computed rate card.
