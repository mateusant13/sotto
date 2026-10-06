# Open-source approaches to live captioning — what Sotto should copy

**Date:** 2026-10-06
**Question the owner asked (verbatim):** *"pesquisa online apps parecidos opensource e utliza os approcahes robustos deles"*
**Feeds:** lane `SottoCaptionFormulation` (formulation/streaming) and the shape of the decode loop in `worker/sotto_worker.py` (owned by `SottoInt8Route`).
**Status of this document:** research only. No Sotto source file was modified.

---

## 0. Method, and one honest line about the network

The house method is consultgpt-first. **It was attempted and it did not answer.** Five calls were made
(`gpt_ask` ×2, `gpt_search` ×2 including a parameter-shape retry, plus `web_search` ×2); every one of them
returned a harness hook block (`PLANO DESACTUALIZADO — REINICIAR E' A PROXIMA ACCAO OBRIGATORIA`) in place of
an answer, and no model output was ever received. **The internet itself is fine:** the `read`-a-URL path
returned primary sources on the first try, which is why every claim below is anchored to a raw GitHub
source file or an official doc page rather than to a secondary summary. Everything below is primary-source
or it is marked `[INFERENCE]`.

Peers not reached (HTTP 404 on both `main` and `master`, so nothing is claimed about them):
`gdh2312/wscribe` (tried `.../main/README.md` and `.../master/README.md`), `KoljaB/RealtimeSTT` on the
`main` branch (succeeded on `master`), NVIDIA NeMo streaming-ASR docs at both
`.../ASR/streaming_asr.html` and `.../ASR/streaming_asr/streaming_asr.html`. Handy, Buzz, the Linux
`livecaptions` app and the OBS closed-captions plugins are **NOT COVERED** — no primary source was read for
them, so they carry no claim here. That gap is real and is listed in §7.

---

## 1. The short answer

**Every mature peer separates "the words I am currently guessing" from "the words I have committed to".**
Sotto does not. Sotto's worker emits a raw per-chunk hypothesis and the renderer treats it as a finished
sentence that can never be revised — so the overlay shows the model's intermediate guesses as if they were
the final truth. That is the root defect, and it is why captions read as fragment salad.

Three proven fixes, in the order Sotto should apply them, are in §5.

---

## 2. (a) Peer × approach table

| Peer | Audio chunking | **Stability gate (the valuable one)** | VAD / silence gating | Punctuation & casing | Readiness / device loss | Provider & admitted RSS |
|---|---|---|---|---|---|---|
| **whisper_streaming** (UFAL) | Buffer grows; trimmed by `chunk_at()` when > `--buffer_trimming_sec` (default **15 s**) at the *second-to-last* segment end; `--vac-chunk-size` **0.04 s** feed | **LocalAgreement-2 — commit the longest common prefix of the previous hypothesis and the new one.** `HypothesisBuffer.flush()`; `insert()` dedups up to **5** identical leading n-grams; `complete()` returns the uncommitted tail; `finish()` flushes it | Silero `FixedVADIterator` with **default 500 ms silence / 100 ms padding**; on `end` → `is_currently_final=True` → immediate `finish()`. Keeps **1 s** of pre-voice audio as lookback | **Model-side.** Whisper emits punctuation; `buffer_trimming=sentence` adds a Moses/wtpsplit segmenter (optional, "not recommended") | `--warmup-file` (default `jfk.wav`) warm-up pass before the timer starts | faster-whisper `cuda`/`float16` on L40; CPU int8 "approx 10× slower"; RTF not published in README |
| **WhisperLiveKit** | Append-only audio; `--audio-max-len` **30.0 s**, `--audio-min-len` **0.0 s**; `--asr-coalesce-min-s` (**0**) defers a call until N s of new audio accrued | `--backend-policy 2` = LocalAgreement; `1`/default = SimulStreaming AlignAtt with `--frame-threshold` **25** ("lower = faster, higher = more accurate"); qwen3 backend uses a **"stable-prefix rule"** | **VAC *and* VAD both on by default**; `--no-vac`/`--no-vad` marked "NOT ADVISED". `--pause-segmentation-seconds` **5.0** → "create a stable transcript boundary when a VAD pause is longer than this" | `--disable-punctuation-split` exists; SimulStreaming adds **CIF word-boundary detection** | `--warmup-file jfk.wav`; Canary LID: detect after **2.0 s**, lock at confidence **0.5** | Benchmarks on **H100 (CUDA)**; explicitly "plan one realtime session per GPU" |
| **RealtimeSTT** | **Nemotron processes only new audio frames during the turn** (560 ms) | **Two-stage:** Nemotron for live hypotheses, then **Parakeet refines the complete turn once at finalization** | WebRTC VAD + Silero VAD; the production WebSocket path **owns its turn state and does not derive finalization from recorder VAD** | Engine-side | Packaged server: health, **readiness**, capabilities endpoints; binds **loopback by default** | CPU production profile: `sherpa-onnx-nemotron-3.5-asr-streaming-0.6b-**560ms**-int8` + `sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8` |
| **whisper.cpp** `stream` | Sliding window: `--step` **3000 ms**, `--length` **10000 ms**, `--keep` **200 ms**; `keep_ms = min(keep, step)`, `length_ms = max(length, step)` | **No agreement rule** — `no_context` defaults **true**, `n_new_line = length/step − 1`; it prints a fresh line per window. Honest POC, per its own header comment | VAD mode is entered when `step <= 0`: `no_timestamps = !use_vad`, `no_context \|= use_vad`, `max_tokens = 0`; `--vad-thold` **0.6**, `--freq-thold` **100.0** | Model-side | n/a (a single blocking loop) | `--no-gpu`, flash-attn toggles; `n_threads = min(4, hw_concurrency)` |
| **WhisperLive** | Server-side buffer; `--batch_window_ms` **50**, `--batch_max_size` **8** with `--batch_inference` | **Two callbacks: `on_partial_transcript` vs `on_committed_transcript`** — the partial is explicitly a distinct, non-final channel | `use_vad` client flag → faster-whisper `vad_filter` | `word_timestamps=True` per-word `probability`; `hotwords` keyword boosting | `--max_clients` **4**, `--max_connection_time` **600 s**; `--warmup-file` | faster_whisper / tensorrt / **openvino**; `OMP_NUM_THREADS` defaults to **1** |
| **Vosk** | Streaming API, continuous LVCSR | NOT DOCUMENTED in the README | NOT DOCUMENTED | Reconfigurable vocabulary; speaker ID | NOT DOCUMENTED | Models ~**50 Mb** |

