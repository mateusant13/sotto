# RECIBO — plano de verificação de runtime, e o estado medido agora (2026-11-09)

**Autor:** `RuntimeVerifyPlan` (subagente OMP).
**Janela de medição:** 2026-11-09 13:48:30–14:08:55 -0300.
**Escopo:** itens 6 e 7 do `TODO-omp-handoff-20261109.md`, menos o runtime em si (bloqueado no dono).
**Regras cumpridas:** nada foi lançado, reiniciado ou mostrado; nenhum input sintético; nenhum browser; nenhum terminal visível; nenhum Herdr; nenhum ficheiro do produto, `AGENTS.md` ou baseline tocado; a bateria não foi corrida; `_main/code-health-baseline.json` não foi refrescado. Só leitura + este ficheiro.

## 0. Contrato e estado do entregável

Checkboxes de protocolo que valem para esta tarefa, com fonte:

- **Não lançar/mostrar a app, não injectar input, não abrir browser/terminal/Herdr** — fonte: bloco `Context` desta tarefa (`HARD RULES`).
- **Só leitura; escrever apenas este recibo** — fonte: bloco `Target`/`Acceptance` desta tarefa.
- **Não correr a bateria; não refrescar `_main/code-health-baseline.json`** — fonte: bloco `Context` desta tarefa.
- **Fechar com `SELF-AUDIT` + `CACHE/PRICE`** — fonte: `I:/!manager/AGENTS.md`, blocos standard `SELF-AUDIT` e `CACHE/PRICE`.
- **Veredicto de frescura verbatim + claims -> comando/linha + pids/start + census** — fonte: `Acceptance` desta tarefa.

**Estado do entregável:** as medições deste recibo são **LIVE** (corri os instrumentos e li o estado real: oracle, psutil, `panel_state.py`, census). Os comandos da §2 são **UNWIRED** — não existe instância nova para os consumir; "escrevi o ficheiro" não é LIVE.

## 1. Frescura — veredicto verbatim

**Veredicto: STALE** (`EXIT=3`). O comando `python _main/live-code-freshness-oracle.py --strict` nomeia `pid=? started=?`; a linha de arranque que o oracle não vê nomeia **pid 50452** (`SHELL_STARTUP_STAGE ... 08:14:03.288`), e a janela é a árvore WebView2 **43976/30504** sob essa shell. Não há FRESH em nenhuma das duas corridas.

### 1.1 Corrida de 2026-11-09 13:48:30 -0300

Comando: `python _main/live-code-freshness-oracle.py --strict`

```
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=? started=?
  processo: sha256=77D4D1680260   <- GRAVADO no arranque, nao muda
  disco   : sha256=D6FAAA3D53D7 files=104   <- lido AGORA (2026-11-09 13:48:30), move-se a cada commit
  prova A : hash diferente
  prova B : indisponivel
  conjunto: 0 ficheiro(s) de code_identity() -- `--files` lista-os
  porque  : a etiqueta do processo nao e a do disco (hash diferente); sem linha de arranque nao ha prova B
  >>> O QUE O DONO CARREGA NAO E ESTE CODIGO. Nenhuma afirmacao sobre comportamento vale aqui:
  >>> fechar a app e abrir de novo ANTES de julgar o sintoma.
EXIT=3
```

### 1.2 Corrida de 2026-11-09 14:08:33 -0300 (mesma instância, árvore a mover-se)

```
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=? started=?
  processo: sha256=77D4D1680260   <- GRAVADO no arranque, nao muda
  disco   : sha256=EAB6892F23EF files=104   <- lido AGORA (2026-11-09 14:08:33), move-se a cada commit
  prova A : hash diferente
  prova B : indisponivel
  conjunto: 0 ficheiro(s) de code_identity() -- `--files` lista-os
  porque  : a etiqueta do processo nao e a do disco (hash diferente); sem linha de arranque nao ha prova B
  >>> O QUE O DONO CARREGA NAO E ESTE CODIGO. Nenhuma afirmacao sobre comportamento vale aqui:
  >>> fechar a app e abrir de novo ANTES de julgar o sintoma.
EXIT=3
```

### 1.3 Leitura: o veredicto é STALE, mas `pid=?` é artefacto do instrumento

**O veredicto STALE é verdadeiro** pela prova A: o hash gravado no arranque (`sha256=77D4D1680260`) não é o hash do disco (`D6FAAA3D53D7` às 13:48:30, `EAB6892F23EF` às 14:08:33 — a árvore está a ser editada por outras lanes, logo a referência da prova A move-se).

**Mas `pid=? started=?` não é um facto: é a janela de leitura do oracle.** A linha de arranque desta instância existe no mesmo log:

