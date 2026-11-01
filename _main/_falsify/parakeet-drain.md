# Falsificação: "quando a carga liberar, o Sotto recarrega sozinho e processa QUALQUER audio nao processado, com o parakeet"

**Data:** 2026-11-01
**Agente:** `FalsifyParakeetDrain` (falsifier / veredict-only — nenhum ficheiro do produto foi tocado)
**Risco:** T2 — fallback chain / wake / re-load logic.

---

```text
CLAIM: quando a carga liberar, o Sotto recarrega sozinho e processa QUALQUER audio nao processado, com o parakeet
RISK-CLASS: T2 — fallback chains, cooldowns, failure classifiers, wake/warm logic
AUTHOR-INSTRUMENT: NOT STATED — the brief names `live-queue-drain-oracle.py` (does not exist on disk) and `_main/load-shedding-oracle.py` (exists). Neither was run: both are the author's instruments and the falsifier must attack with a DIFFERENT one.
MY-INSTRUMENT: `_falsify_drain/metric.py` (written from scratch for this task; parses the worker's OWN stderr counters and its OWN stdout caption lines and computes the set differences itself) + `_falsify_drain/arm.py` / `_falsify_drain/arm5.py` (the controlled arms that PRODUCE the scenario the live log does not contain) + `_falsify_drain/drain_probe.py` (independent from-scratch parser of `_main/webview-run.log` and of `history/`). Why it is NOT the author's: the author's oracle reports the shedder's LEVEL; mine never reads the level table at all. It reconstructs (1) the SET of audio the worker SAW and RECEIVED, (2) the SET it TRANSCRIBED, from `WORKER_STATS` / `REDUX_*` counters and from the caption lines themselves, and subtracts the two sets.
FALSIFYING-OBSERVATION: NAMED BEFORE ANY RUN — "a chunk that the worker SAW (received by the decoder at 16 kHz) and that was held by the shedder is ABSENT from the parakeet's output after the load freed". Concretely, it would fire as: `A_dec − WAIT − CONSUMED > tolerance` OR `(A_dec − WAIT) − COVER > tolerance` OR `CONSUMED − COVER > tolerance` (a chunk the engine consumed that produced no text), OR the worker's own ledger `reduxAudioIn ≠ reduxAudioOut + reduxAudioSpooled`, OR `reduxAudioDropped > 0`, OR a coverage gap larger than one decoder chunk (0.56 s) in the parakeet's own caption intervals. ANY of those = the claim is FALSIFIED (the falsifier's named observation fired).
NEGATIVE-CONTROL: an input with the property known ABSENT, reported absent — ARM 2 (`arm2_never_frees`): the load NEVER frees, so the property "the shedder's backlog was drained" is known ABSENT. The instrument reports it absent: `REDUX_SWITCH_STOP ... left_s=16.9` (16.9 s of audio STILL HELD at the stop), the worker's own ledger `reduxAudioIn=199 reduxAudioOut=60 reduxAudioSpooled=139 reduxAudioDropped=0` (199 in = 60 transcribed + 139 still held), and only 2 parakeet caption lines covering 6.00 s of the 19.90 s the decoder received. The instrument's own verdict on ARM 2 is RED, i.e. it reports the "drained" property as absent when it is absent.
   A second negative control of the SAME SHAPE, at the level of the FORGERY: `_falsify_drain/neg_arm.py` forges the arm's OWN records three ways and the instrument must go RED each time (see PROBE).
POSITIVE-CONTROL: an input with the property known PRESENT, reported present — ARM 1 (`arm1_shed_then_free`): a real speech file, real `mode=shed` for 10 s, then the load frees. The property "the shedder's backlog was drained" is known PRESENT. The instrument reports it present: the worker's own ledger `reduxAudioIn=543 reduxAudioOut=543 reduxAudioSpooled=0 reduxAudioDropped=0` (543 in = 543 out, 0 dropped, 0 still held), `REDUX_SWITCH_STOP ... left_s=0.0 failures=0 deferred=0`, and 19 parakeet caption lines whose [start,end] intervals cover 54.30 s with NO gap — exactly the 54.30 s the decoder received. The instrument's verdict on ARM 1 is green on all three metrics.
PROBE: `python H:/sotto/_falsify_drain/metric.py arm1_shed_then_free arm2_never_frees arm3_never_shed arm4_disk_spool arm5_release_reload` — exit 0 — verdict-bearing lines:
   arm1_shed_then_free  A_tap=55.60  A_dec=54.30  WAIT=0.00  CONSUMED=54.30  TAIL=0.00  STREAM=0.00  COVER=54.30 (ends at 54.30)
   arm1_shed_then_free  parakeet lines=19  streaming lines=0  passes=15  gaps=none
   arm1_shed_then_free  COUNTER metric: LOST=+0.00 (tol 0.10) -> green
   arm1_shed_then_free  TEXT    metric: LOST=+0.00 (tol 1.60 = 1.50 rounding + 0.10) -> green
   arm1_shed_then_free  CONSUMED vs COVERED: LOST=+0.00 (tol 1.60) -> green
   arm1_shed_then_free  VERDICT: green
   arm2_never_frees    A_tap=20.80  A_dec=19.90  WAIT=16.90  CONSUMED=6.00  TAIL=16.90  STREAM=0.00  COVER=6.00 (ends at 6.00)
   arm2_never_frees    CONSISTENCY: the record claims text for audio it also claims is still waiting -> RED
   arm2_never_frees    VERDICT: RED
   arm3_never_shed     A_tap=21.30  A_dec=20.30  WAIT=0.00  CONSUMED=0.00  TAIL=0.00  STREAM=20.16  COVER=20.16 (ends at 20.16)
   arm3_never_shed     COUNTER metric: LOST=+0.14 (tol 0.66) -> green
   arm3_never_shed     TEXT    metric: LOST=+0.14 (tol 0.66 = 0.00 rounding + 0.66) -> green
   arm3_never_shed     VERDICT: green
   arm4_disk_spool     A_tap=54.90  A_dec=53.50  WAIT=0.30  CONSUMED=53.20  TAIL=0.00  STREAM=0.00  COVER=52.90 (ends at 53.20)
   arm4_disk_spool     parakeet lines=19  streaming lines=0  passes=8  gaps=[(9.0, 9.1), (35.1, 35.3)]
   arm4_disk_spool     COUNTER metric: LOST=+0.00 (tol 0.10) -> green
   arm4_disk_spool     TEXT    metric: LOST=+0.30 (tol 1.10 = 1.00 rounding + 0.10) -> green
   arm4_disk_spool     VERDICT: green
   arm5_release_reload A_tap=114.90  A_dec=114.40  WAIT=0.00  CONSUMED=114.40  TAIL=0.00  STREAM=0.00  COVER=114.40 (ends at 114.40)
   arm5_release_reload parakeet lines=40  streaming lines=0  passes=33  gaps=none
   arm5_release_reload COUNTER metric: LOST=+0.00 (tol 0.10) -> green
   arm5_release_reload TEXT    metric: LOST=+0.00 (tol 3.40 = 3.30 rounding + 0.10) -> green
   arm5_release_reload VERDICT: green
VERDICT: NOT-REFUTED
WHAT-WOULD-SETTLE: n/a
```

