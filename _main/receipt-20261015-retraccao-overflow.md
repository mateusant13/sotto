# RETRACCAO 2: nao ha overflow -- eu li mal o print, e corrigi dois elementos a toa

Nas rodadas 3 e 4 reportei ao dono um defeito: a linha em formacao transbordava pela
direita e as palavras ficavam cortadas. Apliquei duas correccoes, uma em
.captions__body e outra em #caption-float .caption-float__line.

A MEDICAO, nas duas vezes:
  shots3  62 859 B  sha256 1c1dae1aae3a43c8...
  shots4  62 859 B  sha256 1c1dae1aae3a43c8...  (depois de .captions__body)
  shots5  62 859 B  sha256 1c1dae1aae3a43c8...  (depois de #caption-float)

Dois prints identicos, e porque: OLHANDO BEM, o texto nao esta cortado -- esta em DUAS
LINHAS. A LEGENDA NASCE ENQUANTO... na primeira e FRASE AINDA ESTA EM FORMA na
segunda, as duas completas e visiveis. O que eu tomei por corte era a quebra de linha.
Nao havia defeito nenhum.

E a segunda prova: se uma daquelas correccoes tivesse acertado no elemento certo, o
render TINHA de mudar -- e nao mudou nenhuma das duas. Duas correccoes sem efeito e o
sinal de que nao havia nada a corrigir.

O QUE FICA FEITO, apesar de nao haver defeito: as duas regras acrescentadas sao
inofensivas e defensaveis -- max-width 100% e overflow-x hidden no elemento que segura
a linha sao a coisa certa a ter, e ficam com a medicao que as justifica.

E A CONTAGEM: esta e a SEGUNDA retracao visual desta sessao. A primeira foi o bloco
negro (afirmei ser historico sem limite, e tem limite de 200 por desenho). Nas duas eu
disse ao dono, com numeros na mao, que havia um defeito -- e nao havia.

A licao, e ela e a regra do goal: OLHAR nao basta. E preciso olhar e nao concluir.
Um print que parece mostrar um corte pode estar a mostrar uma quebra de linha, e so a
comparacao de bytes separa as duas.
