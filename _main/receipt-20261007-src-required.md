# Recibo — o gate passa a EXIGIR o `src=` (H:/sotto, 2026-10-07)

**Lane:** `SottoSrcRequired` · **Repo:** `H:/sotto` · **Data:** 2026-10-07
**Ambito:** SO o Sotto (ordem do dono: *"trabalha so no sotto. nao mais no manager ou omp"*).
**Janela/audio:** NADA de janela e NADA de audio — so' leitura de ficheiro + um store em
`history-verify/` e `node`/`py -3`. Nao arranquei o shell nem o painel.

Engloba as DUAS edicoes que a lane `SottoSilentFallback` nomeou no seu proprio
`gate_melhor` (`_main/receipt-20261007-silent-fallback.md`).

---

## 0. O buraco, verbatim do recibo anterior (`falta_no_gate`)

> o novo campo NAO e' exigido por nenhum gate: `route-stamp-gate.js` le so' `route=`.
> Cenario que atravessa: uma mudanca futura faz `routeSourceFor` devolver um valor
> CONSTANTE (`'fallback'` sempre, ou `'worker-stamped'` sempre) e TODOS os gates atuais
> ficam verdes — o `src=` continua a ser escrito, so' que mentindo.

E o `gate_melhor` da mesma lane, verbatim:

> acrescentar a `_main/_cura-oracle-suite.py` a sonda `silent-fallback-probe` e, no
> `route-stamp-gate`, exigir que `route=final` carregue `src=` e que a arm NAO-VACUA valha
> (rota igual, fonte diferente). Input que TEM de deixar RED: (1) `node
> _main/silent-fallback-probe.js --engine <copia com a derivacao forca-constante>` (= o
> `--emit-mutant` de hoje) e (2) um stream sem `final` onde a linha de disco leia
> `src=worker-stamped`.

---

## 1. As duas edicoes

### 1a. `_main/route-stamp-gate.js` — o `src=` passa a ser EXIGIDO e RECALCULADO

O gate LE hoje so' `route=`; agora tem uma arm `G5` que, para cada linha `route=final`
no disco, REFUSA qualquer `src=` que nao seja o que a **propria arm recalcula** a partir
do SEU input — e um `route=final` SEM `src=` (um `null !== expected`) tambem e' recusado:

* arm do fallback (stream sem NENHUM `final`, cadencia NATURAL): so' `src=fallback` e'
  honesto;
* fixture (`final:true/false` presentes): so' `src=worker-stamped` e' honesto.

Para o gate poder exigir o campo, o SEU replay passou a SER FIEL: `run()` agora apanha
`meta.routeSource` no `onCommit` e passa-o a `store.append(...)`. Antes de hoje o replay
largava o campo, logo as linhas escritas pelo gate NAO tinham `src=` — exigir o campo sem
esta correccao deixaria o gate VERMELHO sobre si mesmo. `routesOnDisk()` passou a devolver
tambem `src=` e a cauda crua; a captura de `route` foi mantida **byte-identica**
(`/\s*<!--\s*(route=\S+)/`) para nenhum histograma `found` poder mover-se.

O mutante NOVO (a derivacao forcada a constante) e' construido pelo PROPRIO gate, a partir
do ficheiro vivo, com a expressao assertada PRESENTE exactamente uma vez (senao SETUP
ERROR rc=2) — a mesma mutacao que `silent-fallback-probe.js --emit-mutant` escreve.

### 1b. `_main/_cura-oracle-suite.py` — a sonda entra na suite

Nova linha `("silent-fallback-probe", [... node _main/silent-fallback-probe.js ...], 120)`
na tabela `ORACLES`, invocada atraves do interpretador como as outras sondas `.js`.

**NAO toquei** `app/electron/caption-formulation.js` (a `routeFor` tem de ficar
byte-identica — sha INALTERADO abaixo), `app/electron/panel.js`, o worker, nem o painel.

