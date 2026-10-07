"""What an ANN index actually costs here: faiss HNSW at 120 k x 256, measured end to end.

hnswlib could NOT be measured: pip has only an sdist for win_amd64/cp311 and the build needs
MSVC 14.0+, which this box does not have (measured). faiss-cpu ships a wheel, so HNSW is
measured through faiss's own implementation (same algorithm, same parameters).

Measured: build time from scratch, single-vector and batch insert, one-id delete, whole-file
serialize/parse (there is no incremental durable append), query latency and RECALL@10 against
numpy exact, and faiss's own flat (brute force) scan for comparison.

Run: python _main/_index-hnsw-probe.py [--json OUT]
"""
import argparse
import json
import os
import sys
import time

import numpy as np

D = 256
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "_index-ann")
N = 120_000
M = 16
EFC = 200
Q = 200          # queries used for latency/recall
K = 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    import faiss

    os.makedirs(WORK, exist_ok=True)
    rng = np.random.default_rng(2026)
    X = rng.standard_normal((N, D), dtype=np.float32)
    X /= np.linalg.norm(X, axis=1, keepdims=True)
    Xq = rng.standard_normal((Q, D), dtype=np.float32)
    Xq /= np.linalg.norm(Xq, axis=1, keepdims=True)

    res = {"probe": "_index-hnsw-probe.py", "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "faiss": faiss.__version__, "vectors": N, "dims": D, "M": M, "efConstruction": EFC,
           "metric": "INNER_PRODUCT on unit vectors (= cosine)", "queries": Q}

    # exact ground truth (numpy) for recall
    t0 = time.perf_counter()
    exact = np.argsort(-(Xq @ X.T), axis=1)[:, :K]
    res["numpy_exact_groundtruth_s_for_200_queries"] = round(time.perf_counter() - t0, 2)

    # faiss FLAT (brute force, SIMD)
    flat = faiss.IndexFlatIP(D)
    flat.add(X)
    t0 = time.perf_counter()
    _, If = flat.search(Xq, K)
    flat_ms = (time.perf_counter() - t0) / Q * 1e3
    res["faiss_flat_bruteforce"] = {"ms_per_query_k10": round(flat_ms, 3),
                                    "recall": 1.0,
                                    "index_bytes": int(flat.ntotal * D * 4)}

    # HNSW build
    index = faiss.IndexHNSWFlat(D, M, faiss.METRIC_INNER_PRODUCT)
    index.hnsw.efConstruction = EFC
    t0 = time.perf_counter()
    index.add(X)
    build_s = time.perf_counter() - t0
    res["build_120k"] = {"seconds": round(build_s, 2), "vectors_per_s": round(N / build_s),
                         "note": "faiss HNSW build is single-threaded"}
    res["hnsw_ram_bytes_reported"] = int(index.ntotal * (D * 4 + M * 2 * 4))

    # incremental: one vector, then a batch
    v = rng.standard_normal((1, D), dtype=np.float32)
    v /= np.linalg.norm(v)
    t0 = time.perf_counter()
    index.add(v)
    res["add_one_vector_ms"] = round((time.perf_counter() - t0) * 1e3, 2)
    B = rng.standard_normal((1000, D), dtype=np.float32)
    B /= np.linalg.norm(B, axis=1, keepdims=True)
    t0 = time.perf_counter()
    index.add(B)
    res["add_1000_vectors_s"] = round(time.perf_counter() - t0, 3)

    # delete one id out of 121001
    ids = np.array([5000], dtype=np.int64)
    t0 = time.perf_counter()
    index.remove_ids(ids)
    res["remove_ids_one_id_ms"] = round((time.perf_counter() - t0) * 1e3, 2)
    res["ntotal_after_remove"] = int(index.ntotal)

    # serialize: memory -> bytes -> file (the ONLY durability point)
    t0 = time.perf_counter()
    blob = faiss.serialize_index(index)
    ser_s = time.perf_counter() - t0
    path = os.path.join(WORK, "hnsw.faiss")
    t0 = time.perf_counter()
    faiss.write_index(index, path)
    write_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    idx2 = faiss.read_index(path)
    read_s = time.perf_counter() - t0
    res["serialize"] = {"serialize_s": round(ser_s, 3), "write_index_s": round(write_s, 3),
                        "read_index_s": round(read_s, 3), "file_bytes": os.path.getsize(path),
                        "file_MiB": round(os.path.getsize(path) / 2**20, 1),
                        "payload_bytes": N * D * 4,
                        "overhead_bytes_per_vector": round(
                            (os.path.getsize(path) - N * D * 4) / N, 1)}

    # query latency + recall vs exact, efSearch sweep
    res["search"] = {}
    for ef in (16, 32, 64, 128, 256):
        index.hnsw.efSearch = ef
        t0 = time.perf_counter()
        _, I = index.search(Xq, K)
        per_q = (time.perf_counter() - t0) / Q * 1e3
        rec = float(np.mean([len(set(I[i]) & set(exact[i])) / K for i in range(Q)]))
        res["search"]["ef=%d" % ef] = {"ms_per_query_k10": round(per_q, 3), "recall@10": round(rec, 4)}
        if ef == 16:
            res["search_ef16_example"] = {"query0_index": [int(x) for x in I[0]],
                                          "query0_exact": [int(x) for x in exact[0]]}

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
