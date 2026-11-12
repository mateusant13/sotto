# 05 — O CAMINHO AO VIVO: de um bloco de áudio a uma palavra pintada

Este ficheiro segue **um** bloco de áudio desde o corte no worker até ao pixel que o dono lê, e nomeia cada
porta que o pode calar. Descreve o código em `HEAD`: onde comentário e código discordam, manda o código.

**Aviso de frescura (2026-11-11 23:28).** O processo que escreveu `_main/webview-run.log` NÃO é o
código do disco:

```
$ python _main/live-code-freshness-oracle.py --strict
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  processo: sha256=1D027EB01669   <- GRAVADO no arranque
  disco   : sha256=E3270577EB2F files=110
  MUDOU DEPOIS DO ARRANQUE: sotto_webview.py
rc=3
```

`[MEASURED]` esse comando, essa saída, 2026-11-11: os números do log provam que uma etiqueta já correu
num processo real, não que o `HEAD` produza a mesma distribuição. `[INFERENCE]` qualquer frequência
lida do ficheiro descreve uma shell anterior à última edição de `sotto_webview.py`.

## 1. O bloco: 8 960 amostras, 560 ms

O worker fixa a taxa em 16 000 Hz (`[CODE] worker/engine_switch.py:37`, importada por
`worker/sotto_worker.py:147`) e o tamanho do bloco vem do modelo, não de uma constante do código:
`"chunk_samples": 8960` (`[CODE] worker/models/nemotron-3.5-asr-ptbr-onnx-int4/genai_config.json:16`),
lido em `self.chunk = cfg["chunk_samples"]` (`[CODE] worker/sotto_worker.py:1571`). `[MEASURED] python -c
"print(8960/16000)"` → `0.56`, 2026-11-11: o bloco são **560 ms** de áudio.

O laço ao vivo concatena cada bloco do tap e corta um chunk de cada vez
(`[CODE] worker/sotto_worker.py:8033-8036`: `np.concatenate([buf, block])`, depois `seg = buf[:
asr.chunk]`). O carimbo de chegada é tirado **antes** do decode (`[CODE] worker/sotto_worker.py:8047`,
`_wall_tap = time.time()`), e os segundos de áudio da linha saem do índice do chunk, não do relógio:

| campo | valor | evidência |
|---|---|---|
| `start` do chunk | `round((idx - 1) * asr.chunk / TARGET_SR, 2)` | `[CODE] worker/sotto_worker.py:8069` |
| `end` do chunk | `round(idx * asr.chunk / TARGET_SR, 2)` | `[CODE] worker/sotto_worker.py:8070` |

O bloco também é oferecido ao motor de lote quando `fuse_history` está ligado
(`[CODE] worker/sotto_worker.py:8027`, `switch.add_live_audio(block)`), e a chamada só acumula: não
acorda motor nenhum (`[CODE] worker/engine_switch.py:1224-1253`).

## 2. A linha: parcial, fecho e o JSONL

`LineFormer.push` recebe o texto do chunk e devolve 0–2 eventos (`[CODE] worker/sotto_worker.py:5609`);
um fragmento vazio não publica nada (`[CODE] worker/sotto_worker.py:5621-5622`). Uma pausa de áudio
**fecha a linha antes** do chunk novo quando `start - self._end >= self.gap_s`
(`[CODE] worker/sotto_worker.py:5642-5649`), com `gap_s = SENTENCE_GAP_S = 8.0`
(`[CODE] worker/sotto_worker.py:4851`). O tecto é `SENTENCE_MAX_CHARS = 90`
(`[CODE] worker/sotto_worker.py:4857`), aplicado como **lookahead** para o fragmento que estouraria abrir
a linha seguinte (`[CODE] worker/sotto_worker.py:5653-5657`); pontuação terminal fecha depois do chunk
(`[CODE] worker/sotto_worker.py:5692-5693`).

### 2.1 Parcial: a última palavra por provar não vai ao ecrã

