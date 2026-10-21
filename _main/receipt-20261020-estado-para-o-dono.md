# O QUE EU ESTOU A FAZER AGORA, E O QUE FALTA

**Para o dono — 2026-10-20, ~19:40.**
Escrito pelo Lead. Os números aqui são medidos, não lembrados.
Regra do repo: *"um grep é uma afirmação com prazo de validade"* — por isso
tudo o que está escrito abaixo foi **medido hoje**, e o que não foi medido
está marcado como tal.

---

## 0. O RESUMO EM 10 LINHAS

1. A **app do dono fechou-se** (tray-quit, `rc=0`, 12:13:45) — não a matei.
2. O bloco da **legenda** (palavras inteiras + fora do painel + display YouTube)
   está **implementado e medido**, à espera de **commit**.
3. Encontrei e corrigi um **defeito meu** hoje: o corte da palavra a cresc er
   também apagava a última palavra de uma legenda **já fechada**. Portão apanhou.
4. Os **designs** foram medidos: **4 regras** explicam porque truncam.
5. O **design mais importante** ficou por aplicar: a legenda viva é desenhada
   pelo **renderer NATIVO** (GDI+), não pelo `caption.html`. O CSS que o
   subagent arrumou **não chega ao ecrã do dono**. Isto é o achado mais
   importante do dia e está detalhado em §4.
6. **Baterias**: a principal e a 2ª estão verdes **antes** deste bloco.
7. **Disco I: a 0,45 % livre** — risco de ENOSPC.
8. **751 entradas alheias** staged, intactas — decisão do dono.

---

## 1. O QUE MUDEI HORA (nesta sessão, depois do último commit)

### 1.1 Um defeito MEU, encontrado e corrigido hoje

**O que era.** Ontem introduzi o "hold-back": a última palavra da linha em
formação é **retida** até duas hipóteses consecutivas concordarem nela
(LocalAgreement-2), porque o dono pediu *"só palavras inteiras"*.

**O defeito.** O hold-back era aplicado a **toda** linha em formação — inclusive
a uma linha que o worker já **FECHOU** (`meta.final === true`). Numa linha
fechada a última palavra **já é inteira** e nunca mais muda. Resultado: a tela
mostrava uma frase **sem a última palavra**.

**Prova.** `_main/caption-independent-oracle.js` ARM A18, nos bytes enviados:

```
real="quixotescamente uma"   want="quixotescamente uma linha"
```

**A correcção.** O **motor** é quem sabe se a linha está fechada
(`meta.final`), e `state()` é a janela pública dele. O painel passa a ler
essa resposta em vez de adivinhar pelo nome da fonte:

| ficheiro | o que mudou |
|---|---|
| `app/panel/caption-formulation.js` | novo `tailClosed` (diz se o fragmento actual fechou a linha) + exposto em `state()` |
| `app/panel/panel.js` | `renderProvisional` só retém a palavra quando a linha **ainda está a crescer** |

**Nota sobre `tailClosed`:** **não** é o `bufferFinal` pegajoso do motor (esse
sobrevive até o buffer ser drenado e responde a outra pergunta). `tailClosed` é
do **fragmento que produziu a hipótese que está no ecrã agora**.

**Medido depois:** **57 checks, 0 failed — VERDICT: PASS.**

### 1.2 A regra do `data-float` (o que a tela reserva)

A página escrevia `documentElement[data-float]` a seguir ao **interruptor** do
módulo. Mas o **shell** lê esse atributo para **dimensionar a barra**
(`sotto_webview.py:6527` e `:6579`) — e a barra não deve reservar altura para
uma legenda que **não está pintada**.

Agora o atributo segue **o que está pintado** (`want`), não o interruptor.

**Prova (mutante N11):** voltar ao interruptor faz a arm **A23** ir a vermelho.
E o mutante **N6** (a shell não vê o estado) também é re-ancorado e morre:
a âncora antiga (`on ? 'on' : 'off'`) tinha desaparecido com a minha mudança e
o braço negativo morria com *"SETUP ERROR: mutant anchor absent"* — um
instrumento **partido**, não um vermelho.

**Estado medido do braço negativo:** **11/11 mutantes vermelhos** —
N1 N2 N3 N4 N5 N6 **N11** N7 N8 N9 N10. **NEG-ARM VERDICT: PASS.**

---

## 2. A LISTA COMPLETA (todo list)

