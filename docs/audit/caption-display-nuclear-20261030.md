# A legenda do audio anterior no audio novo — mapa nuclear do audio ao ecra (2026-10-30)

Leitura estatica de `H:/sotto` (nenhuma app lancada, nenhum ficheiro de produto tocado).
Cada afirmacao numerica tem comando em §8; o que nao foi medido leva `[INFERENCE]`.
`ficheiro:linha` sem directoria = o ficheiro canonico em `app/` ou `worker/`; as copias
em `_main/_gaps-g1-after-*` sao instantaneos antigos e nao sao a fonte.

## 0. Veredicto em uma linha

O texto nao "volta" por um unico bug: o `LineFormer` (worker) publica parciais sem
IDENTIDADE de stream, a `audio_q` nunca e' esvaziada quando a escada roda o endpoint
(`worker/sotto_worker.py:5737,6196,6596`), e o shell estampa o epoch no momento de
ENFILEIRAR (`sotto_webview.py:9802`), nao no momento de PINTAR — logo protege o texto
que ja estava no slot e deixa passar o texto velho que ainda vai chegar; no fim, o
overlayer nativo repinta o ultimo `text` que guarda quando alguem lhe diz `show(True)`
(`caption_overlay.py:1159-1161`).

## 1. INGEST -> TEXTO

| salto | ficheiro:linha | comportamento | edge case | VERDE/RED/POR-MEDIR |
|---|---|---|---|---|
| tap WASAPI abre no MIX rate | `worker/wasapi_loopback.py:693` (`block_ms=100`), `:720` (`self.rate = self.ep.rate`) | blocos float32 mono ao rate do endpoint (48 kHz tipico) | endpoint recusa 16 kHz: `Initialize` falha e a escada desce de rung | VERDE |
| fila de audio vivo | `worker/sotto_worker.py:5737` (`queue.Queue(maxsize=256)`) | produtor `on_block` -> consumidor `asr_thread` | `maxsize` em BLOCOS, nao em segundos: 256 x 100 ms = 25,6 s de atraso potencial | RED |
| tecto em SEGUNDOS | `worker/live_queue.py:29` (`LIVE_QUEUE_MAX_S = 2.0`), `:41` (`enqueue_live`) | passa do tecto -> sai o bloco MAIS ANTIGO, entra o novo | 20 blocos a 100 ms; o audio de ha 2 s e' deitado fora | VERDE |
| produtor conta a remocao | `worker/sotto_worker.py:5917-5923` | `evicted`/`dropped` contados em `counters["queue_evicted"]` | a chave e' criada com `.get(...,0)` no ramo, nao em `counters` (`:5753-5775`) | POR-MEDIR |
| consumidor | `worker/sotto_worker.py:6196` (`audio_q.get(timeout=0.25)`) | unico caminho que TIRA da fila | e' tambem o unico: nao existe `audio_q.clear` em ficheiro nenhum (§8/B) | RED |
| chunk 560 ms | `worker/sotto_worker.py:913-914` (docstring "8960-sample (560 ms)"), `:6360-6364` (`while len(buf) >= asr.chunk`) | a palavra so nasce numa fronteira de chunk | fala curta no fim do stream fica em `buf` ate ao `flush()` (`:6410`) | VERDE |
| decisao de fala ANTES do ganho | `worker/sotto_worker.py:6359` | `gate.is_speech(seg)` corre no sinal PRE-gain e o veredicto e' passado a `run_chunk` | com gate desligado e' sempre `True` | VERDE |
| gate dentro do chunk | `worker/sotto_worker.py:967-1009` | chunk de musica/silencio nao chega ao encoder; o relogio avanca | parcial ja emitido nao e' retirado quando o chunk seguinte e' gated | POR-MEDIR |
| `stream_epoch` do diarizador | `worker/sotto_worker.py:3418`, `:5974` | zero do wall clock para atribuir fala a falante | so com `--speakers`; nao viaja para o shell | VERDE |
| provacao da palavra | `worker/stable_words.py:111` (`proven_text`), `:147` (`close_parts`) | a cauda aberta nao vai para o ecra ate o tokenizer provar | ultima palavra de um parcial espera o TOKEN seguinte (ate um chunk) | VERDE |
| linha fecha por silencio de AUDIO | `worker/sotto_worker.py:3265` (`SENTENCE_GAP_S = 8.0`), `:3744-3751` | `start - _end >= 8 s` fecha ANTES do chunk novo | 8 s sem fala = 8 s de legenda congelada no ecra | VERDE |
| linha fecha por tecto | `worker/sotto_worker.py:3269` (`SENTENCE_MAX_CHARS = 90`), `:3757-3763` | lookahead: o fragmento que estouraria abre a linha seguinte | `carry=True` transporta a cauda nao provada (`_close`, `:3684`) | VERDE |
| evento para o fio | `worker/sotto_worker.py:3500-3562` | `text/start/end/final/closed/stable/source` (+`chunk_start`/`chunks` quando ha source) | **nao ha chave de stream/tap/epoch**: dois taps diferentes produzem eventos indistinguiveis | RED |
| JSONL e flush | `worker/sotto_worker.py:536-539` | um objecto por linha, `flush()` imediato | stdout e' o unico contrato; uma linha perdida e' invisivel | VERDE |

