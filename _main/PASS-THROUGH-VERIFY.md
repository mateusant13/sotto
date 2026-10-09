# PASS-THROUGH-VERIFY

Lane: `lane/ptverify` (worktree `H:\sotto-wt\ptverify`, branch off `lane/mergeall` @ 7242a69)

Purpose: re-measure the four load-bearing claims with an explicit POPULATION and WINDOW,
instead of repeating single-run numbers as if they were measurements.

- **TEMP:** `$env:TMPDIR='I:\cc-tmp'`
- **Weights:** `H:\sotto\worker\models` (9 dirs) — this worktree is a COPY and has none.

## Claims under test

1. `PIPELINE-WORKS.md` numbers vs `lane/e2e` (captions / RTF / RSS size, `--audio` ignored without `--selftest`).
2. Portuguese-shaped ASR defect: reproduces or not; and was the bad sample a live-room capture.
3. 16 ms budget: `<=25 ms @ N=211200` claim, `KeyError: 'rank'` non-reproduction.
4. Fake-worker disclosure drift 5 -> 8, and the strength of "0 contaminated".

## Status

In progress. Results table below is populated only from runs executed in this lane.

| # | Claim | Verdict | Population | Window | rc |
|---|-------|---------|-----------|--------|----|
| 1 | PIPELINE-WORKS | pending | - | - | - |
| 2 | PT defect | pending | - | - | - |
| 3 | 16 ms | pending | - | - | - |
| 4 | Stand-ins | pending | - | - | - |

No receipt is retracted by this lane. Findings only.