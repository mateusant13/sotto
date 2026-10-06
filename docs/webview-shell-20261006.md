# Sotto — the WebView2 shell (replaces Electron)

status: done

**Date:** 2026-10-06
**Owner ask:** *"pode mudar o electron pra outra coisa melhor se tu conseguir"* → *"e tu ja trocou pra webview?"*
**Answer:** yes. `app/webview/sotto_webview.py` is a WebView2 (pywebview 6.2.1 +
pythonnet) host that loads the **existing, unmodified** panel from
`app/electron/panel.html`, and `app/electron/` is untouched and still runs.

| | |
|---|---|
| Shell | `H:\sotto\app\webview\sotto_webview.py` |
| Launcher | `H:\sotto\app\webview\run.cmd` |
| Staging page | `H:\sotto\app\webview\stage.html` (empty; buys the preload ordering) |
| Receipt | this file |
| Logs | `H:\sotto\_main\webview-*.log`, `webview-*.stdout.txt` |

---

## 1. The app RUNS — window created at the docked geometry

```
$ py -3 sotto_webview.py --dump-dom ; echo rc=$?
sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=26028
sotto: panel window created frame=false transparent=true alwaysOnTop=true skipTaskbar=true resizable=false show=false focusable=false engine=WebView2/pywebview
sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
sotto: primary display bounds={"x": 0, "y": 0, "width": 1920, "height": 1080} workArea={"x": 0, "y": 0, "width": 1920, "height": 1032} scaleFactor=1.0
sotto: panel setAlwaysOnTop(floating) ok style=WS_EX_LAYERED|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_TRANSPARENT
sotto: panel setFocusable(false) ok (WS_EX_NOACTIVATE)
sotto: panel setIgnoreMouseEvents(true, forward) ok (WS_EX_TRANSPARENT)
sotto: panel setVisibleOnAllWorkspaces SKIPPED - no WebView2/WinForms equivalent exists
sotto: panel client area forced to 380x900 (window 380x900)
sotto: PRELOAD_INSTALLED where=initialization-completed status=RanToCompletion
sotto: STAGING_LOADED core=yes -> navigating to panel H:\sotto\app\electron\panel.html
sotto: RECEIVER_READY captions=0 hasBridge=True placeholder="Waiting for audio Nothing is being transcribed yet. Captions appear here line by"
sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
...
sotto: SHELL_EXIT rc=0 reason=dump-dom
rc=0
```

`panel geometry:` is **byte-identical** to the Electron arm's
(`_main/electron-dump-fresh.log:4`): `docked=right work=1920x1032@(0,0)
window=380x900@(1528,66) margin=12`. It is a port of `main.js::dockRight`
(`sotto_webview.py:dock_right`), a pure function, and it also clamps correctly
on a degenerate work area (measured: `work=0x0@(0,0)` → `window=1x1@(-1,-1)`,
the same result the JS clamp produces).

`RECEIVER_READY … hasBridge=True` is the page→host channel proven end to end:
that line exists only because `panel.js:205 bridge.ready({...})` reached the host.

---

## 2. The SAME rect probe produces the SAME layout numbers

Both arms ran the **same probe text** (`main.js:273-290`, copied verbatim into
`sotto_webview.py:DUMP_DOM_PROBE`) against the **same files**, minutes apart.

> **The Electron arm's numbers had to be re-measured.** The receipts in
> `_main/dump-real.log` / `_main/rect-probe.log` are from 02:13–02:14, but
> `app/electron/panel.css` is from **02:19:40** — the CSS changed *after* they
> were taken, so `#panel` had moved from `[10,10,360,880]` to `[0,0,380,900]`.
> Comparing against them would have compared two different pages. Both logs
> below are fresh.

**Electron arm** (`_main/electron-dump-fresh.log`):

