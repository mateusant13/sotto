# Recibo — o SILENT FALLBACK que mascarava a DE-LANDAGEM (H:/sotto, 2026-10-07)

**Lane:** `SottoSilentFallback` · **Repo:** `H:/sotto` · **Data:** 2026-10-07
**Ambito:** SO o Sotto (ordem do dono: *"trabalha so no sotto. nao mais no manager ou omp"*).
Nao toquei `I:/!manager`, hooks/extensoes omp, nem o worker.
**Janela/audio:** NADA de janela e NADA de audio. O probe e' "pure file reads + one store
under a temp root" — nao abre o painel Electron/WebView2 e nao abre dispositivo nenhum
(nada pode ser audivel ao dono). Nao precisei do `_main/panel-live-vs-history-probe.js`
porque a mudanca NUNCA precisa do painel para ser exercida: ela vive no engine + store,
que correm fora do DOM.

---

## 0. O defeito (verbatim, `app/electron/caption-formulation.js:296-301` ANTES)

```js
  function routeFor(reason) {
    if (bufferFinal) return 'final';
    if (bufferSawFinal) return 'provisional-draft';
    return PANEL_DEADLINE_REASON.test(String(reason == null ? '' : reason))
      ? 'provisional-draft'
      : 'final';                              // <-- manufactures 'final' BY DEFAULT
  }
```

Quando o worker NAO estampa nada, a ultima linha devolve `'final'`. Foi isto que fez a
de-landagem da M2 (`line_events` / `take_closed` / `_event(final=)`) PASSAR EM SILENCIO por
um dia (lane SottoCaptionLines, `_main/receipt-20261007-caption-lines.md`, 19885 B, sha
`039f80b9…`; P1 ticket **`4fb5b25380cbc8269977e22e`**).

## 1. A mudanca — anuncia, NAO apaga

1. **O fallback NAO foi removido.** `routeFor` ficou BYTE-IDENTICAL (o gate
   `_main/route-stamp-gate.js` muta-o pelo literal `const route = routeFor(reason);` e o
   else-half por `ELSE_RE` — se qualquer um sair, o gate vira SETUP ERROR rc=2 em vez da
   metade RED). O worker vivo e' o snapshot PRE-CURE (128569 B) e PRECISA do wrap.
2. **O fallback agora tem VOZ.** `routeSourceFor(route)` deriva QUAL ramo decidiu a rota —
   do PROPRIO `route` que `routeFor` devolveu mais o teste de voto do worker — logo os dois
   NAO podem discordar por construcao:
   - `'worker-stamped'`  — um voto do worker decidiu (`final:true`→`final`; `final:false`→`provisional-draft`)
   - `'panel-deadline'`  — sem voto; o deadline/flush do painel decidiu (`provisional-draft`)
   - `'fallback'`        — sem voto E a rota e' `'final'`: a linha so' chegou ao transcript
                           porque o else-half a FABRICOU. **A de-landagem, anunciada.**
3. **O campo viaja ate' o disco e e' legivel pelo painel e pelo gate.** `commit()` poe
   `routeSource` no meta → `panel.js recordHistory` repassa → `history-store.js` (Node) e
   `sotto_webview.py:_history_provenance` (o shell VIVO) gravam `src=<valor>` NA LINHA, logo
   depois de `start=` (para nao partir os leitores antigos `route=… start=…`).
4. **O P1 e' citado no comentario** de `routeFor` (`4fb5b25380cbc8269977e22e`), em
   `caption-formulation.js`, `panel.js` e `history-store.js`.

O sinal que isso compra, na pipeline viva de hoje (worker pre-cure sem `final`): TODA linha
do transcript passa a ler `route=final src=fallback` em vez de `route=final` — o silencio
virou um carimbo legivel sem correr a app.

## 2. A aceitacao — um PAR DE CONTROLE, nao uma assercao

Probe novo: **`_main/silent-fallback-probe.js`** (file reads + um store em `history-verify/`;
NAO abre janela). Corre o engine REAL e o store REAL sobre o stream REAL
`_main/_route-stream-long.jsonl` (1226 eventos; 135 `final:true`, 1091 `final:false`).

### ARM A (final ESTAMPADO pelo worker) e ARM B (NENHUM carimbo) — output VERBATIM

