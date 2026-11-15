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
REM ── O TECTO E' DECLARADO AQUI, NAO HERDADO (medido 2026-11-15) ──────────────
REM O motor declarava `WORKER_THREADS_DEFAULT = 2` em `warm_engine.py:149`,
REM mas um default e' um valor que alguem muda sem passar por este ficheiro:
REM a largada nao dizia numero nenhum. Medido neste host: `pythonw.exe(42792)`
REM = `warm_engine.py` custou **14,15 % da maquina** (2,83 de 20 nucleos) e a
REM leitura anterior do mesmo actor deu **18,2 % / 3,6 nucleos / 57 fios** --
REM duas medicoes do mesmo actor, nenhuma delas com um tecto escrito ao lado
REM do comando que a larga.
REM
REM `--threads 2` = 2 fios POR SESSAO (encoder/decoder/joint do nemotron), o
REM MESMO numero que a shell entrega ao worker (`--worker-threads`). NAO e' 2
REM nucleos: medido em 2026-11-09, o mesmo orcamento ainda queima 0,6-1,6 de um
REM nucleo porque sao tres sessoes ORT com pool proprio, e `--threads 1` foi
REM recusado por medicao (a margem sobre o tempo real cai de 2-5x para ~1x).
REM
REM O QUE NAO SE FAZ AQUI: enjaular o motor em `watcher run --cpu 40`. Quando
REM ha' um cliente LIGADO este processo E' o ASR ao vivo -- o mesmo caminho que a
REM regra do dono de 2026-11-11 proibe estrangular ("throttling is the worst of
REM the approaches"). Parado (sem cliente) ele ja' nao descodifica: o tap parqueado
REM alimenta o RING e nao o descodificador, e o TTL de 600 s o expira
REM (`WARM_EXIT why=idle-expired`). O custo medido existe enquanto o dono quer
REM transcricao; o tecto tem de ser o de fios, nao um corte de CPU que atrasa a
REM legenda.
start "" /b "%PY%" "app\webview\warm_engine.py" --threads 2
exit /b 0
