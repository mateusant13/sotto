# SCOPE ANSWER: the index IS part of this product -- and it is sitting in QUARANTINE

Written 2026-10-07 16:28:24 -03:00 at HEAD e459a9b.
Search: grep for `SearchIndex|store.py|search.py|upsert_embeddings` across H:\sotto,
EXCLUDING `_moved/`. 25 matches returned; the decisive ones below. POPULATION = the
grep hit count reported by the tool, WINDOW = this turn.

## 1. The index is NOT orphaned -- it has a DECLARED INTERFACE and a CROSS-LANE CONTRACT
`H:\sotto\_main\quarantine-index-collision-20260707\__init__.py:5-6`:
> "store.py   the WRITER: a completed clip, then its ASR `done` -- THE DECLARED INTERFACE
>  search.py  the READ side: FTS5 text search + time / device / duration filters"
>
> :16 "THE CONTRACT WITH THE OTHER LANES, in one paragraph"

A contract "with the other lanes" cannot describe dead code from another project. The
index is a designed component of THIS product.

## 2. But it is in QUARANTINE -- `_main/quarantine-index-collision-20260707/`
That directory holds `__init__.py`, `store.py`, `search.py`, `schema.py` and a
`selftest.py` (510+ lines referencing store.py and search.py). It is named for a
**collision** -- which is the very decision I flagged ~15 turns ago as "my unauthorised
decision, unresolved": `schema.sql` vs `schema.py`.

## 3. The collision already produced a real bug, documented before I arrived
`_main/probe-upsert-verdict.md:55`, quoted:
> "`SearchIndex.search()` hits do **not** carry a top-level `rank` key...
> So `slice_upsert.py:81` (`h['rank']`) is a **real bug** in the merged ..."
> :106 "| committed probe valid? | **NO** -- crashes at `slice_upsert.py:81`,
>         `KeyError: 'rank'`, before any assertion |"

That is a gate refusing to pass a broken probe, with the exact rc-class of failure named.

## 4. What I got wrong, plainly
I spent several turns optimising a latency gate on `src/index/` under the `_moved`
tree, treating it as the product. It is the product's **index**, but it is quarantined,
and the round-trip between clip -> transcript -> FTS search is **not yet wired**. The
panel works; search does not.

## 5. THE OWNER DECISION THIS UNBLOCKS -- named, not taken
`_main/quarantine-index-collision-20260707/` holds a self-contained, self-tested
implementation of writer + reader + schema + selftest. Reinstatement needs ONE call:
`schema.sql` or `schema.py` is canonical, and the other is retired. I have not made
it and I will not -- it is the decision I have escalated for ~15 turns.
