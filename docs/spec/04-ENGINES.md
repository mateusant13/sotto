# 04 - MOTORES: os dois transcritores, e o que custam

Este documento responde a uma pergunta: com o código em `HEAD`, **quem transcreve o quê, em que
condições, com que memória e a que preço de CPU**. O não medido está em `## Lacunas`, como `[UNKNOWN]`.

## 1. O que existe no disco, e o que o código procura

| motor | papel | caminho que o código abre | tamanho em disco |
|---|---|---|---|
| nemotron 3.5 ASR pt-BR (ONNX int4) | **ao vivo** (streaming) | `worker/models/nemotron-3.5-asr-ptbr-onnx-int4` (lido de `worker/config.json`) | `793359414` B |
| parakeet redux (ONNX int4) | **lote** (in-process) | `worker/models/parakeet-redux-onnx-int4` | `436071656` B |
| parakeet redux (ternário) | lote, processo filho | `worker/models/parakeet-redux-ternary` | **não existe** |

`[MEASURED]` 2026-11-11, `du -sb` dos dois `worker/models/...` → `793359414` e `436071656` B;
`ls worker/models` não mostra `parakeet-redux-ternary`.

O motor ao vivo lê o contrato do checkpoint, não uma constante: `blank_id`, `chunk_samples` e
`max_symbols_per_step` `[CODE] worker/sotto_worker.py:1570-1573`.

O lote prefere o parakeet in-process e só cai para o runner quando o parakeet não está no disco
`[CODE] worker/engine_switch.py:770-772`.

O runner ternário é outro programa, com o contrato `--wav PATH [--json] [--model-dir DIR]`
`[CODE] worker/redux_batch.py:13`, e o caminho por omissão dele é o checkpoint **ternário**
`[CODE] worker/redux_batch.py:39`, que não existe nesta árvore; o runner recusa carregar sem
`config.json`, `model.safetensors` e `ternary.json` `[CODE] worker/redux_batch.py:112-120`.

`[INFERENCE]` Nesta máquina o lote corre sempre no processo do worker, sobre o ONNX int4; o
runner ternário é reserva que não carrega até o checkpoint existir.

## 2. A política: quem transcreve este bloco

O worker só constrói o interruptor com opt-in explícito: `redux_optin = bool(args.redux_when_hidden)
or (SOTTO_REDUX_WHEN_HIDDEN == "1")`; sem nenhum, `switch = None` e o worker é o de streaming de
sempre `[CODE] worker/sotto_worker.py:8188-8200`.

Na app que o dono corre, quem liga esse canal é a acção de carga, antes de o shell lançar o filho
`[CODE] app/webview/load_shedding.py:1201-1204`. `[MEASURED]` 2026-11-11,
`grep -c "LOAD_ACTION_WORKER_CHANNEL" _main/webview-run.log` → `13`, todas
`source=load_action SOTTO_REDUX_WHEN_HIDDEN=1`.

As três portas de armar, e o que as mantém fechadas `[CODE] worker/engine_switch.py:629-645`:

| porta | condição | consequência quando falha |
|---|---|---|
| 1. flag/ambiente | `--redux-when-hidden` ou `SOTTO_REDUX_WHEN_HIDDEN=1` | não há interruptor nenhum; streaming puro |
| 2. motor de fundo no disco | parakeet ONNX **ou** runner + checkpoint ternário | `REDUX_SWITCH_REFUSED armed=false` e o streaming **não** é cortado |
| 3. ficheiro fresco e escondido | `panel-visibility.json` fresco e `visible=false` | um ficheiro morto lê como VISÍVEL; falha para o lado do streaming |

A expressão que arma, pinada por oráculo: `self.armed = bool(self.enabled and
self.runner_available and self.model_available or (self.enabled and self.engine_available))`
`[CODE] worker/engine_switch.py:786-788`. A recusa distingue runner de checkpoint:
`reason=runner-missing` / `reason=checkpoint-missing`, ambos com o caminho `[CODE]
worker/engine_switch.py:879-891`.

