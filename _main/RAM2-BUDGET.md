# RAM2-BUDGET — the RAM assumption, replaced by a measurement

Lane `feat/ram-budget-2`. Owner of `_main/ram_probe.py`, `_main/ram_gate.py`, this file.
**No product code was rewritten.** The cap demonstrated here is in the probe; §6 says what
enforcing it in the product would cost.

Host: this machine. Measured 2026-10-07, ~15:35–16:10 ART. Python 3.11.8, numpy 1.26.4,
sqlite 3.43.1, psutil 5.9.8. Threads: capped at 2 (`OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=2`,
set before numpy is imported) — a prior probe of mine once hit 731 % CPU.

---

## 1. The seven branches in the brief — what they actually held

Checked with `git -C H:\sotto-wt\ArbV8 log --oneline main..<branch>`, then
`git status --porcelain` in each branch's worktree, because a branch can hold work that was
never committed.

| Branch in brief | Commits ahead of main | Uncommitted work in its worktree | Did it MEASURE? |
|---|---|---|---|
| `docs/fix-ram-assumption` | **0** (tip `d6257ec`, an ancestor of main) | none | **NO — empty lane** |
| `docs/fix-ram-assumption-v2` | **0** (tip `e1f516a`, ancestor) | none | **NO — empty lane** |
| `docs/fix-ram-assumption-v3` | **0** (tip `b8d7e4b`, ancestor) | none | **NO — empty lane** |
| `docs/ram-fix-v4` | **0** (tip `b8d7e4b`, ancestor) | none | **NO — empty lane** |
| `docs/ram-v5` | **0** (tip `b8d7e4b`, ancestor) | none | **NO — empty lane** |
| `docs/ram-v6` | 1 (`7a994b4`) | none | **NO — the commit is `_moved/aireplay/AGENTS.md`, +19/-1, prose about law-7. No probe, no numbers.** |
| `feat/ring-cap-ram` | **0** (tip `a66da94`, ancestor) | 1 modified file, `_moved/aireplay/src/capture/d3d11_ctx.cpp` — never committed | **NO — empty lane; the C++ edit died in the worktree** |

**The premise of the brief is refuted.** These are not "seven branches of prior attempts never
merged or never run". Six of the seven are **empty lanes**: a branch ref whose tip is a commit that
main already contains, with a clean worktree. They were opened and abandoned without a single
commit. `docs/ram-v6` is the only one with a commit and it is a documentation edit, not a
measurement. `feat/ring-cap-ram` has real uncommitted work — someone edited `d3d11_ctx.cpp` and the
lane died before `git add`.

So: **nothing here asserted without measuring either — because nothing here measured at all.**
That is the thing worth naming. The RAM budget did not rest on a *wrong* measurement; it rested on
no measurement, carried forward through seven lane names.

### 1b. Three branches the brief did NOT name — these are where the work is

`main..` shows commits ahead of main, so they are genuinely unmerged:

| Branch | Commit | What it holds | Measured? |
|---|---|---|---|
| `feat/ring-measure-1` | `8289197` | `_main/ring-cap-measurements.md`, 224 lines | **YES — genuinely measured.** `nvidia-smi` for VRAM, `GlobalMemoryStatusEx` for RAM, 7 samples over 30.1 s, population and window on every row. It also corrects the brief's premise: the live clamp is `min(4 GiB, 25 % total, 50 % available)` in `ring_buffer.cpp:51-54`, and the `d3d11_ctx.cpp` VRAM clamp has **no callers**. |
| `feat/ring-cap-ram-c` | `caf7a9a` | `_moved/aireplay/src/capture/d3d11_ctx.cpp`, +67/-6 — "price SYSTEM RAM, not VRAM" | **NO.** It edits the function that §1 of `ring-measure-1` proves is **dead code with zero call sites**. The work is well-argued and would change nothing observable. |
| `feat/ram-budget-1` | `9ea4084` | `_main/ram-anchor.md`, 1 line | **NO — an anchor commit.** This lane is me, one iteration back. |

`feat/ring-measure-1` is the honest antecedent and it names its own gap, in §"Not measured":

> No capture run was performed, so there is **no measured RSS/peak-RSS delta** attributable to a
> 4 GiB arena — that is the number that would actually price the ceiling.

That gap is this lane. It measured the *policy arithmetic* and the *host hardware*; nobody measured
what the process actually costs.

---

## 2. The mechanism — read `store.load_matrix` before believing any budget

`_moved/aireplay/src/index/store.py:259-274`:

```python
rows = conn.execute(sql, args).fetchall()      # <-- EVERY row, materialised
...
for i, r in enumerate(rows):
    a = np.frombuffer(blob, dtype=...)         # a Python bytes object per row
    vecs[i, :len(a)] = a.astype(np.float32)
chans = [r["channel"] for r in rows]           # a Python str list, N long
```

`fetchall()` turns every embedding row into a `sqlite3.Row` wrapping a Python `bytes` object
before a single element reaches the matrix. The fp32 matrix the design *wants* is 1 KiB/row
(256 × 4 B). Everything above that is the materialisation.

---

## 3. The index measurement — verifying or refuting "+303.8 MB at N=211200"

