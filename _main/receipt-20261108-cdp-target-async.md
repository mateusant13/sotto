# RECIBO — `cdp-target-async` (2026-11-08)

**Estado do entregavel:** `DARK` no sentido estrito do START — o codigo esta LIGADO no produto
(`CdpCaptionSource.start()` arranca o fio, `sotto_webview` ja' chamava `target_video_id()`), e
exercitado ao vivo no oraculo (A1–A5, harness). O que NAO existe e' prova na instancia viva: o
pid 42572 corre codigo ANTERIOR e segura o mutex de instancia unica — a prova ao vivo corre no
arranque seguinte do dono. Ver "NOT measured".

Segunda faixa do stutter DM de 2026-11-08 (watcher). Ficheiros tocados:
`app/webview/youtube_cdp_source.py`, `_main/cdp-target-async-oracle.py`,
`_main/code-health-baseline.json` (uma entrada). **NAO** toquei `overlay_paint.py` nem
`caption_overlay.py` (faixa `PaintCostNuclear`), nem `_main/_audit-verify-all.cmd`, nem o pin do
`AGENTS.md` (o `Main` e' o dono unico da integracao desses dois).

## O ANTES (reproduzido por mim, `_main/webview-run.log`, instancia viva pid 42572)

```
2026-11-08 04:38:04.639 sotto: EXTERNAL_CAPTIONS_READ_MS ms=1281.0 phases={'import': 0.0, 'target': 15.0, 'source': 15.0, 'yt-in': 15.0, 'cdp': 15.0, 'vid': 1281.0, 'youtube': 1281.0, 'end': 1281.0}
2026-11-08 04:37:03.800 sotto: EXTERNAL_CAPTIONS_READ_MS ms=1375.0 phases={'import': 0.0, 'target': 0.0, 'source': 1375.0, 'yt-in': 1375.0, 'cdp': 1375.0, 'vid': 1375.0, ...}
2026-11-08 04:40:24.316 sotto: EXTERNAL_CAPTIONS_READ_STATS n=362 mean_ms=2.9 p95_ms=0.0 max_ms=1000.0 interval_s=0.10
2026-11-08 04:37:54.122 sotto: EXTERNAL_CAPTIONS_READ_STATS n=528 mean_ms=13.0 p95_ms=16.0 max_ms=1375.0 interval_s=0.10
2026-11-08 04:36:43.649 sotto: YOUTUBE_TARGET_SLOW ms=1360 vid=sAQTn_qRZPw ttl_s=10
2026-11-08 04:37:03.800 sotto: YOUTUBE_TARGET_SLOW ms=1375 vid=sAQTn_qRZPw ttl_s=10
2026-11-08 04:38:04.638 sotto: YOUTUBE_TARGET_SLOW ms=1266 vid=AWR7Dy5ItrY ttl_s=10
2026-11-08 04:40:23.998 sotto: YOUTUBE_TARGET_SLOW ms=1000 vid=sfN8OTYA-e0 ttl_s=10
```

A testemunha de que o custo era a pergunta do alvo: `04:37:03.800` tem o `YOUTUBE_TARGET_SLOW
ms=1375` e o `EXTERNAL_CAPTIONS_READ_MS ms=1375.0` **no mesmo milissegundo** — a linha de log
saia de dentro da leitura. A volta inteira cabia entre `cdp` (15,0 ms, o `_yt_cdp_ensure`) e
`vid` (1281,0 ms), e o unico trabalho nessa janela era
`youtube_cdp_source.list_targets()` (`/json/list` por HTTP). 5 linhas SLOW na ultima hora.

## A MUDANCA (o que mudou de fio, e o que NAO mudou)

- O `/json/list` passou a ser pago pelo fio `yt-cdp-target` (`_tid_run`), que publica
  `(hora, video_id)` em `_tid_cache`.
- `target_video_id()` deixou de fazer I/O depois da primeira publicacao: le' o cache.
  **O unico pedido que ainda pode sair do chamador e' o PRIMEIRO** (cache vazio: antes de o fio
  publicar, um duplo de teste que nunca chamou `start()`); `_tid_refresh` grava o cache mesmo
  quando a resposta e' `''`, logo nunca ha' um segundo pedido pelo chamador. Isto e' declarado,
  nao escondido — e' o que mantem honestos os bracos `STALE-ID` (`yt-target-stale-oracle`) e
  `A5` (`youtube-cdp-slow-oracle`), que perguntam o id a duplos de teste.
- `_TID_TTL_S` / `_TID_SLOW_MS` / `_TID_SLOW_TTL_S` mantem o significado: sao a CADENCIA do
  refrescador agora (0,5 s; 10 s depois de uma chamada > 500 ms) — o numero de pedidos ao Chrome
  nao subiu, mudou o fio que os paga.
- `YOUTUBE_TARGET_SLOW` mantem nome e campos (`ms`, `vid`, `ttl_s`) e ganhou `src=refresher`.

## O DEPOIS (medido no oraculo, `python _main/cdp-target-async-oracle.py`)

| braco | o que mede | resultado |
|---|---|---|
| A1-WARM | o fio publica antes de a leitura perguntar | `refreshes=1 vid='AAAAAAAAAAA'` |
| A1-NO-BLOCK | 1000 × `target_video_id()` com `list_targets` falso a dormir **1,2 s** | `calls=1000 total=0.000s p95=0.0004 ms` (limite 0,05 ms) |
| A3-SLOW | sinal de lentidao, com a testemunha do fio | `YOUTUBE_TARGET_SLOW ms=1188 vid=AAAAAAAAAAA ttl_s=10 src=refresher`, `_tid_ttl=10.0` |
| A4-LIFECYCLE | fio unico, zero pedidos sem attach, morte no `stop()` | `fio='yt-cdp-target' um_so=True pedidos_sem_attach=0 morreu=True` |
| A5-CALLER | quem fez o HTTP nunca foi o chamador | `pedidos=1 de threads que nao o refrescador: []` |
| A2-REBIND | `/json/list` devolve aba A, depois aba B; `_yt_identify` REAL | `YOUTUBE_TARGET_REBOUND was=AAAAAAAAAAA now=BBBBBBBBBBB why=aba`, `yt_video_id='BBBBBBBBBBB'` |

`VERDICT: PASS (arms=6 fail=0)`, wall time 2,70 s.

`--neg-arm` (dois mutantes, cada um numa COPIA): `inline` derruba `A1-NO-BLOCK`
(`calls=2 total=2.391s p95=1203.8 ms estourou=True`) e `sem-slow-log` derruba `A3-SLOW`
(`''`); imprime `NEG-ARM: PASS (dois mutantes, os dois apanhados)` e devolve **rc=1**;
wall time 9,51 s.

O relogio-limite do A1 (`TOTAL_BUDGET_S + SLEEP_S`) existe para o mutante ser APANHADO em ~2 s
em vez de a medicao pendurar 20 minutos: um braco que so' mede nao distingue "rapido" de "ainda
nao voltou".

## CADENCIA E PIOR ESTALIDADE (declaradas)

- cadencia normal: **0,5 s** (`_TID_TTL_S`);
- cadencia lenta: **10 s** (`_TID_SLOW_TTL_S`), quando o refresh mede > 500 ms;
- pior estalidade servida: `cadencia + duracao da chamada`, com a chamada limitada pelo prazo do
  `urlopen` (`list_targets`, 3,0 s) → **≤ 1,9 s** no caminho normal (0,5 s + 1,4 s medidos) e
  **≤ 11,4 s** no regime lento. E' a mesma ordem de grandeza de antes (o cache antigo tambem
  valia 0,5 s/10 s), agora sem bloquear o laco.
