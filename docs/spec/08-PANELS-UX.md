# 08 — PAINÉIS E UX: o que ele vê e como conduz

Este ficheiro descreve a superfície que o dono toca: as duas teclas globais, o `Alt+C` com double em `DOUBLE_TAP_S = 0,40 s`, a janela da legenda, a geometria das duas páginas, o arrasto, os temas, a busca e o menu PT-BR do ícone. Cada frase factual leva etiqueta; as frases de 2026-11-25 foram lidas no código em disco e verificadas com os oráculos nomeados. O anexo de decisões é `docs/hotkey-gestos.md`; aqui mede-se o que o código faz.

## 1. As superfícies que ele vê

| superfície | o que é no ecrã | evidência |
|---|---|---|
| **faixa de baixo** (`strip`) | barra curta: legendas vivas e poucos botões; rect 380×40 @ (770,948) | `[CODE]` `body[data-surface="strip"]` (`app/panel/panel.css:1526`); `[MEASURED]` `grep "PANEL_SURFACE surface=strip" _main/webview-run.log \| tail -1` → `2026-11-11 00:48:49.103 ... window=380x40@(770,948) docked=bottom-strip edit_mode=false` (2026-11-11) |
| **painel da direita** (`panel`) | coluna completa: cabeçalho, transcrição, histórico, busca; rect 380×900 @ (1528,12) | `[CODE]` `SURFACES = ['strip','panel']` (`app/panel/surface.js:35`); `[MEASURED]` `grep "PANEL_SURFACE surface=panel" _main/webview-run.log \| tail -1` → `2026-11-11 00:48:54.648 ... window=380x900@(1528,12) docked=right edit_mode=false` (2026-11-11) |
| **legenda nativa** | janela PRÓPRIA, alfa por pixel, sem placa de WebView2 | `[CODE]` "No WebView2, no colour key, no plate" (`app/webview/caption_overlay.py:16`); "ela é livre na minha tela" (`app/webview/sotto_webview.py:21614`) |
| **escondido** | nada mapeado — o resultado de um toque na faixa fora da janela do double, ou de um toque no painel | `[CODE]` `hide_panel` (`app/webview/sotto_webview.py`); `next_action` (`app/webview/hotkey_gesture.py:232-242`) |
`[INFERENCE]` São duas páginas numa só janela, alternadas por um atributo (`app/panel/surface.js:10-16`), mais uma janela nativa que o painel não possui: esconder o painel não apaga a legenda, porque `hide_panel` só chama `_blank_caption_window` quando `_caption_wanted` está falso (`app/webview/sotto_webview.py:16486-16530`).

## 2. `Alt+C` — double promove, toque simples não

| estado antes do toque | o ecrã | evidência |
|---|---|---|
| escondido | faixa de baixo, no mesmo instante | `[CODE]` `if not visible: return True, 'strip'` (`app/webview/hotkey_gesture.py:232-233`) |
| faixa mostrada por Alt+C há ≤ `DOUBLE_TAP_S = 0,40 s` | painel da direita (promoção) | `[CODE]` `DOUBLE_TAP_S = 0.40` (`hotkey_gesture.py:111`) e `next_action` (`hotkey_gesture.py:234-242`) |
| faixa com show mais antigo, ou mostrada por outra via | escondido | `[CODE]` `since_show_s = None` (`app/webview/sotto_webview.py:18093-18099`) |
| painel da direita | escondido | `[CODE]` `return False, str(surface)` (`hotkey_gesture.py:242`) |

Três invariantes que o código sustenta:

1. **Um `WM_HOTKEY` = um passo, imediato** — o primeiro toque não espera; a janela de 0,40 s mede a idade do show da faixa, não a duração da tecla, e só existe para o double (`[CODE]` `next_action`, `app/webview/hotkey_gesture.py:201-242`).
2. **A decisão lê a JANELA, não uma intenção**: `window_visible(self.hwnd)` e a última superfície *aplicada* (`surface_applied`), que `hide_panel` não limpa (`[CODE]` `app/webview/sotto_webview.py:18081-18089`).
3. **Nada de trabalho na thread do `RegisterHotKey`**: `_hotkey_dispatch` soma a pressão a um contador e põe um token numa fila FIFO (`[CODE]` `app/webview/sotto_webview.py:18017-18058`); `_hotkey_resolve` drena a rajada e chama `hotkey_numbers().advance(...)` uma vez (`[CODE]` `app/webview/sotto_webview.py:18060-18158`).

