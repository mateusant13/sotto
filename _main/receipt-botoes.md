# Recibo — lane BOTOES (painel de baixo minimo, movivel; live; X na direita)

**Lane:** botoes · **Repo:** `H:/sotto` · **Data:** 2026-10-12 (America/Sao_Paulo)
**Escopo de escrita:** `app/panel/panel.html`, `app/panel/panel.css`,
`_main/botoes-lane-oracle.js` (novo), `_main/botoes-lane-gesture-oracle.js` (novo), este recibo.
**Nada mais foi tocado.** `app/panel/panel.js`, `caption-float.js`, `themes/**`, `skins/**`,
`app/webview/**` e `worker/**` ficaram intactos. Sem commit, sem push, sem `git add -A`.
**Nenhum lancamento:** nenhum comando deste recibo abre a app, o shell, o worker, o WebView2
ou um browser. Todos os instrumentos sao `node` sobre bytes e um jsdom.

---

## 0. Pins medidos no fim de todas as edicoes

| ficheiro | bytes | linhas | CRLF / bare LF | sha256 |
|---|---|---|---|---|
| `app/panel/panel.html` | **69 730** | 1 185 | 1 184 / **0** | `2A065214AC0571B335CF3B9E6431B6216A1D8DAC9ADB4FF61FAD673366DE33FE` |
| `app/panel/panel.css` | **118 985** | 3 128 | 3 127 / **0** | `C2002FC75D49E77350B8C1D5905E111B815435C4983F14543F32FA003D0EE54F` |
| `_main/botoes-lane-oracle.js` | **14 668** | 276 | 0 / 275 | `71C3FE6997D913522FD0078A474AF201E351E0D6B1630908AE45A5B25E1A3526` |
| `_main/botoes-lane-gesture-oracle.js` | **8 690** | 167 | 0 / 166 | `F8664EED71F409BB9816AB08C962FEA1744D205BBCE0D74442547EF947863E7E` |

Os dois assets do painel continuam **CRLF com 0 bare LF** (a propriedade que o resto da
bateria assume); os dois oraculos sao LF, como os outros instrumentos de `_main/`.
Os dois `node --check` passam (rc=0) e o `panel.css` fecha com profundidade de chaves 0.

---

## 1. MINIMO — o que foi medido antes de cortar, e o que saiu

### 1.1 O censo (instrumento: leitura dos bytes de `panel.html`, regex sobre a `<section class="stripbar">`)

**ANTES** — 8 botoes + o mostrador de estado, 13 ids dentro da tira:
`strip-live-button`, `strip-theme-button`, `strip-open-button`, `strip-hide-button`,
`strip-font-smaller-button`, `strip-font-larger-button`, `strip-float-button`,
`strip-pause-button` (+ `strip-controls`, `strip-live-label`, `strip-state`, `strip-dot`, `strip-word`).

**DEPOIS** — 5 botoes + o mostrador, 11 ids:
`strip-live-button`, `strip-open-button`, `strip-hide-button`, `strip-float-button`,
`strip-pause-button` (+ `strip-controls`, `strip-drag-handle`, `strip-live-label`, `strip-state`,
`strip-dot`, `strip-word`). **8 botoes -> 5.**

### 1.2 O botao de transparencia — JA NAO ESTAVA (confirmado, nao assumido)

`grep` sobre os bytes: `strip-transparency-button` = **0 ocorrencias** em `panel.html` e em
`panel.css` antes desta lane comecar. A lane anterior (three-overlays) ja o tinha apagado, com
a causa raiz medida no `_main/webview-run.log` (linha 114746, `TRANSPARENCY_ON click_through=true`).
Nada a fazer aqui. O meu oraculo fixa-o na mesma (check A5), para que nao volte por uma linha de markup.

### 1.3 O que saiu, com a medicao que tornou cada corte seguro

