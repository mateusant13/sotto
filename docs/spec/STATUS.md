# STATUS — o registo vivo da especificação

Este ficheiro é a memória do trabalho. É actualizado a cada onda; não é um relatório final.
Cada linha diz o que está **escrito**, com que **evidência**, e o que **falta**.

Última actualização: **2026-11-15**. O ledger passou de 23 para **41 defeitos** (D-24..D-32 são a
rodada de 2026-11-14/15: z-order do painel, a linha que sobrevivia ao player, a bandeira de pausa,
a janela de aviso tomada por fala, a placa do BLOCO, o `Ctrl+Space` num jogo que ninguém jogava, e
a carga do motor por bloco; D-33/D-34 são a varredura de base de 2026-11-15; D-36 nasceu da
varredura de evidência da mesma data, e é a mesma classe do D-01 na camada que julga evidência; D-37..D-40
são a corrida da bateria da mesma data, que fechou RED sobre cinco instrumentos e nenhum defeito de
produto; D-41 é a cura do D-04 que estava INERTE no processo — a shell passava um handle de ficheiro
a quem abre por nome, o `TypeError` caía no fail-open e o motor quente era pedido em todo o arranque,
com 9 `WARM_ENGINE_EVIDENCE_FAILED` e 0 `WARM_ENGINE_NOT_REQUESTED` no log do dono). A tabela de números foi **re-medida hoje**, coluna a coluna, com o
comando ao lado; os valores anteriores estavam 3 dias velhos e dois deles já não eram verdade
(a bateria tinha 503 passos, tem **526**; a especificação tinha 1 477 citações, tem **1 678**).

## Ondas

Todas as treze ondas estão escritas. `linhas` e as contagens de etiqueta foram medidas com
`wc -l` e `grep -o '\[CODE\]' | wc -l` sobre cada ficheiro.

