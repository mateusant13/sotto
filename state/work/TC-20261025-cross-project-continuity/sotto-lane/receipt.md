# Receipt — lane `sotto-lane-task-resolver-continuation`

Task `TC-20261025-cross-project-continuity` · lane `sotto-lane-task-resolver-continuation` · role `worker`
· route: owner-authorized OpenCode Go 1 (DeepSeek V4.1 Flash) · date 2026-10-25 · **no commit, no push**.
> **SUPERSEDED 2026-10-25 — the route this lane actually ran on was OpenCode Go 3
> (`opencode-go-3/deepseek-v4.1-flash`); Go 1 and Go 2 failed on an expired API key. Evidence, commands and
> the limits of that evidence: §11. The sentence above is kept, not rewritten: it is what was dispatched.**
>
> **Measured 2026-10-26** — `providerID=opencode-go-3`, `session=ses_e8d811684ffe1TrRQxUW83QVPI`: the one
> session window `06:58:02 -> 07:08:15` that contains this file's creation instant `07:07:32`. The other
> two candidate sessions had already closed (`2.4 s` at `06:57:30`, `0.9 s` at `06:57:57`). Instrument
> `opencode.db` / `session_v2.model`, read-only; gate `_main/receipt-provenance-oracle.py`; §11(d).

State claimed: **spawned -> returned**. Nothing here is `verified` in the sense of an independent
verifier: `FIXED, NOT VERIFIED` is the honest label for the product-facing part, and the rows that could
not be exercised say so.

---

## 1. Inputs loaded (skill delivery, by content not by claim)

| artifact | bytes | sha256 | matches declaration |
|---|---|---|---|
| `I:\!manager\skills\task-resolver\SKILL.md` v1.3.0 | 12731 | `9220565f6e6111922fcdd6724cc7a7f3dc0c212957556f4de6b24f206dac022f` | **yes** — the digest the brief gave |
| `I:\!manager\skills\subagent-worklist\SKILL.md` v1.1.4 | 22181 | `42f46db6dc138059ba8dd766906a8ea40c7f2bbb7086c574db1421e4f14f8203` | **yes** |
| `I:\!manager\state\work\TC-20261025-cross-project-continuity\owner-request.md` | 1394 | `44480fb7307c30f730c1f857bd548df00f532c6b640283bd8ed855e477638328` | **yes** — `review_inputs` |
| `.agents/skills/task-resolver/SKILL.md` (repo copy) | 12731 | `9220565f…` | **identical to the canonical** — the repo copy is not a fork |
| `state/…/sotto-lane/todo.md` (r0) | 6476 | `cbe8fb2db3b55b683d592092ed0457d4a6da928dce422e34c8c6a4c720622f88` | **yes** — matches `dispatch-snapshot.json` `todo` and `todo_r0`; first bytes `23 20 4c 61 …` = `# Lane TODO — sotto-lane-…` |

Both required skills were read in full (the task-resolver body 1–54 and the worklist body 1–296) before
any edit. `source-manifest.json`, declared in the TODO `read_paths`, **does not exist** on disk: recorded
under `C-04` instead of being assumed.

`python I:\!manager\tools\worklist-replay.py --validate-header --todo <todo> --repo-root H:\sotto` ->
`VERDICT: PASS code=PASS mode=header paths=9`, **rc=0**.

## 2. Acceptance classification (the dispatch's first mechanical step)

| # | row | class | executable gate | negative control |
|---|---|---|---|---|
| A1 | chosen acceptance rows classified | **JUDGMENT** | this table, read against §2 of the task-resolver | falsifier: any row below with no gate or no falsifier |
| A2 | a project-native deterministic gate exists and is wired into the real invoker | **MECHANICAL** | `scripts/task-resolver-gate.py` check `battery-wired` | mutation `unwire-battery` -> `NEG-ARM PASS` on `battery-wired` |
| A3 | the gate passes on the real repo | **MECHANICAL** | `python scripts\task-resolver-gate.py` rc=0 | — |
| A4 | the negative control is attributable to the intended assertion | **MECHANICAL** | `--mutation <name>` must refuse **the named check**, not "some check" | 6 named arms, §5 |
| A5 | a real accepted-work slice from the existing roadmap is delivered | **MECHANICAL** | `python _main\claims-date-oracle.py` rc=0 + `--neg-arm` 6 named arms | 6 mutations, §5 |
| A6 | unrelated edits preserved | **MECHANICAL** | `git status --porcelain` before/after set difference | zero removals; +5 paths, all mine (§7) |