| # | Tarefa | Estado | Prova / número |
|---|---|---|---|
| 1 | **Áudio**: o vídeo do YouTube que tocava sem parar | **FEITO** | renderer morto isolado; **peak 0,000000** em todos os endpoints de render; zero sessões de áudio do Chrome |
| 2 | **Correcção da protecção de render** do painel + portões | **FEITO** (commit `d7dd9be`) | Blink medido: painel `rgba(11,15,20,0.98)` nos 3 estados; portão novo 9/9; 2ª bateria 145/145 |
| 3 | **Legenda só com palavras inteiras** (Nemotron + YouTube) | **EM CURSO — implementada, à espera de commit** | typewriter aposentado (1 nó de texto por palavra); hold-back corrigido hoje; probe 94/94; oráculo 57/57 |
| 4 | **Legenda com o aspecto do YouTube** (quebra de linhas, display) | **EM CURSO — CSS pronto, MAS não chega ao ecrã** | ver §4 — o renderer vivo é **nativo** |
| 5 | **Legenda ao vivo DENTRO do painel** | **EM CURSO —implementado, à espera de commit** | `shouldPaint` passa a falso com `data-caption-window` presente; arm A22/A23 novas |
| 6 | **Designs que truncam / fora de encaixe** | **MEDIDO — aplicação pendente** | 4 regras, 45 designs medidos; 100 prints das 50 demos |
| 7 | **751 entradas staged alheias** | **ESPERANDO DECISÃO DO DONO** | intactas, 0SEP |
| 8 | **Relançar a app** para a correcção de CSS/HTML entrar em vigor | **PENDENTE — só o dono** | a app atual corre com os bytes antigos em memória |

---

## 3. O BLOCO QUE ESTÁ PRONTO A SER COMMITADO

Ficheiros (todos medidos, EOL preservado):

| ficheiro | B | EOL | o que |
|---|---|---|---|
| `app/panel/panel.js` | 185710 | CRLF 3691 / bareLF 0 | palavras inteiras (1 nó de texto), hold-back corrigido, `tailClosed` |
| `app/panel/panel.css` | 161051 | CRLF 3761 / bareLF 0 | revelo por **palavra** (o typewriter foi aposentado) |
| `app/panel/caption-float.js` | 20366 | CRLF 450 / bareLF 0 | `shouldPaint` + `data-float` segue o que é pintado |
| `app/panel/caption-formulation.js` | 51172 | CRLF 1063 / bareLF 0 | `tailClosed` exposto |
| `app/panel/zip-overlay.css` | 30415 | CRLF 545 / bareLF 0 | legenda some do painel com "on" **e** com "off" |
| `app/panel/caption.html` | 15383 | **LF** | display do YouTube (subagent) |
| `app/panel/caption-float.css` | 13814 | CRLF 268 / bareLF 0 | tokens + regras do documento da legenda (subagent) |
| `app/webview/youtube_captions.py` | 74300 | **LF** 1803 | `_join_segs` preserva a quebra de linha do cue |
| `_main/_panel2-dom-probe.js` | 64822 | CRLF 1104 / bareLF 0 | re-ancorado (GREEN 94/94) |
| `_main/_panel2-dom-neg-control.js` | 5937 | **LF** 143 | +3 mutantes (6/6 vermelhos) |
| `_main/caption-independent-oracle.js` | — | **LF** | +A22, +A23, +A23b, N6 re-ancorado, N11 novo |

**Portões verdes (medidos hoje):**
- `node _main/caption-independent-oracle.js` → **57 checks, 0 failed**
- `node _main/caption-independent-oracle.js --neg-arm` → **11/11 vermelhos**
- `node _main/_panel2-dom-probe.js` → **94/94 GREEN**
- `node _main/_panel2-dom-neg-control.js` → **6/6 vermelhos**

**Ainda por correr antes do commit:** a bateria principal (85 passos) e a 2ª
bateria (145), porque `panel.js` e `caption-formulation.js` mudaram.

---

## 4. O ACHADO MAIS IMPORTANTE DO DIA — E O QUE FALTA DE VERDADE

O dono pediu, verbatim:

> *"voce nao ta fazendo a legenda parecendo com como o youtube da DISPLAY e
> quebra as linhas e etc. é pra tu fazer isso."*

O subagent fez o trabalho de CSS **e mediu o resultado** (Blink, 900×170):

