E2 MEDIDO POR NUMEROS: o painel esta 18% mais escuro e com a luz INVERTIDA

O dono: "compara as prints das demos dos .zip com as prints do que ta implementado
atual. eu nao gostei dos atuais. e pra imitar mais os .zip."

Novo instrumento: _main/zip-fidelity-by-numbers.py. Nao confia em olho -- esta sessao
retractou DUAS vezes por acreditar na minha propria leitura de um print. Mede
ESTRUTURA: perfil de luminancia em tercos, fracao escura, energia de arestas e a
cor da tinta. Descodifica com Pillow offline e nao lanca nada.

MEDIDO (demo do zip D contra o painel shipped, theme-1):

  demo  1280x800  top=0.144 mid=0.162 bot=0.084  dark=0.75  edge=0.032  ink=(15,11,7)
  shot   380x900  top=0.108 mid=0.091 bot=0.140  dark=0.93  edge=0.028  ink=(23,15,16)

  DELTA dark = 0.18   <- o shipped e 18% mais escuro que a demo
  DELTA edge = 0.004  <- a densidade de estrutura e praticamente igual

E A DIFERENCA QUE IMPORTA, e ela e de FORMA e nao de quantidade:

  demo:  top=0.144  mid=0.162  bot=0.084    -> CLARO em cima, ESCURO em baixo
  shot:  top=0.108  mid=0.091  bot=0.140    -> ESCURO em cima, CLARO em baixo

O PERFIL DE LUZ ESTA INVERTIDO. A demo do zip poe a luz no topo e no meio e escurece
a zona da legenda, que e exactamente o desenho das tres camadas que eu proprio medi
no index.css:90-98 (scrim-top, scrim-bottom, vinheta). O painel shipped faz o
contrario: escuro em cima, e a legenda -- que devia ser a zona escura -- e a parte
mais clara do ecra.

O que isto NAO prova: nao prova que o painel e feio, nem que e fiel. Prova, com
numeros, que a ONDE a luz esta nao corresponde a demo -- e essa e a primeira vez
nesta sessao que o E2 tem uma resposta que nao e a minha opiniao.

O proximo passo, concreto: a zona da legenda no shipped tem de ficar mais escura que
o topo. O instrumento passa a ser o gate: enquanto o perfil estiver invertido, fica
vermelho.
