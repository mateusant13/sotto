# Sotto panel window — visibility audit
**Axis: does the owner ever see the panel when he should not?**
2026-10-06 · read-only audit of `H:/sotto` · author seat `AuditWindowVisibility`

---

## VERDICT (the two or three sentences that matter)

1. **YES — the owner can see the panel with no user action, for up to ~63 ms at every launch.**
   The shell's window is created at its real on-screen geometry (`x=geometry['x']=1528`, `sotto_webview.py:992`), and pywebview calls `form.Show()` on **every** navigation when the window is transparent (`edgechromium.py:346-349`), which is the default here (`transparent=not self.args.opaque`, `sotto_webview.py:995`). The shell's own re-assert does not close it: the 25 ms census measured the window WS_VISIBLE in 18 of 20 launches, longest **63 ms** (`_main/panel-startup-flash-census.log`).

2. **The house census (`window-census.ps1`) is the instrument that is WRONG for this axis.**
   Its declared meaning is *"a handle … is on the screen"* (`window-census.ps1:11-14`) but its predicate is `$p.MainWindowHandle != 0` (`window-census.ps1:60-70`), which is `IsWindowVisible` **with no monitor test**. It therefore goes RED for a window parked at `-32000`/`-10000` that the owner cannot see, and it is **not panel-specific** — today it alarmed on `cmd` (08:28:22Z), `dwm` (08:18:21Z) and `python` (08:16:21Z). An `ALERTA-JANELA` line is **not** admissible as "the Sotto panel was on the owner's screen".

3. **Fact (b)'s identification does not survive a search.** The number `23863834` appears in **no file** under `H:/sotto` (command and output in §1.3). The shell logs on disk that *do* exist show the opposite of the "visible=false in every run" claim: the move-into-place run `_live-nokill2.log` prints `PANEL_VISIBILITY_ON_SCREEN visible=true … show_requested=false`.

---

## 0. What each instrument actually reads (so (a) vs (b) becomes decidable)

| instrument | file:line | predicate |
|---|---|---|
| shell "ON_SCREEN" | `app/webview/sotto_webview.py:442-443` (`window_visible` → `IsWindowVisible`), logged `:1167-1171` | **WS_VISIBLE of `self.hwnd` only** |
| shell "AT_STARTUP" | `sotto_webview.py:1167-1171`-adjacent (`_measure_startup_visibility:1113`, log at `:1143-1145`) | same |
| house census | `I:/!manager/scripts/window-census.ps1:60-70` (`Get-Process … .MainWindowHandle`) | first top-level window with `IsWindowVisible` **AND** `GW_OWNER==0` |
| house probe (the honest one) | `H:/sotto/_main/panel-visible-window-probe.py:20-27` | `mech = WS_VISIBLE`; `owner = mech AND rect intersects a monitor` |

**These two predicates are the SAME predicate** (`.NET MainWindowHandle` is documented as *visible top-level, unowned*; the shell calls `IsWindowVisible` directly). A window parked off-monitor is WS_VISIBLE. The house already wrote this down in its own probe:

> `_main/panel-visible-window-probe.py:27` — *"A window parked at -32000 is WS_VISIBLE and on NO monitor, so a census that reads `IsWindowVisible` alone calls it 'visible' for the entire startup."*

Consequence used throughout: on the **same hwnd at the same instant** the two instruments **cannot** disagree. So a conflict between (a) and (b) is necessarily a conflict of **hwnd**, **pid**, or **instant** — never of predicate.

---

## 1. Reconcile (a) with (b)

### 1.1 (a) — the shell's own logs, reproduced
`_main/_verify-moveinto.log` (hwnd `3809880`, pid `37632`) shows the OFFSCREEN variant's start:
```
sotto: PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=3809880 form.Visible=false opacity=1.0 show_requested=false
sotto: STAGING_LOADED core=yes -> navigating to panel H:\sotto\app\electron\panel.html
```
… and **stops there** — it never reaches `PANEL_VISIBILITY_ON_SCREEN`. That is the *hang* of the `x=OFFSCREEN` creation (§2.1), not a clean run.

