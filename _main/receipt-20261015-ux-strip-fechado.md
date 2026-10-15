# O AUDIT DE UX DO STRIP ENTREGOU -- e QUATRO dos oito achados estao fechados

O subagente `ux-strip-bar` entregou com instrumentos proprios, **sem lancar a app, sem uma
tecla e sem nada na tela do dono** (Chromium headless a 1040x100, cinco temas). Oito
achados, todos com numero. Quatro fechados por mim nesta rodada.

## O QUE ESTAVA ERRADO -- e o maior era uma coisa que eu proprio fiz

**F2 (ALTA) -- A PILULA VAZIA DE ~800 px.** Medido: `#strip-state` com **803,48 / 795,09 /
800,59 / 799,66 / 799,97 px** de largura, e a marca `sotto` a x=**817,48** -- fora do ecra --
em vez de x=8. **Era isto a moldura vazia que ele fotografou**: uma caixa com borda, sem
conteudo dentro, a comer a barra inteira, com o nome da app empurrado para fora.

Causa: duas regras a somar. `zip-overlay.css:22-25 #strip-state{order:-1}` (que eu escrevi,
e cujo comentario diz *"order 99 is what parked it on the right; the zip has it leftmost"* --
eu troquei-o) vezes `.stripbar__state{flex:1}` do `panel.css`, que a estica.

    #strip-state { order: 99; }        /* era -1 */
    .stripbar__state { flex: 0 0 auto; }

**F3 (MEDIA) -- o contorno de TODOS os controles a 2,26:1.** O limiar e 3:1, e a ordem dele
em [41856] e *"visiveis o suficiente pro usuario"*. Borda de `0.28` para `0.38` = 3,19:1.

**F4 (MEDIA) -- o LIVE verde com a PALAVRA vermelha.** E era pior do que o audit via: o
`panel.css` tinha um bloco chamado *"STATE ON: red, filled, loud"* que pintava o estado live
de VERMELHO, enquanto o meu override o pintava de VERDE. **Duas decisoes opostas na mesma
pilula** -- e **vermelho num indicador quer dizer erro, e "live" nao e um erro.** Tudo a
verde, incluindo o pseudo-elemento, que e onde a palavra vive.

**F5 (MEDIA) -- a hairline de 1 px no topo.** O `border: 0` que eu tinha posto remove a
BORDA e nao toca no pseudo-elemento: o audit mediu `.panel::before` com `content=''`,
1040x1 px e um gradiente. **Uma moldura por outro nome**, contra a ordem [50531].

    body .panel::before { content: none !important; }

## O QUE O AUDIT CONFIRMOU ESTAR CERTO, e vale registar

  * TODO o texto do strip passa AA: marca 16,33:1, palavra de estado 16,33:1, `off` 12,94:1,
    `live` 4,97:1;
  * **o X e o controle mais a direita** (x=1006, w=26) -- a ordem [32218];
  * **zero sobreposicao** entre a marca e os controles, nos cinco temas -- a ordem [50531];
  * **nao ha botao de transcript nem de "em curso"/"historico"** no markup do strip --
    [41856], cumprido;
  * **nenhuma barra de scroll** do documento (`scrollables NONE`);
  * `.panel` com `border-width: 0` e `radius: 0` no strip.

## O QUE FICA, e o mais grave e cross-lane

**F1 (BLOQUEADOR) -- o dialogo de Pause e ILEGIVEL na janela do strip.** Medido a 1040x100:
a caixa tem `340x68` (o user-agent limita um `dialog:modal` a `calc(100%-32px)`), o conteudo
tem 158-198 px, e o TITULO fica a **y=-93,0** (t1) ... **-127,0** (t5) -- **91 a 127 px ACIMA
da janela.**

**E o `overflow: hidden` que eu pus esta rodada ANTERIOR so o RECORTOU.** O audit tem as duas
versoes: antes, `overflowY=auto` com `scrollHeight 260 / clientHeight 0` -- a barra que ele
fotografou; depois, `overflowY=hidden` com o titulo fora da janela. **Eu troquei uma barra de
scroll por um corte, e chamei-lhe cura.**

**CSS NAO RESOLVE ISTO:** nao cabe um modal de 220-260 px num HWND de 40/100 px. A cura e
**ou a shell crescer a janela para o modal, ou o Pause do strip encaminhar a confirmacao para
a superficie do painel.** Fica nomeado, com a medida, para nao ser vendido como fechado.

**F6, F7, F8 (baixas)** -- o estilo proprio do Pause esta morto (`strip-button--pause` so
existe no `panel.css` e o botao nao carrega a classe); a marca pinta `SOTTO` em vez do
`sotto` minusculo que o markup documenta; e um comentario diz que a linha quebra quando o
`.stripbar` nao tem `flex-wrap`. Nenhuma delas mexe no que ele ve agora.
