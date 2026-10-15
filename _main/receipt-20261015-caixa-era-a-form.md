# A CAIXA CLARA ERA A FORM -- e a cura e `TransparencyKey`, nao `BackColor`

## O QUE A SONDA PROVOU, com o ecra do dono como testemunha

A sonda `_main/_design-lane/capwin-probe.py` abre SO a janela da legenda (sem
single-instance, sem bridge, sem worker, portanto sem tocar na app dele), injecta texto,
espera e sai sozinha. Log medido:

    workArea=0,0 1920x1032
    caption window at 510,814 900x170
    saiu

**A JANELA ABRE.** O screenshot mostra a legenda no FUNDO-CENTRO da tela -- a 510,814
numa area de 1920x1032, que e exactamente o meio. Isto era a maior lacuna da rodada
anterior e esta fechada com os olhos, nao com leitura.

## Os tres testes que atribuiram a caixa clara

1. **O `body` pintado de VERMELHO -> a caixa ficou CLARA.** Logo NAO e a pagina.
2. **A form pintada de VERMELHO -> a caixa ficou VERMELHA.** Logo e A FORM.
3. **`TransparencyKey` posto a magenta -> a caixa CLARA DESAPARECEU.**

Os tres cabem numa linha cada, e juntos fecham a duvida que quatro tentativas de
adivinhacao nao fecharam.

## Porque e que `Color.Transparent` nao funcionava

Uma form de TOPO nao tem pai para onde compor. O .NET aceita o valor -- o pywebview ja
pos `SupportsTransparentBackColor` (winforms.py:289) -- e cai no `SystemColors.Control`,
o cinza claro `rgb(240,240,240)` que se via. **O caminho do WinForms para uma form de
topo e uma COR-CHAVE:** `TransparencyKey` tira do ecra tudo o que for exactamente essa
cor.

## E porque e que a janela PRINCIPAL parecia nao precisar disto

A pagina dela cobre a form INTEIRA com o slab translucido, portanto o cinza da form
nunca se ve. **A pagina da legenda e transparente DE PROPOSITO -- e foi por isso que a
form apareceu.** Nao era um defeito da segunda janela: era a primeira vez que a form
desta app ficou exposta.

## A cura, no shell

`_on_caption_before_show` (`sotto_webview.py`), assinado no `before_show` da janela da
legenda:

    magenta = Color.FromArgb(0xFF, 0xFF, 0x00, 0xFF)
    form.BackColor = magenta
    form.TransparencyKey = magenta

Magenta e nao branco: a legenda e `#f5f8fc`, e uma chave branca podia cair nas letras e
apaga-las. O magenta nao aparece em nenhuma folha do painel.

O `before_show` corre na THREAD DA UI, e tem de ser -- o controlador do WebView2 so se
toca la (`CoreWebView2Controller members can only be accessed from the UI thread`,
medido). `--opaque` continua a dar o slab escuro, porque esse flag existe para desistir
da transparencia de proposito.

`py_compile` rc=0, 534 430 B.

## UMA COISA QUE EU PARTI, e como

Ao inserir o metodo fiz `L.splice(i, 0, ...novo)` com `novo` a ser uma STRING (eu tinha
feito `.join("\r\n")` antes). **O spread de uma string insere um CARACTER por linha** --
o ficheiro ficou com um caracter por linha e `py_compile` deu `SyntaxError` na 4269.
Apanhado pelo compile, restaurado com `git checkout --`, e refeito com ARRAY. O ficheiro
esta em 10 267 linhas e compila. Fica escrito porque e a segunda vez nesta sessao que
uma insercao por indice me custa um ficheiro.

## O QUE FALTA

* A legenda antiga, dentro do painel, ainda la esta -- de proposito, enquanto a nova nao
  estiver confirmada pelo dono.
* O botao live ainda nao manda na janela; ela aparece com a primeira legenda.
* Nada disto foi visto DENTRO da app a correr: a app do dono tem o codigo velho e o
  hot-reload so recarrega o painel. O que esta provado e o CAMINHO, nao a app.