## 2. TEXTO -> SHELL

| salto | ficheiro:linha | comportamento | edge case | VERDE/RED/POR-MEDIR |
|---|---|---|---|---|
| bridge construida | `app/webview/sotto_webview.py:9490` (`WorkerBridge(...)`) | `on_caption=self.on_worker_caption` | o objecto bridge e' a unica identidade de fonte que o shell tem | VERDE |
| epoch ao arrancar worker | `app/webview/sotto_webview.py:9519-9521` | worker novo -> `_source_epoch += 1`, slot limpo | cobre reinicio de PROCESSO, nao rotacao de endpoint | VERDE |
| epoch ao limpar pixels | `app/webview/sotto_webview.py:9730-9731` | `_blank_caption_window` incrementa e limpa o slot | e' a unica outra rotura do epoch (§8/C: 2 sitios) | VERDE |
| chegada de legenda | `app/webview/sotto_webview.py:9912` (`on_worker_caption`) | filtra fonte externa, emite para o painel e empurra para a janela | **nao recebe nem le epoch do evento** | RED |
| identidade de processo | `app/webview/sotto_webview.py:9915`, `:9933-9938` | compara `self.bridge` antes/depois; se mudou, descarta (`BRIDGE_CAPTION_DROP_SUPERSEDED`) | rotacao de endpoint dentro do MESMO worker nao muda o objecto | RED |
| painel externo suprime ASR | `app/webview/sotto_webview.py:9932-9936` | com `external_captions_active`, a linha ASR e' contada e descartada | nao limpa o slot nem o `text` ja pintado | RED |
| canal do painel | `app/webview/sotto_webview.py:9929` (`emit_async('caption', ...)`) | latch por `kind`: um payload pendente por canal | um `final:true` pode ser substituido pelo parcial seguinte antes da UI correr (`:10773-10779`) | RED |
| janela propria recebe o texto | `app/webview/sotto_webview.py:9935` | `push_caption_to_window(text)` sem `meta` | a janela nunca sabe se o evento era `final` nem de que tap veio | RED |
| travessia para o overlay | `app/webview/sotto_webview.py:9755` (`push_caption_to_window`) | um slot unico `_caption_pending`, nao uma fila | texto mais novo substitui o que ainda nao foi pintado (intencional) | VERDE |
| interruptor do dono | `app/webview/sotto_webview.py:9779-9780` | sem `_caption_wanted` nao se escreve na janela | serrilha antes do clique: nada e' pintado | VERDE |
| estampo do epoch no enfileirar | `app/webview/sotto_webview.py:9802-9803` | `(now, text, previous, _source_epoch)` | **estampa o epoch de AGORA**: texto velho que chega depois da troca nasce com epoch novo | RED |
| `_drain` recusa epoch gasto | `app/webview/sotto_webview.py:9811-9820` | `epoch != cur` -> `CAPTION_DROP_EPOCH`, nao pinta | so apanha o que ja estava enfileirado ANTES do incremento | VERDE |
| pinta | `app/webview/sotto_webview.py:9824-9825` | `set_text` + `show(True)` na thread de UI | `_post` fire-and-forget: ordem entre dois pushes nao e' garantida | VERDE |
| trava de `_post` em voo | `app/webview/sotto_webview.py:9857-9863` | um post em voo durante 2 s; os seguintes so substituem o slot | um post perdido custa ate 2 s sem pintar nada | POR-MEDIR |
| idle hide | `app/webview/sotto_webview.py:9669` (`CAPTION_IDLE_HIDE_S = 6.0`), `:9741-9748` | 6 s sem legenda -> pixels fora, interruptor do dono intacto | a proxima legenda reacende sem tocar em nada | VERDE |
| fonte externa entra | `app/webview/sotto_webview.py:9945` (`external_caption`), `:9994` (`_park_worker_for_external`) | para o worker e passa a pintar a linha do player | **nao incrementa `_source_epoch`**: o slot e o `text` do ASR sobrevivem a troca de fonte | RED |
| fonte externa sai | `app/webview/sotto_webview.py:2677` (`external_captions_active = False`) | devolve o microfone ao ASR | tambem sem epoch: a ultima linha do player fica no `text` do overlay | RED |