| # | botao | o que fazia | porque saiu | o que se perde |
|---|---|---|---|---|
| 1 | `#strip-theme-button` | ciclava o template no clique | *"o painel de baixo, deve conter apenas o bare minimum"* | o CICLO rapido. O tema continua alcancavel: `#strip-open-button` abre o painel e o `#theme-chevron` de la abre a lista. `grep -c strip-theme-button app/panel/panel.js` = **0** — nenhum handler ficou pendurado |
| 2 | `#strip-font-smaller-button` | baixava `--caption-scale` | idem (e a tira ja nao mostra legenda nenhuma) | nada exclusivo: o PAR do painel (`#font-smaller-button`/`#font-larger-button`) continua em `.panel__controls`, e `panel.js wireFontDial` liga os quatro com o mesmo `applyCaptionScale`; remover dois call sites deixa os dois que ficam |
| 3 | `#strip-font-larger-button` | subia `--caption-scale` | idem | idem |

**Os tres NULL-CHECKS do `panel.js` foram verificados, nao supostos:** `bind(dom.stripFontSmallerButton, -1)`
comeca por `if (!button) return;` e `dom.stripFloatButton`/`stripLiveButton`/`stripOpenButton`/
`stripHideButton` tem todos `if (dom.…)` antes de qualquer `addEventListener`. `panel.js` NAO foi tocado.

### 1.4 O que FICOU, e porque

`live` (o dono nomeou-o), `open` (unica porta para o painel), `hide` (o X; sem ele nao ha saida da
janela), `linhar` (o dono pediu-o em 2026-10-12), `pause` (unico controlo que larga a RAM do motor).
O mostrador `#strip-state` nao e botao.

### 1.5 "mais estreito, do tamanho dos botoes"

`--strip-height` = **40px** (medido: `:root { --strip-height: 40px; }`, panel.css). Uma linha de
botoes de 26px + 8px de padding do slab. A LARGURA nao e do documento: a janela e do shell
(`_main/panel-visibility.json` rect `1040x100`), e a lane three-overlays ja tinha provado que um
body transparente + uma pilula `max-content` **era** o bug da "cor solida". Nao repeti esse erro:
a slab continua a ENCHER a janela. A largura estreita e cross-lane e fica pedida no §6.

---

## 2. MOVIVEL — a metade da PAGINA, e o contrato exacto que o Lead tem de ler

### 2.1 O que esta feito (a metade (a))

`app/panel/panel.html`, um `<script>` inline (3 130 B) no fim do documento, porque `panel.js`
e de outra lane. Ele:

1. le a posicao guardada ANTES do primeiro paint e pinta-a;
2. liga `pointerdown` em `#strip-controls` (a barra toda — a pega `#strip-drag-handle` e a
   afordancia VISIVEL, nao a unica zona arrastavel);
3. um `pointerdown` que cai num `button/a/input/select/textarea` **nao** e um arrasto (o controlo
   fica com o clique);
4. `pointermove` calcula `dx/dy` do ponto de agarre, aplica um limiar de **4 px**, e depois
   pinta + grava + avisa o shell;
5. `pointerup`/`pointercancel`/`blur` fecham o gesto. Um clique que nunca moveu NAO reescreve a
   posicao (defeito medido durante o desenvolvimento: um clique simples gravava `{x:0,y:0}` por
   cima da posicao escolhida — corrigido e fixado no oraculo de gesto, ARM 5).

**Nada aqui move a janela.** O shell e que a move (§2.2). A pagina aplica o deslocamento a
`.panel` com `transform: translate(var(--strip-move-x), var(--strip-move-y))`, portanto a barra
segue o ponteiro mesmo sem o shell; quando o shell mover a JANELA tem de pôr `body[data-strip-moved]`
e a pagina para de transformar — senao os dois movimentos somavam-se.

### 2.2 A metade (b) — O QUE O LEAD TEM DE LER, exactamente

**Chave de storage (a que o shell le):**

```
localStorage["sotto:strip-offset"]
```

**Forma do valor** (JSON, uma linha):

```json
{ "x": -40, "y": 12, "v": 1 }
```

