# run.cmd launch-entry gaps G1–G4 — FIXED, each asserted before/after

axis: launch entry · lane: `SottoRunCmdGaps` · date: 2026-10-06
Source of the four gaps: `docs/audit/launch-entry.md` §2 (lane `AuditLaunchEntry`).
This file is the closing receipt: the four gaps are FIXED in the code, and the
oracle `_main/run-cmd-exit-oracle.py` now asserts each one as a BEFORE/AFTER
pair — every gap arm runs twice, against a copy of the tree whose shell AND
wrapper are the saved pre-fix bytes (BEFORE) and against the live tree (AFTER),
every other file identical.

| artefact | sha256 |
|---|---|
| `app/webview/sotto_webview.py` (fixed) | `f8b1de2acd3f0ca6b4ed73bd4fcdf57d49255d12e5ae2526592843e16873545e` |
| `app/webview/run.cmd` (fixed) | `8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b` |
| `_main/sotto-webview-prefix-20261006.py` (pre-fix shell, saved before editing) | `45f37917d3e49f8cb92ecc39cc2695832ff84899f9e5164969b498e4c7a3da03` |
| `_main/run-cmd-prefix-20261006.cmd` (pre-fix wrapper, from the earlier lane) | `b9c08fecb94f8031d40bf88a37d49c9e1a0c44167e711ad1344a8dac6f8add6e` |
| `_main/run-cmd-exit-oracle.py` (extended) | `5f43d7f296488c27ff87f41dc5aec9330e1be1a8e077f2857ff1b967de4ae5cb` |

Run of record: `py -3 _main/run-cmd-exit-oracle.py --label gapfix4` →
`VERDICT PASS` (receipt `_main/run-cmd-exit-oracle-gapfix4.json`).

---

## The four fixes

### G1 — a missing panel reported 0 (`run.cmd` exited 0 while the app exits 3)

`--check-args` USED to `return 0` before the panel-existence check further down
`main()`. The pre-flight therefore validated the argv and nothing else, and with
`app/electron/panel.html` absent a normal launch was `start`ed: the app logged
`PANEL_MISSING` and exited **3**, and `run.cmd` had already answered **0**.

Fix — `sotto_webview.py:2527-2533`: the pre-flight now asserts the panel file
before it returns, and refuses with the SAME status a real launch would exit
with (`return 3`), through `_preflight_refuse` (`sotto_webview.py:2477`) so the
reason is both printed (a console run) and mirrored to `--log` when the caller
gave one. Nothing is opened and nothing is started: only the file is stat()ed.

### G2 — a missing `pywebview` reported 0

`import webview` is late (`main()` imports it just before `webview.start()`,
and `create_window()` imports it to load the WinForms assemblies). An
`ImportError` there exited the process **1** — after `run.cmd` had already
answered 0.

Fix — `sotto_webview.py:2537-2544`: `--check-args` now imports `webview` itself,
where the wrapper is still listening, and refuses with `return 1`. The late
import is kept for the real launch path (it must not run before the UI loop
exists); the check only proves it resolves.

### G3 — a hang reported 0

The measured hang (launch-entry.md §3/§4): the shell logged `STAGING_LOADED`,
its `load_url(panel)` never came back, there was no `PRELOAD_ACTIVE` — and
`run.cmd` still answered 0, because `start` detaches the app and the wrapper
never saw anything after the spawn.

Fix — a bounded readiness handshake, both halves windowless:

* `sotto_webview.py:2459` — hidden `--ready-file PATH`; the shell **touches that
  file** the moment the panel navigation has completed
  (`mark_launch_ready`, `sotto_webview.py:253`, called at `:1294`, immediately
  after `PRELOAD_ACTIVE` — exactly the boundary the hang never crossed).
* `sotto_webview.py:2464` — hidden `--wait-ready PATH` mode; the wrapper calls it
  and it polls, bounded, for that file: **0 = up, 4 = HANG**
  (`wait_ready_file`, `sotto_webview.py:279`, bound from `SOTTO_READY_BOUND`,
  default 30 s).
* `run.cmd:131-166` — a FRESH `ready-<r>-<r>.txt` per launch is handed to the
  app (`--ready-file`, `run.cmd:149/155`), the app is `start`ed as before, and
  `run.cmd:159` calls `--wait-ready`. On timeout it echoes the refusal and
  exits **4**, writing `sotto: HANG rc=4 by=run.cmd-readiness` to the run log
  (`run.cmd:165`).

