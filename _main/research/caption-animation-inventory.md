# Inventário — render de legenda e animação (foco: roll-up)

Escopo: só leitura. Nenhum ficheiro de código foi alterado por este trabalho.
Data da leitura: **2026-11-08 02:05 -0300**; HEAD `b0e1e27`.

Comandos que produzem todas as âncoras abaixo: `grep -n` / `read` sobre os ficheiros citados.
Números que não vêm de uma constante do código estão marcados `[INFERENCE]`.

> **AVISO DE ÁRVORE EM MOVIMENTO.** Enquanto este inventário era escrito, um trabalho
> concorrente alterou o *working tree* de `app/webview/{youtube_reveal,caption_overlay,overlay_paint}.py`
> (`git diff --stat` às 02:05: `caption_overlay.py` +73, `overlay_paint.py` +22,
> `youtube_reveal.py` +39 linhas, **não commitado**). Essas alterações **já incluem parte do
> roll-up** (progresso, deslocamento no bitmap, agendamento de frames). O relatório descreve o
> estado do *working tree* nesse instante e separa explicitamente **HEAD/shipped** de
> **worktree/não commitado**, porque a diferença é o próprio objecto do inventário. Linhas de
> `caption_overlay.py` abaixo de `_next_delay` podem deslocar-se enquanto o peer edita.

---

## 1. Onde a legenda é PINTADA, por superfície

| Superfície | Entrada | Cadeia de pintura | Âncoras |
|---|---|---|---|
| **Overlay nativo Win32** (a legenda que o dono vê quando o botão `live` está ON) | shell cria em `sotto_webview.py:11244`; cada push chama `ov.set_text(...)` em `sotto_webview.py:15913` | `_update` → `_display` → `_layout` → `_premultiplied_bitmap` → `UpdateLayeredWindow` | `caption_overlay.py:605` (`_update`), `:611` (chamada a `_display`), `:856` (`_display`), `:629` (`_layout`), `:639` (bitmap), `:675` (`UpdateLayeredWindow`) |
| **Painel** — caixa `#captions-body` > `#caption-list` | `panel.js` `renderProvisional` (linha em formação) e `addCaption` (linha fechada) | append do `<li class="caption">` no fim da lista + pin do scroll | `panel.html:598`, `:612`; `panel.js:1332` e `:1594` (`dom.list.append`); `panel.js:1719` (`scrollTop = scrollHeight`) |
| **Overlay flutuado WebView2** (`#caption-float`) | `panel.js:1637` → `SottoCaptionFloat.push`; ou ponte própria quando não há painel | DOM próprio do `caption-float.js` (host/stage/col) + `caption-float.css` | `caption-float.js:1-83` (doc do contrato), `caption-float.css:331` |
| **Skin em shadow DOM** | `skin-host.js` | clona o template do mockup, uma `<span>` por palavra; a última leva `word-in` | `skin-host.js:651-654` |
| **Simulador offline** | `_main/sim/make-youtube-caption-sim.py` | replay por `youtube_reveal.frame` | `make-youtube-caption-sim.py:140-156` |

A legenda nativa **não é** a do painel nem a do `caption-float`: são três DOMs/renderizadores
independentes. As contagens e os relógios do overlay vivem em `caption_overlay.py`; a política de
desenho vive em `youtube_reveal.py`; a geometria e o GDI+ vivem em `overlay_paint.py`
(divisão explicada em `caption_overlay.py:147-163`).

---

## 2. Toda a animação existente

### 2.1 Overlay nativo (o que o dono vê)

