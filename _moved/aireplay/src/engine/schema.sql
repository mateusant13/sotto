-- src/engine/schema.sql -- the Engine's DURABLE SPINE.

PRAGMA journal_mode=WAL;
PRAGMA synchronous=FULL;      -- a clip row is committed BEFORE the engine acks it (ARM-F)
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

-- Why SQLite is the spine and not the bus: the bus (JSONL over the pipe/socket) is
-- allowed to DROP -- the design note's bounded queues drop with a counter, because a
-- caption that is one sample late is worthless.  A clip is not that.  The clip row and
-- the speech rows hang off it here, and they survive the process: TerminateProcess is
-- the test (ARM-F), and the row exists or it does not.

-- One row per clip.  content_key is the WHOLE-FILE SHA-256 hex (length 64, UNIQUE) --
-- the same identity rule as src/index/schema.sql's video.content_key, so lane B's
-- index can join on it without inventing a second key.  Divergence recorded in the
-- receipt: this table is engine/in/clip_named, the index's is video.
CREATE TABLE IF NOT EXISTS clip (
    clip_id      TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    content_key  TEXT UNIQUE,          -- NULL while state='cutting' (row before bytes)
    started_at   REAL NOT NULL,        -- seconds, engine clock
    duration_ms  INTEGER NOT NULL DEFAULT 0,
    modes        TEXT NOT NULL DEFAULT '',
    frames       INTEGER NOT NULL DEFAULT 0,
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    state        TEXT NOT NULL DEFAULT 'cutting',   -- 'cutting' | 'done' | 'failed'
    asr_state    TEXT NOT NULL DEFAULT 'pending',   -- 'pending' | 'ok' | 'dropped' | 'dead'
    created_at   REAL NOT NULL,
    committed_at REAL
);
CREATE INDEX IF NOT EXISTS clip_state   ON clip(state);
CREATE INDEX IF NOT EXISTS clip_started ON clip(started_at);

-- Speech rows hang off the clip (ON DELETE CASCADE: no orphan speech).
CREATE TABLE IF NOT EXISTS speech_segment (
    clip_id    TEXT NOT NULL REFERENCES clip(clip_id) ON DELETE CASCADE,
    seg_index  INTEGER NOT NULL,
    t0         REAL NOT NULL,
    t1         REAL NOT NULL,
    text       TEXT NOT NULL,
    provider   TEXT NOT NULL DEFAULT 'asr.transcribe',
    infer_s    REAL,
    created_at REAL NOT NULL,
    PRIMARY KEY (clip_id, seg_index)
);

-- OCR rows hang off the clip the same way.
CREATE TABLE IF NOT EXISTS ocr (
    clip_id    TEXT NOT NULL REFERENCES clip(clip_id) ON DELETE CASCADE,
    t_ms       INTEGER NOT NULL,
    text       TEXT NOT NULL,
    box        TEXT,
    created_at REAL NOT NULL
);

-- Visual (scene / detection) rows hang off the clip the same way.
CREATE TABLE IF NOT EXISTS visual (
    clip_id    TEXT NOT NULL REFERENCES clip(clip_id) ON DELETE CASCADE,
    t_ms       INTEGER NOT NULL,
    label      TEXT NOT NULL,
    score      REAL NOT NULL,
    created_at REAL NOT NULL
);

-- Provenance: every search hit can name the clip it came from.  This is NOT lane B's
-- text_fts (that is FTS5 inside the index); this is the engine's own join table and
-- search is a LIKE over it, which is why a hit always carries clip_id + content_key.
CREATE TABLE IF NOT EXISTS clip_text (
    clip_id TEXT NOT NULL REFERENCES clip(clip_id) ON DELETE CASCADE,
    source  TEXT NOT NULL,              -- 'speech' | 'ocr' | 'visual'
    text    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS clip_text_src ON clip_text(source);

CREATE TABLE IF NOT EXISTS engine_meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
