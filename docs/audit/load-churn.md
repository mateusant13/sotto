# load-churn — the model does not reload in a loop any more

Lane `SottoLoadChurn`, 2026-10-06. Repo `H:/sotto`.

**OWNER, VERBATIM (the ask this lane closes):**

> "nao esta funcionando. nem o audio padrao que usam pra testar, nem o audio do chorme. funcionou
> parcialmente apos essa mensagem. e o modelo loading ta toda hora saind out de load. faz o model
> sair de load apos 3 minutos, nao super rapido."

Two complaints: (1) the **model cycles through "loading" all the time**; (2) **no audio works** —
neither the standard test audio nor Chrome's — "partially" and intermittently.

Files touched: **`app/webview/sotto_webview.py`** (the app; untracked/new — see §7). The worker
(`worker/sotto_worker.py`) is **not** touched by this lane: the diagnosis below shows it owed
nothing.

---

## 1. WHY IT CHURNED — the watcher restarted the worker mid-stream

Main's diagnosis, re-derived from the code and confirmed against the LIVE log:

* There is **no unload / idle / TTL timer** in the worker. It is built ONCE and released only when
  the process exits (`worker/sotto_worker.py:1752`):

  ```
  1752:        asr = StreamAsr(model_dir, providers=providers, use_vad=use_vad, lang_id=lang_id)
  ```

  A repo-wide search for `unload|idle_timeout|idle_seconds|ttl|keep_warm` in the worker, both
  shells and `config.json` finds **no such knob** (only unrelated prose in `hot_reload.py`
  docstrings). So the cycling was **not** an idle-unload.

* The churn was the **hot-reload watcher**, wired to restart the worker on every settled file
  change. PRE-FIX `app/webview/sotto_webview.py:2053` (text as read at the start of this lane):

  ```python
  2053:    def restart_worker(self, files):
  2054:        """Stop the one worker and start it again, on a worker file change."""
  2055:        if self.bridge is None:
  2056:            log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
  2057:                'reason=no-worker-running')
  2058:            return False
  2059:        self.bridge.stop('hot-reload')
  2060:        self.bridge = None
  2061:        started = self.start_worker('hot-reload')
  2062:        log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
  2063:            f'spawns={self.bridge.spawns if self.bridge else 0} '
  2064:            f'started={str(started).lower()}')
  2065:        return started
  ```

  and it was wired at `:2008`/`:2042`:

  ```python
  on_worker_changed=self.restart_worker
  ```

  There was **no guard**: a worker mid-stream was stopped and respawned on the spot. The watcher's
  own window is only **250 ms of quiet** (`app/webview/hot_reload.py:52` `DEBOUNCE_MS = 250`) —
  BELOW the cadence of a cross-lane save burst (five lanes saving every 1–3 s reached 250 ms of
  quiet between consecutive saves), so *every* save flushed and *every* flush paid a full worker
  respawn — i.e. a model load.

**Confirmed in the LIVE app log `H:/sotto/_main/_live_owner3.log`** (the app the owner had running,
pre-fix):

```
106: sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=1 debounce_ms=250
107: sotto: HOT_RELOAD_EVENT kind=worker file=sotto_worker.py action=3 events=2 debounce_ms=250
108: sotto: BRIDGE_CAPTION_SENT delivered=true text="Samples Sunday and he can come immediately after"
...
120: sotto: BRIDGE_SPAWNED pid=39872 argv=[... sotto_worker.py ...]
121: sotto: WORKER_AUTOSTART=started reason=hot-reload
122: sotto: HOT_RELOAD_WORKER_RESTART files=["sotto_worker.py"] spawns=1 started=true
```

Line 108 is a **live caption**; lines 106–107 are the file-change burst; line 122 is the restart
landing **on top of a worker that was mid-stream and working**. That is the churn.

## 2. RESTART COUNT — before / after

Census over the one pre-fix live session (`_main/_live_owner3.log`, 705 lines):

| counter | before |
|---|---|
| `HOT_RELOAD_WORKER_RESTART` (worker restarts caused by a file change) | **12** |
| `HOT_RELOAD_EVENT kind=worker` (settled bursts) | 24 |
| `BRIDGE_SPAWNED` | 20 |
| `BRIDGE_EXIT` (`rc=1`, worker deaths) | 19 |

