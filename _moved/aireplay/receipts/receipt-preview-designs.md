# Receipt — uma página que mostra as cinco direções de design

**Lane:** preview-designs · **repo:** `H:\aireplay` · **data:** 2026-10-07/08

## O que foi entregue

| | |
|---|---|
| **ficheiro** | `H:\aireplay\docs\design\preview.html` |
| tamanho / sha256 | 63 221 B · `7CC4A89BFA8C5B2DD89EB2A2F3612CCF41B3C29312B1C39FD142D0E1C6918758` |
| **como abre** | duplo clique. Não precisa de build, de servidor nem de rede. Testado com `file:///H:/aireplay/docs/design/preview.html` |
| vistas | `#tele` `#bcast` `#mano` `#cine` `#inst` (uma direção em palco) · `#compare` (as cinco lado a lado) · `#diff` (diferenças A↔B) · `#diag`/`#diag-compare` (mede-se a si própria) |
| controlos | `1–5` troca a direção · `0` comparação · `9` diferenças · `espaço` pausa · selector de cena (Noite/Palco/Abismo) · 0,6× / 1× / 1,6× |
| capturas | `H:\aireplay\_main\preview-direcoes-01-teleprompter.png` · `-02-comparacao.png` · `-03-diferencas.png` (headless Chrome, sem janela) |
| dumps de verificação | `H:\aireplay\_main\_preview-diag-compare.html`, `_preview-diag-diag.html`, `_pv-{tele,bcast,mano,cine,inst,compare,diff}.html` |

Fonte, lida (não adivinhada): `docs/design/sotto-app-design-directions/src/data/designs.ts`,
`components/{Panel,Caption,bits,Ticker,Stage,Directions,Verdict}.tsx`, `hooks/useTranscription.ts`,
`src/index.css`; segunda leitura em `docs/design/sotto-transcription-panel-designs/src/{components/panels.tsx,lib/scripts.ts,index.css}`.
As três cenas são `sotto-app-design-directions/public/scenes/{noir,stage,deep}.jpg`, referenciadas por
caminho **relativo** a `preview.html` (o brief permite-o explicitamente) — a página tem de ficar em
`docs/design/`. Zero `http://`/`https://` no ficheiro (medido: 0 ocorrências, inclusive o SVG do grão,
com o `xmlns` percent-encoded).

## As cinco, uma linha cada

1. **Teleprompter** (`#f2e9d8`) — Barlow Condensed; histórico recua em cinza (25%/50%), só a linha viva
   brilha (`glowPulse` 2,6 s) — a legenda é um fluxo de leitura, não um registo.
2. **Broadcast** (`#ff6a55`) — IBM Plex Mono; cada linha fechada leva **índice + timecode** em grelha
   `24/38/1fr`, a última palavra em âmbar, caret `▍`; o rodapé é instrumentação (PT-BR · 48K · medidor · CONF).
3. **Manuscrito** (`#a9c1d9`) — Newsreader **serifada**; a frase em curso vive sublinhada, com cursor de
   texto, e cada palavra ganha tinta progressivamente (`--ink-op` 0,45→1,0).
4. **Cartão de Cinema** (`#e4b363`) — Fraunces; a fala em formação chega em **névoa** (`blur(3px)`→0),
   itálico, filete ouro à esquerda; entrelinha 1,9 — presença editorial mínima.
5. **Instrumento** (`#5fd3a7`) — Space Grotesk; um **LED contínuo** à esquerda (barra 3 px que respira)
   mais quadrado 5×5 vazado em cada linha fechada; tudo o resto subordinado ao indicador.

## Tipografia — o que substituí (não fingi nenhuma)

**Nenhuma das cinco famílias do design está instalada neste Windows.** Medido com dois instrumentos
independentes, que concordam: `[System.Drawing.Text.InstalledFontCollection]` e um detector de **largura**
em canvas dentro da própria página (`fontAvailable`, com controlo: Georgia→presente, fonte-inexistente→ausente).

| direção | pedida | usada por baixo |
|---|---|---|
| 01 Teleprompter | Barlow Condensed | **Bahnschrift SemiCondensed** (grotesca condensada do Windows) |
| 02 Broadcast | IBM Plex Mono | **Cascadia Mono** |
| 03 Manuscrito | Newsreader | **Georgia** (é o fallback que o próprio `index.css` declara) |
| 04 Cartão de Cinema | Fraunces | **Georgia** (idem; perde-se o eixo *wonk*/itálico macio da Fraunces) |
| 05 Instrumento | Space Grotesk | **Segoe UI** (fallback declarado `ui-sans-serif`) |

A barra de tipografia do `preview.html` diz isto em tempo de execução, e as famílias pedidas estão
**primeiro** no stack — se o dono instalar as fontes, a página muda sozinha, sem editar nada.

**Instrumento que mentiu, e fica registado:** `document.fonts.check('16px "Barlow Condensed"')` devolve
**`true`** no Chrome headless para as cinco famílias ausentes (só acompanha `@font-face`, não fontes locais).
Se a página tivesse acreditado nele, teria escrito "instalada" cinco vezes. Foi substituído pelo detector
de largura; o controlo (uma fonte que não existe) é o que prova que o detector sabe dizer **não**.

## O segundo protótipo — como difere (vista `#diff`, 9 linhas)

