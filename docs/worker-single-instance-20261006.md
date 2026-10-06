# One bridge, one worker — `worker-bridge.js`, 2026-10-06

**Owner's report, verbatim:** *"o alt c nao spawnar multiplos processos indesejados. faz
direito. nao sei como deve fazer mas faz direito"*.

**Lane:** `worker-bridge.js` only. **`app/electron/main.js` was NOT modified by this
lane** — the guard in `startWorker()` is the other lane's half, and it is already on
the BRIDGE (`if (workerBridge)`, `main.js:486`). Nothing here touches it.

---

## 1. The mechanism, verified before anything was changed

Three facts, each read out of the file rather than assumed:

| fact | where (pre-fix line numbers) |
| --- | --- |
| `start()` refused only on `this.child` | `worker-bridge.js:366` — `if (this.child) return false;` |
| a death sets `child = null` **and then** arms a restart timer | `:452` (`this.child = null`) → `:469` (`#scheduleRestart('exit')`) → `:518` (`this.timer = setTimeout(...)`) |
| `#spawn()` had no second-child guard | `:380` — it assigned `this.child = child` unconditionally |

So the window is: **worker dies → `child === null` while `this.timer` is still
ARMED inside that same bridge.** Any `start()` inside it spawned a second python,
and the armed timer then spawned a third, orphaning the first (`this.child`
overwritten, nothing holding a handle to the old process).

The defect was **reproduced, not argued**: §4 runs this same self-test against the
pre-fix bridge and it fails with `maxLive=2` and both pids named.

## 2. What changed (`app/electron/worker-bridge.js`)

1. **The fact a caller could not see, now exposed** — `hasPendingRestart`
   (`timer !== null`), `liveChildCount` (0 or 1), `isActive` (live child OR armed
   restart, and not stopped). `isActive` is what makes `start()` idempotent on the
   BRIDGE instead of on the child.
2. **`#spawn()` asserts one-bridge-one-child**: `this.child !== null` → refuse,
   log `BRIDGE_DOUBLE_SPAWN_REFUSED`, and cancel the timer that got it there. Every
   legitimate respawn path (`close`, `error`, the silence ceiling, `stop`) clears
   `child` FIRST, so a non-null child on entry means the spawn would orphan a live
   worker.
3. **`#scheduleRestart()` cancels a still-armed timer before arming its own.** A
   spawn that never starts emits BOTH `error` and `close` on the same child, and
   each handler scheduled its own retry: the second `setTimeout` overwrote
   `this.timer` while the first stayed armed, producing one invisible timer that
   `stop()` could not reach.
4. **`stop()` cancels both timers through one `#cancelRestart()` path** and logs
   what was armed at the moment of the stop.

`#spawn()` and `#scheduleRestart()` now take a `why`, and `#spawn()` returns a
boolean; the `why` shadowing in the two `catch`/handler blocks was renamed to
`message`.

Docs updated: `app/electron/BRIDGE.md` — the "Restart, backoff…" bullet and a new
"Single-instance self-test" subsection. That file already carried another lane's
uncommitted audio-device edit; the change here is additive and does not touch it.

## 3. Acceptance 1 — the self-test, both arms, VERBATIM

```powershell
cd H:\sotto\app\electron
node bridge-single-instance-selftest.js   # rc 0
```

