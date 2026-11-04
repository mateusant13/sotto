# YouTube source identity — quem diz qual vídeo o Sotto lê

Medido em 2026-11-03, no browser do dono, com o Sotto a viver. Este documento
existe porque três afirmações do código sobre "qual é o vídeo" estavam erradas ao
mesmo tempo, e cada uma sozinha bastava para deixar o ecrã vazio.

## O defeito, medido

```
18:24:41 YOUTUBE_TRACK_READY video_id=m_bJQ4G1Ht8 state=has-track cues=10 cached=True
18:26:16 YOUTUBE_TRACK_PAINT video_id=m_bJQ4G1Ht8 source=other-video match=0 painted_words=0
```

164 linhas, uma rodada a cada ~32 s, enquanto o Chrome tinha **uma** aba de vídeo
aberta — outra (`2K_Rm8cho1I`) — e o `m_bJQ4G1Ht8` já não existia em aba nenhuma.
`source=other-video` é o pipeline a recusar-se a si mesmo.

## As três causas

1. **O id declarado nunca era reperguntado.** `_yt_identify` guardava `yt_video_id`
   e devolvia pelo caminho rápido para sempre. Uma vez guardado, nenhum tick
   voltava a perguntar que aba estava aberta.
2. **`pick_target` FILTRA as abas pelo id declarado.** Com a aba fechada devolvia
   `None, 'video-not-open'`; sem alvo não há foto; sem foto não há `videoId` para
   corrigir o id. O laço fechava-se sobre si mesmo.
3. **O nome da fonte tinha duas formas.** O resolvedor publica a URL
   (`https://www.youtube.com/watch?v=…`, de `_yt_source_by_title`) e o ramo do
   YouTube compara com o literal `'external:youtube'`. Com a porta CDP ligada a
   URL era o valor único, portanto:

   ```
   YOUTUBE_TICK_MS src='https://www.youtube.com/watch?v=Rgx8dpiPwpA'
                   vid='Rgx8dpiPwpA' why='cdp-fresh-skip'   (4 Hz)
   ```

   O ramo do YouTube não corria; a varredura genérica também não (a foto estava
   fresca); três linhas pintadas no player e **nada** no Sotto.

## A regra que ficou

- **A aba aberta manda.** `_choose()` (em `youtube_cdp_source`) tenta o id
  declarado; quando ele não está aberto, escolhe pelo título da janela ou pela
  única aba e o motivo passa a `stale-declared:…`. O shell re-declara e diz o
  nome: `YOUTUBE_TARGET_REBOUND was=… now=… why=aba`.
- **A lista de abas é HTTP, não websocket.** `/json/list` responde em
  milissegundos; a foto da CDP depende de a página responder ao
  `Runtime.evaluate`, e a de uma aba em segundo plano devolve
  `slow (WebSocketTimeoutException)` e nunca publica. A autoridade de *qual* aba
  é, portanto, `target_video_id()`.
- **Um nome, duas formas.** `youtube.com/watch` na fonte passa a
  `'external:youtube'` antes do `if`, e o resolvedor deixa de poder desligar o
  ramo que o serve.

## O arranque pede o attach, e o tick nao mente (2026-11-04)

O pedido de attach morava no **primeiro tick** do laço da legenda, e o laço só
existe depois de metade do arranque. Medido no log do dono, app subida às
10:06:36: `CAPTION_PIPELINE_START reason=pre-webview` às 10:06:36.483 e
`YOUTUBE_CDP_SOURCE state=attached` só às 10:06:40.798. Pior: a linha que devia
pedir a ligação dentro do pipeline chamava `self._yt_cdp_ensure()`, método que
existe **no watcher** e não na shell — o `AttributeError` caía no `except` e
saía como `YOUTUBE_CDP_PREOPEN_FAILED`, portanto o arranque nunca pedia nada.

E o diagnóstico do laço mentia em duas frentes (61 linhas seguidas,
10:56:04 → 10:57:16, com o Chrome aberto num vídeo):

