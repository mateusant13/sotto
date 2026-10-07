"""Profile the index QUERY path at scale: explicit phase timers + cProfile.

Companion to slice_scale_probe.py (which OWNS the gate and the population; this
file measures WHERE the milliseconds go and must not change the verdict).

It builds the store with the REAL store.py API at the same N, loads the REAL
SearchIndex, then times EVERY query with (a) an explicit per-phase breakdown and
(b) cProfile over the identical loop, so the two can be checked against each
other.  cProfile distorts absolute numbers, so the PHASE TIMERS are the ones
quoted as percentages in index_perf_profile.md; cProfile is quoted for call-site
attribution.

THREADS: <=2 via env set before numpy is imported.

Usage:  python index_perf_prof.py [N] [n_queries]

EXIT:  0 always.  This file MEASURES; it does not gate.  The gate is
       slice_scale_probe.py's and only its.
"""
import os

# --- thread budget FIRST, before numpy exists in this process ---------------
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import cProfile  # noqa: E402
import pathlib  # noqa: E402
import pstats  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src" / "index"))

import store, search  # noqa: E402

store.set_thread_budget(2)
import numpy as np  # noqa: E402

DIM = 256
CHANNEL = "visual"
MODEL = "index-perf-prof-v1"
SEED = 20261007
BUDGET_MS = 16.0


def build(n, chunk=4096):
    """Build the store at population n through the real store.py API."""
    rng = np.random.default_rng(SEED)
    tmp = tempfile.mkdtemp(prefix="index-perf-")
    db = pathlib.Path(tmp) / "scratch.sqlite"
    conn = store.connect(db)
    video_id = store.upsert_video(
        conn, content_key=rng.bytes(32).hex(),
        path="/synthetic/perf-nonexistent.mp4", size_bytes=1_234_567,
        mtime_ns=1_760_000_000_000_000_000, duration_ms=60_000,
        codec="synthetic", w=1920, h=1080, fps=25.0)
    seg_ids = []
    conn.execute("BEGIN")
    for i in range(n):
        seg_ids.append(store.upsert_segment(
            conn, video_id=video_id, start_ms=i * 5000, end_ms=(i + 1) * 5000,
            n_visual=1))
        if len(seg_ids) == chunk:
            conn.execute("COMMIT")
            conn.execute("BEGIN")
    conn.execute("COMMIT")
    for start in range(0, n, chunk):
        m = min(chunk, n - start)
        vecs = rng.standard_normal((m, DIM)).astype(np.float32)
        store.upsert_embeddings(
            conn, [(seg_ids[start + j], CHANNEL, vecs[j]) for j in range(m)],
            model=MODEL, dtype="fp32", dim=DIM)
        del vecs
    return conn, seg_ids


def phase_timers(idx, n_queries):
    """Explicit timers on each stage of ONE search() call, repeated n_queries.

    Re-implements the exact arithmetic SearchIndex.search performs (via the real
    object, not a copy) so every stage is charged for what it actually costs.
    """
    qrng = np.random.default_rng(SEED + 1)
    queries = [idx.vecs[int(qrng.integers(0, idx.n))] for _ in range(n_queries)]

    # warm the pages so the first-touch cost is not charged to a phase
    for q in queries[:3]:
        idx.search(q, k=10)

    tot = {k: 0.0 for k in ("l2", "matvec", "mask_copy", "where", "argpart",
                            "argsort", "hitlist", "rrf", "materialise", "TOTAL")}
    counts = {"matvec_calls": 0, "mask_copy_calls": 0, "where_calls": 0,
              "argpart_calls": 0, "argsort_calls": 0, "hitlist_calls": 0}
    lat = []

    for q in queries:
        t_all = time.perf_counter()
        scores, detail = {}, {}
        for channel, weight in search.WEIGHTS.items():
            t = time.perf_counter()
            qn = search._l2(q)
            tot["l2"] += time.perf_counter() - t

            t = time.perf_counter()
            sims = idx.vecs @ qn
            tot["matvec"] += time.perf_counter() - t
            counts["matvec_calls"] += 1

            t = time.perf_counter()
            mask = idx._masks[channel].copy()
            tot["mask_copy"] += time.perf_counter() - t
            counts["mask_copy_calls"] += 1

            t = time.perf_counter()
            sims = np.where(mask, sims, -np.inf)
            tot["where"] += time.perf_counter() - t
            counts["where_calls"] += 1

            t = time.perf_counter()
            take = min(search.K_PER_CHANNEL, idx.n)
            top = np.argpartition(-sims, take - 1)[:take]
            tot["argpart"] += time.perf_counter() - t
            counts["argpart_calls"] += 1

            t = time.perf_counter()
            top = top[np.argsort(-sims[top])]
            tot["argsort"] += time.perf_counter() - t
            counts["argsort_calls"] += 1

            t = time.perf_counter()
            knn = [(int(idx.seg_ids[i]), r + 1, float(sims[i]))
                   for r, i in enumerate(top) if np.isfinite(sims[i])]
            tot["hitlist"] += time.perf_counter() - t
            counts["hitlist_calls"] += 1

            t = time.perf_counter()
            for seg_id, rank, cosine in knn:
                scores[seg_id] = scores.get(seg_id, 0.0) + weight / (search.RRF_K + rank)
                detail.setdefault(seg_id, {})[channel] = {
                    "rank": rank, "cosine": round(cosine, 6)}
            tot["rrf"] += time.perf_counter() - t

        t = time.perf_counter()
        idx._materialise(scores, detail, 10)
        tot["materialise"] += time.perf_counter() - t
        tot["TOTAL"] += time.perf_counter() - t_all
        lat.append((time.perf_counter() - t_all) * 1000.0)

    return tot, counts, lat


