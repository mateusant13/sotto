# A legenda do YouTube, 1:1 — medido em `WdaHAGRBB6s` (2026-10-22)

O dono, verbatim:

> *"legenda do youtube ta completamente bugada. … tu vai pegar exatamente a transcricao do
> navegador/youtube desse video e comparar com o que aparece no transcript do sotto. vai comparar
> tanto a legenda ao vivo que a gente retira do proprio youtube, quanto a legenda ao vivo usando os
> modelos locais. a que retiramos do youtube, tem que bater timing, linha/~quebra de linha e etc, 1:1."*
>
> *"e nao esquece: tu vai fazer funcionar 1:1, e tambem ter o display 1:1. é pra surgir palavras,
> quebrar linhas, usar o timing de nova linha ou nao, igual o youtube. e se tu nao souber fazer isso,
> pesquisa online"*

## 1. De onde veio a verdade

O browser usado foi o Chrome do `chrome-devtools-mcp` (porta 9222), **não** o Chrome do dono
(`DevToolsActivePort` = 60427). O dono respondeu que não era preciso o dele. Nenhuma janela dele foi
tocada.

A verdade não foi lida do ecrã: foi lida do **payload que o próprio player consome**
(`/api/timedtext … fmt=json3`), que é o mesmo documento que desenha a legenda. O painel de transcrição
do YouTube não chega a listar nada neste vídeo — o botão de legendas diz
*"Não há legendas/legendas descritivas disponíveis"* mesmo existindo a faixa `en-orig` —, por isso a
comparação é feita contra o payload, não contra o painel.

Ficheiro de verdade, guardado no repo: **`_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3`** (9 304 B).

## 2. O comando e a saída (executado)

```
python _main\youtube-1to1-probe.py --video WdaHAGRBB6s
```

```
track do YouTube : en-orig (auto) English (Original)
janela do player : rcRows=2 ccCols=40
linhas do YouTube: 19   |   cues do Sotto: 19
…
IGUAIS no texto: 19/19   |   IGUAIS no start: 19/19

A JANELA ao longo de 33.8 s (amostra a cada 0.1 s, 339 amostras):
  YouTube com DUAS linhas vivas :  32.0 s  (94%)
  YouTube com UMA linha viva    :   1.9 s  (6%)
  YouTube sem linha viva        :   0.0 s  (0%)
```

**A extração já está 1:1.** As 19 linhas que o player do YouTube desenha e os 19 cues que o
`youtube_captions.fetch_track` devolve coincidem **no texto e no instante de entrada, 19 de 19**,
incluindo os fragmentos que parecem errados (`'>> No.'`, `'fine.'`,
`">> No, you don't understand."`). O que o dono viu no histórico não é a extração a mentir — é o
**display** a deitar linhas fora e a repeti-las.

## 3. O defeito do display, com o número

O payload declara a janela em `wpWinPositions[1]`: **`rcRows: 2`** e **`ccCols: 40`** — duas linhas de
quarenta colunas. Cada linha é um evento sem `aAppend`; cada separador é um evento `aAppend: 1` cujo
único segmento é `"\n"`.

Duas linhas ficam vivas ao mesmo tempo durante **94 % do vídeo** (32,0 s de 33,8 s). O caminho vivo
chamava `youtube_captions.cue_at`, que devolve **um** cue (o que começou por último) — logo deitava a
segunda linha fora em nove décimos do tempo, e a linha que ficava mudava a cada poll. É daí que vêm as
seis cópias da mesma frase e a frase partida ao meio (`"I'll be"` sem o `"fine."` que vinha na linha
seguinte).

Exemplo do que o YouTube desenha, medido:

| t (s) | linhas no ecrã do YouTube |
|---|---|
| 2,12 | `'Have you ever had to kill a man?'` + `'>> No.'` |
| 6,35 | `'>> Then this sword is useless.'` + `">> Don't worry about me, Yamato. I'll be"` |
| 10,58 | `"After the ritual, I'd love to train with"` + `"you sometime. Blackmore Academy doesn't"` |

O `cue_at` mostrava só a de baixo, e trocava-a por outra linha no instante seguinte.

