# CRON-TRUTH — attempt 3 (lane/cront)

**Status: ANCHOR COMMITTED. Investigation in progress.**
Attempt 3 of 3. Attempts 1 and 2 failed leaving only the anchor commit.

## Anchor facts (measured, not assumed)

- Worktree: `H:\sotto-wt\cront`
- Branch: `lane/cront`
- Base HEAD at attempt 3 start: `26a8223`
- `git worktree list` exit 0; worktree present; `git status --porcelain` EMPTY at start (clean).

## Question under measurement

Does cron `d43fb9be-283d-4dd3-8e73-d9fb562fd181` actually FIRE and DELIVER?

Reported preconditions at attempt 3 start: armed with `*/3`, but `claimId=None`,
`deliveryAttempts=0`. Zero firings observed in the entire session.

## Known confound (do not rediscover)

The scheduler hydrates from the store ONLY at process start (`restoreActiveJobs`,
in-memory Map). A cron row written while mcode is running does NOT fire until the
next process start. Therefore "no firing observed" is NOT by itself a defect.

The deliverable is separating:
  (a) defect — scheduler never fires a cron it has hydrated
  (b) hydration limit — cron was written/armed after process start and was never
      hydrated into the running process

## Verdict

UNKNOWN — investigation not yet complete. See sections below as they land.