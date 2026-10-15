# A CAIXA CINZENTA: loaded + Invoke, as DUAS metades -- e vi-o com os olhos

## O erro que faltava, medido na sonda

A cura anterior punha a transparencia do WebView2 no before_show. Corrigi para o
loaded -- e a sonda devolveu:

    LOADED_BGC_FAILED InvalidOperationException:
    CoreWebView2Controller members can only be accessed from the UI thread.

O evento loaded NAO corre na thread da UI. O controlador JA EXISTE -- e um acesso a
membro, nao um nulo -- mas tocar-lhe daquela thread e recusado. E no shell isso estava
dentro de um try, portanto a cura falhava em SILENCIO e o log dizia apenas
CAPTION_WEBVIEW2_BGC_FAILED at=loaded.

## As duas metades, e nenhuma chega sozinha

  * loaded -- porque o before_show corre ANTES de o controlador existir, e ali a
    propriedade fica guardada sem efeito (o comentario de _on_before_show di-lo por
    palavras: EnsureCoreWebView2Async has been called but has not completed);
  * Invoke -- porque o loaded chega numa thread que nao pode tocar no controlo.

O Invoke que ja vivia no before_show fica, mas e INUTIL: corre cedo demais para valer.
Fica escrito para nao se corrigir o sitio errado outra vez.

## E VERIFIQUEI COM OS OLHOS, capturando SO a regiao da janela

O dono: e pra TU printar as coisas, nao eu. e e pra tu printar so a tela do app ou da
funcao, nao da minha tela inteira. A captura e de 510,814 900x170 -- a janela, mais nada.

    ANTES  (LOADED_BGC_FAILED) ............... retangulo CINZENTO uniforme, a legenda dentro
    DEPOIS (LOADED_INVOKE_BGC set=transparent) a legenda FLUTUA: le-se HUGE Claude Code
    Update, & Anthropic IPO! AI News em baixo e wie... no canto superior direito --
    conteudo do ambiente de trabalho A ATRAVESSAR a janela.

A caixa desapareceu. O que resta de escuro atras do texto e o proprio ambiente, nao uma
placa: a prova e que o conteudo de baixo e legivel ATRAVES dela.

py_compile rc=0, 548 938 B.

## A licao, a terceira vez hoje que a mesma coisa me apanha

UMA CURA QUE DISPARA NAO E UMA CURA QUE FUNCIONA. O log dizia
CAPTION_WEBVIEW2_BGC set=transparent e a caixa estava la. Depois passou a dizer at=loaded
e a caixa continuava -- porque a excepcao era apanhada e so o FAILED a denunciava,
perdido entre milhares de linhas. O que fechou isto foi OLHAR a regiao da janela depois
de cada tentativa, e nao ler o log.

## O que continua por fazer

* Reiniciar a app para ele receber a cura -- feito a seguir a este commit.
* O driver que come o DPC (28-32% de um core com o Sotto FORA) continua sem nome.
* O subagente do caminho emit/meter continua a correr.
