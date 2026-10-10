# ARM A -- ODS1 INSTRUMENT, SYNTHETIC STORE -- RUN RECEIPT

Data da corrida: 2026-10-10T02:56:31Z (UTC). Instrumento: I:/cc-tmp/ods1-armA/ods1.py.
Reverificacao: a 2026-10-10T03:48Z as tres corridas foram repetidas com o MESMO
  ods1.py (nao editado desde as 02:56Z; sha256 conferido) e o censo saiu identico: clean
  rc 0 (red 0 / info 24 / recusas 0), mutant rc 1 (red 1 / info 30), full rc 1 (red 32 / info 134 /
  recusas 9). O verificador independente foi repetido na mesma hora: 88 checks, 0 falhas, rc 0.
Loja sintetica: I:/cc-tmp/ods1-armA/store (17 clips, 9 ficheiros estrangeiros, 23 linhas de indice).
Verificador independente: I:/cc-tmp/ods1-armA/check_armA.py (nao partilha codigo com ods1.py).

Escrito em PT-BR sem acentos: a regra desta lane e ASCII puro.

DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE.

## 1. O que foi corrido, e o que NAO foi

Tres corridas do mesmo binario, sobre tres lojas sinteticas escritas por
I:/cc-tmp/ods1-armA/make_fixtures.py. Os valores dos ficheiros sao entradas de teste
ESCOLHIDAS por esta lane; nao sao medicoes de nada no disco real.

| loja | saida | exit_code | clips | estrangeiros | linhas db | VERMELHO | info | recusas |
|---|---|---|---|---|---|---|---|---|
| store-clean | out-clean.json | 0 | 4 | 0 | 4 | 0 | 24 | 0 |
| store-mutant | out-mutant.json | 1 | 5 | 0 | 5 | 1 | 30 | 0 |
| store (full) | out-full.json | 1 | 17 | 9 | 23 | 32 | 134 | 9 |

Confirmacao de seguranca desta corrida: nenhum dispositivo de audio ou video foi aberto,
nenhum build foi feito (src/capture/build.cmd nao foi chamado), nenhum stream foi tocado,
nenhuma escrita em git, nenhum push, nenhuma rede. O root da loja esta em I:/cc-tmp,
FORA do repo: a arvore do produto nunca foi lida. Nada foi adicionado ao git.

## 2. O cabecalho da saida (contrato que o instrumento imprime de si)

* DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE -- a arvore nao tem copias; o
  instrumento nao escreve nada dentro do root.
* reads: pixels=false, sps_pps=false, streams_decoded=false, audio_device_opened=false,
  bytes_written_into_root=0.
* tolerancias, cada uma com a sua origem:
  PAD_S = 0.10 (READ specs/02-asr.md:165 -- "0.10 either side, this is why recorded
  segments overlap"); DUR_TOLERANCE_MS = 1 (ESCOLHIDA por esta lane, nao ha numero no
  spec); CLIPID_KEY_TOLERANCE_S = 0.0 (READ layout.py:433 -- o key copia o start do
  clip id, logo qualquer diferenca e uma contradicao); mp4_epoch_offset_s = -2082844800
  (COMPUTED dentro do instrumento: datetime(1904,1,1,utc).timestamp()).
* um valor ausente imprime a palavra UNKNOWN. Nunca 0. Nunca um palpite.
## 3. As contradicoes plantadas e a linha que cada uma produziu

Cada bloco abaixo tem: o clip, o facto (verdade independente), a linha que o instrumento
imprimiu, e o rank de cada fonte. Ranks: 1 clip-id, 2 key.json, 3 db, 4 container, 5 mtime.

