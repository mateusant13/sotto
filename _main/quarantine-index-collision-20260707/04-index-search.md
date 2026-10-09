# SPEC 04 — THE INDEX: SCHEMA, WRITE PATH, SEARCH SURFACE, AND WHAT IT SAYS WHEN IT CANNOT KEEP UP

**Status: SPEC — normative. Every number below is tagged `MEASURED` (a command on this box,
named with its log), `READ` (a source, cited), `⚙` (an engineering DECISION with its reason
printed), or `UNKNOWN` (nobody has shown it). **No question is left open in this file:** where
one was genuinely undecided, it is decided here and the reason is recorded inline.

It is written from the measured design (`docs/research/07-index-search.md`,
`receipts/receipt-07-index-search.md`), from the identity rules of
`docs/research/08-import-library.md`, from the embedding decision in
`receipts/receipt-06-embeddings.md`, and from **the ASR's real output**, which was re-run and
inspected for this spec (§7). It covers the whole `src/index/` package, which was **empty when this spec was drafted**
(`H:\sotto\_moved\aireplay\src\index` did not exist, verified 2026-10-07 ~12:1x). ⚠ **L4 is
implementing this spec IN PARALLEL, and `src/index/` is being written as you read this**
(`store.py`, `schema.py`, `search.py`, `selftest.py` all appeared between 12:18 and 12:38 on
2026-10-07). **§2.4 is the section most likely to be already violated** — the `INSERT OR
REPLACE` defect below was found in L4's code on the same day. If you are L4: re-read §1.1,
§2.4 and §6.3 before trusting what you wrote before 12:4x.

`MEASURED` = a command on this box produced it · `READ` = a source says it (path:line or URL
given) · `⚙` = a decision of this spec, with the reason inline · `UNKNOWN` = nobody has shown
it. Host: Win11 26200 · i5-13600K (14C/20T) · RTX 5080 · **CPU only**
(`CUDAExecutionProvider` does not load through ORT here, `AGENTS.md:230-234`).
Lane thread budget: **2 threads** (law 8). Every `MEASURED` latency below is a **2-thread**
number unless the row says otherwise.

---

## 0. THE DECISION IN ONE PARAGRAPH

**One SQLite file holds the whole record — the clip, its segments, its transcripts, its OCR
lines, and every vector as an fp16 blob — and SQLite's own FTS5 is the lexical surface.**
Search is **one exact numpy scan of the vector matrix in RAM** (206.2 MiB, **15.99 ms min /
20.3 ms median** at 211 200 vectors, `research 07 §1`), fused with FTS5's bm25 ranking by
**Reciprocal Rank Fusion** over four lists (`speech 1.0`, `ocr 1.0`, `visual 0.7`,
`lexical 1.0` ⚙, `k = 100` per list). **The store is WAL + `synchronous=NORMAL`, proven by a
kill inside a transaction with two red controls** (`receipt-07 §5`: ARM A `integrity_check=ok`
with 16 000 rows = a clean multiple of the 2 000 batch; ARM B `journal_mode=OFF` → **18 041
torn rows**; ARM C a starved `cache_size` → **"database disk image is malformed"**). **No
reranker** — the smallest local cross-encoder costs **10.8 s** for 100 candidates against an
**83.2 ms** fused query (`research 07 §4`). **The failure this whole spec is organised around
is the one where the clip exists and cannot be found**, so the write path inserts the
recovery anchor **before** the file, and §2.5 makes the gap closable by a scan that is
already measured at **8.667 ms**.

---

## 1. THE DATA MODEL

### 1.1 THE PRAGMAS — and the one that must never be starved

Set once, on every connection, before any statement (`research 07 §1`):

| pragma | value | why |
|---|---|---|
| `journal_mode` | **`WAL`** | the only setting with a proven crash result: kill inside a transaction, `integrity_check=ok`, **16 000 rows recovered = a clean multiple of the 2 000 batch** (`receipt-07 §5` ARM A) |
| `synchronous` | **`NORMAL`** | the same ARM A. Under WAL, `NORMAL` may lose the last commits on power loss but cannot corrupt the file — that is the trade this store makes deliberately |
| **`cache_size`** | **`-65536` (64 MiB)** ⚙ | **ARM C is the measured reason**: the same WAL + `NORMAL` with `cache_size=50` produced **"database disk image is malformed"**, 6 invalid page numbers, and a query that RAISED `DatabaseError` (`receipt-07 §5`). The page cache is not a tuning knob here; starving it turns a recoverable crash into a destroyed store |
| `busy_timeout` | **`5000` (ms)** ⚙ | `specs/01 §5` runs the light writer while capture continues; a 5 s window is the most any one transaction may hold the file, so a busy wait longer than that would be waiting on a bug |
| `foreign_keys` | **`ON`** ⚙ | a transcript row whose segment is gone is the exact class of hole §2 exists to prevent; SQLite does **not** enforce FKs unless this is set, and the default is OFF |
| **`recursive_triggers`** | **`ON`** ⚙ | ⚠ **NOT optional — it is the fix for a measured BLOCKER.** SQLite's default is OFF, and with it OFF **`INSERT OR REPLACE` deletes the conflicting row WITHOUT firing its `AFTER DELETE` trigger** — so the old text stays in `transcript_fts` forever while `fts_orphans` stays **0**, and the reconciliation of §2.5 cannot see it. MEASURED with `fts5vocab(transcript_fts,'row')` on 4 arms: recursive OFF after a `REPLACE` → stale token `ponte` still indexed (**stale: True**); `recursive_triggers=ON` → clean; explicit `UPDATE` → clean; `DELETE`+`INSERT` → clean. §2.4 forbids `REPLACE` on these tables **and** this pragma is set, so neither hole is reachable |
| `mmap_size` | **`0`** ⚙ | the 206.2 MiB search-RAM figure (`research 07 §6`) was measured **without** mmap; turning it on would silently change the number the memory budget was derived from |
| `wal_autocheckpoint` | **`1000` (pages)** ⚙ | SQLite's own default; named here so a later reader knows it was **kept, not chosen**. A checkpoint is a file write, and §3 forbids a query from ever paying one |

**The store lives at `%LOCALAPPDATA%\Sotto\store.db`**, never beside the video and never on
`I:` (`research 08 §-`: the DB/index/temp belong on the NVMe; `I:` is the owner's
`Seagate ST4000DM004`, measured at **19.7 MB/s** sequential and **0.041 MB/s** random with a
**21.9 ms median / 516 ms p95** random-4 KiB latency, `receipt-08 §1-2`). Derived artefacts
(posters) go to `%LOCALAPPDATA%\Sotto\thumbs\<content_key[0:2]>\…` (`research 08`).

### 1.2 THE SIX TABLES

`⚙` marks a column **this spec adds to** `research 07 §2`'s schema, with the reason given in
its row. The six table names are `research 07 §2`'s and are **not** to be renamed.

#### `video` — one row per playable file

A clip Sotto cut, **or** a file the library scanner found. The difference is `produced_by`,
**never the table** (`research 07 §2`).

| column | type | null | why |
|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | no | surrogate; the only thing a JOIN carries cheaply |
| `clip_uuid` | `TEXT NOT NULL UNIQUE` | no | ⚙ **the recovery anchor.** `content_key` is NULL until the hash pass (§2.2), so a fresh clip has no durable identity at cut time. Without this column §2.5 has nothing to scan for |
| `content_key` | `TEXT` | **yes** | SHA-256 of the whole file — the **durable identity**, and the reason a moved file is an `UPDATE` and not a re-index (`research 07 §2`; `research 08`: a *path* key re-processes all 300 GB after one rename). NULL until the hash pass, which is a by-product of a pass that already reads the bytes |
| `file_key` | `TEXT` | **yes** | `(volume_serial, ntfs_file_id)` — the cheap "have I seen this object" memo, **MEASURED at 22 µs with zero bytes read** (`receipt-08 §3`). A rename costs one open and zero reprocessing |
| `path` | `TEXT NOT NULL` | no | the only thing the UI opens; it **changes** on a move, which is why it is not an identity |
| `size_bytes`, `mtime_ns` | `INTEGER` | **yes** | NULL until the cut/`probe` stage has actually read them |
| `duration_ms` | `INTEGER` | **yes** | the **clip** duration from the container. ⚠ **not** `done.wav_format.duration_s`, which is the whole **wav file** — measured 3600.0 s against a 120 s slice (`lane-spec04-asr-emit.json`) |
| `w`, `h` | `INTEGER` | **yes** | from the encoder, not from `ffprobe` |
| `fps` | `REAL` | **yes** | ⚙ `REAL`, not INTEGER: the desktop arm's source ran at **54 fps against a declared 30** and the clip came out 1.8× slow motion (`specs/03 §2.7`). An integer frame rate cannot hold the number the capture actually produced |
| `codec`, `mode` | `TEXT` | **yes** | `H.264`/`HEVC`/`AV1`; `gaming`/`desktop` (`specs/01 §1`) |
| **`audio_wav`** | `TEXT` | **yes** | ⚙ the 16 kHz mono PCM16 wav L2 produced and the ASR consumed. NULL for a library file never transcribed — and that is the honest state, not a defect |
| **`audio_offset_ms`** | `INTEGER NOT NULL DEFAULT 0` | no | ⚙ **the offset of the wav's `t=0` inside this video's timeline.** See §1.3 — this is the single most confusable quantity in the schema |
| `src_device_id`, `src_device_name` | `TEXT` | **yes** | ⚙ **the capture/audio device**, so "filter by device" (§3.3) is answerable. NULL for a library file, which has no device |
| `produced_by` | `TEXT NOT NULL` | no | `capture-cut` \| `library-scan` \| `import`. The producer, recorded per row (`research 07 §2`) |
| `state` | `TEXT NOT NULL DEFAULT 'cutting'` | no | §6.1 |
| `missing` | `INTEGER NOT NULL DEFAULT 0` | no | a **state, never a delete**: a scan that does not see the file sets 1 and keeps every transcript and vector searchable (`research 07 §2`) |
| `added_at` | `INTEGER NOT NULL` | no | unix **seconds** — the ordering key and the keyset cursor (§3.5) |
| `last_seen_scan` | `INTEGER` | **yes** | NULL until a scan has actually looked |

