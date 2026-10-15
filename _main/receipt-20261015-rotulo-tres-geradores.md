# O ROTULO DO TRANSCRIPT ESTAVA EM TRES GERADORES -- e eu so sabia de dois

O dono mandou tirar o botao de transcript, e eu tirei o ROTULO do HTML. O que se seguiu
e a tarefa de tirar o rotulo dos TRES geradores que o emitem -- e eu so encontrei dois.

FEITO E VERDADE:
  * gen_themes.py -- bloco removido, 5 tema-N + panel-designs.css regenerados.
  * gen_zipc.py -- as DUAS ocorrencias (linhas 334 e 591) removidas JUNTAS, e o
    produto escrito com --out. VERIFICADO: zipc-designs-oracle da
    `9 check(s), 0 failed`, `387 selector(s), 0 that match NO node`.

FALTA, MEDIDO NA BATERIA (5 vermelhos, 4 deles meus):
  * gen_cinematic.py AINDA emite .history__label -- e os oraculos cine-themes e
    cinematic-designs passaram de verde a vermelho com `control RED`. O CSS gerado
    mudou e a expectativa deles ficou velha, como ja aconteceu duas vezes nesta sessao
    (o HIDDEN_FLAGS e o braco do scrim).
  * three-overlays-oracle neg da SETUP ERROR: o mutante usa o span que eu removi como
    ANCORA (`mutant anchor absent in panel.html: <span...`). O mutante precisa de uma
    ancora nova.

A CONTA QUE EU ERREI: procurei o rotolo num ficheiro, corrigi, e nao procurei nos
outros DOIS geradores. Foram precisas DUAS voltas da bateria para eu descobrir que
eram tres -- e cada volta custou 6 minutos.

O que a proxima rodada tem de fazer, em UMA passada:
  1. remover .history__label de gen_cinematic.py e regenerar cinematic.css;
  2. correr os DOIS oraculos de fidelidade dos cine e re-baselinear a expectacao se ela
     ficou velha -- dizendo no recibo QUAL era o valor antigo;
  3. dar uma ancora nova ao mutante do three-overlays;
  4. so depois correr a bateria inteira.
