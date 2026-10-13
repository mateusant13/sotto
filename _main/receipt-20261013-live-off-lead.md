# RECIBO — a legenda arranca DESLIGADA e o botão `live` é o dono dela (2026-10-13)

**Lead.** Escopo de escrita: `app/panel/panel.{html,js,css}`, `app/panel/caption-float.js`,
os seis oráculos re-baselinados (por uma lane), e este recibo.

---

## 1. A decisão que o dono mandou eu ir buscar aos prompts dele

Perguntei-lhe (turno 1) se o `live` devia arrancar ligado (a legenda aparece logo no Alt+C) ou
desligado (a faixa fina primeiro, e o clique liga a legenda). Ele respondeu:
*"'Uma decisão que ficou por tua conta' já respondi nos meus prompts aqui do deepseek harness,
onde estamos. veja na nossa conversa, ou na conversa que começa com 'continue. aqui o handoff:'"*.

Fui buscá-la. A conversa é `session-b4dd3d3d` (`.dsh/sessions/--H-sotto--`, título
`"continue. aqui o handoff: Handoff"`), e o dono responde nas mensagens dele, verbatim:

> **[handoff, msg 25]** *"é pra existir 3 'overlays'. primeiro, o painel de baixo. **nele eu
> ativo o segundo overlay**, q é a legenda independente."*
> **[handoff, msg 20]** *"e ele tem um botao de linhar a legenda, que **liga ela NA TELA**, igual
> um overlay, EXATAMENTE IGUAL os .zip fazem."*
> **[handoff, msg 29]** *"o botao de mostrar a legenda ao vivo deve ser o 'live'. e deve ser
> CLARO quando ta live e quando nao ta."*

O painel de baixo é o overlay 1 e a legenda é o overlay 2, **ACTIVADO a partir dele**. Portanto:
o `live` arranca **DESLIGADO**, a faixa abre fina, e o clique põe a legenda na tela.

**Como o encontrei** (fica escrito porque o instrumento foi reaproveitável): as sessões estão em
`C:\Users\Administrador\.dsh\sessions\<workspace>\<id>\session.v4.jsonl.zstd`, que é uma
**sequência de frames zstd concatenados** — `zlib.zstdDecompressSync` só lê o PRIMEIRO (189 B de
um ficheiro de 1,3 MB, o que me enganou à primeira). O CLI `H:\msys64\mingw64\bin\zstd.exe -dc`
lê-os todos; e `.dsh/storages/session_projcache/sessions/<id>.json` guarda o TÍTULO sem
compressão, que é como localizei a conversa certa num grep.

---

## 2. O ACHADO GRAVE: o meu trabalho do turno 1 e 2 tinha sido DESCARTADO

Antes de escrever uma linha, medi o chão:

| ficheiro | o que eu tinha deixado (turno 2) | o que estava lá |
|---|---|---|
| `app/panel/panel.css` | faixa reta (`border-radius: 0`, plana, hairline) | **`border-radius: 10px`**, gradiente, 4 lados |
| `app/panel/panel.html` | "Linhar" apagado | **`#strip-float-button` de volta** |
| `app/panel/panel.js` | `applyFloat(liveEnabled)`, sem `paintFloatState` | **contrato antigo inteiro** |
| `app/panel/caption-float.js` | comentários atualizados | versão original |

**Outra lane trabalha na mesma branch e reverteu `app/panel/`** (a árvore estava igual a
`e36a09b`; e `e72e785 — "THE STRIP DRAG WORKS"` commitou `panel.html` já revertido, movendo o
script do arrasto inline para `app/panel/strip-drag.js` por causa do CSP). **Os meus ficheiros
nunca estavam commitados, portanto um `git checkout` de caminho apagou-os.** Os oráculos de
`_main` sobreviveram (ficaram ` M`), o que é a razão pela qual `strip-float-oracle.js` e
`three-overlays-oracle.js` **passavam com o painel ANTIGO**: eles fixavam o contrato NOVO e o
produto era que estava velho.

**Lição, e é o que este recibo existe para registar: quem escreve em `app/panel` tem de
COMMITAR. Um working tree partilhado por várias lanes não é um lugar onde trabalho não commitado
sobrevive.**

---

## 3. O que re-apliquei (e desta vez commitado)

1. `panel.html`: `#strip-float-button` apagado; `#strip-live-button` com
   `aria-pressed="false"` e o título/aria-label a dizer o que o clique faz.