The other OFFSCREEN-variant run on disk, `_main/_live-nokill2.log` (hwnd `9512544`, pid `38600`), **did** complete and it prints the opposite of (a):
```
sotto: PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=9512544 form.Visible=false opacity=1.0 show_requested=false
sotto: panel moved into place x=1528 y=66 (created off-screen at -32000)
sotto: PANEL_VISIBILITY_ON_SCREEN visible=true where=startup hwnd=9512544 panel_shown=false show_requested=false
```
`visible=true` with `show_requested=false` and `panel_shown=false`: **the panel was on screen, on its own, nobody asked.** So "`PANEL_VISIBILITY_ON_SCREEN visible=false` in every run" is **false as stated** — the same instrument prints `true` under the same conditions in the move-into-place arm.

### 1.2 (b) — the census line is real, but it is not a panel claim
`I:/!manager/state/progress/window-census.log`:
```
ALERTA-JANELA ts=2026-10-06T08:20:21Z chave=38780:23863834 pid=38780 hwnd=23863834 nome=pythonw
```
Its neighbours in the same file, **today**, are not the panel at all:
```
ALERTA-JANELA ts=2026-10-06T08:28:22Z chave=16984:4594320 pid=16984 hwnd=4594320 nome=cmd
ALERTA-JANELA ts=2026-10-06T08:18:21Z chave=2124:39527852 pid=2124 hwnd=39527852 nome=dwm
ALERTA-JANELA ts=2026-10-06T08:16:21Z chave=27896:72165002 pid=27896 hwnd=72165002 nome=python
```
`cmd`, `dwm` and a bare `python` are not the Sotto panel. The census itself says so by design: *"DOES NOT MEASURE: whose window it is"* (`window-census.ps1:14-19`). So an `ALERTA-JANELA` identifies **a WS_VISIBLE window in some process**, never "the panel is on the owner's screen".

### 1.3 The hwnd in (b) is not in any shell log on disk
```
$ grep -rla "23863834" H:/sotto
$ echo rc=$?
rc=1
```
`rc=1` = zero matches across the whole tree. And the pid in (b) has no shell log either — the only `38780` under `H:/sotto` is a number in an oracle's pid list:
```
$ grep -rl "38780" H:/sotto
H:/sotto\_main\run-cmd-exit-oracle-neg-arm.json
```
So the clause *"23863834 is EXACTLY the hwnd the shell's own log reported as visible=false"* is **not checkable against any artifact**, and the shell logs that do exist (`_live-nokill2.log`) contradict the reading it supports.

### 1.4 My own in-process measurement of the live desktop (no window launched)
`eval` kernel, `EnumWindows` + `IsWindowVisible` + `GetWindowRect`, sampled 2026-10-06 08:26:41Z:
```
--- WinForms / Sotto / Chrome_WidgetWin windows ---
pid=30440(pythonw.exe) hwnd=18224816 vis=False xy=(-10000,66) 380x900 owner=0 cls='WindowsForms10.Window.8.app.0.aec740_r16_ad1' title='Sotto'
```
Exactly **one** Sotto window existed, it was **hidden**, and it sat at **x=-10000** — off every monitor (the displays start at x=0). The census agreed: `JANELAS ts=…08:26:21Z … alarmSet=0`. The current shipped shell never writes `-10000` (grep: only `OFFSCREEN = -32000` at `:431`), so this parked position comes from the running build / a probe, not from the file under audit — recorded as a finding (F5).

### 1.5 Which is wrong, exactly
* **The census is wrong for the question.** Its predicate cannot tell "on the owner's screen" from "WS_VISIBLE off-monitor", and it fires on non-panel processes. Evidence: `window-census.ps1:60-70` predicate; the `cmd`/`dwm`/`python` alarms above; `panel-visible-window-probe.py:27` nailing the defect.
* **(a)'s all-clear is also unsound, but for a different reason.** The shell line is a **single sample taken after settle**; it is blind to a 43–63 ms event. `_live-nokill2.log` is the same instrument printing the opposite. So (a) cannot be used as "the panel never appears".
* **The conflict itself is an artifact**: different pids (`38780` census / `37632` shell log / `30440` live), different instants, same predicate. Not one window measured twice.

