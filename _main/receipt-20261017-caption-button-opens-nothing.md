# RECEIPT — o botão de legenda não abre nada (2026-10-17)

O dono, verbatim, e este ficheiro existe porque o código o desobedecia:

> "ao clicar no botao de legenda, nao deve abrir qualquer coisa. é pra ativar a
> legenda, na minha tela, sem background, sem estar conectada a qualquer painel.
> ela é livre na minha tela, um overlay"

E o painel tem de ser o da imagem de referência: **curto e simples**, uma barra.

---

## 1. O que um clique fazia, medido

`_main/webview-run.log`, 2026-10-17, um clique no botão LIVE:

```
21:40:12.621  STRIP_HEIGHT from=40 to=220 source=css css_value=220 reason=surface-strip-float-on
21:40:12.638  PANEL_SURFACE surface=strip reason=strip-float-on window=380x220@(770,768)
21:40:12.643  PANEL_SURFACE surface=strip reason=float-on      window=380x220@(770,768)
```

A janela do dono crescia **180 px** (380x40 → 380x220) por causa de um botão que
só devia acender uma legenda. E seis segundos depois, sozinho:

```
21:43:51.360  CAPTION_WINDOW_IDLE_HIDDEN after_s=6.0 reason=no-caption
21:43:51.362  STRIP_HEIGHT from=220 to=40 reason=surface-strip-float-off
21:43:51.376  PANEL_SURFACE surface=strip reason=float-off window=380x40@(770,992)
```

Isto é a barra a crescer e a cair sozinha, sem o dono tocar em nada.

## 2. As três escritas que abriam a janela

Não era uma. Um clique produzia duas linhas `PANEL_SURFACE` com 5 ms de diferença
porque havia **dois** escritores e cada um pedia o resize por si:

| # | quem | o que escrevia |
|---|---|---|
| 1 | `panel.js applyFloat` | `setStripHeight(FLOAT_HEIGHT)` → `--strip-height: 220px` |
| 2 | `panel.js applyFloat` | `bridge.setPanelSurface('strip', 'strip-float-on')` |
| 3 | `caption-float.js setFloat` | `window.sotto.setPanelSurface('strip', 'float-on')` |

O shell lia a variável de volta em `refresh_strip_height` (`sotto_webview.py:7970`)
e encostava a janela a ela. Cortar só a #2 não resolvia: a #3 fazia o mesmo.

## 3. O "background" era a página, não a legenda

`caption-float.css:69` fazia `html[data-float="on"], body[data-float="on"]
{ background: transparent }` — exactamente no instante do clique.

E a janela do painel **não é layered**: `WS_EX_LAYERED` é opt-in e está desligado
por omissão (`sotto_webview.py:4969`), confirmado ao vivo nesta sessão:

```
panel setAlwaysOnTop(floating) ok style=WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_TRANSPARENT
```

Numa janela WinForms opaca, `transparent` na página não revela o ambiente — revela
o que o formulário não pinta, que é **branco**. Essa era a laje e os cantos
brancos. Os pixels da legenda já eram transparentes; o que aparecia era a página
por trás deles.

## 4. O botão era decoração

`push_caption_to_window` era chamado sem condição por cada linha de legenda
(`:7231` ASR, `:7273` externa), e o log mostra a janela a subir **sem nenhum
clique**:

```
21:41:00.242  CAPTION_OVERLAY_PUSH count=1 visible=true hwnd=1775132 text="15 mil há 8 h"
```

`"15 mil há 8 h"` é o contador de visualizações da página do YouTube, não uma
legenda. O botão ligava o que já estava ligado.

## 5. O que foi feito

| ficheiro | mudança |
|---|---|
| `app/panel/panel.js` | `FLOAT_HEIGHT` **eliminado**; `applyFloat` não escreve altura nem chama `setPanelSurface`; nova guarda `shellOwnsCaptionWindow()` |
| `app/panel/caption-float.js` | `setFloat` deixou de pedir o resize ao shell |
| `app/panel/caption-float.css` | eliminada a regra que punha a página transparente |
| `app/webview/sotto_webview.py` | `_caption_wanted` (o interruptor do dono); `push_caption_to_window` passa a depender dele; `_blank_caption_window` tira só os pixels; `_caption_idle_hide` e `hide_panel` já não desligam nada; retirada a segunda porta (`float-on`) |

A regra da guarda: **um shell que tem janela de legenda própria não leva nada
daqui**. O botão pede a janela ao shell (`requestCaptionOverlay`) e pinta-se a
partir do que o shell respondeu (`data-caption-window`). O que fica é o caminho
antigo, só para probe de browser — um shell sem `setLiveEnabled` não tem janela
de legenda, e ali a página é a legenda.

## 6. A legenda é a janela nativa

`app/webview/caption_overlay.py`, `WS_EX_LAYERED | WS_EX_TRANSPARENT |
WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST`, desenhada com
`UpdateLayeredWindow` e um DIB ARGB pré-multiplicado: alfa por pixel, cliques
passam para o vídeo, nunca rouba o foco, nunca entra na barra de tarefas. Mede o
seu próprio texto e encosta-se ao fundo da área de trabalho. **Não tem fundo**,
porque nada pinta por trás das palavras — e não está empanel nenhum.