```sql
CREATE TABLE video(
  id             INTEGER PRIMARY KEY,
  clip_uuid      TEXT    NOT NULL UNIQUE,
  content_key    TEXT,
  file_key       TEXT,
  path           TEXT    NOT NULL,
  size_bytes     INTEGER,
  mtime_ns       INTEGER,
  duration_ms    INTEGER,
  w              INTEGER,
  h              INTEGER,
  fps            REAL,
  codec          TEXT,
  mode           TEXT,
  audio_wav      TEXT,
  audio_offset_ms INTEGER NOT NULL DEFAULT 0,
  src_device_id  TEXT,
  src_device_name TEXT,
  produced_by    TEXT    NOT NULL,
  state          TEXT    NOT NULL DEFAULT 'cutting',
  missing        INTEGER NOT NULL DEFAULT 0,
  added_at       INTEGER NOT NULL,
  last_seen_scan INTEGER
);
```

#### `segment` — the retrieval unit; its grain is **the producer's chunk, not a fixed grid**

⚠ **This section was wrong in its first draft and the error mattered.** It declared a fixed
**5 s window** while §4.3 writes **one row per ASR chunk** — and the real chunks are **3.96 /
5.08 / 6.96 / 6.98 / 8.06 / 8.08 / 13.76 / 13.82 s**, **none of them 5.00 s and none
grid-aligned** (MEASURED on the registered clip). A schema whose declared grain contradicts
its own write path is unimplementable: the implementer must pick one and will pick silently.

**The decision: `segment` carries whatever the producing pass emits, and there is NO fixed grid
in the schema.** Reasons, in order of weight:

1. the ASR is **silence-aligned** by law (`specs/02 §3`): a fixed grid collapses its text to
   ratio **0.229** against the oracle. Any scheme that re-cuts the speech to hit 5 s boundaries
   re-introduces the exact defect `specs/02` was written to prevent;
2. chunks **overlap** by 0.20 s (§7), so a fixed grid cannot even be assigned without
   duplicating or dropping ~4 % of every clip's speech;
3. `UNIQUE(video_id, start_ms)` and the whole idempotence story depend on the writer's own
   boundaries, not on an invented one.

`window_ms` in `meta` (§1.2) is therefore a **planning average for the embedding pass**, which
*is* ours to choose — never a schema invariant, and never a claim about a `segment`.

| column | type | null | why |
|---|---|---|---|
| `seg_id` | `INTEGER PRIMARY KEY` | no | surrogate |
| `video_id` | `INTEGER NOT NULL REFERENCES video(id)` | no | a segment with no video cannot be opened, and that is a defect not a state |
| `start_ms`, `end_ms` | `INTEGER NOT NULL` | no | **milliseconds, relative to the video's start.** The timestamp belongs to the segment, not the video — a hit is a window (`research 07 §2`) |
| `n_visual`, `n_speech`, `n_ocr` | `INTEGER NOT NULL DEFAULT 0` | no | cheap "which channels exist for this window", so the gallery can grey out a channel without three `COUNT`s |
| `state` | `TEXT NOT NULL DEFAULT 'new'` | no | §6.1 |
| — | **`UNIQUE(video_id, start_ms)`** | — | ⚙ **the idempotence key of the whole write path.** Re-running the ASR over the same clip must land on the SAME row, not create a twin and orphan the old transcript (§2.4). ⚠ **it can MERGE**, if two passes disagree on a `start_ms` for the same video — counted as `segments_collided` (§6.3), never silent |

```sql
CREATE TABLE segment(
  seg_id   INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES video(id),
  start_ms INTEGER NOT NULL,
  end_ms   INTEGER NOT NULL,
  n_visual INTEGER NOT NULL DEFAULT 0,
  n_speech INTEGER NOT NULL DEFAULT 0,
  n_ocr    INTEGER NOT NULL DEFAULT 0,
  state    TEXT    NOT NULL DEFAULT 'new',
  UNIQUE(video_id, start_ms)
);
CREATE INDEX segment_video ON segment(video_id, start_ms);   -- research 07 §2
CREATE INDEX segment_state ON segment(state);                 -- reconciliation scan, 8.667 ms @120 201 rows
```

#### `transcript` — exactly one row per segment that the ASR produced

| column | type | null | why |
|---|---|---|---|
| `seg_id` | `INTEGER PRIMARY KEY REFERENCES segment(seg_id)` | no | **1:1**; re-transcription replaces, it never appends |
| `start_ms`, `end_ms` | `INTEGER NOT NULL` | no | denormalised from `segment` so the lexical JOIN is one hop, not two |
| `text` | `TEXT NOT NULL` | no | ⚠ **may legitimately be `''`.** The runner does `texts.append(text or "")` and `chars = len(text or "")` (`src/asr/runner.py` `texts.append(text or "")` (runner.py:230) and `row = {` (runner.py:231-239)), so an empty recognition is a **real row with 0 chars**, not a missing one. NULL would be the lie; `''` is the truth |
| `text_norm` | `TEXT NOT NULL` | no | the column FTS5 indexes. Definition in §1.4 |
| `producer` | `TEXT NOT NULL` | no | ⚠ **the ASR does NOT emit this** — measured: the union of the `done` object's keys is 34 and none is `producer` (§7). **The index synthesises it** from the TEMPLATE in §5 #27 — **never a literal**, or a row written at `--threads 2` claims `intra=4` |
| `model_sha256` | `TEXT NOT NULL` | no | ⚠ **likewise not emitted.** `engine.verify_model_dir` checks **sizes only** (`src/asr/engine.py:90-111`, `def verify_model_dir`), so the runner cannot report a hash it never computed. The index takes it from `asr.constants.MODEL_FILE_SHA256` |
| `n_chars` | `INTEGER NOT NULL` | no | `done.segments[i].chars`, denormalised so a result list needs no join |
| `asr_wall_s`, `asr_rtfx` | `REAL` | **yes** | from `done.segments[i].wall_s` and `done.rtfx_steady`. NULL only for a row written by something that is not the ASR |

```sql
CREATE TABLE transcript(
  seg_id       INTEGER PRIMARY KEY REFERENCES segment(seg_id),
  start_ms     INTEGER NOT NULL,
  end_ms       INTEGER NOT NULL,
  text         TEXT    NOT NULL,
  text_norm    TEXT    NOT NULL,
  producer     TEXT    NOT NULL,
  model_sha256 TEXT    NOT NULL,
  n_chars      INTEGER NOT NULL,
  asr_wall_s   REAL,
  asr_rtfx     REAL
);
CREATE INDEX transcript_seg ON transcript(seg_id);   -- research 07 §2
```

#### `ocr` — lane 02's request list, verbatim

`research 07 §2` fixes these columns; they are reproduced unchanged, and only the type and
the nullability are made explicit.

| column | type | null | why |
|---|---|---|---|
| `seg_id` | `INTEGER NOT NULL REFERENCES segment(seg_id)` | no | |
| `line_no` | `INTEGER NOT NULL` | no | the line's order within the window; 0-based |
| `t_ms`, `t_end_ms` | `INTEGER NOT NULL` | no | ⚠ **relative to the SEGMENT**, not the video — an OCR line lives inside one 5 s window, and `research 07 §2`'s comment names the column pair verbatim |
| `text_raw` | `TEXT NOT NULL` | no | as the engine read it |
| `text_norm` | `TEXT NOT NULL` | no | FTS5's column |
| `box` | `TEXT` | **yes** | JSON array `[x,y,w,h]` in segment-local pixels. NULL when the engine reports no box |
| `conf` | `REAL` | **yes** | NULL when the engine reports no confidence |
| `engine` | `TEXT NOT NULL` | no | which OCR produced it |
| `model_sha256` | `TEXT NOT NULL` | no | which weights |
| `frame_ref` | `TEXT` | **yes** | a **pointer into the thumbs cache**, never a frame in the store — law 4: never store frames |

```sql
CREATE TABLE ocr(
  seg_id INTEGER NOT NULL REFERENCES segment(seg_id),
  line_no INTEGER NOT NULL,
  t_ms INTEGER NOT NULL, t_end_ms INTEGER NOT NULL,
  text_raw TEXT NOT NULL, text_norm TEXT NOT NULL,
  box TEXT, conf REAL,
  engine TEXT NOT NULL, model_sha256 TEXT NOT NULL,
  frame_ref TEXT,
  PRIMARY KEY(seg_id, line_no)
);
CREATE INDEX ocr_seg ON ocr(seg_id);   -- research 07 §2
```

#### `embedding` — the vectors, and the primary key IS the work unit