```
sotto: SINGLEINSTANCE module=H:\sotto\app\electron\worker-bridge.js
sotto: SINGLEINSTANCE_STEP arm-hold-one-start-accepted=ok detail=calls=25 accepted=1 spawns=1
sotto: SINGLEINSTANCE_STEP arm-hold-live-processes-never-exceed-one=ok detail=maxLive=1 maxBridgeChild=1 samples=84 pidsSeen=1
sotto: SINGLEINSTANCE_STEP arm-hold-accessors-report-active=ok detail=live=1 isActive=true pendingRestart=false
sotto: SINGLEINSTANCE_STEP arm-hold-stop-kills-the-only-worker=ok detail=spawnsBefore=1 spawnsAfter=1 liveAfterStop=0
sotto: SINGLEINSTANCE_STEP arm-die-restart-timer-is-armed-while-child-is-null=ok detail=armed=true liveChildCount=0 isActive=true pendingRestart=true
sotto: SINGLEINSTANCE_STEP arm-die-start-refused-while-armed=ok detail=calls=24 accepted=0 spawns=2
sotto: SINGLEINSTANCE_STEP arm-die-live-processes-never-exceed-one=ok detail=maxLive=1 maxBridgeChild=1 samples=202 pidsSeen=5 over=[] restarts=2->5
sotto: SINGLEINSTANCE_STEP arm-die-restart-still-happens=ok detail=restarts=5 spawns=5 (a bridge that stops restarting would pass the count above by doing nothing)
sotto: SINGLEINSTANCE_STEP stop-cancels-every-timer=ok detail=armedAtStop=false stillArmed=false spawns 5->5 restarts 5->5 live 0->0 pidsSeen=5
sotto: SINGLEINSTANCE_RESULT PASS steps=9 rc=0
SINGLEINSTANCE PASS steps=arm-hold-one-start-accepted=ok arm-hold-live-processes-never-exceed-one=ok arm-hold-accessors-report-active=ok arm-hold-stop-kills-the-only-worker=ok arm-die-restart-timer-is-armed-while-child-is-null=ok arm-die-start-refused-while-armed=ok arm-die-live-processes-never-exceed-one=ok arm-die-restart-still-happens=ok stop-cancels-every-timer=ok rc=0
```

**Arm A (`hold`, the CONTROL).** Worker stays up, `start()` ×25 → `accepted=1`,
`maxLive=1`. This arm is labelled a control because **it also passes against the
broken bridge** (§4) — on its own it proves nothing about the defect.

**Arm B (`die`, THE DEFECT).** Worker exits 7 immediately, so the window opens:
`armed=true liveChildCount=0 isActive=true pendingRestart=true`. Alt+C is then
pressed 24 more times inside that window: `accepted=0`. The bridge keeps exactly
one worker alive across several backoff windows — `maxLive=1`, `over=[]` (no sample
ever saw two), while still doing its job (`restarts=2->5 spawns=5`).

What is being counted is **OS processes**, not the bridge's own counter: every
fake worker appends its own `os.getpid()` to a file, the test polls
`process.kill(pid, 0)` every 5 ms, and the pass condition is the MAXIMUM over the
run. `stop()` is then checked with `spawns`/`restarts` frozen and 1.5 s elapsed —
longer than the 800 ms max backoff — so a cancelled restart that fired late would
show up as a new spawn.

## 4. The gate is NOT vacuous — same test, pre-fix bridge, RED

```powershell
New-Item -ItemType Directory -Force _single-instance | Out-Null   # generated dir; both tests recreate it, nothing committed there
"C:\Program Files\Git\cmd\git.exe" show HEAD:app/electron/worker-bridge.js > _single-instance\worker-bridge-prefix.js
$env:SOTTO_BRIDGE_MODULE = "_single-instance\worker-bridge-prefix.js"
node bridge-single-instance-selftest.js   # rc 3
```

```
sotto: SINGLEINSTANCE_STEP arm-hold-one-start-accepted=ok detail=calls=25 accepted=1 spawns=1
sotto: SINGLEINSTANCE_STEP arm-hold-live-processes-never-exceed-one=ok detail=maxLive=1 maxBridgeChild=0 samples=84 pidsSeen=1
sotto: SINGLEINSTANCE_STEP arm-hold-accessors-report-active=FAIL detail=live=undefined isActive=undefined pendingRestart=undefined
sotto: SINGLEINSTANCE_STEP arm-hold-stop-kills-the-only-worker=ok detail=spawnsBefore=1 spawnsAfter=1 liveAfterStop=0
sotto: SINGLEINSTANCE_STEP arm-die-restart-timer-is-armed-while-child-is-null=FAIL detail=armed=false liveChildCount=undefined isActive=undefined pendingRestart=undefined
sotto: SINGLEINSTANCE_STEP arm-die-start-refused-while-armed=FAIL detail=calls=24 accepted=5 spawns=13
sotto: SINGLEINSTANCE_STEP arm-die-live-processes-never-exceed-one=FAIL detail=maxLive=2 maxBridgeChild=0 samples=536 pidsSeen=29 over=[{"at":1791264907518,"live":2,"pids":[29256,36640]},{"at":1791264907542,"live":2,"pids":[29256,29524]},{"at":1791264907587,"live":2,"pids":[29256,12480]},{"at":1791264909262,"live":2,"pids":[34552,29800]}] restarts=12->29
sotto: SINGLEINSTANCE_STEP arm-die-restart-still-happens=ok detail=restarts=29 spawns=30 (a bridge that stops restarting would pass the count above by doing nothing)
sotto: SINGLEINSTANCE_STEP stop-cancels-every-timer=FAIL detail=armedAtStop=true stillArmed=undefined spawns 30->30 restarts 29->29 live 1->0 pidsSeen=30
sotto: SINGLEINSTANCE_RESULT FAIL steps=9 rc=3
```

