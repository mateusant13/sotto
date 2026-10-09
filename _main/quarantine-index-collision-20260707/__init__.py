"""index -- Sotto's searchable clip index. ONE SQLite file (`docs/research/07-index-search.md`).

Layout:
  schema.py   the DDL, `PRAGMA user_version`, and an ADDITIVE migration that never loses a row
  store.py    the WRITER: a completed clip, then its ASR `done` -- THE DECLARED INTERFACE
  search.py   the READ side: FTS5 text search + time / device / duration filters
  selftest.py the gate harness (`python -m index.selftest --arm A`), arms A/B/C/D

Why SQLite and not faiss/hnswlib/sqlite-vec: measured on this box (07-index-search.md:11-30).
One file, 0 extra bytes installed, crash-safe under WAL with two red controls, and the vector
half is a numpy scan of the fp16 blobs -- 16 ms for an exact answer at 211 200 vectors, against
an ANN index whose recall on this data measured 3-29% (07-index-search.md:21). This lane owns
the RELATIONAL half and the LEXICAL half; the vector half belongs to the ANN lane and the
`embedding` table here is its declared home, unwritten by this lane (07-index-search.md:40).

THE CONTRACT WITH THE OTHER LANES, in one paragraph (full text at the top of `store.py`):
L1 calls `ingest_clip(index, clip)` the moment the muxed `.mp4` exists on disk, with the
`CutResult` fields (src/capture/replay.h:59-76) as a JSON mapping; L2 calls
`ingest_asr_done(index, clip_id, done)` when the background ASR pass finishes, with the runner's
`done` event VERBATIM (src/asr/runner.py:258-305). Both are idempotent on `clip_id`. Seconds go
in, milliseconds are stored; the conversion happens once, in `store._ms`.

This module imports nothing heavy: no numpy, no onnxruntime. The ASR engine pins its thread
pools before numpy loads (`src/asr/__init__.py`), and the index must never be the thing that
loads them.
"""

from __future__ import annotations

from .schema import (
    BUSY_TIMEOUT_MS,
    FTS_TABLE,
    SCHEMA_VERSION,
    fts5_available,
    index_info,
    migrate,
    open_index,
    transaction,
)
from .search import SearchFilter, SearchResult, fts5_match_expression, search_text
from .store import (
    PRODUCER_ASR,
    ClipRecord,
    IngestResult,
    ingest_asr_done,
    ingest_clip,
    ingest_many,
    normalise_text,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SCHEMA_VERSION",
    "BUSY_TIMEOUT_MS",
    "FTS_TABLE",
    "open_index",
    "migrate",
    "transaction",
    "index_info",
    "fts5_available",
    "ClipRecord",
    "IngestResult",
    "PRODUCER_ASR",
    "normalise_text",
    "ingest_clip",
    "ingest_asr_done",
    "ingest_many",
    "SearchFilter",
    "SearchResult",
    "search_text",
    "fts5_match_expression",
]