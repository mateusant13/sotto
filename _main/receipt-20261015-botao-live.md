# O BOTAO LIVE MANDA NA JANELA DA LEGENDA -- e o sinal ja la estava

O objetivo, por palavras: *"Ligar/desligar pelo botao live"*. Era o que faltava.

## O sinal ja chegava, com o nome certo

`caption-float.js:243`, quando o estado do overlay MUDA:

    if (changed) {
      var b = window.sotto;
      if (b && typeof b.setPanelSurface === 'function') {
        b.setPanelSurface('strip', want ? 'float-on' : 'float-off');
      }
    }

E o shell recebe isso em `SottoHost._panel_surface`, que ja lia `payload.get('reason')`
e o passava adiante. **A razao E o estado.** Nao faltava porta nenhuma: faltava alguem
do outro lado a ler. Uma condicao, e a janela passa a seguir o botao:

    if reason in ('float-on', 'float-off'):
        self._shell.show_caption_window(reason == 'float-on')

**Sem polling, sem um segundo metodo de ponte, sem uma linha de JS.** Antes disto a
janela aparecia com a PRIMEIRA LEGENDA -- bom sinal, mas nao o botao: se ele ligasse o
live sem nada a tocar, a janela nao aparecia, e era exactamente o defeito que o objetivo
nomeia.

## E um docstring que estava FALSO, corrigido no caminho

`_panel_surface` dizia, desde sempre:

    `panel.js:1239-1243` is the ONLY caller

**E falso.** O `caption-float.js:243` tambem chama, e chama com a razao que interessa. O
docstring ficou corrigido: dois chamadores, nomeados.

Isto vale mais do que parece: eu quase passei a procurar um metodo de ponte NOVO para
ligar o botao, quando o caminho ja existia e so nao tinha leitor do lado do shell. **A
docstring a dizer "o UNICO chamador" foi o que me quase mandou construir uma segunda
ponte para um sinal que ja estava a chegar.**

`py_compile` rc=0, 540 698 B.

## O QUE FALTA NO OBJETIVO, e digo-o

1. **A legenda antiga, dentro do painel, ainda la esta** -- de proposito, e a rede de
   seguranca. Sai quando ele confirmar a nova a correr.
2. **A janela e fixa em 170 px.** O objetivo diz "dimensionada ao proprio conteudo";
   hoje o conteudo cabe, mas uma linha longa passa do tecto.
3. **NADA DISTO FOI VISTO DENTRO DA APP A CORRER.** A app do dono tem o codigo de ha 10
   horas; o `before_show` da janela da legenda so corre num arranque novo. O que esta
   provado e o CAMINHO -- sonda, screenshot e compilacao.