**C01 INTERVAL OVERLAP -- 20261009T120120Z-0008 vs 20261009T120121Z-0009.**
Factos independentes: A008 key [1791547280, 1791547284], A009 key [1791547281,
1791547285] -- ranks [2,2], ambos do key.json. Sobreposicao medida 3.000 s (values
overlap_s), contra a tolerancia PAD_S 0.10. Linha VERMELHA:
"subject=20261009T120120Z-0008 vs 20261009T120121Z-0009, detail="intervals overlap by
3.000 s, which is more than the PAD_S 0.10 s tolerance".

**C02 IDENTICAL IDENTITY -- o mesmo par.** Os dois clip.mp4 sao byte-iguais
(sha256=bc61af69259b9f5b..., ambos os lados 5430 bytes). Linha VERMELHA com sha256 no
subject, evidencia nos dois directorios, e o texto a nomear o limite do indice: "the index
enforces UNIQUE(content_key) (schema.sql:44) so only ONE may be indexed -- the rest is
DUPLICATE ROOM this tree does NOT write".

**C02 IDENTICAL IDENTITY (segunda) -- not-a-clip-id/clip.mp4 vs imports/db-zero-duration.mp4**,
os dois sha256=386b4226ee4f8d1...: a mesma identidade sob um nome que nao e clip id.

**C02-CONTENT-KEY-LIE (IDENTITY CLAIM LIES) -- 20261009T120220Z-0017.** O key.json
declara content_key=34743952a84bfff1... e os bytes dao dbc16d9f72fc9ca7...: a linha
IMPRIME OS DOIS e conclui "identity by content is NOT what the row claims". As 13
declaracoes de identidade da loja foram recalculadas, 13 de 13.

**C03 PATH MOVED -- 20261009T120130Z-0010.** A linha do db aponta para
clips/2026/10/08/20261008T110000Z-0099/clip.mp4, que NAO existe; o clip vive no seu
directorio de clip id. Linha VERMELHA PATH MOVED com db_path, now_at e ranks [3,1],
evidencia no caminho morto e no directorio vivo. NOTA DE DESCOBERTA: a forma "duas
linhas para uma identidade" e irrepresentavel -- video.content_key e UNIQUE
(schema.sql:44), a segunda INSERT foi tentada e recusada com IntegrityError (ver
fixture_correction_20261009 em manifest.json). O dono pode querer saber que o indice
nao consegue guardar dois caminhos para a mesma identidade.

**C03 DB ROW ABSENT -- 20261009T120121Z-0009 (consequencia, nao plantada).** So um dos dois
clips byte-iguais pode estar no indice, por causa do UNIQUE; o outro fica "committed on
disk with no video row naming it". Isto e consequencia do plantado C02 e vale como achado
honesto, nao como falha do instrumento.

**C05 NEGATIVE OR ZERO INTERVAL -- 20261009T120100Z-0007.** O key diz started_at_s
1791547260.0 e ended_at_s 1791547258.0: acaba antes de comecar. Linha VERMELHA: "the
chosen end (1791547258.000000) does not come after the rank-1 start (1791547260.000000,
source=clip-id): the row is not a time interval at all".

**C07 DECLARED vs DECODED -- 20261009T120040Z-0006.** key.json duration_ms=4000 contra o
trak de video do moov. Linha: "key.json duration_ms=4000 but the moov video trak decodes
5000 ms (1000 ms apart, tolerance 1 ms)", values {key_ms 4000, container_ms 5000}.

**C08 DURATION SOURCE MISMATCH.**
* 20261009T120040Z-0006: db 4000 vs moov 5000 (1000 ms).
* legacy-2026-09-01.mp4: db 2500 vs moov 3000 (500 ms).
* db-zero-duration.mp4 e not-a-clip-id/clip.mp4: db 0 vs moov 2000 (2000 ms cada).
* 20261009T120154Z-0014: db 0 vs moov 2000.

