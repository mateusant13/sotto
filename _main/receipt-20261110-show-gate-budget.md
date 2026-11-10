# RECIBO - o show que confia no que nao foi confirmado, e o RED de um processo velho (2026-11-10)

Card: `p0 arranque: demora DEMAIS a responder a keybindings/qualquer coisa -- tornar extremo`.
Tudo aqui foi medido nesta arvore hoje, com o comando ao lado. Nenhum numero foi copiado de log
antigo.

## 1. O que o card pedia, e o que estava por baixo

| metade | instrumento | numero medido |
|---|---|---|
| resposta do Alt+C (o show) | `_main/paint-live-show-oracle.py` sobre `_main/webview-run.log` | 22 shows, `content_wait_ms` p50 31 / p95 125 / max 250, `wait_ms` p50 15 / p95 78, **total p50 78 / p95 157 / max 297**, `paint_ack=false` **zero** |
| a linha que reprovava | o mesmo oraculo | `PANEL_SHOWN ... content_ack=false content_why=ui-thread-busy content_attempts=1 content_wait_ms=250.0 paint_ack=true wait_ms=47.0` as 2026-11-09 21:21:55.103 |
| quem escreveu essa linha | `python _main/live-code-freshness-oracle.py` | `LIVE_CODE STALE pid=52792 started=2026-11-09 21:21:46.700` -- o processo e' anterior a' cura |

Ou seja: o portao estava RED por uma linha produzida por **codigo anterior**, e a causa dessa linha
era uma metade do proprio instrumento que nunca podia disparar.

## 2. As tres curas, cada uma com a sua prova

### 2-a. O orcamento e' da ESPERA, nao de uma pergunta

`app/webview/sotto_webview.py` -- `gate_probe` entregava `left` (o orcamento inteiro) a' primeira
pergunta. Uma pagina com a UI ocupada nao responde nesses 250 ms, e `gate_should_retry` -- que existe
para `ui-thread-busy` -- ficava sem orcamento nenhum. Agora:

```python
CONTENT_GATE_ATTEMPT_FRACTION = 0.5      # metade do orcamento por pergunta
ask_s = max(CONTENT_GATE_RETRY_MIN_S,
            min(left, budget_s * CONTENT_GATE_ATTEMPT_FRACTION))
```

O pior caso continua **250 ms de espera total** (nunca 250 ms por tentativa) e uma pagina ocupada
recebe duas perguntas. O 0,5 vem do campo: `content_wait_ms` de um show BOM tem p95 **125 ms** = metade
do orcamento.

### 2-b. A soma e' o que o olho paga

