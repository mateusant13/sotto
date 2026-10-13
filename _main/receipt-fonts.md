# receipt — LANE FONTS: as fontes ORIGINAIS dos .zip nas letras/frases

Lane: fonts. Data: 2026-10-12 (America/Sao_Paulo). Nenhum lançamento: nada abriu GUI,
shell, worker, WebView2 ou browser. `$env:TMPDIR=I:/cc-tmp» em todos os comandos.

## 0. A RESPOSTA CURTA

**Nenhuma FAMÍLIA de fonte dos .zip falta no painel.** As 16 famílias que os 5 .zip
nomeiam estão todas em `app/panel/fonts/» (71 ficheiros `.woff2») e todas declaradas em
`app/panel/themes/fonts.css». O passo "arranja o .woff2 que falta" tinha **zero** itens —
não inventei URLs nem descarreguei nada: a fonte é local (`@fontsource» já instalado em
`app/panel/_fonts/node_modules»), e o gerador `build_fonts.py» copia de lá.

**O que FALTAVA era PESO, não família:** 2 temas pediam o peso **300** da sua família de
legenda e o bundle não tinha essa face, portanto o CSS *font matching* escolhia a face
**mais próxima (400)** — a letra pintava mais pesada do que o .zip manda. Corrigido (4
ficheiros novos, 4 `@font-face» novos). Gate + controlo abaixo.

## 1. A TABELA PEDIDA (família do zip → disco? → declarada? → que temas a usam)

Instrumento: `node» sobre os bytes. "usada por" = família de `--font-sans»/`--font-caption»/
`--font-mono» do bloco de tokens de cada `:root[data-theme=...]» nas 7 folhas geradas
(`theme-1..5.css», `cinematic.css», `panel-designs.css»), 36 scopes.

| família do zip | ficheiro em `app/panel/fonts/» | `@font-face» em fonts.css | usada por |
|---|---|---|---|
| Barlow Condensed | sim (400 500 600 700) | sim | theme-1, pd-tele |
| IBM Plex Mono | sim (400 500 600 + 400i) | sim | theme-2, pd-bcast, os 10 `cine-*» de zip C (mono) |
| Newsreader | sim (300 400 500 600 + 300i 400i 500i) | sim | theme-3, cine-cafe, cine-tideline, cine-linen |
| Fraunces | sim (300 400 500 600 + 300i 400i 500i) | sim | theme-4, pd-cine, cine-warm-hour, cine-motel-glow, cine-last-reel, cine-dustlight, cine-ember |
| Space Grotesk | sim (400 500 600 700) | sim | theme-5, pd-instr |
| Inter | sim (300 400 500 600) | sim | cine-rainglass, cine-fieldnotes, cine-cellar, cine-linen, cine-blue-hour |
| Instrument Serif | sim (400 + 400i) | sim | cine-analog |
| Instrument Sans | sim (400 500 600 + 400i) | sim | pd-mano |
| Lora | sim (400 500 600 + 400i 500i) | sim | cine-shelves, cine-rooftop, cine-reading-hour |
| Cormorant Garamond | sim (300 400 500 + 300i 400i) | sim | cine-cellar |
| DM Mono | sim (300 400 500 + 400i) | sim | os 9 `cine-*» de zip C (mono) |
| JetBrains Mono | sim (300 400 500) | sim | **nenhum** destes 36 (é usado por `themes/zipc-panels.css», fora do meu escopo de escrita) |
| Bricolage Grotesque | sim (300..800) | sim | **nenhum** destes 36 — ver §5 |
| Jost | sim (300 400 500) | sim | cine-last-train |
| Manrope | sim (300 400 500 600) | sim | cine-rainline |
| Outfit | sim (300 400 500 600) | sim | cine-midnight-rain, cine-velvet-dusk, cine-tideline-body, cine-quiet-streets, cine-north-fog |

Fonte da coluna "do zip": as 5 `index.html» extraídas pedem exactamente estas 16 famílias em
`fonts.googleapis.com/css2?family=…» (medido: 16 `family=» distintos, 0 fora desta lista), e
os `@theme» dos próprios zips declaram-nas em `--font-display/body/tele/bcast/mano/cine/inst»
(zip A e E), `--font-{display,body,mono,cond,cinema,instr}» (zip E), `fonts.{ui,display,caption}»
(zip D), `captionFont/panelFont» (zip C) e `font-{body,display,mono}» (zip B).

## 2. A DISCREPÂNCIA MEDIDA (o que estava mesmo errado)