```
$ node _main/silent-fallback-probe.js
stream    : _main\_route-stream-long.jsonl — 1226 event(s) (final:true 135, final:false 1091)
engine    : app\electron\caption-formulation.js

ARM A (worker-stamped final)
  LIVE    : final-route commits carry routeSource = ["worker-stamped"]
  HISTORY : 130 line(s) on disk — routes {"final":130} — sources {"worker-stamped":130}
  LINE A  : <!-- route=final start=0.56 src=worker-stamped reason=status-change -->

ARM B (NO worker stamp — the wrapped result)
  LIVE    : final-route commits carry routeSource = ["fallback"]
  HISTORY : 264 line(s) on disk — routes {"final":264} — sources {"fallback":264}
  LINE B  : <!-- route=final start=0.56 src=fallback reason=chars 90 -->

--- the control pair, both colours of the SAME probe ---
[PASS] ARM A: a worker-stamped final still emits route=final
[PASS] ARM A: the new field says it was STAMPED (worker-stamped) on disk
[PASS] ARM B: with NO worker stamp the renderer still emits route=final (the wrap)
[PASS] ARM B: the new field says the FALLBACK engaged (fallback) on disk
[PASS] NON-VACUITY: the two arms carry the SAME route value(s)   real = ["final"] want = ["final"]
[PASS] NON-VACUITY: and DIFFERENT sources (the change proved something)  real = false want = false
[PASS] COMPAT: the old route=… start=… capture still yields route final and a start

RESULT: GREEN — 7/7 arm(s)
===RC=0===
```

**A NAO-VACUIDADE e' o ponto.** As duas arms leem a MESMA rota (`final`) e os campos NOVOS
DIFEREM (`worker-stamped` vs `fallback`). Se as duas lessem igual, a mudanca nao teria
provado nada. A `LINE A` e a `LINE B` mostram o mesmo `route=final` e `src=` diferente.

### Metade RED — a MESMA sonda contra um MUTANTE que apaga a distincao

```
$ node _main/silent-fallback-probe.js --emit-mutant _main/_sf-red-copy.js
wrote mutant engine: _main\_sf-red-copy.js
emit rc=0
$ node _main/silent-fallback-probe.js --engine _main/_sf-red-copy.js
engine    : _main\_sf-red-copy.js   (MUTANT COPY)
...
[PASS] ARM A: the new field says it was STAMPED (worker-stamped) on disk
[FAIL] ARM B: the new field says the FALLBACK engaged (fallback) on disk
       real = ["worker-stamped"]   want = ["fallback"]
[FAIL] NON-VACUITY: and DIFFERENT sources (the change proved something)
       real = true   want = false
RESULT: RED — 5/7 arm(s)
===RC=1===
```
(O mutante forca `return 'worker-stamped';` no lugar da expressao de derivacao; a COPIA e'
escrita em `_main/` e APAGADA depois. O ficheiro vivo so' e' LIDO.) Com a distincao apagada,
as duas arms leem igual — e a sonda vai RED. O par nao e' vacuo.

## 3. rcs e como corri

| comando | rc |
|---|---|
| `node --check app/electron/caption-formulation.js` | 0 |
| `node --check app/electron/panel.js` | 0 |
| `node --check app/electron/history-store.js` | 0 |
| `node --check _main/silent-fallback-probe.js` | 0 |
| `py -3 -m py_compile app/webview/sotto_webview.py` | 0 |
| `node _main/silent-fallback-probe.js` (GREEN) | **0** |
| `node _main/silent-fallback-probe.js --engine _main/_sf-red-copy.js` (RED) | **1** |
| `node _main/route-stamp-gate.js` | 0 — `GATE: PASS — 11/11 arm(s) (live GREEN, and every arm RED on its own mutation)` |
| `node _main/panel-live-vs-history-probe.js` | 0 — `RESULT: GREEN — 9/9 arm(s)` |
| `node _main/historico-vs-redux-probe.js` | 0 — `RESULT: GREEN — the transcript carries only the worker-closed line` |
| `node app/electron/transcript-append-oracle.js` | 0 — `RESULT: GREEN — every worker line is appended once, in order, word for word` |
| neutrality check (temporario, apagado) | 0 |