**O que o modo decide, e o que ele NÃO decide.** O mapeamento é `shed=="muito-alta"` → `"shed"`,
`shed=="alta"` → `"batch"`, resto → `"stream"`, com a excepção da visibilidade: `hidden_after_s`
só entra se `unload_when_hidden` for verdadeiro `[CODE] worker/engine_switch.py:1000-1005`. E
`unload_when_hidden` é `False` por omissão `[CODE] worker/engine_switch.py:675` e o `main()` do
worker **não** o passa `[CODE] worker/sotto_worker.py:8194-8219`. `[INFERENCE]` Logo, em `HEAD`, o
painel escondido 20 s **não** põe o worker em `batch`; só a carga (`alta`) ou o estacionamento das
legendas o fazem, porque o modelo ao vivo só é largado por pressão `[CODE]
worker/engine_switch.py:682-688`.

No modo `batch` o bloco **não** é descodificado: entra em `switch.add_audio(block)` +
`maybe_kick()` e o `continue` salta o decode do stream `[CODE] worker/sotto_worker.py:8007-8012`.
No modo `shed` entra em `switch.add_audio(block)` e `continue`, **sem** `maybe_kick` `[CODE]
worker/sotto_worker.py:8014-8020`. Em qualquer dos dois a captura continua: o tap não é tocado
`[CODE] worker/engine_switch.py:625-627`.

## 3. O lote: acordar, ceder a vez, e o piso da recarga

O valor por omissão de cada botão, todos nomeados no topo do módulo `[CODE]
worker/engine_switch.py:149-205`:

| constante | valor | o que mede |
|---|---|---|
| `REDUX_BATCH_INTERVAL_DEFAULT_S` | `15.0` | tecto inferior de áudio por passe de fundo (`REDUX_MAX_AUDIO_DEFAULT_S = 120.0` limita a RAM antes do spool) |
| `REDUX_MIN_AUDIO_S` | `1.0` | abaixo disto não vale acordar o modelo |
| `REDUX_BATCH_PASS_MAX_S` | `30.0` | áudio que **um** passe leva; o resto fica na fila |
| `REDUX_MIN_FREE_MB_DEFAULT` | `4600.0` | piso de memória do runner ternário |

O piso de memória é **do motor que vai correr**, não um número só: `floor_mb =
self.engine_min_free_mb if self.batch_kind == "parakeet" else self.min_free_mb` `[CODE]
worker/engine_switch.py:1436-1439`, e o do parakeet é `800.0` MB porque o pico medido do export é
~615 MB `[CODE] worker/engine_policy.py:34-36`.

`maybe_kick` é o único chamador que respeita o piso de memória, porque é o único que pode esperar:
`if not self.armed or self.mode != "batch"` sai, `pending_seconds() < batch_interval_s` sai, senão
`flush_pending(reason, respect_memory_floor=True)` `[CODE] worker/engine_switch.py:1307-1313`.

As razões de adiamento, todas com linha própria:

| razão | quando | o áudio |
|---|---|---|
| `REDUX_BATCH_DEFERRED reason=<live>` | o passe ao vivo está a decodificar (ou acabou de) | fica na fila, o tick seguinte tenta |
| `REDUX_BATCH_DEFERRED reason=reload-floor` | o motor foi largado há menos de `max(60 s, 10 × load_s)` | fica na fila |
| `REDUX_BATCH_DEFERRED reason=low-memory` | livre < piso do motor | fica na fila |
| `REDUX_BATCH_RELOAD_FLOOR` / `REDUX_BATCH_LOW_MEMORY` `attempting=anyway` | cauda (sem tick seguinte) dentro de um piso | tenta mesmo assim e di-lo |

`[CODE]` as três primeiras em `worker/engine_switch.py:1344-1349`, `:1414-1422`, `:1448-1455`; as
duas caudas em `:1424-1433` e `:1456-1465`.

