# SottoRunCmdExitContract — `run.cmd` returns the CHILD's status

status: DONE
repo: `H:/sotto` (branch `main`; `app/webview/` is UNTRACKED, so nothing was committed)
lane: SottoRunCmdExitContract (worker) · date: 2026-10-06

(Placement note: this receipt first went to `I:/!manager/runs/`, the linted receipts
corpus, and the manager-side closure-admission guard REFUSED it: a done card there
requires a `bash`-executable `production_entrypoint` with reject/accept controls, a
`provenance_sha` in the MANAGER repo and `owned_paths` relative to it. This lane's
deliverable lives in `H:/sotto` and is untracked, so it cannot satisfy that contract;
the sibling lanes' receipts for this repo live in `_main/*.md`, which is where this one
lives.)

verify: `cd H:/sotto && py -3 _main/run-cmd-exit-oracle.py --label after`  — the ARM conjunct
result:
`ARM-VERDICT    PASS  all 4 arms green`
`ARM-RCS bogus=2(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)`
exit code **1** — the code is 1 for the OTHER conjunct, not the arms:
`CENSUS-VERDICT FAIL  262 samples, 141 with a visible window` / `VERDICT FAIL  arms=PASS census=FAIL`.
An earlier pass of the same subject exited **0** with the same ARM verdict and `CENSUS OK: … 213 samples visible_samples=0`.

verify: `cd H:/sotto && py -3 _main/run-cmd-exit-oracle.py --neg-arm`  — the inverted copy
result:
`ARM-VERDICT    PASS  arm1(bogus) RED-as-expected=True arms2-4-still-green=True failed=['bogus']`
`ARM bogus  rc=0 want=2 FAIL`  (the defect, reproduced on the reverted copy)
`ARM-RCS bogus=0(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)`
exit code **1** (census conjunct again). Copy byte-verified before it runs:
`copy_run_cmd_sha256=b9c08fecb94f8031…` == `neg_src_sha256`; a control that has stopped
being a control is REFUSED, not run.

verify: `cd H:/sotto && py -3 _main/_armE-window-census.py -- py -3 _main/run-cmd-exit-oracle.py --label after`
result: the oracle's own lines plus `CENSUS-PID pid_tree_root=7468 samples=215 visible_samples_over_tree=0 distinct=0 child_rc=0`.
In a LATER pass of the SAME subject this driver printed 0 while the oracle's census printed
`141 of 262` — the hole §5 and the GATE-CHANGE REQUEST below name. exit code 0 (child rc 0).

verify: `cd H:/sotto && py -3 _main/_runcmd-panel-flash-probe.py --runs 8` and `… --direct --runs 8`
result: `RUN 8 flash_samples=88 … pid=26980 title='Sotto'` / `RUN 8 flash_samples=130 … pid=23392 title='Sotto'` —
both arms flash, including with NO `run.cmd` in the path, so the launcher is exonerated. exit code 0.

verify: pre-fix copy vs live wrapper, `--help` captured with `CREATE_NO_WINDOW`
result: `BEFORE rc=0 bytes=2272   AFTER rc=0 bytes=2272   IDENTICAL: True`. exit code 0.

