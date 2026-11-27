# 06 — YOUTUBE: a fonte externa, o relógio, as línguas

Este ficheiro descreve a única fonte do Sotto que não vem do microfone: a legenda que o próprio YouTube já tem. Tudo foi lido no código em `HEAD` (2026-11-11) ou medido no log da instância do dono; nenhum número foi copiado de outro documento. Os `[MEASURED]` de log vêm de `_main/webview-run.log`, 207 056 linhas, última escrita `2026-11-11 22:57` `[MEASURED] wc -l _main/webview-run.log → 207056`. O `sotto_webview.py` tem mtime 23:11, **depois** do fim do log `[MEASURED] ls -l --time-style=+%Y-%m-%d\ %H:%M app/webview/sotto_webview.py → 2026-11-11 23:11`; as contagens de shell podem não incluir a última edição — ver `## Lacunas`.

## 1. Porque é que a fonte existe

O dono pediu a legenda **do vídeo**, não o texto da página: *"faz a legenda do youtube mostrar na tela em tempo real. se precisar pegar o tempo do video, faça"* `[CODE] app/webview/youtube_captions.py:3-7`. O caminho antigo (`external_subs.py`, UI Automation) lia o que a página pintava, e o que chegou à caixa em 2026-10-19 foram `Oferta sujeita aos termos. Cancele quando quiser.` e `há 4 sem.` — chrome da página, não fala do vídeo `[CODE] app/webview/youtube_captions.py:15-22`.

A fonte responde a duas perguntas separadas, e é a junção delas que produz uma legenda em tempo real: *qual é a faixa deste vídeo* e *em que instante o player está* `[CODE] app/webview/youtube_captions.py:18-21`. A ASR nunca é desligada por esta fonte: sem faixa, a regra do dono é transcrever ao vivo — *"se for um video sem legenda, vaio transcrever ao vivo igual"* `[CODE] app/webview/youtube_captions.py:34-38`. Os quatro ficheiros que a implementam somam 5 903 linhas — `youtube_captions.py` 2 515 (faixa, cache, parse, relógio UIA), `youtube_cdp_source.py` 2 393 (o DOM via CDP e a escolha de aba), `youtube_clock.py` 184 (funções puras do relógio), `youtube_reveal.py` 811 (a revelação e o motor de desenho) — e a eles juntam-se `youtube_monotonic.py` (285) e `youtube_window.py` (551) `[MEASURED] wc -l app/webview/youtube_*.py → 184 285 551 811 2393 2515 (2026-11-11)`. Medido de novo em 2026-11-27: `wc -l app/webview/youtube_window.py → 549`; os números de 2026-11-11 ficam como registo, não como linha citada.

## 2. As duas rotas: a árvore e a CDP

As duas rotas leem **a mesma coisa** — a linha que o player desenha — e diferem no canal: a árvore de acessibilidade (UI Automation) entrega os filhos da janela de legenda; a CDP entrega o DOM da mesma janela. A segunda existe por uma razão medida: com a aba em segundo plano o Chrome deixa de expor a janela de legenda na árvore, e o Sotto ficava sem fonte nenhuma `[CODE] app/webview/youtube_cdp_source.py:3-14`.

### 2.1 A ordem em que as rotas são tentadas

`_youtube` é o único ponto de decisão `[CODE] app/webview/sotto_webview.py:5513-5645`. Só janelas reconhecidas como YouTube entram neste ramo: a string `'external:youtube'`, ou uma URL `youtube.com/watch` convertida nela `[CODE] app/webview/sotto_webview.py:4458-4466`; as outras seguem a varredura de página, que serve quem pinta a legenda no próprio HTML (Stremio) `[CODE] app/webview/sotto_webview.py:4505-4535`. A ordem é: `_yt_identify` resolve o `videoId` (foto CDP primeiro, árvore só se não há foto) `[CODE] app/webview/sotto_webview.py:5628-5780` → `_yt_cdp_fast_lines` devolve as `rows` da foto CDP **e termina** `[CODE] app/webview/sotto_webview.py:5849-5876` → `_youtube_painted` lê as palavras da árvore `[CODE] app/webview/sotto_webview.py:4886-4930` → `_yt_cdp_lines` é o segundo consumidor da mesma foto (ver §2.4) `[CODE] app/webview/sotto_webview.py:5982-6016` → `_yt_track_poll` pede a faixa sem bloquear e a pintura alinha-a; sem pintura, a cue é servida pelo relógio `[CODE] app/webview/sotto_webview.py:5480-5511,5608-5643`.

