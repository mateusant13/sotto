# A BARRA ILEGIVEL: tinta escura sobre placa escura -- e a contradicao estava escrita

## As TUAS palavras, do disco, das ultimas 200 horas

Extrai os 82 prompts da sessao e filtrei os que falam de botoes e barras. Sao 15, e os que
mandam sao estes:

[41856] 10-14 23:17
  *"tira em curso e historico das barras. tira o botao de transcript. OS BOTOES SAO BOTOES
   SIMPLES E PEQUENOS POREM VISIVEIS O SUFICIENTE PRO USUARIO. e nao e pra ter tema branco."*

[32218] 10-12 23:52
  *"o painel de baixo tem que ser movivel pra cima ou pra baixo ou pros lados. e TIRA O BOTAO
   DA DIREITA DE MOSTRAR LEGENDA. O BOTAO DE MOSTRAR A LEGENDA AO VIVO DEVE SER O LIVE. e
   deve ser CLARO QUANDO TA LIVE E QUANDO NAO TA. e o botao de x pra dar hide introduzido em
   lugar aleatorio e estupido. BOTA ELE NA DIREITA DOS BOTOES."*

[24395] 10-12 07:21
  *"ele deve ser menor ainda, mais estreito, do tamanho dos botoes. OS BOTOES TEM QUE SER
   MAIS CLAROS."*

## O que estava a falhar, e a causa

A barra falhava em **"visiveis o suficiente"** e em **"CLAROS"** -- e a causa e uma
CONTRADICAO que ficou dentro do `zip-overlay.css`:

    L111  body[data-surface="strip"]:not([data-float="on"]) .panel {
            background: rgba(11, 15, 20, 0.98) !important;     <- PLACA ESCURA

    L122  .stripbar__brand, .strip-button, .stripbar__state {
            color: #0b0f14 !important;                          <- TINTA ESCURA

    L158  .stripbar, .stripbar * { color: #0b0f14 !important; } <- TINTA ESCURA EM TUDO

E o comentario por cima destas linhas diz, literalmente: *"every visible thing sits on a
LIGHT slab, so a single descendant rule is both simpler and more truthful"*. **A placa era
CLARA quando estas regras foram escritas. Alguem -- eu, hoje -- escureceu a placa para tirar
o branco que ele reportou, e nao tocou na tinta que dependia dela.** Ficou tinta escura sobre
placa escura, e o que ele viu foi `CAPTIONS OFF` e `SOTTO` a desaparecer.

## O que mudou

    tinta ......... #0b0f14  ->  #e8edf4     (clara)
    muted ......... rgba(0,0,0,0.35)  ->  rgba(232,237,244,0.5)
    bordas ........ rgba(0,0,0,0.38)  ->  rgba(232,237,244,0.3)
    hover ......... #ffffff  ->  rgba(232,237,244,0.16)   (o hover BRANCO numa barra escura)

E a LIVE, que era `background: #0b0f14` com texto verde -- um botao que nao tinha forma
porque o fundo dele era a cor da barra:

    background: rgba(55, 214, 122, 0.18) !important;
    color: #37d67a !important;
    border-color: #37d67a !important;

**Um fundo verde translucido e uma borda verde dao-lhe corpo sem mudar a paleta -- e isso e
o "CLARO quando ta live e quando nao ta" que ele pediu.**

## O que fica por fazer, com as palavras dele a guiar

* **"restaura os botoes que tinha"** -- ainda nao sei QUAIS sairam. As palavras dele nomeiam
  os que SAEM (transcript, o da direita de mostrar legenda), nao os que voltam. Preciso de
  comparar o markup actual com uma revisao anterior da barra, e isso e uma medida, nao uma
  suposicao.
* **O erro vermelho** -- `WasapiError Initialize(SHARED|LOOPBACK) failed 0x8889000A`, que e
  `AUDCLNT_E_DEVICE_IN_USE`. Ele ja mandou arrumar isto em [41856]: *"sotto ta reclamando de
  coisa nao carregada, com erro vermelho. arruma"*. **Continua la, e mostra-lhe um codigo
  hexadecimal em vez de uma frase.**
