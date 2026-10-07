# Recibo — o campo LIVE e o campo HISTORY do painel: mesma fonte? (H:/sotto, 2026-10-07)

**Lane:** `SottoLiveVsHistory` · **Repo:** `H:/sotto` · **Data:** 2026-10-07
**Ambito:** SO o Sotto (ordem do dono: *"trabalha só no sotto. nao mais no maanger ou omp"*).
**Janela/audio:** NADA. Nao arranquei o shell nem o painel (nao ha janela, nao ha audio); so'
leitura de ficheiro + `node` sobre o motor/store reais, em roots descartaveis. Sem
`VoiceMeeter`/saida default.

Ordem do dono, verbatim:

> *"o live nvidia do painel do sotto é pra ser o nvidia funcionando, enquanto o historico nao é
> pra ser NUNCA o historico do live nvidia. é pra ser do parakeet redux. e eu to vendo q nao ta
> desse jeito"*

---

## 0. VEREDICTO

| campo | o que o dono espera | o que esta' no disco HOJE (antes desta lane) | veredicto |
|---|---|---|---|
| **LIVE** (`panel.html:166` "Live · NVIDIA", `#caption-list`) | o nvidia a funcionar | alimentado pelo motor nvidia (nemotron) — **sim** | **TRUE** |
| **HISTORY** (`panel.html:109` "History · Redux", `#history-list`) | **NUNCA** o live nvidia; Parakeet Redux | alimentado pelo **proprio caminho LIVE** (`addCaption` -> `recordHistory`) | **FALSE** — a observacao do dono esta' CERTA |

**(a) O campo LIVE e' o caminho nvidia — TRUE.** O motor que pinta a caixa de baixo e'
`app/electron/caption-formulation.js`, alimentado pelos captions do worker nvidia; o
`worker/config.json` `model.dir` e' `models/nemotron-3.5-asr-streaming-0.6b-int8`, e o proprio
stream gravado que o oracle usa (`_main/_route-stream-long.jsonl`) declara
`"model":"nemotron-3.5-asr-streaming-0.6b-int8"` em cada evento (medido, §2).

**(b) O HISTORY era a propria historia do LIVE nvidia — FALSE, e e' o defeito que o dono viu.**
Um unico produtor alimentava os dois campos: a funcao que PINTA a caixa
(`panel.js:175 addCaption`) chamava a que ESCREVE o historico (`panel.js:207 recordHistory`) na
sua ultima linha util. A guarda de rota (`panel.js:336 if (route !== 'final') return;`) so'
filtrava o PROVISORIO; as linhas `route=final` que passavam vinham do **mesmo motor nvidia**, logo
o HISTORY era, em texto, o fecho do live nvidia — exactamente o que o dono proibe.

**(c) `PARAKEET REDUX` NAO EXISTE NO DISCO.** Sem pesos, sem call site (`glob`/`grep` sobre
`H:/sotto` nao encontram nada). O PLANO existe e e' do dono (`README.md:20`, `:24`, `:54`):
streaming **Nemotron** a gravar, **Parakeet Redux** (`moondream/parakeet-redux` via
`transcribe.cpp`) para a transcricao canonica DEPOIS. Uma lane anterior registou o mesmo limite
(`docs/audit/historico-vs-redux.md` §0(b), `_main/panel-live-vs-history-20261006.md` §6). **Nao se
liga o que nao existe:** esta lane landa o CORTE (o HISTORY recusa a fonte LIVE) e NOMEIA o motor
EM FALTA (§4). A sonda `_main/segment-rerun-probe.py` (2a passagem pelo MESMO modelo) permanece a
canario da ausencia desse motor batch.

---

## 1. `file:line` de cada campo — ANTES desta lane

