#!/usr/bin/env python
"""Gate harness for the clip index: `python -m index.selftest --arm A --db FILE`.

Registered arms (`--arm`):
  A          a FRESH db: 6 clips / 9 segments written from a REAL ASR `done` payload, then
             named queries with their POPULATION and WINDOW. Every count is asserted.
  B          a SECOND run on the SAME db: idempotent re-ingest (counts unchanged), and an
             OLD-SHAPE v0 db migrated ADDITIVELY -- its row kept, its columns added, its
             transcript BACKFILLED into the FTS table so it is searchable.
  C          THE CONTROL. Arm A's assertion set, unchanged, against a COPY of the package with
             one guarantee reverted. Both mutants must go RED -- an instrument that cannot say
             NO is worthless (specs/02-asr.md:257, the house rule).
  D          two OS processes writing one file: no "database is locked", no duplicate rows,
             `PRAGMA integrity_check` ok.

`--expect red` inverts the verdict: the arm is SUPPOSED to fail, and the harness reports
`RED-as-expected` -- that is how arm C proves the gate can say no. Same convention as
`asr.parity`.

Exit code: 0 = every arm met its expectation · 1 = at least one did not.

THE FIXTURE IS REAL TEXT. Every transcript string below is copied verbatim from
`_main/runs/threads11/silence-t4-p1.json` -- the measured 11-segment silence-aligned run of
`plain-3600s.wav[900,1020)` (docs/research/11-onnx-threads.md:45: 814 chars, sha256 746DFD19,
byte-identical in all 8 arms of the sweep). Portuguese WITH its accents and English, including
the registered one-word difference between segment 3 and segment 11 (`clos`/`closed`, and
`Monday`/`year`). `--verify-fixture` re-reads that file and fails if the text embedded here has
drifted from it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

if __package__ in (None, ""):  # allow `python src/index/selftest.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from index.schema import FTS_TABLE, SCHEMA_VERSION, index_info, open_index  # noqa: E402
from index.search import SearchFilter, search_text  # noqa: E402
from index.store import ingest_asr_done, ingest_clip, normalise_text  # noqa: E402

ARMS = ("A", "B", "C", "D")
#: internal: arm D spawns two of these as separate OS processes.
ARMS_INTERNAL = ("D-writer",)
ALL_ARMS = ARMS + ARMS_INTERNAL

# ---------------------------------------------------------------------------------------------
# The fixture.  Real sentences, real times (seconds), a FIXED epoch so every number below is
# deterministic -- a gate that depends on wall-clock "now" is a gate that fails for a reason
# nobody can reproduce.
# ---------------------------------------------------------------------------------------------
T0 = 1761000000.0  # arbitrary and FIXED

#: Verbatim from `_main/runs/threads11/silence-t4-p1.json`, segments[] (chars = len(text)).
S_PT_RADIO = "O rádio anunciou que a ponte sobre o rio vai ser interditada na próxima segunda-feira."
S_PT_MORADORES = "Os moradores precisam de um caminho alternativo para chegar ao trabalho."
S_EN_MONDAY = "The radio announced that the bridge over the river will be clos next Monday."
S_EN_YEAR = "The radio announced that the bridge over the river will be closed next year."
S_EN_RESIDENTS = "Residents need an alternative route to get to work."

DEV1 = r"\\.\DISPLAY1"
DEV2 = r"\\.\DISPLAY2"

# (clip_id, device, duration_s, started_at_s, [(sentence, start_s, end_s), ...])
CLIPS: tuple[tuple[str, str, float, float, tuple[tuple[str, float, float], ...]], ...] = (
    ("clip-0001", DEV1, 30.0, T0 + 0,
     ((S_PT_RADIO, 0.0, 8.06), (S_EN_MONDAY, 8.06, 14.74))),
    ("clip-0002", DEV1, 12.5, T0 + 100, ((S_EN_RESIDENTS, 0.0, 13.76),)),
    ("clip-0003", DEV2, 45.0, T0 + 200, ((S_PT_MORADORES, 0.0, 6.98),)),
    ("clip-0004", DEV1, 8.0, T0 + 300, ((S_EN_YEAR, 0.0, 3.96),)),
    ("clip-0005", DEV2, 60.0, T0 + 400,
     ((S_PT_RADIO, 0.0, 8.06), (S_PT_MORADORES, 8.06, 15.04), (S_EN_MONDAY, 15.04, 21.72))),
    ("clip-0006", DEV2, 20.0, T0 + 500, ((S_EN_RESIDENTS, 0.0, 13.76),)),
)

N_CLIPS = len(CLIPS)
N_SEGS = sum(len(c[4]) for c in CLIPS)
DEVICE_PATH = r"H:\sotto\_moved\aireplay\_main\runs\clips"
_REPO = Path(__file__).resolve().parents[2]
FIXTURE_ARTEFACT = _REPO / "_main" / "runs" / "threads11" / "silence-t4-p1.json"


# ---------------------------------------------------------------------------------------------
# The two producers' payloads, exactly as L1 and L2 will hand them over.
# ---------------------------------------------------------------------------------------------
def clip_payload(clip_id: str, device: str, duration_s: float, started_at_s: float) -> dict:
    """L1's `CutResult` (src/capture/replay.h:59-76) as the JSON mapping `ingest_clip` takes."""
    return {
        "clip_id": clip_id,
        "clip_path": f"{DEVICE_PATH}\\{clip_id}.mp4",
        # Both NULL today and that is the measured truth: the muxer writes VIDEO ONLY
        # (src/capture/mp4_writer.h) and 8 of 8 sample clips carry no audio stream. The columns
        # exist now so the row never has to be rebuilt when L2 attaches audio.
        "h264_path": None,
        "aac_path": None,
        "started_at_s": float(started_at_s),
        "duration_s": duration_s,
        "width": 1920,
        "height": 1080,
        "fps": 60.0,
        "size_bytes": int(duration_s * 1_500_000),
        "source_device": device,
        "mode": "instant",
        "content_key": hashlib.sha256(clip_id.encode()).hexdigest(),
    }


