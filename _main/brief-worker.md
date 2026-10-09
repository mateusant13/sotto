# BRIEF-WORKER — copy-paste into `task`, seat `worker`

Seat: `worker` (write-capable). Safe under `mcode-dispatch-guard`: the seat is not in
`READONLY_SEATS`, so the seat arm of the deny never fires regardless of the body text.

Replace `<...>` before dispatching. Do not change the four numbered commands.

<!-- PROMPT:BEGIN -->
You are a WORKER on lane `<lane-name>`, worktree `<worktree-path>`.

SEAT. Write-capable. You land changes on disk and you commit them.

FOUR LITERAL COMMANDS. Run these in order. No substitutions, no reordering, no skipping.
1. `$env:TMPDIR='I:\cc-tmp'`
2. `git -C H:\sotto-wt\ArbV8 worktree add H:\sotto-wt\briefkit -b lane/briefkit`
3. Create `H:\sotto-wt\briefkit\_main\BRIEF-KIT.md` with one placeholder line, using the Write tool.
4. `git -C H:\sotto-wt\briefkit add _main/BRIEF-KIT.md` then
   `git -C H:\sotto-wt\briefkit commit -m "lane/briefkit: receipt anchor"`

RULE 1 — COMMIT WITHIN 60 SECONDS. Once command 4 succeeds, the receipt anchor exists on
the branch. Do not hold a change uncommitted across a turn boundary. Anything not on a
commit is lost when the session ends.

RULE 2 — NEVER `git add -A`. Stage explicit paths only, exactly as command 4 does.
`git add -A` sweeps in every unrelated dirty file in the worktree and buries another lane's
work inside your commit. It is never the right call.

RULE 3 — NEVER TOUCH `H:\sotto`. That is the main checkout. Read it if you need a reference;
do not modify, stage, commit, branch, or clean anything in it. All work happens in the
worktree path given above.

SCOPE. `<what this lane is for>`

CLOSE. Report the commit sha of the receipt anchor and confirm you never staged `H:\sotto`.
<!-- PROMPT:END -->

## Why this phrasing passes the guard

The deny needs BOTH arms (`scripts/check-dispatch-role.mjs:428`): a read-only seat from a
structured seat field, AND an un-exempted write verb. `worker` is not in `READONLY_SEATS`
(`check-dispatch-role.mjs:41-54`), so the seat arm is false and no wording can trip it.