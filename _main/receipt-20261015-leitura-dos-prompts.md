# O QUE EU ENCONTREI AO LER OS TEUS PROMPTS — e o que corrigi hoje

O dono: *"a primeira coisa q tu vai fazer e entender a sessao em q vc esta e ler todos
os meus prompts relacionados a design ou temas"*. Fiz isso: descomprimi o transcript da
sessao (zstd, 189 MB) e extrai os 65 prompts teus. Estao guardados em
I:/cc-tmp/meus-prompts.txt.

## O TEU INTENTO, verbatim, por ordem

[860] 2026-10-09 — A ORIGEM:
  "my original intent is to have different templates (but the button to change
   template should stay the same place so user just keeps clicking. also a dropdown to
   choose the templates, that you use your mouse and when hover the tamplates preview.).
   and all templates should be very close to the ones in the .zip files in the
   workspace. INCLUDING the way the live subtitles in the BOTTOM AND MIDDLE OF THE
   SCREEN. the bottom panel should not contain the transcript or history. just the
   panel of the right. the bottom panel should be really small and minimalistic. the
   actual subtitles in the screen as overlay should be the ones like the .zip files."

[30564] — OS TRES OVERLAYS:
  "é pra existir 3 overlays. primeiro, o painel de baixo. nele eu ativo o segundo
   overlay, q é a legenda independente. ela mostra na minha tela, SEM FUNDO, SEM NADA,
   extremamente clean, e apenas algo pra estilizar ela ou dar corpo. tipo uma barra a
   esquerda dela, onde ela se apoia. o terceiro painel, é o da direita. onde deve ter
   todos os botoes. o painel de baixo, deve conter apenas o bare minimum. e é só no
   painel da direita que aparece historico de qualquer coisa."

[13770] — O REVAMP:
  "cada tema encontrado dentro dos .zip, fiquem com o design IGUAL, e só muda a posicao
   dos botoes. e pra realmente ser um revamp, cada zip diferente/tema, nao simplesmente
   uma skin por cima ou recolor."

[24395] — A TRADUCAO:
  "eu nao quero que seja por cima do nosso painel atual, ou na mesma div do painel. eu
   quero que tudo seja traduzido pro tamanho atual, e com os botoes atuais. o resto,
   tem que ser igual ... e o painel de baixo, ta errado. ele nao deve mostrar legenda
   de jeito nenhum. ele deve ser menor ainda, mais estreito, do tamanho dos botoes. os
   botoes tem que ser mais claros."

[32218] — A ULTIMA VEZ, quatro coisas:
  "a porra do painel, é pra ser minimo. a porra da legenda, é pra ser independente do
   painel, nao acoplado. e eu to vendo div com cor solida inves de invisivel. e eu to
   vendo pouquissimas fontes, inves das FONTES ORIGINAIS DO .ZIP ... o painel de baixo
   tem que ser movivel. e tira o botao da direita de mostrar legenda. o botao de
   mostrar a legenda ao vivo deve ser o live. e deve ser CLARO quando ta live e quando
   nao ta. e o botao de x pra dar hide introduzido em lugar aleatorio é estupido. bota
   ele na DIREITA DOS BOTOES."

[42268] e [50531] — O QUE EU CORRIGI HOJE:
  "cada design tem que ser igual dos zip, só os botoes que ficam no mesmo lugar. e nao
   é pra ter MOLDURA no painel. é pra ter moldura se o design das demos tem moldura.
   tira esse padrao de design de todos." / "em NENHUM design, eu quero MOLDURA, botao
   por cima da logo ou DIFERENTE na posicao em pixel de outro design" + "e tambem nao
   quero q apareça a BARRA DE SCROLL"

## O QUE CORRIGI HOJE

1. A MOLDURA DA JANELA. `panel.css:169` tinha `border: 1px solid var(--line)` no
   `.panel` -- um contorno a volta da JANELA INTEIRA -- e os 45 temas re-coloriam-no
   (`border-color: var(--line)`). Removido, e uma regra na folha carregada POR ULTIMO
   (`zip-overlay.css`, panel.html:10) mata qualquer moldura que os tres geradores
   voltem a desenhar no `.captions__body`.

2. A BARRA DE SCROLL. Estava em DOIS sitios e em DOIS motores: `panel.css` tinha
   `scrollbar-width: thin` e `.captions__body::-webkit-scrollbar { width: 3px }` -- e o
   WebView2 e Chromium, logo quem pintava era o SEGUNDO. Ambos a `none`/`display:none`.
   A lista CONTINUA a rolar; so a barra saiu.

3. A LEGENDA EM BAIXO. `panel.css:3052` dizia `top: 34px` na regra do float -- isso
   ESTICAVA a legenda de baixo da barra ate ao fundo, em vez de a pousar no fundo. E o
   teu pedido de origem ([860]): *"the live subtitles in the BOTTOM AND MIDDLE of the
   screen"*. Passou a `top: auto` com o `bottom: 0` que ja la estava, para a caixa se
   dimensionar pelo proprio conteudo e POUSAR no fundo. O palco ja e centrado
   (`justify-content: center` + `margin: 0 auto`).

## O LIMITE QUE EU NAO CONSIGO PASSAR SOZINHO, e digo-o

A legenda vive na MESMA JANELA que a barra. O comentario do proprio CSS explica:
*"The two overlays share one window, so they are STACKED, never overlapped"*. Uma
janela partilhada nao pode POUSAR a legenda no fundo da TELA e ao mesmo tempo ter a
barra no topo dela -- e e por isso que o print do dono mostra o painel E a legenda ao
mesmo tempo, que e o *"duas coisa sobrepostas"* que ele descreveu.

Para a legenda ser REALMENTE solta no meio-baixo da tela, como os .zip fazem, ela tem
de ser uma JANELA PROPRIA -- separada da barra. Isso e mudanca de shell
(`sotto_webview.py`), nao de CSS, e e a proxima coisa que eu faco.

## O QUE NAO FIZ, e nao finjo

* O design do print do dono esta partido de outra maneira: o painel mostra o historico
  E a legenda ao mesmo tempo.
* O botao por cima da logo nao foi tocado.
* Os botoes na mesma posicao em pixel: unifiquei no `gen_cinematic.py` ha dias, mas os
  outros dois geradores e os temas dos .zip nao foram verificados com os olhos.
* A bateria nao foi corrida depois destas mudancas de CSS.
