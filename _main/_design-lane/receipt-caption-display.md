# A legenda tem de parecer com o DISPLAY do YouTube

**Lane:** caption display · **Date:** 2026-10-20 · **Files owned and changed:**
`app/panel/caption.html`, `app/panel/caption-float.css` ·
**Instruments added:** `_main/_design-lane/caption-display-oracle.py`,
`_main/_design-lane/caption-display-shot.py`

## 0. A ordem, e a referência

O dono, 2026-10-20, verbatim:

> *"voce nao ta fazendo a legenda parecendo com como o youtube da DISPLAY e
> quebra as linhas e etc. é pra tu fazer isso. faça."*

A referência (o display do YouTube num video): texto **branco** com um
**contorno preto pesado** em volta dos glifos (NÃO uma placa de fundo), numa
**sans grande** (≈36 px a 1080p, peso medio), **centrado**, em **no maximo
duas linhas**, e a quebra entre as duas linhas cai numa **fronteira de
palavra** -- nunca dentro de uma palavra.

## 1. O VIEWPORT: O "CLAMP DE 492 px" NAO EXISTE PARA A LEGENDA

Este e o primeiro achado, e ele muda o que da para medir.

O AGENTS.md (regra 4) e o brief desta lane dizem que o headless Edge "prende" o
viewport de layout a 492 px, qualquer que seja o `--window-size`, e portanto
que uma medicao da legenda e uma medicao a 492 px. **Isso e FALSO para a
legenda**: o 492 px e um **MINIMO**, nao um maximo. Medido em
`I:/cc-tmp/vp-probe.py` (headless Edge 155.0.4283.62, `--dump-dom`, seis
pedidos, uma execucao):

| `--window-size` | viewport medido |
|---|---|
| 900x170 | **876** x 78 |
| **924x262** | **900 x 170**  <-- a janela da legenda |
| 1200x400 | 1176 x 308 |
| 492x300 | 492 x 208 |
| 380x900 | **492** x 808  <-- o PANEL: pede 380 e recebe 492, e o PNG e um CROP |
| 900x170, `--headless=old` | 876 x 78 |

Ou seja: `viewport_w = max(492, pedido_w - 24)` e `viewport_h = pedido_h - 92`.
O 492 aparece **so quando se pede menos** que 516 -- e e por isso que o painel
(e nao a legenda) e um crop de 492 px. Pedindo 924, a pagina da legenda tem
**900 x 170**, que e o tamanho real da janela (`sotto_webview.py:5881-5884`:
`cap_w = max(360, min(900, wa_w - 80))` = 900 numa area de trabalho de 1920,
`cap_h = 170`).

**Logo: a legenda PODE ser medida na largura real, num Blink real.** E o
instrumento faz exactamente isso (`--window-size=924,262`).

## 2. O DIAGNOSTICO, COM NUMEROS

### 2.1 O DOCUMENTO DA LEGENDA (os dois ficheiros desta lane)

Medido com o oraculo, sobre os bytes do HEAD (`--source=head`), viewport
900x170:

```
   V2   RED   colour rgb(245, 248, 252) (want white)
   V3   OK    outline 2px rgba(0, 0, 0, 0.85) (want >= 2px black)
   V4   OK    painted ancestors 0, html rgba(0, 0, 0, 0), body rgba(0, 0, 0, 0)
   V5   RED   font Georgia, "Times New Roman", serif / weight 700
   V6   RED   font-size 21.75px (want 36px)
   V7   RED   align left, block off by 11.00px, worst glyph off by 387.37px
   V10  RED   balance 0.959 (want <= 0.20)
   VERDICT: FAIL (red: V2,V5,V6,V7,V10)
```

E para a legenda longa, o `V8` tambem fica vermelho:

```
   V8   RED   4 line box(es): esta e uma legenda muito mais comprida do que | ...
```

Isto e, em numeros: **serif** (Georgia/Times), **21.75 px**, **flush a
esquerda** (a pior linha de glifos a 387.37 px do centro), cor
`rgb(245,248,252)`, contorno de 2 px a 85 %, e as duas linhas com **95.9 % de
diferenca** entre si (a primeira cheia, a segunda com tres palavras). A legenda
longa ocupava **4 linhas**.

