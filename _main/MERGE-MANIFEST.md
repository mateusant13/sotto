# MERGE MANIFEST — unmerged branch work in Sotto / ShadowPlay clone

**POPULATION:** 101 branches enumerated via `git -C H:\sotto-wt\ArbV8 branch --list`
(100 non-`main` + `main`). Every one of the 100 was measured individually.
**WINDOW:** snapshot taken 2026-10-07 ~15:35–15:55 -03:00 against `main @ 615110e`
(78 commits, "merge: scale gate fix -- 9-arm selftest, old gate proved RED on a 3.3x miss").
Any branch not in this table is either already merged or is a member of a family named here.

**PROPOSAL ONLY — no merge was executed into `main` by this sweep.** The owner executes.

---

## 0. Correction of the previous census

The earlier census read `git log main` and concluded "zero production work". That is wrong
and this manifest supersedes it. `main` has 78 commits and the real, unmerged production work
is visible only on branches. Two corrections to the naive measurement, both applied here:

1. **`git diff main...<branch>` (three-dot) is not the only signal, and two-dot is misleading here.**
   `git diff main <branch>` (two-dot) reports 384–4213 changed lines on *every* branch — but
   that number is almost entirely **main's own 78 commits of progress** that the branch lacks,
   not branch work. Using two-dot would invert the verdict on every row.
2. **Three-dot overcounts "unmerged".** It measures merge-base→branch, which stays non-zero even
   when `main` has independently absorbed the same content. Every row below was therefore
   re-checked **per file by blob sha** (`git rev-parse main:<file>` vs `<branch>:<file>`).
   Only content genuinely absent from `main` is counted. That test is what demoted
   `feat/audio-v6` from "93-line divergence" to **already merged**.

**Headline: the "500+ lines" figure was real, but it is ~80% verdict documents, not code.
Genuinely unmerged PRODUCTION CODE is 159 lines on exactly 2 branches.**

---

## 1. FAMILY TABLE — branches with work not in `main`

Recovery is reported **per family, deduplicated**: where one branch carries another's
commits byte-identically, the superset is counted once and the members are marked redundant.
Families are the unit. Branches are the evidence.

| # | Family — branch(es) | sha range | Files | Lines (add/del) | What it implements | VERDICT |
|---|---|---|---|---|---|---|
| F1 | `feat/ring-cap-ram-c` | `caf7a9a` (1 ahead) | 1 | +67/−6 = **73** | Ring capture budget is priced from **SYSTEM RAM** (`clamp(0.25×TotalPhysicalMemory, 256 MiB, 4096 MiB)`) instead of `dedicated_vram/16`, with a `SOTTO_RING_CAP_MB` override that passes through the same bounds and refuses absurd input out loud. | **MERGE NOW** |
| F2 | `feat/stdin-v9` | `b9a7e89..fe544e4` (2 ahead) | 1 | +86 = **86** | Blocking `ReadFile` on the `STD_INPUT_HANDLE` as the detached-process control channel — one line in, one flushed line out, byte-at-a-time so a command cannot steal the next byte's first char; no stdin handle ⇒ channel OFF, not broken. | **NEEDS REVIEW — conflicts** |
| F3 | `feat/build-verify-1` **⊃** `feat/ring-measure-1`, `feat/hb-truth-1` | `938074b..24df100` (5 ahead) | 3 | +467 = **467** (members add 224 + 75, **byte-identical** — see §3) | Build/heartbeat/ring verification receipts: real compile rc + errors for the recovered stdin control, measured delivery (real queue counts), measured RAM/VRAM + candidate ceilings. | **MERGE NOW** |
| F4 | `feat/probe-e2e-1` | `2acc0ae` (1 ahead) | 1 | +112 = **112** | Verdict for the e2e slice probe's **first real execution**: `RC=0` read from `$LASTEXITCODE` after redirection, `VERDICT: GREEN`, empty FAILURES, per-stage pass/fail. | **MERGE NOW** |
| F5 | `docs/ram-v6` | `7a994b4` (1 ahead) | 1 | +19/−1 = **20** | Splits law-7's 16 GB **design floor** from this box's measured **47.74 GiB**, so neither licenses the other's ring number. | **NEEDS REVIEW — depends on F1** |
| F6 | `feat/cut-verb-3` | `0ac3fc2` (1 ahead) | 1 | +9 = **9** | Anchor recording that `build.cmd:12` hardcodes `H:\aireplay\src\capture` — a **different checkout** with a different `main.cpp` sha, not this tree. | **MERGE NOW** (cheap, real ops finding) |
| F7 | `feat/verify-499-1` | `458856c` (1 ahead) | 1 | +3 = **3** | Placeholder header — "measurement in progress". No measurement. | **DEAD — do not merge** |
| F8 | **anchor-only family (22 branches)** — `feat/audio-wire`, `feat/audio-wire-2`, `feat/auth-fix-2`, `feat/blind-bdeda02`, `feat/blind-bdeda02-2`, `feat/crash-probe-2`, `feat/crash-probe-3`, `feat/cut-verb-2`, `feat/endpoint-stable-1`, `feat/forgery-fix-2`, `feat/index-perf-1`, `feat/merge-audit-2`, `feat/probe-e2e-2`, `feat/ram-budget-1`, `feat/review-952`, `feat/review-db0cf35`, `feat/rrf-3ch-1`, `feat/rrf-crash-1`, `feat/rrf-probe-2`, `feat/scale-probe-2`, `docs/parity-1`, `chore/merge-sweep-1` | 22 distinct shas | 22 | +22 = **22** | One-line provenance anchors ("index: perf anchor", "crash: probe anchor"). Lanes that created an anchor and died. **Zero functionality.** | **DEAD — do not merge** (24 lines total for the whole family) |

