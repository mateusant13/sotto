# F8 RE-MEDIDO: a minha cura fechou UMA causa, e a segunda continua la

## A medicao, com o harness do proprio audit

  node _main/_ux-cdp.mjs --url file:///H:/sotto/app/panel/panel.html --w 380 --h 900
       --setup <data-theme=theme-N> --probe _main/_ux-probe-header.js

  theme-1   theme-button x=132 w=84   chevron x=218   smaller 248   larger 278   hide 338
  theme-2   theme-button x=122 w=84   chevron x=210   smaller 242   larger 274   hide 338

## O que a minha cura conseguiu, e esta medido

A largura do theme-button e CONSTANTE: **84 px nos dois temas**. Antes era 70,41 no theme-1 e
78,02 no theme-2 -- e no pd-cine chegava a 169,6, que era o que empurrava o X para fora da
janela. **Essa causa esta removida.**

## E o que NAO conseguiu, dito com o numero

**O chevron continua a 218 no theme-1 e a 210 no theme-2 -- 8 px de diferenca.** A ordem dele
[50531] e *a MESMA posicao em pixel entre designs*, e 8 px nao e a mesma posicao.

**E a causa NAO e a largura do botao:** a fileira comeca em x=102 no theme-1 e x=90 no
theme-2 -- 12 px de diferenca na largura TOTAL do conjunto, com os mesmos 7 controles de 28 px
e o mesmo hide a fechar em 338+28=366 nos dois. **Um conjunto mais largo do lado esquerdo, com
o mesmo numero de pecas do mesmo tamanho, so pode vir do espacamento entre elas ou de um
elemento a mais que eu nao vi.**

**Nao identifiquei qual dos dois e.** Fica nomeado como o proximo passo do F8: medir os GAPS
da fileira tema a tema e contar os filhos de `.panel__controls` em cada um.

## O que isto vale, apesar de incompleto

Antes desta medicao eu tinha uma cura e uma suspeita. Agora tenho: **uma causa fechada com
numero (a largura), uma causa medida mas nao identificada (12 px de largura da fileira), e a
prova de que a minha cura sozinha NAO fecha o F8.**

E a licao do metodo: **a re-medicao desmentiu a expectativa.** Eu esperava que com 84 px fixos
o chevron ficasse igual nos dois temas. Nao ficou. Sem esta corrida eu teria fechado o F8 por
construcao -- que e exactamente o erro que o audit existe para apanhar.