`maxLive=2` with four named pid pairs is the owner's report, reproduced as
processes: **29 python starts from 25 Alt+C presses**, two alive at once. The
control arm passes on both bridges, exactly as predicted.

## 5. Acceptance 2 — process count from OUTSIDE, before and after the backoff window

A separate instrument, because a count taken from inside the bridge is a
self-report. This one asks Windows which `python.exe` processes have
`worker_probe.py` — **the probe's own script path** — in their command line. Never
by image name: other lanes run python on this box.

```powershell
node worker-proc-count-probe.js   # rc 0
```

```
sotto: PROCCOUNT worker_script=H:\sotto\app\electron\_single-instance\worker_probe.py
sotto: PROCCOUNT filter = python.exe whose CommandLine contains "worker_probe.py"
sotto: PROCCOUNT window armed at t+418ms: liveChildCount=0 isActive=true pendingRestart=true
sotto: PROCCOUNT startsAcceptedInsideWindow=0 of 20
sotto: PROCCOUNT BEFORE the backoff window  = max 1 over 6 samples (t+418ms .. t+2018ms)
sotto: PROCCOUNT AFTER the backoff window   = max 1 over 31 samples (t+2018ms .. t+9724ms)
sotto: PROCCOUNT AFTER stop()               = max 0 over 10 samples | maxBeforeFirstSpawn=0 (5 samples) bridgeSpawns=6 restarts=6
sotto: PROCCOUNT_SERIES ms:count -36:0 208:1 455:0 716:0 989:1 1240:0 1518:0 1766:0 2033:0 2296:1 2569:0 2795:0 3044:0 3287:0 3521:0 3752:0 3989:0 4232:1 4487:0 4719:0 4979:0 5221:0 5520:0 5766:0 6017:0 6284:1 6529:0 6784:0 7034:0 7297:0 7538:0 7780:0 8060:0 8316:1 8572:0 8815:0 9127:0 9430:0 9707:0 9980:0 10485:0 10947:0 11296:0 11571:0 11822:0 12051:0 12294:0 12540:0 12854:0
sotto: PROCCOUNT cleanup killedOurOwnPids=0
sotto: PROCCOUNT_RESULT PASS baselineMax=0 beforeMax=1 afterMax=1 afterStopMax=0 rc=0
```

**BEFORE the backoff window = max 1** (6 samples), **AFTER = max 1** (31 samples),
**after `stop()` = max 0**. Six workers ran in sequence; none overlapped. The
series is pasted so the claim can be checked rather than believed.

Two instrument corrections that changed a number, recorded because both would have
made this receipt false:

- **First version printed `0` and `0`.** Both moments landed between a worker dying
  and the next starting — true, and silent about the peak. The claim is about the
  MAXIMUM, so it now samples continuously (one PowerShell, ~250 ms per WMI sample;
  sampling by process restart would step over the whole defect window) and reports
  maxima per window.
- **First version printed `baselineBeforeAnySpawn=1`.** That window was measured up
  to `armedAt`, which INCLUDES the first worker. A number next to a claim it does
  not support is worse than no number; the baseline is now strictly pre-`t0` and
  reads 0.

## 6. Acceptance 3 — `node --check`

```
> cd H:\sotto\app\electron ; node --check worker-bridge.js ; echo "NODE_CHECK_RC=$?"
NODE_CHECK_RC=0
```

```
> node --check bridge-single-instance-selftest.js   -> (no output) exit 0
> node --check worker-proc-count-probe.js          -> (no output) exit 0
```

## 7. Acceptance 4 — `main.js` untouched by this lane

`git status` on this repo shows `M app/electron/main.js` — that is the OTHER lane's
half (the `if (workerBridge)` guard and its comment, present in the working tree
before this lane started, `main.js:479-489`). This lane changed exactly:

- `app/electron/worker-bridge.js` (edited)
- `app/electron/bridge-single-instance-selftest.js` (new)
- `app/electron/worker-proc-count-probe.js` (new)
- `app/electron/BRIDGE.md` (docs, additive)
- `docs/worker-single-instance-20261006.md` (this file)

## 8. No regression in the existing path

`bridge-selftest.js` (the parser / status / restart self-test, 7 steps) re-run after
the change:

```
sotto: BRIDGE_SELFTEST_STEP canned-jsonl-captions=ok ...
sotto: BRIDGE_SELFTEST_STEP restart-after-crash=ok detail=restarts=2 captions=2 died=true backoff=true
sotto: BRIDGE_SELFTEST_STEP missing-worker-status=ok detail=names-worker=true names-path=true not-waiting=true ...
sotto: BRIDGE_SELFTEST_RESULT PASS steps=7
BRIDGE_SELFTEST PASS steps=... rc=0
```

**This test caught a regression I introduced.** An earlier edit dropped
`this.restarts += 1` from `#scheduleRestart`, so backoff never grew — every retry
came back at the 400 ms base and `arm-die-restart-still-happens` read `restarts=0`.
It is restored, and the reason is written at the line so the next edit does not
repeat it.

## 9. Process hygiene

- Nothing was killed by name. Every signal went to a pid this lane's own worker
  reported in its own pid file, and `cleanup killedOurOwnPids=0` /
  `killedOurOwnPids=0` in the final runs because every worker had already exited.
  Post-run census of `python.exe` matching `worker_probe*` / `arm-hold` /
  `arm-die`: **0**.
- **No visible window from this lane.** The bridge spawns with
  `windowsHide: true` and piped stdio; the probe's PowerShell is spawned with
  `windowsHide: true` and `-NonInteractive`. The `ALERTA-JANELA … pid=14396
  nome=python` that appeared in `ManagerWindowCensus` at 05:35:21Z is **not mine**:
  14396 appears in none of this lane's four logs (this lane's pids were 10388,
  12076, 12332, 23104, 23300, 33396 and the arm pids), the process was already gone
  when queried, and the python processes alive on this box belong to other lanes
  (`sotto_webview.py --show …` pid 32468, `cuda_probe.py` pid 3564). That lane's
  `--show` is the likely cause. `ManagerWindowCensus` returned to EM DIA on its own
  at 05:36:21Z.

## 10. The governors the SELO named — named, not silently dropped

`[dispatch=NAO]`: this seat has no dispatch tool, so the seal's required close
(3–4 of 23 external governors RED) is **not** mine to close, and the injected seal
is not evidence about this work. For the record, and measured rather than assumed:

| governor | state | owner of the debt | is it this lane's? |
| --- | --- | --- | --- |
| `ManagerDiskCensus` | VERMELHO-SILENCIO, 34.5 h | Task Scheduler `scripts/disk-census-task.sh`, artefact not emitting | no |
| `theorist-always-on` | VERMELHO-SILENCIO, 39.2 h | Task Scheduler `scripts/theorist-always-on-scheduled.cmd` | no |
| `theorist-delta-guard` | VERMELHO-SEM-SINAL, 5.95 d | declared artefact absent from disk; no producer to ask | no |
| `ManagerWindowCensus` | flapped to VERMELHO-FALHA at 05:35:21Z | the `sotto_webview.py --show` python of another lane (§9) | no — identified, not mine |

All four belong to scheduled-task producers in `I:/!manager/scripts`, which is
outside `H:/sotto` and outside this assignment. **Whoever holds the dispatch seat
owns routing those**; this lane has neither the tool nor the mandate, and guessing
at them would be the "same line with a new date" the seal itself calls out.

## 11. CACHE/PRICE — verbatim

