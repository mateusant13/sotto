# UM ORCAMENTO DE ASR PARA O PROCESSO -- e um portao que o faz cumprir

status: done
owner: EngineSerialization (subagente), 2026-11-09
files:
  - `worker/engine_switch.py`  (orcamento `asr_budget`, portao `asr_admit`, proxy
    `AsrSerializedEngine`, `_wait_for_live`, `_park`, `_batch_admission`,
    `_defer_for_live`, `_resolve_budget`)
  - `worker/sotto_worker.py`   (o interruptor recebe `asr_threads=current_threads()`;
    `run_chunk` marca o batimento do passe ao vivo)
  - `_main/engine-serialization-oracle.py`  (19 bracos + `--neg-arm` de 13 mutantes)

## O DEFEITO, pelo ficheiro e linha onde o laco o produzia

`worker/sotto_worker.py:6205` `resume_catch_up()` e' chamada **a cada bloco de
audio (10 Hz)** pelo laco do audio, e na borda do `PARK_LEVELS` faz:

    worker/sotto_worker.py:6233   started = bool(switch.flush_pending('load-resume'))

`worker/engine_switch.py:1308` `flush_pending` e' o unico caminho que arranca o
motor de LOTE (`:1430` `_start_pass` -> thread `redux-batch` ->
`engine_policy.run_engine_pass`), e o seu proprio docstring diz que corre nos
DOIS modos ("the tail is the point"). Ou seja: a retoma (`load-resume`, `:6233`)
e a cauda (`stream-end`, `:7864`) arrancavam o parakeet **com o motor AO VIVO a
decodificar no mesmo processo** -- e uma janela do lote leva **2,40 s** de parede
medidos, contra um chunk de 0,56 s do stream. Nao ha escala de tempo em que os
dois "se intercalem": durante todo o dreno do backlog os dois passes queimavam
nucleo ao mesmo tempo.

MEDIDO no log do DONO (pid 37112, 18:59:28 -> 20:36): CINCO `REDUX_BATCH_KICK`
(`20:14:33 audio_s=483.92`, `20:20:35 540.52`, `20:25:57 566.8`, `20:30:09 303.12`,
`20:35:09 170.92`) e **ZERO `REDUX_ENGINE_DONE`** -- nenhum passe do lote chegou
ao fim naquela execucao, e o pendente caiu porque `take_pending` ja' tinha
LIMPO a fila. Causa no mesmo ficheiro: o `except BaseException` de
`run_engine_pass` chama `sw._park(...)`, **metodo que nunca existiu**; e a partir
do primeiro `park` publicado pela shell (`self._park = park`, string) nem o
`AttributeError` era o que saia. O handler que existe para devolver o audio
morria, a thread `redux-batch` com ele, e os segundos daquele passe ficavam no
vazio. Curado em `engine_switch.py:967` `_park` (delega a
`engine_policy.park_pass`) + `self._park_reason` para o campo publicado.

## O ORCAMENTO, como NUMERO

```
asr_budget(2) = {'total': 2, 'live': 2, 'small': 1, 'batch': 2}
```

  * UM numero por PROCESSO: o `--threads` do worker (2 em producao, medido em
    `AGENTS.md`: 2 fios/sessao cortaram o pico de 286,2 % para 174,1 % com o
    MESMO hash de transcricao);
  * `live=2` e' o encoder do stream, INTEIRO: corta-lo mudaria a latencia da
    legenda, que e' o que esta lane nao pode tocar (por isso o passe ao vivo e'
    `grant` em TODOS os estados, A4);
  * `small=1` e' decoder/joint -- o mesmo piso que `session_options` ja' aplica;
  * `batch=min(2, total)`: o lote nao tem numero proprio, recebe a parte do
    MESMO orcamento (`_resolve_budget`);
  * INVARIANTE: o pico de fios de intra-op de UM passe e'
    `max(live, small, batch) == total`, e o PORTAO impede que dois passes o
    usem no mesmo instante (`engine_switch.py:1352`).