```
sotto: electron version=40.10.2 chrome=144.0.7559.236 node=24.15.0
sotto: panel window created frame=false transparent=true alwaysOnTop=true skipTaskbar=true resizable=false show=false focusable=false
sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide
sotto: RECEIVER_READY captions=0 placeholder="Waiting for audio Nothing is being transcribed yet. Captions"
sotto: DOMDUMP {"viewport":[380,900],"zoom":1,"body":[380,900],"sheets":1,"els":{"#panel":{"rect":[0,0,380,900],"color":"rgb(232, 238, 246)","display":"grid","position":"absolute","visibility":"visible","opacity":"1"},".panel__header":{"rect":[17,17,346,35],...
```

**WebView2 arm** (`_main/webview-dump.stdout.txt`):

```
sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,66) margin=12
sotto: DOMDUMP {"body":[380,900],"els":{"#caption-list":{"color":"rgb(232, 238, 246)","display":"none","opacity":"1","position":"static","rect":[0,0,0,0],"visibility":"visible"},"#clear-button":{"color":"rgb(154, 168, 189)","display":"grid","opacity":"1","position":"static","rect":[301,20,28,28],"visibility":"visible"},"#panel":{"color":"rgb(232, 238, 246)","display":"grid","opacity":"1","position":"absolute","rect":[0,0,380,900],"visibility":"visible"},...
```

**Mechanical diff — 14 fields, 0 mismatches:**

```
$ py -3  (parse both DOMDUMP lines, compare viewport/zoom/body/sheets + every
          element's rect/color/display/position/visibility/opacity)
fields compared: 14 | MISMATCHES: 0
IDENTICAL
```

Every rect, every computed colour, `viewport [380,900]`, `zoom 1`,
`body [380,900]`, `sheets 1` matches. The same HTML/CSS renders the same layout
under WebView2 as under Electron.

---

## 3. Alt+C REGISTERS and toggles

`--selftest` posts a **real `WM_HOTKEY`** to the registering thread's own queue
— the same queue the OS writes to — so the delivery path under test is the
real one, not a direct call to the toggle function.

```
$ py -3 sotto_webview.py --selftest ; echo rc=$?
sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=3596
...
sotto: SELFTEST hotkey_registered=true accelerator=Alt+C
sotto: PANEL_HIDDEN reason=selftest-baseline visible=false
sotto: SELFTEST state=hidden visible=false
sotto: PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
sotto: SELFTEST state=after-hotkey-1 visible=true press_delivered=true presses=1
sotto: PANEL_HIDDEN reason=hotkey visible=false
sotto: SELFTEST state=after-hotkey-2 visible=false presses=2
sotto: SELFTEST focus_before=856942 focus_after=856942 focus_stolen=false
sotto: SELFTEST rc=0
sotto: SHELL_EXIT rc=0 reason=selftest
rc=0
```

* **The two states:** `visible=false` → `visible=true` → `visible=false`, with
  `presses=1` then `presses=2` counted by the hotkey thread itself.
* **`RegisterHotKey` returned success** — the line is only printed after a
  non-zero return. A failure prints `HOTKEY_REGISTER_FAILED … winerror=1409`,
  which is what a second concurrent instance produces (observed, and it is the
  correct refusal: two shells must not both own Alt+C).
* **No focus stolen:** the foreground HWND is `856942` before and after both
  toggles. The mechanism is `WS_EX_NOACTIVATE` plus `ShowWindow(SW_SHOWNOACTIVATE)`.
  The hotkey thread never calls `Activate`/`SetForegroundWindow`.

---

## 4. MEMORY — measured, and it does NOT favour the WebView2 arm

Measured with `GetProcessMemoryInfo` (working set), not estimated.

**WebView2 arm**, panel shown (`--show --memory --memory-wait 7`):

| process | RSS |
|---|---|
| `python.exe` (the host) | **95.7 MB** |
| `msedgewebview2.exe` ×6 (depths 1–2) | **320.6 MB** |
| **total** | **416.3 MB** |

