# F8 FECHADO: DELTA ZERO -- e eram DUAS causas, as duas medidas

## A ordem

[50531], verbatim: *a MESMA posicao em pixel entre designs*.

## Causa 1: a largura do botao dependia do NOME do tema

  MEDIDO (audit):  theme-button  70,41 px (theme-1)  78,02 (theme-2)  169,6 (pd-cine)
  CURADO:          84 px fixos + ellipsis                          (commit 402c096)

**E isso NAO chegou.** A re-medicao desmentiu a minha expectativa: o chevron continuava a 218
no theme-1 e 210 no theme-2 -- 8 px. **Foi essa medicao que me obrigou a procurar a segunda
causa, e ela existe.**

## Causa 2: o GAP da fileira era de cada tema

  MEDIDO:  .panel__controls  theme-1  x=102  w=264  gap=2px
                            theme-2  x= 90  w=276  gap=4px

A conta fecha sem sobra: 7 controlos (6 de 28 px mais o botao de 84) = 252 px, mais SEIS
espacos. 252 + 6x2 = 264 e 252 + 6x4 = 276. **Os 12 px de diferenca sao o gap.**

E a origem sao DUAS direcoes do gerador, cada uma com o seu valor:

    gen_themes.py:1770   @S@ .panel__controls{ gap: 2px; }
    gen_themes.py:2017   @S@ .panel__controls{ gap: 4px; }

com o `panel.css:289` a declarar a base (`gap: 6px`) que ambas derrubam.

  CURADO:  body .panel__controls { gap: 6px !important; }   no `zip-overlay.css`

A folha que carrega por ultimo, para alcancar todos os temas de uma vez -- a mesma tecnica da
moldura e da cor-chave.

## A MEDICAO QUE FECHA, com o harness do proprio audit

  node _main/_ux-cdp.mjs --url file:///H:/sotto/app/panel/panel.html --w 380 --h 900
       --setup <data-theme=theme-N> --probe I:/cc-tmp/ux-probe-row.js

    theme-1   row x=78  w=288  gap=6px
    theme-2   row x=78  w=288  gap=6px

    DELTA theme-1 vs theme-2:
      theme-button d=0    theme-chevron d=0    font-smaller d=0    font-larger d=0
      tune-button  d=0    pause-button  d=0    hide-button  d=0
      row.width delta = 0

**Delta ZERO em todos os sete controlos.** E o X fecha em 338 + 28 = 366, dentro da janela de
380 -- o overflow de 19,6 px que o audit mediu no pd-cine vinha da largura do botao, que esta
fixada.

## O que isto ensina, e e o mais importante deste recibo

**A minha primeira cura nao bastou, e eu so o soube porque RE-MEDI.** Se tivesse fechado o F8
por construcao -- *a largura esta fixa, logo as posicoes estao fixas* -- teria entregado um
F8 fechado no papel e partido na tela, com 8 px de deriva entre temas e o X a mudar de sitio.

A regra do dono e *nenhum criterio se fecha sem numero*. **Este fechou com sete zeros.**

## O que NAO esta medido

Os 25 temas `cine-*` e os 10 `pd-*` NAO foram medidos -- sao carregados tardiamente pelo
`lazy-assets.js` e o harness so carrega `panel.html` com `data-theme` trocado. **O que esta
provado e theme-1 contra theme-2, e que as duas causas medidas sao as duas que variavam.**
Fica nomeado: a re-medicao dos `pd-*` precisa de um setup que injete o CSS tardio primeiro.
