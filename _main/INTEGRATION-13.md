# INTEGRATION-13 — finish the worktrees, land everything, prune the rest

**Date:** 2026-10-09 · **Repo under merge:** `H:\sotto-wt\ArbV8` (`main`)
**Product root `H:\sotto`:** read-only, never modified. **Scratch:** `I:\cc-tmp`.
`git add -A` never used; every path was listed explicitly.

Owner's brief, verbatim: *"termina os trabalhos das worktrees, se ja nao foi
terminado ainda, e da merge commit push etc."* then *"limpa oq e inútil ou
duplicado do sotto e suas worktrees"* and, for the conflicts, *"monte um workflow
voce mesmo pra voce resolver tudo e fazer tudo LAND e depois da commit e push"*.

---

## 1. Headline — before / after

| | before | after |
|---|---|---|
| worktrees registered | **318** | **9** |
| `refs/heads` | **330** | **8** |
| `main` `rev-list --count` | **253** (`02b8608`) | **401** |
| commits added to `main` | — | **148** (58 merge + 90 content) |
| files changed on `main` | — | **304** |
| branches on `origin` | **1** (`main`, 243 commits stale) | **184** (all of them) |
| `origin/main` | `a3c288f` (243 behind) | == local `main` |

The 9 worktrees left are `H:\sotto`, `ArbV8` (`main`) and the 6 `main.cpp`
branches plus `feat/stdin-v9` which has two.

## 2. What landed, in four waves

**Wave 1 — 21 branches (receipts + code), preflight clean.** Includes the
largest receipt in the repo: `lane/intmerge12`'s `INTEGRATION-11.md` (281 lines),
whose lane *did* the work — its 15 merges are exactly how `main` reached
`02b8608` — and then committed the receipt without merging it.

**Wave 2 — 19 of 21.** `lane/replay` and `lane/censusfix` were refused by the
real preflight (both add a root `LANE-ANCHOR.md`, and `lane/census-tree3` had
already brought one minutes earlier). Not resolved by hand; their unique files
landed later in wave 3.

**38 dirty worktrees committed first.** 62 paths, all measured to be content
`main` did **not** hold (`IN_MAIN = 0` of 62): receipts, probes, `.ps1` runners,
source edits, an 83-file `_recovered/` stash, a 54-file `dispatch-guard/` suite.
Refused only by explicit guards — detached HEAD, a merge in progress, a path
escaping the worktree, a missing path — and none tripped.

**Wave 3 — 14 conflicts landed by an evidence-derived workflow.** Measured, not
guessed: for each conflicted file the multiset
`lines(branch) − lines(main)` was computed.

| decision | count | basis |
|---|---|---|
| `OURS` (keep `main`) | 13 | branch's unique lines are `placeholder` / `# skeleton`, or an older draft, or an alternative implementation of a feature `main` already has |
| `THEIRS` (take the branch) | **1** | `lane/blind5` `_main/blind_run.ps1` |

The one `THEIRS`: measured **98.84 % identical** to `main` with a **single hunk**
— `return $out` → `return ,$out` plus a 3-line comment naming a real PowerShell
defect (a `byte[]` enumerated into the output stream arrives as `Object[]`/null
and makes `Process.StandardInput.BaseStream.Write` throw). `main` did not have
that fix. It does now.

Two rules were *not* applied blind, both checked first:
- `feat/cut-verb-5`'s `main.cpp` branch-only lines were `stdin_handle(...)` and
  `cmd == "ping"` — grepping `main`'s `main.cpp` returned **`stdin_handle` ×3**
  and **`cmd == "ping"` ×1**, so `main` already carries it → `OURS`.
- `feat/ring-cap-ram`'s `d3d11_ctx.cpp` and `main`'s are **two independent
  implementations of the same "Law 7 ring budget"** (`SOTTO_RING_MB` vs
  `SOTTO_RING_CAP_MB`, `system_phys_bytes()` vs `system_total_phys_bytes()`).
  `main`'s is the integrated one → `OURS`.

**Wave 4 — the 4 excluded candidates, landed selectively.** Per file:
bytes already in `main` → skipped as duplicate; backup path → skipped; otherwise
written and staged. `lane/thresh3` landed 5 and skipped 5 byte-identical copies
of worker scripts; `lane/audiofix` 2; `lane/recovery` 1 (`worker_186c969e_HEAD.py`)
and **82 backup paths skipped**; `feat/rrf-3ch-2` 1. Then `git merge -s ours` for
each, which marks them absorbed **without changing a single byte**: the tree sha
was `8c126d1e…` before and `8c126d1e…` after.

## 3. Gates — on the merged bytes, existing files only

`git diff --name-only 02b8608..main`, filtered to paths that exist on disk
(the first run did not filter and reported every `_backup/` file the commit had
deliberately deleted as a "syntax failure" — a false red, corrected here):

| gate | checked | failed |
|---|---|---|
| `py -3 -m py_compile` | **34** | **0** |
| `node --check` (`.js`/`.mjs`) | **49** | **0** |
| `json.load` | **9** | **0** |

`git diff --diff-filter=D 02b8608..main`: 160 deleted paths, **160 under
`_backup/`, 0 anywhere else**. Nothing outside the backup was removed.

