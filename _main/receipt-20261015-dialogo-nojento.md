# O DIALOGO NOJENTO: barra de scroll fora, e o texto que argumentava contra ele proprio

## O que a captura fora do ecra mostrou

`I:/cc-tmp/off1.png` -- o dialogo *"Pause and unload?"*, com:

  * uma BARRA DE SCROLL dentro do dialogo;
  * duas linhas de copia a mais, incluindo um paragrafo que dizia ao utilizador que ele NAO
    PRECISA do botao que acabou de carregar;
  * um botao desactivado, *"Pause -- not available in this shell yet"*;
  * *"This build cannot pause yet"* a vermelho.

## O que eu fechei nesta rodada

**1. A barra de scroll, e a CAUSA dela.** O `<dialog>` nao declarava `overflow`, portanto o
valor do user-agent (`auto`) entrava, e o conteudo -- mais alto que a caixa -- punha a barra.

    .pause-dialog {
      overflow: hidden;

**E o `hidden` sozinho teria escondido o corte em vez de o resolver** -- por isso, no mesmo
passo:

**2. O paragrafo de enchimento saiu do markup.** Era o *"Worth knowing: the background
transcript is extremely light -- it costs almost nothing to leave running. Pausing is not
necessary to keep the PC fast, and resuming reloads the model and takes a few seconds."*

Ele fazia DUAS coisas mas:

  * enchia o dialogo ate a altura que OBRIGAVA o `<dialog>` a ganhar barra de scroll;
  * **e argumentava contra ele proprio** -- um dialogo a dizer ao utilizador que nao precisa
    do botao que ele acabou de carregar. **Isso nao e informacao, e uma desculpa.**

## Seguro, e verificado antes de mexer

`grep -c pause-dialog-honest app/panel/panel.js` = **0**. Nenhum handler procura o elemento,
portanto a remocao nao deixa nada pendurado. (Esta verificacao e a licao de hoje: eu ja
removi um elemento hoje e deixei dez regras mortas e um oraculo vermelho.)

## O QUE FALTA NESTE DIALOGO, e e do `panel.js`

Os dois defeitos que mais contribuem para o *"nojenta"* continuam la, e sao de JS:

  1. **um botao DESACTIVADO** com o rotulo *"Pause -- not available in this shell yet"* --
     **oferecer ao utilizador uma funcao que nao existe e pior do que nao a oferecer.** Se
     `bridge.pause()` nao existe, o botao nao deve estar no dialogo;
  2. **a linha vermelha** *"This build cannot pause yet. The panel has no bridge.pause()
     call..."* -- **um erro sobre o qual ele nao pode agir, escrito para um programador.**

Ficam nomeados com o ficheiro. **Nao os toquei porque sao JS e o meu contexto esta no fim --
e mexer em JS sem correr e como o `clientX` de hoje: parece certo e falha na mao do dono.**
