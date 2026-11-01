# A legenda do YouTube, medida — a especificação que o Sotto imita

O dono, 2026-11-01, verbatim:

> *"tu deve entender literalmente como funciona as legendas do youtube e o display e as
> animeacoes e as quebras de linha 1:1 e imitar no sotto ... mesmo qunado é só transcricao
> em temporeal, deve imitar o comportamento da legenda do youtube."*

Este documento é a resposta numérica. Cada linha da tabela diz **quanto**, **onde foi medido**
(ficheiro e chave de saída) e **se é medição ou inferência**. Um número sem instrumento não
entra aqui; o que não foi medido está marcado `[INFERENCE]`, com o valor que o Sotto usa e
porquê.

## O instrumento

```
python _main\sim\measure-youtube-captions.py            # a tabela
python _main\sim\measure-youtube-captions.py --json m.json   # as chaves citadas abaixo
```

`_main/sim/measure-youtube-captions.py` é o ÚNICO produtor dos números desta página. Sai com
`rc=0` quando mediu e `rc=2` quando a fixture falta — ausência de medição não é medição.

As fontes que ele lê, e o que cada uma pode dizer:

| Fonte | O que ela é | O que só ela pode dizer |
|---|---|---|
| `_main/fixtures/yt-WdaHAGRBB6s.en-orig.json3` | o payload do próprio player (`wireMagic: pb3`, `events`, `wpWinPositions`) | a janela declarada, a vida de cada linha, o instante de cada palavra |
| `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json` | 16 quadros do player lidos por CDP (`_main/yt-1to1-live-compare.py`), vídeo pausado no instante pedido | o que o player **desenha**: quantas linhas, quais estão dentro da caixa, a opacidade |
| `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json` | 16 quadros que comparam a quebra do player com a do overlay | se a quebra é a do payload ou uma re-quebra nossa |

## A tabela

| # | Comportamento | Medido | Instrumento (ficheiro → chave) | Estado |
|---|---|---|---|---|
| 1 | Linhas da janela | **2** (`rcRows`) | payload → `window.rcRows` | medido |
| 2 | Colunas declaradas | **40** (`ccCols`) | payload → `window.ccCols` | medido |
| 3 | Caracteres por linha | mín 4, mediana 30, **máx 42** (19 linhas) | payload → `lines.chars_per_row` | medido |
| 4 | Linhas acima de `ccCols` | 1 de 19 (o player não respeita `ccCols` à letra) | payload → `lines.rows_over_ccCols` | medido |
| 5 | Palavras partidas dentro de uma linha | **0 de 19** | payload → `lines.split_words_inside_a_row` | medido |
| 6 | Palavras por linha | mín 1, mediana **5**, máx 8 | payload → `word_clock.words_per_row` | medido |
| 7 | Relógio de revelação | `tStartMs` da linha **+** `tOffsetMs` do segmento | payload → `word_clock.origin` | medido |
| 8 | Palavras com `tOffsetMs` declarado | **69 de 88** | payload → `sources.words_with_offset_declared` | medido |
| 9 | Intervalo entre palavras | mín **0,04 s**, mediana **0,24 s**, máx **1,08 s** (69 intervalos) | payload → `word_clock.gaps_s` | medido |
| 10 | Intervalos ≤ 120 ms / ≤ 40 ms | **18 / 1** (a revelação é contínua, não em saltos) | payload → `word_clock.gaps_at_or_below_120ms` | medido |
| 11 | Linhas desenhadas ao longo do vídeo | 1 linha: **1,88 s**; 2 linhas: **24,3 s**; 3 linhas: **7,66 s** | payload + modelo → `rollup.drawn_rows_over_time` | medido |
| 12 | Linhas desenhadas sem a linha a sair | 1: 1,88 s; 2: 31,96 s (nunca 3) | payload → `rollup.drawn_rows_over_time_without_exit` | medido |
| 13 | Duração do *exit* (rolamento para fora) | **0,424 s .. 0,552 s**, modelo usa **0,45 s**, reproduz **16/16** quadros | UIA → `rollup.exit_s_bracket_s` | medido |
| 14 | Linha nova antes do fim da revelação anterior | **0 de 18** casos | payload → `rollup.new_row_before_previous_reveal_done` | medido |
| 15 | Delta linha nova → última palavra da anterior | mín **0,08 s**, mediana **0,72 s**, máx **1,36 s** | payload → `rollup.new_row_delta_from_previous_last_word_s` | medido |
| 16 | Hold de uma linha pronta | mín **0,88 s**, mediana **2,48 s**, máx **4,68 s** | payload → `hold_s` | medido |
| 17 | Linhas por quadro do player | 1 linha: 3 quadros, 2: 9, 3: 4 (máx **3**) | UIA → `uia.shape.rows_per_sample` | medido |
| 18 | O modelo de *exit* reproduz a contagem de linhas | **16/16** | UIA → `uia.shape.model_reproduces_row_count` | medido |
| 19 | Texto pintado == relógio de palavra do payload | **15/16** (o 16.º está um segmento atrás, 11 ms depois do instante dele) | UIA → `uia.agree` / `uia.disagree` | medido |
| 20 | Linha pintada **antes** do seu `start` (cue adiantada) | **0 de 16** quadros | UIA → `early.rows_drawn_before_start` | medido |
| 21 | Linhas fora da caixa (a rolar para fora) | **1 de 16** quadros | UIA → `uia.shape.outside_box` | medido |
| 22 | Opacidade < 1 nos quadros do player | **0 de 16** (o fade dura menos que o intervalo entre quadros, ~0,65 s) | UIA → `uia.shape.opacity_below_1` | medido |
| 23 | Duração e curva do fade de ENTRADA | 0,12 s, `1-(1-t)²` (ease-out quadrático) | Sotto: `word_fade.DURATION_S`; o painel usa **140 ms** `ease-out` sobre `opacity` (`app/panel/panel.css`, `sotto-word-in`) | **`[INFERENCE]`** |
| 24 | Duração e curva do fade de SAÍDA | 0,45 s, mesma curva | `word_fade.alpha_out` (`EXIT_S`) | **`[INFERENCE]`** (a *janela* do exit é medida: linha 13) |
| 25 | Mesma quebra de linha que o overlay antigo | 4 de 16 (texto junto igual em 15/16) | break-position → `same_break`, `same_joined_text` | medido |
| 26 | O painel escalona a revelação | **não** — `animation-delay: calc(var(--type-step) * 0ms)`; só o fade de 140 ms da palavra nova | `app/panel/panel.css` (`.caption__word[data-typing]`) | medido (CSS) |

