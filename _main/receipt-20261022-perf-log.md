# Recibo — a ferramenta de performance, e o que ela mediu (2026-10-22)

## O pedido, verbatim

> *"faz uma ferramenta de loggar a performance que o sotto causa. depois, abre o sotto. veja se tu logga
> coisas como meu sistema travando ou dando stutter. usar isso pra melhorar o sotto. vamos usar tools
> corretas e robustas. pode usar algum pacote ja existente e etc."*

## A ferramenta

`_main/sotto-perf-log.py` — JSONL + relatório. **psutil 5.9.8** (já instalado) para CPU/DPC/interrupt/
disco/processos; `wpr.exe` existe (ETW) e é a ferramenta certa para uma caça **profunda**, mas escreve
gigabytes em discos a 0,4-20 % livres — declarado, não usado nesta passagem.

Quatro medidas, cada uma pela razão escrita no ficheiro:

| # | o que | como |
|---|---|---|
| 1 | **o stutter** | slip de um `sleep(25 ms)`: quanto tardou a acordar. `p50/p90/p99/max` e a contagem de slips > 50 / 100 / 250 ms |
| 2 | CPU por espécie | `cpu_times_percent` incl. **`interrupt`** e **`dpc`** (DPC corre acima de qualquer thread: é a fonte clássica de freeze e não aparece no CPU de nenhum processo) |
| 3 | disco e RAM | `disk_io_counters` (MB/s e % do intervalo em I/O) + RAM disponível |
| 4 | **a família do Sotto** | por **ÁRVORE de processos** (descendentes da shell), nunca por nome: `shell`/`worker`/`webview`, cada pid novo com o instante, e os `msedgewebview2.exe` que **não** são do Sotto contados à parte |

```
python _main\sotto-perf-log.py --launch --seconds 150     # 8 s de base, abre a app, mede
python _main\sotto-perf-log.py --report <ficheiro>.jsonl
python _main\sotto-perf-log.py --solo --seconds 45        # sonda sozinha (sem amostrador)
python _main\sotto-perf-log.py --in-process-probe ...     # o desenho ANTIGO, para A/B
```

## O defeito do PRÓPRIO instrumento (o primeiro achado, e o mais importante)

A 1.ª corrida (150 s, com a app) reportou o seguinte: **p99 209 ms, max 1135 ms, 25 slips acima de
250 ms** — com a família do Sotto a **n=1 / 121 MB**, CPU 38-53 %, DPC < 1,5 % e o disco a 0 % de I/O.
Uma máquina ociosa não atrasa um timer um segundo.

A causa era o instrumento: a sonda corria numa **thread** do mesmo processo do amostrador, e o
amostrador varre a tabela de processos (722 vivos, a pedir a linha de comando a cada um) a cada 5 s —
**segurando o GIL**. Medido com o falsificador (mesma máquina, mesmos 45 s, mesma app aberta):

| sonda | p50 | p90 | p99 | max | >100 ms |
|---|---|---|---|---|---|
| **processo próprio** (a correcta) | **0,5 ms** | 1,5 | 10,0 | 64,7 | **0** |
| thread a partilhar o GIL (o 1.º desenho) | 7,4 ms | 57,4 | 267,8 | 755,4 | 44 |

⇒ **o "stutter de 1,1 s" era o instrumento a medir-se a si mesmo.** A sonda passou para **processo
próprio** (imune por construção) e o relatório passou a imprimir a espécie da sonda. Segundo defeito,
também corrigido: o `Sink` estava *line-buffered* e custava **3,5 ms por amostra de 25 ms** (525 ms de
contabilidade numa corrida de 6 s); com 64 KB de buffer caiu para **11,5 ms**.

## O que a ferramenta mediu, com a app SÃ

Estado real: **10 processos, pico de 1801 MB, 35,0 s de CPU em 120 s** (29 % de um núcleo, contínuo).

| papel | pico n | CPU | RSS |
|---|---|---|---|
| **worker** | 1 | **104,3 %** | **1271 MB** |
| webview | 7 | 30,6 % | 361 MB |
| shell | 1 | 19,6 % | 161 MB |

**Por que o worker aparece a 104,3 % e 1271 MB nesta janela:** nos 120 s medidos couberam **dois
carregamentos do modelo** (o 26668 a carregar até 03:26:16 e o 28920 a carregar de 03:28:01 a
03:28:17). Não é o custo de repouso do worker; é a soma de dois loads. O repouso medido a seguir é
**CPU 25,9 s em ~3,3 min** com **3070 MB privados / 21 MB residentes**.

**O stutter da máquina com o Sotto a correr é pequeno e não é do Sotto:** p50 0,7 ms, p90 8,3,
**p99 27,5**, max 103,2 — **4 slips acima de 50 ms em 4280 amostras**. Os dois piores (103 e 94 ms)
coincidem com a família a n=9 / 459 MB, não com CPU nem com disco.

## O defeito de produto que a medição expôs: o TREADMILL do dispositivo mudo

No log da app, com timestamps:

```
03:25:51  BRIDGE_SPAWNED pid=26668                       (preload)
03:26:16  BRIDGE_LOAD_MS ms=24750 worker_load_s=22.25    <- 24,75 s a carregar o modelo
03:27:43  BRIDGE_STATUS_NOAUDIO state="silent-device"  "VoiceMeeter Output (VB-Audio Vo [MME]
                                                        peaked 0.000122 < floor 0.002"
03:27:46  BRIDGE_EXIT pid=26668 rc=3 captions=0
03:28:01  BRIDGE_SPAWNED pid=28920                       <- 15 s depois, outra vez
03:28:17  BRIDGE_LOAD_MS ms=16235 worker_load_s=14.15
```

**O ciclo é REAL mas NÃO é perpétuo — e a primeira versão deste recibo disse "para sempre", o que
era FALSO.** O que a leitura do código e o log de seguida mostram:

1. O 1.º worker (26668) não morreu de silêncio puro: morreu com **`stderr_tail=["ROTATION_CEILING
   reached rotations=…`** — esgotou os candidatos de tap e todos estavam planos. `BRIDGE_DEATH rc=3
   deaths=1 kind=no-audio`.
2. A shell respawnou-o **15 s** depois (`03:28:01`) — que é exactamente `no_audio_backoff_base *
   2**0` (`sotto_webview.py:13022-13025`), ou seja a escada a funcionar.
3. O 2.º worker (28920) **não voltou a morrer**: entra em `BRIDGE_SILENT_BENIGN ms=30000` a cada
   30 s, com `state=no-audio` benigno. Logo o `no_audio_restarts` fica em 1 e o tecto nunca chega a
   ser atingido.
4. O tecto existe e é explícito (`:13004-13021`): `no_audio_restart_cap=3`, e depois
   `BRIDGE_RESTART_SUPPRESSED reason=… why=restarting-cannot-fix-a-routing-problem resume=press-Alt+C`
   com uma mensagem para o dono. **O desenho já protege a máquina** — é a ORDEM n.º 3 a funcionar.

**O modelo NÃO é libertado quando o worker fica benigno** (medido 03:31: `rss 21 MB` **mas
`private 3070 MB`**): as páginas foram *trimmed*, a memória está comprometida à mesma.

⇒ O custo real medido, e não um treadmill infinito: **uma recarga redundante** de 1,2 GB (o 1.º
worker gastou 24,75 s a carregar, o 2.º 16,2 s, ambos para aprenderem a mesma coisa), e 3 GB
comprometidos por um worker que não transcreve nada.

**O defeito de RAIZ, e o que o dono sente:** `peak=0.000122 < floor 0.002` em todos os candidatos —
com este dispositivo **o Sotto não transcreve nada**. O log di-lo a cada 30 s. A cura é de **rotagem**
(VoiceMeeter / som do Windows) e é decisão do dono, não código.

**A melhoria que a ordem dos eventos justifica (proposta, não feita):** o modelo carrega **antes** de
se saber que o dispositivo está plano — `state="model-loaded"` em `worker/sotto_worker.py:5261`, a
rotação de dispositivos em `:6308-6760`. Numa secretária sem nada roteado, isso paga 1,2 GB de leitura
e 15-25 s de CPU **para depois descobrir que não havia nada para captar**. Uma verificação de tap
barata (abrir e medir uma janela curta) antes do load pouparia o load inteiro nesse caso. Tem um
custo: acrescenta a verificação ao caminho feliz. Vai ao dono como decisão.

## Dois factos de ambiente medidos ao abrir a app

1. **Não se pode lançar a app a partir desta pane.** As duas largadas a partir do contexto do servidor
   OpenCode deram `TRAY_ICON_ADD ok=false winerror=5` **e** `WEBVIEW2_INIT_FAILED` (`RPC_E_DISCONNECTED`
   na 1.ª, `E_ACCESSDENIED` na 2.ª): a app sobe **sem painel e sem worker**. Não é sessão (esta shell e
   o Explorer estão os dois na sessão 1, interactiva) e não é disco. A mesma linha de comando lançada
   pelo **Task Scheduler com `/it`** (o contexto do utilizador interactivo) deu uma app **sã**:
   `TRAY_ICON_ADD ok=true winerror=0`, `panel window created`, `WORKER_PRELOAD done started=true`.
   É o mecanismo por trás da regra *"só o LEAD lança"*: **não é cerimónia, é que a app fica avariada se
   for lançada de fora.** (Histórico: 69 `TRAY_ICON_ADD ok=true` e 6 `TRAY_UNAVAILABLE`, das quais 2
   são as minhas.) A instância partida foi morta e o mutex `Local\SottoShell` devolvido; a tarefa
   agendada foi apagada.
2. **A app não arranca com o Windows.** `HKCU\...\Run\Sotto` **não existe** (a chave tem ~20 entradas,
   e o Sotto não é uma delas). O AGENTS afirma que existe. O dono fechou a app às 21:37 de ontem e ela
   não voltou — porque nada a traz de volta.

## O que fica declarado e NÃO foi medido

- O painel aberto (Alt+C) durante uma medição: mudar o Alt+C do dono não é para uma lane.
- O `wpr.exe`/ETW (traço com stack walking) — a ferramenta certa para uma caça profunda, deixada de
  fora por escrever gigabytes em discos quase cheios.
- Se o worker a 104 % de CPU está a transcrever áudio real ou silêncio: a medição de agora apanhou-o a
  meio do treadmill; medir isso exige fixar o dispositivo.
