"""FAISS HNSW at 120 k x 256, measured end to end at the lane's 2-thread budget.

The interrupted lane's `_index-hnsw-probe.py` wrote NOTHING (0-byte log, empty work dir) --
twice, including one run by this lane -- so this version is STAGED: every stage appends to the
JSON file before the next one starts, and any exception is written to `<json>.err` with a
traceback. A crash therefore costs one stage, not the whole measurement.

faiss is asked to use 2 OpenMP threads explicitly (`faiss.omp_set_num_threads`) because it has its
own thread pool and OMP_NUM_THREADS alone is not proof.

Measured: build time, single/batch insert, one-id delete, whole-file write/read (faiss has no
incremental durable append), query latency and RECALL@10 against numpy exact, faiss FLAT for
comparison, and the file overhead per vector.

Run: pythonw.exe _main\_index-ann-probe2.py --json _main\index-ann.json
"""
import argparse
import json
import os
import sys
import time
import traceback

import numpy as np

D = 256
N = 120_000
M = 16
EFC = 200
Q = 100
K = 10
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-ann")


class Stager:
    """Writes the JSON after every stage, so a late crash keeps the earlier numbers."""

    def __init__(self, path):
        self.path = path
        self.data = {"probe": "_index-ann-probe2.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "vectors": N, "dims": D, "M": M, "efConstruction": EFC,
                     "queries": Q, "k": K, "stages": {}}

    def stage(self, name, value):
        self.data["stages"][name] = value
        self.flush()

    def flush(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)


def ms(fn, reps=5, warm=1):
    for _ in range(warm):
        fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1e3)
    ts.sort()
    return {"min_ms": round(ts[0], 3), "median_ms": round(ts[len(ts) // 2], 3), "reps": reps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=os.path.join(HERE, "index-ann.json"))
    a = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    import faiss

    faiss.omp_set_num_threads(2)
    st = Stager(a.json)
    st.data["faiss"] = faiss.__version__
    st.data["faiss_omp_threads"] = int(faiss.omp_get_max_threads())
    st.data["thread_env"] = {k: os.environ.get(k) for k in
                             ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")}

    rng = np.random.default_rng(2026)
    X = rng.standard_normal((N, D), dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    Xq = rng.standard_normal((Q, D), dtype=np.float32)
    Xq /= np.linalg.norm(Xq, axis=1, keepdims=True)
    st.stage("corpus", {"matrix_MiB": round(X.nbytes / 2**20, 1)})

    # exact ground truth
    t0 = time.perf_counter()
    exact = np.argsort(-(Xq @ X.T), axis=1)[:, :K]
    st.stage("numpy_exact_groundtruth", {"queries": Q, "k": K,
                                         "seconds": round(time.perf_counter() - t0, 2),
                                         "ms_per_query": round((time.perf_counter() - t0) / Q * 1e3, 3)})

    # faiss FLAT = brute force with SIMD, the honest comparison for the numpy scan
    flat = faiss.IndexFlatIP(D)
    flat.add(X)
    st.stage("faiss_flat", {"index_bytes": int(flat.ntotal * D * 4),
                            "search_k10": ms(lambda: flat.search(Xq, K), reps=5, warm=1)})
    del flat

    # HNSW build
    index = faiss.IndexHNSWFlat(D, M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = EFC
    t0 = time.perf_counter()
    index.add(X)
    build_s = time.perf_counter() - t0
    st.stage("hnsw_build", {"seconds": round(build_s, 2), "vectors_per_s": round(N / build_s),
                            "ntotal": int(index.ntotal)})
    st.stage("hnsw_ram_formula", {"bytes_per_vector_D4_plus_M2x4": D * 4 + M * 2 * 4,
                                  "index_bytes_formula": N * (D * 4 + M * 2 * 4)})

    # incremental insert
    v = rng.standard_normal((1, D), dtype=np.float32)
    v /= np.linalg.norm(v)
    t0 = time.perf_counter()
    index.add(v)
    one_ms = (time.perf_counter() - t0) * 1e3
    B = rng.standard_normal((1000, D), dtype=np.float32)
    B /= np.linalg.norm(B, axis=1, keepdims=True)
    t0 = time.perf_counter()
    index.add(B)
    batch_s = time.perf_counter() - t0
    st.stage("incremental_add", {"one_vector_ms": round(one_ms, 3),
                                 "batch_1000_s": round(batch_s, 3),
                                 "ntotal": int(index.ntotal)})

    # one-id delete -- faiss may simply NOT IMPLEMENT it for this index type; that is a finding,
    # not a crash: record the refusal and carry on.
    try:
        t0 = time.perf_counter()
        index.remove_ids(np.array([5000], dtype=np.int64))
        st.stage("remove_one_id", {"implemented": True,
                                   "ms": round((time.perf_counter() - t0) * 1e3, 2),
                                   "ntotal_after": int(index.ntotal)})
    except Exception as e:
        st.stage("remove_one_id", {"implemented": False,
                                   "error": "%s: %s" % (type(e).__name__, e),
                                   "ntotal_unchanged": int(index.ntotal),
                                   "consequence": "a deleted or moved file cannot be removed from an "
                                                  "HNSW index; the only cure is a full rebuild"})

    # durability: faiss has ONE durability point, the whole-file dump
    path = os.path.join(WORK, "hnsw.faiss")
    t0 = time.perf_counter()
    faiss.write_index(index, path)
    write_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    idx2 = faiss.read_index(path)
    read_s = time.perf_counter() - t0
    size = os.path.getsize(path)
    st.stage("durability", {"write_index_s": round(write_s, 3), "read_index_s": round(read_s, 3),
                            "file_bytes": size, "file_MiB": round(size / 2**20, 1),
                            "payload_bytes_120k_fp32": N * D * 4,
                            "overhead_bytes_per_vector": round((size - N * D * 4) / N, 1),
                            "note": "no incremental durable append; the dump IS the index"})
    del idx2

    # query latency + recall vs exact, efSearch sweep
    search = {}
    for ef in (16, 32, 64, 128, 256):
        index.hnsw.efSearch = ef
        t0 = time.perf_counter()
        _, I = index.search(Xq, K)
        per_q = (time.perf_counter() - t0) / Q * 1e3
        rec = float(np.mean([len(set(I[i]) & set(exact[i])) / K for i in range(Q)]))
        search["ef=%d" % ef] = {"ms_per_query_k10": round(per_q, 3), "recall@10": round(rec, 4)}
        st.stage("search", search)
    return 0


if __name__ == "__main__":
    _j = [x for x in sys.argv if x.endswith(".json")]
    _p = _j[0] if _j else os.path.join(HERE, "index-ann.json")
    try:
        sys.exit(main())
    except Exception:
        with open(_p + ".err", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
