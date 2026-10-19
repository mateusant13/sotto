@echo off
REM ===========================================================================
REM  Sotto -- THE APP.  Double-click this file, or run it from a terminal.
REM
REM    run.cmd                  TRANSCRIBE, wait for Alt+C; the panel stays
REM                              HIDDEN unless you ask for it -- it is not
REM                              mapped at full opacity while nobody asked (the
REM                              navigation Show gate; 25 ms census `live` 0/20 vs
REM                              `nogate` 4/20). That is not a promise about pixels:
REM                              the alpha=0 creation-dance map remains, and the
REM                              SAME census read 18/20 in an earlier pass -- the
REM                              two numbers are UNRECONCILED in AGENTS.md. See
REM                              _main/receipt-20261007-panel-startup-flash.md.
REM    run.cmd --show           start with the panel already up
REM    run.cmd --no-worker      shell only: start NO transcription worker
REM    run.cmd --with-worker    accepted alias -- the worker is the default
REM    run.cmd --help           every flag
REM
REM  THE WORKER STARTS BY DEFAULT (F1, 2026-10-07). Until this change the flag
REM  was the other way round and `run.cmd` passed nothing, so Alt+C opened a
REM  panel reading "Waiting for audio" with no capture process in existence --
REM  the owner's acceptance ("alt c mostra as transcricoes em tempo real")
REM  failing on the most obvious path. The default now lives in the shell
REM  (`sotto_webview.py`), not in this wrapper, so there is no second flag
REM  table here to drift: `--no-worker` turns it off and `--with-worker` only
REM  FORCES it past an automatic opt-out.
REM
REM  The WebView2 shell (sotto_webview.py) is the app. The panel it hosts is
REM  app\panel\. The EARLIER shell is app\_legacy-electron\ -- kept only for its
REM  own files and for comparison, not as a fallback; nothing here reaches for it.
REM
REM  NO CONSOLE WINDOW. A normal launch goes through pythonw.exe, which is a
REM  GUI-subsystem binary: Windows allocates no console for it. Measured on this
REM  box (Start-Process pythonw, detached):
REM      stdout=None stderr=None GetConsoleWindow()=0
REM  (`_main\webview-pythonw-console.json`) ? so the `print()` in the shell's
REM  log() is a no-op there, which is why run.cmd passes --log and the run's
REM  receipt is the FILE, not the screen.
REM
REM  THERE IS NO FALLBACK TO python.exe (gap G4, 2026-10-06). When pythonw.exe
REM  was absent the wrapper used to run the app under python.exe -- a CONSOLE
REM  binary, i.e. a console WINDOW on the owner's screen. It now refuses loudly
REM  and exits 3, windowless. See the `PYW` block below.
REM
REM  A LAUNCH REPORTS A HANG (gap G3, 2026-10-06). `start` detaches the app, so
REM  the wrapper used to answer 0 no matter what happened next -- measured: a
REM  launch stopped at STAGING_LOADED and run.cmd still said 0
REM  (docs/audit/launch-entry.md ?3/?4). A FRESH ready-file now travels with the
REM  app; the shell touches it once the panel navigation has completed, and
REM  run.cmd waits for it, BOUNDED, exiting 4 on timeout. It still does not wait
REM  for the app to EXIT -- the app lives for days by design.
REM
REM  --help and the --*-probe flags are the exception: they PRINT, so they run
REM  under python.exe and write to the terminal you already have. That creates
REM  no new window; it uses yours. Native H:\ paths only -- a node-style
REM  ./ relative path does not execute on this box (rc=127, measured).
REM ===========================================================================

setlocal
set "HERE=%~dp0"
cd /d "%HERE%"

