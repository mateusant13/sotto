# Audit — the shell and the bridge

Axis: `app/webview/sotto_webview.py` (the WebView2 shell) and `app/electron/worker-bridge.js`
(the reference bridge). READ-ONLY audit; the only artifact written is this file.

## Files under audit (pinned by hash)

| file | bytes | mtime (epoch) | md5 |
|---|---|---|---|
| `H:/sotto/app/webview/sotto_webview.py` | 109863 | 1791275097 | `96abe6eb72b029f0b84266c1206b9ed5` |
| `H:/sotto/app/electron/worker-bridge.js` | 34374 | 1791264709 | `834a1bf19958e482c8c18b183caf50cc` |
| `H:/sotto/worker/sotto_worker.py` | 77911 | 1791270227 | `8728805e9b43d6b8314004c5cfa7b6d7` |

`app/webview/` also contains three sibling variants — `_flash-nocure-sotto_webview.py`,
`_flash-show-sotto_webview.py`, `_vis-live-sotto_webview.py` (112–112.5 KB each). They are
A/B experiment copies (their names match the startup-flash lane), not snapshots of the live
file; the live file is `sotto_webview.py` and it is intact (ends at
`if __name__ == '__main__': sys.exit(main())`, verified with `tail -c 120 ... | od -c`).

The app is running (pid 30848, per the ticket). It was **not** touched, killed, restarted, or
probed interactively.

---

## 0. The history, confirmed

`worker-bridge.js` (JS) once held a non-reentrant lock while `#spawn()` reached a lock-taking
function → deadlock, `statuses=0` for eight cycles. The **Python port fixed exactly that one
instance** and says so in a docstring: `_arm_silence` (`sotto_webview.py:2117-2140`) carries
"MUST NOT take `self._lock`", because `_spawn()` is called from `start()` with the lock held
and `threading.Lock` is not reentrant. I re-read that path: `start()` (`:1901`) takes `_lock`,
calls `_spawn()` (`:1916`), and `_spawn()` → `_arm_silence()` (`:1911`) takes **no** lock,
while `_schedule_restart()` (`:2210`) also takes **no** lock. So the original
hard-deadlock class is genuinely absent from the Python bridge. What follows is the same
*class* surviving in other shapes.

---

## Findings

Every finding cites `file:line` and, where marked **[MEASURED]**, a run whose output is pasted.
The measurement is a windowless probe (`pythonw.exe`, no console, no window) that imported the
module and called its own functions directly — no worker was spawned, no page was opened.

### F1 — **[MEASURED]** `exec_js` runs every injected script **twice** (HIGH)

`sotto_webview.py:1409-1421`:

```python
        try:
            self._ui(_run)          # :1415  first execution
        except Exception as exc:
            box['error'] = repr(exc)
            done.set()

        self._ui(_run)              # :1420  SAME script, executed again
        if not done.wait(timeout):
            return None
```

`_ui(_run)` runs `_run` once per call, and `_run` issues `self.core.ExecuteScriptAsync(script)`
(`:1404-1408`). There are two unconditional calls, so **every** JS the shell sends is evaluated
twice. This is not a no-op idiom: the first call is inside `try`, the second is outside it, so
the duplicate is not an error-handling twin — it is a copy/paste duplicate.

Confirmed count with a raw grep:

```
$ grep -n "_ui(_run)" app/webview/sotto_webview.py
1415:            self._ui(_run)
1420:        self._ui(_run)
```

Blast radius — every caller of `exec_js` (`:1383`) inherits it:
`emit` (`:1431`) → `send_status`/`send_geometry`/caption/status delivery; `apply_panel_state`
(`:1444`); `reply_info` (`:1596`); `BRIDGE_PROBE` at `_on_loaded` (`:1271`); `DUMP_DOM_PROBE`
(`:1741`).

- For **captions**, `emit('caption', …)` → page `window.__sotto_emit('caption', json)`
  (`sotto_webview.py:664`) → `panel.js` `bridge.onCaption(...)` → `engine.ingest(text, meta)`
  (`panel.js:144-148`). Running it twice calls `engine.ingest` twice on identical `(text, meta)`.
  In `caption-formulation.js:268-345` the second identical call satisfies
  `start < lastAudioEnd` (revision branch, `:287-296`), which resets `committed`/`provisional`
  for the span and re-derives the line from a now-empty buffer — i.e. the duplicate is not
  absorbed; it perturbs the join state. The exact visible effect (flicker vs double line) was
  **not** measured here (needs the DOM/join harness), but "runs twice" is proven by the source.
