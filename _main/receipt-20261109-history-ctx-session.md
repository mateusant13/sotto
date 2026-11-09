status: done

# receipt — history-context snapshot must not cross an audio session (2026-11-09)

Lane: HistoryContextSession. Scope: `app/webview/sotto_webview.py` (the
`_history_ctx_last` / `_history_ctx_last_start` / `ctx-reused` path) and the
focused oracle `_main/history-context-oracle.py`. No battery, no app launch, no
`worker/sotto_worker.py` edit, no `_main/code-health-baseline.json` refresh.

## 1. Reproduce in source — where the leak lives

The snapshot is captured with NO session identity, and the fallback donates it
to any line whose `start` is within 8 s of it:

```
app/webview/sotto_webview.py:14149   self._history_ctx_last = ctx
app/webview/sotto_webview.py:14150   self._history_ctx_last_start = round(float(start), 2)
app/webview/sotto_webview.py:3290    _HISTORY_CTX_NEAR_S = 8.0
app/webview/sotto_webview.py:14179   last = getattr(self, '_history_ctx_last', None)
app/webview/sotto_webview.py:14180   last_start = getattr(self, '_history_ctx_last_start', None)
app/webview/sotto_webview.py:14186       and abs(float(start) - float(last_start)) <= _HISTORY_CTX_NEAR_S:
app/webview/sotto_webview.py:14187       return dict(last)
```

`start` is the WORKER's audio clock, and that clock restarts at zero with every
respawn — the same fact the renderer already relies on:

```
worker/sotto_worker.py:5064    "start": None if self._start is None else round(self._start, 2),
worker/sotto_worker.py:5281    self._start = self._end = None      # every close
worker/sotto_worker.py:5345    self._start = start                # first chunk of a line
app/panel/caption-formulation.js:1036-1038
    // The equality is `===`, not `<`, on purpose: a WORKER RESTART resets the
    // audio clock, so the new session's first chunk carries a start far BELOW
    // the emitted line's.
```

A new child is a new audio clock (`sotto_webview.py:20815 self.spawns += 1`,
`:20928 BRIDGE_SPAWNED pid=...`). So session A's last line at `start=5.0` and
session B's first line at `start=9.0` are numerically "near" while belonging to
different speech; the 8-second window (14186) hands B the app the owner was
looking at while A was closing. The ring lookup at `_history_context_for`'s top
has the same defect when B's `start` lands within 0.05 s of an A entry.

## 2. Fix — a session identity the code proves, cleared at the boundary