O parcial não publica `self.line()` cru: publica `proven_text(...)` sobre os fragmentos
(`[CODE] worker/sotto_worker.py:5688`), que devolve o prefixo provado e a cauda aberta
(`[CODE] worker/stable_words.py:111`). A prova é a marca `▁` do tokenizer, lida em `open_word_start`
(`[CODE] worker/stable_words.py:60`): o que fica à esquerda do último início de palavra está provado. O
evento leva `stable=True` (`[CODE] worker/sotto_worker.py:5702`) e só é reenviado quando o texto muda
(`[CODE] worker/sotto_worker.py:5698-5702`). Uma pausa no áudio publica a cauda inteira sem fechar a
linha: `publish_on_silence` (`[CODE] worker/sotto_worker.py:5716`) chama `worker/silence_tail.py` e emite
`stable=True` (`[CODE] worker/sotto_worker.py:5731`), invocado pelo laço ao vivo quando o chunk
descodificou vazio (`[CODE] worker/sotto_worker.py:8097-8101`).

### 2.2 Fecho: fora de banda, uma vez

`_close` constrói o evento de fecho e guarda-o em `self._closed` com `final=True, closed=True,
stable=True` (`[CODE] worker/sotto_worker.py:5589`); a linha parcial equivalente só sai se nunca tinha
sido mostrada (`[CODE] worker/sotto_worker.py:5590-5595`). O fecho viaja **fora de banda**, por
`take_closed()` (`[CODE] worker/sotto_worker.py:5603`), e o laço drena-o em `drain()`
(`[CODE] worker/sotto_worker.py:7793`). O texto vem da segunda passagem quando ela está ligada, e da
linha ao vivo quando não está (`[CODE] worker/sotto_worker.py:7776-7791`); a segunda passagem está
**desligada por omissão**, armada só por `SOTTO_SECOND_PASS=1` (`[CODE] worker/sotto_worker.py:7642-7650`).
`[INFERENCE]` com o interruptor em OFF o `final` é a mesma linha que o parcial já mostrou.

`line_events` é o único sítio que remove a marca interna `closed` e normaliza `final`
(`[CODE] worker/sotto_worker.py:5738-5759`). O evento que sai tem esta forma fixa:

| campo | significado | evidência |
|---|---|---|
| `type` / `text` | `"caption"` e o texto do evento | `[CODE] worker/sotto_worker.py:5355-5356` |
| `start` | início da **linha**, não do chunk mais recente | `[CODE] worker/sotto_worker.py:5363` |
| `end` | fim do chunk mais recente | `[CODE] worker/sotto_worker.py:5364` |
| `chunk_start` / `chunks` | relógio do chunk e lista `[start, end, texto]`, só com `source` | `[CODE] worker/sotto_worker.py:5377-5381` |
| `final` | a linha foi FECHADA pelo worker | `[CODE] worker/sotto_worker.py:5389` |
| `stable` | as palavras deste evento já estão provadas | `[CODE] worker/sotto_worker.py:5408` |
| `tap_ms` | `int(round(self._wall * 1000.0))`, só com relógio de captura | `[CODE] worker/sotto_worker.py:5418` |
| `source` | dispositivo/processo do tap, só quando existe | `[CODE] worker/sotto_worker.py:5425` |

`[CODE]` o evento do caminho ao vivo **não** carrega `route`: quem o acrescenta é o motor de lote
(`route="redux-batch"`, `[CODE] worker/engine_policy.py:382`) e o overlay Redux (`route="redux-live"`,
`[CODE] worker/redux_live.py:1535`). O par `final`/`provisional-draft` é vocabulário de ADMISSÃO,
derivado na shell/painel a partir de `final` (ver §8), não um campo do ASR ao vivo.

`emit` escreve um objecto JSON por linha e faz `flush` (`[CODE] worker/sotto_worker.py:1001-1035`). Se o
pai fechar o cano, escreve `EMIT_PIPE_DEAD` no stderr e sai **0**
(`[CODE] worker/sotto_worker.py:1029-1035`): um cano morto é "o meu leitor foi-se", não um crash. O `-u`
do `Popen` impede o pipe de bufferizar 8 KB e prender uma legenda
(`[CODE] app/webview/sotto_webview.py:23461-23472`).

## 3. A porta da rota: `live_route.admit`

Todo o caption do worker passa por um único sítio antes de ser escrito: `emit` chama
`payload = live_route.admit(payload, log=route_log)` quando `type == "caption"`
(`[CODE] worker/sotto_worker.py:1017-1025`). O `admit` nunca levanta e nunca perde a linha: qualquer
excepção devolve o payload intacto (`[CODE] worker/live_route.py:322-323`).