```
2026-11-09 08:14:03.288 sotto: SHELL_STARTUP_STAGE pid=50452 stage=pre-lock python=C:\Program Files\Python311\python.EXE panel=true
```

Ela está no offset de byte **64 689 455**; o ficheiro tem 72 305 518 B e a janela `TAIL_BYTES = 4 MiB` começa em **68 111 214 B** — a linha está **3,26 MiB fora** da janela. O oracle procura `SHELL_STARTUP_STAGE`/`SHELL_START` só nos últimos 4 MiB (`live-code-freshness-oracle.py:68`, `TAIL_BYTES`), não encontra, e cai em `started is None` (`:186-190`): sem prova B, imprime `pid=?`.

O registo append-only `_main/_cache/live-code-freshness.jsonl` mostra o instante em que a prova B se perdeu:

- `at=2026-11-09 11:37:18` — `pid=50452`, `started=2026-11-09 08:14:03.288`, `proof_a=true`, `proof_b_changed=14`, lista de 14 ficheiros.
- `at=2026-11-09 13:12:29` — `pid=""`, `started=""`, `proof_b_changed=null`, `why="... sem linha de arranque nao ha prova B"`.

Ou seja: a instância é a mesma (50452, 08:14:03.288); o que mudou foi o log a crescer para lá da janela. `python _main/live-code-freshness-oracle.py --files` também imprime `arranque=?` e etiqueta **todos** os 104 ficheiros como `antes` — vacuamente, porque não há instante de arranque com que comparar. Isto é um defeito do instrumento, não do produto; não o corrigi (fora do escopo, só leitura).

## 2. Claims de runtime que source + gates NÃO fecham

**Pré-condição para todas as linhas:** o dono abre uma instância nova; `python _main/live-code-freshness-oracle.py --strict` tem de imprimir `LIVE_CODE FRESH` (hoje imprime STALE — nenhuma afirmação de comportamento vale contra a instância actual). Os comandos abaixo são read-only e não lançam nada; os que exigem DOM (tema/busca) precisam que a instância seja aberta com `--cdp-port 9333` ou `SOTTO_CDP_PORT=9333` (`app/webview/webview2_args.py:31`, porta explícita; sem pedido o valor herdado é removido).

### 2.1 Comandos exatos (definições usadas na tabela)

```bash
# $ORACLE — frescura, primeiro de tudo
python _main/live-code-freshness-oracle.py --strict

# $READ / $JSON — estado do painel e do worker (o instrumento é app/webview/panel_state.py;
# _main/panel_state.py NÃO existe)
python app/webview/panel_state.py --read
python app/webview/panel_state.py --read --json

# $LAST <tag> — última linha de um tag no log vivo
python -c "import io;print([l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'sotto: LIVE_ENABLED ' in l][-1])"
# (trocar 'sotto: LIVE_ENABLED ' pelo tag desejado; exemplos abaixo)

# $COUNTS — contagens desde o último SHELL_STARTUP_STAGE
python -c "import io;t=io.open('_main/webview-run.log',encoding='utf-8',errors='replace').read();s=t.rsplit('SHELL_STARTUP_STAGE pid=',1)[1];print('spawns=%d exits=%d loads=%d releases=%d deferred=%d'%(s.count('BRIDGE_SPAWNED'),s.count('BRIDGE_EXIT '),s.count('sotto: WORKER REDUX_ENGINE_LOAD'),s.count('sotto: WORKER REDUX_ENGINE_RELEASED'),s.count('REDUX_BATCH_DEFERRED reason=reload-floor')))"

# $HIDE — esconder (Ctrl+Space), esperar >10 s, retomar; mede o intervalo
python -c "import io;L=[l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'sotto: LIVE_ENABLED ' in l];h=max(i for i,l in enumerate(L) if 'on=false' in l);r=min(i for i,l in enumerate(L) if i>h and 'on=true' in l);t=io.open('_main/webview-run.log',encoding='utf-8',errors='replace').read();s=t[t.index(L[h]):t.index(L[r])];print(L[h]);print(L[r]);print('worker_alive=%d history_append=%d engine_released=%d'%(s.count('BRIDGE_ALIVE WORKER_ALIVE'),s.count('sotto: HISTORY_APPEND'),s.count('sotto: WORKER REDUX_ENGINE_RELEASED')))"

# $THREADS — orçamento de fios e custo do worker
python -c "import io;print([l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'WORKER WORKER_THREADS ' in l][-1])"
python -c "import io;print([l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'WORKER WORKER_THREAD_PLAN ' in l][-1])"
python -c "import io;print([l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'WORKER WORKER_GENAI_THREADS ' in l][-1])"
python -c "import io;print([l.rstrip() for l in io.open('_main/webview-run.log',encoding='utf-8',errors='replace') if 'WORKER WORKER_COST ' in l][-1])"
# pid do worker: ler childPid de $READ; depois:
python _main/shell-thread-cpu.py <worker_pid> --seconds 8 --top 8
python _main/shell-thread-cpu.py 50452 --seconds 8 --top 8   # shell

# $AUDIT / $CPU — stutter antes/depois
python _main/caption-frame-audit.py --since HH:MM
python _main/shell-thread-cpu.py <shell_pid> --seconds 8 --top 8

# $CDP — DOM do painel VIVO (requer --cdp-port 9333; playwright existe em
# H:/env/npm-global/node_modules/playwright, medido)
node --input-type=module -e "import { chromium } from 'file:///H:/env/npm-global/node_modules/playwright/index.mjs'; const b=await chromium.connectOverCDP('http://127.0.0.1:9333'); const p=b.contexts()[0].pages().find(x=>x.url().includes('panel.html')); console.log(JSON.stringify(await p.evaluate(()=>({theme:document.documentElement.dataset.theme,searching:document.getElementById('history-tools')?.classList.contains('is-searching'),hidden:document.getElementById('history-search')?.hidden,hits:document.querySelectorAll('#history-list .hist').length,note:document.getElementById('history-note')?.textContent})))); await b.close();"
```

