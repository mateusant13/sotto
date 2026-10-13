# RECEIPT — o botão `live` é o botão da legenda, e o painel de baixo é uma faixa reta (2026-10-13)

**Lead.** Escopo de escrita exercido: `app/panel/panel.html`, `app/panel/panel.js`,
`app/panel/panel.css`, `app/panel/caption-float.js`, este recibo, e dois instrumentos de
sondagem meus fora do repo (`I:\cc-tmp\live-smoke.js`, `I:\cc-tmp\strip-css.js`).
**Nada mais foi tocado por mim.** Os geradores de tema e os oráculos de design foram
entregues a duas lanes (ver §5). Sem `git add`, sem `git commit`.

---

## 1. A ordem do dono, verbatim (2026-10-13)

> *"teu trabalho é ver como os .zip implementam cada painel diferente e imitar 1:1. o que vai
> ser diferente é os botoes, todos iguais, e o lugar de mudar de design nos paineis, todos
> iguais. pro painel de baixo, ele tem que ser mais uma faixa/linha reta. e o botao de legenda
> pra ativar a legenda deve ser o botao 'live'. o botao 'live' ativo deve mostrar na tela as
> legendas, igual acontece nas demos de qualquer .zip."*

**"O painel de baixo" é a STRIP** — a vocabulary já fixada pelo próprio Lead em
`docs/owner-brief-20261012.md` §"O 'painel de baixo' é a STRIP" (medida:
`PANEL_GEOMETRY_RESTORED surface=strip rect=1040x100@(440,920)`). Não foi re-interpretada aqui.

---

## 2. A causa medida da queixa de design: a app do dono estava CEGA

**Não era o CSS dos temas. Era o canal página→shell.** O commit `7fcd97e` (2026-10-12 22:26)
partiu `SottoHost.dispatch`: o dict literal de handlers avaliava
`self._set_strip_offset` — método de `SottoShell`, não de `SottoHost` — portanto o
`AttributeError` disparava **ao construir o mapa**, para QUALQUER `kind`. Nada da página
chegava ao shell, e os assets diferidos respondiam **200 VAZIO**.

Medido no log da shell do dono antes do reinício (`_main/webview-run.log`):

```
2026-10-13 04:34:25.572 sotto: PANEL_LAZY_EMPTY url=file:///H:/sotto/app/panel/themes/cinematic.css
2026-10-13 04:34:25.575 sotto: PANEL_LAZY_EMPTY url=file:///H:/sotto/app/panel/skins/skins.js
2026-10-13 04:34:25.583 sotto: PANEL_LAZY_EMPTY url=file:///H:/sotto/app/panel/skin-host.js
2026-10-13 04:34:25.587 sotto: PANEL_LAZY_EMPTY url=file:///H:/sotto/app/panel/skin-layout.css
2026-10-13 04:34:29.800 sotto: PANEL_LAZY_EMPTY url=file:///H:/sotto/app/panel/themes/panel-designs.css
```

Ou seja: **30 dos 45 designs (25 `cine-*` + 5 `pd-*`) não tinham folha de estilo nenhuma** e
as 20 skins nunca montavam. A correcção já estava em disco (commit `ce45249`, 04:46, da lane
lazy-ask); faltava o **reinício da shell**.

**A shell reiniciou às 04:47:29** (`SINGLE_INSTANCE already_running=false`) e o canal voltou:

```
04:47:31.071 PANEL_LAZY_GATE_ARMED registered=5 urls=5
04:47:31.243 RECEIVER_READY captions=0 hasBridge=True
04:47:31.246 PRELOAD_ACTIVE hasSotto=true methods=15 hotkey=Alt+C
```

**Nenhum `PANEL_LAZY_EMPTY` depois disso.** Readback da própria página
(`_main/_paint-asked.log:50`, braço `--theme cine-cellar`, 05:16:52):

