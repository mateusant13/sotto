# "RESTAURA OS BOTOES QUE TINHA" -- a MEDICAO: nove viraram quatro, e cinco sairam

Ordem dele, verbatim: *"restaura os botoes que tinha. remove os botoes que eu ja falei pra
remover anteriormente."* Isto mede-se com git, e foi o que fiz.

## A barra original -- `1d97536`, 2026-10-10

  <section class="stripbar" id="strip-controls">
    <span class="stripbar__brand">sotto</span>
    strip-live-button .................. LIVE
    strip-theme-button ................. a amostra de cor do tema
    strip-theme-chevron ................ a seta do dropdown
    strip-transparency-button .......... Transparency
    strip-open-button .................. Open panel
    strip-hide-button .................. Hide
    strip-font-smaller-button .......... Smaller
    strip-font-larger-button ........... Larger
    strip-pause-button ................. Pause

**NOVE controlos.**

## A barra de agora -- HEAD

    strip-live-button .................. live
    strip-open-button .................. Open panel
    strip-hide-button .................. Hide
    strip-pause-button ................. Pause

**QUATRO controlos.**

## OS CINCO QUE SAIRAM, e o que se sabe de cada um

  1. **strip-theme-button** -- o seletor de tema. **SAIU SEM EU LHE DIZER.**
  2. **strip-theme-chevron** -- a seta do dropdown. Igual.
  3. **strip-transparency-button** -- saiu porque estava BUGADO, e o dono descreveu o bug:
     *"cliquei num botao e ele sumiu e agora ta so a cor solida de volta, inteira"*. **Este
     NAO pode voltar sem a cura primeiro** -- restaurar um botao que mata o painel e
     restaurar o defeito.
  4. **strip-font-smaller-button** -- o diminui o tamanho da letra.
  5. **strip-font-larger-button** -- o aumenta. O shell ainda fala de *"the owner font
     dial"* em varios sitios, portanto o mecanismo pode estar vivo sem o botao.

## E o dropdown nao e um extra: e um pedido DELE, de origem

[860], 2026-10-09, verbatim:

  *"also a dropdown to choose the templates, that you use your mouse and when hover the
   tamplates preview."*

**O seletor de temas com pre-visualizacao ao passar o rato foi pedido por ele no primeiro dia
e a barra que o servia ja nao existe.** Quando eu escrevi num recibo que o dropdown "nao
existe", a verdade e pior: **existiu e foi tirado, sem uma linha a dizer porque.**

## O que eu faco com isto, e a ordem

  1. **os quatro seguros** -- theme, theme-chevron, smaller, larger -- voltam, com os rotulos
     que o dono pediu: *"botoes simples e pequenos porem visiveis o suficiente"*;
  2. **o transparency NAO volta antes da cura** -- e o bug tem nome no comentario do shell
     (*"cliquei num botao e ele sumiu"*), portanto a ordem e cura-primeiro, botao-depois;
  3. **e nada disto entra sem o mark-up e o CSS juntos**, porque foi a separacao dos dois que
     produziu a barra ilegivel de hoje.

## O que fica por medir

**Porque e que cada um saiu.** O `git log -S` por id de botao diz em que commit cada um
desapareceu, e a mensagem desse commit diz o motivo. **Nao fiz essa parte ainda** -- e e a
diferenca entre restaurar o que ele quer e restaurar o que ja foi decidido tirar.
