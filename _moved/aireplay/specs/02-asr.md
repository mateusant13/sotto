# SPEC 02 — THE ASR ENGINE: THE MEASURED EXPORT, THE THREAD KNEE, AND SILENCE SEGMENTATION

Owner's brief (2026-10-08, verbatim intent): *a better ShadowPlay — the transcript must be
searchable in the same panel as the clip; the heavy pass runs in the background when the machine is
not in a match.* This spec covers **only** the ASR engine that produces the transcript. It does not
cover capture, the ring, the index or the UI.

Status: **SPEC, and — unlike `specs/01` — every number below is MEASURED on this box.** Nothing in
this file is inherited from the brief; the brief's ASR claims were verified or discarded in
`docs/research/04-asr.md`, `05-onnx-asr.md`, `10-redux-2-threads.md` and `11-onnx-threads.md`.
Each constant carries its **provenance** as `path:line` (research doc, or the probe source line that
produced it). A constant without provenance is a bug in this spec.
Code: `src/asr/` (`python -m asr.transcribe --wav FILE [--json]`).

`MEASURED` = a command on this box produced it · `READ` = source read, line given · `UNKNOWN` =
nobody has shown it. Host: Windows 11 · i5-13600K (6 P + 8 E / 20 logical) · RTX 5080 · **CPU only**
(`CUDAExecutionProvider` is not loadable through ORT here, `AGENTS.md:230-234`).

---

## 0. THE DECISION IN ONE PARAGRAPH

**The engine is the `istupakov/parakeet-tdt-0.6b-v3-onnx` int8 ONNX export** (670.6 MB on disk,
5/5 sha256 verified), run on the **CPU** with **`intra_op_num_threads = 4`, `inter_op_num_threads =
1`**, over audio **cut on silence**, emitting **a compact 10 Hz level event on stdout** for the
panel's wave. It peaks at **~0.88 GB RSS at ~10 s segments with a flat 20-minute curve**, it is
**~4.4× lighter than the ternary Redux runner** (3.90–4.58 GB) and at the same 4-thread budget it is
**equal or faster** than it (8.74× vs 7.41×). Its text **is** the ternary's text (byte-identical on
EN, one hyphen on PT). **The background pass is this export, NOT the ternary** — the earlier "Redux
ternary for the background pass" line in `AGENTS.md:137` is superseded by
`docs/research/10-redux-2-threads.md`; the ternary keeps exactly one job, the **parity oracle**.

---

## 1. THE ARTEFACT — what is on disk, byte for byte

Directory: `models/parakeet-tdt-0.6b-v3-onnx/` (`AGENTS.md:162`). Revision
**`8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce`** — the revision the local HF cache names
(`.cache/huggingface/download/*.metadata`, line 1 of each).

| file | bytes | sha256 (first…last) | provenance |
|---|---|---|---|
| `encoder-model.int8.onnx` | **652 183 999** | `6139D2FA…5AFF09` | `docs/research/05-onnx-asr.md:22` |
| `decoder_joint-model.int8.onnx` | **18 202 004** | `EEA7483E…667A70` | `05-onnx-asr.md:22` |
| `nemo128.onnx` | **139 764** | `A9FDE148…019E9F` | `05-onnx-asr.md:23` |
| `vocab.txt` | **93 939** | blobId `fc43e1c7…` (git blob, no LFS) | `05-onnx-asr.md:24` |
| `config.json` | **97** | blobId `02a77300…` | `05-onnx-asr.md:24` |
| **total** | **670 619 803 B = 670.6 MB (639.5 MiB)** | the sum of the five rows above; see the note |

**Verification is a gate, not a note:** the three LFS blobs are checked against
`https://huggingface.co/api/models/istupakov/parakeet-tdt-0.6b-v3-onnx?blobs=true` and the two small
files against their **git blobId** (which is what the local `.cache` etag stores — `vocab.txt` has no
`lfs.sha256` because it is not LFS, `05-onnx-asr.md:24`). **5/5 MATCH** (`05-onnx-asr.md:25`).
**The fp32 sidecar `encoder-model.onnx.data` (2 435 420 160 B) is NOT on this disk and must not be
fetched** — it is 3.6× the int8 encoder and buys nothing for the product (`05-onnx-asr.md:25`).
**One correction owed to the doc:** `05-onnx-asr.md:25` prints the total as **670 589 803 B**, a
**30 000-byte arithmetic slip** (619 → 589). The sum of the five registered sizes is
**670 619 803 B**; both round to 670.6 MB, which is what `AGENTS.md:162` and the HF tree say. The
spec and `src/asr/constants.py` use the measured sum, and the model-free selftest checks it.

