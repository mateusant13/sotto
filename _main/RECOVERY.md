# RECOVERY RECEIPT — worker/sotto_worker.py

**Incident:** 2026-10-07 16:55, root ran `git -C H:\sotto checkout main -- worker/sotto_worker.py`
while `H:\sotto` was on `feat/build-verify-1`. The file was already showing ` M` in
`git status --porcelain` (modified, uncommitted). The checkout overwrote it.
The lost content is the **uncommitted working-tree version** of that file.

**Hard rule:** nothing in `H:\sotto` is modified by this recovery. All work happens in
`H:\sotto-wt\recover` on branch `lane/recover` (cut from `main` @ `a296318`).

---

## Status (as of first commit — filled in below by each search)

### 1. `git -C H:\sotto stash list`
```
EXIT=0
(empty — no stash entries)
```
**Result: NOT RECOVERABLE via stash.**

### 2. `git fsck --lost-found --dangling`
See section 2 below (populated during the search).

### 3. Other worktrees / branches holding a differing `worker/sotto_worker.py`
See section 3.

### 4. Windows-side artifacts (`.orig`, `.rej`, editor backups, shadow copies)
See section 4.

### 5. `lane/*` branches with a non-matching `worker/sotto_worker.py`
See section 5.

---

## `feat/build-verify-1` (@ 24df100) vs `main` (@ a296318)
See section 6.

---

## Verdict
_Filled in at end of investigation._