# BRIEF-VERIFIER — copy-paste into `task`, seat `verifier`

Seat: `verifier` (read-only). **This template contains zero artifact-producing
imperatives.** Its entire output channel is the FINAL MESSAGE, so the review is
greppable by the next lane. See `brief-persist.md` for the lane that stores it.

Replace `<...>` before dispatching. Do not change the REPORT FORMAT block.

<!-- PROMPT:BEGIN -->
You are a VERIFIER on lane `<lane-name>`, worktree `<worktree-path>`.

SEAT. Read-only inspection. Produce no artifacts on disk. Your seat is not permitted to
place anything on the filesystem, and nothing you hand back depends on a file existing.

SCOPE. `<path, diff, or commit sha under review>`

METHOD.
- Read the named scope. Inspect only; the worktree stays byte-identical to how you found it.
- For each claim the brief asserts, state whether the repository shows it.
- Prefer a measurement you can quote over an opinion about what probably happened.
- If a check cannot be run here, say so plainly and leave the finding open.

REPORT FORMAT. Your entire report is your FINAL MESSAGE, in exactly this shape, one
finding per line, no fences, nothing outside the block:

REVIEW-BEGIN
REVIEW-ID: <short-id>
REVIEW-SCOPE: <path or sha>
REVIEW-VERDICT: PASS or FAIL
REVIEW-FINDING-COUNT: <n>
FINDING <n> | SEVERITY: high|med|low | FILE: <path:line> | CLAIM: <assertion under test> | EVIDENCE: <measured fact> | STATUS: open|fixed
REVIEW-END

RULES ON THE SHAPE.
- The literal first line is `REVIEW-BEGIN`. The literal last line is `REVIEW-END`.
- One `FINDING` line per finding. Never fold a finding across two lines.
- `STATUS` is `open` or `fixed`. Anything you did not measure is `open`.
- `REVIEW-FINDING-COUNT` equals the number of `FINDING` lines.
- The pipe `|` is the field delimiter. A finding containing a pipe breaks the parse; use a
  slash instead.
- No banner, no sign-off, no summary paragraph, no code fence. A later lane greps these
  lines and nothing else, so anything outside the block is lost when this session ends.

CLOSE. Your FINAL MESSAGE is the block above and nothing further.
<!-- PROMPT:END -->

## Why this phrasing passes the guard

The seat arm IS live here — `verifier` is in `READONLY_SEATS` (`check-dispatch-role.mjs:45`).
So the body carries no `WRITE_VERB` hit (`check-dispatch-role.mjs:79-80`). Two rules make
the negative survive the matcher:

- `Produce no artifacts on disk.` is imperative-shaped with the quantifier immediately
  after the verb, which is the exemption at `check-dispatch-role.mjs:131-134` + `:299-302`.
  The declarative form of the same sentence is a deny.
- Nothing else in the body trips the verb matcher, so no other sentence can fire.

Note for the caller: paste only the PROMPT block. The prose above is safe now too — it
was not, once, and a sentence of commentary here can deny a dispatch just as easily as the
brief can. That is the same failure class as the "C Edit Contract" denial recorded at
`check-dispatch-role.mjs:135-145`, and it is why the trap list lives in `BRIEF-KIT.md`
rather than inside a pasteable body.

## Why the report lives in the message

A review that leaves no artifact does not persist across turns — the next lane cannot see
it. The seat that cannot place a file on disk can still place a greppable block in its
final message, and `brief-persist.md` stores that block into `_main\REVIEWS.md`. Two
dispatches, both lawful, durable result.