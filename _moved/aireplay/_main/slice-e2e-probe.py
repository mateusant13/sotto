"""Lane Q slice v6 -- the chain, end to end on SYNTHETIC data only.

Extends the merged slice_probe.py (which proved `import store, search` works)
into the four steps that actually matter:

  1. build a SQLite DB from schema.sql (store.connect does the executescript)
  2. upsert ONE synthetic segment with a random 256-d fp32 vector (store.py)
  3. run one query via search.py (RRF over the three channels)
  4. print the ranked hits

Both colours:
  GREEN -- the query returns the row just inserted.
  RED   -- upserting the SAME content_key twice must NOT duplicate; row count
           stays 1.  Same for the (seg_id, channel) embedding key.

Facts obeyed, not re-litigated:
  * WAL + synchronous=NORMAL are the crash-safe pragmas (they live in schema.sql).
  * Identity is content_key = whole-file SHA-256, NEVER the path.
  * <=2 threads, set BEFORE numpy does real work.
  * random vectors only -- no real media, no real footage.

Path logic is slice_probe.py's, verbatim and PROVEN:
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src" / "index"))
"""

import hashlib
import pathlib
import random
import sys
import tempfile
import time

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src" / "index"))

# <=2 threads, set before numpy is imported for real work.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    import os
    os.environ[_v] = "2"

import numpy as np   # noqa: E402
import store         # noqa: E402
import search        # noqa: E402

