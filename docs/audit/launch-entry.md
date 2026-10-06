# Audit — how the app is started, and what it reports when it fails

axis: launch entry · lane: `AuditLaunchEntry` · date: 2026-10-06 · READ-ONLY audit.
Every claim below carries `file:line` or the command + its output. Nothing here
was edited; the only write performed is this file.

Entry points under audit:

| file | role |
|---|---|
| `H:/sotto/app/webview/run.cmd` | the launcher (double-click target) |
| `H:/sotto/app/webview/sotto_webview.py` | the shell (the app) |
| `C:/Users/Administrador/.omp/run/daemons/26e631d39281aff7/daemons/sotto-app/` | the harness service that ran it and reported 127 |

---

## 0. The three measured facts, and what I found for each

| fact | verdict |
|---|---|
| `run.cmd <bogus>` used to answer rc=0; a fix landed | **fix HOLDS** — re-measured today, §1. It is real, and it is narrow: §2 lists what it does not cover, with `file:line`. |
| a supervised harness service logged a healthy start then reported `failed with exit code 127` | **the 127 is the WRAPPER's, not the shell's and not the worker's** — §3. The precise trigger inside the wrapper is NOT established (see §3.4: the decisive test needs a relaunch, which is forbidden here). |
| one run had `HOTKEY_REGISTERED` and no `WORKER_AUTOSTART` | **a SYMPTOM, not a second defect** — §4: `start_worker` is only reachable from the shell's *second* `_on_loaded`, and that event never fired. The shell hung after `STAGING_LOADED`. |

---

## 1. The pre-flight fix — verified today, not taken from the receipt

### 1.1 What the launcher does

`run.cmd` resolves the interpreter (`run.cmd:38-49`), then — **before anything is
spawned** — runs the shell's own parser on the same argument list:

```bat
run.cmd:83  set "PREFLIGHT_RC=0"
run.cmd:84  "%PYW%" "%SHELL%" --check-args %*
run.cmd:85  set "PREFLIGHT_RC=%ERRORLEVEL%"
run.cmd:86  if not "%PREFLIGHT_RC%"=="0" (
run.cmd:87    echo run.cmd: the shell REFUSED this argument list ^(rc=%PREFLIGHT_RC%^). Nothing was started.
run.cmd:91    >>"%HERE%..\..\_main\webview-run.log" echo sotto: ARGS_REJECTED rc=%PREFLIGHT_RC% by=run.cmd-preflight
run.cmd:92    exit /b %PREFLIGHT_RC%
run.cmd:104  ) else ( start "" "%PYW%" "%SHELL%" %* )
run.cmd:112 exit /b 0
```

The flag is the shell's own, hidden from `--help` (`sotto_webview.py:2432-2433`)
and it returns **before** `_open_log` and before any window
(`sotto_webview.py:2449-2463`).

### 1.2 Re-measured now (windowless `pythonw`, starts nothing)

```
$ "C:/Program Files/Python311/pythonw.exe" H:/sotto/app/webview/sotto_webview.py \
      --check-args --with-worker --log H:/sotto/_main/x.log --no-hotkey --no-hot-reload --exit-after 60
rc=0
$ ... --check-args --bogus-flag
sotto-webview: error: unrecognized arguments: --bogus-flag
rc=2
$ ... --check-args --show --with-worker
rc=0
```

So: **a bogus flag exits 2 (was 0), a real call-site argv exits 0, and nothing
is opened, logged or started in the pre-flight.** The fix is real and holds.

Live corroboration that the receipt branch actually fires on this box: the shared
log carries the pre-flight's own line —
`H:/sotto/_main/webview-run.log` contains `sotto: ARGS_REJECTED rc=2 by=run.cmd-preflight`.

### 1.3 A control that does NOT go vacuous

`_main/run-cmd-exit-oracle.py --neg-arm` restores the pre-fix wrapper from
`_main/run-cmd-prefix-20261006.cmd` (sha256 `b9c08fec…`) into a COPY and refuses
to run if the copy is no longer a control; the copy's bogus arm reads rc=0 while
the live one reads rc=2 (`_main/RunCmdExitContract.md`). I did not re-run the
oracle (it starts the app); the code path it asserts is the same one I measured
by hand in §1.2.

