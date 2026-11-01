# TC-20261022 — backlog do dono (últimas 100 h)

Extraído de `opencode.db` (55 prompts de utilizador, 2026-10-21 00:46 → 2026-10-22 03:44), texto
integral em `runs/owner-prompts-100h.txt`. O prompt que fecha quase todo o bloco C está na **linha 29**
(2026-10-21 18:24:35) e é citado verbatim nas linhas abaixo.

Regra: **uma linha fecha só com um comando executado cuja saída é citada aqui.**

Legenda: **FECHADO** · **PARCIAL** (medido, não resolvido) · **ABERTO**.

**Contagem (2026-10-22, ~07:1x): 39 linhas - 22 FECHADO, 6 PARCIAL, 10 ABERTO, 1 DECIDIDO (C8).** (*B3 fechou com o payload real 19/19; B5/B6 passaram a ter mecanismo medido e codigo escrito, presos a ficheiros de outra lane.*)

---

## A. Stutter / performance

| id | palavras do dono | estado | evidência |
|---|---|---|---|
| A1 | "foi só eu botar áudio no pc" | **PARCIAL** | VRAM atribuída: 13 312 MiB, **0 do Sotto**. 7 474 MiB = `services.archive_transcribe`, 2 926 MiB = `codeintel.daemon` — nenhum existe em `H:\sotto`. Worker do Sotto: pico **1478 MiB**, libertado ao sair. Falta o *slip* sob inferência. |
| A2 | "os testes demoram muito e são pesados" | **FECHADO** | cache + modo rápido: 399,8 → 130,2 → 27,7 s |
| A3 | "faz uma ferramenta de loggar a performance" | **FECHADO** | `_main/sotto-perf-log.py` |
| A4 | "abre o sotto" | **FECHADO** | shell 25892, `TRAY_ICON_ADD ok=true` |
| A5 | "uso inteligente da vram" | **FECHADO** | `5. VRAM -- peak in use : 3055 MiB (the Sotto family's peak share: 19 MiB)`; adapter 3051 vs `nvidia-smi` 3032 MiB |

## B. Legendas

