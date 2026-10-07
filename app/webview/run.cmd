@echo off
REM ===========================================================================
REM  Sotto -- THE APP.  Double-click this file, or run it from a terminal.
REM
REM    run.cmd                  start hidden, TRANSCRIBE, wait for Alt+C
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
"%PYW%" "%SHELL%" --check-args %*
set "PREFLIGHT_RC=%ERRORLEVEL%"
if not "%PREFLIGHT_RC%"=="0" (
  echo run.cmd: the shell REFUSED this launch ^(rc=%PREFLIGHT_RC%^). Nothing was started.
  echo run.cmd: rc=2 is a bad flag, rc=3 a missing panel, rc=1 a missing pywebview. "run.cmd --help" lists the flags.
  REM The receipt, in the same file a normal launch writes to: without it a
  REM rejected list would leave the log with NO bytes at all (measured).
  >>"%HERE%..\..\_main\webview-run.log" echo sotto: PREFLIGHT_REFUSED rc=%PREFLIGHT_RC% by=run.cmd-preflight
  exit /b %PREFLIGHT_RC%
)
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
  >>"%HERE%..\..\_main\webview-run.log" echo sotto: HANG rc=4 by=run.cmd-readiness
  exit /b 4
)
exit /b 0