# STATUS — o registo vivo da especificação

Este ficheiro é a memória do trabalho. É actualizado a cada onda; não é um relatório final.
Cada linha diz o que está **escrito**, com que **evidência**, e o que **falta**.

Última actualização: 2026-11-11 (W0).

## Ondas

| onda | estado | o que fica escrito | evidência |
|---|---|---|---|
| W0 inventário + índice | **feito** | `README.md`, este `STATUS.md`, contagem medida da superfície | `os.walk` medido: 229 ficheiros / 123 560 linhas |
| W1 arquitectura | **feito** (2026-11-11) | `01-ARCHITECTURE.md`: 6 secções — árvore de processos, largada do `run.cmd` (6 passos), 47 nomes de fio, o contrato shell↔worker (ARGV+env, JSONL de 3 tipos, 16 ficheiros de estado), as 5 guardas de processo, e as 3 coisas que a shell NÃO pode fazer ao worker | `run.cmd:236,311,316`; `_spawn`; `_consume`; `main():26084-26105`; `_child_env` |
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
| D-01 | dois mutantes congelados do worker não estavam no git (`.gitignore`: `worker/_sotto_worker_agcinert.py` e `worker/runs/`), e dois oráculos dependem deles (`_main/agc_order_live.py:37`, `_main/verdict-order-oracle.py:71`): num clone limpo esses dois não corriam | ALTA | **corrigido 2026-11-11** — `git ls-files` passa a devolver os dois (`git add -f`), `.gitignore` explica por que, e o `.gitattributes` foi REGENERADO (`python _main/_make-gitattributes.py --write`; `--verify` rc=0) para os prender ao EOL medido (`worker/*.py` e `worker/runs/*.py` = `text eol=crlf`) |

## Números medidos nesta campanha

Guardados aqui porque a próxima sessão não deve re-medir o que já está medido **e o mundo não mudou**.

| o quê | número | como |
|---|---|---|
| linhas do produto | 123 543 em 229 ficheiros | `os.walk` por extensão, excluindo `.git`/`node_modules`/`_legacy`/`models`/`runs`/`_cache` |
| shell | 26 362 linhas, `SottoShell` com 227 membros, 29 classes | `ast` + contagem de `\n` |
| worker | 9 493 linhas, 17 classes | `ast` |
| bateria | 476 passos / 476 com registo | `_main/battery-record-pairing-oracle.py` |
| pin da bateria | 360331 B / 4165 CRLF / 0 bare LF | `agents-md-pins-oracle.py` |
| oráculos ligados | 195 ligados / 108 sem passo / 303 na população | `battery-wiring-oracle.py` |

Re-medido a 2026-11-11 23:1x, depois de a ordem p0 do dono (*"as soon as i open it, should start the
subtitles"*) entrar: a decisão do arranque passou a `SottoShell.caption_wanted_at_start` (pura) e o
par `caption-wanted-default` + o seu negativo entrou na bateria — daí `474 -> 476` passos, `194 ->
195` ligados e o pin novo. Documento de comportamento em `08-PANELS-UX.md` (a escrever) e a regra
operacional em `docs/hotkey-gestos.md` §"A legenda ABRE ligada".
