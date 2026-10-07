# Sotto vs. a YouTube reference — why our transcript skips words

**Lane:** `SottoVsReferencia` · **date:** 2026-10-06 · **verdict: the loss is in the DECODE, not the model and not the VAD.**

Owner, verbatim: *"baixa o video. veja a transcricao, normal. depois, simula a transcricao pela pipeline
que temos do sotto. compara. veja por que a nossa e tao ruim e pula varias palavras."*

---

## 0. TL;DR

| | |
|---|---|
| What was compared | the **same 25:08 audio** through (a) YouTube's caption and (b) the Sotto worker's **file / non-live** branch |
| Words | reference **4 303** · Sotto **2 183** → **50.7 %** |
| Omitted words | **2 159** (with 429 substitutions and 39 insertions) |
| Word error rate | **0.6105** (population 4 303 reference words, window 0 – 1 508.1 s) |
| Character error rate | **0.5768** (population 24 086 normalised characters, same window) |
| Chunks that produced **no text at all** | **1 597 of 2 692 = 59.3 %** (560 ms each) |
| VAD-gated chunks | **0 of 2 692** — the VAD never fired |
| Music-gated chunks | **0** — the gate is OFF in this branch |
| Exit code | **0** — the run is green while half the words are gone |

**The cause (one line):** `worker/sotto_worker.py:679-682` re-primes the RNN-T prediction network at
**every 560 ms chunk boundary** (`h`/`c` back to zero, first decoder call consumes only the blank). That is
a *decode* decision, and it is what drops the words. Same weights, same encoder features, same chunk grid,
same joint, same argmax — **only the predictor policy differs** (whole video, 2 692 chunks, CUDA, int8):

| arm | rule | tokens | words | % of ref | **omissions** | empty chunks | **WER** | **CER** |
|---|---|---|---|---|---|---|---|---|
| **1 = shipped** | `h`,`c` ← 0 each chunk; first decode eats `<blank>` | 5 661 | 2 183 | 50.7 % | **2 159** | **1 597 / 2 692 = 59.3 %** | **0.6105** | 0.5768 |
| 2 | `h`,`c` **carried** across chunks; first decode eats `<blank>` | 8 192 | 3 304 | 76.8 % | 1 286 | 622 / 2 692 = 23.1 % | 0.5954 | 0.3656 |
| **3** | `h`,`c` carried; first decode eats the **last emitted symbol** | **10 738** | **4 279** | **99.4 %** | **122** | **270 / 2 692 = 10.0 %** | **0.1536** | **0.0883** |

Arm 1 **reproduces the shipped run exactly** (5 661 tokens / 2 183 words / 1 597 empty / `blank_frac` 0.7689)
and its transcript is **byte-identical** to the shipped `sotto-full-text.txt` (11 591 chars, sha256
`449fe638bb019357…`) — the self-check that this harness measures the shipped decode and nothing else, so
every delta below is attributable to the predictor policy and to nothing else. Arm 3 cuts **WER
0.6105 → 0.1536** and **omissions 2 159 → 122** — a 17.7× reduction in dropped words, with no change of
weights, model, chunk size or frames. Arm 3's remaining WER is dominated by **substitutions (441)**, i.e.
disagreements between two ASR systems about spelling — not lost content.

120 s window (chunks 0-213) gives the same ordering 463 / 619 tokens; the instruments are
`_main/sotto-vs-ref-decode-arms.py` and `_main/sotto-vs-ref-compare.py`.

---

## 1. What was downloaded, and what the reference IS

```
TARGET: https://youtu.be/PQw0TRzpCkk     (25:08 — 1508.081 s container, 1508.066 s of samples)
DEST:   G:/sotto-ref/                    (I: is at 99.4 % — nothing was written to I: or C:)
```

`yt-dlp` was already installed (`C:\Program Files\Python311\Scripts\yt-dlp.exe`, 2026.08.19).

```bat
cd G:\sotto-ref
yt-dlp --no-playlist -f "bv*+ba/b" --no-write-auto-subs --no-write-subs -o "%(id)s.%(ext)s" https://youtu.be/PQw0TRzpCkk
::   -> PQw0TRzpCkk.webm   150 380 911 B  sha256:b92b7453191578bc…
ffmpeg -y -v error -i PQw0TRzpCkk.webm -vn -ac 1 -ar 16000 -c:a pcm_s16le PQw0TRzpCkk.16k-mono.wav
::   -> PQw0TRzpCkk.16k-mono.wav   48 258 202 B   1508.066 s / 16 kHz / mono / pcm_s16le
::      sha256:e49843327c02f444…
```