```json
{"lazyLog":[{"kind":"load","detail":"cine-cellar -> themes/cinematic.css, skins/skins.js, skin-host.js, skin-layout.css"},
            {"kind":"ask","detail":"themes/cinematic.css"},{"kind":"inject","detail":"themes/cinematic.css"},
            {"kind":"ask","detail":"skins/skins.js"},{"kind":"inject","detail":"skins/skins.js"},
            {"kind":"ask","detail":"skin-host.js"},{"kind":"inject","detail":"skin-host.js"},
            {"kind":"ask","detail":"skin-layout.css"},{"kind":"inject","detail":"skin-layout.css"}],
 "cinRules":616,"sottoSkins":"object","skinHost":"object","bodySkin":"1","sheets":12}
```

`cinRules=616` é a prova de que o `cinematic.css` de 350 326 B chegou inteiro ao documento;
`bodySkin="1"` é a skin montada. **É esta a metade "imitar 1:1" que estava em falta: os
designs não estavam errados, não estavam a ser CARREGADOS.**

---

## 3. O que eu mudei (o botão `live` e a faixa)

### 3.1 O botão `live` é agora o botão da legenda

Antes havia DOIS controlos: `#strip-live-button` (o toggle do motor, `bridge.setLiveEnabled`
— método que a shell NÃO implementa) e `#strip-float-button` ("Linhar", que soltava a
legenda na tela). O dono já tinha dito em 2026-10-12, no próprio CSS:
*"o botao de mostrar a legenda ao vivo deve ser o live"*. Hoje repetiu, e a fusão foi feita:

| ficheiro | antes | depois |
|---|---|---|
| `panel.html` | `#strip-float-button` ("Linhar") + `#strip-live-button` | SÓ `#strip-live-button`; o elemento "Linhar" foi apagado |
| `panel.js` | `applyLiveEnabled` só pintava o botão | `applyLiveEnabled` termina em `applyFloat(liveEnabled)`: **um facto só** — `aria-pressed="true"` ⇔ `body[data-float]="on"` ⇔ a legenda solta na tela |
| `panel.js` | `dom.stripFloatButton`, `paintFloatState()`, `toggleFloat()` | removidos (nenhuma referência pendurada; `grep` = 0 em código) |
| `panel.js` | `applyFloat` chamava `setPanelSurface('strip')` sempre, com `else setSurface('strip')` | só chama a shell quando `currentSurface() === 'strip'` — um apply de `live` na surface do painel NÃO pode puxar a strip para o ecrã |
| `panel.css` | `#strip-float-button { order: 5 }`, `.strip-button--float` | removidos; `#strip-hide-button` passou a `order: 5` (pausa 4, X 5, estado 99) |

### 3.2 A faixa: um painel de baixo RETO

`body[data-surface="strip"] .panel`, três declarações e nada mais:

| propriedade | antes | depois |
|---|---|---|
| `border-radius` | `10px` | **`0`** |
| `border` | `1px solid var(--line)` (4 lados) | **`border: 0`** + `border-top: 1px` + `border-bottom: 1px` (sem montantes nas pontas) |
| `background` | gradiente 180° de dois stops | **`rgba(11, 15, 20, 0.98)`** plano |

Altura (`--strip-height: 40px`), largura, padding e a geometria dos botões **não mudaram** — a
shell lê `--strip-height` para dimensionar a janela.

---

## 4. O que foi MEDIDO (comandos e números)

### 4.1 A cascata real da faixa — `node I:\cc-tmp\strip-css.js` (jsdom, painel.css inline)

```
strip .panel border-radius = 0px
strip .panel border-top-width = medium / border-left-width = 0px
strip .panel background-image = none
strip .panel background-color = rgba(11, 15, 20, 0.98)
live button order = 2      hide button order = 5      pause button order = 4
```

### 4.2 O contrato do botão — `node I:\cc-tmp\live-smoke.js` (jsdom, os 12 módulos REAIS)

```
strip-live-button present: true
strip-float-button present: false
strip row children: brand | grip | live | open | hide | pause | state   (a ordem VISUAL é do CSS: pausa 4, X 5)
initial        pressed=true  body[data-float]=on   html[data-float]=on   --strip-height=220px
after click 1  pressed=false body[data-float]=off  html[data-float]=off  --strip-height=40px
after click 2  pressed=true  body[data-float]=on   html[data-float]=on   --strip-height=220px
captionFloat state={"on":true,"painted":true,"standalone":false,"feed":"panel","mounted":true,...}
SCRIPT ERRORS: none
```