| campo | rotulo/DOM | fonte do TEXTO (cadeia) |
|---|---|---|
| **LIVE** (nvidia) | `panel.html:166` `<span class="history__label">Live &middot; NVIDIA</span>` -> `panel.html:183` `<ol id="caption-list">` | `panel.js:175 addCaption()` (pinta) <- `panel.js:88 onCommit` <- `panel.js:160 wireCaptions` `bridge.onCaption` <- shell `on_worker_caption` <- worker `sotto_worker.py` (motor nvidia: `worker/config.json` `model.dir=models/nemotron-3.5-asr-streaming-0.6b-int8`) <- motor `caption-formulation.js:408 onCommit(line, reason, {route, start, routeSource})` |
| **HISTORY** ("redux") | `panel.html:109` `<span class="history__label">History &middot; Redux</span>` -> `panel.html:157` `<ol id="history-list">` | `panel.js:207 recordHistory(text, reason, meta)` — **chamada DENTRO de `addCaption`** — -> `panel.js:303 recordHistory()` -> `panel.js:382 historyApi.append(body, options)` -> store: `history-store.js:95 append()` (Electron) / `sotto_webview.py:2148 history_append()` (WebView2) -> ficheiro -> lido de volta por `historyApi.tail` (`panel.js:282 loadHistory`) |

**Um produtor, dois campos.** A linha que faz o HISTORY ser o historico do LIVE:

```
panel.js:175   function addCaption(text, reason, meta) {     <- PINTA o LIVE (#caption-list)
panel.js:207     recordHistory(text, reason, meta);          <- ESCREVE o HISTORY (#history-list)
```

`grep -rn "historyApi.append\|\.append(body" app/electron/panel.js` -> **um unico** call site do
store (`panel.js:382`), dentro de `recordHistory`; e `recordHistory` so' e' chamada de um sitio
(`panel.js:207`, dentro do LIVE). Nao ha segundo produtor.

---

## 2. MEDICAO — o oracle da fonte, o MESMO comando nas duas cores

A classe de defeito desta lane NAO e' "o HISTORY aceita o provisorio" (isso e'
`_main/historico-vs-redux-probe.js`, ja' GREEN e NAO contradito aqui). E' "o HISTORY e' a fonte
LIVE". Oracle NOVO: `_main/live-vs-history-source-oracle.js` (executa a funcao REAL de decisao e o
store REAL; sem janela).

```
$ cd H:/sotto && node _main/live-vs-history-source-oracle.js          # rc=0
stream    : _main\_route-stream-long.jsonl — 1226 event(s), model=nemotron-3.5-asr-streaming-0.6b-int8
source    : app\electron\history-source.js   (LIVE_PRODUCER=live CANONICAL_PRODUCER=redux)
panel     : app\electron\panel.js   route-guard=true uses-isCanonicalLine=true

AS SHIPPED (route=final AND canonical producer) on the LIVE nvidia commits
  LIVE    : 1221 commit(s) handed to the panel (the bottom box paints all)
  HISTORY : 0 accepted by the choke point, on disk 0 — {}

SAME commits stamped producer:'redux' (the canonical path — is it OPEN?)
  LIVE    : 1221 commit(s) handed to the panel (the bottom box paints all)
  HISTORY : 130 accepted by the choke point, on disk 130 — {"final":130}

BEFORE (pre-cure permissive: (route||'final')==='final') on the LIVE commits
  LIVE    : 1221 commit(s) handed to the panel (the bottom box paints all)
  HISTORY : 1221 accepted by the choke point, on disk 1221 — {"null":1221}
...
RESULT: GREEN — 13/13 arm(s)
```

**O PAR DE CONTROLO (exigencia de aceitacao) esta' nas tres linhas do meio:**
* `AS SHIPPED` — o MESMO stream, os MESMOS 1221 commits entregues a caixa LIVE, e o HISTORY
  **0** linhas. Os dois campos **JA' NAO** tiram da mesma fonte.
* `producer:'redux'` — os MESMOS commits; o HISTORY **130** linhas (`route=final`). O caminho
  canonico esta' **ABERTO**, nao e' um beco sem saida — so' nao tem motor que o alimente hoje.