| Animação | Escopo | Onde | Estado | Ordem / nota |
|---|---|---|---|---|
| Revelação palavra a palavra | **PALAVRA** | `youtube_reveal.word_clock_count` `:235`, `first_words` `:160`, `_reveal_text` `:446` | **LIGADO** | Não é animação de interpolação: é um prefixo recalculado a cada instante; `_reveal_text` usa `min(relógio da palavra, cap)` |
| Fade de entrada da linha/janela | **BLOCO** | `word_fade.alpha_at` `:40` (0,12 s, ease-out quadrático) → `caption_overlay._fade_alpha` `:507` → `BLENDFUNCTION.SourceConstantAlpha` `caption_overlay.py:674` | **DESLIGADO** | `FADE_ON = False` em `caption_overlay.py:332`. Ordem do dono: 2026-10-30 pediu animação; 2026-11-03 mandou tirar (*"e ta com animacao fade in que eu JA MANDEI VOCE TIRAR"*). Com `False`, `_fade_alpha` devolve sempre 255 e nenhum frame intermédio é publicado |
| Fade de saída da linha que rola para fora | **LINHA** | `word_fade.alpha_out` `:89` (`EXIT_S = 0.45`, `:86`), chamado em `youtube_reveal.frame` `:517` | **DESLIGADO no caminho que pinta** | O motor calcula o alfa, mas: (a) no caminho do cue os alfas são forçados a 255 (`caption_overlay.py:873-875`); (b) no caminho ASR as marcas `exiting` são **descartadas** quando `FADE_ON` é `False` (`caption_overlay.py:886-889`). É coerente com a medição: o player mantém `opacity` 1 e a linha sai da caixa (spec, linha 22/26) |
| Deslocamento vertical do roll-up (linha nova entra, anterior sobe) | **LINHA** (todas as linhas do bloco sobem um espaço) | `youtube_reveal.roll_progress` `:539` + `frame` devolve `displaced_at` `:524-527`; `_PlayerCue.roll` `caption_overlay.py:280`; `overlay_paint._premultiplied_bitmap` `offset_y` `:734`, `y` `:735`, loop `:739-745`; caixa fixa em `_layout(..., rows=…)` `overlay_paint.py:628-629`; frames armados em `_next_delay` `caption_overlay.py:571-575` | **LIGADO apenas no caminho do cue** — e **NÃO COMMITADO** | Presente no *working tree* às 02:05. O caminho ASR continua a forçar `_roll = 0.0` (`caption_overlay.py:884`) e a descartar a 3.ª linha (`:887-889`). Nenhum oráculo mede a curva (ver §5) |
| Movimento da janela/bitmap inteiro | **BLOCO** | `caption_overlay.py:666-670` (`x` centrado, `y = work.y + work.height - height - 48*scale`) | **LIGADO (salto, não animação)** | A janela é ancorada no fundo; quando `height` muda (nº de linhas), o bitmap inteiro salta sem interpolação. Antes do roll em curso era isto que o dono via |

### 2.2 Painel (CSS + JS)

| Animação | Escopo | Onde | Estado |
|---|---|---|---|
| Entrada de linha (`caption-in`, 220 ms, `opacity` 0→1 + `translateY(5px)`) | **LINHA** | regra base `.caption { animation: none; }` — `panel.css:1248` (o comentário em `:1244-1247` nomeia a animação removida) | **DESLIGADO** (ordem do dono 2026-11-02: *"e tira a animacao de fade in"*) |
| Fade da palavra nova | **PALAVRA** | `.caption--provisional .caption__word[data-typing] { opacity: 1; animation: none !important; }` — `panel.css:2776-2782`; desactiva também as animações dos temas em `panel.css:2797-2799` | **DESLIGADO** (ordem do dono 2026-11-02) |
| Animação de palavra dos temas (`cine-c1-word` 620 ms, `cine-c2-word` 420 ms, `cine-fade`/`cine-rise`) | **PALAVRA** | `themes/cinematic.css:2985`, `:5667-5671`, keyframes `:27-35`; `cine-fade`/`cine-rise` estão definidos mas **sem nenhum consumidor** nos temas | Declaradas; **neutralizadas** pelo `!important` de `panel.css:2782` |
| Troca de letras numa revisão (`sotto-letter-swap-in`, 34 ms + 16 ms de stagger, `opacity` + `translate3d(0,-.22em)` + `scale(.86)`) | **LETRA** | JS gera o keyframe em `letter-swap.js:69-72`; chamado em `panel.js:1566-1572` (`addCaption`, ramo `existing`) | **LIGADO** (respeita `prefers-reduced-motion`, `letter-swap.js:73-74`) |
| `scrollTop = scrollHeight` ao inserir linha | **BLOCO** | `panel.js:1719` (`pinLiveTranscriptToBottom`), chamado por `followNewestLine` `:1648-1655` | **LIGADO, salto instantâneo**; não há `scroll-behavior` em `panel.css` (grep: 0 ocorrências) |
| Barra LED a respirar (`caption-led-breathe`, 1,5 s, `scaleY .45↔1`) | **BLOCO decorativo** | `panel.css:3307`, keyframes `:3310-3313`; `.caption-float__led:not(.is-on)` desliga em `:3319-3322` | **LIGADO** (overlay flutuado) |
| Barras `listening` | decorativo | `panel.css:1394-1408`, keyframes `:1410` | LIGADO |
| Status a respirar | decorativo | `panel.css:1498-1501`, `:3534-3537` | LIGADO |
| Medidor de áudio (`transform: scaleY`, 90 ms linear) | decorativo | `panel.css:623-626` | LIGADO |
| Transições de cor/borda de botões e linhas | decorativo | `panel.css:466-469`, `:838-841` | LIGADO |
| Máscara do topo do painel | estático (não anima) | `panel.css:1188-1189` (`mask-image`) | — |

