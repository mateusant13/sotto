@echo off
REM ===========================================================================
REM  Sotto -- THE APP.  Double-click this file, or run it from a terminal.
REM
REM    run.cmd                  start hidden, wait for Alt+C
REM    run.cmd --show           start with the panel already up
REM    run.cmd --with-worker    also spawn worker\sotto_worker.py
REM    run.cmd --help           every flag
REM
REM  The WebView2 shell (sotto_webview.py) is the app. app\electron\ is the
REM  EARLIER shell and is kept only for its panel files and for comparison --
REM  it is not a fallback and nothing here reaches for it.
REM
REM  NO CONSOLE WINDOW. A normal launch goes through pythonw.exe, which is a
REM  GUI-subsystem binary: Windows allocates no console for it. Measured on this
REM  box (Start-Process pythonw, detached):
REM      stdout=None stderr=None GetConsoleWindow()=0
REM  (`_main\webview-pythonw-console.json`) — so the `print()` in the shell's
REM  log() is a no-op there, which is why run.cmd passes --log and the run's
REM  receipt is the FILE, not the screen.
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
if not exist "%PYW%" set "PYW=%PYEXE%"
if not exist "%PYW%" (
  echo run.cmd: no pythonw beside %PYEXE%.
  exit /b 3
)

REM ---- flags that must PRINT go to the console interpreter ----------------
set "NEEDS_STDOUT="
for %%A in (%*) do (
  if /I "%%~A"=="--help"       set "NEEDS_STDOUT=1"
  if /I "%%~A"=="-h"           set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--dump-dom"  set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--selftest"  set "NEEDS_STDOUT=1"
  if /I "%%~A"=="--memory"    set "NEEDS_STDOUT=1"
)

if defined NEEDS_STDOUT (
  "%PYEXE%" "%SHELL%" %*
  exit /b %ERRORLEVEL%
)

REM ---- normal launch: pythonw, detached, with a log file the run can leave --
REM A default log so a hidden run still leaves a receipt. An explicit --log
REM on the command line wins; batch cannot test for that cheaply, so the
REM default is only appended when the user did not already pass one.
set "PASSED_LOG="
for %%A in (%*) do (
  if /I "%%~A"=="--log" set "PASSED_LOG=1"
)
if defined PASSED_LOG (
  start "" "%PYW%" "%SHELL%" %*
) else (
  REM The path is left as the repo-relative walk: the shell resolves it, and
  REM MEASURED to land the file at H:\sotto\_main\webview-run.log. Normalising
  REM it with `for %%I in ("%HERE%..\..\_main")` was tried and REJECTED: cmd
  REM mangles the quoted argument and the run then wrote no log at all.
  start "" "%PYW%" "%SHELL%" --log "%HERE%..\..\_main\webview-run.log" %*
)
exit /b 0