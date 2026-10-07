# SPEC 04 — THE INDEX AND SEARCH: ONE SQLITE FILE, AN EXACT NUMPY SCAN, RRF, NO RERANKER

Owner's brief (2026-10-08, verbatim intent): *a better NVIDIA ShadowPlay — instant replay that
never loses the clip, plus a searchable memory. "onde eu falei de comprar GPU?" → the moment, the
clip, the line. The owner's existing ~1 000-video library goes into the SAME index — no copies of
the videos, no frame dumps.*

Status: **SPEC, and every number below is MEASURED on this box** — nothing here is inherited from
the brief. The whole design was measured first in `docs/research/07-index-search.md`; this file
transcribes it into a contract. Each constant carries its provenance as `research/07:NN`, which is
**line NN of that document**. **A constant without provenance is a bug in this spec**, and where the
research measured nothing, this file writes `**UNKNOWN — not measured**` rather than a plausible
number — *a spec with invented numbers is worse than no spec, because it launders a guess into an
authority.*

`MEASURED` = a command on this box produced it · `READ` = source read (URL given in `research/07`) ·
`UNKNOWN — not measured` = nobody has shown it. Host: Windows 11 · i5-13600K · RTX 5080.

**Every latency in this file was measured at the lane's 2-thread budget**
(`OMP/OPENBLAS/MKL_NUM_THREADS=2`, recorded inside every JSON — `research/07:8-9`), which is law 8:
*our* measurements are politeness on the owner's machine; the product's engine is the exception and
wants the measured knee (`AGENTS.md:306-320`, `ROADMAP.md:233-234`). **The scan at the product's
4-thread knee is `UNKNOWN — not measured`** (`research/07:30`, `research/07:85`).

---

## 0. THE DECISION IN ONE PARAGRAPH

**The store is ONE SQLite file** holding the relational record *and* every vector, as fp16 blobs in
`embedding(seg_id, channel, vec BLOB)` (`research/07:4-5`, schema at `research/07:33-43`). **Search is
a numpy brute-force scan of the whole matrix in RAM — exact, not approximate: 15.99 ms min /
20.3 ms median per channel over the product's real 211 200-vector corpus** (`research/07:27`).
The three provenance channels merge with **Reciprocal Rank Fusion**, every hit naming the channels
that matched (`research/07:48`). A **4th lexical list joins the fusion** — SQLite FTS5 over
`ocr.text_norm` + `transcript.text_norm` — because OCR's required baseline is lexical, and lane 02
measured game tokens coming back byte-exact (`research/07:53`). **There is no reranker**: the smallest
shippable local one costs **10.8 s/query**, 130× the entire fused query (`research/07:58`,
`research/07:64`). **Identity is `content_key`, a whole-file SHA-256 — never the path**
(`research/07:46`). Crash safety is **proven in both colours**: WAL + `synchronous=NORMAL` recovered
exactly **16 000 rows** after `taskkill /F`, while `journal_mode=OFF` tore to **18 041** and a tiny
`cache_size` produced a **malformed** database (`research/07:24`).

Against law 4 (*the index is tiny next to the video*): **the whole store is 144 MB for a ~300 GB
library — 0.05 %** (`research/07:82`). **Never store frames. Never store a second copy of a video.**
The `ocr` table carries `frame_ref` (`research/07:38`) — a **reference**, never frame bytes.

---

## 1. THE STORE — ONE SQLITE FILE, AND THE FOUR THAT WERE REFUSED

The search path is a **numpy flat scan over the SQLite blob table**: the array is derived, so it
costs **0 extra bytes of installed dependency** (`research/07:13`). This is the default, and the
table below is the refutation record — every alternative was measured, not dismissed.