Contagem mecânica (`grep -c`, 02:05): `panel.css` 6 `@keyframes`/15 `animation:`/9 `transition`;
`themes/cinematic.css` 11/35/104; `themes/panel-designs.css` 11/33/43; `theme-1..5.css` 3/8/9,
3/9/9, 1/8/11, 2/7/11, 7/9/9; `caption-float.css` 0/1/0.

### 2.3 Divergência de documentação (achado)

`docs/youtube-caption-spec.md:58` e `:63` afirmam que o painel usa **140 ms `ease-out` sobre
`opacity` (`sotto-word-in`)**. Essa regra **não existe no repositório**: `grep -rn "sotto-word-in"`
só encontra o próprio `.md`; e `panel.css:2776-2782` fixa `animation: none !important` desde a
ordem de 2026-11-02. A spec está desactualizada nesse ponto (linhas 23 e 26 da tabela).

---

## 3. O relógio da revelação e o agendamento

### 3.1 A origem dos instantes

* **Caminho YouTube**: cada linha (`rows_from_cues`, `youtube_reveal.py:410`) traz
  `{"text","words":[{"start","text"}],"start","end","cap"}`; o instante da palavra é
  `tStartMs (linha) + tOffsetMs (segmento)` — spec linhas 7-9, `word_clock_count:235`.
* **Caminho ASR**: `LiveRows.push(text, at)` (`youtube_reveal.py:631`).
  `step = min(WORD_GAP_S, MAX_LAG_S / len(fresh))` (`:656`); `base = max(at, última palavra
  datada + step)` (`:676`); cada palavra nova →
  `start = base + i*step` (`:677-678`). Correções mantêm o `start` das palavras que continuam
  iguais no prefixo (o `common` de `:648-655`). Constantes: `WORD_GAP_S = 0.24` (`:395`),
  `MAX_LAG_S = 0.36` (`:402`).

### 3.2 A revelação

`_reveal_text` (`:446`) → `word_clock_count` (`:235`) conta palavras com `start <= t`;
`first_words` (`:160`) corta o prefixo. `cap` (pintura do player) é o tecto adicional.
`_drawn` (`:464-486`) filtra `start <= t` e mantém `capacity + rollup` linhas
(`CAPACITY = 2` `:85`, `ROLLUP_ROWS = 1` `:93`); a linha que acabou fica até `end + EXIT_S`
(`EXIT_S = 0.45` `:407`).

No overlay, o instante de desenho é o do **player**, não o do `monotonic()` da leitura:
`_PlayerCue` (`caption_overlay.py:193`) guarda `t` (relógio do vídeo na leitura) e `at`
(`monotonic()` da leitura); `clock()` (`:256`) devolve
`t + min(agora - at, PLAYER_HOLD_S=3.0) * rate`, com `floor` que nunca recua.

### 3.3 `next_clock` e o agendamento

* `_PlayerCue.next_clock` (`caption_overlay.py:299`): devolve
  `now + (min(start ainda futuro) - clock(now))`, considerando `start` de linha **e** de palavra.
  `None` quando nada está por revelar.
* `LiveRows.next_clock` (`youtube_reveal.py:737`): `min(start de palavra > t)`.
* `_next_delay` (`caption_overlay.py:539`) escolhe o **mínimo** entre:
  `word_fade.next_delay` (tecto `1/60 s`) se houver fade; o próximo instante de palavra do
  `LiveRows`; `FRAME_S` se alguma marca estiver `exiting`; `FRAME_S` se `0 < _roll < 1`;
  o `_cue.next_clock`. Sem candidatos devolve `None`.
* `_arm_tick` (`:582`) cria `threading.Timer(delay)` daemon com geração (`_tick_gen`);
  `_tick` (`:596`) chama `_update` se a geração ainda for a actual. Não há tick fixo nem timer
  num ecrã parado.

---

## 4. Como o overlay nativo desenha as linhas hoje

### 4.1 Montagem do texto

`_display` (`caption_overlay.py:856`):

* com `_cue`: `_cue_texts()` (`:896`) chama `_PlayerCue.frame` (`:264`) e `_clamp_rows`
  (tecto `PLAYER_ROWS + 1` no worktree, `:909`), devolve `rows_text(...)` + alfas (`:861-877`);
* com `_live`: `_live.frame(monotonic())` (`:883`), filtra `exiting` se `FADE_ON` é `False`
  (`:886-889`);