| onda | estado | o que fica escrito | evidência |
|---|---|---|---|
| W0 inventário + índice | **feito** | `README.md`, este `STATUS.md`, contagem medida da superfície | **233 ficheiros / 128 998 linhas**, medidos por `_main/spec-scale.py` (re-medido 2026-11-15) |
| W1 arquitectura | **feito** | `01-ARCHITECTURE.md` (174 l., 9 `[CODE]` / 1 `[MEASURED]`): árvore de processos, largada do `run.cmd` (6 passos), 47 nomes de fio, o contrato shell↔worker, os ficheiros de estado, as 5 guardas de processo, as 3 coisas que a shell NÃO pode fazer ao worker | `run.cmd:236,311,316`; `_spawn`; `_consume`; `_child_env` |
| W2 arranque | **feito** | `02-BOOT.md` (350 l., 72 `[CODE]` / 16 `[MEASURED]` / 5 `[INFERENCE]` / 6 `[UNKNOWN]`): do duplo-clique ao primeiro pixel — as etapas `SHELL_STARTUP_STAGE`, os prazos de cada uma, o vigia da UI, o que falha e o que o dono vê | log vivo + oráculos `boot-interaction`, `boot-profile`, `ui-watchdog` |
| W3 captura | **feito** | `03-CAPTURE.md` (349 l., 119/9/4/8): os quatro braços de captura, o tap por processo e a lei do fio dono, a escada `c/p/a/b/tail` com `CAPTURE_FIRST_PICK`/`LADDER_TRY`, o alvo por NOME, o silêncio e as cinco guardas, o AGC e o tecto, o que a shell vê | `worker/sotto_worker.py`; `worker/wasapi_loopback.py`; `worker/process_target.py` |
| W4 motores | **feito** | `04-ENGINES.md` (350 l., 68/23/4/8): `ReduxHiddenSwitch` e as três portas, as constantes do lote, o orçamento de fios (tabela 188,0 % → 142,7 %), o motor quente e o `WARM_ATTACHED=0`, o `VramGuard`, o shedding por carga | `worker/engine_policy.py`; `worker/engine_switch.py`; `app/webview/warm_engine.py`; `load_shedding.py` |
| W5 caminho ao vivo | **feito** | `05-LIVE-PATH.md` (349 l., 161/8/4/6): do bloco de áudio ao pixel — parciais, `route`, o choke point do histórico, a pintura, os orçamentos medidos por elo | `app/webview/sotto_webview.py`; `caption_overlay.py`; `word_fade.py` |
| W6 YouTube | **feito** | `06-YOUTUBE.md` (175 l., 109/21/3/7): a fonte CDP, o relógio do player e a tolerância por estado, `_yt_clock_static`, a troca de vídeo, a política de língua (original em en/pt/es, escolhida fora deles) | `app/webview/youtube_cdp_source.py`; `youtube_clock.py`; `caption_settings.py` |
| W7 histórico e estado | **feito** | `07-HISTORY-STATE.md` (380 l., 299/13/15/8): o formato da linha e o `ctx1=`, as duas portas de admissão, a fusão, a retenção de 180 dias, busca e export, o anel de 12 h, a fila de lote, e cada ficheiro de estado com escritor/leitor/contrato de falha | `sotto_webview.py:15688`; `history_context.py`; `worker/audio_ring.py`; `batch_queue.py` |
| W8 painéis e UX | **feito** | `08-PANELS-UX.md` (346 l., 112/13/7/7): Alt+C por índice de pressão, Ctrl+Space (HOLD e o engolir do espaço), a caixa da legenda, os temas, o arrasto, as configurações e o que fica gravado | `hotkey_gesture.py`; `space_swallow.py`; `caption_drag.py`; `app/panel/**` |
| W9 modos de falha | **feito** | `09-FAILURE-MODES.md` (350 l., 37/30/15/6): o que acontece quando cada peça falha — dispositivo, worker, página, WebView2, Chrome/CDP, disco, energia, rede — e o que o dono vê em cada caso | linha por modo com a tag do log e o oráculo que a lê |
| W10 ledger de defeitos | **feito** | `10-DEFECTS.md` (**41 defeitos** com ANTES/DEPOIS/comando; D-02 é a ordem p0 do dono; D-24..D-32 entraram em 2026-11-14/15, D-33/D-34 na varredura de base de 2026-11-15 e D-35 na leitura do caminho de escrita do histórico, D-36 na varredura da própria evidência, D-37..D-40 na corrida da bateria que fechou RED sobre cinco instrumentos, e D-41 na sessão de 2026-11-15 que apanharia a cura do D-04 a ser INERTE no processo) | `git ls-files`; `live-code-freshness-oracle`; `caption-wanted.json`; `battery-budget-oracle` |
| W11 spec-alvo | **feito** | `11-TARGET.md` (279 l.): o comportamento que eu escolho, jornada a jornada, com o que "funciona" quer dizer em cada uma | deriva das jornadas de `00-PROMISE.md` |
| W12 selo | **feito** | índice, referências cruzadas, o portão das citações (`_main/spec-citations-oracle.py`) e o do **catálogo de módulos** (`_main/spec-coverage-oracle.py`: um bloco por ficheiro de produto em `13-MODULES.md`; `docs=16 ausentes=0 nome_apenas=0 classes_sem_seccao=0`) | `SPEC-CITATIONS VERDICT: PASS`; `SPEC-COVERAGE VERDICT: PASS` (+ `--neg-arm`) |
| W13 módulos | **feito** | `13-MODULES.md` (84 blocos — os 114 módulos de produto, com skin e sonda como classe — + 6 secções de cabeçalho: um bloco por ficheiro de produto, com o que garante, quem o chama, o que escreve e o que o dono vê quando falha) | `spec-coverage-oracle.py` mede a população por `os.walk`, não por lista curada |

## Defeitos já confirmados (detalhe em `10-DEFECTS.md`)