Porque a linha 23/24 são inferência: a captura lê a opacidade a ~0,65 s por quadro
(`fade.smallest_resolvable_s`) e o fade dura menos que isso; a animação CSS do player só se lê
numa sessão viva com `getComputedStyle`, que o instrumento não abre
(`fade.why`). O `out_s` de 0,45 s **não** é arbitrário: é o mesmo número que reproduz os 16
quadros do *exit* (linha 13), e é essa coincidência que o torna defensável.

## Os números viram regras — e as regras têm nome

Uma tabela que ninguém pode violar não serve de nada. Cada número acima está **no código**, e
nomear a função é o que permite a um oráculo verificar o número sem repetir o cálculo.

| Regra | Onde vive | Números |
|---|---|---|
| A janela é 2 linhas + a que sai | `youtube_reveal.CAPACITY` / `ROLLUP_ROWS`; `_drawn` corta em `capacity + rollup` | 1, 11, 12, 17 |
| Uma palavra por relógio, nunca um lote | `word_clock_count`, `first_words`, `_reveal_text` | 7, 8, 9, 10 |
| O *exit* dura 0,45 s e o alfa é POR LINHA | `word_fade.alpha_out`, `youtube_reveal.frame`, `caption_overlay._premultiplied_bitmap(alphas=…)` | 13, 21, 24 |
| O ponto vivo não fica ao lado da linha que sai | `_premultiplied_bitmap` (`led_row`: a primeira linha de alfa 255) | 11, 13, 17 |
| Uma linha não aparece antes do seu `start` | `_drawn` (`start <= t`) | 20 |
| A linha que sai fica `capacity` posições atrás | `frame` (`displaced_at`), `EXIT_S` | 11, 12, 13 |
| Nunca se parte uma palavra; o tecto é 42 caracteres | `caption_wrap.CHAR_CEILING` (= `youtube_reveal.MAX_CHARS`), `caption_wrap.wrap` | 3, 5 |
| O texto do player viaja com `\n` e NÃO volta a ser quebrado | `youtube_reveal.rows_text` → `caption_overlay._layout` (ramo do `'\n'`) | 25 |
| O ASR entra ao compasso medido, com atraso limitado | `LiveRows.push` (`WORD_GAP_S` 0,24 s, `MAX_LAG_S` 0,36 s) | 9, 10 |

## Uma cue que chega adiantada

Duas coisas diferentes, e as duas medidas:

1. **O payload nunca declara uma linha que começa antes de a anterior acabar de ser revelada**
   (linha 14: 0 de 18) e o **player nunca pinta uma linha antes do `start` dela** (linha 20:
   0 de 16 quadros). Logo a regra do Sotto — `_drawn` só desenha `start <= t` — não é uma
   escolha nossa: é o que o player faz. Uma cue adiantada fica **parada** até ao instante dela;
   não se pinta o futuro nem se adianta a linha.
2. **O que o Sotto faz quando a cue adiantada chega pelo canal do sistema** é outra pergunta, e
   a resposta está no outro lado do caminho: `youtube_monotonic` (o relógio não recua) e
   `sotto_webview._yt_decide`/`_yt_advance` (decidem pelo relógio, não pela ordem de chegada).
   Medido em `_main/youtube-monotonic-oracle.py`, arm 8: a regra antiga recua 224 linhas num
   replay de 390, a nova recua 0.

