# RECIBO - o lote carrega o motor uma vez, e o cage devolve o rc que mediu

Tudo o que aqui esta' escrito foi medido nesta arvore, nesta sessao. Onde o numero tem comando, o
comando esta' ao lado. O que nao foi medido diz `UNMEASURED`.

## 1. O lote: um filho por LOTE, nao por bloco

**O defeito.** `BatchQueue.step()` largava um filho do driver por BLOCO, e cada filho carregava o
motor do zero. Uma fila de N blocos comprava N cargas de modelo para transcrever N trechos que
cabiam numa carga.

**A cura, em `app/webview/batch_queue.py`:**
- `MAX_BLOCKS_PER_CHILD = 8` (`batch_queue.py:134`) -- o lote e' limitado por um numero declarado,
  nao pelo que estiver na fila.
- `next_entries` (`batch_queue.py:321`) reclama ate' 8 blocos `queued` de uma vez, com uma unica
  escrita de manifesto por bloco reclamado.
- `command_for(entries)` (`batch_queue.py:746`) leva TODOS os payloads num `--transcribe` com
  `nargs='+'` (`batch_queue.py:1222`).
- `_settle_batch` (`batch_queue.py:872`) casa o resultado por `id`: o driver emite um resultado por
  `id` e o fallback (driver velho, texto unico) so' se aplica a um lote de UMA entrada -- atribuir um
  texto unico a 8 blocos seria duplicar uma frase em 8 linhas, que e' corrupcao, nao fallback.
- `load_engine` (`batch_queue.py:1109`) carrega o motor uma vez por lote e aceita `--threads`.
- O `step()` foi DECOMPOSTO (`_wait_batch`, `_settle_batch`, `_requeue_all`): medido no ratchet,
  `max_func` de 109 -> 72 linhas.

**Portoes, corridos nesta sessao:**

| comando | veredicto |
|---|---|
| `python _main/batch-queue-drain-oracle.py` | `VERDICT: PASS (6/6 arms)` -- inclui `Green spawns=1` com 8 blocos reclamados |
| `python _main/batch-queue-drain-oracle.py --neg-arm` | `NEG-ARM: PASS` (3 mutantes, cada um pela SUA arm) |
| `python _main/batch-executor-ceiling-oracle.py` | `VERDICT: PASS (19/19)` |
| `python _main/batch-executor-ceiling-oracle.py --neg-arm` | `NEG-ARM taxa_medida=0.416 orcamento=0.120 APANHADO`, `NEG-ARM: PASS` |

O oraculo do tecto mede a taxa de SERVICO do laco (o que a casa chama "um laco dorme o ORCAMENTO,
nunca o proprio trabalho") contra `BATCH_CPU_BUDGET`, e o braco negativo prova que a medicao nao e'
decorativa: com o orcamento apagado da linha, a mesma medicao da' `0.416` e o mutante cai.

**A atribuicao do DM do watcher.** O DM acusou `python.exe(53836)` e a linha de comando dele era
`batch_queue.py --transcribe` -- essa linha e' do lote DESTA arvore, logo a atribuicao esta' certa e o
pedido era "o custo por bloco". Populacao no log vivo dele (`_main/webview-run.log`, 25 439 116 B,
fechado 2026-11-11 22:57): **2** `BATCH_EXEC_DONE`, **8** `BATCH_EXEC_YIELDED`, **2** ids distintos --
ou seja o defeito e' ESTRUTURAL (1 carga de motor por bloco), nao volume de fila; e' por isso que ele
se mede no oracle e nao no log.

**UNMEASURED:** quanto tempo REAL de transcricao o lote poupa na maquina do dono. O que esta' medido e'
a contagem de largadas e a taxa de servico; uma corrida de audio real nao foi feita nesta sessao.

## 2. O contrato no spec

`docs/spec/07-HISTORY-STATE.md` §9.3 ("Uma carga do motor por LOTE, nao por bloco") declara o
invariante com citacao `[CODE]` de cada linha. `_main/spec-citations-oracle.py`:
`SPEC-CITATIONS: docs=16 citacoes=1452 sem_ficheiro=0 fora_de_alcance=0 index_ausente=0
fora_da_tabela=0` -> `PASS`.

## 3. O cage da bateria devolvia o rc de ANTES de correr

**O defeito, medido.** A corrida de 2026-11-12 05:0x terminou com
`BATTERY-VERDICT: RED - 2 step(s) failed` e `child exit code 1` -- e chegou ao largador como
**`rc=0`**. O `.cmd` imprime o veredicto certo e mente na unica coisa que o chamador le, que e'
exactamente o que o `AGENTS.md` proibe ("o exit code E o veredicto").

**A causa.** `%ERRORLEVEL%` dentro de um bloco entre parenteses e' expandido quando o bloco e' LIDO,
ou seja ANTES de o `python -m watcher run` correr: o `exit /b %ERRORLEVEL%` do bloco devolvia o codigo
de ANTES do cage.

**A cura.** Subrotina `:__battery_cage` (`_main/_audit-verify-all.cmd:4318`) chamada por
`call :__battery_cage` (linha 112) -- uma etiqueta `call` volta a ler cada linha, logo o `exit /b` da
subrotina le' o codigo REAL -- mais `if defined SOTTO_BATTERY_CAGED if errorlevel 1 exit /b 1`
(linha 113), que nao depende de expansao nenhuma. Sem `!` na etiqueta: a expansao atrasada continua
DESLIGADA acima dela, que e' o que mantem o `I:\!watcher` literal (a armadilha que o proprio ficheiro
documenta).

**Controlo de DOIS bracos, o mesmo filho a sair 1:**
`_main/_cache/cage-rc-old.cmd` (a forma antiga) -> **rc 0**;
`_main/_cache/cage-rc-new.cmd` (a forma curada) -> **rc 1**.
Os dois ficheiros estao na cache, byte a byte, e o `python -c "import sys;sys.exit(1)"` e' o filho dos
dois -- nenhum dos bracos toca em audio, ecra ou modelo.

## 4. `panel-hidden-at-startup-oracle`: o texto, nao o cano fechado

`proc.stdout` depois de `communicate()` esta' FECHADO, e um `TextIOWrapper` nao tem `.splitlines()`:
medido nesta corrida, `AttributeError` na linha 1209 -- o passo morria em vez de julgar o mutante.
Agora le' o texto que o `communicate()` devolveu. `python _main/panel-hidden-at-startup-oracle.py`
-> `ORACLE GREEN failures=0`, `VERDICT: PASS` (54,26 s, medido hoje com a maquina quieta).

## 5. O ratchet

`code-health` acusou `app/webview/batch_queue.py` por bytes/linhas/defs (crescimento REAL do lote:
o reclamar em bloco, o parser por id e o carregador do motor) e por `max_func`, que a decomposicao
devolveu a 72. O crescimento restante e' absorvido com `--update` **depois** do commit do ficheiro
(`--skip-dirty` recusa fixar um estado que o commit nao reproduz -- a regra do pin que descreve o
commit).

## 6. O que NAO esta' verificado

- A bateria completa nao foi re-corrida depois destas mudancas; a ultima corrida completa e' a de
  05:0x (RED: 2 passos, os dois re-medidos verdes isoladamente nesta sessao --
  `panel-hidden-at-startup-oracle` 54,26 s PASS e `skip-verdict-guard` `GREEN - 521 step log(s)`).
- O rc do `.cmd` corrigido foi provado nos dois bracos de fixture; a corrida REAL que o exercita e' a
  proxima, e ela tem de mostrar rc igual ao `BATTERY-VERDICT`.
