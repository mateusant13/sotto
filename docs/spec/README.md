# SOTTO — A ESPECIFICAÇÃO DO COMPORTAMENTO

Este directorio responde a uma pergunta só: **o que é que o Sotto faz?** Não "o que devia fazer",
não "o que foi prometido" — o que o código em `HEAD` faz, em que ordem, com que números, e onde é
que isso se parte.

Existe porque o dono, verbatim, pediu: *"your goal is done when you can turn into WORDS all
behavior of sotto. and how all connects with ux and usage. put into words the before and after."*

## Como ler

| ficheiro | responde |
|---|---|
| `00-PROMISE.md` | a promessa ao utilizador, as jornadas reais, o que conta como "funciona" |
| `01-ARCHITECTURE.md` | quantos processos, quantos fios, quem fala com quem, quem é dono do quê |
| `02-BOOT.md` | do duplo-clique ao primeiro pixel: estados, prazos, o que falha e como |
| `03-CAPTURE.md` | de onde vem o áudio: escada de dispositivos, tap por processo, silêncio |
| `04-ENGINES.md` | os dois motores, o motor quente, a VRAM, o shedding por carga |
| `05-LIVE-PATH.md` | do bloco de áudio ao pixel: parciais, rota, pintura, orçamentos |
| `06-YOUTUBE.md` | a fonte externa, o relógio do player, a troca de vídeo, as línguas |
| `07-HISTORY-STATE.md` | tudo o que fica escrito em disco: histórico, ajustes, journals |
| `08-PANELS-UX.md` | Alt+C, Ctrl+Space, painéis, temas, arrasto, o que ele vê |
| `09-FAILURE-MODES.md` | o que acontece quando cada peça falha, e o que o dono vê |
| `10-DEFECTS.md` | o registo de defeitos: desenho de base, antes/depois, evidência, gravidade |
| `11-TARGET.md` | o comportamento final que EU escolho, jornada a jornada |
| `12-GLOSSARY.md` | cada tag do log, cada ficheiro de estado, cada termo |
| `13-MODULES.md` | **um bloco por ficheiro de produto**: o que garante, quem o chama, o que escreve, o que o utilizador vê quando falha (o catálogo que responde pela população) |
| `STATUS.md` | o registo vivo: o que já está escrito, o que falta, o que foi medido |

## Os três graus de evidência (usados em todos os ficheiros)

Uma frase neste directorio diz sempre de onde vem. Sem etiqueta, é prosa — e prosa não conta.

- `[CODE]` — lido no ficheiro, com `ficheiro:linha`. Foi lido, não inferido de um resumo.
- `[MEASURED]` — um número, com o comando ou a linha de log que o produziu, e a data.
- `[INFERENCE]` — conclusão minha a partir de `[CODE]`/`[MEASURED]`, com o raciocínio à vista.
- `[UNKNOWN]` — não medido, não lido, ou medido num processo anterior ao código.

Um `[MEASURED]` de uma instância que corre código ANTERIOR ao `HEAD` mede o código velho: o
projecto tem um portão para isso (`_main/live-code-freshness-oracle.py --strict`, que devolve
`STALE`/`FRESH`/`UNKNOWN`). Onde isso importa, a frase diz qual dos três.

## Escala do que está a ser descrito

Medido em 2026-11-12 com `python _main/spec-scale.py` (o instrumento existe porque um número publicado
sem o comando que o produziu apodrece; a regra das extensões e dos directórios excluídos está escrita
no cabeçalho dele):

| superfície | ficheiros | linhas |
|---|---|---|
| `app/webview/**/*.py` (a shell e os seus módulos) | 45 | 48 718 |
| `worker/**/*.py` (o motor de transcrição) | 65 | 36 015 |
| `app/panel/**` (a UI web: HTML/CSS/JS + os temas) | 124 | 43 196 |
| total de produto lido | **234** | **127 929** |

O ficheiro maior é `app/webview/sotto_webview.py`, **26 774 linhas**, com **217 membros** em
`SottoShell` e mais 28 classes (o watcher de legendas externas, a ponte do worker, a bandeja, o
hotkey, o vigia de VRAM, o seguidor de arrasto, o monitor de carga...). O segundo é
`worker/sotto_worker.py`, **9 493 linhas**, 17 classes. O maior ficheiro de UI é
`app/panel/panel.js` (4 724 linhas) e `app/panel/themes/cinematic.css` (7 543).

Três ficheiros dentro de `worker/` **não são produto**: `_prefix_audioflag.py` (4 511 linhas),
`_sotto_worker_agcinert.py` (2 561) e `runs/_verdict-order-mutant.py` são cópias CONGELADAS do
worker usadas como mutantes por oráculos. Os dois últimos não estavam no git e entravam no índice em
2026-11-11 (`10-DEFECTS.md` §D-01 — `git ls-files` devolve os três desde então).

## O selo: 16 ficheiros, 5 312 linhas, 1 446 citações

Medido em 2026-11-12 com um `os.walk`/`len(splitlines())` e `grep -o '\[TAG\]'` ficheiro a
ficheiro, depois de entrar o `13-MODULES.md` (47 blocos, um por módulo de produto, mais as três
classes que são dados):

| o quê | número |
|---|---|
| ficheiros deste directorio | 16 (14 documentos + este índice + `STATUS.md`) |
| linhas | 5 312 |
| `[CODE]` | 1 329 |
| `[MEASURED]` | 170 |
| `[INFERENCE]` | 61 |
| `[UNKNOWN]` | 68 |
| citações `ficheiro:linha` resolvidas | **1 446**, 0 sem ficheiro, 0 fora de alcance |

Dois portões, e eles julgam metades diferentes: `_main/spec-citations-oracle.py` abre cada
ficheiro citado, resolve cada linha e recusa uma citação a um ficheiro que não existe ou a uma
linha além do fim; `_main/spec-coverage-oracle.py` faz a pergunta simétrica — percorre os ficheiros
de PRODUTO e recusa um módulo que documento nenhum nomeie (`115` módulos, `0` ausentes, `5`
casados só pelo nome, que a linha `NOME-APENAS` diz). Os dois estão na bateria
(`spec-citations`, `spec-coverage` e os respectivos `red-as-expected-*`).

**O que o portão NÃO prova.** Que a linha citada diga o que a frase diz. Duas frases passaram o
portão e estavam erradas — o escritor de `_main/webview-worker-tracebacks.log` e o papel de
`history/audio/` — e as duas foram corrigidas no `01-ARCHITECTURE.md` a partir do código, com o
`grep` ao lado (`STATUS.md` §"Duas contradições").



## A regra que este directorio respeita

Este projecto já paga caro por documentação que descreve um estado que já não existe. Por isso:

1. **Nenhum número é copiado de outro documento.** Cada `[MEASURED]` foi re-medido, ou diz
   explicitamente que é histórico e de quando.
2. **A prosa descreve o código, e o código manda.** Quando os dois discordam, o defeito é do
   código ou da prosa — e o `10-DEFECTS.md` diz qual.
3. **O que não se sabe escreve-se como não se sabe.** `[UNKNOWN]` é uma resposta.

Os documentos antigos (`docs/politica-youtube.md`, `docs/worker-lifecycle.md`,
`docs/hotkey-gestos.md`, `docs/bateria-e-portoes.md`, `docs/factos-medidos.md`, ...) continuam a
ser a memória das decisões. Este conjunto não os substitui: ele descreve o comportamento e
aponta para eles quando a razão de uma escolha vive lá.
