# A JANELA DA LEGENDA: verificada por render, e um defeito real apanhado a ler

## O DEFEITO QUE EU APANHEI — e teria feito a legenda sair errada

O `caption-float.css` prende as regras a atributos no `<html>` e no `<body>`:

    html[data-float="on"]
    body[data-float="on"]
    body[data-surface="strip"][data-float="on"] .caption-float  (o display:block)
    body[data-surface="panel"] #caption-float                    (o esconder no painel)

A minha `caption.html` **nao tinha nenhum deles** -- carregava o CSS e as regras nao
casavam. Corrigido: o `<html>` leva `data-float="on"` e o `<body>` leva
`data-surface="strip" data-float="on"` -- exactamente os valores que a app a correr tem
quando o overlay esta em cima, para as duas pintarem igual.

## E VERIFIQUEI POR RENDER, nao por leitura

Nova sonda `_main/_design-lane/caption-window-shot.py`: copia o `app/panel/` para um
diretorio temporario, INJETA texto de teste (`SottoCaption.set/credits/listening`) e
renderiza a pagina a 900x170 com o Chromium headless do `shot.py`. Porque a app do dono
tem o codigo VELHO e o hot-reload so recarrega o PAINEL (nunca o SHELL), um render e a
unica forma honesta de ver isto hoje.

O QUE A IMAGEM MOSTRA (I:/cc-tmp/cap/caption-window.png, 900x170, 18 088 B):
  * FUNDO TRANSPARENTE -- confirmado, o `--default-background-color=00000000` passou e
    o PNG leva alfa. Nada de div de cor solida.
  * A LINHA VIVA EM BAIXO E CENTRADA -- o pedido de origem [860]: *"the live subtitles
    in the BOTTOM AND MIDDLE of the screen"*.
  * A BARRA LED de 4px a esquerda -- o unico CORPO do overlay, o design "inst" do zip.
  * A LINHA ANTERIOR por cima, mais fraca (opacity 0.42).
  * OS CREDITOS em monoespaco, maiusculas, espacados.
  * SEM MOLDURA e SEM SCROLLBAR.

UMA COISA QUE PARECIA DEFEITO E NAO E, e fica escrito para nao se "corrigir" depois:
por tras do texto aparece um cinzento que, sobre o branco do render, le como uma PLACA.
E a sombra de legibilidade, `text-shadow: 0 2px 18px rgba(0,0,0,0.88), 0 1px 2px
rgba(0,0,0,0.72)` (panel.css:3140-3142), e e o que faz o texto vencer sobre qualquer
video. **E sombra, nao fundo** -- e a diferenca que o dono pediu quando disse *"sem
fundo, sem nada, extremamente clean"*.

## O QUE FICOU LIGADO

  `hide_panel` (L5743) ....... esconde a janela da legenda quando o painel se esconde
  `on_worker_caption` (L6380)  mostra-a na PRIMEIRA legenda, e empurra o texto
  `show_caption_window` ...... poe o estado `listening` na pagina tambem

`py_compile` rc=0. As quatro folhas que a pagina carrega existem todas; os tres ids que
o JS procura existem todos.

## O QUE FALTA, e nao finjo

1. **A legenda antiga, dentro do painel, ainda la esta.** NAO a tirei, de proposito:
   enquanto a janela nova nao estiver VISTA a correr, tira-la deixava o dono sem
   legenda nenhuma. Sai assim que ele confirmar a nova.
2. **O botao live ainda nao manda nela.** Hoje ela aparece com a primeira legenda, que
   e um bom proxy (so ha legenda enquanto o worker ouve) mas nao e o botao. Falta uma
   ponte JS->shell.
3. **NAO VERIFICADO A CORRER.** O render prova a PAGINA; nao prova que o pywebview abre
   a segunda janela, nem que o Windows a poe no fundo-centro do workArea.
