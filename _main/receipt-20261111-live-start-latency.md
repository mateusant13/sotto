# RECIBO - "abro o sotto e a legenda nao funciona": a cadeia medida (dono, 2026-11-11)

Sessao viva: pid 49180, arranque `2026-11-11 17:34:20.322`, log `_main/webview-run.log`.
PASSO 0 (`_main/live-code-freshness-oracle.py --strict`): `LIVE_CODE FRESH` -- processo e disco
com o mesmo sha256 (`C9F1CDB08819`, 109 ficheiros), nenhum ficheiro mudou depois do arranque.
Logo toda a medicao abaixo e' do codigo que esta' no disco AGORA, nao de codigo velho.

## 1. O que ele disse, e o numero que cada frase tem por tras

| fala dele (verbatim) | medido | veredicto |
|---|---|---|
| "meu ctrl space nao fez nada assim que abri o sotto" | `HOTKEY_PRESSED` 17:34:26.599 -> `LIVE_ENABLED on=true` 17:34:26.619 (**20 ms**); nada no ecra ate' 17:36:02.4 | a TECLA foi honrada; a TELA ficou muda **95,8 s** |
| "leva mais de um segundo pra legenda funcionar" | arranque -> primeira pintura **102 110 ms** | `BOOT-INTERACTION VERDICT: FAIL` (orcamento 15 000 ms) |
| "abri um video no youtube, levou 3 segundos" | `TARGET_REBOUND` 17:46:10.205 -> `TRACK_READY has-track` 17:46:18.474 -> primeira linha 18.547 = **8,3 s** | o mesmo defeito, pior do que ele contou |
| "aparecendo na tela de forma aleatoria so' porque ta tocando um audio" | o ASR transcreve o audio do PROPRIO YouTube enquanto a faixa do YouTube tambem pinta (`YT_FRAME rows=1` as 17:46:18.547 e `CAPTION_IN` do ASR as 17:46:05.822) | duas fontes na mesma tela |
| "ta dando replay em audios que ja tocaram a minutos atras" | `CAPTION_IN start=381.84` pintado as 17:46:05.822; captura comecou 17:34:42.834, logo aquele audio e' de **17:41:04.7 = 5 min 01 s atras** | o relogio do stream perdeu 5 minutos |

## 2. A cadeia, elo por elo (todos do log de hoje)

```
17:34:20.322  SHELL_STARTUP_STAGE
17:34:20.517  HOTKEY_REGISTERED Alt+C
17:34:20.523  SPACE_SWALLOW_INSTALLED (Ctrl+Space ENGOLIDO)
17:34:20.524  HOTKEY_LIVE_ARMED Ctrl+Space          <- a tecla esta' viva 0,2 s apos o arranque
17:34:20.539  WARM_FALLBACK_COLD reason=absent       <- o motor quente ainda NAO existia
17:34:20.559  BRIDGE_SPAWNED pid=54524               <- o worker nasce A FRIO
17:34:20.921  WARM_ENGINE_START_TASK rc=0            <- 382 ms DEPOIS; corrida perdida por desenho
17:34:26.599  HOTKEY_PRESSED (Ctrl+Space)            <- o dono aperta 6,3 s apos abrir
17:34:26.619  LIVE_ENABLED on=true                   <- honrado em 20 ms
17:34:35.651  BRIDGE_LOAD_MS ms=15109                <- modelo pronto 15,1 s depois do spawn
17:34:42.834  STATUS_APPLIED capture-started
17:34:49.620  STATUS_APPLIED tap-silent-desktop
17:35:26.461  STATUS_APPLIED device-rotated (flat)   <- 66 s num endpoint com peak 0.0
17:36:02.432  primeira pintura visivel (927 CAPTION_PROVISIONAL_PAINT na sessao)
```

Quatro custos independentes, cada um com a sua lane:

1. **Motor quente perdido por 382 ms** (`WARM_FALLBACK_COLD` antes de `WARM_ENGINE_START_TASK`):
   o arranque paga 15,1 s de carga a frio onde a medicao da casa diz **0,97 s** de attach.
2. **Escada de dispositivo**: 66 s num endpoint plano (`tap-silent-desktop` -> `device-rotated (flat)`)
   e `CAPTURE_SIGNAL_BACK gap_s=63` -- a primeira legenda de audio dele nao podia existir antes disso.
