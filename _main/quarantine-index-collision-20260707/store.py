"""store.py -- the WRITER: a completed clip, then its transcript. The declared interface.

================================================================================
THE DECLARED INTERFACE -- what lane L1 (instant cut) and lane L2 (audio) hand me.
Lanes L1 and L2 own their files; this file is the contract they call. Nothing here
needs their code to exist, and nothing here calls into theirs.
================================================================================

TWO CALLS, IN THIS ORDER. Both are idempotent (the same payload twice = the same rows),
so a retry, a re-cut or a re-run of the background pass is free.

(1) WHEN THE CLIP FILE IS ON DISK -- L1, right after `perform_cut()` returns ok and
    `Mp4Writer::close()` has written the `moov` (src/capture/mp4_writer.h). This is
    `CutResult` (src/capture/replay.h:59-76) plus the ids L1 owns.

        ingest_clip(index, clip) -> IngestResult

    Payload -- a JSON object (L1 is C++; `src/engine/json.cpp` already parses one) or
    the mapping directly. Field by field, with the C++ field it comes from:

      clip_id       TEXT  REQUIRED  stable identity, L1's to mint ("clip_000123").
                               It is the PRIMARY KEY: re-cutting the same ring window
                               with the same id updates one row instead of duplicating.
      clip_path     TEXT  REQUIRED  the muxed .mp4                     (CutResult::path)
      h264_path     TEXT?          the raw Annex-B/AVC stream when one exists. Today the
                               muxer writes VIDEO ONLY -- there is no AAC anywhere on
                               disk and 8 of 8 sample clips carry no audio stream (a
                               measured fact of this repo), so both are NULL until L2
                               lands. Recorded now so the row never has to be rebuilt.
      aac_path      TEXT?          the AAC elementary stream, same caveat.
      started_at_s  REAL?          epoch seconds, the clip window START (not the cut time):
                               this is the axis a library-wide time filter runs on.
      duration_s    REAL?          seconds                             (clip_seconds)
      width/height  INT?           (Mp4Config::width/height) -- replay.cpp:57 pins 1920x1080
      fps           REAL?          (ModeNumbers::fps)
      size_bytes    INT?           (CutResult::bytes_written via Mp4Writer)
      source_device TEXT?          the capture device, e.g. "\\\\.\\DISPLAY1". This is a
                               FILTER axis in search(), so its spelling is L1's contract.
      mode          TEXT?          "instant" | "manual" | "highlight"
      content_key   TEXT?          whole-file SHA-256 (lane 08). Identity for the library
                               import path; NEVER the path (07-index-search.md:46).
      mtime_ns      INT?           (lane 08's identity column)

(2) WHEN THE BACKGROUND PASS FINISHES -- L2, after `asr.runner.transcribe()` returns
    the `done` event for that clip's wav (src/asr/runner.py:258-305). The payload is
    THAT OBJECT, VERBATIM and unparsed -- this function reads the keys the runner
    actually emits, not keys I wished for.

        ingest_asr_done(index, clip_id, done) -> IngestResult

    Keys read out of `done` (src/asr/runner.py:258-303): `segments[]`, each row being
    exactly what the stdout `segment` event carries (runner.py:230-240) --
    {i, start, end, audio_s, wall_s, chars, text} -- plus `n_segments`, `text`,
    `segment_mode`, `quantization`, `model_dir` for the producer tag. Times in those
    rows are SECONDS (3 dp), already offset by the runner's `--offset-s`; they become
    `start_ms`/`end_ms` here. See the unit law below.

ORDER IS GUARANTEED, not assumed: the clip row is written at the cut (S1, on the
critical path), the transcript hours later in the idle window (S3, background --
specs/01-capture-modes-and-scheduling.md:68-70). L2 therefore calls
`ingest_asr_done(clip_id=...)` with a clip id L1 already wrote.

THE UNIT LAW -- seconds in, milliseconds stored. Every producer this lane talks to
counts in seconds (`CutResult::clip_seconds` is a double; the ASR rows are 3-dp
seconds) and lane 07's schema is in ms (`start_ms`, `end_ms`, `duration_ms`). The
conversion happens ONCE, in `_ms()`, and nowhere else. Search takes seconds too, so
the two faces of the API agree and only the DB is in ms.
"""

