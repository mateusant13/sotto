# Recibo — lane `three-overlays` (2026-10-12)

**Lane:** three-overlays · **Repo:** `H:/sotto` · **Tip medido:** `908030f`
**Escopo de escrita:** `app/panel/panel.css`, `app/panel/panel.html`, `app/panel/panel.js`,
`app/panel/caption-float.js`, `_main/three-overlays-oracle.js` (novo), este recibo.
**Nada mais foi tocado.** `worker/**`, `app/webview/**`, `AGENTS.md` e instrumentos de outras
lanes ficaram intactos (medido: `git status --porcelain` mostra exactamente os 4 ficheiros de
`app/panel/` modificados e o oráculo novo como `??`). **Não houve commit nem push.**

---

## 1. O pedido do dono, verbatim (2026-10-12 16:33)

> *“e o alt c ta bugado. ta uma cor solida, uma div inteira. no meio dela, tinha o painel de
> baixo. cliquei num botao e ele sumiu e agora ta so a cor solida de volta, inteira. e pra
> existir 3 ‘overlays’. primeiro, o painel de baixo. nele eu ativo o segundo overlay, q e a
> legenda independente. ela mostra na minha tela, sem fundo, sem nada, extremamente clean, e
> apenas algo pra estilizar ela ou dar ‘corpo’. tipo uma barra a esquerda dela, onde ela se
> apoia, por exemplo. to so falando exemplo, tu vai ver como isso acontece nos .zip que tem ai
> no workspace e tu vai ver doq eu to falando. o terceiro painel, e o da direita. onde deve ter
> todos os botoes. o painel de baixo, deve conter apenas o bare minimum. e e so no painel da
> direita que aparece historico de qualquer coisa. faca tudo.”*

Ordem de trabalho: **o bug primeiro**, depois as três overlays, depois o portão.

---

## 2. O BUG — causa raiz medida, não inferida

### 2.1 A janela que o dono tem

`_main/panel-visibility.json`, lido 2026-10-12T17:55 -03:00, `pid=33248`:

```
geometry = { surface: "strip", x: 440, y: 920, width: 1040, height: 100,
             docked: "bottom-strip", workWidth: 1920, workHeight: 1032 }
```

E `_main/webview-run.log` (12 061 096 B, 118 499 linhas, lido nesta sessão), linha **114721**:

```
114720 STRIP_HEIGHT from=148 to=40 source=css css_value=40 extra=0 reason=surface-hotkey
114721 WINDOW_GEOMETRY reason=surface-strip ok=true work=1920x1032@(0,0) window=1040x100@(440,920)
114722 panel client area forced to 1040x100 (window 1040x100)
114723 PANEL_SURFACE surface=strip reason=hotkey document_surface="strip" window=1040x100@(440,920)
114724 WEBVIEW_CHILD shown=2 already=3 failed=0
114727 PANEL_SHOWN reason=hotkey mode=strip visible=true show=SW_SHOW+FOREGROUND
```

**Facto 1 — o CSS pede 40px e a janela tem 100px.** A linha 114720 diz que o documento declarou
`--strip-height: 40px`; a 114721 diz que a janela ficou **1040x100**. O rect guardado em
`panel-visibility.json` (`surface:"strip"`, 1040x100) ganha ao valor do CSS dentro de
`geometry_for` (`app/webview/sotto_webview.py:6447`), que devolve o rect guardado sempre que
`saved["surface"] == surface`. Contagem no log: `window=1040x100` **32x**,
`client area forced to 1040x100` **24x**. Isto é cross-lane (shell) e está reportado em §7.

**Facto 2 — o que a shell pinta quando o documento não pinta.** O formulário nasce com
`BackColor = #0B0F14` opaco (`sotto_webview.py:3926-3931`). É essa a cor que o dono vê.

### 2.2 As duas regras que produziam o sintoma

O bloco do strip em `panel.css` (lane S2, 2026-10-12) fazia exactamente duas coisas:

```css
body[data-surface="strip"] { background: transparent; }        /* o body deixa de pintar */
body[data-surface="strip"] .panel { width: max-content; ... }   /* a slab vira uma pílula */
```

Com a janela em 1040x100 e o formulário opaco por baixo, **uma pílula `max-content` centrada
num body transparente É o relato do dono**: “uma cor solida, uma div inteira. no meio dela,
tinha o painel de baixo”. A largura não veio do CSS — veio da shell. Um documento que quer um
strip estreito não o consegue por se recusar a pintar.

