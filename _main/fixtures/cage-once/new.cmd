@echo off
REM A FORMA CURADA (2026-11-12): o corpo vive atras de um rotulo e o cabecalho NUNCA
REM cai nele depois do filho -- exit 0 ou exit 1, o processo que largou sai aqui.
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
exit /b %ERRORLEVEL%
