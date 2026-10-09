"""Sotto index store: the one SQLite file that holds the record and the vectors.

Design + measured numbers: docs/research/07-index-search.md
Schema: schema.sql (same directory).

The one rule everything here obeys: IDENTITY IS content_key (whole-file SHA-256),
NEVER THE PATH.  Every write below is an upsert keyed on content_key or on the
table's primary key, so re-running any pass is a no-op rather than a duplicate.
That is what makes a rename free (one UPDATE, one row) and what lets the heavy
"promotion" pass re-run without redoing the light pass.

Threading: the whole index is scanned by numpy at <=2 threads; nothing here is
parallel.  See schema.sql for the crash-safety pragmas, which are MEASURED.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

import numpy as np

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

# Set BEFORE numpy is imported for any real work; the 2-thread lane budget is
# from the brief, not a preference (docs/research/07-index-search.md sec 1).
THREAD_ENV = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
              "NUMEXPR_NUM_THREADS")


def set_thread_budget(n: int = 2) -> None:
    for var in THREAD_ENV:
        os.environ[var] = str(n)


def connect(path: str | os.PathLike, *, create: bool = True) -> sqlite3.Connection:
    """Open the store and apply schema.sql (idempotent, CREATE IF NOT EXISTS)."""
    path = Path(path)
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(str(path), isolation_level=None)  # explicit BEGIN/COMMIT
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # foreign_keys is per-connection, and executescript cannot set it inside the
    # same transaction it opens, so re-assert it here.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def journal_mode(conn: sqlite3.Connection) -> str:
    return conn.execute("PRAGMA journal_mode").fetchone()[0]


# ---------------------------------------------------------------------------
# video  (== lane 08's asset table).  content_key is the identity.
# ---------------------------------------------------------------------------

_VIDEO_COLS = ("content_key", "file_key", "path", "size_bytes", "mtime_ns",
               "duration_ms", "codec", "w", "h", "fps", "bitrate", "last_seen_scan",
               "missing", "state")


def upsert_video(conn: sqlite3.Connection, *, content_key: str, path: str,
                 size_bytes: int, mtime_ns: int, duration_ms: int = 0,
                 file_key: str | None = None, codec: str | None = None,
                 w: int | None = None, h: int | None = None,
                 fps: float | None = None, bitrate: int | None = None,
                 last_seen_scan: int | None = None, missing: int = 0,
                 state: str = "discovered") -> int:
    """Idempotent on content_key.  Returns the video row id, new or existing.

    A file that moved has the same content_key and a new path -> this UPDATEs the
    path and clears `missing`, and returns the SAME id.  One row, no re-index.
    A file whose bytes changed has a new content_key -> a NEW row, by design
    (07-index-search.md sec 2: the old one is superseded, never deleted).
    """
    cur = conn.execute(
        f"""INSERT INTO video ({','.join(_VIDEO_COLS)})
            VALUES ({','.join('?' * len(_VIDEO_COLS))})
            ON CONFLICT(content_key) DO UPDATE SET
                path         = excluded.path,
                file_key     = COALESCE(excluded.file_key, video.file_key),
                size_bytes   = excluded.size_bytes,
                mtime_ns     = excluded.mtime_ns,
                duration_ms  = excluded.duration_ms,
                codec        = COALESCE(excluded.codec, video.codec),
                w            = COALESCE(excluded.w, video.w),
                h            = COALESCE(excluded.h, video.h),
                fps          = COALESCE(excluded.fps, video.fps),
                bitrate      = COALESCE(excluded.bitrate, video.bitrate),
                last_seen_scan = COALESCE(excluded.last_seen_scan, video.last_seen_scan),
                missing      = excluded.missing,
                state        = excluded.state
            RETURNING id""",
        (content_key, file_key, path, size_bytes, mtime_ns, duration_ms, codec, w,
         h, fps, bitrate, last_seen_scan, missing, state))
    row = cur.fetchone()
    if row is None:  # RETURNING unsupported on this sqlite build
        row = conn.execute("SELECT id FROM video WHERE content_key = ?",
                           (content_key,)).fetchone()
    return int(row[0])


def move_video(conn: sqlite3.Connection, content_key: str, new_path: str) -> int:
    """The rename case, stated on its own so nobody re-keys on the path."""
    return upsert_video(conn, content_key=content_key, path=new_path,
                        size_bytes=_size_of(conn, content_key),
                        mtime_ns=_mtime_of(conn, content_key),
                        last_seen_scan=None, missing=0)


def _size_of(conn: sqlite3.Connection, content_key: str) -> int:
    r = conn.execute("SELECT size_bytes FROM video WHERE content_key = ?",
                     (content_key,)).fetchone()
    return int(r[0]) if r else 0


def _mtime_of(conn: sqlite3.Connection, content_key: str) -> int:
    r = conn.execute("SELECT mtime_ns FROM video WHERE content_key = ?",
                     (content_key,)).fetchone()
    return int(r[0]) if r else 0


def mark_missing(conn: sqlite3.Connection, content_keys: list[str]) -> int:
    """`missing` is a STATE, never a delete: the transcript and the vectors stay
    searchable and the UI can say the file is gone (08-import-library.md)."""
    conn.executemany("UPDATE video SET missing = 1 WHERE content_key = ?",
                     [(k,) for k in content_keys])
    return len(content_keys)


# ---------------------------------------------------------------------------
# segment / transcript / ocr / embedding / marker
# ---------------------------------------------------------------------------

def upsert_segment(conn: sqlite3.Connection, *, video_id: int, start_ms: int,
                   end_ms: int, seg_id: int | None = None,
                   n_visual: int = 0, n_speech: int = 0, n_ocr: int = 0,
                   state: str = "pending") -> int:
    if seg_id is not None:
        conn.execute(
            """INSERT INTO segment (seg_id, video_id, start_ms, end_ms,
                                     n_visual, n_speech, n_ocr, state)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(seg_id) DO UPDATE SET
                   video_id = excluded.video_id, start_ms = excluded.start_ms,
                   end_ms   = excluded.end_ms,  n_visual = excluded.n_visual,
                   n_speech = excluded.n_speech, n_ocr    = excluded.n_ocr,
                   state    = excluded.state""",
            (seg_id, video_id, start_ms, end_ms, n_visual, n_speech, n_ocr, state))
        return seg_id
    return int(conn.execute(
        """INSERT INTO segment (video_id, start_ms, end_ms,
                                n_visual, n_speech, n_ocr, state)
           VALUES (?,?,?,?,?,?,?) RETURNING seg_id""",
        (video_id, start_ms, end_ms, n_visual, n_speech, n_ocr, state)).fetchone()[0])


def upsert_transcript(conn: sqlite3.Connection, *, seg_id: int, text: str,
                      text_norm: str, start_ms: int = 0, producer: str = "light",
                      model_sha256: str | None = None) -> None:
    """One ASR result per window.  INSERT OR IGNORE for the same model (a no-op,
    so promotion cannot redo the light pass), REPLACE when the model changes."""
    conn.execute(
        """INSERT INTO transcript (seg_id, start_ms, text, text_norm, producer,
                                  model_sha256)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(seg_id) DO UPDATE SET
               start_ms = excluded.start_ms, text = excluded.text,
               text_norm = excluded.text_norm, producer = excluded.producer,
               model_sha256 = excluded.model_sha256""",
        (seg_id, start_ms, text, text_norm, producer, model_sha256))


def upsert_ocr_lines(conn: sqlite3.Connection, seg_id: int,
                     lines: list[dict]) -> int:
    """lines: [{line_no, t_ms, t_end_ms, text_raw, text_norm, box, conf,
                engine, model_sha256, frame_ref}, ...] -- lane 02's shape."""
    rows = [(seg_id, int(l["line_no"]), int(l.get("t_ms", 0)),
             l.get("t_end_ms"), l.get("text_raw"), l.get("text_norm"),
             l.get("box"), l.get("conf"), l.get("engine"),
             l.get("model_sha256"), l.get("frame_ref")) for l in lines]
    conn.executemany(
        """INSERT INTO ocr (seg_id, line_no, t_ms, t_end_ms, text_raw, text_norm,
                            box, conf, engine, model_sha256, frame_ref)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(seg_id, line_no) DO UPDATE SET
               t_ms = excluded.t_ms, t_end_ms = excluded.t_end_ms,
               text_raw = excluded.text_raw, text_norm = excluded.text_norm,
               box = excluded.box, conf = excluded.conf,
               engine = excluded.engine, model_sha256 = excluded.model_sha256,
               frame_ref = excluded.frame_ref""", rows)
    return len(rows)


