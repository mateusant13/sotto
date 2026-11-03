# RECEIPT 2026-11-03 — a shell em repouso, os prazos que morrem e o log que nao cresce

Sessao principal (`I:/!manager`, assento principal), repo `H:/sotto`, 04:4x–06:1x.
Todos os numeros abaixo vieram de um comando que correu nesta sessao; o comando
esta ao lado. O que nao correu esta marcado `[INFERENCE]`.

## 0. O instrumento que faltava: `THREAD_CPU` por NOME

`tid 39712 94,8 %` nao se le. Em CPython no Windows `threading.Thread.ident` E' o
tid nativo (`PyThread_get_thread_ident` devolve `GetCurrentThreadId`), e
`GetThreadTimes` le-se de medium para high — sem py-spy, sem administrador, sem
atrasar a app. Entrou em `app/webview/sotto_webview.py`:

    THREAD_CPU total=101% top=sotto-vram-guard:97% sotto-external-captions:3% ...

Uma linha por minuto, e SO' acima de 20 % no total (abaixo disso o log fica quieto).

O mesmo instrumento respondeu a segunda pergunta de graca: `loops` por 5 s provou
que o laco do observador de teclas faz ~196 voltas a cada 5 s (`poll_s=25 ms`), e
nao esta preso.

## 1. A shell gastava um nucleo inteiro em repouso — 102 % -> 3,7 %

| o que | antes | depois | como |
|---|---|---|---|
| shell (um nucleo) | 102 % | **3,7 %** | `psutil` cpu_times em 8 s, 3 amostras |
| causa | `sotto-vram-guard` | — | `THREAD_CPU` (3 amostras de 30 s) |

A causa era um patch mal ancorado: o `stop_event.wait(INTERVAL_S)` do `VramGuard`
tinha ficado **fora** do `while`, com dois fragmentos de comentario dentro do laco.
O laco passou a perguntar a' NVML em ciclo fechado. `git blame` do sitio: o patch
desta sessao; a `interleaving` explica porque passou — a MESMA linha de espera
existe em mais do que um `run` do ficheiro.

Prova do depois: `pid 28888`, 8 s de amostra, **3,7 %**; e o censo por nome nao
publica nada (total < 20 %).

## 2. Um prazo de sonda que existia no papel e nao matava nada

| o que | medido |
|---|---|
| instancia `--selftest --exit-after 45` (pid 35348, arrancou 03:59:53) | **viva 1 h 45 min** depois do prazo, 130 MB de shell + 115 MB de WebView2 |
| o unico sinal dela | `BRIDGE_STATS_REPLY` de 60 em 60 s |
| arranque que morre em `WEBVIEW2_INIT_FAILED` com `--exit-after 8` | correu **89 s** e teve de ser morto a' mao |
| depois da cura, o mesmo comando | **sai em 10,2 s, rc=0** |

Causa: o prazo era armado no FIM do despacho de probes, depois de
`run_selftest()` — que nunca voltava. Um prazo armado depois do trabalho que nao
acaba nao e' um prazo. Agora nasce em `main()`, com uma rede a' +15 s (`os._exit`)
para o desligamento educado que fica preso.

## 3. O log do dono chegou aos 54 MB; agora cresce 20 linhas/min

`_main/webview-run.log` medido a **54 077 826 B**, com **382** linhas
`HOTKEY_OBSERVER_ALIVE` num unico arranque (720 por hora) e `YOUTUBE_TICK_MS
avg=0 max=0 n=49` congelado escrito de 5 em 5 s.

| depois | valor |
|---|---|
| crescimento | **20,0 linhas/min** (90 s medidos: 30 linhas) |
| `HOTKEY_OBSERVER_ALIVE` | 6 batimentos nos primeiros 30 s, saida imediata se a volta prender (`max_gap_ms > 200`), depois de 5 em 5 min |
| `YOUTUBE_TICK_MS` | via `log_repeat(key, linha, 300)`: sai quando o TEXTO muda |

## 4. Sem player, o leitor perguntava a janela 10x/s

`IDLE_INTERVAL_S = 0.25` existia no ficheiro com o comment certo e era **letra
morta** — o `wait` pedia sempre `INTERVAL_S`. Mesma familia do `VramGuard`.

    antes:  YOUTUBE_TICK_MS n=49 (10 Hz, 49-50 ticks por 5 s)
    depois: YOUTUBE_TICK_MS n=20 (4 Hz, 20 ticks por 5 s)

