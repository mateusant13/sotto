# INTEGRATION-11 — lane/intmerge12

**Seat:** branch worker · session `mvs_04272bd2a88f4bf79b2da989bfb66ce5`
**Date:** 2026-10-07 (19:24 -03)
**Repo under merge:** `H:\sotto-wt\ArbV8` · **Anchor branch:** `lane/intmerge12` (worktree `H:\sotto-wt\intmerge12`)
**Product root `H:\sotto`:** read-only, never modified. **Scratch:** `I:\cc-tmp` (`TMPDIR/TEMP/TMP` set there; C: is at ~10 GB free).
`git add -A` never used. `git push` never used.

---

## 1. The 10th dirty path — `_main/FAM-ARBV8-INVENTORY.md`

The brief asked for the dirty count (10) to be reconciled against 9, and for the new path to be
identified *first*. It is identified by **three independent instruments that agree**.

**Instrument 1 — set difference against a prior lane's own enumeration.**
`lane/dirtyrescue` (now merged, `_main/DIRTY-RESCUE.md`) enumerated the 9 dirty paths by reading
each off disk at the 21:07 UTC window. The 10 paths measured now, minus those 9:

| # | path | status | in dirtyrescue's 9? |
|---|---|---|---|
| 1 | `_main/CRON-VERDICT.md` | ` M` | yes |
| 2 | `FRICTION-LEDGER.md` | `??` | yes |
| 3 | **`_main/FAM-ARBV8-INVENTORY.md`** | `??` | **NO — this is the 10th** |
| 4 | `_main/cron-restore-probe.py` | `??` | yes |
| 5 | `_main/cron-restore-refute.py` | `??` | yes |
| 6 | `_main/cron-silence-control.py` | `??` | yes |
| 7 | `_main/cron-store-loose-ends.py` | `??` | yes |
| 8 | `_main/pos.bat` | `??` | yes |
| 9 | `_main/spawn2.bat` | `??` | yes |
| 10 | `control/optchat/view.txt` | `??` | yes (`control/`, 1 file) |

**Instrument 2 — mtime clustering.** Nine of the ten fall in a tight **17:28:16 → 17:34:16**
window (a single batch). `_main/FAM-ARBV8-INVENTORY.md` stands alone at **18:37:01**, 63 minutes
clear of the next-newest path.

**Instrument 3 — the file testifies about itself.** Its own header reads
`WINDOW = state as measured 2026-10-07 18:36:55 -03:00`, and its §1 pastes the porcelain
**verbatim — which lists exactly 9 paths and does not list itself.** It is a receipt written by a
lane that measured the 9 immediately before it appeared.

### Is it unbacked work? YES — and it is real work

`git cat-file -e <branch>:_main/FAM-ARBV8-INVENTORY.md` across all 153 lane refs: **absent from
every one.** No lane branch carries it.

Its content is not a stub. It is an evidence receipt: POPULACAO/WINDOW declared, the verbatim
porcelain, a per-file H/D table for staging (`_main/CRON-VERDICT.md | M | 81 | 1 | 8011`), the
finding that CRON-VERDICT.md is **additive (+81/-1) not a rewrite**, and a per-claim grep table
mapping each citation in that verdict to the untracked script that could reproduce it. Its own
seat note says `Writes ONLY this receipt. No git add/checkout/reset/commit.` — **the lane died at
the turn boundary having written the file but never committed it**, which is exactly the failure
mode this whole lane exists to absorb.

**Incompleteness (stated, not hidden):** its `counts:` block is blank — `tracked modified:` and
`untracked:` are labelled but never filled in. That is the one hole; the measurement is trivially
recoverable (1 tracked modified, 9 untracked).

**Verdict: REAL, unbacked, and still uncommitted. It was NOT staged by this lane** — staging it is
a product decision (it is one of the 10 protected dirty paths), not an integration step.

---

## 2. Census by machine sum

Method is `git -C H:\sotto-wt\ArbV8 for-each-ref --format='%(refname:short)' refs/heads/lane/`
with first and last entries printed before any total is trusted (the prior census that returned
POPULATION=0 via a `git branch --list` PowerShell loop is not repeated).

```
POPULATION (refs/heads/lane/) = 153
FIRST = lane/altc
LAST  = lane/whytask
```

Per-branch `git rev-list --count main..<branch>` (the REF `main`, never a path):