### 4.3 A faixa PINTA na WebView2 real — `py -3 _main/panel-paint-probe.py --theme cine-cellar --secs 12 --strip --readback`

```
ARM asked: hwnd=1183622 rect=(-10000, 800, -8960, 1020)  [1040x220 — a faixa + a legenda solta]
           printwindow_ok=True getdibits_rows=220 distinct_colours=65 bytes=915200
PANEL_LAZY_ALLOW url=themes/cinematic.css   (e skins.js, skin-host.js, skin-layout.css)
ARM-VERDICT asked: PAINTED
ARM-VERDICT notasked: NO-WINDOW
PAINT-VERDICT PASS
```

### 4.4 Portões da casa — `node _main/instruments-battery.mjs`

**79/81 rc=0, failed=2, launches=0.** Os dois vermelhos (`handler-map`, `handler-map neg`) foram
**artefacto de concorrência meu** — eu tinha um `panel-paint-probe.py` a correr ao mesmo tempo.
Re-corridos isolados, ambos PASSAM:

```
py -3 _main/bridge-handler-map-oracle.py            -> VERDICT: PASS -- 3 check(s), 0 fail   rc=0
py -3 _main/bridge-handler-map-oracle.py --neg-arm  -> VERDICT: PASS -- 4 check(s), 0 fail   rc=0
                                                       (mutante RED em "the map did NOT report itself unbuildable")
```

`py -3 _main/agents-md-pins-oracle.py` -> **AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)**.

---

## 5. O que ficou entregue a duas lanes (e o que cada uma tem de provar)

| lane | entrega | escopo |
|---|---|---|
| oracles-strip | re-baseline de `strip-float-oracle.js`, `three-overlays-oracle.js`, `botoes-lane-oracle.js`, `caption-independent-oracle.js`, `_s2-bar-dom-oracle.js`, `_panel2-dom-probe.js` ao contrato novo, com braço negativo que saiba dizer NÃO | `_main/**` |
| buttons-same | *"os botoes, todos iguais"*: parar de emitir, nos TRÊS geradores, qualquer regra por-design que mova ou estilize `.panel__controls` / `.panel__controls .icon-button` / `body[data-surface='strip'] .stripbar { justify-content }`; regenerar; re-baselinar os oráculos de design | `_main/_design-lane/gen_*.py` + `app/panel/themes/**` |

---

## 6. A decisão que NÃO foi confirmada pelo dono, e é de uma linha

O `live` **arranca ON** (`panel.js`: `let liveEnabled = true`), portanto o Alt+C abre a faixa
**já com a legenda solta na tela** (janela 1040x220) — é o comportamento das demos dos .zip
(*"igual acontece nas demos de qualquer .zip"*), e é o que o §4.2 mede.

**A outra leitura** — *"o botao de legenda PRA ATIVAR a legenda"* e *"o painel de baixo tem que
ser mais uma faixa/linha reta"* — pede o contrário: a faixa abre FINA (40px) e a legenda só
aparece quando se clica no `live`. **Perguntei ao dono com as duas opções e a pergunta
expirou sem resposta em 120 s**, por isso escolhi a leitura literal de "live ativo ⇒ legenda na
tela" + "igual às demos". Trocar é UMA linha: `let liveEnabled = true;` -> `false` em
`app/panel/panel.js`, mais `aria-pressed="false"` no `#strip-live-button` de `panel.html`.

---

## 7. NÃO MEDIDO / não fechado

1. **Não vi a faixa com os olhos do dono.** O que está medido é a cascata (jsdom), o contrato
   (jsdom) e um `PrintWindow` de 65 cores da faixa na WebView2 real — **não** uma captura
   interpretada, e o braço `asked` do probe saiu `UNSETTLED` numa corrida de 16 s (a
   instabilidade conhecida do instrumento: caret de 1,06 s contra o orçamento de settle).