`docs/roadmap.md` was read first. It is the **2026-10-05 plan** whose milestones M0..M6 are explicitly
superseded in stack terms; the accepted work in flight lives in `docs/roadmap-observability.md`
(P0..P3, 2026-10-23). **Chosen item: P0.3** — "uma afirmação numérica no `AGENTS.md` sem data/medição ao
lado é vermelha; baseline ratchet".

Why P0.3 and not P0.1 (which is listed first): P0.1 (`sotto facts` + `facts.json`) needs `--verify` to
re-run instruments, and several of those instruments load the models — heavy class, and the central
performance gate is **AMBER with `heavy_allowed=False`** (§6). P0.2 needs the oracles' outputs to exist.
P0.3 is the only P0 item with no dependency and no heavy process, so it is the highest-priority item a
lane can honestly close today. This is a stated deviation from strict list order, with its reason, not a
silent re-prioritisation.

## 3. Changed paths (exact)

| path | kind | bytes | sha256 (final) |
|---|---|---|---|
| `AGENTS.md` | modified (4 targeted replacements) | 20439 | `c3f65324e1904d419254161e4578762fcbcfe66949a1c3f20be12ace7e0ff048` |
| `_main/_audit-verify-all.cmd` | modified (one insertion, +31 lines) | 114291 | `56d357c83a999792e1c33b0411bf233ce564f4104c0a89a334e3e95142ff0322` |
| `_main/claims-date-oracle.py` | new | 18206 | `684256c80119e0095617ab9be923c8757d9a146221a5e08ef69a0049768683a7` |
| `_main/claims-date-baseline.json` | new | 2600 | `5d4c47f3d00f6a96c7b554ed61d2566681c1d73c6bd264d7c7a3d3507a130636` |
| `scripts/task-resolver-gate.py` | new | 16461 | `d092474a7aa81185cdc2dfa35f053be5094baca3edbbd6067e05577331335ac8` |
| `scripts/test_task_resolver_gate.py` | new | 3695 | `104c23ddd7ae428b121e7beb7f39f118ef798a4f83c4227fcef756bdde67f5e1` |
| `docs/roadmap.md` | modified (appended status section) | 7316 | `bf39c4d0abc460829abfa7912f5d02134c1b2ab36b47bba169f91f67df0d1c1d` |
| `docs/roadmap-observability.md` | modified (P0.3 delivery status appended) | 6157 | `9fd76d66304dace512a82444336bb7fd8bcc23580aaf931ce6c27f2ca314fa4a` |

Plus this lane directory: `todo.md` (appended), `receipt.md` (this file).

`AGENTS.md` edits, each an exact-match replacement:

1. `Protocolo completo (11 passos,` -> `(11 passos, contados em 2026-10-25 no docs/bug-hunt.md,`
2. `protocolo de **11 passos** (`docs/bug-hunt.md`)` -> `… (docs/bug-hunt.md, contados em 2026-10-25)`
3. `119 linhas de medicoes…` -> `120 linhas nao vazias de medicoes … (o ficheiro tem 123 linhas)`
4. the battery pin row: `111454 B / 1499 CRLF / 204A93EE…` -> `114291 B / 1530 CRLF / 56D357C8…`, with the
   previous pin kept in the `Era …` history exactly as the row already does.

## 4. Commands and exit codes (all run from `H:\sotto`)

