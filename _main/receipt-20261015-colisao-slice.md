PARTI O GERADOR COM UM SLICE, E O RESTAURO APAGOU O TRABALHO DA LANE

O que se passou, medido:

  * Estava a reverter a minha propria edicao em gen_cinematic.py e fi-lo com um slice
    em JavaScript. Procurei o anchor com 12 espacos de indentacao; a linha real tem 8.
    O indexOf devolveu -1. O slice(-1) ficou so com o ULTIMO CARACTER do ficheiro.
  * O gen_cinematic.py ficou TRUNCADO em 1434 linhas, com a cauda de main() apagada:
    a emissao do CSS, os self-checks, a escrita dos ficheiros, as licencas e o
    if __name__ desapareceram. py_compile passava -- uma funcao truncada e sintatica --
    mas correr o gerador nao emitia nada. Era exactamente o defeito da regra N2.
  * A lane D viu o ficheiro truncar e reportou uma COLISAO com outro escritor. Nao havia
    outro escritor: era eu, a partir o ficheiro que ela tinha aberto.

O QUE FIZ:
  git checkout -- _main/_design-lane/gen_cinematic.py    RESTORE=0
  py_compile                                             COMPILE=0
  corre e regenera o CSS                                 sem erro

ESTADO MEDIDO AGORA: gen_cinematic.py 1600 linhas, 86 871 B, if __name__ presente,
compila e corre. cinematic.css com 27 scrims planos e 0 camadas do zip -- o estado
consistente anterior a tudo. Nada ficou partido.

CONSEQUENCIA, E A PEDIRO DESCULPA: o checkout restaurou a versao do HEAD, e a edicao 1
da lane D (theme_css, linhas 810-840) foi PERDIDA. Aviso-lhe por mensagem para a
refazer, e com o que eu medi da estrutura para ela nao repetir.

O QUE A ESTRUTURA ENSINOU, medido: o gerador emite a regra .panel por tema em DOIS
sitios -- a linha ~1412 e o bloco t[css] do tema -- e o segundo vem depois no ficheiro e
ganha. Mudei so o primeiro e o CSS ficou com 15 temas curados e 12 planos: o segundo
sitio repoz o plano. Mudar um sitio so cria uma regra DUPLICADA e nao cura nada. A cura
tem de entrar nos dois, ou o primeiro sitio tem de passar a ser a unica fonte.

E A REGRA QUE FICOU: dois escritores no mesmo ficheiro sem nenhum a saber. Antes de eu
voltar a tocar em gen_cinematic.py, digo a lane. Ela fica de fazer o mesmo.