def asr_payload(segments: tuple[tuple[str, float, float], ...], wav: str) -> dict:
    """L2's `done` event, VERBATIM in the shape `asr.runner.transcribe` emits
    (src/asr/runner.py:230-240 per segment row, :258-303 for the envelope)."""
    rows = [
        {
            "i": i,
            "start": round(start, 3),
            "end": round(end, 3),
            "audio_s": round(end - start, 3),
            "wall_s": round((end - start) / 7.29, 3),  # the measured RTFx at the thread knee
            "chars": len(text),
            "text": text,
        }
        for i, (text, start, end) in enumerate(segments)
    ]
    return {
        "type": "done",
        "label": Path(wav).name,
        "wav": wav,
        "model_dir": "models/parakeet-tdt-0.6b-v3-onnx",
        "quantization": "int8",
        "provider_requested": "cpu",
        "segment_mode": "silence",
        "offset_s": 0.0,
        "audio_s": round(segments[-1][2], 3),
        "n_segments": len(rows),
        "seg_median_s": round(sorted(r["audio_s"] for r in rows)[len(rows) // 2], 3),
        "seg_max_s": round(max(r["audio_s"] for r in rows), 3),
        "load_s": 2.31,
        "infer_s": 12.5,
        "rtfx_infer": 7.29,
        "level": {"n_events": 0, "hz": 10, "peak": 0.0},
        "segments": rows,
        "text": " ".join(r["text"] for r in rows),
    }


def _wipe(db: Path) -> None:
    """A FRESH db means fresh: the -wal and -shm siblings go too, or arm A inherits a hot WAL."""
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            p.unlink()


def _seed_db_on(con) -> None:
    """Both producers, in order, on the caller's connection: L1's cut, then L2's pass."""
    for clip_id, device, duration_s, started, segments in CLIPS:
        ingest_clip(con, clip_payload(clip_id, device, duration_s, started))
        ingest_asr_done(con, clip_id, asr_payload(segments, f"{DEVICE_PATH}\\{clip_id}.wav"))


def _seed(db: Path) -> None:
    con = open_index(db)
    try:
        _seed_db_on(con)
    finally:
        con.close()


def _check(checks: list[dict], name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _no_window() -> dict:
    """Rule 1 of the house brief: this harness spawns real processes, and a stray console on
    the owner's screen has already got two lanes shouted at. `CREATE_NO_WINDOW` on Windows,
    nothing anywhere else."""
    if os.name != "nt":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


# ---------------------------------------------------------------------------------------------
# ARM A -- fresh db, write, search.  Every assertion names its POPULATION and its WINDOW.
# ---------------------------------------------------------------------------------------------
def arm_a(db: Path) -> dict:
    checks: list[dict] = []
    _wipe(db)
    con = open_index(db)
    try:
        info0 = index_info(con)
        _seed_db_on(con)
        info = index_info(con)

        _check(checks, "fts5-probed-on-this-build", info0["fts5"],
               f"sqlite {info0['sqlite_version']}")
        _check(checks, "journal-mode-is-wal", info0["journal_mode"].lower() == "wal",
               info0["journal_mode"])
        _check(checks, "population.clips", info["rows"]["video"] == N_CLIPS,
               f"clips={info['rows']['video']} of {N_CLIPS}")
        _check(checks, "population.segments", info["rows"]["segment"] == N_SEGS,
               f"segments={info['rows']['segment']} of {N_SEGS}")
        _check(checks, "population.transcripts", info["rows"]["transcript"] == N_SEGS,
               f"transcripts={info['rows']['transcript']} of {N_SEGS}")
        _check(checks, "population.fts-rows", info["rows"][FTS_TABLE] == N_SEGS,
               f"fts={info['rows'][FTS_TABLE]} of {N_SEGS}")
        _check(checks, "integrity", info["integrity_check"] == "ok", info["integrity_check"])

        # -- the unit law, read back from the stored row rather than from the write's claim ---
        dur = con.execute("SELECT duration_ms FROM video WHERE id = 'clip-0005'").fetchone()[0]
        _check(checks, "unit.seconds-to-ms", dur == 60000, f"clip-0005 duration_ms={dur}")
        seg = con.execute(
            "SELECT start_ms, end_ms FROM segment WHERE video_id='clip-0001' "
            "ORDER BY start_ms LIMIT 1").fetchone()
        _check(checks, "unit.segment-start-ms", seg[0] == 0 and seg[1] == 8060,
               f"start_ms={seg[0]} end_ms={seg[1]}")

        # -- A1: a Portuguese-only word.  population 6 clips, WINDOW = the whole library ------
        r = search_text(con, "segunda")
        _check(checks, "A1.segunda-hits", r.total_hits == 2,
               f"found={r.total_hits} of pop {r.population}")
        _check(checks, "A1.segunda-clips", r.matched_clips == 2, f"clips={r.matched_clips}")
        _check(checks, "A1.segunda-population", r.population == N_CLIPS, f"pop={r.population}")
        _check(checks, "A1.every-hit-carries-the-token",
               all("segunda" in normalise_text(h["text"]) for h in r.hits),
               "no hit without the word")

        # -- A2: an ASCII token; FTS5 and the LIKE fallback must AGREE -----------------------
        r = search_text(con, "bridge")
        _check(checks, "A2.bridge-hits", r.total_hits == 3,
               f"found={r.total_hits} of pop {r.population}")
        _check(checks, "A2.bridge-clips", r.matched_clips == 3, f"clips={r.matched_clips}")
        r_like = search_text(con, "bridge", use_fts=False)
        _check(checks, "A2.like-mode-is-live", r_like.mode == "like", r_like.mode)
        _check(checks, "A2.like-equals-fts",
               sorted(h["seg_id"] for h in r_like.hits) == sorted(h["seg_id"] for h in r.hits),
               f"like={len(r_like.hits)} fts={len(r.hits)}")

        # -- A3: diacritic folding.  `próxima` exists ONLY in the accented Portuguese text, so
        #        an UNACCENTED query finding it can only come from `remove_diacritics 2`. The
        #        LIKE fallback cannot do it (text_norm keeps the accent) -- measured here, and
        #        the reason FTS5 stays the default rather than "just use LIKE".
        r_acc = search_text(con, "próxima")
        r_fold = search_text(con, "proxima")
        _check(checks, "A3.accented-query", r_acc.total_hits == 2,
               f"'próxima' found={r_acc.total_hits} of pop {r_acc.population}")
        _check(checks, "A3.unaccented-query-folds", r_fold.total_hits == 2,
               f"'proxima' found={r_fold.total_hits} -- same hits, the accent was folded")
        _check(checks, "A3.fold-hits-identical",
               sorted(h["seg_id"] for h in r_fold.hits) == sorted(h["seg_id"] for h in r_acc.hits),
               "folded and accented queries must select the same rows")
        r_like_fold = search_text(con, "proxima", use_fts=False)
        _check(checks, "A3.like-cannot-fold", r_like_fold.total_hits == 0,
               f"LIKE found={r_like_fold.total_hits}: the fallback is weaker, as documented")
        # `radio` matches the accented Portuguese AND the two English sentences, so the two
        # spellings are equal here -- 5 segments over 3 clips.
        r_radio = search_text(con, "radio")
        _check(checks, "A3.radio-covers-pt-and-en",
               r_radio.total_hits == 5 and r_radio.matched_clips == 3,
               f"found={r_radio.total_hits} clips={r_radio.matched_clips}")

        # -- A4: the registered model difference, one word, exactly one hit ------------------
        r_year = search_text(con, "year")
        _check(checks, "A4.year-is-one-hit", r_year.total_hits == 1, f"found={r_year.total_hits}")
        _check(checks, "A4.year-is-clip-0004",
               bool(r_year.hits) and r_year.hits[0]["clip_id"] == "clip-0004",
               r_year.hits[0]["clip_id"] if r_year.hits else "none")

        # -- A5: filter by DEVICE.  population = DISPLAY2 clips = 3 --------------------------
        r_dev = search_text(con, "bridge", SearchFilter(device=DEV2))
        _check(checks, "A5.device-population", r_dev.population == 3, f"pop={r_dev.population}")
        _check(checks, "A5.device-hits", r_dev.total_hits == 1, f"found={r_dev.total_hits}")
        _check(checks, "A5.device-is-respected",
               all(h["source_device"] == DEV2 for h in r_dev.hits), "no foreign device in hits")

        # -- A6: filter by TIME WINDOW [T0+300, T0+1000) -- population 3, 2 hits ------------
        r_win = search_text(con, "bridge", SearchFilter(since_s=T0 + 300, until_s=T0 + 1000))
        _check(checks, "A6.window-population", r_win.population == 3, f"pop={r_win.population}")
        _check(checks, "A6.window-hits", r_win.total_hits == 2, f"found={r_win.total_hits}")
        _check(checks, "A6.window-excludes-before",
               all(h["started_at_s"] >= T0 + 300 for h in r_win.hits), "no hit before the window")
        r_win2 = search_text(con, "bridge", SearchFilter(since_s=T0 + 1000))
        _check(checks, "A6.empty-window-is-empty", r_win2.total_hits == 0,
               f"found={r_win2.total_hits}")

        # -- A7: filter by DURATION >= 40 s -- population 2 (45 s and 60 s) ------------------
        r_dur = search_text(con, "segunda", SearchFilter(min_duration_s=40.0))
        _check(checks, "A7.duration-population", r_dur.population == 2, f"pop={r_dur.population}")
        _check(checks, "A7.duration-hits", r_dur.total_hits == 1, f"found={r_dur.total_hits}")
        r_band = search_text(con, "segunda",
                             SearchFilter(min_duration_s=40.0, max_duration_s=50.0))
        _check(checks, "A7.duration-band", r_band.total_hits == 0,
               f"found={r_band.total_hits} (no Portuguese clip is 40-50 s long)")

        # -- A8: AND vs OR --------------------------------------------------------------------
        r_and = search_text(con, "segunda workday")
        _check(checks, "A8.and-is-strict", r_and.total_hits == 0, f"found={r_and.total_hits}")
        r_or = search_text(con, "segunda workday", require_all=False)
        _check(checks, "A8.or-is-loose", r_or.total_hits == 2, f"found={r_or.total_hits}")

        # -- A9: hostile queries must NOT raise.  Every one of these is FTS5 syntax. ----------
        for hostile in ('"', "*()", "AND OR NEAR", '""', "-", "^", "segunda*",
                        "NEAR(segunda feira)", "*", "  ", "segunda AND", "col:val"):
            try:
                rr = search_text(con, hostile)
                _check(checks, f"A9.hostile[{hostile}]", rr.mode in ("fts5", "like", "empty"),
                       f"mode={rr.mode} found={rr.total_hits}")
            except sqlite3.Error as exc:
                _check(checks, f"A9.hostile[{hostile}]", False,
                       f"raised {type(exc).__name__}: {exc}")

        # -- A10: an empty query is "no query", never "everything" ---------------------------
        r_empty = search_text(con, "")
        _check(checks, "A10.empty-mode", r_empty.mode == "empty", r_empty.mode)
        _check(checks, "A10.empty-not-everything", r_empty.total_hits == 0,
               f"found={r_empty.total_hits} (a blank box must not dump the library)")

        # -- A11: a hit carries enough to open the file at mm:ss.s ---------------------------
        hit = search_text(con, "segunda").hits[0]
        for field in ("seg_id", "clip_id", "clip_path", "source_device", "start_ms", "end_ms",
                      "text", "producer"):
            _check(checks, f"A11.hit-has-{field}", hit.get(field) is not None,
                   str(hit.get(field)))

        # -- A12: `limit` truncation is visible, never silent --------------------------------
        r_lim = search_text(con, "radio", limit=1)
        _check(checks, "A12.limit-truncates", len(r_lim.hits) == 1, f"len={len(r_lim.hits)}")
        _check(checks, "A12.truncation-is-reported", r_lim.truncated and r_lim.total_hits == 5,
               f"truncated={r_lim.truncated} total={r_lim.total_hits}")

        # -- A13: a `missing` file is not a hit unless the caller asks ------------------------
        con.execute("UPDATE video SET missing = 1 WHERE id = 'clip-0005'")
        r_miss = search_text(con, "segunda")
        _check(checks, "A13.missing-excluded", r_miss.total_hits == 1, f"found={r_miss.total_hits}")
        r_miss2 = search_text(con, "segunda", SearchFilter(include_missing=True))
        _check(checks, "A13.missing-includable", r_miss2.total_hits == 2,
               f"found={r_miss2.total_hits}")
        con.execute("UPDATE video SET missing = 0 WHERE id = 'clip-0005'")

        return {
            "arm": "A",
            "ok": all(c["ok"] for c in checks),
            "n_checks": len(checks),
            "n_failed": sum(1 for c in checks if not c["ok"]),
            "population": {"clips": N_CLIPS, "segments": N_SEGS},
            "window": {"since_s": None, "until_s": None, "note": "whole library"},
            "rows": info["rows"],
            "checks": checks,
        }
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------
# ARM B -- a second run on the SAME db, and the additive migration of an OLD-SHAPE db.
# ---------------------------------------------------------------------------------------------
_LEGACY_VIDEO = """
CREATE TABLE video (
    id TEXT PRIMARY KEY, content_key TEXT, file_key TEXT, path TEXT NOT NULL,
    size_bytes INTEGER, mtime_ns INTEGER, duration_ms INTEGER NOT NULL DEFAULT 0,
    w INTEGER, h INTEGER, fps REAL, added_at_s REAL, last_seen_scan_s REAL,
    missing INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'recorded'
)
"""
_LEGACY_SEGMENT = """
CREATE TABLE segment (
    seg_id INTEGER PRIMARY KEY, video_id TEXT NOT NULL, start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL, n_visual INTEGER NOT NULL DEFAULT 0,
    n_speech INTEGER NOT NULL DEFAULT 0, n_ocr INTEGER NOT NULL DEFAULT 0,
    state TEXT NOT NULL DEFAULT 'closed', UNIQUE (video_id, start_ms)
)
"""
_LEGACY_TRANSCRIPT = """
CREATE TABLE transcript (
    seg_id INTEGER PRIMARY KEY, start_ms INTEGER NOT NULL, end_ms INTEGER NOT NULL,
    text TEXT NOT NULL, text_norm TEXT NOT NULL, producer TEXT, model_sha256 TEXT,
    created_at_s REAL
)
"""


def arm_b(db: Path) -> dict:
    checks: list[dict] = []
    before = open_index(db)
    rows_before = index_info(before)["rows"]
    before.close()

    # B1/B2/B3 -- re-open and re-ingest the SAME db.
    con = open_index(db)
    try:
        info1 = index_info(con)
        _check(checks, "B1.schema-version-stable", info1["schema_version"] == SCHEMA_VERSION,
               f"{info1['schema_version']} of {SCHEMA_VERSION}")
        _seed_db_on(con)
        info2 = index_info(con)
        _check(checks, "B2.idempotent-rows", info2["rows"] == rows_before,
               f"before={rows_before} after={info2['rows']}")
        _check(checks, "B2.integrity-after-replay", info2["integrity_check"] == "ok",
               info2["integrity_check"])

        # L1 re-cuts the same clip_id with a partial payload; nothing already known may vanish.
        first = dict(con.execute("SELECT * FROM video WHERE id = 'clip-0001'").fetchone())
        con.execute("UPDATE video SET aac_path = ? WHERE id = 'clip-0001'",
                    (f"{DEVICE_PATH}\\clip-0001.aac",))
        partial = clip_payload("clip-0001", DEV1, 30.0, T0)
        for key in ("width", "height", "fps", "size_bytes", "source_device", "content_key",
                    "started_at_s", "aac_path"):
            partial.pop(key, None)
        ingest_clip(con, partial)
        after = dict(con.execute("SELECT * FROM video WHERE id = 'clip-0001'").fetchone())
        _check(checks, "B3.partial-keeps-device", after["source_device"] == first["source_device"],
               str(after["source_device"]))
        _check(checks, "B3.partial-keeps-width", after["w"] == first["w"], str(after["w"]))
        _check(checks, "B3.partial-keeps-accent-path",
               after["aac_path"] == f"{DEVICE_PATH}\\clip-0001.aac", str(after["aac_path"]))
        _check(checks, "B3.rows-unchanged", index_info(con)["rows"] == rows_before,
               "an upsert must never add a row")
    finally:
        con.close()

    # B4/B5 -- an OLD-SHAPE v0 db: lane 07's original `video`, one row, one transcript, no FTS.
    legacy = db.with_name(db.stem + "-legacy-v0.db")
    _wipe(legacy)
    raw = sqlite3.connect(str(legacy), isolation_level=None)
    raw.execute(_LEGACY_VIDEO)
    raw.execute(_LEGACY_SEGMENT)
    raw.execute(_LEGACY_TRANSCRIPT)
    raw.execute("INSERT INTO video (id, path, duration_ms, state) VALUES (?,?,?,?)",
                ("old-clip", r"H:\old\old-clip.mp4", 30000, "recorded"))
    raw.execute("INSERT INTO segment (video_id, start_ms, end_ms) VALUES (?,?,?)",
                ("old-clip", 0, 8060))
    raw.execute(
        "INSERT INTO transcript (seg_id, start_ms, end_ms, text, text_norm) VALUES (1,0,8060,?,?)",
        (S_PT_RADIO, normalise_text(S_PT_RADIO)),
    )
    raw.execute("PRAGMA user_version = 0")
    raw.close()

    con = open_index(legacy)
    try:
        info3 = index_info(con)
        _check(checks, "B4.version-migrated", info3["schema_version"] == SCHEMA_VERSION,
               f"{info3['schema_version']}")
        _check(checks, "B4.row-survived", info3["rows"]["video"] == 1,
               f"video={info3['rows']['video']}")
        _check(checks, "B4.segment-survived", info3["rows"]["segment"] == 1, "")
        _check(checks, "B4.transcript-survived", info3["rows"]["transcript"] == 1, "")
        _check(checks, "B4.path-intact",
               con.execute("SELECT path FROM video WHERE id='old-clip'").fetchone()[0]
               == r"H:\old\old-clip.mp4", "")
        _check(checks, "B4.duration-intact",
               con.execute("SELECT duration_ms FROM video WHERE id='old-clip'").fetchone()[0]
               == 30000, "")
        for col in ("source_device", "h264_path", "aac_path", "started_at_s", "mode"):
            _check(checks, f"B4.column-added[{col}]",
                   col in {r[1] for r in con.execute("PRAGMA table_info(video)")}, "")
        _check(checks, "B4.fts-table-created", info3["fts5"], "")
        _check(checks, "B4.fts-backfilled", info3["rows"][FTS_TABLE] == 1,
               f"fts={info3['rows'][FTS_TABLE]}: an index without the old row answers wrong")
        r_old = search_text(con, "segunda")
        _check(checks, "B4.old-row-is-searchable", r_old.total_hits == 1,
               f"found={r_old.total_hits}")
        _check(checks, "B4.integrity", info3["integrity_check"] == "ok", info3["integrity_check"])

        # B5 -- a NEWER schema is refused loudly, never silently downgraded.
        con.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
        con.close()
        try:
            open_index(legacy)
            _check(checks, "B5.newer-schema-refused", False, "it OPENED a newer db")
        except RuntimeError as exc:
            _check(checks, "B5.newer-schema-refused", "NEWER" in str(exc), str(exc)[:90])
    finally:
        # `Connection.close()` is idempotent in CPython's sqlite3 and B5 deliberately closed
        # `con` before re-opening it, so a bare close here cannot raise.
        con.close()

    return {
        "arm": "B",
        "ok": all(c["ok"] for c in checks),
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["ok"]),
        "rows_before": rows_before,
        "population": {"clips": N_CLIPS, "segments": N_SEGS},
        "window": {"since_s": None, "until_s": None, "note": "whole library"},
        "checks": checks,
    }


# ---------------------------------------------------------------------------------------------
# ARM C -- THE CONTROL.
#
# On the wording: reverting the ASSERTIONS themselves would make the arm vacuously GREEN and
# would prove nothing. So what is reverted is the GUARANTEE those assertions measure, and the
# assertion set is carried over unchanged. Each mutant is built from an anchor line that must
# occur EXACTLY ONCE (if the live file moves, building the control fails loudly instead of
# reporting a RED that proves nothing), and the copy runs in its OWN process so the mutation is
# actually loaded.
# ---------------------------------------------------------------------------------------------
MUTANTS: dict[str, tuple[str, str, str]] = {
    # name: (file, the exact live line, the line that replaces it)
    "unit": (
        "store.py",
        'return int(round(float(seconds) * 1000))',
        'return int(float(seconds))  # MUTANT: seconds stored as seconds',
    ),
    # The QUOTING, not the tokeniser: with the quotes gone, a raw `AND`/`NEAR`/`col:val` reaches
    # FTS5 as syntax and `MATCH` raises. This is the exact defect the A9 hostile set exists for,
    # so it is the exact thing the control must prove the gate can see.
    "escape": (
        "search.py",
        """    return joiner.join('"' + t.replace('"', '""') + '"*' for t in tokens), tokens""",
        '    return joiner.join(tokens), tokens  # MUTANT: no quoting, the query is FTS5 syntax',
    ),
}


def _make_mutant(name: str, root: Path) -> dict:
    if name not in MUTANTS:
        raise ValueError(f"unknown mutant {name!r}; expected one of {sorted(MUTANTS)}")
    filename, old, new = MUTANTS[name]
    pkg = root / "index"
    if pkg.exists():
        shutil.rmtree(pkg)
    shutil.copytree(Path(__file__).resolve().parent, pkg)
    cache = pkg / "__pycache__"
    if cache.exists():  # a stale .pyc must never win over the mutation
        shutil.rmtree(cache)
    target = pkg / filename
    live_bytes = target.read_bytes()
    text = live_bytes.decode("utf-8")
    occurrences = text.count(old)
    if occurrences != 1:
        raise RuntimeError(
            f"index.selftest: mutant {name!r} needs its anchor line exactly once in "
            f"{filename}, found {occurrences}. The CONTROL cannot be built -- the live file "
            "moved, and a no-op mutation that still reported RED would be theatre."
        )
    target.write_text(text.replace(old, new), encoding="utf-8")
    return {
        "mutant": name,
        "file": filename,
        "anchor_occurrences": occurrences,
        "old": old.strip(),
        "new": new.strip(),
        "live_sha256": hashlib.sha256(live_bytes).hexdigest()[:16],
        "mutant_sha256": hashlib.sha256(target.read_bytes()).hexdigest()[:16],
    }


def _run_arm_a_in(root: Path, db: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "index.selftest", "--arm", "A", "--db", str(db),
         "--json", str(db.with_suffix(".json"))],
        cwd=str(root), env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=300, **_no_window(),
    )


def arm_c(db: Path, work: Path) -> dict:
    checks: list[dict] = []
    work.mkdir(parents=True, exist_ok=True)
    for name in sorted(MUTANTS):
        mroot = work / f"mutant-{name}"
        mroot.mkdir(parents=True, exist_ok=True)
        mdb = mroot / "mutant.db"
        try:
            minfo = _make_mutant(name, mroot)
        except RuntimeError as exc:
            _check(checks, f"C.{name}.control-buildable", False, str(exc))
            continue
        _check(checks, f"C.{name}.copy-differs",
               minfo["live_sha256"] != minfo["mutant_sha256"],
               f"{minfo['live_sha256']} -> {minfo['mutant_sha256']}")
        proc = _run_arm_a_in(mroot, mdb)
        _check(checks, f"C.{name}.goes-RED", proc.returncode != 0,
               f"rc={proc.returncode} -- 0 would mean the gate CANNOT see this defect")
        detail = ""
        report = mdb.with_suffix(".json")
        if report.exists():
            try:
                payload = json.loads(report.read_text(encoding="utf-8"))
                failed = [c["name"] for c in (payload.get("checks") or []) if not c["ok"]]
                detail = f"arm A red on {len(failed)} check(s): {failed[:6]}"
            except (OSError, ValueError, TypeError) as exc:
                detail = f"the mutant report was unreadable ({exc}); stderr={proc.stderr[-200:]}"
        _check(checks, f"C.{name}.red-is-informative", bool(detail),
               detail or "no detail captured: the mutant died before it could report")
        minfo["rc"] = proc.returncode
        minfo["detail"] = detail
        checks.append({"name": f"C.{name}.mutation", "ok": True,
                       "detail": f"{minfo['file']}: {minfo['old']}  ->  {minfo['new']}"})

    return {
        "arm": "C",
        "ok": all(c["ok"] for c in checks),
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["ok"]),
        "population": {"clips": N_CLIPS, "segments": N_SEGS},
        "window": {"since_s": None, "until_s": None, "note": "whole library"},
        "checks": checks,
    }


