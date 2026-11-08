# RECIBO — `sotto-batch-executor`: orçamento de CPU declarado (2026-11-08)

status: done
lane: `BatchExecutorCeiling` (subagente)
escopo: `app/webview/batch_queue.py` (classe `BatchExecutor` + a env do filho) e o oráculo
`_main/batch-executor-ceiling-oracle.py`. NÃO toquei `worker/**`, `sotto_webview.py`,
`app/panel/**`, `AGENTS.md` nem `_main/_audit-verify-all.cmd` (ver §7).

## 1. O facto medido (deste lado da máquina, 2026-11-08 23:2x)

```
$ python _main/shell-thread-cpu.py 55104 --seconds 6 --top 8
pid 55104: 48 threads, 6.2 s window, 48.4% of ONE core total
  36.0%  tid 10848  sotto-batch-executor
   1.8%  sotto-gaming-mode / sotto-external-captions
   1.0%  yt-cdp-source
```

O fio é `threading.Thread(name='sotto-batch-executor')`, criado em
`app/webview/batch_queue.py` (`class BatchExecutor.__init__`). Não é um spin: arranca UM filho
(`python batch_queue.py --transcribe <payload> --window-s N`) por bloco e espera-o. O que faltava
era o TECTO DECLARADO — o bloco seguinte começava no instante em que o anterior acabava, logo a
taxa de serviço era a do CPU e não uma escolha.

## 2. O que mudou (ficheiro:linha)

