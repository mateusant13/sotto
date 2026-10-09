"""RED probe: the two ways this index is allowed to fail, and must not.

SYNTHETIC DATA ONLY.  Every content_key is the SHA-256 of a counter string, no
drive is walked, no file of the owner's is opened or hashed.

Test 1 - IDEMPOTENCY.  Re-upserting the same `content_key` must NOT duplicate.
The whole reason identity is content_key and never the path
(docs/research/07-index-search.md sec 2): a re-run pass must be a no-op rather
than a duplicate.  Checked on every table the passes touch, including the FTS5
index -- an FTS index that duplicates its rows on a re-run is worse than one
that duplicates nothing, because it silently inflates every lexical score.

Test 2 - CRASH ATOMICITY.  `taskkill /F` the writer mid-transaction, reopen, and
the row count must be a CLEAN MULTIPLE OF THE BATCH.  Not "most rows survived":
a torn count means a batch landed halfway and the WAL did not protect us.  This
is the control the brief pins -- WAL + synchronous=NORMAL recovered exactly
16 000 rows after taskkill /F, while journal_mode=OFF gave a torn 18041 and
cache_size=50 gave "database disk image is malformed".  Both wrong pragmas are
re-run here as a NEGATIVE CONTROL, because a crash test that can only pass
proves nothing.

Run: python _index-red-probe.py [--batches 8] [--rows 2000]
"""

from __future__ import annotations

import os

# BEFORE numpy: the lane budget is 2 threads.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import store           # noqa: E402

HERE = Path(__file__).parent
SCRATCH = HERE / "_scratch"
BATCH_ROWS = 2000          # the brief's proven-clean batch size
CRASH_AFTER_BATCHES = 5    # kill once 5 batches have committed
CHILD = HERE / "_index-red-crash-child.py"

# table -> the count that must not move when the same content_key is re-upserted
COUNT_SQL = {
    "video":       "SELECT COUNT(*) FROM video WHERE content_key=?",
    "segment":     "SELECT COUNT(*) FROM segment WHERE seg_id=?",
    "transcript":  "SELECT COUNT(*) FROM transcript WHERE seg_id=?",
    "ocr":         "SELECT COUNT(*) FROM ocr WHERE seg_id=?",
    "embedding":   "SELECT COUNT(*) FROM embedding WHERE seg_id=?",
    "marker":      "SELECT COUNT(*) FROM marker WHERE seg_id=?",
}
EXPECTED = {"video": 1, "segment": 1, "transcript": 1, "ocr": 3,
            "embedding": 3, "marker": 1, "text_fts": 4}


def content_key(i: int) -> str:
    return hashlib.sha256(f"synthetic://video/{i}".encode()).hexdigest()


def fresh_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix)
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------------------
# TEST 1 - idempotency on content_key
# ---------------------------------------------------------------------------