`[MEASURED]` 2026-11-25: `python _main/altc-gesture-oracle.py` → `ALTC-GESTURE GREEN -- arms=104 pass=104 fail=0`; o braço negativo derruba o oráculo nos seus seis mutantes (`ALTC-GESTURE VERMELHO`, entre `fail=2` e `fail=17` cada), `NEG-ARM PASS -- RED as designed`, rc=1. O log alive carrega `HOTKEY_COALESCED ... double_since_ms=` (`app/webview/sotto_webview.py:18147-18149`), que distingue o double do toque isolado.

O show da faixa, em ordem: `PANEL_SURFACE surface=strip` → `WEBVIEW_CHILD` → `PANEL_SHOW_COST` → `PANEL_SHOWN reason=... mode=strip`; a direita usa `show_side` (`[CODE]` `app/webview/sotto_webview.py:18356`). A monitor escolhido é o do cursor/work area, por `select_display_for_point` (`docs/shell-contract.md`, §2026-11-25).

## 3. `Ctrl+Space` — o interruptor da legenda ao vivo

Uma pressão comuta o interruptor do dono, não os pixels (`[CODE]` `app/webview/sotto_webview.py:16659-16681`). O corpo, em ordem:

1. `_hotkey_resolve('live')` lê `_caption_wanted` e inverte-o; `shown` fica no log como diagnóstico (`[CODE]` `app/webview/sotto_webview.py:16659-16680`).
2. `_set_live_enabled({'on': ...})` grava, loga `LIVE_ENABLED on=... wanted=... panel_closed=false` **antes** do trabalho de UI, e só depois mostra/esconde a janela (`[CODE]` `app/webview/sotto_webview.py:21615-21650`).
3. Ligar não espera pela próxima linha: uma pintura com menos de `CAPTION_REPLAY_MAX_S` volta com `CAPTION_WINDOW_REPLAYED age_ms=... paused=... player=...` (`[CODE]` `app/webview/sotto_webview.py:21670-21683`).

**O interruptor corta o DISPLAY e mais nada.** A lei do dono está em `AGENTS.md` §3 ("LEGENDA AO VIVO DESLIGADA NÃO É MODELO DESLIGADO"), e o código cumpre-a por construção: `push_caption_to_window` só escreve com a flag ligada, e a docstring diz que `hide_panel('caption-on')` foi removido (`[CODE]` `app/webview/sotto_webview.py:21589-21614`). `show_caption_window` só chama `ov.show(True/False)` (`[CODE]` `app/webview/sotto_webview.py:19065-19120`), logo worker, modelo e histórico não são tocados.

`[MEASURED]` `grep -c LIVE_ENABLED _main/webview-run.log` → **33**; `grep -c HOTKEY_LIVE_STEP` → **31**
(2026-11-11). A linha do passo, verbatim: `HOTKEY_LIVE_STEP caption_on=false shown=true wanted=true`
(2026-11-11 17:41:48.197).

## 4. Em jogo, o `Ctrl+Space` é devolvido ao jogo

A tabela é pura: `gaming_mode.live_hotkey_plan(gaming, registered, register_failed)` (`[CODE]`
`app/webview/gaming_mode.py:497-539`).

| em jogo? | plano | o que acontece |
|---|---|---|
| não, tecla tomada | `take` | `RegisterHotKey` + `MOD_NOREPEAT` **e** o hook `WH_KEYBOARD_LL` (`[CODE]` `app/webview/sotto_webview.py:8080-8100`) |
| não, registo recusado (`1409`) | `stay-free` | observador passivo; a tecla passa e o log diz `swallow=false the_key_passes_through=true` (`[CODE]` `app/webview/sotto_webview.py:8096-8104`) |
| sim | `give-back` | `UnhookWindowsHookEx` **antes**, `UnregisterHotKey` depois (`[CODE]` `app/webview/sotto_webview.py:8106-8118`) |