## 3. SHELL -> ECRA

| salto | ficheiro:linha | comportamento | edge case | VERDE/RED/POR-MEDIR |
|---|---|---|---|---|
| area de trabalho e tema | `app/webview/caption_overlay.py:924`, `:928` | posicao/escala e tokens do tema | sem tema, desenha o aspecto anterior | VERDE |
| `_update` compoe | `app/webview/caption_overlay.py:994-1005` | texto visivel -> layout -> bitmap -> `UpdateLayeredWindow` | sem texto E sem `previous` -> `hide()` | VERDE |
| texto vazio limpa | `app/webview/caption_overlay.py:1002-1004` | `if not text and not previous: self.hide()` | `hide()` (`:1172-1184`) limpa `text`/`previous` E esconde | VERDE |
| `_blank_caption_window` | `app/webview/sotto_webview.py:9733` | chama `ov.show(False)` | **`show(False)` so faz `ShowWindow(SW_HIDE)`; NAO limpa `self.text`** | RED |
| `show(True)` repinta | `app/webview/caption_overlay.py:1159-1162` | se ha `text` guardado: `_update()` + `SetWindowPos` + `ShowWindow` | reacender a janela depois de um blank repinta a ULTIMA legenda antiga | RED |
| fade da linha nova | `app/webview/caption_overlay.py:1099`, `app/webview/word_fade.py:31` (`DURATION_S = 0.12`) | `_fade_t0` arma a rampa ease-out de 120 ms | `alpha_at(0) == 0` (`word_fade.py:55-56`): o primeiro frame e' invisivel | VERDE |
| sprout palavra a palavra | `app/webview/caption_overlay.py:800` (`WORD_STEP_S = 0.045`), `:1108-1136` | desenha as primeiras `_shown` palavras | linha NOVA nasce com `_shown = 1` (`:1092`) | VERDE |
| `_same_line` so olha a 1a palavra | `app/webview/caption_overlay.py:803`, `:1089-1096` | mesma 1a palavra -> nao reinicia sprout nem fade | frase nova com a mesma palavra inicial herda o estado da anterior | POR-MEDIR |
| quebra em 2 linhas | `app/webview/caption_overlay.py:604` (`_layout`), `:650` (`_cw.wrap_tail`), `app/webview/caption_wrap.py:55` (`MAX_LINES = 2`), `:357` | janela rola: ficam as DUAS ULTIMAS linhas | `_layout` devolve `scrolled` e `_update` NAO o usa: o inicio sai sem aviso | RED |
| fonte do YouTube: duas linhas | `app/webview/youtube_window.py:42` (`CAPACITY = 2`), `:49` (`live_lines`), `:140` (`revealed_lines`) | vive(t) = cues com `start <= t < end`; desenho = as 2 ultimas | buraco entre cues devolve `[]` (o player tambem nao desenha) | VERDE |
| colapso de crescimento | `app/webview/youtube_window.py:150` (`collapse_growth`), `:183` (`window_key`) | a mesma janela nao e' re-emitida | chave com separador `\x1f` (`:46`) para `["a","b"]` != `["a\x1fb"]` | VERDE |
| relogio por palavra pintada | `app/webview/youtube_reveal.py:193` (`word_clock_count`), `:231` (`window_by_paint`) | o prefixo revelado segue as palavras que o PLAYER pintou | sem relogio, cresce na ordem do cue (nao no instante do video) | VERDE |
| rows -> texto com `\n` | `app/webview/youtube_reveal.py:326` (`rows_text`), `sotto_webview.py:9769-9775` | `_layout` desenha as linhas como o player as quebrou | `instant=True` forcado: nunca re-quebra uma rows window | VERDE |
| titulo "carregando modelo…" | `app/webview/sotto_webview.py:13567` | empurra texto fixo para a janela | sem epoch: entra como se fosse legenda e ocupa o slot | POR-MEDIR |

