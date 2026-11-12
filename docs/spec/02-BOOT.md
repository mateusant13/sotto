# 02 — ARRANQUE: do duplo-clique à primeira legenda pintada

Este ficheiro descreve o que o código em `HEAD` FAZ entre o duplo-clique e o primeiro pixel de
legenda: a ordem em que os objectos nascem, quem espera por quem, e o número que cada espera publica.
Tudo o que é factual leva etiqueta, e a linha citada foi lida nesta campanha (2026-11-11).

**O aviso que vale para a página inteira.** O processo vivo no momento desta leitura é ANTERIOR ao
código. `[MEASURED]` `python _main/live-code-freshness-oracle.py --strict` (2026-11-11 23:25:48):
`LIVE_CODE STALE log=H:\sotto\_main\webview-run.log`, `pid=41852 started=2026-11-11 22:56:36.341`,
`processo: sha256=1D027EB01669` contra `disco: sha256=E3270577EB2F files=110`, `MUDOU DEPOIS DO
ARRANQUE: sotto_webview.py`. Logo os números de sessões reais desta página são **históricos**, e cada
um diz a data e a sessão de onde vem.

## 1. A cadeia de largada

O `Sotto.cmd` da raiz é um encaminhador, não um segundo ponto de entrada: `[CODE]` `Sotto.cmd:31`
faz `call "%~dp0app\webview\run.cmd" %*` e devolve `exit /b %ERRORLEVEL%`; o `run.cmd` também é
ponto de entrada directo `[CODE]` `run.cmd:2-4` e fixa o próprio directório em `run.cmd:78-80`
`[CODE]`. A sequência completa:

| # | passo | o que faz | onde |
|---|---|---|---|
| 1 | defaults de ambiente | `SOTTO_REDUX_LIVE=1` e `SOTTO_REDUX_WHEN_HIDDEN=1` só quando não estão definidos | `run.cmd:113`, `run.cmd:140` |
| 2 | achar o interpretador | `py -3 -c "import sys;print(sys.executable)"`; sem ele, `where python` | `run.cmd:149-152` |
| 3 | escolher GUI | `%PYEXE:python.exe=pythonw.exe%`; sem `pythonw.exe` recusa com `rc=3` — não há `fallback` para consola | `run.cmd:158`, `run.cmd:166-170` |
| 4 | flags que IMPRIMEM | `--help`, `-h`, `--dump-dom`, `--selftest`, `--memory`, `--install-autostart`, `--uninstall-autostart`, `--autostart-status` correm sob `"%PYEXE%"` no terminal existente e saem com o `%ERRORLEVEL%` | `run.cmd:178-197` |
| 5 | pre-flight | `"%PYW%" "%SHELL%" --check-args %*`, com o `stderr` capturado para `sotto-preflight-refusal-<rand><rand>.txt` | `run.cmd:250-252` |
| 6 | recusa do pre-flight | imprime `the shell REFUSED this launch (rc=N). Nothing was started.`, o texto do interpretador, e escreve `sotto: PREFLIGHT_REFUSED rc=N by=run.cmd-preflight` no log | `run.cmd:254-269` |
| 7 | `--check-args` sozinho | o pre-flight É a acção: `exit /b %PREFLIGHT_RC%`, nada arranca | `run.cmd:277` |
| 8 | ficheiro de prontidão | `READY_FILE=%HERE%..\..\_main\ready-%RANDOM%-%RANDOM%.txt`, apagado antes de viajar | `run.cmd:294-295` |
| 9 | `start` da app | `start "" "%PYW%" "%SHELL%" ... --ready-file "%READY_FILE%"`; log por omissão `_main\webview-run.log` quando o utilizador não passou `--log` | `run.cmd:301-309` |
| 10 | espera limitada | `"%PYW%" "%SHELL%" --wait-ready "%READY_FILE%"` | `run.cmd:312` |
| 11 | `rc=4` = HANG | duas frases no terminal, `sotto: HANG rc=4 by=run.cmd-readiness` no log, `exit /b 4` | `run.cmd:315-319` |

Três consequências que o código impõe, e que a tabela não mostra:

1. **Uma largada normal corre a shell TRÊS vezes** `[INFERENCE]` a partir de `run.cmd:252`
   (pre-flight), `run.cmd:302`/`run.cmd:308` (app) e `run.cmd:312` (espera): três processos
   `pythonw.exe`, e só o segundo sobrevive.
2. **O pre-flight valida contra o `argparse` da própria shell** `[CODE]` `run.cmd:207-212` — não há
   segunda tabela de flags em batch. O modo em si está em `main()`: `[CODE]`
   `sotto_webview.py:26016-26050` devolve 3 quando falta `PANEL_HTML` (`:26036-26038`), 1 quando
   `import webview` falha (`:26045-26049`) e 0 quando a lista passa (`:26050`); `rc=2` é o próprio
   `parse_args` a sair.
3. **A espera é LIMITADA e não espera pelo fim da app** `[CODE]` `run.cmd:284-292`: o tecto vem de
   `SOTTO_READY_BOUND` (por omissão `'30'`, `sotto_webview.py:26011`), e `wait_ready_file`
   (`:2727`) faz poll de 0,1 s (`:2742`), devolvendo 0 quando o ficheiro aparece e 4 quando o prazo
   esgota (`:2736-2743`).

O ficheiro de prontidão é tocado por `mark_launch_ready` `[CODE]` `sotto_webview.py:2700-2722`, que
escreve `ready pid=<pid>` (`:2720`) e poda os `ready-*.txt` com mais de um dia (`:2657-2688`,
`max_age_s=86400.0`). Quem o chama é `_complete_startup` `[CODE]` `:14172-14173` — primeiro
`_STARTUP_READY['done'] = True`, depois `mark_launch_ready(self.args.ready_file)`. O estado de
arranque é da APP e o ficheiro é do largador `[CODE]` `:2642-2656`.

**O caminho `rc=4` medido no log de hoje.** `[MEASURED]` `sed -n '207048,207056p'
_main/webview-run.log` (2026-11-11):

```
2026-11-11 22:56:36.341 sotto: SHELL_STARTUP_STAGE pid=41852 stage=pre-lock python=C:\Program Files\Python311\python.EXE panel=true
2026-11-11 22:56:36.380 sotto: SHELL_CODE_ID sha256=1D027EB01669 files=110
2026-11-11 22:56:36.382 sotto: SINGLE_INSTANCE name=Local\SottoShell already_running=false
2026-11-11 22:56:36.382 sotto: SHELL_JOB_ARMED pid=41852 kill_on_close=true
2026-11-11 22:56:36.437 sotto: PANEL_GEOMETRY_RESTORED surface=panel rect=380x900@(1528,12) writtenAt=2026-11-11T22:56:25-03:00 clamped=false
2026-11-11 22:56:36.437 sotto: panel window created frame=false transparent=true alwaysOnTop=true skipTaskbar=true resizable=false show=false focusable=false engine=WebView2/pywebview
2026-11-11 22:56:36.437 sotto: panel geometry: docked=right work=1920x1032@(0,0) window=380x900@(1528,12) margin=12
2026-11-11 22:56:36.437 sotto: primary display bounds={"x": 0, "y": 0, "width": 1920, "height": 1080} workArea={"x": 0, "y": 0, "width": 1920, "height": 1032} scaleFactor=1.0
sotto: HANG rc=4 by=run.cmd-readiness
```

`[MEASURED]` são as últimas nove linhas do ficheiro: `wc -l _main/webview-run.log` = `207056`, e não
há linha depois. Nessa sessão não existe `CAPTION_PIPELINE_START`, `BRIDGE_SPAWNED` nem
`WEBVIEW2_PROFILE_SWEEP`, porque a cauda acima é o fim do ficheiro `[MEASURED]`. `[MEASURED]`
`tasklist /FI "PID eq 41852"` às 23:29:53 devolve `nenhuma tarefa em execução correspondente aos
critérios especificados`. `[INFERENCE]` a sessão morreu entre a criação da janela e a primeira linha
que `create_window` escreve depois dela (`CAPTION_OVERLAY_MODE`, `:12928`): o `HANG` descreve uma app
que não chegou a `mark_launch_ready`.

## 2. `main()`: a ordem que o código executa

`main()` começa em `[CODE]` `sotto_webview.py:25945`; a ordem real dos passos é esta, e não a ordem
em que os assuntos costumam ser listados:

| # | passo | símbolo | onde | rasto no log |
|---|---|---|---|---|
| 1 | parser da shell | `parse_args` | `:25947` | — |
| 2 | vigia de arranque | `_start_startup_stack_watch` | `:25948` (corpo em `:25900-25943`) | `STARTUP_NOT_READY s=15/30/60` e um despejo para `_main/_startup-stacks.log` |
| 3 | prioridade | `raise_visible_priority` | chamada `:25959`, função `:10237` | `SHELL_PRIORITY was=… now=… raised=…` (`:10260`, `:10266`) |
| 4 | prazo de sonda | dois `threading.Timer` de `--exit-after` (+15 s como rede) | `:25976-25979` | — |
| 5 | ambiente WebView2 | `apply_webview2_environment` | chamada `:25992`, função `:25822` | `WEBVIEW2_ENV` (`:25993`), `WEBVIEW2_BROWSER_ARGS` (`:25998`) |
| 6 | modos que não abrem janela | `--wait-ready` (`:26002-26014`), `--check-args` (`:26016-26050`), `--probe-reload` (`:26052`) | — | `PREFLIGHT_REFUSED` só quando há recusa |
| 7 | abrir o recibo | `_open_log` | `:26058` | `LOG_ROTATED` quando roda |
| 8 | banner | `shell=webview2 pywebview=… python=… pid=` | `:26059` | a primeira linha com data da sessão |
| 9 | identidade da app | `APP_USER_MODEL_ID` | `:26061-26065` | `APP_USER_MODEL_ID value=… ok=…` |
| 10 | painel presente? | `PANEL_HTML` | `:26067-26068` | `PANEL_MISSING path=…` e `return 3` |
| 11 | marcos de arranque | `SHELL_STARTUP_STAGE` | `:26080` | `stage=pre-lock` |
| 12 | identidade do código | `code_identity()` | `:26094` | `SHELL_CODE_ID sha256=… files=…` |
| 13 | autostart | `autostart_install/uninstall/status` | `:26100-26106` | — |
| 14 | instância única | `take_single_instance_lock` | `:26125-26160` | `SINGLE_INSTANCE name=… already_running=…` (`:8701`) |
| 15 | árvore morre com a shell | `_hold_kill_on_close_job` | `:26179`, função `:8597` | `SHELL_JOB_ARMED pid=… kill_on_close=true` (`:8669`) |
| 16 | janelas | `SottoShell(args)` + `create_window()` | `:26185-26186` | `panel window created …` (`:12756`) |
| 17 | detector de jogo | `arm_gaming_watcher` | `:26191` | — |
| 18 | teclas e legenda | `arm_hotkey`, `start_caption_pipeline('pre-webview')` | `:26205`, `:26212` | `CAPTION_PIPELINE_START reason=pre-webview` |
| 19 | vigias opcionais | hot-reload, auto-relançamento, bandeja, clique-fora | `:26270-26312` | `HOT_RELOAD_DISABLED`, `TRAY_DISABLED`, … |
| 20 | perfis mortos | fio `sotto-profile-sweep` + `WEBVIEW2_PROFILE ephemeral` | `:26334-26355` | `WEBVIEW2_PROFILE_SWEEP dirs=… mb=…` |
| 21 | ciclo de eventos | `webview.start(icon=SOTTO_ICON)` | `:26357` | — |

O que esta tabela fixa, e que a lista "mutex, prioridade, ambiente, perfis" não fixa:

- **A prioridade sobe ANTES de existir ficheiro de log.** `[CODE]` a chamada está em `:25959` e o
  `_open_log` só em `:26058`; `log()` só espelha para o ficheiro quando `_LOG_FILE` não é `None`
  `[CODE]` `:2594-2612`. Logo `SHELL_PRIORITY` nunca entra no `--log`. `[MEASURED]` `grep -ac
  "SHELL_PRIORITY" _main/webview-run.log` = `0` (2026-11-11).
- **O ambiente WebView2 sofre do mesmo**, e por desenho: os knobs são lidos quando o ambiente é
  criado, dentro de `create_window`, e têm de estar postos antes `[CODE]` `:25984-25991`.
  `[MEASURED]` `grep -ac "WEBVIEW2_ENV" _main/webview-run.log` = `0`.
