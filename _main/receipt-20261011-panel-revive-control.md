# Receipt — the panel's repair control now exists (2026-10-11)

## What was missing, measured

`app/panel/panel.js` wires the footer status as a REPAIR CONTROL: one click asks the shell to kill
the worker and respawn it. It carries **23** `revive` references — `reviveSupported()` (`:2007`)
gates the click on `typeof bridge.revive === 'function'`, `revivePipeline()` (`:2013`) posts
`bridge.revive('panel-status')` (`:2045`), and `:1968-1969` states the contract in words: *"the SHELL
does the killing and the respawning (`SottoShell.revive_worker`) — the panel never spawns anything
itself"*. Instrument: `grep -n revive` over `app/webview/**` → **ZERO matches**. The shell half was
never written, so on every launch the control reported itself unsupported and the owner's ONLY
recovery from a stalled pipeline was a dead click reading *"This shell cannot restart the pipeline (no
bridge.revive())"*.

That is not a cosmetic gap. The measured Alt+C failure of 2026-10-11 was a worker whose tap FROZE
mid-stream while the process stayed alive (~34 min deaf, 68x `BRIDGE_SILENT_BENIGN … reason=flat`).
The repair control is exactly the affordance for that state — and it answered nothing.

## What was added (6 additive edits, no behaviour removed)

| # | site | edit |
|---|---|---|
| 1 | `START_REASONS` | `'revive'` added, so `start_worker('revive')` cannot decline |
| 2 | `SottoShell.__init__` | `_revive_lock` + `_revive_thread` (the in-flight latch) |
| 3 | message dispatch dict | `'revive': self._revive` — without it the page's post landed in `BRIDGE_UNKNOWN_KIND` |
| 4 | `_revive(payload)` | the transport: `self._shell.revive_worker(payload['reason'] or 'page')` |
| 5 | `revive_worker` + `_do_revive` | the decision and the worker half (see the order below) |
| 6 | injected `window.sotto` | `revive: function (reason) { post('revive', {reason: …}); }` |

The ORDER inside the revive is the contract: reload timers stop FIRST (a reload boundary landing in
the middle would fight the restart) → the old child stops with `reason='revive'` → the two latches
about THAT child are dropped (`pending_error` is the sticky death the panel keeps painting until a
caption proves recovery; `no_audio` is a verdict about the child just killed, and carried over it
would paint the fresh worker as deaf before it had opened a device) → `start_worker('revive')`
respawns. The panel is painted `Restarting the pipeline…` / `busy` BEFORE the thread starts, so the
control never looks dead for the half second the child takes to die, and a second click inside that
window is refused with `REVIVE_REFUSED reason=already-in-flight` instead of stacking a second spawn.

## The instrument, and that it can say NO

`py -3 _main/revive-pipeline-oracle.py --shell-only` — ARM S runs `revive_worker` **in process**
against fake child/bridge/reload objects. It never launches the shell, the worker or a browser.

* **WITH the fix: `ARM S: GREEN` / `VERDICT: PASS` / rc=0** (17 assertions, incl. the exact paint
  sentence, the refusal path, `stop_reason='revive'`, both latches dropped, `start_worker` called
  exactly once, the reload policy stopped exactly once, and the in-flight latch released).
* **WITHOUT it — the same arm against the PRE-CHANGE shell** (`git show HEAD:app/webview/sotto_webview.py`
  → a copy beside the live shell, because the shell imports `hot_reload` from its own directory):
  `AttributeError: 'FakeShell' object has no attribute 'revive_worker'` — **rc=1**. The arm cannot
  pass on a shell without the fix, so the green is not vacuous.
* CONTROL-2's premise is verified STATICALLY: the oracle builds its shell mutant by stripping the
  exact line `            'revive': self._revive,` — that line exists in the file, so the control is
  available to the run that is allowed to launch.

## Pins (instrument: `node` + `crypto.createHash('sha256')` over the raw bytes)

| revision | bytes | sha256 | endings |
|---|---|---|---|
| committed blob at `bf325c3` (pre-change, LF as git stores it) | 410 967 | `933AA193A111EE2F…` | LF |
| working tree before this change (CRLF) | 419 259 | `AB2A824C5F2AC07F…` (16-hex) | 8 292 CRLF / 0 bare LF |
| **after this change** | **424 688** | **`C28CEA4ADD837A6757511AD8F602901F4EED68AE0E1A83CDE5F9F6E6C97B7827`** | **8 393 CRLF / 0 bare LF** |

`py -3 -m py_compile app/webview/sotto_webview.py` → rc=0. `app/panel/panel.js` was NOT touched
(sha256 `8b09859707e00292…`) — the panel half already existed.

## UNMEASURED, and why (owner's standing order, top of AGENTS.md)

The oracle's other arms LAUNCH things, so they are deferred to the authorised-launch batch:
**ARM P / ARM P2** (panel.js in a real Chromium, with and without `bridge.revive`), **ARM L** (the
live shell with a real worker, a real click at 22 s), and **`--neg-arm`** (CONTROL-1 panel minus
`wireRevive();`, CONTROL-2 shell minus its dispatch entry — the latter launches the shell with
`--no-worker`). Until those run, the composite claim "click → worker respawned in the real app" is
**NOT measured**; what IS measured is the shell's decision procedure (ARM S) and the panel's own
wiring (unchanged, previously measured by the same oracle).

**Not claimed:** that a revive recovers a FROZEN tap in the real app. ARM S proves the ordering and
the latches; the live click path is ARM L's job.