Os números que decidem: `LIVE_MAX_AGE_S = 2.5` (`[CODE] worker/live_route.py:67`) e `CLOCK_JITTER_MS =
250.0` (`worker/live_route.py:74`). A decisão está em `live_route_verdict`
(`[CODE] worker/live_route.py:220-253`), que devolve `{'paint', 'reason', 'age_s', 'producer'}`.
`caption_producer` (`[CODE] worker/live_route.py:133-151`) classifica por rota e, na falta dela, pela
origem: `route=redux-batch` **ou** `producer=redux` → `"redux"`; tudo o resto → `"live"` — nunca `unknown`.

`caption_age_s` devolve a idade honesta, por esta ordem: `tap_ms` contra `now`
(`[CODE] worker/live_route.py:187-189`), `audio_age_s` carimbado por quem tem o relógio do áudio
(`[CODE] worker/live_route.py:191-192`), `end` contra `clock_s` (`[CODE] worker/live_route.py:194-195`);
sem nenhum, `None` (`[CODE] worker/live_route.py:197`). `[CODE]` um carimbo no FUTURO além de
`CLOCK_JITTER_MS` também devolve `None` (`worker/live_route.py:214-215`), porque `max(0.0, negativo)`
transformava "não consigo medir" em "fresco".

A decisão é pura e a **ordem das portas no código** é esta (`[CODE] worker/live_route.py:237-253`):

| ordem | condição | resultado | razão no log |
|---|---|---|---|
| 1 | `producer == "redux"` | não pinta | `batch-route` |
| 2 | `route_owner == "player"` | não pinta | `player-owns-route` |
| 3 | a linha inteira é ruído (`m`/`hm`/`mhm`) | não pinta | `noise` |
| 4 | idade `None` | **pinta** e conta o buraco | `unknown-age` |
| 5 | idade `<= 2.5 s` | pinta | `fresh` |
| 6 | idade `> 2.5 s` | não pinta | `stale` |

Uma recusa marca o payload: `history_only=True` e `route_refused=<razão>`
(`[CODE] worker/live_route.py:304-305`). Uma admissão carimba `age_s` quando conhecido
(`[CODE] worker/live_route.py:285-286`). `LIVE_ROUTE_REFUSED` sai **uma vez por episódio**
`(razão, produtor)` e o episódio fecha quando uma linha do mesmo produtor volta a pintar
(`[CODE] worker/live_route.py:297-302, 308-320`). `[INFERENCE]` um vídeo de duas horas com o player a
fornecer legendas produz uma linha de log, não milhares.

`[MEASURED] grep -c LIVE_ROUTE_REFUSED _main/webview-run.log` → `24` (2026-11-11): a porta já correu
numa instância real, o que prova que a etiqueta existe no processo vivo, não a taxa do `HEAD`.

## 4. A shell: `_consume` → `on_worker_caption`

`WorkerBridge._consume` é o único leitor do stdout do worker
(`[CODE] app/webview/sotto_webview.py:23866`), arrancado pela thread da ponte
(`[CODE] app/webview/sotto_webview.py:23888-23895`), e entrega cada linha a
`self.on_worker_caption(text, meta)` (`[CODE] app/webview/sotto_webview.py:23980-23981`). Esse método
(`[CODE] app/webview/sotto_webview.py:19327`) faz, por esta ordem — o passo 4 é o que faz a recusa de rota
do worker ser "entra no histórico e não pinta", porque o texto vai para a página ANTES do `return`:

| passo | o que faz | evidência |
|---|---|---|
| 1 | observa a sessão de histórico do `meta` | `[CODE] app/webview/sotto_webview.py:19335-19337` |
| 2 | funde stream+finisher quando `SOTTO_FUSION=1` (§5) | `[CODE] app/webview/sotto_webview.py:19346-19348` |
| 3 | recusa a linha local se o player é dono do ecrã | `[CODE] app/webview/sotto_webview.py:19357-19361` |
| 4 | `history_only` → painel/histórico e **return** (sem overlay) | `[CODE] app/webview/sotto_webview.py:19397-19401` |
| 5 | `emit_async('caption', …)` para o painel | `[CODE] app/webview/sotto_webview.py:19404` |
| 6 | `final`, `tap`, `at` para `emit` e `_live_stale_run = 0` | `[CODE] app/webview/sotto_webview.py:19415-19419` |
| 7 | escreve `CAPTION_IN` com `start/end/final/stable/tap_ms/age_ms` | `[CODE] app/webview/sotto_webview.py:19444` |
| 8 | conta `CAPTION_ARRIVAL_BLOWN` só para linha viva | `[CODE] app/webview/sotto_webview.py:19461-19463` |
| 9 | recusa a PINTURA se a idade do áudio passar de 30 s | `[CODE] app/webview/sotto_webview.py:19492-19503` |
| 10 | senão empurra para a janela: `push_caption_to_window` | `[CODE] app/webview/sotto_webview.py:19516-19519` |

