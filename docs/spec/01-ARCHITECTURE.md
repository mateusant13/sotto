# 01 — ARQUITECTURA: quem é quem

Tudo aqui é `[CODE]` a menos que diga outra coisa. Cada afirmação tem o ficheiro e a linha ao lado,
e foi lida nesta campanha (2026-11-11), não herdada de um documento antigo.

## 1. A árvore de processos

```
explorer.exe (autostart no logon, ou duplo-clique do dono)
└── cmd.exe   app/webview/run.cmd                            [285 linhas]
    ├── pythonw.exe ... --check-args <flags>     PRE-FLIGHT, começa NADA   (run.cmd:216)
    ├── start "" pythonw.exe ... --log ... --ready-file ...   A APP        (run.cmd:266,272)
    └── pythonw.exe ... --wait-ready <ficheiro>  ESPERA limitada, rc=4 = HANG (run.cmd:276)

pythonw.exe sotto_webview.py        A SHELL — o processo que o dono vê
├── python.exe -u worker/sotto_worker.py      O WORKER — outro processo, BELOW_NORMAL
│   ├── fios: asr, tap-open, plp-owner, plp-handler, sotto-heartbeat,
│   │         sotto-frontend, file-tap
│   └── (nenhum filho: o worker não larga processos)
├── msedgewebview2.exe × N        O browser que hospeda app/panel/
└── ~30 fios da shell             (lista em §3)
```

`[CODE]` o par não é `detached`: `run.cmd:266,272` faz `start "" "%PYW%" ...`, ou seja o `cmd.exe` sai
quando a app nasce, e a app fica sem pai de consola — é o que permite ao dono fechar o `cmd` sem
matar o Sotto.

**A shell é GUI-subsystem (`pythonw.exe`), e por isso não tem stdout.** Medido e escrito no próprio
`run.cmd:51-57`: `Start-Process pythonw` dá `stdout=None stderr=None GetConsoleWindow()=0`. É a
razão pela qual o `--log` existe e o recibo de uma corrida é o FICHEIRO, não o ecrã. `[CODE]`

**Não há fallback para `python.exe`.** `run.cmd:166-170` recusa com `rc=3` quando não há
`pythonw.exe` ao lado do interpretador, porque o fallback de antes pintava uma consola na tela do
dono. `[CODE]`

## 2. A largada, por dentro do `run.cmd`

| passo | o que faz | onde |
|---|---|---|
| 1 | `SOTTO_REDUX_LIVE` / `SOTTO_REDUX_WHEN_HIDDEN`: **NÃO são definidos aqui** — o dono único é `WorkerBridge._child_env` (`setdefault`, `"1"`), e este ficheiro só o diz em comentário | `run.cmd:82-99`; `app/webview/sotto_webview.py` `_child_env` |
| 2 | resolve `pythonw.exe` a partir de `py -3 -c "import sys;print(sys.executable)"`; sem ele, `where python` | `run.cmd:112-121` |
| 3 | flags que IMPRIMEM (`--help`, `--selftest`, `--memory`, `--dump-dom`, autostart) vão por `python.exe` — usam o terminal que já existe | `run.cmd:143-161` |
| 4 | `--check-args`: o parser DA SHELL valida a lista; nada arranca | `run.cmd:216` |
| 5 | `start` da app, com perfil efémero do WebView2 e log por omissão `_main\webview-run.log` | `run.cmd:260-273` |
| 6 | `--wait-ready`: espera limitada (30 s, `SOTTO_READY_BOUND`) que a app toque o ficheiro de prontidão; `rc=4` e a frase `HANG` se não tocar | `run.cmd:276-285` |

Duas consequências de desenho que valem a pena dizer em palavras:

1. **Uma flag recusada deixou de responder "sucesso".** Antes de 2026-10-06 `run.cmd --bogus-flag`
   saía `0` com zero bytes de log e zero processos (`run.cmd:199-204`). O pre-flight existe para
   isso e valida contra o `argparse` da própria shell — uma tabela só.