---

## 2. A aceitacao

### 2a. `node _main/route-stamp-gate.js` — ANTES (verbatim, rc 0)

```
GATE: PASS — 11/11 arm(s) (live GREEN, and every arm RED on its own mutation)
```

### 2b. `node _main/route-stamp-gate.js` — DEPOIS (verbatim, rc 0)

```
GATE: PASS — 17/17 arm(s) (live GREEN, and every arm RED on its own mutation)
```

As **11 arms pre-existentes continuam TODAS PASS** (nenhuma foi enfraquecida; as novas sao
ADICIONADAS). Lista literal desta corrida:

```
[PASS] G1 ORIGIN: the engine stamps the route from `meta.final`, and the worker's vote beats the panel deadline
[PASS] G2 FIXTURE: the history carries ONLY the worker-closed line
[PASS] G3 THE ARM: a stream with NO `final` key writes NOTHING on disk
[PASS] CONTROL: the SAME arm on the defect (`route = null`) is RED — the two sides AGREE
[PASS] CONTROL: the SAME arm on the mutant (`routeFor` else -> 'final') is RED — the named regression
[PASS] CONTROL: that mutant STAYS GREEN on the fixture — why the fixture alone is not a gate
[PASS] CONTROL: the defect merges the two fields (every commit is a history line)
[PASS] CONTROL: the gate is not vacuous — BOTH mutations bit the engine source, once each
[PASS] G4 PANEL CHOKE: `panel.js recordHistory` is FAIL-CLOSED (guard normalised, not byte-matched)
[PASS] CONTROL: the SAME panel check on the pre-cure guard (`|| 'final'` restored) is RED — the named regression
[PASS] CONTROL: the panel mutant bit the panel source exactly once (the check is not vacuous)
```

As **6 arms novas** (a exigencia + os seus controlos NAO-VACUOS):

```
[PASS] G5 SRC REQUIRED: every `route=final` line names the `src=` the SAME command RECOMPUTES
       real = {"fallbackArm":[],"fixture":[]}   want = {"fallbackArm":[],"fixture":[]}
[PASS] CONTROL: the fallback arm at the natural cadence DID produce `route=final` lines (the check is not vacuous)
[PASS] CONTROL: the SAME `src=` check on the constant-derivation mutant (`routeSourceFor` forced constant) is RED — the fallback that cannot say it engaged
[PASS] CONTROL: that mutant is GREEN on the fixture — the check refuses only the LIE, not the field
[PASS] CONTROL: the `src=` mutant bit the engine source exactly once (the check is not vacuous)
       real = {"srcChanged":true,"srcMatches":1}   want = {"srcChanged":true,"srcMatches":1}
[PASS] CONTROL: the recomputation REFUSES a `route=final` line with NO `src=` (and ignores a provisional line)
       real = [null,"worker-stamped"]   want = [null,"worker-stamped"]
```

