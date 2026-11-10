# RECIBO — o motor quente nunca subiu: `/run` para uma tarefa que não existia

Tudo o que segue foi medido nesta árvore e nesta máquina, 2026-11-10. Onde uma linha diz
`PASS` ou um número, o comando está ao lado.

## 1. O card do dono, e o que a medição respondeu

Card: *"p0 arranque: demora DEMAIS a responder a keybindings/qualquer coisa -- tornar extremo"*.

A primeira suspeita era a shell. **Refutada, com número.** Reconstruído o arranque da última
sessão dele (`_main/webview-run.log`, pid 52792):

| instante | linha |
|---|---|
| 0,000 s | `SHELL_STARTUP_STAGE pid=52792` |
| 0,145 s | `CAPTION_OVERLAY_CREATED hwnd=16782796` |
| 0,155 s | `HOTKEY_REGISTERED role=panels accelerator=Alt+C register=true` |
| 0,159 s | `CAPTION_PIPELINE_START reason=pre-webview` |
| 3,491 s | `UI_WATCHDOG_STARTED` |
| 6,418 s | `PANEL_SHOWN reason=hotkey-cycle-strip` — **a tecla dele foi pressionada a 5,851 s** |

Alt+C responde em **0,567 s** desde a pressão, 6,4 s depois do arranque. A shell não é o
problema. O que continua a demorar é o **modelo**:

```
2026-11-09 21:22:30  BRIDGE_LOAD_MS ms=44344 pid=30804 worker_load_s=42.59 load_bg_closed_by=deadline
```

**42,59 s** de carga, em cada arranque.

## 2. A causa: a tarefa do motor quente não existia

O motor quente (desenho `state/design/warm-worker-20261104.md`, motor fora da shell, `attach`
a 0,97 s) é criado pelo **Agendador de Tarefas** (`\SottoWarmEngine`, R1: `schtasks` é o pai,
nunca um `Popen` da shell). O XML que a define está no repo desde 2026-11-04
(`_main/warm-engine/warm-engine-task.xml`). Medido hoje:

```
$ schtasks /query /tn SottoWarmEngine /v /fo LIST
rc 1
ERRO: O sistema não pode encontrar o arquivo especificado.
```

E no log do dono, **11** ocorrências, todas iguais, uma por arranque:

```
WARM_ENGINE_START_TASK task=SottoWarmEngine rc=1 out="" err=""
```

`schtasks /run` numa tarefa ausente devolve 1 e **não faz nada**, em silêncio. O motor quente
nunca subiu; cada arranque pagou a carga a frio. A linha de log que existia não distinguia
nada: `rc=1 out="" err=""` é o mesmo texto para "a tarefa não existe", "a tarefa recusou" e
"o agendador está morto".

## 3. A cura

`app/webview/sotto_webview.py`:

* `WARM_ENGINE_TASK_XML` — o caminho do XML que já existia.
* `ensure_warm_engine_task()` — consulta a tarefa; se faltar, **regista-a** (`/create /tn <task>
  /xml <xml> /f`) pelo `_main/hidden-launch.py` (o único largador sancionado: `schtasks` é uma
  app de consola e a shell corre em `pythonw`). Devolve `present` / `created` / `failing`, e
  **nunca levanta**: o motor quente é aceleração, e a escada fria tem de continuar a funcionar
  quando ele não sobe (INV-3).
* `start_warm_engine_task()` chama-a antes do `/run`, e a linha passou a
  `WARM_ENGINE_START_TASK task=.. rc=.. registered=.. out=.. err=..`.

## 4. Medido depois da cura, nesta máquina

```
WARM_ENGINE_TASK_ABSENT   task=SottoWarmEngine query_rc=1 xml_exists=true
WARM_ENGINE_TASK_CREATED  task=SottoWarmEngine rc=0 out="" err=""
$ schtasks /query /tn SottoWarmEngine /fo LIST
rc 0
Nome da tarefa: \SottoWarmEngine   Status: Pronto   Modo de Logon: Interativo apenas
```

Com a tarefa registada (lease `heavy` `94cd5c533dd44605920b435e2b9cf5bf`, gate **GREEN** antes):

