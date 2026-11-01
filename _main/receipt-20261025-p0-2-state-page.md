# Recibo — P0.2: a página de estado é gerada, e recusa-se a inventar

item: **P0.2** do `docs/roadmap-observability.md` (2026-10-23) · data **2026-10-25** · repo `H:\sotto`
· **sem commit, sem push** · estado honesto: **ENTREGUE, NÃO VERIFICADO por verificador independente**.

A frase do roadmap que isto fecha: *"Página de estado **gerada** a partir das saídas dos oráculos,
nunca escrita à mão; recusa renderizar um passo que não correu"*, com o portão *"recusa-se a inventar:
um passo ausente é `NOT RUN`, nunca um verde"*.

---

## P0.2

## 1. Porque P0.2 e não outro item (a escolha, com a razão medida)

`docs/roadmap-observability.md` §P0 lista P0.1 e P0.2 como os dois por fazer. **P0.1** (`sotto facts` +
`facts.json`) precisa de `--verify` a re-correr instrumentos, e vários deles carregam os modelos —
classe `heavy`, e o portão central está **AMBER com `heavy_allowed=False`** (§6). **P0.2** lê bytes:
nenhum processo pesado, nenhum ficheiro de produto. É o único item de P0 que uma lane pode fechar
honestamente hoje.

## 2. O que mudou (caminhos exactos, bytes, sha256)

| caminho | tipo | bytes | sha256 |
|---|---|---|---|
| `_main/sotto-state-page.py` | **novo** (LF) | 32442 | `c01a49cdcafea8d27f6c23fa0aa96777375d3d7c22280dcecfac2821fa64e873` |
| `docs/state-generated.md` | **novo**, gerado (LF) | 16725 | `1ab4e22ad129458aa3843c756ed3530f1b92a5aa3127ea614978a87a189cfe68` |
| `_main/_audit-verify-all.cmd` | 2 passos novos (`state-page`, `red-as-expected-state-page`) | 115613 (1544 CRLF / 0 bare LF) | `128ca98a6f5214665e4355552bdb150a1cd6f677cf79b9f492a37546d06782e7` |
| `AGENTS.md` | pin do `.cmd` re-medido + a linha de história | 20917 | `9ee49eef974c5a0407473ba65c1d1e604a0b1a2f0d30946dd57b359970138c73` |
| `docs/roadmap-observability.md` | estado da P0 com P0.2 entregue + números de P3.3 | 8099 | `a84f7572a1f45f614a61804ae25adacf0ee7c2c995769133109177057fbf94a2` |
| `_main/stepcache-cost-probe.py` | **novo** (P3.3: mede e não corta) | 10039 | `bf4d7645bbb040fe254ac550a75aa602d415dbeb893eab2fc5b89f458ccf51c5` |

**Os três ficheiros de produto sujos de outras lanes NÃO foram tocados:**
`app/webview/sotto_webview.py`,
`app/webview/youtube_window.py`, `worker/sotto_worker.py`. `code-health` continua no mesmo estado
medido antes desta lane — os mesmos 8 métricas pioradas, nenhuma nova (§5).

## 3. O desenho: três artefactos, nenhuma prosa escrita à mão

A página é uma função pura de:

1. **declaração** — `_main/_audit-verify-all.cmd`: `call :step [always] [heavy] NOME EXPECT "deps"
   "%OUT%\NOME.log" <cmd>` e `call :expectred NOME !STEP_RC! "log" "TOKEN"`. A **lista de passos vem
   daqui**, logo a página não pode inventar um passo que a bateria não declara nem perder um que ela
   declara (check `step-declared`).
2. **registo** — `_cache/battery-steps.json`, escrito pelo `_main/_stepcache.py`: rc, expect_rc,
   timestamp, deps e respectivos hashes, sha256 do log. Sem entrada aqui o passo **não correu**.
3. **saídas** — `_main/_audit-verify/*.log`.

Seis estados, e a regra que cada um exige:

| estado | exige |
|---|---|
| `PASS` | rc == expect == 0 **e** log com o sha256 registado **e** fingerprint das deps de hoje |
| `EXPECTED-RED` | rc == expect != 0 **e** o token de `:expectred` presente no log |
| `FAIL` | rc != expect (inclui um braço negativo que ficou verde) |
| `STALE` | correu bem, mas as deps mudaram depois da medição |
| `NO-VERDICT` | log ausente/alterado, token ausente, dep ausente, registo ilegível |
| `NOT RUN` | o stepcache não tem registo |