| id | uma linha | gravidade | estado |
|---|---|---|---|
| D-23 | a legenda local do áudio que o player pinta era **descartada** — não ia ao ecrã nem ao histórico —, e o docstring afirmava que ia ao histórico; o contador por episódio era zerado antes de ser lido e media sempre `0` | ALTA | **corrigido, NÃO verificado** — `_main/external-owner-oracle.py` 7/7 arms, `--neg-arm` 3/3; o destino definitivo da linha recusada é decisão de produto em `11-TARGET.md` §J4 |
| D-01 | dois mutantes congelados do worker não estavam no git (`.gitignore`: `worker/_sotto_worker_agcinert.py` e `worker/runs/`), e dois oráculos dependem deles (`_main/agc_order_live.py:37`, `_main/verdict-order-oracle.py:71`): num clone limpo esses dois não corriam | ALTA | **corrigido 2026-11-11** — `git ls-files` devolve os dois (`git add -f`), `.gitignore` explica por que, e o `.gitattributes` foi REGENERADO (`python _main/_make-gitattributes.py --write`). NOTA 2026-11-15: o `--verify` citado aqui era INERTE na data deste fecho -- caía no ramo de impressão, media nada e devolvia rc=0. Hoje ele DELEGA no portão real (`_main/_gitattributes-verify.py`) e é ele que dá `VERDICT: PASS`; ver AGENTS.md §O EOL DO REPO |
| D-02 | o arranque obedecia a `_main/caption-wanted.json` e um `false` gravado suprimia a legenda em TODA a abertura seguinte | CRÍTICA | **corrigido, NÃO verificado** — `caption_wanted_at_start` (21 arms + neg-arm 4/4); o processo do dono corre código anterior (`live-code-freshness` = STALE) |
| D-03 | `ast.get_source_segment` re-parte a fonte inteira por chamada: 143,9 s para extrair 264 funções; 52,1 s → 0,85 s no `gaming-hotkey` | MÉDIA | corrigido em dois sítios medidos (0,47 s; 61× byte-idêntico); os outros 38 ficheiros por medir |
| D-04 | cada abertura paga uma carga de motor quente (7,5–26,0 s, ~1 GB residente) que sai ao fim de 600 s sem ninguém a usar; as aberturas distam horas | ALTA | **corrigido, NÃO verificado** — o pedido passa a ser por EVIDÊNCIA (`warm_evidence`, fail-open: sem série PEDE); medido antes: 8 cargas, 8 `WARM_EXIT why=idle-expired`, ZERO `WARM_ATTACHED` |
| D-05 | o portão do relógio julgava 36 de 449 passos invocado sem `--policy`, e o RED descrevia a invocação | MÉDIA | **corrigido** — recusa `CANNOT-MEASURE` (rc 2) antes de escrever; 6 arms (`R1`–`R5`); neg-arm 6/6 |
| D-06 | bateria: 2 470,3 s em 413 passos presos a `cap40` (o portão julga 2 293,3 s) contra o alvo de 60 s; seis passos somam 506,2 s = 20 % | MÉDIA | aberto, com a cauda nomeada por CAUSA — quatro braços negativos pagavam o trabalho inteiro por mutante; medidos 92,2→56,8 s, 59,8→44,4 s, 53,1→34,8 s, 110,2→12,9 s, cada um com o veredicto intacto |
| D-07 | o número do painel no arranque circulou em QUATRO versões sem população, e o portão exigia a contradição | ALTA | **corrigido** — leitor puro `--read`, fixture do log vivo, neg-arm 3/3 |
| D-08 | o censo do painel abria o próprio log com `'w'`: cada invocação apagava a evidência da anterior (4 073 B → 42 B) | ALTA | **corrigido** — append com rotação, `--read` não escreve |
| D-09 | o menu do ícone re-armava as DUAS teclas: o `Ctrl+Space` ficava preso no fio velho (hook + `RegisterHotKey`), o novo pagava 1409 e o gate de recuo abria — o mesmo toque alternava duas vezes | CRÍTICA | **corrigido, NÃO verificado** — `arm_hotkey_role` recusa um segundo fio por papel; 19 arms + neg-arm 6/6 |
| D-10 | o braço `7d` do `altc-gesture` exigia a lista literal do desligar e acusava produto CERTO desde 2026-11-11 (a bateria estava RED nesse passo, 97/98) | MÉDIA | **corrigido** — o braço julga o domínio; 5º mutante prova; 98/98, neg-arm 5/5 |
| D-11 | a segunda legenda da janela substituía a primeira no latch de `emit_async` — fala perdida sem uma linha no log, e a página é que commita o histórico | CRÍTICA | **corrigido** — kinds de EVENTO enfileiram (tecto 32, excedente DITO em `CAPTION_EMIT_DROPPED`); 6 arms, neg-arm 2/2 |
| D-12 | o `--ready-file` do G3 era escrito pelo caminho dos 25 s, com a página do painel pendurada: o largador respondia 0 ao único HANG que sabe medir | ALTA | **corrigido** — `_mark_launch_ready(panel_loaded)`; arms C1/C2, mutante B2 |
| D-13 | a ordem "passe de lote ligado" valia só por `run.cmd`; o autostart do logon larga `pythonw` e não passa por ele — no logon o motor de lote corria DESLIGADO | ALTA | **corrigido** — `env.setdefault('SOTTO_REDUX_LIVE','1')` em `_child_env`; `app-target` arm e, e o oráculo passou a ter passo |
| D-14 | o motor quente entra na lista de *reap* da saída (`.kill()` levanta, `.wait()` não existe) e o matador externo mata-o pelo pid, com dois docstrings a prometer o contrário | MÉDIA | **corrigido, NÃO verificado** 2026-11-12 — `children=` e `backstop_pids=` separados; e a varredura do matador passou a correr também quando o handle do pai chega tarde (`no-handle`); 13 arms + neg-arm 5/5, passo `exit-backstop` |
| D-15 | uma largada de MEDIÇÃO (`--probe-v2` e mais oito) tomava lock privado e escrevia `panel-state.json`/`panel-visibility.json` por cima dos ficheiros da app viva — o worker do dono recebia `visible=false` e perdia o nível de shed | ALTA | **corrigido, NÃO verificado** — um único predicado para lock e estado, sufixo = nome do lock, worker lê o mesmo ficheiro; 15 arms + neg-arm 3/3 |
| D-16 | um `SOTTO_WEBVIEW_AFTER_LOAD_S` presente e ilegivel caia em 25 s de espera na thread que ainda nao chamou `webview.start()` — a espera que o proprio comentario diz ter produzido o `HANG rc=4` | MÉDIA | **corrigido, NÃO verificado** — `after_load_wait_s` devolve zero e a razao; 4 casos executados, neg-arm 6/6 |
| D-17 | uma largada de MEDIÇÃO drenava a FILA DO BATCH do dono (io 69,1 MB/s medido no stutter) | ALTO | corrigido, NÃO verificado -- `isolated_queue_dir`; `measurement-flags` A9, neg-arm 6/6 |
| D-18 | o ramo `no_audio` do cao de guarda nunca testava a prova de vida -- worker travado nao era reiniciado | CRÍTICO | corrigido, NÃO verificado -- 7 arms + neg-arm 2/2 |
| D-19 | o tecto `MAX_PER_HOUR` dizia "por hora" e nunca era zerado: 3 reinícios na vida do processo | ALTO | **corrigido, NÃO verificado** — `cost_watchdog.window_expired`; 43 arms, neg-arm 13/13; verificado só quando o processo dele correr este código |
| D-20 | a MEDIDA da legenda construía a fonte com peso `1` (booleano `bold`) e o DESENHO com o peso do tema: com a placa `tight` as últimas letras caíam fora do bitmap | ALTO | **corrigido, NÃO verificado** — `_measure` recebe `liveWeight`/`prevWeight`; 10 arms, neg-arm 9/9 |
| D-21 | `PanelVisibilityReader._fallback` herdava o `last_payload` da última leitura boa: uma shell morta estacionada mandava `shed='muito-alta'` para sempre e calava o transcritor | ALTO | **corrigido, NÃO verificado** — `last_payload = None` nas três falhas; ARM 6b (um leitor, duas voltas) + mutante do produtor morto |
| D-22 | `probe_tabs` cortava a POPULAÇÃO de abas em `MAX_PROBE_TABS` antes de saber qual toca (`tabs=7` no log do dono), e o log imprimia o número já cortado | MÉDIO | **corrigido, NÃO verificado** — vagas limitadas pelo relógio; `tabs_total/probed/done/abandoned`; 24 arms, neg-arm 17/17 |