- o fio nao faz um unico pedido enquanto `_run` nao marcar `_attached` (fonte que nunca ligou nao
  arranca trabalho), e uma falha de attach recente suspende-o 30 s (a mesma janela da guarda que
  ja' existia em `target_video_id`).

## SITIOS (file:line, arvore como esta' agora)

- `app/webview/youtube_cdp_source.py:926` — `_TID_THREAD_NAME = "yt-cdp-target"`.
- `app/webview/youtube_cdp_source.py:994-1001` — `_tid_cache`, `_tid_ttl`, `_tid_thread`,
  `_tid_refreshes` no `__init__`.
- `app/webview/youtube_cdp_source.py:1019-1031` — `start()` arranca o refrescador com a fonte.
- `app/webview/youtube_cdp_source.py:1186` — `stop()` (o mesmo `_stop` mata os dois fios).
- `app/webview/youtube_cdp_source.py:1206-1259` — `target_video_id()`, leitura de cache.
- `app/webview/youtube_cdp_source.py:1262-1268` — `_tid_start()` (idempotente).
- `app/webview/youtube_cdp_source.py:1270-1296` — `_tid_run()` (o fio; zero I/O sem `_attached`).
- `app/webview/youtube_cdp_source.py:1298-1337` — `_tid_refresh()` (o corpo antigo, com
  `YOUTUBE_TARGET_SLOW ... src=refresher`).
- `app/webview/sotto_webview.py:3619, 3682, 4785, 4795` — chamadas de `target_video_id()`:
  **inalteradas** (o contrato da funcao nao mudou; o rebind em 4795-4801 continua a ser o mesmo
  codigo que produz `YOUTUBE_TARGET_REBOUND`, provado em A2 com a fonte real).

## PORTAS (o que corri, e o resultado)

| porta | resultado |
|---|---|
| `cdp-target-async-oracle.py` | `VERDICT: PASS (arms=6 fail=0)` |
| `cdp-target-async-oracle.py --neg-arm` | rc=1, `NEG-ARM: PASS (dois mutantes, os dois apanhados)` |
| `yt-target-stale-oracle.py` | `VERDICT: PASS (arms=7 fail=0)` — STALE-ID e REBOUND intactos |
| `youtube-cdp-slow-oracle.py` (nao pedido, afectado) | `6/6 arms green`, A5 `sonda-livre=True ('SLOWVID0001' calls=1)` |
| `code-health-oracle.py` | a MINHA entrada passou a `SAME app/webview/youtube_cdp_source.py 81035 B (+0) 1670 linhas`; os 6 RED restantes sao `caption_overlay.py`/`overlay_paint.py` da outra faixa |
| `battery-class-oracle.py` | `PASS -- arms=3 fail=0` |
| `battery-wiring-oracle.py` | RED por desenho enquanto o passo nao existir: `new-unwired ... cdp-target-async-oracle.py, paint-cost-oracle.py`. Provei o verde com os meus dois passos colados numa COPIA da arvore: `ligados=156 -> 157`, e o unico sem passo ficou a ser `paint-cost-oracle.py` (da outra faixa) |
| `agents-md-pins-oracle.py` | `PASS -- 2 pin(s) checked live, 0 failure(s)`. Para o `Main` re-medir depois de colar: `_main/_audit-verify-all.cmd` = **284085 B**, **3441 CRLF** / 0 bare LF, sha256 `557B59AC377C6AFE0E1141D5549223273533FC32362EE7D801EDB3ED6355C95D` (medido 07:5x, mtime 04:49:49). NAO toquei no ficheiro |
| `claims-date-oracle.py` | RED com 4 afirmacoes sem data — todas no `AGENTS.md` da outra faixa (`paint`/`cost * 1.02`/`1 591 Hz`). O censo deste portao le' **so' o `AGENTS.md`** (`doc_lines`), logo nenhum ficheiro meu entra nele |

## O QUE O `Main` tem de colar (dono unico da integracao)

Ponto de insercao: **entre a linha 1397** (`call :expectred red-as-expected-yt-target-stale
!STEP_RC! "%OUT%\yt-target-stale-neg.log" "NEG-ARM PASS"`) **e a linha 1399** (`REM O ECO DO DONO
NAO ABRE NADA ...`), depois da linha em branco 1398. Texto exacto (CRLF, como o ficheiro):

```
REM O ALVO FORA DO LACO (2026-11-08, MEDIDO na instancia viva pid 42572): `EXTERNAL_CAPTIONS_READ_MS
REM ms=1281.0 phases={'cdp': 15.0, 'vid': 1281.0}` -- o `/json/list` de 1,0-1,4 s corria dentro do laco
REM de leitura e de ~10 em ~10 s nao saia um quadro. O fio `yt-cdp-target` paga a pergunta e
REM `target_video_id()` passa a ler memoria; o `--neg-arm` derruba a chamada inline e o log SLOW.
call :step cdp-target-async 0 "_main\cdp-target-async-oracle.py;app\webview\youtube_cdp_source.py" "%OUT%\cdp-target-async.log" python _main\cdp-target-async-oracle.py
call :record cdp-target-async !STEP_RC!
call :step red-as-expected-cdp-target-async 1 "_main\cdp-target-async-oracle.py;app\webview\youtube_cdp_source.py" "%OUT%\cdp-target-async-neg.log" python _main\cdp-target-async-oracle.py --neg-arm
call :expectred red-as-expected-cdp-target-async !STEP_RC! "%OUT%\cdp-target-async-neg.log" "NEG-ARM: PASS"
```

(`sotto_webview.py` nao entra nos deps: as chamadas ficaram como estavam; se entrar, e' uma
dependencia a mais sem mudanca de codigo do lado dele.)

**Tamanho declarado do meu oraculo para o baseline do code-health:** `_main/cdp-target-async-oracle.py`
= **14055 B** (0 CRLF, 329 linhas). Ele nao entra no `code-health-baseline.json`
porque `population()` so' mede `app/webview`, `worker` e `app/panel`.

## TECTO DECLARADO

- O fio novo: **1 thread daemon** por fonte, inerte (0 pedidos) ate' ao attach; morre no `stop()`.
- Pedidos ao Chrome: **inalterados** (2/s no caminho normal, 0,1/s no lento) — a cadencia e' a
  que o cache ja' tinha.
- Custo do oraculo: 2,70 s no braco verde e 9,51 s no `--neg-arm`, quase todo `sleep` (1,2 s a
  fingir o `/json/list`); CPU desprezavel, logo sem `watcher run --cpu` (o modulo `watcher` nem
  existe nesta arvore: `python -m watcher` -> `No module named watcher`).
- Crescimento absorvido no baseline (nunca folgado): `youtube_cdp_source.py`
  bytes 76213 -> **81035**, linhas 1580 -> **1670**; `defs`, `classes`, `max_func`,
  `except_pass`, `globals` **iguais** (27 / 1 / 230 / 6 / 0).

## NOT measured

- **Nao ha prova na instancia viva.** O pid 42572 corre codigo anterior e segura o mutex de
  instancia unica; a prova (um `EXTERNAL_CAPTIONS_READ_MS` com `phases['vid']` de microssegundos
  e `YOUTUBE_TARGET_SLOW ... src=refresher`) corre no arranque seguinte do dono. Tudo o que este
  recibo afirma sobre latencia foi medido no harness, com `list_targets` FALSO.
- Nao medi o custo em CPU do fio novo com o `_main/shell-thread-cpu.py` (exigiria a app a correr
  com ESTE codigo). A expectativa declarada: o fio dorme > 99 % do tempo (cadencia 0,5 s/10 s) e
  nao faz nada sem attach.
- Nao medi o comportamento com a porta CDP real (a sonda por aba/corrida de `_choose` no fio):
  o harness usa abas sem `webSocketDebuggerUrl`, logo `_choose` cai em `pick_target`. O caminho
  `pick_playing` dentro do fio nao foi exercitado.
- Nao verifiquei o rebind com um Chrome real a fechar uma aba; a cura foi provada com
  `/json/list` falso e o `_yt_identify` real.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: CdpTargetAsync
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpTargetAsync']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpTargetAsync']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T07:51:56.637401+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpTargetAsync']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CdpTargetAsync']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — o START manda `todo init` na primeira chamada; este toolset nao tem
  `todo`, entao o cartao e o `done` vao no texto do resultado (regra 5). O que faria diferente:
  perguntar ao `Main`, ANTES de desenhar, se o `.cmd` e o pin mudaram de dono — eu desenhei o
  plano com a integracao no meu lado e so' a mensagem a meio o desmentiu.
