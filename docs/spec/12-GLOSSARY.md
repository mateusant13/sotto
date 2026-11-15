# 12 — GLOSSÁRIO: cada termo, cada tag, cada ficheiro

Este ficheiro é o dicionário dos outros onze. Responde a três perguntas que os documentos de
comportamento usam sem explicar: **que palavra é esta**, **que linha de log é esta**, **que ficheiro
é este**. Tudo o que aqui está foi medido nesta campanha (2026-11-11) com o comando que acompanha o
número; quando um termo só se pode descrever pelo código, a referência é `ficheiro:linha` lida.

## 1. Como os números deste ficheiro foram produzidos

| o quê | comando | resultado |
|---|---|---|
| tags distintas no produto | o script da caixa abaixo, sobre `app/webview/*.py` + `worker/*.py` | **793** tags, **89** famílias, **77** ficheiros `[MEASURED]` 2026-11-11 |
| tags distintas no log vivo | `grep -oE 'sotto: [A-Z][A-Z0-9_]+' _main/webview-run.log \| sed 's/^sotto: //' \| sort -u \| wc -l` | **273** `[MEASURED]` 2026-11-11 |
| cobertura do scanner | comparação dos dois conjuntos acima | **250** das 273 estão no fonte; **23** não `[MEASURED]` |
| tamanho do log | `wc -l _main/webview-run.log` | **207 056** linhas, **25 439 116** B `[MEASURED]` |
| passos da bateria | `grep -cE "^[[:space:]]*call :step " _main/_audit-verify-all.cmd` | **476** `[MEASURED]` |
| classes de passo | `grep -cE "call :step heavy "` / `:skipped` / `:expectred` / `:record` / `always` | 12 / 16 / 204 / 249 / 180 `[MEASURED]` |
| oráculos e gates | `ls _main/*oracle*.py` / `ls _main/*gate*.py` / `ls _main/*.py` | 280 / 28 / 723 `[MEASURED]` |
| instrumentos com `--neg-arm` | `grep -rlE "\-\-neg-arm" _main/*.py \| wc -l` | **303** `[MEASURED]` |
| recibos e logs da bateria | `ls _main/receipt-*.md` / `ls _main/_audit-verify/*.log` | **414** / **543** `[MEASURED]` |
| histórico | `find history -name "*.md" \| wc -l` / `du -sh history` | **24** ficheiros, **72 M** `[MEASURED]` |

Os 23 tags que o scanner não apanha não são um mistério: são os que nascem de uma literal separada
da chamada (`log_repeat('bridge-alive', 'BRIDGE_ALIVE …')`, `log('HANG …')` construído por
concatenação, `_write_stdout`). O conjunto medido no log é a prova de que existem; o scanner é o
inventário de quem os escreve.

O scanner, executado a partir de `H:/sotto` (reproduz os 793/89):

```python
import re, pathlib, collections
p1 = re.compile(r"(?:^|[^\w])(?:[A-Za-z_]\w*\.)*(?:log|warn|log_repeat|log_fn|_log|_emit_log|emit|log_line)\(\s*f?['\"]([A-Z][A-Z0-9_]{2,})", re.S)
p2 = re.compile(r"(?:sys\.stderr\.write|(?:^|[^\w])print)\(\s*f?['\"]([A-Z][A-Z0-9_]{2,})", re.S)
tags, owner = set(), collections.defaultdict(set)
files = sorted(set(pathlib.Path('.').glob('app/webview/*.py')) | set(pathlib.Path('.').glob('worker/*.py')))
for f in files:
    t = f.read_text(encoding='utf-8', errors='replace')
    s = {m.group(1) for m in p1.finditer(t)} | {m.group(1) for m in p2.finditer(t)}
    tags |= s
    owner['shell' if str(f).startswith('app') else 'worker'] |= s
print(len(files), len(tags), len(collections.Counter(k.split('_')[0] for k in tags)),
      len(owner['shell']), len(owner['worker']), sorted(owner['shell'] & owner['worker']))
# 77 793 89 732 63 ['SELFTEST', 'VERDICT']
```

## 2. TERMOS

