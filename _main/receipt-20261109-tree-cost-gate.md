# RECIBO - o custo da ARVORE ganha um portao (2026-11-09, pane wD:p1)

Origem: TRES DMs de stutter do watcher na mesma noite, todas a acusar a mesma arvore e
nenhuma delas com um passo da bateria capaz de a julgar.

| hora | acusacao da DM | o que a DM mediu |
|---|---|---|
| 19:57 | `pythonw.exe(27568)` | cpu 8,2 % da maquina, 3 episodios em 60 min |
| 20:1x | `pythonw.exe(27568)` | 26,6 % da maquina, 3 episodios em 60 min |
| 23:2x | `pythonw.exe(27568)` | 8,7 % da maquina sobre 2 processos, **6 episodios em 60 min**, sinais `interrupt`+`creation`, `creation=45,06/s` |

## 1. O que ja' existia, e por que nao bastava

| instrumento | o que julga | medido 2026-11-09 |
|---|---|---|
| `shell-thread-budget` | a SHELL, 25 % de um nucleo | a shell estava em **0,2 %** de um nucleo numa janela de 60 s |
| `cost-watchdog` | o `WORKER_COST` que o worker **publica** | a parte a falar de si |
| `ort-spin-idle` | o spin-wait do onnxruntime ocioso | 16,1 % -> 0,0 % sem spin (ja' curado) |

Nenhum mede os dois processos **de fora** e nenhum julga a **soma**. O detector dessa
classe continuou a ser o dono a reclamar.

## 2. O actor, medido e NOMEADO (23:3x)

```
$ python -m watcher profile 27568
PROFILE pid=27568 (pythonw.exe) window=8.32s cpu=1.3% of one core = 0.1% of the machine threads_seen=59

$ python -m watcher profile 37112
PROFILE pid=37112 (python.exe) cpu=18.0% of one core = 0.9% of the machine threads_seen=66
         CANNOT-MEASURE -- thread-attribution unavailable: psutil...threads() returned 0 thread ids
         while num_threads() says 66

$ python _main/shell-thread-cpu.py 37112 --seconds 10 --top 8
pid 37112: 66 fios, 10.4 s de janela, 253.4% de um nucleo no total
   77.8%   11616  (sem nome)
   77.2%   42436  session-9-intra-op-0
   52.0%   42592  session-10-intra-op-0
   42.7%   53140  session-8-intra-op-0
calibracao: processo mediu 242.0% no mesmo intervalo -> razao 1.05
```

**253,4 % de um nucleo = 2,5 nucleos = 12,7 % da maquina**, e o actor tem nome: **tres
sessoes ONNX a decodificar ao mesmo tempo**, cada uma com o seu pool `intra-op`, mais o
fio do decode ao vivo.

**file:line:** `worker/engine_switch.py` -- a sessao do lote nasce com o SEU proprio
numero (`REDUX_LIVE_THREADS`, construcao da sessao em `_make_engine(... threads=...)`,
~`:712`), independente do `--threads` que a shell passa ao worker
(`worker/sotto_worker.py`). Duas politicas, um processo: 2+1+1 fios no stream **e**
outros 2 no lote, ao mesmo tempo. Uma janela do lote custa 2,40 s de parede e o chunk do
stream e' 0,56 s de audio, logo nao existe entrelacamento possivel -- ou um cede a vez
inteira, ou os dois queimam nucleo. A cura (orcamento UNICO de ASR) esta' em voo na lane
`EngineSerialization`, que e' dona desses dois ficheiros.

## 3. O que a DM atribui e NAO e' desta arvore

```
$ python -m watcher perf
SAMPLE   cpu=85.3%  commit=65.5%  ram_free=12.9G  dpc=0.83%  irq=1.44%  stall_gap=3ms
CREATION MEASURED  window=10.0s  count=2  rate=20.00/s  window_rate=0.20/s
          parent=mixed [pythonw.exe(53000) 1/2, cargo.exe(23596) 1/2] sustained=0.0s
```

- `creation`: **0,20/s agora** contra 45,06/s no episodio; os creators do episodio que a
  DM lista sao `chrome.exe(25992) x13` (o Chrome do dono, `--remote-debugging-port=9222`),
  `msedge.exe(34848) x10` (`--headless=new`, `H:\!gravador`) e `cargo.exe(23596) x2`.
  Nenhum e' desta arvore.
- `interrupt`: kernel/DEP/DPC da maquina (`dpc=0,83 %`, `irq=1,44 %`), e os `tick.stall`
  do mesmo `perf` caem em `ffmpeg.exe(48832)`, `ffmpeg.exe(46912)`, `chrome.exe`,
  `msedge.exe`, `System (pid 4)`.
- Volume: `pythonw.exe(27568) 0,264 MB/s` contra `ld.exe(16236) 56,253 MB/s [H]`,
  `bun.exe(3780) 36,5 MB/s`, `rg.exe(39304) 21,2 MB/s` -- o disco desta razao e' outra
  lane a compilar.

## 4. O portao novo (o que este recibo entrega)

`_main/tree-cost-oracle.py` + o par na bateria (`tree-cost`, `red-as-expected-tree-cost`).

| propriedade | valor | por que esse |
|---|---|---|
| soma julgada | shell + worker, **% de UM nucleo** | a unidade da casa; 100 % = um nucleo, nao a maquina |
| tecto | **150,0 %** | medido 99-137 % nesta maquina; 150 deixa a folga normal e ainda apanha o degrau das tres sessoes |
| ratchet | **+20 %** sobre `_main/tree-cost-baseline.json` | recusa o crescimento lento que um tecto unico deixaria passar |
| actor | o fio mais quente **COM NOME** | um numero sem actor e' beco |
| identidade | PID carimbado no log (`SHELL_STARTUP_STAGE` + `BRIDGE_SPAWNED`) | o `CommandLine` dos processos do dono vem **VAZIO** (`pythonw.exe(27568) -> ''`): app `high`, pane `medium`; medir por argv dava SKIPPED e o portao seria decorativo |
| sem arvore viva | `VERDICT: SKIPPED` | um passo saltado nao e' um portao que passou |

Medido:

```
$ python _main/tree-cost-oracle.py
measuring pid=27568 pythonw.exe
measuring pid=37112 python.exe
TREE-COST tree=136.6% de um nucleo (tecto 150.0%, baseline -1.0%)
          shell=0.9% worker=135.7% top=session-9-intra-op-0:44.8%
VERDICT: PASS
rc=0

$ python _main/tree-cost-oracle.py --neg-arm
NEG-ARM arm: calm PASS              OK
NEG-ARM arm: episode FAIL           OK
NEG-ARM arm: growth FAIL            OK
NEG-ARM arm: none CANNOT-MEASURE    CANNOT-MEASURE
NEG-ARM: PASS -- 4 readings judged as declared
rc=1
```

O `--neg-arm` muta a **leitura** (leituras sinteticas), nunca o produto: as quatro
leituras cobrem o calmo que passa, o episodio de 530 % (26,6 % de 20 nucleos) que tem de
falhar, o crescimento contra um baseline premido que tem de falhar, e a ausencia dos dois
processos que tem de dar `CANNOT-MEASURE` -- sem esta ultima, um instrumento que devolve
`None` por defeito proprio e' indistinguivel de "nao houve nada".

## 5. Portoes da mesma rodada

| portao | medido |
|---|---|
| `agents-md-pins-oracle.py` | `AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)` (330374 B / 3878 CRLF / sha `BF01F6FA...`) |
| `battery-wiring-oracle.py` | `PASS checks=7 fail=0`, `ligados=175 sem_passo=109 populacao=284` |
| `battery-record-pairing-oracle.py` | `passos: 429 | nomes com registro: 429 | achados: 0` |
| `battery-class-oracle.py` | `PASS -- arms=3 fail=0` |
| `undefined-names-oracle.py` | `GREEN -- 19 ficheiros de producao, 0 nomes usados e nunca definidos` |

## 6. RETRO (passo 5 da DM) e o que ele confirmou

`python scripts/retro-scan.py --home H:/pi-agent --project H:/sotto --days 3` ->
`sessions_scanned=10 owner_turns=142 corrections=29 after_success_claim=3
repeated_instruction_groups=0`. **Zero grupos repetidos**: a friccao NAO e' uma regra
ignorada varias vezes, e' UMA classe que nunca teve portao. Pela regra do proprio retro
(caso 1: existe regra, ela nao e' mecanismo) a resposta correta nao e' prosa nova -- e'
transformar a regra em portao. E' exactamente o que o §4 entrega, e por isso nenhuma
frase foi acrescentada ao `AGENTS.md` alem do pin e da linha do par.

## 7. O "depois" da shell, e a decisao que NAO se toma sem numero

| janela | total da shell | fio mais quente |
|---|---|---|
| episodio da DM (leitura lenta, 33,3 s num `target`) | 16,9 % de um nucleo | `sotto-external-captions` |
| 60 s com a app calma | **0,2 %** | `yt-cdp-source` 0,1 % |
| 8,7 s com a foto CDP VELHA (fallback UIA) | **26,3 %** | **`yt-clock` 13,3 %** |

O `yt-clock` e' o laco de `app/webview/sotto_webview.py:_ensure_clock_sampler` (`:6131`,
thread em `:6177`): ele so' pergunta ao UIA **quando a foto da CDP esta' velha**
(`if hwnd and self._yt_snap_video() is None`), e cada amostra UIA custa 391-1375 ms
(documentado no proprio bloco). Ou seja: os 13,3 % sao o caminho de FALLBACK a funcionar,
e e' exactamente quando a CDP caiu que a legenda depende dele.

**Decisao declarada: a cadencia do `yt-clock` NAO desce.** Afrouxar 0,4 s -> 1,6 s
economizaria o nucleo e pagaria com o erro de extrapolacao do relogio (o erro maximo e'
o passo da amostra), ou seja com a sincronizacao da legenda, na janela em que ela ja'
esta' no caminho alternativo -- a queixa oposta a que este trabalho serve. O que se corta
nesse caminho e' a leitura LENTA (feito, `READ_SLOW_MS`), nao o relogio.

Instrumento que fica para a proxima instancia: a taxa de amostras do `yt-clock` hoje so'
se mede de FORA, por CPU por fio (`_main/shell-thread-cpu.py`, o que esta' tabela acima
usou). Uma linha `YT_CLOCK_RATE samples= misses= ms_avg=` no proprio laco daria a taxa
sem instrumento externo; ela nao entra agora porque o codigo novo so' corre num arranque
do dono e um contador que ninguem le e' a doenca que esta casa ja' pagou (instrumento
sem chamador).

## 8. O que NAO esta' medido

- O "depois" da cura das tres sessoes: a lane `EngineSerialization` esta' a medir o custo
  da janela do parakeet antes de editar. `UNMEASURED` ate' ela largar o orcamento unico.
- A app do dono nao foi reiniciada por esta pane (`--no-self-relaunch` esta' posto): o
  codigo novo do laco de leitura so' entra num arranque dele. `fixed, NOT verified`.