### 1.1 Provenance of the reference — read this before quoting any number

The video ships **several audio tracks** and the caption tracks are **per track**. `yt-dlp --list-formats`
shows format `251-20` tagged `[en-US] English (US) original (default)`, and the same list shows
`251-9 [pt-BR]`, `251-4 [fr-FR]`, … — YouTube's auto-dubbing. The default, and what
`-f "bv*+ba/b"` picked, is the **English original**.

| | |
|---|---|
| reference used | **YouTube caption, language `en`, 642 segments, 4 303 words** |
| **kind** | **AUTOMATIC (machine ASR), NOT a human transcript** |
| why `en` and not `pt` | the audio actually transcribed is the **English original** track. The `pt` caption (704 segments) also exists and is fluent, because YouTube **auto-translates** the `en` auto-caption — it is a translation of an ASR output, two machine steps away from the audio, and using it would have compared Sotto's English audio against Portuguese text |
| how obtained | the `youtube_transcript` tool (`langs="en,en-orig"`, `json=true`). `yt-dlp --write-auto-subs` was tried **three times** and failed every time on `HTTP Error 429` from the timedtext endpoint (`--extractor-args "youtube:player_client=web_safari,tv"` → "The page needs to be reloaded") |
| human track? | **none exists.** `yt-dlp --list-subs` lists an `Available automatic captions` block and **no** `Available subtitles` block |
| landed at | `G:/sotto-ref/reference-en.txt` (24 497 B, sha256:d90513bc2815c32d…) |

**Consequence for every number in this report:** this is an **ASR-vs-ASR** comparison. YouTube's caption has
its own errors ("GBT Nex", "Tibbo", "Enthropic", "Chad GBT", "Dakota" for *Decodable*). The WER/CER below is
therefore a **RELATIVE** figure — it measures disagreement between two ASR systems, **not** accuracy against
ground truth. The **ratio** and the **omission list** are the load-bearing evidence, and §4 shows that the
omissions are content words, not spelling disagreements.

Plausibility check on the reference itself: 4 303 words / 1 508.1 s = **2.85 words/s ≈ 171 wpm**, an ordinary
narration rate. Sotto's 2 183 words = **1.45 words/s ≈ 87 wpm** — far too low for continuous speech, which is
exactly the owner's complaint.

---

## 2. The Sotto run (non-live / "redux" route)

The worker's non-live branch is the **file arm**, reached by `--selftest --audio` or by
`SOTTO_AUDIO_FILE` — it drives the same `StreamAsr`, the same JSONL, the same model, with no audio device.
No app, no panel, no loopback.

```bat
cd H:\sotto\worker
python sotto_worker.py --selftest --audio "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" ^
    > "G:/sotto-ref/sotto-full-int8-vad-on.jsonl" 2> "G:/sotto-ref/sotto-full-int8-vad-on.err"
::  rc=0   wall 176.66 s
```

| field | value |
|---|---|
| `model` | `nemotron-3.5-asr-streaming-0.6b-int8` |
| `providers` | `['CUDAExecutionProvider', 'CPUExecutionProvider']` |
| `lang_id` / `lang` | `101` / `auto` (source `config:auto`) |
| `use_vad` | **true** |
| `gate` (speech/music) | **off** — file-arm default |
| `audio_s` | 1507.52 (of 1508.066 → see §5.2) |
| `tokens` | **5 661** |
| `frames` / `blanks` | 24 501 / 18 840 → `blank_frac` **0.7689** |
| `empty_chunks` | **1 597** of 2 692 |
| `vad_gated_chunks` | **0** |
| `music_gated_chunks` | **0** |
| `rtf` | 0.108 |
| `peak_rss_mb` | 2 498.2 |
| exit | **0** |

Full transcript: `G:/sotto-ref/sotto-full-text.txt`.

> **Note on the measured revision.** The working tree is **dirty** (`worker/sotto_worker.py`, `M`), and a
> sibling lane landed a device-routing change at 10:09:24 local. That diff (9 hunks) touches **only** the
> WASAPI ladder (`device_candidates`, `prefer_rendering_now`); none of `run_chunk`, `selftest`, `detok`,
> `max_sym` or the priming lines appear in it (`git diff -U0 | grep` for those symbols returns nothing), so
> the file-arm decode measured here is unaffected. Measured file: **2 685 lines, sha256
> `d4f4d5296dda87bf735b26d0f34c42f5ab8b9f45a56b22e440ed4401d43f5d4e`**. Line numbers below are that revision.

---

## 3. The numbers

