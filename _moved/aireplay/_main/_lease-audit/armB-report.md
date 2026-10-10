# ARM B -- ODS-1 SOBRE OS CLIPS REAIS (LEITURA APENAS)

POPULACAO LIDA (PATH): 10 stores, todos em H:/sotto/_moved/aireplay/_main/_lane22-run
JANELA DA LEITURA: as 10 corridas do instrumento correram de 2026-10-10T04:15:34.810101+00:00 a 2026-10-10T04:15:35.870011+00:00;
  verificador independente 2026-10-10T04:57:08Z a 2026-10-10T04:57:10Z.
  mtime mais recente na populacao (layout.json mais novo): 2026-10-08T00:04:21Z.
FICHEIROS DE PROVA: I:/cc-tmp/ods1-armB/ (runs/, runs-mirror/, armB-run-log.json,
  armB_census.json, check-armB-output.json, check_armB.py, ods1_armB.py,
  DIFF-armA-vs-armB.txt, armB-clip-classification.json).

Regra que segui: SO LEITURA. Nenhum clip, key.json ou linha de db foi escrito, movido,
renomeado ou corrigido. Onde um relogio ou duracao parece errado, ficou REGISTADO como
medida mais UNKNOWN, nunca corrigido. 0 ficheiros da populacao mudaram de mtime durante
todo o Arm B (medido pelo verificador). Nada em G:. Nada de git add/commit/push (a arvore
continua com ?? _main/_lease-audit/). Sem build, sem dispositivo de audio, sem rede, sem
janela visivel.

## (a) O QUE CORREU

1. INSTRUMENTO: I:/cc-tmp/ods1-armB/ods1_armB.py (= ods1.py mais 5 patches; diff completo
   em DIFF-armA-vs-armB.txt). layout.py usado como contrato: H:/sotto/_moved/aireplay/src/storage/layout.py,
   sha256 fe02e34b9a6339c763e193323a6e9a8e970ca4f15fdf99127543a6b43830ebd6.
2. 10 CORRIDAS, uma por store, com --arm b: o guard E-ROOT-INSIDE-REPO passa a aviso LOUD
   ("E-ROOT-INSIDE-REPO NOT APPLIED (--arm b, authorised product-tree read)"), registado no
   stdout e no JSON (guard_note). O verificador confirma: 1 nota de guard distinct em 10 runs.
   As 10 saidas tem rc=1 por desenho (ha encontros), 7/7 auto-auditoria verde em cada uma
   (70 linhas no total, 0 vermelhas).
3. 2 CORRIDAS DUPLICADAS sobre o mesmo root H (mirror-arme, mirror-armc) como controlo de
   determinismo: contagens identicas. Total 12 ficheiros em runs/.
4. 10 CORRIDAS SOBRE O ESPELHO I:/cc-tmp/f13-2/jprod/_lane22-run (mirror dos 10 stores):
   contagens identicas as de H em 10 de 10 stores; a arvore do espelho e byte-identica
   (hash de arvore igual, 386 ficheiros).
5. VERIFICADOR INDEPENDENTE: I:/cc-tmp/ods1-armB/check_armB.py -- segundo leitor com walk,
   parser de caixas e prioridade proprios, sem partilhar codigo com o instrumento.
   Resultado: 24 verificacoes verdes, 1 vermelha (a contradicao de (b)), 1 medida registada.

CONTAGENS TOTAIS dos 10 runs (POPULACAO = os 10 stores H acima):
99 linhas emitidas (uma por clip), 0 linhas de db, 0 chaves de conteudo duplicadas,
818 encontros (621 C01 + 95 C03 + 102 REFUSAL), 70 linhas de auditoria, 0 vermelhas.
Cada clip tem clip_id unico DENTRO do seu store, mas os clip_ids REPETEM entre stores
(a lane recriou a populacao varias vezes): qualquer conclusao e por store, nunca global.

CENSO DA POPULACAO (medido, 99 clip.mp4): 94 com caixa truncada, 5 com ftyp mais uma
caixa de tamanho zero e sem moov, 1 com 4 bytes. 98 key.json, 89 thumb.jpg,
89 transcript.json, 1 .partial, 10 layout.json. 0 ficheiros .db em qualquer store.

## (b) VERMELHOS POR CLIP (valores medidos)