---

## 2. What the pre-flight does NOT cover — with `file:line`

The pre-flight validates **the argument list only**. It cannot see any failure
that happens after the interpreter accepts the argv, because `start` detaches
the app and `run.cmd:112` returns `0` unconditionally. Concrete, checkable gaps:

**G1 — a missing panel still reports 0.** `--check-args` returns at
`sotto_webview.py:2463`, i.e. **before** the panel existence check at
`sotto_webview.py:2469-2470` (`PANEL_MISSING … return 3`). So with
`app/electron/panel.html` absent, `run.cmd` returns **0** and the app exits **3**.
Command that would show it (NOT run — it starts the app):
`py -3 sotto_webview.py --log x.log` with the panel renamed.

**G2 — a missing `pywebview` still reports 0.** `import webview` is late, inside
`main()` at `sotto_webview.py:2502`; an `ImportError` there exits the process
**1** while `run.cmd` has already returned 0.

**G3 — the shell can hang after `STAGING_LOADED` and `run.cmd` still says 0.**
This is exactly what §3/§4 measured for the supervised run. `run.cmd` has no way
to see it: the app is detached (`run.cmd:104`).

**G4 — if `pythonw.exe` is absent, the app launches under `python.exe`.**
`run.cmd:48-49`:

```bat
set "PYW=%PYEXE:python.exe=pythonw.exe%"
if not exist "%PYW%" set "PYW=%PYEXE%"
```