| # | command | rc | verdict |
|---|---|---|---|
| 1 | `python scripts\task-resolver-gate.py` (**pre-wiring**) | **1** | 5 PASS, `battery-wired` **FAIL** — the pre-fix regression, at the intended assertion |
| 2 | `python scripts\test_task_resolver_gate.py` (**pre-wiring**) | **1** | 4 tests, **7 failures** (positive + 6 `COPY-BROKEN`) — RED as predicted |
| 3 | `python _main\claims-date-oracle.py --write-baseline` | 0 | wrote 7 entries, ceiling 7 |
| 4 | `python _main\claims-date-oracle.py` (after the generator, before provenance) | **1** | `baseline-schema` FAIL: entries missing `date`/`instrument` — the generator alone is not provenance |
| 5 | `python _main\claims-date-oracle.py` (after cures + hand-filled baseline) | 0 | `BATTERY-VERDICT claims-date PASS checks=4 fail=0` |
| 6 | `python _main\claims-date-oracle.py --neg-arm` | **1 by design** | `NEG-ARM PASS mutations=6 named-arm-fail=0` |
| 7 | `python scripts\task-resolver-gate.py` (**post-wiring**) | 0 | `BATTERY-VERDICT task-resolver-gate PASS checks=6 fail=0` |
| 8 | `python scripts\task-resolver-gate.py --neg-arm` | **1 by design** | `NEG-ARM PASS mutations=6 named-arm-fail=0` |
| 9 | `python _main\agents-md-pins-oracle.py` (after the `.cmd` edit, before the AGENTS.md cure) | **1** | `AGENTS-PINS FAIL` — `114291 B false`, `1530 CRLF false`: a **pre-existing project gate** went EXPECTED-RED on my edit |
| 10 | `python _main\agents-md-pins-oracle.py` (after the pin cure) | 0 | `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` |
| 11 | `python scripts\test_task_resolver_gate.py` (post-wiring) | 0 | `Ran 4 tests … OK` |
| 12 | `python _main\tooling-intent-oracle.py` | 0 | `declaradas: 10 \| baseline 160 \| vermelhas: 0`, ratchet not grown |
| 13 | `python _main\battery-heavy-gate.py` | 0 | PASS, 6 heavy steps still declared, none of them mine |
| 14 | `python _main\code-health-oracle.py` | **2** | **FAIL, PRE-EXISTING** — see §6, not attributable to this lane |
| 15 | `cmd /c python scripts\task-resolver-gate.py` | 0 | same verdict under the battery's own shell |
| 16 | `cmd /c python scripts\task-resolver-gate.py --neg-arm` | **1** | log carries `NEG-ARM PASS mutations=6` — exactly what `:expectred … 1 … "NEG-ARM PASS"` needs |
| 17 | `cmd /c python _main\claims-date-oracle.py` | 0 | same verdict under `cmd.exe` |
| 18 | `cmd /c python _main\claims-date-oracle.py --neg-arm` | **1** | log carries `NEG-ARM PASS mutations=6` |
| 19 | `python _main\_stepcache.py check --step claims-date --expect-rc 0 --deps "…" --log …` | 1 | `MISS reason=no-entry` — the step name and the dep list parse in the battery's own cache |
| 20 | `python _main\_stepcache.py check --step task-resolver-gate …` | 1 | `MISS reason=no-entry` — same |
| 21 | `python I:\!manager\tools\performance-gate.py status` | **4** | `AMBER … heavy_allowed=False … disk-amber` -> the full battery is **NOT RUN** (§6) |
| 22 | `git status --porcelain=v1` before / after | 0 | 708 -> 713 paths, **+5, -0** (§7) |

The full transcript of the last sweep is at `I:\cc-tmp\sotto-lane-final.log` (scratch, outside the repo).

## 5. The two gates, and what their negative arms actually prove

**`scripts/task-resolver-gate.py`** (6 checks: `agents-mandate`, `skill-version`, `skill-digest`,
`gate-bootstrap-law`, `evidence-vocabulary`, `battery-wired`). Its six mutations and the check each one
**must** refuse:

| mutation | must refuse |
|---|---|
| `drop-agents-mandate` | `agents-mandate` |
| `drop-skill-version` | `skill-version` |
| `fork-skill` (appends one line) | `skill-digest` |
| `drop-gate-bootstrap` | `gate-bootstrap-law` |
| `drop-no-verdict` | `evidence-vocabulary` |
| `unwire-battery` | `battery-wired` |

6/6 `NEG-ARM PASS`. This is stricter than the sibling `check-bug-hunt-wiring.py`, which accepts a
refusal by *any* check: here a mutation that goes red for the wrong reason is `NEG-ARM FAIL`.

**`_main/claims-date-oracle.py`** (4 checks: `new-undated-claim`, `baseline-schema`,
`baseline-ceiling`, `baseline-orphans`) with six mutations: `append-undated-claim`,
`drop-entry-date`, `drop-entry-instrument`, `grow-baseline`, `orphan-entry`, `drop-baseline`.
6/6 `NEG-ARM PASS`, each on its named check. `drop-baseline` is the fail-safe arm: a missing baseline
must be **red**, never a no-verdict, and it is red through `new-undated-claim`.

The gate found a real defect on its first run, which is the strongest thing that can be said about it:
`AGENTS.md` claimed **119** lines of measured facts; `docs/factos-medidos.md` has **120** non-empty
lines (123 raw). The number was stale, and it is now corrected and dated. Two further claims
(`11 passos` ×2) were verified by counting `docs/bug-hunt.md`'s numbered steps — **11**, so they were
true and are now dated. Baseline **7 -> 4** in one pass: the ratchet moved in the only direction it is
allowed to.

## 6. What is NOT verified (read this before quoting anything above)

