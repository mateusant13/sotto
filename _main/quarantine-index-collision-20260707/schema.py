"""schema.py -- the store's DDL, its version, and the migration that never loses a row.

ONE SQLite file holds the record (docs/research/07-index-search.md:10-13, the measured store
decision: "numpy flat over the SQLite blob table", 0 extra bytes installed, crash-safe under
WAL with TWO RED CONTROLS at 07-index-search.md:24). This module owns everything about that
file EXCEPT the writes (`store.py`) and the reads (`search.py`).

The relational half is lane 07's schema verbatim (07-index-search.md:31-42); three columns are
added here because this lane's brief demands them and lane 07 does not carry them:
`video.source_device`, `video.h264_path`, `video.aac_path`. Nothing lane 07 declared was
renamed or dropped -- two names for one table is how a repo grows a bug (07-index-search.md:32).

FTS5 IS PROBED, NOT ASSUMED. `fts5_available()` builds a virtual table, inserts a row and runs a
MATCH against it; if any step raises, the search path falls back to LIKE over `text_norm` and
says so in `SearchResult.mode`. Measured on this box: SQLite 3.43.1 / Python 3.11.8, FTS5 YES
-- but a bundled SQLite is a build decision, not a promise, so the code never reads a version
string to decide.
"""

from __future__ import annotations

import re
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

__all__ = [
    "SCHEMA_VERSION",
    "BUSY_TIMEOUT_MS",
    "FTS_TABLE",
    "fts5_available",
    "open_index",
    "transaction",
    "migrate",
    "index_info",
]

#: Bumped only by an additive change to the DDL below. `PRAGMA user_version` carries it.
SCHEMA_VERSION = 1

#: A concurrent writer waits instead of raising "database is locked". A requirement, not a guess:
#: gate arm D runs two OS processes against one file.
BUSY_TIMEOUT_MS = 10_000

# ---------------------------------------------------------------------------------------------
# The DDL.  Every statement is IF NOT EXISTS and every migration step is ADDITIVE (ADD COLUMN,
# CREATE INDEX IF NOT EXISTS, CREATE VIRTUAL TABLE IF NOT EXISTS + backfill).  Nothing here DROPs,
# RENAMEs or rewrites a row: opening an existing db must not lose anything.
# ---------------------------------------------------------------------------------------------

_SCHEMA: tuple[str, ...] = (
    # lane 07's `video` IS lane 08's `asset` -- two names for one table is how a repo grows a bug
    # (07-index-search.md:32). Identity is `content_key` (whole-file SHA-256, lane 08), never the
    # path: a rename must cost one UPDATE and zero re-indexing (07-index-search.md:46).
    """
    CREATE TABLE IF NOT EXISTS video (
        id               TEXT PRIMARY KEY,
        content_key      TEXT,
        file_key         TEXT,
        path             TEXT NOT NULL,
        h264_path        TEXT,
        aac_path         TEXT,
        size_bytes       INTEGER,
        mtime_ns         INTEGER,
        duration_ms      INTEGER NOT NULL DEFAULT 0,
        w                INTEGER,
        h                INTEGER,
        fps              REAL,
        source_device    TEXT,
        mode             TEXT,
        started_at_s     REAL,
        added_at_s       REAL,
        last_seen_scan_s REAL,
        missing          INTEGER NOT NULL DEFAULT 0,
        state            TEXT NOT NULL DEFAULT 'recorded'
    )
    """,
    # lane 07 (07-index-search.md:36). `UNIQUE(video_id, start_ms)` is ADDED by this lane and is
    # load-bearing: re-running the ASR pass over the same wav must upsert the SAME segment rows,
    # not duplicate them. That uniqueness is what makes `ingest_asr_done` idempotent.
    """
    CREATE TABLE IF NOT EXISTS segment (
        seg_id    INTEGER PRIMARY KEY,
        video_id  TEXT NOT NULL REFERENCES video(id) ON DELETE CASCADE,
        start_ms  INTEGER NOT NULL,
        end_ms    INTEGER NOT NULL,
        n_visual  INTEGER NOT NULL DEFAULT 0,
        n_speech  INTEGER NOT NULL DEFAULT 0,
        n_ocr     INTEGER NOT NULL DEFAULT 0,
        state     TEXT NOT NULL DEFAULT 'closed',
        UNIQUE (video_id, start_ms)
    )
    """,
    # lane 07 (07-index-search.md:37). No denormalised video_id: the answer path is
    # transcript -> segment -> video, which is what 07-index-search.md:44 measured at 0.011 ms.
    """
    CREATE TABLE IF NOT EXISTS transcript (
        seg_id       INTEGER PRIMARY KEY REFERENCES segment(seg_id) ON DELETE CASCADE,
        start_ms     INTEGER NOT NULL,
        end_ms       INTEGER NOT NULL,
        text         TEXT NOT NULL,
        text_norm    TEXT NOT NULL,
        producer     TEXT,
        model_sha256 TEXT,
        created_at_s REAL
    )
    """,
    # lane 02's request list, verbatim (07-index-search.md:38-39): FTS5 over `ocr.text_norm` is the
    # REQUIRED lexical baseline for game tokens like `ERRO 0x80070005: ACESSO NEGADO`
    # (07-index-search.md:53). Declared here, written by lane 02's pass -- NOT by this lane.
    """
    CREATE TABLE IF NOT EXISTS ocr (
        seg_id       INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
        line_no      INTEGER NOT NULL,
        t_ms         INTEGER NOT NULL,
        t_end_ms     INTEGER NOT NULL,
        text_raw     TEXT NOT NULL,
        text_norm    TEXT NOT NULL,
        box          TEXT,
        conf         REAL,
        engine       TEXT,
        model_sha256 TEXT,
        frame_ref    TEXT,
        PRIMARY KEY (seg_id, line_no)
    )
    """,
    # Declared by lane 07 (07-index-search.md:40) and used by the ANN lane over the fp16 blobs.
    # THIS LANE NEVER WRITES IT -- the primary key (seg_id, channel) IS the work unit, so a
    # repeated pass with the same model is a no-op INSERT OR IGNORE (07-index-search.md:70).
    """
    CREATE TABLE IF NOT EXISTS embedding (
        seg_id       INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
        channel      TEXT NOT NULL,
        dim          INTEGER NOT NULL,
        dtype        TEXT NOT NULL,
        vec          BLOB NOT NULL,
        model        TEXT,
        model_sha256 TEXT,
        built_at_s   REAL,
        PRIMARY KEY (seg_id, channel)
    )
    """,
    # lane 07 (07-index-search.md:41).
    """
    CREATE TABLE IF NOT EXISTS marker (
        seg_id  INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
        kind    TEXT NOT NULL,
        value   TEXT,
        source  TEXT,
        PRIMARY KEY (seg_id, kind, source)
    )
    """,
)