- **O mutex é a única guarda que termina a app sem janela.** `[CODE]` `:26154-26158`: se
  `take_single_instance_lock` devolve falso, sai com `warn` e `return 0` — a segunda instância.
- **A largada de MEDIÇÃO leva um nome de mutex derivado.** `[CODE]` `:26125-26152`:
  `measurement_lock_name` (`:8722-8741`) constrói `Local\SottoShell.m.<flags>`; duas sondas com as
  MESMAS flags colidem (`SINGLE_INSTANCE_MEASURE_BUSY`, `:26146`) e duas com flags diferentes correm
  lado a lado `[CODE]` `:8730-8740`.
- **O job object não tem excepção para medição.** `[CODE]` `:26179` está fora de qualquer `if`.
- **A varredura de perfis é o PENÚLTIMO passo.** `[CODE]` `:26333-26355`: corre no fio
  `sotto-profile-sweep` só quando `lock_excuse` é falso, apaga `%TEMP%\tmp*\EBWebView` com mais de
  5400 s (`:11159-11188`) e nomeia o motivo do perfil efémero em `WEBVIEW2_PROFILE ephemeral`
  (`:26353`).

## 3. `create_window`: a janela, o painel e o overlay

`create_window` está em `[CODE]` `sotto_webview.py:12743`. A ordem interna é: geometria guardada, URL
de STAGING, criação da janela, criação do overlay nativo, ligação dos três eventos.

1. **Abre em `stage.html`, não no painel.** `[CODE]` `:12754-12765` — `url = file_url(STAGE_HTML)`
   (`STAGE_HTML` em `:116`). O `preload` registado no handler do host chega DEPOIS da navegação do
   painel, medido como `PRELOAD_ACTIVE hasSotto=false` na primeira leitura `[CODE]` `:12746-12753`.
2. **A janela nasce escondida, transparente e no sítio real.** `[CODE]` `:12765-12805`: `hidden=True`,
   `transparent=not self.args.opaque`, `on_top=True`, `frameless=True`, `min_size=(200, 40)` e o
   `x`/`y` da geometria calculada; criar fora do ecrã quebra o `load` `[CODE]` `:12787-12802`.
3. **A legenda é uma janela Win32, não um WebView2.** `[CODE]` `:12830-12852` (o WebView2 é filho
   opaco e `LWA_COLORKEY` não chega ao conteúdo); o objecto é `caption_overlay.NativeCaptionOverlay`
   `[CODE]` `:12900-12903`, e a criação regista `CAPTION_OVERLAY_CREATED hwnd=… layered=true
   transparent=true noactivate=true` em `app/webview/caption_overlay.py:690-691` `[CODE]`.
4. **O tema é reaplicado na criação.** `[CODE]` `:12913-12930`: `_apply_overlay_theme(stored,
   why='overlay-created')` (`:21291`); sem desenho guardado pede a medida agora por
   `window.SottoBrand.push()` e loga `CAPTION_OVERLAY_THEME_REPLAYED theme=youtube source=default
   why=no-stored-design`, com desenho loga `theme=<nome> source=stored`; em ambos publica
   `CAPTION_OVERLAY_MODE native=true hwnd=… work=AxB` `[CODE]` `:12928-12929`.
5. **A pressão que chegou cedo é honrada aqui.** `[CODE]` `:12931-12948`: se `_caption_show_pending`
   não é `None`, escreve `CAPTION_WINDOW_DEFERRED_APPLIED on=<bool>` (`:12934`), fixa
   `_caption_window_shown` e chama `caption_overlay.show(bool(pending))`; com `on`, arranca o bloqueio
   de estado com `_caption_status_start()` (`:18625`). Sem texto, `show` devolve `False` `[CODE]`
   `caption_overlay.py:1676-1681`.
6. **Os três eventos são ligados no fim.** `[CODE]` `:12972-12974`: `before_show` → `_on_before_show`,
   `loaded` → `_on_loaded`, `closing` → `_on_closing`.

