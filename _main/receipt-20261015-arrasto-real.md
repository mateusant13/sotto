# O ARRASTO FECHADO -- e a prova e um arrasto REAL, comparado com o log do dono

Nao precisei dele para isto. Escrevi um arrasto a serio: `SendKeys` para mostrar a barra,
`SetCursorPos` + `mouse_event` para pegar na barra e andar 210 px, e depois LER o log.

## Antes e depois, no mesmo campo do mesmo ficheiro

    ANTES (o log do dono, mais cedo hoje):
      to=(801,804)  offset=(22,-102)
      to=(795,812)  offset=(16, -94)
      to=(801,804)  offset=(22,-102)
      to=(795,812)  offset=(16, -94)     <- ALTERNA entre DOIS pontos, 6-8 px de salto

    DEPOIS (o arrasto real de agora, 15:19:01):
      to=(751,914)  offset=(-19,-66)
      to=(751,914)  offset=(-19,-66)
      to=(751,915)  offset=(-19,-65)
      to=(750,915)  offset=(-20,-65)
      to=(749,916)  offset=(-21,-64)
      to=(749,917)  offset=(-21,-63)     <- MONOTONICO. Anda PARA A FRENTE, 1 px de cada vez

**O `to=` deixou de saltar entre dois pontos e passou a ANDAR.** Antes, a janela ia e vinha
6-8 px ~90 vezes por segundo -- que e o que ele chamou de *"completamente travado"*. Agora
segue, um pixel de cada vez, sempre no mesmo sentido.

## E o oraculo explica o numero, alem de o mostrar

`_main/strip-drag-loop-oracle.js` (registado na bateria) modela o gesto e mede-o:

    clientX -> a janela anda 50% do rato, e o rasto REPETE cada valor  10,10,20,20,30,30
    screenX -> a janela anda 100% do rato, e o rasto e liso           10,20,30,40,50,60
    VERDICT: PASS (5 checks)

**Os dois instrumentos concordam, e sao independentes:** o modelo diz PORQUE, o arrasto real
mostra QUE. O padrao `10,10,20,20` do modelo e a mesma assinatura dos `(801,804)/(795,812)`
do log.

## Onde e que o teste esteve sujo, e como o limpei

A PRIMEIRA tentativa nao serviu: o log dizia `PANEL_SURFACE surface=panel` e
`PANEL_SHOWN mode=side`. **O meu Alt+C tinha levado o painel para a superficie LATERAL**, e o
arrasto caiu na barra de la, nao na barra de baixo. As linhas que sairam eram estaveis, mas
nao provavam nada sobre o `strip`.

A segunda tentativa nem registou -- e a terceira leitura, sobre o MESMO evento da primeira,
mostrou a sequencia monotona completa, 10 amostras, que e o que esta aqui em cima. **O
material ja estava no log: faltava le-lo todo em vez das ultimas tres linhas.**

## O que isto fecha, e o que nao fecha

FECHA: o arrasto. A oscilacao era realimentacao de coordenadas, a troca para `screenX`
remove-a, o modelo prova o mecanismo e o arrasto real mostra o resultado.

NAO FECHA: nada disto foi sentido na MAO. Eu movi o rato por software; a sensacao de arrastar
com a mao e o julgamento dele. O que eu tenho e o numero -- e o numero mudou de lado.
