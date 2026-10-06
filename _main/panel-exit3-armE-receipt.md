# panel-exit3-oracle — ARM E (the hold's SECOND half: a caption returns the panel to live)

status: DONE
## Status: DONE

lane: SottoErrorRecovery · repo H:/sotto · date 2026-10-06

## What was asked

`app/webview/sotto_webview.py` now HOLDS a worker death across the automatic
restart until a CAPTION proves recovery (lane SottoExit3Panel). NOTHING asserted
the other half — that a real caption actually CLEARS the held error and returns
the panel to the live state. Every existing arm would stay green on a fix that
held forever, because none ever feeds a caption after an error. Deliver ARM E
into `_main/panel-exit3-oracle.py` (no third oracle), with a RED copy of today's
shell that removes the CLEAR path.

## Deliverable 1 — ARM E, added to `_main/panel-exit3-oracle.py`

`arm0_recovery()` drives the shell's OWN `WorkerBridge` (the same driver ARM 0
and ARM D use — no device, no model, no WebView2), runs the REAL exit-3 sequence
(`silent-device` status, the worker's own `done`, then the non-zero exit that
arms the hold), then feeds a REAL caption on the SAME bridge:

* E1 death on screen and HELD · E2 restart warm-up (`model-loading`) SWALLOWED ·
  E3 caption DELIVERED to the page handler · E4 caption LIFTS the hold
  (`pending_error` None, `BRIDGE_DEATH_LIFTED` logged) · E5 panel LIVE
  (`Receiving captions`, error=false, placeholder GONE) · E6 warm-up AFTER the
  caption PAINTS again (not held).

Gate (both colours in ONE command):

```
$ py -3 _main/panel-exit3-oracle.py --unit --neg-arm
  "arm_e_recovery": {
    "error_state": {"footer": "Worker stopped (exit 3) - Worker finished on silent-device", "error": true, "holding": true},
    "held_once": true,
    "caption_delivered": true,
    "lifted": true,
    "live_state": {"footer": "Receiving captions", "error": false, "placeholderHidden": true, "delivered": true},
    "warmup_after_caption_painted": true
  }
  "verdict": "PASS", "failures": []
```

## Deliverable 2 — RED input: the CLEAR path removed in a COPY

`build_neg_mutant_e()` builds `_main/_panel-clear-lifted-mutant.py` from TODAY's
shell by removing exactly the 3-line CLEAR block. Guards: the block must appear
EXACTLY once (counted) or the arm REFUSES, and the artefact hash must MOVE:

```
"neg_arm_e": {
  "mutant": "H:\\sotto\\_main\\_panel-clear-lifted-mutant.py",
  "src_sha16": "d4392f8779a8f948",
  "mutant_sha16": "9a971d2049666007",
  "child_rc": 1,
  "child_failures": [
    "ARM 0/recover: a caption did not lift the pending death",
    "ARM E/E4: the caption did NOT lift the held death (pending_error is still set)",
    "ARM E/E4: no BRIDGE_DEATH_LIFTED line -- the clear path never ran",
    "ARM E/E5: the panel did NOT return to live after the caption -- it stayed in ERROR showing 'Worker stopped (exit 3) - Worker finished on silent-device'",
    "ARM E/E5: the panel is not showing the live footer 'Receiving captions': 'Worker stopped (exit 3) - Worker finished on silent-device'",
    "ARM E/E5: the placeholder is still up after the caption (panel.js:156 hides it on the first committed line)",
    "ARM E/E6: a warm-up AFTER the caption was still HELD -- the clear did not take, the hold is sticky"
  ]
}
```

The mutant goes RED on the EXACT claim (the panel stays in ERROR), and ARM D
stays GREEN (no `done-*` case appears in `child_failures`) — the mutation is
surgical, not a mutant that broke everything. Count guard, measured:

```
$ PANEL_ORACLE_SHELL=_panel-clear-lifted-mutant.py py -3 _main/panel-exit3-oracle.py --unit --neg-arm   # rc=1
    "NEGATIVE ARM E: cannot build the mutant: the CLEAR block appears 0 times in ... (expected exactly 1)"
```

## Acceptance — BOTH painted states, from the REAL shell

