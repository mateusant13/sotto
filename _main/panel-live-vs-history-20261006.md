# Sotto — painel: o campo LIVE (nvidia) e o campo HISTORY — medicao, defeito e cura

Lane: `SottoPanelLiveHistory` · 2026-10-06 · alvo **`H:/sotto`** (nada foi escrito em `I:/!manager`;
a unica interaccao com o manager foi a disposicao do passe do teorista que o hook exigiu).

Ordem do dono, verbatim:

> *"o live nvidia do painel do sotto é pra ser o nvidia funcionando, enquanto o historico nao é
> pra ser NUNCA o historico do live nvidia. é pra ser do parakeet redux. e eu to vendo q nao ta
> desse jeito"*

---

## 0. VEREDICTO

**(a) Os DOIS campos liam a MESMA fonte.** O produtor e' **um so** e alimenta os dois: a funcao
que PINTA a caixa ao vivo (`panel.js addCaption`) e' a MESMA que escreve o historico
(`recordHistory`), chamada no seu interior. O `HISTORY` e' literalmente o historico do `LIVE`
nvidia — que e' exactamente o que o dono proibe.

**(b) A guarda que devia separar os dois era VACUA.** Existia o vocabulario de rota
(`final` / `provisional-draft`) e tres guardas (painel + dois stores), mas **nenhum produtor
estampava a rota**: o motor nao a calculava, `caption-formulation.js` nao tinha a palavra `route`,
e `panel.js:325` fazia `const route = (meta && meta.route) || 'final'` — o *default* permissivo
tornava tudo `final` e TUDO entrava no historico. Medido (§4): **1221 de 1221** linhas na caixa
eram tambem 1221 no historico, todas `route=null`.

**(c) A cura: PARTIR O FEED.** O motor passa a estampar a rota, e o painel passa a ser
FAIL-CLOSED. A caixa ao vivo fica intacta; o historico so' aceita a linha FECHADA.

---

## 1. MEDICAO — `file:line` de cada campo (ANTES da cura)

| campo | rotulo | DOM que recebe | fonte do TEXTO (cadeia) |
|---|---|---|---|
| **LIVE** (nvidia) | `panel.html:166` — `<span class="history__label">Live &middot; NVIDIA</span>` | `panel.html:183` `<ol id="caption-list">` | `panel.js:207 addCaption()` (pinta) ← `panel.js:88 onCommit` ← `panel.js:156 wireCaptions` `bridge.onCaption` ← `sotto_webview.py:2371 on_worker_caption` ← `sotto_webview.py:3112 meta` ← worker `sotto_worker.py:_event` (o motor nvidia: `worker/config.json` `model.dir = models/nemotron-3.5-asr-streaming-0.6b-int8`) |
| **HISTORY** | `panel.html:109` — `<span class="history__label">History &middot; Redux</span>` | `panel.html:157` `<ol id="history-list">` | `panel.js:207 recordHistory(...)` — **chamada DENTRO de `addCaption`**, o mesmo caminho do LIVE — → `panel.js:303 recordHistory()` → `historyApi.append` → `sotto_webview.py:2056 history_append` / `history-store.js append` |

**Os dois campos leem a MESMA fonte.** `addCaption` (o campo LIVE) chama `recordHistory` (o campo
HISTORY) na sua ultima linha util (`panel.js:207`), com o **mesmo objecto de texto**:

```
panel.js:88   onCommit: (text, reason, meta) => addCaption(text, reason, meta),
panel.js:175  function addCaption(text, reason, meta) {          <- PINTA o LIVE
panel.js:207    recordHistory(text, reason, meta);               <- ESCREVE o HISTORICO
```

`grep -rn "recordHistory" app/ | grep -v node_modules` → **um unico call site**, dentro do LIVE.
Um produtor, dois campos.

---

## 2. A CAUSA da guarda vacua (medida, nao deduzida)

```
$ node _main/historico-vs-redux-probe.js          # a sonda da casa para esta classe
commits   : 1221 handed to the panel — {"null":1221}
on disk   : 1221 line(s) in 1 file(s) — {"null":1221}
[FAIL] every line on disk is a worker-closed line (route=final)
       real = ["null"]   want = ["final"]
RESULT: RED — 2 violation(s)
```

Todas as rotas sao `null`. A razao, com `file:line`:

- `app/electron/caption-formulation.js:284` `commit()` chamava `onCommit(line, reason)` — **sem
  meta**, logo `addCaption` recebia `meta === undefined`;