| termo | o que é no código | evidência |
|---|---|---|
| **shell** | `class SottoShell`, o processo que o dono vê; 26 362 linhas | `[CODE] app/webview/sotto_webview.py:12512`; `[MEASURED] wc -l` |
| **worker** | `worker/sotto_worker.py`, processo separado `BELOW_NORMAL`, sem `stdin`, fala JSONL por `emit()` | `[CODE] worker/sotto_worker.py:1001`; `docs/spec/01-ARCHITECTURE.md` §4.1 |
| **bridge** | `class WorkerBridge` (spawn + leitura JSONL) e `class WarmPipeBridge` (attach ao motor quente) | `[CODE] app/webview/sotto_webview.py:23047,24740` |
| **tap** | a captura de áudio. Há dois: o *tap global* (rung (a), WASAPI loopback do endpoint) e o *tap por processo* (`INCLUDE_TARGET_PROCESS_TREE`, escolhido por NOME e re-escolhido quando o pid morre) | `[CODE] worker/wasapi_loopback.py:1`; `worker/process_target.py:2-8` |
| **rung / ladder** | a escada de candidatos de dispositivo: *rung* é a CLASSE do candidato — `(a)` WASAPI loopback, `(b)` heurística de nome / PortAudio; a *ladder* é a lista ordenada e sem duplicados que os percorre | `[CODE] worker/wasapi_loopback.py:1554,1579`; `worker/sotto_worker.py:2612` (`device_candidates`) |
| **rung vs attempt** | o *attempt* é o índice da tentativa dentro da escada (`attempt=3/11`); o *rung* é a classe do dispositivo dessa tentativa. Uma rotação de endpoint gasta attempts, não rungs | `[CODE] worker/sotto_worker.py:2608` (`LADDER_TRY attempt=%d/%d … api=…`) |
| **park** | parquear = libertar o motor sem perder o pedido: `set_engine_park(reason)`, com razões `captions`/`vram`; a shell só publica o pedido, quem para é o worker | `[CODE] app/webview/sotto_webview.py:19698,19702,19742` |
| **shed / shedding** | baixar de nível de motor por carga medida: `leve` (tudo), `alta` (nemotron off, parakeet on), `muito alta` (parakeet off também). Áudio nunca é a coisa largada | `[CODE] app/webview/load_shedding.py:31-37,47` |
| **route** | a decisão de PINTAR: `redux-batch` nunca pinta; rota `player` suprime a local; senão a idade decide (`age_s <= LIVE_MAX_AGE_S`); sem idade a linha pinta e conta-se `LIVE_ROUTE_UNKNOWN_AGE` | `[CODE] worker/live_route.py:1-30`; `worker/sotto_worker.py:1001,1025` em `emit` chama `live_route.admit` |
| **partial** | linha ainda aberta: `final=false`, `kind='partial'`; pode ser reescrita | `[CODE] app/webview/sotto_webview.py:12117`; `19444` |
| **final** | linha fechada pelo produtor (`final=true`); com o áudio em silêncio fecha minutos depois, por isso idade grande numa `final` é projecto, não atraso | `[CODE] app/webview/sotto_webview.py:19410-19418,19458` |
| **stable** | campo do worker por `CAPTION_IN`: a linha não tem cauda aberta — a última palavra está provada pelo tokenizador (`▁`) | `[CODE] app/webview/sotto_webview.py:19444`; `worker/stable_words.py:22-38` |
| **warm engine** | processo do Task Scheduler que já tem o grafo carregado; a shell só se LIGA a ele (named pipe + mutex + `_main/warm-engine.pid`) | `[CODE] app/webview/warm_engine.py:1-30,95` |
| **preload** (duas coisas) | (1) `PRELOAD_INSTALLED` = o *bootstrap* JS que o WebView2 instala em cada documento criado; (2) o *preload* do motor = carregar 1,9 GB antes de ser preciso, vetado por G1..G4 (`unknown` não é permissão) | `[CODE] app/webview/sotto_webview.py:14022`; `app/webview/warm_engine.py:32-38` |
| **surface** | o nome da única página que veste dois layouts: `strip` ou `panel`, recusando qualquer outro | `[CODE] app/webview/sotto_webview.py:7421`; `app/panel/surface.js:35` |
| **strip** | a faixa de legendas (surface `strip`); a sua altura/largura são lidas do CSS e do DOM com fallback declarado | `[CODE] app/webview/sotto_webview.py:7416-7427,7470` |
| **overlay** | a janela Win32 em camada própria (`WS_EX_LAYERED`+`ULW_ALPHA`), desenhada por GDI+, sem WebView2 e sem color key | `[CODE] app/webview/caption_overlay.py:1-29,535` |
| **plate** | a placa atrás das palavras; `tight` (abraça a linha medida) ou `normal` | `[CODE] app/webview/caption_overlay.py:516`; `app/webview/caption_settings.py:28` |
| **visual** | o par persistido `{opacity, plate}` da legenda nativa; `opacity` escala placa/régua/LED, nunca a tinta do texto | `[CODE] app/webview/caption_settings.py:3-11,49` |
| **skin** | o pacote de aspecto exportado para o painel: `window.SOTTO_SKINS` (lido uma vez no parse) | `[CODE] app/webview/sotto_webview.py:194`; `app/panel/skins/skins.js:8` |
| **theme** | o CSS de tema do painel (9 ficheiros em `app/panel/themes/`) e, no overlay, o dicionário de tokens que `_normalise_theme` valida | `[MEASURED] ls app/panel/themes/*.css` = 9; `[CODE] app/webview/overlay_paint.py:356` |
| **provenance** | o sufixo HTML `<!-- route=… start=… reason=… -->` que o escritor põe no fim da linha do histórico; vocabulário fechado `('final','provisional-draft','batch')` | `[CODE] app/webview/sotto_webview.py:866-870,15394` |
| **context token** | o `ctx1=<token>` do mesmo sufixo: cinco campos (`sourceApp`, `audioSource`, `viewingApp`, `viewingTitle`, `viewingUrl`) comprimidos em ~12 bytes, tecto 512 chars | `[CODE] app/webview/history_context.py:39-49`; `app/webview/sotto_webview.py:15419` |
| **spool** | o áudio `float32` cru que espera: o do worker em `%TEMP%\sotto-pending-audio-<pid>` e a fila de lote em disco (um manifesto JSON por bloco + o cru ao lado) | `[CODE] app/webview/batch_queue.py:13-14,24`; `worker/audio_ring.py:286` |
| **journal** | série escrita em disco para que uma afirmação seja uma data: o *tap journal* por endpoint (`endpoint-signal.json`) e a linha por minuto `BRIDGE_WORKER_COST` no log | `[CODE] worker/wasapi_loopback.py:596`; `app/webview/cost_watchdog.py:14,22` |
| **oracle** | instrumento que julga comportamento sem abrir janela nem dispositivo; 280 em `_main/` | `[MEASURED] ls _main/*oracle*.py \| wc -l` = 280 |
| **negative arm** | a metade que prova o detector: muta uma cópia e exige que o selftest CAIA; a convenção da casa é `--neg-arm` sair **1** ao apanhar, porque o passo declara `expect-rc=1` | `[CODE] _main/_battery-plan.py:459-464` |
| **ratchet** | tecto que só pode descer: o total da bateria não cresce mais de `RATCHET_PCT` sobre o baseline e nenhum passo passa de `SOTTO_STEP_DEADLINE_S` sem dívida declarada | `[CODE] _main/battery-budget-oracle.py:1,14-17` |
| **pin** | um número (tamanho/sha) escrito num documento e conferido por portão contra a medição viva; o pin da bateria é `360331 B / 4165 CRLF / 0 bare LF` | `[CODE] _main/agents-md-pins-oracle.py:1-3` |
| **battery** | `_main/_audit-verify-all.cmd`: 476 passos, agrega rc, falha se QUALQUER passo ficar vermelho | `[CODE] _main/_audit-verify-all.cmd:1-31`; `[MEASURED]` contagem acima |
| **step class** | a marca que diz como o passo se julga: `gate` (rc=0), `control` (tem de apanhar a cópia partida), `skipped` (arma que o ambiente pode tornar incómoda; nunca conta em `gate=`), `expect-red` (vermelho por desenho, tem de sair 1) e a marca `heavy` (não é veredicto: declara que abre o mundo do dono e só corre com `SOTTO_BATTERY_HEAVY=1`) | `[CODE] _main/_audit-verify-all.cmd:29-63` |
| **receipt** | o recibo de uma corrida em `_main/receipt-*.md`; 414 ficheiros | `[MEASURED] ls _main/receipt-*.md \| wc -l` |
| **mutant** | cópia deliberadamente estragada usada como braço negativo: as `_main/_redux-gate-mutants/` e as cópias congeladas `worker/_prefix_audioflag.py` / `worker/_sotto_worker_agcinert.py` | `[MEASURED] ls _main/_redux-gate-mutants`; `[CODE] _main/_battery-plan.py:459` |