Normalisation, applied **identically to both sides**: casefold, strip accents, `’`→`'`, drop all punctuation,
split on whitespace. Words per the reference population: 4 303; window 0 – 1 508.066 s.

| metric | value | population | window |
|---|---|---|---|
| reference words | 4 303 | 642 caption segments | 0 – 1508.1 s |
| Sotto words | 2 183 | 1 091 caption events / 5 661 tokens | 0 – 1507.5 s |
| **words captured** | **50.7 %** | 2 183 of 4 303 | whole video |
| matched | 1 715 | — | — |
| **substitutions** | **429** | 429 aligned pairs | whole video |
| **deletions = OMISSIONS** | **2 159** | of 4 303 reference words | whole video |
| insertions (extra) | 39 | of 2 183 Sotto words | whole video |
| **WER** | **0.6105** | 4 303 reference words | 0 – 1508.1 s |
| **CER** | **0.5768** | 24 086 normalised chars | 0 – 1508.1 s |
| Sotto token rate | 3.76 tokens/s | 5 661 tokens / 2 692 chunks | 0 – 1507.5 s |
| **empty chunks** | **1 597 / 2 692 = 59.3 %** | 560 ms each | 0 – 1507.5 s |
| Sotto words/s | 1.45 | — | — |
| reference words/s | 2.85 | — | — |

**WER and CER are ASR-vs-ASR** (see §1.1). The population and window are stated with each so the figure can
be re-derived; neither is a claim of absolute accuracy.

### 3.1 The first 30 omissions, with position

`pos` = index of the word in the normalised reference (0-based), so it can be re-found mechanically.
`t` = the audio time at which Sotto **resumes** after the gap — taken from the Sotto chunk the hypothesis
lands on, so it is **derived from the alignment**, not read off a clock on the reference. These are the
**first 30** of the 2 159 deletions, in reference order, exactly as the alignment emits them
(`compare.json → first_omissions`).

| # | pos | word | t (s) | # | pos | word | t (s) | # | pos | word | t (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 3 | no | 1.68 | 11 | 27 | for | 7.28 | 21 | 57 | new | 17.92 |
| 2 | 4 | uploads | 1.68 | 12 | 34 | some | 10.64 | 22 | 58 | model | 17.92 |
| 3 | 9 | of | 2.80 | 13 | 35 | several | 10.64 | 23 | 59 | that | 17.92 |
| 4 | 10 | days | 2.80 | 14 | 36 | new | 10.64 | 24 | 62 | is | 19.60 |
| 5 | 14 | in | 3.92 | 15 | 37 | updates | 10.64 | 25 | 63 | known | 19.60 |
| 6 | 15 | london | 3.92 | 16 | 41 | to | 12.32 | 26 | 64 | about | 19.60 |
| 7 | 20 | back | 5.60 | 17 | 42 | talk | 12.32 | 27 | 65 | and | 19.60 |
| 8 | 24 | the | 7.28 | 18 | 43 | about | 12.32 | 28 | 69 | gbt | 20.72 |
| 9 | 25 | craziest | 7.28 | 19 | 49 | biggest | 15.12 | 29 | 70 | nex | 20.72 |
| 10 | 26 | weekend | 7.28 | 20 | 50 | mystery | 15.12 | 30 | 74 | minor | 21.84 |

Reference for those first positions, verbatim:
*"Sorry for the **no uploads** for the last couple **of days**. I was out **in London** actually, but I'm
finally **back** and it wasn't **the craziest weekend for** AI news, but we still got **some several new
updates** that we need **to talk about**, especially from OpenAI cuz the **biggest mystery** right now from
OpenAI is a **new model that** not much **is known about** and it is called GBT Nex…"*

Sotto, same span, verbatim:
*"Sorry for the For the last couple I was out Actually, but But I'm finally And it wasn't AI But But we still
got That we need  Especially from Open A 'cause the Right now from Open AI  is a Not much  it is GPT …"*

**These are content words, in runs** — not spelling noise. And the pattern is the tell: Sotto lands ~3 words
per 560 ms chunk and then produces **nothing** for the next one or two.

### 3.2 A sample of the substitutions (429 total, first 20)

| ref pos | reference | Sotto |
|---|---|---|
| 29 | news | but |
| 68 | called | gpt |
| 79-82 | gbt 6 . 1 astra | gpt six point one |
| 98-99 | similar to | simi g |
| 132 | cuz | 'cause |
| 136 | lead | open |
| 140 | started | start |
| 154 | ship | imp |

Notice `simi`, `imp`, `Open A` — **cut tokens**: the chunk boundary lands mid-word and the tail is lost.
That is hypothesis 2 of the brief, and it is real but *small* (§5.2).