It still does NOT wait for the app to EXIT: the app is meant to sit hidden for
days; only the readiness handshake is bounded. Measured: a normal launch returns
in ~2.0–2.5 s (`wrapper_ms=2472`/`2033` below) while the app lives its full 8 s.

Consequence handled: `--check-args` had been a hidden no-op that started the app
(it returned 0 having opened nothing). With the readiness wait, that run would
have looked like a HANG. `run.cmd:80-124` now treats the pre-flight switch as
the REQUESTED action — it runs the pre-flight and exits with its status,
starting nothing.

### G4 — the `pythonw` → `python.exe` fallback put a console on the screen

`run.cmd` used to run `if not exist "%PYW%" set "PYW=%PYEXE%"`: with
`pythonw.exe` absent, the app was launched under `python.exe` — a CONSOLE
binary, i.e. a console WINDOW on the owner's screen (the owner has said three
times that must never happen).

Fix — `run.cmd:61-76`: the fallback line is DELETED. A missing `pythonw.exe` is
now a loud, windowless refusal that names the console it refuses to open and
exits **3**.

### The receipt token, renamed

The wrapper's refusal receipt was `ARGS_REJECTED`, which no longer describes the
event now that the pre-flight refuses a missing panel / missing pywebview too.
It is now `sotto: PREFLIGHT_REFUSED rc=N by=run.cmd-preflight`
(`run.cmd:116`); the oracle follows (`PREFLIGHT_REFUSED_RE`).

---

## Before/after, per gap (from the run of record)

| gap | AFTER (fixed) | BEFORE (pre-fix bytes) | the BEFORE failure was real |
|---|---|---|---|
| G1 panel-absent | **rc=3**, nothing started | **rc=0** | the BEFORE copy's own app log carries `PANEL_MISSING` — the app exited 3 and the wrapper said 0 |
| G2 pywebview-absent | **rc=1**, nothing started | **rc=0** | the pre-fix shell exits **1** measured directly, and under the pre-fix wrapper it started anyway (first log line present) |
| G3 hang | **rc=4** after the bounded wait, HANG receipt written | **rc=0** | the same stub logged `STAGING_LOADED` and never came up |
| G4 console-fallback | **rc=3**, names the refusal, no fallback line as ACTIVE code | **rc=0** | the pre-fix wrapper still carries `if not exist "%PYW%" set "PYW=%PYEXE%"` and proceeded past the missing pythonw |

`py_compile rc=0` is not offered as evidence for anything.

---

## The oracle output, verbatim

