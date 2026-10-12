@echo off
REM Registra o Sotto para arrancar com o Windows (logon do utilizador, escondido).
REM Pedido do dono: "faz o sotto sempre iniciar com windows" (2026-10-12).
REM O launch vai por run.cmd -- o mesmo que o dono usa -- escondido e destacado do Task Scheduler,
REM por isso NAO morre quando a sessao de trabalho do Lead termina.
REM Para remover: schtasks /delete /tn Sotto /f
REM Para lancar agora: schtasks /run /tn Sotto
schtasks /create /tn "Sotto" /xml "%~dp0sotto-task.xml" /f
if errorlevel 1 exit /b 1
schtasks /query /tn "Sotto" /v /fo LIST
exit /b 0