| store | weight | incremental while recording | verdict |
|---|---|---|---|
| **numpy flat over the SQLite blob table** | **0 extra** (the array is derived) | ✓ **0.011 ms/row** | **THE DEFAULT** (`research/07:13`) |
| `sqlite-vec` 0.1.9 | 295 723 B installed (win_amd64 wheel 292 804 B, READ PyPI) | ✓ 0.113 ms/row | **for the record, NOT for search** (`research/07:14`) |
| `faiss-cpu` 1.15.1 | 64.5 MiB installed | ✓ in RAM, but a **full rewrite** to persist | only past the crossover (`research/07:15`) |
| `hnswlib` 0.8.0 | — | — | **NOT INSTALLABLE HERE** (`research/07:16`) |
| `LanceDB` 0.40.0 | 25–35 MiB wheel + `pyarrow>=16` (86.2 MiB here) + pydantic | ✓ | NOT INSTALLED (heavy) (`research/07:17`) |
| `Qdrant local` 1.19.1 | pure-python wheel + grpc/http2/protobuf | ✓ | NOT INSTALLED (`research/07:18`) |

Why each refusal is a measurement, not a preference:

- **`hnswlib` cannot be installed here.** PyPI publishes **only an sdist**
  (`hnswlib-0.8.0.tar.gz`, 36 206 B, no wheel of any platform — READ
  `https://pypi.org/pypi/hnswlib/0.8.0/json`) and the build needs MSVC 14.0+, which is absent
  (`AGENTS.md:93`). `import hnswlib` → `ModuleNotFoundError` (MEASURED). So HNSW was measured
  **through faiss's own implementation** instead (`research/07:19`).
- **faiss HNSW is fast and CANNOT DELETE.** Build 120 k (M=16, efC=200): **85.21 s** (1 408 vec/s,
  single thread); query 0.154 ms at `ef=16` → 1.216 ms at `ef=256`. `remove_ids` →
  **`RuntimeError: remove_ids not implemented for this type of index`** (MEASURED)
  (`research/07:20`): **a moved or deleted file cannot be removed without a full rebuild** — which
  is precisely the operation §3 makes mandatory.
- **Its recall on this data was 3–29 %** (`recall@10` 0.034 / 0.05 / 0.104 / 0.176 / 0.29 across the
  `ef` sweep) — but that is the *worst* case, on random 256-d unit vectors that are nearly
  orthogonal, so it is **not** a prediction for real embeddings (`research/07:21`). The decision does
  not rest on it: **at 16 ms for an exact answer there is no reason to buy speed with unmeasured
  recall loss.** `UNKNOWN — not measured`: HNSW recall on real embeddings (`research/07:21`).
- **`sqlite-vec` vec0 is ~16× slower than numpy**: same 120 k vectors, same process, 2 threads,
  `k=10` **118.9 ms** / `k=100` **136.1 ms**, against numpy's 7.6 ms (`research/07:23`). Its **partition
  key is the trap**: `partition key = video_id` (1000 shards) → 902 / 1074 ms and a **1050 MiB** file
  for a 206 MiB payload (**5.1×**). It wins only when the query carries that key
  (`k=100 AND video_id=42` = 0.82 ms). **The rule this yields: a partition key must be a filter you
  ALWAYS apply — global search always filters `channel`, never `video_id`** (`research/07:23`).
- **The one measured exception, kept on the record:** `faiss.IndexFlatIP` does 100 queries in
  494.7 ms = **4.95 ms/query** (batch of 100, 2 threads) against numpy's 7.64 ms for a *single*
  query, on the same 122.88 MB payload with no approximation (`research/07:22`). ⚙ **The comparison
  is batch-against-single** — the batch amortises the matrix read — so this is **not** evidence that
  faiss beats numpy per query. If the UI ever issues batches, re-measure both sides batched before
  switching.

---

## 2. THE SCHEMA — SIX TABLES, AND `video` IS `asset`

**`video` IS lane 08's `asset`** (`docs/research/08-import-library.md`) — two names for one table is
how a repo grows a bug, so this spec ships **ONE name: `video`**, keeping lane 08's identity columns
(`research/07:32`). Transcribed verbatim from `research/07:33-43`:

```sql
video(id PK, content_key, path, size_bytes, mtime_ns, duration_ms, w, h, fps,
      added_at, last_seen_scan, missing, state)          -- lane 08: content_key = whole-file SHA-256
segment(seg_id PK, video_id FK, start_ms, end_ms, n_visual, n_speech, n_ocr, state)
transcript(seg_id PK, start_ms, text, text_norm, producer, model_sha256)
ocr(seg_id, line_no, t_ms, t_end_ms, text_raw, text_norm, box, conf, engine, model_sha256, frame_ref,
    PK(seg_id, line_no))                                 -- lane 02's request list, verbatim
embedding(seg_id, channel, dim, dtype, vec BLOB, model, model_sha256, built_at, PK(seg_id, channel))
marker(seg_id, kind, value, source)
CREATE INDEX segment_video ON segment(video_id, start_ms);
```

Rules this schema carries, each traceable:

- **The timestamp belongs to the SEGMENT, not the video.** A hit is a 5 s window, so *"open X at
  mm:ss.s"* is a property of the hit (`research/07:44`).
- **The answer path is ONE JOIN, measured at 0.011 ms** (`research/07:44`): a KNN hit names a
  `seg_id`; `segment` gives `start_ms`; `video` gives `path` → `"clip_0644.mp4 @ 04:05.0"`.
- **`PK(seg_id, channel)` IS the work unit** (§10): same channel + same model is `INSERT OR IGNORE`
  (a no-op); a different model is `INSERT OR REPLACE`, and the change is **detectable per row, never
  a silent mix** (`research/07:70`).
- **`model_sha256` on `transcript` and `embedding` is mandatory**, because it is what makes
  promotion and invalidation decidable (§10) — and it is what §9's reranker verdict would have needed
  if the answer had been yes.
- **`state` and `missing` are load-bearing**, not bookkeeping (§3).
- **`frame_ref` is a reference.** OCR lines point at frames; the frames themselves are never stored
  (law 4).

---

## 3. IDENTITY AND INVALIDATION — `content_key`, NEVER THE PATH

**Identity is `content_key` = whole-file SHA-256, NEVER the path** (`research/07:35`, `research/07:46`).
Lane 08 MEASURED what a path key costs: **a path key re-processes all 300 GB after one rename**
(`research/07:46`).

| what happened on disk | what the index does |
|---|---|
| **moved** (same `content_key`, new `path`) | `UPDATE video SET path=?, missing=0` — **no re-index, one row** (`research/07:46`) |
| **deleted** (a scan does not see it) | set `missing=1` and **keep every row** — the transcript and vectors stay searchable, the UI says the file is gone; the KNN drops `missing=1` rows with the same free mask as any filter (`research/07:46`) |
| **changed** (same path, new `content_key`) | a **NEW** `video` row; the old one is superseded, **never deleted** (`research/07:46`) |

**Never delete embeddings on a path miss.** And note the shape of that rule: it is **exactly** what
an HNSW index cannot do (§1, `remove_ids not implemented`) — the cheap store is not only faster here,
it is the only one of the five that can honour the invalidation contract.

**Dropping `missing=1` costs no time**: the mask is applied *after* the full scan, so a filter is
free (§6, `research/07:28`).

---

## 4. LIVE CLIPS AND THE IMPORTED LIBRARY ARE THE SAME ROWS

**The SAME index holds new clips and the imported library.** A clip is a `video` row created by
S1+S2 (`specs/01`); a library file is one created by the scanner (`state='discovered'`) before any
content work. **The difference is the producer, never the table**: the light writer versus lane 08's
leased job queue (`research/07:45`).

Which pass wrote each row is recorded, not guessed: **`transcript.producer`** and
**`embedding.model`** (`research/07:45`).

**The durable queue with leases is lane 08's `job` table — recovery is one UPDATE** (every `running`
row with an expired lease returns to `pending`). **Do not invent a second one** (`research/07:71`).

---

## 5. SIZES — 117.19 MiB, 206.2 MiB, AND 0.05 % OF THE LIBRARY

1 000 videos × 10 min = 600 s ÷ 5 s = **120 segments/video → 120 000 segments** (`research/07:73`).

| | vectors | FP32 | FP16 |
|---|---|---|---|
| one vector per segment (visual only) | 120 000 | 122 880 000 B = **117.19 MiB** / 122.88 MB | 61 440 000 B = **58.59 MiB** / 61.44 MB (`research/07:76`) |
| **all three channels** (speech ~60 %, OCR ~16 % — **an assumed mix**) | **211 200** | 216 268 800 B = **206.25 MiB** / 216.27 MB | 108 134 400 B = **103.13 MiB** / 108.13 MB (`research/07:77`) |