Medido: o caminho CDP alimenta o ecrã de facto — 13 798 dos 13 870 `YT_FRAME` saem com `src=external:youtube:track`, 72 com `src=external:youtube:liveframe` `[MEASURED] grep -o "YT_FRAME src=[^ ]*" _main/webview-run.log | sort | uniq -c (2026-11-11)`.

### 2.2 `parse_snapshot`: o que conta como linha

`EXTRACT_JS` corre na página e devolve `videoId`, `title`, `rows`, `segs`, `t`, `paused`, `rs`, `rate`, `why` `[CODE] app/webview/youtube_cdp_source.py:159-210`. A geometria é `getBoundingClientRect` (viewport, nunca coordenadas de ecrã) e uma linha só conta se estiver **pelo menos meia dentro** do clip de `overflow: hidden`; as que rolaram para fora continuam no DOM e são descartadas `[CODE] app/webview/youtube_cdp_source.py:181-196`.

`parse_snapshot` é puro e testável sem Chrome `[CODE] app/webview/youtube_cdp_source.py:766-824`: payload que não é JSON ou não é `dict` → `None` `[CODE] app/webview/youtube_cdp_source.py:768-774`; texto de cada linha e de cada filho passa por `strip_speaker_markers` e vazio é descartado `[CODE] app/webview/youtube_cdp_source.py:784-796`; os quatro cantos de cada `items[]` são `int` e **uma linha sem filhos não é uma linha** (`if not kids: continue`) `[CODE] app/webview/youtube_cdp_source.py:797-806`; devolve `stamp`, `videoId`, `t`, `paused` (`None` **fica** `None`), `rate`, `rs`, `title`, `rows`, `items`, `why` `[CODE] app/webview/youtube_cdp_source.py:807-823`.

### 2.3 O marcador `>>` e a semântica de `no-captions`

A lista de marcadores é do `youtube_window` e o caminho CDP importa-a **pelo caminho**, para não haver duas listas que divergem no primeiro marcador novo `[CODE] app/webview/youtube_cdp_source.py:52-75`. Os marcadores são `>>`, `&gt;&gt;` e `››` `[CODE] app/webview/youtube_window.py:246`; `strip_speaker_markers` tira-os do **início** (em laço) e do **meio** da linha, porque o player abre o turno de quem fala a seguir e o painel pode juntar dois segmentos `[CODE] app/webview/youtube_window.py:351-374`.

A palavra `no-captions` **não existe no código**: `grep -rn "no-captions" app/webview/*.py` devolve zero linhas `[MEASURED] 2026-11-11`. O que existe são ausências diferentes, e confundi-las é o defeito que o módulo impede:

| ausência | valor real | significado |
|---|---|---|
| o DOM não tem linha visível | `why='no-painted-caption'` (`'no-window'` sem contentor) | o player não pinta nada **agora** `[CODE] youtube_cdp_source.py:164,176,197` |
| o vídeo não tem faixa | `state='no-track'` | não há faixa para servir `[CODE] youtube_captions.py:526-536` |
| a faixa existe, o instante não tem cue | `state='no-cue-in-window'` | o player também não mostra nada aqui `[CODE] youtube_captions.py:526-536` |
| o instante não é conhecido | `state='time-unknown'` | **não** é "o vídeo está parado" `[CODE] youtube_captions.py:531-533` |

Os quatro estados são o contrato inteiro `[CODE] app/webview/youtube_captions.py:163`. Quando a faixa não é `has-track`, `_youtube` chama `_yt_forget(..., urgent=True)` e `_read_inner` faz `_release('youtube-no-track')` — o ASR volta **agora** `[CODE] app/webview/sotto_webview.py:5591-5592,4488-4492`. Os silêncios de pinta-e-não-pinta não o devolvem: a faixa pisca, e cada piscar custaria uma carga de modelo — `YT_RELEASE_S` é 30,0 s contra `RELEASE_S` 1,8 s `[CODE] app/webview/sotto_webview.py:3893-3901`.

### 2.4 O segundo consumidor da foto, e a prova de que não fala