---

## 2. The `OFFSCREEN=-32000` cure and `_move_into_place`

### 2.1 The cure is not in the shipped path, and it is broken twice where it was tried
Current `sotto_webview.py` creates the window **at the real geometry**, not off-screen:
```
sotto_webview.py:992-993   x=geometry['x'],  y=geometry['y'],
sotto_webview.py:999       hidden=True,
```
and `_move_into_place` is **dead code** — defined at `:1083`, **no caller**:
```
$ grep -n "_move_into_place(" app/webview/sotto_webview.py
1083:    def _move_into_place(self):
```
The removal is recorded in a note, with a measured reason:
```
sotto_webview.py:1259-1262  # NOTE: `_move_into_place` (the OFFSCREEN cure) was removed 2026-10-06:
                            # creating the window at -32000 broke the panel load, and its move-back
                            # left the panel VISIBLE at startup (measured: PANEL_VISIBILITY_ON_SCREEN
                            # visible=true). Geometry is fixed at creation instead.
```
Both failure modes are in the house's own artifacts:
1. **Creation at -32000 hangs the panel load** — `_verify-moveinto.log` stops at `STAGING_LOADED`; the same is written at `sotto_webview.py:982-990` (*"WebView2 does not complete the stage->panel navigation for a window parked at -32000 … the shell HANGS"*).
2. **The move-back leaves it visible** — `_live-nokill2.log`: `panel moved into place x=1528 y=66` then `PANEL_VISIBILITY_ON_SCREEN visible=true`.

### 2.2 "What if the panel is shown before the move?" — that is not hypothetical; it is the observed failure
The sequence in `_live-nokill2.log` is exactly: window created off-screen → pywebview's navigation `Show()` makes it **WS_VISIBLE while still at -32000** → `_move_into_place` moves a **visible** window onto the owner's screen at `(1528,66)` → `ON_SCREEN visible=true`. The `_move_into_place` docstring claims *"by the time the window is at a position the owner can see, it is hidden"* (`:1095-1105`) — the run refutes it.

### 2.3 Do they hold on every path? No.
* Off-screen-create path: **fails** (hang) — `_verify-moveinto.log`.
* Off-screen-create that survives: **fails** (visible at destination) — `_live-nokill2.log`.
* Shipped path (geometry at creation): the off-screen protection is **absent by construction**; the only net is `_reassert_hidden`, which §3 shows does not close the flash.

### 2.4 Stale/contradictory comment (landmine)
Inside `create_window`, immediately after the "removed" note, the code still says:
```
sotto_webview.py:1013-1014  # transparency must stay on. The startup flash is handled by the OFFSCREEN
                            # creation position below.
```
but the creation **below** is at `geometry['x']` (`:992`), and `:1259` says OFFSCREEN was removed. Two comments in one function assert opposite designs. The docstring at `:1531-1535` also still describes the OFFSCREEN+`_move_into_place` cure as "the cure that CLOSES it", while `_on_loaded` no longer calls it. A future editor reading `:1013` or `:1531` will reintroduce the measured-broken hang.

---

## 3. The `transparent=True` Show/Hide dance at every navigation

### 3.1 The mechanism (library, verbatim)
```
C:/Program Files/Python311/Lib/site-packages/webview/platforms/winforms.py:775   window.events.before_show.set()
winforms.py:777-781  if window.hidden: browser.Opacity = 0; browser.Show(); browser.Hide(); browser.Opacity = 1
edgechromium.py:346-349  def on_navigation_start(...):
                             if self.pywebview_window.transparent:
                                 self.form.Show(); self.form.Activate()
edgechromium.py:102  self.webview.NavigationStarting += self.on_navigation_start   # subscribed in __init__
```
The shell navigates **twice** (stage.html, then panel.html → `sotto_webview.py:1250-1255`), so pywebview runs `form.Show()` **twice** at startup.

### 3.2 The shell's re-assert
`sotto_webview.py:1496` `_on_navigation_start` → sync `_reassert_hidden()` (`:1543`) + POSTED copy (`:1544`); `_reassert_hidden` (`:1546-1555`) does `hide_window(hwnd)` only if visible and no user request. It subscribes at `:1211` inside `_on_core_ready` (which is subscribed at `:1185`).

