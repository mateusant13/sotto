# RECEIPT — lane ZIP-C PANELS: os 10 painéis do 3.º zip passam a ser 10 DESIGNS

**Data:** 2026-10-12 (America/Sao_Paulo)
**Lane:** zipc-panels (D1 + D2 do relatório `I:/cc-tmp/design-bugs-audit.md`)
**Nada foi lançado.** Nenhum browser, shell, worker, WebView2, `run.cmd` ou `_audit-verify-all.cmd`.
Todos os instrumentos são em processo (Python, Node, css-tree, jsdom) e nenhum abre janela.

**Escopo de escrita exercido — exactamente 3 ficheiros, e mais nenhum:**

| ficheiro | antes | agora |
|---|---|---|
| `app/panel/themes/zipc-panels.css` | 35 875 B / `9E32F9160C38B855…` | **72 757 B / `CB08DCA3AF1C4F227B3FB75B4F38D8001FD32CF63D1010244818445ED10275A9`** (2 568 CRLF / 0 bare LF) |
| `_main/_design-lane/gen_zipc.py` | **não existia** | 71 239 B (novo — o gerador que faltava) |
| `_main/zipc-designs-oracle.py` | **não existia** | 22 785 B (novo — o portão) |

`app/panel/panel.css`, `panel.html`, `panel.js`, `caption-float.js`, `themes/fonts.css`,
`themes/cinematic.css`, `themes/panel-designs.css`, `app/panel/skins/**`, `app/webview/**` e
`worker/**` **não foram tocados por mim** — mtimes em §7. Nenhum `git add/commit/push`.

`$env:TMPDIR = I:/cc-tmp` em todos os comandos.

---

## 0. A AUDITORIA FOI RE-VERIFICADA ANTES DE MEXER — e uma das 4 medições estava MAL

As 4 medições de D1 foram re-corridas com o meu próprio parser de bytes sobre o ficheiro
publicado (`9E32F9160C38B855…`, o mesmo pin da auditoria):

| # | o que a auditoria dizia | o que eu medi | veredicto |
|---|---|---|---|
| (a) | **2** sequências de selectores distintas (7 + 3) | **1** sequência, idêntica nos 10: 18 blocos e 24 membros por vírgula em cada um | **CORRIGIDA** — ver abaixo |
| (b) | dentro de cada grupo só 6 e 4 declarações de layout/tipografia diferem | 9 propriedades diferem nos 10; as não-cor são 8: `border`, `border-bottom`, `border-radius`, `padding`, `font-family`, `font-size`, `font-weight`, `letter-spacing` | confirmada em substância |
| (c) | `repeating-linear-gradient` 0, `grid-cols` 0, `rounded-full` 0, `backdrop-filter` 0, `::after` 0 | **0 / 0 / 0 / 0 / 0** (e `grid-template` 0, `display: grid` 0, `border-radius: 50%` 0, `var(` 0, `@media` 0) | **confirmada** |
| (d) | o esqueleto do GlassCards são 18 selectores sobre o DOM que o painel já tem | confirmado: os 18 são `.panel`, `.panel::before`, `.captions__body`, `.caption`, `.caption__text`, `.caption--latest .caption__text`, `.caption__time`, `.caption__led`, os 2 do placeholder, `.status__dot`, `.status--live .status__dot`, `.status__text`, os 4 do histórico, `.history__path`, `.strip-button`, `.strip-button:hover`+`:focus-visible`, os 2 do stripbar | **confirmada** |

**A correcção, e porque importa.** O "grupo de 7 + grupo de 3" é real, mas NÃO está nos
selectores: está na DECLARAÇÃO `.caption`. Os 7 primeiros (GlassCards, Paper, Quotes, Ledger,
Feed, Bubbles, Chips) levam `border: 1px solid X`; os 3 últimos (Hairline, Timeline, Gutter)
levam `border: 0` **mais** `border-bottom: 1px solid X` — é isso que faz 54 vs 55 declarações
por tema e 14 vs 15 de layout. Normalizando `:root[data-theme='X']` para
`:root[data-theme=*]`, as 10 sequências ficam **byte a byte iguais**.

Consequência para o trabalho: o defeito é **mais grave** do que a auditoria escreveu, não menos.
Não eram "2 esqueletos": era **UM** esqueleto com dez paletas. O portão novo mede isso como
`D: 1 distinct selector sequence(s) for 10 designs` (era) contra `D: 10` (agora).

---

## 1. D1 — A TABELA: design → o que o ZIP faz → o que o NOSSO CSS fazia → o que faz agora