After the fix (`python app/webview/sotto_webview.py --probe-reload`, real files + the real watcher,
§4):

| arm | touches | restarts |
|---|---|---|
| GUARD (capture open) | 6 | **0 during the capture, 1 total** |
| STORM (guard+floor removed = the old behaviour) | 6 | **6** |
| BURST (tight burst, no capture) | 8 | **1** |

## 3. THE FIX (step 1) — debounce + mid-stream guard + 180 s floor

All in `app/webview/sotto_webview.py`. Three rules, in order, in a small policy class
(`:2293`) that the shell delegates to; the restart itself stays in the shell (`:2087` `restart_worker`
now only QUEUES, and `:_do_worker_restart` does the one stop+start).

**DEBOUNCE = 2000 ms** (`:157`). Why this value: the watcher's own window is 250 ms of quiet, which
is *below* a cross-lane save cadence, so it coalesces nothing across lanes; 2 s of quiet coalesces
one lane's save-storm while staying responsive. (In the probe, a burst is 1 restart either way;
this cap bites on the burst-after-burst case.)

**GUARD — a mid-stream worker is never restarted** (`:2387`):

```
2387:        if br.is_capturing():
2388:            self.log(f'HOT_RELOAD_WORKER_DEFERRED files={json.dumps(files)} '
2389:                     'reason=capturing -- applies at the next boundary')
2390:            return                    # pending stays; boundary() re-arms
```

`is_capturing()` (`:2479`) is True from the worker's `capture-started` status (`:2689`) until the
child stops/exits (`:2606` `stop`, `:2791` `_wait`) or the run reports a terminal state (`:2692`).
A queued reload lands at the next boundary: a natural respawn re-reads the file, and that is logged
as `HOT_RELOAD_WORKER_APPLIED_AT_BOUNDARY reason=respawn-reread-file` — it does **not** cost a
second restart (`:2400–2408`, guarded by comparing the request time to the bridge's `spawned_at`,
`:2465`). The boundary is signalled from `on_worker_status` (`:2031`).

**FLOOR = 180000 ms** (`:165`) — the owner's "3 minutes". See §5 for why this is a reload floor and
NOT an idle-unload.

## 4. THE PROOF — touch the worker file N times while a capture runs → ONE restart

New measurement mode, `--probe-reload` (`:3102`), which drives **real files** through the **real**
`hot_reload.HotReload` watcher and the **real** `WorkerReloadPolicy`. The only stand-in is the
bridge object, which exposes exactly the two fields the policy reads (`child`, `is_capturing()`);
the `restart` callable counts spawns.

```
$ cd H:/sotto/app/webview && py -3 sotto_webview.py --probe-reload ; echo RC=$?
HOT_RELOAD_WORKER_QUEUED files=["sotto_worker.py"] debounce_ms=200 min_interval_ms=180000
HOT_RELOAD_WORKER_DEFERRED files=["sotto_worker.py"] reason=capturing -- applies at the next boundary
   ... (x6, one per touch, each spaced 0.4 s — WIDER than the watcher's 250 ms window) ...
ARM guard touches=6 restarts_during_capture=0 expect=0
HOT_RELOAD_WORKER_APPLIED_AT_BOUNDARY files=["sotto_worker.py"] reason=respawn-reread-file
ARM guard total_spawns=1 (policy_restarts=0 + boundary_respawn=1) expect=1
ARM storm touches=6 restarts=6 expect=6
ARM burst writes=8 restarts=1 expect=1 debounce_ms=2000
SELFTEST reload rc=0
RC=0
```

* **GUARD arm**: 6 touches, each far enough apart to flush on its own, while `is_capturing()` is
  True → **0 restarts during the capture**; at the boundary the worker respawns once → **1 total
  spawn**, not 6.
* **STORM arm (control, turns RED if the test cannot see the defect)**: the SAME 6 touches with the
  guard and the floor removed (the pre-fix behaviour) → **6 restarts**. This is what proves arm 1
  means something.
* **BURST arm**: 8 writes inside the watcher window → **1 restart**.

The probe opens **no window and no worker**, so it is safe to run under `pythonw` and adds nothing
to the startup flash.

## 5. THE 3-MINUTE RULE (step 2) — there is NO unload, and here is the measurement

