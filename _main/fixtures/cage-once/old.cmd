@echo off
REM A FORMA ANTIGA (o defeito MEDIDO 2026-11-12): o cabecalho so' sai quando o filho
REM FALHA, logo um filho caged que sai 0 cai no corpo e a bateria inteira corre DUAS vezes.
if "%~1"=="--caged" goto :__body
if not defined NOCAGE goto :__outer
:__body
echo BODY-RAN
exit /b 0
:__outer
call :__child
if errorlevel 1 exit /b 1
echo BODY-RAN
exit /b 0
:__child
call "%~f0" --caged
exit /b %ERRORLEVEL%
