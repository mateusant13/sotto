# O ORFAO --size-chrome TEM LEITOR, E OS DOIS ORACULOS DOS CINE PASSAM

Na rodada passada a minha remocao do rotulo deixou um orfao: `--size-chrome` era
declarado nos 25 temas e a UNICA leitora era a regra `.history__label`. Os dois
oraculos de fidelidade dos cine apanharam-no -- e foi a segunda volta da bateria
que o mostrou, porque eu so corrigi dois dos tres geradores.

  cine-themes-oracle C1 ....... declared+unread: --size-chrome (x25)
  cinematic-designs-oracle C .. 53 token(s) declared; 1 with NO reader anywhere

A CURA, e nao foi apagar a declaracao: o token existe para o TAMANHO do texto de
chrome, e o `.captions__hint` -- a linha quieta por cima da legenda -- e exactamente
essa classe de texto e nao tinha tamanho proprio. Dei-lhe o leitor que faz sentido,
em vez de apagar um token que o dialogo de ajuste do dono conhece.

MEDIDO DEPOIS:
  cine-themes-oracle ......... 20 check(s), 0 failed, VERDICT PASS
  cinematic-designs-oracle .. 53 token(s) declared, 0 with NO reader, VERDICT PASS

E a conta que esta rodada ensina, que e a mesma de sempre: remover um elemento nao e
apagar uma linha, e fechar o que essa linha segurava. Aqui segurava um token, e o
token ficou orfao, e os gates apanharam. A regra N1 desta repo outra vez -- e eu
fui eu que a escrevi.