## 4. O que foi feito (código novo, sem tocar em ficheiro de outra lane)

**`app/webview/youtube_window.py`** — a regra que o payload descreve, em duas linhas:

```python
vivas(t)  = [c for c in cues if c.start <= t < c.end]
desenho(t) = vivas(t)[-2:]      # a capacidade que o rcRows declara
```

com `window_key(lines)` (chave estável, com ordem, para o chamador só emitir quando a janela MUDA) e
`history_line(lines)` (as duas linhas juntas, sem repetir o pedaço que já está na anterior).

**`_main/youtube-window-oracle.py`** — o portão. A expectativa é calculada dos **eventos crus**, não do
parser julgado; a implementação é comparada com ela em **339 instantes**.

```
python _main\youtube-window-oracle.py
  PASS 1.1 19 linhas de legenda (sem os separadores)
  PASS 1.2 o parser do repo ve as mesmas 19
  PASS 1.3 janela declarada rcRows=2 ccCols=40
  PASS 2.1 339 instantes concordam
  PASS 3.1 ha instantes com DUAS linhas  -- 320 de 339 amostras (94%)
  PASS 3.2 ha instantes com UMA  -- 19 de 339
  PASS 4.3 a janela muda 19 vezes em 339 amostras (nao uma por poll)
BATTERY-VERDICT youtube-window-oracle PASS  checks=12 fail=0        rc=0
```

Braço negativo executado (a implementação forçada a UMA linha, a expectativa no `rcRows` real):

```
python _main\youtube-window-oracle.py --neg-arm
  FAIL 2.1 339 instantes concordam  -- 320 divergem; primeiro em t=1.90
           want=['Have you ever had to kill a man?', '>> No.'] got=['>> No.']
BATTERY-VERDICT youtube-window-oracle FAIL  checks=12 fail=1        rc=1  (por desenho)
```

O mutante que o dono **fotografou** é exactamente o `got=['>> No.']` acima.

## 5. A ligação que falta (e por que não foi feita)

O caminho vivo chama `cue_at` em **`app/webview/sotto_webview.py`** (`:2246` e `:2305`). Esse ficheiro
está alterado por outra lane (`git status`: ` M`), tal como `app/webview/youtube_captions.py`
(30 linhas a mais: `TARGET_OVERRIDE`/`set_target_language`, um selector de língua — nada a ver com
`cue_at`).

O patch, para quem tem esses ficheiros abertos:

```python
import youtube_window

lines = youtube_window.live_lines(track.get('cues') or (), t)
key = youtube_window.window_key(lines)
if key != _last_window_key:                 # so emite quando a JANELA muda
    _last_window_key = key
    show_caption_lines(lines)               # duas linhas, a de cima primeiro
    history_append(youtube_window.history_line(lines))
```

Sem a chave, o histórico volta a receber a mesma janela a cada poll (é o defeito das seis cópias).

## 6. A auto-dublagem

Medido no player: `audioTracks` = **20**, `defaultAudioTrackIndex = 10` → `en-US.4`, e as dublagens
(`ja.10`, `pt-BR.10`, `fr-FR.10`, …) ao lado da original. O índice por omissão era a trilha **original
inglesa**, e o `getAudioTrack()` reportou `isAutoDubbed: false`; a dublagem não estava activa **nesta**
página. O que fica por fazer é do lado do Sotto: ao reutilizar YouTube, **fixar a faixa de áudio
original** e nunca aceitar uma `audioTrackId` de dublagem. `setAudioTrack({id:'ja.10'})` devolveu
`true`, portanto a API aceita a escolha — o Sotto é que ainda não a faz.

## 7. O que este recibo NÃO prova

- **O caminho pintado** (`external_subs.caption_lines`, UIA a ler a legenda que o browser desenhou)
  não foi exercitado: precisa da app, e lançar a app é do LEAD. A janela de duas linhas tem de ser
  aplicada também lá, senão o ecrã continua a uma linha mesmo com a fonte de dados certa.
- **A comparação com os modelos locais** (a segunda metade do pedido) não foi feita: transcrever este
  vídeo com o Nemotron exige lançar o worker. É do LEAD.
