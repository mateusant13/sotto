# MAXCHUNKS — the 7 vs 24 caption gap

Lane: `lane/maxch` (worktree `H:\sotto-wt\maxch`, base `main` @ a296318).
Source receipt under test: `_main/PIPELINE-WORKS.md`.

Two claims are under test:

1. **max-chunks hypothesis** — that the old receipt's `7 captions` came from
   `--max-chunks 40`, not from a broken pipeline. The uncapped run reported 24.
2. **live-capture hypothesis** — that the old receipt captured a LIVE DEVICE
   (`WASAPI loopback: CABLE Input`, `230 meter`) because `--audio` was ignored
   without `--selftest`, so its Portuguese text was the room, not `sample1.flac`.

Numbers in this file always carry POPULATION and WINDOW. Results appended below
as experiments complete.

## METHOD

`main:worker/sotto_worker.py` is copied into the worktree (never `git checkout`
over `H:\sotto`). Weights come from `H:\sotto\worker\models` via `--model`.
Invocation is always `--selftest --audio <file>` (BOTH flags), plus `--max-chunks N`.

## RESULTS

(filled in below)