# Sotto — the WebView2 shell IS the app

status: done

**Date:** 2026-10-06
**Owner ruling, verbatim:** *"sem fallback. webview2 é pra funcionar, pronto."*

`app/webview/run.cmd` is **the app**. Nothing calls Electron a fallback; where
the Electron tree is mentioned it is called what it is — the earlier shell,
kept for its panel files and as the reference arm.

| | |
|---|---|
| the app | `H:\sotto\app\webview\run.cmd` |
| the shell | `app/webview/sotto_webview.py` (WebView2, pywebview 6.2.1 + pythonnet) |
| hot reload | `app/webview/hot_reload.py` |
| docs | `app/webview/README.md`, this file |
| prior receipt | `docs/webview-shell-20261006.md` (the port) |
| logs | `H:\sotto\_main\webview-*.log`, `console-census-*.json` |

---

## 1. `run.cmd --help` works and names the app

```
$ cd H:\sotto\app\webview
$ cmd /c "run.cmd --help"
usage: sotto-webview [-h] [--show] [--hotkey HOTKEY] [--worker WORKER]
                     [--python PYTHON] [--device DEVICE] [--capture CAPTURE]
                     [--with-worker] [--dump-dom] [--opaque] [--selftest]
                     [--memory] [--memory-wait MEMORY_WAIT]
                     [--exit-after EXIT_AFTER] [--no-hot-reload] [--log LOG]

The Sotto panel, hosted by WebView2 (pywebview).
...
rc=0

names the app: True
mentions fallback: False
has --no-hot-reload: True
```

