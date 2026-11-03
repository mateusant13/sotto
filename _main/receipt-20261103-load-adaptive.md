# RECIBO — a carga decide o MODO do worker, e o áudio que esperou é transcrito sozinho

**Data:** 2026-11-03
**Repo:** `H:/sotto`
**Lane:** `LoadGate`
**Ownership exercida:** `app/webview/load_shedding.py`, `app/webview/batch_queue.py`
(novo), a região `LOAD_SHEDDING` de `app/webview/sotto_webview.py`,
`_main/load-shedding-oracle.py`, este recibo.

**Ordem do dono, verbatim:**

> *"os modelos entram e saem conforme a carga do sistema, e o audio nao
> processado e' processado sozinho quando a carga liberta -- SEM NUNCA TRAVAR A
> MAQUINA DO DONO"*

## CORRECÇÃO DE 2026-11-03 (defeito medido em produção, ordem do assento principal)

O log vivo do dono (`_main/webview-run.log`, ~15 s) tinha **quatro** mudanças de
nível publicadas:

```
LOAD_ACTION_PUBLISHED level=alta  engines=parakeet stopped=nemotron why=subiu: commit=63.2% cpu=92.6% >= limiar de alta (imediatamente)
LOAD_ACTION_LEVEL     level=leve  commit_pct=58.9 cpu_pct=68.1 why=desceu um degrau ... 3 amostras
LOAD_ACTION_HELD      level=leve  published=alta reason=sustentacao stable=1/3
LOAD_ACTION_PUBLISHED level=leve  engines=nemotron,parakeet stopped=nenhum
LOAD_ACTION_LEVEL     level=alta  commit_pct=60.5 cpu_pct=91.4 why=subiu: commit=60.5% cpu=91.4% >= limiar de alta
LOAD_ACTION_PUBLISHED level=alta  engines=parakeet stopped=nemotron why=subiu: ... (imediatamente)
```

Cada par `alta`↔`leve` mandava o worker largar/recarregar o nemotron (1,2 GB de
pico) — a queixa *"o modelo loading ta toda hora saind out de load"* — e, com a
CPU desta máquina a viver em 88–95 %, o motor **ao vivo** ficava largado a maior
parte do tempo. Duas regras novas, ambas armadas:

**A. A acção NUNCA larga o motor ao vivo.** O `shed` publicado passou a ser o
nível do **FUNDO**: com o gesto do dono ligado (`_caption_wanted`, o
`LIVE_ENABLED` do botão) o único valor publicável é `leve`; `alta`/`muito-alta`
só entram no ficheiro com o ao vivo **desligado**. Quem desliga o nemotron é o
gesto, não um limiar. Log: `LOAD_ACTION_PUBLISHED … live=nemotron-por-gesto` ou
`live=por-limiar`, e `LOAD_ACTION_LIVE_HELD` (1×/min) quando a decisão diz
"carregado" e o ficheiro diz `leve`.

O shell continua a ler o **publicado**: `open_action` põe `monitor.state` numa
`PublishedView` (a decisão fica no `LoadShedding` real), e é isso que
`shedding_level()` escreve no `panel-visibility.json`.

**B. O triturador de níveis está morto.** Regras medidas em `LoadAction`:
`MIN_DWELL_S = 60` entre **duas publicações** (nas duas direcções); só
`muito-alta` sobe sem esperar; `leve -> alta` exige as **mesmas 3 amostras
sustentadas** que uma descida; o piso de 180 s continua a valer para o que
recarrega modelo. Uma excepção é imediata e só ela: **ligar o ao vivo** publica
`leve` no tick seguinte, dentro do dwell (não carrega modelo nenhum — devolve o
produto).

**Veredicto:** a acção está **ARMADA por omissão**, **liga ela própria o canal
que o worker lê** (`SOTTO_REDUX_WHEN_HIDDEN=1`, antes de o shell lançar o filho)
e o lever é o **modo** que o worker já obedece (campo `shed`), **sem matar o
processo** — matar perdia a captura. Há **PISO de 180 s** nas descidas, **histerese** e **sustentação**; o
áudio que ficou sem transcrição passa por uma **fila em disco** que sobrevive a
um restart; e um **executor `BelowNormal`** o transcreve com o **mesmo backend
ONNX int4 do worker**, cedendo quando `sample_load()` sobe. Tudo medido:
oráculo **168 arms verdes, 11 mutantes caídos**, e o motor a sério (15 s de áudio
transcritos, e o worker em `--redux-when-hidden` a trocar de modo **sem perder um
bloco**). A app **não foi largada** e a bateria completa **não foi corrida**.

---

