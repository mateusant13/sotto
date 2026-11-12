@echo off
REM A TERCEIRA ARM: o MESMO cabecalho curado, com o filho caged a FALHAR. O rc tem de
REM atravessar o `if errorlevel 1 exit /b 1` e o fixture tem de sair 1.
if "%~1"=="--caged" goto :__body
if not defined NOCAGE goto :__outer
:__body
echo BODY-RAN
exit /b 0
:__outer
call :__child
if errorlevel 1 exit /b 1
exit /b 0
:__child
call "%~f0" --caged
exit /b 1