**O piso da recarga é a cura de um ciclo medido.** `reload_floor_left()` devolve
`max(RELOAD_FLOOR_S, RELOAD_FLOOR_LOAD_FACTOR * load_s)` menos o tempo desde a largada, com `60.0`
s e factor `10.0` `[CODE] worker/engine_policy.py:251-262`, `:54-58`. A largada **nunca** é
recusada: `release()` cai a referência ao backend e escreve `REDUX_ENGINE_RELEASED` com
`rss_before_mb`/`rss_after_mb` `[CODE] worker/engine_policy.py:265-286`. O ciclo que isto corta
está medido no
recibo: `REDUX_ENGINE_LOAD 82` / `REDUX_ENGINE_RELEASE 70` numa execução, par mais apertado a 31 s
`[MEASURED]` `_main/receipt-20261109-reload-floor.md:12-18` (2026-11-09).

`[MEASURED]` 2026-11-11 23:40, sobre `_main/webview-run.log` (25 439 116 B):

```
LOADS        31   load_s min 0.84  mediana 2.93  max 19.35
RSS pós-carga     min 492.5 MB   mediana 1524.9 MB   max 2463.8 MB
RELEASES     14   MB devolvidos mediana 465.4  min -20.6  max 514.2
```

A linha que o lote deixa quando corre: `REDUX_BATCH_KICK reason=interval engine=parakeet
audio_s=15.0 kicks=488 held_in=186962 asr_waits=0 asr_wait_s=0.0 asr_expired=0 pid=42180`
`[MEASURED]` `_main/webview-run.log`, 2026-11-11 22:45:46; `grep -c REDUX_BATCH_KICK` → `838`.

`REDUX_MODE` não chega ao log vivo: `ENGINE_VISIBLE_TAGS` não o inclui `[CODE]
app/webview/sotto_webview.py:1588-1646`, e `grep -c` → `0` `[MEASURED]` 2026-11-11; o número
contável de mudanças de modo é `switches`, na cauda de morte de cada `BRIDGE_EXIT`.

## 4. O orçamento de fios, e a serialização dos dois passes

O worker resolve o orçamento **uma vez**: `--threads N` (N>0) > `OMP_NUM_THREADS` do ambiente > 4
`[CODE] worker/sotto_worker.py:718-733`, aplica-o antes de importar numpy/ORT `[CODE]
worker/sotto_worker.py:653-687`, e o log diz quem decidiu: `WORKER_THREADS threads=%d source=%s`
`[CODE] worker/sotto_worker.py:6821`. A shell entrega `--worker-threads 2` por omissão e só emite
a flag quando o valor é > 0 `[CODE] app/webview/sotto_webview.py:23039-23043`,
`app/webview/sotto_webview.py:25519`.

O defeito que isto corrige está medido no código: o `--threads N` era **inerte** porque um
`setdefault("OMP_NUM_THREADS","4")` anterior ganhava e as três sessões abriam com 4 fios cada
`[CODE] worker/sotto_worker.py:656-663`.

O orçamento é **um número** e é dividido, não somado: `asr_budget(total)` devolve
`{'total': total, 'live': total, 'small': 1, 'batch': min(2, total)}`, com o invariante
`max(live, small, batch) == total` e o portão a impedir dois passes no mesmo instante `[CODE]
worker/engine_switch.py:311-327`. O default do orçamento é `REDUX_LIVE_THREADS = 2` `[CODE]
worker/engine_switch.py:279`, `:308`.

O portão tem duas metades: `asr_admit` decide o **início** (o lote cede enquanto o ao vivo
decodificou nos últimos `ASR_LIVE_FRESH_S = 3.0` s, ou enquanto o `mode` for `stream`) `[CODE]
worker/engine_switch.py:344`, `:417-440`; e `AsrSerializedEngine` fecha o buraco de um passe já
começado, dormindo `time.sleep(0.05)` no último instante antes de carregar e antes de cada janela,
com limite de `ASR_LIVE_WAIT_S = 2.0` s `[CODE] worker/engine_switch.py:381-410`, `:354-356`.

`[MEASURED]` o custo que o portão cortou, na sonda com os dois backends reais (2026-11-09):

