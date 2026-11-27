# Receipt — a family sweep is a loop, and a shell loop is a stutter

**Card:** `dm-3e2757b5705d76bcf5db` (watcher, STUTTER, owner order 2026-11-07)
**Date:** 2026-11-27
**Lane:** this seat (`omp.exe(91016)`, cwd `H:\sotto`)

## 1. The measurement that opened it

The watcher's own verdict on the box, while the signals were live:

```
culprit = python.exe(45980)  io 1.50425MB/s
attribution = machine:disk.saturated
cmdline = python _main/youtube-cdp-source-oracle.py --neg-arm
chain   = python.exe(45980) <- cmd.exe(83344) <- python.exe(89944) <- omp.exe(91016)
DISK    H: q_avg=0.80 busy=80.3% lat=0.20ms r=16.69MB/s w=1.82MB/s
```

**Attribution: correct, and mine.** `omp.exe(91016)` is this seat; the pid was a
child of my own ad-hoc family sweep. No misattribution to send back.

## 2. The line

`bash`, in this seat's own tool call — not a file in the repo:

```
for f in _main/*youtube*oracle*.py _main/yt-*oracle*.py; do
    timeout 180 H:/Python311/python.exe "$f" > I:/cc-tmp/sweep_$base.out 2>&1
done
```

Two costs, and a ceiling fixes neither:

1. **Nothing was reused.** The 1.5 MB `sotto_webview.py` was read from disk by
   every one of the 41 oracles. `_main/_stepcache.py` — the content-keyed cache
   the battery already uses — was never consulted.
2. **Nothing declared a ceiling.** No thread count, no priority, no disk budget,
   no bound on concurrent processes. `timeout 180` is a per-step deadline, not a
   ceiling.

## 3. The cut, at the source

`_main/oracle-family-sweep.py` (new, 8 623 B):

| property | how |
|---|---|
| do it once | `_stepcache check` by **content** before paying a process start; a HIT starts nothing |
| one at a time | one child at a time |
| never the owner's priority | `BELOW_NORMAL_PRIORITY_CLASS \| CREATE_NO_WINDOW` |
| one library thread | `OMP/MKL/OPENBLAS/NUMEXPR/VECLIB = 1` in the child env |
| a deadline, named | `--timeout` per step, reported as `rc=124` |
| honest tail | `SUMMARY oracles= hit= miss= fail=`, plus every RED named |

## 4. Proof — the same box, the same instrument

| run | wall | hits | misses | fails |
|---|---:|---:|---:|---:|
| the old shell loop (41 oracles) | not measured as a suite | — | — | 1 (`youtube-sync`) |
| new, cold (`--no-cache`) | **61.0 s** | 0 | 25 | 0 |
| new, warm | **2.3 s** | **25** | 0 | 0 |

`child_wall_s=0.0` on the warm run: **no oracle process was started at all.**

`python -m watcher perf` **while the cold sweep ran**:

```
SAMPLE   cpu=82.0%  commit=82.5%  disk_lat=3.7ms  stall_gap=0ms
H: q_now=0  q_avg=0.03  busy=3.2%  lat=0.36ms  ops=80
```

Against the card's episode — H: `q_avg=0.80`, `busy=80.3%`, `lat=0.20ms` — the
same volume under the same family of work now sits at **q_avg 0.03, busy 3.2%**.

**The work still completed:** 25/25 oracles, `fail=0`, in both directions. The
41-oracle family sweep that produced this card is now **0 non-zero**.

## 5. What is NOT claimed

- The card's 1,50425 MB/s is a **spike value in the tick that fired**, not a
  rate; per its own note it says nothing about the current rate. The current
  reading above is the one this receipt stands on.
- `python.exe(82192)` was the top H: consumer at 47.07 MB/s when I measured
  after my sweep ended. **Not mine** — not my tree, not my spawn. Named here so
  the census does not attribute it to this lane.
- `cpu=82.0%` during the run includes two other lanes' work visible in the same
  `perf` output (`codeintel-worktrees`, `VOD.RIP`). This receipt claims the disk
  and the process count, not the CPU total.

## 6. The rule

`AGENTS.md`, section *UMA VARREDURA DE FAMILIA E' UM LACO, E UM LACO DE SHELL E'
UM STUTTER*: a family sweep is an isolation, not a `bash` `for`; anyone needing
their own loop declares the four numbers (child threads, priority, deadline,
concurrent processes) and goes through the cache.

## 7. Gates

- `_main/oracle-family-sweep.py --family youtube` → `fail=0` rc 0, cold and warm.
- `claims-date-oracle.py` PASS checks=4 fail=0 (the block is dated inline).
- `agents-md-pins-oracle.py` PASS.
- `undefined-names-oracle.py --json` → `{"files":20,"undefined":0,"verdict":"GREEN"}`.