2. **O recibo é escrito por `python`, não por `cmd >>`.** Medido em 2026-10-12: com a app viva, o
   `>>` do `cmd` é recusado com erro 32 e os dois recibos do wrapper ficavam mudos exactamente
   quando a app está a correr (`run.cmd:266-269`). Por isso há `run-cmd-log-append.py`.

## 3. Os fios da shell, por nome

A shell e o worker nomeiam cada fio que criam (medido: **47** nomes distintos em `app/webview/*.py` + `worker/*.py`; 64 incluindo os nomes montados por `f-string`). Os que
mudam comportamento:

| fio | de onde | o que faz |
|---|---|---|
| `sotto-worker-stdout` / `sotto-worker-stderr` | `_spawn` | bombeia JSONL e a cauda de erro do worker |
| `sotto-worker-wait` | `_spawn` | colhe o filho e colore a morte |
| `sotto-worker-reap` | `stop` | mata e colhe sem prender o chamador |
| `sotto-panel-visibility` | `PanelVisibilityWriter` | escreve `panel-visibility.json` a cada 3,0 s |
| `sotto-panel-state` / `sotto-panel-stall` / `sotto-panel-nav-retry` | `panel_state.py`, shell | o retrato vivo do painel e a recuperação de navegação |
| `sotto-ui-watchdog` | shell | pergunta ao Windows se a janela responde |
| `sotto-vram-guard` | `VramGuard` | vigia a VRAM e parqueia motores |
| `sotto-topmost` | shell | devolve `WS_EX_TOPMOST` a cada 2 s |
| `sotto-thread-cpu`, `sotto-slow-read`, `sotto-cost-*` | instrumentos | medem CPU/serie do próprio processo |
| `sotto-yt-track`, `yt-cdp-source`, `yt-clock`, `yt-probe`, `yt-src-resolver` | `ExternalCaptionWatcher` e `youtube_*` | a fonte externa do YouTube |
| `sotto-warm-*`, `warm-load`, `warm-decode`, `warm-send`, `warm-accept`, `warm-attach-tap` | `WarmPipeBridge`, `warm_engine` | o motor de transcrição pré-carregado |
| `sotto-tray`, `sotto-stdout`, `sotto-shell-relaunch`, `sotto-revive`, `sotto-profile-sweep`, `sotto-power-window`, `sotto-startup-watch`, `sotto-window-drag`, `sotto-strip-metrics`, `sotto-yt-track`, `speaker-sidecar-drain` | vários | bandeja, relançamento próprio, arrasto, medição da faixa, sidecar de falantes |

`[INFERENCE]` O número de fios não é gratuito: cada um é um pedido de trabalho ao sistema, e o
projecto já mediu que um fio criado por frame custa 90 % de um núcleo (`caption-tick-thread`,
AGENTS.md §A LEI DO CUSTO). A regra que o `01` fixa: **um fio por responsabilidade, nunca por
evento.**

## 4. O contrato shell ↔ worker

### 4.1 Shell → worker: só ARGV e ambiente. Nunca `stdin`.

`[CODE]` `_spawn` (sotto_webview.py:23461-23480):

```python
argv = [self.command, '-u', self.worker_path] + list(self.extra_args)
self.child = subprocess.Popen(
    argv, cwd=os.path.dirname(self.worker_path),
    stdin=subprocess.DEVNULL, stdout=PIPE, stderr=PIPE,
    env=env, text=True, encoding='utf-8', errors='replace', bufsize=1,
    **popen_kwargs(creationflags))
```

- **`stdin=DEVNULL`.** O worker não tem canal de comando. Isto é uma decisão estrutural, não um
  esquecimento: a única coisa que a shell pode fazer a um worker é **substituí-lo**. (No worker,
  `grep stdin` devolve zero linhas — `[MEASURED]`.)
