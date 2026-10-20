# Recibo — a faixa 1:1: a do YouTube, tal e qual (2026-10-20)

**Dono, verbatim (2026-10-20):** *"eu quero a legenda 1:1 do video do youtube.
eu mesmo vou comparar a nossa legenda em tempo real com a do youtube. lembra
que é pra tu simplesmente pegar a do youtube mesmo e usar pelo app. o app só
nao faz isso se nao tem a legenda disponivel."*

Isto é um requisito de **exactidão**: a linha que o Sotto mostra tem de ser a
MESMA linha que o player do YouTube pinta. A medicao de base estava feita; o
que faltava era **a regra que escolhe a faixa**, e ela estava errada por
acaso, nao por razao.

---

## 1. O QUE MUDEI

| ficheiro | o que |
|---|---|
| `app/webview/youtube_captions.py` | a regra nova: a faixa do PLAYER primeiro; o sinal lido do proprio player; a honestidade no log |
| `_main/yt-player-track-oracle.py` | o portao NOVO (10 bracos, 4 mutantes) |
| `_main/yt-player-track-probe.py` | o instrumento REUTILIZAVEL (lado a lado, com numeros) |
| `_main/_audit-verify-all.cmd` | o portao registado como PASSO |

**`app/webview/sotto_webview.py` NAO foi tocado** (a lane do stall tinha-o em
edicao; e nao era preciso: o modulo le o signal do player sozinho).

---

## 2. O SINAL DO PLAYER — o que foi MEDIDO

### 2.1 A pagina real (headless Edge + CDP, video MUTED, `cUeZMUGCxrw`)

O player, com a faixa carregada, pinta a legenda **dentro** de um elemento
que carrega a LINGUA da faixa:

```html
<div class="caption-window ytp-caption-window-bottom ytp-caption-window-rollup"
     id="caption-window-1" dir="ltr" tabindex="0" lang="pt" draggable="true" ...>
  <span class="captions-text"><span class="caption-visual-line">
    <span class="ytp-caption-segment">&gt;&gt; Configurar leva 1 minuto. Conecte o</span>
```

* a `lang="pt"` do elemento da legenda, e
* a linha pintada era **portugues** — as duas coisas concordam.

O `ytInitialPlayerResponse.captions.playerCaptionsTracklistRenderer` da
pagina real tem **21 faixas, todas `kind=asr`**, com `vssId` `a.de`, `a.ar`,
... `a.en`, `a.pt`, ... e **nenhum parametro `tlang` em nenhum baseUrl**.

### 2.2 A correspondencia entre a faixa do PLAYER e a chave do yt-dlp

Isto e o ponto que **corrige** a premissa do brief. Lidos lado a lado, no
mesmo instante, o pedido que o **PLAYER** faz e o pedido que o **yt-dlp**
faz para cada chave do MESMO video:

| quem | pedido | resultado medido |
|---|---|---|
| **o PLAYER** (`a.pt`) | `?v=..&caps=asr&kind=asr&lang=pt` | — |
| yt-dlp **`pt-orig`** | `?v=..&caps=asr&kind=asr&lang=pt` | **HTTP 200, 679 cues** ("Pessoal , temos um novo gerador de") |
| yt-dlp **`pt`** | `?v=..&caps=asr&kind=asr&lang=ar&tlang=pt` | **HTTP 429** (payload recusado) |

**Logo: a faixa que o player pinta e a chave `-orig`, NAO a chave `pt`.** A
correspondencia `a.pt` -> `pt` que o brief propunha esta errada: a chave `pt`
e um pedido **diferente** (a faixa original traduzida ao vivo), que o proprio
yt-dlp chama de *"damaged subtitles"* (`yt-dlp/extractor/youtube/_video.py`,
`Setting tlang=lang returns damaged subtitles`) e que o YouTube recusa com
HTTP 429 em todos os formatos.

A mesma leitura para o ingles: `en-orig` = `lang=en` (sem `tlang`), 200, 622
cues ("Folks, we have a new open-source image"); `en` = `lang=ar&tlang=en`,
429.

### 2.3 O que o browser pt-BR mostra por omissao

Medido, com o video a tocar (mudo) e o navegador em `pt-BR`: o player
escolheu **`lang="pt"`** e pintou **portugues** — ou seja, a traducao
automatica para a lingua do navegador, que e a faixa `pt-orig`. O video
original e em ingles (`en-US`).

---

## 3. A REGRA NOVA

1. **O sinal do player manda.** `youtube_captions.player_track_signal()`
   le a janela de legenda do player e devolve a lingua que ele esta a
   pintar. `tracks_from_info(info, prefs, player_lang=...)` poe essa faixa
   **primeira** na lista.
2. **A chave e a `-orig`.** Para a lingua `X` do player, a chave servida e
   `X-orig` (o pedido sem `tlang`), e nao `X` (o pedido com `tlang`, o
   recusado).
3. **Dentro de uma lingua, a ordem e a do player**: a faixa manual quando o
   video a tem, depois a automatica `-orig`, e so depois a traduzida.
4. **O fallback fica.** Sem sinal do player, manda a preferencia de lingua
   (`pt`, `en`) — e o resultado passa a dizer `player_known=0` com o motivo.
5. **A honestidade e obrigatoria.** O modulo escreve no log da app:
   `sotto: YOUTUBE_PLAYER_TRACK known=<0|1> lang=<X|-> source=<...>
   served=<chave> served_source=<...> why=<motivo>`
   — uma linha por MUDANCA de estado. Sem sinal, a linha diz "nao sei" e
   porque; nunca finge que a primeira faixa que respondeu e a certa.
