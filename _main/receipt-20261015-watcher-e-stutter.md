# O WATCHER A CORRER, O ARRANQUE LIGADO, E O STUTTER ATRIBUIDO AO CAMINHO DE AUDIO

## As tuas duas ordens, feitas e medidas

1. **"faz correr"** -- `Steady Watcher` arrancada: tarefa `Running`, processo **pid 41764**,
   e o estado fresco a ser escrito (`heartbeat.json` 13:41:22, `health.json` 13:41:21,
   `mood=steady`).
2. **"faz ele iniciar com windows"** -- as SETE tarefas estavam `Disabled` e passaram
   todas a `Ready`: `Steady Watcher`, `-DeepSweep`, `-DumpCleanup`, `-EnsurePagefile`,
   `-LogSweep`, `-Retention`, `-WmiGuard`.

## O disco: TU TINHAS RAZAO, e eu estava errado

Eu apontei o `diskhealth` do watcher -- `volume I: 2.3% free` -- como causa. **E uma
percentagem sem o tamanho do volume e uma mentira por omissao:**

    I: livre 79,9 GB de 3726 GB
    H: livre 86,3 GB   G: 35,3 GB   D: 19,3 GB   C: 14,1 GB   E: 10,6 GB   F: 16,5 GB

**79,9 GB livres nao e um disco cheio.** E tu disseste-o antes de eu o medir: *"o disco
ja tava assim antes e nao travava"*. Tinhas razao nas duas metades -- no estado E na
conclusao. O detalhe do `health.json` esta VELHO (nao re-medido), e eu li-o como se
fosse fresco. Fica escrito: um `detail` sem data nao e uma medicao.

## O hook de rato: MEDIDO LIMPO, e o numero

O suspeito obvio era o hook global do Sotto (`WH_MOUSE_LL`, instalado no caminho de
input do Windows). Corri o instrumento que o proprio codigo nomeia,
`_main/hook-cost-oracle.py`, em processo:

    ARM A n=4000 mean=0.0057 p50=0.0042 p99=0.0275 max=0.4069 ms
    HOOK_COST at the measured cadence 11.82 clicks/min:
       arm A 0.0275 ms per click = 1.1702 s per hour of hook time
    VERDICT PASS

E, mais importante que o numero: **o callback NAO trata movimento de rato.** Em modo
normal so ouve botoes (`_on_mouse`, L2241: `elif message in (WM_LBUTTONDOWN,
WM_RBUTTONDOWN, WM_MBUTTONDOWN, WM_XBUTTONDOWN)`). Um movimento custa uma comparacao e
um `CallNextHookEx`. **O hook nao explica um rato que engasga ao mover.**

## A ATRIBUICAO: o caminho de AUDIO, e o sintoma encaixa

Medido com a app e o resto do PC a correr normalmente, janela de 5 s:

    System      3.36 s  = 67.2% de um core
    audiodg     0.75 s  = 15.0% de um core

**`System` a 67% de um core e tempo de DPC/ISR.** Num PC parado isso devia ser menos de
5%. E o `audiodg` -- o motor de audio do Windows -- a 15% de um core inteiro.

**PORQUE E QUE ISTO EXPLICA O SINTOMA EXACTO:** o tempo de DPC/ISR atrasa o caminho de
INPUT. O ponteiro do rato e servido por interrupcoes; a composicao do ecra corre no GPU
e num orcamento de frame. Um DPC longo come o primeiro e nao o segundo. **Rato a
engasgar com a imagem normal nao e um sintoma de CPU cheia nem de disco cheio -- e a
assinatura de latencia de DPC.**

**QUEM ALIMENTA O `audiodg`:** o Sotto captura o audio do SISTEMA em loopback WASAPI,
continuamente, sempre que o worker esta a ouvir. E o log mede a cadencia que isso impoe:

    BRIDGE_METER count=307556 in_window_s=30.0   ->  10 252 eventos por segundo

Mais o VoiceMeeter, que e um driver de audio virtual e e notorio por latencia de DPC.
Nenhum dos dois esta provado como A causa; os dois estao no caminho medido.

## A MEDIDA QUE FECHA ISTO, e o que eu faco a seguir

**Parar a captura 2 minutos e re-medir `System` e `audiodg` no mesmo instrumento.**
  * Se o `System` cair de 67% para perto de zero -> a captura e a causa, e ha cura
    (formato/periodo do loopback, ou desligar a captura quando ninguem esta a ver).
  * Se ficar em 67% -> a causa e outra coisa no sistema, e o Sotto fica limpo.

Nao o fiz ainda: parar a captura significa mexer na app que ele esta a usar, e isso e
uma decisao que se toma com ele a saber, nao por conta propria no meio de uma rodada.

## O QUE FICA ABERTO, e nao finjo

* A legenda na janela propria (objetivo do goal) esta provada em sonda e NAO confirmada
  na app a correr -- a app tem o codigo velho desde o ultimo arranque.
* O stutter esta ATRIBUIDO a um caminho, nao provado. Falta a medida de cima.
* O `diskhealth` do watcher continua a reportar um detalhe sem data; vale corrigi-lo
  para incluir o espaco ABSOLUTO, nao so a percentagem.
