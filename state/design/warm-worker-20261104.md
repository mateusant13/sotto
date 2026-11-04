# Warm engine — a first caption inside 3 s without a visible window, a stutter, a double load or a stray process

**Status:** DESIGN ONLY. Nothing here is implemented and no number here is a claim about code that does
not exist. Every measured number carries the command or receipt that produced it; anything derived by
arithmetic from measured terms is marked `[INFERENCE]` and is an obligation for the implementing lane,
not a result.

**Lane:** `lane/warm-worker-design-2`, worktree `H:/sotto-wt/WarmWorkerDesign-2`.
**Date:** 2026-11-04.
**Sources re-read for this design:** `AGENTS.md` (law), `_main/receipt-20261104-boot-fast.md`,
`_main/receipt-20261104-worker-churn.md`, `_main/windows-autostart/README.md` +
`_main/windows-autostart/sotto-task.xml`, `app/webview/sotto_webview.py:16852-18200` (`WorkerBridge`),
`:6240-6320` (the job object), `:6313-6380` (single-instance lock), `:12986-13173` (`start_worker`),
`:13271-13340` (`revive_worker`), `:14086-14100` (`engine_park_reason` / `set_engine_park`),
`:15668-15700` (`_pause_shell`), `:15990-16005` (`_do_worker_restart`), `app/webview/load_shedding.py` (`LoadProbe`, `LoadShedding`,
`PARK_LEVELS`, `PublishedView`), `worker/sotto_worker.py:673-700` (`hold_idle_slot`), `:5144-5210`
(`resume_catch_up`), `_main/panel-visibility.json` (live), `_main/tap-silent-desktop-oracle.py`,
`_main/console-window-audit.py`, `_main/load-shedding-oracle.py`, `_main/worker-churn-oracle.py`,
`H:/sotto-wt/BootFast/_main/time-to-first-caption-oracle.py`.

---

## 0. The question, as a negation (the falsifier this design must survive)

> *No warm process exists. The shell must therefore load the graph itself before it can caption, and the
> first caption can never precede that load.*

That sentence is today's law and it is measured twice:

- `_main/time-to-first-caption-oracle.py --log H:/sotto/_main/webview-run.log --pid 32540` →
  `first caption : 09:58:29.360 +65037 ms text="audience"`, `VERDICT: FAIL` against the 3000 ms limit.
- Isolated worker boot, file seam, machine idle (`_main/receipt-20261104-boot-fast.md` §3(b)):
  `model-loaded 5 624 ms (load_s=5.44)` → `capture-started 7 556 ms` → `primeira legenda 9 014 ms`.

The load is not the whole 65 s — 44.6 s of it is the deliberate `tap-silent-desktop` hold on a silent
machine, and 2 981 ms is the decoder closing its first line. But the load is the part the design can
remove from the shell's critical path, and removing it is the only route to 3 s:

    graph             4.6 - 5.4 s   (4 802-5 624 ms, receipt §4 table)
    front end         1.7 - 3.4 s   (og.Model, 1 711-3 400 ms, receipt §4 mechanism block)
    device ladder     1.79 s        (LADDER_ALONE_S, receipt §4)
    first line close  2.98 s        (CAPTION_IN - BRIDGE_METER = 65 014 - 62 033, oracle table)
    ---------------------------------------------------------------
    cold floor        ~9 - 13 s     (measured 9.0 s file seam; live: capture-started at +17.4 s
                                     under WebView2 contention, first caption +65 s with 44.6 s
                                     of that being the silent-desktop hold)

`3 s` is unreachable from cold. It is reachable from a graph that is already loaded **and holding
audio**. This document is the ownership structure that makes such a process safe to have.

---

## 1. Invariants

