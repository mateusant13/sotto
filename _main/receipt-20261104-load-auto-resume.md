# RECEIPT — load gating + Parakeet catch-up (lane `LoadAutoResume-2`)

Worktree: `H:/sotto-wt/LoadAutoResume`, branch `lane/load-auto-resume`, base `82e16a5`.
Owned files: `app/webview/load_shedding.py`, the engine-choice/catch-up entry points of
`worker/sotto_worker.py`, `worker/redux_batch.py` (untouched — see §Not proven),
`_main/load-shedding-oracle.py`.

## 1. The order, verbatim

> *"modelos carregados dependendo da carga do sistema ou nao. quando carga liberar, carrega
> sozinho (NUNCA TRAVAR O PC DO USUARIO OU STUTTER) e processa qualquer audio nao processado,
> com o parakeet."*

## 2. Instrument

| what | instrument | why it is the instrument |
|---|---|---|
| commit pressure | `load_shedding._commit_pct_windows()` → `GlobalMemoryStatusEx` (`ullTotalPageFile`/`ullAvailPageFile`) | the same field the shell publishes; one field, no second truth |
| system CPU | `load_shedding.LoadProbe._cpu_pct_system()` → `psutil.cpu_percent(interval=None)` (non-blocking delta) | second signal; the owner named both ("nunca travar o PC") |
| traffic light / lease | `python I:/!manager/tools/performance-gate.py status` | fleet gate; `GREEN`, `heavy_allowed=True` during this lane |

Thresholds (unchanged by this lane — they are the shipped decision, re-measured here, not re-invented):

| level | commit % | CPU % | engines |
|---|---|---|---|
| `leve` | `< 88` | `< 90` | nemotron + parakeet |
| `alta` | `>= 88` | `>= 90` | parakeet only |
| `muito-alta` | `>= 94` | `>= 98` | none (capture continues, audio waits) |

Hysteresis: descend only below `RESUME_PCT=80` **and** `CPU_RESUME_PCT=70`, `CONFIRM_SAMPLES=3`
inside `WINDOW_SAMPLES=5`, one notch at a time, `ACTION_FLOOR_S=180` between descents,
`MIN_DWELL_S=60` between publications. New in this lane: `RESUME_RETRY_S=5`.

Measured on this box while the arms ran (5 samples, 0.5 s apart):

```
SAMPLE (58.48, None) (58.52, 79.1) (57.75, 71.2) (56.89, 60.3) (56.40, 82.2) (55.96, 83.5)
performance-gate: GREEN  commit-pct=58.5 < amber 80.0   heavy_allowed=True
```

So the machine ran `leve` the whole time: nothing below was measured under artificial pressure,
and no heavy work was launched for this lane.

## 3. BEFORE — what was missing

Parking existed; **resuming did not**:

* `worker/engine_switch.py:712-716` (`shed` branch) deliberately does not kick the batch pass:
  *"Sem `maybe_kick`: acordar o modelo e' o custo que este nivel existe para cortar."*
* `ReduxHiddenSwitch.maybe_kick` (`:846-848`) returns early unless `self.mode == "batch"`.
* `worker/sotto_worker.py` calls `maybe_kick()` only inside `if mode == "batch":`.

Consequence, by reading the code: a backlog accumulated in `shed` that came back on `leve`
(mode `stream`) had **no caller** able to hand it to the Parakeet pass — it waited in
`PendingAudio` (RAM→disk, lossless) until `ReduxHiddenSwitch.stop()` at process exit. The owner
would get the transcription when he closed the app.

## 4. The change

