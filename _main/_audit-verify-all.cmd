@echo off
REM ===========================================================================
REM  Sotto -- the whole verification battery in one command, AND IT SAYS NO.
REM
REM    _main\_audit-verify-all.cmd            run everything; exit 0 ONLY if every
REM                                           step held and every control went RED
REM
REM  Every step prints a `[step] name rc=N` beacon to the console and the full
REM  output to _main\_audit-verify\*.log, so a claim in the receipt can be
REM  re-checked without re-reading this file. Nothing here starts a window, an
REM  audio device, or the app: the app itself cannot run in this session's
REM  sandbox (pythonnet is denied), which is why the battery is all DOM-free
REM  oracles and compile checks.
REM
REM  ---------------------------------------------------------------------------
REM  AGGREGATION -- added 2026-10-08. WHY IT EXISTS (measured, not imagined):
REM  this file used to print each step's rc and then `exit /b 0` unconditionally,
REM  so a run with THREE red steps (`hotkey-delivery` rc=1, `verdict-gate` rc=2,
REM  `history-producer-gate` rc=1) exited 0. The file everyone quoted as "the
REM  battery is green" could report success while steps were red -- the exact
REM  defect class this repo has been fighting: a failure answering as success.
REM
REM  Now every step's rc is recorded and the batch exits NON-ZERO if ANY step
REM  failed, printing a final summary: total steps, the per-step rc list, the
REM  controls seen, and the names of the failed ones.
REM
REM  FOUR KINDS OF STEP, and the difference matters to a reader:
REM    gate        succeeds when it exits 0                  (:record)
REM    control     succeeds ONLY by catching a deliberately-broken COPY, so it
REM                must exit 0 AND print its own control verdict. A control that
REM                does NOT go red is a FAILURE here, never a pass.       (:control)
REM    skipped     an arm the environment can make UNRUNNABLE (the Alt+C delivery
REM                arm, while the owner's app holds the key): rc=0 AND EITHER the
REM                instrument's skip verdict -- then it is counted in `skipped=` and
REM                NEVER in `gate=`, because it did not verify anything -- OR its
REM                verified verdict, then it counts as a real gate. Neither verdict
REM                present is a FAILURE: a step that cannot say what it did is not a
REM                pass.                                            (:skipped)
REM    expect-red  an instrument with no control mode of its own, run in the mode
REM                that is RED BY DESIGN: it must exit 1 (the defect found) and
REM                print the violation. rc=0 means the defect did not appear,
REM                rc=2 is a setup error -- both are failures here.  (:expectred)
REM  The summary prints which steps are controls and which are skipped, and the
REM  `skipped=` column is the part of the green that is NOT CLAIMED. When the owner
REM  closes the app, that arm stops being skipped and moves from `skipped=` to
REM  `gate=` in the same line -- the transition is visible, never silent.
REM
REM  THE SKIP GUARD closes the other direction: after every step has written its log,
REM  one sweep fails the run if any STEP log carries `VERDICT: SKIPPED` while its step
REM  is not declared skip-capable. An instrument that skips an arm and still exits 0
REM  must not be printed as a pass by a battery that cannot see it.       (skip-verdict-guard)
REM  "STEP log" is load-bearing: the battery's OWN console carries the same literal
REM  text (its beacon ECHOES it), so a sweep that reads the console fails on its own
REM  output -- measured, and cured at the step below.
REM
REM  A MISSING INSTRUMENT IS A FAILURE, NEVER A PASS: a step whose file does not
REM  exist is recorded as rc=MISSING and fails the run. `else ( echo ... MISSING )`
REM  used to be a line on a screen; now it is a red step.
REM
REM  THIS FILE MUST KEEP CRLF LINE ENDINGS. MEASURED 2026-10-08, the first run of
REM  the aggregating version: written LF-only, the batch executed its step list
REM  TWICE and printed TWO summaries -- pass 1 skipped 13 steps and reported
REM  `steps : 16` GREEN, then cmd resumed and re-ran the skipped steps plus the
REM  whole tail, printing a second summary with `steps : 40`. Every beacon was
REM  duplicated (2 model loads, 2 of every control). The subroutines are reached
REM  by `call :label` / `exit /b`, and cmd seeks a batch file by BYTE OFFSET:
REM  with 1-byte LF endings those stored offsets drift, so the interpreter
REM  resumes at the wrong line. Converted to CRLF the same file ran the step list
REM  ONCE (`steps : 29`). If you rewrite this file with a tool that writes `\n`,
REM  convert it back (`-replace "\n", "\r\n"`) or the aggregation will lie.
REM ===========================================================================
setlocal EnableDelayedExpansion
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "OUT=%ROOT%\_main\_audit-verify"
if not exist "%OUT%" mkdir "%OUT%"

set "N=0"
set "GATES=0"
set "CTRLS=0"
set "SKIPN=0"
set "REDS=0"
set "MISSINGN=0"
set "BAD=0"
set "STEPLIST="
set "FAILED="
set "CONTROLLIST="
set "SKIPLIST="
REM Basenames of the logs whose step is DECLARED skip-capable and really skipped this
REM run -- the only logs the skip guard below is allowed to see a skip verdict in.
set "SKIPLOGS=,"

echo === compile checks ===
python -m py_compile app\webview\sotto_webview.py > "%OUT%\pycompile-webview.log" 2>&1
call :record pycompile-sotto_webview !ERRORLEVEL!
python -m py_compile app\webview\hot_reload.py app\webview\panel_state.py > "%OUT%\pycompile-webview-helpers.log" 2>&1
call :record pycompile-webview-helpers !ERRORLEVEL!
python -m py_compile worker\sotto_worker.py > "%OUT%\pycompile-worker.log" 2>&1
call :record pycompile-sotto_worker !ERRORLEVEL!
python -m py_compile worker\wasapi_loopback.py worker\lang_prompt.py > "%OUT%\pycompile-capture.log" 2>&1
call :record pycompile-wasapi+lang !ERRORLEVEL!

echo === the panel/engine oracles that were GREEN before the fixes ===
node app\_legacy-electron\transcript-append-oracle.js > "%OUT%\oracle-transcript-append.log" 2>&1
call :record transcript-append-oracle !ERRORLEVEL!
node _main\live-vs-history-source-oracle.js > "%OUT%\oracle-live-vs-history.log" 2>&1
call :record live-vs-history-source-oracle !ERRORLEVEL!
node _main\historico-vs-redux-probe.js > "%OUT%\oracle-historico-vs-redux.log" 2>&1
call :record historico-vs-redux-probe !ERRORLEVEL!

echo === the gates added by this round ===
if exist _main\history-producer-gate.js (
  node _main\history-producer-gate.js > "%OUT%\gate-history-producer.log" 2>&1
  call :record history-producer-gate !ERRORLEVEL!
) else ( call :record history-producer-gate MISSING )
if exist _main\panel-state-guard-gate.js (
  node _main\panel-state-guard-gate.js > "%OUT%\gate-panel-state-guard.log" 2>&1
  call :record panel-state-guard-gate !ERRORLEVEL!
) else ( call :record panel-state-guard-gate MISSING )
if exist _main\verdict-gate.py (
  python _main\verdict-gate.py > "%OUT%\gate-verdict.log" 2>&1
  call :record verdict-gate !ERRORLEVEL!
) else ( call :record verdict-gate MISSING )

echo === the per-lane probes ===
if exist _main\_lane2-reset-probe.js (
  node _main\_lane2-reset-probe.js > "%OUT%\lane2-reset.log" 2>&1
  call :record lane2-reset-probe !ERRORLEVEL!
) else ( call :record lane2-reset-probe MISSING )
if exist _main\_lane3-verdict-probe.py (
  python _main\_lane3-verdict-probe.py > "%OUT%\lane3-verdict.log" 2>&1
  call :record lane3-verdict-probe !ERRORLEVEL!
) else ( call :record lane3-verdict-probe MISSING )
if exist _main\_lane4-tap-stop-probe.py (
  python _main\_lane4-tap-stop-probe.py > "%OUT%\lane4-tap-stop.log" 2>&1
  call :record lane4-tap-stop-probe !ERRORLEVEL!
) else ( call :record lane4-tap-stop-probe MISSING )
if exist _main\_audit-history-dead.js (
  node _main\_audit-history-dead.js > "%OUT%\audit-history-dead.log" 2>&1
  call :record audit-history-dead !ERRORLEVEL!
) else ( call :record audit-history-dead MISSING )

echo === the panel's row-identity rule: the SAME probe, both colours (gate here, control in CONTROLS) ===
REM `_panel2-repeat-probe.js` has no `--control-*` flag: its control mode IS `--revert`, whose
REM mutant COPY of panel.js is built inline. Wiring BOTH halves means one battery run shows the
REM rule holding on the shipped panel AND the probe able to go RED without it. This row is the
REM GREEN half; `control-panel2-repeat-revert` is the control.
if exist _main\_panel2-repeat-probe.js (
  node _main\_panel2-repeat-probe.js > "%OUT%\panel2-repeat.log" 2>&1
  call :record panel2-repeat-probe !ERRORLEVEL!
) else ( call :record panel2-repeat-probe MISSING )

echo === the day/hour gallery: the module arithmetic, and the DOM that shows it ===
REM Two instruments, two claims. `history-gallery-oracle.js` requires the SHIPPED
REM `app/panel/history-gallery.js` as a plain module (no DOM, no jsdom) and checks the
REM bucketing plus the LOCAL-time stamp; its `--neg-arm` is the control row below.
REM `_panel2-dom-probe.js` is the jsdom probe that presses the real buttons in the real
REM document -- 78 arms, ARM G being the gallery's. Measured 2026-10-08: GREEN 78/78 on
REM the shipped panel, and RED on exactly the two arms that name the auto-append the
REM owner had removed when the same probe was pointed at a mutant copy via
REM `SOTTO_PANEL_DIR` (the other 76 stayed green).
if exist _main\history-gallery-oracle.js (
  node _main\history-gallery-oracle.js > "%OUT%\gallery-oracle.log" 2>&1
  call :record history-gallery-oracle !ERRORLEVEL!
) else ( call :record history-gallery-oracle MISSING )
if exist _main\_panel2-dom-probe.js (
  node _main\_panel2-dom-probe.js > "%OUT%\panel2-dom-probe.log" 2>&1
  call :record panel2-dom-probe !ERRORLEVEL!
) else ( call :record panel2-dom-probe MISSING )

echo === the wiring and the embedded JS (the two things the other gates cannot see) ===
if exist _main\_audit-worker-start-wiring.py (
  python _main\_audit-worker-start-wiring.py > "%OUT%\wiring-worker-start.log" 2>&1
  call :record worker-start-wiring !ERRORLEVEL!
) else ( call :record worker-start-wiring MISSING )
if exist _main\_audit-embedded-js-check.py (
  python _main\_audit-embedded-js-check.py > "%OUT%\embedded-js.log" 2>&1
  call :record embedded-js-check !ERRORLEVEL!
) else ( call :record embedded-js-check MISSING )
if exist _main\_lane1-worker-default-arms.py (
  python _main\_lane1-worker-default-arms.py > "%OUT%\lane1-arms.log" 2>&1
  call :record lane1-worker-default-arms !ERRORLEVEL!
) else ( call :record lane1-worker-default-arms MISSING )

echo === the adversary lane's probes (corrected: the filters it wrote were RED-forever) ===
if exist _main\_review-f1f3.py (
  python _main\_review-f1f3.py > "%OUT%\review-f1f3.log" 2>&1
  call :record review-f1f3 !ERRORLEVEL!
) else ( call :record review-f1f3 MISSING )
if exist _main\_review-tapstop.py (
  python _main\_review-tapstop.py > "%OUT%\review-tapstop.log" 2>&1
  call :record review-tapstop !ERRORLEVEL!
) else ( call :record review-tapstop MISSING )

echo === the strip surface, the wave, and the hot reload that must never wait forever ===
REM Five instruments from the strip-surface lane. The ORACLE builds FOUR broken
REM copies of today's shell (the JS member removed, the dispatch routing removed,
REM the CSS height blinded, the per-sample log restored) and requires each to go
REM RED on its own claim -- so it is a `:control`, and it prints its control
REM verdict. The LOG probe does the same with ONE copy (the per-sample push) and
REM prints its own. The other three are plain gates: each exits 0 only after its
REM arms held, and each is launched with `--no-worker`/`--no-hotkey` so no model
REM is loaded and no audio device is opened.
if exist _main\_strip-surface-oracle.py (
  python _main\_strip-surface-oracle.py > "%OUT%\strip-surface-oracle.log" 2>&1
  call :control strip-surface-oracle !ERRORLEVEL! "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS"
) else ( call :control strip-surface-oracle MISSING "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS" )
if exist _main\_strip-stats-log-probe.py (
  python _main\_strip-stats-log-probe.py > "%OUT%\strip-stats-log.log" 2>&1
  call :control strip-stats-log-budget !ERRORLEVEL! "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS"
) else ( call :control strip-stats-log-budget MISSING "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS" )
if exist _main\_strip-reload-probe.py (
  python _main\_strip-reload-probe.py > "%OUT%\strip-reload.log" 2>&1
  call :record strip-hot-reload !ERRORLEVEL!
) else ( call :record strip-hot-reload MISSING )
if exist _main\_strip-surface-probe.py (
  python _main\_strip-surface-probe.py > "%OUT%\strip-surface.log" 2>&1
  call :record strip-surface-runtime !ERRORLEVEL!
) else ( call :record strip-surface-runtime MISSING )
if exist _main\_strip-restore-probe.py (
  python _main\_strip-restore-probe.py > "%OUT%\strip-restore.log" 2>&1
  call :record strip-geometry-restore !ERRORLEVEL!
) else ( call :record strip-geometry-restore MISSING )
if exist _main\_strip-stats-probe.py (
  python _main\_strip-stats-probe.py > "%OUT%\strip-stats.log" 2>&1
  call :record strip-stats-wave !ERRORLEVEL!
) else ( call :record strip-stats-wave MISSING )