`_yt_cdp_lines` existe para publicar `YOUTUBE_CAPTION`, mas o passo 2 devolve a resposta antes dele e limpa `yt_cdp_rows` no próprio `_yt_rows_impl` `[CODE] app/webview/sotto_webview.py:5862-5876,4843-4852`. Medido: **0** linhas `YOUTUBE_CAPTION` contra 13 315 `YOUTUBE_TICK_MS` e 13 798 frames do tipo `track` `[MEASURED] grep -c YOUTUBE_CAPTION _main/webview-run.log → 0; grep -c YOUTUBE_TICK_MS → 13315 (2026-11-11)`. `[INFERENCE]` O caminho é inalcançável no regime normal; é duplicação morta, não rota alternativa.

## 3. Que aba: `pick_target`, a sonda e o id assíncrono

### 3.1 A decisão pela lista de abas

`pick_target(tabs, video_id="", window_title="")` decide só com a lista HTTP `[CODE] app/webview/youtube_cdp_source.py:900-940`; o título da janela vem **antes** do id declarado porque o id é uma crença e o título é o que ele está a ver `[CODE] app/webview/youtube_cdp_source.py:912-927`.

| ordem | condição | motivo |
|---|---|---|
| 1 | título da janela casa **exactamente** com uma aba / é substring de uma só | `window-title` / `window-title-partial` |
| 2 | o `video_id` declarado aparece no URL | `named` |
| 3 | há id declarado mas não está aberto | `video-not-open` |
| 4 | mais de uma aba `watch` e nada decidiu / uma só / nenhuma | `ambiguous` / `only-tab` / `no-youtube-tab` |

### 3.2 A decisão pela sonda

`choose_target` é a regra completa, e cada degrau tem testemunha `[CODE] app/webview/youtube_cdp_source.py:605-695`:

| degrau | motivo | testemunha |
|---|---|---|
| 0 | `no-player` | nenhuma aba tem jogador |
| 1 | `foreground` | `visibilityState='visible'` **e** `document.hasFocus()`; prefere a que toca |
| 2 | `window-title` / `-partial` | título da janela contra título da aba |
| 3 | `playing` | `currentTime` avançou entre duas leituras |
| 4 | `declared` | o id declarado, **verificado** com jogador |
| 5 | `sticky-last` / `keep-declared` | o último adoptado com jogador; senão o declarado que continua na lista |
| 6 | `only-player` / `paused-loaded` | eliminação; entre pausados, o mais avançado |

`is_real_player` descarta a aba sem linha temporal: `rs == 0` é uma aba descartada pelo Chrome, e `paused=false` numa aba sem vídeo é o que a regra antiga lia como "a tocar" `[CODE] app/webview/youtube_cdp_source.py:463-490`. Cada aba leva **duas** leituras de `currentTime` separadas por 0,12 s; o que separa "toca" de "parado" é a diferença, não a bandeira `paused` `[CODE] app/webview/youtube_cdp_source.py:242,380-420`. As abas são sondadas em paralelo, no máximo 6, com 0,35 s por aba e orçamento de **relógio** de 0,5 s; o que não chegou é descartado `[CODE] app/webview/youtube_cdp_source.py:237,270-271,450-459`. Medido: 64 `YOUTUBE_PROBE_BUDGET`, dos quais 12 com **todas as 6 abas abandonadas** `[MEASURED] grep -o "YOUTUBE_PROBE_BUDGET tabs=[0-9]* done=[0-9]* abandoned=[0-9]*" … | awk '{print $4}' | sort | uniq -c → 36×1, 9×2, 1×3, 3×4, 3×5, 12×6 (2026-11-11)`.

### 3.3 `YOUTUBE_TARGET_STALE` e o fio `yt-cdp-target`

O nome usado pelo chamador é `YT_TARGET_STALE`, mas a linha escrita é `YOUTUBE_TARGET_STALE` `[CODE] app/webview/youtube_cdp_source.py:1790-1810`. Sai quando a idade do id publicado passa de **duas cadências** do refrescador (`age > ttl * 2`), no máximo uma vez por 5,0 s `[CODE] app/webview/youtube_cdp_source.py:1060,1791-1801`.

