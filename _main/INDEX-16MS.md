# Index 16 ms budget — receipt

Lane: lane/idx16. Worktree H:\sotto-wt\idx16. TMPDIR=I:\cc-tmp.

## C. KeyError: 'rank' — REFUTED as stated; real defect is different

The verdict doc (`_main/probe-upsert-verdict.md:55`) blames `slice_upsert.py:81`.
Measured, 2026-10-07, threads<=2, TMPDIR=I:\cc-tmp:

| run | rc | result |
|---|---|---|
| `python _moved/aireplay/_main/slice_upsert.py` | **0** | `RESULT: PASS`, reaches idempotency block |
| `python _main/probe-from-main.py` | **1** | `ModuleNotFoundError: No module named 'store'` at **:26** |
| `python _main/quarantine-index-collision-20260707/selftest.py --help` | **1** | `ModuleNotFoundError: No module named 'index'` at **:47** |

`slice_upsert.py:81` reads `h['seg_id']`, NOT `h['rank']`; `rank` is the
`enumerate` variable. Real `h['rank']` lives at `_main/probe-from-main.py:81`
(sole non-vendored hit repo-wide). The verdict doc's own :94-96 explains the
history: HEAD's `slice_upsert.py` carried `h['rank']` at 13:42:21 and has since
been rewritten. **The doc describes a real past bug, correctly, against a file
that no longer contains it.** The parked buggy copy cannot even reach line 81.

Net: the bug is HISTORICALLY REAL, CURRENTLY NOT REPRODUCIBLE. The live blocker
is the ModuleNotFound pair above, not `KeyError: 'rank'`.

## B. Is the optimisation real? Two codebases, two canonical schemas

The probes do NOT load the quarantined implementation:
`_moved/aireplay/_main/slice_scale_probe.py:33-36` inserts
`<root>/src/index` = `H:\sotto\_moved\aireplay\src\index`.

| | quarantine | `_moved` tree (what probes load) |
|---|---|---|
| schema | `schema.py` (inlined DDL, `SCHEMA_VERSION=1` @:41) | `schema.sql` |
| load site | `store.py:79` `from .schema import FTS_TABLE, transaction` | `store.py:25` `SCHEMA_PATH = Path(__file__).with_name("schema.sql")` |
| store.py | 17284 B | 14746 B |
| selftest runnable | **NO** (needs pkg named `index`) | n/a |

So the 211200 measurement characterises the **schema.sql** build. Any
optimisation sitting in the quarantine's `schema.py` build is **unmeasured**.