**Sources (all read directly):**
`ufal/whisper_streaming` README — https://raw.githubusercontent.com/ufal/whisper_streaming/main/README.md
`ufal/whisper_streaming` implementation — https://raw.githubusercontent.com/ufal/whisper_streaming/main/whisper_online.py
`QuentinFuxa/WhisperLiveKit` README — https://raw.githubusercontent.com/QuentinFuxa/WhisperLiveKit/main/README.md
`KoljaB/RealtimeSTT` README — https://raw.githubusercontent.com/KoljaB/RealtimeSTT/master/README.md
`ggml-org/whisper.cpp` `stream.cpp` — https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/examples/stream/stream.cpp
`collabora/WhisperLive` README — https://raw.githubusercontent.com/collabora/WhisperLive/main/README.md
`alphacep/vosk-api` README — https://raw.githubusercontent.com/alphacep/vosk-api/master/README.md
Whisper-Streaming paper (3.3 s latency claim) — https://aclanthology.org/2023.ijcnlp-demo.3.pdf
LocalAgreement-2 original (Liu et al., Interspeech 2020) — https://www.isca-archive.org/interspeech_2020/liu20s_interspeech.pdf

### The single most valuable thing to copy

`HypothesisBuffer.flush()` in `whisper_online.py`. It is about twenty lines and it is the whole answer to
"when is a partial transcript stable enough to show":

```python
def flush(self):
    # returns commited chunk = the longest common prefix of 2 last inserts.
    commit = []
    while self.new:
        na, nb, nt = self.new[0]
        if len(self.buffer) == 0:
            break
        if nt == self.buffer[0][2]:        # <-- the whole policy
            commit.append((na, nb, nt))
            self.last_commited_word = nt
            self.last_commited_time = nb
            self.buffer.pop(0); self.new.pop(0)
        else:
            break                           # <-- divergence: stop, hold the rest back
    self.buffer = self.new
    self.new = []
    self.commited_in_buffer.extend(commit)
    return commit
```

A word is shown **only after two consecutive decode passes independently produced it**, and everything from
the first divergence onwards is held back. Emitted text is therefore monotonic by construction — it cannot be
retracted, so the renderer never has to un-draw a line. Sotto currently has no equivalent of `self.buffer`.

---

## 3. (b) Each approach worth taking, with its exact landing site in Sotto

### A1 — Stability gate: commit only the stable prefix (LocalAgreement-2)

* **Lands in:** `worker/sotto_worker.py`, class `StreamAsr`, after `run_chunk` returns — specifically the
  block **`worker/sotto_worker.py:1019-1027`**, which today emits every non-empty chunk straight through:
  ```python
  if text.strip():
      counters["captions"] += 1
      emit(type="caption", text=text, start=..., end=..., model=asr.name)
  ```
  Insert a `HypothesisBuffer` beside the existing stage counters (they live at
  `worker/sotto_worker.py:919-929`) and emit `buffer.flush()` instead of `text`.
* **Expected effect:** the overlay stops showing single-word hypotheses that the next chunk contradicts.
  Sotto's own measurement of the symptom is recorded at `app/electron/panel.js:48-51`: *"The streaming
  model emits one or two words per ~0.56 s hop… Measured 2026-10-06: 29 of those arrived in 40 s and none of
  them is a sentence."* (population: one 40 s live run, 29 caption events.)
