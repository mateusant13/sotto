# RECIBO — o worker que queima CPU sem produzir linha (2026-11-09)

Tudo abaixo foi medido nesta arvore hoje, com o comando ao lado. Onde nao houve
medicao, a linha diz `UNMEASURED`.

## 1. O que aconteceu — e a CORRECCAO da premissa, medida 40 min depois

| # | a medicao | o instrumento | o numero |
|---|---|---|---|
| 1 | o worker do dono, amostra unica | watcher (`I:/!watcher`), ao vivo | `worker/sotto_worker.py` **pid 20676**, 232 min de vida, **270,6 %c** numa janela, `rows=0` no `YOUTUBE_TICK_MS`, **6 176 s** de CPU acumulada |
| 2 | o mesmo codigo, arranque novo, amostra unica | watcher, apos o painel respawnar | **1,2 %c** — fator **240** |
| 3 | o custo que o processo publica de dentro | `WORKER_STATS private_mb` no log da morte | `private_mb=3401.2`, `rss_mb=873.0` |
| 4 | o que o produto via antes desta cura | `grep -c WORKER_COST` sobre a arvore | **0** — nenhuma serie, nenhuma data |
| 5 | recargas pagas pelo respawn | `BRIDGE_LOAD_MS` (quatro, em oito horas) | 5 500 / 23 547 / 28 125 / 57 875 ms |
| 6 | **A FORMA da serie do MESMO codigo, 12 amostras de 5 s** | `psutil.cpu_times` sobre o pid 14712, 2026-11-09 ~16:3x | **73 113 87 1 1 0 65 99 209 1 1 0** %c — mediana **33**, media **54**, pico **209**, e a media desde o arranque (464 s de CPU em 1 476 s) = **31,5 %c** |

**A PREMISSA DAS LINHAS 1–2 ESTAVA ERRADA, e a linha 6 e' a correcao.** Uma janela
unica de 6 s pode cair inteira dentro de um passe de lote (os mesmos 6 s medidos aqui
deram **307,4 %c**) e chamar de "degradacao" o que e' o motor de lote a fazer o
trabalho: o worker alterna rajadas de 1–2 nucleos com ociosidade, e o pid morto tinha
**1 768 legendas** e `REDUX_BATCH_KICK kicks=142` no `stderr_tail` da propria morte —
ou seja, **produzia**. E o `rows=0` que o watcher leu e' o do **`YOUTUBE_TICK_MS`**
(linhas do PLAYER), nao o do worker: duas unidades diferentes com o mesmo nome.

O que sobra e' o que este trabalho de facto entrega: **o produto nao tinha serie
nenhuma** (`grep -c WORKER_COST` = 0), por isso a unica leitura possivel era uma
janela solta — e ela mentiu duas vezes, uma a favor do "esta' degradado", outra a favor
do "o kill curou". Com `WORKER_COST` + `BRIDGE_WORKER_COST` a mesma pergunta tem uma
serie por minuto com `rows`, `rows_per_min` e `cpu_s_per_row`.


## 2. O que foi implementado (quatro pecas, uma por metade do problema)

| peca | ficheiro | o que faz |
|---|---|---|
| a forma da linha | `worker/sotto_worker.py` — `format_worker_cost()` (modulo) + `cost_line()` (no laco) | publica `WORKER_COST tag=.. cpu_s=.. cpu_pct_avg=.. rows=.. rows_since_tick=.. rows_per_min=.. cpu_s_per_row=.. uptime_s=.. pid=..` a cada tick de stats; `cpu_s` e' `time.process_time()` do PROPRIO processo |
| o parser | `app/webview/sotto_webview.py` — `parse_worker_cost()` | campos ficam strings; campo ausente NAO vira zero; `WORKER_STATS` nao e' custo |
| o transporte | `_pump` -> `WorkerBridge.on_cost` -> `SottoShell.on_worker_cost` | a linha chega ao handler pelas DUAS construcoes da ponte (fria e quente) |
| a decisao | `app/webview/cost_watchdog.py` — `plan()` PURA | `restart` quando `cpu_pct_avg >= 60` **e** `rows_since_tick == 0` por `STALL_TICKS=18` ticks (3 min), com piso de 600 s entre reinicios e tecto de 3/hora; o reinicio usa `revive_worker('cost-watchdog')`, o caminho que ja' existe e ja' tem oraculo |