O que impede o espaço de vazar é o hook, não o registo: a docstring regista a premissa medida e errada
de que `RegisterHotKey` tirava a tecla do caminho de input (`[CODE]` `app/webview/space_swallow.py:1-51`).
A classificação é pura — engole `VK_SPACE` com `Ctrl` físico em baixo, **uma** alternância por `keydown`
(o auto-repeat não alterna), e declara mentiroso o estado preso passado `STUCK_HELD_S = 3.0` sem `keyup`
(`[CODE]` `app/webview/space_swallow.py:72,130-184`).

A deteção é um fio que **só lê e loga**: `TICK_S = 2.0` com `GAME_DWELL_TICKS = 10` de histerese
(`[CODE]` `app/webview/gaming_mode.py:123-128`) e uma linha por transição, `GAMING_MODE on=... game=...
why=...` (`[CODE]` `app/webview/gaming_mode.py:431-441`). A transição sai como `HOTKEY_LIVE_MODE
role=live mode=swallow|passthrough|free gaming= swallow= hook= registered= plan=` (`[CODE]`
`app/webview/sotto_webview.py:8130-8141`). `[INFERENCE]` O `Alt+C` fica sempre registado (só o papel `live` passa pelo plano e pelo `LiveHotkeyThread`, `app/webview/sotto_webview.py:10383-10390`), logo dentro do jogo a legenda liga-se pelo `Alt+C` ou pelo botão LIVE do painel.

## 5. O arranque: a legenda ABRE ligada

Ordem do dono, verbatim (2026-11-11): *"as soon as i open it, should start the subtitles in my screen.
the ctrl space."* A decisão é pura, `SottoShell.caption_wanted_at_start(args, stored=None, env=None)`
(`[CODE]` `app/webview/sotto_webview.py:21508-21552`), e avalia por esta ordem:

| condição | devolve | `reason` no log | evidência |
|---|---|---|---|
| `SOTTO_CAPTION_WANTED_DEFAULT` é `0`/`1` | esse valor | `env(SOTTO_CAPTION_WANTED_DEFAULT=0)` | `[CODE]` `sotto_webview.py:21536-21541` |
| `SOTTO_LANE_LAUNCH=1` | `false` | `lane(SOTTO_LANE_LAUNCH=1)` | `[CODE]` `sotto_webview.py:21547-21549` |
| flag de medição presente | `false` | `measurement-flag(--dump-dom)` | `[CODE]` `sotto_webview.py:21550-21552` |
| nada disto | `true` | `default` | `[CODE]` `sotto_webview.py:21552` |

**O ficheiro deixou de mandar no arranque.** `_main/caption-wanted.json` continua a ser LIDO, mas não
suprime a abertura: o desacordo vai para o log (`[CODE]` `sotto_webview.py:21522-21531`), nas linhas
`CAPTION_WANTED_START on=%s reason=%s stored=%s stored_at=%s` (`[CODE]`
`app/webview/sotto_webview.py:21566-21569`) e `CAPTION_WANTED_START_OVERRIDES stored=false -- o arranque
liga a legenda (...)` (`[CODE]` `app/webview/sotto_webview.py:21570-21573`).

As excepções não são gosto: são a lei do ecrã (`SOTTO_NEVER_ON_OWNER_SCREEN`), e a tabela de flags é **a
mesma** que o worker usa para não pagar o modelo — `MEASUREMENT_FLAGS` (`[CODE]`
`app/webview/sotto_webview.py:12488-12497`), lida por `_measurement_flag` (`[CODE]`
`app/webview/sotto_webview.py:12500-12510`): `--dump-dom`, `--selftest`, `--memory`, `--no-hotkey`,
`--exit-after`, `--probe-stats`, `--probe-outside-click`, `--probe-edit-mode` e `--probe-v2`.

**O que ele quer continua gravado, e não decide o arranque.** O interruptor escreve `{'on': bool, 'at':
ISO}` por temporário + `os.replace` (`[CODE]` `app/webview/sotto_webview.py:21576-21587`); na abertura
`_caption_wanted` é o resultado da função pura e, se for `true`, `_caption_show_pending` fica armado para
a janela nascer visível (`[CODE]` `app/webview/sotto_webview.py:12892-12900`).

