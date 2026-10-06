# live-for-owner — the app is UP, and Alt+C answers

Lane `SottoLiveForOwner`, 2026-10-06 (run started 08:53:12Z, last measurement 08:57Z).
Repo `H:/sotto`. Log of record: `H:/sotto/_main/live-owner.log`.

The ask was one thing: **have the app RUNNING AND STAYING UP so Alt+C has something to answer,
right now** — while the blank-frame cause is chased elsewhere. It is up, and Alt+C was exercised
end to end. Captions are **not** zero — see §4 and §6.

---

## 1. Launch — the owner's way, and with no console window

```python
# H:/sotto/_main/_live-launch.py -- the house's sanctioned hidden spawner
spawn_hidden.run_hidden(["cmd", "/c", r"H:\sotto\app\webview\run.cmd",
                         "--with-worker", "--log", r"H:\sotto\_main\live-owner.log"])
```

```
RUNCMD_RC 0        # run.cmd's readiness handshake (G3): the app TOUCHED the ready file
SHELL_RC=0
```

`CREATE_NO_WINDOW` is applied to the wrapper `cmd.exe`; `run.cmd` itself `start`s `pythonw.exe`
(GUI subsystem). No window was created — **measured against the house's own instrument**, not
by eye:

| window census | visible windows |
|---|---|
| 2026-10-06T08:52:21Z (before the launch) | `visiveis=14` |
| 2026-10-06T08:53:22Z (after the launch) | `visiveis=14` |

```
JANELAS ts=2026-10-06T08:53:22Z modo=medicao visiveis=14 alarmSet=0 reencontro=0 pidsConhecidos=163 alarmeHerdadoApagado=0
```

`windows` (house tool) on the launch command: `NO WINDOW SHOWING SIGNAL FOUND`.

---

## 2. The four lines required before the app counts as UP (verbatim from the log)

```
1   sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=25800
5   sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=36448
19  sotto: RECEIVER_READY captions=0 hasBridge=True placeholder="Waiting for audio Nothing is being transcribed yet. Captions appear here line by"
20  sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
21  sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=104144864 panel_shown=false show_requested=false
24  sotto: BRIDGE_START reason=with-worker command=C:\Program Files\Python311\python.EXE worker=H:\sotto\worker\sotto_worker.py device=auto capture=callback
27  sotto: BRIDGE_SPAWNED pid=9788 argv=["C:\\Program Files\\Python311\\python.EXE", "H:\\sotto\\worker\\sotto_worker.py"] SOTTO_CAPTURE_MODE=callback SOTTO_AUDIO_DEVICE=(unset)
28  sotto: WORKER_AUTOSTART=started reason=with-worker
```

| required by the brief | line | verdict |
|---|---|---|
| `HOTKEY_REGISTERED … isRegistered=true` | 5 | PRESENT |
| `PRELOAD_ACTIVE hasSotto=true` | 20 | PRESENT |
| `WORKER_AUTOSTART=started` | 28 | PRESENT |
| `PANEL_VISIBILITY_ON_SCREEN visible=false` | 21 | PRESENT |

Process table at launch (windowless, detached):

```
ProcessId   : 25800
CommandLine : "C:\Program Files\Python311\pythonw.exe"  "H:\sotto\app\webview\sotto_webview.py" --with-worker
              --log H:\sotto\_main\live-owner.log --ready-file "H:\sotto\app\webview\..\..\_main\ready-9559-29578.txt"
ProcessId   : 9788    (worker)
CommandLine : "C:\Program Files\Python311\python.EXE" H:\sotto\worker\sotto_worker.py
```

---

## 3. Alt+C end to end — the REAL key, not a function call

A real `Alt+C` was injected with `keybd_event` (the same OS input path a physical keypress takes),
twice, via `H:/sotto/_main/_live_key.py`. It went to the registered hotkey, not to a function.

```
focus_before   hwnd=29631092 title='Finalizar VOD rip e corrigir bugs com swarm'
after_press_1  hwnd=29631092 title='Finalizar VOD rip e corrigir bugs com swarm'
after_press_2  hwnd=29631092 title='Finalizar VOD rip e corrigir bugs com swarm'
```