- For **status** it is idempotent (the same `textContent`/class toggle twice).
- For **probes** it means `--dump-dom` and the preload probe each run their page script twice.

This is the strongest "the shell can behave differently from the JS arm" defect found, and it
is entirely Python-side (the JS arm has no equivalent double-call).

### F2 — **[MEASURED]** The "no audio" falsifier swallows a **real** worker error (HIGH)

`sotto_webview.py` defines a falsifier for sentences claiming audio is absent
(`FALSE_AUDIO_ABSENT_RE`, `:94-95`) and `_status` rewrites any match to `CAPTURE_NOT_STARTED`
and forces `kind='busy'` (`:1888-1891`). The intent is right. But `worker_status_text`'s
`error` branch (`:196`) builds the footer **from the worker's own `detail`**, and the worker's
selftest error detail is literally `f"no audio at {audio}"` (`sotto_worker.py:1216`).

Measured (windowless probe importing the real module):

```
A_text_built        : "Worker error at selftest - no audio at C:/s/sample1.flac"
A_regex_matches     : true
A_kind_from_mapper  : "error"
A_after_status_text : ["Capture not started - the worker has not opened the audio device", "busy"]
A_capture_not_started: true
```

So a **genuine `error` status whose kind was computed as `error`** is rewritten to the neutral
`CAPTURE_NOT_STARTED` string and painted **busy**. This is precisely the "failure path and
success path produce the same observable" the ticket asks for: the panel shows warm-up for a
worker that failed.

Note the mapper's own docstring (`:162-165`) claims "The prose is kept clear of
`FALSE_AUDIO_ABSENT_RE` on purpose" — that is true of the hardcoded `silent-device` /
`device-exhausted` branches (`:191-193`) but **false** of the `stage`+`detail` branch (`:196`)
and the `detail`-only branch (`:198`), which pass the worker's raw words straight through. The
JS arm is immune because `describeState('error')` returns the fixed string
`'Worker reported an error'` (`worker-bridge.js:114`, `:213`), never the detail.

### F3 — **[MEASURED]** An empty caption counts as proof-of-life and clears the death banner (MED)

`_consume` caption branch (`sotto_webview.py:2052-2068`) only refuses `text is None` (`:2053`):

```python
            text = message.get('text')
            if text is None:
                self.malformed += 1
                return
            ...
            self.captions += 1
            ...
            if self.pending_error is not None:
                self.pending_error = None      # :2065  death lifted
            self.on_caption(str(text), meta)   # :2068  empty string emitted
```

The JS arm drops an empty caption first (`worker-bridge.js:704`: `if (text.trim() === '')` →
`BRIDGE_CAPTION_EMPTY dropped=1`). The Python port dropped that guard. Measured:

```
B_empty_caption_emitted : [""]
B_captions_counter      : 1
B_pending_error_after   : null            # the death banner was cleared
B_no_text_field_captions: 0               # {"type":"caption"} with no text -> malformed
B_no_text_field_malformed: 1
```

The panel itself discards an empty line (`panel.js:152` `if (!text) return false;`), so nothing
false is *rendered* — but the shell's own state (`captions`, `pending_error`) treats "content
that renders nothing" as "the worker transcribed". A `pending_error` set by a non-zero exit
(`_wait`, `:2182`) is cleared by the next empty caption, and the panel stops showing the death
while `captions` under-counts nothing and over-counts one. The live worker never emits empty
text (`sotto_worker.py:1367` guards `if text.strip():`), so this is latent — but it is exactly
the "mapper whose input can be ABSENT" shape: the same arm hardened `done`+absent-verdict
(`:144-156`) and left the caption path's absent-content case open.

### F4 — **[MEASURED-by-read]** `start()` returns `true` even when no worker was spawned (MED)

`sotto_webview.py:1901-1917`: `start()` takes the lock, refuses only on
`self.stopped or self.child` (`:1902`), then always `return True` (`:1917`) regardless of what
`_spawn()` did. `_spawn()` returns `None` on **every** path and, for a missing worker
(`:1922-1931`), emits `'Worker not found'` and schedules a restart — but `start()` reports
success. The JS arm returns the spawn result: `start()` ends with `return this.#spawn('start')`
and `#spawn` returns `false` for a missing file (`worker-bridge.js:449-468`).