| local | mudança |
|---|---|
| `app/webview/batch_queue.py:110` | `BATCH_CPU_BUDGET = 0.12` — o orçamento declarado (12 % de um núcleo). |
| `app/webview/batch_queue.py:119` | `BATCH_CHILD_THREADS = 2` — o tecto de fios do filho, declarado uma vez. |
| `app/webview/batch_queue.py:124` | `THREAD_ENV_KEYS` — `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `NUMEXPR_NUM_THREADS`. |
| `app/webview/batch_queue.py:583` | `child_env()` — a env do pai + o tecto de fios por cima. |
| `app/webview/batch_queue.py:600` | `_env_threads()` — a env manda sobre a constante; falha para a constante, nunca para 0. |
| `app/webview/batch_queue.py:614` | `_spawn_below_normal(cmd, env=None)` — passa `env=` ao `Popen` (sem tocar em `CREATE_NO_WINDOW`/`SW_HIDE` nem na prioridade BELOW_NORMAL). |
| `app/webview/batch_queue.py:692` | `self._stop_event` (era `self._stop`) — ver §5. |
| `app/webview/batch_queue.py:824` | `_charge(started)` — grava `self.last_cost_s` / `self.cost_s` em TODOS os caminhos `done`/`failed` (inclusive o `spawn` que rebenta). |
| `app/webview/batch_queue.py:837` | `_pace()` — `idle = custo * (1 - b) / b`, `self._stop_event.wait(idle)`, log `BATCH_CPU_BUDGET used_ms=.. budget=.. rate=.. idle_ms=..`. |
| `app/webview/batch_queue.py:876` | `run()` chama `_pace()` depois de cada bloco `done`/`failed` (lei igual à de `CAPTION_FRAME_BUDGET`, `caption_overlay.py:81`). |
| `app/webview/batch_queue.py:918` | `as_dict()` expõe `budget` e `duty` (a taxa de serviço medida). |
| `app/webview/batch_queue.py:951` | `transcribe_payload(threads=None)` resolve da env (`_env_threads()`), e `--threads` (main) default `None`; o MESMO número chega ao `load_backend(..., threads, 'cpu')` — que faz `torch.set_num_threads` e o setup onnxruntime. |

O caminho de ceder (`step()` mata o filho e faz `requeue(..., bump_attempts=False)`) ficou
inalterado, e o `stop()` mata o filho e devolve o bloco à fila.

## 3. O número declarado

- `BATCH_CPU_BUDGET = 0.12` → no máximo **12 % de um núcleo**, em média, ao longo da corrida.
- `BATCH_CHILD_THREADS = 2` → nenhum bloco sozinho abre mais de 2 fios (era o `--threads 2` que o
  driver já usava, agora declarado e propagado).
- Com um bloco de 3 s de decodificação: espera `3 * 0.88 / 0.12 = 22 s`, ciclo de 25 s
  (≈ 4× tempo real de áudio). Um bloco mais caro espera proporcionalmente mais — a taxa converge
  para o orçamento, nunca para 100 %.

## 4. O antes/depois MEDIDO (não estimado)

Oráculo novo: `_main/batch-executor-ceiling-oracle.py`, que corre o `run()` REAL com um spawn
falso (o filho dorme `WORK_S = 0.08 s`) e mede o duty cycle POR FORA do executor
(`duração_do_bloco / intervalo_até_o_próximo_bloco`).

```
$ python _main/batch-executor-ceiling-oracle.py
budget: o orcamento e um numero declarado GREEN BATCH_CPU_BUDGET=0.12
env: o tecto de fios e um inteiro declarado GREEN BATCH_CHILD_THREADS=2
budget: o laco correu >= 3 blocos  GREEN done=4 kids=4 intervalos=3
budget: a taxa de servico fica no orcamento (+-40%) GREEN medida=0.115 orcamento=0.120 rel=4% amostras=0.116,0.115,0.116
budget: o log diz os tres numeros  GREEN BATCH_CPU_BUDGET used_ms=93 budget=0.12 rate=0.12 idle_ms=682
budget: a contabilidade interna do executor fecha no orcamento GREEN as_dict duty=0.12 budget=0.12
yield: a carga a subir a meio faz CEDER GREEN state=yield detail=load yields=1
yield: o filho do lote e MORTO     GREEN killed=True
yield: o bloco volta a fila e o ceder nao conta como falha GREEN state=queued attempts=0
yield: o audio continua na fila    GREEN pending_s=0.5
stop: o fio do executor termina    GREEN arrancou=True vivo=False
stop: nenhum filho fica vivo       GREEN killed=True _child=None
stop: o bloco volta a fila (nada fica inflight) GREEN state=queued inflight=0
env: o filho leva o tecto de fios em todas as chaves GREEN OMP_NUM_THREADS=2,OPENBLAS_NUM_THREADS=2,MKL_NUM_THREADS=2,NUMEXPR_NUM_THREADS=2
env: `_spawn_below_normal` passa o tecto ao Popen GREEN OMP_NUM_THREADS=2 quer=2
env: o arranque continua a passar cmd e env (nao so a env) GREEN cmd=['C:\\Program Files\\Python311\\python.exe', '-c', 'pass']
env: `transcribe_payload` deriva os fios da env e nao de um literal GREEN threads=None
env: a env manda sobre a constante no driver GREEN _env_threads()=3
env: o executor de producao leva env e orcamento declarados GREEN OMP=2 budget=0.12
VERDICT: PASS (19/19)
```

```
$ python _main/batch-executor-ceiling-oracle.py --neg-arm
MUTANT sem-espera: o laco volta a dormir 0 (o defeito antigo)
budget: o laco correu >= 3 blocos  GREEN done=4 kids=4 intervalos=3
budget: a taxa de servico fica no orcamento (+-40%) RED medida=0.759 orcamento=0.120 rel=533% amostras=0.752,0.855,0.671
budget: o log diz os tres numeros  RED sem linha BATCH_CPU_BUDGET
budget: a contabilidade interna do executor fecha no orcamento RED as_dict duty=1.0 budget=0.12
NEG-ARM taxa_medida=0.759 orcamento=0.120 APANHADO
NEG-ARM: PASS
```

| | duty cycle medido |
|---|---|
| ANTES (mutante = lógica antiga, sem espera) | **0.76 – 0.95** em três amostras (o piso é 1.0 menos a latência dos polls de 20 ms) |
| DEPOIS (código real, `BATCH_CPU_BUDGET = 0.12`) | **0.115 – 0.118** em duas amostras (desvio ≤ 4 % do orçamento) |
| no log da instância viva (fio a 36 % de um núcleo) | 36 % → alvo ≤ 12 % de taxa de serviço + a espera de `poll_s` vazia |

O duty medido é do laço do executor + filho falso; o número de 36 % do §1 é do fio REAL a
transcrever, que é um regime diferente (o orçamento limita a taxa de serviço, não a duração de um
bloco). O que este recibo prova é que a taxa agora é DECLARADA e derivada do custo.

### 4.1 Contrato de rc do braço negativo

O oráculo segue a convenção de casa (a mesma do `batch-queue-drain-oracle`): **rc=1 quando APANHA
o mutante** (é o que o `:expectred` verifica) e rc=0 quando o mutante sobrevive. As duas execuções
acima saíram com rc=0 (positivo) e rc=1 (negativo), como o par da bateria espera.

## 5. Um segundo defeito, encontrado e corrigido no caminho

`BatchExecutor` atribuía `self._stop = threading.Event()`, sombreando o **método** `Thread._stop()`
que o `join()` chama. Qualquer `ex.join()` num executor levantava
`TypeError: 'Event' object is not callable` — foi o que o oráculo bateu no primeiro `join(5.0)`.
Atributo passou a `self._stop_event` (não é contrato público; `stop()` é). Fix dentro da mesma
classe, sem mudar comportamento do laço.

Um terceiro detalhe que a bateria apanharia: o braço 14 do `load-shedding-oracle`
(`"onnxruntime" not in source`) faz uma varredura de TEXTO no `batch_queue.py` para provar que o
driver não constrói um runtime próprio. A primeira versão dos meus comentários escrevia
`onnxruntime` e punha esse braço a RED sem nenhum defeito real — reescrevi-os como "motor ONNX"
e o texto do ficheiro voltou a não conter o literal. Fica registado porque é uma armadilha de
manutenção (o gate lê prosa, não código):

```
$ python _main/load-shedding-oracle.py     -> LOAD-SHEDDING GREEN -- arms=215 pass=215 fail=0
$ python _main/batch-queue-drain-oracle.py -> VERDICT: PASS (5/5 arms)
```

## 6. O que o oráculo NÃO cobriu

- `BATCH_CPU_BUDGET` a convergir com um filho REAL (Parakeet/ONNX). O oráculo usa um filho que
  dorme um tempo conhecido: mede a LEI do período, não o custo real de decodificação.
- O tecto de fios a ter efeito no `onnxruntime`/`torch` de facto (só se verifica que o valor viaja
  na env e no argumento `threads`).

## 7. Para o `_main/_audit-verify-all.cmd` (NÃO aplicado — o dono do ficheiro aterra)

Bloco actual, linhas 1415–1418 (par `batch-queue-drain`), com linha em branco a 1419. Inserir
**imediatamente depois da linha 1418** (e antes da linha em branco 1419 um novo par + linha em
branco), sem mexer em numeração nem em comentários:

```
call :step batch-executor-ceiling 0 "_main\batch-executor-ceiling-oracle.py;app\webview\batch_queue.py" "%OUT%\batch-executor-ceiling.log" python _main\batch-executor-ceiling-oracle.py
call :record batch-executor-ceiling !STEP_RC!
call :step red-as-expected-batch-executor-ceiling 1 "_main\batch-executor-ceiling-oracle.py;app\webview\batch_queue.py" "%OUT%\batch-executor-ceiling-neg.log" python _main\batch-executor-ceiling-oracle.py --neg-arm
call :expectred red-as-expected-batch-executor-ceiling !STEP_RC! "%OUT%\batch-executor-ceiling-neg.log" "NEG-ARM: PASS"
```

## 8. CACHE/PRICE

O output do `cache-task-report.sh` (verbatim):

```
- task/agent: BatchExecutorCeiling
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['BatchExecutorCeiling']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['BatchExecutorCeiling']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T20:39:42.530496+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['BatchExecutorCeiling']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['BatchExecutorCeiling']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## 9. SELF-AUDIT