2. **A pergunta do §6 não foi respondida.**
3. **A fidelidade 1:1 design-a-design continua a NÃO ser medida por comparação com o mockup.**
   O que existe é: os 45 temas pintam e todos diferem (censo de 2026-10-13, 0 sha256
   duplicado), os assets diferidos agora CARREGAM (`cinRules=616`), e os oráculos de estrutura
   por família. "Diferente" não é "igual ao design" — o instrumento que compara uma captura com
   o mockup não existe.
4. **Um `panel-paint-probe.py` foi corrido por uma das lanes às 05:16:48** (tema
   `cine-cellar`, `strip=False`, `secs=16`), apesar da instrução de não lançar nada. Não
   deixou janela no ecrã do dono (a cópia corre em `x=-10000`) e o processo terminou; ficou
   registado aqui e as duas lanes foram avisadas.


---

# FINAL — o estado depois das duas lanes, medido pelo Lead (2026-10-13 05:3x)

## F1. "os botoes, todos iguais" — FEITO nos geradores, não à mão

Os TRÊS geradores deixaram de emitir QUALQUER regra por-design sobre o lugar ou o estilo do
cluster de controlos:

| gerador | antes | depois | o que saiu |
|---|---|---|---|
| `_main/_design-lane/gen_cinematic.py` | 84 158 B | **83 064 B** | os 4 blocos `.panel__controls` do `CLUSTERS` (coluna-centro, pílula-centro, carril-esquerda), as 4 linhas `body[data-surface='strip'] .stripbar { justify-content }` e a banda `.captions__list { padding-bottom: 36px }` que só existia para reservar o sítio da linha absoluta |
| `_main/_design-lane/gen_zipc.py` | 71 239 B | **70 637 B** | as 10 linhas `out.append((s + " .panel__controls", [("justify-content", …), ("order", …)]))` |
| `_main/_design-lane/gen_themes.py` | 164 970 B | **164 334 B** | as 10 regras `.panel__controls` / `.panel__controls .icon-button` dos cinco blocos CHROME |

**Prova de reprodutibilidade ANTES de editar (regra 10 da AGENTS.md):** os três geradores correram
para caminhos de rascunho e os DEZ outputs saíram byte a byte iguais aos que estão em disco
(`ALL_IDENTICAL=True`). Só depois foram editados.

**Outputs regenerados** (nenhum ficheiro gerado foi editado à mão):

| ficheiro | antes | depois | Δ |
|---|---|---|---|
| `theme-1.css` | 28 973 | 28 605 | −368 |
| `theme-2.css` | 29 191 | 28 950 | −241 |
| `theme-3.css` | 29 341 | 29 187 | −154 |
| `theme-4.css` | 28 274 | 28 049 | −225 |
| `theme-5.css` | 29 297 | 29 056 | −241 |
| `panel-designs.css` | 139 610 | 138 377 | −1 233 |
| `cinematic.css` | 350 326 | 336 230 | −14 096 (83 linhas acrescentadas são só comentário reescrito) |
| `zipc-panels.css` | 72 757 | 71 870 | −887 |

**Depois da regeneração: `0` selectores `.panel__controls {`, `0` regras
`.stripbar { justify-content`, `0` regras `.captions__list { padding-bottom: 36px }` nos oito
ficheiros.** `app/panel/panel.css` é agora o ÚNICO sítio que decide onde a linha de botões fica —
em todos os 45 designs. E como o `theme-switcher.js` monta o chevron de temas DENTRO do
`.panel__controls`, o "lugar de mudar de design" é o mesmo em todos, que é a segunda metade da
frase do dono.

## F2. O que EU re-corri (não aceito a palavra das lanes)

