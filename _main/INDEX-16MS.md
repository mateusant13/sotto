# Index 16 ms budget — receipt

Lane: lane/idx16. Worktree `H:\sotto-wt\idx16`. TMPDIR=I:\cc-tmp. Threads<=2.
All runs 2026-10-07, WINDOW 16:35–16:50 -03:00.

## A. Is the budget real? NOT DECIDABLE BY POPULATION — and 16 ms is a misquote

The 211 200 population is **arithmetic, not observation**.
`04-index-search.md:852` row 6 flags its own basis:
> "the 60 %/16 % split is `research 07 §6`'s ASSUMPTION, not a measurement"

and `:874` / `:1013`:
> "the owner's real library is **0 scanned** so far" · "144 MB / 1000 videos is arithmetic"

So **POPULATION of observed product clips = 0.** Neither 20 000 nor 211 200 is a
measured product load; 211 200 = "1000 clips x 10 min" (`:852`).

**The 16 ms figure is not the budget at that population.** The budget table
`:673` reads: *"vector scan, k=100, 211 200 vectors (three channels) — budget
**<= 25 ms** — MEASURED 15.99 ms min / 20.3 ms median (13.5 GB/s)"*. 16 ms is the
spec's own measured *value* (`:33-34`, `:987` "exact is 16 ms"), not its budget.

**Latency measurement is currently CONTAMINATED and cannot be reproduced here.**
My own run, `slice_scale_probe.py 20000 100`, **rc=0**:
`p50=47.82ms p95=105.18ms 0.0% under 16ms` — ~9x the quoted 5.34 ms. Cause, measured
not guessed: CPU **100%**, 10 concurrent `python.exe`, **PID 19996 = lane
`gatecheck` running `slice_scale_probe.py 211200 100 4096`** (started 16:35:49,
still live, 214 MB) plus `audiofix` ASR and `cap2panel` probes. My 20 000 figure
is NOT evidence against the 5.34 ms figure.

## B. Is the optimisation real? YES — a real, unexploited 3x

`search.py:101-106` loops the 3 channels of `VECTOR_CHANNELS` (`:33`) and calls
`knn()` per channel; `knn()` runs the **full** `sims = self.vecs @ q`
(`search.py:68`) **every time**. At 211 200 x 256 fp32 that is 3 x 206.2 MiB =
618.6 MiB scanned per query instead of 206.2 MiB. `sims` is channel-independent;
only `mask` is. Hoisting line 68 out of the channel loop is a **3x reduction,
bit-identical output**. This needs no schema decision.

**But the probes do not load the quarantined build**:
`slice_scale_probe.py:33-36` inserts `<root>/src/index` =
`H:\sotto\_moved\aireplay\src\index`.

| | quarantine | `_moved` (what probes load) |
|---|---|---|
| schema | `schema.py` (inlined DDL, `SCHEMA_VERSION=1` @`:41`) | `schema.sql` |
| load site | `store.py:79` `from .schema import ...` | `store.py:25` `SCHEMA_PATH = ...with_name("schema.sql")` |

store.py 17284 B vs 14746 B. **Any optimisation in the quarantine is unmeasured.**

## C. KeyError 'rank' — REFUTED as stated; real defect is different

| run | rc | result |
|---|---|---|
| `slice_upsert.py` | **0** | `RESULT: PASS` |
| `probe-from-main.py` | **1** | `ModuleNotFoundError: No module named 'store'` @`:26` |
| quarantine `selftest.py` | **1** | `ModuleNotFoundError: No module named 'index'` @`:47` |

`slice_upsert.py:81` reads `h['seg_id']`; `rank` is the `enumerate` variable. The
only real `h['rank']` is `_main/probe-from-main.py:81`. The verdict doc's own
`:94-96` says HEAD's `slice_upsert.py` *had* it at 13:42:21 and was later
rewritten. Historically real, currently unreproducible.

## D. Collision NOT resolved — facts only

Live blocker is the pair of ModuleNotFound errors, not `KeyError`. The quarantine
cannot self-test as named (`selftest.py:45` requires the package be called
`index`). Owner's call.