## 0. Resposta às 4 restrições do assento principal (2026-11-03)

**1) "o áudio só existe dentro do worker; matar o worker perde o áudio".**
Concordo, e o desenho foi **mudado por causa disso**. A acção deixou de ser
`bridge.stop()` e passou a ser **escrever o nível no ficheiro que o worker já
poll** (`_main/panel-visibility.json`, campo `shed`). Medido no próprio worker
esta sessão (`sed -n 6124,6148p worker/sotto_worker.py`):

* `mode == "batch"` → o **decode de streaming é saltado** e o bloco vai para
  `switch.add_audio(block)` + `maybe_kick()`;
* `mode == "shed"` → `switch.add_audio(block)` e `continue`, **sem**
  `maybe_kick`: *"acordar o modelo e' o custo que este nivel existe para cortar"*.

Nos três modos a **captura continua**. Não há modo de captura novo a construir.
`park_worker()`/`resume_worker()` (o kill) **foram removidos** — ficaria um
segundo campeão de guardas para o mesmo lever, e um deles perde áudio.

**2) "o batch já existe e é o parakeet; não escreva um segundo transcritor".**
Não escrevi um motor novo, mas **corrijo o pressuposto com número**: nesta
máquina `worker/redux_batch.py` é o runner **ternário** e **não tem checkpoint**
(`worker/models/parakeet-redux-ternary` não existe; `ls` devolve *No such file*).
O motor de batch que o worker REALMENTE usa é o **ONNX int4**, via
`engine_policy.ParakeetEngine` → `redux_live.load_backend('onnx', …)`; o próprio
worker o diz no arranque:

```
REDUX_BATCH_ENGINE engine=parakeet name=onnx dir=H:\sotto\worker\models\parakeet-redux-onnx-int4
        missing=none runner_available=true checkpoint_available=false
```

O driver da fila chama **esse** `redux_live.load_backend` com **esse** directório
(arm 14 mede: mesmo `load_backend`, mesmo `DEFAULT_ONNX_DIR`, nenhum runtime
próprio, e o directorio do driver == o que o `engine_switch` resolve). O que ele
acrescenta é só a **fonte** (ficheiro em vez de dispositivo) e o **relógio**
(tudo o que a CPU der, em vez do ritmo de tempo real do `FileTap`) — sem isso um
lote de 10 minutos de áudio levava 10 minutos de parede.

**3) "o piso e a histerese são o ponto frágil".** É por isso que o piso **vive
dentro do `LoadShedding`** (`floor_s`): o número que o ficheiro diz e o número
que a decisão tomou são o **mesmo** — duas verdades seriam uma oscilação à
espera. E o piso é aplicado **só à descida** (a que recarrega modelo); subir é
imediato. Medido: com `floor_s=180` e um `last_descent_at` a 1 000 s, **19
voltas calmas** não tiram o nível de `muito-alta` (`held_by_floor=18`), e passado
o piso desce **um degrau** e a publicação acompanha (`level=alta published=alta`).
A banda `RESUME..HIGH` segura: 20 voltas a alternar 88,5 %/85 % ficam em `alta`
publicado, **zero** mudanças.

**4) "o shell está a ser editado por mim".** A minha edição é **um hunk só** na
região `LOAD_SHEDDING` de `_start_slow_read_monitor` (`# SHEDDING POR CARGA`),
sem tocar em mais nada do ficheiro. Todas as decisões estão em `load_shedding.py`
e `batch_queue.py`; a shell constrói o `LoadSheddingMonitor`, **não arranca o
laço dele** (ver §2) e chama `load_shedding().open_action(self, monitor=monitor,
log_fn=log)` — uma função.

**E o pedido de prova do `--redux-when-hidden`:** corrido, e está medido na §5.

---

## 1. Diff stat e hashes

```
 _main/load-shedding-oracle.py | 560 +++++++++++++++++++++++++++++++++++++-
 app/webview/load_shedding.py  | 342 +++++++++++++++++++++++++-
 app/webview/batch_queue.py    | 874 (ficheiro novo)
 app/webview/sotto_webview.py  |  25 (a MINHA região; o resto do diff do
                                     ficheiro é do assento principal, que o
                                     edita na mesma sessão)
```

**Nota de honestidade sobre o "antes":** o assento principal **committou a
árvore a meio desta sessão** (`f0eac06`), por isso
`git show HEAD:app/webview/sotto_webview.py | grep -c open_action` = **2** — a
minha região já está no HEAD. O "antes" de `load_shedding.py` e do oráculo é o
commit anterior à lane (`80cfc536…`, `951097f3…`).

