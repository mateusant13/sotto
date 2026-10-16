# F8, A HIPOTESE QUE FALHOU: margin-left:auto NAO move a fileira

## O que tentei e porque

Apos fixar a largura do botao (84 px) e o gap (6 px), medi de novo:

    pd-cine   row x=62  w=288  gap=6px    hide dir=350
    theme-2   row x=78  w=288  gap=6px    hide dir=366

Mesma largura, mesmo gap, e a fileira 16 px mais a esquerda no pd-cine. A minha hipotese:
`margin-left: auto` em `.panel__controls` empurra-a para a direita em flex E em grid, e como
as larguras batem, as duas arestas passariam a coincidir.

    body .panel__controls { margin-left: auto !important; }

## O que a re-medicao disse

    pd-cine   row x=62   (IDENTICO)
    theme-2   row x=78   (IDENTICO)

**A regra nao mudou nada.** A hipotese estava errada -- provavelmente o cabecalho grid do
theme-2 coloca a fileira numa AREA de grelha cujo tamanho decide a posicao, e o cabecalho
flex do pd-cine faz o mesmo por outro caminho. `margin-left: auto` nao vence nenhum dos dois.

## O que fiz com isso

**REMOVI A REGRA.** Uma declaracao inerte com `!important` na folha que carrega por ultimo e
divida -- a propria classe que os oraculos de regras mortas deste repo existem para apanhar.

O gap fixo (`gap: 6px`) FICA: esse sim foi medido a funcionar (288 px nos dois, gap 6px nos
dois, e o X dentro da janela nos dois).

## O estado do F8

  * largura do theme-button .... FECHADA (84 px nos dois, medido)
  * gap da fileira ............. FECHADO (6 px nos dois, medido)
  * POSICAO da fileira ......... ABERTA (x=62 contra x=78, medido duas vezes)

**A terceira causa -- o cabecalho ser `display:flex padding=36px` num e `display:grid
padding=0px` noutro -- continua sem cura.** E eu nao vou adivinhar outra: com o contexto
que me resta, dizer o nome exacto da diferenca (o layout do `.panel__header`, medido) e mais
util do que uma terceira tentativa sem medida.
