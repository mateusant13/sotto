# A CAIXA TEM DUAS CAMADAS: a FORM e depois o WEBVIEW2 -- as duas fechadas

## Os testes que atribuiram cada camada (sonda isolada, ecra do dono como testemunha)

  1. `body` a VERMELHO, form a transparente ....... caixa CLARA -> nao era a pagina
  2. form a VERMELHO .............................. caixa VERMELHA -> e a FORM
  3. form MAGENTA + `TransparencyKey` MAGENTA ..... caixa ESCURA -> a form saiu, sobra
     uma SEGUNDA camada
  4. form VERDE + chave MAGENTA ................... caixa VERDE -> a chave so remove a
     cor EXACTA, e prova que o mecanismo funciona como esperado
  5. `form.Invoke(...)` a por `webview.DefaultBackgroundColor = Transparent`
     .............................................. `INVOKE_WEBVIEW2_BGC set=transparent`

## O que cada camada e

**A FORM.** Uma form de TOPO nao tem pai para onde compor, portanto
`form.BackColor = Color.Transparent` -- que o shell ja fazia -- cai no
`SystemColors.Control` do .NET, o cinza `rgb(240,240,240)`. O que funciona numa form de
topo e uma COR-CHAVE: `form.BackColor = form.TransparencyKey = magenta` tira do ecra
tudo o que for exactamente essa cor. Magenta e nao branco porque a legenda e `#f5f8fc`
e uma chave branca podia apagar letras.

**O WEBVIEW2.** Com a form ja removida sobra um retangulo do tamanho da janela -- e e o
CONTROLO WebView2, que pinta o proprio fundo. Medido nos dois lados:
  * posto no `before_show` ................ nao pega
  * posto de outro thread ................. `CoreWebView2Controller members can only
    be accessed from the UI thread` -- e o que explica o primeiro
  * posto com `form.Invoke(...)` .......... RESPONDE (`INVOKE_WEBVIEW2_BGC
    set=transparent`)

## A cura que ficou no shell, em `_on_caption_before_show`

    magenta = Color.FromArgb(0xFF, 0xFF, 0x00, 0xFF)
    form.BackColor = magenta
    form.TransparencyKey = magenta
    form.Invoke(Action(_kill_wv_bg))     # poe DefaultBackgroundColor=Transparent

`--opaque` continua a dar o slab escuro, porque esse flag existe para desistir da
transparencia de proposito. `py_compile` rc=0, 535 830 B.

## A EXPLICACAO DE TUDO, que so aparece quando se junta as duas camadas

**Porque e que a janela PRINCIPAL desta app nunca mostrou esta caixa?** Porque a pagina
dela cobre a form INTEIRA com o slab translucido e o WebView2 pinta por cima dele. O
cinza da form e o fundo do WebView2 nunca se veem. **A pagina da legenda e transparente
DE PROPOSITO -- e foi por isso que as duas camadas apareceram pela primeira vez.** Nao
era um defeito da segunda janela; era a primeira vez que a base desta app ficou exposta.

## O QUE FALTA

* Confirmar as DUAS camadas juntas numa so corrida: as duas foram medidas em separado, e
  a sonda que as juntou foi morta pela sonda antes da fixture. Falta UMA corrida limpa
  com as duas curas e um screenshot.
* A legenda antiga, dentro do painel, ainda la esta -- de proposito, ate o dono confirmar.
* O botao live ainda nao manda na janela; ela aparece com a primeira legenda.
* Nada disto foi visto DENTRO da app a correr: o que esta provado e o CAMINHO.
