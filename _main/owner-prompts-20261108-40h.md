# Owner prompts — Sotto panel (last 40 h)

Collected 2026-11-08T06:4xZ from the harness transcripts themselves (`H:/pi-agent/sessions/**/*.jsonl`) and from
`H:/pi-agent/history.db`, not from recaps or receipts. Window: **2026-11-06T14:00Z → 2026-11-08T06:33Z**
(40 h before the owner's ask at 06:33:18Z).

Transcripts of record: `H:/pi-agent/sessions/--H--sotto--/2026-11-06T19-14-01-218Z_01a1b248-3d82-756a-a50a-2fd9ba36272b.jsonl`
(in-window) and `H:/pi-agent/sessions/--H--sotto--/2026-11-06T03-45-42-092Z_01a1aef6-56cc-7250-bb22-d233dab67bfc.jsonl`
(lineage).

Reading rules, so every row stays checkable:

- The **verbatim** column is the stored message text, unchanged. `⏎` marks a line break that exists in the
  original; nothing else was added, removed or translated. The harness' own `[Image #n, WxH]` placeholders
  are kept because they are part of the stored text.
- `fixed?` names a commit and the instrument that measured it, or says `NOT ADDRESSED`.
- **Every commit verdict below is an oracle verdict, not a screen verdict.** `_main/receipt-20261107-round2.md`
  §7 measured the live instance as `STALE` (`live-code-freshness-oracle.py --strict`: process 2026-11-07
  10:24:53 vs a different disk hash). Nothing here has been seen on the owner's screen.

## (a) In-window complaints and orders — 8 messages (5 complaints + 3 orders)

| id | UTC | session | verbatim | surface named | fixed? |
|---|---|---|---|---|---|
| W1 | 2026-11-07T13:25:09.949Z | `01a1b248` | [Image #1, 381x897] essa escolha da legenda é muito feia. compara como era antes. até a div. remove o "show in folder". tem que ser SOMENTE um icone. e os dois tem que ficar a direita. [Image #2, 382x899]  e na imagem 2, tu percebe que falta varios temas q nao foram modificados. tu vai fazer os temas nao modificados, serem modificados, igual oq tu pode ver no git history. so que tu nao vai manter os defeitos. e ne frase de efeito "the room so far". | panel: visual choice of the caption box, `Show in folder` label, the two glyphs' alignment, theme coverage, `the room, so far` | 0d7e5c6 (2026-11-07T14:48Z) + `_main/receipt-20261107-round2.md` §1 items 1-4; panel-header GREEN 24/24, skin dead-text 87/87, 45 themes 0 clipped. The DIV itself ('ate a div') is not named in the receipt → UNVERIFIED |
| W2 | 2026-11-07T14:26:42.732Z | `01a1b248` | é ridicul o fato que um stutter qualquer do meu pc, faça a legenda dessincronizar ou nao funcionar mais ou demorar pra voltar a ficar certa. sendo que o mecanismo do YOUTUBE devia ser extremamente facil de implementar na legenda ao vivo e extremamente responsivo, entao nao devia se afetar. se a porra da legenda do youtube ta se movendo, mesmo com o stutter acontecendo, a NOSSA legenda que pegamos do youtube, TAMBEM. | live caption: sync vs the YouTube player under a PC stutter | 0d7e5c6 + round2 §5; `stutter-caption-oracle.py` GREEN arms=14 (err 2.312s -> 0.021s on a 3s stutter) |
| W3 | 2026-11-08T04:58:03.751Z | `01a1b248` | começa uma todo list. depois, com base no material, quero que tu entenda exatamente como a animação de entrada da legenda do youtube funciona, e tu vai imitar pro sotto. local://paste-1.md | caption entrance animation (imitate YouTube) | PARTIAL: c403b5d (roll-up, ROLL_S=0.433 bezier(0,0,.2,1), oracle 8/8) + a4739f4 (computed live) + 33c1feb (spec). The full 1:1 entrance was not seen on his screen |
| W4 | 2026-11-08T04:59:16.605Z | `01a1b248` | e eu quero a animação de quando começa uma linha nova e a outra linha vai pra cima | caption: old line rises when a new line starts | c403b5d (commit message quotes this exact order); caption-rollup-oracle PASS 8/8, --neg-arm rc=1 |
| W5 | 2026-11-08T06:30:24.393Z | `01a1b248` | feature nova: segurar control, permite eu arrastar a legenda pra onde eu quero. e o control segurado tambem vai ter um indicativo bem minimo de que da pra arrastar a legenda. talvez algum tipo de glow ou animacao ou outra coisa que é muito facil de entender. | caption placement: Ctrl-drag + minimal affordance (glow/animation) | NOT ADDRESSED — no commit after 05:40Z; session title at 06:32 became `RESUME: Hold Ctrl to drag caption with affordance glow` (work started, nothing landed) |
| W6 | 2026-11-08T06:30:55.883Z | `01a1b248` | por que a porra do painel de baixo do sotto ta gigante? restaura como era antes | panel: size of the BOTTOM panel | NOT ADDRESSED — last commit 5fa6e87 (05:40Z); the uncommitted `app/panel/panel-unified.css` diff touches history rows only, not panel height |
| W7 | 2026-11-08T06:31:41.207Z | `01a1b248` | usa skills pra arrumar: apertar alt c super rapido deixa o app travando pra caralho. deixa completamente flúido. é pra abrir os paineis e qualquer outra coisa super rapido com o alt c sendo spammado. sem travar. | panel: Alt+C spam latency / freeze while opening panels | NOT ADDRESSED — no commit; instrument `_main/hotkey-spam-oracle.py` exists untracked (in flight) |
| W8 | 2026-11-08T06:33:22.920Z | `01a1b248` | VAI LER TODOS OS MEUS PROMPTS QUE JA FALEI NA SESSAO DO SOTTO NAS ULTIMAS 40 HORAS E VEJA QUANDO EU RECLAMEI DO LAYOUT/TEMAS LEGENDAS NO PAINEL E ARRUMA. ESSA LEGENDA TA PATETICA. [Image #1, 371x892] . E TIRA QUALQUER COISA QUE DIZ "READY" EMBAIXO DOS TEMAS. ⏎  ⏎ USA SUBAGENTS PRA TUDO | panel: caption legibility ('PATETICA') + a `READY` caption under the themes + full re-audit of layout/themes/captions | OPEN: legibility half is DARK — uncommitted `HISTORY-LEGIBILITY` block in `app/panel/panel-unified.css` (13.5px floor, Instrument Sans, 60px stamp track); `READY` half NOT ADDRESSED (0 literal `READY` in `app/panel/**`; census lane in flight) |

`W8` has an earlier submission of the same text at 06:33:05Z without the image; the transcript keeps the
re-submitted message (06:33:22.920Z) and that is the one quoted. `W6`/`W7` differ from the history index by
8 s and 3 s; the transcript timestamps are used throughout.

## (a2) Outside-window lineage — the round he is actually pointing at

One prompt, `2026-11-06T04:07:18.146Z`, session `01a1aef6` (H:/pi-agent/sessions/--H--sotto--/
2026-11-06T03-45-42-092Z_01a1aef6-56cc-7250-bb22-d233dab67bfc.jsonl), 10 h **before** the declared window.
It is the origin of the panel/theme/caption work the owner calls "a rodada do dono (24 pedidos)"
(`383a49a`), and `W1` on 2026-11-07 proves several of its items had NOT reached his screen by then.
It is listed here verbatim so the fixes can be driven from the sentence, not from the receipt's elisions.

| id | UTC | session | verbatim | surface named | fixed? |
|---|---|---|---|---|---|
| A1 | 2026-11-06T04:07:18.146Z | `01a1aef6` | no workspace, tem varios designs de LEGENDA e fundo da legenda. quero que tu coloque menu dropdown pra eu escolher. deve aparecer no painel da direita. | theme picker: designs of LEGENDA and its background, in the right panel | 383a49a + receipt-20261106-panel-owner-round.md §1 item 2 (`theme-switch-oracle` PASS, 0 failures) |
| A2 | 2026-11-06T04:07:18.146Z | `01a1aef6` | tira a BARRA de pesquisa de historico, deixa so um botao pequeno com o simbolo de pesquisa. | history: the search BAR | 383a49a + receipt §1 item 3 (`panel-search-keyboard-oracle` PASS, 4 arms) |
| A3 | 2026-11-06T04:07:18.146Z | `01a1aef6` | tambem tira a data de mostrar o historico do painel na direita. | history: the date shown above the list | 383a49a + receipt §1 item 4 (stamp is a bare `<time>`; 45 themes, CLIPPED 0) |
| A4 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outra coisa: o historico tem que persistir, aparecendo no painel da direita, por padrao, ate 48hrs. nao faça isso ser travado ou pesado. | history: 48 h persistence, always shown, never heavy | 383a49a + receipt §1 item 5 (`history-write-oracle` PASS) |
| A5 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e nao é pra DUPLICAR frase nunca no historico. | history: duplicated sentences | 383a49a + receipt §1 item 6 (`history-merge-oracle` PASS arms 22/22) |
| A6 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e nao é pra começar a ativar o historico so quando eu mostro o painel. é pra sempre aparecer no painel. | history: starts only when the panel is shown | 383a49a + receipt §1 item 5 (same oracle) |
| A7 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outra coisa: acha TODOS os temas/layouts dos paineis, e a posicao de botoes ou de logo MAIS COMUM, fixa. significa que se em 20 paineis o botao de trocar pro proximo tema esta na coordenada x, TODOS os temas tem que ficar na coordenada x, o mesmo botao. FIXO. muda EM MASSA isso. e é claro, isso vale pra todos os botoes. | all themes/layouts: button/logo coordinates fixed, changed in mass | 383a49a + receipt §1 items 7 and 18 (`theme-button-geometry-oracle` PASS, 3 checks 0 failed) |
| A8 | 2026-11-06T04:07:18.146Z | `01a1aef6` | o painel de BAIXO deve ser opaco. MEIO transparente. nao 100% solido. já os botoes, pode ser solido. | bottom panel opacity vs button solidity | 383a49a + receipt §1 item 8 (panel-header GREEN 21/21, theme-preview PASS) |
| A9 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outra coisa: pesquisa bem, usa bem as skills, pra implementar o fato de ser possivel mover qualquer painel pela tela. já que agora ta extremamente bugado. a tentativa ta muito falha. [Image #1, 371x891] [Image #2, 371x900] olha como ta bugado. | moving any panel by the screen | 383a49a + receipt §1 item 9 (`panel-drag-targets-oracle` PASS, 12 arms) |
| A10 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e tambem: o historico nao deve ficar centralizado. é começando pela esquerda. | history alignment: left, not centred | 383a49a + receipt §1 item 10 (NOT LEFT-ALIGNED 0 of 45 themes) |
| A11 | 2026-11-06T04:07:18.146Z | `01a1aef6` | alem disso, a segunda imagem mostra que o historico nao ta mostrando em todos os temas. | history missing in some themes | 383a49a + receipt §1 item 10 (list always mounted, 45 themes) |
| A12 | 2026-11-06T04:07:18.146Z | `01a1aef6` | alem disso, os botoes de baixo nao devem existir, desse painel da direita. esse botao de "Hold" é stale, entao pode tirar. ele é configuracao de uma coisa que ja troquei. | bottom buttons of the right panel; the stale `Hold` button | 383a49a + receipt §1 item 11 (`hotkey-hold.css` deleted; DOM probe 87/87) |
| A13 | 2026-11-06T04:07:18.146Z | `01a1aef6` | tira qualquer frase de efeito de qualquer painel e tema, tipo "the room, so far" ou "transcript history". qualquer frase explicativa. | effect phrases in every panel/theme (`the room, so far`, `transcript history`) | 383a49a + receipt §1 item 12 (DOM probe 87/87) |
| A14 | 2026-11-06T04:07:18.146Z | `01a1aef6` | identifica os temas que NÃO tem horario, e faça ter. | themes without a timestamp | 383a49a + receipt §1 item 13 (STAMP UNREADABLE 0 of 45) |
| A15 | 2026-11-06T04:07:18.146Z | `01a1aef6` | alem disso, ao deixar o mouse encima do botao de menu dropdown pra escolher tema, usar o scroll pra cima ou pra baixo deve trocar os temas. | theme dropdown: scroll changes the theme | 383a49a + receipt §1 item 14 (`theme-switch-oracle` PASS) |
| A16 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outra coisa completamente imbecil: o historico CORTA no meio da frase. imagina uma frase com 10 palavras. a cada 3 ou de forma aleatoria, palavras NO meio de outras palavras, somem. entao "banana pera manga" do nada vira "banana manga". a logica ta extremamente errada, tu vai ter que fazer full audit. | history cuts words mid-sentence; full audit of the logic | 383a49a + receipt §1 item 15 (CLIPPED 0, LINE-CLAMPED 0 in 45 themes) |
| A17 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e o negocio de scrollar botao pra aumentar ou diminuir ou ir pra frente ou pra tras: tambem faça essa funcao no botao de aumentar o tamanho da legenda. | caption-size button: scroll to grow/shrink | 383a49a + receipt §1 item 16 (DOM probe 87/87) |
| A18 | 2026-11-06T04:07:18.146Z | `01a1aef6` | o botao de pause tambem nao ta completo. o botao nao muda pra unpause. | pause button never becomes unpause | 383a49a + receipt §1 item 17 (panel-header ARM 7, GREEN 21/21 + pause payload 5/5) |
| A19 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e outra coisa de design: sotto tem que ter o MESMO TAMANHO de logo/letra, na MESMA LINHA/PIXEL. e os botoes tem que ter um PADRAO de espaçamento. tem hora que o botao vermelho que indica se ta "rec" ou não, fica muito distante ou entra dentro de outr obotao. | logo/letter same size, same pixel line, spacing standard, red REC button overlapping | 383a49a + receipt §1 item 18 (`theme-button-geometry-oracle` PASS) |
| A20 | 2026-11-06T04:07:18.146Z | `01a1aef6` | to vendo que ALGUNS temas tem a "legenda ao vivo" inbutida no painel da direita. aquela legenda NAO é pra existir no painel da direita. é pra assistir na legenda que aparece na tela, a que vem do control espaço. | 'legenda ao vivo' embedded in the right panel of SOME themes | 383a49a + receipt §1 item 19 (DOM probe 87/87) |
| A21 | 2026-11-06T04:07:18.146Z | `01a1aef6` | e parece que ta bem burro a insercao no historico. se tem um audio contínuo tocando, ele nao cria as frases e bota no historico, parece que ele simplesmente streama na PRIMEIRA DIV do painel da direita, e a frase vai se cortando e cortando e nunca vai pro historico cada frase. tu deveria saber colocar isso com limite de caractere, ou entao, quando a nossa normalizacao de frases ou palavras sabe quando é um fim de frase. | history insertion of continuous audio: line streams into the FIRST DIV instead of committing sentences | 383a49a + receipt §1 item 20 (`history-write-oracle` PASS) |
| A22 | 2026-11-06T04:07:18.146Z | `01a1aef6` | tambem tem resquicios de um circulo ou quadrado no painel da direita no historico encima/embaixo do HORARIO da legenda/historico, retira isso. isso era de uma DEMO que mostrava personagens naqueles quadrados, mas nao é assim que o sotto deve ser. e tem que ter contraste bom, TODOS os textos no historico vs o horario do texto. de preferencia deixa o horario mais escuro/cinza, e o texto mais "aceso" no seu devido design. | history: square/circle residue around the timestamp; contrast stamp vs text | 383a49a + receipt §1 items 4 and 21 (STAMP UNREADABLE 0, STAMP LOUDER THAN TEXT 0 in 45 themes) |
| A23 | 2026-11-06T04:07:18.146Z | `01a1aef6` | bug que acabei de ver: se eu pauso o video, a legenda do sotto continua por mais uns 2 segundos. | caption keeps running ~2 s after the video is paused | 383a49a + receipt §1 item 22 (`youtube-cdp-source-oracle` PASS 18/18) |
| A24 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outro bug: abrir outro video e ter os dois tocando ao mesmo tempo, ainda continua o ultimo video, inves de dar prioridade ao novo. e obviamente, se eu voltasse pro outro video, daria prioridade pro outro video. se eu desse alt tab, ainda ficaria naquele ali. | two videos: priority to the new tab / Alt-Tab | 383a49a + receipt §1 item 23 (same oracle) |
| A25 | 2026-11-06T04:07:18.146Z | `01a1aef6` | outra coisa: a legenda para, com esse caso de uso de dois videos do youtube. ela tambem buga se eu desativo ela e o video ao mesmo tempo (ja que o control espaço passa pelo pause do video). | caption stops / misbehaves with two videos and when disabled together with the video | 383a49a + receipt §1 item 24 (`ctrlspace-swallow-oracle` PASS 19/19) |

Not carried into the annex because they are not panel surfaces: the two `control espaço` sentences at the
head of the same prompt ("nao deve \"vazar\" pra outros apps" / "isso faz o espaço pausar o video"), and
the process order ("QUEBRA meu prompt em varias etapas").

Also seen in the window and deliberately **not** counted as panel complaints: `2026-11-07T15:05:41.601Z`
("eu ja mandei tu fazer o icon ser responsivo. essa porra eu aperto botao direito e nao responde quando meu
sistema ta sob carga. os outros icones de outros apps sim.") and the `desativar atalho alt c` tray-menu
order a few minutes later (`15:18:25.907Z`, `15:18:46.131Z`) — those are the tray icon/menu, not the panel. The 27
machine `Herdr DM from …` injections (STUTTER/COMPLAINT/pop-injector) are not owner sentences and are
excluded by the verbatim rule.

## (b) Complaint class → complaints, ranked by repetition

Counts are **rows**, primary class each: 8 in-window (`W`) + 25 lineage (`A`) = 33. `READY` is a sub-item of W8, so it is not an extra row.

| rank | class | n (rows) | in-window rows | lineage rows | row ids |
|---|---|---|---|---|---|
| 1 | history list: search bar, date, persistence, duplication, alignment, coverage, cutting, insertion | 9 | 0 | 9 | A2 A3 A4 A5 A6 A10 A16 A21 A22 |
| 2 | themes/colors: coverage, unified geometry, effect phrases, timestamp, dropdown scroll, embedded caption | 8 | 0 (named inside W1 and W8) | 8 | A1 A7 A8 A11 A13 A14 A15 A20 |
| 3 | caption sync vs the player: stutter, pause lag, two videos, disable race | 4 | 1 | 3 | W2 A23 A24 A25 |
| 4 | panel chrome/controls: Hold buttons, caption-size wheel, pause/unpause, spacing, REC button | 4 | 0 | 4 | A12 A17 A18 A19 |
| 5 | caption legibility/typography: font, size, air, what the line looks like | 2 | 2 | 0 | W1 W8 |
| 6 | caption animation/entrance: new line, old line rises, YouTube 1:1 | 2 | 2 | 0 | W3 W4 |
| 7 | moving panels / caption placement by hand | 2 | 1 | 1 | A9 W5 |
| 8 | bottom panel size ("ta gigante") | 1 | 1 | 0 | W6 |
| 9 | panel open latency under Alt+C spam | 1 | 1 | 0 | W7 |
| 10 | `READY` text under the theme cards | 1 (sub-item of W8) | 1 | 0 | W8 |

## (c) THE 10 THINGS HE ASKED FOR THAT THE PANEL STILL DOES NOT DO

Verbatim, in his order. Status says what the tree has, not what his screen shows.

1. "por que a porra do painel de baixo do sotto ta gigante? restaura como era antes" — **LANDED `02f6df9` (2026-11-08T03:58:17-03:00 = 06:58Z), NAO no ecra dele.** Medido no `webview-run.log` dele: a faixa abriu `1040x40 @(440,948)` as 03:30:29 contra `380x40 @(770,948)` de 2026-11-07 10:22 -- 660 px mais larga. `STRIP_WIDTH = 1040 -> 380`.
2. "ESSA LEGENDA TA PATETICA" — **LANDED `c7516b2` (2026-11-08T06:49:21Z), NAO no ecra dele.** O bloco `HISTORY-LEGIBILITY` esta em `app/panel/panel-unified.css`; a linha do historico deixou de usar a face de display do tema em `--size-small` (9 px) e ganhou um piso de 13,5 px.
3. "E TIRA QUALQUER COISA QUE DIZ "READY" EMBAIXO DOS TEMAS." — **LANDED `c7516b2`.** A palavra e' composta em `panel.js` (`const word = state === 'live' ? 'ready' : 'not ready'`), que e' por que um grep por `READY` nao a acha; ela passa a ir para a classe que `panel.css:1541` clipa fora do ecra, e o estado vive em `statusDot.dataset.state`. `panel-header-oracle` arm 9 segura o par.
4. "segurar control, permite eu arrastar a legenda pra onde eu quero." — **OPEN — no commit; session title at 06:32 became the work order (`RESUME: Hold Ctrl to drag caption with affordance glow`).**
5. "e o control segurado tambem vai ter um indicativo bem minimo de que da pra arrastar a legenda. talvez algum tipo de glow ou animacao ou outra coisa que é muito facil de entender." — **OPEN — same order, nothing landed.**
6. "apertar alt c super rapido deixa o app travando pra caralho. deixa completamente flúido." — **LANDED `3e9e26b` (2026-11-08T03:47:02-03:00).** Medido no log dele: 17 toques com gap <300 ms e cada um rodava a transicao inteira, 416-700 ms do toque ao `PANEL_SHOWN`. Agora os toques CONTAM. Instrumento `_main/hotkey-spam-oracle.py`, passo `hotkey-spam` + o seu `--neg-arm` na bateria.
7. "é pra abrir os paineis e qualquer outra coisa super rapido com o alt c sendo spammado. sem travar." — **LANDED `3e9e26b`**, same commit as 6; a medida que decide e' o gap entre toque e `PANEL_SHOWN`, nao a intencao.
8. "VAI LER TODOS OS MEUS PROMPTS QUE JA FALEI NA SESSAO DO SOTTO NAS ULTIMAS 40 HORAS E VEJA QUANDO EU RECLAMEI DO LAYOUT/TEMAS LEGENDAS NO PAINEL E ARRUMA." — **EXECUTED — this file is that read; the fixes are items 1-7.**
9. "e na imagem 2, tu percebe que falta varios temas q nao foram modificados." — **COMMITTED 0d7e5c6, NOT ON HIS SCREEN — 45 themes, 0 clipped/stamp failures, but the live instance predates the commit (STALE).**
10. "é ridicul o fato que um stutter qualquer do meu pc, faça a legenda dessincronizar ou nao funcionar mais ou demorar pra voltar a ficar certa." — **COMMITTED 0d7e5c6, NOT ON HIS SCREEN — stutter-caption-oracle GREEN 14/14; STALE instance still runs the old clock.**

## Evidence: sources searched, and the one prompt that is unrecoverable

| source | what was done | result |
|---|---|---|
| `H:/pi-agent/history.db` (1816 rows) | SQL over `cwd LIKE '%sotto%'`, `created_at` in window and in 2026-11-05→11-07 | 54 rows in window, **27** of them machine `Herdr DM` injections; **no** owner row between 04:07:18Z and 22:05:59Z on 2026-11-06 |
| `H:/pi-agent/sessions/**/*.jsonl` | 281 transcripts with mtime ≥ window start-1h; parsed every `role:user` entry; 629 messages inside the window across all projects | 52 user messages in `01a1b248`; 1 in `01a1aef6`; 0 in-window in the other 4 Sotto sessions |
| `archive` helper | `sessions(project="*")` → 6 Sotto sessions; `prompts(project="H:\\sotto")` → 269 unique, 53 submitted in window | confirms the same population |
| compaction records | all 11 `snapcompact` records of `01a1b248` + 3 of `01a1aef6` | frames are 11-06 ~01:00 pages; they do not contain the 19:14 message |
| repo | `git log --since=2026-11-06T13:00:00Z`, `git status --short`, `git show` of 383a49a / 0d7e5c6 / c403b5d / a4739f4 | the shas in the tables |
| receipts | `_main/receipt-20261106-panel-owner-round.md`, `_main/receipt-20261107-round2.md`, `_main/receipt-20261108-rollup-live.md` | oracle verdicts quoted above |

**Unrecoverable: the owner's prompt at 2026-11-06T19:14:14Z.** The session `01a1b248` was created at
19:14:01Z with the title `🔁 RESUME: Implement caption animation in caption_overlay`; a
`custom_message/skill-prompt` (`project-revival`) is stamped 19:14:14.605Z and the assistant reply of that
turn (19:14:14.981Z) has empty content, i.e. the turn died before persisting. There is no `role:user`
entry for it in the JSONL, `history.db` has no row at that second, and the archived compaction text begins
with the skill body and jumps straight to the 22:05:59Z Herdr DMs. It is **inside** the window and its text
cannot be quoted; it is not counted anywhere above.

## Appendix — completeness inventory (every owner-typed message in the window)

`01a1b248` holds **26** owner-typed messages between 2026-11-07T13:10:27Z and 2026-11-08T06:33:22Z (the other
26 `role:user` entries are machine `Herdr DM from …` injections, excluded by the verbatim rule). 11 are
reported above (W1-W8 + the 3 tray-icon exclusions); the remaining 15 are below, verbatim, and none of them
names a panel surface. `/compact` (typed 52× historically, one row in `history.db` at 06:29:38Z) is a
harness command and is not a `role:user` entry.

| UTC | verbatim |
|---|---|
| 2026-11-07T13:10:27.326Z | ignora o herdr dm. continua oq tu tava fazendo |
| 2026-11-07T13:13:07.603Z | do both |
| 2026-11-07T13:22:15.235Z | me fala qual sua tarefa atual |
| 2026-11-07T13:34:43.785Z | WE CRASHED, CONTINUE WITH ALL. RESUME SUBAGENTS IF YOU HAD |
| 2026-11-07T15:04:59.459Z | qq falta |
| 2026-11-08T04:10:47.929Z | checa essa sessao aqui, onde eu falei de parakeet ultra. me fala se tu ja implementou ele. vai procurar meus prompts |
| 2026-11-08T04:11:31.448Z | tem certeza que o parakeet ultra é tao pior assim? foi medido errado, por acaso? oq garante que mediu da forma correta? vai pesquisar |
| 2026-11-08T04:12:01.879Z | CALMA AI. tu ta vendo MEUS PROMPTs POR QUAL FERRAMENTA? tu acabou de ler meus prompts de OUTRO projeto |
| 2026-11-08T04:12:44.452Z | vai medir de novo do jeito certo agora. |
| 2026-11-08T04:12:57.016Z | e é pra ser GPU. |
| 2026-11-08T04:47:33.595Z | ta demorando por que |
| 2026-11-08T04:48:25.172Z | vai na sessao que a gente ta mesmo e procura meus prompts. é pra tu ver se é o modelo parakeet ultra mesmo que eu queria que fosse medido. que eu me lembre, ele é até mais barato de rodar e melhor que o redux. |
| 2026-11-08T04:53:09.044Z | pesquisa como q faz direito |
| 2026-11-08T04:58:29.829Z | faz em paralelo |
| 2026-11-08T06:31:52.972Z | e inicia uma todo list |

## Counts

- In-window panel messages: **8** (5 complaints: W1 W2 W6 W7 W8; 3 orders: W3 W4 W5).
- In-window owner-typed messages in `01a1b248`: **26**; accounted for: 8 panel + 3 tray-icon exclusions + 15 non-panel (appendix) = 26.
- In-window strict complaints about panel layout/themes/captions: **5**.
- Lineage rows (outside window, same round): **25**.
- Total verbatim rows: **33**. Total complaint units (incl. the `READY` sub-item): **34**.
- First in-window Sotto transcript timestamp: 2026-11-06T22:05:59.697Z (a machine Herdr DM; first
  owner-typed 2026-11-07T13:10:27.326Z; first panel complaint 2026-11-07T13:25:07.351Z).
- Last transcript timestamp: 2026-11-08T06:35:09.449Z (machine Herdr DM; last owner-typed 06:33:22.920Z).