The owner asked to "fazer o model sair de load apos 3 minutos". Read literally that is an idle
unload TTL. **I did not add one, because it would create the exact symptom he is complaining
about.** Measurement, from the worker's own `model-loaded` line in `worker/runs/*.jsonl` (n=59
samples):

| quantity | measured |
|---|---|
| model load wall time (`load_s`) | **min 2.01 s, median 2.87 s, max 8.26 s** |
| RSS while loaded (`rss_mb`) | **1403 MB .. 2089 MB** |

So the model is ~0.6 B and loads in 2–8 s while holding 1.4–2.1 GB. The **reload is the expensive
event**; an idle-unload would trade 1.7 GB of steady RSS for a *repeated multi-second stall* — i.e.
it would ADD reloads, which is the churn. Verbatim from the file: the reload is what the owner is
watching happen.

What the owner's 180 s IS implemented as, safely: a **minimum interval between applied reloads**
(`:165 WORKER_RELOAD_MIN_INTERVAL_MS = 180000`, enforced at `:2413`). The model cannot leave load
more often than once per 180 s. 180 s is ≈20× the worst measured stall (8.26 s), so the floor
bounds the churn without ever being the reason a healthy run stalls.

**OWNER-VISIBLE behaviour, which is the bar:** the model loads once per worker life and stays
loaded; a file change cannot restart it while it is transcribing; and no restart can happen faster
than every 3 minutes. No reload loop.

## 6. THE LIVE CHAIN (step 3) — the FIRST link that breaks, with its log line

Measured on the running app's own log, `H:/sotto/_main/_live_owner3.log`. The chain, in order, from
a FAILING run (lines 43–66):

```
43: sotto: STATUS_APPLIED text="capture-started"          <- link 1: the tap DID open
44: sotto: PLACEHOLDER_APPLIED title="Listening"
45: sotto: STATUS_APPLIED text="device-rotated (flat)"    <- ...and read FLAT
...
55: sotto: STATUS_APPLIED text="capture-started"          <- opened again, flat again
57: sotto: BRIDGE_SILENT ms=15000 pid=13752               <- said nothing for 15 s
61: sotto: BRIDGE_EXIT pid=13752 rc=1 spawns=1 captions=0 statuses=14 malformed=0 stderr_tail=[
      ..., "WORKER_STATS tag=tick blocks=139 block_samples=542400 nonzero_blocks=0
      peak=0.000092 rms=0.00000903 ... chunks=38 captions=0 tokens=0 frames=0 blanks=0 ..."]
```

| link | question | live evidence | verdict |
|---|---|---|---|
| 1 — tap open | is `capture-started` emitted? | line 43 `STATUS_APPLIED text="capture-started"` | **OPEN — but onto a FLAT endpoint** |
| 2 — `nonzero_blocks` | does the tap carry signal? | line 61 `nonzero_blocks=0 peak=0.000092` | **BROKEN** |
| 3 — `peak` | above the floor? | line 61 `peak=0.000092` (≈0) | **BROKEN (same cause)** |
| 4 — caption to panel | does `BRIDGE_CAPTION_SENT` fire? | line 108 `BRIDGE_CAPTION_SENT delivered=true` (in the WORKING run) | works — when links 2–3 hold |

**FIRST BROKEN LINK: link 2 — `nonzero_blocks=0`, `peak=0.000092`.** The tap opens (link 1 is fine)
and then the device ladder rotates away from it as `device-rotated (flat)` and the worker exits
`rc=1` after 15 s of silence. That is the **blank-frame / silent-endpoint defect**, owned by the
sibling lanes (`docs/audit/blank-frames-root-cause.md`, `docs/audit/device-routing.md`), **not** by
this lane — the worker side of the chain is sound; the audio arriving at it is digital silence.

It is INTERMITTENT, exactly as the owner says, and the failing evidence is captured above: of the
runs in this one log, 14 samples carried signal (`nonzero_blocks>0`, e.g. `nonzero_blocks=45
peak=0.401165`) and **3 sampled `nonzero_blocks=0`** — and every zero ends in `BRIDGE_EXIT rc=1`.
The chain produces captions ONLY on the non-zero runs (28 `BRIDGE_CAPTION_SENT` in this session).

