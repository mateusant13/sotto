# Sotto — o GATE da estampilha de rota: a arm que o buraco `falta-no-gate` nomeou

Lane: `RouteStampGate` · 2026-10-06 · alvo **`H:/sotto`** (nada foi escrito fora do repo; a unica
interaccao com o manager foi a disposicao dos passes do teorista que o hook exigiu).

Ordem do dono, verbatim:

> *"o live nvidia do painel do sotto é pra ser o nvidia funcionando, enquanto o historico nao é
> pra ser NUNCA o historico do live nvidia. é pra ser do parakeet redux. e eu to vendo q nao ta
> desse jeito"*

O que esta lane entrega e' **o gate que o recibo anterior nomeou para dispatch**, nao a cura (a cura
ja' landou). Nada do motor foi editado: a mutacao vive numa COPY descartavel.

---

## 0. VEREDICTO

**A arm landou, e ela e' RED-able pela regressao exacta.** Ficheiro novo:
`_main/route-stamp-gate.js` (sha256 `d86a1b80d003cb4ba7097450a1e52e278b7b3a72eb54a9a6d94a485accae93ea`).

- **GREEN** contra o motor SHIPPED: `node _main/route-stamp-gate.js` → **rc 0**, `GATE: PASS — 8/8`.
- **RED** contra uma COPY com a metade `else` de `routeFor` forçada a `'final'`:
  `node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js` → **rc 1**, `GATE: RED — 7/8`,
  e **exactamente uma arm** vira RED: a `G3`.
- O motor LIVE nunca foi aberto para escrita: `sha256` identico antes e depois
  (`c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83`), e `diff` contra a copy mostra
  os 3 versos substituidos e mais nada.

---

## 1. O BURACO, com `file:line`

O recibo anterior (`_main/panel-live-vs-history-20261006.md`, §SELF-AUDIT `falta-no-gate` +
`gate-melhor`) nomeou-o assim: *"a sonda da casa testa o store e o TEXTO do `panel.js`, mas nao
executa o `panel.js` (DOM-bound) e nao verifica que o motor estampa a rota a partir de `meta.final`;
uma mudanca futura que faca `routeFor` devolver sempre `'final'` deixa a sonda VERDE no stream com
`final` e reintroduz o defeito em silencio."*

O mecanismo, medido no codigo em frente (o motor SHIPPED, hoje):

| onde | o que faz |
|---|---|
| `app/electron/caption-formulation.js:296-302` | `routeFor(reason)`: `bufferFinal`→`'final'`; `bufferSawFinal`→`'provisional-draft'`; senao **o prazo do PAINEL** (`hold-timeout`/`status-change`/`flush`, `:294`)→`'provisional-draft'`, **else**→`'final'` |
| `app/electron/caption-formulation.js:349` | `const route = routeFor(reason);` — a unica expressao que decide a rota de cada commit |
| `app/electron/caption-formulation.js:476-477` | `if (typeof meta.final === 'boolean') bufferSawFinal = true; if (meta.final === true) bufferFinal = true;` — a ORIGEM da rota e' `meta.final` |
| `app/electron/panel.js:335-336` | `const route = meta && meta.route; if (route !== 'final') return;` — o choke point FAIL-CLOSED |
| `app/electron/history-store.js:97` | o store recusa `provisional-draft` (defesa em profundidade) |

**Porque o fixture sozinho NAO e' um gate.** Com o mutante ("o else-half devolve `'final'`
incondicionalmente"), o stream GRAVADO continua a produzir `{'provisional-draft':1091,'final':130}` —
porque os 1091 eventos `final:false` **votam** pelo ramo `bufferSawFinal`, que o mutante nao toca.
Medido, verbatim da corrida RED:

```
--- the FIXTURE (final:true/false present), same flush cadence ---
  LIVE   : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}
  MUTANT : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}
```

O fixture nao distingue os dois motores. **O que distingue e' um stream SEM a chave `final`** — e e'
por isso que a arm e' a "no final key".

---

## 2. A ARM, em uma linha

`_main/route-stamp-gate.js:216-218`:

```js
function armNoFinalWritesNothing(r) {
  return r.disk.count === 0;
}
```