Numeros que justificam os limiares, todos medidos nesta casa: worker ocioso e
saudavel **0,4–1,2 %c**; worker transcrevendo **100–150 %c** (com `rows>0`, logo
nao conta); worker degradado **270,6 %c com zero linha**. 60 %c e' 50x o repouso
e 4,5x abaixo do defeito.

**`rows_since_tick`, e nao `rows`**, porque o que interessa e' se ESTE tick produziu
linha — um worker com 1 768 linhas feitas e nenhuma nova esta' tao mudo como o que nunca
comecou. (Foi o caso do pid 20676, e mesmo assim o vigia NAO o teria reiniciado: ele
produzia, em rajadas — ver a correcao da §1.)

## 3. O instrumento que julga

```
python _main/cost-watchdog-oracle.py            -> VERDICT: PASS (32/32 arms), rc=0
python _main/cost-watchdog-oracle.py --neg-arm  -> NEG-ARM: PASS (10/10), rc=1
```

32 arms em cinco familias: **A** a forma que o worker imprime e a CHAMADA no laco do
tap (8), **B** o parser e a fiacao estatica da shell (8), **C** a decisao pura (10),
**D** a FIACAO — o handler REAL da shell, extraido do fonte que embarca e conduzido com
o relogio controlado (6). As arms D
existem porque a classe de defeito desta casa e' a cura que ninguem chama: D2
exige o `revive_worker('cost-watchdog')` a sair UMA vez da serie medida, D3 exige a
linha `WORKER_COST_RESTART` com o numero que a justificou, D4 exige UMA linha por
minuto (nao por tick), D5 exige que um `revive` que levanta vire linha
`WORKER_COST_RESTART_FAILED` em vez de derrubar o pump.

Os dez mutantes, cada um derrubando a SUA arm: limiar a 0 (C3), limiar a 1e9 (C1),
delta ignorado (C5), piso removido (C7), forma sem `rows_since_tick` (A2/A3),
handler sem `revive_worker` (D2), handler journalizando a cada tick (D4), o laco SEM
chamar a linha (A7), a ponte quente sem o `on_cost` (B6) e a RECUSA do `revive_worker`
tratada como reinicio (D6) — as tres ultimas existem porque "a cura que ninguem chama"
— ou que age quando o alvo se recusou — e' a classe medida nesta casa mais vezes do que
qualquer outra.

**A recusa e' do `revive_worker`, nao minha**: ele devolve `False` quando o player esta'
a fornecer a legenda (`_external_parked`, medido 2026-10-20) ou quando ja' ha' um revive
em voo. Antes de o carimbar, o handler pergunta o RESULTADO e so' entao journaliza —
`accepted=false` na linha, e o piso/tecto NAO sao gastos numa recusa. Arm D6 e o mutante
M10 (recusa ignorada) cobrem exactamente isso.

## 4. O commit de 2,7 GB do worker: a resposta a DM do governador

O governador viu `sotto_worker.py` pid 14712 com **2 897 MB de commit privado e
50 MB de RSS** e perguntou se a reserva era devida ou morta. Medido, tres pontos:

1. **E' DEVIDA** — e' a arena do modelo. Serie do proprio processo
   (`BRIDGE_RSS` no log, hoje): `13:00:10 rss=8.9 priv=2754.0 blocks=0` ·
   `13:01:10 rss=10.1 priv=2753.9 blocks=0` · `13:02:10 rss=45.5 priv=2762.7 blocks=45` ·
   `13:04:10 rss=47.4 priv=2762.7 blocks=45` · `13:06:11 rss=35.0 priv=2762.7 blocks=81`.
   Plano em 7 min (+8,8 MB), e o pid anterior em plena carga publicou **3 401,2 MB**.
   O RSS baixo e' working set PODADO de um processo ocioso, nao uma reserva vazia.
   Isto ja' estava escrito no codigo desde 2026-11-04 (`worker/engine_switch.py`,
   `current_private_mb`: working set 13,6 MB / commit 3 828 MB).
2. **NAO E' MORTA** — o estado observado ("no consumer") e' o PARQUE: 13:00:06,
   16 s depois da carga, `STATUS_APPLIED text="tap-engine-parked"` e o tap nao abre
   dispositivo com o painel fechado. Preco de libertar: 5,5–57,9 s de recarga
   (quatro `BRIDGE_LOAD_MS` medidos hoje) e as legendas ja' feitas a espera.
3. **TECTO E VIDA, declarados**: **2,75–3,40 GB de commit privado** enquanto o modelo
   esta' carregado; a vida e' a do processo; o derrube e' o exit (2,8 GB, nao os 17 GB
   do precedente de 2026-11-07).

Contexto que o alarme pede antes de apontar um pid: commit da caixa **70,2 GB de
95,6 GB (73,4 %)**, RAM 36,2/47,7 GB, **563 processos com 57,3 GB** de commit somado
(`Get-Process PagedMemorySize64`). O worker do Sotto sao 2 763 MB = **4,8 %** do
total; os dois maiores sao `pythonw` 56872 (3 062 MB) e `python` 61116 (3 007 MB), e
os `bun.exe` somam ~7,9 GB.

## 5. O QUE NAO ESTA' VERIFICADO

* **Nenhum worker real foi reiniciado por este vigia ainda**, e depois da correcao da
  §1 o caso que ele cobre — CPU >= 60 %c e ZERO linha por 3 min — **nao foi observado
  nenhuma vez** nesta maquina. O vigia e' rede de seguranca, nao cura de um defeito
  medido; a serie que o julgaria so' existe a partir do proximo arranque.
  `UNMEASURED`.
* **A ponte QUENTE nao transporta o custo**: em `WarmPipeBridge` o worker e' outro
  processo e o stderr dele nao passa por este pump. O vigia e' do caminho FRIO, que
  e' o que a instancia do dono usa (`BRIDGE_SPAWNED` no log). Declarado, nao fingido.
* `_main/console-window-audit.py` esta' **RED com 6 sitios**, e nenhum deles foi
  tocado por esta rodada (`git status` vazio para os seis ficheiros) — defeito
  anterior a este trabalho, registado aqui para nao ser confundido com ele.

## 6. Ficheiros tocados

`worker/sotto_worker.py` (+49 linhas), `app/webview/sotto_webview.py` (+104),
`app/webview/cost_watchdog.py` (novo, 113 linhas), `_main/cost-watchdog-oracle.py`
(novo), `_main/code-health-baseline.json` (as duas entradas re-medidas com o
instrumento do proprio oraculo), `_main/_audit-verify-all.cmd` + `AGENTS.md` (o par
de passos e o pin, no mesmo commit).

## 7. O WATCHER PEDIU O DENOMINADOR (2026-11-09, dm-d0720f6fd08e4209c957)

A DM mediu `317,1 %c` no worker 14712 com um fluxo vivo e perguntou quatro coisas
"medidas, nao argumentadas". As quatro respostas, com o comando de cada uma.

### 7.1 `intra_op`/`inter_op` na criacao da sessao — a hipotese da DM esta' REFUTADA

Comando: importar o worker e chamar o MESMO construtor que a criacao usa
(`worker/sotto_worker.py:4269 session_options`), sem abrir dispositivo nenhum.

```
OMP_NUM_THREADS no processo depois do import = 4
OMP_WAIT_POLICY = PASSIVE | CUDA_MODULE_LOADING = LAZY
effective_threads(None) = (4, 'default')
   -> encoder intra=4  decoder intra=1  joint intra=1  inter_op=1 por sessao
   -> total de fios intra = 6
```