| fase | janela | total | o que se vê |
|---|---|---|---|
| ANTES (`asr_admit` forçado a `grant`) | 6,5 s | **188,0 %** de um núcleo | sessões do ao vivo (1/2/3) e do lote (5/6/7) quentes ao mesmo tempo |
| DEPOIS (portão a decidir) | 6,3 s | **142,7 %** | só sessões do ao vivo; a sessão do lote fica a 1,7 % |
| sonda sem o proxy, portão a recusar | — | **336,4 %** com **465** recusas | o portão sozinho não chega: o passe começado continua |

`[MEASURED]` `_main/receipt-20261109-engine-serialization.md:67-70`, `:85-122` (instrumento
`python _main/shell-thread-cpu.py <pid> --seconds 6 --top 8`, pids 35148 e 22924, 2026-11-09). O
log vivo confirma `WORKER_THREADS ... threads=2 source=flag`, contado `16` vezes `[MEASURED]`.

## 5. O motor quente

O motor quente é um **processo separado** que carrega o nemotron fora da shell e fica à espera num
named pipe; a shell tenta `attach` em vez de pagar a carga. O contrato vive em
`app/webview/warm_engine.py` e `app/webview/warm_pipe.py` `[CODE] app/webview/warm_engine.py:818`,
`app/webview/warm_pipe.py:150-151`.

| constante | valor | o que governa |
|---|---|---|
| `WARM_ATTACH_DEADLINE_MS` | `500` | quanto a shell espera pelo `WARM_HELLO` antes de cair para frio `[CODE] app/webview/sotto_webview.py:8282` |
| `WARM_PARK_TTL_S` | `600.0` | um motor parqueado sem `attach` morre ao fim de 10 min `[CODE] app/webview/warm_engine.py:68` |
| `WARM_RELEASE_S` | `120.0` | quanto `muito-alta` tem de persistir para largar os pesos `[CODE] app/webview/warm_engine.py:70` |
| `WARM_LOAD_RETRY_S` | `30.0` | cadência de nova tentativa quando o `load_gate` recusa `[CODE] app/webview/warm_engine.py:72` |
| `SHED_STALE_S` | `9.0` | idade máxima do `shed` publicado que o motor quente aceita `[CODE] app/webview/warm_engine.py:101` |

O nome do pipe carrega a identidade dos pesos e a sessão de Windows: `prefix + session + "-" + key`,
com `key` = `basename + 12 hex de genai_config.json` e `session` = `ProcessIdToSessionId` `[CODE]
app/webview/warm_pipe.py:111-151`. O `attach` recusa um motor cujo `plugin_sha256` não bate com o
ficheiro em disco (`WARM_HELLO_REFUSED why=stale-code`) `[CODE] app/webview/sotto_webview.py:24775-24784`.

A tarefa agendada existe e está pronta: `[MEASURED]` 2026-11-11 23:38, `schtasks /query /tn
SottoWarmEngine /fo LIST` → `Status: Pronto`, `Modo de Logon: Interativo apenas`, rc=0.

**O que o motor quente custou, medido.** `[MEASURED]` `_main/warm-engine.log` (6 017 B,
2026-11-11 20:50), `grep -c WARM_LOAD_MS` → `8`: `41015.3`, `11749.0`, `11597.0`, `11164.2`,
`8060.0`, `12471.5`, `26027.8`, `7452.1` ms, com `resident_mb` entre `239.7` e `1012.8`.

**O que o motor quente ainda não fez, medido.** `[MEASURED]` 2026-11-11 23:40: em
`_main/webview-run.log` (25 439 116 B) `grep -c WARM_ATTACHED` → `0`,
`grep -c WARM_FALLBACK_COLD` → `18`, e as 18 dizem todas `reason=absent`, entre 2026-11-08 18:57 e
2026-11-11 20:40. O `_main/warm-engine.log` não tem uma única linha `WARM_ATTACHED`.

