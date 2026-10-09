# BRIEF-PERSIST — copy-paste into `task`, seat `worker`

This is the second half of the review pattern and the reason reviews stop vanishing.

- `brief-verifier.md` — seat `verifier`, read-only, returns findings in its final message.
- **this file** — seat `worker`, write-capable, stores those findings on disk.

The verifier's report survives as long as someone with a write seat puts it somewhere.
That is this lane. Run it immediately after the verifier returns; the report exists only in
the task result until this lane commits it.

Replace `<...>` before dispatching. Paste the verifier's FINAL MESSAGE into `REPORT`.

<!-- PROMPT:BEGIN -->
You are a WORKER on lane `<lane-name>`, worktree `<worktree-path>`.

SEAT. Write-capable. Your only job is to make an already-finished review durable.

INPUT. The `REPORT` below is the final message of a read-only verifier lane. It is already
complete. Do not re-review, do not extend it, do not second-guess its verdict, and do not
investigate the code yourself.

REPORT:
```
<verifier's FINAL MESSAGE, verbatim>
```

STEPS.
1. Confirm the report contains the literal line `REVIEW-BEGIN` and the literal line
   `REVIEW-END`. If either is missing, stop and say so; do not guess the shape.
2. Take only the lines between those two markers, including the markers.
3. Append them to `H:\sotto-wt\briefkit\_main\REVIEWS.md`. Create that file with the
   single heading line `# REVIEWS` if it is not there yet. Never overwrite an earlier
   review; the file is append-only and each block stays in dispatch order.
4. `git -C H:\sotto-wt\briefkit add _main/REVIEWS.md`
5. `git -C H:\sotto-wt\briefkit commit -m "lane/<lane-name>: persist review <REVIEW-ID>"`

RULE 1 — COMMIT WITHIN 60 SECONDS. The review is not durable until step 5 returns. An
uncommitted append is lost with the session.

RULE 2 — NEVER `git add -A`. Stage ` _main/REVIEWS.md` explicitly, as step 4 does.
`git add -A` would sweep unrelated dirty files into the commit.

RULE 3 — NEVER TOUCH `H:\sotto`. That is the main checkout. Modify, stage, commit, branch
and clean nothing in it.

RULE 4 — VERBATIM. The block is stored byte-for-byte. Do not reformat it, fix its
spelling, renumber its findings, or drop a finding you dislike. It is somebody else's
measurement; your lane is storage, not editorial.

CLOSE. Report the commit sha, the `REVIEW-ID` now stored, and the new line count of
`_main\REVIEWS.md`.
<!-- PROMPT:END -->

## Why this phrasing passes the guard

Same reason as `brief-worker.md`: `worker` is absent from `READONLY_SEATS`
(`check-dispatch-role.mjs:41-54`), so the seat arm of the deny cannot fire
(`check-dispatch-role.mjs:428`) no matter what the body says.

## Why two dispatches instead of one

`verifier` cannot place the file and `worker` cannot review — the hook enforces that split
rather than the brief merely intending it (`check-dispatch-role.mjs:428`, deny path). The
pair costs one extra dispatch and buys a review that survives the turn.