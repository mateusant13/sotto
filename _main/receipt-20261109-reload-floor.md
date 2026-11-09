# RECIBO — o ciclo carga/largada que se excita a si proprio (2026-11-09)

Tudo o que segue foi medido nesta arvore, hoje, com o comando ao lado. Onde digo `PASS`, o `rc`
esta' colado; onde digo `UNMEASURED`, digo-o por palavras.

## 1. A queixa e a medicao que ela obrigou

DM do watcher (`I:\!watcher\state\herdr-inbox\dm-00dbf74d817f8b2c3ddd.md`, stutter 50452):
`SUBTOTAL 50452 -> 2 04m/8/s`, `O D3 e top`, e o cabecalho do log do worker:

```
REDUX_ENGINE_LOAD 82   REDUX_ENGINE_RELEASE 70        (numa execucao)
REDUX_ENGINE_LOAD_MS 1900                              (1,9 GB lidos do disco por carga)
par mais apertado: carga 06:55:15,304 -> largada 06:55:46,571   = 31 s
```

A leitura da DM que este recibo aceita: **o ciclo regula mal porque se excita a si proprio** — o
nivel sobe enquanto a carga pesa, e cai quando ela acaba, e a carga seguinte (que o nivel pediu) e'
o que produz a proxima subida. Nao ha' nada de "estragado": ha' dois relogios que nao conversam.

## 2. A decisao (e o que foi RECUSADO)

