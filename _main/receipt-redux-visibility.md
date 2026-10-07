# Receipt — the panel-visibility channel and the worker's stack-law switch

**Lane:** SottoReduxVisibility · **date** 2026-10-07 · **owner's law implemented:**
*"o nvidia é pro ao vivo, o parakeet redux é pro geral. o ao vivo só acontece quando o painel
ta aberto. quando ta fechado, o redux entra, e vira um transcritor LEVE ao contrario do nvidia."*

## Revisions under test (re-check these before acting on any line number here)

| file | size | mtime | sha256 (16) | mine? |
|---|---|---|---|---|
| `worker/sotto_worker.py` | 223237 B | 2026-10-07 05:17 | `1662C251113295D2` | **yes** (only the mode switch) |
| `app/webview/sotto_webview.py` | — | 2026-10-07 05:1x | `1B93F178DDCC1670` | **mine for the visibility write; edited AGAIN by another lane twice after my last edit** (239394 B → …, verified each time: my symbols intact, gate GREEN 13/13, and the real shell re-booted on the new revision — §5) |
| `app/panel/caption-formulation.js` | 35776 B | 2026-10-07 04:45:51 | `D2ADC0FF9B766DD8` | no (another lane) — **it MOVED from `app/electron/` to `app/panel/` mid-lane** |
| `app/panel/history-source.js` | 3708 B | 2026-10-07 02:34:30 | — | no (another lane; was `app/electron/history-source.js`) |
| `worker/redux_batch.py` | 8559 B | 2026-10-07 04:39:45 | — | no (another lane) |

**The tree was restructured underneath this lane** (`app/electron/` → `app/_legacy-electron/`, live panel files → `app/panel/`, and `app/package.json` now declares `"type": "module"`). Every path and hash above was re-checked AFTER that, not before — see §10.

The owner's live app was **not touched**: shell `pythonw.exe` pid 37436 (started 04:21:14) and worker
`python.exe` pid 29464 (started 04:21:15, `restarts=0`) both predate every edit here, no kill filter
ran, and `_main/webview-run.log` gained no `PANEL_VISIBILITY_*` line and no `kind=worker` restart from
this lane. The live processes keep the module they loaded, so nothing here is live until the shell is
restarted **and** the flag is passed/enabled (see §5).

---

## 1. Half 1 — the visibility channel: what it writes, and where

**File:** `H:\sotto\_main\panel-visibility.json` (path constant `PANEL_VISIBILITY_PATH`,
`app/webview/sotto_webview.py:104-135`). Frozen shape, `schema: "sotto.panel-visibility/1"`:

```json
{ "schema": "sotto.panel-visibility/1",
  "visible": false,          // window_visible(hwnd) — MEASURED, never an intention
  "since_ms": 1791359901622, // epoch ms at which THIS state began
  "age_ms": 9023,            // age AT WRITE; the authoritative duration is now_ms - since_ms
  "pid": 32372,              // the SHELL's pid (the producer)
  "reason": "boot",          // the transition that opened this state
  "transitions": 1,          // counted, so "it switched" is a number
  "writtenAt": "2026-10-07T04:58:30-03:00",
  "writtenAtEpoch": 1791359910.646,
  "staleAfterSeconds": 9.0 }
```

- **Written on every transition** — `show_panel(reason)` / `hide_panel(reason)` publish in the same
  instant as the window moves (`publish_panel_visibility`), and so does `_reassert_hidden`.
- **Refreshed on a cadence** — `PanelVisibilityWriter._loop` every `PANEL_VISIBILITY_INTERVAL_S` (3.0 s),
  re-reading the LIVE window. That is the half that records a map nobody announced (pywebview's own
  navigation-time `Show`, a hot reload): it becomes a transition with `reason=poll`, which is the flag
  that says the FILE is the only record it happened.
- **One log line per transition:** `PANEL_VISIBILITY_MODE visible=false reason=hotkey transitions=2 since_ms=…`,
  plus `PANEL_VISIBILITY_WRITER path=… interval_s=3.0` at arm time and
  `PANEL_VISIBILITY_WRITER_STOP reason=exit writes=… transitions=… errors=…`.
- Written with `panel_state.write_atomic` (temp + fsync + `os.replace`), so a reader never sees half a dump.
- **The age is not self-reported** (the `panel_state.py` rule): `writtenAtEpoch` + `staleAfterSeconds`
  exist so a reader can REFUSE a dead shell's answer; the worker's fail-safe is to read
  missing/unreadable/unknown-shape/stale as **`visible=true` = KEEP STREAMING**.