def test_idempotency(db: Path, rounds: int = 5) -> dict:
    conn = store.connect(db)
    rng = np.random.default_rng(4242)
    ck0 = content_key(9001)

    conn.execute("BEGIN")
    vid = store.upsert_video(conn, content_key=ck0, path="synthetic_library/a.mp4",
                             size_bytes=1024, mtime_ns=1_700_000_000_000_000_000)
    conn.execute("COMMIT")
    conn.execute("BEGIN")
    seg = store.upsert_segment(conn, video_id=vid, start_ms=0, end_ms=5000,
                               n_speech=1, state="light")
    conn.execute("COMMIT")

    lines = [{"line_no": ln, "t_ms": ln * 100, "t_end_ms": ln * 100 + 80,
              "text_raw": f"ERRO 0x80070005: ACESSO NEGADO {ln}",
              "text_norm": f"erro 0x80070005 acesso negado {ln}",
              "box": None, "conf": 0.9, "engine": "synthetic-ocr",
              "model_sha256": "synthetic-ocr-sha", "frame_ref": None}
             for ln in range(3)]

    vec = rng.standard_normal(256).astype(np.float32)
    counts = []
    for r in range(rounds):
        conn.execute("BEGIN")
        # SAME content_key, a DIFFERENT path every round: this is the rename
        # case.  Keyed on the path it would insert one row per round.
        store.upsert_video(conn, content_key=ck0,
                           path=f"synthetic_library/moved_{r}.mp4",
                           size_bytes=1024, mtime_ns=1_700_000_000_000_000_000)
        store.upsert_segment(conn, seg_id=seg, video_id=vid, start_ms=0,
                             end_ms=5000, n_speech=1, state="light")
        store.upsert_transcript(conn, seg_id=seg, text="erro 0x80070005 acesso negado",
                                text_norm="erro 0x80070005 acesso negado",
                                start_ms=0, producer="light",
                                model_sha256="synthetic-asr-sha")
        store.upsert_ocr_lines(conn, seg, lines)
        store.upsert_embeddings(conn, [(seg, "speech", vec), (seg, "ocr", vec),
                                       (seg, "visual", vec)],
                                model="synthetic-embed",
                                model_sha256="synthetic-embed-sha",
                                dtype="fp16", dim=256)
        store.upsert_marker(conn, seg_id=seg, kind="speech", value="1",
                            source="synthetic")
        conn.execute("COMMIT")
        row = {t: conn.execute(sql, (ck0,)).fetchone()[0]
               for t, sql in COUNT_SQL.items()
               if t != "video"}
        row["video"] = conn.execute(COUNT_SQL["video"], (ck0,)).fetchone()[0]
        # the FTS index is the one that is easiest to get wrong and the hardest
        # to notice: a duplicated fts row inflates every lexical score silently
        row["text_fts"] = conn.execute(
            "SELECT COUNT(*) FROM text_fts WHERE text_fts MATCH ?",
            ('"0x80070005"',)).fetchone()[0]
        counts.append(row)

    n_videos = conn.execute("SELECT COUNT(*) FROM video").fetchone()[0]
    moved = conn.execute("SELECT path FROM video WHERE content_key=?",
                         (ck0,)).fetchone()[0]
    journal = store.journal_mode(conn)
    conn.close()

    stable = all(c == counts[0] for c in counts)
    matches_expected = all(counts[-1][t] == EXPECTED[t] for t in EXPECTED)
    return {"rounds": rounds, "per_round": counts, "stable_across_rounds": stable,
            "final_counts": counts[-1], "expected": EXPECTED,
            "final_counts_match_expected": matches_expected,
            "video_rows_in_table": n_videos,
            "path_after_moves": moved, "journal_mode": journal,
            "PASS": stable and matches_expected}


# ---------------------------------------------------------------------------
# TEST 2 - crash atomicity: taskkill /F mid-transaction
# ---------------------------------------------------------------------------

