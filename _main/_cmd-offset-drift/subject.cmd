@echo off
REM Minimal reproducer for cmd.exe's BYTE-OFFSET seeking of a batch file it is
REM already executing. Structure copied from _main\_audit-verify-all.cmd: a main
REM flow that calls labels defined at the END of the file, and subroutines that
REM reach the end via `exit /b`.
REM
REM The controller (_main\_cmd-offset-drift-probe.py) starts this file, waits
REM until it is inside the slow `call`, and then either (a) rewrites the file with
REM the SAME bytes -- the sha256 control -- or (b) rewrites it with one extra REM
REM line near the TOP, which shifts the byte offset of every line below it.
setlocal EnableDelayedExpansion
set "N=0"
echo SUBJECT-BEGIN
call :slow
call :record alpha
call :record beta
call :record gamma
echo SUBJECT-SUMMARY N=!N!
exit /b 0

:record
set /a N+=1
echo [step] %~1 rc=0
exit /b 0

:slow
ping -n 3 127.0.0.1 >nul
echo SUBJECT-INSIDE-SLOW
exit /b 0