`shell.panelVisibility` is also published in `_main/panel-state.json` beside the two facts it is built
from, so a reader can see the channel drift instead of trusting it.

## 2. Half 2 — the switch: flag, default, exact behaviour

**Flag:** `--redux-when-hidden`, `action="store_true"`, `default=REDUX_WHEN_HIDDEN_DEFAULT` and that
constant **is `False`** (`worker/sotto_worker.py:1900`). Env counterpart `SOTTO_REDUX_WHEN_HIDDEN=1`
(the shell spawns this worker itself and has no general extra-flags channel — `WorkerBridge._spawn`
forwards `SOTTO_CAPTURE_MODE`/`SOTTO_AUDIO_DEVICE` by environment, so a flag with no env counterpart
would be a switch nobody can turn on). Absent both → `switch = None` → **no file read, no process, not
one extra stdout/stderr byte**.

**Knobs:** `--redux-hidden-after` (default **20.0 s**), `--redux-batch-interval` (default 15.0 s),
`--redux-max-audio` (default 120.0 s), `--redux-batch` (default `worker/redux_batch.py`),
`--panel-visibility`, `--redux-runner-timeout` (default 180 s). A `0` means "use the built-in default".

**The switch, from the worker's own stderr/stdout (`ARM on`, `--redux-hidden-after 4 --redux-batch-interval 5`):**

```
REDUX_SWITCH armed=true by=--redux-when-hidden hidden_after_s=4.0 batch_interval_s=5.0
             max_audio_s=120.0 runner=H:\sotto\_main\_redux-batch-stub.py visibility=…\vis-on.json
REDUX_VISIBILITY visible=false source=fresh age_s=0.06 hidden_since=… switch_in_s=4.0
REDUX_MODE mode=batch visible=false reason=hidden-4.0s visibility=fresh switches=1 runner=_redux-batch-stub.py
REDUX_BATCH_KICK reason=interval audio_s=5.0 kicks=1 pid=23052
REDUX_BATCH_DONE reason=interval audio_s=5.0 lines=1 rc=0 segments=1 wall_s=0.06 timeout_s=180.0
REDUX_BATCH_KICK reason=interval audio_s=5.0 kicks=2 pid=23052
REDUX_MODE mode=stream visible=true reason=visible-again switches=2 segments=2
REDUX_BATCH_KICK reason=stream-end audio_s=2.0 kicks=3 pid=23052
```

**"Stops the streaming capture" means the streaming DECODE — the tap keeps running**, because a batch
pass over "the accumulated audio" has no audio to accumulate from a closed device. Measured, and this
is the cleanest proof in the run: `WORKER_STATS … redux_mode=batch` shows **`chunks=18` frozen at three
consecutive 4 s ticks** while the panel is hidden (blocks kept arriving: 120 → 160 → 201), and `chunks`
grows again (21, 28, 35, 39) only after `mode=stream`. The per-560 ms encoder pass is what stopped; the
tap never closed, so nothing was lost.

**Back to streaming IMMEDIATELY, without losing the tail:** the resume is decided on the next 100 ms
block, and the audio accumulated since the last interval pass is flushed by an off-thread batch
(`reason=visible-again`/`stream-end`) whose lines come out through `drain_captions()` while the stream is
already live again. Ordering travels on `start`/`end`, not on arrival.

**Every batch line, as it lands on stdout** (`final:true` is the worker's route vote; `producer` is the
payoff):

```json
{"type":"caption","text":"redux-stub segment 01 [0.00-5.00s of 5.00s]","start":0.0,"end":5.0,
 "final":true,"producer":"redux","producerModel":"redux-batch-stub (NOT the real engine)",
 "route":"redux-batch"}
```

