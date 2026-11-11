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