```
YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8'
  cdp_age_ms=2413609 rows=0 why='cdp-fresh-skip'
```

`src='?'` porque `_yt_diag` só era escrito em dois ramos; `cdp_age_ms=2413609`
porque a idade ficou **congelada** no instante em que aquele ramo correu (40
minutos antes), não no instante em que a linha saiu.

**A regra que ficou:**

- `SottoShell._yt_cdp_boot_attach()` — `start_caption_pipeline('pre-webview')`
  chama-a antes do watcher e antes do worker. `youtube_cdp_source.boot_attach`
  faz a MESMA pergunta do laço (`list_targets` + `pick_target`) com **3
  tentativas de 0,4 s** (pior caso ~1,45 s) e escreve uma linha por tentativa:
  `YOUTUBE_CDP_BOOT_ATTACH attempt=1/3 ok=false reason=port-closed`. Quem não
  ligou continua a tentar na thread, e aí cada falha é
  `YOUTUBE_CDP_ATTACH_FAILED attempt=N ok=false reason=… ms=…`
  (`_ATTACH_LOG_N=20` inteiras, depois uma em cada 50: o Chrome pode ficar
  fechado a tarde inteira).
- A fonte nasce **na shell** e o watcher **adota** a dela — duas threads na mesma
  aba era o que a ordem antiga escondia.
- `_yt_diag_now()` compõe `YOUTUBE_TICK_MS`: `src`, `vid`, `cdp_age_ms`, `rows`
  e `why` **nunca** saem `?`. `src`/`vid`/`why` são o último ramo conhecido
  (`unattached`/`none`/`no-frame` quando não há ramo nenhum); a **idade** e as
  **linhas** são lidas na hora, porque são elas que dizem se há foto agora.

## Instrumentos

| instrumento | o que prova |
|---|---|
| `_main/youtube-cdp-boot-oracle.py` | 8 arms; A1 executa `start_caption_pipeline` REAL sem painel; A2 `boot_attach` contra porta fechada (3 motivos) e contra fotografia; A3 o laço REAL adota a aba que navegou (`adopted:OLD->NEW`) e recusa quando o declarado ainda está aberto; A4 `_yt_diag_now` sem `?` com idade viva. `--neg-arm` derruba as 4 (rc=1) |
| `_main/youtube-cdp-source-oracle.py` | 11 arms; `--neg-arm` derruba 6 |
| `_main/yt-target-stale-oracle.py` | 7 arms; `--neg-arm` derruba 4 (STALE-TARGET, STALE-ID, CONNECT, SOURCE-NAME) com rc=1 |
| `_main/yt-loop-uia-oracle.py` | com CDP aberta o tick não paga UIA; `--neg-arm` derruba NO-SNAP e BOOTSTRAP |
| `YOUTUBE_TICK_MS … src= vid= cdp_age_ms= rows= why=` | a decisão do laço por extenso, de 5 em 5 s, **sem `?`** |
| `YOUTUBE_CDP_BOOT_ATTACH` / `YOUTUBE_CDP_ATTACH_FAILED` / `YOUTUBE_CDP_ATTACH_OK` | o pedido de attach no arranque e o motivo de cada tentativa |
| `YOUTUBE_CDP_SOURCE state=…` | `attached` / `slow (…)` / `reconnect (…)` / `stale-declared:…` / `adopted:…->…` |

## Medido depois

O `player` do dono e o Sotto, amostrados em simultâneo (seis amostras, vídeo a
tocar, 1:1 palavra por palavra):

```
player: design and the proposal and later today / I have a design review with …
sotto : YT_FRAME src=external:youtube:track rows=2 lines=['design and the proposal and later toda…
```

## Nota sobre fidelidade

`'Actually I I I think I understand our'` **não** é duplicação do Sotto: é o texto
que o próprio payload do YouTube serve (cue 357.6–363.52), e o player do dono
desenha o mesmo. Confirmado com `youtube_captions.fetch_track` + leitura do DOM
do player na mesma posição.