DIM = 256
CHANNELS = ("speech", "ocr", "visual")
FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    colour = "GREEN" if ok else "RED"
    print(f"  [{colour}] {name}{(' -- ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def synth_vec(seed: int) -> np.ndarray:
    """A random unit vector.  Synthetic by construction -- not derived from media."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM, dtype=np.float32)
    return (v / np.linalg.norm(v)).astype(np.float32)


def fake_content_key(payload: bytes) -> str:
    """Identity is the whole-file SHA-256, never the path.  Bytes are synthetic."""
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    t_start = time.perf_counter()
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="slice-v6-"))
    db = tmpdir / "index.sqlite"

    print(f"tmpdir : {tmpdir}")
    print(f"db     : {db}")

    # ---- STEP 1: build the DB from schema.sql ------------------------------
    print("\n[STEP 1] connect() -> executescript(schema.sql)")
    conn = store.connect(db)
    print(f"  journal_mode       = {store.journal_mode(conn)}")
    print(f"  synchronous        = {conn.execute('PRAGMA synchronous').fetchone()[0]}")
    print(f"  page_size          = {conn.execute('PRAGMA page_size').fetchone()[0]}")
    print(f"  cache_size         = {conn.execute('PRAGMA cache_size').fetchone()[0]}")
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    print(f"  tables ({len(tables)})        = {', '.join(tables)}")
    check("schema applied", "embedding" in tables and "segment" in tables,
          f"{len(tables)} tables")

    # ---- STEP 2: upsert ONE synthetic segment + one 256-d fp32 vector ------
    print("\n[STEP 2] upsert_video -> upsert_segment -> upsert_embeddings (fp32)")
    payload = bytes(random.Random(7).randbytes(4096))      # synthetic "file bytes"
    content_key = fake_content_key(payload)
    print(f"  content_key (sha256) = {content_key}")

    video_id = store.upsert_video(
        conn, content_key=content_key, path=str(tmpdir / "SYNTHETIC-NOT-A-REAL-FILE.mp4"),
        size_bytes=len(payload), mtime_ns=0, duration_ms=10_000, codec="synthetic",
        w=256, h=256, fps=30.0, state="pending")
    seg_id = store.upsert_segment(conn, video_id=video_id, start_ms=0,
                                  end_ms=5_000, state="ready")
    print(f"  video_id={video_id}  seg_id={seg_id}")

    query_vec = synth_vec(seed=42)
    ms_per_row = store.upsert_embeddings(
        conn, [(seg_id, ch, synth_vec(seed=100 + i)) for i, ch in enumerate(CHANNELS)],
        model="synthetic-random-v1", model_sha256=None, dtype="fp32", dim=DIM)
    print(f"  embedded {len(CHANNELS)} channels @ {DIM}-d fp32 "
          f"({ms_per_row:.3f} ms/row MEASURED)")

    n_seg = conn.execute("SELECT COUNT(*) FROM segment").fetchone()[0]
    n_emb = conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0]
    check("one segment row", n_seg == 1, f"segment COUNT={n_seg}")
    check("three embedding rows", n_emb == 3, f"embedding COUNT={n_emb}")

    # ---- STEP 3 + 4: one query, ranked hits -------------------------------
    print("\n[STEP 3+4] SearchIndex.search(query) -- RRF over 3 channels")
    index = search.SearchIndex(conn)
    print(f"  index.n={index.n}  index.dim={index.dim}  channels loaded="
          f"{sorted(set(index.channels))}")

    t0 = time.perf_counter()
    hits = index.search(query_vec, k=10)
    query_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  query MEASURED {query_ms:.3f} ms (n={index.n}; the 16 ms/query target "
          f"is at 211 200 vectors, this is 1)")
    print(f"  hits ({len(hits)}):")
    for rank, h in enumerate(hits, 1):
        print(f"    {rank:>2}. seg_id={h['seg_id']} score={h['score']:.8f} "
              f"channels={h['channels']} path={pathlib.Path(h['path']).name}")
        print(f"        at={h['at']}  evidence={h['evidence']}")

    check("query returns >=1 hit", len(hits) >= 1, f"{len(hits)} hits")
    check("GREEN: the inserted row is the hit", bool(hits) and hits[0]["seg_id"] == seg_id,
          f"expected seg_id={seg_id}, got "
          f"{[h['seg_id'] for h in hits]}")
    check("hit carries video_id + path",
          bool(hits) and hits[0]["video_id"] == video_id
          and pathlib.Path(hits[0]["path"]).name == "SYNTHETIC-NOT-A-REAL-FILE.mp4")

    # ---- RED: same content_key twice must NOT duplicate --------------------
    print("\n[RED] re-upsert the SAME content_key and the SAME (seg_id, channel)")
    video_id2 = store.upsert_video(
        conn, content_key=content_key,
        path=str(tmpdir / "RENAMED-STILL-SAME-CONTENT.mp4"),   # moved, not re-keyed
        size_bytes=len(payload), mtime_ns=123, duration_ms=10_000, codec="synthetic",
        w=256, h=256, fps=30.0, state="pending")
    seg_id2 = store.upsert_segment(conn, video_id=video_id2, start_ms=0,
                                   end_ms=5_000, state="ready")
    store.upsert_embeddings(
        conn, [(seg_id2, ch, synth_vec(seed=100 + i))
               for i, ch in enumerate(CHANNELS)],
        model="synthetic-random-v1", model_sha256=None, dtype="fp32", dim=DIM)

    n_video = conn.execute("SELECT COUNT(*) FROM video").fetchone()[0]
    n_seg2 = conn.execute("SELECT COUNT(*) FROM segment").fetchone()[0]
    n_emb2 = conn.execute("SELECT COUNT(*) FROM embedding").fetchone()[0]
    print(f"  after re-upsert: video={n_video} segment={n_seg2} embedding={n_emb2}")
    print(f"  video_id stable? {video_id2 == video_id}   seg_id stable? {seg_id2 == seg_id}")
    check("RED: video row count stays 1", n_video == 1, f"COUNT={n_video}")
    check("RED: segment row count stays 1", n_seg2 == 1, f"COUNT={n_seg2}")
    check("RED: embedding row count stays 3", n_emb2 == 3, f"COUNT={n_emb2}")
    check("RED: video_id is stable (rename = UPDATE)", video_id2 == video_id,
          f"{video_id} -> {video_id2}")
    moved_path = conn.execute("SELECT path FROM video WHERE id = ?",
                              (video_id,)).fetchone()[0]
    check("RED: the PATH was updated, the key was not",
          pathlib.Path(moved_path).name == "RENAMED-STILL-SAME-CONTENT.mp4",
          pathlib.Path(moved_path).name)

    # ---- a second, DIFFERENT content_key DOES make a new row (control) -----
    payload2 = bytes(random.Random(8).randbytes(4096))
    store.upsert_video(conn, content_key=fake_content_key(payload2),
                       path=str(tmpdir / "SYNTHETIC-OTHER.mp4"),
                       size_bytes=len(payload2), mtime_ns=0)
    n_video3 = conn.execute("SELECT COUNT(*) FROM video").fetchone()[0]
    check("CONTROL: a different content_key DOES add a row", n_video3 == 2,
          f"COUNT={n_video3}")

    sizes = store.store_bytes(conn)
    print(f"\n  on-disk: {sizes['file_mib']:.3f} MiB (page_size={sizes['page_size']}, "
          f"checkpoint={sizes['checkpoint']})")
    print(f"  total wall: {time.perf_counter() - t_start:.3f} s")
    conn.close()

    print("\n" + "=" * 62)
    if FAILURES:
        print(f"VERDICT: RED -- {len(FAILURES)} failed")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("VERDICT: GREEN -- all checks passed (chain ran end to end)")
    return 0


if __name__ == "__main__":
    sys.exit(main())