**Electron arm**, same instrument, same host, whole tree (pid-delta census
after launch: 91.6 + 47.9 + 73.9 + 98.8):

| | |
|---|---|
| **total** | **312.2 MB** |

**So: 416.3 MB against 312.2 MB — the WebView2 shell costs about 33% MORE
memory, not less.** The 213.9 MB quoted for Electron was a single
`electron.exe`; its whole tree is 312.2 MB, and even against that flattering
one-process number the WebView2 host's tree is larger. The Python host alone
(95.7 MB) is the only piece that is smaller, and it is smaller because it is
the part that is not a browser.

An earlier version of this measurement walked only *direct* children and read
210.9 MB. That was wrong and it flattered this shell; the census now walks
descendants (`sotto_webview.py:child_processes`) and the honest number is above.

---

## The panel needed no edit

`app/electron/panel.html`, `panel.css`, `panel.js`, `preload.js`, `main.js`,
`worker-bridge.js` are **unmodified**. The shell only provides what
`preload.js` exposed, through WebView2's equivalents:

| preload.js | WebView2 equivalent here |
|---|---|
| `contextBridge.exposeInMainWorld` | `CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync` |
| `ipcRenderer.on` | `ExecuteScriptAsync("window.__sotto_emit(...)")` |
| `ipcRenderer.send` | `chrome.webview.postMessage` → pywebview's WebMessage pump → `SottoHost.dispatch` |
| `ipcRenderer.invoke` | same channel + a reply id (a real resolved Promise) |

All 14 methods are present and typed, measured by the probe:
`["pushCaption","setStatus","onCaption","onStatus","onGeometry","hide","toggle","quit","setPointerInteractive","getInfo","captionApplied","statusApplied","ready","clearApplied"]`,
plus `HOTKEY: 'Alt+C'` and `platform: 'win32'`.

### The three things that were hard, and what they cost

1. **Preload ordering.** pywebview loads the window URL from its own
   `CoreWebView2InitializationCompleted` handler, subscribed *before* the
   host's, so a preload registered from the host's handler lands after the
   navigation is already in flight. Measured: the first panel parse came up
   with `hasSotto=false` and panel.js painted its "Preload bridge missing"
   branch. Fixed by opening `stage.html` first, registering, then navigating —
   so the panel's **first** parse is correct, with no repair reload.
2. **The client area.** pywebview sets `Form.Size` while the form still has
   the default `Sizable` border and only later switches to `None` for
   `frameless=True`, so the WebView2 child was sized under the old border and
   the panel laid out at **364x861 inside a 380x900 window**. Fixed by pinning
   `Form.ClientSize` after the border change (`_fit_client_area`).
3. **pywebview's wire format.** Three separate measured refusals, each fixed
   at the source rather than papered over: the message must be an **array**
   (`too many values to unpack (expected 3)`); the payload slot must be
   `JSON.stringify(arguments)` — an array of **positional** args
   (`SottoHost.dispatch() takes 2 positional arguments but 3 were given`);
   and each element is encoded **once** (`the JSON object must be str, bytes
   or bytearray, not dict`).

---

## Worker bridge — same contract, same policy

```
sotto: WORKER_PATH H:\sotto\worker\sotto_worker.py
sotto: WORKER_COMMAND C:\Program Files\Python311\python.EXE
sotto: BRIDGE_START reason=with-worker command=C:\Program Files\Python311\python.EXE worker=H:\sotto\worker\sotto_worker.py device=auto capture=callback
sotto: STATUS_APPLIED text="Starting worker... (sotto_worker.py)"
sotto: PLACEHOLDER_APPLIED title="Starting the worker"
sotto: BRIDGE_SPAWNED pid=21300 argv=["C:\\Program Files\\Python311\\python.EXE", "H:\\sotto\\worker\\sotto_worker.py"] SOTTO_CAPTURE_MODE=callback SOTTO_AUDIO_DEVICE=(unset)
```