Leitura do `$COUNTS` no instante actual (14:08:55): `spawns=4 exits=3 loads=6 releases=2 deferred=0` — não é um arranque limpo; ver §3.1.

### 2.2 Tabela claims -> comando -> linha esperada

| # | Claim (recibo de origem) | Comando | Linha esperada numa instância nova |
|---|---|---|---|
| R1 | **Tema do painel na janela real** — 59 temas passam o oracle, mas "nada disto foi visto na tela do dono" (`receipt-20261106-panel-owner-round.md` §5; `receipt-20261108-panel-round-2.md` §5) | dono muda para `theme-3`; `$LAST 'sotto: CAPTION_OVERLAY_THEME_APPLIED theme='`; ou `$CDP` | `CAPTION_OVERLAY_THEME_APPLIED theme=theme-3 font=... live=... brand=theme-3 plate=... alpha=... radius=... fade=...` — ou, no caminho YouTube, `CAPTION_OVERLAY_THEME_REPLAYED theme=youtube brand='theme-3'`; no CDP, `{"theme":"theme-3",...}` |
| R2 | **Busca: keystroke REAL chega ao campo** — o próprio oracle diz que é UNMEASURED (`receipt-20261106-panel-owner-round.md` §5) | dono clica no glifo de busca e digita `the`; `$CDP` | `{"searching":true,"hidden":false,"hits":<N>>0,"note":"<N> matches for “the”"}` |
| R3 | **Arrasto do painel na janela real** — prova é jsdom + oráculos (`receipt-20261108-panel-round-2.md` §5; `receipt-20261108-strip-width-and-caption-drag.md` §4) | dono arrasta o painel pelo cabeçalho; `$LAST 'sotto: WINDOW_DRAG_DONE surface=panel'` | `WINDOW_DRAG_DONE surface=panel to=(<x>,<y>) size=<w>x<h> from=(<x0>,<y0>)` |
| R4 | **Arrasto da legenda + taxa entregue 128–196 Hz** (27 Hz sob carga; 240 Hz é tecto) — `receipt-20261108-caption-clock-and-marker.md` §4; handoff | dono segura Ctrl e arrasta a legenda; `$LAST 'sotto: CAPTION_DRAG_RATE'` e `$LAST 'sotto: CAPTION_DRAG_OFFSET'` | `CAPTION_DRAG_RATE ticks=<n> moves=<n> paints=<n> seconds=<s> hz=<128..196> target_hz=240 paint_ms=<ms>` e `CAPTION_DRAG_OFFSET x=<n> y=<n> saved=true` |
| R5 | **Esconder/retomar a legenda com modelo+história a continuar** — handoff item 6; `receipt-20261109-reload-floor.md` §9-bis | `$HIDE` (Ctrl+Space, >10 s, Ctrl+Space) | `LIVE_ENABLED on=false wanted=false panel_closed=false` seguido de `LIVE_ENABLED on=true wanted=true panel_closed=false`; `worker_alive>0 history_append>0 engine_released=0`; no resume, `CAPTION_OVERLAY_GEOMETRY shown=true on_screen=true rect=... alpha=<n> hwnd=<n>` |
| R6 | **Tecto de CPU/fios do worker** — `receipt-20261109-reload-floor.md` §10; `receipt-20261109-thread-bench-stutter.md` §6; `receipt-20261109-worker-cost-and-commit.md` §5/§7.5 | `$THREADS`; `python _main/shell-thread-cpu.py <worker_pid> --seconds 8 --top 8`; `$LAST 'sotto: THREAD_CPU'` | `WORKER WORKER_THREADS threads=2 source=flag`; `WORKER WORKER_THREAD_PLAN encoder=2 small=1 sessions=3 total_intra=4`; `WORKER WORKER_GENAI_THREADS threads=<n> pinned=<m> cpus=none`; `pid <worker_pid>: <n> fios, 8.0 s de janela, <pct>% de um nucleo no total`; `THREAD_CPU total=<n>% top=<nome>:<pct>% ...` |
| R7 | **Contagem de arranques/recargas** — `receipt-20261109-reload-floor.md` §9-bis; `receipt-20261109-worker-cost-and-commit.md` §7.4 | `$COUNTS`; `$READ`; `$JSON` | `spawns=1 exits=0 loads=1 releases=0 deferred=0` no arranque (1 = carga inicial; 0 antes de o modelo carregar); `captions (worker) = ... spawns=1 restarts=0 deaths=0`; `"reloadCount": 0` |
| R8 | **Stutter antes/depois** — `receipt-20261108-stutter-app-tree.md` §7; `receipt-20261109-thread-bench-stutter.md` §6; `receipt-20261109-load-shedding-io.md` §7 | `$AUDIT`; `$CPU` antes e depois | `quadros=<n> janela=<s>s por_segundo=<n> textos_distintos=<n>`; `repinturas=<n> oscilacoes=<n> pulos_de_linha=<n> vazios=<n>`; `VERDICT: PASS`; `pid <pid>: <n> fios, 8.0 s de janela, <pct>% de um nucleo no total` |
| R9 | **Relógio do YouTube com o vídeo parado** — `receipt-20261108-yt-pause-clock.md` §9/§10 | dono pausa o vídeo; `$LAST 'sotto: YOUTUBE_CDP_PACED'`; `$AUDIT --since HH:MM` | `YOUTUBE_CDP_PACED paused=True poll_s=0.50`; `VERDICT: PASS` no caption-frame-audit |
| R10 | **Roll-up com cue real** — `receipt-20261108-rollup-live.md` §3 (medido hoje: `timedtext` responde `0 bytes`) | repro do §6 do recibo (CDP 9222 na Chrome do dono + `Network.getResponseBody`) | `body len: >0` para `api/timedtext` (hoje: `0`); sem isso a cue real fica UNMEASURED |
| R11 | **Orçamento do batch executor com filho real** — `receipt-20261108-batch-executor-ceiling.md` §6 | `$LAST 'sotto: BATCH_CPU_BUDGET'` | `BATCH_CPU_BUDGET used_ms=<n> budget=0.12 rate=0.12 idle_ms=<n>` (taxa ≤ 0.12) |
| R12 | **Watchdog de custo a reiniciar um worker real** — `receipt-20261109-worker-cost-and-commit.md` §5 | `$LAST 'sotto: WORKER_COST_RESTART'` | `WORKER_COST_RESTART reason=cpu-sem-linha cpu_pct_avg=<n> rows=<n>` — só existe se o caso real (CPU ≥60 %c e zero linhas por 3 min) ocorrer; a ausência não prova nada |