The SECOND break — which this lane fixes — is that once the worker dies, the pre-fix watcher
piled file-change restarts on top of it (`:122` etc.), paying a model load each time. That is §1/§2.

## 7. WHAT CHANGED, and the one thing deliberately NOT changed

`app/webview/sotto_webview.py` (untracked/new file; `git status` shows it as `??`, so there is no
HEAD blob to diff — the PRE-FIX text is pasted verbatim at §1):

| anchor | change |
|---|---|
| `:143–165` | `WORKER_CAPTURING_STATES`, `WORKER_RELOAD_DEBOUNCE_MS=2000`, `WORKER_RELOAD_MIN_INTERVAL_MS=180000` |
| `:2293` | `class WorkerReloadPolicy` — debounce / guard / floor |
| `:1176` | shell constructs the policy |
| `:2031` | `on_worker_status` signals the boundary |
| `:2087` | `restart_worker` now QUEUES (was: restart on the spot) |
| `:2103` | `_do_worker_restart` — the one stop+start |
| `:2462,2465,2479,2547,2606,2689,2692,2791` | bridge tracks `capturing` / `spawned_at`, exposes `is_capturing()` |
| `:3102,3301` | `--probe-reload` mode + dispatch |

**NOT changed:** `app/electron/main.js:624 restartWorkerForHotReload` has the SAME defect (restart
with no guard on a file change). That arm is documented as NOT the app — `app/webview/run.cmd`
header: *"app\electron\ is the EARLIER shell and is kept only for its panel files and for
comparison -- it is not a fallback and nothing here reaches for it."* Editing a dead arm adds risk
with no owner-visible benefit, so it is reported here instead of silently patched. If a future lane
revives the Electron arm, it inherits this bug.

**Constraints honoured:** no window was opened by this lane — the probe starts nothing, and the
worker spawn path is untouched (`CREATE_NO_WINDOW` alone at `:2532`, `pythonw` via `run.cmd`); the
startup flash path is untouched. Kill filters were not needed (nothing was killed).

---

## SELF-AUDIT

**1. protocolos em falta —** Felt the absence of a house rule on **where a lane's measurement doc
lives when a sibling lane owns the same live app**. `SottoLiveForOwner` had the app running with its
own log (`_live_owner.log`, then `_live_owner3.log`); nothing told me whether re-launching to get a
clean live run was mine to do, and a second instance had already killed the first
(`live-for-owner.md` §5). I did NOT relaunch (that would have stolen the owner's live app and
opened a launch path). Different-with-hindsight: file a ticket asking for a "one live app, one
owner lane, log path declared" rule, and read `docs/audit/live-for-owner.md` FIRST before choosing
the live-log path — I read it after starting.

**2. verificacao adicional — que check extra teria aumentado a confianca?** Run the probe against
the **real WorkerBridge** (spawning a trivial worker script that emits `capture-started` and sleeps)
instead of a stand-in bridge, so `capturing` is set by the REAL `_consume`. Cost: ~15 s + a child
process, and it needs a `capture-started` line to arrive within the arm window, which couples the
arm to a real spawn. I judged the stand-in sufficient because the production wiring
(`_consume` → `self.capturing` → `is_capturing()`) is a 3-line path read directly, but the honest
labelling is that the guard's *integration* is proven by inspection, and only the policy is proven
by execution.

**3. checkboxes novas (mecanico) —** `python app/webview/sotto_webview.py --probe-reload ; test $? -eq 0`
as a standing gate for any future edit to `WorkerReloadPolicy`, the `HOT_RELOAD_WORKER_*` logging,
or the bridge's `capturing` bookkeeping. It prints `SELFTEST reload rc=<n>`, exits non-zero on any
arm. Add it next to `hot_reload.py --selftest`.

**4. review por outro subagente —** **sim-com-escopo**: a reviewer should check (a) the
`pending_since` vs `spawned_at` boundary comparison in `_fire` for a race where a respawn and a
request coincide, and (b) that `boundary()` re-arming on every status cannot starve the reload
indefinitely on a worker that emits a status line more often than `debounce_ms`.