O `/json/list` não é pago pelo laço da legenda: é pago pelo fio `yt-cdp-target`, que publica `(hora, video_id)` em memória `[CODE] app/webview/youtube_cdp_source.py:1068-1081,1720-1770`. `target_video_id()` é leitura de memória; sem valor publicado, entrega o pedido ao mesmo fio e espera 0,10 s; com ligação e sem publicação espera 0,30 s `[CODE] app/webview/youtube_cdp_source.py:1055,1064,1640-1680`. A cadência é 0,5 s; uma chamada acima de 500 ms estica-a para 10,0 s até voltar a ser barata `[CODE] app/webview/youtube_cdp_source.py:1041,1049,1955-1975`. Medido: 2 823 `YOUTUBE_TARGET_SLOW`, média **1 310,45 ms**, máximo **94 672 ms**, e **todas** com `ttl_s=10` `[MEASURED] grep -o "YOUTUBE_TARGET_SLOW ms=[0-9.]*" … | awk -F= '{s+=$2;n++;if($2>m)m=$2} END {print n, s/n, m}' → 2823 1310.45 94672 (2026-11-11)`. É este número que justifica o fio.

### 3.4 As classes de tempo-limite e de religação

| classe | valor | efeito | evidência |
|---|---|---|---|
| 1.ª leitura de uma ligação nova | 0,5 s | alvo que não é o jogador não custa 3 s | `[CODE] youtube_cdp_source.py:150` |
| leituras seguintes | 3,0 s | página lenta não fecha a ligação | `[CODE] youtube_cdp_source.py:140` |
| sonda de attach (`/json/list`) | 1,5 s | porta fechada vs máquina carregada | `[CODE] youtube_cdp_source.py:130` |
| espera entre attaches | 2,0 → 8,0 s (dobra) | para de bater a uma porta morta | `[CODE] youtube_cdp_source.py:110,122` |
| 3 prazos seguidos no mesmo socket | 3 | `slow-dead`: fecha e religa | `[CODE] youtube_cdp_source.py:135` |
| sem ninguém a ler / vídeo pausado | 120 s / 0,5 s | fecha o socket; não pede 12 Hz a um vídeo parado | `[CODE] youtube_cdp_source.py:102,106` |

Os motivos são **nomeados**, não um `except` genérico: `_probe_reason` distingue `port-closed` (só `ConnectionRefusedError`), `probe-timeout` e `probe-failed (<Name>)` `[CODE] app/webview/youtube_cdp_source.py:836-856`. Medido: 45 `probe-timeout`, 6 `ambiguous`, 7 `no-player` `[MEASURED] grep -o "YOUTUBE_CDP_ATTACH_FAILED attempt=[0-9]* ok=false reason=[^ ]*" … | grep -o "reason=[^ ]*" | sort | uniq -c (2026-11-11)`. A troca de aba invalida o socket: `_adopt_tab` sobe `_epoch`, o `_run` compara-o com o da ligação aberta e re-liga **no primeiro prazo** `[CODE] app/webview/youtube_cdp_source.py:1479-1510,2040-2070,2155-2165`; o motivo escrito é `tab-stale` `[CODE] app/webview/youtube_cdp_source.py:2066,2162`.

## 4. O relógio do player

### 4.1 `youtube_clock`: três estados e nenhum número redondo

As três palavras que o resto testa são `PLAYING`, `PAUSED`, `ENDED` (e `UNKNOWN` para a ausência de resposta) `[CODE] app/webview/youtube_clock.py:48-51`. `player_state` traduz as bandeiras: `paused` vence `ended`, e a ausência de `playing` é `UNKNOWN` `[CODE] app/webview/youtube_clock.py:78-84`.

| constante | valor | porquê |
|---|---|---|
| `FRESH_S` | 0,30 s | amostra mais nova é **autoritativa**; a CDP publica a ~12 Hz |
| `HOLD_S` | 8,0 s | 5 s (pior stutter do contrato) × 1,6 |
| `BUDGET_S` | 0,15 s | o orçamento de erro pedido pelo dono |
| `DRIFT_MEASURED_S` / `DRIFT_WINDOW_S` | 0,034 s / 8,0 s | a deriva medida do relógio do player |
| `MAX_HOLD_BY_DRIFT_S` | 35,29 s | o que a física permitiria; **não** é o tecto |

`[CODE] app/webview/youtube_clock.py:57-75`. `instant(base_t, age, rate, state, hold)` é a regra inteira `[CODE] app/webview/youtube_clock.py:121-158`: `PAUSED`/`ENDED` devolvem a amostra com avanço 0; `UNKNOWN` devolve a amostra com avanço 0 e diz se já não há âncora; `PLAYING` devolve `base + min(age, HOLD_S) * rate`, e um `rate` fora de `[0.05, 16.0]` cai para 1,0. O `rate` é o `playbackRate` do `<video>`, lido no mesmo snapshot e publicado em `yt_cdp_rate` `[CODE] app/webview/sotto_webview.py:5303-5308; app/webview/caption_overlay.py:275-292`.