## 5. A fusão: duas hipóteses, uma linha

A fusão está **desligada por omissão**: `fusion_enabled()` só devolve verdadeiro para `SOTTO_FUSION` em
`1/true/yes/on` (`[CODE] app/webview/sotto_webview.py:1083-1088`). O núcleo é `worker/fusion.py`, sem I/O
nem relógio: alinha as hipóteses por Needleman-Wunsch (`[CODE] worker/fusion.py:106-160`) e devolve as
`ops` e a `stability` (`[CODE] worker/fusion.py:328-459`).

O elo na shell é `_fusion_caption` (`[CODE] app/webview/sotto_webview.py:19178`): um parcial é guardado
como hipótese STREAM, indexado por `(sessão, start)` (`[CODE] app/webview/sotto_webview.py:19205-19213`);
um `final` da mesma identidade é a hipótese FINISHER e é fundido
(`[CODE] app/webview/sotto_webview.py:19214-19244`). Uma palavra revelada só é substituída se o finisher
discordar NELA e ambos os modelos nunca a tiverem confirmado (`[CODE] worker/fusion.py:58-68`); recusada
a palavra, sai o TARGET fundido e não o texto recebido (`[CODE] app/webview/sotto_webview.py:19263-19268`).
Cada edição deixa `FUSION_EDIT` (`[CODE] app/webview/sotto_webview.py:19259`) e uma falha deixa
`FUSION_FAILED` sem travar o texto (`[CODE] app/webview/sotto_webview.py:19239-19242`).

## 6. A pintura: um slot, um fio, um bitmap

`push_caption_to_window` (`[CODE] app/webview/sotto_webview.py:18877`) é o único emburrador da legenda
nativa: colapsa corridas de caracteres no texto do ASR (`[CODE] app/webview/sotto_webview.py:18888-18889`),
exige o interruptor do dono (`[CODE] app/webview/sotto_webview.py:18970-18972`), e escreve num **slot
único** `self._caption_pending = (now, text, previous, epoch)`
(`[CODE] app/webview/sotto_webview.py:18994`). Duas chegadas antes do pixel **engrossam** uma à outra;
uma linha nova que contém a pendente substitui-a (`[CODE] app/webview/sotto_webview.py:18981-18990`), e o
`tap_ms` do slot é o mais ANTIGO, para a idade não mentir
(`[CODE] app/webview/sotto_webview.py:18989-18990`).

A pintura corre num fio próprio, `sotto-caption-paint`
(`[CODE] app/webview/sotto_webview.py:18494-18501`), e o laço espera 0,5 s por um evento antes de
drenar (`[CODE] app/webview/sotto_webview.py:18503-18517`). `_drain_caption_pending`
(`[CODE] app/webview/sotto_webview.py:18296`) relê o interruptor NO INSTANTE DA PINTURA
(`[CODE] app/webview/sotto_webview.py:18336-18340`), descarta epoch gasto
(`[CODE] app/webview/sotto_webview.py:18317-18322`), calcula `late_s` como a idade do áudio limitada a 3 s
(`[CODE] app/webview/sotto_webview.py:18358-18366`) e chama
`ov.set_text(new_text, new_prev, instant, cue=cue, late_s=_late_s)` e `ov.show(True)`
(`[CODE] app/webview/sotto_webview.py:18369-18370`).

No overlay, `set_text` tem três fontes (`[CODE] app/webview/caption_overlay.py:1372-1410`): `cue`
(relógio do player), `instant=True` (desenha inteiro) e `instant=False` (ASR a crescer). No caminho ASR
a âncora é recuada pelo atraso medido, `live.push(full, time.monotonic() - late_s)`
(`[CODE] app/webview/caption_overlay.py:1428`), e não pelo instante de chegada: o lote entra no sítio do
áudio e o resto segue ao compasso.

