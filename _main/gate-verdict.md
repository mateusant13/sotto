# gate-verdict: the fixed scale gate, run for real

Lane: real-execution verification of the gate fix (b5d945c -> 6aa764b -> 615110e,
branch `feat/scale-gate-4`, merged into `main`).
Worktree: `H:\sotto-wt\gateverify`, branch `chore/gate-verify-1`.
Runner: `_main/gate_run.ps1` (mine). Probe, gate and index: NOT touched.

## VERDICT: the gate fix is CONFIRMED on a real run -- and the real numbers FAIL

The brief expected the compliant run to PASS. **It does not.** That is not a
gate defect; it is the gate doing exactly what it was fixed to do. Both facts
are below, separated, because they are different claims.

**Claim 1 -- the fixed gate can say NO to a real execution. PROVEN.**
At the full target population n=211200 the probe returns `RESULT: FAIL` and
**rc=1**, on the *exact* condition that made the old gate print
`RESULT: PASS`: `frac_under_16ms=0.000`. Old logic shipped a PASS on a 3.3x
miss; the fixed gate, fed the same real measurement, goes RED with a non-zero
exit code. `_main/scale_gate_selftest.py` proved this with 9/9 synthetic arms;
this proves it through the real `store.py` / `search.py`.

**Claim 2 -- the 16 ms budget is not met, even at 1/10th scale.** Not a gate
bug, a performance fact. See the table.

## Flag names actually used