**A regra do rebase.** Uma amostra com idade ≤ `FRESH_S` é autoritativa, e o que **nós** advinhamos é nosso para desfazer: `rebase(floor, t, invented, eps=0.05)` baixa o chão para `t` quando a diferença cabe no avanço inventado, e mantém o chão quando é maior — aí é um seek, e quem o declara é a pintura `[CODE] app/webview/youtube_clock.py:160-184`. `sample_instant` aplica as duas coisas juntas e guarda `_yt_guess_s` `[CODE] app/webview/youtube_clock.py:100-118`. O instante servido nunca recua por leitura atrasada: `youtube_monotonic.decide` só deixa o relógio andar para a frente, e `advance` sobe o chão com a pintura e só o desce num salto para trás maior que `SEEK_BACK_S = 2,0 s` `[CODE] app/webview/youtube_monotonic.py:47-85`.

### 4.2 O relógio parado: `_yt_clock_static`

Uma bandeira `paused=false` pode mentir. `_yt_clock_static` compara `t` entre leituras sucessivas e, se o mesmo valor se mantiver por `CLOCK_STATIC_PAUSE_S = 2,0 s`, declara o player parado e publica `YOUTUBE_CLOCK_STATIC` **uma vez** `[CODE] app/webview/sotto_webview.py:5087-5124,5324-5335`. `t` ausente não é pausa: ausência de medida nunca vira afirmação `[CODE] app/webview/sotto_webview.py:5103-5112`. Medido: **0** linhas `YOUTUBE_CLOCK_STATIC`, contra 5 478 `YOUTUBE_CLOCK_HELD` `[MEASURED] grep -c YOUTUBE_CLOCK_STATIC _main/webview-run.log → 0; grep -c YOUTUBE_CLOCK_HELD → 5478 (2026-11-11)`; `[INFERENCE]` o ramo não foi exercitado nesta instância.

## 5. As bordas de pausa/fim e o que apaga os pixels

`_yt_pause_edge(now_paused)` recebe `paused or ended` a cada snapshot e trata a **borda** `[CODE] app/webview/sotto_webview.py:5126-5168`. Na subida incrementa `_yt_pause_epoch` e, **se a janela está visível**, chama `_blank_caption_window('youtube-paused')` ou `('youtube-ended')` `[CODE] app/webview/sotto_webview.py:5148-5157`. Na descida, se há `last_line` e a legenda está ligada, volta a empurrar a última linha com as `rows` e o `cue` congelado `[CODE] app/webview/sotto_webview.py:5158-5168`.

O `_tick` consome o epoch mas **não pinta** em pausa: o desenho congelado foi removido em 2026-11-09 porque mantinha os pixels vivos num vídeo parado `[CODE] app/webview/sotto_webview.py:6733-6744`. O congelamento do texto é feito no **payload**, não no motor: com `paused`, `ended`, ou `playing is not True`, `_yt_cue_payload` passa as linhas por `freeze_rows`, que corta palavras com `start > t` e devolve `end=None`, `words=[]`, `cap=None` — o mesmo texto em qualquer instante `[CODE] app/webview/sotto_webview.py:6425-6449; app/webview/youtube_cdp_source.py:555-580`. Medido: 277 `CAPTION_WINDOW_BLANKED reason=video-changed`, 10 `reason=youtube-paused-or-ended`, 8 `reason=youtube-paused`, 12 `reason=no-caption-for-…` e 6 `reason=panel-hidden` `[MEASURED] grep -o "CAPTION_WINDOW_BLANKED reason=[a-z-]*" _main/webview-run.log | sort | uniq -c (2026-11-11)`.

`YOUTUBE_TICK_MS` não é por tick: é o agregado de 5,0 s, escrito por `log_repeat` só quando o número muda `[CODE] app/webview/sotto_webview.py:4176-4190`. Formato: `avg=<ms do tick> max=<ms> n=<ticks na janela> src= vid= cdp_age_ms= rows= why=`; exemplo medido `avg=0 max=0 n=20 src='unattached' vid='JM1gEnmaUao' cdp_age_ms=250 rows=0 why='cdp-fresh-skip'` `[MEASURED] grep "YOUTUBE_TICK_MS" _main/webview-run.log | tail -3 → 22:56:13.374 … n=20 (2026-11-11)`. A cadência é decidida por `poll_step`, função pura de três razões `[CODE] app/webview/sotto_webview.py:3757-3778`:

| condição | passo | evidência |
|---|---|---|
| base | `INTERVAL_S = 0,10 s` | `[CODE] sotto_webview.py:3876` |
| ≥ 5 s sem leitura de player, ou vídeo pausado | `IDLE_INTERVAL_S = 0,25 s` | `[CODE] sotto_webview.py:3776-3777,3882` |
| leitura anterior > `READ_SLOW_MS = 200 ms` | 0,25 s durante 1,0 s | `[CODE] sotto_webview.py:3757-3759` |

Entre leituras o desenho é recomposto a `RENDER_S = 0,06 s` sem uma chamada Win32 `[CODE] app/webview/sotto_webview.py:3887,4200-4235`. Medido: `EXTERNAL_CAPTIONS_READ_STATS n=424 mean_ms=7.0 p95_ms=16.0 max_ms=31.0 interval_s=0.10 step_s=0.25` e `YOUTUBE_LOOP_HZ ticks=78 ok=78 none=0 age_ms=260 hz=7.7` `[MEASURED] grep … | tail -1 _main/webview-run.log (2026-11-11)`.

## 6. A política de línguas é LEI

`UNTRANSLATED_LANGS = ('en', 'pt', 'es')` é a lista intocável `[CODE] app/webview/youtube_captions.py:625`. `_target_langs(orig)` devolve, por esta ordem `[CODE] app/webview/youtube_captions.py:660-705`:

| língua original | lista devolvida | consequência |
|---|---|---|
| desconhecida (`orig` vazio) | `(TARGET_OVERRIDE,)` se houver escolha; senão `()` | a regra não pode falar |
| `en`, `pt` ou `es` | `(base,)` — **um só elemento** | servido na própria língua; sem fallback |
| outra, alvo ≠ original | `(target, orig)` | tradução para a língua **escolhida**; o original como último recurso |
| outra, alvo == original | `(base,)` | pedir a mesma faixa duas vezes é desperdício |

O código que decide é literalmente `if base in UNTRANSLATED_LANGS: return (base,)` e `return (target, orig)` `[CODE] app/webview/youtube_captions.py:696-705`; `target` é `_base_lang(TARGET_LANG)` `[CODE] app/webview/youtube_captions.py:568,699`. **O docstring do mesmo bloco diz outra coisa** — "any other language (Chinese, Japanese, ...): ENGLISH" `[CODE] app/webview/youtube_captions.py:676-683`. `[INFERENCE]` O texto descreve a ordem de 2026-10-30; a ordem de 2026-11-08 mudou o alvo para a língua escolhida e o docstring ficou para trás. Quem manda é o código — e o comentário de `caption_settings` diz o mesmo que ele `[CODE] app/webview/caption_settings.py:1-12`.

`TARGET_LANG` é lido do disco no import `[CODE] app/webview/youtube_captions.py:609`. O módulo dos ajustes tem `DEFAULT_TARGET = 'pt'` e o caminho `_main/caption-settings.json`, desviável por `SOTTO_CAPTION_SETTINGS` `[CODE] app/webview/caption_settings.py:22,29-33`. `target_lang()` normaliza para a base e **nunca** devolve vazio; `save()` escreve temporário-e-renomeia e uma falha não levanta `[CODE] app/webview/caption_settings.py:44-47,62-76`. `set_target_language()` grava, actualiza `TARGET_LANG` e guarda a escolha em `TARGET_OVERRIDE` `[CODE] app/webview/youtube_captions.py:637-657`. O override **não** fura a lei num vídeo de língua conhecida: só é usado quando `orig` é vazio `[CODE] app/webview/youtube_captions.py:686-696`. Medido: o ficheiro em disco é `{"target_lang": "pt"}`, 26 bytes, mtime `Nov 11 20:01` `[MEASURED] cat _main/caption-settings.json; ls -l _main/caption-settings.json (2026-11-11)`.

As 2 341 linhas `YOUTUBE_TRACK_READY` distribuem-se assim `[MEASURED] grep -o "YOUTUBE_TRACK_READY video_id=[^ ]* state=[a-z-]* cues=[0-9]* lang=[^ ]* source=[^ ]* reason=[a-z-]*" … | awk '{print $3,$5,$6,$7}' | sort | uniq -c (2026-11-11)`: `has-track`/`ok` com `en-orig` auto 1 610, `pt-orig` auto 350, `pt-BR` manual 143, `en` manual 3; `no-track` com `extract-failed` 226 e `no-tracks-listed` 9.

