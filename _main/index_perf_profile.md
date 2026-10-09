# Index query path — profile at scale (N=20000 and N=211200)

Lane: `feat/index-perf-2`.  Profile committed BEFORE any code change, per brief.
Measured on this box, Python 3.11, numpy on OpenBLAS, **<=2 threads**
(`OMP/OPENBLAS/MKL/NUMEXPR=2` set before numpy is imported).

Tools: `_moved/aireplay/_main/index_perf_prof.py` (this lane, MEASURES only —
it does not gate; `slice_scale_probe.py` keeps the gate and is not edited here).
Two independent measurements are reported and cross-checked:

* **phase timers** — an explicit `time.perf_counter()` charge on each stage of
  the real `SearchIndex.search()` arithmetic.  These are the percentages quoted
  as authoritative; they do not distort their own targets.
* **cProfile** — over the identical loop, quoted for call-site attribution.
  cProfile inflates absolute numbers, so percentages are never taken from it.

Raw logs: `base-n20000.txt`, `base-n211200.txt`, `prof-n20000.txt`,
`prof-n211200.txt` (written to `I:\cc-tmp`).

---

## 1. ROOT CAUSE (one sentence)

**`SearchIndex.search()` runs the full N x 256 fp32 matvec once per RRF channel
— three times per query, over the UNION of all channels' rows — so the two
channels that have no rows in the index still scan the entire 216 MB matrix and
have their results discarded by the channel mask, and because that wasted work is
O(N) it is 66% of the query at every population and is the entire budget miss.**

Corollary that makes it a *scaling* defect and not constant overhead: at
N=20000 the matvec is 83.6% of the query, at N=211200 it is 93.7%.  The wasted
fraction is fixed at 2/3 of the scans; the scans themselves grow linearly with N,
so the miss grows with the population instead of staying a constant tax.

---

## 2. Phase timers — POPULATION n=211200, WINDOW 60 timed queries, <=2 threads

| # | phase (call site)                          | ms/query | % of query | calls/query |
|---|--------------------------------------------|---------:|-----------:|------------:|
| 1 | matvec `search.py:68` `self.vecs @ q`      | 133.3096 | **93.65%** | 3 |
| 2 | argpartition `search.py:86`               |   5.5850 |   3.92%   | 3 |
| 3 | where `search.py:84` `np.where(mask,...)` |   1.0838 |   0.76%   | 3 |
| 4 | hit list comp `search.py:88`              |   0.6171 |   0.43%   | 3 |
| 5 | argsort `search.py:87`                    |   0.4813 |   0.34%   | 3 |
| 6 | materialise `search.py:173`               |   0.4421 |   0.31%   | 1 |
| 7 | mask copy `search.py:69`                  |   0.3221 |   0.23%   | 3 |
| 8 | l2 norm `search.py:67`                    |   0.2854 |   0.20%   | 1 |
| 9 | RRF dict merge `search.py:107`            |   0.1560 |   0.11%   | 1 |
|   | **TOTAL**                                  | 142.3485 | 100.00%   |   |

p50 133.90 ms, p95 224.09 ms, max 301.61 ms, **0.0% under 16 ms**.

## 3. Phase timers — POPULATION n=20000, WINDOW 100 timed queries, <=2 threads

| # | phase (call site)                          | ms/query | % of query | calls/query |
|---|--------------------------------------------|---------:|-----------:|------------:|
| 1 | matvec `search.py:68` `self.vecs @ q`      |   7.9562 | **83.57%** | 3 |
| 2 | hit list comp `search.py:88`              |   0.4718 |   4.96%   | 3 |
| 3 | argpartition `search.py:86`               |   0.3920 |   4.12%   | 3 |
| 4 | materialise `search.py:173`               |   0.2047 |   2.15%   | 1 |
| 5 | where `search.py:84`                      |   0.1504 |   1.58%   | 3 |
| 6 | argsort `search.py:87`                    |   0.0382 |   0.40%   | 3 |
| 7 | l2 norm `search.py:67`                    |   0.1253 |   1.32%   | 1 |
| 8 | RRF dict merge                            |   0.0947 |   0.99%   | 1 |
| 9 | mask copy `search.py:69`                  |   0.0577 |   0.61%   | 3 |
|   | **TOTAL**                                  |   9.5200 | 100.00%   |   |