from __future__ import annotations

import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from .schema import FTS_TABLE, transaction

__all__ = [
    "PRODUCER_ASR",
    "ClipRecord",
    "IngestResult",
    "normalise_text",
    "ingest_clip",
    "ingest_asr_done",
]

#: What `transcript.producer` says wrote a row (07-index-search.md:45: the producer, never the
#: table, is what distinguishes the light writer from lane 08's leased job queue).
PRODUCER_ASR = "asr:parakeet-tdt-0.6b-v3:int8"


def _ms(seconds: float) -> int:
    """THE unit boundary: seconds (what L1/L2 produce) -> milliseconds (what is stored)."""
    return int(round(float(seconds) * 1000))


def normalise_text(text: str) -> str:
    """The column FTS5 indexes. NFKC + casefold, every non-alphanumeric run -> one space.

    Casefold + diacritic handling are what make the lexical path usable on this corpus: the
    ASR emits unpunctuated text with no case structure (`specs/02-asr.md` section 3, the
    transcript is `" ".join` of raw model output), while the OCR channel that lane 07 wants in
    the same FTS list carries SHOUTED game tokens like `ERRO 0x80070005: ACESSO NEGADO`
    (07-index-search.md:53). The RAW text is stored alongside; this column is only the key.
    """
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text).casefold()
    out: list[str] = []
    for ch in folded:
        out.append(ch if ch.isalnum() else " ")
    return " ".join("".join(out).split())


@dataclass(frozen=True)
class ClipRecord:
    """One finished clip. L1's payload, typed. `from_mapping` is what the JSON path uses."""

    clip_id: str
    clip_path: str
    h264_path: str | None = None
    aac_path: str | None = None
    started_at_s: float | None = None
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    size_bytes: int | None = None
    source_device: str | None = None
    mode: str | None = None
    content_key: str | None = None
    file_key: str | None = None
    mtime_ns: int | None = None
    state: str = "recorded"
    missing: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ClipRecord":
        """Refuse loudly on a missing id or path -- a clip with no identity is a bug the index
        must not paper over with a synthetic key (same posture as specs/02-asr.md:9)."""
        clip_id = str(payload.get("clip_id") or "").strip()
        clip_path = str(payload.get("clip_path") or "").strip()
        if not clip_id:
            raise ValueError("index: clip payload has no clip_id; refusing to invent one")
        if not clip_path:
            raise ValueError(f"index: clip {clip_id!r} has no clip_path")
        unknown = set(payload) - {f for f in cls.__dataclass_fields__}
        if unknown:
            # Not fatal -- L1 may add fields -- but the caller is told, because a silently
            # dropped field is how a column stays empty forever without anyone noticing.
            print(f"index: clip {clip_id}: ignoring unknown field(s) {sorted(unknown)}",
                  file=sys.stderr)
        return cls(
            clip_id=clip_id,
            clip_path=clip_path,
            h264_path=payload.get("h264_path") or None,
            aac_path=payload.get("aac_path") or None,
            started_at_s=_opt_float(payload.get("started_at_s")),
            duration_s=_opt_float(payload.get("duration_s")),
            width=_opt_int(payload.get("width")),
            height=_opt_int(payload.get("height")),
            fps=_opt_float(payload.get("fps")),
            size_bytes=_opt_int(payload.get("size_bytes")),
            source_device=payload.get("source_device") or None,
            mode=payload.get("mode") or None,
            content_key=payload.get("content_key") or None,
            file_key=payload.get("file_key") or None,
            mtime_ns=_opt_int(payload.get("mtime_ns")),
            state=str(payload.get("state") or "recorded"),
            missing=int(payload.get("missing") or 0),
        )


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