* `BEFORE` — o choke point pre-cura + o motor vacuoso (`route=null`): **1221 == 1221**, os dois
  campos sao UM — o defeito que o dono viu. E' o controlo que prova que o check NAO e' vacuo
  (o `CONTROL: the shipped and pre-cure HISTORY counts DIFFER` passa com 0 vs 1221).

### 2b. As sondas da casa continuam GREEN (a cura de ontem nao foi tocada)

```
$ node _main/historico-vs-redux-probe.js        # rc=0 — GREEN; on disk 130 {"final":130}
$ node _main/panel-live-vs-history-probe.js     # rc=0 — GREEN 9/9 arm(s)
$ node _main/route-stamp-gate.js                # rc=0 — GATE: PASS — 17/17 arm(s)
```

`route-stamp-gate`'s G4 continua a ler `panel.js recordHistory` como FAIL-CLOSED (uma unica
`const route = …;` sem `'final'`, e o teste `if (route !== 'final') return;` presente) — a guarda
de rota NOVA (fonte) e' ADICIONADA, nunca substitui a antiga.

---

## 3. A CURA (o menor corte que faz o HISTORY uma fonte DIFERENTE do LIVE)

Nao se pode mexer em `worker/**`, no gate (`_main/route-stamp-gate.js`), nas sondas
(`_main/*probe.js`) nem na metade `route` de `caption-formulation.js` (todas de lanes que
landaram hoje). E nao se pode pôr a guarda no STORE: as sondas de hoje escrevem no store com
`{source:'live'}` e **exigem aceitacao** — uma guarda de fonte no store deixaria essas sondas
VERMELHAS. Logo a separacao tem de ser no CHOKE POINT do painel, que e' o unico escritor
(`panel.js:382`).

**1) `app/electron/history-source.js` (NOVO, 3708 B)** — o predicado da fonte, DOM-free (para o
oracle executar a FUNCAO real, nao um regex), com o duplo export de `caption-formulation.js`:

```js
const LIVE_PRODUCER = 'live';        // a fonte que o HISTORY pode NUNCA tomar
const CANONICAL_PRODUCER = 'redux';  // a fonte a que o HISTORY e' RESERVADO
function isCanonicalLine(meta) { return producerOf(meta) === CANONICAL_PRODUCER; }
```

Recusa **live**, recusa **ausente/desconhecido** (fail-closed); aceita **redux**.

**2) `app/electron/panel.html:200`** — `<script src="history-source.js"></script>` antes de
`panel.js` (o painel e' um `<script>` simples; `history-source.js` precisa de existir antes de a
`recordHistory` o chamar).

**3) `app/electron/panel.js`** — a guarda ADICIONADA no choke point (a de rota fica intacta):

```js
panel.js:335   const route = meta && meta.route;
panel.js:336   if (route !== 'final') return;
               // OWNER 2026-10-07 — a SEGUNDA metade: o transcrito canonico e' OUTRA FONTE.
panel.js:349   const isCanonical = window.SottoHistorySource
panel.js:350     && window.SottoHistorySource.isCanonicalLine;
panel.js:351   if (!isCanonical || !isCanonical(meta)) return;
```

e o `source` escrito na linha deixa de mentir (`'live'` -> `'redux'`, `panel.js:364`); e o estado
vazio do feed passa a dizer a verdade (`panel.js:412-415`).

**Porque isto e' o MINIMO e e' honesto:** o caminho LIVE (`addCaption`) continua a chamar
`recordHistory`; a chamada agora e' recusada porque a meta do motor nvidia NUNCA declara
`producer:'redux'`. O HISTORY nao pode mais ser alimentado pelo LIVE — por construcao — e o
caminho canonico fica ABERTO para o motor batch (provado no par de controlo). Nao se inventou um
motor: a sonda da casa para o mesmo assunto continua a poder ficar VERMELHA (§4).

---

## 4. O QUE FALTA (nomeado, nunca tapado)

