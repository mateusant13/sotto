# Receipt — the panel no longer maps at startup (2026-10-07)

Lane: `SottoStartupFlash-2` — repo `H:/sotto` ONLY (owner order, verbatim:
*"trabalha só no sotto. nao mais no maanger ou omp"*). No audio was ever rendered
to `VoiceMeier Input` or the default output (*"nao quero ouvir"*): every launch in
this receipt ran `--no-hotkey`, and every measured copy had its window moved to
`x=-10000` so it is on NO monitor.

**VERDICT: FIXED AND MEASURED.** A plain launch no longer maps the panel.
`live` (fixed) **0 of 20** launches with the window mapped; `nogate` (the same
file with ONLY this cure reverted) **4 of 20** launches, longest **57.1 ms**,
5 mapped samples. The control pair differs, and the negative arm shows the
instrument is not blind.

---

## 1. Which call maps the window, and where

Measured, not reasoned: the mapping call is **pywebview's own**, on every
navigation start, and it does not consult any shell gate.

| call | path | line |
|---|---|---|
| the map | `self.form.Show()` inside `on_navigation_start` | `C:/Program Files/Python311/Lib/site-packages/webview/platforms/edgechromium.py:348` (block `:345-349`, gated on `self.pywebview_window.transparent`) |
| its subscription | `self.webview.NavigationStarting += self.on_navigation_start` | `.../webview/platforms/edgechromium.py:102` |
| the creation dance (invisible, alpha=0) | `browser.Show()` | `.../webview/platforms/winforms.py:779` |

The shell's own gate — `if self.args.show or self.visible: return` in
`_on_navigation_start` — is on a DIFFERENT call (its own `hide_window`), so
pywebview's `Show()` walked straight past it. That is the "real gate" the brief
asks for, and it was not in force on the mapping call.

## 2. The fix — refuse the map, do not re-hide it

`app/webview/sotto_webview.py`: new method `_gate_form_show` (installed from
`_on_before_show`). `Show` is a .NET method but pywebview calls it from PYTHON,
so an attribute on the INSTANCE shadows it for exactly that call — measured in
`_main/_pythonnet-show-shadow-test.py`:

```
subclass: type(s).Show is Sub.Show -> True
subclass: s.Show resolves to -> SUBCLASS-GATED
instance: setattr accepted; base.Show -> <function main.<locals>.gated …>
instance: base.Show() -> INSTANCE-GATED
instance: after attempt, type(base).Show -> <unbound method 'Show'>
```

The guard refuses a full-opacity map when nobody asked; it ALLOWS pywebview's own
creation dance (`Opacity < 1`, invisible by construction) and does not touch
`show_panel` (user32 `ShowWindow(SW_SHOWNOACTIVATE)`), which is the path BOTH
user gestures take (`--show` → `_on_loaded` → `show_panel('startup')`; Alt+C →
`toggle_panel` → `show_panel`). **No subscription changes**, so
`_main/panel-hidden-at-startup-oracle.py`'s assertion
`NavigationStarting handlers=2 (1 pywebview + 1 shell)` keeps its exact meaning.

Mechanism, in the app's OWN log (`_main/_flash-live-0.log`) — two navigations,
two refusals, app healthy:

```
sotto: PANEL_SHOW_GATE installed=true method=BrowserForm.Show refuses=map-at-full-opacity-unless-asked
sotto: PANEL_VISIBILITY_AT_STARTUP visible=false … show_requested=false
sotto: PANEL_SHOW_REFUSED reason=not-asked opacity=1.0 … count=1 cure=_gate_form_show source=edgechromium.py:348
sotto: PRELOAD_INSTALLED where=initialization-completed status=RanToCompletion
sotto: STAGING_LOADED core=yes -> navigating to panel H:\sotto\app\electron\panel.html
sotto: PANEL_SHOW_REFUSED reason=not-asked opacity=1.0 … count=2 cure=_gate_form_show source=edgechromium.py:348
sotto: RECEIVER_READY captions=0 hasBridge=True placeholder="Waiting for audio …"
sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=63578724 panel_shown=false show_requested=false
sotto: SHELL_EXIT rc=0 reason=requested
```

Every one of the 19 completed fixed-arm launches carries `count=1` then
`count=2` — 38 refusal lines over 38 files (`_flash-live-*.log` and `.stdout`).

