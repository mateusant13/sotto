# Recibo — os travamentos de ABRIR e de FECHAR o Sotto (2026-10-21)

O dono, pela vigésima vez, verbatim:

> *"entendo por que a bateria trava e da stutter. é por que o start do que quer
> que seja, da stutter no meu computador. eu, de novo, pela vigesima vez, vou
> mandar tu resolver os travamentos que acontecem quando fechamos o sotto ou
> abrimos o sotto"*

E, o que o próprio repo já guardava do mesmo pedido (2026-10-20, verbatim, no
código, `app/webview/sotto_webview.py`):

> *"abrir ou fechar o sotto, principalemnte fechar, trava pra caralho meu pc.
> arruma."*

Este recibo diz **o que foi medido**, **o que mudou**, **o que NÃO mudou** e
**o que continua aberto**. Nenhum número daqui é de memória: cada um tem o
instrumento e o ficheiro de onde saiu.

---

## 1. AS QUATRO CAUSAS MEDIDAS

### 1.1 O ABERTURA: o painel ficava morto 36,9 s

O painel abria e o worker nascia **nesse momento** (`WORKER_PANEL_START
source=show-side`), pelo que o modelo só ficava pronto depois:

```
2026-10-21 17:12:19.322 sotto: WORKER_PANEL_START source=show-side reason=default
2026-10-21 17:12:56.289 sotto: BRIDGE_LOAD_MS ms=36968 pid=52660 worker_load_s=32.59
```

**37 segundos de painel aberto sem uma legenda**, e a máquina ocupada esse
tempo todo (o load é do tamanho que o dono sente).

### 1.2 O ABERTURA: o Alt+C podia esperar DEZ SEGUNDOS

`transparency_hack` (o que torna o painel transparente) chamava
`ui(form_show)` — `_ui` tem um orçamento por omissão de **DEZ SEGUNDOS**
(`UI_MARSHAL_TIMEOUT_S = 10.0`) — e quem chama é a **thread do hotkey**, a
thread do ÚNICO controlo do dono. Uma thread de UI ocupada transformava o
Alt+C numa espera de 10 s.

### 1.3 O FECHO: três segundos de thread do tray gelada

`request_exit` fazia `closer.join(3)` à espera de um `destroy` que é
**cosmético** (o `os._exit` logo a seguir mata a janela de qualquer maneira).

### 1.4 O FECHO (o mais grave): um worker ÓRFÃO depois da app fechar

`os._exit` **não mata o filho**. Um worker nascido depois da decisão de
fechar sobrevive à app, carrega 1,2 GB de modelo e corre a escada de
dispositivos de áudio numa máquina cuja app já closed. Isto não é uma teoria:
é o log do próprio dono (2026-10-20):

```
20:50:25.229  BRIDGE_LOAD_MS ms=67969 pid=47804 worker_load_s=8.75
```

68 s de máquina ocupada — e o guard que impede isto existia **num só** dos
caminhos de spawn (`on_external_captions_released`). Os outros (o painel a
abrir, o *resume* de VRAM, o *revive*) ainda podiam competir com a saída.

---

## 2. O QUE MUDOU (com a medição do antes e do depois)

