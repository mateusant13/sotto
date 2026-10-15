# A CAUSA DO TRAVAMENTO: O HOT-RELOAD ESTAVA LIGADO NA APP DO DONO -- E ERA EU QUE O DISPARAVA

O dono, seis vezes em tres dias: *"quando sotto abre ou fecha, o pc trava"*, *"abrir ou
fechar o sotto causa travamento no meu pc. arruma"*, *"e por que fechar o sotto ainda
trava meu sistema? arruma tudo"*, *"resolve tudo q eu falei sobre sotto travar. por
que ta travando ainda"*.

## O QUE EU MEDI HOJE, com a app DELE a correr

  SHELL  pid=19884  arrancou 04:08:07  RAM 53 MB
  + 2 WebView2 do shell .............. 132 MB
  WORKER pid=17872  arrancou 04:08:10  RAM 81 MB
  ------------------------------------
  TOTAL DO SOTTO .................... 266 MB   4,2% de um core

E o worker ESTA a transcrever: `BRIDGE_CAPTION_SENT delivered=true` as 12:55. O shell
nao reiniciou (de pe desde as 04:08). O Alt+C funciona: `PANEL_SHOWN reason=hotkey
mode=strip` e a seguir `mode=side`.

**266 MB e 4,2% de um core NAO trava PC nenhum.** O estado estavel nao e o problema.

## ENTAO O QUE E, e esta no log

  STAGING_LOADED -> RECEIVER_READY -> PRELOAD_ACTIVE
  12:43:00 · 12:43:14 · 12:43:45 · 12:45:58 · 12:49:56

A pagina RECARREGOU cinco vezes em sete minutos. E o evento que a dispara:

  12:49:55.372  HOT_RELOAD_EVENT kind=panel file=panel.css action=3
  12:49:55.793  HOT_RELOAD_FLUSH kind=panel files=["panel.css"]
  12:49:55.813  HOT_RELOAD_PANEL_DONE reload=10
  12:49:56.256  HOT_RELOAD_APPLIED reload=10

E o `panel.css` tem mtime **12:49:55** -- porque EU o acabei de editar. `hot_reload.py`
vigia `PANEL_ASSETS = (panel.html, panel.css, panel.js)`, e cada escrita num deles
**recria o renderer, re-parseia treze scripts e reconstroi o DOM na maquina que o dono
esta a usar.**

## PORQUE E QUE ISTO ESTAVA LIGADO

O codigo dizia:
    if args.no_hot_reload:  log(DISABLED)
    elif not shell.start_hot_reload():  warn(...)

Ou seja: **arrancava a nao ser que fosse pedido o contrario** -- e o `run.cmd` (o
ficheiro que o dono clica) nao passa flag nenhuma. **Uma funcao de DESENVOLVIMENTO
estava armada em PRODUCAO**, e qualquer escrita minha num ficheiro do painel entrava
dentro da app dele e recarregava-lhe o painel.

## A CURA

O default inverteu-se: `--hot-reload` e ADESAO, e `--no-hot-reload` continua a
funcionar para nao mudar o sentido de nenhum script nem oraculo que ja o passe. Sem
flag -- que e como o `run.cmd` arranca -- o log passa a dizer:

    HOT_RELOAD_DISABLED reason=off-by-default (a development feature...)

Medido: `py_compile` rc=0; `run.cmd` nao passa nenhum dos dois, portanto a app do dono
arranca com o hot-reload DESLIGADO.

## O QUE O DONO TEM DE FAZER

**Fechar e reabrir o Sotto.** A app que esta a correr agora (pid 19884) tem o codigo
VELHO -- o hot-reload ainda la esta. A cura entra no proximo arranque.

## E UMA NOTA QUE EU DEVO, porque a causa era eu

Isto nao era um defeito antigo a esconder-se: era **cada vez que eu editava o painel**,
a app dele recarregava. Ele queixou-se seis vezes e eu procurei o defeito no loop
JS<->Python, no churn do worker, no modelo -- em tudo menos no gesto que eu proprio
fazia cem vezes por dia.