O que fecha o arranque é `_on_loaded` `[CODE]` `sotto_webview.py:14441`: na página `STAGING` troca
para o painel com `load_url(file_url(PANEL_HTML))`; na do painel lê `BRIDGE_PROBE`, publica
`PRELOAD_ACTIVE hasSotto=true methods=…` ou reinstala e recarrega uma vez (`:14453-14466`) e chama
`_complete_startup()` (`:14439`), que toca o ficheiro de prontidão e arranca painel, legenda e worker
`[CODE]` `:14172-14263`.

## 4. O arranque do worker

### 4.1 A tabela de razões, e os seus dois leitores

`_worker_autostart_reason` é estática e pura `[CODE]` `sotto_webview.py:17323`. Devolve uma de cinco
strings, por esta precedência: `'with-worker'` → `'no-worker'` → `'env'` (`SOTTO_NO_WORKER=1`) →
`'measurement-flag(<flag>)'` (`_measurement_flag`) → `'default'` `[CODE]` `:17356-17371`.

| valor | quando | arranca? |
|---|---|---|
| `with-worker` | `--with-worker` presente | sim — autoritativo |
| `no-worker` | `--no-worker` | não |
| `env` | `SOTTO_NO_WORKER=1` | não |
| `measurement-flag(--dump-dom\|--selftest\|--memory\|--no-hotkey\|--exit-after\|--probe-*)` | qualquer flag de `MEASUREMENT_FLAGS` (`:12488-12506`) ou `probe_v2` | não |
| `default` | nada disse o contrário | sim |

A mesma tabela tem um segundo leitor, e é isso que impede duas listas de flags de divergirem: o
arranque da legenda (§6) lê `_measurement_flag` `[CODE]` `:12500-12506`. Quem liga a razão ao acto é
`START_REASONS` `[CODE]` `:17376-17389` (`default`, `with-worker`, `hot-reload`, `revive`,
`panel-open`, `preload`, `external-end`, `vram-resume`) e o primeiro `if` de `start_worker`
`[CODE]` `:17732-17741`: razão fora da tupla escreve `WORKER_AUTOSTART=declined reason=<razão>
by=start_worker` e devolve `False`.

### 4.2 As guardas de `start_worker`, em ordem

`start_worker` começa em `[CODE]` `:17727` e recusa, por esta ordem: razão não autorizada (`:17741`);
shell a sair (`exiting`, `:17760-17762`); bridge já existente (`:17770-17773`,
`cause=already-running`); alvo por app não resolvido (`:17803-17806`, sem construir bridge); motor
quente que responde (`_try_warm_attach`, `:17679`); e só então constrói `WorkerBridge` e chama
`bridge.start(reason)` `[CODE]` `:17836-17868`.

### 4.3 As três linhas de boot

| linha | quem a escreve | o que contém |
|---|---|---|
| `BRIDGE_START reason=… command=… worker=… device=… capture=…` | `WorkerBridge.start` | a intenção, antes de qualquer `Popen` `[CODE]` `:23380-23386` |
| `BRIDGE_SPAWNED pid=… argv=[…] SOTTO_CAPTURE_MODE=… SOTTO_AUDIO_DEVICE=…` | `_spawn`, depois de um `Popen` com sucesso | o argv que CORREU `[CODE]` `:23577-23583` |
| `BRIDGE_LOAD_MS ms=… pid=… worker_load_s=… load_bg_closed_by=…` | `_consume`, no primeiro `state=model-loaded` daquele filho | o tempo do spawn ao grafo carregado `[CODE]` `:23988-23991` |
| `WORKER_BOOT_PROF pid=… boot_prof_s={…} load_phases_s={…}` | a mesma linha de estado, logo a seguir | as fases do arranque do worker `[CODE]` `:24001-24004` |

`boot_prof_s` é medido DENTRO do worker, desde o `import` do módulo, e cobre o que `load_phases_s`
não via (interpretador, `import torch`, CUDA, modelo) `[CODE]` `worker/sotto_worker.py:749-780`,
publicado no payload `model-loaded` (`:7173`); `load_phases_s` são as três sessões (`:7162`).

O ambiente do filho é um contrato fechado: `_child_env` é `dict(os.environ)` + `PYTHONUNBUFFERED=1` +
`SOTTO_CAPTURE_MODE` + `SOTTO_REDUX_WHEN_HIDDEN=1`, e `SOTTO_AUDIO_DEVICE`/`SOTTO_TARGET_PID` só
quando pedidos `[CODE]` `:23397-23438`.