2. `panel.js`: `applyLiveEnabled` termina em `applyFloat(liveEnabled)`; `dom.stripFloatButton`,
   `paintFloatState()` e `toggleFloat()` removidos; `applyFloat` só chama a shell quando
   `currentSurface() === 'strip'`; **`let liveEnabled = false`** com o porquê no comentário; e a
   palavra do estado OFF no mostrador passou de `'Live off'` para `'Captions off'` (a
   transcrição NÃO pára — dizer "Live off" lia-se como "o motor parou").
3. `panel.css`: `order` da linha (brand 0 · grip 1 · live 2 · open 3 · **pause 4 · hide 5** ·
   state 99), regras `.strip-button--float` apagadas, e a faixa: `border-radius: 0`,
   `border: 0` + hairline em cima e em baixo, fundo plano `rgba(11,15,20,0.98)`.
4. `caption-float.js`: comentários a nomear o botão `live` (deixaram de citar o botão removido).

---

## 4. MEDIDO

### 4.1 O contrato, em jsdom com os 12 módulos REAIS — `node I:\cc-tmp\live-smoke.js`

```
strip-live-button present: true
strip-float-button present: false
initial        pressed=false body[data-float]=off --strip-height=40px     <-- a FAIXA FINA
after click 1  pressed=true  body[data-float]=on  --strip-height=220px    <-- a legenda NA TELA
after click 2  pressed=false body[data-float]=off --strip-height=40px
captionFloat on=false
SCRIPT ERRORS: none
```

### 4.2 A cascata real da faixa — `node I:\cc-tmp\strip-css.js`

```
strip .panel border-radius = 0px
strip .panel border-top-width = medium / border-left-width = 0px
strip .panel background-image = none
strip .panel background-color = rgba(11, 15, 20, 0.98)
live order = 2   pause order = 4   hide order = 5
```

### 4.3 Portões (corridos por mim, sobre os bytes congelados)

```
node _main/instruments-battery.mjs   -> SUMMARY: 89/89 instrument(s) rc=0; failed=0; launches=0

node _main/strip-float-oracle.js        -> VERDICT: PASS      (neg-arm: M7 "the straight band
                                           gets its rounded pill corners back" RED)
node _main/three-overlays-oracle.js     -> VERDICT: PASS      (neg-arm: N9 "the LIVE button no
                                           longer drives the caption" RED, N10 RED)
node _main/botoes-lane-oracle.js        -> VERDICT: PASS      (neg-arm: M8 "the removed Linhar
                                           button comes back" RED)
node _main/_s2-bar-dom-oracle.js        -> VERDICT: PASS      (neg-arm: PASS, todos RED)
node _main/caption-independent-oracle.js-> VERDICT: PASS      (neg-arm: PASS, todos RED)
node _main/_panel2-dom-probe.js         -> RESULT: GREEN — 83/83 arm(s)
py -3 _main/strip-geometry-oracle.py    -> VERDICT: PASS -- 17 check(s), 0 fail
py -3 _main/zipc-designs-oracle.py      -> VERDICT: PASS      (9 checks, 0 failed)
py -3 _main/cinematic-designs-oracle.py -> VERDICT: PASS      (6 checks, 0 failed)
py -3 _main/cine-themes-oracle.py       -> VERDICT: PASS      (20 checks, 0 failed)
py -3 _main/base-themes-oracle.py       -> VERDICT: PASS      (2 tokens OPEN, declarados)
```

---

## 5. NÃO MEDIDO / não fechado

1. **Nenhuma tecla Alt+C real foi premida e nenhum pixel desta versão foi lido por mim.** O que
   está medido é o contrato em jsdom, a cascata em jsdom e a bateria estática. O
   `panel-paint-probe.py` não foi corrido nesta ronda.
2. **"os botoes, todos iguais" do turno 1 CONTINUA POR FAZER** — a lane dos geradores que o
   tinha entregue foi apagada com o resto. Medido agora, o painel ainda tem por design:
   `cinematic.css` 21 regras `.panel__controls`, `zipc-panels.css` 10,
   `panel-designs.css` 5, `theme-{1..5}.css` 1 cada, e `cinematic.css` 25
   `body[data-surface='strip'] .stripbar { justify-content }`. Referi-lo aqui em vez de o
   silenciar: o dono pediu-o e ele NÃO está no produto.
3. A fidelidade design-a-design continua sem instrumento de comparação com o mockup (outra lane
   está nisso: `receipt-20261013-zip-mockup-render.md`).