A distribuição prova duas coisas: a faixa **manual** ganha quando existe na língua permitida, e o `-orig` é preferido ao traduzido dentro da automática `[CODE] app/webview/youtube_captions.py:730-761,789-860`; `_pick_entry` prefere `json3` e recusa o `m3u8_native`, porque uma playlist HLS não é um documento WebVTT `[CODE] app/webview/youtube_captions.py:763-788`.

## 7. Trocar de vídeo e de faixa: quanto custa

`_yt_switch_video` muda o id, limpa `yt_cue`, zera o chão de monotonia e apaga a janela **uma vez**, no fim, depois de o estado antigo ser limpo `[CODE] app/webview/sotto_webview.py:5766-5845`. A confirmação de um alvo novo é `YT_REBIND_CONFIRM_S = 1,5 s`, mas é dispensada quando a foto do candidato **já tem linhas** dele: `rows_for(snap, candidate)` devolve `adopt` em vez de `damped` `[CODE] app/webview/youtube_cdp_source.py:1112-1165; app/webview/sotto_webview.py:3908`. Medido: 57 `YOUTUBE_TARGET_REBIND_DAMPED`, 17 `_ARMED`, 92 `_REBOUND` `[MEASURED] grep -o "YOUTUBE_[A-Z_]*" _main/webview-run.log | sort | uniq -c (2026-11-11)`.

O custo real de uma troca, do id novo até ao primeiro `YT_FRAME` com texto novo: `17:51:52.951 → 17:51:53.722 = 771 ms` e `20:01:01.809 → 20:01:08.929 = 7 120 ms` (o segundo inclui adopção de aba, `why=tab-switch`) `[MEASURED] pares de `YOUTUBE_VIDEO_CHANGED` e o `YT_FRAME` seguinte, no mesmo log (2026-11-11)`. O pedido da faixa é *fire-and-forget*: `YouTubeTrackThread.request` só escreve o pedido e devolve o que estiver pronto; quem corre o `yt-dlp` é o fio dela `[CODE] app/webview/sotto_webview.py:3603-3660`. Medido: `YOUTUBE_TRACK_ASK_MS ms=15.0 vid=JM1gEnmaUao polls=37619 new=0` — 15 ms no pior caso, com 37 619 perguntas `[MEASURED] grep "YOUTUBE_TRACK_ASK_MS" _main/webview-run.log | tail -1 (2026-11-11)`.

O custo que se evita é a extracção: o `yt-dlp` custou **5,0 s** por vídeo quando foi medido `[CODE] app/webview/sotto_webview.py:3519-3531` (número histórico do comentário; ver `## Lacunas`). A lista de candidatos (com URLs assinadas) fica em cache por `CANDIDATE_TTL_S = 1 800 s` e é re-escolhida para o player de agora, sem outra extracção `[CODE] app/webview/youtube_captions.py:994,921-980`; a procura pela pintura está limitada a `_PAINT_SEARCH_MAX = 6`, verificado **antes** do fetch `[CODE] app/webview/youtube_captions.py:2124,1360-1395`. Quando o dono troca de vídeo, o resultado da faixa antiga não contamina o novo: o fetch superseded é descartado e **não** arma a janela de `REFRESH_S` que faria o vídeo novo esperar atrás dele `[CODE] app/webview/sotto_webview.py:3705-3725`. Medido: 12 `YOUTUBE_TRACK_DROPPED` `[MEASURED] grep -c YOUTUBE_TRACK_DROPPED _main/webview-run.log → 12 (2026-11-11)`.

## 8. A revelação 1:1: `youtube_reveal` e `_PlayerCue.roll`