O zip está extraído em `docs/design-intake/cinematic-transcription-app-designs (1)/`.
As 10 estruturas foram lidas de `src/components/panels/PanelSetA.tsx` (GlassCards:22, Hairline:143,
Paper:249, Quotes:357, Ledger:460) e `PanelSetB.tsx` (Feed:18, Bubbles:137, Timeline:272,
Chips:397, Gutter:507), com as paletas e a tipografia em `src/data/scenes.ts`.

| # | design | o ZIP faz (componente:linha) | o nosso CSS **fazia** (medido) | o nosso CSS **faz agora** |
|---|---|---|---|---|
| 01 | **GlassCards** | um cartão por segmento com `backdropFilter: blur(20px)`, raio `max(12, radius-6)`, avatar circular de 28px com iniciais; cabeçalho com `-space-x-2` de avatares sobre uma régua `border-t` (:22-141) | `.caption` = pílula de 12px com `background` chapado; **0** `backdrop-filter`; **0** `border-radius: 50%`; nenhum avatar | `.caption` = cartão `display: grid` `28px 1fr` com `backdrop-filter: blur(20px)` e `border-radius: max(12px, calc(var(--radius-lg) - 6px))`; `.caption::before` = avatar circular de 28px; `.captions__bar::before` = 3 avatares sobrepostos desenhados a `radial-gradient` |
| 02 | **Hairline** | painel **sem superfície nenhuma** ("near-invisible"); linha de tabs com sublinhado activo; cada segmento `grid-cols-[44px_1fr]` com `border-b`; ponto de 4px antes do nome (:143-247) | `.panel` com 2 radiais + borda; `.caption` com fundo, `border: 0`, raio 0 | `.panel` e `.captions__body`: `background: none`, `border-color: transparent`, raio 0, sem sombra; `.captions__bar` com `border-bottom` + `::before` = a tab "transcript" com sublinhado a `var(--accent)`; `.caption` `grid-template-columns: 44px 1fr`; ponto de 4px em `.caption__text::before` |
| 03 | **Paper** | **página pautada**: `repeating-linear-gradient(180deg, transparent 0 27px, rgba(60,40,26,.075) 27px 28px)`; régua de margem de 1.5px em x=52; linhas `grid-cols-[52px_1fr]` com o texto numa baseline de 27px; carimbo "filed" na última; assinatura "— continued…" no pé (:249-355) | `.captions__body` com cor chapada; **0** `repeating-linear-gradient`; linha de 27px ausente; sem carimbo | `.captions__body` com `background-image: repeating-linear-gradient(…)` + `::before` = a régua de margem a 52px em accent/35%; `.caption` `grid-template-columns: 52px 1fr`; `.caption__text` `line-height: var(--leading-closed)` = 2.16 × 12.5px = **27px** (a baseline do zip); `.caption--latest .caption__text::after` = "filed"; `.captions__list::after` = a assinatura |
| 04 | **Quotes** | cartão por citação com `borderLeft: 2px solid` na cor do falante; aspas de 34px em Instrument Serif a 18%; régua de 20px na atribuição (:357-458) | `.caption` com `border: 1px solid` uniforme e raio; sem aspas; sem régua | `.caption` com `border-left: 2px solid var(--accent)`; `.caption::before` = `content: "\201C"` a 34px Instrument Serif; `.caption__time::before` = régua de 20px |
| 05 | **Ledger** | cabeçalho de colunas "time / voice / transcript" em `grid-cols-[46px_58px_1fr]`; entradas na mesma grelha; **zebra** `i % 2 ? soft : transparent`; fio por entrada (:460-545) | `.caption` com fundo e raio; **0** `grid-template-columns` | `.caption` `grid-template-columns: 46px 58px 1fr`; `.caption__led` — o elemento que o `panel.css` esconde — volta ao fluxo como célula "voice"; `.caption:nth-child(even)` = a zebra; `.captions__bar::before` = a banda de colunas |
| 06 | **Feed** | **log, não cartões**: `flex gap-2`, sem superfície; **rampa de opacidade por recência** `max(0.14, 1 - d*0.075)`; caret `>` na linha viva; barra "sheen" animada no cabeçalho (:18-135) | `.caption` com fundo e raio; **0** `:nth-last-child`; sem caret | `.caption` `display: flex`, sem superfície/borda/raio, mono; **13 regras** `:nth-last-child(k)` = a rampa (1 → 0.14); `.caption--latest::before` = `>`; `@keyframes zipc-sheen` + `.captions__bar::after` = a barra |
| 07 | **Bubbles** | bolhas de conversa: `max-w-[86%]`, raio 16 com **um canto de cauda a 5px**; a 2.ª voz `justify-end`; chips de falante no cabeçalho; 3 pontos a pulsar (:137-270) | `.caption` com fundo e raio uniforme; **0** `align-self` | `.caption` `max-width: 86%`, `border-radius: 16px 16px 16px 5px`, `align-self: flex-start`; `.caption:nth-child(even)` → `flex-end` + cauda espelhada `16px 16px 5px 16px`; `.captions__bar::before` = pill de falante; 3 pontos em `.caption__time::before` |
| 08 | **Timeline** | **espinha** vertical de 1px com gradiente que desvanece nas duas pontas; ponto de 7px por segmento com anel `box-shadow: 0 0 0 2px`; `grid-cols-[52px_1fr]` (:272-395) | `.caption` com fundo; sem espinha; sem pontos | `.captions__body::before` = a espinha (`linear-gradient(180deg, transparent, line 8%, line 92%, transparent)`); `.caption::before` = ponto de 7px com anel de 2px; `.caption--latest::before` acende e alarga o anel para 4px |
| 09 | **Chips** | **capítulos a cada 4 segmentos**: banda com "chapter NN" + régua + hora; a hora em chip `rounded-full`; campo de busca arredondado no cabeçalho (:397-505) | `.caption` com fundo; **0** `counter(` | `.caption:nth-child(4n+1)` = a banda, com `counter(zipc-chapter, decimal-leading-zero)` em `grid-column: 1 / -1`; `.caption__time` = chip pill; `.captions__bar::after` = o campo de busca |
| 10 | **Gutter** | página clara; **gutter de 54px** com a hora E um avatar de 24px por baixo; fio por entrada; pill "rec" (:507-571) | `.caption` com fundo e raio 0; sem avatar | `.caption` `grid-template-columns: 54px 1fr` com `.caption::before` = avatar de 24px na coluna 1, linha 2; `border-bottom` por entrada; `.captions__bar::after` = pill "rec" |