### Already in `main` — nothing to recover (reported, not dropped)

| Bucket | Branches | Evidence |
|---|---|---|
| Fully merged | **67** | `rev-list --count main..<branch>` = 0 |
| Ahead but **zero** content divergence | **2** — `feat/audio-tap-2`, `feat/audio-tap-real` | 3-dot diff empty; tree equals merge-base |
| Diverged but **content absorbed** | **1** — `feat/audio-v6` (`dbe7d8a`) | 3-dot showed `audio_tap.h` +9, but per-file blob check: `main` already holds that content → **0 recoverable** |

**POPULATION check: 8 (unmerged families, F1–F8) + 67 + 2 + 1 = 78 content-states,
covering all 100 non-`main` branches. F8 alone accounts for 22 of them.**

---

## 2. READY TO MERGE NOW

Additive, non-conflicting, **verified** with read-only `git merge-tree --write-tree main <branch>`
(exit 0 = clean; no working tree touched). In dependency order.

**POPULATION: 4 of 8 families. WINDOW: main @ `615110e`.**

| Order | Family | Command | Conflict check |
|---|---|---|---|
| 1 | F1 `feat/ring-cap-ram-c` — **highest value; fixes a LIVE defect** | `git -C H:\sotto-wt\ArbV8 merge --no-ff feat/ring-cap-ram-c` | `merge-tree` exit **0** |
| 2 | F6 `feat/cut-verb-3` — ops finding, 9 lines, new file only | `git -C H:\sotto-wt\ArbV8 merge --no-ff feat/cut-verb-3` | `merge-tree` exit **0** |
| 3 | F3 `feat/build-verify-1` — receipts bundle (supersedes ring-measure-1 + hb-truth-1) | `git -C H:\sotto-wt\ArbV8 merge --no-ff feat/build-verify-1` | `merge-tree` exit **0** |
| 4 | F4 `feat/probe-e2e-1` — e2e verdict | `git -C H:\sotto-wt\ArbV8 merge --no-ff feat/probe-e2e-1` | `merge-tree` exit **0** |

Order rationale: F1 is independent and lands the only live production fix, so it goes first.
F6–F4 are mutually independent (disjoint files: `_moved/aireplay/src/capture/main.cpp` vs
`_moved/aireplay/AGENTS.md` vs `_main/*.md`) and can be taken in any order.

