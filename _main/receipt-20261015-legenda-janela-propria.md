# A LEGENDA NUMA JANELA PROPRIA -- a raiz de quase tudo o que ele reclamou

O dono, seis vezes em tres dias, verbatim:
  *"a porra da legenda, e pra ser independente do painel, nao acoplado"* [32218]
  *"essa legenda ao vivo deveria aparecer no MEIO EM BAIXO da minha tela, igual eu ja
    falei DEZENAS DE VEZES nessa sessao"* [42215]
  *"e tu entendeu como eu quero as legendas na tela? que nao sao acopladas a painel
    algum? a legenda ao vivo. como overlay"* [37242]
  *"the live subtitles in the BOTTOM AND MIDDLE of the screen"* [860, a ORIGEM]

## PORQUE UMA JANELA, E NAO CSS

A legenda vivia DENTRO da janela da barra, empilhada debaixo dela. O proprio CSS
explicava: *"The two overlays share one window, so they are STACKED, never
overlapped"*. Um caixote partilhado NAO consegue pousar a legenda no fundo da TELA e
ao mesmo tempo ter a barra no topo dele -- e era por isso que o print do dono mostrava
o painel E a legenda, o *"duas coisa sobrepostas"* que ele descreveu.

**Duas janelas nao se podem sobrepor uma a outra.** O problema deixa de existir por
construcao, nao por regra de CSS.

## O QUE FOI FEITO

1. **`app/panel/caption.html`** (NOVO, 3 716 B) -- a pagina propria da legenda. Carrega
   apenas o essencial (`fonts.css`, `panel.css`, `caption-float.css`, `zip-overlay.css`)
   e expoe TRES chamadas: `SottoCaption.set(texto, anterior)`, `.credits(t)`,
   `.listening(on)`. Sem fundo, sem moldura, sem scrollbar, sem polling, sem ficheiro
   de estado -- o shell manda, a pagina pinta.

2. **`sotto_webview.py`: uma SEGUNDA janela** (`self.caption_window`), criada ao lado da
   primeira. Onde: no **fundo-centro do `workArea`** -- o retangulo que exclui a barra
   de tarefas, para a legenda nao ficar por baixo dela. Larga (ate 900 px) e baixa
   (170 px), porque o zip poe a legenda numa faixa larga por cima do video, nao numa
   coluna. `frameless`, `transparent`, `on_top`, `hidden` a nascenca.
   x = workArea.x + (workArea.w - largura) / 2      <- o MEIO
   y = workArea.y + workArea.h - altura - 48        <- EM BAIXO

3. **O caminho da legenda**: `on_worker_caption` (o UNICO sitio por onde toda a legenda
   passa, `BRIDGE_CAPTION_SENT`) passa a alimentar tambem a janela propria, e a
   **mostra na primeira linha** -- porque uma legenda so chega enquanto o worker esta a
   ouvir, portanto o aparecimento fica ligado ao proprio sinal, sem polling nem estado
   duplicado.

## O QUE FALTA, e digo-o

* **Esconder a janela quando o painel se esconde.** A chamada
  `show_caption_window(False)` tem de ir no caminho do hide. Ainda nao esta ligada.
* **Nada disto foi VISTO a correr.** A app do dono (pid 19884) tem o codigo VELHO -- o
  hot-reload so recarrega o PAINEL, nao o SHELL. So um arranque novo mostra a janela.
* **A legenda antiga, dentro do painel, ainda existe.** As duas vao aparecer juntas ate
  eu tirar a de dentro do painel. E a proxima coisa.

Medido: `py_compile` rc=0, e a janela e criada antes de `webview.start()`, que e o
requisito do pywebview para varias janelas no mesmo laco.
