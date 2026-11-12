# STATUS — o registo vivo da especificação

Este ficheiro é a memória do trabalho. É actualizado a cada onda; não é um relatório final.
Cada linha diz o que está **escrito**, com que **evidência**, e o que **falta**.

Última actualização: 2026-11-12 (rodada de defeitos — D-09).

## Ondas

Todas as treze ondas estão escritas. `linhas` e as contagens de etiqueta foram medidas com
`wc -l` e `grep -o '\[CODE\]' | wc -l` sobre cada ficheiro.

| onda | estado | o que fica escrito | evidência |
|---|---|---|---|
| W0 inventário + índice | **feito** | `README.md`, este `STATUS.md`, contagem medida da superfície | `os.walk` medido: 229 ficheiros / 123 543 linhas |
| W1 arquitectura | **feito** | `01-ARCHITECTURE.md` (174 l., 9 `[CODE]` / 1 `[MEASURED]`): árvore de processos, largada do `run.cmd` (6 passos), 47 nomes de fio, o contrato shell↔worker, os ficheiros de estado, as 5 guardas de processo, as 3 coisas que a shell NÃO pode fazer ao worker | `run.cmd:236,311,316`; `_spawn`; `_consume`; `_child_env` |
| W2 arranque | **feito** | `02-BOOT.md` (350 l., 72 `[CODE]` / 16 `[MEASURED]` / 5 `[INFERENCE]` / 6 `[UNKNOWN]`): do duplo-clique ao primeiro pixel — as etapas `SHELL_STARTUP_STAGE`, os prazos de cada uma, o vigia da UI, o que falha e o que o dono vê | log vivo + oráculos `boot-interaction`, `boot-profile`, `ui-watchdog` |
| W3 captura | **feito** | `03-CAPTURE.md` (349 l., 119/9/4/8): os quatro braços de captura, o tap por processo e a lei do fio dono, a escada `c/p/a/b/tail` com `CAPTURE_FIRST_PICK`/`LADDER_TRY`, o alvo por NOME, o silêncio e as cinco guardas, o AGC e o tecto, o que a shell vê | `worker/sotto_worker.py`; `worker/wasapi_loopback.py`; `worker/process_target.py` |
| W4 motores | **feito** | `04-ENGINES.md` (350 l., 68/23/4/8): `ReduxHiddenSwitch` e as três portas, as constantes do lote, o orçamento de fios (tabela 188,0 % → 142,7 %), o motor quente e o `WARM_ATTACHED=0`, o `VramGuard`, o shedding por carga | `worker/engine_policy.py`; `worker/engine_switch.py`; `app/webview/warm_engine.py`; `load_shedding.py` |
| W5 caminho ao vivo | **feito** | `05-LIVE-PATH.md` (349 l., 161/8/4/6): do bloco de áudio ao pixel — parciais, `route`, o choke point do histórico, a pintura, os orçamentos medidos por elo | `app/webview/sotto_webview.py`; `caption_overlay.py`; `word_fade.py` |
| W6 YouTube | **feito** | `06-YOUTUBE.md` (175 l., 109/21/3/7): a fonte CDP, o relógio do player e a tolerância por estado, `_yt_clock_static`, a troca de vídeo, a política de língua (original em en/pt/es, escolhida fora deles) | `app/webview/youtube_cdp_source.py`; `youtube_clock.py`; `caption_settings.py` |
| W7 histórico e estado | **feito** | `07-HISTORY-STATE.md` (348 l., 293/10/14/8): o formato da linha e o `ctx1=`, as duas portas de admissão, a fusão, a retenção de 180 dias, busca e export, o anel de 12 h, a fila de lote, e cada ficheiro de estado com escritor/leitor/contrato de falha | `sotto_webview.py:15688`; `history_context.py`; `worker/audio_ring.py`; `batch_queue.py` |
| W8 painéis e UX | **feito** | `08-PANELS-UX.md` (346 l., 112/13/7/7): Alt+C por índice de pressão, Ctrl+Space (HOLD e o engolir do espaço), a caixa da legenda, os temas, o arrasto, as configurações e o que fica gravado | `hotkey_gesture.py`; `space_swallow.py`; `caption_drag.py`; `app/panel/**` |
| W9 modos de falha | **feito** | `09-FAILURE-MODES.md` (350 l., 37/30/15/6): o que acontece quando cada peça falha — dispositivo, worker, página, WebView2, Chrome/CDP, disco, energia, rede — e o que o dono vê em cada caso | linha por modo com a tag do log e o oráculo que a lê |
| W10 ledger de defeitos | **feito** | `10-DEFECTS.md` (531 l.): 10 defeitos com ANTES/DEPOIS/comando; D-02 é a ordem p0 do dono; D-05 corrigido nesta campanha | `git ls-files`; `live-code-freshness-oracle`; `caption-wanted.json`; `battery-budget-oracle` |
| W11 spec-alvo | **feito** | `11-TARGET.md` (205 l.): o comportamento que eu escolho, jornada a jornada, com o que "funciona" quer dizer em cada uma | deriva das jornadas de `00-PROMISE.md` |
| W12 selo | **feito** | índice, referências cruzadas e o portão das citações (`_main/spec-citations-oracle.py`, 1 174 citações em 15 documentos, 0 sem ficheiro, 0 fora de alcance) | `SPEC-CITATIONS VERDICT: PASS` |