---

## 1. Porque é que o registo VIVO não decide a alegação (e o que foi feito em vez disso)

O `_main/webview-run.log` tem 234 execuções, 204 com `WORKER_STATS`, **43** com os contadores do motor de fundo, 43 290 eventos de legenda e 2 084 linhas no store de histórico.

**Mas todas as 43 execuções com contadores de fundo foram execuções de dispositivo SILENCIOSO.** Cada uma delas tem `nonzero_blocks` 0–2, `peak=0.000122`, e `music_gated_chunks` == todos os chunks. O motor de fundo correu **25 passes sobre esse silêncio e produziu ZERO linhas**.

```
$ python H:/sotto/_falsify_drain/drain_probe.py
runs total              : 234
caption events in log    : 43290
history lines in store   : 2084
runs with a REAL loss (lost_s > tolerance): 0 of 43
POSITIVE CONTROL -- runs that NEVER shed (mode=stream, switches=0):
positive-control runs: 6, RED among them: 0
```

Isto é um facto medido, não uma inferência: **o registo vivo não contém NENHUMA execução em que a fala tenha sido retida pelo shedder e depois transcrita.** Pode haver 0 perdas ou 100 % de perdas — o registo vivo não consegue dizer. Por isso a falsificação correu sobre execuções controladas que produzem exatamente o cenário da alegação.

## 2. As execuções controladas (ARM) — como foram feitas

Nada disto toca o ecrã do dono:

- **Fonte de áudio = FICHEIRO**, via `SOTTO_FILE_TAP=H:\sotto\_main\pt-br-sample.wav` (pt-BR real, 15 s, peak 0.58). Nenhum dispositivo é aberto; `nonzero_blocks=514` confirma áudio real com fala.
- **Ficheiro de visibilidade PRIVADO**: `--panel-visibility H:\sotto\_falsify_drain\arm\panel-visibility.json`. O ficheiro da shell viva nunca é tocado, e o `Local\SottoShell` nunca é tomado (é um WORKER, não uma shell: sem janela, sem tray, sem Alt+C). `CREATE_NO_WINDOW (0x08000000)` no filho.
- **Áudio silenciado** antes de cada braço (`python H:/sotto/_main/mute-audio.py --mute`), **des-silenciado no fim** (`--unmute` → `{"state": "unmuted", "muted": false, ...}`).
- **A shell viva NÃO foi morta.** Verificado: `OpenMutexW('Local\SottoShell')` → handle 588 (nonzero) e o log continua a crescer (46 289 341 bytes às 16:12).
- **A inversão é disparada pela PRÓPRIA linha do worker**, não por um relógio de parede: o harness espera por `REDUX_MODE mode=shed` e só depois conta o `dwell_s`. (A primeira versão do harness invertia por temporizador e a inversão caía ANTES do modelo carregar — o braço media `switches=0`, isto é, media nada com ar de medir.)

Comandos (produzidos por `_falsify_drain/arm.py`, registados em `_falsify_drain/arm/arms.json`):

```
python H:\sotto\worker\sotto_worker.py --redux-when-hidden \
  --panel-visibility H:\sotto\_falsify_drain\arm\panel-visibility.json \
  --redux-hidden-after 1.0 --redux-batch-interval 3.0 --redux-max-audio 120.0 \
  --meter-hz 0 --stats-interval 2.0 --max-seconds 60
env: SOTTO_FILE_TAP=H:\sotto\_main\pt-br-sample.wav  SOTTO_REDUX_WHEN_HIDDEN=1
     SOTTO_REDUX_SPOOL_DIR=H:\sotto\_falsify_drain\arm\spool  PYTHONUNBUFFERED=1
```

| braço | o que muda | o que mede |
|---|---|---|
| `arm1_shed_then_free` | `muito-alta` → (10 s) → `leve` | a alegação inteira: retido → libertado → drenado |
| `arm2_never_frees` | `muito-alta` o tempo todo | **controlo negativo**: a carga NUNCA liberta |
| `arm3_never_shed` | `leve` + visível | **controlo positivo**: nunca é retido (via streaming) |
| `arm4_disk_spool` | `muito-alta` → `leve`, `--redux-max-audio 4` | o caminho **disco** (RAM 120 s → spool) |
| `arm5_release_reload` | `muito-alta`→`leve`→`muito-alta`→`leve` | a metade **"recarrega sozinho"** |

## 3. Números crus — ARM 1 (a alegação, executada)

```
REDUX_SHEDDING level=muito-alta published=muito-alta measured=leve commit_pct=59.8% engines=nemotron:off,parakeet:off
REDUX_MODE mode=shed reason=shed-muito-alta visibility:fresh switches=1 held_s=0.0 note=audio-fica-para-processar-depois
REDUX_SHEDDING level=leve published=leve measured=leve commit_pct=60.6% cpu_pct=52.0% engines=nemotron:on,parakeet:on
REDUX_MODE mode=batch visible=false reason=hidden-1.0s visibility:fresh switches=2 engine=parakeet runner=redux_batch.py
REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=2.1 rss_mb=960.7 loads=1
REDUX_SWITCH_STOP armed=true switches=2 segments=15 segment_lines=19 kicks=15 batch_seconds=54.3 failures=0 deferred=0 refusals=0 left_s=0.0 spooled=0 fallbacks=0/543
WORKER_STATS tag=final blocks=556 block_samples=889600 nonzero_blocks=514 resampled_samples=868800 chunks=0 captions=0 audio_s=0.00 queue_drops=0 queue_evicted=32 redux_mode=batch redux_captions=19 redux_segments=15 redux_kicks=15 redux_held_s=0.0 redux_switches=2 redux_deferred=0
```

Contas do worker (`done` payload), a **identidade do livro-razão do próprio worker**:

| braço | `reduxAudioIn` | `reduxAudioOut` | `reduxAudioSpooled` (ainda retido) | `reduxAudioDropped` | identidade |
|---|---|---|---|---|---|
| arm1 | 543 | 543 | 0 | **0** | 543 = 543 + 0 ✔ |
| arm2 | 199 | 60 | **139** | 0 | 199 = 60 + 139 ✔ |
| arm3 | 0 | 0 | 0 | 0 | ✔ (nunca houve fundo) |
| arm4 | 535 | 532 | 3 | 0 | 535 = 532 + 3 ✔ |
| arm5 | 1144 | 1144 | 0 | 0 | 1144 = 1144 + 0 ✔ |

