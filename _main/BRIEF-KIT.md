# BRIEF-KIT

Dispatch briefs that survive the `mcode-dispatch-guard` hook, and the reviewer pattern that
makes a review survive the turn.

**This file is NOT a pasteable brief.** It quotes forbidden phrasings on purpose so they can
be recognised. Keep every pasteable template free of them — that separation is a measured
requirement, not tidiness (see trap 14).

## Templates

| File | Seat | Purpose |
|---|---|---|
| `brief-worker.md` | `worker` | Lands a change and commits it. Carries the four literal commands. |
| `brief-verifier.md` | `verifier` | Read-only review. Entire report in its FINAL MESSAGE, greppable. |
| `brief-persist.md` | `worker` | Stores a verifier's report into `_main\REVIEWS.md`. |

Paste only the text between the `<!-- PROMPT:BEGIN -->` / `<!-- PROMPT:END -->` markers.
All three were measured ALLOW as a PROMPT block **and** as a whole-file paste.

## THE RULE, LOCATED (not guessed)

Source: `C:\Users\Administrador\.minimax\plugins\mcode-dispatch-guard\scripts\check-dispatch-role.mjs`,
wired as `PreToolUse` on matcher `task`.

A deny requires **both** arms (`check-dispatch-role.mjs:428`):

1. **Seat arm.** A read-only seat, taken only from a structured field of `tool_input`.
   Candidates in order: `agent_name`, `agentName`, `agent`, `role`, `agent_type`,
   `subagent_type`, `subagentType` (`:75`). `agent_name` is the measured field — 22/22 real
   dispatches used it, and all six alternatives scored 0/22 (`:58-74`). Read-only values:
   `scout, explore, explorer, verifier, verify, review, reviewer, auditor, readonly,
   read-only, observe, observer` (`:41-54`).
2. **Write-order arm.** An un-exempted match of
   `/\b(write|create|produce|generate|author|implement|save|edit|patch|fill in|complete)\b/gi`
   (`:79-80`) over `JSON.stringify(tool_input)` (`:418`).

Four exemptions, checked in this order: backward negation within 60 chars (`:87-92`, `:292`);
proper-noun use, i.e. capitalised and not opening its clause (`:215-218`); capacity modal
`can/could/may/might/will/would/shall` immediately before (`:169`, `:221-225`); trailing
quantifier `no|none|nothing|zero|not one` within 24 chars **and only on an imperative
clause** (`:131-134`, `:299-302`). Comma is **not** a clause boundary; the boundaries are
`. ; : ! ? \n` (`:127`).

A seat merely mentioned in prose does not trigger anything (`:28-34`). Nothing in prose is
a seat. Only the seat field counts.

## MEASURED EVIDENCE

Plugin self-test: 12/12 arms PASS, `SELFTEST_VERDICT=PASS`.
Own probe: 42 payloads through the live hook, 40 emitted a verdict, 30 ALLOW / 10 DENY.
All six read-only spellings ALLOW `brief-verifier.md`; `brief-worker.md` DENIES at seat
`verifier`, proving the seat arm and not the wording is what flips.

## TRAP LIST

One per line: the offending text, then the exact substitution.

1. `You create no files, you edit nothing, you commit nothing.` → `Produce no artifacts on disk.` — DENY `create`/declarative-statement; the subject `You` makes the clause declarative, so the trailing `no` is never read as a negation.
2. `You write NO files.` → `Write no files.` — DENY `write`/declarative-statement; same cause, and this is the one the hook's own message quotes.
3. `Produce nothing. Then create the census.` → `Produce nothing. The census is out of scope.` — DENY `create`/order; a trailing quantifier only negates the verb it follows.
4. `Produce absolutely nothing whatsoever on any disk.` → `Produce no artifacts on disk.` — DENY `Produce`/order; the quantifier must sit within 24 chars of the verb, and `absolutely` pushes it out.
5. `Do not, for any reason at any point, run git add or git commit or any write command of any kind.` → `Do not use any write command.` — DENY at a measured 70-char gap, ALLOW at 15; `NEGATION_REACH` is 60 and a negation further back governs a different clause.
6. `Edit the file.` → change `agent_name` to `worker` — DENY `Edit`/order; this is a genuine order and no wording saves it.
7. `Save the report.` → `Report the report contents in your final message.` — DENY `Save`/order.
8. `Complete the census.` → `Report the census count in your final message.` — DENY `Complete`/order; `complete` is in the verb list and reads as harmless in English.
9. A `worker` body dispatched under `agent_name="verifier"` → fix the seat field, not the sentence — DENY `Write`/order; measured on this kit's own `brief-worker.md`.
10. Relying on a capital to exempt a hit → rewrite the sentence — `C Edit Contract` ALLOWs but `Edit the file.` DENYs, because a sentence-initial capital is not a proper noun.
11. `Fix the module, append a line, insert a row, delete the scratch file.` → dispatch it under `agent_name="worker"` — ALLOWED, but that is a HOLE not a pass: `fix/append/insert/delete/push/update` are outside `WRITE_VERB`. Measured ALLOW.
12. Naming the read-only seat in prose to look safe → put the seat in `agent_name` — `A scout must never create a file` measures ALLOW; prose confers nothing either way.
13. `you will produce the report` → do not lean on the modal — measures ALLOW via the capacity-modal exemption; a documented false negative, so a green here is not evidence the brief is lawful.
14. Commentary placed inside a pasteable body → move it here — the first draft of `brief-verifier.md` DENIED as a whole-file paste on `write`, fired by its own explanatory sentence "uses a write verb at all". Same class as the `C Edit Contract` denial at `:135-145`.

## THE REVIEWER PATTERN

The conflict is real and it is not resolvable by rewording: `verifier` is read-only, so the
hook denies any file it is handed (`:428`), and a review that leaves no artifact does not
survive the turn. So the review is split across two lawful dispatches.

1. **`brief-verifier.md`** — seat `verifier`, read-only. Its only output channel is the
   FINAL MESSAGE, holding `REVIEW-BEGIN` … `REVIEW-END` with one pipe-delimited `FINDING`
   line per finding. Greppable, and it survives the hook precisely because it orders
   nothing onto disk.
2. **`brief-persist.md`** — seat `worker`, write-capable. Appends that block verbatim to
   `_main\REVIEWS.md`, stages it by explicit path, commits within 60 seconds.

Dispatch 2 immediately after 1. Until it commits, the review exists only in the task result
and is lost with the session — which is the exact failure the two-dispatch pattern removes.

BRIEF KIT: READY (14 traps, 3 templates)