```
$ py -3 _main/run-cmd-exit-oracle.py --label gapfix4
RUN-CMD EXIT ORACLE label=gapfix4 pid=34352
RUN-CMD run_cmd=H:\sotto\app\webview\run.cmd
RUN-CMD run_cmd_sha256=8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b
RUN-CMD under_test_sha256=8951e69c3b758fb05b9ca4a17f35a27b0556c6042e65d7ec232994e0bb5d367b (the live wrapper; equal means "the fix is under test")
RUN-CMD preflight_in_under_test=True
RUN-CMD shell_sha256=f8b1de2acd3f0ca6b4ed73bd4fcdf57d49255d12e5ae2526592843e16873545e shell_mtime=1791276082
ARM argv          rc=0 want=0 ms=0 PASS
    [ok] ['no args (double-click)'] -> accepted by the pre-flight :: rc=0 argv=[]
    [ok] ['README.md: --show --with-worker'] -> accepted by the pre-flight :: rc=0 argv=['--show', '--with-worker']
    [ok] ['webview-app-20261006.md: --selftest --log'] -> accepted by the pre-flight :: rc=0 argv=['--selftest', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-055017.log']
    [ok] ['webview-app-20261006.md: --exit-after 25'] -> accepted by the pre-flight :: rc=0 argv=['--exit-after', '25']
    [ok] ['runcmd-entry-driver.py ARM caption'] -> accepted by the pre-flight :: rc=0 argv=['--with-worker', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-055017.log', '--no-hotkey', '--no-hot-reload', '--exit-after', '60']
    [ok] ['the --dump-dom measurement path'] -> accepted by the pre-flight :: rc=0 argv=['--dump-dom', '--log', 'H:\\sotto\\_main\\_runcmd-argv-arm-055017.log']
    [ok] ['the --memory / --opaque flags'] -> accepted by the pre-flight :: rc=0 argv=['--memory']
    [ok] ['the --memory / --opaque flags'] -> accepted by the pre-flight :: rc=0 argv=['--opaque']
ARM bogus         rc=2 want=2 ms=345 PASS
    [ok] rc == 2 (the child's own argparse status, passed through) :: rc=2
    [ok] the wrapper says so on its own console :: run.cmd: the shell REFUSED this launch (rc=2). Nothing was started.
    [ok] a receipt line is appended to the run log (before the fix this arm appended NO bytes at all) :: 'sotto: PREFLIGHT_REFUSED rc=2 by=run.cmd-preflight'
    [ok] nothing was started: no `shell=webview2` line appended :: appended_bytes=52
    [ok] no process is left behind in this tree :: leftovers=[]
ARM help          rc=0 want=0 ms=306 PASS
    [ok] rc == 0 :: rc=0
    [ok] the console interpreter printed the usage header :: ['usage: sotto-webview [-h] [--show] [--hotkey HOTKEY] [--no-hotkey]']
    [ok] every flag the shell declares is in the usage (17/17) :: none missing
    [ok] the pre-flight switch stays OUT of --help :: hidden
    [ok] no process is left behind in this tree :: leftovers=[]
ARM start-logged  rc=0 want=0 ms=2472 PASS pid=16516
    [ok] rc == 0 :: rc=0
    [ok] the wrapper returned BEFORE the app exited (the wait is the bounded READINESS handshake, not the 8.0s lifetime) :: wrapper_ms=2472 app_lives=8.0s
    [ok] the app's OWN first line is in the run log, with its pid :: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=16516
    [ok] the published pid (16516) was a real, running process :: pid=16516 alive=True
    [ok] the app reached its own clean exit (SHELL_EXIT line) :: SHELL_EXIT rc=0
    [ok] the READINESS boundary (PRELOAD_ACTIVE -- what the G3 handshake keys on) was crossed in the log :: PRELOAD_ACTIVE hasSotto=true
    [ok] no leftover: the published pid is gone :: pid=16516 gone=True 
ARM start-default rc=0 want=0 ms=2033 PASS pid=37360
    [ok] rc == 0 :: rc=0
    [ok] the wrapper returned BEFORE the app exited (the wait is the bounded READINESS handshake, not the 8.0s lifetime) :: wrapper_ms=2033 app_lives=8.0s
    [ok] the app's OWN first line is in the run log, with its pid :: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=37360
    [ok] the published pid (37360) was a real, running process :: pid=37360 alive=True
    [ok] the app reached its own clean exit (SHELL_EXIT line) :: SHELL_EXIT rc=0
    [ok] the READINESS boundary (PRELOAD_ACTIVE -- what the G3 handshake keys on) was crossed in the log :: PRELOAD_ACTIVE hasSotto=true
    [ok] no leftover: the published pid is gone :: pid=37360 gone=True 
GAPS the before/after pairs of docs/audit/launch-entry.md §2 (BEFORE = a copy whose shell+wrapper are the pre-fix bytes)
GAP G1 panel-absent        PASS want=non-zero (3); before=0
  after  rc=3 ms=428 args=['--show']
  before rc=0 ms=281 args=['--show']
    [ok] AFTER: run.cmd REFUSES the launch (non-zero) :: rc=3
    [ok] AFTER: the refusal is rc 3 -- the SAME status the app exits with :: rc=3 want=3 stdout='sotto: PANEL_MISSING path=H:\\sotto\\_main\\_gaps-g1-after-6g_3ezt_\\app\\electron\\panel.html\nrun.cmd: the shell REFUSED this launch (rc=3). Nothing was started.\nrun'
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=52
    [ok] BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS :: rc=0
    [ok] BEFORE: the app really did fail (its own log carries PANEL_MISSING) :: ['sotto: PANEL_MISSING path=H:\\sotto\\_main\\_gaps-g1-before-czgf5mrg\\app\\electron\\panel.html']
GAP G2 pywebview-absent    PASS want=non-zero (1); before=0
  after  rc=1 ms=355 args=['--show']
  before rc=0 ms=226 args=['--show']
    [ok] AFTER: run.cmd REFUSES the launch (non-zero) :: rc=1
    [ok] AFTER: the refusal is rc 1 -- the status the app would exit with :: rc=1 want=1 stdout='sotto: PYWEBVIEW_IMPORT_FAILED ImportError: pywebview is not installed (gaps oracle G2)\nrun.cmd: the shell REFUSED this launch (rc=1). Nothing was started.\nrun.'
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=52
    [ok] BEFORE: the pre-fix wrapper answered 0 -- the failure AS SUCCESS :: rc=0
    [ok] BEFORE: the app started anyway (pre-fix shell logged its first line) :: ['sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=32388']
    [ok] BEFORE: the PRE-FIX SHELL exits 1 with no pywebview (measured direct) :: rc=1 err_tail=['ImportError: pywebview is not installed (gaps oracle G2)']
GAP G3 hang                PASS want=non-zero (4); before=0
  after  rc=4 ms=5391 args=['--show']
  before rc=0 ms=165 args=['--show']
    [ok] AFTER: run.cmd reports a HANG -- rc 4, not 0 :: rc=4 want=4 ms=5391
    [ok] AFTER: the wrapper wrote its OWN HANG receipt to the run log :: ['sotto: HANG rc=4 by=run.cmd-readiness']
    [ok] AFTER: the app really had been started and never came up (STAGING_LOADED, no ready file, no PRELOAD_ACTIVE) :: ['sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)']
    [ok] BEFORE: the pre-fix wrapper answered 0 for the SAME hang :: rc=0
    [ok] BEFORE: the same stub had been started and never came up :: ['sotto: STAGING_LOADED core=yes -> navigating to panel (G3 STUB never-ready)']
GAP G4 console-fallback    PASS want=non-zero (3); before=0
  after  rc=3 ms=92 args=['--show']
  before rc=0 ms=105 args=['--show']
    [ok] AFTER: run.cmd exits 3 when pythonw.exe is absent :: rc=3 want=3 ms=92
    [ok] AFTER: it NAMES the refusal, so the owner is not left guessing :: ['run.cmd: no pythonw.exe beside H:\\sotto\\_main\\_gaps-g4-after-3e6n4o91\\fakepy\\python.exe.', 'run.cmd: refusing to fall back to python.exe -- that opens a console window.']
    [ok] AFTER: nothing was started (no shell line in this copy's log) :: log_bytes=0
    [ok] AFTER: the fallback assignment is GONE from the wrapper under test (checked on the ACTIVE lines -- a REM quoting it does not count) :: absent
    [ok] BEFORE: the pre-fix wrapper still carries the console fallback :: present (the defect)
    [ok] BEFORE: it proceeded past the missing pythonw and answered 0 :: rc=0
CENSUS cadence_ms=100 samples=260 visible_samples=0 tracked_pids=86
CENSUS-GAPS samples=71 visible_samples=0 (the gap phase, where a window is the DEFECT being demonstrated)
CENSUS OK: no visible window in 260 samples of this run's own pids during the ARMS phase (the census primitives are the repo's)
ARM-VERDICT    PASS  all 4 arms green
GAP-VERDICT    PASS  all 4 gaps green (AFTER non-zero, BEFORE 0)
CENSUS-VERDICT PASS  260 samples, 0 with a visible window
ARM-RCS bogus=2(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)
GAP-RCS G1 panel-absent        after=3 before=0
GAP-RCS G2 pywebview-absent    after=1 before=0
GAP-RCS G3 hang                after=4 before=0
GAP-RCS G4 console-fallback    after=3 before=0
VERDICT PASS  all conjuncts green
RECEIPT H:\sotto\_main\run-cmd-exit-oracle-gapfix4.json
```