| column | type | null | why |
|---|---|---|---|
| `seg_id` | `INTEGER NOT NULL REFERENCES segment(seg_id)` | no | |
| `channel` | `TEXT NOT NULL` | no | `CHECK (channel IN ('speech','ocr','visual'))` ⚙ — the three provenance channels are constitutional (`research 07 §3`) and a fourth value must be a schema error, not a silent fourth space |
| `dim` | `INTEGER NOT NULL` | no | 256 ⚙ (see §5) |
| `dtype` | `TEXT NOT NULL` | no | `CHECK (dtype IN ('float16','float32'))`; the shipped value is **`float16`** — a **disk** decision, never a compute one (`research 07 §1`) |
| `vec` | `BLOB NOT NULL` | no | `dim * 2` bytes for fp16, little-endian. **CHECKed by the writer**, because a short blob is a silent recall loss that no query will ever explain |
| `model`, `model_sha256` | `TEXT NOT NULL` | no | which weights produced it — the promotion rule keys on this (`research 07 §5`) |
| `built_at` | `INTEGER NOT NULL` | no | unix seconds |
| — | **`PRIMARY KEY (seg_id, channel)`** | — | ⚙ **this IS the work unit**: the same channel with the same model is `INSERT OR IGNORE` (a measured no-op); with a different model it is `INSERT OR REPLACE`, and the change is **detectable per row, never a silent mix** (`research 07 §5`) |

```sql
CREATE TABLE embedding(
  seg_id INTEGER NOT NULL REFERENCES segment(seg_id),
  channel TEXT NOT NULL CHECK(channel IN ('speech','ocr','visual')),
  dim INTEGER NOT NULL,
  dtype TEXT NOT NULL CHECK(dtype IN ('float16','float32')),
  vec BLOB NOT NULL,
  model TEXT NOT NULL, model_sha256 TEXT NOT NULL, built_at INTEGER NOT NULL,
  PRIMARY KEY(seg_id, channel)
);
CREATE INDEX embedding_channel ON embedding(channel);   -- research 07 §2
```

#### `marker` — a user or engine label on a window

`(seg_id, kind, value, source)` in `research 07 §2`, with the key made explicit:

| column | type | null | why |
|---|---|---|---|
| `seg_id` | `INTEGER NOT NULL REFERENCES segment(seg_id)` | no | |
| `kind` | `TEXT NOT NULL` | no | `highlight` \| `bookmark` \| `refused` … |
| `value` | `TEXT NOT NULL` | no | |
| `source` | `TEXT NOT NULL` | no | **who** wrote it — `user` and `engine` must be able to hold opposite claims about the same window |
| — | **`PRIMARY KEY (seg_id, kind, source)`** ⚙ | — | two sources are two rows (a user's `bookmark` is not overwritten by an engine's), and a re-run is idempotent via `INSERT OR REPLACE` |

```sql
CREATE TABLE marker(
  seg_id INTEGER NOT NULL REFERENCES segment(seg_id),
  kind TEXT NOT NULL, value TEXT NOT NULL, source TEXT NOT NULL,
  PRIMARY KEY(seg_id, kind, source)
);
```

#### `meta` — ⚙ ADDED BY THIS SPEC, and it is not optional

`research 07 §2` has six tables. **This spec adds a seventh, `meta`,** and the reason is this
spec's own acceptance criterion: *a later reader must be able to check conformance.* A store
whose parameters live only in code cannot be audited without the code that made it, and this
project's most expensive lesson is precisely that an unverifiable claim is not a claim
(`AGENTS.md`, verification rule). One row, `k = 1`, upserted at open:

| key | value | why |
|---|---|---|
| `schema_version` | `1` | ⚙ the number this spec defines. A future `2` must migrate, not guess |
| `created_at` / `app_version` | unix s / string | which build wrote this store |
| `search_mode` | **`fts5`** \| **`like`** | which lexical surface this store was built with (§1.4) |
| `tokenizer` | **`unicode61 remove_diacritics 2`** | so a store is never queried with a tokenizer it was not built with |
| `rrf_weights` | JSON `{"speech":1.0,"ocr":1.0,"visual":0.7,"lexical":1.0}` | the fusion is data, not a constant in a function |
| `rrf_k` | `100` | per list (`research 07 §3`) |
| `rrf_const` | `60` | RRF's constant; stated so a later reader can recompute a score by hand |
| `window_ms` | `5000` | the segment granularity the corpus arithmetic assumes (`research 07 §6`) |
| `asr_model_sha256` | the encoder/decoder sha | what this store's transcripts were produced by |

```sql
CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
```

### 1.3 THE TWO OFFSETS — never conflate them

There are **two different offsets** in this pipeline and mixing them is the most likely way to
build an index whose timestamps are subtly wrong everywhere:

| quantity | meaning | MEASURED example |
|---|---|---|
| `video.audio_offset_ms` | where the **wav's `t=0`** sits inside the video's timeline | `0` for a clip whose audio covers the whole clip |
| `done.offset_s` | where the **slice** sits inside the **wav** (`--offset-s`) | `900` on the registered slice |

And a third fact that decides the mapping: **the ASR's `segments[].start` is ABSOLUTE within
the wav, not relative to the slice** (`src/asr/runner.py:233` — `"start": round(cfg.offset_s + a, 3)"`).
MEASURED: `offset_s = 900`, `segments[0].start = 914.32`.

> **The conversion, normative:**
> `segment.start_ms = video.audio_offset_ms + round(done.segments[i].start * 1000)`
> `segment.end_ms   = video.audio_offset_ms + round(done.segments[i].end   * 1000)`
> `done.offset_s` is **not** subtracted again — it was already added by the runner.

### 1.4 THE LEXICAL SURFACE — **FTS5**, decided

**Decision: SQLite FTS5, external-content, `tokenize='unicode61 remove_diacritics 2'`.**
There is no fallback in the sense of "try FTS5 and hope"; there is a **declared** alternative
recorded in `meta.search_mode`, and §6.4 says what happens when it is in force.

| question | answer | evidence |
|---|---|---|
| is FTS5 even available here? | **YES.** SQLite **3.43.1**, `ENABLE_FTS5` in `pragma compile_options`, `fts5` in `pragma_module_list()` | **MEASURED** `_main/lane-spec04-fts5-avail.log` |
| which tokenizers construct? | `unicode61` (± `remove_diacritics 0/1/2`) ✅ · `porter unicode61 remove_diacritics 2` ✅ · `trigram` ✅ · **`ascii` + `remove_diacritics` ❌ `error in tokenizer constructor`** | **MEASURED** `_main/lane-spec04-fts5-tok.log` — so **never** write `ascii remove_diacritics 2`; it does not construct |
| why `unicode61 remove_diacritics 2`? | **2** = full Unicode case-fold + diacritic removal; MEASURED, `acesso` matches `ACESSO NEGADO`, `acesso negado` **and** `Acesso à Negado` | **MEASURED** `_main/lane-spec04-fts5-tok.log` |
| why external-content, not contentless? | `content='transcript'` keeps the base table the single source of truth and lets the FTS index be **rebuilt from it** with `'rebuild'`. A contentless table cannot be rebuilt — and the failure this spec exists to prevent is a row that exists and cannot be found | ⚙ `research 07 §1`'s crash result + §2.5 |
| what does it cost? | **+3.75 MiB** on a 28.32 MiB store (**32.07 MiB** total for 120 201 segments / 72 200 transcripts / 19 200 OCR lines) — **+13.2 %** | **MEASURED** `_main/lane-spec04-index-cost.log` |
| does it slow the light write? | median **0.0458 ms** with FTS5 vs **0.0448 ms** without = **1.02×**; p95 **0.1670 ms** vs **0.0892 ms** = **1.87×**. Free on the median, visible on the tail | **MEASURED** same log |

```sql
CREATE VIRTUAL TABLE transcript_fts USING fts5(
  text_norm, content='transcript', content_rowid='seg_id',
  tokenize='unicode61 remove_diacritics 2');
CREATE VIRTUAL TABLE ocr_fts USING fts5(
  text_norm, content='ocr', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2');

-- SIX triggers, and they are NOT optional. MEASURED: with these absent, `trigger count = 0`
-- and the lexical surface stays permanently EMPTY -- every MATCH returns no rows while the
-- transcript is plainly in the table. That is the silent failure §6 forbids, shipped by
-- omission. The 'delete' form on update/delete is what stops a re-transcription leaving the
-- OLD text searchable forever.
CREATE TRIGGER transcript_ai AFTER INSERT ON transcript BEGIN
  INSERT INTO transcript_fts(rowid, text_norm) VALUES (new.seg_id, new.text_norm);
END;
CREATE TRIGGER transcript_ad AFTER DELETE ON transcript BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text_norm)
  VALUES('delete', old.seg_id, old.text_norm);
END;
CREATE TRIGGER transcript_au AFTER UPDATE ON transcript BEGIN
  INSERT INTO transcript_fts(transcript_fts, rowid, text_norm)
  VALUES('delete', old.seg_id, old.text_norm);
  INSERT INTO transcript_fts(rowid, text_norm) VALUES (new.seg_id, new.text_norm);
END;
CREATE TRIGGER ocr_ai AFTER INSERT ON ocr BEGIN
  INSERT INTO ocr_fts(rowid, text_norm) VALUES (new.rowid, new.text_norm);
END;
CREATE TRIGGER ocr_ad AFTER DELETE ON ocr BEGIN
  INSERT INTO ocr_fts(ocr_fts, rowid, text_norm)
  VALUES('delete', old.rowid, old.text_norm);
END;
CREATE TRIGGER ocr_au AFTER UPDATE ON ocr BEGIN
  INSERT INTO ocr_fts(ocr_fts, rowid, text_norm)
  VALUES('delete', old.rowid, old.text_norm);
  INSERT INTO ocr_fts(rowid, text_norm) VALUES (new.rowid, new.text_norm);
END;
```