def _as_blob(vec: np.ndarray, dtype: str) -> bytes:
    a = np.ascontiguousarray(vec, dtype=np.float16 if dtype == "fp16" else np.float32)
    return a.tobytes()


def upsert_embeddings(conn: sqlite3.Connection, rows: list[tuple[int, str, np.ndarray]],
                      *, model: str, model_sha256: str | None = None,
                      dtype: str = "fp16", dim: int = 256) -> float:
    """rows: [(seg_id, channel, vec), ...].  Returns MEASURED ms/row.

    (seg_id, channel) is the work unit: the same channel with the same model is a
    no-op, a different model replaces the row and the change is detectable per
    row -- never a silent mix of two models in one result set.
    """
    payload = [(seg_id, channel, dim, dtype, _as_blob(vec, dtype), model,
                model_sha256) for seg_id, channel, vec in rows]
    t0 = time.perf_counter()
    conn.execute("BEGIN")
    conn.executemany(
        """INSERT INTO embedding (seg_id, channel, dim, dtype, vec, model,
                                 model_sha256)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(seg_id, channel) DO UPDATE SET
               dim = excluded.dim, dtype = excluded.dtype, vec = excluded.vec,
               model = excluded.model, model_sha256 = excluded.model_sha256,
               built_at = unixepoch()""", payload)
    conn.execute("COMMIT")
    return (time.perf_counter() - t0) * 1000.0 / max(1, len(payload))


