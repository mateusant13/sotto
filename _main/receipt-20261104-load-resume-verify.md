# RECEIPT — the two load cards, closed by MEASUREMENT (or not at all)

Tree: `H:/sotto-wt/LoadResumeVerify-2`, branch `lane/load-resume-verify`, base `b92681c`
(`git worktree add … -b lane/load-resume-verify b92681c`).
`lane/load-auto-resume` is already merged: `git rev-list --count lane/load-auto-resume ^HEAD` = **0**
(the lane's commit is `1b97530`, 2026-11-04 11:15:29), so the code measured here is the code shipped.

**Verdicts**

| card | verdict | proof |
|---|---|---|
| A — *"modelos carregam conforme a carga do sistema e voltam sozinhos quando a carga libera, sem travar o PC"* | **CLOSED** | `load-shedding-oracle` GREEN 215/215 (rc=0) + `--neg-arm` rc=1; ARM 23/24/25 + the wiring arm |
| B — *"audio nao processado vai para o parakeet em batch quando a carga libera"* | **CLOSED** | `load-shedding-oracle` ARM 13/25 + `batch-queue-drain-oracle` 5/5 (rc=0) + `--neg-arm` rc=1 |

No product file was changed by this lane. The measurement is an INSTRUMENT, and a receipt is not
the proof: every claim below is a line an oracle printed in this tree, with its rc.

---

## 0. One thing that is NOT evidence here: the live app is STALE

```
$ python _main/live-code-freshness-oracle.py --strict
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=42548 started=2026-11-04 10:06:36.407
  processo: sha256=3533907AABB8
  disco   : sha256=0B0C29A964C1 files=39
  porque  : a etiqueta do processo nao e a do disco (hash diferente)
rc=3
```

pid 42548 started **10:06:36**; the resume code landed **11:15:29**. So the running process is the
build *before* the retoma, and the absence of a `LOAD_RESUME` line in `_main/webview-run.log` proves
nothing about this lane (bug-hunt PASSO 0: STALE means restart before judging, not "it does not work").
Everything below is measured headless on the current tree; the one thing that cannot be observed
today is a `LOAD_RESUME` line from a real app process, and it is marked as such in §A.4.

---

## A. Card A — models follow the load and come back on their own

### A.1 Commands and rc

```
$ TMPDIR=I:/cc-tmp python _main/load-shedding-oracle.py
LOAD-SHEDDING GREEN -- arms=215 pass=215 fail=0
rc=0                      (log: _main/_audit-verify/load-resume-verify-load-shedding.log, 270 lines)

$ TMPDIR=I:/cc-tmp python _main/load-shedding-oracle.py --neg-arm
NEG-ARM(retoma) PASS -- RED as designed: 5 arm(s)
rc=1                      (log: _main/_audit-verify/load-resume-verify-load-shedding-neg.log)
```

### A.2 The lines that prove the mechanism (verbatim from the log)

ARM 23 — the edge, exactly once, with the backlog counted:

```
  GREEN a serie alta -> baixa produz EXACTAMENTE UMA retoma  retomas=1 levels=['muito-alta', 'muito-alta', 'alta', 'leve', 'leve', …]
  GREEN e o N do backlog entregue e' o N que esperava  blocks=25
  GREEN o motor carregou SOZINHO, uma vez  loads=1
  GREEN o log da retoma diz `blocks=N` (o tamanho do backlog entregue)  LOAD_RESUME level=leve blocks=25 audio_s=2.50 engine=parakeet commit=12.0% cpu=6.0% why=calmo — a carga libertou: o motor carrega sozinho e o audio que esperou entra no lote do parakeet
  GREEN contagem: N entrou == N saiu  in=25 out=25
  GREEN a espera drenou para ZERO e nada se perdeu  seconds=0.0 dropped=0
  GREEN ticks calmos seguintes NAO voltam a carregar (uma vez por borda)  loads=1
```

ARM 24 — the two guards that keep it from *travar o PC*:

```
  GREEN a serie alta -> UMA baixa -> alta NAO desce o nivel (a confirmacao manda)  ['muito-alta', 'muito-alta', 'muito-alta', 'muito-alta', 'muito-alta']
  GREEN e a retoma nunca e' autorizada: o motor FICA estacionado  resumes=0
  GREEN o nivel desceu mas a RE-LEITURA viu 97 %: nenhuma retoma  resumed=0 levels=['alta', 'leve', 'muito-alta']
  GREEN e o motor NAO foi carregado (a leitura velha nao carrega 615 MB)  loads=0
  GREEN a recusa e' DITA no log (nao e' um silencio)  LOAD_RESUME_HELD level=leve commit=97.0% cpu=95.0% why=commit>=80% — a carga subiu entre a descida e a carga do motor; o motor FICA estacionado e o audio continua a esperar
  GREEN e o audio continua TODO a espera (a carga subiu, ele fica para depois)  held=25 dropped=0
```

ARM 25 — N blocks in, the same N in the log, one model load:

```
  GREEN a linha da retoma leva o N e o audio_s do backlog entregue  LOAD_RESUME level=leve blocks=37 audio_s=3.70 engine=parakeet commit=12.0% cpu=6.0% why=calmo — …
  GREEN e o lote do parakeet recebeu esse mesmo audio  REDUX_BATCH_KICK reason=load-resume engine=parakeet audio_s=3.7 kicks=1 held_in=37 pid=5048
  GREEN 37 blocos -> 1 carga do motor -> espera a ZERO  loads=1 seconds=0.0
```

Wiring (a function nobody calls passes every arm above):

```
  GREEN o laco do audio CHAMA a retoma (o codigo nao e' um ornamento)  resume_catch_up(switch, resume_gate)
  GREEN o modulo da decisao tem a RETOMA (`ResumeGate`/`resume_calm`)
```

The parking half, and the automatic return to `stream`:

```
ARM 10  GREEN o modelo foi LARGADO (a sessao ONNX cai e o RSS volta)  loaded=False releases=1
        GREEN e a largada esta' no log, com o motivo  REDUX_ENGINE_RELEASE reason=shed-muito-alta engine=parakeet held_s=0.0 — a carga mandou parar; recarrega sozinho quando a carga libertar
        GREEN e RECARREGOU sozinho no lote seguinte  loads=2
ARM 13  GREEN sem pedido, volta a `stream` (o motor recarrega sozinho)  mode=stream
ARM 22  GREEN commit 40 + cpu 95 -> alta (a CPU sozinha ja pede)  alta
        GREEN a RAZAO nomeia a medida que decidiu  subiu: commit=40.0% cpu=95.0% >= limiar de alta
```

### A.3 The code path this measures (file:line, HEAD b92681c)

* The shell publishes the level, it does not kill the process:
  `app/webview/sotto_webview.py:9895-9902` builds `LoadSheddingMonitor` and calls
  `load_shedding().open_action(self, monitor=monitor, log_fn=log)`;
  `app/webview/load_shedding.py:1055` (`open_action`) starts a `LoadGuard` (`:981`) whose
  `_arm_worker_channel` (`:1011`) sets `SOTTO_REDUX_WHEN_HIDDEN=1` in the worker's environment
  **before** the shell spawns it.
* The decision is one number (`LoadAction`, `:755`), with `target()` (`:878`): with the owner's live
  engine on, the *background* is what yields — the file never says `alta` while the gesture wants
  the live engine.
* The return half: `worker/sotto_worker.py:5155` (`_resume_gate`) builds the gate from the **same**
  probe the switch reads; `:5168` (`resume_catch_up`) ticks it per audio block; the call site is
  `:6484-6485`, immediately after `switch.tick()` in `asr_thread`.
* `ResumeGate` is `app/webview/load_shedding.py:529`; the edge is `:563`; the mandatory re-read is
  `LoadProbe.reread` (`:363`) reached from `_reread`; the band is `resume_calm` (`:498`) — it
  refuses to load when commit is *missing*, the opposite direction of `level_for` and deliberate.
* 615 MB is only spent on an edge: `flush_pending` (`worker/engine_switch.py:871`) is the loader, and
  it is also what `maybe_kick` (`:846`) uses — no second transcriber.

### A.4 Real instrument, on this box (not injected numbers)

Run in the eval kernel against the worktree modules:

```
batch_queue._default_level() -> leve | sample_load() -> {'commit_pct': 61.65986848975251, 'cpu_pct': None}
executor.allowed at that level -> True
EDGE leve -> {'resume': True, 'parked': False, 'commit_pct': 61.651769664958955, 'cpu_pct': None, 'why': 'calmo', 'resumes': 1}
next tick (no edge) -> sem-borda
resume_calm(reality) -> (True, 'calmo')
```

The real `LoadProbe`/`GlobalMemoryStatusEx` reading on this machine (commit ≈61.7 % < 80) authorises
the reload, and the *next* tick does nothing — one authorisation per edge, with the product's own
instrument. The pressures above the band (88/94/90/98) are still the shipped thresholds and the
owner's measured 92.5 % regime; they cannot be produced headless, and ARM 24(b) is the arm that
rehearses the refusal.

**[UNOBSERVED]** a `LOAD_RESUME` line in a real app process. The instance on the owner's desktop
(pid 42548) predates `1b97530` by 69 minutes (§0). Restarting the app is the owner's/daily-ritual's
move, not a lane's; nothing in this receipt claims it happened.

---

## B. Card B — unprocessed audio goes to Parakeet in batch when the load releases

There are two edges with audio, and both are measured.

### B.1 Commands and rc

```
$ TMPDIR=I:/cc-tmp python _main/batch-queue-drain-oracle.py
foreign-enqueue-is-picked-up     GREEN pickup=True spawns=1 done=1 manifesto_no_comando=True
no-work-stays-idle               GREEN spawns=0
level-above-leve-does-not-run    GREEN spawns=0 queued=1
inflight-recovers-once           GREEN done=1 spawns=1 ok
run-loop-adopts-dead-spool       GREEN queued=1 inflight=0 done=0 failed=0 errors=[]
VERDICT: PASS (5/5 arms)
rc=0                     (log: _main/_audit-verify/load-resume-verify-batch-drain.log)

$ TMPDIR=I:/cc-tmp python _main/batch-queue-drain-oracle.py --neg-arm
NEG-ARM refresh-desligado GREEN (o defeito volta) pickup=False spawns=0 done=0 manifesto_no_comando=False
NEG-ARM adopt-roots-apagado GREEN (o defeito volta) adopt_roots nunca e atribuido no __init__ -- o `run()` leria um campo que nao existe
NEG-ARM: PASS
rc=1                     (log: _main/_audit-verify/load-resume-verify-batch-drain-neg.log)
```

Both mutants are the two production defects this module already paid for, put back: no `refresh()`
(the queue grows from outside) and no `adopt_roots` assignment (a dead worker's spool is orphaned).
Each makes its arm RED — the detector is proven against the defect, not against a hypothetical.

### B.2 The lines that prove "the load releases and the batch runs" (disk queue)

`load-shedding-oracle` ARM 13 runs the real `BatchExecutor` against a real `BatchQueue` on disk:

```
  GREEN um bloco para transcrever na fila
  GREEN com a carga acima de `leve` o executor NAO arranca nada  state=idle detail=level=muito-alta spawned=0
  GREEN `alta`/`muito-alta` nao sao nivel para o lote
  GREEN com a carga liberta o bloco e' transcrito e marcado `done`  state=done detail=linha
  GREEN e o texto transcrito fica no manifesto  'linha'
  GREEN o filho e' o driver `--transcribe` (um ficheiro, sem dispositivo)
  GREEN a carga a subir a meio do bloco faz o executor CEDER  state=yield detail=load yields=1
  GREEN e o processo do lote e' MORTO (nao fica a competir com o dono)
  GREEN o bloco volta a fila e o ceder NAO conta como falha  state=queued attempts=0
  GREEN o audio continua na fila (nada foi deitado fora ao ceder)  pending_s=0.1
  GREEN o filho REAL arranca com prioridade BELOW_NORMAL (medido com psutil)  nice=16384
```

and the queue's ingress/adoption half (drain oracle): a block enqueued by **another process** is
picked up (`pickup=True spawns=1 done=1 manifesto_no_comando=True`), an `inflight` left by a dead
process runs **once** (`done=1 spawns=1 ok`), and the real `run()` loop adopts a dead worker's spool
(`queued=1 … errors=[]`).

### B.3 The worker's own backlog at the load edge

`ARM 25` (§A.2) is the same order's other half: 37 blocks held while the machine is loaded, then on
the edge `LOAD_RESUME level=leve blocks=37 … engine=parakeet` and `REDUX_BATCH_KICK reason=load-resume
engine=parakeet audio_s=3.7 kicks=1 held_in=37` — the audio that waited enters the Parakeet pass.

### B.4 Code path (file:line, HEAD b92681c)

* Gate: `app/webview/batch_queue.py:618` (`allowed()` = level is `leve`), `:612` (`level()`),
  `:636` (`step()`), `:728` (`run()` re-reads the directory only with no child in flight, `:761`).
* Where the level comes from: `:532` (`_default_level`) calls `load_shedding.sample_load()` +
  `level_for_load` — the **same** instrument as the decision, and on failure it returns
  `muito-alta` (fail-closed: "I do not know" is not "run the batch").
* Measured on this box, not assumed: `_default_level() -> leve`, `allowed() -> True` (§A.4).
  The disk-queue release half in ARM 13 uses an injected `level_fn` (the pressures are injected);
  the *source* of that level is the real function measured here.
* Producers into the disk queue: `queue.adopt_dead_spools` (`:440`) — a dead worker's spool is
  copied in, never removed — plus `enqueue_file`/`enqueue_f32`. The **live** worker's backlog does
  not go to disk: it goes straight into the Parakeet pass through `flush_pending`
  (`worker/engine_switch.py:871`), which is the one-transcriber rule, not a missing wire.

### B.5 Instrument note (honesty, not a card failure)

In this run arm 5 printed `queued=1 inflight=0 done=0`, whereas the same arm in `H:/sotto` printed
`done=1`: its predicate is `queued + done > 0`, so it is satisfied the moment adoption enqueues, and
the strict transcription is read a moment later in the shared `stats()`. What the arm claims —
"the real `run()` adopts" — is what it measures, and its negative arm goes RED when
`self.adopt_roots` is deleted. The transcription of a queue entry is proven independently by arm 1
(`done=1`) and by ARM 13 (§B.2). Worth tightening the predicate to `done >= 1` the next time that
oracle is opened; it is not evidence of a missing behaviour today.

---

## C. Negative controls, both oracles

| oracle | `--neg-arm` | rc | what goes RED |
|---|---|---|---|
| `load-shedding` | 13 mutants | **1** | ordem invertida, canal ×2, derrama, selector, dwell, subida, piso, histerese, restart, cede, cpu-wiring, **retoma (5 arms)** |
| `batch-queue-drain` | 2 mutants | **1** | `_refresh_queue` disabled → foreign pickup False; `adopt_roots` deleted → adoption arm RED |

The resume mutant is the guard this card needed: `ResumeGate._reread` stops consulting
`resume_calm`, i.e. the catch-up would load on the *level* without re-reading the machine. Its five
arms go RED (`resumed=1` on a 97 % machine, `loads=1`, no `LOAD_RESUME_HELD`, no resume line,
`held=0`), which is exactly the stutter the owner forbade.

## D. Battery state (corroboration, not the proof)

`_cache/battery-steps.json` (in `H:/sotto`) already carries both, with the expected rcs:

```
load-shedding             expect_rc=0 rc=0  2026-11-04T11:36:17-0300   (post-lane)
red-as-expected-load-shedding  expect_rc=1 rc=1  11:36:50
batch-queue-drain         expect_rc=0 rc=0  2026-11-04T08:42:38-0300
red-as-expected-batch-queue-drain expect_rc=1 rc=1  08:42:48
```

`app/webview/batch_queue.py` last changed `edf66d9` 2026-11-04 08:36:40 and
`_main/batch-queue-drain-oracle.py` at `6c9f1d6` 01:46:40 — both **before** their 08:42 record, so
the frozen record describes the current files; the fresh run in §B.1 re-measures them anyway.

## E. Files and reproduction

* Added by this lane: `_main/receipt-20261104-load-resume-verify.md`, plus four working logs
  `_main/_audit-verify/load-resume-verify-{load-shedding,load-shedding-neg,batch-drain,batch-drain-neg}.log`
  — local only (`.gitignore:29 *.log`), and regenerable in ~40 s by §E.
* No product file touched. No app launched; no window, no pop-up, no synthetic input.
* The worktree carries a **directory junction**
  `worker/models/parakeet-redux-onnx-int4 → H:/sotto/worker/models/parakeet-redux-onnx-int4`
  (0 bytes copied) because ARM 14 asserts the checkpoint exists; it is gitignored.
* Reproduce exactly:

```
cd H:/sotto-wt/LoadResumeVerify-2
TMPDIR=I:/cc-tmp python _main/load-shedding-oracle.py            ; # rc 0, 215/215
TMPDIR=I:/cc-tmp python _main/load-shedding-oracle.py --neg-arm  ; # rc 1, RED as designed
TMPDIR=I:/cc-tmp python _main/batch-queue-drain-oracle.py        ; # rc 0, 5/5
TMPDIR=I:/cc-tmp python _main/batch-queue-drain-oracle.py --neg-arm ; # rc 1
```
