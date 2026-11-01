# Recibo — P3.1: o ratchet do wiring da bateria

item: **P3.1** de `docs/roadmap-observability.md` (2026-10-23) · data **2026-10-25** · repo `H:\sotto`
· **sem commit, sem push** · estado honesto: **ENTREGUE e ligado à bateria, NÃO VERIFICADO por
verificador independente e NÃO exercitado dentro de uma corrida da bateria** (gate `heavy` AMBER).

## P3.1

A linha do roadmap: *"Ratchet do wiring da bateria: 90 oráculos de enforcement existem e nenhum passo os
corre (37 de 127 ligados); um oráculo novo sem passo é vermelho"* — portão declarado:
`_main/battery-wiring-oracle.py` + baseline.

## 1. O defeito que isto fecha

Um oráculo que ninguém corre é um comentário caro: existe, parece enforcement e não prova nada. O
`AGENTS.md` já escreve a versão desta falha para a bateria (*"um passo saltado não é um portão que
passou"*); P3.1 aplica-a à população de ficheiros. Antes deste passo não havia **nenhum** mecanismo que
impedisse a população de crescer mais depressa do que o *wiring*.

## 2. Numeros: os três do roadmap estavam velhos, e os de hoje são medidos

| | roadmap (2026-10-23) | medido 2026-10-25 11:5x |
|---|---|---|
| população de enforcement | 127 | **171** |
| ligados (`call :step`) | 37 | **47** |
| sem passo | 90 | **124** |

Os três números antigos ficam **retirados**, não corrigidos — a mesma regra que a P0.3 mechaniza para o
`AGENTS.md`. A população usa **os mesmos cinco globs** do `_main/tooling-intent-oracle.py`
(`*oracle*.py`, `*-gate.py`, `*_gate*.py`, `*-guard.py`, `*_guard*.py`): duas definições de "oráculo de
enforcement" seriam duas verdades. O *wiring* é lido das linhas `call :step` da **própria** `.cmd`, que
é a única declaração que executa passos.

## 3. Registo antes da edição dependente (Task Resolver, passo 1–2)

`T-08` foi apendada ao TODO existente com `status: doing` **antes** de qualquer ficheiro novo, e o
replay estrito foi corrido nesse estado: `RED code=REQUIRED_ID_UNSETTLED detail=T-08 status=doing`. É o
estado em voo declarado, não um verde emprestado. Classificação das linhas de aceitação:

| # | linha | classe | invocador real | controlo positivo | controlo negativo |
|---|---|---|---|---|---|
| R1 | o censo separa população/ligados/sem-passo e a partição fecha | **MECHANICAL** | `python _main\battery-wiring-oracle.py` | `wiring-counted` com 171 = 47 + 124 | `blank-battery` → `wiring-counted` recusa |
| R2 | um oráculo novo sem passo é vermelho | **MECHANICAL** | idem | `new-unwired` verde com baseline completo | `add-unwired-oracle` → `new-unwired` |
| R3 | o baseline só pode encolher | **MECHANICAL** | idem | `baseline-orphans` verde | `wire-baselined` e `delete-baselined` → `baseline-orphans` |
| R4 | o tecto vive no código, não no JSON | **MECHANICAL** | idem | `baseline-ceiling` com 124 ≤ 124 | `grow-baseline` → `baseline-ceiling` |
| R5 | um baseline ausente não é um verde | **MECHANICAL** | idem | `census-readable` verde | `drop-baseline` → `census-readable` |
| R6 | um oráculo existente mas nunca chamado **não** conta como prova | **JUDGMENT** | este recibo | o baseline nomeia os 124 com razão e data | falsificador: qualquer entrada cujo ficheiro já esteja ligado → `baseline-orphans` |

**Invoker da bateria:** `call :step battery-wiring 0 … python _main\battery-wiring-oracle.py` e
`call :step red-as-expected-battery-wiring 1 … --neg-arm` com o token `NEG-ARM PASS`.

## 4. O que mudou (caminhos exactos)

| caminho | tipo | bytes | sha256 |
|---|---|---|---|
| `_main/battery-wiring-oracle.py` | **novo** (LF, sem BOM — primeiros bytes `35 33 47` = `#!`) | 17152 | `e187596a0413745cf32c2e94d09cc89d24763930edaab4b3197a07e3268bdafc` |
| `_main/battery-wiring-baseline.json` | **novo**, 124 entradas com `file`/`reason`/`date` | 16781 | `0b8c997694cefb7ab611f9ab785443e4c26af378e36beeee40e39432cf8013e2` |
| `_main/_audit-verify-all.cmd` | 2 passos novos (7 linhas de comentário + 6 de passo) | 116990 (1558 CRLF / 0 bare LF) | `a81e170b4b0a25c0f2e3e35090256b7321453d4c18e7dffd9458c5be4739285f` |
| `AGENTS.md` | pin re-medido + a linha de história | 21388 | `40483d8764414e0a34797bdafff82ba4ca2a6b1fbac7fafacdca0883a1c829ab` |
| `docs/state-generated.md` | regenerada (126 passos) | 16971 | `c6dce624bd4164971b7852b8baebc41ce38af18a9cc7508848bdbb1347b556ce` |

Ficheiros de produto de outras lanes: **não tocados** (`app/webview/sotto_webview.py`,
`app/webview/youtube_window.py`, `worker/sotto_worker.py`; mtimes 2026-10-23/24).

## 5. Evidência executada

**O ratchet a morder o próprio autor** (o `expected red` que vale mais: o ficheiro novo é um oráculo e
ainda não tinha passo, e o baseline recusou-se a licenciá-lo):

```
python _main\battery-wiring-oracle.py --write-baseline
RED  125 oraculo(s) sem passo > CEILING 124: nao se grava um baseline que cresce
rc=1
```

Depois do par de passos entrar na bateria:

```
python _main\battery-wiring-oracle.py --write-baseline
wrote _main\battery-wiring-baseline.json with 124 entry(ies) (ceiling 124, ligados 47 de 171)

python _main\battery-wiring-oracle.py
CHECK census-readable    PASS  populacao=171 ligados=47 sem_passo=124
CHECK baseline-schema    PASS  0 entrada(s) sem file/reason/date
CHECK baseline-ceiling   PASS  baseline com 124 entrada(s) <= CEILING 124
CHECK new-unwired        PASS  nenhum oraculo novo sem passo
CHECK baseline-orphans   PASS  nenhuma entrada orfa
CHECK wiring-counted     PASS  ligados=47 sem_passo=124 populacao=171
SUMMARY populacao=171 ligados=47 sem_passo=124 ceiling=124
BATTERY-VERDICT battery-wiring PASS checks=6 fail=0
rc=0

python _main\battery-wiring-oracle.py --neg-arm
MUTATION add-unwired-oracle  NEG-ARM PASS [esperado: new-unwired]        recusou por: new-unwired
MUTATION wire-baselined      NEG-ARM PASS [esperado: baseline-orphans]   recusou por: baseline-orphans
MUTATION delete-baselined    NEG-ARM PASS [esperado: baseline-orphans]   recusou por: baseline-orphans
MUTATION grow-baseline       NEG-ARM PASS [esperado: baseline-ceiling]   recusou por: baseline-ceiling
MUTATION drop-baseline       NEG-ARM PASS [esperado: census-readable]    recusou por: census-readable
MUTATION blank-battery       NEG-ARM PASS [esperado: wiring-counted]     recusou por: wiring-counted
NEG-ARM PASS mutations=6 named-arm-fail=0
rc=1
```

Portões que policiam a mudança:

```
python _main\agents-md-pins-oracle.py
sotto:     1558 CRLF                                      true
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
VERDICT: PASS                                                            rc=0

python _main\sotto-state-page.py --require-fresh
SUMMARY passos=126 PASS=49 EXPECTED-RED=17 FAIL=7 STALE=37 NO-VERDICT=7 NOT RUN=9
BATTERY-VERDICT state-page PASS checks=8 fail=0                          rc=0

python _main\claims-date-oracle.py   -> BATTERY-VERDICT claims-date PASS checks=4 fail=0   rc=0
python _main\tooling-intent-oracle.py-> TOOLING-INTENT VERDICT PASS     rc=0
   (declaradas 10 -> 11: o ficheiro novo declara `# NO-BUG:` com a razão de P3.1)
```

## 6. Passagem de refutação

**(a) A atribuição de um mutante estava errada — corrigida.** `blank-battery` foi escrito a esperar
`census-readable`; com a bateria vazia essa verificação **continua verde** (a população não é vazia e a
partição ainda fecha), e quem recusa é `wiring-counted` (`wired > 0`). A mutação passou a nomear
`wiring-counted`: um check, uma afirmação. Sem esta passagem ficaria um mutante que "passa" pelo motivo
errado.

**(b) Um segundo erro, este de mecânica.** Os mutantes que precisam de um nome **sem passo** liam a
população da cópia em `$TMPDIR`, onde não há `_main/*.py` — davam `ERROR nenhum oraculo sem passo no
repo real`. Passaram a receber `ctx = {pop, unwired}` do repo real; a população de ~171 ficheiros não se
copia para uma sandbox, e isso está declarado no cabeçalho do ficheiro.

**(c) O que a passagem não derrubou, e fica como limite.** O portão prova que o ficheiro é
**referenciado** por um passo; não prova que o passo o invoque com o argv certo, nem que o oráculo seja
honesto (isso é o teste de cada um). Um oráculo chamado por um *wrapper* fica `unwired` e tem de ser
declarado no baseline com essa razão.

## 7. Fronteira do Watcher (porque não há corrida da bateria aqui)

`I:\!manager\tools\performance-gate.py status` → **AMBER**, `heavy_allowed=False` (commit 81,4 %), com
um lease `light` de outro dono activo. Logo: **nenhuma corrida completa da bateria nesta lane**. Os dois
passos novos foram exercitados com o **argv exacto** que a `.cmd` lhes dá e os rc que ela espera (0 e 1),
mas o verde *dentro de uma corrida* fica `NOT RUN` — a página de estado mostra-o assim, e é assim que
deve estar.

## 8. Reverter

Apagar `_main/battery-wiring-oracle.py` e `_main/battery-wiring-baseline.json`; retirar os dois blocos
`battery-wiring` / `red-as-expected-battery-wiring` da `.cmd` e reverter o pin no `AGENTS.md` para
**115613 B / 1544 CRLF / `128CA98A…6D82E7`**; regenerar `docs/state-generated.md`. Nada mais importa
estes ficheiros.

## 9. Abertos, com dono

1. **Corrida da bateria** (fecha o verde dos dois passos novos): precisa do lease `heavy`.
2. **`code-health` FAIL rc=2** — 8 métricas em 3 ficheiros de outra lane, inalterado por esta.
3. **124 oráculos sem passo** — a dívida está agora **visível e com tecto**; cada um fecha-se ligando-o
   (a entrada sai do baseline) ou apagando-o. P3.1 não promete zero: promete que não cresce.