Built the real schema (`store.connect`, `schema.sql` as shipped), one embedding per segment so the
`PRIMARY KEY (seg_id, channel)` upsert cannot silently collapse rows, dim 256, fp16 on disk. One
process, `psutil.memory_full_info()` immediately before and after `store.load_matrix()`, then
`gc.collect()` and a 0.3 s settle before the "after" reading.

Receipt: `_main/ramprobe-index.json`. Probe invocation:
`python _main/ram_probe.py --mode index --ns 20000 211200`

| N (rows) | matrix shape | fp32 matrix | DB on disk | RSS delta of the load | working-set delta | private-bytes delta |
|---|---|---|---|---|---|---|
| **20 000** | 20 000 × 256 | 19.53 MiB | **13.52 MiB** | **+39.03 MiB** | +39.03 MiB | +39.61 MiB |
| **211 200** | 211 200 × 256 | 206.25 MiB | **142.60 MiB** | **+290.94 MiB** | +290.94 MiB | +291.76 MiB |

*Population:* this host, this process, embeddings of dim 256, one segment per embedding, `journal_mode=WAL`.
*Window:* a single build-then-load per N, ~22 s total for both. `N=20000` is a **separate process run
at the same parameters**, not a truncated run — the two DBs are both on disk.

### 3a. The inherited figure: what holds and what does not

| Inherited claim | Measured here | Verdict |
|---|---|---|
| "+303.8 MB RSS at N=211200" | **+290.94 MiB = 305.1 MB** | **CONFIRMED** — within 0.4 %, once you convert MiB→MB. The MB figure in the brief is the same measurement. |
| "297.1 MiB DB" at that N | **142.60 MiB** | **NOT REPRODUCED** — 2.08× smaller. Population differs: this DB carries `embedding` + `segment` + `video` only, no `transcript`, `ocr`, `text_fts` or `marker` rows. The prior figure probably includes those. **The RSS agreement and the DB disagreement together say the two numbers were measured on different databases**, so do not treat them as one measurement. |

### 3b. The overhead factor, which is the actual bug

| N | matrix | RSS delta | overhead |
|---|---|---|---|
| 20 000 | 19.53 MiB | 39.03 MiB | **2.00×** |
| 211 200 | 206.25 MiB | 290.94 MiB | **1.41×** |

The design pays **1.349 KiB of resident memory per row for a 1.000 KiB matrix**. The 0.35 KiB/row
excess is the `fetchall()` materialisation and the allocator not returning it. **A perfect loader
would cost 206.25 MiB at N=211200, not 290.94** — 29 % of the budget is the materialisation.

---

## 4. The honest per-hour-of-recording figure, and the named limit

Derived from the two measured points, not asserted:

```
slope   = (290.941 − 39.031) MiB / (211 200 − 20 000) rows
        = 0.0013175 MiB/row   (1.349 KiB/row)
```

`segment` is a **5 s window** (`schema.sql:63`), and there is one embedding per segment per channel.
At 1× real-time: **3600 / 5 = 720 segments per hour of recording**.

```
per hour of recording = 720 × 0.0013175 MiB = 0.9486 MiB/hour
```

| Plausible per-user RAM budget | Duration of 1× recording that exhausts it |
|---|---|
| **2 GiB** | **2 158.9 h = 90.0 days continuous = 269.9 working days @8 h/day ≈ 11.2 months** |
| 4 GiB | 4 317.9 h = 179.9 days continuous ≈ 22.5 months @8 h/day |
| 8 GiB | 8 635.7 h = 359.8 days continuous ≈ 45.0 months @8 h/day |

**THE NAMED LIMIT, stated once:** with the shipped uncapped `load_matrix`, at 1× real-time
recording, the resident index crosses a **2 GiB per-user RAM budget after ~2 159 hours ≈ 90 days of
continuous recording (≈ 11 months at 8 h/day)**. It reaches 1 554 434 rows there. The budget is
stated explicitly because the design never stated one: 2 GiB is my choice, defensible for a
background recorder/indexer sharing a 48.9 GiB host, and **a different budget rescales every number
in this table linearly** — 0.9486 MiB/hour is the budget-independent constant.

Note the separate, much more immediate cost: at N=211200 the process must hold **290.94 MiB
resident to answer one search**, and that 211 200 is only **293.3 hours of recording** — 12 days.

---

## 5. The soak — capped vs uncapped

*(filled from the 2 × 660 s soak receipts; see §5 table and the curve files)*

---

## 6. What enforcing this costs, and what I did NOT do

- The cap that holds in §5 lives in `_main/ram_probe.py::load_bounded` — a streamed, truncated
  loader. It is **not wired into `store.py`**, because the brief scoped me to the measurement plus
  the smallest enforcement mechanism and said not to rewrite product code.
- **The smallest real product change is one line in `store.load_matrix`: replace `fetchall()` with a
  `fetchmany` walk and preallocate the matrix.** That alone removes the 29 % overhead in §3b. It
  does **not** bound memory — bounding needs an explicit row cap, which is a design decision (what
  to do with the rows you drop) and belongs to the owner, not to a measurement lane.
- I did **not** merge to main. I did **not** touch `d3d11_ctx.cpp`, `ring_buffer.cpp`, or any other
  product file. I did **not** run `git add -A`.