## 3. TAGS

Forma de uma linha de log, lida em `log()`: `{stamp} sotto: {TAG} {k=v}…` `[CODE]
app/webview/sotto_webview.py:2594-2615`. O worker escreve a sua parte por `emit()` (JSONL) e por
`stderr`, e a shell republica-a com o prefixo `WORKER ` `[CODE] app/webview/sotto_webview.py:23778`.

### 3.1 Por dono

| dono | tags | nota |
|---|---|---|
| shell (`app/webview/*.py`) | **732** | inclui overlay, painéis, hotkey, youtube, bridge |
| worker (`worker/*.py`) | **63** | 13 são palavras de selftest/CLI (`PARITY`, `SKIP`, `NEG`, `MISSING`, `BUILT`, `TEXT`, `REFUSED`, `FIXTURE`…), não tags de comportamento |
| ambos | 2 | `SELFTEST`, `VERDICT` — palavras de selftest, não tags de comportamento `[MEASURED]` |
| famílias | **89** | as maiores: `CAPTION`=82, `PANEL`=72, `YOUTUBE`=66, `BRIDGE`=54, `WARM`=44, `HOTKEY`=43, `TRAY`=32, `REDUX`=27, `HOT`=24, `STRIP`=23, `BATCH`=23, `EXTERNAL`=19, `UI`=17, `AUDIO`=15 `[MEASURED]` |

### 3.2 Bridge e processo