**C09 KEY START vs CLIP ID -- 20261009T120020Z-0005.** O clip id
20261009T120020Z-0005 descodifica para 1791547220 (rank 1, parse_clip_id); o seu
key.json diz started_at_s 1791547220.5. Delta 0.500 s contra uma tolerancia de 0.0 s.
Linha VERMELHA, evidencia no key.json e no directorio, ranks [2,1], values
{key_started_at_s 1791547220.5, clip_id_started_at_s 1791547220, delta_s 0.5}. Repare-se
que a LINHA continua a comecar no rank 1 (o clip id manda sobre o key) e termina no
rank 2: a contradicao esta na linha, nao na ordem das fontes.

**C2TRAK -- 20261009T120040Z-0006.** trak#0 handler "vide" 5000 ms, trak#1 handler "soun"
8000 ms. Linha: values {trak_durations_s [5.0, 8.0], handlers ["vide","soun"],
max_minus_min_s 3.0}, severidade informativa: a diferenca audio/video NAO entra no C07.
## 4. O VERMELHO que a arma A apanhou no proprio instrumento

Um segundo leitor, I:/cc-tmp/ods1-armA/check_armA.py, le os mesmos ficheiros com o seu
proprio parser mp4 e nao partilha uma linha de codigo com ods1.py. Ele nao serve para
concordar: serve para discordar. Discordou, e a discordancia era real.

**O bug: a duracao do contentor era lida com max(durs).** find_contradictions
calculava cont_ms = max(durs) sobre os traks do moov. Em 20261009T120040Z-0006 o trak#0
e handler "vide" (5000 ms) e o trak#1 e handler "soun" (8000 ms). O max() escolhia o
AUDIO, e o instrumento imprimia "o moov descodifica 8000 ms" ao mesmo tempo que a sua
propria linha dizia duration_ms=5000 -- usava exactamente o "max reader" que o texto do
seu C2TRAK avisa que nao se deve usar. Corrigido com um helper unico, video_trak_ms(),
que devolve a duracao do trak de handler "vide" (nunca 0, nunca max); usado nos dois
sitios, clip_timeline e foreign_timeline. Depois da correccao o C07 passa a dizer
"key.json duration_ms=4000 but the moov video trak decodes 5000 ms (1000 ms apart)" e o
C08 o mesmo contra a db. O leitor independente confirma: video_ms_of(A006) = 5000,
trak_facts = [("vide",5000),("soun",8000)].

**Como e que esse bug se escondeu: uma corrida que nunca aconteceu.** A primeira versao
do comando de corrida passava o caminho do python ja citado para dentro de um cmd /c; a
camada de escape do harness duplicava as aspas, o cmd respondia "nao e reconhecido como
um comando interno ou externo" e saida com rc 1 -- o MESMO codigo que o instrumento
devolve por desenho quando ha VERMELHO. Durante varias leituras li ficheiros de saida
antigos como se fossem novos; o run_started_utc nao avancava, que era o unico sinal
honesto de que nada tinha corrido. A licao fica no relatorio: um spawn que nao consegue
comecar o programa sai 1, igual ao instrumento; e o teste de "a corrida aconteceu" e o
carimbo de saida, nao o exit code.

**E dois bugs MEUS no leitor independente, que sao a prova de que ele e independente.**
(a) lia o handler do hdlr em b[i+8:i+12] -- o campo pre_defined -- em vez de b[i+12:i+16],
e o kind() nunca encontrava o hdlr. (b) lemos a timescale do mdhd no sitio errado e
mdhd_timescale() devolvia None neste formato de ficheiro; substituido por mdhd_ts(), que le
a timescale no offset de conteudo s+12. Os dois foram encontrados por sondagem ao modulo,
nao por comparacao com o instrumento. So depois dos dois e que os numeros passaram a
coincidir -- o que e exactamente o valor de um segundo leitor: ele parte de suposicoes
proprias e erra sozinho.
## 5. As duas armadilhas de sanidade, nos tres bracos

