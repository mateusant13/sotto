# RECIBO — o relatador que morreu com o cano (dono, 2026-11-08)

## 1. O DEFEITO, medido na instância dele

`pid 42572`, arrancado **04:01:44** (o mesmo processo que respondeu a todas as medições de
stutter desta sessão).

| facto | valor medido | instrumento |
|---|---|---|
| último byte escrito no log | **04:57:13.351** (`YOUTUBE_CDP_HEALTH age=0.02 …`) | `_main/webview-run.log`, 417 875 linhas, mtime `Nov 8 04:57` |
| o processo continua vivo? | **sim** — 52 fios, `status=running` | `psutil` |
| quanto custa? | **100,0 %** de um núcleo; `sotto-caption-tick` **78,5 %** | `_main/shell-thread-cpu.py 42572` |
| o pai do processo? | **nenhum** (`Process.parent()` → `None`) | `psutil` |
| `panel-state.json` e `panel-visibility.json` | mtime **04:57** também | `ls -lt _main/` |

Três horas e meia de app viva, a queimar um núcleo, e **nenhum dos doze instrumentos que leem
esse log tinha um número novo** — porque o log parou. O `log()` faz:

```python
with _LOG_LOCK:
    print(line, flush=True)          # ← sem guarda
    if _LOG_FILE is not None:
        _LOG_QUEUE.put(line)
```

O pai morto deixou o `print` a escrever num cano sem leitor: cada chamada levanta
`OSError: [Errno 22] Invalid argument`. É **a mesma classe** que esta casa já curou do lado do
worker (`_main/emit-pipe-dead` → `BRIDGE_DEATH_CAUSE OSError 22`, 2026-11-04). Do lado da shell
ninguém a tinha curado — e aqui a consequência não é uma excepção, é o **silêncio**: a app continua
a correr, deixa de escrever, e todo instrumento que julga custo/legenda/hotkey responde sobre um
processo que já não fala.

## 2. A CURA (`app/webview/sotto_webview.py`)

`_write_stdout()` — o relator **não levanta** e **não depende de consumidor vivo**:
o cano morto é detectado **uma vez**, o facto vai para o **ficheiro** (o artefacto de aceitação)
como `LOG_STDOUT_DEAD err=… -- o cano do largador morreu; o ficheiro e' o artefacto`, e o `print`
deixa de ser tentado (uma syscall falhada por linha, para sempre, num processo que escreve milhares
de linhas por hora, também é custo). `log()` e `warn()` passam os dois por lá; a fila do ficheiro
tem o seu próprio `try` para que um espelho partido não mate o chamador.

## 3. O ORÁCULO — `_main/log-sink-dead-oracle.py` (6 arms + 3 mutantes)

Executa o `log()`/`warn()` **REAIS** do ficheiro que embarca, contra um `sys.stdout` que levanta.

| arm | o que exige | medido |
|---|---|---|
| A1 | stdout vivo: a linha chega ao stdout **e** à fila do ficheiro | `stdout_tem=True fila=1` |
| A2 | cano morto: `log()` não levanta **e** o ficheiro recebe | `err=None espelho=True` |
| A3 | detecção **uma** tentativa, não uma por linha | `tentativas=1` (duas chamadas) |
| A4 | `LOG_STDOUT_DEAD` com a excepção, **uma** vez | `marcadores=1 outros=2` |
| A5 | `warn()` sobrevive pelo mesmo caminho | `err=None` com `WARN` no espelho |
| A6 | `AttributeError` (o `pythonw` sem stdout) idem | `err=None` |

`--neg-arm` escreve **cópias** do módulo com o `print` directo de volta e exige RED:
medido **`NEG-ARM check=3/3`**, e o mutante `marcador-sem-o-facto` reproduz exactamente o estado
vivo (`err=OSError(22, 'Invalid argument')`, `fila=0`, sem marcador) → **`VERDICT: FAIL (1/6)`**.
Positivo: **`VERDICT: PASS (6/6)`**.

Um defeito de instrumento veio com o oráculo e ficou escrito nele: a cópia mutante vive num tmp
**sem os irmãos** (`hot_reload`, `youtube_window`), logo a árvore real tem de ficar em `sys.path`
e o tmp vai por **append** — `insert(0)` punha a cópia à frente dos irmãos e o import morria.

## 4. O QUE ISTO NÃO PROVA

* **A app dele continua a correr o código de 04:01:44** (sem esta cura). O `log()` morto só se
  cura no próximo arranque; até lá os instrumentos que leem `_main/webview-run.log` estão a
  julgar um processo que não fala — e um deles (`shell-thread-budget`) passou a dizer
  `SKIPPED reason=stale-instance` em vez de um vermelho sobre o passado.
* Não se sabe **porque o pai morreu** às 04:57: fora do alcance desta pane (o processo é `high`,
  `py-spy dump` dá `Acesso negado`). O que se sabe: depois de ele morrer, a app ficou muda — e
  isso é que é o defeito, não a morte do pai.
* O ciclo de vida do fio `sotto-caption-tick` (78,5 %) tem dono noutra faixa: a lei do custo e a
  arm A10 de `_main/caption-tick-thread-oracle.py` (fracção de núcleo 0,27 contra orçamento 0,40).

## 5. BATERIA

Par `log-sink-dead` + `red-as-expected-log-sink-dead` ligado em `_main/_audit-verify-all.cmd`
(2 passos, 4 linhas de `call`), ao lado do par `cdp-target-async` (outra faixa, integrado por mim).
`battery-wiring` medido depois: `ligados=158 sem_passo=110 populacao=268`, o único
`new-unwired` é `paint-cost-oracle.py` (faixa do `PaintCostNuclear`, em curso); `step-line-shape`
PASS; `battery-class` PASS 3/3.