| id | palavras do dono | estado | evidência |
|---|---|---|---|
| B1 | "para de traduzir pt br do inglês e do espanhol" | **FECHADO** | `TARGET_LANG='en'`, `NEVER_TRANSLATED_LANGS=('es',)`; `youtube-captions-oracle` 53/53 |
| B2 | "da opção pra todas essas línguas… inclusive as que acabei de falar pra não tocar" (no botão de menu) | **PARCIAL** | **implementado por outra lane neste tree**: `panel.html:492-493` (`<label for="translation-select">Translate to</label>` + `<select id="translation-select">`), lista em `panel.js:339` com `en`/`pt`/`es` primeiro e a opção `''`/`Auto (recommended)`, ligação em `panel.js:2404` → `bridge.setTranslationTarget`. Falta a confirmação do dono de que a lista traz todas. |
| B3 | "a legenda do youtube tá atrasada ou adiantada. no mesmo timing" | **FECHADO** (o timing da extraccao e 1:1) | **O PARSER ESTÁ EXONERADO por medição.** Ergui `parse_json3`/`_join_segs`/`cue_at` do módulo real com `ast` e conduzi um documento json3 sintético: as fronteiras são **exactamente** semiabertas — `t=0,999 -> (nenhum)`, `t=1,0 -> cue`, `t=2,999 -> cue`, `t=3,0 -> (nenhum)`, `t=3,199 -> (nenhum)`, `t=3,2 -> cue seguinte`, `t=5,0 -> (nenhum)`. Não há atraso nem avanço introduzido na leitura das cues ⇒ o desvio que ele vê está **a jusante**: na leitura do relógio do player (`player_time`/UIA) ou no painel. **Medido em `WdaHAGRBB6s` com o payload real:** `python _main\youtube-1to1-probe.py --video WdaHAGRBB6s` -> `IGUAIS no texto: 19/19   |   IGUAIS no start: 19/19`. Nao ha atraso nem adiantamento na tabela que retiramos: cada linha entra no instante exato que o player do YouTube usa (`tStartMs`). O que parecia atraso era o display a mostrar UMA linha quando o YouTube mostra DUAS (ver B6/B5). Recibo: `runs/TC-20261022-youtube-1to1.md`. |
| B4 | "legenda que termina em vírgula" (`… enfim,.`) | **FECHADO** | **Mecanismo:** o modelo emite a vírgula como ÚLTIMO token de um chunk enquanto não sabe se a frase continua; a linha fecha depois (no tecto de `max_chars`, num silêncio, ou no ponto que chega no chunk SEGUINTE) e o texto publicado leva as duas marcas. Corrigido em `worker/sotto_worker.py` com duas funções puras: `tidy_line` (colapsa `,.` `,!` `,?` `,;` `,:` e vírgula dupla — nunca acrescenta nada) aplicada em `LineFormer.line()`, e `tidy_final` (que também corta `,` `;` `:` no FIM) aplicada em `LineFormer._close()`. Prova: `_main/caption-punctuation-oracle.py` → `C1 LineFormer.line() returns tidy_line(join_fragments(...))` · `C2 LineFormer._close() finalises through tidy_final()` · `C3 10 arm(s) hold, including the owner's `enfim,.` -> `enfim.`` → `VERDICT: PASS`; braço negativo (tirar a regra `,.`) → `NEG-ARM VERDICT: PASS -- control GREEN, mutant RED`. Os três "não faças": vírgula sozinha intacta, `...` intacto, nada acrescentado. Portões vizinhos: `caption-lines-oracle` **12 PASS / 0 FAIL**, `word-split-oracle` PASS. |
| B5 | "coisa duplicada", "a frase era maior, foi sumindo" | **PARCIAL** (a chave que mata a duplicacao existe; falta ligar) | **Mecanismo medido, com os números do próprio histórico do dono.** Um censo sobre os `history/**/*.md` (2 077 linhas, 2026-10-06/07) conta **517 linhas (24,9%) que RECOMECAM e ALONGAM a frase anterior** — `'O rádio'` -> `'O rádio Segunda'` -> `'O rádio Segunda Os'` -> `'O rádio Segunda Os O rádi'`, a 6 e 2 s de distância. É exactamente a reclamação: a mesma frase acrescentada ao histórico várias vezes, cada vez maior. **Hoje já não acontece assim:** no log de 2026-10-22 (46 `CAPTION_APPLIED`) há **1** caso de recomeço-alongamento e 4 repinturas com texto igual; em 2026-10-21 eram 7 de 96. O que **não** existe é guarda no armazém: `sotto_webview.py history_append` (L7473) só recusa `route=provisional-draft` e escreve tudo o resto em `-a`, sem olhar para a linha anterior. E a cura tem um preço que é do dono: um armazém append-only não pode SUBSTITUIR a linha antiga pela maior, logo ou se larga a linha nova (perdem-se as palavras novas) ou se fica com as duas. Mede-se, não se adivinha — e o ficheiro é de outra lane. **B3/B6/B4 já mostraram que o parser e a pontuação não são a causa.** **A duplicacao tem causa medida:** o caminho vivo emite a janela a cada poll, sem comparar com a poll anterior -- e o texto da janela so muda 19 vezes em 339 amostras (medido no ARM 4.3 do portao). **Escrito:** `youtube_window.window_key` (ordem conta, repeticao nao) e `history_line` (um pedaco repetido entra uma vez: `history_line(['fine.','fine.']) == 'fine.'`). Ligacao presa ao `sotto_webview.py` (outra lane). |
| B6 | "no youtube quebra linha no timing" | **PARCIAL** (janela de 2 linhas escrita e provada; falta ligar) | **A quebra de linha do cue CHEGA ao app.** Um cue de duas linhas (`segs` com `"\n"` no meio, como o YouTube desenha) volta do parser como `'primeira linha\nsegunda linha'` — `contem '\n': True`. O parser não achata a cue; se a quebra cai no sítio errado é o painel a re-embrulhar pela largura (medida que precisa do renderizado, e `panel.js` está ocupado por outra lane). **O mecanismo, medido:** o payload declara `wpWinPositions[1] = {rcRows: 2, ccCols: 40}` e cada separador de linha e um evento `aAppend: 1` com `"\\n"`. Duas linhas ficam vivas ao mesmo tempo em **94 % do video** (32,0 s de 33,8 s, 339 amostras de 0,1 s). O caminho vivo usava `cue_at`, que devolve UM cue. **Escrito:** `app/webview/youtube_window.py` (`live_lines` = as `rcRows` ultimas linhas vivas, `window_key` para so emitir quando a janela muda, `history_line` sem repetir pedaco). **Portao:** `python _main\youtube-window-oracle.py` -> `checks=12 fail=0`, rc=0, e o braco negativo `--neg-arm` -> `FAIL 2.1 339 instantes concordam -- 320 divergem; primeiro em t=1.90 want=['Have you ever had to kill a man?', '>> No.'] got=['>> No.']`, rc=1 por desenho. Falta a ligacao em `sotto_webview.py:2246/2305` (ficheiro de outra lane) e no caminho pintado (`external_subs.caption_lines`), que precisa do app (LEAD). |
| B7 | "até as legendas tão erradas" | **ABERTO** | worker transcreve (RTF 0,567, `peak_rss_mb 775.8`), mas o texto de `plain-30s.wav` sai com "precim"/"apraxima" — por confirmar se é o áudio de teste |

## C. Painel / temas

