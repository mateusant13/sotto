@echo off
REM A FORMA CURADA (2026-11-12): `call :label` rele cada linha, e `if errorlevel 1`
REM nao depende de expansao nenhuma. O filho sai 1 e este ficheiro TAMBEM sai 1.
if not defined CAGE_FIXTURE_RAN call :__cage
if errorlevel 1 exit /b 1
exit /b 0
:__cage
set "CAGE_FIXTURE_RAN=1"
python -c "import sys;sys.exit(1)"
exit /b %ERRORLEVEL%