Identity chosen: the worker CHILD PROCESS (plus bridge spawn counter), stamped by
`WorkerBridge._consume` from the `child` argument it already receives explicitly
("a dead worker's pipe can still be draining while `self.child` already points at
its replacement", `sotto_webview.py:20893-20896`), and the literal `external`
for the player path (whose `start` is `time.monotonic()`, not the audio clock).

```
app/webview/sotto_webview.py:14073  _history_ctx_session_of(meta)          # reads meta['historySession']
app/webview/sotto_webview.py:14095  _history_ctx_observe_session(session)  # clears ring+last on change
app/webview/sotto_webview.py:14135  observe call in note_history_context (before recording)
app/webview/sotto_webview.py:17085-17087  observe call in on_worker_caption (EVERY caption, incl. partials)
app/webview/sotto_webview.py:17270  'historySession': 'external'
app/webview/sotto_webview.py:17272-17274  observe call in external_caption
app/webview/sotto_webview.py:21260  WorkerBridge.history_session(child)
app/webview/sotto_webview.py:21310  meta['historySession'] = self.history_session(child)
```

Why at the first PARTIAL, not at the first final: partials never call
`note_history_context`, so a partial is the earliest event that can prove the new
clock; observing it drops the old snapshot before any line of the new session can
commit. The two call sites are guarded with `getattr` because probe harnesses
extract these methods (`caption-kept-on-hide-oracle.py`) and must not die on a
partial shell.

`_history_context_for` itself is untouched (the write oracle extracts it by AST);
the guard is at the capture/boundary, not at every reader.

## 3. Oracle extension

`_main/history-context-oracle.py`:

- `s25-nova-sessao-nao-herda-8s` (line 239): session A snapshot at `start=5.0`,
  session B's first PARTIAL at `start=9.0`, then a committed B line at
  `start=9.0`. The old context must NOT appear (expected the fresh `seen`).
- `s25b-nova-sessao-nao-herda-anel`: same boundary, B line at `start=5.0`, so the
  RING key path is exercised too.
- `u7`/`u8` (lines 721-726): the session stamp and the caption-path observation
  are WIRED in the shipped shell, not only implemented.
- `--shell PATH` (line 929): judges a COPY of the shell — the BEFORE proof,
  without reverting the live file.
- `--neg-arm` mutants `n15` (caption path stops observing) and `n16` (observer
  stops clearing) — both must be caught by the new arms.

## 4. Runs (commands + output)

### 4.1 AFTER — live fixed shell

```
$ python _main/history-context-oracle.py
...
ok  s25-nova-sessao-nao-herda-8s
ok  s25b-nova-sessao-nao-herda-anel
ok  u7-consume-carimba-a-sessao
ok  u8-caption-observa-a-sessao
VERDICT: PASS arms 120/120
```

### 4.2 BEFORE — temp copy with the pre-fix decision (live file untouched)

The copy is the current shell with only the session-clear block replaced by
`# PRE-FIX COPY: the snapshot is never cleared on a session change.`
(behaviourally the pre-fix code: capture has no boundary). Built at
`G:\Temp\hist-prefix-s9gldvx_\sotto_webview_pre_fix.py`.

```
$ python _main/history-context-oracle.py --shell "G:\Temp\hist-prefix-s9gldvx_\sotto_webview_pre_fix.py"
RED s25-nova-sessao-nao-herda-8s  got='old-session' want='seen'
RED s25b-nova-sessao-nao-herda-anel  got='old-session' want='seen'
ok  u7-consume-carimba-a-sessao
ok  u8-caption-observa-a-sessao
VERDICT: FAIL arms 118/120
```

`got='old-session'` is the previous session's snapshot being donated — the
defect reproduced, and only the two new arms are red.

### 4.3 `--neg-arm` — the detector's own proof

```
$ python _main/history-context-oracle.py --neg-arm
ok  n15-caption-nao-observa-sessao -> RED: s25-nova-sessao-nao-herda-8s,s25b-nova-sessao-nao-herda-anel,u8-caption-observa-a-sessao
ok  n16-sessao-nao-limpa-o-snapshot -> RED: s25-nova-sessao-nao-herda-8s,s25b-nova-sessao-nao-herda-anel
NEG-ARM PASS mutants 16/16
```

### 4.4 Sibling focused gates (not the battery)

```
$ python _main/history-write-oracle.py   -> VERDICT: PASS
$ python _main/history-merge-oracle.py   -> VERDICT: PASS arms 32/32
$ python _main/caption-kept-on-hide-oracle.py -> caption-kept-on-hide-oracle: PASS
```

The codec lane's arms (`p-*`, `q-*`, `n12..n14`) are intact and green; its
`percentDecode`/`ignoreBOM`/White_Space work was not reverted.

`canonical-producer-oracle.py` judges the same `_consume` hop and pins the meta
key set. Its extraction was updated to carry `history_session` and its
projection to the new contract; the hop was verified directly:

```
$ python (direct extract_consume + shell_projection on the live shell)
text: bom dia, mundo
meta keys: ['end', 'historySession', 'model', 'producer', 'start']
session: worker:2e2a5072810:0:0
producer: redux
keys-ok: True
```

The FULL oracle still aborts BEFORE that arm, at its worker-stamp assertion
(`worker/sotto_worker.py` no longer contains
`"producer": str(payload.get("producer") or REDUX_PRODUCER),` — the file is
dirty and owned by another lane). That failure is not caused by this change and
the worker file was not touched here.

## 5. Residual, stated honestly

`history_append` still receives only `start` (the panel's commit meta is a new
literal `{route, start, routeSource, producer?, source?}`, `caption-formulation.js:821-827`),
so it cannot compare a late commit's session at resolve time. Direction covered:
a NEW session's line can no longer inherit the OLD snapshot (cleared on its first
caption). Direction left: an OLD session's line committed after the new session's
first FINAL could inherit the new snapshot. The practical window is the panel's
1.5 s commit hold vs. the new worker's model load (seconds), and the new session's
partial already cleared the old snapshot; closing it completely needs the session
on the commit options, i.e. a `panel.js` change outside this assignment.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: HistoryContextSession
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['HistoryContextSession']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['HistoryContextSession']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T16:58:27.451733+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['HistoryContextSession']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['HistoryContextSession']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — I added a method call to `external_caption`, a method
  `caption-kept-on-hide-oracle.py` extracts by AST, and it died on the partial
  harness. The missing protocol is "before adding a call inside a method that
  `ast.get_source_segment` extracts, grep the extracting oracles and either add
  the stub or guard with `getattr`". Done after the failure, with `getattr`.
- **verificacao adicional** — a behavioural arm that constructs a real
  `WorkerBridge.__new__` with a fake child and drives `_consume` → `on_caption`,
  asserting the emitted meta carries the token. Cheap (no spawn); not run.
- **checkboxes novas** — mechanical pre-edit check:
  `grep -l "ast.get_source_segment\|get_source_segment" _main/*oracle*.py` before
  touching a method they extract; the command that must stay RED if the guard is
  removed is `python _main/caption-kept-on-hide-oracle.py` (it already is the
  falsifier: it failed before the `getattr` guard).
- **review por outro subagente** — sim-com-escopo: the shell diff (5 sites) and
  the oracle arms/mutants; not the codec lane's symbols.
- **gate-doubt**
  - `verde-de-verdade:` the 120/120 run loads the live shell and the same arms
    are RED on the pre-fix copy (118/120), so the green is not pass-by-
    construction; `--neg-arm` 16/16 kills n15/n16 on the new arms. The
    `--shell` flag is not hand-supplied for the green run (defaults to the live
    file).
  - `falta-no-gate:` the oracle never executes the real `WorkerBridge._consume`
    → `on_worker_caption` round trip. `u7`/`u8` only read source strings, so a
    future refactor that renames `historySession` in one of the two files would
    leave the behavioural arms green (they build the meta by hand) while the
    shipped stamp vanished.
  - `gate-melhor:` add `s26` that calls
    `WorkerBridge._consume` on a JSON caption line with a fake `child.pid` and
    asserts the `on_caption` meta's `historySession` equals
    `bridge.history_session(child)`; input that must leave it RED: delete
    `meta['historySession'] = self.history_session(child)` from `_consume`.
- **confianca** — alta for the source-level boundary and the arms (pre-fix RED
  and post-fix GREEN both observed); media for the residual reverse direction
  (§5), which needs the panel commit to carry the session.
- **nao verificado** — the live app (not launched, per the house rules); a real
  worker restart through the panel commit path; the battery (not run).