3. **YouTube**: `REBIND_ARMED confirm_s=1.5` (12 x `REBIND_DAMPED`), depois
   `CDP_SOURCE state=slow` -> `slow-dead (3 prazos)` -- **6,1 s** de socket morto antes de qualquer
   re-attach -- e mais 5,9 s ate' a faixa ser listada. Na sessao: **15 anexacoes** em 12 minutos
   (`ATTACH_OK attempt=14`, `attempt=15`) e `state=wrong-video` a repetir.
4. **Live ASR 5 minutos atras**: `WORKER_COST cpu_pct_avg=174.1 cpu_s_per_row=3.500` e
   `REDUX_BATCH_KICK audio_s=156.24 held_in=13502 asr_waits=1 asr_expired=5` no mesmo instante.
   O texto que ele viu "replay" e' o stream a drenar audio de 17:41:04.

## 3. Por que ele viu o "nada": o aviso existe e e' de disparo unico

`on_worker_loading_text` pinta `carregando modelo...` quando o worker publica `state=model-loading` e o
shell ainda nao tem `loaded`. Foi **uma** vez, ~17:34:20.6, quando `CAPTION_WANTED_RESTORED on=false`:
a legenda ao vivo estava DESLIGADA, logo a janela nem existia. Quando ele ligou as 26.619, o aviso ja'
tinha sido consumido e nada o re-arma. Um EVENTO servido antes do interruptor nao e' um estado.

## 4. O instrumento que devia ter apanhado isto estava cego

`_main/boot-interaction-oracle.py` casava `'CAPTION_PAINT '` (com espaco) e `CAPTION_OVERLAY_LAG`.
O log tem `CAPTION_PAINT_LAG` (29) e `CAPTION_PROVISIONAL_PAINT` (927) -- **956 pinturas invisiveis**
ao portao, que respondia `UNMEASURED -- sem pintura no log`. Corrigido nesta rodada com
`_paint_witness`: cinco formas, a mais antiga em TEMPO ganha, e o `--neg-arm` ganhou **G3/R6b/G4/G5**
(um braco por forma, e o RED continua a cair em cada uma): `NEG-ARM: PASS -- 12/12`.

Depois da correcao o portao diz o que o dono sentiu:
`arranque -> 1a legenda = 102110.0 ms` contra 15000 -> **FAIL**, com a nota a dizer qual testemunha
(`PAGINA, nao overlay`) para ninguem ler o numero como se fosse pixel do overlay.

## 5. O QUE FALTA, e o que NAO esta' medido

- As quatro curas estao em quatro lanes (YtInstant, BootAck, LiveRoute, DeviceLadder). Nenhuma foi
  vista na tela dele: `verified` continua a exigir uma corrida real da app, pela mao dele.
- `CAPTION_PAINT_SURFACE` (a testemunha do overlay para o caminho do player) ainda nao existe no
  ficheiro; enquanto nao existir, o numero acima e' o da PAGINA, e o pixel do overlay pode vir depois.
- O `WARM_FALLBACK_COLD` e' uma CORRIDA (382 ms) medida uma vez nesta sessao. Uma corrida so' nomeia
  a classe; nao mede a frequencia. Re-medir em tres arranques antes de afirmar "sempre".

## 6. "A legenda aparece de forma aleatoria" -- MEDIDO: DUAS ROTAS PINTAM NA MESMA JANELA

Recorte de `_main/webview-run.log` (pid 49180), um intervalo de 4 s:

```
17:46:02.090 CAPTION_PROVISIONAL_PAINT n=1185 src=external:youtube:track text="parking space."
17:46:05.822 CAPTION_IN start=381.84 end=383.84 final=true tap_ms=None age_ms=None text="replanement of code water, shows a level of leadership dinga"
17:46:05.826 CAPTION_PROVISIONAL_PAINT n=1186 id=381.84 src=- conf=0 prov=10 text="replanement of code water ..."
17:46:18.547 YT_FRAME src=external:youtube:track rows=1 lines=['My name is Chip, used to be the lead designer at Grab.']
```

Tres leituras, cada uma com o numero ao lado:

1. **A guarda de rota EXISTE e a maioria das linhas e' barrada -- mas a transicao e' MUDA.**
   `grep -c AUDIO_ROUTE` no log da' **0**: essa tag nao existe nesta arvore, e a primeira versao
   deste paragrafo afirmou-a. O que existe medido: `EXTERNAL_CAPTIONS_ASR_SUPPRESSED count=1`
   as 17:36:30.317 e `count=100` as 17:48:02.336 -- 99 linhas do ASR barradas em 11,5 min pelo
   portao de `on_worker_caption` (`external_captions_active and not source.startswith('external:')`).
   Mesmo assim 3 chegaram ao ecra (`src=-`), logo a bandeira estava **False** naqueles instantes.
   O unico sitio que a poe a False e' `external_captions_active = False` em `_release`, e a linha
   `EXTERNAL_CAPTIONS_RELEASED` vive DENTRO de `if self.last_line:` -- uma limpeza com `last_line`
   vazio limpa as bandeiras **sem escrever nada**. Nenhum `EXTERNAL_CAPTIONS_RELEASED` existe em
   2026-11-11. Ou seja: a troca de dono da superficie acontece, e o log nao a tem.
2. **O payload do ASR nao traz a idade do audio**: `tap_ms=None age_ms=None`. Sem esse numero nao
   existe recusa possivel do lado da shell, e e' por isso que o atraso de ~5 min nao tem portao.
3. **O texto do ASR nao e' o audio que o player toca.** No mesmo instante o player diz "My name is
   Chip, used to be the lead designer at Grab" e o ASR diz "replanement of code water ... leadership
   dingases". Nao e' so' corrida de rota: o tap esta' a ler outra fonte desde a rotacao
   (`device-rotated reason=flat` 17:35:26 -> `tap-own-endpoint-loud` 17:35:34).

Classe do defeito, decidida pela medicao: **(c) o tap pega a fonte errada** + **(a) nao ha guarda de
rota na pintura**. As duas sao independentes e as duas tem de cair: uma guarda de rota sozinha
esconde a (c) sem a corrigir.

## 7. A CADEIA FECHADA: reconexao CDP -> adocao de OUTRA aba -> superficie em branco -> o ASR pinta

Os mesmos 4 s da secao 6, agora com os elos que faltavam (log vivo, pid 49180):

```
17:46:02.951 YOUTUBE_CDP_SOURCE state=slow (ConnectionAbortedError)
17:46:03.003 YOUTUBE_CDP_SOURCE state=reconnect (ConnectionAbortedError)
17:46:03.512 YOUTUBE_CDP_TAB_SWITCH from=8C97D93B... to=4D2C5751... vid=JM1gEnmaUao
17:46:03.513 YOUTUBE_TARGET pick=JM1gEnmaUao why=paused-loaded declared=zEgthOmOrc0 tabs=7
17:46:05.039 YOUTUBE_CDP_SOURCE state=adopted:zEgthOmOrc0->JM1gEnmaUao
17:46:05.108 CAPTION_WINDOW_BLANKED reason=video-changed epoch=30 wanted=false
17:46:05.108 YOUTUBE_VIDEO_CHANGED video_id=JM1gEnmaUao
17:46:05.822 CAPTION_IN ... text="replanement of code water, ..." ; PAINT n=1186 src=-
17:46:18.547 YT_FRAME src=external:youtube:track lines=['My name is Chip, used to be the lead designer at Grab.']
```

Cada elo e' um facto medido, e a soma e' a queixa do dono:

1. **A reconexao ADOTA outra aba.** Com 7 abas abertas, `pick` escolheu `JM1gEnmaUao`
   (`why=paused-loaded`) embora o video declarado fosse `zEgthOmOrc0` e o dono estivesse a ver esse.
   Uma queda de socket virou uma TROCA DE VIDEO.
2. **A troca esvazia a superficie e baixa o dono dela** (`VIDEO_CHANGED` -> `last_line=''`). O
   `_release` seguinte limpa `external_captions_active` sem escrever linha (secao 6).
3. **714 ms depois o ASR pinta** a hipotese dele -- audio de outro momento (`start=381.84`), com
   `src=-` e `tap_ms=None`. O dono ve uma frase que nao tem nada a ver com o que esta' no ecra.