and the run's `done` carries the split, never a sum: `"captions": 33, "reduxCaptions": 3,
"reduxSegments": 3, "reduxBatchSeconds": 12.0, "reduxRunnerFailures": 0, "reduxSwitches": 2,
"reduxArmed": true, "reduxVisibilityReads": 340, "reduxVisibilityFallbacks": 0` — all `redux*` keys are
added **only when the switch exists**, which is what makes "flag off = today's bytes" checkable.

**Three gates must ALL be open** before the first chunk is cut: (1) the flag/env; (2) **the runner must
exist on disk** — otherwise the switch is REFUSED loudly and the run keeps streaming (the HARD RULE: today
the streaming engine is the only transcriber, so switching to an engine that is not there means zero
transcription while the owner is not looking); (3) the file must be FRESH and say hidden for longer than N.

**One consequence I had to fix, and it is the kind of thing that would have shipped broken:** the verdict
chain asked `chunks == 0` → `buffer-never-reached-chunk-size` BEFORE any caption test, and the panel paints
a non-healthy `done` verdict as an ERROR. The app comes up HIDDEN, so with the flag on a run can spend its
whole life on the light path and cut not one chunk — a run that transcribed the owner's audio would have
been announced as a failure. `decide_verdict` now sums `captions + redux_captions` into `emitted` and the
chunk test is `chunks == 0 and emitted == 0`. With the flag off `redux_captions` is always 0, so every
branch is byte-identical to before.

**The memory floor (`--redux-min-free-mb`, default 4600 MB), added after a consultation.** This is the
one place where the lane changed a design decision on advice rather than on measurement, so both the
advice and my treatment of it are on the record (§9). A batch pass is DEFERRED — not attempted — while
free physical memory is below the floor, because the runner's documented peak is ~3.9 GB and a failed
allocation loses the pass; the audio stays buffered and the next tick retries. **The tail is the
exception, and deliberately:** `visible-again`/`stream-end` have no next tick, so a deferral there would
simply DROP the owner's last minute. Tails attempt under pressure and log
`REDUX_BATCH_LOW_MEMORY … attempting=anyway`, so the attempt is a receipt rather than a silence. A
measurement that fails returns `None` and does NOT block (a failed measurement is not evidence of
pressure). `--redux-min-free-mb 0` explicitly disables the gate; `done.reduxBatchDeferred` and
`WORKER_STATS … redux_deferred=` publish how often it fired.

## 3. Instrument 1 — the probe (both colours, one command)
```
python _main\_redux-visibility-probe.py
```

Runs the REAL worker through the REAL live loop fed from a FILE (`SOTTO_FILE_TAP` — **no audio device
opened, no hotkey registered, no shell in the process**), with the visibility file written by the REAL
shipped writer class (`PanelVisibilityWriter`, imported headless) and flipped exactly as
`SottoShell.publish_panel_visibility(reason)` flips it. One command, `VERDICT: PASS — 7/7 arm(s)`,
in the order printed by the run:

| arm | runner | flag | measured |
|---|---|---|---|
| `off` | stub | **absent** | `mode_lines=0 kicks=0 redux_captions=0`, `stream_captions=22`, `chunks=25`, no `reduxCaptions` key on `done` → **byte-for-byte today's run** |
| `on` | stub | present, hidden 16 s | `switches=2`, `batch=1 stream=1`, `kicks=3`, `redux_captions=3`, `stream_captions=29`, `chunks=37`, `verdict=captions-emitted` |
| `real` | **`worker\redux_batch.py`** | present, hidden 24 s | `switches=2`, `kicks=2`, `redux_captions=4` (**real Portuguese text**), `stream_captions=41`, `chunks=45`, `verdict=captions-emitted` |
| `missing` | path that does not exist | present | `mode_lines=0 kicks=0`, `done.reduxArmed=false`, 22 streaming captions → **REFUSED, kept streaming** |
| `stale` | stub | present, dump 10 s old | `mode_lines=0`, `reduxSwitches=0`, 22 streaming captions → a dead producer's `visible:false` was **not obeyed** |
| `fail` | always-non-zero runner | present, hidden 15 s | `batch=1`, `kicks=3`, `REDUX_BATCH_DONE … lines=0 rc=4` ×3, `REDUX_BATCH_FAILED reason=runner-rc … failures=3 tail="…DELIBERATE FAILURE…"`, 3 × `redux-batch-empty` status, `reduxRunnerFailures=3`, **streaming unaffected** (12 captions, `verdict=captions-emitted`) |
| `throttle` | stub | present, **`--redux-min-free-mb 999999`** | 90 interval passes deferred (`REDUX_BATCH_DEFERRED reason=low-memory … held_s=4.0 → 12.9` — **the audio is KEPT**), `kicks=1` and it is the TAIL (`reason=stream-end audio_s=12.6`) after `REDUX_BATCH_LOW_MEMORY … attempting=anyway`, and the one pass transcribed the whole window (`redux-stub segment 01 [0.00-5.00s of 12.60s]`, `02`, `03`) → **nothing lost** |

Every arm exits `rc=0` with `verdict='captions-emitted'`, i.e. the batch engine's lines count as real
captions and the `done` word stays healthy while the panel is hidden — which is the whole point of §2's
verdict fix.

The two counter-checks that would have caught the bug I actually shipped mid-lane: the probe asserts
every `reason=interval` kick carries `audio_s >= batch_interval_s - 0.6` and caps the kick count. The
first version of `maybe_kick` delegated straight to the flush path, so on the live loop (one call per
100 ms block) it kicked a batch **every time 1 s of audio had accumulated — 12 invocations for a 16 s
hidden window**, i.e. a queue of model loads instead of a batch cadence. Fixed; the same window now
produces 3. The probe's own first run also died printing a worker line the console cp1252 could not
encode and took three unrun arms with it; `say()` now escapes only the console copy and the log stays UTF-8.

## 4. Instrument 2 — the source gate, BOTH colours in one command

```
python _main\redux-flag-gate.py --neg-arm
```

```
[shipped] claims: env-optin=OK fail-safe=OK flag-exists=OK flag-guarded=OK hard-rule=OK
          payload-guarded=OK shell-loop=OK shell-measured=OK shell-transitions=OK stamp=OK
          switch-wired=OK verdict-counts-batch=OK
