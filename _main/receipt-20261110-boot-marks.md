# RECIBO - o bloco do arranque que tinha numero e nao tinha nome (2026-11-10)

## 1. A ordem

Dono, 2026-11-09 18:06Z: *"o sotto performa mal em carga alta"*. A pergunta que uma lane pode
responder sem a mao dele: **onde** o arranque da pagina gasta o tempo.

## 2. Medido no log vivo dele (`_main/webview-run.log`, 32 `PANEL_BOOT_PROFILE`)

| sessao | early | dom | load | firstPaint | longtasks | slowest |
|---|---|---|---|---|---|---|
| 2026-11-09 21:22 | 51 ms | 168 ms | 170 ms | **356 ms** | `[]` | `[]` |
| 2026-11-10 09:34 | 29 ms | **472 ms** | 483 ms | **1040 ms** | `[]` | `[]` |

Duas coisas ficam ditas por estes numeros, e uma delas e' sobre o INSTRUMENTO:

1. O primeiro quadro da pagina passou de 356 ms a **1040 ms** entre as duas sessoes -- 2,9x.
2. **`longtasks` e `slowest` estao vazios nas 32 linhas.** Vazio nos dois campos ao mesmo tempo nao
   e' "nada foi lento": e' um contexto onde `PerformanceObserver('longtask')` e a Resource Timing
   nao entregam nada. O `marks` foi de 29 ms a 472 ms e nenhum campo diz ONDE.

Uma hipotese caiu por medicao antes de virar trabalho: `app/panel/skins/skins.js` tem **812 978 B**,
o maior payload da pagina -- e o custo dele e' `read 2,9 ms + exec 7,6 ms`, e ele ja' e' PEDIDO e nao
eager (`lazy-assets.js`). Nao e' o culpado.

## 3. A cura

* `BOOT_PROFILE_JS` expoe `window.__sottoBootMark` (a mesma lista de `marks` que ja' publicava) e o
  payload ganhou `longtask_supported` e `resources` -- os dois campos que estavam vazios em 32/32
  passam a dizer SE estao disponiveis, em vez de se lerem como "nada lento".
* A pagina marca as suas etapas: `panel-js` (primeira linha do `panel.js`), `theme:<nome>` (depois de
  `paintAll`, o passo mais caro do documento), `wired` (fiacao completa), `paint1`/`paint2` (primeiro
  quadro) e `no-bridge` (o outro desfecho: sem ponte a pagina nao liga nada).
* Sem medidor, `bootMark` e' um no-op (`typeof`), entao um harness nao ganha um erro por um marco.

## 4. A prova

`node _main/_cache/boot-marks-smoke.mjs` (descartavel, jsdom, sem janela):

```
shell expoe __sottoBootMark = true | payload le marks = true
marcos vistos = ["panel-js","no-bridge"]
sem medidor: erro=nenhum
SMOKE GREEN
```

`python _main/undefined-names-oracle.py` -> `GREEN -- 19 ficheiros de producao, 0 nomes usados e
nunca definidos`.

## 5. O QUE NAO ESTA' MEDIDO

* **Qual** etapa e' o bloco de 443 ms: isso exige um arranque novo, e a proxima linha
  `PANEL_BOOT_PROFILE` da sessao dele passa a responde-lo entre dois marcos.
* Porque o `firstPaint` variou 2,9x entre duas sessoes: a pagina e' a mesma e o que mudou foi a carga
  da maquina -- ou seja, o numero da sessao de 09:34 nao separa "pagina mais lenta" de "maquina
  ocupada". Medir isso pede a mesma pagina sob dois niveis de carga declarados.
