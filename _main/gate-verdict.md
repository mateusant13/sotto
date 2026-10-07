# Gate fix verified on a real run -- and a measurement caveat that matters more

## What the fixed gate did (VERIFIED)
Commit `6aa764b` + merge `615110e` on `main`. Real executions of
`_moved/aireplay/_main/slice_scale_probe.py`, rc captured by redirecting to a file and
reading `$LASTEXITCODE` (never piping to `Select-Object -First N`):

| N | p50 | p95 | frac under 16 ms | RESULT | rc |
|---|---|---|---|---|---|
| 20000 | 15.14 ms | 22.74 ms | 0.570 | FAIL | 1 |
| 5000  | 0.88 ms  | 1.79 ms  | 1.000 | PASS | 0 |

The old gate printed `RESULT: PASS` on a 3.3x budget miss. The new gate returns
**non-zero and FAIL** when the budget is missed, and PASS/0 when it is met. The
discrimination is proven in both directions on real runs, not only in the 9-arm selftest.

## The caveat: the old N=20000 "PASS" was measured on a quiet machine
An earlier run recorded N=20000 as p50 5.34 ms, p95 7.45 ms, 100% under the 16 ms budget.
Today the SAME N on the SAME commit gives p50 15.14 ms -- 2.8x slower. POPULATION of lanes
running concurrently at the moment of today's run: 13. The host was not idle.

**Consequence:** absolute latency numbers from `slice_scale_probe.py` are NOT comparable
across runs unless the fleet is quiesced. The previous scale verdict (`scale-verdict.md`,
N=211200, p50 52.94 ms, 0% under budget) was taken with a low fleet count and is therefore
likely OPTIMISTIC, not conservative -- but that direction is UNVERIFIED, not measured.

## What this does and does not invalidate
- Does NOT invalidate: the gate is fixed and can say NO. Two real runs, opposite verdicts,
  correct rc both ways.
- DOES invalidate: any claim of the form "the index meets 16 ms at N=20000". That claim is
  now withdrawn -- it does not reproduce.
- Still open: whether 16 ms is achievable at N=211200 on a QUIET host. Unmeasured.

## Method rule this exposes
A gate that discriminates is necessary and not sufficient. A MEASUREMENT also needs a
declared machine state. From now on every latency figure carries the concurrent lane count
as part of its POPULATION.