**5. gate-doubt:**
- **verde-de-verdade:** the green is `SELFTEST reload rc=0` from `--probe-reload`. Is it vacuous?
  Tested. The STORM arm prints `restarts=6 expect=6` and would set `rc=3` if the policy stopped
  restarting — so the harness can go RED, and arm 1 is not a pass-by-construction: the same callable
  that arm 1 shows as 0 is shown as 6 in arm 2. The debounce (2000) is passed explicitly per arm, and
  arm 1 uses 200 ms on purpose to isolate the guard. One vacuity I DID find and fixed while writing:
  arm 2 initially left `capturing=True`, which would have deferred and made the control pass
  vacuously; it sets `capturing=False` (`pre-fix: no guard existed at all`).
- **falta-no-gate:** the gate does NOT verify that the REAL `_consume` sets `capturing` — a future
  change that renames the `capture-started` state (or stops emitting it during the ladder) would
  leave `capturing` permanently False, the guard inert, and `--probe-reload` would STILL print
  rc=0, because the probe supplies `capturing` itself. That is the scenario a future change walks
  through.
- **gate-melhor:** a check that reads a real worker log and asserts the bridge's own state machine
  reaches `capturing=True` — e.g. feed `_consume` the exact line
  `{"type": "status", "state": "capture-started", ...}` (as recorded at
  `worker/runs/gate-live-drone.jsonl:8`) into a bare `WorkerBridge` and assert `is_capturing()` is
  True; RED input = `state="boot"`. Command shape:
  `py -3 -c "import sotto_webview as s; b=s.WorkerBridge('py', 'x'); b.child=object(); b._consume(r'{\"type\":\"status\",\"state\":\"capture-started\"}'); assert b.is_capturing()"`.

**6. confianca —** **alta** for the churn fix (the cause is in the live log and the guard is proven
by a RED-able probe) · **media** for §5's "no unload" (it is a measurement-backed judgement about
what the owner wants; the owner could still want the RAM back, and that trade is his to make) ·
**alta** for the first broken live link (it is a pasted log line, `nonzero_blocks=0`).

**7. nao verificado —**
- The FIX has never run inside a LIVE app: the running instance is pre-fix (it was launched before
  this edit), and I did not relaunch it. The `--probe-reload` arms are the only execution evidence.
- The Electron arm (`main.js:624`) is unpatched and untested here.
- The `_do_worker_restart` path (real `bridge.stop` + `start_worker`) is not exercised by the probe;
  only the policy's decision to CALL it is.
- Whether `capture-started` is the ONLY mid-stream state the worker emits (I read the emitter at
  `sotto_worker.py:2139` and the state list; I did not exhaustively enumerate every future emitter).
- `cache-task-report.sh` was run; see §8. No live-vs-fix performance number exists because the fix
  was not live at measure time.

## 8. CACHE / PRICE

See the verbatim `cache-task-report.sh` output appended below.

```
$ bash I:/!manager/scripts/cache-task-report.sh SottoLoadChurn ; echo RC=$?
RC=0
## CACHE/PRICE
- task/agent: SottoLoadChurn
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLoadChurn.jsonl
- cache: read=9237888 write=0 hit=97.6089% (cache-read / input+cache-read); universe: 62 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLoadChurn.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=58 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 62 of 62 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T09:15:50.241000+00:00 | break_items=2; WHEN=2026-10-06T09:18:00.092000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 115208 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLoadChurn']; window: 2026-10-06T09:15:50.241000+00:00..2026-10-06T09:18:00.092000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1107f-61c6-744e-aa27-414f8abe8cd9 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278150241 | session_id=01a1107f-61c6-744e-aa27-414f8abe8cd9 provider=deepseek-flash model=deepseek-flash item_index=91; turn_id=1791278280092 (state=RESOLVED-BREAKS-OMP; ...)
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- usage rows: 62
- input tokens: 226303
- output tokens: 46536
- cache-read tokens: 9237888
- cache-write tokens: 0
- hit ratio: 97.6089% (cache-read / input+cache-read)
- prefix breaks: 5
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T09:15:50.241000+00:00; WHERE session_id=01a1107f-61c6-744e-aa27-414f8abe8cd9 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278150241
  - break_items=2; WHEN=2026-10-06T09:18:00.092000+00:00; WHERE session_id=01a1107f-61c6-744e-aa27-414f8abe8cd9 provider=deepseek-flash model=deepseek-flash item_index=91; turn_id=1791278280092
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(`report generated_at: 2026-10-06T09:22:27.065475+00:00`)