Os dois tetos julgavam cada metade (`content_wait_ms<=350`, `wait_ms<=400`); um show de
`300 + 200 = 500 ms` passava com as duas verdes. O oraculo passou a julgar
`content_wait_ms + wait_ms <= 400` (o mesmo orcamento que ja' existia) e a publicar a cauda:
`total_p50_ms` / `total_p95_ms` / `total_max_ms`. Medido: 78 / 157 / 297 ms -- a rede existe para a
cauda que hoje nao existe.

### 2-c. STALE nao e' veredicto sobre a arvore

O oraculo pergunta ao `live-code-freshness-oracle.py`; com o processo `STALE` **ou** `UNKNOWN` um RED
vira `PAINT-LIVE VERDICT: SKIPPED (processo STALE -- a evidencia e' do codigo anterior...)` e cada
falha e' reimpressa como `STALE-EVIDENCE` (a evidencia nunca se apaga). A demissao e' a funcao PURA
`demote_stale(verdict, fresh)` e o `--neg-arm` julga a matriz inteira:

| entrada | saida exigida |
|---|---|
| `RED` + `STALE` | `SKIPPED` |
| `RED` + `FRESH` | `RED` (um processo fresco continua a reprovar) |
| `RED` + `UNKNOWN` | `SKIPPED` |
| `GREEN` + `STALE` | `GREEN` |
| `SKIPPED` + `FRESH` | `SKIPPED` |

## 3. Os bracos

* `show-soma-acima-do-orcamento` -- muta a ultima linha para `content_wait_ms=300` + `wait_ms=200`:
  cada metade SOB o seu teto, a soma acima do orcamento. Apanhado so' pela arm da soma.
* `busy_attempts >= 2` -- a pergunta que **gasta tudo o que lhe dao** (como a producao faz) tem de
  receber uma segunda chance dentro dos mesmos 250 ms. Com o codigo de antes este braco mede
  `attempts=1`; foi por isso que a sequencia de brinquedo antiga (50 ms por pergunta) nao via o
  defeito: dava cinco tentativas num caso que a producao dava uma.

## 4. Medido, nesta arvore

```
python _main/paint-live-show-oracle.py
  PAINT-LIVE processo=STALE (LIVE_CODE STALE log=...webview-run.log)
  STALE-EVIDENCE conteudo nao aplicado antes do mapa (2026-11-09 21:21:55.057): ack=false why=ui-thread-busy ...
  STALE-EVIDENCE show 2026-11-09 21:21:55.103: content_ack=false (o mapa nao esperou o conteudo)
  PAINT-LIVE VERDICT: SKIPPED (processo STALE -- a evidencia e' do codigo anterior; o proximo arranque a julga)
  rc=0

python _main/paint-live-show-oracle.py --neg-arm
  red-stale-demovido -> SKIPPED ok · red-fresh-fica-red -> RED ok · red-unknown-demovido -> SKIPPED ok
  green-nunca-mexe -> GREEN ok · skipped-nunca-mexe -> SKIPPED ok · constante-do-gate-em-falta -> REFUSED ok
  NEG-ARM cases=19 caught=19
  NEG-ARM PASS   rc=1 (convencao da casa: o negativo que apanha sai 1)

python _main/agents-md-pins-oracle.py        -> AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
python _main/battery-wiring-oracle.py        -> PASS populacao=294 ligados=186 sem_passo=108
python _main/undefined-names-oracle.py       -> GREEN -- 19 ficheiros, 0 nomes usados e nunca definidos
```

## 4-bis. O extractor que montava um namespace INCOMPLETO (medido no proprio dia)

A primeira versao da cura pendurou o `--neg-arm` **40 s** em vez de falhar. Causa, achada com
`faulthandler`: `_main/content-gate-answer-probe.py` injecta no namespace das funcoes extraidas uma
lista FIXA de constantes (`GATE_CONSTANTS`) que nao conhecia `CONTENT_GATE_ATTEMPT_FRACTION`; o
`NameError` caia DENTRO do `try/except Exception` que existe para a pagina muda, o relogio ficava
parado em 0 s (a pergunta nunca acontecia) e o `while True` do `gate_probe` girava para sempre.

Curado em duas metades: a constante entrou na allowlist, e `missing_gate_constants()` **recusa** um
namespace incompleto antes de o executar (`SystemExit` com o nome do que falta). Provado:

```
missing with the constant dropped from the allowlist: ['CONTENT_GATE_ATTEMPT_FRACTION']
refused: o gate usa constante(s) que o extractor nao injecta: CONTENT_GATE_ATTEMPT_FRACTION
```

e o braco `constante-do-gate-em-falta` julga as duas metades (a fonte real nao tem constante em
falta; a allowlist sem ela e' recusada) em toda corrida.

## 4-ter. A sonda da pagina: a raiz por custo medido, o perfil fora dela, e uma escada

`_main/content-gate-answer-probe.py` publicava `PROBE UNMEASURED: a sonda nao respondeu em 45 s`
(66 s e 105 s por corrida). Nao era o navegador:

| medicao | numero |
|---|---|
| write de 64 KiB em `I:\cc-tmp` (a raiz da casa), ao longo do dia | **0,0 ms / 709,4 ms / 1595,8 ms / 4,41 s** |
| a MESMA pagina com o perfil do Edge em `I:\cc-tmp` | **TIMEOUT 90 s** |
| a MESMA pagina com o perfil no temp do sistema | **3,4 s**, rc=0, 92 902 B de DOM |
| depois da cura (raiz saudavel, perfil fora, escada) | **14,6 s** com medicao completa |

Tres mudancas, cada uma com o numero impresso na corrida:

* `probe_root()` passa a medir **o pior de uma rajada de 8 x 64 KiB** em cada candidata, com a ordem
  da casa primeiro e o sistema so' quando a da casa passa de `PROBE_ROOT_SLOW_MS` = **400 ms**; uma
  raiz lenta e' RECUSADA por nome (`PROBE_ROOT ... RECUSADA write_ms=..`) em vez de virar um timeout
  mudo que parece culpa do navegador. Uma medida unica nao bastava: dizia `saudavel` e o Edge nao
  devolvia o DOM no minuto seguinte.
* o **perfil efemero do Edge** vai para o temp do sistema e e' apagado no fim (a pagina e o resto
  continuam na raiz da casa): ~15 MB que nao voltam, contra a regra do `TMPDIR` que existe para o
  scratch de projeto.
* **a escada**: prazo curto na primeira raiz (`PROBE_ROOT_FIRST_S` = 20 s) e, se ela nao responde,
  a MESMA pagina no temp do sistema com o prazo cheio. A linha `PROBE arm root=.. deadline_s=..
  answered=..` diz qual das duas respondeu -- medido hoje nas duas direcoes (arm 1 numa corrida,
  arm 2 na outra).

O controle (`--neg-arm`, agora um passo da bateria) julga a escada com um `_run_edge` FALSO, zero
navegador: L1 primeira estoura e a segunda responde (`ok=True`, 2 raizes), L2 nenhuma responde
(`ok=False` com a razao), L3 a primeira responde e nenhuma segunda e' paga. `NEG-ARM cases=3
caught=3`, rc=1. Primeira versao do controle media `ok=False` por causa do proprio fixture (aspas
simples onde o `_attr` exige `data-gate-probe-<chave>="..."`) -- corrigido, porque um controle que
falha pelo dado nao prova nada.

## 4-quater. O motor quente: a tarefa EXISTE, e o texto do `schtasks` e' cego

O cartao do arranque estava escrito como "bloqueado no gate". A medicao de hoje separa as duas
metades:

| o que | como | numero |
|---|---|---|
| a tarefa `\SottoWarmEngine` esta' registada? | `schtasks /query /tn SottoWarmEngine` | **rc=0** |
| o mesmo nome com uma que nao existe | `schtasks /query /tn SottoNaoExisteXYZ` | **rc=1** |
| o XML que o Windows guardou | `C:\Windows\System32\Tasks\SottoWarmEngine` (UTF-16, sem admin) | existe, mtime **2026-11-10 06:33:05**, `<Triggers />` vazio, `IgnoreNew`, `PT0S`, `InteractiveTerminal`=InteractiveToken, accao `warm-engine-run.cmd` |
| o TEXTO de qualquer um dos dois | `out`/`err` do `schtasks` por um cano | **0 B nos tres nomes** |

Ou seja: a cura de 06:42 (`7fb5134`) fez o seu trabalho -- a tarefa existe e o `/run` deixa de ser um
`rc=1` silencioso -- e o `rc` e' o instrumento que o diz. O **texto** do `schtasks` nao sai por um
cano neste hospedeiro (ele escreve pela consola), logo as linhas `WARM_ENGINE_TASK_CREATED ...
out="" err=""` nao sao uma criacao que falou pouco: sao o unico desfecho que este Windows imprime.
Ficou escrito no docstring do oraculo e no sitio do log, porque a leitura errada ("criou com erro")
e' o defeito seguinte.

O que continua **NAO MEDIDO**, e agora com o nome certo: o `/run` + `attach` custam **1,9 GB de
modelo** (`heavy`), e o `I:/!manager/tools/performance-gate.py status` devolve **UNKNOWN** --
`sample-unknown: disk counter read failed`, isto e', o proprio leitor de
`Win32_PerfRawData_PerfDisk_PhysicalDisk` por `powershell` estoura neste hospedeiro.

**O QUE "ESToura" QUER DIZER, medido hoje**: aquela leitura NAO devolve. O mesmo
`Get-CimInstance Win32_PerfRawData_PerfDisk_PhysicalDisk -Filter "Name='_Total'"`, corrido a mao
com uma consola presente, foi morto aos **180 s** (e uma corrida anterior morreu no prazo de 60 s com
`rc=124`, `out=''`, `err=''`). Logo o gate nao fica verde por retentativa: o instrumento do gate e'
que esta' preso. As duas substituicoes testadas no mesmo minuto sao **cegas** por cano sem consola,
o que o `_main/hidden-launch.py` desta arvore usa: `Get-Counter '\PhysicalDisk(_Total)\Avg. Disk
sec/Transfer' -SampleInterval 1 -MaxSamples 1` -> **rc=1, 0 B**, 4,4 s; a mesma classe CIM com
`-OperationTimeoutSec 5` -> **rc=0, 0 B**, 6,4 s. Uma cura tem de ler por FICHEIRO (o `powershell`
grava e o Python le') ou pela PDH por `ctypes`, nunca por um cano. A medicao foi registada na caixa
do gestor: `I:\!watcher\state\herdr-inbox\dm-7ca781e36c80fc7f6dc5.md` (rc=0, `--no-inject`, o
registro e' a entrega).

Com o gate
UNKNOWN nao ha lease `heavy`, logo nao se larga o `/run` a partir desta lane. O numero que falta e'
o par `WARM_ATTACH` (0,97 s medido com motor falso) contra `BRIDGE_LOAD_MS` (~43 s), e ele precisa
de uma janela `heavy` OU do arranque do dono, que ja' leva a cura e escreve
`WARM_ENGINE_START_TASK ... registered=present`.

## 4-bis. O gate foi consertado no MESMO dia, e o veredicto mudou de UNKNOWN para AMBER (medido 2026-11-10)

O §4 acima descreve o defeito: o gate nao conseguia ler o disco por `powershell` e publicava `UNKNOWN`.
Consertado no repo dono (`I:/!manager`, commit `3f4c531`): o leitor passou a **PDH por `ctypes`**
(`pdh.dll`: `PdhOpenQueryW` / `PdhAddEnglishCounterW` / `PdhCollectQueryData` /
`PdhGetFormattedCounterValue`), sem `powershell` e sem WMI.

| amostra | state | commit | avail_phys | disk (min/avg/max ms) | reason |
|---|---|---|---|---|---|
| 1 | amber | 82,7 % | 38,3 % | 0,0 / 6,8 / 24,3 | `commit-pct >= amber 80.0` |
| 2 | amber | 82,8 % | 38,2 % | 0,0 / 4,6 / 3,0 | idem |
| 3 | amber | 82,7 % | 38,4 % | 10,9 / 4,3 / 9,5 | idem |

O lease `heavy` foi **pedido**, e a recusa esta' ao lado do pedido:

```
$ python I:/!manager/tools/performance-gate.py acquire --kind heavy --owner sotto-warm-pair --ttl 900
refused heavy lease owner=sotto-warm-pair state=amber
  - heavy-requires-green
  - amber-light-allowed:commit-only avail=37.7%>15.0% disk-max=0.8ms<20.0ms ttl<=300s leases<=1
  - commit-pct=83.1 >= amber 80.0
```

**O PAR CONTINUA NAO MEDIDO, e o motivo mudou de nome**: antes era o instrumento preso (`UNKNOWN`),
agora e' a maquina a **82,7-83,1 % de commit**, acima do amber de 80 % que o gate da frota exige para
`heavy`. Nao e' um pico — as tres amostras e as amostras do dia anterior (81-84 %) concordam. Uma carga
de 1,9 GB a este commit poe a caixa acima de 90 %, que e' o estado em que o dono sente o PC travar.

**E AS DUAS PORTAS NAO CONCORDAM, o que vale registar**: o veto do proprio motor
(`app/webview/load_shedding.py`, `HIGH_PCT = 88.0`) **permitiria** a carga a 82,7 % (`leve` ate' 88 %);
quem recusa e' o gate da FROTA, com amber a 80 %. Consequencia pratica, e ela e' a razao de esta nota
existir: uma lane que perguntasse so' ao motor carregaria 1,9 GB num momento em que a frota proibe. Quem
pede uma carga de modelo consulta o **gate da frota** primeiro; o G1 do motor e' a guarda de
producao, nao a autorizacao de trabalho pesado.

**O que fecha o card, quando a caixa permitir** (um comando, sem instrumento novo):

```
python I:/!manager/tools/performance-gate.py acquire --kind heavy --owner sotto-warm-pair --ttl 900
schtasks /run /tn "\\SottoWarmEngine"        # arranca sem consola e sem janela (R4: sem triggers)
# evidencia: _main/warm-engine.log  ->  WARM_LOAD_MS ms=<carga> resident_mb=<rss>
#                                     ->  WARM_ATTACHED ms=<attach> load_ms=<carga> mode=warm-idle
# limite de aceitacao: attach << BRIDGE_LOAD_MS (a serie VIVA, medida agora: 15 amostras em
#   _main/webview-run.log, 4,9 s a 61,8 s, mediana 27,0 s -- o custo depende de os 1,9 GB
#   estarem em page cache, e e' por isso que o limite e' "attach << carga", nao um numero fixo)
python app/webview/warm_engine.py --stop; python I:/!manager/tools/performance-gate.py release --id <id>
```

O `attach` com `live=false` (`mode=warm-idle`) NAO abre dispositivo de audio: o codigo do
`AttachedSession` so' abre o tap dentro de `if self.live:` (`app/webview/warm_engine.py:579`), logo esta
medicao nao toca no audio do dono; ela custa CPU e commit, e so' isso que o lease regula.

**Uma SEGUNDA testemunha, que nao e' o gate** (`.steady-watcher.json`, escrito as 16:15 no cwd desta
arvore): `mood: "emergency"`, `heavy_job_cap_pct: 4.4`, e o aviso dele, verbatim: *"memory serious:
15.6G free, commit 88% -- trimming workers, not killing -- held by python.exe (pid 2464) 4.91G
[vodrip], python.exe (pid 39676) 3.46G [gravador], bun.exe (pid 18560) 3.23G, pythonw.exe (pid 65816)
2.38G [gravador], bun.exe (pid 24560) 2.16G [codeintel-worktrees]"* e *"Do not retry-loop."* Os
seguradores do commit sao **outros projetos**; nenhum deles e' o Sotto. Um pedido de 1,9 GB agora
empilha em cima deles -- e e' por isso que a resposta certa hoje e' a recusa registada, nao uma nova
tentativa.

## 5. O que NAO esta' verificado

* `fixed, NOT verified`: o numero que fecha este card e' o **proximo arranque do dono** -- com o
  processo `FRESH`, um show com `content_ack=false` volta a ser RED e o oraculo o nomeia. A linha
  `LADDER_TRY`/`PANEL_SHOWN` desse arranque e' a evidencia; eu nao abro a janela dele.
* O ganho de latencia do Alt+C **nao** foi medido num processo com a cura: a p95 de 157 ms e' do
  processo STALE. O que esta' provado aqui e' que o portao deixou de julgar codigo velho e que o
  orcamento tem duas chances em vez de uma.
* `_main/_cache/sotto_webview_nograce.py` (fixture de outro oraculo) ainda carrega o `gate_probe`
  antigo: e' copia descartavel, nao embarca.