# ---------------------------------------------------------------------------------------------
# ARM D -- two OS processes, one file.
# ---------------------------------------------------------------------------------------------
D_PARTS = {
    1: ("clip-0001", "clip-0002", "clip-0005"),
    2: ("clip-0003", "clip-0004", "clip-0006"),
}
#: process 2 ALSO rewrites clip-0001, so the two writers contend for the SAME ROW and not
#: merely for the same file -- the case that actually deadlocks a naive writer.
D_SHARED = "clip-0001"
#: How many times each process rewrites its clips. Without this the whole arm is theatre: one
#: write measured 0.9 ms, so two processes launched back to back never overlap and "no lock
#: error" would be a claim about nothing.
D_ROUNDS = 25


def _barrier(work: Path, part: int, timeout_s: float = 60.0) -> float:
    """Wait for BOTH writers to be up before either writes -- otherwise process 1 finishes
    before process 2 has even opened the file and the arm measures nothing. Returns the wall
    clock the write loop started at (a CLOCK BOTH PROCESSES AGREE ON, which is what makes the
    overlap assertion below possible)."""
    work.mkdir(parents=True, exist_ok=True)
    (work / f"ready{part}").write_text(str(os.getpid()), encoding="utf-8")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if (work / "ready1").exists() and (work / "ready2").exists():
            return time.time()
        time.sleep(0.005)
    print(f"index.selftest: barrier timed out for part {part}; writing anyway", file=sys.stderr)
    return time.time()


