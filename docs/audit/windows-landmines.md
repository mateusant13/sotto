# Windows-specific failure modes in `H:/sotto` — audit

**Scope.** Every occurrence in `H:/sotto` of the six landmines this house has measured
elsewhere, with a verdict of *bites* / *does-not-bite* and the evidence for each.

The six landmines, as named in the brief:

1. `pythonw` vs `python.exe` — no stdout, and `argparse` exiting 2 into a void.
2. `CREATE_NO_WINDOW` alone vs together with `DETACHED_PROCESS` — detached returns an
   **empty channel with rc 0**.
3. `taskkill` truncating a log so the last lines vanish.
4. `conhost` windows appearing from a console child.
5. Paths with spaces.
6. `subprocess.run(timeout=)` **not** being a time ceiling on Windows.

**Method.** Read-only. I read the source and the house's own measurement artefacts
(`*.json`, oracle logs), and I ran **two live windowless measurements** of my own
(landmine 2 and landmine 3), each reproduced below. Host: Windows 10.0.26200, this box.
Interpreter for every spawn I launched: `python.exe` with `CREATE_NO_WINDOW` **only**.
The running app (pid **30848**) was not touched, killed, restarted, or queried.

**Surfaces found in `H:/sotto`:**

| surface | what it is |
|---|---|
| `app/webview/run.cmd`, `app/webview/sotto_webview.py`, `app/webview/hot_reload.py` | **THE APP** (pywebview + WebView2). `AGENTS.md`: "The app is `app/webview/run.cmd`." |
| `worker/sotto_worker.py`, `worker/wasapi_loopback.py` | the ASR worker |
| `app/electron/*.js` | **LEGACY** Electron shell ("NOT a fallback", `AGENTS.md`) |
| `_main/*.py`, `app/electron/_hotreload/*.py`, `probe/*.py`, `worker/_probe/*.py` | probes / oracles / harness |

`worker/wasapi_loopback.py` and `app/webview/hot_reload.py` contain **no** `subprocess`,
`os.system`, `os.startfile` or console spawn of any kind (verified by grep) — they are
out of scope for this audit except where noted.

---

## Landmine 1 — `pythonw` vs `python.exe` (no stdout; `argparse` exits 2 into a void)

### The law and its in-repo measurement

The house's own measurement lives in the repo:

- `_main/_pwtest3.py` (whole file) writes `_main/_pwtest3.json`; that JSON is the receipt:
  ```json
  { "exe": "C:\\Program Files\\Python311\\pythonw.exe",
    "stdout": "None", "stderr": "None", "console_hwnd": 0, "print": "ok" }
  ```
  A `print()` under `pythonw.exe` succeeds in the process and reaches **nothing**
  (`sys.stdout is None`), and there is no console at all (`GetConsoleWindow()==0`).
- `AGENTS.md` states the `argparse` half verbatim: *"`run.cmd --bogus-flag` returned rc=0
  with no output, no log bytes and no process: argparse exits 2 on `pythonw.exe` (whose
  stdout is None) and `start` reports only its OWN success, so the interpreter's status
  never reached the caller."*
- `_main/run-cmd-exit-oracle.py:1-30` is the gate that holds that fix on both colours.

### Occurrences