### 3.3 Does it hold? Measured: NO.
`_main/panel-startup-flash-census.log` (25 ms grid, 20 launches/arm):
```
ARM-SUMMARY live: launched=20 launches_with_mech=18/20 samples=2875 mech_samples=24 longest_mech_ms=63
ARM nocure: longest_mech_ms=68
```
`_main/panel-visible-window-probe.json` (10 ms grid, arm `live`): `launches_with_owner=6`, `longest_owner_ms=43.3` — i.e. the **owner axis** (rect intersects a monitor) also fired for up to 43.3 ms.
Independent instrument `_main/_armE-census-run2.txt`: `CENSUS-PID visible pid=32508 hwnd=82451080 title='Sotto' sample=168` and `ALERTA-JANELA chave=32508:82451080 samples_visible=1` over **302 samples at 100 ms** — a Sotto window truly WS_VISIBLE.

So the sync+posted pair **shortens** the flash but does not close it, exactly as the shell's own docstring admits (`:1524-1527`).

### 3.4 An unverified ordering hole (flag, not proven)
pywebview subscribes `on_webview_ready` at `edgechromium.py:101` and, **inside that handler**, calls `self.load_url(self.pywebview_window.real_url)` (`edgechromium.py:306`). The shell subscribes its own `NavigationStarting` handler only later, in `_on_core_ready` (`:1211`), which is the **second** handler of the same `CoreWebView2InitializationCompleted` event (pywebview subscribed first at `:101`). The shell's comment asserts the first navigation is covered (`:1205-1209`). Whether that is true depends on whether WebView2 raises `NavigationStarting` **synchronously** inside `Navigate()` (then the first Show is unguarded) or on a later posted message (then it is guarded). **I could not verify this without running the app.** It is exactly the kind of path that lets the first `Show()` escape.

---

## 4. Can the app show itself with NO user action? — YES

* The only *intentional* self-show at startup is gated on the flag: `sotto_webview.py:1284-1285` `if self.args.show: self.show_panel('startup')`; `--show` is `:2384`.
* But the **unintended** show is unconditional: `edgechromium.py:348` `self.form.Show()`. With `transparent` on by default (`:995`), the window becomes WS_VISIBLE at its real geometry on every navigation, regardless of `--show` / `–no-hotkey` / nobody pressing Alt+C.
* Proof it reaches the owner's **screen** (not just WS_VISIBLE): `_live-nokill2.log` `PANEL_VISIBILITY_ON_SCREEN visible=true … show_requested=false`; `panel-visible-window-probe.json` `longest_owner_ms=43.3`; `_armE-census-run2.txt` a `title='Sotto'` window caught visible.
* **Autostart: none.** The app does not launch itself at login:
  ```
  $ schtasks /query /fo csv /nh | grep -i "sotto\|webview"     → (empty)
  Startup folder                                                → no Sotto entry
  HKCU\...\Run                                                  → no Sotto entry
  ```
  So the defect needs one launch (double-click `run.cmd`); after that it flashes the panel on its own for ≤63 ms at startup, **and `run.cmd` advertises the opposite** (`run.cmd:6` `start hidden, wait for Alt+C`).

---

## 5. Findings (each cited)