| campo | tipo | significado |
|---|---|---|
| `x` | inteiro | deslocamento CUMULATIVO em pixels CSS (DIP) desde a posicao DOCKADA, para a direita. Negativo = para a esquerda |
| `y` | inteiro | idem, para baixo. Negativo = para cima |
| `v` | inteiro | versao do formato. **`1` hoje.** Um leitor que nao reconheca `v` deve ignorar o valor inteiro, nunca reinterpretar |

Ausente = nunca foi arrastado (usar a posicao dockada). O valor e escrito em CADA move e no release.

**Chamada opcional do bridge (o shell pode implementar para o movimento ao vivo):**

```js
window.sotto.setStripOffset(dx, dy, phase)
//   dx, dy : inteiros, o MESMO deslocamento cumulativo do storage
//   phase  : "move" durante o arrasto, "end" no release
```

A pagina faz `typeof bridge.setStripOffset === "function"` antes de chamar — um shell que ainda
nao a tenha continua a receber a posicao pelo `localStorage`. O metodo NAO existe em
`app/webview/sotto_webview.py` hoje (medido: `grep -n setStripOffset` = 0 ocorrencias no shell).

**O que o shell tem de fazer com isto (e so isto):**

1. ao abrir a tira, ler `localStorage["sotto:strip-offset"]` e somar `(x, y)` ao rect dockado,
   com o clamp da area de trabalho que o `edit_drag_to` ja faz
   (`sotto_webview.py:6114-6118`: `max(work.x, min(x - grab, work.x + work.width - width))`);
2. ao receber `setStripOffset(dx, dy, "move")`, aplicar `SetWindowPos(hwnd, HWND_TOPMOST, x*scale,
   y*scale, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)` — o mesmo caminho de `edit_drag_to` (`:6127-6129`);
3. por `body[data-strip-moved]` no documento quando mover a JANELA (uma linha de `exec_js`),
   senao a pagina transforma E a janela move: 2x;
4. em `"end"`, gravar a geometria (`publish_panel_visibility("edit-move")` ja existe, `:6136`).

**O que NAO e preciso:** nenhum `--flag` novo, nenhum parser novo, nenhuma segunda tabela de
posicoes. `_main/panel-visibility.json` continua a ser a fonte da verdade do rect; este offset e
a INTENCAO do dono por cima dela.

---

## 3. BOTAO LIVE — o que cada um era, e o que passou a ser

### 3.1 O que foi medido ANTES (tres nos, nao um)

| id | onde | o que era, medido |
|---|---|---|
| `#live-label` | painel da DIREITA, dentro de `.captions__bar` | um `<span>` que pintava a palavra "Live" **acima da caixa de legenda**. NAO era botao: `grep -n "live-label" app/panel/panel.js` = **0**; nenhum `addEventListener` em todo o repo; as unicas referencias fora do markup eram as COPAS de fixture em `_main/`. Nao tinha clique, nao tinha estado, nao fazia nada |
| `#strip-live-button` | tira | O TOGGLE real. `panel.js applyLiveEnabled` (:2011) escreve `aria-pressed`, `aria-disabled`, `data-wired` e o `title`; o clique (:1828) chama `applyLiveEnabled(!liveEnabled)` |
| `#strip-live-label` | dentro do toggle | o TEXTO. `panel.js:2026` reescreve-o para `LIVE` em cada apply — e o comentario do modulo diz que a palavra e o NOME do controlo, nao o estado |

**O que foi feito:** `#live-label` foi APAGADO (era o unico no da direita ligado a legenda), e o
`#strip-live-button` passou a ser o UNICO controlo que a anuncia. O `<section class="captions">`
continua a ter o seu proprio `aria-label="Live caption"`, portanto a arvore de acessibilidade
continua a nomear a regiao — nada ficou mudo.

### 3.2 "CLARO quando ta live e quando nao ta" — os dois estados

Medido antes: os dois estados ja tinham `aria-pressed` diferente, mas **a mesma palavra e o mesmo
vermelho** — a unica diferenca que o olho tinha era um tinte fraco num pilula de 22 px. O dono
estava a olhar para o controlo e nao conseguia dizer em que estado estava.

