# A LEGENDA FLUTUA: as duas curas juntas e um screenshot que o prova

A corrida limpa desta rodada -- sonda com as DUAS curas e a fixture, um screenshot:

    workArea=0,0 1920x1032
    caption window at 510,814 900x170
    INVOKE_WEBVIEW2_BGC set=transparent
    FORM_TRANSPARENCYKEY set=magenta
    WEBVIEW2_BGC set=transparent
    fixture injectada
    a fechar

E o que o ecra mostra: **a legenda "Uma vez que voce foi." no FUNDO-CENTRO da tela,
com a barra LED verde, e o conteudo que esta por tras VISIVEL ATRAVES DELA.** A caixa
opaca que atravessou quatro rodadas desapareceu. O texto le-se pelo proprio peso e pela
sombra de legibilidade, que e o corpo que o zip desenha.

## A cura completa, e as duas metades sao precisas

    # 1. A FORM. Uma form de TOPO nao tem pai para onde compor, e
    #    `BackColor = Color.Transparent` cai no `SystemColors.Control`. Cor-chave:
    magenta = Color.FromArgb(0xFF, 0xFF, 0x00, 0xFF)
    form.BackColor = magenta
    form.TransparencyKey = magenta

    # 2. O WEBVIEW2, que pinta o proprio fundo por cima da form ja transparente.
    #    Tem de ser na THREAD DA UI -- `form.Invoke` e a marshala.
    form.Invoke(Action(_kill_wv_bg))     # DefaultBackgroundColor = Transparent

Nenhuma das duas chega sozinha: foi medido. A form sozinha deixa o escuro do WebView2;
o WebView2 sozinho deixa o cinza da form.

## O caminho ate aqui, porque a atribuicao e a parte util

  body a VERMELHO, form transparente ... caixa CLARA ..... nao era a pagina
  form a VERMELHO .................... caixa VERMELHA .. e a FORM
  form MAGENTA + chave MAGENTA ....... caixa ESCURA .... a form saiu; sobra 2a camada
  form VERDE + chave MAGENTA ......... caixa VERDE ..... a chave remove a cor EXACTA
  + form.Invoke no WebView2 .......... RESOLVIDO

## Esta no shell desde `380ec47`

`_on_caption_before_show`, assinado no `before_show` da janela da legenda. `py_compile`
rc=0. `--opaque` continua a dar o slab escuro.

## O QUE FALTA, e nao finjo

1. **NAO foi visto DENTRO da app a correr.** O que esta provado e o CAMINHO: a sonda
   constroi a janela exactamente como o shell a constroi, com as mesmas curas. A app do
   dono tem o codigo velho; o `before_show` da janela da legenda so corre num arranque
   novo. **E um arranque que confirma, e e o proximo passo.**
2. A legenda antiga, dentro do painel, ainda la esta -- de proposito, para ele nao ficar
   sem legenda nenhuma se a nova falhar. Sai quando ele confirmar.
3. O botao live ainda nao manda na janela; ela aparece com a primeira legenda.
4. A janela e fixa em 170 px de altura. O objetivo diz "dimensionada ao proprio
   conteudo"; hoje o conteudo cabe, mas uma linha longa pode passar de 170.