## 4. HISTORICO + PAINEL + HOTKEY

| salto | ficheiro:linha | comportamento | edge case | VERDE/RED/POR-MEDIR |
|---|---|---|---|---|
| painel recebe parcial | `app/panel/panel.js:1286-1294` | `armHoldTimer()` + `engineFor(source).ingest(text, meta)` | engine por `source` (`meta.source`), `null` sem source | VERDE |
| painel recebe player | `app/panel/panel.js:1309-1321` | canal `external-caption`: `engine.reset()` e `ingest` de UMA linha | reset por linha e' o que evita "previous. previous. current." | VERDE |
| motor: silencio de audio | `app/panel/caption-formulation.js:81` (`SENTENCE_GAP_S = 8`), `:773-775` | `start - lastAudioEnd >= 8` -> `commit('audio-gap …')` | mesmo limiar do worker: as duas camadas fecham juntas | VERDE |
| motor: re-leitura | `app/panel/caption-formulation.js:783-793` | `start < lastAudioEnd` -> filtra o que ja estava no ecra | filtra `committed` E `provisional` | VERDE |
| motor: tecto de caracteres | `app/panel/caption-formulation.js:84` (`90`), `:800-810` | lookahead; o fragmento que estoura abre linha nova | guarda `reentered` para um fragmento maior que o tecto | VERDE |
| motor: continuacao ja escrita | `app/panel/caption-formulation.js:894-903` | `start === emittedStart` -> so entra o prefixo que cresceu | `===` de proposito: reinicio de worker faz o `start` CAIR | VERDE |
| commit e rota | `app/panel/caption-formulation.js:706`, `:150` (`COMMIT_MAX_HOLD_MS = 1500`) | linha fecha por regra ou por deadline de 1500 ms | o deadline escreve `hold-timeout`, nao um `final` do worker | VERDE |
| hold-back da ultima palavra | `app/panel/panel.js:1101-1146` | segura a ultima palavra ate `tailClosed`/`stable`/externo | com `stable:true` do worker nao segura segunda vez | VERDE |
| `stable` no fio | `app/panel/stable-words.js:26-30`, `:54-61` | `wordsAreWhole(tailClosed, key)` | evento sem a chave -> `false` (leitura segura) | VERDE |
| historico: so `final` | `app/panel/panel.js:1841`, `sotto_webview.py:8266-8273` | painel grava so `route=final`; o store RECUSA `provisional-draft` | invariante repetido nos dois sitios | VERDE |
| historico: anti-duplicado | `app/webview/sotto_webview.py:8287-8290` | compara so com a ULTIMA linha do ficheiro | frase repetida uma hora depois entra (de proposito) | VERDE |
| hotkey: 1 toque / 2 toques | `app/webview/hotkey_gesture.py:71` (`resolve_taps`), `:97` (`CYCLE`), `:100` (`next_surface`) | o codigo de hoje CICLA `nada -> baixo -> direita` a cada pressao | `resolve_taps` ja nao decide o ciclo: e' `next_surface` que le a janela | POR-MEDIR |
| hotkey: HOLD | `app/webview/hotkey_gesture.py:47` (`HOTKEY_HOLD_MS = 200.0`), `:57` (`is_hold`) | >= 200 ms em baixo = legenda ao vivo on/off | 204/438/468 ms da tabela do dono caem em HOLD (risco escrito no ficheiro) | VERDE |
| hotkey: entrega ao cruzar o limiar | `app/webview/sotto_webview.py:3862-3890` (`_tick`), `:3805` (`_deliver_hold`) | HOLD dispara sem esperar o release | release perdido NUNCA entrega HOLD (`:3846-3850`) | VERDE |
| hotkey: o que o HOLD faz | `app/webview/sotto_webview.py:8851-8858` -> `:11436` (`show_caption_window(on)`) | so muda o display; nao toca no worker nem no historico | **reacende a janela com o `text` antigo ainda dentro** (ver §3) | RED |

