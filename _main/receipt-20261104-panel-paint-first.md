# Receipt — 2026-11-04 — panel-paint-first (a ordem do show)

Lane: `PanelPaintFirst-2` · worktree `H:/sotto-wt/PanelPaintFirst-2` · branch `lane/panel-paint-first-2`
(base `8007032`, commit da lane `paint: the map waits for the content -- a pre-map content gate and the
order it publishes`).

## A ordem, verbatim

> *"o painel dar show, nao deve carregar o background e mostrar, e depois carregar a ui"*

## O que o show fazia (a ordem, lida no fonte)

Os tres caminhos que mapeiam o painel — `show_panel` (startup/tray/`--show`/`toggle_panel`),
`show_strip` e `show_side` (o ciclo do Alt+C) — tinham todos esta sequencia:

```
set_panel_surface(present=True)   # POSTA o `SottoSurfaces.set` e APLICA a geometria JA'
  ... geometry (SetWindowPos, janela escondida) ...
arm_paint_ack()                   # POSTA o script do ack
show_without_activating()/foreground_unlock()   # <- O MAPA: user32, nao pergunta nada a' pagina
transparency_hack()
wait_paint_ack()                  # espera DEPOIS do mapa -- mede, nao ordena
```

Tres perigos de ordem, medidos por leitura:

1. **A superficie e' POSTADA, o mapa nao espera.** `set_panel_surface(present=True)`
   (`sotto_webview.py:14990`) usa `exec_js_post`, logo o `SottoSurfaces.set` que escreve
   `body[data-surface]` — a regra que escolhe o layout inteiro (`panel.css:1596` esconde o
   `.panel__header` na faixa) — pode correr DEPOIS do `ShowWindow`. O primeiro frame passa a ser a
   superficie anterior.
2. **O ack de pintura nao ordena nada.** `arm_paint_ack` e' postado e `wait_paint_ack` corre depois do
   mapa: a cura de 2026-11-01 mediu o show, nao o ordenou. Ele tambem nao podia: o ack usa dois
   `requestAnimationFrame`, e o compositor desta maquina nao corre rAF de janela escondida.
3. **A leitura do offset da barra no caminho do show tinha o orcamento por omissao do `exec_js`
   (10 s).** `_strip_offset` → `_strip_offset_from_page` corre dentro de `set_panel_surface`, ou seja
   ANTES do mapa: com a cache vazia (processo novo) e o UI thread preso, a primeira faixa custava
   ate 10 s antes de mapear — o *"abrir o sotto trava"* que a casa ja' mediu.

Nao mudou, de proposito: `transparency_hack` continua DEPOIS do mapa. E' a unica chamada que faz um
WebView2 transparente compor (`platforms/edgechromium.py:348`) e ela propria e' um `form.Show()`; move-la
para antes do mapa mapearia a janela antes de qualquer gate. O custo da PRIMEIRA apresentacao ja' e'
pago fora do ecra por `_warm_paint`.

## A mudanca

`app/webview/sotto_webview.py`

* `CONTENT_GATE_TIMEOUT_MS = 250.0` + `CONTENT_GATE_JS` (:428-487) — o gate de conteudo: aplica a
  superficie (idempotente, `surface.js:69`), FORCA recalc de estilo e layout com
  `getBoundingClientRect()`, e devolve a impressao digital do estilo JA' aplicado (o `display`
  computado do `.panel__header`, o rect do body, o fundo). Layout nao precisa de compositor: **e' por
  isso que o ack e' respondivel com a janela escondida**, ao contrario do rAF de `PAINT_ACK_ARM_JS`.
* `content_gate()` (:10970) — pergunta, com orcamento, e **falha aberta**: `NoAnswer`/timeout ⇒ o mapa
  acontece e a linha diz `ack=false why=ui-thread-busy|not-applied`. Um Alt+C que nao faz nada e' o
  defeito que a casa ja' proibiu.
* `show_panel` (:11977), `show_strip` (:12294), `show_side` (:12360) — `content = self.content_gate(...)`
  imediatamente ANTES do mapa, e o `PANEL_SHOWN` de cada um passa a publicar
  `content_ack=<bool> content_wait_ms=<ms>`. A testemunha da ordem fica escrita nas duas pontas:
  `PANEL_CONTENT ... order=before-map` e o show que ele informou.
