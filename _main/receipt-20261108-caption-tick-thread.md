# RECIBO — o relogio do overlay criava um FIO por frame (2026-11-08)

## O que o watcher mediu, e o que isso nomeia

`I:/!manager/state/herdr-inbox/dm-b3a60c01c7c15abc09b.md` (DM do proprio `watcher` ao assento,
2026-11-08 02:33): arvore de **8 processos** do `sotto_webview.py` (pid 45084), **9,7 % da maquina**,
`interrupt=20.755 %` do tempo de CPU em `cpu time>=10` e **`creation=90.879 creations/s`**. O pedido
dele e' o que a regra do dono de 2026-11-07 exige: **nomear a linha, declarar o tecto, provar antes e
depois.**

O pid 45084 arrancou as **00:48:51** (`--no-self-relaunch`), com 56 fios e 185 MB: ele e' a instancia
do dono e NAO carrega esta cura. A medicao do watcher descreve, portanto, o codigo ANTERIOR a esta
mudanca -- que e' o codigo certo para julgar.

## A linha

`app\webview\caption_overlay.py`, `NativeCaptionOverlay._arm_tick`:

```python
timer = threading.Timer(delay, lambda: self._tick(gen))   # UM FIO POR QUADRO
```

`_next_delay` arma um frame de 16 ms (`word_fade.FRAME_S`) enquanto houver palavra a revelar ou uma
linha a subir, e o roll-up que o dono pediu hoje armou exactamente essa janela. A 16 ms isso e' um
`CreateThread` + `WaitForSingleObject` **por quadro**, ~62 por segundo com a legenda ao vivo.

E' a unica criacao por frame que a app tem: `grep -n "Popen|subprocess.run|check_output"` em
`youtube_cdp_source.py` e `youtube_captions.py` da' **zero** -- o caminho do YouTube e' websocket/HTTP,
nao processo. As outras criacoes de fio da shell sao de arranque (`sotto-tray`, `sotto-ui-watchdog`,
`sotto-log`, ...) e de sonda (`--exit-after`, `run_stats_probe`), nenhuma por frame.

## A VARREDURA DA CLASSE (o irmao, nao so' o sitio)

`grep -n "threading.Timer\|threading.Thread("` em `sotto_webview.py` devolve sete `Timer` e sete
`Thread` de producao, e os sete `Timer` estao todos atras de uma bandeira de SONDA: `--probe-edit-mode`
(12454), `--exit-after` (12543/12553), `--probe-stats-wait` (12564), `--probe-v2` (12568),
`--dump-dom-wait` (12581), `--probe-outside-click` (12594). Uma sonda arma UM timer e morre. Os
`Thread` de producao sao de ARRANQUE (`sotto-tray`, `sotto-ui-watchdog`, `sotto-log`,
`_cpu_census_thread`, `_yt_clock_thread`, `sotto-panel-stall`, `sotto-exit-escalator`): um cada.
**O relogio do overlay era o unico criador de fio por FRAME da app inteira**, e agora e' zero.

## A cura

Um fio `daemon` unico (`sotto-caption-tick`) que espera num `threading.Event` com PRAZO: o
`_arm_tick` grava `_tick_deadline` (monotonic), sinaliza o `Event` e nunca cria fio nenhum; o laco
acorda no prazo, confere `gen`/`deadline` sob o `RLock` (que ja' era `RLock`, logo `_update ->
_arm_tick` nao se tranca) e chama o `_tick` real. Sem nada a mudar (`delay is None`) o fio **espera
1 s no Event** em vez de girar. O `destroy()` poe `_tick_stop`, sinaliza e o fio morre.

## As provas

| prova | comando | resultado |
|---|---|---|
| o relogio ainda PINTA e nao ha criacao por frame | `python _main\caption-tick-thread-oracle.py` | `VERDICT: PASS (5/5)` |
| o braco antigo cai | `python _main\caption-tick-thread-oracle.py --neg-arm` | `NEG-ARM: PASS` (A2: 105 `threading.Timer` em 1 s; A3: cresceu 2) |
| os vizinhos da legenda nao regrediram | `caption-rollup-oracle`, `youtube-1to1-oracle`, `reveal-clock-oracle`, `paint-row-seam-oracle`, `caption-switch-race-oracle` | `PASS (8/8)`, `GREEN`, `PASS arms 5/5`, `PASS`, rc=0 |
| o par esta' na bateria e a classe esta' certa | `battery-wiring-oracle.py` / `battery-class-oracle.py` | `PASS checks=7 fail=0` / `PASS arms=3` |
| nenhum sitio novo abre janela | `console-window-audit.py` | `PASS -- 0 sitio(s)` |
| o pin do `AGENTS.md` e' o ficheiro medido | `agents-md-pins-oracle.py` | `PASS -- 2 pin(s), 0 failure(s)` |

**O custo, medido no MESMO banco de ensaio** (5 s de frames de 5 ms, `_tick`/`_update` reais, so' o
`_update` conta em vez de desenhar):

| relogio | CPU de um nucleo | frames | custo por frame |
|---|---|---|---|
| ANTIGO (`Timer` por frame) | 8,1 % | 866 | 0,0094 % |
| NOVO (fio unico) | 2,2 % | 319 | 0,0069 % |

O banco nao mede so' o churn: conta tambem o `_tick`. A parte que o churn explica e' a **diferenca**
(-28 % por frame) e a contagem crua: **105 criacoes de fio por segundo** contra **zero**.

## O tecto declarado (regra do dono, 2026-11-07: mandar otimizar, nunca parar)

- criacoes de fio do overlay por frame: **0** (era 1); por segundo, com a legenda ao vivo: **0** (eram ~62).
- fios do overlay: **2** em uso (o do `_thread_main` que ja' existia + o do relogio), nenhum deles por frame.
- o trabalho continua: `A1` mede 63 frames/s no oraculo e a cadeia `_update -> _arm_tick` e' a real.

## O que NAO esta' provado

- A instancia viva do dono (pid 45084, arrancada as 00:48:51) corre o codigo VELHO: a cura vale no
  proximo arranque. Nenhuma lane mata nem relanca a app dele (`SOTTO_NEVER_ON_OWNER_SCREEN`); o
  autostart/duplo-clique e' a via.
- `creation=90.879/s` e' a MEDICAO DO WATCHER numa janela de stutter; o instrumento desta arvore conta
  construcoes de `threading.Timer` no caminho real, nao etw de criacao de fio do processo inteiro. As
  duas concordam na ordem de grandeza (62/s de frames de 16 ms), nao no numero exacto.
- O `interrupt=20.755 %` nao e' atribuido a esta linha: interrupcoes sao tempo de kernel de hardware e
  o watcher nao as atribui por processo. Fica declarado, nao explicado.