| tag | o que diz | evidência |
|---|---|---|
| `BRIDGE_SPAWNED` | o worker nasceu: pid e contrato do arranque | `[CODE] sotto_webview.py:23577` |
| `BRIDGE_LOAD_MS` | quanto custou ler os pesos (`model-loaded`) | `[CODE] sotto_webview.py:23988` |
| `BRIDGE_EXIT` | o filho morreu: `rc`, `killed` | `[CODE] sotto_webview.py:24406` |
| `BRIDGE_DEATH_CAUSE` | a frase da morte (cano partido incluído) | `[CODE] sotto_webview.py:24415` |
| `BRIDGE_RESTART_SUPPRESSED` | a escada RECUSOU relançar: `reason`, `ladder=…` | `[CODE] sotto_webview.py:24524` |
| `BRIDGE_ALIVE` | batimento do worker, com `seq`/`phase`/`age_ms` | `[CODE] sotto_webview.py:23699` |
| `BRIDGE_CAPTION_SENT` | a ponte entregou (amostrada 1 em 20; `final` sai sempre) | `[CODE] sotto_webview.py:19426` |
| `BRIDGE_MALFORMED` | linha que não é JSON válido | `[CODE] sotto_webview.py:23871` |
| `BRIDGE_UNKNOWN_KIND` | mensagem JSON de tipo desconhecido | `[CODE] sotto_webview.py:11986` |
| `BRIDGE_RSS` | custo de memória do filho | `[CODE] sotto_webview.py:23767` |
| `BRIDGE_STATS_PUSH` / `BRIDGE_METER` | séries de stats/medidores (não uma linha por amostra) | `[CODE] sotto_webview.py:20565,23835` |
| `BRIDGE_GATE=GREEN\|RED` | veredicto do portão do arranque: no RED leva `reasons=`, no GREEN `hasPanelElement`/`url` | `[CODE] sotto_webview.py:22107-22110` |
| `EMIT_PIPE_DEAD` | o worker escreveu num cano sem leitor e saiu 0 | `[CODE] worker/sotto_worker.py:1032` |

### 3.3 Legenda e pintura

| tag | o que diz | evidência |
|---|---|---|
| `CAPTION_IN` | o contrato de chegada: `start/end/final/stable/tap_ms/age_ms` | `[CODE] sotto_webview.py:19444` |
| `CAPTION_APPLIED` | a linha foi aplicada ao painel/overlay, com `kind` | `[CODE] sotto_webview.py:12115` |
| `CAPTION_ARRIVAL_BLOWN` | a idade na CHEGADA passou o orçamento (só a via viva julga) | `[CODE] sotto_webview.py:19461` |
| `CAPTION_PROVISIONAL_PAINT` | o painel pintou um parcial | `[CODE] sotto_webview.py:12141` |
| `CAPTION_OBSERVED` | texto observado antes de decidir rota | `[CODE] sotto_webview.py:15066` |
| `CAPTION_OVERLAY_DROP` | o overlay recusou pintar (ex.: fonte externa manda) | `[CODE] sotto_webview.py:18916` |
| `CAPTION_DROP_EPOCH` | linha de uma época antiga de captura descartada | `[CODE] sotto_webview.py:18319` |
| `CAPTION_OVERLAY_MODE` | overlay nativo ligado, com `hwnd` | `[CODE] sotto_webview.py:12928` |
| `CAPTION_FRAME_LIMIT` | o tecto de 240 Hz limitou o pedido ao custo medido da pintura | `[CODE] caption_overlay.py:994` |
| `CAPTION_LOADING_TEXT_WITHHELD` | `carregando modelo…` retido porque o player manda | `[CODE] sotto_webview.py:18872` |
| `STATUS_APPLIED` | um `status` do worker virou texto de painel | `[CODE] sotto_webview.py:12168` |

### 3.4 YouTube e fonte externa

| tag | o que diz | evidência |
|---|---|---|
| `YOUTUBE_TICK_MS` | custo de um tick: `avg/max/n/src/vid/cdp_age_ms/rows/why` | `[CODE] sotto_webview.py:4181` |
| `YOUTUBE_LOOP_HZ` | o laço externo: `ticks/ok/none/age_ms/hz/src_reads/src_errs` | `[CODE] sotto_webview.py:5194` |
| `YOUTUBE_CDP_SOURCE` | estado do attach ao CDP | `[CODE] sotto_webview.py:5056` |
| `YOUTUBE_CDP_HEALTH` | idade e contadores da leitura CDP | `[CODE] sotto_webview.py:5229` |
| `YOUTUBE_CLOCK_HELD` | linha do relógio do player com `t/served/floor` | `[CODE] sotto_webview.py:5429` |
| `YOUTUBE_TRACK_PAINT` | cue do player pintada, com `match` | `[CODE] sotto_webview.py:3739` |
| `YOUTUBE_PAINT_STALE` | pintura com idade acima do aceitável | `[CODE] sotto_webview.py:5962` |
| `YOUTUBE_PAINT_READ_FAILED` | a leitura para pintar falhou | `[CODE] sotto_webview.py:4984` |
| `YT_FRAME` | um retrato do DOM do player (`rows`, `lines`) | `[CODE] sotto_webview.py:6777` |
| `EXTERNAL_CAPTIONS_WATCH` | o watcher arrancou, com intervalo | `[CODE] sotto_webview.py:4036` |
| `EXTERNAL_CAPTIONS_READ_STATS` | custo da leitura externa (`mean/p95`) | `[CODE] sotto_webview.py:4064` |
| `EXTERNAL_CAPTIONS_ENGINE_PARKED` | o motor local foi parqueado porque a fonte externa manda | `[CODE] sotto_webview.py:19737` |
| `EXTERNAL_OWNER` | a POSSE do ecrã mudou de dono: `owner/previous/reason/had_line/episode/active` mais `suppressed_episode` (linhas locais perdidas NO episódio que acaba de terminar) e `suppressed_total` (o total da vida). Uma linha por TRANSIÇÃO, nunca por legenda | `[CODE] sotto_webview.py:19615` |
| `ASR_PAINT_REFUSED` | uma linha do microfone foi recusada porque o player manda no ecrã: `episode/suppressed` — e ela é **descartada**: não vai ao ecrã nem ao histórico (`10-DEFECTS.md` §D-23). Um aviso por episódio, não por linha | `[CODE] sotto_webview.py:19651` |
| `CAPTION_WANTED_START` | a decisão do arranque sobre ligar a legenda: `on/reason/stored/stored_at` (D-02; o ficheiro guardado não vence o arranque e o desacordo vai para `CAPTION_WANTED_START_OVERRIDES`) | `[CODE] sotto_webview.py:21931` |

