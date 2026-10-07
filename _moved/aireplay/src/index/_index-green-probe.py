"""GREEN probe: build the store at the product's real corpus scale, query it, and
report MEASURED ms/query and MEASURED MiB against the targets.

SYNTHETIC DATA ONLY.  Nothing here reads a drive, opens a video, or touches the
owner's library: every content_key is the SHA-256 of a counter string, every
vector is a seeded random unit vector, every text is generated from a fixed
vocabulary.  content_key is computed from a synthetic payload purely so the
identity column has the shape it has in production (64 hex chars).

Targets (docs/research/07-index-search.md sec 6, MEASURED on this box):
    120 000 x 256 FP32            = 117.19 MiB
    3-channel corpus 211 200 vec  = 206.25 MiB fp32 / 103.13 MiB fp16
    single full scan, k=100       = 15.99 ms min / 20.3 ms median  (2 threads)
    fused RRF, 3 channels         = 72.6 ms min / 83.2 ms median
    incremental insert            = 0.011 ms/row
    file on disk (fp16 + rows)    = 137.34 MiB (MEASURED by this lane, not a guess)

Run: python _index-green-probe.py [--scale full|smoke]
"""

from __future__ import annotations

import os

# BEFORE numpy: the lane budget is 2 threads and it is measured, not assumed.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse
import hashlib
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import search          # noqa: E402
import store           # noqa: E402

SEED = 20261007
VOCAB = ("alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima "
         "mike november oscar papa quebec romeo sierra tango uniform victor "
         "whiskey xray yankee zulu erro acesso negado sistema audio video "
         "transcricao falha recuperada janela overlay botao menu").split()
GAME_TOKEN = "ERRO 0x80070005: ACESSO NEGADO"

VIDEOS = 1000
SEGMENTS_PER_VIDEO = 120          # 10 min / 5 s
SEG_MS = 5000
DIM = 256
SPEECH_FRAC = 0.60                # doc 07 sec 6: assumed mix
OCR_FRAC = 0.16

TARGETS = {
    "scan_ms_per_query": 15.99,
    "scan_ms_median": 20.3,
    "fused_ms_min": 72.6,
    "fused_ms_median": 83.2,
    "vec_payload_mib_fp32_3ch": 206.25,
    "vec_payload_mib_fp32_1ch": 117.19,
    "insert_ms_per_row": 0.011,
}


def content_key(i: int) -> str:
    """Synthetic whole-file SHA-256: hash of a counter string, NOT of any file."""
    return hashlib.sha256(f"synthetic://video/{i}".encode()).hexdigest()


def norm_text(rng: np.random.Generator, words: int = 24) -> str:
    toks = [VOCAB[i] for i in rng.integers(0, len(VOCAB), words)]
    return " ".join(toks).lower()