Tabela por store (PATH = H:/sotto/_moved/aireplay/_main/_lane22-run/<store>). C01 = pares de
intervalos que se sobrepoe; a sobreposicao vem de key ended_at_s (rank 2).

  store                                  clips  C01   sobrepos. min/max/media (s)   C03  REFUSAL
  armA-store                             11     55    3600.716 / 36000.716 / 14400.778  11   11
  armB-store                             12     66    7200.189 / 79200.189 / 31200.291  12   12
  armC-store                             4      6     200.045 / 3600.045 / 1300.052      3    5
  armE-store                             1      0     --                               1    1
  layout-selftest/layout-root            7      21    39449.206 / 57449.285 / 45449.233 6    8
  negctl-D0-work/armA-store             11     55    3600.780 / 36000.780 / 14400.833  11   11
  negctl-LOUD-ALARM-work/armB-store     12     66    7200.512 / 79200.512 / 31200.573  12   12
  negctl-RECONCILE-PARTIAL-work/armC-store 5   10    200.968 / 3600.968 / 1160.976       3    6
  negctl-RETENTION-BYTES-work/armA-store 24   276   3600.275 / 82800.275 / 30000.440   24   24
  negctl-WRITE-ADMISSION-work/armB-store 12   66    7200.046 / 79200.046 / 31200.107   12   12
  TOTAL                                  99    621                                             95  102

VERMELHO 1 -- 99 de 99 clips: o contentor nao da duracao (REFUSAL).
  94 clips: R-BOX-TRUNCATED com terminal R-NO-MOOV. Exemplo medido,
  H:/sotto/_moved/aireplay/_main/_lane22-run/armA-store/clips/2026/10/07/20261007T130417Z-0013/clip.mp4:
  uma caixa de topo ao byte 24 declara 2762319527 bytes e o ficheiro so tem 40948, ou
  seja a caixa pede mais bytes do que o mp4 tem -> nao ha moov, logo nao ha tabela de
  amostras donde ler duracao.
  5 clips: R-BOX-UNKNOWN com terminal R-NO-MOOV (ftyp valido, depois uma caixa de tamanho
  zero, limpa ate ao fim, sem moov):
    armC-store/20261007T233419Z-0002, armC-store/20261008T000059Z-0006,
    negctl-RECONCILE-PARTIAL-work/armC-store/20261007T233421Z-0002,
    negctl-RECONCILE-PARTIAL-work/armC-store/20261007T234421Z-0003,
    negctl-RECONCILE-PARTIAL-work/armC-store/20261008T000101Z-0006.
  1 clip (4 bytes) termina em R-NO-FTYP: layout-selftest/layout-root/clips/2026/01/01/20260101T000000Z-0001/clip.mp4.
  CONTROLO: 3 mp4 reais fora de qualquer store (H:/sotto/_moved/aireplay/_main/_census09-ctl/ctl-normal.mp4,
  ctl-faststart.mp4, ctl-frag.mp4) TEM moov e 0 de 3 foram recusados. O instrumento le um
  moov quando ele existe; a populacao dos stores e que nao o tem.

VERMELHO 2 -- 95 de 99 clips: C03 (nao ha linha de video que nomeie o clip).
  Isto nao e uma medida de reconciliation par a par: ha 0 ficheiros .db nos 10 stores
  (0 de 99 directorios de clip). O instrumento nao tem linha nenhuma para comparar.
  Os 4 clips parcial-nao-commitados nao disparam C03 (verdict partial-uncommitted).