### 2.3 Notas de honestidade por linha

- **R1/R2/R3:** o painel não deixa linha de log para tema/busca/arrasto de DOM; o tema chega ao overlay nativo (`CAPTION_OVERLAY_THEME_*`) e o arrasto do painel deixa `WINDOW_DRAG_BEGIN/DONE`. A busca não deixa NENHUMA linha: só o DOM via CDP (ou o olho do dono) a fecha.
- **R4:** `CAPTION_DRAG_RATE` não existe no log actual (0 ocorrências); `CAPTION_DRAG_OFFSET` tem 3 no log total, 0 desde 08:14 (outra sessão). É claim não verificada, não "quase verificada".
- **R5:** a instância actual (start 08:14:03) tem **zero** linhas `LIVE_ENABLED`; as últimas são de 06:57:04–06:59:37 (instância anterior) e terminam em `on=false`. Desde 08:14 há `HISTORY_APPEND`=23 e `BRIDGE_ALIVE WORKER_ALIVE`=2663, mas sem um par hide/resume nesta instância não se pode atribuir a continuação ao gesto. É claim não verificada. O `$HIDE` conta `REDUX_ENGINE_RELEASED` sem distinguir a razão; se no intervalo houver `reason=shed-muito-alta`, a libertação é da válvula de memória, não do gesto — ler a linha.
- **R6:** o worker vivo (56316) arrancou com `argv=["...python.EXE","-u","H:\sotto\worker\sotto_worker.py"]` — **sem `--threads`** (`BRIDGE_SPAWNED` de 13:43:45.996); o worker resolve então `--threads N > OMP_NUM_THREADS > 4` (`effective_threads`; o default 4 é do worker, o `WORKER_THREADS_DEFAULT = 2` é o default da shell nova, `sotto_webview.py:22797`). O plano `encoder=2 small=1 total_intra=4` só existe depois de a shell nova passar `--threads 2`. Hoje o log tem **zero** linhas `WORKER_THREADS`/`WORKER_THREAD_PLAN`/`WORKER_GENAI_THREADS`/`WORKER_COST`.
- **R7:** desde o arranque actual (08:14:03), o log tem **6** `WORKER REDUX_ENGINE_LOAD` e **2** `WORKER REDUX_ENGINE_RELEASED` de topo (08:29:48, 08:34:43, 08:38:23, 09:18:26, 13:11:43, 13:15:32, 13:16:34 e 14:11:32 — o último já depois do snapshot); as 189 ocorrências totais incluem também `stderr_tail` de mortes antigas. O que **não** existe é `REDUX_BATCH_DEFERRED` (0) e as tags de plano/custo (`WORKER_THREADS`/`WORKER_THREAD_PLAN`/`WORKER_GENAI_THREADS`/`WORKER_COST`, 0). O `ENGINE_VISIBLE_TAGS` actual (`sotto_webview.py:1366-1387`) inclui `REDUX_ENGINE_LOAD`, `REDUX_ENGINE_RELEASED`, `WORKER_THREADS`, `WORKER_THREAD_PLAN`, `WORKER_COST`, `WORKER_GENAI_THREADS`, `REDUX_SWITCH`, `REDUX_BATCH_KICK` — mas **não** inclui `REDUX_BATCH_DEFERRED`; portanto o marcador do piso (`reason=reload-floor`) **não é legível ao vivo** (só no `stderr_tail` da morte). Isto é [INFERENCE] do fonte, não medido (o caso nunca ocorreu: 0 ocorrências).
- **R9:** o `caption-frame-audit` lê o log; sem o dono a pausar, não há `YOUTUBE_CDP_PACED paused=True` novo. Já observado em 14:10:28 (depois do snapshot): `YOUTUBE_CDP_PACED paused=True poll_s=0.50`.
- **R10:** a Chrome do dono em 9222 é o browser dele; nenhuma lane deve dirigi-la sem autorização. O recibo original mediu `200` com corpo `0 bytes`; a pergunta continua aberta.
- **R12:** o caso do watchdog nunca foi observado nesta máquina; a linha é a rede, não uma cura medida.