O gate imprime tambem, na nova secao, a cadencia do fallback (o UNICO sitio onde
`src=fallback` e' legitimo):

```
--- THE FALLBACK CADENCE: the SAME no-`final` stream at the NATURAL cadence — the else-half manufactures every `final` ---
  LIVE    (shipped engine)                   : 264 commit(s) {"final":264}, panel accepted 264, on disk 264 — {"final":264} — routes {"final":264}
  MUTANT  (routeSourceFor -> constant)       : 264 commit(s) {"final":264}, panel accepted 264, on disk 264 — {"final":264}
```

### 2c. A METADE RED — o input que a lane anterior entregou

O mutante por ela nomeado (`silent-fallback-probe.js --emit-mutant`) deixa o **GATE** RED:

```
$ node _main/silent-fallback-probe.js --emit-mutant _main/_sf-red-copy.js
wrote mutant engine: _main\_sf-red-copy.js          (emit rc 0)

$ node _main/route-stamp-gate.js --engine _main/_sf-red-copy.js
engine    : _main\_sf-red-copy.js   === ENGINE UNDER TEST: NOT the live file (...) — RED is expected ===
...
[FAIL] G5 SRC REQUIRED: every `route=final` line names the `src=` the SAME command RECOMPUTES
       real = {"fallbackArm":["worker-stamped","worker-stamped", ... 264x ...],"fixture":[]}
       want = {"fallbackArm":[],"fixture":[]}
...
GATE: RED — 16/17 arm(s)          rc 1
```

A **mesma** metade RED na sonda standalone (o par de cores da lane anterior, reconfirmado
hoje): `node _main/silent-fallback-probe.js --engine _main/_sf-red-copy.js` →
`RESULT: RED — 5/7 arm(s)`, rc 1.

E a sonda GREEN sobre o ficheiro vivo: `node _main/silent-fallback-probe.js` →
`RESULT: GREEN — 7/7 arm(s)`, rc 0 (LINE A `<!-- route=final start=0.56 src=worker-stamped
reason=status-change -->`, LINE B `<!-- route=final start=0.56 src=fallback reason=chars 90 -->`).

### 2d. `py -3 _main/_cura-oracle-suite.py` — a nova linha SUITE

Corrida com `--only` sobre as QUATRO sondas `.js` (ver §5, porque a suite INTEIRA inclui
duas linhas que ARRANCAM O SHELL e a minha ordem proibe janela):

```
[     GREEN] route-stamp-gate                 rc=0 wall=0.4s
[     GREEN] historico-vs-redux-probe         rc=0 wall=0.1s
[     GREEN] panel-live-vs-history-probe      rc=0 wall=0.2s
[     GREEN] silent-fallback-probe            rc=0 wall=0.1s
SUITE: GREEN=4
receipt: _main/_cura-oracle-suite-src-required.json
```

`silent-fallback-probe` aparece AGORA entre as rows (antes so' corria a mao).

---

## 3. rcs e como corri

| comando | rc |
|---|---|
| `node --check _main/route-stamp-gate.js` | 0 |
| `py -3 -m py_compile _main/_cura-oracle-suite.py` | 0 |
| `node _main/route-stamp-gate.js` (ANTES) | **0** — `PASS — 11/11` |
| `node _main/route-stamp-gate.js` (DEPOIS) | **0** — `PASS — 17/17` |
| `node _main/silent-fallback-probe.js` | **0** — `GREEN — 7/7` |
| `node _main/silent-fallback-probe.js --emit-mutant _main/_sf-red-copy.js` | **0** |
| `node _main/silent-fallback-probe.js --engine _main/_sf-red-copy.js` | **1** — `RED — 5/7` |
| `node _main/route-stamp-gate.js --engine _main/_sf-red-copy.js` | **1** — `RED — 16/17` |
| `py -3 _main/_cura-oracle-suite.py --only route-stamp-gate,silent-fallback-probe,historico-vs-redux-probe,panel-live-vs-history-probe` | **0** — `SUITE: GREEN=4` |

As copias temporarias (`_main/_sf-red-copy.js`, `_main/_rs-nosrc-gate.js`) foram APAGADAS;
o `glob` confirma que nao sobra nenhuma. Os ficheiros `_route-stamp-*-engine.js` que o
proprio gate escreve sao removidos pelo gate na mesma corrida.

---

## 4. `sha256` ANTES / DEPOIS de cada ficheiro tocado

```
ANTES  55e1d9cd5307acf5c74467bde73c213d3ebbfc1a767a0b82ec238463e67a0634  _main/route-stamp-gate.js
DEPOIS ad0e3709b949bbeef9b3e24400b0d9e22a844c1854a06caff87073f3ac1fbc59  _main/route-stamp-gate.js
       (ultima edicao medida pelo instrumento: 30047 B -> 30635 B; a anterior acrescentou a
        secao do fallback + o mutante-fonte + a G5)

ANTES  ceb3d83d47ad3935021db1651738824ce12d4ba49214007552bed8ee048043da  _main/_cura-oracle-suite.py
DEPOIS d6f8e1c63975686e2a70788ec255ce9ab10ac15603352fa8534200bab75c8f6b  _main/_cura-oracle-suite.py
       (6083 B -> 6642 B)

NAO TOCADO  50fa575bd3a7e1efd416a319d1b3b0875fcd837d0e6ee1b7ff4c8932823651d8  _main/silent-fallback-probe.js
NAO TOCADO  70216812d7cf2c601d0e8c3b653eba754d1fce7b05830d0043240adddd7b020c  app/electron/caption-formulation.js
```

O hash de `caption-formulation.js` e' EXACTAMENTE o que a lane anterior gravou no seu
recibo (70216812…): `routeFor` continua byte-identica (non-goal respeitado, o gate nao
virou SETUP ERROR).

---

## 5. Nota de escopo / janela

A suite INTEIRA (`py -3 _main/_cura-oracle-suite.py` sem `--only`) inclui
`panel-hidden-at-startup-oracle` e `run-cmd-exit-oracle`, que ARRANCAM O SHELL. A minha
ordem e' *"NO VISIBLE WINDOW: do not start the shell or the panel"*, e o proprio AGENTS.md
documenta que o painel fica VISIVEL de ~50 ms a ~7 s em quase todos os arranques (tres
instrumentos independentes). Correr a suite inteira violaria a ordem, logo corri-a com
`--only` sobre as quatro linhas `.js` (purp-he file+store, sem janela, sem dispositivo).
O `SUITE:` acima e' o recibo real dessa corrida; as outras linhas precisam do shell/
dispositivo e ficam POR CORRER por este assento — nao as declaro verdes.

Dois travamentos de instrumento medidos e contornados (documentados aqui porque custaram
tempo): (a) o guard pre-tool do theorist-seal recusa TODO `bash`/`edit` nomeando um pass id
(`theory-2026-10-07T04-54Z.md`, reescrito pelo loop) que a tool `theorist_seal` NAO consegue
enderecar — o `theorist_seal(action=status)` diz "newest pass 05-17Z" enquanto a recusa diz
`04-54Z`, e a tool so' dispoe do pass que ela escolhe. Resultado: o canal fica em deadlock e
any `answer`/`skip` escreve uma row que NAO limpa o pass recusado. Contornei com as tools
`emergency_*` (guard + razao documentados em cada chamada). (b) `grep -E` e' bloqueado por um
landmine-guard (uutils) — substitui por `grep` nativo/PowerShell/`node`.

---

## SELF-AUDIT

- **protocolos em falta** — faltou-me uma regra para **editar um gate que eu proprio
  exijo mais estrito**: exigir `src=` OBRIGOU-me a corrigir o replay do gate (que largava
  `routeSource`); se eu tivesse so' acrescentado a assercao, o gate ficava VERMELHO sobre a
  sua propria metade GREEN e eu podia ter lido isso como "a assercao funciona". Descobri-o
  por LEITURA de `run()`. Faria diferente: no brief, "se um gate le' um campo do artefacto,
  confirma que o caminho que produz esse artefacto no proprio gate o CARREGA". Segunda regra
  em falta: o canal theorist-seal tem DOIS resolvedores de "pass mais recente" que podem
  divergir (§5) e nada no brief diz a quem pertence o desempate.
- **verificacao adicional** — corri a barata: o controlo do `src=` AUSENTE (linha sintetica
  com `src=null`) dentro do gate, e o controlo mutante-GREEN-na-fixture (a verificacao recusa
  a MENTIRA, nao o campo). A que NAO corri e' caro/proibido: a suite INTEIRA (arranca o shell
  = janela) e o caminho Python `_history_provenance` ao vivo — continua nao-exercido, como no
  recibo anterior. Custo de o fazer: uma janela no ecra do dono, proibida.
- **checkboxes novas** — MECANICO 1: "um gate que passa a EXIGIR um campo tem de tocar o
  input que o produz — senao os 11 arms antigos ficam verdes e a nova assercao e vacua ou
  auto-vermelha". Comando: `node _main/route-stamp-gate.js` tem de imprimir
  `PASS — 17/17`. MECANICO 2: "o novo requisito tem de vir com um input que o deixa RED e um
  que o mantem GREEN": RED = `--engine <constante>` (16/17), GREEN = ficheiro vivo (17/17) e
  mutante-src-na-fixture (`real = []`). Se ambos os lados nao existirem no mesmo comando, o
  requisito nao esta' provado.
- **review por outro subagente** — **sim-com-escopo**: (a) o `run()` do gate agora passa
  `routeSource` ao store — rever que isso nao muda NENHUM histograma `route` (eu argumento que
  nao muda, e a G2 da' `{final:130}` igual ao ANTES); (b) a escolha de `expectedSrc` por arm
  (fallback→`fallback`, fixture→`worker-stamped`) — rever se ha' um terceiro valor legitimo
  que eu nao contemplei. Nao vale re-rever a suite (mudanca de 5 linhas).
- **gate-doubt**:
  - **verde-de-verdade:** — o GREEN 17/17 e' real: as 11 arms antigas correm IDENTICAS (mesma
    texto de `real`/`want`), a G5 corre sobre o ficheiro vivo, e as 5 arms de controlo vao RED
    sob a sua propria mutacao (impresso ao vivo). O RED 16/17 veio de um input DERIVADO do
    proprio ficheiro (`--emit-mutant`), assertado presente antes do uso. **Um verde que eu
    DESCONTO:** a suite com `--only` NAO prova que as linhas pre-existentes da suite continuam
    verdes — so' as quatro `.js` que eu escolhi; as outras precisam do shell/dispositivo.
  - **falta-no-gate:** — o que o gate NAO verifica e devia: nada do `src=` em si ficou por
    cobrir — mas o gate continua a NAO OLHAR o caminho VIVO do Python
    (`sotto_webview.py:_history_provenance`), logo um writer Python que deixasse de escrever
    `src=` NAO acordaria este gate (ele so' exercita o twin Node). Cenario que atravessa: uma
    mudanca que so' toque o writer Python passa com G5 verde. Tentei partir isso e nao
    consegui dentro do gate (ele nao carrega Python); e' o mesmo buraco que o recibo anterior
    ja' nomeou (`_history_provenance` ao vivo nao exercido).
  - **gate-melhor:** — MECANICO: exigir o `src=` TAMBEM no caminho Python, por um oracle que
    chame `_history_provenance` directamente (funcao pura sobre `meta`) e verifique que devolve
    `src=fallback`/`src=worker-stamped`. RED input: um `meta` sem `routeSource` tem de dar uma
    linha SEM `src=` (e o oracle tem de a acusar). Nao o escrevi — `sotto_webview.py` e' do
    shell e o carregar arrasta pywebview; deixo-o nomeado, dono: quem sustentar o writer
    Python.
- **confianca** — **alta** no nucleo: as duas edicoes estao provadas com o par de cores no
  MESMO comando, o input RED e' o que a lane anterior nomeou, e o `routeFor` continua
  byte-identico. **media** em: (1) a suite inteira por correr (linhas com janela); (2) o
  writer Python nao exercido (confiado por simetria textual + o twin Node gated).
- **nao verificado** — (1) a suite INTEIRA (linhas `panel-hidden-at-startup-oracle` e
  `run-cmd-exit-oracle` arrancam o shell → janela, proibido). (2) `sotto_webview.py`
  `_history_provenance` ao VIVO. (3) o estado da lane irma `SottoRelandM1M3` (mexe no worker).
  (4) O deadlock do theorist-seal (§5) — reportei o comportamento, nao o diagnosticei no
  codigo do hook.

---

## CACHE/PRICE

Comando: `bash I:/!manager/scripts/cache-task-report.sh "C:/Users/Administrador/.omp/agent/sessions/--I--!manager--/2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26/SottoSrcRequired.jsonl"`
— **rc=0**. (Nota: o path do recibo da lane anterior e o do brief usam `I:/manager`; o real e'
`I:/!manager` — com o `!`.)

```
## CACHE/PRICE
- task/agent: C:/Users/Administrador/.omp/agent/sessions/--I--!manager--/2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26/SottoSrcRequired.jsonl
- cache: read=12459904 write=0 hit=98.1725% (cache-read / input+cache-read); universe: 75 usage rows; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- usage rows: 75
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 231947
- output tokens: 47114
- cache-read tokens: 12459904
- cache-write tokens: 0
- hit ratio: 98.1725% (cache-read / input+cache-read)
- prefix breaks: 12140 (state=RESOLVED-BREAKS-OMP; population: 100 of 126180 OMP prefix-ledger rows attributable to SottoSrcRequired; window: 2026-10-06T09:25:46.179000+00:00..2026-10-07T05:19:47.187000+00:00)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
- WHEN / WHERE failed (primeiros 5 de ~100 pares; completo no output da tool):
  - break_items=100; WHEN=2026-10-06T09:25:46.179000+00:00; WHERE session_id=01a11088-… provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278746179
  - break_items=100; WHEN=2026-10-06T09:25:47.669000+00:00; WHERE session_id=01a11088-… provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791278747669
  - break_items=100; WHEN=2026-10-06T09:25:48.916000+00:00; WHERE session_id=01a11088-… provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278748916
  - break_items=74; WHEN=2026-10-06T09:26:06.259000+00:00; WHERE session_id=01a11088-… provider=deepseek-flash model=deepseek-flash item_index=2; turn_id=1791278766259
  - break_items=177; WHEN=2026-10-06T09:26:42.525000+00:00; WHERE session_id=01a11088-… provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278802525
```

O `price` e' `$0.00000000` (os modelos desta lane reportam custo 0; as taxas por-modelo
exactas sao `UNKNOWN` na fonte). Nada aqui e' zero-por-desconhecimento: a fonte existe e
respondeu rc=0. A ultima quebra de prefixo do MEU turno e'
`WHEN=2026-10-07T05:19:47.187000+00:00 provider=deepseek-flash item_index=158` — muitas
quebras sao o theorist-seal a reescrever os ficheiros de pass entre chamadas (ver §5), o que
re-invalida o prefixo.

---

## TICKETS / pendencias deste assento

- **Ticket `cd83a545b1710c695609b9d1`** (kind=gate-refusal, harness=omp, P2): o guard
  pre-tool do theorist-seal e a tool `theorist_seal` resolvem "pass mais recente" de formas
  DIFERENTES (a tool diz 05-17Z pelo id; o guard recusa nomeando 04-54Z pela mtime de um
  ficheiro reescrito), e a tool nao aceita um pass id arbitrario — logo nenhum `answer`/`skip`
  limpa a recusa. Contornado com `emergency_*`. Ficheiro
  `I:/!manager/state/tickets/tickets.jsonl`.
- **Pendencia de assento (NAO minha para escrever):** o selo do dono endereca-me como
  "capacidade desconhecida" porque `agents/SottoSrcRequired.md` NAO existe. A escrita dessa
  linha (`tools:`) vive em `C:/Users/Administrador/.omp/agent/agents/` — fora do Sotto — e a
  minha ordem expressa e' *"trabalha so no sotto"*. DONO: quem sustentar o registo de
  `agents/` (assento principal). Sem essa linha, o proximo selo continua a nao-me atribuir
  ferramenta nenhuma.