### 2.3 O botão que fez o painel sumir

Narrativa medida, linhas 114727-114748, na ordem em que aconteceu:

```
114727 PANEL_SHOWN reason=hotkey mode=strip visible=true
114729 POINTER_INTERACTIVE active=true  click_through=false   <- o rato entrou na slab
114730 POINTER_INTERACTIVE active=false click_through=true    <- saiu
114731 POINTER_INTERACTIVE active=true  click_through=false   <- entrou de novo
114732..114738 OUTSIDE_CLICK point=(809,958)..(889,953) decision=not-armed   <- 7 cliques
114739..114743 PANEL_LAZY_EMPTY_FAILED url=themes/cinematic.css / skins/skins.js /
               skin-host.js / skin-layout.css   (CreateWebResourceResponse em falta)
114741 WARN PAGE_ERROR text="unhandledrejection: SottoHost.dispatch() takes 2 positional
               arguments but 3 were given"
114744 OUTSIDE_CLICK point=(889,958)
114745 OUTSIDE_CLICK point=(1008,955)      <- DENTRO do rect 440..1480 x 920..1020
114746 TRANSPARENCY_ON click_through=true captions=kept      <- O BOTAO
114747 POINTER_INTERACTIVE active=false click_through=true noactivate=true
114748 PANEL_HIDDEN reason=hotkey visible=false
```

O clique em **(1008,955)** cai dentro do rect da janela (x 440..1480, y 920..1020) e é o clique
no `#strip-transparency-button`. Esse botão chamava `panel.js applyTransparency(true)`, que punha
`data-transparency="on"` no body, e havia **uma** regra à espera disso:

```css
body[data-surface="strip"][data-transparency="on"] .panel { display: none; }
```

O único nó que ainda pintava desaparecia. Sobrava 100% da cor opaca do formulário — *“agora ta
so a cor solida de volta, inteira”*. E a shell ainda tinha posto `WS_EX_TRANSPARENT`
(`TRANSPARENCY_ON click_through=true`), portanto o botão também já não podia ser clicado de volta.

Contagens no log inteiro: `TRANSPARENCY_ON` **2** (linhas 89542 e 114746),
`POINTER_INTERACTIVE active=false` **355**, `PANEL_SURFACE_REFUSED` **4**.

### 2.4 A correcção

1. `body[data-surface="strip"] { background: transparent }` **apagada**;
2. a pílula `width: max-content` **apagada** e substituída por uma slab que **ENCHE a janela**
   (`inset: 0` herdado da regra base `.panel`, uma linha de grelha, `padding: 4px 8px`,
   `border: 1px solid var(--line)`, `border-radius: 10px`, gradiente
   `rgba(17,24,35,0.97) -> rgba(11,15,20,0.98)`, `box-shadow: none`, `overflow: hidden`);
3. as **duas** regras de `[data-transparency="on"]` apagadas;
4. `#strip-transparency-button` apagado do markup **e** do `dom` de `panel.js`, com o binding
   de clique removido — `applyTransparency` ficou sem nenhum chamador de UI (verificado:
   `stripTransparencyButton.addEventListener` = **0** ocorrências).

O contrato que isto restaura é o do próprio ficheiro, `panel.html:101-106`: *“the slab fills the
window and is the only element that takes pointer events. There is NO transparent margin inside
this window”*.

### 2.5 Uma regra morta apagada pelo caminho

Havia **duas** regras com o mesmo selector `body[data-surface="strip"] .panel`, a segunda a
ganhar por ordem (mesma especificidade). A primeira declarava
`grid-template-rows: minmax(calc(var(--strip-height) - var(--strip-chrome)), 1fr) auto auto`,
`gap: 8px`, `padding: 10px 11px`, `border-radius: 12px` — **as quatro já estavam mortas quando
alguém as lesse**. Foi substituída por um comentário que diz onde está a regra viva
(“THE WINDOW IS THE BAR”), em vez de ficar a parecer viva. Consequência registada:
`--strip-chrome` (78px) fica **definido e sem consumo** — nada o lê hoje.

---

## 3. As três overlays

### 3.1 Overlay 1 — o painel de baixo (bare minimum)

O `stripbar` tem **exactamente 8 botões** mais o mostrador de estado. Medido sobre os bytes:

| # | id | rótulo |
|---|---|---|
| 1 | `strip-live-button` | (toggle de escuta) |
| 2 | `strip-theme-button` | (cicla o tema) |
| 3 | `strip-open-button` | Open panel |
| 4 | `strip-hide-button` | Hide |
| 5 | `strip-font-smaller-button` | Smaller |
| 6 | `strip-font-larger-button` | Larger |
| 7 | `strip-float-button` | Linhar |
| 8 | `strip-pause-button` | Pause |
| — | `strip-state` (+`strip-dot`,`strip-word`) | a palavra de estado |

**Removidos do strip:** `#strip-transparency-button` (o botão do bug) e `#strip-theme-chevron`.
O chevron é escondido **por CSS** e não só removido do markup, porque `theme-switcher.js`
`ensureChevron` (linhas 619-623) **recria o nó** se ele faltar:

```css
body[data-surface="strip"] #strip-theme-chevron { display: none; }
```

### 3.2 Overlay 2 — a legenda independente

Autoridade: os `.zip` do workspace (`I:/cc-tmp/zip1/src/`). O desenho **`inst`** verbatim:
`flex max-w-[720px] items-stretch gap-4` + `span w-[4px] shrink-0 rounded-full bg-led led-breathe`
+ `div min-h-[2.4em]`, e em `src/index.css` o `.led-breathe` é
`scaleY(0.45 -> 1 -> 0.45)`, `transform-origin: bottom`, `1.5s ease-in-out`. **Sem fundo no
caption em lado nenhum do zip.**

Traduzido para `panel.css` / `panel.html`:

- `.caption-float` — `position: fixed`, `left/right/bottom: 0`, `z-index: 40`,
  `display: none`, **`pointer-events: none`**;
- `body[data-surface="strip"][data-float="on"] .caption-float { display: block }` — só o
  atributo a pinta;
- `.caption-float__stage` — `display: flex`, `align-items: stretch`, `justify-content: center`,
  `gap: 16px`, `max-width: 720px`, `padding: 0 24px 12px`;
- `.caption-float__led` — **4px**, `border-radius: 999px`, `background: var(--accent-gradient)`,
  `transform-origin: bottom`, `animation: caption-led-breathe 1.5s ease-in-out infinite`;
  `:not(.is-on)` desliga a animação e baixa a opacidade para 0.3;
- `.caption-float__line` — `font-size: calc(clamp(24px, 3.1vw, 42px) * var(--caption-scale))`,
  `font-weight: 700`, `line-height: 1.14`; `.is-empty` = 13px, `letter-spacing: 0.3em`,
  maiúsculas, branco a 30% — o **OUVINDO…** do zip;
- `caption-float.js` escreve `OUVINDO\u2026` quando não há texto e está a ouvir, e liga/desliga
  `is-empty` e `is-on`;
- `@media (max-height: 139px)` esconde `__prev`, `__meter` e `__credits` — a shell só dá 100px
  hoje, portanto sem isto o overlay nascia cortado.

**A barra a que a legenda se apoia é o único corpo do overlay.** A invariante é verificada
literalmente: *nenhuma regra pinta fundo, borda, sombra, `backdrop-filter` ou `outline` no
próprio `.caption-float`* (check B1, 0 regras).

### 3.3 Enquanto a legenda está solta, a barra sai da frente

As duas overlays partilham **uma** janela, portanto empilham-se em vez de se sobreporem:

```css
body[data-surface="strip"][data-float="on"] .panel { inset: 0 0 auto 0; height: auto; }
body[data-surface="strip"][data-float="on"] .caption-float { top: 34px; }
```

34px = 26px do botão do strip + 8px de `padding` do `.panel`. **Porque não esconder a barra:**
a legenda é `pointer-events: none` e o overlay não tem controlo próprio; com a barra escondida o
dono ficava com uma janela que não consegue clicar e sem caminho de volta — o mesmo beco sem
saída que o botão de transparência construía. **Porque não click-through:**
`bridge.setTransparency(true)` punha `WS_EX_TRANSPARENT` sem recuperação do lado da página
(medido: `TRANSPARENCY_ON click_through=true`, e o dono não conseguiu clicar de volta). A janela
fica interactiva.

### 3.4 Overlay 3 — o painel da direita (todos os botões, todo o histórico)

Cabeçalho do painel: `#font-smaller-button`, `#font-larger-button`, `#panel-pause-button`,
`#hide-button`, `#sotto-accent`. Controlos: `#history-toggle`, `#search-button`, `#reveal-button`.
O selector de temas (`#theme-picker`) e o `#tune-dialog` são criados por JS e **escondidos no
strip** por CSS:

```css
body[data-surface="strip"] .theme-picker,
body[data-surface="strip"] #tune-dialog { display: none !important; }
```

O histórico vive só aqui, e isso é uma regra, não uma impressão:

```css
body[data-surface="panel"] .stripbar,
body[data-surface="strip"] .panel__header,
body[data-surface="strip"] .history,      <- o histórico NÃO existe no strip
body[data-surface="strip"] .status__text { display: none; }
```

E nenhum nó de histórico mora no markup do strip (check C3: os 13 ids do `stripbar` não contêm
`history` nem `transcript`). O caminho de ida é o botão **Open panel** → `openFullPanel(reason)`
→ `bridge.setPanelSurface(‘panel’, reason)` (`panel.js:2081-2083`), medido a funcionar no log:
`PANEL_SURFACE surface=panel reason=strip-open` **6x**.

---

## 4. Pins (medidos no fim de todas as edições)

| ficheiro | bytes | linhas | CRLF / bare LF | sha256 (24) |
|---|---|---|---|---|
| `app/panel/panel.css` | 108 638 | 2 943 | 2 942 / **0** | `ABC7BD63F280FF00FCE0B8EA` |
| `app/panel/panel.html` | 61 579 | 1 065 | 1 064 / **0** | `33ED88B9E6F4D93A74E812AB` |
| `app/panel/panel.js` | 147 279 | 3 027 | 3 026 / **0** | `BCCB78E026D6A28E6BDFF35C` |
| `app/panel/caption-float.js` | 4 965 | 119 | 118 / **0** | `602288DAE3946524241EC0C2` |
| `_main/three-overlays-oracle.js` | 18 722 | 315 | 0 / 314 | `EAA79DAB2DE00AD9A9716378` |

Os quatro ficheiros do painel continuam **CRLF com 0 bare LF**, a propriedade que o resto da
bateria assume. O oráculo novo é LF (é um instrumento de `_main/`, não um asset do painel).

---

## 5. O oráculo — `_main/three-overlays-oracle.js`

Node puro, **sem browser e sem lançar nada**: lê os bytes de `app/panel/*`, faz o parse das
regras CSS com um parser próprio (percorre os bytes e conta profundidade, portanto uma **lista**
de selectores e um `@media` aninhado são ambos tratados) e afirma o contrato.

### 5.1 Cor verde — os bytes que vão a bordo

```
$ node _main/three-overlays-oracle.js
THREE-OVERLAYS ORACLE -- PRISTINE (the shipped bytes)
  ... 30 check(s), 0 failed
VERDICT: PASS
rc = 0
```

Os 30 checks, por família: **A1-A5** as três superfícies existem e o caminho entre elas existe;
**B1-B6** a invariante de “sem fundo” e o desenho do zip; **C1-C4** histórico só à direita;
**D1-D6** colocação dos botões; **E1-E5** o bug está fechado; **F1-F4** o desenho da legenda.

Os que interessam ao pedido, com o detalhe que o oráculo imprime:

```
ok  A1 the bottom surface exists (strip-scoped rules)      54 rule(s)
ok  A2 the right surface exists (panel-scoped rules)        3 rule(s)
ok  B1 no rule paints a background or a box on .caption-float itself
ok  B3 the overlay is click-through (pointer-events:none)  none
ok  B4 the overlay is display:none until data-float=on     none
ok  B5 the zip 4px breathing bar exists                    .caption-float__led + @keyframes
ok  C1 .history is display:none on the strip               body[data-surface="strip"] .history { display:none }
ok  C2 .history is reachable on the right panel            no panel-scoped .history rule
ok  C3 no history/transcript node lives in the strip markup
ok  D1 the strip carries the bare-minimum button set       all 8 present
ok  D2 the strip carries NO transparency button and NO theme chevron  transparency:false chevron:false
ok  E1 nothing hides the slab on data-transparency=on any more
ok  E4 the strip bar FILLS its window                      max-content:false transparent-body:false
ok  F4 while floated, the bar steps to the top             panel inset:0 0 auto 0 + caption top:34px
```

### 5.2 Cor vermelha — `--neg-arm`, 7 mutantes, todos RED

Cada mutante é aplicado a uma **cópia** em scratch (`TMPDIR=I:\cc-tmp`), uma mutação de cada vez,
com a cópia reposta nos bytes originais antes de cada uma — um mutante só pode falhar por sua
conta. Resultado medido:

```
$ node _main/three-overlays-oracle.js --neg-arm
  RED    N1 the transparency trap is re-added            -> 1 failing: E1
  RED    N2 the overlay gains a background               -> 1 failing: B1
  RED    N3 .history is un-hidden on the strip           -> 1 failing: C1
  RED    N4 the transparency button comes back           -> 2 failing: D2 | E2
  RED    N5 the strip shrinks back to a max-content pill -> 1 failing: E4
  RED    N6 the breathing bar is deleted                 -> 1 failing: B5
  RED    N7 the OUVINDO... empty state is deleted        -> 1 failing: B6
NEG-ARM VERDICT: PASS -- every mutant went RED.
rc = 0
```

N1 é o **bug do dono a ser reintroduzido** e o oráculo apanha-o; N5 é a **pílula** e N2 é o
“sem fundo”. Sem estes três o verde não valeria nada.

### 5.3 Dois defeitos do próprio oráculo, apanhados pelo braço negativo

Registados porque são o ponto do braço negativo:

1. **N7 ficou GREEN na primeira corrida.** O check B6 procurava a palavra `is-empty` no
   `caption-float.js`, e o mutante que apaga o `classList.toggle` deixava a palavra viva **num
   comentário** ao lado. Corrigido para afirmar o **código**
   (`/classList\.toggle\(.is-empty.,\s*empty\)/` e `textContent = .OUVINDO`), não a menção.
2. **C1 falhava nos bytes bons.** A regra que esconde o histórico no strip é **um membro de uma
   lista de quatro selectores**, e o meu primeiro matcher exigia que o membro *fosse* a classe.
   Corrigido para procurar o token `.history` (com `(?![-\w])`, para não apanhar
   `.history__label`, que tem regras próprias de pausa nas duas superfícies) dentro do compound,
   e para exigir que o **próprio membro** seja `panel`-scoped no C2.

---

## 6. Censo colateral — não parti nenhum portão de outra lane

Corri os 14 oráculos `node` de `_main/` que lêem o painel e **não lançam processo nenhum**
(classificados por ausência de `child_process`/`spawn`/`run.cmd`/`sotto_webview`):

| oráculo | rc | veredicto |
|---|---|---|
| `caption-renderer-integration.js` | 0 | 7 PASS / 0 FAIL |
| `history-gallery-oracle.js` | 0 | GREEN 6/6 |
| `history-producer-gate.js` | 0 | GREEN producer-wired-through |
| `letter-swap-oracle.js` | 0 | 84/84 |
| `live-vs-history-source-oracle.js` | 0 | GREEN 13/13 |
| `panel-state-guard-gate.js` | 0 | GREEN 3/3 |
| `redux-live-contract-oracle.js` | 0 | PASS 8/8 |
| `route-stamp-gate.js` | 0 | PASS 17/17 |
| `scope-leak-oracle.js` | 0 | PASS 9 stylesheets, leaked=0 |
| `theme-preview-oracle.js` | 0 | PASS |
| `theme-scope-oracle.js` | 0 | PASS |
| `theme-tune-oracle.js` | 0 | 64/64 |
| `strip-float-oracle.js` | **1** | **45 checks, 2 failed** — ver §6.1 |
| `flicker-dom-oracle.js` | **1** | pré-existente, ver §6.2 |

### 6.1 `_main/strip-float-oracle.js` — o portão da lane S2 fixa o bug

Este oráculo é da lane S2, escrito **2026-10-12 17:02** (13 530 B, sha `DECFCD09788BA44D`), e
fixa exactamente as duas regras que produziram o relato do dono:

```
FAIL  S3 the strip panel sizes itself to its content   no width:max-content on the strip surface
FAIL  S5 the strip body is transparent (the bar is only buttons)   no transparent body
```

**Não toquei no ficheiro** (é de outra lane). Os outros **43** checks dele continuam verdes —
nomeadamente S1 (`--strip-height` 40px), S4 (sem linha de legenda no strip), S8-S19 (o botão
Linhar, os nós do overlay, os exports do módulo) e W1-W9 (a cablagem no `panel.js`), portanto a
minha alteração não lhe mexeu no resto. **Acção pedida ao Lead:** reformar ou re-basear S3/S5;
enquanto isso o portão da S2 vai dizer RED sobre bytes que são a correcção do bug que o dono
reportou.