def upsert_marker(conn: sqlite3.Connection, *, seg_id: int, kind: str,
                  value: str | None = None, source: str | None = None) -> None:
    conn.execute(
        """INSERT INTO marker (seg_id, kind, value, source) VALUES (?,?,?,?)
           ON CONFLICT(seg_id, kind) DO UPDATE SET
               value = excluded.value, source = excluded.source""",
        (seg_id, kind, value, source))


# ---------------------------------------------------------------------------
# load: fp16 blobs -> one fp32 matrix, cast ONCE at load (07 sec 3: fp16 is a
# DISK decision, never a compute one -- native fp16 matvec measured 8.8x slower).
# ---------------------------------------------------------------------------

def channel_blocks(rows) -> tuple[np.ndarray, dict[str, tuple[int, int]]]:
    """(order, blocks) for grouping loaded rows by channel.

    `order` is the permutation that puts the rows of each channel together;
    `blocks[channel] = (lo, hi)` is that channel's half-open range in the
    PERMUTED array.  Channels with no rows are simply absent from `blocks`, and
    an absent channel is how search.py knows it may skip the scan entirely.
    """
    if not rows:
        return np.zeros(0, np.int64), {}
    codes = np.array([r["channel"] for r in rows], dtype=object)
    uniq, code = np.unique(codes, return_inverse=True)
    order = np.argsort(code, kind="stable")
    sorted_code = code[order]
    blocks: dict[str, tuple[int, int]] = {}
    for i, name in enumerate(uniq):
        lo = int(np.searchsorted(sorted_code, i, side="left"))
        hi = int(np.searchsorted(sorted_code, i, side="right"))
        if hi > lo:
            blocks[str(name)] = (lo, hi)
    return order, blocks