`[INFERENCE]` A ordem dos carimbos explica o zero: a shell tenta o `attach` e, ao falhar com
`absent`, manda arrancar a tarefa (`start_warm_engine_task`, `[CODE] app/webview/sotto_webview.py:17715`),
e o motor só aparece ~1 s depois (`WARM_FALLBACK_COLD` às `17:34:20.539` e `WARM_ENGINE_START` às
`17:34:22`; o mesmo par às `20:01:00`/`20:01:01` e às `20:40:37`/`20:40:38`) `[MEASURED]`. Ou seja:
o motor quente é lançado **pela falha** e fica parqueado para a abertura seguinte; se essa abertura
chegar mais de 600 s depois, ele já expirou (`WARM_EXIT why=idle-expired held_s=600.1`). O número
de aceitação do `attach` (0,97 s contra 42,59 s a frio) foi medido contra um motor falso, e o
recibo declara-o por verificar ponta a ponta `[MEASURED]`
`_main/receipt-20261110-warm-engine-task.md:86-91`, `:139-142`.

## 6. VRAM: o guarda, o estacionamento e o pool

`VramGuard` é um fio da shell que lê a VRAM livre por NVML a cada `INTERVAL_S = 3.0` s `[CODE]
app/webview/sotto_webview.py:3350`, `:3428-3429`. Os números:

| constante | valor | razão escrita no código |
|---|---|---|
| `LOW_MB` | `1200.0` | abaixo disto, parquear `[CODE] app/webview/sotto_webview.py:3367` |
| `MODEL_VRAM_MB` | `2000.0` | o modelo medido ocupa 1175–1703 MiB, arredondado para o lado seguro `[CODE] app/webview/sotto_webview.py:3371-3375` |
| `RESUME_MB` | `LOW_MB + MODEL_VRAM_MB = 3200.0` | a retoma tem de deixar espaço para o próprio modelo `[CODE] app/webview/sotto_webview.py:3376-3381` |
| `POST_RESUME_GRACE_S` | `90.0` | o dip da própria carga não conta como "outra app", com `STREAK = 2` amostras antes de agir `[CODE] app/webview/sotto_webview.py:3382`, `:3390-3397` |

O parque **não mata o processo**: publica `park=vram` no `panel-visibility.json`, e o worker larga
os dois motores dentro do próprio processo, mantendo a captura e o áudio acumulado `[CODE]
app/webview/sotto_webview.py:19745-19761`. O latch da retoma é `_vram_parked`: a primeira versão
limpava-o **antes** de pedir a retoma e, com o painel escondido, deixava `park=vram` no ficheiro
para sempre; hoje a visibilidade decide **o que** recarregar, nunca **se** o pedido se levanta
`[CODE] app/webview/sotto_webview.py:19765-19790`.

`[MEASURED]` 2026-11-11 23:39, `grep VRAM_GUARD _main/webview-run.log`:

```
2026-11-11 17:34:20.620  VRAM_GUARD started=true interval_s=3.0 low_mb=1200.0 resume_mb=3200.0
2026-11-09 13:13:22  VRAM_GUARD_PARKING free_mb=693 pid=14712   → 13:16:25 RESUMING free_mb=3572
2026-11-09 13:17:22  VRAM_GUARD_PARKING free_mb=1100 pid=14712  → 13:18:25 RESUMING free_mb=3878
2026-11-09 13:20:04  VRAM_GUARD_PARKING free_mb=1105 pid=14712  → 13:20:55 RESUMING free_mb=3592
```

Três pares em oito minutos nesse dia. O recibo de 2026-11-05 mede o antes e o depois de
`RESUME = LOW + MODEL`: com `resume_mb=2400` foram **21 parques e 6 retomadas** no mesmo dia; com
`3200` foi **um parque e uma retomada em ~13 min** `[MEASURED]`
`_main/receipt-20261105-live-rest-and-vram.md:44-50`.

`worker/model_vram_pool.py` é outra biblioteca: garante **uma cópia por modelo por processo**
(`get_or_load` devolve as mesmas sessões para o mesmo modelo + providers) e recusa uma segunda
cópia quando o modelo já está residente noutro processo (`foreign_policy="refuse"`) `[CODE]
worker/model_vram_pool.py:1-23`, `:222-260`. **Não está no caminho de produção** — nenhum ficheiro
de `app/` ou `worker/` o importa; só `_main/vram-reuse-oracle.py` o carrega (`[MEASURED]` 2026-11-15:
censo por `ast` sobre `app/`, `worker/` e `_main/` devolve **duas** importações do pool no
repositório, uma delas a do próprio oráculo, nenhuma de produto). O caminho real de uma carga é
`worker/sotto_worker.py` → `StreamAsr`; o pool descreve um contrato de reutilização que o produto
**ainda não usa**. O que ele **não** faz: a VRAM é
privada do processo que a alocou; reutilizá-la exigiria `cudaIpcGetMemHandle` do dono `[CODE] worker/model_vram_pool.py:15-19`.