## 3. The instrument's own output — both arms at 25 ms, N=20 each

```
=== VERDICT ===
mech = WS_VISIBLE & alpha!=0 (the Show happened; POSITION ignored)
owner = mech AND on a monitor (what the owner can actually see)
live: launches_with_mech=0/20 mech_samples=0 owner_samples=0 occluded_samples=5 longest_mech_ms=0 longest_owner_ms=0
nogate: launches_with_mech=4/20 mech_samples=5 owner_samples=0 occluded_samples=5 longest_mech_ms=57 longest_owner_ms=0
NEGATIVE-ARM mechanism reproduces=true (neg arms present=1) | FIXED arms mech-clean=true (fixed arms present=1)
```

`_main/_sflash-pair20.out` (sha256 of the measured shells logged as
`sha256_live=64ed8606a996b892`). The `nogate` arm is the PRE-fix shell in
behaviour: its only edit is
`self._gate_form_show(form)` → a `pass` comment (the counter and docstrings are
inert). Its episodes, per launch:

```
FLASH nogate launch=9  at=943.8ms  dur~0.0ms  mech=true phase=at-startup-marker
FLASH nogate launch=10 at=1472.5ms dur~0.0ms  mech=true phase=after-a-reassert
FLASH nogate launch=13 at=890.7ms  dur~0.0ms  mech=true phase=before-startup-markers
FLASH nogate launch=19 at=901.4ms  dur~57.1ms mech=true phase=at-startup-marker
```

The same class of window, same instrument, before the fix — PRE-fix baseline
taken the same day on the pre-edit file (`sha256 becac0a6…`),
`_main/_sflash-smoke.out`:

```
ARM-SUMMARY live:   launched=6 launches_with_mech=1/6 samples=1014 mech_samples=1  longest_mech_ms=0
ARM-SUMMARY nocure: launched=6 launches_with_mech=6/6 samples=968  mech_samples=546 longest_mech_ms=6130
```

### The gross control (instrument not blind)

`nocure` — the navigation-start subscription reverted to the CoreWebView2 event
— kept the window mapped for **~5.2–6.1 s on 6 of 6 launches** (`_sflash-smoke.out`).
`nogate-nonet` (this cure AND the re-assert subscription removed) is wired into
the instrument for the same purpose. The instrument refuses to print a verdict
without BOTH halves, and says so when one is missing.

## 4. The owner's own ask still works, and the panel still PAINTS