O portao tem DUAS metades, e as duas sao necessarias:

  1. `asr_admit` (`engine_switch.py:402`, puro) decide o INICIO de um passe:
     `batch` cede enquanto o ao vivo estiver vivo -- pelo `mode` OU pelo
     BATIMENTO medido (`note_live_decode` em `run_chunk`,
     `live_age_s < ASR_LIVE_FRESH_S = 3,0`), a pior das duas fontes.
  2. `AsrSerializedEngine` (`engine_switch.py:366`) fecha o buraco que o
     portao sozinho deixa: um passe JA' comecado continua quando o ao vivo
     comeca. Medido na sonda com o portao ligado a recusar 465 pedidos e o
     processo a marcar **336,4 %** de um nucleo, com as sessoes do lote quentes
     ao lado das do ao vivo. O proxy faz o lote DORMIR (`_wait_for_live`,
     `:1013`, `time.sleep(0.05)`, 0,0 % de CPU, GIL libertado) no ultimo
     instante antes de carregar e antes de CADA janela; limite de 2,0 s para uma
     CAUDA (que nao tem tick seguinte) nao ficar presa para sempre.

## ANTES / DEPOIS, o mesmo instrumento, a mesma caixa

Instrumento da casa, apontado ao pid da sonda durante cada fase. A sonda usa os
DOIS backends reais (parakeet ONNX int4, 2 fios cada) e o codigo de envio; o
"antes" e' o MESMO codigo com `asr_admit` forcado a `grant` (o defeito), o
"depois" e' o portao a decidir.

    python G:/Temp/sotto-engine-budget/probe2.py 2 <log> 10 nogate   # ANTES
    python G:/Temp/sotto-engine-budget/probe2.py 2 <log> 10 gate     # DEPOIS
    python _main/shell-thread-cpu.py <pid> --seconds 6 --top 8

### ANTES -- pid 35148 (`nogate`, 20:42:35): dois passes a decodificar

```
pid 35148: 34 fios, 6.5 s de janela, 188.0% de um nucleo no total
calibracao: processo mediu 186.3% no mesmo intervalo -> razao 1.01
     pct    cpu_s     tid  nome
   38.0%     2.47   32572  (sem nome)        <- chamador do transcribe (ao vivo)
   35.6%     2.31   43916  (sem nome)        <- chamador do transcribe (lote)
   35.6%     2.31   51176  session-6-intra-op-0   <- lote
   35.3%     2.30   12196  session-2-intra-op-0   <- ao vivo
   11.8%     0.77   35124  session-5-intra-op-0   <- lote
   11.3%     0.73   37852  session-3-intra-op-0   <- ao vivo
    8.9%     0.58   25872  session-1-intra-op-0   <- ao vivo
    8.9%     0.58   42476  session-7-intra-op-0   <- lote
```

`PHASE1_CONCURRENT_END live_windows=3 batch_windows=4 batch_deferred=0` e
`PHASE2_GATED_END ... 200.0 %` com 2+3 janelas. As DUAS familias de sessoes
(1/2/3 do ao vivo, 5/6/7 do lote) quentes no mesmo intervalo: o defeito.

### DEPOIS -- pid 22924 (`gate`, 20:43:48): o lote espera

```
pid 22924: 34 fios, 6.3 s de janela, 142.7% de um nucleo no total
calibracao: processo mediu 137.7% no mesmo intervalo -> razao 1.04
     pct    cpu_s     tid  nome
   49.9%     3.12   42568  session-2-intra-op-0   <- ao vivo (encoder)
   47.6%     2.98   51972  (sem nome)            <- chamador do transcribe (ao vivo)
   23.7%     1.48   48076  session-3-intra-op-0   <- ao vivo
   19.0%     1.19   34028  session-1-intra-op-0   <- ao vivo
    1.7%     0.11   21156  session-8-intra-op-0   <- lote OCIOSO, 1,7 % (nao decodifica)
```

`PHASE1_CONCURRENT_END live_windows=8 batch_windows=0 batch_deferred=390`: o
lote foi recusado 390 vezes e NAO decodificou; as sessoes 5/6/7 nao aparecem na
lista. 188,0 % -> **142,7 %** (o termo do lote, ~45 pontos de um nucleo,
desaparece) e o passe ao vivo fez **8 janelas em 10 s contra 3 em 12 s** do
antes -- o mesmo prazo, com o nucleo que o lote ja' nao ocupa.

`PHASE3` (o ao vivo para, o lote drena): `batch_windows=2`, texto nao vazio
(`batch_sha=ae292e8c4722`) -- o backlog continua a sair, agora sozinho.

### O worker VIVO do dono (pid 37112) -- o numero que isto tem de mover

O worker vivo carregou o codigo as 18:59:28 e nao pode ser reiniciado daqui
(nenhuma janela, nenhum dispositivo). MEDIDO nele, mesmo instrumento:

```
MAIN, 23:3x:   pid 37112: 66 fios, 253.4% de um nucleo
                 77.8%  11616  (sem nome)
                 77.2%  42436  session-9-intra-op-0
                 52.0%  42592  session-10-intra-op-0
                 42.7%  53140  session-8-intra-op-0
EU, 20:56:     pid 37112: 64 fios, 10.3 s de janela, 80.8% no fio amostrado,
                 processo 170.1% no mesmo intervalo (razao 0.47)
                 34.2%  42436  session-9-intra-op-0
                 24.2%  42592  session-10-intra-op-0
                 19.7%  53140  session-8-intra-op-0
EU, 20:37:     28.3% (session-9 10.0%, 10.0% sem nome, session-10 3.5%, session-8 2.5%)
EU, 21:03 (cage pedido pelo Main): `python -m watcher run --cpu 40 -- python
               _main/tree-cost-oracle.py` -> `No module named watcher` (o pacote nao
               existe nesta arvore; `I:/!manager/scripts/watcher` nao e' importavel) --
               CANNOT-CAGE, corrido SEM cage e dizendo-o.
EU, 21:12 (gate do Main): tree=255.4% shell=4.5% worker=250.9% top=session-20-intra-op-2:60.9%
               (`python _main/tree-cost-oracle.py`, mediana de 3 janelas, tecto 250,0 %)
```

TRES de TRES sessoes quentes (8/9/10 = encoder/decoder/joint do motor AO VIVO):
a carga do worker vivo hoje e' o passe ao vivo. O lote tem de esperar por ele --
que e' exactamente o que o portao faz -- e a arvore so' desce abaixo do passe ao
vivo se o passe ao vivo mudar, o que esta lane nao pode tocar (prazo da legenda).

## CENSO DAS SESSOES (o que existe em repouso, e o que o contador diz)

