# TO BE ANSWERED BY OWNER -- armadura A da OD S1

Cada item aqui e algo que a minha loja sintetica NAO conseguiu decidir sozinha, e onde eu podia ter escolhido um numero ou uma regra por palpite. Nao escolhi. Cada item traz o que esta escrito, o que eu fiz na ausencia de resposta, e o que muda quando o dono responde. Data: 2026-10-10.

## Q1. Duas janelas ASR podem sobrepor-se, e dois CLIPES podem?

O que esta escrito: specs/02-asr.md:165 diz que PAD_S e 0.10 de cada lado e explica "this is why recorded segments overlap". O produto, pela letra do proprio spec, ESPERA sobreposicao.
O que eu fiz: tratei a sobreposicao acima de PAD_S como VERMELHO (C01) em qualquer sujeito, clips ou segmentos.
O que a resposta muda: se o produto assume sobreposicao entre clipes tambem, o C01 passa a ser ruido em cada canto deste produto e tem de levar uma tolerancia maior ou sair do caminho dos clips. Se so as janelas ASR se sobrepoem, o C01 fica como esta e passa a procurar sobreposicao entre clipes que a sobreposicao de ASR nao explica.

## Q2. Dois clipes de uma sequencia tem de ser contiguos?

O que esta escrito: nada encontrado. schema.sql:65-68 guarda o start_ms da janela ASR na tabela segment, nunca na tabela video.
O que eu fiz: reporto o vao entre clips como INFO-GAP e nao como VERMELHO.
O que a resposta muda: se houver regra de contiguidade, ela precisa da tabela segment para ser testavel, e o instrumento passa a precisar de a ler.

## Q3. Um ficheiro importado tem fonte de duracao alem da db e do contentor?

O que esta escrito: o video.duration_ms vem do indice; o contentor tem o seu moov.
O que eu fiz: para linhas estrangeiras so existem os ranks 3 (db) e 4 (contentor).
O que a resposta muda: se a importacao trouxer a sua propria duracao, falta-lhe um rank acima de 4, e o instrumento tem de o saber para nao preferir a db.

## Q4. O moov de um ficheiro importado traz um creation_time utilizavel?

O que esta escrito: o escritor deste produto escreve 0 literal em mvhd/tkhd/mdhd (mp4_writer.cpp:257/272/293), logo para clips nossos o campo nao serve.
O que eu fiz: nao uso creation_time para nada; imprimo um censo dos campos em zero.
O que a resposta muda: num importado o campo pode vir preenchido (epoca 1904). Se o produto quiser usa-lo, precisa de uma regra que nao confunda 0 com 1904 -- e o meu censo continua a ser necessario para os nossos.

## Q5. Como e que o indice guarda um caminho movido?

O que esta escrito: video.content_key e UNIQUE (schema.sql:44). A identidade e o sha256 do ficheiro inteiro (schema.sql:4), nunca o caminho.
O que eu fiz (medido): tentei duas linhas para a mesma identidade e a segunda INSERT falhou com IntegrityError; a unica forma representavel de "caminho movido" e uma linha com um caminho obsoleto (missing=1).
O que a resposta muda: se o produto algum dia aceitar dois caminhos para uma identidade, o C03 PATH MOVED muda de forma e eu preciso de uma segunda coluna, nao de uma segunda linha.

## Q6. Quantos ms de tolerancia na comparacao de duracoes?

O que esta escrito: nada encontrado.
O que eu fiz: DUR_TOLERANCE_MS = 1, escolhido por esta lane, e rotulado como escolhido no cabecalho de cada saida.
O que a resposta muda: com 1 ms, um clip de 5 s e o seu contentor batem certo so se concordarem ao milissegundo. Se o produto truncar milissegundos por desenho, a tolerancia tem de subir, ou o C07/C08 ficam permanentemente VERMELHO.

## Q7. A arvore drifted: as citacoes de linha valem o que?

O que esta escrito: nada -- e uma pergunta sobre este repo. A arvore _moved/aireplay divergiu de HEAD esta semana (outras lanes trabalharam nela).
O que eu fiz: reli cada ficheiro citado antes de escrever o relatorio e datai a leitura (2026-10-10).
O que a resposta muda: nada no instrumento; muda a confianca que o dono poe nos numeros de linha. Se quiser citacoes estaveis, diga-me qual a revisao que e a de referencia.

---

# ARMA B - o que a loja REAL nao conseguiu decidir (2026-10-10)

PA: H:/sotto/_moved/aireplay/_main/_lane22-run (10 stores, 99 clips, 98 key.json, 0 .db).
POPULACAO: 99 media mp4 + 98 key.json em 10 directorios de store; 12 ficheiros de run;
3 mp4 de controle FORA da loja. JANELA: leitura em 2026-10-10T04:15:34Z .. 04:15:35Z
(runs), verificador 2026-10-10T04:57:08Z .. 04:57:10Z; o mtime mais novo da POPULACAO e
2026-10-08T00:04:21Z; 0 mtimes mudaram. O braco B e o PRIMEIRO que correu sobre a loja
verdadeira - os Q1..Q7 acima sao da armadura sintetica e continuavam por responder.
Artefactos: I:/cc-tmp/ods1-armB/ (armB-report.md/.json, ods1_armB.py, check_armB.py,
armB_census.py/.json, armB-clip-classification.json, check-armB-output.json,
armB-run-log.json, DIFF-armA-vs-armB.txt). Os 12 outputs por store ficam em
I:/cc-tmp/ods1-armB/runs/ (~3.3 MB) e NAO sao aterrados: o instrumento aterrado
reprodu-los de novo, e o espelho I:/cc-tmp/ods1-armB/runs-mirror/ e byte-identico.