REM ---- THE REDUX LIVE OVERLAY, ON BY DEFAULT (owner, 2026-10-18) -------------
REM WHY THIS LINE EXISTS HERE AND NOT ANYWHERE ELSE.
REM
REM The owner asked for the Parakeet to rewrite the closed lines. It was turned
REM on for the RUNNING shell by putting SOTTO_REDUX_LIVE=1 in that process's
REM environment -- which lasts exactly as long as that process. Measured
REM 2026-10-18: the value was also written to HKCU\Environment and
REM WM_SETTINGCHANGE was broadcast (the call returned success), and that is
REM NOT the same as the next launch inheriting it: a double-click here inherits
REM the EXPLORER's environment block, built at logon, and no instrument available
REM here can read what the Explorer will pass down. The probe that tried to ask
REM it answered with Path= set to PowerShell's own, i.e. it asked the wrong
REM process. So "configured and proven" was true for the shell in front of me
REM and unproven for the one the owner returns to -- which is the state that
REM made this line necessary.
REM
REM IT IS NOT HERE BECAUSE OF DRIFT. `WorkerBridge._child_env` builds the
REM child's environment as `dict(os.environ)` plus the keys the bridge owns, and
REM `_main/app-target-oracle.py` ARM e exists to hold that contract: "the env is
REM byte-identical to the pre-existing contract: os.environ + SOTTO_CAPTURE_MODE,
REM nothing else". Adding a default there was tried and turned ARM e RED, which
REM is the gate being right -- a bridge that quietly starts adding keys of its
REM own is how a second table appears. THIS file is the documented entry
REM ("Double-click it"), it already decides things the shell cannot see, and a
REM value set here is inherited by `start "" "%PYW%" ...` and by every child the
REM shell spawns from there.
REM
REM HOW TO TURN IT OFF: `set SOTTO_REDUX_LIVE=0` in the shell before running
REM this. The worker reads "0" and "1" as the only two values the environment
REM rung recognises (worker/sotto_worker.py `redux_live_settings`), and "0" is an
REM explicit off. The line below only ever supplies a value when there is none.
if not defined SOTTO_REDUX_LIVE set "SOTTO_REDUX_LIVE=1"

set "SHELL=%HERE%sotto_webview.py"
if not exist "%SHELL%" (
  echo run.cmd: %SHELL% is missing. The app cannot start.
  exit /b 3
)

REM ---- locate pythonw beside the interpreter `py -3` resolves ---------------
set "PYEXE="
for /f "delims=" %%I in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
if not defined PYEXE (
  for /f "delims=" %%I in ('where python 2^>nul') do if not defined PYEXE set "PYEXE=%%I"
)
if not defined PYEXE (
  echo run.cmd: no python found on this machine.
  exit /b 3
)
set "PYW=%PYEXE:python.exe=pythonw.exe%"
REM ---- G4: NO FALLBACK to the console interpreter ---------------------------
REM Until 2026-10-06 the next line read `if not exist "%PYW%" set "PYW=%PYEXE%"`,
REM which put the app on the owner's screen under python.exe -- a CONSOLE
REM binary, i.e. a console WINDOW -- when pythonw.exe was absent. The owner has
REM said three times: never a visible console. A machine with python.exe and no
REM pythonw.exe is now a loud, windowless refusal, not a degraded run. (This is
REM why the pre-flight below also runs on %PYW%: with the fallback gone, %PYW%
REM can no longer silently become the console interpreter.)
if not exist "%PYW%" (
  echo run.cmd: no pythonw.exe beside %PYEXE%.
  echo run.cmd: refusing to fall back to python.exe -- that opens a console window.
  exit /b 3
)

REM ---- flags that must PRINT go to the console interpreter ----------------
set "NEEDS_STDOUT="
REM `--check-args` is the pre-flight's OWN switch: asked for it, the pre-flight
REM IS the action (see below), so the wrapper must not then `start` the app.
set "CHECK_ARGS_ONLY="
for %%A in (%*) do (
  if /I "%%~A"=="--help"       set "NEEDS_STDOUT=1"
  if /I "%%~A"=="-h"           set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--dump-dom"  set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--selftest"  set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--memory"    set "NEEDS_STDOUT=1"
  REM The autostart modes PRINT their result (what was written to, or removed
  REM from, HKCU\...\Run, and whether it still points at THIS checkout), so they
  REM need the console interpreter for the same reason --help does: under
  REM pythonw their output would be a no-op and the owner would see nothing.
  if /I "%%~A"=="--install-autostart"   set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--uninstall-autostart" set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--autostart-status"    set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--check-args" set "CHECK_ARGS_ONLY=1"
)

if defined NEEDS_STDOUT (
  "%PYEXE%" "%SHELL%" %*
  exit /b %ERRORLEVEL%
)