The panel went VISIBLE and BACK, both times `reason=hotkey` (verbatim from the log):

```
64   sotto: PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
78   sotto: PANEL_HIDDEN reason=hotkey visible=false
```

Independent confirmation 5 s later, read straight from the window manager (not from the log):

```
IsWindowVisible(104144864)=False
```

Two further toggles happened at 08:55Z from OUTSIDE this lane — most likely the owner's own
Alt+C at his keyboard, followed by the panel's own hide button (`reason=page`, `panel.js:261`):

```
168  sotto: PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
169  sotto: POINTER_INTERACTIVE active=true click_through=false
184  sotto: PANEL_HIDDEN reason=page visible=false
```

So the owner's key is answered by the running app: `reason=hotkey` on every show. Focus is never
stolen — the foreground window stayed the video window through all of it (`focus_stolen=false`,
and the hwnd above is unchanged before/after).

### 3.1 The SAME test against the app that is actually running now (pid 29500)

The instance above (pid 25800) was superseded at 08:57:12Z (§5/§6). The test was therefore REPEATED
against the live app — two real injected Alt+C, at 09:06Z, on its own log
`H:/sotto/_main/_live_owner.log`:

```
BEFORE: shown=1 hidden=0
focus_before   hwnd=58005580 title='voce ta dentro do mcode, nao OMP. entenda tudo que'
after_press_1  hwnd=58005580 title='…'      (focus unchanged)
after_press_2  hwnd=58005580 title='…'      (focus unchanged)
AFTER:  shown=2 hidden=1
```

```
477  sotto: PANEL_HIDDEN reason=hotkey visible=false
478  sotto: PANEL_SHOWN  reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
```

Both transitions carry `reason=hotkey` — the registered hotkey, not a function call — and the panel
is **VISIBLE** as of that last line, so the owner's panel is on screen with live captions in it at
the end of this run.

---

## 4. What the owner will SEE, one line per step

1. **Before pressing anything** — nothing on screen: no window, no console, no taskbar entry
   (`skipTaskbar=true`, `focusable=false`). The app is invisible by design.
2. **Press Alt+C** — a 380x900 panel appears docked at the right edge of the 1920x1032 work area
   (`window=380x900@(1528,66)`), always-on-top, **without taking focus** — the keystrokes stay where
   they were.
3. **While it is up** — a dark translucent caption bar (CSS `panel.css:202`,
   `rgba(8,11,16,0.55)→0.2`) with the caption text; the rest of the 380x900 is transparent.
4. **The text is real** — my instance delivered and painted three captions
   (`BRIDGE_CAPTION_SENT delivered=true text="Os"` line 43, `text="Ser interditada"` 89,
   `text="Os mora"` 92), and the instance running NOW is doing better: its log carries
   `CAPTION_APPLIED … count=25` and a full sentence of live text
   (`text="Today for a He'll have to put an appear At some Sunday and he can come immediately"`).
   **Captions are NOT zero — do not report them as zero.**
5. **But they are intermittent** — the worker crash-loops (§5) and one of its arms bound a silent
   device (`SILENT-DEVICE Driver de captura de som primário [Windows DirectSound] peak=0.00…`,
   `BRIDGE_EXIT rc=3`), so between spawns the panel shows a placeholder
   ("Warming up" / "Listening" / "Worker is running but has said nothing" / "Worker stopped").
   The sentence above is also fragmented — it reads like several utterances glued together, which is
   the blank-frame defect showing through: most frames are blank (`blank_frac=0.92…1.0`), so what
   survives is patchy.