- A largura `ccCols: 40` não foi usada para julgar o *wrap* dentro de cada linha: só o
  `caption_wrap.py` decide isso, e a linha do YouTube aqui já vem inteira (sem `\n` no texto).

## 8. "Fora de sync": o mecanismo, medido na app do dono (2026-10-22 06:54)

Relay do contrato (`127.0.0.1:9224`, `ompRelayVersion=18.6.1`), a aba do vídeo escolhida **por url**.
Isto não é dedução: é a linha do log da app dele, no mesmo intervalo em que o browser foi amostrado.

**O browser não pintou UMA linha de legenda em 30,5 s de reprodução.** Amostra a cada 100 ms,
`video.currentTime` de 0,000 a 30,509, **400 amostras, `caption = null` em todas** (o CC desta aba está
desligado: `.ytp-subtitles-button[aria-pressed=false]`).

**E a app, no mesmo intervalo, diz que leu 8 palavras pintadas:**

```
06:54:16.019 YOUTUBE_TRACK_READY video_id=WdaHAGRBB6s state=has-track cues=19 lang=en-orig source=auto
06:54:16.019 YOUTUBE_TRACK_PAINT video_id=WdaHAGRBB6s source=painted cue=0 match=1 painted_words=8
06:54:18.515 EXTERNAL_CAPTIONS_RELEASED reason=youtube-no-track
06:54:18.515 BRIDGE_START reason=external-end ... worker=H:\sotto\worker\sotto_worker.py
06:54:47.437 YOUTUBE_TRACK_READY ... (o ciclo outra vez)
```

e, 6 s antes, a linha que explica tudo:

```
06:52:49.198 YOUTUBE_TRACK_STATE reason=clock-unreadable urgent=false
```

**A cadeia medida:**

1. **O relógio do player não é legível** (`clock-unreadable`). Sem `t`, a tabela de cues — que está
   1:1 (secção 2) — não pode ser usada para escolher a linha. A tabela certa fica inútil.
2. **`painted_words=8` de uma janela vazia.** O `caption = null` nas 400 amostras prova que o browser
   não desenhou nada; a app contou 8 "palavras pintadas" do mesmo sítio. É texto fantasma: o nó da
   legenda que já não está a ser desenhado continua legível por UIA.
3. Sem relógio e com texto fantasma, a legenda é mostrada **quando** o UIA a consegue ler, não **quando**
   o vídeo a diz. Isso é, por definição, fora de sync — e explica a mesma linha seis vezes no histórico
   (cada leitura do fantasma é um evento novo).
4. Ao fim de 6 s sem linha nova a app **blanca a caixa**, manda o YouTube embora
   (`EXTERNAL_CAPTIONS_RELEASED reason=youtube-no-track`) e **arranca o worker local**
   (`BRIDGE_START reason=external-end`) — que passa a transcrever o áudio que estiver a tocar, que nao
   tem relacao com os cues do YouTube. Duas fontes a alternar é o que ele vê como "patético e bugado".

**O que isto obriga a mudar** (os três, em ficheiros que outra lane tem abertos):

- ler o relógio — sem ele nada disto pode estar em sync;
- não aceitar `painted_words` de uma janela sem nó desenhado (o contador tem de vir do mesmo nó que a
  legenda que se mostra, ou não conta);
- a janela de duas linhas (`youtube_window.live_lines`) em vez do `cue_at` de um cue.

## 9. Auto-dublagem, o que foi medido e o que falta

No player response desta página existem **20 faixas de áudio** (`uk.10`, `fr-FR.10`, `pt-BR.10`, …,
`en-US.4`) com `defaultAudioTrackIndex = 10` → a original inglesa. `mp.getAudioTrack()` devolveu
`id = "und"` — o player não reporta uma escolha explícita, está na omissão. `mp.setAudioTrack({id})`
devolveu `true` quando chamado, portanto a API aceita a selecção.

O que falta é do lado do Sotto: **fixar a faixa original** ao reutilizar YouTube e **recusar** qualquer
`audioTrackId` de dublagem — senão o worker local transcreve a dublagem (o `reason=external-end` acima
mostra que ele fica a transcrever o áudio do sistema).

## 10. O ARRANJO (2026-10-22, feito, com portoes)