## 3. Estado as-of-now (2026-11-09 14:08:55 -0300)

### 3.1 PIDs vivos (psutil, read-only)

| processo | pid | ppid | start (psutil) | threads | RSS | estado |
|---|---:|---:|---|---:|---:|---|
| shell `pythonw.exe` (`sotto_webview.py --log ... --no-self-relaunch --ready-file ...`) | **50452** | — | **2026-11-09 08:14:02** | 58 | 104,4 MB | running |
| worker `python.exe` (`-u H:\sotto\worker\sotto_worker.py`) | **56316** | 50452 | **2026-11-09 13:43:45** | 63 | 1 732,7 MB | running |
| WebView2 root (`--webview-exe-name=pythonw.exe`) | **43976** | 50452 | **2026-11-09 08:14:04** | 52 | 86,7 MB | running |
| WebView2 renderer (o DOM do painel) | **30504** | 43976 | **2026-11-09 08:14:04** | 32 | 84,2 MB | running |

O painel não é um processo separado: é o renderer 30504 dentro da árvore WebView2 do shell 50452. O worker 56316 é o 4.º spawn da shell (`spawns=4 restarts=3 deaths=3`), com `lastExit=15` e `noAudio=true` (`tap-silent-desktop`, `window_s=12.0 endpoints=6 peak=0.0`).

Contagens desde o arranque actual: `spawns=4 exits=3 loads=6 releases=2 deferred=0`; `HISTORY_APPEND=23`; `BRIDGE_ALIVE WORKER_ALIVE=2663`; `LIVE_ENABLED=0`.