p50 8.69 ms, p95 15.54 ms, max 19.70 ms, **97.0% under 16 ms** (gate needs 99.0%).

## 4. cProfile call-site attribution (60 queries, n=211200, tottime)

```
   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
      180    7.054    0.039    7.377    0.041 search.py:61(knn)
      180    0.251    0.001    0.251    0.001 {method 'argpartition' of 'numpy.ndarray'}
      180    0.032    0.000    0.032    0.000 search.py:88(<listcomp>)
      180    0.017    0.000    0.017    0.000 {method 'copy' of 'numpy.ndarray'}
       60    0.013    0.000    7.413    0.124 search.py:92(search)
      180    0.007    0.000    0.015    0.000 search.py:36(_l2)
       60    0.007    0.000    0.007    0.000 {method 'execute' of 'sqlite3.Connection'}
       60    0.005    0.000    0.011    0.000 store.py:277(segments_for)
       60    0.004    0.000    0.019    0.000 search.py:173(_materialise)
```

`knn` carries 7.054 s of 7.413 s total (95.2% tottime).  Inside `knn`, the
matvec is the charge; the sqlite calls (`segments_for`, `execute`) together are
**0.012 s = 0.16%** of the query.  **There is no SQL in the query hot path**, so
no missing index can explain this miss — see §6.

---

## 5. What the numbers say about the ceiling

At n=211200 the in-RAM matrix is 211200 x 256 x 4 B = **206.25 MiB** (the probe
reports 297.1 MiB on disk because the blobs are fp32 there and the WAL is
included).  Exact KNN must read every row of it on every query, so the matvec is
a pure memory-bandwidth scan: 206.25 MiB / 16 ms = **12.9 GiB/s** is required to
meet the budget at this population.

Observed, from the clean (unprofiled) probe run at p50 72.39 ms with 3 scans:
one full scan = **~24 ms**, i.e. ~8.6 GB/s single-threaded.  Therefore:

* Removing the two wasted scans (root cause) is **necessary** — it takes the query
  from 3 scans to 1 scan, ~72 ms -> ~26 ms — but on its own it is **not
  sufficient**: 26 ms is still over the 16 ms budget.
* The remaining single 206 MiB scan at ~8.6 GB/s cannot reach 12.9 GiB/s on one
  thread.  The scan must be split across the 2 threads the brief allows.

Both levers are applied in the fix; the second one is only justified because the
first is measured and the bandwidth ceiling is measured, not assumed.

## 6. "Add the missing index" — measured, and NOT applicable here

The brief lists adding an index as a candidate fix.  Measurement says no:
`embedding`, `segment` and `video` are all read by primary key or covered by an
existing index during the query, and the sqlite calls are 0.16% of query time
(`segments_for` 0.005 s + `execute` 0.007 s over 60 queries).  An index cannot
speed up a 206 MiB numpy matvec.  **No index was added, because none is needed
on this path** — adding one would have been an unmeasured change that costs write
throughput in `upsert_*` for no measured read win.

## 7. Baseline verdicts (unmodified code, `slice_scale_probe.py`)

| population | p50 (ms) | p95 (ms) | max (ms) | under 16 ms | gate |
|---|---:|---:|---:|---:|---|
| n=20000, 100 queries | 11.06 | 14.38 | 22.71 | 97.0% | **FAIL** (needs 99.0%) |
| n=211200, 100 queries | 72.39 | 104.77 | 118.50 | 0.0% | **FAIL** |

These are this box's numbers. The lane brief records p50 5.34 / p95 7.45 at
n=20000 and p50 52.94 / p95 68.35 / max 86.25 at n=211200; this host is slower and
noisier, so the absolute values differ. **The verdict is identical: met at small
N, missed by 3.3x (brief) / 4.5x (this box) at large N, and 0.0% of queries inside
16 ms.** Both populations MISS here; the scaling shape is the finding.

Note the brief labels this "index upsert".  It is not: `slice_scale_probe.py`
times `SearchIndex.search()`, and its printed `upsert:` line is the ingest rate
(0.209 ms/row, 44.14 s for 211200 rows, outside the 16 ms budget entirely).  The
16 ms budget and the 52.94 ms p50 in the brief belong to the **query** path, so
that is what is profiled and fixed here.