`--show` (the arm that is allowed to put a window on a monitor; the copy is still
parked at `x=-10000`, so nothing reached the owner's desk):

```
show: launches_with_mech=6/6 mech_samples=787 longest_mech_ms=6297   (_sflash-show.out)
sotto: PANEL_SHOWN reason=startup visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
sotto: PANEL_VISIBILITY_ON_SCREEN visible=true where=startup … panel_shown=true show_requested=true
```

Paint, through `PrintWindow(PW_RENDERFULLCONTENT)` — `_main/panel-paint-probe.py`
(off-monitor copy, capture taken AFTER `PANEL_SHOWN` + 2 s settle):

```
FIXED   (gate present): asked: PAINTED distinct_colours=65 t_s=3.21 px_sha256=1e762bdd6b55d0c6
                        notasked: NO-WINDOW          PAINT-VERDICT PASS   (rc=0)
CONTROL (gate removed): asked: PAINTED distinct_colours=65 t_s=3.21 px_sha256=1e762bdd6b55d0c6
                        notasked: NO-WINDOW          PAINT-VERDICT PASS   (rc=0)
```

**Byte-identical pixel hash** with and without the gate: the cure changed
nothing about what the panel paints when the owner asks for it, and the
`notasked` arm returns NO-WINDOW — the capture is not measuring a stale or
cached bitmap.

## 5. Files touched — sha256 before → after

| file | before | after |
|---|---|---|
| `app/webview/sotto_webview.py` | `becac0a6c1dfd6b082f1384fac86a91bcf152a78587f9b276ce0eb6394f3ac02` | `64ed8606a996b892665a647a440cbdc672d809c297fa7011ee7b84d76b6b569b` |
| `_main/panel-startup-flash-census.py` | `f0eeb05cf92458fcef0a7b9e20c548fec56abf1f9964da59737e3acb812de68c` | `062cc39e840bc2a01cfea2dbdde724ecf7497223e9b4cd493fb28cbdedcd5cfd` |
| `AGENTS.md` | `80570f027c1c3a0e23ed941629bd7bd046b3de2b944cfba22091ce1aec7a3729` | `38696e3e6d555ec4ad892bdd68db910346af8abd3a5ad0b9433cd1b1eaaacafe` |
| `_main/panel-paint-probe.py` (new) | — | `7b23e4d63dbd74a534d2dc6b63400488dccda53fbd818a484bfa7c8de9c33acd` |
| `_main/_pythonnet-show-shadow-test.py` (new) | — | `1dc95dd3a4318aeb385fb24b5be0a74497dc3510316edc3cf67752e4894e4397` |

All four are `py_compile` rc=0 (`_main/_compile-check2.out`). AGENTS.md's claim
that `--opaque` was "the only measured closure" was false after this work and is
corrected in place. **Non-goals respected**: `_main/run-cmd-exit-oracle.py`,
`worker/**` (M1–M3) and `app/electron/caption-formulation.js` were not touched.

### Instrument defects found and fixed on the way (they were gates, not cosmetics)

1. `precure`'s pattern named the OLD `self.core.NavigationStarting` registration
   → `build_variant` raised `SystemExit` and **the instrument's default arms
   could not run at all**. Pattern now names today's line.
2. The verdict judged FIXED arms on `owner_samples`, and every fixed arm is an
   off-screen copy, so `owner` is **0 BY CONSTRUCTION** — it printed
   `FIXED-CLEAN` for a shell that still flashed, on every run before today. It
   now judges `mech`, the axis the negative arms move and the axis that travels
   (a docked launch is on the primary monitor, so `mech=0 ⇒ owner=0` there).
3. A run with NO arms printed `VERDICT PASS` (both halves vacuous). The vacuous
   half is now named in the log.
4. The default arm set (`precure,real,opaque`) could never be a control pair
   (`real` is refused by default). Default is now `live,nogate,opaque`.
5. **NOT fixed, reported:** the census's `at_startup`/`on_screen` columns can
   disagree with the very log they read — `_flash-show-0.log:21` says
   `PANEL_VISIBILITY_ON_SCREEN visible=true` while the census printed
   `on_screen=False` for that launch (5 of 6 show-arm launches). The `mech`
   counts do not use that parse, so the pair above is unaffected.

## 6. Disclosures (what a reader must not have to discover)

- **1 of 20 fixed-arm launches stalled** (`LAUNCH live 1/20 rc=-999`, no
  `PANEL_VISIBILITY_ON_SCREEN`). Its log (`_main/_flash-live-1.log`) stops after
  `PANEL_VISIBILITY_AT_STARTUP` — **before** `CoreWebView2InitializationCompleted`,
  with NO `PANEL_SHOW_REFUSED` and no `STAGING_LOADED`. That is upstream of the
  gate (no navigation ever started), so the gate cannot be its cause; it is
  unattributed, and 1 event cannot separate a 5 % pre-existing rate from a 0 %
  one. Pre-edit runs: 20 launches, 0 stalls; post-edit: 40 launches, 1 stall.
- **The house 60 s census named MY copies**: `ALERTA-JANELA ts=05:23:21Z
  pid=16116 … _flash-show-sotto_webview.py … --show` and again at `05:24:21Z`
  for `_paint-offscreen-sotto_webview.py … --show` (governor `ManagerWindowCensus`
  went `VERMELHO-FALHA` because of them). Both are the `asked` arms, whose whole
  point is a mapped window, and both are at `x=-10000`, i.e. on no monitor —
  the census reads `IsWindowVisible`, not position. Nothing appeared on the
  owner's screen; the alarms are the census doing its job on an off-desk window.
- **Residual:** the creation-dance map remains (5 of 20 launches, one 25 ms
  sample, `alpha=0` ⇒ fully transparent — the same class the house already
  accepts for `--opaque`). `catches` ≠ 0 even where `mech` is 0.
- The observer governor pendency (G:/superharness, daemon stale) that the owner's
  seal names is **not this lane's and not in `H:/sotto`**; its remedy is a
  restart from the shell that owns the daemon pid, which this seat does not own.

## SELF-AUDIT

- **protocolos em falta** — I did not re-read `_main/panel-hidden-at-startup-oracle.py`
  before editing the shell, only its grep hits. It asserts the subscription
  structure I preserved, so it stayed valid — but that is luck ordered by
  design, not procedure. Next time: run the owning oracle BEFORE the edit as a
  pre-flight, not after as a hope.
- **verificacao adicional** — (a) DONE, and it was the one that mattered: the
  paint check first returned `UNIFORM`, which I nearly read as "the gate blanked
  the panel"; the control (gate reverted) returned the identical blank hash,
  which exposed my probe's timing artifact (it captured the creation-dance blip
  at t≈0.95 s). (b) Still open and cheap: `CoreWebView2.CapturePreviewAsync` as a
  second, independent pixel route. (c) Re-run the fixed arm at N=40 to bound the
  1/20 stall (~9 min).
