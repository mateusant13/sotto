# DIMENSIONADA AO CONTEUDO -- a ultima peca de codigo do objetivo

O objetivo, por palavras: *"dimensionada ao proprio conteudo"*. A janela era fixa em
170 px. Uma linha que ocupasse tres cortava; uma janela alta a mais cobria o ecra de
graca.

## A cadeia, e sao quatro elos

1. **A pagina mede-se a si propria.** `caption.html` expoe
   `window.SottoCaption_neededHeight()`, que le o palco com `getBoundingClientRect()`
   -- ja inclui o padding e a quebra de linha -- e soma 8 px de folga.
2. **O `set()` devolve-a.** O `evaluate_js` do pywebview devolve o valor da ULTIMA
   expressao, portanto `needed = win.evaluate_js('...SottoCaption.set(...)')` e a
   altura, sem uma segunda travessia.
3. **O shell redimensiona E MOVE.** `_fit_caption_window(needed)`.
4. **A folga vem do `set`.** Zero significa "a pagina nao se soube medir", e zero nao
   mexe nada.

## O detalhe que faz a diferenca, e e onde isto se podia estragar

`resize()` do pywebview conserva o canto SUPERIOR. A legenda esta ancorada ao FUNDO
(`bottom: 0`). **So redimensionar fazia a legenda crescer PARA CIMA a partir de uma base
que subia -- a base mexia-se, que e o contrario exacto de "pousada no fundo".** Por isso a
posicao e recalculada para a ARESTA DE BAIXO ficar onde estava:

    bottom = cap_y + (have if have else want)
    win.move(cap_x, bottom - want)

**E a histerese de 8 px** e o que impede o tremor: uma medida que oscila 1 px entre duas
legendas punha a janela a tremer a cada linha. So mexe quando a diferenca passa de 8.

## Verificado por RENDER, nao por leitura

O `caption.html` mudou, e um erro de JS ali quebrava a janela toda. Renderizado a
900x170 com a fixture: **a imagem e identica ao render anterior a mudanca** -- LED verde,
linha anterior fraca, "Uma vez que voce foi.", os creditos, tudo no fundo e centrado.
A fixture aplicar-se PROVA que o `set()` corre e devolve.

`py_compile` rc=0, 545 064 B.

## O QUE FALTA NO OBJETIVO -- e agora e uma coisa tua e duas de honestidade

1. **NADA DISTO FOI VISTO DENTRO DA APP A CORRER.** A app do dono tem o codigo de ha
   mais de 10 horas; o `before_show` da janela da legenda so corre num arranque novo.
   Tudo o que esta provado e o CAMINHO: sonda, screenshot, render e compilacao.
2. **A marca `data-caption-window` devia ler `IsWindowVisible`.** Hoje ela e escrita
   depois de o `show()` correr, o que protege contra uma EXCECAO mas nao contra um
   sucesso que mente -- se a janela devolver sucesso e nao aparecer, a legenda do painel
   esconde-se a mesma.
3. **E um limite honesto do auto-dimensionamento:** a altura medida depende da LARGURA,
   que e fixa em 900. Numa janela mais estreita a mesma frase quebra mais e o numero
   medido envelhece. Hoje e coerente porque a largura nao muda; se mudar, isto tem de
   voltar a ser medido, e nao assumido.
