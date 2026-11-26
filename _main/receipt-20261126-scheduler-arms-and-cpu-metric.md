# Three arms that measured the scheduler, and a check that WAS the friction

Date: 2026-11-26. Tree: `H:/sotto`, `feat/speaker-attribution-20261019`.
Commit: `948d61be57` (parent `3537f6250a`).

Run #10 (`_main/_audit-verify/_battery-run-20261126-180900.log`, 4 135,4 s) finished
`RED - 8 step(s) failed`. Five of the eight were not defects of the product and not defects of the
step: they were **measurements whose population moved** because the box was starved by my own
scouts and a 9,81 GB worktree reclaim running beside the cage. Each one is repaired at the
instrument, because a gate that flips on scheduling is a coin toss, and a coin toss costs a
70-minute run every time it lands wrong.

## 1. `paint-cost` A2 — an absolute wall bar inside a CPU cap

Measured, same code, same machine:

| window | hit p95 | miss p50 |
|---|---|---|
| standalone | 0,110 ms (p50 0,073, max 0,299) | 8,36 ms |
| inside the battery cage | 15,164 ms | — |

106× on a bar of `HIT_P95_MAX_MS = 2.0`. `process_time` was tried as the cure and **rejected on
measurement**: Windows `process_time` has ~15,6 ms granularity, so every sample read `0.000 ms` —
an arm that cannot fail, i.e. a false green. Final form:

- the **ratio** `miss/hit >= HIT_RATIO_MIN = 20.0` is judged always, measured in the same run;
- the absolute `2.0 ms` bar is judged only when `SOTTO_BATTERY_CAGED != '1'`;
- under the cage over the bar the arm prints `A2 CANNOT-MEASURE why=caged-cpu-cap` — a named
  refusal, never a PASS.

The cache-off mutant still fails inside **and** outside the cage, so the arm can still fail.

## 2. `step-deadline` A8/A9 — an absolute priority class

The battery's cage is a Job Object already running the tree at `BELOW_NORMAL`. A8/A9 read the
child's absolute class, so on unchanged code A9 flipped red the moment the harness was caged
(parent and child both `0x4000`; the launcher had no room to demote). Repaired to judge **relative
to the parent's own class**, read from the live process (`GetPriorityClass` on
`GetCurrentProcess`), with `_RANK` over `{0x40, 0x4000, 0x20, 0x8000, 0x100, 0x80}`:

- A8 = the launcher must **strictly demote** when the parent is `NORMAL`; otherwise
  `A8 CANNOT-MEASURE why=parent-already-demoted parent=0x.. child=0x..`;
- A9 = `child == parent`.

Proved in three directions (`I:/cc-tmp/prio-arms.py`):

1. demoted parent `0x4000` → `A8 CANNOT-MEASURE`, `A9 PASS`, `STEP-DEADLINE SELFTEST: PASS (9 arms)`, rc 0;
2. mutant that demotes the timing steps → `A9 FAIL`, rc 1 (caught);
3. mutant that never demotes → `A8 FAIL`, rc 1 (caught).

## 3. `benchmarks/budgets.json` — two subsystem budgets judged the queue

The same two commands, unchanged tree, two runs: `tooling_intent_ms` **510,31 ms** vs
**1 353,11 ms** (+165,2 %); `feature_map_gate_ms` **1 241,91 ms** vs **2 592,68 ms**. Wall time
inside `--cpu 40 --io very-low` is a statement about the scheduler. Both metrics switched to
`metric_name: cpu_ms` / `parse_mode: cpu_ms`.

The CPU reading itself cost three attempts, and the third is the one that ships
(`C:/Users/Administrador/.agents/skills/project-revival/scripts/benchmark_history.py`):

| attempt | observed | verdict |
|---|---|---|
| `resource.getrusage(RUSAGE_CHILDREN)` | module absent on Windows → `NaN` on every row | impossible |
| `os.times().children_user + children_system` | `0.0` on every row, always | **false green**, thrown out |
| `psutil` sampling of the child tree at 50 ms, max of samples | see below | ships |

Known-answer runs of the sampler:

| child | wall | cpu_ms |
|---|---|---|
| CPU-bound loop (`sum` of 8M) | 390 ms | 344 ms |
| `time.sleep(1.0)` | 1 068 ms | 62 ms |
| `feature_map_sync.py --gate` ×2 | 1 451 / 1 659 ms | 891 / 922 ms |

An unsampled child (shorter than one sample) yields `NaN`, and `NaN` becomes `CANNOT-MEASURE` in the
metric — never a passing `0.0`. The sampler also keeps the **maximum** across samples and never
freezes on a failed tree enumeration: the first version did freeze, and reported `cpu_ms=31,25`
against `wall_ms=1295,75` for a command that really burns ~900 ms.

## 4. `friction.rust_compile_loop` — the verifier was the friction

`verify_cmd` was `Path('.').rglob('*')` over 8,87 GiB, measured at **15,068 s** against its own
`target_s = 8.0`: the gate could not pass while the check was the thing being measured. Replaced by
a bounded census over **three declared sources** (`_main/_audit-verify-all.cmd`, `scripts/*.py`,
`_main/*.cmd`) for the invariant that actually matters — the inner loop never invokes `cargo`:

```
friction.rust_compile_loop   0.124   target=8.0  VERIFIED
```

`loop_friction_audit.py measure --repo . --gate` → `verdict PASS, failures []`, six rows VERIFIED.

## Ambient, not repaired, and why

`panel-live-box-oracle` hit the 240 s step deadline after printing `arms : 4/4`; standalone it is
**rc 0, 10,29 s, `VERDICT: PASS (arms 4/4, mutantes 3/3 RED)`**. `red-as-expected-caption-overlay-screen`
was killed with no output; standalone **rc 1, `NEG-ARM: PASS`** (the expected red).
`red-as-expected-youtube-cdp-boot` raised `MemoryError` reading the 1,5 MB shell while the box sat at
72 % commit; standalone **rc 1, `NEG-ARM VERDICT: PASS (6/6)`**, 29 s. All three are the same
finding: **nothing heavy runs beside the battery**, which is now the standing rule for this tree.

## Verification after the last edit

`python _main/step-deadline.py --selftest` → `PASS (9 arms)`; `python _main/paint-cost-oracle.py` →
`PAINT-COST PASS`; `benchmark_history.py --selftest` → `{"selftest":"PASS","arms":4}`;
`benchmark_history.py run --repo .` → `cpu_ms` populated on every row;
`loop_friction_audit.py measure --gate` → `PASS`; `battery-launch.py --verify` → `VERIFY: PASS`.
The full battery on the settled tree is the next run and its exit code is the verdict.
