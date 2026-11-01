@echo off
REM -- Acao da tarefa agendada `SottoRelaunch`. Ve _main/sotto-relaunch.py para o porque.
REM -- `pythonw` porque uma janela de consola visivel e' proibida neste repo (o censo de
REM -- janelas loga ALERTA-JANELA a cada 60 s). O veredicto vive em _main/shell-relaunch.log.
REM --
REM -- Uso:  schtasks /run /tn SottoRelaunch
REM --       schtasks /run /tn SottoRelaunch   (com o argumento abaixo, so' le')
setlocal
set PYTHONW=C:\Program Files\Python311\pythonw.exe
set SCRIPT=H:\sotto\_main\sotto-relaunch.py
if /i "%~1"=="--check" (
  "%PYTHONW%" "%SCRIPT%" --check
) else (
  "%PYTHONW%" "%SCRIPT%" --relaunch --tag task
)
endlocal