* `SHOW_PAGE_READ_TIMEOUT_S = 0.25` + `_strip_offset_from_page`/`_strip_offset` (:15070-15150) — a
  leitura do offset passa a ser limitada a 250 ms, diz `STRIP_OFFSET_READ_NO_ANSWER` e **nao entra na
  cache** quando nao responde (gravar a ausencia perdia o offset do dono para o resto do processo).

`_main/paint-live-show-oracle.py`

* Julga a ORDEM: cada `PANEL_SHOWN` da sessao viva tem de ter, ANTES dele, um `PANEL_CONTENT` com
  `ack=true`, mais `content_ack=true` e `content_wait_ms<=350`; mantem `paint_ack=true`,
  `wait_ms<=400` e o `PAINT_WARM ack=true` (inclusive a regra de 2026-11-04: sem show, o warm nao se
  exige).
* `judge_source()`: le a ordem no FONTE — `content_gate(` tem de aparecer antes do mapa em
  `show_panel`/`show_strip`/`show_side`. E' o que apanha o mutante mesmo quando o log e' de uma
  instancia antiga.

## Numeros

ANTES (log do dono, read-only `H:/sotto/_main/webview-run.log`):

```
$ grep -c 'PANEL_CONTENT' _main/webview-run.log
0
$ grep -c 'PANEL_SHOWN'   _main/webview-run.log
514
$ python _main/paint-live-show-oracle.py
PAINT-LIVE arranque=2026-11-04 10:06:36.407 warm=1 ack=1 conteudo=0 conteudo_ack=0 shows=0 max_wait_ms=None max_content_wait_ms=None
PAINT-LIVE show (verbatim, FORA da sessao viva): 2026-11-03 13:02:04.247 sotto: PANEL_SHOWN reason=hotkey-cycle-strip mode=strip hwnd=22092754 visible=true show=SW_SHOWNOACTIVATE focus=no-pointer-lock paint_ack=true wait_ms=344.0
PAINT-LIVE show (verbatim, FORA da sessao viva): 2026-11-03 13:02:08.126 sotto: PANEL_SHOWN reason=hotkey-cycle-side mode=side hwnd=22092754 visible=true show=SW_SHOWNOACTIVATE focus=no-pointer-lock paint_ack=true wait_ms=16.0
PAINT-LIVE show (verbatim, FORA da sessao viva): 2026-11-04 09:57:56.000 sotto: PANEL_SHOWN reason=hotkey-cycle-strip mode=strip hwnd=260382146 visible=true show=SW_SHOWNOACTIVATE focus=no-pointer-lock paint_ack=true wait_ms=234.0
PAINT-LIVE VERDICT: SKIPPED (nenhum Alt+C nesta sessao ainda (2026-11-04 10:06:36.407) -- nada a julgar)
```

Nenhuma das 514 linhas de show tem testemunha de conteudo — a pergunta nao existia.

DEPOIS (o que e' medivel sem pousar a app no ecra dele):

```
$ python _main/paint-live-show-oracle.py --log H:/sotto/_main/webview-run.log --source app/webview/sotto_webview.py
... PAINT-LIVE VERDICT: SKIPPED (nenhum Alt+C nesta sessao ainda ...)   rc=0
```

A sessao viva comecou as 10:06:36.407, antes deste codigo: o `content_ack` so' aparece depois de o
dono reiniciar. O SKIPPED e' honesto (um passo saltado nao e' um portao que passou) e as linhas
antigas ficam impressas como evidencia do que havia.

A metade do JS, com um DOM falso em `node` (`I:/cc-tmp/gate2.js`, throwaway, fora do repo):

```
A (css aplicado) ack=true vis=hidden head="none" -> POSITIVO-OK
B (css ausente)  ack=false style=false -> RED-as-required
```

`vis=hidden` e' o ponto: o gate responde com a janela escondida (layout nao precisa de compositor), e
com a folha da superficie nao aplicada ele diz `style=false` — o mapa fica informado de que a janela
ia' aparecer com o layout errado.

## Braco negativo (o portao da casa: rc=1 quando apanha)

