# RECIBO - a terceira DM de stutter do mesmo oraculo, e o tecto que so' existia em prosa

DM: `dm-0b536b4b7d2187e5b20f` (watcher, `2026-11-15T21:14:31Z`), `target=wD:p1` (project sotto).
Dono, verbatim: *"acabou de acontecer stutter. culpa de quem?"* -- a ordem que faz a DM ser
automatica. Nada aqui foi copiado de log velho: cada numero abaixo foi medido nesta sessao.

## 1. A ATRIBUICAO, POR EVIDENCIA E NAO POR SUSPEITA

A DM acusa `python.exe(36448)`, e a arvore ja' nao existe quando ela e' escrita
(`OpenProcess -> err=87`). Sao meus: `cwd = H:\sotto`,
`cmdline = python _main/parakeet-ultra-oracle.py --engine redux`.

| facto | valor medido | instrumento |
|---|---|---|
| pid nasceu | `2026-11-15T21:13:35.333Z` | `create_time` do proprio evento do watcher |
| pid morto | `2026-11-15T21:14:31.268Z` | `status/events.jsonl` `kind=extreme_kill_dm` |
| valor no tick que disparou | `15.157 % da maquina`, limite `8.0` | o mesmo evento (`threshold`, `unit`) |
| a cura ja' estava no disco? | **NAO** -- commit `72c7cc7` e' de `21:22:38Z` | `git log -1 --format=%cI` |
| sobreviveu `1 processo(s)`? | `TERMINATED` (1 de 1) | `evidence` da DM |

**Conclusao:** a arvore morta correu o codigo de ANTES da cura, por **7 min 47 s**. Nao e' uma
regressao da cura: e' o ultimo episodio da classe que a cura fecha. O que a cura NAO fechava
esta' em §3.

Onde estavam os fios, e por que o `--cpu 40` nao segurava nada (medido no commit anterior):

- esta maquina tem **20 nucleos logicos / 14 fisicos**;
- `jobs.set_cpu_rate` documenta `10000 = 100% of the machine`, logo `--cpu 40` = 40 % da MAQUINA
  = ~8 nucleos;
- o ORT, sem `threads=` no construtor, abre `intra_op_num_threads` = **nucleos FISICOS** (14)
  por sessao, e o oraculo abre 3 engines em fila;
- a linha que MATA e' `stutter_relief_tree_min_pct = 8.0` (`% of machine`), ou seja o `--cpu 40`
  ficava **5x acima da linha que mata** -- o cage nao era uma protecao, era uma autorizacao.

## 2. O QUE JA' ESTAVA CURADO (commit `72c7cc7`, e continua)

`_main/parakeet-ultra-oracle.py:78` `ORACLE_THREADS = 2`, e o numero vai ao CONSTRUTOR de cada
backend (`worker/redux_live.py:328` -> `reference.OnnxParakeet(..., threads=...)`,
`worker/models/parakeet-redux-onnx-int4/transcribe.py:209` `options.intra_op_num_threads`).
Medido no commit: auto = 398 % de um nucleo (87,64 s cpu / 22,0 s wall); 2 fios = 159 %
(65,28 / 41,0); 2 fios sob `--cpu 6 --io very-low` = **5,56 % da maquina** (64,72 / 58,2). WER
identico nos tres (0,1154).

## 3. O BURACO QUE ESTA DM EXPOS -- e a cura deste turno

O tecto (`--cpu 6`) vivia **so' no docstring do ficheiro**. O processo nao tinha como saber se
aquela largada tinha acontecido, e o unico jeito de descobrir era o watcher matar a arvore. Um
numero que o proprio processo nao consegue ler e' uma promessa, nao um tecto.

`_main/parakeet-ultra-oracle.py:81` `read_cpu_cap_pct()` le o Job Object **de dentro do
processo**, sem handle: `QueryInformationJobObject(NULL, 15, ...)`. MEDIDO nesta maquina:

| condicao | `ControlFlags` | `CpuRate` | a funcao devolve |
|---|---|---|---|
| sem cage | `0` | `0` | `None` |
| sob `--cpu 6` | `5` (`ENABLE|HARD_CAP`) | `600` | `6.0` |

E `main()` (`:491`) imprime a linha em toda invocacao:

```
# CEILING cpu 6.00% of machine (Job Object hard cap, read from inside this process)
# CEILING none -- UNCAGED: no Job Object CPU cap; the watcher ends a tree of this project at 8% of machine (line: `stutter_relief_tree_min_pct`)
```

Um instrumento que nao sabe dizer que NAO esta' limitado nao e' um instrumento: as duas linhas
acima sao o controle que faltava, e a segunda nomeia a linha que mata.

## 4. PROVA, NO MESMO COMANDO, OS DOIS BRACOS