_INDICES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS video_started ON video(started_at_s)",
    "CREATE INDEX IF NOT EXISTS video_device ON video(source_device)",
    "CREATE INDEX IF NOT EXISTS segment_video ON segment(video_id, start_ms)",
    "CREATE INDEX IF NOT EXISTS transcript_start ON transcript(start_ms)",
)

# The search surface.  `remove_diacritics 2` is why a Portuguese query for `coracao` finds
# `coração` -- the transcript carries no punctuation and no case structure, so the lexical path
# must be accent- and case-insensitive or it is useless on this corpus.
FTS_TABLE = "transcript_fts"
_FTS_DDL = f"""
CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE}
USING fts5(seg_id UNINDEXED, text_norm, tokenize='unicode61 remove_diacritics 2')
"""

# Columns added by this lane on top of lane 07's `video`, with the fragment used to add them to
# an OLD db that predates them.  Additive only -- an existing row keeps every value it had and
# gains NULLs, which every reader already tolerates.
_ADDED_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("video", "h264_path", "TEXT"),
    ("video", "aac_path", "TEXT"),
    ("video", "source_device", "TEXT"),
    ("video", "started_at_s", "REAL"),
    ("video", "mode", "TEXT"),
)

_CREATE_RE = re.compile(
    r"CREATE\s+(?:VIRTUAL\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def fts5_available(con: sqlite3.Connection) -> bool:
    """MEASURED, not assumed: build an FTS5 table, insert a row, MATCH it, tear it down.

    A version string is not a capability -- a build can ship SQLite without the fts5 extension
    compiled in, and the search path must degrade to LIKE instead of raising at query time.
    """
    try:
        con.execute("CREATE VIRTUAL TABLE temp.fts5_probe USING fts5(x)")
        con.execute("INSERT INTO temp.fts5_probe(x) VALUES ('probe')")
        # The left operand of MATCH must be the BARE table name -- a schema-qualified
        # `temp.fts5_probe MATCH ...` raises "no such column" and would silently degrade every
        # search on a perfectly good build.
        hit = con.execute(
            "SELECT count(*) FROM temp.fts5_probe WHERE fts5_probe MATCH 'probe'"
        ).fetchone()
        con.execute("DROP TABLE temp.fts5_probe")
        return bool(hit and int(hit[0]) == 1)
    except sqlite3.Error as exc:
        print(
            f"index: FTS5 probe failed ({type(exc).__name__}: {exc}); the LIKE fallback in "
            "search.py takes over and SearchResult.mode will say 'like'",
            file=sys.stderr,
        )
        try:
            con.execute("DROP TABLE IF EXISTS temp.fts5_probe")
        except sqlite3.Error as drop_exc:
            # Best-effort temp cleanup on an ALREADY-degraded path. What is lost when this
            # fires: the `temp.fts5_probe` scratch table survives on THIS connection only (temp
            # is per-connection and vanishes at close), and the diagnostic line above already
            # told the caller the search surface degraded. Nothing else in the store is touched.
            print(f"index: could not drop temp.fts5_probe either ({drop_exc})", file=sys.stderr)
        return False


@contextmanager
def transaction(con: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit IMMEDIATE transaction. The store runs in autocommit (`isolation_level=None`), so
    every write states its own boundary; IMMEDIATE takes the write lock up front, which is what
    makes two concurrent writers queue on `busy_timeout` instead of failing at COMMIT."""
    con.execute("BEGIN IMMEDIATE")
    try:
        yield con
    except BaseException:
        con.execute("ROLLBACK")
        raise
    con.execute("COMMIT")


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return (
        con.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (name,)
        ).fetchone()
        is not None
    )


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(con, table):
        return set()
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def migrate(con: sqlite3.Connection) -> dict:
    """Bring `con` to SCHEMA_VERSION without losing a row. Idempotent: running it twice changes
    nothing the second time (gate arm B). Returns what it actually did."""
    before = int(con.execute("PRAGMA user_version").fetchone()[0])
    created: list[str] = []
    added: list[str] = []
    indexed: list[str] = []
    backfilled = 0

    if before > SCHEMA_VERSION:
        # Refuse loudly rather than "migrating" a newer file downwards -- that is how a store
        # loses data. Same posture as the ASR runner refusing a 44.1 kHz wav (specs/02-asr.md:9).
        raise RuntimeError(
            f"index: db schema_version={before} is NEWER than this build's {SCHEMA_VERSION}; "
            "refusing to open it (a newer Sotto wrote it)"
        )

    with transaction(con):
        for stmt in _SCHEMA:
            match = _CREATE_RE.match(stmt.strip())
            name = match.group(1) if match else ""
            if name and not _table_exists(con, name):
                created.append(name)
            con.execute(stmt)

        # Additive columns: an old db opens without losing its rows and gains the new ones NULL.
        for table, column, decl in _ADDED_COLUMNS:
            if column not in _columns(con, table):
                con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                added.append(f"{table}.{column}")

        for stmt in _INDICES:
            name = stmt.rsplit(" ON ", 1)[-1]
            if not con.execute(
                "SELECT 1 FROM sqlite_master WHERE type='index' AND name = ?", (name,)
            ).fetchone():
                indexed.append(name)
            con.execute(stmt)

        fts = False
        if fts5_available(con):
            con.execute(_FTS_DDL)
            fts = True
            # Backfill: a db created before the FTS table existed already holds rows, and an
            # index that does not contain them would answer "no hits" to a query that should hit.
            backfilled = con.execute(
                f"INSERT INTO {FTS_TABLE}(seg_id, text_norm) "
                "SELECT t.seg_id, t.text_norm FROM transcript t "
                f"WHERE NOT EXISTS (SELECT 1 FROM {FTS_TABLE} f WHERE f.seg_id = t.seg_id)"
            ).rowcount

        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    return {
        "from_version": before,
        "to_version": SCHEMA_VERSION,
        "tables_created": created,
        "columns_added": added,
        "indices_created": indexed,
        "fts5": fts,
        "fts_rows_backfilled": max(backfilled, 0),
    }


def open_index(db_path: str | Path, *, create: bool = True) -> sqlite3.Connection:
    """Open (and migrate) the index. THE product entry point.

    Pragmas, and why each one is here:
      journal_mode=WAL + synchronous=NORMAL -- the shipped config, EARNED: with `OFF/OFF` a kill
        inside a transaction left a torn row count, and with `cache_size=50` the file came back
        "database disk image is malformed" (07-index-search.md:24). Two red controls.
      busy_timeout -- a second writer waits instead of raising (gate arm D).
      foreign_keys=ON -- the segment/transcript/ocr cascade is real, not documentary.
    """
    path = Path(db_path)
    if not create and not path.exists():
        raise FileNotFoundError(f"index: no such db and create=False: {path}")
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(path), isolation_level=None, timeout=BUSY_TIMEOUT_MS / 1000.0)
    con.row_factory = sqlite3.Row
    con.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    # `PRAGMA journal_mode` returns a row, so the cursor must be drained before the next
    # statement or python's sqlite3 raises "Recursive use of cursors not allowed".
    con.execute("PRAGMA journal_mode = WAL").fetchall()
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA foreign_keys = ON")
    migrate(con)
    return con


def index_info(con: sqlite3.Connection) -> dict:
    """What is actually on disk -- the numbers a receipt quotes. Every count is a full table
    count (the POPULATION), never a filtered one."""

    def count(table: str) -> int:
        if not _table_exists(con, table):
            return -1
        return int(con.execute(f"SELECT count(*) FROM {table}").fetchone()[0])

    return {
        "sqlite_version": sqlite3.sqlite_version,
        "schema_version": int(con.execute("PRAGMA user_version").fetchone()[0]),
        "journal_mode": con.execute("PRAGMA journal_mode").fetchone()[0],
        "integrity_check": con.execute("PRAGMA integrity_check").fetchone()[0],
        "fts5": bool(con.execute(
            "SELECT 1 FROM sqlite_master WHERE name = ?", (FTS_TABLE,)
        ).fetchone()),
        "rows": {
            "video": count("video"),
            "segment": count("segment"),
            "transcript": count("transcript"),
            "ocr": count("ocr"),
            "embedding": count("embedding"),
            "marker": count("marker"),
            FTS_TABLE: count(FTS_TABLE),
        },
    }