# MAPA DE LATÊNCIA DO SOTTO — onde cada coisa tem de ficar 4x mais rápida

Medido em 2026-11-03 nesta máquina (H:\sotto), instância `pid=20576` e `pid` da
primeira largada de 04:07, a não ser onde a linha diz outra data. Cada número tem
o instrumento ao lado. **Nenhuma linha aqui é estimativa sem marca**: o que não foi
medido leva `[INFERENCE]`.

## O caminho completo, do duplo-clique ao pixel

```
① largada do processo          ② pipeline de legendas   ③ worker carrega modelo
   pythonw → mutex → hotkey       spawn do worker +        75 s (!) — nemotron
   ~1.4 s (medido)                vigia do YouTube         desde o disco
                                 ~0.01 s depois do ①
④ página do painel             ⑤ laço do YouTube          ⑥ pintura da legenda
   WebView2 nav → DOM             1 leitura de UIA            push → ack
   25 s (medido)                  mediana 62 ms / p90 110   62 ms (medido)
                                  / máx 1234 ms (medido)
⑦ alternância do gesto         ⑧ histórico
   press → passo                   append no disco
   34 ms (medido 03:22)           [INFERENCE] ~1-10 ms
```

## Tabela: estágio → hoje → alvo (÷4) → gargalo → onde se mexe

|#|estágio|hoje (medido)|alvo|gargalo real|ficheiro|
|---|---|---|---|---|---|
|①|lancamento → hotkey armada|**1,4 s** (`CAPTION_PIPELINE_START` 04:07:09.139 − `SHELL_STARTUP_STAGE`) — era 74 s antes da cura de 2026-11-03|≤0,35 s|carga de `sotto_webview.py` (17 114 linhas) e imports|`app/webview/sotto_webview.py`|
|②|pipeline de legendas|**0,01 s** depois do ① (`BRIDGE_SPAWNED` 04:07:09.152)|já está|—|idem|
|③|worker carrega o modelo|**75 s** (`BRIDGE_LOAD_MS worker_load_s=74.88`)|≤18 s|pesos + sessão ORT; **e o modelo é recarregado a cada relançamento**|`worker/sotto_worker.py`|
|④|página do painel pronta|**25 s** (`WEBVIEW_NAV start t=17563` → `dom t=42735`)|≤6 s|renderer bloqueado durante o bootstrap da página; `loaded` do pywebview chega 15 s depois do DOM|`app/panel/panel.html`, `app/panel/panel.js`|
|⑤|leitura do YouTube (1 tick)|mediana **62,5 ms**, p90 **110 ms**, máx **1234 ms** (16 amostras, `EXTERNAL_CAPTIONS_READ_MS`, 04:07–04:09)|mediana ≤15 ms|`phases={'target': …}` — resolver o elemento de legenda na árvore de UI Automation a cada tick|`app/webview/youtube_captions.py`, `external_subs.py`|
|⑥|pintura da legenda (push→ack)|**62 ms** (`PAINT_WARM ack_wait_ms=62.0`)|≤15 ms|IPC do overlay nativo + espera de ack|`app/webview/caption_overlay.py`, `overlay_paint.py`|
|⑦|gesto → acção|**34 ms** (`HOTKEY_LIVE_STEP` 03:22:19.844)|≤8 ms|poller de 25 ms (100 ms a arrastar) + fila do overlay|`app/webview/hotkey_gesture.py`, `sotto_webview.py`|
|⑧|histórico|não medido ainda|≤2 ms|append + fsync|`app/webview/history-*`|

## Por que o dono sente "tão pesado"

Três custos independentes, todos medidos, e nenhum é do Chromium em si:

1. **75 s de carga de modelo** por relançamento (③). O worker subia ao fim de 74 s
   porque o arranque só o largava depois do painel carregar; hoje larga em 1,4 s,
   mas o *modelo* continua a levar 75 s a ficar pronto. Duas curas: carregar mais
   depressa (mmap/ORT provider) e **não recarregar** (worker residente).
2. **25 s para uma página local de 700 KB** (④) — e o painel é opcional para a
   legenda. Nada do que o dono vê depende dele.
3. **62 ms por tick de UIA, com picos de 1,2 s** (⑤) — a legenda do YouTube atrasa
   porque a leitura custa mais do que o intervalo de 40 ms. Precisa de um handle
   em cache ou de eventos, não de uma travessia de árvore por tick.

## Peças que não podem ficar no caminho crítico

- O painel **não** é pré-requisito da legenda (já tratado: pipeline arranca antes do
  WebView2).
- O histórico **não** é pré-requisito da pintura.
- O tema do overlay não pode ser aplicado a cada push (já existe
  `CAPTION_OVERLAY_THEME_DEFERRED`).

## 04:40-04:45 — o que ficou cravado (medido nesta árvore, nesta sessão)

| # | o que foi medido | antes | depois | a linha que prova |
|---|---|---|---|---|
| 1 | arranque -> cadeia de legendas | 74 s | **1,4 s** | `CAPTION_PIPELINE_START reason=pre-webview` |
| 2 | desktop em silêncio (o dono a jogar) | recarga do modelo + 3 recusas do tap | **0 recargas** | `BRIDGE_SILENT_BENIGN state=no-audio because="tap-silent-desktop ..." restarts=0` |
| 3 | cache do WebView2 em disco | 448 perfis / 6,4 GB | **0 / 0** | `WEBVIEW2_PROFILE_SWEEP dirs=448 mb=6404` |
| 4 | stdout do worker | bufferizado por blocos (8 KB) | `-u` + `PYTHONUNBUFFERED=1` no argv REAL | `BRIDGE_SPAWNED argv=[... "-u" ...]` |
| 5 | WebView2 e o modelo disputavam a máquina | os dois ao mesmo tempo | o painel espera o modelo, tecto 25 s | `SHELL_WEBVIEW_AFTER_LOAD loaded=.. waited_ms=..` |
| 6 | `EXEC_JS` antes de haver página | um WARN por chamada | `EXEC_JS_DEFERRED`, uma vez | log |

### O piso do worker — medido, e o que o explica

`WORKER_PROVIDERS` aos 53 s e `BRIDGE_LOAD_MS ms=64954` com `worker_load_s=11.0`: o worker
leva ~50 s até escolher providers e 11 s até o modelo carregar. A sonda do CUDA num processo
limpo custa **0,05 s quando o CUDA falha** (`cublasLt64_13.dll` ausente) e é inteiramente o
carregamento das DLLs de CUDA/cuDNN quando ele funciona — logo **não há sonda barata a
remover**: é o preço do GPU nesta máquina. Duas consequências que o número autoriza:

1. não tocar no caminho do provider — qualquer sonda paga o mesmo carregamento;
2. o mesmo modelo em CPU carrega em **0,28 s** contra 11 s (medido, dossier
   `politica-youtube`). Trocar GPU por CPU para o motor AO VIVO é **decisão do dono**, não
   minha: paga-se em qualidade/velocidade de decode para ganhar ~10 s no arranque.

### Ainda por curar, com o número ao lado

- painel: **25 s** de `WEBVIEW_NAV start` a `dom` — a iniciativa presa no
  `ExecuteScriptAsync` do pywebview (o `stage.html` já corta um dos dois saltos).
- leitura UIA do YouTube: **62 ms** por leitura, ~25 leituras/s (`YOUTUBE_TICK_MS n=107/2s`).
- overlay: **62 ms** por pintura.

O resto do caminho (Alt+C 264 ms, gesto, `join_fragments`, monotonicidade) já estava medido
antes desta passagem e não foi tocado aqui.
