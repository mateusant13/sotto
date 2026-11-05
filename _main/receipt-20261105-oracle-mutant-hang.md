# Receipt — o passo `panel-hidden-at-startup` prendia a bateria por 35 minutos

Data: 2026-11-05, sessao principal. Instrumento: `_main/panel-hidden-at-startup-oracle.py`.
Nada aqui e' inferido: cada numero saiu de um comando colado abaixo.

## O que se mediu

A bateria leve arrancou as 06:46:34 e **nunca terminou**. O censo de processos nomeou o filho:

```
06:46:34 pid=54836  cmd.exe      cmd /c _main\_audit-verify-all.cmd
06:52:49 pid=58708  python.exe   python _main\panel-hidden-at-startup-oracle.py
```

`py-spy dump --pid 58708` (processo VIVO, 35 min depois de arrancar):

```
Thread 40344 (active+gil): "MainThread"
    arm_paint_ack (sotto_webview_pre-fix-shape.py:12018)
    show_panel (sotto_webview_pre-fix-shape.py:13070)
    _owner_ask (panel-hidden-at-startup-oracle.py:791)
    run (panel-hidden-at-startup-oracle.py:767)
    arm_hidden (panel-hidden-at-startup-oracle.py:982)
    arm_mutation (panel-hidden-at-startup-oracle.py:1117)
```

Ou seja: a trava estava **dentro do mutante**, no caminho do show. Corrida standalone com
`timeout 120` nunca passou do braco EXTERNAL-FLAG — reproduzivel.

Repetido com o mutante nomeado e output sem buffer, a pilha do proprio fio saiu:

```
_on_before_show -> _start_ui_watchdog -> _start_slow_read_monitor
  -> _start_power_recovery -> power_recovery.attach -> Event.wait
```

Todas as esperas dessa cadeia tem prazo (5 s no `attach`), e mesmo assim o fio nao voltou:
o que prende e' o **estado do processo** — cada mutante era carregado no MESMO interpretador,
com o CLR/pythonnet de cada copia. Prova de que e' artefacto do harness e nao da shell: o
mesmo mutante (`ticket-repro`, que tem de ficar SADIO) travou numa corrida e passou na
seguinte, com o codigo da shell identico entre as duas.

## A cura

1. **Cada mutante corre no seu proprio `python`.** `run_mutant_isolated()` larga o filho com
   `CREATE_NO_WINDOW` (a regra das janelas) e `timeout` de parede; o filho imprime
   `MUTANT-RESULT <json>`.
2. **O filho mata-se a si proprio com a pilha na mao.** `faulthandler.dump_traceback_later(
   MUTANT_ARM_DEADLINE_S, exit=True)` — uma trava custa o prazo (90 s) e deixa no log do passo
   as frames que nunca voltaram, em vez de um silencio.
3. **Um mutante travado e' APANHADO**, e o veredicto diz que foi por trava; um mutante do tipo
   "tem de ficar sadio" e' FALHA se travar (as duas coisas nao se confundem).

## Depois

`python _main/panel-hidden-at-startup-oracle.py --repeats 2` — **69,1 s**, `ORACLE GREEN
failures=0`, `VERDICT: PASS`; os quatro mutantes correm em processos separados e o
`ticket-repro` da' `expected=immune ... the oracle correctly finds visibility intact`.
O braco negativo continua a falhar por desenho: `--neg-arm` → `NEG-ARM PASS mutants 3/3`,
rc=1, 2,4 s.

Antes: 35+ min presos e a bateria inteira perdida. Depois: 69 s e verde.
