# O LACO DE RECARGA DO WORKER — 1,9 GB de modelo por cada dois minutos

**Data:** 2026-11-04, 03:1x-04:0x (hora local da maquina)
**Objetivo que este recibo serve:** *"torna tudo 10x mais leve e rapido com mesma qualidade."*
**Instrumentos:** `_main/worker-churn-oracle.py` (novo, par na bateria), `py-spy 0.4.2` via
`_main/launch-as-token.py` (o worker e a shell correm em integridade `high`; o `py-spy` desta
pane nao abre o processo — `Acesso negado` — e o token da app resolve isso sem elevar nada),
`_main/worker-churn-oracle.py --neg-arm`, `_main/live-code-freshness-oracle.py --strict`.

## O DEFEITO, MEDIDO

O log VIVO (`_main/webview-run.log`), sem eu tocar em nada:

```
03:18:03  BRIDGE_SPAWNED pid=26440
03:20:13  BRIDGE_SILENT ms=30000 pid=26440
03:20:14  BRIDGE_KILLED pid=26440 rc=1 why=the-shell-terminated-it
03:20:14  BRIDGE_SPAWNED pid=17044          <- 1,9 GB de modelo recarregado
03:22:41  BRIDGE_EXIT pid=17044 rc=0 killed=False
03:22:43  BRIDGE_SPAWNED pid=37212          <- 2,0 s depois: outra recarga completa
```

Duas metades independentes do mesmo desperdicio:

1. **Um tap aberto sobre uma maquina QUIETA nao escreve nada por desenho.** O ramo
   `endpoint-idle` do laco espera em `stop.wait(0.1)` (`worker/sotto_worker.py`, ~:6910) e
   `WORKER_STATS` so' conta como progresso quando `blocks` AVANCA — logo o cao de guarda de 30 s
   mata um worker saudavel e paga a recarga.
2. **`rc=0` nao e' um crash.** O retry de 1 s (`backoff_base=1000`) existe para uma morte com
   excecao; aplicado a um worker que terminou por vontade propria (escada de dispositivos
   esgotada), so' faz o laco de recarga.

## O QUE MUDOU

`worker/sotto_worker.py` — **o laco publica que avancou:**

* `PROGRESS = {'seq', 'phase', 'at'}` + `progress(fase)`, chamado no cabecalho do laco de
  candidatos (`ladder`), na volta da janela (`window`) e na espera do endpoint ocioso
  (`idle-wait` — o sitio exacto onde o silencio matava).
* `start_heartbeat(every_s=8.0)`: um fio que publica `WORKER_ALIVE seq=.. phase=.. age_ms=..` **so'
  enquanto o `seq` MUDA**. E' prova de PROGRESSO, nao de liveness: um laco travado cala-se e o cao
  de guarda continua a apanha-lo. `sys.stderr.write('\n' + msg + '\n')` — o `\n` a frente existe
  porque o ONNX escreve WIDESTRING sem newline e prefixa a linha.
* `WORKER_ALIVE_ARMED every_s=.. thread=..` no arranque do fio: *"o batimento nao chegou"* deixou
  de ser indistinguivel de *"o batimento nunca foi armado"*.

`app/webview/sotto_webview.py` — **a shell credita o batimento e poe piso na saida limpa:**

* `is_alive_beat(line)` = `'WORKER_ALIVE' in line` (uma funcao so', que o oraculo executa e o braco
  negativo muta) + `PROGRESS_TAGS` ganhou `'WORKER_ALIVE'`; o ramo chama `_arm_silence()` e escreve
  `BRIDGE_ALIVE ...` uma vez por minuto via `log_repeat` (o mesmo mecanismo do `HOTKEY_OBSERVER_ALIVE`).
* `CLEAN_EXIT_FLOOR_MS = 20000`: uma saida `rc=0` nao volta em 1 s. O piso nomeia-se no log
  (`BRIDGE_RESTART_FLOOR ... why=clean-exit-not-a-crash`).

## A ARMADILHA QUE CUStou A TARDE (e ficou no AGENTS.md)

