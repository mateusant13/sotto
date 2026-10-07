# INTEGRATION-2 — merge of `lane/shresearch` and `lane/pushprep` into `main`

Anchor branch: `lane/intmerge` (worktree `H:\sotto-wt\intmerge`), created from `main @ f9e38d6`.
Repo under merge: `H:\sotto-wt\ArbV8`. `H:\sotto` was not modified.

## merge-tree dry runs (conflict pre-flight)

Git 2.51.0.windows.1 — two-arg `merge-tree` writes a tree and reports conflicts via exit code.

| Branch | Command | rc | Verdict |
|---|---|---|---|
| `lane/shresearch` | `git merge-tree main lane/shresearch` | **0** | clean, tree `88ddc938f90ef0075ca7d8b2286b041b6b8bf1b4` |
| `lane/pushprep` | `git merge-tree main lane/pushprep` | **0** | clean, tree `eb1fd272df88dfe30c0b31f88966a87b65f14018` |

No rc was non-zero, so no conflict resolution was guessed or authored.

## Overlap census

`git diff --name-only f9e38d6..main` returned **POPULATION=0** — `main` had not moved
since the branch point, so there was no main-side drift to collide with.

| Branch | `git diff --name-only f9e38d6..<branch>` | POPULATION | Commits ahead |
|---|---|---|---|
| `lane/shresearch` | `_main/SHADOWPLAY-GAP.md` | 1 | 2 (`6a9aa33` anchor, `50c25f9` table) |
| `lane/pushprep` | `_main/PUSH-PREP.md` | 1 | 2 (`31b8ace` anchor, `43780ae` receipt) |

- Overlap branch-to-branch: **POPULATION=0** (disjoint single files).
- Overlap branch-to-main: **POPULATION=0**.
- Overlap against the dirty set: **POPULATION=0** — neither branch touches
  `_main/CRON-VERDICT.md`, `FRICTION-LEDGER.md`, `control/`, or any of the
  `cron-*` / `*.bat` untracked paths.

## Commit count

| Point | `rev-list --count HEAD` |
|---|---|
| Before | **206** |
| After merge 1 (`shresearch`) | 209 |
| After merge 2 (`pushprep`) | **212** |

+6 total = 2 + 1 merge commit per branch. (Each lane carries a receipt anchor
commit, so +3 per merge is expected, not +2.)

## Dirty census

The 9 pre-existing dirty paths were re-measured immediately before **each** merge.
Count stayed at 9 throughout; no clean/reset/checkout/stash was ever run.

| Point | Dirty count |
|---|---|
| Before | **9** |
| Pre-merge 1 | 9 |
| Post-merge 1 | 9 |
| Pre-merge 2 | 9 |
| After | **9** |

Status letters before and after are byte-identical:

```
 M _main/CRON-VERDICT.md
?? FRICTION-LEDGER.md
?? _main/cron-restore-probe.py
?? _main/cron-restore-refute.py
?? _main/cron-silence-control.py
?? _main/cron-store-loose-ends.py
?? _main/pos.bat
?? _main/spawn2.bat
?? control/
```

## Per-branch outcome

| Branch | merge-tree rc | Merge | Result commit | Outcome |
|---|---|---|---|---|
| `lane/shresearch` | 0 | `--no-ff`, ort, clean | `3761f73` | **landed** — `_main/SHADOWPLAY-GAP.md`, 105 insertions |
| `lane/pushprep` | 0 | `--no-ff`, ort, clean | `c7f33f6` | **landed** — `_main/PUSH-PREP.md`, 174 insertions |

Both artifacts verified present in the `main` HEAD tree via `git ls-tree`.
No `merge --abort` was needed.

## Constraints honoured

- `git add -A` never used; the anchor commit staged exactly `_main/INTEGRATION-2.md`.
- Nothing pushed.
- `H:\sotto` not modified.
- Nothing cleaned, reset, checked out, or stashed.

INTEGRATED: shresearch=yes pushprep=yes