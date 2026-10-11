# Canonical producer: the T3 answer, my verification, and the decision I own (2026-10-11)

## What T3 measured, and what I re-measured myself

The T3 lane delivered `_main/canonical-producer-oracle.py` and `_main/receipt-20261011-canonical-producer.md`.
I verified both pins and then RAN THE ORACLE MYSELF, both colours, in-process via `spawnSync("py", ...)`
with `windowsHide:true` (no launch of the app, the shell or the worker; the owner stop order holds):

| artefact | claimed | I measured |
|---|---|---|
| `_main/canonical-producer-oracle.py` | 37 969 B, sha256 `3EE12D05…F743844A` | **MATCH** |
| `_main/receipt-20261011-canonical-producer.md` | 38 382 B, sha256 `1B1B2129…4B830BD9` | **MATCH** |
| GREEN arm | `45/45`, `VERDICT: PASS`, rc=0 | **`SUMMARY: 45/45 checks green; failed=[]` / `VERDICT: PASS` / rc=0** |
| RED arm (`--red-arm`) | `9 of 37` fail, rc=1 | **`RED-ARM SUMMARY: 9 of 37 checks FAILED against the mutant subject` / `VERDICT: FAIL` / rc=1** |

So the oracle can say NO, and its GREEN is not a gate that feeds itself: the same checks run against
mutants of the real bytes (gate renamed / worker stamp removed / shell projection cut) and 9 of them move.

**The answer is PARTIALLY, and the split matters.** In CODE, end to end: **YES, now measured** — the real
`_run_runner` queues a real `type:"caption"` event stamped `producer:"redux"`, the real shell forwards every
key but `type`/`text` as meta, the real engine REBUILDS that meta and carries the tag, and the real gate
accepts it. In a LIVE RUN: **NO** — the only stamping arm is the Redux batch switch, its default is OFF, and
**the checkpoint is not on disk**: `worker/models/` holds exactly one directory
(`nemotron-3.5-asr-streaming-0.6b-int8`), so `redux_batch.py` cannot load and the worker queues a
`redux-batch-empty` status instead of a caption.

## THE DECISION (mine, per the owner's *"toma todas as decisoes voce mesmo"*)

The owner fork was: **(i)** keep the literal `redux`, or **(ii)** rename the tag to `canonical-tdt` across
`history-source.js` + `panel.js` + the worker + `redux_batch.py` + the oracle in ONE edit.

**DECIDED: (i) KEEP THE LITERAL.** Three reasons, in order of weight:

1. **A rename would strand the archive.** Every canonical line already written carries
   `producer:"redux"`. The gate is fail-closed, so after a rename those stored lines stop being canonical
   and the owner's "History · Redux" half silently empties — a data-visible regression bought for naming
   purity. The UI label (`panel.html:109`) would also have to change in the same edit or the panel and the
   store would disagree.
2. **The tag names the shipped ARTEFACT, and that artefact is what the label says.** `moondream/parakeet-redux`
   is the finisher this repo ships and the one the guard is written for; `redux_batch.py`'s own docstring
   records that it is a ternary re-quant of `nvidia/parakeet-tdt-0.6b-v3`, which makes `redux` the packaging
   name and `tdt` the architecture name — both true, neither a lie.
3. **The risk the rename guards against is not reachable today.** The arm is OFF by default and its
   checkpoint is absent, so no non-Redux engine can write a line. A rename now would be preparation for a
   hypothetical at a real cost.

**The standing condition this decision carries:** the day the finisher is swapped for an engine that is NOT
the Redux package, the tag MUST be renamed in the ONE edit the T3 lane already mapped (`history-source.js:51`,
`panel.js`, `sotto_worker.py`'s `REDUX_PRODUCER`, `redux_batch.py`, the oracle) **together with a migration
for the stored lines**, or the guard becomes a lie. That is now a documented trigger, not an open question.

## The gap that remains, and it is not this one

The reason the canonical half is decorative today is the **absent checkpoint**, and a sibling lane is fixing
the adjacent hazard the T3 lane found: the switch arms on the RUNNER FILE while the weights are gone, so
`--redux-when-hidden` with no checkpoint would cut streaming while hidden and fail every batch — panel closed
and nothing transcribed. That fix (arm on the weights, refuse loudly when they are missing) is in flight;
restoring the checkpoint itself is a download, not a code change, and is NOT done here.

## NOT MEASURED

- No live run: no worker-stamped caption was ever observed on real stdout, and the batch commit was forced
  by the engine's own `flush('hold-timeout')` in-process.
- Whether the batch engine, once its weights are restored, would produce lines the gate accepts — that needs
  the download plus a real run, both outside the stop order.