- **`-u` não é estilo, é latência.** Sem ele o pipe bufferiza 8 KB por bloco e uma legenda pode
  ficar presa 109 s (`prev` medido 2026-11-03, citado no comentário de `_spawn`).
- **O ambiente é um contrato pinado.** `_child_env` (23308-23352) é `dict(os.environ)` +
  `PYTHONUNBUFFERED=1` + `SOTTO_CAPTURE_MODE` + `SOTTO_REDUX_WHEN_HIDDEN=1`, mais
  `SOTTO_AUDIO_DEVICE` e `SOTTO_TARGET_PID` **só quando pedidos**. `_main/app-target-oracle.py`
  ARM e mantém este contrato; o orçamento de fios viaja em ARGV (`--threads`), precisamente para
  não acrescentar uma chave.
- **Classe de prioridade.** `CREATE_NO_WINDOW` (0x08000000) + `BELOW_NORMAL_PRIORITY_CLASS`
  (0x00004000) — o worker lê 1 GB de pesos e não pode ganhar à secretária. A shell, por sua vez,
  sobe-se a si própria para NORMAL no arranque (`raise_visible_priority`, `main():25870`).

### 4.2 Worker → shell: JSONL, uma linha por evento

`_consume` (23777-23963) é o único leitor. Três tipos:

| `type` | efeito na shell |
|---|---|
| `caption` | **a única prova de vida.** Texto vazio é RECUSADO (`'' IS NOT A CAPTION`); uma legenda levanta o `pending_error` e limpa o veredicto `no_audio`. Leva `meta` = todos os outros campos, mais `historySession` (pid + época). |
| `meter` | os medidores de sinal/peak do worker |
| `status` | `state` governa o texto do painel e a reserva da janela de silêncio: `model-loading` (só antes do primeiro `model-loaded` daquele filho) pinta `carregando modelo…`; `model-loaded` fecha a janela de carga e publica `BRIDGE_LOAD_MS` + `WORKER_BOOT_PROF`; `capture-started` marca `capturing=True` e carimba a época da captura; estados de erro/`done` fecham a captura; `boot/stage=providers` publica `WORKER_PROVIDERS`. |

Tudo o que não é um destes três é contado (`self.malformed`) e a linha aparece como
`BRIDGE_MALFORMED` / `BRIDGE_UNKNOWN`. **Um protocolo que ignora o que não conhece é como um
`except: pass`** — aqui pelo menos conta.

### 4.3 O terceiro canal: FICHEIROS

Como não há `stdin`, o controlo que não é "matar e relançar" viaja em disco:

| ficheiro | escritor | leitor | contrato |
|---|---|---|---|
| `_main/panel-visibility.json` | shell, fio `sotto-panel-visibility`, cada 3,0 s | worker | schema `sotto.panel-visibility/1`; `visible` é MEDIDO (`IsWindowVisible`), não "nós escondemos"; `writtenAtEpoch` + `staleAfterSeconds` deixam o leitor recusar a resposta de uma shell morta; **falha-se para `visible=true`** (manter a transcrever é a regra dura) |
| `_main/panel-state.json` | shell (`PanelVisibilityWriter`/estado) | instrumentos, oráculos, `panel_state.py --read` | o retrato do painel; a idade não é auto-reportada (um produtor morto não pode actualizar um número dentro do ficheiro que parou de escrever) |
| `_main/caption-settings.json` | shell (menu dos 3 pontos) | shell | língua-alvo + visual da legenda |
| `_main/caption-wanted.json` | shell | shell | o registo da última intenção de mostrar legenda. **Desde 2026-11-11 o arranque NÃO o obedece**: a decisão é de `SottoShell.caption_wanted_at_start` (pura) — liga por omissão, desliga numa corrida de MEDIÇÃO (`MEASUREMENT_FLAGS`) ou numa largada de lane (`SOTTO_LANE_LAUNCH=1`), e o desacordo com o ficheiro vai para o log (`CAPTION_WANTED_START_OVERRIDES`). Ver `docs/hotkey-gestos.md` §"A legenda ABRE ligada" |
| `_main/caption-drag-offset.json` | shell (`caption_drag`) | shell | onde ele arrastou a legenda |
| `_main/hotkey-settings.json` | shell (bandeja + menu) | shell no arranque | `{"panels": "Alt+C", "live": "Ctrl+Space", "panels_enabled": bool}`; ficheiro quebrado cai nas teclas de fábrica em vez de deixar a app surda |
| `_main/shell-relaunch.json` | `shell_relaunch` | `shell_relaunch` | contador de relançamentos na hora (tecto por hora) |
| `_main/diar-watch.json` | shell | instrumentos | estado da cadeia de falantes |
| `_main/webview-run.log` | shell, `run.cmd`, worker (via ponte) | todos | o recibo vivo |
| `_main/webview-worker-tracebacks.log` | worker (`sotto_worker.py:9408`) `[CODE]` | instrumentos | a frase inteira da morte do worker (tecto 256 KB) `[CODE]` |
| `history/<AAAA-MM-DD>/<HH>.md` | shell (`history_append`) | shell, painel, busca | a transcrição; linha `- [HH:MM:SS] texto` + comentário de proveniência |
| `history/audio/` | worker (`AudioRing`) `[CODE]` `worker/audio_ring.py:102` | instrumentos de replay `[CODE]` | anel de 12 h: TODO o áudio do tap em segmentos Opus de 16 kHz mono, mais `index.jsonl`/`lines.jsonl` (`07-HISTORY-STATE.md` §8.1) |
| spool do lote | shell (`batch_queue`) | shell | `BatchQueue` em disco com `adopted.json` |

`[INFERENCE]` Isto explica porque é que o projecto tem tantos oráculos que "executam o produtor e
lêem o ficheiro": o ficheiro **é** a interface. Também explica a classe de defeito mais cara da
casa (o `panel-deps`): se o produtor muda e o leitor é cacheado, o verde passa a descrever outro
programa.

## 5. As guardas de processo (o que impede duas apps e processos órfãos)

| guarda | mecanismo | evidência |
|---|---|---|
| instância única | mutex `Local\SottoShell`; uma segunda largada diz que já corre e sai `0` | `main():26084-26105` |
| largadas de MEDIÇÃO | levam uma mutex DERIVADA das flags (`measurement_lock_name`) e **saltam o hotkey**: uma sonda não rouba o Alt+C do dono | `main():26055-26080` |
| árvore morre com a shell | job object com `KILL_ON_JOB_CLOSE` (`_hold_kill_on_close_job`) — medido: 25 `msedgewebview2.exe` de quatro árvores, três delas de instâncias mortas | `main():26090`; AGENTS.md §job-object |
| perfil WebView2 | efémero por largada + varredura de perfis mortos (`WEBVIEW2_PROFILE_SWEEP`) | `main():26240-26262` |
| ambiente herdado | `apply_webview2_environment` remove `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` herdado; uma porta de depuração explícita é `--cdp-port N` | `main():25903`; `app/webview/webview2_args.py` |

## 6. O que a shell NÃO pode fazer ao worker (e porquê)

Três coisas que parecem naturais e não existem, e a razão de cada uma:

1. **Não lhe pode dizer "muda de dispositivo".** Não há canal. A escada de dispositivos roda DENTRO
   do worker; a shell só observa `status.device` e `candidates`.
2. **Não lhe pode dizer "processa agora o áudio que ficou".** O interruptor de lote lê
   `panel-visibility.json` e a carga medida; é o worker que decide.
3. **Não pode reiniciá-lo barato.** Cada reinício custa a leitura dos pesos: `BRIDGE_LOAD_MS`
   medido 8 906 ms a 61 781 ms conforme a máquina (log do dono, várias datas). É por isso que
   existem o piso de 20 s após saída limpa, a janela de silêncio que mede SILÊNCIO e não idade, e
   a escada que para de relançar depois de N mortes seguidas.

