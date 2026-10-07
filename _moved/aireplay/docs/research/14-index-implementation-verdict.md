# 14 — Which `_moved/aireplay/src/index/` implementation belongs in `main`?

**STATUS: STUB — IN PROGRESS.** Committed first so no work is lost if this lane aborts.

Two implementations collided in `H:\sotto\_moved\aireplay\src\index/`:

- **(A) merged** — branch `feat/index-impl`, merge `0e16d16`: `schema.sql`, `store.py`, `search.py`, `_index-green-probe.py`
- **(B) quarantined** — `H:\sotto\_main\quarantine-index-collision-20260707\`: `schema.py`, `__init__.py`, `selftest.py`, `store.py`, `search.py`

Verdict and criteria table: PENDING.

## Lane v3 status (in progress)

WIP marker committed first. READ so far: both file sets enumerated; `index-final.json`
census says it came from probe `_index-final-probe.py` against db
`H:\aireplay\_main\_index-final\store.db` — a DIFFERENT probe and a different tree
from the merged `_index-green-probe.py` in `H:\sotto`. Provenance check in progress.

## Method rules

- Read-only except this file. No moves, no deletes, no `src/index/` edits.
- <=2 threads.
- Every claim tagged MEASURED (command/rc), READ (file:line), or UNKNOWN.