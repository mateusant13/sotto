# O STUTTER: o Sotto esta LIMPO, a maquina esta carregada, e eu sou parte da carga

O dono, verbatim, duas vezes: *"meu mouse fica travando pra caralho mas parece que a
tela e normal"*. Este recibo e a atribuicao, com o numero de cada passo.

## 1. O DISCO: ele tinha razao, eu estava errado

Eu apontei `volume I: 2.3% free` do `health.json` como causa. Medido:
    I: livre 79,9 GB de 3726 GB
**79,9 GB livres nao e disco cheio.** Ele disse-o antes de eu medir: *"o disco ja tava
assim antes e nao travava"*. E o `detail` do `health.json` esta VELHO -- eu li-o como
fresco. Regra que fica: um `detail` sem data nao e uma medicao.

## 2. O HOOK DE RATO DO SOTTO: medido limpo

`_main/hook-cost-oracle.py`, em processo:
    ARM A n=4000  mean=0.0057  p99=0.0275  max=0.4069 ms
    0.0275 ms por clique = 1.17 s por HORA de hook time
    VERDICT PASS
E o decisivo: **o callback nao trata movimento** (`_on_mouse` L2241 so ouve botao). Um
movimento custa uma comparacao e um `CallNextHookEx`. Nao explica um rato que engasga AO
MOVER.

## 3. A CAPTURA DO SOTTO: NAO E A CAUSA -- e este e o teste que fecha

Medido com a app e o PC a correr normalmente, janela de 6 s cada:

    COM captura ..... System = 74,0% / 91,4% / 96,6% de um core   audiodg = 15-23%
    SEM captura ..... System = 109,4% / 78,9% / 40,9% / 42,2%     audiodg = 7,6-17,4%

**O worker do Sotto foi morto e o shell nao o repôs; o `System` continuou a 41-109% de
um core e o `audiodg` continuou a trabalhar.** Uma maquina sem captura nenhuma do Sotto
nao baixou o tempo de kernel. **A captura esta limpa.**

## 4. O QUE A MAQUINA ESTA A FAZER -- e eu sou parte disso

    chrome        pid=12100   84% de um core
    python        pid=3996    80%      <- as MINHAS sondas
    msedgewebview2 pid=38560  78%
    chrome        pid=40080   78%
    grep          pid=18024   77%      <- A MINHA FERRAMENTA DE BUSCA
    python        pid=13088   75%
    chatterino    pid=22616   65%
    WinRAR        pid=38728   64%      <- "Extraindo de warlock-and-boobs..."
    System        pid=4       32%
    dwm           pid=38324   32%

Aberto ao mesmo tempo: **WinRAR a extrair um arquivo**, VoiceMeeter, Discord,
Chatterino, NVIDIA Overlay, Taskmgr, e varias janelas do Chrome.

**A parte que eu devo dizer: o `grep` a 77% de um core e a MINHA ferramenta, e as duas
`python` sao as minhas sondas.** Nesta sessao eu corri -- so nesta rodada -- um oraculo
de hook com 12 000 disparos, uma varredura de rede de sessoes, e varias medicoes de 5 a
30 s. **Eu sou parte da carga que ele esta a sentir, e nao o conto como se fosse dele.**

## 5. O QUE NAO FICOU FECHADO

**Nao nomeei o driver.** O tempo de DPC/ISR esta alto e variavel (32-109% de um core) e
nao e do Sotto -- mas *qual* driver o come nao esta medido. O instrumento existe e esta
no disco: **`C:\WINDOWS\system32\wpr.exe`**, com o perfil `dpcisr`; o `xperf` NAO existe
nesta maquina. A corrida e `wpr -start dpcisr` -> 20 s -> `wpr -stop`, e o relatorio
nomeia o modulo. **E o proximo passo, e e uma medida curta.**

Suspeitos que o quadro sustenta, por ordem: (a) o driver de audio virtual **VoiceMeeter**
com `audiodg` a trabalhar; (b) a contencao de CPU com oito processos entre 60% e 84% de
um core; (c) o **WinRAR a extrair**, que satura o IO; (d) `dwm` a 32%.

## As ordens dele, feitas
  * "faz correr" .......... `Steady Watcher` a `Running`, pid 41764, heartbeat fresco
  * "iniciar com windows" . as SETE tarefas passaram de `Disabled` a `Ready`
