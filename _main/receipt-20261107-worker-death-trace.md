# RECIBO - a morte do worker passa a ser diagnosticavel (2026-11-07)

Tudo aqui foi medido nesta arvore, hoje. Os comandos estao citados; os numeros saem deles.

## 0. O que obrigou este trabalho

DM do watcher `dm-b3018cc79ce290cc8fe1` (ordem do dono: *"acabou de acontecer stutter. culpa de
quem? é pra sempre verificar o maior culpado do stutter, e mandar dm automaticamente"*), com
`culprit = pythonw.exe(23244)`, `cpu 8.4% of machine over 8 process(es) of the tree`,
`interrupt=12%`, `creation=9.083/s`.

A resposta a essa DM exigiu medir o que a arvore gasta. O resultado:

| facto | numero | instrumento |
|---|---|---|
| mortes do worker hoje | **6** | `BRIDGE_DEATH rc=1 deaths=6` em `_main\webview-run.log` |
| frase das seis | `Worker error at unhandled - OSError: [Errno 22] Invalid argument` | idem, campo `last=` |
| recargas compradas por elas | **11703 / 27015 / 33860 / 37157 ms** | idem, `BRIDGE_LOAD_MS` |
| traceback guardado | **nenhum** -- 2 linhas de stderr por morte, as da carga (`REDUX_ENGINE_YIELD`, `REDUX_ENGINE_RELEASED`) | `stderr_tail=` da mesma linha |

Seis mortes, a mesma frase, zero causas. O `contract_guard` **ja'** apanhava a excepcao -- o que
faltava era o relator e o sitio onde a frase ficava.

## 1. As duas causas, as duas curadas

**(1) O RELATOR LEVANTAVA.** `contract_guard` chamava `err_fn("sotto: UNHANDLED ...")`, que e' o
`err()` de `worker/engine_switch.py:98` e faz `sys.stderr.write(...)`. Com o handle do stderr
invalido esse `write` faz `EINVAL` **dentro** do `except`, e a saida 4 (com significado) virava uma
saida **1** sem frase -- exactamente o `rc=1` que o log mostra seis vezes. Curado nos dois sitios:

* `worker/engine_switch.py` -- `err()` nunca levanta (`except (OSError, ValueError, AttributeError)`).
* `worker/sotto_worker.py` -- `emit_fn` e `err_fn` dentro de `try/except BaseException`, para
  nenhum relator poder transformar uma morte explicada numa morte muda.

**(2) A FRASE IA SO' PARA O CANAL QUE FALHA.** `stderr` e' o mesmo canal cujo handle invalida. A
frase passou a ir tambem para um **ficheiro**: `_main\webview-worker-tracebacks.log`, com bloco
carimbado (`=== data pid= ===`), tecto (`TRACEBACK_LOG_MAX = 256 KiB`) e reciclagem para metade --
o tecto nao e' decorativo, esta maquina tem pressao de disco medida. `SOTTO_WORKER_TRACEBACK_LOG`
desvia o ficheiro (o oraculo usa um temporario; uma maquina apertada pode mandar para outro volume
sem tocar em codigo).

## 2. A prova

`_main\worker-death-trace-oracle.py` -- **12 arms** contra o codigo real (`import sotto_worker` +
`import engine_switch`, 0,06 s), e o negativo:

```
VERDICT: PASS -- 12/12 arm(s)                          rc=0
NEG-ARM: PASS -- 3/3 mutantes apanhados                rc=1
```

| arm | o que exige |
|---|---|
| A1 / A1b | excepcao em `main` -> **4**, e o painel recebe a frase (`stage=unhandled`) |
| A2 / A2b | o ficheiro nomeia a excepcao **e** traz a frame (`Traceback (most recent call last)`, `boom`) |
| A3 | `emit_fn` morto (cano partido) -> **4** |
| A4 | `err_fn` morto (`EINVAL`) -> **4** -- o defeito medido |
| A5 | `engine_switch.err()` num stderr invalido nao levanta |
| A6 / A6b | 1,6 MB despejados -> ficheiro <= 256 KiB, e o bloco **novo** sobrevive a reciclagem |
| A7 / A8 | `KeyboardInterrupt` -> 130; `SystemExit(2)` atravessa (o codigo de uso nao e' achatado) |
| A9 | `main` limpo -> 0 e **nada** escrito |

Mutantes do `--neg-arm`, cada um numa **copia** (`worker/` inteiro copiado para um temporario,
so' um ficheiro mutado): M1 tira a chamada que guarda o ficheiro, M2 tira o `try/except` do
relator, M3 repoe o `write` cru do `err()`. 3/3 CAUGHT.

**SMOKE NUM PROCESSO REAL** (nao so' import): um subprocesso com **stdout E stderr fechados**
(`subprocess.DEVNULL` nos dois) a correr `contract_guard(boom)` com `OSError(22)`:

```
rc do processo = 4
ficheiro existe = True B = 450
nomeia a excepcao = True   tem frame = True
OSError: [Errno 22] Invalid argument
```

Antes desta cura esse processo saia **1** e nao deixava nada.

## 3. A bateria

Dois passos, declarados `always` (correm em ~1,2 s e leem dois ficheiros de codigo):

```
call :step worker-death-trace 0 "...;worker\sotto_worker.py;worker\engine_switch.py" ... python _main\worker-death-trace-oracle.py
call :step red-as-expected-worker-death-trace 1 "..." ... python _main\worker-death-trace-oracle.py --neg-arm
call :expectred red-as-expected-worker-death-trace !STEP_RC! "..." "NEG-ARM: PASS"
```

**PIN medido** (`_main\_audit-verify-all.cmd`): **274820 B**, **3341 CRLF** / 0 bare LF,
sha256 `67A43AB9E9340B132585AA6D4368A7FDFA8777B646ABC94E8ACD2443F118A65F`; AGENTS.md actualizado
e `agents-md-pins-oracle.py` PASS (2 pins, 0 falhas). Portoes corridos nesta rodada:
`battery-wiring` PASS (ligados=148, sem_passo=109, populacao=257), `battery-class` PASS (3 arms),
`undefined-names` GREEN (19 ficheiros, 0 nomes por definir).

`code-health`: o crescimento **declarado** e' `worker/engine_switch.py` (+1018 B, +21 linhas,
+1 `except_pass`) e `worker/sotto_worker.py` (+2588 B, +58 linhas, +2 `defs`, +3 `except_pass`);
as duas entradas do baseline foram actualizadas **cirurgicamente** (nao por `--update`, que
regenera a tabela inteira e lavaria o crescimento das outras lanes que estao no working tree).
Veredicto depois: `CODE-HEALTH VERDICT PASS`, `--neg-arm` 3/3.

## 4. O QUE NAO ESTA' MEDIDO (e nao se afirma)

* **A causa RAIZ do `OSError [Errno 22]` nao esta' identificada.** O que esta' feito e' a
  instrumentacao que a nomeia: a proxima morte deixa o traceback completo em
  `_main\webview-worker-tracebacks.log`. As duas linhas de contexto antes de cada morte sao
  `REDUX_ENGINE_YIELD reason=shed level=muito-alta` e `REDUX_ENGINE_RELEASED
  reason=shed-muito-alta`, ou seja o caminho de **load-shedding** e' o suspeito nomeado, nao o
  culpado provado.
* **O CPU da instancia viva (pid 23244) continua no codigo anterior.** A cura do spin do timer
  (`6ce772a`) e esta so' entram numa instancia nova; o restart e' do dono (a app nao se
  auto-relanca: arrancou com `--no-self-relaunch`). `interrupt=12 %` desse pid e' o passado, nao
  o presente do codigo.
* As **6 mortes de hoje nao voltaram a acontecer** depois da cura neste working tree, mas a
  instancia viva nao corre este codigo -- nao ha' "antes/depois" na mesma instancia, e esse numero
  fica UNMEASURED de proposito.