VERMELHO 3 (A NO CONTRADICAO, MEDIDA PELA PRIMEIRA VEZ) -- 95 de 95 chaves: o intervalo da
  propria chave contradiz o duration_ms da propria chave.
  Medido em check_armB.py (segundo leitor, leitura apenas): intervalo = ended_at_s -
  started_at_s, comparado com duration_ms da MESMA chave, tolerancia DUR_TOL_MS=1.
  95 de 95 chaves parsed falham. Amplitude do intervalo: min 1800066.681 ms (30.0 min),
  max 86400625.539 ms (24.0 h). Distribuicao de duration_ms (n=95): 30000 x 83, 1000 x 7,
  1001 x 1, 1002 x 1, 1003 x 1, 1004 x 1, 1005 x 1.
  Por store (intervalos em ms, duration_ms): arma-store 11 chaves {30000 x 11}
  3600924-39600716; armb-store 12 {30000 x 12} 7200592-86400189; armc-store 3 {1000 x 3}
  1800067-7200056; arme-store 1 {30000 x 1} 86400625.539; layout-selftest/layout-root 6
  {1000,1001,1002,1003,1004,1005 x 1 cada} 39449206-57449285.
  Exemplo PATH: H:/sotto/_moved/aireplay/_main/_lane22-run/armA-store/clips/2026/10/07/20261007T130417Z-0013/key.json:
  started_at_s 1791378257.0, ended_at_s 1791417857.716265 (intervalo 39600716.265 ms),
  duration_ms 30000. O started_at_s dessa chave iguala o clip_id (rank 1) em 95 de 95
  chaves, 0 desacordos. O content_key iguala o sha256 do seu clip.mp4 em 95 de 95.
  Isto NAO foi corrigido: ficou registado como medida mais UNKNOWN.

  Porque e que isto e CONTRADICAO e nao leitura velha ou copiada (controlo medido):
  key mtime_ns e size_bytes coincidem com o clip.mp4 real em 95 de 95 chaves;
  committed_at_s - ended_at_s = 0.0 em 25 chaves e >0 em 70, max |delta| 0.001549959 s
  (ou seja ended_at_s e o instante de commit e o mtime real do ficheiro falam da mesma
  operacao), enquanto so o duration_ms fala em segundos (1 s a 30 s).

  LACUNA DO INSTRUMENTO (nao a pintei de verde): o instrumento nao tem classe para isto.
  C05 so dispara quando o intervalo e <= 0, e os 95 intervalos sao positivos. C08 precisa de
  uma duracao do contentor e nao ha nenhuma (99 de 99 recusam). Proponho uma classe nova
  (nome a confirmar pelo dono; sugestao C10 KEY-SELF-DURATION) para: o intervalo da chave
  contradiz o duration_ms da propria chave. Hoje o instrumento ve 818 encontros e nao ve
  este, o unico que envolve 95 de 95 chaves.

VERMELHO 4 -- 3 chaves com erro explicito (o instrumento recusou, nao inventou):
  armC-store/clips/2026/10/08/20261008T000059Z-0006/key.json -- nao e JSON
    ("Expecting property name enclosed in double quotes: line 1 column 3");
  negctl-RECONCILE-PARTIAL-work/armC-store/clips/2026/10/08/20261008T000101Z-0006/key.json -- nao e JSON (mesmo erro);
  layout-selftest/layout-root/clips/2026/01/01/20260101T000000Z-0001/key.json -- layout_version 99;
    esta build nao tem regra de leitura (conhecidas: [1]). Recusar bate ler v2 como v1.
  Mais 1 clip sem chave utilizavel, sem erro possivel:
  negctl-RECONCILE-PARTIAL-work/armC-store/clips/2026/10/07/20261007T234421Z-0003 (key.json ausente;
    verdict partial-uncommitted, o fim veio do mtime do media, rank 5).
  MEDIDO, nao hipotese: os 4 clips com verdict partial-uncommitted da populacao sao
  EXACTAMENTE estes 4 sem chave utilizavel
  (verdicts das 99 linhas: committed 95, partial-uncommitted 4). A causa dessa correlacao
  e UNKNOWN; nao corrigi.

C06 (vazio ASR vs clip): FICA GAP. NAO foi reproduzido neste braco -- o Arm B nao leu ASR.
  schema.sql:65-68 poem o ASR start_ms em segment, nao em video, e eu nao li segment neste
  braco. Se uma lane o reproduzir, que diga com que dados; aqui continua GAP, nao verde.

## (c) O QUE E UNKNOWN (nunca escrevi zero nem verde onde so ha ausencia de medida)

1. A DURACAO REAL de cada clip: UNKNOWN. O contentor nao da (94 R-BOX-TRUNCATED +
   5 R-BOX-UNKNOWN). O writer escreve literal 0 nos campos de tempo do mp4
   (mp4_writer.cpp:257, :272, :293), pelo que um selo mp4 seria UNKNOWN, nao uma data.
2. QUEM tem razao na contradicao (b)/vermelho3: UNKNOWN. Se e o writer que escreve
   duration_ms em segundos, ou se e o contrato da chave que mudou, nao da para saber
   lendo o disco. Nao corrigi nada.
3. C02 (identidade identica), C02-CONTENT-KEY-LIE: GAP. Nao ha db para comparar.
4. C04 (zero-epoch): GAP. 0 campos com epoca zero encontrados nesta populacao -- isso e
   ausencia de medida, nao prova de ausencia.
5. C07 (declarado vs decoded): GAP. Sem moov nao ha decoded para comparar.
6. C08 (duration-source mismatch): GAP hoje, exactamente porque a duracao do contentor
   nao existe. E por isso que vermelho3 fica sem classe (ver (b)).
