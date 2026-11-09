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