### 1.1 Os meios usados, e porque não há elementos novos

`app/panel/panel.html` **não está no meu escopo de escrita**. Logo nenhum design pode acrescentar
um elemento: a estrutura é construída com gradientes (incluindo `repeating-`), `grid`,
pseudo-elementos com `content`, raios, filtros, contadores e `order`, **sobre os nós que o painel
já tem**. O DOM real, medido: `.caption` é um `<li>` dentro de `#caption-list`
(`<ol class="captions__list">`, filho de `.captions__body`), e o `panel.js:799-839` constrói-o com
`.caption__led`, `.caption__time`, `.caption__text` (`.caption__confirmed`, `.caption__provisional`,
`.caption__mark`) — cinco nós que os designs usam.

**O que NÃO é reconstruível, e é declarado em vez de falsificado:** os avatares do zip levam as
**iniciais do falante**. A linha de legenda do painel não tem elemento com nome nem atributo com
ele (`data-source` leva `proc:<pid>`, não um nome), portanto o círculo é construído (preenchimento
+ anel) e as iniciais não. É a única marca de identidade do zip que fica por fazer, e fica por
falta de DADO, não de CSS.

### 1.2 A POSIÇÃO DOS BOTÕES — a única coisa que o dono autoriza a diferir

Verbatim: *"cada tema encontrado dentro dos .zip, fiquem com o design IGUAL, e so muda a posicao
dos botoes."* O painel tem UM agrupamento de controlos (`.panel__controls`, dentro de
`.panel__header`), portanto o espaço de posições que existe sem tocar no `panel.html` é
`justify-content` + `order`:

| posição | designs |
|---|---|
| `order: 0` + `flex-start` (antes do wordmark, à esquerda) | **Hairline** |
| `order: 1` + `space-between` (a par do wordmark, distribuído) | **Quotes**, **Bubbles** |
| `order: 2` + `flex-end` (depois do wordmark, à direita) | GlassCards, Paper, Ledger, Feed, Timeline, Chips, Gutter |

**Desvio declarado:** o zip diferencia também a FORMA do controlo (GhostButton com borda em
GlassCards/Quotes/Bubbles/Chips vs. texto simples em Hairline/Paper/Ledger/Feed/Timeline/Gutter).
Isso **não** foi portado, e a razão é uma ordem POSTERIOR do dono sobre a barra de baixo —
*"os botoes tem que ficar mais claros, mais faceis de"* (recibo `_main/receipt-20261012-S2.md`
§1.1, onde o alfa do preenchimento subiu de 0.08 para 0.16 e o contraste medido de 7.18:1 para
12.90:1). Deixar 6 dos 10 com botões de texto transparente desfaria essa correcção. Os 10 ficam
com botão preenchido na paleta do seu design.