[shipped] VERDICT GREEN (12/12 claims hold)
mutants built: 11/11 (each a COPY in _main\_redux-gate-mutants)
NEG-VERDICT: GREEN — all 11 mutants moved exactly their own claim: flag-exists, flag-guarded,
             env-optin, switch-wired, stamp, hard-rule, fail-safe, payload-guarded,
             verdict-counts-batch, shell-loop, shell-measured
GATE-VERDICT: GREEN — shipped pair holds every claim AND every claim is load-bearing
```

**RED (as shipped = impossible to fake):** each mutant reverts exactly ONE claim — `REDUX_WHEN_HIDDEN_DEFAULT
= True` → `flag-exists` RED; `if redux_optin:` → `if True:` → `flag-guarded` RED; `REDUX_PRODUCER = "live"`
→ `stamp` RED; `self.armed = True` → `hard-rule` RED; `_fallback` returning `False` → `fail-safe` RED;
the batch `continue` → `pass` → `switch-wired` RED; `emitted` sum removed → `verdict-counts-batch` RED;
the cadence loop disabled → `shell-loop` RED; `observe` returning `False` → `shell-measured` RED. Only
the named claim moves in each case (checked, not asserted).

The gate earned its keep on itself: its FIRST `fail-safe` claim counted only `return self._fallback(...)`
sites inside `read()`, so the mutant that made `_fallback` return `False` left it GREEN — a presence test
certifying a value it never read, which is the exact defect class the gate exists for. The claim now reads
the fallback's own return.

## 5. Instrument 3 — the SHELL's own show/hide, executed (no window)

```
python _main\_redux-shell-visibility-arms.py
```

Runs the real `SottoShell.observe_panel_visible` / `show_panel('hotkey')` / `hide_panel('hotkey')` /
`start_panel_visibility()` with the Win32 boundary replaced (no WebView2 object, no `create_window`, no
window, no device, no hotkey), then reads the file they wrote and the `PANEL_VISIBILITY_MODE` lines they
logged. Verdict `GREEN`:

```
ARM boot      start_panel_visibility() -> True, path=_main\_redux-shell-visibility.json
ARM show      dump visible=True  reason=hotkey   log: …MODE visible=true  reason=hotkey transitions=2
ARM hide      dump visible=False reason=hotkey   log: …MODE visible=false reason=hotkey transitions=3
ARM show-fail dump visible=False (the window refused to map)   ← publishes the WINDOW, not the intention
ARM cadence   writtenAtEpoch 1791359109.033 -> 1791359109.924 transitions 3 -> 3
ARM unannounced window mapped with no show() call -> dump visible=True reason=poll transitions=4
ARM stale     worker.PanelVisibilityReader on a 60 s old dump -> visible=True why=stale(age=60.0s>limit=5.0s)
ARM fresh     the same file, fresh -> visible=False why=fresh
```

**And on the REAL shell** (the app itself, `--dump-dom --no-hotkey`, no worker spawned —
`WORKER_AUTOSTART=declined reason=measurement-flag(--dump-dom)`), `SHELL_EXIT rc=0`:

```
sotto: PANEL_SHOW_REFUSED reason=not-asked … count=2 cure=_gate_form_show
sotto: PANEL_VISIBILITY_WRITER path=H:\sotto\_main\panel-visibility.json interval_s=3.0
sotto: PANEL_VISIBILITY_MODE visible=false reason=boot transitions=1 since_ms=1791359901622
sotto: PANEL_VISIBILITY_WRITER_STOP reason=exit writes=4 transitions=1 errors=0
```

`writes=4` over a 9 s life at a 3 s cadence = the boot dump plus three refreshes, one transition;
`_main/panel-visibility.json` then read `pid=32372` (the shell's own pid), `visible=false`. This is the
only check that proves the new call is REACHABLE from the real startup path — a typo in `_on_loaded`
would have broken the owner's app on its next launch, and a source gate cannot see that.

## 6. The payoff, and the blocker that was found and fixed by another lane

My side stamps `producer:"redux"` on every batch line (necessary). On my first run the FULL path was
**not** open, and that was measured, not read:

```
node _main\_redux-producer-path.js         # FIRST version, 04:44
ARM B  meta keys the engine built = [route, start, routeSource]     ← producer DROPPED
ARM B  isCanonicalLine(that meta) = false      lines the transcript takes = 0
```

`app/panel/caption-formulation.js:408` called `onCommit(line, reason, {route, start, routeSource})` — a
new three-key object — so the field died before `panel.js → recordHistory → isCanonicalLine` ever saw it.
**The lane owning those files fixed it at 04:45:51** (`bufferProducer` / `committedProducer()`, plus a
new `routeSource` value `'worker-stamped-producer'`). The instrument now stands guard over the OPEN path,
with the control that makes it attributable to the field — and it was re-pinned after the file MOVED from
`app/electron/` to `app/panel/` (§10):

```
node _main\_redux-producer-path.js        # rewritten, current (engine path printed by the run)
ENGINE  app\panel\caption-formulation.js
GUARD   app\panel\history-source.js
ARM A  isCanonicalLine({producer:'redux',route:'final'}) = true
ARM A  isCanonicalLine({route:'final'}) = false      ARM A  isCanonicalLine({producer:'live',…}) = false
ARM B  REDUX line   -> engine meta keys [producer, route, routeSource, start], producer="redux"
                       isCanonicalLine = true      transcript takes 1/1
