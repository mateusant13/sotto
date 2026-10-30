# Bend 2 in Sotto — reference bundle

Ported 2026-10-29 from `consultgpt` (owner order, same day). Byte-identical copies.

| file | sha256 |
|---|---|
| `BEND_PROOFS_REFERENCE.md` | `f27cfadfa77edd63fe3e97f12396cf49faa30f5d967c2ef7460f26632f480949` |
| `BEND_LAW_GUIDE.md` | `7f50a5fc627c5db1dfaf982addd02d980e8043cc685f4f342654533027ae212d` |
| `BEND2_SOURCE_AUDIT_2026-10-28.md` | `c893dbf37023ccb5f18d5381ea0e940fd2a31d65901abcf4a33ee48f0b4a018a` |
| `BEND_VERIFICATION.md` | `73fa58dd13129752b308219e0a7a021797ef09fb25636e806169a52aa8037898` |
| `EVOLUTION_TOOLCHAIN.md` | `3f5ed4d0e35d46a8295995bdfca61182344aef20c0c6c1e5df3dd06ca7714be3` |

Read `BEND_PROOFS_REFERENCE.md` first (contract, syntax, six-check gate, F-6/F-6b traps),
then `BEND_LAW_GUIDE.md` (the five law-writing rules and the E11.5 worked example).

## The contract, once

Human writes `LAWS.bend` (claims only, one `law` each). Agent writes `PROOF.bend`
(`import LAWS.bend as Laws`, one `def Laws.<law>` per claim, plus refutation helpers). **The gate
is `bend PROOF.bend --verdict`** in WSL `ubuntu-bend`; `--check-only` proves nothing and is never
a gate. Every law ships a **negative control that must fail** and names the law it falsifies. A
law proves the *pure model*; a `tests/` mirror binds it to the **real production function**, and
the mirror must go RED when the fix is neutralised. Name the production input that reaches the
law (F-6) or do not ship it as evidence.

## Sotto's goal, as the owner stated it (2026-10-29)

*"make youtube subtitles appear on my screen on sotto app, and synced, almost 1:1 with youtube."*

That is **two different artifacts**, and conflating them is how the last false green happened:

- **"appear"** is an *ordering* property of a pure decision — which producer's line may be
  painted, and when. Provable with a law.
- **"synced, almost 1:1"** is a *budget* — a measured wall-clock drift against YouTube's own
  caption timeline. **No Bend law can prove a budget** (`BEND_LAW_GUIDE.md` §"What a proof
  CANNOT show", item e). It needs a falsifier that runs the real app path and prints
  `drift_ms` per cue against a reference timeline; the law underneath proves only the ordering.

## Where the laws attach (paths verified on disk 2026-10-29)

The caption pipeline moved out of `app/electron/` into **`app/panel/`** — several older agent
declarations still cite `app/electron/*`, which no longer exists:

- `app/panel/caption-formulation.js` — `words`, `agreedPrefixLength`, `healSeams`, `formulate`,
  `formulateTokens`, `describeReadiness`, `createEngine`. The decision surface.
- `app/panel/history-source.js` — `producerOf`, `isCanonicalLine`: which producer may write the
  canonical transcript.
- `app/panel/panel.js` — `recordHistory` choke point; the paint path.
- `app/panel/caption-float.js`, `app/panel/caption.html` — the on-screen caption surface.
- `worker/sotto_worker.py` — `StreamAsr.run_chunk`, the RNN-T predictor carry across chunks.
- `_main/youtube-paint-first-oracle.py` — existing instrument: caption appears WITH the page,
  with a real `--neg-arm` mutant. Start the sync falsifier from this shape.
- `_main/route-stamp-gate.js`, `_main/complaints-closure-gate.py` — existing gates.

## Seed laws — claims to write first (one file each)

1. **`paint_requires_an_accepted_route`.** `paintable(meta) == true → routeOf(meta) ∈ ACCEPTED`.
   Mirror: `app/panel/caption-formulation.js` + `panel.js` `recordHistory`; neutralise the route
   guard and the same grid must violate it. Negative control: a line with `route=final` from the
   live streaming engine must be rejected.
2. **`history_never_takes_the_stream_source`.** `isCanonicalLine(meta) == true → producerOf(meta)
   ≠ live-streaming-engine`. This is the live-vs-history separation as a law, not a comment.
3. **`a_later_cue_never_paints_earlier`.** Given non-decreasing input timestamps, the emitted
   paint order is non-decreasing: `t_i ≤ t_j → paintIndex(i) ≤ paintIndex(j)`. Provable on the
   pure komposition in `caption-formulation.js`; the mirror drives `formulateTokens` with the
   real chunk grid.
4. **`repeating_a_cue_does_not_advance_the_display`.** Idempotence **paired with a REJECTS
   clause** (`cancel_idempotent` + `cancels_queued` / `preserves_finished` upstream): a no-op
   must be unable to pass. Negative control: a "consume and drop" implementation (paints once,
   then always reports the same index) must FAIL this law.
5. **`healSeams_never_invents_text`.** The repaired line is over the union of observed words:
   no token appears that no observed chunk contained. Kills the whole class of "the caption got
   smoother because it made words up".

## Falsifier to write for the budget half (not a law)

A single script, one entrypoint, typed exits, arms: cold page → first caption, live stream →
rolling caption, and a **drift arm** comparing painted cue time against a reference timeline
(`painted_at_ms − cue_at_ms`), with a `--neg-arm` that delays the paint by design and must go
RED. Publish `drift_ms` per arm; never publish a boolean `synced`.

## Toolchain

`wsl -d ubuntu-bend -e bash -lc 'bend version'` → 2.0.39 (latest release). `--verdict` needs
Lean ≥ 4.34.0 (`~/.elan/bin/lean`). Explicit PATH on every call (F-4). Alpine cannot run Lean.

## What LANDED on 2026-10-29 (the YouTube 1:1 path)

The seed laws below describe the **panel** caption path (`app/panel/`). The owner's 2026-10-29
order was about the **YouTube** path, and that is the bundle that was written first:

| file | what it is |
|---|---|
| `bend_core/LAWS.bend` | 11 laws over the pure model of the 1:1 decisions (reveal count, line liveness, window size) + the model they need |
| `bend_core/PROOF.bend` | one `def Laws.<law>` per law, plus the refutation helpers |
| `bend_core/NEGATIVE_*.bend` | 11 controls, one FALSE claim each, each naming the law it falsifies |
| `bend_core/model.py` | the same model in Python for a host without Bend — a SAMPLE, not a proof, and it says so |
| `_main/bend-laws-gate.py` | the gate: `bend PROOF.bend --verdict` in WSL, with six typed exit codes, the pinned law inventory, the control set, and two tamper probes |

```
wsl -d ubuntu-bend -e bash -lc 'export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; cd /mnt/h/sotto/bend_core && bend PROOF.bend --verdict'
```

The gate the battery calls is `python _main/bend-laws-gate.py` (rc 0 = green, 2 = a law failed,
3 = a control misbehaved, 4 = infrastructure, 5 = inventory drift, 6 = a tamper probe misbehaved).
Receipt: `_main/receipt-20261029-youtube-1to1-laws-and-drift.md`.

**The budget half is NOT a law.** The timing is measured by `_main/youtube-drift-oracle.py`, which
prints `drift_ms` per row against YouTube's own payload timeline, and whose `--neg-arm` injects
+250 ms and must go RED. There is no boolean "synced" anywhere.

**The seed laws above are still open.** They concern the panel path, and the bundle that landed
concerns the YouTube path; the two are complementary, not substitutes.