---

## 4. Why the four candidate hypotheses in the brief are NOT the cause

Each is answered with a number, not an argument.

### 4.1 "Does the VAD discard stretches between windows?" — **NO. Eliminated.**

The VAD is **on** (`worker/config.json` → `model.use_vad: true`, read at
`worker/sotto_worker.py:1755` and forwarded to the front end at **`sotto_worker.py:499-500`**,
`self.sp.set_option("use_vad", "1" if use_vad else "0")`; a gated chunk returns `None` and is handled at
**`sotto_worker.py:641-646`**).

**Measured: `vad_gated_chunks = 0` over 2 692 chunks.** The shipped Silero VAD (threshold 0.3 /
`silence_duration_ms` 3 360 / `prefix_padding_ms` 560) **never withheld a single chunk** on this audio. So
the VAD cannot be the source of 2 159 missing words. (The repo already knew this on other audio:
`docs/oss-approaches-20261006.md` §10 — the flip is a **no-op**, `vad_gated_chunks 0`.)

`tap_window` is a **live-branch** concept only: it is the rotation budget for a flat capture device
(`--tap-window`, `sotto_worker.py:1682`; resolved `sotto_worker.py:1949`; loop `sotto_worker.py:2276`). The
file arm never opens a device, so `tap_window` is unreachable here. **Eliminated by reachability.**

### 4.2 "Is the window cut mid-word and the cut side thrown away?" — **PARTLY, and it is NOT the cause.**

Two distinct effects, both real, neither of them the loss:

* **The tail chunk is dropped.** `selftest()` computes **`total_chunks = len(pcm) // asr.chunk`**
  (`sotto_worker.py:1585`). 24 129 062 samples // 8 960 = **2 692** chunks = 1 507.52 s; the remaining
  **8 742 samples = 0.546 s** are never fed. **0.546 s of 1 508.066 s = 0.036 %.** Not 2 159 words.
* **Mid-word cuts.** A chunk-final token that does not open a new word (no sentencepiece metaspace `▁`) is
  the signature, counted per chunk by `_main/sotto-vs-ref-probe.py` as `partial_tail_tokens`:
  **744 of the 1 095 non-empty chunks (68.0 %)** end on a mid-word token. That number looks alarming and
  mostly is not: for a subword model the boundary landing inside a word is **normal**, because the next
  chunk's first token continues it. The visible *loss* is only where the continuation never arrives — the
  fragments in §3.2 (`simi`, `imp`, `Open A`) — and the decisive evidence that the boundary is **not** the
  main loss is §5.1: arm 3 keeps **exactly this chunk grid and this boundary** and lands 4 279 of 4 303 words.
  A cause that survives an unchanged boundary cannot be the boundary.

### 4.3 "Is there a token/second limit per block that truncates?" — **NO. Eliminated.**

`sotto_worker.py:690`: `limit = self.max_sym * T + 16`, with `max_sym = 10`
(`genai_config.json: max_symbols_per_step`) and **`T = 7` for every chunk** — the encoder graph declares a
**static** output shape `outputs [1, 7, 1024]`, so `T` is 7 in all 2 692 chunks and the ceiling is **86
symbols per chunk**. Measured: **`symbols_over_limit_chunks = 0`**, and the per-chunk symbol histogram is
`0→1597, 1→38, 2→99, 3→161, 4→180, 5→181, 6→170, 7→103, 8→71, 9→43, 10→26, 11→15, 12→3, 13→1, 15→1,
23→1, 26→1, 83→1` — the largest chunk of the whole video emitted **83** symbols against a ceiling of 86, so
the guard never bound and no chunk was truncated by it. The walk also always consumed all 7 frames:
`frames = 7 + symbols` exactly (24 501 = 2 692 × 7 + 5 661 ✓) and `blanks = 2 692 × 7 = 18 844 ≈ 18 840`.
**The guard never fired.**

The histogram is also the shape of the defect: a spike at **0** (1 597 chunks) beside a broad mode at 3-6.
Half the audio produced a full burst and the other half produced **nothing at all** — which is what
"we land three words and then skip the next sentence" looks like as a number.

### 4.4 "Does the `_join`/merge of blocks lose the boundary?" — **NO. Eliminated.**

The transcript reported is **`asr.detok(asr.labels)`** (`sotto_worker.py:1547`, emitted as
`selftest-done.text`) — the **whole token list** joined once (`detok`, **`sotto_worker.py:548-555`**:
`"".join(parts).replace("\u2581", " ")`). Nothing is dropped there. `LineFormer`
(`sotto_worker.py:1446-1490`) shapes only the **live caption events**; it cannot lose a word the label list
already holds. (It *can* suppress a displayed line — `_close()` requires `text != self._shown` — but that is
a panel artefact, not a transcript one.)