ARM C  LIVE line    -> engine meta keys [route, routeSource, start], producer=undefined   (CONTROL)
                       isCanonicalLine = false     transcript takes 0/1
PRODUCER-PATH-VERDICT: GREEN
```

ARM C is the owner's law as an executable arm: the two fields are again two sources, and the RED this arm
now reports is "the drop came BACK".

The real engine also ran standalone against a 16 kHz mono WAV cut from `_main/pt-br-sample.wav`
(`python worker\redux_batch.py --wav … --json`): two caption lines and one `{"type":"result"}` line, all
`"producer": "redux"`, `real_time_factor 13.29`. The worker emits only the `type=="caption"` lines (the
probe asserts no `result` line leaks onto its stdout).

## 7. What is NOT verified, and what could not be done

1. **The `fail` arm's first attempt failed for an ENVIRONMENTAL reason, and the reason is itself a
   finding.** It exited 2 with
   `RuntimeException: [ONNXRuntimeError] 6 : RUNTIME_EXCEPTION : … bad allocation` while loading the
   streaming model, because **another lane's `_main\redux-long-probe.py run --cases all --device cpu`
   (pid 17832, started 04:56:03) held a `redux_batch.py` child on a **300 s** WAV at **3571 MB RSS**,
   leaving 3137 MB free on this box.** I did not kill it (not mine), waited for memory (19 GB free), and
   re-ran: the arm then PASSED. So the failure path IS verified, and the transient allocation failure is
   recorded as a real constraint rather than papered over: **the real runner's documented 3.9 GB peak
   happens while the streaming model (1.5 GB resident in the owner's live worker) is still loaded — this
   switch does NOT unload it — and a sibling process was MEASURED failing to allocate under exactly that
   load.** `--redux-when-hidden` with the real engine needs ~4 GB of transient headroom here; that is the
   owner's call, not something this lane may tune away.
2. **The DEFAULT `--redux-hidden-after 20.0` was never run** — the probe uses 4 s to keep the arm short.
   The constant and its wiring are gated; the 20 s figure itself is asserted, not measured.
3. **`REDUX_BUFFER_TRIMMED` (`--redux-max-audio`, 120 s) was never exercised** — it needs >120 s of hidden
   audio. Bounded-buffer trimming is therefore unverified.
4. **The switch is not live in the owner's app**, by construction: the running shell keeps the module it
   loaded (no `PANEL_VISIBILITY_*` line in `_main/webview-run.log`), the running worker was started at
   04:21:15 (before every edit), and the flag defaults OFF and is not passed by `WorkerBridge._spawn`.
   Turning it on in the shipped app needs `SOTTO_REDUX_WHEN_HIDDEN=1` in the shell's environment (or a
   `_spawn` change in a file this lane may only edit for the visibility-write part) **plus a restart**.
5. **No fresh flash census.** I launched the real shell twice for `--dump-dom` and I do **not** claim no
   window appeared: the 60 s house census cannot prove absence and I did not run a 25 ms census of my own.
   What the shell's own log says is `PANEL_VISIBILITY_ON_SCREEN visible=false` with 2 × `PANEL_SHOW_REFUSED`
   (`cure=_gate_form_show`), which is that gate's claim, already owned and measured by another lane.
6. **Legacy Electron arm not exercised.** `producer` survives the WebView2 shell verbatim
   (`WorkerBridge._consume` builds `meta` from every key except `type`/`text`) and the Electron
   `worker-bridge.js` builds a FOUR-key meta by hand (`source/start/end/model/final`) — so the payoff is a
   WebView2-shell fact; the Electron arm would still drop the field. Electron is documented as legacy, so
   this is a note, not a defect claim.
7. **The harness is a file tap, not a device.** Every arm used `SOTTO_FILE_TAP` — no audio device was
   opened anywhere in this lane (house rule), so the switch's behaviour under a real WASAPI tap, a device
   rotation, or `AUDCLNT_E_DEVICE_IN_USE` is untested.

## 8. Files this lane owns, and what it deliberately did not touch

**Edited (my two files, each only its half):** `app/webview/sotto_webview.py` (visibility-write only: `PanelVisibilityWriter`, the constants,
`start_panel_visibility`/`observe_panel_visible`/`publish_panel_visibility`/`panel_visibility_snapshot`,
the publish calls in `show_panel`/`hide_panel`/`_reassert_hidden`, the stop in `request_exit`), and
`worker/sotto_worker.py` (the mode switch only: constants, `PanelVisibilityReader`, `ReduxHiddenSwitch`,
the args, the `asr_thread` consumption, the `done`/`WORKER_STATS` fields, and the verdict-batch counting).

**New in `_main\`:** `_redux-visibility-probe.py` (the probe), `redux-flag-gate.py` (the gate),
`_redux-producer-path.js` (the payoff instrument), `_redux-shell-visibility-arms.py` (the shell half
executed), `_redux-batch-stub.py` (STUB — a stand-in that says so in every line), `_redux-batch-fail.py`
(the always-failing runner), and the logs they wrote.

**NOT touched:** `worker/redux_batch.py`, `app/panel/*`, `app/_legacy-electron/*`, `AGENTS.md`, the panel
files, `run.cmd`.

## 9. The consultation the house rule asks for, and what I did with it

`docs/tools/consultgpt.md` (added mid-lane) asks for a ChatGPT consultation when a design question is
open. I asked about the one genuine open tradeoff — the ~5.4 GB peak of a batch pass beside the resident
streaming model — with `gpt --no-code --session sotto-redux-memory --prompt-file …`. **The first attempt
failed in the documented silent mode:** the saved session holds my prompt and a **0-char response**, with
`Composer not visible within 25000ms` in its own log. I read it back with `gpt --show --session …` (which
is how I know the response is empty rather than late) and retried with a shorter prompt; that one
answered.

**ACCEPTED — one recommendation, implemented and gated:** *"gate batch execution on measured system
memory pressure"*. That is the `--redux-min-free-mb` floor of §2 with its interval/TAIL split, its own
gate claim (`memory-gate`), and its own probe arm (`throttle`). It directly serves the invariant the
consultation was told to respect ("transcription must never simply stop") because a deferred pass keeps
its audio instead of losing it to a failed allocation.

**REJECTED FOR NOW — one recommendation, with the reason:** *"trim/empty the hidden worker's working set
before batch startup (`EmptyWorkingSet`)"*. It is a real idea — resident pages drop while the model stays
loaded, so resume should stay fast — but the consultation itself flags it as needing execution testing
(`Working-set eviction is not the same as unloading the model … pages may fault back in`), and the cost
of being wrong is paid on the Alt+C path, where a panel that answers slowly is the exact failure this
project has already been burned by. I am not going to change the hot path on an untested mechanism at the
end of a lane; it is recorded here as the recommended next experiment, with the two numbers to measure
(Alt+C→first caption latency, and batch peak RSS/commit).

**NOT ACTED ON:** its closing note that *"if paging latency still violates the resume requirement,
serialization (option 3) is the safer fallback—not option 1"*. That is a recommendation to reconsider the
owner's own rule (streaming lives exactly as long as the panel is open), and the memory evidence for it
is a **single transient** allocation failure I observed under another lane's 3.5 GB load — not a
demonstrated steady state. It is the owner's trade to make, not mine.

## 10. The tree moved underneath this lane (and what it broke, and how I found out)

While this lane was finishing, another lane restructured the repo: `app/electron/` → `app/_legacy-electron/`,
the live panel files → `app/panel/`, and **`app/package.json` gained `"type": "module"`**. Three
consequences, each caught by an instrument rather than by reading:

1. `node _main\_redux-producer-path.js` went from GREEN to `SETUP ERROR: no such file` — the paths it
   hard-coded were gone. It now tries `app/panel/` → `app/electron/` → `app/_legacy-electron/`, **prints
   which one it used**, and is GREEN again on `app/panel/` (both colours, §6).
2. A `require()` of `app/panel/caption-formulation.js` then returned an **empty namespace**
   (`keys: []`, `typeof createEngine: undefined`) — because the file is under a `"type": "module"`
   boundary, so Node loads it as ESM while its body assigns the CommonJS `module.exports`. The instrument
   now loads it the way BOTH of its real consumers do — the source is evaluated with `module`/`exports`
   AND `window` present, exactly as the panel's `<script>` tag does — so it is immune to where the file
   sits. That fix is why the verdict above is a VERDICT and not a setup error.
3. `app/webview/sotto_webview.py` was edited twice by another lane after my last edit. Re-checked each
   time: my symbols intact (4 × `PANEL_VISIBILITY_PATH`, the writer class, all three methods, both
   publish sites), `python -m py_compile` clean, the gate GREEN 13/13 against the new revision, and the
   real shell re-booted on it (`PANEL_VISIBILITY_WRITER` → `PANEL_VISIBILITY_MODE visible=false
   reason=boot` → `writes=4` → `SHELL_EXIT rc=0`).

## 11. House-rule compliance, stated plainly

- **No visible window was created by me.** Every worker/child was spawned with `CREATE_NO_WINDOW`
  (`0x08000000`) and `pythonw.exe` (the probe prints `pythonw=yes`); every file-tap arm passes
  `SOTTO_FILE_TAP` and never a device. The two shell launches passed `--no-hotkey` and
  `--dump-dom`/`--exit-after` (so `SINGLE_INSTANCE_SKIPPED` and no worker spawned). **I do not claim no
  window appeared** — that needs a 25 ms census, which is another lane's gate and I did not re-run it;
  what I have is the shell's own `PANEL_VISIBILITY_ON_SCREEN visible=false` + `PANEL_SHOW_REFUSED ×2`.
- **No audio device was opened** in any run of this lane, and **no global hotkey was registered**.
- **The owner's live app was never touched**: no kill filter ran; the live shell (pid 37436) and worker
  (pid 29464) predate every edit and are still alive; `_main/webview-run.log` gained no
  `PANEL_VISIBILITY_*` and no `kind=worker` restart from me. The one process I found that was NOT mine
  (a 3.5 GB `redux_batch.py` under another lane's `_redux-long-probe.py`) I left strictly alone.
- **One honest caveat about "flag off = today"**: it is `switch is None` (no read, no process, no extra
  byte) plus a gate claim and a probe arm — `byte-identical` is therefore *argued and checked at the
  branch level*, not proven by diffing two full runs' bytes.