`--arm-e-real` runs the REAL WebView2 shell twice, driven by the fake worker
`_main/_armE-fake-worker.py` (it writes only the line shapes
`worker/sotto_worker.py` writes — the shell's own `_consume` handles it). The
three `--dump-dom` DOMs below are the shell's OWN `BRIDGEPROBE` (`rendered()`),
not the unit driver. Source: `_main/_armE-real-out.txt`.

ERROR (mode=hold — the exit-3 death, held across 4 restarts, NO caption ever):
```
"text": "Worker stopped (exit 3) - Worker finished on silent-device",
"error": true, "live": false, "className": "status status--error",
"placeholderTitle": "Worker stopped",
"placeholderBody": "verdict=silent-device device=Mapeador de som da Microsoft - Input peak=0.000122 blocks=34 captions=0 A restart is scheduled. Captions stay off until the worker reports a caption.",
"placeholderHidden": false, "captions": 0
"worker_exits": [3,3,3,3]   "lifted_lines": []      # no caption => never lifts
```

LIVE (mode=recover — run 1 dies exit 3; run 2 emits `model-loading` (HELD) then a
REAL caption, and the page's hold timer commits it):
```
"text": "Receiving captions",
"error": false, "live": true, "className": "status status--live",
"placeholderHidden": true, "captions": 1
"worker_exits": [3, 1]
"death_lines":  ["sotto: BRIDGE_DEATH rc=3 deaths=1 last=\"Worker finished on silent-device\""]
"held_lines":   ["sotto: BRIDGE_STATUS_HELD state=\"model-loading\" behind=\"done\""]
"lifted_lines": ["sotto: BRIDGE_DEATH_LIFTED reason=caption captions=1"]
```

So BOTH halves are shown on the real panel: the death survives the restart
(`BRIDGE_STATUS_HELD`, DOM error over 4 deaths), and the caption returns it to
live (`BRIDGE_DEATH_LIFTED`, DOM `Receiving captions`, placeholder gone). The
`hold` run is also the real-shell NEGATIVE arm: without a caption the panel never
returned to live in 12 s across 4 deaths.

## Measurement that CONTRADICTS the brief (reported as required)

`_armE-window-census.py` samples visible top-level windows owned by THIS probe's
OWN pid tree, every 100 ms (env `CENSUS_CADENCE_MS`), and the child is spawned
`CREATE_NO_WINDOW`. In 2 of the real-shell runs it caught the panel window
VISIBLE:

```
CENSUS-PID visible pid=36332 hwnd=6955742 title='Sotto' sample=4      # 200 ms cadence, 1/163
CENSUS-PID visible pid=32508 hwnd=82451080 title='Sotto' sample=168   # 100 ms cadence, 1/302
CENSUS-PID visible pid=1568 hwnd=1712882 title='Sotto' class='WindowsForms10.Window.8.app.0.aec740_r16_ad1' sample=25   # 30 ms cadence, 1/… (shell run directly)
```
The third catch carries the CLASS NAME, and it is the SAME WinForms class
AGENTS.md's own BEFORE-run failure record names (`_main/panel-startup-visibility.log`,
arm P, `WindowsForms10.Window.8.app.0.aec740_r16_ad1`) — so the visible window is
the panel's OWN top-level form, not a WebView2 helper. In the other runs the
census caught NOTHING:
```
CENSUS-PID pid_tree_root=36216 samples=164 visible_samples_over_tree=0 distinct=0      # 200 ms
CENSUS-PID pid_tree_root=18448 samples=767 visible_samples_over_tree=0 distinct=0      # 30 ms, oracle-wrapped
```
So 3 of 5 censuses caught it (each for a single sample, i.e. a sub-sample flash);
the shell's OWN visibility log in every run reports `PANEL_VISIBILITY_ON_SCREEN
visible=false` (`_main/panel-exit3-armE-{hold,recover}.log:19`). An intermittent,
sub-sample-length panel flash at shell startup was therefore caught by my own
census, contradicting AGENTS.md's `arm P 0 of 41` claim — at least for the
`python.exe` launcher this oracle uses (the AGENTS.md oracle ran `pythonw.exe`).
Not rooted out here (out of this lane's scope); flagged for the visibility lane.

## GATE-CHANGE REQUEST

- gate: `_main/panel-exit3-oracle.py` — `py -3 _main/panel-exit3-oracle.py --unit --neg-arm`
  (and `--arm-e-real` for the two real DOMs).
- change (already landed in the gate): add `arm0_recovery()` = ARM E; wire it into
  `--unit` and the default run; add `build_neg_mutant_e()` + `neg_arm_e()` under
  `--neg-arm`; extend `rendered()` with `placeholderHidden`; add `env=` to
  `run_shell`; add `--arm-e-real`. New support files: `_main/_armE-fake-worker.py`,
  `_main/_armE-window-census.py`. `AGENTS.md` holds the contract row (both halves
  now gated).
- non-vacuity control: the CLEAR-removed COPY must (and does) go RED, on ARM E
  specifically, with ARM D green — see `neg_arm_e` output above.

## SELF-AUDIT

- protocolos em falta — I read AGENTS.md first and followed the no-window rule,
  but I DID NOT read `scripts/self-audit-lint.sh`'s receipt contract BEFORE
  working, only at close; that is why the GATE-CHANGE REQUEST block was added
  late. Next time: read the receipt linter up front when the deliverable is a
  gate. Also: the SELO DO DONO injected every turn named 4-5 external governors
  in VERMELHO; those are owned by Task Scheduler scripts and this seat has no
  dispatch, so I could only report them, not close them — I did not touch them.
- verificacao adicional — a THIRD real-shell run with the caption removed is a
  negative control I already have (the `hold` mode, 4 deaths, `lifted_lines: []`);
  the extra check I'd add is a real-shell mutant run (point `PANEL_ORACLE_SHELL`
  at the clear-removed COPY and run `--arm-e-real`) — NOT run: the real-shell arm
  spawns the shell with a fixed `SHELL` constant, so the mutant run is unit-only.
  Cost to add: ~1 small change to pass the shell path through to the real arm.
- checkboxes novas — MECHANIC: (1) after any oracle edit, run BOTH
  `--unit --neg-arm` AND `--arm-e-real` and assert `verdict PASS` in each; (2) a
  gate that adds a PAINT assertion must carry a mutant whose RED names that exact
  assertion (here `ARM E/E5`), not just any red.
- review por outro subagente — sim-com-escopo: send the diff of
  `_main/panel-exit3-oracle.py` + `_main/_armE-fake-worker.py` to a reviewer for
  (a) whether ARM E's live-state model over-claims vs the real page's
  unconditional `addCaption` paint, and (b) whether `neg_arm_e`'s "ARM D must
  stay green" list is complete. I accept a pass to another subagent.
- gate-doubt:
  - verde-de-verdade: the gate GREEN is real — it ran on the current shell (not a
    stale copy), the mutant is rebuilt from TODAY's shell with a hash-moved guard,
    and the ARM E assertions FAILED on the mutant (`child_rc=1` with named `ARM E`
    failures) proving the assertions can say NO. The real-shell GREEN is a real
    WebView2 `BRIDGEPROBE`, and the `hold` run (no caption) showed the panel NOT
    returning to live — the arm is not green by construction.
  - falta-no-gate: ARM E asserts the CONTRACT (death on screen until the caption
    lifts it). What it does NOT verify: the real page's `addCaption` paints
    `Receiving captions` on ANY caption UNCONDITIONALLY (panel.js:189), so on the
    real shell a broken clear would still paint live and a future change that
    removed the clear would show up as the STALE HOLD (later warm-ups swallowed),
    not a red footer. The arm asserts both (E4/E6 and E5), but the E5 red is a
    model fact, not a real-DOM fact. A future change that neutralises `addCaption`
    while keeping the clear would be caught only by E5's stub, not by the DOM.
  - gate-melhor: run `--arm-e-real` with `PANEL_ORACLE_SHELL` pointing at the
    clear-removed COPY and assert the recover DOM STILL goes live but the shell log
    carries NO `BRIDGE_DEATH_LIFTED` and a warm-up AFTER the caption is HELD —
    command: `PANEL_ORACLE_SHELL=_panel-clear-lifted-mutant.py py -3
    _main/panel-exit3-oracle.py --arm-e-real`; input that must leave it RED: the
    clear-removed COPY (expected `BRIDGE_DEATH_LIFTED` absent). NOT wired yet
    (named as cost above) — the current real arm imports a fixed `SHELL`.
- confianca — alta for the unit ARM E + mutant (deterministic, reproducible);
  media for the real-shell arm (sound but 35 s and launcher-dependent); the window
  flash finding is LOW-confidence on rate (2 of 4 censuses) but the window itself
  was real when caught.
- nao verificado — (a) a real-shell run of the CLEAR-removed mutant (named above);
  (b) the exact origin/duration of the startup panel flash (my census caught 1
  sample; I did not bound it with a tighter instrument); (c) ARM E under the
  Electron arm (`app/electron/`), which is LEGACY.

## CACHE/PRICE

- cache: read=8533504 write=0 hit=97.8517% (cache-read / input+cache-read); universe: 59 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoErrorRecovery.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: WHEN=2026-10-06T07:36:19.595000+00:00 (1) | 07:36:20.691000 (1) | 07:36:21.936000 (1) | 07:36:22.481000 (3) | 07:38:08.779000 (3) | 07:43:42.309000 (1) — 10 prefix breaks, state=RESOLVED-BREAKS-OMP
- where-failed: session_id=01a11024-2635-71f0-8264-ef87ba2f3f6d, providers cline-pass/stealth/pixel-canary item_index=0, space-bunny-free item_index=0, ling-3.1-flash-free item_index=0, deepseek-flash item_index=0/54/143
- source: stdout of `scripts/cache-task-report.sh SottoErrorRecovery` (2026-10-06T07:47:31Z); full report at artifact://1303