### NOT in the list above, and why

- **F2 `feat/stdin-v9` — EXCLUDED, it conflicts.** `merge-tree` exit **1**:
  `CONFLICT (content): Merge conflict in _moved/aireplay/src/capture/main.cpp`.
  `main` has rewritten that file since the branch forked. Requires manual resolution
  (owner decision on stdin control vs. current `main.cpp` structure). Do **not** attempt
  a blind merge. Branch tip `fe544e4`, base commit `b9a7e89`.
- **F5 `docs/ram-v6` — EXCLUDED, it depends on F1.** It documents F1 as unmerged
  ("exists on `feat/ring-cap-ram-c` … but is **NOT an ancestor of `main`** … **Until that
  merge lands, the defect is LIVE**"). Merging it *before* F1 makes the text true but
  merges a description of a bug you are about to fix; merging it *after* F1 makes the text
  **stale**. It needs a wording edit, not just a merge. → **UNVERIFIED whether the owner
  prefers amend-then-merge or merge-then-amend.**
- **F7, F8 — DEAD.** No product value.

---

## 3. Deduplication evidence (why F3 is one row, not three)

Blob-sha equality, `feat/build-verify-1` vs its members:

| File | `build-verify-1` | member branch | identical? |
|---|---|---|---|
| `_main/ring-cap-measurements.md` | `7d4fcae1151d208203ce34fd12e539cbf11f3339` | `feat/ring-measure-1` `7d4fcae…` | **YES** |
| `_main/heartbeat-truth.md` | `3cef6b8c0d35ee6cdd8d7803ab0ac940e6c8499f` | `feat/hb-truth-1` `3cef6b8c…` | **YES** |

`feat/build-verify-1` also integrates `248dfc9` (`feat/scale-probe-1`), which is **already an
ancestor of `main`** and contributes 0 new content. So **merge `build-verify-1` only**;
after it lands, `feat/ring-measure-1` and `feat/hb-truth-1` carry nothing further.

---

## 4. TOP 5 BY PRODUCT VALUE (ShadowPlay functionality)

Ranked on whether the branch moves **capture, cut, instant replay, crash recovery, index, search** —
not on line count.

1. **F1 `feat/ring-cap-ram-c` (73 lines) — INSTANT REPLAY, the only live bug fix in the set.**
   The replay ring is a `std::vector<uint8_t>` in **system RAM**, but the cap was priced from
   **dedicated VRAM/16**. On this box that bound at 998.69 MiB ≈ 2% of the pool it should read
   and **silently clipped 4K60 to 46.5 s instead of the promised 120 s**. Confirmed live:
   `git merge-base --is-ancestor caf7a9a main` → exit 1. Corroborated independently by F5's
   doc. Fix is clean-mergeable and 4.8x'd in severity-to-lines.
2. **F2 `feat/stdin-v9` (86 lines) — CAPTURE control plane.** The channel that lets a detached
   capture process be driven by a parent (ping/step). Real code, real receipts — but it
   **conflicts with `main`** and needs an owner decision. Highest *ceiling*, blocked by merge cost.
3. **F3 `feat/build-verify-1` (467 lines) — CRASH RECOVERY / build truth.** The receipts that
   let anyone tell whether a capture build is real, whether heartbeat delivery actually happens
   (measured queue counts, not "should work"), and what the ring actually costs. Largest line
   count in the set and it is what makes F1/F2 auditable.
4. **F4 `feat/probe-e2e-1` (112 lines) — END-TO-END search/chain proof.** First real execution of
   the e2e slice probe, `RC=0`, `VERDICT: GREEN`, exit code read from `$LASTEXITCODE` after
   redirection rather than a pipe. Documentation of a working chain, not the chain itself.
5. **F6 `feat/cut-verb-3` (9 lines) — CUT.** 9 lines, but it carries the single most
   operationally valuable sentence in the whole sweep: `build.cmd:12` hardcodes
   `H:\aireplay\src\capture`, a **different checkout with a different `main.cpp` sha**.
   Any future "cut" lane that builds there is building the wrong tree. Cheap to keep.

**Everything not on this list is a document about a measurement, a provenance anchor, or an
empty placeholder.** Note what is **absent** from all 90+ branches: no `search` implementation,
no working `cut` verb, no `crash recovery` code, no `index` code — only docs and probes about them.
**UNVERIFIED** whether that work exists somewhere outside this repo (e.g. the separate
`H:\aireplay` checkout) or was never written.

---

## 5. Line accounting

**POPULATION:** 100 non-`main` branches, deduplicated into 8 families holding unmerged content.
**WINDOW:** main @ `615110e`, 78 commits, measured 2026-10-07 ~15:35–15:55 -03:00.

| Measure | Lines |
|---|---|
| Raw sum over all 32 diverging branches (double-counts families) | 1091 |
| **Deduplicated by family (F1–F8)** | **792** |
| — of which **production code** (F1 + F2) | **159** |
| — of which verification/verdict documents (F3 + F4) | 579 |
| — of which spec/ops docs (F5 + F6) | 29 |
| — of which dead anchors/placeholders (F7 + F8) | 25 |
| **Clean-mergeable now (F1+F3+F4+F6)** | **661** (160 of it production code) |
| Blocked on conflict resolution (F2) | 86 |
| Blocked on wording decision (F5) | 20 |

---

## 6. Method, so it can be re-run and contradicted

```
git -C H:\sotto-wt\ArbV8 branch --list --format='%(refname:short)'   # population
git -C H:\sotto-wt\ArbV8 rev-list --count main..<branch>             # is it ahead
git -C H:\sotto-wt\ArbV8 diff --numstat main...<branch>              # 3-dot candidate files
git -C H:\sotto-wt\ArbV8 rev-parse main:<file> <branch>:<file>       # THE decisive test
git -C H:\sotto-wt\ArbV8 merge-tree --write-tree main <branch>       # read-only conflict check
```

`merge-tree --write-tree` never touches the index or working tree — that is why conflict status
is reported here without a merge having been performed. No `git add -A` was run; no branch was
merged; `main` is untouched.

### Window drift — re-verified

`main` advanced **during** this sweep, from `615110e` to **`82ddeb7`**
(`scale: gate verified RED on a real run (rc=1 at N=20000)…`, reflog `main@{0}`). This sweep
performed **no merge and no commit to `main`** — the advance is another lane's. Because every
conflict check above was computed against the older head, all six were **re-run against
`82ddeb7` and every verdict is unchanged**:

| Branch | vs `615110e` | vs `82ddeb7` |
|---|---|---|
| `feat/ring-cap-ram-c` (F1) | clean | **clean** |
| `feat/cut-verb-3` (F6) | clean | **clean** |
| `feat/build-verify-1` (F3) | clean | **clean** |
| `feat/probe-e2e-1` (F4) | clean | **clean** |
| `docs/ram-v6` (F5) | clean | **clean** |
| `feat/stdin-v9` (F2) | conflict | **conflict** |

Ancestry re-checked at the new head: `caf7a9a`, `24df100`, `2acc0ae` all still **NOT** ancestors
of `main` (`merge-base --is-ancestor` exit 1 each) — none of the four READY families was
absorbed while the sweep ran. **The READY TO MERGE NOW list stands as written, valid against
`main @ 82ddeb7`.** If `main` moves again, re-run the `merge-tree` command from §6 before merging.

**UNVERIFIED / limits of this sweep:**
- Conflicts are detected structurally (`merge-tree` exit 1), not by compiling. A clean merge can
  still fail the build — F1 touches `d3d11_ctx.cpp` and **no build was run here**.
- Semantic overlap between F1 and F5 was reasoned from prose, not from a spec trace.
- Branches were measured as named at this snapshot; a branch pushed mid-sweep is not in POPULATION.
- The 22-branch anchor family was sampled (3 of 22 contents read); all 22 were counted as
  1-line anchors from `--numstat`, which is mechanical, but only 3 were read verbatim.