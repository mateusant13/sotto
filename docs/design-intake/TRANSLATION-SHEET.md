# Folha de traducao -- os 5 .zip de design -> o painel ATUAL do Sotto

Frente S1 (docs/design-intake). Medido 2026-10-12. Nenhum processo foi lancado por esta
frente: tudo o que aqui se afirma sobre o painel vivo vem de LER os bytes em disco, nunca
de o abrir. Onde isso deixa um buraco, esta escrito na seccao 7.

## 0. A ordem do dono, verbatim

> *"o painel de baixo, ta errato. ele nao deve mostrar legenda de jeito nenhum. ele deve ser
> menor ainda, mais estreito, do tamanho dos botoes. os botoes tem que ser mais claros. e ele
> tem um botao de linhar a legenda, que liga ela NA TELA, igual um overlay, EXATAMENTE IGUAL
> os .zip fazem."*

E a descricao do overlay, tambem do dono:

> *"ela mostra na minha tela, sem fundo, sem nada, extremamente clean, e apenas algo pra
> estilizar ela ou dar corpo. tipo uma barra a esquerda dela, onde ela se apoia"*

**Restricoes da delegacao, que valem para toda esta folha:** nada por cima do painel atual,
nada dentro da div do painel atual, e o desenho antigo NUNCA substitui a estrutura atual.
Traduz-se para o tamanho atual, com os botoes atuais; o resto tem de ficar igual.

## 1. O estado ATUAL do painel (medido em disco, 2026-10-12)

### 1.1 Duas superficies, um documento

O painel tem DUAS superficies no mesmo documento, escolhidas por atributo no body:
body[data-surface="panel"] (o painel de 380x900) e body[data-surface="strip"] (a barra).
Os temas entram por data-theme no elemento html. Isto e o chao de toda a traducao:
qualquer desenho dos zips tem de caber nestas duas superficies, sem as substituir.

### 1.2 A strip, depois da ordem do dono

| facto | valor medido | onde |
|---|---|---|
| altura da strip | --strip-height: 40px (era 100px) | panel.css:2583 |
| altura do overlay | --float-height: 220px | panel.css:2586 |
| legenda na strip | .captions fica display:none nesta superficie | panel.css:2554 |
| botao da strip | 26px, border-radius 999px, so icone | panel.css:2695 |
| o painel.html carrega | 12 scripts, 8 folhas de estilo | panel.html (contado um a um) |

O painel.html carrega agora, por ordem: caption-formulation.js, history-source.js,
history-gallery.js, surface.js, themes/themes.js, themes/panel-designs.js,
themes/zipc-panels.js, theme-switcher.js, theme-tune.js, panel.js, letter-swap.js,
caption-float.js. E as folhas: themes/fonts.css, panel.css, theme-1..5.css,
themes/zipc-panels.css.

NOTA DE REVISAO: isto MUDOU durante esta frente. A lista que eu tinha medido antes eram 11
scripts e nao incluia zipc-panels.js, letter-swap.js nem caption-float.js; skins/skins.js e
skin-host.js deixaram de estar no documento. Uma lane irma mexeu no painel vivo enquanto eu
media os zips. Todos os numeros desta folha sao da revisao de AGORA.

### 1.3 O overlay flutuante -- a peca central da ordem do dono

**Ja esta implementado.** caption-float.js (4 965 B, mtime 2026-10-12T20:28:45Z) e o modulo
que pinta a legenda solta, e o cabecalho dele cita o dono verbatim. O que ele faz:

| peca | valor medido | onde |
|---|---|---|
| o no | #caption-float, IRMAO de .panel (nunca filho) | panel.html:954 |
| posicao | position:fixed; left:0; right:0; bottom:0; z-index:40 | panel.css:2756 |
| fundo | NENHUM -- nunca, em nenhum estado | panel.css:2752 |
| cliques | pointer-events:none | panel.css:2763 |
| quando aparece | so em body[data-surface="strip"][data-float="on"] | panel.css:2768 |
| topo | 34px (a barra de botoes sobe para o topo, os dois empilham) | panel.css:2795 |
| palco | flex, gap 16px, max-width 720px, centrado, padding 0 24px 12px | panel.css:2803 |
| a barra | 4px, border-radius 999px, var(--accent-gradient), respira 1.5s | panel.css:2821 |
| a linha | clamp(24px,3.1vw,42px) x --caption-scale, peso 700, line-height 1.14 | panel.css:2865 |
| sombra | 0 2px 18px rgba(0,0,0,0.88) + 0 1px 2px rgba(0,0,0,0.72) | panel.css:2872 |
| vazio | "OUVINDO..." 13px, tracking 0.3em, branco a 30% | panel.css:2879 |
| medidor | 3px x 132px, preenchido com --accent-gradient | panel.css:2890 |
| creditos | mono 10.5px, tracking 0.09em, uppercase | panel.css:2915 |
| janela curta | @media (max-height:139px) esconde prev/medidor/creditos | panel.css:2932 |

O botao e do panel.js: #strip-float-button (panel.html:807-827), etiqueta "Linhar" que vira
"Deslinhar", aria-pressed, e applyFloat() a 2134 do panel.js. Um botao, um atributo
(body[data-float]), uma altura de janela.

### 1.4 Os artefactos vivos, contados

| conjunto | quantos | ficheiro |
|---|---|---|
| temas | 30 | themes/themes.js |
| paineis do 2.o zip | 5 | themes/panel-designs.js |
| paineis do 3.o zip | 10 | themes/zipc-panels.js |
| skins congeladas | 20 | skins/cinematic-2/ (prefixos de ficheiro) |
| **total** | **65** | |

## 2. Como cada zip APRESENTA a legenda -- o eixo (c)

Este e o eixo que decide a ordem do dono, e o unico que importa para o botao de linhar.
Medido no JSX/CSS de cada zip, nunca assumido.

### A -- sotto-app-design-directions (5 designs)

A legenda e um irmao solto, em posicao absoluta, FORA do painel: .sotto-caption e
absolute, left:14px, right:calc(min(33vw,224px)+24px), bottom:118px, pointer-events:none,
e NAO tem fundo, nem borda, nem sombra. O painel (.sotto-panel) e que e um cartao: absolute,
top:108px, bottom:128px, right:10px, width:min(33vw,224px); no desktop, aspect-ratio 380/900
e height:min(74vh,720px). NAO existe barra de baixo em A, e NAO existe nenhum botao de
soltar/linhar/flutuar em A.

### B -- cinematic-transcription-app-designs (10 temas)

A legenda e um overlay solto e PERMANENTE: LiveCaption.tsx:74-79 e
pointer-events-none absolute inset-x-0 bottom-[5.5vh], irmao do painel em App.tsx:211-241.
O unico alternador que existe e INVERSO: abrir o painel EMPURRA a legenda (md:right-[360px]).
Os tres offsets deliberadamente diferentes sao 360 / 384 / 380 px. O token --shadow mapeia
para text-shadow e NUNCA para box-shadow -- a mesma decisao que o dono pediu ("sem fundo").
Nao ha :root: os tokens vem de @theme, de style={theme.vars} inline, e de literais.

### C -- cinematic-transcription-app-designs (1) (10 paineis)