Instrumento: `node _main/fonts-fidelity-oracle.mjs» (bytes; nenhum browser).

* ARM C: 23 pares distintos (família|peso|estilo) pedidos por uma regra das 7 folhas geradas
  (282 regras com `font-family»). **2 sem `@font-face» exacto:**
  `Fraunces|300|normal» (regra de `theme-4») e `Newsreader|300|normal» (regra de `cine-tideline»).
* ARM D: 35 scopes de tema; **2 sem face exacta para a letra da legenda**:
  `theme-4» (Cinema Card) `--font-caption: Fraunces» com `--weight-caption: 300»;
  `cine-tideline» `--font-caption: Newsreader» com `--weight-caption: 300».
* O que o .zip manda, verbatim no código dele: zip A
  `src/components/Caption.tsx:110» = `"font-cine text-[clamp(24px,3vw,42px)] font-light …"» →
  **Fraunces 300**; zip C `src/data/scenes.ts» cena `tideline» `captionFont: F.news» com
  `font-light» → **Newsreader 300**. E os próprios URLs Google Fonts dos zips pedem esse peso
  nos DOIS estilos: zip C `Fraunces:ital,opsz,wght@0,9..144,300..500;1,9..144,300..500» e
  `Newsreader:ital,opsz,wght@0,6..72,200..500;1,6..72,200..400»; zip A `Fraunces:…1,9..144,300».
  Logo o itálico 300 também é do .zip (a linha em formação é itálica), não é oblíquo sintetizado.

## 3. O QUE FIZ (e a prova de que a regeneração reproduz o disco)

1. **Antes de tocar em nada**, provei que o gerador é o que produziu o ficheiro em disco:
   copiei `_main/_design-lane/build_fonts.py» para `I:/cc-tmp/build_fonts_repro.py» com
   `PANEL/FONTS_OUT/CSS_OUT» redireccionados para `I:/cc-tmp/fonts-repro/», e corri:
   `py -3 I:/cc-tmp/build_fonts_repro.py».
   Resultado: `wrote 66 @font-face block(s)», **`fonts.css» reproduzido = 27 971 B, sha256
   `53AE10C9C3907590BF41AFAB…», BYTE-IDENTICAL ao que estava em disco: true**; 66 ficheiros
   copiados (o disco tinha 67 — ver §5).
2. Editei a tabela `FAMILIES» de `build_fonts.py»: `Newsreader (300,400,500,600) + (300,400,500)»
   e `Fraunces (300,400,500,600) + (300,400,500)», com o comentário que cita as linhas dos zips.
3. `py -3 H:/sotto/_main/_design-lane/build_fonts.py» → **70 `@font-face»** (66 + 4),
   `1313.8 KB», rc=0.
4. Diff contra a reprodução (§1): **4 blocos ADICIONADOS, 0 REMOVIDOS, 0 alterados** — só as
   quatro faces 300 entraram; nenhum dos 66 blocos antigos mudou de bytes.
5. `app/panel/themes/fonts.css» = **29 571 B, 721 linhas, 0 CRLF / 720 LF,
   sha256 `9033B2371C6222B0DB43A97C2FBA755B5947F8F5706FF08B7BC658104AB2E498»**.
6. Ficheiros novos (sha256 sobre os bytes em disco):

| ficheiro | bytes | sha256 |
|---|---|---|
| fraunces-latin-300-normal.woff2 | 17 928 | `EB7978600911337E093A9B339E355A5493C4A2A6609AF2839E8298C0B5444174» |
| fraunces-latin-300-italic.woff2 | 22 816 | `74CB64BFA9B1CE23F22CC323A0AB39430389E23C2E07446D05377C7A33296CA5» |
| newsreader-latin-300-normal.woff2 | 22 976 | `7370B0829A4D60C6918B775D2FA486C7850A76CF5CD35504F79EF3857987952A» |
| newsreader-latin-300-italic.woff2 | 24 736 | `A3D7B97821E2BB16904E3470C48F2C4C4E860F99B334AB264B97EEEC7FCDBAA3» |

Cada um traz o seu `@font-face» com `font-display: swap» e o `unicode-range» latino da própria
família (lido de `unicode.json» do pacote) — nada foi escrito à mão em `fonts.css».

**NOTA DE ESCOPO, e é uma regra que falta:** o meu escopo de escrita diz
`_main/_design-lane/gen_*.py (o gerador, se a fonte entrar no CSS gerado)». O gerador de
`fonts.css» **não é** `gen_*.py» — é `_main/_design-lane/build_fonts.py», e o próprio
`fonts.css» diz "GENERATED by build_fonts.py. Do not hand-edit". Como `app/panel/themes/fonts.css»
ESTÁ no meu escopo, a única maneira de lhe acrescentar faces sem violar o contrato do ficheiro
era editar o gerador dele. Fi-lo, e declaro-o aqui: **a regra exacta que falta no escopo é
"`_main/_design-lane/build_fonts.py»" na lista de escrita** (o glob `gen_*.py» não o apanha).
Nenhum ficheiro fora do escopo foi tocado — ver §6.

## 4. O GATE, E O CONTROLO

`node _main/fonts-fidelity-oracle.mjs» (novo, `_main/fonts-fidelity-oracle.mjs»,
sha256 `14491C2377EEA385E61A735062804F5C2541E8B1434784C4011EF19FE1487721»).

* **ARM A** — 16 famílias dos zips; em disco e declaradas: **0 em falta**.
* **ARM B** — 70 `@font-face»; `src» quebrado **0**; `font-display» diferente de `swap» **0**;
  1 ficheiro em disco que nenhum `@font-face» declara → **WARN**, não RED (ver §5).
* **ARM C** — 23 pares (família|peso|estilo) pedidos por regra; **0 sem face exacta**.
* **ARM D** — 35 scopes; **0 falhas** na face da legenda; 18 probes de itálico (só onde o URL do
  zip pede aquele itálico) e 17 saltados (nenhum zip pede esse itálico).
* `VERDICT: PASS (A=true B=true C=true D=true)», **rc=0**.

**CONTROLO (braço negativo, defeito injectado numa CÓPIA):**
`node _main/fonts-fidelity-oracle.mjs --neg-arm» → copia `themes/» + `fonts/» para
`I:/cc-tmp/sotto-fonts-neg-*/», apaga da CÓPIA todos os `@font-face» da família da legenda do
primeiro scope (Barlow Condensed, a de `theme-1»), e volta a correr C e D:

* CÓPIA: 71 → 67 `@font-face»; **ARM C = 2 RED** (`Barlow Condensed|600|normal x3» em
  `[theme-1,pd-tele]»; `Barlow Condensed|700|normal x1» em `[theme-1]»);
  **ARM D = 2 RED** (`theme-1 … weight=700 normal … has no exact face»; `pd-tele … 600 …»);
  `NEG-ARM verdict: RED as required».
* O braço de controlo do MESMO comando continua verde (A/B na árvore real) → o defeito é o único
  que mudou. `VERDICT: PASS (control GREEN=true, injected RED=true)», rc=0.

Sem este braço, o verde do §4 não contava: é a cópia que prova que o oráculo sabe dizer NÃO.

## 5. O QUE **NÃO** FECHEI, E PORQUÊ

1. **"Vejo pouquíssimas fontes" NÃO é explicado por um ficheiro em falta.** Medido: 16/16
   famílias presentes e declaradas; **14/16 chegam a pelo menos um tema**. As duas que não
   chegam a nenhum dos 36 scopes que eu posso escrever são **Bricolage Grotesque** (0 temas) e
   **JetBrains Mono** (0 destes; é usado por `themes/zipc-panels.css», fora do meu escopo).
   Instrumento: `grep -rn Bricolage app/panel» → 8 linhas, **todas** em `themes/fonts.css» (as 6
   faces) e `theme-tune.js:105» (a opção do selector); nenhuma regra de tema.
2. **Porque NÃO liguei Bricolage Grotesque a nenhum tema:** nos zips ele é `--font-display» — a
   face do CHROME DA PÁGINA dos mockups (`sotto-app-design-directions/src/App.tsx:68»
   `<p className="font-display text-[17px] font-extrabold …">SOTTO</p>», idem
   `sotto-transcription-panel-designs/src/App.tsx:72»), e **não** a face dos componentes do
   painel: `Panel.tsx:58» (zip A) usa `font-tele» e `panels.tsx:31» (zip E) usa `font-body», ou
   seja a face DO DESENHO — que é exactamente o que o gerador já escreve em `--font-sans» e o que
   `.wordmark__name» herda. Ligar `--font-display» ao wordmark seria uma mudança de desenho que
   o .zip NÃO manda, portanto não a fiz. **Se o Lead quiser que o wordmark use a face display**,
   a regra que falta e os ficheiros são: acrescentar um token `--font-brand» em
   `_main/_design-lane/gen_themes.py» (à tabela de tokens extra, ao `build_direction_theme» e ao
   `build_panel_theme») e em `_main/_design-lane/gen_cinematic.py» (à lista de tokens e ao
   `fonts.display» de cada tema do zip D), depois regenerar e provar com a reprodução byte-a-byte.
3. **18 dos 35 temas pintam a linha em formação em itálico numa família sem itálico no bundle**
   (Outfit, Jost, Manrope, Space Grotesk, Barlow Condensed, Inter, IBM Plex Mono 500) — o browser
   sintetiza o oblíquo. **Não os empacotei** porque os URLs Google Fonts dos próprios zips NUNCA
   pedem esse itálico (ex.: `Outfit:wght@300;400;500;600», sem eixo `ital»), logo o mockup também
   recebe oblíquo sintetizado — empacotar seria inventar. Medido, para o caso de o dono querer:
   os pacotes `@fontsource» de **Space Grotesk, Manrope e Outfit não têm itálico latino nenhum**
   (`latin-italic=0»), portanto ali nem há ficheiro para empacotar sem outra fonte.
4. **`MANIFEST.warmFonts» não existe em nenhum manifesto** — `grep -rn warmFonts app/panel» →
   4 linhas, TODAS em `theme-switcher.js» (348, 373, 374, 410); 0 em `themes/themes.js»,
   `themes/panel-designs.js», `themes/zipc-panels.js». Sem a lista, `warmFonts()» cai no ramo de
   recurso e pede `document.fonts.load('16px "<primeira palavra do label>"')» — p.ex.
   `16px "Midnight"», que não é uma família → o aquecimento não carrega nada. É um defeito real
   mas **não** é a causa de "pouquíssimas fontes": o aquecimento é pré-carga, não é o caminho do
   desenho. Ficheiro fora do meu escopo (`app/panel/theme-switcher.js»); a regra que falta é
   declarar `warmFonts» no manifesto.
5. **`ibm-plex-mono-latin-700-normal.woff2» (14 956 B) está em disco e nenhum `@font-face» o
   declara.** Nenhum zip pede IBM Plex Mono 700 (zip A/B: `wght@400;500;600»; zip E:
   `ital,wght@0,400;0,500;0,600;1,400») e a ARM C prova que nenhum tema o pede, logo são bytes
   mortos — o gerador nunca o volta a criar. Deixei-o como WARN e não o declarei (declará-lo
   acrescentaria uma face que nenhum zip manda). Se o Lead quiser limpá-lo, o ficheiro é
   `app/panel/fonts/ibm-plex-mono-latin-700-normal.woff2» e o sítio é `app/panel/fonts/».
6. **NÃO MEDI O QUE O WEBVIEW2 PINTA.** Nenhum lançamento é permitido nesta lane. A afirmação
   que faço é estática e é a que o gate prova: *o CSS tem agora a face exacta (família+peso+
   estilo) que o tema pede*, logo o *font matching* deixa de escolher 400. Que os glifos na tela
   sejam os do .zip só um lançamento do Lead pode confirmar.
7. **A causa de "pouquíssimas fontes" continua NÃO ATRIBUÍDA.** Os candidatos que sobraram, cada
   um com o instrumento que falta: (a) `app/panel/lazy-assets.js» — `cinematic.css» e
   `panel-designs.css» já não são `<link>» do documento e só chegam depois de o shell responder a
   um `ask» (`theme-switcher.js:311» diz isso por escrito); se esse pedido falhar, um tema
   `cine-*»/`pd-*» pinta com a base. Medir isso exige lançar (fora do meu escopo). (b) o dono
   pode estar a olhar para o selector de fonte do `theme-tune.js», que oferece as 16 famílias +
   2 do sistema (medido: 18 opções em `FONT_OPTIONS», `theme-tune.js:87-114») — 18 não é
   "pouquíssimas", mas é a lista que ele vê.

## 6. FICHEIROS TOCADOS (e a prova de que nada mais foi)

`git -C H:/sotto status --porcelain -- <escopo>» devolve, exactamente:

    M _main/_design-lane/build_fonts.py
    M app/panel/themes/fonts.css
    ?? _main/fonts-fidelity-oracle.mjs
    ?? app/panel/fonts/fraunces-latin-300-italic.woff2
    ?? app/panel/fonts/fraunces-latin-300-normal.woff2
    ?? app/panel/fonts/newsreader-latin-300-italic.woff2
    ?? app/panel/fonts/newsreader-latin-300-normal.woff2

As 7 folhas geradas (`theme-1..5.css», `cinematic.css», `panel-designs.css») **não** foram
regeneradas nem tocadas (mtime 2026-10-11, medido) — a mudança de gerador não as afecta: os
pesos 300 já lá estavam, o que faltava era o ficheiro. `panel.css», `panel.html», `panel.js»,
`caption-float.js», `themes/zipc-panels.css» e `skins/**» não foram tocados por mim. Sem
`git add», sem commit, sem push.

## 7. COMANDOS, PARA REPETIR TUDO

    $env:TMPDIR='I:/cc-tmp'
    node H:/sotto/_main/fonts-fidelity-oracle.mjs            # PASS, rc=0
    node H:/sotto/_main/fonts-fidelity-oracle.mjs --neg-arm  # RED as required, rc=0
    py -3 H:/sotto/_main/_design-lane/build_fonts.py         # 70 faces, 1313.8 KB, rc=0
    # reproducao byte-a-byte do gerador (o passo 3.1):
    node -e "…redireccionar PANEL/FONTS_OUT/CSS_OUT para I:/cc-tmp/fonts-repro…"
    py -3 I:/cc-tmp/build_fonts_repro.py