O compasso da palavra vem de `youtube_reveal.LiveRows`: o intervalo mediano é `WORD_GAP_S = 0.24`
(`[CODE] app/webview/youtube_reveal.py:395`) e um lote de N palavras entra em `min(0.24, 0.36/N)` por
palavra, logo o último entra no máximo `MAX_LAG_S = 0.36 s` depois do primeiro
(`[CODE] app/webview/youtube_reveal.py:402,686`). O próximo instante é `next_clock(t)`
(`[CODE] app/webview/youtube_reveal.py:767-776`), e é ele que arma o frame
(`[CODE] app/webview/caption_overlay.py:843`).

O fade da linha nova está **desligado** (`FADE_ON = False`, `[CODE] app/webview/caption_overlay.py:533`):
a linha aparece. O fade de saída usa `word_fade.alpha_out` com `EXIT_S = 0.45`
(`[CODE] app/webview/youtube_reveal.py:506-517`, `[CODE] app/webview/word_fade.py:99`).

## 7. O painel: `caption`, `caption-applied` e `stats`

A página recebe o texto por `window.__sotto_emit('caption', …)`
(`[CODE] app/webview/sotto_webview.py:10717-10722`), conta por kind e chama o subscritor; o painel ingere
a linha no motor daquela `source` (`[CODE] app/panel/panel.js:1510-1513`) e o commit pinta a linha, chama
`recordHistory` e responde `bridge.captionApplied(text)` (`[CODE] app/panel/panel.js:1700-1701`). O prazo
é `COMMIT_MAX_HOLD_MS = 1500` (`[CODE] app/panel/caption-formulation.js:171`) e a rota é derivada de
`final` ali mesmo (`[CODE] app/panel/caption-formulation.js:672-677`).

`captionApplied` chega ao Python como kind `caption-applied` (`[CODE] app/webview/sotto_webview.py:11944`)
e cai em `_caption_applied` (`[CODE] app/webview/sotto_webview.py:12077`), o único lugar onde o pixel do
painel é datado:

* a idade só conta se o `tap` ainda não contou — `caption_lag_aged`
  (`[CODE] app/webview/sotto_webview.py:649-666`, chamado em `12100-12103`); um `tap` reutilizado
  publica `tap_reused=true` e não entra na série (`[CODE] app/webview/sotto_webview.py:12102-12108`);
* `final` não entra na série ao vivo, e `CAPTION_APPLIED` leva `kind`, `queue_ms`, `audio_ms`,
  `budget_ms` e `over` (`[CODE] app/webview/sotto_webview.py:12112-12126`);
* o estouro do orçamento tem linha própria: `CAPTION_BUDGET_BLOWN … path=panel`
  (`[CODE] app/webview/sotto_webview.py:12133-12137`).

A pintura provisória do DOM tem instrumento próprio: a página chama `SottoPaintSink`
(`[CODE] app/webview/sotto_webview.py:10738-10740`), o kind `paint-row` entra em `_paint_row`
(`[CODE] app/webview/sotto_webview.py:11890`), que escreve a linha só se ela começar por
`CAPTION_PROVISIONAL_PAINT` (`[CODE] app/webview/sotto_webview.py:12140-12153`).

`stats` é o outro push, um só payload para o pull e para o push: `stats()` devolve
`{tag:'meter', peak, blocks, paused}` com amostra fresca
(`[CODE] app/webview/sotto_webview.py:20230-20291`, `METER_FRESH_S = 2.0` em `3195`) e os campos de
`WORKER_STATS` quando não há (`[CODE] app/webview/sotto_webview.py:20292-20325`); `on_worker_stats`
empurra-o por `emit_async` (`[CODE] app/webview/sotto_webview.py:20534-20556`), que colapsa por KIND —
um payload pendente é substituído, nunca enfileirado duas vezes
(`[CODE] app/webview/sotto_webview.py:20620-20630`) — com o script `window.__sotto_emit(kind, json)`
(`[CODE] app/webview/sotto_webview.py:20661-20664`).

## 8. Quem entra no histórico

Há **três** portas, e cada uma recusa por uma razão diferente:

1. **O worker** marca `history_only` e `route_refused` (`[CODE] worker/live_route.py:304-305`); a shell
   respeita a marca sem julgar, emite ao painel e retorna antes do overlay
   (`[CODE] app/webview/sotto_webview.py:19397-19401`).
