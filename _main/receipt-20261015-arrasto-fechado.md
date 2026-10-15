# O ARRASTO: O LACO FECHADO -- `clientX` era relativo a JANELA QUE O SHELL MOVE

## O defeito, exacto, e sao duas palavras

O `strip-drag.js` JA calculava o delta desde o inicio do arrasto -- o que faltava era o
SISTEMA DE COORDENADAS:

    start = { px: event.CLIENTX, py: event.CLIENTY, ox: offset.x, oy: offset.y };
    var dx = event.CLIENTX - start.px;

**`clientX/clientY` sao relativos ao VIEWPORT DA JANELA.** O shell move a JANELA -- e tem
de mover, e o contrato -- e mover a janela muda o `clientX` do ponteiro **SEM O RATO
MEXER**. Entao:

  1. o dono mexe o rato 10 px, `dx` = 10, a pagina pede 10 px de deslocamento;
  2. o shell move a janela 10 px PARA A DIREITA;
  3. o ponteiro, parado, passa a ler `clientX` 10 px MENOR;
  4. `dx` cai para ~0, a pagina pede 0, o shell puxa a janela de volta;
  5. volta ao 1 -- para sempre, ~90 vezes por segundo.

**Nao era lentidao nem bloqueio: era realimentacao.** O dono sentiu *"completamente
travado"* porque a janela RESISTIA a sair do par de posicoes em vez de seguir o rato.

## E encaixa, ao pixel, no que o log dizia

    13:57:46.096  phase=move  offset=(22,-102)  to=(801,804)  base=(779,906)
    13:57:46.100  phase=move  offset=(16, -94)  to=(795,812)  base=(779,906)
    13:57:46.111  phase=move  offset=(22,-102)  to=(801,804)  base=(779,906)

O `base` NUNCA muda (esta fixo em (779,906), como o shell promete no comentario dele), o
`offset` ALTERNA, e a diferenca entre os dois pontos e exactamente o avanco que a janela faz
e desfaz. **O shell estava a obedecer; quem errava a medida era quem a tirava.**

## A correccao

    start = { px: event.SCREENX, py: event.SCREENY, ox: offset.x, oy: offset.y };
    var dx = event.SCREENX - start.px;

`screenX/screenY` sao relativos ao ECRA e **nao mudam quando a janela anda**, portanto `dx`
passa a medir so o que o dono mexeu. E a diferenca entre seguir o rato e perseguir a propria
cauda.

**Zero `event.clientX` restantes no ficheiro.** `node --check` verde.

## O que NAO esta provado, e digo-o

**Nao vi o arrasto a correr depois da mudanca.** O que esta provado e o mecanismo -- o laco
explica os dois valores alternados do log, e `screenX` e imune a eles por construcao. A
prova e um arrasto real com o log a mostrar `to=` a ANDAR PARA A FRENTE em vez de alternar.

## Duas coisas que aprendi aqui, e que me custaram tempo

  1. **Medi se o caminho corria antes de ler o codigo dele.** Sem isso eu teria procurado um
     bug de ligacao numa funcao que corre 1 498 vezes.
  2. **E li o que ele FAZ, no log, antes de ler como o faz.** O padrao de dois valores
     alternados disse "realimentacao" antes de eu abrir o ficheiro -- e o ficheiro tinha
     um `clientX` a espera de ser visto.
