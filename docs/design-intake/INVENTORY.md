# Inventario dos 5 .zip de design -- S1 (docs/design-intake)

Medido 2026-10-12, instrumento: node sobre os bytes em disco (walk recursivo + statSync),
na pasta extraida docs/design-intake/<zip>/. Nada foi lancado; nenhum processo abriu.

## 1. Resumo

| zip | letra | ficheiros | bytes | designs de origem |
|---|---|---|---|---|
| sotto-app-design-directions.zip | A | 21 | 458538 | ver seccao 3 |
| cinematic-transcription-app-designs.zip | B | 18 | 154052 | ver seccao 3 |
| cinematic-transcription-app-designs (1).zip | C | 19 | 211028 | ver seccao 3 |
| cinematic-transcription-app-designs (2).zip | D | 17 | 213313 | ver seccao 3 |
| sotto-transcription-panel-designs.zip | E | 14 | 140474 | ver seccao 3 |
| **TOTAL** | | **89** | **1177405** | **50 designs distintos** |

O total de bytes extraidos coincide EXACTAMENTE com a soma dos campos
uncompressed size do central directory de cada zip -- controlo de fidelidade da
extracao: VERDE (5 de 5).

## 2. Ficheiros por zip

### A -- sotto-app-design-directions.zip  (21 ficheiros, 458538 B)

| # | caminho | bytes | tipo |
|---|---|---|---|
| 1 | index.html | 1155 | HTML |
| 2 | package-lock.json | 85633 | JSON |
| 3 | package.json | 629 | JSON |
| 4 | public/scenes/deep.jpg | 51419 | JPEG |
| 5 | public/scenes/noir.jpg | 189769 | JPEG |
| 6 | public/scenes/stage.jpg | 77892 | JPEG |
| 7 | src/App.tsx | 3532 | TSX (React) |
| 8 | src/components/bits.tsx | 2313 | TSX (React) |
| 9 | src/components/Caption.tsx | 5248 | TSX (React) |
| 10 | src/components/Directions.tsx | 4047 | TSX (React) |
| 11 | src/components/Panel.tsx | 10185 | TSX (React) |
| 12 | src/components/Stage.tsx | 7949 | TSX (React) |
| 13 | src/components/Ticker.tsx | 1284 | TSX (React) |
| 14 | src/components/Verdict.tsx | 2719 | TSX (React) |
| 15 | src/data/designs.ts | 4461 | TypeScript |
| 16 | src/hooks/useTranscription.ts | 2654 | TypeScript |
| 17 | src/index.css | 6031 | CSS |
| 18 | src/main.tsx | 230 | TSX (React) |
| 19 | src/utils/cn.ts | 169 | TypeScript |
| 20 | tsconfig.json | 681 | JSON |
| 21 | vite.config.ts | 538 | TypeScript |

### B -- cinematic-transcription-app-designs.zip  (18 ficheiros, 154052 B)

| # | caminho | bytes | tipo |
|---|---|---|---|
| 1 | index.html | 873 | HTML |
| 2 | package-lock.json | 85637 | JSON |
| 3 | package.json | 629 | JSON |
| 4 | src/App.tsx | 9746 | TSX (React) |
| 5 | src/components/Backdrop.tsx | 1256 | TSX (React) |
| 6 | src/components/DesignRail.tsx | 2188 | TSX (React) |
| 7 | src/components/HistoryPanel.tsx | 13058 | TSX (React) |
| 8 | src/components/LiveCaption.tsx | 5650 | TSX (React) |
| 9 | src/components/TopBar.tsx | 6550 | TSX (React) |
| 10 | src/data.ts | 6135 | TypeScript |
| 11 | src/hooks/usePrefersReducedMotion.ts | 578 | TypeScript |
| 12 | src/hooks/useTranscriptPlayer.ts | 3267 | TypeScript |
| 13 | src/index.css | 6685 | CSS |
| 14 | src/main.tsx | 230 | TSX (React) |
| 15 | src/themes.ts | 10182 | TypeScript |
| 16 | src/utils/cn.ts | 169 | TypeScript |
| 17 | tsconfig.json | 681 | JSON |
| 18 | vite.config.ts | 538 | TypeScript |

### C -- cinematic-transcription-app-designs (1).zip  (19 ficheiros, 211028 B)

| # | caminho | bytes | tipo |
|---|---|---|---|
| 1 | index.html | 1028 | HTML |
| 2 | package-lock.json | 85637 | JSON |
| 3 | package.json | 629 | JSON |
| 4 | src/App.tsx | 5296 | TSX (React) |
| 5 | src/components/CaptionStage.tsx | 6028 | TSX (React) |
| 6 | src/components/Chrome.tsx | 4453 | TSX (React) |
| 7 | src/components/DesignSwitcher.tsx | 5845 | TSX (React) |
| 8 | src/components/HistoryPanel.tsx | 566 | TSX (React) |
| 9 | src/components/panels/PanelSetA.tsx | 24459 | TSX (React) |
| 10 | src/components/panels/PanelSetB.tsx | 26131 | TSX (React) |
| 11 | src/components/panels/shared.tsx | 5570 | TSX (React) |
| 12 | src/components/StreamText.tsx | 1411 | TSX (React) |
| 13 | src/data/scenes.ts | 31445 | TypeScript |
| 14 | src/hooks/useTranscription.ts | 4829 | TypeScript |
| 15 | src/index.css | 6083 | CSS |
| 16 | src/main.tsx | 230 | TSX (React) |
| 17 | src/utils/cn.ts | 169 | TypeScript |
| 18 | tsconfig.json | 681 | JSON |
| 19 | vite.config.ts | 538 | TypeScript |