| | palavra (visivel) | palavra (DOM) | cor | aria-pressed |
|---|---|---|---|---|
| **ON** | `live` | `LIVE` | pill VERMELHO (`rgba(229,72,77,.22)`, borda `.85`, glifo `#ff6b70`) | `"true"` |
| **OFF** | `off` | `LIVE` | pill CINZA (`rgba(148,163,184,.1)`, borda `.45`, glifo `#94a3b8` a 75%) | `"false"` |

**Como a palavra muda sem tocar no `panel.js`** (que e de outra lane): o texto do DOM e escondido
com `font-size: 0` — **nao** `display:none`, para continuar na arvore de acessibilidade e para o
probe de leitura continuar a encontra-lo — e a palavra do ESTADO e pintada pelo `::after` da
propria pilula, com `content` escolhido por `aria-pressed`, o atributo que o modulo JA mantem.
As duas palavras sao funcao do MESMO atributo, portanto nao podem discordar.

`_main/_panel2-dom-probe.js` ARM T continua a passar e continua a ler `"LIVE"` no `textContent`
(medido: `[PASS] and the label follows the state  real = "LIVE"`), o que prova que a metade do
DOM nao foi quebrada.

---

## 4. O BOTAO DA DIREITA QUE MOSTRAVA LEGENDA — qual era, e porque foi seguro apaga-lo

**O unico no do painel da direita ligado a legenda era `#live-label`** (o `<span>` do §3.1).
Nao havia mais nada: o censo de TODOS os `<button>` do documento da **19** botoes, e os do painel
da direita sao `#font-smaller-button`, `#font-larger-button`, `#panel-pause-button`, `#hide-button`
(em `.panel__controls`), `#history-toggle`, `#history-root`, `#search-button`, `#search-clear`,
`#reveal-button` (no bloco do historico) — **nenhum deles mostra ou esconde legenda**, e nenhum foi
tocado. O `#history-toggle` e o unico que se lhe poderia parecer: ele abre a GAVETA DO HISTORICO
(`aria-expanded`/`aria-controls="history-body"`, `panel.js:1126`), o que e uma coisa diferente e
que o dono quer no painel da direita.

**Verificacao de que nao apaguei um botao que faz outra coisa:** o `#live-label` nao tinha
`addEventListener`, nao tinha `id` referenciado por `panel.js`, nao tinha handler em nenhum modulo,
e nao era `<button>` (era `<span class="history__label">`). O seu `title` (o nome do modelo)
desapareceu com ele — e o mesmo texto continua no `title` do `#strip-live-button` e no `aria-label`
da seccao, portanto a informacao nao se perdeu.

---

## 5. X PARA A DIREITA — as duas superficies

| superficie | ANTES | DEPOIS | como e imposto |
|---|---|---|---|
| tira | `#strip-hide-button` era `order: 4`, **no meio** (live, theme, open, **hide**, font-, font+, float, pause) | **`order: 6`**, ultimo controlo. Ordem pintada: brand(0) · grip(1) · live(2) · open(3) · pause(4) · linhar(5) · **hide(6)** · state(99) | regra `body[data-surface="strip"] #strip-hide-button { order: 6; }` (a=1, nenhum tema a pode mover) |
| painel da direita | `#hide-button` **ja era** o ultimo: DOM `[font-, font+, panel-pause, hide]` e `order: 7`, o maior do cluster | **inalterado** (medido, nao assumido) | `.panel__controls #hide-button { order: 7; }` + ser o ultimo filho no DOM |

O dono disse *"introduzido em lugar aleatorio e estupido"* — o defeito estava na TIRA, e era
medivel: `#strip-hide-button` pintava entre o `open` e o `linhar`. As duas superficies ficaram
coerentes: o X e o ultimo CONTROL, e so o MOSTRADOR de estado (que nao e botao) vem depois.

---

## 6. O LINK DO `caption-float.css`

`panel.html` passou a ter, **imediatamente depois** de `panel.css`:

```html
<link rel="stylesheet" href="caption-float.css" />
```

Medido: `href="panel.css"` @ offset **2065**, `href="caption-float.css"` @ **2310** — o segundo
depois do primeiro, como pedido.