A legenda e absolute bottom-0 left-0 z-20 com pb-[7vh], SEM contentor nenhum, so textShadow.
Traz ainda 5 variantes de legenda (wide, tight, italic, editorial, mono) e 10 cenas.
O accent da legenda DIVERGE do accent do painel em duas cenas: dustlight (#F09A55 contra
#C4562F) e fieldnotes (#A9CBC6 contra #3F5E60).

### D -- cinematic-transcription-app-designs (2) (20 temas)

Vinte temas. O eixo (c) de D nao foi medido tema a tema -- ver seccao 7. O que esta medido e
que 16 dos 20 casam com skins congeladas vivas e 4 ficam ambiguos.

### E -- sotto-transcription-panel-designs (5 paineis)

Maquete fixa de 380x900, com useMeasureHeight e scale = panelH/900. A legenda vive dentro do
painel, no corpo com mask-fade-top, e o painel e que decide se tem caixa:

* Teleprompter -- sem caixa nenhuma (sem fundo, sem borda, sem raio, sem sombra).
* Broadcast -- caixa com border 1px rgba(255,255,255,0.1), raio 0, fundo 0.88.
* Manuscrito -- fundo 0.62 com blur, sem flex, regua de margem a esquerda.
* Cartao de Cinema -- o MAIS solto por construcao: sem borda, gradiente que acaba em 0.14, sem chrome.
* Instrumento -- o MAIS contido: unico com raio (10px), borda e fundo 0.92.

Em E tambem NAO existe nenhum botao de soltar/linhar/flutuar. Os keycaps do rodape do
Instrumento sao spans, nao botoes.

## 3. O que se traduz para o painel ATUAL

### 3.1 A conclusao que atravessa os cinco zips

**Nos cinco zips a legenda solta e um CAMINHO DE RENDERIZACAO PERMANENTE, nunca um
alternador.** Nao ha, em zip nenhum, um botao que a solte. O dono pediu um botao. Logo o
botao e uma DECISAO DE DESENHO ORIGINAL desta casa, nao uma porta de um prototype -- e o que
se porta dos zips nao e o botao, sao as PROPRIEDADES do overlay:

| propriedade | os zips fazem | o painel atual faz | igual? |
|---|---|---|---|
| fundo | nenhum, nunca | nenhum, nunca | SIM |
| cliques | pointer-events:none | pointer-events:none | SIM |
| posicao | fundo do ecra, centrado | fundo da janela, centrado | SIM na intencao |
| corpo | uma barra a esquerda | uma barra 4px com --accent-gradient | SIM |
| sombra | so text-shadow | so text-shadow | SIM |
| irmao do painel | sim | sim (#caption-float e irmao de .panel) | SIM |
| alcance | o ecra INTEIRO | a janela do Sotto (1040x100 hoje) | **NAO** |

### 3.2 A unica coisa que NAO fica "exatamente igual"

O dono escreveu "EXATAMENTE IGUAL os .zip fazem". Nos zips a legenda flutua sobre o ECRa
INTEIRO, por cima de outra aplicacao qualquer. No Sotto ela vive dentro da janela do shell,
que hoje mede 1040x100. Isto NAO e uma falta de trabalho: e uma decisao com medicao por tras.
O caminho obvio -- bridge.setTransparency(true), que poe a janela click-through -- foi medido
e deixou o dono SEM PODER CLICAR EM NADA de volta (o log tem TRANSPARENCY_ON
click_through=true, e o dono relatou "cliquei num botao e ele sumiu"). Por isso o overlay
fica dentro da janela e a janela continua interactiva. O comentario do panel.css:2776-2784
regista exactamente isto. **Marcado como AMBIGUO / decisao pendente do dono.**

### 3.3 O que ainda nao chega ao ecra (medido)

A altura pedida pelo overlay e --float-height: 220px, mas o shell entrega 1040x100. O
panel.css:2595-2600 regista a causa medida: a linha 114720 do _main/webview-run.log diz
STRIP_HEIGHT from=148 to=40 source=css css_value=40 -- o shell LEU os 40px -- e as linhas
seguintes continuam a docar window=1040x100. O rect guardado em
_main/panel-visibility.json (geometry.surface=strip, 1040x100) e o que o geometry_for
devolve, portanto a altura do CSS nunca chega ao HWND. Ha defesa no CSS:
@media (max-height:139px) esconde o prev, o medidor e os creditos, para a legenda ficar
correcta nas duas alturas.

### 3.4 A largura "do tamanho dos botoes" nao se resolve no documento

O dono pediu a strip "menor ainda, mais estreito, do tamanho dos botoes". O painel.css
regista, com medicao, que o documento NAO consegue isso sozinho: o shell entrega 1040 de
largura e pinta cada pixel nao pintado com o seu #0B0F14 opaco, portanto um body
transparente com uma pill centrada da exactamente o defeito que o dono descreveu ("uma cor
solida, uma div inteira. no meio dela, tinha o painel de baixo"). A largura e do SHELL.
**Marcado como CROSS-LANE: precisa do Lead, nao desta frente.**

## 4. A folha, design a design

Cada linha traz (a) geometria e estrutura, (b) cor, tipografia e efeitos, (c) como a legenda e
apresentada. Onde um eixo nao foi medido, esta dito.

### 4.1 Zip A -- 5 designs (src/data/designs.ts)

Os cinco PARTILHAM a mesma moldura de painel, verbatim:
"h-full flex flex-col overflow-hidden rounded-lg border shadow-[0_28px_90px_rgba(0,0,0,0.6)]
backdrop-blur-md". O que muda entre eles e o accent e a fonte.

| design | (a) geometria | (b) accent / fonte | (c) legenda |
|---|---|---|---|
| Teleprompter (tele) | .sotto-panel absolute top:108px bottom:128px right:10px width:min(33vw,224px); desktop aspect-ratio 380/900, height:min(74vh,720px) | #f2e9d8 / Barlow Condensed | .sotto-caption solta, absolute bottom:118px, sem fundo |
| Broadcast (bcast) | igual | #ff6a55 / IBM Plex Mono | igual |
| Manuscrito (mano) | igual | #a9c1d9 / Newsreader | igual |
| Cartao de Cinema (cine) | igual | #e4b363 / Fraunces | igual |
| Instrumento (inst) | igual | #5fd3a7 / Space Grotesk | igual |

Em A NAO existe barra de baixo e NAO existe botao de soltar. O painel e um cartao; a legenda
e um irmao solto com pointer-events:none e sem fundo, borda ou sombra.

### 4.2 Zip B -- 10 temas (src/themes.ts)

Os 13 tokens de cada tema sao injectados INLINE por style={theme.vars} em App.tsx:176.
Nao ha :root -- ha tres fontes de token ao mesmo tempo (@theme, o style inline, e literais).

| tema | (a) geometria | (b) cor / efeitos | (c) legenda |
|---|---|---|---|
| midnight-rain | painel + overlay solto | 13 tokens inline | LiveCaption solta, bottom-[5.5vh], irmao do painel |
| warm-hour | igual | igual | igual |
| velvet-dusk | igual | igual | igual |
| study-light | igual | igual | igual |
| tideline | igual | igual | igual (a chave tideline colide -- ver 6.2) |
| motel-glow | igual | igual | igual |
| paper-moon | igual | igual | igual |
| quiet-streets | igual | igual | igual |
| last-reel | igual | igual | igual |
| north-fog | igual | igual | igual |

Propriedades transversais de B, todas medidas: --shadow mapeia para TEXT-shadow, nunca para
box-shadow; a linha fantasma, a deixa do orador e a etiqueta Live/Paused levam cada uma o seu
proprio text-shadow; .eq e sempre renderizado e .eq.paused span usa animation-play-state:paused.
O painel EMPURRA a legenda quando abre (md:right-[360px]) -- o unico alternador que B tem, e
e inverso ao que o dono pediu.

### 4.3 Zip C -- 10 paineis + 5 variantes + 10 cenas

**Este zip ja foi portado para o painel vivo** (themes/zipc-panels.js, mtime
2026-10-12T16:37:22Z, e themes/zipc-panels.css 35 875 B). O swatch de cada entrada E o accent
do proprio desenho.

| design | (a) onde vive no zip | (b) accent vivo (swatch) | (c) legenda |
|---|---|---|---|
| GlassCards | PanelSetA.tsx:22 | #E9A85B | absolute bottom-0 left-0 z-20, pb-[7vh], sem contentor, so textShadow |
| Hairline | PanelSetA.tsx:147 | #9FC4D8 | igual |
| Paper | PanelSetA.tsx:250 | #C4562F | igual |
| Quotes | PanelSetA.tsx:346 | #E8C69B | igual |
| Ledger | PanelSetA.tsx:454 | #D8B060 | igual |
| Feed | PanelSetB.tsx:21 | #8B93F2 | igual |
| Bubbles | PanelSetB.tsx:110 | #D8A7E8 | igual |
| Timeline | PanelSetB.tsx:226 | #BED6DC | igual |
| Chips | PanelSetB.tsx:324 | #FFC496 | igual |
| Gutter | PanelSetB.tsx:457 | #4A6B74 | igual |

As 5 variantes de legenda (wide, tight, italic, editorial, mono, declaradas em scenes.ts:9)
sao variantes de UMA legenda, nao designs separados, e ficam deliberadamente fora da contagem
de 50. O accent da legenda diverge do accent do painel em dustlight (#F09A55 contra
#C4562F) e fieldnotes (#A9CBC6 contra #3F5E60).

### 4.4 Zip D -- 20 temas (src/themes.ts)

| tema | (a) | (b) | (c) |
|---|---|---|---|
| blue-plate, cellar, linen, side-b, north-window, adobe, glasshouse, film-club, nightswim, snowline, dusk-highway, harbor, fireside, paper-rain, terrace, quiet-marina | NAO MEDIDO tema a tema | NAO MEDIDO tema a tema | NAO MEDIDO tema a tema |
| rainline, reading-hour, last-train, blue-hour | NAO MEDIDO | NAO MEDIDO | NAO MEDIDO |

O que esta medido em D: 16 dos 20 casam por nome com skins congeladas vivas, e 4 ficam
ambiguos entre um tema cine-* e uma skin de mesmo nome. Ver seccao 7 para o buraco.

### 4.5 Zip E -- 5 paineis (src/components/panels.tsx)

Maquete fixa 380x900 com scale = panelH/900. A legenda vive DENTRO do painel, no corpo com
mask-fade-top, e o painel decide se tem caixa. Estes 5 ja vivem no painel como pd-tele,
pd-bcast, pd-mano, pd-cine, pd-instr.

| design | (a) geometria | (b) cor / tipo / efeito | (c) legenda |
|---|---|---|---|
| Teleprompter | absolute inset-0 flex flex-col; corpo mask-fade-top px-7 pb-14 pt-24; SEM caixa | Barlow Condensed; gradiente 0.82 -> 0.42 -> 0.12; backdrop blur 2px; mask-fade-top 120px; breatheGlow | dentro do painel, sem fundo, historicas 25px, activa 32px |
| Broadcast | border 1px rgba(255,255,255,0.1), raio 0, fundo 0.88, blur 6px; cabecalho e rodape com border | IBM Plex Mono; REC, timecode; telemetria simulada com Math.random a cada 900ms | dentro, com caixa de live border-l-2 accent |
| Manuscrito | fundo 0.62, blur 7px, SEM flex; regua de margem absolute left:27px | Instrument Sans; linha activa italica com underline decoration-white/25; settle 1s | dentro, sem caixa; 18px, line-height 1.6 |
| Cartao de Cinema | absolute inset-0, blur 3px, gradiente; corpo px-9 pb-20 pt-32 | Fraunces; gradiente 0.72 -> 0.4 -> 0.14; assinatura italica 13px a 25%; activa com blur 0.45px | dentro; o MAIS solto por construcao (sem borda) |
| Instrumento | raio 10px (o UNICO), border rgba(255,255,255,0.08), fundo 0.92, blur 8px; cabecalho e rodape | Space Grotesk; 3 barras EQ; keycaps 22x20 raio 5; unico box-shadow do conjunto (indicator-pulse) | dentro; a mais contida; activa 23px bold |

Em E NAO existe botao de soltar/linhar/flutuar. Os keycaps do rodape do Instrumento sao
SPANS, nao botoes -- nao ha nada clicavel ali para portar.

## 5. O que tem de ficar IGUAL

1. **A estrutura atual nao se toca.** As duas superficies (body[data-surface]) e o tema por
   data-theme no html continuam a ser o chao. Nenhum zip substitui isto.
2. **A legenda da strip continua a nao existir.** .captions display:none nessa superficie.
3. **O overlay nao ganha fundo, nunca.** Nem plate, nem box, nem backdrop, nem border.
   A barra de 4px E o corpo -- e o que o dono descreveu.
4. **O overlay nao come cliques.** pointer-events:none, como em A e em B.
5. **O overlay e irmao de .panel, nunca filho.** Nada entra na div do painel atual.
6. **A sombra e text-shadow, nunca box-shadow.** Decisao de B, e a mesma do dono.
7. **Os botoes atuais ficam.** O botao novo (Linhar) e um .strip-button como os outros, com a
   mesma geometria de 26px e raio 999px.
8. **O tema manda na cor.** A barra e o medidor usam var(--accent-gradient), portanto
   acompanham os 45 temas sem uma segunda paleta.

## 6. Impossivel ou ambiguo

### 6.1 IMPOSSIVEL no documento: a largura da strip

O dono quer a strip "do tamanho dos botoes". O documento nao pode: o shell entrega 1040x100 e
pinta os pixels nao pintados com #0B0F14 opaco. Recusar pintar da o defeito que o dono
descreveu. **Precisa do shell -- CROSS-LANE, para o Lead.**

### 6.2 AMBIGUO: a chave tideline

No manifesto vivo existem DUAS entradas que normalizam para tideline: cine-tideline e
cine-tideline-body. O zip B tem um tema chamado tideline. Um primeiro-que-chega creditaria
uma e esconderia a outra em silencio, portanto o oraculo guarda TODOS os candidatos e marca a
linha como AMBIGUOUS em vez de escolher. **Decisao pendente: qual das duas e a Tideline do zip B.**

### 6.3 AMBIGUO: quatro temas do zip D com dois candidatos cada

rainline, reading-hour, last-train e blue-hour casam AO MESMO TEMPO com um tema cine-* e com
uma skin congelada de nome igual. O oraculo nao escolhe. **Decisao pendente.**

### 6.4 IMPOSSIVEL sem quebrar o uso: flutuar sobre o ecra inteiro

O dono disse "EXATAMENTE IGUAL os .zip fazem". Nos zips a legenda flutua sobre o ecra todo,
por cima de outra aplicacao. Para isso a janela teria de ser click-through, e isso foi MEDIDO
e deixou o dono sem poder clicar em nada. O overlay fica dentro da janela. **Esta e a unica
coisa que nao fica exatamente igual, e e uma decisao, nao um esquecimento.**

### 6.5 O botao de linhar nao tem porta num prototype

Nos cinco zips a legenda solta e permanente -- nao ha botao nenhum que a solte. O botao e
decisao original desta casa. O que se porta sao as propriedades do overlay, nao o controlo.

### 6.6 Codigo morto que NAO se porta

Do zip C: session.source, GhostPill, IconMic, IconCheck, countWords. E Math.random aparece em
3 sitios, o que torna a demo nao-determinista -- nao se porta como comportamento.

### 6.7 Nao portar o painel sem o overlay

Se um painel for portado e o overlay ficar de fora, a app fica SEM legendas vivas: o
HistoryPanel do zip B so mostra linhas fechadas, e a linha em voo existe exclusivamente no
LiveCaption. Isto e uma armadilha de sequencia, nao uma preferencia.

## 7. O que NAO foi medido (e por isso nao se afirma)

* **Nada foi aberto.** Esta frente nao lancou a app, o shell, o worker nem o run.cmd. Tudo o
  que se diz do painel vivo e leitura de bytes em disco. **Nao ha uma unica medicao de DOM
  vivo, de pintura, nem de comportamento em runtime.**
* **O overlay nunca foi visto a funcionar.** caption-float.js existe e esta carregado pelo
  panel.html, mas se ele PINTA o que o CSS promete nao foi verificado -- proibido lancar.
* **O eixo (b) do zip D nao foi medido** tema a tema: 20 temas, sem cores, tipografia nem
  efeitos por tema. O subagente que os estava a levantar esgotou o espaco. Fica em aberto.
* **O eixo (c) do zip D nao foi medido.**
* **A altura 220px do overlay nunca foi honrada pelo shell** -- o rect guardado ganha. O CSS
  defende-se com @media (max-height:139px), mas isso nao foi visto a correr.
* **Nenhum zip foi construido nem aberto.** app/package.json anuncia uma toolchain morta; o
  caminho vivo nao tem passo de build. As geometrias vem do JSX/CSS, nao de um render.
* **A equivalencia visual nao foi medida.** O gap-oracle e uma matriz de NOMES. Ele diz que
  theme-1 se chama Teleprompter; nao diz que se PARECE com o Teleprompter do zip A.
* **O interior das skins nao foi lido.** Contam-se os 20 prefixos de ficheiro; nenhum .html
  nem .css dentro de skins/cinematic-2/ foi interpretado quanto a identidade de desenho.

## 8. O portao, e como o re-correr

docs/design-intake/gap-oracle.mjs e a matriz de nomes entre os 5 zips e o painel vivo.
Corre-se em processo, sem lancar nada:

    node docs/design-intake/gap-oracle.mjs               (a matriz)
    node docs/design-intake/gap-oracle.mjs --json        (a mesma, em JSON)
    node docs/design-intake/gap-oracle.mjs --self-check  (o braco de controlo)

O braco de controlo e obrigatorio antes de citar qualquer numero: sem ele o verde nao
significa nada. Ele faz TRES mutacoes numa copia do painel vivo e exige que a matriz REGRIDA
em cada uma -- apagar uma entrada do themes.js, apagar um prefixo de skin, e quebrar o
frozen[] do index.json. Medido nesta revisao: **CONTROL ARM VERDICT: PASS (0 falhas)**, rc=0,
e as tres mutacoes regridem (Broadcast; blue-plate+Broadcast; frozen 0 contra prefixos 19).

Numeros desta revisao, todos com o braco de controlo verde a frente:

| medida | valor |
|---|---|
| designs nos 5 zips | 50 (5 + 10 + 10 + 20 + 5) |
| artefactos vivos | 65 (30 temas + 15 paineis + 20 skins) |
| STRICT (nome igual, sem pontes) | 36 de 50 implementados, 14 em falta |
| ALIASED (com as 20 pontes declaradas) | 46 de 50 implementados, 4 em falta |
| ambiguos | 5 (tideline + os 4 do zip D) |
| vivos sem origem em zip nenhum | 19 (15 temas + 4 skins) |

Os 19 vivos sem origem decompõem-se em duas coisas MUITO diferentes, e mistura-las seria
desonesto: **10 sao genuinamente sem origem** (cine-cafe, cine-rainglass, cine-fieldnotes,
cine-dustlight, cine-rooftop, cine-analog, cine-shelves, cine-ember, cine-cellar, cine-linen)
e **9 sao orfaos so por causa da ambiguidade** (cine-tideline, cine-rainline, cine-blue-hour,
cine-reading-hour, cine-last-train, e as skins blue-hour, last-train, rainline, reading-hour).
Os segundos TEM origem no zip D; o que falta e decidir qual candidato e o certo.