### D -- cinematic-transcription-app-designs (2).zip  (17 ficheiros, 213313 B)

| # | caminho | bytes | tipo |
|---|---|---|---|
| 1 | index.html | 1117 | HTML |
| 2 | package-lock.json | 85637 | JSON |
| 3 | package.json | 629 | JSON |
| 4 | src/App.tsx | 9007 | TSX (React) |
| 5 | src/components/DesignGallery.tsx | 7828 | TSX (React) |
| 6 | src/components/HistoryPanel.tsx | 18221 | TSX (React) |
| 7 | src/components/LiveCaptions.tsx | 15414 | TSX (React) |
| 8 | src/components/Stage.tsx | 5201 | TSX (React) |
| 9 | src/components/TopChrome.tsx | 12981 | TSX (React) |
| 10 | src/hooks/useTranscription.ts | 7241 | TypeScript |
| 11 | src/index.css | 4267 | CSS |
| 12 | src/lib/scripts.ts | 10853 | TypeScript |
| 13 | src/main.tsx | 230 | TSX (React) |
| 14 | src/themes.ts | 33299 | TypeScript |
| 15 | src/utils/cn.ts | 169 | TypeScript |
| 16 | tsconfig.json | 681 | JSON |
| 17 | vite.config.ts | 538 | TypeScript |

### E -- sotto-transcription-panel-designs.zip  (14 ficheiros, 140474 B)

| # | caminho | bytes | tipo |
|---|---|---|---|
| 1 | index.html | 1121 | HTML |
| 2 | package-lock.json | 85633 | JSON |
| 3 | package.json | 629 | JSON |
| 4 | src/App.tsx | 12284 | TSX (React) |
| 5 | src/components/panels.tsx | 11995 | TSX (React) |
| 6 | src/components/Stage.tsx | 10890 | TSX (React) |
| 7 | src/hooks/useMeasureHeight.ts | 478 | TypeScript |
| 8 | src/hooks/useTranscriber.ts | 3488 | TypeScript |
| 9 | src/index.css | 5844 | CSS |
| 10 | src/lib/scripts.ts | 6494 | TypeScript |
| 11 | src/main.tsx | 230 | TSX (React) |
| 12 | src/utils/cn.ts | 169 | TypeScript |
| 13 | tsconfig.json | 681 | JSON |
| 14 | vite.config.ts | 538 | TypeScript |


## 3. Designs de origem por zip (medido pelo gap-oracle.mjs, nao pelo listado do zip)

| zip | designs | onde vivem | nomes |
|---|---|---|---|
| A | 5 | src/data/designs.ts (array DESIGNS) | tele, bcast, mano, cine, inst |
| B | 10 | src/themes.ts | midnight-rain, warm-hour, velvet-dusk, study-light, tideline, motel-glow, paper-moon, quiet-streets, last-reel, north-fog |
| C | 10 paineis | src/components/panels/PanelSetA.tsx + PanelSetB.tsx | GlassCards, Hairline, Paper, Quotes, Ledger, Feed, Bubbles, Timeline, Chips, Gutter |
| C | +5 variantes de legenda | scenes.ts (campo caption) | wide, tight, italic, editorial, mono |
| C | +10 cenas | scenes.ts | cafe, rainglass, dustlight, analog, shelves, lampblack, rooftop, tideline, ember, fieldnotes |
| D | 20 | src/themes.ts | blue-plate, cellar, linen, side-b, north-window, adobe, glasshouse, film-club, nightswim, rainline, reading-hour, snowline, last-train, dusk-highway, harbor, fireside, blue-hour, paper-rain, terrace, quiet-marina |
| E | 5 | src/components/panels.tsx | Teleprompter, Broadcast, Manuscript, Cinema, Instrument |

**Total de designs distintos: 5 + 10 + 10 + 20 + 5 = 50.**

O parser do zip A tem de cortar o array DESIGNS explicitamente: designs.ts tambem
declara SCENES (:105-109) com id/name (noir, stage, deep), que sao IMAGENS de fundo e
nao designs. Ler o ficheiro inteiro conta 8 em vez de 5. O oraculo corta de
DESIGNS: DesignDef[] ate ao primeiro ]; de topo. Ha um check que falha se isto regredir.

## 4. O que este inventario NAO mede

* Nao abre nenhum ficheiro de imagem: .png/.jpg/.svg sao contados por bytes e extensao,
  nunca inspeccionados quanto a conteudo.
* Nao compara o interior dos 5 zips com o que esta extraido: a fidelidade foi provada
  pelo total de bytes contra o central directory, nao por hash ficheiro a ficheiro.
* Nao mede o que os prototypes PARECEM ao correr: nenhum zip foi construido nem aberto
  (nao ha passo de build; ver AGENTS.md, app/package.json anuncia uma toolchain morta).
* As contagens de designs sao de NOMES declarados no codigo, nao de componentes
  renderizados. Um design declarado e nunca usado contaria na mesma.