| measure | value |
|---|---|
| lane branches | **153** (up from 149 at 22:19 UTC; `lane/intmerge12` is one of them) |
| branches with commits not in `main` | **133** |
| branches already fully absorbed (0 ahead) | **20** |
| **TOTAL commits ahead, machine-summed** | **151** |
| max single-branch lead | **2 commits** (18 branches) |

Population grew +4 during this lane's session; the merge did not cause it — new lanes were being
created concurrently by other seats.

---

## 3. Classification — REAL vs STUB

`git diff --name-status main...<branch>` over all 133 branches:

- **323 file entries, 229 unique paths, 100 % status `A`.** Every lane change is a pure
  *addition* — zero modifications. This is why every merge below was clean.
- Dominant duplication: `RESCUE-82.md` ×12 branches, `SECRET-SCAN.md` ×11, `OWNER-DECISIONS.md` ×9.
- **53 distinct path-signatures across 133 branches.**

STUB was decided by reading the file body, not by size. The stub families literally contain the
word: `placeholder`, `Placeholder anchor. Filled by the census/merge pass.`, `Status: IN PROGRESS`,
`RESULTS (filled in below)`, `Pending measurement`, or are empty (`lane/cronstall` = **0 bytes**).
A receipt is REAL only if it carries a measurement, code, or an evidence-backed verdict.

**Notable borderline calls, stated so they can be overturned:**
- `lane/ptv2` (701 B) — declares POPULATION/WINDOW discipline but all four verdicts read `PENDING`.
  **STUB.**
- `lane/maxch` (987 B) — real hypothesis and real METHOD, but `## RESULTS (filled in below)`. **STUB.**
- `lane/cront` (1251 B) — `Verdict: UNKNOWN`, but records a genuine reusable technical finding:
  the scheduler hydrates from the store only at process start (`restoreActiveJobs`, in-memory Map),
  so "no firing observed" is **not by itself a defect**. Saved later lanes a dead end → **REAL**.
- `lane/blind2` — matrix doc is a 104 B stub, but `blind_corpus.txt` (11,305 B) and `blind_run.ps1`
  (9,413 B) are real artifacts. **REAL on 2 of 3 paths.**
- `lane/rescue82h` — `_main/RESCUE-82.md` is a 26 B anchor, but it carries the **only** non-placeholder
  `RESCUE-82.md` in the population plus a 5,529 B inventory and 164 byte-exact rescued files.
  **REAL**, and the best version of that question.

---

## 4. Overlap analysis

```
git -C H:\sotto-wt\ArbV8 diff --name-only f9e38d6..main   ->   POPULATION = 2
    _main/PUSH-PREP.md
    _main/SHADOWPLAY-GAP.md
```

Checked against every REAL branch's `--name-only`: **POPULATION of overlapping paths = 0.**
Neither file is touched by any branch merged below. (Both were introduced by already-merged
`lane/pushprep` / `lane/shresearch`, which is why they are in the `f9e38d6..main` set.)

**`_main/CRON-VERDICT.md` prohibition honoured by measurement, not assumption:** every one of the
153 lane refs was probed with `diff --name-only main...<branch>`. **NONE touches
`_main/CRON-VERDICT.md`.** It is the one tracked-modified dirty path and it was never a merge
candidate.

---

## 5. `merge-tree` pre-flight rc, and the merges

`git -C H:\sotto-wt\ArbV8 merge-tree main <branch>` re-run against the *evolving* `main` immediately
before each merge, so rc reflects real state, not a stale baseline.

| # | branch | merge-tree rc | merge rc | commits after | dirty | 10 dirty paths |
|---|---|---|---|---|---|---|
| 1 | `lane/dirtyrescue` | **0** | 0 | 215 | 10 | survived |
| 2 | `lane/hygiene` | **0** | 0 | 218 | 10 | survived |
| 3 | `lane/recovery` | **0** | 0 | 221 | 10 | survived |
| 4 | `lane/asrq2` | **0** | 0 | 224 | 10 | survived |
| 5 | `lane/briefkit` | **0** | 0 | 227 | 10 | survived |
| 6 | `lane/roadmap` | **0** | 0 | 230 | 10 | survived |
| 7 | `lane/blind2` | **0** | 0 | 233 | 10 | survived |
| 8 | `lane/rescue82h` | **0** | 0 | 236 | 10 | survived |
| 9 | `lane/ffprep` | **0** | 0 | 239 | 10 | survived |
| 10 | `lane/recordfix` | **0** | 0 | 241 | 10 | survived |
| 11 | `lane/mergegate` | **0** | 0 | 243 | 10 | survived |
| 12 | `lane/nr` | **0** | 0 | 245 | 10 | survived |
| 13 | `lane/cront` | **0** | 0 | 248 | 10 | survived |
| 14 | `lane/intmerge` | **0** | 0 | 251 | 10 | survived |
| 15 | `lane/intmerge8` | **0** | 0 | 253 | 10 | survived |

