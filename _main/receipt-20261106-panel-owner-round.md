# RECIBO — a rodada do painel e da legenda (dono, 2026-11-06)

Tudo o que segue foi medido nesta arvore, hoje. Onde a linha diz `PASS`, o comando esta ao lado e
foi corrido nesta sessao; nenhum numero aqui foi copiado de um log velho.

## 1. O que o dono pediu, e onde cada pedido aterrou

| # | pedido (verbatim) | onde aterrou | instrumento | veredicto |
|---|---|---|---|---|
| 1 | *"control espaço ... nao deve \"vazar\" pra outros apps ... isso faz o espaço pausar o video"* | `app/webview/space_swallow.py` (novo) + `LiveHotkeyThread` | `_main/ctrlspace-swallow-oracle.py` (19 arms) + `_main/ctrlspace-swallow-probe.py` (mede no Windows) | `CTRLSPACE-SWALLOW VERDICT: PASS (19/19)` |
| 2 | *"coloca menu dropdown pra eu escolher"* legenda/fundo | `app/panel/theme-switcher.js` (dropdown + scroll sobre o botao) | `_main/theme-switch-oracle.js` | `VERDICT: PASS (0 failure(s))` |
| 3 | *"tira a BARRA de pesquisa ... so um botao pequeno com o simbolo"* | `app/panel/panel.html` + `panel.js` (busca atras do icone) | `_main/panel-search-keyboard-oracle.py` | `VERDICT: PASS` (4 arms; a arm 4 e' o controlo numa copia contraditoria) |
| 4 | *"tira a data de mostrar o historico"* / *"retira"* os quadrados/circulos em volta do horario | `app/panel/panel-unified.css` (o horario e' um `<time>` sem moldura) | `_main/panel-history-clip-probe.mjs` | `CLIPPED 0`, `NOT LEFT-ALIGNED 0` em **45 temas** |
| 5 | *"o historico tem que persistir ... ate 48hrs ... nao é pra começar a ativar o historico so quando eu mostro o painel"* | `app/panel/history-store.js` + `history-source.js` + o choke point do shell | `_main/history-write-oracle.py` | `VERDICT: PASS` |
| 6 | *"nao é pra DUPLICAR frase nunca"* | `history-merge` / `caption-formulation` | `_main/history-merge-oracle.py` | `VERDICT: PASS arms 22/22` |
| 7 | *"acha TODOS os temas/layouts ... posicao ... MAIS COMUM, fixa ... muda EM MASSA"* | `app/panel/panel-unified.css` (novo, carregado POR ULTIMO) | `_main/theme-button-geometry-oracle.py` | `VERDICT: PASS` (3 checks, 0 failed) |
| 8 | *"o painel de BAIXO deve ser opaco. MEIO transparente ... os botoes, pode ser solido"* | `panel-unified.css` (fundo do painel com alfa; `.btn` opaco) | `_main/panel-header-oracle.js` + `theme-preview-oracle.js` | `GREEN 21/21`, `PASS` |
| 9 | *"ser possivel mover qualquer painel pela tela ... ta extremamente bugado"* | `app/panel/strip-drag.js` + `skin-layout.css` | `_main/panel-drag-targets-oracle.js` | `PASS -- 12 arms, 0 divergentes` |
| 10 | *"o historico nao deve ficar centralizado. é começando pela esquerda"* + *"nao ta mostrando em todos os temas"* | `panel-unified.css` (`justify-content: flex-start` e a lista sempre montada) | `_main/panel-history-clip-probe.mjs` | `NOT LEFT-ALIGNED rows in 0 of 45 theme(s)` |
| 11 | *"os botoes de baixo nao devem existir ... 'Hold' é stale"* | `app/panel/hotkey-hold.css` **apagado** (`D` no git) + o markup | `_main/_panel2-dom-probe.js` | `RESULT: GREEN — 87/87 arm(s)` |
| 12 | *"tira qualquer frase de efeito ... 'the room, so far' ou 'transcript history'"* | `panel.html` / `panel.js` (os rotulos saem) | `_main/_panel2-dom-probe.js` | idem |
| 13 | *"identifica os temas que NAO tem horario, e faça ter"* | `panel-unified.css` (o horario e' montado pelo JS, nao pelo tema) | `_main/panel-history-clip-probe.mjs` | `STAMP UNREADABLE 0 of 45` |
| 14 | *"ao deixar o mouse encima do botao de menu dropdown ... o scroll ... deve trocar os temas"* | `theme-switcher.js` (`wheel` sobre o gatilho) | `_main/theme-switch-oracle.js` | `PASS` |
| 15 | *"o historico CORTA no meio da frase ... full audit"* | `panel-unified.css` (nada de `text-overflow`/`line-clamp` na linha) + o engine | `_main/panel-history-clip-probe.mjs` | `CLIPPED 0`, `LINE-CLAMPED 0` em 45 temas |
| 16 | *"scroll ... no botao de aumentar o tamanho da legenda"* | `panel.js` (`wheel` no controle de tamanho) | `_main/_panel2-dom-probe.js` | 87/87 |
| 17 | *"o botao de pause ... o botao nao muda pra unpause"* | `panel.js` lê `paused` do canal `stats`; shell carimba o campo em `stats()` | `_main/panel-header-oracle.js` **ARM 7** | `GREEN 21/21` (ver §2) |
| 18 | *"MESMO TAMANHO de logo/letra, na MESMA LINHA/PIXEL ... PADRAO de espaçamento ... o botao vermelho ... entra dentro de outro botao"* | `panel-unified.css` (grid fixo do cabecalho, vao fixo de 8 px) | `_main/theme-button-geometry-oracle.py` | `VERDICT: PASS` (3 checks, 0 failed) |
| 19 | *"ALGUNS temas tem a 'legenda ao vivo' inbutida no painel da direita ... NAO é pra existir"* | `panel-unified.css` esconde o bloco embutido no painel da direita | `_main/_panel2-dom-probe.js` | 87/87 |
| 20 | *"se tem um audio contínuo tocando ... nunca vai pro historico cada frase"* | `caption-formulation.js` (fim de frase por pontuacao/limite, nunca stream na primeira div) | `_main/history-write-oracle.py` | `PASS` |
| 21 | *"contraste bom ... horario mais escuro/cinza, o texto mais aceso"* | `panel-unified.css` | `_main/panel-history-clip-probe.mjs` | `STAMP UNREADABLE 0`, `STAMP LOUDER THAN TEXT 0` em 45 temas |
| 22 | *"se eu pauso o video, a legenda do sotto continua por mais uns 2 segundos"* | `app/webview/youtube_cdp_source.py` (`paused`/`ended` do DOM) | `_main/youtube-cdp-source-oracle.py` | `VERDICT: PASS (18/18)` |
| 23 | *"abrir outro video ... prioridade ao novo ... alt tab"* | `youtube_cdp_source.py` (`tab_is_foreground`, `tab_is_playing`, a escada de preferencia) | idem | idem |
| 24 | *"buga se eu desativo ela e o video ao mesmo tempo"* | `space_swallow.py` + o caminho do toggle | `_main/ctrlspace-swallow-oracle.py` | `PASS (19/19)` |

## 2. O braco NOVO de hoje: o pause e' do SHELL

Ordem verbatim: *"o botao de pause tambem nao ta completo. o botao nao muda pra unpause."*

O glifo ja' trocava ao CLIQUE (`paintPauseControls`), mas `paused` era uma variavel DA PAGINA:
esconder o painel e mostra-lo de novo com os motores descarregados pintava **Pause** sobre um shell
que estava pausado. A cura tem duas metades, e as duas sao uma linha:

* `app/webview/sotto_webview.py` `stats()`: `payload['paused'] = bool(self._paused)` — o estado
  viaja no canal que a pagina JA' pede a cada segundo e que o shell JA' empurra por
  `emit_async('stats', …)`.
* `app/panel/panel.js` `wireLevel()`: `if (typeof fields.paused === 'boolean' && fields.paused !== paused) setPaused(fields.paused, null);`
  — **ausente nao e' falso**: um payload sem o campo nao move o botao.

Medido em `_main/panel-header-oracle.js` (jsdom, o `panel.html` real, TODAS as folhas de estilo na
ordem real, os scripts reais):

```
=== ARM 7 — o botao de pause APRENDE o estado do shell ===
[PASS] the shell's paused=true flips the button to RESUME, false flips it back
       real    = ["true","false",true,true]
[PASS] a stats payload WITHOUT the field leaves the button exactly where it was
       real    = ["false","g"]
[PASS] CONTROL - with the wiring removed the same payload leaves the glyph alone
       real    = [true,"false"]
ARMS: 1=3/3 2=2/2 3=4/4 4=6/6 5=1/1 6=2/2 7=3/3
VERDICT: GREEN -- 21/21 arm(s)
```

O `stats()` TEM DUAS SAIDAS, E A PRIMEIRA E' A QUE CORRE QUASE SEMPRE: um tick de medidor fresco
substitui a linha de `WORKER_STATS` inteira e volta antes da cauda. Carimbar o pause so' na ultima
saida deixaria o botao sem noticia exactamente no caso NORMAL -- e o defeito pareceria intermitente,
a pior forma de o entregar. O carimbo esta' nas **duas**, e o passo `panel-pause-payload` executa a
funcao REAL (importada, ligada a um shell falso com `bridge.last_meter` / `last_worker_stats` /
`_paused`) em 5 arms:

```
[PASS] A1 medidor FRESCO com _paused=True -> paused True (e o resto do payload intacto)
[PASS] A2 o mesmo ramo com _paused=False -> paused False, e o campo EXISTE
[PASS] A3 medidor VELHO (a saida do WORKER_STATS) tambem carrega o pause
[PASS] A4 shell sem o atributo -> paused False, e nao levanta
[PASS] A5 sem medidor e sem linha -> still the whole state, tag=stats
VERDICT: PASS -- 5/5 arm(s)
```

O `--neg-arm` escreve uma copia do modulo com o carimbo arrancado das duas saidas, importa-a (os
irmaos vem do diretorio real) e exige que as arms caiam: medido **`MUTANT: 0/5`**, `NEG-ARM: PASS`,
rc=0.

O CONTROL do ARM 7 (jsdom) e' um **mutante montado**, nao uma frase: o oraculo escreve uma copia de `panel.js` com o
`setPaused` arrancado, monta-a numa pagina PROPIA (o loader ganhou um mapa de overrides, resolvido
contra `panelDir()`) e exige que a arm va' RED ali. Duas correccoes de instrumento no caminho, as
duas medidas: o glifo nao e' `<path>` quando esta' a correr (e' um `<g>` de dois rects), e o
`panel.js` embarcado e' **CRLF** -- uma ancora byte-exact contra LF dava um FALSE RED ("a fiação nao
esta' presente") sobre fiação que esta'.

## 3. Gates corridos nesta sessao

| comando | veredicto |
|---|---|
| `node _main/panel-header-oracle.js` | `GREEN -- 21/21 arm(s)` |
| `node _main/panel-drag-targets-oracle.js` | `PASS -- 12 arms, 0 divergentes` |
| `node _main/theme-switch-oracle.js` | `PASS (0 failure(s))` |
| `node _main/theme-preview-oracle.js` | `PASS` |
| `node _main/_panel2-dom-probe.js` | `GREEN — 87/87 arm(s)` |
| `node _main/panel-history-clip-probe.mjs` | 45 temas: `CLIPPED 0`, `LINE-CLAMPED 0`, `STAMP UNREADABLE 0`, `STAMP LOUDER 0`, `NOT LEFT-ALIGNED 0` |
| `python _main/ctrlspace-swallow-oracle.py` | `PASS (19/19)` |
| `python _main/input-path-oracle.py` | `PASS` — nenhum hook global de rato; o unico hook e' o `WH_KEYBOARD_LL` gated de `space_swallow.py` |
| `python _main/history-merge-oracle.py` | `PASS arms 22/22` |
| `python _main/history-write-oracle.py` | `PASS` |
| `python _main/youtube-cdp-source-oracle.py` | `PASS (18/18)` |
| `python _main/undefined-names-oracle.py` | `GREEN` — 19 ficheiros, 0 nomes usados e nunca definidos |
| `python _main/battery-wiring-oracle.py` | `PASS checks=7 fail=0` (populacao=251, ligados=142) |
| `python _main/battery-class-oracle.py` | `PASS -- arms=3 fail=0` |
| `python _main/agents-md-pins-oracle.py` | `PASS -- 2 pin(s) checked live, 0 failure(s)` |
| `python _main/panel-search-keyboard-oracle.py` | `VERDICT: PASS` (4 arms) |
| `python _main/theme-button-geometry-oracle.py` | `VERDICT: PASS` (3 checks, 0 failed) |
| `python _main/theme-button-contrast-oracle.py` | `VERDICT: PASS` (3 checks, 0 failed) |
| `python _main/panel-pause-payload-oracle.py` | `VERDICT: PASS -- 5/5 arm(s)` |
| o mesmo com `--neg-arm` | `MUTANT: 0/5`, `NEG-ARM: PASS`, rc=0 |

## 4. Pins

* `_main\_audit-verify-all.cmd` = **267654 B**, **3283 CRLF** / 0 bare LF,
  sha256 `55C59B782F0052C55008C04184F9FF10B6E6F6D1685F5024BFDD3C595A57FEE1`, depois dos **cinco passos
  novos**: `panel-header-oracle`, `panel-drag-targets`, `panel-history-clip`,
  `panel-pause-payload` e o seu `red-as-expected-*`. As tres primeiras dependem de
  `app\panel\panel-unified.css`; o par do pause depende de
  `app\webview\sotto_webview.py` e `app\panel\panel.js`, porque executa as duas metades. O pin vive no `AGENTS.md` e o `agents-md-pins-oracle` confirma-o.
  A insercao das linhas foi feita em LF por engano e normalizada para CRLF **antes** de medir: o pin
  acima e' o do ficheiro com 0 bare LF, nao o do estado intermediario.
* `app/panel/hotkey-hold.css` foi **apagado** (`D` no git) — o botao "Hold" e' de uma configuracao
  que o dono ja' trocou.
* `app/panel/panel-unified.css` e' **novo** e carrega por ULTIMO no `panel.html`, depois de
  `button-contract.css`: e' ele que NAO pode ser derrotado por um tema.

## 5. O QUE NAO ESTA' VERIFICADO

* Nada disto foi visto na TELA do dono: a prova e' jsdom + oraculos + os arm do Windows que nao
  renderizam audio nem abrem janela. `verified` continua a exigir uma corrida real da app, pela mão
  dele.
* O `panel-search-keyboard` diz o que ele proprio nao pode: que um keystroke REAL chegou ao campo
  e' UNMEASURED, e exige a largada que a ordem do dono proibe.
