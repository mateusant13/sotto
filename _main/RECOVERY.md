# RECOVERY RECEIPT — `worker/sotto_worker.py`

Lane: `lane/recovery` · Anchor commit: `2249e96` · Date: 2026-10-07
Target: `H:\sotto\worker\sotto_worker.py` (uncommitted edits destroyed by a `checkout`/`reset`)
Constraint honoured: **`H:\sotto` was never written to.** No checkout, reset, clean, update-ref or
lost-found write was issued against it. Every read below used `cat-file` / `diff` / `ls-tree` only.

## WHAT ACTUALLY HAPPENED (not "lost" — stashed 6 s before the reset)

| | |
|---|---|
| destroying command | `24df100 HEAD@{2026-10-07 13:58:41 -0300}: reset: moving to HEAD` (reflog line 1) |
| last stash before it | `1f47e838` @ `2026-10-07 13:58:35 -0300` — `WIP on feat/build-verify-1: 24df100` |
| gap | **6 seconds** |
| why it looked lost | `refs/stash` no longer exists (`rev-parse --verify refs/stash` → rc=128); `git stash list` is empty. The stash survived **only** as dangling commits, so `git stash apply`/`pop` cannot reach it. |
| worktree proof of the revert | `worker/sotto_worker.py` is 236,802 B on disk; HEAD blob `186c969e` is 232,291 B. The 4,511 B gap is exactly CRLF: `core.autocrlf=true`, 4,511 CR-LF pairs, 236,802 − 4,511 = 232,291. `git hash-object` of the worktree file = `186c969e…` = HEAD, and `git status --porcelain` is empty. The worktree really was reverted to the committed state. |

## ROUTE TABLE

| route | command | rc | POPULATION | verdict |
|---|---|---|---|---|
| 1 | `git -C H:\sotto fsck --unreachable --dangling --no-progress` | **2** | 141 unreachable blobs, 46 unreachable commits, 242 unreachable trees (0 dangling) | **RECOVERED.** rc=2 comes from pre-existing `invalid reflog entry` errors on `lane/asrq2`, not from this command. The 46 "unreachable commits" are `git stash` entries (`WIP on …`); 23 of them carry the target file. |
| 2 | `git -C H:\sotto reflog --date=iso \| Select-Object -First 60` | **0** | 61 entries; line 1 is the `reset: moving to HEAD` at 13:58:41 | **RECOVERED.** Identifies the exact destroying command and its timestamp. |
| 3 | `git -C H:\sotto stash list` | **0** | **0 entries.** `refs/stash` absent (`rev-parse --verify refs/stash` → rc=128) | Empty route, but **not** a dead end: the stash ref was dropped, so the content survives only as the dangling commits of route 1. `git stash apply` will not work. |
| 4 | `Get-ChildItem -Path H:\sotto -Recurse -Include *.orig,*.rej,*~` | **0** (0 hits) | 0 backup files. `ORIG_HEAD` exists = `24df100` (= current HEAD, so no pre-reset pointer). `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REBASE_HEAD` absent. | Nothing recovered — nothing to recover. `ORIG_HEAD` adds no information: it points at the post-reset HEAD. |
| 5 | `fsck --lost-found` extract + diff | **0** | blob `fab495ac193bfddeff24a5888f545980ebc06677`, **237,489 B**, `ast.parse` OK, +89/−8 vs HEAD, 6 hunks | **RECOVERED.** See below. |
| 6 | `vssadmin list shadows` | **0** | 1 shadow `{9093735F-CA3F-498A-8B99-D184ABCAE54F}` (2026-10-07 16:40:59) on volume **(C:)** only | Dead end for this file: H: is `Volume{610d1e52-10d4-436b-b959-6d32af5d8bdd}` and is **not** shadowed. |

### Deliberate deviation from the literal route 1 / route 5 commands
Both are written in the brief as `fsck --lost-found`, which **writes** `H:\sotto\.git\lost-found`
and therefore violates the READ-ONLY rule in the same brief. I ran the no-write variant
(`--unreachable --dangling`) and extracted via `git cat-file blob`, which yields byte-identical
objects and touches nothing. Consequence: no `.git\lost-found` directory exists — which is correct,
since creating it would have modified the repo under protection. `git bundle create` was also
attempted (rc=128, `Refusing to create empty bundle`) and abandoned for the same reason: it needs a
ref, and creating one in the shared object store would have mutated `H:\sotto`.

## WHAT WAS RECOVERED

The recovered object is **not only the worker file.** The stash `1f47e838` vs its base `24df100` is
**82 files, +22,801 / −2,392 lines**. `worker/sotto_worker.py` is +89/−8; the largest single loss is
`app/webview/sotto_webview.py` at **2,323 changed lines**.

`worker/sotto_worker.py` — blob `fab495ac`, 237,489 B, 4,245 diff-relevant region, 6 hunks:
`class AudioMeter.__init__` gains a `block_s` parameter and block-count windowing (the "80 blocks
produced 48 events over 8 s = 6.0 points/s" measurement), `METER_HZ_DEFAULT = 10.0` is restored with
the dated 2026-10-08 reversal note, and `main()` gains `--meter-hz` / `SOTTO_METER_HZ` handling.
The content is dated, measured engineering prose — not truncated or garbage.

### Artefacts on disk (GC-proof — copied out of git)
- `_recovered/stash-1f47e838/` — **all 82 files, 8,120,498 B** (contains binaries: PNGs, `wgc-probe.exe`).
- `_recovered/worker_fab495ac.py` — the recovered worker, 237,489 B, `git hash-object` = `fab495ac…`.
- `_recovered/worker_186c969e_HEAD.py` — the pre-loss HEAD baseline, 232,291 B, kept so the diff is reproducible.

Committed on this lane: `_recovered/worker_fab495ac.py` (text) and this receipt.
**Not committed**, per the binary rule: `_recovered/stash-1f47e838/` (contains PNG and `.exe`).

## RISK THAT REMAINS

`1f47e838` and its 80 sibling files are still **unreachable** in the shared object store. Nothing in
`H:\sotto` references them, so `git gc` on that repo would destroy them. They are safe *as files* now
(because of the copy above) but **not** as git objects. Making them durable in git requires a ref or
a commit, and both mutate `H:\sotto`, which this lane was forbidden to do. **That is the one decision
this receipt cannot make for you.**

## P0 — WHAT'S NEXT

1. **`git gc` in `H:\sotto` will destroy the other 80 stashed files.** The on-disk copy in
   `_recovered/stash-1f47e838/` is currently the only copy. Promote it (copy into `H:\sotto` and
   commit) before any maintenance run.
2. `app/webview/sotto_webview.py` lost 2,323 lines — larger than the file this lane was chartered
   for. Worth its own brief.
3. Do not run `git stash apply` expecting it to work: `refs/stash` is gone (rc=128).

RECOVERY VERDICT: RECOVERED - worker/sotto_worker.py blob fab495ac (237,489 B, +89/-8 vs HEAD, AST_OK)
plus all 82 stashed files (8,120,498 B), extracted from dangling stash commit 1f47e838