De onde vinham: `zip-overlay.css` e a ULTIMA folha que a pagina carrega e
declara, com `!important`, o tipo do overlay -- "THE SERIF LINE", verbatim
(`zip-overlay.css:359-364`): `font-family: var(--font-serif, Georgia, ...)`
`!important`, `font-size: 1.45em !important` (1.45 x 15 px herdados = 21.75
px), `line-height: 1.28 !important`; e `text-align: left !important` na
coluna e nas duas linhas (`:285-292`). E `caption-float.css` trazia
`overflow-wrap: break-word` + `hyphens: auto`, que **partem palavras** (o
proprio screenshot do dono lia "communicatio / n").

### 2.2 A LEGENDA QUE O DONO VE DE FACTO -- E O BLOQUEIO

Isto tem de ser dito com todas as letras, porque e o que decide o valor
deste trabalho:

> **A legenda que esta no ecra do dono NAO e esta pagina. E o overlay NATIVO.**

- `app/webview/sotto_webview.py:5885-5891`, verbatim: *"THE FLOATING CAPTION
  IS A NATIVE LAYERED WINDOW, NOT A WEBVIEW2."* O shell cria
  `caption_overlay.NativeCaptionOverlay` (`:5905-5911`) e e esse objecto que
  recebe o texto (`push_caption_to_window` -> `ov.set_text(...)`, `:8646-8687`).
- `CAPTION_HTML` (`sotto_webview.py:69`) esta DEFINIDO E NAO E USADO POR NADA.
  Medido: `Select-String CAPTION_HTML app/webview/sotto_webview.py` -> **1
  ocorrencia** (a definicao); `webview.create_window` -> **1 ocorrencia**
  (`:5805`, a janela do painel). **Nenhuma janela carrega `caption.html`.**
- O overlay nativo desenha com GDI+: `GraphicsPath.AddString` + `Pen`
  (`:281-291`), `UpdateLayeredWindow` (`:502`), `WS_EX_LAYERED`
  (`:423`) -- sem WebView2, sem placa, alfa por pixel.

O que o overlay nativo faz hoje, medido (mesmo GDI+, sem abrir janela nem
audio: `caption_overlay._layout` + `caption_wrap`):

| propriedade | valor medido no overlay vivo | onde |
|---|---|---|
| face | **Segoe UI Bold** (peso 700) | `caption_overlay.py:268-269` |
| tamanho | **34 px** (`max(16, 34*scale)`) | `caption_overlay.py:266` |
| contorno | `Pen` preto de `max(2, 6*scale)` = **6 px**, desenhado **por baixo** do preenchimento -> **3 px visiveis** | `caption_overlay.py:287-290` |
| alinhamento | `StringAlignment.Center` | `caption_overlay.py:271-272` |
| orcamento | `budget_px(1920, 34px)` = **727.06 px** (o tecto de 42 caracteres e que aperta; a fracao BBC de 68 % daria 1305) | `caption_wrap.py:316-331` |
| quebra | `wrap` = `['e o que eu quero e que a', 'legenda apareca aqui em baixo,']` + overflow `'igual o youtube faz'` | `caption_wrap.py:204` |
| janela | `wrap_tail` mostra as **DUAS ULTIMAS** linhas e **ROLA** `'e o que eu quero e que a'` (21 caracteres) | `caption_wrap.py:270-313` |
| as duas linhas | **532.5 px** e **329.3 px** -> **balance 0.382** (38 % de diferenca) | medido com `Graphics.MeasureString` |

**O "quebra as linhas" que o dono acusa esta medido: 38 % de diferenca entre as
duas linhas**, e 21 caracteres do inicio da frase a rolarem para fora. O
overlay nativo JA tem texto branco, contorno preto pesado e centrado -- o
que lhe falta em relacao ao YouTube e o **equilibrio** das duas linhas, o
**peso medio** e a **sans**.