* **The device is NOT forced.** `device=auto`, and `SOTTO_AUDIO_DEVICE=(unset)`
  in the child env — the env var is exported only when `--device=` is passed.
* `SOTTO_CAPTURE_MODE=callback` travels by **environment**, never by argv, so a
  strict-`argparse` worker cannot be killed by a preference.
* JSONL stdout (`{"type":"caption",…}` / `{"type":"status",…}`) is parsed, and
  both status invariants from `worker-bridge.js` are kept: an empty status is
  refused (it would leave the stale line on screen), and a status asserting
  audio is absent is **falsified** — the system tap on this host measures
  CAPTURED, so "waiting for audio" is a lie with a fix attached to it.

---

## Divergences from the Electron arm — named, not hidden

| | Electron | WebView2 | why |
|---|---|---|---|
| hotkey repeat | keydown repeats | `MOD_NOREPEAT` | holding Alt+C should not machine-gun the panel |
| all-workspaces | `setVisibleOnAllWorkspaces` | **not ported** | WinForms/WebView2 has no equivalent; the shell logs `SKIPPED` |
| worker state names | `STATE_MAP` dictionary | **not ported** | a cosmetic table in another file; raw tokens are shown verbatim rather than guessed at |
| pixel capture in `--dump-dom` | `capturePage()` | **not ported** | it needs a drawable surface, i.e. a visible window; the dump measures the DOM, and a measurement run must not put a window on the owner's screen |

## Did a window appear on the owner's screen?

**Yes, and only these two, both deliberate:**

* `--show` and `--with-worker --show` runs put the **Sotto panel itself** on
  screen — that window is the deliverable, and those runs are what prove it
  renders and what the memory number describes. The machine's window census
  recorded them: `ALERTA-JANELA … nome=python` at 05:41:21.
* `--dump-dom` and `--selftest` show **nothing**: the dump measures the DOM,
  and the selftest's window exists but is `SW_SHOWNOACTIVATE` +
  `WS_EX_NOACTIVATE` and is never foreground (`focus_before == focus_after`).

The Electron arm's own `--dump-dom` also shows its window by design
(`showInactive()` before `capturePage()`); that was the reference run.

## Runtime actually installed (not assumed)

```
$ py -3 -m pip show pywebview
Name: pywebview  Version: 6.2.1
$ py -3 -c "import pythonnet"          # pythonnet ok
$ WebView2 runtime, registry HKLM\SOFTWARE\WOW6432Node\...\EdgeUpdate\Clients\{F3017226-...}
FOUND pv ('154.0.4258.53', 1)
```

Nothing had to be installed: pywebview 6.2.1 and the WebView2 runtime were
already on this box.

## How to run it

```
H:\sotto\app\webview\run.cmd                    REM hidden, wait for Alt+C
H:\sotto\app\webview\run.cmd --show             REM panel up immediately
H:\sotto\app\webview\run.cmd --with-worker      REM also spawn worker\sotto_worker.py
H:\sotto\app\webview\run.cmd --help             REM every flag
```