O `argv` do worker vivo (`BRIDGE_SPAWNED pid=14712 argv=[python, -u,
sotto_worker.py]`) **nao leva `--threads`**, logo a fonte e' `default` = 4. O pool
do ORT **nao** esta' na largura da maquina (a DM deduziu isso dos 66 fios): sao
**6** fios intra + 3 inter. O lote (parakeet ONNX) acrescenta `intra_op=2`.

Onde estao os 67 fios entao: `py-spy dump --pid 14712` devolve **err 5 (acesso
negado, exige elevacao a partir deste assento)** — nomes de fio sao `CANNOT-MEASURE`
aqui. O que se mede sem elevacao: 67 fios vivos, **0,3 %c em repouso** (6 s), io zero.

### 7.2 o %c por chunk: a linha agora traz o denominador

`WORKER_COST` ganhou `chunks_since_tick`, `ms_per_chunk`, `audio_s_since_tick` e
`rtf`, calculados como DELTAS do tick (a mesma forma de `rows_since_tick`), com
`ms_per_chunk=none` quando o tick nao fechou chunk nenhum — zero seria uma mentira
aritmetica. A shell passou a relatar a linha INTEIRA
(`ENGINE_VISIBLE_TAGS += 'WORKER_COST'`) e o `BRIDGE_WORKER_COST` carrega os quatro.

Medido: `_main/cost-watchdog-oracle.py` **34/34** (`--neg-arm` 10/10 apanhados).

**A LINHA NAO PODE APARECER NO LOG DE HOJE, e isso e' medicao, nao desculpa:** a
shell viva (pid 50452) arrancou as **08:14:02**, e tanto o relay do plano de fios
(commit 12:23) como todo o encanamento de custo (13:17) sao posteriores. Um processo
Python nao le codigo novo; o worker 14712 (12:58:50) tambem precede o commit de
custo. `UNMEASURED` ate' o dono reiniciar a shell — `--no-self-relaunch` esta' posto
e nenhuma lane poe a app na tela dele.

### 7.3 o tecto, com o que existe hoje

| grandeza | valor medido | instrumento |
|---|---|---|
| um fluxo vivo, repouso entre lotes | **0,3 %c**, io **0,00 MB/s**, 67 fios | `psutil` 6 s no pid 14712 |
| o MESMO pid, janela de **154 s** a 1 Hz | p50 **0,0 %c** · p90 **4,6** · p99 **394,1** · max **415,6**; fios **65..67**; RSS **201 MB** | `psutil` 154 s, `I:/cc-tmp/worker-window.json` |
| RSS / commit privado agora | **424 MB / 4608 MB** | `psutil` |
| media de vida do worker anterior (13920 s) | **270,6 %c**, 6176 s de CPU | `WORKER_COST` no log |
| passe de lote, medido pelo proprio worker | 15,0 s de audio em **3,64 s** de parede (5 janelas) | `REDUX_ENGINE_DONE` |
| custo do fio do stream depois da cura 12->6 | **49,8 ms/chunk** | recibo anterior |

Leitura: o pico de 317 %c **nao e'** um pool largo a rodar um fluxo; e' o **motor de
lote** (parakeet, 3,64 s por 15 s de audio) a correr EM CIMA do stream. Duas
engrenagens, um processo. A janela de 154 s diz a FORMA da curva, e ela e' bimodal:
**~90 % dos segundos a zero** e rajadas de 4 nucleos — uma media ao longo da vida
(270,6 %c) descreve uma maquina que nunca existiu; o que existe e' o lote a bater.

### 7.4 dois workers ao mesmo tempo?

