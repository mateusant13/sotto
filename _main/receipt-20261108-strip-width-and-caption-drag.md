# RECIBO — a faixa de baixo volta a 380, e o Ctrl arrasta a legenda (2026-11-08)

Duas ordens dele, as duas do mesmo minuto (`01a1b248`, 06:30:24Z e 06:30:55Z), as duas medidas
nesta arvore. Onde está escrito `PASS`, o comando está ao lado e foi corrido nesta sessão.

## 1. W6 — *"por que a porra do painel de baixo do sotto ta gigante? restaura como era antes"*

**O QUE MUDOU, medido no log da instância dele (`_main/webview-run.log`):**

| instante | leitura | linha |
|---|---|---|
| 2026-11-07 10:22:40 | `WINDOW_GEOMETRY reason=metrics-hotkey-cycle-strip window=380x40@(770,948)` | `:284356` |
| 2026-11-08 03:30:29 | `STRIP_WIDTH from=None to=1040 source=content` | `:388721` |
| 2026-11-08 03:30:31 | `WINDOW_GEOMETRY reason=surface-strip window=1040x40@(440,948)` | `:388799` |

660 px mais larga, **2,74×** a área. A altura foi ao contrário (−60 px contra o `--strip-height:
100px` de antes), portanto "gigante" só podia ser a largura — e era.

**A CAUSA, e ela é uma tautologia.** `body[data-surface="strip"] .panel` é `position:absolute;
inset:0` (a regra "THE WINDOW IS THE BAR"), logo o rect que `strip_width_from_dom()` lê **é** o
client rect da janela: a leitura devolvia a largura que a janela já tinha, `geometry_for` escrevia-a
no rect salvo, e o número não tinha conteúdo nenhum. Era um ponto fixo a 1040.

**A CURA, duas metades:**

1. `STRIP_WIDTH = 380` (e `STRIP_WIDTH_MIN` 480 → 320, senão o piso recusava o próprio valor). O
   `dock_strip` na área de trabalho dele (1920×1032) cai **exactamente** no rect que ele chama de
   "como era antes": `380x40@(770,948)` — é o que a arm A2 do oráculo mede, não afirma.
2. `content_width_is_self_measure(value, window_width)` — a leitura é **recusada por nome** quando o
   "conteúdo" é a própria janela (`STRIP_WIDTH source=content refused value=1040 window=1040
   reason=self-measure why=panel-fills-window`). A leitura continua viva para o layout que a
   justificou (`max-content` de pill, cujo box **não** é o da janela) e uma largura de janela
   desconhecida nunca é recusa: "não perguntei" não é "é o mesmo número".

**Oráculo:** `_main/strip-width-oracle.py` — 11 arms, as três primeiras sobre o **rect previsto**
(puro), as outras sobre os dois sítios REAIS do shell (`strip_width_from_dom` e
`refresh_strip_width`, com `window_width_dip()` extraído para poder ser injectado — um oráculo que
precisa de abrir uma janela só pode abrir a do dono).
**Medido:** `VERDICT: PASS -- 11/11`; `--neg-arm` arranca a guarda numa cópia → `MUTANT: 8/11`,
`NEG-ARM: PASS` (A4a, A5a, A6 vermelhas), **rc=1** (a convenção da casa: o controlo devolve 1 quando
apanha).

**O que NÃO está verificado:** o rect na tela dele. O valor foi derivado do log dele e da aritmética
do `dock_strip`, e a instância viva que ele está a olhar corre código ANTERIOR (`LIVE_CODE STALE`);
a confirmação exige uma largada, e nenhuma lane abre a app na tela dele.

## 2. W5 — *"segurar control, permite eu arrastar a legenda pra onde eu quero"*

Core puro `app/webview/caption_drag.py` (zero Win32 na decisão) + a fiação em
`caption_overlay._tick/_update` (o MESMO fio de tick, sem hook, sem timer, sem segundo bitmap) + a
marca mínima que ele pediu: contorno de 3 px `#7dd3fc` que **pulsa** com Ctrl segurado e fica
**sólido** a arrastar, desenhado no bitmap do quadro que já existe.

**Oráculo:** `_main/caption-drag-oracle.py` — 11 arms, incluindo os dois cantos do clamp, o clique sem
Ctrl (inerte), a persistência em `_main/caption-drag-offset.json` (JSON partido vale 0,0) e a marca
medida em **PIXEL** (só na banda da borda) com um GDI+ real fora do ecrã.
**Medido:** `VERDICT: PASS (11/11)`; `--neg-arm` muta a decisão → `NEG-ARM: PASS (vermelhas=6/11:
P1, P4, P5, P6, P7, P9; exigidas=P4, P7, P9)`.

**Custo medido** (relatório da lane): ~0,28–0,33 ms de CPU por quadro ARMADO (≈1 % de um núcleo a
30 Hz), poll ocioso ~0,3 ms/s **sem repintar**.
**DARK:** o arrasto real contra o cursor, o aspecto composto sobre o vídeo e DPI≠1 — nenhum se mede
sem a app na tela dele.

## 3. Gates

| gate | veredicto |
|---|---|
| `strip-width-oracle` | PASS 11/11, `--neg-arm` rc=1 |
| `caption-drag-oracle` | PASS 11/11, `--neg-arm` PASS |
| `caption-tick-thread` | 5/5 (o fio de tick continua UM) |
| `panel-header-oracle` | 27/27 (arm 9: a palavra `ready` fora do ecrã, o ponto com o estado) |
| `panel-history-clip-probe` | 45 temas, 0 CLIPPED / 0 LINE-CLAMPED / 0 STAMP UNREADABLE |
| `undefined-names` | GREEN, 19 ficheiros, 0 nomes sem definição |
| `code-health` | PASS (crescimento declarado absorvido: `panel.js`, `hotkey_gesture.py`, `sotto_webview.py`, `caption_overlay.py`, `panel-unified.css`) |
| `battery-wiring` | PASS, `ligados=155 sem_passo=109 populacao=264` |
| `battery-class` | PASS, arms=3 |
| `agents-md-pins-oracle` | PASS (pin 282682 B / 3428 CRLF) |

## 4. O QUE NÃO ESTÁ VERIFICADO (dito, não escondido)

Nada disto foi visto na tela do dono nesta rodada: a prova é jsdom + oráculos + aritmética do
`dock_strip`, e a instância que ele olha é anterior ao código. `verified` continua a exigir uma
corrida real da app, pela mão dele.