```
$ python _main/paint-live-show-oracle.py --neg-arm --log H:/sotto/_main/webview-run.log --source app/webview/sotto_webview.py
  show-sem-ack                 -> RED      RED-as-required  show ...: paint_ack=false
  mapa-antes-do-conteudo       -> RED      RED-as-required  show ...: nenhum PANEL_CONTENT ack=true ANTES do show (a janela foi ma...
  show-sem-ack-conteudo        -> RED      RED-as-required  show ...: content_ack=false (o mapa nao esperou o conteudo)
  conteudo-nao-aplicado        -> RED      RED-as-required  conteudo nao aplicado antes do mapa (...): ack=false why=applied
  show-lento                   -> RED      RED-as-required  show ...: wait_ms=951.0 > 400
  sessao-sem-aquecimento       -> RED      RED-as-required  a sessao viva nao tem PAINT_WARM: o show cai no caminho frio
  fonte-mapa-antes-do-gate     -> RED      RED-as-required  show_panel: o mapa (`show_without_activating(self.hwnd)`) vem ANTES do gate
POSITIVE-CONTROL: o fonte REAL tem a ordem certa? sim
NEG-ARM cases=7 caught=7
NEG-ARM PASS
rc=1
```

`mapa-antes-do-conteudo` e `fonte-mapa-antes-do-gate` sao o mutante que o ticket pede: a janela
mostrada antes de o conteudo ser aplicado, um no log e outro no ficheiro que a app carrega.
Positivo de controlo (log limpo, sintetico): `POSITIVE CONTROL: GREEN []`.

## Portoes

```
$ python _main/lane-screen-gate.py
  braco 1 synthetic-input       : verde
  braco 2 lane-launcher-visible : verde
  braco 3 agents-rule           : verde
VERDICT: PASS
rc=0

$ python _main/console-window-audit.py
CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela
```

`_main/console-window-gate.py` **nao existe nesta arvore** — o proprio AGENTS.md o diz (a regra
2026-11-04 sobre pop-ups nomeia-o e logo corrige: "o `console-window-gate.py` que esta regra citava
nunca existiu nesta arvore"). O vizinho real e' `console-window-audit.py`, corrido acima.

No HEAD em que a lane nasceu (`82e16a5`) esse censo reprovava por divida ALHEIA
(`_main/line-closed-oracle.py:91  NO-FLAG  larga node sem guarda`, `VERDICT FAIL -- 1 sitio(s) que
abrem janela`). O commit `8007032` da frota apaga esse ficheiro; a lane foi rebased para cima dele e o
censo passou a `PASS`. Nenhum ficheiro de outra lane foi tocado: `git show --stat` desta lane lista
dois ficheiros.

## O que NAO ficou provado

* **`[INFERENCE]` o primeiro frame do dono tem conteudo.** Nenhuma lane pode pousar a app no ecra dele
  (`SOTTO_NEVER_ON_OWNER_SCREEN`), logo nao houve show ao vivo com este codigo. O que esta' provado e'
  a ORDEM (fonte + log) e a resposta do gate; o pixel e' de `_main/panel-paint-first-census.py`, numa
  instancia privada, e nao foi corrido aqui.
* **`[INFERENCE]` o gate responde sempre com a janela escondida.** A evidencia e' indirecta e fica
  escrita: o escritor de `panel-state.json` le `PANEL_STATE_PROBE` (que le
  `scrollHeight`/`clientHeight`, logo forca layout) a cada 2 s, e
  `_main/panel-state.SottoPovSelftest.json` tem valores reais com o painel escondido
  (`panel.live.scroll.client=749`, `panelDom.reason=""`). Se um dia nao responder, a linha diz
  `ack=false why=ui-thread-busy` e o show acontece na mesma — falha aberta, nunca um Alt+C morto.
* **O show continua a custar ate' +250 ms no pior caso** quando a pagina nao responde. Nao ha' medicao
  ao vivo deste numero; o orcamento e' o do `CONTENT_GATE_TIMEOUT_MS`, e o oraculo publica RED se ele
  passar dos 350 ms.

## Ficheiros

```
 _main/paint-live-show-oracle.py | 325 ++++++++++++++++++++++++++++++--------
 app/webview/sotto_webview.py    | 151 +++++++++++++++++++
 2 files changed, 416 insertions(+), 60 deletions(-)
```