7. C09 / C2TRAK / R-DATA-QUALITY / INFO-GAP: sem alvos medidos nesta populacao.
8. PORQUE ha sobreposicoes de 3600 s a 82800 s em 9 de 10 stores: UNKNOWN. Duas hipoteses
   nao medidas: (a) os relogios destes clips foram reescritos por outras lanes esta semana
   (logo o que li pode nao ser o que a lane de captura escreveu); (b) um writer que reutiliza
   um started_at antigo. NAO escolhi nenhuma.
9. Se os 3 mp4 de controle (com moov) representam o writer correcto: UNKNOWN. Eles estao
   FORA da populacao e o instrumento le-lhes o moov bem (0 de 3 recusados).
10. O estado REAL no momento da captura de cada clip: UNKNOWN. So li o que esta em disco
    agora, com a JANELA acima.

O que o verificador confirma como VERDE (24 de 25 verificacoes; a vermelha e vermelho3):
10 stores e 99 clips; 0 db; 0 de 99 media com moov; 4 clips sem chave utilizavel,
registados; 95 chaves com started_at_s == clip_id; 95 content_key == sha256 do media;
95 chaves com mtime_ns e size_bytes iguais ao media; 0 stores com varios clips a partilhar
um unico instante de fim; 12 ficheiros de run parseiam; 1 run por store; todo o clip tem
linha; as linhas do instrumento concordam com a leitura independente (0 desacordos);
70 linhas de auto-auditoria (7 x 10) todas verdes; 1 nota de guard; os 10 runs sairam 1 por
desenho; C01 621 pares do instrumento == 621 pares do leitor, por store, 0 diferencas;
o espelho I: e byte-identico e reproduz contagens identicas em 10 de 10 stores;
3 mp4 de controle fora da loja nao recusados; 0 mtimes mudaram na populacao.

VOCABULARIO DE RECUSA mantido (cada um vira UNKNOWN, nunca 0). Medido: 13 strings R-
distintas em I:/cc-tmp/ods1-armB/ods1_armB.py -- R-BOX-TRUNCATED, R-BOX-UNKNOWN,
R-BOX-VERSION, R-DURATION-UNKNOWN, R-KEY-UNREADABLE, R-NO-DURATION, R-NO-FTYP,
R-NO-MOOV, R-NO-TIMESCALE, R-UNREADABLE, R-VERSION, R-WRONG-DIR, R-DATA-QUALITY.
Os que dispararam nesta populacao: R-BOX-TRUNCATED 94, R-BOX-UNKNOWN 5; terminais
R-NO-MOOV 98 e R-NO-FTYP 1; R-KEY-UNREADABLE 3. Os restantes nao tiveram alvo aqui.
Auto-auditoria 7/7 verde em cada um dos 10 runs (70 linhas).

## (d) PERGUNTAS AO DONO

P1. Vermelho3 e do writer ou do contrato da chave? Ou seja: duration_ms deve estar em ms
    (como o nome diz) ou em segundos? Com uma resposta eu digo qual dos dois lados mente,
    mas nao corrijo nada sem o dono mandar.
P2. Criar a classe nova C10 KEY-SELF-DURATION (intervalo da chave vs duration_ms da propria
    chave) ou isso e papel de C08 alargado? Hoje 95 de 95 chaves passam sem classe.
P3. O C03 como esta dispara uma vez por clip so porque nao ha NENHUM db nos 10 stores
    (0 de 99 directorios). Isso e informacao sobre o indice, nao sobre o clip: deve o ODS
    distinguir "nao ha indice" de "o indice nao viu este clip"?
P4. As sobreposicoes de 3600 s a 82800 s sao um artifact de relogios reescritos por outras
    lanes esta semana, ou o writer reutiliza started_at? Nao ha medida que decida.
P5. Os 3 mp4 de controle (com moov, fora da loja) foram escritos pelo mesmo writer? Se sim,
    o que muda entre eles e os 99 media da loja?

## PROCEDENCIA
Valores de fixture sintetica sao entradas escolhidas, nunca medidas. Leituras reais citam
ficheiro:linha. A arvore aninhada _moved/aireplay divergiu de HEAD (lido em disco 2026-10-10).
Cada numero acima traz PATH + POPULACAO + JANELA + ISO. Nada foi adicionado ao git; os
artefactos ficam em I:/cc-tmp/ods1-armB/ e o pai aterra-os no pai com caminhos explicitos.
Nada em G:. TMPDIR = I:\cc-tmp.