- **verificacao adicional** — correr o passo `cdp-target-async` dentro de
  `_main/_audit-verify-all.cmd` a serio (nao uma copia): e' o que falta para "LIVE" na bateria, e
  custa o mesmo que o oraculo (2,7 s) mais o cache por conteudo. Nao o fiz porque o ficheiro e'
  do `Main`.
- **checkboxes novas** — `python -c "import ast;ast.parse(open(<novo-oraculo>).read())"` antes de
  o ligar nao chega (ja' passava); o que faltou foi um passo MECANICO que carregue o modulo da
  COPIA do `--neg-arm` com os IRMAOS ao lado: `_load_sibling` rebentou com `FileNotFoundError` e
  o `--neg-arm` morreu a meio em vez de medir. Fica como regra: qualquer oraculo que carregue
  `youtube_cdp_source.py` por `spec` tem de copiar `youtube_window.py` ao lado.
- **review por outro subagente** — `sim-com-escopo — o desenho do cache/`_tid_ttl` e a fronteira
  "um unico pedido pelo chamador" (a razao pela qual os duplos de teste continuam a responder)`.
- **gate-doubt**
  - `verde-de-verdade:` o `VERDICT: PASS` do meu oraculo NAO e' vacuo: o `--neg-arm` corre os
    MESMOS bracos contra duas copias mutadas e exige RED no braco que nomeia (mutante `inline` ->
    `A1-NO-BLOCK FAIL calls=2 total=2.391s`; `sem-slow-log` -> `A3-SLOW FAIL ''`). O
    `code-health` verde para o meu ficheiro tambem nao e' vacuo: o baseline foi escrito com os
    valores MEDIDOS (81035/1670) e a linha do `SAME ... (+0)` prova que o `measure()` leu o
    ficheiro atual. O `agents-md-pins` mediu 284085 B/3441 CRLF sozinho — eu nao toquei no
    ficheiro nem no pin.
  - `falta-no-gate:` o A1 mede `target_video_id()` no harness com um `list_targets` falso; NAO
    mede o laco de legendas real. Um cenario que passa: alguem poe o `_tid_refresh()` tambem no
    fim de `_run` (o fio do websocket) e o `/json/list` lento volta a competir com o attach —
    nenhum braco olha para `_run`. Outro: um mutante que troque a cadencia para 0,05 s (20
    pedidos/s ao Chrome do dono) passa todos os bracos; nada mede a TAXA de pedidos.
  - `gate-melhor:` `python _main/cdp-target-async-oracle.py` com um braco novo `A6-RATE` que
    conta as chamadas a `list_targets` em 2,0 s de fio ligado e exige `<= 2*t+1` (com
    `t=_TID_TTL_S`); entrada que o deixa VERMELHO: `_TID_TTL_S = 0.05`.
- **confianca** — `alta` no que foi medido (6 bracos, 2 mutantes apanhados, 2 oraculos antigos
  verdes, baseline do meu ficheiro absorvido); `media` no comportamento ao vivo, pela ausencia de
  prova na instancia. Subiria com o passo na bateria a serio e um arranque do dono com este
  codigo.
- **nao verificado** — instancia viva (pid 42572 corre codigo anterior); CPU do fio novo com a
  app a correr; `_choose`/`pick_playing` dentro do fio contra Chrome real; rebind com uma aba
  real a fechar; taxa de pedidos (nenhum braco a mede).