## 5. Os buracos que permitem a legenda velha (por gravidade, ficheiro:linha)

1. **(b) A fila de audio antiga nao e' esvaziada quando o endpoint roda.**
   `audio_q` e' criada em `worker/sotto_worker.py:5737` e o UNICO consumidor e'
   `:6196`; nao existe `audio_q.clear` (nem `get_nowait` sobre ela) em ficheiro nenhum
   (§8/B). `close_tap` (`:6596-6615`) para o stream e diz na docstring que isso impede o
   tap abandonado de continuar a alimentar a fila — mas nao tira o que JA LA ESTA.
   `LIVE_QUEUE_MAX_S = 2.0` (`worker/live_queue.py:29`) garante que esses blocos sao
   audio do endpoint ABANDONADO, e o ramo de gen (`:6199-6244`) so corre quando o
   primeiro bloco novo chega: o buffer velho e' consumido e decodificado primeiro.
   Agravante de proveniencia: `former.set_source(...)` (`:6206`) corre ANTES de
   `former.flush()` (`:6237`), logo o fecho da linha do tap ANTIGO e' publicado com o
   `source` do tap NOVO.
2. **(a) O overlayer guarda e repinta o ultimo texto.**
   `_update` limpa quando nao ha texto (`app/webview/caption_overlay.py:1002-1004`), e
   `hide()` limpa de facto (`:1172-1184`, `self.text = ""` em `:1178`). Mas
   `_blank_caption_window` usa `ov.show(False)` (`app/webview/sotto_webview.py:9733`),
   que so faz `ShowWindow(SW_HIDE)` (`caption_overlay.py:1172-1175`): o `text` fica
   dentro do objecto. Qualquer `show(True)` posterior — `:1159-1162` — repinta-o sem
   esperar legenda nova. Quem chama `show(True)`: o push normal (`sotto_webview.py:9825`),
   mas tambem `show_caption_window(on)` (`:9874-9891`) a partir do HOLD
   (`:8851` -> `:11436`). Ou seja: VIDEO NOVO -> blank -> HOLD -> a legenda do video
   anterior volta ao ecra.
3. **(d) O que o shell faz a um parcial de fonte anterior: nada.**
   `push_caption_to_window` estampa o epoch no instante em que ENFILEIRA
   (`:9802-9803`) e `_drain` recusa epochs gastos (`:9811-9820`) — isso protege o texto
   que ja estava no slot quando houve incremento. Mas (i) o evento do worker nao traz
   identidade de stream (`worker/sotto_worker.py:3500-3562`), (ii) o unico teste de
   processo que o shell faz e' a identidade do objecto bridge (`:9915`, `:9937-9941`),
   e (iii) uma rotacao de endpoint nao recria a bridge. Resultado: o parcial que o tap
   abandonado produz chega DEPOIS da rotacao, e' estampado com o epoch NOVO e passa
   pelo filtro — pintado como se fosse audio do endpoint novo.
4. **(c) YouTube ao trocar de video: o estado do video muda, o da fonte nao.**
   O ramo `vid != self.yt_video_id` (`app/webview/sotto_webview.py:2293-2314`) limpa
   `yt_hit`, `yt_serve_floor`, `yt_foreign_t/key`, `_yt_anchor`, `_yt_track`,
   `last_line`, `last_rows`, `finalized`, `_caption_pending` e chama
   `_blank_caption_window('video-changed')` — que INCREMENTA o epoch (`:9730`). Esse
   caminho esta' tapado. O que NAO e' limpo: `_external_last_text` em
   `external_caption` (`:9981-9984`), usado por `extends_previous` (`:3285`) — a primeira cue do
   video novo e' comparada com a ultima do video ANTERIOR. E a troca de CLASSE de fonte
   (ASR <-> player) nunca incrementa o epoch: `_park_worker_for_external`
   (`:10017-10032`) e `_release` (`:2668-2682`) nao tocam em `_source_epoch` (§8/C).