def load_matrix(conn: sqlite3.Connection, *, channels: tuple[str, ...] | None = None,
                include_missing: bool = False) -> tuple[np.ndarray, np.ndarray,
                                                         list[str], np.ndarray,
                                                         dict[str, tuple[int, int]]]:
    """Returns (vectors fp32 [N,dim], seg_ids [N], channels [N], video_ids [N],
    blocks {channel: (lo, hi)}).

    ROWS ARE GROUPED BY CHANNEL.  This is the fix for the measured scale defect
    (_main/index_perf_profile.md): search.py used to scan the whole matrix once
    per RRF channel and mask the other channels' rows out afterwards, so with 3
    channels it moved 3x the bytes it needed and threw 2x of them away -- 93.7%
    of a query at n=211200, and O(N) on top of that.  Grouping at load makes each
    channel ONE CONTIGUOUS SLICE, so its KNN is a scan of its own rows only.

    Grouping costs no memory: the buffer is filled through `order`, and
    `vecs[lo:hi]` is then a view, not a copy.
    """
    sql = ("SELECT e.seg_id, e.channel, e.dim, e.dtype, e.vec, s.video_id "
           "FROM embedding e JOIN segment s ON s.seg_id = e.seg_id "
           "JOIN video v ON v.id = s.video_id")
    where = []
    if channels:
        where.append("e.channel IN (%s)" % ",".join("?" * len(channels)))
    if not include_missing:
        where.append("v.missing = 0")
    args = list(channels or [])
    if where:
        sql += " WHERE " + " AND ".join(where)
    rows = conn.execute(sql, args).fetchall()

    if not rows:
        return (np.zeros((0, 0), np.float32), np.zeros(0, np.int64), [],
                np.zeros(0, np.int64), {})

    dim = max(int(r["dim"]) for r in rows)
    order, blocks = channel_blocks(rows)
    vecs = np.empty((len(rows), dim), dtype=np.float32)
    for i, oi in enumerate(order):
        r = rows[oi]
        blob = r["vec"]
        a = np.frombuffer(blob, dtype=np.float16 if r["dtype"] == "fp16" else np.float32)
        vecs[i, :len(a)] = a.astype(np.float32)   # the one-and-only cast
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True).clip(1e-12)
    seg_ids = np.array([int(rows[oi]["seg_id"]) for oi in order], dtype=np.int64)
    chans = [rows[oi]["channel"] for oi in order]
    video_ids = np.array([int(rows[oi]["video_id"]) for oi in order], dtype=np.int64)
    return vecs, seg_ids, chans, video_ids, blocks


def segments_for(conn: sqlite3.Connection, seg_ids: list[int]) -> dict[int, sqlite3.Row]:
    """The answer path: one JOIN, seg_id -> start_ms -> path (0.011 ms MEASURED)."""
    out: dict[int, sqlite3.Row] = {}
    for i in range(0, len(seg_ids), 500):
        chunk = seg_ids[i:i + 500]
        q = ("SELECT s.seg_id, s.start_ms, s.end_ms, s.video_id, v.path, v.missing "
             "FROM segment s JOIN video v ON v.id = s.video_id "
             f"WHERE s.seg_id IN ({','.join('?' * len(chunk))})")
        for r in conn.execute(q, chunk):
            out[int(r["seg_id"])] = r
    return out


def store_bytes(conn: sqlite3.Connection) -> dict:
    """Real on-disk size, WAL included -- the MiB numbers must be measured."""
    page = conn.execute("PRAGMA page_size").fetchone()[0]
    wal = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
    db = Path(conn.execute("PRAGMA database_list").fetchone()[2])
    total = db.stat().st_size if db.exists() else 0
    for suffix in ("-wal", "-shm"):
        p = db.with_name(db.name + suffix)
        if p.exists():
            total += p.stat().st_size
    return {"page_size": page, "file_bytes": total,
            "file_mib": total / 1024 ** 2, "checkpoint": wal}