O fingerprint não é reimplementado: o motor `_main/_stepcache.py` é carregado e usado
(`fingerprint(deps)`), porque duas implementações do mesmo fingerprint seriam duas verdades.

## 4. Controlos - o positivo e os oito negativos, executados

Positivo (a página real, na raiz real):

```
python _main\sotto-state-page.py --require-fresh
CHECK step-declared        PASS  declarados=124 na_pagina=124 duplicados=- ausentes=- inventados=-
CHECK no-invented-green    PASS  0 verde(s) sem sustentacao
CHECK absent-is-not-run    PASS  0 passo(s) sem registo e sem log fora de NOT RUN
CHECK expected-red-token   PASS  0 EXPECTED-RED sem o token exigido
CHECK verdict-vocabulary   PASS  vocabulario fora da lista
CHECK cells-match-record   PASS  0 celula(s) fora do registo
CHECK page-in-sync         PASS  pagina identica a renderizacao fresca
CHECK summary-counts       PASS  resumo da pagina = contagem real
SUMMARY passos=124 PASS=49 EXPECTED-RED=17 FAIL=7 STALE=37 NO-VERDICT=7 NOT RUN=7
BATTERY-VERDICT state-page PASS checks=8 fail=0
rc=0
```

Negativos (`python _main\sotto-state-page.py --neg-arm`, **rc=1 por desenho**):

```
MUTATION forget-step         NEG-ARM PASS [esperado: absent-is-not-run]  recusou por: no-invented-green, absent-is-not-run, page-in-sync, summary-counts
MUTATION add-fake-row        NEG-ARM PASS [esperado: step-declared]     recusou por: step-declared, page-in-sync
MUTATION drop-row            NEG-ARM PASS [esperado: step-declared]     recusou por: step-declared, page-in-sync
MUTATION rc-mismatch         NEG-ARM PASS [esperado: no-invented-green] recusou por: no-invented-green, page-in-sync, summary-counts
MUTATION strip-neg-token     NEG-ARM PASS [esperado: expected-red-token] recusou por: no-invented-green, expected-red-token, page-in-sync, summary-counts
MUTATION fingerprint-drift   NEG-ARM PASS [esperado: page-in-sync]      recusou por: no-invented-green, page-in-sync, summary-counts
MUTATION falsify-when        NEG-ARM PASS [esperado: cells-match-record] recusou por: cells-match-record, page-in-sync
MUTATION hand-edit-verdict   NEG-ARM PASS [esperado: page-in-sync]      recusou por: no-invented-green, absent-is-not-run, page-in-sync
NEG-ARM PASS mutations=8 named-arm-fail=0
rc=1
```

**`falsify-when` nasceu da passagem de refutação, não do desenho.** A primeira versão julgava só o
*estado* de cada linha: uma linha com o `quando` (ou o `rc`, ou o `log`) editados à mão passava as seis
verificações estruturais, porque a frescura só é exigida com `--require-fresh`, e o passo da bateria
corre sem ela. A cura é o check `cells-match-record`, que compara as quatro células de medida
(`rc`, `expect`, `quando`, `log`) com o registo, e o mutante que a prova. O buraco está fechado e
declarado aqui em vez de ter sido varrido para debaixo do tapete.

O mutante que a linha do roadmap pede por nome é `forget-step`: apaga o registo **e** o log de um passo
que a página dá como verde, e a recusa nomeada é `absent-is-not-run` — a página deixa de poder dizer
verde, e o gate di-lo nessa verificação e não "nalguma".

**Limite dos mutantes, declarado:** correm sobre uma cópia em `$TMPDIR` com a página, o registo, o
motor, a `.cmd` e os logs. As **deps não são copiadas** — pesam **830 927 381 B** em 166 ficheiros
(medido 2026-10-25), por isso o motor é apontado ao repo real (`module.REPO = root`). É uma escolha
declarada no código, e é por isso que o mutante `fingerprint-drift` reescreve o **fingerprint
registado** em vez de sujar uma dep real: mesma observável, sem tocar na árvore.

## 5. O que a primeira página diz do repo (factos, não opiniões)

`passos=124 PASS=49 EXPECTED-RED=17 FAIL=7 STALE=37 NO-VERDICT=7 NOT RUN=7` (medido 2026-10-25 10:3x).