- `grep -n route app/electron/caption-formulation.js` → **(none)**: o motor nunca produzia rota;
- `app/electron/panel.js:325` `const route = (meta && meta.route) || 'final';` — com `meta`
  indefinido, `route === 'final'` **sempre** → a guarda `if (route !== 'final') return;` nunca
  disparava;
- `app/electron/history-store.js:97` e `app/webview/sotto_webview.py:2067` recusam apenas
  `'provisional-draft'` — que **ninguem estampava** — logo tambem nao travavam nada.

Isto e' exactamente a assinatura que o dono ve: a caixa ao vivo e o historico com o MESMO texto.

---

## 3. A CURA (o diff)

### 3.1 `app/electron/caption-formulation.js` — o motor passa a ESTAMPAR a rota

sha256 DEPOIS desta lane: `c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83` (25790 B).
O ANTES nao tem hash honesto a dar: o ficheiro ja' tinha **edicoes nao-commitadas de outra lane**
(`git status` → `M app/electron/caption-formulation.js`), logo `git show HEAD:` e' outra arvore e
`git diff` **nao** esta' limitado a esta lane — a mesma lei "um commit escopado ao ficheiro nao e'
escopado as minhas edicoes". O ANTES fica registado pelo **comportamento** (§4, `route = null`) e
pelos hunks abaixo.

- estado novo (`bufferFinal`, `bufferSawFinal`, `lineStart`) e o predicado `routeFor(reason)`
  (linhas `268-302`);
- `takeBuffer()` limpa-os (linhas `337-341`);
- `commit()` le a rota antes de esvaziar e passa-a no meta:
  ```
  const route = routeFor(reason);          // 349
  const start = lineStart;                 // 350
  ...
  onCommit(line, reason, { route, start });  // 322
  ```
- `ingest()` regista o voto do worker (linhas `476-478`):
  ```
  if (meta && typeof meta.final === 'boolean') bufferSawFinal = true;
  if (meta && meta.final === true) bufferFinal = true;
  if (lineStart === null) lineStart = start;
  ```

A regra, em uma linha (`routeFor`):

```
if (bufferFinal)      -> 'final'             # o WORKER disse que fechou (final:true) — o "redux"
if (bufferSawFinal)   -> 'provisional-draft' # o worker votou LIVE (final:false)
senao                 -> 'provisional-draft' se o reason for um PRAZO DO PAINEL
                          (hold-timeout | status-change | flush), senao 'final'
```

O voto do worker VENCE quando existe (os dois sentidos). O `senao` e' o que salva a producao de
hoje: o worker **nao** estampa `final` (§6), e sem esta metade o historico ficaria VAZIO; com ela,
o historico recebe as linhas que o AUDIO fechou e NUNCA os fragmentos de prazo do painel (o
`flush('status-change')` a cada restart do worker — 1091 dos 1221 do §4).

Comportamento MEDIDO nos `reason` que a producao usa (motor real, um fragmento por caso):

| entrada | `reason` do commit | rota | vai ao HISTORICO? |
|---|---|---|---|
| sem `final`, 1 fragmento | `status-change` | `provisional-draft` | **nao** |
| sem `final`, 1 fragmento | `hold-timeout` | `provisional-draft` | **nao** |
| sem `final`, 1 fragmento | `stream-end` | `final` | sim |
| sem `final`, 1 fragmento | `audio-gap 3.00s` | `final` | sim |
| `final:false` | `status-change` | `provisional-draft` | **nao** |
| `final:true` | `stream-end` | `final` | sim |

### 3.2 `app/electron/panel.js` — a guarda passa a FAIL-CLOSED

```
- const route = (meta && meta.route) || 'final';
- if (route !== 'final') return;
+ // FAIL-CLOSED (owner 2026-10-06). ... (comentario, linhas 325-334)
+ const route = meta && meta.route;
+ if (route !== 'final') return;
```

`panel.js` (sha256 `135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962`).
Uma rota AUSENTE deixa de ser tratada como `final` — era essa a vacuidade.

### 3.3 O que NAO foi tocado, de proposito

- `panel.html` / `panel.css`: os rotulos ficam. `Live · NVIDIA` diz a verdade (o motor e' o nvidia,
  `worker/config.json` `model.dir`); `History · Redux` passa a dizer a verdade **no vocabulario do
  codigo** — a linha fechada ("redux"), e nao a legenda ao vivo (ver §6 para o limite).
- `app/webview/sotto_webview.py:2067` e `app/electron/history-store.js:97`: as guardas do store
  ficam como estao (defesa em profundidade; e a sonda da casa testa-as por texto, §4).
- `worker/**`: **nao** tocado (non-goal: sem mudancas de ASR/selecao de modelo; e o ficheiro
  `worker/sotto_worker.py` **nao existe** no disco agora — `git status` → `D worker/sotto_worker.py`).