---

## 2. O GERADOR — e a correcção do registo (regra 10 da AGENTS.md)

**A premissa do brief estava errada, e medi-a antes de agir.** O `zipc-panels.css` **não era
gerado**: o próprio cabeçalho dizia `WHY AUTHORED AND NOT GENERATED`, e:

| medição | valor |
|---|---|
| `git log --diff-filter=A -- app/panel/themes/zipc-panels.css` | **1** commit (`0c25c4f`), e nenhum deles um gerador |
| `git grep -n zipc -- "*.py"` (antes deste trabalho) | **0** ocorrências |
| o único consumidor do ficheiro fora de `app/panel` | `_main/strip-float-oracle.js` (Z1-Z7), que o LÊ |

Não havia gerador nenhum para re-correr, portanto a prova da regra 10 ("uma corrida fresca
reproduz os bytes em disco") não tinha a que ser aplicada. **Fechei o buraco na mesma, e da forma
mais forte que existe:** escrevi `_main/_design-lane/gen_zipc.py` com DOIS perfis, e o perfil
`legacy` **reproduz o ficheiro publicado byte a byte ANTES de eu tocar em nada**:

```
py -3 _main/_design-lane/gen_zipc.py --profile legacy --out I:/cc-tmp/final-legacy.css
profile=legacy bytes=35875 sha256=9E32F9160C38B85555CBBFB81BC4F608560057BC4178F7DDC4AAF6716F29D76E
```

e o pin em disco (antes da reescrita) era
`9E32F9160C38B85555CBBFB81BC4F608560057BC4178F7DDC4AAF6716F29D76E` — **iguais**.
Ou seja: o gerador é FIEL ao que estava em disco, e a diferença entre `--profile legacy` e
`--profile designs` é exactamente o trabalho de design, não um acidente.

O ficheiro de produto **nunca foi editado à mão**: foi escrito por
`py -3 _main/_design-lane/gen_zipc.py --profile designs --out app/panel/themes/zipc-panels.css`.
O ARM H do portão §4 recusa qualquer edição manual: compara os bytes em disco com a saída fresca
do gerador.

---

## 3. D2 — O DIÁLOGO DE AFINAÇÃO DO DONO PASSA A ESTAR VIVO NOS 10

O `theme-tune.js` escreve **17 tokens** inline em `<html>` (`themeElement()` →
`document.documentElement`, `:477`; `apply()` → `el.style.setProperty`, `:594`). No ficheiro
publicado: `var()` = **0** e **0/17** tokens consumidos — o diálogo era decorativo nos 10.

Agora, **por design, medido no ficheiro em disco** (ARM B do portão):

```
170/170 design-token pairs live
```

Isto é 10 designs × 17 tokens, cada um DECLARADO no `:root[data-theme='X']` do próprio design e
CONSUMIDO com `var()` nas suas próprias regras. `var(` no ficheiro: **0 → 701**.

A correspondência semântica, que é o que faz o controlo fazer sentido:

| token do diálogo | papel no painel | onde é consumido |
|---|---|---|
| `--size-caption`, `--leading-caption`, `--weight-caption`, `--tracking-caption`, `--caption-upper` | a linha **em formação** (o rótulo do `theme-tune.js` diz "legenda ao vivo") | `.caption--latest .caption__text`, `.caption--provisional .caption__text` |
| `--size-closed`, `--leading-closed`, `--weight-closed` | a linha **fechada** (o rótulo diz "linha fechada") | `.caption__text` |
| `--text-secondary` / `--text-provisional` | texto confirmado / provisório | as mesmas regras |
| `--accent` (+ `--accent-soft`, `--theme-swatch`, `--line`, `--line-strong` — os 4 `colorKeys` do campo de cor) | destaque, bordas, o swatch do botão de tema | **215** consumos da família (`--accent` 127, `--accent-soft` 29, `--line` 37, `--line-strong` 12, `--theme-swatch` 10, este último em `.theme-button::after`) |
| `--bg-slab` / `--bg-slab-strong` | fundo do painel (base / topo) | o gradiente de `.panel` |
| `--radius-lg` | cantos do painel | `.panel`, `.captions__body`, os cartões |
| `--motion-in` | duração das transições | `.caption`, `.strip-button`, `.captions__body` |
| `--type-step` | digitação letra a letra | `.caption__ch` (`animation-delay`) |
| `--font-sans` | fonte do tema | `.panel`, `.caption__text`, chrome |

Cada design declara também a **ponte** para o espaço de nomes do `panel.css` (`--text`,
`--text-dim`, `--text-faint`, `--radius`, `--font`, `--mono`, `--accent-from`, `--accent-to`,
`--accent-gradient`, `--bg`), que é o mecanismo que as `theme-1..5.css` já usam.

### 3.1 O defeito que a reescrita apanhou e que ninguém tinha medido

`panel.css` anima `.caption` com `caption-in 220ms ease-out both` — e `both` faz o
`opacity: 1` do keyframe **continuar a ganhar** sobre qualquer `opacity` estático. O design 06
(Feed) é exactamente uma rampa de opacidade por recência: sem o corrigir, a rampa seria **inerte**
no browser apesar de estar no CSS. Os cinco temas do dono já recusam a animação
(`animation: none` em cada `theme-N.css`); os 10 designs fazem o mesmo e põem uma transição com
`var(--motion-in)` no lugar.

---

## 4. O PORTÃO, COM CONTROLO — `_main/zipc-designs-oracle.py`

Nada é lançado. 9 braços, todos medidos sobre os bytes em disco.

```
py -3 _main/zipc-designs-oracle.py
```

```
ZIPC-DESIGNS ORACLE -- PRISTINE (the bytes on disk)
  file: H:\sotto\app\panel\themes\zipc-panels.css
  72757 B, sha256 CB08DCA3AF1C4F22

  ok   A no two designs are structurally identical            min pairwise structural difference = 63 (>= 20), worst pair Paper vs Timeline
  ok   B every design consumes the 17 tune tokens             170/170 design-token pairs live
  ok   C every design carries its own zip identity marks      20/20 identity marks present in their own design
  ok   D no two designs declare the same selector sequence    10 distinct selector sequence(s) for 10 designs
  ok   E every design is built, not just recoloured           smallest structural fingerprint = 166 (>= 100)
  ok   F the marks that measured zero are back                every mark that measured 0 is back
  ok   G every selector member is rooted at a theme scope     0 leaked member(s), 0 unscoped block(s)
  ok   H the file is the generator's output, not a hand edit  the file IS the generator's output (72757 B, sha256 CB08DCA3AF1C4F22)
  ok   I every selector matches a node of the real panel DOM  397 selector(s), 0 that match NO node in panel.html

9 check(s), 0 failed
VERDICT: PASS
```

**O braço A é o que responde à queixa do dono.** A impressão digital de um design é o conjunto de
pares `(selector, propriedade)` mais `(selector, propriedade=valor)` para as propriedades
ESTRUTURAIS — e as cores ficam de fora de propósito (`background`, `border-color` não contam),
porque uma recoloração pura não pode passar por estrutura. Medido nos DOIS ficheiros:

| | impressão digital por design | diferença mínima entre um par | sequências distintas |
|---|---|---|---|
| **publicado** (`9E32F916…`) | 57, 58, 57, 57, 57, 57, 57, 58, 57, 58 | **0** (Timeline vs Gutter) | **1** de 10 |
| **agora** (`CB08DCA3…`) | 176, 171, 172, 166, 173, 182, 177, 175, 189, 176 | **63** (Paper vs Timeline) | **10** de 10 |

Ou seja: no ficheiro publicado havia um par de designs (Timeline e Gutter) que, tirada a cor, não
diferia em NADA. Agora o par mais parecido difere em 63 declarações estruturais.

### 4.1 O CONTROLO — o defeito injectado em CÓPIAS, e o portão fica VERMELHO

```
py -3 _main/zipc-designs-oracle.py --neg-arm
```

```
  CONTROL GREEN  failed=none

  PASS M1 the shipped file (one skeleton recoloured ten times)   want RED on A,B,C,D,E,F   got RED on A,B,C,D,E,F,H,I
  PASS M2 every var() consumed by a literal (the D2 defect)      want RED on B             got RED on B,H
  PASS M3 Paper loses the ruled page                             want RED on C             got RED on C,F,H
  PASS M4 Hairline's gutter collapses onto GlassCards' column    want RED on C             got RED on C,H
  PASS M5 Feed loses the recency ramp                            want RED on C             got RED on C,F,H
  PASS M6 a selector that matches no node in the panel           want RED on I             got RED on H,I

NEG-ARM VERDICT: PASS -- 6 mutant(s), 0 wrong, 0 inert, control GREEN
```

**M1 é o controlo que importa e não é sintético: são os bytes PUBLICADOS**, obtidos de
`gen_zipc.py --profile legacy`, ou seja o defeito real que o dono viu. Ele vai RED em A, B, C, D,
E e F — todos os braços que medem D1/D2 — e passa no G, que é exactamente o resultado que a
auditoria registou: o portão de scope estava VERDE enquanto os dez eram o mesmo desenho.

Os outros cinco mutantes provam que cada braço sabe dizer NÃO por si: M2 (tirar o `var()`) mata o
B; M3/M4/M5 matam o C cada um na sua marca; M6 (um selector com gralha) mata o I. Nenhum é inerte.

**Nota de rigor sobre M3/M5/M6:** eles caem também no H (deixam de ser a saída do gerador) e, no
caso de M3/M5, no F (as contagens globais das marcas descem). Não finjo que cada mutante falha
num braço só; o que afirmo, e está medido, é que cada um falha **no braço que lhe compete**.

### 4.2 O braço I reproduz, sozinho, o D5 da auditoria

O ARM I corre a lista de selectores contra o DOM real do `panel.html` num jsdom, com uma linha de
legenda construída como o `panel.js` a constrói (mais 18 linhas, para as regras
`:nth-child(4n+1)` e `:nth-last-child(n+13)` terem alvo) e com os estados de runtime
(`.status--live`, `.is-paused`, `#theme-button`) aplicados. Sobre o ficheiro PUBLICADO:

```
FAIL I every selector matches a node of the real panel DOM
       240 selector(s), 10 that match NO node in panel.html
       DEAD: .history__source | .history__source | ...
```

**10 selectores mortos, todos `.history__source`** — o mesmo número que a auditoria mediu no D5
(10 ocorrências em `zipc-panels.css`). Sobre o ficheiro novo: `397 selector(s), 0 that match NO node`.

---

## 5. OS OUTROS PORTÕES QUE JÁ EXISTIAM

| comando | resultado |
|---|---|
| `node _main/scope-leak-oracle.js` | **VERDICT PASS** — 9 folhas, 0 fugas; `zipc-panels.css preludes=336 at-rules=1 leaked=0 B=72757` |
| `node _main/scope-leak-oracle.js --neg-arm` | **NEG-ARM VERDICT PASS** — 4 mutantes, 4 RED, controlo GREEN, rc=0 |
| `node _main/strip-float-oracle.js` | 47 checks, **1 falha: Z5** — ver §6.1 |
| `node _main/theme-preview-oracle.js` | **FAIL** — pré-existente, alheia a mim — ver §6.2 |
| `node _main/three-overlays-oracle.js` | **FAIL** (2 checks) — pré-existente, alheia a mim — ver §6.2 |
| `node docs/design-intake/gap-oracle.mjs` | rc=0 (a matriz de nomes; não mede estrutura) |

**Sintaxe, com um parser a sério (css-tree, `H:/sotto/node_modules/css-tree`):**
`csstree.parse(css, {positions:true})` → **OK**; 338 regras, 1 412 declarações,
**0 propriedades desconhecidas**, e das 992 declarações não-custom **0 valores inválidos**
(as 545 que o lexer marca são todas `var(`, e o css-tree diz literalmente
`Matching for a tree with var() is not supported`). O ficheiro está em **CRLF (2 568) com 0 bare LF**.

---

## 6. O QUE **NÃO** FECHEI, E POR QUÊ

### 6.1 `strip-float-oracle.js` Z5 fica VERMELHO — o check fixa o defeito que o D2 remove

```js
const capSizes = (zipcCss.match(/\.caption__text\s*\{[^}]*font-size:\s*\d+px/g) || []).length;
add("Z5 each design declares its own caption size", capSizes >= 10, capSizes + " .caption__text font-size rules");
```

O Z5 exige um **px literal** dentro de `.caption__text`. A correcção do D2 é precisamente trocar
esse literal por `var(--size-closed)` / `var(--size-caption)` — sem isso o diálogo de afinação
continua morto. É o mesmo padrão que a `AGENTS.md` §9 já registou para
`canonical-producer-oracle.py`: *"those two arms used to PIN the defect, and went RED the moment it
was fixed"*.

**A intenção do Z5 continua satisfeita, e mais forte:** os 10 designs declaram cada um o SEU
tamanho (`--size-caption`: 34, 28, 33, 36, 31, 24, 30, 32, 32, 27 px — **9 valores distintos**, e
Timeline e Chips partilharem 32px é FIEL ao zip, `scenes.ts:581` e `:648`) e consomem-nos —
medido pelo ARM B (170/170). `_main/strip-float-oracle.js` **não está no meu escopo de escrita**, por isso
não o toquei. **Patch exacto para o Lead (1 linha):**

```js
const capSizes = (zipcCss.match(/\.caption__text\s*\{[^}]*font-size:\s*(?:\d+px|var\(--size-(?:closed|caption))/g) || []).length;
```

Não o fiz eu porque o brief fecha o escopo em 4 ficheiros, e um portão re-baselinado pela lane que
está a ser julgada pelo portão não vale nada.

### 6.2 Dois portões já estavam VERMELHOS antes de eu escrever, e a causa não é minha

`theme-preview-oracle.js ARM14.1` e `three-overlays-oracle.js D1/D6` falham porque
**`#strip-theme-button` deixou de existir no markup**:

```
FAIL ARM14.1 panel.html still ships #strip-theme-button (the cycler stays) — absent from markup
FAIL D1 the strip carries the bare-minimum button set   strip-theme-button,strip-font-smaller-button,strip-font-larger-button
```

O check é `/id="strip-theme-button"/.test(htmlBytes)` sobre `panel.html`. Medi: em `panel.html`
há **4** ocorrências de `strip-theme-button` e **todas as 4 são comentários/prosa**
(linhas 278, 630, 690, 699); nenhuma é `id="strip-theme-button"`. O ficheiro foi movido por uma
lane irmã às **00:40:11Z**, e o meu único ficheiro de produto foi escrito às **00:46:47Z** — e é
CSS de 10 temas, que não pode apagar um botão do markup. Não é regressão minha.

### 6.3 NÃO MEDIDO — nada foi pintado, e digo-o com o instrumento

**Não há uma única medição de pintura neste recibo.** A ordem dura da lane proíbe lançar o
browser/app/shell, e o `sotto_webview.py` está a ser editado por lanes irmãs. Tudo o que afirmo
sobre o que o dono VÊ é derivado de: parse de bytes (o meu), css-tree (sintaxe e valores),
jsdom (os selectores casam com o DOM real) e aritmética. **A equivalência visual design-a-design
continua NÃO MEDIDA** — o que está medido é a estrutura, os selectores, as propriedades e os
tokens.

Em particular, ficam **não verificados no browser**:

* que o `backdrop-filter` dos designs 01/04/06/07/09 produza o vidro fosco visível (blura o fundo
  do PRÓPRIO painel dentro da página; o desktop atrás da janela continua fora de alcance, e é por
  isso que o alfa das superfícies é o do `panel-designs.css`);
* que a rampa de opacidade do Feed leia como "log que desvanece" e não como "texto apagado" —
  o piso de 0.14 é o do zip (`PanelSetB.tsx:65`), mas o zip tem 6-8 linhas e o painel guarda
  `MAX_CAPTIONS = 200` (`panel.js`), portanto a rampa tem 12 degraus úteis e um piso;
* o alinhamento ao pixel da espinha do Timeline (calculei `left: 69.5px` para o centro da calha
  entre as colunas de 52px e o `gap` de 16px, com o `padding: 10px` do `.captions__list`);
* o `line-height: var(--leading-closed)` = 2.16 do Paper cair exactamente em cima da pauta de
  27px com a fonte real (Fraunces a 12.5px) — a aritmética dá 27.0px exatos, mas quem pinta a
  baseline é o motor de fontes;
* o contraste dos textos de cada design sobre as novas superfícies (o `Paper` e o `Gutter` são
  páginas CLARAS com `color-scheme: light`; o resto é escuro).

O comando exacto para o Lead fechar isto (só o Lead lança):

```
cmd /c app\webview\run.cmd --show
```

e depois escolher os 10 temas no picker; para o controlo do loader diferido,
`--no-lazy` (o braço de controlo que o `sotto_webview.py:4303` já nomeia).

### 6.4 Duas coisas que decidi e que o Lead pode querer reverter

1. **O tamanho da legenda.** No ficheiro publicado, `.caption__text` era **34px em TODAS as
   linhas** — mas 34px é o `captionSize` do `scenes.ts`, que o zip usa no `CaptionStage`
   (o overlay, que é do `caption-float.js`), não na lista do painel, onde o zip escreve
   `text-[13px]` (`PanelSetA.tsx:106`). Traduzi para a arquitectura que os temas do dono já usam:
   `--size-caption` (34px etc.) na linha EM FORMAÇÃO e `--size-closed` (13px etc., o valor do zip)
   nas linhas fechadas. Fica fiel ao zip e faz os DOIS controlos de tamanho do diálogo viverem.
   Se o dono preferir 34px em tudo, é uma linha no `STRUCT` do gerador.
2. **O Feed fica em minúsculas.** O zip pede `transform: "lowercase"` no caption da cena
   `lampblack` (`scenes.ts:451`), e eu consumo-o como `--caption-upper: lowercase`. É a
   assinatura do design e é ajustável no diálogo; se soar a defeito no ecrã, o valor está no
   `STRUCT` do gerador.

### 6.5 O que continua ABERTO do relatório da auditoria, e não era desta lane

D3 (100 declarações sem leitor nos 25 `cine-*`), D4 (3 itálicos sintetizados), D5 (as 42
referências de classe mortas — das quais as 10 `.history__source` do zipc **desapareceram**
com esta reescrita, porque os selectores agora casam), D6, D7 e D8: **intocados**. O D5 nos outros
ficheiros continua aberto e o meu ARM I é reutilizável para o medir (`--file`).

---

## 7. PINOS (regra 2 — tamanho, fim de linha, sha256, mtime)

| ficheiro | bytes | CRLF / bare LF | sha256 (16) | mtime (UTC) | quem |
|---|---|---|---|---|---|
| `app/panel/themes/zipc-panels.css` | 72 757 | 2 568 / 0 | `CB08DCA3AF1C4F22…` | 2026-10-13T00:46:47Z | **eu** |
| `_main/_design-lane/gen_zipc.py` | 71 239 | (py) | — | 2026-10-13T00:46:47Z | **eu (novo)** |
| `_main/zipc-designs-oracle.py` | 22 785 | (py) | — | 2026-10-13T00:52:19Z | **eu (novo)** |
| `app/panel/themes/zipc-panels.css` **antes** | 35 875 | 1 234 / 0 | `9E32F9160C38B855…` | 2026-10-12T16:37:22Z | — |
| `app/panel/panel.css` | 118 985 | — | — | 2026-10-13T00:33:54Z | lane irmã |
| `app/panel/panel.html` | 69 730 | — | — | 2026-10-13T00:40:11Z | lane irmã |
| `app/panel/panel.js` | 153 765 | — | — | 2026-10-13T00:14:09Z | lane irmã |
| `app/panel/caption-float.js` | 16 614 | — | — | 2026-10-13T00:22:23Z | lane irmã |
| `app/panel/themes/fonts.css` | 29 571 | — | — | 2026-10-13T00:15:03Z | lane irmã |
| `app/panel/themes/cinematic.css` | 312 230 | — | — | 2026-10-11T21:27:24Z | não movido |
| `app/panel/themes/panel-designs.css` | 128 716 | — | — | 2026-10-11T22:59:40Z | não movido |

As mtimes das linhas "lane irmã" são **anteriores** à minha escrita das 00:46:47Z, e nenhuma
delas foi tocada por mim. Nenhum `git add`, `commit` ou `push` foi corrido — o Lead faz.

---

## 8. COMANDOS, TODOS RE-EXECUTÁVEIS, NENHUM LANÇA NADA

```
$env:TMPDIR = 'I:/cc-tmp'

# a prova do gerador (regra 10) -- tem de dar 9E32F9160C38B855...
py -3 _main/_design-lane/gen_zipc.py --profile legacy --out I:/cc-tmp/final-legacy.css

# o portão, nos dois sentidos
py -3 _main/zipc-designs-oracle.py
py -3 _main/zipc-designs-oracle.py --neg-arm

# o portão contra o ficheiro PUBLICADO (8 de 9 braços RED)
py -3 _main/_design-lane/gen_zipc.py --profile legacy --out I:/cc-tmp/legacy.css
py -3 _main/zipc-designs-oracle.py --file I:/cc-tmp/legacy.css

# os portões que já existiam
node _main/scope-leak-oracle.js
node _main/scope-leak-oracle.js --neg-arm
node _main/strip-float-oracle.js

# sintaxe com um parser a sério
node I:/cc-tmp/css-parse-check2.js

# regenerar o produto (o Lead, se quiser)
py -3 _main/_design-lane/gen_zipc.py --profile designs --out app/panel/themes/zipc-panels.css
```

*Fim do recibo.*
