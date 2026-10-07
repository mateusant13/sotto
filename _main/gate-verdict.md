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