**merge-tree rc non-zero count: 0. Conflicts: 0. Nothing was guessed or resolved by hand.**

`git merge --no-ff --no-edit` was used, one at a time, in value order. After **every** merge the
dirty set was re-read and compared as an exact sorted set of status-letter+path strings — not just
a count. All 15 steps reported `survived=True`. Any difference would have triggered
`git merge --abort`; that path was never taken.

### Before / after

| | before | after |
|---|---|---|
| `main` HEAD | `c7f33f6` "merge: lane/pushprep (push preparation receipt)" | `02b8608` "Merge branch 'lane/intmerge8'" |
| `rev-list --count main` | **212** | **253** (+41 = 26 absorbed lane commits + 15 merge commits) |
| dirty paths in `H:\sotto-wt\ArbV8` | **10** | **10** |
| branches still holding unmerged commits | 132 | 117 |

### The 10 dirty paths survived — verified by byte size, not just status

Re-measured after all 15 merges against the inventory `lane/dirtyrescue` recorded pre-merge:

| path | expected bytes | actual | status letter |
|---|---|---|---|
| `_main/CRON-VERDICT.md` | 8011 | **8011** | ` M` |
| `FRICTION-LEDGER.md` | 3408 | **3408** | `??` |
| `_main/cron-restore-probe.py` | 2435 | **2435** | `??` |
| `_main/cron-restore-refute.py` | 4421 | **4421** | `??` |
| `_main/cron-silence-control.py` | 4691 | **4691** | `??` |
| `_main/cron-store-loose-ends.py` | 3574 | **3574** | `??` |
| `_main/pos.bat` | 239 | **239** | `??` |
| `_main/spawn2.bat` | 592 | **592** | `??` |
| `control/optchat/view.txt` | 516 | **516** | `??` |
| `_main/FAM-ARBV8-INVENTORY.md` | (new, 3513) | **3513** | `??` |

All 15 merged branches re-measured `rev-list --count main..<branch> = 0`.

---

## 6. Merged — the 15, with what each contributes

| branch | receipts | value |
|---|---|---|
| `lane/dirtyrescue` | `DIRTY-RESCUE.md` + 7 `_tools/` | the 9-path baseline this lane's §1 depends on; the 4-pass cron methodology |
| `lane/hygiene` | `WORKTREE-HYGIENE.md` (50 KB) | machine census, rollback-first move plan; verdict KEEP 70 / DIRTY-RESCUE 34 / EMPTY 73 / ORPHAN 0 |
| `lane/recovery` | `RECOVERY.md` + `_recovered/worker_fab495ac.py` (237 KB) | the only surviving copy of the `sotto_worker.py` edits destroyed by the checkout |
| `lane/asrq2` | `ASR-TRUTH.md` | architecture verdict at `file:line`: no `--lang`, only `--lang-id`, default `auto` (101) |
| `lane/briefkit` | `BRIEF-KIT.md` + 3 | briefs that survive the dispatch-guard hook |
| `lane/roadmap` | `ROADMAP.md` (24 KB) | feature gap, ordered delivery, acceptance gates |
| `lane/blind2` | `blind_corpus.txt` (11 KB) + `blind_run.ps1` (9 KB) | the 45-case blind corpus and its runner |
| `lane/rescue82h` | `RESCUE-82-BACKUP-INVENTORY.md` + 164 files | 82 uncommitted `H:\sotto` files, byte-exact, working + committed |
| `lane/ffprep` | `FF-PREP.md` | rollback command recorded first, product-root pre-state |
| `lane/recordfix` | `RECORD-FIX.md` | durable records that were measurably wrong |
| `lane/mergegate` | `MERGE-GATE.md` | 5-case behavioural gate for the `audio_file`/`file_mode` change |
| `lane/nr` | `NONREGRESSION.md` | base + `TMPDIR=I:\cc-tmp` + read-only-root constraints |
| `lane/cront` | `CRON-TRUTH.md` | the process-start hydration confound (verdict still UNKNOWN) |
| `lane/intmerge` | `INTEGRATION-2.md` | prior integration receipt, method precedent |
| `lane/intmerge8` | `INTEGRATION-7.md` | independently recorded **9 dirty paths at main `c7f33f6`** — corroborates §1 |