Dentro da app: **nao**, e esta' medido nas duas pontas — `start_worker` recusa com
`cause=already-running` e `revive_worker` para antes de arrancar. No log:
`BRIDGE_EXIT pid=20676 rc=15` as 12:58:48.670 e `BRIDGE_SPAWNED pid=14712` as
12:58:50.683 — **1,8 s** entre a morte e o nascimento, zero sobreposicao.

Fora da app: **nada impede**. O `worker/sotto_worker.py` nao tem mutex nem ficheiro
de trava (`grep -n "CreateMutex|mutex|SINGLETON" worker/sotto_worker.py` = 0), por
isso uma lane ou um script que o largue directamente cria um segundo worker — foi o
que a minha propria sonda fez hoje. O que existe e' um portao do LARGADOR, nao do
processo.

## 7.5 OS 36 FIOS DO STREAM NAO TEM BOTAO (medido 2026-11-09, resposta a dm-dcf7fdb3659187751249)

O watcher corrigiu a minha medida (`p50 6 %c`, `p99 634 %c`, 15 de 90 amostras acima de
300 %c) e perguntou de onde vem os ~60 fios que nao sao o ORT. A resposta tem nome, e
muda o alvo da cura.

### O CENSO, lido do proprio Windows

`GetThreadDescription` sobre os tids do pid 14712 (toolhelp, sem elevacao) devolve os nomes
que o ONNX Runtime da' aos fios de cada sessao. Agrupado:

| grupo | fios | o que e' |
|---|---|---|
| `session-2/3/68` | 9 cada (**27**) | `og.Model` do nemotron -- `intra_op=10` por sessao |
| `session-1` | 12 | encoder do stream (`intra=4` -> 3) + sessoes que partilham `SessionOptions` |
| `session-4..7, 12..15` | 1 cada (8) | decoder/joint e as quatro sessoes do parakeet (`intra=2` -> 1) |
| `(sem nome)` | 19 | python main, WASAPI, `redux-batch`, `sotto-frontend`, canos |

Mapeamento do ORT medido na mesma maquina (sessao sobre `preprocessor.onnx`, contando fios
nomeados): **`intra=4` -> 3**, **`intra=1` -> 0**, **default -> 13**. Um grupo de 9 fios e'
portanto `intra_op=10` -- a largura da maquina (20 logicos / 2), nao um orcamento.

### O `og.Model` e' o dono, e nao aceita o numero

Num processo limpo, com `OMP_NUM_THREADS=4`:

```
og.Model(dir)                                             -> +36 fios (3 sessoes x 9), load 3,8 s
Config.set_provider_option('cpu','intraOpNumThreads','4')  -> 36 fios        IGNORADO
genai_config.json + model.session_options/intra_op_num_threads -> ficheiro RECUSADO
```

Consequencia para a cura 12->6: `session_options()` governa as TRES sessoes de ORT do
nemotron e **nao toca** no motor que faz o stream. O pico de 6 nucleos e' o genai a correr
com 10 fios por sessao; o lote (`REDUX_ENGINE_DONE audio_s=15.0 windows=5 wall_s=3.64`)
soma por cima, mas nao e' o dono do pico.

### O que foi construido

`worker/sotto_worker.py`: `genai_thread_ids()`, `cpu_mask()`, `cap_genai_threads()` -- chamado
logo depois de `og.Model` + `create_streaming_processor()`. Publica
`WORKER_GENAI_THREADS threads=N pinned=M cpus=...` em TODO arranque (com aperto ou sem ele) e
aplica `SOTTO_GENAI_CPUS` (`4-9`, `0,1,2`) como afinidade, mais `BELOW_NORMAL` nos fios. Sem a
variavel nada muda: um aperto nao medido no stream do dono seria a adivinha que esta casa
proibe. `ENGINE_VISIBLE_TAGS` da shell carrega a tag.

O lever e' de DENTRO do processo por medicao: `OpenThread(SET_INFORMATION)` num processo
alheio devolve **err=5** neste assento; o dono do processo abre os seus proprios fios.

### Medido e nao-medido, sem enfeite