**Nota de cronologia (medida):** quando este link foi escrito, `app/panel/caption-float.css`
**nao existia** (`Test-Path` = False) e foi acrescentado na mesma, como o brief manda. A lane
CAPTION criou-o entretanto — re-medido no fim desta lane: **existe, 6 756 B, mtime
2026-10-13T00:13:29Z**, e NAO tem uma unica regra sobre `#strip-live-button`, `.stripbar` ou
`.panel__controls` (0 ocorrencias de cada, medido), portanto nao colide com nada do que esta lane
escreveu. A posicao do link importa: sendo o ULTIMO dos quatro primeiros, e a folha que tem a
ultima palavra sobre a overlay, que e o que a lane CAPTION quer.

---

## 7. O GATE — as duas cores, com controlo

### 7.1 `_main/botoes-lane-oracle.js` — 33 checks sobre os BYTES

```
$env:TMPDIR="I:\cc-tmp"; node _main/botoes-lane-oracle.js
  -> 33 check(s), 0 failed   VERDICT: PASS   rc=0

$env:TMPDIR="I:\cc-tmp"; node _main/botoes-lane-oracle.js --neg-arm
  -> RED  M1 the live button is deleted                        -> 4 failing check(s)
     RED  M2 the live OFF state loses its word                 -> 1 failing check(s)
     RED  M3 the right panel caption label comes back          -> 2 failing check(s)
     RED  M4 hide stops being the rightmost control on the strip -> 1 failing check(s)
     RED  M5 the drag gesture pointerdown binding is deleted   -> 1 failing check(s)
     RED  M6 the caption-float.css link is deleted             -> 2 failing check(s)
     RED  M7 the strip shows its caption box again             -> 1 failing check(s)
     NEG-ARM VERDICT: PASS -- every mutant went RED.   rc=0
```

Braços: **A** minimo (censo, `display:none`, 40px) · **B** o live e o controlo · **C** nenhuma
porta de legenda na direita · **D** o X e o ultimo controlo nas duas superficies · **E** o gesto
e o contrato de storage · **F** o link · **G** os dois estados do live (palavra E cor).
Cada mutante e injetado numa COPIA de `app/panel` inteira (verificada byte a byte antes de mutar).

### 7.2 `_main/botoes-lane-gesture-oracle.js` — o gesto NUM DOM, 11 checks

O oraculo dos bytes prova que o gesto esta DECLARADO. Este prova que ele FUNCIONA: carrega o
`panel.html` real em jsdom, corre os scripts reais e empurra eventos de ponteiro a serio.

```
$env:TMPDIR="I:\cc-tmp"; node _main/botoes-lane-gesture-oracle.js
  -> 11 check(s), 0 failed   VERDICT: PASS   rc=0
```

| # | o que prova | medido |
|---|---|---|
| 1 | o arrasto grava | `typeof raw === "string"` |
| 2 | a forma e `{x,y,v}` | `[60, 30, 1]` para um gesto de (100,100)->(160,130) |
| 3 | o documento e pintado | `["60px","30px"]` |
| 4 | o bridge e chamado | `[60, 30, "move"]` |
| 5 | um pointerdown num BOTAO nao e arrasto | storage = `null` |
| 6 | uma carga nova RESTAURA antes do primeiro paint | `["-40px","12px"]` |
| 7/7b/7c | **CONTROLO**: o mesmo documento com o handler `pointermove` renomeado | storage `null`, `0` moves ao bridge, paint preso em `0px` (um arrasto real deixaria `100px`) |

### 7.3 Regressoes nos gates que ja existiam (medidos, nao escondidos)