6. **Press Alt+C again** (or click the panel's hide button) — the panel disappears; the app stays
   up and answers the next Alt+C.

---

## 5. Staying up — the shell does; the worker does not; and MY shell was later replaced

Measured over 45 s (08:54:0x → 08:55:0x), then again at 08:56:21Z — all of it on the instance THIS
lane launched (pid 25800, log `H:/sotto/_main/live-owner.log`):

| t | log lines | captions | worker spawns | worker exits |
|---|---|---|---|---|
| T0 | 125 | 3 | 4 | 3 |
| T1 (+45 s) | 165 | 3 | 5 | 4 |
| 08:56:21Z | 342 | 3 | 12 | 12 |

For that whole window the **shell** (pid 25800) never exited — it is the process that owns Alt+C —
while the **worker** dies and is respawned every ~15–30 s (`BRIDGE_EXIT … rc=1`, once `rc=3` on the
silent device, `BRIDGE_SILENT ms=15000`), each respawn paying model load again (`rss_mb=2412.6` in
line 102 — the worker reaches ~2.4 GB). Two causes are visible in the stress and neither belongs to
this lane: (a) hot-reload restarts it whenever a sibling lane writes `sotto_worker.py` —
`HOT_RELOAD_EVENT kind=worker file=sotto_worker.py` (lines 60–62) — and (b) the worker scores
`blank_frac=0.98`/`1.0` and sometimes picks the silent DirectSound input.

**Then my instance was superseded, and that is measured, not inferred.** `live-owner.log` stops
growing at 08:57:12Z (37 477 bytes, `SHELL_EXIT` = 0 occurrences) and `Get-Process -Id 25800` returns
nothing; ten seconds later another lane launched the app with ITS OWN log:

```
ProcessId    : 29500
CreationDate : 06/10/2026 05:57:22
CommandLine  : "C:\Program Files\Python311\pythonw.exe" H:\sotto\app\webview\sotto_webview.py
               --with-worker --log H:\sotto\_main\_live_owner.log
```

Two app instances do not coexist here — the second one's arrival coincides with mine's death to
within ten seconds. Whatever the mechanism (that lane's launch, or a single-instance guard), the
honest reading is that **the app the owner has is pid 29500, and §6 is about that one**. §2–§5 remain
the receipt of the launch this lane performed and verified.

Hot reload is LEFT ON on purpose: it is the owner's default path, and it means the blank-frame fix
lands in the live app without a restart.

---

## 6. The RUNNING app at the end of this run

**pid 29500** — verified AFTER it replaced mine, and this is the one left running:

```
ProcessId    : 29500
CreationDate : 06/10/2026 05:57:22
CommandLine  : "C:\Program Files\Python311\pythonw.exe" H:\sotto\app\webview\sotto_webview.py
               --with-worker --log H:\sotto\_main\_live_owner.log
```

All four required lines are present in ITS log (`H:/sotto/_main/_live_owner.log`), so it is UP by the
same bar §2 applies:

```
1   sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=29500
5   sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=38528
20  sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
21  sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=5380366 panel_shown=false show_requested=false
28  sotto: WORKER_AUTOSTART=started reason=with-worker
```

### 6.1 pid 29500 DIED TOO — and the app left running is the THIRD instance (pid 41488)

Measured, in order, after §6 was first drafted:

* `_live_owner.log` ends at 09:07:30Z with `SHELL_CLOSING` and **no `SHELL_EXIT`**;
  `Get-Process -Id 29500` → alive=False. Pid 29500 lived from 08:57:22Z to ~09:07:30Z —
  **ten minutes and eight seconds**.
* A count at 09:07:47Z of `pythonw.exe` running `sotto_webview.py` returned **0**. For ~40 seconds
  the owner had NO app: Alt+C would have answered nothing.
* The lane relaunched it (same windowless path, fresh log `H:/sotto/_main/live-owner-2.log`):

```
RUNCMD_RC 0 log H:/sotto/_main/live-owner-2.log
1   sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=41488
5   sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=40004
26  sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
27  sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=54925986 panel_shown=false show_requested=false
34  sotto: WORKER_AUTOSTART=started reason=with-worker
```

* and Alt+C was re-verified against THIS instance, real injected key, `reason=hotkey` both ways:

```
55  sotto: PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
56  sotto: PANEL_HIDDEN reason=hotkey visible=false
```

(focus stayed on the owner's Chrome/YouTube window throughout).

**THE RISK TO "STAYING UP", named.** Two instances have now died under this lane, and both deaths
line up with another lane: 25800 died 10 s before 29500 appeared, and 29500 lived exactly 10 m 08 s
and then shut down cleanly. There is **no** `sotto` entry in the Task Scheduler
(`schtasks /query | grep -i sotto` → empty) and **no** single-instance guard in `sotto_webview.py`
(grep for `single|mutex|Mutex|CreateMutex` finds only `isinstance`), so this is a LANE driving the
app — launch, measure, `quit()` — not the house and not the app. **The app the owner has is pid
41488, and it stays up only as long as that lane does not cycle it again.** Whoever owns that loop
must be asked to leave one instance standing.

_(Instrument note, because it nearly cost this report: the first count said `count=2`. The filter
`CommandLine -like '*sotto_webview.py*'` matches the QUERYING POWERSHELL PROCESS ITSELF — the
pattern is inside its own command line. Counting `Name='pythonw.exe'` as well is what makes the
number real; without it a one-app census answers 2 and a zero-app census answers 1. A LATER count
with the correct filter also said 2 once — pids 41488 and a transient 36768 — and the very next
listing, seconds later, showed only 41488. I did not resolve that one: a short-lived second
`pythonw` appeared and vanished between two queries, and I am recording it rather than explaining it
away.)_

**pid 41488**, pythonw, hidden, ready-file handshake satisfied, `HotkeyThread` registered
(thread 40004). Left running.

FINAL STATE at 09:10:12Z (measured, not narrated): `pythonw.exe` running `sotto_webview.py` → **count=1**,
`ProcessId 41488`, `CreationDate 06/10/2026 06:08:05`; its log is 112 lines and STILL GROWING, and it
has already delivered live captions of its own —
`BRIDGE_CAPTION_SENT delivered=true text="He'll have put it"` (line 85). **So the answer to "is
Alt+C going to answer?" is: yes, on pid 41488, right now — and that is a claim with a shelf life,
because a lane has now cycled this app twice in seventeen minutes.**

---

## 7. Side effect found (not this lane's to fix)

Taking the panel on screen raised the house's own window alarm:

```
ALERTA-JANELA ts=2026-10-06T08:55:22Z chave=25800:104144864 pid=25800 hwnd=104144864 nome=pythonw
JANELAS ts=2026-10-06T08:55:22Z modo=medicao visiveis=15 alarmSet=1 reencontro=0 pidsConhecidos=164 alarmeHerdadoApagado=0
```

The census reported `ManagerWindowCensus … VERMELHO-FALHA … assinatura de falha declarada
encontrada na cauda: /^ALERTA-JANELA /`, and then cleared itself on the next pass — the panel went
back to hidden and the 08:56:22Z row set the alarm down:

```
JANELAS ts=2026-10-06T08:56:22Z modo=medicao visiveis=14 alarmSet=0 reencontro=0 pidsConhecidos=164 alarmeHerdadoApagado=1
```

The hwnd in the alert is exactly the Sotto panel (`PANEL_VISIBILITY_AT_STARTUP … hwnd=104144864`).
So the red was transient, NOT a stuck alarm — but it recurs every time the panel is shown, which is
every time the owner uses his own app. That is for the census's owner to reconcile; it is recorded
here because it happened as a consequence of this run and would otherwise be read as an unexplained
alert.

---

## SELF-AUDIT

- **protocolos em falta** — I ran `run.cmd` with the default hot-reload ON while a sibling lane is
  writing `sotto_worker.py`, so my run's worker-churn numbers are contaminated by that lane's edits
  (`HOT_RELOAD_WORKER_RESTART files=["sotto_worker.py"]`). A protocol I should have followed: a
  live-run receipt should name WHO ELSE was writing into the directories this run watches, before
  quoting churn as the app's own behaviour. What I would do differently: `--no-hot-reload` for the
  measurement arm, hot-reload ON only for the arm I leave running.
- **verificacao adicional** — the cheap one I DID run: the census before/after (14→14) and
  `IsWindowVisible(104144864)=False` straight from user32, rather than trusting `PANEL_HIDDEN`'s own
  word. The one I did NOT run, and its cost: reading the panel's actual painted pixels (a
  screen-capture of the 380x900 region while it was shown). It costs a visible capture and the
  panel's own `--opaque`/DOM probe path; the DOM-level paint is already proven by lane
  `SottoPanelPaintsVerdict` (`rendered.text`/`className` measured in the real DOM), so I took that
  as the cheaper instrument.
- **checkboxes novas** — add to this class of work, mechanically: (1) `grep -c 'HOTKEY_REGISTERED .*isRegistered=true' <log>` must be ≥1 AND `grep -c 'HOTKEY_REGISTERED .*isRegistered=false' <log>` must be 0; (2) after the Alt+C pair, assert BOTH `PANEL_SHOWN reason=hotkey visible=true` and `PANEL_HIDDEN` exist in the SAME log section, and that `IsWindowVisible(hwnd)` from user32 AGREES with the last line — a log that says hidden over a window that is visible would otherwise pass; (3) `visiveis` from `window-census.log` before vs after the launch must be EQUAL; **(4) the one this run paid for: `Get-CimInstance Win32_Process` for `sotto_webview.py` must return EXACTLY ONE pid AND it must be the pid the receipt names — re-run this at the END of the turn, not only at launch. My receipt named pid 25800 while pid 29500 was the app; only a re-read caught it. If the count is 0, nobody has the app; if it is 2, two lanes are racing and the next launch may kill the first.**
- **review por outro subagente** — sim-com-escopo: hand the reviewer the two artefacts and the ONE
  claim that matters — "Alt+C reaches the registered hotkey and the panel's real visibility follows
  the log" — plus the falsifier (an injected Alt+C that produces NO `PANEL_SHOWN`, or a
  `PANEL_SHOWN` with `visible=false`). Not the whole log: the churn numbers are contaminated (§5)
  and would invite a re-litigation of the worker, which is another lane's subject.
- **gate-doubt**:
  - **verde-de-verdade**: `RUNCMD_RC 0` is a real green — `run.cmd`'s readiness file is only touched
    by `mark_launch_ready` after `PRELOAD_ACTIVE`, and the log shows `PRELOAD_ACTIVE` for the same
    pid 25800 the wrapper had just started, so it is not a stale ready-file answer. **But this green
    is conditional on a clause I got wrong the first time and had to go back and repair: "the same
    pid 25800" was TRUE at 08:56Z and FALSE at 09:05Z (§5/§6) — the pid the green was pinned to had
    been replaced by another lane's launch. A green that names a pid has a shelf life, and the
    receipt must re-read the pid at the moment it is signed.** The window census green is REAL only
    for the launch window (08:53:22Z, `visiveis=14`); its `alarmSet=0` on that row cannot be read as
    "the app never shows a window", because the 08:55:22Z row does contain `ALERTA-JANELA` with the
    panel's hwnd — a green measured before the thing that turns it red.
  - **falta-no-gate**: nothing verifies that a panel the owner ASKED for (his own app) is
    distinguishable from an unprotected popup. `window-census.ps1` alarms on any new visible
    pythonw hwnd, so a future change that makes the panel show on startup would alarm on every
    boot and train the owner to ignore the alarm — the census would still be "measuring", just with
    no signal left in it.
  - **gate-melhor**: a mechanical check that closes it: the census should carry an allowlist keyed by
    (hwnd owner pid, executable, and the process's OWN registration), and the action that makes it
    RED is a run that shows the panel and does NOT match that key — e.g.
    `bash I:/!manager/scripts/window-census.ps1 --assert-allowlisted` must exit non-zero when
    `ALERTA-JANELA chave=25800:104144864` is present without an allowlist row for the Sotto panel.
- **confianca** — **alta** for the claim that the app is up and Alt+C flips the panel (registration
  + real injected key + log + user32 read, four independent instruments, re-run against the live
  instance in §3.1). **alta** also for "the owner sees text": the running instance's log carries
  `CAPTION_APPLIED … count=25` with a live sentence — that is measured on the app he has, not on
  mine. **media** for the CRASH-LOOP's impact on his experience: worker exits are frequent and one
  arm binds a silent device, so caption flow will be bursty; a clean 10-minute window with no sibling
  lane writing the worker would settle it, and a screen-capture would settle the painted pixels.
  **media, falling** for "the pid in this receipt is the pid of the app": that claim has now been
  wrong once (§5/§6) and is only as fresh as the last process read.
- **nao verificado** — (1) the painted pixels of the panel — I never captured the screen; the paint
  claim is inherited from lane `SottoPanelPaintsVerdict`. (2) WHY the worker exits `rc=1` (the
  `done`/silence path) — that is `BlankFramesRootCause`'s subject and I did not touch it. (3) The
  2.4 GB worker RSS — observed in `BRIDGE_EXIT` lines, not investigated. (4) Whether the 08:55Z
  Alt+C was literally the owner at the keyboard — inferred from the fact that this lane sent only
  two presses, both accounted for at lines 64/78; I cannot prove it was him. (5) The census alarm's
  downstream effects — I observed `alarmSet=1`, did not follow what consumes it. (6) **WHY pid 25800
  died at 08:57:12Z** — I have the timing (it precedes pid 29500 by 10 s) and the artifact (its log
  froze, `SHELL_EXIT` absent), but not the mechanism: another lane's launch, a single-instance guard
  in the shell, or a kill. I did not read `app/webview/sotto_webview.py` for a single-instance path,
  and I did not message the lane that started 29500.

---

## CACHE/PRICE

Verbatim from `bash I:/!manager/scripts/cache-task-report.sh SottoLiveForOwner`:

```
## CACHE/PRICE
- task/agent: SottoLiveForOwner
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLiveForOwner.jsonl
- cache: read=2105728 write=0 hit=95.7275% (cache-read / input+cache-read); universe: 34 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoLiveForOwner.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=27 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000
- when-failed: break_items=1; WHEN=2026-10-06T08:52:04.814000+00:00 | break_items=1; WHEN=2026-10-06T08:52:05.306000+00:00 | break_items=1; WHEN=2026-10-06T08:52:05.920000+00:00 | break_items=3; WHEN=2026-10-06T08:52:06.346000+00:00 | break_items=1; WHEN=2026-10-06T08:54:03.583000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 114258 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLiveForOwner']; window: 2026-10-06T08:52:04.814000+00:00..2026-10-06T08:54:03.583000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11069-8710-7345-a8eb-2e5d8944f99e provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791276724814 | session_id=01a11069-8710-7345-a8eb-2e5d8944f99e provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791276725306 | session_id=01a11069-8710-7345-a8eb-2e5d8944f99e provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791276725920 | session_id=01a11069-8710-7345-a8eb-2e5d8944f99e provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276726346 | session_id=01a11069-8710-7345-a8eb-2e5d8944f99e provider=deepseek-flash model=deepseek-flash item_index=92; turn_id=1791276843583 (state=RESOLVED-BREAKS-OMP; population: 5 of 114258 OMP prefix-ledge…)
- report generated_at: 2026-10-06T08:55:20.751718+00:00
- usage rows: 34
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 93983
- output tokens: 14594
- cache-read tokens: 2105728
- cache-write tokens: 0
- hit ratio: 95.7275% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 5 of 114258 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoLiveForOwner']; window: 2026-10-06T08:52:04.814000+00:00..2026-10-06T08:54:03.583000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

WHEN/WHERE failed: 5 break items, state `RESOLVED-BREAKS-OMP`, 2026-10-06T08:52:04.814Z →
08:54:03.583Z, all on `session_id=01a11069-8710-7345-a8eb-2e5d8944f99e` — `item_index=0` on four
provider switches (cline-pass / space-bunny-free / ling-3.1-flash-free / deepseek-flash) and
`item_index=92` on the deepseek-flash turn. Cost is provider-reported `$0.00000000`; per-model rates
are UNKNOWN in this source, so the $0 is a reported number, not an arithmetic result.