**Fichas of the loaded object** (`MEASURED` off the loaded model, `05-onnx-asr.md:40-43`):
`vocab_size 8193`, `blank_idx 8192`, `max_tokens_per_step 10`, `subsampling 8`, `features 128`,
`nemo-conformer-tdt` — a **TDT** (token-and-duration transducer), **not** the Nemotron RNNT: each
decode step emits a token **and** a duration jump. Quantisation is **dynamic** (`IR 8 / opset 17 /
5654 nodes / DynamicQuantizeLinear ×223 / MatMulInteger ×217 / ConvInteger ×77`,
`05-onnx-asr.md:31-32`) — activations are quantised at runtime, it is not a QDQ graph.
**The preprocessor is `NemoPreprocessorNumpy`** (`05-onnx-asr.md:41-43`): mel runs in NumPy on the CPU
provider, so `nemo128.onnx` is **verified but not loaded** — do not build a design that assumes it is.

**Contract of the runner:** `onnx-asr` 0.12.0, `quantization="int8"` (a **glob**,
`encoder-model?int8.onnx`, `05-onnx-asr.md:37-38`), `providers=["CPUExecutionProvider"]`, model dir
passed as a **local path** so `offline=True` and no HF call happens at load
(`resolver.py:69-72`, cited at `05-onnx-asr.md:26`). Licence **CC-BY-4.0** — attribution only, keep
the notice (`04-asr.md:23`, HF API `tags`).

---

## 2. THREADS — `intra_op = 4`, `inter_op = 1`, AND THE ORT DEFAULT IS FORBIDDEN

**`INTRA_OP_NUM_THREADS = 4` · `INTER_OP_NUM_THREADS = 1`** (`11-onnx-threads.md:53`).

Steady-state RTFx, mean of two passes (the second **reversed** as a drift control), same ≤120 s slice
of `plain-3600s.wav` [900, 1020), int8, CPU, `OMP/OPENBLAS/MKL = intra_op`
(`11-onnx-threads.md:20-25`):

| `intra_op` | RTFx fixed grid | RTFx silence-aligned | CPU % measured | RSS after load | peak `wset` |
|---|---|---|---|---|---|
| 1 | 2.82 | 3.28 | 100 / 106 % | 735.3 MB | 880.0 MB |
| 2 | 4.93 | 5.62 | 200 / 313 % | 738.7 MB | 882.7 MB |
| **4** | **7.29** | **8.74** | **400 / 669 %** | **738.8 MB** | **885.1 MB** |
| 6 | 7.34 | 7.23 | 600 / 736 % | 741.2 MB | 886.9 MB |

- **The knee is 4.** Marginal return per thread: **1→2 = 1.75× · 2→4 = 1.48–1.55× · 4→6 = 1.01×
  (fixed) / 0.83× (silence)** (`11-onnx-threads.md:29`). 6 threads buys nothing on the fixed grid and
  **loses 14–20 %** on the realistic silence-aligned chunking; the two *quietest* arms of the whole
  sweep were both 6-thread arms and **still lost to 4** (`11-onnx-threads.md:37-39`).
- **The extra speed is free:** RSS is the weights, not the threads — after load
  **734.9–741.6 MB across all 16 arms** (6.7 MB spread, monotone +6 MB from 1 to 6), peak `wset`
  **879.6–886.9 MB** fixed / **920.2–929.7 MB** silence (`11-onnx-threads.md:30-33`).
- **The pin is verifiable, and that is why it is a contract:** measured CPU% was **exactly N**
  (100 / 200 / 400 / 600 %) — no oversubscription (`11-onnx-threads.md:27`). The runner must be able
  to *prove* it used 4, and the oracle checks it.