`youtube_reveal.frame(rows, t)` é a **única** regra de desenho; as duas fontes (YouTube e ASR) só produzem `rows` com a mesma forma `[CODE] app/webview/youtube_reveal.py:340-380,489-540`. A janela é `CAPACITY = 2` linhas mais `ROLLUP_ROWS = 1` a sair `[CODE] app/webview/youtube_reveal.py:85,93`; uma linha que acabou continua desenhada durante `EXIT_S = 0,45 s` e o alfa desce até 0 `[CODE] app/webview/youtube_reveal.py:407,489-540`. O corte do texto é o **prefixo** que os relógios das palavras já revelaram, e o `cap` do chamador é o tecto: `min(cap, relógio)` `[CODE] app/webview/youtube_reveal.py:446-462`; o `cap` vem de `window_by_paint`, que usa `aligned - painted_from` — quantas palavras o player já pintou `[CODE] app/webview/youtube_reveal.py:110-125,283-337`. O `\n` dentro do texto é uma quebra **do player** e não é colapsado `[CODE] app/webview/youtube_reveal.py:201-211`; o `>>` fica no texto mas **não gasta orçamento de revelação** — conta zero em `speech_words` e em `first_words` `[CODE] app/webview/youtube_reveal.py:129-198`.

O overlay guarda as linhas com o instante do vídeo (`t`), o `monotonic` da leitura (`at`) e o `rate` `[CODE] app/webview/caption_overlay.py:267-286`. O relógio em vigor é `t + (agora - at) * rate`, limitado a `PLAYER_HOLD_S = 3,0 s` e nunca abaixo do `floor` já desenhado `[CODE] app/webview/caption_overlay.py:210,293-300`. `_PlayerCue.roll(now)` devolve 0,0 → 1,0 do deslocamento vertical: sem linha a sair devolve 0,0; senão usa `displaced_at` (o `start` da linha que empurrou) e `youtube_reveal.roll_progress(clock - displaced_at, EXIT_S)` `[CODE] app/webview/caption_overlay.py:317-334`. A curva e a duração são as do player — 0,433 s e `cubic-bezier(0, 0, .2, 1)` — e o `y` é resolvido por bissecção de 40 iterações `[CODE] app/webview/youtube_reveal.py:542-600`.

O payload é curto de propósito: `_yt_cue_payload` manda as cues entre `base_t - 1,0 s` e `base_t + 3,0 s`, com `rate`, e em pausa manda o resultado de `freeze_rows` `[CODE] app/webview/sotto_webview.py:6385-6449`. Medido: 115 `YOUTUBE_PAINT_STALE` com `painted_age_s` de 1,6–1,7 s, ou seja o ramo "a pintura congelou, quem manda é a faixa" foi exercitado `[MEASURED] grep "YOUTUBE_PAINT_STALE" _main/webview-run.log | tail -3 → 1.7 / 1.6 / 1.6 (2026-11-11)`. O limiar do `PaintStall` é `STALE_S = 1,5 s` de relógio de vídeo com a mesma assinatura `[CODE] app/webview/youtube_monotonic.py:136,155-235`.

## Lacunas

- `[UNKNOWN]` **A extracção de 5,0 s não foi re-medida**; o número é comentário de 2026-10-19 `[CODE] app/webview/sotto_webview.py:3519-3531`. Fechar: `extract_info(skip_download)` sobre um vídeo público, cronometrado. Exige rede não autorizada.
- `[UNKNOWN]` **`YOUTUBE_SWITCH_FIRST_FRAME` não aparece no log** (`grep -c → 0`), apesar de existir no código `[CODE] app/webview/sotto_webview.py:6008-6012`. Fechar: corrida com troca de id real e a tag lida.
- `[UNKNOWN]` **`YOUTUBE_CLOCK_STATIC` nunca disparou**: não há prova de execução do ramo do relógio parado. Fechar: corrida com `currentTime` imóvel e `paused=false` ≥ 2 s.
- `[UNKNOWN]` **O log é anterior ao mtime do shell** (23:11 vs fim 22:57). Fechar: `python _main/live-code-freshness-oracle.py --strict`; não corrido.
- `[UNKNOWN]` **A morte de `_yt_cdp_lines` é inferida**, não traçada; a única prova é `YOUTUBE_CAPTION=0` em 13 315 ticks. Fechar: traço com `SOTTO_YT_CPROFILE=1`.
- `[UNKNOWN]` **`parse_snapshot` com `paused` ausente vs `null`** só foi lido `[CODE] app/webview/youtube_cdp_source.py:814-816`. Fechar: fixture sem a chave, resultado impresso.
- `[UNKNOWN]` **Quantas abas existem quando a sonda abandona 6 de 6** não se sabe: `tabs=6` é o corte de `MAX_PROBE_TABS` `[CODE] app/webview/youtube_cdp_source.py:237,450-459`. Fechar: imprimir `len(tabs)` antes do corte.