- **The full battery did not run.** `performance-gate.py status` -> **AMBER, `heavy_allowed=False`**
  (disk latency 85.5 ms sustained), and AGENTS.md puts "uma bateria completa" in the heavy class. So
  `battery-wired` proves the **bytes** of the step lines and the argv was exercised under `cmd.exe`; it
  does **not** prove a green `steps=` line from a real run. Row `A2` is `PASS` for wiring-as-bytes and
  `NOT RUN` for battery-green.
- **`code-health` is RED in this tree and it is not mine.** `app/webview/sotto_webview.py` (+9249 B),
  `app/webview/youtube_window.py` (untracked, 5872 -> 7347 B), `worker/sotto_worker.py`
  (+1142 B, `except_pass` 13 -> 14) all sit in the uncommitted working tree **before** this lane
  (`git status` before-snapshot holds all three). This lane wrote no file in `app/` or `worker/`. The
  consequence still stands and is not softened: **this tree's battery cannot be called green**, by me or
  by anyone, until those edits are reconciled by their author.
- **The `3,90 GB` ternary-arm claim was not re-measured.** Re-measuring means loading the ternary model
  — heavy class, refused by the same AMBER gate. Its baseline entry says so in its own `reason`.
- **Preservation of pre-existing hunks in `AGENTS.md` is `UNKNOWN`, not proven.** `AGENTS.md` was already
  ` M` at lane start and `source-manifest.json` (which would have carried a byte-level before-image) does
  not exist, so there is no snapshot to diff against. What *is* measured: each of my four edits was an
  exact-unique-match replacement (so it cannot have rewritten bytes outside its span), and the three
  gates that read `AGENTS.md` (`agents-md-pins`, `claims-date`, `task-resolver-gate`) are green. For
  `_main/_audit-verify-all.cmd` the equivalent claim **is** proved byte-exactly: the inserted block is 31
  lines / 2837 B / 31 CRLF and the file grew by exactly 2837 B (111454 -> 114291), so nothing else moved.
- **`scripts/` vs `_main/`.** Every other oracle in this repo lives in `_main/`; `scripts/` was the path
  the dispatch declared, and `scripts/check-bug-hunt-wiring.py` is precedent. Recorded as a deliberate
  obedience to the brief, not a convention (see `falta-no-gate` in the SELF-AUDIT).

## 7. Unrelated-edit preservation (A6)

`git status --porcelain=v1`: **708** paths at lane start, **713** at the end. `Compare-Object`:
**5 added, 0 removed.**

```
 M docs/roadmap.md                       <- mine
?? _main/claims-date-baseline.json       <- mine
?? _main/claims-date-oracle.py           <- mine
?? scripts/task-resolver-gate.py         <- mine
?? scripts/test_task_resolver_gate.py    <- mine
```

`AGENTS.md`, `_main/_audit-verify-all.cmd` (` M`) and `docs/roadmap-observability.md` (`??`) were already
dirty/untracked before this lane, so their status code could not change; §6 states exactly what that
does and does not prove.

## 8. Evidence per worklist item

### C-01
Mission field confirmed: `mission:` on the r0 line 5 is "Use Task Resolver v1.3 in sotto-lane and
continue the project's existing accepted work with an immediately wired, falsifiable mechanical gate";
every action below serves it.

### C-02
Task read from its own artifacts: `todo.md` r0 (6476 B, `cbe8fb2d…`), `dispatch-snapshot.json`
(`row_count: 24`, `required_ids`), `owner-request.md` (1394 B, `44480fb7…`). No brief was paraphrased
from memory.

### C-03
Readiness basis recorded at the top of `todo.md` (`role`, `target_access`, `output_write`, `route`,
`budget`) and in §2: the route is the owner-authorized Go 1 DeepSeek V4.1 Flash, `budget` is a
process/silence ceiling only, and no tool-call or agent-count limit was applied.

**Correction — see §11.** The route named in the sentence above is the route as *dispatched*, not the
route that ran. The process that produced this lane used **`opencode-go-3/deepseek-v4.1-flash`**, after
Go 1 and Go 2 failed on `AI.Error: This API key has expired`. The authorisation covers it — header line 9
reads "if no live response, try Go 2 through Go 6 in order" — so the route was lawful and the *sentence*
was wrong, which is the only thing corrected here.

### C-04
Every declared `read_paths` entry was tested for existence. **`source-manifest.json` is absent**
recorded here as an input gap, with the live substitute: the dirty set is re-derived from `git status`
today (§7) rather than quoted from a file that does not exist.

### C-05
Skill + TODO delivery: §1 gives path, version, byte count and sha256 for both required skills, matched
against the digests the brief declared; the TODO r0 digest matches `dispatch-snapshot.json`. This is a
traceability record of the bytes I read, not a claim that a harness injected them.