### 4.4 Preload e motor quente

- **Preload.** `WORKER_PRELOAD_DELAY_S = 0.0`, `WORKER_PRELOAD_IDLE_S = 6.0`,
  `WORKER_PRELOAD_MAX_WAIT_S = 120.0` `[CODE]` `:730-736`. `_schedule_preload_worker` arranca um fio
  `sotto-worker-preload` e loga `WORKER_PRELOAD scheduled delay_s=… idle_s=… ceiling_s=…`
  `[CODE]` `:17432-17433`; o corpo espera que o dono esteja quieto (`GetLastInputInfo`,
  `:17436-17466`) e desiste com `reason=worker-already-running` (`:17475`) ou
  `reason=external-captions-on-screen` (`:17486`). `SOTTO_NO_PRELOAD=1` repõe o antigo e escreve
  `WORKER_PRELOAD declined reason=env SOTTO_NO_PRELOAD=1 start=first-panel-open` `[CODE]`
  `:17415-17419`.
- **Quem pede o preload é `_complete_startup`, e só para `reason == 'default'`** `[CODE]`
  `:14236-14263`: os caminhos explícitos e as medições nunca chegam lá.
- **Motor quente.** `_try_warm_attach` corre ANTES de construir `WorkerBridge` `[CODE]`
  `:17679-17728`, com prazo `WARM_ATTACH_DEADLINE_MS = 500` `[CODE]` `:8282`. Falha =
  `WARM_FALLBACK_COLD reason=<porquê>` e a escada fria segue intacta; sucesso seria `WARM_ATTACHED
  reason=… pid=… mode=… load_ms=…` `[CODE]` `:17722-17725`.
- **O que se mediu nesta árvore:** `[MEASURED]` `grep -ac` em `_main/webview-run.log` (2026-11-11) —
  `WARM_FALLBACK_COLD` = `18`, `WARM_ATTACHED` = `0`, `WORKER_PRELOAD` = `0`, `WORKER_AUTOSTART` =
  `33`, `BRIDGE_SPAWNED` = `24`. `[INFERENCE]` o motor quente nunca respondeu nem o preload apareceu
  nas sessões guardadas — consistente com código anterior ao preload.

## 5. O orçamento de arranque, como os oráculos o medem

Os limites não estão no código de produção: `[MEASURED]` `grep -rn "FIRST_CAPTION_BUDGET_MS\|LIMIAR_MS"
app/ worker/` (2026-11-11) devolve **zero linhas** — vivem nos oráculos, que são quem julga.

| oráculo | limiar | o que conta como "legenda pintada" |
|---|---|---|
| `_main/boot-interaction-oracle.py` | `FIRST_CAPTION_BUDGET_MS = 15000.0` `[CODE]` `:68`; `SHOW_BUDGET_MS = 400.0` `[CODE]` `:65`; `LIVE_BUDGET_MS = 400.0` `[CODE]` `:66` | a primeira das cinco `PAINT_WITNESSES` `[CODE]` `:148-155`, a mais antiga em TEMPO: `CAPTION_PAINT_SURFACE`, `CAPTION_PAINT `, `CAPTION_PAINT_LAG`, `CAPTION_OVERLAY_LAG`, `CAPTION_PROVISIONAL_PAINT` |
| `_main/time-to-first-caption-oracle.py` | `LIMIAR_MS = 3000` `[CODE]` `:90` | `CAPTION_PAINT` (regex com espaço, `:119`) ou `YOUTUBE_TRACK_PAINT` com `painted_words>0`; placeholders não contam `[CODE]` `:95-101` |

A sessão em julgamento é sempre a ÚLTIMA: `session_lines` corta o log na última `SHELL_STARTUP_STAGE
... stage=pre-lock` `[CODE]` `boot-interaction-oracle.py:97-105`; sem sessão o veredicto é SKIPPED,
nunca PASS `[CODE]` `:100-105`.

**Medições de hoje, com o comando e a saída.** `[MEASURED]` (2026-11-11):