def arm_d_writer(db: Path, part: int, work: Path, rounds: int = D_ROUNDS) -> dict:
    by_id = {c[0]: c for c in CLIPS}
    out: dict = {"part": part, "rounds": rounds, "clips": [], "segments": 0,
                 "writes": 0, "errors": [], "t_start": 0.0, "t_end": 0.0}
    con = open_index(db)
    try:
        targets = list(D_PARTS[part])
        if part == 2:
            targets.append(D_SHARED)  # the contended row, every round
        out["t_start"] = _barrier(work, part)
        for _round in range(rounds):
            for clip_id in targets:
                _, device, duration_s, started, segments = by_id[clip_id]
                try:
                    ingest_clip(con, clip_payload(clip_id, device, duration_s, started))
                    res = ingest_asr_done(con, clip_id,
                                          asr_payload(segments, f"{DEVICE_PATH}\\{clip_id}.wav"))
                    out["clips"].append(clip_id)
                    out["segments"] += res.segments
                    out["writes"] += 1
                except sqlite3.Error as exc:
                    out["errors"].append(f"{type(exc).__name__}: {exc}")
        out["t_end"] = time.time()
    finally:
        con.close()
    out["locked"] = any("locked" in e.lower() or "busy" in e.lower() for e in out["errors"])
    return out