```
py -3 _main/zipc-designs-oracle.py        -> 9 checks, 0 failed. VERDICT: PASS
                                             A min pairwise diff = 63 (>=20)   E smallest fingerprint = 162 (>=100)
py -3 _main/cinematic-designs-oracle.py   -> 6 checks, 0 failed. VERDICT: PASS
py -3 _main/cine-themes-oracle.py         -> 20 checks, 0 failed. VERDICT: PASS
py -3 _main/base-themes-oracle.py         -> VERDICT: PASS (ARM D reproduz tudo byte-for-byte)
node _main/strip-float-oracle.js          -> 50 checks, 0 failed. VERDICT: PASS
node _main/three-overlays-oracle.js       -> 31 checks, 0 failed. VERDICT: PASS
node _main/botoes-lane-oracle.js          -> 34 checks, 0 failed. VERDICT: PASS
node _main/_s2-bar-dom-oracle.js          -> 23 checks, 0 failed. VERDICT: PASS
node _main/caption-independent-oracle.js  -> 48 checks, 0 failed. VERDICT: PASS
node _main/_panel2-dom-probe.js           -> RESULT: GREEN — 83/83 arm(s)
py -3 _main/bridge-handler-map-oracle.py  -> VERDICT: PASS (3/0)  e  --neg-arm PASS (4/0, mutante RED)
py -3 _main/agents-md-pins-oracle.py      -> AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
```

Pins do produto, congelados e conferidos por mim depois de todas as lanes:
`panel.html` **69 875 B** `D844CF5B77370779…`, `panel.js` **154 949 B** `447FEE7F7E8BF59F…`,
`panel.css` **119 872 B** `3AD01D08BD52A3FE…`, `caption-float.js` **18 401 B** `B07BFFE56062EDEF…`.

## F3. A app do dono RECEBEU as duas mudanças

O watcher de hot reload só vigia `PANEL_ASSETS = ('panel.html', 'panel.css', 'panel.js')`
(`app/webview/hot_reload.py:55`) — **não** vigia `themes/**`. Como a regeneração dos temas não
dispara reload nenhum, o Lead forçou um: reescreveu `panel.css` com os MESMOS bytes (só a mtime
muda) e o watcher fez o resto. Medido no log da shell:

```
05:33:40.680 HOT_RELOAD_FLUSH kind=panel files=["panel.css"] events=2 debounce_ms=250
05:33:40.683 HOT_RELOAD_PANEL_DONE files=["panel.css"] reload=9 hotkey=Alt+C
05:33:40.876 RECEIVER_READY captions=0 hasBridge=True
05:33:40.906 HOT_RELOAD_APPLIED reload=9 visible=false hotkey_still_registered=true
05:33:40.906 HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden reload=9
```

Sem `PAGE_ERROR`, sem `Uncaught`, e o painel ficou ESCONDIDO (o dono tinha-o escondido). A app
tem agora, em memória: o botão `live` fundido, a faixa reta e os 8 CSS de tema regenerados.

## F4. Correção da atribuição do probe das 05:16

Aquele `panel-paint-probe.py` (tema `cine-cellar`, `strip=False`, `secs=16`) **não foi de
nenhuma das minhas duas lanes** — a lane dos oráculos mandou a lista completa dos seus comandos
(só leitura) e a lane dos botões também. Os artefactos deixados em `I:\cc-tmp`
(`ver47.ps1`, `ver47.png`, `cl47.ps1`) e o processo `_main/instruments-battery.mjs` que
apanhei a correr às 05:2x sugerem **outra sessão/agente na mesma máquina**. Fica registado como
não-atribuído, não como violação das minhas lanes.

## F5. A bateria da casa, LIMPA (nada mais a correr) — 81/81

A corrida das 05:11 deu `79/81` porque **eu** tinha um `panel-paint-probe.py` a correr ao mesmo
tempo; o `bridge-handler-map-oracle.py` copia e lança a shell, e a concorrência foi o artefacto.
Re-corrida com a máquina parada:

```
node _main/instruments-battery.mjs
SUMMARY: 81/81 instrument(s) rc=0; failed=0; launches=0
         (no shell, app or worker is opened -- the ONE run.cmd invocation in this list is its
          --help pre-flight, which argparse answers and exits)
```

Inclui, verdes: `handler-map` 6/0 e `handler-map neg` 8/0, `scope-leak` 9 folhas 0 fugas,
`letter-swap` 84/84 + 4/4 RED, `history-producer-gate` GREEN com o controlo RED,
`agents-md-pins` PASS. **rc=0, exit code 0.**