---

## 5. THE CAUSE

### 5.1 The prediction network is re-primed at every chunk boundary

**`worker/sotto_worker.py:679-682`** (measured revision, 2 685 lines):

```python
        # The prediction network is RE-PRIMED at every chunk boundary: h/c start
        # at zero and the first decoder call consumes only the blank. …
        self.h = np.zeros((2, 1, self.hidden), np.float32)          # :679
        self.c = np.zeros((2, 1, self.hidden), np.float32)          # :680
        # Blank first: position 0 of the decoder output is "nothing emitted yet".
        dout, self.h, self.c = self._decode(np.array([[self.blank]], np.int64), self.h, self.c)   # :682
```

The encoder's acoustic history survives in the cache (`cache_last_channel` / `cache_last_time`, fed back each
chunk), but the **prediction network's textual state is destroyed 2 692 times** in this video — once per
560 ms.

**Instrument:** `_main/sotto-vs-ref-decode-arms.py`. It drives the **same** `StreamAsr` — same weights, same
front end, same 8 960-sample chunk grid, same joint, same argmax, same blank — and changes **only** where
`h`/`c` and the seed target come from. Arm 1 reproduces the shipped walk statement for statement.

**Numbers, WHOLE VIDEO** (2 692 chunks, 1 507.5 s, CUDA, int8, `lang_id=auto`, `use_vad=true`, gate off):

| arm | rule | tokens | words | % ref | omissions | empty chunks | blank_frac | WER | CER | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | shipped: `h`,`c` ← 0 each chunk; first decode eats `<blank>` | 5 661 | 2 183 | 50.7 % | 2 159 | **1 597 (59.3 %)** | 0.7689 | 0.6105 | 0.5768 | 114.1 s |
| 2 | `h`,`c` **carried**; first decode eats `<blank>` | 8 192 | 3 304 | 76.8 % | 1 286 | 622 (23.1 %) | 0.6970 | 0.5954 | 0.3656 | 111.2 s |
| **3** | `h`,`c` carried; first decode eats the **last emitted symbol** | **10 738** | **4 279** | **99.4 %** | **122** | **270 (10.0 %)** | **0.6370** | **0.1536** | **0.0883** | 186.9 s |

Arm 1 reproduces the shipped `--selftest` run to the token (5 661 / 2 183 / 1 597 / 0.7689) **and
byte-for-byte**: its `text` is identical to `G:/sotto-ref/sotto-full-text.txt` — 11 591 characters, sha256
`449fe638bb019357…` both sides (`python -c "…json.load(open('arms-full.json'))['arms'][0]['text']=='…'"` →
`IDENTICAL`). The harness measures the shipped decode and nothing else. Recovered by the change of policy
alone: **omissions 2 159 → 122 (17.7× fewer) and WER 0.6105 → 0.1536 (4.0× lower).**

Arm 1's first 120 s in this harness: *"Sorry for the For the last couple I was out Actually, but But I'm
finally And it wasn't AI But But we still got That we need  Especially from Open A 'cause the Right now from
Open"*.
Arm 3's, same audio: *"for the no uploads for the last couple days.  I was out in London actually, but I'm
finally back and it wasn't the craziest weekend for AI News but we still got some several ne upd…"* — the
reference is *"Sorry for the no uploads for the last couple of days. I was out in London actually, but I'm
finally back and it wasn't the craziest weekend for AI news, but we still got some several new updates…"*.
**The words are all there.**

**Honest caveat, named:** arm 2 alone is a *worse* transcript than arm 3 and not merely a cheaper one — it
glues tails (`backnst`, `weekendn`, `gotral`) and doubles a word (`from from`), which is why its WER
(0.5954) barely improves on the shipped arm's despite recovering 1 121 words. That is the defect the worker's
README measured on a 13.44 s clip and chose re-priming to avoid. The measurement here is that the avoid-cost
was **half the transcript**; and that **arm 3 removes the glue**: seeding the first decode of a chunk with
the last emitted symbol instead of the blank keeps the state consistent with the token that actually ended
the previous chunk. Arm 3's residue is 441 **substitutions** (spelling/variant disagreement between two ASR
systems), not 2 159 lost words.

### 5.1b Arm 3 — carry + seed (the corpus is where the fix is)

Arm 2 shows that carrying the state is worth 1 121 words, but it glues tails. Arm 3 asks why: if `h`/`c`
already hold the history, the first decode of a chunk must not be fed a `<blank>` the state has already
consumed — it must be fed **the symbol that actually ended the previous chunk**. One line changes:

```python
# arm 1 / 2 (shipped):            first = np.array([[self.blank]], np.int64)
# arm 3:                          first = np.array([[last_sym]],     np.int64)
```

Result over the whole video: **10 738 tokens / 4 279 words** against the reference's 4 303 (**99.4 %**),
**122 omissions** (vs 2 159), **270 empty chunks (10.0 %)** (vs 1 597), **WER 0.1536** (vs 0.6105),
**CER 0.0883** (vs 0.5768). The glue is gone with it: §5.1's arm-2 sample reads `backnst / weekendn /
gotral`, arm 3's reads `back and it wasn't the craziest weekend for`.

Arm 3 costs wall time — 186.9 s against arm 1's 114.1 s, RTF 0.124 vs 0.076 — because it emits **1.90×** the
tokens and the walk is one joint call per (frame, label) cell. That is the honest price of the fix, and it is
paid on a GPU that sits at RTF 0.076 idle; the live branch has 560 ms of real time per chunk to spend.

**What is NOT claimed:** arm 3 is a *diagnostic harness*, not a landed patch. It re-implements the walk in
`_main/sotto-vs-ref-decode-arms.py` to vary one policy at a time; the shipped `run_chunk` was not modified by
this lane (it is a shared hot file owned by several lanes — see §7's note on the dirty tree). Landing the fix
in `worker/sotto_worker.py` is the next action, and arm 3's exact rule is what to land.

### 5.2 The corroboration already sitting in the repo

`docs/oss-approaches-20261006.md:436`, written by another lane, states the symptom as a **premise** and never
tests it:

> *"The worker here emits one or two words per 560 ms hop with the decoder re-primed each chunk
> (`worker/sotto_worker.py:416-417`), so successive fragments are **disjoint word bursts**, not re-reads of a
> shared window."*

(That citation is to an older revision of the file — the priming it names now sits at `:679-682`, and the
read-back in §2 pins the revision this audit used.)

"One or two words per 560 ms hop" is **1.79 – 3.57 words/s**; the reference speaks **2.85 words/s**. So the
repo independently described the defect — and treated it as a constraint to design around (LocalAgreement-2)
rather than as a bug to fix. §5.1 is the measurement that was missing.

### 5.3 What the live branch adds on top (not measured here — named, not claimed)

The file arm is the **milder** arm. The live branch (`asr_thread`) adds two stages the file arm does not have:

* **`SpeechMusicGate`**, ON by default for live (`sotto_worker.py:1889-1894`, `gate_enabled = not _file_mode`),
  thresholds `GATE_DB_RANGE_MIN = 18.0` / `GATE_RMS_FLOOR = 0.004` / `GATE_HOLD_CHUNKS = 3`
  (`sotto_worker.py:1182-1184`). A chunk it rejects **never reaches the encoder** (`sotto_worker.py:620-626`)
  — on a video with a music bed or a narrow-dB-span speaker that is *more* chunks removed, each one a hole in
  the encoder cache.
* **`AutoGain`** applied per chunk before the decode (`sotto_worker.py:2003`, `:2158`), absent in the file arm.

Neither is in the numbers above; both are candidates for *further* loss in the owner's actual app and deserve
their own measurement. Stated as [INFERENCE]: not measured by this lane.

---

## 6. What the numbers rule out about the model

* `blank_frac = 0.7689` is **not** the discriminator. The worker's own README calls ~0.756 "real speech" on
  this model. A metric that reads "healthy" while half the words are gone is why this took a reference
  comparison to see.
* The model is not starved of frames, and this was **measured per chunk, not inferred**:
  `_main/sotto-vs-ref-probe.py` reports `T` and the front-end shape for all 2 692 chunks — **`T = 7` in
  every single one** (the unique set of observed `T` is `{7}`), and **`audio_features` is `[1, 65, 128]` in
  every one**. That is exactly the graph's declared `outputs [1, 7, 1024]` fed from
  `audio_signal [1, 65, 128]` = `pre_encode_cache_size 9` + 56 new mel frames (`subsampling_factor 8`,
  `hop_length 160`, 56 × 10 ms = 560 ms ✓). The front-end contract is right and the frame budget is complete.
* It is not the level: the video's WAV is `mean −26.3 dB / max −4.6 dB`, against the bundled
  `sample1.flac` at `mean −25.1 dB / max −6.7 dB`. Comparable — the file arm has no AGC and does not need one
  to reach the same operating point.

---

## 7. Exact commands to reproduce

```bat
:: 1. download + 16 kHz mono
mkdir G:\sotto-ref
cd /d G:\sotto-ref
yt-dlp --no-playlist -f "bv*+ba/b" --no-write-auto-subs --no-write-subs -o "%(id)s.%(ext)s" https://youtu.be/PQw0TRzpCkk
ffmpeg -y -v error -i PQw0TRzpCkk.webm -vn -ac 1 -ar 16000 -c:a pcm_s16le PQw0TRzpCkk.16k-mono.wav

:: 2. reference caption (tool: youtube_transcript, langs="en,en-orig", json=true)  -> reference-en.txt

:: 3. the shipped pipeline over the file arm (the "redux" route)
cd /d H:\sotto\worker
python sotto_worker.py --selftest --audio "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" ^
       > "G:/sotto-ref/sotto-full-int8-vad-on.jsonl" 2> "G:/sotto-ref/sotto-full-int8-vad-on.err"

:: 4. per-chunk instrument (shapes, T, symbols, empty chunks, mid-word tails)
cd /d H:\sotto
python _main/sotto-vs-ref-probe.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" "G:/sotto-ref/probe-int8-vad-on.jsonl"

:: 5. the decode arms — same weights/features/grid, only the predictor policy differs
python _main/sotto-vs-ref-decode-arms.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" "G:/sotto-ref/arms-full.json" --arms 1,2,3

:: 6. the numbers in section 3
python _main/sotto-vs-ref-compare.py --ref "G:/sotto-ref/reference-en.txt" ^
       --probe "G:/sotto-ref/probe-int8-vad-on.jsonl" --out "G:/sotto-ref/compare.json"
```

**Gotcha, measured and paid for:** two concurrent CUDA processes in this harness die at ~62 s with `rc=255`
and a stderr containing only `providers: ['CUDAExecutionProvider', …]` — no traceback. Run the probes
**serially**. And a probe that constructs `StreamAsr` directly must call `W._add_cuda_dll_dirs()` first, or it
falls back to CPU and compares a different token stream (arm 1 read 460 tokens on CPU vs 463 on CUDA).

## 8. Artifacts

| path | what |
|---|---|
| `G:/sotto-ref/PQw0TRzpCkk.webm` | the video (150 380 911 B) |
| `G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav` | 16 kHz mono PCM the worker consumes (48 258 202 B) |
| `G:/sotto-ref/reference-en.txt` | the reference transcript (YouTube auto caption, `en`) |
| `G:/sotto-ref/sotto-full-int8-vad-on.jsonl` | the shipped run, JSONL |
| `G:/sotto-ref/sotto-full-text.txt` | the shipped transcript as text |
| `G:/sotto-ref/probe-int8-vad-on.jsonl` | per-chunk instrument output |
| `G:/sotto-ref/arms-full.json` | the decode arms |
| `G:/sotto-ref/compare.json` | every derived number |
| `H:/sotto/_main/sotto-vs-ref-probe.py` | instrument 1 |
| `H:/sotto/_main/sotto-vs-ref-decode-arms.py` | instrument 2 |
| `H:/sotto/_main/sotto-vs-ref-compare.py` | the census |

---

## 9. The fix, and who owns landing it

**The change to land** is arm 3's rule, in `worker/sotto_worker.py` `run_chunk` — the two lines at **:679-680**
must stop zeroing `h`/`c` at every chunk, and the seed at **:682** must stop being the blank:

```python
# instead of  self.h = zeros(...); self.c = zeros(...); _decode([[blank]], h, c)
seed = np.array([[self._last_symbol if self._last_symbol is not None else self.blank]], np.int64)
dout, self.h, self.c = self._decode(seed, self.h, self.c)
```

with `self.h`/`self.c` initialised once per run (already done at **:503-504**) and `self._last_symbol`
updated where a symbol is emitted (`chunk_ids.append(y)`).

**Measured effect of exactly that rule, whole video:** WER **0.6105 → 0.1536**, omissions **2 159 → 122**,
words **2 183 → 4 279 (99.4 % of the reference)**. **Measured cost:** wall **114.1 s → 186.9 s** (RTF
0.076 → 0.124) on CUDA, and +5 077 tokens on the JSONL.

**This lane did NOT touch `worker/sotto_worker.py`.** That file is dirty and shared — a sibling lane landed a
device-routing change in it at 10:09:24 while this audit ran — and the honest next step is one lane owning
the decode change with these arms as its oracle, not two lanes editing the same hot function. The oracle is
already written and runnable:

```
python _main/sotto-vs-ref-decode-arms.py G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav /tmp/arms.json --arms 3
```

**Two more questions this audit did not answer, named rather than implied:**

1. **Does the same defect hit the bundled sample?** `sample1.flac` (13.44 s) is what the README's
   carry-vs-re-prime table was measured on, and it reported carry as *worse* there. Re-running the three arms
   on `worker/assets/sample1.flac` is cheap and would either reconcile the two results or show the clip is too
   short for the defect to appear (24 chunks; this video shows 1 597 empty chunks in 2 692).
2. **How much do the live branch's `SpeechMusicGate` and `AutoGain` add?** Both are OFF in the file arm
   (§5.3). The owner watches the live branch, so the number he actually experiences is at most this bad and
   plausibly worse. `SOTTO_GATE=1` in the file arm reproduces the live gate cheaply.

---

## 10. STATE CHANGE — the cure LANDED after this audit was written

**Dated forward note.** Everything above measures `worker/sotto_worker.py` at
**sha256 `d4f4d5296dda87bf735b26d0f34c42f5ab8b9f45a56b22e440ed4401d43f5d4e` (132 418 B)**, and those
numbers stand as measurements of that revision — §2 pins it, so they stay re-derivable. This section exists
because the forward-looking status line — §9's *"the fix is NOT landed"*, repeated in the not-verified list —
became **false** a few hours after it was written. A document that says "not landed" while the cure is in the
tree is the class this house refuses, so the correction is recorded rather than left standing.

- `worker/sotto_worker.py` is now **149 856 B, sha256
  `04a0aec6fe84ca8e0f709df56c19531448fbe0aff0709ee51bf7b40dd671cae2`**.
- The landed rule is **exactly arm 3** of `_main/sotto-vs-ref-decode-arms.py`:
  - `self._last_symbol = None` at **:512** and **:584**; `self._last_symbol = y` where a symbol is emitted, **:783**;
  - `seed = self.blank if self._last_symbol is None else self._last_symbol` at **:740**;
  - the comment block at **:716-731** names the defect and quotes **this audit's number** —
    *"re-prime per chunk -> 2 183 words (50.7 % of ref)"*.
- The shipped worker now reports, over the same 1 508 s file: **tokens 10 738 / empty_chunks 270 /
  vad_gated_chunks 0**, transcript **4 279 words** of the reference's 4 303 (**99.4 %**).
- That is **byte-identical to arm 3** (10 738 / 270 / 4 279, WER 0.1536), against the pre-cure shipped arm
  (5 661 / 1 597 / 2 183, WER 0.6105). **Arm 3 was a faithful oracle for the landed cure**, and the cause
  reported in §5 is confirmed by an independent lane landing it.
- Landed-run receipts: `G:/sotto-ref/sotto-full-cura.jsonl`, `G:/sotto-ref/ship-int8.jsonl`. The transcript
  now opens *"for the no uploads for the last couple days.  I was out in London actually, but I'm finally back
  and it wasn't the crazi…"* — the words §3.1 listed as missing.

**What this does NOT change.** §5.3 still holds: the live route's `SpeechMusicGate` and `AutoGain` remain
unmeasured, so *"a legenda AO VIVO continua HORRIVEL"* cannot be called closed by this landing alone.
Registry row `DONO-20261006-caption-quality` is therefore only **partly** answered by this work — the
file/redux route is fixed and measured; the live-arm residual is still an open measurement.

## 11. Attribution of my write-set (for lanes checking who touched what)

This lane's **complete** write-set, in every repo — nothing else was written by `SottoVsReferencia`:

| path | what |
|---|---|
| `H:/sotto/docs/audit/sotto-vs-referencia.md` | this audit |
| `H:/sotto/docs/audit/sotto-vs-referencia.RECEIPT.md` | the receipt (SELF_AUDIT_CLEAN) |
| `H:/sotto/_main/sotto-vs-ref-probe.py` | instrument 1 (per-chunk observation) |
| `H:/sotto/_main/sotto-vs-ref-decode-arms.py` | instrument 2 (the decode arms) |
| `H:/sotto/_main/sotto-vs-ref-compare.py` | instrument 3 (the census) |
| `G:/sotto-ref/*` | the downloaded video, its 16 kHz mono WAV, the reference transcript, run outputs |

**Nothing under `H:/sotto/app/` was opened or written by this lane.** In particular
`H:/sotto/app/electron/panel.js` — flagged as a post-close diff (78 insertions / 20 deletions / 23 692 B /
sha256 `e374a37e…`) by theory pass `2026-10-06T15-50Z` F6 — carries **no** contribution from this work, so
that diff should be attributed by the lane that owns `app/electron`, not to the #943 reconciliation.