### 6.2 `_main/flicker-dom-oracle.js` — quebrado antes desta lane

```
_main/flicker-dom-oracle.js:15
    let panel = document.querySelector(‘#sotto-panel’);
ReferenceError: document is not defined
```

Rebenta na **linha 15**, antes de ler um único byte do painel: é um instrumento de harness DOM
(`require(‘jsdom’)` está lá, o `global.document` é que não é montado). Não é regressão minha e
não tem relação com `app/panel/*`.

---

## 7. Achados cross-lane — NÃO corrigidos aqui

Todos medidos, nenhum tocado (fora do meu escopo de escrita):

1. **O rect guardado ganha ao CSS.** `panel-visibility.json` tem `surface:"strip" 1040x100` e
   `geometry_for` (`sotto_webview.py:6447`) devolve o rect guardado quando
   `saved["surface"] == surface`, portanto `--strip-height: 40px` é ignorado no arranque. O log
   mostra `STRIP_HEIGHT from=148 to=40 source=css css_value=40` seguido de
   `window=1040x100`. **É a shell que decide a largura do strip**; a queixa “mais estreito, do
   tamanho dos botoes” é dela. O painel só pode garantir que a janela *lê-se* como painel.
2. **`PANEL_LAZY_EMPTY_FAILED` continua vivo: 99 ocorrências** no log inteiro, por URL:
   `skins/skins.js` 24, `skin-host.js` 24, `themes/cinematic.css` 23, `skin-layout.css` 23,
   `themes/panel-designs.css` 5 — todas com
   `AttributeError("‘CoreWebView2’ object has no attribute ‘CreateWebResourceResponse’")`. Os temas
   cinematográficos e os skins **não chegam ao painel** por esta via.
3. **A terceira superfície que o dono pediu é recusada pelo nome.** O duplo Alt+C quer
   `surface="side"` e `SURFACE_NAMES = (‘strip’, ‘panel’)` (`sotto_webview.py:1437`) recusa:
   `PANEL_SURFACE_REFUSED surface="side" reason=hotkey-double` **4x** (linhas 91062, 91081,
   114760, 114777). A “terceira overlay” do dono é servida pelo `panel`, que já existe — mas o
   atalho que ele descreve continua a não ter para onde ir.
4. **Não existe kind de bridge para mudar a altura do strip ou do float.** `panel.js`
   `setStripHeight` só consegue mexer na variável CSS e chamar `setPanelSurface`; quem redimensiona
   é a shell. Registado como limite, não como defeito.
5. **Um erro de página vivo:** `SottoHost.dispatch() takes 2 positional arguments but 3 were
   given` (linha **114741**, `unhandledrejection`) — o contrato de 3 slots do `BOOTSTRAP_JS` contra
   a assinatura do handler. `BRIDGE_UNKNOWN_KIND` = 0, `BRIDGE_BAD_MESSAGE` = 0,
   `BRIDGE_HANDLER_FAILED` = 0, portanto não está a partir o bridge — mas está lá.

---

## 8. NÃO MEDIDO — o que este recibo NÃO afirma

- **Nada foi lançado.** A ordem do dono reserva o lançamento ao Lead, e esta lane não correu a
  app, o shell, o worker nem qualquer probe de WebView2. Portanto: **não medi um único pixel do
  que o WebView2 pinta** com estas alterações. O que está medido é o CSS, o markup, a cablagem e
  o log do dono; a prova de tinta continua a faltar.
- O log citado é o do shell **pré-pin** que o dono está a correr (`pid 33248`), e as suas linhas
  **não têm carimbo de hora** — não afirmo horas a partir dele.
- Não sei se o dono vê a largura de 1040px como “estreito o suficiente” depois da correcção: o
  pedido de estreiteza é da shell (§7.1) e continua por satisfazer.
- `--strip-chrome` (78px) ficou definido e sem consumo; não medi se algum tema ou skin o lê.

---

## 9. Comandos, para reproduzir

```powershell
$env:TMPDIR=‘I:\cc-tmp’
cd H:\sotto
node _main/three-overlays-oracle.js              # 30 checks, 0 failed, VERDICT: PASS, rc=0
node _main/three-overlays-oracle.js --neg-arm    # 7/7 RED, NEG-ARM VERDICT: PASS, rc=0
node _main/strip-float-oracle.js                 # 45 checks, 2 failed (S3/S5, a lane S2)
```