```
$ python _main/boot-interaction-oracle.py --json
BOOT-INTERACTION SKIPPED reason=stale-process live=LIVE_CODE STALE log=H:\sotto\_main\webview-run.log

$ python _main/time-to-first-caption-oracle.py --json
{ "shell_pid": 41852, "start": "2026-11-11 22:56:36.341000",
  "first_paint": null, "limit_ms": 3000, "elapsed_ms": null, "verdict": "SKIPPED" }
```

`[MEASURED]` o braço de pintura do mesmo oráculo, que julga dois FICHEIROS de forma e não abre nada:

```
$ python _main/boot-interaction-oracle.py --paint-arm
paint-arm RED fixture=boot-interaction-altc-paint-slow.log rc=1 verdict=FAIL alt-c 1o: pintura=3142.0 budget=400
paint-arm GREEN fixture=boot-interaction-altc-paint-fast.log rc=0 verdict=PASS alt-c 1o: pintura=364.0 budget=400
paint-arm MUTACAO fixture=mutacao-do-consero rc=1 verdict=FAIL alt-c 1o: pintura=3142.0
PAINT-ARM: PASS -- red=FAIL green=PASS mutacao=FAIL
```

As duas fixtures são logs de forma: o braço prova o juiz, não o arranque do `HEAD` `[INFERENCE]`.

**Números históricos.** `[MEASURED]` recibo `_main/receipt-20261111-live-start-latency.md` §1 e §4,
sessão pid 49180 de 2026-11-11 17:34:20: arranque → primeira pintura **102 110 ms** contra o
orçamento de 15 000 ms (`BOOT-INTERACTION VERDICT: FAIL`), e `BRIDGE_LOAD_MS ms=15109` na mesma
sessão. `[MEASURED]` recibo `_main/receipt-20261111-boot-and-park.md` §1, sessão pid 21400 de
2026-11-11 00:48:42: primeira legenda **59 016 ms** depois do arranque, `BRIDGE_LOAD_MS ms=6969`, com
o worker a nascer a 00:48:42.483 e a legenda a sair a 00:49:41.295. `[MEASURED]` o docstring de
`time-to-first-caption-oracle.py:5-8` cita 2026-11-04 como `65 s` entre `SHELL_STARTUP_STAGE
09:57:24.323` e `CAPTION_PAINT 09:58:29.360`. Nenhum destes números foi produzido pelo código de hoje.

## 6. A decisão da legenda no arranque (ordem do dono, 2026-11-11)

A regra é uma função pura, e é ela — não o ficheiro de estado — que decide se a legenda nasce ligada:
`caption_wanted_at_start(args, stored=None, env=None)` `[CODE]` `sotto_webview.py:21508`.

| precedência | condição | resultado | evidência |
|---|---|---|---|
| 1 | `SOTTO_CAPTION_WANTED_DEFAULT` em `('0','1')` | `on = (raw == '1')`, razão `env(SOTTO_CAPTION_WANTED_DEFAULT=N)` | `[CODE]` `:21540-21543`, constante `:21505` |
| 2 | `SOTTO_LANE_LAUNCH=1` | `False`, razão `lane(SOTTO_LANE_LAUNCH=1)` | `[CODE]` `:21547-21548` |
| 3 | `_measurement_flag(args)` devolve flag | `False`, razão `measurement-flag(<flag>)` | `[CODE]` `:21549-21551` |
| 4 | nada acima | `True`, razão `default` | `[CODE]` `:21552` |

`MEASUREMENT_FLAGS` tem oito entradas — `--dump-dom`, `--selftest`, `--memory`, `--no-hotkey`,
`--exit-after`, `--probe-stats`, `--probe-outside-click`, `--probe-edit-mode` `[CODE]`
`:12488-12497` — e `_measurement_flag` acrescenta `--probe-v2` quando `probe_v2 > 0` `[CODE]`
`:12503-12505`.

O ficheiro continua a ser lido, mas deixou de mandar: `_caption_wanted_at_start` abre
`_main/caption-wanted.json` (`CAPTION_WANTED_PATH`, `:21500-21502`), lê `on`/`at`, chama a função pura
e escreve as duas linhas auditáveis `[CODE]` `:21554-21576`:

- `CAPTION_WANTED_START on=<bool> reason=<razão> stored=<none|true|false> stored_at=<iso>`
  `[CODE]` `:21566-21568`;