1. **O MOTOR `Parakeet Redux` NAO EXISTE no disco nem tem call site.** `moondream/parakeet-redux`
   (batch, ternary/1.58-bit, 25 idiomas incl. pt, CC-BY-4.0) corre por `transcribe.cpp` segundo o
   plano do dono (`README.md:20-24`). **Dono do fecho:** quem sustentar o ASR batch — tem de
   produzir uma linha com `producer:'redux'` e entrega-la ao painel (no arm WebView2, por uma
   feed nova do shell; no arm Electron, pelo mesmo bridge). **Ate' la', o HISTORY fica VAZIO e
   DIZ-O** — nao ha' motor que o encha, e um campo vazio e' honesto, ao contrario de um campo com
   o texto do live nvidia.
2. **O STORE continua a aceitar `route=final` de qualquer `source`.** As sondas de hoje
   (`historico-vs-redux-probe`, `panel-live-vs-history-probe`, `route-stamp-gate`) EXIGEM isso
   (escrevem com `source:'live'` e esperam aceitacao), logo a guarda de fonte NAO pode viver
   la'. A separacao e' no painel, que e' o unico escritor (`panel.js:382`); um escritor NOVO que
   contornasse `recordHistory` reabriria o buraco. Nomeado como `falta_no_gate` na SELF-AUDIT.

---

## 5. `sha256` ANTES / DEPOIS de cada ficheiro tocado

```
ANTES  893012d26610cf7cc33a5444fd27fbb04d3bfb55cad431bed4b172d2c10e13d8  25001 B  app/electron/panel.js
DEPOIS 9099fb3c513408645d8ca5025cb65b1b215123baab03b7703085eae775686bd7  26388 B  app/electron/panel.js

ANTES  6683e6d8d47a29d1104339253f368216c71123663995131053c116e2c5c6438f   8634 B  app/electron/panel.html
DEPOIS 672cb186e3ca7a0cdc2c1648af7e023261c2235f65efc749950bb652a86273b4   8907 B  app/electron/panel.html

NOVO (nao existia)                                                        3708 B  app/electron/history-source.js
DEPOIS 75d175863c286a7aa6c105c7e0258a93d4d8ec078208d18438651981c02bd915   3708 B  app/electron/history-source.js

NOVO (nao existia)                                                       12517 B  _main/live-vs-history-source-oracle.js
DEPOIS 0577e6a6836da76da1adbe4716e3a541d3398f82480f72124e29ea1dedb5f70b  12517 B  _main/live-vs-history-source-oracle.js

NAO TOCADO  f13a843c42972afde17ac8de23e052384b34a4413ec94542ec7b4c3ebb0af6f3   9150 B  app/electron/history-store.js
NAO TOCADO  70216812d7cf2c601d0e8c3b653eba754d1fce7b05830d0043240adddd7b020c  29012 B  app/electron/caption-formulation.js
NAO TOCADO  ad0e3709b949bbeef9b3e24400b0d9e22a844c1854a06caff87073f3ac1fbc59  30635 B  _main/route-stamp-gate.js
```

Os tres NAO-TOCADOS sao o `git status`/`sha256` a provar que os non-goals foram respeitados
(`caption-formulation.js` e o gate mantem o sha que as lanes de hoje gravaram nos seus recibos).

---

## 6. VERIFICACAO DO FIM DE VOO (corrida UMA vez, rc reportado)

| comando | rc | nota |
|---|---|---|
| `node --check app/electron/history-source.js` | 0 | sintaxe |
| `node --check app/electron/panel.js` | 0 | sintaxe |
| `node --check _main/live-vs-history-source-oracle.js` | 0 | sintaxe |
| `node _main/live-vs-history-source-oracle.js` | 0 | **GREEN 13/13** — o par de controlo |
| `node _main/historico-vs-redux-probe.js` | 0 | GREEN — a cura de ontem intacta |
| `node _main/panel-live-vs-history-probe.js` | 0 | GREEN 9/9 — intacta |
| `node _main/route-stamp-gate.js` | 0 | PASS 17/17 — o G4 le a guarda de rota (intacta) |