def cprofile_queries(idx, n_queries=60):
    qrng = np.random.default_rng(SEED + 1)
    queries = [idx.vecs[int(qrng.integers(0, idx.n))] for _ in range(n_queries)]
    for q in queries[:3]:
        idx.search(q, k=10)
    pr = cProfile.Profile()
    pr.enable()
    for q in queries:
        idx.search(q, k=10)
    pr.disable()
    st = pstats.Stats(pr)
    st.sort_stats("tottime")
    return st


def pct(tot, n_queries):
    t = tot["TOTAL"]
    print(f"\n  {'phase':<14}{'ms/query':>12}{'% of query':>14}{'calls/query':>15}")
    print("  " + "-" * 55)
    for k in ("l2", "matvec", "mask_copy", "where", "argpart", "argsort",
              "hitlist", "rrf", "materialise"):
        ms = tot[k] * 1000.0 / n_queries
        calls = {"matvec": 3, "mask_copy": 3, "where": 3, "argpart": 3,
                 "argsort": 3, "hitlist": 3}.get(k, 1)
        print(f"  {k:<14}{ms:>12.4f}{tot[k] / t * 100:>13.2f}%{calls:>15}")
    print("  " + "-" * 55)
    print(f"  {'TOTAL':<14}{t * 1000.0 / n_queries:>12.4f}{100.0:>13.2f}%")


def main(argv):
    n = int(argv[1]) if len(argv) > 1 else 211200
    nq = int(argv[2]) if len(argv) > 2 else 100
    print(f"n={n} dim={DIM} queries={nq} threads=2")

    t0 = time.perf_counter()
    conn, _ = build(n)
    print(f"build: {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    idx = search.SearchIndex(conn)
    load_s = time.perf_counter() - t0
    print(f"load_matrix: {load_s:.2f}s  n={idx.n} dim={idx.dim}")

    tot, counts, lat = phase_timers(idx, nq)
    s = sorted(lat)
    print(f"\nphase timers over WINDOW {len(s)} queries "
          f"(POPULATION n={n}, <=2 threads):")
    print(f"  p50={s[len(s) // 2]:.2f}ms p95={s[int(0.95 * len(s))]:.2f}ms "
          f"max={s[-1]:.2f}ms  under {BUDGET_MS:g}ms="
          f"{sum(1 for x in s if x < BUDGET_MS) / len(s) * 100:.1f}%")
    pct(tot, nq)
    print(f"\n  call counts per query: "
          + ", ".join(f"{k}={v / nq:.1f}" for k, v in counts.items()))

    print("\ncProfile, 60 queries, tottime (call-site attribution):")
    st = cprofile_queries(idx)
    st.print_stats(18)

    sizes = store.store_bytes(conn)
    print(f"\ndb on disk: {sizes['file_mib']:.1f} MiB")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))