def crash_case(db: Path, progress: Path, *, override: str | None,
               batches: int, rows: int) -> dict:
    """One crash trial: run the writer, taskkill /F it, reopen, count."""
    fresh_db(db)
    if progress.exists():
        progress.unlink()

    cmd = [sys.executable, str(CHILD), "--db", str(db),
           "--progress", str(progress), "--batches", str(batches),
           "--rows", str(rows)]
    if override:
        cmd += ["--override", override]
    child = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)

    committed_before_kill = 0
    try:
        deadline = time.time() + 180
        while time.time() < deadline:
            if progress.exists():
                try:
                    n = int(progress.read_text() or 0)
                except ValueError as exc:
                    # DELIBERATE best-effort: the child truncates the note file
                    # before writing it, so a torn read is a real race, not a
                    # failure.  What is lost when it fires: one poll iteration
                    # (0.02 s), nothing else -- the loop re-reads immediately.
                    print(f"[red-probe] progress note torn ({exc}); re-polling",
                          file=sys.stderr)
                    continue
                if n >= CRASH_AFTER_BATCHES * rows:
                    break
            if child.poll() is not None:
                print("[red-probe] WARNING: writer exited before the kill point",
                      file=sys.stderr)
                break
            time.sleep(0.02)
        if progress.exists():
            committed_before_kill = int(progress.read_text() or 0)
        killed = subprocess.run(["taskkill", "/F", "/PID", str(child.pid)],
                                capture_output=True, text=True)
        killed_out = (killed.stdout or "").strip() + (killed.stderr or "").strip()
    finally:
        try:
            out = child.communicate(timeout=60)[0]
        except subprocess.TimeoutExpired:
            child.kill()
            out = child.communicate()[0]
        rc = child.returncode

    # reopen and count.  A torn or corrupt database raises DatabaseError here.
    try:
        conn = store.connect(db, create=False)
        recovered = conn.execute("SELECT COUNT(*) FROM video").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        journal = store.journal_mode(conn)
        conn.close()
        err = None
    except sqlite3.DatabaseError as exc:
        recovered = integrity = journal = None
        err = f"{type(exc).__name__}: {exc}"

    clean = recovered is not None and recovered % rows == 0
    return {"override": override or "none (schema.sql exactly as written)",
            "taskkill_output": killed_out, "child_returncode": rc,
            "child_stdout_tail": (out or "").strip()[-300:],
            "committed_before_kill": committed_before_kill,
            "recovered_rows": recovered, "batch_size": rows,
            "clean_multiple_of_batch": clean,
            "integrity_check": integrity, "journal_mode_after": journal,
            "error": err}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", type=int, default=8)
    ap.add_argument("--rows", type=int, default=BATCH_ROWS)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--skip-negative", action="store_true",
                    help="skip the deliberately-broken-pragma controls")
    args = ap.parse_args()

    SCRATCH.mkdir(parents=True, exist_ok=True)
    report: dict = {"rows_per_batch": args.rows}

    fresh_db(SCRATCH / "red-idem.db")
    report["test1_idempotency"] = test_idempotency(SCRATCH / "red-idem.db",
                                                   rounds=args.rounds)

    progress = SCRATCH / "crash-progress.txt"
    report["test2_crash"] = {
        "as_written": crash_case(SCRATCH / "red-crash.db", progress,
                                 override=None, batches=args.batches,
                                 rows=args.rows),
    }
    if not args.skip_negative:
        report["test2_crash"]["negative_controls"] = [
            crash_case(SCRATCH / "red-crash-off.db", progress,
                       override="journal_off", batches=args.batches,
                       rows=args.rows),
            crash_case(SCRATCH / "red-crash-tiny.db", progress,
                       override="cache_tiny", batches=args.batches,
                       rows=args.rows),
        ]

    ok = report["test1_idempotency"]["PASS"]
    asw = report["test2_crash"]["as_written"]
    ok = ok and asw["clean_multiple_of_batch"] and asw["integrity_check"] == "ok"

    print(json.dumps(report, indent=2, default=str))
    print("\n=== RED PROBE vs TARGETS ===")
    t1 = report["test1_idempotency"]
    print(f"idempotency final counts : {t1['final_counts']}")
    print(f"  expected               : {t1['expected']}")
    print(f"  path after 5 moves     : {t1['path_after_moves']}")
    print(f"  PASS                   : {t1['PASS']}")
    print(f"crash (WAL/NORMAL)       : recovered {asw['recovered_rows']} rows, "
          f"batch {asw['batch_size']}, clean_multiple="
          f"{asw['clean_multiple_of_batch']}, integrity={asw['integrity_check']}")
    for nc in report["test2_crash"].get("negative_controls", []):
        print(f"NEGATIVE CONTROL {nc['override']:<12}: recovered="
              f"{nc['recovered_rows']} clean_multiple="
              f"{nc['clean_multiple_of_batch']} integrity={nc['integrity_check']} "
              f"err={nc['error']}")
    print(f"\nRED PROBE: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())