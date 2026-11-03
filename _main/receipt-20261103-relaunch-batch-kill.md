# Receipt — `--relaunch` batch kill (one delegated token child for the whole set)

Date: 2026-11-03. Repo: `H:/sotto`, branch `feat/speaker-attribution-20261019`, MAIN TREE.
Owner of this lane: exactly `_main/sotto-relaunch.py` + `_main/launch-as-token.py`.
`app/webview/sotto_webview.py`, `worker/**` and the panel state files were NOT touched.

## Problem (measured today)

`kill()` in `_main/sotto-relaunch.py` called `_kill_via_token(pid)` once PER PID; each call
spawned its own `launch-as-token.py` child (CreateProcessAsUser + wait, ~2-3 s each). Measured:
`kill(40060)` walked 6 descendants (python.exe worker + 5 msedgewebview2.exe) in 18 s wall.
`--relaunch` also aborted once with `ABORTA: a instancia antiga nao morreu` because the plain
`taskkill` (medium integrity) was refused and the token path was not reached for the whole set.

## Files changed (sha256)

| file | before | after |
|---|---|---|
| `_main/sotto-relaunch.py` | `e0d50b827d03a210ac2664ea595cc30484a13cb168e9a77ad15d3c37fb1cd444` | `a21c9df9db5c5991ce85323bcaf83bed62a7c9498fea94a39024e49ae244b6b8` |
| `_main/launch-as-token.py` | `e31dbb4f9c7c034ae68838ae7ac72af4f6db57fd3775d24b9c9f4640276322cc` | `1a20d89de96e397e681511b40ba142d55c8df491a3c4c81930b1de2b54296cc5` |

(`git show HEAD:` blob of `sotto-relaunch.py` is `307800c8…`, LF; the working tree before this
change was the same content with CRLF, `e0d50b8…`.)

## Change

1. `launch-as-token.py`
   - NEW `kill_pids_via_high(pids, source=None, timeout=None) -> (ok, source, child, [(pid, rc)])`:
     ONE `pythonw` child under the borrowed `high` token writes a helper script that runs
     `taskkill /PID <pid> /T /F` for each pid, records `pid rc` per line into a state file
     (written with `os.replace`, so the file's existence means complete content), and exits 0
     only when every rc is 0. The parent reads the state file.
   - `kill_via_high(pid)` is now the batch of one pid over the same primitive (signature kept).
   - NEW CLI `--kill-pids 1,2,3`: prints `pid=<n> rc=<rc> morto|NAO morto` per pid and exits 0
     only if all died. `--kill`, `--selftest`, `--neg-arm` and the positional
     `<pid-fonte> <exe> [args]` CLI are unchanged; `--selftest` still proves EXECUTION
     (a child that writes its pid+integrity) and still has the kill-delegation arm.
2. `sotto-relaunch.py`
   - `kill()` resolves the `high` source BEFORE any kill, snapshots the pid + descendants BEFORE
     any kill (`_kill_targets`, same identity as before: PID + name + `ppid` chain), then:
     - if this pane is `high`: cheap native `taskkill /PID … /T /F` per target, then a census;
     - if this pane is `medium` (the measured case): NO direct pass (each was a guaranteed
       `rc=1` at ~0.5 s), the whole set goes to ONE delegated batch child;
     - per-pid fallback only for pids the batch reported as failures AND that a census still
       sees alive (`taskkill` rc is not the final truth: a pid mid-exit returns rc=1 and is
       gone 1 s later — measured today);
     - verification by process census (`_live_pids`, `Get-CimInstance`), never by `alive()`:
       `OpenProcess` on a `high` target is refused with err=5 from this `medium` pane and that
       refusal used to read as "morto" for exactly the process that had to die.
   - `_sweep_litter` (the per-pid legacy loop) is gone; `kill(pid)` keeps its callable signature
     (other probes call it with one argument).
   - `CREATE_NO_WINDOW` preserved on every spawned process and on every `taskkill` invocation.

## Instrument (never touches the owner's screen)

`G:/Temp/batchkill-measure.py` (scratch harness, outside the repo):

- builds a synthetic tree that reproduces the incident's shape: ONE `pythonw` parent + 5
  `pythonw` children, all created with a token borrowed from `explorer.exe` (so the tree is
  `HIGH` like the app, which is what makes the plain `taskkill` from this `medium` pane fail);
- OLD arm = the pre-change module itself, loaded from `git show HEAD:_main/sotto-relaunch.py`
  written to `_main/.old-relaunch-probe.py` (so its `ROOT` resolves to `H:/sotto`), calling the
  old module's own `_sweep_litter` (the per-pid loop) and `_kill_via_token` (one token child per
  pid). The old file's own `kill()` runs the root `/T` first, which reaps this synthetic tree
  before the sweep; the incident's `msedgewebview2.exe` litter survived the app's `/T`, which is
  why the sweep existed, so the sweep is measured first and the root last;