Em ARM 1 o `audio_s=0.00` e `captions=0` provam que **o motor de streaming nunca transcreveu uma palavra** — todo o texto veio do parakeet (`redux_captions=19`, `producer=redux`, `route=redux-batch`). E `left_s=0.0` significa que **nada ficou à espera**.

## 4. ARM 5 — a metade "recarrega sozinho"

```
REDUX_SHEDDING level=muito-alta ... engines=nemotron:off,parakeet:off
REDUX_MODE mode=shed reason=shed-muito-alta switches=1 held_s=0.0
REDUX_SHEDDING level=leve ... engines=nemotron:on,parakeet:on
REDUX_MODE mode=batch visible=false reason=hidden-1.0s switches=2 engine=parakeet
REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=1.87 rss_mb=957.3 loads=1
REDUX_SHEDDING level=muito-alta ... engines=nemotron:off,parakeet:off
REDUX_MODE mode=shed reason=shed-muito-alta switches=3 held_s=1.6
REDUX_ENGINE_RELEASED engine=onnx reason=shed-muito-alta rss_before_mb=1006.7 rss_after_mb=528.1 releases=1
REDUX_SHEDDING level=leve ... engines=nemotron:on,parakeet:on
REDUX_MODE mode=batch visible=false reason=hidden-1.0s switches=4 engine=parakeet
REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=1.7 rss_mb=963.1 loads=2
REDUX_ENGINE_RELEASED engine=onnx reason=stop rss_before_mb=1014.5 rss_after_mb=535.1 releases=2
```

`loads=1` → `RELEASED` → `loads=2`: o modelo **descarregou-se sozinho** quando a carga voltou e **recarregou-se sozinho** quando a carga libertou, sem ninguém pedir. E o total: `IN=1144 OUT=1144 DROPPED=0`, 40 linhas de parakeet, 114.40 s cobertos, `left_s=0.0`.

## 5. O instrumento, e porque é que não é o do autor

O autor assinou a alegação com um oráculo de *nível de shedder*. O meu instrumento **nunca lê a tabela de níveis**. Ele reconstrói dois conjuntos a partir dos factos publicados pelo próprio worker:

- **A_dec** = `resampled_samples / 16000` — o áudio que o **decoder recebeu** (o áudio que o worker viu).
- **CONSUMED** = a cadeia de *yields*, percorrida na ordem do log: cada `REDUX_ENGINE_DONE` abre um passe (`audio_s` handed); um `REDUX_ENGINE_YIELD` que se segue diz que o passe só chegou a `done_s` e devolveu o resto. `CONSUMED = Σ (done_s | audio_s)`.
- **COVER** = a união dos intervalos `[start, end]` das linhas de legenda do **parakeet** — os segundos de áudio que a **SAÍDA** do motor efetivamente cobre.
- **WAIT** = `REDUX_SWITCH_STOP left_s=` — o que ficou retido.

Três métricas independentes, e a alegação é RED se **qualquer uma** passar:

| métrica | fórmula | o que apanha |
|---|---|---|
| COUNTER | `A_dec − WAIT − CONSUMED − STREAM` | perda que os contadores reportam |
| TEXT | `(A_dec − WAIT) − COVER` | áudio que **não produziu texto** |
| CONSUMED-vs-COVER | `CONSUMED − COVER` | áudio **processado sem texto**, mesmo quando um contador mente |

**Tolerâncias, declaradas:** um bloco de captura = 0.10 s (medido: `block_samples / blocks` = 1600 amostras); um chunk do decoder = 0.56 s (8960 amostras), aplicado **só** quando o streaming correu; e uma margem de arredondamento de 0.10 s por fronteira (o `start`/`end` de uma legenda é quantizado ao bloco de captura — daí os dois buracos de 0.1 s e 0.2 s em ARM 4, que são exactamente isso).

## 6. O CONTROLO NEGATIVO do harness — a prova de que o verde não é vácuo

Um ARM verde não vale nada se o ARM não puder ficar vermelho. `_falsify_drain/neg_arm.py` forja os registos do próprio ARM de três maneiras e exige que o instrumento apanhe cada uma.

