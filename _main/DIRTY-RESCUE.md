# DIRTY-RESCUE

Lane `lane/dirtyrescue`. Population of the rescue: **9 dirty paths** in
`H:\sotto-wt\ArbV8`, re-measured at session open with
`git status --porcelain` (2026-10-07, 21:07 UTC window). Every row below was
read from disk; nothing was inferred from a filename.

Preservation rule for this lane: **nothing is deleted and nothing is staged into
main.** `git add -A` was never used. `H:\sotto` was never touched.

## Inventory

| path | bytes | what it is | verdict |
|---|---|---|---|
| `_main/CRON-VERDICT.md` | 8011 | Tracked verdict doc, **+81/-1 additive** §7-§12 measured 2026-10-07 17:29. Four-pass cron investigation with hourly control table and its own retractions | **KEEP → commit to main.** The diff is good; see below |
| `FRICTION-LEDGER.md` | 3408 | **Wrong-path fork** at repo root. Holds a 5-entry friction section (`2026-10-07 — cron_restore · 4 passagens`) in the ledger's own prose format | **ARCHIVE + MERGE.** Unique content; copy preserved at `_tools/FRICTION-LEDGER.fork.md` |
| `_main/cron-restore-probe.py` | 2435 | PASS 1, real read-only probe of `runtime-state.sqlite`, `mode=ro`, POPULATION/WINDOW printed | **KEEP** → `_tools/` |
| `_main/cron-restore-refute.py` | 4421 | PASS 2, built specifically to **refute PASS 1** (boundary clipping its own row) | **KEEP** → `_tools/` |
| `_main/cron-silence-control.py` | 4691 | PASS 3, the **positive control** that separates "cron stopped" from "machine stopped" | **KEEP** → `_tools/` |
| `_main/cron-store-loose-ends.py` | 3574 | PASS 4, closes 3 open ends (second store, chars-vs-bytes, process lifetimes) | **KEEP** → `_tools/` |
| `_main/pos.bat` | 239 | 3-line hardcoded liveness probe; writes `pos_in.txt`, pipes to `mcode.cmd exec` | **ARCHIVE** → `_archive/`. Throwaway launcher, zero diagnostic content |
| `_main/spawn2.bat` | 592 | 4-line hardcoded dispatcher carrying the verbatim brief that started PASS 2 | **ARCHIVE** → `_archive/`. Documents the dispatch, not the finding |
| `control/` (`optchat/view.txt`) | 516 | **Machine-generated** OptChat continuity view, header says `Do not hand-edit: the next run overwrites this file` | **DISCARD.** Regenerable by `compact-view.mjs`; committing it is noise |

The four `.py` files are not scratch. They are a coherent **4-pass methodology**
where pass 2 exists to kill pass 1 and pass 3 is the control pass. That is the
single most reusable artifact in this batch.

## The `FRICTION-LEDGER.md` fork — are entries being lost?

**Yes. Five entries exist nowhere else.**

- Real ledger: `I:\!manager\state\friction\FRICTION-LEDGER.md`, 546763 B,
  3972 lines, sha256 `6130EF39…`, mtime 2026-10-07 18:05.
- Repo-root fork: 3408 B, 54 lines, sha256 `4B3D8930…`. **0.6% of the real file.**

Dedup was run three ways. `Select-String` returned false zeros on this file
(lines up to 6047 chars) and was **discarded as an instrument**; ripgrep agreed,
and the verdict was taken from a whole-file `.IndexOf()` over all 545814 chars,
which cannot truncate.

| needle | in real ledger? |
|---|---|
| `cron_restore` | ABSENT |
| `CRON-VERDICT.md aditivo` | ABSENT |
| `13:11:00` | ABSENT |
| `boundary numa tabela temporal` | ABSENT |
| `store viva não é store a ler` | ABSENT |
| `controle positivo` | ABSENT |
| `prova sem controlo` | ABSENT |
| `memória derivada` | ABSENT |
| `sched-7f2c94e` | ABSENT |
| `22 ms` / `falso verde` / `length(CAST` | ABSENT |
| `8612` / `8553` / `1442` | **FOUND** — numbers only, see below |

The three hits are **numeric coincidences, not coverage**: `8612 B` is F7832
describing `scripts/cron-mission-prompt.md`, `8553 chars` is F7833 describing the
store row, and `1442` is an unrelated determinism audit that happened to count
the same run rows. None states the lesson.