| # | mudança | ficheiro | medição |
|---|---|---|---|
| A | **O PRELOAD**: o worker nasce 20 s depois do arranque da app, em background, na prioridade BELOW_NORMAL do worker — o modelo está pronto **antes** de o dono pedir. `SOTTO_NO_PRELOAD=1` volta ao comportamento antigo. | `app/webview/sotto_webview.py` (`_schedule_preload_worker`, `_preload_worker`, `WORKER_PRELOAD_DELAY_S`, `START_REASONS += 'preload'`) | **antes**: painel morto 36,9 s. **depois**: `WORKER_PRELOAD scheduled delay_s=20.0` (18:08:26.059) → `BRIDGE_SPAWNED` (18:08:46.072, exactamente 20,0 s) → `BRIDGE_LOAD_MS ms=10657 worker_load_s=8.87` (18:08:56.718). **O modelo pronto 30 s depois do arranque, sem o dono tocar em nada.** |
| B | **A ESPERA DO `show` É LIMITADA** (0,25 s) **E TEM POST** como alternativa: se a thread de UI estiver ocupada, o hack é publicado em vez de esperado. | `app/webview/sotto_webview.py` (`TRANSPARENCY_HACK_WAIT_S`, `transparency_hack`) | medido no ar: `HOTKEY_DOUBLE panel=strip after_ms=700` (18:11:20.607) → `PANEL_SHOWN` (18:11:20.608) — **o show inteiro custa 1 ms**. |
| C | **A SAÍDA NÃO GELA A THREAD DO TRAY**: `closer.join(QUIT_DESTROY_WAIT_S)` (0,25 s) em vez de 3 s. | `app/webview/sotto_webview.py` (`QUIT_DESTROY_WAIT_S`) | medido: `BRIDGE_STOP` → `SHELL_CLOSING` = **0,010 s**; `SHELL_CLOSING` → `SHELL_EXIT` = **0,252 s**; total **0,262 s**; o processo morreu ~0,15 s depois do `SHELL_EXIT`. |
| D | **O GUARDA ANTI-ÓRFÃO É CENTRAL**: `start_worker` recusa quando a shell está a morrer. Um worker é filho da shell: se a shell está a morrer, não nasce nenhum filho. | `app/webview/sotto_webview.py` (`start_worker`) | medido: o probe de saída com worker vivo → o worker 53444 morreu com a app, **zero órfãos** (o único `sotto_worker.py` vivo era o da app do dono, pid 34832). |
| E | **O ARENA DO GPU NÃO COME O CARTÃO**: as opções do EP CUDA viajam com os nomes do provider (`arena_extend_strategy=kSameAsRequested`, `gpu_mem_limit` = 4096 MB por omissão). | `worker/sotto_worker.py` (`cuda_provider_options`, `provider_entries`) | ver §3: isto é uma **guarda**, não umaclaims de velocidade. |
| F | **AS FASES DO LOAD SÃO MEDIDAS** (`load_phases_s`): quem quiser saber onde vão os segundos já não tem de adivinhar. | `worker/sotto_worker.py` | medido: encoder 1,56-1,62 s, decoder 0,10-0,31 s, joint 0,07-0,16 s ⇒ **as sessões do ONNX são 1,74-2,09 s**, não o load todo. |

Instrumentos novos (nenhum lança a app do dono):

* `_main/open-close-stall-oracle.py` — **o portão**: julga **ficheiros**
  (5 factos, todos **estruturais/AST**, nunca por substring: a primeira
  versão era por substring e os seus próprios mutantes voltaram INERT).
  `--neg-arm` = 5 mutantes, **5/5 apanhados**, rc=1 por desenho.
* `_main/_cuda-vram-footprint-probe.py` — a VRAM e o tempo de load, com a
  ordem controlada (`--order forward|reverse`).
* `_main/_exit-latency-probe.py` — a saída ao milésimo (handle do processo),
  com verificação de órfão.

---

## 3. O QUE A MEDIÇÃO **REFUTOU** (e o que por isso NÃO é uma claim)

### 3.1 "O worker come 9,7 GB de VRAM" — **NÃO REPRODUZIDO**

O número estava escrito no código (`app/webview/sotto_webview.py`, o guard de
VRAM). Medido agora, com o `nvidia-smi` a amostrar o **dispositivo**:

```
arm options : gpu_peak 4344 MiB   gpu_delta 1207 MiB
arm defaults: gpu_peak 4788 MiB   gpu_delta 1703 MiB
```

**1175-1703 MiB**, não 9,7 GB. A figura de 9,7 GB é de outra configuração (ou
está errada) e **não é usada como justificação** de nada neste recibo. A
opção `gpu_mem_limit` fica como **guarda** (o arena não pode comer o cartão),
não como velocidade.

### 3.2 "As opções do EP CUDA fazem o load 3× mais rápido" — **FALSO**

O primeiro A/B deu 49,21 s (defaults) vs 15,02 s (options) e pareceu um
triunfo. **Repetido com a ordem invertida, o resultado trocou de lado**
(options 11,43 s / defaults 7,89 s): o primeiro braço de uma sequência paga a
cache fria e o drivers do GPU, e o efeito de ordem é maior do que o efeito das
opções. Com as fases medidas:

