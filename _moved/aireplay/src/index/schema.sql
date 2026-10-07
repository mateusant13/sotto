-- Sotto index schema.  ONE SQLite file holds the record AND every vector.
-- Design: docs/research/07-index-search.md (MEASURED on this box).
--
-- IDENTITY: `video.content_key` = whole-file SHA-256.  NEVER the path.
--   A renamed file has the same content_key -> UPDATE path, missing=0, no re-index,
--   still one row.  A path key re-processes the whole library after one rename
--   (docs/research/07-index-search.md sec 2).
--
-- `video` IS lane 08's `asset` table (docs/research/08-import-library.md).
-- One table, one name.  The import lane's identity columns are kept:
-- file_key, content_key, path, size_bytes, mtime_ns, duration_ms, codec, w, h,
-- fps, bitrate, last_seen_scan, missing  (+ added_at, state from doc 07).
--
-- CRASH SAFETY -- the three pragmas below are MEASURED, not chosen:
--   journal_mode=WAL + synchronous=NORMAL  -> taskkill /F mid-transaction
--       recovered exactly 16 000 rows = a clean multiple of the 2 000-row batch.
--   journal_mode=OFF                      -> 18 041 rows, a TORN count.
--   cache_size=50 (tiny)                  -> "database disk image is malformed".
--   => WAL/NORMAL stays, cache_size stays generous.  DO NOT "tune" either away.

PRAGMA journal_mode = WAL;          -- crash-safe, and proven to recover cleanly
PRAGMA synchronous  = NORMAL;       -- correct with WAL: a power-cut can lose a
                                     -- commit, never corrupt the database
PRAGMA cache_size   = -16000;       -- 16 MiB, NEGATIVE = KiB.  Never a tiny
                                     -- positive value: cache_size=50 corrupts.
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

-- ---------------------------------------------------------------------------
-- schema version
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO index_meta(key, value) VALUES ('schema_version', '1');

-- ---------------------------------------------------------------------------
-- video  == lane 08's asset table.  content_key is the identity.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS video (
    id            INTEGER PRIMARY KEY,
    -- whole-file SHA-256 (hex).  UNIQUE => upsert-on-content_key is idempotent.
    content_key   TEXT    NOT NULL UNIQUE
                  CHECK (length(content_key) = 64),
    -- lane 08's cheap "have I seen this object" memo (volume_serial, ntfs_file_id).
    -- Distinct from identity: NULL when unknown, still idempotent on content_key.
    file_key      TEXT    UNIQUE,
    path          TEXT    NOT NULL,
    size_bytes    INTEGER NOT NULL CHECK (size_bytes >= 0),
    mtime_ns      INTEGER NOT NULL,
    duration_ms   INTEGER NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    codec         TEXT,
    w             INTEGER,
    h             INTEGER,
    fps           REAL,
    bitrate       INTEGER,
    added_at      INTEGER NOT NULL DEFAULT (unixepoch()),
    last_seen_scan INTEGER,
    missing       INTEGER NOT NULL DEFAULT 0 CHECK (missing IN (0,1)),
    state         TEXT    NOT NULL DEFAULT 'discovered'
    -- discovered | indexed | superseded | failed
);

-- ---------------------------------------------------------------------------
-- segment -- a 5 s window.  The hit is a window, so start_ms lives HERE,
-- never on video: "open clip_0644.mp4 at 03:41.2" is a property of the hit.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS segment (
    seg_id    INTEGER PRIMARY KEY,
    video_id  INTEGER NOT NULL REFERENCES video(id) ON DELETE CASCADE,
    start_ms  INTEGER NOT NULL CHECK (start_ms >= 0),
    end_ms    INTEGER NOT NULL CHECK (end_ms >= start_ms),
    n_visual  INTEGER NOT NULL DEFAULT 0 CHECK (n_visual    IN (0,1)),
    n_speech  INTEGER NOT NULL DEFAULT 0 CHECK (n_speech    IN (0,1)),
    n_ocr     INTEGER NOT NULL DEFAULT 0 CHECK (n_ocr       IN (0,1)),
    state     TEXT    NOT NULL DEFAULT 'pending'
    -- pending | light | promoted | failed
);

-- ---------------------------------------------------------------------------
-- transcript -- PK is seg_id: one pass's row per window, INSERT OR IGNORE is a
-- no-op for the same model, REPLACE for a changed model.  Never two ASR results.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcript (
    seg_id       INTEGER PRIMARY KEY REFERENCES segment(seg_id) ON DELETE CASCADE,
    start_ms     INTEGER NOT NULL DEFAULT 0,
    text         TEXT,
    text_norm    TEXT,
    producer     TEXT,
    model_sha256 TEXT
);

-- ---------------------------------------------------------------------------
-- ocr -- lane 02's request list, verbatim.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ocr (
    seg_id       INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
    line_no      INTEGER NOT NULL CHECK (line_no >= 0 AND line_no < 4096),
    t_ms         INTEGER NOT NULL DEFAULT 0,
    t_end_ms     INTEGER,
    text_raw     TEXT,
    text_norm    TEXT,
    box          TEXT,
    conf         REAL,
    engine       TEXT,
    model_sha256 TEXT,
    frame_ref    TEXT,
    PRIMARY KEY (seg_id, line_no)
);

