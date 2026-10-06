# The tap restart loop — the shell killed a worker for being quiet on a silent machine

Lane `SottoTapRestartLoop`, 2026-10-06. Target: `app/webview/sotto_webview.py` (the bridge).
`worker/` was NOT touched — the two capture defects that feed this loop belong to the sibling
lane `SottoFlatEndpoint`.

---

## 1. The defect, measured, not inferred

`sotto_webview.py` ran a 15 s no-output watchdog (`WORKER_BRIDGE.silence_ms = 15000`) that
re-armed on **every stdout line** and killed + respawned the worker on expiry. A **caption**
was the only thing that produced output on a quiet machine, so:

> An IDLE DESKTOP produces digital silence **by design** — this repo's own idle-floor probe
> measured `peak=0.000000` on the default render endpoint's loopback over three independent
> 6 s captures (`_main/sdr_idlefloor.out`) — so no caption can ever arrive, so the timer can
> never be lifted, so the worker is killed every 15 s forever, each respawn reloading a
> ~2.4 GB model (`WORKER_STATS ... rss_mb=2413.7`, the worker's own line).

The loop could not converge. It is not a timeout problem: **the criterion was wrong.**

### BEFORE — counted by me from the logs already on disk

| log (one live idle run each) | `BRIDGE_SPAWNED` | `BRIDGE_SILENT` (the kill) | worker exits `rc=1` (= killed) | `rc=3` (its own verdict) | `no-audio` |
|---|---|---|---|---|---|
| `_main/_live_owner3.log` | **54** | **14** | **35** | 18 | 0 |
| `_main/_live_owner.log`   | 30 | 5 | 28 | 2 | 0 |
| `_main/live-owner.log`    | 14 | 4 | 12 | 1 | 0 |
| `_main/live-owner-2.log`  | 6 | 4 | 4 | 0 | 0 |

`rc=1` is `child.terminate()`: the shell's own kill. So in the biggest of these, **35 of 54
worker starts died of the silence kill**, not of anything the worker found. The owner's card
cites a fifth log with 24 `device-rotated (flat)`, 8 `BRIDGE_SILENT`, `spawns=10`; the four
above are the same shape with a longer observation.

Reproduction of the interleaving, from `_main/_live_owner3.log:44-60`:

```
STATUS_APPLIED text="device-rotated (flat)"      <- the worker's OWN verdict on that tap
STATUS_APPLIED text="capture-started"
BRIDGE_SILENT ms=15000 pid=13752                  <- the shell kills it for being quiet
BRIDGE_RESTART reason=silent in_ms=1000 restart=1
BRIDGE_EXIT pid=13752 rc=1 ... spawns=1 ...       <- rc=1: killed, not finished
```

---

## 2. The change

`_on_silence` now reads **the worker's own verdict about the audio**, never the absence of a
caption. Three shapes of that verdict are tracked per child (reset in `_spawn`):

- `device-rotated` with `reason=flat` — the ladder's own per-candidate row, written on the way
  out of a window that stayed under the peak floor. **This is what an idle desktop produces,
  candidate after candidate.** (`open-failed` is NOT included: a device that could not be
  OPENED is a different fact from one that opened and heard nothing.)
- a terminal device state: `silent-device`, `device-exhausted`, `no-speech-in-capture`,
  `music-only-capture` (`WORKER_NO_AUDIO_STATES`).
- a `done` whose `verdict` is one of `WORKER_NO_AUDIO_VERDICTS`. `captions-emitted` is
  deliberately absent — it is the one verdict that says speech DID come out.

Verdict present → the silence is the **correct behaviour of a quiet machine**:

```
BRIDGE_SILENT_BENIGN ms=15000 pid=... state=no-audio because="device-rotated reason=flat ..."
```

— the state is **named** (`no-audio`, painted as *"No audio to transcribe"*), **nothing is
killed**, and the timer is **re-armed** so the watchdog keeps watching.

No verdict → the silence is **anomalous** (the tap opened and then went mute with no
explanation) and the watchdog still kills and restarts, exactly as before.

Not changed: the timeout (still 15 s — the problem was never the time), the exit path
(`_wait` → `_schedule_restart('exit')`), the reload floor, the caption hold.

Named UI state, two channels: `WorkerBridge.state == 'no-audio'` (machine-readable) and the
painted status `{'title': 'No audio to transcribe', ...}` with kind `busy`, not `error`.
The painted text avoids the substring `no audio` on purpose: `_status` rewrites any text
matching `FALSE_AUDIO_ABSENT_RE` into `CAPTURE_NOT_STARTED`/busy, which would turn a named
fact back into a warm-up. If a death is already on screen (`pending_error is not None`) the
paint is held — a real exit outranks a benign quiet — and `BRIDGE_SILENT_BENIGN_HELD` is
logged instead.

---

## 3. The oracle — `_main/tap-restart-loop-oracle.py`

Drives the REAL `WorkerBridge` against a fixture (`_main/_tap-restart-fake-worker.py`) that
writes only the line shapes `worker/sotto_worker.py` writes. Real subprocess, real timers, real
`_pump`/`_consume`/`_arm_silence`/`_on_silence`/`_kill_and_restart`; `silence_ms=600` instead of
15000 to keep it fast. No WebView2, no device, no model, no audio, no window.

### After — `py -3 _main/tap-restart-loop-oracle.py` (rc=0)

| arm | child's own output | spawns | respawns | `BRIDGE_SILENT` kills | benign re-arms | named state |
|---|---|---|---|---|---|---|
| GREEN `idle` | ladder rotates with no caption, then streams quietly | 1 | **0** | 0 | 4 | `no-audio` painted |
| GREEN `verdict-quiet` | + `device-exhausted`/`silent-device`/`done` | 1 | **0** | 0 | 4 | `no-audio` painted |
| GREEN `idle-under-death` | same, with a real exit-3 death already on screen | 1 | **0** | 0 | 8 (all HELD) | **not** painted — held behind the death |
| ANOMALY `no-verdict` | `capture-started`, then nothing, ever | 4 | 3 | 3 | 0 | — (not painted) |
| ANOMALY `signal-quiet` | a caption came out, then mute | 5 | 4 | 3 | 0 | — (not painted) |
| **RED `idle`** (pre-fix copy) | same as GREEN `idle` | 4 | **3** | 3 | 0 | — (not painted) |

(`benign re-arms` counts both variants of the log line: `BRIDGE_SILENT_BENIGN ms=` when the
named state was painted, and `BRIDGE_SILENT_BENIGN_HELD` when a death was on screen and the
paint was correctly withheld.)

`spawns` is the bridge's own counter (`BRIDGE_SPAWNED`); `respawns = spawns - 1` — the first
start is the app starting, and **the acceptance number is `respawns = 0` on the idle arm**.

The green is not a green you cannot turn red:

- **RED arm, built from today's bytes**: the oracle copies `sotto_webview.py`, reverts the
  guard, and asserts the copy differs from the live file by **exactly one line** (counted, not
  assumed) — `line 2875: if self.no_audio: -> if False:` — then runs the SAME fixture through
  it. Respawns go 0 → 3 and `no-audio` disappears. If the copy cannot be built, or differs by
  more than that one line, the oracle **REFUSES** (rc=2) instead of reporting green.
- **ANOMALY arms** prove the watchdog still has teeth: a worker that never explains itself, and
  one that had already produced a caption and then muted, are both still restarted.
- **`silent_greens >= 1`** is asserted on the green arms, so an arm in which the timer never
  fired at all fails instead of passing vacuously.
- **STATIC arm**: every string in the new sets is checked against `worker/sotto_worker.py`
  itself. This arm found a real defect in my first version — `silent-capture` is a worker
  `verdict=`, never a `state=`, so listing it as a state was an invented word that could never
  match. Confirmed non-vacuous: injecting `{'silent-capture'}` / `{'no-such-verdict'}` /
  `captions-emitted` makes it report three failures.

---

## 3b. The same measurement on the REAL app — `_main/_tap-restart-live-arm.py`

The lane's own path, re-run: `run.cmd --with-worker` through
`I:/!manager/scripts/spawn_hidden.py` (windowless), the real `worker/sotto_worker.py`, the real
devices, observed 160 s, then `taskkill /T /F`.

| | BEFORE `_main/_live_owner3.log` | AFTER `_main/_tap-restart-live-after.log` |
|---|---|---|
| `BRIDGE_SPAWNED` | 54 | **1** |
| respawns | 53 | **0** |
| `BRIDGE_SILENT` (the kill) | 14 | **0** |
| worker `rc=1` (= killed) | 35 | **0** |
| `BRIDGE_DEATH` | 53 | **0** |
| named `no-audio` states | 0 | **8** |
| panel painted `"No audio to transcribe"` | 0 | **8** |
| log bytes | 155 816 | 5 451 |

The whole AFTER run is one worker (`BRIDGE_SPAWNED pid=28340`), and that pid never changes:
the watchdog fires eight times, re-arms eight times, and the process is never reloaded.
The `because=` clause names the worker's own sentence, verbatim:

```
BRIDGE_SILENT_BENIGN ms=15000 pid=28340 state=no-audio
    because="device-rotated reason=flat peak=0.465216 floor=0.002" restarts=0
STATUS_APPLIED text="Audio tap silent - nothing to transcribe"
PLACEHOLDER_APPLIED title="No audio to transcribe"
```

**That line corrected a wrong claim in my own change** and it is worth recording: `reason=flat`
is NOT "below the peak floor" — the measured peak here is **0.465216 against a floor of
0.002**, i.e. the tap HEARD something and the model found no speech in the window
(`sotto_worker.py:2163` settles only on a CAPTION). `flat` means "no caption in this window,
moving on". The bridge's treatment is unchanged and still right — the worker is accounting for
the silence — but the comment and this document now say what the measurement says.

### Honest note: this run tripped the window census

`ManagerWindowCensus` went `VERMELHO-FALHA` at 09:51:23 with
`ALERTA-JANELA ... pid=44116 hwnd=1779820 nome=ApplicationFrameHost` (`alarmSet=2`), i.e. a
visible window appeared during/around this run. It is **not** claimed here that the run was
window-free: `run.cmd` launches `pythonw` (no console) and the bridge spawns the worker with
`CREATE_NO_WINDOW`, but the WebView2/pywebview panel brings its own host window, and
`_main/run-cmd-exit-oracle.json` had already recorded this same app-side startup flash as its
own **RED** census conjunct (`arms=PASS census=FAIL -> a VISIBLE window was measured`). It is a
pre-existing app-lane fact, it is named here rather than omitted, and the transient
`ApplicationFrameHost` frame is not something this lane's change touches.

---

## 4. Cross-checks

- `py -3 -m py_compile app/webview/sotto_webview.py` → **rc=0**.
- Wiring: `_on_silence` is the only body of the silence timer; `_arm_silence` is called from
  `_spawn` (once), `_pump` (per stdout line) and the new benign branch (re-arm). `no_audio` is
  reset only in `_spawn`. `_kill_and_restart('silent')` is now reachable **only** from the
  anomalous branch.
- No longer used anywhere: nothing removed. The old log line `BRIDGE_SILENT ms=...` is kept
  verbatim for the anomalous branch so existing log greps keep working.
- No visible window: the fixture is spawned by the shell under test, which passes
  `CREATE_NO_WINDOW`; the oracle itself runs in an existing console. Checked with the `windows`
  instrument (no showing signal).

---

## 5. What this does NOT do

- **The `--max-seconds 0` exit path is untouched.** If the ladder exhausts with every candidate
  flat, the worker emits `device-exhausted`/`silent-device`, prints `done` and exits `rc=3`;
  `_wait` still schedules a restart. That is a *different* respawn source from the one this lane
  measured (`rc=3` occurrences are visible in the BEFORE table) and it is out of the brief. It
  is named here rather than silently folded in.
- **A worker that wedges right after a flat rotation is no longer restarted by the silence
  timer.** That is the deliberate trade: after the worker has declared the tap carries nothing,
  "quiet" and "wedged" are not distinguishable from outside, and the alternative — killing a
  healthy worker forever on a quiet machine — is the measured defect. The backstops are the
  exit path, the hotkey, and hot reload.
- No audio fixture was played and no timeout was raised, per the brief.

---

## SELF-AUDIT

- **protocolos em falta** — I did not read the `skill://` list before starting, and the one that
  bites here is `read-before-concluding`: my first written claim about the trigger
  ("a tap ran a full window below the peak floor") was taken from the worker's NAME for the
  event instead of from the event's PAYLOAD, and the live run's `peak=0.465216` proved it wrong.
  A name is not a measurement. What I would do differently: read the `payload` of the line I am
  about to key a decision on BEFORE writing the decision's justification — here, one
  `_main/_tap-restart-live-after.log` line would have settled it at the start.
- **verificacao adicional** — the EXIT path. The cheapest version of that check is an arm where
  the fixture publishes the verdict and then exits `rc=3`; I did not add it, and the live run
  only shows that path did not fire in 160 s (`restart_exit=0`), which is a "did not fire", not
  a "cannot fire". Cost: one fixture mode + one arm, ~200 ms of runtime.
- **checkboxes novas** — MECHANIC, three of them: (1) after ANY edit to `_on_silence`,
  `_no_audio_evidence` or the fixture, run `py -3 _main/tap-restart-loop-oracle.py` and require
  `VERDICT: PASS` **and** `RED idle respawns >= 2` — a PASS with a red control that stopped
  being red is a dead gate; (2) promote the new STATIC vocabulary arm into the repo's own lint
  so any future state/verdict string added to the bridge is checked against
  `worker/sotto_worker.py` (it already caught one invented string); (3) `py -3 -m py_compile` on
  every edited file, which I did run (`rc=0` on all four files).
- **review por outro subagente** — `sim-com-escopo`: (a) whether the trigger set is right — is
  `device-rotated reason=flat` the correct evidence that the following quiet is expected, or
  should only the terminal states count? That question belongs to whoever owns the worker's
  verdict vocabulary (lane `SottoFlatEndpoint`), not to me; (b) whether the exit path should be
  gated too. I would not ask for a re-review of the implementation itself: the oracle's RED arm
  reproduces the pre-fix defect from today's bytes, so the change's effect is already falsifiable
  without a second pair of eyes.
- **gate-doubt**:
  - `verde-de-verdade:` — two runs, both named. (1) The oracle: the GREEN arms' green is real
    because the **RED** arm runs the SAME fixture through a copy of today's bytes differing by
    exactly ONE line and yields `respawns=3 / no-audio absent`, while the live file yields
    `respawns=0 / no-audio painted` — the pair diverges on identical input, which is what rules
    out pass-by-construction. I also closed the "the timer never ran" vacuity explicitly:
    `silent_greens >= 1` is asserted, so an arm where `_on_silence` never fires FAILS rather
    than passing for free. (2) The live arm: `_main/_tap-restart-live-after.log` — 1
    `BRIDGE_SPAWNED`, 0 `BRIDGE_SILENT ms=`, 8 benign re-arms, pid constant. It is a *shared*
    instrument (the real app on a machine that was also running other lanes), so I report the
    whole-file counts rather than a sampled window. One genuine hole I found in my OWN first
    version and closed: `spawns` counts the first start too, so the acceptance number is
    `respawns = spawns - 1` and both are printed.
  - `falta-no-gate:` — the gate does NOT check the EXIT path, and it cannot see a worker that
    decides to stop on its own. Scenario a future change walks through: `--max-seconds` is set
    (or the ladder exhausts on a silent device), the worker emits `silent-device` + `done` and
    exits `rc=3`, `_wait` schedules a restart, and the ~2.4 GB reload churn returns through a
    path no arm exercises — with all six arms still green.
  - `gate-melhor:` — add arm `EXIT verdict-exit3`: fixture mode `verdict-exit3` emits
    `silent-device`/`device-exhausted`/`done` and then `sys.exit(3)`, and the arm asserts
    `respawns == 0` over 3 × `silence_ms`. Run:
    `py -3 _main/tap-restart-loop-oracle.py`; that input must leave the arm **RED** today
    (today `_wait` respawns unconditionally), which is precisely how the hole stops being
    invisible.
- **confianca** — `alta` for the silence path (live measurement + six arms + a control built
  from today's bytes); `media` for "the app stops churning on an idle desktop" as a whole,
  because the exit path named above is untouched and unverified. Moving it to `alta` requires
  the `verdict-exit3` arm and a decision about whether a no-audio `rc=3` should respawn.
- **nao verificado** — (1) the exit path (`_wait` → `_schedule_restart('exit')`); (2) the hotkey
  and hot-reload restart paths; (3) the real panel DOM — the oracle asserts the bridge's
  `on_status` payload and the live log shows `PLACEHOLDER_APPLIED title="No audio to transcribe"`,
  not a DOM read; (4) whether the `ApplicationFrameHost` window the census flagged at 09:51:23
  came from this run or from another process on the box (`pid=44116 != app pid 45732`); (5) the
  other four BEFORE logs in §1 were counted but not re-run.