```
python _main/parakeet-ultra-oracle.py --neg-arm
  # ORACLE_THREADS applied=2 requested=2 (source=flag)
  # CEILING none -- UNCAGED: ... 8% of machine ...
  NEG-ARM GREEN -- 0 caso(s) divergentes     rc=1  (convencao: 1 = apanhou)

PYTHONPATH=I:\!watcher python -m watcher run --cpu 6 --io very-low -- \
    python _main/parakeet-ultra-oracle.py --neg-arm
  job CPU hard cap 6%  (children inherit)
  io priority VeryLow (readback=0) — the tree loses the disk QUEUE, never the disk
  # ORACLE_THREADS applied=2 requested=2 (source=flag)
  # CEILING cpu 6.00% of machine (Job Object hard cap, read from inside this process)
  NEG-ARM GREEN -- 0 caso(s) divergentes
```

O `rc=1` do negativo e' a convencao da casa (`:expectred` + a frase `NEG-ARM GREEN`, declarado em
`_main/_audit-verify-all.cmd:2336`): responder 0 faria o passo vermelho a passar.

## 5. A DEPENDENCIA DE CACHE QUE ESTE FICHEIRO TINHA ERRADA (achada no mesmo turno)

`_main/_audit-verify-all.cmd` declarava o passo `parakeet-ultra` com
`app\worker\redux_live.py` -- um caminho que **nao existe** nesta arvore -- e sem
`worker\redux_live.py`, que e' o ficheiro que o motor `redux` (o default do oraculo) carrega.
Medido: `test -f app/worker/redux_live.py` -> nao; `worker/redux_live.py` -> sim. Editar o
backend deixava o passo **em cache a reimprimir um PASS sobre outro codigo** -- a classe do
`panel-deps`. Corrigido: as deps nomeiam `worker\redux_live.py` e o `transcribe.py` do export.
Medido depois: `401272 B`, **4606 CRLF**, 0 bare LF, sha256
`D94035DE9D06F97132F59710B9CB9C1C2A59C4D4925B0251FB36918AB7149A7E`; `AGENTS-PINS PASS`.

## 6. ESTADO DA MAQUINA NA MEDICAO (a metade "depois" do par que a DM exige)

```
python -m watcher perf
SAMPLE   cpu=61.4%  commit=66.3%  ram_free=13.4G  dpc=0.45%  irq=1.42%  disk_lat=0.6ms  stall_gap=3ms
H: q_avg=0.12 busy=11.7% lat=0.65ms   I: q_avg=0.11 busy=11.0% lat=0.80ms
python -m watcher perf gate -> GREEN (commit-pct 65.8 < 80, ram 28.1 % > 15, disk-lat 7.2ms < 20)
```

Nenhuma arvore `parakeet-ultra-oracle` viva nesse instante. O `python.exe(72212)` a
`41.035 MB/s` do censo **nao** e' este instrumento (sem `--engine`, sem `cwd H:\sotto`).

## 7. O QUE NAO ESTA' MEDIDO

- O episodio de stutter que a DM reporta e' **anterior** a esta sessao e a arvore dele esta'
  morta: o "antes" e' o numero do watcher (`15.157 % of machine`), nao uma medicao minha.

## 8. O PAR ANTES/DEPOIS, NA MESMA CORRIDA REAL (`--engine redux`)

Largada: `PYTHONPATH=I:\!watcher python -m watcher run --cpu 6 --io very-low -- python
_main/parakeet-ultra-oracle.py --engine redux`. Medido agora, nesta sessao:

```
# CEILING cpu 6.00% of machine (Job Object hard cap, read from inside this process)
VERDICT redux -- WER=0.1154 (2 subs/1 ins/0 del em 26 palavras), RTF=1.0391, carga=7.04s,
         RSS=2317 MB
child exit code 0 — total 127.9s (startup 0.3s, wait 125.6s, wrapper cpu 0.83s, child cpu 66.27s)
```

| | antes (a arvore que a DM matou) | depois (esta corrida) |
|---|---|---|
| CPU no tick | `15.157 % of machine` | `2.59 % of machine` |
| CPU em nucleos | ~3,0 de 20 | 51,8 % de UM nucleo (66,27 s / 127,9 s) |
| linha que mata | `8.0 %` -- **1,9x ACIMA** | `8.0 %` -- **3,1x ABAIXO** |
| tecto legivel pelo processo | nenhum (so' prosa no docstring) | `cpu 6.00 % of machine` |
| IO | nao limitado | `VeryLow (readback=0)` |
| trabalho concluido | morto no meio | **completou, rc=0**, WER identico (0,1154) |

A ultima linha e' a que importa para a ordem do dono (*"otimizar, nunca parar"*): o trabalho
**andou** e ficou 3,1x abaixo da linha que mata. Nao foi um throttle que o fez parar -- foi o
orcamento de fios na origem mais o `--cpu 6` que cabe debaixo da linha.

## 9. O QUE NAO ESTA' MEDIDO (segunda metade)
- A corrida que resta foi a do passo `heavy` completo (`--engine all`, que inclui os dois braços
  ultra e carrega 2,4 GB a mais). O que esta' medido e' o motor `redux`, que e' o default do
  oraculo e o unico que a DM acusou. O passo `heavy` continua opt-in (`SOTTO_BATTERY_HEAVY=1`).
- Nenhuma prova foi feita na TELA do dono: `verified` exige uma corrida real da app e continua
  fora do alcance desta lane.