## Números medidos nesta campanha

Guardados aqui porque a próxima sessão não deve re-medir o que já está medido **e o mundo não mudou**.

| o quê | número | como |
|---|---|---|
| linhas do produto | **128 998 em 233 ficheiros** (a superfície que a spec lê) | `_main/spec-scale.py`, re-medido 2026-11-15 nesta sessão (`app/webview/**/*.py` 50 410 em 46; `worker/**/*.py` 35 271 em 63; `app/panel/**` 43 317 em 124; `unreadable=0`) |
| shell | 27 364 linhas, `SottoShell` com 221 membros, 35 classes | `ast` sobre `app/webview/sotto_webview.py` (membros = `FunctionDef`/`AsyncFunctionDef` do corpo da classe) |
| worker | 9 527 linhas, 18 classes (17 + `LineFormer` no topo; contadas por `ast` hoje) | `ast` sobre `worker/sotto_worker.py` |
| a especificação | 14 documentos (sem `README.md`/`STATUS.md`), **6 520 linhas**, **1 543 `[CODE]` + 179 `[MEASURED]` + 64 `[INFERENCE]` + 73 `[UNKNOWN]`**; os 16 ficheiros somam 6 737 linhas | contagem por ficheiro de `docs/spec/*.md` com `len(t.splitlines())` e `re.findall(r'\[([A-Z]+)\]', t)`, re-medido 2026-11-15 nesta sessão |
| defeitos no ledger | **40** (D-01..D-40) | `sorted(set(re.findall(r'D-(\d+)', …)))` sobre `10-DEFECTS.md` |
| citações resolvidas | **1 678** em 16 documentos, 0 sem ficheiro, 0 fora de alcance, 0 índice ausente, **0 fora do índice do git (A6)**, **0 boletins `[UNKNOWN]` sem condição de fecho (A7, 58 medidos)**, 9/9 documentos com o que-não-se-sabe escrito | `_main/spec-citations-oracle.py` (arms A6 e A7 novas, neg-arm 6/6) |
| catálogo de módulos | `docs=16 ausentes=0 nome_apenas=0 classes_sem_seccao=0`; população **114 módulos** + 2 grupos de classe (`app/panel/skins/`=84, `worker/_probe/`=32 `.py` de 96 ficheiros na pasta) | `_main/spec-coverage-oracle.py` |
| bateria | **526 passos / 526 com registo / 0 achados** | `_main/battery-record-pairing-oracle.py` |
| pin da bateria | **401 086 B / 4 606 CRLF / 0 bare LF** sha256 `4382254C…0F243666` (o blob tem menos bytes em LF; 401 086 é o que um checkout materializa) | `agents-md-pins-oracle.py` (verde, 2 pins, re-medido 2026-11-15) |
| oráculos ligados | **211** ligados / 105 sem passo / 316 na população | `battery-wiring-oracle.py`, re-medido hoje |
| custo da bateria | **1 176,3 s julgados em 310 passos** sob `cap40` | `battery-budget-oracle.py --policy cap40` (`RATCHET-OK`, `TARGET NOT MET`, gap 1 116,3 s de 60 s) |
| censo de consolas | `CONSOLE-AUDIT VERDICT PASS -- 0 sítio(s) que abrem janela` (1 333 ficheiros) | `_main/console-window-audit.py` |
| gate do ecrã do dono | `achados=0 <= baseline=0` sobre 1 157 ficheiros de produto | `_main/owner-screen-gate.py` |
| nomes indefinidos | GREEN — 19 ficheiros de produção, 0 nomes usados e nunca definidos | `_main/undefined-names-oracle.py` |

