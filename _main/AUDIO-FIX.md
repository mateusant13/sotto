# AUDIO-FIX — `--audio` silently ignored without `--selftest`

Lane: `lane/audiofix` (worktree `H:\sotto-wt\audiofix`, base `main` = 8d33896)

## P0
`worker/sotto_worker.py` drops `--audio <file>` unless `--selftest` is also passed.
Every transcription run that omitted `--selftest` captured the LIVE ROOM instead
of the requested file. Silent capture is worse than a failure: output looks valid.

## Steps 1-4 (done, in order, committed)
1. `$env:TMPDIR='I:\cc-tmp'` set per shell invocation.
2. `git -C H:\sotto-wt\ArbV8 worktree list` — `H:\sotto-wt\audiofix` did NOT
   exist. Created: `git worktree add H:\sotto-wt\audiofix -b lane/audiofix main`
   -> `H:/sotto-wt/audiofix  8d33896 [lane/audiofix]`, rc=0.
3. This receipt.
4. `git add` of this ONE file only. Never `git add -A`. Never commit to main.

## Dead-lane state
`H:\sotto-wt\argfix  fe18e22 [chore/audio-flag-1]` exists and is a prior attempt at
this same fix. Inspected separately; see the commits section of this file once read.

## Facts
- product root: `H:\sotto`
- worker: `H:\sotto\worker\sotto_worker.py` (~236 KB)
- `H:\sotto-wt\ArbV8` is a COPY worktree WITHOUT model weights — never report
  "weights absent" from there.
- panel entry: `app\webview\run.cmd`

## Work items
- A. Identify the exact condition under which `--audio` is dropped.
- B. Choose the fix (honour the flag, or fail loudly). One-sentence justification.
- C. Check that PROVES it: `--audio <file>` with NO `--selftest` must use the file
  or fail loudly. NEVER silently use the live device.
- D. Negative arm: the check must be able to go RED.
- E. Non-regression: `--selftest --audio <file>` must behave exactly as before.