### C-06
Deliverables written at the exact declared paths: `AGENTS.md`, `scripts/task-resolver-gate.py`,
`scripts/test_task_resolver_gate.py`, `docs/roadmap.md`, `state/…/sotto-lane/receipt.md` — §3.

### C-07
Write-path discipline: 8 paths touched, all inside `owned_paths` (`H:\sotto`, the lane directory), none
in `.git`, none in `app/`, `worker/`, or any file that was another writer's. No commit, no push.

### C-08
Acceptance executed: §4 rows 5, 7, 11, 12, 13, 15, 17, 22 — each with its rc, not its prose.

### C-09
Falsifier attempted, twice, and it bit once:

- the dispatch falsifier — "any mechanical row proceeds without an executable gate and a falsifiable
  negative control" — would have been satisfied by writing the gate and *not* wiring it; `battery-wired`
  was RED for exactly that reason before the battery edit (row 1);
- and the refutation pass caught **my own first cure**: I first wrote `120 linhas de medicoes` into
  `AGENTS.md`, then measured `123` raw lines and had to refine the sentence to "120 nao vazias … o
  ficheiro tem 123 linhas". The claim was refuted by its own instrument before it shipped.

### C-10
`conditional: true`, and the controls were run anyway: §5's 12 named arms across two gates. No row is
retired by condition.

### C-11
Lane state reconciled: the worklist statuses here match §8's evidence item by item, and the change log in
`todo.md` carries one append-only row per status change.

### C-12
Change log appended in `todo.md`; `changes: []` was replaced by one row per item change, monotonic
`r1..rN`, no wall-clock timestamps.

### C-13
Done/blocked discipline: nothing is called `done` without a receipt; the things that did not run are in
§6 as `NOT RUN` / `UNKNOWN`. No `attempted`, no `in-progress`.

### C-14
Closure checked against the dispatch snapshot: `required_ids` (C-01..C-15, W-01..W-04, T-01..T-05) all
present in the final TODO, row count 24 = 15 + 4 + 5, ids unique; the strict replay result is quoted in
§9.

### C-15
This receipt, ending in `## SELF-AUDIT`.

### W-01
Smallest change that satisfies acceptance: one new gate, one new oracle, one test, four battery steps,
four targeted `AGENTS.md` replacements, two documentation status lines. No refactor rode along.

### W-02
Checks written per project rule: `scripts/test_task_resolver_gate.py` (4 tests) and the `--neg-arm`
mutation harness inside each oracle — the repo's own shape (`--neg-arm` + `red-as-expected-*`), not a new
harness.

### W-03
Mutation/revert path exercised: §5 — 12 mutations, each on a **copy** under `TMPDIR`
(`I:\cc-tmp`), each asserting the *named* check refused, plus the `COPY-BROKEN` guard (an intact copy
that already fails cannot count as a detector). No mutation touched the real tree.

### W-04
No second source of truth: the repo's copy of the task-resolver skill is pinned to the canonical bytes
(`skill-digest`), so a fork is red; `claims-date-baseline.json` is a hash-keyed licence list with a
code-pinned ceiling, an orphan check and a required `instrument` per entry — it cannot become an
amnesty, and a changed `AGENTS.md` line orphans its entry and forces reconciliation. `docs/roadmap.md`
now points at `docs/roadmap-observability.md` instead of restating it: no second backlog.

### T-01
`AGENTS.md` and `docs/roadmap.md` read first; the live accepted backlog is `docs/roadmap-observability.md`;
item **P0.3** chosen, with the reason §2 gives for skipping P0.1.

### T-02
Classification in §2 (4 mechanical, 1 judgment); the missing gate was built and wired **before** the
dependent work (the `.cmd` — the only writable copy of the real invoker) and before the roadmap/doc
edits, which are the dependent product-adjacent edits.

### T-03
Positive and targeted negative controls run, with intended verdicts recorded: §4 rows 1, 5, 6, 7, 8, 9,
10, 11, 15-18; §5's tables.

### T-04
One highest-priority safe slice implemented and exercised through its real entry point: P0.3 ->
`_main/claims-date-oracle.py` green under `cmd.exe`, its `--neg-arm` red by design, its two battery steps
present, and the `_stepcache` contract accepting the step+deps.

### T-05
This receipt + the editable `todo.md` returned with the change log and the SELF-AUDIT below.

## 9. Closure mechanism

- Header mode: `worklist-replay.py --validate-header` -> `PASS paths=9`, rc=0.
- Closure mode: `worklist-replay.py --r0 todo.r0.md --final todo.md --require-receipt-digests
  --repo-root H:\sotto` -> quoted verbatim in the hand-back message; **replay PASS is a statement about
  the worklist and its receipt bindings, never about whether the code works**.