2. **O painel** deriva a rota: `final` → `final`; qualquer outra rota declarada é recusada
   (`provisional-draft` ou `unknown-route`); sem rota, só um produtor canónico entra, como `batch`; sem
   rota e sem produtor, `no-route-no-producer` (`[CODE] app/panel/history-source.js:130-142`); o produtor
   canónico é `redux` (`[CODE] app/panel/history-source.js:91-93`).
3. **O armazém** repete a invariante: `history_append` recusa `route=provisional-draft` e escreve
   `HISTORY_REFUSED` (`[CODE] app/webview/sotto_webview.py:15699-15704`).

O vocabulário que pode ser escrito no ficheiro é fechado e curto:

| tag | valores aceites | evidência |
|---|---|---|
| `route=` | `final`, `provisional-draft`, `batch` | `[CODE] app/webview/sotto_webview.py:870` |
| `src=` | `worker-stamped`, `worker-stamped-producer`, `panel-deadline`, `fallback` | `[CODE] app/webview/sotto_webview.py:892` |
| `producer=` | `redux`, `live` | `[CODE] app/webview/sotto_webview.py:901` |
| `via=` | `pc`, `youtube`, `external` | `[CODE] app/webview/sotto_webview.py:913` |

`_history_provenance` (`[CODE] app/webview/sotto_webview.py:15394`) monta o sufixo
`<!-- ctx1=… route=… producer=… via=… start=… src=… reason=… -->`; uma rota fora de `HISTORY_ROUTES`
devolve a string VAZIA (`[CODE] app/webview/sotto_webview.py:15411-15412`), e a linha é escrita na mesma,
sem marcador — um marcador que ninguém interpreta seria pior do que nenhum
(`[CODE] app/webview/sotto_webview.py:868-870`). O `start=` é a identidade da linha e permite reescrever
a linha que cresce em vez de acrescentar outra
(`[CODE] app/webview/sotto_webview.py:942-947`); `history_append` chama-o em
`[CODE] app/webview/sotto_webview.py:15806`.

`[MEASURED]` nesta máquina, 2026-11-11: `grep -c HISTORY_APPEND _main/webview-run.log` → `829` e `grep -c HISTORY_REFUSED` → `69` — as duas portas já correram; os números misturam shells de 2026-11-08 a 2026-11-11 e não são taxa do `HEAD`.

## 9. Os orçamentos que o código impõe

| constante | valor citado | onde | o que julga | quando estoura |
|---|---|---|---|---|
| `CAPTION_BUDGET_MS` | `1500` | `[CODE] app/webview/sotto_webview.py:18190` | idade do áudio até ao pixel | `CAPTION_ARRIVAL_BLOWN` na chegada, `CAPTION_BUDGET_BLOWN` na pintura |
| `CAPTION_HOLD_BAND_MS` | `(1490, 1520)` | `[CODE] app/webview/sotto_webview.py:18198` | separa "atraso" de "segura intencional" | marca `aged_kind=hold-expired` |
| `LIVE_PAINT_MAX_AGE_S` | `30.0` | `[CODE] app/webview/sotto_webview.py:2968` | legenda vs história | `LIVE_PAINT_REFUSED reason=stale`, sem overlay |
| `LIVE_PAINT_JITTER_S` | `0.25` | `[CODE] app/webview/sotto_webview.py:2982` | carimbo no futuro não é "agora" | idade devolve `None` |
| `LIVE_MAX_AGE_S` | `2.5` | `[CODE] worker/live_route.py:67` | idade que ainda pinta no worker | `history_only` |
| `CLOCK_JITTER_MS` | `250.0` | `[CODE] worker/live_route.py:74` | tolerância entre relógios | idade `None` |
| `CAPTION_FRAME_BUDGET` | `0.40` | `[CODE] app/webview/caption_overlay.py:81` | fracção de núcleo da pintura | período = `cost / 0.40` |
| `FRAME_S` / `FRAME_HZ` | `1/240` / `240` | `[CODE] app/webview/word_fade.py:44,47` | tecto de frames | piso do passo |

