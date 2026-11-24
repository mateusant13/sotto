# 2026-11-24 — a fila relia o directorio 360×/h com o resultado igual, e dizia-o 2288 vezes

## O que estava medido no log do dono

```
BATCH_QUEUE_ORPHANS manifests_without_audio=2 dir=I:\cc-tmp\sotto-batch-queue    x2288
THREAD_CPU total=10% top=sotto-batch-executor:5% yt-clock:3% ...
```

`BatchQueue.refresh()` corria a cada `poll_s` (10 s, **360×/h**), fazia `listdir` + um
`open`+`json.load` por manifesto, com o resultado **sempre o mesmo**, e escrevia a mesma linha de
log 2288 vezes. Agregado das 29 amostras de `THREAD_CPU` desde 14:30: **total da shell 12,6 % de um
núcleo**, `yt-clock` 6,0 %, `sotto-batch-executor` 4,7 %.

## A cura: o directorio cujos nomes não mudaram não se relê

`app/webview/batch_queue.py:262` — `refresh(force=False)` guarda a **lista de nomes** que o `listdir`
já devolve; nomes iguais ⇒ devolve o retrato em RAM sem um único `open`. A primeira leitura corre
sempre (`_scan_stamp is None`) e `force=True` lê sempre, logo a recuperação de `inflight` depois de
um crash não perde nada.

**Porque não o `st_mtime_ns` do directorio** — medido nesta máquina: no NTFS o carimbo do
directorio actualiza-se de forma preguiçosa e `os.stat` devolve o valor antigo por segundos. O braço
A3 do oráculo criou um manifesto e a leitura seguinte respondeu `scans=1`: a guarda escondia trabalho
NOVO. Um NOME é a testemunha certa; um manifesto reescrito no sítio pelo mesmo processo não precisa de
releitura, e nenhum outro processo reescreve um manifesto existente (`enqueue_f32` cria id novo).

A linha de log passa a ser dita **só quando o número muda** (`_orphans_logged`), com o mesmo
argumento: um conjunto de órfãos que não mudou não informa ninguém.

## Antes / depois, mesmo instrumento (2 manifestos, 2000 leituras cada)

| | `refresh()` por chamada | × | linhas de log |
|---|---|---|---|
| antes (`HEAD` `4210aaff18` → `git show`) | **10,9529 ms** | — | 2000 |
| depois | **1,3309 ms** | **8,2×** | 1 |

Contadores do módulo: `scans` (leituras reais), `scan_skips` (guardas). Num laço de 3 refinamentos
com o directorio inalterado: `scans=3 skips=4`.

## Portões

* `_main/batch-queue-scan-oracle.py` — **11/11 arms** (`A1` primeira leitura lê; `A2`/`A2-bis`
  inalterado não relê e devolve o mesmo retrato; `A3` manifesto novo lê e diz o órfão; `A5`/`A5-bis`
  o número novo é dito uma vez e é o número certo `1,2,3`; `A4`/`A4-bis` a dedupe segura mesmo em
  `force=True`; `A6` `force` lê sempre; `A7`/`A7-bis` o payload que chega entra na fila) e
  `--neg-arm` **2/2 mutantes** (guarda desarmada → A2 RED; dedupe desarmada → A4 RED), rc=1, linha
  literal `NEG-ARM PASS`.
* Ligado à bateria: `batch-queue-scan` (always 0) + `red-as-expected-batch-queue-scan` (expectred 1,
  `NEG-ARM PASS`) em `_main\_audit-verify-all.cmd:2350-2360`.
* Regressão no executor REAL: `_main/batch-queue-drain-oracle.py` **6/6 GREEN**, incluindo
  `foreign-enqueue-is-picked-up pickup=True spawns=1 done=1` — a guarda não esconde a fila de fora.
* `_main/agents-md-pins-oracle.py` PASS com o pin re-medido (**420385 B**, 4806 CRLF, sha256
  `522BBAD0…`).

## O que NÃO fica provado

`UNMEASURED` — o `THREAD_CPU` da shell viva depois do arranque com este código. Linhas que o provam
no próximo arranque: (1) nenhuma repetição de `BATCH_QUEUE_ORPHANS` com o mesmo número; (2)
`sotto-batch-executor` fora do topo do `THREAD_CPU total=..% top=..`. O resto dos 4,7 % desse fio
(fóra do `refresh`, que vale no máximo 0,11 % a 0,1 Hz) **não está atribuído** e fica como item
aberto — não é reclamado aqui.

## Custo declarado

Um filho caged (`python -m watcher run --cpu 40 --single --io very-low`), 13,9 s de parede, um
processo, ≤4 fios, RSS ≤1,2 GiB, leitura do motor Parakeet uma vez. Nada em paralelo.
