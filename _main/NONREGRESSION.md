# NON-REGRESSION RECEIPT — lane/nr

**Base:** `main` @ `a296318` (merge: 10 lane branches via lane/mergeall)
**Worktree:** `H:\sotto-wt\nr` (branch `lane/nr`)
**TMPDIR:** `I:\cc-tmp`
**Product root `H:\sotto`:** read-only. Never checked out over. Never mutated.

## Scope
Close two acceptance arms that were never executed:

* **Task A** — three non-regression arms against `main`'s worker:
  1. `--selftest` alone (bundled `sample1.flac`)
  2. `--selftest --audio FILE`
  3. `SOTTO_AUDIO_FILE=FILE`, no flags
* **Task B** — explain `7 captions / rtf 0.08 / RSS 2461 MB` (PIPELINE-WORKS.md)
  against `24 captions / rtf 0.47 / RSS 2417.2 MB` (two independent runs).

## Baseline already executed by root at POPULATION=1 each
| Side | Invocation | mode | rc | captions | WINDOW |
|---|---|---|---|---|---|
| BUG (unpatched) | `--audio FILE` alone | `live` | 3 | 0 | 16:52:35-16:53:46 |
| FIXED | `--audio FILE` alone | `file` | 0 | 24 | 16:55:23-16:55:40 |

Every number in this receipt carries POPULATION and WINDOW.

## Method rules
* Exit codes read via file redirect then `$LASTEXITCODE`. Never piped.
* Never `git add -A`. Only the single receipt file per commit.
* Never commit to `main`.
* `main:worker/sotto_worker.py` copied into this worktree; weights addressed
  explicitly or via `--model` absolute path into `H:\sotto\worker\models`.

## Status
IN PROGRESS — this receipt is the landing marker. Results appended below as arms complete.