A primeira versao do ramo ficou **depois** do `continue` que fecha o bloco de stderr do `_pump`:
inalcancavel. Duas instancias carregaram a cura — worker a bater `seq=516 phase=window` (visto com
`py-spy dump --locals`), as linhas no `stderr_tail` do `BRIDGE_EXIT` — e **zero** `BRIDGE_ALIVE`
saiu. O `py-spy --locals` no fio `sotto-worker-stderr` mostrou a ultima linha processada a ser o
proprio batimento, o que apontou o `continue`. O ramo passou para dentro do bloco.

## A SEGUNDA METADE — O TETO DE ROTACOES NAO PODE SER UM CICLO DE RECARGA

Depois de a shell parar de matar o worker quieto, ficou o outro churn, medido no mesmo log:

```
03:52:17  BRIDGE_LOAD_MS ms=9469 pid=30160
03:55:18  BRIDGE_EXIT pid=30160 rc=0 killed=False spawns=1 captions=0   <- 181 s, 0 legendas
```

O worker abriu todos os candidatos, nenhum entregou um bloco (maquina em silencio) e o **teto de
rotacoes** — que esta' certo, e nasceu dos 2 188 `reason=flat` em dez minutos — fez o processo SAIR.
A consequencia era a recarga dos 1,9 GB a cada ~3 min.

`hold_idle_slot` (worker, ao lado do batimento): quando **nada podia ter sido capturado**
(`should_hold`: `captions == 0` e o desfecho e' `rotation-ceiling`/`all-flat`/`open-failed`/
`explicit-flat`), o processo **fica com o modelo residente**, chama `progress('idle-wait')` a cada
`IDLE_HOLD_POLL_S` (10 s, bem dentro dos 30 s do cao de guarda) e sai quando:

* o **CENSO DE DISPOSITIVOS muda** (um fone entrou) -> `census-changed`, a shell recarrega em 20 s
  com um censo fresco;
* o dono pede parada -> `stopped`;
* a espera acaba (`IDLE_HOLD_MAX_S` = 600 s) -> `hold-expired`.

Um worker que JA' deu legenda nunca espera: a escada e' dele e a proxima volta vale a pena.

## PROVA

Oraculo, **10 arms** (executa o `WorkerBridge._schedule_restart` REAL com `threading.Timer` falso, a
regra do LEITOR sobre a linha real, o `progress()` do worker real, e a espera ociosa com um `stop`
e um censo FALSOS):

```
PASS 1-floor-on-clean-exit   armed_ms=20000 (com piso)
PASS 2-no-floor-on-crash     armed_ms=1000  (caminho do crash, sem piso)
PASS 3-reader-counts-the-beat  startswith_would_miss=True (a linha prefixada pelo ONNX conta)
PASS 3b-reader-ignores-the-meter
PASS 4-worker-progress-moves
PASS 5-hold-only-when-nothing-captured  (captions>0, stop, e um run saudavel NAO esperam)
PASS 6-hold-ends-on-census-change
PASS 7-hold-ends-on-stop
PASS 8-hold-expires          held_s=0.063 polling=0.01
PASS 9-hold-keeps-the-beat-moving  phase=idle-wait
VERDICT: PASS arms=10 fail=0
--neg-arm: rc=1, caidas=[1-floor-on-clean-exit, 3-reader-counts-the-beat,
                          4-worker-progress-moves, 5-hold-only-when-nothing-captured,
                          6-hold-ends-on-census-change]   (5/5 curas mutadas)
```

Vivo, na instancia `4552` (pid da shell) com o modelo carregado em **9,5 s**:

```
03:52:17  BRIDGE_LOAD_MS ms=9469 pid=30160
03:52:26  BRIDGE_ALIVE WORKER_ALIVE_ARMED every_s=8.0 thread=sotto-heartbeat
03:52:34  BRIDGE_ALIVE WORKER_ALIVE seq=120 phase=window age_ms=1983
03:52:42  BRIDGE_ALIVE WORKER_ALIVE seq=208 phase=window age_ms=30
...
```

Contra a linha de base de 03:20:13 (**morto aos 130 s**), a instancia com a cura atravessa a janela
de silencio com batimentos e **sem** `BRIDGE_SILENT`/`BRIDGE_KILLED`.

## PINS