### How the BEFORE arm is built (and why it cannot go vacuous)

`gap_pair()` in the oracle builds two copies under `_main\_gaps-*`: AFTER = the
live shell + live wrapper; BEFORE = `sotto-webview-prefix-20261006.py` +
`run-cmd-prefix-20261006.cmd` (both hashed above), every other file copied from
the tree under test. The G4 arm asserts the BEFORE file still CONTAINS the
fallback line (`present (the defect)`) and the AFTER file does not carry it as
ACTIVE code — so a control that stopped being a control fails the arm instead of
reporting a green it did not earn. Each arm's lever:

| gap | lever in the copy | env |
|---|---|---|
| G1 | `app/electron/panel.html` not written | — |
| G2 | a `webview.py` that raises ImportError shadowed on `PYTHONPATH` | `PYTHONPATH` |
| G3 | the shell replaced by a stub that logs `STAGING_LOADED` and never touches the ready file | `SOTTO_READY_BOUND=5` |
| G4 | `py` shadowed to resolve a fake `python.exe` (a copy of `where.exe`) with NO `pythonw.exe` beside it | `PATH` |

## Scope / limits (stated, not hidden)

* G3's readiness point is the completed panel navigation (`PRELOAD_ACTIVE`),
  i.e. exactly the boundary the measured hang never crossed. A launch that
  stages the panel and THEN dies of something else (e.g. the bridge gate, exit
  3) is still reported 0 by the wrapper — the app is detached and the wrapper
  deliberately does not wait for its exit. That is a separate, unaddressed
  failure mode, not one of G1–G4.
