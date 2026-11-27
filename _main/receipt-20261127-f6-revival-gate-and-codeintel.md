# RECEIPT — F6: the revival gate as a file, and `codeintel full` on a real population

2026-11-27 · branch `feat/speaker-attribution-20261019` · order: Herdr DM `dm-0d23648ea897a2fb1d16-6`
(lane-gravador, ROLLOUT F6), *"Publique um RECIBO, nao um adjetivo"*.

Every number below was produced by the command printed beside it, in this tree, in this session.

## 1. The revival gap: what was claimed, what was measured

|claim (DM)|measured|verdict|
|---|---|---|
|"sotto: NAO ha entrypoint de gate de revival dentro do repo — `feature_map_sync.py` e `benchmark_history.py` so aparecem como caminhos absolutos externos em `_main/_audit-verify-all.cmd:4799,4805`"|`scripts/gate.py` exists (372 lines, 10 stages: artifact-manifest, feature-map, budgets, angles, friction, revival, sim, tests, pytest, agc, task-resolver) and `scripts/revival_gate.py` did **not** exist|**half REFUTED, half confirmed**|
|"`harness/angulos.tsv` FALTA" (fleet census, `H:/!gravador/tools/f6-preflight.py:85` reads `harness/angulos.tsv`)|`harness/angles.tsv` existed with 33 rows; every in-repo and every skill consumer reads `angles.tsv` (`feature_map_sync.py`, `slider_scorecard.py:426`, `revival_bootstrap.py:172`, `I:/!watcher/scripts/revival_gate.py:20`)|**name mismatch, not a missing matrix**|

Both halves are closed in code, in this commit:

- **`scripts/revival_gate.py`** — one file, four checks (feature map, angle matrix, budgets, goal receipts), rc
  law, and `--neg-arm`.
- **`harness/angulos.tsv`** is a **hard link** to `harness/angles.tsv` (same inode, verified:
  `angles 118fc576c1d5bd32 angulos 118fc576c1d5bd32 same True`, `same inode True`). Two names exist because
  the fleet has two vocabularies; a *copy* would drift, so the gate refuses the moment the bytes differ.
- **`harness/features-functional.json`** — the DECLARED translation between the matrix's vocabulary
  (`caption-pipeline`, `youtube-caption`, `altc-gesture`, `audio-capture`, `history`, `codebase`) and the
  feature map's (`_main`, `app/webview`, ...), plus `uncovered_macro` where every macro feature with no angle
  row carries its reason. A silent omission is refused.

### Both directions, on the real files

```
$ python scripts/revival_gate.py
FEATURE SYNC OK
ANGLES HOLES 5 declared with a named missing population
ANGLES OK (33 rows, cmd/expect/neg present, files exist)
BUDGETS OK (6 metrics with commands)
GOAL OK (5 acceptance criteria carry a verifiable receipt)
REVIVAL GATE PASS                                    rc=0

$ python scripts/revival_gate.py --neg-arm
NEG-ARM control: unmutated copy PASS (rc=0)
NEG-ARM a-row-with-no-command-is-not-coverage: rc=2 marker=True CAUGHT
NEG-ARM an-undeclared-macro-feature-is-a-gap: rc=2 marker=True CAUGHT
NEG-ARM a-hole-that-carries-a-command-is-not-a-hole: rc=2 marker=True CAUGHT
NEG-ARM a-twin-that-drifted-is-not-the-same-matrix: rc=2 marker=True CAUGHT
NEG-ARM 4/4 mutants caught
NEG-ARM: PASS                                        rc=1
```

The control run matters: without it, a temp tree that always fails would make every mutant look caught.
`--root` is what lets the same code judge a copy — the population is an argument, not the cwd (DM trap 1).

### What the matrix itself was hiding (found by the gate, not by reading)

- 4 rows had an **empty `cmd`** and no marker: `audio-capture/A3`, `caption-pipeline/A16` (an exact duplicate
  of row 16), `codebase/A14`, `codebase/A18`, `codebase/A20`, `codebase/A15`. Two were turned into real
  two-direction rows (`config-truth-oracle`, `agents-md-pins-oracle`, `youtube-captions-oracle`), one duplicate
  was deleted, and the rest became `HOLE:` rows that name the missing population.
- The `audio-capture/A3` HOLE note claimed *"CAPTURE_SHARE_DROP has no consumer"* — **false**:
  `worker/capture_share.py:288` logs it and `_main/capture-share-oracle.py:287` reads it. The note now says
  what is actually missing (the 30-minute population), not a reader that exists.