* Bateria: `_main\_audit-verify-all.cmd` = **195043 B**, **2444 CRLF** / 0 bare LF,
  sha256 `C6E14C3CD65E70F5EB6009DDC8EE7B11C797FCFE121C3855886F3A969B3B9C40`
  (`agents-md-pins-oracle.py`: PASS; `battery-wiring-oracle.py`: 100/124; `battery-class-oracle.py`: PASS).
* `worker/sotto_worker.py` e `app/webview/sotto_webview.py`: 0 bare LF (CRLF preservado nos dois).

## O QUE NAO ESTA PROVADO

* `verified` continua fora de alcance de uma lane (sem verificador independente e sem uma corrida
  real de horas): o que este recibo entrega e' **medido na maquina viva**, com braco negativo.
* O `CAPTION_PAINT_LAG` p90 da serie historica e' 6,7 s (`p50` 208 ms) — a cauda provavelmente
  inclui janelas com a webview escondida (timers congelados). Nao foi investigada nesta lane.

## A MEDICAO DE 04:1x — O QUE ELE SENTE COMO "TRAVA O PC"

Feita com o dono a jogar (`deadlock.exe` a 405 % de CPU, 4 273 MB) e o worker do Sotto a 270 %:

```
maquina: 20 nucleos logicos, cpu 56 %, memoria 58,6 %
deadlock.exe  405 % CPU  4 273 MB
sotto_worker  270 % CPU  1 877 MB   (ja' BELOW_NORMAL: o jogo ganha a fila)
```

Duas conclusoes medidas, e uma pendencia nomeada:

1. **A prioridade do worker esta' no sitio certo.** Ele entra em `PROCESS_MODE_BACKGROUND_BEGIN`
   durante o carregamento e volta a `BELOW_NORMAL` (`_leave_load_background_mode`). Medido: 145,8 %
   -> 5,1 % num instante em que o jogo subiu a 368 %, e de volta a 270 % quando o jogo folgou.
   Quem cede e' o worker; e' o desenho a funcionar.
2. **O churn de recarga — o "loading toda hora" dele — e' o que produzia os engasgos mais visiveis**,
   e e' o que este recibo fecha.
3. **FECHADO (2026-11-04, 04:3x): a CPU do sistema estava fora da decisao.**
   `load_shedding.LoadShedding.observe(commit_pct, cpu_pct=None)` **aceitava** CPU, `level_for_load`
   juntava as duas medidas com `CPU_HIGH_PCT = 90` / `CPU_VERY_HIGH_PCT = 98` — e
   `LoadSheddingMonitor.run()` chamava `self.state.observe(reading)` **sem** `cpu_pct`. A capacidade
   existia e era inalcancavel (a classe de defeito que este repo ja' nomeia). O que mudou:

   * `load_shedding.SystemCpu`: a leitura do proprio Windows (`GetSystemTimes`, sem `psutil`, sem
     permissao, sem abrir dispositivo). `None` na primeira amostra — um percentual pede duas, e
     `None` nao pede nada.
   * `LoadSheddingMonitor`: `self._cpu = SystemCpu()`, `run()` faz `self.step(reading, self._cpu.sample())`,
     `step(reading, cpu_pct=None)` entrega-o ao `observe`, e o log publica `cpu_pct=` — o numero que
     decidiu, nao o adjectivo.
   * Medido: `SystemCpu` deu **67,2 %** num intervalo de 1 s (a maquina a 56-67 % segundo o
     `psutil`), e `level_for_load(40, 95) -> 'alta'`, `(40, 99) -> 'muito-alta'`, `(40, None) -> 'leve'`.

   Oráculo: `_main/load-shedding-oracle.py` **ARM 22** (10 checks, 3 deles de FIACAO: o monitor
   amostra, entrega, e o log publica) — **LOAD-SHEDDING GREEN, arms=183, fail=0**; `--neg-arm`
   rc=1 com **12/12** mutantes apanhados, incluindo `neg_arm_cpu_wiring` (o monitor amostra e
   descarta) que derruba exactamente as duas arms de fiacao (`fail=2`).

## O QUE ESTA LANE NAO FAZ ENQUANTO ELE JOGA

Nada pesado: nem bateria, nem largada da app, nem varrimento do log inteiro (61,8 MB). O censo de
processos de instrumento, medido depois de parar: **0**.