* On G3 timeout the wrapper reports and exits 4; it does NOT kill the app. It
  cannot name the pid (`start` does not return one, and this box forbids
  `taskkill` by image name / has no `wmic`). The oracle kills its own stubs by
  the pid in the app's own log line.
* `SOTTO_READY_BOUND` (default 30 s) is the only knob; it exists so a test can
  shorten the wait, and it changes the bound, never the flag table.
* `--help`, `--dump-dom`, `--selftest`, `--memory` still run under `python.exe`
  (they PRINT, into the console the caller already has) and skip the readiness
  handshake — by design, unchanged.
* The census RED seen in one earlier run of this oracle (`Sotto` window, n=2) is
  the app's own startup flash — a pre-existing, separately-owned defect
  (`_main/SottoStartupFlash.md`), independent of this lane and not reproducible
  in the run of record (0 visible in 260 samples).

---

## SELF-AUDIT

* **protocolos em falta** — one, and it cost a diagnosis cycle: I shipped the
  G3 arm before mirroring the shell's `--wait-ready` MODE in the stub. The stub
  is called by run.cmd for BOTH halves of the handshake, so a stub that only
  answers `--check-args` slept 600 s inside the wrapper and the arm died on the
  120 s timeout (measured, `_gaps-g3-after-3rxgv30z`). The protocol I should have
  had up front: *before writing a stand-in for a program, list every MODE the
  caller invokes it in.* The rule now lives in the stub's own comment.
* **verificacao adicional** — the cheap one I ran after the fact and would make
  mandatory: enumerate the processes whose COMMAND LINE names my temp copies, to
  find the orphan the timeout left (pid 18104, `pythonw … --wait-ready`). It was
  found with a read-only ctypes command-line reader, killed by exact pid, and its
  directory then deleted. Cost ≈ 3 commands. A harness tool that did this
  directly would have made the `process_census` "1 blocked process" row
  actionable instead of a name I had to chase.
* **checkboxes novas** (mechanical, never "be more careful"):
  1. For any oracle arm that starts a DETACHED child: after the arm, assert the
     arm's own log region was read AFTER waiting for the child's expected line —
     a bare `text_of()` right after `run_wrapper` is a read race (this bit G3's
     BEFORE check once: `[]`).
  2. For any "the line is gone from the file" assertion, assert it against
     NON-REM lines only. `grep -c '^set "PYW=%PYEXE%"'` vs
     `grep -c 'set "PYW=%PYEXE%"'` — the second matched the REM that explains
     the removal.
  3. After any run that `start`s a copy of the tree, `ls _main/_gaps-* / rm -rf`
     must succeed: a directory that cannot be removed is a live process whose cwd
     is it — an orphan, even when its window is invisible.
* **review por outro subagente** — **sim-com-escopo**: re-derive the BEFORE
  readings from the two prefix files and the receipt JSON alone, and try to make
  any gap arm report BEFORE != 0 (i.e. make the control vacuous). Do NOT re-run
  the census phase (it starts the real app).