@dataclass
class IngestResult:
    """What a write actually did -- counts, so a receipt can quote them instead of guessing."""

    clips: int = 0
    segments: int = 0
    transcripts: int = 0
    fts_rows: int = 0
    clip_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "clips": self.clips,
            "segments": self.segments,
            "transcripts": self.transcripts,
            "fts_rows": self.fts_rows,
            "clip_ids": list(self.clip_ids),
        }


_UPSERT_VIDEO_SQL = """
INSERT INTO video (id, content_key, file_key, path, h264_path, aac_path, size_bytes,
                   mtime_ns, duration_ms, w, h, fps, source_device, mode,
                   started_at_s, added_at_s, last_seen_scan_s, missing, state)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(id) DO UPDATE SET
    content_key      = COALESCE(excluded.content_key, video.content_key),
    file_key         = COALESCE(excluded.file_key, video.file_key),
    path             = excluded.path,
    h264_path        = COALESCE(excluded.h264_path, video.h264_path),
    aac_path         = COALESCE(excluded.aac_path, video.aac_path),
    size_bytes       = COALESCE(excluded.size_bytes, video.size_bytes),
    mtime_ns         = COALESCE(excluded.mtime_ns, video.mtime_ns),
    duration_ms      = COALESCE(excluded.duration_ms, video.duration_ms),
    w                = COALESCE(excluded.w, video.w),
    h                = COALESCE(excluded.h, video.h),
    fps              = COALESCE(excluded.fps, video.fps),
    source_device    = COALESCE(excluded.source_device, video.source_device),
    mode             = COALESCE(excluded.mode, video.mode),
    started_at_s     = COALESCE(excluded.started_at_s, video.started_at_s),
    added_at_s       = video.added_at_s,
    last_seen_scan_s = COALESCE(excluded.last_seen_scan_s, video.last_seen_scan_s),
    missing          = excluded.missing,
    state            = excluded.state
"""


def _upsert_clip_row(con: sqlite3.Connection, rec: "ClipRecord", now: float) -> None:
    """The one and only INSERT into `video`. Every nullable column is COALESCE'd against the
    stored row, so a later partial payload can never erase a value an earlier one supplied --
    except `missing` and `state`, which are exactly the facts that change after the first write."""
    con.execute(
        _UPSERT_VIDEO_SQL,
        (
            rec.clip_id, rec.content_key, rec.file_key, rec.clip_path, rec.h264_path,
            rec.aac_path, rec.size_bytes, rec.mtime_ns,
            _ms(rec.duration_s) if rec.duration_s is not None else 0,
            rec.width, rec.height, rec.fps, rec.source_device, rec.mode,
            rec.started_at_s, now, rec.started_at_s, rec.missing, rec.state,
        ),
    )


def ingest_clip(con: sqlite3.Connection, clip: ClipRecord | Mapping[str, Any]) -> IngestResult:
    """Upsert ONE completed clip. Idempotent on `clip_id` -- the same payload twice is one row."""
    rec = clip if isinstance(clip, ClipRecord) else ClipRecord.from_mapping(clip)
    now = time.time()
    with transaction(con):
        _upsert_clip_row(con, rec, now)
    return IngestResult(clips=1, clip_ids=[rec.clip_id])


