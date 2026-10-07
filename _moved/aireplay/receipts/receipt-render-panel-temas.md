# Receipt — o renderizador de capturas por tema

**Lane:** render-panel-temas · **escreve em:** `H:\aireplay` · **lê de:** `H:\sotto` (só leitura)
**Data:** 2026-10-07 · **Veredicto do instrumento:** `PASS` (0 problemas, 1 passagem, sem re-captura
dentro da passagem, **0 deriva** no momento em que o manifest foi escrito)

---

## 1. O que foi entregue

| | |
|---|---|
| **renderizador** | `H:\aireplay\_main\render-panel-temas.py` (75 597 B) |
| **capturas (5)** | uma por tema, 760×1 800 px (380×900 CSS a dpr 2) — a geometria real do painel |
| **comparação** | `panel-temas-comparacao.png` — 1 980×1 080, os cinco lado a lado, cada coluna etiquetada com o que **ela própria mediu** |
| **controlo largo (5)** | `panel-tema-N-<nome>-1920x1080.png` — a flag literal do brief; ver §5 |
| **medidas** | `panel-temas-manifest.json` (170 472 B) e `panel-temas-tabela.md` (13 844 B) — **gerados**, não transcritos à mão |
| **fixture** | `H:\aireplay\_main\panel-temas-fixture\` (cópia gerada) |
| **log** | `H:\aireplay\_main\render-panel-temas.log` |

| ficheiro | px | bytes | sha256 |
|---|---|---|---|
| `panel-tema-1-teleprompter.png` | 760×1800 | 287 515 | `C201F581669B056CE4BB237980C88EC6AAEC21EAE155F16C6AA3719F64BACF0D` |
| `panel-tema-2-broadcast.png` | 760×1800 | 190 515 | `35AEB775999144DD641B723865CFB947EFEFD001AD9FC72E807FAD132626295A` |
| `panel-tema-3-manuscrito.png` | 760×1800 | 218 847 | `50F9AB51BCE6623B91653055BE26248EF623661289814501C31C58D0BC84C31C` |
| `panel-tema-4-cinema-card.png` | 760×1800 | 272 476 | `2DF8A45B8771C5AC6E6E4352E0A5BCF011654D131144B82095F018255BD23BC4` |
| `panel-tema-5-instrumento.png` | 760×1800 | 213 639 | `37CA9BCBB0FA45E20F45667060011A140618F234D3094E188008A487DF2E8F78` |
| `panel-temas-comparacao.png` | 1980×1080 | 522 023 | `5C9C53485634FB8C5955F2B738DDDDF11E8EFADBAA5952CEE198DCA90D0A5CA4` |
| `panel-tema-1-teleprompter-1920x1080.png` | 1920×1080 | 121 587 | `867F673C3814556F145BC04F817386F436D52B6ECBCC84718425FD0C9B528EC8` |
| `panel-tema-2-broadcast-1920x1080.png` | 1920×1080 | 78 448 | `C5536F7E6E86C08B2A38BBFE1E35AEB22C252E0B4A6CA2327A5BD0156EF463C7` |
| `panel-tema-3-manuscrito-1920x1080.png` | 1920×1080 | 108 872 | `792BA6F0BEA32CB878E22B20A114E2AFB2A3591A63B7F1686B813A7E9B00F64F` |
| `panel-tema-4-cinema-card-1920x1080.png` | 1920×1080 | 122 809 | `3277A0E7C3C475B91DA7B0C8675BA790BD01E2083313138A1FDA2BABD0B4008B` |
| `panel-tema-5-instrumento-1920x1080.png` | 1920×1080 | 99 287 | `BBD8ECBE5D026D428CCB7B4E10707E26BA197414C09A32DBDAB771E71C721990` |

**Custo:** 17 arranques de Chrome, **20,0 s no total**, um de cada vez.
**Disco desta lane:** **3,12 MB** (orçamento: 200 MB).
**Threads:** `OMP/OPENBLAS/MKL_NUM_THREADS=2` no ambiente do filho; a única concorrência é a thread do
censo de janelas (uma amostra de 100 ms, custo desprezável).
**Janelas:** censo próprio a **100 ms** — **149 amostras, 0 amostras com janela visível**.
**Processos:** cada Chrome foi morto **por PID exato da minha própria árvore** (`psutil` a partir do
PID que eu lancei); nenhum filtro por nome. Verificado no fim: **nenhum processo `chrome.exe` com o
meu perfil de fixture na linha de comandos**. A app do dono (28428/29008) nunca foi tocada.
**Áudio:** nenhum. `--mute-audio --disable-audio-output` em todos os arranques.

---

## 2. O que o instrumento é

**Uma cópia gerada do documento do painel, com legendas verdadeiras dentro.**

1. **A cópia.** O renderizador lê `app/panel/panel.html` + `panel.css` + `panel.js` + os módulos +
   `themes/*.css` + `themes/fonts.css` + os 14 `.woff2` do bundle, copia-os para
   `_main\panel-temas-fixture\` e gera `panel-fixture.html` a partir do original, substituindo **só**
   três âncoras (uma folha de fixture, o stub da ponte, o driver). Cada âncora é verificada: se o
   documento mudar de forma, o gerador **recusa correr** em vez de produzir uma imagem errada.
   A cópia diz sempre que é cópia: cabeçalho HTML, `<meta name="generator">`,
   `data-fixture="generated-copy"` + `data-fixture-source-sha256` no `<html>`, e o JSON de medidas
   carrega `"fixture": "generated-copy"` com o sha256 de tudo o que foi lido.
2. **As legendas não são desenhadas por mim.** O driver alimenta a **`panel.js` verdadeira** através
   da ponte (`stub.js`, copiado do harness de auditoria do Sotto com o sha256 registado). Cada `<li>`,
   cada `.caption__confirmed`, cada rail e cada `.caption__led` da imagem foi construído pelo próprio
   painel. Isso importa: **outra lane estava a mudar esses ficheiros enquanto isto corria** (§7).
3. **Três estados de legenda**, todos reais:
   - **fechada** (histórico) — 4 linhas, fechadas pela rota `audio-gap`, que é o que uma pausa real
     produz (segmentos a 12 s de distância em tempo de áudio, acima dos `SENTENCE_GAP_S = 8` do painel);
   - **em formação** — uma linha com a parte **confirmada** (`.caption__confirmed`) e a cauda
     **provisória** (`.caption__provisional`), que é o que o LocalAgreement-2 do painel pinta;
   - **a linha viva** — a mesma linha em formação, com o `·` final e o rail/halo que o tema lhe dá.
4. **A fixture de texto é PT-BR real, com proveniência.** Não é lorem ipsum e não é uma linha só.
   Cada frase é uma linha que o worker **realmente fechou** no histórico do dono, e o renderizador
   **verifica que ela ainda existe no ficheiro** antes de correr — se o histórico mudar, ele recusa.

   | linha | proveniência | car. | prefixo da parcial | texto |
   |---|---|---|---|---|
   | fechada | `history/2026-10-06/15.md:88` | 59 | `Porque aqui vou jogar` | Porque aqui vou jogar um machismo será porque aqui a gente. |
   | fechada | `history/2026-10-06/15.md:424` | 67 | `Qual servidor que` | Qual servidor que vocês estão jogando vou meter uma gameplay desse. |
   | fechada | `history/2026-10-06/16.md:43` | 67 | `Possível se chegad` | Possível se chegad o antes eu tinha esmi tado cara esse cara tá de. |
   | fechada | `history/2026-10-06/16.md:431` | 71 | `Um streamer mano` | Um streamer mano traba dele mano a justar o da mira é isso aqui não né. |
   | em formação | `history/2026-10-06/15.md:61` | 60 | `Essa galera que estuda vinte` | Essa galera que estuda vinte e quatro horas eu não estu dei. |

   O **tamanho é o tamanho real do painel**: o painel corta a linha em `SENTENCE_MAX_CHARS = 90`
   (`caption-formulation.js:75`), portanto uma linha "do tamanho real" tem ≤ ~90 caracteres.
   O prefixo de cada parcial é curto o suficiente para o *lookahead* do próprio painel não partir a
   linha em duas — o renderizador **falha** se `len(prefixo)+1+len(linha) > 90`.
   Ficheiros de histórico lidos: `15.md` `EEEEED5777F17942…`, `16.md` `7E20C94C61156402…`.

---

## 3. As três armadilhas medidas que decidiram o desenho

Foram medidas com sondas próprias, guardadas em `_main\` (`_viewport-probe.py`, `_crop-probe.py`,
`_reflow-probe.py`). São a parte transferível deste trabalho.

**(a) A geometria real do painel é 380×900, não 1920×1080.**
`app/webview/sotto_webview.py` → `PANEL_WIDTH = 380`, `PANEL_HEIGHT = 900`; e o ecrã desta máquina é
**96 dpi (escala 1.0)**, portanto a área de cliente do WebView2 é mesmo 380×900 **CSS px**.
O comando do brief (`--window-size=1920,1080`) fotografa um painel que ninguém vê.

**(b) `--window-size` não governa o *viewport* no arranque — mas governa a captura.**
Medido: com `--window-size=380,900`, `innerWidth` lê **492–500** e `innerHeight` lê **805**
(`H − 95`); o `--dump-dom` vê **esse** tamanho e **nunca** vê um `resize`. Já o caminho do
`--screenshot` **redimensiona primeiro**: uma barra desenhada com `width = innerWidth` e redesenhada
no evento `resize` sai com exatamente 380 px na imagem de 380 px, e 1 920 na de 1 920.
*Ou seja: a captura é fiel; a medição por `--dump-dom` não é.* Uma passagem de medidas e uma captura
com as mesmas flags descreveriam **dois layouts diferentes** — e o relatório diria "o painel tem
492 px" ao lado de uma imagem de 380.
**Cura:** `fixture-geometry.css`, uma folha **só da fixture**, fixa a caixa a 380×900
(`html,body{width:380px;height:900px}` + `body{position:relative}`, que dá ao `.panel`
`position:absolute;inset:0` exatamente a mesma caixa que o viewport real). E o `panelRect` é
**verificado** contra 380×900: se não bater, o instrumento falha em voz alta. As cinco capturas
reportam `panelRect 380×900`, `pin ok`.

**(c) `--dump-dom` por `pwsh -Command` devolve stdout VAZIO nesta máquina.**
Todo o Chrome aqui corre por `subprocess.Popen`, nunca por shell. (É a mesma armadilha já registada
no `AGENTS.md` do Sotto para listas de processos.)

**Uma quarta, que é sobre fidelidade e não sobre flags:** o driver **não pode** reenviar a mesma
parcial cumulativa para manter o stream aberto — o `ingest()` do painel **duplica as palavras**
quando a mesma parcial chega duas vezes com o buffer vivo (a guarda de re-cobertura exige
`start < emittedEnd`, falso num segmento novo). O stream é mantido aberto **estendendo o prazo do
próprio painel** (`SottoFormulation.COMMIT_MAX_HOLD_MS`), que é um botão de fixture declarado:
a constante de 1 500 ms **não** foi tocada no repo.

---

## 4. O que o dono está a ver — as cinco, em números

Da tabela gerada `panel-temas-tabela.md` §1–2 (tudo `getComputedStyle` da própria página):

| # | tema | destaque | fechada | em formação | rail | halo | o que os distingue |
|---|---|---|---|---|---|---|---|
| 1 | Teleprompter | `#F2E9D8` | Barlow Condensed 18px/400 | 30px/**700** | **não** (0px/none) | **sim** `0 0 18px` | caixa alta, a linha viva é a maior e a única que brilha |
| 2 | Broadcast | `#FF6A55` | IBM Plex Mono 15px/400 | 20px/600 | **2px solid** vermelho | não | ordinal por linha (`001…005`), timecode, rodapé de instrumentação |
| 3 | Manuscrito | `#A9C1D9` | Newsreader 17px/400 | 23px/400 | **2px solid** azul | não | serifada; confirmado `rgb(220,228,237)` vs cauda `rgb(151,163,176)` |
| 4 | Cinema Card | `#E4B363` | Fraunces 18px/400 | 24px/400 | **2px solid** ouro | não | cauda provisória **itálica**, entrelinha 1,52 |
| 5 | Instrumento | `#5FD3A7` | Space Grotesk 17px/400 | 24px/700 | **4px solid** verde | não | `.caption__led` **`display:block`** — o LED é um elemento real |

Cada uma destas linhas é uma medida, não uma impressão: o rail é `border-left-width/style/color` do
`.caption--provisional`, o halo é `text-shadow !== none` no `.caption__text` da linha em formação.
**As cinco faces concordam com o que os próprios temas escrevem nos seus comentários** — e isso é a
prova mais forte de que a fixture não está a inventar nada.

**As fontes carregaram todas.** `document.fonts.status = "loaded"` e as **cinco** famílias
verificadas a 400 e 700 em cada captura. Isto é o bundle (`themes/fonts.css` + 14 `.woff2`), não
fontes do sistema: o receipt `receipt-preview-designs.md` registou que **nenhuma das cinco famílias
está instalada neste Windows** — é precisamente por isso que o painel as traz empacotadas, e é por
isso que estas capturas mostram Barlow Condensed e Fraunces a sério em vez de substitutos.

---

## 5. O braço de controlo a 1920×1080 (a flag literal do brief)

Cinco ficheiros `panel-tema-N-<nome>-1920x1080.png`, tirados **sem** o pino de geometria, para que a
flag do brief possa ser vista a fazer o que realmente faz: o painel estica-se a 1 920 px, cada
legenda passa a **uma linha só** com ~1 900 px de comprimento, e o botão "Open in folder" ocupa
metade do ecrã. É a prova visual de que 380×900 é a geometria certa, e não um capricho meu.
**Não são as capturas para julgar design** — são o controlo.

---

## 6. Duas coisas que o instrumento encontrou (e que NÃO corrigi)

Não é âmbito deste lane mexer no painel; ficam medidas e nomeadas.

1. **O botão de tema corta a sua própria etiqueta, nos cinco temas.**
   Medido em todas as capturas: `width = 28px`, `clientWidth = 26`, `scrollWidth = 36–43`.
   Causa, lida e não adivinhada: `theme-switcher.js:244` dá ao botão `class="icon-button theme-button"`,
   `panel.css:167-181` define `.icon-button { width: 28px }`, e os cinco temas dão a `.theme-button`
   `max-width: 84px` + `overflow: hidden` + `text-overflow: ellipsis` **sem nunca declararem `width`**
   — a intenção de 84 px é derrotada pelo `width: 28px`. Nas imagens lê-se `oadca`, `nuscr`, `ema C`,
   `rume`, `epromp`. A correção de uma linha (`width: auto` na regra `.theme-button` do tema, ou um
   override em `panel.css`) é do lane que está a mexer no cabeçalho.
2. **A caixa das legendas rola 17–23 px nos temas 3 e 4.** `list.scrollHeight` 550 vs `clientH` 533
   (Manuscrito) e 575 vs 552 (Cinema Card); medido, o topo da lista fica **16 e 22 px acima** da
   caixa. Como o painel segue sempre a linha nova, esses 16/22 px são exatamente os 10 px de `padding`
   da lista mais 6/12 px dos 8 px de `padding` da primeira linha — **nenhum glifo é cortado**
   (visível na folha de comparação). É também a razão pela qual a fixture usa linhas de 59–71
   caracteres: a primeira versão, com linhas de 76–88, empurrava o topo 17–23 px para fora e a
   primeira linha fechada desaparecia em dois temas.

---

## 7. A revisão — o que foi lido, e quando (o painel mexeu enquanto eu trabalhava)

O brief avisou que outro lane estava a mudar o painel. Aconteceu, e mais do que uma vez:

- `panel.js` 80 768 → 90 235 B às **09:15:15**; `panel.html` 28 137 → 35 286 B às **09:16:37**;
  `panel.css` 34 793 → 39 466 B às **09:16:31**; `theme-switcher.js` 12 315 → 14 199 B às **09:11:42**.
- os cinco `theme-N.css` foram reescritos às **08:10**, outra vez às **09:34:11**, e outra vez às
  **09:38:48** — esta última mudou mesmo os bytes do `theme-4.css` (22 898 → 22 848 B).

Uma primeira captura ficou pronta às 09:35 e **ficou desatualizada 3 minutos depois**. O renderizador
lê no momento da captura, regista o sha256 do que leu e volta a ler no fim; se algo mudou **durante**
a passagem, **re-captura** (até `--attempts`, por omissão 3) e di-lo. Acrescentei-lhe também uma
verificação de **deriva depois da passagem**, porque a primeira versão não a tinha e foi assim que a
captura desatualizada quase passou por boa. A entrega final é uma **re-captura** da revisão de
09:38:48, com `panelMovedDuringPass: []` e `panelMovedAfterPass: []`.

| ficheiro | bytes | mtime | sha256 |
|---|---|---|---|
| `panel.html` | 35 286 | 2026-10-07 09:16:37 | `F2FF9A64B376C900…` |
| `panel.css` | 39 466 | 2026-10-07 09:16:31 | `B6A40709CA70811E…` |
| `panel.js` | 90 235 | 2026-10-07 09:15:15 | `7AEC7459ED204DFB…` |
| `theme-switcher.js` | 14 199 | 2026-10-07 09:11:42 | `2ABB57757F2B9F01…` |
| `themes/theme-1.css` | 23 460 | 2026-10-07 09:38:48 | `4F0406417F27C8B7…` |
| `themes/theme-2.css` | 24 515 | 2026-10-07 09:38:48 | `B4D7A5910B425DFC…` |
| `themes/theme-3.css` | 22 669 | 2026-10-07 09:38:48 | `F0787205A028C47F…` |
| `themes/theme-4.css` | 22 848 | 2026-10-07 09:38:48 | `3F8BEEBB671F51DF…` |
| `themes/theme-5.css` | 24 841 | 2026-10-07 09:38:48 | `3D1A44F23429B83C…` |
| `themes/fonts.css` | 6 524 | 2026-10-07 08:27:24 | `…` (ver §7 da tabela) |
| `themes/themes.js` | 3 380 | 2026-10-07 08:26:06 | `…` |
| `caption-formulation.js` | 35 781 | 2026-10-07 05:22:48 | `9465401C36CF818D…` |
| `history-source.js` | 3 708 | 2026-10-07 02:34:30 | `…` |
| `surface.js` | 4 413 | 2026-10-07 04:39:22 | `…` |
| `fonts/*.woff2` (14) | 244 028 no total | 2026-10-07 08:27:24 | (um a um em §7 da tabela) |
| `_harness/stub.js` (copiado do Sotto) | 11 872 | 2026-10-07 05:20:09 | `4A0D27BA74D359EF…` |

**sha256 combinado da fixture: `CB3CB109E83750E8E4B7E303E5248D544B1C0D24D6B86EE7538FBC2FB21112C4`.**
Os 31 ficheiros estão um a um (sha256 completo) em `panel-temas-tabela.md` §7 e no manifest.
**Como o painel está a mudar agora, estes números envelhecem: a captura é desta revisão, e voltar a
capturar é um comando** (§8).

---

## 8. Como se volta a correr

```
py -3 H:\aireplay\_main\render-panel-temas.py                  # 5 temas + comparação + controlo largo
py -3 H:\aireplay\_main\render-panel-temas.py --themes 1,5     # só alguns
py -3 H:\aireplay\_main\render-panel-temas.py --no-wide        # sem o braço de 1920
```

Código de saída **0 = todos os veredictos passaram**; qualquer outra coisa é uma falha com a razão
impressa. Falha se: o PNG não tiver 760×1 800, o tema aplicado não for o pedido, o `panelRect` não for
380×900, faltar uma linha fechada ou a linha em formação, uma fonte não carregar, um selector esperado
não existir nesta revisão, a folha de comparação não receber as medidas dos cinco iframes, o censo vir
uma janela visível, um Chrome exceder o tempo, o disco passar de 200 MB, ou o painel mudar sem
estabilizar dentro das passagens permitidas. **Deriva depois da passagem não é falha** — é impressa e
escrita no manifest como `panelMovedAfterPass`, porque a captura continua a ser uma imagem verdadeira
da revisão cujo sha256 está escrito.

---

## 9. O que NÃO consegui provar

- **Que a área de cliente do WebView2 do dono seja exatamente 380×900 CSS px.** É o que dizem
  `PANEL_WIDTH/PANEL_HEIGHT` e a escala de 96 dpi que medi; não o medi na janela a correr (isso
  exigiria lançar o shell, e a app dele está a correr — proibido). Se a janela real for mais estreita,
  a pressão de largura é maior, não menor.
- **Que o `--dump-dom` descreva o layout da captura sem o pino.** Provei o contrário: descreve o
  tamanho clampado (492×805). Foi por isso que o pino existe, e é a única coisa que a fixture
  acrescenta ao documento.
- **Que o botão de tema cortado seja uma regressão nova ou antiga.** Medi-o nesta revisão; não comparei
  com revisões anteriores, e o lane que está a mexer no cabeçalho pode estar a meio de o arranjar.
- **Que esta revisão seja a final.** O painel mudou três vezes durante o lane; a captura é de
  **09:38:48** e havia 0 deriva quando o manifest foi escrito. Qualquer edição posterior invalida-a,
  e a re-captura é um comando.
- **A superfície `strip`** (o que o Alt+C abre). Está fora do âmbito desta entrega, que é uma captura
  por tema na superfície `panel`. A fixture sabe fazê-la (`data-surface` é um atributo), mas não a
  fotografei.
- **O painel a correr.** Isto é uma cópia com um stub de ponte: prova o que o `panel.html`, o
  `panel.css`, o `panel.js` e os cinco temas **pintam**, não o que o shell faz (a janela, o
  click-through, a ordem entre o `exec_js` do shell e o evento de status).
- **Nada sobre o áudio.** Nenhuma captura abriu dispositivo de áudio e nenhuma abriu janela.