- **ORT's default (`intra_op = 0`) is FORBIDDEN in the product:** it burns **690 %** of a core-set to
  deliver **3.11×** — one core's throughput for 6.9 cores — and pinning 2 threads is **1.95× faster**
  than it (`05-onnx-asr.md:88-90`). Any RTFx measured at default on this box is an artefact of that
  contention (`05-onnx-asr.md:89-90`).
- **REFINEMENT OF LAW 8 (recorded so it is not re-litigated):** "as few threads as possible" was the
  wrong lesson. The **≤2-thread budget belongs to our measurement lanes** (politeness on the owner's
  machine, `AGENTS.md:286-290`), **not to the product's engine, which wants 4** (`11-onnx-threads.md:53-57`).
  4 of 20 logical CPUs is far under the 7.3-core incident law 8 was written from.
- **`OMP/OPENBLAS/MKL/NUMEXPR = intra_op`** is set at process launch by the lane
  (`11-onnx-threads.md:15-16`) and is set by the runner before NumPy is imported, so the energy
  splitter cannot out-thread the budget. `OMP_NUM_THREADS` alone is **inert** for the *ternary*
  runner (kestrel overwrites it, `10-redux-2-threads.md:21-27`) — it is **not** inert here.
- **THE PIN BOUNDS ORT'S POOL, NOT THE PROCESS — measured on the product's own engine
  2026-10-08** (`_main/asr02-threadprobe.py`: the same 10 s chunk ×3 through
  `asr.engine.OnnxAsrEngine`, in-process 250 ms CPU poll, inference phase only). At
  `intra_op = 1` the process reads **99.9 % median / 106.2 % max** — exactly one core. At
  `intra_op = 4` it reads **507.1 % median / 781.2 % max**, i.e. **~5 cores, not 4**, while the
  throughput still scales as the knee predicts (RTFx **3.30 → 7.21 = 2.18×**, text identical).
  Lane 11's own instruments read 400 / 669 % (`11-onnx-threads.md:27`); the difference is the
  process's *other* users of the core (the NumPy mel preprocessor, and ORT's pool behaviour),
  **not a lost pin** — at 1 thread the pin is exact, which is what makes the 4-thread reading
  interpretable. **Consequence for law 8:** "4 threads" is the **ORT budget**; the AI Scheduler
  must budget **~5–8 cores** for the ASR process, not 4. The *configuration*
  (`intra = 4`, `inter = 1`) stays the contract, and it is what the oracle checks.

**UNKNOWN, named:** the knee on a genuinely quiet box (none was available; the box ran at 10–47 %
whole-machine CPU, so every absolute RTFx is **14–19 % below** the quiet-box lane's — the 2-thread
row 4.93 vs 6.06 is the cleanest cross-check, both `OMP=2`, `11-onnx-threads.md:41-43`); 8+ threads
(never run); the CUDA path (never run).

---

## 3. SEGMENTATION — BY SILENCE, NEVER ON A FIXED GRID

**A fixed 10 s grid cuts words in half and yields garbage at the seams. Silence-aligned cutting makes
the int8 export's text *be* the Redux text.**

- Fixed 10 s grid vs the reference: **ratio 0.229** (648 vs 741 chars), seams produce
  `The radio announce. that…`, `anunció que la bridge`, `TECA. Video announced`
  (`05-onnx-asr.md:105`). This is a **CHUNKING-POLICY effect, not a model effect**
  (`_main/probe-onnx-asr-split.py:6-12`).
- Silence-aligned on the same slice: **8/11 segments IDENTICAL** to the sibling's captions, 2 differ
  only in the final `ed` of `closed`, 1 is the probe's own cut at 1020 s (`05-onnx-asr.md:103`).
  On [900, 1080): **13/16 identical**, the rest differ **only** in that same `ed` (`05-onnx-asr.md:104`).
- **Control that makes it a measurement:** the split probe's `--mode fixed` reproduced the main
  probe's transcript **byte for byte** (648 chars), and both clips' text is **identical** at ORT's
  default threads and at 2 threads (`05-onnx-asr.md:108-110`).

**The splitter, exactly as measured** (`_main/probe-onnx-asr-split.py:45-85`) — ported verbatim into
`src/asr/segment.py`; every constant below is a named constant in `src/asr/constants.py`:

| constant | value | provenance |
|---|---|---|
| `FRAME_MS` | **20** (RMS frame) | `probe-onnx-asr-split.py:46` |
| `SILENCE_FLOOR_PERCENTILE` | **10** (the noise floor) | `probe-onnx-asr-split.py:50` |
| `SILENCE_THRESHOLD_MULT` | **4.0** | `probe-onnx-asr-split.py:51` |
| `SILENCE_ABS_FLOOR` | **0.005** | `probe-onnx-asr-split.py:51` |
| `MIN_SILENCE_S` | **0.30** (shorter runs are not cuts) | `probe-onnx-asr-split.py:45` |
| cut point | **midpoint of the silent run** | `probe-onnx-asr-split.py:62` |
| `MAX_SEGMENT_S` | **15.0** | `probe-onnx-asr-split.py:45` |
| `MIN_SEGMENT_S` | **0.6** (shorter segments are dropped) | `probe-onnx-asr-split.py:45` |
| oversize split | at the **quietest 20 ms frame** in `[min_seg, max_seg]` of the segment | `probe-onnx-asr-split.py:70-75` |
| `PAD_S` | **0.10** either side (this is why recorded segments overlap) | `probe-onnx-asr-split.py:77` |
| silence-only segments | **dropped** | `probe-onnx-asr-split.py:82` |
| `FIXED_GRID_S` | **10.0 — CONTROL ONLY, default OFF** | `probe-onnx-asr-split.py:88-95` |

- **The threshold is relative *and* absolute:** `thr = max(4 × p10(rms), 0.005)`. The relative term
  adapts to a noisy game mix; the absolute floor stops digital silence from being read as speech.
- **This is energy-only.** `onnx-asr`'s own Silero VAD is **not on disk** and was never exercised
  (`05-onnx-asr.md:119-120`); do not claim a VAD is in the path.
- **Segment length sets the peak RSS, not time on task:** **10 s → 0.88 GB · 30 s → 1.17 GB · one
  120 s pass → 1.77 GB** (`05-onnx-asr.md:67`). `MAX_SEGMENT_S = 15.0` therefore lives in the
  0.88–1.0 GB band, and the **15 s cap is what keeps the product inside it** — raising it is a
  memory decision, not a quality one.
- **On the registered slice the splitter produces 11 segments, median 6.98 s, max 13.82 s**
  (`_main/runs/threads11/silence-t4-p1.json`: `n_segments 11`, `seg_median_s 6.98`, `seg_max_s 13.82`).
  The splitter is deterministic and model-free, so this is a **byte-level regression target** that
  costs no inference to check.

---

## 4. MEMORY — THE NUMBER THAT DECIDED THE ENGINE

| what | peak | provenance |
|---|---|---|
| after load | **735–748 MB** (lanes 05 and 11 agree) | `05-onnx-asr.md:52`, `11-onnx-threads.md:30` |
| 120 s slice, 10 s segments | **873.7 MB** poll / **881.4 MB** `peak_wset` | `05-onnx-asr.md:54` |
| 120 s slice, silence-aligned | **909.1 / 923.1 MB** | `05-onnx-asr.md:56` |
| **20 min of audio, 10 s segments** | **874.6 / 882.0 MB — FLAT, no leak** | `05-onnx-asr.md:55` |
| curve over 20 min | 873.5 → 831.1 MB; **~43 MB handed back at ~13 min** | `05-onnx-asr.md:62-66` |
| ternary Redux, same job | **4.49–4.58 GB at 120 s slices** (3.90 GB was a short-clip figure) | `10-redux-2-threads.md:62-63` |

- **Budget rule for the product: quote the segment length with the number.** ~0.9 GB is the number
  for ~10 s segments; it is not a property of the model.
- **The comparison that closed the engine choice**, at the same thread budget on the same 120 s
  slice: int8 ONNX **6.06× at 0.87–0.92 GB** vs ternary **3.48–4.30× at 4.49–4.58 GB** —
  **~1.4–1.5× faster and ~4.9–5.2× lighter** (`10-redux-2-threads.md:71-79`). At 4 threads the ONNX
  export reaches 8.74× against the ternary's own 4-thread cap of 7.41× (`11-onnx-threads.md:240-242`).
- **Never run the ternary and the ONNX engine at once** for this job; the ternary is the oracle, and
  the oracle runs on demand, not in the product loop (`04-asr.md:99-102`).