### 3.5 Painel, faixa, hotkey, bandeja

| tag | o que diz | evidência |
|---|---|---|
| `PANEL_VISIBILITY_WRITER` | o fio que publica visibilidade arrancou | `[CODE] sotto_webview.py:11641` |
| `PANEL_HIDDEN` | painel escondido, com `reason` | `[CODE] sotto_webview.py:16497` |
| `PANEL_GEOMETRY_CLAMPED` | a geometria pedida foi presa à área de trabalho | `[CODE] sotto_webview.py:20772` |
| `PANEL_EDIT_GEOMETRY_SAVED` | o arrasto de edição gravou a geometria | `[CODE] sotto_webview.py:20137` |
| `PANEL_LAZY_GATE_ARMED` | o portão de carregamento lazy do painel ficou armado | `[CODE] sotto_webview.py:14067` |
| `STRIP_HEIGHT_FALLBACK` | a altura da faixa caiu no valor declarado | `[CODE] sotto_webview.py:7470` |
| `HOTKEY_TOGGLE` | um passo do ciclo dos painéis (`step=hide`) | `[CODE] sotto_webview.py:16727` |
| `HOTKEY_COALESCED` | pressões engolidas por já haver um dreno a correr | `[CODE] sotto_webview.py:16690` |
| `HOTKEY_FALLBACK` | a tecla pedida não pôde ser registada e caiu noutra | `[CODE] sotto_webview.py:10447` |
| `HOTKEY_GESTURE_FAILED` | o gesto (painéis/live) falhou ao executar | `[CODE] sotto_webview.py:8550` |
| `HOTKEY_PANELS_DISABLED` | painéis desligados pelas settings, com `requested` | `[CODE] sotto_webview.py:10358` |
| `TRAY_HOTKEY` | menu da bandeja pediu o hotkey | `[CODE] sotto_webview.py:17178` |
| `UI_WATCHDOG_STRIKE` | o Windows não respondeu: `strike`, `hwnd`, `kind` | `[CODE] sotto_webview.py:13263` |

### 3.6 Motor, carga, execução

| tag | o que diz | evidência |
|---|---|---|
| `WARM_ATTACHED` | a shell ligou-se ao motor quente (`load_ms`) | `[CODE] sotto_webview.py:17722` |
| `WARM_FALLBACK_COLD` | desistiu e arrancou a frio, com razão | `[CODE] sotto_webview.py:17712` |
| `WARM_REPLAY_TO_HISTORY` | linha reenviada foi para o histórico e não para o ecrã | `[CODE] sotto_webview.py:19399` |
| `WORKER_PRELOAD` / `WORKER_AUTOSTART=declined` | o arranque do worker foi preparado ou recusado com razão | `[CODE] sotto_webview.py:17416,17741` |
| `VRAM_GUARD_PARKING` | o vigia de VRAM vai parquear, com `free_mb` | `[CODE] sotto_webview.py:19750` |
| `LOAD_ACTION_STARTED` | a acção de carga ficou armada (amostras/piso) | `[CODE] sotto_webview.py:13555` |
| `REDUX_SHEDDING` | nível publicado vs medido, motores ligados, porquê | `[CODE]` log vivo, `_main/webview-run.log` 2026-11-09 05:28 |
| `REDUX_ENGINE_LOAD` | carga do motor de fundo com `load_s`/`rss_mb` | `[CODE]` log vivo, 2026-11-08 18:32 |
| `REDUX_BATCH_FAILED` | lote falhou e DEVOLVE o áudio, com backoff | `[CODE] worker/engine_policy.py:441-457` |
| `LADDER_TRY` | um candidato da escada: `attempt/…/ms/retries/result` | `[CODE] worker/sotto_worker.py:2608` |
| `LIVE_ROUTE_REFUSED` / `LIVE_ROUTE_UNKNOWN_AGE` | a rota recusou pintar / pintou sem idade | `[CODE] worker/live_route.py:1-30` |