- Which mode produced this evidence: **strict** (`--require-receipt-digests`), receipt digest computed
  from the final bytes of this file and written into the `done` rows afterwards.

## 10. Next action (owner or next lane)

1. **Reconcile the uncommitted product edits** (`app/webview/sotto_webview.py`,
   `app/webview/youtube_window.py`, `worker/sotto_worker.py`) so `code-health` can go green; until then
   no battery run can be green and nobody should quote one.
2. **Run the full battery when the fleet gate clears AMBER** (`performance-gate.py status` ->
   `heavy_allowed=True`) and confirm `steps=` carries `task-resolver-gate`, `red-as-expected-task-resolver-gate`,
   `claims-date`, `red-as-expected-claims-date` with the expected verdicts.
3. Continue P0 with **P0.2** (`_main/sotto-state-page.py`) or **P0.1** once a heavy window exists;
   P1.1..P1.5 remain serial and product-file work, P2.1/P2.2 remain blocked on the owner.

## 11. Provenance correction — the route actually used was OpenCode Go 3

**The claim this corrects.** Line 4 of this receipt said the lane ran on `OpenCode Go 1 (DeepSeek V4.1
Flash)`, and §C-03 repeated it as "the route is the owner-authorized Go 1 DeepSeek V4.1 Flash". That was
false about the route that actually ran. Nothing is deleted: line 4 now carries a `SUPERSEDED` marker
pointing here, and this section is the record of what replaced it.

**The corrected claim.** The work in this receipt was produced by an `opencode run` process whose model
was **`opencode-go-3/deepseek-v4.1-flash`** — OpenCode **Go 3**, DeepSeek V4.1 Flash. Go 1 and Go 2 were
launched first and died on `AI.Error: This API key has expired`.

### Evidence (a) — the manager's process observation, which this lane cannot re-measure

The dispatch for this correction states, verbatim: *manager-observed process-info for PID 29004 shows the
command `opencode run` with model `opencode-go-3/deepseek-v4.1-flash`*. Measured now, in this pane:

```
> Get-CimInstance Win32_Process -Filter "ProcessId=29004"
PID=29004 NOT RUNNING
```

PID 29004 has exited, so **its own `CommandLine` is not re-measurable by this lane**. That observation is
therefore labelled `REPORTED` here, never `MEASURED`. Everything below is what this lane *can* measure,
and it is enough to name the route without trusting the report.

### Evidence (b) — the launcher's own log names the route, independently of the manager

`C:\Users\Administrador\.local\share\opencode\log\opencode.log` — read once, **34 293 281 B**, sha256
`db4a3c87815da5cbfc9682c5444242807ca8895c8d70b3f04aaa141b25ed5175` (the file grows while panes run; the
digest pins the read). Timestamps are the log's own, **UTC**; local time is UTC+3. Filtering that log on
this lane's own title gives four launches, in order — the whole fallback chain, in the artifact:

| UTC | run | `--model` | title | reading |
|---|---|---|---|---|
| `09:57:24.558Z` | `7a2f293f` | `opencode-go-1/deepseek-v4.1-flash` | `Sotto backlog continuation` | Go 1, aborted **4 ms** later at `09:57:24.562Z`: `cli process failed … CliError/ShowHelp: Help requested` — a malformed argv, zero work done |
| `09:57:30.034Z` | `82b502f5` | `opencode-go-1/deepseek-v4.1-flash` | `Sotto backlog continuation` | Go 1, the real attempt |
| `09:57:57.082Z` | `db71ed08` | `opencode-go-2/deepseek-v4.1-flash` | `Sotto backlog continuation Go2` | Go 2 |
| `09:58:02.348Z` | `f1244cdf` | **`opencode-go-3/deepseek-v4.1-flash`** | `Sotto backlog continuation Go3` | **the launch that survived** |

The receipt at this path was written at `10:07:32Z` — five minutes into the Go 3 launch, and after no
other. Corroborating the failure half of the report, the same log carries **seven** `level=ERROR …
cause="AI.Error: This API key has expired. Create a new API key in OpenCode Console …"` events inside the
window those launches open: `09:56:54.960Z`, `09:57:32.823Z`, `09:57:33.624Z`, `09:57:38.099Z`,
`09:57:45.526Z`, `09:57:56.219Z`, `09:57:58.117Z` — i.e. after the Go 1 launch (`09:57:30`) and after the
Go 2 launch (`09:57:57`), with **none** between the Go 3 launch (`09:58:02`) and the receipt's write.

