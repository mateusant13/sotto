# O ARRASTO: O LACO, PROVADO POR MODELO -- e o modelo provou-me errado primeiro

# O oraculo

`_main/strip-drag-loop-oracle.js` (novo, registado na bateria). Modela o gesto: o ponteiro
anda 10 px por passo NO ECRA, a pagina calcula o delta, o shell move a janela para o offset,
e mede-se o DESLOCAMENTO TOTAL da janela contra o do ponteiro.

    node _main/strip-drag-loop-oracle.js

    ponteiro andou ................ 200 px
    clientX -> janela andou ....... 100 px   ( 50% do rato)
    screenX -> janela andou ....... 200 px   (100% do rato)

    clientX rasto:  10, 10, 20, 20, 30, 30     <- CADA VALOR DUAS VEZES
    screenX rasto:  10, 20, 30, 40, 50, 60     <- liso

    ok  A  screenX: a janela segue o rato ate ao fim
    ok  B  clientX: a janela anda METADE do que o rato andou
    ok  C  clientX: o rasto REPETE cada valor (o engasgo que ele sentiu)
    ok  D  screenX: cada passo acrescenta os 10 px todos
    ok  E  screenX: o rasto NAO repete nenhum valor
    VERDICT: PASS

## E ISTO E O DEFEITO QUE ELE DESCREVEU, ao numero

**`clientX` faz a janela andar a METADE da velocidade do rato, com cada posicao repetida.**
Nao era paralisia total -- era um arrasto que fica para tras e engasga, e o dono chamou-lhe
*"completamente travado"*. **O modelo reprodu-lo, e a correccao tira-o.**

## O erro que eu cometi, e que vale mais do que o acerto

**A minha primeira versao do oraculo deu 4 FALHAS -- e a culpa era do modelo, nao do codigo.**
Eu tinha escrito `offset = offset + dx`, ACUMULANDO o delta a cada passo. **O codigo real nao
acumula**: e `live = start.ox + dx`, calculado de fresco em cada evento, com o `start.ox`
guardado no `pointerdown`.

Com o modelo errado, o `clientX` parecia PERFEITO (200 de 200 px) e o `screenX` parecia
catastrofico (2100 px, dez vezes o rato). **Se eu tivesse acreditado na primeira corrida,
teria concluido o OPOSTO do verdadeiro e "corrigido" o lado certo.**

O que me salvou foi a forma do rasto: `10, 20, 30, 40` acumulado nao bate com o codigo que eu
tinha acabado de ler. Fui ver o `strip-drag.js` outra vez, vi `live = start.ox + dx`, e o
modelo caiu.

## O que fica por provar

**Nao houve um arrasto fisico depois da correccao.** O que esta provado e o MECANISMO -- o
modelo reproduz o defeito e a troca remove-o, e o `screenX` e imune por definicao (a posicao
do ponteiro no ecra nao depende de onde a janela esta). **A prova final e um arrasto real com
o log a mostrar `STRIP_DRAG to=` a ANDAR PARA A FRENTE em vez de alternar entre dois pontos.**