- pinned arm = one `kill_via_high(pid, source)` per pid with the source pinned (isolates the
  cost of one child per pid from the per-pid source re-resolution);
- NEW arm = `sotto_relaunch.kill(root_pid)`;
- counts delegated children by wrapping the launcher module's `launch()` (the only thing that
  calls `CreateProcessAsUser`);
- times until a `psutil` census says every spawned pid is gone, and distinguishes
  `AccessDenied` from `NoSuchProcess` (`AccessDenied != gone`);
- kills every process it spawned and prints a final tagged-pid census.

Exact commands:

```
python G:/Temp/batchkill-measure.py
python -m py_compile _main/sotto-relaunch.py _main/launch-as-token.py
python _main/undefined-names-oracle.py
python _main/console-window-gate.py
python _main/shell-relaunch-oracle.py
python _main/launch-as-token.py --selftest
python _main/launch-as-token.py --neg-arm
python _main/launch-as-token.py --kill-pids <pid[,pid]>
```

## Before / after (6-pid HIGH set, same harness, three runs)

| run | OLD per-pid (as shipped) | OLD per-pid, source pinned | NEW batch `kill()` |
|---|---|---|---|
| 1 | 15.94 s, **6** token children | 5.10 s, 6 | 8.72 s, **1** |
| 2 | 16.14 s, **6** token children | 5.45 s, 6 | 4.67 s, **1** |
| final-pre-optimisation | 15.29 s, 6 | 4.87 s, 6 | 10.57 s, 1 |
| earlier (CRLF/HEAD path) | 15.46–19.00 s, 5–6 | — | — |

- Token children spawned by the OLD loop: one per pid (`6` for `6` pids; the as-shipped code can
  cost `5` when its per-pid `_selftest_source()` call loses the source for one pid — observed in
  2 of 6 runs, that pid was then reaped by the root's `/T`).
- Token children spawned by the NEW `kill()`: **1** for the whole set (the single extra child in
  one run came from the designed per-pid fallback on a pid that was alive after the batch).
- `all_gone: true` in every arm; final tagged-pid census `[]` (nothing spawned survives).
- `C:\Windows\System32\taskkill.exe` rc inside the batch: root `0`, its children `128` (the
  root's `/T` reaps them first) — `kill()` treats 128 as "already gone" only for the retry
  decision and still verifies the whole set by census before returning `True`.

## Negative arm (a pid that does not exist is NOT "killed")

- `kill_pids_via_high([<pid that exited>])` → `ok=False`, `[(pid, 128)]`.
- CLI: `launch-as-token.py --kill-pids <same pid>` →
  `pid=<n> rc=128 NAO morto | kill-pids via token ok=False fonte=14096 …`, `rc=1`.
- Positive control, same CLI: `--kill-pids a,b` on two real sleepers →
  `pid=a rc=0 morto | pid=b rc=0 morto … ok=True`, `rc=0`, both gone.

## Oracles / gates

- `python -m py_compile` both files: OK.
- `python _main/undefined-names-oracle.py` → `UNDEFINED-NAMES GREEN -- 18 ficheiros de producao,
  0 nomes usados e nunca definidos`.
- `python _main/console-window-gate.py` → `findings=0 baseline=0 new=0 VERDICT: GREEN`.
- `python _main/shell-relaunch-oracle.py` → `VERDICT GREEN -- arms=12 pass=12 fail=0`
  (includes arm 7 "kill by pid, never by name" and arm 8 "kill → wait mutex → launch", and its
  own mutant M5, which anchors the `taskkill /PID … /T /F` line inside `kill`).
- `python _main/launch-as-token.py --selftest` → `SELFTEST PASS … filho pid=56652 executou,
  integridade=S-1-16-12288 (HIGH)` + `KILL-DELEGATION PASS … via token ok=True, saiu=True`.
- `python _main/launch-as-token.py --neg-arm` → `NEG-ARM PASS -- RED as designed … err=5`
  (rc=1 by contract).

## Risk to the owner's running app

- The instrument only ever passed pids of its own synthetic tree (`pythonw`, spawned under a
  borrowed `explorer.exe` token) to `kill()`; no kill target in `_main/shell-relaunch.log`
  belongs to the app, and grep of every measurement log for the app pid is `0`.
- No `--relaunch` was executed by this lane; `--check` was read-only.
- Observed concurrently: another lane ran `--relaunch tag=nouia2` at 05:11:21 and started pid
  `55304`; that process stopped logging at 05:13:38 with no `SHELL_EXIT` line. It is not a target
  of this instrument (no kill line names it) — whoever owns that relaunch should confirm whether
  it expected the instance to stop.
- Remaining risk of the change itself: the delegated batch is spawned with a token duplicated
  from a `high` process of this session; if no `high` source is openable, `kill()` reports
  failure instead of pretending, exactly as before. `--relaunch` still prints
  `ABORTA: a instancia antiga nao morreu` only when the final census still sees a target.