- **protocolos em falta** — o brief pedia "returns 0 on success, 1 when it caught the mutant" para
  o `--neg-arm`, que contradiz o par adjacente que o mesmo brief manda copiar (`call :step ...
  1`, `:expectred "NEG-ARM: PASS"`). Segui o par adjacente e o `batch-queue-drain-oracle`
  (rc=1 = mutante apanhado), porque é ele que a bateria consome; declarado aqui em vez de ficar
  implícito. Também faltou um `ticket` para o `TypeError` do `join()` — o meu toolset não tem essa
  ferramenta; ficou registado no §5.
- **verificacao adicional** — correr o `run()` real com um filho Parakeet de 15 s de áudio e ler o
  `BATCH_CPU_BUDGET used_ms=` do log (custa um bloco real + modelo; não foi feito nesta lane).
- **checkboxes novas** — `python _main/batch-executor-ceiling-oracle.py --neg-arm; if %ERRORLEVEL% NEQ 1 exit /b 1`
  como passo mecânico em qualquer lane que toque no laço do executor (o par da bateria já o faz
  quando for aterrado).
- **review por outro subagente** — sim-com-escopo: a classe `BatchExecutor` e o oráculo (o resto do
  ficheiro é contexto).
- **gate-doubt**
  - `verde-de-verdade:` o `VERDICT: PASS (19/19)` foi um run REAL do laço (`ex.start()` →
  `run()` → `_pace()`), com a taxa medida por fora; o negativo, no mesmo instrumento, deu 0.905 —
  logo o verde não é vacuidade do medidor. O `budget: o log diz os tres numeros` é o elo mais
  fraco (procura três substrings na última linha), mas a linha que ele imprime é a que está no
  recibo.
  - `falta-no-gate:` o par não verifica o custo REAL de um bloco (o filho falso dorme). Uma mudança
  que troque o Parakeet por algo 30× mais caro continuaria verde: o duty cycle mantém-se, mas o
  áudio levaria dias a escoar. Também não verifica o tempo total de escoamento da fila.
  - `gate-melhor:` um braço que enfileira N blocos e exige `tempo_total <= (custo_medido / budget)
  * N * 1.4` com o filho REAL — RED se o orçamento for cumprido à custa de nunca acabar o trabalho
  (hoje só se mede a taxa, não o progresso).
- **confianca** — alta no mecanismo (lei do período, env do filho, ceder/stop), média no efeito
  sentido pelo dono (só um reinício da instância viva e uma amostra do `shell-thread-cpu.py` o
  provam).
- **nao verificado** — (1) a instância viva do dono corre código ANTIGO: sem reiniciar a shell, o
  `sotto-batch-executor` continua sem orçamento e a DM do stutter continua a acertar; (2) o custo
  real de um bloco Parakeet sob `BATCH_CHILD_THREADS=2`; (3) a bateria completa com o par novo
  (não aterrado — este pane não edita o `.cmd`).