## 7. Como está provado

`python _main/caption-overlay-free-oracle.py` — 11 braços, todos GREEN:

```
A1 applyFloat never calls setPanelSurface
A2 applyFloat never writes a floated height
A3 caption-float setFloat never calls setPanelSurface
A4 applyFloat keeps the shellOwnsCaptionWindow guard
B1 caption-float.css never blanks the page background
C1 push_caption_to_window is gated on _caption_wanted
C2 _set_live_enabled sets _caption_wanted
C3 six seconds of silence does not switch the owner off
C4 hiding the panel does not switch the caption off
C5 _blank_caption_window only clears pixels
D1 no live line sends the float-on reason
```

`--neg-arm` reintroduz cada defeito em memória e exige o vermelho:
**11/11 RED**, `NEG-ARM: PASS -- the oracle can say NO`. `--selftest`: **2/2**.

Bateria corrida nesta sessão, todas com saída 0:

```
tdz-reach-oracle --selftest              SELFTEST: GREEN (3/3)
tdz-reach-oracle panel.js 640 665        VERDICT: GREEN  (0 DIRECT, 0 DEFERRED)
scope-leak-oracle                        VERDICT PASS -- 9 stylesheet(s)
panel-caption-button-probe.mjs           errors: 0 · bridge calls caused by the click: 1
                                          → ["setLiveEnabled", true] · aria-pressed=true
panel-layout-probe.mjs                   overlapping pairs: 0
theme-matrix-probe.mjs                   page errors: 0 (45 temas)
forbidden-audio-line-oracle.py           VERDICT: GREEN
caption-overlay-free-oracle.py           VERDICT: GREEN
```

App relançada depois da mudança: `SINGLE_INSTANCE already_running=false`,
`CAPTION_OVERLAY_MODE native=true hwnd=4592906`, **0 `PAGE_ERROR`**, **0**
`Traceback`.

### A barra, medida em píxeis e não em opinião

Alt+C, depois da mudança:

```
22:03:00.673  STRIP_HEIGHT from=148 to=40 source=css css_value=40 extra=0 reason=surface-hotkey
22:03:00.674  STRIP_WIDTH from=None to=380 source=content reason=surface-hotkey
22:03:00.714  PANEL_SURFACE surface=strip reason=hotkey document_surface="strip"
              window=380x40@(770,948) docked=bottom-strip edit_mode=false
```

Captura **só** da janela (`I:\cc-tmp\shot-panel.ps1`, 380x100), lida byte a byte:

| sítio | cor | o que é |
|---|---|---|
| (0,0) e (379,0) | `rgb(15,19,23)` | a laje do tema |
| (0,50) | `rgb(11,15,20)` | **`rgba(11,15,20,0.98)`** — `panel.css:127`, THE RENDER PROTECTION, viva outra vez |
| (0,99) e (379,99) | `rgb(13,16,20)` | bordo inferior |

Anel de bordo: **1920 px amostrados, 0 quase-brancos (0.0 %)**. Cores distintas
na janela: **141** — um quadro liso teria muito menos, e uma página morta teria
duas. **Nenhum branco em lado nenhum.**

### O oráculo leu três comentários como se fossem código

Correção que o próprio oráculo impõe, na primeira execução: B1 e D1 deram RED
contra ficheiroswhose único `float-on` / `background: transparent` estava em
comentário — um deles dentro do próprio docstring da função que diz **não**
escrever aquele atributo. Daí `strip_css_comments()`, `py_facts()` (árvore:
chamadas, atribuições, nomes lidos por um `if`) e
`py_string_constants_outside_docstrings()`. Um instrumento que lê prosa como
código é o defeito que este repo já pagou duas vezes.

## 8. O que NÃO foi medido

**O clique real, na app viva.** Não existe canal para injectar JavaScript na
página a partir de fora — o `evaluate_js` só existe dentro do processo do shell,
e `_main/_cap2panel-probe.py` e `_design-lane/_wvprobe.py` lançam o seu próprio
shell em vez de falar com o do dono. Para fechar esta prova falta um clique do
dono no botão e a leitura do log: o que tem de aparecer é `LIVE_ENABLED on=true`
**sem** nenhum `PANEL_SURFACE reason=strip-float-on` e **sem** nenhum
`STRIP_HEIGHT from=40 to=220`.

## 9. Pins desta revisão

```
app/panel/panel.js            171 984 B  3 444 CRLF / 0 bare LF  sha256 9BFD812712F563E4…
app/panel/caption-float.js     18 678 B    422 CRLF / 0 bare LF  sha256 32B4AD1A3D0E3FD7…
app/panel/caption-float.css     8 791 B    173 CRLF / 0 bare LF  sha256 6F5427ADFE258208…
app/webview/sotto_webview.py  595 070 B 11 434 CRLF / 0 bare LF  sha256 033511AF04B4B28D…
```