| id | invariant | the structure that makes it true, not the discipline |
|---|---|---|
| **INV-1 single loader** | In one session at any instant at most ONE process holds the model graph, and the shell can only *attach* to it — never load a second copy. | The graph is held only by the process that owns the mutex `Local\SottoWarmEngine.<session>.<model_key>` and the `FILE_FLAG_FIRST_PIPE_INSTANCE` pipe of the same name. The shell's `self.bridge` field is the admissibility token for every spawn path (`start_worker` already refuses when `self.bridge is not None`, `sotto_webview.py:13137`), so adoption and cold start share one gate instead of two. |
| **INV-2 lifetime asymmetry** | The shell owns no process that must outlive it. `BRIDGE.stop` can only ever kill a child the shell spawned. | The engine is created by a Task Scheduler action, so its parent is the scheduler, never the shell and never inside `Local\SottoShell`'s kill-on-close job object. Park is a message on a pipe, not a kill. |
| **INV-3 cold is the floor** | Every warm path has a cold fallback with today's behaviour and today's numbers; no acceptance number depends on the engine being alive. | Attach has a hard deadline and an abort that constructs a normal `WorkerBridge`; the cold path is not modified. A missing, corrupted or stale engine is *slow*, never *wrong*. |
| **INV-4 the gate has a veto** | The engine never loads, taps or decodes at `alta`/`muito-alta`, and releases the weights after `muito-alta` persists. | Both ask points read the same two sources as the worker (`LoadProbe` measured + the shell's published `shed`), take the WORSE, and `unknown` is not permission for a *preload*. |
| **INV-5 a caption is a fact about audio** | No line is painted whose audio age exceeds the existing budget (`CAPTION_PAINT_LAG budget_ms=1500`), and replay is newest-first and bounded. Audio older than the bound goes to history only, carrying its provenance. | The `attach` reply's replay carries `audio_ms` per line; the shell drops to history-only when `audio_ms > WARM_BACKLOG_LIVE_MS`, and the meta carries `src=warm-replay`, so a stale paint announces itself (the SilentFallback lesson). |
| **INV-6 no orphan output** | Nothing decodes while no consumer exists, and there is exactly one writer of history — the shell. | The engine decodes only at attach; while parked it holds weights and, in mode C, raw PCM in a RAM ring that nothing reads out. There is no spool file and no second history path. |

`INV-2` is the one that decides the whole shape. Everything else follows from it.

---

## 2. Ownership and lifetime — the exact mechanism for a process that outlives the shell

### 2.1 Why the obvious mechanism is refused before it is proposed

`BRIDGE.stop` (`sotto_webview.py:17373`) is `child.kill()` — `TerminateProcess` on the PID the shell
itself spawned. `start_worker` carries a comment that names the incident (`os._exit` does not kill a
child, `:13117`), and the shell arms a job object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` precisely so
that the whole tree dies when the shell does (measured cure, `job-object` gate pair in `AGENTS.md`:
before the cure four `msedgewebview2.exe` survived `taskkill /T /F`; after it, *"da arvore ANTIGA ainda
vivos: NENHUM"*). A child that must outlive the shell therefore contradicts two existing cures at once.
`CREATE_BREAKAWAY_FROM_JOB` would "work" only by adding `JOB_OBJECT_LIMIT_BREAKAWAY_OK` to that job,
i.e. by making every future child able to escape the kill — refused (R1).

### 2.2 The mechanism: the engine is a Task Scheduler action, not a `Popen`

Precedent in this tree, measured: `_main/windows-autostart/README.md` —
*"a tarefa corre a app num contexto proprio: medido, `shell pid=33248 ppid=14640` (Task Scheduler) e
`worker pid=35872 ppid=33248`"*. A `Start-Process` from a session died with the session; the same
command through `\Sotto` did not. That is exactly the property needed, already measured on this box.

**Registration.** `_main/warm-engine/warm-engine-task.xml`, modelled line-for-line on
`_main/windows-autostart/sotto-task.xml`, with four deliberate differences:

| field | value | why |
|---|---|---|
| `Triggers` | **none** (no `LogonTrigger`) | a logon load is refused (R4): at logon this box is `alta` or worse — live evidence: `_main/panel-visibility.json` reads `"shed": "muito-alta"` at `writtenAt 2026-11-04T11:28:35-03:00`. The engine loads on an idle window, not on a login storm. |
| `MultipleInstancesPolicy` | `IgnoreNew` (same as `\Sotto`) | first of the three twin locks. |
| `ExecutionTimeLimit` | `PT0S` (same as `\Sotto`) | the default 3-day limit would silently kill a warm engine and turn every boot after day 3 back into a cold boot. |
| `RestartOnFailure` | `count=2`, `interval=PT60S` | a crash-looping engine must not become a load loop — the churn receipt measured `1,9 GB` per reload and 88 reloads in 17 minutes is the failure class (R3). |
| `Hidden=true`, `InteractiveToken`, `LeastPrivilege`, `AllowStartOnDemand=true` | as `\Sotto` | no window, and it runs in the owner's session because WASAPI loopback is per-session. |

**Start.** The shell never spawns the engine; it *asks the scheduler to*:
`schtasks /run /tn SottoWarmEngine`, launched through `_main/hidden-launch.py` (the only sanctioned way
to start `schtasks` in this tree; `console-window-audit.py` sees any other site). The resulting process's
parent is the Task Scheduler service, so it is not in the shell's job and `BRIDGE.stop` has no PID to
kill. **The shell does not even know the engine's PID at spawn time** — it learns it from `WARM_HELLO`,
which is the correct direction: a number the shell did not create is a number the shell cannot kill by
accident.

**Identity, for any instrument that must kill it** (the AGENTS rule: a kill filter names the artefact,
`pid` + start time, never `CommandLine`): the engine writes `_main/warm-engine.pid` on start and removes
it on exit:

    pid<TAB>process_start_time<TAB>session_id<TAB>model_key<TAB>plugin_sha256<TAB>started_at_iso

`_main/warm-engine.log` carries the same identity in `WARM_ENGINE_START` / `WARM_ENGINE_EXIT` lines.

### 2.3 What closes it — exhaustive, so "a stray process" has no room

| trigger | who acts | mark | result |
|---|---|---|---|
| The owner's setting is off, or *Quit Sotto* with keep-warm off | shell sends `{"op":"quit"}` | `WARM_EXIT why=quit` | exit, task back to Ready |
| No attach for `WARM_PARK_TTL_S` (600 s — the same meaning and value as the worker's `IDLE_HOLD_MAX_S = 600.0`) | the engine itself | `WARM_EXIT why=idle-expired` | exit, 1.9 GB returned |
| `muito-alta` sustained for `WARM_RELEASE_S` (120 s) | the engine | `WARM_RELEASE why=shed-muito-alta` | **release, not exit** (the `REDUX_ENGINE_RELEASE` law); reloads on the next `leve` window |
| `run.cmd --warm-engine-stop` | CLI → pipe `quit`; on no answer, kill by `pid`+start time from the pid file | `WARM_EXIT why=cli-stop` | exit |
| logoff / session end | Windows | — | gone with the session, by construction; the engine needs no receipt to die |
| crash | OS | pid file left stale; next shell boot rewrites it | `RestartOnFailure` ≤ 2 |

The engine creates its OWN job object with `KILL_ON_JOB_CLOSE` for its own children. It has none today;
the job is there so that "the engine has no orphan child" is structural rather than accidental.

### 2.4 State machine — engine

    ABSENT ──(task /run)──▶ STARTING ──(mutex taken, pipe created)──▶ UNLOADED
      ▲                        │                                        │
      │                        └─(mutex or FIRST_PIPE_INSTANCE taken)─▶ TWIN_EXIT (rc=0)
      │                                                                 │
      │                                            (gate=leve, probe fresh)
      │                                                                 ▼
      │                                                            LOADING
      │                                                                 │ (graph + front end built)
      │                                                                 ▼
      │   (TTL / quit / muy-alta release)                         PARKED_CLOSED   ◀──────┐
      │                                                                 │  (attach)        │
      │                                                                 ▼                  │
      │                                                            ATTACHED ──(peer EOF)──▶ DETACHED
      │                                                                 │                  │
      │                                                    (owner opt-in)               (re-attach)
      │                                                                 ▼                  │
      └──────────────── exit ◀──────────────────────────────── PARKED_TAP ────────────────┘
                                                                        (census-changed while unattached → PARKED_CLOSED)

Every edge writes one line. There is no edge without a mark, and no mark without an edge.

**Transitions, precisely.**

| from → to | trigger | guard that must pass | mark |
|---|---|---|---|
| ABSENT → STARTING | `schtasks /run` (shell boot, or CLI) | — | `WARM_ENGINE_START pid= started_at= model= plugin_sha=` |
| STARTING → TWIN_EXIT | `CreateNamedPipeW(name, FILE_FLAG_FIRST_PIPE_INSTANCE, 1 instance)` → `ERROR_ACCESS_DENIED`, or `CreateMutexW` → `ERROR_ALREADY_EXISTS` | — | `WARM_TWIN_EXIT rc=0 why=pipe-exists` — **the process ends**, it does not linger |
| STARTING → UNLOADED | pipe + mutex acquired | identity file written | `WARM_PIPE_READY name= instances=1` |
| UNLOADED → LOADING | idle rehearsal timer | **G1** (see §5) | `WARM_LOAD_BEGIN commit_pct= cpu_pct= level= shed=` |
| LOADING → PARKED_CLOSED | `model-loaded` + front end built | — | `WARM_LOAD_MS ms=` / `WARM_LOAD_REFUSED why=g1` |
| PARKED_CLOSED → ATTACHED | `attach` arrives | hello sha + model_key match, gate not `PARK_LEVELS` | `WARM_ATTACHED ms= mode=` |
| PARKED_CLOSED → PARKED_TAP | keep-warm enabled, gate `leve` | **G2** | `WARM_TAP_OPEN mode=warm-tap` |
| PARKED_TAP → ATTACHED | `attach` | hello match | `WARM_ATTACHED mode=warm-tap ring_ms=` |
| ATTACHED → DETACHED | client EOF, or `detach` op | — | `WARM_DETACHED why=peer-eof` / `why=shell-closing` |
| DETACHED → PARKED_TAP | keep-warm on | **G2** | `WARM_TAP_HELD clients=1` |
| DETACHED → PARKED_CLOSED | keep-warm off, or `census-changed` while unattached | — | `WARM_TAP_CLOSED why=census-changed unattached=true` |
| PARKED_* → UNLOADED | `muito-alta` ≥ `WARM_RELEASE_S` | **G4** | `WARM_RELEASE ms_resident= why=shed` |
| any → ABSENT | quit / TTL / crash | — | `WARM_EXIT why=` / `WARM_ENGINE_EXIT rc=` |

### 2.5 State machine — shell, and how a second shell adopts instead of spawning a twin

    BOOT ──▶ ATTACH_TRY ──(hello ok, sha ok)──▶ WARM_BRIDGE (self.bridge = WarmPipeBridge)
                │   │
                │   ├─(no pipe / busy / timeout / sha mismatch)──▶ COLD_BRIDGE (WorkerBridge, today's code)
                │   └─(no pipe AND no mutex)──▶ COLD_BRIDGE + fire `schtasks /run` so the NEXT open is warm
                ▼
           ATTACH_LOST (pipe EOF mid-run) ──▶ COLD_BRIDGE via the existing restart ladder

`ATTACH_TRY` is synchronous with a deadline (`WARM_ATTACH_DEADLINE_MS = 500`), executed **before**
`start_worker` decides anything, at the same point the shell starts the worker today (98 ms after
`SHELL_STARTUP_STAGE` in pid 32540). The five steps:

1. `WaitNamedPipeW(..., 200 ms)` then `CreateFileW` with `WARM_ATTACH_DEADLINE_MS`.
   `ERROR_FILE_NOT_FOUND` → absent; `ERROR_PIPE_BUSY` → one 300 ms retry, then absent.
2. Read one line ≤ 200 ms: `WARM_HELLO {"schema":"sotto.warm/1","pid":…,"started_at":…,"session":…,
   "model_key":…,"plugin_sha256":…,"loaded":true,"mode":"parked-tap","load_ms":…,"resident_mb":…}`.
3. **Freshness** (`INV-2`'s price, and the law this repo already paid for): `plugin_sha256` must equal
   `file_sha256(worker/sotto_worker.py)` on disk **and** the shell's own recorded sha; `model_key` must
   match the weights directory. Mismatch → `WARM_HELLO_REFUSED why=stale-code disk_sha=… engine_sha=…`
   → `quit` → cold. This is `_main/live-code-freshness-oracle.py --strict` applied to a long-lived
   process: a warm engine is *by construction* older than the code, so freshness must be a field, not an
   assumption. `UNKNOWN` is not `FRESH` (the 2026-10-30 lesson).
4. Send `{"op":"attach","shell_pid":…,"shell_started_at":…,"live":<Alt+C state>,"device":…,
   "capture_mode":…,"target_pid":…,"version":<shell sha>}` — every per-run parameter that travels in
   `_child_env` today travels here instead, because the engine has no parent to inherit from.
5. Engine replies `WARM_ATTACHED`. Shell builds `WarmPipeBridge`, assigns `self.bridge`, and from this
   line on **every existing guard keeps working unchanged**, because they all test `self.bridge`.

**Adoption by a second shell, and why it cannot produce a twin.** There is normally no second shell —
`take_single_instance_lock` (`Local\SottoShell`) refuses one. The real case is a *restart* (quit and
reopen, or a crash plus relaunch). Sequence: the engine sees client EOF → `WARM_DETACHED`; the new shell
performs `ATTACH_TRY`; the engine's `attached` flag is false, so it accepts. No load happens, and no
engine is started because the pipe answered. Four independent locks make "twin" impossible, and each has
its own arm (§6 A6; F10 is the case where a second engine is *correct*):

1. Task `MultipleInstancesPolicy=IgnoreNew` — `schtasks /run` on a running task starts nothing.
2. `FILE_FLAG_FIRST_PIPE_INSTANCE` with exactly one instance — the second creator gets
   `ERROR_ACCESS_DENIED` and exits `WARM_TWIN_EXIT rc=0`.
3. The engine mutex, held for the process lifetime (kernel-released on death, so "abandoned" is a fact
   and not a timeout): the shell probes it with a 0 ms acquire to tell *"no engine"* from *"an engine
   that is alive but wedged"*.
4. `_main/warm-engine.pid` with pid + start time, so a wedged engine can be killed by identity and then
   the cold path proceeds.

The wedged case is the only one the design must be explicit about: pipe exists, no hello within
`WARM_ATTACH_DEADLINE_MS`, mutex *not* acquirable. Then: `WARM_ATTACH_FAILED why=pipe-timeout` → send
`quit`, wait 300 ms, then kill by pid+start time from the identity file → verify the mutex is now
acquirable → cold start. If the kill itself fails, the shell does **not** go cold: it writes `WARM_ENGINE_UNKILLABLE pid=` and
refuses to load, because going cold while a wedged engine may still be loading is exactly the double
load INV-1 forbids. The refusal uses the existing shape
(`WORKER_AUTOSTART=declined reason=warm-engine-unkillable`) so the panel and the log already know how
to show it, and the row is RED in A5/A7 rather than hidden behind a slow boot.

### 2.6 The five `bridge.stop()` sites, and what each becomes

`sotto_webview.py` stops the bridge at exactly five places. A warm bridge changes the **meaning** of
`stop` only for those five, and each one has a decision already written into the tree:

| site | today | with a warm engine |
|---|---|---|
| `:10777` `SHELL_CLOSING` | kill the child | `detach(park=True)`; the engine follows TTL/keep-warm. `WARM_DETACHED why=shell-closing` |
| `:12683` tray Quit | kill the child | `quit` when keep-warm is off (the owner asked for the app to close), `detach` when it is on |
| `:13335` `revive_worker` | kill + respawn | `detach` if only the live engine is being cycled; re-attach costs 0 loads |
| `:15682` `_pause_shell` ("Paused — engines unloaded") | kills the child **and** with it the WASAPI client — the comment at `:14095` records the owner's *"fica matando o audio toda hora"* and a 14–26 s reload | `park_release`: the engine unloads weights (the promise "engines unloaded, VRAM free" is kept) and stays alive; the WASAPI client is not closed. `WARM_RELEASE why=owner-pause` |
| `:15998` `_do_worker_restart` (hot reload) | `stop('hot-reload')` + `start_worker` | **`quit`** — the file on disk changed, so the engine is stale by definition; then cold start. `WARM_EXIT why=hot-reload stale_sha=` |

`set_engine_park` (`:14090`) is the precedent that this is the house direction: the park request already
exists precisely because killing the process "made his audio blink".

`WarmPipeBridge` exposes the attributes callers already read — `child` (a shim with `.pid` = the
engine's pid and `.poll()` → `None` while alive, so `getattr(bridge,'child',None)` at `:15674` and
`revive_worker` keep working), `state`, `spawns`, `captions`, `capturing`, `loaded_sha256`,
`last_caption_at`, `stop()`, `start()`. No caller learns a new concept; that is the whole point of
implementing adoption as a bridge rather than as a second path.

---

## 3. The channel

The worker's contract is one JSON object per line on stdout, flushed (`sotto_worker.py:609`). The warm
channel keeps that **exactly**, so the shell's parsers, `on_caption/on_status/on_stats/on_meter`
callbacks and every mark the oracle reads stay single-sourced.

- Transport: `\\.\pipe\sotto-warm-<session>-<model_key>`, duplex byte mode, one instance,
  `FILE_FLAG_FIRST_PIPE_INSTANCE`, explicit SDDL restricted to the owner SID (the default DACL of the
  creating token would already be close; the design pins it rather than inheriting it).
- Engine → shell: the same line kinds the child emits today (`caption`, `status`, `stats`, `meter`,
  `WORKER_ALIVE`), plus envelope lines `WARM_HELLO`, `WARM_BACKLOG_BEGIN/ITEM/END`, `WARM_PING`.
- Shell → engine: `attach`, `detach`, `park`, `release`, `quit`, `set_live`.
- **The engine never blocks on the channel.** A dedicated writer thread drains a bounded deque
  (`WARM_SEND_QUEUE = 512` lines). Meter and stats samples are dropped first and counted
  (`WARM_SEND_DROPPED class=meter n=`); captions are never dropped while the deque has room; if the
  deque is full the engine switches that stream to `history-only` and publishes
  `WARM_SEND_OVERFLOW class=caption` rather than stalling the audio thread. The current pipe has one half of this
  failure already, measured from the other side: `BRIDGE_DEATH_CAUSE OSError: [Errno 22] Invalid
  argument` with `rc=1` came from a worker whose parent had closed the pipe, and the cure (`emit` stops
  taking a traceback when the pipe is dead, `emit-pipe-dead` gate pair) only made the death quiet. Today
  a blocked *write* cannot happen because the shell reaps the child the moment it stops reading; with an
  engine that outlives the shell it becomes a routine event, so it is designed out rather than counted.
- Latency budget for the channel itself: the measured transport is `transport p50=237 ms p90=6848 ms`
  (`_main/receipt-20261104-worker-churn.md`, `CAPTION_PAINT_LAG` decomposition) — the pipe is not the
  cost, so the channel design is not where the milliseconds are won and must not pretend to be.

---

## 4. The three warmth modes, and where a first caption can come from before audio exists

`loaded` in this design means **graph AND front end AND providers**, i.e. everything the worker does up
to just before the device ladder (measured: `model-loaded 5 624 ms` then `gate 7 335 ms` — the front end
construction is inside that 1 711 ms). An engine that has loaded the graph but not the front end would
pay 1.7–3.4 s at attach, which is the trap this definition closes.

| mode | what is held while the shell is closed | cost while closed | attach → first caption |
|---|---|---|---|
| **A — cold** (today) | nothing | 0 | **9.0 s** measured file seam; live: `capture-started` +17.4 s, first caption +65 s (44.6 s of it the silent-desktop hold) |
| **B — warm-idle** | graph + front end (1 877 MB RSS measured) | 0 % CPU, 1.9 GB RAM | attach 0.3 + ladder 1.79 + first chunk 0.56 + close 2.98 + paint 0.02 ≈ **5.6 s** `[INFERENCE]` |
| **C — warm-tap** (owner opt-in) | + one held WASAPI client, + an 8 s **RAM ring** of raw PCM (8 s × 16 kHz × 4 B = 512 000 B), **no decoding** | 0 % CPU beyond the tap, +0.5 MB RAM, one client (the same client count a running app has) | attach 0.3 + newest-first decode of the ring + paint ≈ **1.5 s** `[INFERENCE]` |

**Mode C is the only route to 3000 ms**, and it is opt-in (R5). Mode B is the default when the owner
turns the warm engine on: it halves the cold cost without holding an audio client while the app is
closed.

**Where a first caption can come from when no audio exists.** It cannot come from the local engine:
a caption is a decode of audio samples, and silence decodes to nothing. The honest sources are exactly
three, and the design states each with its measured floor:

1. **Audio that existed before the shell came up** — mode C's ring. This is the case the owner actually
   hits: he opens Sotto while something is playing. The engine already had the last 8 s; it decodes
   newest-first so the first painted line is the most recent speech.
2. **Audio that starts after the shell is up** — attach + 560 ms chunk + the decoder's line-close.
   Measured floor for the close is 2 981 ms (`CAPTION_IN − BRIDGE_METER`), so the first caption lands at
   ~3.5–4.0 s `[INFERENCE]`. **No code change inside the model's contract can paint a first line sooner
   than the decoder takes to close one**, and the design says so instead of promising 3 s universally.
3. **The external YouTube DOM** — measured `YT_FRAME` at **+4 482 ms** (pid 42548) and **+6 252 ms**
   (pid 32540), with the boot receipt's note that the graph was not yet warm when they arrived. It is the
   only source measured to produce text before the local graph is ready, it does not depend on `shed`,
   and it is somebody else's lane (`YtSourceOnBoot`/`YtOneToOne`); this design only records that a warm
   engine neither helps nor competes with it.

Consequently the acceptance table (§6) has a **precondition column**. A row without its precondition met
is `SKIPPED`, never green — the same rule the battery already applies.

**The warmth horizon, stated so the promise is not wider than the structure.** With no logon trigger (R4)
and a park TTL of 600 s, warmth exists in exactly one window: from the moment the engine finishes an idle
load until `WARM_PARK_TTL_S` after the last detach. Concretely:

| the owner's launch | what he gets |
|---|---|
| open Sotto while the engine is parked (previous session ended < 600 s ago) | mode B or C, A1/A2 |
| open Sotto > 600 s after the last close | **cold**, 9–13 s; the shell fires `schtasks /run` at boot, so the *next* open inside the new horizon is warm |
| the autostart launch at logon | **cold, by design** (R4: the box is `alta`/`muito-alta` at login). This row is the one the design refuses to promise, and the acceptance table does not apply to it |
| any launch while `shed` is `alta`/`muito-alta` | the batch path, per the owner's own order (§5 G3) — no live caption from the warm graph, and the panel says which level blocked it |

Raising `WARM_PARK_TTL_S` widens the horizon and holds 1.9 GB for longer; that trade is the owner's
switch (`--warm-engine-ttl`), not this design's default.

The `tap-silent-desktop` cure is preserved, not undone: the engine runs the *same* capture loop
(`worker/sotto_worker.py`), so on a flat desktop it extends the same tap (6 s → 12 → 24 → 48 → 60 cap)
instead of closing and reopening WASAPI clients. Mode C makes the client count *smaller* than the
measured defect (12 clients in 3 minutes, `tap-silent-desktop` receipt): one open per TTL window. And
while unattached, a `census-changed` closes the tap instead of rotating it
(`WARM_TAP_CLOSED why=census-changed unattached=true`) — a rotation nobody listens to is pure hitch.

---

## 5. How the warm path ASKS the load gate (never bypasses it)

The gate is two things that already exist: `LoadProbe` (measured `commit_pct` from
`GlobalMemoryStatusEx`, `cpu_pct` from `psutil`, sampled once per `SAMPLE_INTERVAL_S = 5.0`), and the
shell's published `shed` in `_main/panel-visibility.json` (read by the worker through
`PanelVisibilityReader`; live value today `"shed": "muito-alta"`, `staleAfterSeconds: 9.0`). `PARK_LEVELS
= ('alta', 'muito-alta')`.

Four ask points, all mandatory, all logged with the number that decided:

| | when | what it reads | rule |
|---|---|---|---|
| **G1** | before loading the graph | `LoadProbe.reread()` + published `shed` if fresh (≤ 9 s) | require `level == 'leve'`. **Inversion, deliberate:** `level_for_load(None)` is `leve` ("a failed measurement never disables an engine" — correct for a *live* engine), but a failed measurement must not *authorise* a 1.9 GB preload. `commit is None` → `WARM_LOAD_DEFERRED why=no-measurement`, retry in `WARM_LOAD_RETRY_S = 30`. |
| **G2** | before opening the tap (mode C) | same | `alta`/`muito-alta` = *"alta: desliga nemotron, só parakeet"* (the owner's order, quoted in `docs/worker-lifecycle.md` §3b) — the live engine must not even *hold* a tap in `alta`. |
| **G3** | on every `attach` | `reread()` | if the level rose between load and attach, reply `WARM_ATTACHED mode=shed` and the shell takes the batch path. A warm graph is not an argument to override the shed. |
| **G4** | while resident, every `SAMPLE_INTERVAL_S` | same | `muito-alta` for `WARM_RELEASE_S` (120 s) → `WARM_RELEASE` and the weights go; the next `leve` window reloads. |

There is no environment variable, CLI flag or task argument that skips G1–G4, and the design refuses to
add one (R6). The `shed` also reaches the panel (existing `shed_provider`, `sotto_webview.py:8465`), so a
warm engine sitting idle because the box is loaded is *visible*, not a mystery.

---

## 6. Acceptance table

Every row is a measurement that runs without the owner's screen: log parsing, in-process arms, or a
read-only process census. Window-free, audio-write-free (nothing here mutes, unmutes,
resets an endpoint, or opens a device except the engine itself under the owner's own app).

| # | measurement | instrument | threshold | precondition |
|---|---|---|---|---|
| A1 | shell-up → first painted caption, **audio already playing** | `_main/time-to-first-caption-oracle.py` (exists, uncommitted in `H:/sotto-wt/BootFast`; the battery step is `time-to-first-caption` + `red-as-expected-time-to-first-caption`) | **≤ 3000 ms** (`FAIL` at exactly 3000, already fixed by the oracle's `red-at-3000ms` case) | mode C + keep-warm on + audio present at shell-up |
| A2 | same, mode B | same oracle | ≤ 6000 ms | warm engine on, keep-warm off |
| A3 | same, cold floor (regression guard) | same oracle | ≤ 13 000 ms and **no worse than the pre-change median** | engine absent |
| A4 | attach handshake | `WARM_ATTACHED ms=` in `_main/webview-run.log`, parsed by the new `_main/warm-engine-oracle.py` | p50 ≤ 300 ms, p95 ≤ 500 ms (the deadline); 0 timeouts over 20 attaches | — |
| A5 | **zero cold loads on the attach path** | count of `WARM_COLD_LOAD` / `BRIDGE_SPAWNED` per shell run | exactly 0 `WARM_COLD_LOAD` when attach succeeded | — |
| A6 | twin engine impossible | `_main/warm-engine-oracle.py` arm `twin`: spawn two engines, one pipe | 1 `WARM_PIPE_READY`, 1 `WARM_TWIN_EXIT rc=0`, and a `psutil` census of `1` engine | — |
| A7 | no double load | arm `single-loader`: fake client attaches while a `WorkerBridge` is constructed | `WorkerBridge._spawn` never runs; `start_worker` returns False with `self.bridge is not None` | — |
| A8 | gate has a veto | `_main/warm-engine-oracle.py` arms `g1-*`, `g2-*`, `g4-*`, plus the existing `_main/load-shedding-oracle.py` (183 arms) | 0 `WARM_LOAD_BEGIN` lines at `alta`/`muito-alta`; `WARM_RELEASE` within 120 s of `muito-alta`; `unknown` never loads | — |
| A9 | one WASAPI client, no rotation | `_main/tap-silent-desktop-oracle.py` (8 arms) + count of `device-rotated` / `AUDIO_DEVICE_OPEN` in `_main/warm-engine.log` | ≤ 1 client per 3 min; 0 rotations while unattached and flat; net client count with the app open == today | — |
| A10 | no window, ever | `_main/console-window-audit.py` (AST census), `_main/console-window-watch.py` (EnumWindows at 40 ms + `SetWinEventHook`), `_main/owner-screen-gate.py`, `_main/lane-screen-gate.py`, `_main/hidden-launch-oracle.py` | `WINDOW 0` in the audit; watch reports `0 janelas` for the engine's tree; both screen gates PASS with the frozen baseline unchanged | — |
| A11 | no stray process after the shell dies | arm `orphan`: kill the shell, census by pid+start time | engine alive **by design**, **zero** surviving children of the shell; after `WARM_PARK_TTL_S`: engine gone, task Ready, pid file absent | — |
| A12 | crash is not a loop | arm `crash-loop`: kill the engine N times | `RestartOnFailure` ≤ 2; ≤ 2 loads in the window; a third crash leaves it ABSENT and `WARM_ENGINE_DIED` logged | — |
| A13 | residency cost | per-pid RSS sampled by `psutil` (the `rss-trend`/`BRIDGE_RSS` shape) every 60 s | ≤ 2100 MB parked, ≤ 0.5 % CPU over a 60 s idle window; series judged by shape (linear leak = FLAG) | — |
| A14 | the engine is not stale | `_main/live-code-freshness-oracle.py --strict` extended with the engine's `plugin_sha256` | `FRESH` or refuse attach; `STALE` never attaches; `UNKNOWN` is not `FRESH` | — |
| A15 | channel does not stall the audio loop | arm `blocked-client`: a client that stops reading | `WARM_SEND_DROPPED class=meter` grows, `blocks` keeps advancing, zero stall in `WORKER_STATS` | — |
| A16 | replay never paints stale audio | existing `CAPTION_PAINT_LAG … budget_ms=1500 over=true` counter, plus the `src=warm-replay` field in the commit meta | 0 painted lines with `src=warm-replay` and `audio_ms > 2000` | — |

**Instrument that does not exist yet and is the design's own debt:** `_main/warm-engine-oracle.py`,
with `--neg-arm`, ≥ 12 arms (A4, A6, A7, A8, A11, A12, A15 + the five `bridge.stop()` semantics), wired
into `_main/_audit-verify-all.cmd` as the pair `warm-engine` + `red-as-expected-warm-engine` (the house
pattern, and `battery-wiring-oracle.py` refuses an oracle that is written but not wired — measured: three
oracles were refused that way on 2026-11-03). Until it exists, **A4, A6, A7, A11, A12 and A15 are not
measured** and no row may be reported green.

---

## 7. Failure modes, each with its detector

| # | failure | detector (name the line, not the adjective) | action |
|---|---|---|---|
| F1 | engine holds a graph from *older code* | `WARM_HELLO plugin_sha256=` ≠ `file_sha256(worker/sotto_worker.py)`; `WARM_HELLO_REFUSED why=stale-code`; `live-code-freshness-oracle --strict` | refuse attach, `quit`, cold path, log both shas |
| F2 | pipe exists, engine wedged | `WARM_ATTACH_FAILED why=pipe-timeout` + mutex not acquirable with 0 ms | `quit` → 300 ms → kill by pid+start time → verify mutex → cold |
| F3 | engine dies mid-attach | client EOF → `WARM_ATTACH_LOST why=pipe-eof`; the shell's existing restart ladder then logs `BRIDGE_SPAWNED` | cold restart through the untouched ladder (`_schedule_restart`, floors, caps) |
| F4 | engine crash-loops | `WARM_ENGINE_DIED` × N in `RestartOnFailure` window; task `LastTaskResult` | ≤ 2 restarts, then leave it ABSENT and say so |
| F5 | double load | two `*_LOAD_MS` lines with overlapping windows; `WARM_COLD_LOAD n>0` after a successful attach | INV-1 broke: that is a gate failure (A5/A7), not a tweak |
| F6 | writer stalls the audio loop | `WARM_SEND_BLOCKED_MS` > 500; `blocks` stops advancing in `WORKER_STATS` while `WARM_METER` falls behind | drop meter/stats, `WARM_SEND_OVERFLOW`, never block the capture thread |
| F7 | audio hitch from client churn | `AUDIO_DEVICE_OPEN` / `device-rotated reason=flat` count per 3 min; `tap-silent-desktop` oracle arms | hold instead of reopen (existing cure), close on `census-changed` while unattached |
| F8 | warm graph, shed says `alta` → no live caption and the owner sees nothing | `WARM_ATTACH_SHED level=` + the panel's existing `shed` field | the batch path (owner's law), stated in the panel — never a silent path |
| F9 | engine outlives the owner's patience (1.9 GB for hours) | `_main/warm-engine.pid` age; `WARM_EXIT why=idle-expired` absent while age > TTL | TTL is the structure; the setting and `--warm-engine-stop` are the owner's switches |
| F10 | two sessions (RDP) | pipe and mutex names carry `<session>`; two engines is *correct* there | arm A6 must distinguish "twin" from "other session" |
| F11 | integrity mismatch between the engine's token and the shell's | `WARM_ATTACH_FAILED why=access-denied` on `CreateFileW`; `whoami`/token integrity logged at start | named open item (§9); the design does not assume the pipe crosses integrity levels, it measures it |
| F12 | engine paints stale audio as live | `CAPTION_PAINT_LAG over=true` with `src=warm-replay` | `WARM_BACKLOG_LIVE_MS` drops it to history-only; the meta keeps the provenance |
| F13 | engine holds a device that vanished | `device-rotated`/`census-changed` while `attached=false` | close the tap, `WARM_TAP_CLOSED`, reopen on attach |
| F14 | the task silently kills the engine at 3 days | `ExecutionTimeLimit` = `PT0S` asserted by an arm that reads `schtasks /query /tn SottoWarmEngine /xml` (the `shell-relaunch-oracle.py` already reads task XML this way) | RED at registration time, not after three days |
| F15 | the engine's own log grows unbounded (it lives for hours) | log size / rotation lines | bounded file, rotation on size, counted (`WARM_LOG_ROTATED n=`) — the observer's ledger-rotation lesson: judge by **content**, not by a line count |

---

## 8. Refusals, with the reason

**R1 — Refused: any process spawned by the shell that survives `BRIDGE.stop`.**
A child the shell created but cannot kill makes `BRIDGE_STOP` return `True` while a 2 GB process
continues to hold the device — that is exactly the shape of the failure `stop()`'s own comment is about
("a worker that survives the kill is a capture that continues"), and `CreateProcess(...,
CREATE_BREAKAWAY_FROM_JOB)` only works if the shell's job gains `JOB_OBJECT_LIMIT_BREAKAWAY_OK`, which
weakens the measured `job-object` cure for every future child. The engine is therefore owned by the Task
Scheduler and is never in the shell's tree.

**R2 — Refused: a "preloader" that is a second `Popen` with a socket bolted on.** Same reason as R1, plus
it cannot be adopted after a shell crash (its creator died with it), which is the case that matters.

**R3 — Refused: an engine that auto-restarts forever.** The churn receipt measured 88 reloads of ~1.9 GB
in 17 minutes and that is the stutter the owner reports. `RestartOnFailure` is bounded at 2.

**R4 — Refused: loading the graph at logon.** The box is `alta`/`muito-alta` at the moment of login
(live: `"shed": "muito-alta"`), and *"nunca travar o PC do usuário"* is the owner's order. The engine
loads on an idle window per G1 and reports `WARM_LOAD_DEFERRED` when there is none.

**R5 — Refused: making mode C (tap held while the app is closed) the default.** It means a WASAPI
loopback client is open while the owner believes the app is closed. That is the owner's decision, not a
default: it is an explicit setting, it is logged at start (`WARM_TAP_OPEN while_unattached=true`), and the
default keeps mode B. Privacy is not a performance knob.

**R6 — Refused: any switch that bypasses the load gate** (`SOTTO_WARM_FORCE=1` or a task argument). One
bypass makes G1 decorative, and a decorative gate is the class this repo keeps paying for.

**R7 — Refused: decoding while unattached (a "warm-live" mode).** It produces captions no store will
keep (the shell is the only writer of history; a second writer is the duplicate-caption class — 79
consecutive identical lines measured with `_main/caption-dup-repro.py`), and it burns the measured 270 %
CPU for hours. If nobody is listening, nothing is decoded.

**R8 — Refused: revisiting the optimisation that measured worse.** Moving `start_frontend()` ahead of the
device ladder was implemented and measured interleaved: `primeira legenda 9 014 → 10 199 ms`. It stays
reverted; this design does not reorder the worker's boot.

**R9 — Refused: a visible window, a tray balloon, a message box or any dialog from the engine or its
instruments.** The engine has no UI at all; its state is a file plus log lines; every instrument in §6 is
headless by construction (`owner-screen-gate.py`, `console-window-audit.py`).

**R10 — Refused: removing or degrading the cold path.** The cold `WorkerBridge` keeps its code, its
ladder, its floors and its oracles. A finished warm path is an *optimisation of the attach edge*, and A3
exists to prove the floor did not move.

**R11 — Refused: painting a replayed line as if it were live.** No `src=warm-replay` line whose
`audio_ms` exceeds `WARM_BACKLOG_LIVE_MS` reaches the overlay; older audio is history with provenance.
The SilentFallback receipt is the precedent: a line that reached the transcript only through a fallback
must say so.

---

## 9. What this design does NOT know, and who must measure it before cutover

These are open measurements, not assumptions. Each one is a probe, not a promise.

1. **WASAPI loopback from a Task-Scheduler-launched process in the interactive session.** The measured
   `schtasks /it` failures were `TRAY_ICON_ADD` and the hotkey (UIPI, window messages) — the engine has
   neither, and pipes are DACL-governed, not UIPI-governed. `[INFERENCE]` that audio works; the probe is
   `schtasks /run /tn SottoWarmEngine` plus the engine's own `WARM_CAPTURE_STARTED device=` line, run
   once, headless.
2. **Integrity mismatch between the engine and the shell.** Measured in AGENTS.md: the two `explorer.exe`
   processes of the owner read `high`, a lane's process reads `medium`, and the `\Sotto` task runs
   `InteractiveToken` / `LeastPrivilege`. So a double-clicked shell and a task-launched engine may sit on
   different integrity levels, and the named pipe must cross them (pipes are DACL-governed, not UIPI —
   `[INFERENCE]`, not measured here). The probe is F11's `WARM_ATTACH_FAILED why=access-denied` counter
   plus an explicit SDDL on the pipe.
3. **The mode B / mode C latencies** in §4 are `[INFERENCE]` built from measured components
   (0.3 / 1.79 / 0.56 / 2.98 / 0.02 s). They are acceptance rows A1/A2 and must be measured before the
   design may claim them.
4. **Whether `time-to-first-caption-oracle.py` lands.** It exists only as an untracked file in
   `H:/sotto-wt/BootFast` (`_main/time-to-first-caption-oracle.py`, `??` in that worktree's status). A1–A3
   are unmeasured until it is committed and wired; a missing oracle is never a pass.
5. **Hour-scale behaviour**: a 6-hour residency with the owner's real device rotations, sleep/resume
   (`WM_POWERBROADCAST` — the tree already has `power-recovery`, 28 arms) and RDP attach/detach. No lane
   can produce that in a session; it is a field measurement with the instruments in §6, and it decides
   `WARM_PARK_TTL_S`.

---

## 10. DESIGN.md invariant row

Row to append to the fleet registry `I:/!manager/state/design/DESIGN.md` (the registry is the
system-designer's file; this lane does not write into another tree). Table columns as used there:
`| id | invariant | structure that makes it true | oracle and RED input |`.

| id | invariant | structure that makes it true | oracle and RED input |
|---|---|---|---|
| warm-engine-ownership | A caption's latency never depends on a load the shell must perform, and the only process that outlives the shell is one the shell does not own: the graph is held by a Task-Scheduler-created, pipe-singleton engine the shell can only *attach* to, so the shell can never kill what it must adopt and can never load a second copy. | One engine mutex `Local\SottoWarmEngine.<session>.<model_key>` plus a `FILE_FLAG_FIRST_PIPE_INSTANCE` pipe of the same name (one holder; the loser exits `WARM_TWIN_EXIT`), the task's `IgnoreNew` + `ExecutionTimeLimit=PT0S` + bounded `RestartOnFailure`, an identity file with `pid`+start time, and adoption expressed as `WarmPipeBridge` in the existing `self.bridge` field so every pre-existing spawn guard remains the twin-load gate. | Oracle to build: `_main/warm-engine-oracle.py` (≥12 arms, `--neg-arm`, wired as `warm-engine` + `red-as-expected-warm-engine`). RED inputs, each of which must be REFUSED: two engines started (pipe+twin arm); `WorkerBridge._spawn` reachable while an attach succeeded; a load at `shed=alta`/`muito-alta` or with `LoadProbe=None`; an attach with mismatched `plugin_sha256`; a painted `src=warm-replay` line with `audio_ms>2000`; a surviving child of the shell after the shell dies. Measurement of record: `_main/time-to-first-caption-oracle.py` (≤3000 ms, mode C, audio present at shell-up) and `H:/sotto/state/design/warm-worker-20261104.md`. |

---

## 11. Commands used in this design (verbatim, so nothing here is a citation chain)

```
$ python -c "import json;d=json.load(open('_main/panel-visibility.json',encoding='utf-8'));print(list(d.items())[:12])"
  [('schema','sotto.panel-visibility/1'), ... ('shed','muito-alta')]        # live shed, 2026-11-04T11:28:35

$ grep -n "WORKER_SILENCE_MS =\|WORKER_LOAD_SILENCE_MS =\|CLEAN_EXIT_FLOOR_MS =" app/webview/sotto_webview.py
  1021:WORKER_SILENCE_MS = 30000
  1029:WORKER_LOAD_SILENCE_MS = 180000
  1038:CLEAN_EXIT_FLOOR_MS = 20000

$ grep -n "IDLE_HOLD_MAX_S\|IDLE_HOLD_POLL_S" worker/sotto_worker.py
  673:IDLE_HOLD_MAX_S = 600.0
  674:IDLE_HOLD_POLL_S = 10.0

$ grep -n "PARK_LEVELS\|SAMPLE_INTERVAL_S" app/webview/load_shedding.py
  323:SAMPLE_INTERVAL_S = 5.0
  683:PARK_LEVELS = ('alta', 'muito-alta')

$ grep -n "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE" app/webview/sotto_webview.py
  6284:        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000

$ grep -n "DEFAULT_MUTEX_NAME" app/webview/sotto_webview.py
  5976:DEFAULT_MUTEX_NAME = 'Local\\SottoShell'

$ grep -rn "WorkerBridge(" --include=*.py . | grep -v "class WorkerBridge"
  app/webview/sotto_webview.py:  exactly one live construction site (`self.bridge = WorkerBridge(`, :13173)

$ grep -n "self.bridge.stop" app/webview/sotto_webview.py
  10777 closing / 12683 exit / 13335 revive / 15682 pause / 15998 hot-reload

$ du -sh worker/models/nemotron-3.5-asr-ptbr-onnx-int4
  757M

$ git worktree add H:/sotto-wt/WarmWorkerDesign-2 -b lane/warm-worker-design-2 HEAD
```

Measured numbers quoted above come from `_main/receipt-20261104-boot-fast.md` (65 037 ms decomposition,
4.6–5.4 s graph, 8.5–10.5 s `BRIDGE_LOAD_MS`, 9 014 ms file-seam boot, 1.79 s ladder, 1.86 s front end,
the interleaved table that reverted the reordering) and `_main/receipt-20261104-worker-churn.md`
(1 877 MB worker RSS, `CAPTION_PAINT_LAG` p50/p90, the shed `alta`→batch order, the churn numbers).
Nothing in this document was executed against a live engine, because none exists.