---

## 4. NON-VACUIDADE — a MESMA sonda, valor DIFERENTE antes/depois

Sonda nova: `_main/panel-live-vs-history-probe.js` (sha256
`50fc0a373024d47d1113b47b287d9150ba8594ba80936d9ff6426369eed86f91`). Le um stream REAL gravado
(`_main/_route-stream-long.jsonl`, 1226 eventos, 135 `final:true` / 1091 `final:false`), corre-o
pelo **motor real** e entrega cada commit ao **store real**, em roots descartaveis. O ANTES e' uma
MUTACAO do proprio motor (`const route = routeFor(reason)` → `const route = null`), construida em
COPY no run — nunca o ficheiro vivo.

```
$ cd H:/sotto && node _main/panel-live-vs-history-probe.js
stream    : _main\_route-stream-long.jsonl — 1226 event(s) (final:true 135, final:false 1091)
engine    : app\electron\caption-formulation.js
panel     : app\electron\panel.js   guard(if (route !== 'final') return;) present=true

BEFORE (engine with `route = null` — the defect the owner saw)
  LIVE    : 1221 commit(s) handed to the panel — {"null":1221}
  HISTORY : panel accepted 1221, on disk 1221 line(s) — {"null":1221}

AFTER  (the shipped engine)
  LIVE    : 1221 commit(s) handed to the panel — {"provisional-draft":1091,"final":130}
  HISTORY : panel accepted 130, on disk 130 line(s) — {"final":130}

AFTER  (a stream that stamps NO `final` — fail-closed, the "NUNCA" half)
  LIVE    : 1221 commit(s) handed to the panel — {"provisional-draft":1221}
  HISTORY : panel accepted 0, on disk 0 line(s) — {}

AFTER  (same stream, NATURAL cadence — the audio still closes lines)
  LIVE    : 264 commit(s) handed to the panel — {"final":264}
  HISTORY : panel accepted 264, on disk 264 line(s) — {"final":264}

--- the split, both colours of the SAME probe ---
[PASS] BEFORE: the two fields are ONE — every commit reaches the history
[PASS] AFTER : no live caption (provisional-draft) reaches the history
[PASS] AFTER : every history line is a worker-closed line (route=final)
[PASS] AFTER : the same audio still reaches the history (not "write nothing")
[PASS] AFTER : the LIVE box is untouched — the panel is still handed the live partial
[PASS] AFTER : a stream with NO `final` key writes NOTHING at the worst-case flush cadence (the "NUNCA" half)
[PASS] AFTER : a stream with NO `final` key is NOT emptied — the audio still closes lines
[PASS] AFTER : the panel guard is FAIL-CLOSED (no `|| final` default)
[PASS] control: the two values DIFFER (the probe is not vacuous)
RESULT: GREEN — 9/9 arm(s)
```

**O valor diferente, que e' a exige^ncia:** `on disk` **1221 → 130** (e `{"null":1221}` →
`{"final":130}`). Duas linhas, um unico comando.

A sonda da CASA para a mesma classe tambem virou verde com a cura, e o valor mudou:

```
$ node _main/historico-vs-redux-probe.js
commits   : 1221 handed to the panel — {"provisional-draft":1091,"final":130}
on disk   : 130 line(s) in 1 file(s) — {"final":130}
[PASS] no provisional draft reaches the transcript (any flush cadence)
[PASS] every line on disk is a worker-closed line (route=final)
[PASS] the same audio reached the file at all (the fix is not "write nothing")
[PASS] the LIVE BOX is untouched: the panel is still handed the provisional line
RESULT: GREEN — the transcript carries only the worker-closed line
```

---

## 5. COMO O PAINEL FOI EXERCITADO (sem janela na tela do dono)

**Headless / API read. NENHUMA janela foi aberta, nenhum porto foi ligado.**

- `node _main/panel-live-vs-history-probe.js` e `node _main/historico-vs-redux-probe.js` carregam
  o **motor real** (`app/electron/caption-formulation.js`) e o **store real**
  (`app/electron/history-store.js`) e escrevem em roots descartaveis
  (`H:/sotto/history-verify/*`) — **nunca** em `history/` do dono.
- A LEITURA do painel real (WebView2) **nao foi refeita**: a app nao corre agora, porque
  `worker/sotto_worker.py` **nao existe no disco** (`git status` → `D worker/sotto_worker.py`) e o
  shell faz spawn exactamente desse caminho (`app/webview/sotto_webview.py:65`, `:3704`).
  Arrancar a app poria uma JANELA na tela do dono e morreria sem worker — logo **nao se arranca**.
  A ultima leitura real do painel em disco e' `_main/panel-state.json` (19:52), anterior a esta
  lane e a' ausencia do worker. Dito, nao escondido.

