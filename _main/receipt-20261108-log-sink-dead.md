# RECIBO — o relatador que morreu com o cano (dono, 2026-11-08)

## 1. RETRACÇÃO — a história que eu escrevi primeiro está ERRADA

A primeira versão deste recibo dizia: o log morreu às 04:57:13, a app ficou **três horas** viva e
muda a queimar um núcleo. **Isso não aconteceu.** Eu li a hora **local** do log (04:57) como se
fosse UTC. A hora local desta máquina é UTC−3: o processo estava vivo e a escrever **naquele
instante**, e o ficheiro cresceu até **54 082 341 B** às 05:02:30, quando o dono o fechou
(`SHELL_EXIT rc=0 reason=tray-quit statsPushes=354 statsReplies=3644`, `EXIT_TERMINATE code=0
reason=tray-quit`).

A lição tem nome nesta casa — *"o grep deu ZERO tem prazo de validade; re-correr antes de repetir"* —
e a variante de hoje é pior porque **um número parecia fresco**: o Python daqui dá 05:07 local
quando o UTC é 08:07, e eu comparei um carimbo local com um relógio que julgava ser UTC.

## 1-bis. O DEFEITO QUE FICA DE PÉ (e não depende do incidente)

O que **está** medido na instância (pid 42572, arrancada 04:01:44 local, fechada às 05:02:30):

| facto | valor | instrumento |
|---|---|---|
| custo total da shell | **100,0 %** de um núcleo; depois 101,4 % | `_main/shell-thread-cpu.py 42572` |
| fio mais quente | `sotto-caption-tick` **93,6 %**, depois **78,5 %** | idem, duas amostras |
| fios | 52 | `psutil` |
| pai do processo | **nenhum** (`Process.parent()` → `None`) | `psutil` |

E a classe do `log()`, medida **por leitura do código e por execução do braço negativo**, não por
observação do incidente:

```python
with _LOG_LOCK:
    print(line, flush=True)          # ← sem guarda: um cano morto levanta
    if _LOG_FILE is not None:
        _LOG_QUEUE.put(line)
```
A casa já pagou esta classe **do lado do worker** (`emit` com cano partido → `BRIDGE_DEATH_CAUSE
OSError 22`, passo `emit-pipe-dead`, 2026-11-04). Do lado da shell não havia cura nenhuma, e o custo
de a ter é de duas linhas. **O `OSError 22` nesta instância é UNMEASURED** — e é assim que este
recibo o escreve.

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

* **Nenhum `OSError 22` foi observado na instância viva** — ver §1. O que a cura garante é o
  comportamento sob cano morto, provado por execução do `log()` real contra um `stdout` que
  levanta (A2-A6), não por um incidente.
* **Porque o pai do processo é `None`**: o largador sai por desenho (o shell é o processo que fica);
  não há aqui evidência de cano partido. `py-spy dump` no pid dá `Acesso negado` (o shell corre a
  `high`, esta pane a `medium`), logo a pilha do fio a 93,6 % é **UNMEASURED** — quem a mede é a
  arm A10 do `caption-tick-thread`, que conduz o laço real com o custo real.
* O ciclo de vida do fio `sotto-caption-tick` (78,5 %) tem dono noutra faixa: a lei do custo e a
  arm A10 de `_main/caption-tick-thread-oracle.py` (fracção de núcleo 0,27 contra orçamento 0,40).

## 5. BATERIA

Par `log-sink-dead` + `red-as-expected-log-sink-dead` ligado em `_main/_audit-verify-all.cmd`
(2 passos, 4 linhas de `call`), ao lado do par `cdp-target-async` (outra faixa, integrado por mim).
`battery-wiring` medido depois: `ligados=158 sem_passo=110 populacao=268`, o único
`new-unwired` é `paint-cost-oracle.py` (faixa do `PaintCostNuclear`, em curso); `step-line-shape`
PASS; `battery-class` PASS 3/3.
