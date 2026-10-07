"""Brute-force (exact) kNN in numpy: how far does a flat scan go, and when does it stop?

Question it answers, with arithmetic instead of opinion:
  "~120 k vectors of 256 dims: is a numpy brute-force scan already enough?"

Each arm: allocate an N x 256 matrix, time a full dot-product scan against one query
(vector), then top-10 extraction, then the practical bits (load time, RAM bytes, GB/s
achieved). Sizes are swept to find the point where a scan stops being free.

Run:  python _main/_index-bruteforce-probe.py [--json OUT] [--quick]
Env:  OMP_NUM_THREADS etc. must be set BEFORE numpy import (this script does not touch it;
      the lane runs a second process with OMP_NUM_THREADS=1 to get the single-core arm).
"""
import argparse
import json
import os
import platform
import sys
import time

import numpy as np

D = 256
TOP_K = 10


def timeit(fn, reps):
    fn()  # warm
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    ts.sort()
    return {
        "min_ms": ts[0] * 1e3,
        "median_ms": ts[len(ts) // 2] * 1e3,
        "max_ms": ts[-1] * 1e3,
        "reps": reps,
    }


def arm(N, dtype, reps_scan, rng):
    X = rng.standard_normal((N, D)).astype(dtype)
    q = rng.standard_normal(D).astype(dtype)
    bytes_ = X.nbytes
    out = {
        "N": N,
        "dtype": np.dtype(dtype).name,
        "matrix_bytes": bytes_,
        "matrix_MiB": bytes_ / 2**20,
    }

    def scan():
        return X @ q

    out["scan"] = timeit(scan, reps_scan)
    scores = scan()

    def topk():
        return np.argpartition(scores, -TOP_K)[-TOP_K:]

    out["topk"] = timeit(topk, max(20, reps_scan))

    # effective bandwidth of the scan: bytes read per query / time
    gbs = bytes_ / (out["scan"]["min_ms"] * 1e-3) / 1e9
    out["scan_effective_GB_per_s"] = gbs

    # cosine ranking needs a norm divide (or normalise once at insert)
    n = np.linalg.norm(X, axis=1)

    def cosine():
        return (X @ q) / (n * np.linalg.norm(q) + 1e-9)

    out["cosine_scan"] = timeit(cosine, max(3, reps_scan // 4))
    del X, scores, n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--max-n", type=int, default=1_000_000)
    a = ap.parse_args()

    rng = np.random.default_rng(12345)
    # numpy's own BLAS/multithread state is whatever the process was started with
    try:
        cfg = np.show_config(mode="dicts")
    except Exception:
        cfg = {}

    res = {
        "probe": "_index-bruteforce-probe.py",
        "when": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version,
        "numpy": np.__version__,
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count(),
        "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
        "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        "dims": D,
        "arms": [],
        "load_and_cast": {},
    }

    sizes = [120_000] if a.quick else [120_000, 250_000, 500_000, 1_000_000]
    sizes = [n for n in sizes if n <= a.max_n]
    for N in sizes:
        base_reps = max(3, min(200, int(20_000_000 / N)))
        res["arms"].append(arm(N, np.float32, base_reps, rng))
        res["arms"].append(arm(N, np.float16, base_reps, rng))

    # fp16 ON DISK, fp32 IN RAM: what does the one-time load+cast cost?
    N = min(1_000_000, a.max_n)
    t0 = time.perf_counter()
    X32 = rng.standard_normal((N, D)).astype(np.float32)
    t_gen = time.perf_counter() - t0
    X16 = X32.astype(np.float16)
    t0 = time.perf_counter()
    back = X16.astype(np.float32)
    t_cast = time.perf_counter() - t0
    res["load_and_cast"] = {
        "N": N,
        "fp32_bytes": X32.nbytes,
        "fp16_bytes": X16.nbytes,
        "generate_fp32_s": t_gen,
        "fp16_to_fp32_cast_ms": t_cast * 1e3,
        "fp16_to_fp32_effective_GB_per_s": X16.nbytes / t_cast / 1e9,
        "same_values": bool(np.array_equal(back[0], X16.astype(np.float32)[0])),
    }

    # fp16 matvec vs fp32 matvec, same N, same values: is fp16 arithmetic even a win?
    N = 120_000
    A32 = rng.standard_normal((N, D)).astype(np.float32)
    A16 = A32.astype(np.float16)
    q32 = rng.standard_normal(D).astype(np.float32)
    q16 = q32.astype(np.float16)
    res["fp16_vs_fp32_scan"] = {
        "fp32_ms": timeit(lambda: A32 @ q32, 50)["min_ms"],
        "fp16_ms": timeit(lambda: A16 @ q16, 50)["min_ms"],
        "fp16_cast_first_ms": timeit(lambda: (A16.astype(np.float32) @ q32), 20)["min_ms"],
    }

    txt = json.dumps(res, indent=2)
    print(txt)
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