def build(db_path: Path, videos: int, segs_per_video: int, *, fp16: bool = True) -> dict:
    if db_path.exists():
        for suffix in ("", "-wal", "-shm"):
            p = db_path.with_name(db_path.name + suffix)
            if p.exists():
                p.unlink()
    conn = store.connect(db_path)
    rng = np.random.default_rng(SEED)
    dtype = "fp16" if fp16 else "fp32"
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    conn.execute("BEGIN")
    for v in range(videos):
        vid = store.upsert_video(conn, content_key=content_key(v),
                                 path=f"synthetic_library/clip_{v:04d}.mp4",
                                 size_bytes=600 * 1024 * 1024, mtime_ns=1_700_000_000_000_000_000 + v,
                                 duration_ms=600_000, w=1920, h=1080, fps=30.0,
                                 file_key=f"(1234567890,{0x100000 + v})")
        conn.execute("COMMIT")
        conn.execute("BEGIN")
    timings["video_rows_ms"] = (time.perf_counter() - t0) * 1000

    # segments + text, batched
    t0 = time.perf_counter()
    seg_rows, tr_rows, seg_ids = [], [], []
    next_id = 1
    for v in range(videos):
        for s in range(segs_per_video):
            seg_rows.append((next_id, v + 1, s * SEG_MS, (s + 1) * SEG_MS, 1, 0, 0, "light"))
            if rng.random() < SPEECH_FRAC:
                tr_rows.append((next_id, s * SEG_MS, norm_text(rng),
                                norm_text(rng), "light", "synthetic-asr-sha"))
            seg_ids.append(next_id)
            next_id += 1
    conn.executemany("INSERT INTO segment (seg_id, video_id, start_ms, end_ms,"
                     " n_visual, n_speech, n_ocr, state) VALUES (?,?,?,?,?,?,?,?)", seg_rows)
    conn.executemany("INSERT INTO transcript (seg_id, start_ms, text, text_norm,"
                     " producer, model_sha256) VALUES (?,?,?,?,?,?)", tr_rows)
    conn.execute("COMMIT")
    timings["segment_rows_ms"] = (time.perf_counter() - t0) * 1000

    # ocr lines: 16 % of segments, every 10th one carries the exact game token
    t0 = time.perf_counter()
    conn.execute("BEGIN")
    ocr_rows = []
    for i, sid in enumerate(seg_ids):
        if rng.random() >= OCR_FRAC:
            continue
        n_lines = int(rng.integers(1, 4))
        for ln in range(n_lines):
            text = GAME_TOKEN if (sid % 997 == 0 or sid == 1) and ln == 0 else norm_text(rng, 10)
            ocr_rows.append((sid, ln, 0, 400, text, text.lower(), None, 0.91,
                             "synthetic-ocr", "synthetic-ocr-sha", None))
    conn.executemany("INSERT INTO ocr (seg_id, line_no, t_ms, t_end_ms, text_raw,"
                     " text_norm, box, conf, engine, model_sha256, frame_ref)"
                     " VALUES (?,?,?,?,?,?,?,?,?,?,?)", ocr_rows)
    conn.execute("COMMIT")
    timings["ocr_rows_ms"] = (time.perf_counter() - t0) * 1000

    # embeddings: one `visual` per segment, plus `speech` 60 % and `ocr` 16 %.
    insert_ms_total, n_vec = 0.0, 0
    t0 = time.perf_counter()
    # no outer BEGIN: upsert_embeddings owns its own transaction, which is what
    # makes each batch its own crash-atomic commit unit.
    batch = []
    for i, sid in enumerate(seg_ids):
        batch.append((sid, "visual", rng.standard_normal(DIM).astype(np.float32)))
        if rng.random() < SPEECH_FRAC:
            batch.append((sid, "speech", rng.standard_normal(DIM).astype(np.float32)))
        if rng.random() < OCR_FRAC:
            batch.append((sid, "ocr", rng.standard_normal(DIM).astype(np.float32)))
        if len(batch) >= 3000:
            # upsert_embeddings returns ms/ROW; accumulate total ms, not rates.
            insert_ms_total += store.upsert_embeddings(
                conn, batch, model="synthetic-embed", model_sha256="synthetic-embed-sha",
                dtype=dtype, dim=DIM) * len(batch)
            n_vec += len(batch)
            batch.clear()
    if batch:
        insert_ms_total += store.upsert_embeddings(
            conn, batch, model="synthetic-embed", model_sha256="synthetic-embed-sha",
            dtype=dtype, dim=DIM) * len(batch)
        n_vec += len(batch)
    timings["embedding_total_ms"] = (time.perf_counter() - t0) * 1000
    timings["insert_ms_per_row"] = insert_ms_total / max(1, n_vec)

    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("video", "segment", "transcript", "ocr", "embedding", "text_fts")}
    sizes = store.store_bytes(conn)
    journal = store.journal_mode(conn)
    conn.close()
    return {"counts": counts, "sizes": sizes, "journal_mode": journal,
            "vectors": n_vec, "timings": timings, "dtype": dtype}