- **7 `FAIL`, todos da corrida de 2026-10-24**, e nenhum é desta lane: `code-health` rc=2,
  `exception-hygiene` rc=2, `red-as-expected-code-health` rc=2 (esperava 1),
  `panel-flash-contradiction` rc=1, `red-as-expected-panel-flash-contradiction` rc=2 (esperava 1),
  `strip-hot-reload` rc=3, `strip-surface-runtime` rc=3.
- **37 `STALE`**: o passo correu bem, mas as deps mudaram depois. É o preço honesto de 713 caminhos
  sujos; sem o estado `STALE` estes 37 apareceriam como verdes de hoje, que é precisamente a tabela
  escrita à mão que P0.2 existe para não ter.
- **7 `NO-VERDICT`**, e a maioria é "log alterado depois do registo": o log foi reescrito por uma
  corrida posterior e o registo descreve bytes que já não existem. `lane3-verdict-probe`,
  `tap-open-timeout`, `mute-audio`, `strip-stats-log-budget`, `strip-geometry-restore`,
  `strip-stats-wave`, `control-panel-exit3-neg-arm`.
- **7 `NOT RUN`**: `caption-dup-repro`, `task-resolver-gate`, `red-as-expected-task-resolver-gate`,
  `claims-date`, `red-as-expected-claims-date` (os quatro últimos nasceram **depois** da corrida de
  2026-10-24) e os dois desta lane, `state-page` e `red-as-expected-state-page`.
- `code-health` foi corrido à mão nesta lane e continua **FAIL rc=2** com os mesmos 8 métricas
  pioradas dos três ficheiros de outra lane — nenhuma nova introduzida aqui.

## 6. Portões que policiam esta mudança (corridos, com saída)

```
python _main\agents-md-pins-oracle.py
sotto: PIN 2 -- the _audit-verify-all.cmd corrections row:
sotto:     115613 B                                       true
sotto:     1544 CRLF                                      true
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
VERDICT: PASS
rc=0

python _main\claims-date-oracle.py
CHECK new-undated-claim    PASS  4 afirmacao(oes) sem data, todas com licenca no baseline
CHECK baseline-schema      PASS  4 entrada(s) com line_sha256/excerpt/reason/date/instrument
CHECK baseline-ceiling     PASS  baseline com 4 entrada(s) <= CEILING 4
CHECK baseline-orphans     PASS  nenhuma entrada orfa
BATTERY-VERDICT claims-date PASS checks=4 fail=0
rc=0

python _main\tooling-intent-oracle.py
declaradas: 10 | baseline (sem declaracao): 160 | vermelhas: 0
ratchet: baseline declara 160; hoje sem declaracao sao 160 (nao pode crescer)
TOOLING-INTENT VERDICT PASS
rc=0

python _main\code-health-oracle.py
piorem: 8 metrica(s)
CODE-HEALTH VERDICT FAIL
rc=2   <-- dívida de OUTRA lane, inalterada por esta (8 antes, 8 depois)
```

`_main\sotto-state-page.py` declara `# NO-BUG:` com a razão (trabalho de capacidade, P0.2), como a lei
do `tooling-intent` exige para uma ferramenta nova.

## 7. Linhas que ficam ABERTAS, com o dono e o que as fecha

1. **A bateria completa NÃO correu.** `performance-gate.py status` → **AMBER**,
   `heavy_allowed=False` (commit 81,4 %). Logo `state-page` e `red-as-expected-state-page` estão na
   bateria **e foram exercitados à mão** com os mesmos comandos e os mesmos rc, mas o verde
   *dentro de uma corrida da bateria* não está provado. Fecha-se com
   `_main\_audit-verify-all.cmd` quando o lease `heavy` abrir, e a linha fica `NOT RUN` até lá.
2. **`code-health` FAIL** (8 métricas, 3 ficheiros de outra lane). Fecha-se reconciliando
   `app/webview/sotto_webview.py`, `app/webview/youtube_window.py`, `worker/sotto_worker.py` — fora do
   `owned_paths` desta lane.
3. **`STALE=37` / `NO-VERDICT=7` na página** não são defeitos do portão: são o retrato do repo. Fecham-se
   com uma corrida da bateria que re-registe os passos e, para os `NO-VERDICT` por log alterado, com a
   mesma corrida (registo e log voltam a casar).

## 8. Reverter

