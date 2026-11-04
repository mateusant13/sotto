@echo off
REM ===========================================================================
REM  Sotto -- the whole verification battery in one command, AND IT SAYS NO.
REM
REM    _main\_audit-verify-all.cmd            run everything; exit 0 ONLY if every
REM                                           step held and every control went RED
REM
REM  Every step prints a `[step] name rc=N` beacon to the console and the full
REM  output to _main\_audit-verify\*.log, so a claim in the receipt can be
REM  re-checked without re-reading this file. Nothing here starts a window, an
REM  audio device, or the app: the app itself cannot run in this session's
REM  sandbox (pythonnet is denied), which is why the battery is all DOM-free
REM  oracles and compile checks.
REM
REM  ---------------------------------------------------------------------------
REM  AGGREGATION -- added 2026-10-08. WHY IT EXISTS (measured, not imagined):
REM  this file used to print each step's rc and then `exit /b 0` unconditionally,
REM  so a run with THREE red steps (`hotkey-delivery` rc=1, `verdict-gate` rc=2,
REM  `history-producer-gate` rc=1) exited 0. The file everyone quoted as "the
REM  battery is green" could report success while steps were red -- the exact
REM  defect class this repo has been fighting: a failure answering as success.
REM
REM  Now every step's rc is recorded and the batch exits NON-ZERO if ANY step
REM  failed, printing a final summary: total steps, the per-step rc list, the
REM  controls seen, and the names of the failed ones.
REM
REM  FOUR KINDS OF STEP, and the difference matters to a reader:
REM    gate        succeeds when it exits 0                  (:record)
REM    control     succeeds ONLY by catching a deliberately-broken COPY, so it
REM                must exit 0 AND print its own control verdict. A control that
REM                does NOT go red is a FAILURE here, never a pass.       (:control)
REM    skipped     an arm the environment can make UNRUNNABLE (the Alt+C delivery
REM                arm, while the owner's app holds the key): rc=0 AND EITHER the
REM                instrument's skip verdict -- then it is counted in `skipped=` and
REM                NEVER in `gate=`, because it did not verify anything -- OR its
REM                verified verdict, then it counts as a real gate. Neither verdict
REM                present is a FAILURE: a step that cannot say what it did is not a
REM                pass.                                            (:skipped)
REM    expect-red  an instrument with no control mode of its own, run in the mode
REM                that is RED BY DESIGN: it must exit 1 (the defect found) and
REM                print the violation. rc=0 means the defect did not appear,
REM                rc=2 is a setup error -- both are failures here.  (:expectred)
REM  The summary prints which steps are controls and which are skipped, and the
REM  `skipped=` column is the part of the green that is NOT CLAIMED. When the owner
REM  closes the app, that arm stops being skipped and moves from `skipped=` to
REM  `gate=` in the same line -- the transition is visible, never silent.
REM
REM  A FIFTH MARK, NOT A FIFTH KIND: `heavy`. A heavy step is not a different
REM  verdict -- it is the same gate, with a DECLARATION that it opens the owner's
REM  world: the app shell (and with it the WebView2 runtime -- 38
REM  msedgewebview2.exe and a saturated VRAM, measured 2026-10-21 and written down
REM  in _main/_strip-stats-log-probe.py), the real output device, or the GPU.
REM  The owner, 2026-10-21, verbatim: *"tu ta fazendo algo que faz meu pc
REM  travar/stutter?"* and *"tu vai garantir que minha reclamacao nunca mais
REM  aconteca"*. So a heavy step does NOT run unless the owner asks for it
REM  (SOTTO_BATTERY_HEAVY=1). It is then counted in `skipped=`, NAMED in the
REM  summary under `heavy:`, and NEVER counted in `gate=`. A CACHED heavy step is
REM  free -- no process is started -- and keeps its gate. The class is a
REM  DECLARATION the owner can audit in one place (the `call :step ... heavy`
REM  lines) and the portão `_main/battery-heavy-gate.py` checks that the
REM  declaration and the instruments agree.
REM
REM  THE BATTERY'S OWN PRIORITY is BELOW NORMAL (see the block near the top):
REM  the machine starts any process with a 53-127 ms stutter (measured
REM  2026-10-21), so the battery yields the CPU and the disk queue to the owner.
REM
REM  THE SKIP GUARD closes the other direction: after every step has written its log,
REM  one sweep fails the run if any STEP log carries `VERDICT: SKIPPED` while its step
REM  is not declared skip-capable. An instrument that skips an arm and still exits 0
REM  must not be printed as a pass by a battery that cannot see it.       (skip-verdict-guard)
REM  "STEP log" is load-bearing: the battery's OWN console carries the same literal
REM  text (its beacon ECHOES it), so a sweep that reads the console fails on its own
REM  output -- measured, and cured at the step below.
REM
REM  A MISSING INSTRUMENT IS A FAILURE, NEVER A PASS: a step whose file does not
REM  exist is recorded as rc=MISSING and fails the run. `else ( echo ... MISSING )`
REM  used to be a line on a screen; now it is a red step.
REM
REM  THIS FILE MUST KEEP CRLF LINE ENDINGS. MEASURED 2026-10-08, the first run of
REM  the aggregating version: written LF-only, the batch executed its step list
REM  TWICE and printed TWO summaries -- pass 1 skipped 13 steps and reported
REM  `steps : 16` GREEN, then cmd resumed and re-ran the skipped steps plus the
REM  whole tail, printing a second summary with `steps : 40`. Every beacon was
REM  duplicated (2 model loads, 2 of every control). The subroutines are reached
REM  by `call :label` / `exit /b`, and cmd seeks a batch file by BYTE OFFSET:
REM  with 1-byte LF endings those stored offsets drift, so the interpreter
REM  resumes at the wrong line. Converted to CRLF the same file ran the step list
REM  ONCE (`steps : 29`). If you rewrite this file with a tool that writes `\n`,
REM  convert it back (`-replace "\n", "\r\n"`) or the aggregation will lie.
REM ===========================================================================
setlocal EnableDelayedExpansion
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "OUT=%ROOT%\_main\_audit-verify"
if not exist "%OUT%" mkdir "%OUT%"
set "CACHE_STATE=%ROOT%\_cache\battery-steps.json"

REM ===========================================================================
REM  THE BATTERY'S OWN PRIORITY -- BELOW NORMAL.
REM  The owner, 2026-10-21 (verbatim): *"tu ta fazendo algo que faz meu pc
REM  travar/stutter?"* and *"entendo por que a bateria trava e da stutter. e por
REM  que o start do que quer que seja, da stutter no meu computador"*. MEASURED
REM  2026-10-21 on this machine: starting ANY process costs the owner a 53-127
REM  ms stutter, because the disks are nearly full and a start is a disk read.
REM  So the battery puts ITSELF below normal: the owner's foreground work wins
REM  the CPU and the disk queue, and the battery's children INHERIT the class
REM  (CreateProcess inherits the parent's priority class) -- the python that
REM  checks the cache, the instrument, and the app shell the heavy steps start.
REM  This is the second half of the guarantee: the first half is that the heavy
REM  steps do not run at all unless the owner asks (see :step_heavyskip).
REM  The .ps1 is written as a FILE on purpose: the AGENTS' own measured lesson
REM  (`_main/_audit-hotkey-delivery.py`) is that the inline `powershell -Command`
REM  form of a CIM query returns EMPTY stdout here, so this uses the file form.
REM  If PowerShell is missing the battery says so and runs at normal priority:
REM  a missing priority is not a failed run.
set "BATTERY_PRIO_PS1=%TEMP%\sotto-battery-priority.ps1"
set "BATTERY_PRIO_REPORT=%OUT%\_battery-priority.txt"
set "BATTERY_PRIORITY_LINE="
if exist "%BATTERY_PRIO_PS1%" del /q "%BATTERY_PRIO_PS1%" 2>nul
> "%BATTERY_PRIO_PS1%" echo $ErrorActionPreference='SilentlyContinue'
>>"%BATTERY_PRIO_PS1%" echo $me=Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
>>"%BATTERY_PRIO_PS1%" echo $parent=$me.ParentProcessId
>>"%BATTERY_PRIO_PS1%" echo $p=Get-Process -Id $parent -ErrorAction SilentlyContinue
>>"%BATTERY_PRIO_PS1%" echo $p.PriorityClass='BelowNormal'
>>"%BATTERY_PRIO_PS1%" echo $report="BATTERY-PRIORITY " + $p.PriorityClass + " pid=" + $parent
>>"%BATTERY_PRIO_PS1%" echo Set-Content -Path $args[0] -Value $report
>>"%BATTERY_PRIO_PS1%" echo Write-Output "BATTERY-PRIORITY-OK"
for /f "usebackq tokens=1" %%P in (`powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%BATTERY_PRIO_PS1%" "%BATTERY_PRIO_REPORT%" 2^>nul`) do set "BATTERY_PRIORITY_VERDICT=%%P"
if exist "%BATTERY_PRIO_REPORT%" ( set /p BATTERY_PRIORITY_LINE=<"%BATTERY_PRIO_REPORT%" )
if not defined BATTERY_PRIORITY_LINE set "BATTERY_PRIORITY_LINE=NOT-SET (PowerShell unavailable or denied) -- the battery runs at normal priority"
del /q "%BATTERY_PRIO_PS1%" 2>nul

set "N=0"
set "GATES=0"
set "CTRLS=0"
set "SKIPN=0"
set "REDS=0"
set "MISSINGN=0"
set "BAD=0"
set "CACHEDN=0"
set "HEAVYN=0"
set "HEAVYLIST="
set "STEPLIST="
set "FAILED="
set "CONTROLLIST="
set "SKIPLIST="
REM Basenames of the logs whose step is DECLARED skip-capable and really skipped this
REM run -- the only logs the skip guard below is allowed to see a skip verdict in.
set "SKIPLOGS=,"

echo === compile checks ===
call :step pycompile-sotto_webview 0 "app\webview\sotto_webview.py" "%OUT%\pycompile-webview.log" python -m py_compile app\webview\sotto_webview.py
call :record pycompile-sotto_webview !STEP_RC!
call :step pycompile-webview-helpers 0 "app\webview\hot_reload.py;app\webview\panel_state.py" "%OUT%\pycompile-webview-helpers.log" python -m py_compile app\webview\hot_reload.py app\webview\panel_state.py
call :record pycompile-webview-helpers !STEP_RC!
call :step pycompile-sotto_worker 0 "worker\sotto_worker.py" "%OUT%\pycompile-worker.log" python -m py_compile worker\sotto_worker.py
call :record pycompile-sotto_worker !STEP_RC!
call :step pycompile-wasapi+lang 0 "worker\wasapi_loopback.py;worker\lang_prompt.py" "%OUT%\pycompile-capture.log" python -m py_compile worker\wasapi_loopback.py worker\lang_prompt.py
call :record pycompile-wasapi+lang !STEP_RC!

echo === the panel/engine oracles that were GREEN before the fixes ===
call :step transcript-append-oracle 0 "app\_legacy-electron\transcript-append-oracle.js;app\panel\caption-formulation.js;worker\runs\gate-live-speech.jsonl;worker\runs\ACCEPT-after.jsonl" "%OUT%\oracle-transcript-append.log" node app\_legacy-electron\transcript-append-oracle.js
call :record transcript-append-oracle !STEP_RC!
call :step live-vs-history-source-oracle 0 "_main\live-vs-history-source-oracle.js;app\panel\history-source.js;app\panel\caption-formulation.js;app\panel\panel.js;app\panel\history-store.js" "%OUT%\oracle-live-vs-history.log" node _main\live-vs-history-source-oracle.js
call :record live-vs-history-source-oracle !STEP_RC!
call :step historico-vs-redux-probe 0 "_main\historico-vs-redux-probe.js;app\panel\caption-formulation.js;app\panel\history-store.js" "%OUT%\oracle-historico-vs-redux.log" node _main\historico-vs-redux-probe.js
call :record historico-vs-redux-probe !STEP_RC!

REM O CAMINHO DA LINHA DO BATCH ATE O DISCO (2026-11-01). O motor de batch emite
REM `{type,text,start,end,producer:'redux'}` -- SEM `route`, SEM flag `final`
REM (`worker/redux_batch.py:185`), e o choke point do painel recusava-a uma instrucao
REM ANTES da guarda que existe para a aceitar: medido na loja inteira, 0 linhas
REM `route=batch` em 2084. O oraculo executa as TRES metades do ficheiro entregue
REM (a decisao, o call site `recordHistory` e o escritor da proveniencia) e o braco
REM de baixo exige que os mutantes vao RED.
call :step redux-transcript-path 0 "_main\_redux-transcript-path.py;app\panel\history-source.js;app\panel\panel.js;app\webview\sotto_webview.py" "%OUT%\redux-transcript-path.log" python _main\_redux-transcript-path.py
call :record redux-transcript-path !STEP_RC!

REM A LEGENDA NAO PODE CONCATENAR A MESMA LINHA DUAS VEZES (2026-11-03). Medido
REM no log VIVO do dono (pid 18156, 11:45): o worker publicou as tres versoes
REM cumulativas limpas e o `CAPTION_APPLIED` publicou a soma delas --
REM "Ig u a galera ig u a galera do a esquerda ig u a galera do a esquerda tava
REM gravando.". O motor do painel so' reconhecia a re-leitura pelo `start`;
REM sem ele o fragmento era concatenado. O oraculo empurra os eventos pelo motor
REM REAL nas quatro formas (sem meta, com meta, frase nova, repeticao exacta) e o
REM braco de baixo apaga a cura numa COPIA e exige o braco A vermelho.
call :step caption-cumulative 0 "_main\caption-cumulative-oracle.js;app\panel\caption-formulation.js" "%OUT%\oracle-caption-cumulative.log" node _main\caption-cumulative-oracle.js
call :record caption-cumulative !STEP_RC!
call :step red-as-expected-caption-cumulative 1 "_main\caption-cumulative-oracle.js;app\panel\caption-formulation.js" "%OUT%\caption-cumulative-neg.log" node _main\caption-cumulative-oracle.js --neg-arm
call :expectred red-as-expected-caption-cumulative !STEP_RC! "%OUT%\caption-cumulative-neg.log" "NEG-ARM: PASS"
REM A IDADE DO AUDIO QUE ESTA' NO ECRA (2026-11-03). ORDEM DO DONO, verbatim:
REM *"tu nao tem a porra de um teste ou log que mostra a discrepancia entre audio
REM detectado e display na tela? nao tem nada que grita que o budget de ter
REM mostrado ja passou do ponto?"* -- nao tinha. `tap_ms` viaja do worker (o
REM relogio de parede do bloco que fechou a linha) ate' a pintura, e as linhas
REM `CAPTION_IN`/`CAPTION_PAINT_LAG`/`CAPTION_BUDGET_BLOWN`/`CAPTION_LAG_STATS`
REM publicam audio_ms, queue_ms e o veredicto contra 1500 ms. O braco de baixo
REM roda DOIS mutantes (orcamento infinito e `tap_ms` que nao viaja) e exige as
REM arms correspondentes vermelhas.
call :step caption-lag-budget 0 "_main\caption-lag-budget-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\caption-lag-budget.log" python _main\caption-lag-budget-oracle.py
call :record caption-lag-budget !STEP_RC!
call :step red-as-expected-caption-lag-budget 1 "_main\caption-lag-budget-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\caption-lag-budget-neg.log" python _main\caption-lag-budget-oracle.py --neg-arm
call :expectred red-as-expected-caption-lag-budget !STEP_RC! "%OUT%\caption-lag-budget-neg.log" "NEG-ARM: PASS"
REM `lag-note-cost` (2026-11-04, do commit de perf 1c92e39): `_caption_lag_note`
REM custava 27,1 us por legenda -- 83 % do caminho de aplicar uma legenda -- porque
REM `len(ages) % 25 == 0` e' SEMPRE verdadeiro com a janela cheia (200 % 25 == 0) e a
REM janela de 200 amostras era re-ordenada e re-somada em TODAS as legendas. O
REM oraculo julga o codigo REAL do `SottoShell` em cinco arms (custo dentro de 4x,
REM custo PLANO com a janela cheia, os dez campos da serie contra uma janela
REM re-somada a mao, a cadencia de 25 e a janela de 200) e o `--neg-arm` muta uma
REM COPIA de `sotto_webview.py` quatro vezes. Veio do merge SEM passo: o
REM `battery-wiring` dizia `new-unwired ... lag-note-cost-oracle.py`.
call :step always lag-note-cost 0 "_main\lag-note-cost-oracle.py;app\webview\sotto_webview.py" "%OUT%\lag-note-cost.log" python _main\lag-note-cost-oracle.py
call :record lag-note-cost !STEP_RC!
call :step always red-as-expected-lag-note-cost 1 "_main\lag-note-cost-oracle.py;app\webview\sotto_webview.py" "%OUT%\lag-note-cost-neg.log" python _main\lag-note-cost-oracle.py --neg-arm
call :expectred red-as-expected-lag-note-cost !STEP_RC! "%OUT%\lag-note-cost-neg.log" "NEG-ARM: PASS"
REM `youtube-hidden-clock` (2026-11-04): quando a aba do YouTube esta' escondida o Chrome para
REM de repintar a legenda e `video.currentTime` continua a andar -- medido no Chrome do dono: 40 s
REM com UMA unica assinatura em 790 amostras, e um seek para t=300 com as mesmas duas linhas. O
REM detector so' declara pintura parada com a FAIXA como segunda testemunha (assinatura igual >
REM STALE_S de relogio de VIDEO * ha cue na faixa * a pintura alinha noutra cue) e desenha a cue da
REM faixa ate' uma linha distinta provar que a pintura voltou. O braco negativo desliga cada uma das
REM tres condicoes e exige a arm correspondente vermelha.
call :step always youtube-hidden-clock 0 "_main\youtube-hidden-clock-oracle.py;app\webview\youtube_monotonic.py;app\webview\sotto_webview.py;_main\fixtures\yt-paint-freeze-20261104.json" "%OUT%\youtube-hidden-clock.log" python _main\youtube-hidden-clock-oracle.py
call :record youtube-hidden-clock !STEP_RC!
call :step always red-as-expected-youtube-hidden-clock 1 "_main\youtube-hidden-clock-oracle.py;app\webview\youtube_monotonic.py" "%OUT%\youtube-hidden-clock-neg.log" python _main\youtube-hidden-clock-oracle.py --neg-arm
call :expectred red-as-expected-youtube-hidden-clock !STEP_RC! "%OUT%\youtube-hidden-clock-neg.log" "NEG-ARM PASS"
REM `caption-overlay-screen` (2026-11-04, P0 do dono: `CAPTION_OVERLAY_PUSH
REM visible=true` e ele NAO VIU nada). `_screen_proof()` ja' lia o Windows
REM (`GetWindowRect`/`MonitorFromPoint`/`GetMonitorInfoW`/`GetLayeredWindowAttributes`)
REM e publicava `CAPTION_OVERLAY_GEOMETRY ... on_screen=.. rect=.. alpha=..`, mas
REM NENHUM portao lia esse campo -- `grep -c CAPTION_OVERLAY_GEOMETRY` nesta bateria
REM dava 0. O oraculo executa a FUNCAO REAL: arms A1/A2 contra uma janela LAYERED
REM oculta que ele proprio cria (Win32 de verdade; nada e' mostrado) e A3-A6 contra
REM um `user32` de aritmetica, exigindo um alfa 0 a dar RED por 'invisible' -- a
REM classe exacta do dono. O braco de baixo muta uma COPIA de `caption_overlay.py`
REM quatro vezes (area invertida, alfa ignorado, fecho de falha descartado, rect do
REM `self.visible`) e exige as quatro apanhadas.
call :step always caption-overlay-screen 0 "_main\caption-overlay-screen-oracle.py;app\webview\caption_overlay.py" "%OUT%\caption-overlay-screen.log" python _main\caption-overlay-screen-oracle.py
call :record caption-overlay-screen !STEP_RC!
call :step always red-as-expected-caption-overlay-screen 1 "_main\caption-overlay-screen-oracle.py;app\webview\caption_overlay.py" "%OUT%\caption-overlay-screen-neg.log" python _main\caption-overlay-screen-oracle.py --neg-arm
call :expectred red-as-expected-caption-overlay-screen !STEP_RC! "%OUT%\caption-overlay-screen-neg.log" "NEG-ARM"
REM `youtube-cdp-boot` (2026-11-04): o arranque chamava `self._yt_cdp_ensure()`, que NAO EXISTE -- o
REM `AttributeError` era engolido como `YOUTUBE_CDP_PREOPEN_FAILED` e a ligacao nunca era pedida
REM (medido: 1482 de 3972 linhas `YOUTUBE_TICK_MS` com `src='?'`). O oraculo executa o pedido de
REM arranque, a adopcao da fonte pelo watcher e o diagnostico sem interrogacao.
call :step always youtube-cdp-boot 0 "_main\youtube-cdp-boot-oracle.py;app\webview\youtube_cdp_source.py;app\webview\sotto_webview.py" "%OUT%\youtube-cdp-boot.log" python _main\youtube-cdp-boot-oracle.py
call :record youtube-cdp-boot !STEP_RC!
call :step always red-as-expected-youtube-cdp-boot 1 "_main\youtube-cdp-boot-oracle.py;app\webview\youtube_cdp_source.py" "%OUT%\youtube-cdp-boot-neg.log" python _main\youtube-cdp-boot-oracle.py --neg-arm
call :expectred red-as-expected-youtube-cdp-boot !STEP_RC! "%OUT%\youtube-cdp-boot-neg.log" "NEG-ARM VERDICT: PASS"
call :step red-as-expected-redux-transcript-path 1 "_main\_redux-transcript-path.py;app\panel\history-source.js;app\panel\panel.js;app\webview\sotto_webview.py" "%OUT%\redux-transcript-path-neg.log" python _main\_redux-transcript-path.py --neg-arm
call :expectred red-as-expected-redux-transcript-path !STEP_RC! "%OUT%\redux-transcript-path-neg.log" "NEG-ARM: PASS"

echo === the gates added by this round ===
REM The SECOND control of the same gate, added 2026-10-19: the first one
REM drops the `captions-zero` guard; this one drops the LIVE-OVERLAY term
REM from `emitted` while KEEPING the read. A control that fails for the
REM wrong reason is not a control, and the read is kept on purpose so the
REM copy goes RED on the CLAIM and not on a KeyError.
if exist _main\verdict-gate.py (
  call :step control-verdict-gate-drop-redux-live 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\control-verdict-gate-drop-redux-live.log" python _main\verdict-gate.py --control-drop-redux-live
  call :control control-verdict-gate-drop-redux-live !STEP_RC! "%OUT%\control-verdict-gate-drop-redux-live.log" "CONTROL PASS"
) else ( call :control control-verdict-gate-drop-redux-live MISSING "%OUT%\control-verdict-gate-drop-redux-live.log" "CONTROL PASS" )
if exist _main\history-producer-gate.js (
  call :step history-producer-gate 0 "_main\history-producer-gate.js;app\panel\caption-formulation.js;worker\redux_batch.py;worker\sotto_worker.py" "%OUT%\gate-history-producer.log" node _main\history-producer-gate.js
  call :record history-producer-gate !STEP_RC!
) else ( call :record history-producer-gate MISSING )
if exist _main\panel-state-guard-gate.js (
  call :step panel-state-guard-gate 0 "_main\panel-state-guard-gate.js;app\panel\caption-formulation.js;app\panel\panel.js" "%OUT%\gate-panel-state-guard.log" node _main\panel-state-guard-gate.js
  call :record panel-state-guard-gate !STEP_RC!
) else ( call :record panel-state-guard-gate MISSING )
if exist _main\verdict-gate.py (
  call :step verdict-gate 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\gate-verdict.log" python _main\verdict-gate.py
  call :record verdict-gate !STEP_RC!
) else ( call :record verdict-gate MISSING )

echo === the per-lane probes ===
if exist _main\_lane2-reset-probe.js (
  call :step lane2-reset-probe 0 "_main\_lane2-reset-probe.js;app\panel\caption-formulation.js;app\panel\panel.js" "%OUT%\lane2-reset.log" node _main\_lane2-reset-probe.js
  call :record lane2-reset-probe !STEP_RC!
) else ( call :record lane2-reset-probe MISSING )
if exist _main\_lane3-verdict-probe.py (
  call :step lane3-verdict-probe 0 "_main\_lane3-verdict-probe.py;worker\sotto_worker.py;worker\config.json" "%OUT%\lane3-verdict.log" python _main\_lane3-verdict-probe.py
  call :record lane3-verdict-probe !STEP_RC!
) else ( call :record lane3-verdict-probe MISSING )
if exist _main\_lane4-tap-stop-probe.py (
  call :step lane4-tap-stop-probe 0 "_main\_lane4-tap-stop-probe.py;worker\wasapi_loopback.py" "%OUT%\lane4-tap-stop.log" python _main\_lane4-tap-stop-probe.py
  call :record lane4-tap-stop-probe !STEP_RC!
) else ( call :record lane4-tap-stop-probe MISSING )
if exist _main\_audit-history-dead.js (
  call :step audit-history-dead 0 "_main\_audit-history-dead.js;app\panel\caption-formulation.js;app\panel\history-source.js;app\panel\history-store.js" "%OUT%\audit-history-dead.log" node _main\_audit-history-dead.js
  call :record audit-history-dead !STEP_RC!
) else ( call :record audit-history-dead MISSING )

echo === the panel's row-identity rule: the SAME probe, both colours (gate here, control in CONTROLS) ===
REM `_panel2-repeat-probe.js` has no `--control-*` flag: its control mode IS `--revert`, whose
REM mutant COPY of panel.js is built inline. Wiring BOTH halves means one battery run shows the
REM rule holding on the shipped panel AND the probe able to go RED without it. This row is the
REM GREEN half; `control-panel2-repeat-revert` is the control.
if exist _main\_panel2-repeat-probe.js (
  call :step panel2-repeat-probe 0 "_main\_panel2-repeat-probe.js;app\panel\panel.html;app\panel\panel.js" "%OUT%\panel2-repeat.log" node _main\_panel2-repeat-probe.js
  call :record panel2-repeat-probe !STEP_RC!
) else ( call :record panel2-repeat-probe MISSING )

echo === the day/hour gallery: the module arithmetic, and the DOM that shows it ===
REM Two instruments, two claims. `history-gallery-oracle.js` requires the SHIPPED
REM `app/panel/history-gallery.js` as a plain module (no DOM, no jsdom) and checks the
REM bucketing plus the LOCAL-time stamp; its `--neg-arm` is the control row below.
REM `_panel2-dom-probe.js` is the jsdom probe that presses the real buttons in the real
REM document -- 78 arms, ARM G being the gallery's. Measured 2026-10-08: GREEN 78/78 on
REM the shipped panel, and RED on exactly the two arms that name the auto-append the
REM owner had removed when the same probe was pointed at a mutant copy via
REM `SOTTO_PANEL_DIR` (the other 76 stayed green).
if exist _main\history-gallery-oracle.js (
  call :step history-gallery-oracle 0 "_main\history-gallery-oracle.js;app\panel\history-gallery.js" "%OUT%\gallery-oracle.log" node _main\history-gallery-oracle.js
  call :record history-gallery-oracle !STEP_RC!
) else ( call :record history-gallery-oracle MISSING )
if exist _main\_panel2-dom-probe.js (
  call :step panel2-dom-probe 0 "_main\_panel2-dom-probe.js;app\panel\panel.html;app\panel\panel.css;app\panel\caption-formulation.js;app\panel\history-source.js;app\panel\history-gallery.js;app\panel\surface.js;app\panel\themes\themes.js;app\panel\themes\panel-designs.js;app\panel\themes\zipc-panels.js;app\panel\theme-switcher.js;app\panel\theme-tune.js;app\panel\panel.js;app\panel\letter-swap.js;app\panel\caption-float.js;app\panel\strip-drag.js" "%OUT%\panel2-dom-probe.log" node _main\_panel2-dom-probe.js
  call :record panel2-dom-probe !STEP_RC!
) else ( call :record panel2-dom-probe MISSING )

REM The live caption BOX (owner, 2026-10-20, verbatim: "a app parece viva mas
REM nao entrega nada"): the caption arrived as a PROVISIONAL line, the list was
REM born with the `hidden` attribute, and only the COMMIT path ever took that
REM attribute off -- so the line was in the DOM and INVISIBLE while the
REM placeholder stayed on screen. This gate runs the REAL panel in jsdom and
REM asserts that the box shows the line, that the placeholder comes back when
REM the box empties, and that the painted line carries the cue the owner saw.
REM Its THREE MUTANTS (real copies of the panel, one break each) must each go
REM RED on the claim they break -- a gate that cannot say NO is decoration.
if exist _main\panel-live-box-oracle.js (
  call :step panel-live-box-oracle 0 "_main\panel-live-box-oracle.js;app\panel\panel.html;app\panel\panel.css;app\panel\panel.js;app\panel\caption-formulation.js;app\panel\surface.js;app\panel\theme-switcher.js;app\panel\letter-swap.js;app\panel\caption-float.js;app\panel\strip-drag.js" "%OUT%\panel-live-box-oracle.log" node _main\panel-live-box-oracle.js
  call :record panel-live-box-oracle !STEP_RC!
) else ( call :record panel-live-box-oracle MISSING )

REM AS BORDAS DO PAINEL (owner, 2026-10-21, verbatim: "as bordas de cada design
REM nao tao transparentes, tao cinzas/pretas. assim, nao ficam arredondadas pelo
REM design"). DUAS CAUSAS INDEPENDENTES, ambas em `app/panel/panel.css`: (1) a
REM base pintava no ROOT e uma background no root PROPAGA PARA O CANVAS, sem
REM ser cortada pelo border-radius -- os quatro cantos eram uma placa quadrada
REM cinza/preta por cima da qual o arredondamento do design era desenhado; (2) o
REM piso era o LITERAL `12px !important`, que esmagava o raio proprio de cada
REM design (GlassCards declara 22px, Bubbles 20px, Quotes 18px). O piso passou a
REM `max(var(--radius, 14px), 12px)`.
REM ESTE PORTAO JULGA FICHEIROS (AGENTS regra 6: um portao que julga ficheiros
REM entra na bateria) e LANCA NADA. A metade RENDERIZADA e medida por
REM `_main/_border-radius-probe.py` (Chromium de verdade, 45 designs), que
REM LANCA um browser e por isso fica FORA da bateria -- declarado aqui.
REM O BRACO NEGATIVO: os tres mutantes tem de virar um braco VERMELHO. rc=1 POR
REM DESENHO (o `--neg-arm` REPROVA de proposito).
if exist _main\border-radius-gate.py (
  call :step border-radius-gate 0 "_main\border-radius-gate.py;app\panel\panel.css" "%OUT%\border-radius-gate.log" python _main\border-radius-gate.py
  call :record border-radius-gate !STEP_RC!
) else ( call :record border-radius-gate MISSING )
if exist _main\border-radius-gate.py (
  call :step red-as-expected-border-radius-gate 1 "_main\border-radius-gate.py;app\panel\panel.css" "%OUT%\border-radius-gate-neg.log" python _main\border-radius-gate.py --neg-arm
  call :expectred red-as-expected-border-radius-gate !STEP_RC! "%OUT%\border-radius-gate-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-border-radius-gate MISSING "%OUT%\border-radius-gate-neg.log" "NEG-ARM PASS" )
REM
REM O UNICO CAMINHO QUE LARGA UM FILHO (2026-11-04). `_main/hidden-launch.py` e'
REM o que a bateria inteira atravessa: `cmd`, `powershell`, `.cmd` e `python`
REM passam todos por ele. MEDIDO hoje: `run()` e `popen()` passavam
REM `creationflags=` DUAS vezes ao `Popen` e morriam num `TypeError` ANTES de
REM arrancar o filho -- `run(['cmd','/c',r'_main\_audit-verify-all.cmd'])`
REM devolvia o Traceback e NENHUM passo corria. Nenhum portao viu isso: o
REM `console-window-gate.py` que a AGENTS.md nomeia NAO EXISTE nesta arvore, e um
REM portao de TEXTO veria a bandeira presente (duas vezes).
REM O QUE ESTE JULGA: o EFEITO no sistema operativo -- o filho de `run` e de
REM `popen` diz `GetConsoleWindow()==0`, o censo nao encontra NENHUMA janela de
REM consola visivel na arvore do filho, e `run` ESPERA (3 s de filho => >=3 s).
REM O BRACO NEGATIVO repoe o `TypeError` numa COPIA e exige as quatro arms
REM vermelhas; rc=1 POR DESENHO.
if exist _main\hidden-launch-oracle.py (
  call :step hidden-launch 0 "_main\hidden-launch-oracle.py;_main\hidden-launch.py" "%OUT%\hidden-launch.log" python _main\hidden-launch-oracle.py
  call :record hidden-launch !STEP_RC!
) else ( call :record hidden-launch MISSING )
if exist _main\hidden-launch-oracle.py (
  call :step red-as-expected-hidden-launch 1 "_main\hidden-launch-oracle.py;_main\hidden-launch.py" "%OUT%\hidden-launch-neg.log" python _main\hidden-launch-oracle.py --neg-arm
  call :expectred red-as-expected-hidden-launch !STEP_RC! "%OUT%\hidden-launch-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-hidden-launch MISSING "%OUT%\hidden-launch-neg.log" "NEG-ARM PASS" )
REM
REM O FEED SEM PAGINA (2026-11-04). O pipeline de legendas arranca ANTES do
REM WebView2, de proposito; quando o motor NAO inicializa (`WEBVIEW2_INIT_FAILED
REM 0x80010108`, medido 02:48:24 numa instancia propria) o `core` fica a `None` e
REM cada amostra do medidor escrevia um `WARN POSTED_CALLABLE_FAILED ...
REM 'NoneType' object has no attribute 'ExecuteScriptAsync'` -- 541 linhas em
REM ~60 s, com a legenda do YouTube a CHEGAR e a nunca poder ser pintada. O
REM oraculo corre o `emit_async` REAL com `core=None` (50 pushes -> UMA linha),
REM com pagina (o payload mais novo TEM de sair: um feed engolido e' outro
REM defeito) e depois da pagina existir. O negativo desliga a CONDICAO numa
REM COPIA e exige a arm A vermelha com `AttributeError`; rc=1 POR DESENHO.
if exist _main\emit-prewebview-oracle.py (
  call :step emit-prewebview 0 "_main\emit-prewebview-oracle.py;app\webview\sotto_webview.py" "%OUT%\emit-prewebview.log" python _main\emit-prewebview-oracle.py
  call :record emit-prewebview !STEP_RC!
) else ( call :record emit-prewebview MISSING )
if exist _main\emit-prewebview-oracle.py (
  call :step red-as-expected-emit-prewebview 1 "_main\emit-prewebview-oracle.py;app\webview\sotto_webview.py" "%OUT%\emit-prewebview-neg.log" python _main\emit-prewebview-oracle.py --neg-arm
  call :expectred red-as-expected-emit-prewebview !STEP_RC! "%OUT%\emit-prewebview-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-emit-prewebview MISSING "%OUT%\emit-prewebview-neg.log" "NEG-ARM PASS" )
REM
REM O CTRL+SPACE QUE SO' FUNCIONAVA AS VEZES (2026-11-04, reportado pelo dono:
REM *"control espaco nao ta funcionando"* e *"funciona so' de vez em quando"*).
REM MEDIDO no log vivo: `HOTKEY_OBSERVER_ALIVE role=live ... max_gap_ms=281..609`
REM -- a volta do observador atrasa ate' ~0,6 s (GIL tomado pela inferencia e
REM pelas leituras de UIA) e um toque de Ctrl+Space de ~120-200 ms cai INTEIRO
REM entre duas leituras. A cura le o BIT 0 de `GetAsyncKeyState` ("carregada
REM desde a chamada anterior"): o Windows guarda a borda e no'-la lemos com a
REM volta atrasada, sem hook global e sem roubar a tecla ao sistema. O oraculo
REM corre o observador REAL com `key_state` injectado, e o negativo tira a
REM leitura do bit 0 de uma COPIA e exige `presses=0` na arm do toque.
if exist _main\hotkey-live-edge-oracle.py (
  call :step hotkey-live-edge 0 "_main\hotkey-live-edge-oracle.py;app\webview\sotto_webview.py" "%OUT%\hotkey-live-edge.log" python _main\hotkey-live-edge-oracle.py
  call :record hotkey-live-edge !STEP_RC!
) else ( call :record hotkey-live-edge MISSING )
if exist _main\hotkey-live-edge-oracle.py (
  call :step red-as-expected-hotkey-live-edge 1 "_main\hotkey-live-edge-oracle.py;app\webview\sotto_webview.py" "%OUT%\hotkey-live-edge-neg.log" python _main\hotkey-live-edge-oracle.py --neg-arm
  call :expectred red-as-expected-hotkey-live-edge !STEP_RC! "%OUT%\hotkey-live-edge-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-hotkey-live-edge MISSING "%OUT%\hotkey-live-edge-neg.log" "NEG-ARM PASS" )
REM
REM A TELA DO DONO (2026-10-23). A ordem, verbatim, e ele deu-a DUAS vezes:
REM "para de abrir essa merda na minha tela. tu vai resolver no teu ambiente ai
REM sem encher o meu saco", e depois "faz gates ou agents.md". O portao julga
REM FICHEIROS e LANCA NADA: (1) nenhum instrumento de nivel 1 de `_main`
REM ADICIONA `keybd_event`/`SendInput`/`mouse_event`/`SendKeys`/`BlockInput` --
REM um evento sintetico mede o WINDOWS, nao a app (medido 2026-10-23: quatro
REM `err=0` no pressionador e ZERO linhas no log do Sotto); (2) nenhum harness
REM de lane pede `--show`, que e a bandeira que faz o painel nascer no ecra
REM dele; (3) `AGENTS.md` tem de conter o marcador SOTTO_NEVER_ON_OWNER_SCREEN,
REM porque uma lei que so vive na cabeca de quem a aprendeu desaparece no fim
REM do contexto. A divida ANTERIOR a regra (13 instrumentos com input sintetico,
REM 2 harnesses com --show) esta CONGELADA em `_main\lane-screen-baseline.json`
REM e NAO pode crescer -- o detector le CODIGO, nao comentarios, para nao
REM castigar quem documenta a regra.
REM O BRACO NEGATIVO: quatro mutantes (input sintetico novo, --show novo,
REM marcador apagado, ficheiro do baseline a CRESCER) tem de virar vermelho.
REM rc=1 POR DESENHO (o `--neg-arm` REPROVA de proposito) e o texto
REM `NEG-ARM PASS` tem de aparecer.
if exist _main\lane-screen-gate.py (
  call :step lane-screen-gate 0 "_main\lane-screen-gate.py;_main\lane-screen-baseline.json;AGENTS.md" "%OUT%\lane-screen-gate.log" python _main\lane-screen-gate.py
  call :record lane-screen-gate !STEP_RC!
) else ( call :record lane-screen-gate MISSING )
if exist _main\lane-screen-gate.py (
  call :step red-as-expected-lane-screen-gate 1 "_main\lane-screen-gate.py;_main\lane-screen-baseline.json" "%OUT%\lane-screen-gate-neg.log" python _main\lane-screen-gate.py --neg-arm
  call :expectred red-as-expected-lane-screen-gate !STEP_RC! "%OUT%\lane-screen-gate-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-lane-screen-gate MISSING "%OUT%\lane-screen-gate-neg.log" "NEG-ARM PASS" )
REM -- caption-dup-repro: o laco do B5 (a legenda duplicada). A prova do detector vive DENTRO do
REM passo -- a fase 4 tira a guarda ao `history_append` e exige que o replay fique VERMELHO -- por
REM isso nao ha um `red-as-expected-*` separado: se o detector ficar cego, e ESTE passo que fica
REM vermelho. Ele tambem mede o historico real (fase 1) e minimiza um par real (fase 2).
if exist _main\caption-dup-repro.py (
  call :step caption-dup-repro 0 "_main\caption-dup-repro.py;app\webview\sotto_webview.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\caption-dup-repro.log" python _main\caption-dup-repro.py
  call :record caption-dup-repro !STEP_RC!
) else ( call :record caption-dup-repro MISSING )
REM
REM -- O FECHO DAS RECLAMACOES (2026-10-22) --------------------------------
REM `complaints-closure-gate.py` le o corpus do dono (148 mensagens para H:\sotto),
REM separa as 81 reclamacoes por uma lista de padroes DECLARADA, e exige uma seccao
REM por id em `.opencode/complaints-closure.md` com `evidence:` executada (rc=0 e
REM bloco de saida) e `status: closed`. Julga FICHEIROS: nao lanca nada.
REM O BRACO NEGATIVO tira a evidencia de uma seccao e inventa um id: rc=1 POR
REM DESENHO, e o texto `NEG-ARM PASS` tem de aparecer.
if exist _main\complaints-closure-gate.py (
  call :step complaints-closure 0 "_main\complaints-closure-gate.py;.opencode\complaints-closure.md;_main\complaints_canon.py;_main\complaints-closure-build.py" "%OUT%\complaints-closure.log" python _main\complaints-closure-gate.py
  call :record complaints-closure !STEP_RC!
) else ( call :record complaints-closure MISSING )
if exist _main\complaints-closure-gate.py (
  call :step red-as-expected-complaints-closure 1 "_main\complaints-closure-gate.py;.opencode\complaints-closure.md" "%OUT%\complaints-closure-neg.log" python _main\complaints-closure-gate.py --neg-arm
  call :expectred red-as-expected-complaints-closure !STEP_RC! "%OUT%\complaints-closure-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-complaints-closure MISSING "%OUT%\complaints-closure-neg.log" "NEG-ARM PASS" )
REM
REM `youtube-paint-first-oracle.py` julga a correcao do dono de 2026-10-22 09:35
REM (*"tu so viu carregar a pagina depois de varios segundos de ja ter carregado?
REM arruma isso"*): a legenda passa a mostrar as palavras que o player JA pinta em
REM vez de ficar vazia a espera do track. Duas armas + um mutante que apaga a chamada.
if exist _main\youtube-paint-first-oracle.py (
  call :step youtube-paint-first 0 "_main\youtube-paint-first-oracle.py;app\webview\sotto_webview.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\youtube-paint-first.log" python _main\youtube-paint-first-oracle.py
  call :record youtube-paint-first !STEP_RC!
) else ( call :record youtube-paint-first MISSING )
if exist _main\youtube-paint-first-oracle.py (
  call :step red-as-expected-youtube-paint-first 1 "_main\youtube-paint-first-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-paint-first-neg.log" python _main\youtube-paint-first-oracle.py --neg-arm
  call :expectred red-as-expected-youtube-paint-first !STEP_RC! "%OUT%\youtube-paint-first-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-paint-first MISSING "%OUT%\youtube-paint-first-neg.log" "NEG-ARM PASS" )
REM
REM `youtube-foreign-paint-oracle.py` julga o defeito medido em 2026-10-23 com
REM `_main\yt-1to1-live-compare.py`: o player PINTA a traducao (`lang=pt`) enquanto a
REM politica serve `en-orig`, o alinhamento por texto nao tem o que alinhar e a app
REM devolvia `painted-other-track` PARA SEMPRE -- o dono ficou sem legenda do YouTube e o
REM ASR tomou o lugar. A cura: o RELOGIO do player escolhe a cue da faixa SERVIDA, e so
REM enquanto ANDA (o congelado e medido). Quatro bracos, tres mutantes, neg-arm executado.
if exist _main\youtube-foreign-paint-oracle.py (
  call :step youtube-foreign-paint 0 "_main\youtube-foreign-paint-oracle.py;app\webview\sotto_webview.py;app\webview\youtube_captions.py" "%OUT%\youtube-foreign-paint.log" python _main\youtube-foreign-paint-oracle.py
  call :record youtube-foreign-paint !STEP_RC!
) else ( call :record youtube-foreign-paint MISSING )
if exist _main\youtube-foreign-paint-oracle.py (
  call :step red-as-expected-youtube-foreign-paint 1 "_main\youtube-foreign-paint-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-foreign-paint-neg.log" python _main\youtube-foreign-paint-oracle.py --neg-arm
  call :expectred red-as-expected-youtube-foreign-paint !STEP_RC! "%OUT%\youtube-foreign-paint-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-foreign-paint MISSING "%OUT%\youtube-foreign-paint-neg.log" "NEG-ARM PASS" )
REM `input-path-oracle.py` julga o defeito de 2026-10-23, medido no log do dono:
REM `OUTSIDE_CLICK_HOOK installed=true type=WH_MOUSE_LL` 22 ms depois do arranque
REM com o painel NUNCA mostrado -- um hook global poe TODOS os eventos do rato a
REM passar por um callback Python, e o cursor soluça enquanto o resto do sistema
REM nao (e fica bom sob Ctrl+Alt+Del, que nao entrega hooks de utilizador). O
REM portao julga FICHEIROS + o estado de um objecto: NAO instala hook, NAO cria
REM janela, NAO lanca nada. Seis bracos, quatro mutantes, neg-arm executado.
if exist _main\input-path-oracle.py (
  call :step input-path 0 "_main\input-path-oracle.py;app\webview\sotto_webview.py" "%OUT%\input-path.log" python _main\input-path-oracle.py
  call :record input-path !STEP_RC!
) else ( call :record input-path MISSING )
if exist _main\input-path-oracle.py (
  call :step red-as-expected-input-path 1 "_main\input-path-oracle.py;app\webview\sotto_webview.py" "%OUT%\input-path-neg.log" python _main\input-path-oracle.py --neg-arm
  call :expectred red-as-expected-input-path !STEP_RC! "%OUT%\input-path-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-input-path MISSING "%OUT%\input-path-neg.log" "NEG-ARM PASS" )
REM `exception-hygiene-oracle.py` e a lei do "fix on sight" (consultgpt,
REM `.cursor/rules/fix-on-sight.mdc`) mecanizada como CATRACA: 40 `except
REM Exception: pass` sem razao escrita no produto (medido 2026-10-23, 11
REM ficheiros) nao podem AUMENTAR. Mudar 40 tipos num turno parte o produto; a
REM catraca impede o proximo em silencio e obriga a baixar o numero quando a
REM divida encolhe. AST, nao substring; a isencao e o COMENTARIO e o braco C3
REM prova-o no sentido negativo. Quatro mutantes, neg-arm executado.
if exist _main\exception-hygiene-oracle.py (
  call :step exception-hygiene 0 "_main\exception-hygiene-oracle.py;_main\exception-baseline.json;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\exception-hygiene.log" python _main\exception-hygiene-oracle.py
  call :record exception-hygiene !STEP_RC!
) else ( call :record exception-hygiene MISSING )
if exist _main\exception-hygiene-oracle.py (
  call :step red-as-expected-exception-hygiene 1 "_main\exception-hygiene-oracle.py;_main\exception-baseline.json" "%OUT%\exception-hygiene-neg.log" python _main\exception-hygiene-oracle.py --neg-arm
  call :expectred red-as-expected-exception-hygiene !STEP_RC! "%OUT%\exception-hygiene-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-exception-hygiene MISSING "%OUT%\exception-hygiene-neg.log" "NEG-ARM PASS" )
REM `seam-coverage-oracle.py` e a lei mais forte da nota de 2026-10-23 do
REM Superharness (`runs/workflow-quality-loop-findings.md`, §"The missing
REM control"): a cobertura que conta e INVCADORES ENUMERADOS com controlo
REM positivo a passar e NEGATIVO a falhar NO INVOCADOR REAL, sobre o total. Um
REM mutante qualquer a deixar o portao vermelho nao diz QUAL invocador ficou
REM desprotegido -- e a primeira passagem deste trabalho deixava tres sem
REM controlo (encerramento, canal entre threads, segundo tipo de hook). Nove
REM invocadores no inventario, cada um com o seu braco e o seu mutante.
REM Nao lanca nada: importa a shell em processo, sem janela e sem hook.
if exist _main\seam-coverage-oracle.py (
  call :step seam-coverage 0 "_main\seam-coverage-oracle.py;_main\seam-inventory.json;_main\input-path-oracle.py;app\webview\sotto_webview.py" "%OUT%\seam-coverage.log" python _main\seam-coverage-oracle.py
  call :record seam-coverage !STEP_RC!
) else ( call :record seam-coverage MISSING )
if exist _main\seam-coverage-oracle.py (
  call :step red-as-expected-seam-coverage 1 "_main\seam-coverage-oracle.py;_main\seam-inventory.json" "%OUT%\seam-coverage-neg.log" python _main\seam-coverage-oracle.py --neg-arm
  call :expectred red-as-expected-seam-coverage !STEP_RC! "%OUT%\seam-coverage-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-seam-coverage MISSING "%OUT%\seam-coverage-neg.log" "NEG-ARM PASS" )
REM `bug-ledger-oracle.py` e a maquina de estados da nota do manager
REM (`state/research/bug-hunt-workflow-approaches.md`, 2026-10-23): reported ->
REM reproduced -> cause-isolated -> fixed -> verified -> recurrence-watch, e
REM "fixed" NUNCA pode ser apresentado como "verified". O portao exige que
REM `fixed` cite um passo DA BATERIA e o seu braco negativo, e que `verified`
REM tenha um verificador que nao seja o autor. Hoje os dois bugs estao FIXED,
REM NOT VERIFIED -- e o portao di-lo em letras grandes.
if exist _main\bug-ledger-oracle.py (
  call :step bug-ledger 0 "_main\bug-ledger-oracle.py;_main\bug-ledger.json;_main\incidents\INC-20261023-01-mouse-hook.md;_main\receipt-20261021-open-close-stall.md" "%OUT%\bug-ledger.log" python _main\bug-ledger-oracle.py
  call :record bug-ledger !STEP_RC!
) else ( call :record bug-ledger MISSING )
if exist _main\bug-ledger-oracle.py (
  call :step red-as-expected-bug-ledger 1 "_main\bug-ledger-oracle.py;_main\bug-ledger.json" "%OUT%\bug-ledger-neg.log" python _main\bug-ledger-oracle.py --neg-arm
  call :expectred red-as-expected-bug-ledger !STEP_RC! "%OUT%\bug-ledger-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-bug-ledger MISSING "%OUT%\bug-ledger-neg.log" "NEG-ARM PASS" )
REM `tooling-intent-oracle.py` fecha o buraco que a nota do manager chama de
REM `blocked_bug_ids`/`evidence_unblocked`: uma ferramenta de enforcement so e
REM elegivel se disser que bug desbloqueia (`# BLOCKS: BUG-...`) ou se declarar
REM trabalho de capacidade (`# NO-BUG: razao`). Um id tem de existir no ledger.
REM A divida antiga (160 ficheiros sem declaracao) esta no baseline e NAO pode
REM crescer: e um ratchet, nao uma amnistia. Ha ~165 ferramentas em _main e
REM nenhuma dizia para que existia.
if exist _main\tooling-intent-oracle.py (
  call :step tooling-intent 0 "_main\tooling-intent-oracle.py;_main\tooling-intent-baseline.json;_main\bug-ledger.json" "%OUT%\tooling-intent.log" python _main\tooling-intent-oracle.py
  call :record tooling-intent !STEP_RC!
) else ( call :record tooling-intent MISSING )
if exist _main\tooling-intent-oracle.py (
  call :step red-as-expected-tooling-intent 1 "_main\tooling-intent-oracle.py;_main\tooling-intent-baseline.json" "%OUT%\tooling-intent-neg.log" python _main\tooling-intent-oracle.py --neg-arm
  call :expectred red-as-expected-tooling-intent !STEP_RC! "%OUT%\tooling-intent-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-tooling-intent MISSING "%OUT%\tooling-intent-neg.log" "NEG-ARM PASS" )
REM `external-resume-oracle.py` fecha a ORDEM 3 do dono. O `AGENTS.md` dizia que
REM `on_external_captions_released()` NAO trazia o worker de volta; re-medido em
REM 2026-10-23 ele traz, atras de quatro guardas e de um piso de 45 s -- mas nada
REM o provava, e um comportamento certo sem controlo volta a partir-se em
REM silencio. Oito bracos (exiting, park, pausa, escondido, legenda visivel,
REM piso, caminho feliz, depois do piso) e oito mutantes, cada um a derrubar O
REM SEU braco. Nao lanca nada: importa a shell e usa um `self` falso.
if exist _main\external-resume-oracle.py (
  call :step external-resume 0 "_main\external-resume-oracle.py;app\webview\sotto_webview.py" "%OUT%\external-resume.log" python _main\external-resume-oracle.py
  call :record external-resume !STEP_RC!
) else ( call :record external-resume MISSING )
if exist _main\external-resume-oracle.py (
  call :step red-as-expected-external-resume 1 "_main\external-resume-oracle.py;app\webview\sotto_webview.py" "%OUT%\external-resume-neg.log" python _main\external-resume-oracle.py --neg-arm
  call :expectred red-as-expected-external-resume !STEP_RC! "%OUT%\external-resume-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-external-resume MISSING "%OUT%\external-resume-neg.log" "NEG-ARM PASS" )
REM `silence-kill-oracle.py` -- UM KILL DO PROPRIO SHELL NAO E' UMA MORTE DO WORKER.
REM Medido no log do dono: das 10 `BRIDGE_SILENT` anomalas, 9 sao seguidas no mesmo pid do
REM `BRIDGE_EXIT rc=1` que o `TerminateProcess` devolve -- e o `_wait` publicava-o como
REM `BRIDGE_DEATH kind=error`, painel vermelho e recarga contada como falha, num worker que
REM transcrevia. O caso que doi' (19:36:40) tinha `CAPTION_APPLIED count=200` 0,4 s antes: o
REM `blocks` congela durante um lote longo e o cao de guarda mata quem trabalha. Agora o kill
REM publica `BRIDGE_KILLED` e `killed=true`, e as linhas de lote contam como progresso. Cinco
REM arms; o braco negativo muta a marca do kill e as PROGRESS_TAGS e exige as duas RED.
if exist _main\silence-kill-oracle.py (
  call :step silence-kill 0 "_main\silence-kill-oracle.py;app\webview\sotto_webview.py" "%OUT%\silence-kill.log" python _main\silence-kill-oracle.py
  call :record silence-kill !STEP_RC!
) else ( call :record silence-kill MISSING )
if exist _main\silence-kill-oracle.py (
  call :step red-as-expected-silence-kill 1 "_main\silence-kill-oracle.py;app\webview\sotto_webview.py" "%OUT%\silence-kill-neg.log" python _main\silence-kill-oracle.py --neg-arm
  call :expectred red-as-expected-silence-kill !STEP_RC! "%OUT%\silence-kill-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-silence-kill MISSING "%OUT%\silence-kill-neg.log" "NEG-ARM PASS" )
REM O CHURN DE RECARGA (2026-11-04). Medido no log do dono, duas metades da mesma
REM moeda: `BRIDGE_SILENT ms=30000 pid=26440` as 03:20:13 matou um worker que estava
REM quieto porque o tap aberto sobre uma maquina QUIETA nao escreve nada por desenho
REM (`endpoint-idle` -> `stop.wait(0.1)`, e `WORKER_STATS` nao conta enquanto `blocks`
REM nao avanca); e `BRIDGE_EXIT rc=0` as 03:22:41 respawnou as 03:22:43 -- 2,0 s, ou
REM seja 1,9 GB de modelo recarregado para um worker que terminou por vontade propria.
REM O worker passou a publicar `WORKER_ALIVE` a partir do LACO (prova de progresso: cala
REM quando o laco trava) e a saida limpa tem piso de 20 s. O braco negativo muta o piso
REM numa copia do shell e o `progress` numa copia do worker, e exige as duas arms RED.
if exist _main\worker-churn-oracle.py (
  call :step worker-churn 0 "_main\worker-churn-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\worker-churn.log" python _main\worker-churn-oracle.py
  call :record worker-churn !STEP_RC!
) else ( call :record worker-churn MISSING )
if exist _main\worker-churn-oracle.py (
  call :step red-as-expected-worker-churn 1 "_main\worker-churn-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\worker-churn-neg.log" python _main\worker-churn-oracle.py --neg-arm
  call :expectred red-as-expected-worker-churn !STEP_RC! "%OUT%\worker-churn-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-worker-churn MISSING "%OUT%\worker-churn-neg.log" "NEG-ARM: PASS" )
REM `rss-trend-oracle.py` -- A MEMORIA TEM DE SER UMA SERIE. O worker publica `rss_mb` em cada
REM `WORKER_STATS`, mas a shell so' o guardava na CAUDA DA MORTE: o numero existia exactamente
REM quando ja' nao havia o que medir, e 'leak' ficava uma afirmacao sem medida. Desde 2026-11-02
REM a shell escreve `BRIDGE_RSS rss_mb=.. blocks=..` uma vez por minuto, e este passo julga a
REM forma: fuga linear (FLAG), aquecimento que assenta (ok), dente de serra (ok) e serie curta
REM (UNKNOWN -- NUNCA verde). O braco negativo poe o limiar em 1e9 e a arm da fuga tem de cair.
if exist _main\rss-trend-oracle.py (
  call :step rss-trend 0 "_main\rss-trend-oracle.py;app\webview\sotto_webview.py" "%OUT%\rss-trend.log" python _main\rss-trend-oracle.py
  call :record rss-trend !STEP_RC!
) else ( call :record rss-trend MISSING )
if exist _main\rss-trend-oracle.py (
  call :step red-as-expected-rss-trend 1 "_main\rss-trend-oracle.py" "%OUT%\rss-trend-neg.log" python _main\rss-trend-oracle.py --neg-arm
  call :expectred red-as-expected-rss-trend !STEP_RC! "%OUT%\rss-trend-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-rss-trend MISSING "%OUT%\rss-trend-neg.log" "NEG-ARM PASS" )
REM `death-cause-oracle.py` -- A MORTE DO WORKER TEM DE PUBLICAR A CAUSA. Medido na
REM sessao do dono a jogar (2026-11-02): o worker morreu DUAS vezes `rc=1` (19:22:29 e
REM 19:36:40, 14-26 s de recarga cada) e o `BRIDGE_DEATH` publicava TRES linhas de
REM stderr -- `WORKER_STATS` + `REDUX_BATCH_KICK` -- com o traceback de fora. As duas
REM mortes ficaram indiagnosticaveis. Agora a cauda guarda 40 linhas e a morte publica
REM `BRIDGE_DEATH_CAUSE <excecao>`. Quatro arms com um FILHO real, e o braco negativo
REM repoe `STDERR_TAIL_MAX = 3` e tem de derrubar a arm da retencao.
if exist _main\death-cause-oracle.py (
  call :step death-cause 0 "_main\death-cause-oracle.py;app\webview\sotto_webview.py" "%OUT%\death-cause.log" python _main\death-cause-oracle.py
  call :record death-cause !STEP_RC!
) else ( call :record death-cause MISSING )
if exist _main\death-cause-oracle.py (
  call :step red-as-expected-death-cause 1 "_main\death-cause-oracle.py;app\webview\sotto_webview.py" "%OUT%\death-cause-neg.log" python _main\death-cause-oracle.py --neg-arm
  call :expectred red-as-expected-death-cause !STEP_RC! "%OUT%\death-cause-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-death-cause MISSING "%OUT%\death-cause-neg.log" "NEG-ARM PASS" )
REM `caption-seam-dedup-oracle.py` -- a repeticao no seam do chunk. Medido na
REM captura real do dono: os chunks `'umas'` (16,80-17,36) e `'tem umas'`
REM (17,36-17,92) produziam a linha `... tem umas tem umas youtuber ...`. O carry
REM do predictor NAO se desliga (medido no mesmo audio: sem carry o run morre para
REM `Caram Tem`), por isso a cura e' de texto, em `join_fragments`. Sete arms e o
REM braco negativo que poe `SEAM_REPEAT_MIN_WORDS = 1` e tem de derrubar a arm B
REM (uma palavra repetida e' fala, nao artefacto).
if exist _main\caption-seam-dedup-oracle.py (
  call :step caption-seam-dedup 0 "_main\caption-seam-dedup-oracle.py;worker\sotto_worker.py" "%OUT%\caption-seam-dedup.log" python _main\caption-seam-dedup-oracle.py
  call :record caption-seam-dedup !STEP_RC!
) else ( call :record caption-seam-dedup MISSING )
if exist _main\caption-seam-dedup-oracle.py (
  call :step red-as-expected-caption-seam-dedup 1 "_main\caption-seam-dedup-oracle.py;worker\sotto_worker.py" "%OUT%\caption-seam-dedup-neg.log" python _main\caption-seam-dedup-oracle.py --neg-arm
  call :expectred red-as-expected-caption-seam-dedup !STEP_RC! "%OUT%\caption-seam-dedup-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-caption-seam-dedup MISSING "%OUT%\caption-seam-dedup-neg.log" "NEG-ARM PASS" )
REM `agc_order_probe.py` arm D -- O TETO DE PICO. O ganho era aplicado e depois
REM `np.clip`-ado, um CORTE DURO; na captura real do dono (loopback `VoiceMeeter
REM Input`, 30 s) o `WORKER_STATS` publicou `peak_out=1.000000` em TODOS os ticks e
REM ganhos ate' +23,5 dB -- o modelo ouvia topos achatados e o texto dele saia
REM instavel entre duas passagens do MESMO audio. A arm D exige pico de saida <=
REM `AGC_CEILING` com `limited_blocks > 0`, e o braco negativo desarma o teto num
REM TOKEN numa copia do worker e exige o RED no mesmo `main()`.
if exist _main\agc_order_probe.py (
  call :step agc-peak-ceiling 0 "_main\agc_order_probe.py;worker\sotto_worker.py" "%OUT%\agc-peak-ceiling.log" python _main\agc_order_probe.py
  call :record agc-peak-ceiling !STEP_RC!
) else ( call :record agc-peak-ceiling MISSING )
if exist _main\agc_order_probe.py (
  call :step red-as-expected-agc-peak-ceiling 1 "_main\agc_order_probe.py;worker\sotto_worker.py" "%OUT%\agc-peak-ceiling-neg.log" python _main\agc_order_probe.py --neg-arm
  call :expectred red-as-expected-agc-peak-ceiling !STEP_RC! "%OUT%\agc-peak-ceiling-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-agc-peak-ceiling MISSING "%OUT%\agc-peak-ceiling-neg.log" "NEG-ARM PASS" )
REM `reveal-park-oracle.py` fecha as duas metades que o dono reportou em 2026-11-02:
REM a frase do YouTube entrando de uma vez (o ancora do relogio fino so' existia no
REM ramo `painted`, e o ramo do relogio so' mudava o ecra quando o UIA mudava de
REM segundo) e o microfone PARKED para sempre (`BRIDGE_STOP reason=external-captions`
REM as 18:52:13, `spawns=1` ate' ao fim da sessao dele). Cinco arms: ancora nos dois
REM ramos do relogio, a revelacao palavra a palavra contra o `tOffsetMs` do fixture,
REM o microfone a voltar depois de 30 s, e o piso que impede o buraco entre cues de
REM custar uma carga de modelo. Tres mutantes, cada um derruba O SEU braco.
if exist _main\reveal-park-oracle.py (
  call :step reveal-park 0 "_main\reveal-park-oracle.py;app\webview\sotto_webview.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_window.py;app\webview\youtube_captions.py" "%OUT%\reveal-park.log" python _main\reveal-park-oracle.py
  call :record reveal-park !STEP_RC!
) else ( call :record reveal-park MISSING )
if exist _main\reveal-park-oracle.py (
  call :step red-as-expected-reveal-park 1 "_main\reveal-park-oracle.py;app\webview\sotto_webview.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_window.py;app\webview\youtube_captions.py" "%OUT%\reveal-park-neg.log" python _main\reveal-park-oracle.py --neg-arm
  call :expectred red-as-expected-reveal-park !STEP_RC! "%OUT%\reveal-park-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-reveal-park MISSING "%OUT%\reveal-park-neg.log" "NEG-ARM PASS" )
REM `youtube-verbatim-oracle.py` fecha as TRES imagens que o dono mandou a 2026-11-02,
REM verbatim: *"sotto devia ta copiando 1:1 sem truncar palavras"* e *"ja nao ta
REM aparecendo"*. O ramo pintado deixou de re-quebrar a partir do track (a janela
REM cortava em `cap = min(pintado, relogio_de_palavra)`: meia palavra, linha a
REM construir-se, e o cue anterior empilhado por baixo) e passou a devolver as
REM LINHAS que o player desenha, uma por linha, inteiras, com o `>>` removido.
REM `always` porque le o SHELL e o `youtube_window.py` ao vivo.
if exist _main\youtube-verbatim-oracle.py (
  call :step youtube-verbatim 0 "_main\youtube-verbatim-oracle.py;app\webview\sotto_webview.py;app\webview\youtube_window.py" "%OUT%\youtube-verbatim.log" python _main\youtube-verbatim-oracle.py
  call :record youtube-verbatim !STEP_RC!
) else ( call :record youtube-verbatim MISSING )
if exist _main\youtube-verbatim-oracle.py (
  call :step red-as-expected-youtube-verbatim 1 "_main\youtube-verbatim-oracle.py;app\webview\youtube_window.py" "%OUT%\youtube-verbatim-neg.log" python _main\youtube-verbatim-oracle.py --neg-arm
  call :expectred red-as-expected-youtube-verbatim !STEP_RC! "%OUT%\youtube-verbatim-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-youtube-verbatim MISSING "%OUT%\youtube-verbatim-neg.log" "NEG-ARM: PASS" )
REM `code-health-oracle.py` e o RATCHET do "horrivel" medido: 758 679 B / 13 273
REM linhas num modulo, uma funcao `main` de 2 297 linhas, 82 `except: pass`. Nao
REM preme por um big-bang (as notas dizem `smaller batches`); mede sete factos por
REM ficheiro e falha em QUALQUER piora. `always` de proposito: a populacao e um
REM DIRECTORIO, logo uma lista de deps nunca estaria completa -- e um passo em
REM cache com uma populacao que mudou e um falso verde.
if exist _main\code-health-oracle.py (
  call :step always code-health 0 "_main\code-health-oracle.py" "%OUT%\code-health.log" python _main\code-health-oracle.py
  call :record code-health !STEP_RC!
) else ( call :record code-health MISSING )
if exist _main\code-health-oracle.py (
  call :step always red-as-expected-code-health 1 "_main\code-health-oracle.py" "%OUT%\code-health-neg.log" python _main\code-health-oracle.py --neg-arm
  call :expectred red-as-expected-code-health !STEP_RC! "%OUT%\code-health-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-code-health MISSING "%OUT%\code-health-neg.log" "NEG-ARM PASS" )
REM NOMES USADOS E NUNCA DEFINIDOS (2026-11-01). `py_compile` olha a sintaxe e a
REM bateria IMPORTA os modulos -- um import passa. Medido duas vezes hoje, as duas em
REM producao: o worker morreu no arranque com `NameError: name 'REDUX_LIVE_DEFAULT'
REM is not defined` (a lista de `from engine_switch import (...)` perdeu o nome) e o
REM caminho do despejo chamava `slice_blocks` quando o nome e' `_slice_blocks` --
REM logo o NameError saia do `except BaseException` e matava o worker. `always` de
REM proposito: a populacao e' uma LISTA de ficheiros de producao, e uma lista de deps
REM em cache descreveria um codigo que ja' mudou.
if exist _main\undefined-names-oracle.py (
  call :step always undefined-names 0 "_main\undefined-names-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py;worker\engine_policy.py;worker\engine_switch.py" "%OUT%\undefined-names.log" python _main\undefined-names-oracle.py
  call :record undefined-names !STEP_RC!
) else ( call :record undefined-names MISSING )
if exist _main\undefined-names-oracle.py (
  call :step always red-as-expected-undefined-names 1 "_main\undefined-names-oracle.py" "%OUT%\undefined-names-neg.log" python _main\undefined-names-oracle.py --neg-arm
  call :expectred red-as-expected-undefined-names !STEP_RC! "%OUT%\undefined-names-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-undefined-names MISSING "%OUT%\undefined-names-neg.log" "NEG-ARM PASS" )
REM A BATTERIA QUE NAO ABRE O MUNDO DO DONO (owner, 2026-10-21, verbatim:
REM *"tu ta fazendo algo que faz meu pc travar/stutter?"* e *"tu vai garantir que
REM minha reclamacao nunca mais aconteca"*). O portão julga FICHEIROS e corre as
REM ETIQUETAS DA PROPRIA BATERIA sobre um passo falso -- e o passo pesado e o
REM opt-in, entao o portão nao abre a app do dono. O braco negativo rc=1 POR
REM DESENHO.
if exist _main\battery-heavy-gate.py (
  call :step battery-heavy-gate 0 "_main\battery-heavy-gate.py;_main\_audit-verify-all.cmd;_main\_strip-surface-probe.py;_main\_strip-stats-log-probe.py;_main\_strip-restore-probe.py;_main\_strip-stats-probe.py;_main\panel-exit3-oracle.py;_main\mute-audio-oracle.py" "%OUT%\battery-heavy-gate.log" python _main\battery-heavy-gate.py
  call :record battery-heavy-gate !STEP_RC!
) else ( call :record battery-heavy-gate MISSING )
if exist _main\battery-heavy-gate.py (
  call :step red-as-expected-battery-heavy-gate 1 "_main\battery-heavy-gate.py;_main\_audit-verify-all.cmd;_main\_strip-surface-probe.py;_main\_strip-stats-log-probe.py;_main\_strip-restore-probe.py;_main\_strip-stats-probe.py;_main\panel-exit3-oracle.py;_main\mute-audio-oracle.py" "%OUT%\battery-heavy-gate-neg.log" python _main\battery-heavy-gate.py --neg-arm
  call :expectred red-as-expected-battery-heavy-gate !STEP_RC! "%OUT%\battery-heavy-gate-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-battery-heavy-gate MISSING "%OUT%\battery-heavy-gate-neg.log" "NEG-ARM PASS" )
REM `scripts\task-resolver-gate.py` e o MANDATO do task-resolver como MECANISMO. O
REM `AGENTS.md` manda usar a skill em todo o trabalho nao-trivial, e a skill manda
REM construir o portao ANTES da edicao dependente -- e nada o provava. O
REM `check-bug-hunt-wiring.py` fecha a mesma classe para o bug-hunt e o task-resolver
REM ficou de fora. Seis checks: o mandato no AGENTS.md, a versao, o sha256 da copia do
REM repo contra o canonico (uma copia divergente e uma segunda fonte de verdade), a lei
REM do bootstrap, o vocabulario de evidencia, e -- o que fecha o circuito -- os DOIS
REM portoes deste mandato a serem CORRIDOS por esta bateria, cada um com o seu braco
REM negativo. Nao lanca nada: le tres ficheiros.
if exist scripts\task-resolver-gate.py (
  call :step task-resolver-gate 0 "scripts\task-resolver-gate.py;AGENTS.md;.agents\skills\task-resolver\SKILL.md;_main\_audit-verify-all.cmd" "%OUT%\task-resolver-gate.log" python scripts\task-resolver-gate.py
  call :record task-resolver-gate !STEP_RC!
) else ( call :record task-resolver-gate MISSING )
if exist scripts\task-resolver-gate.py (
  call :step red-as-expected-task-resolver-gate 1 "scripts\task-resolver-gate.py;AGENTS.md;.agents\skills\task-resolver\SKILL.md;_main\_audit-verify-all.cmd" "%OUT%\task-resolver-gate-neg.log" python scripts\task-resolver-gate.py --neg-arm
  call :expectred red-as-expected-task-resolver-gate !STEP_RC! "%OUT%\task-resolver-gate-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-task-resolver-gate MISSING "%OUT%\task-resolver-gate-neg.log" "NEG-ARM PASS" )
REM `_main\claims-date-oracle.py` e o P0.3 do roadmap de observabilidade de 2026-10-23:
REM "uma afirmacao numerica no AGENTS.md sem data/medicao ao lado e vermelha; baseline
REM ratchet". A unidade e o BLOCO e nao a linha -- medido 2026-10-25, a leitura
REM linha-a-linha acusava 23 sitios e quase todos eram a continuacao de uma frase cuja
REM cabeca carrega a data. Quatro checks e seis mutantes; o baseline (4 entradas) so pode
REM encolher, e o tecto vive no CODIGO para o JSON nao poder levantar o seu proprio.
if exist _main\claims-date-oracle.py (
  call :step claims-date 0 "_main\claims-date-oracle.py;_main\claims-date-baseline.json;AGENTS.md" "%OUT%\claims-date.log" python _main\claims-date-oracle.py
  call :record claims-date !STEP_RC!
) else ( call :record claims-date MISSING )
if exist _main\claims-date-oracle.py (
  call :step red-as-expected-claims-date 1 "_main\claims-date-oracle.py;_main\claims-date-baseline.json;AGENTS.md" "%OUT%\claims-date-neg.log" python _main\claims-date-oracle.py --neg-arm
  call :expectred red-as-expected-claims-date !STEP_RC! "%OUT%\claims-date-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-claims-date MISSING "%OUT%\claims-date-neg.log" "NEG-ARM PASS" )

REM --- P3: O PRIMEIRO FRAME DO PAINEL (2026-11-01, ordem do dono) ---------------
REM "o painel dar show nao deve carregar o background e mostrar, e depois carregar a ui" -- o
REM defeito e' o frame 0 de uma janela recem-mapeada chegar ao ecra sem conteudo. O censo
REM `_main\panel-paint-first-census.py` MEDE isso em pixeis (std/spread sobre o buffer da
REM janela) e compara tres bracos na mesma corrida: a app CURADA, a app do rev ANTIGO
REM (`uncured`, que TEM de dar blank>0) e dois controles sinteticos. Medido 2026-11-01:
REM cured [0,0,0] / uncured [17,0,0] first_content 289,5 ms.
REM
REM A MEDICAO e' `heavy` (larga uma instancia privada da app: o portao `battery-class`
REM recusa um passo `always` que nomeie um largador) e grava a leitura. O passo BARATO
REM re-julga essa leitura pela MESMA funcao `verdict()` do censo -- sem relancar nada --
REM e o braco negativo muta uma leitura limpa em QUATRO pontos e exige que os quatro
REM sejam recusados, para o portao nao ser um comentario que so' sabe dizer PASS.
REM O MESMO defeito, no PROCESSO VIVO do dono: cada `PANEL_SHOWN` da sessao que ele carrega
REM tem de trazer `paint_ack=true` e `wait_ms<=400`. Sem show nenhum desde o arranque o
REM oraculo diz `VERDICT: SKIPPED` e o passo skip-capable conta-o como SKIPPED -- nunca
REM como um portao que passou. As tres mutacoes do `--neg-arm` mordem uma cauda sintetica
REM limpa e tem de sair todas RED (medido: cases=3 caught=3).

REM O CARREGAR DO MODELO NAO ENGASGA O ECRA (ordem do dono: nada de stutter): as janelas
REM de carga da sessao viva (`BRIDGE_SPAWN` -> `BRIDGE_LOAD_MS`) nao podem ter um unico
REM `UI_THREAD_STALL` ou `exec_js TIMEOUT` dentro. Medido 2026-11-01 13:5x na sessao dele:
REM 4 janelas (23 s, 23 s, 27 s, 28 s), estalos=0 em todas. Sem janela na sessao, SKIPPED.
REM O terceiro braco do `--neg-arm` e' de ESPECIFICIDADE: um estalo FORA da janela nao pode
REM ser contado -- sem ele o verde nao vale nada.
if exist _main\stall-under-load-oracle.py (
call :step always stall-under-load 0 "_main\stall-under-load-oracle.py;app\webview\sotto_webview.py" "%OUT%\stall-under-load.log" python _main\stall-under-load-oracle.py
call :skipped stall-under-load !STEP_RC! "%OUT%\stall-under-load.log" "STALL-UNDER-LOAD VERDICT: GREEN" "STALL-UNDER-LOAD VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped stall-under-load MISSING "%OUT%\stall-under-load.log" "STALL-UNDER-LOAD VERDICT: GREEN" "STALL-UNDER-LOAD VERDICT: SKIPPED" "VERDICT: SKIPPED" )
if exist _main\stall-under-load-oracle.py (
call :step always red-as-expected-stall-under-load 1 "_main\stall-under-load-oracle.py" "%OUT%\stall-under-load-neg.log" python _main\stall-under-load-oracle.py --neg-arm
call :expectred red-as-expected-stall-under-load !STEP_RC! "%OUT%\stall-under-load-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-stall-under-load MISSING "%OUT%\stall-under-load-neg.log" "NEG-ARM PASS" )
if exist _main\paint-live-show-oracle.py (
call :step always paint-live-show 0 "_main\paint-live-show-oracle.py;app\webview\sotto_webview.py" "%OUT%\paint-live-show.log" python _main\paint-live-show-oracle.py
call :skipped paint-live-show !STEP_RC! "%OUT%\paint-live-show.log" "PAINT-LIVE VERDICT: GREEN" "PAINT-LIVE VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped paint-live-show MISSING "%OUT%\paint-live-show.log" "PAINT-LIVE VERDICT: GREEN" "PAINT-LIVE VERDICT: SKIPPED" "VERDICT: SKIPPED" )
if exist _main\paint-live-show-oracle.py (
call :step always red-as-expected-paint-live-show 1 "_main\paint-live-show-oracle.py" "%OUT%\paint-live-show-neg.log" python _main\paint-live-show-oracle.py --neg-arm
call :expectred red-as-expected-paint-live-show !STEP_RC! "%OUT%\paint-live-show-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-paint-live-show MISSING "%OUT%\paint-live-show-neg.log" "NEG-ARM PASS" )
if exist _main\panel-paint-first-census.py (
call :step heavy panel-paint-first-measure 0 "_main\panel-paint-first-census.py;app\webview\sotto_webview.py;app\webview\code_identity.py;app\panel\panel.js;app\panel\panel.css" "%OUT%\panel-paint-first-measure.log" python _main\panel-paint-first-census.py --run --save-json _main\_cache\panel-paint-first.json
call :record panel-paint-first-measure !STEP_RC!
) else ( call :record panel-paint-first-measure MISSING )
if exist _main\panel-paint-first-census.py (
call :step always panel-paint-first 0 "_main\panel-paint-first-census.py;_main\_cache\panel-paint-first.json" "%OUT%\panel-paint-first.log" python _main\panel-paint-first-census.py --judge _main\_cache\panel-paint-first.json
call :record panel-paint-first !STEP_RC!
) else ( call :record panel-paint-first MISSING )
if exist _main\panel-paint-first-census.py (
call :step always red-as-expected-panel-paint-first 1 "_main\panel-paint-first-census.py;_main\_cache\panel-paint-first.json" "%OUT%\panel-paint-first-neg.log" python _main\panel-paint-first-census.py --judge _main\_cache\panel-paint-first.json --neg-arm
call :expectred red-as-expected-panel-paint-first !STEP_RC! "%OUT%\panel-paint-first-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-panel-paint-first MISSING "%OUT%\panel-paint-first-neg.log" "NEG-ARM PASS" )

REM `_main\receipt-provenance-oracle.py` fecha a classe que este repo pagou em 2026-10-26: o recibo
REM de um lane declarava `route: OpenCode Go 1` e o processo que o produziu corria em `opencode-go-3`.
REM A rota declarada era a que a politica SONDA primeiro (model-routing.md: `opencode-go-1` primeiro),
REM nao a que serviu o trabalho -- uma intencao escrita no lugar de um facto medido. Uma declaracao de
REM rota no cabecalho tem de trazer a MEDICAO (`providerID=` + `session=ses_...`) e o INSTRUMENTO que a
REM produziu; uma declaracao que difere da medicao so passa se se declarar SUBSTITUIDA e nomear a
REM medicao no mesmo cabecalho. Quatro checks e quatro bracos nomeados.
REM `always` de proposito: a populacao e `state\work\**\receipt*.md`, que muda sempre que um lane
REM escreve um recibo -- um resultado em cache descreveria recibos que ja nao existem.
if exist _main\receipt-provenance-oracle.py (
  call :step always receipt-provenance 0 "_main\receipt-provenance-oracle.py" "%OUT%\receipt-provenance.log" python _main\receipt-provenance-oracle.py
  call :record receipt-provenance !STEP_RC!
) else ( call :record receipt-provenance MISSING )
if exist _main\receipt-provenance-oracle.py (
  call :step always red-as-expected-receipt-provenance 1 "_main\receipt-provenance-oracle.py" "%OUT%\receipt-provenance-neg.log" python _main\receipt-provenance-oracle.py --neg-arm
  call :expectred red-as-expected-receipt-provenance !STEP_RC! "%OUT%\receipt-provenance-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-receipt-provenance MISSING "%OUT%\receipt-provenance-neg.log" "NEG-ARM PASS" )

REM
REM === OS SETE ORACULOS QUE FALTAVAM NA BATERIA (2026-11-03) ====================
REM
REM O `battery-wiring-oracle` media-os como `new-unwired`: sete oraculos escritos
REM pelas lanes de 2026-11-03, verdes na linha de comando e SEM passo -- logo nada
REM os corria e nada garantia que continuassem a descrever a arvore. Cada par abaixo
REM e' um positivo com as suas dependencias REAIS e o seu braco negativo.
REM
REM DUAS CORRECCOES NOS PROPIOS INSTRUMENTOS foram necessarias para os poder
REM declarar, e ficam escritas porque sao defeitos de instrumento:
REM  1. `yt-loop-uia-oracle --neg-arm` respondia NEG-ARM IMPOSSIVEL: ancora ausente
REM     com rc=2: a ancora citava `return [], False` e a cura passou a devolver
REM     `return '', _src, True`. Uma ancora e' uma afirmacao sobre o fonte e
REM     envelhece como uma. Re-ancorada, o braco volta a apanhar NO-SNAP e BOOTSTRAP.
REM  2. cinco dos `--neg-arm` saiam 0 ao APANHAR o mutante. O `:expectred` exige
REM     rc=1, portanto um controlo que devolve 0 nao podia ser declarado controlo.
REM     Os cinco passaram a devolver 1 e a dizer `NEG-ARM: PASS`.
REM
call :step async-track-fetch 0 "_main\async-track-fetch-oracle.py;app\webview\sotto_webview.py" "%OUT%\async-track-fetch.log" python _main\async-track-fetch-oracle.py
call :record async-track-fetch !STEP_RC!
call :step red-as-expected-async-track-fetch 1 "_main\async-track-fetch-oracle.py;app\webview\sotto_webview.py" "%OUT%\async-track-fetch-neg.log" python _main\async-track-fetch-oracle.py --neg-arm
call :expectred red-as-expected-async-track-fetch !STEP_RC! "%OUT%\async-track-fetch-neg.log" "NEG-ARM: PASS"

call :step batch-queue-drain 0 "_main\batch-queue-drain-oracle.py;app\webview\batch_queue.py" "%OUT%\batch-queue-drain.log" python _main\batch-queue-drain-oracle.py
call :record batch-queue-drain !STEP_RC!
call :step red-as-expected-batch-queue-drain 1 "_main\batch-queue-drain-oracle.py;app\webview\batch_queue.py" "%OUT%\batch-queue-drain-neg.log" python _main\batch-queue-drain-oracle.py --neg-arm
call :expectred red-as-expected-batch-queue-drain !STEP_RC! "%OUT%\batch-queue-drain-neg.log" "NEG-ARM: PASS"

call :step hotkey-live-toggle 0 "_main\hotkey-live-toggle-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\hotkey-live-toggle.log" python _main\hotkey-live-toggle-oracle.py
call :record hotkey-live-toggle !STEP_RC!
call :step red-as-expected-hotkey-live-toggle 1 "_main\hotkey-live-toggle-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\hotkey-live-toggle-neg.log" python _main\hotkey-live-toggle-oracle.py --neg-arm
call :expectred red-as-expected-hotkey-live-toggle !STEP_RC! "%OUT%\hotkey-live-toggle-neg.log" "NEG-ARM PASS"

call :step loading-placeholder 0 "_main\loading-placeholder-oracle.py;app\webview\sotto_webview.py" "%OUT%\loading-placeholder.log" python _main\loading-placeholder-oracle.py
call :record loading-placeholder !STEP_RC!
call :step red-as-expected-loading-placeholder 1 "_main\loading-placeholder-oracle.py;app\webview\sotto_webview.py" "%OUT%\loading-placeholder-neg.log" python _main\loading-placeholder-oracle.py --neg-arm
call :expectred red-as-expected-loading-placeholder !STEP_RC! "%OUT%\loading-placeholder-neg.log" "NEG-ARM guard-removed"

REM `youtube-land` le' o LOG VIVO (`_main\webview-run.log`), logo corre SEMPRE e nunca
REM em cache. Sem `CAPTION_LAND` na sessao viva ele diz `YOUTUBE-LAND VERDICT: SKIPPED`
REM com rc=0 -- um passo saltado NAO e' um portao que passou, e o `:skipped` conta-o
REM SKIPPED. O braco negativo corre sobre um log SINTETICO no formato real, portanto
REM exercita-se hoje mesmo.
call :step always youtube-land 0 "_main\youtube-land-oracle.py;app\webview\caption_overlay.py;_main\webview-run.log" "%OUT%\youtube-land.log" python _main\youtube-land-oracle.py
call :skipped youtube-land !STEP_RC! "%OUT%\youtube-land.log" "YOUTUBE-LAND VERDICT: PASS" "YOUTUBE-LAND VERDICT: SKIPPED" "YOUTUBE-LAND VERDICT: SKIPPED"
call :step red-as-expected-youtube-land 1 "_main\youtube-land-oracle.py;app\webview\caption_overlay.py" "%OUT%\youtube-land-neg.log" python _main\youtube-land-oracle.py --neg-arm
call :expectred red-as-expected-youtube-land !STEP_RC! "%OUT%\youtube-land-neg.log" "NEG-ARM: PASS"

REM `time-to-first-caption` e' a ACAO DO DONO medida em ms (2026-11-04: *"uma legenda
REM ate' 3 s depois de a app estar de pe'"*). Le' o LOG VIVO (`_main\webview-run.log`)
REM e NUNCA larga a app: nenhuma janela, nenhum dispositivo de audio, nenhum modelo.
REM Logo corre SEMPRE (nunca em cache) e e' `:skipped`, nao `:record`: sem nenhuma
REM `CAPTION_PAINT` no arranque em julgamento ele diz `TIME-TO-FIRST-CAPTION VERDICT:
REM SKIPPED` com rc=0 -- um passo saltado NAO e' um portao que passou e o `:skipped`
REM conta-o em `skipped=`. Uma medicao >= 3000 ms NAO e' um skip: o oraculo sai 1 e o
REM `:skipped` reprova o passo, porque o numero e' exactamente a aceitacao.
REM O braco negativo corre sobre logs SINTETICOS em memoria (9 casos: 1,2 s tem de dar
REM PASS, 9 s e 3000 ms exactos tem de dar rc=1, um arranque anterior nao pode ser lido
REM como este, um placeholder nao e' legenda, e uma tabela de fases nao pode ficar
REM presa na marca que falta, e um log ABSENTE e' SKIPPED e nao reprova a bateria),
REM portanto exercita-se hoje mesmo.
call :step always time-to-first-caption 0 "_main\time-to-first-caption-oracle.py;_main\webview-run.log" "%OUT%\time-to-first-caption.log" python _main\time-to-first-caption-oracle.py --stale-skips
call :skipped time-to-first-caption !STEP_RC! "%OUT%\time-to-first-caption.log" "TIME-TO-FIRST-CAPTION VERDICT: PASS" "TIME-TO-FIRST-CAPTION VERDICT: SKIPPED" "TIME-TO-FIRST-CAPTION VERDICT: SKIPPED"
call :step red-as-expected-time-to-first-caption 1 "_main\time-to-first-caption-oracle.py" "%OUT%\time-to-first-caption-neg.log" python _main\time-to-first-caption-oracle.py --neg-arm
call :expectred red-as-expected-time-to-first-caption !STEP_RC! "%OUT%\time-to-first-caption-neg.log" "NEG-ARM: PASS"

call :step youtube-land-replay 0 "_main\youtube-land-replay-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-land-replay.log" python _main\youtube-land-replay-oracle.py
call :record youtube-land-replay !STEP_RC!
call :step red-as-expected-youtube-land-replay 1 "_main\youtube-land-replay-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-land-replay-neg.log" python _main\youtube-land-replay-oracle.py --neg-arm
call :expectred red-as-expected-youtube-land-replay !STEP_RC! "%OUT%\youtube-land-replay-neg.log" "NEG-ARM: PASS"

call :step yt-loop-uia 0 "_main\yt-loop-uia-oracle.py;app\webview\sotto_webview.py" "%OUT%\yt-loop-uia.log" python _main\yt-loop-uia-oracle.py
call :record yt-loop-uia !STEP_RC!
call :step red-as-expected-yt-loop-uia 1 "_main\yt-loop-uia-oracle.py;app\webview\sotto_webview.py" "%OUT%\yt-loop-uia-neg.log" python _main\yt-loop-uia-oracle.py --neg-arm
call :expectred red-as-expected-yt-loop-uia !STEP_RC! "%OUT%\yt-loop-uia-neg.log" "NEG-ARM: PASS"

REM O ALVO MORTO (2026-11-03, MEDIDO no browser do dono): o id declarado `m_bJQ4G1Ht8` ficou 164
REM linhas no log com a unica aba de video aberta a mostrar OUTRO video -- `pick_target` filtra as
REM abas por esse id, nao acha, nao produz foto, e sem foto o id tambem nao se cura. O par prova as
REM duas metades (a escolha e o re-declarar do shell) e o `--neg-arm` derruba quatro bracos.
call :step yt-target-stale 0 "_main\yt-target-stale-oracle.py;app\webview\youtube_cdp_source.py;app\webview\sotto_webview.py" "%OUT%\yt-target-stale.log" python _main\yt-target-stale-oracle.py
call :record yt-target-stale !STEP_RC!
call :step red-as-expected-yt-target-stale 1 "_main\yt-target-stale-oracle.py;app\webview\youtube_cdp_source.py;app\webview\sotto_webview.py" "%OUT%\yt-target-stale-neg.log" python _main\yt-target-stale-oracle.py --neg-arm
call :expectred red-as-expected-yt-target-stale !STEP_RC! "%OUT%\yt-target-stale-neg.log" "NEG-ARM PASS"

REM O ECO DO DONO NAO ABRE NADA (ordem de 2026-11-04: "nao faz nenhum script existente ou novo
REM abrir coisa na minha tela tipo pop up"). O `owner-screen-gate` le` 987 ficheiros de produto por
REM `ast` (Python) e com comentarios/strings removidos (JS) e recusa `webbrowser.open`,
REM `os.startfile`, `tkinter`, `MessageBoxW`, `ShellExecute`, `window.open(`/`alert(` e quaisquer
REM `subprocess` que largue `start`/`explorer`/`mshta`/`control`/um URL. A janela do PROPRIO Sotto
REM nao conta: e` o produto. O `--neg-arm` escreve um ficheiro que abre um browser e exige o RED.
call :step owner-screen 0 "_main\owner-screen-gate.py;app\webview\sotto_webview.py;app\panel\panel.js" "%OUT%\owner-screen.log" python _main\owner-screen-gate.py
call :record owner-screen !STEP_RC!
call :step red-as-expected-owner-screen 1 "_main\owner-screen-gate.py" "%OUT%\owner-screen-neg.log" python _main\owner-screen-gate.py --neg-arm
call :expectred red-as-expected-owner-screen !STEP_RC! "%OUT%\owner-screen-neg.log" "NEG-ARM PASS"

REM A ARVORE MORRE COM A SHELL (medido 2026-11-04: `taskkill /T` deixava QUATRO
REM `msedgewebview2.exe` a deter `Local\SottoShell`, e cada largada seguinte abortava em 20 s).
REM O `job-object-oracle` larga um pai que dorme um filho e morre com `os._exit`; o filho TEM de
REM morrer (job kill-on-close). O `--neg-arm` corre o mesmo SEM job e exige o filho VIVO -- sem
REM esse lado, um filho que morresse por outra razao faria o positivo passar sem provar nada.
call :step job-object 0 "_main\job-object-oracle.py" "%OUT%\job-object.log" python _main\job-object-oracle.py
call :record job-object !STEP_RC!
call :step red-as-expected-job-object 1 "_main\job-object-oracle.py" "%OUT%\job-object-neg.log" python _main\job-object-oracle.py --neg-arm
call :expectred red-as-expected-job-object !STEP_RC! "%OUT%\job-object-neg.log" "NEG-ARM PASS"

REM UM CANO MORTO NAO E' UM CRASH (medido no log do dono a 2026-11-04 01:13:40:
REM `BRIDGE_DEATH_CAUSE OSError: [Errno 22] Invalid argument` em `sys.stdout.write`, rc=1,
REM death kind=error -- o pai fechou o cano no meio de uma recarga e o worker levou traceback
REM por escrever onde ninguem lia, a pagar uma recarga de 14-26 s). O oraculo importa o worker
REM REAL, poe um stdout que levanta OSError(22), e exige: nenhuma excecao escapa, `EMIT_PIPE_DEAD`
REM no stderr, e saida 0. O `--neg-arm` repoe a escrita crua numa COPIA ao lado do original e
REM exige as arms 1-3 vermelhas.
call :step emit-pipe-dead 0 "_main\emit-pipe-dead-oracle.py;worker\sotto_worker.py" "%OUT%\emit-pipe-dead.log" python _main\emit-pipe-dead-oracle.py
call :record emit-pipe-dead !STEP_RC!
call :step red-as-expected-emit-pipe-dead 1 "_main\emit-pipe-dead-oracle.py;worker\sotto_worker.py" "%OUT%\emit-pipe-dead-neg.log" python _main\emit-pipe-dead-oracle.py --neg-arm
call :expectred red-as-expected-emit-pipe-dead !STEP_RC! "%OUT%\emit-pipe-dead-neg.log" "NEG-ARM PASS"

REM === FIM DOS SETE =============================================================
REM
REM `_main\sotto-state-page.py` e o P0.2 do roadmap de observabilidade de 2026-10-23: a pagina de
REM estado (docs\state-generated.md) e GERADA das saidas dos oraculos e recusa-se a inventar -- um
REM passo que nao correu e `NOT RUN`, nunca um verde. CORRE SEMPRE (`always`): as seis verificacoes
REM leem a evidencia VIVA (`_cache\battery-steps.json` + `_main\_audit-verify\*.log`) e um resultado
REM em cache descreveria um estado que ja nao existe. Custo medido 2026-10-25: 3,49 s.
if exist _main\sotto-state-page.py (
call :step always state-page-write 0 "_main\sotto-state-page.py;_main\_audit-verify-all.cmd;_main\_stepcache.py;_cache\battery-steps.json" "%OUT%\state-page-write.log" python _main\sotto-state-page.py --write
call :record state-page-write !STEP_RC!
) else ( call :record state-page-write MISSING )
if exist _main\sotto-state-page.py (
  call :step always state-page 0 "_main\sotto-state-page.py;docs\state-generated.md;_main\_audit-verify-all.cmd;_main\_stepcache.py;_cache\battery-steps.json" "%OUT%\state-page.log" python _main\sotto-state-page.py --check
  call :record state-page !STEP_RC!
) else ( call :record state-page MISSING )
if exist _main\sotto-state-page.py (
  call :step always red-as-expected-state-page 1 "_main\sotto-state-page.py;docs\state-generated.md;_main\_audit-verify-all.cmd;_main\_stepcache.py;_cache\battery-steps.json" "%OUT%\state-page-neg.log" python _main\sotto-state-page.py --neg-arm
  call :expectred red-as-expected-state-page !STEP_RC! "%OUT%\state-page-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-state-page MISSING "%OUT%\state-page-neg.log" "NEG-ARM PASS" )

REM `_main\battery-wiring-oracle.py` e o P3.1 do roadmap de observabilidade de 2026-10-23: nenhum
REM oraculo de enforcement novo sem um passo que o corra, e o baseline so pode ENCOLHER. A populacao
REM usa os MESMOS cinco globs do `tooling-intent-oracle.py`; o *wiring* e lido das linhas `call :step`
REM desta propria `.cmd`. Medido 2026-10-25: populacao 170, ligados 48, sem passo 122 (eram 124
REM antes de este par entrar), e o baseline tem tecto 124 pinado no codigo. Nao lanca nada: le bytes.
if exist _main\battery-wiring-oracle.py (
  call :step battery-wiring 0 "_main\battery-wiring-oracle.py;_main\battery-wiring-baseline.json;_main\_audit-verify-all.cmd;_main\tooling-intent-oracle.py" "%OUT%\battery-wiring.log" python _main\battery-wiring-oracle.py
  call :record battery-wiring !STEP_RC!
) else ( call :record battery-wiring MISSING )
if exist _main\battery-wiring-oracle.py (
  call :step red-as-expected-battery-wiring 1 "_main\battery-wiring-oracle.py;_main\battery-wiring-baseline.json;_main\_audit-verify-all.cmd;_main\tooling-intent-oracle.py" "%OUT%\battery-wiring-neg.log" python _main\battery-wiring-oracle.py --neg-arm
  call :expectred red-as-expected-battery-wiring !STEP_RC! "%OUT%\battery-wiring-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-battery-wiring MISSING "%OUT%\battery-wiring-neg.log" "NEG-ARM PASS" )

REM `_main\complaints-reconcile-gate.py` e o P3.2 do roadmap de observabilidade de 2026-10-23: as
REM DUAS listas do dono (o backlog de 2026-10-22 com 10 ABERTO e o documento de fecho com 31/31)
REM davam veredictos opostos sobre as mesmas mensagens e nada as juntava. Uma linha por reclamacao,
REM e a contradicao calculada -- 13 hoje -- tem de trazer `gap` a dizer o que a evidencia do fecho
REM NAO mede. CORRE SEMPRE (`always`): a populacao inclui o corpus em `I:\!manager\...`, que o
REM `_stepcache` nao consegue fingerprintar por viver fora do repo -- um resultado em cache
REM descreveria um corpus que ja mudou. Custo: leitura de texto, sem subprocessos.
if exist _main\complaints-reconcile-gate.py (
  call :step always complaints-reconcile 0 "_main\complaints-reconcile-gate.py;_main\complaints-reconcile.json;_main\closure-evidence-policy.json;.opencode\complaints-closure.md;runs\TC-20261022-sotto-backlog.md;_main\complaints_canon.py" "%OUT%\complaints-reconcile.log" python _main\complaints-reconcile-gate.py
  call :record complaints-reconcile !STEP_RC!
) else ( call :record complaints-reconcile MISSING )
if exist _main\complaints-reconcile-gate.py (
  call :step always red-as-expected-complaints-reconcile 1 "_main\complaints-reconcile-gate.py;_main\complaints-reconcile.json;_main\closure-evidence-policy.json;.opencode\complaints-closure.md;runs\TC-20261022-sotto-backlog.md;_main\complaints_canon.py" "%OUT%\complaints-reconcile-neg.log" python _main\complaints-reconcile-gate.py --neg-arm
  call :expectred red-as-expected-complaints-reconcile !STEP_RC! "%OUT%\complaints-reconcile-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-complaints-reconcile MISSING "%OUT%\complaints-reconcile-neg.log" "NEG-ARM PASS" )
REM `_main\youtube-1to1-oracle.py` e o check 1:1 do dono (2026-10-26, verbatim: *"tem que
REM bater timing, linha/quebra de linha e etc, 1:1"*): palavras, quebras, timing e revelacao
REM palavra-a-palavra contra o PAYLOAD do proprio YouTube, no mesmo instante, com as duas
REM pontas guardadas (payload em `_main\fixtures`, cues servidos em `_cache`). A janela do
REM YouTube vem do `rcRows` do payload e a do Sotto e OUTRA coisa de proposito -- se as duas
REM lessem o mesmo numero, o mutante da janela nao podia ser apanhado.
REM ESTE PASSO ESTEVE VERMELHO ATE 2026-10-26 E PASSOU A VERDE NO MESMO DIA: `word-reveal-1to1`
REM media 69 segmentos com `tOffsetMs` no payload e 0 offsets nos cues servidos, e o prefixo
REM revelado divergia em 388/677 amostras. Agora o cue carrega o relogio do proprio YouTube e o
REM prefixo bate em 677/677. O `red-as-expected` ao lado e o que impede este verde de ser um
REM selo: 8 mutantes, cada um tem de ser recusado pela arm que lhe compete.
if exist _main\youtube-1to1-oracle.py (
call :step always youtube-1to1 0 "_main\youtube-1to1-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;_cache\youtube-captions\WdaHAGRBB6s.jsonl;app\webview\youtube_captions.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\youtube-1to1.log" python _main\youtube-1to1-oracle.py
call :record youtube-1to1 !STEP_RC!
) else ( call :record youtube-1to1 MISSING )
if exist _main\youtube-1to1-oracle.py (
call :step always red-as-expected-youtube-1to1 1 "_main\youtube-1to1-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;_cache\youtube-captions\WdaHAGRBB6s.jsonl;app\webview\youtube_captions.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\youtube-1to1-neg.log" python _main\youtube-1to1-oracle.py --neg-arm
call :expectred red-as-expected-youtube-1to1 !STEP_RC! "%OUT%\youtube-1to1-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-1to1 MISSING "%OUT%\youtube-1to1-neg.log" "NEG-ARM PASS" )

REM ---------------------------------------------------------------------------
REM A SEGUNDA FONTE DA LEGENDA DO YOUTUBE (2026-11-03). Com a aba em segundo
REM plano o Chrome para de expor a legenda na arvore de acessibilidade (medido:
REM 3 minutos com um UNICO YOUTUBE_CAPTION), e a fonte passa a ser o DOM do
REM player pela CDP. As arms EXECUTAM as decisoes reais de
REM `app\webview\youtube_cdp_source.py`: o formato das linhas, o lixo, a
REM IDENTIDADE (7 abas watch nesta maquina: sem o id, `ambiguous`), o relogio do
REM player, o recorte pelo `overflow: hidden` e a ausencia de
REM `Emulation.setFocusEmulationEnabled` -- medido lado a lado, ele leva a
REM leitura de 2-5 ms para 108 ms de mediana e 5 s de p90, o que e' o instrumento
REM a criar a lentidao que depois mede. Custo: texto, sem rede e sem janela.
if exist _main\youtube-cdp-source-oracle.py (
call :step always youtube-cdp-source 0 "_main\youtube-cdp-source-oracle.py;app\webview\youtube_cdp_source.py;app\webview\sotto_webview.py;_main\_yt-live-latency.py" "%OUT%\youtube-cdp-source.log" python _main\youtube-cdp-source-oracle.py
call :record youtube-cdp-source !STEP_RC!
) else ( call :record youtube-cdp-source MISSING )
if exist _main\youtube-cdp-source-oracle.py (
call :step always red-as-expected-youtube-cdp-source 1 "_main\youtube-cdp-source-oracle.py;app\webview\youtube_cdp_source.py;app\webview\sotto_webview.py;_main\_yt-live-latency.py" "%OUT%\youtube-cdp-source-neg.log" python _main\youtube-cdp-source-oracle.py --neg-arm
call :expectred red-as-expected-youtube-cdp-source !STEP_RC! "%OUT%\youtube-cdp-source-neg.log" "NEG-ARM VERDICT: PASS"
) else ( call :expectred red-as-expected-youtube-cdp-source MISSING "%OUT%\youtube-cdp-source-neg.log" "NEG-ARM VERDICT: PASS" )

REM ---------------------------------------------------------------------------
REM ---------------------------------------------------------------------------
REM AS TRES PORTAS QUE ESTAVAM ESCRITAS E FORA DA BATERIA (2026-11-03). O
REM `battery-wiring-oracle` recusou-as com razao (`new-unwired: 3 oraculo(s) sem
REM passo e sem licenca`): um oraculo que nao corre em sitio nenhum e' um ficheiro,
REM nao um portao. Cada um traz o seu `red-as-expected`, com a convencao da casa --
REM o negativo responde rc=1 quando apanha os mutantes, e 0 quando um escapa.
if exist _main\caption-producer-oracle.py (
call :step always caption-producer 0 "_main\caption-producer-oracle.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\caption-producer.log" python _main\caption-producer-oracle.py
call :record caption-producer !STEP_RC!
) else ( call :record caption-producer MISSING )
if exist _main\caption-producer-oracle.py (
call :step always red-as-expected-caption-producer 1 "_main\caption-producer-oracle.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\caption-producer-neg.log" python _main\caption-producer-oracle.py --neg-arm
call :expectred red-as-expected-caption-producer !STEP_RC! "%OUT%\caption-producer-neg.log" "NEG-ARM VERDICT: PASS"
) else ( call :expectred red-as-expected-caption-producer MISSING "%OUT%\caption-producer-neg.log" "NEG-ARM VERDICT: PASS" )
if exist _main\caption-style-oracle.py (
call :step always caption-style 0 "_main\caption-style-oracle.py;app\panel\panel.html;app\webview\sotto_webview.py" "%OUT%\caption-style.log" python _main\caption-style-oracle.py
call :record caption-style !STEP_RC!
) else ( call :record caption-style MISSING )
if exist _main\caption-style-oracle.py (
call :step always red-as-expected-caption-style 1 "_main\caption-style-oracle.py;app\panel\panel.html;app\webview\sotto_webview.py" "%OUT%\caption-style-neg.log" python _main\caption-style-oracle.py --neg-arm
call :expectred red-as-expected-caption-style !STEP_RC! "%OUT%\caption-style-neg.log" "NEG-ARM VERDICT: PASS"
) else ( call :expectred red-as-expected-caption-style MISSING "%OUT%\caption-style-neg.log" "NEG-ARM VERDICT: PASS" )
if exist _main\hotkey-observed-oracle.py (
call :step always hotkey-observed 0 "_main\hotkey-observed-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\hotkey-observed.log" python _main\hotkey-observed-oracle.py
call :record hotkey-observed !STEP_RC!
) else ( call :record hotkey-observed MISSING )
if exist _main\hotkey-observed-oracle.py (
call :step always red-as-expected-hotkey-observed 1 "_main\hotkey-observed-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\hotkey-observed-neg.log" python _main\hotkey-observed-oracle.py --neg-arm
call :expectred red-as-expected-hotkey-observed !STEP_RC! "%OUT%\hotkey-observed-neg.log" "NEG-ARM held-removed"
) else ( call :expectred red-as-expected-hotkey-observed MISSING "%OUT%\hotkey-observed-neg.log" "NEG-ARM held-removed" )

REM A REVELACAO PALAVRA-A-PALAVRA NO CAMINHO VIVO (2026-10-29). O
REM `youtube-1to1-oracle.py` acima compara o PAYLOAD com os cues servidos: e um
REM check ESTATICO, e nao ve o caminho vivo. MEDIDO 2026-10-29: o ramo `painted`
REM de `sotto_webview._youtube` montava a janela com o INICIO DO CUE
REM (`hit.cue.start + 0.001`), e `revealed_lines` corta a linha pelos relogios
REM das palavras -- logo SO a primeira palavra passava e a linha NUNCA crescia
REM no ecra. O `revealed_lines` era chamada (o `reveal-wired` do 1to1 via), e
REM mesmo assim o defeito era invisivel para esse check.
REM ESTE PASSO mede a JANELA DE PRODUCAO (`youtube_reveal.window_by_paint`)
REM contra as linhas que o PROPRIO player pintou, gravadas em
REM `_main\fixtures\yt-WdaHAGRBB6s.break-position-20261026.json`. MEDIDO
REM 2026-10-29: 15/15 linhas iguais.
REM O ORACULO chama o `align_painted` DE PRODUCAO (nao uma reconstrucao): com
REM o `hit` reconstruido a mao (sem `from_index`) a linha que rola para fora
REM nunca aparecia, e o instrumento media uma coisa que a producao nao faz.
REM O `red-as-expected` ao lado atrasa a pintura de uma palavra: tem de dar
REM RED, senao o verde nao mede nada.
if exist _main\youtube-reveal-oracle.py (
call :step always youtube-reveal 0 "_main\youtube-reveal-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.break-position-20261026.json;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_reveal.py;app\webview\youtube_captions.py;app\webview\youtube_window.py;app\webview\sotto_webview.py" "%OUT%\youtube-reveal.log" python _main\youtube-reveal-oracle.py
call :record youtube-reveal !STEP_RC!
) else ( call :record youtube-reveal MISSING )
if exist _main\youtube-reveal-oracle.py (
call :step always red-as-expected-youtube-reveal 1 "_main\youtube-reveal-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.break-position-20261026.json;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_reveal.py;app\webview\youtube_captions.py" "%OUT%\youtube-reveal-neg.log" python _main\youtube-reveal-oracle.py --neg-arm
call :expectred red-as-expected-youtube-reveal !STEP_RC! "%OUT%\youtube-reveal-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-reveal MISSING "%OUT%\youtube-reveal-neg.log" "NEG-ARM PASS" )

REM AS LINHAS DO PLAYER E AS QUEBRAS DE LINHA (2026-10-29). O `youtube-1to1`
REM compara o texto JUNTO; este compara a JANELA DE LINHAS e a POSICAO DA
REM QUEBRA. MEDIDO 2026-10-26: a posicao da quebra divergia em 12/16 amostras
REM -- o `caption_wrap.wrap` divide por espaco e DESTRUI o `\n` do YouTube, e a
REM nossa largura (714,0 px) nao e a do YouTube, logo nunca podem concordar.
REM A CORRECAO (2026-10-29): as linhas do player atravessam o caminho inteiro
REM com a quebra intacta (`rows_text` -> `push_caption_to_window` -> o `\n`
REM que o `caption_overlay._layout` respeita sem re-quebrar). MEDIDO
REM 2026-10-29: 16/16 linhas, 16/16 quebras, `clipped=0`.
if exist _main\youtube-rows-oracle.py (
call :step always youtube-rows 0 "_main\youtube-rows-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_reveal.py;app\webview\youtube_captions.py;app\webview\caption_overlay.py;app\webview\sotto_webview.py" "%OUT%\youtube-rows.log" python _main\youtube-rows-oracle.py
call :record youtube-rows !STEP_RC!
) else ( call :record youtube-rows MISSING )
if exist _main\youtube-rows-oracle.py (
call :step always red-as-expected-youtube-rows 1 "_main\youtube-rows-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;app\webview\youtube_reveal.py;app\webview\youtube_captions.py;app\webview\caption_overlay.py" "%OUT%\youtube-rows-neg.log" python _main\youtube-rows-oracle.py --neg-arm
call :expectred red-as-expected-youtube-rows !STEP_RC! "%OUT%\youtube-rows-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-rows MISSING "%OUT%\youtube-rows-neg.log" "NEG-ARM PASS" )

REM O ORCAMENTO DE TEMPO (2026-10-29) -- o "quase 1:1" do dono. ESTE PASSO NAO
REM DIZ "SINCRONIZADO": uma lei prova uma ORDEM, nunca um milissegundo, e o
REM dono pediu o comportamento, nao um booleano. O `youtube-drift-oracle.py`
REM imprime o `drift_ms` de CADA linha contra a linha do tempo do proprio
REM YouTube (o payload) e da o observado (o clock do player). MEDIDO
REM 2026-10-29: 16 linhas, min +23 ms, max +704 ms, mediana +107,2 ms -- e o
REM max e LIMITADO pela amostragem (a grelha de amostras vai de 637 a 849 ms, e
REM 12 das 19 linhas do payload ficam fora da janela capturada). O valor e
REM publicado como numero, com o sinal, e nunca como veredicto booleano.
REM O `red-as-expected` injeta +250 ms na referencia: tem de dar RED, senao o
REM instrumento nao deteta um atraso que ele diz detectar.
if exist _main\youtube-drift-oracle.py (
call :step always youtube-drift 0 "_main\youtube-drift-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json" "%OUT%\youtube-drift.log" python _main\youtube-drift-oracle.py
call :record youtube-drift !STEP_RC!
) else ( call :record youtube-drift MISSING )
if exist _main\youtube-drift-oracle.py (
call :step always red-as-expected-youtube-drift 1 "_main\youtube-drift-oracle.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json" "%OUT%\youtube-drift-neg.log" python _main\youtube-drift-oracle.py --neg-arm
call :expectred red-as-expected-youtube-drift !STEP_RC! "%OUT%\youtube-drift-neg.log" "NEG-ARM"
) else ( call :expectred red-as-expected-youtube-drift MISSING "%OUT%\youtube-drift-neg.log" "NEG-ARM" )

REM ---------------------------------------------------------------------------
REM AS LEIS DO CAMINHO 1:1 (2026-10-29). O DONO, 2026-10-29, verbatim:
REM *"le a bend/README.md primeiro -- LAWS.bend e PROOF.bend para as decisoes
REM puras, mais um falsificador medido para o orcamento de tempo"*.
REM
REM O QUE ESTE PORTAO E, e o que ele NAO e:
REM   PROVA: as AFIRMACOES de `bend_core\LAWS.bend` sobre o modelo puro do
REM   caminho 1:1 -- a revelacao palavra-a-palavra, a vitalidade de uma linha, o
REM   tecto da janela. O kernel (Lean 4.34 via BendTT) prova cada lei para
REM   TODAS as entradas do dominio, e um def por lei e o que a preenche.
REM   NAO PROVA: o ORCAMENTO DE TEMPO. Uma lei prova uma ORDEM, nunca um
REM   milissegundo -- o `drift_ms` e do `youtube-drift-oracle.py` acima.
REM   NAO PROVA: o que o dono VE no ecra. Isso e dos mirrors
REM   (`youtube-reveal-oracle.py`, `youtube-rows-oracle.py`).
REM
REM O `--verdict` E O UNICO MODO USADO COMO PORTAO: o `--check-only` nao corre
REM prova nenhuma e imprime `ALL PROOFS CHECK` num ficheiro que o kernel
REM recusa (upstream #1897, #1896).
REM
REM AS SEIS SAIDAS TIPADAS (POL-6), porque um portao que responde 0 ou 1
REM confunde "a lei e falsa" com "o portao nao correu":
REM   0 todas as leis verificam e todos os controlos falham pelo motivo certo
REM   2 uma lei NAO verificou         3 um controlo negativo fez o que nao devia
REM   4 INFRAESTRUTURA (nunca "a lei e falsa")
REM   5 o inventario de leis divergiu   6 uma sonda de TAMPER nao se comportou
REM
REM O PASSO E `always` (nunca em cache): o portao le o estado VIVO das provas e
REM dos ficheiros, e um resultado em cache descreveria um estado que ja nao
REM existe. O `red-as-expected` ao lado nao se aplica -- o portao ja inclui os
REM controlos negativos E as sondas de tamper, e um `--neg-arm` seria uma
REM segunda copia do mesmo mecanismo.
REM ---------------------------------------------------------------------------
if exist _main\bend-laws-gate.py (
call :step always bend-laws 0 "_main\bend-laws-gate.py;bend_core\LAWS.bend;bend_core\PROOF.bend;bend_core\NEGATIVE_revealed_flag.bend;bend_core\NEGATIVE_of_bool_agrees.bend;bend_core\NEGATIVE_live_flag.bend;bend_core\NEGATIVE_live_flag_before.bend;bend_core\NEGATIVE_window_rows_min.bend;bend_core\NEGATIVE_window_rows_capacity.bend;bend_core\NEGATIVE_window_rows_live.bend;bend_core\NEGATIVE_count_due_only.bend;bend_core\NEGATIVE_count_due_monotone.bend;bend_core\NEGATIVE_count_due_empty.bend;bend_core\NEGATIVE_count_due_one_word.bend" "%OUT%\bend-laws.log" python _main\bend-laws-gate.py
call :record bend-laws !STEP_RC!
) else ( call :record bend-laws MISSING )

REM O MODELO EM PYTHON (2026-10-29). `bend_core\model.py` e a MESMA amostra do
REM modelo, em Python, para um host sem o toolchain do Bend. NAO E O PORTAO: o
REM portao e o `bend-laws` acima, que prova para TODAS as entradas. Este passo
REM e uma LEITURA -- e o que permite a um leitor conferir o numero que a lei
REM restringe sem instalar nada. O `red-as-expected` troca o modelo por um
REM quebrado e tem de dar RED: um verificador que so diz "ok" nao e verificador.
if exist bend_core\model.py (
call :step always bend-laws-model 0 "bend_core\model.py" "%OUT%\bend-laws-model.log" python bend_core\model.py
call :record bend-laws-model !STEP_RC!
) else ( call :record bend-laws-model MISSING )
if exist bend_core\model.py (
call :step always red-as-expected-bend-laws-model 1 "bend_core\model.py" "%OUT%\bend-laws-model-neg.log" python bend_core\model.py --neg-arm
call :expectred red-as-expected-bend-laws-model !STEP_RC! "%OUT%\bend-laws-model-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-bend-laws-model MISSING "%OUT%\bend-laws-model-neg.log" "NEG-ARM PASS" )

REM O CAMINHO DO Alt+C (o UNICO controlo do dono) tem de sobreviver a um
REM atributo em falta. MEDIDO 2026-10-20: `show_panel`, `show_strip` e
REM `show_side` liam `self.external_captions_active`,
REM `self.external_captions_available` e `self._vram_parked` DIRECTAMENTE,
REM ao lado de `getattr(self, '_paused', False)`. Com um atributo em falta,
REM o caminho do Alt+C rebenta com AttributeError -- e o dono fica sem
REM painel. A correcao leu os tres com `getattr(..., False)`: semantica
REM IDENTICA, porque o `__init__` semeia os tres a False (:5710-5711, :5718).
REM O PORTAO e PURO (o AST do shell + um FAKE; sem browser, sem app, sem
REM audio, sem processo) e tem 7 arms + 3 mutantes no `--neg-arm`.
REM MEDIDO: 1,97 s (normal) + 0,38 s (`--neg-arm`).
REM ---------------------------------------------------------------------------
if exist _main\panel-hidden-at-startup-oracle.py (
  call :step panel-hidden-at-startup-oracle 0 "_main\panel-hidden-at-startup-oracle.py;app\webview\sotto_webview.py;app\webview\stage.html;app\panel\panel.html" "%OUT%\panel-hidden-at-startup.log" python _main\panel-hidden-at-startup-oracle.py
  call :record panel-hidden-at-startup-oracle !STEP_RC!
) else ( call :record panel-hidden-at-startup-oracle MISSING )
REM O BRACO NEGATIVO: os mutantes tem de virar um braco VERMELHO. rc=1 POR
REM DESENHO (o `--neg-arm` REPROVA de proposito).
if exist _main\panel-hidden-at-startup-oracle.py (
  call :step red-as-expected-panel-hidden-at-startup 1 "_main\panel-hidden-at-startup-oracle.py;app\webview\sotto_webview.py;app\webview\stage.html;app\panel\panel.html" "%OUT%\panel-hidden-at-startup-neg.log" python _main\panel-hidden-at-startup-oracle.py --neg-arm
  call :expectred red-as-expected-panel-hidden-at-startup !STEP_RC! "%OUT%\panel-hidden-at-startup-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-panel-hidden-at-startup MISSING "%OUT%\panel-hidden-at-startup-neg.log" "NEG-ARM PASS" )

echo === the wiring and the embedded JS (the two things the other gates cannot see) ===
if exist _main\_audit-worker-start-wiring.py (
  call :step worker-start-wiring 0 "_main\_audit-worker-start-wiring.py;app\webview\sotto_webview.py" "%OUT%\wiring-worker-start.log" python _main\_audit-worker-start-wiring.py
  call :record worker-start-wiring !STEP_RC!
) else ( call :record worker-start-wiring MISSING )
if exist _main\_audit-embedded-js-check.py (
  call :step embedded-js-check 0 "_main\_audit-embedded-js-check.py;app\webview\sotto_webview.py;app\webview\hot_reload.py;app\webview\panel_state.py;app\webview\external_subs.py;app\webview\youtube_captions.py;app\webview\caption_overlay.py;app\webview\caption_wrap.py" "%OUT%\embedded-js.log" python _main\_audit-embedded-js-check.py
  call :record embedded-js-check !STEP_RC!
) else ( call :record embedded-js-check MISSING )
if exist _main\_lane1-worker-default-arms.py (
  call :step lane1-worker-default-arms 0 "_main\_lane1-worker-default-arms.py;app\webview\sotto_webview.py" "%OUT%\lane1-arms.log" python _main\_lane1-worker-default-arms.py
  call :record lane1-worker-default-arms !STEP_RC!
) else ( call :record lane1-worker-default-arms MISSING )

echo === the YouTube captions that REPLACE the live one: the chrome must not reach the box ===
REM Owner, 2026-10-19, verbatim: "eu quero que tu trabalhe nas legendas do youtube
REM substituem a ao vivo". TWO instruments, two claims.
REM
REM `_external-subs-stability-oracle.py` drives the REAL `app/webview/external_subs.py`
REM `caption_lines` against synthetic UI Automation polls, and checks that the chrome the
REM owner's own log produced -- the view counter, the age of the video, a chat handle, a
REM separator glyph, and the counter SPLIT IN TWO WORDS (the case an element-shaped rule
REM cannot see) -- never reaches the caption box. Its `nochrome` arm removes the rule from
REM a COPY and MUST let the chrome through: the oracle has to be able to say no.
REM
REM `external-caption-chrome-census.py` reads the REAL external lines out of the app's
REM OWN log and says how many of them were chrome; its negative arm removes the rule and
REM shows the survivors going back up. THE COUNT IS NOT A CONSTANT: the log keeps growing
REM (the app is open), so the number in that REM was true when it was written and moves
REM from then on. The FIXTURE step below is the one with a number that does NOT move.
REM
REM BOTH were outside this battery until 2026-10-19, which is how the `head` arm of the
REM first one rotted in silence: it kept running and it stopped proving anything.
if exist _main\_external-subs-stability-oracle.py (
  call :step external-subs-stability 0 "_main\_external-subs-stability-oracle.py;app\webview\external_subs.py" "%OUT%\external-subs-stability.log" python _main\_external-subs-stability-oracle.py
  call :record external-subs-stability !STEP_RC!
) else ( call :record external-subs-stability MISSING )
if exist _main\external-caption-chrome-census.py (
  call :step external-caption-chrome-census 0 "_main\external-caption-chrome-census.py;app\webview\external_subs.py;_main\webview-run.log" "%OUT%\external-caption-chrome-census.log" python _main\external-caption-chrome-census.py --neg-arm
  call :record external-caption-chrome-census !STEP_RC!
) else ( call :record external-caption-chrome-census MISSING )
REM The FIXTURE: the SAME rules over the SAME rows, built from the lists the
REM instrument itself carries. The numbers are a property of the RULES, not of
REM whatever the log happens to hold today -- so anybody can reproduce them:
REM     python _main/external-caption-chrome-census.py --fixture --neg-arm
REM MEDIDO 2026-10-20: 19 linhas, 11 de chrome apanhadas, 8 legendas que sobrevivem,
REM 1 RESIDUE reportada; o braco negativo leva o chrome de 11 a 0 e as legendas de 8 a 19.
if exist _main\external-caption-chrome-census.py (
  call :step external-caption-chrome-census-fixture 0 "_main\external-caption-chrome-census.py;app\webview\external_subs.py" "%OUT%\external-caption-chrome-census-fixture.log" python _main\external-caption-chrome-census.py --fixture --neg-arm
  call :record external-caption-chrome-census-fixture !STEP_RC!
) else ( call :record external-caption-chrome-census-fixture MISSING )
REM Owner, 2026-10-20, verbatim: "eu ja mandei tu resolver o negocio de que por
REM algum motivo texto de outras coisas que nao sao o transcript do video do youtube
REM fica vazando pro nosso app". TWO HOLES, and this is the instrument that says
REM no to both of them.
REM
REM `external-subs-geometry-window-oracle.py` drives the REAL
REM `app/webview/external_subs.py` against SYNTHETIC UI Automation trees -- no real
REM window, no browser, no app, no audio, and none of the owner's state touched.
REM It pins:
REM   * the GEOMETRY: with the page rect (0,121,1905,4107) AND the real video
REM     element (16,189,1354,942) both present, the band is 655.86..942 (inside
REM     the video) and NOT 2592.32 (inside the comments), and the measured page
REM     chrome does not reach the caption box; with no video element the old
REM     fallback still reads the window;
REM   * the WINDOW: a "youtube" title in a NON-BROWSER (the owner's own File
REM     Explorer, "kicktwitchyoutube_instagram - Explorador de Arquivos") is not
REM     a player, the YouTube URL is proof on its own, the measured real window
REM     is still external:youtube and still yields its video id, and
REM     find_player_window returns the browser's window, not the Explorer's.
REM
REM Its NEGATIVE ARM is EXECUTED: six broken copies of the module, and each one
REM has to turn an arm RED. A gate that cannot fail is a promise.
if exist _main\external-subs-geometry-window-oracle.py (
  call :step external-subs-geometry-window 0 "_main\external-subs-geometry-window-oracle.py;app\webview\external_subs.py" "%OUT%\external-subs-geometry-window.log" python _main\external-subs-geometry-window-oracle.py
  call :record external-subs-geometry-window !STEP_RC!
) else ( call :record external-subs-geometry-window MISSING )


echo === the YOUTUBE REAL TRACK, the MUTE, and the rule that the ASR is the base ===

REM Three instruments for the owner's order of 2026-10-19: *"faz a legenda do
REM youtube mostrar na tela em tempo real"*, *"youtube ta mostrando texto burro
REM da pagina inves da porra da legenda/transcriptino de um video"* and *"e nao
REM e pra tu parar de transcrever audio do chrome. e audio do youtube CASO
REM tenha legenda do youtube. se for um video sem legenda, vaio transcrever ao
REM vivo igual."*
REM
REM `youtube-captions-oracle.py` judges the READER: the video's OWN caption
REM track (yt-dlp), the four states (has-track / no-track / no-cue-in-window /
REM time-unknown), and the player's clock read from the real seek bar.
REM
REM `youtube-track-wiring-oracle.py` judges the WIRING: that the PAGE's own text
REM never reaches the caption box for a YouTube window, that only a REAL cue
REM ever stops the live transcription, and that a video with no caption track
REM gives the microphone back. It builds FIVE broken copies of the shell and
REM requires each one to turn an arm RED.
REM
REM `mute-audio-oracle.py` is the MUTE (owner, 2026-10-19, verbatim: *"se tu
REM vai usar audio padrao pra testar qualquer coisa, muta"*). It was OUTSIDE
REM this battery until now -- which is exactly how a gate rots in silence: it
REM kept passing and it stopped being asked. Its arms restore the original
REM volume in a `finally`, so a failed arm cannot leave the owner's speakers
REM muted.
if exist _main\youtube-captions-oracle.py (
  call :step youtube-captions 0 "_main\youtube-captions-oracle.py;app\webview\youtube_captions.py" "%OUT%\youtube-captions.log" python _main\youtube-captions-oracle.py
  call :record youtube-captions !STEP_RC!
) else ( call :record youtube-captions MISSING )
REM THE NATIVE CAPTION'S LINE BREAKING (owner, 2026-10-21): the caption the
REM owner SEES is drawn by the native renderer (caption_overlay.py +
REM caption_wrap.py) -- `caption.html` is loaded by no window at all -- so the
REM YouTube-style breaking and the "só palavras inteiras" rule are judged
REM THERE. Pure: GDI+ into a MEMORY bitmap, no window, no app, no audio.
if exist _main\caption-native-wrap-oracle.py (
  call :step caption-native-wrap 0 "_main\caption-native-wrap-oracle.py;app\webview\caption_wrap.py;app\webview\caption_overlay.py" "%OUT%\caption-native-wrap.log" python _main\caption-native-wrap-oracle.py
  call :record caption-native-wrap !STEP_RC!
) else ( call :record caption-native-wrap MISSING )

REM `yt-player-track-oracle.py` judges the 1:1 RULE (owner, 2026-10-20,
REM verbatim: *"eu quero a legenda 1:1 do video do youtube. eu mesmo vou
REM comparar a nossa legenda em tempo real com a do youtube."*). The track
REM the PLAYER paints is the track the app serves: the player's own caption
REM window carries the `lang` it is showing, and the yt-dlp key whose
REM request carries NO `tlang` is the one the player asks for. When the
REM player says nothing, the fallback decides AND the log says so.
if exist _main\yt-player-track-oracle.py (
  call :step yt-player-track 0 "_main\yt-player-track-oracle.py;app\webview\youtube_captions.py" "%OUT%\yt-player-track.log" python _main\yt-player-track-oracle.py
  call :record yt-player-track !STEP_RC!
) else ( call :record yt-player-track MISSING )
REM `yt-mirror-align-oracle.py` judges the CAMINHO ESPELHO (owner, 2026-10-20,
REM verbatim: *"eu quero a legenda 1:1 do video do youtube. eu mesmo vou
REM comparar a nossa legenda em tempo real com a do youtube. ... e eu ja mandou
REM tu resolver o negocio de que por algum motivo texto de outras coisas que
REM nao sao o transcript do video do youtube fica vazando pro nosso app."*).
REM
REM THE TWO THINGS THE UIA COULD NOT ANSWER, both measured on the owner's own
REM Chrome on 2026-10-20:
REM   * the player's CLOCK IS FROZEN -- the seek bar's RangeValue and the
REM     player's own clock text read +0.00 s in 8.35 s of wall clock, while
REM     the painted line advanced +8.96 s in the track (the clock said t=2.0
REM     with the video at t=530);
REM   * the caption window exposes NO LANGUAGE -- 0 of 448 elements have the
REM     UIA 30007 property -- so the app served the track of the language
REM     PREFERENCE (`pt-orig`) while the player painted `en-orig`.
REM
REM So the app reads the line the player is PAINTING and finds the track that
REM HOLDS it. This gate pins the alignment, the discrimination between the two
REM languages of the same video, and the three rules the rollup forces: the cut
REM at the front (the rollup drops its oldest line), the half-written word
REM ('...on t' for '...on the'), and the minimum of exact words.
if exist _main\yt-mirror-align-oracle.py (
  call :step yt-mirror-align 0 "_main\yt-mirror-align-oracle.py;app\webview\youtube_captions.py" "%OUT%\yt-mirror-align.log" python _main\yt-mirror-align-oracle.py
  call :record yt-mirror-align !STEP_RC!
) else ( call :record yt-mirror-align MISSING )
REM O BRACO NEGATIVO: os mutantes tem de virar um braço VERMELHO. rc=1 POR
REM DESENHO (o `--neg-arm` REPROVA de proposito), como em `mute-audio-oracle.py`.
if exist _main\yt-mirror-align-oracle.py (
  call :step red-as-expected-yt-mirror-align 1 "_main\yt-mirror-align-oracle.py;app\webview\youtube_captions.py" "%OUT%\yt-mirror-align-neg.log" python _main\yt-mirror-align-oracle.py --neg-arm
  call :expectred red-as-expected-yt-mirror-align !STEP_RC! "%OUT%\yt-mirror-align-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-yt-mirror-align MISSING "%OUT%\yt-mirror-align-neg.log" "NEG-ARM PASS" )
REM ---------------------------------------------------------------------------
REM O DELTA DA LANE DE DESIGN: a lane re-renderizava TODOS os shots sempre
REM (medido: 13 min para 100 jobs, para produzir as MESMAS imagens).
REM `shots-delta.py` decide, POR JOB, se os bytes de entrada e o output
REM sao os MESMOS de antes: so o que mudou e re-renderizado. O portao e
REM PURO (ficheiros num temporario; sem browser, sem rede, sem app, sem audio)
REM e tem 19 arms + 11 mutantes.
REM ---------------------------------------------------------------------------
if exist _main\shots-delta-oracle.py (
  call :step shots-delta-oracle 0 "_main\shots-delta-oracle.py;_main\_design-lane\shots-delta.py;_main\_design-lane\intake-shots.py" "%OUT%\shots-delta-oracle.log" python _main\shots-delta-oracle.py
  call :record shots-delta-oracle !STEP_RC!
) else ( call :record shots-delta-oracle MISSING )
REM O BRACO NEGATIVO: os mutantes tem de virar um braco VERMELHO. rc=1 POR
REM DESENHO (o `--neg-arm` REPROVA de proposito).
if exist _main\shots-delta-oracle.py (
  call :step red-as-expected-shots-delta-oracle 1 "_main\shots-delta-oracle.py;_main\_design-lane\shots-delta.py;_main\_design-lane\intake-shots.py" "%OUT%\shots-delta-oracle-neg.log" python _main\shots-delta-oracle.py --neg-arm
  call :expectred red-as-expected-shots-delta-oracle !STEP_RC! "%OUT%\shots-delta-oracle-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-shots-delta-oracle MISSING "%OUT%\shots-delta-oracle-neg.log" "NEG-ARM PASS" )
REM ---------------------------------------------------------------------------
REM O EOL DO REPO PASSOU A SER UMA REGRA. Sem `.gitattributes`, um
REM checkout nesta box entregava CRLF a TODOS os ficheiros de texto
REM (medido: 9/9 ficheiros representativos), o que destruia a convencao
REM do AGENTS.md (`_main/*.py` = LF) e mudava o sha de tudo o que esta
REM byte-pinhado. O verificador materializa um checkout REAL e compara
REM os terminadores um a um com a arvore de trabalho de hoje.
REM Custo medido: 3,35 s e 45,7 MB (pasta fixa em TMPDIR, nao cresce).
REM ---------------------------------------------------------------------------
if exist _main\_gitattributes-verify.py (
  call :step gitattributes-verify 0 "_main\_gitattributes-verify.py;_main\_make-gitattributes.py;.gitattributes" "%OUT%\gitattributes-verify.log" python _main\_gitattributes-verify.py
  call :record gitattributes-verify !STEP_RC!
) else ( call :record gitattributes-verify MISSING )
REM ---------------------------------------------------------------------------
REM O PORTAO DOS PINOS DO AGENTS.md. O proprio AGENTS.md diz (linha ~767):
REM "It is now in the battery ... a gate that is not in the battery is a
REM gate that rots in silence, and this one rotted in silence for seven
REM days". MEDIDO 2026-10-20: era FALSO -- 0 ocorrencias do nome aqui.
REM E o portao estava VERMELHO: o AGENTS.md carregava o tamanho antigo
REM deste ficheiro. O portao mede o `run.cmd --help` (o pre-flight, que
REM nao abre janela) e os bytes deste .cmd, e exige que o AGENTS.md os
REM carregue. Um pin que parte porque o codigo cresceu e um pin A FAZER
REM O SEU TRABALHO; um pin que parte porque ninguem correu o portao e
REM podrao.
REM ---------------------------------------------------------------------------
if exist _main\agents-md-pins-oracle.py (
  call :step agents-md-pins 0 "_main\agents-md-pins-oracle.py;app\webview\run.cmd;_main\_audit-verify-all.cmd;AGENTS.md" "%OUT%\agents-md-pins.log" python _main\agents-md-pins-oracle.py
  call :record agents-md-pins !STEP_RC!
) else ( call :record agents-md-pins MISSING )
if exist _main\lang-id-oracle.py (
  call :step lang-id-oracle 0 "_main\lang-id-oracle.py;worker\lang_prompt.py;worker\sotto_worker.py;worker\config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;docs\model-specs\original\fp16\languages.json;worker\assets\sample1.flac" "%OUT%\lang-id-oracle.log" python _main\lang-id-oracle.py
  call :record lang-id-oracle !STEP_RC!
) else ( call :record lang-id-oracle MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\lang-id-oracle.py (
  call :step red-as-expected-lang-id-oracle 1 "_main\lang-id-oracle.py;worker\lang_prompt.py;worker\sotto_worker.py;worker\config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;docs\model-specs\original\fp16\languages.json;worker\assets\sample1.flac" "%OUT%\lang-id-oracle-neg.log" python _main\lang-id-oracle.py --neg-arm
  call :expectred red-as-expected-lang-id-oracle !STEP_RC! "%OUT%\lang-id-oracle-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-lang-id-oracle MISSING "%OUT%\lang-id-oracle-neg.log" "NEG-ARM PASS" )
if exist _main\model-spec-oracle.py (
  call :step model-spec-oracle 0 "_main\model-spec-oracle.py;worker\config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;docs\model-specs\original\fp16\languages.json" "%OUT%\model-spec-oracle.log" python _main\model-spec-oracle.py
  call :record model-spec-oracle !STEP_RC!
) else ( call :record model-spec-oracle MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\model-spec-oracle.py (
  call :step red-as-expected-model-spec-oracle 1 "_main\model-spec-oracle.py;worker\config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;docs\model-specs\original\fp16\languages.json" "%OUT%\model-spec-oracle-neg.log" python _main\model-spec-oracle.py --neg-arm
  call :expectred red-as-expected-model-spec-oracle !STEP_RC! "%OUT%\model-spec-oracle-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-model-spec-oracle MISSING "%OUT%\model-spec-oracle-neg.log" "NEG-ARM PASS" )
if exist _main\scope-leak-oracle.js (
  call :step scope-leak 0 "_main\scope-leak-oracle.js;app\panel\themes\theme-1.css;app\panel\themes\theme-2.css;app\panel\themes\theme-3.css;app\panel\themes\theme-4.css;app\panel\themes\theme-5.css;app\panel\themes\panel-designs.css;app\panel\themes\zipc-panels.css;app\panel\themes\fonts.css;app\panel\themes\cinematic.css" "%OUT%\scope-leak.log" node _main\scope-leak-oracle.js
  call :record scope-leak !STEP_RC!
) else ( call :record scope-leak MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\scope-leak-oracle.js (
  call :step red-as-expected-scope-leak 1 "_main\scope-leak-oracle.js;app\panel\themes\theme-1.css;app\panel\themes\theme-2.css;app\panel\themes\theme-3.css;app\panel\themes\theme-4.css;app\panel\themes\theme-5.css;app\panel\themes\panel-designs.css;app\panel\themes\zipc-panels.css;app\panel\themes\fonts.css;app\panel\themes\cinematic.css" "%OUT%\scope-leak-neg.log" node _main\scope-leak-oracle.js --neg-arm
  call :expectred red-as-expected-scope-leak !STEP_RC! "%OUT%\scope-leak-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-scope-leak MISSING "%OUT%\scope-leak-neg.log" "NEG-ARM PASS" )
if exist _main\panel-flash-contradiction-oracle.py (
  call :step panel-flash-contradiction 0 "_main\panel-flash-contradiction-oracle.py;AGENTS.md" "%OUT%\panel-flash-contradiction.log" python _main\panel-flash-contradiction-oracle.py
  call :record panel-flash-contradiction !STEP_RC!
) else ( call :record panel-flash-contradiction MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\panel-flash-contradiction-oracle.py (
  call :step red-as-expected-panel-flash-contradiction 1 "_main\panel-flash-contradiction-oracle.py;AGENTS.md" "%OUT%\panel-flash-contradiction-neg.log" python _main\panel-flash-contradiction-oracle.py --neg-arm
  call :expectred red-as-expected-panel-flash-contradiction !STEP_RC! "%OUT%\panel-flash-contradiction-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-panel-flash-contradiction MISSING "%OUT%\panel-flash-contradiction-neg.log" "NEG-ARM PASS" )
if exist _main\per-app-source-plumbing-oracle.py (
  call :step per-app-source-plumbing 0 "_main\per-app-source-plumbing-oracle.py;worker\sotto_worker.py" "%OUT%\per-app-source-plumbing.log" python _main\per-app-source-plumbing-oracle.py
  call :record per-app-source-plumbing !STEP_RC!
) else ( call :record per-app-source-plumbing MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\per-app-source-plumbing-oracle.py (
  call :step red-as-expected-per-app-source-plumbing 1 "_main\per-app-source-plumbing-oracle.py;worker\sotto_worker.py" "%OUT%\per-app-source-plumbing-neg.log" python _main\per-app-source-plumbing-oracle.py --neg-arm
  call :expectred red-as-expected-per-app-source-plumbing !STEP_RC! "%OUT%\per-app-source-plumbing-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-per-app-source-plumbing MISSING "%OUT%\per-app-source-plumbing-neg.log" "NEG-ARM PASS" )
if exist _main\redux-live-contract-oracle.js (
  call :step redux-live-contract 0 "_main\redux-live-contract-oracle.js;app\panel\caption-formulation.js;app\panel\panel.js;_main\redux-live-smoke.jsonl" "%OUT%\redux-live-contract.log" node _main\redux-live-contract-oracle.js
  call :record redux-live-contract !STEP_RC!
) else ( call :record redux-live-contract MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\redux-live-contract-oracle.js (
  call :step red-as-expected-redux-live-contract 1 "_main\redux-live-contract-oracle.js;app\panel\caption-formulation.js;app\panel\panel.js;_main\redux-live-smoke.jsonl" "%OUT%\redux-live-contract-neg.log" node _main\redux-live-contract-oracle.js --neg-arm
  call :expectred red-as-expected-redux-live-contract !STEP_RC! "%OUT%\redux-live-contract-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-redux-live-contract MISSING "%OUT%\redux-live-contract-neg.log" "NEG-ARM PASS" )
if exist _main\word-split-oracle.py (
  call :step word-split-oracle 0 "_main\word-split-oracle.py;worker\sotto_worker.py;_main\word-split-trace.json;_main\_wordsplit-before.jsonl;_main\_wordsplit-after.jsonl;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\vocab.txt" "%OUT%\word-split-oracle.log" python _main\word-split-oracle.py
  call :record word-split-oracle !STEP_RC!
) else ( call :record word-split-oracle MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\word-split-oracle.py (
  call :step red-as-expected-word-split-oracle 1 "_main\word-split-oracle.py;worker\sotto_worker.py;_main\word-split-trace.json;_main\_wordsplit-before.jsonl;_main\_wordsplit-after.jsonl;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\vocab.txt" "%OUT%\word-split-oracle-neg.log" python _main\word-split-oracle.py --neg-arm
  call :expectred red-as-expected-word-split-oracle !STEP_RC! "%OUT%\word-split-oracle-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-word-split-oracle MISSING "%OUT%\word-split-oracle-neg.log" "NEG-ARM PASS" )
if exist _main\vad-option-probe.py (
  call :step vad-option-probe 0 "_main\vad-option-probe.py;worker\config.json;worker\sotto_worker.py;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json" "%OUT%\vad-option-probe.log" python _main\vad-option-probe.py
  call :record vad-option-probe !STEP_RC!
) else ( call :record vad-option-probe MISSING )
REM O BRACO NEGATIVO: rc=1 POR DESENHO, e o log tem de dizer NEG-ARM PASS.
if exist _main\vad-option-probe.py (
  call :step red-as-expected-vad-option-probe 1 "_main\vad-option-probe.py;worker\config.json;worker\sotto_worker.py;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json" "%OUT%\vad-option-probe-neg.log" python _main\vad-option-probe.py --neg-arm
  call :expectred red-as-expected-vad-option-probe !STEP_RC! "%OUT%\vad-option-probe-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-vad-option-probe MISSING "%OUT%\vad-option-probe-neg.log" "NEG-ARM PASS" )
if exist _main\youtube-track-wiring-oracle.py (
  call :step youtube-track-wiring 0 "_main\youtube-track-wiring-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-track-wiring.log" python _main\youtube-track-wiring-oracle.py
  call :record youtube-track-wiring !STEP_RC!
) else ( call :record youtube-track-wiring MISSING )
REM The FREEZE. Owner, 2026-10-20, verbatim: *"abrir ou fechar o sotto,
REM principalemnte fechar, trava pra caralho meu pc. arruma."* -- and the
REM owner's own log says why, with a number: 68 s from the spawn to the model
REM (`BRIDGE_LOAD_MS ms=67969` with `worker_load_s=8.75`), of which ~59 s was
REM the CAPTURE LADDER waiting on a Bluetooth headset whose open BLOCKS (it
REM does not come back and it raises nothing), and at QUIT the caption
REM reader's release path brought the worker BACK, 0.65 s before the shell
REM exited -- an orphan, because `os._exit` does not kill a child.
REM The gate judges the two fixes: the open has a DEADLINE, and the shell does
REM not bring the worker back while it is dying.
if exist _main\tap-open-timeout-oracle.py (
  call :step tap-open-timeout 0 "_main\tap-open-timeout-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\tap-open-timeout.log" python _main\tap-open-timeout-oracle.py
  call :record tap-open-timeout !STEP_RC!
) else ( call :record tap-open-timeout MISSING )
REM The SECOND freeze defect (owner, 2026-10-20, verbatim: *"abrir ou fechar o
REM sotto, principalemnte fechar, trava pra caralho meu pc. arruma."*). The OPEN
REM was fixed the same day (68 s -> 3,2 s); THIS is the other one, and the
REM owner's own log says why, with a number: 93 `UI_THREAD_STALL begin-invoke
REM not run in 10 s` and 68 `exec_js TIMEOUT after 10.0s`, ALL of them inside ONE
REM 50 s window (01:55:30 -> 01:56:20) while a design lane was rendering 45
REM themes with headless Edge. The load was the TRIGGER; the code was the
REM FREEZE: the panel's 1/s `getStats()` pull went through a SYNCHRONOUS
REM `exec_js` with a 10 s budget, and the thread it held was the PUMP thread --
REM the one that carries the captions.
REM
REM `ui-stall-oracle.py` drives the REAL `app/webview/sotto_webview.py` in
REM process, with a FAKE WinForms form whose UI thread NEVER DRAINS. It proves
REM that (1) the stats reply does not hold its caller, (2) N replies leave at
REM most ONE posted callable, (3) every id is still answered -- the panel's
REM Promise resolves -- (4) a stall is DISTINGUISHABLE from a legitimate `None`
REM and carries its reason and what was asked, (5) `emit_async`'s latch still
REM holds, and (6) the panel-state DUMP (a diagnostic, every 2 s) neither
REM blocks nor grows the WinForms queue. Its NEGATIVE ARM IS EXECUTED: FOUR
REM broken copies of the shell, each of which has to turn RED on its OWN claim.
REM No app, no window, no worker, no audio.
if exist _main\ui-stall-oracle.py (
  call :step ui-stall-oracle 0 "_main\ui-stall-oracle.py;app\webview\sotto_webview.py" "%OUT%\ui-stall-oracle.log" python _main\ui-stall-oracle.py
  call :record ui-stall-oracle !STEP_RC!
) else ( call :record ui-stall-oracle MISSING )
if exist _main\mute-audio-oracle.py (
  call :step always heavy mute-audio 0 "_main\mute-audio-oracle.py" "%OUT%\mute-audio.log" python _main\mute-audio-oracle.py
  call :skipped mute-audio !STEP_RC! "%OUT%\mute-audio.log" "VERDICT: PASS" "MUTE-AUDIO VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped mute-audio MISSING "%OUT%\mute-audio.log" "VERDICT: PASS" "MUTE-AUDIO VERDICT: SKIPPED" "VERDICT: SKIPPED" )
REM `device-silence-oracle.py` e' o CONTRATO do dispositivo que nao entrega nada,
REM medido com o worker REAL em tres bracos (sem shell, sem janela): (1) um
REM endpoint que ABRE e nao entrega um unico bloco de callback -- MEDIDO
REM 2026-11-01 neste caixa, `Mixagem estereo (Realtek HD Audio Stereo input)`,
REM 0 blocos em 4 s ao lado de 39 no cabo -- que ate' aqui saia com o veredicto
REM `no-callback-blocks` e **rc=0**, o word que todo o chamador le' como sucesso;
REM (2) um endpoint que entrega blocos TODOS abaixo do piso (`silent-device`,
REM caminho provado e intocado); (3) fala renderizada no cabo e capturada, que
REM tem de sair rc=0 com legendas. Cada braco exige o SEU rc e o SEU veredicto, e
REM o MESMO ficheiro importa a shell de producao e exige que um `done` com estes
REM veredictos pinte `no-audio` -- worker, oraculo e shell concordam por MEDICAO,
REM nao por copia. O `--neg-arm` repoe a linha antiga numa COPIA do worker e
REM exige rc=0 nela (rc=1 por desenho).
if exist _main\device-silence-oracle.py (
  call :step always heavy device-silence 0 "_main\device-silence-oracle.py;worker\sotto_worker.py;worker\wasapi_loopback.py;app\webview\sotto_webview.py;worker\assets\sample1.flac" "%OUT%\device-silence.log" python _main\device-silence-oracle.py
  call :skipped device-silence !STEP_RC! "%OUT%\device-silence.log" "DEVICE-SILENCE VERDICT: PASS" "DEVICE-SILENCE VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped device-silence MISSING "%OUT%\device-silence.log" "VERDICT: PASS" "DEVICE-SILENCE VERDICT: SKIPPED" "VERDICT: SKIPPED" )
if exist _main\device-silence-oracle.py (
  call :step always heavy red-as-expected-device-silence 1 "_main\device-silence-oracle.py;worker\sotto_worker.py;app\webview\sotto_webview.py" "%OUT%\device-silence-neg.log" python _main\device-silence-oracle.py --neg-arm
  call :skipped red-as-expected-device-silence !STEP_RC! "%OUT%\device-silence-neg.log" "NEG-ARM PASS" "DEVICE-SILENCE VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped red-as-expected-device-silence MISSING "%OUT%\device-silence-neg.log" "NEG-ARM PASS" "DEVICE-SILENCE VERDICT: SKIPPED" "VERDICT: SKIPPED" )

echo === a secretaria do dono: sem janela, sem audio mutado, com a GPU declarada ===
REM As tres portas que nasceram das ordens dele de 2026-11-02: (1) nada em foreground
REM (`console-window-audit`: censo AST de 1139 ficheiros que resolve o
REM creationflags NO ESCOPO, mais `console-window-watch --neg-arm` para o criterio
REM que julga o ecra; o `console-window-gate` de regex foi aposentado por ser o
REM mesmo criterio lido pior e com baseline 0),
REM (2) o audio dele nao se toca (`owner-audio-gate`: escrever exige
REM SOTTO_OWNER_AUDIO_OK=1, senao rc=9 com `recusa: audio do dono`), (3) o motor AO
REM VIVO diz em que provider corre (`worker-providers`: um CUDA disponivel e nao
REM escolhido e' o fallback silencioso medido hoje, 10,75x contra 2,27x).
if exist _main\console-window-audit.py (
  call :step always console-window-audit 0 "_main\console-window-audit.py;_main\console-window-watch.py;_main\console-weakflag-baseline.json;app\webview\no_console.py" "%OUT%\console-window-audit.log" python _main\console-window-audit.py
  call :record console-window-audit !STEP_RC!
) else ( call :record console-window-audit MISSING )
if exist _main\console-window-audit.py (
  call :step always red-as-expected-console-window-audit 1 "_main\console-window-audit.py" "%OUT%\console-window-audit-neg.log" python _main\console-window-audit.py --neg-arm
  call :expectred red-as-expected-console-window-audit !STEP_RC! "%OUT%\console-window-audit-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-console-window-audit MISSING "%OUT%\console-window-audit-neg.log" "NEG-ARM PASS" )
if exist _main\console-window-watch.py (
  call :step always red-as-expected-console-window-watch 1 "_main\console-window-watch.py" "%OUT%\console-window-watch-neg.log" python _main\console-window-watch.py --neg-arm
  call :expectred red-as-expected-console-window-watch !STEP_RC! "%OUT%\console-window-watch-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-console-window-watch MISSING "%OUT%\console-window-watch-neg.log" "NEG-ARM PASS" )

REM (`capture-exclude`: a janela da legenda desaparece de QUEM GRAVA o ecra,
REM ordem do dono de 2026-11-04 -- as features do `perssua-re` que faltavam.
REM O oraculo cria um HWND REAL e LE DE VOLTA a afinidade: pedir 0x11 e ficar
REM com 0x00 e' falha. Nove arms (escada para build antiga, interruptor por
REM env, o `EX_STYLE` do overlay com `WS_EX_TRANSPARENT`/`WS_EX_NOACTIVATE`, e a
REM chamada viva do caminho do overlay) e quatro mutantes, cada um com o seu
REM braco. Nenhum dos dois abre janela visivel: e' um HWND escondido em
REM (-4000,-4000) e fechado no `finally`.)
if exist _main\capture-exclude-oracle.py (
  call :step always capture-exclude 0 "_main\capture-exclude-oracle.py;app\webview\capture_exclusion.py;app\webview\caption_overlay.py" "%OUT%\capture-exclude.log" python _main\capture-exclude-oracle.py
  call :record capture-exclude !STEP_RC!
) else ( call :record capture-exclude MISSING )
if exist _main\capture-exclude-oracle.py (
  call :step always red-as-expected-capture-exclude 1 "_main\capture-exclude-oracle.py;app\webview\capture_exclusion.py;app\webview\caption_overlay.py" "%OUT%\capture-exclude-neg.log" python _main\capture-exclude-oracle.py --neg-arm
  call :expectred red-as-expected-capture-exclude !STEP_RC! "%OUT%\capture-exclude-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-capture-exclude MISSING "%OUT%\capture-exclude-neg.log" "NEG-ARM PASS" )

REM (`history-merge`: a linha do historico e' UMA linha, nao um fluxo de eventos.
REM Dono, 2026-11-04, verbatim: *"o historico da legenda e completamente IMBECIL
REM na logica. fica duplicando frase"* -- medido no painel dele, a mesma frase
REM gravada seis vezes enquanto crescia. O oraculo executa `history_merge`, o
REM leitor da cauda e o caminho inteiro `history_append` sobre um HISTORY_ROOT
REM temporario; o `--neg-arm` muta uma COPIA do shell em dois sentidos (sempre
REM acrescentar, sempre saltar) e exige o RED do arm correspondente. Nenhum dos
REM dois abre a app: mexe em ficheiros de um diretorio temporario.)
if exist _main\history-merge-oracle.py (
  call :step always history-merge 0 "_main\history-merge-oracle.py;app\webview\sotto_webview.py;app\panel\panel.js" "%OUT%\history-merge.log" python _main\history-merge-oracle.py
  call :record history-merge !STEP_RC!
) else ( call :record history-merge MISSING )
if exist _main\history-merge-oracle.py (
  call :step always red-as-expected-history-merge 1 "_main\history-merge-oracle.py;app\webview\sotto_webview.py" "%OUT%\history-merge-neg.log" python _main\history-merge-oracle.py --neg-arm
  call :expectred red-as-expected-history-merge !STEP_RC! "%OUT%\history-merge-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-history-merge MISSING "%OUT%\history-merge-neg.log" "NEG-ARM PASS" )

REM (`reveal-clock`: a revelacao da legenda e' ancorada no AUDIO, nao na chegada
REM do ASR. Dono, verbatim: *"a legenda do youtube ta fora de sync. atrasada.
REM depois faz um catch up super rapido e atrasa de novo"* -- medido no log dele,
REM 09:58:32 `audio_ms=1567` seguido de `audio_ms=64` e outra vez `audio_ms=2644`.
REM O oraculo executa o `set_text` REAL de `caption_overlay.py` e conta as
REM palavras reveladas com e sem o recuo; os dois mutantes (ignorar o recuo,
REM recuar sempre 3 s) caem em arms DIFERENTES.)
if exist _main\reveal-clock-oracle.py (
  call :step always reveal-clock 0 "_main\reveal-clock-oracle.py;app\webview\caption_overlay.py;app\webview\sotto_webview.py" "%OUT%\reveal-clock.log" python _main\reveal-clock-oracle.py
  call :record reveal-clock !STEP_RC!
) else ( call :record reveal-clock MISSING )
if exist _main\reveal-clock-oracle.py (
  call :step always red-as-expected-reveal-clock 1 "_main\reveal-clock-oracle.py;app\webview\caption_overlay.py" "%OUT%\reveal-clock-neg.log" python _main\reveal-clock-oracle.py --neg-arm
  call :expectred red-as-expected-reveal-clock !STEP_RC! "%OUT%\reveal-clock-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-reveal-clock MISSING "%OUT%\reveal-clock-neg.log" "NEG-ARM PASS" )

REM (`tap-first-block`: o candidato MORTO cai aos 2 s e nao aos 44. Medido no
REM arranque do dono, 2026-11-04: `capture-started` as 09:57:41 e a rotacao so'
REM as 09:58:25, com `blocks=0` o tempo todo -- 65 s ate' a primeira legenda. A
REM ordem dele e' 3 s. O oraculo executa `first_block_decided` do worker real; o
REM `--neg-arm` muta uma COPIA (piso de 60 s, rotacionar sempre) e exige o RED de
REM arms DIFERENTES. Nenhum dos dois abre dispositivo de audio.)
if exist _main\tap-first-block-oracle.py (
  call :step always tap-first-block 0 "_main\tap-first-block-oracle.py;worker\sotto_worker.py" "%OUT%\tap-first-block.log" python _main\tap-first-block-oracle.py
  call :record tap-first-block !STEP_RC!
) else ( call :record tap-first-block MISSING )
if exist _main\tap-first-block-oracle.py (
  call :step always red-as-expected-tap-first-block 1 "_main\tap-first-block-oracle.py;worker\sotto_worker.py" "%OUT%\tap-first-block-neg.log" python _main\tap-first-block-oracle.py --neg-arm
  call :expectred red-as-expected-tap-first-block !STEP_RC! "%OUT%\tap-first-block-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-tap-first-block MISSING "%OUT%\tap-first-block-neg.log" "NEG-ARM PASS" )

if exist _main\owner-audio-gate.py (
  call :step always owner-audio-gate 0 "_main\owner-audio-gate.py;_main\mute-audio.py" "%OUT%\owner-audio-gate.log" python _main\owner-audio-gate.py
  call :record owner-audio-gate !STEP_RC!
) else ( call :record owner-audio-gate MISSING )
if exist _main\owner-audio-gate.py (
  call :step always red-as-expected-owner-audio-gate 1 "_main\owner-audio-gate.py;_main\mute-audio.py" "%OUT%\owner-audio-gate-neg.log" python _main\owner-audio-gate.py --neg-arm
  call :expectred red-as-expected-owner-audio-gate !STEP_RC! "%OUT%\owner-audio-gate-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-owner-audio-gate MISSING "%OUT%\owner-audio-gate-neg.log" "NEG-ARM: PASS" )
if exist _main\worker-providers-oracle.py (
  call :step always worker-providers 0 "_main\worker-providers-oracle.py;app\webview\sotto_webview.py" "%OUT%\worker-providers.log" python _main\worker-providers-oracle.py
  call :skipped worker-providers !STEP_RC! "%OUT%\worker-providers.log" "WORKER-PROVIDERS VERDICT: PASS" "WORKER-PROVIDERS VERDICT: SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped worker-providers MISSING "%OUT%\worker-providers.log" "WORKER-PROVIDERS VERDICT: PASS" "WORKER-PROVIDERS VERDICT: SKIPPED" "VERDICT: SKIPPED" )
if exist _main\worker-providers-oracle.py (
  call :step always red-as-expected-worker-providers 1 "_main\worker-providers-oracle.py" "%OUT%\worker-providers-neg.log" python _main\worker-providers-oracle.py --neg-arm
  call :expectred red-as-expected-worker-providers !STEP_RC! "%OUT%\worker-providers-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-worker-providers MISSING "%OUT%\worker-providers-neg.log" "NEG-ARM: PASS" )

echo === the adversary lane's probes (corrected: the filters it wrote were RED-forever) ===
if exist _main\_review-f1f3.py (
  call :step review-f1f3 0 "_main\_review-f1f3.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\review-f1f3.log" python _main\_review-f1f3.py
  call :record review-f1f3 !STEP_RC!
) else ( call :record review-f1f3 MISSING )
if exist _main\_review-tapstop.py (
  call :step review-tapstop 0 "_main\_review-tapstop.py;worker\wasapi_loopback.py" "%OUT%\review-tapstop.log" python _main\_review-tapstop.py
  call :record review-tapstop !STEP_RC!
) else ( call :record review-tapstop MISSING )

echo === the strip surface, the wave, and the hot reload that must never wait forever ===
REM Five instruments from the strip-surface lane. The ORACLE builds FOUR broken
REM copies of today's shell (the JS member removed, the dispatch routing removed,
REM the CSS height blinded, the per-sample log restored) and requires each to go
REM RED on its own claim -- so it is a `:control`, and it prints its control
REM verdict. The LOG probe does the same with ONE copy (the per-sample push) and
REM prints its own. The other three are plain gates: each exits 0 only after its
REM arms held, and each is launched with `--no-worker`/`--no-hotkey` so no model
REM is loaded and no audio device is opened.
if exist _main\_strip-surface-oracle.py (
  call :step strip-surface-oracle 0 "_main\_strip-surface-oracle.py;app\webview\sotto_webview.py;app\panel\panel.js;worker\sotto_worker.py" "%OUT%\strip-surface-oracle.log" python _main\_strip-surface-oracle.py
  call :control strip-surface-oracle !STEP_RC! "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS"
) else ( call :control strip-surface-oracle MISSING "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS" )
if exist _main\_strip-stats-log-probe.py (
  call :step always heavy strip-stats-log-budget 0 "_main\_strip-stats-log-probe.py;_main\_strip_stats_load.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-stats-log.log" python _main\_strip-stats-log-probe.py
  call :skipped strip-stats-log-budget !STEP_RC! "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS" "STRIP-LOG CONTROL SKIPPED" "VERDICT: SKIPPED"
) else ( call :skipped strip-stats-log-budget MISSING "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS" "STRIP-LOG CONTROL SKIPPED" "VERDICT: SKIPPED" )
if exist _main\_strip-reload-probe.py (
  call :step strip-hot-reload 0 "_main\_strip-reload-probe.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-reload.log" python _main\_strip-reload-probe.py
  call :record strip-hot-reload !STEP_RC!
) else ( call :record strip-hot-reload MISSING )
if exist _main\_strip-surface-probe.py (
  call :step heavy strip-surface-runtime 0 "_main\_strip-surface-probe.py;app\webview\sotto_webview.py;app\panel\panel.css" "%OUT%\strip-surface.log" python _main\_strip-surface-probe.py
  call :record strip-surface-runtime !STEP_RC!
) else ( call :record strip-surface-runtime MISSING )
REM O BRACO NEGATIVO DO strip-surface (2026-11-01). O instrumento julgava 26
REM assercoes sem NENHUM controlo: uma leitura verde era aceita por ser verde. O
REM `--neg-arm` le o relatorio que o passo de cima acabou de escrever, muta a
REM LEITURA em tres sitios e exige os tres RED pelo mesmo `judge()` que publica o
REM veredicto -- matar o `checks` ja calculado provaria so a aritmetica do `any()`.
REM `heavy` e nao `always`: o comando nomeia o proprio largador da app, e o portao
REM `battery-class-oracle` recusa qualquer passo nao-`heavy` cujo comando o nomeie
REM (medido: a primeira versao nasceu `always` e o portao deu RED com razao). O
REM `--neg-arm` nao larga nada -- le o relatorio --, mas a classe e' lida do
REM COMANDO, e afrouxar o portao para este caso seria o gate a servir o passo.
if exist _main\_strip-surface-probe.py (
  call :step heavy red-as-expected-strip-surface 1 "_main\_strip-surface-probe.py" "%OUT%\strip-surface-neg.log" python _main\_strip-surface-probe.py --neg-arm
  call :expectred red-as-expected-strip-surface !STEP_RC! "%OUT%\strip-surface-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-strip-surface MISSING "%OUT%\strip-surface-neg.log" "NEG-ARM PASS" )
if exist _main\_strip-restore-probe.py (
  call :step heavy strip-geometry-restore 0 "_main\_strip-restore-probe.py;app\webview\sotto_webview.py" "%OUT%\strip-restore.log" python _main\_strip-restore-probe.py
  call :record strip-geometry-restore !STEP_RC!
) else ( call :record strip-geometry-restore MISSING )
if exist _main\_strip-stats-probe.py (
  call :step always heavy strip-stats-wave 0 "_main\_strip-stats-probe.py;_main\_strip_stats_load.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-stats.log" python _main\_strip-stats-probe.py
  call :skipped strip-stats-wave !STEP_RC! "%OUT%\strip-stats.log" "STRIP-STATS VERDICT: GREEN" "STRIP-STATS VERDICT: SKIPPED"
) else ( call :skipped strip-stats-wave MISSING "%OUT%\strip-stats.log" "STRIP-STATS VERDICT: GREEN" "STRIP-STATS VERDICT: SKIPPED" )
REM The oracle of the two steps above: it proves the LOAD HONESTY of the shared
REM decision (a page that does not come up in time is a SKIP with the numbers,
REM a low ratio with both arms live is still a RED) and it runs FOUR broken copies
REM of that decision which must all go RED. It launches NO shell and touches no
REM audio device, so it is a plain gate and the cache may serve it -- its deps
REM carry every file it reads, including the two gates it checks the wiring of.
if exist _main\_strip-stats-load-oracle.py (
  call :step strip-stats-load-oracle 0 "_main\_strip-stats-load-oracle.py;_main\_strip_stats_load.py;_main\_strip-stats-log-probe.py;_main\_strip-stats-probe.py" "%OUT%\strip-stats-load-oracle.log" python _main\_strip-stats-load-oracle.py
  call :record strip-stats-load-oracle !STEP_RC!
) else ( call :record strip-stats-load-oracle MISSING )

echo === Alt+C, the only control: registration table, delivery+fallback+mutex, autostart ===
if exist _main\_audit-hotkey-probe.py (
  call :step always hotkey-registration 0 "_main\_audit-hotkey-probe.py" "%OUT%\hotkey-registration.log" python _main\_audit-hotkey-probe.py
  call :record hotkey-registration !STEP_RC!
) else ( call :record hotkey-registration MISSING )
if exist _main\_audit-hotkey-delivery.py (
  call :step always hotkey-delivery 0 "_main\_audit-hotkey-delivery.py;app\webview\sotto_webview.py" "%OUT%\hotkey-delivery.log" python _main\_audit-hotkey-delivery.py
  call :skipped hotkey-delivery !STEP_RC! "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim"
) else ( call :skipped hotkey-delivery MISSING "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim" )
REM THE THREE HOTKEY GATES (owner, 2026-10-21). They judge the GESTURE: the
REM 1/2/3 contract, the gesture WINDOW and the caption's UNDO -- the fix for
REM "alt c nao ta funcionando direito pra abrir o painel" (a human double press
REM measures 300-500 ms and the window was 250). Until 2026-10-21 they were NOT
REM in this battery, which is exactly how a gate rots in silence (AGENTS.md
REM rule 6). They are PURE: no app, no window, no audio, no browser.
REM THE OPEN/CLOSE STALL GATE (owner, 2026-10-21, the twentieth time: "eu, de
REM novo, pela vigesima vez, vou mandar tu resolver os travamentos que
REM acontecem quando fechamos o sotto ou abrimos o sotto"). It judges FILES:
REM five structural facts, by AST -- never by substring, because a substring
REM fact can be satisfied by a COMMENT and this gate's own first version was
REM exactly that mistake (its mutants came back INERT). It launches NOTHING.
REM The receipt is _main\receipt-20261021-open-close-stall.md.
if exist _main\open-close-stall-oracle.py (
  call :step open-close-stall 0 "_main\open-close-stall-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\open-close-stall.log" python _main\open-close-stall-oracle.py
  call :record open-close-stall !STEP_RC!
) else ( call :record open-close-stall MISSING )
REM O BRACO NEGATIVO: cinco mutantes, cada um parte UMA vez. rc=1 POR DESENHO
REM (o `--neg-arm` REPROVA de proposito).
if exist _main\open-close-stall-oracle.py (
  call :step red-as-expected-open-close-stall 1 "_main\open-close-stall-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\open-close-stall-neg.log" python _main\open-close-stall-oracle.py --neg-arm
  call :expectred red-as-expected-open-close-stall !STEP_RC! "%OUT%\open-close-stall-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-open-close-stall MISSING "%OUT%\open-close-stall-neg.log" "NEG-ARM PASS" )
REM The autostart check READS the registry (a read needs no elevation) and fails
REM if the Run value points somewhere other than THIS checkout -- which is what a moved tree looks like from the login side. The step runs _main\autostart-status-check.py (2026-10-12) because the shell OWN exit code IS the status (0=on+matching, 1=off, 2=unreadable, 3=elsewhere): recording that rc as a plain gate painted a healthy OFF machine RED. The wrapper reads the registry itself, cross-checks the shell own answer, exits 0 for the two VALID states and 3 for another checkout. The REM line below keeps its original wording.
REM moved tree looks like from the login side.
call :step always autostart-status 0 "_main\autostart-status-check.py;app\webview\sotto_webview.py" "%OUT%\autostart-status.log" python _main\autostart-status-check.py
call :record autostart-status !STEP_RC!

echo === CONTROLS: every one of these succeeds ONLY by going RED on a broken copy ===
REM ---------------------------------------------------------------------------
REM These are the arms that had ROTTED because nothing ever ran them. A control
REM that is never executed silently stops being a control: `verdict-gate.py
REM --control-unguard-captions-zero` and `history-producer-gate.js
REM --control-stamp-nvidia` both sat exiting 2 (a setup error, i.e. no control at
REM all) with every gate around them green. They are steps now, and the summary
REM marks them as controls.
REM
REM Each line requires BOTH: the instrument's rc=0 -- which each of these returns
REM ONLY after it has built its broken copy and seen the gate go RED on it -- AND
REM the control verdict text in the log, quoted with python (ASCII substrings, so
REM a console-codepage mojibake cannot hide a missing verdict). rc=0 without the
REM text is a failure here, and so is a MISSING instrument.
REM ---------------------------------------------------------------------------
if exist _main\verdict-gate.py (
  call :step control-verdict-gate-unguard 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\control-verdict-gate-unguard.log" python _main\verdict-gate.py --control-unguard-captions-zero
  call :control control-verdict-gate-unguard !STEP_RC! "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS"
) else ( call :control control-verdict-gate-unguard MISSING "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS" )
if exist _main\history-producer-gate.js (
  call :step control-history-producer-stamp-nvidia 0 "_main\history-producer-gate.js;app\panel\caption-formulation.js;worker\redux_batch.py;worker\sotto_worker.py" "%OUT%\control-history-producer-stamp-nvidia.log" node _main\history-producer-gate.js --control-stamp-nvidia
  call :control control-history-producer-stamp-nvidia !STEP_RC! "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS"
) else ( call :control control-history-producer-stamp-nvidia MISSING "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS" )
REM `redux-flag-gate.py --neg-arm` already runs the shipped pair GREEN and then
REM builds one mutant COPY per claim, requiring each to go RED on its own claim
REM ONLY; rc=0 is that conjunction. This is the superset of the plain gate, which
REM is why the plain form is not a separate step.
if exist _main\redux-flag-gate.py (
  call :step control-redux-flag-neg-arm 0 "_main\redux-flag-gate.py;worker\sotto_worker.py;app\webview\sotto_webview.py" "%OUT%\control-redux-flag-neg-arm.log" python _main\redux-flag-gate.py --neg-arm
  call :control control-redux-flag-neg-arm !STEP_RC! "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN"
) else ( call :control control-redux-flag-neg-arm MISSING "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN" )
REM `--unit --neg-arm` is the no-shell half: the classifier's arms, the `done`
REM mapping and the recovery arm, plus two reverted COPIES of today's shell that
REM must go RED. rc=0 requires every one of those; the JSON keys `neg_arm` /
REM `neg_arm_e` prove the control halves actually ran rather than being skipped.
if exist _main\panel-exit3-oracle.py (
  call :step heavy control-panel-exit3-neg-arm 0 "_main\panel-exit3-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\control-panel-exit3-neg-arm.log" python _main\panel-exit3-oracle.py --unit --neg-arm
  call :control control-panel-exit3-neg-arm !STEP_RC! "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e"
) else ( call :control control-panel-exit3-neg-arm MISSING "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e" )
REM `wasapi-com-init-oracle.py` with NO flag is already both colours in one
REM command: the live module must PASS and the recorded pre-fix copy must be RED.
REM It opens no audio device by construction (stubbed `_ole32`, arms 5-6 only
REM CoInitialize/CoUninitialize). Its own `--neg-arm` is the pre-fix copy ALONE --
REM a debug subset of this run -- so the plain form is what is wired.
if exist _main\wasapi-com-init-oracle.py (
  call :step control-wasapi-com-init 0 "_main\wasapi-com-init-oracle.py;worker\wasapi_loopback.py" "%OUT%\control-wasapi-com-init.log" python _main\wasapi-com-init-oracle.py
  call :control control-wasapi-com-init !STEP_RC! "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS"
) else ( call :control control-wasapi-com-init MISSING "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS" )
REM `_panel2-repeat-probe.js --revert` is the row-identity rule's negative control: it builds a COPY
REM of `app/panel/panel.js` with the identity lookup disabled, and all four arms must then FAIL.
REM TWO verdict strings are required, not one, because this probe's failure mode was not a wrong
REM verdict but an UNREACHABLE one: rc=1 with a `TypeError` and no `RESULT:` line at all, and the
REM mutant left on disk, in BOTH colours (measured 2026-10-08 against the pre-fix revision). rc=0 now
REM means the arms ran, the control went RED, and the mutant was removed.
if exist _main\_panel2-repeat-probe.js (
  call :step control-panel2-repeat-revert 0 "_main\_panel2-repeat-probe.js;app\panel\panel.html;app\panel\panel.js" "%OUT%\control-panel2-repeat-revert.log" node _main\_panel2-repeat-probe.js --revert
  call :control control-panel2-repeat-revert !STEP_RC! "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true"
) else ( call :control control-panel2-repeat-revert MISSING "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true" )
REM `history-gallery-oracle.js --neg-arm` injects the bare-date stamp
REM (`new Date(entry.date)`) into a COPY of the module's parse and requires the LOCAL-time
REM arm to go RED while the stamp-independent arms stay green. The box is GMT-0300
REM (offsetMinutes=180, printed by the run), so the trap is OBSERVABLE here; on a UTC box
REM the same injection moves nothing and the oracle says so instead of claiming a control
REM it did not have -- that vacuity is the failure this row exists to catch.
if exist _main\history-gallery-oracle.js (
  call :step control-history-gallery-neg-arm 0 "_main\history-gallery-oracle.js;app\panel\history-gallery.js" "%OUT%\control-history-gallery-neg-arm.log" node _main\history-gallery-oracle.js --neg-arm
  call :control control-history-gallery-neg-arm !STEP_RC! "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true"
) else ( call :control control-history-gallery-neg-arm MISSING "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true" )
REM `historico-vs-redux-probe.js --gate-off` has NO control mode of its own: the
REM flag loads the store with the one guard line DELETED, so the probe is RED BY
REM DESIGN and exits 1 (its own "FAIL" code) with the violation named. That is why
REM this one is :expectred and not :control.
if exist _main\historico-vs-redux-probe.js (
  call :step red-as-expected-historico-gate-off 1 "_main\historico-vs-redux-probe.js;app\panel\caption-formulation.js;app\panel\history-store.js" "%OUT%\control-historico-gate-off.log" node _main\historico-vs-redux-probe.js --gate-off
  call :expectred red-as-expected-historico-gate-off !STEP_RC! "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript"
) else ( call :expectred red-as-expected-historico-gate-off MISSING "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript" )

REM ---------------------------------------------------------------------------
REM THE HISTORY SEARCH (owner, 2026-10-18/19, prompt #29, verbatim: *"a busca tem
REM de ser extremamente inteligente"*). Three gates that PROVE the three layers
REM -- literal / phonetic soundex / fuzzy Levenshtein, bounded -- and NONE of them
REM was in this battery: a gate that is not in the battery rots in silence, which
REM is exactly how the first `head` arm died.
REM
REM   search-oracle.py             the LIVE shell's search predicate, EXTRACTED by
REM                                 `ast` (never re-implemented, never imported) and
REM                                 judged arm by arm: literal wins, accents fold,
REM                                 the sound layer, the bounded fuzzy layer, the
REM                                 all-words guard, the per-layer caps -- plus the
REM                                 real history store.
REM   search-twin-parity.py        the live Python search and its JavaScript twin
REM                                 must AGREE on every (line, query) pair.
REM   panel-search-keyboard-oracle.py
REM                                 the audit row F9 ("o campo de busca do painel nao
REM                                 pode receber teclado") and the invariant over the
REM                                 real run log.
REM
REM EACH OF THE THREE ALSO HAS AN EXECUTED NEGATIVE ARM: `--neg-arm` runs ONLY
REM the mutants / the control, and exits 1 BY DESIGN (the negative arm has to
REM fail). Each one therefore gets an EXPECT-RED step here: rc=1 PLUS the log
REM carrying `NEG-ARM PASS`. A mutant that does not apply -- a missing or ambiguous
REM anchor -- or one the gate cannot SEE, makes that step RED. That is the whole
REM point: a gate that only knows how to agree is not a gate.
REM
REM HONEST NOTE ABOUT THE CORPUS (and it is NOT a secret): `search-oracle.py` and
REM `search-twin-parity.py` judge the REAL history of this machine (`history\`),
REM which the owner transcribes into WHILE this battery runs. It is DADO VIVO,
REM not source, so it is NOT one of the deps below -- deps are FILES, and a
REM directory that grows is not a file, so a fingerprint over it would lie about
REM what was judged. Each oracle PRINTS the corpus it judged (lines, bytes,
REM sha256), so whoever reads the log -- cached or not -- sees WHICH corpus
REM produced that verdict, and the beacon says "(cached)" when the step was
REM reused instead of re-judged.
REM ---------------------------------------------------------------------------
if exist _main\search-oracle.py (
  call :step search-oracle 0 "_main\search-oracle.py;app\webview\sotto_webview.py" "%OUT%\search-oracle.log" python _main\search-oracle.py
  call :record search-oracle !STEP_RC!
) else ( call :record search-oracle MISSING )
if exist _main\search-oracle.py (
  call :step red-as-expected-search-oracle 1 "_main\search-oracle.py;app\webview\sotto_webview.py" "%OUT%\search-oracle-neg.log" python _main\search-oracle.py --neg-arm
  call :expectred red-as-expected-search-oracle !STEP_RC! "%OUT%\search-oracle-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-search-oracle MISSING "%OUT%\search-oracle-neg.log" "NEG-ARM PASS" )
if exist _main\panel-search-keyboard-oracle.py (
  call :step panel-search-keyboard 0 "_main\panel-search-keyboard-oracle.py;app\webview\sotto_webview.py;app\panel\panel.js;app\panel\panel.html" "%OUT%\panel-search-keyboard.log" python _main\panel-search-keyboard-oracle.py
  call :record panel-search-keyboard !STEP_RC!
) else ( call :record panel-search-keyboard MISSING )
if exist _main\panel-search-keyboard-oracle.py (
  call :step red-as-expected-panel-search-keyboard 1 "_main\panel-search-keyboard-oracle.py;app\webview\sotto_webview.py;app\panel\panel.js;app\panel\panel.html" "%OUT%\panel-search-keyboard-neg.log" python _main\panel-search-keyboard-oracle.py --neg-arm
  call :expectred red-as-expected-panel-search-keyboard !STEP_RC! "%OUT%\panel-search-keyboard-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-panel-search-keyboard MISSING "%OUT%\panel-search-keyboard-neg.log" "NEG-ARM PASS" )

echo === the heavy one LAST: loads the int8 model, opens NO device ===
if exist _main\_audit-fresh-processor-probe.py (
  call :step fresh-processor-probe 0 "_main\_audit-fresh-processor-probe.py;worker\config.json;worker\sotto_worker.py;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\.gitattributes;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\audio_processor_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\decoder.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\decoder.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\encoder.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\encoder.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\joint.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\joint.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\model_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\README.md;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\silero_vad.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\tokenizer_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\tokenizer.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\vocab.txt" "%OUT%\fresh-processor.log" python _main\_audit-fresh-processor-probe.py
  call :record fresh-processor-probe !STEP_RC!
) else ( call :record fresh-processor-probe MISSING )

echo === the cache that makes this battery incremental ===
REM The oracle of the cache itself: the arms (HIT/MISS by CONTENT) and the
REM EXECUTED negative arm -- four broken copies of the engine, each of which
REM has to go RED on its own claim. It runs in its own temp dir and never
REM touches this battery or the real state.
if exist _main\_stepcache-oracle.py (
  call :step stepcache-oracle 0 "_main\_stepcache-oracle.py;_main\_stepcache.py" "%OUT%\stepcache-oracle.log" python _main\_stepcache-oracle.py
  call :record stepcache-oracle !STEP_RC!
) else ( call :record stepcache-oracle MISSING )

echo === the skip guard: NO step may print a skip verdict unless its kind declares it ===
REM Every step above wrote its log. An instrument that silently skips an arm and still
REM exits 0 is a skip wearing a pass, and the difference is visible only in its log --
REM so this single sweep refuses the whole run if ANY step's log carries a skip verdict
REM (`VERDICT: SKIPPED`) while that step is not declared skip-capable. The declared
REM logs are named by `:skipped` itself and handed to the instrument in `--exclude`.
REM
REM IT USED TO READ ITS OWN TRANSCRIPT -- measured 2026-10-08, do not narrow this
REM back. The sweep was an inline python that globbed `%OUT%\*.log` and excluded only
REM `_run-*`. The battery's own console, kept in `%OUT%` as `_battery-run-<ts>.log`,
REM carries the literal `VERDICT: SKIPPED` -- because `:skipped` ECHOES the skip text
REM in its beacon line -- so the guard failed the whole run for a DECLARED skip,
REM naming `_battery-run-20261007-130942.log` and `_battery-run-20261007-131528.log`.
REM A guard that fails on its own output is not measuring the steps. THE RULE NOW: a
REM STEP LOG is a `*.log` in `%OUT%` whose basename does NOT start with `_`, because
REM every artifact the battery itself writes is `_`-prefixed (`_battery-run-*`,
REM `_run-*`, `_skip-guard.log`, `_battery-summary.txt`) and a run console is a
REM transcript of the whole run, not the log of a step.
REM The instrument ALSO runs a five-arm control on EVERY invocation, so it cannot be
REM green by reading nothing. Both colours, one command each:
REM   python _main\_skip-verdict-guard.py --dir _main\_audit-verify --exclude ",hotkey-delivery.log,"   -> rc 0, 64 logs read
REM   python _main\_skip-verdict-guard.py --dir _main\_skip-guard-redcheck --exclude ","                   -> rc 1, names bogus-step.log only
if exist _main\_skip-verdict-guard.py (
  call :step always skip-verdict-guard 0 "_main\_skip-verdict-guard.py" "%OUT%\_skip-guard.log" python _main\_skip-verdict-guard.py --dir "%OUT%" --exclude "!SKIPLOGS!"
  call :record skip-verdict-guard !STEP_RC!
) else ( call :record skip-verdict-guard MISSING )


REM ======================================================================
REM PASSOS RECONSTRUIDOS 2026-10-30 a partir de _cache/battery-steps.json
REM (o ficheiro foi truncado a 0 B por um write que falhou; ver
REM  _main/_battery-restore-steps.py -- o comando de cada passo foi PROVADO
REM  pelo rc do registo, um a um)
REM ======================================================================
if exist _main\altc-first-caption-oracle.py (
REM CLASSE HEAVY (2026-10-30): este passo mede um GESTO DO DONO -- sem uma sessao
REM viva, do build que esta' no disco, com uma pressao de Alt+C, nao ha o que medir e o
REM oraculo responde NO-MEASURE (rc=2). Nao e' o passo que falhou: e' uma medicao que
REM nenhum passo pode produzir por si.
call :step heavy altc-first-caption 0 "_main\altc-first-caption-oracle.py;_main\webview-run.log" "%OUT%\altc-first-caption.log" python _main\altc-first-caption-oracle.py
call :record altc-first-caption !STEP_RC!
) else ( call :record altc-first-caption MISSING )

if exist _main\altc-gesture-oracle.py (
call :step always altc-gesture 0 "_main\altc-gesture-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\altc-gesture.log" python _main\altc-gesture-oracle.py
call :record altc-gesture !STEP_RC!
) else ( call :record altc-gesture MISSING )

if exist _main\headphone-cut-probe.py (
call :step always headphone-cut 0 "_main\headphone-cut-probe.py;_main\webview-run.log" "%OUT%\headphone-cut.log" python _main\headphone-cut-probe.py
call :record headphone-cut !STEP_RC!
) else ( call :record headphone-cut MISSING )

if exist _main\incomplete-word-oracle.py (
call :step always incomplete-word 0 "_main\incomplete-word-oracle.py;worker\sotto_worker.py;worker\stable_words.py;app\panel\stable-words.js;app\panel\caption-formulation.js;app\panel\panel.js" "%OUT%\incomplete-word.log" python _main\incomplete-word-oracle.py
call :record incomplete-word !STEP_RC!
) else ( call :record incomplete-word MISSING )

if exist _main\ladder-signal-oracle.py (
call :step always ladder-signal 0 "_main\ladder-signal-oracle.py;worker\sotto_worker.py;app\webview\sotto_webview.py;app\webview\shell_relaunch.py;app\webview\audio_playing.py" "%OUT%\ladder-signal.log" python _main\ladder-signal-oracle.py
call :record ladder-signal !STEP_RC!
) else ( call :record ladder-signal MISSING )

if exist _main\launch-as-token.py (
call :step always launch-as-token 0 "_main\launch-as-token.py" "%OUT%\launch-as-token.log" python _main\launch-as-token.py --selftest
call :record launch-as-token !STEP_RC!
) else ( call :record launch-as-token MISSING )

if exist _main\live-code-freshness-oracle.py (
call :step always live-code-freshness 0 "_main\live-code-freshness-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\live-code-freshness.log" python _main\live-code-freshness-oracle.py
call :record live-code-freshness !STEP_RC!
) else ( call :record live-code-freshness MISSING )

if exist _main\load-shedding-oracle.py (
call :step always load-shedding 0 "_main\load-shedding-oracle.py;app\webview\load_shedding.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\load-shedding.log" python _main\load-shedding-oracle.py
call :record load-shedding !STEP_RC!
) else ( call :record load-shedding MISSING )

if exist _main\altc-first-caption-oracle.py (
call :step always red-as-expected-altc-first-caption 1 "_main\altc-first-caption-oracle.py" "%OUT%\altc-first-caption-neg.log" python _main\altc-first-caption-oracle.py --neg-arm
call :expectred red-as-expected-altc-first-caption !STEP_RC! "%OUT%\altc-first-caption-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-altc-first-caption MISSING "%OUT%\altc-first-caption-neg.log" "NEG-ARM PASS" )

if exist _main\altc-gesture-oracle.py (
call :step always red-as-expected-altc-gesture 1 "_main\altc-gesture-oracle.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py" "%OUT%\altc-gesture-neg.log" python _main\altc-gesture-oracle.py --neg-arm
call :expectred red-as-expected-altc-gesture !STEP_RC! "%OUT%\altc-gesture-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-altc-gesture MISSING "%OUT%\altc-gesture-neg.log" "NEG-ARM PASS" )

if exist _main\headphone-cut-probe.py (
call :step always red-as-expected-headphone-cut 1 "_main\headphone-cut-probe.py" "%OUT%\headphone-cut-neg.log" python _main\headphone-cut-probe.py --neg-arm
call :expectred red-as-expected-headphone-cut !STEP_RC! "%OUT%\headphone-cut-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-headphone-cut MISSING "%OUT%\headphone-cut-neg.log" "NEG-ARM PASS" )

if exist _main\incomplete-word-oracle.py (
call :step always red-as-expected-incomplete-word 1 "_main\incomplete-word-oracle.py;worker\stable_words.py" "%OUT%\incomplete-word-neg.log" python _main\incomplete-word-oracle.py --neg-arm
call :expectred red-as-expected-incomplete-word !STEP_RC! "%OUT%\incomplete-word-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-incomplete-word MISSING "%OUT%\incomplete-word-neg.log" "NEG-ARM PASS" )

if exist _main\ladder-signal-oracle.py (
call :step always red-as-expected-ladder-signal 1 "_main\ladder-signal-oracle.py;worker\sotto_worker.py" "%OUT%\ladder-signal-neg.log" python _main\ladder-signal-oracle.py --neg-arm
call :expectred red-as-expected-ladder-signal !STEP_RC! "%OUT%\ladder-signal-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-ladder-signal MISSING "%OUT%\ladder-signal-neg.log" "NEG-ARM PASS" )

if exist _main\launch-as-token.py (
call :step always red-as-expected-launch-as-token 1 "_main\launch-as-token.py" "%OUT%\launch-as-token-neg.log" python _main\launch-as-token.py --neg-arm
call :expectred red-as-expected-launch-as-token !STEP_RC! "%OUT%\launch-as-token-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-launch-as-token MISSING "%OUT%\launch-as-token-neg.log" "NEG-ARM PASS" )

rem --- O MOTOR AO VIVO TEM PESOS? (2026-11-02) -------------------------------------
rem worker/models/ foi ESVAZIADO a 2026-11-01 16:28 e o worker morreu no arranque com
rem "model dir not found". Este passo le o genai_config.json REAL e exige os tres numeros
rem normativos (blank_id/chunk_samples/max_symbols_per_step) e os tamanhos dos grafos. Um
rem artefacto que ja desapareceu uma vez repoe-se por um comando: _main\fetch-nemotron.py.
rem NAO descarrega nada -- um portao que faz rede e um portao que falha offline.
if exist _main\fetch-nemotron.py (
call :step always nemotron-weights 0 "_main\fetch-nemotron.py" "%OUT%\nemotron-weights.log" python _main\fetch-nemotron.py --verify
call :record nemotron-weights !STEP_RC!
) else ( call :record nemotron-weights MISSING )

if exist _main\fetch-nemotron.py (
call :step always red-as-expected-nemotron-weights 1 "_main\fetch-nemotron.py" "%OUT%\nemotron-weights-neg.log" python _main\fetch-nemotron.py --neg-arm
call :expectred red-as-expected-nemotron-weights !STEP_RC! "%OUT%\nemotron-weights-neg.log" "NEG-ARM: PASS"
) else ( call :expectred red-as-expected-nemotron-weights MISSING "%OUT%\nemotron-weights-neg.log" "NEG-ARM: PASS" )

if exist _main\load-shedding-oracle.py (
call :step always red-as-expected-load-shedding 1 "_main\load-shedding-oracle.py;app\webview\load_shedding.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\load-shedding-neg.log" python _main\load-shedding-oracle.py --neg-arm
call :expectred red-as-expected-load-shedding !STEP_RC! "%OUT%\load-shedding-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-load-shedding MISSING "%OUT%\load-shedding-neg.log" "NEG-ARM PASS" )

if exist _main\shell-relaunch-oracle.py (
call :step heavy red-as-expected-shell-relaunch 1 "_main\shell-relaunch-oracle.py" "%OUT%\shell-relaunch-neg.log" python _main\shell-relaunch-oracle.py --neg-arm
call :expectred red-as-expected-shell-relaunch !STEP_RC! "%OUT%\shell-relaunch-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-shell-relaunch MISSING "%OUT%\shell-relaunch-neg.log" "NEG-ARM PASS" )

if exist _main\youtube-word-clock-oracle.py (
call :step always red-as-expected-word-clock 1 "_main\youtube-word-clock-oracle.py;app\webview\youtube_reveal.py;app\webview\caption_overlay.py;app\webview\word_fade.py" "%OUT%\word-clock-neg.log" python _main\youtube-word-clock-oracle.py --neg-arm
call :expectred red-as-expected-word-clock !STEP_RC! "%OUT%\word-clock-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-word-clock MISSING "%OUT%\word-clock-neg.log" "NEG-ARM PASS" )

if exist _main\youtube-monotonic-oracle.py (
call :step always red-as-expected-youtube-monotonic 1 "_main\youtube-monotonic-oracle.py;app\webview\youtube_monotonic.py;_main\webview-run.log" "%OUT%\youtube-monotonic-neg.log" python _main\youtube-monotonic-oracle.py --neg-arm
call :expectred red-as-expected-youtube-monotonic !STEP_RC! "%OUT%\youtube-monotonic-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-monotonic MISSING "%OUT%\youtube-monotonic-neg.log" "NEG-ARM PASS" )

if exist _main\youtube-sotto-drift-oracle.py (
call :step always red-as-expected-youtube-sotto-drift 1 "_main\youtube-sotto-drift-oracle.py;app\webview\youtube_window.py" "%OUT%\youtube-sotto-drift-neg.log" python _main\youtube-sotto-drift-oracle.py --neg-arm
call :expectred red-as-expected-youtube-sotto-drift !STEP_RC! "%OUT%\youtube-sotto-drift-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-sotto-drift MISSING "%OUT%\youtube-sotto-drift-neg.log" "NEG-ARM PASS" )

if exist _main\youtube-switch-oracle.py (
call :step always red-as-expected-youtube-switch 1 "_main\youtube-switch-oracle.py;app\webview\youtube_captions.py;app\webview\sotto_webview.py" "%OUT%\youtube-switch-neg.log" python _main\youtube-switch-oracle.py --neg-arm
call :expectred red-as-expected-youtube-switch !STEP_RC! "%OUT%\youtube-switch-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-switch MISSING "%OUT%\youtube-switch-neg.log" "NEG-ARM PASS" )

if exist _main\yt-no-dub-oracle.py (
call :step always red-as-expected-yt-no-dub 1 "_main\yt-no-dub-oracle.py" "%OUT%\yt-no-dub-neg.log" python _main\yt-no-dub-oracle.py --neg-arm
call :expectred red-as-expected-yt-no-dub !STEP_RC! "%OUT%\yt-no-dub-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-yt-no-dub MISSING "%OUT%\yt-no-dub-neg.log" "NEG-ARM PASS" )

if exist _main\shell-relaunch-oracle.py (
call :step heavy shell-relaunch 0 "_main\shell-relaunch-oracle.py;app\webview\shell_relaunch.py;app\webview\sotto_webview.py;_main\sotto-relaunch.py;_main\sotto-relaunch.cmd" "%OUT%\shell-relaunch.log" python _main\shell-relaunch-oracle.py
call :record shell-relaunch !STEP_RC!
) else ( call :record shell-relaunch MISSING )


if exist _main\youtube-word-clock-oracle.py (
call :step always word-clock 0 "_main\youtube-word-clock-oracle.py;app\webview\youtube_reveal.py;app\webview\youtube_window.py;app\webview\youtube_captions.py;app\webview\sotto_webview.py;app\webview\caption_overlay.py;app\webview\word_fade.py" "%OUT%\word-clock.log" python _main\youtube-word-clock-oracle.py
call :record word-clock !STEP_RC!
) else ( call :record word-clock MISSING )

if exist _main\youtube-monotonic-oracle.py (
call :step always youtube-monotonic 0 "_main\youtube-monotonic-oracle.py;app\webview\youtube_monotonic.py;app\webview\sotto_webview.py;_main\webview-run.log" "%OUT%\youtube-monotonic.log" python _main\youtube-monotonic-oracle.py
call :record youtube-monotonic !STEP_RC!
) else ( call :record youtube-monotonic MISSING )

if exist _main\youtube-rate-oracle.py (
call :step always youtube-rate 0 "_main\youtube-rate-oracle.py;app\webview\sotto_webview.py;app\webview\caption_overlay.py;app\webview\youtube_cdp_source.py" "%OUT%\youtube-rate.log" python _main\youtube-rate-oracle.py
call :record youtube-rate !STEP_RC!
) else ( call :record youtube-rate MISSING )

if exist _main\youtube-rate-oracle.py (
call :step always red-as-expected-youtube-rate 1 "_main\youtube-rate-oracle.py;app\webview\sotto_webview.py;app\webview\caption_overlay.py;app\webview\youtube_cdp_source.py" "%OUT%\youtube-rate-neg.log" python _main\youtube-rate-oracle.py --neg-arm
call :expectred red-as-expected-youtube-rate !STEP_RC! "%OUT%\youtube-rate-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-youtube-rate MISSING "%OUT%\youtube-rate-neg.log" "NEG-ARM PASS" )

if exist _main\click-through-applied-oracle.py (
call :step always click-through-applied 0 "_main\click-through-applied-oracle.py;app\webview\sotto_webview.py" "%OUT%\click-through-applied.log" python _main\click-through-applied-oracle.py
call :record click-through-applied !STEP_RC!
) else ( call :record click-through-applied MISSING )

if exist _main\click-through-applied-oracle.py (
call :step always red-as-expected-click-through-applied 1 "_main\click-through-applied-oracle.py;app\webview\sotto_webview.py" "%OUT%\click-through-applied-neg.log" python _main\click-through-applied-oracle.py --neg-arm
call :expectred red-as-expected-click-through-applied !STEP_RC! "%OUT%\click-through-applied-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-click-through-applied MISSING "%OUT%\click-through-applied-neg.log" "NEG-ARM PASS" )

if exist _main\topmost-keepalive-oracle.py (
call :step always topmost-keepalive 0 "_main\topmost-keepalive-oracle.py;app\webview\topmost_keepalive.py" "%OUT%\topmost-keepalive.log" python _main\topmost-keepalive-oracle.py
call :record topmost-keepalive !STEP_RC!
) else ( call :record topmost-keepalive MISSING )

if exist _main\topmost-keepalive-oracle.py (
call :step always red-as-expected-topmost-keepalive 1 "_main\topmost-keepalive-oracle.py;app\webview\topmost_keepalive.py" "%OUT%\topmost-keepalive-neg.log" python _main\topmost-keepalive-oracle.py --neg-arm
call :expectred red-as-expected-topmost-keepalive !STEP_RC! "%OUT%\topmost-keepalive-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-topmost-keepalive MISSING "%OUT%\topmost-keepalive-neg.log" "NEG-ARM PASS" )

rem ---- O PORTO DE DEPURACAO DO WEBVIEW2 E' NOSSO, NUNCA DA CAIXA -------
rem Nascido de um defeito medido a 2026-11-04: o ambiente desta sessao tem
rem `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333`, e o
rem loader do WebView2 le essa variavel no ambiente do PROCESSO. Um valor
rem herdado abre um porto de depuracao em TODAS as janelas WebView2 da app e,
rem pior, faz o MESMO binario comportar-se diferente na sessao do dono (que nao
rem tem o valor) e na de uma lane (que tem) -- a medicao verde numa lane deixa
rem de dizer nada sobre o que ele ve. O produto NAO precisa do porto: a fonte
rem do YouTube le o browser do dono em 9222. Por isso o valor herdado e' REMOVIDO
rem e so' `--cdp-port N` / `SOTTO_CDP_PORT=N` o poem. Os dois passos sao
rem `always`: leem o ficheiro da shell e executam a funcao REAL num processo,
rem e um resultado em cache descreveria um ficheiro que ja mudou.
if exist _main\webview2-args-scope-oracle.py (
call :step always webview2-args-scope 0 "_main\webview2-args-scope-oracle.py;app\webview\webview2_args.py;app\webview\sotto_webview.py" "%OUT%\webview2-args-scope.log" python _main\webview2-args-scope-oracle.py
call :record webview2-args-scope !STEP_RC!
) else ( call :record webview2-args-scope MISSING )

if exist _main\webview2-args-scope-oracle.py (
call :step always red-as-expected-webview2-args-scope 1 "_main\webview2-args-scope-oracle.py;app\webview\webview2_args.py;app\webview\sotto_webview.py" "%OUT%\webview2-args-scope-neg.log" python _main\webview2-args-scope-oracle.py --neg-arm
call :expectred red-as-expected-webview2-args-scope !STEP_RC! "%OUT%\webview2-args-scope-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-webview2-args-scope MISSING "%OUT%\webview2-args-scope-neg.log" "NEG-ARM PASS" )

if exist _main\power-recovery-oracle.py (
call :step always power-recovery 0 "_main\power-recovery-oracle.py;app\webview\power_recovery.py;app\webview\sotto_webview.py" "%OUT%\power-recovery.log" python _main\power-recovery-oracle.py
call :record power-recovery !STEP_RC!
) else ( call :record power-recovery MISSING )

if exist _main\power-recovery-oracle.py (
call :step always red-as-expected-power-recovery 1 "_main\power-recovery-oracle.py;app\webview\power_recovery.py;app\webview\sotto_webview.py" "%OUT%\power-recovery-neg.log" python _main\power-recovery-oracle.py --neg-arm
call :expectred red-as-expected-power-recovery !STEP_RC! "%OUT%\power-recovery-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-power-recovery MISSING "%OUT%\power-recovery-neg.log" "NEG-ARM PASS" )

if exist _main\power-recovery-oracle.py (
call :step heavy power-recovery-live 0 "_main\power-recovery-oracle.py;app\webview\power_recovery.py;app\webview\sotto_webview.py;_main\keepalive.py" "%OUT%\power-recovery-live.log" python _main\power-recovery-oracle.py --live-arm
call :record power-recovery-live !STEP_RC!
) else ( call :record power-recovery-live MISSING )

if exist _main\youtube-sotto-drift-oracle.py (
call :step always youtube-sotto-drift 0 "_main\youtube-sotto-drift-oracle.py;app\webview\youtube_reveal.py;app\webview\youtube_window.py;app\webview\youtube_captions.py;_main\fixtures\yt-WdaHAGRBB6s.en-orig.json3;_main\fixtures\yt-WdaHAGRBB6s.live-compare-20261026.json" "%OUT%\youtube-sotto-drift.log" python _main\youtube-sotto-drift-oracle.py
call :record youtube-sotto-drift !STEP_RC!
) else ( call :record youtube-sotto-drift MISSING )

if exist _main\youtube-switch-oracle.py (
call :step always youtube-switch 0 "_main\youtube-switch-oracle.py;app\webview\youtube_captions.py;app\webview\sotto_webview.py" "%OUT%\youtube-switch.log" python _main\youtube-switch-oracle.py
call :record youtube-switch !STEP_RC!
) else ( call :record youtube-switch MISSING )

if exist _main\yt-no-dub-oracle.py (
call :step always yt-no-dub 0 "_main\yt-no-dub-oracle.py;app\webview\youtube_captions.py;app\webview\sotto_webview.py" "%OUT%\yt-no-dub.log" python _main\yt-no-dub-oracle.py
call :record yt-no-dub !STEP_RC!
) else ( call :record yt-no-dub MISSING )


REM ---- O DISPLAY NAO HERDA A FONTE ANTERIOR, E UM PASSO QUE LARGA A APP
REM NAO PODE CORRER NA CLASSE `always` (2026-10-30).
if exist _main\stale-display-oracle.py (
call :step always stale-display 0 "_main\stale-display-oracle.py;app\webview\caption_overlay.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\stale-display.log" python _main\stale-display-oracle.py
call :record stale-display !STEP_RC!
) else ( call :record stale-display MISSING )
if exist _main\stale-display-oracle.py (
call :step always red-as-expected-stale-display 1 "_main\stale-display-oracle.py;app\webview\caption_overlay.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\stale-display-neg.log" python _main\stale-display-oracle.py --neg-arm
call :expectred red-as-expected-stale-display !STEP_RC! "%OUT%\stale-display-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-stale-display MISSING "%OUT%\stale-display-neg.log" "NEG-ARM PASS" )

if exist _main\battery-class-oracle.py (
call :step always battery-class 0 "_main\battery-class-oracle.py;_main\_audit-verify-all.cmd" "%OUT%\battery-class.log" python _main\battery-class-oracle.py
call :record battery-class !STEP_RC!
) else ( call :record battery-class MISSING )
if exist _main\battery-class-oracle.py (
call :step always red-as-expected-battery-class 1 "_main\battery-class-oracle.py;_main\_audit-verify-all.cmd" "%OUT%\battery-class-neg.log" python _main\battery-class-oracle.py --neg-arm
call :expectred red-as-expected-battery-class !STEP_RC! "%OUT%\battery-class-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-battery-class MISSING "%OUT%\battery-class-neg.log" "NEG-ARM PASS" )

if exist _main\live-queue-oracle.py (
call :step always live-queue 0 "_main\live-queue-oracle.py;worker\live_queue.py;worker\sotto_worker.py" "%OUT%\live-queue.log" python _main\live-queue-oracle.py
call :record live-queue !STEP_RC!
) else ( call :record live-queue MISSING )
if exist _main\live-queue-oracle.py (
call :step always red-as-expected-live-queue 1 "_main\live-queue-oracle.py;worker\live_queue.py;worker\sotto_worker.py" "%OUT%\live-queue-neg.log" python _main\live-queue-oracle.py --neg-arm
call :expectred red-as-expected-live-queue !STEP_RC! "%OUT%\live-queue-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-live-queue MISSING "%OUT%\live-queue-neg.log" "NEG-ARM PASS" )

if exist _main\flat-endpoint-oracle.py (
call :step always flat-endpoint 0 "_main\flat-endpoint-oracle.py;worker\wasapi_loopback.py" "%OUT%\flat-endpoint.log" python _main\flat-endpoint-oracle.py
call :record flat-endpoint !STEP_RC!
) else ( call :record flat-endpoint MISSING )

REM -- A MAQUINA CALADA NAO E' UM DISPOSITIVO PARTIDO (2026-11-02) -------------
REM Medido na sessao viva pid 4404: 12 clientes WASAPI abertos em 3 minutos com o
REM desktop em silencio (`device-rotated reason=flat` a cada 15 s, `peak=0.0`), e
REM cada abertura e' um hitch no motor de audio que o dono partilha. O oraculo
REM executa a funcao REAL do worker (8 arms) e mais a fiacao no ramo da janela; o
REM `--neg-arm` desliga a guarda numa COPIA e exige os arms 1-2 vermelhos.
if exist _main\tap-silent-desktop-oracle.py (
call :step always tap-silent-desktop 0 "_main\tap-silent-desktop-oracle.py;worker\sotto_worker.py" "%OUT%\tap-silent-desktop.log" python _main\tap-silent-desktop-oracle.py
call :record tap-silent-desktop !STEP_RC!
) else ( call :record tap-silent-desktop MISSING )

if exist _main\tap-silent-desktop-oracle.py (
call :step always red-as-expected-tap-silent-desktop 1 "_main\tap-silent-desktop-oracle.py;worker\sotto_worker.py" "%OUT%\tap-silent-desktop-neg.log" python _main\tap-silent-desktop-oracle.py --neg-arm
call :expectred red-as-expected-tap-silent-desktop !STEP_RC! "%OUT%\tap-silent-desktop-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-tap-silent-desktop MISSING "%OUT%\tap-silent-desktop-neg.log" "NEG-ARM PASS" )

echo.

REM -- CTRL+SPACE EM GAMING, O NAO-ROUBO DE FOCO E A DETECCAO DE JOGO (2026-11-04)
REM Ordem do dono: *"e em gaming: control espaço nao da display na legenda. nao
REM faz nada. nem on nem off. fora de gaming: control espaço nao ativa o espaço em
REM apps. detecta 'gaming' parecido com o que meu projeto !watcher do disco i faz."*
REM O oraculo executa o observador REAL, o caminho REAL do toggle (com o user32
REM por tras de um GRAVADOR) e o detector REAL: mede que o toggle nao rouba o
REM primeiro plano, que nao existe API que coma teclas, que a pressao que cai
REM dentro de uma volta perdida ainda e' vista (o bit 0), e que o dwell do
REM !watcher mantem `is_gaming()` pelos ticks que ele manda. Sem janela, sem
REM tecla sintetica.
if exist _main\gaming-hotkey-oracle.py (
call :step always gaming-hotkey 0 "_main\gaming-hotkey-oracle.py;app\webview\gaming_mode.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py;app\webview\caption_overlay.py" "%OUT%\gaming-hotkey.log" python _main\gaming-hotkey-oracle.py
call :record gaming-hotkey !STEP_RC!
) else ( call :record gaming-hotkey MISSING )

if exist _main\gaming-hotkey-oracle.py (
call :step always red-as-expected-gaming-hotkey 1 "_main\gaming-hotkey-oracle.py;app\webview\gaming_mode.py;app\webview\sotto_webview.py;app\webview\hotkey_gesture.py;app\webview\caption_overlay.py" "%OUT%\gaming-hotkey-neg.log" python _main\gaming-hotkey-oracle.py --neg-arm
call :expectred red-as-expected-gaming-hotkey !STEP_RC! "%OUT%\gaming-hotkey-neg.log" "NEG-ARM PASS"
) else ( call :expectred red-as-expected-gaming-hotkey MISSING "%OUT%\gaming-hotkey-neg.log" "NEG-ARM PASS" )

echo.
echo =============== BATTERY SUMMARY ===============
echo steps    : !N!   gate=!GATES!  control=!CTRLS!  skipped=!SKIPN!  expect-red=!REDS!  missing=!MISSINGN!  cached=!CACHEDN!
echo cached   : !CACHEDN! step(s) were reused from the cache (their content and their logs were unchanged)
REM THE SLOWEST STEPS (owner, 2026-10-21: *"a bateria deve ser rapida"*). Until
REM this table existed nobody could say WHICH step was heavy -- and the fast
REM mode reads the same numbers to decide what to skip.
python _main\_stepcache.py slowest --state "%CACHE_STATE%" --top 8 > "%OUT%\_slowest.txt" 2>&1
echo slowest  : the steps that took the longest last run
type "%OUT%\_slowest.txt"
if "!HEAVYLIST!"=="" ( set "HEAVYTEXT=-none-" ) else ( set "HEAVYTEXT=!HEAVYLIST!" )
echo heavy    : !HEAVYTEXT!
echo             (the HEAVY class opens the owner's screen, his audio device or his GPU -- these did NOT run; set SOTTO_BATTERY_HEAVY=1 to run them)
echo priority : !BATTERY_PRIORITY_LINE!
if defined SOTTO_BATTERY_FAST echo fastmode : ON -- a step slower than the threshold was SKIPPED, not run, and is listed under skipped=
if "%SOTTO_BATTERY_HEAVY%"=="1" echo heavymode: ON -- the heavy steps RAN: they opened the owner's screen, his audio device or his GPU
echo per-step : !STEPLIST!
echo controls : !CONTROLLIST!
if "!FAILED!"=="" ( set "FAILEDTEXT=-none-" ) else ( set "FAILEDTEXT=!FAILED!" )
if "!SKIPLIST!"=="" ( set "SKIPTEXT=-none-" ) else ( set "SKIPTEXT=!SKIPLIST!" )
echo failed   : !FAILEDTEXT!
echo skipped  : !SKIPTEXT!
if "!BAD!"=="0" (
  set "VERDICT=GREEN - every step held and every control went RED on its broken copy"
)
if "!BAD!"=="0" if not "!SKIPN!"=="0" (
  set "VERDICT=GREEN WITH !SKIPN! SKIPPED - !SKIPN! step(s) did NOT verify this run and are NOT counted as gates: !SKIPTEXT!"
)
if "!BAD!"=="0" if not "!HEAVYN!"=="0" (
  set "VERDICT=!VERDICT! - !HEAVYN! of them are the HEAVY class (they open the owner's screen, his audio device or his GPU and did NOT run: !HEAVYTEXT!)"
)
if "!BAD!"=="0" if not "!CACHEDN!"=="0" (
  set "VERDICT=!VERDICT! - !CACHEDN! step(s) were reused from the cache: their files did not change and their logs are still the ones that were verified"
)
if not "!BAD!"=="0" (
  set "VERDICT=RED - !BAD! step(s) failed"
)
echo BATTERY-VERDICT: !VERDICT!
echo receipts in %OUT%
>"%OUT%\_battery-summary.txt" echo steps=!N! gate=!GATES! control=!CTRLS! skipped=!SKIPN! expect-red=!REDS! missing=!MISSINGN! cached=!CACHEDN! failed=!BAD!
>>"%OUT%\_battery-summary.txt" echo rcs: !STEPLIST!
>>"%OUT%\_battery-summary.txt" echo controls: !CONTROLLIST!
>>"%OUT%\_battery-summary.txt" echo skipped: !SKIPTEXT!
>>"%OUT%\_battery-summary.txt" echo heavy: !HEAVYTEXT!
>>"%OUT%\_battery-summary.txt" echo priority: !BATTERY_PRIORITY_LINE!
>>"%OUT%\_battery-summary.txt" echo slowest:
>>"%OUT%\_battery-summary.txt" type "%OUT%\_slowest.txt"
>>"%OUT%\_battery-summary.txt" echo failed: !FAILEDTEXT!
>>"%OUT%\_battery-summary.txt" echo exit-code: !BAD!
>>"%OUT%\_battery-summary.txt" echo BATTERY-VERDICT: !VERDICT!
REM The exit code IS the aggregation: 0 only when nothing failed. Nothing else in
REM this file may return 0 on a red step.
if not "!BAD!"=="0" exit /b 1
exit /b 0

REM ===========================================================================
REM  The recorders. Every step calls exactly one of these with its OWN rc as an
REM  argument, so no step can print a beacon without being counted.
REM ===========================================================================

REM ===========================================================================
REM  THE STEP CACHE. One step, one fingerprint, one honest answer.
REM ===========================================================================
REM
REM :step [always] <name> <expect-rc> <deps;> <logfile> <command...>
REM
REM   The engine is _main\_stepcache.py and the state is _cache\battery-steps.json.
REM   The fingerprint of a step is the CONTENT of every file it judges -- the
REM   instrument itself plus the product files it reads. Change the bytes and
REM   the step runs again; touch a file without changing a byte and it does
REM   NOT. mtime alone decides nothing, because mtime is not what the gate read.
REM
REM   A HIT is only a HIT when all three hold: the fingerprint matches, the
REM   recorded rc is the rc this step is SUPPOSED to produce, and the log the
REM   step produced is still there, byte for byte. Anything else is a MISS. A
REM   step that FAILED is never reused as if it had passed: the rc is part of
REM   the proof, not a decoration.
REM
REM   `always` marks a step whose truth is OUTSIDE the files -- the Windows
REM   registry, the real keyboard, the real audio device, the owner's own app
REM   holding Alt+C, and the sweep that proves no step lied. Those are NEVER
REM   cached: a cache that reuses a reading of the outside world is a lie, and
REM   a lie that is faster is still a lie.
REM
REM   The command's exit code comes back in STEP_RC, and the caller hands it to
REM   the recorder (:record / :control / :skipped / :expectred), so the FOUR
REM   KINDS keep their meaning exactly as before. A cached step still has to
REM   prove its verdict in its log -- the control reads the SAME log the
REM   previous run wrote, and if the verdict text is not there, it FAILS.
REM
REM   STEP_CACHED says whether the step was reused (the summary counts them),
REM   and STEP_TAG is the "  (cached)" the beacon carries so a reader can see
REM   which steps did not run.
:step
set "STEP_RC="
set "STEP_CACHED=0"
set "STEP_TAG="
set "STEP_FASTSKIP="
set "STEP_HEAVYSKIP="
set "S_ALWAYS="
set "S_HEAVY="
if /i "%~1"=="always" goto step_take_always
if /i "%~1"=="heavy" goto step_take_heavy
goto step_args
:step_take_always
set "S_ALWAYS=1"
shift
if /i "%~1"=="heavy" goto step_take_heavy
goto step_args
:step_take_heavy
set "S_HEAVY=1"
shift
:step_args
set "S_NAME=%~1"
set "S_EXPECT=%~2"
set "S_DEPS=%~3"
set "S_LOG=%~4"
shift
shift
shift
shift
set "S_CMD="
:step_build
if "%~1"=="" goto step_built
if defined S_CMD goto step_append
set "S_CMD=%~1"
shift
goto step_build
:step_append
set "S_CMD=!S_CMD! "%~1""
shift
goto step_build
:step_built
set "S_HIT=0"
set "S_CACHED_RC="
set "S_ELAPSED="
set "S_THRESHOLD="
set "S_FASTSKIP=0"
set "S_ALWAYSFARG="
if "!S_ALWAYS!"=="1" set "S_ALWAYSFARG=--always"
REM THE ALWAYS STEPS ASK TOO. The check is cheap and it is the only thing that
REM knows how long a step took -- and the FAST MODE reads that number. An
REM always step is never CACHED, but it is still TIMED. `--always` keeps the
REM check from answering HIT for it (its truth is outside the files).
for /f "tokens=1,* delims==" %%A in ('python _main\_stepcache.py check --step "!S_NAME!" --expect-rc !S_EXPECT! --deps "!S_DEPS!" --log "!S_LOG!" --state "%CACHE_STATE%" !S_ALWAYSFARG! 2^>nul') do (
  if /i "%%A"=="HIT" set "S_HIT=1"
  if /i "%%A"=="rc" set "S_CACHED_RC=%%B"
  if /i "%%A"=="elapsed" set "S_ELAPSED=%%B"
  if /i "%%A"=="threshold" set "S_THRESHOLD=%%B"
  if /i "%%A"=="SKIP-SLOW" set "S_FASTSKIP=1"
)
if "!S_FASTSKIP!"=="1" goto step_fastskip
REM THE HEAVY CLASS (owner, 2026-10-21, verbatim: *"tu ta fazendo algo que faz meu
REM pc travar/stutter?"* and *"tu vai garantir que minha reclamacao nunca mais
REM aconteca"*). A heavy step opens the owner's SCREEN, his AUDIO DEVICE or his GPU:
REM it starts the app shell -- and with it the WebView2 runtime, 38
REM msedgewebview2.exe and a saturated VRAM (measured 2026-10-21, written down in
REM _main/_strip-stats-log-probe.py) -- or it touches the real output device.
REM The machine starts ANY process with a 53-127 ms stutter (measured 2026-10-21),
REM so these are the steps the owner FELT. They do NOT run unless the owner asks
REM for them: SOTTO_BATTERY_HEAVY=1.
REM A CACHED heavy step is FREE (no process is started) and keeps its gate. A heavy
REM step that would have to RUN is skipped, counted as SKIPPED, and NAMED in the
REM summary -- never rounded up to a pass.
if "!S_HEAVY!"=="1" if not "%SOTTO_BATTERY_HEAVY%"=="1" if not "!S_HIT!"=="1" goto step_heavyskip
if "!S_ALWAYS!"=="1" goto step_run
if "!S_HIT!"=="1" goto step_hit
:step_run
REM THE CLOCK. A MARKER FILE, not another process: the battery already starts a
REM python for every step, and one more per step would be a tax on every run
REM to serve one mode.
echo.>"%CACHE_STATE%.t0"
!S_CMD! > "!S_LOG!" 2>&1
set "STEP_RC=!ERRORLEVEL!"
python _main\_stepcache.py record --step "!S_NAME!" --expect-rc !S_EXPECT! --deps "!S_DEPS!" --rc !STEP_RC! --log "!S_LOG!" --state "%CACHE_STATE%" --t0 "%CACHE_STATE%.t0" >nul 2>&1
exit /b 0
:step_fastskip
REM THE FAST MODE (owner, 2026-10-21: *"a bateria deve ser rapida"*). This step
REM was slower than the threshold in the last run, so it is NOT run now. It is
REM NOT a gate that passed: the recorder counts it as SKIPPED and the summary
REM names it, with the time it had taken.
echo BATTERY-FAST-SKIP step=!S_NAME! last_s=!S_ELAPSED! threshold_s=!S_THRESHOLD!>"!S_LOG!"
set "STEP_RC=0"
set "STEP_FASTSKIP=1"
exit /b 0
:step_heavyskip
REM THE HEAVY CLASS DID NOT RUN. It is NOT a gate that passed and NOT a failure:
REM the battery was told not to open the owner's screen, his audio device or his
REM GPU, so the step that does that did not run. It is counted in `skipped=`, it is
REM NAMED in the summary, and the summary says how many steps did NOT verify.
REM The log carries the BATTERY's marker, not the instrument's words: the
REM instrument never spoke, so nothing in it can be read as a verdict.
REM (The opt-in is the VALUE "1", not the mere EXISTENCE of the variable: a
REM caller that sets SOTTO_BATTERY_HEAVY=0 means OFF, and a check of `defined`
REM would run the heavy steps for it. Measured 2026-10-22 by the very census
REM instrument that caught it.)
echo BATTERY-HEAVY-SKIP step=!S_NAME! reason=opens-the-owner-screen-or-audio-device opt-in=SOTTO_BATTERY_HEAVY>"!S_LOG!"
set "STEP_RC=0"
set "STEP_FASTSKIP=1"
set "STEP_HEAVYSKIP=1"
exit /b 0
:step_hit
set "STEP_RC=!S_CACHED_RC!"
set "STEP_CACHED=1"
set "STEP_TAG=  (cached)"
set /a CACHEDN+=1
exit /b 0
REM :record <name> <rc>          -- an ordinary gate: rc=0 is the only pass.
:record
if defined STEP_FASTSKIP goto fastskip
set /a N+=1
set /a GATES+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
if "%~2"=="0" (
  echo [step] %~1 rc=0!STEP_TAG!
  exit /b 0
)
if /i "%~2"=="MISSING" (
  set /a MISSINGN+=1
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=MISSING"
  echo [step] %~1 MISSING  ** THE INSTRUMENT IS NOT THERE: a missing step is not a pass **
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  ** FAILED **
exit /b 0

REM :skipped <name> <rc> <log> <verified-text> <skip-text> [<skip-text-2>]
REM   For an arm the ENVIRONMENT can make unrunnable -- today the Alt+C delivery arm,
REM   which `_audit-hotkey-delivery.py` skips by design while the owner's live shell
REM   holds the key. Three outcomes, and no fourth:
REM     * rc<>0 or MISSING                 -> FAILURE (a step that exits non-zero has
REM                                           not "skipped", it has failed)
REM     * rc=0 AND the skip text(s) present -> SKIPPED: counted in `skipped=`, listed
REM                                           in the summary, and NEVER counted in
REM                                           `gate=`, because nothing was verified
REM     * rc=0 AND the verified text present, no skip text -> a REAL gate this run
REM     * rc=0 with NEITHER                -> FAILURE. This is the direction that
REM       matters: an instrument that cannot say whether it verified or skipped must
REM       not be rounded up to a pass, and a silent no-op posing as a skip is exactly
REM       the family this battery exists to kill.
REM   A second skip text makes the skip claim stronger: for this probe both
REM   `VERDICT: SKIPPED` AND `CANNOT claim` are required, so a stray mention of the
REM   word in a verified run cannot be read as a skip.
:skipped
REM THE FAST MODE (owner, 2026-10-21: *"a bateria deve ser rapida"*). A step
REM that was slower than the threshold was NOT RUN, and the battery's own marker
REM says so in the log (`BATTERY-FAST-SKIP ...`). The instrument never spoke, so
REM its own skip/verified literals are absent BY DESIGN -- reading them as "the
REM instrument cannot say what it did" turned a skipped step into a FAILED one
REM (measured 2026-10-21: the fast run reported 2 failures, both of them steps
REM that were skipped on purpose). A step the BATTERY skipped is skipped, not
REM failed -- and, like every other skip, it is NOT counted as a gate.
if defined STEP_FASTSKIP goto fastskip
set /a N+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "WHY="
set "OUTCOME="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing step is not a pass, and it is not a skip either"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 - this step exits 0 whether it verifies or skips, so a non-zero rc is a FAILURE, not a skip"
if not defined WHY (
  call :hastext "%~3" "%~5"
  if "!HAS!"=="yes" set "OUTCOME=skipped"
)
if not defined WHY if not "%~6"=="" (
  call :hastext "%~3" "%~6"
  if not "!HAS!"=="yes" set "OUTCOME="
)
if not defined WHY if not defined OUTCOME (
  call :hastext "%~3" "%~4"
  if "!HAS!"=="yes" set "OUTCOME=verified"
)
if not defined WHY if not defined OUTCOME set "WHY=rc=0 but the log carries NEITHER the skip verdict (%~5) NOR the verified verdict (%~4) - the instrument cannot say what it did, and a step that cannot say is not a pass"
if defined WHY (
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=%~2"
  echo [step] %~1 rc=%~2  [SKIP-CAPABLE]  ** STEP FAILED: !WHY! **
  if /i "%~2"=="MISSING" set /a MISSINGN+=1
  exit /b 0
)
if "!OUTCOME!"=="skipped" (
  set /a SKIPN+=1
  set "SKIPLIST=!SKIPLIST! %~1"
  for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,"
  echo [step] %~1 rc=0  [SKIPPED] NOT VERIFIED: the instrument itself says this arm did not run, its own words being %~5!STEP_TAG!
  exit /b 0
)
set /a GATES+=1
echo [step] %~1 rc=0  [SKIP-CAPABLE, verified this run] %~4 - the skip verdict is absent, so this IS a gate!STEP_TAG!
exit /b 0

REM :fastskip -- the FAST MODE did not run this step (owner, 2026-10-21).
REM   It did NOT verify anything, so it is NOT a gate that passed, NOT a
REM   control that went RED and NOT an expect-red arm that failed: it is
REM   counted in `skipped=`, NAMED in the summary, and the verdict says how
REM   many steps did not verify. A step that cannot say what it did is never
REM   rounded up to a pass.
:fastskip
set /a N+=1
set /a SKIPN+=1
if defined STEP_HEAVYSKIP (
  set "STEPLIST=!STEPLIST! %~1=heavy-skip"
  set "SKIPLIST=!SKIPLIST! %~1"
  for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,
  set "HEAVYLIST=!HEAVYLIST! %~1"
  set /a HEAVYN+=1
  echo [step] %~1 rc=0  [SKIPPED: heavy class] NOT RUN: it opens the owner's screen, his audio device or his GPU -- set SOTTO_BATTERY_HEAVY=1 to run it
  exit /b 0
)
set "STEPLIST=!STEPLIST! %~1=fast-skip"
set "SKIPLIST=!SKIPLIST! %~1"
for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,
echo [step] %~1 rc=0  [SKIPPED: fast mode] NOT RUN: slower than the threshold in the last run
exit /b 0

REM :control <name> <rc> <log> <required-text> [<required-text-2>]
REM   A control PASSES only when the instrument exits 0 (its own "the copy went
REM   RED" signal) AND its log carries the required verdict text. Anything else --
REM   a non-zero rc, a missing file, an rc=0 with no verdict in the log -- FAILS.
REM   The optional second text exists for a probe whose verdict can be unreachable
REM   (rc=1 and a traceback instead of a verdict): it lets the step demand a second,
REM   independent fact from the same run (e.g. that the mutant COPY was removed).
:control
if defined STEP_FASTSKIP goto fastskip
set /a N+=1
set /a CTRLS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 and this step succeeds ONLY by catching its broken copy"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed the control verdict %~4 - the control did not report catching its copy"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=0  [CONTROL] went RED on the broken copy as required!STEP_TAG!
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [CONTROL]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :expectred <name> <rc> <log> <required-text> [<required-text-2>]
REM   For an instrument whose RED-by-design mode has NO control wrapper. It must
REM   exit 1 -- the defect found -- and print the violation it found. rc=0 means
REM   the deliberately-broken copy was NOT caught (the control did not go red),
REM   and rc=2 is a setup error: both FAIL.
:expectred
if defined STEP_FASTSKIP goto fastskip
set /a N+=1
set /a REDS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="1" if not defined WHY set "WHY=rc=%~2 - this step must find the injected defect and exit 1; rc=0 means the control did NOT go red, rc=2 is a setup error"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~4"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=1  [EXPECT-RED] the defect was found and named, as required!STEP_TAG!
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [EXPECT-RED]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :hastext <file> <text>  -- sets HAS=yes|no. Read as BYTES and decoded as
REM UTF-8 so a console-codepage mojibake in the log cannot hide a verdict, and so
REM the required text may contain quotes or an em dash.
:hastext
set "HAS=no"
python -c "import io,sys;t=io.open(sys.argv[1],'rb').read().decode('utf-8','replace');sys.exit(0 if sys.argv[2] in t else 3)" "%~1" "%~2" >nul 2>&1
if "!ERRORLEVEL!"=="0" set "HAS=yes"
exit /b 0
