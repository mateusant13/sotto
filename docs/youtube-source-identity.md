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

## Instrumentos

| instrumento | o que prova |
|---|---|
| `_main/yt-target-stale-oracle.py` | 7 arms; `--neg-arm` derruba 4 (STALE-TARGET, STALE-ID, CONNECT, SOURCE-NAME) com rc=1 |
| `_main/yt-loop-uia-oracle.py` | com CDP aberta o tick não paga UIA; `--neg-arm` derruba NO-SNAP e BOOTSTRAP |
| `YOUTUBE_TICK_MS … src= vid= cdp_age_ms= rows= why=` | a decisão do laço por extenso, de 5 em 5 s |
| `YOUTUBE_CDP_SOURCE state=…` | `attached` / `slow (…)` / `reconnect (…)` / `stale-declared:…` |

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