Nao corri a suite INTEIRA (`py -3 _main/_cura-oracle-suite.py` sem `--only`): as linhas
`panel-hidden-at-startup-oracle` e `run-cmd-exit-oracle` ARRANCAM O SHELL (janela) — proibido pela
minha ordem. As quatro linhas `.js` que importam a esta mudanca foram corridas a mao, acima.

---

## SELF-AUDIT

- **protocolos em falta** — faltou-me um protocolo para quando a ordem do dono CONTRADIZ um gate
  de outra lane que landou hoje. As sondas `historico-vs-redux-probe` / `panel-live-vs-history-probe`
  / `route-stamp-gate` exigem que o STORE aceite `{source:'live'}`; a ordem do dono exige que o
  HISTORY NUNCA seja do live. Nao ha' regra escrita a dizer QUAL fica onde — decidi sozinho (a
  separacao vai para o CHOKE POINT do painel, os gates preservados). Faria diferente: o brief devia
  declarar que as sondas de hoje testam a INVARIANTE ANTIGA (`route=final`) e NAO a nova (fonte),
  para eu saber que preservar o store e' obrigatorio e que a separacao tem de ser no consumidor.
- **verificacao adicional** — corri a barata: executei o predicADO REAL (`history-source.js`) em vez
  de o reescrever, e o par de controlo no MESMO comando. A que NAO corri e' caro/proibido: ler o
  DOM do painel real (arranca a app = janela + device). A ultima leitura REAL do painel e'
  `_main/panel-state.json` (02:28, `namedState:"no-worker"`, `live.count:0`) — STALE, e dito.
- **checkboxes novas** — MECANICO: *antes de partir um feed por uma fonte, correr
  `grep -rn <campo> _main/*probe.js` e, se uma sonda de hoje escrever esse campo e EXIGIR
  aceitacao, a guarda NAO pode viver no store — tem de viver no consumidor.* Comando de prova:
  `node _main/live-vs-history-source-oracle.js` tem de dar `GREEN 13/13` E as tres sondas de hoje
  tem de continuar verdes no MESMO comando. E: *toda guarda de fonte nova tem de vir com uma arm
  que a ABRE* (`producer:'redux'` -> 130 linhas), senao a cura e' indistinguivel de "escrever
  nada".
- **review por outro subagente** — **sim-com-escopo**: (a) reler a escolha de por a guarda no
  choke point e NAO no store, contra as sondas de hoje (eu julgo que e' forcada, mas um reviewer
  independente pode ver um caminho que preserve as sondas e a feche ainda mais a montante);
  (b) reler se `source:'redux'` (antes `'live'`) em `panel.js:364` nao tem leitor que eu nao vi
  (grep: nao tem). Nao vale re-rever o predicado (10 linhas puras).
- **gate-doubt**:
  - **verde-de-verdade:** o GREEN 13/13 e' real: o predicado e' o FICHEIRO VIVO executado (nao um
    regex), o store e' o REAL, e as duas cores vao por caminhos DIFERENTES (0 vs 1221) no MESMO
    comando. O verde das tres sondas da casa correu sobre os ficheiros vivos. **Um verde que eu
    DESCONTO:** o oracle prova o CHOKE POINT do painel como uma PREDICADO mecanico
    (`route==='final' && isCanonicalLine`), nao executando `panel.js` (DOM-bound) — a ligacao do
    painel a esse predicado e' assercao de TEXTO (`SottoHistorySource.isCanonicalLine` presente).
    E' o mesmo compromisso que as sondas da casa usam para o painel.
  - **falta-no-gate:** o oracle NAO verifica o caminho do WRITER Python (`sotto_webview.py
    history_append`), que e' o que o arm WebView2 (a APP) usa: ele nao sabe de `producer`, so' de
    `route`. Cenario que atravessa: uma feed nova do shell que chame `history.append` com uma meta
    que PASSE a guarda do painel mas nao a do Python passa — mas a guarda do painel (o choke point)
    e' a MESMA para os dois arms (panel.js e' partilhado), logo o corte mantem-se; o buraco e' que o
    Python nao tem a SEGUNDA guarda (defesa em profundidade assimetrica).
  - **gate-melhor:** MECANICO: por no oracle uma arm que carregue o guard Python
    (`_history_provenance`/`history_append`) e verifique que ele TAMBEM recusa uma linha
    nao-canonica. Custo: `sotto_webview.py` arrasta pywebview ao `import`. NAO o escrevi — nomeado,
    dono: quem sustentar o writer Python. RED input: uma meta sem `producer` tem de dar uma linha
    SEM escrever no ficheiro.