```
## CACHE/PRICE
- task/agent: SottoWorkerSingleInstance
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoWorkerSingleInstance.jsonl
- cache: read=8408176 write=0 hit=97.6342% (cache-read / input+cache-read); universe: 66 usage rows from ...\SottoWorkerSingleInstance.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=66 input=$0.00000000 output=$0.00000000 cacheRead=$0.00
- when-failed: break_items=2; WHEN=2026-10-06T05:28:44.099000+00:00 | break_items=2; WHEN=2026-10-06T05:33:49.004000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 110763 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoWorkerSingleInstance']; window: 20
- where-failed: session_id=01a10fad-a598-72b1-9340-36de7bb402c6 provider=space-bunny-free model=space-bunny-free item_index=29; turn_id=1791264524099 | session_id=01a10fad-a598-72b1-9340-36de7bb402c6 provider=space-bunny-free model=space-bunny-free item_index=92; turn_id=1791264829004 (state=RESOLVED-BREAKS-OMP)
- report generated_at: 2026-10-06T05:36:55.065703+00:00
- usage rows: 66
- model + route: opencode-zen/space-bunny-free
- input tokens: 203737
- output tokens: 31548
- cache-read tokens: 8408176
- cache-write tokens: 0
- hit ratio: 97.6342% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=66 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 66 of 66 matched
- prefix breaks: 4 (state=RESOLVED-BREAKS-OMP; population: 2 of 110763 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoWorkerSingleInstance']; window: 2026-10-06T05:28:44.099000+00:00..2026-10-06T05:33:49.004000+00:00)
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T05:28:44.099000+00:00; WHERE session_id=01a10fad-a598-72b1-9340-36de7bb402c6 provider=space-bunny-free model=space-bunny-free item_index=29; turn_id=1791264524099
  - break_items=2; WHEN=2026-10-06T05:33:49.004000+00:00; WHERE session_id=01a10fad-a598-72b1-9340-36de7bb402c6 provider=space-bunny-free model=space-bunny-free item_index=92; turn_id=1791264829004
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

## SELF-AUDIT

**protocolos em falta.** Two. (1) *Run the instrument against the broken code
before trusting its green.* I built the self-test, ran it, and only afterwards
thought to point it at the pre-fix bridge. Had the mutant run not existed, the
receipt would have shipped a green that had never been shown capable of being red —
and the mutant run is what exposed that arm A is vacuous on its own. (2) *When an
edit tool reports a repaired boundary or a syntax error, re-read before issuing the
next edit.* My `PUT` over `#scheduleRestart`'s head silently consumed
`this.restarts += 1`, and I kept editing on top of a file the tool had just told me
was broken. The cost was a real regression in backoff, caught only because the test
read `restarts` rather than trusting the log.

**verificacao adicional.** Ran, at ~1 min each: (a) the pre-fix mutant RED, §4 —
this is the one that mattered; (b) `bridge-selftest.js` for regressions, §8. Not
run, and I would if there were time: driving the real `worker/sotto_worker.py`
(~2.1 GB RSS per instance) through the same Alt+C burst under `electron .` — the
bridge's own `windowsHide` spawn path is exercised only through the inline `-c`
worker here, so the real worker's argv/env handling is covered by the existing
self-test rather than by this one. Cost: one 2.1 GB load and an Electron window.

**checkboxes novas.** Three mechanical steps for this class of work:

1. *Before writing the fix, extract the pre-fix file and run the new test against
   it.* `git show HEAD:<file> > _tmp/prefix.js` + `SOTTO_BRIDGE_MODULE=<that>`
   must be **rc 3** with the failure naming a real process/pid. If the new test is
   green against the old code, the test is not a proof and nothing else in the
   receipt should be believed.
2. *Every counter a test reads must be incremented somewhere the test can watch.*
   The `arm-die-restart-still-happens` step exists only because the test reads
   `bridge.restarts`; it is what caught the dropped increment. Assert on
   counters, not only on log strings.
3. *A measurement window must be strictly narrower than its label.* The
   `baselineBeforeAnySpawn=1` bug was a window that did not match its name. Print
   the window's bounds in the same line as the number (the probe now does:
   `max 1 over 6 samples (t+418ms .. t+2018ms)`), so a mismatched label is visible
   in the output instead of only in the source.

**review por outro subagente.** sim-com-escopo: the three accessors' semantics
(`isActive` vs `liveChildCount` vs `hasPendingRestart`) and the `#spawn` refusal's
interaction with the missing-file and spawn-threw paths, which I reasoned about but
did not exercise with a test — `BRIDGE_DOUBLE_SPAWN_REFUSED` never fired in any run
here, because the arms reach it only through a surviving superseded timer. My
evidence that the refusal path works is `bridge-selftest.js`'s
`missing-worker-status` passing (the missing path still schedules restarts) plus
code reading. Accepto passar o meu trabalho para review de outro subagente.

**gate-doubt**