`python app/webview/panel_state.py --read` às 13:57:28: `freshness=FRESH`, `producerPid=50452`, `sequence=10238`, `namedState=tap-dead-endpoint`, `panel.status='not ready' kind='busy'`, `live.count=106`, `shell.visible=False`, `reloadCount=0`, `captionLogCount=106`, `panelVisibility.visible=false since=boot transitions=1`.

### 3.2 Cauda do log (13:57:27–14:08:55)

```
2026-11-09 13:57:27.088 sotto: YOUTUBE_LOOP_HZ ticks=40 ok=40 none=0 age_ms=290 hz=8.0 src_reads=41417 src_errs=2
2026-11-09 13:57:27.339 sotto: YOUTUBE_TICK_MS avg=0 max=0 n=20 src='external:youtube:cdp' vid='VvINNQeF3jk' cdp_age_ms=266 rows=0 why='painted'
2026-11-09 13:57:28.092 sotto: YOUTUBE_CDP_HEALTH age=0.02 stats={'reads': 41419, 'errors': 2, 'last_error': 'ConnectionAbortedError: [WinError 10053] ...', 'note': 'attached'}
...
2026-11-09 14:08:55.206 sotto: YOUTUBE_CDP_SOURCE state=attached
2026-11-09 14:08:55.341 sotto: YOUTUBE_TARGET pick=c86ooa8R_OI why=declared declared=c86ooa8R_OI tabs=2
2026-11-09 14:08:55.713 sotto: YOUTUBE_CDP_SOURCE state=attached
```

Último `THREAD_CPU` observado: `2026-11-09 13:59:05.230 sotto: THREAD_CPU total=6% heartbeat=true top=sotto-batch-executor:3% sotto-gaming-mode:1% yt-cdp-source:0% yt-cdp-target:0%`.

### 3.3 A shell precede o código?

| comparação | instante | resultado |
|---|---|---|
| shell start (log) | 2026-11-09 08:14:03.288 | — |
| `git log -1 --format=%ad --date=iso -- app/webview/sotto_webview.py` (às 13:48) | `feee26d 2026-11-09 13:44:11 -0300` | shell **5 h 30 min 08 s** mais velha |
| mesmo comando às 14:03 (HEAD `e88c649 14:03:49`) | `f12dcd3 2026-11-09 14:02:59 -0300` | shell **5 h 48 min 56 s** mais velha |
| aggregate `git log -1 ... -- app/webview app/panel worker` | `f12dcd3 2026-11-09 14:02:59 -0300` | idem |
| worker start (psutil) | 2026-11-09 13:43:45 | — |
| `git log -1 ... -- worker/sotto_worker.py` | `feee26d 2026-11-09 13:44:11 -0300` | worker **26 s** mais velho que o próprio ficheiro |
| hash do processo vs disco | 13:48:30 / 14:08:33 | `77D4D1680260` vs `D6FAAA3D53D7` / `EAB6892F23EF` — diferente nas duas |

**Conclusão:** a shell (50452) e o worker (56316) precedem o código que decidem o comportamento; a shell carrega `files=102` no `SHELL_CODE_ID` de arranque, enquanto `code_files()` no disco já devolve 104. Qualquer afirmação de runtime dos recibos de 2026-11-06..09 é `fixed, NOT verified` até o dono abrir uma instância nova.

## 4. Artifact census

Comando pedido: `python I:/!watcher/tools/artifact-census.py --project H:/sotto`.

**Corrida 1 (comando pedido, canalizado por `| tail -60`):** ficou 900 s sem produzir output (o tecto do job; o `tail` só escreve no fim e o processo foi morto). **Corrida 2 (mesmo instrumento, tecto explícito):** `python I:/!watcher/tools/artifact-census.py --project H:/sotto --max-seconds 300` — terminou em **162,70 s**, `EXIT=0`, sem `[VARREDURA CORTADA]`. **Corrida 3 (repetição, cache quente):** o mesmo comando terminou em **35,74 s**, `EXIT=0`; o total citado passou de `231.78` para `231.79 GiB` (a árvore move-se; a diferença é arredondamento/1 referência).

