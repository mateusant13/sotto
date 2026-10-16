# BOTOES NO MESMO PIXEL: o theme-button tinha largura do CONTEUDO e empurrava a fileira

## O que o audit mediu (header-rects.json), tema a tema, mesma viewport

    theme-button:  theme-1 w=70.41 ... theme-2 w=78.02 ... pd-cine w=169.6
    theme-chevron: theme-1 x=218 ... theme-2 x=210 ... pd-cine x=235.6
    smaller: theme-1 x=248 ... theme-2 x=242
    hide do pd-cine: right edge a 19.6 px PARA FORA da janela de 380 (cortado)

A ordem do dono [50531]: a MESMA posicao em pixel entre designs.

## A causa, e e uma regra

    .theme-button { width: auto; white-space: nowrap; }

**A largura saia do NOME.** Nomes de tamanhos diferentes davam botoes de tamanhos diferentes,
e como o botao mora numa fileira `flex` com `gap: 6px`, cada nome empurrava tudo o que vinha
depois. No pd-cine, o nome de 169,6 px empurrou o X para fora da janela.

## A cura

    .theme-button {
      width: 84px; min-width: 84px; max-width: 84px;
      box-sizing: border-box;
      display: inline-block; padding: 0 6px;
      white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis;
    }

**84 px fixos e ellipsis.** O nome longo e cortado com reticencias em vez de empurrar a
fileira; `box-sizing: border-box` para o `padding: 0 6px` nao sair da conta; e 84 cobre os
nomes curtos medidos (70,41 e 78,02) sem os colar a borda.

## O que isto NAO fecha, dito

1. **A linha y=14 vs y=24,5 entre theme-N e pd-*.** O audit mediu a fileira a y=14 nos cinco
   temas e a y=24,5 em todos os pd-*. E o outro eixo da mesma queixa, e eu nao lhe toquei.
2. **A marca a colapsar a 0 px em 4 de 10 designs.** Medido pelo audit. Precisa de um
   `min-width` ou de um layout que nao dependa do conteudo, e eu nao medi o suficiente para
   o fixar sem adivinhar.
3. **NAO re-medi depois da mudanca.** O provado aqui e a causa (o width que depende do nome)
   e que a cura a remove por construcao. A re-medicao dos rects nos dez temas e a prova que
   falta, e usa o `_main/_ux-header-probe.js` do audit.