Mechanical check on this block, since it is the kind of section that is easy to
write and hard to read: `bash I:/!manager/scripts/self-audit-lint.sh
H:/sotto/docs/worker-single-instance-20261006.md` →
`SELF-AUDIT-LINT: inspected=1 violations=0 no-verdict=0 / SELF_AUDIT_CLEAN`, rc 0.
(First run was rc 1 `GATE-DOUBT-SHALLOW`: the three sub-questions were written in
italic `*verde-de-verdade.*` form, which the gate does not accept as an answer —
it wants `**verde-de-verdade**:` with the bold closed before the colon. Fixed.)

- **verde-de-verdade**: Three greens are load-bearing and I looked at each:
  `SINGLEINSTANCE PASS rc=0` — real, because the same binary goes rc 3 with
  `maxLive=2` on the pre-fix module (§4), and the control arm is the arm that would
  have passed vacuously; it is labelled a control precisely so nobody cites it as
  the proof. `PROCCOUNT_RESULT PASS rc=0` — real, but it depends on the sampler
  actually seeing a worker alive, which is why the first version's `0`/`0` was
  discarded and the worker was given a 350 ms lifetime; with the series pasted, six
  `1`s are visible, so the `max 1` is an observation and not an absence of
  measurement. `BRIDGE_SELFTEST PASS rc=0` — this one is **shared**: it exercises
  the same bridge I changed, from a file another lane owns, so a future edit to
  `bridge-selftest.js` could make it green for the wrong reason. Race I am most
  exposed to: the working tree already carried another lane's uncommitted
  audio-device edit to `worker-bridge.js` and `BRIDGE.md`; my measurement is of the
  COMBINED file, and I cannot separate the two from inside this lane.
- **falta-no-gate**: The gate never sees the `error` + `close` double-schedule that
  fix #3 addresses: no arm spawns a command that fails to start (a nonexistent
  interpreter), so the superseding-cancel line is covered by reading and by
  `missing-worker-status`, not by measurement. A future change that arms a timer
  from any path other than `#scheduleRestart` would sail through. Scenario: someone
  adds a "retry sooner on silence" timer next to `silenceTimer`; `stop()` clears
  both today only because there are exactly two and both are named in it.
- **gate-melhor**: A third arm, `arm-spawn-fails`: create the bridge with
  `command: 'python-does-not-exist'` and `requireExists: false`, so Node emits
  `error` **and** `close` for the same child, then assert
  `hasPendingRestart === true` and — the part that is RED today — that after
  `stop()` and `wait(maxBackoff * 3)` no further `spawns` occur. Command:
  `SOTTO_SINGLEINSTANCE_ARM=spawn-fails node bridge-single-instance-selftest.js`;
  the input that must leave it RED is any code where `#scheduleRestart` re-arms
  without the `#cancelRestart` supersede. I did not add it: it needs a failure path
  whose exact `error`+`close` ordering I could only verify by running it, and
  guessing at the assertion would have shipped a step whose RED I had not seen.

**confianca.** media-alta. Alta on the mechanism (reproduced as real pids against
the pre-fix code, then closed) and on `start()`/`#spawn`/`stop()`. The gap between
media and alta is the untested `#spawn` refusal and double-schedule paths, and the
fact that the arms use an inline `-c` worker rather than the real
`sotto_worker.py`: an inline worker cannot wedge on a model import the way the live
worker can, so the silence-ceiling path that also re-enters `#spawn` is untested
here. What would move it to alta: the `arm-spawn-fails` arm green against a
deliberately un-superseded mutant, plus one `electron . --with-worker` run with a
real worker death and a burst of Alt+C.

**nao verificado**

- The `BRIDGE_DOUBLE_SPAWN_REFUSED` path never executed in any run — read, not
  measured.
- The silence-ceiling → `#scheduleRestart` → `#spawn` cycle is not exercised by
  either arm (`silenceMs: 60000`, and both workers emit a status immediately).
- `electron .` (the real shell) was not run; both tests are plain node against the
  bridge module, so main.js's use of the new accessors is untested from this lane.
- The mutant used is `HEAD`'s `worker-bridge.js`, which predates another lane's
  uncommitted audio-device edit. It reproduces the double-spawn defect exactly
  (`maxLive=2`), but it is not a byte-for-byte copy of the working tree as it stood
  before this lane's edit.
- No test covers two SEPARATE `WorkerBridge` objects pointed at the same worker
  path — one bridge per process is main.js's guarantee, not the bridge's.