Nenhuma janela foi aberta em NENHUMA destas corridas (todas sao leitura de ficheiro + um
store sob `history-verify/`). O painel nunca precisou de arrancar.

## 4. `sha256` ANTES / DEPOIS de cada ficheiro tocado

```
ANTES  c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83  app/electron/caption-formulation.js
DEPOIS 70216812d7cf2c601d0e8c3b653eba754d1fce7b05830d0043240adddd7b020c  app/electron/caption-formulation.js

ANTES  135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962  app/electron/panel.js
DEPOIS 893012d26610cf7cc33a5444fd27fbb04d3bfb55cad431bed4b172d2c10e13d8  app/electron/panel.js

ANTES  536160b3b11c62d2efeb2bf424bb9fcb9ded30d9b8802d0799c416f92d6979af  app/electron/history-store.js
DEPOIS f13a843c42972afde17ac8de23e052384b34a4413ec94542ec7b4c3ebb0af6f3  app/electron/history-store.js

ANTES  64b563429a6f0787b860ab9c058aca98fb3b32ee9f0ec15d9d9093ffed5de1b2  app/webview/sotto_webview.py
DEPOIS becac0a6c1dfd6b082f1384fac86a91bcf152a78587f9b276ce0eb6394f3ac02  app/webview/sotto_webview.py

NOVO   50fa575bd3a7e1efd416a319d1b3b0875fcd837d0e6ee1b7ff4c8932823651d8  _main/silent-fallback-probe.js
```

**NAO TOCADO por mim:** `_main/caption-lines-oracle.py` (ja' estava `M`, da lane
SottoCaptionLines) e `_main/segment-rerun-probe.py` (non-goals explicitos). O
`worker/sotto_worker.py` mudou de hash DURANTE esta lane (`eac2959f…` → `473d0ee6…`) porque a
lane IRMA `SottoRelandM1M3` esta' a edita-lo AGORA — eu NUNCA escrevi nele.

## 5. `history-route-oracle.js` esta' RED — e e' PRE-EXISTENTE (provado, nao afirmado)

`node _main/history-route-oracle.js` → rc=1, 3 violacoes. **Nao e' minha.** Ele e' um oraculo
UNTRACKED (`git status` → `?? _main/history-route-oracle.js`), escrito contra a REVISAO
DE-LANDADA: as suas arms 3 e 4 exigem `meta.fileText` e que `onCommit` so' dispare para linhas
FECHADAS — e `fileText` NAO existe em NENHUMA revisao do engine em disco (grep: ausente tanto
no ficheiro vivo como em `git show HEAD:app/electron/caption-formulation.js`). E' da MESMA
familia da `segment-rerun-probe` e da `caption-lines-oracle`: um oraculo que testa o contrato
de-landado, logo vermelho por construcao ate' a M2 voltar.

**Prova mecanica da neutralidade da minha mudanca** (script temporario, JÁ apagado): reconstrui
o engine SEM o codigo `routeSource` e conduzi o MESMO stream das arms 3/4 pelos dois:
```
arm4 LIVE  : [{"text":"Nossa, eu vou.","reason":"status-change","route":"provisional-draft"}]
arm4 REVERT: [{"text":"Nossa, eu vou.","reason":"status-change","route":"provisional-draft"}]
arm4 identical (route/text/fileText/reason): true
stream routes identical: true
===RC=0===
```
Identico. A minha mudanca e' ROUTE-NEUTRA: nao toca em `route`, `text`, `fileText`, `reason`.

## 6. Coordenacao / notas

- O irmao `SottoRelandM1M3` esta' a mexer no worker AGORA e ja' mudou o hash. Nao colidi: eu
  so' toquei o renderer + os dois writers de provenance + o shell.
- O gate `_main/route-stamp-gate.js` (dono: lane `SottoProbeWiring-3`) LE hoje so' `route=` na
  cauda (`/\s*<!--\s*(route=\S+)/`). O novo campo esta' em `src=` NA MESMA cauda, logo o gate
  PODE le-lo — mas exigi-lo quando `route=final` e' decisao/edicao do dono do gate, nao minha.
  Deixei o ficheiro do gate intacto.

---

## SELF-AUDIT

