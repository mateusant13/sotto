# O ORACULO APANHOU AS 10 REGRAS MORTAS QUE EU CRIEI -- e eu parti o gerador a tentar
  cura-las

O dono mandou tirar o botao de transcript, e eu tirei tambem o ROTULO do HTML. O
zipc-designs-oracle.py (check I, que eu proprio pedi ha rodadas) apanhou a conta:

  FAIL I every selector matches a node of the real panel DOM
  397 selector(s), 10 that match NO node in panel.html
  DEAD: .history__label x10

Ou seja: os tres geradores (gen_themes.py, gen_zipc.py e os pd-*) continuavam a
emitir regras para um elemento que ja nao existe. E a mesma classe de defeito que este
repo ja mediu uma vez (~45 linhas mortas no panel.css) -- e que o gate existe para
apanhar. Desta vez apanhou, e de mim.

O QUE EU CONSEGUI:
  * gen_themes.py -- removido o bloco .history__label, e os 5 tema-N e o
    panel-designs.css regenerados. Os mortos la: 0.
  * O FIX DO E2 (o escuro no fundo, medido bot 0.140 -> 0.105) MANTIDO.

O QUE EU NAO CONSEGUI, E PARTI A TENTAR:
  * gen_zipc.py tem DUAS ocorrencias do selector, nao uma. Corrigi a primeira e o
    oraculo passou a dar DOIS falhos em vez de um -- o check H (o ficheiro e a saida
    do gerador) comecou a dar VERMELHO, porque a minha segunda correccao produziu
    Python que compila mas gera saida diferente.
  * REVERTIDO. gen_zipc.py voltou ao estado commitado e o zipc-panels.css foi
    regenerado (10 mortos la, como estava).

O FICA: 10 regras mortas no zipc-panels.css, MEDIDAS e NOMEADAS, e um trabalho de
meia hora: ha DUAS ocorrencias em gen_zipc.py (linha 591 e a que esta dentro do bloco
de estilos), e as duas tem de sair juntas -- uma de cada vez parte o check H.

E a licao, que e a regra N2 desta repo: corrigir um gerador exige ver TODAS as
ocorrencias antes de tocar em nenhuma. Corrigi metade, e o gate que prova que o
ficheiro e a saida do gerador foi o que me apanhou.
