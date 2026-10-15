# A JANELA DA LEGENDA ABRE -- e a caixa clara e um defeito ABERTO, medido

## O QUE ESTA PROVADO (sonda `_main/_design-lane/capwin-probe.py`, isolada)

A sonda abre SO a janela da legenda -- sem single-instance, sem bridge, sem worker,
portanto nao toca na app do dono -- injecta texto, espera e sai sozinha. Log medido:

    workArea=0,0 1920x1032
    caption window at 510,814 900x170
    FORM_BACKCOLOR set=transparent
    fixture injectada
    saiu

E o screenshot do ecra mostra a legenda **no fundo-centro da TELA**, com a barra LED
verde a esquerda e o texto "Uma vez que voce foi." -- a 510,814, que e exactamente
meio-centro do workArea. **A POSICAO E O CAMINHO DA SEGUNDA JANELA ESTAO PROVADOS.**
A pagina pinta o que deve: fundo transparente no render headless, a linha viva, a
anterior mais fraca, os creditos, sem moldura e sem scrollbar.

## O DEFEITO ABERTO: uma caixa clara por tras da legenda

O que se ve no ecra real e um retangulo claro do tamanho exacto da janela
(900x170) por tras do texto. NAO aparece no render headless -- logo nao e a pagina,
e a JANELA.

O QUE JA TENTEI, e o que cada tentativa mediu:
  1. tirar `background_color=` da criacao ........ NAO resolveu
  2. `form.BackColor = Color.Transparent` ........ disparou, NAO resolveu
  3. `form.webview.DefaultBackgroundColor = Transparent` .. disparou, NAO resolveu
  4. po-lo TARDE (1,2 s) .......................... FALHOU com
     `InvalidOperationException: CoreWebView2Controller members can only be accessed
      from the UI thread` -- o controlador so se toca na thread da UI, o que explica
     porque (3) tem de ser posto no `before_show`, que corre nessa thread.

O MECANISMO DO PYWEBVIEW, lido no sitio (`webview/platforms/winforms.py:286-292`):

    if window.transparent and self.browser:
        self.SetStyle(WinForms.ControlStyles.SupportsTransparentBackColor, True)
        self.browser.DefaultBackgroundColor = Color.Transparent
    else:
        self.BackColor = ColorTranslator.FromHtml(window.background_color)

**No ramo transparente ele NAO poe `self.BackColor`** -- a form fica com o
`SystemColors.Control` do .NET (medido no comentario do shell como `rgb(240,240,240)`).
A cura do shell existe exactamente para isso e EU TENHO-A posta; ela dispara e a caixa
fica. **Logo o que pinta o retangulo e um TERCEIRO caminho, ainda nao atribuido.**

## A PROXIMA MEDIDA, e e o que eu faco a seguir

A janela PRINCIPAL desta app E transparente -- os screenshots do dono mostram o
ambiente de trabalho por tras do painel. Entao o caminho bom existe no mesmo processo.
A medida que resolve isto sem adivinhar: **a mesma sonda a abrir DUAS janelas -- a
principal (transparente, sabida boa) e a da legenda -- e um screenshot das duas no
mesmo ecra.** A diferenca entre elas e o que falta, e ve-se.

Sonda guardada: `_main/_design-lane/capwin-probe.py`. Receita para a correr:
  "C:/Program Files/Python311/pythonw.exe" _main/_design-lane/capwin-probe.py
e, 4 s depois, um screenshot do ecra. `I:/cc-tmp/capwin3.ps1` faz as duas coisas.