| file:line | what it does | bites? |
|---|---|---|
| `app/webview/run.cmd:14-19` | doc: a normal launch goes through `pythonw.exe`; `print()` is a no-op there, hence `--log` | by design |
| `app/webview/run.cmd:39-51` | locates `pythonw.exe` beside the interpreter `py -3` resolves; falls back to `python.exe` | correct |
| `app/webview/run.cmd:56-66` | `--help`/`-h`/`--dump-dom`/`--selftest`/`--memory` run under **`python.exe`** so they PRINT | **fixes the landmine** |
| `app/webview/run.cmd:83-92` | PRE-FLIGHT: `"%PYW%" "%SHELL%" --check-args %*` before anything starts; non-zero → echo the refusal, append `ARGS_REJECTED` to `_main/webview-run.log`, `exit /b <rc>` | **fixes the argparse-into-void landmine** |
| `app/webview/sotto_webview.py:2450-2468` | `--check-args` mode: `parse_args` validates and returns 0; starts nothing, logs nothing | the other half of the fix |
| `_main/_pwtest3.py` (whole) + `_main/_pwtest3.json` | the measurement that `pythonw` has `stdout=None` | reference receipt |
| `_main/gpu-diag.py:2-3` | docstring: *"Must run under python.exe so stderr is real (pythonw has no stderr, which is exactly how the reason gets lost)"* | **bites if run under pythonw** — but the file itself requires `python.exe` |
| `_main/lang-id-oracle.py:14-15` | "Launched with pythonw by `_main/lang-id-runs.py`, so no console appears" | writes to files, so the missing stdout is handled |
| `_main/_dance-probe.py:18-19` | "Launched with pythonw.exe + CREATE_NO_WINDOW" | reads back via a log line, not stdout |
| `_main/device-names.py:2-3` | "Writes a log (pythonw)" | writes to `device-names.log` — handles it |
| `_main/_visiblechanged-probe.py:12-13` | launched under `pythonw.exe` | writes to a file |
| `app/electron/_hotreload/preflight.py:1-13` | "run under pythonw.exe, never python.exe … Everything is written to a report file: pythonw has no stdout" | handles it (report file) |
| `app/electron/_hotreload/{psdiag,winprobe,selfwindow,whois,acceptance}.py` | all run under `pythonw`, all write `*.json` reports | handle it |

### Verdict

**The app path is correct and the `argparse`-into-a-void failure is closed** by the
pre-flight (`run.cmd:83-92` + `sotto_webview.py:2462`), and the two output branches are
justified by a measurement (`_pwtest3.json`). The landmine **bites only a probe that
launches a printing entrypoint under `pythonw` without redirecting to a file**; every
such probe in the repo works around it by writing a file, and `_main/gpu-diag.py:2-3`
names the trap explicitly.

---

## Landmine 2 — `CREATE_NO_WINDOW` alone vs with `DETACHED_PROCESS` (empty channel, rc 0)

### My live measurement (this host, 2026-10-06)

I reproduced the exact PowerShell call that `_main/_probe/console-census.py` issues,
varying only `creationflags`:

```
CNW_only   : rc=0 bytes=4040 stderr=0 ms=535  head='12536|pythonw.exe|"I:\\!produtos202608\\BrandOps\\...
CNW|DET    : rc=0 bytes=0    stderr=0 ms=76   head=''
DET_only   : rc=0 bytes=0    stderr=0 ms=63   head=''
```

`CREATE_NO_WINDOW | DETACHED_PROCESS` returns a **0-byte channel with rc 0**, and
`DETACHED_PROCESS` alone does the same. `CREATE_NO_WINDOW` alone returns 4040 bytes.
This is the landmine, reproduced verbatim, and it is **executable-specific**: the same
flags on `node.exe` do not blank the channel (see `preflight.json` below).

### Occurrences