5. **O latch de `emit_async` pode comer um `final`.**
   `app/webview/sotto_webview.py:10773-10779`: `pending[kind] = payload` por `kind`.
   Um `final:true` seguido do parcial do chunk seguinte, antes de a UI correr, deixa
   so o parcial. O `final` e' a UNICA rota para o historico
   (`app/panel/panel.js:1841`, `sotto_webview.py:8266`): a linha desaparece do
   transcrito sem erro nenhum. `emit_async` existe para o canal de stats
   (`:10742-10767`); o canal `caption` herdou-o em `:9929`.
6. **`_same_line` compara so a primeira palavra** (`caption_overlay.py:803`):
   uma frase nova que comece pela mesma palavra nao reinicia o sprout nem arma o fade
   (`:1089-1096`). Nao e' texto velho, mas e' estado velho a atravessar a fronteira.
7. **`_layout` calcula `scrolled` e `_update` ignora-o** (`caption_overlay.py:650`,
   `:1007`): com mais de 2 linhas o inicio sai do ecra sem marcador — o dono ve
   "faltar palavras", que e' o sintoma irmao do jumpscare.
8. **`queue_evicted` nunca e' impresso.** Contado em `worker/sotto_worker.py:5917-5923`,
   ausente de `stats_line` (`:5865-5895`): a prova de que a cura da fila esta' a
   trabalhar (ou a ser insuficiente) nao sai em nenhum `WORKER_STATS`.

## 6. Os buracos que custam latencia (idem)

1. **Quantizacao de 560 ms.** `worker/sotto_worker.py:913-914`, `:6360-6364`: a
   primeira palavra de uma fala so pode aparecer depois de um chunk INTEIRO. Piso
   estrutural de 0,56 s entre fala e primeiro token, antes de qualquer inferencia.
   `[INFERENCE]`: o valor real por cima disto nao foi medido (§7).
2. **Profundidade da fila.** `LIVE_QUEUE_MAX_S = 2.0` (`live_queue.py:29`): o display
   atrasa o que estiver na fila, e a fila guarda o MAIS NOVO — logo o atraso maximo e'
   2 s de audio, nao 25,6 s (`:5737`). Se o decoder fica abaixo de tempo real, o tecto
   e' atingido em permanencia e cada bloco antigo e' deitado fora; sem
   `queue_evicted` em `stats_line` (§5.8) isso e' invisivel.
3. **Palavra provada so no token seguinte.** `worker/stable_words.py:111-146` +
   `worker/sotto_worker.py:3782`: a cauda aberta espera o proximo token. O piso e'
   um token, o tecto pratico e' um chunk (0,56 s) quando a palavra cai na fronteira.
4. **Slot unico + trava de 2 s.** `sotto_webview.py:9857-9863`: enquanto ha um `_post`
   em voo, os pushes so substituem o slot. Se esse post se perder, a janela nao pinta
   nada durante 2 s (o comentario em `:9799-9803` admite a troca "atraso por silencio").
5. **Primeiro frame invisivel.** `word_fade.py:55-56` devolve 0 para `t <= 0`, e
   `set_text` chama `_update()` no mesmo instante em que arma o fade
   (`caption_overlay.py:1099-1105`): o frame inicial e' desenhado com
   `SourceConstantAlpha = 0`; o seguinte so chega a 1/60 s (`word_fade.py:32`), e a
   rampa completa leva 120 ms.
6. **Sprout de 45 ms por palavra.** `caption_overlay.py:800`, `:1108-1136`: uma linha
   nova nasce com UMA palavra e ganha uma a cada 45 ms. Um parcial de 8 palavras leva
   ~315 ms a ficar inteiro no ecra — por cima do fade e da latencia de texto.
7. **1500 ms de espera para o historico.** `caption-formulation.js:150`
   (`COMMIT_MAX_HOLD_MS`): nao atrasa a caixa ao vivo, atrasa o transcrito; um
   `hold-timeout` escreve uma linha que o worker nunca fechou.