---

## 6. LIMITES HONESTOS (o que esta lane NAO entrega)

1. **"PARAKEET REDUX" nao existe no repo.** Sem pesos, sem call site:
   `glob H:/sotto/**/*parakeet*`, `**/*.gguf`, `**/*transcribe*` → **nada**; `grep -rn parakeet
   worker/ app/` → nada. Ligar o Parakeet Redux como o ASR do historico e' uma mudanca de
   **modelo/ASR** — que o ticket proibe ("No ASR or model-selection changes"). O que esta lane
   entrega e' o **corte**: o historico ja' NAO aceita a legenda ao vivo; aceita a linha FECHADA.
   O "redux" no codigo = o STORE (`panel.html:109`), como `AGENTS.md` ja' registou.
2. **O produtor de `final` esta' AUSENTE.** O contrato do stream (`_main/_route-stream-long.jsonl`)
   e a sonda da casa exigem `"final": bool` no evento de caption (M2 do desenho,
   `worker/sotto_worker.py:_event`). Medido: **nenhum** ficheiro em `worker/` ou `app/` estampa
   essa chave (`grep '"final"' worker/ app/` → nada; HEAD do worker idem; as 3 worktrees irmas
   idem). Com o worker assim, o historico cai na regra `senao` de `§3.1` (fecha por AUDIO, nao pelo
   prazo) — **nao fica vazio**, e o `[PASS] ... NOT emptied` prova-o — mas o corte COMPLETO
   ("só a linha que o WORKER fechou") so' acontece quando o worker estampar `final:true` no
   `_close()`. Esse e' o trabalho de quem tem o assento do worker, nao desta lane (non-goal).

---

## 7. VERIFICACAO DO FIM DE VOO (corrida UMA vez, rc reportado)

| comando | rc | nota |
|---|---|---|
| `node --check app/electron/caption-formulation.js` | **0** | sintaxe |
| `node --check app/electron/panel.js` | **0** | sintaxe |
| `node --check _main/panel-live-vs-history-probe.js` | **0** | sintaxe |
| `node app/electron/transcript-append-oracle.js` | **0** | GREEN — "every worker line is appended once, in order, word for word" |
| `node _main/historico-vs-redux-probe.js` | **0** | GREEN — the transcript carries only the worker-closed line |
| `node _main/panel-live-vs-history-probe.js` | **0** | GREEN — 9/9 arm(s) |
| `node _main/history-route-oracle.js` | **2** | SETUP ERROR: `worker/sotto_worker.py` ausente — **pre-existente e independente desta lane** |
| `py -3 _main/caption-lines-oracle.py` | **1** | `ModuleNotFoundError: No module named 'sotto_worker'` — mesma causa (worker ausente) |

## SELF-AUDIT

- **protocolos em falta** — senti falta de um protocolo que diga qual e' o produtor NORMATIVO do
  `route` (worker vs motor). Os docs `docs/audit/ao-vivo-vs-redux.md` §5 e `historico-vs-redux.md`
  descrevem M1-M4 **no worker**, mas o codigo vivo nao tem o call site, e a sonda da casa assume-o.
  Faria diferente: abrir com uma pergunta de contrato "quem estampa `final`?" antes de tocar
  consumidores — foi o que consumiu mais tempo aqui.
- **verificacao adicional** — corrida e' barata: um arm que da' um stream **sem** `final` e mostra
  que o historico nao fica vazio (adicionado, `legacyNatural`, §4 `[PASS] ... NOT emptied`). Sem
  ela, a cura pareceria esvaziar o historico em producao.
- **checkboxes novas** — (mecanico) *antes de partir um feed por uma flag, correr
  `grep -rn "<flag>" worker/ app/ | grep -v node_modules` e, se o produtor nao existir, declarar a
  dependencia no recibo*; e *toda cura de feed termina com `node <probe> | tail -3` mostrando um
  valor DIFERENTE do ANTES, no MESMO comando*.
- **review por outro subagente** — **sim-com-escopo**: um reviewer independente que leia
  `app/electron/caption-formulation.js` `routeFor()` e diga se a metade "senao" viola o pedido
  "NUNCA o historico do live nvidia" (eu julgo que nao: exclui o `status-change`/`hold-timeout`,
  que foi o mecanismo medido; mantem as linhas que o AUDIO fechou).