Native `H:\` paths only. `./node_modules/.bin/electron` does not execute on
this box (**rc=127**, measured) — the Electron arm was re-run with
`H:\sotto\app\node_modules\electron\dist\electron.exe` for exactly that reason.
---

## SELF-AUDIT

**protocolos em falta** — I did not know two rules before this lane and would
repeat the mistake. (1) *A green gate must be able to say RED.* My first
`BRIDGE_GATE` read only `panelSaidBridgeMissing` — the **absence** of a string in
the body — and it passed **vacuously** on a 404 page that had no body text at
all, while I had already printed `hasSotto=true`. I only caught it because I
added the document's own identity (`url`, `hasPanelElement`) to the probe when
something else looked wrong. What I would do differently: write the gate's RED
case **first**, and make it fire on a deliberately broken input before trusting
it GREEN. (2) *The instrument must measure the thing the claim is about.* My
first memory census walked only **direct** children and read 210.9 MB; the true
WebView2 tree is 416.3 MB. The instrument was flattering the thing it was
measuring. Before any number goes in a receipt: ask what the number would be if
the claim were false, and make the instrument unable to produce it.

**verificacao adicional** — run and cheap, so run: re-ran the whole acceptance
set **after** the last code change (the tightened gate), because every earlier
green was measured on a build I had since edited. Confirmed still GREEN with
the stronger conditions. The one I could NOT run cheaply: an end-to-end caption
from the real worker into the real panel — see *nao verificado*.

**checkboxes novas** — for any WebView2/pywebview shell:
1. `py -3 sotto_webview.py --dump-dom` must print
   `BRIDGE_GATE=GREEN hasPanelElement=true url=…/panel.html` — a gate that
   names the **document**, not just a string's absence.
2. `grep "SHELL_EXIT rc=" <log>` — a run that produced no exit line is not a run,
   whatever else it printed.
3. `tasklist /FI "PID eq <pid>"` for every pid the run logged — a receipt that
   leaves a process behind is not finished.
4. A layout diff against the previous shell **re-measured in the same session**;
   compare `panel.css`'s mtime with the log's, because a stale receipt compares
   two different pages. (This bit me: `panel.css` was 5 min newer than the
   Electron numbers I was about to quote.)

**review por outro subagente** — **nao**. Not because the work is un-reviewable
but because every claim in this receipt is a pasted log line plus a mechanical
diff, and a second reader would re-read those same lines rather than add an
instrument. If one thing deserves adversarial review it is the three pywebview
wire-format rules in `BOOTSTRAP_JS` — each was found by a crash message, and a
reviewer should check there is no fourth.

- **Gate-doubt**

**verde-de-verdade:** for each gate, could it have passed vacuously?
* `BRIDGE_GATE` — **yes, and it did.** One earlier run printed
  `hasSotto=true … panelSaidBridgeMissing=false` while the document was
  `Error: 404 Not Found` with no `#panel` in it. Named race: *absence-of-a-string
  on a page that never rendered the panel*. Now closed by four required
  conditions (`panelSaidBridgeMissing` false, `hasPanelElement` true,
  `url` endswith `panel.html`, `DOMDUMP.els['#panel']` non-null); re-run green.
* `SELFTEST rc=0` — could pass with a null `hwnd`, because `self.visible` would
  stay `False` and `if … or self.visible` would be satisfied. Closed by
  requiring `presses == 2` **and** by the `PANEL_SHOWN … visible=true` line that
  only prints after a real `IsWindowVisible` — that line was present, so this
  path did not run vacuously.
* the layout diff — compares two JSON blobs. If **both** arms had measured the
  same wrong document it would be green. It cannot have here: the Electron side
  is a separate process with its own renderer and printed real element rects.
  Residual risk named rather than dismissed.
* the memory number — not a gate; it is a measurement, and the one I already had
  to correct once (see *protocolos em falta*).

**falta-no-gate:** no gate exercises a **caption** travelling worker → host →
page → DOM → `CAPTION_APPLIED`. Every gate above stops at `ready`. A future
change that broke only the `caption` kind of `dispatch` — or broke
`on_worker_caption` — would pass all four acceptance gates green and deliver a
panel that never shows a word. Scenario: someone edits the worker JSONL key from
`text` to `caption`, or drops the `caption` entry from the dispatch table.

**gate-melhor** — add to `run_dump_dom` a self-caption: call
`window.sotto.pushCaption('<probe text>')` through `ExecuteScriptAsync`, then
require `#caption-list` to contain it and `CAPTION_APPLIED` to appear in the
log. RED input: `--worker H:\sotto\worker\does-not-exist.py` (bridge goes to
`missing` and no caption can arrive) — the run must exit 3, not 0.