## 4. The 10 protected dirty paths — byte-exact, re-checked after every wave

All 10 verified by `os.path.getsize` against the inventory `lane/dirtyrescue`
recorded, after wave 1, wave 2, wave 3 and the `_backup/` removal:
`ALL_OK=True` each time. `_main/CRON-VERDICT.md` 8011, `FRICTION-LEDGER.md` 3408,
`_main/FAM-ARBV8-INVENTORY.md` 3513 and the other seven — none staged, modified
or deleted.

## 5. Prune — 157, and the 6 that were deliberately NOT pruned

Approved by the owner: 163. Measurement cut it to **157**, because the number
I first quoted was wrong about 6 of them:

- **152** rejected as stub/scaffold (the tier call is in `I:\cc-tmp\plan4.txt`).
- **5** `lane/blind{3,6,7,8,matrix}` — proven redundant: `main` already holds
  `blind_corpus.txt` byte-identical (11305 B), `blind_run.ps1` **strictly newer**
  (9710 B with the unary-comma fix) and a bigger `BLIND-MATRIX.md`.
- **KEPT — 6 branches edit `_moved/aireplay/src/capture/main.cpp` and hold lines
  `main` does not have:**

| branch | bytes | lines only the branch has |
|---|---|---|
| `feat/cut-verb-4` | 44217 | **171** |
| `feat/reply-fix-1` | 32695 | **201** |
| `feat/auth-fix-1` | 31826 | **191** |
| `feat/parse-fix-1` | 27769 | **128** |
| `feat/cut-verb-i2` | 27803 | **70** |
| `feat/stdin-v9` | 23245 | **10** |

My brief to the owner called all 163 "stub or exact duplicate". For these 6 that
is **false** — they are different edits to one file, not duplicates of it. Pruning
them would have destroyed unmerged code on a justification that did not hold, so
they were kept. They are the open work.

Every ref was deleted with `-D`, which is safe for one measured reason:
`git push origin --all` ran **before** any pruning, so all 184 branches exist on
`origin` and are recoverable by name.

## 6. `_backup/H-sotto/` removed from `main` — the owner's call

164 files, `committed/` + `working/`, `lane/rescue82h`'s byte-exact rescue of the
2026-10-07 checkout accident. Owner: *"backup tem que existir é no remoto. push ja
e backup, correto? entao faça pushes."*

Measured before removing it — it is a **stale snapshot, not the live tree**:

| file | in backup | live in `H:\sotto` |
|---|---|---|
| `AGENTS.md` | 54598 B | **60765 B** |
| `app/panel/panel.js` | 83780 B | **118951 B** |
| `README.md` | 2870 B | **14180 B** |
| `worker/config.json` | 4707 B | **5882 B** |

No tracked file referenced it. The bytes remain in this commit's history and on
`lane/rescue82h` at `origin`. **Deleting the paths deletes no information.**

## 7. Instrument defects found, both in my own tooling

1. **`protected_state()` opened paths relative to the script's cwd.** Every size
   read `None`, so every merge was reported `VIOLATION → aborted` while
   `git merge --no-ff` had already **committed** and `git merge --abort` silently
   found no `MERGE_HEAD`. The printed verdict was wrong in the direction that
   *looked* safe. Fixed with `os.chdir(WT)`; re-measured from the worktree, all
   10 byte-exact. Hit three times (`_wt-merge.py`, `_wt-land.py`, and the first
   run of `_wt-cleanup-run.py` where `git("worktree", "remove", …)` passed the
   subcommand as the repo and removed **nothing** while reporting 135 refusals).
2. **A gate that did not filter to existing files** reported 40+ false failures
   on paths the `_backup/` commit had deliberately deleted. Corrected in §3.

## 8. What this pass did NOT do

- **Did not modify `H:\sotto`.** Read-only throughout; its 94 modified / 914
  untracked files are untouched and are a separate decision.
- **Did not stage any of the 10 protected dirty paths.**
- **Did not delete anything outside `_backup/` from `main`** (measured, §3).
- **Did not touch `origin`'s branch set** — only pushed; nothing pruned remotely,
  on purpose, because the remote *is* the backup.
- **Did not resolve a conflict by hand** where the content was ambiguous; the 6
  `main.cpp` branches were kept instead.

### Risks left open

1. **6 branches of `main.cpp` hold 10–201 unmerged lines each** (§5). That is the
   remaining real work, and merging them needs someone to read the deltas — they
   are old variants of a file `main` has grown to 62614 B.
2. **`H:\sotto` is 191 commits behind `main` and still dirty.** It is the product
   root and was out of scope; syncing it is a product decision.
3. **`_sotto-lanes/`** in `H:\sotto-wt` holds three receipts from a concurrent
   seat (`BUILD-VERDICT`, `DRIFT-CENSUS`, `MERGE-DEBT`) and is unreferenced by
   any tracked file. Left alone — it is another seat's work, not this pass's.

---

LANDED: 58 merge commits, 14 conflicts resolved by measurement (13 OURS / 1 THEIRS),
0 hand-guessed, 157 branches pruned with a pre-prune push, 164 backup paths removed,
34+49+9 gates green, 10 protected paths byte-exact