---

## 5. WHERE THE COST IS — THE ENCODER, AND THE TDT LOOP IS NOT WORTH TOUCHING

`MEASURED` on a 10 s chunk, 2 threads (`05-onnx-asr.md:91-95`, `_main/probe-onnx-asr-phases.py`):
preprocess **0.006–0.011 s** · **encode 0.63–1.78 s** (126 encoder frames) · **decode 0.009–0.023 s**
(35–44 `decoder_joint` calls). **The encoder is ≥95 % of the time.** The ternary shows the same shape:
encoder 79.7–88.5 %, decode 3.3–11.0 % (`10-redux-2-threads.md:55-58`).

- **Consequence, and it is a rule:** optimisation belongs to the **encoder** (its quantisation, its
  provider, its frame batching) — **never to the TDT decode loop**. A better loop buys ≤5 %.
- **RE-DERIVED FROM THE PRODUCT'S OWN CODE — measured 2026-10-08** (`--phases`, which probes the
  first AND the last segment of the registered run; `_main/runs/asr02/repro-silence-t4.json`):
  **last segment (3.96 s): preprocess 0.0038 · encode 0.4530 · decode 0.0122 s → encoder share
  96.6 %** — the ≥95 % claim holds in steady state. **First segment (8.06 s): preprocess 0.1454 ·
  encode 1.2619 · decode 0.0170 s → encoder share 88.6 %**, because the first preprocessor call is
  **38× the steady one** (0.145 s vs 0.004 s). So the registered "encoder ≥95 %" is a
  **steady-state** figure and the first segment pays a cold-preprocessor warm-up; the TDT loop is
  **1.2–2.6 %** either way, which is why it is never the place to optimise.
- **The first call after load is NOT a law.** Lane 05 saw the first encode 2.5× faster
  (`05-onnx-asr.md:93-95`); lane 11 measured first-chunk ÷ steady RTFx across 16 arms as
  **0.41–2.63 — sign not stable, mechanism UNKNOWN** (`11-onnx-threads.md:46-49`). So **the runner
  reports steady-state RTFx (first segment excluded) as the product number** and the inclusive one
  only for comparison.
- **Load is 1.88–2.30 s warm / 1.96–4.13 s under contention at 4 threads** (`11-onnx-threads.md:24`,
  `05-onnx-asr.md:52`), and it is a per-process cost the AI Scheduler must own: a model load is not
  free and must not happen per clip if it can be amortised.

---

## 6. PARITY — THE TERNARY IS THE ORACLE, AND THE HARNESS SHIPS BOTH COLOURS

The product runner must reproduce the sibling's Redux transcripts. The reference texts are the
ternary's own outputs, read **read-only** from `H:\sotto`:

| arm | audio | oracle | measured verdict | provenance |
|---|---|---|---|---|
| **EN** | `_redux-long/src-en-8s.wav` (8.5 s) | `_main/redux-en.txt` (last line) | **EXACT — 130/130 chars, ratio 1.000000, 0 diff blocks** | `05-onnx-asr.md:101`; **reproduced by this spec's runner 2026-10-08** |
| **PT** | `_redux-long/src-pt-15s.wav` (15 s) | `_main/redux-ptbr.txt` (last line, **cp1252**) | registered: ratio 0.993711, one char `segunda-feira` → `segunda feira` — **but that arm was a ONE-SHOT 15 s pass. With SILENCE SEGMENTATION the same clip is EXACT (ratio 1.000000, 0 diff blocks, the hyphen survives)** | registered `05-onnx-asr.md:102`; corrected 2026-10-08, receipt 02 |
| **long slice** | `plain-3600s.wav` [900, 1020) silence-aligned | sibling captions | **8/11 segments IDENTICAL**; 2 differ only `closed`→`clos`; 1 is the probe's cut at 1020 s | `05-onnx-asr.md:103` |
| **same-engine regression** | same slice, same mode | `_main/runs/threads11/silence-t4-p1.txt` (814 chars, sha256 `746DFD19…`) | **byte-identical in all 8 arms of the sweep**, and **byte-identical again from this spec's runner (11 segments, 814 chars, sha256 `746DFD19…`)** | `11-onnx-threads.md:45`; reproduced 2026-10-08 |

