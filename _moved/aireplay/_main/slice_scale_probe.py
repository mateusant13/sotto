"""Scale the population from n=1 to n=N and measure the REAL numbers.

slice_upsert.py proved the round-trip at n=1 (one vector, one channel, one run).
That cannot speak to the real target: 211 200 vectors of 256 dims fp32 = 206.25 MiB
with a 16 ms/query budget at <=2 threads.  This probe moves the population to N
(default 211200) and reports what actually happens, through the REAL store.py and
search.py APIs only -- no private path, no benchmark harness of its own.

SYNTHETIC ONLY: numpy default_rng noise, a scratch DB in tempfile.mkdtemp().
No real media, no owner library.

THREADS: exactly <=2, via OMP/OPENBLAS/MKL/NUMEXPR env set BEFORE numpy is
imported (the owner's stutter at 731.9% CPU came from probes like this one).

Usage:  python slice_scale_probe.py [N] [n_queries] [chunk]

EXIT:  0 only if every one of the N embeddings landed AND every query returned
       at least one hit.  A gate that cannot say NO is useless.
"""
import os

# --- thread budget FIRST, before numpy exists in this process ---------------
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import pathlib  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src" / "index"))

import store, search  # noqa: E402

store.set_thread_budget(2)
import numpy as np  # noqa: E402

DIM = 256
CHANNEL = "visual"           # one of search.VECTOR_CHANNELS, as at n=1
MODEL = "slice-scale-rng-v1"
SEED = 20261007
BUDGET_MS = 16.0


# --------------------------------------------------------------------------
# resident memory: psutil if importable, else the Windows working set by ctypes
# --------------------------------------------------------------------------
def _psutil_rss_mb():
    try:
        import psutil
    except Exception:
        return None
    return psutil.Process(os.getpid()).memory_info().rss / 1024 ** 2


def _ctypes_rss_mb():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    handle = ctypes.windll.kernel32.GetCurrentProcess()
    psapi = ctypes.windll.psapi
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return pmc.WorkingSetSize / 1024 ** 2


def rss_mb():
    v = _psutil_rss_mb()
    return v if v is not None else _ctypes_rss_mb()


def rss_source():
    return "psutil" if _psutil_rss_mb() is not None else "ctypes"


# --------------------------------------------------------------------------
def main(argv):
    n = int(argv[1]) if len(argv) > 1 else 211200
    n_queries = int(argv[2]) if len(argv) > 2 else 100
    chunk = int(argv[3]) if len(argv) > 3 else 4096
    if n <= 0:
        print("N must be positive")
        return 2

    mem_source = rss_source()
    mem_start = rss_mb()
    print(f"n               : {n}  dim={DIM} channel={CHANNEL} fp32")
    print(f"thread budget   : 2 (env set pre-numpy) mem_source={mem_source}")
    print(f"rss before      : {mem_start:.1f} MB")
    print(f"queries         : {n_queries}  budget={BUDGET_MS} ms")
    print(f"chunk           : {chunk} rows per upsert_embeddings call")

    rng = np.random.default_rng(SEED)
    tmp = tempfile.mkdtemp(prefix="slice-scale-")
    db = pathlib.Path(tmp) / "scratch.sqlite"
    conn = store.connect(db)
    print(f"db              : {db}  journal={store.journal_mode(conn)}")

    video_id = store.upsert_video(
        conn,
        content_key=rng.bytes(32).hex(),
        path="/synthetic/scale-nonexistent.mp4",
        size_bytes=1_234_567,
        mtime_ns=1_760_000_000_000_000_000,
        duration_ms=60_000,
        codec="synthetic",
        w=1920, h=1080, fps=25.0,
    )
    print(f"video_id        : {video_id}")

    # -- segments: real store API, batched inside explicit transactions so the
    #    211k INSERTs are not 211k fsyncs (store.connect uses isolation_level=None,
    #    so BEGIN/COMMIT is the correct way to batch).
    t_seg = time.perf_counter()
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
    seg_s = time.perf_counter() - t_seg
    print(f"segments        : {len(seg_ids)} in {seg_s:.2f}s "
          f"({seg_s * 1000 / max(1, n):.4f} ms/row)")

    # -- vectors + embeddings through the REAL upsert_embeddings -------------
    #    Generated per chunk: 211200x256 fp32 is 206 MiB and the payload list
    #    holds a copy of every blob, so holding all of it would double the peak.
    t_up = time.perf_counter()
    done = 0
    for start in range(0, n, chunk):
        m = min(chunk, n - start)
        vecs = rng.standard_normal((m, DIM)).astype(np.float32)
        rows = [(seg_ids[start + j], CHANNEL, vecs[j]) for j in range(m)]
        store.upsert_embeddings(conn, rows, model=MODEL, dtype="fp32", dim=DIM)
        done += m
        del vecs, rows
        if start % (chunk * 8) == 0:
            print(f"  upserted {done}/{n} "
                  f"({time.perf_counter() - t_up:.1f}s)", flush=True)
    up_s = time.perf_counter() - t_up
    ms_per_row = up_s * 1000 / max(1, n)
    print(f"upsert          : {done}/{n} in {up_s:.2f}s "
          f"({ms_per_row:.4f} ms/row)")

    landed = int(conn.execute(
        "SELECT COUNT(*) FROM embedding WHERE model = ? AND dim = ?",
        (MODEL, DIM)).fetchone()[0])
    print(f"embeddings in db: {landed}")
    sizes = store.store_bytes(conn)
    print(f"db on disk      : {sizes['file_mib']:.1f} MiB "
          f"(page_size={sizes['page_size']})")

    # -- load the matrix the way search.py loads it, then time EVERY query ----
    mem_loaded = rss_mb()
    t_load = time.perf_counter()
    idx = search.SearchIndex(conn)
    load_s = time.perf_counter() - t_load
    print(f"SearchIndex     : n={idx.n} dim={idx.dim} load={load_s:.2f}s "
          f"rss={mem_loaded:.1f} MB")
    if idx.n != landed:
        print(f"FAIL: index holds {idx.n} vectors but {landed} rows landed")
        return 1

    qrng = np.random.default_rng(SEED + 1)
    times_ms = []
    empty = 0
    for _ in range(n_queries):
        qi = int(qrng.integers(0, idx.n))       # an in-population query
        q = idx.vecs[qi]
        t0 = time.perf_counter()
        hits = idx.search(q, k=10)
        times_ms.append((time.perf_counter() - t0) * 1000.0)
        if not hits:
            empty += 1

    times_ms.sort()
    p50 = statistics.median(times_ms)
    p95 = times_ms[min(len(times_ms) - 1, int(0.95 * len(times_ms)))]
    under = sum(1 for t in times_ms if t < BUDGET_MS) / len(times_ms)
    mem_end = rss_mb()

    print(f"\nquery ms        : min={times_ms[0]:.2f} p50={p50:.2f} "
          f"p95={p95:.2f} max={times_ms[-1]:.2f}")
    print(f"under {BUDGET_MS:g} ms     : {under * 100:.1f}%")
    print(f"empty results   : {empty}/{n_queries}")
    print(f"rss after       : {mem_end:.1f} MB  delta={mem_end - mem_start:+.1f} MB")

    ok = True
    if landed != n:
        print(f"FAIL: {landed} embeddings landed, expected {n}")
        ok = False
    if empty:
        print(f"FAIL: {empty} queries returned no hit")
        ok = False

    print(f"\nSCALE: n={n} p50={p50:.2f}ms p95={p95:.2f}ms "
          f"frac_under_16ms={under:.3f} mem_delta={mem_end - mem_start:.1f}MB")

    conn.close()
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))