```
$ python H:/sotto/_falsify_drain/neg_arm.py arm1_shed_then_free
--- BASELINE (the arm's own records) ---
   baseline    A_dec=54.30  cover=54.30  wait=0.00  consumed=54.30  bg=19
               COUNTER: +0.00/0.10  TEXT: +0.00/1.60  CONSUMED-vs-COVER: +0.00/1.60  -> green
--- FORM A: one engine pass loses 0.56 s (the COUNTER form) ---
   lines altered: 1
   FORM A      A_dec=54.30  cover=54.30  wait=0.00  consumed=53.74  bg=19
               COUNTER: +0.56/0.10  TEXT: +0.00/1.60  CONSUMED-vs-COVER: -0.56/1.60  -> RED
   the SECONDS metric went RED while the baseline is green: YES
--- FORM B: one parakeet caption line is DELETED (the TEXT form) ---
   lines removed: 1
   FORM B      A_dec=54.30  cover=51.30  wait=0.00  consumed=54.30  bg=18
               COUNTER: +0.00/0.10  TEXT: +3.00/1.60  CONSUMED-vs-COVER: +3.00/1.60  -> RED
   the probe went RED while the baseline is green: YES
--- FORM C: a line is deleted AND left_s is inflated (the COUNTERS HIDE IT form) ---
   lines removed: 1  left_s inflated by: 1
   FORM C      A_dec=54.30  cover=51.30  wait=3.00  consumed=54.30  bg=18
               COUNTER: -3.00/0.10  TEXT: +0.00/1.60  CONSUMED-vs-COVER: +3.00/1.60  -> RED
   the COUNTER metric is GREEN (the counter hides it) but a TEXT-side metric is RED (TEXT=+0.00, CONSUMED-vs-COVER=+3.00, tol 1.60): YES

ARM-HARNESS NEGATIVE CONTROL: A=RED B=RED C=RED -> PASS
```

O mesmo no ARM 4 (o caminho do disco): `ARM-HARNESS NEGATIVE CONTROL: A=RED B=RED C=RED -> PASS`.

**Nota de honestidade:** o FORM C é a razão pela qual existe a terceira métrica. Com apenas as duas primeiras, um contador inflado (`left_s`) tornava o probe verde enquanto o áudio já tinha desaparecido. A métrica CONSUMED-vs-COVER é a que apanha esse caso. Isto foi descoberto pelo próprio controlo negativo — não foi assumed.

O segundo controlo negativo (`_falsify_drain/neg_control.py`, sobre o registo vivo e o store) também passa: uma forgery de 0.56 s num contador faz 34 execuções ficarem RED, e uma linha apagada do store é notada (`hist_lines 2084 → 2083`, e o conjunto store-menos-log encolhe exactamente 1).

```
NEGATIVE CONTROL RESULT: A=RED B=RED -> PASS
```

## 7. A ressalva que NÃO se pode esconder

**O mecanismo drena. A alegação, tal como foi escrita, é however sobre o que acontece DEPOIS.**

O store de histórico do dono (`history/`) tem 2 084 linhas, e **ZERO** delas carrega `producer=redux` ou `route=redux-batch`:

```
$ grep -rl "redux" history/            -> (nada)
$ grep -oh "route=[a-z-]*" history/*/*.md | sort | uniq -c
   1571 route=final
     11 route=provisional-draft
```

E o código diz porquê. `app/panel/history-source.js` é o predicado que decide que produtor pode escrever no transcript canónico:

```js
const LIVE_PRODUCER = 'live';
const CANONICAL_PRODUCER = 'redux';
function isCanonicalLine(meta) {
  return producerOf(meta) === CANONICAL_PRODUCER;   // fail-closed
}
```

O `producer: 'redux'` que o parakeet carimba **é o que o predicado exige** — e o predicado está no browser, não no worker. `app/panel/caption-formulation.js:commit()` calcula `route` e `routeSource` e passa `producer` no meta; `panel.js recordHistory` chama então `history_append`. O shell (`app/webview/sotto_webview.py:8342`) aceita `route ∈ ('final','provisional-draft')` e recusa `provisional-draft`.

Isto é **diferente** da rota do texto que o parakeet produz. A alegação, lida literalmente, é sobre o parakeet **processar** o áudio retido — e isso está medido e confirmado. Se a alegação incluir "e o texto chega ao transcript do dono", **essa parte não está provada por esta execução**: os braços correm o WORKER directamente, sem o painel Electron, e o store não recebeu uma única linha `producer=redux` em 2 084 linhas de histórico.

**Afirmação a favor, que também não está provada:** o registo vivo não tem **nenhuma** execução de fala retida pelo shedder. As 43 execuções com contadores de fundo foram todas sobre silêncio. A alegação, quanto ao *produto em uso*, repousa em evidência de execução controlada, não em evidência viva de fala real.

## 8. O veredict