- `CAPTION_WANTED_START_OVERRIDES stored=false -- o arranque liga a legenda (ordem do dono,
  2026-11-11: "as soon as i open it, should start the subtitles")`, só quando o gravado é `false` e a
  decisão é `true` `[CODE]` `:21569-21573`.

O consumidor é `create_window`: `self._caption_wanted = self._caption_wanted_at_start()` e, quando é
verdade, `self._caption_show_pending = True` `[CODE]` `:12892-12898` — o pedido de pixels que o bloco
`CAPTION_WINDOW_DEFERRED_APPLIED` (§3, passo 5) aplica. O interruptor grava sempre o estado da sessão
em `caption-wanted.json` (`_caption_wanted_store`, `:21576-21589`): o ficheiro é registo, não contrato.

**O veredicto medido, hoje.** `[MEASURED]` `python _main/caption-wanted-default-oracle.py`
(2026-11-11) — 21 arms, nenhuma arranca a app:

```
A1 sem flags -> liga                         PASS on=True reason=default
A2 --dump-dom -> nao liga                    PASS on=False reason=measurement-flag(--dump-dom)
A4b lane -> nao liga                         PASS on=False reason=lane(SOTTO_LANE_LAUNCH=1)
A7 stored=false -> liga mesmo assim          PASS on=True
A7 log nomeia o override                     PASS CAPTION_WANTED_START on=true reason=default stored=false stored_at=2026-11-11T17:41:48 | CAPTION_WANTED_START_OVERRIDES ...
A10 create_window le a decisao nova          PASS assign=True
A10 create_window arma os pixels quando liga PASS pending=True
A11 o interruptor nao toca motor/worker      PASS encontrado=-
VERDICT: PASS -- 21/21 arm(s)
```

`[MEASURED]` a mesma verificação no log real: `grep -ac "CAPTION_WANTED_START" _main/webview-run.log`
= `0` (2026-11-11). `[INFERENCE]` nenhuma largada real correu este código: a decisão está provada por
oráculo e ainda não foi vista num processo do dono.

## Lacunas

- `[UNKNOWN]` **Quanto custa o arranque do `HEAD`.** O processo vivo é anterior ao código
  (`LIVE_CODE STALE`) e o log não tem sessão do `HEAD` com pintura; fechar exige uma largada real e
  depois `python _main/boot-interaction-oracle.py --json` e
  `python _main/time-to-first-caption-oracle.py --json` sobre o log novo.
- `[UNKNOWN]` **Onde a sessão das 22:56 parou.** O log termina nas linhas de criação da janela e o pid
  já não existia às 23:29:53; sem a pilha dessa sessão não se sabe se bloqueou `webview.create_window`
  ou o arranque do WebView2. Fechar exige `_main/_startup-stacks.log` dessa largada ou um
  `STARTUP_NOT_READY` com despejo, que o ficheiro não tem.
- `[UNKNOWN]` **A atribuição das fases do worker numa sessão do `HEAD`.** `WORKER_BOOT_PROF` e
  `load_phases_s` existem no código e no payload, mas nenhum valor desta árvore foi lido nesta
  campanha; fechar exige uma sessão viva e `grep "WORKER_BOOT_PROF" _main/webview-run.log`.
- `[UNKNOWN]` **A taxa de attach do motor quente.** `WARM_ATTACHED` = 0 no log guardado, mas o
  ficheiro roda aos 64 MB e as sessões antigas foram descartadas — o zero pode ser do ficheiro, não do
  produto. Fechar exige três arranques seguidos com `grep -c WARM_ATTACHED/WARM_FALLBACK_COLD`.
- `[UNKNOWN]` **O tempo entre o `start ""` do `run.cmd` e a primeira linha do log.** O wrapper não
  carimba o `start` e o `HANG` é acrescentado sem data; fechar exige um carimbo no wrapper ou a data
  de criação do `ready-*.txt`.
- `[UNKNOWN]` **Onde a página gasta os 59-671 ms antes da primeira linha do `panel.js`.**
  `_main/receipt-20261110-boot-where.md` §2 mede a variação em oito corridas e §5 declara a atribuição
  por ficheiro `UNMEASURED`; fechar exige `PANEL_BOOT_PROFILE` de uma sessão real com marcos.