8. **YouTube: 300 ms de leitura + 60 ms de recomposicao.**
   `sotto_webview.py:1941` (`INTERVAL_S = 0.30`), `:1946` (`RENDER_S = 0.06`): o UIA
   nao e' lido mais depressa, o desenho e' recompsoto a 60 ms entre leituras.
9. **Rotacao de endpoint paga o proprio atraso.** `worker/sotto_worker.py:302`
   (`TAP_WINDOW_S = 6.0`), `:366` (`TAP_REOPEN_MIN_S = 5.0`), `:337`
   (`MAX_ROTATIONS_WITHOUT_SIGNAL = 8`): enquanto a escada procura um endpoint com
   sinal, o shell nao recebe legenda nenhuma. `[INFERENCE]`: quanto disto caiu na
   sessao do dono nao foi contado (§7).

## 7. O que ficou POR MEDIR

1. **Latencia fala -> pixel, por salto.** Nao existe instrumento que carimbe o instante
   da FALA. O unico relogio que chega ao log e' `CAPTION_OVERLAY_LAG age_ms=`
   (`sotto_webview.py:9845`), que mede enfileirar -> pintar, nao falar -> pintar.
   Os 560 ms de chunk, a fila, o fade e o sprout foram lidos no codigo, nao medidos
   juntos.
2. **Profundidade da `audio_q` durante o relato do dono.** Precisava de
   `queue_evicted` e `queue_drops` impressos (`worker/sotto_worker.py:5865-5895`) e de
   uma amostra por segundo; hoje so o stderr diz `audio queue over ...` nas 3 primeiras
   ocorrencias (`:5917-5923`).
3. **Quantas vezes `CAPTION_DROP_EPOCH` dispara** e com que `enq`/`cur`
   (`sotto_webview.py:9817-9819`). Sem essa contagem, "o epoch tapa o jumpscare" e' uma
   afirmacao sobre o mecanismo, nao sobre o comportamento observado.
4. **Quantos `final` o latch de `emit_async` comeu.** Comparar
   `BRIDGE_CAPTION_SENT` (`:9930`) com as linhas escritas por `HISTORY_APPEND`
   (`:8305`) na mesma sessao fecharia isto; nao foi feito.
5. **Se a rotacao de endpoint alguma vez e' a causa do text antigo** na sessao do dono:
   exige cruzar `device-rotated` (`:7046-7053`) com a primeira linha publicada depois,
   e o worker nao carimba o tap no evento (§1, ultima linha).
6. **Ar quente**: nenhuma medição de tempo de inferencia por chunk nesta leitura;
   `asr.wall`/`infer_wall_s` existem no `stats_line` mas nao foram lidos de um run.
7. **O limite de 200 ms do HOLD** (`hotkey_gesture.py:47`) foi ESCOLHIDO pelo dono, nao
   re-medido — o proprio ficheiro o diz (`:36-39`). Os 204/438/468 ms da tabela dele
   caem hoje em HOLD e isso nao foi observado.

## 8. PROVENIENCIA (comando exacto + resultado por contagem)

Todos os comandos correram em `H:/sotto`, leitura apenas (`grep`/`sed`), sem lancar a app.