- **checkboxes novas** — TWO, both mechanical: **(1) "capture after the ask"** —
  a pixel assertion about a window is VOID unless the capture is taken after the
  process's own "shown" marker; RED input is my own `_paint-probe.out`
  (`t_s=0.95`, `distinct_colours=1`, run after the panel had loaded fine).
  **(2) "the fixed arm is judged on the axis the negative arm moves"** — read the
  criterion's axis and the arm's own geometry; if a fixed arm is off-screen, an
  `owner`-based criterion is vacuous. RED input: the census's own pre-today
  verdict on a shell that still flashed.
- **review por outro subagente** — **sim-com-escopo**: an independent lane should
  (a) re-run `_main/panel-startup-flash-census.py --n 20 --arms live,nogate`
  against `sha256 64ed8606…` and check the two counts differ, (b) try to make a
  plain launch map a window by any OTHER route (a pywebview upgrade, a second
  `Show()` path, `window.show()`), and (c) falsify the claim that the stall is
  upstream of the gate.
- **gate-doubt**
  - **verde-de-verdade**: the PASS in `_sflash-pair20.out` is real —
    `live 0/20` vs `nogate 4/20` is a measured difference with a negative arm
    present. The greens I must DISCOUNT: (i) the earlier 30-second census runs
    printed `VERDICT PASS` on `opaque` alone with **zero arms in both lists**
    (vacuous; now logged); (ii) the pre-today census would have printed
    `FIXED-CLEAN` on `owner_samples` for a shell that flashed (vacuous axis; now
    `mech`); (iii) the first paint runs returned `UNIFORM` for a panel that
    paints (instrument artifact, caught only because I ran the control).
  - **falta-no-gate**: (a) NO gate asserts that the FIXED arm of a flash census is
    itself a copy of the shipping file — `live` is built by the instrument, and a
    stale/hand-edited `live` variant would be judged as the app. (b) NO gate
    asserts that the *ask* still works: a cure that refuses every map —
    including `--show`/Alt+C — would make `mech=0` and pass every criterion
    here while costing the owner the panel; I ran the `show` arm by hand, and
    nothing forces that. (c) NO gate ties the census's `at_startup`/`on_screen`
    columns back to the log lines they claim to parse (defect 5 above, live and
    unfixed).
  - *gate-melhor*: (a) **ask-must-work**: in the same run, `--arms show --n 2`
    must print `PANEL_SHOWN reason=startup visible=true` in the child's log, else
    RED — RED input is a gate variant that refuses `self.args.show` too
    (one-line mutation of `_gate_form_show`). (b) **criterion-axis assertion**:
    if every fixed arm ran off-screen, the verdict line must say
    `axis=mech (owner vacuous by geometry)`; RED input is the pre-today criterion
    at `panel-startup-flash-census.py`. (c) **parsed-column round-trip**: for
    every launch, assert the census's `on_visible` equals the last
    `PANEL_VISIBILITY_ON_SCREEN visible=` in the same file; RED input is
    `_flash-show-0.log` vs the `show 0/6` line of `_sflash-show.out`.
- **confianca** — **alta** for the fix and the pair (two independent signals: the
  25 ms window enumeration and the app's own two refusal lines per launch, plus a
  byte-identical paint hash with and without the gate). **media** for the stall's
  attribution (1 event) and for the census's parsed columns (known bug).