- **Two kinds of oracle, and they must not be confused:** the EN/PT arms are the **TERNARY** oracle
  (a different engine's output); the long-slice arm is a **REGRESSION** lock (the same engine's
  measured text). The harness labels each arm with its kind so nobody reads a regression lock as
  independent evidence.
- **`redux-ptbr.txt` is cp1252, not UTF-8** (0xE1 at offset 135) — a UTF-8 reader crashes on it
  (`05-onnx-asr.md:110`). The harness tries utf-8 → cp1252 → latin-1 and records which one it used.
- **Both oracle files carry two header lines** (`model loaded in …`, `<wav>: Ns of audio in …`) — the
  transcript is the **last non-empty line** (`_main/parity-onnx-asr.py:39-42`).
- **The text carries no quality trade for the thread count:** all 8 arms of each instrument produced
  byte-identical text (fixed 648 chars, silence 814) (`11-onnx-threads.md:45`).

**The gate (house rule — an instrument that cannot say NO is worthless):** `_main/oracle-02-asr.py`
runs the product runner and **must go RED** on (a) a **deliberately-broken copy** of `src/asr` with
`INTRA_OP_NUM_THREADS` reverted to 1 — the contract check (`intra == 4 and inter == 1`) fails — and
(b) a broken copy with `DEFAULT_SEGMENT_MODE` switched to `"fixed"` — the text collapses to the
measured **ratio 0.229** (`05-onnx-asr.md:105`). Both controls run the same code with the measured
law broken; nothing else changes.

---

## 7. THE 10 Hz LEVEL EVENT — THE WAVE'S ONLY HONEST SOURCE

**The panel cannot draw a wave from what exists today, and the reason is measured:** the level field
`peak` is a **run maximum** (only ever raised — three consecutive ticks print the identical
`peak=0.554093` while `rms` drifts, `12-audio-level-contract.md:14`), published on **stderr** at
**0.1 Hz** (`--stats-interval` default 10.0 s, `12-audio-level-contract.md:21`) and **dropped in the
shell** (`window.sotto` has no `getStats`/`onStats`, `12-audio-level-contract.md:25-31`). A wave drawn
from it is a monotone line that only rises — **"uma onda inventada é inaceitável"**
(`receipts/receipt-12-audio-level-contract.md:45-47`).

**The contract this spec fixes:**

| constant | value | provenance |
|---|---|---|
| `BLOCK_MS` | **100** → the native block rate is **10 Hz** | `12-audio-level-contract.md:20` |
| `LEVEL_HZ` | **10** | `12-audio-level-contract.md:20,23` |
| field | **`peak` = linear sample peak, 0.0–1.0, mono — not dB, not RMS** | `12-audio-level-contract.md:12` |
| per window | **windowed, never a run maximum** | the defect, `12-audio-level-contract.md:14` |
| smoothing | instant attack, exponential release, `RELEASE_TAU_S = 0.200` (**CHOICE**, inside the measured 150–250 ms band) | `12-audio-level-contract.md:45` |
| history | `LEVEL_HISTORY = 128` → **12.8 s** of visible wave | `12-audio-level-contract.md:44` |
| channel | **stdout**, one compact JSON object per line | `12-audio-level-contract.md:43` |
| budget | ≤ ~96 bytes/event → **≤ ~1 KB/s** at 10 Hz, against ~6 KB/s for the existing 600 B stats line at 10 Hz | `12-audio-level-contract.md:43` |

Event shape (keys are short **because the channel also carries captions**):
`{"type":"level","a":<audio_s>,"p":<peak>,"r":<rms>,"e":<envelope>}` — `a` is the audio clock at the
end of the window, `p` the window peak, `r` the window RMS, `e` the smoothed envelope the wave draws.
**The emitter is driven by the audio clock, not by wall time** (10 events per audio second), so a
faster-than-real-time pass emits the same number of events as a live one.

**The stdout contract, whole:** one **NDJSON** object per line — `level` (10 Hz) · `segment` (when a
segment closes) · `done` (once, carrying the transcript and every metric). `--json` prints **exactly
one line, the `done` object**, and nothing else; diagnostics go to **stderr**. The wave therefore
never competes with the transcript for the channel, and a batch run is greppable.

