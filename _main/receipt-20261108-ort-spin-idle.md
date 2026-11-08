# RECIBO — o spin-wait do onnxruntime era um imposto FIXO em repouso

Medido nesta arvore, 2026-11-08. Todo numero aqui saiu de um comando corrido nesta sessao; onde
nao ha' numero, esta' escrito `[INFERENCE]` ou `UNMEASURED`.

## 1. Como o defeito apareceu

O watcher mandou **quatro DMs de stutter na mesma hora**, sempre o mesmo pid. A primeira atribuicao
(por processo) dizia `pythonw.exe(55104)`; a arvore inteira medida por processo mostrou o contrario:

```
$ python  (psutil, 5 s de janela, cpu_times por pid da arvore)
   50.3% de 1 nucleo  pid=7144   fios=80   python.exe      <- o WORKER, 2,3 GB
   13.8% de 1 nucleo  pid=55104  fios=52   pythonw.exe     <- a shell
    0.6% de 1 nucleo  pid=22764  fios=51   msedgewebview2.exe
   TOTAL 64.7% de 1 nucleo = 3.2% da maquina (20 logicos)
```

E a atribuicao por FIO -- que o `watcher profile` **nao** consegue fazer (`psutil.Process.threads()`
devolve 0 tid com `num_threads()=48`) e o instrumento da casa faz:

```
$ python _main/shell-thread-cpu.py 7144 --seconds 6 --top 10
pid 7144: 80 fios, 6.2 s de janela, 57.4% de um nucleo no total
   19.8%  tid 47092  session-29-intra-op-0
   19.3%       ---   (sem nome)
    8.0%  tid 54216  session-30-intra-op-0
    4.3%  tid 62608  session-28-intra-op-0
```

Tres sessoes (`encoder`, `decoder`, `joint`) e os fios do pool intra-op do ORT **a girar**.

## 2. A medicao isolada, com e sem spin

Sem dispositivo, sem audio, sem janela: so' construir as tres sessoes reais e ficar parado 6 s.

| configuracao | ocioso | fios |
|---|---|---|
| `SPIN ON` (padrao do ORT) | **16,1 % de um nucleo** | 17 |
| `SPIN OFF` (`allow_spinning=0`) | **0,0 % de um nucleo** | 17 |

O preco do passivo, medido no mesmo dia (300 chamadas seguidas num grafo `40x64`, 3 repeticoes, melhor):

| configuracao | por chamada |
|---|---|
| `SPIN ON` | **40,0 us** |
| `SPIN OFF` | **73,4 us** (+33,5 us) |

**A ARITMETICA QUE DECIDE:** um chunk e' de 560 ms; ~300 chamadas por chunk dao **~10 ms** de custo
extra (+1,8 % da janela) contra **16 % de um nucleo que nunca mais se devolve**. O orcamento de
latencia da casa e' 1 500 ms, e 10 ms nao o move. O spin e' o lado errado da troca para um motor que
passa a maior parte do tempo parado entre chunks.

## 3. A cura, e onde ela vive

| ficheiro | o que mudou |
|---|---|
| `worker/sotto_worker.py` (cabecalho, junto do `OMP_NUM_THREADS`) | `os.environ.setdefault("OMP_WAIT_POLICY", "PASSIVE")` — o ORT usa o OpenMP para a mesma espera, e o `setdefault` deixa o ambiente do dono ganhar |
| `worker/sotto_worker.py:session_options()` | `session.intra_op.allow_spinning=0` e `session.inter_op.allow_spinning=0`, nas DUAS sessoes de cada grafo (o builder e' chamado uma vez por grafo) |

Nada mais mudou: threads intra-op continuam 4 (`OMP_NUM_THREADS`), `inter_op` continua 1,
`graph_optimization_level` continua como estava (encoder BASIC, resto ALL).

## 4. O portao

`_main/ort-spin-idle.py` — executa o `session_options()` do PROPRIO worker e constroi as tres
sessoes reais (grafos de 2,7 MB no total; nenhum dispositivo e' aberto):

| arm | o que exige | medido |
|---|---|---|
| A1 `tres-sessoes-constroem` | as tres sessoes sobem | GREEN `sessoes=3` |
| A2 `ocioso-dentro-do-tecto` | <= 3 % de um nucleo em repouso | GREEN `ocioso=0.0%` |
| A3 `as-duas-chaves` | `SessionOptions` carrega as duas chaves a `0`, lidas por `get_session_config_entry` | GREEN `intra_op=0, inter_op=0` |
| A4 `omp-passivo` | o cabecalho do worker, executado num filho com o ambiente LIMPO, deixa `PASSIVE`; com a variavel ja' posta, **nao** se sobrepoe | GREEN `automatico='PASSIVE' com-a-variavel='ACTIVE'` |

`--neg-arm`: escreve uma copia do worker sem as duas chaves e sem o `setdefault` e exige o vermelho:

```
A2 ocioso-dentro-do-tecto     RED   ocioso=18.4% tecto=3.0% de 1 nucleo
A3 as-duas-chaves             RED   ... does not have configuration with key ...
A4 omp-passivo                RED   automatico='' com-a-variavel='ACTIVE'
NEG-ARM: PASS -- mutacoes=2     (rc=1)
```

O mutante reproduz o defeito **e** e' apanhado por tres arms; o ficheiro real passa as quatro.

## 5. O que NAO esta' verificado

* **A instancia viva do dono continua com o codigo ANTERIOR.** `python _main/live-code-freshness-oracle.py
  --strict` -> `LIVE_CODE STALE pid=55104 started=2026-11-08 13:38:36`, `processo sha256=1C4A7E1DAE1C`
  contra `disco FD56234EEB84`. O pool so' deixa de girar na proxima largada; **UNMEASURED no processo vivo**.
* O custo real por bloco **com esta cura** nao foi medido dentro do worker (o oraculo mede o
  `SessionOptions` e o repouso, nao a inferencia). O numero de 33,5 us/chamada e' de um grafo sintetico
  `40x64`; o custo dos grafos reais e' `[INFERENCE]` na mesma ordem.
* `code-health`: o crescimento declarado foi pinado no baseline para os dois ficheiros tocados
  (`worker/sotto_worker.py` +1 249 B / +19 linhas / +1 `except_pass`; `app/webview/batch_queue.py`
  +7 087 B / +152 linhas / +2 `defs`, do tecto do lote que a lane irma' entregou) e o juiz passou
  `CODE-HEALTH VERDICT PASS`.