Consequence in the shell: `SottoShell.start_worker` logs
`WORKER_AUTOSTART=started reason=…` (`:1651`) even though the worker path does not exist, so the
startup receipt asserts a success for a failure. This is the ticket's "failure path and success
path produce the same observable" at the API boundary.

### F5 — Lock held across a blocking UI round-trip (MED)

`start()` holds `self._lock` (`:1901`) across `_bridge_status()` → `_status()` → `on_status()`
(`:1658-1660`) → `SottoShell.apply_panel_state` (`:1444`) → `send_status` → `emit` →
`exec_js` → `_ui`, and `_ui` waits on the UI thread with `done.wait(10)` (`:1358`). With F1,
that is up to **four** `ExecuteScriptAsync` round-trips (status ×2, placeholder ×2) inside the
lock, each with a 10 s ceiling.

This is the same class as the history (a lock held across a call that touches the same object's
protocol), just with a bounded consequence: any UI-thread activity that needs the lock during
that window — `dispatch('quit')` → `SottoShell.quit` → `request_exit` → `bridge.stop('exit')`
which takes `_lock` at `:1988` — will block the UI thread until `_ui`'s 10 s timeout releases
the worker thread. Net effect: a possible multi-second freeze on start/quit, self-recovering,
not a permanent deadlock. No `RLock`/`hasPendingRestart`/`isActive` guard from the JS arm is
present on this side.

### F6 — `_schedule_restart` does not cancel the previously armed timer (MED/LOW)

`sotto_webview.py:2210-2220` overwrites `self._restart_timer` (`:2219`) without cancelling the
timer already in that slot. The JS arm added exactly this guard and documents why
(`worker-bridge.js:578-585`, `#cancelRestart('superseded-by-…')`): a spawn that never starts can
emit **both** `error` and `close` on one child, each scheduling its own retry, leaving one timer
armed and invisible to `stop()`. The Python `_cancel_timers` (`:2141-2148`) only cancels the
**latest** `_restart_timer`, so a superseded timer is not cancelled. What saves it today is the
guard in `_restart` (`:2222-2223`: `if self.stopped or self.child is not None: return`) plus
`_schedule_restart`'s own `if self.stopped: return` (`:2211`). That guard is the *only* thing
preventing a twin child — the belt the JS arm added is missing.

A concrete double-schedule path exists: `_on_silence` (`:2149`) calls
`_kill_and_restart('silent')` → `_schedule_restart('silent')`, and the terminated child makes
`_wait` (`:2159`) run `_schedule_restart('exit')` (`:2199`) for the **same** death. Two timers
are armed; only the later one is referenced.

### F7 — **[MEASURED]** State-name sets are separator-sensitive where the JS arm normalises (LOW)

The Python sets (`:112-126`) use the worker's hyphen spelling (`device-exhausted`,
`silent-device`, `model-loading`). `worker_status_kind` (`:134`) compares the raw `state` with
`in`. The JS arm normalises `[\s\-.]` → `_` before lookup (`worker-bridge.js:213-222`), so it
matches either spelling. Measured:

```
D_hyphen_in_error_set   : true
D_underscore_in_error_set: false
D_kind_hyphen           : "error"
D_kind_underscore       : "busy"     # device_exhausted painted as health
```

The live worker emits hyphens (`sotto_worker.py:1559` `device-exhausted`, `:1630`
`silent-device`), so this is latent — but it is the "two arms disagree on the same input"
class, and it means a worker that spells a state with an underscore is silently mis-painted as
healthy by this arm and correctly by the other.

### F8 — A status line without `type` is silently dropped (LOW/latent)

`sotto_webview.py:2046-2051`/`:2098`: `kind = message.get('type')`; anything that is not
`'caption'` or `'status'` increments `malformed` and returns without a status. A JSON object
that is a status by shape (`{"state":"error",…}`) but omits `"type"` is therefore dropped. The
JS arm behaves the same (`worker-bridge.js:684-694`), and the live worker always sets `type`
(`sotto_worker.py:296`, every call passes `type=`), so this is latent — recorded because it is a
status path that can be skipped with no visible symptom other than `malformed`.

### F9 — `stop()` emits no final status on the Python side (LOW)

`sotto_webview.py:1987-2004` terminates the child and returns; it never calls `_status`. The JS
arm emits `#status('Worker stopped', 'error', …)` in `stop()` (`worker-bridge.js:635-636`).
After a shell `stop()` (hot-reload restart, or exit) the panel keeps the previous footer until
the next status arrives. Cosmetic; noting for parity.