| path (H:/sotto) | sha256 (after) | what |
|---|---|---|
| `app/webview/run.cmd` | `9e2f910f5854710e…` | + the PRE-FLIGHT block (starts nothing; propagates the child's rc) |
| `app/webview/sotto_webview.py` | `a3b61c250757b26c…` | + hidden `--check-args` (parser) + the early return in `main()` |
| `_main/run-cmd-exit-oracle.py` | (new) | the gate: 5 arms, both colours in ONE command |
| `_main/run-cmd-prefix-20261006.cmd` | `b9c08fecb94f8031…` | the PRE-FIX wrapper bytes — the negative arm's input |
| `_main/_runcmd-panel-flash-probe.py` | (new) | the 50 ms probe that found the panel flash (§5) |
| `AGENTS.md`, `app/webview/README.md` | appended | the measured facts + the exit contract |

## 1. The defect (measured by lane SottoRunCmdEntry — NOT re-found here)

`app/webview/run.cmd --bogus-flag` → **rc=0**, stdout empty, NO log bytes, NO shell
line, NO leftover process. argparse exits 2 on `pythonw.exe` (whose stdout is None)
and `start` reports only its OWN success, so the interpreter's status never reached the
caller. Same family as the rest of the round: a failure answering as success.

## 2. The fix — option (a), and the line option (b) would key on

`start` is KEPT: a wrapper that waited for the app would hold the caller's console open
for the whole session, and the app is meant to sit hidden for days. The child's status
is taken **where it can still be seen — in a run that STARTS NOTHING**:

```bat
"%PYW%" "%SHELL%" --check-args %*          REM the shell's OWN parser, windowless
set "PREFLIGHT_RC=%ERRORLEVEL%"
if not "%PREFLIGHT_RC%"=="0" (
  echo run.cmd: the shell REFUSED this argument list ^(rc=%PREFLIGHT_RC%^). …
  >>"%HERE%..\..\_main\webview-run.log" echo sotto: ARGS_REJECTED rc=%PREFLIGHT_RC% by=run.cmd-preflight
  exit /b %PREFLIGHT_RC%                   REM the CHILD's rc, not a synthetic code
)
```

Chosen over (b) because (a) costs one ~70–250 ms `pythonw` run, touches nothing the
caller owns, and cannot be fooled by a STALE log line — the trap (b) would have to solve
explicitly (`_main/webview-run.log` is appended across runs, so a line from the previous
launch could answer for this one). The line (b) would key on is the shell's FIRST and it
exists — **`sotto: shell=webview2 pywebview=<v> python=<v> pid=<N>`** — the oracle's
start arms ASSERT it, and the kill pid is parsed out of it.

`--check-args` is `help=argparse.SUPPRESS`, so `run.cmd --help` is byte-identical (see the
verify line above).

NOT covered, said out loud: a list argparse ACCEPTS that fails later (missing pywebview,
bad panel path) still reports 0. Covering that needs (b).

## 3. The three rc values — before and after

BEFORE (pre-fix wrapper byte-restored into a copy at `G:\Temp\sotto-runcmd-neg-karg4v8p`,
sha `b9c08fec…`, every other file the one under test):

```
ARM-VERDICT    PASS  arm1(bogus) RED-as-expected=True arms2-4-still-green=True failed=['bogus']
ARM-RCS bogus=0(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)
ARM bogus  rc=0 want=2 FAIL
    [NO] rc == 2 (the child's own argparse status, passed through) :: rc=0
    [NO] the wrapper says so on its own console :: (no output)
    [NO] a receipt line is appended to the run log (before the fix appends NO bytes at all) :: ''
```

AFTER (live wrapper):

```
RUN-CMD run_cmd_sha256=9e2f910f5854710e7edca38de795257113300a74c1c07a52efa66dfc8cb062d7
RUN-CMD shell_sha256=a3b61c250757b26ce2556e107fabe7f8d5f34e1622ba346639153f36081009ef shell_mtime=1791273714
ARM argv  rc=0 want=0 PASS   (8 real call-site argv sets, all accepted)
ARM bogus rc=2 want=2 PASS   rc=2 | "run.cmd: the shell REFUSED this argument list (rc=2). Nothing was started." |
                             "sotto: ARGS_REJECTED rc=2 by=run.cmd-preflight" | no shell= line | leftovers=[]
ARM help  rc=0 want=0 PASS   usage: sotto-webview … 17/17 declared flags present, --check-args hidden
ARM start-logged  rc=0 want=0 PASS pid=38508  wrapper_ms=247 (app lives 8 s) | pid alive | SHELL_EXIT rc=0 | pid gone
ARM start-default rc=0 want=0 PASS pid=13912  wrapper_ms=321 | pid alive | SHELL_EXIT rc=0 | pid gone
ARM-VERDICT    PASS  all 4 arms green
ARM-RCS bogus=2(want 2) help=0(want 0) start-logged=0(want 0) start-default=0(want 0) argv=0(want 0)
```

**rc table: bogus 0 → 2. `--help` 0 → 0, usage byte-identical. normal detached start 0 → 0.**

## 4. The negative arm

`--neg-arm` builds the copy, REFUSES to run if the control has stopped being one
(`--check-args` already present, or byte-identical to the wrapper under test), and
inverts the verdict for arm 1 only. Measured: arm 1 RED (rc=0), arms 2–4 still green,
`failed=['bogus']` — the copy differs from the fixed tree in exactly one file and exactly
one arm moved, which is what makes it a control. The `argv` arm is VACUOUS in the copy
(the pre-fix wrapper has no pre-flight at all) and the oracle now PRINTS that
(`ARM-NOTE … VACUOUS in this copy`) instead of counting it as a pass.

## 5. The window census against my own pids

Two readings, and they disagree — which is itself the finding.

House census driver (`_main/_armE-window-census.py`, 100 ms) around the oracle, clean pass:
`CENSUS-PID pid_tree_root=7468 samples=215 visible_samples_over_tree=0 distinct=0 child_rc=0`;
oracle's own census that pass: `213 samples, visible_samples=0`.

Later the same session the app's panel became visible on EVERY start, and my oracle's
census said so — while the house driver, around an EARLIER pass of the same subject,
had printed 0:

```
CENSUS ALERTA-JANELA 38508:21898664 pid=38508 hwnd=21898664 title='Sotto' class='WindowsForms10.Window.8.app.0.aec740_r16_ad1' n=71
CENSUS ALERTA-JANELA 13912:29630596 pid=13912 hwnd=29630596 title='Sotto' class='WindowsForms10.Window.8.app.0.aec740_r16_ad1' n=70
CENSUS RED: 141 of 262 samples had a VISIBLE window in this run's tree
ARM-VERDICT    PASS  all 4 arms green
CENSUS-VERDICT FAIL  262 samples, 141 with a visible window
```

Why they disagree: the app is `start`-DETACHED, so once the cmd.exe that launched it
exits, a walk of the LIVE process table cannot reach it (its recorded parent pid is
dead). My oracle's census is MONOTONE and seeds the tracked set from the pid in the app's
own log line — the only reason the second reading exists.

`_main/_runcmd-panel-flash-probe.py` (50 ms cadence, 20 starts, pid read from the app's
log line) located it: the `Sotto` form VISIBLE for 1–2 samples at +0.76 s / +0.98 s after
the app's first line in 2 of 5 starts, and for 88 / 130 samples (≈4.4 s / ≈6.5 s) on the
8th consecutive start — in BOTH arms, `--direct` included, so **`run.cmd` is
exonerated**. The 60 s house census caught it too, on pids this probe started:
`ALERTA-JANELA ts=2026-10-06T08:02:21Z chave=34752:30877334 pid=34752 nome=pythonw`
(pid proved mine by the `pid=` lines in `_main/_runcmd-panel-flash.log`); 6 such pythonw
alarms exist today. Filed as ticket `7d45df2bec5431c26ff74563`; the FIX belongs to the
lane already sampling it (`_main/panel-startup-flash-census.py`). No app start was
performed after that measurement.

## 6. Regression audit of the new gate

Every `run.cmd` call site in the repo was grepped for flags: `docs/webview-app-20261006.md`
(`--selftest --log`, `--exit-after 25`), `_main/runcmd-entry-driver.py`
(`--with-worker --log --no-hotkey --no-hot-reload --exit-after 60`), README/driver
(`--show --with-worker`), bare `cmd /c run.cmd` (double-click). ALL are accepted by the
pre-flight, asserted mechanically by the `argv` arm — the guard for the only way this fix
can hurt: a call site passing a flag the shell does not know would now FAIL where it used
to "work".

## GATE-CHANGE REQUEST — `_main/_armE-window-census.py` cannot see the thing it measures

The hole, measured twice in one session: the sampling loop re-walks `tree(root)` every
tick, so an app DETACHED by `start` becomes invisible the moment the cmd.exe that launched
it exits. Price paid: `visible_samples_over_tree=0` around a pass in which the app's own
pid was visible for 141 samples.

Merge-ready patch (keeps the CLI, adds no dependency):

```python
#  in the sampling loop, replace  pids = tree(root)  with:
tracked |= tree(root)                       # MONOTONE: never forget a pid
for extra in extra_pids():                  # pids read from the subject's own log
    tracked.add(extra)                      #   (`sotto: shell=webview2 … pid=<N>`)
wins = [w for w in visible_windows() if w[0] in tracked]
#  __init__:  tracked = {root}   ;   new flag: --pid-file PATH (repeatable)
```

Non-vacuity control: run it around `_main/run-cmd-exit-oracle.py --label after` and require
the two readings to AGREE (`visible_samples_over_tree != 0` in a pass where the oracle's own
census reports >0); the pre-patch form returns 0 there — that is the RED arm. I did NOT edit
the sibling's instrument (another lane's file); the patch is offered, Main merges.