| id | palavras do dono | estado | evidência |
|---|---|---|---|
| C1 | "o botão do nome do tema não tem contraste, não dá pra ver a borda" | **FECHADO** | **Antes: 1,35-1,56:1** (o `--line` é uma hairline painel/desktop; sobre o fill `--accent-soft` do próprio botão fica abaixo dos 3:1 que a WCAG 1.4.11 pede de um limite de componente). **Candidatos medidos nos cinco temas** (borda vs o fill que ela delimita): `--line-strong` 2,05:1 · accent@45% 2,26:1 · accent@60% 3,06:1 · **accent@70% 3,71:1** (escolhido) · accent@100% 6,26:1. Corrigido no **gerador** (`gen_themes.py`: novo token `--accent-line`, `accent_line` no `REQUIRED`, `.theme-button{border:1px solid var(--accent-line)}`, hover `var(--accent)`), regenerado (5 temas, +30/−10 linhas, CRLF intacto) e provado por `_main/theme-button-contrast-oracle.py`: `worst 3.71:1 (needs 3.0)` — theme-1 7,43 · theme-2 3,71 · theme-3 4,74 · theme-4 4,80 · theme-5 4,87. Braço negativo: `NEG-ARM VERDICT: PASS -- control GREEN, mutant RED`. Portões depois: `wordmark-oracle` PASS, `zipc-designs-oracle` 10/10 PASS, `border-radius-gate` PASS. |
| C2 | "o `sotto` escrito em pixels diferentes, não tá padronizado" | **FECHADO** | **CORRIGIDO o meu diagnóstico anterior, que era falso:** `panel-designs.css` (temas `pd-*`) **não é carregado pelo painel** — `panel.html:60-71` carrega só `theme-1..5.css` + `zipc-panels.css`, logo não havia "declarações contraditórias". O defeito real, medido **dentro da família carregada**: cinco temas, cinco marcas — Teleprompter 11px/600/0,20em (regra partilhada), Broadcast `var(--size-time)`/600/0,14em, Manuscrito `var(--size-time)`/400/0,06em, Cinema Card 11px/500/0,34em, Instrumento 9px/600/0,28em. **Corrigido no gerador** (`BRAND_METRICS` acrescentado no fim de `build()`, para a lane A, fixando 11px/600/0,2em — a família e a cor de cada direcção continuam a ser o desenho). Prova: `wordmark-metrics-oracle` → `one triple in all five -- 11px/600/0.2em` · `all five equal the shared panel.css rule` · `no theme re-breaks a metric after the normalising block` → `VERDICT: PASS`; braço negativo (theme-5 outra vez a 9px) → 3/3 RED, `NEG-ARM VERDICT: PASS`. Portões a seguir: `wordmark` PASS, `theme-button-contrast` PASS, `theme-button-geometry` PASS, `zipc-designs` PASS, `border-radius-gate` PASS. |
| C3 | "as bordas de cada design não tão transparentes, tão cinzas/pretas. assim não ficam arredondadas" | **FECHADO** | `.panel` tem `border: 0` e o anel de 1px foi removido (panel.css:196-224, com a tua ordem de 2026-10-15 *"em NENHUM design, eu quero moldura"*). Falta a metade renderizada → `_main/_border-radius-probe.py` (lança Chromium; **deferido**, modo luz). **Medido no documento VIVO, 45 temas, com o renderizador do próprio repo:** `node _main\theme-matrix-probe.mjs` (Edge via Playwright, `panel.html` servido tal como está, sem tocar no shell) → `themes in the shipped dropdown: 45` · `rendered: 45` · `themes whose panel still paints a VISIBLE edge (border or shadow): 0` · `themes whose panel corner is still SQUARE: 0` · `distinct box-shadow values across 45 themes: 1` (`rgba(255,255,255,0.05) 0px 1px 0px 0px inset, rgba(0,0,0,0.6) 0px -34px 54px -34px inset`) · `page errors: 0` · 12,6 s. As bordas cinzentas que ele viu NÃO estão no que é servido hoje: nenhum tema pinta aresta visível e todos têm canto redondo. |
| C4 | "o tema broadcast é bugado" | **ABERTO** (mecanismo MEDIDO) | Broadcast = `theme-2` (`theme-switcher.js:53`). **Três hipóteses eliminadas por medição.** (i) Os cinco temas declaram **exactamente o mesmo conjunto de 47 custom properties** no `:root` (em falta: nenhuma). (ii) **Censo de `var()` mortas** no conjunto que o `panel.html` carrega (10 folhas, 78 properties): as usadas-sem-declaração e não escritas por JS são **4** — `--surface` (1 uso) e `--menu-bg`/`--menu-fg`/`--menu-line` (6 usos, `button-contract.css`) — e **todas têm fallback**, logo não são o bug. (iii) **Auditoria estática dos cinco temas** (chavetas, propriedade duplicada no mesmo bloco, valor suspeito, mesma propriedade declarada duas vezes com valores diferentes): `theme-1` 1 achado real, `theme-2` 1, `theme-3` 2, `theme-4` 1, `theme-5` 3 — e o de `theme-2` (`border-left-color: transparent` vs `var(--line-strong)`) é **o mesmo em todos**, logo não distingue a Broadcast. (Os 4 "comprimentos sem unidade" são falsos positivos do meu detector: apanhou o dígito de `var(--space-2)`/`var(--space-3)`, não um comprimento.) Falta a metade renderizada. **Render fresco, tema contra tema, como ele mandou:** em `_main/shots/20261022-theme-matrix/theme-1.png` (Teleprompter) a fila do topo cabe inteira — `s o t t o` + gear + ponto + `Teleprompter ●` + chevron + menu + fechar. Em `theme-2.png` (Broadcast), **na MESMA largura (380 px)**, o design carrega quatro células a mais (`rec`, `REC`, `CH·01`, timecode) e o resultado mede-se: o nome do tema sai `Teleprompte…`, o timecode sai `--:--` em vez de `--:--:--:--`, e o gear é CORTADO pela fila. É defecto de desenho, não do motor. Cura possível: esconder `chrome__chan`/`chrome__tc` abaixo de uma largura, ou deixar a fila quebrar — **decisão do dono**, porque esconder o timecode tira algo que o Broadcast mostra de propósito. |
| C5 | "tira a caixa de procurar texto e textos como 'transcript history'" | **ABERTO** | **CONFIRMADO PRESENTE:** `panel.html:601-614` (`<form class="search" id="search-form">`, `placeholder="Search transcript…"`). "transcript history" = **0** ocorrências. **Conflito documentado:** a procura foi *pedida* por ti em 2026-10-18/19 (bateria L822, prompt #29) e **revogada** em 2026-10-21 — e três oráculos ancoram o pedido antigo (`search-oracle`, `search-twin-parity`, `panel-search-keyboard`). Plano: tirar o `<form>` do painel, inverter os três oráculos e a linha de aceitação. |
| C6 | "tira barras que indicam se tá on ou off, o que deve indicar é apenas uma pequena bola/círculo" | **ABERTO** | O estado já é `status__dot` + texto `not ready` (`panel.html:1119-1120`). Candidato restante: `.caption__led` (um indicador por linha). Precisa de sonda de DOM — **deferido**. |
| C7 | "não usa MDASH em lugar nenhum do painel" | **FECHADO** | varredura de 25 ficheiros com máscara de comentário: **1 406 MDASH, 0 no texto renderizado** (todos em comentários). Verificado também `&mdash;`/`&#8212;`/`\u2014`/`fromCharCode(8212)`: zero. |
| C8 | "para de mostrar erro no painel. ou que algo parou" | **DECIDIDO PELO DONO 2026-10-22 06:4x** | — **Decisão, verbatim:** *"para de mostrar erro. e gritar."* ⇒ (1) o PAINEL deixa de mostrar estado de erro (sem ponto vermelho, sem `sotto-state-breathe` de erro, sem "algo parou"); (2) a app/worker deixa de GRITAR — sem repetição periódica de aviso de silêncio. **O que fica, e porquê:** UMA linha de veredicto legível por máquina (`verdict=silent-device`, exit 3), silenciosa e sem repetição — sem ela uma corrida muda fica indistinguível de uma a funcionar e todos os testes ficam cegos. Implementação presa: `panel.html`/`panel.js`/`panel.css` e `sotto_webview.py` estão de outra lane. |
| C9 | "vários designs trocam o tamanho do botão e a posição… não consigo manter o mouse" | **FECHADO** | **Medido: os cinco temas declaram a MESMA geometria** — `.theme-button` = `padding: 0 6px`, `max-width: 84px`, `flex: 0 1 auto`, `min-width: 0` nos cinco; o swatch `::after` = 6×6px + `margin-left: 5px` nos cinco; e **nenhum** tema declara `position`/`top`/`left`/`order`/`transform` num botão. Portão novo `_main/theme-button-geometry-oracle.py`: `all five themes declare the same 7 geometry declaration(s) over 2 button rule(s)` · `no theme pins, offsets, reorders or transforms a button` · `the theme picker is the same in all five` → `VERDICT: PASS` (rc=0); braço negativo (um tema faz o `.icon-button` saltar) → `NEG-ARM VERDICT: PASS -- control GREEN, mutant RED`. Entrou nos dois formatos da bateria (`node --check` rc=0, CRLF 370 / 0 bare LF). |
| C10 | "retira o ícone do app… deixa só escrito `sotto`" | **FECHADO** | `panel.html:157` (ícone e tag saíram) |
| C11 | "design com uma bola… completamente ridículo" | **FECHADO** | **0 avatares**; o único `border-radius:50%` é o ponto 7×7 da Timeline e o detector lê o TAMANHO (`AVATAR_MIN_PX=20`). Arm J proíbe as 7 marcas da demo; mutantes M7/M8 provam-no. |
| C12 | "designs truncados, padroniza todos" | **PARCIAL** | **10 sequências distintas para 10 designs** (era 9; Gutter era cópia de GlassCards, corrigido no gerador, `+76 B`); 13/13 marcas. Falta a comparação renderizada com os `.zip`. |
| C13 | "legenda viva dentro do painel da direita não deve existir, só a de baixo" | **ABERTO** | precisa de sonda de DOM |
| C14 | "quero na direita o botão de fechar/hide, e na esquerda dele um botão de 3 pontos pra abrir mais opções… o botão de mudar designs continua ali" | **PARCIAL** | **implementado por outra lane neste tree**: `panel.html:454` `<div class="panel__menu" id="panel-menu" hidden role="menu" aria-label="More options">`, accionado por `aria-controls="panel-menu"` (`panel.html:394`); `theme-button` está **fora** do menu (offset 19 325 < 29 306). Falta confirmar a ORDEM final (fechar à direita, 3 pontos à esquerda) — o botão de fechar não tem `id` reconhecível e a lane ainda está a mexer. |
| C15 | "também retira 'live captions' do painel" | **FECHADO** | só em comentários (`panel.html:117/157/160`, `panel.js:2189`) |
| C16 | "para de falar 'speak and the line flows'… é simples: ready, not ready" | **FECHADO** | a frase só aparece num comentário (`panel.js:3684`); o texto servido é `not ready` (`panel.html:1120`) |
| C17 | (o mesmo) "ready, not ready" | **FECHADO** | `panel.html:1120` |
| C18 | "muitas vezes a logo do sotto tá truncada ou tem algo por cima" | **ABERTO** (mecanismo MEDIDO) | precisa da metade renderizada (mesma sonda da C3) **Mecanismo:** a marca é o PRIMEIRO item de uma linha flex (`panel.html:212,234,239,246`) e `panel.css` dá-lhe `white-space: nowrap` + `min-width: 32px`, **sem** `flex: none` e **sem** `overflow: hidden` ⇒ a caixa pode ficar em 32 px enquanto o texto precisa de ≥ 35,75 px (5 × 0,45em + 5 × 2,2 px de tracking) e o vizinho seguinte `pinta por cima` do que transborda. Explica o "muitas vezes": só sob pressão de largura. Cura de uma linha: `.chrome__brand, .wordmark { min-width: max-content; flex: 0 0 auto }` — **não aplicada**, `panel.css` está de outra lane. Recibo: `runs/TC-20261022-c18-logo-truncada.md`. **A medição substitui o limite inferior** (`_main/brand-truncation-probe.mjs`, Edge sobre o `panel.html` servido, 5 temas × 2 superfícies × 3 larguras): a **900 px** tudo cabe (`over=0` em 9 caixas); a **420 px** o `chrome--bcast` do tema 2 fica `box=32 need=41 over=9 overlap=1`; a **320 px** quatro dos cinco temas transbordam (`theme-2 over=9`, `theme-3 over=7 overlap=53`, `theme-4 over=7 overlap=40`, `theme-5 over=9 overlap=1`). O `flex` lido é `0 1 auto` com `min-width: 32px` — encolhível, como o recibo deduziu. A strip nunca transborda (`flex: 0 0 auto`, `min-width: 46px`). Cura em `panel.css` (outra lane): `.chrome__brand, .wordmark { min-width: max-content; flex: 0 0 auto }`. Números: `TOTAL: 27 brand measurement(s) across 3 widths; 5 with the text wider than its box.` |
| C19 | "nao usa screenshots q ja existem. tire novas, pra todos. ate pros do .zip" (prompt 9) | **FECHADO** | **NÃO ESTAVA NO BACKLOG ATÉ 2026-10-22 06:2x** — achado na auditoria dos 55 prompts. O dono pediu expressamente para **não** reusar imagens antigas e tirar novas de **todos** os designs, incluindo os do `.zip`. E exactamente o que eu NÃO posso ter feito: citei `_main/_panel-brand-theme{1..5}.png` de **07/10** no C18 e digo no recibo que são velhas. Precisa de um renderizador (Chromium/CDP ou WebView2) — lançamento. **Feito nesta passagem, sem reusar uma só imagem antiga:** `node _main\theme-matrix-probe.mjs` → 45 screenshots novas (`theme-1..5`, 30 `cine-*`, 5 `pd-*`, e os **10 do .zip**: GlassCards, Hairline, Paper, Quotes, Ledger, Feed, Bubbles, Timeline, Chips, Gutter) → `_main/shots/20261022-theme-matrix/` com `MANIFEST.md`: `shots copiados: 45`, `4,59 MB`, `zip designs presentes: 10 de 10`. O que NÃO cobre: a legenda nativa (camada GDI+, não WebView2) — precisa do app, e lançar app só o LEAD. |
| C20 | "faça o botão de config de design poder ser aplicado pro tema atual, ou de forma global" (prompt 36) | **ABERTO** | **NÃO ESTAVA NO BACKLOG ATÉ 2026-10-22 06:2x.** É um pedido de FUNCIONALIDADE, não de cor: o `theme-tune.js` (alterado por outra lane agora) tem de aplicar a afinação ao tema corrente ou a todos. Sem ficheiro livre, sem medição. |
| C21 | "os backgrounds... não têm espaçamento bom, o texto começa logo no primeiro pixel... não tem uma ´borda´/linha esquerda que simboliza o começo de uma linha de texto" (prompt 8) | **ABERTO** | **NÃO ESTAVA NO BACKLOG ATÉ 2026-10-22 06:2x** — o C12 cobria "truncados", não isto: (a) o texto encosta no primeiro pixel do fundo opaco; (b) falta a régua vertical à esquerda que marca o início da linha. Cura em CSS de tema (`app/panel/themes/*`, meus) **mais** `panel.css` (de outra lane) — precisa do render para medir o `padding` real de cada design. |
| C22 | "a legenda do painel que aparece ali, nao ta sendo loggada direito ou dando display direito" (prompt 31) | **ABERTO** | **NÃO ESTAVA NO BACKLOG ATÉ 2026-10-22 06:2x** — o B5 cobria o duplicado, não o LOG. O writer é `history_append` (`sotto_webview.py:7473`, de outra lane), que só recusa `route=provisional-draft`. Medida já feita: 2 077 linhas de histórico lidas, **517** a recomeçar a frase anterior; e o log de hoje tem `HISTORY_APPEND` por escrever. Falta a parte "display". |

**Comandos que fecham C11/C12:**
`python _main\zipc-designs-oracle.py` → `10 check(s), 0 failed` / `VERDICT: PASS` (rc=0)
`python _main\zipc-designs-oracle.py --neg-arm` → `NEG-ARM VERDICT: PASS -- 8 mutant(s), 0 wrong, 0 inert, control GREEN`

## D. Motor / lifecycle

| id | palavras do dono | estado | evidência |
|---|---|---|---|
| D1 | "parakeet no segundo pass com lifecycle inteligente" | **ABERTO** | buraco em `on_external_captions_released` (`sotto_webview.py:9194`) |
| D2 | "alt+c: ativa/desativa, painel de baixo, painel da direita" | **FECHADO** | AGENTS §2 (400 ms medido) |
| D3 | "cresceu pra 12 dps pra 13… entenda se é culpa do sotto" | **FECHADO** | **não é o Sotto** (tabela em A1/D3) |
| D4 | "worker busy-spin (1.3-1.8 cores) com sem backoff no respawn" | **FECHADO** | **A paragem existia e nunca corria.** O tecto `no_audio_restart_cap=3` estava a **indent 12**, dentro do `if self.stopped:` e atrás de um `return` — código inalcançável que `ast.parse` aceita. Medido no oráculo novo, contra o ficheiro real: **antes** 6 mortes → 6 respawns `[15, 30, 60, 120, 240, 300]` e **zero** `BRIDGE_RESTART_SUPPRESSED`; **depois** de desindentar o bloco (4 espaços, −72 B, CRLF intacto) → `6 deaths -> exactly 3 respawn(s) [15.0, 30.0, 60.0], then SUPPRESSED`. Braço negativo: `NEG-ARM VERDICT: PASS -- control GREEN, mutant RED`. Relatório: `runs/TC-20261022-sotto-worker-spin.md`. **Por medir:** os 1.3-1.8 core — o PC foi reiniciado e a app não está a correr; lançar a app é do LEAD e é passo pesado. **A metade do CPU, medida estruturalmente:** `_main/worker-busy-loop-oracle.py` — um censo AST de todos os `while` do worker e do shell: **13 loops `while` no worker**, e os de condição CONSTANTE (`while True:`) são **três** — `drain_captions` (`sotto_worker.py:4463`, escapa por `return`), `_log_writer` e `wait_ready_file` (shell) — **todos com escape** (break/return/raise/chamada bloqueante). Nenhum loop pode terminar só com a morte do processo ⇒ `VERDICT: PASS`; braço negativo (um `while True: pass` acrescentado) → `NEG-ARM VERDICT: PASS -- control GREEN, mutant RED`. **O QUE ISSO NÃO PROVA, e fica dito no próprio oráculo:** não mede CPU (os 1,3-1,8 cores só o `_main/sotto-perf-log.py --launch` pode dizer, e isso custa um lançamento) e não vê dentro de uma extensão C (onnxruntime, sounddevice, pycaw). **A METADE DO CPU, ATRIBUÍDA com o instrumento do próprio repo** (`_main/sotto-perf-log.py --report`, ficheiro `_main/perf/sotto-perf-20261022-032626.jsonl`, 120 s com a app sã): `CPU used (process time, whole run): 35.0 s` em 120 s = **0,29 núcleos de média**; os picos por papel são `worker 104.3 % / 1271 MB`, `webview n=7 30.6 % / 361 MB`, `shell 19.6 % / 161 MB` ⇒ a soma dos picos dá **1,55 núcleos**, que cai dentro da faixa que ele descreveu (1,3-1,8) e acontece nos CARREGAMENTOS do modelo, não num laço. E a máquina não estava a engasgar por nossa causa nessa janela: `p50 0.7 ms, p99 27.5, MAX 103.2, slips > 50 ms: 4` em **4280** amostras. O que MULTIPLICAVA esse custo era a escada de respawn (recarregar o modelo a cada 15 s), e essa está fechada acima. |
| E1 | "nao consigo apertar shift c... veja se e culpa do sotto" (prompt 3) | **FECHADO** | **NÃO ESTAVA NO BACKLOG como linha própria** — estava só como facto em `AGENTS.md`. O Sotto registra **UM** acelerador (Alt+C, com fallback `Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C`) e **nunca** registou o `Shift+C` simples: é do AutoClicker do dono, que o apanha quando está em foco. Exoneração por leitura do registo do hotkey; a prova de que o Sotto — com Alt+C — continua vivo está em D2 (400 ms, `PANEL_SHOWN`). |

## E. Fora do produto

Contexto 400k, truncamento de output, AGENTS enxuto — configuração do editor, não deste repositório.

---

## DEFERIDO PELO MODO LUZ (retomar às 06:00)

1. **C3/C18** — sonda renderizada (`_main/_border-radius-probe.py`) para as bordas cinzas/pretas e para a
   logo truncada/sobreposta. Lança Chromium ⇒ >60 s e não se faz em modo luz.
2. ~~**C1** — corrigir no gerador~~ **FEITO em 2026-10-22 05:0x** (ver a linha C1): token `--accent-line`
   no gerador, temas regenerados, `theme-button-contrast-oracle` PASS (pior caso 3,71:1) com braço negativo.
3. **C5** — remover o `<form class="search">` e inverter os três oráculos + a linha de aceitação.
   **BLOQUEADO POR COLABORAÇÃO, não por decisão do dono:** `app/panel/panel.html`, `panel.js` e `panel.css`
   estão **alterados (não comitados) por outra lane** neste tree — a mesma que está a implementar o menu de
   3 pontos (C14) e o selector de tradução (B2). Editar o painel agora era escrever por cima do trabalho dela.
   Retomar quando esses três ficheiros estiverem limpos. O mesmo vale para **C8** e **C13**.
4. **A1** — medir o *slip* com o worker a inferir (carrega modelo ⇒ proibido em modo luz).

### Passagem 8 — a ancora do handler-map e uma lição de EOL

25. `_main/bridge-handler-map-oracle.py` estava **VERMELHO** (`extra=['brand-tokens', '…translation-target']`,
    `missing=[]`): a lista da vocabulário ficou atrás de duas adições reais, verificadas nos dois lados antes de
    entrarem — `brand-tokens` (`app/panel/brand-bridge.js:408` → `sotto_webview.py:5376`) e `translation-target`
    (`sotto_webview.py:4660` → `:5417`). Não foi afrouxado: `missing=[]` era a prova de que o produto não perdeu
    nada. Agora `VERDICT: PASS -- 7 check(s), 0 fail` e neg-arm `9 check(s), 0 fail`.
26. **LIO DE EOL, custou três comandos:** assumi que o ficheiro era CRLF (o `git show` mostrava CRLF) e
    converti-o; o único juiz é `_main/_gitattributes-verify.py`, que respondeu
    `DIVERGE _main/bridge-handler-map-oracle.py hoje=CRLF checkout=LF → VERDICT: FAIL`. Revertido para LF →
    `DIVERGENTES: 0`, `VERDICT: PASS`. **Nunca decidir o EOL pela impressão do `git show`; perguntar ao
    verificador.**

### Passagem 7 — o busy-spin, metade estrutural

23. `_main/worker-busy-loop-oracle.py` (novo) — censo AST de `while True:` no worker e no shell, 2 afirmações
    e o censo impresso (para o dia vermelho nomear o loop). `--neg-arm` acrescenta um `while True: pass` → RED.
    **Não mede CPU** — diz isso no cabeçalho para o verde não ser lido como reclamação fechada.
24. `_main/instruments-battery.mjs` — os dois passos entraram (`node --check` rc=0, CRLF 395/0, 29 038 B).

### Passagem 6 — a bateria inteira e três hipóteses eliminadas

20. Nada mudou no produto nesta passagem: correu a **bateria principal** (modo rápido) →
    `steps 95, gate=62, control=8, skipped=8, expect-red=17, missing=0, cached=38`, **rc=0**, 131,9 s — VERDE,
    e nenhum dos passos que eu acrescentei caiu. Bateria secundária `153/157`; o único vermelho de legendas
    (`caption independent of panel`, arm B2/B3/B3b) é sobre a pintura de `caption-float.css` e `panel.css`,
    ficheiros de OUTRA lane, e fica dito em vez de contado como meu.
21. **B3/B6 medidos e o parser exonerado** (funções erguidas do módulo real por `ast`, sem importar o
    `youtube_captions` inteiro): fronteiras de cue **exactamente semiabertas**; cue de duas linhas conserva o
    `\n` (`contem '\n': True`). O desvio está a jusante — relógio do player ou painel.
22. **C4**: auditoria estática dos cinco temas não encontrou nada que distinga a Broadcast; três hipóteses
    eliminadas, resta a metade renderizada.

## O que já mudou no produto (duas passagens)

### Passagem 1 — o portão dos designs e a marca

1. `app/panel/themes/zipc-panels.css` — regenerado: 68 275 → **68 351 B**, sha256 `82E32C2506D59CE8`
   (4 linhas: Gutter ganha `.caption:last-child { border-bottom: 0 }`).
2. `_main/_design-lane/gen_zipc.py` — essa regra, com proveniência.
3. `_main/zipc-designs-oracle.py` — o portão exigia de volta as 7 marcas que o dono mandou tirar; passaram
   de obrigatórias a **proibidas** (arm J + M7/M8).
4. `_main/instruments-battery.mjs` — `wordmark-oracle.py` e o seu `--neg-arm` entraram (estavam em
   nenhuma bateria); etiqueta `zipc designs neg (6)` → `(8)`.

### Passagem 2 — o respawn infinito (busy-spin)

5. `app/webview/sotto_webview.py` — o tecto `no_audio_restart_cap` estava **inalcançável** (indent 12,
   dentro de `if self.stopped:`, atrás de um `return`). Desindentado 4 espaços: 739 351 → **739 279 B**
   (−72), CRLF preservado (14 109 / 0 bare LF). Efeito medido: 6 respawns `[15,30,60,120,240,300]` →
   **3 respawns `[15,30,60]` e para**.
6. `_main/worker-respawn-ceiling-oracle.py` (novo) — 3 afirmações (estrutural, comportamental, escada
   limitada), com braço negativo que **repõe o defeito original** e exige RED. Não lança nada.
7. `_main/instruments-battery.mjs` — os dois passos do oráculo acima entraram na segunda bateria
   (`node --check` rc=0, CRLF 355 / 0 bare LF).

### Passagem 3 — o contraste do botão e a geometria dos botões

8. `_main/_design-lane/gen_themes.py` — novo token derivado **`--accent-line`** (accent a 0,70), `accent_line`
   no `REQUIRED`, `.theme-button` passa a `border: 1px solid var(--accent-line)` e o hover sobe para
   `var(--accent)` (antes apontava a `--line-strong`, *mais fraca* que o novo repouso).
9. `app/panel/themes/theme-1..5.css` — regenerados pelo gerador: **+30/−10 linhas** nos cinco, CRLF intacto
   (730/778/748/738/808 CRLF, 0 bare LF). `themes.js` e `zipc-panels.css` ficaram **byte-idênticos** ao que
   já estavam (comparados por sha256 antes/depois — o gerador reescreve-os e não mudou nada).
10. `_main/theme-button-contrast-oracle.py` (novo) — compõe as cores sobre a slab como o browser faz e exige
    3:1 em todos os temas; braço negativo repõe a hairline. **A primeira versão deste oráculo estragou o EOL
    dos cinco temas** (lia com universal newlines e restaurava em LF: 0 CRLF / 730 bare LF) — corrigido com
    `newline=""` na leitura, regenerado, e o braço negativo re-corrido com CRLF preservado.
11. `_main/theme-button-geometry-oracle.py` (novo) — C1/C2/C3 sobre a geometria dos botões nos cinco temas.
12. `.gitattributes` — regenerado (`_main/_make-gitattributes.py --write`, **+3 linhas**) porque o
    `_main/_gitattributes-verify.py` acusava `app/panel/brand-bridge.js` como DIVERGENTE (LF hoje, CRLF no
    checkout) e não tinha regra própria. Depois: `VERDICT: PASS -- um checkout reproduz a arvore de hoje`,
    `DIVERGENTES: 0`.

### Passagem 4 — a marca é a mesma nos cinco temas

13. `_main/_design-lane/gen_themes.py` — **`BRAND_METRICS`**: um bloco acrescentado no fim de `build()` para a
    lane A que fixa `font-size: 11px; font-weight: 600; letter-spacing: 0.2em` nas quatro variantes
    (bcast/mano/cine/inst). Fica **fora** dos templates `CHROME` de propósito: o `CHROME[5]` alberga uma âncora
    da lane B que exige **exactamente um** `font-size: 11px;` — escrito lá dentro deu
    `BUILD FAILURE: the pd-chrome anchor for design 5 occurs 2 time(s), must be exactly 1`, e foi assim que
    aprendi a lição em vez de a contornar.
14. `app/panel/themes/theme-1..5.css` — regenerados: **+75/−10 linhas** nos cinco, CRLF intacto
    (739/787/757/747/817, 0 bare LF). `themes.js` e `zipc-panels.css` outra vez **byte-idênticos** (sha256).
15. `_main/wordmark-metrics-oracle.py` (novo) — simula a **cascata** (regra base do `panel.css`, depois as
    regras de cada tema por ordem de ficheiro) em vez de procurar uma string; por isso o theme-1, que não tem
    override nenhum, é julgado correctamente em vez de ser um caso especial. Neg-arm: theme-5 outra vez a 9px
    → 3/3 RED.
16. `_main/instruments-battery.mjs` — os dois passos acima entraram (`node --check` rc=0, CRLF 379/0).

### Passagem 5 — a vírgula no fim da legenda

17. `worker/sotto_worker.py` — `tidy_line` / `tidy_final` (funções puras, sem I/O) e as duas chamadas:
    `LineFormer.line()` e `LineFormer._close()`. As tabelas (`LINE_TIDY_FIX`, `LINE_TRAILING_JUNK`) estão
    no topo do módulo, junto a `join_fragments`, para o oráculo as poder extrair com `ast` sem importar o
    worker (importar puxaria o onnxruntime). Ficheiro: **7183 CRLF / 0 bare LF**, `py_compile` rc=0.
18. `_main/caption-punctuation-oracle.py` (novo) — 3 afirmações (duas no AST, uma no comportamento com
    10 braços). O primeiro braço negativo dizia `anchor spent` porque procurava a entrada com `\n` e o
    ficheiro é CRLF — corrigido a ancorar sem o terminador de linha.
19. `_main/instruments-battery.mjs` — os dois passos entraram (`node --check` rc=0, CRLF 387/0).