| file | symbol | why |
|---|---|---|
| `app/webview/load_shedding.py` | `resume_calm(commit_pct, cpu_pct)` | the band as one pure predicate: `< RESUME_PCT` **and** `< CPU_RESUME_PCT`; a missing commit reading does **not** authorise (this path *loads* 615 MB, the opposite of `level_for`'s "unknown = switch nothing off") |
| `app/webview/load_shedding.py` | `class ResumeGate` | the epoch: fires only on the **edge** parked→not-parked; then **re-reads the machine** (`probe.reread()`), one authorisation per edge, `retry()` with a 5 s floor when the pass could not start |
| `app/webview/load_shedding.py` | `LoadProbe.reread()` | opens the 5 s sampling window on purpose: the number that authorised the descent is exactly the number that may already have risen |
| `worker/sotto_worker.py` | `_resume_gate(switch)` | builds the gate from the *same* `load_shedding` module and the *same* `switch.probe` the decision uses |
| `worker/sotto_worker.py` | `resume_catch_up(switch, gate=None)` | the catch-up entry point: on the edge, `switch.flush_pending("load-resume")` hands the accumulated audio to the Parakeet thread; logs `LOAD_RESUME ... blocks=N audio_s=S` (or `LOAD_RESUME_DEFERRED` when it could not start) |
| `worker/sotto_worker.py` | `asr_thread` (`if switch is not None:` block) | one call next to `switch.tick()`; inert outside the edge |
| `_main/load-shedding-oracle.py` | `arms_resume`, `_parked_switch`, `_descend`, `neg_arm_resume`; `_mutant_layout` now actually copies `sotto_worker.py` | new arms + a negative arm for the re-read; the layout fix turns three previously-crashing negative arms into real mutants |

No level in `ENGINES` gained an `audio` key; the audio path in `shed` is unchanged
(`add_audio(block)` and no kick). **No level drops audio.**

## 5. AFTER — evidence, verbatim

```
$ cd H:/sotto-wt/LoadAutoResume && env -u TMPDIR python _main/load-shedding-oracle.py
LOAD-SHEDDING GREEN -- arms=215 pass=215 fail=0

$ python _main/load-shedding-oracle.py --neg-arm ; echo $?
NEG-ARM(retoma): a retoma deixa de RELER a carga antes de carregar
  RED   o nivel desceu mas a RE-LEITURA viu 97 %: nenhuma retoma  resumed=1 levels=['alta', 'leve', 'muito-alta']
  RED   e o motor NAO foi carregado (a leitura velha nao carrega 615 MB)  loads=1
  RED   a recusa e' DITA no log (nao e' um silencio)  (sem linha)
  RED   e nenhuma linha de retoma foi escrita
  RED   o audio continua TODO a espera (a carga subiu, ele fica para depois)  held=0 dropped=0
NEG-ARM(retoma) PASS -- RED as designed: 5 arm(s)
1
```

New arms (the acceptance list):

**(i) high→low parks then resumes exactly once** — ARM 23. Real `ReduxHiddenSwitch` +
real `LoadShedding` + `resume_catch_up` + `_FakeEngine`, 25 buffered blocks:

```
GREEN a serie alta -> baixa produz EXACTAMENTE UMA retoma  retomas=1 levels=['muito-alta', 'muito-alta', 'alta', 'leve', ...]
GREEN o motor carregou SOZINHO, uma vez  loads=1
GREEN ticks calmos seguintes NAO voltam a carregar (uma vez por borda)  loads=1
GREEN contagem: N entrou == N saiu  in=25 out=25
GREEN a espera drenou para ZERO e nada se perdeu  seconds=0.0 dropped=0
```

**(ii) high→high-after-low keeps it parked** — ARM 24, both guards:

```
(a) hysteresis: GREEN a serie alta -> UMA baixa -> alta NAO desce o nivel  ['muito-alta', 'muito-alta', 'muito-alta', 'muito-alta', 'muito-alta']
    GREEN e a retoma nunca e' autorizada: o motor FICA estacionado  resumes=0
(b) re-read:    LOAD_RESUME_HELD level=leve commit=97.0% cpu=95.0% why=commit>=80% — a carga subiu entre a
                descida e a carga do motor; o motor FICA estacionado e o audio continua a esperar
    GREEN e o motor NAO foi carregado (a leitura velha nao carrega 615 MB)  loads=0
    GREEN o audio continua TODO a espera (a carga subiu, ele fica para depois)  held=25 dropped=0
```

**(iii) N buffered blocks handed to the batch pass, N in the log line** — ARM 25:

```
LOAD_RESUME level=leve blocks=37 audio_s=3.70 engine=parakeet commit=12.0% cpu=6.0% why=calmo — a
carga libertou: o motor carrega sozinho e o audio que esperou entra no lote do parakeet
REDUX_BATCH_KICK reason=load-resume engine=parakeet audio_s=3.7 kicks=1 held_in=37 pid=...
GREEN 37 blocos -> 1 carga do motor -> espera a ZERO  loads=1 seconds=0.0
```

Wiring arm (a function nobody calls passes every arm above): `GREEN o laco do audio CHAMA a
retoma (o codigo nao e' um ornamento)  resume_catch_up(switch, resume_gate)`.

Other gates:

```
$ cd H:/sotto && python _main/worker-providers-oracle.py
WORKER-PROVIDERS VERDICT: PASS          (rc=0; live log line: selected=CUDAExecutionProvider,CPUExecutionProvider)

$ cd H:/sotto-wt/LoadAutoResume && env -u TMPDIR python _main/redux-flag-gate.py
GATE-VERDICT: GREEN — all 13 claims hold as shipped.
```

`worker/redux_batch.py` needs no change: the catch-up hands audio to `engine_policy.run_engine_pass`
→ `ParakeetEngine` (ONNX int4, 615 MB measured), which is the same batch engine the worker already
uses; `redux_batch.py` is the *ternary runner* and its checkpoint is absent on this box
(oracle ARM 14 keeps proving that).

## 6. Negative arms (all 13, worst-of)

`--neg-arm` returns **rc=1** (all mutants must go RED); each printed `PASS -- RED as designed`:
table, channel, drain (3 arms), selector, floor, sustain, persist, cede, channel-arm, dwell,
rise-immediate, cpu-wiring, **resume (5 arms)**.

The resume mutant is the guard this lane adds: `ResumeGate._reread` stops consulting `resume_calm`,
i.e. the catch-up loads on the *level* without re-reading the machine.

## 7. Files changed

```
 _main/load-shedding-oracle.py | 235 +++++++++++++++++++++++++++++++++++++++++-
 app/webview/load_shedding.py  | 175 +++++++++++++++++++++++++++++++
 worker/sotto_worker.py        |  91 ++++++++++++++++
 3 files changed, 500 insertions(+), 1 deletion(-)
```

`worker/models/parakeet-redux-onnx-int4` exists in this worktree as an **untracked 416 MB copy**
(gitignored) because the house rule keeps model weights only in `H:/sotto`; the oracle's ARM 14
needs the directory to exist. Safe to delete; re-copy to re-run the oracle here.

## 8. KNOWN SIDE-EFFECT — code-health ratchet is RED

```
$ env -u TMPDIR python _main/code-health-oracle.py
RED  app/webview/load_shedding.py: bytes piorou de 41850 para 50575
RED  app/webview/load_shedding.py: lines piorou de 923 para 1101
RED  app/webview/load_shedding.py: defs piorou de 9 para 10
RED  app/webview/load_shedding.py: classes piorou de 6 para 7
RED  worker/sotto_worker.py: bytes piorou de 407928 para 412686
RED  worker/sotto_worker.py: lines piorou de 7620 para 7708
RED  worker/sotto_worker.py: defs piorou de 68 para 70
RED  worker/sotto_worker.py: max_func piorou de 2439 para 2447
CODE-HEALTH VERDICT FAIL
```

This is deliberate growth in the two files the ticket assigned, and the ratchet fails on **any**
increase (`--update` is documented as "so com o dono de acordo"). The cure is the repository's own
sanctioned one — `python _main/code-health-oracle.py --update` after the owner/orchestrator accepts
these 8 metrics — or an extraction of `ResumeGate`/`resume_catch_up` into a new product module
(the ratchet explicitly treats new files as the cure). It is **not** a behavioural regression:
`load-shedding-oracle`, `worker-providers-oracle` and `redux-flag-gate` are green.

## 9. What could NOT be proven

* **[INFERENCE] Live app behaviour.** No app was launched (owner screen rule), so no
  `LOAD_RESUME` line was observed coming from a real `parakeet` load. The mechanism is measured
  end-to-end with the real `ReduxHiddenSwitch`, `LoadShedding`, `PendingAudio` and the real
  `resume_catch_up` — with an injected engine, not 615 MB of weights (a real load is heavy work
  and the arms do not need it; ARM 14 + `worker-providers-oracle` cover the engine choice).
* **[INFERENCE] Windows load readings under real pressure.** The 5 samples above were taken on a
  green machine (commit ~58 %). The high-side numbers (88/94/90/98) come from the shipped
  thresholds and the owner's measured 92.5 % regime, not from a re-measurement today.
* The **boot** case (a backlog already on disk when the worker starts with the level already
  `leve`) is not covered by an edge; that backlog is the disk queue's job
  (`batch_queue.BatchExecutor`, ARM 12/13), not this gate's.
* `worker/sotto_worker.py` growth keeps `code-health-oracle` RED (§8) until the baseline is
  updated with owner agreement.
