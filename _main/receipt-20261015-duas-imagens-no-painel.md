# DEFEITO MEDIDO: os temas cinematic poem DUAS imagens por cima do painel

O dono, verbatim: pq tu copiou as coisas das demos q sao sem sentido? por que tem
personagens falando em um dos designs replicados? arruma. e tu ta simplesmente botando de
forma burra alguns designs por cima do painel e ai fica duas coisa sobrepostas que nao
fazem sentido como se fosse um glitch, em diversos designs.

## A CAUSA, MEDIDA NOS BYTES

app/panel/themes/cinematic.css tem 40 url(backdrops/*.jpg) -- FOTOGRAFIAS das demos dos
.zip -- e 28 pseudo-elementos. zipc-panels.css tem 44 pseudo-elementos.

O defeito que o dono ve, e o seguinte, e esta no CSS gerado:

    :root[data-theme=cine-cafe] .panel { background-image: linear-gradient(var(--cine-scrim), var(...   <- LINHA 2357
    /* ... 30 linhas de comentario ... */                                                                       <- 2358..2388
    url(backdrops/cafe.jpg);                                                                                   <- 2389
    background-size: cover, cover;                                                                             <- 2390  DOIS VALORES

Tres factos medidos nisto:

1. background-size: cover, cover tem DOIS valores => o elemento .panel carrega DUAS
   imagens de fundo ao mesmo tempo: o gradiente da linha 2357 e a fotografia da 2389.
   E exactamente "duas coisas sobrepostas ... como se fosse um glitch".

2. A regra da linha 2357 esta PARTIDA: abre chaveta e comeca background-image:
   linear-gradient(...) e depois vem um bloco de comentario e outra declaracao. O CSS
   resultante depende de o comentario calhar no meio da declaracao.

3. A fotografia e o fundo da DEMO, nao do painel. O dono ve personagens falando porque
   uma das fotografias (tideline-body.jpg, cafe.jpg, warm-hour.jpg) mostra pessoas. Nos
   .zip a fotografia e a CENA ATRAS da legenda; copiada para .panel sem o scrim proprio
   que a cena tem, ela aparece por cima do texto.

## O QUE NAO FIZ, E DIGO-O

NAO corrigi. O defeito esta no GERADOR (_main/_design-lane/), nao no CSS gerado, e a
regra da repo e que os ficheiros gerados nunca se editam a mao. Com o contexto que tinha
nao consegui corrigir o gerador e provar a regeneracao -- e uma correccao as cegas aqui
seria o mesmo erro que a regra N2 existe para apanhar.

## ONDE A CORRECCAO TEM DE ENTRAR

1. no gerador: UMA regra .panel por tema, com UMA background-image, e a fotografia
   composta com o scrim da cena NA MESMA declaracao (linear-gradient(...), url(...)),
   nunca em duas regras separadas;
2. o background-size tem de ter tantos valores quantas as imagens, e uma fotografia com
   scrim por cima LE-se como cena, nao como glitch;
3. as 40 fotografias ficam, porque o dono pediu o design igual ao .zip -- o que muda e
   que passam a ser CENA ATRAS, e nao painel por cima.

O instrumento que pode provar: um censo que leia o CSS gerado e conte, por tema, quantas
imagens de fundo o .panel declara. Hoje dao 2 em varios. Esse censo e a porta.