Ou seja, "a legenda aparece de forma aleatoria" nao e' aleatorio: e' **reconexao -> adocao de aba
errada -> superficie sem dono -> ASR**. E' a mesma classe do `yt-target-stale` de 2026-11-03 (o id
declarado ficou 164 linhas no log com outra aba aberta), agora com a metade da pintura.

Correcoes exigidas, por elo: (i) `pick` nunca adota aba que nao seja o video declarado, e nunca
prefere uma `paused-loaded` a uma a tocar; (ii) a troca de video NAO baixa o dono da superficie sem
linha (a transicao tem de ser escrita, e o ASR nao pinta numa superficie que o player acabou de
esvaziar); (iii) o `CAPTION_IN` do ASR tem de carregar `tap_ms`, senao a shell nao tem como recusar.

## 8. A ESCADA DE DISPOSITIVO, RUNG POR RUNG: quem decide e' 6 s, quem ESPERA e' a guarda

Tabela do mesmo arranque (pid 49180), lida do log da shell:

| quando | linha | delta |
|---|---|---|
| 17:34:42.832 | `LADDER_TRY attempt=1/11 device='...VoiceMeeter Input...' ms=16 result=opened` | -- |
| 17:34:49.620 | `STATUS tap-silent-desktop` | +6,8 s |
| 17:35:26.461 | `STATUS device-rotated (flat)` | **+43,6 s do open** |
| 17:35:27.496 | `LADDER_TRY attempt=2/11 device='...CABLE Input...' ms=46 result=opened` | +1,0 s |
| 17:35:34.282 | `STATUS tap-own-endpoint-loud` | +6,8 s |
| 17:36:03.942 | `STATUS Receiving captions` | +40,1 s do attempt 1 |
| 17:36:30.732 | `CAPTURE_SIGNAL_BACK gap_s=63 blocks=1072 captions=1` | -- |

