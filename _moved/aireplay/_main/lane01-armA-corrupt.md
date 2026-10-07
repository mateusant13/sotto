# 07 — THE INDEX: STORE, SCHEMA, THREE-CHANNEL FUSION, RERANKER, TWO SPEEDS

**One question:** what is the store, the schema and the fusion rule of Sotto's index?
**Answer:** ONE SQLite file holds the record **and** every vector (fp16 blobs, `embedding(seg_id, channel)`
primary key); search is a **numpy brute-force scan of the whole matrix in RAM** (206 MiB, **16 ms**/query at
2 threads, exact); the three channels merge with **Reciprocal Rank Fusion** and every hit names the channels
that matched; **no reranker** — the smallest local one costs 10.8 s/query. `MEASURED` = a command on this box
· `READ` = a source says it (URL given) · `UNKNOWN` = nobody has shown it. Lane budget: **2 threads**
(`OMP/OPENBLAS/MKL_NUM_THREADS=2`), recorded inside every JSON.
## 1. THE STORE
| store | weight | one folder | crash-safe | incremental while recording | licence | verdict |
|---|---|---|---|---|---|---|
| **numpy flat over the SQLite blob table** | **0 extra** (the array is derived) | ✓ the .db | **✓ WAL — proven with two red controls** | ✓ 0.011 ms/row | numpy BSD | **THE DEFAULT** |
| **sqlite-vec** 0.1.9 | **295 723 B** installed (win_amd64 wheel 292 804 B, READ PyPI) | ✓ | ✓ WAL | ✓ 0.113 ms/row | MIT + Apache-2.0 | **for the record, NOT for search** |
| **faiss-cpu** 1.15.1 | **64.5 MiB** installed | ✓ one file | ✗ the whole-file dump IS the index | ✓ in RAM, but a full rewrite to persist | MIT | only past the crossover |
| **hnswlib** 0.8.0 | — | — | — | — | Apache-2.0 | **NOT INSTALLABLE HERE** |
| **LanceDB** 0.40.0 | 25–35 MiB wheel + `pyarrow>=16` (86.2 MiB here) + pydantic + lance-namespace | ✓ dir | ✓ | ✓ | Apache-2.0 (classifier, READ) | NOT INSTALLED (heavy) |
| **Qdrant local** 1.19.1 | pure-python wheel + `grpcio`, `httpx[http2]`, `protobuf`, `portalocker` | ✓ dir | ✓ | ✓ | Apache-2.0 | NOT INSTALLED (its own README calls local mode for prototyping) |
- **`hnswlib` cannot be installed here: PyPI publishes ONLY an sdist** (`hnswlib-0.8.0.tar.gz`, 36 206 B, no wheel of any platform — READ `https://pypi.org/pypi/hnswlib/0.8.0/json`), and the build needs MSVC 14.0+, which is absent (the capture lane needed **mingw** for that reason — `AGENTS.md`). `import hnswlib` → `ModuleNotFoundError` (MEASURED). So HNSW is measured **through faiss's own implementation**.
- **faiss HNSW is fast and CANNOT DELETE.** Build 120 k (M=16, efC=200): **85.21 s** (1408 vec/s, single thread). Query **0.154 ms** at `ef=16` → **1.216 ms** at `ef=256`. File **141 371 558 B = 134.8 MiB** for a 117.2 MiB payload (**154.1 B/vector**). `remove_ids` → **`RuntimeError: remove_ids not implemented for this type of index`** (MEASURED): **a moved or deleted file cannot be removed without a full rebuild.**
- **…and its recall on this data is 3–29 %** (`recall@10` 0.034 / 0.05 / 0.104 / 0.176 / 0.29 across the ef sweep). That is the worst case — random 256-d unit vectors are nearly orthogonal, so it is **not** a prediction for real embeddings — but it means the ANN speed win is bought with an **unmeasured** recall loss. At **16 ms for an exact answer** there is no reason to pay it. `UNKNOWN:` HNSW recall on real ones.
- **faiss `IndexFlatIP` is a drop-in faster exact scan**: 100 queries in 494.7 ms = **4.95 ms/query** (batch of 100, 2 threads) against numpy's 7.64 ms for a single query — the batch amortises the matrix read. Same 122.88 MB payload, no approximation. A good middle option if the UI ever issues batches.
- **sqlite-vec vec0 is 16× slower than numpy** — same 120 k vectors, same process, 2 threads: `k=10` **118.9 ms**, `k=100` **136.1 ms**, vs numpy **7.6 ms**. The partition key is the trap: `partition key = video_id` (1000 shards) → `k=10` **902 ms**, `k=100` **1074 ms**, and a **1050 MiB** file for a **206 MiB** payload (**5.1×**). It wins only when the query carries that key: `k=100 AND video_id=42` = **0.82 ms**. Rule: **a partition key must be a filter you ALWAYS apply — global search always filters `channel`, never `video_id`.** vec0 does take live INSERTs (20 000 bulk at **24 805/s**, one committed row **0.113 ms**).
- **Crash safety, both colours in one instrument** (`_index-crash2-probe.py`, `taskkill /F` on the exact PID, aimed by a marker at the instant the writer is INSIDE a transaction, 20 000 rows, batch 2 000). **ARM A** WAL/`synchronous=NORMAL` (the shipped config) → WAL 5 034 672 B at kill, `integrity_check=ok`, **16 000 rows recovered = a clean multiple of the batch**, KNN answers, **clean**. **ARM B** `journal_mode=OFF, synchronous=OFF` → **18 041 rows** — a *torn* count, not a multiple of the batch: the in-flight transaction was partly applied. **ARM C** the same plus `cache_size=50` (so the transaction's pages reach the file before commit) → **`integrity_check` = "database disk image is malformed"**, 6 invalid page numbers, and the query raises **`DatabaseError: database disk image is malformed`**. Two red controls ⇒ the WAL green is **earned**, and this instrument can say NO.
### Is a numpy brute-force scan already enough at ~120 k? Yes — with the arithmetic
- **120 000 × 256 FP32 = 117.19 MiB (122.88 MB)**; `k=100`: **7.64 ms min / 10.05 ms median** (16.1 GB/s).
- The product's real corpus is **three channels: 211 200 vectors = 206.2 MiB (216.3 MB)**; `k=100`: **15.99 ms min / 20.3 ms median** (13.5 GB/s). **The scan is bandwidth-bound and linear in N.**
- **Filtering is free in time**: `channel=speech` 15.68 ms, `channel=ONSCREEN-TEXT-CHANNEL-REMOVED` 14.92 ms, `video 42 ∧ 0–60 s` 14.36 ms, one 5 s window 14.28 ms — the mask is applied *after* the full scan.
- **FP16 is a DISK decision, never a compute one.** Native fp16 matvec of the same 120 k: **67.3 ms — 8.8× slower than fp32** (no fp16 BLAS kernel in this `openblas64` build; the mechanism is an inference, the number is measured). Store fp16, cast **once** at load (**1.0 s/GB**: 61.4 MB in 60.5 ms), scan fp32: **11.0 ms**, and the top-10 is **identical** to the fp32-stored top-10 (10/10 overlap).
- **Crossover, from two measured points in one process:** 0.0916 µs/vector → **50 ms at N ≈ 582 k**, **250 ms at N ≈ 2.77 M**. Brute force stops being comfortable at **~0.5–0.6 M vectors = ~2.7× the product's own 211 k library**; an ANN index is justified only past ~1 M. (At the product's **4-thread** knee it should be ~2× faster → ~1.2 M. **UNKNOWN:** not measured — this lane held the 2-thread budget.)
## 2. THE SCHEMA — and how a hit becomes "open the file X at 03:41.2"
`video` **IS lane 08's `asset`** (`docs/research/08-import-library.md`) — two names for one table is how a repo grows a bug; keep lane 08's identity columns and the brief's table name:
(schema fence removed by ARM-A)
- **The answer path is one JOIN, measured at 0.011 ms**: a KNN hit names a `seg_id`; `segment` gives `start_ms`; `video` gives `path` → `"clip_0644.mp4 @ 04:05.0"`. **The timestamp belongs to the SEGMENT, not the video** — a hit is a 5 s window, so "open X at mm:ss.s" is a property of the hit.
- **The SAME index holds new clips and the imported library.** A clip is a `video` row created by S1+S2 (`specs/01`); a library file is one created by the scanner (`state='discovered'`) before any content work. The difference is **the producer, never the table**: the light writer vs lane 08's leased job queue. `transcript.producer` + `embedding.model` record which pass wrote each row.
- **Invalidation — identity is `content_key`, never the path** (lane 08 MEASURED: a path key re-processes all 300 GB after one rename): **moved** → same `content_key` → `UPDATE video SET path=?, missing=0`, **no re-index, one row**; **deleted** → a scan that does not see it sets `missing=1` and keeps every row (the transcript and vectors stay searchable, the UI says the file is gone) and the KNN drops `missing=1` rows with the same free mask as any filter; **changed** (same path, new `content_key`) → a NEW `video` row, the old one superseded, never deleted. **Never delete embeddings on a path miss** — and note that this is exactly what an HNSW index cannot do (§1).
## 3. FUSION OF THE THREE CHANNELS — filterable by window, and explainable
- **Rule: Reciprocal Rank Fusion, one KNN per channel.** `score(seg) = Σ_c w_c / (60 + rank_c(seg))`, `w = {speech 1.0, ONSCREEN-TEXT-CHANNEL-REMOVED 1.0, visual 0.7}`, each channel contributing `k=100`. RRF because the three channels live in three spaces with three distance scales — **ranks are the only comparable quantity**, which is why the score needs no calibration.
- **Measured: query → 10 explainable hits = 72.6 ms min / 83.2 ms median** at 2 threads (three scans of the 211 200-vector matrix + RRF + the JOIN).
- **Explainable by construction:** each hit carries `channels[]` and, per channel, `rank` + `cosine` — that is the three UI chips. **Control (both colours, one run):** all 10 hits name ≥ 1 channel; all three channels appear in the top-10; **10/10 were matched by more than one channel**.
- **The temporal filter is per-video: `(video_id, t0_ms, t1_ms)`.** A bare `start_ms` range across the library is meaningless — `start_ms` is relative to each video's own start. **Control:** window `(42, 0, 60 s)` → 10/10 hits in video 42 under 60 s; window `(42, 60–65 s)` → **exactly 1 hit**.
- **Cost of the window: none.** 67.98 ms vs 72.57 ms unfiltered — the mask runs after the scan. To make a window *cheap*, slice the array by video (one 10-min video = 120 rows) and scan only those. **UNKNOWN:** the saving.
- **A 4th list belongs in the fusion: SQLite FTS5 over `ONSCREEN-TEXT-CHANNEL-REMOVED.text_norm` + `transcript.text_norm`.** Lane 02 MEASURED that exact game tokens (`ERRO 0x80070005: ACESSO NEGADO`) come back byte-exact, and lexical is the *required* baseline for ONSCREEN-TEXT-CHANNEL-REMOVED. **UNKNOWN:** its RRF weight (not measured here).
## 4. RERANKER — not worth the cost at this scale
Measured denominator, this box, **2 threads**: **53.8 GFLOP/s** fp32 (100×768×768), 56.1 (6400×768×768). Cost model `2 × P × L` per candidate × 100 candidates. Params/licences **READ** from the HF API.
| candidate (READ) | params | licence | 100 cands × 128 tok | at measured fp32 2t |
|---|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L6-v2` | 22 714 113 | apache-2.0 | 0.581 TFLOP | **10.8 s** |
| `mixedbread-ai/mxbai-rerank-base-v1` | 184 422 913 | apache-2.0 | 4.71 TFLOP | 87.6 s |
| `BAAI/bge-reranker-base` | 278 044 931 | mit | 7.12 TFLOP | 132.3 s |
| `jinaai/jina-reranker-v2-base-multilingual` | 278 437 633 | **cc-by-nc-4.0** | 7.13 TFLOP | **not shippable** |
| `BAAI/bge-reranker-v2-m3` | 567 755 777 | apache-2.0 | 14.54 TFLOP | 270.3 s |
| `Qwen/Qwen3-Reranker-0.6B` | 595 776 512 | apache-2.0 | 15.26 TFLOP | 283.6 s |
- **Verdict: NO.** Even the smallest cross-encoder costs **10.8 s** for one query at 2 threads — **130× the entire fused query (83 ms)** — and no measurement exists that it improves top-5 on our data. **Ship top-k vector + lexical overlap**: pure-python Jaccard over 100 candidates measured **0.146 ms** median, **74 000× cheaper**.
- If a reranker is ever wanted it must change one of three things: **≤20 candidates**, **int8 ONNX**, or **the GPU** (`torch.cuda.is_available()` is TRUE here — `AGENTS.md`). The number that would reopen this: an int8 kernel ≥10× the measured fp32 GEMM. **UNKNOWN** — unmeasured here. Free alternative: re-rank with the embedding model itself (no new weights, no new licence).
## 5. TWO SPEEDS — what the light pass writes, and how a segment is promoted
- **LIGHT (while recording, one 5 s window at a time):** `segment` + `transcript` + one vector per channel that exists, **committed per window**: **0.061 ms median, p95 0.198 ms, max 1.056 ms** (200 samples, WAL, `synchronous=NORMAL`). Bulk path **92 688 vectors/s**. It computes only what it already has: the text embedding of the closed line and the visual embedding of the frames in hand.
- **What the light pass does NOT do:** ONSCREEN-TEXT-CHANNEL-REMOVED (lane 02 MEASURED it is a *batch* channel over recorded frames, never live), the second ASR pass, any reranker. That is what makes it light.
- **PROMOTION** runs in lane 01's idle window (`specs/01` §6): the heavy pass writes the missing channel rows and re-runs any channel whose `model_sha256` changed.
- **How double work is avoided — the primary key IS the work unit.** `embedding(seg_id, channel)`: the same channel with the same model is `INSERT OR IGNORE` (**a no-op**); with a different model it is `INSERT OR REPLACE`, and the change is **detectable per row**, never a silent mix. Same for `transcript(seg_id)`. Promoting one 10-minute video = 120 segments × 3 channels = 360 rows ≈ **4 ms** of writes at the measured 92 688 vectors/s.
- The durable queue with leases is lane 08's `job` table — **recovery is one UPDATE** (every `running` row with an expired lease returns to `pending`). Do not invent a second one.
## 6. THE ARITHMETIC OF THE BRIEF, REDONE (do not trust the brief)
1000 videos × 10 min = 600 s ÷ 5 s = **120 segments/video** → **120 000 segments**.
| | vectors | FP32 | FP16 |
|---|---|---|---|
| the brief's own line (visual only, 1 vector/segment) | 120 000 | 120 000×256×4 = **122 880 000 B = 117.19 MiB / 122.88 MB** | **61 440 000 B = 58.59 MiB / 61.44 MB** |
| **all three channels** (speech ~60 %, ONSCREEN-TEXT-CHANNEL-REMOVED ~16 % — **assumed mix**) | **211 200** | **216 268 800 B = 206.25 MiB / 216.27 MB** | **108 134 400 B = 103.13 MiB / 108.13 MB** |
- **The brief's "~123 MB FP32 / 61 MB FP16" is arithmetically CORRECT — and counts ONE vector per segment.** With the product's three channels the same library is **1.76× that: 216 MB FP32 / 108 MB FP16.**
- **+ ids / metadata / index overhead, measured on a real single file** (`_main/_index-final/store.db`): **137.34 MiB = 144.01 MB** for all 211 200 fp16 vectors **and** the whole relational half (1000 video + 120 000 segment + 72 000 transcript + 19 200 ONSCREEN-TEXT-CHANNEL-REMOVED rows + 4 indices) = **+33.2 % over the vector payload**, of which **34.2 MiB** is the relational half. The same file with fp32 vectors: ~240 MiB.
- **ANN overhead, for contrast (all MEASURED):** sqlite-vec vec0 unpartitioned **+6.3 %** (124.6 MiB file / 117.2 MiB payload at 120 k); vec0 partitioned by `video_id` **1050 MiB = 5.1× the payload**; faiss HNSW **134.8 MiB** for the same 117.2 MiB payload (**154.1 B/vector**).
- **RAM to search it: 206.2 MiB fp32** — the fp16 blobs are cast once at load, **0.99 s** for all 211 200 vectors, measured end to end from SQLite.
- **So: 1 000 ten-minute videos, three channels, 256 d, fp16 = 108 MB of vectors, 144 MB of store, 206 MiB of search RAM — against ~300 GB of video. The index is 0.05 % of the library.**
## 7. UNKNOWN — named, with the experiment that settles each
1. **The real speech/ONSCREEN-TEXT-CHANNEL-REMOVED coverage fractions** (60 % / 16 % are this lane's assumption) → count them over 20 real videos; the cost is exactly linear in the vector count.
2. **The scan at the product's 4-thread knee** — measured only at the lane's 2 (expect ~2×).
3. **The window-filtered scan after slicing per video** — the mask costs nothing today; slicing is unmeasured.
4. **Whether an int8 reranker changes §4** — no int8 kernel rate was measured here.
5. **HNSW recall on real embeddings** — random unit vectors are the easy case to *disbelieve*, not to trust.
6. **The FTS5 list's RRF weight**, and whether it belongs in the same fusion.
7. **A crash inside faiss's whole-file dump** — sqlite's WAL was proven with two red controls; faiss's dump was not, and it is the only durability point that store has.
