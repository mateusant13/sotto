# STATUS — o registo vivo da especificação

Este ficheiro é a memória do trabalho. É actualizado a cada onda; não é um relatório final.
Cada linha diz o que está **escrito**, com que **evidência**, e o que **falta**.

Última actualização: 2026-11-11 (W0).

## Ondas

| onda | estado | o que fica escrito | evidência |
|---|---|---|---|
| W0 inventário + índice | **feito** | `README.md`, este `STATUS.md`, contagem medida da superfície | `os.walk` medido: 229 ficheiros / 123 560 linhas |
| W1 arquitectura | em curso | processos, fios, IPC, stores, posse | `run.cmd`, `sotto_webview.main`, `WorkerBridge` |
| W2 arranque | — | | |
| W3 captura | — | | |
| W4 motores | — | | |
| W5 caminho ao vivo | — | | |
| W6 YouTube | — | | |
| W7 histórico e estado | — | | |
| W8 painéis e UX | — | | |
| W9 modos de falha | — | | |
| W10 ledger de defeitos | — | | |
| W11 spec-alvo | — | | |
| W12 selo | — | | |

## Defeitos já confirmados (detalhe em `10-DEFECTS.md`)

| id | uma linha | gravidade | estado |
|---|---|---|---|
| D-01 | dois mutantes congelados do worker não estão no git, e dois oráculos dependem deles: num clone limpo esses oráculos não correm | ALTA | confirmado `[MEASURED]` (`git ls-files`), correcção pendente |

## Números medidos nesta campanha

Guardados aqui porque a próxima sessão não deve re-medir o que já está medido **e o mundo não mudou**.

| o quê | número | como |
|---|---|---|
| linhas do produto | 123 560 em 229 ficheiros | `os.walk` por extensão, sem `models/`/`runs/`/`_legacy` |
| shell | 26 273 linhas, `SottoShell` com 227 membros, 29 classes | `ast` |
| worker | 9 493 linhas, 17 classes | `ast` |
| bateria | 474 passos / 474 com registo | `_main/battery-record-pairing-oracle.py` |
| pin da bateria | 358768 B / 4150 CRLF / 0 bare LF | `agents-md-pins-oracle.py` |
| oráculos ligados | 194 ligados / 108 sem passo / 302 na população | `battery-wiring-oracle.py` |