- **confianca** — **alta** no nucleo: o defeito esta' citado com `file:line`, a cura esta' provada
  com o par de controlo no MESMO comando, e as tres sondas de hoje continuam verdes + os non-goals
  provados por sha. **media** em: (1) a ligacao painel->predicado e' assercao de TEXTO (o painel e'
  DOM-bound); (2) o writer Python nao exercido.
- **nao verificado** — (1) o DOM do painel real (arranca a app = janela/device, proibido);
  `_main/panel-state.json` e' de 02:28 e STALE. (2) `sotto_webview.py history_append` ao VIVO.
  (3) a suite INTEIRA (`_cura-oracle-suite.py` sem `--only`) — duas linhas arrancam o shell.
  (4) o motor Parakeet Redux — nao existe no disco (por isso `media`, nao `alta`, no fecho).

---

## CACHE/PRICE

Comando: `bash I:/!manager/scripts/cache-task-report.sh SottoLiveVsHistory` — **rc=0**.

```
## CACHE/PRICE
- task/agent: SottoLiveVsHistory
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoLiveVsHistory.jsonl
- cache: read=3943040 write=0 hit=96.0885% (cache-read / input+cache-read); universe: 31 usage rows ...; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 ... | opencode-go-1/deepseek-flash: calls=29 ... | opencode-go-1/mimo-v2.6-flash: calls=1 ...
- when-failed: break_items=3; WHEN=2026-10-07T05:31:49.642000+00:00 | break_items=3; WHEN=2026-10-07T05:31:50.559000+00:00 | break_items=2; WHEN=2026-10-07T05:33:47.856000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 126270 OMP prefix-ledger rows ...)
- where-failed: session_id=01a114d8-a20a-71fe-ad15-a8936422d1e8 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791351109642 | ... provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791351110559 | ... provider=deepseek-flash model=deepseek-flash item_index=64; turn_id=1791351227856
- report generated_at: 2026-10-07T05:36:08.033923+00:00
- usage rows: 31
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 160511
- output tokens: 42042
- cache-read tokens: 3943040
- cache-write tokens: 0
- hit ratio: 96.0885% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; ... exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; ...)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

WHEN/WHERE failed: os 3 prefix-breaks deste lane caem em `05:31:49..05:33:47Z`
(session `01a114d8-…`, `provider=cline-pass`/`deepseek-flash`, `item_index=0/64`) — coincidem com
as injecoes do SELO DO DONO no meio do turno, nao com um corte do prefixo do trabalho em si.
`price` e' $0.00000000 reportado pelo provider (rotas free / opencode-go sem preco gravado).

---

## FICHEIROS DESTA LANE

```
app/electron/history-source.js               (NOVO — o predicado da fonte)
app/electron/panel.html                      (M — carrega o predicado antes de panel.js)
app/electron/panel.js                        (M — a guarda de fonte no choke point)
_main/live-vs-history-source-oracle.js       (NOVO — o par de controlo)
_main/receipt-20261007-live-vs-history-source.md   (este recibo)
history-verify/source-{as-shipped,redux,before}/   (roots descartaveis do oracle; nao versionados)
```

NOTA: `history-verify/` e' untracked (nao esta' em `.gitignore`, que so' ignora `history/`) — as
outras sondas da casa ja' escrevem la' (`plvh-*`, `hvr-*`); o oracle segue a mesma pratica e nao
introduz um diretorio novo.