echo === Alt+C, the only control: registration table, delivery+fallback+mutex, autostart ===
if exist _main\_audit-hotkey-probe.py (
  python _main\_audit-hotkey-probe.py > "%OUT%\hotkey-registration.log" 2>&1
  call :record hotkey-registration !ERRORLEVEL!
) else ( call :record hotkey-registration MISSING )
if exist _main\_audit-hotkey-delivery.py (
  python _main\_audit-hotkey-delivery.py > "%OUT%\hotkey-delivery.log" 2>&1
  call :skipped hotkey-delivery !ERRORLEVEL! "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim"
) else ( call :skipped hotkey-delivery MISSING "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim" )
REM The autostart check READS the registry (a read needs no elevation) and fails
REM if the Run value points somewhere other than THIS checkout -- which is what a
REM moved tree looks like from the login side.
python app\webview\sotto_webview.py --autostart-status > "%OUT%\autostart-status.log" 2>&1
call :record autostart-status !ERRORLEVEL!

echo === CONTROLS: every one of these succeeds ONLY by going RED on a broken copy ===
REM ---------------------------------------------------------------------------
REM These are the arms that had ROTTED because nothing ever ran them. A control
REM that is never executed silently stops being a control: `verdict-gate.py
REM --control-unguard-captions-zero` and `history-producer-gate.js
REM --control-stamp-nvidia` both sat exiting 2 (a setup error, i.e. no control at
REM all) with every gate around them green. They are steps now, and the summary
REM marks them as controls.
REM
REM Each line requires BOTH: the instrument's rc=0 -- which each of these returns
REM ONLY after it has built its broken copy and seen the gate go RED on it -- AND
REM the control verdict text in the log, quoted with python (ASCII substrings, so
REM a console-codepage mojibake cannot hide a missing verdict). rc=0 without the
REM text is a failure here, and so is a MISSING instrument.
REM ---------------------------------------------------------------------------
if exist _main\verdict-gate.py (
  python _main\verdict-gate.py --control-unguard-captions-zero > "%OUT%\control-verdict-gate-unguard.log" 2>&1
  call :control control-verdict-gate-unguard !ERRORLEVEL! "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS"
) else ( call :control control-verdict-gate-unguard MISSING "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS" )
if exist _main\history-producer-gate.js (
  node _main\history-producer-gate.js --control-stamp-nvidia > "%OUT%\control-history-producer-stamp-nvidia.log" 2>&1
  call :control control-history-producer-stamp-nvidia !ERRORLEVEL! "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS"
) else ( call :control control-history-producer-stamp-nvidia MISSING "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS" )
REM `redux-flag-gate.py --neg-arm` already runs the shipped pair GREEN and then
REM builds one mutant COPY per claim, requiring each to go RED on its own claim
REM ONLY; rc=0 is that conjunction. This is the superset of the plain gate, which
REM is why the plain form is not a separate step.
if exist _main\redux-flag-gate.py (
  python _main\redux-flag-gate.py --neg-arm > "%OUT%\control-redux-flag-neg-arm.log" 2>&1
  call :control control-redux-flag-neg-arm !ERRORLEVEL! "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN"
) else ( call :control control-redux-flag-neg-arm MISSING "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN" )
REM `--unit --neg-arm` is the no-shell half: the classifier's arms, the `done`
REM mapping and the recovery arm, plus two reverted COPIES of today's shell that
REM must go RED. rc=0 requires every one of those; the JSON keys `neg_arm` /
REM `neg_arm_e` prove the control halves actually ran rather than being skipped.
if exist _main\panel-exit3-oracle.py (
  python _main\panel-exit3-oracle.py --unit --neg-arm > "%OUT%\control-panel-exit3-neg-arm.log" 2>&1
  call :control control-panel-exit3-neg-arm !ERRORLEVEL! "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e"
) else ( call :control control-panel-exit3-neg-arm MISSING "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e" )
REM `wasapi-com-init-oracle.py` with NO flag is already both colours in one
REM command: the live module must PASS and the recorded pre-fix copy must be RED.
REM It opens no audio device by construction (stubbed `_ole32`, arms 5-6 only
REM CoInitialize/CoUninitialize). Its own `--neg-arm` is the pre-fix copy ALONE --
REM a debug subset of this run -- so the plain form is what is wired.
if exist _main\wasapi-com-init-oracle.py (
  python _main\wasapi-com-init-oracle.py > "%OUT%\control-wasapi-com-init.log" 2>&1
  call :control control-wasapi-com-init !ERRORLEVEL! "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS"
) else ( call :control control-wasapi-com-init MISSING "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS" )
REM `_panel2-repeat-probe.js --revert` is the row-identity rule's negative control: it builds a COPY
REM of `app/panel/panel.js` with the identity lookup disabled, and all four arms must then FAIL.
REM TWO verdict strings are required, not one, because this probe's failure mode was not a wrong
REM verdict but an UNREACHABLE one: rc=1 with a `TypeError` and no `RESULT:` line at all, and the
REM mutant left on disk, in BOTH colours (measured 2026-10-08 against the pre-fix revision). rc=0 now
REM means the arms ran, the control went RED, and the mutant was removed.
if exist _main\_panel2-repeat-probe.js (
  node _main\_panel2-repeat-probe.js --revert > "%OUT%\control-panel2-repeat-revert.log" 2>&1
  call :control control-panel2-repeat-revert !ERRORLEVEL! "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true"
) else ( call :control control-panel2-repeat-revert MISSING "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true" )
REM `history-gallery-oracle.js --neg-arm` injects the bare-date stamp
REM (`new Date(entry.date)`) into a COPY of the module's parse and requires the LOCAL-time
REM arm to go RED while the stamp-independent arms stay green. The box is GMT-0300
REM (offsetMinutes=180, printed by the run), so the trap is OBSERVABLE here; on a UTC box
REM the same injection moves nothing and the oracle says so instead of claiming a control
REM it did not have -- that vacuity is the failure this row exists to catch.
if exist _main\history-gallery-oracle.js (
  node _main\history-gallery-oracle.js --neg-arm > "%OUT%\control-history-gallery-neg-arm.log" 2>&1
  call :control control-history-gallery-neg-arm !ERRORLEVEL! "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true"
) else ( call :control control-history-gallery-neg-arm MISSING "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true" )
REM `historico-vs-redux-probe.js --gate-off` has NO control mode of its own: the
REM flag loads the store with the one guard line DELETED, so the probe is RED BY
REM DESIGN and exits 1 (its own "FAIL" code) with the violation named. That is why
REM this one is :expectred and not :control.
if exist _main\historico-vs-redux-probe.js (
  node _main\historico-vs-redux-probe.js --gate-off > "%OUT%\control-historico-gate-off.log" 2>&1
  call :expectred red-as-expected-historico-gate-off !ERRORLEVEL! "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript"
) else ( call :expectred red-as-expected-historico-gate-off MISSING "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript" )