| ficheiro | sha256 ANTES | sha256 AGORA |
|---|---|---|
| `app/webview/load_shedding.py` | `80cfc536804981a3649c77e7b385194baf9f80e239a976843b0b61d6925ff1dd` | `1c9681a9f29f4c631f86f166f358fece4afed9d002073c974d23d66b5b565c64` |
| `app/webview/batch_queue.py` | — (não existia) | `85bae33422a6f86a870a6435afeeeb522c5e5a6cfa56ad4436655231e05eb283` |
| `_main/load-shedding-oracle.py` | `951097f33b0e4a6dd1848fdab014793d2d5081f9c39bbb858f3a670e1a22178d` | `50a09a0ba0e47ca7511c41dbecf12dcfd9d8990a67cc214435e2b3f21f12fd97` |
| `app/webview/sotto_webview.py` | já no HEAD `f0eac06` (árvore commitada a meio da sessão) | `50ea615b77674cc0bf5ea98caa9db3e4664fff6f3df55cb27094154cbca3e909` (o resto do diff é do assento principal) |

Ficheiros: `batch_queue.py` 874 linhas, oráculo ~1 590.

---

## 2. A TABELA DE ACÇÕES (o que acontece, quando, e porque não oscila)

O nível é **escrito** no ficheiro que o worker poll; o worker escolhe o modo.

| nível publicado | modo no worker (`ReduxHiddenSwitch.tick`) | modelos | captura |
|---|---|---|---|
| `leve` | `stream` | nemotron + parakeet | continua |
| `alta` | `batch` | só parakeet (nemotron larga o decode) | **continua** (RAM → spool) |
| `muito-alta` | `shed` | nenhum (parakeet largado) | **continua**, sem acordar o modelo |

**Quem pode publicar cada um (regra A):** com o gesto do dono ligado
(`_caption_wanted`) o ficheiro só leva `leve` — nemotron e parakeet ficam, e é o
**fundo** (a fila) que cede. `alta`/`muito-alta` só são publicáveis com o ao vivo
desligado; `muito-alta` sobe na primeira leitura, `alta` exige as mesmas 3
amostras sustentadas que uma descida, e qualquer publicação respeita 60 s de
dwell desde a anterior.

**A sequência que o defeito mostrou, agora**: 88/60/88/60 em 15 s → **1**
publicação (medido), e com o ao vivo ligado → **0** publicações.

Regras de publicação (`LoadAction`, em `load_shedding.py`):

1. **SUBIR é imediato** — uma leitura a 95 % publica `muito-alta` na hora
   (medido: `published=muito-alta action=published` na 1.ª amostra). Segurança
   primeiro: uma máquina a 95 % não espera por confirmação.
2. **DESCER precisa de `ACTION_SAMPLES = 3` leituras seguidas no nível novo**
   (medido: uma leitura calma isolada → `action=none`, `held=1`).
3. **PISO `ACTION_FLOOR_S = 180 s` entre duas DESCIDAS**, dentro do
   `LoadShedding` (`floor_s`), com `held_by_floor` contado e a razão no log.
4. **HISTERESE**: `RESUME_PCT=80 < HIGH_PCT=88`; a descida é um degrau de cada
   vez com `CONFIRM_SAMPLES=3`; a banda entre 80 e 88 segura o nível.
5. **UM SÓ ESCRITOR do estado**: o laço do `LoadSheddingMonitor` **não arranca**;
   o laço de `open_action` mede **commit E CPU** (`LoadProbe`, a mesma fonte que
   o worker usa) e é quem chama `monitor._publish()`. Dois laços a escrever no
   mesmo `LoadShedding` somariam amostras e as confirmações chegariam a metade
   do tempo.

**O canal para o worker é armado por esta acção** (`LoadGuard._arm_worker_channel`,
ARM 15): `SOTTO_REDUX_WHEN_HIDDEN=1` no ambiente **antes** de o shell lançar o
filho, porque o `--redux-when-hidden` está OFF por omissão e sem ele o worker
constrói `switch=None` e o `shed` é um número que ninguém lê. Um valor já
presente no ambiente é do operador e **não** se reescreve (o log diz
`source=env`); a acção desarmada não arma nada (`source=none armed=false`).
Log: `LOAD_ACTION_WORKER_CHANNEL …`.

Desarmar (só para medição): `SOTTO_LOAD_SHED_ACT=0` — o nível continua a ser
medido/publicado (o worker obedece), a acção não força nada. Um valor que não se
reconhece **não** desarma. `SOTTO_LOAD_SHED=0` continua a desligar a medição.

---

## 3. A FILA EM DISCO (`app/webview/batch_queue.py`)