A observação falsificadora nomeada **não disparou** em nenhum dos cinco braços:
- ARM 1 (a alegação): `COUNTER +0.00`, `TEXT +0.00`, `CONSUMED-vs-COVER +0.00`, ledger `543=543+0`, `dropped=0`, `left_s=0.0`, 19 linhas de parakeet cobrindo 54.30 s sem buraco.
- ARM 4 (disco): `dropped=0` em `AUDIO_PENDING_SPILLED`, ledger `535=532+3`, os 3 s retidos são 0.30 s de resto de chunk + arredondamento.
- ARM 5 (recarga): `loads=1` → `RELEASED` → `loads=2`, ledger `1144=1144+0`, 114.40 s cobertos.

**VERDICT: NOT-REFUTED** — a alegação não foi refutada. Isto **não** é um "provado": é "a observação falsificadora que nomeei não disparou". O que a tornaria decidível está na secção 7: uma execução real (com o painel) em que a fala é retida pelo shedder e depois transcrita, **e** a linha `producer=redux` a aparecer no store.

---

## CACHE/PRICE

Verbatim output of `bash I:/!manager/scripts/cache-task-report.sh FalsifyParakeetDrain`:

```
## CACHE/PRICE
- task/agent: FalsifyParakeetDrain
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyParakeetDrain']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyParakeetDrain']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-01T19:14:22.335411+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyParakeetDrain']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FalsifyParakeetDrain']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Comando: `bash I:/!manager/scripts/cache-task-report.sh FalsifyParakeetDrain`.
O transcript da sessão em `.jsonl` não é resolúvel neste ambiente (`find C:/Users/Administrador/.omp -name "*.jsonl" -newermt "-5 hours"` → vazio; `.omp/agent/sessions` só tem directórios `-tmp` antigos). A forma por `agent_id` resolve para o ledger de telemetria; **todas as linhas reportam UNKNOWN porque 0 linhas de uso casam com esta identidade** (`grep -c "FalsifyParakeetDrain" model-usage.jsonl` → 0). Isto é o comportamento fail-closed do script, não uma omissão.

## GATE-CHANGE REQUEST

**The hole the falsifier found in the gate.** The claim says the parakeet "processa QUALQUER audio nao processado". The drain MECHANISM is proven (5 arms, 3 metrics, 2 negative controls). But the gate measures the drain and stops there: **no gate anywhere measures whether the parakeet's line reaches the owner's transcript.**

Measured today, in the owner's own store:

```
$ grep -rl "redux" history/            -> (nada)
$ grep -oh "route=[a-z-]*" history/*/*.md | sort | uniq -c
   1571 route=final
     11 route=provisional-draft
$ grep -c "producer=redux" history/*/*.md   -> 0
```

2 084 lines of history, **zero** `producer=redux`, **zero** `route=redux-batch`. The chain that would carry a parakeet line there is `worker stdout -> panel recordHistory -> shell history_append -> history/<date>/<hh>.md`, and the shell's gate accepts only `route ∈ ('final','provisional-draft')` (`app/webview/sotto_webview.py:550` `HISTORY_ROUTES`, and `history_append` at :8342 refuses `provisional-draft`). The browser-side predicate (`app/panel/history-source.js isCanonicalLine`) requires `producer === 'redux'` — a key the WORKER stamps but the panel's commit path is what turns into the store's `route=`.

**The mechanical gate this proposes** (one line, and it is RED today):

```bash
# after a shed->resume arm that produced parakeet lines:
grep -c 'producer=redux' history/*/*.md   # must be >= 1
```

Measured now: **0**. That is the RED input. A green build of this gate is the statement "the parakeet's text reached the owner's transcript".

**Its non-vacuity control** — the gate must be able to go GREEN, otherwise it is a gate that can never pass:

```bash
# the same arm, with the panel's canonical-producer path exercised end-to-end:
# the line must appear WITH producer=redux AND with a route the store accepts.
```

[INFERENCE] — the exact panel wiring that would make it green is NOT verified here: this lane never ran the Electron panel (that would put a window on the owner's screen, which `SOTTO_NEVER_ON_OWNER_SCREEN` forbids without the owner's breaker). What IS measured is the RED side: the store has never received such a line.

**Non-vacuity, what IS measured:** the drain side is not vacuous either way — `neg_arm.py` proves the drain probe goes RED on all three forgery forms (A=RED B=RED C=RED) on ARM 1 and ARM 4, and `neg_control.py` proves the live-log/store probe goes RED on a 0.56 s counter forgery (34 runs flip to RED) and on a one-line store deletion (the store-minus-log set shrinks by exactly 1).

**Requested change (Main merges; this lane only prepares):** add the store-arrival assertion above to the same gate that already asserts the drain (`_falsify_drain/` side), so a future change that breaks the drain AND a future change that breaks the delivery are both caught. The request is a ONE-LINE gate plus its RED input (`producer=redux` count = 0 today), not a product change.


## SELF-AUDIT

**1. protocolos em falta** — Encontrei um: o bloco de COMECAR pedia um `todo init` como PRIMEIRO tool call, e a ferramenta `todo` não existe nesta lane (verifiquei o inventário de tools: `read`, `write`, `glob`, `grep`, `bash`, `wait`). O bloco diz explicitamente "Se a tua toolset nao tem `todo`: a linha 1 vira a PRIMEIRA linha do teu resultado e o `done` vira a ULTIMA." **Isto é uma lacuna REAL que eu não honrei**: a linha 1 do meu resultado devia ter sido o card, e a última o `done`. Não fiz isso. Corrigi o mais tarde possível: o card e o `done` estão nas duas pontas desta mensagem final, mas a **primeira linha** não é o card — a sequência já tinha começado. O que faria diferente: verificar a existência da ferramenta `todo` nos primeiros 5 segundos e, na ausência, emitir o card como linha 1 da PRIMEIRA resposta, não da última.

**2. verificacao adicional** — Corri, e correu barato:
- `neg_arm.py` sobre ARM 1 **e** ARM 4 (A=RED B=RED C=RED nos dois) — provou que o probe pode ficar vermelho.
- `neg_control.py` sobre o registo vivo (A=RED B=RED) — a forgery no log vivo e no store é vista.
- A identidade do livro-razão do worker (`IN = OUT + HELD`, `DROPPED=0`) nos **cinco** braços, calculada a partir do `done` payload — uma segunda fonte, independente das minhas três métricas.
- `OpenMutexW('Local\SottoShell')` → 588 (nonzero) + tamanho do log a crescer: a shell viva nunca foi tocada nem morta.
- `mute-audio.py --status` → `{"state": "unmuted", "muted": false}` no fim.
Não corri: um braço com o **painel Electron real** (seria a única prova de que a linha `producer=redux` chega ao store) — o custo é abrir uma janela na tela do dono, que `SOTTO_NEVER_ON_OWNER_SCREEN` proíbe sem o breaker do dono.

**3. checkboxes novas** — Nenhum checkbox NOVO e MECÂNICO para esta classe de trabalho além do que já existe. O que a execução mostrou é um checkbox de **integridade do harness**, que adicionaria:
> "o harness de falsificação tem de conseguir ir a RED antes de um verde ser acreditado" — mecânico: `python _falsify_drain/neg_arm.py <arm>` tem de imprimir `A=RED B=RED C=RED -> PASS` **antes** de o `<arm>` ser lido como evidência; e o harness tem de restaurar os registos originais (o meu `probe()`original **não restaurava** e contaminou o ARM 1 — discovered quando o `A_dec` do ARM 1 mudou de 51.40 para 54.30 entre duas execuções; corrigido com `.bak`/restauro e o ARM 1 foi re-executado limpo).
Acrescentaria também: "um braço só conta como evidência depois de o **livro-razão do worker** (`reduxAudioIn/Out/Spooled/Dropped`) satisfazer a identidade `IN = OUT + HELD` com `DROPPED = 0`" — é uma verificação de uma linha, independente das métricas do falsificador.

**4. review por outro subagente** — `nao — razao: sou o falsifier desta lane; o meu output é um veredict sobre a alegação de outro agente, não código meu para revisão. Não escrevi uma linha do produto (verdict-only). O peer `FalsifyHotkeySpam` está noutra alegação e noutro mecanismo. Aceito que o `Main` re-examine os números brutos — todos os comandos estão no receipt para reprodução.`

**5. confiança** — **média-alta** para a parte mecânica (o mecanismo drena: 5 execuções, 3 métricas, 2 controlos negativos que apanham as três formas de forgery, e o livro-razão do próprio worker a satisfazer a identidade em todas); **média** para atransferência ao produto em uso, porque o registo vivo não tem **nenhuma** execução de fala retida (as 43 são silêncio) e porque o store nunca recebeu uma linha `producer=redux`. O que a mudaria: uma execução real com o painel, fala real retida pelo shedder, e a linha `producer=redux` a aparecer em `history/` — isso elevaria a confiança a alta e fecharia a ressalva da secção 7.

**6. nao verificado** —
- Que a **shell real** (não o worker isolado) drene da mesma forma: não verificado. O painel Electron tem o seu próprio `routeFor`/`recordHistory`/`history_append`; o braço corre o worker e o stdout dele, não o painel.
- Que a linha `producer=redux` chegue ao transcript do dono: **não verificado, e a evidência actual diz que NÃO CHEGOU** (0 de 2 084 linhas do store).
- Comportamento com **conversa real** (dois负载-shedders alternando durante fala contínua): não verificado; ARM 5 alterna, mas com um ficheiro de 15 s repetido e sem o shedder a competir pelo mesmo processo.
- **Cadeia de shedder→spool→disco→requeue** com o disco cheio ou a escrita a falhar: não verificado (o `AUDIO_PENDING_SPILLED` do ARM 4 correu com `dropped=0`, mas sem falha induzida).
- Comportamento com mais de 120 s de backlog (o limite de RAM) em modo `shed`: não verificado; ARM 4 forçou o spill com `--redux-max-audio 4`, mas o total retido foi de ~30 s, não de minutos.
- **A taxa de perda em execução sustentada** (a alegação sob carga real durante horas): não verificado; os braços duram 26–120 s.
- O `_main/load-shedding-oracle.py` e o `live-queue-drain-oracle.py` do autor: **não executados de propósito** (são o instrumento do autor).

**7. gate-doubt:** —
- `verde-de-verdade:` O verde do ARM 1 **é** real, e a corrida em que poderia ter passado vácuo foi fechada: (a) a primeira versão do harness invertia por temporizador e o ARM media `switches=0` — o modo nunca entrou em `shed`, ou seja, um braço que media nada com ar de medir; corrigido pela inversão disparada pela linha do próprio worker (`REDUX_MODE mode=shed`); (b) a primeira versão do `neg_arm.py` **não restaurava** os registos originais e contaminou o ARM 1 (o `A_dec` mudou de 51.40 → 54.30) — o ARM 1 foi re-executado limpo e o número final (54.30) vem da execução limpa; (c) o `probe()` original do `neg_arm.py` levantou `SameFileError` e foi reescrito com `.bak` + restauro; (d) a terceira métrica (CONSUMED-vs-COVER) só existe porque o FORM C expôs que duas métricas podiam ficar verdes com um contador a mentir — não a assumi, **descobri-a**; (e) o primeiro `neg_control.py` comparava o set-difference na **direcção errada** e falhou o FORM B — corrigido para a direção store-menos-log, e agora A=RED B=RED. Nenhum destes verdes foi aceite sem o seu contra-teste.
- `falta-no-gate:` O gate não verifica **que o texto do parakeet chega ao transcript do dono**. Um cenário que uma mudança futura atravessa: alguém acrescenta `route=redux-batch` ao `HISTORY_ROUTES` do shell, ou o `recordHistory` do painel passa a aceitar `producer:'redux'` — e o store continua vazio porque o `history_append` do shell só aceita `final`/`provisional-draft` e o predicado do browser (`history-source.js`) só é avaliado no renderer. Ou, ao contrário: alguém muda `isCanonicalLine` para aceitar `producer:'live'` e o transcript enche-se de streaming — o `grep` das rotas no store (`1571 route=final`, `0 route=redux-batch`) é o que apanha **isto**, e não nenhum gate. Nenhum gate existente mede a **viagem da linha** entre o `stdout` do worker e o ficheiro em `history/`.
- `gate-melhor:` Um check MECÂNICO, de uma linha, que fecha esse buraco: correr um braço com o painel real e afirmar que `grep -c 'producer=redux' history/` cresce de 0 para ≥1. Concretamente: `python _falsify_drain/arm.py arm1_shed_then_free && grep -c 'producer=redux' history/` **tem de ser ≥ 1** (hoje é **0**, medido). Para o tornar RED: este é um gate que **está hoje vermelho** por缺 do wiring — que é exactamente o ponto.

review: skipped (orchestrator discretion, falsifier-lane verdict-only receipt — no product code written; all raw commands are reproducible from this receipt)

## CORRECCAO DO CAMPO, MEDIDA POR MAIN (2026-11-01 16:5x)

O achado 3 deste recibo (`grep -c 'producer=redux' history/... = 0`) esta' certo no
numero e **errado no campo**: o store nao escreve `producer=`. O que ele escreve e'
`route=` e `src=` num comentario HTML na propria linha, e a contagem real de hoje e'
`route=final` 1571, `route=provisional-draft` 11, `src=worker-stamped` 12 -- **zero**
linhas com uma rota de lote/fundo. A conclusao do achado sobrevive a correccao
("nada no transcrito e' atribuido ao parakeet de fundo"), o GATE-CHANGE REQUEST que
ele propoe nao: um portao que procura `producer=redux` e' RED por construcao e
nunca poderia ficar verde. O portao correcto conta `route=`/`src=` e exige uma
linha de lote; fica por decidir em QUAL escritor essa rota nasce.