## 7. Load shedding: os três níveis, a histerese e o que cada um desliga

Os limiares são lidos **duas vezes por amostra** (commit e CPU) e vale o **pior** dos dois `[CODE]
app/webview/load_shedding.py:79-130`:

| medida | `leve` | `alta` | `muito-alta` |
|---|---|---|---|
| commit do sistema | < 88 % | ≥ 88 % | ≥ 94 % |
| CPU do sistema | < 90 % | ≥ 90 % | ≥ 98 % |
| descer exige | — | commit < 80 % **e** CPU < 70 % | idem, um degrau de cada vez |

`[CODE]` os valores em `app/webview/load_shedding.py:47-74`. Subir é imediato e sem degraus;
descer é **um degrau** e só com `CONFIRM_SAMPLES` leituras calmas `[CODE]
app/webview/load_shedding.py:246-272`.

O que cada nível deixa correr, verbatim da tabela do código `[CODE]
app/webview/load_shedding.py:79-83`:

| nível | nemotron | parakeet | modo no worker | áudio |
|---|---|---|---|---|
| `leve` | on | on | `stream` (ou `batch` se a carga mandar) | descodifica ao vivo |
| `alta` | **off** | on | `batch` | acumula para o lote |
| `muito-alta` | **off** | **off** | `shed` | acumula, **não** acorda o lote |

`[CODE]` a tradução nível→modo em `worker/engine_switch.py:1000-1005`; o `shed` só é honrado com o
interruptor armado `[CODE] worker/engine_switch.py:922-926`. Em `muito-alta` e sem passe em voo, o
motor é largado sob pressão `[CODE] worker/engine_switch.py:1038-1041`.

A camada da shell (`LoadAction`) acrescenta quatro guardas, nomeadas no código `[CODE]
app/webview/load_shedding.py:832-865`: `SOTTO_LOAD_SHED_ACT` (armada por omissão; `=0` desarma só
a acção), `MIN_DWELL_S = 60.0` (entre duas publicações), `ACTION_SAMPLES = 3` (leituras
sustentadas) e `ACTION_FLOOR_S = 180.0` (piso entre duas **descidas**).

`SOTTO_LOAD_SHED=0` desliga a **medição** e o `shed` deixa de ser escrito; a distinção entre as
duas variáveis está escrita no comentário do chamador `[CODE] app/webview/sotto_webview.py:13509-13510`,
`:13526`. O nível publicado é o do **fundo**: com o gesto do dono ligado (`live_fn`), o único valor
publicável é `leve`, e o log di-lo (`live=nemotron-por-gesto` / `live=por-limiar`) `[CODE]
app/webview/load_shedding.py:1045-1050`, `:1105-1112`.

`[MEASURED]` 2026-11-11 23:41, no log vivo de 25 MB:

```
LOAD_ACTION_PUBLISHED  alta=106 leve=67 muito-alta=44 | REDUX_SHEDDING  alta=103 leve=40 muito-alta=52
LOAD_ACTION_LEVEL=257  LOAD_ACTION_HELD=195  LOAD_ACTION_LIVE_HELD=51
LOAD_RESUME=0  LOAD_RESUME_DEFERRED=0
```

Uma linha do worker, copiada como o log a traz `[MEASURED]`:

```
2026-11-11 20:09:12  REDUX_SHEDDING level=muito-alta published=alta measured=muito-alta park=none
  commit_pct=94.4% cpu_pct=98.9% engines=nemotron:off,parakeet:off
  why="subiu: commit=94.4% cpu=98.9% >= limiar de muito-alta" visible=false
```