**Limit of (b), not softened.** The failing sessions carry run ids of the supervising process, not of the
launches (e.g. `04d26cc5`, `a78a09ba`, `41fa473a`), so this log is *concurrent with* the Go 1 and Go 2
attempts; it does **not** prove per-launch attribution. That the expired key belongs to the Go pool is
**inference** from the phrase "OpenCode Console", and is labelled as inference here. What (b) does prove
on its own is the one thing that matters for this correction: **the lane that wrote this receipt was
launched on Go 3, not Go 1.**

### Evidence (c) — the instrument discriminates routes (the negative control for Evidence (a))

A `CommandLine` observation is worth nothing unless the model survives in it, so the same sweep measured
four live `opencode.exe` processes at once:

```
pid 10084  (this pane)  ... run --model opencode-go-3/deepseek-v4.1-flash --title "Sotto receipt provenance closure Go3" ...
pid 5552                ... run --model opencode-go-3/deepseek-v4.1-flash --agent docs-writer ...
pid 42308               ... run --model opencode-go-3/beam-free --format json ...
pid 44700               ... run --model tokenharbor/mimo-v2.6-flash:free --agent plan ...
```

Four processes, three distinct model ids, each verbatim in `CommandLine`. So a manager-observed
`CommandLine` naming `opencode-go-3/deepseek-v4.1-flash` for PID 29004 is a *discriminating* observation:
had process-info dropped the `--model` token, Evidence (a) would be worthless. It does not drop it.

### Evidence (d) — the harness's own session record, and the falsifier it has to survive

Measured `2026-10-26`, after this correction was first written, by a second instrument that shares no
code path with the launcher log and does not depend on the manager's observation:
`C:\Users\Administrador\.local\share\opencode\opencode.db`, table `session_v2`, columns
`id`/`model`/`time_created`/`time_updated` — **read-only, metadata only**, no message content read.

The join is *containment of an instant*, not a guess at a launch:

| fact | value | how it is measured |
|---|---|---|
| this receipt's creation instant | `2026-10-25 07:07:32` local (`10:07:32Z`) | `Get-Item …receipt.md` → `CreationTime` |
| the session window containing it | `ses_e8d811684ffe1TrRQxUW83QVPI`, `06:58:02 -> 07:08:15` (`613.3 s`) | `session_v2.time_created <= 07:07:32 <= time_updated` |
| that session's model | `{"id":"deepseek-v4.1-flash","providerID":"opencode-go-3"}` | `session_v2.model`, verbatim |
| the Go 1 candidate | `ses_e8d8193edffeqK5CZTlnQ6e9zt`, `06:57:30 -> 06:57:32` (`2.4 s`) | closed `9 m 60 s` before the write |
| the Go 2 candidate | `ses_e8d812b16ffexbvYjxgbie3r2Q`, `06:57:57 -> 06:57:58` (`0.9 s`) | closed `9 m 34 s` before the write |

**Exactly one** Sotto session window on this machine contains `07:07:32`, and it is a Go 3 session. This is
the independent corroboration §11's table asked for and did not have: it upgrades the route claim from
*one* instrument agreeing with itself (launcher log + live `CommandLine`) to **two instruments that share
no code path** — and it also dates Go 1's death to `2.4 s`, which is what a launch that dies on an expired
key looks like.

**The falsifier, stated so this evidence can be broken rather than believed.** Containment discriminates
only because every competing window had **closed** before `07:07:32`. If a Go 1 or Go 2 session had still
been open at that instant, this same instrument would be silent and the route would stay `REPORTED`. It
also proves the *harness's* attribution, not the model server's: it says which provider the session was
configured with, never which weights answered a particular token. Both limits are the same ones §11's table
already carries for the other arms — the instrument is better, not infallible.