### 3.7 Histórico, shell, arranque

| tag | o que diz | evidência |
|---|---|---|
| `HISTORY_APPEND_FAILED` | a escrita do histórico falhou (o caminho vai no log) | `[CODE] sotto_webview.py:15845` |
| `HISTORY_LINE_MERGED` | a linha foi fundida na anterior (`path/time/bytes`) | `[CODE] sotto_webview.py:15853` |
| `HISTORY_PRUNE` | retenção aplicada (`removed/keep_h/oldest`) | `[CODE] sotto_webview.py:15924` |
| `SHELL_STARTUP_STAGE` | marco do arranque (`stage=pre-lock`…) | `[CODE] sotto_webview.py:26080` |
| `SHELL_JOB_ARMED` | job object com `KILL_ON_JOB_CLOSE` armado | `[CODE] sotto_webview.py:8669` |
| `SHELL_RELAUNCH_ARMED` | relançamento próprio armado, com tecto por hora | `[CODE] shell_relaunch.py:316` |
| `SHELL_EXIT` | saída da shell com `rc` e `reason` | `[CODE] sotto_webview.py:17251` |
| `SINGLE_INSTANCE_MUTEX_FAILED` | a mutex da instância única não pôde ser criada | `[CODE] sotto_webview.py:8694` |
| `WORKER_PAUSED` | worker parado por política (`reason`) | `[CODE] sotto_webview.py:21729` |
| `THREAD_CPU` | censo de CPU por fio do próprio processo | `[CODE] sotto_webview.py:2542` |

### 3.8 Worker

As 63 tags do worker medem-se com o mesmo scanner sobre `worker/*.py`. As famílias são `AUDIO_`
(15: spool, recorder, ring, over-cap, low-disk), `REDUX_` (27: batch, engine, shedding, switch,
fuse), e as soltas `LIVE_ROUTE_OWNER`, `OPEN_RETRY_RETRY`, `ENDPOINT_UNDESCRIBED`,
`WORKER_THREAD_PLAN`, `EMIT_PIPE_DEAD` `[MEASURED]`. Treze das 63 são saída de selftest/CLI e não
tags de comportamento (`PARITY`, `SKIP`, `NEG`, `MISSING`, `BUILT`, `TEXT`, `REFUSED`, `FIXTURE`,
`VERDICT`, `SELFTEST`, `RECOGNISED`, `UNIFIED_JSON`, `UNIFIED_TEXT`).

## 4. FICHEIROS

