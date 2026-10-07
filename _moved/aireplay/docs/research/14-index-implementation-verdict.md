# 14 — Which `_moved/aireplay/src/index/` implementation belongs in `main`?

**STATUS: STUB — IN PROGRESS.** Committed first so no work is lost if this lane aborts.

Two implementations collided in `H:\sotto\_moved\aireplay\src\index/`:

- **(A) merged** — branch `feat/index-impl`, merge `0e16d16`: `schema.sql`, `store.py`, `search.py`, `_index-green-probe.py`
- **(B) quarantined** — `H:\sotto\_main\quarantine-index-collision-20260707\`: `schema.py`, `__init__.py`, `selftest.py`, `store.py`, `search.py`

Verdict and criteria table: PENDING.

## Method rules

- Read-only except this file. No moves, no deletes, no `src/index/` edits.
- <=2 threads.
- Every claim tagged MEASURED (command/rc), READ (file:line), or UNKNOWN.