echo === the heavy one LAST: loads the int8 model, opens NO device ===
if exist _main\_audit-fresh-processor-probe.py (
  python _main\_audit-fresh-processor-probe.py > "%OUT%\fresh-processor.log" 2>&1
  call :record fresh-processor-probe !ERRORLEVEL!
) else ( call :record fresh-processor-probe MISSING )

echo === the skip guard: NO step may print a skip verdict unless its kind declares it ===
REM Every step above wrote its log. An instrument that silently skips an arm and still
REM exits 0 is a skip wearing a pass, and the difference is visible only in its log --
REM so this single sweep refuses the whole run if ANY step's log carries a skip verdict
REM (`VERDICT: SKIPPED`) while that step is not declared skip-capable. The declared
REM logs are named by `:skipped` itself and handed to the instrument in `--exclude`.
REM
REM IT USED TO READ ITS OWN TRANSCRIPT -- measured 2026-10-08, do not narrow this
REM back. The sweep was an inline python that globbed `%OUT%\*.log` and excluded only
REM `_run-*`. The battery's own console, kept in `%OUT%` as `_battery-run-<ts>.log`,
REM carries the literal `VERDICT: SKIPPED` -- because `:skipped` ECHOES the skip text
REM in its beacon line -- so the guard failed the whole run for a DECLARED skip,
REM naming `_battery-run-20261007-130942.log` and `_battery-run-20261007-131528.log`.
REM A guard that fails on its own output is not measuring the steps. THE RULE NOW: a
REM STEP LOG is a `*.log` in `%OUT%` whose basename does NOT start with `_`, because
REM every artifact the battery itself writes is `_`-prefixed (`_battery-run-*`,
REM `_run-*`, `_skip-guard.log`, `_battery-summary.txt`) and a run console is a
REM transcript of the whole run, not the log of a step.
REM The instrument ALSO runs a five-arm control on EVERY invocation, so it cannot be
REM green by reading nothing. Both colours, one command each:
REM   python _main\_skip-verdict-guard.py --dir _main\_audit-verify --exclude ",hotkey-delivery.log,"   -> rc 0, 64 logs read
REM   python _main\_skip-verdict-guard.py --dir _main\_skip-guard-redcheck --exclude ","                   -> rc 1, names bogus-step.log only
if exist _main\_skip-verdict-guard.py (
  python _main\_skip-verdict-guard.py --dir "%OUT%" --exclude "!SKIPLOGS!" > "%OUT%\_skip-guard.log" 2>&1
  call :record skip-verdict-guard !ERRORLEVEL!
) else ( call :record skip-verdict-guard MISSING )

