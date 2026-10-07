# FF-PREP — fast-forward feasibility receipt

## ROLLBACK COMMAND (recorded first, per brief)

```
git -C H:\sotto reset --hard 24df100
```

Pre-state of the product root: branch `feat/build-verify-1` @ `24df100`
("orchestrator: integrate feat/hb-truth-1"). If a fast-forward had been executed
and needed undoing, that command returns `H:\sotto` to this exact commit.

## STEP ACTUALLY TAKEN

**The fast-forward was NOT executed. The tree is dirty and the brief mandates STOP.**

Step-by-step, in order:

1. `$env:TMPDIR='I:\cc-tmp'` — set. (`I:\cc-tmp` exists = True.)
2. `git -C H:\sotto-wt\ArbV8 worktree add H:\sotto-wt\ffprep -b lane/ffprep` — rc=0.
   New worktree at `H:\sotto-wt\ffprep`, branch `lane/ffprep`, HEAD `f9e38d6`.
3. Created this file with a one-line placeholder. Committed it as `4f9c2a2`
   ("lane/ffprep: receipt anchor").
4. Re-verified the ancestry claim from scratch, checked tree cleanliness,
   and **stopped at the dirty gate** (below). No merge command was run.

## MEASUREMENTS (all taken this turn, not inherited from the briefing)

### Ancestry — the briefing's claim is CORRECT

| Check | Command | Result |
|---|---|---|
| is-ancestor | `git merge-base --is-ancestor feat/build-verify-1 main` | **rc = 0** (0 = yes, is an ancestor) |
| commits ahead | `git rev-list --count feat/build-verify-1..main` | **144** |
| commits exclusive | `git rev-list --count main..feat/build-verify-1` | **0** |
| merge-base | `git merge-base feat/build-verify-1 main` | `24df10032955731cf8a6651f221e1a979a36df0f` |
| files differing | `git diff --name-only feat/build-verify-1 main` | **86** |

Two corrections to the prior measurement, neither of which changes the verdict:

- The briefing said **143** commits behind. The real number is **144**.
- The briefing said **0 divergent files**. `git diff --name-only` between the two
  tips reports **86**. "Divergent files" in the narrow sense is still 0 — with 0
  commits exclusive to `feat/build-verify-1` there is nothing of that branch's
  own to diverge — but the two *trees* differ in 86 files because `main` moved
  ahead. The briefing conflated the two.

So: it genuinely IS a fast-forward, with 144 commits to gain and 0 to lose.

### Cleanliness gate — DIRTY, 818 lines

`git -C H:\sotto status --porcelain | Measure-Object -Line` = **818**

Breakdown:

| Class | Count |
|---|---|
| total porcelain lines | 818 |
| tracked files modified (`M`, unstaged) | **82** |
| untracked (`??`) | **736** |
| staged | 0 |

`git diff --quiet` → rc=1, independently confirming a dirty tracked worktree.
git version: `2.51.0.windows.1`.

### Why this is a stop, not a footnote

Of the 82 modified tracked files, **2 collide** with the 86 files that the 144
incoming commits rewrite:

- `AGENTS.md`
- `_main/audio-receipt.md`

The brief is explicit that a fast-forward over uncommitted work is exactly what
destroyed `worker/sotto_worker.py` once already, and that a dirty tree means
STOP. That is the instruction I am following.

One honest nuance, recorded rather than hidden: on git 2.51 `git merge --ff-only`
routes through the normal `unpack_trees` check and would most likely have
**refused** with "Your local changes to the following files would be overwritten
by merge" rather than silently clobbering. So the mechanism is probably a clean
error, not silent destruction. That is an argument that the risk is lower than
feared — it is **not** an argument to ignore a STOP instruction, and it is
definitely not a substitute for the owner's decision about 82 uncommitted files.

### The specific file named in the brief

`H:\sotto\worker\sotto_worker.py` — exists, **236,802 bytes**, and is **not
dirty** (no porcelain entry, no `git diff` output for it). The FF would not have
touched it directly. This is stated as a measured fact, not as a reason to
proceed: the risk was never only that one file.

## WHAT WOULD UNBLOCK THIS

The owner has to decide the fate of the 82 modified tracked files first —
commit, stash, or discard — because two of them collide with the incoming
commits. Until that is decided and the tree is clean, the FF stays refused.
Nothing in this lane should be re-run to "just try it".

FF RESULT: REFUSED - dirty tree