Leitura dos NOMES dos fios (`python _main/shell-thread-cpu.py 37112 --seconds 3
--top 400`), nunca do log (que roda e so' lista eventos):

  20:57  pid 37112, 66 fios: **tres** sessoes, `session-8/9/10-intra-op-0`
         (encoder / decoder / joint do motor AO VIVO), a 34,2 / 24,2 / 19,7 %
         de um nucleo. Nenhuma sessao do lote quente: as dele estao OCIOSAS
         depois do unico `load()` (o parakeet nao volta a ser largado nesta run).
  21:12  `_main/tree-cost-oracle.py`: `top=session-20-intra-op-2:60.9%` -- o
         contador chegou a **20** e existe uma sessao com >= 3 fios de intra-op.

A sessao e' RECONSTRUIDA POR CARGA, nao por kick: `ParakeetEngine.load()`
(`worker/engine_policy.py:222`) devolve o backend em cache (`if self._backend is
not None: return`) e `release()` larga-o; so' o par carga/largada cria sessoes
novas. Na run do dono: `REDUX_ENGINE_LOAD`=1, `REDUX_ENGINE_RELEASE`=0,
`REDUX_BATCH_KICK`=5, `REDUX_ENGINE_DONE`=0 -- nenhuma destas 5 arrancadas
reconstruiu sessoes (uma carga, cinco kicks), e nenhuma acabou (ver o defeito
`_park` acima). MEDIDO, o crescimento 10 -> 20 em ~15 min NAO vem do motor de
lote nem do orcamento: vem de um construtor que nao escreve linha nenhuma. Os
sitios de `InferenceSession` na arvore sao:

    worker/sotto_worker.py:1504/1522/1524   live (StreamAsr, 1x no arranque)
    worker/parakeet_ultra.py:194            preprocessor do motor de lote (2 fios fixos)
    worker/model_vram_pool.py:378           intra_op = OMP_NUM_THREADS (default **8**) -- FORA do orcamento
    worker/speaker_sidecar.py:685           intra_op = numero do chamador -- FORA do orcamento

O ORCAMENTO DESTE TRABALHO GOVERNA DOIS MOTORES: as tres sessoes do stream
(`StreamAsr`, `asr_budget()['live'|'small']`) e o motor de lote
(`asr_budget()['batch']`). Ele NAO governa `model_vram_pool` nem `speaker_sidecar`
-- dois construtores com numero proprio, um deles com 8 fios por omissao. A
sessao `session-20-intra-op-2` (>=3 fios) tem de ser um deles ou um sitio que
ainda nao tem linha de log, e isso e' um bilhete proprio: "um numero por
processo" so' sera verdade quando nenhum construtor de sessao tiver o seu.

### CORRECCAO MEDIDA (Main, 2026-11-09 23:5x): NENHUM dos dois sitios acima pode ser o `session-20-intra-op-2`

A frase acima chama os dois de candidatos. Medido agora, um nao existe em producao e o
outro ja' esta' no numero certo:

    $ grep -rn "model_vram_pool" --include=*.py .
    .\_main\vram-reuse-oracle.py:10   import model_vram_pool as pool     <- o UNICO importador
    .\worker\model_vram_pool.py:211/258                                  <- ele mesmo
    .\app\webview\hot_reload.py:59                                       <- um comentario

O `model_vram_pool.py` tem **ZERO chamadores de producao**: quem o importa e' o portao
`_main/vram-reuse-oracle.py`. O `default 8` dele esta' DORMENTE e nao constroi sessao
nenhuma no worker -- editar esse 8 nao mudaria um fio.

    worker/speaker_sidecar.py:684   def _load_powerset(seg_model: str, threads: int = 2)
                                    opts.intra_op_num_threads = max(1, int(threads))

O sidecar ja' pede 2 por omissao (`threads: int = 2`) e nunca sobe acima do que o
chamador pede. Um 3.o fio (`-intra-op-2`) NAO sai daqui.

Logo: o `session-20-intra-op-2` continua NAO ATRIBUIDO, e o instrumento que o decide e'
uma amostra por fio DURANTE uma janela de CARGA (o unico momento em que sessoes nascem),
nao um palpite sobre dois ficheiros. Fica como bilhete aberto com essa sonda declarada,
e este recibo nao afirma a origem que nao mediu.

## O QUE AINDA FUNCIONA (provado, nao prometido)

  * O TEXTO NAO MUDA. `G:/Temp/sotto-engine-budget/same-text.py` (o motor de
    lote real, a mesma janela de 3 s, por tres caminhos):

        direct      = "('O rádio anunciou que aponte sobre o...', [{'text': 'O rádio anunciou..."
        gated_fast  = "('O rádio anunciou que aponte sobre o...', [{'text': 'O rádio anunciou..."
        gated_slow  = "('O rádio anunciou que aponte sobre o...', [{'text': 'O rádio anunciou..."
        waited_s    = [0.30]
        IDENTICAL   = True

  * O AUDIO DE UM PASSE FALHADO VOLTA (o defeito acima). A15 corre a funcao
    REAL `engine_policy.run_engine_pass` com um motor que estoura: nada escapa,
    `runner_failures=1`, `REDUX_BATCH_FAILED reason=engine-RuntimeError` no log,
    e o que nao foi consumido volta `pending.requeue(...)`.
  * O BACKLOG DRENA QUANDO O AO VIVO PARA: `PHASE3 batch_windows=2` (depois) e
    `9` (antes), com texto; e o `_park` recarrega com backoff, nao num busy loop.
  * A LEGENDA NAO ESPERA: A4 + A16-b (`grant` imediato com o ao vivo parado) e
    o proxy so' faz esperar a thread do LOTE.

## ORACULOS

    python _main/engine-serialization-oracle.py            -> 19/19 arms green, VERDICT: PASS
    python _main/engine-serialization-oracle.py --neg-arm  -> 13/13 mutantes apanhados, rc=1
    python _main/worker-thread-limit-oracle.py             -> VERDICT: PASS (15/15)
    python _main/redux-arm-weights-oracle.py               -> 28/28 green, VERDICT: PASS
    python _main/redux-flag-gate.py                        -> VERDICT GREEN (13/13 claims)

O oraculo extrai as funcoes REAIS por `ast` (`asr_budget`, `asr_admit`,
`_batch_admission`, `_defer_for_live`, `flush_pending`, `_park`, `_wait_for_live`,
`AsrSerializedEngine`, `ReduxHiddenSwitch.__init__`-adjacent wiring) e corre-as;
nunca procura texto no fonte. O `--neg-arm` planta 13 mutantes, UM DIRECTORIO POR
MUTANTE com `sys.dont_write_bytecode` -- eles plantam o mesmo defeito de
instrumento que apanhava este oraculo antes (o `.pyc` do CPython valida por
(mtime INTEIRO, tamanho); dois mutantes do mesmo tamanho, escritos no mesmo
segundo, reaproveitavam o bytecode do anterior e o braco via o mutante errado --
o `M3` "passou" a correr o `M2`).

## PENDENTE (fora do meu alcance: e' commit)

`python _main/code-health-oracle.py --update` recusa com rc=2 porque os dois
ficheiros estao por commitar:

    RED  dirty worktree: 2 entrada(s) mudariam a partir de ficheiro NAO commitado:
         worker/engine_switch.py
         worker/sotto_worker.py
         commit primeiro, `--update` depois -- ou `--allow-dirty` ...
    CODE-HEALTH VERDICT FAIL  (rc=2)

As entradas que o baseline tem de absorver (medidas agora):
`worker/engine_switch.py` bytes 85137 / lines 1583 / defs 14 / max_func 174
(`__init__`, 165 apos o factor `_resolve_budget`; cresceu com os campos do
portao) e `worker/sotto_worker.py` bytes 493511 / lines 9176 / max_func 2752.
Ordem: commitar, `python _main/code-health-oracle.py --update`, e o oraculo verde.

## CACHE/PRICE
- task/agent: EngineSerialization
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['EngineSerialization']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['EngineSerialization']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T23:47:05.895845+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['EngineSerialization']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['EngineSerialization']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## SELF-AUDIT

- **protocolos em falta** -- devia ter desenhado o portao com a peca do ULTIMO
  instante desde o inicio: a primeira versao so' decidia o INICIO do passe, e a
  sonda desmentiu-a (336,4 % com 465 recusas). O protocolo que faltou foi
  "desenha o portao onde o nucleo e' gasto, nao onde a decisao e' tomada".
- **verificacao adicional** -- um par ANTES/DEPOIS com o `ReduxHiddenSwitch`
  REAL e `run_engine_pass` a correr (nao so' `asr_admit`): custa ~2 min e dois
  carregamentos do modelo, e fecharia a distancia entre a sonda e o worker.
- **checkboxes novas** -- (1) `.pyc`/bytecode: todo o harness que escreve um
  mutante para disco tem de usar directorio novo por mutante e
  `sys.dont_write_bytecode = True` (mecanico, e o `M3` falso-verde prova-o);
  (2) todo o `--neg-arm` imprime `RC=$?` e exige 1; (3) todo o par
  antes/depois imprime `calibracao ... razao` -- a razao 0,47 acima diz que a
  amostra de fios perdeu threads e o numero do PROCESSO e' que manda.
- **review por outro subagente** -- sim-com-escopo: o desenho do portao
  (inicio vs ultimo instante) e a colisao `_park`/`_park_reason`.
- **gate-doubt** --
  (a) `verde-de-verdade:` os 19 bracos correm funcoes extraidas por `ast` do
  ficheiro de envio (nao uma copia), e o `--neg-arm` prova que cada braco pode
  ficar RED; o verde do `M3` ANTERIOR era falso e veio de bytecode reaproveitado
  (corrigido com directorio por mutante + `dont_write_bytecode`). O
  `worker-thread-limit-oracle` A14 passou a correr o `main()` real, nao um stub.
  (b) `falta-no-gate:` nada mede o worker VIVO com o orcamento novo -- um
  `--threads 2` nao garante que o lote nunca decodifique ao mesmo tempo no
  processo de verdade; um proximo arranque pode regredir sem nenhum oraculo o
  ver, porque a sonda e' um processo de teste e o braco A16 e' unitario.
  (c) `gate-melhor:` um braco que constroi o `ReduxHiddenSwitch` REAL com os dois
  backends reais e corre `run_engine_pass` enquanto uma thread marca
  `note_live_decode` a 10 Hz, exigindo `max(sessoes_do_lote_quentes)==0` no
  intervalo -- RED se o proxy sair. Comando: `python
  _main/engine-serialization-oracle.py` com esse braco; input que o poe RED:
  M12 (o proxy deixa de esperar).
- **confianca** -- alta no orcamento e no portao de inicio (19 bracos + 13
  mutantes + sonda A/B); media no proxy: provado por A16 e pela sonda `gate`
  (lote a 0 janelas), mas nao com o `run_engine_pass` real.
- **nao verificado** -- o worker VIVO nao pode carregar o codigo novo sem
  reiniciar (nenhuma janela/audio permitidos aqui), por isso o AFTER de registo
  do pid 37112 e' o par da sonda com o MESMO codigo, nao o worker do dono.
  `code-health --update` fica por commitar.