- **gate-doubt**
  - **verde-de-verdade:** os verdes que corre: `historico-vs-redux-probe` GREEN e
    `panel-live-vs-history-probe` 9/9 GREEN. **PODIAM ter passado vacuosos e a segunda existe
    precisamente para isso:** a sonda da casa so' e' RED-able pelo `--gate-off` (mutacao do store);
    a minha prova o mutante do MOTOR (`route = null`) DENTRO do mesmo comando, e o `[PASS] control:
    the two values DIFFER` falha se os dois lados derem o mesmo numero. O verde e' real: 1221 vs 130.
  - **falta-no-gate:** a sonda da casa testa o store e o TEXTO do `panel.js`, mas **nao egxecuta**
    o `panel.js` (DOM-bound) e **nao verifica** que o motor estampa a rota a partir de `meta.final`;
    uma mudanca futura que faca `routeFor` devolver sempre `'final'` deixa a sonda VERDE no stream
    com `final` (130 linhas) e reintroduz o defeito em silencio. Cenario: alguem troca a metade
    `senao` por `'final'` fixo.
  - **gate-melhor:** um arm que corre o motor com o stream SEM `final` e exige `on disk == 0` no
    cadence de flush maximo; e' a minha arm
    `[PASS] a stream with NO final key writes NOTHING at the worst-case flush cadence`. Input que a
    deixa RED: `routeFor` com a metade `senao` trocada por `'final'`.
- **confianca** — **media-alta**. Alta na MEDICAO (os dois campos leem a mesma fonte, provado por
  `file:line` + sonda) e no CORTE (1221 → 130, 9/9). Media na entrega ao dono porque o corte
  COMPLETO depende do `final` que o worker nao estampa (§6.2) — o que muda isso e': o worker
  estampar `final:true` em `_close()`, e o stream da sonda virar producao.
- **nao verificado** — (1) a app REAL / WebView2 com a cura a correr (worker ausente, §5);
  (2) `history-route-oracle.js` (rc=2) e `caption-lines-oracle.py` (rc=1) — bloqueados pelo worker
  ausente, pre-existentes; (3) `panel-exit3-oracle.py` / `dom-probe.js` — nao corridos (precisam da
  app); (4) o corte com `final` a chegar de um worker real (so' o fixture prova).

---

## CACHE/PRICE
- task/agent: SottoPanelLiveHistory
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoPanelLiveHistory.jsonl
- cache: read=17485824 write=0 hit=98.5448% (cache-read / input+cache-read); universe: 83 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoPanelLiveHistory.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN � not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=80 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/deepseek-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000; opencode-go-4/deepseek-flash $0.00000000 vs $0.00000000 over 83 of 83 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T22:47:28.304000+00:00 | break_items=3; WHEN=2026-10-06T22:47:29.083000+00:00 | break_items=3; WHEN=2026-10-06T22:47:30.415000+00:00 | break_items=2; WHEN=2026-10-06T22:48:52.486000+00:00 | break_items=1; WHEN=2026-10-06T22:53:49.900000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 123290 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelLiveHistory']; window: 2026-10-06T22:47:28.304000+00:00..2026-10-06T22:53:49.900000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791326848304 | session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791326849083 | session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791326850415 | session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=31; turn_id=1791326932486 | session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=146; turn_id=1791327229900 (state=RESOLVED-BREAKS-OMP; population: 5 of 123290 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelLiveHistory']; window: 2026-10-06T22:47:28.304000+00:00..2026-10-06T22:53:49.900000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T23:03:34.410342+00:00
- usage rows: 83
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash, opencode-go-4/deepseek-flash
- input tokens: 258218
- output tokens: 88949
- cache-read tokens: 17485824
- cache-write tokens: 0
- hit ratio: 98.5448% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN � not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=80 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/deepseek-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000; opencode-go-4/deepseek-flash $0.00000000 vs $0.00000000 over 83 of 83 matched usage rows
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 5 of 123290 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelLiveHistory']; window: 2026-10-06T22:47:28.304000+00:00..2026-10-06T22:53:49.900000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T22:47:28.304000+00:00; WHERE session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791326848304
  - break_items=3; WHEN=2026-10-06T22:47:29.083000+00:00; WHERE session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791326849083
  - break_items=3; WHEN=2026-10-06T22:47:30.415000+00:00; WHERE session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791326850415
  - break_items=2; WHEN=2026-10-06T22:48:52.486000+00:00; WHERE session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=31; turn_id=1791326932486
  - break_items=1; WHEN=2026-10-06T22:53:49.900000+00:00; WHERE session_id=01a11365-df40-72d2-8915-eb558ad86aba provider=deepseek-flash model=deepseek-flash item_index=146; turn_id=1791327229900
- verdict: UNKNOWN � no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