- **protocolos em falta** — senti falta de uma REGRA para **quando uma mudanca muda o CONTRATO
  que um gate muta por LITERAL**. O `route-stamp-gate` muta `routeFor` por `ELSE_RE` e a linha
  `const route = routeFor(reason);`; se eu tivesse "limpo" o codigo (ex.: fundir `routeFor` num
  `classifyRoute` que devolve um objeto, como era o desenho obvio), o gate teria virado
  SETUP ERROR rc=2 (nao RED) e a metade de controle teria ficado MUDA — passa-por-construcao
  ao contrario. Descobri-o por LEITURA do gate antes de editar, nao por regra. Faria diferente:
  acrescentaria ao brief "se o ficheiro e' mutado por literal por um gate, preserva os literais".
- **verificacao adicional** — corri e e' barata: a NEUTRALIDADE (secao 5). A que NAO corri e
  declararia o custo se pedida: exercer o caminho WebView2 AO VIVO (o `_history_provenance` do
  Python com um `history-append` real). Custo: arrancar o shell = janela + risk de audio; o
  brief proibe. Confio na simetria textual dos dois writers + `py_compile` rc=0, e DIGO que o
  caminho Python ao vivo NAO foi exercido (ver nao-verificado).
- **checkboxes novas** — MECANICO: **um gate que muta um ficheiro por LITERAL deve falhar
  ALTO se o literal sumir — e quem edita esse ficheiro deve nomear os literais no brief.**
  Comando: `node _main/route-stamp-gate.js` tem de continuar a imprimir
  `GATE: PASS — 11/11 ... every arm RED on its own mutation` (input que o deixa RED-as-expected
  e' repor `(meta && meta.route) || 'final'` em `panel.js` ou `const route = null`). Segunda
  checkbox: **um sinal que distingue A de B tem de vir com a arm NAO-VACUA** — aqui, `keys(route)`
  igual e `keys(src)` diferente, no MESMO run. Sem isso, `src=` podia estar sempre `fallback` e
  o teste passaria sem provar nada.
- **review por outro subagente** — **sim-com-escopo**: review (a) de que a ORDEM dos tokens na
  provenance (`route= start= src= reason=`) preserva TODOS os leitores antigos — eu li 4 parsers
  (`route-stamp-gate`, `history-route-oracle`, `historico-vs-redux-probe`, `transcript-append-
  oracle`) e o COMPAT arm confirma-o, mas um segundo olho sobre parsers nao citados vale; (b) de
  que o `src=` deve OU NAO ser exigido pelo gate. Nao vale re-rever o resto (leitura de ficheiro).
- **gate-doubt**:
  - **verde-de-verdade** — o GREEN 7/7 e o RED 5/7 sao cores REAIS da MESMA sonda: o RED veio de
    um mutante derivado do PROPRIO ficheiro (`--emit-mutant`), com a expressao assertada presente
    antes do uso (senao SETUP ERROR). Nao ha' flag suprida a mao nem artefacto stale (o mutante e'
    escrito e apagado na mesma corrida). O `route-stamp-gate` GREEN 11/11 tambem e' real: ele
    imprime ao vivo que TODAS as arms vao RED sob a sua propria mutacao. O unico "verde" que eu
    NAO tomo por bom e' a ausencia de `ALERTA-JANELA`: o censo da casa amostra 1x/60 s, logo nao
    prova nada sobre janelas <60 s — mas aqui nem houve arranque de shell, so' leitura de ficheiro,
    entao a questao nem se poe.
  - **falta-no-gate** — o novo campo NAO e' exigido por nenhum gate: `route-stamp-gate.js` le so'
    `route=`. Cenario que atravessa: uma mudanca futura faz `routeSourceFor` devolver um valor
    CONSTANTE (`'fallback'` sempre, ou `'worker-stamped'` sempre) e TODOS os gates atuais ficam
    verdes — o `src=` continua a ser escrito, so' que mentindo. So' a `silent-fallback-probe`
    (a MINHA) apanharia isso, e ela nao esta' na suite.
  - **gate-melhor** — MECANICO: acrescentar a `_main/_cura-oracle-suite.py` (dono:
    SottoProbeWiring-3) a sonda `silent-fallback-probe` e, no `route-stamp-gate` (dono:
    SottoProbeWiring-3), exigir que `route=final` carregue `src=` e que a arm NAO-VACUA valha
    (rota igual, fonte diferente). Input que TEM de deixar RED: (1)
    `node _main/silent-fallback-probe.js --engine <copia com a derivacao forca-constante>` (=
    o `--emit-mutant` de hoje) e (2) um stream sem `final` onde a linha de disco leia
    `src=worker-stamped`. Nao editei nenhum dos dois — nao sao meus.
