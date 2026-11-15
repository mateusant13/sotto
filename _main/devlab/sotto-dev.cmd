@echo off
REM ===========================================================================
REM  `sotto dev` -- the easy way to exercise the real pipeline.
REM
REM  WHAT IT DOES. It builds (or reuses, by content) a 16 kHz mono audio window
REM  cut from a real video's own audio track and runs the REAL worker live loop
REM  over it, then scores the result against the video's own captions. No audio
REM  device is opened, no hotkey is registered, no window is shown, and the
REM  owner's screen is never touched: the audio is CUT FROM A FILE, so nothing
REM  plays at all.
REM
REM  WHY NOT A BROWSER (measured 2026-11-15, four arms). Headless Chrome plays
REM  and buffers a video fine, but a seek PAST the buffered range parks at
REM  `readyState=1 networkState=2` and never fetches again: baseline, with
REM  anti-throttling flags, and with a wait-then-play all stayed RECOVERED=False
REM  for 10 s, while a headed-offscreen window recovered. Headed steals focus,
REM  which is forbidden, so the audio comes from the stream instead -- exact,
REM  seekable, deterministic and cacheable.
REM
REM  STEPS
REM    Sotto.cmd dev                      reuse cache, else build 60:20 and score
REM    Sotto.cmd dev 60:20                same, explicit window
REM    Sotto.cmd dev 60:20 300:20,600:15  several windows, one command
REM    Sotto.cmd dev --video <id> ...     a different video
REM    Sotto.cmd dev --strips             ablate the pipeline on the same audio
REM    Sotto.cmd dev --selftest           judge the audibility gate itself
REM    Sotto.cmd dev --status             what is cached
REM ===========================================================================
setlocal

set "ROOT=%~dp0..\.."
set "LAB=%ROOT%\_main\devlab\lab.py"
if not exist "%LAB%" (
  echo SOTTO-DEV: lab not found at "%LAB%"
  exit /b 2
)

REM  pythonw.exe: no console window for the child. The wrapper keeps its own
REM  console (a double-clicked .cmd gets one); the payload adds nothing.
set "PY=python"
where pythonw.exe >nul 2>nul && set "PY=pythonw"

set "VIDEO=rS4VMlwf2qM"
set "MODE=run"
set "WINDOWS=%~1"
if "%WINDOWS%"=="" set "WINDOWS=60:20"

:parse
if "%~1"=="" goto dispatch
if /i "%~1"=="--strips"    ( set "MODE=strips"    & shift & goto parse )
if /i "%~1"=="--selftest"  ( set "MODE=selftest"  & shift & goto parse )
if /i "%~1"=="--status"    ( set "MODE=status"    & shift & goto parse )
if /i "%~1"=="--video"     ( set "VIDEO=%~2"      & shift & shift & goto parse )

:dispatch
if /i "%MODE%"=="selftest" goto do_selftest
if /i "%MODE%"=="status"   goto do_status

REM  Build (or hit) the audio windows first: a cache hit is instant, and this is
REM  the step that would ever touch the network.
echo SOTTO-DEV: windows %WINDOWS% of video %VIDEO%
%PY% "%LAB%" window --video %VIDEO% --windows %WINDOWS%
if errorlevel 1 (
  echo SOTTO-DEV: window step failed
  exit /b 1
)

if /i "%MODE%"=="strips" goto do_strips

echo SOTTO-DEV: scoring each window against the video's own captions
set "FAILED=0"
for %%W in (%WINDOWS:,= %) do (
  for /f "tokens=1,2 delims=:" %%A in ("%%W") do (
    %PY% "%LAB%" score --video %VIDEO% --window %%A %%B
    if errorlevel 1 set "FAILED=1"
  )
)
if "%FAILED%"=="1" (
  echo SOTTO-DEV: RED -- at least one window could not be scored
  exit /b 1
)
echo SOTTO-DEV: GREEN
exit /b 0

:do_strips
for /f "tokens=1,2 delims=:" %%A in ("%WINDOWS%") do (
  %PY% "%LAB%" strips --video %VIDEO% --window %%A %%B
)
exit /b %ERRORLEVEL%

:do_selftest
%PY% "%LAB%" selftest
exit /b %ERRORLEVEL%

:do_status
%PY% "%LAB%" status
exit /b %ERRORLEVEL%