| | antes | depois |
|---|---|---|
| tipo de letra | Georgia serif | **Inter**, peso 500 |
| tamanho | 21,75 px | **36 px** |
| cor | `rgb(245,248,252)` | **`rgb(255,255,255)`** |
| contorno | 2 px @ 85 % | **6 px preto** |
| alinhamento | esquerda, pior glifo **387 px** fora do centro | **centro, 0,00 px** |
| 2 linhas | equilíbrio 0,959 | **0,178** |
| palavra partida | `break-word` + `hyphens:auto` | **`normal` + `none` — 0 palavras partidas** |

**E depois descobriu o que ninguém lhe disse:**

> **`caption.html` NÃO É CARREGADA POR NENHUMA JANELA.**
> `sotto_webview.py:69` define `CAPTION_HTML` — e há **1 ocorrência**: a
> definição. O único `webview.create_window` é o do painel (`:5805`).
> `sotto_webview.py:5885` diz: *"THE FLOATING CAPTION IS A NATIVE LAYERED
> WINDOW, NOT A WEBVIEW2"*.

**Consequência honesta:** o CSS que o subagent arrumou está **correto e
medido**, mas **não aparece no ecrã do dono**. A legenda que ele vê é
desenhada por `app/webview/caption_overlay.py` (GDI+).

**Medido no renderer nativo (o que o dono vê hoje):**
- Segoe UI **Bold** 34 px, caneta preta de 6 px (3 px visível), já **centrado**
- as duas linhas: **532,5 px vs 329,3 px** (equilíbrio **0,382** — desequilibrado)
- `wrap_tail` **rola 21 caracteres para fora** ⇒ **perde-se o meio da frase**

**Portanto, o que falta de verdade:**
1. O **"quebra as linhas como o YouTube"** tem de ser feito no renderer
   **NATIVO** (`caption_overlay.py` + `caption_wrap.py`), não no CSS.
2. **"Palavras inteiras"** também tem de valer no caminho nativo — é lá que a
   palavra está a ser cortada.
3. O `caption.html`/`caption-float.css` ficam como o **fallback** (o host sem
   janela de legenda), e é lá que a correcção faz sentido.

Isto **não** é o subagent a falhar: é o subagent a medir a coisa certa e a dizer
que o ecrã dele não é o ecrã do dono. A acção é minha.

---

## 5. OS DESIGNS — O QUE FOI MEDIDO, O QUE FALTA

Subagent **perdido** (a sessão caiu), mas deixou o trabalho **completo** em
disco: recibo, instrumentos e 372 ficheiros de prova
(`docs/design-intake/`, 93,7 MB).

### 5.1 As 4 regras (com números)

**REGRA 1 — o tamanho da linha viva foi copiado do palco CENTRAL, não do painel de 380 px.**
O zip tem **dois** componentes de legenda: o do **palco central**
(`Caption.tsx`, `clamp(30px,4.6vw,54px)`) e o do **painel lateral**
(`Panel.tsx`, `text-[18.5px]`). O gerador leu o **primeiro** para a linha viva.

| theme | o painel do zip | o produto | razão |
|---|---|---|---|
| theme-1 (tele) | 18,5 px | **30 px** | **1,62×** |
| theme-2 (bcast) | 10,5 px | **18 px** | **1,71×** |
| theme-3 (mano) | 14,5 px | **21 px** | **1,45×** |
| theme-4 (cine) | 15 px | **24 px** | **1,60×** |
| theme-5 (inst) | 14,5 px | **24 px** | **1,66×** |

O `vw` é a armadilha: calibrado para um palco de 1280–1920 px, a 380 px o
`4.6vw` dá 17,5 px ⇒ o **piso** do `clamp` ganha ⇒ o tamanho **mínimo** que a
legenda central alguma vez teve, numa coluna 2–3× mais estreita.

**REGRA 2 — a coluna do produto é mais estreita que a de todas as demos.**
A linha é uma grelha com uma coluna de **hora** que não encolhe: **54 px** +
**10 px** de gap ⇒ sobra **205–292 px** de texto. As demos: **272 px** (zip A),
**300–348 px** (zip E), **350–414 px** (zip C).

**REGRA 3 — o produto corta palavras ao meio; as demos nunca.**
`panel.css:1324-1325` — `.caption__text { overflow-wrap: break-word;
hyphens: auto; }`. Cada demo constrói a legenda **palavra a palavra** com
`white-space: pre` — uma palavra nunca é partida.