As duas fontes discordam (`published=alta`, `measured=muito-alta`) e o worker obedece à pior. Uma
outra linha do mesmo log mostra `level=leve ... engines=nemotron:on,parakeet:on visible=false`
`[MEASURED]` 20:46:44: a visão não larga modelo neste build (§2). `LOAD_RESUME=0` significa que a
retoma de áudio por descida de carga, embora existente no código (`resume_catch_up`, `ResumeGate`),
**não foi observada** neste log `[CODE]
worker/sotto_worker.py:6453-6505`; `[UNKNOWN]` se ela já disparou noutra janela.

## 8. Factos de modelo que são lei

O contrato do nemotron não é convenção: é lido do `genai_config.json` no arranque `[CODE]
worker/sotto_worker.py:1570-1573`.

| facto | valor | fonte |
|---|---|---|
| `blank_id` | `13087` | `[CODE] docs/model-specs/README.md:28` |
| `max_symbols_per_step` | `10` | `[CODE] docs/model-specs/README.md:29` |
| `chunk_samples` | `8960` (= 0,56 s a 16 kHz) | `[CODE] docs/model-specs/README.md:30` |

`[MEASURED]` 2026-11-11 23:40, o comando que `docs/model-specs/README.md:301` manda correr: `py -3 -c "... print('blank_id',g['blank_id'],'chunk',g['chunk_samples'],'maxsym',g['max_symbols_per_step']) ..."`
→ `dir models/nemotron-3.5-asr-ptbr-onnx-int4`, `blank_id 13087 chunk 8960 maxsym 10`,
`lang_id auto use_vad True`. `[INFERENCE]` 8960 / 16000 = 0,56 s exactos, o que fixa o passo do
ao vivo e o prazo que o portão da §4 protege.

Dois motores foram **recusados por medição**, e a recusa é lei nesta árvore:

- **`parakeet-ultra`**: mesma precisão ao carácter, 3,5× o tempo, 2,1× a RAM e **truncagem** de um
  clipe de 90 s para 9 palavras `[MEASURED]` `_main/receipt-20261104-parakeet-ultra-refused.md:7-30`
  (2026-11-04). `[MEASURED]` 2026-11-11 23:38, `du -sb` dos dois exports → `436071656` (redux) e
  `2528340716` (ultra) = **5,8×** o disco.
- **ARK-ASR-0.6B**: `0,27×` em inglês e `0,61×` em pt-BR, pico de 2358–2478 MB, e em português
  **traduz em vez de transcrever** `[MEASURED]` `_main/receipt-20261030-ark-asr-vs-parakeet.md:22-31`
  (2026-10-30).

## Lacunas

- `[UNKNOWN]` O `attach` do motor quente de ponta a ponta: zero `WARM_ATTACHED` em 18 arranques.
  Fechar exige um arranque com o motor parqueado e fresco, e a linha `WARM_ATTACHED ... load_ms=`
  no log.
- `[UNKNOWN]` A latência real de `attach` (o 0,97 s é contra um motor falso): fechar exige medir
  `WARM_HELLO` → primeira legenda num run com o motor quente vivo.
- `[UNKNOWN]` Se `LOAD_RESUME` alguma vez disparou: `0` ocorrências no log actual; fechar exige um
  log com `LOAD_RESUME`/`LOAD_RESUME_DEFERRED` e `blocks=` na mesma linha.
- `[UNKNOWN]` O pico de VRAM do parakeet ONNX int4, separado do processo: `MODEL_VRAM_MB` é uma
  média arredondada de duas medições `[CODE] app/webview/sotto_webview.py:3371-3375`; fechar exige
  um delta NVML por carregamento, isolado do sistema.
- `[UNKNOWN]` Quantas das 106 publicações `alta` puseram o worker em `batch`: `REDUX_MODE` não é
  forwardado; fechar exige acrescentar a tag à lista do shell ou ler cada `stderr_tail`.
- `[UNKNOWN]` O runner ternário em produção: o checkpoint não existe nesta árvore, logo
  `_run_runner` não foi exercido; fechar exige o checkpoint completo e um passe de fundo forçado.