`[MEASURED] python -c "print(1000/240)"` → `4.167` e 240 × 0,56 = `134.4` frames ao tecto num bloco de
560 ms (2026-11-11). O tecto de 240 Hz **não é a taxa**: `_limit_by_paint` mede o custo real e impõe
`cost / CAPTION_FRAME_BUDGET` como período mínimo, dizendo no log `CAPTION_FRAME_LIMIT want_hz=…
paint_ms=… budget=0.40 rate_hz=…` no máximo uma vez a cada 5 s
(`[CODE] app/webview/caption_overlay.py:985-998`). `[INFERENCE]` com os 11,6 ms de p50 citados no módulo,
o piso é ~29 ms (34 Hz), não 240 Hz.

O relógio do frame é `perf_counter`, e a razão está no código: `time.monotonic()` nesta máquina tem 15
ms de granularidade, tornando inalcançável qualquer tecto acima de ~62 Hz
(`[CODE] app/webview/caption_overlay.py:487-501`); `_frame_now = time.perf_counter`
(`[CODE] app/webview/caption_overlay.py:502`). Os carimbos que saem do overlay continuam em
`time.monotonic()` (`caption_overlay.py:498-501`), porque comparam com o relógio do shell. O laço dorme
com `Event.wait` acima de 5 ms e `time.sleep` abaixo, sem voltar ao topo pelo último milissegundo
(`[CODE] app/webview/caption_overlay.py:1014-1045`).

## 10. O caminho do YouTube

O caminho do player **partilha** o slot, a thread de pintura, o overlay, o `history_append` e o
vocabulário de tags, e **contorna** o worker e a fusão: `external_caption` decide `final` pelo texto
(cue que estende o anterior é linha a formar) (`[CODE] app/webview/sotto_webview.py:19529-19566`), carimba
`start`/`end` em `time.monotonic()` com `historySession='external'`
(`[CODE] app/webview/sotto_webview.py:19581-19594`), emite `external-caption` ao painel
(`[CODE] app/webview/sotto_webview.py:19639-19642`) e empurra para a janela com `rows=`/`cue=`
(`[CODE] app/webview/sotto_webview.py:19672`). `[CODE]` uma linha do YouTube NUNCA passa por
`live_route.admit` nem por `_fusion_caption`: o seu `tap_ms` é `None` e a testemunha dela é
`CAPTION_PAINT_SURFACE src=player` (`[CODE] app/webview/sotto_webview.py:18387-18391`). O relógio do
player, a troca de vídeo e as línguas estão em `06-YOUTUBE.md`.

## Lacunas

- `[UNKNOWN]` O comportamento do `HEAD` no processo vivo: o oráculo diz `STALE` (`MUDOU DEPOIS DO
  ARRANQUE: sotto_webview.py`, 2026-11-11 23:28) e `CAPTION_PAINT_SURFACE` tem **0** ocorrências no log
  (`[MEASURED] grep -c CAPTION_PAINT_SURFACE _main/webview-run.log` → `0`). Fechar exigiria relançar a
  app e pintar uma linha em cada superfície — proibido nesta lane.
- `[UNKNOWN]` A taxa de frames alcançada neste `HEAD`: `CAPTION_FRAME_LIMIT` só é escrito quando o custo
  morde (`[CODE] app/webview/caption_overlay.py:992-998`) e `[MEASURED] grep -c CAPTION_FRAME_LIMIT` → `23`
  no ficheiro misto, sem separar por processo.
- `[UNKNOWN]` A fracção de linhas que a porta de rota recusa em `HEAD`: o log tem `24`
  `LIVE_ROUTE_REFUSED` (`[MEASURED]`, 2026-11-11), mas o processo é anterior ao disco.
- `[UNKNOWN]` Se a linha `redux-live` deve pintar: `producer=redux` (`[CODE] worker/redux_live.py:1535`) é
  classificado como `redux` (`[CODE] worker/live_route.py:142-151`) e `admit` marca `history_only` por
  `batch-route`, mas não encontrei afirmação escrita de que seja o desenho.
- `[UNKNOWN]` O tempo real de decode por bloco: os 120–400 ms de
  `[CODE] app/webview/sotto_webview.py:18182-18187` são comentário de 2026-11-03, não medição desta lane
  (medir exige o modelo carregado e um tap vivo).
- `[UNKNOWN]` O efeito da fusão em produção: `SOTTO_FUSION` está desligado por omissão
  (`[CODE] app/webview/sotto_webview.py:1083-1088`) e não li o ambiente da largada do dono; fechar exige
  `grep SOTTO_FUSION` no ambiente do processo ou `grep -c FUSION_EDIT` num log fresco.
