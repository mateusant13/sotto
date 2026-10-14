# O ULTIMO VERMELHO: DIAGNOSTICADO, NAO FECHADO

2026-10-14. A bateria da 88/9, falha em preflight-refusal-visible-oracle.py (linha G5).

## O que passa e o que falha

Armas 1 a 3 passam: o --bogus-flag devolve rc 2 e o chamador ve o texto do argparse; o --help
devolve rc 0; o --check-args devolve rc 0 sem recibo. A arm 4 e o CONTROLO, e falha.

## Os dois candidatos a controlo, e porque nenhum serve

1. Fixar uma revisao do git. O proprio oraculo detecta: the control revision 3e85202 already
   carries the cure. E git log -S nao encontra nenhum commit que INTRODUZIU a cura -- so
   devolve 5ffeefc, o commit de durabilidade que trouxe a arvore inteira para o indice.
   Ou seja: o run.cmd viveu FORA do indice quase toda a sua vida, e um pino por revisao nao
   consegue expressar antes-da-cura para um ficheiro que nao estava rastreado.

2. O ficheiro embarcido _main/run-cmd-prefix-20261006.cmd, que o outro oraculo usa com
   sucesso. Aqui devolve rc 0 em vez de 2: e de ANTES do pre-voo existir, portanto nao
   recusa nada. Serve ao oraculo que so mede o codigo de saida; nao serve a este, que exige
   a recusa do argparse.

## As minhas cinco tentativas, e todas pioraram

1. Apontar para o ficheiro embarcido: could not read the pre-fix wrapper file.
2. Construir o controlo a mao revertendo a cura: devolveu rc 4 (HANG), nao 2 -- revertei o
   bloco errado.
3. Trocar o marcador por uma verificacao de forma: o controlo correu e devolveu 0.
4. Deixei uma referencia orfa (show.stdout) apos remover a variavel: NameError.
5. Corrigi a orfa: devolveu 0 outra vez.

Reverti tudo; o oraculo esta limpo no HEAD.

## O que falta -- uma coisa so

O controlo certo e o run.cmd de hoje com a cura revertida DE FORMA COMPLETA: manter o
--check-args e o bloco que traduz o rc em 2, e remover apenas a captura do stderr, o echo da
recusa e o log-append. A minha reversao a mao removeu o bloco errado e foi por isso que deu 4.
Faz-se com a ferramenta edit sobre as linhas exactas da regiao da cura, e prova-se pelo
resultado do braco (rc 2 com zero B de texto), nao pela minha leitura.

## O que nao afirmo

Nao fechei o vermelho: a bateria continua 88/9. Nenhum dos fixes de P0 posteriores a ultima
bateria verde esta confirmado por ela, e isso ficou escrito nos commits.