echo.
echo =============== BATTERY SUMMARY ===============
echo steps    : !N!   gate=!GATES!  control=!CTRLS!  skipped=!SKIPN!  expect-red=!REDS!  missing=!MISSINGN!
echo per-step : !STEPLIST!
echo controls : !CONTROLLIST!
if "!FAILED!"=="" ( set "FAILEDTEXT=-none-" ) else ( set "FAILEDTEXT=!FAILED!" )
if "!SKIPLIST!"=="" ( set "SKIPTEXT=-none-" ) else ( set "SKIPTEXT=!SKIPLIST!" )
echo failed   : !FAILEDTEXT!
echo skipped  : !SKIPTEXT!
if "!BAD!"=="0" (
  set "VERDICT=GREEN - every step held and every control went RED on its broken copy"
)
if "!BAD!"=="0" if not "!SKIPN!"=="0" (
  set "VERDICT=GREEN WITH !SKIPN! SKIPPED - !SKIPN! step(s) did NOT verify this run and are NOT counted as gates: !SKIPTEXT!"
)
if not "!BAD!"=="0" (
  set "VERDICT=RED - !BAD! step(s) failed"
)
echo BATTERY-VERDICT: !VERDICT!
echo receipts in %OUT%
>"%OUT%\_battery-summary.txt" echo steps=!N! gate=!GATES! control=!CTRLS! skipped=!SKIPN! expect-red=!REDS! missing=!MISSINGN! failed=!BAD!
>>"%OUT%\_battery-summary.txt" echo rcs: !STEPLIST!
>>"%OUT%\_battery-summary.txt" echo controls: !CONTROLLIST!
>>"%OUT%\_battery-summary.txt" echo skipped: !SKIPTEXT!
>>"%OUT%\_battery-summary.txt" echo failed: !FAILEDTEXT!
>>"%OUT%\_battery-summary.txt" echo exit-code: !BAD!
>>"%OUT%\_battery-summary.txt" echo BATTERY-VERDICT: !VERDICT!
REM The exit code IS the aggregation: 0 only when nothing failed. Nothing else in
REM this file may return 0 on a red step.
if not "!BAD!"=="0" exit /b 1
exit /b 0