`docs/design/sotto-transcription-panel-designs/src/components/panels.tsx` propõe **as mesmas cinco** com os
mesmos nomes, e concorda no essencial (a linha provisória e a fechada não podem ter o mesmo peso). Difere em:

1. **A cor de destaque** — a leitura A dá a CADA direção a sua cor (`designs.ts`); a leitura B usa **uma só**
   (`#e8574f`, + `#e0a63c`, `#7fa86b`) nas cinco. É a diferença mais visível: em B os cinco painéis são o
   mesmo produto com tipografias diferentes.
2. **Tipografia do Manuscrito** — A: `Newsreader` (serifada, "documento a ser escrito"); B:
   `Instrument Sans` (**sem** serifa) — a metáfora passa a ser geométrica (margem de caderno + sublinhado).
3. **Onde vive a legenda viva** — A: **duas** superfícies (painel 380×900 de histórico + legenda ao fundo-centro
   do palco). B: **uma** — o painel É o overlay e a linha viva está lá dentro. Decisão de produto em aberto.
4. **Onde se marca "em formação"** — A: só a linha viva brilha, o fechado recua uniforme. B: o histórico
   também carrega a marca (cauda que assenta no Manuscrito; opacidade por idade no Teleprompter/Cartão).
5. **Névoa** — A `blur(3px)`; B `blur(0,45px)` + opacidade 0,5 (quase imperceptível).
6. **Telemetria** — A recusa-a por desenho; B aceita (`buffer 38ms`, `latência 240ms`, keycaps Alt+C).
7. **Cenário** — A: 3 cenas + selector + critérios; B: 3 cenários com crómio real + modo fantasma + Alt+C a ocultar.

## Verificação (o que foi medido, e como)

- **Sintaxe:** extraí o JS e corri `node --check` → exit 0.
- **Render real, headless:** `chrome --headless=new --virtual-time-budget --dump-dom`, sete vistas. Todas
  devolvem `data-preview-ready="ok"`; cada vista single acende o seu próprio botão de navegação;
  `#compare` → 5 células + 5 painéis; `#diff` → 9 linhas.
- **A página mede-se a si própria** (`#diag-compare`, `data-diag-verdict`):
  `GREEN — todas as medidas OK · assinaturas visuais (fonte|entrelinha|fundo): 5 de 5 distintas`.
  Por direção: painel 255×605, legenda com texto vivo, `form no painel` 7–8 palavras, 3 linhas fechadas,
  **colado ao fim = sim**, **transbordo 0px**, fonte declarada = AUSENTE → substituída.
  Cenas: `noir:ok · stage:ok · deep:ok` (prova que decodificam, `naturalWidth>0`).
- **Sem rede:** 0 ocorrências de `http://` e `https://` no ficheiro; nenhum `src=http…`; a página reporta
  `recursos de rede no documento: nenhum`.
- **Sem janela visível:** todas as corridas foram `--headless=new` com `--user-data-dir` dentro de
  `H:\aireplay\_main\`; censo final meu: **0** processos deste lane (nem headless), perfis temporários
  apagados depois de confirmado o caminho absoluto. A única janela de browser na máquina é a do dono
  ("Auditoria completa do app e redesign — DeepSeek Harness"), que não é minha.

### Dois defeitos apanhados por correr a página (não por a ler)

1. **O guião parava a página.** Em `designs.ts`, `SCRIPT` é `string[][]` e `line.join(" ")` é chamado ao
   fechar a frase. Ao ler as frases para uma lista de strings, `line.join` deixou de existir → `TypeError`
   dentro do `setTimeout` → a cadeia morreu no primeiro fecho e **nenhuma linha fechou** (medido: 0 linhas,
   `forming` com dezenas de caracteres). Corrigido repondo a forma do original.
2. **Cada array interno tem UM elemento.** Em `designs.ts` cada frase é `["A frase inteira."]`, logo
   `forming.map(...)` recebe **um** elemento e o protótipo original avança **frase a frase** — as animações
   *por palavra* (tinta do Manuscrito, névoa do Cartão, subida do Teleprompter) **nunca se vêem palavra a
   palavra** no original. Aqui a frase é dividida em palavras para que o que distingue as cinco seja
   visível; está escrito no rodapé de auto-teste da própria página, não escondido.

## O que NÃO consegui verificar

- **Não vejo imagens.** Este modelo não tem entrada de imagem: as três capturas acima foram tiradas e
  ficam para o dono, mas quem as tem de julgar é ele. A verificação que eu fiz é numérica/estrutural (DOM,
  geometria, transbordo, fonte resolvida), não visual. **O "teste de 1 metro" é dele.**
- **Timing e sensação com olho humano:** as animações (glow 2,6 s, tinta 0,7 s, névoa 0,6 s, marquee 48 s)
  rodam, mas se "parece vivo sem piscar" só se sabe a olhar.
- **Teclado:** `1–5`/`0`/`9`/espaço estão ligados no `keydown`; o headless não os exerce — não os testei a sério.
- **Não subi o protótipo React** (passo 2 do brief): o `npm install` não foi tentado, porque o ficheiro
  HTML é a entrega que conta e já está feita. Nenhum porto foi aberto; o 3080 não foi tocado.
- **Modo comparação com 5 colunas** exige ~1560 px de largura; abaixo disso cai para 3/2/1 colunas
  (medido a 1920×1080 = 5 colunas, painel 255×605). Não medi em ecrãs pequenos.