6. **O cache invalida.** A entrada de cache passa a guardar `player_lang`.
   Quando o dono muda de faixa no player, o cache da faixa antiga **nao e
   servido** (a linha seria a errada) e as candidatas sao pedidas outra vez,
   com a lingua do player primeiro. `CACHE_SCHEMA` foi de 2 para 3 por isso.

---

## 4. OS NUMEROS

### 4.1 O portao novo

`_main/yt-player-track-oracle.py` — **arms 10/10, mutantes 4/4 RED**,
`VERDICT: PASS`.

Os 4 mutantes sao EXECUTADOS (copias quebradas do modulo, a mesma bateria):

| mutante | apanhado por |
|---|---|
| `the-player-signal-is-ignored` | a08 (o cache da faixa antiga e servido) |
| `the-players-track-is-mapped-to-the-tlang-key` — **o mutante do bug real** | a01, a02, a06 |
| `the-switch-is-not-logged` | a05 (o log) |
| `a-refused-payload-is-a-verdict` | a07 (o 429 deixa de ser fallback) |

### 4.2 O 1:1 medido, com numeros

`_main/yt-player-track-probe.py --video cUeZMUGCxrw --player-lang <X>`:

| o player esta em | a app serve | cues comparados | identicos pos-a-pos | veredicto |
|---|---|---|---|---|
| `pt` (o que o browser pt-BR pintou) | `pt-orig` (679 cues) | 679 | **679** | **1:1** |
| `en` (o dono muda para ingles) | `en-orig` (622 cues) | 622 | **622** | **1:1** |

O pedido que a app faz e o pedido do player, palavra por palavra:
`{v: cUeZMUGCxrw, caps: asr, kind: asr, lang: pt}` (sem `tlang`).

### 4.3 Os portoes que ja existiam (nao podem partir)

| portao | veredicto |
|---|---|
| `_main/youtube-captions-oracle.py` | **PASS arms 47/47 mutantes 11/11** |
| `_main/youtube-track-wiring-oracle.py` | **PASS arms 12/12 mutantes 5/5** |
| `_main/yt-player-track-oracle.py` (novo) | **PASS arms 10/10 mutantes 4/4** |

---

## 5. O QUE **NAO** FOI MEDIDO (e porque)

1. **A leitura do `lang` pela UIA no browser do dono.** O sinal existe no
   DOM (medido acima), mas a **janela do dono nao estava aberta** com o
   video quando esta lane correu (`find_player_window()` devolveu 0; so havia
   um `about:blank` e uma aba do ChatGPT). Portanto **nao foi medido** se o
   Chromium expoe esse `lang` a UI Automation — o que o modulo le e a
   propriedade de linguagem da UIA (30007) do elemento da janela de legenda,
   convertida de Windows-LCID para o codigo do YouTube. O portao mede o
   que happens **quando a propriedade responde** (a09, com uma arvore falsa:
   1046 -> "pt").
   * Como o Chrome desta box **nao expoe a pagina** na arvore da UIA quando
     a aba nao e a do player (medido: 45 e 112 elementos, todos da moldura do
     browser), o sinal pode vir `known=0` — e entao o log DIZ isso e a
     preferencia manda. **A app nunca finge.**
2. **A leitura ao vivo da faixa do player na janela real** — pelo mesmo
   motivo (janela fechada). O `--player-lang` do probe mede o resto da
   cadeia (escolha + payload + cues) sem depender da janela.
3. **O menu de legendas** do player (que tambem nomeia a faixa) nao foi
   usado: em headless abre **vazio** (0 itens, medido) e o `lang` da janela
   de legenda foi o sinal que respondeu.

---

## 6. LIMITACOES

1. **O `lang` da janela de legenda so existe com a faixa carregada.** Um
   player sem legenda nao diz nada — e o modulo trata "nao disse" como
   "nao sei", nao como "nao ha legenda" (a10).
2. **O sinal e por regiao, nao por pais.** `lang="pt-BR"` e `lang="pt-PT"`
   viram "pt" (o LCID 1046 e o 2070). O yt-dlp tambem expoe a chave por
   lingua base, portanto a linha servida e a mesma.
3. **O `fetch_track` le o browser a cada 30 s** (a cadencia do leitor da
   shell). Se o video aberto nao for o pedido, o sinal e descartado
   (`other-video`) — e o modulo nao diz nada sobre ele.
4. **A ligacao `external_subs`**: o modulo importa o irmao por caminho
   (`_external_subs()`), porque os portoes carregam o ficheiro por caminho e
   o directorio nao esta no `sys.path`. Sem isso, uma falha de importacao
   pareceria "o player nao disse nada".
5. **`SOTTO_YT_PLAYER_TRACK=0`** desliga a leitura ao vivo (a escotilha de
   um portao que nao pode tocar no browser do dono).
6. **A hermeticidade**: o `fetch_track` pergunta ao browser que esta aberto
   para saber a faixa; o portao antigo `youtube-captions-oracle.py` usa o
   video de fixture `dQw4w9WgXcQ`, e so um player aberto nesse video exacto
   com outra lingua mudaria a ordem das fixtures. Risco medido: minimo,
   declarado.

---

## 7. O QUE MUDOU PARA O DONO (em uma frase)

Antes, a app servia a primeira faixa que respondesse — e por acaso era a
certa, porque a outra estava a ser recusada; agora ela serve **a faixa que o
player esta a pintar**, e quando nao sabe, o log **diz que nao sabe**.