| # | comando | resultado |
|---|---|---|
| A | `grep -n "audio_q" worker/sotto_worker.py \| wc -l` | `7` — 5737 (criacao), 5918 (put via `enqueue_live`), 6196 (get), 4 comentarios |
| B | `grep -c "audio_q.clear\|audio_q.queue.clear" worker/sotto_worker.py` | `0` — nao existe esvaziamento da fila em sitio nenhum |
| B2 | `grep -n "get_nowait" worker/sotto_worker.py` | `1` hit, `:4658`, e e' sobre `self._captions` (fila do batch), NAO sobre `audio_q` |
| C | `grep -c "_source_epoch = int(getattr(self, '_source_epoch', 0)) + 1" app/webview/sotto_webview.py` | `2` — `:9519` (worker arrancou) e `:9730` (`_blank_caption_window`); nenhum em `external_caption`/`_park_worker_for_external`/`_release` |
| D | `sed -n '5865,5895p' worker/sotto_worker.py \| grep -c queue_evicted` | `0` — o contador da cura da fila nao sai no `WORKER_STATS` |
| E | `grep -n "maxsize=256" worker/sotto_worker.py` | `1` — `:5737`, 256 blocos x 100 ms = 25,6 s de tecto nominal |
| F | `grep -n "def stats_line" worker/sotto_worker.py` | `:5865` |
| G | `grep -c '"stable"' worker/sotto_worker.py` | `1` — `:3555` (`_event`); e' a chave que `stable-words.js` le |
| H | `sed -n '9912,9944p' app/webview/sotto_webview.py \| grep -n bridge` | `4` hits — a unica identidade de fonte testada e' o objecto bridge (`:9915`, `:9937`) |
| I | `grep -c "self.push_caption_to_window(" app/webview/sotto_webview.py` | `3` — `:9935` (ASR, sem `meta`), `:10012` (player), `:13567` (texto fixo) |
| J | `grep -n "former.set_source\|former.flush()" worker/sotto_worker.py` | `former.set_source` em `:6206` e o `for event in line_events(former.flush()):` do ramo de gen em `:6237`: `set_source` corre ANTES do `flush` |
| K | `sed -n '6180,6450p' worker/sotto_worker.py \| grep -c "emit(model=asr.name, \*\*event)"` | `6` sitios de publicacao no braco vivo |
| L | `grep -c "LineFormer(" worker/sotto_worker.py` | `3` — `:4752` (selftest), `:5967` (vivo), `:6070` (segunda passagem) |
| M | `grep -n "def _update\|def set_text\|def show\|def hide" app/webview/caption_overlay.py` | `:994`, `:1069`, `:1154`, `:1172` |
| N | `grep -n "if not text and not previous" app/webview/caption_overlay.py` | `:1002` — o unico caminho que limpa o texto pintado |
| O | `grep -n "self._post(lambda: ov.show(False))" app/webview/sotto_webview.py` | `:9733` e `:9891` — os dois blanks usam `show(False)`, que nao limpa `text` |
| P | `grep -n "def armHoldTimer\|function renderProvisional\|function recordHistory" app/panel/panel.js` | `:1014`, `:1101`, `:1841` |
| Q | `grep -n "COMMIT_MAX_HOLD_MS = \|const SENTENCE_GAP_S\|const SENTENCE_MAX_CHARS" app/panel/caption-formulation.js` | `:150` (1500 ms), `:81` (8 s), `:84` (90) |
| R | `grep -n "WORD_STEP_S = \|DURATION_S = \|FRAME_S = " app/webview/caption_overlay.py app/webview/word_fade.py` | `caption_overlay.py:800` (0.045), `word_fade.py:31` (0.12), `word_fade.py:32` (1/60) |
| S | `grep -n "HOTKEY_HOLD_MS = \|CYCLE = \|def next_surface" app/webview/hotkey_gesture.py` | `:47` (200.0), `:97`, `:100` |
| T | `grep -n "RENDER_S = \|INTERVAL_S = \|STABLE_FINAL_S = \|RELEASE_S = \|YT_RELEASE_S = " app/webview/sotto_webview.py` | `:1946` (0.06), `:1941` (0.30), `:1949` (1.6), `:1952` (1.8), `:1960` (30.0) |
| U | `wc -l` nos ficheiros do caminho | `worker/sotto_worker.py` 7457, `worker/wasapi_loopback.py` 1162, `worker/stable_words.py` 162, `worker/live_queue.py` 64, `app/webview/sotto_webview.py` 15219, `caption_overlay.py` 1218, `caption_wrap.py` 417, `youtube_reveal.py` 350, `youtube_window.py` 240, `hotkey_gesture.py` 112, `app/panel/panel.js` 3935, `caption-formulation.js` 1070, `stable-words.js` 77 |
| V | `grep -c "^| " docs/audit/caption-display-nuclear-20261030.md` menos cabecalhos | linhas de tabela em §1-§4: **14 + 17 + 14 + 15 = 60**; veredictos nelas: **VERDE 39, RED 15, POR-MEDIR 6** |
| W | `git status --short docs/audit/` | antes da escrita: vazio. Depois: `?? docs/audit/caption-display-nuclear-20261030.md` — unico ficheiro novo em `docs/audit`. Repo inteiro: 608 unstaged e 184 untracked, contra 608/183 na primeira leitura desta sessao (o +1 e' este documento) |