REM ---- PRE-FLIGHT: the child's OWN parser decides, before anything runs -----
REM Measured 2026-10-06 (lane SottoRunCmdEntry): `run.cmd --bogus-flag` exited 0
REM with no log bytes, no shell line and no process. argparse rejects the flag
REM and exits 2 on pythonw.exe, whose stdout is None, and `start` reports only
REM its OWN success -- so a rejected flag answered as success. Same family as
REM the rest of this round: a failure answering as success.
REM
REM `start` is KEPT: a wrapper that waited for the app would hold the caller's
REM console for the whole session, and the app is meant to sit hidden for days.
REM The child's status is taken where it can still be seen -- in this run, which
REM STARTS NOTHING. pythonw keeps it windowless. The flag table it validates
REM against is the shell's own argparse, so there is no second copy in batch to
REM drift from the shell; --check-args is hidden from `--help` for that reason.
set "PREFLIGHT_RC=0"
REM G5: give the pre-flight interpreter a HANDLE. pythonw writes nowhere on its
REM own (stdout and stderr are None), and MEASURED 2026-10-12: the SAME
REM `--check-args --bogus-flag` run delivers 757 B of argparse usage/error when a
REM file handle is provided and 0 B when it is not. So the message was never
REM "discarded by pythonw" -- nobody had given it somewhere to go. %TEMP% is used
REM instead of _main\ so that a wrapper copied elsewhere cannot fail HERE: with an
REM unwritable target cmd would not run the child at all and a GOOD list would be
REM refused, which is worse than a lost message.
REM THE REFUSAL CAPTURE LIVES BESIDE THE LOG, NOT IN %TEMP%.
REM MEASURED 2026-10-14, and it is a start-stopping defect: the SAME command,
REM the SAME interpreter, the ONLY difference the redirect target --
REM   2>G:\Temp\sotto-preflight-refusal.txt   -> rc 120  and the app will not start
REM   2>I:\cc-tmp\rf.txt                       -> rc 2, the argparse text present
REM rc 120 is what cmd answers when it cannot give the child the redirect it was
REM told to give it, so a machine whose %TEMP% is full, read-only or on a drive that
REM refuses the write gets a wrapper that REFUSES A GOOD LAUNCH and prints nothing
REM the caller can act on. This program is going to be used by thousands of people
REM and %TEMP% is a property of THEIR machine, not of ours.
REM
REM _main\ is the one directory this wrapper already proves writable: the same
REM pre-flight writes its receipt there through run-cmd-log-append.py. So the
REM capture goes beside the log it is a receipt FOR, and it carries the run id so
REM two launches cannot collide on the name.
REM THE REFUSAL CAPTURE GOES BESIDE THE LOG, AND THE PATH IS RESOLVED, NOT WRITTEN BY HAND.
REM MEASURED 2026-10-15, and this is a defect MY OWN cure introduced: a batch file with
REM CRLF eats backslashes in some `cmd /c` invocations, and a hand-written `%HERE%..\..`
REM relative path then resolved to `app\webview\sottoappwebviewsotto_webview.py` -- with
REM every `\s` and `\w` gone. pythonw could not open it, the capture landed in the WRONG
REM directory as a file named `-preflight-refusal.txt` (the `sotto-preflight-refusal-`
REM prefix and both %RANDOM% halves eaten with the same backslashes), and the caller got a
REM refusal whose text was an ENOENT instead of the argparse usage.
REM
REM `for ... in (path) do set X=%%~fI` RESOLVES the path to a normalised absolute one, which
REM is immune to the eaten-backslash class of bug. This is the same reason run.cmd already
REM uses %%~fI-style expansion elsewhere instead of string arithmetic on paths.
for /f "delims=" %%I in ("%HERE%..\..\_main\") do set "LOGDIR=%%~fI"
if not exist "%LOGDIR%" set "LOGDIR=%HERE%"
set "REFUSAL=%LOGDIR%sotto-preflight-refusal-%RANDOM%%RANDOM%.txt"
if exist "%REFUSAL%" del /q "%REFUSAL%" >nul 2>&1
"%PYW%" "%SHELL%" --check-args %* 2>"%REFUSAL%"
set "PREFLIGHT_RC=%ERRORLEVEL%"
if not "%PREFLIGHT_RC%"=="0" (
  echo run.cmd: the shell REFUSED this launch ^(rc=%PREFLIGHT_RC%^). Nothing was started.
  REM The interpreter OWN words: WHICH flag, not only the class of refusal.
  if exist "%REFUSAL%" type "%REFUSAL%"
  echo run.cmd: rc=2 is a bad flag, rc=3 a missing panel, rc=1 a missing pywebview. "run.cmd --help" lists the flags.
  REM The receipt, in the same file a normal launch writes to: without it a
  REM rejected list would leave the log with NO bytes at all (measured 2026-10-06).
  REM MEASURED AGAIN 2026-10-12, WITH THE APP RUNNING: cmd.exe own `>>` append
  REM onto that file is REFUSED with error 32 ("the file is already being used
  REM by another process") -- so BOTH receipts in this wrapper were silent
  REM exactly when the app is up, and the Windows autostart task registered
  REM 2026-10-12 keeps it up by default. Same probe, same instant: cmd 0 bytes,
  REM python +17 bytes. So the receipt goes through python, which CAN open the
  REM file (pythonw, windowless). The helper is _main\run-cmd-log-append.py.
  "%PYW%" "%HERE%run-cmd-log-append.py" "%HERE%..\..\_main\webview-run.log" --append-file "%REFUSAL%" --line "sotto: PREFLIGHT_REFUSED rc=%PREFLIGHT_RC% by=run.cmd-preflight"
  exit /b %PREFLIGHT_RC%
)
if exist "%REFUSAL%" del /q "%REFUSAL%" >nul 2>&1
REM Asked for the pre-flight itself, the pre-flight IS the action: return its
REM status and start nothing. Until 2026-10-06 `run.cmd --check-args` passed the
REM pre-flight and then `start`ed the app, which returned 0 having opened
REM nothing -- a second way for "nothing happened" to answer as success
REM (docs/audit/launch-entry.md, ?2).
if defined CHECK_ARGS_ONLY exit /b %PREFLIGHT_RC%

REM ---- normal launch: pythonw, detached, with a log file the run can leave --
REM A default log so a hidden run still leaves a receipt. An explicit --log
REM on the command line wins; batch cannot test for that cheaply, so the
REM default is only appended when the user did not already pass one.
REM
REM G3: a FRESH ready-file travels with the app, and the shell TOUCHES it the
REM moment the panel navigation has completed (`mark_launch_ready`, after
REM PRELOAD_ACTIVE). The wait for it is BOUNDED and reports a HANG, which the
REM detached `start` alone could never do -- measured 2026-10-06 a launch
REM stopped at STAGING_LOADED and run.cmd still answered 0 (see
REM docs/audit/launch-entry.md ?3/?4). It does NOT wait for the app to EXIT:
REM the app is meant to sit hidden for days; only the readiness handshake is
REM bounded. SOTTO_READY_BOUND overrides the bound (default 30 s) so a test can
REM shorten it; the whole wait lives in the shell's `--wait-ready` mode, so it
REM needs neither a terminal nor a batch sleep.
set "READY_FILE=%HERE%..\..\_main\ready-%RANDOM%-%RANDOM%.txt"
if exist "%READY_FILE%" del /q "%READY_FILE%" >nul 2>&1

set "PASSED_LOG="
for %%A in (%*) do (
  if /I "%%~A"=="--log" set "PASSED_LOG=1"
)
if defined PASSED_LOG (
  start "" "%PYW%" "%SHELL%" %* --ready-file "%READY_FILE%"
) else (
  REM The path is left as the repo-relative walk: the shell resolves it, and
  REM MEASURED to land the file at H:\sotto\_main\webview-run.log. Normalising
  REM it with `for %%I in ("%HERE%..\..\_main")` was tried and REJECTED: cmd
  REM mangles the quoted argument and the run then wrote no log at all.
  start "" "%PYW%" "%SHELL%" --log "%HERE%..\..\_main\webview-run.log" %* --ready-file "%READY_FILE%"
)

REM ---- G3: the bounded readiness wait, and the HANG report ------------------
"%PYW%" "%SHELL%" --wait-ready "%READY_FILE%"
set "READY_RC=%ERRORLEVEL%"
del /q "%READY_FILE%" >nul 2>&1
if not "%READY_RC%"=="0" (
  echo run.cmd: the app did not report READY in time ^(rc=%READY_RC%^) -- a HANG, not a start.
  echo run.cmd: it was started and did not come up; see _main\webview-run.log.
  "%PYW%" "%HERE%run-cmd-log-append.py" "%HERE%..\..\_main\webview-run.log" --line "sotto: HANG rc=4 by=run.cmd-readiness"
  exit /b 4
)
exit /b 0