`[INFERENCE]` A conclusão de desenho que isto impõe, e que `05-LIVE-PATH.md` retoma: **toda a
política que precisa de ser rápida (drenar, parquear, trocar de motor) tem de viver do lado do
worker**, porque do lado da shell o único verbo é "morre".

## 7. As variáveis de ambiente que mudam o produto

Um censo de 2026-11-15 (`environ.get`/`environ[...]` em `app/webview/*.py` + `worker/*.py`) conta
**54** `SOTTO_*` lidas. Destas, **oito mudam comportamento que o dono sente**; o resto é alavanca de
instrumento ou de afinação (§ abaixo). Sem a variável definida, vale o que está escrito em parênteses.

| variável | o que muda | evidência |
|---|---|---|
| `SOTTO_HOT_RELOAD_WORKER` | `1` deixa o watcher **reiniciar** o worker; ausente = detecta e regista, nunca dispara (2026-10-17: duas edições custaram dois minutos de máquina cada) | `sotto_webview.py:23550` |
| `SOTTO_WATCH_WORKER` | basenames vigiados, separados por `;` (ausente: `sotto_worker.py`, `redux_live.py`) | `hot_reload.py:70-73` |
| `SOTTO_NO_SELF_RELAUNCH` | `1` desliga o auto-relançamento da shell, igual a `--no-self-relaunch` | `sotto_webview.py:27294` |
| `SOTTO_NO_EXTERNAL` | `1` desliga o observador de legendas externas. É interruptor **próprio**: `--no-worker` não pode implicar "sem legenda nenhuma" | `sotto_webview.py:20713` |
| `SOTTO_LIVE_HOTKEY` | acorde da legenda ao vivo; ausente = `hotkey-settings.json`, senão `hotkey_numbers()` (existe para uma sonda não roubar a tecla do dono) | `sotto_webview.py:10721` |
| `SOTTO_HISTORY_ROOT` | raiz do arquivo de histórico (ausente: `<repo>/history`) | `sotto_webview.py:843-846` |
| `SOTTO_WEBVIEW_WINDOW_TO_VISUAL` | `0`/`off` sai do modo `WindowToVisual` do WebView2 | `sotto_webview.py:26718` |
| `SOTTO_LOG_CAP_MB` / `SOTTO_LOG_KEEP_MB` | rotação do log vivo e cauda guardada (64 / 16 MB) | `sotto_webview.py:2426-2427` |

**As outras 46 são alavanca, não contrato.** Reproduzir um defeito (`SOTTO_LAYERED=1` volta a compor
branco na faixa, `SOTTO_YT_TARGET_HWND` força a janela do YouTube), afinar tectos (`SOTTO_METER_HZ`,
`SOTTO_SMALL_GRAPH_THREADS`, `SOTTO_GENAI_CPUS`, `SOTTO_LOAD_BG_MAX_S`) ou redireccionar ficheiros
(`SOTTO_CHUNK_TRACE`, `SOTTO_REDUX_WAV_DIR`, `SOTTO_REDUX_SPOOL_DIR`, `SOTTO_WORKER_TRACEBACK_LOG`,
`SOTTO_AUDIO_RING_DIR`). Cada uma lê-se no sítio que a consome — `worker/sotto_worker.py`,
`worker/audio_ring.py`, `worker/engine_policy.py` — e nenhuma é forma de configurar o produto.

**Fora do censo por não serem ambiente:** `SOTTO_VOICE_RE` e `SOTTO_GOLDEN_ANGLE` são `const` de JS em
`panel.js:638-639`; `SOTTO_CMDLINE_*`, `SOTTO_PSDIAG_*` e `SOTTO_WINPROBE_` moram em
`app/_legacy-electron/`, que está morto.