```
$ schtasks /run /tn SottoWarmEngine      -> rc 0        (era rc=1 em 11 de 11)
_main/warm-engine.pid                    -> 52320, escrito em 1,0 s
2026-11-10 06:33:59  WARM_PIPE_READY name=\\.\pipe\sotto-warm-1-nemotron-...
2026-11-10 06:34:40  WARM_LOAD_MS ms=41015.3 resident_mb=239.7
```

O motor carrega **uma vez** (41,0 s, 239,7 MB residentes) e fica PARQUEADO à espera do
`attach`. O número de aceitação do card é o do attach — 0,97 s medidos contra os 42,59 s da
carga a frio —, e ele só se confirma quando a app arrancar com o motor quente por baixo: isso
é **`fixed, NOT verified`** até o dono a abrir.

## 5. O portão

`_main/warm-engine-task-oracle.py` (novo) mede no **Windows desta máquina**, não num fake:

| arm | o que exige | medido |
|---|---|---|
| A0 | a tarefa de teste não existe antes | rc≠0 |
| A1 | uma tarefa ausente é REGISTADA | `created` |
| A1b | e o Windows passa a conhecê-la | `schtasks /query` rc=0 |
| A2 | a segunda chamada é idempotente | `present` |
| A3 | o XML fixa `ExecutionTimeLimit=PT0S` | true (sem limite de 3 dias, F14) |
| A3b | o XML fixa `MultipleInstancesPolicy=IgnoreNew` | true (twin lock #1) |
| A4 | o XML aponta para o largador do repo | `warm-engine-run.cmd` |
| A5 | a linha de log carrega `registered=` | true |
| A6 | a tarefa de teste é APAGADA no fim | rc≠0 |

`python _main/warm-engine-task-oracle.py` → **`VERDICT: PASS (rc=0)`**.

**Braço negativo — e uma correção de instrumento dentro dele.** A primeira versão trocava a
**expectativa** no `--neg-arm` (`want='failing'`) e o mutante passava: um controlo que não pode
falhar, a classe que esta casa já pagou. Agora o braço negativo **muta o código** extraído por
`ast` (M1: o `/create` perde o `/xml`; M2: o veredicto mente `created` sem olhar ao rc) e exige
o vermelho:

```
$ python _main/warm-engine-task-oracle.py --neg-arm   -> rc=1
FAIL A1b e o Windows passa a conhece-la
FAIL A2 a segunda chamada e idempotente
NEG-ARM: PASS -- 2 arm(s) vermelhas
```

Os dois passos entram na bateria (`warm-engine-task` + `red-as-expected-warm-engine-task`,
classe `always` — leem o estado vivo do Windows).

## 6. Pins e portões de apoio

* `_main/_audit-verify-all.cmd` = **341051 B**, **3972 CRLF** / 0 bare LF,
  sha256 `AE965FD0402DC28BC2C84DF1B3D8ABC2451BA5ABD64446DF09D866E56B1D1AF6`;
  `agents-md-pins-oracle.py` → `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.
* `battery-wiring` PASS `ligados=180 sem_passo=108 populacao=288`, `new-unwired PASS`.
* `battery-record-pairing` 444 passos / 444 nomes com registo / 0 achados.
* `battery-class` PASS arms=3.
* `battery-budget` invocado **fora** da bateria dá RED por um motivo que não é meu:
  `politica de largada diferente do baseline (baseline='cap40', corrida=None)` — a corrida
  standalone não regista política. O julgamento válido é o da corrida.

## 7. O que NÃO está verificado

* **A primeira legenda dele com o motor quente.** O `attach` é medido pelo
  `_main/warm-engine-oracle.py` (22 arms) contra um motor falso; o número real de ponta a ponta
  exige a app aberta por ele. `fixed, NOT verified`.
* O motor quente parqueia com TTL de **600 s**; se ele abrir a app mais de dez minutos depois,
  o próximo `/run` paga a carga outra vez. Isso é o desenho (R4: nenhum gatilho no logon, para
  o carregamento não cair numa janela carregada), não um defeito — mas o número que ele sente
  depende de QUANDO abre a app.
