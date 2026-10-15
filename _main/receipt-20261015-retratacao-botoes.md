# RETRACC AO: OS BOTOES NAO DESAPARECERAM -- FORAM REMOVIDOS POR ORDEM DELE

## O que eu afirmei, e era falso

Ha duas rondas eu escrevi, e entreguei a ele:

  "A barra original tinha NOVE controlos... A barra de agora tem QUATRO. FORAM REMOVIDOS
   CINCO... o dropdown de temas e um pedido teu de origem [860]... existiu e foi tirado, sem
   uma linha a dizer porque."

E FALSO, e a prova esta no proprio ficheiro que eu nao fui ler. O panel.html guarda o motivo,
em dois blocos de comentario, exactamente onde os botoes estavam:

    <!-- REMOVED 2026-10-12 (owner: *"o painel de baixo, deve conter apenas o bare
         minimum"* / *"o painel de baixo ... deve ser menor ainda, mais estreito, do
         tamanho dos botoes"*). WHAT STOOD HERE WAS `#strip-theme-button` ... the
         capability is NOT lost -- theme-switcher.js owns BOTH mounts, and the
         panel own #theme-chevron ... opens the full list -->

    <!-- REMOVED 2026-10-12: the theme-list CHEVRON on the strip ... the dropdown MOVED
         TO THE RIGHT PANEL. Its one trigger is #theme-chevron, built inside
         .panel__controls -->

## O que isso diz

  1. A remocao tem a ORDEM DELE citada -- "o painel de baixo deve conter apenas o bare
     minimum", "menor ainda, mais estreito, do tamanho dos botoes". Nao foi um
     desaparecimento silencioso: foi uma ordem, com a frase dele ao lado.
  2. O DROPDOWN NAO SE PERDEU -- MUDOU DE SITIO. O gatilho e #theme-chevron, dentro de
     .panel__controls, no painel da DIREITA. Todos os temas continuam alcancaveis. O que a
     barra perdeu foi uma SEGUNDA porta para a mesma sala.
  3. E o #strip-open-button esta a um clique, na mesma barra.

## Como e que eu errei -- e o erro metodologico vale mais que a correccao

Escrevi um script que entrava no section.stripbar e saia no primeiro /div. O markup e
ANINHADO: o primeiro /div fecha um filho, nao a barra. O script parou cedo, listou 4
controlos, e eu apresentei "nove viraram quatro" como MEDICAO.

E o grep que provava o contrario estava a dois comandos de distancia:

    grep -n "strip-theme-button" app/panel/panel.html
    -> L279, L658, L718, L727 -- e L715-730 e o bloco que explica a remocao.

ESCREVI UM PARSER EM VEZ DE CORRER UM GREP. E apresentei o resultado de um parser quebrado
como se fosse um numero. A regra: quando a ferramenta e nova, o resultado dela nao e um
numero -- e uma hipotese.

## O que isto muda na ordem dele

"restaura os botoes que tinha" -- agora eu sei que os botoes nao sairam: foram retirados por
ordem dele, com a razao escrita. Restaurar o theme-button na barra e desfazer uma decisao QUE
E DELE. O que eu nao posso e restaurar por cima de uma ordem dele sem lhe dizer que a ordem
existe.

E o que a barra tinha de errado era a LEGIBILIDADE -- corrigida em 9546cb9: tinta escura
sobre placa escura. O problema dele pode ser so esse.

## O que fica por confirmar

Se o transparency tambem foi removido por ordem dele. O commit fae207a chama-lhe "the Alt+C
solid-colour bug found and killed" e nao cita uma ordem -- mas eu ja errei uma vez nesta
materia hoje, portanto nao afirmo nada sem ler o bloco de comentario que provavelmente
existe no sitio onde ele estava.