def arm_d(db: Path, work: Path) -> dict:
    checks: list[dict] = []
    # This arm owns `work/d-race` and NOTHING else. An earlier version wiped the caller's whole
    # work dir, which deleted the other arms' reports -- and the gate's own log, raising
    # PermissionError on Windows and taking the arm down with it.
    race = work / "d-race"
    if race.exists():  # stale ready-markers from a previous run would fake the barrier
        shutil.rmtree(race)
    race.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["PYTHONIOENCODING"] = "utf-8"
    procs = {
        part: subprocess.Popen(
            [sys.executable, "-m", "index.selftest", "--arm", "D-writer",
             "--db", str(db), "--work", str(race), "--part", str(part),
             "--json", str(race / f"d{part}.json")],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", **_no_window(),
        )
        for part in (1, 2)
    }
    reports: dict[int, dict] = {}
    for part, proc in procs.items():
        _stdout, stderr = proc.communicate(timeout=600)
        payload = None
        jpath = race / f"d{part}.json"
        if jpath.exists():
            try:
                payload = json.loads(jpath.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                payload = None
        reports[part] = {"rc": proc.returncode, "payload": payload,
                         "stderr_tail": stderr.strip()[-300:]}

    for part in (1, 2):
        rep = reports[part]
        _check(checks, f"D.part{part}.rc0", rep["rc"] == 0,
               f"rc={rep['rc']} stderr={rep['stderr_tail'][-160:]}")
        _check(checks, f"D.part{part}.no-lock-error", not (rep["payload"] or {}).get("locked"),
               str((rep["payload"] or {}).get("errors")))

    # THE ARM IS VACUOUS UNLESS THEY ACTUALLY OVERLAPPED.  Each writer stamped its write loop
    # with a clock both processes share, so the two intervals' intersection is checkable: if it
    # is empty the two writers never contended and "no locked db" says nothing about the schema.
    w1 = reports[1].get("payload") or {}
    w2 = reports[2].get("payload") or {}
    lo = max(float(w1.get("t_start") or 0), float(w2.get("t_start") or 0))
    hi = min(float(w1.get("t_end") or 0), float(w2.get("t_end") or 0))
    _check(checks, "D.writers-overlapped", 0 < hi - lo,
           f"writer windows [{w1.get('t_start')},{w1.get('t_end')}] and "
           f"[{w2.get('t_start')},{w2.get('t_end')}] overlap by {round(hi - lo, 4)} s "
           f"({w1.get('rounds')}/{w2.get('rounds')} rounds each)")
    _check(checks, "D.both-writers-wrote",
           (w1.get("writes") or 0) > 0 and (w2.get("writes") or 0) > 0,
           f"writes={w1.get('writes')}/{w2.get('writes')}")

    con = open_index(db)
    try:
        info = index_info(con)
        _check(checks, "D.clips-written-once", info["rows"]["video"] == N_CLIPS,
               f"video={info['rows']['video']} of {N_CLIPS} (a duplicate is a lost update)")
        _check(checks, "D.segments-written-once", info["rows"]["segment"] == N_SEGS,
               f"segment={info['rows']['segment']} of {N_SEGS}")
        _check(checks, "D.transcripts-written-once", info["rows"]["transcript"] == N_SEGS,
               f"transcript={info['rows']['transcript']} of {N_SEGS}")
        _check(checks, "D.fts-not-duplicated", info["rows"][FTS_TABLE] == N_SEGS,
               f"fts={info['rows'][FTS_TABLE]} of {N_SEGS}")
        _check(checks, "D.integrity", info["integrity_check"] == "ok", info["integrity_check"])
        _check(checks, "D.searchable-after-race", search_text(con, "segunda").total_hits == 2,
               f"found={search_text(con, 'segunda').total_hits}")
        _check(checks, "D.shared-row-not-doubled",
               con.execute(
                   "SELECT count(*) FROM transcript t JOIN segment s ON s.seg_id = t.seg_id "
                   "WHERE s.video_id = ?", (D_SHARED,)).fetchone()[0] == 2,
               "the contended clip must hold exactly its own 2 segments")
    finally:
        con.close()

    return {
        "arm": "D",
        "ok": all(c["ok"] for c in checks),
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["ok"]),
        "population": {"clips": N_CLIPS, "segments": N_SEGS},
        "window": {"since_s": None, "until_s": None, "note": "whole library"},
        "writers": {str(k): v["payload"] for k, v in reports.items()},
        "checks": checks,
    }


