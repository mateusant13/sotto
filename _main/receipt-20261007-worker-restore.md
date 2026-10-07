# Sotto receipt — worker restored after an uncommitted deletion

Owner directive (verbatim): 'trabalha só no sotto. nao mais no maanger ou omp.'

## What was wrong
`worker/sotto_worker.py` was DELETED in the worktree while still tracked at HEAD — the largest
single deletion in the repo (`git diff --stat HEAD`: 17 files changed, 1743 insertions(+), 2761
deletions(-); the worker alone was 2580 lines). It is the ONLY engine: `AGENTS.md:101` states the
batch model (Parakeet Redux) is NOT on disk, so nothing replaced it.

## The lost version is NOT recoverable — say it plainly
* deleted worktree file: **149 856 B**, proved from the pyc header
  (`worker/__pycache__/sotto_worker.cpython-311.pyc`, PEP 552 flags=0: src_size at byte 12 =
  149856, src_mtime at byte 8 = 1791294701).
* `git fsck --lost-found --no-progress` → **no dangling objects** (rc=0). The 149 856 B version was
  never staged, so it is gone. `git checkout` would NOT bring it back.

## What was restored, and why THAT one
| candidate | bytes | sha256 (16) | has the documented fixes? |
|---|---|---|---|
| HEAD:worker/sotto_worker.py | 127 023 | ffe3b62fce7660ef | yes |
| `_main/_ordem-before/sotto_worker.py` | 128 569 | 85923bc4aa06da0c | yes |

Both survivors carry every fix AGENTS.md documents as RESOLVED — measured by token count on both:
`silent-device` ×8, `ran_but_silent` ×6, `all-candidate-taps-flat` ×3, `use_vad` ×10, `blank_id` ×1.
`_ordem-before` was chosen because it is the LATER revision (mtime 2026-10-06T13:12:27Z, 2605 lines
vs HEAD's 2581, 35 insertions / 11 deletions apart) and is larger, hence nearer the lost 149 856 B.

## Evidence
* `copy _main/_ordem-before/sotto_worker.py -> worker/sotto_worker.py`
* after: 128 569 B, sha256 `85923bc4aa06da0c` — **byte-identical** to the source.
* `python -m py_compile worker/sotto_worker.py` -> **rc=0, clean**.
* `git status --porcelain -- worker/sotto_worker.py` -> **`M worker/sotto_worker.py`**.
  This is the point: the file is MODIFIED, not DELETED, so the next `git checkout` cannot silently
  revert it and the app has an engine again.
* `git diff --stat` vs HEAD: `46 +++---, 35 insertions(+), 11 deletions(-)`.

## What remains open (owner's call, not taken)
* the 149 856 B revision is lost; only 128 569 B is recovered.
* `H:/sotto` is **ahead 4** of origin/main with 11 tracked files modified. Nothing committed here.
* the app is NOT running (no electron/sotto process on the box at the time of this work).

## Revert
`git checkout -- worker/sotto_worker.py` restores HEAD's 127 023 B version. Nothing else was touched.