`[MEASURED]` (2026-11-11) `$ cat _main/caption-wanted.json` → `{"on": false, "at":
"2026-11-11T17:41:48"}`; `grep -c CAPTION_WANTED_START _main/webview-run.log` → **0**; a última linha do
assunto é `2026-11-11 20:00:59.992 ... CAPTION_WANTED_RESTORED on=false from=2026-11-11T17:41:48`.
`[INFERENCE]` A instância viva corre código ANTERIOR ao `HEAD` (a linha `RESTORED` já não existe no
caminho novo): a ordem está **corrigida no código e NÃO verificada na tela**, como em `10-DEFECTS.md`
§D-02.

## 6. Geometria e arrasto

### 6.1 A largura da faixa de baixo

`[CODE]` O caminho padrão é `dock_strip(work, width=self.strip_width_live(), height=self.strip_height)`
(`app/webview/sotto_webview.py:20782-20783`), que centra a barra e a limita a `work - 2*margin`, com
`STRIP_MARGIN = 44` (`app/webview/sotto_webview.py:7456-7480`). A largura vem da **página**:
`strip_width_from_dom` mede o `getBoundingClientRect()` de `.panel` (`[CODE]`
`app/webview/sotto_webview.py:20834-20866`) e **recusa** a leitura quando a página é a janela — "medir a
janela não é medir o conteúdo" (`[CODE]` `app/webview/sotto_webview.py:20898-20904`).

`[MEASURED]` com a leitura recusada, a queda é `STRIP_WIDTH = 380` (`[CODE]`
`app/webview/sotto_webview.py:3162`), e o log diz as três coisas: `STRIP_WIDTH source=content refused
value=380 window=380 reason=self-measure why=panel-fills-window` e `STRIP_WIDTH source=fallback value=380
reason=warm-startup why=content-unavailable` (2026-11-11 20:01:03.558). A altura é da folha:
`STRIP_HEIGHT from=148 to=40 source=css css_value=40` (2026-11-11 20:01:03.556). `[INFERENCE]`
1032 − 40 − 44 = 948, que é o `y` medido em §1.

`[CODE]` Há uma segunda regra, `strip_geometry`, que derivaria 62 % da área de trabalho limitada a
320..1040 (`app/webview/sotto_webview.py:7296-7325`), mas **nenhum caminho de produção a chama**:
`[MEASURED]` `grep -rn "strip_geometry(" app/webview/*.py` →
`app/webview/sotto_webview.py:7296:def strip_geometry(...)` (uma linha, 2026-11-11), e os
consumidores no repo são oráculos e mutantes. `[INFERENCE]` É código não ligado (UNWIRED); a largura que
ele vê é a da pílula, não uma fracção.

### 6.2 O painel da direita

`[CODE]` `dock_right` usa `PANEL_WIDTH = 380`, `PANEL_HEIGHT = 900`, `PANEL_MARGIN = 12` e nunca passa
`PANEL_MAX_WORK_FRACTION = 0.34` da largura útil; fica encostado ao TOPO, não centrado
(`app/webview/sotto_webview.py:168-174,2750-2790`). `[MEASURED]` `window=380x900@(1528,12) docked=right`
numa área de trabalho 1920×1032 (`_main/panel-visibility.json`, lido 2026-11-11).

### 6.3 Arrastar o painel e a faixa

`[CODE]` Quem arrasta é o **Windows**, não a página: `pointerdown` no cabeçalho ou na barra pede
`ReleaseCapture()` + `WM_NCLBUTTONDOWN` com `HTCAPTION` (`app/panel/strip-drag.js:10-22`), que entra no
`beginWindowDrag` do bridge (`app/panel/strip-drag.js:36`; `app/webview/sotto_webview.py:10885-10887`) e
chega a `_begin_window_drag` (`app/webview/sotto_webview.py:21395-21448`). No fim do loop nativo,
`_persist_dragged_geometry` fixa o rect, faz clamp e grava **uma vez** (`[CODE]`
`app/webview/sotto_webview.py:21449-21495`), com `WINDOW_DRAG_DONE surface=panel to=(...) size=...
from=(...)` (`[CODE]` `app/webview/sotto_webview.py:21497-21498`).