* sem motor: `_display_text()` (`:930`), o texto chega já cortado (`instant=True`).

`rows_text` (`youtube_reveal.py:757`) junta as linhas com `ROW_END = "\n"` (mesmo para uma só) —
marcador que impede `_layout` de re-quebrar.

### 4.2 Origem Y, altura de linha

`_layout` (`overlay_paint.py:563`) **não re-quebra** quando há `'\n'` (`:599-602`); portanto
`cur_lines` = linhas do motor, por ordem (mais antiga → mais nova).

`_geom` (`overlay_paint.py:485`):

* `cur_px = max(12, livePx * scale)` — `overlay_paint.py:493`,
* **altura de linha** `line_h = cur_px * t['leading']` — `overlay_paint.py:512`,
* linha anterior `prev_h = prev_px * t['prevLeading']` — `:513`,
* `pad_t/pad_b` de `t['pad'] * scale` — `:495`; `x_text` (`:511`) soma `pad_l` + régua + LED.

`_layout` calcula `height = pad_t + pad_b + line_h * box_rows + (prev_h se prev_line)`
(`:629`) e `width` por medição real (`:622`).

`_premultiplied_bitmap` (`:633`) pinta:

```
y = pad_t + offset_y                       # :735; offset_y = -roll * line_h (:734)
se prev_line: draw_line(prev_line, y, prev_h); y += prev_h   # :737-738
para cada cur_line i: draw_line(line, y, line_h, alpha[i]); y += line_h  # :739-745
```

`draw_line` (`:712`) usa `RectangleF(x_text, top, largura, h)` (`:715`) + `AddString`
(`:718`). Ou seja: **origem Y da linha i = `pad_t + i*line_h`** (mais `prev_h` se houver linha
anterior), e a altura usada é `line_h` — nunca medida por texto; é a do tema.

### 4.3 Posição da janela e altura da caixa

`_update` (`caption_overlay.py:605`) posiciona o bitmap com
`x` centrado (`:666`) e `y = work.y + work.height - height - 48*scale` (`:668`) — âncora no
fundo. Sem alteração de `height`, o texto não se mexe verticalmente.

No worktree, o caminho do cue passa `rows=PLAYER_ROWS` a `_layout` (`caption_overlay.py:629-631`),
fixando a **caixa** em 2 linhas mesmo durante a transição de 3 linhas — é isso que faz o
conteúdo subir dentro da caixa em vez de a caixa crescer.

### 4.4 Existe deslocamento vertical animado?

* **HEAD (`b0e1e27`)**: **não**. `_PlayerCue.frame` chamava `frame(..., rollup=0, exit_s=0.0)`
  (versão commitada) e não havia `offset_y`; cada linha era `pad_t + i*line_h` fixo. A linha
  velha desaparecia num quadro quando o motor a tirava da janela.
* **Working tree (02:05, não commitado)**: **sim, no caminho do cue** —
  `roll_progress` (`youtube_reveal.py:539`) `1-(1-x)²` ao longo de `EXIT_S`, `offset_y`
  (`overlay_paint.py:734`), `displaced_at` por marca (`youtube_reveal.py:524-527`), frames de
  1/60 s enquanto `0 < _roll < 1` (`caption_overlay.py:571-575`).
  No caminho **ASR/live** continua **não**: `_roll = 0.0` (`caption_overlay.py:884`) e a linha
  `exiting` é filtrada (`:886-889`).

### 4.5 Onde o texto é montado e onde entra um offset de animação

* **Montagem**: `_display` (`caption_overlay.py:856`) → `rows_text` (`youtube_reveal.py:757`) →
  `_update:629` (`_layout`) → `_premultiplied_bitmap:639`.
* **Offset**: entra em `_premultiplied_bitmap` como `offset_y` somado à origem de **todas** as
  linhas (`overlay_paint.py:734-735`, e no LED `:768` do worktree), com a caixa fixada por
  `_layout(rows=…)` (`:628-629`). O valor vem de `_PlayerCue.roll` → `roll_progress`
  (`caption_overlay.py:280`, `youtube_reveal.py:539`). O recorte da linha que sai é o próprio
  recorte do bitmap (topo negativo em GDI+), não um fade.

---

## 5. Tabela final — o que existe × o que falta para o roll-up

`mede a curva?` = existe código/instrumento que define **e** verifica a curva temporal daquele
movimento. `sim` só quando há um número e um verificador.