**Três defeitos, três correcções, todas provadas por portão que corre sem a app.**

1. **A janela era de UMA linha.** `sotto_webview._external_lines` devolvia
   `[('external:youtube:track', [text])]` — um cue. Passou a devolver
   `self._yt_lines(track, t)`, que usa `youtube_window.live_lines(cues, t, 2)` e só cai
   para `cue_at` quando a janela vem vazia. O mesmo no ramo do `painted`: a janela é
   calculada a partir do `start` do cue que o player está a pintar, para que a linha de
   cima (a anterior) apareça como aparece no YouTube.
2. **Texto fantasma.** `youtube_captions.painted_words` aceitava qualquer elemento cuja
   classe contivesse `caption-window`, mesmo que já não estivesse desenhado. Medido:
   400 amostras do browser com a legenda VAZIA e a app a contar **8 palavras** — a linha
   que tinha deixado de ser desenhada. Novo filtro `_rendered(el)`: `CurrentIsOffscreen`
   falso **e** rectângulo com área > 0; um elemento cujo peer de automação levantou conta
   como não desenhado (não propaga a excepção).
3. **A chave do histórico.** `youtube_window.window_key` só muda quando a janela muda
   (19 vezes em 339 amostras). É o que impede a mesma frase de entrar seis vezes.

### Prova (comandos executados, saída colada)

```
python _main\youtube-sync-oracle.py
  PASS 1.1 339 instantes concordam
  PASS 1.2 ha instantes com DUAS linhas  -- 320 de 339 (94%)
  PASS 2.1 um elemento DESENHADO passa
  PASS 2.2 OFFSCREEN e recusado
  PASS 2.3 rectangulo VAZIO e recusado
  PASS 2.4 sem peer de automacao e recusado (nao rebenta)
  PASS 3.3 nenhum sitio devolve um cue so  -- 0 sitio(s) ainda com [text]
  PASS 3.4 os dois sitios usam _yt_lines  -- count=2
  PASS 4.1 a janela muda 19 vezes, nao uma por poll
BATTERY-VERDICT youtube-sync-oracle PASS  checks=11 fail=0     rc=0
```

Braço negativo (janela a 1 linha + filtro sempre-verdadeiro): `FAIL 1.2`, `FAIL 2.2`,
`FAIL 2.3`, `FAIL 2.4` — `rc=1` por desenho.

Regressão: `python _main\youtube-captions-oracle.py` → `rc=0` (34,5 s), sem RED — o
contrato do módulo (política de línguas, cache, 429) ficou intacto.

### Auto-dublagem — medido, e o que se pode dizer

`audioTracks` = 20 (`ml.10`, `es-US.10`, `pt-BR.10`, … , `en-US.4`, …),
`defaultAudioTrackIndex = 18` → **`en-US.4`, a original inglesa**. `getAudioTrack()`
devolve `{id: "und"}` (a omissão), e `setAudioTrack({id:"en-US.4"})` devolveu **`false`**
— o player recusa a troca por API neste estado. Conclusão medida: **nesta reprodução não
está a tocar dublagem**; o que toca é a original. O Sotto não tem como escolher a faixa
de áudio do browser (não tem CDP, e o porto de depuração é proibido pelo contrato), por
isso a dublagem só pode ser desligada no próprio YouTube.

## 11. O QUE NÃO ESTÁ VERIFICADO (dito, não escondido)

- **Não vi a legenda na tela.** As três correcções estão provadas por portão sobre o
  payload real e sobre o código, mas o caminho vivo (UIA a ler a janela do player) só se
  exerce com a app a correr — e lançar a app é do LEAD. O que ficou provado é que a app
  passa a devolver DUAS linhas e a não ler um elemento que não está desenhado.
- **A largura de 40 colunas** (`ccCols`) não é usada para quebrar dentro da linha: o
  `caption_wrap.py` continua a decidir isso, e o texto do YouTube aqui já vem inteiro.
- **A comparação com os modelos locais** (segunda metade do pedido original) não foi
  feita: exige transcrever o vídeo com o worker.
- **O `cue_at`** continua a existir e a ser usado por oráculos antigos; a app já não o
  usa como primeira escolha.