`[CODE]` O destino é a chave `geometry` de `_main/panel-visibility.json` (`[CODE]`
`app/webview/sotto_webview.py:815,11786`), lida no arranque por `restore_saved_geometry`, que volta a
fazer clamp e loga `PANEL_GEOMETRY_RESTORED` / `PANEL_GEOMETRY_CLAMPED` (`[CODE]`
`app/webview/sotto_webview.py:21846-21898`). O caminho JS antigo da faixa sobrevive **só** para um host
sem `beginWindowDrag`, e o shell real expõe o membro (`[CODE]` `app/panel/strip-drag.js:36,48-53`); o
desvio que ele grava (`localStorage['sotto:strip-offset']`, `{x,y,v}`) continua a ser lido no show
(`[CODE]` `app/webview/sotto_webview.py:21154-21193`), que loga `STRIP_DRAG_RESTORED offset=...`
(`[CODE]` `app/webview/sotto_webview.py:21068-21069`).

### 6.4 Arrastar a legenda

`[CODE]` Arrastar exige **Ctrl carregado + botão esquerdo + cursor dentro do rect**, e a pressão tem de
ser NOVA (`drag_plan`, `app/webview/caption_drag.py:199-270`). O destino é `cursor − pega`, limitado à
área de trabalho **em cada tick**; largar só grava se mexeu (`app/webview/caption_drag.py:247-262`), e
enquanto o Ctrl está em baixo há uma marca mínima pulsante (`app/webview/caption_drag.py:41-46,178-198`).

`[CODE]` O deslocamento persiste em `_main/caption-drag-offset.json` (`STATE_PATH`,
`app/webview/caption_drag.py:36`), lido na construção do overlay (`app/webview/caption_overlay.py:620`) e
gravado no fim do arrasto (`app/webview/caption_overlay.py:1171`); ausente ou partido vale `(0,0)`
(`app/webview/caption_drag.py:274-284`). `[MEASURED]` (2026-11-11) `$ cat _main/caption-drag-offset.json`
→ `{"x": -40, "y": -81}`; a sessão que o gravou deixou `CAPTION_DRAG_OFFSET x=-40 y=-81 saved=true` e
`CAPTION_DRAG_RATE ticks=49 moves=35 paints=0 seconds=0.403 hz=121.7 target_hz=240 paint_ms=0.00`
(log, 2026-11-11 17:40:09).

## 7. O botão de pausa e o payload `stats`

`[CODE]` O botão é um toggle de três estados pintados por `paintPauseControls` — "Pause · unload the
engines" ↔ "Resume · reload the engines", com `data-paused` no botão (`app/panel/panel.js:3584-3632`). O
clique abre um `<dialog>` que informa e foca **Cancel** (`app/panel/panel.html:1220-1235`,
`app/panel/panel.js:3860-3878`); confirmar chama `bridge.pause({reason: 'panel-confirm'})` (`[CODE]`
`app/panel/panel.js:3891`). O shell pára o worker e responde `{'paused': True, 'text': 'Paused -
engines unloaded'}`, com `WORKER_PAUSED reason=... pid=...` (`[CODE]`
`app/webview/sotto_webview.py:21723-21750`); retomar é o `revive` que já existia (`[CODE]`
`app/panel/panel.js:3634-3662`).

**O estado da pausa viaja no payload `stats`.** `stats()` carimba `paused` nas **duas** saídas — no ramo
do medidor fresco e no da linha `WORKER_STATS` (`[CODE]` `app/webview/sotto_webview.py:20290,20337`) —, e
a página lê-o num só sítio: `fields.paused` muda o estado local (`[CODE]` `app/panel/panel.js:4461-4462`).
Ausente **não** é falso: um payload sem o campo deixa o estado como estava (`[CODE]`
`app/panel/panel.js:4455-4462`). O mesmo payload alimenta a onda com `peak`/`blocks` (`[CODE]`
`app/webview/sotto_webview.py:20230-20300`).

## 8. Temas: escolha, persistência, e a ordem das folhas

`[CODE]` O manifesto lista **30** temas e declara `fallback: 'theme-1'` (`app/panel/themes/themes.js:55-281`);
`[MEASURED]` `grep -c "name: '" app/panel/themes/themes.js` → `30`
(2026-11-11). O documento nasce com `data-theme="theme-1"` escrito à mão, "before any CSS parses"
(`[CODE]` `app/panel/panel.html:10`).