-- ---------------------------------------------------------------------------
-- embedding -- (seg_id, channel) IS the work unit.  Same channel + same model
-- = INSERT OR IGNORE (a no-op, so promotion never redoes work); different model
-- = INSERT OR REPLACE, detectable per row.  No silent mix.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS embedding (
    seg_id       INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
    channel      TEXT    NOT NULL CHECK (channel IN ('speech','ocr','visual')),
    dim          INTEGER NOT NULL CHECK (dim > 0),
    dtype        TEXT    NOT NULL CHECK (dtype IN ('fp16','fp32')),
    vec          BLOB    NOT NULL,
    model        TEXT,
    model_sha256 TEXT,
    built_at     INTEGER NOT NULL DEFAULT (unixepoch()),
    PRIMARY KEY (seg_id, channel)
);

-- ---------------------------------------------------------------------------
-- marker -- free-form typed flags (speech detected, black frame, ...)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marker (
    seg_id INTEGER NOT NULL REFERENCES segment(seg_id) ON DELETE CASCADE,
    kind   TEXT    NOT NULL,
    value  TEXT,
    source TEXT,
    PRIMARY KEY (seg_id, kind)
);

CREATE INDEX IF NOT EXISTS segment_video  ON segment(video_id, start_ms);
CREATE INDEX IF NOT EXISTS segment_window  ON segment(video_id, start_ms, end_ms);
CREATE INDEX IF NOT EXISTS ocr_seg        ON ocr(seg_id);
CREATE INDEX IF NOT EXISTS embedding_chan  ON embedding(channel);
CREATE INDEX IF NOT EXISTS video_missing  ON video(missing, state);

-- ---------------------------------------------------------------------------
-- FTS5 -- the 4th list: lexical over transcript + ocr text.  The required
-- baseline for OCR, and lane 02 MEASURED byte-exact retrieval of game tokens
-- like `ERRO 0x80070005: ACESSO NEGADO`.  unicode61 folds ASCII case and keeps
-- alphanumeric runs, so `0x80070005` is ONE token and comes back byte-exact.
-- The writer lowercases into text_norm (that is what "norm" means); the
-- tokenizer does the rest.
--
-- rowid mapping (both base tables feed this one FTS table, and seg_id collides
-- between them, so the ids cannot both be the rowid):
--     transcript(seg_id)          -> rowid = seg_id
--     ocr(seg_id, line_no)        -> rowid = FTS_OCR_BASE + seg_id*4096 + line_no
-- FTS_OCR_BASE = 2^40 and line_no < 4096 (CHECKed above), so the two id spaces
-- cannot collide for any sane seg_id.
-- Maintained by TRIGGERS, not by the writer: the import lane and the light
-- writer both insert into ocr/transcript directly, and the index must follow
-- without either of them remembering.
-- ---------------------------------------------------------------------------
CREATE VIRTUAL TABLE IF NOT EXISTS text_fts USING fts5(
    text_norm,
    source UNINDEXED,      -- 'transcript' | 'ocr'
    seg_id  UNINDEXED,
    line_no UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);

-- transcript -> text_fts
CREATE TRIGGER IF NOT EXISTS tr_transcript_fts_ai AFTER INSERT ON transcript BEGIN
    INSERT INTO text_fts(rowid, text_norm, source, seg_id, line_no)
    VALUES (NEW.seg_id, NEW.text_norm, 'transcript', NEW.seg_id, -1);
END;
CREATE TRIGGER IF NOT EXISTS tr_transcript_fts_ad AFTER DELETE ON transcript BEGIN
    INSERT INTO text_fts(text_fts, rowid, text_norm, source, seg_id, line_no)
    VALUES ('delete', OLD.seg_id, OLD.text_norm, 'transcript', OLD.seg_id, -1);
END;
CREATE TRIGGER IF NOT EXISTS tr_transcript_fts_au AFTER UPDATE ON transcript BEGIN
    INSERT INTO text_fts(text_fts, rowid, text_norm, source, seg_id, line_no)
    VALUES ('delete', OLD.seg_id, OLD.text_norm, 'transcript', OLD.seg_id, -1);
    INSERT INTO text_fts(rowid, text_norm, source, seg_id, line_no)
    VALUES (NEW.seg_id, NEW.text_norm, 'transcript', NEW.seg_id, -1);
END;

-- ocr -> text_fts.  1099511627776 = 2^40.
CREATE TRIGGER IF NOT EXISTS tr_ocr_fts_ai AFTER INSERT ON ocr BEGIN
    INSERT INTO text_fts(rowid, text_norm, source, seg_id, line_no)
    VALUES (1099511627776 + NEW.seg_id * 4096 + NEW.line_no,
            NEW.text_norm, 'ocr', NEW.seg_id, NEW.line_no);
END;
CREATE TRIGGER IF NOT EXISTS tr_ocr_fts_ad AFTER DELETE ON ocr BEGIN
    INSERT INTO text_fts(text_fts, rowid, text_norm, source, seg_id, line_no)
    VALUES ('delete', 1099511627776 + OLD.seg_id * 4096 + OLD.line_no,
            OLD.text_norm, 'ocr', OLD.seg_id, OLD.line_no);
END;
CREATE TRIGGER IF NOT EXISTS tr_ocr_fts_au AFTER UPDATE ON ocr BEGIN
    INSERT INTO text_fts(text_fts, rowid, text_norm, source, seg_id, line_no)
    VALUES ('delete', 1099511627776 + OLD.seg_id * 4096 + OLD.line_no,
            OLD.text_norm, 'ocr', OLD.seg_id, OLD.line_no);
    INSERT INTO text_fts(rowid, text_norm, source, seg_id, line_no)
    VALUES (1099511627776 + NEW.seg_id * 4096 + NEW.line_no,
            NEW.text_norm, 'ocr', NEW.seg_id, NEW.line_no);
END;