| O que existe | arquivo:linha | mede a curva? | Falta para o roll-up |
|---|---|---|---|
| Janela de 2 linhas + a que sai (`capacity + rollup`) | `youtube_reveal.py:85,93,464-486` | **sim** (spec linhas 11-12, 17-18; instrumento `_main/sim/measure-youtube-captions.py`) | Nada no motor: a janela já é a do player |
| Relógio de palavra do payload (`tStart+tOffsetMs`) | `youtube_reveal.py:235,446`; `docs/youtube-caption-spec.md:7-10` | **sim** (spec linhas 7-10) | Nada |
| Relógio do player no overlay (`t + Δ*rate`, piso, hold 3 s) | `caption_overlay.py:193,256`; `PLAYER_HOLD_S:173` | **sim** (`land_lag_ms`, `_log_land` `:801`) | Nada |
| Alfa de saída por linha (`alpha_out`, 0,45 s) | `word_fade.py:86-89`; `youtube_reveal.py:517` | **sim** — `EXIT_S` derivado de `rollup.exit_s_bracket_s` (spec 13) | **Ligado só no motor.** O cue força 255 (`caption_overlay.py:873-875`) e o live descarta `exiting` com `FADE_ON=False` (`:886-889`). Medição diz opacidade 1: o alfa não deve ser usado como movimento |
| **Deslocamento vertical do roll-up** (`roll_progress` 1-(1-x)², `offset_y = -roll*line_h`) | `youtube_reveal.py:536-563`; `overlay_paint.py:734-745`; `caption_overlay.py:280,629,571-575` | **não** — nenhum oráculo referencia `roll_progress`/`displaced_at`/`ROLL_ROWS` (`grep -rn` em `_main` = 0) | (1) **verificar a curva contra o player** (o `exit_s` é medido, mas o deslocamento em px nunca foi medido); (2) **ligar no caminho ASR** (`_roll=0` em `caption_overlay.py:884`; `exiting` filtrado em `:887-889`); (3) reprovar com mutante (sem offset → 3 linhas paradas) |
| Caixa de altura fixa durante a transição | `overlay_paint.py:628-629`; `caption_overlay.py:629` | **não** | Medir se o player mantém a caixa de 2 linhas ou cresce; hoje é `[INFERENCE]` de desenho, e muda a posição Y de todos os textos de cue com 1 linha |
| Tecto de linhas do cue `PLAYER_ROWS + 1` | `caption_overlay.py:896-910` (`_clamp_rows` em `:909`) | **não** | Uma linha de payload com `'\n'` pode exceder 3 linhas físicas e cortar uma linha viva; sem medição do caso |
| Frames durante a transição | `caption_overlay.py:571-575` (worktree) | **não** | Contagem de frames vs. 0,45 s não medida; sem oráculo, um `_next_delay` que devolva `None` congela a linha a meio do percurso |
| Fade de entrada da linha | `word_fade.py:31,40`; `caption_overlay.py:332,507` | **sim** (curva definida) / **DESLIGADO** | Nada para o roll-up: o player não faz fade de entrada (ordem do dono 2026-11-02/03) |
| Fade da palavra nova no painel | `panel.css:2776-2782` | **não** (desligado por ordem) | Nada: outra superfície |
| Entrada de linha no painel (`caption-in`) | `panel.css:1244-1248` | **não** | Nada para o roll-up nativo; o painel rola por `scrollTop` (`panel.js:1719`), sem animação |
| Fade de letras na revisão (`letter-swap`) | `letter-swap.js:69-72`; `panel.js:1566` | **sim** (duração/stagger) | Nada: outra superfície |
| Simulador offline | `_main/sim/make-youtube-caption-sim.py:140-156` | **não** para roll-up | Só transporta `[texto, alfa, exiting]`; não há `dy`/`roll` no replay, logo a página **não consegue** mostrar nem julgar o roll-up |
| Spec documental | `docs/youtube-caption-spec.md:13,22,26` | **sim** para a janela/exit | Não descreve deslocamento vertical; linha 23/26 está desactualizada sobre o painel |

### Resumo em três linhas

1. **Existe**: a janela de 2+1 linhas, o relógio de palavra do player e do ASR, o `EXIT_S`
   medido, o alfa por linha e a caixa de altura fixa.
2. **Existe no working tree, não commitado e não verificado**: o progresso `1-(1-x)²` do
   deslocamento, o `offset_y` no bitmap e os frames de 1/60 s — **só no caminho do cue**.
3. **Falta**: medição do deslocamento (px/curva) contra o player, um oráculo/mutante que fale
   RED sem ele, o mesmo comportamento no caminho ASR, e o `dy` no simulador — sem isso o
   roll-up é código sem instrumento.