Aplicada ao cenario **"um stream que NAO estampa `final`, no pior caso do painel
(`flush('status-change')` depois de CADA evento)"**, exigindo `true`. As duas metades sao necessarias:
sem o *stream sem `final`* o fixture tapa o mutante (§1); sem o *pior caso de flush* a arm mediria o
fecho natural do audio, nao o prazo do painel — que foi o MECANISMO MEDIDO do defeito
(1091/1221 `reason=status-change`).

E as duas mutacoes, como expressoes do proprio ficheiro (nunca via git — a cura esta' uncommitted):

- **DEFECT** (`_main/route-stamp-gate.js:84-86`): `const route = routeFor(reason);` →
  `const route = null;` — a arvore PRE-CURA, em que o painel tinha o default permissivo
  `(meta && meta.route) || 'final'` e TUDO entrava.
- **MUTANT** (`:87-89`): a expressao que `routeFor` usa no ramo de prazo —
  ``return PANEL_DEADLINE_REASON.test(…)\n ? 'provisional-draft'\n : 'final';`` — trocada por
  ``return 'final';``. **Leitura exacta do ticket**: "o else-half devolve `'final'`" significa que o
  fall-through fica incondicional, i.e. o TESTE DE PRAZO desaparece. (O `else` do ternario ja' devolve
  `'final'` hoje; o que o mutante mata e' a condicao que o guarda.)

Ambas sao **verificadas presentes e unicas antes de usar** (`:126-136`): se um refactor do motor mudar
a forma, o gate morre em **SETUP ERROR rc 2**, nunca passa vacuoso. E ambas reportam `changed` +
`matches` numa arm propria (`CONTROL: the gate is not vacuous — BOTH mutations bit the engine source,
once each`).

---

## 3. GREEN — contra o motor SHIPPED (verbatim)

```
$ cd H:/sotto && node _main/route-stamp-gate.js ; echo rc=$?
stream    : _main\_route-stream-long.jsonl — 1226 event(s) (final:true 135, final:false 1091)
engine    : app\electron\caption-formulation.js
store     : app\electron\history-store.js
panel     : app\electron\panel.js   guard(if (route !== 'final') return;) present=true

--- THE ARM: a stream with NO `final` key, worst-case `status-change` flush after EVERY event ---
  LIVE   (shipped engine)                    : 1221 commit(s) {"provisional-draft":1221}, panel accepted 0, on disk 0 — {}
  DEFECT (const route = null — the owner saw): 1221 commit(s) {"null":1221}, panel accepted 1221, on disk 1221 — {"null":1221}
  MUTANT (routeFor else -> 'final')          : 1221 commit(s) {"final":1221}, panel accepted 1221, on disk 1221 — {"final":1221}

--- the FIXTURE (final:true/false present), same flush cadence ---
  LIVE   : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}
  MUTANT : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}

--- the gate, both colours of the SAME command ---
[PASS] G1 ORIGIN: the engine stamps the route from `meta.final`, and the worker's vote beats the panel deadline
       real = ["provisional-draft","provisional-draft","final"]
       want = ["provisional-draft","provisional-draft","final"]
[PASS] G2 FIXTURE: the history carries ONLY the worker-closed line
       real = {"onDisk":{"final":130},"provisionalHanded":1091}
       want = {"onDisk":{"final":130},"provisionalHanded":1091}
[PASS] G3 THE ARM: a stream with NO `final` key writes NOTHING on disk
       real = true
       want = true
[PASS] CONTROL: the SAME arm on the defect (`route = null`) is RED — the two sides AGREE
       real = false
       want = false
[PASS] CONTROL: the SAME arm on the mutant (`routeFor` else -> 'final') is RED — the named regression
       real = false
       want = false
[PASS] CONTROL: that mutant STAYS GREEN on the fixture — why the fixture alone is not a gate
       real = {"final":130}
       want = {"final":130}
[PASS] CONTROL: the defect merges the two fields (every commit is a history line)
       real = true
       want = true
[PASS] CONTROL: the gate is not vacuous — BOTH mutations bit the engine source, once each
       real = {"defectChanged":true,"defectMatches":1,"mutantChanged":true,"mutantMatches":1}
       want = {"defectChanged":true,"defectMatches":1,"mutantChanged":true,"mutantMatches":1}

GATE: PASS — 8/8 arm(s) (live GREEN, and the same arm RED on both mutations)
rc=0
```

**A arm e' RED-able DENTRO do proprio comando verde.** `G3` e' avaliada em tres motores na mesma
corrida: `true` no shipped, `false` no DEFECT, `false` no MUTANT. Um gate cujo vermelho so' se ve'
noutra corrida e' um gate que pode apodrecer; este carrega o vermelho consigo.

---

## 4. RED — com a mutacao numa COPY (verbatim)

```
$ cd H:/sotto && node _main/route-stamp-gate.js --emit-mutant _main/_route-stamp-red-copy.js ; echo rc=$?
WROTE H:\sotto\_main\_route-stamp-red-copy.js
  the `routeFor`-else mutant COPY (the live engine is untouched)
  run it RED:  node _main/route-stamp-gate.js --engine _main\_route-stamp-red-copy.js
rc=0

$ node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js > _main/_route-stamp-gate-red.txt 2>&1 ; echo rc=$?
rc=1
```

`_main/_route-stamp-gate-red.txt` (verbatim):

```
stream    : _main\_route-stream-long.jsonl — 1226 event(s) (final:true 135, final:false 1091)
engine    : _main\_route-stamp-red-copy.js   === ENGINE UNDER TEST: NOT the live file (app\electron\caption-formulation.js) — RED is expected ===
store     : app\electron\history-store.js
panel     : app\electron\panel.js   guard(if (route !== 'final') return;) present=true

--- THE ARM: a stream with NO `final` key, worst-case `status-change` flush after EVERY event ---
  LIVE   (shipped engine)                    : 1221 commit(s) {"final":1221}, panel accepted 1221, on disk 1221 — {"final":1221}
  DEFECT (const route = null — the owner saw): 1221 commit(s) {"null":1221}, panel accepted 1221, on disk 1221 — {"null":1221}
  MUTANT (routeFor else -> 'final')          : 1221 commit(s) {"final":1221}, panel accepted 1221, on disk 1221 — {"final":1221}

--- the FIXTURE (final:true/false present), same flush cadence ---
  LIVE   : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}
  MUTANT : 1221 commit(s) {"provisional-draft":1091,"final":130}, panel accepted 130, on disk 130 — {"final":130}

--- the gate, both colours of the SAME command ---
[PASS] G1 ORIGIN: the engine stamps the route from `meta.final`, and the worker's vote beats the panel deadline
       real = ["provisional-draft","provisional-draft","final"]
       want = ["provisional-draft","provisional-draft","final"]
[PASS] G2 FIXTURE: the history carries ONLY the worker-closed line
       real = {"onDisk":{"final":130},"provisionalHanded":1091}
       want = {"onDisk":{"final":130},"provisionalHanded":1091}
[FAIL] G3 THE ARM: a stream with NO `final` key writes NOTHING on disk
       real = false
       want = true
[PASS] CONTROL: the SAME arm on the defect (`route = null`) is RED — the two sides AGREE
       real = false
       want = false
[PASS] CONTROL: the SAME arm on the mutant (`routeFor` else -> 'final') is RED — the named regression
       real = false
       want = false
[PASS] CONTROL: that mutant STAYS GREEN on the fixture — why the fixture alone is not a gate
       real = {"final":130}
       want = {"final":130}
[PASS] CONTROL: the defect merges the two fields (every commit is a history line)
       real = true
       want = true
[PASS] CONTROL: the gate is not vacuous — BOTH mutations bit the engine source, once each
       real = {"defectChanged":true,"defectMatches":1,"mutantChanged":true,"mutantMatches":1}
       want = {"defectChanged":true,"defectMatches":1,"mutantChanged":true,"mutantMatches":1}

GATE: RED — 7/8 arm(s)
rc=1
```

**A copy e' a unica coisa mutada. A prova, no mesmo turno:**

```
$ diff app/electron/caption-formulation.js _main/_route-stamp-red-copy.js ; echo "diff rc=$?"
299,301c299
<     return PANEL_DEADLINE_REASON.test(String(reason == null ? '' : reason))
<       ? 'provisional-draft'
<       : 'final';
---
>     return 'final'; /* GATE-MUTANT: the else-half forced to 'final' (the named regression) */
diff rc=1

$ sha256sum app/electron/caption-formulation.js   # antes: c223c506…   depois: c223c506…  (IDENTICO)
c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83  app/electron/caption-formulation.js
```

A copy foi **apagada depois da demo** (`rm -f _main/_route-stamp-red-copy.js`); o gate re-gera-a em
qualquer altura com `--emit-mutant`, a partir do ficheiro vivo — que continua a ser a unica fonte.
O `--emit-mutant` **recusa** escrever sobre o motor vivo (`_main/route-stamp-gate.js:261-264`).

### 4.1 O mutante MAIS FORTE, para adjudicar a leitura do ticket

Existe uma segunda leitura possivel de "o `else` devolve `'final'": matar TAMBEM o ramo
`bufferSawFinal`. Medi-a (copy propria, apagada a seguir):

```
$ node _main/route-stamp-gate.js --engine _main/_route-stamp-strong-copy.js ; echo rc=$?
[FAIL] G1 ORIGIN: the engine stamps the route from `meta.final`, and the worker's vote beats the panel deadline
[FAIL] G2 FIXTURE: the history carries ONLY the worker-closed line
[FAIL] G3 THE ARM: a stream with NO `final` key writes NOTHING on disk
[PASS] CONTROL: that mutant STAYS GREEN on the fixture — why the fixture alone is not a gate
GATE: RED — 5/8 arm(s)
rc=1
```

(ficheiro `_main/_route-stamp-gate-strong.txt`, sha256 `264f18728de77fc1b1a83c5a5cda602b1b781c99bc1337e92bdffccd9dde5769`.)

**Adjudicacao:** o mutante mais forte **tambem** e' apanhado (3 arms RED) — logo o gate cobre as duas
leituras. Mas so' o mutante mais FRACO e' "GREEN no fixture": com o forte, o fixture vira
`{'final':1221}` e o arm `G2` cai. E' por isso que o ticket descreve o fraco — e e' por isso que o
fixture sozinho nunca podia carregar este gate.

---

## 5. NON-VACUIDADE — qual arm pinta quando os dois lados CONCORDAM, e a prova

**A arm e' a `G3`.** Quando o `LIVE` e o `HISTORY` concordam — isto e', quando TODAS as linhas ao vivo
entram no historico — a `G3` (que exige *zero* linhas no disco para um stream sem `final`) vira
`false`. Mostrado a acontecer, na corrida verde, no motor DEFECT:

```
  DEFECT (const route = null — the owner saw): 1221 commit(s) {"null":1221}, panel accepted 1221, on disk 1221 — {"null":1221}
[PASS] CONTROL: the SAME arm on the defect (`route = null`) is RED — the two sides AGREE
       real = false    want = false
[PASS] CONTROL: the defect merges the two fields (every commit is a history line)
       real = true     want = true
```

`1221 commit(s)` e `on disk 1221` — o numero IDENTICO e' a concordancia dos dois campos. E na corrida
RED a mesma arm esta' `real = false, want = true` → `[FAIL]` → rc 1. **Arm, valor medido, e a
diferenca entre os dois:** `0` (shipped) vs `1221` (mutado), no mesmo comando.

---

## 6. WIRING — quem INVOCA esta arm, com a linha

**Ninguem.** Prova (busca em todo o repo, excluindo o proprio ficheiro do gate e os seus logs):

```
$ cd H:/sotto && grep -rn "route-stamp-gate" . | grep -v node_modules
.\_main\route-stamp-gate.js:22: *   node _main/route-stamp-gate.js
.\_main\route-stamp-gate.js:25: *   node _main/route-stamp-gate.js --emit-mutant _main/_route-stamp-red-copy.js
.\_main\route-stamp-gate.js:26: *   node _main/route-stamp-gate.js --engine _main/_route-stamp-red-copy.js     # rc 1
.\_main\route-stamp-gate.js:76://   node _main/route-stamp-gate.js                          -> GREEN, rc 0
.\_main\route-stamp-gate.js:77://   node _main/route-stamp-gate.js --engine <mutant copy>   -> RED,   rc 1
.\_main\route-stamp-gate.js:270:    console.log(`  run it RED:  node _main/route-stamp-gate.js --engine ${...}`);
```

Nada mais no repo invoca probe nenhum desta classe: `.git/hooks/` tem so' os `.sample`, o
`package.json` da raiz nao tem `scripts`, e o `app/electron/package.json` declara
`transcript-append-oracle` mas nao estas sondas. E' a MESMA condicao das duas sondas irmaas
(`historico-vs-redux-probe.js`, `panel-live-vs-history-probe.js`), que a `AGENTS.md:96-97` documenta
como **comando de mao**.

**Wiring mais barato, proposto (nao landado — o ficheiro nao e' desta lane):** o
`_main/_cura-oracle-suite.py` ja' existe, ja' corre oraculos em serie e ja' landa um `receipt` JSON;
falta-lhe UMA linha na lista `ORACLES`. A suite invoca `[PY] + argv` com `cwd=REPO`
(`_main/_cura-oracle-suite.py:73`, `:56` — `VERDICT = {0:"GREEN",1:"RED",2:"UNRUNNABLE"}`), logo a
linha tem de atravessar para o `node`:

```python
    ("route-stamp-gate",
     ["-c", "import subprocess,sys;sys.exit(subprocess.call(['node','_main/route-stamp-gate.js'],cwd=r'H:/sotto'))"],
     120),
```

**A forma dessa linha foi MEDIDA, nao suposta** — corri-a exactamente assim, do repo:

```
$ cd H:/sotto && py -3 -c "import subprocess,sys;sys.exit(subprocess.call(['node','_main/route-stamp-gate.js'],cwd=r'H:/sotto'))" ; echo rc=$?
...
GATE: PASS — 8/8 arm(s) (live GREEN, and the same arm RED on both mutations)
rc=0
```

O oraculo devolve rc **0/1/2**, que e' exactamente o que a suite ja' espera — entra sem tocar em mais
nada da suite.

**Nao landei esta linha, e digo por que^:** `_main/_cura-oracle-suite.py` e' **untracked e e' o
entregavel de outra lane** (`docs/audit/predictor-carry-cura.md:172-175`: "Esta lane landou
`_main/_cura-oracle-suite.py`"). O brief nao me deu mapa de posse e a regra da casa e' "cada lane edita
os seus ficheiros". Uma linha a mais e' trivial; faze-la a um entregavel de outra lane sem coordenar
nao e'. **Quem tiver o assento da suite adiciona a linha acima (uma linha, sem tocar em mais nada) e o
buraco fecha-se mecanicamente.**

---

## 7. ADJUDICACAO DA PERGUNTA ABERTA DO REVIEW (um paragrafo)

**Confirmo o juizo da lane: o `else` de `routeFor` NAO viola o "NUNCA o historico do live nvidia" —
mas e' um ESTADO DE ESPERA, nao o corte completo, e isso tem de ficar dito.** O codigo em frente
(`caption-formulation.js:296-302`) so' chega ao `else` quando (a) nenhum fragmento do buffer votou
`final:true` (`bufferFinal` falso) E (b) nenhum votou `final:false` (`bufferSawFinal` falso) E (c) o
`reason` do fecho NAO e' um prazo do painel — `PANEL_DEADLINE_REASON = /^(hold-timeout|status-change|flush)/`
(`:294`). Os unicos `reason` que sobram na producao sao os do AUDIO e do comprimento:
`stream-end`, `audio-gap N.NNs` (`:380`) e `chars N` (`:410`); os que o dono via como "a legenda ao
vivo" (`status-change` a cada restart do worker — 1091/1221 medidos) estao **excluidos por construcao**,
e por isso a concordancia dos dois campos nao pode voltar por este ramo. O voto do worker, quando
existe, ganha nos DOIS sentidos (`:297-298`), e a partir do momento em que
`worker/sotto_worker.py:_event` estampar `final`, o ramo `else` deixa de ser consultado. A ressalva
honesta: enquanto o worker nao estampar `final` (o §6.2 do recibo anterior, ainda verdadeiro), as
linhas que o `else` admite foram fechadas pelo AUDIO, mas continuam a ser texto do MESMO motor
streaming — portanto "parakeet redux / 2a passagem" ainda nao e' a proveniencia delas. O `else` e' a
coisa que impede o historico de ficar VAZIO enquanto isso (provado pelo `G3` do `panel-live-vs-history-probe.js`:
o mesmo stream a cadencia NATURAL escreve 264 linhas); nao e' a coisa que cumpre a ordem. E o gate
landado nao depende da adjudicacao: a `G3` so' afirma que um stream SEM `final` no pior caso de flush
do painel escreve ZERO — o mecanismo exacto que o dono mandou parar.

---

## 8. FICHEIROS TOCADOS E `sha256`

| ficheiro | accao | sha256 |
|---|---|---|
| `_main/route-stamp-gate.js` | **NOVO** (o gate + a arm + as duas mutacoes) | `d86a1b80d003cb4ba7097450a1e52e278b7b3a72eb54a9a6d94a485accae93ea` |
| `_main/route-stamp-gate-20261006.md` | **NOVO** (este recibo) | nao tem auto-hash honesto (o proprio `write` muda o ficheiro); `sha256sum _main/route-stamp-gate-20261006.md` pelo leitor |
| `_main/_route-stamp-gate-green.txt` | log da corrida verde | `ba153aa80e7fa832dcff15f096993a53b74dbe26ba859cb1787e8438dc5d253c` |
| `_main/_route-stamp-gate-red.txt` | log da corrida vermelha | `5ee47a2f04692a68c838ba1075873a583149f1e0a23cce88bb5f890cbaa82e41` |
| `_main/_route-stamp-gate-strong.txt` | log do mutante forte (§4.1) | `264f18728de77fc1b1a83c5a5cda602b1b781c99bc1337e92bdffccd9dde5769` |
| `app/electron/caption-formulation.js` | **NAO TOCADO** (so' lido; a mutacao vive em copy) | `c223c506ee04088acc3c708b39cc8c4f861fb87f27b8a98f9f3e89ad4c968a83` (antes == depois) |
| `app/electron/panel.js` | NAO TOCADO | `135f9f6eae3dbb2e52bfbdfb5266842f7593cdec8f66e6d1f306bef1ae12e962` |
| `app/electron/history-store.js` | NAO TOCADO | `536160b3b11c62d2efeb2bf424bb9fcb9ded30d9b8802d0799c416f92d6979af` |
| `_main/_route-stamp-red-copy.js` | criado e **apagado** (demo do RED) | — |
| `_main/_route-stamp-strong-copy.js` | criado e **apagado** (§4.1) | — |
| `worker/**` | **NAO TOCADO** (non-goal) | — |

Os mutantes internos (`_main/_route-stamp-defect-engine.js`, `_main/_route-stamp-mutant-engine.js`)
sao apagados pelo proprio gate no fim de cada corrida (`fs.rmSync`); verificado:
`no throwaway copies on disk`. Artefactos descartaveis em `history-verify/route-stamp-*` (4 roots,
como as sondas irmaes) — **nunca** o `history/` do dono.

---

## 9. VERIFICACAO DO FIM DE VOO (corrida UMA vez, rc reportado)

| comando | rc | nota |
|---|---|---|
| `node --check _main/route-stamp-gate.js` | **0** | sintaxe |
| `node --check app/electron/caption-formulation.js` | **0** | sintaxe (ficheiro apenas lido) |
| `node _main/route-stamp-gate.js` | **0** | GATE PASS, 8/8 |
| `node _main/route-stamp-gate.js --engine <copy mutada>` | **1** | GATE RED, 7/8 — so' `G3` |
| `node _main/historico-vs-redux-probe.js` | **0** | a sonda da casa continua GREEN (nao tocada) |
| `node _main/panel-live-vs-history-probe.js` | **0** | GREEN, 9/9 (nao tocada) |
| `node app/electron/transcript-append-oracle.js` | **0** | GREEN (nao tocado) |
| `py -3 -c "…subprocess.call(['node','_main/route-stamp-gate.js'])…"` | **0** | a forma da linha de wiring do §6, medida |

**Nenhuma janela foi aberta:** o gate e' leitura de ficheiros + `require` + escrita em
`history-verify/`; nao arranca a app, nao spawna `python.exe`/electron, nao liga porto. `node` corre no
console do proprio shell da sessao (invisivel), como as sondas irmaes.

---

## SELF-AUDIT

- **protocolos em falta** — senti falta de um protocolo para **editar um entregavel de OUTRA lane
  quando o wiring so' existe dentro dele**. A regra "cada lane edita os seus ficheiros" e o pedido
  "landa o wire" colidem exactamente aqui, e resolvi-o a mao (propor + medir a forma da linha, §6).
  Faria diferente: abrir com a pergunta "em que ficheiro e' que este gate PODE landar?" ANTES de
  escrever o gate — teria moldado o gate para um ficheiro meu ja' invocado (nao ha nenhum) ou
  negociado a linha com o assento da suite no inicio, e nao no fim.
- **verificacao adicional** — corrida, e barata, fi-la: **(a)** o mutante FORTE (§4.1), que era a unica
  forma de saber se a minha leitura de "else-half → 'final'" era a do ticket ou uma mais fraca;
  **(b)** medir a forma exacta da linha de wiring em vez de a escrever de memoria (`py -3 -c …` rc 0);
  **(c)** o `[PASS] CONTROL: that mutant STAYS GREEN on the fixture`, que e' o que torna o §1 uma
  MEDICAO e nao uma afirmacao. O que ficou por fazer e seria caro: correr a arm contra um stream REAL
  novo de um worker que estampe `final` — nao existe produtor (`worker/sotto_worker.py` ausente do
  disco, `git status` → `D`).
- **checkboxes novas** — (mecanico) **toda arm de gate declara, no proprio comando, a mutacao que a
  deve deixar RED, e o `want` dessa gemea e' `false`**: aqui `G3` (`want true`) e
  `CONTROL: the SAME arm on the mutant … is RED` (`want false`) vivem no mesmo `arms[]`. Sem a gemea,
  um gate "verde" nao diz nada. Corolario: **a mutacao so' conta se o gate provar que `bit`** —
  `defectChanged/mutantChanged + matches == 1`, senao e' SETUP ERROR rc 2.
- **review por outro subagente** — **sim-com-escopo**: um revisor independente que leia
  `_main/route-stamp-gate.js` e responda (1) se a `G3` e' de facto RED-able so' pelo mutante nomeado e
  nao por um artefacto de leitura, e (2) se as minhas duas leituras de "else-half" (§2 vs §4.1) sao a
  adjudicacao certa do ticket. NAO precisa rever o motor (§1 e' leitura, nao mudanca) nem a ordem do
  dono.
- **gate-doubt**
  - **verde-de-verdade:** os verdes que corre — `GATE PASS 8/8` (rc 0), `historico-vs-redux-probe`
    GREEN, `panel-live-vs-history-probe` 9/9, `transcript-append-oracle` GREEN. **O verde da casa
    PODIA ser vacuoso** e o recibo anterior ja' o disse: a sonda da casa so' e' RED-able pelo
    `--gate-off`, que muta o STORE, nunca o MOTOR — um motor que rote tudo `'final'` deixa-a GREEN.
    O meu verde NAO e': o mesmo `arms[]` carrega duas mutacoes do motor, cada uma com o seu
    `want=false`, e a corrida RED (rc 1, §4) mostra as duas a disparar. O mutante forte (§4.1) mostra
    ainda que o verde do `G2` nao e' um artefacto de soma — ele vira RED nesse mutante.
  - **falta-no-gate:** o que **este** gate NAO verifica — e e' o resto do gap nomeado, o que sobra da
    frase "nunca EXECUTA o `panel.js`": **nao executa o `panel.js`** (DOM-bound; so' afirma a guarda
    fail-closed por TEXTO, `_main/route-stamp-gate.js:229-237`). Cenario que atravessa: alguem troca
    `panel.js:336` por `if ((meta && meta.route) || 'final' !== 'final') return;` de novo — o meu gate
    fica **GREEN**, porque ele testa a rota ate' ao STORE, nao o choke point do painel. O unico
    instrumento que fecha isso e' um DOM real (`_main/flicker-dom-oracle.js` / `dom-probe.js`), que
    precisa da app — e a app **nao se arranca** (`worker/sotto_worker.py` ausente; e poria janela).
    Fica declarado, nao escondido.
  - **gate-melhor:** o check mecanico que fecha o buraco ACIMA (o `panel.js` por TEXTO a mudar de forma
    sem que ninguem repare) e' **normalizar a guarda antes de a comparar**: extrair de `panel.js` a
    linha `const route = …;` + o teste seguinte e exigir que o TESTE seja exactamente
    `route !== 'final'` e que a ATRIBUICAO nao contenha `|| 'final'` — em vez do `includes()` literal
    de hoje. Comando: `node _main/route-stamp-gate.js` com um arm novo cujo input RED e' um `panel.js`
    de COPY com `const route = (meta && meta.route) || 'final';` restaurado (o pre-cure). **Input que
    tem de o deixar RED: `const route = (meta && meta.route) || 'final';`** — hoje passa. Para o
    buraco que ESTA lane fechou, o input que deixa RED e' o mutante nomeado (medido, §4).
- **confianca** — **alta** na arm e no gate (as duas cores medidas no mesmo comando, a mutacao provada
  a morder, o motor vivo com sha identico antes/depois). **media** no wiring: a linha de suite foi
  medida e corre rc 0, mas **nao esta' landada** e portanto hoje o gate so' corre por mao. O que muda
  isso: uma linha no `ORACLES` do `_main/_cura-oracle-suite.py` (§6), por quem tem esse assento.
- **nao verificado** — (1) o `panel.js` EXECUTADO num DOM (non-goal: precisa da app, que nao se
  arranca); (2) o corte com `final` a chegar de um worker REAL (o produtor nao existe no disco);
  (3) a suite a correr o gate por dentro (linha proposta, nao landada); (4) census de
  `history-verify/route-stamp-*` — sao roots descartaveis, recriados a cada corrida.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh RouteStampGate` — saida VERBATIM:

```
## CACHE/PRICE
- task/agent: RouteStampGate
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\RouteStampGate.jsonl
- cache: read=7037056 write=0 hit=97.2249% (cache-read / input+cache-read); universe: 49 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\RouteStampGate.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=48 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs $0.00000000 over 49 of 49 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T23:06:56.405000+00:00 | break_items=2; WHEN=2026-10-06T23:08:52.786000+00:00 | break_items=2; WHEN=2026-10-06T23:17:48.312000+00:00 | break_items=2; WHEN=2026-10-06T23:28:25.245000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 123709 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'RouteStampGate']; window: 2026-10-06T23:06:56.405000+00:00..2026-10-06T23:28:25.245000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791328016405 | session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=47; turn_id=1791328132786 | session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=139; turn_id=1791328668312 | session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=153; turn_id=1791329305245 (state=RESOLVED-BREAKS-OMP; population: 4 of 123709 OMP prefix-ledger rows attributable… [truncado na colagem; a linha completa esta' na saida do instrumento]
- report generated_at: 2026-10-06T23:33:05.300946+00:00
- usage rows: 49
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 200859
- output tokens: 64256
- cache-read tokens: 7037056
- cache-write tokens: 0
- hit ratio: 97.2249% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-go-1/deepseek-flash: calls=48 … | opencode-go-1/mimo-v2.6-flash: calls=1 …; partition sums to the reported total: … over 49 of 49 matched usage rows
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 4 of 123709 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'RouteStampGate']; window: 2026-10-06T23:06:56.405000+00:00..2026-10-06T23:28:25.245000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T23:06:56.405000+00:00; WHERE session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791328016405
  - break_items=2; WHEN=2026-10-06T23:08:52.786000+00:00; WHERE session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=47; turn_id=1791328132786
  - break_items=2; WHEN=2026-10-06T23:17:48.312000+00:00; WHERE session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=139; turn_id=1791328668312
  - break_items=2; WHEN=2026-10-06T23:28:25.245000+00:00; WHERE session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash model=deepseek-flash item_index=153; turn_id=1791329305245
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

**WHEN / WHERE failed (lido do bloco acima):** 4 prefix breaks nesta sessao — 23:06:56Z / 23:08:52Z /
23:17:48Z / 23:28:25Z, todos `session_id=01a11377-bd56-704d-884f-2bec74abb345 provider=deepseek-flash
model=deepseek-flash`, todos `state=RESOLVED-BREAKS-OMP` (population 4 of 123709 rows — artefacto de
fila/pacing do ledger de prefixos do OMP, ja' resolvido, nao uma quebra do trabalho desta lane);
`cache-write=0` e `hit=97.2249%` em 49 usage rows. `cost=$0.00000000` — reportado pelo provider, com as
taxas exactas por modelo **UNKNOWN** na mesma fonte.