---

## 8. THE RUNNER'S CONTRACT

`python -m asr.transcribe --wav FILE [--json]` (run from `src/`, or `python src/asr/transcribe.py`).

| flag | default | why |
|---|---|---|
| `--wav` | required | PCM **16 kHz mono PCM16**; anything else is **refused loudly (exit 2)** — never resampled silently | `05-onnx-asr.md:41`, `probe-onnx-asr-split.py:39` |
| `--offset-s` / `--max-s` | 0 / all | the ≤120 s slice discipline the house mandates for measurement runs | `AGENTS.md:286-290` |
| `--model-dir` | `models/parakeet-tdt-0.6b-v3-onnx` (repo-relative) | path ⇒ offline load | `05-onnx-asr.md:26` |
| `--quant` / `--provider` | `int8` / `cpu` | the measured artefact and provider | `05-onnx-asr.md:37-39` |
| `--segment-mode` | **`silence`** (`fixed` = CONTROL ONLY) | §3 | `05-onnx-asr.md:105` |
| `--max-seg` | **15.0** | §3 — the memory knob | `05-onnx-asr.md:67` |
| `--threads` / `--inter-threads` | **4** / **1** | §2 | `11-onnx-threads.md:53` |
| `--level` | `on` | the wave is a contract, not a mode | §7 |
| `--json` | off | one JSON document instead of the event stream | §7 |
| `--phases` | off | instrument-only: splits encode/decode on the **first and the last** segment (the first is atypical, §5) | `probe-onnx-asr-phases.py` |

`done` carries, at minimum: `threads{intra,inter,omp_env}` · `segment_mode` · `n_segments` ·
`seg_median_s` · `seg_max_s` · `audio_s` · `load_s` · `infer_s` · `rtfx_infer` · **`rtfx_steady`**
(§5) · `rss_after_load_mb` · `rss_peak_mb` · `rss_peak_wset_mb` · `cpu_median_pct` · `cpu_max_pct` ·
`level{n_events,hz,peak}` · `segments[]` · `text`.

**Every metric the receipt will quote is produced by the process that did the work** (RSS from its own
`psutil` poll at 1 Hz plus the OS `peak_wset`, `probe-onnx-asr.py:43-66`), not by an external guess.

---

## 9. WHAT THIS SPEC DELIBERATELY DOES NOT DO

- **It does not resample.** A 44.1 kHz or stereo file is refused, not silently converted — a silent
  conversion is how a language or a level gets destroyed.
- **It does not use a fixed grid, and does not offer one as a normal mode.** `--segment-mode fixed`
  exists so the oracle can prove it is worse; it is never a default.
- **It does not run the ternary engine in the product.** The ternary is the parity oracle only.
- **It does not claim a VAD.** The splitter is energy-only; `onnx-asr`'s Silero VAD is not on disk.
- **It does not promise word-level timestamps.** Segment boundaries are the model's own and were
  never compared against a reference (`04-asr.md:139`, `05-onnx-asr.md:120`).
- **It does not use the GPU.** `CUDAExecutionProvider` does not load through ORT here, and law 5
  requires the CPU path to be the product path.

## 10. WHAT IS STILL UNKNOWN (named, not hidden)

1. **Game audio.** Every number here is read speech (FLEURS-class) or the sibling's synthetic clips.
   There is **no measurement of any candidate on music + explosions + overlapping speech**
   (`04-asr.md:132-134`). The noise gap is Redux's widest weakness (MUSAN 9.04 vs 6.72,
   `04-asr.md:30`), and it is inherited by this export.
2. **Audio past 120 s of continuous input.** The 20-minute curve was built from the same 120 s slice
   repeated in series (`05-onnx-asr.md:60-66`), and the lanes were budget-bound to ≤120 s slices.
   A two-hour session is **UNVERIFIED**.
3. **The knee on a quiet box** (§2), **8+ threads**, and the **CUDA path** — never run.
4. **Word timestamps** and the model's VAD head — never exercised.
5. **The 5× gap** between the READ benchmark (31.4× int8, `04-asr.md:42`) and this box (6.06× at 2
   threads) is **UNATTRIBUTED** (`05-onnx-asr.md:117-118`); the thread pathology is part of it, not
   all of it.