The real ledger's own **last entry** already records this incident — it names
`?? FRICTION-LEDGER.md` at the repo root and cites F8456 as the same prior
mistake, and sets the rule *always write to the absolute destination path*. So
the **mistake** is filed. The **content** the lane wrote to the wrong path never
reached the ledger.

### Unique entries, preserved in full

P1 — **boundary on a temporal table set at the value you are trying to refute.**
`COUNT(*) WHERE created_at_ms > 13:11:00.000Z` returned `1`; the true last row is
`13:11:00.022Z`, 22 ms past the boundary, so the query counted the row it was
supposed to exclude. Lesson: anchor on the measured `MAX()` and ask `> MAX()`; a
`1` where you expected `0` is the exact shape of a false green.

P2 — **a proof with no control.** P2 confirmed `MAX` unchanged and 0 rows after
it, but that is trivially compatible with *the process was dead the whole time*.
Lesson: every negative claim about a live system needs a **positive control in
the same window** — hourly `cron_runs` beside `message_rows`/`sessions`. The
busiest hour (3077 messages) with **zero** crons is what closes the question.

P3 — **"a freshly started process" tested once.** One boot cannot separate
"hydration does not happen" from "this instance is the wrong one". Lesson:
measure **how many times the hypothesis was tested** — here 18 distinct hours with
a new session and 0 executions, plus `sched-7f2c94e`, a job **born that day**,
armed for +1 min, `OVERDUE 5.4 h`. A recent job cannot have "slept since Tuesday".

P4 — **a number cited from a column that does not exist.** §2 claimed
`prompt_bytes=8553` "from the database" against an 8612-byte file, presented as a
content divergence. `cron_definitions` has **no** `prompt_bytes`; the value came
from `length(prompt)` which counts **characters**, while 8612 is the file in
**bytes**. The "59 bytes" were UTF-8 encoding. Lesson: before calling two numbers
a "divergence", ask **what each one counts** — `length()` is chars,
`length(CAST(x AS BLOB))` is bytes. Two columns, one fact.

P5 — **a live store is not a store you read.** The briefing asserted *"there is no
cron store in `.minimax\v2`"*, which the root had written into memory two days
earlier from a grep, without opening the file. `sqlite/runtime-state.sqlite`
exists, **3.36 GB**, 1442 executions, 30 jobs. The memory was false and it was
**driving action** (restarting the runtime). Lesson: **a derived memory is not a
measurement — open the file.**

## The `CRON-VERDICT.md` diff — is the change good?

**Yes, and it is the strongest thing in this batch.** `+81/-1`, purely additive:
the one deletion is the trailing no-newline marker. It adds §7-§12 answering
*does a freshly restarted process restore cron delivery?* with **NÃO** — measured
over 4 passes, with the hourly control table, the clean `sched-7f2c94e7c5eb`
case (created 15:06:11Z, `*/3 * * * *`, `run_count=0`, `OVERDUE 5.4 h`), and a
retraction table (§10) that **withdraws four of its own earlier claims** from the
17:17 version, including its own §6 recommendation to restart.

Two things keep it honest and worth committing:

- §11 states the **mechanism is still a hypothesis**, not a measurement.
- §11 states **nothing was written**; every connection was `file:…?mode=ro`.

## Recommendation to the owner

**Commit to main:** `_main/CRON-VERDICT.md` only. The diff is additive,
self-retracting, and the conclusion is what the four probes measured.

**Archive to `_archive`:** `pos.bat`, `spawn2.bat` — hardcoded launchers, kept
because archiving beats deleting. Preserved at `_tools/` here.

**Merge, do not commit:** the 5 fork entries above belong appended to
`I:\!manager\state\friction\FRICTION-LEDGER.md` at the **absolute** path. The
repo-root copy should then go. Until that merge happens the content is orphaned:
a lane reading the canonical ledger sees F8456 complaining about the stray file
but not the five lessons it was written to hold.

**Discard:** `control/` — generated, self-overwriting by design.

**Keep as tools:** the four `.py` probes in `_tools/`. They are read-only,
`mode=ro`, and print POPULATION/WINDOW on every count. They are the reusable
instrument for the next cron question, and pass 2 is a reusable *pattern* — a
lane that should doubt its own pass 1 has a ready-made refuter.

`DIRTY RESCUE: 7 preserved / 2 archived / 1 at risk`