## Duas contradições encontradas e resolvidas no selo

O portão das citações prova que cada `ficheiro:linha` existe; **não** prova que a linha diz o que a
frase diz. Duas frases passavam o portão e estavam erradas, e as duas foram corrigidas no
`01-ARCHITECTURE.md` a partir do código, não da prosa que as acompanhava:

1. `_main/webview-worker-tracebacks.log` era atribuído à **shell**; o escritor é
   `worker/sotto_worker.py:9408` (`grep -rn webview-worker-tracebacks --include=*.py` devolve o
   worker e seis cópias congeladas do worker, nenhuma da shell).
2. `history/audio/` era descrito como "áudio que ficou sem transcrição"; é o **anel de 12 horas** do
   `AudioRing` que guarda **todo** o áudio do tap
   (`worker/audio_ring.py:102,114,189`), e o áudio não transcrito vive no `PendingAudio` do worker e
   na fila de lote (`07-HISTORY-STATE.md` §8.2).

## O que este registo NÃO afirma

- Nenhuma jornada é `verified`: exige o processo do dono a correr ESTE código, e a lei do `STALE`
  continua a valer (`live-code-freshness-oracle --strict`).
- Os `[UNKNOWN]` de cada documento continuam abertos. Um `[UNKNOWN]` é uma resposta, não uma dívida
  escondida: cada um diz o que o fecharia.