| file:line | what it does | flags | bites? |
|---|---|---|---|
| `_main/_probe/console-census.py:102-106` | `python_pids()` — the census that lists python/pywx **with command lines**, via PowerShell `-Command` | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | **BITES — proven.** It reads 0 bytes rc 0, so `python_pids()` always returns `[]`. The docstring ("Read from the PowerShell process table") is false; the instrument is blind |
| `app/electron/_hotreload/preflight.py:56` | `node --check <file>` syntax gate | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | **does NOT bite** — `preflight.json` shows `main.js`/`hot-reload.js` rc 0 with empty output, and the **negative control** (`_syntax_control_broken.js`) rc=1 with 232 B of stderr; the gate is not vacuous |
| `app/electron/_hotreload/acceptance.py:355` | positive-control child (marker process) | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | does NOT bite — `Popen` with **no capture**; only `child.pid` is used |
| `app/electron/_hotreload/acceptance.py:384` | launch `electron.exe` | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | does NOT bite for *this* landmine — `stdout=logfh` is a **file handle**, not a pipe |
| `app/electron/_hotreload/acceptance.py:519-524` | `taskkill /PID /T /F` | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | **not blanked** — my run shows `taskkill` under this combo still returns its message (rc 128, non-empty). But `report.json` records `taskkill_out: ""`, unexplained (see "Not verified") |
| `app/electron/_hotreload/winprobe.py:62` | spawn a `pythonw` child to watch for windows | `CREATE_NO_WINDOW \| DETACHED_PROCESS` | does NOT bite — `Popen`, **no capture** |
| `_main/_probe/hotreload-acceptance.py:28,130-133` | launch the `pythonw` shell | `NO_WINDOW = 0x08000000 \| 0x00000008` | does NOT bite — `Popen`, **no capture** (it watches the file `.stdout`) |
| `_main/_ppv-census-driver.py:11-14,40` | drives the house census; **explicitly refuses DETACHED** | `CREATE_NO_WINDOW` alone | correct — and it treats an empty channel as `CEGO`, never as clean |
| `_main/lang-id-runs.py:4-5,25,57` | worker arms; comment: *"(0x8) makes a PowerShell child emit 0 bytes"* | `CREATE_NO_WINDOW` alone | correct |
| `_main/lang-id-default-arms.py:3-4,20` | worker arms; comment: *"adding DETACHED_PROCESS makes a child emit 0 bytes on this box, measured"* | `CREATE_NO_WINDOW` alone | correct |
| `app/electron/_hotreload/acceptance.py:136-142,163-169` | the command-line query; comment records the trap and routes it via a **`.ps1` FILE** with `CREATE_NO_WINDOW` alone | `CREATE_NO_WINDOW` alone | correct |
| `_main/_probe/console-census.py:94` (doc) | *"always CREATE_NO_WINDOW so this census never creates the console it is looking for"* | — | the doc is right; the code at :106 is not |

Correct `CREATE_NO_WINDOW`-only capture sites (all fine): `_main/run-cmd-exit-oracle.py:102,272`;
`_main/runcmd-entry-driver.py:172`; `_main/device-silence-oracle.py:41,69`;
`_main/panel-exit3-oracle.py:87,156`; `_main/panel-startup-visibility-oracle.py:92,268`;
`_main/panel-startup-flash-census.py:66,354`; `_main/panel-visible-window-probe.py:79,284`;
`_main/verdict-order-oracle.py:73,161`; `_main/vad-arm-run.py:17,27`;
`_main/_armE-window-census.py:26,110`; `_main/measure-asr-warmup.py:39`;
`_main/_run-hidden.py:14`; `_main/_runcmd-console-probe.py:26`.

### Verdict

**One bite, and it is proven: `_main/_probe/console-census.py:106`.** Its
`python_pids()` — the exact function whose output builds the kill filter and attributes a
pid — is blind, because the flags it passes to PowerShell blank the channel to 0 bytes
rc 0. Everything else in the repo either uses `CREATE_NO_WINDOW` alone (with the trap
documented in two probe files and one acceptance comment) or uses the combo only on paths
that need no captured channel.

---

## Landmine 3 — `taskkill` truncating a log so the last lines vanish

### My live measurement (this host, 2026-10-06)

I killed a child with `taskkill /PID <pid> /F` mid-run and checked a log the child had
written **without** an explicit flush:

```
file 200B while alive: 200            # python, stdout -> FILE, no flush, still running
pipe after kill bytes: 200            # python, stdout -> PIPE, no flush
node->PIPE after taskkill /F bytes: 50  # node, stdout -> PIPE
```

In all three configurations the bytes the child wrote **survived** `taskkill /F`. I could
**not** reproduce "the last lines vanish" with a Python child (file or pipe) nor a Node
child (pipe) on this host.

### Occurrences