`[CODE]` Trocar de tema é **uma** escrita de atributo — `el.dataset.theme = theme.name`
(`app/panel/theme-switcher.js:961`); nenhuma folha é criada, pedida ou substituída. A escolha persiste em
`localStorage['sotto.theme']` (`STORE_KEY`, `app/panel/theme-switcher.js:42,73-85`), com leitura e escrita
defensivas porque `localStorage` sobre `file://` pode lançar (`app/panel/theme-switcher.js:33-40,62-71`).
O shell confirma que o perfil WebView2 é persistente, logo "um tema escolhido numa sessão anterior pode
ser o tema desta" (`[CODE]` `app/webview/sotto_webview.py:187-190`). No arranque, a escolha gravada é
aplicada antes do `mount`: `api.set(known(stored) ? stored : FALLBACK, { persist: false })`
(`[CODE]` `app/panel/theme-switcher.js:1099-1102`). Ajustes por tema vivem noutra chave,
`localStorage['sotto.theme.tune']` (`[CODE]` `app/panel/theme-tune.js:69,446,499-509`).

### 8.1 `panel-unified.css` carrega em último

`[CODE]` A ordem estática do `<head>` é `themes/fonts.css` → `panel.css` → `caption-float.css` → as cinco
`themes/theme-N.css` → `themes/zipc-panels.css` → `button-contract.css` → `panel-unified.css`
(`app/panel/panel.html:48-95`). `panel-unified.css` é a **última `<link>` do documento** (`[MEASURED]`
`grep -n "<link" app/panel/panel.html` → a última é `:95`), e vem depois do contrato de botões para
"settle the boxes the contract does not name" (`[CODE]` `app/panel/panel.html:88-95`).

`[INFERENCE]` "Último no documento" não é "último na rede": as folhas pesadas (`themes/cinematic.css`,
`themes/panel-designs.css`, `skins/skins.js`, `skin-host.js`, `skin-layout.css`) são **adiadas** e chegam
por pedido da página (`[CODE]` `app/webview/sotto_webview.py:200-207`), logo podem aplicar-se depois. É
por isso que o desenho medido tem de ser re-empurrado.

### 8.2 O dropdown e o `SottoBrand.push`

`[CODE]` O gatilho da lista é `#theme-chevron`, dentro de `.panel__controls` do painel da direita; a lista
`#theme-dropdown` é criada pelo módulo e pendurada no `body` porque `.panel` tem `overflow: hidden`
(`app/panel/theme-switcher.js:117-166,747-760`). Rato por cima ou foco **pré-visualiza sem gravar**;
clicar (ou Enter/Espaço) **grava**; sair ou Escape **reverte** (`[CODE]`
`app/panel/theme-switcher.js:960-963`). A roda anda pelos temas com trava de 120 ms (`[CODE]`
`app/panel/theme-switcher.js:699-724`). `[CODE]` Na faixa, o cabeçalho inteiro — e com ele o gatilho — está
escondido (`body[data-surface="strip"] .panel__header`, `app/panel/panel.css:1526`), tal como o dropdown e
o picker (`app/panel/panel.css:1545-1546`); `[INFERENCE]` trocar de tema é uma acção do painel da direita.

`[CODE]` O desenho medido viaja para a janela nativa: `brand-bridge.js` tira um snapshot dos tokens e
posta `brand-tokens` (`app/panel/brand-bridge.js:477`), com `MutationObserver` sobre `data-theme`, `style`
e `class` mais leituras tardias a 1 800/3 600/5 200 ms, porque uma folha adiada pode chegar depois
(`app/panel/brand-bridge.js:505-524`). `window.SottoBrand` expõe `snapshot`, `push` e `last`
(`[CODE]` `app/panel/brand-bridge.js:526-531`). No shell, `_brand_tokens` chama `_apply_overlay_theme`
(`[CODE]` `app/webview/sotto_webview.py:11899,12226-12235`), que aplica **só a placa** (`plate`,
`rowRadius`, `pad`) e deixa tipografia e tamanho ao player (`[CODE]`
`app/webview/sotto_webview.py:21291-21340`).

## 9. O aspecto da legenda: placa e transparência

