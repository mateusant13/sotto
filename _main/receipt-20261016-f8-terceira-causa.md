# F8, TERCEIRA CAUSA: a FILEIRA muda de sitio -- e a palavra (brand) colapsada e a suspeita

## O que a medicao do pd-cine diz (harness do audit, mesma viewport 380x900)

    pd-cine   row x=62  w=288  gap=6px    hide dir = 322+28 = 350
    theme-2   row x=78  w=288  gap=6px    hide dir = 338+28 = 366

## O que isto prova sobre o que eu ja fiz

**A cura da largura + gap FUNCIONA:** o X fechava a 399,6 no pd-cine (19,6 px FORA de 380)
e agora fecha a 350 -- dentro. **O corte desapareceu.** E `w=288`, `gap=6px` sao iguais nos
dois.

## E o que continua aberto, com o numero

**A fileira inteira esta 16 px mais a esquerda no pd-cine (x=62 contra x=78).** Todos os sete
controlos movem juntos -- e a largra e o gap iguais -- portanto a causa NAO e dentro da
fileira: **e a POSICAO da fileira dentro do cabecalho.**

**A suspeita, e vem do audit:** a marca (wordmark) colapsa a **0 px de largura em 4 dos 10
designs** (pd-tele, pd-cine e outros). O cabecalho e `display: flex; justify-content:
space-between` -- e sem a palavra para ocupar a esquerda, a fileira dos controlos desloca-se
para a posicao que a distribuicao lhe da.

**Nao afirmei que e isso sem medir:** o que esta medido e a POSICAO divergente (62 vs 78), nao
a regra que a decide. O proximo passo e a medicao do cabecalho (`.panel__header`) nos dois:
`justify-content`, `gap`, filhos visiveis e a largura da palavra.

## Os dois subagentes silenciosos estao de volta

O dono: *"e se voce tinha subagents rodando, veja se da pra dar resume neles. tinhamos
crashado."* **Dois tinham terminado SEM relatorio** -- e eram exactamente os dois itens
abertos:

  * `c07c39f8` (diagnostico do Alt+C) -- RETOMADO, `messageId 9b3f58be`. Pedido: o que sabe
    que eu nao sei alem do foreground, e se ha `PANEL_FOREGROUND_ATTACH` desde as 08:08.
  * `a2209c89` (rects dos botoes por tema) -- RETOMADO, `messageId 7f8f3284`. Pedido:
    medir os 5 pd-* e 2-3 cine-* com o CSS tardio injectado, e o DELTA contra theme-2.

**Ambos com `status: accepted`.** Sem lancar nada, sem por nada no ecra dele -- disse-lhes isso
de novo na mensagem de retoma, por escrito.