| file:line | what it does | bites? |
|---|---|---|
| `app/electron/_hotreload/acceptance.py:519-524` | `taskkill /PID <electron> /T /F` after `stdout=logfh` (the app's `app.log`) | **bites as "no graceful shutdown"** — see below; buffered-tail loss not reproduced |
| `app/electron/_hotreload/workerarm.py:156` | `taskkill /PID /T /F` on electron, stdout to a log | same |
| `app/electron/_hotreload/optout.py:68` | `taskkill /PID /T /F` on electron | same |
| `_main/run-cmd-exit-oracle.py:272` | `taskkill /PID /F` — **fallback only**, reached after the app was already expected to reach its own `SHELL_EXIT` (`:430-437`) | low risk |
| `_main/runcmd-entry-driver.py:172-174` | `taskkill /PID /T /F` with `errors='replace'` | — (see the codepage note) |
| `_main/runcmd-entry-driver.py:168-170` | comment: *"taskkill writes in the OEM codepage … a strict utf-8 decode raised INSIDE the reader thread and handed back `stdout=None` (measured, first run of this driver)"* | **this is a real, in-repo taskkill failure that made output vanish** (a decode error swallowed it → `None`), and the fix (`errors='replace'`) is present |
| `_main/runcmd-entry-driver.py:207-210` | native `TerminateProcess` fallback when `taskkill` left the app alive | — |
| `_main/_probe/kill-sotto-shell.ps1:6`, `_main/_kill-my-probes.ps1:9` | `Stop-Process -Force` by artifact-matched cmdline | — |

### Verdict

Two honest results:

- **Buffered-tail loss did not reproduce.** `taskkill /F` on a Python child (file and pipe)
  and a Node child (pipe) preserved all written bytes. The app's own `log()`
  (`app/webview/sotto_webview.py:243-246`) **flushes every line and flushes the log file**,
  so the shell's receipt is not at risk from a kill in that sense.
- **The bite that IS real and documented is different in mechanism:** `taskkill /F` runs no
  orderly shutdown, so Electron's `will-quit` never runs and `HOT_RELOAD_STOPPED` never
  appears in the acceptance logs — stated by the repo itself at
  `app/electron/HOTRELOAD.md:326-330`. And the codepage case at
  `_main/runcmd-entry-driver.py:168-170` is a *measured* taskkill interaction that lost the
  output entirely (reader-thread decode error → `stdout=None`), precisely because of the
  pt-BR OEM codepage.

I therefore report the landmine as **partly applicable**: the "kill skips the shutdown
path" half bites and is documented; the "buffered tail is truncated" half I could not
reproduce on this host with the writers in this repo.

---

## Landmine 4 — `conhost` windows from a console child

### Occurrences / evidence

| file:line | what it does | bites? |
|---|---|---|
| `app/webview/run.cmd:14-19,66,104-110` | normal launch via `pythonw.exe` (GUI subsystem → **no console at all**) | correct |
| `app/webview/sotto_webview.py:1943-1944,1947` | worker spawned with `creationflags=CREATE_NO_WINDOW` | suppresses the **window** (a console is still allocated — see below) |
| `app/electron/worker-bridge.js:488` | legacy bridge `spawn(..., { windowsHide: true })` (Node sets `CREATE_NO_WINDOW`) | suppresses the window |
| `_main/_probe/console-census.py:1-20,96-100` | counts `conhost.exe` before/after and reads the child's own `GetConsoleWindow()` | the census instrument itself |
| `_main/_runcmd-console-probe.py:33-56` | measures `GetConsoleWindow()` / `IsWindowVisible()` on SELF, a **bare** child, and a `spawn_hidden` child | measures the trap |
| `_main/_probe/hotreload-acceptance.py` header, `AGENTS.md:53-65,145-149` | the law; and the recorded incident `ALERTA-JANELA pid=24836 … nome=python` from launching `python.exe` directly | the trap |

The precise law (stated by the house window-census governor itself and reproduced in
`AGENTS.md`): **`CREATE_NO_WINDOW` suppresses the WINDOW; it does not prevent the console
from being allocated — 1 `conhost.exe` is born per run.** `GetConsoleWindow()!=0` alone
would confuse "console allocated but invisible" with "window on screen", which is why
`_main/_runcmd-console-probe.py` reports both handle and `IsWindowVisible()`.

### Verdict

**The production app does not bite it** — it launches through `pythonw.exe` (no console
image) or with `CREATE_NO_WINDOW`. The risk lives in the *ops scripts that run under
`powershell.exe`* (`_main/make-tts-samples.ps1`, `worker/_probe/install_gpu*.ps1`,
`_main/_win.ps1`) — those are console hosts and would flash if run from an interactive
tool shell without a hidden-spawn shim; they are not part of the app and are not invoked by
it. The house already carries both a census and the incident receipt.

---

## Landmine 5 — paths with spaces

### What I checked

- **No command is ever built as a string and handed to a shell.** `grep` for
  `shell=True`, `os.system`, `os.startfile` over all of `H:/sotto` returns **zero
  functional hits** (only docstring mentions). Every spawn uses a **list argv**, so
  `C:\Program Files\Python311\pythonw.exe` and device names with spaces are single
  elements — safe by construction. Examples: `_probe/hotreload-acceptance.py:130-133`,
  `_main/measure-readiness.py:42-54`, `app/electron/_hotreload/acceptance.py:503-513`.
- **`run.cmd` quotes its paths** (`:66,84,104,110`) and does the `pythonw` substitution on
  the full quoted value (`:48`: `set "PYW=%PYEXE:python.exe=pythonw.exe%"`). The repo records
  the one quoting near-miss at `run.cmd:107-112`: normalising the default log path with
  `for %%I in ("%HERE%..\..\_main")` was **tried and rejected** because "cmd mangles the
  quoted argument and the run then wrote no log at all."
- **`%*` is expanded unquoted** at `run.cmd:57,66,84,101,104,110`. This is standard cmd
  behaviour (`%*` carries the caller's own quoting), and every consumer
  (`--check-args`, `--log`, the `for %%A` scans) tolerates token splitting. No path the app
  passes through `%*` contains a space.
- **Inline PowerShell `-Command` quoting is fragile** and the repo documents it as a
  measured *blindness*, not a space bug: `app/electron/_hotreload/acceptance.py:147-149`
  ("passing it inline was measured blind, because argv quoting mangles the embedded
  quotes") and `_main/runcmd-entry-driver.py:217`. `_main/_probe/console-census.py:102-105`
  is the remaining inline `-Command` caller — but my measurement showed it *does* return
  bytes under `CREATE_NO_WINDOW` alone (4040 B), so its blindness comes from
  `DETACHED_PROCESS` (landmine 2), not from quoting.

### Verdict

**No occurrence of the landmine bites.** Every path crosses a process boundary as a list
element. The two real hazards the repo hit are (a) cmd mangling a quoted path inside a
`for` expansion (`run.cmd:107-112`, avoided) and (b) inline PowerShell `-Command` quoting
(`acceptance.py:147`), which the repo routes through `.ps1` files instead.

---

## Landmine 6 — `subprocess.run(timeout=)` is not a time ceiling on Windows

The Windows reality: a timeout raises `TimeoutExpired`, but (a) terminating kills only the
**direct** child, not its tree, and (b) `run()`'s post-timeout pipe drain can still block
if a grandchild holds the handle. A bare `Popen.wait(timeout=…)` with no handler does not
kill anything at all — on timeout the exception propagates and the child is left running.

### Occurrences

| file:line | pattern | ceiling? |
|---|---|---|
| `_main/verdict-order-oracle.py:164-167` | `wait(timeout=…)` → `except TimeoutExpired: proc.kill(); proc.wait()` | **correct** (the model pattern) |
| `_main/panel-startup-flash-census.py:358-361` | same shape | correct |
| `_main/measure-asr-warmup.py:74-77` | `terminate(); wait(timeout=10)` / `kill()` | correct |
| `_main/measure-readiness.py:92-95` | `wait(timeout=10)` / `kill()` | correct |
| `_main/_probe/psdiag.py:50-58` | `subprocess.run(..., timeout=90)` in a `try` with `TimeoutExpired` recorded | correct |
| **`_main/device-silence-oracle.py:71`** | `rc = proc.wait(timeout=400)` — **no handler** | **NOT a ceiling** — on timeout the worker is orphaned, the `.out`/`.err` handles never close |
| **`_main/panel-exit3-oracle.py:160`** | `rc = proc.wait(timeout=400)` — no handler | **NOT a ceiling** (app orphaned on timeout) |
| **`_main/panel-startup-visibility-oracle.py:386`** | `rc = proc.wait(timeout=400)` — no handler | **NOT a ceiling** |
| **`_main/run-live-hidden.py:71`** | `rc = proc.wait(timeout=300)` — no handler; and `DETACHED_PROCESS` defined at `:25` but **unused** | **NOT a ceiling** — a hung worker stays alive |
| `_main/_armE-window-census.py:136` | `rc = proc.wait()` — no timeout | no ceiling by design |
| `_main/_run-hidden.py:24` | `subprocess.run(..., timeout=120)` on `electron.exe` | **suspected bite** — electron spawns renderer/gpu/utility children (`sotto_webview.py:2325-2329` documents that electron's tree is multi-level); a hung child holding the pipe can defeat the timeout. Not verified (I may not launch electron) |
| `_main/gpu-diag.py:37-39` | `subprocess.run(..., timeout=20)` on `nvidia-smi` | single child, fine |
| `_main/native_imports.py:34-37` | `subprocess.run(..., timeout=45)` on `python -c` | single child, fine |
| `_main/lang-id-runs.py:57`, `_main/lang-id-default-arms.py:46` | `subprocess.run(..., timeout=900/1200)` on the worker | single child, fine in the common case |
| `_main/panel-exit3-oracle.py:699,771`, `_main/_ppv-census-driver.py:40` | `subprocess.run(..., timeout=…)` | single child, fine |
| `_main/runcmd-entry-driver.py:172-174` | `subprocess.run(taskkill…, timeout=30)` | fine |

### Verdict

**Bites in three oracles** (`device-silence-oracle.py:71`, `panel-exit3-oracle.py:160`,
`panel-startup-visibility-oracle.py:386`) where `wait(timeout=…)` is used with **no
handler**: a child that outlives the ceiling is left running (an orphan) and its file
handles are never closed. The `subprocess.run(timeout=)` sites on single children are
acceptable; `_main/_run-hidden.py:24` on the multi-process `electron.exe` is the one place
where the timeout is plausibly **not** a ceiling (unverified — see below).

---

## Summary — what bites

| # | landmine | verdict | the occurrence(s) that matter |
|---|---|---|---|
| 1 | `pythonw` / `argparse` into a void | **contained** | `run.cmd:83-92` + `sotto_webview.py:2462` fix it; `_main/gpu-diag.py:2-3` documents the residual trap |
| 2 | `CREATE_NO_WINDOW`+`DETACHED` empty channel | **BITES (proven by live run)** | `_main/_probe/console-census.py:102-106` |
| 3 | `taskkill` truncating a log | **partly** | buffered-tail loss **not reproduced**; the "no graceful shutdown" half is real and documented (`HOTRELOAD.md:326-330`); the codepage half is real and fixed (`runcmd-entry-driver.py:168-170`) |
| 4 | `conhost` window from a console child | **contained in the app** | `run.cmd` uses `pythonw`; `sotto_webview.py:1943`/`worker-bridge.js:488` suppress the window |
| 5 | paths with spaces | **no bite** | all boundaries use list argv; two near-misses documented (`run.cmd:107-112`, `acceptance.py:147`) |
| 6 | `subprocess.run(timeout=)` not a ceiling | **BITES in 3 oracles** | `device-silence-oracle.py:71`, `panel-exit3-oracle.py:160`, `panel-startup-visibility-oracle.py:386` |

### Findings requiring an edit (NOT made — READ-ONLY)

- **F1** `_main/_probe/console-census.py:106` — `creationflags=0x08000000 | 0x00000008`
  blanks the channel; drop `DETACHED_PROCESS` (use `CREATE_NO_WINDOW` alone) so
  `python_pids()` can see anything. Highest-confidence finding.
- **F2** `_main/device-silence-oracle.py:71`, `_main/panel-exit3-oracle.py:160`,
  `_main/panel-startup-visibility-oracle.py:386` — wrap `wait(timeout=…)` in
  `try/except TimeoutExpired` and `kill()` on timeout (copy `verdict-order-oracle.py:164-167`).
- **F3** `_main/run-live-hidden.py:71` — same missing `except`; and `DETACHED_PROCESS`
  at `:25` is a dead constant (never referenced).
- **F4** `_main/_run-hidden.py:24` — `subprocess.run(timeout=)` around the multi-process
  `electron.exe` may not be a ceiling; needs a tree-kill on timeout (pattern of F2).

---

## What I could NOT verify, and why

1. **Landmine 3 "buffered tail truncated": not reproduced.** My controlled runs (Python
   file, Python pipe, Node pipe) all preserved the killed child's unflushed bytes. If the
   house's original repro used a different writer (a C console program, or `cmd.exe`), I did
   not reproduce that case. The in-repo *measured* taskkill failures are the will-quit skip
   and the OEM-codepage decode `stdout=None`.
2. **`app/electron/_hotreload/acceptance.py:522` taskkill output.** `report.json` shows
   `taskkill_out: ""` while my run of `taskkill` under the same `CREATE_NO_WINDOW |
   DETACHED_PROCESS` flags returned a non-empty message. I did not re-run the acceptance
   (it launches Electron). The empty string is unexplained — possibly the app exited
   cleanly so `taskkill` reported nothing useful, possibly the archive elided it.
3. **`_main/_run-hidden.py:24` electron timeout.** Not tested — I may not launch the app or
   a browser. The reasoning is from `sotto_webview.py:2325-2329` (electron has a multi-level
   child tree) plus the documented libuv/`CreateProcess` semantics; this is `[INFERENCE]`.
4. **Landmine 1 under `pythonw` end-to-end** — I did not launch `pythonw`; I read
   `_pwtest3.json`, which is the repo's own measurement of exactly that.
5. **`app/src-tauri/` (Rust) and `app/verify/`.** Grep found no process spawn, console
   call, or `Command::new` in the Rust tree, and `AGENTS.md:16-20` states the Tauri tree
   "cannot be built on this host"; I did not compile it. Not audited beyond grep.
6. **The live app (pid 30848).** Not queried, killed, or restarted.

---

## Appendix — the two live runs (verbatim)

**Landmine 2 reproduction** (windowless; my process spawned with `CREATE_NO_WINDOW` only):

```
CNW_only   : rc=0 bytes=4040 stderr=0 ms=535 head='12536|pythonw.exe|"I:\\!produtos202608\\BrandOps\\dashboard\\backend\\.venv\\Scripts\\p'
CNW|DET    : rc=0 bytes=0    stderr=0 ms=76  head=''
DET_only   : rc=0 bytes=0    stderr=0 ms=63  head=''
```

**Landmine 3 reproduction:**

```
taskkill CNW: rc=128 out='ERRO: o processo "999999" nÆo foi encontrado.'
taskkill CNW|DET: rc=128 out='ERRO: o processo "999999" não foi encontrado.'
node present: True
file 200B while alive: 200
pipe after kill bytes: 200
node->PIPE after taskkill /F bytes: 50
```

---

## SELF-AUDIT

- **protocolos em falta** — I did not read the manager-side law the house measured for the
  "taskkill truncates a log" landmine (it lives under `I:/!manager`, outside this read-only
  `H:/sotto` mandate), so I characterised it from first principles + the sotto docs rather
  than from the house's own repro. If that repro exists, F-per-landmine-3 should be re-cut
  against it. What I would do differently: search `I:/!manager/scripts` and
  `I:/!manager/state` for the taskkill entry **first**, before running my own probe.
- **verificação adicional** — the cheap check that raises confidence on the highest-value
  finding: run `console-census.py --list` and observe that `python_pids()` prints **zero**
  rows while this session's own `python.exe`/`pythonw.exe` are running. Cost: one ~5 s
  windowless run. Not run here because the deliverable was already proven by direct
  reproduction of the exact call.
- **checkboxes novas (mecanicas)** —
  1. `grep -rn "0x08000000 *| *0x00000008\|CREATE_NO_WINDOW *| *DETACHED_PROCESS" <repo>`
     must return **only** call sites whose `subprocess.run/Popen` do **not** capture a pipe
     (allow-listed by a inline comment). Input that leaves it RED: a newly added call that
     both sets the combo and passes `capture_output=True`/`stdout=PIPE` and consumes the
     value.
  2. For every `\.wait\(timeout=` in `**/*.py`: the enclosing block MUST contain
     `except subprocess.TimeoutExpired` and a `.kill()` in the handler. RED input:
     `device-silence-oracle.py:71` as it stands today.
- **review por outro subagente** — **sim-com-escopo**: the two live measurements (landmine 2
  and landmine 3) and the F1–F4 finding lines. A second worker should re-run my
  `CREATE_NO_WINDOW|DETACHED` reproduction on `console-census.py`'s exact argv and confirm
  0 bytes, then confirm F1 by running `console-census.py --list` and checking it prints no
  rows.
- **gate-doubt**
  - **verde-de-verdade:** the only "green" I relied on is `preflight.json`'s
    `control_is_red: true` (node syntax gate). That green is real and not vacuous — the
    negative control produced `rc=1` and 232 B of `SyntaxError` stderr; a gate that could
    not go red would have shown rc 0/empty. My own measurement (landmine 2) is the
    counter-case that makes that green *specific to node*, not general.
  - **falta-no-gate:** the repo's window census and my audit both key on **process names and
    flags**; none of them checks that a *captured* `subprocess` returned non-empty when the
    caller needed a value. A future change that adds `CREATE_NO_WINDOW|DETACHED_PROCESS` to
    a capturing call would pass every existing gate. Named scenario: someone "fixing" a
    window warning by adding `DETACHED_PROCESS` to `run-cmd-exit-oracle.py:272`, which would
    silently blank the `taskkill` receipt the oracle prints.
  - **gate-melhor:** `python - <<EOF` walking every `.py` under `H:/sotto`, asserting that no
    AST `Call` has both a `creationflags=` kw whose value mentions `0x8`/`DETACHED` **and** a
    truthy `capture_output`/`stdout=subprocess.PIPE` kw. RED input: `console-census.py`
    today; also any PR that re-introduces the combo on a capturing call. (This is a static
    gate; it does not need to launch anything.)
- **confianca** — **alta** for landmine 2 (directly reproduced), landmine 5 (grep-complete)
  and landmine 6's missing-except sites (read directly). **media** for landmine 1
  (relies on `_pwtest3.json`, the repo's own measurement) and landmine 4 (contained by
  construction, not by a run). **baixa** for landmine 3's "buffered tail" half (did not
  reproduce) and for `_run-hidden.py:24` electron timeout (`[INFERENCE]`). What would move
  landmine 3 to alta: the house's original repro command.
- **não verificado** — (1) the house's taskkill-truncation repro; (2) the acceptance
  `taskkill_out: ""` discrepancy; (3) `_run-hidden.py` electron timeout under a hung child;
  (4) Rust `src-tauri` beyond grep; (5) the live app pid 30848 (deliberately untouched).

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: AuditWindowsLandmines
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditWindowsLandmines.jsonl
- cache: read=5338240 write=0 hit=96.6964% (cache-read / input+cache-read); universe: 47 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditWindowsLandmines.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=40 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; o...
- when-failed: break_items=1; WHEN=2026-10-06T08:24:35.111000+00:00 | break_items=1; WHEN=2026-10-06T08:24:37.355000+00:00 | break_items=1; WHEN=2026-10-06T08:24:38.769000+00:00 | break_items=3; WHEN=2026-10-06T08:24:40.623000+00:00 | break_items=2; WHEN=2026-10-06T08:26:26.242000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 113472 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditWindowsLandmines']; window: 2026-10-06T08:24:35.111000+00:00..2026-10-06T08:26:26.242000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11050-0fed-77ae-b5f0-9604776a1494 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275075111 | session_id=01a11050-0fed-77ae-b5f0-9604776a1494 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275077355 | session_id=01a11050-0fed-77ae-b5f0-9604776a1494 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791275078769 | session_id=01a11050-0fed-77ae-b5f0-9604776a1494 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275080623 | session_id=01a11050-0fed-77ae-b5f0-9604776a1494 provider=deepseek-flash model=deepseek-flash item_index=122; turn_id=1791275186242 (state=RESOLVED-BREAKS-OMP; population: 5 of 113472 OMP prefix-ledg...
- report generated_at: 2026-10-06T08:29:07.868702+00:00
- usage rows: 47
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 182378
- output tokens: 33475
- cache-read tokens: 5338240
- cache-write tokens: 0
- hit ratio: 96.6964% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 5 of 113472 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditWindowsLandmines']; window: 2026-10-06T08:24:35.111000+00:00..2026-10-06T08:26:26.242000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
