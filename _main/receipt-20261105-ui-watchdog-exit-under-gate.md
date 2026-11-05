# A app saiu sozinha as 01:33: o gate de cada commit prendia o fio de UI

**Estado:** CONTAINED (a causa foi removida e o braco medido). `verified` nao:
a prova final e' a proxima sessao dele viva com o gate a correr por cima.

## Observado (verbatim do log, `_main/webview-run.log`)

```
01:25:44.773  UI_WATCHDOG_STRIKE strike=1 hwnd=11741758 err=1460
01:28:40.304  UI_WATCHDOG_STRIKE strike=2 hwnd=11741758 err=1460
01:28:51.400  UI_WATCHDOG_STRIKE strike=3 hwnd=11741758 err=1460
01:33:19.509  EXIT_BEGIN code=9 reason=ui-watchdog pid=28844 children=[]
01:33:19.509  UI_WATCHDOG_EXIT code=9 -- a UI estava presa; a sair para nao deixar janelas congeladas no ecra
01:33:26.645  EXIT_ESCALATED_SELF code=9 reason=primary-exit-did-not-return
```

No mesmo minuto o motor estava SAUDAVEL: `BRIDGE_STATS_PUSH count=190
in_window_s=45.2 payload={"peak":0.997009,"blocks":9242.0...}` e
`BRIDGE_ALIVE WORKER_ALIVE seq=9236 phase=window`. Nao foi o modelo: foi o fio de
UI.

`err=1460` e' `ERROR_TIMEOUT` devolvido por `SendMessageTimeout` ao proprio hwnd
da shell -- a assinatura de um fio de UI preso, nao de uma janela fechada.

## A causa medida

`nvenc.test.mjs` corre no gate de CADA commit (`scripts/pre-commit` ->
`run-all.mjs`) e a sua arm do GOP fazia `captureAndEncode(..., seconds: 12..30)`,
que em `nvenc.js` e' `ffmpeg -f gdigrab -framerate 60 -i desktop`. `gdigrab` a
60 fps **prende o compositor do Windows** enquanto corre. Nesta sessao eu corri
tres instancias em paralelo, duas vezes, e numa delas a app do dono foi apanhada
no meio: tres strikes e saiu.

Nenhum instrumento deste repo deve prender a app do dono para produzir um numero
sobre o NVENC.

## A cura e a prova

`nvenc.js:captureAndEncode` aceita `source: "testsrc2"` (lavfi) e usa
`-f lavfi -i testsrc2=size=1280x720:rate=<fps>` em vez de `gdigrab`. Mesmo NVENC,
mesmo `-g 250`, **zero pixels do ecra de ninguem**. O caminho do produto
(`gdigrab desktop`) continua medido pela captura curta de 2 s, no arm que existe
para isso.

Medido:

| | antes | depois |
|---|---|---|
| duracao total da suite | 15-40 s | 4,4 s |
| gaps lidos no ficheiro | 347, 359, 916, 932, 920 (GPUs a competir) | 250 exacto |
| 3 instancias concorrentes | 0/3 verdes (um keyframe cada) | 3/3 verdes |

## O que NAO se conclui daqui

- O `UI_WATCHDOG_EXIT` em si nao foi julgado: a app preferir sair a deixar uma
  janela congelada, e isso e' decisao de desenho. O que se mediu foi a causa do
  congelamento, e ela era minha.
- A caixa estava tambem com `I:` a 100 % (35 GB de 3,7 T livres) e 72 processos
  de browser; libertar 6,6 GB de scratch meu nao entra nesta conta como cura.