## Defeitos já confirmados (detalhe em `10-DEFECTS.md`)

| id | uma linha | gravidade | estado |
|---|---|---|---|
| D-01 | dois mutantes congelados do worker não estavam no git (`.gitignore`: `worker/_sotto_worker_agcinert.py` e `worker/runs/`), e dois oráculos dependem deles (`_main/agc_order_live.py:37`, `_main/verdict-order-oracle.py:71`): num clone limpo esses dois não corriam | ALTA | **corrigido 2026-11-11** — `git ls-files` devolve os dois (`git add -f`), `.gitignore` explica por que, e o `.gitattributes` foi REGENERADO (`python _main/_make-gitattributes.py --write`; `--verify` rc=0) |
| D-02 | o arranque obedecia a `_main/caption-wanted.json` e um `false` gravado suprimia a legenda em TODA a abertura seguinte | CRÍTICA | **corrigido, NÃO verificado** — `caption_wanted_at_start` (21 arms + neg-arm 4/4); o processo do dono corre código anterior (`live-code-freshness` = STALE) |
| D-03 | `ast.get_source_segment` re-parte a fonte inteira por chamada: 143,9 s para extrair 264 funções; 52,1 s → 0,85 s no `gaming-hotkey` | MÉDIA | corrigido em dois sítios medidos (0,47 s; 61× byte-idêntico); os outros 38 ficheiros por medir |
| D-04 | cada abertura paga uma carga de motor quente (7,5–26,0 s, ~1 GB residente) que sai ao fim de 600 s sem ninguém a usar; as aberturas distam horas | ALTA | aberto; a escolha é do dono (TTL maior vs pedir o motor por evidência) |
| D-05 | o portão do relógio julgava 36 de 449 passos invocado sem `--policy`, e o RED descrevia a invocação | MÉDIA | **corrigido** — recusa `CANNOT-MEASURE` (rc 2) antes de escrever; 6 arms (`R1`–`R5`); neg-arm 6/6 |
| D-06 | bateria: 2 470,3 s em 413 passos presos a `cap40` (o portão julga 2 293,3 s) contra o alvo de 60 s; seis passos somam 506,2 s = 20 % | MÉDIA | aberto; a cauda é `red-as-expected-*` a copiar a árvore |
| D-07 | o número do painel no arranque circulou em QUATRO versões sem população, e o portão exigia a contradição | ALTA | **corrigido** — leitor puro `--read`, fixture do log vivo, neg-arm 3/3 |
| D-08 | o censo do painel abria o próprio log com `'w'`: cada invocação apagava a evidência da anterior (4 073 B → 42 B) | ALTA | **corrigido** — append com rotação, `--read` não escreve |
| D-09 | o menu do ícone re-armava as DUAS teclas: o `Ctrl+Space` ficava preso no fio velho (hook + `RegisterHotKey`), o novo pagava 1409 e o gate de recuo abria — o mesmo toque alternava duas vezes | CRÍTICA | **corrigido, NÃO verificado** — `arm_hotkey_role` recusa um segundo fio por papel; 19 arms + neg-arm 6/6 |
| D-10 | o braço `7d` do `altc-gesture` exigia a lista literal do desligar e acusava produto CERTO desde 2026-11-11 (a bateria estava RED nesse passo, 97/98) | MÉDIA | **corrigido** — o braço julga o domínio; 5º mutante prova; 98/98, neg-arm 5/5 |

## Números medidos nesta campanha

Guardados aqui porque a próxima sessão não deve re-medir o que já está medido **e o mundo não mudou**.

| o quê | número | como |
|---|---|---|
| linhas do produto | 123 543 em 229 ficheiros | `os.walk` por extensão, excluindo `.git`/`node_modules`/`_legacy`/`models`/`runs`/`_cache` |
| shell | 26 362 linhas, `SottoShell` com 227 membros, 29 classes | `ast` + contagem de `\n` |
| worker | 9 493 linhas, 17 classes | `ast` |
| a especificação | 15 ficheiros, 3 865 linhas, 1 111 `[CODE]` + 173 `[MEASURED]` + 63 `[INFERENCE]` + 70 `[UNKNOWN]` | `wc -l` + `grep -o` por etiqueta |
| citações resolvidas | 1 174 em 15 documentos, 0 sem ficheiro, 0 fora de alcance | `_main/spec-citations-oracle.py` |
| bateria | 480 passos / 480 com registo | `_main/battery-record-pairing-oracle.py` |
| pin da bateria | 363150 B / 4196 CRLF / 0 bare LF | `agents-md-pins-oracle.py` |
| oráculos ligados | 197 ligados / 108 sem passo / 305 na população | `battery-wiring-oracle.py` |
| custo da bateria | 2 293,3 s julgados em 413 passos presos a `cap40` | `battery-budget-oracle.py --policy cap40` |

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