REM ===========================================================================
REM  The recorders. Every step calls exactly one of these with its OWN rc as an
REM  argument, so no step can print a beacon without being counted.
REM ===========================================================================

REM :record <name> <rc>          -- an ordinary gate: rc=0 is the only pass.
:record
set /a N+=1
set /a GATES+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
if "%~2"=="0" (
  echo [step] %~1 rc=0
  exit /b 0
)
if /i "%~2"=="MISSING" (
  set /a MISSINGN+=1
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=MISSING"
  echo [step] %~1 MISSING  ** THE INSTRUMENT IS NOT THERE: a missing step is not a pass **
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  ** FAILED **
exit /b 0

REM :skipped <name> <rc> <log> <verified-text> <skip-text> [<skip-text-2>]
REM   For an arm the ENVIRONMENT can make unrunnable -- today the Alt+C delivery arm,
REM   which `_audit-hotkey-delivery.py` skips by design while the owner's live shell
REM   holds the key. Three outcomes, and no fourth:
REM     * rc<>0 or MISSING                 -> FAILURE (a step that exits non-zero has
REM                                           not "skipped", it has failed)
REM     * rc=0 AND the skip text(s) present -> SKIPPED: counted in `skipped=`, listed
REM                                           in the summary, and NEVER counted in
REM                                           `gate=`, because nothing was verified
REM     * rc=0 AND the verified text present, no skip text -> a REAL gate this run
REM     * rc=0 with NEITHER                -> FAILURE. This is the direction that
REM       matters: an instrument that cannot say whether it verified or skipped must
REM       not be rounded up to a pass, and a silent no-op posing as a skip is exactly
REM       the family this battery exists to kill.
REM   A second skip text makes the skip claim stronger: for this probe both
REM   `VERDICT: SKIPPED` AND `CANNOT claim` are required, so a stray mention of the
REM   word in a verified run cannot be read as a skip.
:skipped
set /a N+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "WHY="
set "OUTCOME="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing step is not a pass, and it is not a skip either"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 - this step exits 0 whether it verifies or skips, so a non-zero rc is a FAILURE, not a skip"
if not defined WHY (
  call :hastext "%~3" "%~5"
  if "!HAS!"=="yes" set "OUTCOME=skipped"
)
if not defined WHY if not "%~6"=="" (
  call :hastext "%~3" "%~6"
  if not "!HAS!"=="yes" set "OUTCOME="
)
if not defined WHY if not defined OUTCOME (
  call :hastext "%~3" "%~4"
  if "!HAS!"=="yes" set "OUTCOME=verified"
)
if not defined WHY if not defined OUTCOME set "WHY=rc=0 but the log carries NEITHER the skip verdict (%~5) NOR the verified verdict (%~4) - the instrument cannot say what it did, and a step that cannot say is not a pass"
if defined WHY (
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=%~2"
  echo [step] %~1 rc=%~2  [SKIP-CAPABLE]  ** STEP FAILED: !WHY! **
  if /i "%~2"=="MISSING" set /a MISSINGN+=1
  exit /b 0
)
if "!OUTCOME!"=="skipped" (
  set /a SKIPN+=1
  set "SKIPLIST=!SKIPLIST! %~1"
  for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,"
  echo [step] %~1 rc=0  [SKIPPED] NOT VERIFIED: the instrument itself says this arm did not run, its own words being %~5
  exit /b 0
)
set /a GATES+=1
echo [step] %~1 rc=0  [SKIP-CAPABLE, verified this run] %~4 - the skip verdict is absent, so this IS a gate
exit /b 0

REM :control <name> <rc> <log> <required-text> [<required-text-2>]
REM   A control PASSES only when the instrument exits 0 (its own "the copy went
REM   RED" signal) AND its log carries the required verdict text. Anything else --
REM   a non-zero rc, a missing file, an rc=0 with no verdict in the log -- FAILS.
REM   The optional second text exists for a probe whose verdict can be unreachable
REM   (rc=1 and a traceback instead of a verdict): it lets the step demand a second,
REM   independent fact from the same run (e.g. that the mutant COPY was removed).
:control
set /a N+=1
set /a CTRLS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 and this step succeeds ONLY by catching its broken copy"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed the control verdict %~4 - the control did not report catching its copy"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=0  [CONTROL] went RED on the broken copy as required
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [CONTROL]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :expectred <name> <rc> <log> <required-text> [<required-text-2>]
REM   For an instrument whose RED-by-design mode has NO control wrapper. It must
REM   exit 1 -- the defect found -- and print the violation it found. rc=0 means
REM   the deliberately-broken copy was NOT caught (the control did not go red),
REM   and rc=2 is a setup error: both FAIL.
:expectred
set /a N+=1
set /a REDS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="1" if not defined WHY set "WHY=rc=%~2 - this step must find the injected defect and exit 1; rc=0 means the control did NOT go red, rc=2 is a setup error"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~4"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=1  [EXPECT-RED] the defect was found and named, as required
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [EXPECT-RED]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :hastext <file> <text>  -- sets HAS=yes|no. Read as BYTES and decoded as
REM UTF-8 so a console-codepage mojibake in the log cannot hide a verdict, and so
REM the required text may contain quotes or an em dash.
:hastext
set "HAS=no"
python -c "import io,sys;t=io.open(sys.argv[1],'rb').read().decode('utf-8','replace');sys.exit(0 if sys.argv[2] in t else 3)" "%~1" "%~2" >nul 2>&1
if "!ERRORLEVEL!"=="0" set "HAS=yes"
exit /b 0
