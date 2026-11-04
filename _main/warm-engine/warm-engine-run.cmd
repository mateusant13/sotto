@echo off
REM THE WARM ENGINE LAUNCHER -- started by Task Scheduler (`\SottoWarmEngine`),
REM never by the shell (design R1). `pythonw` has no console and the task is
REM `Hidden=true`, so nothing here can paint a window.
REM
REM `start /b` returns the task to Ready immediately; the engine is a long-lived
REM process whose life is governed by the pipe (attach/detach/quit), not by this
REM cmd exiting.
setlocal
cd /d "%~dp0..\.."
if not defined TMPDIR set "TMPDIR=I:\cc-tmp"
set "PY=pythonw"
where pythonw >nul 2>&1 || set "PY=python"
start "" /b "%PY%" "app\webview\warm_engine.py"
exit /b 0