Duas medicoes que mudam o que os Q1..Q7 significam:

- 99 de 99 contentores NAO dao duracao (94 R-BOX-TRUNCATED, 5 R-BOX-UNKNOWN, que terminam
  em 98 R-NO-MOOV + 1 R-NO-FTYP). Ou seja o rank 4 (contentor) do Q3 NAO existe para os
  nossos clips: a resposta ao Q3 fica provisoria enquanto o writer nao escrever moov.
- 95 de 95 chaves dao um intervalo (ended_at_s - started_at_s) que CONTRADIZ o seu proprio
  duration_ms por mais de 1 ms: intervalo minimo 1800066.681 ms, maximo 86400625.539 ms,
  contra duration_ms de 1000 a 30000. Exemplo:
  _lane22-run/armA-store/clips/2026/10/07/20261007T130417Z-0013/key.json, intervalo
  39600716.265 ms contra duration_ms 30000. O instrumento nao tem classe para isto (C05 so
  dispara em intervalo menor ou igual a 0; C08 precisa de uma duracao de contentor) -
  registado como LACUNA, nao como verde.

## P1. A contradicao da duracao e do writer ou do contrato da chave?

O que esta escrito: nada. duration_ms tem um nome que diz milissegundos.
O que eu fiz: NAO corrigi nada. A classe C10 nao existe; a contradicao esta registada como
LACUNA do instrumento com PATH + POPULACAO (95 de 95) + JANELA.
O que a resposta muda: com uma resposta digo qual dos dois lados mente - se e o writer que
escreve duration_ms em segundos, ou se e o contrato da chave que mudou - e a LACUNA passa
a classe. Pergunta directa: duration_ms deve estar em ms ou em segundos?

## P2. Criar C10 KEY-SELF-DURATION, ou isso e papel do C08 alargado?

O que esta escrito: C08 precisa de uma duracao de contentor para comparar.
O que eu fiz: deixei 95 de 95 chaves passarem sem classe nenhuma.
O que a resposta muda: se a chave se contradiz a si propria, isso e um defeito do lado do
clip e precisa de aparecer numa contagem. Hoje nao aparece em nenhuma.

## P3. O ODS deve distinguir "nao ha indice" de "o indice nunca viu este clip"?

O que esta escrito: nada. O C03 como esta dispara uma vez por clip SO porque ha 0 .db nos
10 stores (0 de 99 directorios de clip).
O que eu fiz: reportei C03 tal como esta - 95 chaves committed + 2 com erro explicito
(uma nao-JSON, uma layout_version=99) + 1 clip sem key.json.
O que a resposta muda: o C03 hoje conta a ausencia do INDICE, nao do clip. Sem a distincao,
a contagem enche-se com uma loja que nunca teve indice. Isto estende o Q1/Q2 da armadura A,
que saiam do caso sintetico.

## P4. As sobreposicoes de 3600 s a 82800 s sao de relogios reescritos, ou o writer
   reutiliza started_at?

O que esta escrito: nada nesta repo. 621 pares C01 medidos numa janela continua de 200.045 s
a 82800.275 s; 9 das 10 stores tem sobreposicoes nessa gama.
O que eu fiz: NAO escolhi nenhuma das duas hipoteses - (a) os relogios destes clips foram
reescritos por outras lanes esta semana; (b) um writer que reutiliza um started_at antigo.
O que a resposta muda: se for (a), a loja esta suja e o ODS corre outra vez depois de as
lanes pararem; se for (b), o writer tem um defeito de started_at e a captura estara a
mentir sobre a ordem. Isto e tambem a resposta do Q2 da armadura A, agora com dados.

## P5. Os 3 mp4 de controle foram escritos pelo mesmo writer?

O que esta escrito: os 3 tem moov e o instrumento le-lhes a duracao (0 de 3 recusados);
estao FORA da populacao da loja.
O que eu fiz: usei-os como controle de que a recusa R-NO-MOOV e do sujeito, nao do leitor.
Nao tirei conclusao sobre o writer.
O que a resposta muda: se forem do mesmo writer, o que muda entre eles e os 99 media da
loja e justamente a duracao que a loja nao tem - e o writer pode ter sido corrigido a meio
da sessao. Se nao forem, o controle nao prova o leitor e nada mais.

## P6 (novo, da armadura B). O Alt+Shift+F10 e desta sessao?

Nada a ver com a loja: a lane E reportou que nao ha RegisterHotKey nem VK_* em
src/engine/*.py e nao conseguiu dizer quem e dono do Alt+Shift+F10. Fica registado aqui
para o dono nao responder duas vezes. Se o atalho e do painel (app/panel/), a engine nunca
o deve registar.

## PROCEDENCIA DESTA SECCAO

Cada numero acima traz PATH + POPULACAO + JANELA + ISO e foi lido do disco em 2026-10-10.
Nada foi adicionado ao git por este braco; os artefactos ficam em I:/cc-tmp/ods1-armB/ e o
pai aterra-os no pai com caminhos explicitos. Nada em G:. TMPDIR = I:\cc-tmp.