| instrumento | antes | agora | leitura |
|---|---|---|---|
| `node _main/_s2-bar-dom-oracle.js` | PASS 23/23 | **PASS 23/23** | sem regressao. O bar continua sem legenda, o overlay continua a espelhar a linha |
| `node _main/strip-float-oracle.js` | PASS 47/47 | **PASS 47/47** | sem regressao. O `#strip-float-button` continua no markup e na ordem certa |
| `node _main/_panel2-dom-probe.js` | RED 81/82 | **RED 81/82** | **mesma falha, pre-existente**: ARM H exige `grid-template-rows: minmax(calc(var(--strip-height) - var(--strip-chrome)), 1fr) auto auto` no strip, regra que a lane three-overlays apagou (hoje `minmax(0, 1fr)`). Medido sobre os bytes de `HEAD:app/panel/panel.css`: a regex **tambem nao casa la** (`matches HEAD bytes: false`). Nao e minha. ARM T (o live) passa |
| `node _main/three-overlays-oracle.js` | PASS 30/30 | **FAIL 30/30, 2 falhas** | **D1 e D6 falham porque fixam os 8 botoes**, incluindo os tres que o dono mandou sair (theme + font dial). Nao posso editar esse ficheiro (fora do escopo) — pedido no §8 |
| `node _main/theme-preview-oracle.js` | PASS | **FAIL, 1 falha** | **ARM14.1** exige `#strip-theme-button` no markup. Mesma causa, mesmo pedido no §8 |

---

## 8. O QUE NAO CONSEGUI FECHAR — e o pedido exacto ao Lead

1. **TRES gates fixam os botoes que o dono mandou sair.** Falham por isso, e a falha e a
   informacao certa (o gate esta a defender a versao antiga). Precisam de re-baseline, e nenhum
   deles esta no meu escopo de escrita:
   * `_main/three-overlays-oracle.js` — `D1` (a lista `BARE` de 8 ids) e `D6` (exige
     `id="strip-theme-button"[^>]*data-theme-button`). O que passa a ser verdade: a tira tem
     **5** botoes, `strip-live-button`, `strip-open-button`, `strip-hide-button`,
     `strip-float-button`, `strip-pause-button`.
   * `_main/theme-preview-oracle.js` — `ARM14.1` (`panel.html still ships #strip-theme-button`).
     O que passa a ser verdade: o ciclo vive so no painel da direita; a lista (`#theme-chevron`)
     e o proprio `#theme-button` continuam la, e `#strip-open-button` leva ao painel.
   * `_main/_panel2-dom-probe.js` — `ARM H` ja estava RED antes desta lane (medido contra
     `HEAD:app/panel/panel.css`). Nao e meu, mas fica nomeado para nao parecer meu.

2. **A metade (b) do movimento — a JANELA — nao esta feita e nao pode ser feita por mim**
   (`app/webview/**` fora do escopo). O contrato completo esta no §2.2: chave
   `localStorage["sotto:strip-offset"]`, valor `{x,y,v}` em DIP, bridge opcional
   `setStripOffset(dx, dy, "move"|"end")`, e o `body[data-strip-moved]` que evita o movimento a 2x.
   **Sem esta metade o dono arrasta e a barra anda DENTRO da janela**, nao no ecra.

3. **A largura da tira** (`"mais estreito"`) e da shell: o rect guardado
   (`_main/panel-visibility.json`, `1040x100`) ganha ao `--strip-height: 40px` do CSS dentro de
   `geometry_for`. Ja reportado pela lane three-overlays; continua aberto.

4. **Nao medi nada com o WebView2 real.** Nenhum lancamento nesta lane (a regra do repo: so o Lead
   lanca). O que fica por medir: (a) se o arrasto move a janela de facto; (b) se o `::after` com
   `content` pinta como esperado no Chromium do WebView2 (em jsdom a regra existe e casa, mas o
   `content` de um pseudo-elemento nao e renderizado); (c) se a pega e visivel a 40px de altura.
   O comando que o Lead pode correr, quando quiser: `H:\sotto\app\webview\run.cmd --show`
   (o dono esta a usar a app; a instancia e unica).

5. **`panel.js` nao foi tocado**, por escopo. Consequencia declarada: a palavra do estado OFF e
   pintada por CSS (`::after`), nao pelo JS. Se uma lane futura preferir que o `panel.js` escreva
   `live`/`off` no `#strip-live-label`, a regra de CSS tem de sair NO MESMO commit, senao as duas
   palavras aparecem lado a lado.

