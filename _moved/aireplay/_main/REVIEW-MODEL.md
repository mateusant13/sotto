# REVIEW MODEL THAT SURVIVES ITS OWN REVIEWERS

**The measured problem.** `fleet-persistence.py`, POPULATION = every child row in
`local_runtime_sessions`, WINDOW = 2026-10-07 13:10:43 local.

| parent | children | aborted | idle | started |
|---|---|---|---|---|
| mvs_a00662 (the idle session) | 38 | **32** | 4 | 2 |
| mvs_b7a9f3 (this orchestrator) | 30 | 0 | 20 | 10 |

**32 of 38 aborted.** A lane does not outlive the turn that dispatched it.

## Why the current rule cannot survive this

`ORCHESTRATOR-PROMPT.md` says: when a lane finishes, dispatch a reviewer; a lane with no
review is not done. Against the census above that rule is **unexecutable** -- the reviewer
is dispatched by the turn that saw the lane finish, and by the next observation point both
the lane and the reviewer are aborted.

Measured today: **8 reviewers dispatched, 4 finished, 1 read.** The system produces review
objects faster than it consumes them and nothing in the design notices.

## The rule that survives

**Dispatch the reviewer in the SAME turn that dispatched the lane, and have it report into
a FILE, not into a conversation.**

1. **Same-turn dispatch.** A later reviewer may find the lane already aborted; it cannot
   read a live diff, it reads the COMMITTED artefact. Acceptance is therefore "the lane
   bytes are committed" -- visible in git, not in a task list.
2. **Report to a file.** A verdict delivered as a chat message dies with its turn. Written
   to `receipts/review-<LANE>.md` it survives. Same lesson as the queue: a row in a store
   is durable; a row in a conversation is not.
3. **Consume verdicts from DISK.** The wake loop already watches `receipts\*.md` as an
   event (it fired on exactly that signal at 12:22:17). Extend it to
   `receipts\review-*.md`, so a finished reviewer BECOMES the wake -- the one mechanism
   measured to survive turns, unlike the fleet.

## The gate

    CHK-REV-1  every committed lane has receipts/review-<LANE>.md on disk
    CHK-REV-2  that review names at least one file:line it personally inspected
    CHK-REV-3  each defect it found carries an owning lane, so a fix is routable
    CHK-REV-4  CONTROL: a review naming no file:line FAILS

CHK-REV-4 is the arm that matters: a review naming no file and no line may have read
nothing, and a file-existence check passes it happily.

## What this does NOT solve

- It does not make lanes persist. They die; 32/38. It makes their OUTPUT persist, which is
  the part that was broken.
- It does not give a same-turn reviewer an independent runtime. For genuine independence
  dispatch in a LATER turn against the committed artefact and accept the latency; each
  verdict records the id of the turn that dispatched it, so the mode is never ambiguous.