**confianca** — **alta** on the four acceptance criteria: each is a pasted log
line or a mechanical diff against a re-measured baseline, and I have the failing
versions of all of them in this session's logs. **media** on the worker bridge:
its spawn contract is proven, its end-to-end caption path is not.

**nao verificado** —
1. **A caption end-to-end from the real worker.** `--with-worker` spawns the
   worker correctly (`BRIDGE_SPAWNED pid=… argv=[…] SOTTO_CAPTURE_MODE=callback
   SOTTO_AUDIO_DEVICE=(unset)`) and its status reaches the page
   (`STATUS_APPLIED`, `PLACEHOLDER_APPLIED`), but every worker-mode run **died
   externally at ~30 s with rc=1 and no Python traceback**, before the
   `--exit-after` timer or the `MEMORY` line. No exception was raised by this
   host; the runs that do not spawn the worker (`--dump-dom`, `--selftest`,
   `--memory`) all exit rc=0 in 4–17 s. Most likely the ASR worker's model load
   on a loaded box, not a defect in the shell — but I did not prove that, so it
   is listed here rather than excused.
2. **`--exit-after` with a live worker.** I fixed the one defect I *did* find
   there (`window.destroy()` blocking behind the UI thread — it is now on its own
   thread with a 3 s cap), but the fixed path was never observed printing
   `SHELL_EXIT` in worker mode.
3. **`setVisibleOnAllWorkspaces` parity** — not ported; no WebView2/WinForms
   equivalent exists. Named, not tested.
4. **Non-100% DPI.** `dpi_scale()` and the DIP↔physical conversion are written
   and correct by inspection; this host is scale 1.0, so that branch never ran.
5. **`getInfo()`'s resolved Promise.** The id round-trip is implemented; no gate
   calls it, and `panel.js` does not use it.
6. **Multi-monitor.** `primary_display()` uses
   `MonitorFromPoint(0,0, DEFAULTTOPRIMARY)`, matching Electron's
   `getPrimaryDisplay()`. One monitor attached.

## CACHE/PRICE
- task/agent: SottoWebViewShell
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoWebViewShell.jsonl
- cache: read=37646548 write=0 hit=98.7518% (cache-read / input+cache-read); universe: 141 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoWebViewShell.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=141 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 141 of 141 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T05:17:50.386000+00:00 | break_items=3; WHEN=2026-10-06T05:23:00.964000+00:00 | break_items=2; WHEN=2026-10-06T05:32:58.524000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 110906 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoWebViewShell']; window: 2026-10-06T05:17:50.386000+00:00..2026-10-06T05:32:58.524000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=43; turn_id=1791263870386 | session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=68; turn_id=1791264180964 | session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=231; turn_id=1791264778524 (state=RESOLVED-BREAKS-OMP; population: 3 of 110906 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoWebViewShell']; window: 2026-10-06T05:17:50.386000+00:00..2026-10-06T05:32:58.524000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T05:49:31.732674+00:00
- usage rows: 141
- model + route: opencode-zen/space-bunny-free
- input tokens: 475845
- output tokens: 98381
- cache-read tokens: 37646548
- cache-write tokens: 0
- hit ratio: 98.7518% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=141 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 141 of 141 matched usage rows
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 3 of 110906 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoWebViewShell']; window: 2026-10-06T05:17:50.386000+00:00..2026-10-06T05:32:58.524000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T05:17:50.386000+00:00; WHERE session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=43; turn_id=1791263870386
  - break_items=3; WHEN=2026-10-06T05:23:00.964000+00:00; WHERE session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=68; turn_id=1791264180964
  - break_items=2; WHEN=2026-10-06T05:32:58.524000+00:00; WHERE session_id=01a10fa3-9c9b-7112-88f5-97e1fd7d0674 provider=space-bunny-free model=space-bunny-free item_index=231; turn_id=1791264778524
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