# ---------------------------------------------------------------------------------------------
def verify_fixture(artefact: Path) -> dict:
    """The embedded text must still BE the measured text. This is the drift lock."""
    problems: list[str] = []
    if not artefact.exists():
        return {"ok": False, "problems": [f"artefact missing: {artefact}"]}
    try:
        payload = json.loads(artefact.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"ok": False, "problems": [f"artefact unreadable: {exc}"]}
    want = {S_PT_RADIO, S_PT_MORADORES, S_EN_MONDAY, S_EN_YEAR, S_EN_RESIDENTS}
    have = {row.get("text") for row in payload.get("segments") or []}
    for text in sorted(want - have):
        problems.append(f"no longer in the measured run: {text[:60]!r}")
    return {
        "ok": not problems,
        "artefact": str(artefact),
        "n_segments_in_artefact": len(payload.get("segments") or []),
        "text_chars_in_artefact": len(payload.get("text") or ""),
        "problems": problems,
    }


def print_report(info: dict) -> None:
    arm = info.get("arm", "?")
    print(f"--- ARM {arm}: {'PASS' if info.get('ok') else 'RED'} "
          f"({info.get('n_failed', 0)}/{info.get('n_checks', 0)} check(s) failed)")
    print(f"    POPULATION: {info.get('population')}")
    print(f"    WINDOW    : {info.get('window')}")
    if "rows" in info:
        print(f"    ROWS      : {info['rows']}")
    if "rows_before" in info:
        print(f"    ROWS BEFORE REPLAY: {info['rows_before']}")
    for check in info.get("checks") or []:
        if not check["ok"] or info.get("verbose"):
            print(f"    [{'ok  ' if check['ok'] else 'FAIL'}] {check['name']}  {check.get('detail','')}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m index.selftest",
                                description=__doc__.splitlines()[0])
    p.add_argument("--arm", default="A", choices=list(ALL_ARMS))
    p.add_argument("--db", default="", help="the index file (required)")
    p.add_argument("--work", default="", help="scratch dir for arms C/D (default: <db>.work)")
    p.add_argument("--part", type=int, default=0, help="arm D-writer only")
    p.add_argument("--rounds", type=int, default=D_ROUNDS, help="arm D-writer only")
    p.add_argument("--expect", default="pass", choices=["pass", "red"])
    p.add_argument("--json", default="", help="write the full report here")
    p.add_argument("--verify-fixture", action="store_true",
                   help="only check the embedded transcript text against the measured run")
    p.add_argument("-v", "--verbose", action="store_true", help="print passing checks too")
    args = p.parse_args(argv)

    if args.verify_fixture:
        out = verify_fixture(FIXTURE_ARTEFACT)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1

    if not args.db:
        print("index.selftest: --db is required", file=sys.stderr)
        return 2
    db = Path(args.db)
    work = Path(args.work) if args.work else db.with_name(db.stem + ".work")

    if args.arm == "D-writer":
        out = arm_d_writer(db, args.part, work, args.rounds)
        if args.json:
            Path(args.json).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(out, ensure_ascii=False))
        return 0 if not out["errors"] else 1

    if args.arm == "A":
        info = arm_a(db)
    elif args.arm == "B":
        info = arm_b(db)
    elif args.arm == "C":
        _wipe(db)
        _seed(db)
        info = arm_c(db, work)
    elif args.arm == "D":
        _wipe(db)
        info = arm_d(db, work)
    else:  # pragma: no cover -- argparse already restricted the choices
        print(f"unknown arm {args.arm!r}", file=sys.stderr)
        return 2

    info["verbose"] = args.verbose
    print_report(info)
    if args.expect == "red":
        info["expectation"] = "RED-as-expected"
        verdict_ok = not info.get("ok")
    else:
        info["expectation"] = "PASS"
        verdict_ok = bool(info.get("ok"))
    print(f"ARM-VERDICT {args.arm}: {'PASS' if info.get('ok') else 'RED'} "
          f"({info['expectation']})")
    if args.json:
        Path(args.json).write_text(json.dumps(info, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 0 if verdict_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())