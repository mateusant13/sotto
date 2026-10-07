"""Lane Q: prove the content_key round-trip on a scratch DB.

Creates a scratch SQLite DB from schema.sql (via store.connect, which is the
same path production uses), upserts ONE synthetic segment with a random 256-d
fp32 vector, reads it back through SearchIndex, and re-upserts the SAME
content_key to prove the row count stays 1.

SYNTHETIC ONLY: the "video" is a random SHA-256 of random bytes and the
vector is numpy default_rng noise.  No real media, no owner library touched.

Usage:  python slice_upsert.py     (rc 0 = all assertions held)
"""
import os
import pathlib
import sys
import tempfile

# Thread budget MUST be set before numpy is imported for real work (store.py).
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src" / "index"))

import store, search  # noqa: E402

DIM = 256
CHANNEL = "visual"          # one of search.VECTOR_CHANNELS
MODEL = "slice-synthetic-rng-v1"


def count(conn, table):
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def main():
    store.set_thread_budget(2)
    import numpy as np

    rng = np.random.default_rng(20261007)

    tmp = tempfile.mkdtemp(prefix="slice-upsert-")
    db = pathlib.Path(tmp) / "scratch.sqlite"

    conn = store.connect(db)
    print(f"db              : {db}")
    print(f"journal_mode    : {store.journal_mode(conn)}")
    print("schema applied  : OK (store.connect runs schema.sql)")

    # -- identity: whole-file SHA-256, never the path -----------------------
    content_key = rng.bytes(32).hex()
    print(f"content_key     : {content_key[:16]}... ({len(content_key)} hex chars)")

    video_id = store.upsert_video(
        conn,
        content_key=content_key,
        path="/synthetic/nonexistent-a.mp4",
        size_bytes=1_234_567,
        mtime_ns=1_760_000_000_000_000_000,
        duration_ms=60_000,
        codec="synthetic",
        w=1920, h=1080, fps=25.0,
    )
    seg_id = store.upsert_segment(
        conn, video_id=video_id, start_ms=0, end_ms=5_000, n_visual=1,
    )
    vec = rng.standard_normal(DIM).astype(np.float32)
    ms_per_row = store.upsert_embeddings(
        conn, [(seg_id, CHANNEL, vec)], model=MODEL, dtype="fp32", dim=DIM,
    )
    print(f"upsert          : video_id={video_id} seg_id={seg_id} "
          f"({ms_per_row:.3f} ms/row)")

    # -- read it back through search.py -------------------------------------
    idx = search.SearchIndex(conn)
    hits = idx.search(vec, k=5)
    print(f"\nSearchIndex     : n={idx.n} dim={idx.dim}")
    print(f"ranked hits     : {len(hits)}")
    for rank, h in enumerate(hits, 1):
        print(f"  rank={rank} seg_id={h['seg_id']} video_id={h['video_id']} "
              f"score={h['score']:.6f} channels={sorted(h['channels'])} "
              f"cosine={h['evidence'][CHANNEL]['cosine']:.6f} at={h['at']}")
    assert len(hits) == 1, f"expected exactly 1 hit, got {len(hits)}"
    assert hits[0]["seg_id"] == seg_id, f"hit is the wrong segment: {hits[0]}"

    # -- idempotency: SAME content_key again --------------------------------
    before = {t: count(conn, t) for t in ("video", "segment", "embedding")}
    video_id2 = store.upsert_video(
        conn,
        content_key=content_key,
        path="/synthetic/renamed-b.mp4",     # moved file: new path, same key
        size_bytes=1_234_567,
        mtime_ns=1_760_000_000_000_000_000,
        duration_ms=60_000,
    )
    after = {t: count(conn, t) for t in ("video", "segment", "embedding")}
    print(f"\nre-upsert id    : {video_id2} (same as {video_id}: "
          f"{video_id2 == video_id})")
    print(f"rows before     : {before}")
    print(f"rows after      : {after}")
    assert video_id2 == video_id, "content_key upsert returned a new id"
    assert after == before, f"row counts changed on re-upsert: {before} -> {after}"
    assert after["video"] == 1, f"expected 1 video row, got {after['video']}"

    row = conn.execute("SELECT path FROM video WHERE content_key = ?",
                       (content_key,)).fetchone()
    print(f"path updated to : {row['path']}")

    conn.close()
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())