### F10 — `_spawn()` runs on the restart thread **without** `_lock` (LOW, race)

`_restart()` (`:2222`) → `_spawn()` (`:1919`) re-checks `self.stopped` at `:2223` but then calls
`_spawn()` unlocked. If `stop()` (which takes `_lock`) runs between that check and the `Popen`
in `_spawn`, a child can be spawned after the bridge is stopped; `_wait` then returns early
(`:2171` `if self.stopped: return`) and that child is never terminated. The JS arm shares this
window (its timer callback re-checks `this.stopped` immediately before `#spawn`), so it is not a
Python regression — but the Python `_spawn` mixes lock discipline (locked when reached from
`start()`, unlocked from the timer) and this is the concrete consequence.

---

## What happens on death, on restart, and in quiet periods

- **Death.** The reader thread `_wait` (`:2159`) blocks on `child.wait()`, records
  `BRIDGE_EXIT … rc=… spawns=… captions=… statuses=… malformed=… stderr_tail=…`, nulls
  `self.child`, and for `rc != 0` increments `deaths`, sets `pending_error` (from `last_error`
  or a synthesised `exit` entry), and emits `'Worker stopped (exit N) - …'` with the last two
  stderr lines appended (`:2176-2196`). A clean `rc == 0` clears `pending_error` and is reported
  as "stopped", not "died".
- **Restart.** `_schedule_restart` (`:2210`) increments `restarts` and sets a daemon
  `threading.Timer` with delay `min(backoff_max, backoff_base · 2**restarts)` (defaults
  `1000`/`30000` ms — `:1841-1842`). `_restart` (`:2222`) gates on `stopped or child`, then
  `_spawn`. While `pending_error` is set, the restart's warm-up statuses
  (`WORKER_WARMUP_STATES`, `:123-126`) are held behind the death banner and **not** painted
  (`:2088-2095`, `BRIDGE_STATUS_HELD`); only a real caption lifts it (`:2063-2066`).
- **Quiet.** Each stdout line re-arms a silence watchdog (`_pump` → `_arm_silence`, `:2117`);
  if no line arrives within `silence_ms` (default 15000) `_on_silence` (`:2149`) emits
  'Worker is running but has said nothing' and calls `_kill_and_restart('silent')`. The silence
  timer is a daemon and re-armed (never cancelled-and-left) on every line.

---

## What I could NOT verify (and why)

1. **The user-visible effect of F1** (double `engine.ingest`): I proved the double call from
   source (`:1415`,`:1420`) and read the revision branch it feeds
   (`caption-formulation.js:287-296`), but did not run the DOM/join harness, so I do not claim
   "duplicate caption appears" — only "the join path is invoked twice with identical input."
   Running it needs the Electron/join harness, which the ticket forbids me to launch.
2. **F5's freeze duration in the live app.** The 10 s ceilings are read from `_ui`/`exec_js`
   (`:1358`,`:1413`); I did not induce a start/quit collision against the running pid 30848.
3. **F4/F2 on the live transport.** Both are [MEASURED] against the imported functions, not
   against a running shell streaming to a real panel.
4. **`hot_reload.py` internals.** I confirmed it has no external dependency (it notes
   `watchdog` is NOT installed) and uses its own `threading.Lock` (`:357`,`:375`,`:393`,`:458`),
   but did not audit its debounce/flush locking in depth — outside the two named files.
5. **The three `_flash-*`/`_vis-live-*` sibling variants.** Not diffed line-by-line against the
   live file (the diff is dominated by line-ending differences: live is LF, `diff` reports the
   whole file). They are experiments, not the code under audit.
6. **Whether pid 30848 is loaded from this exact hash.** I did not query its image/command line
   (the ticket says it is running and not to disturb it).

---

## SELF-AUDIT

- **protocolos em falta** — I should have applied `read-before-concluding` harder before
  reading `worker_status_text`'s "clear of FALSE_AUDIO_ABSENT" docstring as a fact: the
  docstring is false for the `error`/`detail` branch, and I only caught it because a probe ran
  the real function. The protocol I leaned on instead — "run the function, don't trust the
  comment" — should have been the first move for every prose claim in these files. Different
  next time: treat every "on purpose" comment as a claim to falsify with a 3-line probe.
- **verificacao adicional** — I ran the extra check that raised confidence most: a windowless
  `pythonw` probe that imported the real module and exercised `worker_status_kind`,
  `worker_status_text`, `_status` and `_consume` directly, turning four findings from
  code-reading into measured output (pasted in F2/F3/F7). It cost ~1 s and no window. I did
  **not** run the DOM/join harness for F1's visible effect — cost: needs Electron/the join
  harness, which the brief forbids launching.