- **The brief's "~123 MB FP32 / 61 MB FP16" is arithmetically CORRECT — and counts ONE vector per
  segment.** With the product's three channels the same library is **1.76× that: 216 MB FP32 /
  108 MB FP16** (`research/07:78`). `UNKNOWN — not measured`: the real speech/OCR coverage fractions
  (60 % / 16 % are **this lane's assumption**; the cost is exactly linear in the vector count)
  (`research/07:84`).
- **The real single-file number, with everything in it** (`_main/_index-final/store.db`, MEASURED):
  **137.34 MiB = 144.01 MB** for all 211 200 fp16 vectors **and** the whole relational half
  (1 000 `video` + 120 000 `segment` + 72 000 `transcript` + 19 200 `ocr` rows + 4 indices) =
  **+33.2 % over the vector payload**, of which **34.2 MiB** is the relational half. The same file
  with fp32 vectors ≈ **240 MiB** (`research/07:79`).
- **ANN overhead, for contrast (all MEASURED):** sqlite-vec vec0 unpartitioned **+6.3 %**
  (124.6 MiB file / 117.2 MiB payload at 120 k); vec0 partitioned by `video_id` **1050 MiB = 5.1× the
  payload**; faiss HNSW **134.8 MiB** for the same 117.2 MiB payload (`research/07:80`). See §13 for
  the per-vector reading of the HNSW figure.
- **RAM to search it: 206.2 MiB fp32.** The fp16 blobs are cast **once** at load — **0.99 s** for all
  211 200 vectors, measured end to end from SQLite (`research/07:81`); cast throughput
  **1.0 s/GB** (61.4 MB in 60.5 ms) (`research/07:29`).
- **So: 1 000 ten-minute videos, three channels, 256 d, fp16 = 108 MB of vectors, 144 MB of store,
  206 MiB of search RAM — against ~300 GB of video. The index is 0.05 % of the library**
  (`research/07:82`).

**FP16 is a DISK decision, never a compute one** (`research/07:29`). Native fp16 matvec of the same
120 k measured **67.3 ms — 8.8× slower than fp32** (no fp16 BLAS kernel in this `openblas64` build;
the mechanism is an inference, the number is measured). **Store fp16, cast once at load, scan fp32**:
11.0 ms, and the top-10 was **identical** to the fp32-stored top-10 (**10/10 overlap**).

---

## 6. SEARCH — A BRUTE-FORCE EXACT SCAN, 16 ms PER CHANNEL

**numpy brute-force scan of the whole matrix in RAM. Exact. No approximation.** At the product's own
corpus:

| corpus | vectors | `k=100` | bandwidth |
|---|---|---|---|
| one vector per segment | 120 000 | **7.64 ms min / 10.05 ms median** | 16.1 GB/s (`research/07:26`) |
| **the real three-channel corpus** | **211 200** | **15.99 ms min / 20.3 ms median** | 13.5 GB/s (`research/07:27`) |

- **The scan is bandwidth-bound and linear in N** (`research/07:27`). The headline "16 ms" is the
  **minimum** of that sweep; the median is **20.3 ms** — quote the median in any UI latency promise.
- **Filtering is free in time**, because the mask is applied *after* the full scan: `channel=speech`
  15.68 ms, `channel=ocr` 14.92 ms, `video 42 ∧ 0–60 s` 14.36 ms, one 5 s window 14.28 ms
  (`research/07:28`).
- **The temporal filter is per-video: `(video_id, t0_ms, t1_ms)`.** A bare `start_ms` range across the
  library is meaningless — `start_ms` is relative to each video's own start (`research/07:51`).
  **Control (MEASURED):** window `(42, 0, 60 s)` → 10/10 hits in video 42 under 60 s; window
  `(42, 60–65 s)` → **exactly 1 hit** — which is the correct answer, since a 10-minute video is 120
  rows of 5 s (`research/07:52`).
- **The cost of the window is none:** 67.98 ms vs 72.57 ms unfiltered (`research/07:52`).
  To make a window *cheap*, slice the array per video and scan only those rows.
  **`UNKNOWN — not measured`: the saving** (`research/07:52`, `research/07:86`).

**The crossover, and when to revisit this decision.** From two measured points in one process:
0.0916 µs/vector → 50 ms at N ≈ 582 k, 250 ms at N ≈ 2.77 M. Brute force stops being comfortable at
**~0.5–0.6 M vectors ≈ 2.7× the product's own 211 k library**; an ANN index is justified only past
~1 M (`research/07:30`). ⚠ The two points in that sentence are **not consistent with each other** —
see §13. `UNKNOWN — not measured`: the 4-thread scan (expected ~2× faster, i.e. ~1.2 M before the
crossover) — this lane held the 2-thread budget (`research/07:30`, `research/07:85`).

---

## 7. FUSION — RRF OVER THREE CHANNELS, PLUS A 4TH LEXICAL LIST

**Rule: Reciprocal Rank Fusion, one KNN per channel.**

```
score(seg) = Σ_c  w_c / (60 + rank_c(seg))
w = { speech 1.0, ocr 1.0, visual 0.7 }        each channel contributes k = 100
```

(`research/07:48`.) **RRF because the three channels live in three spaces with three distance scales
— ranks are the only comparable quantity**, which is why the score needs no calibration
(`research/07:48`).

- **Measured end to end: query → 10 explainable hits = 72.6 ms min / 83.2 ms median** at 2 threads
  (three scans of the 211 200-vector matrix + RRF + the JOIN) (`research/07:49`). That is ~3× the
  single-channel 16–20 ms, as three scans must cost.
- **Explainable by construction:** each hit carries `channels[]` and, per channel, `rank` + `cosine` —
  **those are the three UI chips** (`research/07:50`, and the shape the owner approved in
  `AGENTS.md:61-67`). **Control, both colours in one run:** all 10 hits name ≥ 1 channel; all three
  channels appear in the top-10; **10/10 were matched by more than one channel**.
- **A hit must be able to say WHICH channel matched** (`AGENTS.md:61-64`) — this is why `channels[]`
  is part of the contract and not a debug field.

**A 4th list belongs in the fusion: SQLite FTS5 over `ocr.text_norm` + `transcript.text_norm`**
(`research/07:53`). Lane 02 MEASURED that exact game tokens (`ERRO 0x80070005: ACESSO NEGADO`) come
back byte-exact, and **lexical is the *required* baseline for OCR** (`research/07:53`).

> **`UNKNOWN — not measured`: the FTS5 list's RRF weight**, and whether it belongs in the same
> fusion (`research/07:53`, `research/07:89`).
>
> ⚙ **Shipping rule until it is measured:** build the FTS5 channel and run it, but **keep it out of
> the default fusion** — a list fused in at an invented weight is exactly the failure this repo has
> already paid for. Ship it as an explicit lexical mode until its weight is measured on real data.

---

## 8. NO RERANKER — IT COSTS 10.8 s PER QUERY

Measured denominator, this box, **2 threads**: **53.8 GFLOP/s** fp32 (100×768×768), 56.1
(6400×768×768). Cost model `2 × P × L` per candidate × 100 candidates. Params/licences READ from the
HF API (`research/07:55`).

| candidate (READ) | params | licence | 100 cands × 128 tok | at measured fp32 2t |
|---|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L6-v2` | 22 714 113 | apache-2.0 | 0.581 TFLOP | **10.8 s** |
| `mixedbread-ai/mxbai-rerank-base-v1` | 184 422 913 | apache-2.0 | 4.71 TFLOP | 87.6 s |
| `BAAI/bge-reranker-base` | 278 044 931 | mit | 7.12 TFLOP | 132.3 s |
| `jinaai/jina-reranker-v2-base-multilingual` | 278 437 633 | **cc-by-nc-4.0** | 7.13 TFLOP | **not shippable** |
| `BAAI/bge-reranker-v2-m3` | 567 755 777 | apache-2.0 | 14.54 TFLOP | 270.3 s |
| `Qwen/Qwen3-Reranker-0.6B` | 595 776 512 | apache-2.0 | 15.26 TFLOP | 283.6 s |

(`research/07:56-63`.)

**Verdict: NO** (`research/07:64`). Even the smallest cross-encoder costs **10.8 s** for one query at
2 threads — **130× the entire fused query (83 ms)** — and **no measurement exists that it improves
top-5 on our data**. (`UNKNOWN — not measured`, and it is the reason the verdict is easy.)

**Ship top-k vector + lexical overlap instead:** pure-python Jaccard over 100 candidates measured
**0.146 ms median — 74 000× cheaper** (`research/07:64`).

If a reranker is ever wanted it must change one of three things: **≤20 candidates**, **int8 ONNX**,
or **the GPU** (`torch.cuda.is_available()` is TRUE here — `AGENTS.md`) (`research/07:65`). The number
that would reopen this: an int8 kernel ≥10× the measured fp32 GEMM — **`UNKNOWN — not measured`**
(`research/07:65`, `research/07:87`). Free alternative: **re-rank with the embedding model itself** —
no new weights, no new licence (`research/07:65`).

---

## 9. CRASH SAFETY — PROVEN IN BOTH COLOURS

**This is the one part of the index whose green was earned rather than assumed.** The instrument is
`_index-crash2-probe.py`: `taskkill /F` on the exact PID, aimed by a marker at the instant the writer
is **INSIDE** a transaction, 20 000 rows, batch 2 000 (`research/07:24`).

| arm | config | result |
|---|---|---|
| **A** | **WAL + `synchronous=NORMAL`** (the shipped config) | WAL **5 034 672 B** at kill, `integrity_check=ok`, **16 000 rows recovered = a clean multiple of the batch**, KNN answers → **clean** |
| **B** | `journal_mode=OFF, synchronous=OFF` | **18 041 rows — torn**, not a multiple of the batch: the in-flight transaction was partly applied |
| **C** | arm B **+ `cache_size=50`** | **`integrity_check` = "database disk image is malformed"**, 6 invalid page numbers, and the query raises **`DatabaseError: database disk image is malformed`** |

(`research/07:24`.) **Two red controls ⇒ the WAL green is earned, and this instrument can say NO**
(`research/07:24`) — which is what makes it worth more than the numbers it guards
(`AGENTS.md:271-276`).

**The shipping configuration, in full:**

- ✅ **`journal_mode=WAL`**
- ✅ **`synchronous=NORMAL`**
- ✅ **batched transactions**, committed per unit of work (light pass: **per 5 s window**,
  `research/07:67`; the probe proved a 2 000-row batch recovers as a clean multiple)
- ❌ **never `journal_mode=OFF`** — arm B tore
- ❌ **never a tiny `cache_size`** — arm C produced a malformed database
- ⚠ **`cache_size` for shipping = `UNKNOWN — not measured`.** The only value on record, `50`, is a
  **red control**. ⚠ And note arm C layered `cache_size=50` **on top of** arm B's already-broken
  journal config, so it does **not** isolate `cache_size` as a cause — see §13. **Do not "fix" this
  by citing arm C as proof that a small cache corrupts a database.**

**Incremental insert while recording: 0.011 ms/row** (`research/07:13`), independently corroborated
by the bulk path's **92 688 vectors/s** (= 0.0108 ms/vector) at `research/07:67`. ⚠ The research
prints `0.011 ms` in two places for two different operations — see §13.

---

## 10. TWO SPEEDS — WHAT THE LIGHT PASS WRITES, AND HOW A SEGMENT IS PROMOTED

**LIGHT (while recording, one 5 s window at a time):** `segment` + `transcript` + one vector per
channel that exists, **committed per window**: **0.061 ms median, p95 0.198 ms, max 1.056 ms**
(200 samples, WAL, `synchronous=NORMAL`). Bulk path **92 688 vectors/s** (`research/07:67`). It
computes only what it already has: the text embedding of the closed line and the visual embedding of
the frames in hand.

**What the light pass does NOT do:** OCR (lane 02 MEASURED it is a *batch* channel over recorded
frames, never live), the second ASR pass, any reranker. **That is what makes it light**
(`research/07:68`).

**PROMOTION** runs in lane 01's idle window (`specs/01` §6): the heavy pass writes the missing channel
rows and re-runs any channel whose `model_sha256` changed (`research/07:69`).

**How double work is avoided — the primary key IS the work unit** (`research/07:70`):

| situation | statement | effect |
|---|---|---|
| same channel, same model | `INSERT OR IGNORE` | **a no-op** |
| same channel, different model | `INSERT OR REPLACE` | the change is **detectable per row, never a silent mix** |
| `transcript(seg_id)` | same two rules | ASR re-run is safe for the same reason |
| promoting one 10-minute video | 120 segments × 3 channels = **360 rows ≈ 4 ms** of writes | at the measured 92 688 vectors/s (`research/07:70`) |

**One 5 s window, one vector per channel** — and this is forced by the model, not chosen:
`embeddinggemma-2`'s `encode()` returns **exactly ONE 768-d vector per call, for the whole input**
(32 frames, 5 minutes of audio or one sentence alike) — **no per-frame vectors, no per-second
vectors, and no timestamps come out** (`AGENTS.md:106-110`). **Sotto's 5 s granularity is OUR loop:
one call per window.** The index dimension is **256** (Matryoshka), one call per 5 s window
(`AGENTS.md:115`, sizes at `research/07:26`).

---

## 11. THE CONSTANTS — the table to copy into code

| constant | value | source |
|---|---|---|
| index dimension | **256** | `AGENTS.md:115`, `research/07:26` |
| segment granularity | **5 s** | `AGENTS.md:109`, `research/07:73` |
| vectors per segment (visual) | 1 | `research/07:73` |
| channel weights `w` | **{speech 1.0, ocr 1.0, visual 0.7}** | `research/07:48` |
| RRF constant | **60** | `research/07:48` |
| `k` per channel | **100** | `research/07:48` |
| stored dtype | **fp16** (`dtype` column records it) | `research/07:29`, `research/07:79` |
| scan dtype | **fp32**, cast once at load | `research/07:29` |
| `journal_mode` | **WAL** | `research/07:24` |
| `synchronous` | **NORMAL** | `research/07:24` |
| light-pass commit unit | **one 5 s window** | `research/07:67` |
| identity key | **`content_key` = whole-file SHA-256** | `research/07:35`, `research/07:46` |
| lane measurement threads | **2** (`OMP/OPENBLAS/MKL_NUM_THREADS=2`) | `research/07:8-9`, law 8 |
| `cache_size` (shipping) | **`UNKNOWN — not measured`** — the only value on record is a red control | §9, `research/07:24` |
| FTS5 RRF weight | **`UNKNOWN — not measured`** — keep the channel out of the default fusion | §7, `research/07:53` |
| product-engine threads | the measured knee is **4**; lanes measure at **≤2** | `AGENTS.md:236-239`, `ROADMAP.md:233-234` |

---

## 12. UNKNOWN — NAMED, WITH THE EXPERIMENT THAT SETTLES EACH

1. **The real speech/OCR coverage fractions** (60 % / 16 % are this lane's assumption) → count them
   over 20 real videos; the cost is exactly linear in the vector count (`research/07:84`).
2. **The scan at the product's 4-thread knee** — measured only at the lane's 2 (expect ~2×)
   (`research/07:85`).
3. **The window-filtered scan after slicing per video** — the mask costs nothing today; slicing is
   unmeasured (`research/07:86`).
4. **Whether an int8 reranker changes §8** — no int8 kernel rate was measured (`research/07:87`).
5. **HNSW recall on real embeddings** — random unit vectors are the easy case to *disbelieve*, not to
   trust (`research/07:88`).
6. **The FTS5 list's RRF weight**, and whether it belongs in the same fusion (`research/07:89`).
7. **A crash inside faiss's whole-file dump** — sqlite's WAL was proven with two red controls; faiss's
   dump was not, and it is the only durability point that store has (`research/07:90`).

Added by this transcription, because a spec must not leave an implementation guessing:

8. **The shipping `cache_size`** — `research/07:24` records only the red control (§9).
9. **The shipped import batch size** — the crash probe's 2 000 rows is a *probe* parameter
   (`research/07:24`); the shipped importer's batch is `UNKNOWN — not measured`.

---

## 13. WHERE `research/07` CONTRADICTS ITSELF OR OVER-STATES — SAID OUT LOUD, NOT PAPERED OVER

A transcription that silently picks a side is a transcription that launders. Five places, with the
reading this spec ships:

1. **The "16 ms" headline is the sweep's MINIMUM, not its typical value.** The product's own corpus
   is **15.99 ms min / 20.3 ms median** (`research/07:5` vs `research/07:27`). Both are quoted
   everywhere in this spec; **promise the median (20 ms/channel), never the min.**
2. **The crossover sentence does not arithmetic.** `research/07:30` gives one rate, 0.0916 µs/vector,
   and two consequences: "50 ms at N ≈ 582 k" and "250 ms at N ≈ 2.77 M". The second is consistent
   (2.77 M × 0.0916 µs = 253.7 ms). **The first is not**: 0.0916 µs/vector puts 50 ms at
   **N ≈ 546 k**, and 582 k would be 53.3 ms. Either the rate or the N is off by ~7 %. **The
   conclusion is unaffected** (both readings sit inside the doc's own "~0.5–0.6 M, ≈2.7× the 211 k
   library"), so the decision ships; **the exact crossover point does not ship.**
3. **`cache_size=50` is not an isolated cause.** Arm C is arm B **plus** `cache_size=50`
   (`research/07:24`) — `cache_size` was never tested with WAL on. So arm C proves *the instrument
   detects a malformed file*; it does **not** prove *a small cache corrupts a database*. This spec
   forbids `journal_mode=OFF` and forbids an unmeasured `cache_size`; it makes no claim about the
   mechanism.
4. **`0.011 ms` appears twice, for two different operations.** `research/07:13` prints it as
   incremental-insert **per row**; `research/07:44` prints it as the **answer-path JOIN**. The bulk
   rate in `research/07:67` (**92 688 vectors/s = 0.0108 ms**) independently corroborates the §9
   per-row reading. **Do not merge the two measurements** — a JOIN and a row insert are different
   operations that happen to round to the same printed value.
5. **Law 4's headline sizes count ONE vector per segment.** `AGENTS.md:287-289` and
   `ROADMAP.md:229` state "~120 k segment vectors ≈ 123 MB FP32 / 61 MB FP16"; that is the visual
   channel alone (`research/07:76`). With three channels the same library is **1.76× that —
   216 MB FP32 / 108 MB FP16** (`research/07:77-78`). **The law's principle is unaffected** (still
   0.05 % of the library, still "never frames, never a second copy"); only the quoted figure is
   one-channel. This spec ships the three-channel numbers.

Also read carefully rather than as contradiction: **the faiss `IndexFlatIP` 4.95 ms/query is a
BATCH-of-100 figure** compared against numpy's 7.64 ms **single** query (`research/07:22`) — the
doc says so itself. It is not evidence that faiss is faster per query.

---

## 14. WHAT THIS SPEC DELIBERATELY DOES NOT DO

- **It does not store frames.** `ocr.frame_ref` is a reference; the pixels are never copied (law 4,
  `research/07:38`).
- **It does not store a second copy of a video.** The imported library is indexed in place — rows
  and vectors only (`AGENTS.md:38-39`, `research/07:82`).
- **It does not use an ANN index**, and it does not pay unmeasured recall loss for 12 ms
  (`research/07:21`, `research/07:30`).
- **It does not ship a reranker** — 10.8 s/query is 130× the whole fused query, and no measurement
  says it would help (`research/07:64`).
- **It does not invent a second job queue.** Leases and recovery are lane 08's `job` table
  (`research/07:71`).
- **It does not promise a fusion weight for the FTS5 list.** §7 ships the channel and refuses the
  weight.
- **It does not promise the OCR channel is live.** OCR is a batch channel over recorded frames
  (`research/07:68`); the light pass never runs it.
- **It does not promise a latency at the product's 4 threads.** Every number here is the lane's
  2-thread budget (§11).