The only word `fallback` that existed in the repo was in `run.cmd`'s own
header. It is gone (`AGENTS.md` keeps one, quoting the owner's ruling).

---

## 2. Start hidden, Alt+C through `--selftest`, focus not stolen

```
$ cmd /c "run.cmd --selftest --log H:\sotto\_main\B-selftest.log"
sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=36684
sotto: SELFTEST hotkey_registered=true accelerator=Alt+C
sotto: PANEL_HIDDEN reason=selftest-baseline visible=false
sotto: SELFTEST state=hidden visible=false
sotto: PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
sotto: SELFTEST state=after-hotkey-1 visible=true press_delivered=true presses=1
sotto: PANEL_HIDDEN reason=hotkey visible=false
sotto: SELFTEST state=after-hotkey-2 visible=false presses=2
sotto: SELFTEST focus_before=71404 focus_after=71404 focus_stolen=false
sotto: SELFTEST rc=0
sotto: SHELL_EXIT rc=0 reason=selftest
```

`visible=false → true → false`, `presses=1` then `2`, `rc=0`, and
**`focus_before == focus_after`**.

**One honest note.** An earlier run of this same command printed
`HOTKEY_REGISTER_FAILED … winerror=1409` and `SELFTEST rc=3`. That was not a
flaky hotkey: the previous `--exit-after 25` instance was still alive and
already owned Alt+C. Two shells must not both own it, and `winerror=1409` is
the correct refusal. The run above is the one with nothing else alive.

---

## 3. Touch `panel.css`, the RUNNING shell reloads it, no restart

```
$ py -3 -u hotreload-acceptance.py
launched: {"pid": 32288, ...}
panel_ready: {"saw": true}
before: {"our_pid": 32288, "alive": true, "shell_identity_lines": 1,
         "identity": ["sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=32288"]}
baseline_reloads: {"count": 0}
touched: {"file": "H:\\sotto\\app\\electron\\panel.css",
          "how": "write-temp+rename-over",
          "sha256_after": "51538db4ed0b1ab9fdd58182272857451cfd9c446864085f2f9f700711fabb82"}
reload_applied: {"saw": true,
                 "line": "sotto: HOT_RELOAD_APPLIED reload=1 visible=false hotkey_still_registered=true"}
after: {"our_pid": 32288, "still_alive": true, "shell_identity_lines": 1,
        "no_restart": true,
        "identity": ["sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=32288"]}
hotkey_survived_reload: {"lines": ["sotto: HOT_RELOAD_APPLIED reload=1 visible=false hotkey_still_registered=true"]}
reload_count: {"count": 1, "lines": ["sotto: HOT_RELOAD_PANEL_DONE files=[\"panel.css\"] reload=1 hotkey=Alt+C"]}
reverted: {"sha256": "0f5dad3dcf36e56c0aae9f85286f950b71ded63f32bfd31151c72108b2229bb4",
           "matches_before": true}
revert_reloaded: {"saw": true}
verdict: {"rc": 0, "PASSED": true}
rc=0
```

* **No restart:** one `shell=… pid=` identity line before and after, and pid
  32288 alive throughout. A restart would have to announce a new pid.
* **The touch is the real editor shape** — write-temp then rename over, which
  is the case a file watch dies on.
* **Reverted byte-for-byte**, sha256 recorded on both sides.
* **The revert reloaded too** (`reload=2`): one save, one reload, both ways.

---

## 4. The console census — and the instrument was WRONG first

```
$ py -3 console-census.py D-BEFORE
D-BEFORE: processes=366 conhost=19
$ cmd /c "run.cmd --exit-after 25"    (via run.cmd)
$ py -3 console-census.py D-AFTER
D-AFTER: processes=373 conhost=19
DELTA conhost = 0
```

**`conhost` count did not move: no console window was created by this lane.**

### The first census was a green that could not go red

The first version of this instrument reported **`conhost=0` before and after**,
and I nearly wrote that up as the proof. It was worthless. The Toolhelp walk
re-created its `PROCESSENTRY32W` after every `Process32NextW`, discarding the
row the call had just written and reading a zeroed struct instead. Measured:

```
n 371 min 0 max 0
sample [(0, '[System Process]'), (0, ''), (0, ''), ...]
```

**Every row: pid 0, exe name empty.** A filter for `conhost.exe` over that can
only ever return 0 — no observation of the machine could turn it red. The box
in fact carries **19–23 `conhost.exe` processes** at rest.

Fixing it (allocate the struct once) and re-measuring gave the honest baseline,
and the positive control proves the fixed instrument can still move:

```
fixed-baseline:     processes=392 conhost=23
fixed-with-console: processes=393 conhost=23   (a cmd.exe was running)
fixed-after-console: processes=380 conhost=22  (it had exited)
```

### Why a process census and not a window census

`EnumWindows` is refused on this box by the privacy guard, and it is right to
be: another application's windows are not this lane's to read. A console window
cannot exist without a console process, so `conhost.exe` before/after answers
the same question without touching anyone's windows, titles or state.

### The child's own console, measured directly

`pythonw.exe` is a GUI-subsystem binary, so Windows allocates no console for
it. Launched detached by `Start-Process` and asked from the inside:

```
{"exe": "C:\\Program Files\\Python311\\pythonw.exe",
 "stdout": "None", "stderr": "None", "console_hwnd": 0}
```

(`_main/_pwtest3.json`.) And the launcher is confirmed to be the GUI binary:

```
$ py -3 list-sotto-procs.ps1 | …    # filter names the ARTIFACT
LAUNCHED BY run.cmd -> exe=pythonw.exe pid=18100
  cmdline: "C:\Program Files\Python311\pythonw.exe" "H:\sotto\app\webview\sotto_webview.py" --log …
```

`pythonw` has no stdout, so `run.cmd` passes `--log` and **the receipt of a
hidden run is the file** `H:\sotto\_main\webview-run.log`. `--help`,
`--dump-dom`, `--selftest` and `--memory` print, so they run under `python.exe`
and write to the terminal you already have.

---

## 5. The watcher's own gate — six arms, no window

```
$ py -3 hot_reload.py --selftest
selftest: HOT_RELOAD_ENABLED watchers=2 debounce_ms=250
selftest: ARM burst writes=8 flushes=1 expect=1
selftest: ARM single writes=1 flushes=1 expect=1
selftest: ARM rename renames=3 flushes=1 expect=1 alive_after_rename=true
selftest: ARM alive_after flushes=1 expect=1
selftest: ARM worker flushes=1 expect=1
selftest: ARM non_asset flushes=0 expect=0
selftest: SELFTEST rc=0
rc=0
```

### Why this file exists at all

`app/electron/hot-reload.js` already owns this idea for the Electron arm. It is
CommonJS and `require`s `node:fs`; a Python process cannot load it, so it was
**not portable and could not be reused**. `hot_reload.py` reproduces its
*contract* — watch directories not files, 250 ms debounce per kind, decide
when and hand the caller the settled list — with the engine-appropriate
mechanism. `watchdog` is not installed on this box (measured
`ModuleNotFoundError: No module named 'watchdog'`), so it uses
`ReadDirectoryChangesW` directly rather than adding a dependency.

### Three measured facts this box does not match the docs

1. **The OVERLAPPED event is never signalled.** `ReadDirectoryChangesW`
   completes and `GetOverlappedResult` returns the bytes within ~0.1–0.3 s,
   but `WaitForSingleObject(event, 5000)` returns **258 (`WAIT_TIMEOUT`)** with
   the data already in the buffer. The first version of the loop waited on that
   event, blocked forever, reported nothing — and hot reload simply never
   fired (`ARM burst writes=8 flushes=0 expect=1`, rc=3). Completion is now
   polled, with the wait reduced to a sleep tick.
   (`_main/_probe/rdc.out`, `_main/_probe/rdc2.out`.)
2. **`ctypes.wintypes` has no `OVERLAPPED` and no `POINTER`** on this Python —
   both measured as `AttributeError`. Both structures are declared locally.
3. **A pending overlapped read points the kernel at the OVERLAPPED struct and
   the buffer.** Allocating them per loop iteration handed the kernel pointers
   into released heap; the process later died with
   `Windows fatal exception: access violation` inside `shutil.rmtree`
   — 2/2 with the cleanup, 0/2 without (`_main/_probe/hr5.out`,
   `hr6.out`). They are owned by the watcher for its lifetime, and `stop()`
   drains the cancelled read before any handle is closed.

---

## What did NOT get measured cleanly

- **Memory was not re-measured** for the new hot-reload code path. The
  +33% figure in `docs/webview-shell-20261006.md` stands as previously
  measured; two directory watchers and a 100 ms poll tick are the only new
  cost, and nothing here re-litigates the owner's ruling on it either way.
- **The `--with-worker` path was not exercised in this lane** — it spawns
  `worker/sotto_worker.py`, which lane `SottoInt8Route` owns. `run.cmd`
  forwards the flag and the shell's `BRIDGE_START` path is unchanged, but no
  run here proves a worker spawned from the new launcher.
- **`panel.css` is a shared file.** The acceptance touches it and reverts it
  with a sha256 check; a sibling lane editing it at the same moment would show
  up as a revert whose `matches_before` is false. It was true in every run
  recorded here.

---

## SELF-AUDIT

**protocolos em falta** — two, and both cost real time.

(1) *A green gate must be able to say RED.* My console census reported
`conhost=0` before and after, and I was about to write that up as proof. It was
a green that **could not go red**: the Toolhelp walk re-created its
`PROCESSENTRY32W` after every `Process32NextW`, threw away the row just written,
and read a zeroed struct — 371 rows, every pid 0, every name empty. A filter
for `conhost.exe` over that returns 0 forever. The real baseline is 19–23. What
I would do differently, and now do in the code: before writing any number up,
ask *what would this instrument print if the claim were false?* — and if the
answer is "the same thing", the instrument is the bug. I only found it because
the baseline seemed too round; I should have distrusted it immediately.

(2) *Prefer the instrument you can see.* `shell_pids()` asked PowerShell
`Get-CimInstance` over `-Command` and got **empty stdout every time** — while
the same query in a `.ps1` file returned every row. The empty list made the
acceptance report `no_restart: false` for a shell that was demonstrably alive.
An instrument that reads nothing reports "nothing is running" no matter how much
is. What I would do differently: before trusting an external command's output,
run it once against a case whose answer I already know — here, *is my own pid
in the list?* — and keep that check in the harness.

**verificacao adicional** — run, because it was cheap and it changed a
conclusion. After fixing the census I ran a **positive control**: start a
`cmd.exe`, census, let it exit, census again. It moved `conhost 23 → 23 → 22`
and `processes 392 → 393 → 380`. Without that, "delta 0" is indistinguishable
from "the instrument is blind" — which is exactly the bug I had just fixed.

**checkboxes novas** — for any lane that writes a measurement harness in this
repo:
1. `grep -c . <output>` must be non-trivial and must contain a value you did
   not put there yourself. A census that returns an empty list is a red flag,
   not a zero.
2. Every instrument gets a **positive control** run before its negative result
   is quoted: create the condition, prove the number moves, destroy it, prove
   the number comes back.
3. Assert the instrument against **its own process**: `pid_alive(os.getpid())`
   must be `True`. If a liveness check is `False` for the caller, the check is
   wrong, not the machine.

**gate-doubt**
- **verde-de-verdade**: three gates, and **one of them was a false green that I
  caught and reported**: the `conhost=0` census. Name of the race — the
  instrument's own bug (`PROCESSENTRY32W` reallocated per iteration) made the
  filter vacuous, and I read the vacuous 0 as a measurement. The other two: the
  hot-reload gate is RED-capable by construction (the `alive_after` arm fails
  the moment a watcher dies at a rename, and it caught three real bugs during
  this lane); the selftest gate is RED-capable because `rc=3` was observed on
  this very command when the hotkey was contended.
- **falta-no-gate**: neither the reload nor the selftest asserts the *rendered
  pixels* — they assert the host's own log lines and the DOM bridge. A change
  that made `load_url` succeed while leaving the panel visually stale would
  pass both. The `--dump-dom` probe would catch a layout regression but is not
  wired into the reload path.
- **gate-melhor**: after a hot reload, run the existing `DUMP_DOM_PROBE` in the
  same process and compare it to the pre-touch probe; RED if the panel element
  is missing or `#panel` no longer has `rect [0,0,380,900]`. Input that must
  leave it RED: `reload_panel_assets` pointed at `stage.html` instead of the
  panel — the bridge probe still answers `hasSotto=true`, so today that passes.

**confianca** — **média→alta** on the four acceptance criteria, each measured
with a command whose output is pasted above; **média** on the whole lane, for
the reason below. What would raise it: exercising `--with-worker` end to end
(this lane cannot — the worker file belongs to `SottoInt8Route`), and a
post-reload DOM assertion.

**nao verificado**
- `--with-worker` actually spawning a worker from the new `run.cmd`.
- That the reloaded panel renders the *edited CSS*, as pixels (the DOM bridge and
  the host log are proven; the pixels are not).
- Memory of the shell with the hot-reload watchers armed.
- Whether a `--with-worker` run survives a worker-source save (the restart path
  `restart_worker` is written and compiled but was never exercised, because
  touching `worker/*.py` is outside this lane's files).

---

## CACHE/PRICE

- cache: read=41692489 write=0 hit=99.0568% (cache-read / input+cache-read); universe: 174 usage rows from the SottoWebViewDefault session JSONL
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source). Model/route: opencode-zen/space-bunny-free, 174 calls, input 396974 / output 76722 / cacheRead 41692489 / cacheWrite 0 tokens.
- when-failed: 6 prefix breaks, 3 attributable to this session. WHEN=2026-10-06T05:59:03.253000+00:00 | WHEN=2026-10-06T06:03:50.120000+00:00 | WHEN=2026-10-06T06:13:51.828000+00:00
- where-failed: session_id=01a10fc9-0848-7436-a6c1-849ba0399793 provider=space-bunny-free item_index=49 turn_id=1791266343253 | item_index=123 turn_id=1791266630120 | item_index=323 turn_id=1791267231828 (state=RESOLVED-BREAKS-OMP)
- source: `bash I:/!manager/scripts/cache-task-report.sh SottoWebViewDefault` — full verbatim output kept at `H:\sotto\_main\_probe\cache-report.txt`; instrument `scripts/cache-task-report.sh`, generated_at 2026-10-06T06:19:00.755283+00:00. Verdict printed by the instrument: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision.