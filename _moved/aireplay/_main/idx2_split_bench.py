"""Is a 2-thread split of the KNN scan actually faster on this box?

The fix has two levers and only one of them is certain: dropping the two
wasted scans (measured, 3x -> 1x).  The other is a claim that the remaining
206 MiB scan splits across the 2 threads the brief allows.  A claim is not a
measurement, so this measures it BEFORE the fix is written.

numpy releases the GIL inside BLAS, so a ThreadPoolExecutor(2) split is real
parallelism, not interleaving.  Verifies BOTH: the split is faster, and it
returns the same top-k as the single-thread path.

Usage: python idx2_split_bench.py [N]
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import sys  # noqa: E402
import time  # noqa: E402
from concurrent.futures import ThreadPoolExecutor  # noqa: E402

import numpy as np  # noqa: E402

DIM = 256
K = 100
N = int(sys.argv[1]) if len(sys.argv) > 1 else 211200
WINDOW = 40

rng = np.random.default_rng(20261007)
M = rng.standard_normal((N, DIM)).astype(np.float32)
M /= np.linalg.norm(M, axis=1, keepdims=True).clip(1e-12)
M = np.ascontiguousarray(M)
Q = rng.standard_normal((DIM,)).astype(np.float32)
Q /= np.linalg.norm(Q)

mib = M.nbytes / 1024 ** 2
print(f"N={N} dim={DIM} matrix={mib:.2f} MiB  threads=2 max")
print(f"to meet 16 ms this scan needs {mib / 1024 / 0.016:.1f} GiB/s\n")

pool = ThreadPoolExecutor(2)
NB = 2
bounds = [(i * N // NB, (i + 1) * N // NB) for i in range(NB)]
bufs = [np.empty(hi - lo, dtype=np.float32) for lo, hi in bounds]


def scan_1t():
    sims = M @ Q
    take = min(K, sims.shape[0])
    top = np.argpartition(sims, sims.shape[0] - take)[-take:]
    return top, sims


def scan_2t():
    def work(i):
        lo, hi = bounds[i]
        np.dot(M[lo:hi], Q, out=bufs[i])
    list(pool.map(work, range(NB)))
    sims = np.concatenate(bufs)
    take = min(K, sims.shape[0])
    top = np.argpartition(sims, sims.shape[0] - take)[-take:]
    return top, sims


# correctness first: identical top-k?
t1, s1 = scan_1t()
t2, s2 = scan_2t()
same = np.array_equal(np.sort(s1[t1]), np.sort(s2[t2]))
print(f"top-k identical between 1t and 2t: {same}\n")

for name, fn in (("1 thread ", scan_1t), ("2 threads", scan_2t)):
    for _ in range(3):
        fn()
    ts = []
    for _ in range(WINDOW):
        t0 = time.perf_counter()
        fn()
        ts.append((time.perf_counter() - t0) * 1000.0)
    ts.sort()
    p50 = ts[len(ts) // 2]
    print(f"{name}: p50={p50:7.2f}ms p95={ts[int(.95 * len(ts))]:7.2f}ms "
          f"min={ts[0]:7.2f}ms  -> {mib / 1024 / (p50 / 1000):5.1f} GiB/s")

pool.shutdown()