- **nao verificado** — (1) why `live 1/20` stalled; (2) painting with the panel
  ON a monitor (both paint arms are off-monitor — `PrintWindow` proved content
  exists, not where it lands); (3) `Alt+C` end-to-end on the owner's desk (only
  `--show` was measured; no probe registers Alt+C by design — AGENTS.md forbids
  it); (4) the census's `at_startup`/`on_screen` parse disagreement; (5) the
  `nocure`/`precure` arms as negative controls after this cure (the `nocure` arm
  now installs the gate before its own registration crashes, so it is no longer
  a valid negative — `nogate` is); (6) the AGENTS.md claim that this gate also
  survives a pywebview upgrade — it depends on `Show` being called from Python.

## CACHE/PRICE

`bash 'I:/!manager/scripts/cache-task-report.sh' SottoStartupFlash-2` — verbatim:

```
## CACHE/PRICE
- task/agent: SottoStartupFlash-2
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoStartupFlash-2.jsonl
- cache: read=18975744 write=0 hit=98.4131% (cache-read / input+cache-read); universe: 79 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoStartupFlash-2.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=78 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 79 of 79 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-07T05:02:48.371000+00:00 | break_items=2; WHEN=2026-10-07T05:04:55.312000+00:00 | break_items=2; WHEN=2026-10-07T05:10:24.129000+00:00 | break_items=1; WHEN=2026-10-07T05:22:24.541000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 126223 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoStartupFlash-2']; window: 2026-10-07T05:02:48.371000+00:00..2026-10-07T05:22:24.541000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114be-14ad-7324-ba87-c1db776b4611 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791349368371 | session_id=01a114be-14ad-7324-ba87-c1db776b4611 provider=deepseek-flash model=deepseek-flash item_index=45; turn_id=1791349495312 | session_id=01a114be-14ad-7324-ba87-c1db776b4611 provider=deepseek-flash model=deepseek-flash item_index=109; turn_id=1791349824129 | session_id=01a114be-14ad-7324-ba87-c1db776b4611 provider=deepseek-flash model=deepseek-flash item_index=232; turn_id=1791350544541 (state=RESOLVED-BREAKS-OMP; population: 4 of 126223 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoStartupFlash-2']; window: 2026-10-07T05:02:48.371000+00:00..2026-10-07T05:22:24…
- report generated_at: 2026-10-07T05:29:11.695567+00:00
- usage rows: 79
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 305982
- output tokens: 118423
- cache-read tokens: 18975744
- cache-write tokens: 0
- hit ratio: 98.4131% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 6 (state=RESOLVED-BREAKS-OMP; population: 4 of 126223 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoStartupFlash-2']; window: 2026-10-07T05:02:48.371000+00:00..2026-10-07T05:22:24.541000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

WHEN/WHERE failed, per the script's own fields: 4 prefix breaks at
`05:02:48.371Z`, `05:04:55.312Z`, `05:10:24.129Z` and `05:22:24.541Z`, all on
`session_id=01a114be-14ad-7324-ba87-c1db776b4611 provider=deepseek-flash
model=deepseek-flash`, at item_index 0 / 45 / 109 / 232 (turn ids
1791349368371 / 1791349495312 / 1791349824129 / 1791350544541). Raw output:
`_main/_cache-report.out`.

## Evidence files

| file | what |
|---|---|
| `_main/_sflash-pair20.out` | the control pair, N=20 per arm (15 107 B) |
| `_main/_sflash-smoke.out` | PRE-fix baseline + `nocure` gross control (8 427 B) |
| `_main/_sflash-opaque.out` | `--opaque` arm, N=8 (4 073 B) |
| `_main/_sflash-show.out` | the owner's ask, N=6 (6 547 B) |
| `_main/_paint-probe3.out`, `_main/_paint-probe3-control.out` | PAINTED vs PAINTED, identical hash (2 256 / 1 763 B) |
| `_main/_paint-probe.out`, `_main/_paint-probe2*.out` | the VOID captures (pre-`wait_for_show`), kept |
| `_main/_pythonnet-show-shadow-test.out` | the instance-shadowing mechanic (349 B) |
| `_main/_flash-live-*.log` | 20 app logs; `_flash-live-0.log` is the mechanism exhibit |
| `_main/_compile-check2.out`, `_main/_cache-report.out` | compile + cache report |
