# `codeintel full` receipt — sotto

## Lane, tree and base

- Lane: `RolloutSotto`
- Worktree: `G:/Temp/wt/RolloutSotto-20261128T012202Z`
- Branch: `lane/RolloutSotto-20261128T012202Z`
- HEAD measured: `91fae2c44c0e7c62e833a5cf3c8ebbac3fd953be` — `fix(audit): delete a wall metric that could not measure, and stop sampling the box twice`
- The assignment named HEAD `6e65c1f`; the repository had advanced three commits by measurement time. Every number below was observed on the HEAD above, not on `6e65c1f`.

## Pin proof (`file:line` from tracked `AGENTS.md`)

Command:

```
git -C G:/Temp/wt/RolloutSotto-20261128T012202Z show HEAD:AGENTS.md | grep -n -m 3 'project-revival.*4\.6\.0'
```

Output:

```
1302:**Skill pinado: `project-revival` v4.6.0** (`C:/Users/Administrador/.agents/skills/project-revival/SKILL.md`
```

Continuation (same tracked file):

```
1303:declara `version: "4.6.0"`, medido 2026-11-27). As quatro etapas de revival deste repo vivem em
```

Independent confirmation of the installed skill: `C:/Users/Administrador/.agents/skills/project-revival/SKILL.md:5` is `  version: "4.6.0"`.

## Sotto's own gate — run once