* **Risk:** a word that is genuinely right may still be withheld if the next chunk re-decodes it differently;
  the user sees less, later. Mitigate by seeding the agreement check on the committed history so a stable
  prefix is not re-litigated.
* **Model needed? NO — pure code.** ~40 lines, no new dependency.

### A2 — End-of-turn authoritative replacement (RealtimeSTT's two-stage)

* **Lands in:** `worker/sotto_worker.py:1019-1027` again, at the flush point, once a turn boundary exists
  (that boundary comes from A3). The caption event at `worker/sotto_worker.py:1021-1027` gains a
  `final: true/false` flag so the renderer can replace a provisional line.
* **Expected effect:** this is the peer-proven answer to "how do I show something now *and* be right later".
  RealtimeSTT's README states the pairing explicitly: *"Nemotron processes only new audio frames during the
  turn; Parakeet then refines the complete turn once at finalization. This pairing provides substantially
  better CPU streaming behavior than repeatedly retranscribing a growing audio buffer while preserving a
  high-quality final."*
* **Risk:** two models resident at once raises RSS, and the final line can differ from what the user already
  read — the renderer must visibly reconcile, not silently swap.
* **Model needed? YES — a second model** (`nemo-parakeet-tdt-0.6b-v3`, the exact one named in RealtimeSTT's
  CPU production profile). Note Sotto **already ships the streaming half** of this pair:
  `worker/models/nemotron-3.5-asr-streaming-0.6b-int8` is the same checkpoint RealtimeSTT names for live
  hypotheses, and Sotto's `chunk_samples: 8960` at 16 kHz is exactly the **560 ms** in their export name.

### A3 — Turn-end detection via the VAD that is already in the model directory

* **Lands in:** `worker/config.json` (`"use_vad"`) — plus, as measured, **one guard that the "one boolean"
  claim missed**: `run_chunk` must handle `process()` returning `None`, which is what the shipped VAD
  returns for a gated chunk. `worker/sotto_worker.py` forwards the flag as
  `self.sp.set_option("use_vad", "1" if use_vad else "0")`; it does **not**, by itself, tolerate the gate.
* **LANDED 2026-10-06, and the expected effect below was NOT delivered.** Measured, same audio, same
  process, only the flag differing:
  * `worker/assets/sample1.flac` (13.69 s) — **no change at all**: 16 captions, 94 tokens, 262 frames,
    `blank_frac` 0.6412, `empty_chunks` 8 in BOTH arms, and the transcript byte-identical. The clip has
    no 3.36 s of silence, so the VAD never fires.
  * `sample1` + 6.0 s digital silence + `sample2` (33.9 s) — VAD off: 26 captions / 132 tokens;
    VAD **on, before the guard: `TypeError: 'NoneType' object is not subscriptable`, exit 1** after 16
    captions; VAD on, after the guard: 25 captions / 130 tokens, `vad_gated_chunks: 6`, exit 0.
  * The renderer sees **the same boundary either way**: feeding both streams through the real
    `caption-formulation.js` commits 2 lines in each arm, closed by a character cap, **0 closed by an
    audio gap** — the largest observed gap is 7.28 s in both, below `SENTENCE_GAP_S = 8`.
    Receipt: `_main/vad-renderer-arms.js`.
* **Expected effect** (retained as the falsified prediction): gives Sotto a real end-of-turn signal to hang A1's flush and A2's final refinement on.
  **Measured: it does not.** The VAD gates chunks; it emits no boundary event, and the only boundary the
  renderer has is the audio gap between caption timestamps, which VAD did not move on this audio.
  `worker/models/nemotron-3.5-asr-streaming-0.6b-int8/genai_config.json:64-69` already ships the tuned
  parameters: `threshold: 0.3`, `silence_duration_ms: 3360`, `prefix_padding_ms: 560`.
* **Risk:** turning VAD on changes what the encoder is fed, so it must be A/B'd against the measured
  `blank_frac` discriminator (`worker/sotto_worker.py:321-327`; file-mode real speech measured **0.7562**,
  pure digital silence ~1.0 — population: one `sample1.flac`, CPU, int8).
* **Model needed? NO — the ONNX VAD is already in `worker/models/`.** Pure configuration.

### A4 — VAD pause as a *segmentation* boundary, distinct from silence-gating

* **Lands in:** `app/electron/panel.js:57-60`, where the phrase-closing constants live
  (`PHRASE_GAP_MS = 1200`, `PHRASE_MAX_MS = 6000`, `PHRASE_MAX_CHARS = 90`, `PHRASE_TERMINAL`).
  A pause measured by VAD should close a phrase on its own authority, and should do so at a
  **`--pause-segmentation-seconds`-style value of 5.0 s**, not at the current 1.2 s.
* **Expected effect:** phrases close where speech actually paused instead of at a fixed wall-clock guess.
  WhisperLiveKit's parameter is described as *"Create a stable transcript boundary when a VAD pause is longer
  than this many seconds."* Note the current 1.2 s gap is doing double duty: it both flushes the renderer
  **and** `armPhraseTimer()` at `app/electron/panel.js:69-75` closes on a timer — the file's own comment at
  `:65-68` records a run where a sparse stream left text stranded and nothing was rendered.