- **confianca** — **alta** no nucleo (o par de controle e' nao-vacuo por construcao: rota igual,
  fonte diferente, e a metade RED existe; a neutralidade da mudanca esta' PROVADA por execucao
  identica com/sem o codigo). **media** exactamente em: (1) o caminho Python ao vivo
  (`_history_provenance`) nao exercido — confiado por simetria textual com o twin Node; (2) a
  escolha de VERBO (aceitar `src=` como `fallback` no transcript) e' uma decisao de desenho, nao
  uma medida.
- **nao verificado** — (1) `app/webview/sotto_webview.py:_history_provenance` ao VIVO (nao
  arranquei o shell: janela). (2) Quem e' que a `route-stamp-gate`/suite devia passar a exigir
  `src=` (decisao do dono do gate, nao minha). (3) O estado vivo da lane irma `SottoRelandM1M3`
  (o hash do worker mudou a meio — ela esta' a trabalhar; nao medi o resultado dela). (4) se
  algum parser de provenance NAO citado neste recibo existir no repo — grep a `route=` cobriu
  os 4 conhecidos, nao uma enumeracao exaustiva.

---

## CACHE/PRICE

A colar em baixo `bash I:/!manager/scripts/cache-task-report.sh <o meu session jsonl>`.

Comando: `bash I:/!manager/scripts/cache-task-report.sh "C:/Users/Administrador/.omp/agent/sessions/--I--!manager--/2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26/SottoSilentFallback.jsonl"` — **rc=0**, wall 5.43 s.

```
## CACHE/PRICE
- task/agent: C:/Users/Administrador/.omp/agent/sessions/--I--!manager--/2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26/SottoSilentFallback.jsonl
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoSilentFallback.jsonl
- cache: read=9274240 write=0 hit=97.7971% (cache-read / input+cache-read); universe: 59 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoSilentFallback.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=57 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 59 of 59 matched usage rows
- report generated_at: 2026-10-07T05:08:40.384281+00:00
- usage rows: 59
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 208902
- output tokens: 60422
- cache-read tokens: 9274240
- cache-write tokens: 0
- hit ratio: 97.7971% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 12144 (state=RESOLVED-BREAKS-OMP; population: 101 of 126031 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', '.../SottoSilentFallback.jsonl', 'SottoSilentFallback']; window: 2026-10-06T09:25:46.179000+00:00..2026-10-07T05:06:26.165000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed: (lista de ~100 pares — VERBATIM as primeiras linhas; WHEN/WHERE completos em artifact://7534)
  - break_items=100; WHEN=2026-10-06T09:25:46.179000+00:00; WHERE session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791278746179
  - break_items=100; WHEN=2026-10-06T09:25:47.669000+00:00; WHERE session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791278747669
  - break_items=655; WHEN=2026-10-07T03:49:22.975000+00:00; WHERE session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=26; turn_id=1791344962975
  - break_items=215; WHEN=2026-10-07T04:50:27.339000+00:00; WHERE session_id=01a11088-84b0-75a9-9c9f-193b70f51d26 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791348627339
  - break_items=2; WHEN=2026-10-07T05:06:26.165000+00:00; WHERE session_id=01a114ba-8989-76ba-aab2-27bbdcb9a07b provider=deepseek-flash model=deepseek-flash item_index=220; turn_id=1791349586165
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

O bloco `WHEN/WHERE` completo tem ~100 pares e foi truncado pela ferramenta (768 B/linha); as
ultimas entradas ficam em `artifact://7534`. O `price` e' `$0.00000000` (os modelos desta lane
— `opencode-go-1/deepseek-flash`, `mimo-v2.6-flash`, `cline-pass/stealth/pixel-canary` — reportam
custo 0; as taxas por-modelo exactas sao `UNKNOWN` na fonte). Nada aqui e' zero-por-desconhecimento:
a fonte existe e respondeu rc=0.