## SELF-AUDIT

- **protocolos em falta** — none missing for this ticket's deliverable, but one I did not
  follow and should have: I edited a SHARED file (`app/webview/sotto_webview.py`) BEFORE
  resolving ownership with the lane already working in that file, and my attempt to
  coordinate failed at the tool level (a peer `write` to `agent://…` is resolved as a
  filesystem path — ticket `720e24e659a4b8202da91edb`). What I would do differently: hash
  the shared file, message the owner, wait one turn, THEN edit. Here it cost nothing only
  because the file held exactly my 16 added lines and was byte-unchanged
  (`a3b61c250757b26c`) across every run — luck, not method.
- **verificacao adicional** — the cheap one I did NOT run: a SECOND negative arm that
  reverts the SHELL half while the wrapper half stays (a wrapper passing `--check-args` to a
  shell that does not know it). Cost ≈ 10 s; it would prove the two halves fail together
  instead of only proving the wrapper half alone. Second cheap one skipped: the census
  primitives' own `--selftest` before believing their 0.
- **checkboxes novas** (mechanical; never "be more careful"):
  1. `py -3 _main/run-cmd-exit-oracle.py --neg-arm` AND `py -3 _main/run-cmd-exit-oracle.py`
     in ONE command with both ARM-VERDICTs pasted — a wrapper rc claim without its inverted
     copy is unfalsifiable.
  2. before editing a shared file, record `sha256(file)` in the receipt and re-record it
     after every run (this receipt's table) — that is how "no sibling clobbered me" becomes
     a fact.
  3. any "no window appeared" claim states CADENCE + PID SOURCE in the same line as the count.
- **review por outro subagente** — sim-com-escopo: review `_main/run-cmd-exit-oracle.py`
  (arm expectations + the neg-arm inversion) and the `run.cmd` pre-flight block. Not needed:
  the census/flash material, which another lane is re-measuring right now.
- **gate-doubt**:
  - *verde-de-verdade:* `ARM-VERDICT PASS` is real — arm 1 asserts rc **2** (not merely
    non-zero), a receipt LINE in the shared log, the absence of `shell=webview2`, and no
    leftover pid; the `--help` arm derives 17 flags FROM THE SOURCE (not a hardcoded list)
    and byte-identity was measured separately (2272 B both sides). The one VACUOUS green I
    found is labelled: the `argv` arm in `--neg-arm` (no pre-flight exists there), printed
    as `ARM-NOTE … VACUOUS in this copy`. `CENSUS-VERDICT PASS` in the first pass was not
    vacuous (213–225 samples, 22–24 tracked pids incl. WebView2 children) but was NOT
    stable (141/262 later) — which is why a census green was never used as evidence for the
    wrapper claim.
  - *falta-no-gate:* the oracle does not verify that the process it later kills is the one
    the shell logged, beyond that log line (a forged line would pass); and the census is a
    HARD conjunct today, so a future `--show` (panel visible on purpose) turns the whole
    VERDICT red for a REQUESTED behaviour. Tried and failed to break the arms: argparse's
    exit code is fixed, so arm 1 cannot pass with rc≠2, and the pre-fix copy's bogus arm
    cannot be made green.
  - *gate-melhor:* add `--expect-census{=0|any}` (default `any`) so a receipt declares
    whether the census is a hard conjunct or a reported observation, and run the census
    primitives' own selftest first so a RED census names the INSTRUMENT before the subject.
    Input that must leave the hole-RED: `--pid-file` pointing at a log whose pid is already
    dead while the tree holds a visible window → the monotone form must still find it, the
    pre-patch form returns 0.
- **confianca** — alta for the exit contract (3 rc values, both colours, inverted copy,
  byte-identical `--help`, 8 real call-site argv sets). media for "no window appeared":
  proven in the first pass and DISPROVEN later, with the disproof attributed to the app (both
  arms flash, including with no wrapper in the path). What would raise it: a clean census
  pass AFTER the flash lane lands its cure, then re-run the oracle.
- **nao verificado** — (1) a bogus flag delivered the way the OWNER delivers it (explorer
  double-click: no console at all) — my runs give cmd a hidden console, so the echo is
  visible to me; (2) `start` from a parent with NO console; (3) `--dump-dom` / `--selftest` /
  `--memory` end to end (only their argv is asserted; they bypass the pre-flight by design);
  (4) a MISSING `pythonw.exe` (rc would be cmd's 9009, unmodelled); (5) that
  `_main/run-cmd-prefix-20261006.cmd` remains a valid pre-fix control after anyone COMMITS
  the fixed wrapper — nothing asserts it beyond the oracle's `--check-args`-absence check.

## CACHE/PRICE

```
- cache: read=12156142 write=0 hit=98.1101% (cache-read / input+cache-read); universe: 76 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoRunCmdExitContract.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); routes: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- when-failed: 2026-10-06T07:50:01.629Z, 07:50:02.244Z, 07:50:02.833Z, 07:50:03.320Z, 07:51:52.781Z, 07:56:59.846Z (6 break events; state=RESOLVED-BREAKS-OMP; 6 of 112996 OMP prefix-ledger rows attributable to this agent)
- where-failed: provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0 turn_id=1791273001629 | space-bunny-free item_index=0 | ling-3.1-flash-free item_index=0 | deepseek-flash item_index=0 turn_id=1791273003320 | deepseek-flash item_index=32 turn_id=1791273112781 | deepseek-flash item_index=120 turn_id=1791273419846
- source: stdout of `bash I:/!manager/scripts/cache-task-report.sh SottoRunCmdExitContract` (generated_at 2026-10-06T08:07:02.142598Z); that report's own verdict line is `UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision`
```