The falsifier was not merely reasoned about: `header-route-measured` in
`_main/receipt-provenance-oracle.py` is the machine check that this section exists precisely because it did
**not** exist, and the gate was RED on this very file before the sentence above was written (§5 of that
oracle's header records the red-first).

### What this correction does not touch

- **No measured verdict moves.** §3's path hashes, §4's 22 rcs, §5's twelve named arms, §6's
  `NOT RUN`/`UNKNOWN` list and §7's 708 -> 713 preservation count are unchanged and were **not re-run**
  for this correction. Only a provenance sentence was false; the acceptance work stands exactly as
  measured, `FIXED, NOT VERIFIED` included.
- **The route was lawful.** Header line 9 already authorises it: *"if no live response, try Go 2 through
  Go 6 in order"*. Go 3 is the declared fallback, not a deviation from the dispatch.
- **The TODO header still says Go 1, deliberately.** It is a locked header field after dispatch
  (worklist skill §6: a header change needs a new orchestrator snapshot), and rewriting it would also
  break `dispatch-snapshot.json`'s `todo`/`todo_r0` digest. The honest shape is therefore: **header = what
  was dispatched, receipt = what actually ran.** Recommendation to the orchestrator, not an action taken
  here: if the header must name the effective route, issue a new snapshot with `route_model_provider`
  restated for Go 3; this lane will not do that unilaterally.

### The cost of this correction, paid in the same pass

Appending this section changes the receipt's bytes, and every `done` row binds that exact byte string
(`@sha256:`). Per the worklist skill §6a the order is: finish the report, hash once, then bind — so the
receipt was finalised first, hashed, and **all 24 `done` rows were rebound to the new digest in one
pass**, with one `status` change-log row per rebind (`r25`..`r48`, old and new receipt ref in each row) and
`C-03`'s note refined to name the corrected route. `todo.r0.md` is untouched: `6476 B`, sha256
`cbe8fb2db3b55b683d592092ed0457d4a6da928dce422e34c8c6a4c720622f88`, re-measured after the edit and equal
to `dispatch-snapshot.json`.

The strict replay's own verdict is **not** written here: it depends on the digest of these bytes, so
stating it inside the file would change the digest that produced it. It is quoted verbatim in the
hand-back message, exactly as §9 does — that is the same reason §9 gives for not embedding it either.

### Verdict for this section

| row | verdict | why |
|---|---|---|
| route actually used = OpenCode Go 3 / DeepSeek V4.1 Flash | `PASS` | launcher log names the surviving Go 3 launch (§b); this pane's own `CommandLine` is Go 3 (§c) |
| Go 1 and Go 2 failed on an expired API key | `PASS` (concurrency) / `UNKNOWN` (per-launch attribution) | seven expired-key events bracket both launches; the log does not tie a key to a launch |
| PID 29004's own `CommandLine` | `REPORTED` | process gone at `07:12:49` local; not re-measurable by this lane |
| independent verification of any of the above | `NOT RUN` | no reviewer ran this; `PASS` here means *measured by the author*, never *independently verified* |

## SELF-AUDIT

1. claimed-state: spawned -> returned. No `verified`: no independent verifier, and the app never ran.
2. what-changed: 8 files (+2 lane files), §3 with bytes and hashes.
3. commands-run: §4, 22 rows, each with its rc; every green has its command, every red has its owner.
4. what-I-did-not-do: no commit, no push, no full battery, no heavy process, no launch of the app, no
   write in `app/` or `worker/`, no new backlog.
5. refuted-mine: my first `AGENTS.md` cure stated `120 linhas` without saying which line count; my own
   instrument (123 raw) refuted it and the sentence now names both numbers.
6. red-I-did-not-cause: `code-health` rc=2 on three pre-existing dirty product files; named, not hidden,
   and not rounded up.
7. gate-doubt:
   - verde-de-verdade: both gates are green because their mutations were executed on copies and each one
     refused **by its named check** (12/12), and because the pre-fix run of the same instrument was RED at
     exactly `battery-wired` — the same bytes produced FAIL then PASS, so the transition is a repair, not
     a fresh green.
   - falta-no-gate: `scripts/task-resolver-gate.py` lives outside `_main/`, and
     `tooling-intent-oracle.py` globs only `_main/` — so a portão born in `scripts/` escapes the
     intent-declaration law entirely. The same gap hides any future `scripts/*-gate.py`.
   - gate-melhor: make `tooling-intent-oracle.py`'s population cover `scripts/` and every top-level tool
     directory it can discover, so `NO-BUG`/`BLOCKS` is required wherever an oracle is born — and let
     `battery-wired` assert the *verdict line* of a recorded step log rather than only the step's bytes,
     which would close the distance between "wired" and "ran green".
8. provenance-corrected: line 4 and §C-03 named **OpenCode Go 1**; the launcher log shows Go 1
   (`09:57:30Z`, after a malformed Go 1 attempt at `09:57:24Z`), Go 2 (`09:57:57Z`) and Go 3
   (`09:58:02Z`, `opencode-go-3/deepseek-v4.1-flash`) for this lane's own title, and this pane's live
   `CommandLine` (pid 10084) is Go 3. Corrected in §11; PID 29004's own process-info stays `REPORTED`,
   because the process had already exited. Rebinding all 24 `done` rows to the new receipt digest is the
   price of editing a receipt, paid in one pass, with `todo.r0.md` byte-identical.