Directório: `SOTTO_BATCH_QUEUE_DIR`, senão `TMPDIR`, senão **`I:\cc-tmp`**
(medido: `TMPDIR` está vazio e `tempfile.gettempdir()` = `G:\Temp`; sem o
candidato do dono a fila ia para o temp do sistema — arm mede
`I:\cc-tmp\sotto-batch-queue`), senão `gettempdir()`.

Um par por bloco, mais um índice de adopção:

```
<epoch-ms>-<pid>-<seq>.json   manifesto (id, created, rate, samples, seconds,
                              source, state, attempts, retry_at, text, error)
<epoch-ms>-<pid>-<seq>.f32    áudio CRU float32 mono 16 kHz (como o worker o escreveu)
adopted.json                  (caminho|tamanho|mtime) do spool já adoptado
```

Medido por oráculo (ARM 12, 19 arms): escrita **atómica** (`.tmp` +
`os.replace`, payload primeiro); restart vê os blocos e um `inflight` de um
processo morto **volta a `queued`** mantendo a ordem; os bytes sobrevivem
**byte a byte**; manifesto sem áudio e `.tmp` abandonado **não** entram na fila;
um bloco só sai com `done` (texto no manifesto) ou `failed` após
`MAX_ATTEMPTS=3` com o erro escrito.

**Adopção**: o spool `sotto-pending-audio-<pid>/pending-*.f32` de um worker
**morto** é copiado para a fila; o de um worker **vivo** não (ele ainda o vai
transcrever). A origem não é apagada — pertence ao worker.

---

## 4. O EXECUTOR (prioridade baixa, cede, sem dispositivo)

* filho com `BELOW_NORMAL_PRIORITY_CLASS | CREATE_NO_WINDOW`; **medido** com
  `psutil`: `nice=16384` (`BELOW_NORMAL`);
* corre só em `leve`; lê o nível por `load_shedding.sample_load()` →
  `level_for_load` (a **mesma** fonte);
* com a carga a subir a meio do bloco: **mata o filho**, devolve o bloco a
  `queued` **sem contar como falha** (`attempts=0`), 30 s de espera;
* driver `--transcribe`: lê o `float32`, transcreve com `redux_live` (ONNX int4),
  **nenhum** caminho de captura (`sounddevice`/`PaStream` ausentes — arm);
* log: `BATCH_EXEC_DONE|YIELDED|RETRY|FAILED|SPAWN_FAILED`.

---

## 5. O que MEDI (comando → número)

| comando | resultado |
|---|---|
| `python -m py_compile app/webview/load_shedding.py app/webview/batch_queue.py app/webview/sotto_webview.py _main/load-shedding-oracle.py` | `COMPILE_RC=0` |
| `python _main/load-shedding-oracle.py` | `LOAD-SHEDDING GREEN -- arms=168 pass=168 fail=0` (eram 78) |
| `python _main/load-shedding-oracle.py --neg-arm` | **rc=1**, **11/11 mutantes caídos**: tabela, canal, derrama, escolhedor, **piso**, **sustentação**, **restart da fila**, **ceder do executor**, **canal do worker**, **dwell 60 s → 0**, **subida imediata para `alta`** |
| `python app/webview/batch_queue.py --transcribe <15 s pt-br>.f32 --rate 16000 --window-s 8` | **15,0 s de áudio em 6,66 s de parede**, texto correcto (2 linhas `route=batch-queue`) |
| `BatchExecutor.step()` sobre a fila real com o mesmo áudio | `done` em **11,7 s** (`BATCH_EXEC_DONE … captions=2 chars=159`), `pending_s=0.0` |
| `psutil.Process(filho).nice()` | `16384` |
| `load_shedding.open_action(FakeShell(), queue_dir=<tmp>)` | `armed=True level=leve batch=True`, `BATCH_QUEUE_STARTED dir=… priority=below-normal` |
| **worker vivo em modo ficheiro** (ver abaixo) | `mode=batch` por `shed`, **16 legendas** `producer=redux`, captura a continuar |

### 5.1 A prova pedida: `--redux-when-hidden` não parte nada (medido ao vivo)

```
SOTTO_FILE_TAP=I:/cc-tmp/loadgate-tap.wav SOTTO_REDUX_SPOOL_DIR=I:/cc-tmp/loadgate-spool \
  python worker/sotto_worker.py --redux-when-hidden --redux-hidden-after 1 \
    --redux-batch-interval 4 --max-seconds 45
```

Linhas do próprio worker (verbatim, excertos):