* `_main/cost-watchdog-oracle.py` **37/37** (A11 `cpu_mask` le faixas e recusa lixo; A12 a
  linha sai mesmo sem aperto; A13 o relay na shell lido por **AST** -- a primeira versao
  cortava no parentese de um comentario e publicava AUSENTE sobre um tag que estava la') e
  `--neg-arm` **10/10**.
* Worker reiniciado pelo ARTEFACTO (`cmdline` contem `sotto_worker.py`, 14712 -> 56316 em
  **1,8 s**). Repouso, 60 s: **p50 0,0 %c, p99 3,1, max 3,1**, 63 fios, RSS 1728 MB.
* **As linhas novas NAO aparecem no log, e a razao e' medida**: a shell viva (pid 50452)
  arrancou as **08:14:02**; o relay de `WORKER_THREAD_PLAN` e' de 12:23 e o encanamento de
  custo de 13:17-16:44. Um processo Python nao le codigo novo. Restart do worker nao basta
  (o relay e' da shell) e a shell so' entra num arranque novo pela mao do dono
  (`--no-self-relaunch`). `UNMEASURED` ate' la -- e e' a razao pela qual nao existe um p99
  "depois" honesto neste recibo.

## 8. O VIGIA DE CUSTO NUNCA DECIDIU NADA: `self.log` nao existe no `SottoShell` (2026-11-10)

Medido no log vivo do dono (`_main/webview-run.log`, pid 52792, 21:23:06.046):

```
BRIDGE_COST_CALLBACK_FAILED error=AttributeError("'SottoShell' object has no attribute 'log'")
```

`on_worker_cost` chamava `self.log(...)` em tres sitios, e o `SottoShell` **nao tem** esse
metodo (o `log` desta arvore e' de MODULO). As consequencias encadeiam-se:

1. o primeiro `WORKER_COST` levantava **antes** de `if not verdict['restart']: return`;
2. o `on_cost` do `WorkerBridge` engolia a excepcao (por desenho: um raise ali derrubaria o
   canal de stderr e com ele o heartbeat do cao de guarda) e escrevia a linha acima;
3. logo o vigia que existe para reiniciar um worker caro e mudo **nunca decidiu reiniciar**, e
   a serie `BRIDGE_WORKER_COST` que ele publica nunca apareceu uma unica vez.

Cura: os tres sitios passam a `log(...)` (o de modulo).

**A causa de o oraculo nao o ter apanhado e' o proprio instrumento**, e essa tambem foi
corrigida: o `ShellStub` do `_main/cost-watchdog-oracle.py` fornecia um metodo `log` que o
`SottoShell` nao tem -- o handler extraido corria contra um dublê mais generoso do que a
producao. Agora o stub **nao tem** `log`; o `log` de modulo e' injectado no namespace do handler
e trocado pelo coletor em `drive()`. Duas arms novas:

| arm | o que exige | medido |
|---|---|---|
| D7 | o handler REAL conduzido sobre um stub que so' tem o que o `SottoShell` tem: nao levanta e publica `BRIDGE_WORKER_COST` | PASS |
| D8 | a serie conduzida (saudavel, caro, revive-a-levantar, recusa) nao levanta nenhuma volta | PASS |

E o mutante novo **M11** (voltar a `self.log`) tem de cair na D7:

```
$ python _main/cost-watchdog-oracle.py           -> VERDICT: arms=39 pass=39 fail=0
$ python _main/cost-watchdog-oracle.py --neg-arm -> NEG-ARM: PASS -- 11/11 mutantes apanhados
   M11 o handler volta a chamar self.log        RED em D7   caught
```

Uma correccao de instrumento veio junto: o `drive()` deixou de deixar a excepcao matar o
oraculo (o M11 derrubava o processo com `AttributeError` em vez de reprovar a arm); a excepcao
fica REGISTADA no stub e quem possui o "nao levanta" e' a D7.

`fixed, NOT verified`: o proximo arranque dele e' que diria `BRIDGE_WORKER_COST` no log.