- **checkboxes novas** — add a mechanical step to this class of work: *"for every status/mapper
  function, feed it the ABSENT and EMPTY forms of each field it reads, and assert the kind and
  text"* — a 5-line pytest over `worker_status_kind`/`worker_status_text` would have caught F3
  and F7 without a human reading the sets. Second: *"grep for the same expression issued twice
  in one function"* as a lint (it would flag `:1415`/`:1420`).
- **review por outro subagente** — **sim-com-escopo**: yes, for F1's user-visible consequence
  (does the double `engine.ingest` change rendered lines?), which needs the join harness and a
  second pair of eyes; the rest of the audit is source+probe backed and does not need it.
- **gate-doubt**:
  - **verde-de-verdade**: the only "green" I produced was the probe run: `pythonw rc=0` and
    the JSON file it wrote. That green is real (the module imported and the functions returned
    the values shown), but it is a *unit*-level green, not an end-to-end one: it does not prove
    the running shell behaves this way on the wire. `--dump-dom`/`bridge-selftest.js` were NOT
    run for this audit.
  - **falta-no-gate**: there is **no** Python-arm regression suite: `bridge-selftest.js`
    (JS) exists, but nothing in `app/webview/` runs `worker_status_kind`/`_consume`. A future
    change that re-orders `_consume`'s severity check, or edits `WORKER_ERROR_STATES`, passes
    nothing RED because nothing tests it.
  - **gate-melhor** — a mechanical check: pytest that asserts
    `worker_status_kind('done', {}) == 'error'` **and**
    `worker_status_kind('done', {'verdict':'captions-emitted'}) == 'busy'` **and**
    `'no audio' in worker_status_text('error', {'stage':'selftest','detail':'no audio at X'}, 'e')`
    **and** that `WorkerBridge._status` does NOT leave that text unchanged. Input that must
    leave it RED: revert `:2065` (delete the `pending_error = None` line) or the `done`
    absent-verdict guard — each should fail.
- **confianca** — **alta** for F1–F4, F7 (source + windowless probe); **media** for F5, F6,
  F10 (source + reasoning about scheduling, not induced); **media-baixa** for F8/F9 (latent,
  live worker never triggers them). What would raise it: the pytest above, and one induced
  start/quit collision against a disposable shell.
- **nao verificado** — listed explicitly in "What I could NOT verify" above (6 items).

---

## CACHE/PRICE

```
$ bash scripts/cache-task-report.sh AuditShellBridge   # rc=0
## CACHE/PRICE
- task/agent: AuditShellBridge
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditShellBridge.jsonl
- cache: read=4133248 write=0 hit=96.5824% (cache-read / input+cache-read); universe: 42 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditShellBridge.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=36 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-4/space-bunny-free $0.00000000; opencode-zen/space-bunny-free $0.00000000
- when-failed: break_items=1; WHEN=2026-10-06T08:24:36.872000+00:00 | break_items=1; WHEN=2026-10-06T08:24:38.308000+00:00 | break_items=3; WHEN=2026-10-06T08:24:41.534000+00:00 | break_items=4; WHEN=2026-10-06T08:26:17.637000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 113439 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditShellBridge']; window: 2026-10-06T08:24:36.872000+00:00..2026-10-06T08:26:17.637000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11050-0fed-77b0-8113-2904569e6bb0 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275076872 | session_id=01a11050-0fed-77b0-8113-2904569e6bb0 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275078308 | session_id=01a11050-0fed-77b0-8113-2904569e6bb0 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275081534 | session_id=01a11050-0fed-77b0-8113-2904569e6bb0 provider=deepseek-flash model=deepseek-flash item_index=87; turn_id=1791275177637 (state=RESOLVED-BREAKS-OMP; …)
- report generated_at: 2026-10-06T08:28:25.995696+00:00
- usage rows: 42
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/space-bunny-free
- input tokens: 146255
- output tokens: 29261
- cache-read tokens: 4133248
- cache-write tokens: 0
- hit ratio: 96.5824% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; …)
- WHEN / WHERE failed: (4 rows, listed above)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

HONEST NOTE on the price: `$0.00000000` is what the session JSONL records, and the exact
per-model rates are `UNKNOWN` in that source — so the true cost is not known from here; I am
reporting the instrument's value, not asserting zero cost.