**REGRA 4 — os painéis das demos não têm 380 px.**
zip4: 350, 352, 366, 372, 378, **384**, **388**, **396**, **400**, **414** px.
zip5: 356–392 px. Cinco dos dez do zip4 são **MAIS LARGO** que a coluna onde
têm de viver. E os sheets gerados **não carregam a largura** (medido: **0**
tokens de largura).

### 5.2 O que falta aplicar

1. **`_main/_design-lane/gen_themes.py:832-838`** — ler a linha viva do
   **Panel.tsx**, não do Caption.tsx. Valores: 18,5 / 10,5 / 14,5 / 15 / 14,5 px.
   (E o `caption_upper` do theme-1 passa a `none`: o painel lateral não
   maiúscula; o palco central sim.)
2. **`app/panel/panel.css:1269-1325`** — dar o espaço de volta à coluna de
   texto (a hora por cima da linha, ou na calha).
3. **A largura do design** — o gerador tem de emitir a largura e o painel tem
   de a respeitar.
4. **`app/panel/panel.css:3339-3346`** — a linha da janela da legenda está
   **hardcoded ao theme-5** (Instrumento): `clamp(24px,3.1vw,42px)` **é** o
   `--size-caption` do theme-5. Passar a ler `var(--size-caption)`.
5. **`app/panel/caption.html`** — carregar o manifesto e os sheets dos temas e
   seguir o tema escolhido.

---

## 6. PORTÕES, BATERIAS E O ESTADO DO REPO

| portão | estado | quando |
|---|---|---|
| `caption-independent-oracle.js` | **57/57, 0 failed** | hoje |
| `caption-independent-oracle.js --neg-arm` | **11/11 vermelhos** | hoje |
| `_panel2-dom-probe.js` | **94/94 GREEN** | hoje |
| `_panel2-dom-neg-control.js` | **6/6 vermelhos** | hoje |
| `caption-doc-scope-blink.py` | 9 checks, 0 failed | commit `d7dd9be` |
| `_gitattributes-verify.py` | 2300 ficheiros, **0 divergentes** | commit `d7dd9be` |
| bateria principal (85 passos) | GREEN WITH 1 SKIPPED | commit `d7dd9be` — **a correr de novo** |
| 2ª bateria (145) | **145/145, launches=0** | commit `d7dd9be` — **a correr de novo** |

**Repo:** HEAD = `d7dd9be`, branch `feat/speaker-attribution-20261019`,
**upstream 0/0** (nada por push). **751 entradas alheias** staged — **intactas**.

---

## 7. RISCOS E COISAS QUE NÃO MEDI

- **`I:` a 0,45 % livre** (16,9 GB de 3,726 TB). Os ficheiros grandes
  (`aud.csv` 9,1 GB, `rs-liveness.sqlite` 3,2 GB) **não são meus** — não toco.
  Uma lane pode morrer com ENOSPC.
- **A app do dono tem de ser RELANÇADA** para a correcção de CSS/HTML entrar em
  vigor (o CSS é servido em cada arranque). **Não reliancei a app dele.**
- **Não medido**: o que está exactamente no CABLE (exigia um 2.º grabador no
  dispositivo do dono); se o vídeo dele está routed para o CABLE.
- **Erro meu a reportar**: na primeira tentativa de matar o renderer do vídeo
  matei o renderer de **outro** Chrome (o de debug) por falta de filtro de
  árvore. Com o filtro correcto, o renderer do vídeo foi morto isolado e o
  Chrome do dono ficou intacto.

---

## 8. O QUE EU VOU FAZER A SEGUIR (sem depender do dono)

1. Correr a **bateria principal** e a **2ª bateria** com o bloco da legenda.
2. **Commitar** o bloco da legenda (com `SOTTO_SKIP_RUN_ALL=1` na mensagem, por
   causa das flakes de `app/shadowplay/`, que são de outro produto).
3. **Corrigir o renderer NATIVO** (`caption_overlay.py` + `caption_wrap.py`):
   quebra de linhas como o YouTube, e **palavras inteiras** no caminho que o
   dono vê. Com portão e braço negativo.
4. **Aplicar as 4 regras dos designs**, começando pelo `gen_themes.py` (que é
   o que fixa theme-1..5) e pela coluna de texto.
5. Push.

**E o que depende do dono:** relançar a app (para a ver), e decidir as 751
entradas staged.
