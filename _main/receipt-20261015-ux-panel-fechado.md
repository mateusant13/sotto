# O SEGUNDO AUDIT: TRES ORDENS TUAS AINDA VIOLADAS, E AS TRES FECHADAS

O subagente `ux-side-panel` entregou nove achados. Os tres CRITICOS sao ordens que ele ja
tinha dado e que continuavam por cumprir -- e **um deles eu tinha "corrigido" no sitio
errado.**

## F1 (CRITICO) -- a gaveta do transcript AINDA pintava uma barra de scroll

A ordem dele, verbatim [50532]: *"e tambem nao quero q apareca a barra de scroll"*.

MEDIDO: `#history-list` com **10 px de gutter reservado**, `scrollbar-width: thin`,
`::-webkit-scrollbar{display:block;width:8px}`, e **1601 px de conteudo dentro de 208**
(evidencia `I:/cc-tmp/ux-audit/P2-panel-history-theme1.png`).

**E eu tinha ido corrigir a barra de scroll no STRIP.** A ordem era sobre o painel, e a lista
do historico ficou de fora -- o fix do `.captions__body` nunca chegou a gaveta. Agora chegou:
`scrollbar-width: none` + `::-webkit-scrollbar{display:none}`. **A lista continua a rolar; o
que sai e o desenho da barra.**

## F2 (CRITICO) -- o dialogo "Personalizar tema" pintava a sua propria barra de 15 px

Mesma ordem, outro sitio: `#tune-body` com gutter 15, `scrollbar-width: auto`, webkit
`display: block`, **905 > 468 px**. Corrigido com as mesmas duas declaracoes.

## F3 (CRITICO) -- TODO dialogo abria no CANTO SUPERIOR ESQUERDO

A causa e uma linha que ninguem ve: o reset `* { margin: 0 }` (`panel.css:99-103`) **derruba o
`margin: auto` que o user-agent da a um `dialog`.**

MEDIDO a 380x900: sem o fix, a caixa fica em **{0,0,340,162}**; com ele, em **{20,369}** --
centrada. `python: .pause-dialog { margin: auto; }`. **Uma linha, e o `.tune-dialog` herda.**

## O que fechei antes, do outro audit (o do strip)

  * **F2** -- a pilula VAZIA de ~800 px que empurrava a marca para x=817 (era a moldura que ele
    fotografou): `order: -1` -> `99` e `flex: 0 0 auto`;
  * **F3** -- o contorno de todos os controles a 2,26:1, abaixo do limiar 3:1: alfa 0,28 ->
    0,38 = 3,19:1;
  * **F4** -- o LIVE verde com a palavra VERMELHA. E era pior do que o audit via: o `panel.css`
    tinha um bloco *"STATE ON: red, filled, loud"* a pintar o estado live de vermelho, contra o
    verde do override. **Vermelho num indicador quer dizer erro, e "live" nao e um erro.**
  * **F5** -- a hairline de 1 px no topo, que o `border: 0` nao tocava porque vive num
    `::before`:
    `body .panel::before { content: none !important; }`

## O QUE FICA, e o mais grave e cross-lane

**F1 do strip (BLOQUEADOR) -- o dialogo de Pause nao cabe na janela do strip.** O segundo
audit confirma-o por outro caminho: a 1040x100 o user-agent limita um `dialog:modal` a
`max-height: calc(100% - 32px)` = 68 px, e o conteudo tem 162 -- **a barra que ele fotografou
tem DUAS causas reproduziveis, e nenhuma se resolve com CSS.**

**E o `overflow: hidden` que eu pus NO RECORTOU:** o titulo ficou 91 a 127 px acima da janela.
Troquei uma barra de scroll por um corte e chamei-lhe cura. A cura e a shell crescer a janela
para o modal, ou o Pause do strip encaminhar a confirmacao para o painel.

**E quatro achados de legibilidade, todos MEDIDOS, que eu nao fechei:**

  * **F4 (ALTA)** -- sobre video BRANCO a legenda viva nao tem forma de letra: de 23 209 px
    alterados, **17** sao mais claros que o fundo (contraste p10/p50 = 1,07/1,31). **O que se
    ve e a sombra preta -- um borrao.** Cura proposta, e respeita o "sem fundo":
    `-webkit-text-stroke:2px rgba(0,0,0,.85); paint-order: stroke fill;`
  * **F5/F6 (ALTAS)** -- a linha anterior esta a ~15% e os creditos a ~29%, porque **dois alfas
    se MULTIPLICAM** (`0.36 x 0.42` e `0.52 x 0.55`);
  * **F7 (ALTA)** -- o texto pequeno falha AA: `.caption__time` 2,10:1; glifos 2,65:1; hint e
    path 2,65:1. **Cura no GERADOR** (`gen_themes.py`): `--text-muted` 0,30 -> 0,52 e
    `--text-secondary` 0,50 -> 0,64. **Nunca a mao no `theme-*.css`** -- sao gerados.
  * **F8 (MEDIA)** -- o mesmo botao em posicoes diferentes por design, e **o `#hide-button` do
    `pd-cine` corre 19,6 px PARA FORA da janela de 380** (cortado); a marca colapsa a 0 px de
    largura em 4 dos 10 designs.

**Tudo o que ficou esta nomeado com ficheiro, linha e numero.** Nada foi vendido como fechado.