- `codebase/A20`'s note carried a **stale pin** (`429952 B/F9AC..`) while `AGENTS.md` pins `469851 B/84FEE1…`.
  The note no longer copies the numbers; it points at the file that owns them.
- 33 rows, `python`/`node` interpreter present, script file present: **33 rows, 0 problems** (checked by a
  direct audit of every `cmd`/`neg` cell).

`scripts/gate.py` now runs it as a stage:

```
$ python scripts/gate.py --skip ... (revival + sim only)
revival PASS rc=0 1781ms REVIVAL GATE PASS
sim REFUSED rc=2 1250ms child rc=1: 8 substantive code/harness file(s) changed ... without updating `revival/sim.jsonl`
gate REFUSED sim in 3031ms rc=2
```

That refusal is the new stage proving it runs, and the sim gate proving it is fed.

## 2. `codeintel full` — the recipe, with the population printed beside it

The first three attempts **refused**, and each refusal is a measurement of the recipe's precondition in this
repo (DM trap 4: whole tree does not measure):

|command|result|
|---|---|
|`full --scope H:/sotto/scripts --max-population-files 400 --json H:/sotto`|rc 2 `PRODUCER-CEILING`, `population_counts={'scope': 0}` — scope resolved to nothing, so the veto counted the walk|
|`full H:/sotto --scope scripts --max-population-files 400 --json`|rc 2 `PRODUCER-CEILING`, `scope: 0`|
|`full H:/sotto --scope features --max-population-files 5 --json`|rc 2 `SCOPE-POPULATION-EMPTY: scope ['features'] resolved to 2 file(s), 0 auditable; zero population is CANNOT-MEASURE, not clean`|
|`full H:/sotto --scope scripts --json` (no ceiling)|killed at **900 s**, no document; 3 detector caches had written 3 315 031 + 10 390 991 + 210 740 B|
|`full H:/sotto --scope worker --max-population-files 100 --json`|rc 2 `PRODUCER-CEILING`, `scope: 0`|

**The mechanism, measured:** `--max-population-files` is judged against the WHOLE population, not the scope's
slice — so a ceiling smaller than the tree refuses before the scope applies, and a ceiling larger than the tree
lets the detectors run on the scope. The command that measures:

```
$ py -3 -m codeintel full H:/sotto --scope worker --max-population-files 4000 --json
rc=2   82.27 s
population_counts={'outside-scope': 0, 'scope': 319, 'scratch': 0}
findings=319   detectors_measured=17/18   cannot_measure=1
severity: high 138 / medium 97 / info 84
classes: SUPPRESS-BROAD-EXCEPT 100 · DEFAULT-PATH-DRIFT 57 · AMBIGUOUS-PROVENANCE 47 ·
         STALE-UNRESOLVED 47 · DUPLICATED-CONSTANT 38 · DEAD-CONFIG-KEY 31 · RETURN-NONE-EXCEPT 31 ·
         ABSOLUTE-DEFAULT-PATH 29 · INERT-GRADUATION 28 · HALLUCINATED-IMPORT 20 · others 21
```

`exit 2` is the auditing contract, not a crash: findings were found. `outside-scope 0` and `scratch 0` are the
two numbers the scorer refuses on, and both are zero here.

**Scoring: `CANNOT-MEASURE why=no-ground-truth-for-sotto`.** There is no adjudicated truth file for this repo,
and building one from this same run would score the run against itself — the recall number would be circular.
The honest next slice is adjudicating the 319 rows by hand and publishing precision, exactly as `!watcher` did
(94.29 % on 35 adjudicated). That slice is **not** claimed here.

## 3. What is still open (named, not hidden)

- **319 findings unadjudicated** — precision/recall stay `CANNOT-MEASURE` until they are read one by one.
- **5 declared HOLES** in the angle matrix (`audio-capture/A3` 30-min soak, `codebase/A1` end-to-end lane
  launch, `A11` absent-dependency ladders, `A13` restart recovery, `A18` mock-vs-real). Each names its missing
  population in `harness/angles.tsv`; none can pass.
- **`--scope` semantics** are a codeintel repo issue (the ceiling counts the tree, the scope counts the
  slice). Worked around here by printing the population; the fix belongs in `H:/codeintel-worktrees/...`.
- **`revival-gate` is not yet a battery step**: `_main/_audit-verify-all.cmd` was running a full battery during
  this work, so the pair (`:step 0` + `:expectred`) is prepared and will land when the run settles. A driver
  stage in `scripts/gate.py` exists today.
