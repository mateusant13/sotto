# A CAIXA CINZENTA: a cura estava a correr CEDO DEMAIS -- e o Sotto esta EXONERADO

## 1. A caixa cinzenta, e a causa esta escrita no proprio shell

O dono, com o print: *"essa caixa de merda na tela ta parecendo transparente pra
voce?"*. **Nao estava.** E o log dizia as duas curas aplicadas:

    14:33:26.384  CAPTION_FORM_TRANSPARENCYKEY set=magenta reason=overlay-not-a-slab
    14:33:26.385  CAPTION_WEBVIEW2_BGC set=transparent

**A causa esta no comentario de `_on_before_show`, escrito por quem fez aquilo:**

    "The earliest hook that exists: the WinForms form is built and
     EnsureCoreWebView2Async has been called but HAS NOT COMPLETED."

**O `before_show` corre ANTES de o `CoreWebView2Controller` existir.** Ali o
`DefaultBackgroundColor` e uma propriedade sem controlador por tras: fica guardada e NAO
TEM EFEITO, e o WebView2 acaba por pintar o fundo DELE por cima da form que ja esta
transparente. **A caixa cinzenta e o WebView2, nao a form.**

PORQUE E QUE A SONDA PASSOU E A APP NAO: na sonda o `form.Invoke(...)` ficou em FILA e
correu depois de o controlador subir. No shell o `before_show` **ja corre na thread da
UI**, portanto o `Invoke` executa NA HORA -- cedo. **A mesma cura, aplicada no mesmo
sitio, com um resultado diferente por causa da thread em que o evento chega.**

A CURA: `caption_window.events.loaded += self._on_caption_loaded`, que e o primeiro
evento em que o controlo existe. `py_compile` rc=0, 547 847 B. **NAO VERIFICADO** -- ele
fechou a app antes de eu conseguir olhar.

## 2. O SOTTO ESTA EXONERADO -- medido com ZERO processos dele

Ele escreveu: *"acabei de fechar o app. meu sistema ta simplesmente nojento de travando."*
Isso tornou possivel a medida que faltava. Contagem e resultado:

    processos do Sotto AGORA: 0
    restam depois de matar: 0
    webview2 do Sotto: 0

    SOTTO FORA 1   System=32,0% de um core   audiodg=10,4%
    SOTTO FORA 2   System=28,1%              audiodg= 7,6%
    SOTTO FORA 3   System=29,9%              audiodg= 7,0%

**Sem um unico processo do Sotto, o `System` (DPC/ISR) fica a 28-32% de um core e o
`audiodg` a 7-10%.** O travamento que ele sente com a app fechada NAO E O SOTTO. E o
numero e o mesmo que eu media COM a app a correr -- o que diz que o Sotto nao acrescenta
nada mensuravel a esse caminho.

## 3. O profiling, e o que correu mal nele

* `wpr -start dpcisr` .......... **esse perfil NAO EXISTE** nesta instalacao
  (`0x80070002`). Os perfis disponiveis estao listados; ha um chamado **`Audio`**,
  descrito como *"Audio glitches"*, que e o perfil certo para este sintoma e e LEVE.
* `wpr -start CPU` ............. correu, mas produziu **2017 MB de ETL** em 20 s e o
  `tracerpt` gerou **2770 MB de CSV**. Parei-o e apaguei os dois: ~4,8 GB devolvidos ao
  I:, que ficou com 69,1 GB livres. **A licao: um perfil com stacks, em 20 s, neste
  volume, e uma medida cara demais para o que ela responde.**
* Contadores CIM ................ **FUNCIONAM**, ao contrario do `Get-Counter` (que
  devolveu zero). Por CPU: `0  DPC=5%  Interrupt=5%  User=23%  Privileged=23%` -- o
  CPU 0 carrega o DPC e o tempo privilegiado. **E o instrumento a usar a seguir.**

## 4. O que NAO esta medido, e digo-o

* **Que driver come o tempo de DPC.** E a pergunta dele e continua aberta. O caminho
  barato e `wpr -start Audio` (leve), ou os contadores CIM por CPU ao longo do tempo
  para ver se acompanham o `audiodg`.
* Se a cura do `loaded` tira a caixa cinzenta. Compila; nao foi vista.
* Onde esta a perda de performance que ele pediu para eu achar. O subagente esta a
  construir o instrumento do caminho `emit`/`meter` em `_main/`; o numero que ja existe
  e `BRIDGE_METER 307556 eventos / 30 s = 10 252/s`, e ele nao esta explicado.