```
=== artifact-census H:\sotto ===
volumes: C:\, D:\, E:\, F:\, G:\, H:\, I:\  stores: target, .venv, venv, node_modules, .pytest_cache, .mypy_cache, .ruff_cache, __pycache__, dist, build, .next, .turbo, codeintel-models, codeintel
POSSUÍDO PELO PROJETO: 7.77 GiB em 4 checkout(s);  31 MiB são store de build/cache
    7.58 GiB  H:/sotto  [git-register]  artefatos 32 MiB
          32 MiB  node_modules/
      78 MiB  H:/sotto-wt/ArbV8  [git-register]  artefatos 0 MiB
           0 MiB  __pycache__/
      74 MiB  H:/sotto-wt/UltraRefine  [git-register]  artefatos 0 MiB
      43 MiB  H:\sotto-wt-WakeBoth  [git-file-orphan]  artefatos 0 MiB
CITADO PELO CÓDIGO (usado, posse NÃO provada; NÃO somado): 231.79 GiB
  110.59 GiB  I:\!produtos202608   <- _main/focus-title-oracle.json:1707
   39.90 GiB  I:\importantes   <- _main/receipt-20261030-altc-acesso-clicker-fone.md:75
   25.03 GiB  G:\superharness   <- .agents/skills/task-resolver/SKILL.md:66
   18.90 GiB  H:\!gravador   <- _main/receipt-20261107-round2.md:143
   13.93 GiB  G:\env-data   <- .opencode/complaints-closure.md:743
    6.23 GiB  I:\cc-tmp   <- .opencode/complaints-closure.md:474
    5.59 GiB  H:\codeintel-worktrees   <- _main/receipt-20261109-load-shedding-io.md:83
    5.19 GiB  H:\pi-agent   <- _main/owner-prompts-20261108-40h.md:3
SEM PROVA (só nome igual, NÃO somado): 73.08 GiB
   67.35 GiB  H:\jcode-target-gnu
    1.78 GiB  H:\jcode-target-control
    1.36 GiB  H:\b1-appcore-target
    1012 MiB  I:\wt-target-keepalive
     449 MiB  H:\sotto-wt
     414 MiB  G:\sotto-ref
     342 MiB  G:\jcode-target-gnu
     324 MiB  I:\target-infinity
      23 MiB  G:\sotto-dirty-backup-20261007-194203
      19 MiB  I:\cl-pair-A1
      19 MiB  I:\cl-tlock-2
      17 MiB  G:\sotto-dirty-backup-20261010-030752-delta
```
(EXIT=0)

**Total possuído por volume** (a partir dos checkouts listados; os volumes sem checkout possuído ficam a 0):

| volume | possuído | não provado (UNPROVEN) |
|---|---:|---:|
| H: | 7,77 GiB | ≈ 71,30 GiB |
| I: | 0 | ≈ 1,34 GiB |
| G: | 0 | ≈ 0,40 GiB |
| C:, D:, E:, F: | 0 | 0 |
| **total** | **7,77 GiB** | **73,08 GiB** |

**UNPROVEN = 73,08 GiB** (o maior item: `H:\jcode-target-gnu`, 67,35 GiB). O total "citado pelo código" é **231,79 GiB**, mas o census não o soma ao possuído (posse não provada) — e essa é a leitura correta: `I:\!produtos202608` (110,59 GiB) e `G:\superharness` (25,03 GiB) são citados por oráculos/recibos, não possuídos por `H:/sotto`.

## 5. Top issues (por ordem de impacto na verificação)

1. **O oracle de frescura perde `pid`/`started`/prova B depois de ~4 MiB de log.** O veredicto STALE é verdadeiro, mas o relatório diz "sem linha de arranque" quando a linha existe (offset 64 689 455 vs janela 68 111 214) e `--files` carimba tudo `antes` vacuamente. Evidência: `_main/_cache/live-code-freshness.jsonl` 11:37:18 (`pid=50452`, prova B=14) -> 13:12:29 (`pid=""`).
2. **O marcador do piso de recarga (`REDUX_BATCH_DEFERRED reason=reload-floor`) não está em `ENGINE_VISIBLE_TAGS`.** O worker escreve-o no stderr, mas o `_pump` só publica as tags da tupla; logo o número que provaria o piso a morder não é legível ao vivo (só no `stderr_tail` da morte). [INFERENCE] do fonte; 0 ocorrências de `REDUX_BATCH_DEFERRED` hoje (as tags `REDUX_ENGINE_LOAD`/`RELEASED` têm 6/2 de topo desde 08:14).
3. **A instância viva precede todo o código de 2026-11-06..09.** Shell 08:14:03.288 vs `f12dcd3 14:02:59` (5 h 48 min); worker 13:43:45 vs `feee26d 13:44:11` (26 s). Nenhum claim de runtime destes recibos está verificado.
4. **O instrumento `_main/panel_state.py` citado no brief não existe**; o real é `app/webview/panel_state.py`. `_main/artifacts-census` também não existe (usei `I:/!watcher/tools/artifact-census.py`, como o brief autoriza).
5. **Tema/busca/arrasto do painel não deixam linha de log.** Tema chega ao overlay (`CAPTION_OVERLAY_THEME_*`), arrasto do painel deixa `WINDOW_DRAG_*`, mas a busca não deixa nada: só CDP 9333 ou o olho do dono. O `panel-search-keyboard-oracle.py` declara isso explicitamente (UNMEASURED para um keystroke real).

