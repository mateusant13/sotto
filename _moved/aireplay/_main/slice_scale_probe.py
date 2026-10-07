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
       at least one hit AND the measured latency threshold is met (>=99% of
       the timed queries under 16 ms AND p95 <= 16 ms).  A gate that cannot
       say NO is useless -- see the gate() docstring for how this one shipped
       a PASS on a 3.3x budget miss.  Non-zero on every FAIL.
"""
import os

# --- thread budget FIRST, before numpy exists in this process ---------------
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import pathlib  # noqa: E402
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

# --- the gate's thresholds, declared here so they are auditable -------------
# A query MEETS the budget when it returns in under BUDGET_MS.  PASS requires
# BOTH clauses below, so that neither one alone can carry a broken measurement:
#   UNDER_MIN_FRAC : at least this fraction of the timed queries under budget
#   P95_MAX_MS     : the p95 of the timed queries at or under this ceiling
# UNDER_MIN_FRAC is 0.99 and not 1.00 because a single GC pause in a timing
# sample should not decide the verdict; the p95 clause is what stops the tail
# from being waved through.  Every threshold the gate uses must appear here.
UNDER_MIN_FRAC = 0.99
P95_MAX_MS = BUDGET_MS


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
# THE GATE.
#
# DEFECT (measured, not hypothetical): this file printed "RESULT: PASS" at
# n=211200 with frac_under_16ms=0.000 -- p50 52.94 ms, p95 68.35 ms, max
# 86.25 ms, NOT ONE of 100 queries inside the 16 ms budget.  The exact logic
# error was this: the verdict was the accumulator
#         ok = True
#         if landed != n: ...  ok = False      # data completeness only
#         if empty:     ...  ok = False      # data completeness only
# which never mentions BUDGET_MS, under, p50 or p95 anywhere.  The latency was
# measured, printed and printed again in the SCALE line -- and then discarded
# by the one thing whose job was to judge it.  `ok` was a COMPLETENESS check
# wearing the label of a THRESHOLD check: it could only say NO if rows went
# missing, so it said PASS to a total miss.  A gate that cannot say NO is
# worse than no gate, because it manufactures confidence.
#
# The fix is not a bigger `ok`.  It is that the latency threshold is now a
# clause of the verdict, computed from the same numbers that are printed, and
# _main/scale_gate_selftest.py feeds this gate a deliberately broken
# measurement and asserts it goes RED.
# --------------------------------------------------------------------------
def latency_stats(times_ms):
    """(count, min, p50, p95, max, frac_under_budget) from query times in ms.

    THE SINGLE SOURCE OF THE PRINTED NUMBERS: main() prints what the gate
    judged, so a gate and its own evidence can never drift apart.
    """
    t = sorted(times_ms)
    n = len(t)
    if n == 0:
        raise ValueError("latency_stats: no query timings collected")
    # Nearest-rank, kept bit-for-bit as the probe has always computed it
    # (index min(len-1, int(q*len))) so the p95 printed here stays comparable
    # with the 68.35 ms recorded in _main/scale-verdict.md.  It reads one rank
    # high at q=0.95, which makes the gate STRICTER, never looser.
    p50 = t[min(n - 1, int(0.50 * n))]
    p95 = t[min(n - 1, int(0.95 * n))]
    under = sum(1 for x in t if x < BUDGET_MS) / n
    return n, t[0], p50, p95, t[-1], under


def gate(n, landed, n_queries, empty, times_ms,
         under_min=UNDER_MIN_FRAC, p95_max=P95_MAX_MS):
    """Decide the verdict from MEASURED numbers.  -> (ok: bool, reasons: list[str])

    `reasons` is empty if and only if ok.  Each reason names the population it
    was measured over, so a FAIL line is evidence and not an assertion.
    """
    reasons = []
    if landed != n:
        reasons.append(f"only {landed}/{n} embeddings landed in the store")
    if empty:
        reasons.append(f"{empty}/{n_queries} queries returned no hit")

    if not times_ms:
        reasons.append(
            f"no query timings collected over a population of "
            f"{n_queries} queries at n={n}: unmeasured is not a pass")
        return False, reasons

    cnt, lo, p50, p95, hi, under = latency_stats(times_ms)
    window = f"POPULATION n={n}, WINDOW {cnt} timed queries, <=2 threads"

    if under < under_min:
        reasons.append(
            f"latency budget MISSED: {under * 100:.1f}% of {cnt} queries under "
            f"{BUDGET_MS:g} ms, need {under_min * 100:.1f}% "
            f"(min={lo:.2f} p50={p50:.2f} p95={p95:.2f} max={hi:.2f} ms; "
            f"{window})")
    if p95 > p95_max:
        reasons.append(
            f"p95 {p95:.2f} ms over the {p95_max:g} ms ceiling: {cnt} timed "
            f"queries, p50={p50:.2f} max={hi:.2f} ms ({window})")

    return (not reasons), reasons


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
    win_t0 = time.perf_counter()
    win_start = time.strftime('%Y-%m-%d %H:%M:%S')
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

    mem_end = rss_mb()
    mem_delta = mem_end - mem_start

    # window + population header: every count below is denominated by these
    t_end = time.perf_counter()
    print(f"\nwindow          : {win_start} -> {time.strftime('%H:%M:%S')} "
          f"({t_end - win_t0:.1f}s elapsed)")
    print(f"population      : n={n} vectors, {n_queries} timed queries, "
          f"<=2 threads (OMP={os.environ['OMP_NUM_THREADS']})")

    cnt, lo, p50, p95, hi, under = latency_stats(times_ms)
    print(f"query ms        : min={lo:.2f} p50={p50:.2f} "
          f"p95={p95:.2f} max={hi:.2f}   (n={cnt} timed queries)")
    print(f"under {BUDGET_MS:g} ms     : {under * 100:.1f}% "
          f"({sum(1 for t in times_ms if t < BUDGET_MS)}/{cnt} queries; "
          f"gate needs {UNDER_MIN_FRAC * 100:.1f}%)")
    print(f"empty results   : {empty}/{n_queries}")
    print(f"rss after       : {mem_end:.1f} MB  delta={mem_delta:+.1f} MB")

    ok, reasons = gate(n, landed, n_queries, empty, times_ms)
    for r in reasons:
        print(f"FAIL: {r}")

    print(f"\nSCALE: n={n} p50={p50:.2f}ms p95={p95:.2f}ms "
          f"frac_under_{BUDGET_MS:g}ms={under:.3f} mem_delta={mem_delta:.1f}MB")
    print(f"GATE : budget={BUDGET_MS:g}ms under_need>={UNDER_MIN_FRAC:.2f} "
          f"p95_need<={P95_MAX_MS:g}ms  "
          f"(POPULATION n={n}, WINDOW {cnt} queries, <=2 threads)")

    conn.close()
    print("RESULT: PASS" if ok else "RESULT: FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))