**A armadilha do 1-jan-1970.** O escritor deste produto escreve o literal 0 nos campos de
epoca (mp4_writer.cpp:257 mvhd, :272 tkhd, :293 mdhd). Se o instrumento tratasse 0 como
um instante, todos os contentores datavam de 1970-01-01 e nenhum operador ia acreditar no
resto da timeline. Resultado medido: 0 linhas imprimiram uma DATA derivada de um carimbo
mp4 (self-audit zero_epoch_fields_formatted_as_dates, 7 verdades nos tres bracos). O que o
instrumento imprime em vez disso e um CENSO de campos em zero, por tipo de caixa, em
20261009T120040Z-0006: mvhd:creation_time 1, mvhd:modification_time 1,
tkhd:creation_time 2, tkhd:modification_time 2, mdhd:creation_time 2,
mdhd:modification_time 2 -- e o offset de epoca mp4 (-2082844800 s) e COMPUTADO dentro do
instrumento, nao decorado de um comentario.

**Ausente imprime UNKNOWN, nunca 0.** Self-audit zero_is_never_an_absent_value: 0 linhas
usam o numero 0 como valor. Seis linhas carregam pelo menos um valor ausente e cada uma
imprime a palavra UNKNOWN.

**Seven self-audits, todos verdes nas tres corridas:** rows_emitted_equals_visited (26 =
17 + 9), no_duplicate_rows (26 linhas, 26 distintas),
zero_epoch_fields_formatted_as_dates, unknown_prints_as_the_literal_word (6 linhas),
zero_is_never_an_absent_value, clip_start_is_rank_1_when_present (17 de 17 linhas comecam
no rank 1, a unica fonte acima do key.json) e every_identity_claim_was_recomputed (13
declaracoes, 13 recalculadas contra os bytes). Um instrumento que nao sabe dizer NAO nao
vale nada: os dois bracos de controle abaixo sao o NAO dele.
## 6. Os bracos de controle -- o instrumento sabe dizer NAO?

* **store-clean** (loja sem nenhuma contradicao plantada): 0 VERMELHO, exit_code 0.
  Se o instrumento tivesse acusado alguma coisa aqui, todos os VERMELHOS da loja completa
  seriam suspeitos. Nao acusou.
* **store-mutant** (a loja limpa MAIS uma unica sobreposicao de 0.10 s em
  20261009T120015Z-0900): exactamente 1 VERMELHO, classe C01, sobre esse clip,
  exit_code 1. Uma copia deliberadamente partida tem de ficar VERMELHA; ficou, e ficou
  so essa.
* **store completa**: exit_code 1, 32 VERMELHO, 9 recusas, self-audit 7/0,
  expectation_checks_failed = 0 -- o instrumento tambem correu o seu proprio manifesto de
  expectativas (make_fixtures.py escreve o que espera) e todas as expectativas bateram
  certo.

Censo VERMELHO por classe na loja completa (isto e o numero relatavel; o banner do stdout
conta com os informativos e nao e comparavel): C01 1, C02 3, C03 3, C05 5, C07 1, C08 5,
C09 1, C2TRAK 1, R-DATA-QUALITY 3, REFUSAL 9.

## 7. As nove RECUSAS -- um ficheiro ilegivel nao tem duracao 0, tem duracao DESCONHECIDA

Cada recusa traz a primeira causa E o codigo terminal (code -> terminal_code), e a linha
fica com duracao UNKNOWN:

| ficheiro | primeira causa | terminal |
|---|---|---|
| clips/.../20261009T120138Z-0012/clip.mp4 | R-BOX-TRUNCATED | R-NO-MOOV |
| clips/.../20261009T120150Z-0013/clip.mp4 | R-VERSION (key v2) | -- |
| clips/.../20261009T120205Z-0016 | R-WRONG-DIR | -- |
| imports/not-really.mp4 | R-BOX-TRUNCATED | R-NO-FTYP |
| imports/moov-truncated.mp4 | R-BOX-TRUNCATED | R-NO-MOOV |
| imports/moov-no-duration.mp4 | R-NO-DURATION | R-DURATION-UNKNOWN |
| imports/moov-no-timescale.mp4 | R-NO-TIMESCALE | R-NO-DURATION |
| imports/mp4-unknown-box.mp4 | R-BOX-UNKNOWN | R-NO-MOOV |
| imports/mvhd-v1.mp4 | R-BOX-VERSION | R-NO-DURATION |