## CACHE/PRICE
- task/agent: RuntimeVerifyPlan
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RuntimeVerifyPlan']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RuntimeVerifyPlan']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T17:14:29.585238+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RuntimeVerifyPlan']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RuntimeVerifyPlan']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## 6. SELF-AUDIT

- **protocolos em falta** — o bloco `COMECAR` manda começar com `todo init`; esta toolset não tem `todo`. Em vez de fingir, o card curto vai na primeira linha do resultado e o `done` na última, como o próprio bloco prevê para toolsets sem `todo`. Também não há `ticket`: o defeito do oracle (§5.1) fica registado aqui e não num ticket — é a única via disponível nesta toolset.
- **verificação adicional** — correr `python _main/live-code-freshness-oracle.py --strict` com um log sintético cuja linha de arranque esteja a >4 MiB do fim e exigir que o relatório resolva `pid`/`started` (hoje falha por construção). Custo: um ficheiro temporário + uma corrida, ~1 s; não o fiz porque só podia escrever este recibo.
- **checkboxes novas** — mecânica: no `live-code-freshness-oracle.py`, procurar `SHELL_STARTUP_STAGE`/`SHELL_START` para trás em blocos até encontrar (ou indexar o offset na escrita), e falhar com `pid` vazio só quando o log inteiro não tiver a linha. Comando que a deixaria RED hoje: o log actual (a linha existe e o oracle imprime `pid=?`).
- **review por outro subagente** — `sim-com-escopo`: repetir §1 (duas corridas + jsonl), §3 (psutil + `git log`) e §4 (census) numa sessão própria; a tabela §2 é um plano, não uma medição, e deve ser revista por quem for executá-la.
- **gate-doubt** —
  - **verde-de-verdade:** o `EXIT=3`/STALE do oracle é real (prova A: hash diferente), não passa por construção; o que passa por construção é o `pid=?` — a janela de 4 MiB garante que uma instância com >4 MiB de log nunca resolve a linha de arranque. O `panel_state.py --read` deu `freshness=FRESH` com `ageSeconds=0.756` e `producerPid=50452`: verde real (o ficheiro é reescrito a cada 2 s), mas é frescura do DUMP, não do CÓDIGO. O census `EXIT=0` é real: 162,70 s < 300 s, sem marcador de corte.
  - **falta-no-gate:** o oracle não verifica que o `pid` resolvido é um processo vivo; imprime `pid=?` e continua. Cenário que atravessa: uma instância com 5 h de log e 100 MB — o operador lê `STALE` e conclui "não há processo", quando há um (50452). O `--files` também não distingue "antes do arranque" de "sem arranque": tudo é `antes`.
  - **gate-melhor:** no `judge()`, se `started is None`, procurar a linha de arranque para trás em blocos de 4 MiB até ao início do ficheiro e, se a encontrar, calcular a prova B; se não a encontrar, imprimir `pid=?` com `why="linha de arranque ausente do log inteiro"`. Input que tem de deixar RED: um log de teste com a linha a 5 MiB do fim e um `pid` conhecido — hoje imprime `pid=?`, amanhã tem de imprimir o `pid`.
- **confiança** — `alta` nos factos medidos (pids, start times, git dates, census, verbatim do oracle); `média` na tabela §2, porque os comandos de DOM (tema/busca) dependem de a instância ser aberta com `--cdp-port 9333` e de o dono executar o gesto.
- **não verificado** — (1) qualquer comportamento numa instância nova (não existe); (2) tema/busca/arrasto reais na tela do dono; (3) Ctrl+Space hide/resume com modelo+história nesta instância (o log actual só mostra o estado restaurado `on=false`); (4) `CAPTION_DRAG_RATE` (0 ocorrências); (5) `WORKER_THREADS`/`WORKER_THREAD_PLAN`/`WORKER_GENAI_THREADS`/`WORKER_COST` ao vivo (0 ocorrências); (6) `REDUX_ENGINE_LOAD`/`REDUX_ENGINE_RELEASED` de topo (6/2 desde 08:14; o resto em `stderr_tail`); (7) `REDUX_BATCH_DEFERRED` (0); (8) o census literal de 900 s (timeout, sem output) — os números vêm da corrida limitada a 300 s; (9) `python -m watcher perf` não foi corrido (não é instrumento desta árvore e não estava no brief).