⚠ **`ocr` is a composite-PK table and therefore still has a `rowid`** (it is not declared
`WITHOUT ROWID`), so `content_rowid='rowid'` and `new.rowid` are correct — **MEASURED**:
`INSERT INTO ocr_fts(ocr_fts) VALUES('rebuild')` over a populated `ocr` returns **1 row**, and
`INSERT INTO transcript_fts(transcript_fts) VALUES('rebuild')` returns **1 row** on this
schema. Both rebuild commands (§2.5's repair) are **verified working**.

### 1.5 ⚠ THE MATCH-PARSING RULE — an unquoted query is a CRASH, not a miss

**This is the single most important line in the spec for a Portuguese-language product.**

An FTS5 `MATCH` string is **not a string literal**. Unquoted punctuation is query syntax, so a
hyphenated word is parsed as *phrase minus column* and **RAISES**:

```
'segunda-feira'   -> RAISED  OperationalError: no such column: feira
'"segunda-feira"' -> OK  3 rows
'segunda'         -> OK  3 rows
```

**MEASURED** — and not on synthetic text: the query was run against **the product's own
registered ASR output** (`lane-spec04-fts5-realtext.log`), whose first segment is *"O rádio
anunciou que a ponte sobre o rio vai ser interditada na próxima **segunda-feira**."* `r-adio`
likewise raises `no such column: adio`.

**Normative rule:**

1. **The query string is escaped, never interpolated raw.** `MATCH` is the one place in this
   store where a user keystroke becomes syntax. **The rule, precisely:**

   | input shape | emit | why |
   |---|---|---|
   | a bare term | `"<term with " doubled>"` | a quoted string is a literal phrase; `segunda-feira` inside quotes is **one** token sequence, not `segunda` minus column `feira` |
   | a term ending in `*` | `"<term without the star>"*` — i.e. **the prefix operator goes OUTSIDE the quotes** | ⚠ **wrapping `acess*` in quotes yields the literal phrase `acess*`, silently destroying prefix search** — the exact "looks like a miss, is really a bug" failure this section exists to prevent. MEASURED: `acess*` unquoted matches `ACESSO NEGADO`; the quoted form matches nothing |
   | a bare `*`, or any operator the escaper cannot prove | **refuse with `QUERY_MALFORMED`** (§6.3) | never guess a user's syntax |

   A stricter implementation may tokenise on whitespace and join the terms with `OR`. **MEASURED
   control:** an escaper built on the quoted-term rule survived a 32-query attack set without
   raising — but that attack set did **not** include a trailing `*`, which is why the row above
   exists.
2. **A query that still fails to parse is reported as `QUERY_MALFORMED`, not swallowed and
   not shown as "no results"** (§6.3). An empty result and a crash are different facts, and
   the UI must be able to tell them apart.
3. What is safe, MEASURED on the real text: single tokens (`segunda`), phrases
   (`"ponte"`, `"acesso negado"`), prefixes (`acess*`), exact hex codes
   (`0x80070005`, byte-exact — this is the case `research 07 §3` requires of OCR), and `OR`
   (`segunda OR ponte`).

### 1.6 THE FALLBACK, named and loud

If `ENABLE_FTS5` is absent — it is **present on this box** (`lane-spec04-fts5-avail.log`),
but the store must survive a rebuild on a Python without it — then:

- the store is created with `meta.search_mode = 'like'`;
- the lexical surface becomes `LIKE '%term%'` over `text_norm`, which is a **full scan**, and
- the UI **says so, once, in the same words** as §6.5's `SEARCH_DEGRADED`.

A `LIKE` fallback is **not** a silent degradation: the alternative — a search box that answers
in 14 ms on this build and 40 s on the next one — is the silent failure the project forbids
(law 6, and `AGENTS.md`'s house rule: *a failure must never answer as success*).

---

## 2. THE WRITE PATH

### 2.1 THE ORDER — the anchor is written BEFORE the file

**The failure this whole section exists to prevent: the clip exists on disk and is
unfindable.** It happens the moment the process dies between writing the file and writing the
row. So the row comes first:

| # | step | transaction | state after | law |
|---|---|---|---|---|
| **T0** | `INSERT INTO video(clip_uuid, path, produced_by, state='cutting', added_at) …` | **own commit** | the clip is **visible and findable before it exists** | §2.5 |
| **T1** | remux the ring into `path + '.part'`; `flush` + `fsync`; atomic `rename` onto `path` | — | the file exists, complete or absent — never partial | `specs/03 §2.7` |
| **T2** | `UPDATE video SET state='clipped', size_bytes, duration_ms, w, h, fps, codec, mode, src_device_* …` | **own commit** | the clip is browsable with real metadata | `specs/01 §4` S2 |
| **T3** | thumbnail + poster; `UPDATE video SET poster=…` | own commit | §2.6 |
| **T4** | ASR over `audio_wav`; **all** rows + all FTS rows in **ONE** transaction (§2.4) | one commit | the transcript is searchable | `specs/02` |
| **T5** | embedding vectors; `INSERT OR IGNORE` / `INSERT OR REPLACE` | batched (§5) | the window is semantically searchable | `research 07 §5` |

**Why the row first and not the file first.** The two states are not symmetric:

- a **row with no file** is *recoverable* — §2.5 finds `state='cutting'`, looks for the file,
  and either promotes it or marks it `cut-failed` with a reason;
- a **file with no row** is *invisible forever*. Nothing in this product scans the video
  folder on its own initiative for strays, and the whole design (`research 08`: *the index is
  the database; the folder is only an input*) says a scan is an explicit act.

So the ordering is not a preference. It is the only one of the two orders whose failure is
detectable.

### 2.2 `content_key` IS FILLED LATER, AND THAT IS FINE

`content_key` is NULL at T0–T2 and is computed by the hash pass, which
`research 08` makes **a by-product of a pass that already reads the bytes** (SHA-256 is
**882.6 MB/s** warm, MEASURED `receipt-08 §1`; a separate hash pass would be 5.8 min of CPU
against 1–4 h of drive — the most expensive way to learn nothing). The consequence is
normative: **a brand-new clip is not yet de-duplicated**, and the index must not pretend
otherwise. Two clips of the same instant cut twice are two rows until the hash pass runs.

### 2.3 THE LIGHT COMMIT — the write budget

One closed 5 s window is **one transaction**: its `segment` row, its `transcript` row, and
(through the trigger) its FTS row.

| | MEASURED (n = 200 commits, 120 k-segment store) |
|---|---|
| min | **0.0360 ms** |
| **median** | **0.0458 ms** |
| **p95** | **0.1670 ms** |
| max | **18.1258 ms** ← the outlier is the file's own fsync, and it is **reported, not averaged away** |

`research 07 §5` measured the same shape at **0.061 ms median / 0.198 ms p95** on a store
**with no FTS5**; this spec's store has it, which is why the number above is the one the
budget uses.

**Budget: the light commit is ≤ 1 ms at p95.** It is met with a **1000× margin** at this
corpus size, and the margin is the point: `specs/01 §5` puts the light pass at tier 3, below
"CLIP SAVE + APPEARANCE", and a write that took 40 ms would start to matter to the capture
process's disk. ⚠ **the p95 is over a store of 120 201 segments; SQLite write cost grows with
the WAL and the B-tree depth, so re-measure at 10× the corpus before quoting this at scale.**
**UNKNOWN: the light-commit latency at 1.2 M segments.**

### 2.4 THE TRANSCRIPT WRITE — one transaction, idempotent, FTS included

The whole ASR result is **one** transaction, never one-per-segment:

- `research 08` states the rule this inherits: *the payload and the `done` row commit in the
  same transaction, so a power-off can never leave "transcript written, job still pending"
  (double work) nor "job done, no transcript" (a silent hole).* A partially-transcribed clip
  that claims to be complete is the same defect one level down, so **one commit for all N
  segments**.
- **Idempotence** comes from `segment.UNIQUE(video_id, start_ms)`: re-running the ASR
  overwrites the same rows. Write with
  `INSERT INTO segment(…) VALUES(…) ON CONFLICT(video_id,start_ms) DO UPDATE SET … RETURNING seg_id`
  (SQLite ≥ 3.35; this box is **3.43.1**), then:

  | the upsert returned | do this to `transcript` | **never** |
  |---|---|---|
  | a **new** `seg_id` | `INSERT` (no conflict possible) | |
  | an **existing** `seg_id` | `UPDATE … WHERE seg_id = ?` | ⚠ **`INSERT OR REPLACE`** |

  **`INSERT OR REPLACE` is FORBIDDEN on `transcript` and `ocr`,** and the reason is measured,
  not stylistic: REPLACE is `DELETE` + `INSERT`, and with `recursive_triggers` OFF — SQLite's
  default — the **`AFTER DELETE` trigger does not fire**, so the superseded text stays in the
  FTS index permanently while `fts_orphans` remains **0** and §2.5's reconciliation cannot
  see it. That is silent recall loss, and the wrong-MATCH control below confirms the store is
  not even corrupt (`integrity-check` clean), so nothing else will ever report it. §1.1 sets
  `recursive_triggers=ON` as the second line of defence; the rule above is the first.
- **The `transcript` row and its FTS row are the same commit** because the trigger is inside
  the transaction. There is no ordering to get wrong and no window in which the text exists in
  one surface and not the other — MEASURED: `transcripts_absent_from_fts = 0` across 72 200
  rows after the run, and **MEASURED again at row level**: the §1.4 triggers put the new text
  in `transcript_fts` inside the same `execute`, and the `'delete'` form on update keeps the old
  text from surviving a re-transcription.
- ⚠ **`ON CONFLICT` merges silently** when two producers disagree about a `start_ms`. That is
  counted, never hidden: `segments_collided` in §6.3.

### 2.5 RECONCILIATION — closing the gap, on a measured budget

Two scans, both measured on the 120 k-segment corpus:

| scan | cost | MEASURED |
|---|---|---|
| which clips are not finished | `SELECT count(*) FROM segment WHERE state != 'indexed'` | **8.667 ms** @ 120 201 rows |
| does the lexical surface cover every transcript | `… WHERE NOT EXISTS (SELECT 1 FROM transcript_fts f WHERE f.rowid = t.seg_id)` | **55.584 ms** @ 72 200 rows |

**Cadence:** the `state` scan at **every engine start** and every **60 s**; the FTS-coverage
scan at **every engine start** only (it is 7× dearer and the triggers make a divergence nearly
impossible). The value of running the FTS scan **once at startup** and *logging the count* is
that a store built by an older build, or by a writer that bypassed the triggers, is caught
before the owner searches for something he already recorded — with
`INSERT INTO transcript_fts(transcript_fts) VALUES('rebuild')` as the repair (**MEASURED: that
exact command returns 1 row on this schema**, and `ocr_fts` likewise).

**The repair ladder for `state = 'cutting'` rows**, in order — never delete:

1. the file exists and is ≥ 1 byte → run T2 (the metadata is cheap: `ffprobe` header is
   **0.0425 s**, `receipt-08 §1`) → `state='clipped'`;
2. the file exists but is 0 bytes or `.part` only → delete the partial, `state='cut-failed'`,
   **count it** (§6.4);
3. the file is absent → `state='cut-failed'` **with the reason**, never a silent drop.

**`missing = 1` is a state, never a delete.** A scan that does not see the file sets it and
keeps every transcript and vector searchable; the KNN drops `missing=1` rows with the same
free mask as any other filter, and the UI says the file is gone. **Never delete embeddings on
a path miss** — and note that this is exactly what an HNSW index cannot do: faiss's
`remove_ids` **RAISES `RuntimeError: remove_ids not implemented`** (MEASURED, `receipt-07 §4`).

---

## 3. THE READ PATH

### 3.1 THE QUERY SURFACE — one entry point

```python
def search(q: SearchQuery) -> SearchResult
```

```python
@dataclass(frozen=True)
class SearchQuery:
    text: str = ""                       # "" => the vector lists only
    channels: tuple[str, ...] = ("speech", "ocr", "visual", "lexical")
    video_id: int | None = None          # §3.3
    src_device_id: str | None = None     # §3.3
    t0_ms: int | None = None             # within ONE video -- §3.2
    t1_ms: int | None = None
    min_duration_ms: int | None = None   # clip duration -- §3.3
    max_duration_ms: int | None = None
    added_since: int | None = None       # unix seconds
    order: str = "recent"                # "recent" | "relevance" | "earliest"
    limit: int = 50                      # HARD cap 200
    cursor: tuple[int, int, int] | None = None   # keyset, §3.5
```

```python
@dataclass(frozen=True)
class Hit:
    video_id: int; seg_id: int; path: str; start_ms: int
    score: float                         # the RRF score, §3.4
    channels: tuple[str, ...]            # which lists produced it -- the UI chips
    per_channel: dict[str, dict]         # {"speech": {"rank": 3, "cosine": 0.71}, …}
    text: str | None                     # the speech text, when present
    missing: bool                        # the file is gone; the row is not
```

`SearchResult` adds `hits`, `total_estimate` (⚠ **an estimate, labelled as one** — an exact
`COUNT` over a fused RRF result is not a thing), `elapsed_ms` per stage, and `mode`.

### 3.2 THE TEMPORAL FILTER IS PER-VIDEO — a bare range is meaningless

`start_ms` is relative to **each video's own start**. A global `start_ms BETWEEN` across the
library would mix video 1's first minute with video 900's last. MEASURED control: window
`(42, 0, 60 s)` → **10/10** hits in video 42 under 60 s; window `(42, 60–65 s)` → **exactly 1**
hit (`research 07 §3`). **So `t0_ms`/`t1_ms` REQUIRE `video_id`**; the index raises
`QueryError` otherwise rather than returning a plausible wrong answer.

**The window filter is free in time** — 67.98 ms vs 72.57 ms unfiltered, because the mask runs
*after* the scan (`research 07 §3`). ⚠ **to make a window genuinely cheap, slice the array by
video first** (one 10-min video = 120 rows). **UNKNOWN: that saving — unmeasured.**

### 3.3 FILTERS

| filter | column | notes |
|---|---|---|
| time within a video | `segment.start_ms` | requires `video_id`, §3.2 |
| **device** | `video.src_device_id` | ⚙ **added by this spec.** `research 07 §2`'s schema has no device column, so "filter by device" was **unanswerable**; the audio endpoint id is free to read (**MEASURED** 22 µs, zero bytes, `receipt-08 §3`) and the capture device is known at cut time |
| duration | **`video.duration_ms`** | ⚠ the **clip's** duration, not the segment's. A segment's duration is ~`window_ms` for every row, so a segment-duration filter selects almost nothing — a real trap, and the reason this row names which table |
| added since | `video.added_at` | unix seconds |
| missing | `video.missing` | defaults to **excluding** `missing=1` from the vector lists; the row survives (§2.5) |
| channel | `embedding.channel` | `CHECK`-constrained to the three |

### 3.4 FUSION — **RRF, four lists, k = 100 each**

`score(seg) = Σ_c w_c / (60 + rank_c(seg))`, with **`w = {speech 1.0, ocr 1.0, visual 0.7, lexical 1.0}`** and `k = 100` per list.

- the three weights `{speech 1.0, ocr 1.0, visual 0.7}` are **`research 07 §3`'s**, measured
  and inherited unchanged;
- **`lexical 1.0` is ⚙ DECIDED HERE** (`research 07 §7.6` left it UNKNOWN). Reason: RRF's
  only input is **rank**, because the four lists live in incomparable scales — that is the
  whole reason RRF was chosen. A weight is therefore a statement about *how much a list's top
  hits should be believed*, not about its scores. Lexical is the **required baseline** for OCR
  (`research 07 §3`: game tokens like `ERRO 0x80070005: ACESSO NEGADO` come back byte-exact,
  MEASURED) and it is exact where the vector lists are approximate, so it sits **level with
  the two text channels** and above `visual 0.7`, which is the weakest channel on the model's
  own card (**video 50.67** vs image 57.28, `receipt-06 §5`). **What would reopen it:** the
  weight is a one-line change in `meta.rrf_weights`, and the experiment that settles it is
  A/B the fused top-10 with `w_lexical ∈ {0.5, 1.0, 2.0}` over 20 hand-labelled queries.
- `60` is RRF's constant (`research 07 §3`), stored in `meta.rrf_const` so a score can be
  recomputed by hand.

**Every hit names the channels that produced it.** MEASURED control: all 10 hits name ≥ 1
channel, all three channels appear in the top-10, and **10/10 were matched by more than one
channel** (`research 07 §3`). The lexical list's contribution to that control is **UNKNOWN** —
this spec does not claim 4-channel agreement.

### 3.5 ORDERING AND PAGINATION

| `order` | key | for |
|---|---|---|
| `recent` **(default)** | `added_at DESC, video_id DESC, start_ms DESC` | the gallery — the common case, and the only one on the critical path of "I just recorded this" |
| `relevance` | `score DESC, start_ms ASC` | only when `text` is non-empty; **undefined (and refused) otherwise**, because an empty query has no relevance order |
| `earliest` | `added_at ASC, video_id ASC, start_ms ASC` | "find me that thing from eight minutes ago" (`specs/01 §1`, desktop mode's whole reason to exist) |

**Pagination is keyset, never `OFFSET`.** `OFFSET n` re-walks `n` rows; at 120 k segments the
cost grows with the library, and a gallery that gets slower as the library grows is a defect.
The cursor is the tuple `(added_at, video_id, start_ms)`. ⚙ **`OFFSET` is permitted only for
`offset ≤ 1000`** and is documented as the escape hatch for a UI that cannot hold a cursor.

### 3.6 THE LATENCY BUDGET — every number MEASURED, 2 threads

| operation | budget | MEASURED | source |
|---|---|---|---|
| vector scan, `k=100`, 211 200 vectors (three channels) | **≤ 25 ms** | **15.99 ms min / 20.3 ms median** (13.5 GB/s) | `research 07 §1` |
| full fused query → 10 explainable hits | **≤ 150 ms** | **72.6 ms min / 83.2 ms median** | `research 07 §3` |
| lexical only, `k=100`, 72 200 transcripts | **≤ 30 ms** | **14.583 ms median** (14.011 / 16.988) | **MEASURED** `lane-spec04-index-cost.log` |
| lexical one token, `k=10` | — | **12.740 ms** · prefix `acess*` **12.755 ms** · hex `0x80070005` **12.583 ms** · phrase `"acesso negado"` **15.693 ms** | **MEASURED** same |
| **the full answer path** (FTS5 + `transcript` + `segment` + `video`, `k=10`) | **≤ 60 ms** | **37.572 ms**, returning `clip_0130.mp4 @ 15.000 s` and the real text | **MEASURED** same |
| gallery page (20 rows, no vectors) | **≤ 20 ms** | ⚙ derived from the answer-path measurement, not separately measured | — |
| engine start: load the fp16 matrix into RAM | **≤ 2 s** | **0.99 s** for 211 200 vectors end to end from SQLite | `research 07 §6` |
| engine start: reconciliation (§2.5) | **≤ 100 ms** | **8.667 ms + 55.584 ms** | **MEASURED** `lane-spec04-index-cost.log` |
| light commit (§2.3) | **≤ 1 ms** p95 | **0.0458 ms median / 0.1670 ms p95** | **MEASURED** same |

⚠ **These are 2-thread numbers** (law 8, and `research 07`'s own budget). The product's engine
wants 4 (`specs/02 §2`), so the scan **should** be ~2× faster — but **UNKNOWN: no fused query
has been measured at 4 threads.** Quote the 2-thread figure in any receipt; do not quote the
hope.

⚠ **The crossover is stated so nobody re-derives it wrongly:** brute force hits **50 ms at
N ≈ 582 000** and 250 ms at N ≈ 2.77 M, because the scan is bandwidth-bound and linear
(`research 07 §1`). At the product's own 211 k that is **2.7× headroom**. An ANN index is
justified past ~1 M vectors — and it would cost the ability to delete a row, which this
product needs (§2.5).

---

## 4. THE INTERFACES

These are the three seams the rest of the fleet codes against. They are **exact**.

### 4.1 L1 — INSTANT CUT (capture) → index

The capture process emits **one NDJSON object on stdout** when a clip is written (`specs/03`,
and `ROADMAP §P0.3`: JSON Lines over stdio, the bridge already hardened in production).

```json
{"type":"clip","clip_uuid":"<16 hex>","path":"H:\\clips\\clip_0644.mp4",
 "produced_by":"capture-cut","mode":"gaming","codec":"H.264","fps":60.0,
 "w":1920,"h":1080,"clip_seconds":120.0,"bytes":675000000,"frames_in_clip":7200,
 "base_qpc_ns":123456789012345,"cut_qpc_ns":123456789012345+120000000000,
 "ring_dropped_at_cut":0,"idr_pre_roll_ms":340.0,"wall_ms":412.7,
 "src_device_id":"...","src_device_name":"...","ok":true,"note":""}
```

**Field provenance — read this before coding against it.** MEASURED over `src/capture/*.{h,cpp}`:

| field | status |
|---|---|
| `clip_seconds`, `bytes`, `frames_in_clip`, `base_qpc_ns`, `cut_qpc_ns`, `ring_dropped_at_cut`, `idr_pre_roll_ms`, `wall_ms`, `ok`, `note` | ✅ **exist verbatim** in `CutResult`, `src/capture/replay.h:59-76` — MEASURED, and `frames_in_clip` keeps its own name (an earlier draft of this spec renamed it to `frames`; that was wrong and is corrected here) |
| `w`, `h`, `fps`, `mode`, `codec` | ✅ **exist** via `Replay::width()/height()/cfg()`/`armed_codec()` (`replay.h:97-106`) |
| **`clip_uuid`** | ⚠ **DOES NOT EXIST anywhere in `src/capture/`.** It is a **required addition to lane 03's wire event**: the cut thread mints 8 random bytes and hex-encodes them at T0. ⚠ **It cannot be derived index-side from `path`** — the path changes on a move, and §2.5's recovery anchor must survive that |
| **`produced_by`** | ⚠ **DOES NOT EXIST.** Constant `'capture-cut'` for this producer; the index may default it, but the **field is required** so a future producer (import, copy) is distinguishable without a code change |
| **`src_device_id`, `src_device_name`** | ⚠ **DO NOT EXIST in the capture struct.** L2 owns the audio endpoint; **the capture-side seam must carry them from L2's `attach_audio` (§4.2)**, not from the cut event. ⚠ **if L2 cannot supply an id, these stay NULL and the device filter (§3.3) returns everything** — which is a stated degradation, not a silent one |

**Deliberately NOT carried across:** `base_abs`, `end_abs`, `encoded_in_window`,
`captured_in_window`, `expected_in_window` (also in `CutResult`). They are ring-arena offsets
and per-window counters for the cut's own accounting; they belong in the capture log
(`specs/03 §3`'s `Stats`), not in a durable index row. If a receipt ever needs them, the log
has them.

⚠ **CONCURRENCY WARNING, measured by another lane on this repo while this spec was being
written: `src/asr/` is being edited in parallel.** `runner.py` and `transcribe.py` changed at
12:20 on 2026-10-07 and `engine.py` at 12:34 — *after* this spec's citations were taken. The
ASR's **emitted shape did not change** (the 7 `segments[]` keys, `text or ""`, and the `done`
construction are all byte-identical in the new revision — re-read and confirmed), but **bare
line numbers are not a durable citation.** So this spec cites `path:line` **and** the symbol or
the exact quoted token; if a line number has moved, the symbol is what to trust.

**Index side — the only function L1's lane calls into the index:**

```python
def register_clip(rec: ClipRecord) -> int   # -> video.id
```

It performs **T0 → T1 → T2** (§2.1) and is **idempotent on `clip_uuid`**: a re-delivered event
updates the row, never duplicates it.

⚠ **`ok: false` MUST be emitted on a refused cut** (`specs/03 §2.7`: no IDR ⇒ refuse and say
so) — and then **no `video` row is written at all**, because T0 is the anchor and there is
nothing to anchor.

### 4.2 L2 — AUDIO → index

L2 does **not** call the index. It produces the wav, and its **contract is the ASR's**, which
is `src/asr/audio.py:53-61` (`def _check`)'s and is not negotiable:

> **16 000 Hz · mono · PCM16 (`sampwidth == 2`).** Anything else is **refused loudly** — the
> runner maps the exception to **exit 2** (`src/asr/transcribe.py:110-114`, `return 2` at :114). Never resampled
> silently: a silent conversion is how a language or a level gets destroyed (`specs/02 §9`).

The reusable, already-proven conversion is **`resample_to_16k(x, src)`** at
`H:\sotto\worker\sotto_worker.py:1090-1105` (`TARGET_SR = 16000`, `:77`) — exact integer
ratios block-average, otherwise `np.interp`. **Reuse it; do not rebuild it** (`ROADMAP §P0.2`).
The loopback tap itself is `WasapiLoopbackTap` (`H:\sotto\worker\wasapi_loopback.py:678`),
which delivers float32 mono at the endpoint's **mix** rate — a loopback stream cannot use
16 kHz, so the resample happens downstream.

**Index side:**

```python
def attach_audio(clip_id: int, wav_path: Path, *, sample_rate: int, channels: int,
                 sampwidth: int, frames: int, source_rate: int,
                 device_id: str | None, device_name: str | None) -> None
```

It records `video.audio_wav`, `src_device_id/name`, and — **it MUST refuse to write a wav that
is not 16 000/1/2**, because a wav that fails ASR's check is a clip whose transcript will never
exist and whose failure would otherwise surface only at search time. See §6.2.

### 4.3 ASR → index — the exact payload the index ingests

```python
def write_transcript(clip_id: int, done: dict) -> TranscriptWriteResult
```

`done` is **verbatim the object `python -m asr.transcribe --json` prints**. Measured, its
**34 top-level keys, in this order** (`_main/lane-spec04-asr-emit.json`):

```
type, label, wav, model_dir, quantization, provider_requested, segment_mode,
threads{intra,inter,env,session_providers,model_name,onnx_asr,onnxruntime,
        ort_available_providers},
wav_format{path,sample_rate,channels,sampwidth,frames,duration_s},
offset_s, audio_s, audio_processed_s, n_segments, seg_median_s, seg_max_s,
load_s, infer_s, rtfx_infer, rtfx_steady, rtfx_slice,
rss_start_mb, rss_after_load_mb, rss_peak_mb, rss_peak_wset_mb,
cpu_median_pct, cpu_max_pct, cpu_load_median_pct, cpu_load_max_pct,
rss_samples, rss_curve, level{n_events,hz,block_ms,peak,release_tau_s,history,
history_points}, phases, segments[], text
```

and each element of `segments[]` has **exactly these 7 keys**:

```
i, start, end, audio_s, wall_s, chars, text
```

**What the index MUST do:**

| from | into | rule |
|---|---|---|
| `segments[i].start` / `.end` | `segment.start_ms` / `.end_ms` | via §1.3: `audio_offset_ms + round(s*1000)`. **`start` is ABSOLUTE within the wav** — MEASURED `offset_s=900` → `start=914.32` |
| `segments[i].text` | `transcript.text` | as-is; **`''` is legal** (§1.2) |
| `segments[i].chars` | `transcript.n_chars` | |
| `segments[i].wall_s` | `transcript.asr_wall_s` | |
| `done.rtfx_steady` | `transcript.asr_rtfx` | the **steady-state** number; the first segment is excluded by the runner (`specs/02 §5`) |
| `done.threads.intra/inter` + `quantization` + `done.threads.model_name` | `transcript.producer` | ⚠ **synthesised — the ASR does not emit it** |
| `asr.constants.MODEL_FILE_SHA256` | `transcript.model_sha256` | ⚠ **synthesised** — `verify_model_dir` checks **sizes only** (`src/asr/engine.py:90-111`, `def verify_model_dir`), so the runner never computes a hash |
| `done.wav_format.sample_rate/channels/sampwidth` | validation | refuse unless `16000 / 1 / 2` (§4.2) |
| `done.wav_format.path` | cross-check against `video.audio_wav` | a mismatch means the ASR read a different file than the index believes — `STATE_MISMATCH`, §6.2 |

**What the index MUST NOT require**, because the ASR does not emit it (§7): `producer`,
`model_sha256`, a confidence or likelihood, a language code, word-level timings, or a VAD
flag. `specs/02 §9` promises **no word timestamps** and `specs/02 §3` states the splitter is
**energy-only** — the Silero VAD is not on disk. An index schema with a
`confidence REAL NOT NULL` column would be unbuildable on day one.

### 4.4 The interface the UI consumes

```python
def get_state() -> StateReport      # clips pending / indexed / failed, §6.4's counters
def get_clip(video_id: int) -> ClipDetail
def reconcile(*, now_s: int) -> ReconcileReport
```

`get_state()` is how the UI obeys law 6: **no index → still save the clip, and say so.** Every
number it returns is a **count**, never an estimate presented as a count.

---

## 5. NORMATIVE PARAMETERS

Every number, its unit, and why it is that number. `⚙` = decided by this spec.

| # | parameter | value | unit | why |
|---|---|---|---|---|
| 1 | **embedding window** (a *planning average*, NOT a schema invariant — see §1.2) | **5000** | ms | the granularity the **visual** pass uses, which is ours to choose. ⚠ **It is NOT the `segment` grain**: the ASR is silence-aligned and its chunks MEASURED 3.96–13.82 s, median 6.98 s. Any storage figure quoted "per 5 s segment" is therefore an **estimate**, and §5 rows 6–9 carry the measured correction |
| 2 | embedding `dim` | **256** | dims | `receipt-06 §8` decides 256d; `receipt-06 §5`: MMEB overall **59.01 / 58.56 / 56.24 / 45.65** at 768/512/256/128 — 256 is the knee. ⚠ **BLOCKED ON THE OWNER**: no weights on disk (B4), so the recall falsifier has not run. If 256d video recall is unusable the answer is **768d**, not a different model (`receipt-06 §10`) |
| 3 | embedding `dtype` on disk | **`float16`** | — | a **disk** decision, never a compute one: native fp16 matvec is **67.3 ms — 8.8× slower** (no fp16 BLAS kernel in this `openblas64` build). Store fp16, cast once at load, scan fp32; the top-10 is **identical** (10/10) (`research 07 §1`) |
| 4 | cast-on-load cost | **0.99 s** for 211 200 vectors (1.0 s/GB) | s | the engine-start budget (§3.6) |
| 5 | channels | **3** (`speech`, `ocr`, `visual`) | — | the provenance channels; `CHECK`-constrained so a fourth cannot appear silently |
| 5b | **`segment` count per 1000 × 10 min, at the MEASURED grain** | **55 000** (read speech) · **40 000** (continuous audio) | rows | ⚠ **RE-DERIVED, replacing `research 07 §6`'s 120 000**, which assumed a 5 s grid the ASR never produces (§1.2). MEASURED: **11 chunks per 120 s = 5.5 s mean** ⇒ 55 chunks per 10 min ⇒ **55 000**. The lower bound is `MAX_SEGMENT_S = 15.0` (`specs/02 §3`) ⇒ 40 chunks ⇒ **40 000**. Content of many short utterances exceeds 55 000, bounded only by `MIN_SEGMENT_S = 0.6`; a silent clip yields **0**. **So 40 000–55 000 is the defensible range and every storage figure scales with it. UNKNOWN: the chunk rate on the owner's own gaming footage — every measurement available here is read speech** |
| 6 | vectors, product corpus | **211 200** | rows | 120 000 visual + 72 000 speech + 19 200 OCR. ⚠ **the 60 %/16 % split is `research 07 §6`'s ASSUMPTION, not a measurement** — the cost is exactly linear in the vector count |
| 7 | vector payload, fp16 | **108.13 MB / 103.13 MiB** | B | `211 200 × 256 × 2` |
| 8 | total store, fp16 + relational | **144.01 MB / 137.34 MiB** | B | MEASURED on a real single file: **+33.2 %** over the payload, of which **34.2 MiB** is relational (`research 07 §6`) |
| 9 | search RAM (fp32 in RAM) | **206.2 MiB** | B | 211 200 × 256 × 4. This is the number law 4 and law 5 are about: **0.05 % of a 300 GB library** |
| 10 | **`journal_mode`** | **`WAL`** | — | the only crash configuration with a measured result: `integrity_check=ok`, **16 000 rows = a clean multiple of the 2 000 batch** (`receipt-07 §5` ARM A) |
| 11 | **`synchronous`** | **`NORMAL`** | — | same ARM A. May lose the last commits on power loss; cannot corrupt the file. That is the trade, taken knowingly |
| 12 | **`cache_size`** | **`-65536`** | KiB (negative = KiB) | **ARM C**: WAL + `NORMAL` with `cache_size=50` → **"database disk image is malformed"**, query RAISED (`receipt-07 §5`). **Never lower it** |
| 13 | `busy_timeout` | **5000** | ms | ⚙ the most one light transaction may hold the file (§2.3), rounded up |
| 14 | `foreign_keys` | **ON** | — | ⚙ SQLite's default is OFF; an orphan transcript is the hole §2 prevents |
| 15 | `wal_autocheckpoint` | **1000** | pages | SQLite's default, **kept** and named so a reader knows it was not chosen |
| 16 | **light-commit batch** | **1 window per transaction** | rows | MEASURED **0.0458 ms median / 0.1670 ms p95**; batching further saves nothing measurable and **widens the window in which a crash loses work** |
| 17 | bulk insert rate | **43 009** (transcript+FTS) / **228 229** (ocr) | rows/s | MEASURED, 2 threads. `research 07 §5` measured **92 688** vectors/s for embeddings alone (no relational rows) |
| 18 | reconciliation interval | **60 s** (state scan) / **startup only** (FTS coverage) | s | the state scan is **8.667 ms**; the FTS scan is **55.584 ms**, i.e. 7× dearer, and the triggers make divergence nearly impossible |
| 19 | **RRF `k` per list** | **100** | rows | `research 07 §3` |
| 20 | **RRF `const`** | **60** | — | RRF's constant; stored in `meta` so a score is hand-checkable |
| 21 | **RRF weights** | **`{speech 1.0, ocr 1.0, visual 0.7, lexical 1.0}`** | — | the first three are `research 07 §3`'s MEASURED; `lexical 1.0` is ⚙ **decided here** (§3.4) |
| 22 | **`k` returned to the UI** | **50** default, **200** hard cap | rows | ⚙ a gallery page is 20; the cap stops a scripted caller from turning a 16 ms scan into a 200-row serialisation |
| 23 | page size (`OFFSET` escape hatch) | **1000** | rows | ⚠ past this, keyset pagination is mandatory (§3.5) |
| 24 | **FTS tokenizer** | **`unicode61 remove_diacritics 2`** | — | MEASURED available and correct: `acesso` matches `ACESSO NEGADO`, `acesso negado` **and** `Acesso à Negado` |
| 25 | **FTS5 file overhead** | **+3.75 MiB on 28.32 MiB = +13.2 %** | MiB | MEASURED at 120 201 segments / 72 200 transcripts / 19 200 OCR lines |
| 26 | FTS5 light-commit overhead | **1.02× median / 1.87× p95** | ratio | MEASURED. The write path pays it deliberately, because lexical is the **required** baseline for OCR (`research 07 §3`) |
| 27 | **`producer` string** | **TEMPLATE**, not a literal ⚠ | — | `"asr:" + done.quantization + "/" + done.threads.model_name + "/intra=" + str(done.threads.intra) + ",inter=" + str(done.threads.inter) + "," + <provider actually used>` — every field read from `done`. ⚠ **hard-coding `intra=4,inter=1` would be a lie for any other run**: the §7 evidence itself was produced at `--threads 2` and reads `intra=2`. `<provider actually used>` is `done.threads.ort_available_providers` filtered by what `done.threads.session_providers` shows was actually used — on this box that is `CPU` (`CUDAExecutionProvider` does not load) |
| 28 | retention | **NONE — nothing is ever deleted** | — | ⚙ **decided, with the reason:** deletion is what makes "a clip exists and is unfindable" possible, and `missing=1` is a **state**, not a delete (`research 07 §2`). A user who wants a clip gone gets a `marker`, not a `DELETE`. **UNKNOWN: the store's growth on a real 300 GB library** — 144 MB per 1000 ten-minute videos is arithmetic from `research 07 §6`, and the owner's real library is 0 scanned so far |
| 29 | WAL truncation | on clean close **and** at every checkpoint ⚙ | — | a `-wal` left unbounded is the one way this store grows without bound; `pragma wal_checkpoint(TRUNCATE)` is what every probe in `receipt-07` ran |
| 30 | store location | `%LOCALAPPDATA%\Sotto\store.db` | path | NVMe, never `I:` (the owner's HDD: **19.7 MB/s** seq, **0.041 MB/s** random, 21.9 ms median random latency, `receipt-08 §1-2`) |

---

## 6. THE FAILURE VOCABULARY

**The rule, normative:** *a silent failure is a defect.* `AGENTS.md` law 6 is explicit —
**"no ASR → still record, and say the transcript is missing; no index → still save the clip."**
Every state below is a **word the UI can print**, never an absence of one. A clip in a
half-written state must look half-written.

### 6.1 `video.state` — the exact vocabulary

| state | meaning | the UI says |
|---|---|---|
| `cutting` | T0 committed, the file not yet written (§2.1) | *"saving…"* |
| `clipped` | the file exists and its metadata is known | normal |
| `transcribing` | the ASR process holds this clip | *"transcribing…"* — `specs/01 §4` requires a clip with no transcript to **look unfinished, not be hidden** |
| `indexed` | transcript (or a deliberate skip) written, at least one channel present | normal, searchable |
| `cut-failed` | no file, or an unreadable partial | **the reason** (`video.note`), never a silent drop |
| `transcribe-failed` | the ASR refused or died | the exit code and the stderr line |

`segment.state`: `new` → `transcribing` → `transcribed` → `indexed`; plus `failed`. ⚠ **`text
= ''` with `chars = 0` is `state='indexed'`, not `failed`** — silence produced no words, which
is a true answer to "what was said".

### 6.2 ERRORS — each one names its cause and its remedy

| name | when | message shape |
|---|---|---|
| `AUDIO_FORMAT_REFUSED` | a wav that is not 16 000/1/2 reached the ASR | `"audio 48000 Hz stereo refused: the ASR contract is 16 kHz mono PCM16 (src/asr/audio.py:53-61, _check)"` — **the clip is still saved**, law 6 |
| `STATE_MISMATCH` | `done.wav_format.path` ≠ `video.audio_wav` | `"ASR read C:\a.wav but the index recorded C:\b.wav"` — a **wrong index is worse than none** |
| `QUERY_MALFORMED` | the escaped query still does not parse (§1.5) | `"search: <term> could not be parsed — try quotes"` — **never "no results"** |
| `MODEL_UNVERIFIED` | `verify_model_dir` refuses (`src/asr/engine.py:90-111`, `def verify_model_dir`) | `"model dir is not the verified artefact: <per-file problems>"` |
| `CORRUPT_STORE` | `PRAGMA integrity_check` is not `ok` | `"the index is damaged — rebuild from the clips (they are all still on disk)"`. ⚠ **The clips are the source of truth**; the store is rebuildable, which is the deepest reason this design is safe |
| `SEARCH_DEGRADED` | `meta.search_mode = 'like'` (§1.6) | `"lexical search is running in fallback mode — slower"` |

### 6.3 "KEEPING UP" — the counters, and they are never merged

The index is S3/S4, below capture in priority (`specs/01 §5`), so it **drops with a counter and
says so** rather than blocking:

| counter | meaning |
|---|---|
| `clips_pending` | `video` rows not yet `indexed` |
| `clips_failed` | `cut-failed` + `transcribe-failed`, by reason |
| `segments_pending` | `segment` rows whose `state != 'indexed'` |
| `vectors_pending` | `(segment, channel)` pairs implied by the pending work and not yet in `embedding` |
| `fts_orphans` | transcript rows the lexical surface cannot see — **must be 0**; MEASURED **0** over 72 200 rows |
| **`stale_fts_tokens`** | ⚠ **tokens indexed for text that no longer exists.** `fts_orphans` is the opposite direction and cannot see this. **Cheap and MEASURED**: `SELECT count(*) FROM transcript_fts WHERE transcript_fts MATCH '"<a distinctive token from the current row>"' AND rowid NOT IN (SELECT seg_id FROM transcript)` is useless per-token; instead build `fts5vocab(transcript_fts, 'row')` (a one-off, O(n) audit) and compare it against the union of the live `text_norm` values. **Any token present in the vocab and absent from the live text is stale** |
| **`segments_collided`** | ⚠ `ON CONFLICT(video_id,start_ms)` fired — two producers disagreed on a `start_ms`. ⚠ **not a drop:** the merge is deliberate, the count is the receipt |
| `last_reconcile_unix_s` | when §2.5 last ran |
| `search_degraded` | `meta.search_mode != 'fts5'` |

**When it cannot keep up, it is a number the UI shows, not a queue that grows silently.** A SKIP
is not a pass and a backlog is not a healthy state — the same rule that made the ASR's oracle
print each arm in its own column.

### 6.4 THE ONE REFUSAL

**If the store cannot be opened or `integrity_check` fails, the engine REFUSES TO START THE
INDEX and says so — and keeps recording.** This is law 6 verbatim: a recorder that claims to be
armed while it is broken is the worst failure this product can have. The clip path never
depends on the index being alive; it depends on it being **honest**.

---

## 7. THE CROSS-CHECK — what the ASR *actually* emits

This is the acceptance requirement, and it was **executed**, not inferred. Command, exit code
and evidence, all reproducible:

```
$ py -3 -m asr.transcribe --wav H:\sotto\_main\_redux-long\plain-3600s.wav \
      --offset-s 900 --max-s 120 --threads 2 --level off --json
RESULT plain-3600s.wav: silence 11 segs (med 6.98s max 13.82s) audio 120.0s
       load 8.141s infer 21.393s rtfx(infer/steady/slice)=4.06/4.08/5.61
       threads(intra=2,inter=1) cpu(infer med/max)=217.2/238.4%
       rss(load/peak/peak_wset)=736.4/911.4/923.9MB chars=814        # exit=0
```

**Reproduces `specs/02 §6`'s regression lock exactly** — 11 segments, **814 chars**, median
6.98 s, max 13.82 s — at 2 threads. The event file is **4 811 B**, sha256 `f895749477532574…`
(`lane-spec04-asr-emit.json`). Six facts that the schema in §1 was written against:

| # | MEASURED fact | where it bites the index |
|---|---|---|
| 1 | `segments[]` has **exactly 7 keys**: `i, start, end, audio_s, wall_s, chars, text` | §4.3 — the writer's whole input surface |
| 2 | **`start` is ABSOLUTE in the wav**: `offset_s=900` ⇒ `segments[0].start = 914.32` | §1.3 — the `audio_offset_ms` formula; an implementer who treats it as slice-relative puts every timestamp 900 s early |
| 3 | **adjacent segments OVERLAP by exactly 0.20 s** (`i=0` ends 922.38, `i=1` starts 922.18) — and a **gap of 10.26 s** between `i=3` (ends 947.600) and `i=4` (starts 957.860), which is real silence | `PAD_S = 0.10` either side (`specs/02 §3`). ⚠ **there is NO non-overlap invariant** — a segment may start before its predecessor ends. The invariant that DOES hold, and is the one §1.2's `UNIQUE(video_id, start_ms)` relies on, is that **`start` is strictly increasing** across all 11 segments (verified on the real output). The two negative gaps are silence the splitter left alone |
| 4 | **`sum(chars) = 804` but `len(done.text) = 814`** | the clip-level text is `" ".join(stripped non-empty)` (`src/asr/runner.py`, the `text = " ".join(...)` line), i.e. **10 join spaces**. Store per-segment text; do **not** assume the concatenation is reversible by naive concatenation |
| 5 | the output file is **valid UTF-8** (4 811 B, decodes clean) and carries non-ASCII (`rádio`, `interditada`) | `text`/`text_norm` are **UTF-8**. ⚠ `receipt-02`'s cp1252 lesson (`redux-ptbr.txt` has `0xE1` at offset 135) applies to the **oracle files**, not to this channel — but the index must still open its store with an explicit UTF-8 path, never a locale default |
| 6 | `wav_format.duration_s = 3600.0` while `audio_s = 120.0` | §1.2: `video.duration_ms` is the **clip's**; never `wav_format.duration_s` |

**And the fact that decided §1.5:** that registered transcript's first segment contains
**`segunda-feira`** — and an unquoted `MATCH 'segunda-feira'` **RAISES**
`OperationalError: no such column: feira` on the product's own text
(`lane-spec04-fts5-realtext.log`). The escaping rule is not a hardening suggestion; without it
the search box **crashes on ordinary Portuguese**.

---

## 8. WHAT THIS SPEC DELIBERATELY DOES NOT DO, AND WHAT STAYS UNKNOWN

**Does not:**

- **store frames, or a second copy of a video** (law 4). `frame_ref` is a pointer to a derived
  poster cache; the vector payload is **0.05 %** of the library.
- **delete anything.** Retention is **none** (§5 #28); `missing=1` is a state.
- **run a reranker** — **10.8 s** per query at 100 candidates against an **83.2 ms** fused
  query, and no measurement exists that it improves top-5 on our data (`research 07 §4`).
- **use an ANN index** — exact is **16 ms**, HNSW recall on real embeddings is unmeasured, and
  `remove_ids` **RAISES** (`research 07 §1`), which §2.5 requires.
- **require word-level timestamps or a confidence** — the ASR emits neither (`specs/02 §9`), so a
  schema demanding them is unbuildable on day one.
- **invent a second job queue.** The durable lease-based `job` table is **lane 08's**
  (`research 08`: `job(asset_id, stage, chunk, params_hash, state, attempts, lease_expires_at,
  started_at, finished_at, error)`, stages `probe → thumb → audio → asr → frame → embed → ocr`,
  recovered by **one UPDATE** — every `running` row with an expired lease returns to
  `pending`). ⚙ **This spec references it and does not redefine it**, because two job tables is
  how a repo grows a bug. The index's tables in §1.2 are the job's **payload**.

**UNKNOWN, named with the experiment that settles each** (inherited from `research 07 §7` and
extended here):

1. **the real speech/OCR coverage fractions** (60 %/16 % are assumptions) — count over 20 real
   videos; cost is exactly linear in the vector count;
2. **the fused query at 4 threads** — measured only at 2, expect ~2×;
3. **the window-filtered scan after slicing per video** — the mask is free today; slicing is not
   measured;
4. **whether an int8 reranker changes the verdict** — no int8 kernel rate was measured;
5. **HNSW recall on real embeddings** — 3–29 % is on random unit vectors, the case to
   disbelieve, not to trust;
6. **256d vs 768d video recall** — **BLOCKED ON THE OWNER** (B4: no embedding weights on disk;
   the ~1.5 GB download is his call). The falsifier is 200 s of his own footage → 5 s windows →
   recall@5 at 768d vs 256d;
7. **the light-commit latency at 1.2 M segments** — §2.3's p95 is over 120 201 segments;
8. **the store's growth on a real 300 GB library** — 144 MB / 1000 videos is arithmetic.