**O ORACULO TAMBEM VE O OVERLAY NATIVO?** Nao. Ele mede o documento. E o
documento, ate hoje, estava **muito mais longe** do display do YouTube do que
o overlay nativo: serif, 21.75 px, a esquerda, 4 linhas, 95.9 % de diferenca
entre as linhas. Esta lane corrigiu o documento (que e o que lhe cabe) e mediu
o overlay nativo (que nao lhe cabe) -- o mapa de portagem esta na secao 6.

## 3. A MUDANCA

Dois ficheiros, e **cada propriedade decidida em UM sitedo** (foi a primeira
versao que falhou o braco negativo: as duas folhas declaravam as mesmas
propriedades e a do `caption.html` sombreava a do `caption-float.css`, e sete
mutantes sobreviveram -- ver a secao 5).

### 3.1 `app/panel/caption-float.css` -- os NUMEROS e as propriedades que ninguem força

Tokens (a face, o tamanho, o peso, o interlinhamento e o contorno vivem aqui,
**uma vez**):

```css
:root {
  --caption-face: 'Inter', 'Segoe UI', system-ui, sans-serif;
  --caption-size: 36px;
  --caption-weight: 500;
  --caption-leading: 1.2;
  --caption-outline: 6px;
  --caption-prev-size: 26px;
  --caption-prev-outline: 4px;
}
```

- **A face:** Roboto nao esta empacotado. **Inter** esta
  (`fonts/inter-latin-{300,400,500,600}`) e e o seu gemeo de metricas: o mesmo
  esqueleto neo-grotesque, a mesma altura de x, o mesmo 500 "medio" que o
  YouTube usa.
- **O tamanho:** 36 px e o tamanho do YouTube a 1080p. **Nao** e um `vw`: a
  janela da legenda tem 900 px, e um `vw` mediria as palavras contra a CAIXA
  e nao contra o ecra que o dono esta a ver. `--caption-scale` (o botao de
  fonte do dono) continua a multiplicar.
- **O contorno:** `-webkit-text-stroke` centra o traço na borda do glifo, e
  `paint-order: stroke fill` pinta o branco POR CIMA da metade interior. Um
  traço de 6 px sao **3 px de preto visivel fora da letra**, e a letra
  mantem a forma. 6 px e a mesma caneta que o overlay nativo usa
  (`caption_overlay.py:287`).
- **A quebra:** `overflow-wrap: normal` + `hyphens: none` -- e isto que torna
  VERDADEIRA a frase "o texto nunca parte a meio de uma palavra": sem os dois,
  o navegador so pode partir num espaco.
- `text-wrap: balance` -- o que equilibra as duas linhas (Chromium desde o
  114; esta maquina corre Edge 155).
- As regras sao `html[data-caption-doc] #caption-float ...`: o marcador que so
  `caption.html` tem (medido: `data-caption-doc` aparece **apenas** em
  `caption.html`), portanto o overlay do PAINEL (o cartao serif do zip) nao e
  tocado.

### 3.2 `app/panel/caption.html` -- as CINCO propriedades que `zip-overlay.css` força

`zip-overlay.css` e a ultima folha e traz `!important`; so uma declaracao
**posterior** da mesma propriedade o vence. Estas cinco sao, portanto, decididas
aqui, com os mesmos tokens:

```css
html[data-caption-doc] body[data-float="on"] .caption-float__line {
  font-family: var(--caption-face) !important;
  font-size: calc(var(--caption-size) * var(--caption-scale)) !important;
  line-height: var(--caption-leading) !important;
  letter-spacing: 0 !important;
  text-align: center !important;
}
```

Mais: o **palco** passa a ter **um unico item** (a coluna do texto), o que
centra as palavras em **450.0 px** de uma janela de 900 px, para qualquer
largura de legenda (medido: `block off by 0.00px, worst glyph off by 0.00px`).