O numero que importa: a JANELA que decide a rotacao e' **6,0 s** (o proprio `NO_AUDIO_CLEARED
evidence=... window_s=6.0`), mas a rotacao so' veio aos **43,6 s**. Os ~37 s do meio sao a guarda
`silent_desktop_hold` (cura de 2026-11-04, que ESTENDE a mesma tap 6 -> 12 -> 24 -> 48 -> 60 s
enquanto ninguem toca em endpoint nenhum) a segurar um rung que ja' tinha dado zero.

E o medidor NAO estava cego -- a hipotese foi testada e caiu: 1441 `BRIDGE_METER` na sessao, 740 com
`peak > 0` (0,3244 / 0,1924 / 0,5782 / 0,1088 / 0,652 / 0,4737 nas ultimas). Durante a janela plana o
`peak=0.0` era VERDADE. A cura certa e' a guarda que espera, nao o instrumento que mede.

## 9. O PROCESSO VIVO JA' E' MAIS VELHO QUE O CODIGO (2026-11-11, 20:0xZ)

`python _main/boot-interaction-oracle.py` passou a imprimir
`BOOT-INTERACTION SKIPPED reason=stale-process live=LIVE_CODE STALE log=...webview-run.log`, com cada
falha reimpressa como `STALE-EVIDENCE`. Nao e' um defeito do oraculo: o processo do dono (pid 49180)
arrancou as 17:34 e as quatro lanes desta rodada estao a escrever a arvore agora. Qualquer numero da
sessao viva mede o codigo ANTIGO.

Consequencia, e ela vai no relatorio final sem eufemismo: as curas desta rodada sao **fixed, NOT
verified** ate' o dono reiniciar a app. O que ja' esta' fechado e' a MEDICAO (secoes 2-8) e o
instrumento que a torna juiz.

### 7-bis. A FREQUENCIA do defeito, no log de hoje (pid 49180)

| evento | contagem |
|---|---|
| `YOUTUBE_CDP_SOURCE state=slow (WebSocketTimeoutException)` | 65 |
| `YOUTUBE_CDP_SOURCE state=reconnect` | 4 |
| `YOUTUBE_CDP_SOURCE state=adopted:<de>-><para>` | **5** |
| `YOUTUBE_CDP_SOURCE state=attached` | 48 |
| `CAPTION_WINDOW_BLANKED` | 46, em **7** milissegundos com mais de um blank |

Cinco adocoes numa sessao e' a taxa da "legenda aleatoria": cada adocao fabrica o
`VIDEO_CHANGED` que esvazia a superficie e baixa o dono dela. E os 7 milissegundos com dois blanks
significam que o epoch sobe duas vezes no mesmo instante -- dois objetos, ou um objeto a esvaziar
duas vezes. Nenhum dos dois casos tem linha que os distinga.


### 7-ter. O QUE ELE VE DEPOIS DO BLANK: o ASR repinta a fala do proprio video, em ingles, 0,11 s depois

A pergunta que faltava responder era *"o texto que sobe depois do blank e' ruido ou e' fala?"*. Medido
hoje em `_main/webview-run.log` (pid 49180): para cada `CAPTION_WINDOW_BLANKED`, a primeira pintura nos
2 s seguintes, com o texto:

| atraso | tipo | texto pintado |
|---|---|---|
| +0,11 s | final | `"It looks like we have our first."` `count=457 aged_kind=final-close` |
| +0,98 s | partial | `"Led me."` `audio_ms=83 queue_ms=3 budget_ms=1500 over=false` |
| +0,14 s | final | `"Mmm."` `count=506` |
| +0,71 s | final | `"Recent knowledge it looks like opening eye testing up."` `count=529` |
| +0,65 s | final | `"Is basically unpar or even slightly."` `count=595` |

Duas conclusoes, as duas com numero:

1. **O texto e' a FALA DO VIDEO, transcrita pelo NOSSO motor** (nao e' ruido nem alucinacao): o tap
   carrega o audio do YouTube, o ASR transcreve-o em ingles, e a linha sobe para a superficie.
2. **O blank e' desfeito em 0,11 s.** Um esvaziamento que a rota local pode repintar imediatamente nao
   e' uma cerca: e' um piscar. Enquanto a rota local tiver permissao de pintar com o player a decorrer,
   o `CAPTION_WINDOW_BLANKED` e' decorativo -- e sao **311** linhas `CAPTION_WINDOW_BLANKED` no log.

E' exactamente a porta `player-owns-route` que o `worker/live_route.py` passou a fechar (o shell declara
que o player pinta, a linha local do MESMO audio nao pinta por cima), e o numero que a justifica e' o par
acima: pintura em 0,11 s contra um blank de 7 ms.

A leitura do DONO (*"fica aparecendo na tela de forma aleatoria so' por que ta tocando um audio, que nem
speaker e'"*) estava certa em cada palavra: e' o audio do video, e o momento e' o do blank/adocao.

## 10. AS CURAS, com o numero de cada uma (2026-11-11, sessao inteira)

| # | o que estava partido (medido) | a cura | o numero |
|---|---|---|---|
| 1 | o Ctrl+Space registava e o ecra ficava mudo: primeiro pixel **95,8 s** depois (so' quando uma faixa do YouTube apareceu) | o toggle LE o bloqueador no instante e escreve a razao verdadeira na mesma fenda da legenda (`model-loading`, `waiting-first-line`, `no-track`, `no-audio`, `waiting-player-row`), com poll de 250 ms enquanto houver status no ecra | status em **<= 2 ms** no harness; `_main/live-ack-oracle.py` **9/9**, neg-arm **7/7** |
| 2 | audio de **301 s** atras pintado como ao vivo (`CAPTION_IN start=381.84 final=true tap_ms=None`) | `LIVE_PAINT_MAX_AGE_S = 30.0` (3,7x o pior caso HONESTO medido: 1846 parciais com `tap_ms`, p99 **1837 ms**, max **8070 ms**) recusa a PINTURA e nunca o texto -- o `emit_async` ja' correu, o historico fica | `LIVE_PAINT_REFUSED` uma vez por episodio |
| 3 | **1818** pinturas com audio velho no log, pior caso **3543,40 s**; o lote pintava e o ruido (`Mmm`) pintava | `worker/live_route.py` (puro) com as portas na ordem em que cada uma cala a linha: rota de lote -> posse do player -> ruido -> velho/fresco/desconhecido; `admit` e' o ponto UNICO no `emit` | replay do corpus: **0** pinturas de lote, `live_paints=1943`, `live_refused=143`; oraculo **42/42**, neg-arm **8/8** |
| 4 | a escada de dispositivo esperava **43,63 s** num rung que entregou ZERO (dobragem 6->12->24->48) e abria antes um endpoint plano conhecido | `FLAT_EVIDENCE_S = 4.0` (janela em que um endpoint a renderizar teria entregue ~2000 amostras = 50x o piso) + journal do tap (`%LOCALAPPDATA%\Sotto\endpoint-signal.json`) que poe o sinal a' frente e o plano provado no fim | rung->rotacao **43,63 s -> 0,00 s**; abertura->1o dispositivo com sinal **43,673 -> 0,016 s** (journal quente); oraculo **17/17**, neg-arm **6/6** |
| 5 | o `log=err` do filtro da rota levantava `UnboundLocalError` na PRIMEIRA legenda -- a cura custava a legenda que existia para proteger | `route_log` (stderr que nunca levanta); o filtro da rota nao pode partir o `emit` | `emit-pipe-dead` **PASS** (5 arms) e neg-arm a apanhar 4 |

### 10-bis. A ORDEM DOS COMMITS, e por que cada um e' um so'

`52b9884` a lei (troca de dono se escreve; reconexao e' transporte) -> `cb60f58` o recibo do blank
repintado em 0,11 s -> `58ee568` o shell (ack + idade) -> `b0bfa76`/`540f11b` a escada e o journal ->
`0136e19` os dois instrumentos da janela plana -> `3cd27c6` a rota ao vivo no worker ->
`fb3206d` o `UnboundLocalError` -> `9c9212e`/`69975d0` os dois stubs com a assinatura de ontem.

### 10-ter. TRES DEFEITOS DE INSTRUMENTO, todos da mesma forma

1. **`boot-interaction-oracle` dizia UNMEASURED** "arranque -> 1a legenda" com pinturas no log (casava
   duas das cinco formas de linha). Corrigido; e' o juiz desta rodada.
2. **Dois oraculos carimbavam 12/24/48/60** e ficaram vermelhos quando a janela plana passou a 4 s --
   o instrumento a acusar quem esta' certo. Agora perguntam o numero ao PRODUTO e um arm novo exige
   que ele seja curto (<= 8 s).
3. **Dois stubs tinham a assinatura de ontem** (`take_pending(max_s=)`, `_start_pass(..., last_s)`), e o
   `TypeError` subia de DENTRO do produto. Corrigidos nos dois sitios.

E uma limitacao que fica escrita: o `undefined-names` **nao** apanha a classe do `UnboundLocalError`
(`err` esta' definido no escopo, via `except ... as err`). Quem a fecha e' a arm que conduz o `emit`
REAL -- a que a lane da rota esta' a escrever.

### 10-quater. O QUE CONTINUA NAO MEDIDO

* Nada disto correu na INSTANCIA dele: as curas estao no disco e o processo vivo (`pid 49180`) e'
  anterior ao codigo. `live-code-freshness-oracle --strict` diz **STALE**, logo o veredicto e'
  **fixed, NOT verified** ate' ele reiniciar a app (a shell nao se relanca sozinha: `--no-self-relaunch`).
* Os numeros de "antes" sao do log dele; os de "depois" sao de replay e de harness. A medicao que
  fecha o ciclo e' o proximo arranque dele com `CAPTION_STATUS_SHOWN`, `LIVE_PAINT_REFUSED` e
  `CAPTION_PAINT_SURFACE` no log.

## 11. AS QUATRO LANES, integradas (2026-11-11, tarde)

O dono, verbatim: *"bota subagents pra arruamr toda tua todo list"*. Quatro lanes
despachadas num lote unico, cada uma com o seu ficheiro e o seu oraculo; a
integracao e' este assento, porque os ficheiros partilham a shell.

| lane | pedido (verbatim do dono) | o numero antes -> depois | oraculo (positivo / negativo) |
|---|---|---|---|
| YtInstant | *"eu abri um video no youtube, e levou 3 segundos pra aparecer a legenda. inves de ser INSTANTANEO. arruma"* | troca -> 1a foto **11 203 -> 388 ms**; morto, 1o prazo -> 1a foto **8 482 -> 388/888 ms**; damp de rebind **1 541 -> 0 ms** | `youtube-first-cue` **11/11** / **11/11** (3 mutantes do SHELL) |
| BootAck | *"meu ctrl space nao fez nada assim que abri o sotto"* | OFF com o ecra vazio: **0** pixeis, **0** linhas -> status em **0 ms** + timer de 6 s que o remove; `age_s=-5.0` era AFIRMADO como fresco -> `None` | `live-ack` **14/14** / **14/14** |
| LiveRoute | *"a legenda ... aparece de forma aleatoria so' por que ta tocando um audio"* | **1818** pinturas com audio velho (pior **3 543,40 s**) -> **0** pinturas de lote no replay; 143 de 2 086 linhas ao vivo recusadas e escritas no historico | `live-route` **48/48** / **9/9** (o I1 conduz o `emit` REAL) |
| DeviceLadder | *"abro o sotto, e leva mais de um segundo pra legenda funcionar"* | rung->rotacao **43,63 -> 0,00 s**; abertura->1o dispositivo com sinal **43,673 -> 0,016 s** | `device-ladder-cost` **17/17** / **6/6** |

### 11-bis. O que a INTEGRACAO teve de decidir (e por que)

- **A ordem dos encaixes na shell e' uma so'.** `on_worker_caption` recebeu a posse do ecra
  (`81100ad`) antes de a primeira cue desta rodada (`d2c281a`); o parche da posse foi rebaseado
  contra o ficheiro vivo, nao contra o de ontem, e o `live-route` voltou a **48/48** com as tres
  arms de encaixe a deixarem de dizer `pending:patch`.
- **A cura das funcoes puras nao chega ao processo sozinha.** YtInstant entregou o modulo e
  declarou os tres encaixes na shell; este assento escreveu-os, e a arm **W1** passou a lê-los por
  `ast`. Sem ela o oraculo ficava verde sobre um modulo que a app nunca chama -- a classe do
  `panel-deps`, que esta casa ja' pagou tres vezes.
- **Um instrumento a acusar quem esta' certo, tres vezes na mesma rodada.** Dois stubs com a
  assinatura de ontem (`take_pending(max_s=)`, `_start_pass(..., held_before_s)`) levantavam
  `TypeError` de DENTRO do produto; e a primeira versao da arm do epocario media o NOME
  (`_read_slow_until` em qualquer sitio) em vez do caminho -- o mutante `if False:` passava. Todos
  corrigidos e medidos.

### 11-ter. O COMMIT MAP desta rodada

`061b6eb` a cue do YouTube (modulo) -> `c51b104` o shell do ack/idade do ON -> `81100ad` a posse
do ecra com um escritor -> `d2c281a` os tres encaixes na shell + a arm W1 -> `6d01948` os tres
pares na bateria e o pin re-medido (`358768 B` / `4150 CRLF` / `0 bare LF`) -> `ff65544` o
ratchet do `code-health` absorvendo o crescimento declarado.
Antes: `52b9884` `cb60f58` `58ee568` `b0bfa76` `540f11b` `0136e19` `3cd27c6` `fb3206d`
`9c9212e` `69975d0` `a9fcc3b`.

### 11-quater. A FRONTEIRA, outra vez

**fixed, NOT verified.** Os quatro pedidos estao no disco e provados por oraculo; o processo vivo
(`pid 49180`, arrancado antes do codigo) continua a correr a versao anterior -- `live-code-freshness
--strict` diz **STALE**, e a shell nao se relanca sozinha (`--no-self-relaunch`). O ciclo fecha no
proximo arranque dele, com estas linhas no log:

- `CAPTION_STATUS_SHOWN reason=model-loading|waiting-first-line|...` (o Ctrl+Space responde);
- `LIVE_PAINT_REFUSED` e `EXTERNAL_OWNER` (a rota e a posse do ecra);
- `YOUTUBE_VIDEO_CHANGED video_id=... why=rows-ready|tab-switch` (a cue instantanea);
- `YOUTUBE_READ_HOLD_DROPPED` e `DEVICE_LADDER_SIGNAL` (o alvo novo e a escada).