* **gate-doubt**:
  - *verde-de-verdade:* every green here is a real process status, not a
    swallowed one. `ARM-RCS`/`GAP-RCS` are `subprocess` returncodes of `cmd /c`,
    and each gap arm carries a SECOND, independent observation of the same
    event (the app's own log line, or a direct run of the pre-fix shell). The
    one green I do NOT fully trust: **G4's AFTER check that "nothing was
    started"** rests on `log_bytes=0` — true, but vacuous on its own (a log that
    was never opened is also empty), which is why the arm ALSO carries the
    stdout naming the refusal and the active-line absence of the fallback. The
    CENSUS green is real but phase-scoped: it is 260 samples of the ARMS phase,
    and the census correctly reported 0 in the gap phase too — so a console
    window from the G4 BEFORE arm was NOT observed this time (the `where.exe`
    window is shorter than the 100 ms cadence). I do not claim that observation.
  - *falta-no-gate:* the oracle verifies that G1–G4 are CLOSED, and does not
    verify that no OTHER post-spawn failure still answers 0. A future change
    walks straight through this: an app that stages the panel and then exits 3
    (bridge-gate-red, `sotto_webview.py:1773`) still leaves `run.cmd` at 0.
    Also uncovered: `--dump-dom/--selftest/--memory` paths never reach the
    pre-flight or the handshake, so a regression there is invisible to every arm.
  - *gate-melhor:* a check that closes the first hole: assert the READINESS
    moment is *durable* — extend the G3 arm with a second stub that touches the
    ready file and THEN exits 3, and require `run.cmd` to report that exit.
    Input that must leave it RED (today it would): stub writes the ready file,
    `request_exit(3)`, `run.cmd --show` → the wrapper returns 0. That is the
    next gap in this family, and it needs a deliberate decision (a bounded
    post-ready observation window) that this brief did not ask for.
* **confianca** — **alta** for G1/G2/G4 (each is a `file:line` return-value or
  assignment change, asserted on both colours with a second observation per
  arm). **alta** for G3's rc contract (measured 4 on the stub, 0 on a healthy
  launch with the readiness boundary crossed). **media** for G3's readiness
  POINT being the right one in the field: it is exactly the boundary the
  measured hang failed to cross, but it was chosen from the audit's evidence,
  not from a fresh live hang. What would raise it: one instrumented live launch
  of the real app with `SOTTO_READY_BOUND=5`.
* **nao verificado** —
  1. No live G3 hang of the REAL app was produced (the hang is a third, unnamed
     cause per launch-entry.md §4; the arm uses a stub that reproduces the
     measured shape).
  2. The G4 console window was not observed by the census in the run of record
     (below cadence); the arm asserts the refusal and the absence of the
     fallback line instead.
  3. No non-Windows host and no machine without `py -3` was exercised.
  4. The `--dump-dom`/`--selftest`/`--memory` (python.exe) paths were not
     re-measured — they are untouched by these edits and are only asserted as
     `--check-args` argv sets.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoRunCmdGaps
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoRunCmdGaps.jsonl
- cache: read=15032320 write=0 hit=98.4517% (cache-read / input+cache-read); universe: 85 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoRunCmdGaps.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=78 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; o...
- when-failed: break_items=1; WHEN=2026-10-06T08:36:19.751000+00:00 | break_items=1; WHEN=2026-10-06T08:36:20.509000+00:00 | break_items=1; WHEN=2026-10-06T08:36:21.352000+00:00 | break_items=3; WHEN=2026-10-06T08:36:22.031000+00:00 | break_items=2; WHEN=2026-10-06T08:38:52.566000+00:00 | break_items=2; WHEN=2026-10-06T08:43:18.185000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 114092 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoRunCmdGaps']; window: 2026-10-06T08:36:19.751000+00:00..2026-10-06T08:43:18.185000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275779751 | session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275780509 | session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791275781352 | session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275782031 | session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-flash model=deepseek-flash item_index=50; turn_id=1791275932566 | session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-...
- report generated_at: 2026-10-06T08:51:33.472026+00:00
- usage rows: 85
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 236411
- output tokens: 100530
- cache-read tokens: 15032320
- cache-write tokens: 0
- hit ratio: 98.4517% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 6 of 114092 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoRunCmdGaps']; window: 2026-10-06T08:36:19.751000+00:00..2026-10-06T08:43:18.185000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T08:36:19.751000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791275779751
  - break_items=1; WHEN=2026-10-06T08:36:20.509000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791275780509
  - break_items=1; WHEN=2026-10-06T08:36:21.352000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791275781352
  - break_items=3; WHEN=2026-10-06T08:36:22.031000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275782031
  - break_items=2; WHEN=2026-10-06T08:38:52.566000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-flash model=deepseek-flash item_index=50; turn_id=1791275932566
  - break_items=2; WHEN=2026-10-06T08:43:18.185000+00:00; WHERE session_id=01a1105b-2a29-7640-b6f3-8b9ca915f0d5 provider=deepseek-flash model=deepseek-flash item_index=168; turn_id=1791276198185
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(The `cline-pass`, `space-bunny-free` and `ling-3.1-flash-free` rows belong to the
harness's own model-fallback probes inside this session, not to this lane's
work; the partition is reported verbatim rather than trimmed.)