| caminho | escritor | leitor | schema / contrato |
|---|---|---|---|
| `_main/panel-visibility.json` | shell, `publish_panel_visibility` + o fio de 3 s | worker, `warm_engine` | `schema: sotto.panel-visibility/1`; `visible` MEDIDO; `staleAfterSeconds: 9.0`; falha para `visible=true` `[CODE] sotto_webview.py:815-816,15292` `[MEASURED] cat` |
| `_main/panel-state.json` | shell (`panel_state.py`) | instrumentos, `panel_state.py --read` | retrato do painel (`namedState`, `panel.live.lines`, `placeholder`) `[CODE] panel_state.py:83,304` `[MEASURED] head` |
| `_main/panel-state.json.request` | shell | shell | pedido de dump, lido pelo escritor `[CODE] sotto_webview.py:365` |
| `_main/caption-settings.json` | menu dos 3 pontos (`set_target_lang`/`set_visual`) | shell no arranque | `{"target_lang": "pt"}` + `opacity`/`plate`; escrita atómica `[CODE] caption_settings.py:33,62` `[MEASURED] cat` |
| `_main/caption-wanted.json` | shell | shell | `{"on": bool, "at": ISO}`; desde 2026-11-11 NÃO suprime o arranque `[CODE] sotto_webview.py:21502,21508` `[MEASURED] cat` |
| `_main/caption-drag-offset.json` | shell (`caption_drag`) | shell | `{"x": int, "y": int}` `[CODE] caption_drag.py:36,299` |
| `_main/hotkey-settings.json` | bandeja + menu | shell no arranque | `{"panels": "Alt+C", "live": "Ctrl+Space"}`; quebrado cai nas teclas de fábrica `[CODE] hotkey_settings.py:40` |
| `_main/shell-relaunch.json` | `shell_relaunch` | `shell_relaunch` | `{"relaunches": [epoch…]}` — tecto por hora `[CODE] shell_relaunch.py:89,133` |
| `_main/warm-engine.pid` | warm engine | shell/instrumentos | `pid + hora de arranque` (uma das quatro fechaduras) `[CODE] warm_engine.py:19,95` |
| `_main/warm-engine.log` | warm engine | instrumentos | o estado do motor quente é este log `[CODE] warm_engine.py:96` |
| `_main/webview-run.log` | shell (`log`), `run.cmd`, worker via ponte | todos | `{stamp} sotto: TAG …`; roda aos 64 MB (`LOG_ROTATED`) `[CODE] sotto_webview.py:2594,2372` `[MEASURED] 25 439 116 B` |
| `_main/webview-worker-tracebacks.log` | worker, `_death_trace` | oráculo `worker-death-trace` | bloco `=== data pid=… ===`; tecto 256 KB, recicla metade `[CODE] worker/sotto_worker.py:9405-9435` |
| `_main/_audit-verify/*.log` | bateria (um por passo) | quem lê o recibo | saída integral do passo; 543 ficheiros `[MEASURED] ls` |
| `history/<AAAA-MM-DD>/<HH>.md` | shell, `history_append` | painel, busca, prune | linha `- [HH:MM:SS] texto` + `<!-- route=… -->`; retenção 4320 h `[CODE] sotto_webview.py:836-845,15688` |
| `history/audio/index.jsonl` | `worker/audio_ring.py` | índice de segmentos | `{file,t0,t1,samples,rate,kbps,bytes}` `[CODE] audio_ring.py:25,286` `[MEASURED] head` |
| `history/audio/lines.jsonl` | `worker/audio_ring.py` | busca de linhas | `{t0,t1,text,source}` `[CODE] audio_ring.py:26,422-433` |
| `%LOCALAPPDATA%\Sotto\endpoint-signal.json` | tap (`_journal_save`) | tap (escolha de endpoint) | `SOTTO_ENDPOINT_JOURNAL` desvia/desliga; ausente = journal vazio `[CODE] worker/wasapi_loopback.py:596-612` |
| `<TMPDIR>\sotto-batch-queue\` | `BatchQueue` | `BatchExecutor` | um manifesto JSON por bloco + `float32` cru; `adopted.json` regista spools adoptados `[CODE] batch_queue.py:24,489-493` |
| `_main/diar-live.json` | sidecar de falantes | worker (`speaker_bridge`) | `{"segments":[{"start","end","speaker"}], "threshold", "written_at"…}` `[CODE] speaker_bridge.py:48` `[MEASURED] cat` |
| `_main/diar-watch.json` | sidecar `--watch-only` | shell (`_diar_watch_path`) | estado da cadeia de falantes; ausente hoje `[CODE] sotto_webview.py:25084-25093` |
| `_main/battery-budget-baseline.json`, `battery-wiring-baseline.json` | o próprio oráculo, com `--baseline` | `battery-budget-oracle`, `battery-wiring-oracle` | baselines do ratchet; baseline ausente = RED, não passe `[CODE] battery-budget-oracle.py:47,937` |
| `history/<dia>/<HH>.summary.json` | **ninguém em HEAD** | — | existe **1** em disco (`history/2026-10-06/16.summary.json`) e `grep -rln "summary.json" app` devolve 0 `[MEASURED]` |

## 5. SINONIMOS E NOMES MORTOS

Esta secção existe porque o repo paga por prosa que descreve um estado que já não existe. Cada nome
abaixo foi testado com o comando colado; o resultado é o que o comando devolveu.

### 5.1 O gesto antigo (removido a 2026-10-30)

O próprio código guarda a lápide: `sotto_webview.py:2863-2868` diz que saíram `HOTKEY_HOLD_MS`,
`HOTKEY_TAP_WINDOW_MS`, `HOLD_CEILING_MS`, `is_hold`, `resolve_taps`, `_tick`/`_finish_measure`/
`_measuring`/`fake_hold_ms` do `HotkeyThread`, `on_hold` e `hotkey_hold` `[CODE]`.

| nome | comando | resultado |
|---|---|---|
| `HOTKEY_GESTURE_MS` | `grep -rF HOTKEY_GESTURE_MS --include=*.py app worker \| wc -l` | **0** |
| `HOTKEY_CAPTION_DEFER_MS` | idem, `--include=*.py --include=*.js --include=*.cmd` | **0** |
| `hotkey_hold` | `grep -rnwE 'hotkey_hold' --include=*.py app worker \| grep -vc ':#'` | **0** (só a lápide em comentário) |
| `HOTKEY_HOLD_MS` / `HOTKEY_TAP_WINDOW_MS` / `HOLD_CEILING_MS` / `fake_hold_ms` | `grep -rnF HOTKEY_HOLD_MS --include=*.py app worker` | **2** ocorrências, ambas PROSA (`hotkey_gesture.py:12`, `sotto_webview.py:2865`); **0** executáveis |
| `is_hold`, `resolve_taps`, `_finish_measure`, `_measuring` | `grep -rnwE 'is_hold\|resolve_taps\|_finish_measure\|_measuring' --include=*.py app worker \| wc -l` | **2** linhas, ambas a lápide `sotto_webview.py:2865-2866` |
| `HOTKEY_DOUBLE` | `grep -rF HOTKEY_DOUBLE --include=*.py app worker \| wc -l` | **0** |
| `HOTKEY_TRIPLE`, `HOTKEY_LONG` | idem | **0** e **0** |

O que **não** está morto, e é a armadilha simétrica: `HOTKEY_SINGLE` e `HOTKEY_HOLD` são nomes vivos
(3 e 2 ocorrências em `app`/`worker`) `[MEASURED]`; apagá-los por parecerem da mesma família seria
um defeito novo. `HOTKEY_GESTURE_MS` sobrevive em **8** ficheiros — recibos, logs de auditoria e o
índice `.codeintel`, nenhum deles código-fonte `[MEASURED] grep -rlF | wc -l`.

### 5.2 Nomes de instrumento e de estado

| nome | comando | resultado |
|---|---|---|
| `line-closed` | `grep -rF line-closed --include=*.py app worker \| wc -l` | **0** — fora do produto vive em `AGENTS.md`, dois recibos, no oráculo `_main/redux-live-contract-oracle.js` e no índice `.codeintel` |
| `LINE_CLOSED` | idem | **0** |
| `MOUSE_HOOK`, `OUTSIDE_CLICK_HOOK` | idem (`*_HOOK`) | **0** em `.py`; `OUTSIDE_CLICK_HOOK` só na lápide `_audit-verify-all.cmd:991` |
| `WM_HOOK_SYNC` | `grep -rF WM_HOOK_SYNC --include=*.py --include=*.js --include=*.cmd .` | **0** |
| `capture_ledger` | `grep -rF capture_ledger --include=*.py app worker \| wc -l` | **0** (o nome vivo é *tap ledger*/*journal*) |
| `SOTTO_HISTORY_DAYS`, `HISTORY_RETENTION_DAYS` | idem | **0** — a unidade é HORAS (`HISTORY_RETENTION_H`, 4320) `[CODE] sotto_webview.py:835` |
| `MONITOR_DEFAULTTOPRARY` | `grep -rF MONITOR_DEFAULTTOPRARY --exclude-dir=.git .` | **0** em `.py`/`.js`/`.cmd`; **7** linhas em prosa (`docs/shell-contract.md` §layout e três artefactos de `_main`), todas a citar o typo — o nome correcto é `MONITOR_DEFAULTTOPRIMARY` (`sotto_webview.py:2829`) |
| `SHELL_EXIT_ARMED`, `EXIT_WATCHDOG_GRACE_S`, `METER_HZ_DEFAULT`, `WORD_STEP_S` | idem, `.py`/`.js`/`.cmd` | **0** em código; só em `docs/shell-contract.md` e `docs/youtube-caption-spec.md` |
| `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED` | idem | **0** em código; só em `docs/worker-lifecycle.md` |

### 5.3 Armadilhas de grep que esta secção documenta

1. **Substring mente.** `grep -F on_hold` casa `_caption_hold` (`sotto_webview.py:18227`); use
   `grep -nw` ou exclua comentários `[MEASURED]`.
2. **Um ficheiro `.cmd` não é um `.py`.** `SOTTO_BATTERY_HEAVY` e `SOTTO_STEP_DEADLINE_S` dão 0 no
   corpus `.py` e são vivos em `_main/_audit-verify-all.cmd` `[MEASURED]`.
3. **`_main` não é fonte de verdade de tags.** 723 `.py` em `_main`; vários são cópias congeladas do
   shell (`_cache/sotto_webview_nograce.py` e os `_panel-*-mutant.py`, ambos sob `_cache/` no
   `.gitignore`), por isso um censo sobre `_main` conta o mesmo tag duas vezes `[MEASURED] ls`. Um
   caminho sob `_cache/` **não é evidência citável**: existe só nesta máquina, e um clone limpo
   não o tem.

## Lacunas

- `[UNKNOWN]` — a lista completa dos 89 nomes de família com o dono de cada um: medi as 14 maiores e
  o total, não as 89. Fechar com o mesmo scanner a imprimir `família → ficheiros` e uma leitura das
  famílias com menos de 3 tags.
- `[UNKNOWN]` — o significado dos 23 tags do log que o scanner não apanha (nascem de literais
  separadas da chamada). Fechar com uma passagem AST sobre `log_repeat`/`_write_stdout` em vez de
  regex.
- `[UNKNOWN]` — o schema de `_main/diar-watch.json`: o ficheiro não existe nesta máquina hoje
  (`ls` devolve ausente), e o leitor aceita-o opcionalmente. Fechar correndo o sidecar
  `--watch-only` numa máquina com áudio de falantes — não nesta sessão.
- `[UNKNOWN]` — quem escrevia `history/<dia>/<HH>.summary.json`: nenhum escritor em `app/`,
  `worker/` ou `_main/*.py`; o único exemplar é de 2026-10-06 e pode vir de uma versão anterior ao
  git deste checkout. Fechar com `git log -S summary.json`.
- `[UNKNOWN]` — os valores de `SOTTO_STEP_DEADLINE_S` e `RATCHET_PCT` em vigor nesta corrida sem
  executar o oráculo do orçamento (não corrido por ordem: nada da bateria nesta lane). Fechar exige
  `python _main/battery-budget-oracle.py --policy cap40` e os dois valores citados da sua saída.
- `[UNKNOWN]` — o custo real de cada passo `heavy` (12 declarados): exige `SOTTO_BATTERY_HEAVY=1`,
  proibido nesta lane.