def measure(db_path: Path, *, queries: int = 100, k: int = 10) -> dict:
    conn = store.connect(db_path)
    t0 = time.perf_counter()
    idx = search.SearchIndex(conn)
    load_ms = (time.perf_counter() - t0) * 1000
    rng = np.random.default_rng(SEED + 1)
    queries_v = rng.standard_normal((queries, DIM)).astype(np.float32)
    queries_v /= np.linalg.norm(queries_v, axis=1, keepdims=True)

    # one probe of the real vectors, so the scan is a true full-matrix scan
    scan_ms, fused_ms, top10_multi = [], [], 0
    for q in queries_v:
        t0 = time.perf_counter()
        idx.knn(q, channel="visual", k=100)
        scan_ms.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        hits = idx.search(q, k=k)
        fused_ms.append((time.perf_counter() - t0) * 1000)
        if len(hits) == k and all(len(h["channels"]) >= 1 for h in hits):
            if len(set(tuple(h["channels"]) for h in hits)) > 1:
                top10_multi += 1

    # lexical channel: byte-exact retrieval of a game token
    t0 = time.perf_counter()
    fts_hits = idx.search_text(f'"{GAME_TOKEN.split(":")[0].strip()}"')
    fts_ms = (time.perf_counter() - t0) * 1000
    fts_probe = idx.search_text("0x80070005")
    fts_sample = conn.execute(
        "SELECT t.text_norm FROM text_fts t WHERE t.text_fts MATCH ? LIMIT 1",
        ("0x80070005",)).fetchone()

    # incremental insert, one committed row at a time (the LIGHT path shape)
    inc_ms = []
    for i in range(50):
        sid = idx.seg_ids[i % idx.n]
        vec = rng.standard_normal(DIM).astype(np.float32)
        t0 = time.perf_counter()
        store.upsert_embeddings(conn, [(int(sid), "speech", vec)],
                                model="synthetic-embed",
                                model_sha256="synthetic-embed-sha",
                                dtype=conn.execute("SELECT dtype FROM embedding LIMIT 1").fetchone()[0],
                                dim=DIM)
        inc_ms.append((time.perf_counter() - t0) * 1000)
    sizes = store.store_bytes(conn)
    conn.close()
    return {
        "load_ms": load_ms, "n_vectors_in_ram": int(idx.n), "dim": int(idx.dim),
        "scan_ms_min": min(scan_ms), "scan_ms_median": statistics.median(scan_ms),
        "fused_ms_min": min(fused_ms), "fused_ms_median": statistics.median(fused_ms),
        "ram_vec_mib": idx.vecs.nbytes / 1024 ** 2,
        "hits_all_name_a_channel": top10_multi,
        "fts_ms": fts_ms, "fts_hits": len(fts_hits),
        "fts_0x80070005_hits": len(fts_probe),
        "fts_sample_text": (fts_sample[0] if fts_sample else None),
        "incremental_ms_median": statistics.median(inc_ms),
        "incremental_ms_max": max(inc_ms),
        "sizes": sizes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="full", choices=("full", "smoke"))
    ap.add_argument("--queries", type=int, default=100)
    ap.add_argument("--db", default=str(Path(__file__).parent / "_scratch" / "green.db"))
    args = ap.parse_args()

    videos, segs = (VIDEOS, SEGMENTS_PER_VIDEO) if args.scale == "full" else (10, 12)
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    build_info = build(db_path, videos, segs)
    build_s = time.perf_counter() - t0
    meas = measure(db_path, queries=args.queries)

    report = {"scale": args.scale, "build_s": build_s, "build": build_info,
              "measure": meas, "targets": TARGETS}
    print(json.dumps(report, indent=2, default=str))

    n = meas["n_vectors_in_ram"]
    fp32_mib = n * DIM * 4 / 1024 ** 2
    print("\n=== vs TARGETS ===")
    print(f"vectors in RAM      : {n}  (fp32 matrix {fp32_mib:.2f} MiB)")
    print(f"  target 1-channel  : 120 000 = {TARGETS['vec_payload_mib_fp32_1ch']} MiB")
    print(f"  target 3-channel  : 211 200 = {TARGETS['vec_payload_mib_fp32_3ch']} MiB")
    print(f"scan ms/query       : min {meas['scan_ms_min']:.2f} median "
          f"{meas['scan_ms_median']:.2f}   target 15.99 / 20.3")
    print(f"fused RRF ms/query  : min {meas['fused_ms_min']:.2f} median "
          f"{meas['fused_ms_median']:.2f}   target 72.6 / 83.2")
    print(f"file on disk        : {meas['sizes']['file_mib']:.2f} MiB")
    print(f"insert ms/row       : bulk {build_info['timings']['insert_ms_per_row']:.4f}  "
          f"single-row median {meas['incremental_ms_median']:.4f}  target 0.011")
    print(f"journal_mode        : {build_info['journal_mode']}")
    print(f"FTS 0x80070005 hits : {meas['fts_0x80070005_hits']}  "
          f"sample={meas['fts_sample_text']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())