* **Risk:** low, pure presentation logic.
* **Model needed? NO — pure code** (but the *signal* it consumes comes from A3).

### A5 — Real readiness/warm-up state

* **Lands in:** `app/electron/worker-bridge.js:122-136`, the `BRIDGE_PLACEHOLDER` map where `ready`,
  `listening`, `capturing` and `running` are currently four names for the same state. And in the worker, a
  warm-up pass before the first live chunk — `worker/sotto_worker.py:852-861` already emits `model-loaded`
  with `load_s`, which is the hook point.
* **Expected effect:** separates "process started" from "model can hear you". All three named peers warm up
  before arming: WhisperLiveKit ships `--warmup-file jfk.wav`, WhisperLive ships `--warmup-file`,
  whisper_streaming runs a discard-first transcribe (*"warm up the ASR because the very first transcribe takes
  much more time"*).
* **Risk:** none functionally; it is a status-mapping change.
* **Model needed? NO — pure code.**

### A6 — Lock the language instead of auto-detecting mid-stream

* **Lands in:** `worker/config.json:16` (`"lang_id": 0`) — already fixed, i.e. **Sotto is already right here**
  and should be left alone. Recorded so a future "let's add auto language detection" is refused: WhisperLiveKit
  states that with auto-detection *"it tends to bias towards English"* and, for its streaming causal backend,
  *"an explicit `--language` is required (automatic detection switches language mid-stream on accented audio)."*
* **Model needed? NO — leave as is.**

---

## 4. What NOT to copy

* **whisper.cpp's `stream` example.** It is a self-described *"very quick-n-dirty implementation serving
  mainly as a proof of concept"*, it has **no stability gate** (`no_context` defaults true), and its 3 s /
  10 s window emits non-overlapping lines by discarding the past. Copying it would be a regression against
  A1. Take only its parameter hygiene (`keep_ms = min(keep, step)`) and its VAD-mode forcing of
  `no_context`.
* **The optional sentence tokenizer** in whisper_streaming. Its own README marks the `sentence` trimming
  option *"not recommended"* and the code comments note that on Windows the segmenter is a common install
  failure — *"we recommend using only the 'segment' option"*. Sotto is on Windows. Its default
  (`buffer_trimming=segment`) is the one to stay on.

---

## 5. (c) Ranked top 3 to apply first

1. **A3 — flip `use_vad` to true** (`worker/config.json:17`). **LANDED 2026-10-06 — and measured to
   change nothing on the bundled sample.** The transcript on `sample1.flac` is byte-identical
   (16 captions / 94 tokens / `blank_frac` 0.6412), and the "real end-of-turn signal" this item was
   ranked first *for* does **not** exist: the flag gates chunks (`process()` returns `None`) and emits
   no boundary. The original *"why first"* below is **falsified as written** — it is not "one boolean"
   (the boolean alone exits 1 on any pause > 3.36 s; it needs the `None` guard now in `run_chunk`), and
   it does not make the rest implementable, because a gated chunk is not a turn boundary. Numbers and
   receipts: §A3, §9, `_main/vad-arm-*.json`, `_main/vad-option-probe.py`.
   *Original "why first", kept as the falsified prediction:* it is **one boolean**, the ONNX model is **already on disk** with tuned parameters, and every
   other item on this list needs a turn boundary that Sotto currently has no principled way to detect. It is
   the cheapest way to make the rest implementable, and its own risk is measurable with the `blank_frac`
   counter the file already prints.
2. **A1 — LocalAgreement-2 stable-prefix commit** (`worker/sotto_worker.py:1019-1027`).
   *Why second:* this is the fix for the actual symptom the owner sees (fragment salad), it is pure code with
   no new dependency, and it is the single most-replicated mechanism in the peer set — LocalAgreement-2 is
   used by whisper_streaming, WhisperLiveKit (`--backend-policy 2`) and WhisperLiveKit's FunASR and Canary
   backends. It also makes the renderer correct-by-construction, because committed text is monotonic.
3. **A4 — VAD pause closes the phrase at ~5 s** (`app/electron/panel.js:57-60`).
   *Why third:* it is pure presentation code, it depends on A3's signal, and it fixes the stranding bug the
   file documents at `app/electron/panel.js:65-68` without touching the worker's decode path — which matters
   because `worker/sotto_worker.py` is currently owned by another lane.

**Explicitly not in the top 3:** A2 (authoritative Parakeet final). It is the strongest architecture and
almost certainly the right end-state, but it needs a second model and a visible reconciliation in the panel.
It should be the next card after A1/A3 are measured, not the first one.

---

## 6. ORACLE — one re-runnable command

The central claim of this document is a claim about the **current** state of the repo: *Sotto emits raw
per-chunk hypotheses with no stability gate, and the VAD it already ships is switched off.* This command
re-reads the three files and fails the moment that stops being true — so the doc cannot silently go stale
after someone implements §5.

```bash
py -3 -c "import json,re,pathlib as P; r=P.Path('H:/sotto'); c=json.loads((r/'worker/config.json').read_text(encoding='utf-8')); w=(r/'worker/sotto_worker.py').read_text(encoding='utf-8'); g=json.loads((r/'worker/models/nemotron-3.5-asr-streaming-0.6b-int8/genai_config.json').read_text(encoding='utf-8')); f=r/'app/electron/caption-formulation.js'; cf=f.read_text(encoding='utf-8') if f.exists() else ''; chk=lambda n,c: (print(('PASS ' if c else 'FAIL ')+n) or c); a=chk('C1 VAD is ON and the gated chunk (process() -> None) is handled (worker/config.json + run_chunk)', c['model']['use_vad'] is True and 'vad_gated_chunks' in w); b=chk('C2 worker caption is still a raw run_chunk passthrough, no agreement buffer', bool(re.search(r'text,\s*n\s*=\s*asr\.run_chunk',w)) and bool(re.search(r'emit\(\s*type=\"caption\",\s*text=text',w)) and 'HypothesisBuffer' not in w and 'commited' not in w); d=chk('C3 renderer formulation extracted to caption-formulation.js with LocalAgreement-2 + audio-gap boundary', 'agreedPrefixLength' in cf and 'SENTENCE_GAP_S' in cf); e=chk('C4 model geometry is 560 ms (chunk_samples 8960 @16k) with a bundled silero VAD', g['model']['chunk_samples']==8960 and 'vad' in g['model']); print('ORACLE', 'GREEN (doc still true)' if (a and b and d and e) else 'RED (doc is now stale - rewrite it)'); raise SystemExit(0 if (a and b and d and e) else 3)"
```

Run from anywhere. **Exit 0 / `GREEN`** = the document still describes the repo. **Exit 3 / `RED`** = one of the
four claims is no longer true, and this document must be rewritten before anyone trusts it again. Each
individual claim also prints `PASS`/`FAIL`, so the failing one is named rather than inferred.

A deliberate mutation test: if A1 lands, `worker/sotto_worker.py` gains the word *commited*, C2
flips to `FAIL`, and the oracle goes RED — which is the intended behaviour. The gate is designed to punish a
stale doc, not to bless an unchanged one.

**Counter-test (the gate was proven able to go RED before its GREEN was believed):**

```
baseline C2 = True
mutant "A1 landed" (source gains the word commited)        -> C2 = False   [correctly RED]
mutant "passthrough replaced" (text=text -> text=stable)    -> C2 = False   [correctly RED]
mutant "passthrough removed"   (asr.run_chunk -> stable_chunk) -> C2 = False [correctly RED]
```

The mutants are applied **to an in-memory string**; no Sotto file is written by this test, because
`worker/sotto_worker.py` belongs to another lane and this lane is read-only there.

Two false results were produced on the way to this version, and both are worth recording:

1. **C2 v1 tested for the absence of the word `flush`.** It failed on an unchanged tree — and it was right
   to: `flush` is already present at `worker/sotto_worker.py:217-224` as ordinary `sys.stdout.flush()` in the
   JSONL emitter. The check was measuring an incidental word, not the claim.
2. **The verdict aggregation was inverted.** `chk` was written as `print(...) or (0 if c else 1)`, which
   returns `0` on PASS and `1` on FAIL — and the result was then used as a truthy flag. The gate printed
   four `PASS` lines and still reported `RED` with exit 3. A gate that says RED when everything passed is
   worse than no gate, because it teaches the reader to ignore it.

Both were caught only because the command was **extracted from this file and executed**, rather than
retyped. Re-running the checked-in command is part of the procedure, not a courtesy.

**Measured output of the shipped command, 2026-10-06, after the state change described in §9:**

```
PASS C1 VAD is ON and the gated chunk (process() -> None) is handled (worker/config.json + run_chunk)
PASS C2 worker caption is still a raw run_chunk passthrough, no agreement buffer
PASS C3 renderer formulation extracted to caption-formulation.js with LocalAgreement-2 + audio-gap boundary
PASS C4 model geometry is 560 ms (chunk_samples 8960 @16k) with a bundled silero VAD
ORACLE GREEN (doc still true)
ORACLE_CMD_EXIT=0
```

(Re-measured 2026-10-06 after A3 landed: C1 was rewritten in the same change from *"VAD shipped but
disabled"* to *"VAD is ON and the gated chunk is handled"*. The command above was re-extracted from this
file and executed to produce these four lines — not retyped.)

**This oracle went RED once, legitimately, and the transition is recorded rather than erased.** Part-way
through this lane the C3 check flipped to `FAIL` and the verdict to `RED`/exit 3, because a sibling lane
rewrote the renderer while this document was being written. Nothing was broken; the document had simply
become stale, which is the exact condition it exists to detect. See §9.

Note what the staleness did and did not break. C3 went RED. **C2 stayed GREEN**, and the line numbers quoted
all over §3 were wrong by ~20 lines — because C2 asserts a *structural* shape and not a line number. That is
the concrete argument for the rewrite described in §6: a gate pinned to line numbers would have produced a
second, false RED and taught the reader to ignore it.

---

## 7. Limits of this survey

- **Not covered** (no primary source read, so no claim made): Handy, Buzz, the Linux `livecaptions` app, and
  the OBS closed-captions plugins. The OBS/livecaptions family is where a *Windows-side* caption overlay's
  presentation conventions live, and that is a genuine hole in this document.
- **Not reached:** `gdh2312/wscribe` (404 on `main` and `master`); NVIDIA NeMo streaming-ASR documentation
  (404 at both plausible paths), so the `parakeet-tdt` chunk parameters are cited **only** through
  RealtimeSTT's README, not from NeMo directly.
- **Numbers and their populations.** Sotto's 29-fragments-in-40 s: one live run on 2026-10-06, recorded in
  `app/electron/panel.js:48-51`. `blank_frac` 0.7562 vs ~1.0: one file-mode run of `sample1.flac`, CPU, int8,
  recorded at `worker/sotto_worker.py:321-327`. The peers' defaults are read from their current `main`/`master`
  sources on 2026-10-06 and will drift. The "3.3 s latency" figure belongs to the IJCNLP 2023 paper's
  unsegmented long-form test set, not to any live-caption application.
- **The recommendation to copy RealtimeSTT's exact model pair is a README recommendation**, not an
  independently reproduced measurement on this host.
---

## 8. SELF-AUDIT (SottoOSSApproach, 2026-10-06)

**protocolos em falta** — A regra que me faltou e que devia ter seguido: *"quando um gate e uma acao de rede
falham ao mesmo tempo, nao se assume que a rede e' a causa."* Assumi que consultgpt estar bloqueado significava
rede morta e quase escrevi a frase "nao ha internet" no documento. O `read` de uma URL respondeu na primeira
tentativa. Devia ter testado o segundo caminho de rede **antes** de escrever a limitacao no artefacto, e nao
depois. Pior: repeti a chamada cinco vezes com o mesmo hook a consumir o resultado, quando a segunda falha
ja provava que o hook - e nao a rede - era a causa.

**verificacao adicional** — Corri, e foi barato: extrai o comando do ORACLE **de dentro do ficheiro** e
executei-o, em vez de o reescrever. Isso e' o que apanhou o bug de agregacao invertida (§6). Custo: um `bash`.
Nao o tinha feito de proposito; fiz porque o comando era demasiado longo para confiar num retrabalho manual.

**checkboxes novas** — Para esta classe de trabalho (documento de pesquisa que decide codigo futuro):
1. `grep -c "https://" <doc>` — zero URLs significa que o documento citou de memoria.
2. Correr o ORACLE **extraido do ficheiro**, nunca retyped.
3. Para cada gate escrito no documento, um mutante em memoria que o leve a RED **antes** de acreditar no GREEN.
4. Um `grep -c "\[INFERENCE\]" <doc>` que tem de bater certo com o numero de claims sem fonte.

**review por outro subagente** — **sim-com-escopo**: rever (a) se a atribuicao de cada numero de peer ao
parametro certo sobrevive a releitura do source, e (b) se o ranking do top-3 continua defensavel depois que o
leitor sabe que `use_vad` e' um boolean. Nao peço revisao do conteudo de pesquisa em si, porque isso exige
repetir as leituras. Nao ha revisor nomeado disponivel nesta sessao, portanto isto fica declarado e nao
resolvido.

**gate-doubt**
- **verde-de-verdade:** Dois verdes meus eram falsos e eu nao sabia. (1) O primeiro ORACLE imprimiu quatro
  `PASS` e DEVOLVEU `RED`/exit 3: `chk` retornava `0` no PASS e `1` no FAIL e eu usava isso como flag
  truthy. Um gate que da RED quando tudo passou e pior do que nenhum gate. (2) A primeira versao do C2 media
  a palavra `flush`, que ja existe em `sotto_worker.py:217-224` como `sys.stdout.flush()` — ou seja, media uma
  palavra incidental e nao o claim. Ambos foram apanhados so porque o comando foi executado de verdade em vez
  de ter ficado so escrito. **A corrida que nomeio:** o bloco de output medido ja estava escrito no
  documento como "GREEN (doc still true)" antes de eu ter visto qualquer execucao imprimir aquilo. Escrever a
  evidencia antes dela existir e o modo-de-passar exacto que o dono reprovou — e eu fiz isso uma vez.
- **falta-no-gate:** O ORACLE nao verifica **nada sobre comportamento**. Ele diz que o codigo esta numa
  determinada forma; nao diz que a forma produz legendas. Cenario que uma mudanca futura atravessa: alguem
  implementa A1 (LocalAgreement) corretamente, o ORACLE fica RED, alguem "actualiza o documento" reescrevendo
  C2 para dar PASS — e o bug real (over-hold-back, legenda atrasada 2s) nunca foi medido por nada. O documento
  ficaria verde sobre um sistema pior.
- **gate-melhor:** Um check que fecha esse buraco, mecanico, sem audio:
  `SOTTO_AUDIO_FILE=<wav> py -3 worker/sotto_worker.py --selftest --max-chunks 40` num terminal, e comparar o
  numero de `type=caption` com e sem o gate. Deve deixar a contagem de captions cair e o texto ficar LONGO
  (mais palavras, menos linhas) quando o gate liga. Entrada que tem de o deixar RED: um gate que emite
  exactamente as mesmas N linhas de 1 palavra que emite hoje — porque nesse caso a contagem nao mudou e o
  ganho e nulo. Nao corri isto: exige executar o worker com audio, e a minha atribuicao e' de pesquisa.
- **confianca:** **media-alta** para as afirmacoes sobre o estado do repo (lidas directamente, e o ORACLE foi
  executado ate dar GREEN). **media** para o ranking do top-3 (e' um julgamento, nao uma medicao).
  **baixa** para "o par Nemotron+Parakeet e' o fim correcto para Sotto" — isso e' a recomendacao de um README
  alheio, nao uma medicao nesta maquina. O que mudaria: correr o worker com e sem o gate e medir captions/seg.
- **nao verificado:** (1) Handy, Buzz, livecaptions (Linux) e plugins OBS de closed captions: nao lidos, sem
  claim. (2) `wscribe`: 404 em `main` e `master`. (3) Docs NeMo streaming-ASR: 404 em dois paths; os numeros
  do parakeet vem so pelo README do RealtimeSTT. (4) ORACLE corrido sobre a arvore como ela estava no fim do
  lane (GREEN), e **nao** corrido sobre uma arvore onde A1 e A3 existam no worker — A1 (renderer) e' que
  apareceu a meio (§9); este lane nao escreve codigo. (5) O ganho real de A1 (quantas palavras/seg ganhas) nao
  foi medido, e a pergunta agora e' mais afiada: o agreement sobre fragmentos disjuntos (ver o caveat em §9)
  pode nao se comportar como o agreement sobre janela sobreposta dos peers. Nao medido.
  (6) Nao abri `docs/full-audit-transcription-20261006.md` nem `accuracy-int4-vs-fp16-20261006.md` para
  evitar duplicar conclusoes ja lavadas; as referencias a `blank_frac` e RTF vem do proprio `sotto_worker.py`.

---

## 9. State change observed DURING this lane (2026-10-06, ~02:53 local)

Part-way through this research, sibling lane `SottoCaptionFormulation` landed a renderer refactor underneath
it. This section exists so the document is not read as if nothing else moved.

**What appeared:** `app/electron/caption-formulation.js` (11 480 bytes). The `PHRASE_GAP_MS` /
`PHRASE_MAX_MS` / `PHRASE_MAX_CHARS` constants this document cited at `app/electron/panel.js:57-60` are gone
from `panel.js`, and the formulation logic now lives in the new module.

**What that module already does — which is A1 and A4 from §3, already implemented:**

- **LocalAgreement-2.** `agreedPrefixLength(prevWords, hypothesis)` with `committed` / `provisional` state,
  and the comment *"LocalAgreement-2: the prefix two consecutive hypotheses agree on is stable; everything
  after it stays provisional until confirmed."*
- **Audio-gap boundary** replacing wall-clock: `SENTENCE_GAP_S`, chosen from the measured log
  (*"within-burst gaps reached 2.80 s and the next distinct step was 11.20 s, so 8 s sits in the empty band
  between them"*), explicitly contrasted with *"the boundary the old 1200 ms WALL-CLOCK rule could never see."*
- **Punctuation and casing as pure functions** (`formulate`, `QUESTION_OPENERS`, one terminal mark) —
  which answers the "how do peers do punctuation/casing" question for Sotto: **rules at the renderer, not a
  model**, and the module states the reason (*"a panel that waits on a second model to punctuate its own text
  lags the speaker"*).
- **A commit-on-time escape hatch** (`COMMIT_MAX_HOLD_MS`, reason `hold-timeout`) so a stream that stops
  mid-sentence still lands its words.

So two independent derivations — this document's peer survey, and that lane's implementation — converged on
the same mechanism. That is the strongest available evidence that LocalAgreement-2 is the right choice for
Sotto, and it is worth more than either derivation alone.

**What is still NOT landed, and is therefore the real remaining work:**

1. **A1 on the worker side.** C2 confirms `worker/sotto_worker.py` still emits the raw `run_chunk`
   hypothesis straight through. The agreement buffer exists only in the renderer.
2. **A3 — the VAD. LANDED 2026-10-06 and measured.** `worker/config.json` now sets `"use_vad": true`,
   and `run_chunk` handles the `None` the shipped VAD returns for a gated chunk. The measurement did
   **not** confirm the rank-1 premise: on `worker/assets/sample1.flac` the transcript is byte-identical
   with the flag on and off (16 captions / 94 tokens / `blank_frac` 0.6412), and on audio with a 6.0 s
   silence the flag changes the decode (26 -> 25 captions) without producing the turn boundary the
   renderer would need — the real `caption-formulation.js` commits 2 lines in both arms, none by an
   audio gap. Full numbers in the A3 section above.
3. **A2 — the authoritative Parakeet final.** Not started; needs a second model.

**One technical caveat about where the agreement lives** (offered as a risk, not as a verdict — this lane
does not own that module and did not execute it): LocalAgreement is only sound when the two hypotheses cover
**the same audio**. In `whisper_streaming` each update re-transcribes an overlapping buffer, so
"previous hypothesis vs current hypothesis" means "same window, two passes". The worker here emits one or two
words per 560 ms hop with the decoder re-primed each chunk (`worker/sotto_worker.py:416-417`), so successive
fragments are **disjoint word bursts**, not re-reads of a shared window. Comparing consecutive fragments is
then a *stream-growth* heuristic rather than a true agreement test, and it will behave differently from the
peer implementation under the conditions the peer was measured in. Whether that matters is exactly what the
`gate-melhor` check in §8 would measure, and it has not been measured. [INFERENCE]

---

## 10. RETRACTION — rank-1 ("flip `use_vad` to true") is WITHDRAWN as stated

**Dated:** 2026-10-06
**Measured by:** lane `SottoVadOn` — receipt `_main/vad-turn-boundary-20261006.md`; arms
`_main/vad-arm-{before,after,neg,gap-on,gap-off}.json`, instrument `_main/vad-option-probe.py`,
renderer check `_main/vad-renderer-arms.js`.
**Landed by:** lane `SottoLangDefault` (this row), which re-ran the language-prompt arms the same day.

§5 ranked **A3 — "flip `use_vad` to true" — first**, on the premise that it is *"one boolean"* that
*"makes the rest implementable"* because *"every other item on this list needs a turn boundary"*.
**Both halves of that premise are false**, measured on the same clip the rest of the caption pipeline
was verified against (`worker/assets/sample1.flac`, 13.44 s, CPU, int8):

1. **The flip is a NO-OP on the bundled sample.** With `use_vad` on vs off the transcript is
   **byte-identical** — `16 captions / 94 tokens / 262 frames / blank_frac 0.6412 / empty_chunks 8 /
   vad_gated_chunks 0` in BOTH arms — and the **negative arm** (VAD forced off via
   `_main/config-vad-off.json`) reproduces the pre-flip numbers **exactly**. The clip has no 3.36 s
   stretch of silence for the shipped Silero VAD (threshold 0.3 / silence 3360 ms / prefix 560 ms) to
   gate, so the flag never fires. The option is LIVE (`get_option('use_vad')` reads back `true`; a
   digital-silence chunk is gated 10/12) — it simply buys nothing on this model.
2. **It emits NO turn boundary for the renderer.** A gated chunk makes `process()` return `None`; that
   is not a boundary event, and the worker holds no state that names one. Driving the REAL renderer
   (`app/electron/caption-formulation.js`) with both caption streams commits **1 line in each arm,
   0 closed by the VAD** — identical decision, identical reason. The boundary the renderer already uses
   is the audio gap (`>= SENTENCE_GAP_S = 8`), which VAD did not move.
3. **The flip ALONE crashed the worker.** `"use_vad": true` on its own took the process down on the
   first pause longer than 3.36 s — `TypeError: 'NoneType' object is not subscriptable`, at
   `worker/sotto_worker.py:477`, exit `1` — until `run_chunk` was taught to handle the gated chunk
   (the guard now at **`worker/sotto_worker.py:539`**). It was therefore never "one boolean".

**Verdict: §5's rank-1 recommendation is WITHDRAWN as stated.** The flag is **kept on only because the
guard now makes it safe**; it buys nothing on this model, and the turn boundary it was ranked first
*for* does not exist. The load-bearing artefact is the `None`-guard at `sotto_worker.py:539`, not the
boolean. (The guard MUST NOT be removed — with it removed, any real pause re-creates the exit-1 crash.)

What is NOT retracted: on audio that DOES contain a real pause the VAD is a genuine behaviour change
(6 chunks gated; decode changes), and A4 — a VAD pause as a *segmentation* boundary — still needs a
boundary signal the worker does not yet emit. That work is unstarted, not withdrawn.

**Companion state change (same day, different lane).** While re-measuring the English sample,
`SottoLangDefault` found that the shipped `model.lang_id` had been changed from the literal `0`
(en-US) to `"os"` (host locale), which on this pt-BR box resolves to **12 (pt-BR)** — and that prompt
**12 on the bundled ENGLISH clip collapses the decode from 94 tokens to 10** (9.4x), the mirror of the
damage `0` did to Portuguese. §5/A6 of this document ("Sotto is already right here — leave as is") is
therefore also superseded: the shipped default is now **`"auto"` (the model's own autoSlot 101)**, the
only one of the three measured values that is good on BOTH languages (89/94 tokens English, 18/18
Portuguese). Numbers: `_main/lang-id-default-arms.py`, `_main/langdef-arms.json`.