`[CODE]` O dono escolhe `plate` (`tight` | `normal`) e `opacity` (0,30..1,00, que escala o alfa da PLACA
e nunca a tinta do texto) — `app/webview/caption_settings.py:22-27,49-60`; o clamp vive num sítio só, no
Python. O painel oferece `#caption-plate-select` e `#caption-opacity-range` (`[CODE]`
`app/panel/panel.js:203-205,2961-2980`), e a transparência mostrada é o INVERSO do alfa, com máximo de
70 % (= alfa 0,30) (`app/panel/panel.js:421-439`). `sendCaptionLook` converte e chama
`bridge.setCaptionVisual({plate, opacity})` (`[CODE]` `app/panel/panel.js:442-447`); o shell grava
primeiro e aplica depois, logando `CAPTION_VISUAL plate=... opacity=... live=...` (`[CODE]`
`app/webview/sotto_webview.py:12187-12222`).

**Onde cada coisa fica:** o valor com autoridade é `_main/caption-settings.json`, escrito pelo shell
(`[CODE]` `app/webview/caption_settings.py:28-45,86-97`); o `localStorage` do painel
(`sotto.captionPlate`, `sotto.captionOpacity`) só serve para a caixa abrir com o que está no ar
(`[CODE]` `app/panel/panel.js:419-427`). Na janela nativa, o ficheiro é lido na construção (`[CODE]`
`app/webview/caption_overlay.py:516-523`) e `set_visual` re-aplica ao vivo (`app/webview/caption_overlay.py:764-789`).
`[MEASURED]` (2026-11-11) o ficheiro tem só `{"target_lang": "pt"}`, logo vigoram os defaults
`plate='tight'`, `opacity=1.0` (`[CODE]` `app/webview/caption_settings.py:23-27`).

## 10. A busca: um glifo que revela o campo

`[CODE]` "Tira a BARRA de pesquisa de historico, deixa so um botao pequeno com o simbolo de pesquisa"
(ordem de 2026-11-06, citada em `app/panel/panel.js:3969-3978`). O `#history-search-button` alterna
`is-searching` em `.history__tools`, revela `#history-search`, foca-o e selecciona o texto; um segundo
clique fecha (`app/panel/panel.js:3981-3997`). Enter corre a busca, Escape fecha, campo vazio limpa
(`[CODE]` `app/panel/panel.js:4003-4022`). A predicação não mudou: `runSearch` usa
`historyApi.search(query, 200)` e repinta a mesma lista (`[CODE]` `app/panel/panel.js:4025-4060`); sem
store a nota é "Search is off · no transcript store" (`app/panel/panel.js:4035-4046`). Markup:
`#history-search-button` e `#history-search` (`[CODE]` `app/panel/panel.html:656,669`).

## 11. O ícone da bandeja e o seu menu


`[CODE]` Cinco itens de texto, com ids fixos para nenhum mudar de número; o menu PT-BR é construído em `app/webview/sotto_webview.py:11100-11151` e o oráculo lê os ids `[1, 4, 5, 3, 2]`.

| id | texto PT-BR | o que faz | evidência |
|---|---|---|---|
| 1 | `Abrir painel` | abre o painel completo | `[CODE]` `sotto_webview.py:11117` |
| 2 | `Sair do Sotto` | `request_exit(0, reason='tray-quit')` — a única saída; o probe encontra-a pelo texto | `[CODE]` `sotto_webview.py:11145`, `_main/tray-quit-probe.py:289` |
| 3 | `Editar posicao da legenda` | alterna o modo de edição da geometria | `[CODE]` `sotto_webview.py:11142-11143` |
| 4 | `Desativar atalho Alt+C` / `Ativar atalho Alt+C` | arma/solta **só** o `Alt+C` e persiste `panels_enabled` | `[CODE]` `sotto_webview.py:11123-11127` |
| 5 | `Desligar legendas (Ctrl+Space)` / `Ligar legendas (Ctrl+Space)` | chama `hotkey_live()` — a MESMA porta da tecla | `[CODE]` `sotto_webview.py:11131-11141` |