```
REDUX_SWITCH armed=true by=--redux-when-hidden hidden_after_s=1.0 batch_interval_s=4.0
REDUX_BATCH_ENGINE engine=parakeet name=onnx dir=...parakeet-redux-onnx-int4 missing=none
                   runner_available=true checkpoint_available=false
REDUX_SHEDDING level=alta published=alta measured=leve commit_pct=61.2% ... why="the shell decided"
REDUX_MODE mode=batch visible=false reason=shed-alta visibility=fresh switches=1 engine=parakeet
REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=4.0 kicks=1 held_in=40 pid=31900
REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=2.78 rss_mb=1489.7 loads=1
{"type": "caption", "text": "Rádio anunciou que a ponte sobre o rio", "start": 0.0, "end": 3.0,
 "final": true, "producer": "redux", "producerModel": "parakeet-redux-onnx-int4", "route": "redux-batch"}
WORKER_STATS tag=final blocks=397 ... redux_mode=batch redux_captions=16 redux_segments=9
             redux_kicks=8 redux_switches=1 ... queue_drops=0 queue_evicted=8
{"type": "status", "state": "done", "verdict": "captions-emitted", ... "peak_rss_mb": 1543.8}
```

O que isto prova, com número: **`reason=shed-alta`** — o modo foi escolhido pelo
nível que a shell publica (a minha acção); a captura **não parou**
(`blocks=397`, `held_in=40 → 130`, `queue_drops=0`); o batch correu no **mesmo**
ONNX int4 do worker (`load_s=2.78`) e produziu **16 legendas** com
`producer='redux'`. Ou seja: este lever **já funciona** e a política de carga só
precisava de o conduzir — que é o que esta lane passou a fazer.

---

## 6. [INFERENCE] (não medido por esta lane)

- Que a **VRAM do nemotron** é devolvida no modo `batch`: o código salta o
  decode e o `asr` fica residente; a libertação fina de sessão não foi amostrada
  com monitor de VRAM (a app não foi largada). O que está medido é o
  **comportamento**: decode parado, áudio acumulado, batch a correr.
- Que o worker **vai** ler o `shed` da shell na app real: medido no worker
  isolado (`reason=shed-alta`); na app quem escreve é o
  `PanelVisibilityWriter` que já existia (arms 8 e 10 do oráculo).
- Latência interactiva durante o lote: a promessa assenta em `BelowNormal`
  (medido) + ceder (medido), não numa medição de `stutter`.

---

## 7. O que fica para a verificação VIVA do assento principal

1. **arranque**: `LOAD_SHEDDING_STARTED` + `LOAD_ACTION_STARTED armed=true
   floor_s=180 samples=3 queue=I:\cc-tmp\sotto-batch-queue` +
   `LOAD_ACTION_WORKER_CHANNEL source=load_action SOTTO_REDUX_WHEN_HIDDEN=1` na
   mesma largada, e o worker a dizer `REDUX_SWITCH armed=true
   by=SOTTO_REDUX_WHEN_HIDDEN=1`;
2. **carga sustentada**: `LOAD_ACTION_LEVEL level=alta|muito-alta …` →
   `LOAD_ACTION_PUBLISHED …` → no worker `REDUX_MODE mode=batch|shed` e
   `BRIDGE_STOP` **ausente** (a captura continua);
3. **a carga a libertar**: `LOAD_ACTION_HELD reason=dwell`/`reason=sustentacao`,
   depois a descida (com `held_by_floor` se dentro dos 180 s) — e, com o ao vivo
   ligado, **nenhuma** mudança: `LOAD_ACTION_LIVE_HELD … o motor ao vivo e o do
   GESTO`; o worker fica em `REDUX_MODE mode=stream`;
4. **a fila**: `BATCH_QUEUE_ADOPTED files=N` só depois de um worker morto, e
   `BATCH_EXEC_DONE id=… captions=N` quando o nível for `leve`, sem
   `BATCH_EXEC_YIELDED` a meio;
5. **(d) do assento principal** — shell abaixo de 10 % de um núcleo em repouso:
   o custo desta lane em repouso é um `psutil.cpu_percent(interval=None)` a cada
   5 s e um `listdir` do spool a cada 60 s (arm: o executor só arranca filho com
   `leve` e fila não vazia).

**Configuração**: `SOTTO_LOAD_SHED_ACT=0` desarma a **acção** (o nível continua
a ser medido e publicado, e a fila continua a ser escoada em `leve` — o áudio
sem transcrição não fica à espera de uma bandeira);
`SOTTO_BATCH_QUEUE_DIR` escolhe a fila (nesta máquina o omissão resolve
`I:\cc-tmp\sotto-batch-queue`); `SOTTO_LOAD_SHED=0` desliga a medição toda.