```
run 1 (HEURISTIC ) load_s=6.55  encoder=1.561 decoder=0.105 joint=0.072  sessions=1.738
run 2 (EXHAUSTIVE) load_s=6.98  encoder=1.581 decoder=0.143 joint=0.100  sessions=1.824
run 3 (HEURISTIC ) load_s=10.59 encoder=1.621 decoder=0.314 joint=0.158  sessions=2.092
```

**1,738 s vs 1,824 s — dentro do ruído.** Portanto:

* `cudnn_conv_algo_search` **fica no default do ORT** (EXHAUSTIVE): não há
  ganho medido, e trocá-lo trocaria uma velocidade de inferência que ninguém
  mediu por um tempo de load que ninguém vê. Fica no ambiente para a
  pergunta continuar respondível.
* `arena_extend_strategy=kSameAsRequested` e `gpu_mem_limit` ficam como
  **guardas** (o default arredonda cada alocação para a potência de dois
  seguinte e o limite é ilimitado), **sem claim de velocidade**.

### 3.3 "O disco é o custo do load" — **FALSO**

Os 747 MB do modelo leem-se a **1,9 GB/s ⇒ 0,39 s**. O load não é disco.

### 3.4 "O `closer.join(3)` era a causa do travamento de fechar" — **parcial**

O join de 3 s era um travamento **real** (o dono, 3 s sem resposta ao fechar),
mas **não** era a causa principal: a causa principal do fecho era o **órfão**
(§1.4), que carregava 1,2 GB e corria a escada de áudio **depois** da app
fechar. As duas coisas estão corrigidas.

---

## 4. O QUE CONTINUA ABERTO (com o número, não com a intuição)

1. **O load do modelo varia com a máquina: 4,1 s a 49,2 s.** As sessões são
   1,74-2,09 s; o resto é `og.Model` + o processador + a contenção. Num PC
   ocupado o load foi de 32,59 s (log do dono) e de 49,21 s (aqui). **O
   preload tira o load do momento em que o dono está a olhar** — não o torna
   mais rápido.
2. **A escada de dispositivos de áudio continua a ser um contributor**: o log
   vivo mostra `device-open-refused` e `device-rotated` em ciclo, e o
   `BRIDGE_LOAD_MS ms=67969` de 2026-10-20 é 68 s de spawn **dos quais ~59 s
   são a escada** (`TAP_OPEN_TIMEOUT_S=4.0`, `TAP_REOPEN_MIN_S=5.0`, e o
   headset Bluetooth do dono). **Não tocado neste recibo.**
3. **O `peak` do áudio está a 0.0** no worker vivo (`BRIDGE_STATS_PUSH
   payload={"peak":0.0}`): o worker está vivo mas não está a capturar. É
   Knights-and-knaves com o Routing (o loopback do dono), **não** com a
   latência, e **não** foi tocado aqui.
4. **A máquina do dono está em estado degradado**: I: com **0,4 % livre**
   (13,8 GB de 3726 GB), D: 2,1 %, E: 2,3 %, e **722 processos** vivos. O
   "o start do que quer que seja dá stutter" tem uma componente de MÁQUINA
   que o Sotto não controla. **Isto é um aviso, não uma acção: o dono
   decide o que limpar.**
5. **O Red/Parakeet lifecycle (ordem n.º 3)** continua por fazer — o recibo
   `_main/receipt-20261021-parakeet-lifecycle.md` está por executar.

---

## 5. COMO SE VERIFICA (sem confiar neste texto)

```
py -3 _main/open-close-stall-oracle.py            # rc 0, 5/5 factos
py -3 _main/open-close-stall-oracle.py --neg-arm  # rc 1 = PASS por desenho
py -3 _main/_cuda-vram-footprint-probe.py --arm both --order reverse
py -3 _main/_exit-latency-probe.py --with-worker --hold 30
```

O portão **julga ficheiros** ⇒ entra na bateria. Os dois probes **lançam
processos** ⇒ ficam **fora** da bateria, e é dito no `AGENTS.md`.
