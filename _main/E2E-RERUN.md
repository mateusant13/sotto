# E2E RERUN — independent re-verification of the end-to-end captions claim

Lane: lane/e2e (== main @ 8d33896). Worktree: H:\sotto-wt\e2e-rerun.
Worktree note: brief said H:\sotto-wt\e2e, but that path is already a worktree held
by another lane (feat/probe-e2e-2, untracked files present). Not clobbered.

Command (BOTH flags; omitting --selftest makes --audio silently ignored):
`python H:\sotto\worker\sotto_worker.py --selftest --audio H:\sotto\worker\assets\sample1.flac`

## RUN A — POPULATION = 1 run, WINDOW = 2026-10-07 ~16:38-16:39 -03:00
rc = 0. wall 23.69 s. Independent peak RSS 2417.2 MB (measured by polling probe,
not the worker's self-report).
stdout 33 non-empty lines: 24 caption, 9 status, **0 meter**.
Language: ENGLISH. tokens=120. rtf=0.47. load_s=12.75, infer_wall_s=6.318.
RECOGNISED: "going along slushy country roads and speaking to damp audiences in
drafty schoolrooms day after day for a fortnight he'll have to put in appearance
at some place of worship on Sunday morning he can come tosk immediately afterward"

Run B pending.