Instancia viva pid 49316, player fechado, 5 s por janela.

## 5. Um estado publicado antes do form deixou de se perder

O pipeline de legendas arranca antes do WebView2 de proposito, e o mesmo arranque
publica `Starting worker...`, `boot`, `model-loading` — todos caidos em
`EMIT_DROPPED reason=no-form`. Agora o ultimo payload de cada `kind` espera e sai no
primeiro post:

    EMIT_DROPPED kind="status" reason=no-form queued=true (x5)
    EMIT_FLUSHED kinds=1 after-first-post="geometry"
    STATUS_APPLIED text="model-loading"  ->  boot, model-loaded, gate, device, ...

## 6. O arranque do worker: 24,35 s -> 5,43 s (lane WorkerBoot, receipt proprio)

`worker/_probe/boot-io.py`, modo ficheiro, A/B contra o worker de HEAD:
`import torch` 7,88 s -> 0,05 s, sonda CUDA descartada 3,54 s -> 0,
`og.Model` fora do caminho 7,71 s -> 0, leitura de arranque 340 MB -> 126 MB.
Na instancia viva de hoje: `BRIDGE_LOAD_MS ms=4531` / `ms=6297` / `ms=6234`
(`worker_load_s` 4,16 / 5,52 / 5,6).

## 7. A legenda do YouTube 1:1 (lane YtLand + fiacao do assento, receipt proprio)

O cue do player passa a viajar com o RELOGIO dele ate' a janela nativa:
`_tick -> external_caption(cue=) -> push_caption_to_window(cue=) ->
_caption_pending_cue -> ov.set_text(..., cue=cue)`.
Provas: cadeia completa sem janela (overlay recebe rows=1, t=12.5, `shown=True`);
`_main/youtube-land-oracle.py --neg-arm` 6/6 mutantes; `youtube-1to1` GREEN 11/11
com 13/13 mutantes; `reveal-park` 5/5 com `--neg-arm` 3/3.

**NAO PROVADO AQUI:** nenhum `CAPTION_LAND` foi visto num log vivo — exige um player
a tocar. O `land_lag_ms` continua por medir em producao.

## 8. Portoes que correram nesta sessao

| portao | veredicto |
|---|---|
| `undefined-names-oracle` | GREEN, 18 ficheiros |
| `altc-gesture-oracle` | GREEN, arms=86 pass=86 |
| `youtube-1to1-oracle` | GREEN 11/11; `--neg-arm` 13/13 |
| `reveal-park-oracle` | GREEN 5/5 (era RED 3/5 por culpa do FAKE); `--neg-arm` 3/3 |
| `word-split-oracle` | PASS |
| `caption-producer-oracle` | PASS 8/8 |
| `caption-style-oracle` | PASS 6/6 |
| `app-target-oracle` | PASS, live 9/9, dois mutantes RED-as-expected |
| `agents-md-pins-oracle` | PASS |
| `claims-date-oracle` | PASS, checks=4 |
| `exception-hygiene-oracle` | PASS apos baseline (deltas sao de 2026-10-20/10-06, nao de hoje); `--neg-arm` 4/4 |
| `live-code-freshness-oracle` | FRESH (hash do processo == hash do disco) |
| `code-health-oracle` | **FAIL** — ver divida em §9 |

## 9. Divida registada (nao escondida)

* `_youtube` em `sotto_webview.py` cresceu 292 -> **531 linhas**. Lane `YoutubeSplit`
  despachada para extracao pura (limite: `_youtube` < 120 linhas, nenhum helper > 120,
  zero mudanca de comportamento, provado por 1to1 + reveal-park + land).
* `code-health` tem 34 metricas piores desde 2026-11-02 22:02 (era `piorem: 0`): sao
  bytes/linhas/defs de funcionalidade que aterrou hoje (worker boot, overlay, load
  shedding, fiacao do cue). O baseline so' se atualiza com esta lista escrita.
* 41 pastas medidas em `H:/sotto-wt` + `I:/wt` = **1184 MB**; `git worktree prune`
  removeu 11 registos estaleiros (17 -> 6 registados). As pastas nao registadas
  ficam para decisao do dono: algumas tem trabalho nao commitado de outras lanes.
