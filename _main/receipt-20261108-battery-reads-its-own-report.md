# RECIBO — a bateria que nao lia o proprio relatorio (2026-11-08)

Corrida de partida: `_main\_audit-verify-all.cmd` de **2026-11-08T10:0xZ**, `steps=371`,
`BATTERY-VERDICT: RED - 17 step(s) failed`. Dezessete era o numero que o recibo anterior
(`receipt-20261108-gate-repairs.md`) tinha deixado; esta rodada mede o que SOBRAVA depois dele e o que
a medicao nova encontrou: **seis defeitos**, todos de INSTRUMENTO, nenhum de produto.

| # | defeito | como foi medido | cura |
|---|---|---|---|
| 1 | **o bloco do painel corria DEZ passos com UM `call :record`** — e o unico registo carimbava o `!STEP_RC!` do ULTIMO passo no nome do PRIMEIRO | `battery-record-pairing-oracle.py` novo: `achados: 10` (`9` x `R1-sem-registo`, `1` x `R2-registo-atrasado`) | dez `:record`/`:expectred`, um por passo; `R2` trocado do ultimo para o PRIMEIRO registo posterior (o `else` de um `if exist` tem um segundo `:record` do mesmo nome, e ler o ULTIMO dava falso positivo em `battery-plan`) |
| 2 | `red-as-expected-caption-drag` declarado `:step ... 0` (espera rc=0) com um oraculo que devolve **1 quando apanha** | `python _main/caption-drag-oracle.py --neg-arm` → `rc=1`, `NEG-ARM: PASS` | `:step 1` + `:expectred ... "NEG-ARM: PASS"` |
| 3 | `red-as-expected-outside-click-timer` no mesmo contrato trocado | `python _main/outside-click-timer-oracle.py --neg-arm` → `rc=1` | `:step 1` + `:expectred` |
| 4 | `red-as-expected-hotkey-spam` declarado `:expectred` com um oraculo que devolvia **0 ao apanhar** | `--neg-arm` → `rc=0` com `NEG-ARM PASS` impresso | `return EXIT_FAIL` no ramo "apanhou"; medido `rc=1` e o positivo continua `rc=0` (19/19 arms) |
| 5 | **tres `--neg-arm` a morrer em `FileNotFoundError`** porque o mutante e' uma COPIA de `youtube_cdp_source.py` num diretorio temporario e `_load_sibling` (youtube_cdp_source.py:50) carrega `youtube_window.py` PELO CAMINHO do proprio ficheiro | blast de 5 oraculos cdp: 3 com `sibcrash=1` e **zero** linhas `NEG-ARM` (`yt-target-stale`, `youtube-cdp-slow`, `youtube-cdp-boot`) | o irmao e' copiado para o diretorio do mutante nos tres; medido depois: `NEG-ARM: PASS -- 7 arms, 5 mutants`, `NEG-ARM VERDICT: PASS (6/6)`, `NEG-ARM PASS (RED as designed)` |
| 6 | `youtube-land --neg-arm`: o mutante `real-late` reescrevia TODAS as linhas com um carimbo FIXO (`2026-11-03 05:43:00.000`), destruindo a ordem do log real; e a guarda do braco vivo perguntava a CONTAGEM de cues em vez do CONTROL | no log de 418 814 linhas: 5672 cues, controlo `rc=2` (`numeros que nao concordam (cue_t0=202.397 pintado duas vezes)`) e o mutante herdava esse 2, contado como "escapou" | o prefixo da linha original fica; e o braco vivo passa a exigir `control rc==0` — uma amostra imensuravel e' DITA (`saltado: 5672 cue(s), controlo rc=2 ...`) e nao entra no total. Medido: `6 of 6 mutant(s) caught`, `NEG-ARM: PASS`, `rc=1` |
| 7 | `warm-engine` RED **so' dentro da bateria**: `single-loader RED -- start_worker returned True` / `stop-detaches-not-kills RED -- warm bridge attached` | sozinho: `WARM-ENGINE VERDICT: PASS -- 22 arm(s), 0 red`; dentro da corrida: 2 red | as arms 15 e 17 esperavam `("unloaded","loading","parked-closed")` — e `unloaded` e' o PRIMEIRO estado —, logo faziam o attach contra um motor que ainda nao carregou e o `WARM_ATTACH_DEADLINE_MS = 500` (sotto_webview.py:7368) expirava sobre a maquina carregada. As duas passam a esperar `WARM_READY_STATES` (o motor CARREGADO e a aceitar). O prazo de 500 ms NAO se toca: e' politica do produto (`morno e' LENTO, nunca ERRADO`) e estas arms provam a invariante de um carregador, nao a latencia |

## 1. Porque o defeito #1 e' o pior desta casa

`:step` nao conta nada. Ele corre o comando, grava o registo do cache e deixa o `rc` em `!STEP_RC!`.
Quem conta e' `:record` / `:expectred` / `:skipped`. Com um registo para dez passos:

- NOVE vereditos nunca chegavam ao sumario (nem aos `failed=` nem aos `gate=`);
- o decimo lia o `!STEP_RC!` de OUTRO passo — no bloco medido, o de `red-as-expected-panel-deps`;
- e o `else ( call :record panel2-dom-probe MISSING )` continuava a existir, o que fazia o bloco
  PARECER registado a quem so' olhasse para o nome.

A mesma classe apareceu uma segunda vez: o `battery-plan` tem DOIS `:record battery-plan` (o do
caminho feliz e o do `else`), e ler o ULTIMO registo marcava-o como atrasado. As duas metades do
portao sao independentes de proposito: `R1` acha o registo em falta, `R2` acha o registo que le o `rc`
errado, `R3` acha o registo de um passo que nao existe. Medido com as tres doencas plantadas numa
COPIA: `NEG-ARM: PASS (3/3 mutantes apanhados)`, e o mutante orfao derruba A SUA arm (`R3-registo-orfao`
e a unica regra a mais no achado dele).

## 2. O que ficou medido depois das curas

| instrumento | veredicto | comando |
|---|---|---|
| `battery-record-pairing-oracle.py` | PASS — `passos: 382, nomes com registo: 382, achados: 0` | `python _main/battery-record-pairing-oracle.py` |
| o mesmo, controlo | `NEG-ARM: PASS (3/3)` | `... --neg-arm` (rc=1) |
| `battery-wiring-oracle.py` | PASS — `ligados=160 sem_passo=109 populacao=269` | `python _main/battery-wiring-oracle.py` |
| o mesmo, controlo | `NEG-ARM PASS mutations=6`, rc=1 | `... --neg-arm` |
| `battery-class-oracle.py` | PASS — `arms=3 fail=0` | |
| `undefined-names-oracle.py` | GREEN — 19 ficheiros de producao, 0 nomes | |
| `agents-md-pins-oracle.py` | PASS — 2 pins ao vivo | |
| `warm-engine-oracle.py` | `WARM-ENGINE VERDICT: PASS -- 22 arm(s), 0 red`; `--neg-arm` `NEG-ARM PASS -- 6/6 mutant(s) caught` (rc=1) | |
| `hotkey-spam-oracle.py` | positivo `rc=0` 19/19; `--neg-arm` `rc=1` com 12 arms RED | |

Pin do ficheiro, medido depois das curas: `_main\_audit-verify-all.cmd` = **290125 B**, **3507 CRLF**
/ 0 bare LF, sha256 `1427E999159AE6ACFA6809EFC919970F09612AA622D253621B850DBA8C9A6E72`
(`AGENTS.md`, §A BATERIA), e `agents-md-pins-oracle.py` le-o ao vivo.

## 3. O QUE NAO ESTA' VERIFICADO

- A corrida completa re-feita com estas curas estava a correr quando este recibo foi escrito. O
  `BATTERY-VERDICT` dela vive em `_main\_audit-verify\_battery-summary.txt` com o run id ao lado, e e'
  ele que conta — este recibo nao o adianta.
- `verified` continua impossivel de uma lane: nenhum destes numeros foi visto no ECRA do dono, e as
  curas nao mudam nada que ele veja. Mudam o que os instrumentos dizem sobre o que ele ve.