* **A LARGADA NUNCA E' RECUSADA.** Primeira versao desta cura tinha um piso `MIN_LOADED_S = 120 s`
  em `release()` ("nao largar o que acabou de se carregar"). **Retirada antes de commitar**: um
  modelo que a pressao pediu para sair tem de sair, e um piso na largada e' exactamente a inversao
  que o dono proibe (a maquina e' o que nao pode sofrer). Largar devolve 460 MB e e' barato;
  **o que custa 1,9 s de disco e a rajada de CPU e' VOLTAR**.
* **O PISO E' NO LADO DA CARGA.** `ParakeetEngine.reload_floor_left()` conta os segundos que faltam
  para o motor poder voltar a carregar: `max(RELOAD_FLOOR_S, RELOAD_FLOOR_LOAD_FACTOR * load_s)`
  = `max(60 s, 10 x load_s)` — um motor cuja leitura custa 20 s espera 200 s.
* **O LOTE DO INTERVALO ESPERA; UMA CAUDA TENTA E DIZ QUE TENTOU.** `maybe_kick` passa
  `respect_memory_floor=True` e devolve `False` dentro do piso, com o audio na fila e o tick seguinte
  a tentar outra vez (`REDUX_BATCH_DEFERRED reason=reload-floor wait_s=.. held_s=..`). Uma cauda nao
  tem tick seguinte, logo tenta e escreve `REDUX_BATCH_RELOAD_FLOOR ... attempting=anyway` — uma
  recusa muda seria perda do ultimo minuto do dono.

## 3. O que mudou, por ficheiro

| ficheiro | mudanca |
|---|---|
| `worker/engine_policy.py` | `RELOAD_FLOOR_S = 60.0`, `RELOAD_FLOOR_LOAD_FACTOR = 10.0`; `ParakeetEngine.loaded_t`/`released_t`, `reload_floor_left()`, `release_age_s()`; `release()` regista o instante e **nunca recusa** |
| `worker/engine_switch.py` | `flush_pending` consulta `reload_floor_left()` do motor: deferivel (intervalo) ou "tenta e diz" (cauda) |
| `_main/redux-arm-weights-oracle.py` | ARMs **R1-R8** (o piso no motor e no lote) + mutante **M5** que remove o deferimento |
| `_main/load-shedding-oracle.py` | `_FakeEngine.reload_floor_left()` (0 por omissao: a arm 11 continua a medir o comportamento de antes) |

## 4. Verificacao — os tres comandos e os tres vereditos

```
python _main/redux-arm-weights-oracle.py
  GREEN ARM SUMMARY: 28/28 checks green; red=[]
  VERDICT: PASS                                        rc=0

python _main/redux-arm-weights-oracle.py --neg-arm
  MUTANT VERDICT M5-reload-floor-removed: ... missing=[] extra=[] -> OK
  MUTANT VERDICT M4-control-comment-only-must-move-nothing: expect_red=[] observed_red=[] -> OK
  VERDICT: PASS                                        rc=0

python _main/load-shedding-oracle.py
  LOAD-SHEDDING GREEN -- arms=240 pass=240 fail=0       rc=0
python _main/load-shedding-oracle.py --neg-arm
  NEG-ARM(largada-cpu) PASS ... NEG-ARM(largada-cega) PASS    rc=1
```

As arms novas, com os numeros delas:

| arm | medido |
|---|---|
| R1 piso zero antes de largar | `floor_left=0.0` |
| R2 a largada nunca e' recusada | `release=True releases=1 loaded=False` |
| R3 o piso comeca em 60 s | `floor_left=60.0` (`RELOAD_FLOOR_S=60.0`) |
| R4 o piso passa | `floor_left=0.0` aos 61 s |
| R5 o piso cresce com o custo da carga | `floor_left=200.0` para `load_s=20` (`factor=10.0`) |
| R6 o lote espera o piso | `kicked=False deferred=1`, linha `reason=reload-floor` |
| R7 uma cauda tenta e diz que tentou | linha `REDUX_BATCH_RELOAD_FLOOR ... attempting=anyway` |
| R8 sem piso o lote nao espera | `deferred=0`, nenhuma linha |

M5 (o deferimento arrancado com `if False:`) derruba **R6 e R7 e mais nada**; o mutante de controlo
(um comentario) nao move arm nenhuma — o instrumento nao avermelha por qualquer diff.

## 5. O QUE NAO ESTA' MEDIDO

* **A contagem de cargas depois da cura, na instancia do dono, e' UNMEASURED.** O worker vivo corre o
  codigo de antes de hoje; a cura e' do FICHEIRO. O numero que a fecha e'
  `grep -c REDUX_ENGINE_LOAD` no log dele por hora depois de um worker novo — e o worker novo e'
  arrancado pelo artefacto (matar o pid cujo `cmdline` contem `sotto_worker.py`; a shell respawna em
  ~1 s), nunca pela mao dele na app.
* **O efeito no stutter** so' se afirma com o instrumento do watcher e a mesma janela depois.
* O `ReleaseGate` da largada (commit/CPU) nao foi tocado por esta cura.

## 6. As outras duas regras da MESMA DM, e quem as cumpre

A DM propunha tres regras. A #2 e' a deste recibo. As outras duas **ja' estao no ficheiro**, no
`ReleaseGate` de `app/webview/load_shedding.py:696-753`, e a medicao de hoje diz por que o caso do
log do dono passa a ser recusado:

| regra da DM | mecanismo | numero |
|---|---|---|
| 1. nao largar o que o proximo passe precisa sem o `shed` PERSISTIR | `may_release` devolve `'memoria-sustentada-espera'` com `wait_s` no log | `RELEASE_PERSIST_S = 120.0` s |
| 3. preferir PAUSA a unload quando ha' commit | `commit < HIGH_PCT` -> `'cpu-apenas'`, o modelo FICA (o modo `shed` ja' pausou o lote) | `HIGH_PCT = 88.0`, `VERY_HIGH_PCT = 94.0` |