## Um motor, dois produtores

`app/webview/youtube_reveal.py` expõe **uma** computação de desenho (`frame`), e os dois
caminhos alimentam-na com a mesma forma de linha:

```
YouTube  --payload--> rows_from_cues(cues) --(hit/pintura)--> window_by_paint --> frame()
                 (youtube_captions.parse_json3 -> cue["words"])
ASR      --texto-->  LiveRows.push(text, at) --------------------> frame()
```

O que `frame` devolve é `[{"text", "alpha", "exiting"}]`: o texto revelado de cada linha, o alfa
dela (255 viva, a descer na que sai) e se está a sair. `caption_overlay` desenha exactamente
isso — sem segundo relógio, sem segundo `wrap`, e sem um "sprout" próprio para a transcrição ao
vivo (o `WORD_STEP_S` de 2026-10-18 morreu com este trabalho). Onde o YouTube tem o
`tOffsetMs` da palavra, o ASR tem a chegada da palavra: `LiveRows.push` guarda o instante de
cada palavra nova e **mantém** o das palavras que continuam iguais no prefixo, por isso uma
correcção do modelo no fim da frase não reinicia a revelação da frase inteira.

A janela do overlay (2 linhas + a que sai) e a quebra (`caption_wrap`, com a fonte e a largura
reais) são as mesmas nos dois caminhos: `LiveRows` recebe o `wrap` do overlay
(`caption_overlay._wrap_fn`) e devolve TODAS as linhas; é o motor que escolhe quantas caberão
no ecrã. Um `wrap` que devolvesse 2 linhas punha o roll-up a cargo da quebra — o defeito que
esta separação existe para impedir.

## Paridade medida entre os dois produtores

A mesma tabela de números, agora sobre o **produtor do ASR**, com a arm que a mede em
`_main/youtube-1to1-oracle.py` (correm no veredicto normal; o mutante de cada uma corre em
`--neg-arm`, e é ele que prova que a arm sabe ficar vermelha):

| Arm | O que mede | Valor medido | Mutante que a põe RED |
|---|---|---|---|
| `live-rollup` | o produtor do ASR desenha 3 linhas e o alfa da que sai desce | **442 de 1978 quadros**, alfa **255 → 1** | `close-by-clock` (a linha sai pelo relógio, `end = at`) |
| `live-word-at-a-time` | palavras que entram no MESMO quadro | **1** (máximo, em toda a faixa) | `flat-asr-batch` (`gap = 0`, o lote todo de uma vez) |
| `row-alpha-in-pixels` | o alfa chega ao **bitmap**: soma do canal A quando a 1.ª linha desce | **1 912 772 → 1 459 343 → 750 782** | `row-alpha-ignored` (desenhar sem `alphas`) |
| `one-engine` | o display lê o motor e não tem segundo relógio | âncoras presentes: 3, relógios proibidos: 0 | `second-clock` (voltar a pôr `WORD_STEP_S`) |
| `early` (instrumento) | linhas que o player pinta antes do `start` | **0 de 16** quadros | — (medição, não arm) |

O caminho do YouTube continua a bater 1:1 com o payload nas 677 amostras (`words-1to1`,
`linebreaks-1to1`, `timing-1to1`, `word-reveal-1to1`), e os **13 mutantes** do ficheiro
correm em `python _main\youtube-1to1-oracle.py --neg-arm`, que imprime
`NEG-ARM PASS mutations=13 named-arm-fail=0`.

## Julgar a animação sem a app

`_main/sim/youtube-caption-sim.html` é a página que replaya um payload real pelas **mesmas
funções** (gerada por `_main/sim/make-youtube-caption-sim.py`, que importa
`youtube_reveal` e `word_fade` e não reimplementa nada): cada palavra, cada linha, cada alfa e
cada duração vêm do motor. Se a animação estiver errada na página, está errada na app.

## O que este documento não mede

* A curva CSS exacta do player (`[INFERENCE]`, linha 23/24).
* O estilo tipográfico do player (a fonte, o peso, o contorno). O Sotto desenha com a cara do
  tema: a legenda é do Sotto e imita o **comportamento**, não o tipo de letra do YouTube.
* A legenda automática (ASR do próprio YouTube): o payload medido é uma faixa curada. O que se
  mede aqui é a MECÂNICA da janela e do relógio, que é a mesma.
* O painel. A linha 26 diz o que ele faz (um fade de 140 ms na palavra nova, sem escalonamento:
  o multiplicador da `--type-step` é 0), e isso NÃO é um número do YouTube — é o desenho que o
  painel já tinha. Quem imita o player é o overlay nativo (`caption_overlay` + `youtube_reveal`);
  o painel não ganha um segundo relógio por causa deste trabalho.