`[CODE]` O texto de cada item é a ACÇÃO que ele faz, lido do estado VIVO e não do ficheiro (`panels_state()` / `live_state()`), e o menu só é reconstruído quando o texto muda (`[CODE]` `app/webview/sotto_webview.py:11153-11176`). `[MEASURED]` 2026-11-25: `python _main/tray-menu-oracle.py` → `CHECK arms=27 failed=0`, `VERDICT: PASS` — o mutante que repõe `Open panel` é apanhado. O painel e a faixa também são PT-BR: `Traduzir para:`, `Fundo da legenda:`, `Abrir painel`, `Esconder`, `Pausar`, `Esconder a legenda...` em `[CODE] app/panel/panel.html:411,431,453,971,1020,1078,492`.

## 12. Instrumentos que fixam este contrato

`[CODE]` Todos existem no disco (`ls _main/<nome>`, verificado nesta campanha em 2026-11-11); os veredictos
**não** foram re-corridos aqui.

| instrumento | o que fixa |
|---|---|
| `_main/altc-gesture-oracle.py` | o double em `DOUBLE_TAP_S` e os mutantes que o derrubam (104 arms, medido 2026-11-25) |
| `_main/caption-wanted-default-oracle.py` | a precedência de `caption_wanted_at_start` |
| `_main/hotkey-panels-switch-oracle.py` | o interruptor do id 4 e a persistência |
| `_main/ctrlspace-swallow-oracle.py` | `classify_event` e o hook |
| `_main/tray-menu-oracle.py` | ids, textos e a reconstrução só quando o texto muda |
| `_main/caption-drag-oracle.py` | `drag_plan` e o `clamp_pos` |
| `_main/window-drag-oracle.py` | o arrasto nativo e a persistência do rect |
| `_main/panel-drag-targets-oracle.js` | que elementos da página são pega de arrasto |
| `_main/strip-drag-shell-oracle.py` | o caminho shell do offset da faixa |
| `_main/theme-preview-oracle.js` | dropdown, pré-visualização e "sem chevron na faixa" |
| `_main/caption-plate-oracle.py` | `plate`/`opacity` e o piso de alfa |

## Lacunas

- `[UNKNOWN]` **Se o processo vivo corre este `HEAD`.** Não corri `_main/live-code-freshness-oracle.py`
  nesta campanha; o sinal é indirecto (zero `CAPTION_WANTED_START`, última linha `CAPTION_WANTED_RESTORED
  on=false` às 20:00:59). Fecha-se com a app reaberta e uma linha `CAPTION_WANTED_START on=true
  reason=default` na sessão nova.
- `[UNKNOWN]` **O que ele vê em pixels.** Nada aqui foi medido por captura de ecrã nem por censo de frames;
  "aparece", "legível" e "por cima de tudo" não estão medidos. Fecha-se com captura e censo de janelas,
  nunca pela leitura do código.
- `[UNKNOWN]` **A latência do gesto até ao pixel neste `HEAD`.** O log tem `PANEL_SHOW_COST` de sessões
  anteriores; não re-corri `--selftest` (proibido nesta tarefa). Fecha-se com
  `_main/altc-first-caption-oracle.py` sobre um build fresco.
- `[UNKNOWN]` **Se a lista do dropdown está completa em runtime.** O manifesto declara 30 temas, mas
  `themes/cinematic.css` e `themes/panel-designs.css` são adiadas e podem não ter chegado quando a lista
  abre. Fecha-se com `SottoTheme.list()` e `stats()` na página viva.
- `[UNKNOWN]` **A superfície visual do `theme-tune` (`#tune-button`).** Li a chave de persistência e a regra
  de pré-visualização, não a UI completa (`app/panel/theme-tune.js`, 1 068 linhas, lido em fragmentos).
  Fecha-se lendo o ficheiro inteiro e o `#tune-dialog` no markup.
- `[UNKNOWN]` **Multi-monitor e escala ≠ 1,0.** O clamp é aritmético e testado por função pura, mas não foi
  medido num monitor secundário nem a 125 %/150 %. Fecha-se movendo as duas superfícies e lendo
  `PANEL_GEOMETRY_CLAMPED`.
- `[UNKNOWN]` **O que acontece ao ícone se o Explorer reiniciar.** Existe `TRAY_MENU_FOREGROUND ok=...`
  (`app/webview/sotto_webview.py:9982`), mas não li nem medi a recuperação depois de um `TaskbarCreated`.
  Fecha-se com um reinício do Explorer e o log.