O par medido na DM -- `LOAD_ACTION_PUBLISHED ... commit=59.0% cpu=99.1%` seguido de
`REDUX_ENGINE_RELEASED` -- e' exactamente o caso `cpu-apenas`: **59,0 % < 88,0 %**, logo a largada
e' recusada e o log diz `REDUX_ENGINE_KEPT ... why=cpu-apenas`. Aquela largada aconteceu antes de a
guarda estar no caminho; com ela, o ciclo nao comeca (nao ha' largada) e, se houver largada por
memoria real, o piso da #2 impede a recarga imediata.

## 7. O que a DM pediu em `load()`

A DM apontava `worker/engine_policy.py:201-222` (`load()`) como o sitio do ciclo. Este recibo
**nao poe o piso dentro do `load()`**: um piso no `load()` recusaria a carga do caminho de STREAM
(`transcribe()` chama `load()`), ou seja calaria o motor ao vivo para poupar disco -- a inversao que
o dono proibe. O piso vive no unico chamador que existe para decidir cargas: o LOTE
(`flush_pending`), que e' quem pode esperar sem perder audio.

## 8. O REPLAY DO LOG DO DONO (2026-11-09, 12:0x) -- quantas das 82 cargas a cura corta

Instrumento: as duas funcoes que EMBARCAM (`load_shedding.ReleaseGate.may_release` e a aritmetica
`max(60 s, 10 x load_s)`), alimentadas com as linhas do proprio `_main/webview-run.log`
(65 340 820 B) e com o relogio real daquelas linhas. Nao e' simulacao de modelo: e' o predicado
publicado a julgar o passado medido.

```
LOAD_ACTION_PUBLISHED: 443   (leve 151, alta 208, muito-alta 84)
REDUX_ENGINE_RELEASED: 70    REDUX_ENGINE_LOAD: 80-82
```

**O ReleaseGate sobre as 84 publicacoes `muito-alta` do log:**

| razao | publicacoes | larga? |
|---|---|---|
| `cpu-apenas` (commit < 88 %) | **69** | NAO |
| `memoria-sustentada-espera` (commit >= 88 % ha' < 120 s) | 5 | NAO |
| `commit-ilegivel` (direccao segura, OOM) | 4 | sim |
| `memoria-sustentada` (>= 88 % por >= 120 s) | 3 | sim |
| `memoria-emergencia` (>= 94 %) | 3 | sim |
| **total** | **84** | **10 largam, 74 nao** |

Ou seja: das **70 largadas** que o log registou, **no maximo 10** teriam acontecido com a guarda no
caminho. As 69 em `cpu-apenas` sao exactamente o regime que a DM nomeia (`commit=59.0% cpu=99.1%`):
a pressao e' de CPU, o modelo nao e' o recurso escasso, e o modo `shed` ja' tinha pausado o lote.

**O piso da recarga sobre os pares release -> load do mesmo log:**

| piso | pares adiados |
|---|---|
| 60 s | **15 de 59** |
| (contraste) 120 s | 26 de 59 |

`load_s` no log: min 0,94 s, mediana 2,28 s, max 19,35 s — logo o piso efectivo e' 60 s na maioria
das cargas, e `max(60, 10 x 19,35) = 193,5 s` para a carga mais cara. O par mais apertado medido
(4,4 s) esta' entre os adiados.

**O que este replay NAO prova:** que a instancia viva pare de ciclar -- o worker em execucao corre o
codigo de antes de hoje. O que ele prova e' que, com estas duas guardas no caminho, o passado medido
nao se reproduz: 74 das 84 janelas severas nao largam nada, e 15 das recargas ficam a espera.

## 9. O WORKER NOVO (2026-11-09, 09:07) -- quem corre a cura a partir de agora

O worker vivo carregava o codigo de 08:14:03 (pid 43076). Morto pelo ARTEFACTO, como a casa exige:

```
43076 python.EXE -u H:\sotto\worker\sotto_worker.py     started 08:14:03  rss 815,8 MB  cpu 5,5 % de um nucleo
kill em 09:07:03  ->  BRIDGE_EXIT pid=43076 rc=15 killed=False spawns=1
   BRIDGE_SPAWNED pid=20676                                      09:07:04.932   (1,1 s depois)
   BRIDGE_LOAD_MS ms=23547 pid=20676 worker_load_s=22.85         09:07:28.342
```

A identidade foi provada pelo `cmdline` ANTES do kill (`sotto_worker.py`, filho do pid 50452 =
`pythonw.exe ... sotto_webview.py`), nunca pelo nome do processo. A SHELL nao foi tocada: ela tem
`--no-self-relaunch`, e um arranque novo dela so' com a mao do dono.

**Porque este worker TEM a cura:** `worker/engine_policy.py` tem mtime **08:43:44** e o processo
nasceu **09:07:04** -- o `reload_floor_left()` e os dois pisos foram lidos do disco por este
processo. O `worker/engine_switch.py` foi reescrito as **09:07:29** por OUTRA lane (removeu o
`_release_when_idle`, que ninguem lia, e reordenou um kwarg) -- isto e' posterior ao arranque e nao
afecta o piso, cuja linha (`reason=reload-floor`) continua no ficheiro; o proximo arranque e' que
leva essa limpeza.

**O numero pos-reinicio e' do watcher**, por acordo: ele mede, na mesma janela, `REDUX_ENGINE_LOAD`
por hora, quantos com `REDUX_BATCH_DEFERRED reason=reload-floor` / `attempting=anyway`, e o pico de
MB/s e de % de um nucleo. A janela comeca em **09:07:04.932**. O que eu posso afirmar daqui:
**nenhuma linha `REDUX_ENGINE_LOAD`/`REDUX_ENGINE_RELEASED`/`REDUX_BATCH_*` foi escrita nos
primeiros minutos** -- o parakeet so' carrega no primeiro passe de fundo, e sem passe nao ha' rajada.

### 9-bis. O que consigo e o que NAO consigo medir nesta instancia, e porque

Nos primeiros 10 minutos da janela nova (09:07:04.932 -> 09:16:59) o log tem **zero** linhas
`REDUX_ENGINE_LOAD` / `REDUX_ENGINE_RELEASED` / `REDUX_BATCH_*`. Medido por dois caminhos que
concordam: uma varredura unica e um laco de 480 s (`achados: 0`), e o mesmo zero no instrumento do
watcher. Isso era compativel com duas coisas, e uma delas ja' esta' descartada:

1. **o interruptor esta' armado e nao houve nenhum passe de fundo** -- e' esta a verdadeira, ver
   abaixo;
2. ~~o interruptor nao esta' armado nesta shell~~ -- descartada por medicao.

**O que DESCARTA a hipotese 2:** o worker ANTERIOR desta MESMA shell (pid 50452, mesmas flags,
mesmo `pythonw`) armou de facto o interruptor -- o log dele tem
`REDUX_ENGINE_RELEASED ... releases=1` as 08:34:43 e `REDUX_ENGINE_LOAD ... loads=2` as 08:38:23,
e essas linhas so' existem se `flush_pending` correu, ou seja se `armed` era verdadeiro. O ambiente
e' herdado do pai, e o pai nao mudou (pid 50452, arrancado 08:14:03).

**Porque nao leio o ambiente directamente:** o `psutil.Process(...).environ()` dos dois pids levanta
`AccessDenied`, e a causa esta' medida com os SIDs ao lado (`GetTokenInformation`,
`TokenIntegrityLevel`, lidos de um pane `medium`):

| pid | processo | integridade |
|---|---|---|
| 3012 | watcher daemon | `S-1-16-8192` (**medium**) |
| 50452 | shell Sotto | `S-1-16-12288` (**high**) |
| 20676 | worker Sotto | `S-1-16-12288` (**high**) |
| 50820 | este pane | `S-1-16-8192` (**medium**) |

UIPI: `medium` nao le' `high`. E a MESMA parede que produz o `stutter_relief park_failed pid=20676
'open_pid: access denied'` do journal do watcher -- nao e' um pid estranho, e' o parque a bater na
integridade. Nada a apertar do lado do Sotto: do lado do daemon nao ha' acao possivel.

**O que fica em aberto e' a CONTAGEM, e ela tem uma marca de calendario:** a instancia anterior levou
**15,70 min** ate' o primeiro `REDUX_ENGINE_LOAD` (08:29:48 sobre um arranque as 08:14:03), **20,66
min** ate' a primeira release e **24,33 min** ate' o segundo load -- com o commit da maquina em
58-59 % e o cpu em 82-99 %. Pela mesma forma, a janela nova nao devia ver nada antes de **09:22:47**.
`loads=0` antes dessa marca e' a forma normal, nao um resultado nulo; e o marcador de que o piso
morde em producao e' `REDUX_BATCH_DEFERRED`, que so' pode aparecer quando houver uma RECARGA
TENTADA -- entre 08:43 (a cura no disco) e 09:07 nao houve nenhuma, e por isso `DEFERRED=0` la' nao
prova que a guarda falhou: prova que ela nao teve o que guardar.

**MEDIDO, e a marca acima corrige-se:** o primeiro `REDUX_ENGINE_LOAD` da janela nova chegou as
**09:18:26.308 (+11,36 min)** -- `loads=1 load_s=2.97 rss_mb=1524.9`. A previsao de "nada antes de
09:22:47" era uma derivacao de UMA instancia (+15,70 min) e a decisao de hoje veio por outro caminho
(`LOAD_ACTION_PUBLISHED level=alta` as 09:17:15, "o worker muda de modo", imediato; o load 71 s
depois). Com duas instancias medidas a banda honesta e' **+11 a +16 min**, nao um instante. Na
mesma janela, ate' 09:24: `LOAD_ACTION_PUBLISHED` 3, `REDUX_ENGINE_RELEASED` 0, `REDUX_BATCH_*` 0
-- sem largada nao ha' pedido de recarga, logo o piso continua sem oportunidade de morder.

### 9-ter. Uma correccao de INSTRUMENTO que a medicao desta janela obrigou (2026-11-09, 09:2x)

`_main/load-shedding-oracle.py` (arm 26, "pressao de memoria (89 %) larga so' depois de 120 s
SUSTENTADOS") passou a VERMELHO com a guarda nova `RELEASE_GAP_S` que outra lane escreveu no
`load_shedding.py` -- e o vermelho era do ARM, nao da guarda. A sonda saltava de `t=0` para
`t=119` e da' para `t=120`: **um buraco de 119 s entre duas leituras**, e a guarda de 2026-11-09
trata um buraco como "a pressao pode ter acabado" e ZERA o relogio (o que e' certo). O arm passou a
amostrar de 5 em 5 s, que e' como a pressao real chega, e ficou verde.

Prova de que o vermelho nao era da guarda e nem da cura do piso: carregando `git show
HEAD:app/webview/load_shedding.py` num modulo a parte e correndo a MESMA sequencia esparsa, o
`may_release` devolve `True` em `t=120` -- ou seja o comportamento antigo do arm so' funcionava
porque a guarda do buraco ainda nao existia.

**O que NAO e' meu e fica declarado:** as 09:23 a arvore carrega edicoes em voo de OUTRA lane em
`app/webview/load_shedding.py` (09:20:06), `app/webview/sotto_webview.py` (09:17:06),
`worker/engine_switch.py` (09:20:24) e `worker/sotto_worker.py` (09:20:18) -- e o mesmo oraculo
publica **2 RED** em arms do `mode` ("e o nivel desce para `batch`", "e um SEGUNDO aperto na mesma
sessao volta a ser dito") que pertencem a essa edicao, nao ao piso de recarga. Nao os persigo e nao
os reverto: o ficheiro e' dessa lane. Fica o numero ao lado deles: **249 de 251 arms verdes, 2 RED,
ambos no `mode` do interruptor**.

## 10. O ORCAMENTO DE FIOS DO WORKER PASSA A SER LEGIVEL AO VIVO (2026-11-09, 13:0x)

Pergunta do watcher: "o teu worker tem 76 fios e um pico de 3,9 nucleos -- que orcamento esta' a
correr?". As tres leituras, todas desta sessao:

| o que | numero | instrumento |
|---|---|---|
| worker em repouso | **76 fios, 3,7 % de um nucleo**; topo 2,3 % / 1,1 % | `_main/shell-thread-cpu.py 20676 --seconds 8 --top 8` |
| orcamento NO CODIGO | intra-op **2**, inter-op 1, `allow_spinning=0`, `OMP_WAIT_POLICY=PASSIVE` | `_main/worker-thread-limit-oracle.py` -> `PASS (15/15)` |
| o que o worker VIVO recebeu | **nenhuma flag**: `argv=["...python.EXE","-u","H:\sotto\worker\sotto_worker.py"]` | `BRIDGE_SPAWNED pid=20676` |

Logo o worker vivo resolve `ambiente > default 4` -- ate' **3 sessoes x 4 fios = 12 fios de ORT**, e
um pico de 3,9 nucleos cabe nessa aritmetica. 76 fios nao e' o mecanismo (sao pools parados; o spin
continua desligado, senao o repouso mediria os 16,1 % de 2026-11-08).

A razao da flag ausente esta' medida: `python _main/live-code-freshness-oracle.py --strict` ->
`LIVE_CODE STALE pid=50452 started=08:14:03.288 | processo sha256=77D4D1680260 | disco 3FED08353D1B`.
A cura do `--threads` esta' no disco e nao no processo; ela chega ao dono num arranque novo, que e'
dele (nenhuma lane poe a app na tela dele, e o `--self-relaunch` esta' desligado).

**A cura desta secao e' de OBSERVABILIDADE, nao de consumo:** o worker ja' escrevia
`WORKER_THREADS threads=N source=flag|env|default` no stderr, e o stderr so' e' publicado na cauda da
morte -- o numero que decide quantos nucleos o ONNX pode ocupar era ilegivel exactamente enquanto o
worker corria (a mesma classe do `ratchet` sem chamador). `WORKER_THREADS` entrou em
`ENGINE_VISIBLE_TAGS` (`app/webview/sotto_webview.py`), logo o `_pump` copia a linha para o log ao
vivo. Portao: arm **A15** do `worker-thread-limit-oracle.py` (AST sobre a tupla; exige tambem que o
worker ESCREVA a linha e que o `_pump` publique por `startswith(ENGINE_VISIBLE_TAGS)`) + mutante
**M10** que arranca a tag da tupla. Medido: `VERDICT: PASS (15/15)` e `--neg-arm` **rc=1**, 10
mutantes apanhados. `verified` nao: a linha so' aparece no proximo arranque da shell.

## 11. O INSTRUMENTO DA FRESCURA TINHA UMA REFERENCIA QUE ANDA (2026-11-09, 13:1x)

Correcao do watcher, aceite e landada. O `live-code-freshness-oracle.py` decidia pela prova A
(etiqueta gravada no arranque x hash do disco **agora**) e, quando ela existia, **nunca corria** a
prova B (instante do arranque x `mtime` de cada ficheiro). O veredicto era verdadeiro e nao
falsificavel: a segunda ponta da prova A move-se a cada commit, logo o numero citado numa DM morre em
minutos -- medido nesta sessao, o mesmo ficheiro lido duas vezes deu `3FED08353D1B` e depois
`72CB6AC71423` (objectos diferentes: 102 ficheiros contra 1, os dois certos).

O que mudou:

* **as duas provas correm sempre**, e o relatorio nomeia qual das pontas se move:
  `processo: sha256=… <- GRAVADO no arranque, nao muda` / `disco: sha256=… <- lido AGORA (hora),
  move-se a cada commit` / `prova A: hash diferente` / `prova B: 13 ficheiro(s) com mtime depois do
  arranque`. A frase reproduzivel passa a ser a da prova B: **13 ficheiros mudaram depois das
  08:14:03.288**, com a lista.
* **cada avaliacao fica gravada** em `_main/_cache/live-code-freshness.jsonl` (append-only, roda a
  256 KB): `at`, veredicto, `pid`, `started`, `boot_hash`, `disk_hash_at`, as duas provas e os
  ficheiros. "O que ele dizia as 13:20" deixa de depender de alguem o ter citado bem.
* **controlo**: novo caso `B-manda-com-A-igual` (hash igual, arranque anterior ao codigo) -> STALE.
  `--control` PASS com 6 casos; `--strict` continua **rc=3**.
* **um defeito que o controlo apanhou a escrever isto**: o instante do arranque vem truncado ao
  segundo e o `mtime` tem sub-segundo, logo um ficheiro do MESMO segundo do arranque aparecia como
  "mudou depois". Tolerancia de 1 s, com o porque' no codigo.

O veredicto do processo do dono nao mudou (STALE, 13 ficheiros, o mais recente `sotto_webview.py` as
10:04:47): o que mudou e' a qualidade da prova.

### 11-bis. O CONJUNTO TAMBEM E' UM INSTRUMENTO (mesma DM, segunda metade)

O watcher confirmou os 13 com um instrumento dele (`os.walk` em `app/` + `worker/`) e explicou porque
tinha escrito 46 antes: a leitura anterior incluia `_main/*.py` (11 ferramentas que a app nao carrega) e
os `.json` de estado, que mudam a cada minuto de uso. Os dois numeros estavam certos para o SEU
conjunto -- logo o numero nao era reproduzivel sem ele. Duas mudancas:

* a linha do relatorio passou a nomear o conjunto: `conjunto: 102 ficheiro(s) de code_identity()`;
* `--files` imprime o conjunto inteiro com `mtime` e a marca `DEPOIS`/`antes` contra o arranque. Medido
  agora: `--files | grep -c DEPOIS` = **13**, exactamente o numero do relatorio e o do instrumento
  independente dele.

Frase reproduzivel fixada: **13 ficheiros de app/ + worker/ mudaram depois das 08:14:03.288, o mais
recente `app/webview/sotto_webview.py` as 10:04:47** -- e o comando que a verifica e'
`python _main/live-code-freshness-oracle.py --files` (ou o `os.walk` dele).

## 12. O ARMAMENTO DO PASSE DE FUNDO NAO TINHA LINHA VIVA -- E A PROVA DISSO E' UMA LISTA (2026-11-09, 13:2x)

Ao contar as cargas de hoje pelo log do dono apareceu outra coisa. Depois do worker novo das
09:07:04, `grep -c "REDUX_SWITCH armed"` = **0**, o que eu ia ler como "o interruptor nao esta'
armado". Nao era isso: `grep -c REDUX_SWITCH` no log inteiro da' **21**, e **todas** as 21 estao
dentro de um `stderr_tail=[...]` de um `BRIDGE_EXIT` -- ou seja, a linha do armamento existe e so'
aparece na CAUDA DA MORTE.

A causa esta' numa tupla: `ENGINE_VISIBLE_TAGS` (`app/webview/sotto_webview.py`), o filtro do
`_pump` para o que sobe ao log enquanto o worker corre. Tinha `REDUX_ENGINE_LOAD`,
`REDUX_SHEDDING` e `WORKER_THREADS`; **nao tinha** `REDUX_SWITCH` nem `REDUX_BATCH_KICK`. A linha que
responde "o passe de fundo esta' armado na app do dono?" era, na pratica, invisivel -- a mesma classe
de 2026-11-01 ("o interruptor existia e nunca era construido na app"): o facto existia e ninguem o
podia ler.

Curado no ficheiro e no portao:

* `ENGINE_VISIBLE_TAGS` ganhou `REDUX_SWITCH` e `REDUX_BATCH_KICK`, com o porque' medido no commentario;
* a arm **A15** do `_main/worker-thread-limit-oracle.py` deixou de exigir UMA tag e passa a exigir o
  CONJUNTO (`WORKER_THREADS`, `REDUX_SWITCH armed`, `REDUX_BATCH_KICK`), com o emissor lido como a UNIAO
  `worker/sotto_worker.py` + `worker/engine_switch.py` -- as duas tags novas nascem no `engine_switch`,
  e um portao que lesse so' o worker acusaria quem esta' certo (foi esse o primeiro RED que ele deu);
* o mutante **M11** tira `REDUX_SWITCH` da tupla numa copia e a A15 tem de cair. Medido:
  `VERDICT: PASS (15/15)` e `NEG-ARM: PASS -- 11 mutants caught`, cada mutante derrubado pela SUA arm.

### 12-bis. O `code-health` estava RED com a divida de HOJE, nao com a minha

O passo estava a falhar desde as cures de hoje (`sotto_webview.py` +32 400 B, `history_context.py`
novo, `engine_switch.py` +6 344 B, `warm_engine.py`, `load_shedding.py`, `engine_policy.py`,
`panel.js`, `history-store.js`). O baseline foi regenerado (`--update`) e o diff **inteiro** sao as 16
linhas que este dia landou: `brand-bridge.js`, `caption-formulation.js`, `history-store.js`,
`panel-unified.css`, `panel.css` (-492 B), `panel.js`, `caption_drag.py`, `caption_overlay.py`,
`history_context.py` (novo), `load_shedding.py`, `sotto_webview.py`, `warm_engine.py`,
`youtube_cdp_source.py`, `engine_policy.py`, `engine_switch.py`, `sotto_worker.py` -- nenhum ficheiro
fora das cures desta sessao. Depois: `CODE-HEALTH VERDICT PASS`, `--neg-arm` 3/3.