---

## 7. Deduplicated — 82 duplicate-skipped, 35 unique stubs, 0 conflicted

117 branches were left holding commits. All 117 were skipped; they partition cleanly.

**(a) 23 branches duplicate a receipt already merged — the best version won:**

| branch family | count | merged instead |
|---|---|---|
| `lane/rescue82{,b..l}` | 11 | `lane/rescue82h` (only non-placeholder `RESCUE-82.md`) |
| `lane/blind3..8`, `lane/blindmatrix` | 6 | `lane/blind2` (real corpus + runner) |
| `lane/roadmap2..4` | 3 | `lane/roadmap` (24 KB vs stubs) |
| `lane/cront5`, `lane/cron6` | 2 | `lane/cront` (real confound finding) |
| `lane/recover` | 1 | `lane/recovery` (237 KB recovered source) |

**(b) 59 branches are duplicates inside still-stub families** — same receipt path, every variant a
placeholder, so no best version exists: `SECRET-SCAN.md` ×11, `OWNER-DECISIONS.md` ×9,
`THRESHOLD-RESULTS.md` ×8, `ELECTRON-ARM.md` ×8, `ASR-WER.md` ×6, `WORKTREE-ARCHIVE.md` ×6,
`CRON-FIX.md` ×6, `INTEGRATION-3.md` ×3, `DISPATCH-GUARD.md` ×3, `AUDIO-BATTERY.md` ×3,
`SCALE-AUDIT.md` ×3, `CRON-VERIFIED.md` ×2, `HARVEST.md` ×2, `SURVIVAL.md` ×2,
`PASS-THROUGH-VERIFY.md` ×2.

**(c) 35 branches are unique-but-stub** — no duplicate to dedup against; skipped purely because
their only content is a placeholder: `RECOVERY.md`(superseded), `REDACTION-PREP.md`,
`CRON-STALL.md` (0 bytes), `TICK-DELTA.md`, `WAKE-CHAIN.md`, `CAPTION-THRESHOLD.md`,
`PARSER-RECHECK.md`, `MERGE-AUDIT.md`, `MISSION-WATCH.md`, `MAXCHUNKS.md`, `INTEGRATION-{4,5,6,8,9,10}.md`,
`WHY-NOTHING.md`, `HANG-DIAGNOSIS.md`, `CRON-DIAGNOSIS.md`, `DELIVERY-CONTRACT.md`,
`CRON-DELIVERY.md`, `CRON-FIX.md`, `guardfix/guard3`, `electron3..8`, `scan2..12`, `thresh3..9`,
`cronfix2..6`, `cronverify2`, `decisions2..10`, `wer2..6`, `scale3`, `scalegate2`,
`rescue82c..l`, `ptverify`.

**Reconciliation:** 15 merged + 23 (a) + 59 (b) + 35 (c) = **132** external branches that held
commits, + 20 already-absorbed + `lane/intmerge12` = **153**. ✔

---

## 8. What this lane did NOT do, and why

- **Did not stage or commit any of the 10 dirty paths.** They are other lanes'/the owner's
  uncommitted evidence. `lane/dirtyrescue` reached the same conclusion and recorded it as a
  preservation rule. Staging them is a product decision.
- **Did not merge the 35 unique stubs.** Brief: do not merge branches whose only content is a stub.
- **Did not merge the 82 duplicates.** Their content is byte-equivalent-or-worse than the version
  that landed; merging them would only re-add `placeholder`.
- **Did not modify `H:\sotto`.** Read-only throughout.
- **Did not touch `_main/CRON-VERDICT.md`.** Prohibition honoured; verified no branch touches it.
- **Did not clean up the branch population.** 153 refs / ~230 worktrees remain. That is a hygiene
  question and `lane/hygiene` already has the plan; it is not this lane's call.

### Risks left open

1. **`_main/FAM-ARBV8-INVENTORY.md` is real and still unbacked.** It is the one piece of newly
   identified work that no branch holds. It should be committed by whoever owns that lane's output,
   or deliberately discarded with a recorded reason.
2. **117 branches still carry only placeholders.** They are inert weight in `refs/heads/lane/*` and
   will keep inflating the population until pruned. A census that counts branches will keep
   over-reporting work that does not exist.
3. **`lane/cront`'s verdict is still UNKNOWN.** Merging the receipt does not resolve it.

---

INTEGRATED: 15 merged, 82 duplicate-skipped, 0 conflicted