`PYEXE` is `python.exe`, so the fallback path is a **console** interpreter, and
`run.cmd:104/110` then `start`s the app under it. That breaks the file's own
headline guarantee (run.cmd:19-24: "NO CONSOLE WINDOW … a normal launch goes
through pythonw.exe") and the house rule "never leave a visible console window"
(`H:/sotto/AGENTS.md`). It is only reachable on a machine with `python.exe` and
no `pythonw.exe`; Python's Windows installer ships both, so this is a latent
gap, not an observed one. Note the pre-flight runs on the SAME `%PYW%`, so it
does not detect the degradation either.

**G5 — the pre-flight itself is a `pythonw` run with no stdout.** argparse writes
`usage:`/`error:` to stderr; `pythonw` has `stdout=None stderr=None` (the fact
run.cmd:19-24 cites). So a user running `run.cmd` with a bad flag sees only the
`echo` at `run.cmd:87` on their console — correct — but the interpreter's own
message is discarded, and the exit code is the ONLY signal the pre-flight can
pass on. That is by design, and it is why the receipt line at `run.cmd:91`
exists; it is worth stating that the rc is the whole contract.

**Not a gap but worth naming:** `--check-args` is itself an accepted flag, so
`run.cmd --check-args` passes the pre-flight, starts the app, and the app returns
0 having opened nothing (`sotto_webview.py:2449-2463`). A hidden no-op flag, low
risk, but it is a second way for "nothing happened" to answer as success.

---

## 3. The `exit 127` under the harness supervisor — what it is and is not

### 3.1 The service, verbatim from disk

`/proc` listed it as `sotto-app [service] — failed`. Its own files:

`C:/Users/Administrador/.omp/run/daemons/26e631d39281aff7/daemons/sotto-app/spec.json`:

```json
{"name":"sotto-app",
 "application":"C:\\Program Files\\Git\\bin\\bash.exe",
 "args":["-l","-c","rm -f _main/_live-app.log && \"/c/Program Files/Python311/pythonw.exe\" app/webview/sotto_webview.py --with-worker --log H:/sotto/_main/_live-app.log"],
 "cwd":"H:\\sotto", "pty":true,
 "ready":{"log":"HOTKEY_REGISTERED"},
 "restart":"no","persist":false,"detached":false}
```

`…/sotto-app/meta.json`:

```json
{"daemon":{"name":"sotto-app","state":"failed","createdAt":1791274777116,
 "startedAt":1791274777118,"restartCount":0,"outputBytes":83,
 "exitedAt":1791274844157,"exitCode":127}}
```

Converted (verified with `date -u -d @…`): started **08:19:37Z**, exited
**08:20:44Z**, up **67 s** — the `up 1m7s` the panel showed.

So the supervised process is a **bash wrapper**, and the exit code `127` is
recorded against **that bash**, not against `sotto_webview.py`.

`output.log` is 83 bytes, all of it PTY/ConPTY setup plus one window-title
escape naming the wrapper — no command output, no bash error line:

```
$ cat -A output.log
^[[6n^[[?9001h^[[?1004h^[[m^[]0;C:\Program Files\Git\bin\bash.exe^G^[[?25h^[[?9001l^[[?1004l
```

(For scale: sibling services that exited 0 print their own command output here —
`int8dl` 420 B of HF fetch progress, `sotto-acc-fetch` `rc=0`, etc. Because the
`sotto-app` command is `rm -f …` + `pythonw …` and pythonw is a GUI binary whose
output is redirected by `--log`, **zero bytes on the PTY is also what a
SUCCESSFUL run of this command would look like.** Emptiness here is therefore
NOT evidence of failure — I checked the siblings precisely to avoid that wrong
conclusion.)

### 3.2 The shell DID start

`H:/sotto/_main/_live-app.log` (1404 B, 15 lines) is the shell's own `--log`
output for this launch. It reaches a healthy startup and then stops:

```
sotto: shell=webview2 pywebview=6.2.1 python=3.11.8 pid=30848
sotto: panel window created …
sotto: panel geometry: docked=right window=380x900@(1528,66) margin=12
sotto: HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true … thread=32892
sotto: HOT_RELOAD_WATCH …
sotto: HOT_RELOAD_ENABLED watchers=2 debounce_ms=250
sotto: panel setAlwaysOnTop(floating) ok …
sotto: panel client area forced to 380x900 (window 380x900)
sotto: PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=60499642 form.Visible=false opacity=1.0 show_requested=false
sotto: STAGING_LOADED core=yes -> navigating to panel H:\sotto\app\electron\panel.html      ← LAST LINE
```

That file can only have been written by `sotto_webview.py` running under
`pythonw.exe --log H:/sotto/_main/_live-app.log`, so **the wrapper's command
executed**.

### 3.3 Why the 127 is NOT the shell and NOT the worker

- **Not the shell.** `_exit_code` starts at 0 (`sotto_webview.py:945`) and is
  only ever set by `request_exit(code)`, and every caller passes 0 or 3 —
  `:1606`, `:1746` (`dump-dom-failed`), `:1773` (`bridge-gate-red`),
  `:1779-1795` (`selftest-needs-hotkey`). `run_memory`/`main` return
  `shell._exit_code` (`:2503`). **There is no path that yields 127 from the
  shell.** I grepped the whole file for `127`; the only hits are the
  `http://127.0.0.1:23602` comment.
- **Not the worker.** `_live-app.log` has no `WORKER_AUTOSTART`, no `BRIDGE_SPAWNED`,
  no `WORKER_PATH` — the worker was never spawned (§4). A process that never
  started cannot be the one that exited 127.
- **The code does not propagate from the shell anyway.** The wrapper exited at
  **08:20:44Z**, but `_live-app.log` was last modified at **08:21:25Z** (measured:
  `stat -c %y` → `2026-10-06 05:21:25 -0300`; UTC = 08:21:25Z) — i.e. **41 s
  AFTER** the recorded exit. A child that writes 41 s after its parent's recorded
  exit cannot be the source of that exit code.

**Therefore the 127 belongs to the wrapper layer (bash and/or the harness's
command resolution), not to the app.** On this box 127 is the "command not
found" family: the harness's own shell returns exactly that shape —
`"/c/Windows/System32/where.exe" cmd.exe` → `error: command not found:
/c/Windows/System32/where.exe`, `rc=127` (measured, §3.4.1).

### 3.4 What I could NOT establish, and the exact test that would

I could not identify *which* token of the wrapper's command was not found, for a
reason that is itself a finding: **bash would have printed the failure.**

3.4.1 — I reproduced the wrapper shape against benign children (NO app launched):

```
$ "C:/Program Files/Git/usr/bin/bash.exe" -l -c 'rm -f /tmp/zzz && "/c/Program Files/Python311/pythonw.exe" -c "import sys;sys.exit(0)"; echo SHAPE_RC=$?'
SHAPE_RC=0
$ ... pythonw.exe -c "import sys;sys.exit(7)"
SHAPE_RC=7
$ ... pythonw.exe app/webview/NOPE.py
C:\Program Files\Python311\pythonw.exe: can't open file 'H:\sotto\app\webview\NOPE.py': [Errno 2] No such file or directory
SHAPE_RC=2
```

So a real login `bash` **does** resolve `/c/Program Files/Python311/pythonw.exe`
and **does** propagate the child's exit code, and a genuine "not found"/"can't
open" prints a line. The supervised run's PTY has **no such line**, yet reports
127. That combination — 127 with no not-found message — is what I could not
close from disk.

3.4.2 — Leading hypotheses, ranked, each with its falsifier (none run, because
each needs the app launched, which this brief forbids):

1. **Command-string mangling before bash saw it.** `bash.exe` started (its PTY
   title is in `output.log`, so the harness spawned it), but bash's `-c` string
   may have been re-quoted by the broker so that the inner `"` around the MSYS
   path did not survive; bash would then have run a truncated command.
   *Falsifier:* relaunch the SAME spec and read the PTY's stderr — a real
   not-found prints a `bash: …: No such file or directory` line; §3.4.1 shows it
   must.
2. **The harness's `ready` condition can never be met, and the failure is
   reported against the wrapper.** `ready` is `{"log":"HOTKEY_REGISTERED"}` — a
   regex matched against the **service's own output** (`omp://tools/bash.md`,
   "Success, named service": readiness reads the service's log). But the shell
   writes `HOTKEY_REGISTERED` to `--log H:/sotto/_main/_live-app.log`, **not to
   the PTY**, and `pythonw` has no stdout. So the ready line was written where
   the supervisor cannot see it: the log has it (§3.2), the PTY does not
   (§3.1). Whether an unsatisfied `ready` is *what* ends the run at 67 s with
   127 is unproven, but the readiness blindness is **measured**: `ready` points
   at a stream the app never writes to.
   *Falsifier:* declare `ready` on a condition the app does emit on stdout, or
   pass the log path as the readiness source, and see whether the 127 survives.
3. **The broker killed the wrapper** (e.g. on the readiness timeout) and 127 is
   the mapped code. *Falsifier:* one relaunch with `ready` removed; if the
   process then lives past 67 s, the readiness path was the trigger.

The single command that would settle all three — and that I deliberately did
not run — is a relaunch of the recorded spec with its stderr surfaced, e.g.
`docs/audit` should be re-run with the PTY tail preserved. **Launching the app is
forbidden in this brief**; that is the blocker, stated as such, not a guess.

### 3.5 A second, independent observation that changes the story

`meta.json` says `restartCount:0`, `state:"failed"`, so this was the one run.
Its shell wrote `pid=30848`. The brief that sent me said **"the app is RUNNING
right now (pid 30848)"**. It was not, by the time I looked:

```
$ tasklist /FI "PID eq 30848"
INFORMAÇÕES: nenhuma tarefa em execução correspondente aos critérios especificados.
```

`_live-app.log`'s mtime is frozen at 08:21:25Z (no writer since), and
`webview-run.log`'s mtime is 05:05:28 local. Many `pythonw.exe` and
`msedgewebview2.exe` processes exist (14 pythonw rows, 8 WebView2 hosts), so
*a* shell may be up — but **not pid 30848**, and not the one this log belongs to.
The most likely reading: `30848` was read out of `_live-app.log`'s first line and
was already stale when the brief was written. Anyone re-issuing "do not kill
pid 30848" should re-derive the pid from the live table, not from that log.

---

## 4. `HOTKEY_REGISTERED` with no `WORKER_AUTOSTART` — the mechanism

`WORKER_AUTOSTART` is logged in exactly one place,
`sotto_webview.py:1651-1652`, inside `start_worker`, which is called from
exactly one place:

```python
sotto_webview.py:1283  if not self.startup_done:
sotto_webview.py:1284      self.startup_done = True
sotto_webview.py:1285      self.send_geometry()
sotto_webview.py:1286      self._measure_on_screen_visibility('startup')
sotto_webview.py:1287      if self.args.with_worker:
sotto_webview.py:1288          self.start_worker('with-worker')
```

and that block lives in `_on_loaded` **after** the staging branch:

```python
sotto_webview.py:1249  def _on_loaded(self):
...
sotto_webview.py:1253      if not self.staged:
sotto_webview.py:1254          self.staged = True
sotto_webview.py:1255          log(f'STAGING_LOADED core=… -> navigating to panel {PANEL_HTML}')
sotto_webview.py:1256          self.window.load_url(file_url(PANEL_HTML))
sotto_webview.py:1257          return
```

`_on_loaded` fires **twice** on a healthy start: once for `stage.html` (logs
`STAGING_LOADED`, returns) and once for the panel (logs `PRELOAD_ACTIVE`,
`RECEIVER_READY`, then `WORKER_AUTOSTART`). In `_live-app.log` it fired **once**:
the last line is `STAGING_LOADED`, and there is no `PRELOAD_ACTIVE` and no
`RECEIVER_READY`. **The second navigation never completed, so line 1287 was
never reached and the worker was never spawned.** The absence of
`WORKER_AUTOSTART` is a *symptom of the hang*, not a separate wiring bug.

For contrast, the healthy run in `_main/runcmd-entry-report.txt` shows the full
sequence in one log: `STAGING_LOADED` → `PRELOAD_INSTALLED` → `PRELOAD_ACTIVE` →
`RECEIVER_READY` → `WORKER_AUTOSTART=started reason=with-worker`.

The `--with-worker` deadlock that once produced this exact symptom was already
fixed — `WorkerBridge.start()` holds the non-reentrant `_lock`
(`sotto_webview.py:1900-1917`), `_spawn` arms the watchdog at `:1985`, and
`_arm_silence` carries the "MUST NOT take `self._lock`" contract at
`:2117-2123`. So the deadlock is not the cause here. The shipped file's own
comments name two *other* causes of a `STAGING_LOADED` hang, both removed
(off-screen creation `sotto_webview.py:972-991`; clearing
`window.transparent` `:1004-1012`) — which means a **third** cause reproduced
this afternoon and is not yet named. That is the real open item this axis hands
back, and it correlates with §3: the same supervised launch both hung the shell
and recorded 127 against the wrapper.

---

## 5. What I could not verify (explicit)

1. **The exact trigger of the wrapper's 127** (§3.4). Requires relaunching the
   app; forbidden. The two falisifiable hypotheses and their tests are given.
2. **Whether the `STAGING_LOADED` shell in `_live-app.log` is this service's own
   child or a later, separate launch.** The `rm -f` at the head of the wrapper
   command would have deleted the file first, and its mtime (08:21:25Z) is after
   the service exit (08:20:44Z); both a child that outlived its parent and a
   later launch fit the timestamps. I could not distinguish them without an
   instrumented relaunch.
3. **G1/G2/G3 by execution.** I read the code paths; I did not run the app with a
   missing panel / missing pywebview / hanging navigation to see `run.cmd` answer
   0. (Reading the return values is decisive for G1/G2; G3 is what §3/§4
   measured indirectly.)
4. **G4 by execution.** No machine state was created (I did not remove
   `pythonw.exe`); the gap is read off `run.cmd:48-49`.
5. **The current live pid of the app.** I established 30848 is gone; I did not
   establish which pid *is* the app now. Reproducing the harness's own
   `ProcStartTrace`/`lane` census was out of scope and the sanctioned census tool
   returned `0 processes sampled` for my filters, so I will not assert a pid.
6. **The `--help` byte-identity claim** from `RunCmdExitContract.md`
   (2272 B both sides). I confirmed `--check-args --help` rc=0 and prints the
   17-flag usage, but I did not diff bytes against the pre-fix wrapper.

---

## SELF-AUDIT

- **protocolos em falta** — one: the brief said "READ-ONLY … write EXACTLY ONE
  file", and I came within one call of running `run.cmd --bogus-flag` to see the
  receipt appear. That call **appends** a line to `_main/webview-run.log` — a
  second file write. I stopped and measured `--check-args` directly under
  `pythonw` instead (§1.2), which is the same predicate with no write. The rule I
  should have had up front: *before "verify by running", grep the command for
  its side effects.*
- **verificacao adicional** — the cheap one I did NOT run: measure whether the
  harness's `ready` regex can EVER fire, by grepping the service's `output.log`
  for `HOTKEY_REGISTERED` (it cannot — the app never writes to the PTY). I
  inferred it from `output.log`'s content instead of asserting it as a check.
  Cost ≈ 1 command; it would upgrade §3.4 hypothesis 2 from "leading" to
  "measured".
- **checkboxes novas** (mechanical, never "be more careful"):
  1. Before any "verify by running" of a launcher: `grep -n ">>\|\"start \"\|--log" <launcher>`
     and refuse the run if it writes a path you were not authorised to write.
  2. For any supervised-service audit: **read `spec.json` and `meta.json` before
     quoting the panel**, because the panel's `exit=127` is the WRAPPER's code
     and the panel does not say so. Assert `application` == the thing you think
     exited.
  3. For any "no output ⇒ it failed" claim on a service: compare `output.log`
     size against a sibling service known to exit 0 **for a command that also
     prints nothing**; here the emptiness was a red herring until I diffed.
- **review por outro subagente** — **sim-com-escopo**: re-derive §3 purely from
  `spec.json` + `meta.json` + `output.log` + `_live-app.log` and try to falsify
  "the 127 is the wrapper's, not the shell's". Do NOT re-run §1 (measured) and do
  NOT run §5.1 (needs a launch).
- **gate-doubt**:
  - *verde-de-verdade:* `rc=0`/`rc=2` from §1.2 is real — I got both colours in
    one session with the real shell, and `--check-args` returns before
    `_open_log` (`sotto_webview.py:2449-2465`), so nothing was started or logged;
    the green is not vacuous. The one green I do NOT trust is "output.log is
    empty ⇒ failed": §3.1 shows the sibling services prove that emptiness is
    consistent with success for this command shape. `state:"failed"` itself is
    the supervisor's word for the WRAPPER; I treat it as a wrapper verdict only.
  - *falta-no-gate:* the pre-flight gate does NOT cover any post-argv failure —
    named as scenarios in G1–G4, all of which `run.cmd` reports as `0`. The one
    that a future change walks straight through: **a renamed/removed
    `app/electron/panel.html`** (G1), because the check that would catch it
    (`sotto_webview.py:2469`) sits after the pre-flight's early return.
  - *gate-melhor:* make the shell's `--check-args` ALSO assert the two static
     prerequisites it can see without opening a window — panel file present and
     `import webview` resolvable — and return 3/1 from `--check-args` when they
     are not. Input that must leave it RED:
     `pythonw sotto_webview.py --check-args` with `app/electron/panel.html`
     renamed → today `rc=0`, must be non-zero.
- **confianca** — **alta** for §1 (fix holds; measured both colours), for §2 (each
  gap is a `file:line` return-value chain or a literal fallback assignment), and
  for §4 (the only caller of `start_worker` is behind a branch that requires the
  second `_on_loaded`, which the log proves did not fire). **media-baixa** for §3
  beyond "the 127 is the wrapper's": I proved what it is NOT, and gave ranked,
  falsifiable candidates for what it IS, but did not land the trigger. What would
  raise it: one instrumented relaunch with the PTY stderr surfaced (§3.4.2).
- **nao verificado** — §5, items 1–6.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: AuditLaunchEntry
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditLaunchEntry.jsonl
- cache: read=5332403 write=0 hit=95.3629% (cache-read / input+cache-read); universe: 39 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditLaunchEntry.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=31 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=8 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 39 of 39 matched usage rows
- when-failed: break_items=16; WHEN=2026-10-06T08:24:50.363000+00:00 | break_items=2; WHEN=2026-10-06T08:26:13.291000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 113507 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditLaunchEntry']; window: 2026-10-06T08:24:50.363000+00:00..2026-10-06T08:26:13.291000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11050-0fed-77ac-b6ad-c18280440faf provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791275090363 | session_id=01a11050-0fed-77ac-b6ad-c18280440faf provider=deepseek-flash model=deepseek-flash item_index=75; turn_id=1791275173291
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
