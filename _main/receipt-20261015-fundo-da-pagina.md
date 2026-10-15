# A CAIXA: o fundo vinha da PROPRIA PAGINA -- e a regra foi para a folha que e a ultima

## O que ainda pintava, depois de a transparencia do WebView2 ficar certa

O log ja dizia CAPTION_WEBVIEW2_BGC set=transparent at=loaded-invoke, e a captura da regiao
da janela continuava a mostrar caixa. A causa esta no panel.css:105-127:

    html,
    body {
      background: rgba(11, 15, 20, 0.98);   <- A BASE OPACA
    }

Essa base existe por uma razao medida -- e a cor que se ve quando o WebView2 nao pinta. Mas
na janela da legenda ela E a caixa: escuro a 98% por cima do ambiente de trabalho.

E o detalhe que interessa: a caption.html JA trazia
html, body { background: transparent !important } no proprio <style>, DEPOIS das quatro
folhas -- verifiquei a ordem, e esta mesmo depois. NAO CHEGOU. Em vez de ir atras da
especificidade, a regra foi para a folha que e GARANTIDAMENTE a ultima (panel.html:10), com
o escopo no atributo que so esta pagina tem:

    html[data-caption-window],
    html[data-caption-window] body {
      background: transparent !important;
      background-color: transparent !important;
      background-image: none !important;
    }

html(0,1,0) + body(0,0,1) contra o panel.css (0,0,1): ganha, e nao depende da ordem nem de
!important sozinho. E assim nao toca em nada do painel.

## A prova, e e a captura DA REGIAO -- nao do ecra

    I:/cc-tmp/capwin-only.png  -- 510,814 900x170, a janela mais nada

O que se ve: a legenda com a linha anterior e a viva, e o conteudo do ambiente de trabalho A
ATRAVESSAR no canto superior direito (wie... e uma imagem). SEM RETANGULO, SEM ARESTA.
Comparado com o print do dono -- um cinzento de bordas nitidas -- nao ha borda nenhuma agora.

## As duas metades que fizeram isto, e nenhuma chega sozinha

  1. o WebView2 -- loaded + Invoke, porque o before_show corre antes de o controlador
     existir, e o loaded chega numa thread que nao pode tocar-lhe;
  2. a pagina -- html[data-caption-window] na ultima folha, porque o panel.css da a
     html, body uma base opaca que o !important do <style> da propria pagina NAO derrubou.

E eu mostrei-te a primeira a dizer que estava fechada, e nao estava. A licao e a que ja
ficou escrita noutro recibo: UMA CURA QUE DISPARA NAO E UMA CURA QUE FUNCIONA, e so a
CAPTURA DA REGIAO o diz.

py_compile rc=0. A app foi reiniciada com isto.