E o **ponto** (o ZIP transformou a barra de 4 px num ponto verde de 6 px,
`zip-overlay.css:260-263`) foi posto **dentro da coluna** e medido: como a
janela e de 900 px e a coluna e larga como a janela, um ponto na fila flex
ficava a **105 px** das palavras, na beira do ecra, a parecer um artefacto.
Agora ele e posto contra a **borda esquerda do texto renderizado** (16 px de
distancia) e centrado na **primeira linha viva** -- como o LED do overlay
nativo (`caption_overlay.py:303-309`, `cy = pad + h / 2`).

## 4. A REGRA DE QUEBRA DE LINHAS (a Implementacao)

1. **`overflow-wrap: normal` + `hyphens: none`** -- o navegador so parte num
   espaco. Uma palavra mais comprida do que a coluna **nao parte**: transborda
   e e cortada na borda (medido: 991.6 px de palavra numa coluna de 852 px), que
   e o mesmo intercambio que o YouTube faz. (E o que o dono viu como
   "communicatio / n" deixou de acontecer.)
2. **`text-wrap: balance`** -- as duas linhas ficam equilibradas: medido
   **0.178** de diferenca (a do overlay vivo e **0.382**).
3. **A JANELA QUE CORRE** (no script da propria pagina) -- no maximo duas
   linhas, e o que fica no ecra e o **fim** da frase, como o
   `caption_wrap.wrap_tail` do overlay nativo. O corte e feito em **fronteiras
   de palavra**: o texto e medido nas suas caixas de linha pelo proprio Blink,
   e a pesquisa binaria (`captionFitLines`) escolhe o **maior sufixo** que
   cabe em duas linhas. Nenhuma palavra e inventada, nenhuma e perdida no
   meio, e a quebra e a do navegador.
4. **A FACE CHEGA DEPOIS DO `load`** -- o evento `load` nao espera pela
   webfont e `font-display: swap` pinta primeiro a face de recurso. A medicao
   da pagina e refeita quando as fontes estao prontas (medido: o ponto estava
   em x=48 com a face de recurso e em x=85 com a Inter). O vigia e armado pela
   **primeira `set()`**, nao pelo parser: no parse nao ha fonte pendente,
   `document.fonts.ready` ja esta resolvido e o seu callback correria como
   microtask -- antes do `load`, antes de haver texto, e nunca mais.

## 5. A PROVA

### 5.1 `_main/_design-lane/caption-display-oracle.py`

Rende os ficheiros **enviados** (copiados para um directorio de rascunho) num
Blink real e le os estilos calculados e as caixas de linha de volta. Onze
verificacoes: viewport, branco, contorno, sem placa, face, tamanho, centrado,
no maximo duas linhas, **nenhuma palavra partida**, **equilibrio** das duas
linhas, e o visivel e um **sufixo** da frase.

```
   viewport 900x170   linhas: e o que eu quero e que a legenda apareca | aqui em baixo, igual o youtube faz
   V1   OK    viewport 900x170 (want 900x170)
   V2   OK    colour rgb(255, 255, 255) (want white)
   V3   OK    outline 6px rgb(0, 0, 0) (want >= 2px black)
   V4   OK    painted ancestors 0, html rgba(0, 0, 0, 0), body rgba(0, 0, 0, 0)
   V5   OK    font Inter, "Segoe UI", system-ui, sans-serif / weight 500
   V6   OK    font-size 36px (want 36px)
   V7   OK    align center, block off by 0.00px, worst glyph off by 0.00px (tolerance 1.5)
   V8   OK    2 line box(es): e o que eu quero e que a legenda apareca | aqui em baixo, igual o youtube faz
   V9   OK    split words: none
   V10  OK    balance 0.178 (want <= 0.20)
   V11  OK    visible is a suffix of the cue (whole=True)
VERDICT: PASS
```

As outras tres figuras tambem passam: `short` (1 linha), `long` (a cauda de 2
linhas, `whole=False` porque a cauda e o fim da frase) e `word` (a palavra de
58 caracteres, 991.6 px, **nao partida**).

### 5.2 O BRACO NEGATIVO -- EXECUTADO

Nove mutantes, cada um a editar uma **copia** dos ficheiros enviados, e cada um
tem de pôr o oraculo a VERMELHAR. A saida (executada, `rc=0`):

```
== BRACO NEGATIVO: cada mutante tem de VERMELHAR ==
   M1-anywhere    RED em V9 (cue=word) -- split words: pneumoultramicroscopicsilicovolcanoconiosisfluctuationibus@[0, 1]
   M2-no-outline  RED em V3 (cue=two) -- outline 0px rgb(0, 0, 0) (want >= 2px black)
   M3-left        RED em V7 (cue=two) -- align left, block off by 0.00px, worst glyph off by 144.19px (tolerance 1.5)
   M4-small       RED em V6 (cue=two) -- font-size 14px (want 36px)
   M5-plate       RED em V4 (cue=two) -- painted ancestors 3, html rgba(0, 0, 0, 0), body rgba(0, 0, 0, 0)
   M6-no-balance  RED em V10 (cue=two) -- balance 0.490 (want <= 0.20)
   M7-four-lines  RED em V8 (cue=long) -- 5 line box(es): esta e uma legenda muito mais comprida do | que duas linhas, com palavras suficientes para | ocupar tres ou quatro linhas inteiras no ecra, e | o que o dono ve e sempre o fim dela, porque as | palavras mais novas sao as que ele acabou de ouvir
   M8-pre-fix-wrap RED em V9 (cue=word) -- split words: pneumoultramicroscopicsilicovolcanoconiosisfluctuationibus@[0, 1]
   M9-serif       RED em V5 (cue=two) -- font Georgia, "Times New Roman", serif / weight 500
NEG-ARM PASS: 9/9 mutantes vermelharam
```

**A primeira execucao deste braco negativo foi um FALHA, e ela e que produziu o
desenho final:** sete dos nove mutantes **sobreviveram**, porque editavam o
`caption-float.css` enquanto o `<style>` do `caption.html` redeclarava as
mesmas propriedades com `!important` -- a mutacao nunca chegava ao ecra. Daí a
regra de "cada propriedade e decidida num sitedo" e a regra de que **o mutante
edita o sitio que decide**.

### 5.3 A COR (`caption-display-shot.py`)

Um PNG e **verdade de cor, nao de geometria** (AGENTS.md, regra 4). O script
dispara a pagina, compoe o PNG transparente sobre um cinza de video e mede os
pixels: o texto sai **branco**, com o **contorno preto** a volta de cada glifo
(a forma da letra intacta -- o `paint-order` esta a funcionar), **sem placa** (o
cinza ve-se em todo o lado menos nos glifos), o ponto verde ao lado das
palavras, e as duas linhas centradas. Ficheiros: `I:/cc-tmp/cap/`.

O overlay **nativo** tambem foi desenhado, em processo (GDI+, sem janela, sem
audio): `I:/cc-tmp/cap/native-caption-grey.png` -- e e a figura do que o dono
ve hoje.

## 6. O QUE FALTA, E ONDE (o mapa de portagem)

**O que esta lane NAO pode fazer:** o overlay nativo vive em
`app/webview/caption_overlay.py` e `app/webview/caption_wrap.py`, que nao
sao meus (outro agente esta a edita-los agora). E o overlay nativo e o que o
dono ve. Portanto **a mudanca feita aqui nao muda o ecra do dono** -- ate que
o mesmo desenho aterre no renderizador nativo.

O mapa, com os numeros que a pagina agora usa:

| propriedade | overlay nativo (hoje) | a levar para o nativo | onde |
|---|---|---|---|
| face | Segoe UI Bold 34 px | **Segoe UI Semibold 34-36 px** (o `seguisb.ttf` existe nesta maquina, medido; a Inter e uma webfont e o GDI+ nao a ve) ou "Segoe UI" Regular | `caption_overlay.py:266-269` |
| peso | 700 | **medio** (Semibold / Regular) | idem |
| contorno | Pen 6 px (3 px visiveis) | **o mesmo** -- ja esta certo | `caption_overlay.py:287-290` |
| cor | branco | **o mesmo** | `caption_overlay.py:297-301` |
| centrado | `StringAlignment.Center` na area a direita do LED (centro 16 px a direita do centro da janela) | **centrar na janela** (o LED deixa de comerse no orcamento) | `caption_overlay.py:271-278` |
| **equilibrio das 2 linhas** | **0.382** (532.5 px vs 329.3 px) | **<= 0.20** (o mesmo alvo do oraculo) | `caption_wrap.py:204-267` (a costura: `_seam_index`) |
| orcamento | 727.06 px (tecto de 42 caracteres) | o mesmo, ou um pouco mais, se o peso medio deixar as linhas mais estreitas | `caption_wrap.py:316-331` |
| palavra partida | nunca (o GDI+ parte em palavras) | **o mesmo** | `caption_wrap.py:137-201` |

A costura que produz o equilibrio e a mesma para os dois: hoje
`_seam_index` escolhe a costura **mais atrasada** que o orcamento permite
(ate 3 palavras para tras, `MAX_BACK_FROM_GREEDY`), e por isso a primeira
linha fica cheia e a segunda curta. YouTube equilibra; o mesmo numero que o
oraculo exige (as duas linhas com no maximo 20 % de diferenca) e o que a
costura tem de perseguir.

## 7. O QUE NAO FOI PROVADO

- **A pagina nao e carregada por nenhuma janela hoje** (medido: `CAPTION_HTML`
  tem 1 ocorrencia e nao e usada; `webview.create_window` tem 1 ocorrencia e e
  a do painel). A mudanca e real e esta provada no documento, mas **so aparece
  no ecra se e quando o documento voltar a ser a legenda** -- ou se o desenho
  for portado para o overlay nativo (secao 6).
- **A app nao foi aberta.** Nada nesta lane lanceu o shell, o worker, uma
  janela ou um dispositivo de audio. O overlay nativo foi medido com
  chamadas de funcao em processo (GDI+ a desenhar para um bitmap), sem janela.
- **A geometria vem do oraculo (DOM), nao do PNG.** O PNG e verdade de cor; as
  suas coordenadas nao sao medidas de nada.
- **O PNG e tirado na primeira pintura**, e a primeira pintura usa a face de
  recurso (a `font-display: block` e uma correccao so da copia do script de
  disparo, e nao alterou o resultado). A face esta provada pelo oraculo
  (`fontFamily: Inter`, `fontSize: 36px`), nao pelo PNG.
- **A palavra patologica**: 991.6 px numa coluna de 852 px -- transborda e e
  cortada na borda, nao partida. O YouTube tambem corta. Numa palavra normal
  de portugues isto nao acontece.
- **O `--caption-scale` do dono** continua a multiplicar o tamanho (36 px x
  escala); nao ha medicao do botao, que e do painel.

## 8. O EOL (e uma regra que nao se quebra)

| ficheiro | bytes | CRLF | LF solto | sha256 |
|---|---|---|---|---|
| `app/panel/caption.html` | 15383 | 0 | 287 | `0705A914268AFA7CB4628B5DD25DBD1486866626EAF689DB2BF0C3FA6DB58630` |
| `app/panel/caption-float.css` | 13814 | 268 | **0** | `4719C4B138E4011964DDEAC5099916EF4D38F4D13F887D0881E5AE98F5C979FF` |

`caption.html` continua **LF puro** e `caption-float.css` continua **CRLF
puro**. O `caption-float.css` e o ficheiro que o `.gitattributes` do repo
declara CRLF (`_main/_make-gitattributes.py`), e mexer nele a dedo seria
mexer no sha de tudo o que depende dele.

## 9. COMO CORRER

```
py -3 _main\_design-lane\caption-display-oracle.py --cue=two     # a figura
py -3 _main\_design-lane\caption-display-oracle.py --source=head  # o "antes"
py -3 _main\_design-lane\caption-display-oracle.py --neg-arm      # os 9 mutantes
py -3 _main\_design-lane\caption-display-shot.py --cue=two        # a cor
```
