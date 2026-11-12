@echo off
REM A FORMA ANTIGA, copiada do cabecalho da bateria antes de 2026-11-12: o `%ERRORLEVEL%`
REM dentro do bloco entre parenteses e' expandido quando o bloco e' LIDO, logo `exit /b`
REM devolve o codigo de ANTES do trabalho. O filho sai 1 e este ficheiro sai 0.
if not defined CAGE_FIXTURE_RAN (
  set "CAGE_FIXTURE_RAN=1"
  python -c "import sys;sys.exit(1)"
  exit /b %ERRORLEVEL%
)
exit /b 0