A recusa do key.json v2 e a que vale mais por enquanto: layout.py read_key recusa um v2
("refusing beats reading a v2 as v1"), e o instrumento imprime a recusa em vez de fingir
que leu.
## 8. Os quatro estados de um clip e as linhas C05/C08 a mais

Os quatro estados de .partial, cada um com o que a pasta tem:
20261009T120134Z-0011 (tem key.json) -> partial-committed; 20261009T120138Z-0012 (sem
key.json) -> partial-uncommitted; 20261009T120154Z-0014 (key.json, sem clip.mp4) ->
orphan-key; 20261009T120158Z-0015 (key.json, sem clip.mp4 e sem linha de db) ->
missing-media. O 20261009T120150Z-0013 (key.json v2, recusado por layout.py) tambem
fica partial-uncommitted: sem key legivel nao ha prova de commit. Os 11 sem marcador ->
committed. As 9 linhas estrangeiras -> verdict null: o instrumento nao inventa um estado
para um ficheiro que nao e um clip deste produto.

O 20261009T120205Z-0016 tem .partial e o key.json esta na pasta certa, mas o key
declara clip_id=20261009T123319Z-9999: layout.py recusa o key (R-WRONG-DIR) e o
directorio fica no rank 1. Nao ha caminho B no meio: um nome que nao e diretorio de clip
id nem entra na timeline dos clips.

**Linhas a mais do que as plantadas, e porque la estao (nao escondidas):**

* Mais 4 C05 alem do 20261009T120100Z-0007 plantado. Duas vem de duration_ms = 0 na db
  (20261009T120138Z-0012 e 20261009T120154Z-0014) -- fim igual ao comeco, nao e um
  intervalo. Duas vem de linhas estrangeiras cujo fim veio da db duration_ms = 0 com
  comeco no mtime (rank 5). Nao sao falhas do instrumento: sao a loja a dizer que um
  clip cuja duracao declarada e 0 nao tem intervalo, e o instrumento a imprimir isso.
  A 0011 (db 0) nao da C05 porque o fim vem do key.json (rank 2), e um duration_ms = 0
  na db para um clip assim e o artefacto do build-time "chosen_key_duration_ms or 0",
  nao uma contradicao temporal.
* Um R-DATA-QUALITY (3 no total) para cada caso em que a db declara 0 ms e o contentor
  le-se bem: o valor 0 nao e uma duracao, e uma declaracao falsa de um ficheiro que
  existe.

## 9. O que esta loja sintetica NAO conseguiu reproduzir (e vai para o dono, nao para um palpite)

1. **C06 GAP: 0 achados, e nao por falta de clips.** A regra do C06 e por assunto
   (tiling por subject), e neste braco cada clip e um assunto proprio -- uma linha por
   sujeito nao pode ter vizinhos. A informacao de vao entre clips sai como INFO-GAP (9) e
   nao como VERMELHO, por uma razao do schema: schema.sql:65-68 poe o start_ms da janela
   ASR na tabela segment ("a 5 s window ... start_ms lives HERE, never on video"), e esta
   loja nao tem linhas de segment. Um GAP de ASR so e testavel quando existirem segmentos.
2. **Se dois clipes de uma sequencia tem de ser contiguos.** specs/02-asr.md:165 diz que
   PAD_S 0.10 e porque "recorded segments overlap" -- logo o produto ESPERA sobreposicao
   de janelas ASR. Se o mesmo valer para clipes inteiros, a minha sobreposicao de 3 s e
   normalidade e o C01 esta a gritar sobre nada.
