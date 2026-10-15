A CORRECCAO NAO MUDOU O RENDER -- e registo-o em vez de fingir que sim

Objectivo: a linha em formacao transbordava pela direita e as palavras ficavam
cortadas na margem. Visto com os olhos num print novo (theme-1, 380x900).

O QUE FIZ: `.captions__body` tinha `overflow-y: auto` e nenhum `overflow-x`. A
hipotese era que a linha nao tinha caixa propria onde quebrar, e que o `overflow:
hidden` do `.panel` a cortava. Acrescentei `overflow-x: hidden` ao contentor de
scroll.

O QUE A MEDICAO DIZ: o print novo e BYTE-IDENTICO ao anterior.
  shots3/panel-theme-1.png   sha256 1c1dae1aae3a43c8...   62 859 B
  shots4/panel-theme-1.png   sha256 1c1dae1aae3a43c8...   62 859 B

Ou seja: a correcao nao mudou nada no que e pintado. Duas explicacoes possiveis, e
nao sei qual e:
  1. a sonda serve uma cópia cacheada do CSS (ela corre contra uma copia propria do
     shell, `_paint-offscreen-sotto_webview.py`, e o WebView2 pode estar a servir o
     file:// stylesheet de um cache que nao invalidei);
  2. a linha em formacao nao esta dentro de `.captions__body` -- pode estar noutro
     elemento (o palco da legenda ou o overlay), e o contentor que corrigi nao e o dela.

O QUE NAO FACO: nao digo que esta corrigido. Um print identico e a prova de que nao
esta, e afirma-lo seria a mesma mentira que ja cometi esta sessao (o bloco negro).

O PROXIMO PASSO MEDIDO: descobrir em que elemento vive a linha em formacao, com um
instrumento que leia o DOM renderizado -- nao com um grepo ao ficheiro, que foi o que
me deixou corrigir o contentor errado.