def ingest_asr_done(
    con: sqlite3.Connection,
    clip_id: str,
    done: Mapping[str, Any],
    *,
    producer: str = PRODUCER_ASR,
    model_sha256: str | None = None,
) -> IngestResult:
    """Upsert the transcript of ONE clip from the ASR runner's `done` event, verbatim.

    `done` is exactly what `asr.runner.transcribe()` returns (src/asr/runner.py:258-305); the
    per-segment rows are exactly what its stdout `segment` events carry (runner.py:230-240).
    Nothing here re-derives text from audio and nothing here parses a transcript FILE -- if the
    payload lacks `segments`, the write is a no-op with a loud note, because an index that
    silently stores nothing is worse than one that refuses.
    """
    clip_id = str(clip_id or "").strip()
    if not clip_id:
        raise ValueError("index: ingest_asr_done needs the clip_id L1 wrote")

    known = con.execute("SELECT 1 FROM video WHERE id = ?", (clip_id,)).fetchone()
    if known is None:
        raise ValueError(
            f"index: no clip row {clip_id!r} -- call ingest_clip() first (S1 precedes S3: "
            "specs/01-capture-modes-and-scheduling.md:68-70)"
        )

    rows = done.get("segments")
    if rows is None:
        rows = []
    result = IngestResult(clip_ids=[clip_id])
    if not rows:
        # 0 segments is a MEANINGFUL outcome, not an error: the splitter drops silence-only
        # segments (src/asr/segment.py:102-103), so a silent clip transcribes to an empty
        # transcript and must stay searchable-as-nothing rather than being invented into text.
        print(
            f"index: clip {clip_id}: ASR done carries 0 segments "
            f"(n_segments={done.get('n_segments')!r}, {len(done.get('text') or '')} chars) -- "
            "nothing to index, and that is the measured outcome for a silent clip",
            file=sys.stderr,  # stderr, never stdout: stdout is an NDJSON channel elsewhere
        )
        return result

    created_at = time.time()
    with transaction(con):
        for row in rows:
            text = str(row.get("text") or "")
            start_ms = _ms(row.get("start", 0.0))
            end_ms = _ms(row.get("end", 0.0))
            con.execute(
                """
                INSERT INTO segment (video_id, start_ms, end_ms, n_speech, state)
                VALUES (?,?,?,?, 'closed')
                ON CONFLICT(video_id, start_ms) DO UPDATE SET
                    end_ms   = excluded.end_ms,
                    n_speech = MAX(segment.n_speech, excluded.n_speech),
                    state    = excluded.state
                """,
                (clip_id, start_ms, end_ms, 1),
            )
            seg_id = int(con.execute(
                "SELECT seg_id FROM segment WHERE video_id = ? AND start_ms = ?",
                (clip_id, start_ms),
            ).fetchone()[0])

            con.execute(
                """
                INSERT INTO transcript (seg_id, start_ms, end_ms, text, text_norm, producer,
                                        model_sha256, created_at_s)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(seg_id) DO UPDATE SET
                    start_ms     = excluded.start_ms,
                    end_ms       = excluded.end_ms,
                    text         = excluded.text,
                    text_norm    = excluded.text_norm,
                    producer     = excluded.producer,
                    model_sha256 = COALESCE(excluded.model_sha256, transcript.model_sha256),
                    created_at_s = excluded.created_at_s
                """,
                (seg_id, start_ms, end_ms, text, normalise_text(text), producer,
                 model_sha256, created_at),
            )
            # A plain fts5 table cannot be UPDATEd from the base table, so the row is replaced.
            # Both statements sit in the SAME transaction as the transcript: an index that can
            # disagree with its own text is not an index.
            con.execute(f"DELETE FROM {FTS_TABLE} WHERE seg_id = ?", (seg_id,))
            con.execute(
                f"INSERT INTO {FTS_TABLE}(seg_id, text_norm) VALUES (?, ?)",
                (seg_id, normalise_text(text)),
            )

            result.segments += 1
            result.transcripts += 1
            result.fts_rows += 1

        con.execute("UPDATE video SET state = 'transcribed' WHERE id = ?", (clip_id,))
    return result


def ingest_many(
    con: sqlite3.Connection, clips: Iterable[ClipRecord | Mapping[str, Any]]
) -> IngestResult:
    """Bulk convenience for a library import: ONE transaction for the whole batch, because the
    measured bulk path is 92 688 vectors/s against 0.113 ms per committed row (07-index-search.md
    :67, :23) -- the commit, not the insert, is what costs. Same statement as `ingest_clip`,
    through the same helper, so the two can never drift."""
    total = IngestResult()
    items = list(clips)
    if not items:
        return total
    now = time.time()
    with transaction(con):
        for item in items:
            rec = item if isinstance(item, ClipRecord) else ClipRecord.from_mapping(item)
            _upsert_clip_row(con, rec, now)
            total.clips += 1
            total.clip_ids.append(rec.clip_id)
    return total