Exact command (single run; `SOTTO_RUNTIME` points at this lane's tree so no rail writes into the shared checkout):

```
SOTTO_RUNTIME='G:/Temp/wt/RolloutSotto-20261128T012202Z' 'H:/Python311/python.exe' -m watcher run --cpu 4 --single RolloutSottoGate --io very-low --timeout 240 --cwd 'G:/Temp/wt/RolloutSotto-20261128T012202Z' -- 'H:/Python311/python.exe' scripts/gate.py
```

Wrapper result: `GATE_WRAPPER_RC=2`, reported total `30.9s` (startup `0.7s`, wait `29.9s`, wrapper cpu `0.80s`). Stage lines, verbatim:

```
artifact-manifest PASS rc=0 297ms session-cache               90.6 KiB        1      1  OK        0.25 GiB  [tracked]
feature-map PASS rc=0 2922ms "verdict": "PASS",
budgets PASS rc=0 7109ms basic.yt_capture_replay_ms VERDICT: PASS | e2e.yt_paint_worst_ms VERDICT: PASS | subsystem.undefined_names_scan_ms {"files": 20, "undefined": 0, "undefined_files": 0, "verdict": "GREEN"}
angles PASS rc=0 844ms A3-steady-state-decay cmd=0 neg=1: H:\Python311\python.exe _main/product-soak-oracle.py --fixture
friction REFUSED rc=2 18329ms child rc=1: }
gate REFUSED friction in 29532ms rc=2
```

The driver stops at the first refusal, so `revival`, `sim`, `pytest`, `agc` and `task-resolver` were not reached in this run.

## `codeintel full` — whole main source tree (`--scope _main`)

Exact command (600 s declared ceiling, installed codeintel worktree as cwd):

```
'H:/Python311/python.exe' -m watcher run --cpu 4 --single RolloutSottoFull --io very-low --timeout 600 --cwd 'H:/codeintel-worktrees/triad-milestones-20261105' -- 'H:/Python311/python.exe' -m codeintel full 'G:/Temp/wt/RolloutSotto-20261128T012202Z' --scope _main --json --stream 'G:/Temp/rollout-sotto-full-stream.json'
```

Observed result: rc `124` (wrapper timeout), wall `605 s` (wrapper reported `605.1s`: startup `0.6s`, wait `600.0s`, not-scheduled `0.0s`, wrapper cpu `5.31s`, launched pid cpu `235.91s`). stdout was `0` bytes; the `--stream` document was `1,625,485` bytes and remained parseable. Wrapper verdict, verbatim:

```
NO-VERDICT: timeout after 600s of observed wait; child tree pid 34488 terminated so the caller gets EOF — total 605.1s (startup 0.6s, wait 600.0s, not-scheduled 0.0s, wrapper cpu 5.31s, launched pid cpu 235.91s [that pid only; not its descendants])
```

Where it actually spent the time, read from the kill-safe stream document: `producer.state = running`, `producer.stage = detector:config_drift:measured`, `verdict = cannot-measure`, `exit_code = 2`. The child's own cache telemetry (verbatim) shows the expensive recomputes:

```
[codeintel health] per-file answers [ast_rules] on: HIT 44 / MISS 2405 (hit rate 1.8%), 0 unusable, 0 unkeyable, 2405 recomputed, 0 pruned, 2586512 B written
[codeintel health] per-file answers [config_env] on: HIT 5 / MISS 927 (hit rate 0.5%), 0 unusable, 0 unkeyable, 927 recomputed, 0 pruned, 8149808 B written
[codeintel health] per-file answers [circular_imports] on: HIT 5 / MISS 927 (hit rate 0.5%), 0 unusable, 0 unkeyable, 927 recomputed, 0 pruned, 315587 B written
```

Detector counts at the kill: `detectors_completed 7/18` — `ast_rules`, `dead_imports`, `config_env`, `circular_imports`, `syntax`, `impl_gate`, `config_drift`; `detectors_pending 11/18` — `wired_read`, `sim_rung_lag`, `live_tier`, `fence_rung_inversion`, `projection_freshness`, `typed_field_guard`, `numeric_rationale`, `sim_ledger_invariants`, `silent_enoent_fallback`, `unordered_cap_slice`, `ambiguous_provenance`. No refusal was recorded in that prefix (`cannot_measure: 0`, `cannot_measure_rows: []`), and `population_counts` was `{scope: 2598, outside-scope: 0, scratch: 0}`.

Findings by class from the killed run (partial — 7 detectors, `2598` findings, not a complete census):

| class | count |
|---|---:|
| ABSOLUTE-DEFAULT-PATH | 89 |
| DEAD-CONFIG-KEY | 14 |
| DEAD-IMPORT | 469 |
| DEFAULT-PATH-DRIFT | 117 |
| DUPLICATED-CONSTANT | 378 |
| ENV-VAR-WITHOUT-PRODUCER | 53 |
| HALLUCINATED-IMPORT | 301 |
| JS-SILENT-CAP | 2 |
| PER-ITEM-SPAWN | 12 |
| RETURN-NONE-EXCEPT | 127 |
| SELECTOR-MATCHES-NOTHING | 2 |
| SILENT-TRUNCATION | 62 |
| SUBPROCESS-NO-CONSOLE | 38 |
| SUBPROCESS-NO-TIMEOUT | 127 |
| SUPPRESS-BROAD-EXCEPT | 650 |
| TYPED-FIELD-GUARD | 157 |

## Prior receipt's scope no longer exists at this HEAD

The F6 receipt scoped `--scope _main/_libs`; that path is absent at `91fae2c`. Attempting it under the same wrapper produced rc `2` in `2 s` and these verbatim lines:

```
{"code": "SCOPE-PATH-ABSENT", "requested": ["_main/_libs"], "resolved": []}
full: SCOPE-PATH-ABSENT: requested ['_main/_libs'] resolved to []
```

## `codeintel full` — complete census on the bounded scope (`--scope app,worker`)

The whole `_main` tree cannot finish inside the declared 600 s ceiling, so the complete detector census was taken on the two real product directories `app` (51 `.py`) and `worker` (44 `.py`) — 95 Python files — under the same ceiling.

Exact command:

```
'H:/Python311/python.exe' -m watcher run --cpu 4 --single RolloutSottoFull --io very-low --timeout 600 --cwd 'H:/codeintel-worktrees/triad-milestones-20261105' -- 'H:/Python311/python.exe' -m codeintel full 'G:/Temp/wt/RolloutSotto-20261128T012202Z' --scope app,worker --json --stream 'G:/Temp/rollout-sotto-full-scoped-stream.json'
```

Observed: rc `1`, wall `267 s` (wrapper reported `266.5s`: startup `0.4s`, wait `262.0s`, not-scheduled `0.0s`, wrapper cpu `3.03s`, launched pid cpu `84.36s`). stdout `398,902` bytes, stream `398,900` bytes. Document fields: `verdict: fail`, `complete: true`, `exit_code: 1`, `refusal: null`, `cannot_measure: 0`, `allowed_cannot_measure: []`, `failing_severity_threshold: high`, `producer.stage: complete`.

Detector counts: `detectors.total 18`, `detectors.measured 18`, `detectors.refused []` (`refused_count: 0`), `detectors_completed 18/18`, `detectors_pending 0`. Completed, in order: `ast_rules`, `dead_imports`, `config_env`, `circular_imports`, `syntax`, `impl_gate`, `config_drift`, `wired_read`, `sim_rung_lag`, `live_tier`, `fence_rung_inversion`, `projection_freshness`, `typed_field_guard`, `numeric_rationale`, `sim_ledger_invariants`, `silent_enoent_fallback`, `unordered_cap_slice`, `ambiguous_provenance`.

Findings: `findings_total 523`, all in scope (`population_counts {scope: 523, outside-scope: 0, scratch: 0}`; `population_class_counts {product: 523, benchmarks: 0, docs: 0, tests: 0, unknown: 0}`). A further `outside_scope_count 185` rows are named but not judged; the JSON `summary` counts both populations (708 rows). In-scope findings by class:

| class | count |
|---|---:|
| DEAD-IMPORT | 48 |
| DEFAULT-PATH-DRIFT | 6 |
| DUPLICATED-CONSTANT | 61 |
| ENV-VAR-WITHOUT-PRODUCER | 6 |
| HALLUCINATED-IMPORT | 9 |
| JS-SILENT-CAP | 3 |
| RETURN-NONE-EXCEPT | 78 |
| SILENT-ENOENT-FALLBACK | 4 |
| SILENT-TRUNCATION | 4 |
| SUBPROCESS-NO-CONSOLE | 7 |
| SUBPROCESS-NO-TIMEOUT | 2 |
| SUPPRESS-BROAD-EXCEPT | 245 |
| TYPED-FIELD-GUARD | 46 |
| UNNAMED-FAILURE | 3 |
| WIRED-READ-TRUNCATED-POPULATION | 1 |

In-scope severity: `high 313`, `medium 198`, `info 12`.

## Refusals, verbatim

- The complete `codeintel full` run refused nothing: `detectors.refused: []`, `refused_count: 0`, `cannot_measure_rows: []`, `refusal: null`. Instead, `wired_read` declared its truncation as a finding at info severity; verbatim message:

```
60 of 95 python files exceeded the declared 631-file wiring walk; their verdicts are UNKNOWN_TRUNCATED, not clean
```

with evidence verbatim: `{"code": "WIRED-READ-TRUNCATED-POPULATION", "confidence": 0.85, "file": "app/webview/audio_playing.py", "first": "app/webview/audio_playing.py", "how": "graph detector wired_read", "last": "worker/unified_fixtures.py", "line": 1, "max_files": 631, "population": 95, "truncated_files": 60, "visit_budget": 60000}`.

- The gate's refusal line is quoted verbatim above: `friction REFUSED rc=2 18329ms child rc=1: }` followed by `gate REFUSED friction in 29532ms rc=2`.

- The stale-scope attempt's refusal lines are quoted verbatim above: `{"code": "SCOPE-PATH-ABSENT", "requested": ["_main/_libs"], "resolved": []}` and `full: SCOPE-PATH-ABSENT: requested ['_main/_libs'] resolved to []`.

- One high-severity row is outside the judged scope; verbatim message: `live.foreign_cwd: codeintel.wired_read entrypoint failed from C:\Windows\Temp: RuntimeError: codeintel read cli_main rc=2: ` (class `VIOLATION`, detector `live_tier`, file `codeintel/health/live_tier.py:1`).

## Verdict

PIN PROVEN (`AGENTS.md:1302`, tracked at HEAD); GATE REFUSED at `friction` (rc 2); `codeintel full` cannot cover `_main` in 600 s (rc 124, 7/18, killed at `detector:config_drift:measured`) but completes on `app,worker` in 267 s (rc 1, 18/18, 523 in-scope findings, 0 detector refusals, `verdict: fail`).