3. **Um ficheiro estrangeiro tem alguma fonte de duracao alem de db-vs-contentor?** Nas
   linhas estrangeiras so ha rank 3 e 4; o key.json e o clip-id nao existem la. Se a
   importacao trouxer uma duracao propria, falta-lhe um rank.
4. **O moov de um ficheiro importado traz um creation_time utilizavel?** O writer deste
   produto escreve 0 literal (mp4_writer.cpp:257/272/293); um importado pode vir com
   epoca 1904 preenchida, e hoje o instrumento nao usa esse campo para nada -- por
   escolha, para nao ressuscitar a armadilha do 1970.
5. **O indice nao consegue representar dois caminhos para uma identidade.**
   video.content_key e UNIQUE (schema.sql:44); a segunda INSERT falhou com IntegrityError,
   medido. Se o produto um dia aceitar um caminho movido, o C03 PATH MOVED nao e
   detectavel por duplicacao de linha -- e por outra coisa que ninguem especificou.
6. **Quantos ms de tolerancia para a comparacao de duracoes?** DUR_TOLERANCE_MS = 1 foi
   ESCOLHIDO por esta lane. O numero nao veio de nenhum spec.
## 10. Proveniencia e ressalva honesta

* Todos os valores dos ficheiros desta loja sao entradas de teste ESCOLHIDAS por esta lane.
  O unico numero real no meio e o que vem de leituras: PAD_S 0.10 (specs/02-asr.md:165),
  o inicio do key copiado do clip id (layout.py:433), content_key UNIQUE (schema.sql:44)
  e os zeros literais do escritor (mp4_writer.cpp:257/272/293).
* Ressalva: a arvore _moved/aireplay divergiu de HEAD -- outras lanes trabalharam nela
  esta semana. Cada citacao "ficheiro:linha" acima e uma leitura do ficheiro COMO ESTA EM
  DISCO HOJE, e os numeros de linha nesta arvore podem ter mudado. As citacoes foram
  relidas antes de escrever esta linha; a data e 2026-10-10.
* Verificado: a juncao H:/aireplay, que o brief desta lane manda NAO apagar, existe
  (fs.existsSync e dir /a, 2026-10-10) e aponta para H:/sotto/_moved/aireplay. Nada meu a
  tocou: as minhas escritas foram para I:/cc-tmp/ods1-armA/ e para
  H:\sotto\_moved\aireplay\_main\_lease-audit\, e a unica remocao que fiz foi dos meus
  proprios ficheiros de riscar dentro de I:/cc-tmp/ods1-armA/.
  (Erro que quase passou: um resumo meu dizia H:\sotto\.aireplay; o caminho que o brief
  mandou nao apagar e H:/aireplay, e esse existe. Fica escrito para ninguem "corrigir" um
  caminho que nunca faltou.)
* Nada foi adicionado ao git. Este relatorio e os seus pares sao ficheiros por
  acompanhar, nao commits.

## 11. Como repetir esta corrida

    set TMPDIR=I:\cc-tmp
    "C:\Program Files\Python311\python.exe" I:/cc-tmp/ods1-armA/make_fixtures.py
    "C:\Program Files\Python311\python.exe" I:/cc-tmp/ods1-armA/ods1.py --layout I:/sotto/_moved/aireplay/src/storage/layout.py --root I:/cc-tmp/ods1-armA/store --manifest I:/cc-tmp/ods1-armA/manifest.json --expect-store full --out-md out-full.md --out-json out-full.json
    "C:\Program Files\Python311\python.exe" I:/cc-tmp/ods1-armA/check_armA.py

O verificador independente e o que decide se esta armadura serve: hoje sao 88 verificacoes,
0 falhas, rc 0, saida guardada em check-armA-output.txt.

--
Fim do relatorio da armadura A da OD S1. Nenhum video, audio, build ou git foi tocado para escrever isto.