* **F1 — Self-show with no user action (the axis itself).** `edgechromium.py:348` `form.Show()` under `transparent=True`; `sotto_webview.py:995` sets `transparent` by default; measured on screen ≤63 ms (`panel-startup-flash-census.log`) and ≤43.3 ms on the owner axis (`panel-visible-window-probe.json`). Severity: the defect is real and reproducible.
* **F2 — Census predicate does not match its declared meaning.** `I:/!manager/scripts/window-census.ps1:11-14` ("on the screen") vs `:60-70` (`MainWindowHandle`, no monitor test). Fix already exists in-house: `_main/panel-visible-window-probe.py:20-27` (`MonitorFromWindow(MONITOR_DEFAULTTONULL)`).
* **F3 — Census is not panel-specific.** `window-census.log` alarms on `cmd`/`dwm`/`python` today. An `ALERTA-JANELA` cannot be attributed to the panel without a second census.
* **F4 — Stale/contradictory docs in `sotto_webview.py`.** `:1013-1014` says the flash is handled by the OFFSCREEN position "below", while `:992` creates at real geometry and `:1259-1262` says OFFSCREEN was removed; `:1531-1535` still sells the removed cure as "the cure that CLOSES it". Reintroducing it reproduces the measured hang (`_verify-moveinto.log`).
* **F5 — Dead method + unexplained live position.** `_move_into_place` (`:1083`) has no caller (`grep "_move_into_place(" → only the `def`). Separately, the live hidden panel sat at `x=-10000` (§1.4), a sentinel that exists nowhere in the audited file → the running build ≠ the audited file. Whoever owns the running process should say which build it is.
* **F6 — `_on_navigation_start` early-returns on `self.visible`** (`:1549`). Once the owner shows the panel, later navigations are never re-hidden. Intended, but it means "shown once" ⇒ "never auto-hidden again" for the process lifetime — worth an explicit decision.
* **F7 — `run.cmd` promise vs behaviour.** `run.cmd:6` "start hidden"; the shell flashes on screen at startup (F1). The wrapper is otherwise correct (pythonw, `--check-args` preflight, `--log` receipt).

---

## 6. What I could NOT verify (and why)

1. **The exact instant of the 08:20:21Z census** for pid `38780`: dead process, and **no log for pid 38780 exists** under `H:/sotto` (`grep "38780"` → only an oracle pid list). No retro-interrogation is possible.
2. **Whether `23863834` was ever a Sotto hwnd:** the number is absent from every file under `H:/sotto` (§1.3). Not checkable.
3. **WebView2 synchronous-vs-posted `NavigationStarting`** (§3.4): needs a live run; I did not launch the app.
4. **Which build is the running pywebview** (live window at `-10000`): I did not enumerate command lines (no `wmic`; avoided launching tools that could open a window).
5. **Owner-axis at 60 s census cadence:** the census grid is 60 s, too coarse to see a ≤63 ms event; the flash was measured only with the 10/25 ms in-repo probes.

---

## SELF-AUDIT

* **protocolos em falta** — I did not follow a "no-clicking, no-window" instrument protocol for measuring the live desktop *first*: I read ~15 files before measuring the actual screen, and the single in-process `EnumWindows` snapshot (which launched nothing) settled three questions at once. Better order for this class: **measure the live desktop first, then read code to explain it.**
* **verificacao adicional** — A **2-second in-process screen sampler run twice** (before/after a controlled launch) would have turned §3.4 and the per-instant reconciliation from inference into measurement. Cost: it needs one app launch, which the brief forbade me (`do not launch the app`), so I did not run it.
* **checkboxes novas** — (mechanical) **"instrument predicate == instrument name"**: for every visibility instrument, assert the predicate string contains a monitor test whenever the name contains `screen`/`on-screen`/`ALERTA-JANELA`. Command: `grep -n "IsWindowVisible\|MainWindowHandle" <instrument>` and require `MonitorFromWindow` on the same line-block. Input that MUST leave it RED: `window-census.ps1` as it stands today.
* **review por outro subagente** — **sim-com-escopo**: the reconciliation verdict (§1.5) and the census-defect claim (F2/F3) are the parts that should be reviewed by a lane that did **not** see these intermediates — `AuditWindowsLandmines` or `AuditOracles` — because they are the judgement calls, while §2–§4 are mechanical readings of published artifacts.
* **gate-doubt**
  * **verde-de-verdade**: none of my own gates ran vacuously — I ran no build/lint; my one instrument (in-process `EnumWindows`) returned a concrete hwnd+pid+rect. The **house's** census green is NOT vacuous today (`referee` shows `visiveis=14` real windows), but its `ALERTA` verb is mis-scoped (F3).
  * **falta-no-gate**: the census has **no monitor-axis assertion** — a future change that shows the panel on a second monitor, or parks it at `-10000`, crosses it unseen (or falsely). It also never checks the **window title/class**, so it cannot separate the panel from a `cmd`.
  * *gate-melhor*: extend `window-census.ps1` `Get-Janelas` to also read `GetWindowRect` and mark `on_screen = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONULL) != 0`, and emit `ALERTA-JANELA` only when `on_screen`. RED input that must fail the current script: a WS_VISIBLE window parked at `(-32000,-32000)`.
* **confianca** — **alta** on: the shell self-shows with no user action (F1); the OFFSCREEN cure fails on both paths (§2); the census predicate is non-positional (F2). **media** on the exact reconciliation of the 08:20:21Z line, because the process and its log are gone.
* **nao verificado** — see §6 (five items).

---

## GATE-CHANGE REQUEST
The census is a gate (governor `ManagerWindowCensus`, script `I:/!manager/scripts/window-census.ps1`), so the hole found in §1.5 is returned as a prepared change, not a bare finding.

- gate: `I:/!manager/scripts/window-census.ps1` — run it, then read `I:/!manager/state/progress/window-census.log`.
- hole: `Get-Janelas` (`window-census.ps1:60-70`) tests `$p.MainWindowHandle != 0` only — `IsWindowVisible`, no monitor test. Its declared meaning is "on the screen" (`:11-14`). So it goes RED for a WS_VISIBLE window parked at `-32000`/`-10000` that the owner cannot see, and it cannot separate the panel from a `cmd`/`dwm`.
- change (merge-ready shape): in `Get-Janelas`, also read `GetWindowRect($hwnd)` and set `on_screen = [user32]::MonitorFromWindow($hwnd, 0) -ne 0`; emit `ALERTA-JANELA` only when `on_screen`. The predicate already exists in-repo at `H:/sotto/_main/panel-visible-window-probe.py:20-27`.
- non-vacuity control (input that MUST stay RED on the current script and go GREEN after the change): a WS_VISIBLE window whose rect is fully at `x=-32000` — today it alarms (false positive); with the monitor test it must not, while a WS_VISIBLE window at `x>=0` must still alarm.

## CACHE/PRICE
`bash I:/!manager/scripts/cache-task-report.sh AuditWindowVisibility` (rc=0), stdout verbatim:
```
- task/agent: AuditWindowVisibility
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditWindowVisibility.jsonl
- cache: read=4611968 write=0 hit=95.9356% (cache-read / input+cache-read); universe: 41 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: break_items=1 WHEN=2026-10-06T08:24:37.255Z | break_items=1 WHEN=2026-10-06T08:24:38.673Z | break_items=3 WHEN=2026-10-06T08:24:40.517Z | break_items=2 WHEN=2026-10-06T08:26:14.997Z | break_items=2 WHEN=2026-10-06T08:31:35.637Z (state=RESOLVED-BREAKS-OMP)
- where-failed: session_id=01a11050-0fed-77ab-bff0-be659e29f4b9 provider=space-bunny-free item_index=0; provider=ling-3.1-flash-free item_index=0; provider=deepseek-flash item_index=0; provider=deepseek-flash item_index=62; provider=deepseek-flash item_index=158
- report generated_at: 2026-10-06T08:32:30.243478+00:00
- usage rows: 41
- model + route: opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 195389
- output tokens: 52847
- cache-read tokens: 4611968
- cache-write tokens: 0
- hit ratio: 95.9356% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; 5 of 113576 OMP prefix-ledger rows attributable to keys ['01a10f72-…', 'AuditWindowVisibility'])
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
Key fields the owner asked for:
- `cache: 4611968` read, `0` write, `95.9356%` hit — source: the session JSONL above; instrument `cache-task-report.sh`.
- `price: $0.00000000 USD` — provider-reported; per-model rates `UNKNOWN` (not in source).
- `when-failed: 5` breaks, first `2026-10-06T08:24:37.255Z`, last `2026-10-06T08:31:35.637Z`.
- `where-failed: session 01a11050-0fed-77ab-bff0-be659e29f4b9`, item_index 0/0/0/62/158, providers space-bunny-free/ling-3.1-flash-free/deepseek-flash.
- `source:` the JSONL path printed above.