Apagar `_main/sotto-state-page.py` e `docs/state-generated.md`; retirar os dois blocos `state-page` /
`red-as-expected-state-page` de `_main\_audit-verify-all.cmd` e reverter o pin no `AGENTS.md` para
**114291 B / 1530 CRLF / `56D357C8…42FF0322`**; apagar a secção P0.2 do roadmap. Nada mais importa
estes ficheiros.

## 9. Proveniência

Skill lida: `.agents/skills/task-resolver/SKILL.md` v1.3.0 (12731 B, sha256 `9220565f…022f`) e o TODO
da lane `state/work/TC-20261025-cross-project-continuity/sotto-lane/todo.md` (24/24 settled, replay
estrito `rc=0`). Registo único usado: as linhas **P0.2** e **P3.3** do `docs/roadmap-observability.md`
— não foi criado um segundo backlog. Rota: OpenCode Go 3 / DeepSeek V4.1 Flash.

---

## P3.3

# P3.3 — "custo do cache da bateria": o registo, e a medição que refuta o número do roadmap

## 10. Checklist registada antes da extensão de âmbito (P3.3)

Item aceite: **P3.3** de `docs/roadmap-observability.md` — *"Custo do cache da bateria: 33 s com
100/115 em cache ≈ 0,33 s por passo só para o resolver; medir quanto é arranque de processo e
cortar"*. Ordem de dependências, com a classificação e o controlo de cada linha:

| # | passo | classe | invocador real | controlo positivo | controlo negativo | rollback |
|---|---|---|---|---|---|---|
| 1 | medir o piso de arranque (`python -c pass`, 5 amostras, mediana) | **MECHANICAL** | `_main/stepcache-cost-probe.py` | valor > 0 e reprodutível em 2 corridas | estado ausente → `NO-VERDICT` rc=2, nunca um número | apagar a sonda |
| 2 | medir o resolvedor por dentro (motor + estado + fingerprint de deps **reais**) | **MECHANICAL** | idem | soma dos passos == os passos escolhidos do estado | estado corrompido → `NO-VERDICT` | idem |
| 3 | medir end-to-end (`_stepcache.py check` por processo, mesmo argv da `.cmd`) | **MECHANICAL** | idem | rc e stdout iguais aos do motor chamado directamente | estado vazio → `NO-VERDICT` ("nenhum passo com deps") | idem |
| 4 | comparar com os três números do roadmap (33 s / 100 passos / 0,33 s) | **JUDGMENT** | o recibo | o número medido + a projecção, lado a lado | falsificador: se a projecção batesse 33 s, o roadmap estava certo | — |
| 5 | decidir o alvo do corte | **JUDGMENT** | este §11 | a fracção medida (`resolver/end-to-end`) | falsificador: um corte no resolvedor que não mexa no total | — |
| 6 | cortar de facto (editar `_main\_stepcache.py` ou a linha `for /f` da `.cmd`) | **MECHANICAL** | `_main\_audit-verify-all.cmd` | antes/depois com o mesmo instrumento | — | reverter a linha + o pin |

**Limite de desempenho declarado:** a sonda faz no máximo `SAMPLES=5` subprocessos por passo medido e
`--limit` passos (default 8) — ~130 subprocessos no total, cada um ~60 ms: **ordem de 8 s**, sem
modelos, sem áudio, sem painel. Corre dentro do lease `light`; não pede `heavy`.

**Estado da linha 6: NÃO FEITA.** O corte exige um antes/depois dentro de uma corrida da bateria, e a
bateria está atrás do gate `heavy` (AMBER, `heavy_allowed=False`). P3.3 fica **MEDIDO, não entregue**.

## 11. A medição (e o número do roadmap não se reproduz)

```
python _main\stepcache-cost-probe.py
passos medidos: 8 (agents-md-pins, audit-history-dead, autostart-status, battery-heavy-gate, border-radius-gate, bug-ledger, caption-native-wrap, code-health)
startup      : 42.6 ms  (5 amostras, mediana)
resolver     : 1.6 ms  (motor+estado+fingerprint, por dentro)
end-to-end   : 63.3 ms  (um `_stepcache.py check` por processo)
resolver/share: 2.6 %
projected 100 passos (cache hit): 6.3 s
PROBE-VERDICT measured
rc=0

python _main\stepcache-cost-probe.py --neg-arm
ARM missing-state    PASS  estado ausente: _cache\battery-steps.json
ARM corrupt-state    PASS  estado ilegivel: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
ARM empty-state      PASS  nenhum passo com deps no estado
NEG-ARM PASS arms=3 fail=0
rc=1
```