The probe's argv is **positional only**: `slice_scale_probe.py [N] [n_queries]
[chunk]` (line 15 and `main()` lines 186-188). There is **no `--budget-ms`
flag**; `BUDGET_MS = 16.0` is a module constant (line 47).

- Run A: `python _moved/aireplay/_main/slice_scale_probe.py 20000 100 4096`
- Run C: `python _moved/aireplay/_main/slice_scale_probe.py 211200 100 4096`
- Run B: same module and same measurement path, with `BUDGET_MS` and
  `P95_MAX_MS` re-pointed to `0.0001` from OUTSIDE at import time by
  `gate_run.ps1` (`gate.__defaults__` rebound too, since `gate()`'s `p95_max`
  default is bound at def time). The probe file on disk is unmodified; every
  number below still comes from the same real code path as Run A.

Exit codes were captured by redirecting to a file (`> file 2>&1`) and reading
`$LASTEXITCODE`. Never piped to `Select-Object -First N`.

## Measured (all runs: <=2 threads, OMP=2 set pre-numpy by the probe)

| run | N | WINDOW | min | p50 | p95 | max | under budget | RESULT | rc |
|-----|---|--------|-----|-----|-----|-----|--------------|--------|----|
| A rep1 | 20000 | 100 timed queries | 4.58 | 9.51 | 17.95 | 28.15 | 87.0% (need 99.0%) | FAIL | 1 |
| A rep2 | 20000 | 100 timed queries | 6.23 | 12.37 | 21.11 | 23.70 | 73.0% (need 99.0%) | FAIL | 1 |
| B rep1 | 20000, budget 0.0001 ms | 100 timed queries | 5.16 | 9.67 | 17.40 | 19.69 | 0.0% | FAIL | 1 |
| B rep2 | 20000, budget 0.0001 ms | 100 timed queries | 7.76 | 19.61 | 24.50 | 30.21 | 0.0% | FAIL | 1 |
| C | 211200 | 100 timed queries | 50.80 | 75.71 | 129.45 | 151.06 | 0.0% | FAIL | 1 |

Full-scale run, as the probe prints it:

```
population      : n=211200 vectors, 100 timed queries, <=2 threads (OMP=2)
query ms        : min=50.80 p50=75.71 p95=129.45 max=151.06   (n=100 timed queries)
under 16 ms     : 0.0% (0/100 queries; gate needs 99.0%)
empty results   : 0/100
SCALE: n=211200 p50=75.71ms p95=129.45ms frac_under_16ms=0.000 mem_delta=304.2MB
GATE : budget=16ms under_need>=0.99 p95_need<=16ms  (POPULATION n=211200, WINDOW 100 queries, <=2 threads)
RESULT: FAIL
```

Run C completed in **56.8 s** (43.7 s of it the 211200-row upsert, 0.2071
ms/row; 297.1 MiB on disk; index load 1.86 s; rss delta +304.2 MB). It was run
because it fits the budget, not because it is cheap.

## FULL STDOUT, verbatim

The runner writes raw output to `_main/gate_run_*.txt`, which `.gitignore:44`
(`_main/*.txt`) keeps out of git as probe scratch. So the full streams are
reproduced here, in the committed file.

### Run A, sample 1 -- `python slice_scale_probe.py 20000 100 4096` -> **rc=1**

```
n               : 20000  dim=256 channel=visual fp32
thread budget   : 2 (env set pre-numpy) mem_source=psutil
rss before      : 36.2 MB
queries         : 100  budget=16.0 ms
chunk           : 4096 rows per upsert_embeddings call
db              : I:\cc-tmp\slice-scale-eyunb78b\scratch.sqlite  journal=wal
video_id        : 1
segments        : 20000 in 0.10s (0.0050 ms/row)
  upserted 4096/20000 (0.3s)
upsert          : 20000/20000 in 1.77s (0.0887 ms/row)
embeddings in db: 20000
db on disk      : 28.1 MiB (page_size=4096)
SearchIndex     : n=20000 dim=256 load=0.21s rss=58.5 MB

window          : 2026-10-07 15:35:33 -> 15:35:36 (3.5s elapsed)
population      : n=20000 vectors, 100 timed queries, <=2 threads (OMP=2)
query ms        : min=4.58 p50=9.51 p95=17.95 max=28.15   (n=100 timed queries)
under 16 ms     : 87.0% (87/100 queries; gate needs 99.0%)
empty results   : 0/100
rss after       : 82.9 MB  delta=+46.7 MB
FAIL: latency budget MISSED: 87.0% of 100 queries under 16 ms, need 99.0% (min=4.58 p50=9.51 p95=17.95 max=28.15 ms; POPULATION n=20000, WINDOW 100 timed queries, <=2 threads)
FAIL: p95 17.95 ms over the 16 ms ceiling: 100 timed queries, p50=9.51 max=28.15 ms (POPULATION n=20000, WINDOW 100 timed queries, <=2 threads)

SCALE: n=20000 p50=9.51ms p95=17.95ms frac_under_16ms=0.870 mem_delta=46.7MB
GATE : budget=16ms under_need>=0.99 p95_need<=16ms  (POPULATION n=20000, WINDOW 100 queries, <=2 threads)
RESULT: FAIL
```

### Run B, sample 1 -- budget forced to 0.0001 ms -> **rc=1**

```
n               : 20000  dim=256 channel=visual fp32
thread budget   : 2 (env set pre-numpy) mem_source=psutil
rss before      : 35.6 MB
queries         : 100  budget=0.0001 ms
chunk           : 4096 rows per upsert_embeddings call
db              : I:\cc-tmp\slice-scale-4t0i48l7\scratch.sqlite  journal=wal
video_id        : 1
segments        : 20000 in 0.15s (0.0073 ms/row)
  upserted 4096/20000 (0.4s)
upsert          : 20000/20000 in 2.15s (0.1076 ms/row)
embeddings in db: 20000
db on disk      : 28.1 MiB (page_size=4096)
SearchIndex     : n=20000 dim=256 load=0.14s rss=58.0 MB

window          : 2026-10-07 15:35:37 -> 15:35:40 (3.8s elapsed)
population      : n=20000 vectors, 100 timed queries, <=2 threads (OMP=2)
query ms        : min=5.16 p50=9.67 p95=17.40 max=19.69   (n=100 timed queries)
under 0.0001 ms     : 0.0% (0/100 queries; gate needs 99.0%)
empty results   : 0/100
rss after       : 82.1 MB  delta=+46.5 MB
FAIL: latency budget MISSED: 0.0% of 100 queries under 0.0001 ms, need 99.0% (min=5.16 p50=9.67 p95=17.40 max=19.69 ms; POPULATION n=20000, WINDOW 100 timed queries, <=2 threads)
FAIL: p95 17.40 ms over the 0.0001 ms ceiling: 100 timed queries, p50=9.67 max=19.69 ms (POPULATION n=20000, WINDOW 100 timed queries, <=2 threads)

SCALE: n=20000 p50=9.67ms p95=17.40ms frac_under_0.0001ms=0.000 mem_delta=46.5MB
GATE : budget=0.0001ms under_need>=0.99 p95_need<=0.0001ms  (POPULATION n=20000, WINDOW 100 queries, <=2 threads)
RESULT: FAIL
```

### Run C -- `python slice_scale_probe.py 211200 100 4096` -> **rc=1**

```
n               : 211200  dim=256 channel=visual fp32
thread budget   : 2 (env set pre-numpy) mem_source=psutil
rss before      : 36.1 MB
queries         : 100  budget=16.0 ms
chunk           : 4096 rows per upsert_embeddings call
db              : I:\cc-tmp\slice-scale-roheg7z2\scratch.sqlite  journal=wal
video_id        : 1
segments        : 211200 in 1.80s (0.0085 ms/row)
  upserted 4096/211200 (0.3s)
  upserted 36864/211200 (5.3s)
  upserted 69632/211200 (9.9s)
  upserted 102400/211200 (14.4s)
  upserted 135168/211200 (26.9s)
  upserted 167936/211200 (35.1s)
  upserted 200704/211200 (42.0s)
upsert          : 211200/211200 in 43.73s (0.2071 ms/row)
embeddings in db: 211200
db on disk      : 297.1 MiB (page_size=4096)
SearchIndex     : n=211200 dim=256 load=1.86s rss=65.2 MB

window          : 2026-10-07 15:36:07 -> 15:37:04 (56.8s elapsed)
population      : n=211200 vectors, 100 timed queries, <=2 threads (OMP=2)
query ms        : min=50.80 p50=75.71 p95=129.45 max=151.06   (n=100 timed queries)
under 16 ms     : 0.0% (0/100 queries; gate needs 99.0%)
empty results   : 0/100
rss after       : 340.4 MB  delta=+304.2 MB
FAIL: latency budget MISSED: 0.0% of 100 queries under 16 ms, need 99.0% (min=50.80 p50=75.71 p95=129.45 max=151.06 ms; POPULATION n=211200, WINDOW 100 timed queries, <=2 threads)
FAIL: p95 129.45 ms over the 16 ms ceiling: 100 timed queries, p50=75.71 max=151.06 ms (POPULATION n=211200, WINDOW 100 timed queries, <=2 threads)

SCALE: n=211200 p50=75.71ms p95=129.45ms frac_under_16ms=0.000 mem_delta=304.2MB
GATE : budget=16ms under_need>=0.99 p95_need<=16ms  (POPULATION n=211200, WINDOW 100 queries, <=2 threads)
RESULT: FAIL
```

## What the numbers mean

1. **The gate is no longer decorative.** Every one of the five runs returned a
   non-zero rc; the impossible-budget runs failed for the right reason
   (`0.0% under 0.0001 ms`, `p95 24.50 ms over the 0.0001 ms ceiling`), not by
   accident of an unmeasured window. A PASS has not been observed yet, which
   is the correct posture for an unfixed perf problem and the wrong posture
   for a working one.
2. **16 ms is missed by ~8x at target scale** (p50 75.71, p95 129.45) and by
   ~1.3x at 1/10th scale (p95 17.95-21.11 vs the 16 ms ceiling). With 100
   queries the p95 clause rides the 95th-ranked sample, and `UNDER_MIN_FRAC` is
   0.99 -- so at n=20000 the run needs 99 of 100 queries inside 16 ms and got
   73-87.
3. **The n=20000 spread is host contention, not measurement drift.** The two
   samples differ by 3 ms at p50 on an idle-ish path (min 4.58 vs 6.23) while
   every structural count is identical (`20000/20000` landed, `0/100` empty,
   `20000` in the index). This host runs many lanes at once. Treat the
   small-N absolutes as +-30%; the n=211200 miss (p50 4.7x the budget) is far
   outside any contention envelope.

## Not proven / not claimed

- **No PASS was ever observed.** I could not produce a compliant PASS, so the
  gate's happy path is unproven in the positive direction at these thresholds.
  If a PASS is wanted as a green control, it needs a lower `BUDGET_MS` or a
  smaller `N` -- the self-test's synthetic arms cover that shape already.
- Whether the 16 ms target is reachable at all with the current
  `search.py` scan is out of scope for this lane and not measured here.
- Run B proves the threshold *clause* fires. It does not prove the CLI has a
  budget knob -- it does not; there is no such flag.