**O que isto diz, e o que o roadmap dizia.** O roadmap afirmava **0,33 s por passo** e **33 s** para
100 passos em cache. Medido com o mesmo instrumento por dentro e por fora: **63,3 ms por passo**,
**6,3 s** projectados para 100 — cinco vezes menos. Nenhum dos três números antigos tinha instrumento
ao lado; este fica com um, e por isso o número velho fica **retirado**, não corrigido.

**O alvo do corte muda de sítio.** O resolvedor — que a linha do roadmap mandava atacar — é **2,6 %**
do custo (1,6 ms de 63,3 ms). O custo é **arranque de processo**: 42,6 ms de 63,3 ms (67 %). Um corte
no resolvedor optimizaria o que não pesa.

**Candidato medido para a linha 6** (não aplicado, e por isso não é entrega):

```
python      -c pass : 41.1 ms      python -S   -c pass : 21.7 ms
e2e python   (code-health): 65.4 ms      e2e python -S: 54.0 ms      mesmo stdout: True
```

`-S` corta 17 % do end-to-end com o mesmo veredicto; para 100 passos em cache, 6,5 s → 5,4 s. Aplicá-lo
mexe na linha `for /f` da `.cmd` (linha 1286) e obriga a re-medir o pin e a provar o antes/depois
**dentro** de uma corrida da bateria — trabalho do próximo ciclo, com o lease `heavy` aberto.

## 12. Passagem de refutação (sequencial, depois da primeira verificação)

Objectivo da passagem: **tentar derrubar o resultado**, não confirmá-lo. Duas coisas foram encontradas
e as duas viraram código.

**(a) As células de medida não eram julgadas — REFUTADO, e curado.** A primeira versão julgava o
*estado* de cada linha e nada mais. Uma linha com o `quando` (ou o `rc`, ou o `log`) escritos à mão
passava as verificações estruturais, porque a frescura só é exigida com `--require-fresh` e o passo da
bateria corre sem ela. Cura: check `cells-match-record` (compara `rc`, `expect`, `quando`, `log` com o
registo) e mutante `falsify-when`, que edita um `quando` e tem de ser recusado por esse check —
`NEG-ARM PASS [esperado: cells-match-record]`.

**(b) O problema do observador — REFUTADO, e curado.** Os dois passos desta ferramenta são linhas da
própria página, e a bateria **trunca o log deles antes** de o processo arrancar
(`> "%OUT%\state-page.log"`). O veredicto deles é intrinsecamente corrido enquanto o observador olha: o
resumo comparado com a renderização fresca ia divergir e o passo ficava `FAIL` sozinho, em todas as
corridas. Cura: `SELF_STEPS` — as duas linhas do observador ficam **fora** da comparação de células e
do resumo (o que o passo da bateria julga) e continuam a ser renderizadas e julgadas na escrita.
Controlo positivo executado contra uma cópia com o log do observador truncado como a bateria faz:

```
copy intact, observer log truncated: no error
  step-declared        PASS declarados=124 na_pagina=124 duplicados=- ausentes=- inventados=-
  no-invented-green    PASS 0 verde(s) sem sustentacao
  absent-is-not-run    PASS 0 passo(s) sem registo e sem log fora de NOT RUN
  expected-red-token   PASS 0 EXPECTED-RED sem o token exigido
  verdict-vocabulary   PASS  vocabulario fora da lista
  cells-match-record   PASS 0 celula(s) fora do registo
  summary-counts       PASS resumo da pagina = contagem real
structural verdict: PASS
page row for state-page: NOT RUN
```

**(c) O que a passagem NÃO derrubou, e por isso fica declarado como limite.** (i) Um `rc=0` com texto
de `FAIL` no log continua a ler-se `PASS`: a página afirma *"rc igual ao esperado, log com o sha256
registado, deps inalteradas"* e não afirma que o oráculo é honesto — isso é o `tooling-intent` e o
teste de cada oráculo. (ii) Uma edição **coordenada** da página e do registo escapa a um gate local;
ficaria a precisar de história, não de um censo. (iii) `--check` sem `--require-fresh` não prova que a
página é fresca — prova que nenhuma linha inventa uma medida; quem escreve corre `--require-fresh`.

**Controlos depois da cura** (o número final, não o primeiro): `--require-fresh` → `checks=8 fail=0`,
rc=0; `--neg-arm` → `mutations=8 named-arm-fail=0`, rc=1 por desenho.


